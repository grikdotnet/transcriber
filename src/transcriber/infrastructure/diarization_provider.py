"""Python-owned diarization boundary values and runtime failures (Infrastructure)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real


def _validate_times(start_seconds: float, end_seconds: float) -> None:
    """Reject malformed times; clipping and interval ordering belong to fusion."""
    for value in (start_seconds, end_seconds):
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError("interval timestamps must be finite real numbers")


@dataclass(frozen=True, slots=True)
class NemotronInterval:
    """Copied native interval with a positive recording-local integer identity."""

    start_seconds: float
    end_seconds: float
    speaker_id: int

    def __post_init__(self) -> None:
        _validate_times(self.start_seconds, self.end_seconds)
        if isinstance(self.speaker_id, bool) or not isinstance(self.speaker_id, int):
            raise ValueError("Nemotron speaker identity must be a positive integer")
        if self.speaker_id <= 0:
            raise ValueError("Nemotron speaker identity must be a positive integer")


@dataclass(frozen=True, slots=True)
class CommunityInterval:
    """Copied secondary interval retaining the library's string identity."""

    start_seconds: float
    end_seconds: float
    speaker_id: str

    def __post_init__(self) -> None:
        _validate_times(self.start_seconds, self.end_seconds)
        if not isinstance(self.speaker_id, str) or not self.speaker_id:
            raise ValueError("Community-1 speaker identity must be nonempty text")


class DiarizationProviderFailure(RuntimeError):
    """Copied diagnostic metadata without retaining native objects or tracebacks."""

    def __init__(
        self, *, stage: str, operation: str, diagnostic: str | None = None,
        status: int | None = None,
    ) -> None:
        self.stage = stage
        self.operation = operation
        self.diagnostic = diagnostic
        self.status = status
        message = f"{operation} failed at {stage}"
        if diagnostic:
            message += f": {diagnostic}"
        super().__init__(message)


class RecoverableDiarizationFailure(DiarizationProviderFailure):
    """Secondary capability/inference failure permitting Nemotron fallback."""


class DiarizationCancelled(DiarizationProviderFailure):
    """Fatal cooperative/native cancellation; never a secondary fallback."""


class DiarizationCleanupFailure(DiarizationProviderFailure):
    """Fatal cleanup failure at the resource owner's public stage."""
