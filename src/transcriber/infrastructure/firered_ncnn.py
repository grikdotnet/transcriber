"""Process boundary for the local FireRedVAD NCNN runner."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol, TypeVar

from transcriber.infrastructure.process import CompletedProcessData

DocumentT = TypeVar("DocumentT")


class ProcessExecutor(Protocol):
    def run(self, argv: Sequence[str], *, shell: bool = False) -> CompletedProcessData: ...


class FireRedNcnnFailure(RuntimeError):
    """Closed failure reported at the native-provider integration boundary."""

    def __init__(self, *, path: Path, operation: str, status: int | None = None) -> None:
        self.stage = "speech-detection"
        self.path = path
        self.operation = operation
        self.status = status
        super().__init__(f"{operation} failed at {self.stage}: {path}")


class FireRedNcnnProcess[DocumentT]:
    """Invoke exactly one configured native executable and decode its public document."""

    __slots__ = ("_executable", "_model_dir", "_runner", "_decoder", "_chunk_max_frames")

    def __init__(
        self,
        executable: Path,
        model_dir: Path,
        runner: ProcessExecutor,
        decoder: Callable[[str | bytes], DocumentT],
        *,
        chunk_max_frames: int = 30_000,
    ) -> None:
        executable = Path(executable)
        model_dir = Path(model_dir)
        if not executable.is_absolute() or not model_dir.is_absolute():
            raise ValueError("native executable and model directory paths must be absolute")
        if isinstance(chunk_max_frames, bool) or chunk_max_frames <= 0:
            raise ValueError("chunk_max_frames must be a positive integer")
        self._executable = executable
        self._model_dir = model_dir
        self._runner = runner
        self._decoder = decoder
        self._chunk_max_frames = chunk_max_frames

    @property
    def executable(self) -> Path:
        return self._executable

    @property
    def model_dir(self) -> Path:
        return self._model_dir

    def run(self, audio: Path) -> DocumentT:
        audio = Path(audio)
        if not audio.is_absolute():
            raise ValueError("audio path must be absolute")
        argv = (
            str(self._executable),
            "--audio",
            str(audio),
            "--model-param",
            str(self._model_dir / "firered_vad_non_stream.ncnn.param"),
            "--model-bin",
            str(self._model_dir / "firered_vad_non_stream.ncnn.bin"),
            "--cmvn-means",
            str(self._model_dir / "cmvn_means.bin"),
            "--cmvn-istd",
            str(self._model_dir / "cmvn_istd.bin"),
            "--chunk-max-frames",
            str(self._chunk_max_frames),
        )
        try:
            completed = self._runner.run(argv, shell=False)
        except OSError as error:
            raise FireRedNcnnFailure(path=self._executable, operation="start-provider") from error
        if completed.returncode != 0:
            raise FireRedNcnnFailure(
                path=self._executable,
                operation="native-provider",
                status=completed.returncode,
            )
        try:
            return self._decoder(completed.stdout)
        except (TypeError, ValueError) as error:
            raise FireRedNcnnFailure(
                path=self._executable,
                operation="decode-probabilities",
                status=completed.returncode,
            ) from error
