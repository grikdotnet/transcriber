from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_project_declares_the_independent_asr_console_entry_point() -> None:
    metadata = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["scripts"]["transcriber-asr"] == (
        "transcriber.controller.asr_cli:main"
    )


def test_asr_controller_stays_outside_infrastructure_and_preparation() -> None:
    source = REPOSITORY_ROOT / "src" / "transcriber" / "controller" / "asr_cli.py"

    text = source.read_text(encoding="utf-8")

    assert "transcriber.infrastructure" not in text
    assert "Prepare" not in text
    assert "model-list" not in text


def test_asr_controller_contract_uses_protocol_failure_values_and_managed_signals() -> None:
    source = REPOSITORY_ROOT / "src" / "transcriber" / "controller" / "asr_cli.py"

    text = source.read_text(encoding="utf-8")

    assert "AsrFailure" in text
    assert "SIGINT" in text
    assert "SIGTERM" in text
    assert re.search(r"json\.dumps\(", text) is not None
