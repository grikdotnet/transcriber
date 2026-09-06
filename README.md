# transcriber

Local command-line middleware that extracts one audio stream from a media file with the bundled `vendor/ffmpeg`, runs the local non-streaming FireRedVAD NCNN provider, and writes a manifest plus speech-focused WAV segments.

This delivery supports the CLI only. It does not provide a GUI, API, worker mode, transcription, speaker diarization, or model downloading.

## Requirements

- Python 3.12 and `uv`
- the bundled `vendor/ffmpeg`
- a host-built `vendor/firered-vad-ncnn`
- FireRedVAD model and CMVN assets in `models/firered-vad.ncnn/`

The native provider build requires a local static NCNN `20260113` installation. See the [quickstart](specs/001-local-audio-transcription/quickstart.md) for the offline build and validation commands.

## Run the CLI

The exact task work-directory path must not already exist, although its parent must exist and be writable.

```bash
uv sync --group dev

TASK_PARENT="$(mktemp -d)"
uv run transcriber-prepare \
  fixtures/sample/prepared.wav \
  "$TASK_PARENT/sample-task"
```

The optional split target is expressed in seconds:

```bash
uv run transcriber-prepare \
  SOURCE_MEDIA \
  TASK_WORK_DIRECTORY \
  --max-segment-duration-seconds 30.0
```

The default `30.0` value is an advisory FireRedVAD split target, not a strict segment-duration cap. Valid, ordered intervals returned by FireRedVAD are preserved, including intervals longer than the target.

On success, the command prints exactly four lines identifying the task directory, `prepared.wav`, `manifest.json`, and the non-negative segment count. Generated segment files are stored under `segments/`.

## Sample fixture

`fixtures/sample/prepared.wav` is the supplied integration sample. Its accompanying `fixtures/sample/manifest.json` and historical segment WAVs are diagnostic references only: their segment count and boundaries are not an acceptance oracle for FireRedVAD output. See the [fixture notes](fixtures/sample/README.md) for provenance and reference-data details.

For all arguments, flags, exit statuses, and execution examples, see the [CLI reference](docs/cli.md).
For complete setup, acceptance, failure-path, and artifact-inspection commands, follow the [quickstart and validation guide](specs/001-local-audio-transcription/quickstart.md).
