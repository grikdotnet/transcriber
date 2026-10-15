"""Repository-relative dependency assembly for the local application."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from transcriber.domain.diarization import (
    CommunityPrediction,
    NemotronPrediction,
    SampleSpeakerActivity,
    SpeakerActivity,
)
from transcriber.domain.manifest import decode_manifest, encode_manifest
from transcriber.infrastructure.asr_files import (
    check_segment_files,
    publish_transcript,
    read_manifest_file,
)
from transcriber.infrastructure.diarization_files import decode_canonical_audio, publish_diarization
from transcriber.infrastructure.execution_provider import (
    RecognitionRequest,
    RecognitionResult,
    RecognitionToken,
)
from transcriber.infrastructure.ffmpeg import FfmpegProcess
from transcriber.infrastructure.filesystem import AtomicFileWriter, WorkDirectory
from transcriber.infrastructure.firered_ncnn import FireRedNcnnProcess
from transcriber.infrastructure.firered_postprocessing import FireRedPostprocessor
from transcriber.infrastructure.llama_cpp import HttpLoopbackTransport, LlamaCppExecutionProvider
from transcriber.infrastructure.nemo_speech import NemoSpeechAdapter
from transcriber.infrastructure.process import SubprocessManagedProcessStarter, SubprocessRunner
from transcriber.infrastructure.pyannote import Community1Diarizer
from transcriber.infrastructure.wave_files import WaveFileReader, WaveSegmentWriter
from transcriber.protocol.asr_cli import AsrCommand, AsrFailure, AsrProgress, AsrSuccess
from transcriber.protocol.asr_model_manifest import AsrModelCapabilities, decode_asr_model_manifest
from transcriber.protocol.cli import PrepareCommand, PrepareFailure, PrepareSuccess
from transcriber.protocol.diarization_cli import (
    DiarizationCommand,
    DiarizationFailure,
    DiarizationProgress,
    DiarizationSuccess,
    DiarizationWarning,
)
from transcriber.protocol.diarization_json import (
    DiarizationDocument,
    DiarizationInterval,
    encode_diarization,
)
from transcriber.protocol.firered_probabilities import decode_probability_document
from transcriber.protocol.nemo_diarization import (
    NATIVE_SIGNATURES,
    copy_segments,
    make_model_config,
    make_segment_array,
)
from transcriber.protocol.qwen_asr import (
    decode_qwen_response,
    encode_qwen_request,
    extract_qwen_error_message,
)
from transcriber.service.diarize_audio import DiarizeAudio
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

    diarization_service: DiarizeAudio | None = None

    def diarize(self, command: DiarizationCommand) -> DiarizationSuccess | DiarizationFailure:
        if self.diarization_service is None:
            return DiarizationFailure("validate", "Diarization service is unavailable")
        return self.diarization_service.diarize(command)

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


def build_application(
    *, progress: Callable[[AsrProgress], None] | None = None,
    diarization_progress: Callable[[DiarizationProgress], None] | None = None,
    diarization_warning: Callable[[DiarizationWarning], None] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> Application:
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

    def encode_qwen_recognition_request(request: RecognitionRequest) -> bytes:
        """Map one provider-neutral request into Qwen's request codec."""
        return encode_qwen_request(
            audio_path=request.audio_path,
            recognition_context=request.recognition_context,
            language=request.language,
        )

    def decode_qwen_recognition_response(payload: bytes) -> RecognitionResult:
        """Map Qwen's ordered protocol tokens into provider-neutral tokens."""
        qwen_result = decode_qwen_response(payload)
        return RecognitionResult(
            tokens=tuple(
                RecognitionToken(
                    token_id=token.token_id,
                    text=token.text,
                    log_probability=token.log_probability,
                )
                for token in qwen_result.tokens
            )
        )

    qwen_provider = LlamaCppExecutionProvider(
        executable=paths.llama_provider,
        model_path=paths.qwen_model_directory / qwen_artifacts["model"].path,
        audio_projector_path=paths.qwen_model_directory / qwen_artifacts["audio_projector"].path,
        process_starter=SubprocessManagedProcessStarter(),
        transport=HttpLoopbackTransport(extract_error_message=extract_qwen_error_message),
        encode_request=encode_qwen_recognition_request,
        decode_response=decode_qwen_recognition_response,
    )

    return Application(
        diarization_service=build_diarization_service(
            progress=diarization_progress, warning=diarization_warning,
            check_cancelled=check_cancelled),
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


def build_diarization_service(
    *, progress: Callable[[DiarizationProgress], None] | None = None,
    warning: Callable[[DiarizationWarning], None] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> DiarizeAudio:
    """Assemble lazy runtimes and translate each boundary into its owning layer."""
    paths = resolve_repository_paths()

    def cancellation() -> None:
        if check_cancelled is not None:
            check_cancelled()

    def copy_native_segments(buffer: Any, count: int) -> tuple[tuple[float, float, int], ...]:
        return copy_segments(buffer, count)

    def nemotron(samples: NDArray[np.float32], gpu_index: int) -> NemotronPrediction:
        library = (
            paths.repository_root / "vendor/nemo-speech/install/lib/libnemo_speech_asr_c.dylib"
        )
        adapter = NemoSpeechAdapter(
            library_path=library,
            model_path=paths.repository_root / "models/Nemotron-3-Diarization.q8_0.gguf",
            gpu_index=gpu_index, make_model_config=make_model_config,
            make_segment_array=make_segment_array, copy_segments=copy_native_segments,
            signatures=NATIVE_SIGNATURES, check_cancelled=cancellation,
        )
        return NemotronPrediction(tuple(
            SpeakerActivity(row.start_seconds, row.end_seconds, row.speaker_id)
            for row in adapter.diarize(samples)
        ))

    def community1(
        samples: NDArray[np.float32], count: int, gpu_index: int,
    ) -> CommunityPrediction:
        adapter = Community1Diarizer(
            paths.repository_root / "models/pyannote-community1", gpu_index
        )
        return CommunityPrediction(tuple(
            SpeakerActivity(row.start_seconds, row.end_seconds, row.speaker_id)
            for row in adapter.diarize(samples, count, check_cancelled=cancellation)
        ))

    def solver(matrix: tuple[tuple[float, ...], ...]) -> tuple[tuple[int, int], ...]:
        assignment = import_module("scipy.optimize").linear_sum_assignment
        rows, columns = assignment(matrix, maximize=True)
        return tuple((int(row), int(column)) for row, column in zip(rows, columns, strict=True))

    def encode_result(activity: tuple[SampleSpeakerActivity, ...]) -> bytes:
        return encode_diarization(DiarizationDocument(tuple(
            DiarizationInterval(row.speaker_id, row.start_sample, row.end_sample)
            for row in activity
        )))

    return DiarizeAudio(
        read_manifest_file=read_manifest_file, manifest_decoder=decode_manifest,
        decode_audio=decode_canonical_audio, nemotron=nemotron, community1=community1,
        solver=solver, encode_result=encode_result, publish=publish_diarization,
        progress=progress if progress is not None else lambda _: None,
        warning=warning if warning is not None else lambda _: None,
        check_cancelled=cancellation,
    )
