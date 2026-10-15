from __future__ import annotations

import sys
import tomllib
from importlib.metadata import distribution
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_project_requires_python_312_and_uses_hatchling() -> None:
    assert sys.version_info >= (3, 12)

    metadata_path = REPOSITORY_ROOT / "pyproject.toml"
    assert metadata_path.is_file()
    metadata = tomllib.loads(metadata_path.read_text(encoding="utf-8"))

    assert metadata["project"]["requires-python"] == ">=3.12,<3.13"
    assert metadata["build-system"]["build-backend"] == "hatchling.build"
    assert len(metadata["build-system"]["requires"]) == 1
    assert metadata["build-system"]["requires"][0].startswith("hatchling==")


def test_project_metadata_declares_package_and_console_entry_point() -> None:
    metadata_path = REPOSITORY_ROOT / "pyproject.toml"
    assert metadata_path.is_file()
    metadata = tomllib.loads(metadata_path.read_text(encoding="utf-8"))

    assert metadata["project"]["name"] == "transcriber"
    assert metadata["project"]["scripts"]["transcriber-prepare"] == (
        "transcriber.controller.cli:main"
    )
    assert metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/transcriber"]


def test_project_metadata_explicitly_includes_the_qwen_model_manifest() -> None:
    metadata_path = REPOSITORY_ROOT / "pyproject.toml"
    metadata = tomllib.loads(metadata_path.read_text(encoding="utf-8"))

    force_include = metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]

    assert force_include["src/transcriber/resources/asr_models/qwen3-asr-1.7b.json"] == (
        "transcriber/resources/asr_models/qwen3-asr-1.7b.json"
    )


def test_console_entry_point_loads_a_callable() -> None:
    entry_point = next(
        entry_point
        for entry_point in distribution("transcriber").entry_points
        if entry_point.group == "console_scripts" and entry_point.name == "transcriber-prepare"
    )

    assert callable(entry_point.load())


def test_diarization_entry_point_preserves_dependency_configuration() -> None:
    metadata = tomllib.loads((REPOSITORY_ROOT / 'pyproject.toml').read_text())
    assert metadata['project']['scripts']['transcriber-diarize'] == (
        'transcriber.controller.diarization_cli:main')
    assert 'numpy==2.4.2' in metadata['project']['dependencies']
    assert 'pyannote-ncnn-plda==0.1.0' in metadata['project']['dependencies']
    assert metadata['tool']['uv']['override-dependencies'] == ['numpy==2.4.2']
    assert metadata['tool']['uv']['sources']['pyannote-ncnn-plda']['rev'] == (
        '34c8982e243eda9e42834ed255067ab727410379')
