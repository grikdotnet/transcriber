from dataclasses import FrozenInstanceError

import pytest

from transcriber.infrastructure.diarization_provider import (
    CommunityInterval, DiarizationCancelled, DiarizationCleanupFailure,
    DiarizationProviderFailure, NemotronInterval, RecoverableDiarizationFailure,
)


def test_intervals_preserve_typed_labels_and_double_precision():
    interval = NemotronInterval(0.123456789012345, 8.0, 2)
    assert interval.start_seconds == 0.123456789012345
    assert type(interval.speaker_id) is int
    assert CommunityInterval(-1.0, 20.0, 'speaker_A').speaker_id == 'speaker_A'
    with pytest.raises(FrozenInstanceError):
        interval.speaker_id = 3


@pytest.mark.parametrize('start,end,label', [(True, 1, 1), (float('nan'), 1, 1),
    (0, float('inf'), 1), (0, 1, True), (0, 1, 0), (0, 1, '1')])
def test_nemotron_rejects_malformed_values(start, end, label):
    with pytest.raises(ValueError):
        NemotronInterval(start, end, label)


@pytest.mark.parametrize('label', ['', 1, True])
def test_community_rejects_invalid_identity(label):
    with pytest.raises(ValueError):
        CommunityInterval(0, 1, label)


def test_failures_preserve_metadata_and_do_not_confuse_fallback_with_fatal():
    failure = RecoverableDiarizationFailure(stage='community1', operation='import',
        diagnostic='missing ncnn', status=3)
    assert isinstance(failure, DiarizationProviderFailure)
    assert (failure.stage, failure.operation, failure.diagnostic, failure.status) == (
        'community1', 'import', 'missing ncnn', 3)
    for fatal in (DiarizationCancelled, DiarizationCleanupFailure):
        assert not isinstance(fatal(stage='community1', operation='close'),
            RecoverableDiarizationFailure)
