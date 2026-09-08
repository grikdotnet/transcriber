"""Infrastructure-only subprocess execution boundary."""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True, slots=True)
class CompletedProcessData:
    """Process result without leaking ``subprocess`` objects across the adapter."""

    argv: tuple[str, ...]
    returncode: int
    stdout: bytes
    stderr: bytes


class ProcessRunner(Protocol):
    """Narrow process interface used by executable adapters and test doubles."""

    def run(self, argv: Sequence[str], *, shell: bool = False) -> CompletedProcessData:
        """Run an argv vector and capture its completion data."""


class ManagedProcess(Protocol):
    """Minimum lifecycle operations for one locally managed child process."""

    def poll(self) -> int | None:
        """Return the exit status when the child has exited."""

    def terminate(self) -> None:
        """Request graceful child termination."""

    def kill(self) -> None:
        """Force child termination."""

    def wait(self, *, timeout: float) -> int:
        """Reap the child within the supplied timeout."""

    @property
    def diagnostic(self) -> str:
        """Return captured private child diagnostics, never a public log stream."""


class ManagedProcessStarter(Protocol):
    """Start one managed child without shell parsing."""

    def start(self, argv: Sequence[str], *, shell: bool = False) -> ManagedProcess:
        """Start the argv vector and return its lifecycle boundary."""


class SubprocessRunner:
    """Execute a process without implicit shell parsing."""

    def run(self, argv: Sequence[str], *, shell: bool = False) -> CompletedProcessData:
        command = tuple(argv)
        completed = subprocess.run(
            command,
            shell=shell,
            check=False,
            capture_output=True,
        )
        return CompletedProcessData(
            argv=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class SubprocessManagedProcessStarter:
    """Start a child process owned by an Infrastructure adapter."""

    def start(self, argv: Sequence[str], *, shell: bool = False) -> ManagedProcess:
        child = subprocess.Popen(
            tuple(argv),
            shell=shell,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return _SubprocessManagedProcess(child)


class _SubprocessManagedProcess:
    """Drain bounded private child output while exposing only lifecycle operations."""

    _diagnostic_limit = 8_192

    def __init__(self, child: subprocess.Popen[bytes]) -> None:
        self._child = child
        self._diagnostic_tail = bytearray()
        self._lock = threading.Lock()
        for stream in (child.stdout, child.stderr):
            if stream is not None:
                threading.Thread(target=self._drain, args=(stream,), daemon=True).start()

    def _drain(self, stream: BinaryIO) -> None:
        while block := stream.read(4_096):
            with self._lock:
                self._diagnostic_tail.extend(block)
                del self._diagnostic_tail[: -self._diagnostic_limit]

    @property
    def diagnostic(self) -> str:
        with self._lock:
            return bytes(self._diagnostic_tail).decode("utf-8", errors="replace")

    def poll(self) -> int | None:
        return self._child.poll()

    def terminate(self) -> None:
        self._child.terminate()

    def kill(self) -> None:
        self._child.kill()

    def wait(self, *, timeout: float) -> int:
        try:
            return self._child.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise TimeoutError from error
