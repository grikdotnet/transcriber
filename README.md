# transcriber

Local command-line middleware that extracts one audio stream from a media file with the bundled `vendor/ffmpeg`, runs the local non-streaming FireRedVAD NCNN provider, and writes a manifest plus speech-focused WAV segments.

This delivery supports the CLI only. It does not provide a GUI, API, worker mode, speaker diarization, or model downloading.

## Requirements

- Python 3.12 and `uv`
- the bundled `vendor/ffmpeg`
- a host-built `vendor/firered-vad-ncnn`
- FireRedVAD model and CMVN assets in `models/firered-vad.ncnn/`

The native provider build is only for Media Preparation and requires a local static NCNN `20260113` installation. It is not an ASR Execution Provider build. See the [quickstart](specs/001-local-audio-transcription/quickstart.md) for the offline Media Preparation build and validation commands.

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

## Segment speech recognition

The GUI owns enablement and sequencing: it enables ASR only after `transcriber-prepare` succeeds.
The independent ASR command neither starts nor waits for segmentation.

```text
transcriber-asr TASK_WORK_DIRECTORY --model MODEL_ID [--language auto|LANGUAGE_TAG]
```

The fixed local prerequisites are `vendor/llama-server`,
`models/qwen3-asr-1.7b/Qwen3-ASR-1.7B-Q8_0.gguf`, and
`models/qwen3-asr-1.7b/mmproj-Qwen3-ASR-1.7B-Q8_0.gguf`. `--language` defaults to `auto`; an
explicit value has a 2-8 letter ASCII primary subtag followed by zero or more hyphen-separated
1-8 character ASCII alphanumeric subtags. The command reads segment audio beneath
`TASK_WORK_DIRECTORY/segments/`.

Before provider startup, every referenced Segment path must equal its exact index-derived `segments/segment-NNNN.wav` form. Its resolved filesystem target remains beneath `TASK_WORK_DIRECTORY/segments/`; the target exists with canonical WAV properties and exact manifest duration, verified by exact frame/sample count.

Each completed segment prints `recognized_segments=1 total_segments=10` (with the actual,
constant total). Success ends with
`transcript=/absolute/path/to/sample-task/transcripts-qwen3-asr-1.7b/transcript.txt`; failures use
`ERROR [STAGE] model=MODEL_ID: MESSAGE` on stderr. Exit statuses are:

| Status | Meaning |
|---:|---|
| `0` | Complete Transcript published |
| `1` | Runtime failure, timeout, or cancellation |
| `2` | Invalid arguments, model ID, or language tag |

`transcriber-asr` does not download model artifacts or Execution Providers and does not build an
Execution Provider: the fixed supplied ASR prerequisites require no download or build procedure.
See the [ASR CLI contract](specs/002-segment-asr/contracts/cli.md) for all failure stages and
publication rules.
