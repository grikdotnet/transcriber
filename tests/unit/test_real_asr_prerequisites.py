"""Controlled prerequisite-policy coverage for the real ASR checkpoint."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import RealAsrPaths, enforce_real_asr_prerequisites


def test_real_asr_paths_resolve_fixed_provider_and_qwen_artifacts(tmp_path: Path) -> None:
    paths = RealAsrPaths.from_repository(tmp_path)

    assert paths == RealAsrPaths(
        repository_root=tmp_path.resolve(),
        provider=tmp_path.resolve() / "vendor" / "llama-server",
        model=tmp_path.resolve()
        / "models"
        / "qwen3-asr-1.7b"
        / "Qwen3-ASR-1.7B-Q8_0.gguf",
        audio_projector=tmp_path.resolve()
        / "models"
        / "qwen3-asr-1.7b"
        / "mmproj-Qwen3-ASR-1.7B-Q8_0.gguf",
        sample=tmp_path.resolve() / "fixtures" / "sample" / "prepared.wav",
    )


def test_optional_mode_skips_with_each_missing_fixed_prerequisite(tmp_path: Path) -> None:
    paths = RealAsrPaths.from_repository(tmp_path)

    with pytest.raises(
        pytest.skip.Exception, match="real ASR prerequisite is unavailable"
    ) as raised:
        enforce_real_asr_prerequisites(paths, required=False)

    message = str(raised.value)
    for prerequisite in paths.required_files():
        assert str(prerequisite) in message


def test_required_mode_fails_with_bounded_missing_path_details(tmp_path: Path) -> None:
    paths = RealAsrPaths.from_repository(tmp_path)

    with pytest.raises(pytest.fail.Exception, match="required real ASR prerequisite") as raised:
        enforce_real_asr_prerequisites(paths, required=True)

    message = str(raised.value)
    assert len(message) < 1_024
    for prerequisite in paths.required_files():
        assert str(prerequisite) in message


def test_present_controlled_prerequisites_proceed_without_real_artifacts(tmp_path: Path) -> None:
    paths = RealAsrPaths.from_repository(tmp_path)
    for prerequisite in paths.required_files():
        prerequisite.parent.mkdir(parents=True, exist_ok=True)
        prerequisite.touch()

    enforce_real_asr_prerequisites(paths, required=False)
    enforce_real_asr_prerequisites(paths, required=True)


def test_prerequisite_probe_treats_filesystem_errors_as_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = RealAsrPaths.from_repository(tmp_path)

    def inaccessible(_: Path) -> bool:
        raise OSError("controlled inaccessible path")

    monkeypatch.setattr(Path, "is_file", inaccessible)

    assert paths.missing_prerequisites() == paths.required_files()


@pytest.mark.parametrize("required", [False, True])
def test_missing_prerequisite_messages_are_bounded_for_extreme_paths(
    tmp_path: Path, required: bool
) -> None:
    extreme = "x" * 2_000
    paths = RealAsrPaths(
        repository_root=tmp_path,
        provider=tmp_path / extreme / "llama-server",
        model=tmp_path / extreme / "model.gguf",
        audio_projector=tmp_path / extreme / "mmproj.gguf",
        sample=tmp_path / extreme / "prepared.wav",
    )
    expected = pytest.fail.Exception if required else pytest.skip.Exception

    with pytest.raises(expected) as raised:
        enforce_real_asr_prerequisites(paths, required=required)

    assert len(str(raised.value)) <= 1_023


def test_real_asr_option_defaults_to_optional_prerequisite_policy(
    pytestconfig: pytest.Config,
) -> None:
    assert pytestconfig.getoption("--real-asr-required") is False
