from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriber.protocol.qwen_asr import (
    QwenProviderResponseError,
    decode_qwen_response,
    encode_qwen_request,
    extract_qwen_error_message,
)


def test_automatic_language_request_has_exact_deterministic_provider_relative_audio_bytes() -> None:
    payload = encode_qwen_request(
        audio_path=Path("/task/segments/segment-0007.wav"),
        recognition_context="",
        language="auto",
    )

    assert payload == (
        b'{"messages":[{"role":"system","content":""},'
        b'{"role":"user","content":[{"type":"input_audio",'
        b'"input_audio":{"url":"file://segment-0007.wav"}}]}],'
        b'"stream":false,"temperature":0,"cache_prompt":false}'
    )


def test_explicit_english_request_maps_context_and_assistant_prefill_to_exact_bytes() -> None:
    payload = encode_qwen_request(
        audio_path=Path("/task/segments/segment-0007.wav"),
        recognition_context="Earlier recognized words.",
        language="en-GB",
    )

    assert payload == (
        b'{"messages":[{"role":"system","content":"Earlier recognized words."},'
        b'{"role":"user","content":[{"type":"input_audio",'
        b'"input_audio":{"url":"file://segment-0007.wav"}}]},'
        b'{"role":"assistant","content":"language English<asr_text>"}],'
        b'"stream":false,"temperature":0,"cache_prompt":false}'
    )


def test_qwen_response_returns_only_recognized_text_after_control_prefix() -> None:
    text = decode_qwen_response(
        b'{"choices":[{"message":{"role":"assistant",'
        b'"content":"language English<asr_text>Recognized words"}}]}'
    )

    assert text == "Recognized words"


def test_qwen_silent_audio_response_is_an_empty_success() -> None:
    text = decode_qwen_response(
        b'{"choices":[{"message":{"role":"assistant",'
        b'"content":"language None<asr_text>"}}]}'
    )

    assert text == ""


@pytest.mark.parametrize(
    ("content", "expected_text"),
    (
        ("Recognized words", "Recognized words"),
        ("language English", "language English"),
        ("language lower-case-label<asr_text>Recognized words", "Recognized words"),
        (
            "provider metadata\nlanguage any provider label\n<asr_text>Recognized words",
            "Recognized words",
        ),
    ),
)
def test_qwen_response_accepts_documented_plain_and_metadata_forms(
    content: str, expected_text: str
) -> None:
    payload = (
        b'{"choices":[{"message":{"role":"assistant","content":'
        + json.dumps(content).encode("utf-8")
        + b"}}]}"
    )

    assert decode_qwen_response(payload) == expected_text


@pytest.mark.parametrize(
    "content",
    (
        "Recognized words language English<asr_text>",
        "language English<asr_text>one<asr_text>two",
        "transcript English<asr_text>Recognized words",
        "<asr_text>Recognized words",
        "language   <asr_text>Recognized words",
    ),
)
def test_qwen_response_rejects_malformed_control_prefixes(content: str) -> None:
    payload = (
        b'{"choices":[{"message":{"role":"assistant","content":'
        + json.dumps(content).encode("utf-8")
        + b"}}]}"
    )

    with pytest.raises(QwenProviderResponseError, match="control prefix"):
        decode_qwen_response(payload)


@pytest.mark.parametrize(
    "payload",
    (
        b"not json",
        b"{}",
        b'{"choices":[]}',
        b'{"choices":[{"message":{"role":"user","content":"not assistant text"}}]}',
        b'{"choices":[{"message":{"role":"assistant","content":null}}]}',
        b'{"choices":[{"message":{"role":"assistant","content":"one"}},'
        b'{"message":{"role":"assistant","content":"two"}}]}',
        b'{"choices":NaN}',
        b'{"choices":Infinity}',
        b'{"choices":-Infinity}',
    ),
)
def test_malformed_qwen_response_is_a_provider_response_failure(payload: bytes) -> None:
    with pytest.raises(QwenProviderResponseError, match="provider response"):
        decode_qwen_response(payload)


def test_qwen_error_message_is_extracted_from_provider_error_document() -> None:
    message = extract_qwen_error_message(
        b'{"error":{"message":"audio item is outside the media path",'
        b'"type":"invalid_request_error"}}'
    )

    assert message == "audio item is outside the media path"


@pytest.mark.parametrize(
    "payload",
    (
        b"not json",
        b"{}",
        b'{"error":{"message":17}}',
        b'{"error":{"message":"provider failure","code":NaN}}',
        b'{"error":{"message":"provider failure","code":Infinity}}',
        b'{"error":{"message":"provider failure","code":-Infinity}}',
    ),
)
def test_qwen_error_message_is_absent_without_a_string_provider_message(payload: bytes) -> None:
    assert extract_qwen_error_message(payload) is None


def test_deeply_nested_response_json_is_a_provider_response_failure() -> None:
    payload = b"[" * 10_000 + b"]" * 10_000

    with pytest.raises(QwenProviderResponseError, match="provider response"):
        decode_qwen_response(payload)


def test_deeply_nested_error_json_has_no_extractable_error_message() -> None:
    payload = b"[" * 10_000 + b"]" * 10_000

    assert extract_qwen_error_message(payload) is None
