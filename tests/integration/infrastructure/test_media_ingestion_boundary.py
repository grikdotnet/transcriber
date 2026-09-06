from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.call_log import CallLog
from tests.support.process import FakeCompletedProcess, FakeProcessRunner
from transcriber.infrastructure.ffmpeg import FfmpegFailure, FfmpegProcess
from transcriber.infrastructure.filesystem import WorkDirectory


def test_controlled_media_ingestion_orders_decode_create_and_extraction(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source-with-video.mov"
    source.write_bytes(b"controlled media placeholder")
    task = tmp_path / "task"
    calls = CallLog()
    runner = FakeProcessRunner(
        [FakeCompletedProcess(), FakeCompletedProcess()], call_log=calls, event="ffmpeg"
    )
    ffmpeg = FfmpegProcess(Path("/repository/vendor/ffmpeg"), runner)
    work_directory = WorkDirectory(call_log=calls)

    ffmpeg.validate(source)
    work_directory.create(task)
    ffmpeg.extract(source, task / "prepared.wav")

    assert calls.events == ("ffmpeg", "work-directory.create", "ffmpeg")
    assert runner.calls[1].argv[-10:] == (
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(task / "prepared.wav"),
    )


@pytest.mark.parametrize("source_case", ["missing", "unreadable"])
def test_local_source_failures_do_not_start_ffmpeg_or_create_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source_case: str
) -> None:
    source = tmp_path / "source.mov"
    if source_case == "unreadable":
        source.write_bytes(b"controlled")
        monkeypatch.setattr("transcriber.infrastructure.ffmpeg.os.access", lambda *_: False)
    task = tmp_path / "task"
    runner = FakeProcessRunner()
    ffmpeg = FfmpegProcess(Path("/repository/vendor/ffmpeg"), runner)

    with pytest.raises(FfmpegFailure) as raised:
        ffmpeg.validate(source)

    assert raised.value.stage == "source-media"
    assert raised.value.operation == source_case
    assert runner.calls == []
    assert not task.exists()


@pytest.mark.parametrize("source_case", ["corrupt", "unsupported", "audio-free"])
def test_decode_failures_leave_requested_task_absent(tmp_path: Path, source_case: str) -> None:
    source = tmp_path / "source.mov"
    source.write_bytes(b"controlled")
    task = tmp_path / "task"
    runner = FakeProcessRunner(
        [FakeCompletedProcess(returncode=1, stderr=f"controlled {source_case}")]
    )
    ffmpeg = FfmpegProcess(Path("/repository/vendor/ffmpeg"), runner)

    with pytest.raises(FfmpegFailure):
        ffmpeg.validate(source)

    assert len(runner.calls) == 1
    assert not task.exists()
