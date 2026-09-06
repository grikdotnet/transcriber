from __future__ import annotations

import io
import struct
import wave
from collections.abc import Iterable
from pathlib import Path


def make_pcm(samples: Iterable[int]) -> bytes:
    """Encode signed 16-bit samples as deterministic little-endian PCM bytes."""
    values = tuple(samples)
    if any(value < -32_768 or value > 32_767 for value in values):
        raise ValueError("PCM samples must fit signed 16-bit range")
    return struct.pack(f"<{len(values)}h", *values)


def make_pcm_wav(
    path: Path,
    samples: Iterable[int],
    *,
    sample_rate_hz: int = 16_000,
    channels: int = 1,
) -> Path:
    """Write a deterministic signed 16-bit PCM WAV fixture and return its path."""
    if sample_rate_hz <= 0:
        raise ValueError("sample rate must be positive")
    if channels <= 0:
        raise ValueError("channel count must be positive")

    pcm = make_pcm(samples)
    sample_count = len(pcm) // 2
    if sample_count % channels:
        raise ValueError("interleaved sample count must be divisible by channel count")

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate_hz)
        wav.writeframes(pcm)
    path.write_bytes(buffer.getvalue())
    return path
