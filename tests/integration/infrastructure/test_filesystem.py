from __future__ import annotations

import os
from pathlib import Path

import pytest

from transcriber.infrastructure.filesystem import (
    AtomicFileWriter,
    FilePublicationFailure,
    WorkDirectory,
    WorkDirectoryFailure,
)


def test_work_directory_creates_the_exact_path_and_segments_child(tmp_path: Path) -> None:
    requested = tmp_path / "caller-selected-task"

    created = WorkDirectory().create(requested)

    assert created == requested
    assert requested.is_dir()
    assert (requested / "segments").is_dir()


def test_work_directory_refuses_an_existing_path(tmp_path: Path) -> None:
    requested = tmp_path / "existing"
    requested.mkdir()

    with pytest.raises(WorkDirectoryFailure) as raised:
        WorkDirectory().create(requested)

    assert raised.value.stage == "task-directory"
    assert raised.value.path == requested
    assert raised.value.operation == "create-exclusive"


def test_work_directory_failure_does_not_choose_an_alternate_path(tmp_path: Path) -> None:
    requested = tmp_path / "missing-parent" / "task"

    with pytest.raises(WorkDirectoryFailure):
        WorkDirectory().create(requested)

    assert not requested.exists()
    assert not (tmp_path / "task-1").exists()


def test_atomic_writer_replaces_only_after_complete_same_directory_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "manifest.json"
    observed: dict[str, Path] = {}
    real_replace = os.replace

    def observe_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        temporary = Path(source)
        final = Path(target)
        assert temporary.parent == destination.parent
        assert temporary.read_bytes() == b'{"complete":true}\n'
        assert not destination.exists()
        observed.update(temporary=temporary, final=final)
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", observe_replace)

    AtomicFileWriter().write(destination, b'{"complete":true}\n')

    assert observed["final"] == destination
    assert destination.read_bytes() == b'{"complete":true}\n'
    assert not observed["temporary"].exists()


def test_atomic_writer_preserves_existing_file_and_cleans_temporary_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "manifest.json"
    destination.write_bytes(b"old\n")

    def reject_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        raise OSError("controlled publication failure")

    monkeypatch.setattr(os, "replace", reject_replace)

    with pytest.raises(FilePublicationFailure) as raised:
        AtomicFileWriter().write(destination, b"new\n")

    assert raised.value.stage == "manifest-creation"
    assert raised.value.path == destination
    assert raised.value.operation == "atomic-publish"
    assert destination.read_bytes() == b"old\n"
    assert tuple(tmp_path.iterdir()) == (destination,)
