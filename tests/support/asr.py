"""Controlled ASR Task builders shared by focused ASR tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from tests.support.audio import make_pcm_wav
from tests.support.call_log import CallLog
from transcriber.domain.manifest import ManifestAudio, ManifestSegment, SegmentManifest
from transcriber.infrastructure.execution_provider import (
    ExecutionProviderSession,
    RecognitionRequest,
    RecognitionResult,
    RecognitionToken,
)
from transcriber.protocol.asr_cli import AsrCommand


def make_segment_manifest(*durations: int) -> SegmentManifest:
    """Build an ordered canonical Segment Manifest from segment durations."""
    start_sample = 0
    segments: list[ManifestSegment] = []
    for index, duration_samples in enumerate(durations):
        end_sample = start_sample + duration_samples
        segments.append(
            ManifestSegment(
                index=index,
                start_sample=start_sample,
                end_sample=end_sample,
                duration_samples=duration_samples,
                path=f"segments/segment-{index:04d}.wav",
            )
        )
        start_sample = end_sample
    return SegmentManifest(
        schema_version=1,
        audio=ManifestAudio(total_samples=start_sample),
        segments=tuple(segments),
    )


def make_asr_command(task_work_directory: Path, *, model_id: str = "controlled-asr") -> AsrCommand:
    """Build a valid ASR command for one controlled ASR Model."""
    return AsrCommand(task_work_directory=task_work_directory, model_id=model_id)


class ControlledExecutionProvider:
    """Provider factory that records one task-owned session creation."""

    def __init__(
        self, responses: tuple[tuple[RecognitionToken, ...] | Exception, ...], log: CallLog
    ) -> None:
        self._responses = iter(responses)
        self._log = log
        self.session = ControlledExecutionProviderSession(self._responses, log)
        self.segment_roots: list[Path] = []

    def create(self, *, segment_root: Path) -> ControlledExecutionProviderSession:
        self.segment_roots.append(segment_root)
        self._log.record("provider.create")
        return self.session


class ControlledExecutionProviderSession(ExecutionProviderSession):
    """Started-session double that records ordered recognition requests."""

    def __init__(
        self, responses: Iterator[tuple[RecognitionToken, ...] | Exception], log: CallLog
    ) -> None:
        super().__init__()
        self._responses = responses
        self._log = log
        self.requests: list[RecognitionRequest] = []

    def _start(self, *, readiness_timeout_seconds: float) -> None:
        self._log.record("provider.start")

    def _recognize(
        self, request: RecognitionRequest, *, timeout_seconds: float
    ) -> RecognitionResult:
        self.requests.append(request)
        self._log.record(f"provider.recognize.{request.segment_index}")
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return RecognitionResult(tokens=response)

    def _stop(self, *, graceful_timeout_seconds: float, force_timeout_seconds: float) -> None:
        self._log.record("provider.stop")


def make_asr_task_directory(tmp_path: Path, manifest_bytes: bytes) -> Path:
    """Create one completed-task layout with opaque Segment Manifest bytes."""
    task_work_directory = tmp_path / "asr-task"
    task_work_directory.mkdir()
    (task_work_directory / "segments").mkdir()
    (task_work_directory / "manifest.json").write_bytes(manifest_bytes)
    return task_work_directory


def write_speech_segment(
    task_work_directory: Path,
    index: int,
    duration_samples: int,
    *,
    sample_rate_hz: int = 16_000,
    channels: int = 1,
) -> Path:
    """Write one deterministic PCM WAV at the index-derived segment location."""
    return make_pcm_wav(
        task_work_directory / "segments" / f"segment-{index:04d}.wav",
        (0 for _ in range(duration_samples * channels)),
        sample_rate_hz=sample_rate_hz,
        channels=channels,
    )
