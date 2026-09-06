"""Repository-relative dependency assembly for the local application."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from transcriber.infrastructure.ffmpeg import FfmpegProcess
from transcriber.infrastructure.filesystem import AtomicFileWriter, WorkDirectory
from transcriber.infrastructure.firered_ncnn import FireRedNcnnProcess
from transcriber.infrastructure.firered_postprocessing import FireRedPostprocessor
from transcriber.infrastructure.process import SubprocessRunner
from transcriber.infrastructure.wave_files import WaveFileReader, WaveSegmentWriter
from transcriber.protocol.cli import PrepareCommand, PrepareFailure, PrepareSuccess
from transcriber.protocol.firered_probabilities import decode_probability_document
from transcriber.protocol.manifest import encode_manifest
from transcriber.service.prepare_media import PrepareMedia


@dataclass(frozen=True, slots=True)
class RepositoryPaths:
    """Absolute repository-owned executable and asset paths."""

    repository_root: Path
    ffmpeg: Path
    firered_model_directory: Path
    firered_provider: Path


@dataclass(frozen=True, slots=True)
class MediaDependencies:
    """Concrete dependencies needed by the media-ingestion checkpoint."""

    process_runner: SubprocessRunner
    ffmpeg: FfmpegProcess
    work_directory: WorkDirectory
    atomic_file_writer: AtomicFileWriter


@dataclass(frozen=True, slots=True)
class Application:
    """Public application facade exposed to the CLI controller."""

    service: PrepareMedia

    def prepare(self, command: PrepareCommand) -> PrepareSuccess | PrepareFailure:
        return self.service.prepare(command)


def resolve_repository_paths() -> RepositoryPaths:
    """Resolve checked-in dependencies without consulting the current directory."""
    repository_root = Path(__file__).resolve().parents[3]
    return RepositoryPaths(
        repository_root=repository_root,
        ffmpeg=repository_root / "vendor" / "ffmpeg",
        firered_model_directory=repository_root / "models" / "firered-vad.ncnn",
        firered_provider=repository_root / "vendor" / "firered-vad-ncnn",
    )


def build_media_dependencies() -> MediaDependencies:
    """Build concrete media adapters from repository-owned paths."""
    paths = resolve_repository_paths()
    runner = SubprocessRunner()
    return MediaDependencies(
        process_runner=runner,
        ffmpeg=FfmpegProcess(paths.ffmpeg, runner),
        work_directory=WorkDirectory(),
        atomic_file_writer=AtomicFileWriter(),
    )


def build_application() -> Application:
    """Assemble the complete local workflow from repository-owned paths."""
    paths = resolve_repository_paths()
    dependencies = build_media_dependencies()
    vad = FireRedNcnnProcess(
        paths.firered_provider,
        paths.firered_model_directory,
        dependencies.process_runner,
        decode_probability_document,
    )

    def segment_writer(source: Path) -> WaveSegmentWriter:
        return WaveSegmentWriter(WaveFileReader(source))

    return Application(
        PrepareMedia(
            ffmpeg=dependencies.ffmpeg,
            work_directory=dependencies.work_directory,
            vad=vad,
            postprocessor=FireRedPostprocessor(),
            manifest_encoder=encode_manifest,
            segment_writer_factory=segment_writer,
            manifest_publisher=dependencies.atomic_file_writer,
        )
    )
