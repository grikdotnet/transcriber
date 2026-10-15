"""Canonical Audio decoding and atomic Diarization publication boundaries."""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from transcriber.infrastructure.asr_files import read_manifest_file as read_manifest_file
from transcriber.infrastructure.filesystem import AtomicFileWriter, FilePublicationFailure
from transcriber.infrastructure.wave_files import WaveFileReader


@dataclass(frozen=True, slots=True)
class DecodedAudio:
    """One owning sample buffer shared by identity between runtime adapters."""

    samples: NDArray[np.float32]
    total_samples: int


class DiarizationFilesFailure(RuntimeError):
    """Input or publication failure with the public workflow stage."""

    def __init__(self, *, stage: Literal["validate", "publish"], reason: str, path: Path) -> None:
        self.stage = stage
        self.reason = reason
        self.path = path
        super().__init__(f"{reason} at {path}")


def decode_canonical_audio(task_work_directory: Path, expected_total_samples: int) -> DecodedAudio:
    """Validate schema-fixed Canonical Audio and decode complete PCM16 once."""
    requested = Path(task_work_directory)
    try:
        task_root = requested.resolve()
        canonical = task_root / "prepared.wav"
        if canonical.is_symlink():
            raise DiarizationFilesFailure(stage="validate", reason="symlink", path=canonical)
        resolved = canonical.resolve()
        if not resolved.is_relative_to(task_root) or not canonical.is_file():
            raise DiarizationFilesFailure(
                stage="validate", reason="not-contained-regular-file", path=canonical
            )
        if (
            isinstance(expected_total_samples, bool)
            or not isinstance(expected_total_samples, int)
            or expected_total_samples < 0
        ):
            raise DiarizationFilesFailure(stage="validate", reason="sample-count", path=canonical)
        reader = WaveFileReader(canonical)
        metadata = reader.metadata
        if (
            metadata.sample_rate_hz != 16000
            or metadata.channel_count != 1
            or metadata.sample_width_bytes != 2
            or metadata.compression_type != "NONE"
        ):
            raise DiarizationFilesFailure(stage="validate", reason="format", path=canonical)
        if metadata.frame_count != expected_total_samples:
            raise DiarizationFilesFailure(stage="validate", reason="sample-count", path=canonical)
        pcm = (
            reader.read_frames(start_sample=0, end_sample=metadata.frame_count)
            if metadata.frame_count
            else b""
        )
        if len(pcm) != metadata.frame_count * 2:
            raise DiarizationFilesFailure(stage="validate", reason="pcm-length", path=canonical)
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
        samples /= np.float32(32768)
        return DecodedAudio(samples=samples, total_samples=metadata.frame_count)
    except (EOFError, OSError, RuntimeError, ValueError, wave.Error) as error:
        if isinstance(error, DiarizationFilesFailure):
            raise
        raise DiarizationFilesFailure(
            stage="validate", reason="canonical-audio", path=requested / "prepared.wav"
        ) from error


def publish_diarization(task_work_directory: Path, diarization_bytes: bytes) -> Path:
    """Publish complete bytes using the existing writer's durability behavior."""
    destination = Path(task_work_directory) / "diarization.json"
    try:
        destination = Path(task_work_directory).resolve() / "diarization.json"
        AtomicFileWriter().write(destination, diarization_bytes)
    except (FilePublicationFailure, OSError, RuntimeError) as error:
        raise DiarizationFilesFailure(
            stage="publish", reason="atomic-publish", path=destination
        ) from error
    return destination
