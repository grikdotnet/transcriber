"""Pure canonical-audio timeline facts reported by the native provider."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CanonicalAudio:
    """The accepted audio timeline, without revalidating provider or FFmpeg data."""

    total_samples: int

    def __post_init__(self) -> None:
        if isinstance(self.total_samples, bool) or not isinstance(self.total_samples, int):
            raise TypeError("total samples must be an integer")
        if self.total_samples < 0:
            raise ValueError("total samples must be non-negative")
