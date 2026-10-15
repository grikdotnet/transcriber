"""Full-recording Diarization lifecycle and final publication (Service)."""

from asyncio import CancelledError
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
from numpy.typing import NDArray

from transcriber.domain.diarization import (
    AssignmentSolver,
    CommunityPrediction,
    NemotronPrediction,
    SampleSpeakerActivity,
    SpeakerActivity,
    clip_nemotron_prediction,
    fuse_predictions,
    mask_activity,
)
from transcriber.domain.manifest import SegmentManifest
from transcriber.infrastructure.diarization_files import DecodedAudio
from transcriber.infrastructure.diarization_provider import (
    DiarizationCancelled,
    DiarizationCleanupFailure,
    RecoverableDiarizationFailure,
)
from transcriber.protocol.diarization_cli import (
    DiarizationCommand,
    DiarizationFailure,
    DiarizationProgress,
    DiarizationStage,
    DiarizationSuccess,
    DiarizationWarning,
)


def _ignore_progress(progress: DiarizationProgress) -> None:
    pass


def _ignore_warning(warning: DiarizationWarning) -> None:
    pass


def _check_cancelled() -> None:
    pass


def _clear_failure_tracebacks(error: BaseException) -> None:
    """Drop failed callback frames before releasing caller-owned audio."""
    pending = [error]
    visited: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
        current.__traceback__ = None


@dataclass(frozen=True, slots=True)
class DiarizeAudio:
    """Orchestrate typed callbacks; adapters finish cleanup before returning."""

    read_manifest_file: Callable[[Path], bytes]
    manifest_decoder: Callable[[bytes], SegmentManifest]
    decode_audio: Callable[[Path, int], DecodedAudio]
    nemotron: Callable[[NDArray[np.float32], int], NemotronPrediction]
    community1: Callable[[NDArray[np.float32], int, int], CommunityPrediction]
    solver: AssignmentSolver
    encode_result: Callable[[tuple[SampleSpeakerActivity, ...]], bytes]
    publish: Callable[[Path, bytes], Path]
    progress: Callable[[DiarizationProgress], None] = _ignore_progress
    warning: Callable[[DiarizationWarning], None] = _ignore_warning
    check_cancelled: Callable[[], None] = _check_cancelled

    def diarize(self, command: DiarizationCommand) -> DiarizationSuccess | DiarizationFailure:
        stage: DiarizationStage = "validate"
        audio: DecodedAudio | None = None
        try:
            self.check_cancelled()
            self.progress(DiarizationProgress(stage))
            root = command.task_work_directory.resolve()
            manifest = self.manifest_decoder(self.read_manifest_file(root))
            audio = self.decode_audio(root, manifest.audio.total_samples)
            self.check_cancelled()
            duration = audio.total_samples / manifest.audio.sample_rate_hz
            activity: tuple[SpeakerActivity[int], ...] = ()
            if manifest.segments:
                stage = "nemotron"
                self.progress(DiarizationProgress(stage))
                self.check_cancelled()
                base = clip_nemotron_prediction(
                    self.nemotron(audio.samples, command.nemo_gpu_index), duration
                )
                self.check_cancelled()
                count = len({row.speaker_id for row in base.activity})
                activity = base.activity
                if count >= 2:
                    stage = "community1"
                    self.progress(DiarizationProgress(stage))
                    self.check_cancelled()
                    try:
                        secondary = self.community1(audio.samples, count, command.vulkan_gpu_index)
                    except RecoverableDiarizationFailure as error:
                        reason = str(error)
                        _clear_failure_tracebacks(error)
                        self.warning(DiarizationWarning(reason))
                    else:
                        self.check_cancelled()
                        stage = "fusion"
                        self.progress(DiarizationProgress(stage))
                        self.check_cancelled()
                        activity = fuse_predictions(base, secondary, duration, self.solver)
                        self.check_cancelled()
            stage = "mask"
            self.progress(DiarizationProgress(stage))
            self.check_cancelled()
            payload = self.encode_result(mask_activity(activity, manifest))
            audio = None
            self.check_cancelled()
            stage = "publish"
            self.progress(DiarizationProgress(stage))
            self.check_cancelled()
            destination = self.publish(root, payload)
            return DiarizationSuccess(destination)
        except (KeyboardInterrupt, CancelledError, DiarizationCancelled) as error:
            message = str(error) or "Diarization cancelled"
            _clear_failure_tracebacks(error)
            return DiarizationFailure("cancelled", message)
        except Exception as error:
            message = str(error) or type(error).__name__
            if isinstance(error, DiarizationCleanupFailure):
                stage = cast(DiarizationStage, error.stage)
            _clear_failure_tracebacks(error)
            return DiarizationFailure(stage, message)
        finally:
            audio = None
