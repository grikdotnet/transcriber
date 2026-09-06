"""Primitive WAV slicing and generated-artifact metadata adapters."""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WaveMetadata:
    """Infrastructure-local WAV facts reported by Python's WAV boundary."""

    frame_count: int
    sample_rate_hz: int
    channel_count: int
    sample_width_bytes: int
    compression_type: str


class WaveFileReader:
    """Expose metadata and bounded frame reads for one WAV file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @property
    def metadata(self) -> WaveMetadata:
        with wave.open(str(self.path), "rb") as source:
            return _metadata(source)

    def read_frames(self, *, start_sample: int, end_sample: int) -> bytes:
        _validate_primitive_offsets(start_sample=start_sample, end_sample=end_sample)
        with wave.open(str(self.path), "rb") as source:
            if end_sample > source.getnframes():
                raise ValueError("sample interval exceeds source WAV bounds")
            source.setpos(start_sample)
            return source.readframes(end_sample - start_sample)


class WaveSegmentWriter:
    """Write one frame-aligned WAV slice and report its reopened metadata."""

    def __init__(self, source: WaveFileReader) -> None:
        self._source = source

    def write(
        self,
        path: Path,
        *,
        start_sample: int,
        end_sample: int,
    ) -> WaveMetadata:
        pcm = self._source.read_frames(
            start_sample=start_sample,
            end_sample=end_sample,
        )
        source_metadata = self._source.metadata
        destination = Path(path)
        with wave.open(str(destination), "wb") as generated:
            generated.setnchannels(source_metadata.channel_count)
            generated.setsampwidth(source_metadata.sample_width_bytes)
            generated.setframerate(source_metadata.sample_rate_hz)
            generated.setcomptype(source_metadata.compression_type, "not compressed")
            generated.writeframes(pcm)
        return WaveFileReader(destination).metadata


def _metadata(source: wave.Wave_read) -> WaveMetadata:
    return WaveMetadata(
        frame_count=source.getnframes(),
        sample_rate_hz=source.getframerate(),
        channel_count=source.getnchannels(),
        sample_width_bytes=source.getsampwidth(),
        compression_type=source.getcomptype(),
    )


def _validate_primitive_offsets(*, start_sample: int, end_sample: int) -> None:
    if any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in (start_sample, end_sample)
    ):
        raise TypeError("sample offsets must be integers")
    if start_sample < 0 or end_sample <= start_sample:
        raise ValueError("sample interval must have positive duration")
