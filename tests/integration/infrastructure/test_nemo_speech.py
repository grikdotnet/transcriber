"""Real ABI checkpoint: observe first-party construction, copying and mapping."""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from numpy.typing import NDArray

from tests.conftest import enforce_real_diarization_available
from transcriber.composition.application import build_diarization_service
from transcriber.domain.diarization import NemotronPrediction, SpeakerActivity
from transcriber.infrastructure.diarization_provider import (
    DiarizationCleanupFailure,
    DiarizationProviderFailure,
    NemotronInterval,
)
from transcriber.infrastructure.nemo_speech import NemoSpeechAdapter


@pytest.mark.real_diarization
def test_real_nemotron_adapter_and_composition_mapping(
    real_diarization_audio: NDArray[np.float32], pytestconfig: pytest.Config
) -> None:
    audio = real_diarization_audio
    original = audio.copy()
    calls = []
    actual = NemoSpeechAdapter.diarize

    def observe(
        adapter: NemoSpeechAdapter, samples: NDArray[np.float32]
    ) -> tuple[NemotronInterval, ...]:
        assert samples is audio
        assert adapter.gpu_index == 0
        assert adapter.model_path.is_absolute()
        config = adapter.make_model_config(str(adapter.model_path), adapter.gpu_index)
        assert config.gpu == 0 and config.preset == b"v3-offline"
        assert config.left_context_frames == -1
        rows = actual(adapter, samples)
        calls.append(rows)
        assert isinstance(rows, tuple)
        assert all(isinstance(row, NemotronInterval) for row in rows)
        return rows

    service = build_diarization_service()
    required = pytestconfig.getoption("--real-diarization-required")
    model = Path(__file__).resolve().parents[3] / "models/Nemotron-3-Diarization.q8_0.gguf"
    enforce_real_diarization_available(None if model.is_file() else str(model), required=required)
    with patch.object(NemoSpeechAdapter, "diarize", observe):
        try:
            prediction = service.nemotron(audio, 0)
        except DiarizationCleanupFailure:
            raise
        except DiarizationProviderFailure as error:
            enforce_real_diarization_available(str(error), required=required)
            raise AssertionError("unavailable policy must terminate") from error
    assert len(calls) == 1, "actual adapter must complete; fallback cannot satisfy checkpoint"
    assert isinstance(prediction, NemotronPrediction)
    assert prediction.activity == tuple(
        SpeakerActivity(row.start_seconds, row.end_seconds, row.speaker_id) for row in calls[0]
    )
    np.testing.assert_array_equal(audio, original)
    audio.fill(0)
    assert prediction.activity == tuple(
        SpeakerActivity(row.start_seconds, row.end_seconds, row.speaker_id) for row in calls[0]
    )
    audio[:] = original
    np.testing.assert_array_equal(audio, original)
