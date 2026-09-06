"""Typed segment-manifest entities and deterministic schema-v1 codec."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Final, TypeGuard

SCHEMA_VERSION: Final = 1
AUDIO_PATH: Final = "prepared.wav"
AUDIO_SAMPLE_RATE_HZ: Final = 16_000
AUDIO_CHANNELS: Final = 1
AUDIO_SAMPLE_FORMAT: Final = "pcm_s16le"


@dataclass(frozen=True, slots=True)
class ManifestAudio:
    total_samples: int
    path: str = AUDIO_PATH
    sample_rate_hz: int = AUDIO_SAMPLE_RATE_HZ
    channels: int = AUDIO_CHANNELS
    sample_format: str = AUDIO_SAMPLE_FORMAT


@dataclass(frozen=True, slots=True)
class ManifestSegment:
    index: int
    start_sample: int
    end_sample: int
    duration_samples: int
    path: str


@dataclass(frozen=True, slots=True)
class SegmentManifest:
    schema_version: int
    audio: ManifestAudio
    segments: tuple[ManifestSegment, ...]

    def __post_init__(self) -> None:
        _validate_manifest(self)


def _is_integer(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_manifest(manifest: SegmentManifest) -> None:
    if not _is_integer(manifest.schema_version) or manifest.schema_version != SCHEMA_VERSION:
        raise ValueError("schema_version must equal 1")
    audio = manifest.audio
    if not isinstance(audio, ManifestAudio):
        raise ValueError("audio must be a ManifestAudio")
    if not _is_integer(audio.total_samples) or audio.total_samples < 0:
        raise ValueError("audio.total_samples must be a non-negative integer")
    constant_types_are_valid = (
        isinstance(audio.path, str)
        and _is_integer(audio.sample_rate_hz)
        and _is_integer(audio.channels)
        and isinstance(audio.sample_format, str)
    )
    if (
        not constant_types_are_valid
        or audio.path != AUDIO_PATH
        or audio.sample_rate_hz != AUDIO_SAMPLE_RATE_HZ
        or audio.channels != AUDIO_CHANNELS
        or audio.sample_format != AUDIO_SAMPLE_FORMAT
    ):
        raise ValueError("audio constants do not match the canonical contract")
    if not isinstance(manifest.segments, tuple):
        raise ValueError("segments must be a tuple")

    previous_end = 0
    for expected_index, segment in enumerate(manifest.segments):
        if not isinstance(segment, ManifestSegment):
            raise ValueError("segments must contain ManifestSegment values")
        expected_path = f"segments/segment-{expected_index:04d}.wav"
        fields = (segment.index, segment.start_sample, segment.end_sample, segment.duration_samples)
        if any(not _is_integer(value) for value in fields):
            raise ValueError("segment numeric fields must be integers")
        if segment.index != expected_index:
            raise ValueError("segment index must equal its array position")
        if (
            not isinstance(segment.path, str)
            or segment.path != expected_path
            or _escapes_directory(segment.path)
        ):
            raise ValueError("segment path must match its safe index-derived path")
        if not 0 <= segment.start_sample < segment.end_sample <= audio.total_samples:
            raise ValueError("segment interval must be positive and within audio bounds")
        if segment.duration_samples != segment.end_sample - segment.start_sample:
            raise ValueError("segment duration must equal end_sample - start_sample")
        if expected_index and segment.start_sample < previous_end:
            raise ValueError("segments must be ordered and non-overlapping")
        previous_end = segment.end_sample


def _escapes_directory(path: str) -> bool:
    parsed = PurePosixPath(path)
    return parsed.is_absolute() or ".." in parsed.parts


def encode_manifest(manifest: SegmentManifest) -> bytes:
    """Validate and serialize a manifest as deterministic compact UTF-8 JSON."""
    _validate_manifest(manifest)
    return (json.dumps(asdict(manifest), separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def _closed_object(value: object, keys: frozenset[str], context: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{context} must be an object")
    result = {str(key): item for key, item in value.items()}
    if frozenset(result) != keys:
        raise ValueError(f"{context} fields must be exactly {sorted(keys)}")
    return result


def _required_integer(value: object, context: str) -> int:
    if not _is_integer(value):
        raise ValueError(f"{context} must be an integer")
    return value


def _required_string(value: object, context: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{context} must be a string")
    return value


def decode_manifest(payload: str | bytes) -> SegmentManifest:
    """Decode only a closed schema-v1 manifest and revalidate its invariants."""
    try:
        decoded: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("manifest must be valid UTF-8 JSON") from error
    root = _closed_object(decoded, frozenset({"schema_version", "audio", "segments"}), "root")
    audio_value = _closed_object(
        root["audio"],
        frozenset({"path", "sample_rate_hz", "channels", "sample_format", "total_samples"}),
        "audio",
    )
    segments_value = root["segments"]
    if not isinstance(segments_value, list):
        raise ValueError("segments must be an array")
    segments: list[ManifestSegment] = []
    for value in segments_value:
        segment = _closed_object(
            value,
            frozenset({"index", "start_sample", "end_sample", "duration_samples", "path"}),
            "segment",
        )
        segments.append(
            ManifestSegment(
                index=_required_integer(segment["index"], "segment.index"),
                start_sample=_required_integer(segment["start_sample"], "segment.start_sample"),
                end_sample=_required_integer(segment["end_sample"], "segment.end_sample"),
                duration_samples=_required_integer(
                    segment["duration_samples"], "segment.duration_samples"
                ),
                path=_required_string(segment["path"], "segment.path"),
            )
        )
    return SegmentManifest(
        schema_version=_required_integer(root["schema_version"], "schema_version"),
        audio=ManifestAudio(
            total_samples=_required_integer(audio_value["total_samples"], "audio.total_samples"),
            path=_required_string(audio_value["path"], "audio.path"),
            sample_rate_hz=_required_integer(audio_value["sample_rate_hz"], "audio.sample_rate_hz"),
            channels=_required_integer(audio_value["channels"], "audio.channels"),
            sample_format=_required_string(audio_value["sample_format"], "audio.sample_format"),
        ),
        segments=tuple(segments),
    )
