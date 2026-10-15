"""Project-owned NeMo call sequencing and ownership with a controlled C boundary."""
import ctypes as c
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from transcriber.infrastructure.diarization_provider import (
    DiarizationCancelled,
    DiarizationCleanupFailure,
    DiarizationProviderFailure,
)
from transcriber.infrastructure.nemo_speech import NemoSpeechAdapter
from transcriber.protocol.nemo_diarization import (
    NATIVE_SIGNATURES,
    copy_segments,
    make_model_config,
    make_segment_array,
)


class Symbol:
    def __init__(self, call: Any) -> None:
        self.call = call

    def __call__(self, *args: Any) -> Any:
        return self.call(*args)


class Native:
    def __init__(self, failure: str = '', status: int = 3, interrupt: bool = False) -> None:
        self.events: list[str] = []
        self.failure, self.status, self.interrupt = failure, status, interrupt
        self.empty = False
        self.audio: Any = None
        for name, _, _ in NATIVE_SIGNATURES:
            setattr(self, name, Symbol(lambda *args, name=name: self.invoke(name, *args)))

    def invoke(self, name: str, *args: Any) -> Any:
        operation = name.removeprefix('nemo_speech_')
        self.events.append(operation)
        if operation == 'asr_last_error':
            return b'original diagnostic'
        if operation == 'diar_create':
            config = args[0]._obj
            assert config.gpu == -1 and config.preset == b'v3-offline'
            assert config.model_path == b'/model.gguf'
            args[1]._obj.value = 11
        if operation == 'diar_stream_open':
            assert args[0].value == 11
            args[1]._obj.value = 22
        if operation == 'diar_stream_push_f32':
            assert args[0].value == 22
            assert c.cast(args[1], c.c_void_p).value == self.audio.ctypes.data
            assert args[2] == len(self.audio) and args[3] == 16000
        if operation == 'diar_segments':
            assert args[1] is None
            args[4]._obj.value = 0 if self.empty else 1
            if args[2] is not None:
                args[2][0].start_time = 0.125
                args[2][0].end_time = 1.25
                args[2][0].speaker = 2
        if operation == self.failure:
            if self.interrupt:
                raise KeyboardInterrupt
            if operation in ('diar_stream_close', 'diar_destroy'):
                raise RuntimeError('cleanup broken')
            return self.status
        return 0


def adapter(native: Native, **kwargs: Any) -> NemoSpeechAdapter:
    return NemoSpeechAdapter(
        library_path=Path('/lib.dylib'), model_path=Path('/model.gguf'), gpu_index=-1,
        make_model_config=make_model_config, make_segment_array=make_segment_array,
        copy_segments=copy_segments, signatures=NATIVE_SIGNATURES,
        load_library=lambda _: native, **kwargs,
    )


def run(native: Native, **kwargs: Any) -> Any:
    native.audio = np.zeros(32000, dtype=np.float32)
    return adapter(native, **kwargs).diarize(native.audio)


def test_full_audio_sequence_and_detached_results() -> None:
    native = Native()
    result = run(native)
    assert [(row.start_seconds, row.end_seconds, row.speaker_id) for row in result] == [
        (0.125, 1.25, 2),
    ]
    assert native.events == [
        'diar_create', 'diar_stream_open', 'diar_stream_push_f32', 'diar_stream_finish',
        'diar_segments', 'diar_segments', 'diar_stream_close', 'diar_destroy',
    ]
    for name, args, result_type in NATIVE_SIGNATURES:
        assert getattr(native, name).argtypes == list(args)
        assert getattr(native, name).restype == result_type


def test_zero_count_does_not_allocate() -> None:
    native = Native()
    native.empty = True
    instance = adapter(native)
    instance.make_segment_array = lambda _: pytest.fail('empty output allocated')
    native.audio = np.zeros(0, dtype=np.float32)
    assert instance.diarize(native.audio) == ()
    assert native.events.count('diar_segments') == 1


@pytest.mark.parametrize('operation', ['diar_create', 'diar_stream_open',
    'diar_stream_push_f32', 'diar_stream_finish', 'diar_segments'])
@pytest.mark.parametrize('status', [1, 2, 3, 4, 99])
def test_status_copies_error_before_cleanup(operation: str, status: int) -> None:
    native = Native(operation, status)
    expected = DiarizationCancelled if status == 4 else DiarizationProviderFailure
    with pytest.raises(expected) as caught:
        run(native)
    assert caught.value.status == status
    assert caught.value.diagnostic == 'original diagnostic'
    index = native.events.index(operation)
    assert native.events[index + 1] == 'asr_last_error'
    assert native.events[-1] == 'diar_destroy'
    if operation != 'diar_create':
        assert native.events[-2] == 'diar_stream_close'


@pytest.mark.parametrize('operation', ['diar_create', 'diar_stream_open', 'diar_stream_finish'])
def test_interrupt_cleans_populated_out_handles(operation: str) -> None:
    native = Native(operation, interrupt=True)
    with pytest.raises(DiarizationCancelled):
        run(native)
    assert native.events[-1] == 'diar_destroy'
    if operation != 'diar_create':
        assert native.events[-2] == 'diar_stream_close'


def test_cleanup_failure_still_destroys_model() -> None:
    native = Native('diar_stream_close')
    with pytest.raises(DiarizationCleanupFailure) as caught:
        run(native)
    assert caught.value.stage == 'nemotron'
    assert native.events[-1] == 'diar_destroy'


@pytest.mark.parametrize('row', [(0.0, 1.0, True), (float('nan'), 1.0, 1), (0.0, 1.0, 0)])
def test_malformed_copied_results_are_fatal(row: Any) -> None:
    native = Native()
    instance = adapter(native)
    instance.copy_segments = lambda *_: (row,)
    native.audio = np.zeros(1, dtype=np.float32)
    with pytest.raises(DiarizationProviderFailure) as caught:
        instance.diarize(native.audio)
    assert caught.value.operation == 'copy_segments'
    assert native.events[-2:] == ['diar_stream_close', 'diar_destroy']


def test_output_array_released_before_return() -> None:
    import weakref

    native = Native()
    instance = adapter(native)
    references: list[Any] = []

    def allocate(count: int) -> Any:
        buffer = make_segment_array(count)
        references.append(weakref.ref(buffer))
        return buffer

    instance.make_segment_array = allocate
    native.audio = np.zeros(1, dtype=np.float32)
    instance.diarize(native.audio)
    assert references[0]() is None


def test_application_cancellation_after_create_cleans_model() -> None:
    native = Native()

    def cancelled() -> None:
        if native.events:
            raise DiarizationCancelled(stage='cancelled', operation='application')

    with pytest.raises(DiarizationCancelled):
        run(native, check_cancelled=cancelled)
    assert native.events == ['diar_create', 'diar_destroy']


def test_async_cancellation_during_fetch_releases_buffer() -> None:
    import asyncio
    import weakref

    native = Native()
    instance = adapter(native)
    references: list[Any] = []

    def allocate(count: int) -> Any:
        buffer = make_segment_array(count)
        references.append(weakref.ref(buffer))
        return buffer

    original = native.invoke

    def invoke(name: str, *args: Any) -> Any:
        if name == 'nemo_speech_diar_segments' and args[2] is not None:
            raise asyncio.CancelledError('cancel fetch')
        return original(name, *args)

    native.invoke = invoke
    instance.make_segment_array = allocate
    native.audio = np.zeros(1, dtype=np.float32)
    with pytest.raises(DiarizationCancelled):
        instance.diarize(native.audio)
    assert references[0]() is None
    assert native.events[-2:] == ['diar_stream_close', 'diar_destroy']


def test_cleanup_failure_overrides_async_cancellation() -> None:
    import asyncio

    native = Native('diar_stream_close')
    original = native.invoke

    def invoke(name: str, *args: Any) -> Any:
        if name == 'nemo_speech_diar_stream_finish':
            raise asyncio.CancelledError('cancel finish')
        return original(name, *args)

    native.invoke = invoke
    with pytest.raises(DiarizationCleanupFailure) as caught:
        run(native)
    assert caught.value.stage == 'nemotron'
    assert native.events[-1] == 'diar_destroy'


@pytest.mark.parametrize('boundary', ['copy', 'fetch'])
@pytest.mark.parametrize('failure_kind', ['runtime', 'async', 'keyboard', 'provider'])
@pytest.mark.parametrize('chain', ['none', 'cause', 'context', 'cycle'])
def test_cyclic_failure_releases_output_array(
    boundary: str, failure_kind: str, chain: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import gc
    import weakref

    native = Native()
    instance = adapter(native)
    references: list[Any] = []

    def allocate(count: int) -> Any:
        buffer = make_segment_array(count)
        references.append(weakref.ref(buffer))
        return buffer

    def fail(array: Any, count: int) -> Any:
        failure: BaseException
        if failure_kind == 'async':
            failure = asyncio.CancelledError('buffer failure')
        elif failure_kind == 'keyboard':
            failure = KeyboardInterrupt('buffer failure')
        elif failure_kind == 'provider':
            failure = DiarizationCancelled(stage='nemotron', operation='copy_segments')
        else:
            failure = RuntimeError('buffer failure')
        if chain != 'none':
            try:
                raise failure
            except BaseException as cause:
                wrapper: BaseException = RuntimeError('wrapped buffer failure')
                if failure_kind == 'async':
                    wrapper = asyncio.CancelledError('wrapped buffer failure')
                elif failure_kind == 'keyboard':
                    wrapper = KeyboardInterrupt('wrapped buffer failure')
                elif failure_kind == 'provider':
                    wrapper = DiarizationCancelled(stage='nemotron', operation='copy_segments')
                if chain == 'cycle':
                    cause.__context__ = wrapper
                if chain == 'context':
                    raise wrapper from None
                raise wrapper from cause
        raise failure

    original = native.invoke

    def invoke(name: str, *args: Any) -> Any:
        if name == 'nemo_speech_diar_segments' and args[2] is not None:
            return fail(args[2], args[3])
        return original(name, *args)

    instance.make_segment_array = allocate
    if boundary == 'copy':
        instance.copy_segments = fail
    else:
        monkeypatch.setattr(native, 'invoke', invoke)
    native.audio = np.zeros(1, dtype=np.float32)
    expected = DiarizationProviderFailure if failure_kind == 'runtime' else DiarizationCancelled
    collecting = gc.isenabled()
    gc.disable()
    try:
        with pytest.raises(expected) as caught:
            instance.diarize(native.audio)
        assert references[0]() is None
        assert caught.value.stage == 'nemotron'
        if failure_kind == 'runtime':
            expected_diagnostic = 'buffer failure' if chain == 'none' else 'wrapped buffer failure'
            assert caught.value.diagnostic == expected_diagnostic
        assert native.events[-2:] == ['diar_stream_close', 'diar_destroy']
    finally:
        if collecting:
            gc.enable()
