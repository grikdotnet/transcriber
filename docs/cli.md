# CLI Reference

Run commands from the repository root. Use `uv run` to select the project environment and locked dependencies.

## `transcriber-prepare`

Validates a local audio or video file, extracts its audio, detects speech segments, and writes the prepared audio and segment files to a new work directory.

### Command

```text
uv run transcriber-prepare SOURCE_MEDIA TASK_WORK_DIRECTORY
  [--max-segment-duration-seconds SECONDS]
```

### Parameters

| Parameter | Required | Default | Description |
|---|---:|---:|---|
| `SOURCE_MEDIA` | Yes | — | Path to a readable local audio or video file with a decodable audio stream. |
| `TASK_WORK_DIRECTORY` | Yes | — | New directory where the command writes its results. The parent directory must exist and the specified directory must not already exist. |
| `--max-segment-duration-seconds SECONDS` | No | `30.0` | Preferred segment duration in seconds. The value must be finite and at least `0.01`. The command rounds the value down to 10 ms frames, and detected segments can exceed the preferred duration. |
| `-h`, `--help` | No | — | Displays command help. |

### Examples

Prepare a media file:

```bash
mkdir -p /tmp/transcriber-jobs
uv run transcriber-prepare \
  fixtures/sample/prepared.wav \
  /tmp/transcriber-jobs/sample-task
```

Set a 20-second preferred segment duration:

```bash
mkdir -p /tmp/transcriber-jobs
uv run transcriber-prepare \
  fixtures/sample/prepared.wav \
  /tmp/transcriber-jobs/sample-task-20s \
  --max-segment-duration-seconds 20
```

Display help:

```bash
uv run transcriber-prepare --help
```

## `transcriber-asr`

Recognizes speech in the segments produced by `transcriber-prepare` and writes a structured transcript using the selected model.
The GUI owns enablement and sequencing: it enables ASR only after `transcriber-prepare` succeeds.
`transcriber-asr` does not start, wait for, monitor, or repeat segmentation.

### Command

```text
uv run transcriber-asr TASK_WORK_DIRECTORY --model MODEL_ID
  [--language auto|LANGUAGE_TAG]
```

### Parameters

| Parameter | Required | Default | Description |
|---|---:|---:|---|
| `TASK_WORK_DIRECTORY` | Yes | — | Work directory previously created by `transcriber-prepare`. |
| `--model MODEL_ID` | Yes | — | Identifier of an installed speech-recognition model. |
| `--language auto\|LANGUAGE_TAG` | No | `auto` | Language detection mode or a language tag such as `en`, `nl`, or `pt-BR`. A tag has a 2-8 letter ASCII primary subtag followed by zero or more hyphen-separated 1-8 character ASCII alphanumeric subtags. |
| `-h`, `--help` | No | — | Displays command help. |

The fixed local prerequisites are `vendor/llama-server`,
`models/qwen3-asr-1.7b/Qwen3-ASR-1.7B-Q8_0.gguf`, and
`models/qwen3-asr-1.7b/mmproj-Qwen3-ASR-1.7B-Q8_0.gguf`.

The command reads segment audio beneath `TASK_WORK_DIRECTORY/segments/`. Before provider startup,
every referenced Segment path must equal its exact index-derived `segments/segment-NNNN.wav` form.
Its resolved filesystem target remains beneath `TASK_WORK_DIRECTORY/segments/`; the target exists
with canonical WAV properties and exact manifest duration, verified by exact frame/sample count.

After each successfully processed segment, stdout receives
`recognized_segments=1 total_segments=10`, with the actual constant total. Success ends with an
absolute `transcript=` path. Failures use `ERROR [STAGE] model=MODEL_ID: MESSAGE` on stderr.

| Status | Meaning |
|---:|---|
| `0` | Complete Transcript published |
| `1` | Runtime failure, timeout, or cancellation |
| `2` | Invalid arguments, model ID, or language tag |

### Transcript artifact

For model `qwen3-asr-1.7b`, a successful command atomically publishes:

```text
TASK_WORK_DIRECTORY/transcripts-qwen3-asr-1.7b/transcript.json
```

`transcript.json` is compact UTF-8 JSON with one final LF. Its top-level object has exactly one
`text` member containing an ordered array. Each array entry has exactly `text` (NFKC-normalized
text) and `probability` (a finite number from `0` through `1`), in that order. For example:

```json
{"text":[{"text":"é","probability":0.7},{"text":".","probability":0.7}]}
```

Concatenate entry text without adding separators to reconstruct the normalized transcript.
`transcript.txt` is neither published nor updated.

### Examples

Recognize speech with automatic language detection:

```bash
uv run transcriber-asr \
  /tmp/transcriber-jobs/sample-task \
  --model qwen3-asr-1.7b
```

Specify the language:

```bash
uv run transcriber-asr \
  /tmp/transcriber-jobs/sample-task \
  --model qwen3-asr-1.7b \
  --language en
```

Display help:

```bash
uv run transcriber-asr --help
```

The command grammar, prerequisites, progress output, failure output, and exit statuses are
documented in [the segment ASR CLI contract](../specs/002-segment-asr/contracts/cli.md). The
published artifact is defined by [the structured Transcript contract](../specs/003-normalized-token-json/contracts/transcript-json.md).
`transcriber-asr` does not download model artifacts or Execution Providers and does not build an
Execution Provider.
