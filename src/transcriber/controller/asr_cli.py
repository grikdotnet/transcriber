"""Command-line boundary for independent ASR tasks."""

from __future__ import annotations

import argparse
import json
import signal
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import FrameType

from transcriber.composition.application import RequiredAsrLanguageError, build_application
from transcriber.protocol.asr_cli import AsrCommand, AsrFailure, AsrProgress, AsrSuccess

type PreviousSignalHandler = Callable[[int, FrameType | None], object] | int | None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="transcriber-asr")
    parser.add_argument("task_work_directory", metavar="TASK_WORK_DIRECTORY")
    parser.add_argument("--model", required=True, metavar="MODEL_ID")
    parser.add_argument("--language", default="auto", metavar="auto|LANGUAGE_TAG")
    return parser


def _parse_command(arguments: Sequence[str] | None) -> tuple[AsrCommand | None, int]:
    parser = _parser()
    try:
        namespace = parser.parse_args(arguments)
        command = AsrCommand(
            task_work_directory=Path(namespace.task_work_directory).resolve(),
            model_id=namespace.model,
            language=namespace.language,
        )
    except SystemExit as error:
        return None, _system_exit_status(error)
    except (TypeError, ValueError) as error:
        return None, _argument_error_status(parser, str(error))
    return command, 0


def _system_exit_status(error: SystemExit) -> int:
    return error.code if isinstance(error.code, int) else 2


def _argument_error_status(parser: argparse.ArgumentParser, message: str) -> int:
    try:
        parser.error(message)
    except SystemExit as error:
        return _system_exit_status(error)


def _render_progress(progress: AsrProgress) -> None:
    sys.stdout.write(
        f"recognized_segments={progress.recognized_segments} "
        f"total_segments={progress.total_segments}\n"
    )


def _render_success(result: AsrSuccess) -> None:
    sys.stdout.write(f"transcript={result.transcript}\n")


def _render_failure(result: AsrFailure) -> None:
    """Render one bounded, escaped public ASR failure without provider-log forwarding."""
    prefix = f"ERROR [{result.stage}] model="
    segment = "" if result.segment_index is None else f" segment={result.segment_index}"
    message_separator = ": "
    diagnostic_separator = ": provider said "
    if result.provider_diagnostic is None:
        fixed_length = len(prefix) + len(segment) + len(message_separator)
        available_length = 1_023 - fixed_length
        minimum_message = json.dumps("...[truncated]")[1:-1]
        model = json.dumps(result.model_id)
        message = json.dumps(result.message)[1:-1]
        if len(model) + len(message) > available_length:
            model_budget = available_length - len(minimum_message)
            if len(model) > model_budget:
                model = _truncate_json_string(result.model_id, model_budget)
            message = _truncate_json_content(result.message, available_length - len(model))
        else:
            message = json.dumps(result.message)[1:-1]
        sys.stderr.write(prefix + model + segment + message_separator + message + "\n")
        return

    minimum_diagnostic = json.dumps("...[truncated]")
    model = json.dumps(result.model_id)
    message = json.dumps(result.message)[1:-1]
    fixed_length = len(prefix) + len(segment) + len(message_separator) + len(diagnostic_separator)
    message_budget = 1_023 - fixed_length - len(model) - len(minimum_diagnostic)
    if message_budget < 0:
        message = ""
        model_budget = 1_023 - fixed_length - len(message) - len(minimum_diagnostic)
        model = _truncate_json_string(result.model_id, model_budget)
    else:
        message = _truncate_json_content(result.message, message_budget)
    diagnostic_budget = 1_023 - fixed_length - len(model) - len(message)
    diagnostic = _truncate_json_string(result.provider_diagnostic, diagnostic_budget)
    sys.stderr.write(
        prefix
        + model
        + segment
        + message_separator
        + message
        + diagnostic_separator
        + diagnostic
        + "\n"
    )


def _truncate_json_string(value: str, maximum_length: int) -> str:
    """Render one JSON string within a bound, preserving its enclosing quotes after truncation."""
    rendered = json.dumps(value)
    if len(rendered) <= maximum_length:
        return rendered
    marker = "...[truncated]"
    low = 0
    high = len(value)
    best = json.dumps("")
    while low <= high:
        midpoint = (low + high) // 2
        candidate = json.dumps(value[:midpoint] + marker)
        if len(candidate) <= maximum_length:
            best = candidate
            low = midpoint + 1
        else:
            high = midpoint - 1
    return best


def _truncate_json_content(value: str, maximum_length: int) -> str:
    """Render escaped JSON string content within a bound without splitting an escape sequence."""
    rendered = json.dumps(value)[1:-1]
    if len(rendered) <= maximum_length:
        return rendered
    marker = "...[truncated]"
    low = 0
    high = len(value)
    best = ""
    while low <= high:
        midpoint = (low + high) // 2
        candidate = json.dumps(value[:midpoint] + marker)[1:-1]
        if len(candidate) <= maximum_length:
            best = candidate
            low = midpoint + 1
        else:
            high = midpoint - 1
    return best


def _raise_keyboard_interrupt(signum: int, frame: FrameType | None) -> None:
    """Turn termination signals into cancellation so the Service can stop its provider."""
    del signum, frame
    raise KeyboardInterrupt


def _install_cancellation_handlers() -> tuple[PreviousSignalHandler, PreviousSignalHandler]:
    return (
        signal.signal(signal.SIGINT, _raise_keyboard_interrupt),
        signal.signal(signal.SIGTERM, _raise_keyboard_interrupt),
    )


def _restore_cancellation_handlers(
    previous: tuple[PreviousSignalHandler, PreviousSignalHandler],
) -> None:
    signal.signal(signal.SIGINT, previous[0])
    signal.signal(signal.SIGTERM, previous[1])


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the independent ASR CLI and return its documented process status."""
    command, status = _parse_command(arguments)
    if command is None:
        return status

    application = build_application(progress=_render_progress)
    previous_handlers = _install_cancellation_handlers()
    try:
        result = application.recognize(command)
    except RequiredAsrLanguageError:
        return 2
    except ValueError:
        return 1
    finally:
        _restore_cancellation_handlers(previous_handlers)
    if isinstance(result, AsrFailure):
        _render_failure(result)
        return 1
    _render_success(result)
    return 0
