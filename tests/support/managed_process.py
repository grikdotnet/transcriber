"""Controlled managed-process double consumed by llama.cpp integration tests."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ManagedProcessCall:
    """One recorded managed-process start."""

    argv: tuple[str, ...]
    shell: bool


class ManagedProcessDouble:
    """A reaped process with recorded lifecycle operations."""

    def __init__(
        self,
        *,
        returncode: int | None = None,
        diagnostic: str = "",
        wait_timeout_count: int = 0,
        wait_durations: Sequence[float] = (),
        wait_clock: Callable[[float], None] | None = None,
    ) -> None:
        self.returncode = returncode
        self.diagnostic = diagnostic
        self._wait_timeout_count = wait_timeout_count
        self._wait_durations = list(wait_durations)
        self._wait_clock = wait_clock
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_timeouts: list[float] = []

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminate_calls += 1
        self.returncode = 0

    def kill(self) -> None:
        self.kill_calls += 1
        self.returncode = -9

    def wait(self, *, timeout: float) -> int:
        self.wait_timeouts.append(timeout)
        if self._wait_durations:
            duration = self._wait_durations.pop(0)
            if self._wait_clock is not None:
                self._wait_clock(duration)
        if self._wait_timeout_count:
            self._wait_timeout_count -= 1
            raise TimeoutError
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


class ManagedProcessStarterDouble:
    """Start one supplied managed-process double and capture the argv."""

    def __init__(self, *processes: ManagedProcessDouble) -> None:
        self._processes = list(processes)
        self.calls: list[ManagedProcessCall] = []

    def start(self, argv: Sequence[str], *, shell: bool = False) -> ManagedProcessDouble:
        self.calls.append(ManagedProcessCall(tuple(argv), shell))
        return self._processes.pop(0)
