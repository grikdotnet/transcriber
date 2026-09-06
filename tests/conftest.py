from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("real-vad")
    group.addoption(
        "--real-vad-required",
        action="store_true",
        default=False,
        help="fail instead of skipping when local FireRedVAD prerequisites are unavailable",
    )


@pytest.fixture(scope="session")
def real_vad_paths(request: pytest.FixtureRequest) -> RealVadPaths:
    paths = RealVadPaths.from_repository(Path(__file__).resolve().parents[1])
    enforce_real_vad_prerequisites(
        paths,
        required=bool(request.config.getoption("--real-vad-required")),
    )
    return paths
