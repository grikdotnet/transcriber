"""Ordered happy-path orchestration for one ASR Task."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

from transcriber.domain.manifest import SegmentManifest
from transcriber.domain.transcript import Transcript
from transcriber.infrastructure.asr_files import AsrTaskFilesFailure
from transcriber.infrastructure.execution_provider import (
    ExecutionProvider,
    ExecutionProviderFailure,
    RecognitionRequest,
)
from transcriber.protocol.asr_cli import (
    AsrCommand,
    AsrFailure,
    AsrFailureStage,
    AsrProgress,
    AsrSuccess,
)

ManifestReader = Callable[[Path], bytes]
ManifestDecoder = Callable[[bytes], SegmentManifest]
SegmentFileChecker = Callable[[Path, Sequence[str], Sequence[int]], Literal[True]]
TranscriptPublisher = Callable[[Path, str, bytes], Path]
ProgressPublisher = Callable[[AsrProgress], None]
MissingPrerequisites = Callable[[], Sequence[str]]


class RecognizeSegments:
    """Recognize every prevalidated Speech Segment in Segment Manifest order."""

    def __init__(
        self,
        *,
        read_manifest_file: ManifestReader,
        manifest_decoder: ManifestDecoder,
        check_segment_files: SegmentFileChecker,
        provider: ExecutionProvider,
        publish_transcript: TranscriptPublisher,
        progress: ProgressPublisher,
        context_supported: bool = True,
        missing_prerequisites: MissingPrerequisites = lambda: (),
    ) -> None:
        self._read_manifest_file = read_manifest_file
        self._manifest_decoder = manifest_decoder
        self._check_segment_files = check_segment_files
        self._provider = provider
        self._publish_transcript = publish_transcript
        self._progress = progress
        self._context_supported = context_supported
        self._missing_prerequisites = missing_prerequisites

    def recognize(self, command: AsrCommand) -> AsrSuccess | AsrFailure:
        """Publish one Transcript after all ordered Speech Segment results succeed."""
        missing_prerequisites = self._missing_prerequisites()
        if missing_prerequisites:
            return _failure(
                command,
                "asr-model",
                "missing prerequisites: "
                + ", ".join(json.dumps(path) for path in missing_prerequisites),
            )
        try:
            manifest_bytes = self._read_manifest_file(command.task_work_directory)
        except (OSError, RuntimeError):
            return _failure(command, "task-directory", "task directory is unavailable")
        try:
            manifest = self._manifest_decoder(manifest_bytes)
        except (TypeError, ValueError):
            return _failure(command, "segment-manifest", "Segment Manifest is invalid")
        if not manifest.segments:
            return _failure(
                command,
                "segment-manifest",
                "Segment Manifest must contain at least one Speech Segment",
            )

        filenames = tuple(segment.path for segment in manifest.segments)
        durations = tuple(segment.duration_samples for segment in manifest.segments)
        try:
            if (
                self._check_segment_files(command.task_work_directory, filenames, durations)
                is not True
            ):
                return _failure(
                    command,
                    "segment-files",
                    "segment-file validation must return exactly True",
                )
        except AsrTaskFilesFailure as error:
            return _failure(command, "segment-files", str(error))
        except (OSError, RuntimeError, ValueError):
            return _failure(command, "segment-files", "speech segment validation failed")

        try:
            session = self._provider.create(segment_root=command.task_work_directory / "segments")
        except Exception as error:
            return _provider_failure(command, error)
        transcript = Transcript()
        total_segments = len(manifest.segments)
        segment_index: int | None = None
        result: AsrSuccess | AsrFailure | None = None
        progress_error: BaseException | None = None
        cleanup_failed = False
        try:
            session.start(readiness_timeout_seconds=60.0)
            for segment in manifest.segments:
                segment_index = segment.index
                recognition_result = session.recognize(
                    request=_recognition_request(
                        command,
                        segment.index,
                        segment.path,
                        transcript.recognition_context() if self._context_supported else "",
                    ),
                    timeout_seconds=180.0,
                )
                transcript.append(recognition_result.text)
                try:
                    self._progress(
                        AsrProgress(
                            recognized_segments=segment.index + 1,
                            total_segments=total_segments,
                        )
                    )
                except BaseException as error:
                    progress_error = error
                    break
            if progress_error is not None:
                result = None
            else:
                try:
                    session.stop()
                except BaseException as error:
                    cleanup_failed = True
                    result = _cleanup_failure(command, error)
                else:
                    try:
                        transcript_path = self._publish_transcript(
                            command.task_work_directory,
                            command.model_id,
                            transcript.encode(),
                        )
                    except (OSError, RuntimeError, ValueError):
                        result = _failure(command, "transcript", "transcript publication failed")
                    else:
                        result = AsrSuccess(
                            transcript=transcript_path, recognized_segments=total_segments
                        )
        except (KeyboardInterrupt, asyncio.CancelledError):
            result = _failure(command, "cancelled", "task cancelled")
        except Exception as error:
            result = _provider_failure(command, error, segment_index=segment_index)
        finally:
            if not cleanup_failed:
                try:
                    session.stop()
                except BaseException as error:
                    cleanup_failed = True
                    result = _cleanup_failure(command, error)
        if progress_error is not None:
            if cleanup_failed:
                assert isinstance(result, AsrFailure)
                return result
            raise progress_error
        assert result is not None
        return result


def _recognition_request(
    command: AsrCommand, index: int, filename: str, recognition_context: str
) -> RecognitionRequest:
    """Map one Domain Speech Segment reference to primitive provider input."""
    return RecognitionRequest(
        segment_index=index,
        audio_path=command.task_work_directory / filename,
        recognition_context=recognition_context,
        language=command.language,
    )


def _failure(command: AsrCommand, stage: AsrFailureStage, message: str) -> AsrFailure:
    """Build one closed application-owned failure value."""
    return AsrFailure(stage=stage, message=message, model_id=command.model_id)


def _provider_failure(
    command: AsrCommand, error: BaseException, *, segment_index: int | None = None
) -> AsrFailure:
    """Translate provider exceptions without exposing diagnostics as application messages."""
    if isinstance(error, ExecutionProviderFailure):
        stage: AsrFailureStage = (
            "provider-response"
            if error.message == "provider response failed"
            else "execution-provider"
        )
        return AsrFailure(
            stage=stage,
            message=error.message,
            model_id=command.model_id,
            segment_index=segment_index,
            provider_diagnostic=error.diagnostic,
        )
    return AsrFailure(
        stage="execution-provider",
        message="Execution Provider failed",
        model_id=command.model_id,
        segment_index=segment_index,
    )


def _cleanup_failure(command: AsrCommand, error: BaseException) -> AsrFailure:
    """Translate any cleanup error to its closed, index-free provider stage."""
    diagnostic = error.diagnostic if isinstance(error, ExecutionProviderFailure) else None
    return AsrFailure(
        stage="execution-provider",
        message="provider cleanup failed",
        model_id=command.model_id,
        provider_diagnostic=diagnostic,
    )
