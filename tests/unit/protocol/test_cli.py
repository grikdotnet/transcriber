from __future__ import annotations

from math import inf, nan
from pathlib import Path

import pytest

from transcriber.protocol.cli import (
    FAILURE_STAGES,
    PrepareCommand,
    PrepareFailure,
    PrepareSuccess,
)


def test_prepare_command_defaults_to_thirty_second_split_target() -> None:
    command = PrepareCommand(
        source_media=Path("/media/source.mp4"),
        task_work_directory=Path("/work/task"),
    )

    assert command.split_target_seconds == 30.0
    assert command.split_target_frames == 3_000


def test_prepare_command_floors_split_target_to_complete_ten_ms_frames() -> None:
    command = PrepareCommand(
        source_media=Path("/media/source.wav"),
        task_work_directory=Path("/work/task"),
        split_target_seconds=30.009,
    )

    assert command.split_target_frames == 3_000


@pytest.mark.parametrize("value", [nan, inf, -inf, 0.009, 0.0, -1.0])
def test_prepare_command_rejects_invalid_split_targets(value: float) -> None:
    with pytest.raises(ValueError, match="split target"):
        PrepareCommand(
            source_media=Path("/media/source.wav"),
            task_work_directory=Path("/work/task"),
            split_target_seconds=value,
        )


def test_prepare_command_accepts_minimum_split_target() -> None:
    command = PrepareCommand(
        source_media=Path("/media/source.wav"),
        task_work_directory=Path("/work/task"),
        split_target_seconds=0.01,
    )

    assert command.split_target_frames == 1


@pytest.mark.parametrize("field", ["source_media", "task_work_directory"])
def test_prepare_command_requires_absolute_nonempty_paths(field: str) -> None:
    arguments = {
        "source_media": Path("/media/source.wav"),
        "task_work_directory": Path("/work/task"),
    }
    arguments[field] = Path("relative/path")

    with pytest.raises(ValueError, match="absolute"):
        PrepareCommand(**arguments)


def test_prepare_success_carries_absolute_artifact_paths_and_count() -> None:
    result = PrepareSuccess(
        task_work_directory=Path("/work/task"),
        canonical_audio=Path("/work/task/prepared.wav"),
        manifest=Path("/work/task/manifest.json"),
        segment_count=2,
    )

    assert result.segment_count == 2


@pytest.mark.parametrize(
    ("task_work_directory", "canonical_audio", "manifest"),
    [
        (Path("relative/task"), Path("/work/task/prepared.wav"), Path("/work/task/manifest.json")),
        (Path("/work/task"), Path("relative/prepared.wav"), Path("/work/task/manifest.json")),
        (Path("/work/task"), Path("/work/task/prepared.wav"), Path("relative/manifest.json")),
    ],
    ids=("relative-task-directory", "relative-canonical-audio", "relative-manifest"),
)
def test_prepare_success_rejects_relative_paths(
    task_work_directory: Path,
    canonical_audio: Path,
    manifest: Path,
) -> None:
    with pytest.raises(ValueError, match="absolute"):
        PrepareSuccess(
            task_work_directory=task_work_directory,
            canonical_audio=canonical_audio,
            manifest=manifest,
            segment_count=0,
        )


@pytest.mark.parametrize(
    ("canonical_audio", "manifest", "expected_message"),
    [
        (
            Path("/work/other/prepared.wav"),
            Path("/work/task/manifest.json"),
            "canonical audio",
        ),
        (
            Path("/work/task/prepared.wav"),
            Path("/work/other/manifest.json"),
            "manifest",
        ),
        (
            Path("/work/task/audio.wav"),
            Path("/work/task/manifest.json"),
            "prepared.wav",
        ),
        (
            Path("/work/task/prepared.wav"),
            Path("/work/task/result.json"),
            "manifest.json",
        ),
    ],
    ids=(
        "canonical-audio-outside-task",
        "manifest-outside-task",
        "wrong-canonical-name",
        "wrong-manifest-name",
    ),
)
def test_prepare_success_rejects_invalid_artifact_paths(
    canonical_audio: Path,
    manifest: Path,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        PrepareSuccess(
            task_work_directory=Path("/work/task"),
            canonical_audio=canonical_audio,
            manifest=manifest,
            segment_count=0,
        )


@pytest.mark.parametrize("segment_count", [-1, True, 1.5])
def test_prepare_success_rejects_invalid_segment_count(segment_count: object) -> None:
    with pytest.raises((TypeError, ValueError), match="segment count"):
        PrepareSuccess(
            task_work_directory=Path("/work/task"),
            canonical_audio=Path("/work/task/prepared.wav"),
            manifest=Path("/work/task/manifest.json"),
            segment_count=segment_count,  # type: ignore[arg-type]
        )


def test_failure_stage_labels_are_closed_to_the_cli_contract() -> None:
    assert (
        frozenset(
            {
                "source-media",
                "task-directory",
                "audio-extraction",
                "firered-model",
                "ncnn-runtime",
                "vad-inference",
                "vad-postprocessing",
                "interval-validation",
                "manifest",
                "segment-files",
            }
        )
        == FAILURE_STAGES
    )

    for stage in FAILURE_STAGES:
        assert PrepareFailure(stage=stage, message="actionable failure").stage == stage

    with pytest.raises(ValueError, match="failure stage"):
        PrepareFailure(stage="unknown", message="actionable failure")  # type: ignore[arg-type]


def test_prepare_failure_requires_a_nonempty_message() -> None:
    with pytest.raises(ValueError, match="message"):
        PrepareFailure(stage="source-media", message="   ")
