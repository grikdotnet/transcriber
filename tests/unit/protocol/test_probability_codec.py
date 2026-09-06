from __future__ import annotations

import json
from math import inf, nan

import pytest

from transcriber.protocol.firered_probabilities import (
    AUDIO_CHANNELS,
    AUDIO_SAMPLE_FORMAT,
    AUDIO_SAMPLE_RATE_HZ,
    FRAME_LENGTH_SAMPLES,
    FRAME_SHIFT_SAMPLES,
    SCHEMA_VERSION,
    decode_probability_document,
)


def probability_payload(probabilities: list[float] | None = None) -> dict[str, object]:
    values = [0.1, 0.9] if probabilities is None else probabilities
    return {
        "schema_version": 1,
        "audio": {
            "sample_rate_hz": 16_000,
            "channels": 1,
            "sample_format": "pcm_s16le",
            "total_samples": 720,
        },
        "frames": {
            "frame_length_samples": 400,
            "frame_shift_samples": 160,
            "frame_count": len(values),
            "probabilities": values,
        },
    }


def test_decodes_closed_probability_document_and_public_constants() -> None:
    document = decode_probability_document(json.dumps(probability_payload()))

    assert SCHEMA_VERSION == 1
    assert AUDIO_SAMPLE_RATE_HZ == 16_000
    assert AUDIO_CHANNELS == 1
    assert AUDIO_SAMPLE_FORMAT == "pcm_s16le"
    assert FRAME_LENGTH_SAMPLES == 400
    assert FRAME_SHIFT_SAMPLES == 160
    assert document.audio.total_samples == 720
    assert document.frames.frame_count == len(document.frames.probabilities) == 2
    assert document.frames.probabilities == (0.1, 0.9)


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("root", "schema_version", 2),
        ("audio", "sample_rate_hz", 8_000),
        ("audio", "channels", 2),
        ("audio", "sample_format", "float32"),
        ("audio", "total_samples", -1),
        ("frames", "frame_length_samples", 401),
        ("frames", "frame_shift_samples", 161),
        ("frames", "frame_count", 3),
    ],
)
def test_rejects_invalid_constants_counts_and_metadata(
    section: str, key: str, value: object
) -> None:
    payload = probability_payload()
    target = payload if section == "root" else payload[section]
    assert isinstance(target, dict)
    target[key] = value

    with pytest.raises(ValueError):
        decode_probability_document(json.dumps(payload))


@pytest.mark.parametrize("value", [nan, inf, -inf, -0.01, 1.01, True, "0.5"])
def test_rejects_invalid_probability_values(value: object) -> None:
    payload = probability_payload([value])  # type: ignore[list-item]

    with pytest.raises((TypeError, ValueError), match="probability"):
        decode_probability_document(json.dumps(payload))


@pytest.mark.parametrize("section", ["root", "audio", "frames"])
def test_rejects_extra_fields(section: str) -> None:
    payload = probability_payload()
    target = payload if section == "root" else payload[section]
    assert isinstance(target, dict)
    target["extra"] = True

    with pytest.raises(ValueError, match="fields"):
        decode_probability_document(json.dumps(payload))


@pytest.mark.parametrize("payload", ["", "{", "[]", "null", b"\xff"])
def test_rejects_malformed_or_nonobject_json(payload: str | bytes) -> None:
    with pytest.raises(ValueError):
        decode_probability_document(payload)
