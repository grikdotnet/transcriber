import importlib
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from transcriber.infrastructure.diarization_prerequisites import (
    COMMUNITY_MODEL_FILES, check_community_prerequisites, check_vulkan_device,
)
from transcriber.infrastructure.diarization_provider import RecoverableDiarizationFailure


@pytest.fixture
def prerequisites(tmp_path, monkeypatch):
    for filename in COMMUNITY_MODEL_FILES:
        (tmp_path / filename).write_bytes(b'asset')
    modules = {
        'diarization.pipeline': SimpleNamespace(Diarizer=Mock()),
        'diarization.models': SimpleNamespace(close_vulkan=Mock()),
        'ncnn': SimpleNamespace(get_gpu_count=Mock(return_value=1),
            Net=SimpleNamespace(set_vulkan_device=Mock())),
        'scipy.optimize': SimpleNamespace(linear_sum_assignment=Mock()),
    }
    monkeypatch.setattr(importlib, 'import_module', lambda name: modules[name])
    return tmp_path, modules


def test_module_import_does_not_load_optional_dependencies():
    script = '''import sys
import transcriber.infrastructure.diarization_prerequisites
assert not any(name in sys.modules for name in ('ncnn', 'diarization.pipeline', 'scipy.optimize'))
'''
    subprocess.run([sys.executable, '-c', script], check=True)


def test_returns_lazy_capabilities_without_touching_vulkan(prerequisites):
    path, modules = prerequisites
    result = check_community_prerequisites(path)
    assert result.diarizer_factory is modules['diarization.pipeline'].Diarizer
    assert result.assignment_solver is modules['scipy.optimize'].linear_sum_assignment
    assert result.close_vulkan is modules['diarization.models'].close_vulkan
    modules['ncnn'].get_gpu_count.assert_not_called()


@pytest.mark.parametrize('filename', COMMUNITY_MODEL_FILES)
def test_each_of_eight_assets_is_required(prerequisites, filename):
    path, _ = prerequisites
    (path / filename).unlink()
    with pytest.raises(RecoverableDiarizationFailure, match=filename):
        check_community_prerequisites(path)


@pytest.mark.parametrize('module', ['diarization.pipeline', 'diarization.models', 'ncnn', 'scipy.optimize'])
def test_unloadable_modules_are_recoverable(prerequisites, monkeypatch, module):
    path, modules = prerequisites
    def load(name):
        if name == module:
            raise ImportError('damaged runtime')
        return modules[name]
    monkeypatch.setattr(importlib, 'import_module', load)
    with pytest.raises(RecoverableDiarizationFailure, match='damaged runtime'):
        check_community_prerequisites(path)


@pytest.mark.parametrize('count,index', [(0, 0), (1, 1), (1, -1)])
def test_missing_or_invalid_vulkan_device_is_recoverable(prerequisites, count, index):
    _, modules = prerequisites
    modules['ncnn'].get_gpu_count.return_value = count
    with pytest.raises(RecoverableDiarizationFailure):
        check_vulkan_device(modules['ncnn'], index)


def test_vulkan_check_accepts_selected_device_and_classifies_binding_failure(prerequisites):
    _, modules = prerequisites
    check_vulkan_device(modules['ncnn'], 0)
    with pytest.raises(RecoverableDiarizationFailure):
        check_vulkan_device(SimpleNamespace(), 0)
    modules['ncnn'].get_gpu_count.side_effect = RuntimeError('driver failed')
    with pytest.raises(RecoverableDiarizationFailure, match='driver failed'):
        check_vulkan_device(modules['ncnn'], 0)


def test_cancellation_is_never_translated_to_recoverable(prerequisites, monkeypatch):
    path, _ = prerequisites
    monkeypatch.setattr(importlib, 'import_module', Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        check_community_prerequisites(path)
