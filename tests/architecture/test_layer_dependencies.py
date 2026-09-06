from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = REPOSITORY_ROOT / "src" / "transcriber"
NATIVE_ROOT = REPOSITORY_ROOT / "native" / "firered_vad_ncnn"
LAYERS = (
    "infrastructure",
    "protocol",
    "domain",
    "service",
    "composition",
    "controller",
)
NATIVE_LAYERS = tuple(layer for layer in LAYERS if layer != "domain")

# A layer may depend only on layers explicitly listed here. The table encodes
# architecture/layers.md, including its special Controller restriction.
ALLOWED_DEPENDENCIES = {
    "infrastructure": {"infrastructure"},
    "protocol": {"protocol"},
    "domain": {"protocol", "domain"},
    "service": {"infrastructure", "protocol", "domain", "service"},
    "composition": {
        "infrastructure",
        "protocol",
        "domain",
        "service",
        "composition",
    },
    "controller": {"protocol", "domain", "service", "composition", "controller"},
}


def _python_dependencies(source: Path) -> set[str]:
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    dependencies: set[str] = set()
    for node in ast.walk(tree):
        module: str | None = None
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if len(parts) > 1 and parts[0] == "transcriber" and parts[1] in LAYERS:
                    dependencies.add(parts[1])
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            if module is not None:
                parts = module.split(".")
                if len(parts) > 1 and parts[0] == "transcriber" and parts[1] in LAYERS:
                    dependencies.add(parts[1])
                elif node.level >= 2 and parts[0] in LAYERS:
                    dependencies.add(parts[0])
            elif node.level >= 2:
                dependencies.update(alias.name for alias in node.names if alias.name in LAYERS)
    return dependencies


def _native_dependencies(source: Path) -> set[str]:
    include_pattern = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.MULTILINE)
    dependencies: set[str] = set()
    for include in include_pattern.findall(source.read_text(encoding="utf-8")):
        components = include.replace("\\", "/").split("/")
        dependencies.update(component for component in components if component in LAYERS)
    return dependencies


@pytest.mark.parametrize("layer", LAYERS)
def test_python_layer_exists_and_has_only_allowed_dependencies(layer: str) -> None:
    package = PYTHON_ROOT / layer
    assert package.is_dir(), f"missing planned Python layer package: {package}"
    assert (package / "__init__.py").is_file()

    for source in package.rglob("*.py"):
        forbidden = _python_dependencies(source) - ALLOWED_DEPENDENCIES[layer]
        assert not forbidden, f"{source} imports forbidden layers: {sorted(forbidden)}"


@pytest.mark.parametrize("layer", NATIVE_LAYERS)
def test_native_layer_exists_and_has_only_allowed_dependencies(layer: str) -> None:
    package = NATIVE_ROOT / layer
    assert package.is_dir(), f"missing planned native layer directory: {package}"

    for source in (*package.rglob("*.cpp"), *package.rglob("*.hpp")):
        forbidden = _native_dependencies(source) - ALLOWED_DEPENDENCIES[layer]
        assert not forbidden, f"{source} includes forbidden layers: {sorted(forbidden)}"
