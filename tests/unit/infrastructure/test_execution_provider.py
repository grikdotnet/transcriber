from __future__ import annotations

from pathlib import Path

import pytest

from transcriber.infrastructure.execution_provider import (
    ExecutionProviderFailure,
    ExecutionProviderLifecycleError,
    ExecutionProviderSession,
    RecognitionRequest,
    RecognitionResult,
    RecognitionToken,
)


class ControlledSession(ExecutionProviderSession):
    """Project-owned session double for primitive lifecycle coverage."""

    def __init__(self, result: RecognitionResult) -> None:
        super().__init__()
        self.result = result
        self.start_calls = 0
        self.recognition_requests: list[RecognitionRequest] = []
        self.stop_calls = 0

    def _start(self, *, readiness_timeout_seconds: float) -> None:
        self.start_calls += 1

    def _recognize(
        self, request: RecognitionRequest, *, timeout_seconds: float
    ) -> RecognitionResult:
        self.recognition_requests.append(request)
        return self.result

    def _stop(
        self, *, graceful_timeout_seconds: float, force_timeout_seconds: float
    ) -> None:
        self.stop_calls += 1


def test_recognition_token_preserves_provider_values() -> None:
    token = RecognitionToken(
        token_id=321,
        text="café 世界",
        log_probability=float("-inf"),
    )

    assert token.token_id == 321
    assert token.text == "café 世界"
    assert token.log_probability == float("-inf")


def test_recognition_result_preserves_ordered_tokens() -> None:
    first_token = RecognitionToken(token_id=7, text="first ", log_probability=-0.1)
    second_token = RecognitionToken(token_id=11, text="次", log_probability=-1.5)

    result = RecognitionResult(tokens=(first_token, second_token))

    assert result.tokens == (first_token, second_token)


def test_recognition_result_represents_an_empty_success() -> None:
    result = RecognitionResult(tokens=())

    assert result.tokens == ()


@pytest.mark.parametrize(
    ("arguments", "message"),
    (
        ((None, "recognized", -0.1), "token_id"),
        ((True, "recognized", -0.1), "token_id"),
        ((7, 3, -0.1), "text"),
        ((7, "recognized", True), "log_probability"),
        ((7, "recognized", 0.1), "log_probability"),
        ((7, "recognized", float("inf")), "log_probability"),
        ((7, "recognized", float("nan")), "log_probability"),
    ),
)
def test_recognition_token_rejects_invalid_provider_values(
    arguments: tuple[object, object, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        RecognitionToken(
            token_id=arguments[0],
            text=arguments[1],
            log_probability=arguments[2],
        )


def test_fresh_session_rejects_recognition_until_started() -> None:
    session = ControlledSession(RecognitionResult(tokens=()))
    request = RecognitionRequest(
        segment_index=0,
        audio_path=Path("/task/segments/segment-0000.wav"),
        recognition_context="",
        language="auto",
    )

    with pytest.raises(ExecutionProviderLifecycleError, match="started"):
        session.recognize(request)

    assert session.recognition_requests == []


def test_started_session_returns_empty_successful_text() -> None:
    session = ControlledSession(RecognitionResult(tokens=()))
    request = RecognitionRequest(
        segment_index=2,
        audio_path=Path("/task/segments/segment-0002.wav"),
        recognition_context="prior text",
        language="en-GB",
    )

    session.start()
    result = session.recognize(request)

    assert result.tokens == ()
    assert session.start_calls == 1
    assert session.recognition_requests == [request]


def test_start_is_allowed_once_and_stop_is_idempotent() -> None:
    session = ControlledSession(RecognitionResult(tokens=()))

    session.start()

    with pytest.raises(ExecutionProviderLifecycleError, match="fresh"):
        session.start()

    session.stop()
    session.stop()

    assert session.stop_calls == 1


def test_provider_failure_keeps_diagnostic_separate_from_application_message() -> None:
    failure = ExecutionProviderFailure(
        message="recognition request failed",
        diagnostic="provider response: \"bad audio\"",
    )

    assert str(failure) == "recognition request failed"
    assert failure.message == "recognition request failed"
    assert failure.diagnostic == 'provider response: "bad audio"'


@pytest.mark.parametrize(
    ("arguments", "message"),
    (
        (
            (-1, Path("/task/segments/segment-0000.wav"), "", "auto"),
            "non-negative",
        ),
        (
            (0, Path("segments/segment-0000.wav"), "", "auto"),
            "absolute",
        ),
        (
            (0.0, Path("/task/segments/segment-0000.wav"), "", "auto"),
            "integer",
        ),
        (
            (True, Path("/task/segments/segment-0000.wav"), "", "auto"),
            "integer",
        ),
    ),
)
def test_recognition_request_requires_primitive_safe_values(
    arguments: tuple[int, Path, str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        RecognitionRequest(
            segment_index=arguments[0],
            audio_path=arguments[1],
            recognition_context=arguments[2],
            language=arguments[3],
        )


def test_recognition_request_accepts_context_at_the_code_point_limit() -> None:
    request = RecognitionRequest(
        segment_index=0,
        audio_path=Path("/task/segments/segment-0000.wav"),
        recognition_context="甲" * 2048,
        language="auto",
    )

    assert request.recognition_context == "甲" * 2048


def test_recognition_request_rejects_context_beyond_the_code_point_limit() -> None:
    with pytest.raises(ValueError, match="2048"):
        RecognitionRequest(
            segment_index=0,
            audio_path=Path("/task/segments/segment-0000.wav"),
            recognition_context="甲" * 2049,
            language="auto",
        )
