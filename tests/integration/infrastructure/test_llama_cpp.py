"""Controlled happy-path integration coverage for the llama.cpp adapter."""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest

from tests.support.managed_process import ManagedProcessDouble, ManagedProcessStarterDouble
from transcriber.infrastructure import llama_cpp
from transcriber.infrastructure import process as process_module
from transcriber.infrastructure.execution_provider import (
    ExecutionProviderFailure,
    RecognitionRequest,
    RecognitionResult,
    RecognitionToken,
)
from transcriber.infrastructure.llama_cpp import HttpLoopbackTransport, LlamaCppExecutionProvider
from transcriber.infrastructure.process import SubprocessManagedProcessStarter

EXECUTABLE = Path("/repository/vendor/llama-server")
MODEL = Path("/repository/models/qwen3-asr-1.7b/Qwen3-ASR-1.7B-Q8_0.gguf")
PROJECTOR = Path("/repository/models/qwen3-asr-1.7b/mmproj-Qwen3-ASR-1.7B-Q8_0.gguf")
SEGMENT_ROOT = Path("/task/segments")


class LoopbackTransportDouble:
    """Records only loopback provider transport used by the adapter."""

    def __init__(self) -> None:
        self.health_calls: list[tuple[str, int, float]] = []
        self.recognition_calls: list[tuple[str, int, bytes, float]] = []

    def health(self, *, host: str, port: int, timeout_seconds: float) -> bool:
        self.health_calls.append((host, port, timeout_seconds))
        return True

    def recognize(self, *, host: str, port: int, payload: bytes, timeout_seconds: float) -> bytes:
        self.recognition_calls.append((host, port, payload, timeout_seconds))
        return b"provider response"


class ControlledClock:
    """Deterministic monotonic clock used to prove provider deadlines."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class NeverReadyTransport(LoopbackTransportDouble):
    def health(self, *, host: str, port: int, timeout_seconds: float) -> bool:
        super().health(host=host, port=port, timeout_seconds=timeout_seconds)
        return False


class DelayedRecognitionTransport(LoopbackTransportDouble):
    def __init__(self, clock: ControlledClock) -> None:
        super().__init__()
        self._clock = clock

    def recognize(self, *, host: str, port: int, payload: bytes, timeout_seconds: float) -> bytes:
        self._clock.now += timeout_seconds
        return super().recognize(
            host=host, port=port, payload=payload, timeout_seconds=timeout_seconds
        )


class FailingRecognitionTransport(LoopbackTransportDouble):
    def recognize(self, *, host: str, port: int, payload: bytes, timeout_seconds: float) -> bytes:
        raise ExecutionProviderFailure(
            message="recognition request failed", diagnostic="provider HTTP failure"
        )


class ReadyAtDeadlineTransport(LoopbackTransportDouble):
    def __init__(self, clock: ControlledClock, ready_at: float) -> None:
        super().__init__()
        self._clock = clock
        self._ready_at = ready_at

    def health(self, *, host: str, port: int, timeout_seconds: float) -> bool:
        self._clock.now = self._ready_at
        return True


class LateCollisionTransport(LoopbackTransportDouble):
    def __init__(self, process: ManagedProcessDouble) -> None:
        super().__init__()
        self._process = process
        self._has_collided = False

    def health(self, *, host: str, port: int, timeout_seconds: float) -> bool:
        if not self._has_collided:
            self._has_collided = True
            self._process.diagnostic = "x" * 9_000 + "address already in use"
            self._process.returncode = 1
            return False
        return True


def _provider(
    *, transport: LoopbackTransportDouble, clock: ControlledClock, starter=None, ports=None
):
    return LlamaCppExecutionProvider(
        executable=EXECUTABLE,
        model_path=MODEL,
        audio_projector_path=PROJECTOR,
        process_starter=starter or ManagedProcessStarterDouble(ManagedProcessDouble()),
        transport=transport,
        encode_request=lambda _request: b"request",
        decode_response=lambda _payload: RecognitionResult(tokens=()),
        endpoint_port=ports or (lambda: 43127),
        monotonic_clock=clock,
        sleeper=clock.sleep,
    )


def test_readiness_deadline_uses_injected_clock_without_wall_clock_sleep() -> None:
    clock = ControlledClock()
    transport = NeverReadyTransport()
    provider = _provider(transport=transport, clock=clock)

    with pytest.raises(Exception, match="provider startup timed out"):
        provider.create(segment_root=SEGMENT_ROOT).start()

    assert clock.now == 60.0
    assert all(
        host == "127.0.0.1" and timeout <= 60.0
        for host, _, timeout in transport.health_calls
    )


@pytest.mark.parametrize("ready_at", [60.0, 60.01])
def test_ready_health_at_or_after_deadline_is_rejected_then_failed_startup_reaps_once(
    ready_at: float,
) -> None:
    clock = ControlledClock()
    process = ManagedProcessDouble()
    provider = _provider(
        transport=ReadyAtDeadlineTransport(clock, ready_at),
        clock=clock,
        starter=ManagedProcessStarterDouble(process),
    )
    session = provider.create(segment_root=SEGMENT_ROOT)

    with pytest.raises(ExecutionProviderFailure, match="provider startup timed out"):
        session.start()
    session.stop()
    session.stop()

    assert process.terminate_calls == 1
    assert process.wait_timeouts == [60.0]


def test_request_deadline_uses_injected_clock_and_preserves_loopback_only_transport() -> None:
    clock = ControlledClock()
    transport = DelayedRecognitionTransport(clock)
    provider = _provider(transport=transport, clock=clock)
    session = provider.create(segment_root=SEGMENT_ROOT)
    session.start()

    with pytest.raises(Exception, match="recognition request timed out"):
        session.recognize(
            RecognitionRequest(0, SEGMENT_ROOT / "segment-0000.wav", "", "auto")
        )

    assert clock.now == 180.0
    assert transport.recognition_calls == [("127.0.0.1", 43127, b"request", 180.0)]


def test_provider_request_error_retains_separate_diagnostic() -> None:
    clock = ControlledClock()
    provider = _provider(transport=FailingRecognitionTransport(), clock=clock)
    session = provider.create(segment_root=SEGMENT_ROOT)
    session.start()

    with pytest.raises(ExecutionProviderFailure) as raised:
        session.recognize(RecognitionRequest(0, SEGMENT_ROOT / "segment-0000.wav", "", "auto"))

    assert raised.value.message == "recognition request failed"
    assert raised.value.diagnostic == "provider HTTP failure"


@pytest.mark.parametrize("decoder_error", [TypeError, ValueError])
def test_malformed_decoder_failure_has_bounded_provider_response_stage_and_reaps_session(
    decoder_error: type[Exception],
) -> None:
    clock = ControlledClock()
    process = ManagedProcessDouble()
    transport = LoopbackTransportDouble()

    def reject_malformed_response(_payload: bytes) -> RecognitionResult:
        raise decoder_error("untrusted decoder detail " * 1_000)

    provider = LlamaCppExecutionProvider(
        executable=EXECUTABLE,
        model_path=MODEL,
        audio_projector_path=PROJECTOR,
        process_starter=ManagedProcessStarterDouble(process),
        transport=transport,
        encode_request=lambda _request: b"request",
        decode_response=reject_malformed_response,
        endpoint_port=lambda: 43127,
        monotonic_clock=clock,
        sleeper=clock.sleep,
    )
    session = provider.create(segment_root=SEGMENT_ROOT)
    request = RecognitionRequest(0, SEGMENT_ROOT / "segment-0000.wav", "", "auto")

    session.start()
    with pytest.raises(ExecutionProviderFailure) as raised:
        session.recognize(request)
    session.stop()

    assert raised.value.message == "provider response failed"
    assert raised.value.diagnostic is None
    assert clock.now == 0.0
    assert transport.recognition_calls == [("127.0.0.1", 43127, b"request", 180.0)]
    assert process.terminate_calls == 1
    assert process.wait_timeouts == [60.0]


def test_request_encoder_receives_recognition_request_and_decoder_returns_ordered_tokens() -> None:
    clock = ControlledClock()
    transport = LoopbackTransportDouble()
    encoded_requests: list[RecognitionRequest] = []
    decoded_responses: list[bytes] = []
    decoded_tokens = (
        RecognitionToken(token_id=17, text="Olá ", log_probability=-0.1),
        RecognitionToken(token_id=29, text="世界", log_probability=-0.2),
    )
    provider = LlamaCppExecutionProvider(
        executable=EXECUTABLE,
        model_path=MODEL,
        audio_projector_path=PROJECTOR,
        process_starter=ManagedProcessStarterDouble(ManagedProcessDouble()),
        transport=transport,
        encode_request=lambda request: encoded_requests.append(request) or b"encoded request",
        decode_response=lambda response: decoded_responses.append(response)
        or RecognitionResult(tokens=decoded_tokens),
        endpoint_port=lambda: 43127,
        monotonic_clock=clock,
        sleeper=clock.sleep,
    )
    session = provider.create(segment_root=SEGMENT_ROOT)
    request = RecognitionRequest(
        0, SEGMENT_ROOT / "segment-0000.wav", "", "pt-BR"
    )

    session.start()
    result = session.recognize(request)

    assert encoded_requests == [request]
    assert transport.recognition_calls == [("127.0.0.1", 43127, b"encoded request", 180.0)]
    assert decoded_responses == [b"provider response"]
    assert result.tokens == decoded_tokens


def test_request_encoder_failure_sends_no_recognition_http_request() -> None:
    clock = ControlledClock()
    transport = LoopbackTransportDouble()

    def reject_request(_request: RecognitionRequest) -> bytes:
        raise ValueError("Qwen ASR does not support language tag: cy")

    provider = LlamaCppExecutionProvider(
        executable=EXECUTABLE,
        model_path=MODEL,
        audio_projector_path=PROJECTOR,
        process_starter=ManagedProcessStarterDouble(ManagedProcessDouble()),
        transport=transport,
        encode_request=reject_request,
        decode_response=lambda _payload: RecognitionResult(tokens=()),
        endpoint_port=lambda: 43127,
        monotonic_clock=clock,
        sleeper=clock.sleep,
    )
    session = provider.create(segment_root=SEGMENT_ROOT)
    session.start()

    with pytest.raises(ExecutionProviderFailure) as raised:
        session.recognize(
            RecognitionRequest(0, SEGMENT_ROOT / "segment-0000.wav", "", "cy")
        )

    assert raised.value.message == "Qwen ASR does not support language tag: cy"
    assert transport.recognition_calls == []


def test_http_error_uses_the_injected_qwen_error_message_extractor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extracted: list[bytes] = []

    class ResponseDouble:
        status = 503

        def read(self) -> bytes:
            return b'{"error":{"message":"model unavailable"}}'

    class ConnectionDouble:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def request(self, *_args: object, **_kwargs: object) -> None:
            pass

        def getresponse(self) -> ResponseDouble:
            return ResponseDouble()

        def close(self) -> None:
            pass

    monkeypatch.setattr(llama_cpp.http.client, "HTTPConnection", ConnectionDouble)
    transport = HttpLoopbackTransport(
        extract_error_message=lambda payload: extracted.append(payload) or "model unavailable"
    )

    with pytest.raises(ExecutionProviderFailure) as raised:
        transport.recognize(host="127.0.0.1", port=43127, payload=b"request", timeout_seconds=1.0)

    assert extracted == [b'{"error":{"message":"model unavailable"}}']
    assert raised.value.diagnostic == "model unavailable"


def test_child_exit_reports_bounded_private_diagnostic_and_collision_reselects_endpoint() -> None:
    clock = ControlledClock()
    collided = ManagedProcessDouble(returncode=1, diagnostic="address already in use\nprivate log")
    ready = ManagedProcessDouble()
    starter = ManagedProcessStarterDouble(collided, ready)
    ports = iter((43127, 43128))
    provider = _provider(
        transport=LoopbackTransportDouble(),
        clock=clock,
        starter=starter,
        ports=lambda: next(ports),
    )

    session = provider.create(segment_root=SEGMENT_ROOT)
    session.start()
    session.stop()

    assert [call.argv[8] for call in starter.calls] == ["43127", "43128"]
    assert collided.terminate_calls == 0
    assert collided.wait_timeouts == [60.0]
    assert ready.terminate_calls == 1


def test_late_collision_uses_the_final_diagnostic_tail_before_reselecting_endpoint() -> None:
    clock = ControlledClock()
    collided = ManagedProcessDouble()
    ready = ManagedProcessDouble()
    starter = ManagedProcessStarterDouble(collided, ready)
    ports = iter((43127, 43128))
    provider = _provider(
        transport=LateCollisionTransport(collided),
        clock=clock,
        starter=starter,
        ports=lambda: next(ports),
    )

    session = provider.create(segment_root=SEGMENT_ROOT)
    session.start()
    session.stop()

    assert [call.argv[8] for call in starter.calls] == ["43127", "43128"]


def test_non_collision_child_exit_retains_diagnostic_without_public_log_forwarding() -> None:
    clock = ControlledClock()
    process = ManagedProcessDouble(returncode=7, diagnostic="bad\nprovider\x00details")
    provider = _provider(
        transport=LoopbackTransportDouble(),
        clock=clock,
        starter=ManagedProcessStarterDouble(process),
    )

    with pytest.raises(Exception, match="provider startup failed") as raised:
        provider.create(segment_root=SEGMENT_ROOT).start()

    assert raised.value.diagnostic == "bad provider details"


def test_stop_forces_and_reaps_child_after_grace_timeout() -> None:
    clock = ControlledClock()
    process = ManagedProcessDouble(
        wait_timeout_count=1,
        wait_durations=(60.0, 10.0),
        wait_clock=clock.sleep,
    )
    provider = _provider(
        transport=LoopbackTransportDouble(),
        clock=clock,
        starter=ManagedProcessStarterDouble(process),
    )
    session = provider.create(segment_root=SEGMENT_ROOT)
    session.start()
    session.stop()
    session.stop()

    assert process.terminate_calls == 1
    assert process.kill_calls == 1
    assert process.wait_timeouts == [60.0, 10.0]
    assert clock.now == 70.0


def test_subprocess_timeout_is_translated_at_process_boundary_for_forced_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class PopenDouble:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO()
            self.returncode: int | None = None
            self.terminate_calls = 0
            self.kill_calls = 0
            self.wait_timeouts: list[float] = []

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.terminate_calls += 1

        def kill(self) -> None:
            self.kill_calls += 1

        def wait(self, *, timeout: float) -> int:
            self.wait_timeouts.append(timeout)
            if len(self.wait_timeouts) == 1:
                raise subprocess.TimeoutExpired("llama-server", timeout)
            self.returncode = -9
            return self.returncode

    child = PopenDouble()
    monkeypatch.setattr(process_module.subprocess, "Popen", lambda *_args, **_kwargs: child)
    provider = _provider(
        transport=LoopbackTransportDouble(),
        clock=ControlledClock(),
        starter=SubprocessManagedProcessStarter(),
    )
    session = provider.create(segment_root=SEGMENT_ROOT)
    session.start()
    session.stop()
    session.stop()

    assert child.terminate_calls == 1
    assert child.wait_timeouts == [60.0, 10.0]
    assert child.kill_calls == 1
    assert child.returncode == -9


def test_failed_startup_stop_reaps_an_exited_child_once() -> None:
    clock = ControlledClock()
    process = ManagedProcessDouble(returncode=7, diagnostic="failed")
    provider = _provider(
        transport=LoopbackTransportDouble(),
        clock=clock,
        starter=ManagedProcessStarterDouble(process),
    )
    session = provider.create(segment_root=SEGMENT_ROOT)

    with pytest.raises(ExecutionProviderFailure, match="provider startup failed"):
        session.start()
    session.stop()
    session.stop()

    assert process.wait_timeouts == [60.0]


def test_session_starts_one_loopback_server_recognizes_sequentially_and_reaps_normally() -> None:
    process = ManagedProcessDouble()
    starter = ManagedProcessStarterDouble(process)
    transport = LoopbackTransportDouble()
    encoded_requests: list[RecognitionRequest] = []
    decoded_responses: list[bytes] = []
    decoded_result = RecognitionResult(
        tokens=(RecognitionToken(token_id=1, text="recognized text", log_probability=-0.1),)
    )
    provider = LlamaCppExecutionProvider(
        executable=EXECUTABLE,
        model_path=MODEL,
        audio_projector_path=PROJECTOR,
        process_starter=starter,
        transport=transport,
        encode_request=lambda request: encoded_requests.append(request) or b"encoded request",
        decode_response=lambda payload: decoded_responses.append(payload) or decoded_result,
        endpoint_port=lambda: 43127,
    )
    session = provider.create(segment_root=SEGMENT_ROOT)
    first = RecognitionRequest(
        segment_index=0,
        audio_path=SEGMENT_ROOT / "segment-0000.wav",
        recognition_context="",
        language="auto",
    )
    second = RecognitionRequest(
        segment_index=1,
        audio_path=SEGMENT_ROOT / "segment-0001.wav",
        recognition_context="",
        language="auto",
    )

    session.start()
    first_result = session.recognize(first)
    second_result = session.recognize(second)
    session.stop()

    assert starter.calls[0].argv == (
        str(EXECUTABLE),
        "--model",
        str(MODEL),
        "--mmproj",
        str(PROJECTOR),
        "--host",
        "127.0.0.1",
        "--port",
        "43127",
        "--parallel",
        "1",
        "--ctx-size",
        "8192",
        "--media-path",
        str(SEGMENT_ROOT),
        "--no-webui",
    )
    assert starter.calls[0].shell is False
    assert len(transport.health_calls) == 1
    host, port, readiness_timeout = transport.health_calls[0]
    assert (host, port) == ("127.0.0.1", 43127)
    assert 0.0 < readiness_timeout <= 60.0
    assert encoded_requests == [first, second]
    assert transport.recognition_calls == [
        ("127.0.0.1", 43127, b"encoded request", 180.0),
        ("127.0.0.1", 43127, b"encoded request", 180.0),
    ]
    assert decoded_responses == [b"provider response", b"provider response"]
    assert first_result == decoded_result
    assert second_result == decoded_result
    assert process.terminate_calls == 1
    assert process.kill_calls == 0
    assert process.wait_timeouts == [60.0]
