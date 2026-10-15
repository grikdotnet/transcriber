"""Real Community-1 checkpoint with a controlled valid requested count."""

from dataclasses import replace
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest
from numpy.typing import NDArray

from tests.conftest import enforce_real_diarization_available
from transcriber.composition.application import build_diarization_service
from transcriber.domain.diarization import CommunityPrediction, SpeakerActivity
from transcriber.infrastructure.diarization_prerequisites import check_community_prerequisites
from transcriber.infrastructure.diarization_provider import (
    CommunityInterval,
    DiarizationCleanupFailure,
    DiarizationProviderFailure,
)
from transcriber.infrastructure.pyannote import Community1Diarizer


@pytest.mark.real_diarization
def test_real_community_adapter_and_composition_mapping(
    real_diarization_audio: NDArray[np.float32], pytestconfig: pytest.Config
) -> None:
    audio = real_diarization_audio
    original = audio.copy()
    calls = []
    actual = Community1Diarizer.diarize

    def observe(
        adapter: Community1Diarizer,
        samples: NDArray[np.float32],
        speaker_count: int,
        **kwargs: Any,
    ) -> tuple[CommunityInterval, ...]:
        assert samples is audio and speaker_count == 2
        assert adapter._vulkan_device == 0
        assert adapter._model_dir.is_absolute()
        rows = actual(adapter, samples, speaker_count, **kwargs)
        calls.append(rows)
        assert isinstance(rows, tuple)
        assert all(isinstance(row, CommunityInterval) for row in rows)
        return rows

    constructors = []
    cleanup = []

    def checked_capabilities(model_dir: Any) -> Any:
        capabilities = check_community_prerequisites(model_dir)

        def construct(*args: Any, **kwargs: Any) -> Any:
            constructors.append((args, kwargs))
            assert args == (model_dir,)
            assert kwargs == {"minimum_speakers": 2, "maximum_speakers": 2, "gpu_index": 0}
            return capabilities.diarizer_factory(*args, **kwargs)

        def close() -> None:
            capabilities.close_vulkan()
            cleanup.append(True)

        return replace(capabilities, diarizer_factory=construct, close_vulkan=close)

    monkeypatcher = patch(
        "transcriber.infrastructure.pyannote.check_community_prerequisites",
        checked_capabilities,
    )
    service = build_diarization_service()
    with monkeypatcher, patch.object(Community1Diarizer, "diarize", observe):
        try:
            prediction = service.community1(audio, 2, 0)
        except DiarizationCleanupFailure:
            raise
        except DiarizationProviderFailure as error:
            enforce_real_diarization_available(
                str(error),
                required=pytestconfig.getoption("--real-diarization-required"),
            )
            raise AssertionError("unavailable policy must terminate") from error
    assert len(calls) == 1, "actual adapter must complete; fallback cannot satisfy checkpoint"
    assert len(constructors) == 1 and cleanup == [True]
    assert isinstance(prediction, CommunityPrediction)
    assert prediction.activity == tuple(
        SpeakerActivity(row.start_seconds, row.end_seconds, row.speaker_id) for row in calls[0]
    )
    np.testing.assert_array_equal(audio, original)
