from pathlib import Path
from types import SimpleNamespace

import numpy as np

from transcriber.composition import application
from transcriber.domain.diarization import SampleSpeakerActivity
from transcriber.infrastructure.diarization_provider import CommunityInterval, NemotronInterval
from transcriber.protocol.diarization_json import decode_diarization
from transcriber.protocol.nemo_diarization import NATIVE_SIGNATURES


def test_assembly_injects_native_contract_and_maps_owned_values(monkeypatch) -> None:
    calls = {}

    class Nemo:
        def __init__(self, **kwargs):
            calls.update(kwargs)

        def diarize(self, samples):
            return (NemotronInterval(1.0, 4.0, 3),)

    class Community:
        def __init__(self, model_dir, vulkan_device):
            calls["secondary"] = (model_dir, vulkan_device)

        def diarize(self, samples, count, *, check_cancelled):
            calls["count"] = count
            return (CommunityInterval(2.0, 5.0, "a"),)

    monkeypatch.setattr(application, "NemoSpeechAdapter", Nemo)
    monkeypatch.setattr(application, "Community1Diarizer", Community)
    service = application.build_diarization_service()
    samples = np.zeros(1, dtype=np.float32)
    assert service.nemotron(samples, -1).activity[0].speaker_id == 3
    assert calls["signatures"] is NATIVE_SIGNATURES
    assert calls["gpu_index"] == -1
    assert calls["make_model_config"]("/model", -1).preset == b"v3-offline"
    array = calls["make_segment_array"](1)
    array[0].start_time, array[0].end_time, array[0].speaker = 1.0, 2.0, 3
    assert calls["copy_segments"](array, 1) == ((1.0, 2.0, 3),)
    assert service.community1(samples, 2, 4).activity[0].speaker_id == "a"
    assert calls["count"] == 2
    assert calls["secondary"][1] == 4
    assert calls["secondary"][0].is_absolute()
    document = decode_diarization(service.encode_result((SampleSpeakerActivity(3, 1, 2),)))
    assert document.intervals[0].speaker_id == 3


def test_solver_is_lazy_maximizes_matrix_and_returns_python_integer_pairs(monkeypatch) -> None:
    calls = []

    def solve(matrix, *, maximize):
        calls.append((matrix, maximize))
        return np.array([0]), np.array([1])

    monkeypatch.setattr(
        application,
        "import_module",
        lambda name: calls.append(name) or SimpleNamespace(linear_sum_assignment=solve),
    )
    service = application.build_diarization_service()
    assert calls == []
    assert tuple(service.solver(((1.0, 2.0),))) == ((0, 1),)
    assert calls == ["scipy.optimize", (((1.0, 2.0),), True)]


def test_skips_do_not_load_optional_modules_or_construct_unused_adapters(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import builtins
    from unittest.mock import Mock

    from tests.support.diarization import make_diarization_manifest, make_diarization_task_directory
    from transcriber.protocol.diarization_cli import (
        DiarizationCommand,
        DiarizationFailure,
        DiarizationSuccess,
    )

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert name.split(".")[0] not in {
            "scipy",
            "diarization",
            "ncnn",
            "soundfile",
            "kaldi_native_fbank",
        }
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    forbidden = Mock(side_effect=AssertionError("optional capability must stay unused"))
    monkeypatch.setattr(application, "import_module", forbidden)
    monkeypatch.setattr(application, "Community1Diarizer", forbidden)
    nemo = Mock()
    monkeypatch.setattr(application, "NemoSpeechAdapter", nemo)
    for index, intervals in enumerate(((), ((0, 4),))):
        directory = tmp_path / str(index)
        directory.mkdir()
        root = make_diarization_task_directory(
            directory, make_diarization_manifest(4, intervals), [0] * 4
        )
        for prediction in ((), (NemotronInterval(0.0, 1.0, 7),)):
            nemo.return_value.diarize.return_value = prediction
            warning = Mock()
            service = application.build_diarization_service(warning=warning)
            assert isinstance(service.diarize(DiarizationCommand(root)), DiarizationSuccess)
            warning.assert_not_called()
        if not intervals:
            nemo.assert_not_called()
        # Common WAV validation still runs on both skip branches.
        (root / "prepared.wav").write_bytes(b"invalid")
        result = service.diarize(DiarizationCommand(root))
        assert isinstance(result, DiarizationFailure) and result.stage == "validate"
    forbidden.assert_not_called()


def test_secondary_missing_solver_is_recoverable_before_model_creation(monkeypatch) -> None:
    import pytest

    from transcriber.infrastructure import diarization_prerequisites
    from transcriber.infrastructure.diarization_provider import RecoverableDiarizationFailure

    monkeypatch.setattr(Path, "is_file", lambda _: True)

    def load(name):
        if name == "scipy.optimize":
            raise ModuleNotFoundError("scipy missing")
        return SimpleNamespace(Diarizer=lambda: None, close_vulkan=lambda: None)

    monkeypatch.setattr(diarization_prerequisites.importlib, "import_module", load)
    service = application.build_diarization_service()
    with pytest.raises(RecoverableDiarizationFailure, match="scipy missing"):
        service.community1(np.zeros(1, dtype=np.float32), 2, 0)


def test_secondary_firstparty_mapping_failure_is_not_recoverable(monkeypatch) -> None:
    import pytest

    class Community:
        def __init__(self, *_):
            pass

        def diarize(self, *_, **kwargs):
            return (CommunityInterval(0.0, 1.0, "a"),)

    def broken_mapping(*_):
        raise ValueError("firstparty mapping")

    monkeypatch.setattr(application, "Community1Diarizer", Community)
    monkeypatch.setattr(application, "SpeakerActivity", broken_mapping)
    with pytest.raises(ValueError, match="firstparty mapping"):
        application.build_diarization_service().community1(np.zeros(1, dtype=np.float32), 2, 0)
