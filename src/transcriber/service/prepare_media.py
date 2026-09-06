"""Preparation workflow orchestration across the local integration boundaries."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum, auto
from pathlib import Path
from typing import Protocol, cast

from transcriber.domain.audio import CanonicalAudio
from transcriber.domain.segments import SampleInterval, convert_sample_intervals
from transcriber.infrastructure.wave_files import WaveMetadata
from transcriber.protocol.cli import FailureStage, PrepareCommand, PrepareFailure, PrepareSuccess
from transcriber.protocol.firered_probabilities import FireRedProbabilityDocument
from transcriber.protocol.manifest import ManifestAudio, ManifestSegment, SegmentManifest


class PreparationStage(Enum):
    """Closed lifecycle for one preparation attempt."""

    ARGUMENTS_VALIDATED = auto()
    MEDIA_VALIDATED = auto()
    WORK_DIRECTORY_CREATED = auto()
    AUDIO_EXTRACTED = auto()
    VAD_INFERRED = auto()
    VAD_POSTPROCESSED = auto()
    INTERVALS_VALIDATED = auto()
    MANIFEST_CREATED = auto()
    SEGMENTS_CREATED = auto()
    MANIFEST_PUBLISHED = auto()
    SUCCEEDED = auto()
    FAILED = auto()


class FfmpegBoundary(Protocol):
    def validate(self, source: Path) -> None: ...
    def extract(self, source: Path, destination: Path) -> None: ...


class WorkDirectoryBoundary(Protocol):
    def create(self, path: Path) -> Path: ...


class VadBoundary(Protocol):
    def run(self, audio: Path) -> FireRedProbabilityDocument: ...


class PostprocessorBoundary(Protocol):
    def process(
        self,
        probabilities: tuple[float, ...],
        max_speech_frame: int,
        total_samples: int,
    ) -> tuple[tuple[int, int], ...]: ...


class SegmentWriterBoundary(Protocol):
    def write(
        self, path: Path, *, start_sample: int, end_sample: int
    ) -> WaveMetadata: ...


class ManifestPublisherBoundary(Protocol):
    def write(self, path: Path, content: bytes) -> None: ...


ManifestEncoder = Callable[[SegmentManifest], bytes]
SegmentWriterFactory = Callable[[Path], SegmentWriterBoundary]


class PrepareMedia:
    """Coordinate the complete preparation use case in lifecycle order."""

    def __init__(
        self,
        *,
        ffmpeg: FfmpegBoundary,
        work_directory: WorkDirectoryBoundary,
        vad: VadBoundary,
        postprocessor: PostprocessorBoundary,
        manifest_encoder: ManifestEncoder,
        segment_writer_factory: SegmentWriterFactory,
        manifest_publisher: ManifestPublisherBoundary,
    ) -> None:
        self._ffmpeg = ffmpeg
        self._work_directory = work_directory
        self._vad = vad
        self._postprocessor = postprocessor
        self._manifest_encoder = manifest_encoder
        self._segment_writer_factory = segment_writer_factory
        self._manifest_publisher = manifest_publisher
        self.stage = PreparationStage.ARGUMENTS_VALIDATED

    def prepare(self, command: PrepareCommand) -> PrepareSuccess | PrepareFailure:
        """Prepare artifacts, returning a closed result rather than leaking exceptions."""
        prepared = command.task_work_directory / "prepared.wav"
        manifest_path = command.task_work_directory / "manifest.json"
        try:
            self._ffmpeg.validate(command.source_media)
            self.stage = PreparationStage.MEDIA_VALIDATED

            self._work_directory.create(command.task_work_directory)
            self.stage = PreparationStage.WORK_DIRECTORY_CREATED

            self._ffmpeg.extract(command.source_media, prepared)
            self.stage = PreparationStage.AUDIO_EXTRACTED

            probability_document = self._vad.run(prepared)
            self.stage = PreparationStage.VAD_INFERRED

            primitive_intervals = self._postprocessor.process(
                probability_document.frames.probabilities,
                command.split_target_frames,
                probability_document.audio.total_samples,
            )
            self.stage = PreparationStage.VAD_POSTPROCESSED

            try:
                segments = convert_sample_intervals(
                    tuple(SampleInterval(start, end) for start, end in primitive_intervals),
                    CanonicalAudio(probability_document.audio.total_samples),
                )
            except (TypeError, ValueError) as error:
                raise _WorkflowFailure(
                    "interval-validation", prepared, "validate-intervals"
                ) from error
            self.stage = PreparationStage.INTERVALS_VALIDATED

            manifest = SegmentManifest(
                schema_version=1,
                audio=ManifestAudio(total_samples=probability_document.audio.total_samples),
                segments=tuple(
                    ManifestSegment(
                        index=segment.index,
                        start_sample=segment.start_sample,
                        end_sample=segment.end_sample,
                        duration_samples=segment.duration_samples,
                        path=f"segments/segment-{segment.index:04d}.wav",
                    )
                    for segment in segments
                ),
            )
            encoded_manifest = self._manifest_encoder(manifest)
            self.stage = PreparationStage.MANIFEST_CREATED

            if segments:
                writer = self._segment_writer_factory(prepared)
                for segment, record in zip(segments, manifest.segments, strict=True):
                    segment_path = command.task_work_directory / record.path
                    metadata = writer.write(
                        segment_path,
                        start_sample=segment.start_sample,
                        end_sample=segment.end_sample,
                    )
                    if not _matches_segment(metadata, segment.duration_samples):
                        raise _WorkflowFailure(
                            "segment-files", segment_path, "verify-segment"
                        )
            self.stage = PreparationStage.SEGMENTS_CREATED

            self._manifest_publisher.write(manifest_path, encoded_manifest)
            self.stage = PreparationStage.MANIFEST_PUBLISHED
            result = PrepareSuccess(
                task_work_directory=command.task_work_directory,
                canonical_audio=prepared,
                manifest=manifest_path,
                segment_count=len(segments),
            )
            self.stage = PreparationStage.SUCCEEDED
            return result
        except Exception as error:
            failed_after = self.stage
            self.stage = PreparationStage.FAILED
            return _failure_result(error, failed_after, prepared, manifest_path)


class _WorkflowFailure(RuntimeError):
    def __init__(self, stage: FailureStage, path: Path, operation: str) -> None:
        self.stage = stage
        self.path = path
        self.operation = operation
        super().__init__(f"{operation}: {path}")


def _matches_segment(metadata: WaveMetadata, duration_samples: int) -> bool:
    return (
        metadata.frame_count == duration_samples
        and metadata.sample_rate_hz == 16_000
        and metadata.channel_count == 1
        and metadata.sample_width_bytes == 2
        and metadata.compression_type == "NONE"
    )


def _failure_result(
    error: Exception,
    failed_after: PreparationStage,
    prepared: Path,
    manifest_path: Path,
) -> PrepareFailure:
    raw_stage = getattr(error, "stage", None)
    operation = str(getattr(error, "operation", type(error).__name__))
    path = Path(getattr(error, "path", prepared))

    if raw_stage == "speech-detection":
        status = getattr(error, "status", None)
        if operation == "start-provider":
            stage: FailureStage = "ncnn-runtime"
        elif status == 4:
            stage = "firered-model"
        else:
            stage = "vad-inference"
    elif raw_stage == "manifest-creation":
        stage = "manifest"
        path = manifest_path
    elif raw_stage in {
        "source-media",
        "task-directory",
        "audio-extraction",
        "firered-model",
        "ncnn-runtime",
        "vad-inference",
        "vad-postprocessing",
        "interval-validation",
        "manifest",
        "segment-files",
    }:
        stage = cast(FailureStage, raw_stage)
    elif isinstance(error, _WorkflowFailure):
        stage = error.stage
    else:
        # The active lifecycle gives errors from collaborators without their own
        # wire label a stable public stage.
        stage = cast(
            FailureStage,
            {
                PreparationStage.ARGUMENTS_VALIDATED: "source-media",
                PreparationStage.MEDIA_VALIDATED: "task-directory",
                PreparationStage.WORK_DIRECTORY_CREATED: "audio-extraction",
                PreparationStage.AUDIO_EXTRACTED: "vad-inference",
                PreparationStage.VAD_INFERRED: "vad-postprocessing",
                PreparationStage.INTERVALS_VALIDATED: "manifest",
                PreparationStage.MANIFEST_CREATED: "segment-files",
                PreparationStage.SEGMENTS_CREATED: "manifest",
            }.get(failed_after, "vad-inference"),
        )

    return PrepareFailure(stage=stage, message=f"{operation}: {path}")
