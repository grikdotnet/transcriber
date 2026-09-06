"""Closed FireRedVAD native-runner probability document codec."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Final

SCHEMA_VERSION: Final = 1
AUDIO_SAMPLE_RATE_HZ: Final = 16_000
AUDIO_CHANNELS: Final = 1
AUDIO_SAMPLE_FORMAT: Final = "pcm_s16le"
FRAME_LENGTH_SAMPLES: Final = 400
FRAME_SHIFT_SAMPLES: Final = 160


@dataclass(frozen=True, slots=True)
class ProbabilityAudio:
    sample_rate_hz: int
    channels: int
    sample_format: str
    total_samples: int


@dataclass(frozen=True, slots=True)
class ProbabilityFrames:
    frame_length_samples: int
    frame_shift_samples: int
    frame_count: int
    probabilities: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class FireRedProbabilityDocument:
    schema_version: int
    audio: ProbabilityAudio
    frames: ProbabilityFrames


def _closed_object(value: object, keys: frozenset[str], context: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{context} must be an object")
    result = {str(key): item for key, item in value.items()}
    if frozenset(result) != keys:
        raise ValueError(f"{context} fields must be exactly {sorted(keys)}")
    return result


def _integer(value: object, context: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context} must be an integer")
    if value < minimum:
        raise ValueError(f"{context} must be at least {minimum}")
    return value


def _constant(value: object, expected: object, context: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ValueError(f"{context} must equal {expected!r}")


def decode_probability_document(payload: str | bytes) -> FireRedProbabilityDocument:
    """Decode and validate exactly one schema-v1 probability document."""
    try:
        decoded: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("probability document must be valid UTF-8 JSON") from error

    root = _closed_object(decoded, frozenset({"schema_version", "audio", "frames"}), "root")
    _constant(root["schema_version"], SCHEMA_VERSION, "schema_version")
    audio_value = _closed_object(
        root["audio"],
        frozenset({"sample_rate_hz", "channels", "sample_format", "total_samples"}),
        "audio",
    )
    _constant(audio_value["sample_rate_hz"], AUDIO_SAMPLE_RATE_HZ, "audio.sample_rate_hz")
    _constant(audio_value["channels"], AUDIO_CHANNELS, "audio.channels")
    _constant(audio_value["sample_format"], AUDIO_SAMPLE_FORMAT, "audio.sample_format")
    total_samples = _integer(audio_value["total_samples"], "audio.total_samples")

    frames_value = _closed_object(
        root["frames"],
        frozenset({"frame_length_samples", "frame_shift_samples", "frame_count", "probabilities"}),
        "frames",
    )
    _constant(
        frames_value["frame_length_samples"], FRAME_LENGTH_SAMPLES, "frames.frame_length_samples"
    )
    _constant(
        frames_value["frame_shift_samples"], FRAME_SHIFT_SAMPLES, "frames.frame_shift_samples"
    )
    frame_count = _integer(frames_value["frame_count"], "frames.frame_count")
    raw_probabilities = frames_value["probabilities"]
    if not isinstance(raw_probabilities, list):
        raise TypeError("frames.probabilities must be an array")
    probabilities: list[float] = []
    for raw_probability in raw_probabilities:
        if isinstance(raw_probability, bool) or not isinstance(raw_probability, (int, float)):
            raise TypeError("probability must be a number")
        probability = float(raw_probability)
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError("probability must be finite and in [0, 1]")
        probabilities.append(probability)
    if frame_count != len(probabilities):
        raise ValueError("frames.frame_count must equal probability array length")

    return FireRedProbabilityDocument(
        schema_version=SCHEMA_VERSION,
        audio=ProbabilityAudio(
            sample_rate_hz=AUDIO_SAMPLE_RATE_HZ,
            channels=AUDIO_CHANNELS,
            sample_format=AUDIO_SAMPLE_FORMAT,
            total_samples=total_samples,
        ),
        frames=ProbabilityFrames(
            frame_length_samples=FRAME_LENGTH_SAMPLES,
            frame_shift_samples=FRAME_SHIFT_SAMPLES,
            frame_count=frame_count,
            probabilities=tuple(probabilities),
        ),
    )
