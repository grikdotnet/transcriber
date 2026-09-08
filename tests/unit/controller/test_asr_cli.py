from __future__ import annotations

import json
import signal
from pathlib import Path

import pytest

from transcriber.composition.application import Application
from transcriber.controller import asr_cli
from transcriber.protocol.asr_cli import AsrCommand, AsrFailure, AsrProgress, AsrSuccess
from transcriber.protocol.asr_model_manifest import AsrModelCapabilities


class StubApplication:
    def __init__(self, result: AsrSuccess | AsrFailure) -> None:
        self.result = result
        self.commands: list[AsrCommand] = []
        self.progress: object | None = None

    def recognize(self, command: AsrCommand) -> AsrSuccess | AsrFailure:
        self.commands.append(command)
        if self.progress is not None and isinstance(self.result, AsrSuccess):
            for recognized_segments in range(1, self.result.recognized_segments + 1):
                self.progress(  # type: ignore[operator]
                    AsrProgress(
                        recognized_segments=recognized_segments,
                        total_segments=self.result.recognized_segments,
                    )
                )
        return self.result


def _install_application(monkeypatch: pytest.MonkeyPatch, application: StubApplication) -> None:
    def build(*, progress: object) -> StubApplication:
        application.progress = progress
        return application

    monkeypatch.setattr(asr_cli, "build_application", build)


def test_main_resolves_task_path_invokes_application_and_renders_progress_and_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    transcript = tmp_path / "task" / "transcripts-qwen3-asr-1.7b" / "transcript.txt"
    application = StubApplication(AsrSuccess(transcript=transcript, recognized_segments=2))
    _install_application(monkeypatch, application)

    status = asr_cli.main(["task", "--model", "qwen3-asr-1.7b"])

    assert status == 0
    assert application.commands == [
        AsrCommand(
            task_work_directory=tmp_path / "task",
            model_id="qwen3-asr-1.7b",
            language="auto",
        )
    ]
    assert capsys.readouterr() == (
        "recognized_segments=1 total_segments=2\n"
        "recognized_segments=2 total_segments=2\n"
        f"transcript={transcript}\n",
        "",
    )


@pytest.mark.parametrize(
    "model_id",
    ["Qwen3-asr", "qwen3--asr", "qwen3..asr", "qwen3-.asr", ".qwen3", "qwen3-"],
)
def test_invalid_model_id_returns_status_two_before_application_resolution(
    model_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    build_calls: list[None] = []

    def unexpected_build() -> StubApplication:
        build_calls.append(None)
        raise AssertionError("invalid model IDs must not resolve the application")

    monkeypatch.setattr(asr_cli, "build_application", unexpected_build)

    assert asr_cli.main([str(tmp_path / "task"), "--model", model_id]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "usage:" in captured.err
    assert build_calls == []


def test_syntactically_valid_unregistered_model_reaches_application_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class UnregisteredApplication:
        def recognize(self, command: AsrCommand) -> AsrSuccess:
            assert command.model_id == "another.asr-model"
            raise ValueError("unregistered ASR Model: another.asr-model")

    monkeypatch.setattr(asr_cli, "build_application", lambda **_: UnregisteredApplication())

    assert asr_cli.main([str(tmp_path / "task"), "--model", "another.asr-model"]) == 1
    assert capsys.readouterr().out == ""


def test_progress_renderer_has_the_exact_public_shape(
    capsys: pytest.CaptureFixture[str],
) -> None:
    asr_cli._render_progress(AsrProgress(recognized_segments=3, total_segments=10))

    assert capsys.readouterr() == ("recognized_segments=3 total_segments=10\n", "")


def test_main_passes_an_explicit_valid_language_to_the_application(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    transcript = tmp_path / "task" / "transcripts-qwen3-asr-1.7b" / "transcript.txt"
    application = StubApplication(AsrSuccess(transcript=transcript, recognized_segments=1))
    _install_application(monkeypatch, application)

    assert (
        asr_cli.main(
            [
                str(tmp_path / "task"),
                "--model",
                "qwen3-asr-1.7b",
                "--language",
                "en-GB",
            ]
        )
        == 0
    )

    assert application.commands[0].language == "en-GB"
    capsys.readouterr()


@pytest.mark.parametrize(
    "language",
    [
        "a",
        "englishxx",
        "en-",
        "en-123456789",
        "en_GB",
        "x-private",
        "i-klingon",
    ],
)
def test_invalid_language_returns_status_two_before_application_resolution(
    language: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    build_calls: list[None] = []

    def unexpected_build() -> StubApplication:
        build_calls.append(None)
        raise AssertionError("invalid languages must not resolve the application")

    monkeypatch.setattr(asr_cli, "build_application", unexpected_build)

    assert (
        asr_cli.main(
            [str(tmp_path / "task"), "--model", "qwen3-asr", "--language", language]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "usage:" in captured.err
    assert build_calls == []


@pytest.mark.parametrize(
    "language",
    ("ab", "AbCdEfGh", "en-a", "en-12345678", "abcdefgh-1-ABCDEFGH"),
)
def test_complete_supported_language_tag_grammar_reaches_application_resolution(
    language: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    transcript = tmp_path / "task" / "transcript.txt"
    application = StubApplication(AsrSuccess(transcript=transcript, recognized_segments=1))
    _install_application(monkeypatch, application)

    assert (
        asr_cli.main(
            [str(tmp_path / "task"), "--model", "qwen3-asr", "--language", language]
        )
        == 0
    )

    assert application.commands[0].language == language
    capsys.readouterr()


def test_required_model_automatic_language_returns_two_before_task_or_provider_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class UnexpectedAsrService:
        def recognize(self, command: AsrCommand) -> AsrSuccess:
            raise AssertionError(f"service work must not begin: {command}")

    application = Application(
        service=object(),  # type: ignore[arg-type]
        asr_service=UnexpectedAsrService(),  # type: ignore[arg-type]
        asr_model_id="qwen3-asr-1.7b",
        asr_capabilities=AsrModelCapabilities(context=True, language="required"),
    )
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: application)

    assert asr_cli.main([str(tmp_path / "task"), "--model", "qwen3-asr-1.7b"]) == 2

    assert capsys.readouterr() == ("", "")


def test_runtime_failure_renders_json_escaped_model_message_and_segment_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    application = StubApplication(
        AsrFailure(
            stage="execution-provider",
            message='connection failed at "loopback"\\nprivate log',
            model_id="qwen3-asr-1.7b",
            segment_index=3,
            provider_diagnostic='bad "response"\\nprivate\\x00detail',
        )
    )
    _install_application(monkeypatch, application)

    status = asr_cli.main([str(tmp_path / "task"), "--model", "qwen3-asr-1.7b"])

    assert status == 1
    assert capsys.readouterr() == (
        "",
        'ERROR [execution-provider] model="qwen3-asr-1.7b" segment=3: '
        'connection failed at \\"loopback\\"\\\\nprivate log: '
        'provider said "bad \\"response\\"\\\\nprivate\\\\x00detail"\n',
    )


def test_failure_truncation_is_bounded_and_keeps_quoted_diagnostic_well_formed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    application = StubApplication(
        AsrFailure(
            stage="provider-response",
            message="provider response failed",
            model_id="qwen3-asr-1.7b",
            segment_index=0,
            provider_diagnostic="x" * 2_000,
        )
    )
    _install_application(monkeypatch, application)

    assert asr_cli.main([str(tmp_path / "task"), "--model", "qwen3-asr-1.7b"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.removesuffix("\n")) <= 1_023
    assert captured.err.endswith('...[truncated]"\n')


@pytest.mark.parametrize(
    "diagnostic",
    (
        'quote " backslash \\ control \x00 newline\nnon-ASCII é' * 80,
        '"\\\x00é' * 300,
    ),
)
def test_failure_reserves_a_complete_json_quoted_diagnostic_when_earlier_fields_exhaust_budget(
    diagnostic: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    application = StubApplication(
        AsrFailure(
            stage="execution-provider",
            message=('message with " quote, backslash \\, control \x00, and é ' * 100),
            model_id="a" * 2_000,
            segment_index=0,
            provider_diagnostic=diagnostic,
        )
    )
    _install_application(monkeypatch, application)

    assert asr_cli.main([str(tmp_path / "task"), "--model", "qwen3-asr-1.7b"]) == 1

    line = capsys.readouterr().err.removesuffix("\n")
    rendered_diagnostic = line.rsplit("provider said ", maxsplit=1)[1]
    assert len(line) <= 1_023
    assert rendered_diagnostic.endswith('...[truncated]"')
    assert json.loads(rendered_diagnostic).endswith("...[truncated]")


@pytest.mark.parametrize("message_length", (1_022, 1_023, 1_024))
def test_no_diagnostic_failure_keeps_fixed_syntax_with_long_model_and_hostile_message(
    message_length: int,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = AsrFailure(
        stage="asr-model",
        model_id="a" * 2_000,
        message=('"\\\x00é' * message_length),
    )

    asr_cli._render_failure(result)

    line = capsys.readouterr().err.removesuffix("\n")
    model_text, rendered_message = line.split(": ", maxsplit=1)
    rendered_model = model_text.removeprefix("ERROR [asr-model] model=")
    assert len(line) <= 1_023
    assert json.loads(rendered_model).endswith("...[truncated]")
    assert rendered_message.endswith("...[truncated]")
    assert not line.endswith(": ")


def test_failure_never_forwards_provider_logs_or_success_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    application = StubApplication(
        AsrFailure(
            stage="execution-provider",
            message="provider startup failed",
            model_id="qwen3-asr-1.7b",
            provider_diagnostic="private provider log",
        )
    )
    _install_application(monkeypatch, application)

    assert asr_cli.main([str(tmp_path / "task"), "--model", "qwen3-asr-1.7b"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "transcript=" not in captured.out
    assert "private provider log" in captured.err
    assert "ERROR" in captured.err


@pytest.mark.parametrize("handled_signal", (signal.SIGINT, signal.SIGTERM))
def test_handled_signal_reaches_application_cleanup_and_returns_cancelled_status(
    handled_signal: signal.Signals,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    handlers: dict[signal.Signals, object] = {}
    cleaned_up = False

    class SignalApplication:
        def recognize(self, command: AsrCommand) -> AsrSuccess | AsrFailure:
            nonlocal cleaned_up
            try:
                handler = handlers[handled_signal]
                assert callable(handler)
                handler(handled_signal, None)
            except KeyboardInterrupt:
                return AsrFailure(
                    stage="cancelled", message="task cancelled", model_id=command.model_id
                )
            finally:
                cleaned_up = True

    def install_handler(signum: signal.Signals, handler: object) -> object:
        handlers[signum] = handler
        return signal.SIG_DFL

    monkeypatch.setattr(asr_cli.signal, "signal", install_handler)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: SignalApplication())

    assert asr_cli.main([str(tmp_path / "task"), "--model", "qwen3-asr-1.7b"]) == 1

    assert cleaned_up is True
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == 'ERROR [cancelled] model="qwen3-asr-1.7b": task cancelled\n'
