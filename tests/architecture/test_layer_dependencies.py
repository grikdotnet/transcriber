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

PLANNED_ASR_MODULE_LAYERS = {
    "src/transcriber/domain/manifest.py": "domain",
    "src/transcriber/domain/transcript.py": "domain",
    "src/transcriber/protocol/asr_cli.py": "protocol",
    "src/transcriber/protocol/asr_model_manifest.py": "protocol",
    "src/transcriber/protocol/qwen_asr.py": "protocol",
    "src/transcriber/infrastructure/asr_files.py": "infrastructure",
    "src/transcriber/infrastructure/execution_provider.py": "infrastructure",
    "src/transcriber/infrastructure/llama_cpp.py": "infrastructure",
    "src/transcriber/infrastructure/process.py": "infrastructure",
    "src/transcriber/service/prepare_media.py": "service",
    "src/transcriber/service/recognize_segments.py": "service",
    "src/transcriber/composition/application.py": "composition",
    "src/transcriber/controller/asr_cli.py": "controller",
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


def _forbidden_python_dependencies(layer: str, source: Path) -> set[str]:
    return _python_dependencies(source) - ALLOWED_DEPENDENCIES[layer]


def _python_import_fixture(tmp_path: Path, dependency: str) -> Path:
    source = tmp_path / "fixture.py"
    source.write_text(
        f"from transcriber.{dependency} import fixture\n",
        encoding="utf-8",
    )
    return source


@pytest.mark.parametrize(
    ("layer", "dependency"),
    (
        ("infrastructure", "protocol"),
        ("infrastructure", "domain"),
        ("controller", "infrastructure"),
    ),
)
def test_python_layer_rejects_controlled_illegal_dependency(
    tmp_path: Path,
    layer: str,
    dependency: str,
) -> None:
    source = _python_import_fixture(tmp_path, dependency)

    forbidden = _forbidden_python_dependencies(layer, source)

    assert forbidden == {dependency}


@pytest.mark.parametrize(
    ("layer", "dependency"),
    tuple(
        (layer, dependency)
        for layer, dependencies in ALLOWED_DEPENDENCIES.items()
        for dependency in dependencies
    ),
)
def test_python_layer_allows_each_controlled_permitted_dependency(
    tmp_path: Path,
    layer: str,
    dependency: str,
) -> None:
    source = _python_import_fixture(tmp_path, dependency)

    forbidden = _forbidden_python_dependencies(layer, source)

    assert not forbidden


@pytest.mark.parametrize(
    ("module_path", "layer"),
    tuple(PLANNED_ASR_MODULE_LAYERS.items()),
)
def test_planned_asr_module_has_one_declared_layer(
    module_path: str,
    layer: str,
) -> None:
    path = Path(module_path)

    assert path.parts[:2] == ("src", "transcriber")
    assert path.parts[2] == layer
    assert layer in LAYERS


@pytest.mark.parametrize("layer", LAYERS)
def test_python_layer_exists_and_has_only_allowed_dependencies(layer: str) -> None:
    package = PYTHON_ROOT / layer
    assert package.is_dir(), f"missing planned Python layer package: {package}"
    assert (package / "__init__.py").is_file()

    for source in package.rglob("*.py"):
        forbidden = _forbidden_python_dependencies(layer, source)
        assert not forbidden, f"{source} imports forbidden layers: {sorted(forbidden)}"


@pytest.mark.parametrize("layer", NATIVE_LAYERS)
def test_native_layer_exists_and_has_only_allowed_dependencies(layer: str) -> None:
    package = NATIVE_ROOT / layer
    assert package.is_dir(), f"missing planned native layer directory: {package}"

    for source in (*package.rglob("*.cpp"), *package.rglob("*.hpp")):
        forbidden = _native_dependencies(source) - ALLOWED_DEPENDENCIES[layer]
        assert not forbidden, f"{source} includes forbidden layers: {sorted(forbidden)}"
