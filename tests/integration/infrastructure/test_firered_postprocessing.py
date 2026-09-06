from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

import transcriber.infrastructure.firered_postprocessing as adapter_module
from transcriber.infrastructure.firered_postprocessing import (
    FireRedPostprocessingError,
    FireRedPostprocessor,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PINNED_VAD_SHA256 = "6cd38de7b9877839480c0bb7bbc3e5e59253d32769b4cbaef7d2e69b899ba232"
PINNED_POSTPROCESSOR_SHA256 = "637320cdd09548cbb5756ad4151a6d074325ba2e246eca3aff6fe1963b251231"


def test_pinned_upstream_vad_source_is_unchanged() -> None:
    source = REPOSITORY_ROOT / "third_party/firered-vad/fireredvad/vad.py"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == PINNED_VAD_SHA256


def test_loads_pinned_upstream_postprocessor_from_its_actual_source() -> None:
    source = REPOSITORY_ROOT / "third_party/firered-vad/fireredvad/core/vad_postprocessor.py"

    processor_type = adapter_module._load_postprocessor()

    assert Path(inspect.getsourcefile(processor_type) or "").resolve() == source.resolve()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == PINNED_POSTPROCESSOR_SHA256
    assert FireRedPostprocessor().process(
        (), max_speech_frame=3_000, total_samples=0
    ) == ()


def test_passes_complete_probabilities_and_exact_settings_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    class FakeUpstream:
        def __init__(self, *settings: object) -> None:
            calls.append(("init", *settings))

        def process(self, probabilities: list[float]) -> list[int]:
            calls.append(("process", probabilities))
            return [0, 1, 1, 0, 1]

        def decision_to_segment(
            self, decisions: list[int], wav_dur: float
        ) -> list[tuple[float, float]]:
            calls.append(("segments", decisions, wav_dur))
            return [(0.01, 0.03), (0.04, 0.05)]

    monkeypatch.setattr(adapter_module, "_load_postprocessor", lambda: FakeUpstream)
    probabilities = (0.11, 0.22, 0.33, 0.44, 0.55)

    intervals = FireRedPostprocessor().process(
        probabilities, max_speech_frame=3_000, total_samples=800
    )

    assert calls == [
        ("init", 5, 0.4, 20, 3_000, 20, 201, 50),
        ("process", list(probabilities)),
        ("segments", [0, 1, 1, 0, 1], 0.05),
    ]
    assert intervals == ((160, 480), (640, 800))


def test_passes_canonical_duration_and_preserves_short_eof_remainder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    class FakeUpstream:
        def __init__(self, *_settings: object) -> None:
            pass

        def process(self, probabilities: list[float]) -> list[int]:
            return [1] * len(probabilities)

        def decision_to_segment(
            self, decisions: list[int], wav_dur: float
        ) -> list[tuple[float, float]]:
            calls.append(("segments", decisions, wav_dur))
            return [(0.0, 0.3), (0.3, wav_dur)]

    monkeypatch.setattr(adapter_module, "_load_postprocessor", lambda: FakeUpstream)
    assert FireRedPostprocessor().process((0.7,) * 31, 3_000, total_samples=5_360) == (
        (0, 4_800),
        (4_800, 5_360),
    )
    assert calls == [("segments", [1] * 31, 0.335)]


def test_translates_upstream_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_to_load() -> object:
        raise ImportError("dependency detail")

    monkeypatch.setattr(adapter_module, "_load_postprocessor", fail_to_load)

    with pytest.raises(FireRedPostprocessingError, match="load"):
        FireRedPostprocessor().process((0.5,), 3_000, total_samples=400)


@pytest.mark.parametrize("total_samples", [True, -1, 1.5])
def test_rejects_invalid_canonical_sample_count(total_samples: object) -> None:
    with pytest.raises((TypeError, ValueError), match="total_samples"):
        FireRedPostprocessor().process(
            (), max_speech_frame=3_000, total_samples=total_samples  # type: ignore[arg-type]
        )
