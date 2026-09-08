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

Recognizes speech in the segments produced by `transcriber-prepare` and writes a transcript using the selected model.

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
| `--language auto\|LANGUAGE_TAG` | No | `auto` | Language detection mode or a language tag such as `en`, `nl`, or `pt-BR`. A tag starts with 2–8 ASCII letters and may include hyphen-separated 1–8 character ASCII alphanumeric subtags. |
| `-h`, `--help` | No | — | Displays command help. |

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

The full `transcriber-asr` contract is documented in [the segment ASR CLI contract](../specs/002-segment-asr/contracts/cli.md).
