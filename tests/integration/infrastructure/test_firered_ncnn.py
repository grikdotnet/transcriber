from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.process import FakeCompletedProcess, FakeProcessRunner
from transcriber.infrastructure.firered_ncnn import FireRedNcnnFailure, FireRedNcnnProcess
from transcriber.protocol.firered_probabilities import decode_probability_document

EXECUTABLE = Path("/repository/vendor/firered-vad-ncnn")
MODEL_DIR = Path("/repository/models/firered-vad.ncnn")
AUDIO = Path("/task/prepared.wav")


def _payload() -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "audio": {
                "sample_rate_hz": 16000,
                "channels": 1,
                "sample_format": "pcm_s16le",
                "total_samples": 400,
            },
            "frames": {
                "frame_length_samples": 400,
                "frame_shift_samples": 160,
                "frame_count": 1,
                "probabilities": [0.25],
            },
        }
    )


def test_process_uses_exact_absolute_argv_without_a_shell_and_decodes_stdout() -> None:
    runner = FakeProcessRunner([FakeCompletedProcess(stdout=_payload())])
    process = FireRedNcnnProcess(EXECUTABLE, MODEL_DIR, runner, decode_probability_document)

    document = process.run(AUDIO)

    assert runner.calls[0].argv == (
        str(EXECUTABLE),
        "--audio",
        str(AUDIO),
        "--model-param",
        str(MODEL_DIR / "firered_vad_non_stream.ncnn.param"),
        "--model-bin",
        str(MODEL_DIR / "firered_vad_non_stream.ncnn.bin"),
        "--cmvn-means",
        str(MODEL_DIR / "cmvn_means.bin"),
        "--cmvn-istd",
        str(MODEL_DIR / "cmvn_istd.bin"),
        "--chunk-max-frames",
        "30000",
    )
    assert runner.calls[0].shell is False
    assert document.frames.probabilities == (0.25,)


def test_stderr_is_not_mixed_into_probability_decoding() -> None:
    runner = FakeProcessRunner([FakeCompletedProcess(stdout=_payload(), stderr="diagnostic")])
    process = FireRedNcnnProcess(EXECUTABLE, MODEL_DIR, runner, decode_probability_document)

    assert process.run(AUDIO).frames.frame_count == 1


@pytest.mark.parametrize("returncode", [2, 3, 4, 5, 6])
def test_native_failure_status_is_preserved(returncode: int) -> None:
    runner = FakeProcessRunner(
        [FakeCompletedProcess(returncode=returncode, stderr="bounded native failure")]
    )
    process = FireRedNcnnProcess(EXECUTABLE, MODEL_DIR, runner, decode_probability_document)

    with pytest.raises(FireRedNcnnFailure) as raised:
        process.run(AUDIO)

    assert raised.value.stage == "speech-detection"
    assert raised.value.status == returncode
    assert raised.value.path == EXECUTABLE


def test_malformed_success_stdout_is_a_closed_protocol_failure() -> None:
    process = FireRedNcnnProcess(
        EXECUTABLE,
        MODEL_DIR,
        FakeProcessRunner([FakeCompletedProcess(stdout="not json")]),
        decode_probability_document,
    )

    with pytest.raises(FireRedNcnnFailure) as raised:
        process.run(AUDIO)

    assert raised.value.operation == "decode-probabilities"


def test_all_configured_paths_must_be_absolute() -> None:
    with pytest.raises(ValueError, match="absolute"):
        FireRedNcnnProcess(
            Path("vendor/runner"), MODEL_DIR, FakeProcessRunner(), decode_probability_document
        )
    with pytest.raises(ValueError, match="absolute"):
        FireRedNcnnProcess(
            EXECUTABLE, Path("models"), FakeProcessRunner(), decode_probability_document
        )
