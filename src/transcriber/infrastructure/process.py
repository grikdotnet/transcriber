"""Infrastructure-only subprocess execution boundary."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


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
