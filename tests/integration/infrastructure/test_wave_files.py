from __future__ import annotations

import wave
from pathlib import Path

import pytest

from tests.support.audio import make_pcm, make_pcm_wav
from transcriber.infrastructure.wave_files import (
    WaveFileReader,
    WaveMetadata,
    WaveSegmentWriter,
)


def _read_generated_wave(path: Path) -> tuple[WaveMetadata, bytes]:
    with wave.open(str(path), "rb") as generated:
        metadata = WaveMetadata(
            frame_count=generated.getnframes(),
            sample_rate_hz=generated.getframerate(),
            channel_count=generated.getnchannels(),
            sample_width_bytes=generated.getsampwidth(),
            compression_type=generated.getcomptype(),
        )
        return metadata, generated.readframes(generated.getnframes())


def test_writer_creates_the_exact_requested_sample_slice(tmp_path: Path) -> None:
    source_samples = tuple(range(-6, 6))
    source = make_pcm_wav(tmp_path / "controlled.wav", source_samples)
    destination = tmp_path / "segment.wav"

    metadata = WaveSegmentWriter(WaveFileReader(source)).write(
        destination,
        start_sample=3,
        end_sample=9,
    )

    reopened_metadata, pcm = _read_generated_wave(destination)
    expected_metadata = WaveMetadata(
        frame_count=6,
        sample_rate_hz=16_000,
        channel_count=1,
        sample_width_bytes=2,
        compression_type="NONE",
    )
    assert metadata == expected_metadata
    assert reopened_metadata == expected_metadata
    assert pcm == make_pcm(source_samples[3:9])


def test_offsets_are_frames_and_the_controlled_source_format_is_preserved(
    tmp_path: Path,
) -> None:
    # Six stereo frames. Distinct channel values make byte-offset mistakes visible.
    interleaved_samples = (10, 11, 20, 21, 30, 31, 40, 41, 50, 51, 60, 61)
    source = make_pcm_wav(
        tmp_path / "controlled-stereo.wav",
        interleaved_samples,
        sample_rate_hz=8_000,
        channels=2,
    )
    reader = WaveFileReader(source)
    destination = tmp_path / "middle-frames.wav"

    metadata = WaveSegmentWriter(reader).write(
        destination,
        start_sample=2,
        end_sample=5,
    )

    reopened_metadata, pcm = _read_generated_wave(destination)
    assert reader.metadata == WaveMetadata(
        frame_count=6,
        sample_rate_hz=8_000,
        channel_count=2,
        sample_width_bytes=2,
        compression_type="NONE",
    )
    assert metadata == reopened_metadata == WaveMetadata(
        frame_count=3,
        sample_rate_hz=8_000,
        channel_count=2,
        sample_width_bytes=2,
        compression_type="NONE",
    )
    assert pcm == make_pcm(interleaved_samples[4:10])


@pytest.mark.parametrize(
    ("start_sample", "end_sample"),
    [(-1, 1), (0, 0), (3, 2), (0, 5), (False, 1), (0, True)],
)
def test_reader_rejects_invalid_or_out_of_bounds_primitive_offsets(
    tmp_path: Path,
    start_sample: int,
    end_sample: int,
) -> None:
    source = make_pcm_wav(tmp_path / "controlled.wav", (100, 200, 300, 400))
    destination = tmp_path / "invalid.wav"

    with pytest.raises((TypeError, ValueError)):
        WaveSegmentWriter(WaveFileReader(source)).write(
            destination,
            start_sample=start_sample,
            end_sample=end_sample,
        )

    assert not destination.exists()
