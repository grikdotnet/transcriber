"""Canonical Audio validation and publication boundary behavior."""

from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from tests.support.diarization import make_diarization_manifest, make_diarization_task_directory
from transcriber.infrastructure import diarization_files as files
from transcriber.infrastructure.filesystem import FilePublicationFailure
from transcriber.infrastructure.wave_files import WaveMetadata


def test_decodes_exact_pcm_once_into_owning_array(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_diarization_task_directory(
        tmp_path, make_diarization_manifest(4, ()), [-32768, -1, 0, 32767]
    )
    reader = Mock()
    reader.metadata = WaveMetadata(4, 16000, 1, 2, "NONE")
    reader.read_frames.return_value = np.array([-32768, -1, 0, 32767], dtype="<i2").tobytes()
    factory = Mock(return_value=reader)
    monkeypatch.setattr(files, "WaveFileReader", factory)
    decoded = files.decode_canonical_audio(root, 4)
    np.testing.assert_array_equal(decoded.samples, [-1.0, -1 / 32768, 0, 32767 / 32768])
    assert decoded.total_samples == 4
    assert decoded.samples.dtype == np.float32
    assert decoded.samples.ndim == 1
    assert decoded.samples.flags.c_contiguous and decoded.samples.flags.owndata
    factory.assert_called_once_with(root / "prepared.wav")
    reader.read_frames.assert_called_once_with(start_sample=0, end_sample=4)


def test_zero_samples_never_requests_empty_slice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_diarization_task_directory(tmp_path, make_diarization_manifest(0, ()), [])
    reader = Mock(metadata=WaveMetadata(0, 16000, 1, 2, "NONE"))
    monkeypatch.setattr(files, "WaveFileReader", Mock(return_value=reader))
    decoded = files.decode_canonical_audio(root, 0)
    assert decoded.samples.size == 0 and decoded.samples.flags.owndata
    reader.read_frames.assert_not_called()


@pytest.mark.parametrize(
    "metadata",
    [
        WaveMetadata(2, 8000, 1, 2, "NONE"),
        WaveMetadata(2, 16000, 2, 2, "NONE"),
        WaveMetadata(2, 16000, 1, 1, "NONE"),
        WaveMetadata(2, 16000, 1, 2, "ULAW"),
        WaveMetadata(3, 16000, 1, 2, "NONE"),
    ],
)
def test_rejects_noncanonical_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, metadata: WaveMetadata
) -> None:
    root = make_diarization_task_directory(tmp_path, make_diarization_manifest(2, ()), [0, 0])
    reader = Mock(metadata=metadata)
    monkeypatch.setattr(files, "WaveFileReader", Mock(return_value=reader))
    with pytest.raises(files.DiarizationFilesFailure) as caught:
        files.decode_canonical_audio(root, 2)
    assert caught.value.stage == "validate"
    reader.read_frames.assert_not_called()


@pytest.mark.parametrize("pcm", [b"\0\0", b"\0\0\0", b"\0" * 6])
def test_rejects_incomplete_or_excess_pcm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pcm: bytes
) -> None:
    root = make_diarization_task_directory(tmp_path, make_diarization_manifest(2, ()), [0, 0])
    reader = Mock(metadata=WaveMetadata(2, 16000, 1, 2, "NONE"))
    reader.read_frames.return_value = pcm
    monkeypatch.setattr(files, "WaveFileReader", Mock(return_value=reader))
    with pytest.raises(files.DiarizationFilesFailure):
        files.decode_canonical_audio(root, 2)


@pytest.mark.parametrize(
    "replacement", ["missing", "directory", "internal-symlink", "external-symlink", "loop"]
)
def test_requires_regular_nonsymlink_canonical_path(tmp_path: Path, replacement: str) -> None:
    root = make_diarization_task_directory(tmp_path, make_diarization_manifest(1, ()), [0])
    canonical = root / "prepared.wav"
    canonical.unlink()
    if replacement == "directory":
        canonical.mkdir()
    elif replacement == "internal-symlink":
        canonical.symlink_to(root / "manifest.json")
    elif replacement == "external-symlink":
        canonical.symlink_to(tmp_path / "outside.wav")
    elif replacement == "loop":
        canonical.symlink_to(canonical)
    with pytest.raises(files.DiarizationFilesFailure) as caught:
        files.decode_canonical_audio(root, 1)
    assert caught.value.stage == "validate"


def test_rejects_malformed_wav(tmp_path: Path) -> None:
    (tmp_path / "prepared.wav").write_bytes(b"invalid")
    with pytest.raises(files.DiarizationFilesFailure):
        files.decode_canonical_audio(tmp_path, 1)


def test_publication_delegates_complete_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = Mock()
    monkeypatch.setattr(files, "AtomicFileWriter", Mock(return_value=writer))
    content = b'{"intervals":[]}\n'
    assert files.publish_diarization(tmp_path, content) == tmp_path / "diarization.json"
    writer.write.assert_called_once_with(tmp_path / "diarization.json", content)


def test_publication_translates_shared_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "diarization.json"
    writer = Mock()
    failure = FilePublicationFailure(path=destination)
    writer.write.side_effect = failure
    monkeypatch.setattr(files, "AtomicFileWriter", Mock(return_value=writer))
    with pytest.raises(files.DiarizationFilesFailure) as caught:
        files.publish_diarization(tmp_path, b"complete")
    assert caught.value.stage == "publish"
    assert caught.value.__cause__ is failure
    assert failure.stage == "manifest-creation"


@pytest.mark.parametrize("failure", [EOFError("truncated"), OSError("unreadable")])
def test_translates_pcm_read_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    root = make_diarization_task_directory(tmp_path, make_diarization_manifest(1, ()), [0])
    reader = Mock(metadata=WaveMetadata(1, 16000, 1, 2, "NONE"))
    reader.read_frames.side_effect = failure
    monkeypatch.setattr(files, "WaveFileReader", Mock(return_value=reader))
    with pytest.raises(files.DiarizationFilesFailure) as caught:
        files.decode_canonical_audio(root, 1)
    assert caught.value.stage == "validate"
    assert caught.value.__cause__ is failure
