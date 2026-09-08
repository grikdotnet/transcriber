"""Repository-relative dependency assembly for the local application."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

from transcriber.domain.manifest import decode_manifest, encode_manifest
from transcriber.infrastructure.asr_files import (
    check_segment_files,
    publish_transcript,
    read_manifest_file,
)
from transcriber.infrastructure.ffmpeg import FfmpegProcess
from transcriber.infrastructure.filesystem import AtomicFileWriter, WorkDirectory
from transcriber.infrastructure.firered_ncnn import FireRedNcnnProcess
from transcriber.infrastructure.firered_postprocessing import FireRedPostprocessor
from transcriber.infrastructure.llama_cpp import HttpLoopbackTransport, LlamaCppExecutionProvider
from transcriber.infrastructure.process import SubprocessManagedProcessStarter, SubprocessRunner
from transcriber.infrastructure.wave_files import WaveFileReader, WaveSegmentWriter
from transcriber.protocol.asr_cli import AsrCommand, AsrFailure, AsrProgress, AsrSuccess
from transcriber.protocol.asr_model_manifest import AsrModelCapabilities, decode_asr_model_manifest
from transcriber.protocol.cli import PrepareCommand, PrepareFailure, PrepareSuccess
from transcriber.protocol.firered_probabilities import decode_probability_document
from transcriber.protocol.qwen_asr import (
    decode_qwen_response,
    encode_qwen_request,
    extract_qwen_error_message,
)
from transcriber.service.prepare_media import PrepareMedia
from transcriber.service.recognize_segments import RecognizeSegments


@dataclass(frozen=True, slots=True)
class RepositoryPaths:
    """Absolute repository-owned executable and asset paths."""

    repository_root: Path
    ffmpeg: Path
    firered_model_directory: Path
    firered_provider: Path
    llama_provider: Path
    qwen_model_directory: Path


@dataclass(frozen=True, slots=True)
class MediaDependencies:
    """Concrete dependencies needed by the media-ingestion checkpoint."""

    process_runner: SubprocessRunner
    ffmpeg: FfmpegProcess
    work_directory: WorkDirectory
    atomic_file_writer: AtomicFileWriter


class RequiredAsrLanguageError(ValueError):
    """Raised when a resolved ASR Model requires an explicit language."""


@dataclass(frozen=True, slots=True)
class AsrRegistration:
    """One Composition-owned ASR Model to compatible Service registration."""

    model_id: str
    capabilities: AsrModelCapabilities
    service: RecognizeSegments


@dataclass(frozen=True, slots=True)
class Application:
    """Public application facade exposed to the CLI controller."""

    service: PrepareMedia
    asr_service: RecognizeSegments
    asr_model_id: str
    asr_capabilities: AsrModelCapabilities = field(
        default_factory=lambda: AsrModelCapabilities(context=True, language="optional")
    )
    asr_registrations: tuple[AsrRegistration, ...] = ()

    def prepare(self, command: PrepareCommand) -> PrepareSuccess | PrepareFailure:
        return self.service.prepare(command)

    def recognize(self, command: AsrCommand) -> AsrSuccess | AsrFailure:
        """Resolve one built-in ASR Model before any task or output access."""
        registrations = (
            AsrRegistration(
                model_id=self.asr_model_id,
                capabilities=self.asr_capabilities,
                service=self.asr_service,
            ),
            *self.asr_registrations,
        )
        registration = next(
            (item for item in registrations if item.model_id == command.model_id), None
        )
        if registration is None:
            return AsrFailure(
                stage="asr-model",
                message=f"unregistered ASR Model: {command.model_id}",
                model_id=command.model_id,
            )
        if registration.capabilities.language == "required" and command.language == "auto":
            raise RequiredAsrLanguageError("ASR Model requires an explicit language")
        return registration.service.recognize(command)


def resolve_repository_paths() -> RepositoryPaths:
    """Resolve checked-in dependencies without consulting the current directory."""
    repository_root = Path(__file__).resolve().parents[3]
    return RepositoryPaths(
        repository_root=repository_root,
        ffmpeg=repository_root / "vendor" / "ffmpeg",
        firered_model_directory=repository_root / "models" / "firered-vad.ncnn",
        firered_provider=repository_root / "vendor" / "firered-vad-ncnn",
        llama_provider=repository_root / "vendor" / "llama-server",
        qwen_model_directory=repository_root / "models" / "qwen3-asr-1.7b",
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


def build_application(*, progress: Callable[[AsrProgress], None] | None = None) -> Application:
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

    qwen_manifest = decode_asr_model_manifest(
        files("transcriber.resources.asr_models").joinpath("qwen3-asr-1.7b.json").read_bytes()
    )
    if qwen_manifest.execution_provider != "llama-cpp":
        raise ValueError(
            f"unregistered Execution Provider: {qwen_manifest.execution_provider}"
        )
    qwen_artifacts = {artifact.role: artifact for artifact in qwen_manifest.artifacts.files}
    qwen_prerequisites = (
        paths.llama_provider,
        *(
            paths.repository_root / "models" / qwen_manifest.artifacts.root / artifact.path
            for artifact in qwen_manifest.artifacts.files
        ),
    )

    def missing_qwen_prerequisites() -> tuple[str, ...]:
        """Return fixed missing paths in provider then manifest declaration order."""
        return tuple(
            path.relative_to(paths.repository_root).as_posix()
            for path in qwen_prerequisites
            if not path.is_file()
        )

    qwen_provider = LlamaCppExecutionProvider(
        executable=paths.llama_provider,
        model_path=paths.qwen_model_directory / qwen_artifacts["model"].path,
        audio_projector_path=paths.qwen_model_directory / qwen_artifacts["audio_projector"].path,
        process_starter=SubprocessManagedProcessStarter(),
        transport=HttpLoopbackTransport(extract_error_message=extract_qwen_error_message),
        encode_request=encode_qwen_request,
        decode_response=decode_qwen_response,
    )

    return Application(
        service=PrepareMedia(
            ffmpeg=dependencies.ffmpeg,
            work_directory=dependencies.work_directory,
            vad=vad,
            postprocessor=FireRedPostprocessor(),
            manifest_encoder=encode_manifest,
            segment_writer_factory=segment_writer,
            manifest_publisher=dependencies.atomic_file_writer,
        ),
        asr_service=RecognizeSegments(
            read_manifest_file=read_manifest_file,
            manifest_decoder=decode_manifest,
            check_segment_files=check_segment_files,
            provider=qwen_provider,
            publish_transcript=publish_transcript,
            progress=progress if progress is not None else lambda _: None,
            context_supported=qwen_manifest.capabilities.context,
            missing_prerequisites=missing_qwen_prerequisites,
        ),
        asr_model_id=qwen_manifest.id,
        asr_capabilities=qwen_manifest.capabilities,
    )
