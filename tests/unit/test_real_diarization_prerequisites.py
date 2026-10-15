"""Policy tests; runtime asset/import checks remain owned by Infrastructure."""

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from tests.conftest import enforce_real_diarization_available


@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize("detail", ["missing model", "no Vulkan device", "native load failed"])
def test_unavailable_real_diarization_has_explicit_policy(required: bool, detail: str) -> None:
    outcome = pytest.fail.Exception if required else pytest.skip.Exception
    with pytest.raises(outcome, match=detail):
        enforce_real_diarization_available(detail, required=required)


def test_available_checkpoint_proceeds() -> None:
    enforce_real_diarization_available(None, required=True)
    enforce_real_diarization_available(None, required=False)


def test_real_diarization_option_is_registered(pytestconfig: pytest.Config) -> None:
    assert isinstance(pytestconfig.getoption("--real-diarization-required"), bool)


@pytest.mark.parametrize("engine", ["nemo_speech", "pyannote"])
def test_checkpoint_rejects_bypassing_actual_adapter(
    engine: str,
    monkeypatch: pytest.MonkeyPatch,
    pytestconfig: pytest.Config,
) -> None:
    from importlib import import_module

    from transcriber.domain.diarization import CommunityPrediction, NemotronPrediction

    module = import_module(f"tests.integration.infrastructure.test_{engine}")

    def bypass(*args: Any) -> Any:
        return NemotronPrediction(()) if engine == "nemo_speech" else CommunityPrediction(())

    monkeypatch.setattr(
        module,
        "build_diarization_service",
        lambda: SimpleNamespace(
            nemotron=bypass,
            community1=bypass,
        ),
    )
    monkeypatch.setattr(module, "enforce_real_diarization_available", lambda *args, **kwargs: None)
    checkpoint = (
        module.test_real_nemotron_adapter_and_composition_mapping
        if engine == "nemo_speech"
        else module.test_real_community_adapter_and_composition_mapping
    )
    with pytest.raises(AssertionError, match="actual adapter must complete"):
        checkpoint(np.zeros(160, dtype=np.float32), pytestconfig)
