from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from tests.support.call_log import CallLog


@dataclass(frozen=True)
class FakeCompletedProcess:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class ProcessCall:
    argv: tuple[str, ...]
    shell: bool


class FakeProcessRunner:
    """FIFO process fake that captures exact argv and shell usage."""

    def __init__(
        self,
        results: Iterable[FakeCompletedProcess] = (),
        *,
        call_log: CallLog | None = None,
        event: str = "process.run",
    ) -> None:
        self._results = deque(results)
        self._call_log = call_log
        self._event = event
        self.calls: list[ProcessCall] = []

    def run(self, argv: Sequence[str], *, shell: bool = False) -> FakeCompletedProcess:
        self.calls.append(ProcessCall(tuple(argv), shell))
        if self._call_log is not None:
            self._call_log.record(self._event)
        if not self._results:
            raise AssertionError("FakeProcessRunner has no queued result")
        return self._results.popleft()
