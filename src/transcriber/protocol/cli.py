"""Typed wire contracts shared by the CLI controller and preparation service."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Final, Literal

type FailureStage = Literal[
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
]

FAILURE_STAGES: Final[frozenset[FailureStage]] = frozenset(
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

_FRAME_SECONDS: Final = Decimal("0.01")


def _require_absolute_path(value: Path, field_name: str) -> None:
    if not isinstance(value, Path):
        raise TypeError(f"{field_name} must be a Path")
    if not value.is_absolute():
        raise ValueError(f"{field_name} must be an absolute path")


def _split_target_as_decimal(value: float) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("split target must be a number")
    result = Decimal(str(value))
    if not result.is_finite() or result < _FRAME_SECONDS:
        raise ValueError("split target must be finite and at least 0.01 seconds")
    return result


@dataclass(frozen=True, slots=True)
class PrepareCommand:
    """Validated command passed from the CLI boundary to the service."""

    source_media: Path
    task_work_directory: Path
    split_target_seconds: float = 30.0
    split_target_frames: int = field(init=False)

    def __post_init__(self) -> None:
        _require_absolute_path(self.source_media, "source media")
        _require_absolute_path(self.task_work_directory, "task work directory")
        seconds = _split_target_as_decimal(self.split_target_seconds)
        frames = int((seconds / _FRAME_SECONDS).to_integral_value(rounding=ROUND_FLOOR))
        object.__setattr__(self, "split_target_frames", frames)


@dataclass(frozen=True, slots=True)
class PrepareSuccess:
    """Successful preparation result rendered by the CLI controller."""

    task_work_directory: Path
    canonical_audio: Path
    manifest: Path
    segment_count: int

    def __post_init__(self) -> None:
        _require_absolute_path(self.task_work_directory, "task work directory")
        _require_absolute_path(self.canonical_audio, "canonical audio")
        _require_absolute_path(self.manifest, "manifest")
        if self.canonical_audio != self.task_work_directory / "prepared.wav":
            raise ValueError("canonical audio must be task_work_directory/prepared.wav")
        if self.manifest != self.task_work_directory / "manifest.json":
            raise ValueError("manifest must be task_work_directory/manifest.json")
        if isinstance(self.segment_count, bool) or not isinstance(self.segment_count, int):
            raise TypeError("segment count must be an integer")
        if self.segment_count < 0:
            raise ValueError("segment count must be non-negative")


@dataclass(frozen=True, slots=True)
class PrepareFailure:
    """Actionable runtime failure rendered by the CLI controller."""

    stage: FailureStage
    message: str

    def __post_init__(self) -> None:
        if self.stage not in FAILURE_STAGES:
            raise ValueError(f"unsupported failure stage: {self.stage}")
        if not isinstance(self.message, str):
            raise TypeError("failure message must be a string")
        if not self.message.strip():
            raise ValueError("failure message must be non-empty")
