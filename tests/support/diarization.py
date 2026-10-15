"""Small controlled inputs shared by diarization tests.

T003 file-boundary tests consume the manifest/directory builders. T004 fusion
tests and T009 workflow tests consume the handwritten prediction rows; those
tests construct their owning layer's typed values from the rows. T014 acceptance
tests reuse both inputs. T009/T012 lifecycle tests use the existing CallLog to
observe engine cleanup before publication.

The ten-second prediction example has four seconds of single-speaker agreement
for each pair: ``a -> 1`` and ``b -> 2``. Community-1 can therefore fill the base
gaps [4, 5) and [9, 10). These inputs are handwritten, never inferred by a model
or calculated with production fusion code. Specialized native fakes stay in
the adapter test modules.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from tests.support.audio import make_pcm_wav
from tests.support.call_log import CallLog as CallLog
from transcriber.domain.manifest import (
    ManifestAudio,
    ManifestSegment,
    SegmentManifest,
    encode_manifest,
)

# Rows are (start_seconds, end_seconds, recording-local speaker identity).
NEMOTRON_PREDICTION: tuple[tuple[float, float, int], ...] = (
    (0.0, 4.0, 1),
    (5.0, 9.0, 2),
)
COMMUNITY_PREDICTION: tuple[tuple[float, float, str], ...] = (
    (0.0, 5.0, "a"),
    (5.0, 10.0, "b"),
)


def make_diarization_manifest(
    total_samples: int, speech_intervals: tuple[tuple[int, int], ...]
) -> SegmentManifest:
    """Build T003/T004/T014 mask inputs, including gaps or an empty union."""
    return SegmentManifest(
        schema_version=1,
        audio=ManifestAudio(total_samples=total_samples),
        segments=tuple(
            ManifestSegment(
                index=index,
                start_sample=start,
                end_sample=end,
                duration_samples=end - start,
                path=f"segments/segment-{index:04d}.wav",
            )
            for index, (start, end) in enumerate(speech_intervals)
        ),
    )


def make_diarization_task_directory(
    tmp_path: Path, manifest: SegmentManifest, pcm_samples: Iterable[int]
) -> Path:
    """Write T003/T014 canonical inputs; segment WAVs are not consumed."""
    task_work_directory = tmp_path / "diarization-task"
    task_work_directory.mkdir()
    (task_work_directory / "manifest.json").write_bytes(encode_manifest(manifest))
    make_pcm_wav(task_work_directory / "prepared.wav", pcm_samples)
    return task_work_directory
