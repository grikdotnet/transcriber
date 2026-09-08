from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

import pytest

from transcriber.protocol.asr_model_manifest import decode_asr_model_manifest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_qwen_resource_has_the_checked_in_schema_v1_shape() -> None:
    schema = json.loads(
        (
            REPOSITORY_ROOT
            / "specs/002-segment-asr/contracts/asr-model-manifest.schema.json"
        ).read_text(encoding="utf-8")
    )
    resource = files("transcriber.resources.asr_models").joinpath("qwen3-asr-1.7b.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))

    manifest = decode_asr_model_manifest(resource.read_bytes(), filename=resource.name)

    assert set(payload) == set(schema["required"])
    assert payload["schema_version"] == schema["properties"]["schema_version"]["const"]
    assert set(payload["capabilities"]) == set(
        schema["properties"]["capabilities"]["required"]
    )
    assert set(payload["artifacts"]) == set(schema["properties"]["artifacts"]["required"])
    assert manifest.id == payload["id"]


def test_decoder_rejects_all_contractually_closed_object_fields() -> None:
    resource = files("transcriber.resources.asr_models").joinpath("qwen3-asr-1.7b.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    payload["artifacts"]["files"]["model"]["unexpected"] = "field"

    try:
        decode_asr_model_manifest(json.dumps(payload), filename=resource.name)
    except ValueError as error:
        assert str(error) == "model fields must be exactly: path, sha256"
    else:
        pytest.fail("unknown artifact record field must be rejected")
