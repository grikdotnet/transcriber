"""Controlled Community-1 invocation and resource ownership tests."""

import asyncio
import gc
import weakref
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from transcriber.infrastructure import pyannote
from transcriber.infrastructure.diarization_prerequisites import CommunityPrerequisites
from transcriber.infrastructure.diarization_provider import (
    CommunityInterval,
    DiarizationCancelled,
    DiarizationCleanupFailure,
    RecoverableDiarizationFailure,
)


@pytest.fixture
def runtime(monkeypatch):
    events = []
    stage_values = [object(), object(), object()]
    rows = [SimpleNamespace(start=-0.25, end=2.125, speaker="a")]
    refs = []

    class Diarizer:
        def __init__(self, models_dir, **kwargs):
            events.append(("construct", models_dir, kwargs))
            refs.append(weakref.ref(self))

        def segment(self, audio):
            events.append(("segment", audio))
            return stage_values[0]

        def extract_embeddings(self, audio, segmentation):
            events.append(("embed", audio, segmentation))
            return stage_values[1]

        def cluster(self, segmentation, embeddings):
            events.append(("cluster", segmentation, embeddings))
            return stage_values[2]

        def reconstruct(self, audio, segmentation, clustering):
            events.append(("reconstruct", audio, segmentation, clustering))
            return rows

    def close():
        assert all(ref() is None for ref in refs)
        events.append(("close",))

    capabilities = CommunityPrerequisites(Diarizer, object(), lambda: None, close)
    monkeypatch.setattr(pyannote, "check_community_prerequisites", lambda path: capabilities)
    monkeypatch.setattr(
        pyannote, "check_vulkan_device", lambda ncnn, index: events.append(("gpu", ncnn, index))
    )
    return SimpleNamespace(
        events=events,
        values=stage_values,
        rows=rows,
        cls=Diarizer,
        capabilities=capabilities,
        refs=refs,
    )


def run():
    return pyannote.Community1Diarizer(Path("/models"), 3).diarize(
        np.array([0, 0.5], dtype=np.float32), 4
    )


def test_direct_stages_share_audio_and_objects_and_copy_rows(runtime):
    audio = np.array([0, 0.5], dtype=np.float32)
    result = pyannote.Community1Diarizer(Path("/models"), 3).diarize(audio, 4)
    assert result == (CommunityInterval(-0.25, 2.125, "a"),)
    assert runtime.events == [
        ("gpu", runtime.capabilities.ncnn, 3),
        ("construct", Path("/models"), dict(minimum_speakers=4, maximum_speakers=4, gpu_index=3)),
        ("segment", audio),
        ("embed", audio, runtime.values[0]),
        ("cluster", runtime.values[0], runtime.values[1]),
        ("reconstruct", audio, runtime.values[0], runtime.values[2]),
        ("close",),
    ]
    runtime.rows[0].speaker = "changed"
    assert result[0].speaker_id == "a"


def test_valid_empty_is_success(runtime):
    runtime.rows.clear()
    assert run() == ()


@pytest.mark.parametrize(
    "field,value", [("start", float("nan")), ("end", True), ("speaker", ""), ("speaker", 2)]
)
def test_malformed_rows_are_recoverable(runtime, field, value):
    setattr(runtime.rows[0], field, value)
    with pytest.raises(RecoverableDiarizationFailure):
        run()
    assert runtime.events[-1] == ("close",)


@pytest.mark.parametrize(
    "method", ["__init__", "segment", "extract_embeddings", "cluster", "reconstruct"]
)
@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt, asyncio.CancelledError])
def test_partial_construction_and_stage_failure_release_before_close(
    runtime, monkeypatch, method, error_type
):
    original = getattr(runtime.cls, method)

    def fail(self, *args, **kwargs):
        if method == "__init__":
            original(self, *args, **kwargs)
        raise error_type("broken")

    monkeypatch.setattr(runtime.cls, method, fail)
    expected = RecoverableDiarizationFailure if error_type is RuntimeError else DiarizationCancelled
    with pytest.raises(expected):
        run()
    assert runtime.events[-1] == ("close",)


def test_gpu_failure_still_closes(runtime, monkeypatch):
    def fail(*args):
        raise RecoverableDiarizationFailure(stage="community1", operation="vulkan")

    monkeypatch.setattr(pyannote, "check_vulkan_device", fail)
    with pytest.raises(RecoverableDiarizationFailure):
        run()
    assert runtime.events == [("close",)]


@pytest.mark.parametrize("cleanup_error", [RuntimeError, asyncio.CancelledError])
@pytest.mark.parametrize("inference_failure", [False, True])
def test_cleanup_failure_is_fatal(runtime, monkeypatch, inference_failure, cleanup_error):
    if inference_failure:

        def broken(self, audio):
            raise RuntimeError("inference")

        monkeypatch.setattr(runtime.cls, "segment", broken)

    def fail():
        raise cleanup_error("teardown")

    monkeypatch.setattr(
        pyannote,
        "check_community_prerequisites",
        lambda path: CommunityPrerequisites(runtime.cls, object(), lambda: None, fail),
    )
    with pytest.raises(DiarizationCleanupFailure) as caught:
        run()
    assert caught.value.stage == "community1"


@pytest.mark.parametrize("cancel_check", range(1, 15))
def test_cancellation_checks_surround_gpu_construction_and_stages(runtime, cancel_check):
    checks = 0

    def check_cancelled():
        nonlocal checks
        checks += 1
        if checks == cancel_check:
            raise DiarizationCancelled(stage="community1", operation="cancel")

    with pytest.raises(DiarizationCancelled):
        pyannote.Community1Diarizer(Path("/models"), 3).diarize(
            np.zeros(2, dtype=np.float32), 4, check_cancelled=check_cancelled
        )
    if cancel_check > 1:
        assert runtime.events[-1] == ("close",)


@pytest.mark.parametrize("method", ["__init__", "segment"])
@pytest.mark.parametrize("chain", ["cause", "context", "mixed_cycle"])
@pytest.mark.parametrize("cancelled", [False, True])
def test_nested_exception_frames_release_models_before_close(
    runtime, monkeypatch, method, chain, cancelled
):
    original = getattr(runtime.cls, method)

    def inner(model):
        failure = ValueError("inner failure")
        assert model is not None
        raise failure

    def fail(self, *args, **kwargs):
        if method == "__init__":
            original(self, *args, **kwargs)
        try:
            inner(self)
        except ValueError as cause:
            failure = (
                asyncio.CancelledError("outer failure")
                if cancelled
                else RuntimeError("outer failure")
            )
            if chain == "mixed_cycle":
                other = LookupError("context failure")
                cause.__cause__ = other
                other.__context__ = failure
                raise failure from cause
            if chain == "cause":
                raise failure from cause
            raise failure from None

    monkeypatch.setattr(runtime.cls, method, fail)
    expected = DiarizationCancelled if cancelled else RecoverableDiarizationFailure
    gc_enabled = gc.isenabled()
    gc.disable()
    try:
        with pytest.raises(expected) as caught:
            run()
    finally:
        if gc_enabled:
            gc.enable()
    assert caught.value.operation == ("construct" if method == "__init__" else "segment")
    assert caught.value.diagnostic == "outer failure"
    assert runtime.events.count(("close",)) == 1
