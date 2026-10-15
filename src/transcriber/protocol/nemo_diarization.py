"""Pure ctypes declarations and value copies for the pinned NeMo diarization ABI."""

from __future__ import annotations

import ctypes as c
from typing import Final


class NemoDiarModelConfig(c.Structure):
    _fields_ = [
        ("size", c.c_size_t),
        ("model_path", c.c_char_p),
        ("gpu", c.c_int32),
        ("preset", c.c_char_p),
        ("chunk_frames", c.c_int32),
        ("right_context_frames", c.c_int32),
        ("left_context_frames", c.c_int32),
        ("fifo_frames", c.c_int32),
        ("spkcache_frames", c.c_int32),
        ("update_period_frames", c.c_int32),
    ]


class NemoDiarSegmentationConfig(c.Structure):
    _fields_ = [
        ("size", c.c_size_t),
        ("onset", c.c_float),
        ("offset", c.c_float),
        ("pad_onset_sec", c.c_double),
        ("pad_offset_sec", c.c_double),
        ("min_gap_sec", c.c_double),
        ("min_duration_sec", c.c_double),
    ]


class NemoDiarSegment(c.Structure):
    _fields_ = [
        ("start_time", c.c_double),
        ("end_time", c.c_double),
        ("speaker", c.c_int32),
    ]


# ctypes uses None for a C void return. Handles remain opaque void pointers.
NATIVE_SIGNATURES: Final[tuple[tuple[str, tuple[type, ...], type | None], ...]] = (
    ("nemo_speech_diar_create", (c.POINTER(NemoDiarModelConfig), c.POINTER(c.c_void_p)), c.c_int),
    ("nemo_speech_diar_destroy", (c.c_void_p,), None),
    ("nemo_speech_diar_num_speakers", (c.c_void_p,), c.c_int32),
    ("nemo_speech_diar_seconds_per_frame", (c.c_void_p,), c.c_double),
    ("nemo_speech_diar_stream_open", (c.c_void_p, c.POINTER(c.c_void_p)), c.c_int),
    (
        "nemo_speech_diar_stream_push_f32",
        (c.c_void_p, c.POINTER(c.c_float), c.c_size_t, c.c_int32),
        c.c_int,
    ),
    ("nemo_speech_diar_stream_finish", (c.c_void_p,), c.c_int),
    ("nemo_speech_diar_stream_close", (c.c_void_p,), None),
    (
        "nemo_speech_diar_offline_f32",
        (c.c_void_p, c.POINTER(c.c_float), c.c_size_t, c.c_int32, c.POINTER(c.c_void_p)),
        c.c_int,
    ),
    ("nemo_speech_diar_frame_count", (c.c_void_p,), c.c_int64),
    ("nemo_speech_diar_frame_probs_start", (c.c_void_p,), c.c_int64),
    (
        "nemo_speech_diar_frame_probs",
        (c.c_void_p, c.POINTER(c.c_float), c.c_size_t),
        c.c_int,
    ),
    (
        "nemo_speech_diar_segments",
        (
            c.c_void_p,
            c.POINTER(NemoDiarSegmentationConfig),
            c.POINTER(NemoDiarSegment),
            c.c_size_t,
            c.POINTER(c.c_size_t),
        ),
        c.c_int,
    ),
    ("nemo_speech_asr_last_error", (), c.c_char_p),
)


def make_model_config(model_path: str, gpu: int) -> NemoDiarModelConfig:
    """Build the stateful offline preset, retaining bytes in ctypes ownership."""
    return NemoDiarModelConfig(
        size=c.sizeof(NemoDiarModelConfig),
        model_path=model_path.encode("utf-8"),
        gpu=gpu,
        preset=b"v3-offline",
        left_context_frames=-1,
    )


def make_segmentation_config() -> NemoDiarSegmentationConfig:
    """Describe native default postprocessing; inference passes NULL instead."""
    return NemoDiarSegmentationConfig(size=c.sizeof(NemoDiarSegmentationConfig))


def make_segment_array(count: int) -> c.Array[NemoDiarSegment]:
    """Allocate caller-owned native result storage, including an empty array."""
    return (NemoDiarSegment * count)()


def copy_segments(
    segments: c.Array[NemoDiarSegment], count: int
) -> tuple[tuple[float, float, int], ...]:
    """Detach double-precision times and speaker IDs from caller-owned storage."""
    if not 0 <= count <= len(segments):
        raise ValueError("segment count must fit the allocated array")
    return tuple(
        (float(segments[index].start_time), float(segments[index].end_time),
         int(segments[index].speaker))
        for index in range(count)
    )
