from __future__ import annotations

import pytest

from transcriber.domain.audio import CanonicalAudio
from transcriber.domain.segments import SampleInterval, convert_sample_intervals


def test_converts_ordered_sample_intervals_to_segments() -> None:
    segments = convert_sample_intervals(
        (SampleInterval(160, 480), SampleInterval(640, 800)),
        CanonicalAudio(total_samples=800),
    )

    assert [
        (item.index, item.start_sample, item.end_sample, item.duration_samples) for item in segments
    ] == [
        (0, 160, 480, 320),
        (1, 640, 800, 160),
    ]


def test_preserves_short_positive_remainder_and_over_target_duration() -> None:
    segments = convert_sample_intervals(
        (SampleInterval(0, 496_000), SampleInterval(496_000, 496_160)),
        CanonicalAudio(total_samples=496_160),
    )

    assert [segment.duration_samples for segment in segments] == [496_000, 160]


def test_accepts_empty_intervals() -> None:
    assert convert_sample_intervals((), CanonicalAudio(0)) == ()


@pytest.mark.parametrize(
    "intervals",
    [
        (SampleInterval(2, 2),),
        (SampleInterval(-1, 1),),
        (SampleInterval(0, 1_601),),
        (SampleInterval(320, 640), SampleInterval(160, 320)),
        (SampleInterval(0, 480), SampleInterval(320, 640)),
    ],
)
def test_rejects_invalid_intervals_without_clamping(
    intervals: tuple[SampleInterval, ...],
) -> None:
    with pytest.raises(ValueError):
        convert_sample_intervals(intervals, CanonicalAudio(total_samples=1_600))


def test_preserves_arbitrary_millisecond_endpoint_as_exact_sample_boundary() -> None:
    assert convert_sample_intervals(
        (SampleInterval(0, 5_360),), CanonicalAudio(total_samples=5_360)
    )[0].end_sample == 5_360
