from __future__ import annotations

from pathlib import Path

import pytest

from transcriber.infrastructure.execution_provider import (
    ExecutionProviderFailure,
    ExecutionProviderLifecycleError,
    ExecutionProviderSession,
    RecognitionRequest,
    RecognitionResult,
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


def test_fresh_session_rejects_recognition_until_started() -> None:
    session = ControlledSession(RecognitionResult(text="recognized"))
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
    session = ControlledSession(RecognitionResult(text=""))
    request = RecognitionRequest(
        segment_index=2,
        audio_path=Path("/task/segments/segment-0002.wav"),
        recognition_context="prior text",
        language="en-GB",
    )

    session.start()
    result = session.recognize(request)

    assert result.text == ""
    assert session.start_calls == 1
    assert session.recognition_requests == [request]


def test_start_is_allowed_once_and_stop_is_idempotent() -> None:
    session = ControlledSession(RecognitionResult(text="recognized"))

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
