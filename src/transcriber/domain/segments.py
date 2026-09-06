"""Pure validation of upstream-returned sample intervals."""

from __future__ import annotations

from dataclasses import dataclass

from transcriber.domain.audio import CanonicalAudio


@dataclass(frozen=True, slots=True)
class SampleInterval:
    start_sample: int
    end_sample: int


@dataclass(frozen=True, slots=True)
class FinalSpeechSegment:
    index: int
    start_sample: int
    end_sample: int
    duration_samples: int


def convert_sample_intervals(
    intervals: tuple[SampleInterval, ...], audio: CanonicalAudio
) -> tuple[FinalSpeechSegment, ...]:
    """Validate authoritative ordered sample intervals without clamping."""
    result: list[FinalSpeechSegment] = []
    previous_end_sample = 0
    for index, interval in enumerate(intervals):
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in (interval.start_sample, interval.end_sample)
        ):
            raise TypeError("sample indexes must be integers")
        if interval.start_sample < 0 or interval.end_sample <= interval.start_sample:
            raise ValueError("sample interval must have positive duration")
        if index and interval.start_sample < previous_end_sample:
            raise ValueError("sample intervals must be ordered and non-overlapping")
        if interval.end_sample > audio.total_samples:
            raise ValueError("sample interval exceeds canonical audio bounds")
        result.append(
            FinalSpeechSegment(
                index=index,
                start_sample=interval.start_sample,
                end_sample=interval.end_sample,
                duration_samples=interval.end_sample - interval.start_sample,
            )
        )
        previous_end_sample = interval.end_sample
    return tuple(result)
