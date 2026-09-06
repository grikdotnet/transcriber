"""Repository-bundled FFmpeg invocation boundary."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from transcriber.infrastructure.process import CompletedProcessData


class ProcessExecutor(Protocol):
    """Process dependency accepted by FFmpeg, including controlled test doubles."""

    def run(self, argv: Sequence[str], *, shell: bool = False) -> CompletedProcessData:
        """Execute one argument vector."""


class FfmpegFailure(RuntimeError):
    """Closed, actionable FFmpeg boundary failure."""

    def __init__(self, *, stage: str, path: Path, operation: str) -> None:
        self.stage = stage
        self.path = path
        self.operation = operation
        super().__init__(f"{operation} failed at {stage}: {path}")


class FfmpegProcess:
    """Validate and extract through one explicitly configured FFmpeg executable."""

    __slots__ = ("_executable", "_runner")

    def __init__(self, executable: Path, runner: ProcessExecutor) -> None:
        executable = Path(executable)
        if not executable.is_absolute():
            raise ValueError("FFmpeg executable path must be absolute")
        self._executable = executable
        self._runner = runner

    @property
    def executable(self) -> Path:
        return self._executable

    @property
    def runner(self) -> ProcessExecutor:
        return self._runner

    def validate(self, source: Path) -> None:
        source = Path(source)
        self._require_readable_source(source)
        self._execute(
            (
                str(self._executable),
                "-nostdin",
                "-v",
                "error",
                "-i",
                str(source),
                "-map",
                "0:a:0",
                "-f",
                "null",
                "-",
            ),
            stage="source-media",
            failure_path=source,
            operation="decode",
        )

    def extract(self, source: Path, destination: Path) -> None:
        source = Path(source)
        destination = Path(destination)
        self._execute(
            (
                str(self._executable),
                "-nostdin",
                "-v",
                "error",
                "-i",
                str(source),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(destination),
            ),
            stage="audio-extraction",
            failure_path=destination,
            operation="extract",
        )

    def _require_readable_source(self, source: Path) -> None:
        if not source.exists() or not source.is_file():
            raise FfmpegFailure(stage="source-media", path=source, operation="missing")
        if not os.access(source, os.R_OK):
            raise FfmpegFailure(stage="source-media", path=source, operation="unreadable")

    def _execute(
        self,
        argv: tuple[str, ...],
        *,
        stage: str,
        failure_path: Path,
        operation: str,
    ) -> None:
        try:
            result = self._runner.run(argv, shell=False)
        except OSError as error:
            raise FfmpegFailure(
                stage=stage,
                path=self._executable,
                operation="start-decoder",
            ) from error
        if result.returncode != 0:
            raise FfmpegFailure(stage=stage, path=failure_path, operation=operation)
