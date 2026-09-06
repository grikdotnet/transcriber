from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.process import FakeCompletedProcess, FakeProcessRunner
from transcriber.infrastructure.ffmpeg import FfmpegFailure, FfmpegProcess

FFMPEG = Path("/repository/vendor/ffmpeg")
SOURCE = Path(__file__).resolve()
DESTINATION = Path("/tasks/task-1/prepared.wav")


def test_validation_decodes_exactly_one_audio_stream_without_a_shell() -> None:
    runner = FakeProcessRunner([FakeCompletedProcess()])
    ffmpeg = FfmpegProcess(FFMPEG, runner)

    ffmpeg.validate(SOURCE)

    assert runner.calls[0].argv == (
        str(FFMPEG),
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(SOURCE),
        "-map",
        "0:a:0",
        "-f",
        "null",
        "-",
    )
    assert runner.calls[0].shell is False


def test_extraction_uses_the_fixed_canonical_one_stream_arguments() -> None:
    runner = FakeProcessRunner([FakeCompletedProcess()])
    ffmpeg = FfmpegProcess(FFMPEG, runner)

    ffmpeg.extract(SOURCE, DESTINATION)

    assert runner.calls[0].argv == (
        str(FFMPEG),
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(SOURCE),
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(DESTINATION),
    )
    assert runner.calls[0].shell is False


@pytest.mark.parametrize("outcome", ["corrupt", "unsupported", "audio-free"])
def test_validation_translates_decode_failures(outcome: str) -> None:
    runner = FakeProcessRunner(
        [FakeCompletedProcess(returncode=1, stderr=f"controlled {outcome} result")]
    )
    ffmpeg = FfmpegProcess(FFMPEG, runner)

    with pytest.raises(FfmpegFailure) as raised:
        ffmpeg.validate(SOURCE)

    assert raised.value.stage == "source-media"
    assert raised.value.path == SOURCE
    assert raised.value.operation == "decode"


def test_extraction_translates_process_failure() -> None:
    runner = FakeProcessRunner([FakeCompletedProcess(returncode=1, stderr="controlled")])
    ffmpeg = FfmpegProcess(FFMPEG, runner)

    with pytest.raises(FfmpegFailure) as raised:
        ffmpeg.extract(SOURCE, DESTINATION)

    assert raised.value.stage == "audio-extraction"
    assert raised.value.path == DESTINATION
    assert raised.value.operation == "extract"


def test_process_start_failure_is_an_actionable_dependency_failure() -> None:
    class FailingRunner:
        def run(self, argv: tuple[str, ...], *, shell: bool = False) -> FakeCompletedProcess:
            raise OSError("controlled startup failure")

    ffmpeg = FfmpegProcess(FFMPEG, FailingRunner())

    with pytest.raises(FfmpegFailure) as raised:
        ffmpeg.validate(SOURCE)

    assert raised.value.stage == "source-media"
    assert raised.value.path == FFMPEG
    assert raised.value.operation == "start-decoder"


def test_ffmpeg_executable_must_be_an_absolute_repository_path() -> None:
    with pytest.raises(ValueError, match="absolute"):
        FfmpegProcess(Path("vendor/ffmpeg"), FakeProcessRunner())
