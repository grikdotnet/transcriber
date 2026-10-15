"""Real-file Canonical Audio decode and publication integration."""

from pathlib import Path

import numpy as np

from tests.support.diarization import make_diarization_manifest, make_diarization_task_directory
from transcriber.infrastructure.diarization_files import (
    decode_canonical_audio,
    publish_diarization,
    read_manifest_file,
)


def test_real_files_decode_and_rerun_publication_preserve_inputs(tmp_path: Path) -> None:
    root = make_diarization_task_directory(
        tmp_path, make_diarization_manifest(3, ((0, 3),)), [-32768, 0, 32767]
    )
    before = {path.name: path.read_bytes() for path in root.iterdir()}
    assert read_manifest_file(root) == before["manifest.json"]
    decoded = decode_canonical_audio(root, 3)
    np.testing.assert_array_equal(decoded.samples, [-1, 0, 32767 / 32768])
    destination = publish_diarization(root, b"first complete artifact")
    assert publish_diarization(root, b"second complete artifact") == destination
    assert destination.read_bytes() == b"second complete artifact"
    assert all((root / name).read_bytes() == content for name, content in before.items())
    assert sorted(path.name for path in root.iterdir()) == [
        "diarization.json",
        "manifest.json",
        "prepared.wav",
    ]
