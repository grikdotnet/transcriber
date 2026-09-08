"""Filesystem boundaries for ASR task inputs and transcript publication."""

from __future__ import annotations

import wave
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from transcriber.infrastructure.filesystem import AtomicFileWriter
from transcriber.infrastructure.wave_files import WaveFileReader

_CANONICAL_SAMPLE_RATE_HZ = 16_000
_CANONICAL_CHANNEL_COUNT = 1
_CANONICAL_SAMPLE_WIDTH_BYTES = 2
_CANONICAL_COMPRESSION_TYPE = "NONE"


class AsrTaskFilesFailure(RuntimeError):
    """One closed failure for ASR task segment-file validation."""

    def __init__(self, *, filename: str | None, reason: str, path: Path) -> None:
        self.stage = "segment-files"
        self.filename = filename
        self.reason = reason
        self.path = path
        super().__init__(f"{reason} at {path}" if filename is None else f"{reason}: {filename}")


def read_manifest_file(task_work_directory: Path) -> bytes:
    """Read the task's Segment Manifest as opaque bytes."""
    return (Path(task_work_directory) / "manifest.json").read_bytes()


def check_segment_files(
    task_work_directory: Path,
    segment_filenames: Sequence[str],
    expected_duration_samples: Sequence[int],
) -> Literal[True]:
    """Validate every ordered Speech Segment file without returning file state."""
    task_root = _resolve_or_raise(Path(task_work_directory), filename=None)
    segments_directory = task_root / "segments"
    if len(segment_filenames) != len(expected_duration_samples):
        raise AsrTaskFilesFailure(
            filename=None,
            reason="array-length-mismatch",
            path=segments_directory,
        )

    for index, (filename, duration_samples) in enumerate(
        zip(segment_filenames, expected_duration_samples, strict=True)
    ):
        _check_segment_file(
            task_root,
            segments_directory,
            index,
            filename,
            duration_samples,
        )
    return True


def publish_transcript(task_work_directory: Path, model_id: str, transcript_bytes: bytes) -> Path:
    """Atomically publish complete Transcript bytes at the model-derived output path."""
    task_root = _resolve_or_raise(Path(task_work_directory), filename=None)
    output_directory = task_root / f"transcripts-{model_id}"
    if output_directory.is_symlink():
        _resolve_or_raise(output_directory, filename=None)
        raise AsrTaskFilesFailure(
            filename=None,
            reason="escaping",
            path=output_directory,
        )
    output_directory.mkdir(exist_ok=True)
    destination = output_directory / "transcript.txt"
    AtomicFileWriter().write(destination, transcript_bytes)
    return destination


def _check_segment_file(
    task_root: Path,
    segments_directory: Path,
    index: int,
    filename: str,
    duration_samples: int,
) -> None:
    expected_filename = f"segments/segment-{index:04d}.wav"
    if filename != expected_filename:
        raise _failure(task_root, filename, "filename")
    resolved_segments_directory = _resolve_or_raise(segments_directory, filename=filename)
    if not segments_directory.is_dir() or segments_directory.is_symlink():
        raise _failure(task_root, filename, "escaping")

    target = task_root / filename
    if target.is_symlink():
        resolved_target = _resolve_or_raise(target, filename=filename)
        if not resolved_target.is_relative_to(resolved_segments_directory):
            raise _failure(task_root, filename, "escaping")
        raise _failure(task_root, filename, "replaced")
    if not target.is_file():
        raise _failure(task_root, filename, "missing")
    if isinstance(duration_samples, bool) or not isinstance(duration_samples, int):
        raise _failure(task_root, filename, "duration")

    try:
        reader = WaveFileReader(target)
        metadata = reader.metadata
    except (EOFError, OSError, RuntimeError, ValueError, wave.Error) as error:
        raise _failure(task_root, filename, "format") from error
    if (
        metadata.sample_rate_hz != _CANONICAL_SAMPLE_RATE_HZ
        or metadata.channel_count != _CANONICAL_CHANNEL_COUNT
        or metadata.sample_width_bytes != _CANONICAL_SAMPLE_WIDTH_BYTES
        or metadata.compression_type != _CANONICAL_COMPRESSION_TYPE
    ):
        raise _failure(task_root, filename, "format")
    if metadata.frame_count != duration_samples:
        raise _failure(task_root, filename, "duration")
    try:
        pcm = reader.read_frames(start_sample=0, end_sample=metadata.frame_count)
    except (EOFError, OSError, RuntimeError, ValueError, wave.Error) as error:
        raise _failure(task_root, filename, "format") from error
    expected_pcm_length = (
        metadata.frame_count * metadata.channel_count * metadata.sample_width_bytes
    )
    if len(pcm) != expected_pcm_length:
        raise _failure(task_root, filename, "format")


def _failure(task_root: Path, filename: str, reason: str) -> AsrTaskFilesFailure:
    return AsrTaskFilesFailure(filename=filename, reason=reason, path=task_root / filename)


def _resolve_or_raise(path: Path, *, filename: str | None) -> Path:
    try:
        return path.resolve()
    except (OSError, RuntimeError) as error:
        raise AsrTaskFilesFailure(filename=filename, reason="escaping", path=path) from error
