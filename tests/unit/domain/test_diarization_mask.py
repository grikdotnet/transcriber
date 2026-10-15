"""Sample boundary and exact prepared-region ownership."""

from tests.support.diarization import make_diarization_manifest
from transcriber.domain.diarization import SampleSpeakerActivity, SpeakerActivity, mask_activity


def test_ties_even_clamping_and_collapsed_intervals() -> None:
    manifest = make_diarization_manifest(10, ((0, 10),))
    rows = (
        SpeakerActivity(-1, 2.5 / 16000, 1),
        SpeakerActivity(3.5 / 16000, 20, 2),
        SpeakerActivity(6.1 / 16000, 6.4 / 16000, 3),
    )
    assert mask_activity(rows, manifest) == (
        SampleSpeakerActivity(1, 0, 2),
        SampleSpeakerActivity(2, 4, 10),
    )


def test_exact_mask_splits_merges_touching_regions_preserves_overlap_and_sorts() -> None:
    manifest = make_diarization_manifest(30, ((2, 8), (8, 12), (20, 25)))
    rows = (
        SpeakerActivity(0, 1, 2),
        SpeakerActivity(5 / 16000, 10 / 16000, 1),
        SpeakerActivity(10 / 16000, 22 / 16000, 1),
    )
    assert mask_activity(rows, manifest) == (
        SampleSpeakerActivity(2, 2, 12),
        SampleSpeakerActivity(1, 5, 12),
        SampleSpeakerActivity(1, 20, 22),
        SampleSpeakerActivity(2, 20, 25),
    )


def test_empty_mask_and_zero_audio_return_empty() -> None:
    assert mask_activity((SpeakerActivity(0, 1, 1),), make_diarization_manifest(20, ())) == ()
    assert mask_activity((), make_diarization_manifest(0, ())) == ()
