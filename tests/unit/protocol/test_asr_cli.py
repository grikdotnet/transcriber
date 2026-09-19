from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from transcriber.protocol.asr_cli import (
    ASR_FAILURE_STAGES,
    AsrCommand,
    AsrFailure,
    AsrProgress,
    AsrSuccess,
)


def test_asr_command_carries_validated_absolute_task_path_model_and_language() -> None:
    command = AsrCommand(
        task_work_directory=Path("/work/task"),
        model_id="qwen3-asr-1.7b",
        language="en-GB",
    )

    assert command.task_work_directory == Path("/work/task")
    assert command.model_id == "qwen3-asr-1.7b"
    assert command.language == "en-GB"

    automatic_language = AsrCommand(
        task_work_directory=Path("/work/task"),
        model_id="qwen3-asr-1.7b",
    )

    assert automatic_language.language == "auto"
    with pytest.raises(FrozenInstanceError):
        automatic_language.model_id = "other-model"  # type: ignore[misc]


@pytest.mark.parametrize(
    "model_id",
    ("a", "0", "a-b", "a.b", "a-b.c", "qwen3-asr-1.7b"),
)
def test_asr_command_accepts_nonempty_model_id_components_with_single_separators(
    model_id: str,
) -> None:
    command = AsrCommand(task_work_directory=Path("/work/task"), model_id=model_id)

    assert command.model_id == model_id


@pytest.mark.parametrize(
    ("task_work_directory", "model_id", "language", "expected_message"),
    [
        (Path("relative/task"), "qwen3-asr-1.7b", "auto", "absolute"),
        (Path("/work/task"), "Qwen3-asr-1.7b", "auto", "model ID"),
        (Path("/work/task"), "qwen3--asr", "auto", "model ID"),
        (Path("/work/task"), "qwen3-asr-", "auto", "model ID"),
        (Path("/work/task"), "qwen3-asr.", "auto", "model ID"),
        (Path("/work/task"), ".qwen3-asr", "auto", "model ID"),
        (Path("/work/task"), "qwen3-asr..1", "auto", "model ID"),
        (Path("/work/task"), "qwen3-asr-.1", "auto", "model ID"),
        (Path("/work/task"), "qwen3-asr.-1", "auto", "model ID"),
        (Path("/work/task"), "qwen3_asr", "auto", "model ID"),
        (Path("/work/task"), "qwen3-asr", "englishxx", "language"),
        (Path("/work/task"), "qwen3-asr", "en-GB-", "language"),
        (Path("/work/task"), "qwen3-asr", "x-private", "language"),
        (Path("/work/task"), "qwen3-asr", "en-GB-oed", "language"),
        (Path("/work/task"), "qwen3-asr", "EN-gb-OED", "language"),
        (Path("/work/task"), "qwen3-asr", "zh-min-nan", "language"),
        (Path("/work/task"), "qwen3-asr", "ZH-MIN-NAN", "language"),
    ],
    ids=(
        "relative-task-directory",
        "uppercase-model-id",
        "repeated-model-hyphen",
        "trailing-model-hyphen",
        "trailing-model-version-dot",
        "leading-model-version-dot",
        "repeated-model-version-dot",
        "adjacent-hyphen-dot",
        "adjacent-dot-hyphen",
        "model-underscore",
        "long-language-primary",
        "trailing-language-subtag",
        "private-use-language",
        "grandfathered-english",
        "grandfathered-english-mixed-case",
        "grandfathered-chinese",
        "grandfathered-chinese-uppercase",
    ),
)
def test_asr_command_rejects_invalid_public_values(
    task_work_directory: Path,
    model_id: str,
    language: str,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        AsrCommand(
            task_work_directory=task_work_directory,
            model_id=model_id,
            language=language,
        )


def test_asr_progress_requires_one_based_completed_count_within_total() -> None:
    progress = AsrProgress(recognized_segments=2, total_segments=3)

    assert progress.recognized_segments == 2
    assert progress.total_segments == 3

    for recognized_segments, total_segments in ((0, 3), (4, 3), (1, 0), (True, 1)):
        with pytest.raises((TypeError, ValueError), match="segment"):
            AsrProgress(
                recognized_segments=recognized_segments,
                total_segments=total_segments,
            )


def test_asr_success_requires_absolute_transcript_and_completed_segments() -> None:
    success = AsrSuccess(
        transcript=Path("/work/task/transcripts-qwen3-asr-1.7b/transcript.json"),
        recognized_segments=3,
    )

    assert success.recognized_segments == 3

    with pytest.raises(ValueError, match="absolute"):
        AsrSuccess(transcript=Path("transcript.json"), recognized_segments=1)
    with pytest.raises(ValueError, match="recognized segments"):
        AsrSuccess(transcript=Path("/work/task/transcript.json"), recognized_segments=0)


def test_asr_failure_has_closed_stage_and_optional_segment_diagnostic_fields() -> None:
    assert frozenset(
        {
            "task-directory",
            "segment-manifest",
            "segment-files",
            "asr-model",
            "execution-provider",
            "provider-response",
            "transcript",
            "cancelled",
        }
    ) == ASR_FAILURE_STAGES

    failure = AsrFailure(
        stage="execution-provider",
        message="provider failed",
        model_id="qwen3-asr-1.7b",
        segment_index=3,
        provider_diagnostic="connection reset",
    )

    assert failure.segment_index == 3
    assert failure.provider_diagnostic == "connection reset"
    assert AsrFailure(
        stage="execution-provider",
        message="provider failed",
        model_id="qwen3-asr-1.7b",
    ).provider_diagnostic is None
    assert AsrFailure(
        stage="provider-response",
        message="malformed response",
        model_id="qwen3-asr-1.7b",
    ).segment_index is None
    assert AsrFailure(
        stage="cancelled",
        message="task cancelled",
        model_id="qwen3-asr-1.7b",
    ).segment_index is None

    with pytest.raises(ValueError, match="failure stage"):
        AsrFailure(
            stage="unknown",  # type: ignore[arg-type]
            message="provider failed",
            model_id="qwen3-asr-1.7b",
        )
    with pytest.raises(TypeError, match="failure stage"):
        AsrFailure(
            stage=1,  # type: ignore[arg-type]
            message="provider failed",
            model_id="qwen3-asr-1.7b",
        )
    with pytest.raises(ValueError, match="segment index"):
        AsrFailure(
            stage="execution-provider",
            message="provider failed",
            model_id="qwen3-asr-1.7b",
            segment_index=-1,
        )
    with pytest.raises(TypeError, match="provider diagnostic"):
        AsrFailure(
            stage="execution-provider",
            message="provider failed",
            model_id="qwen3-asr-1.7b",
            provider_diagnostic=1,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("stage", "field_name", "field_value"),
    [
        ("segment-files", "segment_index", 0),
        ("asr-model", "provider_diagnostic", "provider failed"),
    ],
    ids=("non-provider-segment-index", "non-provider-diagnostic"),
)
def test_asr_failure_allows_provider_details_only_for_provider_stages(
    stage: str,
    field_name: str,
    field_value: int | str,
) -> None:
    arguments: dict[str, object] = {
        "stage": stage,
        "message": "failure",
        "model_id": "qwen3-asr-1.7b",
    }
    arguments[field_name] = field_value

    with pytest.raises(ValueError, match="provider"):
        AsrFailure(**arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize("stage", ("execution-provider", "provider-response"))
def test_asr_failure_provider_detail_fields_are_independently_optional(stage: str) -> None:
    segment_failure = AsrFailure(
        stage=stage,  # type: ignore[arg-type]
        message="provider failed",
        model_id="qwen3-asr-1.7b",
        segment_index=0,
    )
    diagnostic_failure = AsrFailure(
        stage=stage,  # type: ignore[arg-type]
        message="provider failed",
        model_id="qwen3-asr-1.7b",
        provider_diagnostic="provider detail",
    )

    assert segment_failure.segment_index == 0
    assert diagnostic_failure.provider_diagnostic == "provider detail"
