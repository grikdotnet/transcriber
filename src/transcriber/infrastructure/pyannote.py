"""Direct, lazy Community-1 inference and Vulkan ownership (Infrastructure)."""

from __future__ import annotations

import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from transcriber.infrastructure.diarization_prerequisites import (
    check_community_prerequisites,
    check_vulkan_device,
)
from transcriber.infrastructure.diarization_provider import (
    CommunityInterval,
    DiarizationCancelled,
    DiarizationCleanupFailure,
    RecoverableDiarizationFailure,
)


def _release_exception_frames(error: BaseException) -> None:
    """Release runtime references in the complete cause/context graph."""
    pending = [error]
    visited: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        for linked in (current.__cause__, current.__context__):
            if linked is not None:
                pending.append(linked)
        traceback.clear_frames(current.__traceback__)
        current.__traceback__ = None
        current.__cause__ = None
        current.__context__ = None


def _not_cancelled() -> None:
    pass


class Community1Diarizer:
    """Own one recording's model references and process-wide Vulkan lifetime."""

    def __init__(self, model_dir: Path, vulkan_device: int) -> None:
        self._model_dir = model_dir
        self._vulkan_device = vulkan_device

    def diarize(
        self,
        samples: NDArray[np.float32],
        speaker_count: int,
        *,
        check_cancelled: Callable[[], None] = _not_cancelled,
    ) -> tuple[CommunityInterval, ...]:
        """Copy results before releasing every model and closing Vulkan."""
        check_cancelled()
        capabilities = check_community_prerequisites(self._model_dir)
        # GPU discovery itself may create Vulkan; cleanup ownership starts here.
        diarizer: Any = None
        segmentation: Any = None
        embeddings: Any = None
        clustering: Any = None
        rows: Any = None
        result: tuple[CommunityInterval, ...] = ()
        failure: RecoverableDiarizationFailure | DiarizationCancelled | None = None
        operation = "vulkan"
        try:
            check_cancelled()
            check_vulkan_device(capabilities.ncnn, self._vulkan_device)
            check_cancelled()
            operation = "construct"
            check_cancelled()
            diarizer = capabilities.diarizer_factory(
                self._model_dir,
                minimum_speakers=speaker_count,
                maximum_speakers=speaker_count,
                gpu_index=self._vulkan_device,
            )
            check_cancelled()
            operation = "segment"
            check_cancelled()
            segmentation = diarizer.segment(samples)
            check_cancelled()
            operation = "extract_embeddings"
            check_cancelled()
            embeddings = diarizer.extract_embeddings(samples, segmentation)
            check_cancelled()
            operation = "cluster"
            check_cancelled()
            clustering = diarizer.cluster(segmentation, embeddings)
            check_cancelled()
            operation = "reconstruct"
            check_cancelled()
            rows = diarizer.reconstruct(samples, segmentation, clustering)
            check_cancelled()
            operation = "copy"
            result = tuple(CommunityInterval(row.start, row.end, row.speaker) for row in rows)
            check_cancelled()
        except BaseException as error:
            diagnostic = str(error)
            if not isinstance(error, Exception) or isinstance(error, DiarizationCancelled):
                failure = DiarizationCancelled(
                    stage="community1",
                    operation=operation,
                    diagnostic=diagnostic,
                )
            else:
                failure = RecoverableDiarizationFailure(
                    stage="community1",
                    operation=operation,
                    diagnostic=diagnostic,
                )
            # Constructor/stage frames can retain partial native models. Clear those
            # frames while keeping only diagnostic text, before Vulkan teardown.
            _release_exception_frames(error)
        finally:
            rows = clustering = embeddings = segmentation = diarizer = None
            cleanup_diagnostic = None
            try:
                capabilities.close_vulkan()
            except BaseException as error:
                cleanup_diagnostic = str(error)
                _release_exception_frames(error)
            if cleanup_diagnostic is not None:
                raise DiarizationCleanupFailure(
                    stage="community1",
                    operation="cleanup",
                    diagnostic=cleanup_diagnostic,
                ) from None
        if failure is not None:
            raise failure from None
        return result
