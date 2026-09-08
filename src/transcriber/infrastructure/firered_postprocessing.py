"""Thin primitive adapter around the pinned unchanged FireRedVAD postprocessor."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Final, Protocol, cast

_FRAME_LENGTH_SAMPLES: Final = 400
_FRAME_SHIFT_SAMPLES: Final = 160


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


def _decisions_to_sample_intervals(
    decisions: list[int], total_samples: int
) -> tuple[tuple[int, int], ...]:
    """Map binary upstream frame decisions onto Canonical Audio samples."""
    intervals: list[tuple[int, int]] = []
    start_sample: int | None = None

    for index, decision in enumerate(decisions):
        if type(decision) is not int or decision not in (0, 1):
            raise FireRedPostprocessingError("upstream decisions must be binary integers")
        sample_position = index * _FRAME_SHIFT_SAMPLES
        if decision == 1 and start_sample is None:
            start_sample = sample_position
        elif decision == 0 and start_sample is not None:
            intervals.append((start_sample, sample_position))
            start_sample = None

    if start_sample is not None:
        end_sample = min(
            len(decisions) * _FRAME_SHIFT_SAMPLES + _FRAME_LENGTH_SAMPLES,
            total_samples,
        )
        intervals.append((start_sample, end_sample))

    return tuple(intervals)


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
            return _decisions_to_sample_intervals(decisions, total_samples)
        except FireRedPostprocessingError:
            raise
        except Exception as error:
            raise FireRedPostprocessingError(
                "failed to load or run FireRedVAD postprocessor"
            ) from error
