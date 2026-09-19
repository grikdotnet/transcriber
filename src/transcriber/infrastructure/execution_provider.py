"""Runtime-neutral execution-provider lifecycle primitives."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RecognitionRequest:
    """One validated local Speech Segment recognition request."""

    segment_index: int
    audio_path: Path
    recognition_context: str
    language: str

    def __post_init__(self) -> None:
        if isinstance(self.segment_index, bool) or not isinstance(self.segment_index, int):
            raise ValueError("segment_index must be an integer")
        if self.segment_index < 0:
            raise ValueError("segment_index must be a non-negative integer")
        if not self.audio_path.is_absolute():
            raise ValueError("audio_path must be absolute")
        if not isinstance(self.recognition_context, str):
            raise ValueError("recognition_context must be text")
        if len(self.recognition_context) > 2048:
            raise ValueError("recognition_context must contain at most 2048 code points")
        if not isinstance(self.language, str) or not self.language:
            raise ValueError("language must be non-empty text")


@dataclass(frozen=True, slots=True)
class RecognitionToken:
    """One provider-neutral, scored transcript token."""

    token_id: int
    text: str
    log_probability: float

    def __post_init__(self) -> None:
        if isinstance(self.token_id, bool) or not isinstance(self.token_id, int):
            raise ValueError("token_id must be an integer")
        if not isinstance(self.text, str):
            raise ValueError("text must be text")
        if isinstance(self.log_probability, bool) or not isinstance(self.log_probability, Real):
            raise ValueError("log_probability must be a real number")
        if math.isnan(self.log_probability) or self.log_probability > 0:
            raise ValueError("log_probability must be less than or equal to zero")


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    """An ordered provider-neutral recognition result for one Speech Segment."""

    tokens: tuple[RecognitionToken, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.tokens, tuple):
            raise ValueError("tokens must be a tuple")
        if not all(isinstance(token, RecognitionToken) for token in self.tokens):
            raise ValueError("tokens must contain RecognitionToken values")


class ExecutionProviderFailure(RuntimeError):
    """Provider failure with a separately carried diagnostic excerpt."""

    def __init__(self, *, message: str, diagnostic: str | None = None) -> None:
        self.message = message
        self.diagnostic = diagnostic
        super().__init__(message)


class ExecutionProviderLifecycleError(RuntimeError):
    """Raised when a provider session operation violates its lifecycle."""


class ExecutionProviderSession(ABC):
    """Guard provider-session lifecycle around adapter-specific operations."""

    def __init__(self) -> None:
        self._state = "fresh"

    def start(self, *, readiness_timeout_seconds: float = 60.0) -> None:
        """Start the provider once and return only when it is ready."""
        if self._state != "fresh":
            raise ExecutionProviderLifecycleError("provider session must be fresh to start")
        self._state = "starting"
        try:
            self._start(readiness_timeout_seconds=readiness_timeout_seconds)
        except BaseException:
            self._state = "failed"
            raise
        self._state = "started"

    def recognize(
        self, request: RecognitionRequest, *, timeout_seconds: float = 180.0
    ) -> RecognitionResult:
        """Recognize one segment after successful startup."""
        if self._state != "started":
            raise ExecutionProviderLifecycleError("provider session must be started to recognize")
        return self._recognize(request, timeout_seconds=timeout_seconds)

    def stop(
        self,
        *,
        graceful_timeout_seconds: float = 60.0,
        force_timeout_seconds: float = 10.0,
    ) -> None:
        """Stop a started or failed session once; later calls are no-ops."""
        if self._state == "stopped":
            return
        needs_cleanup = self._state in {"starting", "started", "failed"}
        self._state = "stopped"
        if needs_cleanup:
            self._stop(
                graceful_timeout_seconds=graceful_timeout_seconds,
                force_timeout_seconds=force_timeout_seconds,
            )

    @abstractmethod
    def _start(self, *, readiness_timeout_seconds: float) -> None:
        """Perform adapter-specific startup and readiness work."""

    @abstractmethod
    def _recognize(
        self, request: RecognitionRequest, *, timeout_seconds: float
    ) -> RecognitionResult:
        """Perform adapter-specific recognition work."""

    @abstractmethod
    def _stop(self, *, graceful_timeout_seconds: float, force_timeout_seconds: float) -> None:
        """Perform adapter-specific process cleanup."""


class ExecutionProvider(Protocol):
    """Factory for fresh sessions configured by Composition."""

    def create(self, *, segment_root: Path) -> ExecutionProviderSession:
        """Create one fresh session for the supplied validated segment root."""
