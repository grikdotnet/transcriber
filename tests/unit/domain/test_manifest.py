from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriber.domain.manifest import (
    ManifestAudio,
    ManifestSegment,
    SegmentManifest,
    decode_manifest,
    encode_manifest,
)


def valid_manifest() -> SegmentManifest:
    return SegmentManifest(
        schema_version=1,
        audio=ManifestAudio(total_samples=10_000),
        segments=(
            ManifestSegment(
                index=0,
                start_sample=0,
                end_sample=3_200,
                duration_samples=3_200,
                path="segments/segment-0000.wav",
            ),
            ManifestSegment(
                index=1,
                start_sample=4_000,
                end_sample=10_000,
                duration_samples=6_000,
                path="segments/segment-0001.wav",
            ),
        ),
    )


def test_manifest_round_trip_is_closed_deterministic_and_newline_terminated() -> None:
    manifest = valid_manifest()
    encoded = encode_manifest(manifest)

    assert encoded.endswith(b"\n")
    assert encoded.count(b"\n") == 1
    assert encode_manifest(manifest) == encoded
    assert decode_manifest(encoded) == manifest
    assert set(json.loads(encoded)) == {"schema_version", "audio", "segments"}


def test_empty_speech_manifest_is_valid() -> None:
    manifest = SegmentManifest(
        schema_version=1,
        audio=ManifestAudio(total_samples=0),
        segments=(),
    )

    assert decode_manifest(encode_manifest(manifest)) == manifest


def test_decode_uses_payload_without_filesystem_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_filesystem_access(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("domain decoder must not access the filesystem")

    monkeypatch.setattr(Path, "open", fail_filesystem_access)
    monkeypatch.setattr(Path, "read_bytes", fail_filesystem_access)

    assert decode_manifest(encode_manifest(valid_manifest())) == valid_manifest()


@pytest.mark.parametrize("value", [True, False])
def test_direct_manifest_rejects_boolean_schema_version(value: bool) -> None:
    with pytest.raises(ValueError, match="schema_version"):
        SegmentManifest(value, ManifestAudio(total_samples=0), ())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sample_rate_hz", True),
        ("channels", True),
    ],
)
def test_direct_manifest_rejects_boolean_audio_constants(field: str, value: bool) -> None:
    values: dict[str, object] = {
        "total_samples": 0,
        "sample_rate_hz": 16_000,
        "channels": 1,
    }
    values[field] = value
    audio = ManifestAudio(**values)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="audio constants"):
        SegmentManifest(1, audio, ())


@pytest.mark.parametrize(
    "segment",
    [
        ManifestSegment(1, 0, 100, 100, "segments/segment-0001.wav"),
        ManifestSegment(0, 0, 100, 99, "segments/segment-0000.wav"),
        ManifestSegment(0, -1, 100, 101, "segments/segment-0000.wav"),
        ManifestSegment(0, 100, 100, 0, "segments/segment-0000.wav"),
        ManifestSegment(0, 0, 100, 100, "../segment-0000.wav"),
        ManifestSegment(0, 0, 100, 100, "segments/wrong.wav"),
    ],
)
def test_manifest_rejects_invalid_segment_semantics(segment: ManifestSegment) -> None:
    with pytest.raises(ValueError):
        SegmentManifest(1, ManifestAudio(total_samples=1_000), (segment,))


@pytest.mark.parametrize(
    "segments",
    [
        (
            ManifestSegment(0, 0, 500, 500, "segments/segment-0000.wav"),
            ManifestSegment(1, 400, 600, 200, "segments/segment-0001.wav"),
        ),
        (ManifestSegment(0, 0, 1_001, 1_001, "segments/segment-0000.wav"),),
    ],
)
def test_manifest_rejects_overlap_and_out_of_bounds(
    segments: tuple[ManifestSegment, ...],
) -> None:
    with pytest.raises(ValueError):
        SegmentManifest(1, ManifestAudio(total_samples=1_000), segments)


@pytest.mark.parametrize("section", ["root", "audio", "segment"])
def test_decode_rejects_extra_fields(section: str) -> None:
    payload = json.loads(encode_manifest(valid_manifest()))
    target = (
        payload
        if section == "root"
        else payload[section]
        if section == "audio"
        else payload["segments"][0]
    )
    target["extra"] = True

    with pytest.raises(ValueError, match="fields"):
        decode_manifest(json.dumps(payload))
