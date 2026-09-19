from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from transcriber.composition import application
from transcriber.infrastructure.execution_provider import (
    RecognitionRequest,
    RecognitionResult,
    RecognitionToken,
)
from transcriber.infrastructure.llama_cpp import HttpLoopbackTransport
from transcriber.infrastructure.process import SubprocessManagedProcessStarter
from transcriber.protocol.asr_cli import AsrCommand, AsrFailure, AsrSuccess
from transcriber.protocol.asr_model_manifest import AsrModelCapabilities
from transcriber.protocol.qwen_asr import QwenRecognitionResult, QwenRecognitionToken

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_application_assembles_the_packaged_qwen_registration_from_foreign_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    registrations = 0
    decoded_model_ids: list[str] = []
    original_decode = application.decode_asr_model_manifest

    class CapturingLlamaCppExecutionProvider:
        def __init__(self, **kwargs: object) -> None:
            nonlocal registrations
            registrations += 1
            captured.update(kwargs)

    def capture_manifest_id(payload: str | bytes):
        manifest = original_decode(payload)
        decoded_model_ids.append(manifest.id)
        return manifest

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(application, "decode_asr_model_manifest", capture_manifest_id)
    monkeypatch.setattr(
        application,
        "LlamaCppExecutionProvider",
        CapturingLlamaCppExecutionProvider,
    )

    built = application.build_application()

    assert built.service is not None
    assert built.asr_service is not None
    assert registrations == 1
    assert decoded_model_ids == ["qwen3-asr-1.7b"]
    assert {
        key: value
        for key, value in captured.items()
        if key not in {"process_starter", "transport", "encode_request", "decode_response"}
    } == {
        "executable": REPOSITORY_ROOT / "vendor" / "llama-server",
        "model_path": (
            REPOSITORY_ROOT / "models" / "qwen3-asr-1.7b" / "Qwen3-ASR-1.7B-Q8_0.gguf"
        ),
        "audio_projector_path": (
            REPOSITORY_ROOT
            / "models"
            / "qwen3-asr-1.7b"
            / "mmproj-Qwen3-ASR-1.7B-Q8_0.gguf"
        ),
    }
    assert callable(captured["encode_request"])
    assert callable(captured["decode_response"])
    assert isinstance(captured["process_starter"], SubprocessManagedProcessStarter)
    assert isinstance(captured["transport"], HttpLoopbackTransport)


def test_qwen_request_wrapper_passes_recognition_request_values_to_protocol_encoder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_provider_arguments: dict[str, object] = {}
    captured_encoder_arguments: dict[str, object] = {}

    class CapturingLlamaCppExecutionProvider:
        def __init__(self, **kwargs: object) -> None:
            captured_provider_arguments.update(kwargs)

    def capture_request(**kwargs: object) -> bytes:
        captured_encoder_arguments.update(kwargs)
        return b"encoded request"

    monkeypatch.setattr(
        application,
        "LlamaCppExecutionProvider",
        CapturingLlamaCppExecutionProvider,
    )
    monkeypatch.setattr(application, "encode_qwen_request", capture_request)

    application.build_application()

    request = RecognitionRequest(
        segment_index=3,
        audio_path=tmp_path / "segment-0003.wav",
        recognition_context="earlier recognized text",
        language="nl-NL",
    )
    encode_request = captured_provider_arguments["encode_request"]
    assert callable(encode_request)
    assert encode_request(request) == b"encoded request"
    assert captured_encoder_arguments == {
        "audio_path": request.audio_path,
        "recognition_context": request.recognition_context,
        "language": request.language,
    }


def test_qwen_response_wrapper_maps_ordered_protocol_tokens_to_provider_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_provider_arguments: dict[str, object] = {}
    protocol_result = QwenRecognitionResult(
        tokens=(
            QwenRecognitionToken(token_id=71, text="first", log_probability=-0.2),
            QwenRecognitionToken(token_id=72, text=" second", log_probability=-1.3),
        )
    )

    class CapturingLlamaCppExecutionProvider:
        def __init__(self, **kwargs: object) -> None:
            captured_provider_arguments.update(kwargs)

    def decode_protocol_response(payload: bytes) -> QwenRecognitionResult:
        assert payload == b"provider response"
        return protocol_result

    monkeypatch.setattr(
        application,
        "LlamaCppExecutionProvider",
        CapturingLlamaCppExecutionProvider,
    )
    monkeypatch.setattr(application, "decode_qwen_response", decode_protocol_response)

    application.build_application()

    decode_response = captured_provider_arguments["decode_response"]
    assert callable(decode_response)
    result = decode_response(b"provider response")
    assert isinstance(result, RecognitionResult)
    assert all(isinstance(token, RecognitionToken) for token in result.tokens)
    assert tuple(
        (token.token_id, token.text, token.log_probability) for token in result.tokens
    ) == ((71, "first", -0.2), (72, " second", -1.3))


def test_application_recognizes_only_the_registered_baseline_model(tmp_path: Path) -> None:
    expected = AsrSuccess(transcript=tmp_path / "transcript.txt", recognized_segments=1)

    class AsrService:
        def __init__(self) -> None:
            self.commands: list[AsrCommand] = []

        def recognize(self, command: AsrCommand) -> AsrSuccess:
            self.commands.append(command)
            return expected

    asr_service = AsrService()
    built = application.Application(
        service=object(),  # type: ignore[arg-type]
        asr_service=asr_service,  # type: ignore[arg-type]
        asr_model_id="qwen3-asr-1.7b",
    )
    baseline = AsrCommand(tmp_path, model_id="qwen3-asr-1.7b")
    unregistered = AsrCommand(tmp_path, model_id="another-asr")

    assert built.recognize(baseline) is expected
    assert built.recognize(unregistered) == AsrFailure(
        stage="asr-model",
        message="unregistered ASR Model: another-asr",
        model_id="another-asr",
    )

    assert asr_service.commands == [baseline]


def test_unknown_model_fails_before_the_registered_service_can_access_task_or_output(
    tmp_path: Path,
) -> None:
    class UnexpectedAsrService:
        def recognize(self, command: AsrCommand) -> AsrSuccess:
            raise AssertionError(f"unknown model must precede service work: {command}")

    built = application.Application(
        service=object(),  # type: ignore[arg-type]
        asr_service=UnexpectedAsrService(),  # type: ignore[arg-type]
        asr_model_id="qwen3-asr-1.7b",
    )

    assert built.recognize(AsrCommand(tmp_path, model_id="another-asr")) == AsrFailure(
        stage="asr-model",
        message="unregistered ASR Model: another-asr",
        model_id="another-asr",
    )


def test_second_compatible_registration_uses_unchanged_transcript_service(tmp_path: Path) -> None:
    expected = AsrSuccess(transcript=tmp_path / "transcript.txt", recognized_segments=1)

    class AsrService:
        def __init__(self) -> None:
            self.commands: list[AsrCommand] = []

        def recognize(self, command: AsrCommand) -> AsrSuccess:
            self.commands.append(command)
            return expected

    asr_service = AsrService()
    built = application.Application(
        service=object(),  # type: ignore[arg-type]
        asr_service=asr_service,  # type: ignore[arg-type]
        asr_model_id="qwen3-asr-1.7b",
        asr_registrations=(
            application.AsrRegistration(
                model_id="second-asr",
                capabilities=AsrModelCapabilities(context=False, language="optional"),
                service=asr_service,  # type: ignore[arg-type]
            ),
        ),
    )

    command = AsrCommand(tmp_path, model_id="second-asr")
    assert built.recognize(command) is expected
    assert asr_service.commands == [command]


def test_application_rejects_a_packaged_model_with_no_provider_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_decode = application.decode_asr_model_manifest
    provider_registrations = 0

    def decode_unknown_provider(payload: str | bytes):
        return replace(original_decode(payload), execution_provider="unknown-provider")

    class UnexpectedLlamaCppExecutionProvider:
        def __init__(self, **_: object) -> None:
            nonlocal provider_registrations
            provider_registrations += 1

    monkeypatch.setattr(application, "decode_asr_model_manifest", decode_unknown_provider)
    monkeypatch.setattr(
        application,
        "LlamaCppExecutionProvider",
        UnexpectedLlamaCppExecutionProvider,
    )

    with pytest.raises(ValueError, match="unknown-provider"):
        application.build_application()

    assert provider_registrations == 0


def test_packaged_qwen_aggregates_missing_fixed_paths_in_manifest_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CapturingLlamaCppExecutionProvider:
        def __init__(self, **_: object) -> None:
            pass

    monkeypatch.setattr(
        application,
        "LlamaCppExecutionProvider",
        CapturingLlamaCppExecutionProvider,
    )
    monkeypatch.setattr(Path, "is_file", lambda _: False)

    built = application.build_application()

    assert built.recognize(AsrCommand(tmp_path, model_id="qwen3-asr-1.7b")) == AsrFailure(
        stage="asr-model",
        message=(
            'missing prerequisites: "vendor/llama-server", '
            '"models/qwen3-asr-1.7b/Qwen3-ASR-1.7B-Q8_0.gguf", '
            '"models/qwen3-asr-1.7b/mmproj-Qwen3-ASR-1.7B-Q8_0.gguf"'
        ),
        model_id="qwen3-asr-1.7b",
    )


def test_application_rejects_automatic_language_for_a_required_model_before_service_work(
    tmp_path: Path,
) -> None:
    class UnexpectedAsrService:
        def recognize(self, command: AsrCommand) -> AsrSuccess:
            raise AssertionError(
                f"required-language rejection must precede service work: {command}"
            )

    built = application.Application(
        service=object(),  # type: ignore[arg-type]
        asr_service=UnexpectedAsrService(),  # type: ignore[arg-type]
        asr_model_id="qwen3-asr-1.7b",
        asr_capabilities=AsrModelCapabilities(context=False, language="required"),
    )

    with pytest.raises(ValueError, match="requires an explicit language"):
        built.recognize(AsrCommand(tmp_path, model_id="qwen3-asr-1.7b"))
