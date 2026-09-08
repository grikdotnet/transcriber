from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from tests.support.asr import make_asr_task_directory, write_speech_segment
from transcriber.infrastructure.asr_files import (
    AsrTaskFilesFailure,
    check_segment_files,
    publish_transcript,
    read_manifest_file,
)
from transcriber.infrastructure.filesystem import FilePublicationFailure


class _ControlledStagedFile:
    """Wrap one temporary file to inject one publication-stage failure."""

    def __init__(self, staged: object, failure: str) -> None:
        self._staged = staged
        self._failure = failure

    @property
    def name(self) -> str:
        return self._staged.name  # type: ignore[union-attr]

    def __enter__(self) -> _ControlledStagedFile:
        self._staged.__enter__()  # type: ignore[union-attr]
        return self

    def __exit__(self, *arguments: object) -> object:
        return self._staged.__exit__(*arguments)  # type: ignore[union-attr]

    def write(self, content: bytes) -> int:
        if self._failure == "write":
            raise OSError("controlled staged-write failure")
        if self._failure == "short-write":
            return self._staged.write(content[:-1])  # type: ignore[union-attr]
        return self._staged.write(content)  # type: ignore[union-attr]

    def flush(self) -> None:
        if self._failure == "flush":
            raise OSError("controlled flush failure")
        self._staged.flush()  # type: ignore[union-attr]

    def fileno(self) -> int:
        return self._staged.fileno()  # type: ignore[union-attr]


def test_manifest_reader_returns_opaque_bytes_without_decoding(tmp_path: Path) -> None:
    payload = b"\x80not-json\x00"
    task_work_directory = make_asr_task_directory(tmp_path, payload)

    assert read_manifest_file(task_work_directory) == payload


def test_segment_file_check_returns_exact_true_only_after_validating_the_complete_batch(
    tmp_path: Path,
) -> None:
    task_work_directory = make_asr_task_directory(tmp_path, b"ignored by file boundary")
    write_speech_segment(task_work_directory, 0, 3)
    write_speech_segment(task_work_directory, 1, 5)

    checked = check_segment_files(
        task_work_directory,
        ("segments/segment-0000.wav", "segments/segment-0001.wav"),
        (3, 5),
    )

    assert checked is True


def test_segment_file_check_reports_array_length_mismatch_as_one_typed_failure(
    tmp_path: Path,
) -> None:
    task_work_directory = make_asr_task_directory(tmp_path, b"manifest")

    with pytest.raises(AsrTaskFilesFailure) as raised:
        check_segment_files(
            task_work_directory,
            ("segments/segment-0000.wav",),
            (),
        )

    assert raised.value.reason == "array-length-mismatch"
    assert raised.value.filename is None


@pytest.mark.parametrize(
    ("filename", "expected_duration_samples", "setup", "reason"),
    [
        ("segments/other.wav", 3, "valid", "filename"),
        ("segments/segment-0000.wav", 3, "missing", "missing"),
        ("segments/segment-0000.wav", 3, "replaced", "replaced"),
        ("segments/segment-0000.wav", 3, "escaping", "escaping"),
        ("segments/segment-0000.wav", 3, "format", "format"),
        ("segments/segment-0000.wav", 4, "valid", "duration"),
    ],
)
def test_segment_file_check_rejects_each_invalid_file_with_filename_and_reason(
    tmp_path: Path,
    filename: str,
    expected_duration_samples: int,
    setup: str,
    reason: str,
) -> None:
    task_work_directory = make_asr_task_directory(tmp_path, b"manifest")
    expected_filename = "segments/segment-0000.wav"
    target = task_work_directory / expected_filename

    if setup == "valid":
        write_speech_segment(task_work_directory, 0, 3)
    elif setup == "replaced":
        replacement = write_speech_segment(task_work_directory, 1, 3)
        target.symlink_to(replacement)
    elif setup == "escaping":
        outside = tmp_path / "outside.wav"
        write_speech_segment(task_work_directory, 1, 3)
        outside.write_bytes((task_work_directory / "segments" / "segment-0001.wav").read_bytes())
        target.symlink_to(outside)
    elif setup == "format":
        write_speech_segment(task_work_directory, 0, 3, sample_rate_hz=8_000)
    else:
        assert setup == "missing"

    with pytest.raises(AsrTaskFilesFailure) as raised:
        check_segment_files(task_work_directory, (filename,), (expected_duration_samples,))

    assert raised.value.filename == filename
    assert raised.value.reason == reason


def test_segment_file_check_stops_at_the_first_invalid_file(tmp_path: Path) -> None:
    task_work_directory = make_asr_task_directory(tmp_path, b"manifest")
    write_speech_segment(task_work_directory, 1, 2, sample_rate_hz=8_000)

    with pytest.raises(AsrTaskFilesFailure) as raised:
        check_segment_files(
            task_work_directory,
            ("segments/segment-0000.wav", "segments/segment-0001.wav"),
            (3, 2),
        )

    assert raised.value.filename == "segments/segment-0000.wav"
    assert raised.value.reason == "missing"


def test_segment_file_check_rejects_a_truncated_pcm_payload_as_format(tmp_path: Path) -> None:
    task_work_directory = make_asr_task_directory(tmp_path, b"manifest")
    speech_segment = write_speech_segment(task_work_directory, 0, 3)
    speech_segment.write_bytes(speech_segment.read_bytes()[:-1])

    with pytest.raises(AsrTaskFilesFailure) as raised:
        check_segment_files(task_work_directory, ("segments/segment-0000.wav",), (3,))

    assert raised.value.filename == "segments/segment-0000.wav"
    assert raised.value.reason == "format"


def test_segment_file_check_rejects_zero_frame_wav_with_mismatched_duration(
    tmp_path: Path,
) -> None:
    task_work_directory = make_asr_task_directory(tmp_path, b"manifest")
    write_speech_segment(task_work_directory, 0, 0)

    with pytest.raises(AsrTaskFilesFailure) as raised:
        check_segment_files(task_work_directory, ("segments/segment-0000.wav",), (1,))

    assert raised.value.filename == "segments/segment-0000.wav"
    assert raised.value.reason == "duration"


@pytest.mark.parametrize(
    ("loop_location", "expected_filename"),
    [
        ("task-root", None),
        ("segments", "segments/segment-0000.wav"),
        ("segment", "segments/segment-0000.wav"),
    ],
)
def test_segment_file_check_translates_symlink_loops_to_typed_escaping_failures(
    tmp_path: Path,
    loop_location: str,
    expected_filename: str | None,
) -> None:
    if loop_location == "task-root":
        task_work_directory = tmp_path / "task-loop"
        task_work_directory.symlink_to(task_work_directory)
    else:
        task_work_directory = make_asr_task_directory(tmp_path, b"manifest")
        loop = (
            task_work_directory / "segments"
            if loop_location == "segments"
            else task_work_directory / "segments" / "segment-0000.wav"
        )
        if loop_location == "segments":
            loop.rmdir()
        loop.symlink_to(loop)

    with pytest.raises(AsrTaskFilesFailure) as raised:
        check_segment_files(task_work_directory, ("segments/segment-0000.wav",), (3,))

    assert raised.value.filename == expected_filename
    assert raised.value.reason == "escaping"


def test_transcript_publication_uses_exact_model_directory_and_atomic_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_work_directory = make_asr_task_directory(tmp_path, b"manifest")
    destination = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.txt"
    destination.parent.mkdir()
    destination.write_bytes(b"previous\n")
    observed: dict[str, Path] = {}
    real_replace = os.replace

    def observe_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        staged = Path(source)
        final = Path(target)
        assert staged.parent == destination.parent
        assert staged.read_bytes() == b"complete\n"
        assert final == destination
        observed["staged"] = staged
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", observe_replace)

    published = publish_transcript(task_work_directory, "qwen3-asr-1.7b", b"complete\n")

    assert published == destination.resolve()
    assert destination.read_bytes() == b"complete\n"
    assert not observed["staged"].exists()


def test_transcript_publication_rejects_an_output_directory_symlink_that_escapes(
    tmp_path: Path,
) -> None:
    task_work_directory = make_asr_task_directory(tmp_path, b"manifest")
    outside_directory = tmp_path / "outside"
    outside_directory.mkdir()
    output_directory = task_work_directory / "transcripts-qwen3-asr-1.7b"
    output_directory.symlink_to(outside_directory, target_is_directory=True)

    with pytest.raises(AsrTaskFilesFailure) as raised:
        publish_transcript(task_work_directory, "qwen3-asr-1.7b", b"complete\n")

    assert raised.value.filename is None
    assert raised.value.reason == "escaping"
    assert tuple(outside_directory.iterdir()) == ()


@pytest.mark.parametrize("content", [b"", b"complete\n"])
def test_transcript_publication_preserves_exact_empty_and_non_empty_bytes(
    tmp_path: Path, content: bytes
) -> None:
    task_work_directory = make_asr_task_directory(tmp_path, b"manifest")

    published = publish_transcript(task_work_directory, "qwen3-asr-1.7b", content)

    assert published.read_bytes() == content


@pytest.mark.parametrize("failure", ["write", "short-write", "flush", "replace"])
def test_transcript_publication_preserves_prior_bytes_and_removes_staged_file_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    task_work_directory = make_asr_task_directory(tmp_path, b"manifest")
    output_directory = task_work_directory / "transcripts-qwen3-asr-1.7b"
    output_directory.mkdir()
    destination = output_directory / "transcript.txt"
    destination.write_bytes(b"previous\n")
    real_named_temporary_file = tempfile.NamedTemporaryFile

    if failure in {"write", "short-write", "flush"}:

        def controlled_named_temporary_file(**kwargs: object) -> _ControlledStagedFile:
            return _ControlledStagedFile(real_named_temporary_file(**kwargs), failure)

        monkeypatch.setattr(
            "transcriber.infrastructure.filesystem.tempfile.NamedTemporaryFile",
            controlled_named_temporary_file,
        )
    else:

        def reject_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
            raise OSError("controlled replace failure")

        monkeypatch.setattr(os, "replace", reject_replace)

    with pytest.raises(FilePublicationFailure):
        publish_transcript(task_work_directory, "qwen3-asr-1.7b", b"complete\n")

    assert destination.read_bytes() == b"previous\n"
    assert tuple(output_directory.iterdir()) == (destination,)


def test_segment_file_preflight_does_not_mutate_existing_transcript_or_create_a_lock(
    tmp_path: Path,
) -> None:
    task_work_directory = make_asr_task_directory(tmp_path, b"manifest")
    write_speech_segment(task_work_directory, 0, 3)
    output_directory = task_work_directory / "transcripts-qwen3-asr-1.7b"
    output_directory.mkdir()
    destination = output_directory / "transcript.txt"
    destination.write_bytes(b"previous\n")

    assert check_segment_files(task_work_directory, ("segments/segment-0000.wav",), (3,)) is True

    assert destination.read_bytes() == b"previous\n"
    assert not tuple(task_work_directory.rglob("*.lock"))
