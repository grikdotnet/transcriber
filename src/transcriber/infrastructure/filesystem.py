"""Exclusive workspace creation and atomic file publication adapters."""

from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Protocol


class EventLog(Protocol):
    """Optional ordered event sink used by controlled boundary tests."""

    def record(self, event: str) -> None:
        """Record one adapter event."""


class WorkDirectoryFailure(RuntimeError):
    def __init__(self, *, path: Path, operation: str = "create-exclusive") -> None:
        self.stage = "task-directory"
        self.path = path
        self.operation = operation
        super().__init__(f"{operation} failed at {self.stage}: {path}")


class FilePublicationFailure(RuntimeError):
    def __init__(self, *, path: Path, operation: str = "atomic-publish") -> None:
        self.stage = "manifest-creation"
        self.path = path
        self.operation = operation
        super().__init__(f"{operation} failed at {self.stage}: {path}")


class WorkDirectory:
    """Create the exact caller-selected task directory once."""

    def __init__(self, *, call_log: EventLog | None = None) -> None:
        self._call_log = call_log

    def create(self, path: Path) -> Path:
        requested = Path(path)
        if self._call_log is not None:
            self._call_log.record("work-directory.create")
        try:
            requested.mkdir(parents=False, exist_ok=False)
            (requested / "segments").mkdir()
        except OSError as error:
            raise WorkDirectoryFailure(path=requested) from error
        return requested


class AtomicFileWriter:
    """Durably stage bytes beside their destination and publish with ``replace``."""

    def write(self, path: Path, content: bytes) -> None:
        destination = Path(path)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as staged:
                temporary = Path(staged.name)
                staged.write(content)
                staged.flush()
                os.fsync(staged.fileno())
            os.replace(temporary, destination)
        except OSError as error:
            if temporary is not None:
                with suppress(OSError):
                    temporary.unlink(missing_ok=True)
            raise FilePublicationFailure(path=destination) from error
