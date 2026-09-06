from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _entry_point() -> Path:
    executable = shutil.which("transcriber-prepare")
    assert executable is not None, (
        "transcriber-prepare must be installed by the project environment"
    )
    return Path(executable).resolve()


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["only-source.wav"],
        ["source.wav", "task", "--max-segment-duration-seconds", "nan"],
        ["source.wav", "task", "--max-segment-duration-seconds", "0.009"],
        ["source.wav", "task", "--unknown-option"],
    ],
)
def test_installed_cli_reports_usage_errors_from_non_repository_cwd(
    arguments: list[str],
    tmp_path: Path,
) -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [_entry_point(), *arguments],
        cwd=tmp_path,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "usage:" in completed.stderr
    assert "transcriber-prepare" in completed.stderr
    assert "Traceback" not in completed.stderr
    assert not (tmp_path / "task").exists()


def test_controller_source_keeps_cli_boundary_out_of_infrastructure() -> None:
    source = REPOSITORY_ROOT / "src" / "transcriber" / "controller" / "cli.py"

    text = source.read_text(encoding="utf-8")

    assert "transcriber.infrastructure" not in text
