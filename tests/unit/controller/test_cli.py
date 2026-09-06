from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from transcriber.controller import cli
from transcriber.protocol.cli import (
    FAILURE_STAGES,
    PrepareCommand,
    PrepareFailure,
    PrepareSuccess,
)


class StubApplication:
    def __init__(self, result: PrepareSuccess | PrepareFailure) -> None:
        self.result = result
        self.commands: list[PrepareCommand] = []

    def prepare(self, command: PrepareCommand) -> PrepareSuccess | PrepareFailure:
        self.commands.append(command)
        return self.result


def _success(task_directory: Path) -> PrepareSuccess:
    return PrepareSuccess(
        task_work_directory=task_directory,
        canonical_audio=task_directory / "prepared.wav",
        manifest=task_directory / "manifest.json",
        segment_count=2,
    )


def _install_application(
    monkeypatch: pytest.MonkeyPatch,
    application: StubApplication,
) -> None:
    monkeypatch.setattr(cli, "build_application", lambda: application, raising=False)


def test_main_resolves_paths_from_non_repository_cwd_and_uses_default_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    task_directory = tmp_path / "relative-task"
    application = StubApplication(_success(task_directory))
    _install_application(monkeypatch, application)

    status = cli.main(["relative-source.wav", "relative-task"])

    assert status == 0
    assert application.commands == [
        PrepareCommand(
            source_media=tmp_path / "relative-source.wav",
            task_work_directory=task_directory,
            split_target_seconds=30.0,
        )
    ]
    captured = capsys.readouterr()
    assert captured.out == (
        f"task_work_directory={task_directory}\n"
        f"canonical_audio={task_directory / 'prepared.wav'}\n"
        f"manifest={task_directory / 'manifest.json'}\n"
        "segment_count=2\n"
    )
    assert captured.err == ""


def test_main_passes_the_custom_split_target_through_protocol_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_directory = tmp_path / "task"
    application = StubApplication(_success(task_directory))
    _install_application(monkeypatch, application)

    status = cli.main(
        [
            str(tmp_path / "source.wav"),
            str(task_directory),
            "--max-segment-duration-seconds",
            "30.009",
        ]
    )

    assert status == 0
    assert len(application.commands) == 1
    assert application.commands[0].split_target_seconds == 30.009
    assert application.commands[0].split_target_frames == 3_000
    capsys.readouterr()


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "0.009", "0", "-1", "not-a-number"])
def test_argument_failure_returns_status_two_before_application_is_built(
    value: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_directory = tmp_path / "must-not-exist"
    build_calls: list[None] = []

    def unexpected_build() -> StubApplication:
        build_calls.append(None)
        raise AssertionError("argument validation must precede application construction")

    monkeypatch.setattr(cli, "build_application", unexpected_build, raising=False)

    status = cli.main(
        [
            str(tmp_path / "source.wav"),
            str(task_directory),
            "--max-segment-duration-seconds",
            value,
        ]
    )

    captured = capsys.readouterr()
    assert status == 2
    assert captured.out == ""
    assert "usage:" in captured.err
    assert "--max-segment-duration-seconds" in captured.err
    assert "Traceback" not in captured.err
    assert build_calls == []
    assert not task_directory.exists()


@pytest.mark.parametrize("stage", sorted(FAILURE_STAGES))
def test_runtime_failure_renders_one_stage_specific_line_and_status_one(
    stage: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    application = StubApplication(
        PrepareFailure(
            stage=stage,  # type: ignore[arg-type]
            message=f"operation failed for {tmp_path / 'relevant-asset'}",
        )
    )
    _install_application(monkeypatch, application)

    status = cli.main([str(tmp_path / "source.wav"), str(tmp_path / "task")])

    captured = capsys.readouterr()
    assert status == 1
    assert captured.out == ""
    assert captured.err == (
        f"ERROR [{stage}]: operation failed for {tmp_path / 'relevant-asset'}\n"
    )
    assert "Traceback" not in captured.err
    assert len(application.commands) == 1


def test_runtime_failure_discards_raw_traceback_and_bounds_external_detail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    relevant_asset = tmp_path / "model.param"
    raw_detail = (
        f"could not load {relevant_asset}\n"
        "Traceback (most recent call last):\n"
        '  File "native-wrapper.py", line 99, in invoke\n'
        "X" * 10_000
    )
    application = StubApplication(PrepareFailure(stage="firered-model", message=raw_detail))
    _install_application(monkeypatch, application)

    status = cli.main([str(tmp_path / "source.wav"), str(tmp_path / "task")])

    captured = capsys.readouterr()
    assert status == 1
    assert captured.out == ""
    assert captured.err.startswith(f"ERROR [firered-model]: could not load {relevant_asset}")
    assert captured.err.endswith("\n")
    assert captured.err.count("\n") == 1
    assert "Traceback" not in captured.err
    assert "native-wrapper.py" not in captured.err
    assert len(captured.err) <= 1_024


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["source.wav"],
        ["source.wav", "task", "unexpected"],
        ["source.wav", "task", "--unknown-option"],
    ],
)
def test_usage_errors_return_status_two_without_a_traceback(
    arguments: Sequence[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    build_calls: list[None] = []

    def unexpected_build() -> StubApplication:
        build_calls.append(None)
        raise AssertionError("usage errors must not build the application")

    monkeypatch.setattr(cli, "build_application", unexpected_build, raising=False)

    status = cli.main(arguments)

    captured = capsys.readouterr()
    assert status == 2
    assert captured.out == ""
    assert "usage:" in captured.err
    assert "transcriber-prepare" in captured.err
    assert "Traceback" not in captured.err
    assert build_calls == []
