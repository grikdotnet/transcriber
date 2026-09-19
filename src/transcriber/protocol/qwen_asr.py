"""Pure Qwen3-ASR chat-completion request and response codecs."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final, Never

_ASR_TEXT_MARKER: Final = "<asr_text>"
_QWEN_LANGUAGE_BY_PRIMARY_SUBTAG: Final[Mapping[str, str]] = MappingProxyType(
    {
        "en": "English",
        "pt": "Portuguese",
        "zh": "Chinese",
        "yue": "Cantonese",
        "ar": "Arabic",
        "de": "German",
        "fr": "French",
        "es": "Spanish",
        "id": "Indonesian",
        "it": "Italian",
        "ko": "Korean",
        "ru": "Russian",
        "th": "Thai",
        "vi": "Vietnamese",
        "ja": "Japanese",
        "tr": "Turkish",
        "hi": "Hindi",
        "ms": "Malay",
        "nl": "Dutch",
        "sv": "Swedish",
        "da": "Danish",
        "fi": "Finnish",
        "pl": "Polish",
        "cs": "Czech",
        "fil": "Filipino",
        "fa": "Persian",
        "el": "Greek",
        "ro": "Romanian",
        "hu": "Hungarian",
        "mk": "Macedonian",
    }
)


class QwenProviderResponseError(ValueError):
    """Raised when a Qwen chat-completion response has no usable text result."""


class QwenUnsupportedLanguageError(ValueError):
    """Raised when a valid language tag has no Qwen provider-language mapping."""


class _NegativeInfinity:
    """A JSON extension value that is valid only for a token log probability."""


@dataclass(frozen=True, slots=True)
class QwenRecognitionToken:
    """One Qwen transcript token after provider control removal."""

    token_id: int
    text: str
    log_probability: float


@dataclass(frozen=True, slots=True)
class QwenRecognitionResult:
    """The ordered transcript tokens from one completed Qwen response."""

    tokens: tuple[QwenRecognitionToken, ...]


def encode_qwen_request(*, audio_path: Path, recognition_context: str, language: str) -> bytes:
    """Encode one Qwen recognition request for llama.cpp."""
    if not isinstance(audio_path, Path) or not audio_path.is_absolute():
        raise ValueError("audio path must be an absolute Path")
    if not isinstance(recognition_context, str):
        raise TypeError("recognition context must be text")
    provider_language: str | None = None
    if language != "auto":
        primary_subtag = language.split("-", maxsplit=1)[0].lower()
        provider_language = _QWEN_LANGUAGE_BY_PRIMARY_SUBTAG.get(primary_subtag)
        if provider_language is None:
            raise QwenUnsupportedLanguageError(
                f"Qwen ASR does not support language tag: {language}"
            )

    messages: list[dict[str, object]] = [
        {"role": "system", "content": recognition_context},
        {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {"url": f"file://{audio_path.name}"},
                }
            ],
        },
    ]
    if language != "auto":
        messages.append(
            {"role": "assistant", "content": f"language {provider_language}<asr_text>"}
        )

    document = {
        "messages": messages,
        "stream": False,
        "temperature": 0,
        "cache_prompt": False,
        "logprobs": True,
        "top_logprobs": 1,
    }
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _reject_non_finite_json_constant(value: str) -> Never:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def _decode_json(payload: bytes) -> object:
    return json.loads(payload, parse_constant=_reject_non_finite_json_constant)


def _decode_response_json_constant(value: str) -> _NegativeInfinity:
    if value == "-Infinity":
        return _NegativeInfinity()
    _reject_non_finite_json_constant(value)


def _decode_response_json(payload: bytes) -> object:
    return json.loads(payload, parse_constant=_decode_response_json_constant)


def _decode_token_record(
    record: object,
    allowed_negative_infinities: set[int],
) -> QwenRecognitionToken:
    """Map one successful provider token record into the Protocol result shape."""
    if not isinstance(record, dict):
        raise QwenProviderResponseError("provider response token must be an object")
    token_id = record.get("id")
    text = record.get("token")
    log_probability = record.get("logprob")
    if isinstance(token_id, bool) or not isinstance(token_id, int):
        raise QwenProviderResponseError("provider response token id must be an integer")
    if not isinstance(text, str):
        raise QwenProviderResponseError("provider response token text must be text")
    if isinstance(log_probability, _NegativeInfinity):
        allowed_negative_infinities.add(id(log_probability))
        decoded_log_probability = float("-inf")
    elif isinstance(log_probability, bool) or not isinstance(log_probability, (int, float)):
        raise QwenProviderResponseError("provider response token log probability must be a number")
    else:
        try:
            decoded_log_probability = float(log_probability)
        except OverflowError as error:
            raise QwenProviderResponseError(
                "provider response token log probability must be a number"
            ) from error
    if math.isnan(decoded_log_probability) or decoded_log_probability > 0:
        raise QwenProviderResponseError(
            "provider response token log probability must be negative or zero"
        )
    return QwenRecognitionToken(
        token_id=token_id,
        text=text,
        log_probability=decoded_log_probability,
    )


def _contains_unpermitted_non_finite_json_constant(
    value: object, allowed_negative_infinities: set[int]
) -> bool:
    if isinstance(value, _NegativeInfinity):
        return id(value) not in allowed_negative_infinities
    if isinstance(value, dict):
        return any(
            _contains_unpermitted_non_finite_json_constant(
                nested_value, allowed_negative_infinities
            )
            for nested_value in value.values()
        )
    if isinstance(value, list):
        return any(
            _contains_unpermitted_non_finite_json_constant(item, allowed_negative_infinities)
            for item in value
        )
    return False


def _discard_initial_language_prefix(
    tokens: tuple[QwenRecognitionToken, ...],
) -> tuple[QwenRecognitionToken, ...]:
    """Discard Qwen's one leading language marker while retaining token provenance."""
    source_text = "".join(token.text for token in tokens)
    language_prefix = "language "
    if source_text.startswith(_ASR_TEXT_MARKER):
        raise QwenProviderResponseError("provider response has malformed initial metadata")
    if not source_text.startswith(language_prefix):
        return tokens

    marker_index = source_text.find(_ASR_TEXT_MARKER, len(language_prefix))
    if marker_index < 0:
        return tokens
    language_value = source_text[len(language_prefix) : marker_index]
    if not language_value:
        raise QwenProviderResponseError("provider response has malformed initial metadata")
    if "\r" in language_value or "\n" in language_value:
        return tokens

    remaining_prefix_length = marker_index + len(_ASR_TEXT_MARKER)
    retained_tokens: list[QwenRecognitionToken] = []
    for token in tokens:
        if remaining_prefix_length >= len(token.text):
            remaining_prefix_length -= len(token.text)
            continue
        if remaining_prefix_length:
            retained_text = token.text[remaining_prefix_length:]
            remaining_prefix_length = 0
        else:
            retained_text = token.text
        if retained_text:
            retained_tokens.append(
                QwenRecognitionToken(token.token_id, retained_text, token.log_probability)
            )
    return tuple(retained_tokens)


def decode_qwen_response(payload: bytes) -> QwenRecognitionResult:
    """Return authoritative transcript tokens from one completed Qwen response."""
    try:
        document = _decode_response_json(payload)
    except (TypeError, UnicodeDecodeError, ValueError, RecursionError) as error:
        raise QwenProviderResponseError("provider response must be valid JSON") from error

    if not isinstance(document, dict):
        raise QwenProviderResponseError("provider response must contain one assistant choice")
    choices = document.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise QwenProviderResponseError("provider response must contain one assistant choice")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise QwenProviderResponseError("provider response choice must be an object")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise QwenProviderResponseError(
            "provider response choice must contain an assistant message"
    )
    if message.get("role") != "assistant":
        raise QwenProviderResponseError("provider response message must have assistant role")
    if choice.get("finish_reason") != "stop":
        raise QwenProviderResponseError("provider response must complete with finish reason stop")
    if "logprobs" not in choice:
        return QwenRecognitionResult(())
    logprobs = choice["logprobs"]
    if not isinstance(logprobs, dict):
        raise QwenProviderResponseError("provider response log probabilities must be an object")
    if "content" not in logprobs:
        return QwenRecognitionResult(())
    probability_content = logprobs["content"]
    if not isinstance(probability_content, list):
        raise QwenProviderResponseError("provider response token list must be an array")

    allowed_negative_infinities: set[int] = set()
    tokens = tuple(
        _decode_token_record(record, allowed_negative_infinities)
        for record in probability_content
    )
    if _contains_unpermitted_non_finite_json_constant(
        document, allowed_negative_infinities
    ):
        raise QwenProviderResponseError("provider response must not contain non-finite JSON values")
    non_empty_tokens = tuple(token for token in tokens if token.text)
    return QwenRecognitionResult(_discard_initial_language_prefix(non_empty_tokens))


def extract_qwen_error_message(payload: bytes) -> str | None:
    """Extract the provider's JSON error message when the provider supplied one."""
    try:
        document = _decode_json(payload)
    except (TypeError, UnicodeDecodeError, ValueError, RecursionError):
        return None
    if not isinstance(document, dict):
        return None
    error = document.get("error")
    if not isinstance(error, dict):
        return None
    message = error.get("message")
    return message if isinstance(message, str) and message else None
