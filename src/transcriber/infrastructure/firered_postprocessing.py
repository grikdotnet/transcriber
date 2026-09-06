"""Thin primitive adapter around the pinned unchanged FireRedVAD postprocessor."""

from __future__ import annotations

import importlib
import sys
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast


class FireRedPostprocessingError(RuntimeError):
    """A bounded failure at the upstream postprocessing boundary."""


class _UpstreamPostprocessor(Protocol):
    def __init__(
        self,
        smooth_window_size: int,
        probability_threshold: float,
        min_speech_frame: int,
        max_speech_frame: int,
        min_silence_frame: int,
        merge_silence_frame: int,
        extend_speech_frame: int,
    ) -> None: ...

    def process(self, probabilities: list[float]) -> list[int]: ...

    def decision_to_segment(
        self, decisions: list[int], wav_dur: float
    ) -> list[tuple[float, float]]: ...


def _load_postprocessor() -> type[_UpstreamPostprocessor]:
    repository_root = Path(__file__).resolve().parents[3]
    third_party_root = repository_root / "third_party" / "firered-vad"
    package_root = third_party_root / "fireredvad"
    core_root = package_root / "core"
    expected_source = core_root / "vad_postprocessor.py"

    loaded = sys.modules.get("fireredvad.core.vad_postprocessor")
    if loaded is not None:
        loaded_source = Path(cast(str, loaded.__file__)).resolve()
        if loaded_source == expected_source.resolve():
            return cast(type[_UpstreamPostprocessor], loaded.VadPostprocessor)

    for module_name in tuple(sys.modules):
        if module_name == "fireredvad" or module_name.startswith("fireredvad."):
            del sys.modules[module_name]

    package = ModuleType("fireredvad")
    package.__path__ = [str(package_root)]
    package.__package__ = "fireredvad"
    core_package = ModuleType("fireredvad.core")
    core_package.__path__ = [str(core_root)]
    core_package.__package__ = "fireredvad.core"
    sys.modules["fireredvad"] = package
    sys.modules["fireredvad.core"] = core_package

    module = importlib.import_module("fireredvad.core.vad_postprocessor")
    if Path(cast(str, module.__file__)).resolve() != expected_source.resolve():
        raise ImportError("FireRedVAD postprocessor did not load from the pinned source")
    return cast(type[_UpstreamPostprocessor], module.VadPostprocessor)


def _seconds_to_sample(value: float) -> int:
    samples = Decimal(str(value)) * Decimal(16_000)
    integral = samples.to_integral_value()
    if samples != integral or integral < 0:
        raise FireRedPostprocessingError("upstream returned a non-sample-aligned timestamp")
    return int(integral)


class FireRedPostprocessor:
    """Supply exact configuration once and preserve primitive upstream intervals."""

    def process(
        self,
        probabilities: tuple[float, ...],
        max_speech_frame: int,
        total_samples: int,
    ) -> tuple[tuple[int, int], ...]:
        if isinstance(max_speech_frame, bool) or not isinstance(max_speech_frame, int):
            raise TypeError("max_speech_frame must be an integer")
        if max_speech_frame <= 0:
            raise ValueError("max_speech_frame must be positive")
        if isinstance(total_samples, bool) or not isinstance(total_samples, int):
            raise TypeError("total_samples must be an integer")
        if total_samples < 0:
            raise ValueError("total_samples must be non-negative")
        try:
            processor_type = _load_postprocessor()
            processor = processor_type(5, 0.4, 20, max_speech_frame, 20, 201, 50)
            decisions = processor.process(list(probabilities))
            timestamps = processor.decision_to_segment(decisions, total_samples / 16_000)
            return tuple(
                (_seconds_to_sample(start_seconds), _seconds_to_sample(end_seconds))
                for start_seconds, end_seconds in timestamps
            )
        except FireRedPostprocessingError:
            raise
        except Exception as error:
            raise FireRedPostprocessingError(
                "failed to load or run FireRedVAD postprocessor"
            ) from error
