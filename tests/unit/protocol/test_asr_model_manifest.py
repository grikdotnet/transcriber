from __future__ import annotations

import json
from collections.abc import Callable
from importlib.resources import files
from pathlib import PurePosixPath
from typing import cast

import pytest

from transcriber.protocol.asr_model_manifest import AsrModelArtifact, decode_asr_model_manifest


def _qwen_payload() -> dict[str, object]:
    resource = files("transcriber.resources.asr_models").joinpath("qwen3-asr-1.7b.json")
    return cast(dict[str, object], json.loads(resource.read_text(encoding="utf-8")))


def test_qwen_model_manifest_resource_decodes_to_the_approved_schema_v1_contract() -> None:
    resource = files("transcriber.resources.asr_models").joinpath("qwen3-asr-1.7b.json")

    manifest = decode_asr_model_manifest(resource.read_bytes())

    assert manifest.schema_version == 1
    assert manifest.id == "qwen3-asr-1.7b"
    assert manifest.display_name == "Qwen3-ASR 1.7B Q8_0"
    assert manifest.source_url == "https://huggingface.co/ggml-org/Qwen3-ASR-1.7B-GGUF"
    assert manifest.execution_provider == "llama-cpp"
    assert manifest.capabilities.context is True
    assert manifest.capabilities.language == "optional"
    assert manifest.artifacts.root == PurePosixPath("qwen3-asr-1.7b")
    assert manifest.artifacts.files == (
        AsrModelArtifact(
            role="model",
            path=PurePosixPath("Qwen3-ASR-1.7B-Q8_0.gguf"),
            sha256="58e22d0532d4eacaf034cfac17a6fed159f37c41390c710186783be439d1fc57",
        ),
        AsrModelArtifact(
            role="audio_projector",
            path=PurePosixPath("mmproj-Qwen3-ASR-1.7B-Q8_0.gguf"),
            sha256="46c1d533af3f354ceb37ce855dbceff7da7fa7cf1e6a523df3b13440bd164c0d",
        ),
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (lambda payload: payload.pop("id"), "ASR Model Manifest fields"),
        (lambda payload: payload.update({"extra": True}), "ASR Model Manifest fields"),
        (lambda payload: payload.update({"schema_version": True}), "schema_version"),
        (lambda payload: payload.update({"display_name": 1}), "display_name"),
        (lambda payload: payload.update({"id": "Unsafe_ID"}), "id"),
        (lambda payload: payload.update({"source_url": "http://example.test/model"}), "source_url"),
        (lambda payload: payload.update({"source_url": "https://"}), "source_url"),
        (
            lambda payload: payload["capabilities"].update({"language": "automatic"}),
            "capabilities.language",
        ),
        (
            lambda payload: payload["capabilities"].update({"unknown": True}),
            "capabilities fields",
        ),
        (
            lambda payload: payload["artifacts"].update({"root": "../models"}),
            "artifacts.root",
        ),
        (
            lambda payload: payload["artifacts"]["files"]["model"].update(
                {"path": "../model.gguf"}
            ),
            "model.path",
        ),
        (
            lambda payload: payload["artifacts"]["files"]["model"].update(
                {"path": "model\\escape.gguf"}
            ),
            "model.path",
        ),
        (
            lambda payload: payload["artifacts"]["files"]["model"].update({"sha256": "A" * 64}),
            "model.sha256",
        ),
        (lambda payload: payload["artifacts"].update({"files": {}}), "artifacts.files"),
    ),
)
def test_decoder_rejects_closed_structural_and_semantic_violations(
    mutate: Callable[[dict[str, object]], object],
    message: str,
) -> None:
    payload = _qwen_payload()

    mutate(payload)

    with pytest.raises(ValueError, match=message):
        decode_asr_model_manifest(json.dumps(payload))


def test_decoder_rejects_duplicate_artifact_paths_after_resolution() -> None:
    payload = _qwen_payload()
    artifacts = cast(dict[str, object], payload["artifacts"])
    files_document = cast(dict[str, object], artifacts["files"])
    audio_projector = cast(dict[str, object], files_document["audio_projector"])
    audio_projector["path"] = "Qwen3-ASR-1.7B-Q8_0.gguf"

    with pytest.raises(ValueError, match="duplicate artifact path"):
        decode_asr_model_manifest(json.dumps(payload))


@pytest.mark.parametrize(
    "filename",
    ("another-model.json", "qwen3-asr-1.7b.txt", "nested/qwen3-asr-1.7b.json"),
)
def test_decoder_rejects_unsafe_or_mismatched_resource_filename(filename: str) -> None:
    with pytest.raises(ValueError, match="filename"):
        decode_asr_model_manifest(json.dumps(_qwen_payload()), filename=filename)


def test_decoder_does_not_inspect_artifact_installation_state() -> None:
    payload = _qwen_payload()

    manifest = decode_asr_model_manifest(json.dumps(payload), filename="qwen3-asr-1.7b.json")

    assert manifest.artifacts.root == PurePosixPath("qwen3-asr-1.7b")
