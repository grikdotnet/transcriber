from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray

import pytest


@dataclass(frozen=True, slots=True)
class RealVadPaths:
    repository_root: Path
    runner: Path
    model_directory: Path
    sample: Path

    @classmethod
    def from_repository(cls, repository_root: Path) -> RealVadPaths:
        root = repository_root.resolve()
        return cls(
            repository_root=root,
            runner=root / "vendor" / "firered-vad-ncnn",
            model_directory=root / "models" / "firered-vad.ncnn",
            sample=root / "fixtures" / "sample" / "prepared.wav",
        )

    def missing_prerequisites(self) -> tuple[Path, ...]:
        required_files = (
            self.runner,
            self.sample,
            self.model_directory / "firered_vad_non_stream.ncnn.param",
            self.model_directory / "firered_vad_non_stream.ncnn.bin",
            self.model_directory / "cmvn_means.bin",
            self.model_directory / "cmvn_istd.bin",
        )
        return tuple(path for path in required_files if not path.is_file())


def enforce_real_vad_prerequisites(paths: RealVadPaths, *, required: bool) -> None:
    missing = paths.missing_prerequisites()
    if not missing:
        return
    detail = ", ".join(str(path) for path in missing)
    if required:
        pytest.fail(f"required real VAD prerequisite is unavailable: {detail}", pytrace=False)
    pytest.skip(f"real VAD prerequisite is unavailable: {detail}")


@dataclass(frozen=True, slots=True)
class RealAsrPaths:
    """Fixed local paths required by the real Qwen ASR checkpoint."""

    repository_root: Path
    provider: Path
    model: Path
    audio_projector: Path
    sample: Path

    @classmethod
    def from_repository(cls, repository_root: Path) -> RealAsrPaths:
        root = repository_root.resolve()
        model_directory = root / "models" / "qwen3-asr-1.7b"
        return cls(
            repository_root=root,
            provider=root / "vendor" / "llama-server",
            model=model_directory / "Qwen3-ASR-1.7B-Q8_0.gguf",
            audio_projector=model_directory / "mmproj-Qwen3-ASR-1.7B-Q8_0.gguf",
            sample=root / "fixtures" / "sample" / "prepared.wav",
        )

    def required_files(self) -> tuple[Path, ...]:
        """Return fixed provider, artifact, and supplied sample paths in check order."""
        return (self.provider, self.model, self.audio_projector, self.sample)

    def missing_prerequisites(self) -> tuple[Path, ...]:
        missing: list[Path] = []
        for path in self.required_files():
            try:
                available = path.is_file()
            except OSError:
                available = False
            if not available:
                missing.append(path)
        return tuple(missing)


def enforce_real_asr_prerequisites(paths: RealAsrPaths, *, required: bool) -> None:
    """Apply optional-skip or required-failure policy without resolving another path."""
    missing = paths.missing_prerequisites()
    if not missing:
        return
    prefix = (
        "required real ASR prerequisite is unavailable: "
        if required
        else ("real ASR prerequisite is unavailable: ")
    )
    detail = _bounded_missing_prerequisite_detail(missing, 1_023 - len(prefix))
    if required:
        pytest.fail(prefix + detail, pytrace=False)
    pytest.skip(prefix + detail)


def _bounded_missing_prerequisite_detail(paths: tuple[Path, ...], maximum_length: int) -> str:
    """Render missing fixed paths without allowing an unbounded pytest diagnostic."""
    rendered = ", ".join(str(path) for path in paths)
    if len(rendered) <= maximum_length:
        return rendered
    marker = "...[truncated]"
    return rendered[: maximum_length - len(marker)] + marker


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.getgroup("real-diarization").addoption(
        "--real-diarization-required",
        action="store_true",
        default=False,
        help="fail when actual two-engine diarization cannot run",
    )
    group = parser.getgroup("real-vad")
    group.addoption(
        "--real-vad-required",
        action="store_true",
        default=False,
        help="fail instead of skipping when local FireRedVAD prerequisites are unavailable",
    )
    asr_group = parser.getgroup("real-asr")
    asr_group.addoption(
        "--real-asr-required",
        action="store_true",
        default=False,
        help="fail instead of skipping when local Qwen ASR prerequisites are unavailable",
    )


@pytest.fixture(scope="session")
def real_vad_paths(request: pytest.FixtureRequest) -> RealVadPaths:
    paths = RealVadPaths.from_repository(Path(__file__).resolve().parents[1])
    enforce_real_vad_prerequisites(
        paths,
        required=bool(request.config.getoption("--real-vad-required")),
    )
    return paths


@pytest.fixture(scope="session")
def real_asr_paths(request: pytest.FixtureRequest) -> RealAsrPaths:
    paths = RealAsrPaths.from_repository(Path(__file__).resolve().parents[1])
    enforce_real_asr_prerequisites(
        paths,
        required=bool(request.config.getoption("--real-asr-required")),
    )
    return paths


def enforce_real_diarization_available(detail: str | None, *, required: bool) -> None:
    """Missing capabilities skip optional runs and fail the required checkpoint."""
    if detail is None:
        return
    message = f"real Diarization prerequisite/runtime is unavailable: {detail}"[:1023]
    if required:
        pytest.fail("required " + message, pytrace=False)
    pytest.skip(message)


@pytest.fixture(scope="session")
def real_diarization_audio(request: pytest.FixtureRequest) -> NDArray[np.float32]:
    """Read a representative ten seconds of the supplied canonical speech audio."""
    import wave

    import numpy as np

    sample = Path(__file__).resolve().parents[1] / "fixtures/sample/prepared.wav"
    required = bool(request.config.getoption("--real-diarization-required"))
    enforce_real_diarization_available(
        None if sample.is_file() else f"missing supplied audio: {sample}",
        required=required,
    )
    with wave.open(str(sample), "rb") as source:
        assert (source.getnchannels(), source.getsampwidth(), source.getframerate()) == (
            1,
            2,
            16000,
        )
        pcm = source.readframes(10 * 16000)
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / np.float32(32768)
    assert samples.size and samples.flags.owndata and samples.flags.c_contiguous
    return samples
