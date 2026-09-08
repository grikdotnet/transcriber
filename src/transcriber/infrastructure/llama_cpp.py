"""Managed loopback llama.cpp Execution Provider adapter."""

from __future__ import annotations

import http.client
import socket
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from transcriber.infrastructure.execution_provider import (
    ExecutionProviderFailure,
    ExecutionProviderSession,
    RecognitionRequest,
    RecognitionResult,
)
from transcriber.infrastructure.process import ManagedProcess, ManagedProcessStarter

_LOOPBACK_HOST = "127.0.0.1"


class QwenRequestEncoder(Protocol):
    """Encode one provider-specific recognition document."""

    def __call__(self, *, audio_path: Path, recognition_context: str, language: str) -> bytes:
        """Return one request document."""


class QwenResponseDecoder(Protocol):
    """Decode one provider-specific recognition document."""

    def __call__(self, payload: bytes) -> str:
        """Return recognized text."""


class LoopbackTransport(Protocol):
    """Transport boundary restricted by the adapter to its loopback endpoint."""

    def health(self, *, host: str, port: int, timeout_seconds: float) -> bool:
        """Return whether the provider is ready."""

    def recognize(self, *, host: str, port: int, payload: bytes, timeout_seconds: float) -> bytes:
        """Send one non-streaming recognition request."""


class HttpLoopbackTransport:
    """Use the llama.cpp loopback HTTP endpoints."""

    def __init__(self, *, extract_error_message: Callable[[bytes], str | None]) -> None:
        self._extract_error_message = extract_error_message

    def health(self, *, host: str, port: int, timeout_seconds: float) -> bool:
        connection = http.client.HTTPConnection(host, port, timeout=timeout_seconds)
        try:
            connection.request("GET", "/health")
            response = connection.getresponse()
            response.read()
            return 200 <= response.status < 300
        except OSError:
            return False
        finally:
            connection.close()

    def recognize(self, *, host: str, port: int, payload: bytes, timeout_seconds: float) -> bytes:
        connection = http.client.HTTPConnection(host, port, timeout=timeout_seconds)
        try:
            connection.request(
                "POST",
                "/v1/chat/completions",
                body=payload,
                headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
            )
            response = connection.getresponse()
            body = response.read()
        except OSError as error:
            raise ExecutionProviderFailure(message="recognition request failed") from error
        finally:
            connection.close()
        if not 200 <= response.status < 300:
            diagnostic = self._extract_error_message(body) or body.decode("utf-8", errors="replace")
            raise ExecutionProviderFailure(
                message="recognition request failed", diagnostic=diagnostic[-8_192:] or None
            )
        return body


def _allocate_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((_LOOPBACK_HOST, 0))
        return int(listener.getsockname()[1])


class LlamaCppExecutionProvider:
    """Create fresh managed llama.cpp sessions with injected Qwen codecs."""

    def __init__(
        self,
        *,
        executable: Path,
        model_path: Path,
        audio_projector_path: Path,
        process_starter: ManagedProcessStarter,
        transport: LoopbackTransport,
        encode_request: QwenRequestEncoder,
        decode_response: QwenResponseDecoder,
        endpoint_port: Callable[[], int] = _allocate_loopback_port,
        monotonic_clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        paths: Sequence[Path] = (executable, model_path, audio_projector_path)
        if any(not path.is_absolute() for path in paths):
            raise ValueError("llama.cpp executable and artifact paths must be absolute")
        self._executable = executable
        self._model_path = model_path
        self._audio_projector_path = audio_projector_path
        self._process_starter = process_starter
        self._transport = transport
        self._encode_request = encode_request
        self._decode_response = decode_response
        self._endpoint_port = endpoint_port
        self._monotonic_clock = monotonic_clock
        self._sleeper = sleeper

    def create(self, *, segment_root: Path) -> ExecutionProviderSession:
        if not segment_root.is_absolute():
            raise ValueError("segment root must be absolute")
        return _LlamaCppSession(
            executable=self._executable,
            model_path=self._model_path,
            audio_projector_path=self._audio_projector_path,
            segment_root=segment_root,
            process_starter=self._process_starter,
            transport=self._transport,
            encode_request=self._encode_request,
            decode_response=self._decode_response,
            endpoint_port=self._endpoint_port,
            monotonic_clock=self._monotonic_clock,
            sleeper=self._sleeper,
        )


class _LlamaCppSession(ExecutionProviderSession):
    """Own one llama.cpp process and its fixed loopback endpoint."""

    def __init__(
        self,
        *,
        executable: Path,
        model_path: Path,
        audio_projector_path: Path,
        segment_root: Path,
        process_starter: ManagedProcessStarter,
        transport: LoopbackTransport,
        encode_request: QwenRequestEncoder,
        decode_response: QwenResponseDecoder,
        endpoint_port: Callable[[], int],
        monotonic_clock: Callable[[], float],
        sleeper: Callable[[float], None],
    ) -> None:
        super().__init__()
        self._executable = executable
        self._model_path = model_path
        self._audio_projector_path = audio_projector_path
        self._segment_root = segment_root
        self._process_starter = process_starter
        self._transport = transport
        self._encode_request = encode_request
        self._decode_response = decode_response
        self._endpoint_port = endpoint_port
        self._monotonic_clock = monotonic_clock
        self._sleeper = sleeper
        self._port: int | None = None
        self._process: ManagedProcess | None = None

    def _start(self, *, readiness_timeout_seconds: float) -> None:
        deadline = self._monotonic_clock() + readiness_timeout_seconds
        while True:
            port = self._endpoint_port()
            if self._start_at_port(port, deadline):
                return

    def _start_at_port(self, port: int, deadline: float) -> bool:
        argv = (
            str(self._executable),
            "--model",
            str(self._model_path),
            "--mmproj",
            str(self._audio_projector_path),
            "--host",
            _LOOPBACK_HOST,
            "--port",
            str(port),
            "--parallel",
            "1",
            "--ctx-size",
            "8192",
            "--media-path",
            str(self._segment_root),
            "--no-webui",
        )
        try:
            self._process = self._process_starter.start(argv, shell=False)
        except OSError as error:
            raise ExecutionProviderFailure(message="provider startup failed") from error
        self._port = port
        while True:
            if self._process.poll() is not None:
                diagnostic = self._diagnostic()
                collision_detected = "address already in use" in (diagnostic or "").lower()
                if collision_detected and self._monotonic_clock() < deadline:
                    self._stop(graceful_timeout_seconds=60.0, force_timeout_seconds=10.0)
                    self._process = None
                    self._port = None
                    return False
                raise ExecutionProviderFailure(
                    message="provider startup failed", diagnostic=diagnostic
                )
            remaining = deadline - self._monotonic_clock()
            if remaining <= 0:
                raise ExecutionProviderFailure(message="provider startup timed out")
            if self._transport.health(
                host=_LOOPBACK_HOST, port=port, timeout_seconds=remaining
            ):
                if self._monotonic_clock() >= deadline:
                    raise ExecutionProviderFailure(message="provider startup timed out")
                return True
            remaining = deadline - self._monotonic_clock()
            if remaining <= 0:
                raise ExecutionProviderFailure(message="provider startup timed out")
            self._sleeper(min(0.01, remaining))

    def _recognize(
        self, request: RecognitionRequest, *, timeout_seconds: float
    ) -> RecognitionResult:
        try:
            request.audio_path.relative_to(self._segment_root)
        except ValueError as error:
            raise ExecutionProviderFailure(
                message="speech segment is outside the media path"
            ) from error
        if self._port is None:
            raise ExecutionProviderFailure(message="provider is not ready")
        if self._process is not None and self._process.poll() is not None:
            raise ExecutionProviderFailure(
                message="provider recognition failed", diagnostic=self._diagnostic()
            )
        try:
            payload = self._encode_request(
                audio_path=request.audio_path,
                recognition_context=request.recognition_context,
                language=request.language,
            )
        except ValueError as error:
            raise ExecutionProviderFailure(message=str(error)) from error
        deadline = self._monotonic_clock() + timeout_seconds
        try:
            response = self._transport.recognize(
                host=_LOOPBACK_HOST,
                port=self._port,
                payload=payload,
                timeout_seconds=timeout_seconds,
            )
        except ExecutionProviderFailure:
            raise
        except OSError as error:
            raise ExecutionProviderFailure(message="recognition request failed") from error
        if self._monotonic_clock() >= deadline:
            raise ExecutionProviderFailure(message="recognition request timed out")
        try:
            return RecognitionResult(text=self._decode_response(response))
        except (TypeError, ValueError) as error:
            raise ExecutionProviderFailure(message="provider response failed") from error

    def _diagnostic(self) -> str | None:
        if self._process is None:
            return None
        diagnostic = getattr(self._process, "diagnostic", "")
        normalized = "".join(
            " " if not character.isprintable() else character for character in str(diagnostic)
        )
        normalized = " ".join(normalized.split())
        return normalized[-8_192:] or None

    def _stop(self, *, graceful_timeout_seconds: float, force_timeout_seconds: float) -> None:
        if self._process is None:
            return
        if self._process.poll() is not None:
            self._process.wait(timeout=graceful_timeout_seconds)
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=graceful_timeout_seconds)
        except TimeoutError:
            self._process.kill()
            self._process.wait(timeout=force_timeout_seconds)
