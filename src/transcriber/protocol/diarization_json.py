"""Closed final Diarization artifact values and deterministic JSON codec.

Manifest containment and timestamp conversion belong to Domain. This boundary
accepts already masked, sorted and merged sample intervals.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import TypeGuard


@dataclass(frozen=True, slots=True)
class DiarizationInterval:
    speaker_id: int
    start_sample: int
    end_sample: int


@dataclass(frozen=True, slots=True)
class DiarizationTimeBase:
    unit: str = "sample"
    sample_rate_hz: int = 16000
    start_inclusive: bool = True
    end_exclusive: bool = True


@dataclass(frozen=True, slots=True)
class DiarizationDocument:
    intervals: tuple[DiarizationInterval, ...]
    schema_version: int = 1
    time_base: DiarizationTimeBase = field(default_factory=DiarizationTimeBase)

    def __post_init__(self) -> None:
        _validate_document(self)


def _is_integer(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _integer(value: object) -> int:
    if not _is_integer(value):
        raise ValueError("numeric fields must be integers, excluding booleans")
    return value


def _validate_document(document: DiarizationDocument) -> None:
    if _integer(document.schema_version) != 1:
        raise ValueError("schema_version must equal 1")
    base = document.time_base
    if (
        not isinstance(base, DiarizationTimeBase)
        or base.unit != "sample"
        or _integer(base.sample_rate_hz) != 16000
        or base.start_inclusive is not True
        or base.end_exclusive is not True
    ):
        raise ValueError("time_base must match the sample time-base constants")
    if not isinstance(document.intervals, tuple):
        raise ValueError("intervals must be a tuple")
    previous_key = (-1, -1, -1)
    previous_ends: dict[int, int] = {}
    for interval in document.intervals:
        if not isinstance(interval, DiarizationInterval):
            raise ValueError("intervals must contain DiarizationInterval values")
        speaker = _integer(interval.speaker_id)
        start = _integer(interval.start_sample)
        end = _integer(interval.end_sample)
        if speaker <= 0 or not 0 <= start < end:
            raise ValueError("intervals require positive identities and 0 <= start < end")
        key = (start, speaker, end)
        if key < previous_key:
            raise ValueError("intervals must be sorted by start, speaker and end")
        if speaker in previous_ends and start <= previous_ends[speaker]:
            raise ValueError("same-speaker overlapping or touching intervals must be merged")
        previous_key = key
        previous_ends[speaker] = end


def encode_diarization(document: DiarizationDocument) -> bytes:
    """Encode canonical compact UTF-8 JSON with exactly one final LF."""
    _validate_document(document)
    value = {
        "schema_version": document.schema_version,
        "time_base": asdict(document.time_base),
        "intervals": [asdict(interval) for interval in document.intervals],
    }
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _object(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"object fields must be exactly {sorted(keys)}")
    return {str(key): item for key, item in value.items()}


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate object keys are forbidden")
        result[key] = value
    return result


def decode_diarization(payload: str | bytes) -> DiarizationDocument:
    """Decode the closed artifact and reject invalid or noncanonical values."""
    try:
        decoded: object = json.loads(payload, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("diarization must be valid UTF-8 JSON") from error
    root = _object(decoded, {"schema_version", "time_base", "intervals"})
    base = _object(
        root["time_base"], {"unit", "sample_rate_hz", "start_inclusive", "end_exclusive"}
    )
    if (
        base["unit"] != "sample"
        or _integer(base["sample_rate_hz"]) != 16000
        or base["start_inclusive"] is not True
        or base["end_exclusive"] is not True
    ):
        raise ValueError("time_base must match the sample time-base constants")
    rows = root["intervals"]
    if not isinstance(rows, list):
        raise ValueError("intervals must be an array")
    intervals: list[DiarizationInterval] = []
    for row in rows:
        value = _object(row, {"speaker_id", "start_sample", "end_sample"})
        intervals.append(DiarizationInterval(
            _integer(value["speaker_id"]),
            _integer(value["start_sample"]),
            _integer(value["end_sample"]),
        ))
    return DiarizationDocument(tuple(intervals), schema_version=_integer(root["schema_version"]))
