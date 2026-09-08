"""Pure Qwen3-ASR chat-completion request and response codecs."""

from __future__ import annotations

import json
from collections.abc import Mapping
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
    }
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _reject_non_finite_json_constant(value: str) -> Never:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def _decode_json(payload: bytes) -> object:
    return json.loads(payload, parse_constant=_reject_non_finite_json_constant)


def decode_qwen_response(payload: bytes) -> str:
    """Return recognized text from exactly one llama.cpp chat-completion choice."""
    try:
        document = _decode_json(payload)
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
    content = message.get("content")
    if not isinstance(content, str):
        raise QwenProviderResponseError("provider response assistant content must be text")

    marker_count = content.count(_ASR_TEXT_MARKER)
    if marker_count == 0:
        return content
    if marker_count != 1:
        raise QwenProviderResponseError("provider response has a malformed control prefix")
    metadata, _, recognized_text = content.partition(_ASR_TEXT_MARKER)
    has_language_metadata = any(
        line.startswith("language ") and line.removeprefix("language ").strip()
        for line in metadata.splitlines()
    )
    if not has_language_metadata:
        raise QwenProviderResponseError("provider response has a malformed control prefix")
    return recognized_text


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
