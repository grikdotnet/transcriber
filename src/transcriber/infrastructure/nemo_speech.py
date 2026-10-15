"""Direct stateful NeMo inference and native resource ownership (Infrastructure)."""
from __future__ import annotations

import asyncio
import ctypes as c
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from transcriber.infrastructure.diarization_provider import (
    DiarizationCancelled,
    DiarizationCleanupFailure,
    DiarizationProviderFailure,
    NemotronInterval,
)


def _no_cancellation() -> None:
    pass


def _release_failure_frames(error: BaseException) -> None:
    """Release native buffers retained by completed callback frames and chains."""
    pending = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        for linked in (current.__cause__, current.__context__):
            if linked is not None:
                pending.append(linked)
        if current.__traceback__ is not None:
            traceback.clear_frames(current.__traceback__)
            current.__traceback__ = None


class NemoSpeechAdapter:
    """Own handles and result storage for one complete Canonical Audio prediction.

    The injected factories describe ctypes objects; their dynamic types remain inside
    this native boundary. Composition supplies wire declarations without a layer import.
    """

    def __init__(
        self, *, library_path: Path, model_path: Path, gpu_index: int,
        make_model_config: Callable[[str, int], Any],
        make_segment_array: Callable[[int], Any],
        copy_segments: Callable[[Any, int], tuple[tuple[float, float, int], ...]],
        signatures: tuple[tuple[str, tuple[type, ...], type | None], ...],
        load_library: Callable[[str], Any] = c.CDLL,
        check_cancelled: Callable[[], None] = _no_cancellation,
    ) -> None:
        self.library_path = library_path
        self.model_path = model_path
        self.gpu_index = gpu_index
        self.make_model_config = make_model_config
        self.make_segment_array = make_segment_array
        self.copy_segments = copy_segments
        self.signatures = signatures
        self.load_library = load_library
        self.check_cancelled = check_cancelled

    def diarize(self, audio: NDArray[np.float32]) -> tuple[NemotronInterval, ...]:
        """Copy intervals before releasing stream, model and caller-owned storage."""
        library: Any = None
        model = c.c_void_p()
        stream = c.c_void_p()
        buffer: Any = None
        config: Any = None
        failure: DiarizationProviderFailure | None = None
        cleanup_errors: list[str] = []
        result: tuple[NemotronInterval, ...] = ()
        operation = 'load'
        try:
            self.check_cancelled()
            if audio.dtype != np.float32 or audio.ndim != 1 or not audio.flags.c_contiguous:
                raise ValueError('audio must be a contiguous one-dimensional float32 array')
            library = self.load_library(str(self.library_path))
            for name, arguments, return_type in self.signatures:
                symbol = getattr(library, name)
                symbol.argtypes = list(arguments)
                symbol.restype = return_type
            config = self.make_model_config(str(self.model_path), self.gpu_index)

            def call(name: str, *arguments: Any) -> None:
                nonlocal operation
                operation = name
                self.check_cancelled()
                status = getattr(library, f'nemo_speech_{name}')(*arguments)
                if status:
                    # Copy the thread-local error before cancellation checks or cleanup.
                    raw_error = library.nemo_speech_asr_last_error()
                    diagnostic = (
                        raw_error.decode('utf-8', errors='replace') if raw_error else None
                    )
                    failure_type = (
                        DiarizationCancelled if status == 4 else DiarizationProviderFailure
                    )
                    raise failure_type(
                        stage='nemotron', operation=name, diagnostic=diagnostic, status=int(status),
                    )
                self.check_cancelled()

            call('diar_create', c.byref(config), c.byref(model))
            if not model.value:
                raise ValueError('successful create returned a null model handle')
            call('diar_stream_open', model, c.byref(stream))
            if not stream.value:
                raise ValueError('successful open returned a null stream handle')
            call('diar_stream_push_f32', stream, audio.ctypes.data_as(c.POINTER(c.c_float)),
                 len(audio), 16000)
            call('diar_stream_finish', stream)
            count = c.c_size_t()
            call('diar_segments', stream, None, None, 0, c.byref(count))
            if count.value:
                capacity = count.value
                buffer = self.make_segment_array(capacity)
                call('diar_segments', stream, None, buffer, capacity, c.byref(count))
                if count.value > capacity:
                    raise ValueError('native segment count exceeds allocated capacity')
                operation = 'copy_segments'
                result = tuple(
                    NemotronInterval(*row) for row in self.copy_segments(buffer, count.value)
                )
                self.check_cancelled()
        except (KeyboardInterrupt, asyncio.CancelledError) as error:
            failure = DiarizationCancelled(stage='nemotron', operation=operation)
            _release_failure_frames(error)
        except DiarizationProviderFailure as error:
            failure = error
            _release_failure_frames(error)
        except Exception as error:
            failure = DiarizationProviderFailure(
                stage='nemotron', operation=operation, diagnostic=str(error),
            )
            _release_failure_frames(error)
        finally:
            # Out holders are inspected even when create/open raised after populating them.
            if library is not None:
                for handle, name in ((stream, 'diar_stream_close'), (model, 'diar_destroy')):
                    if handle.value:
                        try:
                            getattr(library, f'nemo_speech_{name}')(handle)
                        except BaseException as error:
                            cleanup_errors.append(f'{name}: {error}')
                            _release_failure_frames(error)
                        finally:
                            handle.value = None
            buffer = None
            config = None
        if cleanup_errors:
            raise DiarizationCleanupFailure(
                stage='nemotron', operation='cleanup', diagnostic='; '.join(cleanup_errors),
            ) from None
        if failure is not None:
            raise failure from None
        return result
