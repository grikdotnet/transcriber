"""Command-line boundary for independent Diarization Tasks (Controller)."""
import argparse
from collections.abc import Sequence
from pathlib import Path

from transcriber.composition.application import build_application
from transcriber.protocol.diarization_cli import (
    DiarizationCommand,
    DiarizationFailure,
    DiarizationProgress,
    DiarizationWarning,
)


def _render_progress(progress: DiarizationProgress) -> None:
    print(f"stage={progress.stage}", flush=True)


def _diagnostic(value: str) -> str:
    return " ".join(value.splitlines())


def _render_warning(warning: DiarizationWarning) -> None:
    import sys

    print(f"WARNING [community1]: {_diagnostic(warning.reason)}; "
          "using Nemotron-only diarization", file=sys.stderr, flush=True)


def _render_failure(failure: DiarizationFailure) -> None:
    import sys

    print(f"ERROR [{failure.stage}]: {_diagnostic(failure.message)}",
          file=sys.stderr, flush=True)


def main(arguments: Sequence[str] | None = None) -> int:
    """Parse a command, invoke Composition, and render the public CLI contract."""
    parser = argparse.ArgumentParser(prog="transcriber-diarize", allow_abbrev=False)
    parser.add_argument("task_work_directory", metavar="TASK_WORK_DIRECTORY")
    parser.add_argument("--nemo-gpu-index", type=int, default=0, metavar="INDEX")
    parser.add_argument("--vulkan-gpu-index", type=int, default=0, metavar="INDEX")
    try:
        namespace = parser.parse_args(arguments)
        try:
            command = DiarizationCommand(
                Path(namespace.task_work_directory),
                namespace.nemo_gpu_index, namespace.vulkan_gpu_index,
            )
        except ValueError as error:
            parser.error(str(error))
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    try:
        command = DiarizationCommand(
            command.task_work_directory.resolve(), command.nemo_gpu_index, command.vulkan_gpu_index,
        )
    except (OSError, RuntimeError, ValueError) as error:
        _render_failure(DiarizationFailure("validate", str(error)))
        return 1
    try:
        application = build_application(
            diarization_progress=_render_progress, diarization_warning=_render_warning,
        )
        result = application.diarize(command)
    except KeyboardInterrupt:
        result = DiarizationFailure("cancelled", "Diarization cancelled")
    if isinstance(result, DiarizationFailure):
        _render_failure(result)
        return 1
    print(f"diarization={result.diarization.resolve()}", flush=True)
    return 0
