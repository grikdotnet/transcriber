from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.support.call_log import CallLog
from transcriber.domain.manifest import SegmentManifest, encode_manifest
from transcriber.infrastructure.wave_files import WaveMetadata
from transcriber.protocol.cli import PrepareCommand, PrepareFailure, PrepareSuccess
from transcriber.protocol.firered_probabilities import (
    FireRedProbabilityDocument,
    ProbabilityAudio,
    ProbabilityFrames,
)
from transcriber.service.prepare_media import PreparationStage, PrepareMedia


class _BoundaryFailure(RuntimeError):
    def __init__(self, *, stage: str, path: Path, operation: str) -> None:
        self.stage = stage
        self.path = path
        self.operation = operation
        super().__init__(f"{operation}: {path}")


@dataclass(frozen=True)
class _FailureCase:
    event: str
    stage: str
    resource: str
    operation: str


class _Ffmpeg:
    def __init__(self, rig: _Rig) -> None:
        self._rig = rig

    def validate(self, source: Path) -> None:
        assert source == self._rig.source
        self._rig.step("media.validate")

    def extract(self, source: Path, destination: Path) -> None:
        assert source == self._rig.source
        assert destination == self._rig.prepared
        self._rig.step("audio.extract")


class _WorkDirectory:
    def __init__(self, rig: _Rig) -> None:
        self._rig = rig

    def create(self, path: Path) -> Path:
        assert path == self._rig.task
        self._rig.step("work-directory.create")
        return path


class _Vad:
    def __init__(self, rig: _Rig) -> None:
        self._rig = rig

    def run(self, audio: Path) -> FireRedProbabilityDocument:
        # The extracted path is handed straight to the native boundary. There is
        # deliberately no intervening FFmpeg-output inspection collaborator.
        assert audio == self._rig.prepared
        self._rig.step("vad.run")
        return self._rig.probability_document


class _Postprocessor:
    def __init__(self, rig: _Rig) -> None:
        self._rig = rig

    def process(
        self,
        probabilities: tuple[float, ...],
        max_speech_frame: int,
        total_samples: int,
    ) -> tuple[tuple[int, int], ...]:
        assert probabilities == self._rig.probability_document.frames.probabilities
        assert max_speech_frame == self._rig.command.split_target_frames
        assert total_samples == self._rig.probability_document.audio.total_samples
        self._rig.step("vad.postprocess")
        return self._rig.intervals


class _SegmentWriter:
    def __init__(self, rig: _Rig) -> None:
        self._rig = rig

    def write(
        self,
        path: Path,
        *,
        start_sample: int,
        end_sample: int,
    ) -> WaveMetadata:
        index = len(self._rig.writes)
        self._rig.writes.append((path, start_sample, end_sample))
        self._rig.step(f"segment.write.{index}")
        if self._rig.invalid_metadata_index == index:
            return WaveMetadata(
                frame_count=end_sample - start_sample - 1,
                sample_rate_hz=16_000,
                channel_count=1,
                sample_width_bytes=2,
                compression_type="NONE",
            )
        return WaveMetadata(
            frame_count=end_sample - start_sample,
            sample_rate_hz=16_000,
            channel_count=1,
            sample_width_bytes=2,
            compression_type="NONE",
        )


class _Publisher:
    def __init__(self, rig: _Rig) -> None:
        self._rig = rig

    def write(self, path: Path, content: bytes) -> None:
        assert path == self._rig.manifest_path
        assert content == self._rig.encoded_manifest
        self._rig.step("manifest.publish")


class _Rig:
    def __init__(
        self,
        root: Path,
        *,
        intervals: tuple[tuple[int, int], ...] = ((100, 600), (900, 1_025)),
        failure: _FailureCase | None = None,
        invalid_intervals: bool = False,
        invalid_metadata_index: int | None = None,
    ) -> None:
        self.log = CallLog()
        self.source = root / "source.mp4"
        self.task = root / "task"
        self.prepared = self.task / "prepared.wav"
        self.manifest_path = self.task / "manifest.json"
        self.command = PrepareCommand(
            source_media=self.source,
            task_work_directory=self.task,
            split_target_seconds=30.009,
        )
        self.probability_document = FireRedProbabilityDocument(
            schema_version=1,
            audio=ProbabilityAudio(
                sample_rate_hz=16_000,
                channels=1,
                sample_format="pcm_s16le",
                total_samples=1_600,
            ),
            frames=ProbabilityFrames(
                frame_length_samples=400,
                frame_shift_samples=160,
                frame_count=3,
                probabilities=(0.1, 0.9, 0.2),
            ),
        )
        self.intervals = ((100, 600), (500, 700)) if invalid_intervals else intervals
        self.failure = failure
        self.invalid_metadata_index = invalid_metadata_index
        self.manifest: SegmentManifest | None = None
        self.encoded_manifest = b""
        self.writes: list[tuple[Path, int, int]] = []
        self.ffmpeg = _Ffmpeg(self)
        self.work_directory = _WorkDirectory(self)
        self.vad = _Vad(self)
        self.postprocessor = _Postprocessor(self)
        self.segment_writer = _SegmentWriter(self)
        self.publisher = _Publisher(self)

    def step(self, event: str) -> None:
        self.log.record(event)
        if self.failure is not None and self.failure.event == event:
            raise _BoundaryFailure(
                stage=self.failure.stage,
                path=Path(self.failure.resource),
                operation=self.failure.operation,
            )

    def encode(self, manifest: SegmentManifest) -> bytes:
        self.manifest = manifest
        self.step("manifest.encode")
        self.encoded_manifest = encode_manifest(manifest)
        return self.encoded_manifest

    def make_writer(self, source: Path) -> _SegmentWriter:
        assert source == self.prepared
        self.step("segments.open-source")
        return self.segment_writer

    def service(self) -> PrepareMedia:
        return PrepareMedia(
            ffmpeg=self.ffmpeg,
            work_directory=self.work_directory,
            vad=self.vad,
            postprocessor=self.postprocessor,
            manifest_encoder=self.encode,
            segment_writer_factory=self.make_writer,
            manifest_publisher=self.publisher,
        )


_SUCCESS_EVENTS = (
    "media.validate",
    "work-directory.create",
    "audio.extract",
    "vad.run",
    "vad.postprocess",
    "manifest.encode",
    "segments.open-source",
    "segment.write.0",
    "segment.write.1",
    "manifest.publish",
)


def test_complete_service_order_maps_protocol_primitives_to_domain_and_artifacts(
    tmp_path: Path,
) -> None:
    rig = _Rig(tmp_path)
    service = rig.service()

    result = service.prepare(rig.command)

    assert result == PrepareSuccess(
        task_work_directory=rig.task,
        canonical_audio=rig.prepared,
        manifest=rig.manifest_path,
        segment_count=2,
    )
    assert service.stage is PreparationStage.SUCCEEDED
    assert rig.log.events == _SUCCESS_EVENTS
    assert rig.manifest == SegmentManifest(
        schema_version=1,
        audio=rig.manifest.audio,
        segments=rig.manifest.segments,
    )
    assert rig.manifest.audio.total_samples == 1_600
    assert tuple(
        (item.index, item.start_sample, item.end_sample, item.duration_samples, item.path)
        for item in rig.manifest.segments
    ) == (
        (0, 100, 600, 500, "segments/segment-0000.wav"),
        (1, 900, 1_025, 125, "segments/segment-0001.wav"),
    )
    assert rig.writes == [
        (rig.task / "segments/segment-0000.wav", 100, 600),
        (rig.task / "segments/segment-0001.wav", 900, 1_025),
    ]


def test_no_speech_publishes_an_empty_manifest_without_opening_or_writing_slices(
    tmp_path: Path,
) -> None:
    rig = _Rig(tmp_path, intervals=())
    service = rig.service()

    result = service.prepare(rig.command)

    assert result == PrepareSuccess(
        task_work_directory=rig.task,
        canonical_audio=rig.prepared,
        manifest=rig.manifest_path,
        segment_count=0,
    )
    assert rig.log.events == (
        "media.validate",
        "work-directory.create",
        "audio.extract",
        "vad.run",
        "vad.postprocess",
        "manifest.encode",
        "manifest.publish",
    )
    assert rig.manifest is not None
    assert rig.manifest.segments == ()
    assert rig.writes == []


_BOUNDARY_FAILURES = (
    _FailureCase("media.validate", "source-media", "/input/broken.mov", "decode"),
    _FailureCase("work-directory.create", "task-directory", "/output/existing", "create-exclusive"),
    _FailureCase("audio.extract", "audio-extraction", "/output/prepared.wav", "extract"),
    _FailureCase("vad.run", "firered-model", "/models/model.param", "load-model"),
    _FailureCase("vad.run", "ncnn-runtime", "/vendor/firered-vad-ncnn", "load-runtime"),
    _FailureCase("vad.run", "vad-inference", "/output/prepared.wav", "native-provider"),
    _FailureCase("vad.postprocess", "vad-postprocessing", "/output/prepared.wav", "postprocess"),
    _FailureCase("manifest.encode", "manifest", "/output/manifest.json", "encode-manifest"),
    _FailureCase("segments.open-source", "segment-files", "/output/prepared.wav", "open-source"),
    _FailureCase("segment.write.0", "segment-files", "/output/segment-0000.wav", "write"),
    _FailureCase("manifest.publish", "manifest", "/output/manifest.json", "atomic-publish"),
)


@pytest.mark.parametrize("failure", _BOUNDARY_FAILURES, ids=lambda case: case.stage)
def test_each_boundary_failure_is_terminal_and_keeps_resource_and_operation_detail(
    tmp_path: Path,
    failure: _FailureCase,
) -> None:
    rig = _Rig(tmp_path, failure=failure)
    service = rig.service()

    result = service.prepare(rig.command)

    assert isinstance(result, PrepareFailure)
    assert result.stage == failure.stage
    assert failure.resource in result.message
    assert failure.operation in result.message
    assert service.stage is PreparationStage.FAILED
    terminal_index = _SUCCESS_EVENTS.index(failure.event)
    assert rig.log.events == _SUCCESS_EVENTS[: terminal_index + 1]


def test_invalid_intervals_stop_before_manifest_or_segment_creation(tmp_path: Path) -> None:
    rig = _Rig(tmp_path, invalid_intervals=True)
    service = rig.service()

    result = service.prepare(rig.command)

    assert isinstance(result, PrepareFailure)
    assert result.stage == "interval-validation"
    assert str(rig.prepared) in result.message
    assert "validate-intervals" in result.message
    assert service.stage is PreparationStage.FAILED
    assert rig.log.events == _SUCCESS_EVENTS[:5]


def test_generated_artifact_mismatch_stops_publication_with_exact_segment_detail(
    tmp_path: Path,
) -> None:
    rig = _Rig(tmp_path, invalid_metadata_index=1)
    service = rig.service()

    result = service.prepare(rig.command)

    assert isinstance(result, PrepareFailure)
    assert result.stage == "segment-files"
    assert str(rig.task / "segments/segment-0001.wav") in result.message
    assert "verify-segment" in result.message
    assert service.stage is PreparationStage.FAILED
    assert rig.log.events == _SUCCESS_EVENTS[:-1]
    assert "manifest.publish" not in rig.log.events


def test_preparation_stage_is_a_closed_ordered_lifecycle() -> None:
    assert tuple(stage.name for stage in PreparationStage) == (
        "ARGUMENTS_VALIDATED",
        "MEDIA_VALIDATED",
        "WORK_DIRECTORY_CREATED",
        "AUDIO_EXTRACTED",
        "VAD_INFERRED",
        "VAD_POSTPROCESSED",
        "INTERVALS_VALIDATED",
        "MANIFEST_CREATED",
        "SEGMENTS_CREATED",
        "MANIFEST_PUBLISHED",
        "SUCCEEDED",
        "FAILED",
    )
