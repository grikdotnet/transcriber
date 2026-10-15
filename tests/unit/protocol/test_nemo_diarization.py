from __future__ import annotations

import ctypes as c
import gc

import pytest

from transcriber.protocol import nemo_diarization as abi


def test_native_field_order_types_and_alignment() -> None:
    expected = {
        abi.NemoDiarModelConfig: [
            ('size', c.c_size_t), ('model_path', c.c_char_p), ('gpu', c.c_int32),
            ('preset', c.c_char_p), ('chunk_frames', c.c_int32),
            ('right_context_frames', c.c_int32), ('left_context_frames', c.c_int32),
            ('fifo_frames', c.c_int32), ('spkcache_frames', c.c_int32),
            ('update_period_frames', c.c_int32),
        ],
        abi.NemoDiarSegment: [
            ('start_time', c.c_double), ('end_time', c.c_double), ('speaker', c.c_int32),
        ],
        abi.NemoDiarSegmentationConfig: [
            ('size', c.c_size_t), ('onset', c.c_float), ('offset', c.c_float),
            ('pad_onset_sec', c.c_double), ('pad_offset_sec', c.c_double),
            ('min_gap_sec', c.c_double), ('min_duration_sec', c.c_double),
        ],
    }
    for structure, fields in expected.items():
        assert structure._fields_ == fields
        offset = 0
        for name, field_type in fields:
            alignment = c.alignment(field_type)
            offset = (offset + alignment - 1) // alignment * alignment
            assert getattr(structure, name).offset == offset
            offset += c.sizeof(field_type)
        alignment = max(c.alignment(field_type) for _, field_type in fields)
        assert c.alignment(structure) == alignment
        assert c.sizeof(structure) == (offset + alignment - 1) // alignment * alignment
    if c.sizeof(c.c_void_p) == 8:
        assert [c.sizeof(t) for t in expected] == [56, 24, 48]


def test_all_symbol_signatures_match_pinned_header() -> None:
    handle, ptr = c.c_void_p, c.POINTER
    status = c.c_int
    expected = {
        'diar_create': ((ptr(abi.NemoDiarModelConfig), ptr(handle)), status),
        'diar_destroy': ((handle,), None),
        'diar_num_speakers': ((handle,), c.c_int32),
        'diar_seconds_per_frame': ((handle,), c.c_double),
        'diar_stream_open': ((handle, ptr(handle)), status),
        'diar_stream_push_f32': ((handle, ptr(c.c_float), c.c_size_t, c.c_int32), status),
        'diar_stream_finish': ((handle,), status),
        'diar_stream_close': ((handle,), None),
        'diar_offline_f32': (
            (handle, ptr(c.c_float), c.c_size_t, c.c_int32, ptr(handle)), status),
        'diar_frame_count': ((handle,), c.c_int64),
        'diar_frame_probs_start': ((handle,), c.c_int64),
        'diar_frame_probs': ((handle, ptr(c.c_float), c.c_size_t), status),
        'diar_segments': ((handle, ptr(abi.NemoDiarSegmentationConfig),
                           ptr(abi.NemoDiarSegment), c.c_size_t, ptr(c.c_size_t)), status),
        'asr_last_error': ((), c.c_char_p),
    }
    assert {name: (args, result) for name, args, result in abi.NATIVE_SIGNATURES} == {
        'nemo_speech_' + name: signature for name, signature in expected.items()
    }


def test_config_factory_retains_strings_and_native_defaults() -> None:
    config = abi.make_model_config('/models/é.gguf', 2)
    gc.collect()
    assert config.size == c.sizeof(abi.NemoDiarModelConfig)
    assert config.model_path == '/models/é.gguf'.encode()
    assert config.preset == b'v3-offline'
    assert config.gpu == 2
    assert config.left_context_frames == -1
    assert all(getattr(config, name) == 0 for name in (
        'chunk_frames', 'right_context_frames', 'fifo_frames',
        'spkcache_frames', 'update_period_frames'))
    segmentation = abi.make_segmentation_config()
    assert segmentation.size == c.sizeof(abi.NemoDiarSegmentationConfig)
    assert all(getattr(segmentation, name) == 0 for name, _ in segmentation._fields_[1:])


def test_segment_copy_owns_primitive_values_and_preserves_precision() -> None:
    array = abi.make_segment_array(2)
    array[0] = abi.NemoDiarSegment(0.123456789012345, 2.5, 7)
    array[1] = abi.NemoDiarSegment(3.0, 4.0, 1)
    copied = abi.copy_segments(array, 1)
    array[0].speaker = 99
    array[0].start_time = 0
    assert copied == ((0.123456789012345, 2.5, 7),)
    assert tuple(type(value) for value in copied[0]) == (float, float, int)
    assert abi.copy_segments(abi.make_segment_array(0), 0) == ()


@pytest.mark.parametrize('count', [-1, 3])
def test_copy_rejects_counts_outside_allocated_array(count: int) -> None:
    with pytest.raises(ValueError):
        abi.copy_segments(abi.make_segment_array(2), count)
