from __future__ import annotations

import json
from pathlib import Path

from transcriber.domain.manifest import ManifestAudio, SegmentManifest, encode_manifest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_empty_manifest_matches_checked_in_schema_shape() -> None:
    schema = json.loads(
        (
            REPOSITORY_ROOT / "specs/001-audio-segmentation-middleware/contracts/manifest.schema.json"
        ).read_text(encoding="utf-8")
    )
    payload = json.loads(encode_manifest(SegmentManifest(1, ManifestAudio(0), ())))

    assert set(payload) == set(schema["required"])
    assert payload["schema_version"] == schema["properties"]["schema_version"]["const"]
    assert set(payload["audio"]) == set(schema["properties"]["audio"]["required"])
    assert payload["segments"] == []
