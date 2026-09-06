from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from transcriber.domain.audio import CanonicalAudio


@pytest.mark.parametrize("total_samples", [0, 1, 1_920_000])
def test_canonical_audio_accepts_provider_reported_nonnegative_sample_count(
    total_samples: int,
) -> None:
    audio = CanonicalAudio(total_samples=total_samples)

    assert audio.total_samples == total_samples


def test_canonical_audio_is_immutable() -> None:
    audio = CanonicalAudio(total_samples=10)

    with pytest.raises(FrozenInstanceError):
        audio.total_samples = 11  # type: ignore[misc]


@pytest.mark.parametrize("total_samples", [-1, True, 1.0, "1"])
def test_canonical_audio_rejects_invalid_provider_timeline_values(
    total_samples: object,
) -> None:
    with pytest.raises((TypeError, ValueError), match="total samples"):
        CanonicalAudio(total_samples=total_samples)  # type: ignore[arg-type]
