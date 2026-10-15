"""Lazy checks for installed Community-1 capabilities (Infrastructure)."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from transcriber.infrastructure.diarization_provider import RecoverableDiarizationFailure

COMMUNITY_MODEL_FILES = (
    "segmentation.param", "segmentation.bin", "embedding_encoder.param", "embedding_encoder.bin",
    "resnet_seg_1_weight.npy", "resnet_seg_1_bias.npy", "plda.npz", "xvec_transform.npz",
)


@dataclass(frozen=True, slots=True)
class CommunityPrerequisites:
    """Loaded capabilities; no models or Vulkan resources are constructed here."""

    diarizer_factory: Callable[..., Any]
    ncnn: Any
    assignment_solver: Callable[..., Any]
    close_vulkan: Callable[[], None]


def check_community_prerequisites(model_dir: Path) -> CommunityPrerequisites:
    """Check only on the secondary branch; install nothing and leave GPU ownership untouched."""
    try:
        for filename in COMMUNITY_MODEL_FILES:
            if not (model_dir / filename).is_file():
                raise FileNotFoundError(f"required Community-1 model file: {model_dir / filename}")
        pipeline = importlib.import_module("diarization.pipeline")
        models = importlib.import_module("diarization.models")
        ncnn = importlib.import_module("ncnn")
        optimize = importlib.import_module("scipy.optimize")
        capabilities = (pipeline.Diarizer, optimize.linear_sum_assignment, models.close_vulkan)
        if not all(callable(capability) for capability in capabilities):
            raise TypeError("Community-1 runtime capabilities must be callable")
        return CommunityPrerequisites(
            pipeline.Diarizer, ncnn, optimize.linear_sum_assignment, models.close_vulkan,
        )
    except Exception as error:
        diagnostic = str(error)
    raise RecoverableDiarizationFailure(
        stage="community1", operation="prerequisites", diagnostic=diagnostic,
    ) from None


def check_vulkan_device(ncnn: Any, vulkan_device: int) -> None:
    """Check inside adapter ownership: get_gpu_count may create global Vulkan resources.

    The adapter must arrange Vulkan teardown before calling this function, including on failure.
    This function creates no model and does not destroy resources owned by the adapter.
    """
    try:
        if isinstance(vulkan_device, bool) or not isinstance(vulkan_device, int):
            raise ValueError("Vulkan device index must be an integer")
        if vulkan_device < 0:
            raise ValueError("Vulkan device index must be nonnegative")
        if not callable(getattr(ncnn, "get_gpu_count", None)) or not callable(
            getattr(getattr(ncnn, "Net", None), "set_vulkan_device", None)
        ):
            raise RuntimeError("installed NCNN Python binding has no Vulkan support")
        count = ncnn.get_gpu_count()
        if not 0 <= vulkan_device < count:
            raise ValueError(
                f"Vulkan GPU index {vulkan_device} is unavailable (found {count} devices)"
            )
        return
    except Exception as error:
        diagnostic = str(error)
    raise RecoverableDiarizationFailure(
        stage="community1", operation="vulkan", diagnostic=diagnostic,
    ) from None
