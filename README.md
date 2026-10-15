# transcriber

Local command-line middleware that extracts one audio stream from a media file with the bundled `vendor/ffmpeg`, runs the local non-streaming FireRedVAD NCNN provider, and writes a manifest plus speech-focused WAV segments.

This delivery supports separate CLI commands for Media Preparation, segment speech recognition, and speaker diarization. It does not provide a GUI, API, worker mode, or model downloading.

## Requirements

- Python 3.12 and `uv`
- the bundled `vendor/ffmpeg`
- a host-built `vendor/firered-vad-ncnn`
- FireRedVAD model and CMVN assets in `models/firered-vad.ncnn/`

The native provider build is only for Media Preparation and requires a local static NCNN `20260113` installation. It is not an ASR Execution Provider build. See the [quickstart](specs/001-audio-segmentation-middleware/quickstart.md) for the offline Media Preparation build and validation commands.

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
For complete setup, acceptance, failure-path, and artifact-inspection commands, follow the [quickstart and validation guide](specs/001-audio-segmentation-middleware/quickstart.md).

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
`transcript=/absolute/path/to/sample-task/transcripts-qwen3-asr-1.7b/transcript.json`; failures use
`ERROR [STAGE] model=MODEL_ID: MESSAGE` on stderr. Exit statuses are:

| Status | Meaning |
|---:|---|
| `0` | Complete Transcript published |
| `1` | Runtime failure, timeout, or cancellation |
| `2` | Invalid arguments, model ID, or language tag |

For model `qwen3-asr-1.7b`, the successful artifact is
`TASK_WORK_DIRECTORY/transcripts-qwen3-asr-1.7b/transcript.json`. The file is compact UTF-8 JSON
with one final LF and exactly one top-level `text` array. Each entry has exactly `text`
(NFKC-normalized text) and `probability` (a finite number from `0` through `1`), in that order:

```json
{"text":[{"text":"é","probability":0.7},{"text":".","probability":0.7}]}
```

Concatenate entry text without adding separators to reconstruct the normalized transcript.
`transcript.txt` is neither published nor updated.

`transcriber-asr` does not download model artifacts or Execution Providers and does not build an
Execution Provider: the fixed supplied ASR prerequisites require no download or build procedure.
See the [ASR CLI contract](specs/002-segment-asr/contracts/cli.md) for command behavior and the
[structured Transcript contract](specs/003-normalized-token-json/contracts/transcript-json.md) for
publication rules.

## Speaker diarization

After Media Preparation succeeds, run the independent command on the existing task directory:

```bash
uv run transcriber-diarize /tmp/transcriber-jobs/sample-task \
  --nemo-gpu-index 0 --vulkan-gpu-index 0
```

Both GPU indices default to `0`. NeMo accepts `-1` for CPU or a nonnegative ggml GPU index;
Community-1 requires a nonnegative NCNN Vulkan index. The two runtimes enumerate devices
independently. The command uses the preinstalled NeMo C library, Nemotron GGUF and Community-1
Python library, eight model files, SciPy solver and Vulkan device described in the
[runtime guide](docs/diarization-runtime-setup.md). The command installs nothing and starts
neither Media Preparation nor ASR; the GUI owns sequencing and work-directory concurrency.

Nemotron supplies recording-local speaker identities. Community-1 can fill supported gaps after
full-recording identity matching; the final activity is restricted to the exact union of persisted
Speech Segment intervals, with no added collar. An empty union skips all engines; zero or one
observed Nemotron identity skips Community-1 and fusion. Recoverable Community-1 failures warn
and produce masked Nemotron-only activity. Nemotron failure, cancellation, fusion/mask failure,
cleanup failure and publication failure remain fatal.

Success ends with `diarization=/absolute/path/to/sample-task/diarization.json`. This is the only
published diarization artifact; the compact JSON stores speaker IDs and sample bounds at 16 kHz.
See the [CLI reference](docs/cli.md#transcriber-diarize) for stages, statuses and examples.
