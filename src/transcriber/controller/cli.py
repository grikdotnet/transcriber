"""Command-line boundary for local media preparation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from transcriber.composition.application import build_application
from transcriber.protocol.cli import PrepareCommand, PrepareFailure, PrepareSuccess


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="transcriber-prepare")
    parser.add_argument("source_media", metavar="SOURCE_MEDIA")
    parser.add_argument("task_work_directory", metavar="TASK_WORK_DIRECTORY")
    parser.add_argument(
        "--max-segment-duration-seconds",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help="advisory FireRedVAD split target (default: 30.0)",
    )
    return parser


def _parse_command(arguments: Sequence[str] | None) -> tuple[PrepareCommand | None, int]:
    parser = _parser()
    try:
        namespace = parser.parse_args(arguments)
        command = PrepareCommand(
            source_media=Path(namespace.source_media).resolve(),
            task_work_directory=Path(namespace.task_work_directory).resolve(),
            split_target_seconds=namespace.max_segment_duration_seconds,
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


def _render_success(result: PrepareSuccess) -> None:
    sys.stdout.write(
        f"task_work_directory={result.task_work_directory}\n"
        f"canonical_audio={result.canonical_audio}\n"
        f"manifest={result.manifest}\n"
        f"segment_count={result.segment_count}\n"
    )


def _render_failure(result: PrepareFailure) -> None:
    prefix = f"ERROR [{result.stage}]: "
    first_line = result.message.splitlines()[0].strip()
    maximum_message_length = 1_023 - len(prefix)
    sys.stderr.write(prefix + first_line[:maximum_message_length] + "\n")


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the CLI and return its documented process status."""
    command, status = _parse_command(arguments)
    if command is None:
        return status

    result = build_application().prepare(command)
    if isinstance(result, PrepareSuccess):
        _render_success(result)
        return 0
    _render_failure(result)
    return 1
