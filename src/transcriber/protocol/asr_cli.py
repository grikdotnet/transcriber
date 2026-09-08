"""Validated public wire values for the ASR CLI boundary."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

type AsrFailureStage = Literal[
    "task-directory",
    "segment-manifest",
    "segment-files",
    "asr-model",
    "execution-provider",
    "provider-response",
    "transcript",
    "cancelled",
]

ASR_FAILURE_STAGES: Final[frozenset[AsrFailureStage]] = frozenset(
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
)

_MODEL_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\Z")
_LANGUAGE_TAG_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*\Z"
)
_GRANDFATHERED_LANGUAGE_TAGS: Final[frozenset[str]] = frozenset(
    {
        "art-lojban",
        "cel-gaulish",
        "en-gb-oed",
        "i-ami",
        "i-bnn",
        "i-default",
        "i-enochian",
        "i-hak",
        "i-klingon",
        "i-lux",
        "i-mingo",
        "i-navajo",
        "i-pwn",
        "i-tao",
        "i-tay",
        "i-tsu",
        "no-bok",
        "no-nyn",
        "sgn-be-fr",
        "sgn-be-nl",
        "sgn-ch-de",
        "zh-guoyu",
        "zh-hakka",
        "zh-min",
        "zh-min-nan",
        "zh-xiang",
    }
)
_PROVIDER_FAILURE_STAGES: Final[frozenset[AsrFailureStage]] = frozenset(
    {"execution-provider", "provider-response"}
)


def _require_absolute_path(value: Path, field_name: str) -> None:
    if not isinstance(value, Path):
        raise TypeError(f"{field_name} must be a Path")
    if not value.is_absolute():
        raise ValueError(f"{field_name} must be an absolute path")


def _require_model_id(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("model ID must be a string")
    if _MODEL_ID_PATTERN.fullmatch(value) is None:
        raise ValueError(
            "model ID must use lowercase letters and digits separated by hyphens or dots"
        )


def _require_language(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("language must be a string")
    if (
        value != "auto"
        and (
            _LANGUAGE_TAG_PATTERN.fullmatch(value) is None
            or value.lower() in _GRANDFATHERED_LANGUAGE_TAGS
        )
    ):
        raise ValueError("language must be auto or a valid language tag")


def _require_positive_integer(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


@dataclass(frozen=True, slots=True)
class AsrCommand:
    """Validated ASR command passed from the CLI controller to the service."""

    task_work_directory: Path
    model_id: str
    language: str = "auto"

    def __post_init__(self) -> None:
        _require_absolute_path(self.task_work_directory, "task work directory")
        _require_model_id(self.model_id)
        _require_language(self.language)


@dataclass(frozen=True, slots=True)
class AsrProgress:
    """One completed recognition count rendered by the CLI controller."""

    recognized_segments: int
    total_segments: int

    def __post_init__(self) -> None:
        _require_positive_integer(self.total_segments, "total segments")
        _require_positive_integer(self.recognized_segments, "recognized segments")
        if self.recognized_segments > self.total_segments:
            raise ValueError("recognized segments cannot exceed total segments")


@dataclass(frozen=True, slots=True)
class AsrSuccess:
    """Successful ASR result rendered by the CLI controller."""

    transcript: Path
    recognized_segments: int

    def __post_init__(self) -> None:
        _require_absolute_path(self.transcript, "transcript")
        _require_positive_integer(self.recognized_segments, "recognized segments")


@dataclass(frozen=True, slots=True)
class AsrFailure:
    """Actionable ASR runtime failure rendered by the CLI controller."""

    stage: AsrFailureStage
    message: str
    model_id: str
    segment_index: int | None = None
    provider_diagnostic: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.stage, str):
            raise TypeError("failure stage must be a string")
        if self.stage not in ASR_FAILURE_STAGES:
            raise ValueError(f"unsupported failure stage: {self.stage}")
        if not isinstance(self.message, str):
            raise TypeError("failure message must be a string")
        if not self.message.strip():
            raise ValueError("failure message must be non-empty")
        _require_model_id(self.model_id)
        if self.segment_index is not None:
            if isinstance(self.segment_index, bool) or not isinstance(self.segment_index, int):
                raise TypeError("segment index must be an integer")
            if self.segment_index < 0:
                raise ValueError("segment index must be non-negative")
            if self.stage not in _PROVIDER_FAILURE_STAGES:
                raise ValueError("segment index is only valid for provider failure stages")
        if self.provider_diagnostic is not None:
            if not isinstance(self.provider_diagnostic, str):
                raise TypeError("provider diagnostic must be a string")
            if not self.provider_diagnostic.strip():
                raise ValueError("provider diagnostic must be non-empty")
            if self.stage not in _PROVIDER_FAILURE_STAGES:
                raise ValueError("provider diagnostic is only valid for provider failure stages")
