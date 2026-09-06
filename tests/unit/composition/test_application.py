from __future__ import annotations

from pathlib import Path

import pytest

from transcriber.composition.application import (
    MediaDependencies,
    RepositoryPaths,
    build_media_dependencies,
    resolve_repository_paths,
)
from transcriber.infrastructure.ffmpeg import FfmpegProcess
from transcriber.infrastructure.filesystem import AtomicFileWriter, WorkDirectory
from transcriber.infrastructure.process import SubprocessRunner

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_repository_paths_are_independent_of_current_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    paths = resolve_repository_paths()

    assert paths == RepositoryPaths(
        repository_root=REPOSITORY_ROOT,
        ffmpeg=REPOSITORY_ROOT / "vendor" / "ffmpeg",
        firered_model_directory=REPOSITORY_ROOT / "models" / "firered-vad.ncnn",
        firered_provider=REPOSITORY_ROOT / "vendor" / "firered-vad-ncnn",
    )
    assert all(
        path.is_absolute()
        for path in (
            paths.repository_root,
            paths.ffmpeg,
            paths.firered_model_directory,
            paths.firered_provider,
        )
    )


def test_build_media_dependencies_uses_resolved_bundled_ffmpeg(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    dependencies = build_media_dependencies()

    assert isinstance(dependencies, MediaDependencies)
    assert isinstance(dependencies.process_runner, SubprocessRunner)
    assert isinstance(dependencies.ffmpeg, FfmpegProcess)
    assert dependencies.ffmpeg.executable == REPOSITORY_ROOT / "vendor" / "ffmpeg"
    assert isinstance(dependencies.work_directory, WorkDirectory)
    assert isinstance(dependencies.atomic_file_writer, AtomicFileWriter)
