from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriber.protocol.qwen_asr import (
    QwenProviderResponseError,
    QwenUnsupportedLanguageError,
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
        b'"stream":false,"temperature":0,"cache_prompt":false,'
        b'"logprobs":true,"top_logprobs":1}'
    )


def test_unsupported_primary_language_tag_is_rejected_before_qwen_request_encoding() -> None:
    with pytest.raises(QwenUnsupportedLanguageError) as raised:
        encode_qwen_request(
            audio_path=Path("/task/segments/segment-0007.wav"),
            recognition_context="",
            language="cy",
        )

    assert str(raised.value) == "Qwen ASR does not support language tag: cy"


def test_explicit_english_primary_tag_encodes_canonical_qwen_label() -> None:
    payload = encode_qwen_request(
        audio_path=Path("/task/segments/segment-0007.wav"),
        recognition_context="Earlier recognized words.",
        language="en",
    )

    assert payload == (
        b'{"messages":[{"role":"system","content":"Earlier recognized words."},'
        b'{"role":"user","content":[{"type":"input_audio",'
        b'"input_audio":{"url":"file://segment-0007.wav"}}]},'
        b'{"role":"assistant","content":"language English<asr_text>"}],'
        b'"stream":false,"temperature":0,"cache_prompt":false,'
        b'"logprobs":true,"top_logprobs":1}'
    )


@pytest.mark.parametrize(
    ("language", "expected_payload"),
    (
        (
            "en-GB",
            b'{"messages":[{"role":"system","content":""},'
            b'{"role":"user","content":[{"type":"input_audio",'
            b'"input_audio":{"url":"file://segment-0007.wav"}}]},'
            b'{"role":"assistant","content":"language English<asr_text>"}],'
            b'"stream":false,"temperature":0,"cache_prompt":false,'
            b'"logprobs":true,"top_logprobs":1}',
        ),
        (
            "en-US",
            b'{"messages":[{"role":"system","content":""},'
            b'{"role":"user","content":[{"type":"input_audio",'
            b'"input_audio":{"url":"file://segment-0007.wav"}}]},'
            b'{"role":"assistant","content":"language English<asr_text>"}],'
            b'"stream":false,"temperature":0,"cache_prompt":false,'
            b'"logprobs":true,"top_logprobs":1}',
        ),
    ),
)
def test_explicit_english_regional_tags_encode_canonical_qwen_label(
    language: str, expected_payload: bytes
) -> None:
    payload = encode_qwen_request(
        audio_path=Path("/task/segments/segment-0007.wav"),
        recognition_context="",
        language=language,
    )

    assert payload == expected_payload


def test_explicit_language_primary_subtag_is_case_insensitive() -> None:
    payload = encode_qwen_request(
        audio_path=Path("/task/segments/segment-0007.wav"),
        recognition_context="",
        language="EN-us",
    )

    assert payload == (
        b'{"messages":[{"role":"system","content":""},'
        b'{"role":"user","content":[{"type":"input_audio",'
        b'"input_audio":{"url":"file://segment-0007.wav"}}]},'
        b'{"role":"assistant","content":"language English<asr_text>"}],'
        b'"stream":false,"temperature":0,"cache_prompt":false,'
        b'"logprobs":true,"top_logprobs":1}'
    )


@pytest.mark.parametrize(
    ("language", "provider_language"),
    (
        ("zh", "Chinese"),
        ("yue", "Cantonese"),
        ("ar", "Arabic"),
        ("de", "German"),
        ("fr", "French"),
        ("es", "Spanish"),
        ("pt", "Portuguese"),
        ("id", "Indonesian"),
        ("it", "Italian"),
        ("ko", "Korean"),
        ("ru", "Russian"),
        ("th", "Thai"),
        ("vi", "Vietnamese"),
        ("ja", "Japanese"),
        ("tr", "Turkish"),
        ("hi", "Hindi"),
        ("ms", "Malay"),
        ("nl", "Dutch"),
        ("sv", "Swedish"),
        ("da", "Danish"),
        ("fi", "Finnish"),
        ("pl", "Polish"),
        ("cs", "Czech"),
        ("fil", "Filipino"),
        ("fa", "Persian"),
        ("el", "Greek"),
        ("ro", "Romanian"),
        ("hu", "Hungarian"),
        ("mk", "Macedonian"),
        ("pt-BR", "Portuguese"),
        ("zh-Hans-CN", "Chinese"),
    ),
)
def test_supported_language_tag_encodes_canonical_qwen_label_from_primary_subtag(
    language: str, provider_language: str
) -> None:
    payload = encode_qwen_request(
        audio_path=Path("/task/segments/segment-0007.wav"),
        recognition_context="",
        language=language,
    )

    assert json.loads(payload)["messages"][-1] == {
        "role": "assistant",
        "content": f"language {provider_language}<asr_text>",
    }


_DEFAULT_PROBABILITY_CONTENT = object()


def _successful_qwen_response(
    *,
    content: str,
    probability_content: object = _DEFAULT_PROBABILITY_CONTENT,
    include_logprobs: bool = True,
    include_probability_content: bool = True,
    finish_reason: object = "stop",
    include_finish_reason: bool = True,
) -> bytes:
    logprobs: dict[str, object] = {}
    if include_probability_content:
        logprobs["content"] = (
            [] if probability_content is _DEFAULT_PROBABILITY_CONTENT else probability_content
        )
    choice: dict[str, object] = {
        "message": {"role": "assistant", "content": content},
    }
    if include_finish_reason:
        choice["finish_reason"] = finish_reason
    if include_logprobs:
        choice["logprobs"] = logprobs
    return json.dumps(
        {
            "choices": [choice]
        }
    ).encode("utf-8")


def test_qwen_response_exposes_ordered_authoritative_token_values_after_initial_prefix() -> None:
    result = decode_qwen_response(
        _successful_qwen_response(
            content="ignored final assistant content",
            probability_content=[
                {"id": 101, "token": "language English<", "logprob": -3.0},
                {"id": 102, "token": "asr_text>First ", "logprob": -0.1},
                {"id": 103, "token": "second", "logprob": -0.2},
            ],
        )
    )

    assert [
        (token.token_id, token.text, token.log_probability) for token in result.tokens
    ] == [(102, "First ", -0.1), (103, "second", -0.2)]


def test_qwen_response_retains_an_initial_unicode_token_stream_without_a_control_prefix() -> None:
    result = decode_qwen_response(
        _successful_qwen_response(
            content="different final assistant content",
            probability_content=[
                {"id": 9, "token": "Привет ", "logprob": -0.1},
                {"id": 10, "token": "世界", "logprob": -0.2},
            ],
        )
    )

    assert [(token.token_id, token.text, token.log_probability) for token in result.tokens] == [
        (9, "Привет ", -0.1),
        (10, "世界", -0.2),
    ]


@pytest.mark.parametrize(
    "message",
    (
        {"role": "assistant"},
        {"role": "assistant", "content": None},
        {"role": "assistant", "content": 17},
    ),
)
def test_qwen_response_uses_authoritative_tokens_when_final_content_is_absent_or_not_text(
    message: dict[str, object],
) -> None:
    payload = json.dumps(
        {
            "choices": [
                {
                    "message": message,
                    "finish_reason": "stop",
                    "logprobs": {
                        "content": [{"id": 1, "token": "speech", "logprob": -0.1}]
                    },
                }
            ]
        }
    ).encode("utf-8")

    result = decode_qwen_response(payload)

    assert [(token.token_id, token.text, token.log_probability) for token in result.tokens] == [
        (1, "speech", -0.1)
    ]


def test_qwen_response_ignores_an_empty_token_without_reordering_neighboring_tokens() -> None:
    result = decode_qwen_response(
        _successful_qwen_response(
            content="different final assistant content",
            probability_content=[
                {"id": 1, "token": "first", "logprob": -0.1},
                {"id": 2, "token": "", "logprob": -0.2},
                {"id": 3, "token": "third", "logprob": -0.3},
            ],
        )
    )

    assert [(token.token_id, token.text, token.log_probability) for token in result.tokens] == [
        (1, "first", -0.1),
        (3, "third", -0.3),
    ]


def test_qwen_response_discards_initial_language_none_prefix_as_an_empty_success() -> None:
    result = decode_qwen_response(
        _successful_qwen_response(
            content="nonempty final content is ignored",
            probability_content=[
                {"id": 101, "token": "language None<asr_text>", "logprob": -3.0}
            ],
        )
    )

    assert result.tokens == ()


def test_qwen_response_retains_mixed_control_and_transcript_text_with_its_original_score() -> None:
    result = decode_qwen_response(
        _successful_qwen_response(
            content="different final content",
            probability_content=[
                {
                    "id": 21,
                    "token": "language English<asr_text>Retained transcript",
                    "logprob": -0.7,
                }
            ],
        )
    )

    assert [(token.token_id, token.text, token.log_probability) for token in result.tokens] == [
        (21, "Retained transcript", -0.7)
    ]


def test_qwen_response_retains_a_later_language_marker_as_literal_transcript_text() -> None:
    result = decode_qwen_response(
        _successful_qwen_response(
            content="unrelated assistant message",
            probability_content=[
                {"id": 1, "token": "language English<asr_text>First ", "logprob": -0.1},
                {"id": 2, "token": "language Russian<asr_text>second", "logprob": -0.2},
            ],
        )
    )

    assert [(token.token_id, token.text, token.log_probability) for token in result.tokens] == [
        (1, "First ", -0.1),
        (2, "language Russian<asr_text>second", -0.2),
    ]


@pytest.mark.parametrize(
    ("include_logprobs", "include_probability_content"),
    ((True, True), (True, False), (False, False)),
    ids=("empty-list", "absent-list", "absent-container"),
)
def test_qwen_success_without_exposed_probability_tokens_is_an_empty_result(
    include_logprobs: bool,
    include_probability_content: bool,
) -> None:
    result = decode_qwen_response(
        _successful_qwen_response(
            content="final assistant content does not infer tokens",
            include_logprobs=include_logprobs,
            include_probability_content=include_probability_content,
        )
    )

    assert result.tokens == ()


@pytest.mark.parametrize(
    "probability_content",
    (
        None,
        {},
        "not an array",
        [None],
        [[]],
        [{}],
        [{"id": None, "token": "speech", "logprob": -0.1}],
        [{"token": "speech", "logprob": -0.1}],
        [{"id": 1, "token": None, "logprob": -0.1}],
        [{"id": 1, "logprob": -0.1}],
        [{"id": 1, "token": "speech", "logprob": None}],
        [{"id": 1, "token": "speech"}],
        [{"id": True, "token": "speech", "logprob": -0.1}],
        [{"id": 1.5, "token": "speech", "logprob": -0.1}],
        [{"id": "1", "token": "speech", "logprob": -0.1}],
        [{"id": 1, "token": True, "logprob": -0.1}],
        [{"id": 1, "token": 17, "logprob": -0.1}],
        [{"id": 1, "token": "speech", "logprob": True}],
        [{"id": 1, "token": "speech", "logprob": "-0.1"}],
        [{"id": 1, "token": "speech", "logprob": [-0.1]}],
        [{"id": 1, "token": "speech", "logprob": 0.1}],
        [{"id": 1, "token": "speech", "logprob": float("nan")}],
        [{"id": 1, "token": "speech", "logprob": float("inf")}],
        [{"id": 1, "token": "speech", "logprob": -int("9" * 400)}],
    ),
)
def test_qwen_response_rejects_malformed_present_probability_content(
    probability_content: object,
) -> None:
    with pytest.raises(QwenProviderResponseError, match="provider response"):
        decode_qwen_response(
            _successful_qwen_response(
                content="ignored assistant content",
                probability_content=probability_content,
            )
        )


@pytest.mark.parametrize("log_probability", (float("-inf"), 0.0))
def test_qwen_response_accepts_negative_infinite_and_zero_log_probability(
    log_probability: float,
) -> None:
    result = decode_qwen_response(
        _successful_qwen_response(
            content="ignored assistant content",
            probability_content=[
                {"id": 1, "token": "speech", "logprob": log_probability}
            ],
        )
    )

    assert [(token.token_id, token.text, token.log_probability) for token in result.tokens] == [
        (1, "speech", log_probability)
    ]


@pytest.mark.parametrize(
    "token_text",
    (
        "<asr_text>",
        "language <asr_text>",
    ),
)
def test_qwen_response_rejects_malformed_initial_metadata(token_text: str) -> None:
    with pytest.raises(QwenProviderResponseError, match="provider response"):
        decode_qwen_response(
            _successful_qwen_response(
                content="ignored assistant content",
                probability_content=[{"id": 1, "token": token_text, "logprob": -0.1}],
            )
        )


@pytest.mark.parametrize(
    "token_text",
    (
        "language English",
        "language English transcript",
    ),
)
def test_qwen_response_retains_language_looking_text_without_a_complete_initial_prefix(
    token_text: str,
) -> None:
    result = decode_qwen_response(
        _successful_qwen_response(
            content="ignored assistant content",
            probability_content=[{"id": 1, "token": token_text, "logprob": -0.1}],
        )
    )

    assert [(token.token_id, token.text, token.log_probability) for token in result.tokens] == [
        (1, token_text, -0.1)
    ]


@pytest.mark.parametrize(
    ("finish_reason", "include_finish_reason"),
    (("length", True), ("tool_calls", True), ("error", True), (None, True), ("stop", False)),
    ids=("length", "tool-calls", "error", "null", "missing"),
)
def test_qwen_response_rejects_abnormal_or_missing_completion(
    finish_reason: object,
    include_finish_reason: bool,
) -> None:
    with pytest.raises(QwenProviderResponseError, match="provider response"):
        decode_qwen_response(
            _successful_qwen_response(
                content="ignored assistant content",
                finish_reason=finish_reason,
                include_finish_reason=include_finish_reason,
            )
        )


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
