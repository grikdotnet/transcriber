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

## `transcriber-diarize`

Assigns recording-local speaker identities to the complete Canonical Audio in an existing Media
Preparation directory. This separate command starts neither preparation nor ASR. The GUI owns
sequencing and prevents concurrent commands on the same directory.

### Command

```text
uv run transcriber-diarize TASK_WORK_DIRECTORY
  [--nemo-gpu-index INDEX] [--vulkan-gpu-index INDEX]
```

| Parameter | Required | Default | Description |
|---|---:|---:|---|
| `TASK_WORK_DIRECTORY` | Yes | — | Existing Media Preparation directory containing `manifest.json` and canonical `prepared.wav`. Relative invocation paths resolve to absolute paths. |
| `--nemo-gpu-index INDEX` | No | `0` | Integer at least `-1`: `-1` selects CPU; nonnegative indices use NeMo's ggml GPU enumeration. |
| `--vulkan-gpu-index INDEX` | No | `0` | Nonnegative index in NCNN's independent Vulkan GPU enumeration. |
| `-h`, `--help` | No | — | Displays help without reading inputs or loading engines. |

The fixed application-relative prerequisites are
`vendor/nemo-speech/install/lib/libnemo_speech_asr_c.dylib`,
`models/Nemotron-3-Diarization.q8_0.gguf` and `models/pyannote-community1/`, plus the
preinstalled Python libraries, SciPy assignment solver and usable NCNN Vulkan device listed in the
[runtime guide](diarization-runtime-setup.md). Runtime/model paths are independent of the caller's
working directory. No model/path, speaker-count, timeout or fallback-enable option is exposed;
the command performs no installation or download and has no fixed inference deadline.

### Masking, skips and fallback

The command validates the closed Segment Manifest and complete mono 16 kHz PCM16 Canonical Audio,
including exact sample count. The command does not need individual Speech Segment WAVs for the
mask. Both engines receive the complete decoded recording when attempted; identity matching and
fusion precede masking. Nemotron identities and active speaker sets are preserved, and accepted
Community-1 mappings may add single-speaker activity only in empty Nemotron regions. The final
mask is the exact union of manifest Speech Segment intervals, including existing VAD padding and
merged pauses, with no additional collar.

An empty Speech Segment union skips engine, model and solver checks and publishes empty activity.
Otherwise Nemotron runs first. Zero or one distinct identity in positive-duration, clipped
Nemotron activity skips Community-1 checks, imports, inference and fusion without warning.
With at least two identities, Community-1 receives that observed count as both speaker bounds.
A valid empty result or fewer returned identities still proceeds through fusion without warning.

Missing or unloadable secondary packages/assets/solver, unusable Vulkan, secondary inference
exceptions and malformed secondary intervals trigger:

```text
WARNING [community1]: REASON; using Nemotron-only diarization
```

The warning goes to stderr and the command masks Nemotron-only activity. There is no secondary CPU
retry. Common input errors, Nemotron errors, cancellation, fusion/mask errors, cleanup errors and
publication errors are fatal; runtime device availability is checked during execution.

### Output and exit statuses

Attempted stages print flushed stdout lines in execution order: `stage=validate`, `stage=nemotron`,
`stage=community1`, `stage=fusion`, `stage=mask`, `stage=publish`. Skipped stages emit no line.
Success ends with `diarization=ABSOLUTE_PATH`. Failures print `ERROR [STAGE]: MESSAGE` on stderr;
stages are the names above or `cancelled`. Public diagnostics occupy one line.

| Status | Meaning |
|---:|---|
| `0` | Complete fused, Nemotron-only or empty artifact published; help also succeeds. |
| `1` | Input, mandatory runtime, cancellation, fusion/mask, cleanup or publication failure. |
| `2` | Invalid arguments, including malformed/out-of-range indices, unknown options or positional grammar. |

Directory, manifest and audio errors after parsing are `validate` failures with status `1`.
Success atomically publishes only `TASK_WORK_DIRECTORY/diarization.json` after cleanup. Failed or
cancelled attempts preserve previous complete artifact bytes and do not modify input or Transcript
artifacts. No raw predictions, mappings, RTTM or transcript content is published.

```json
{"schema_version":1,"time_base":{"unit":"sample","sample_rate_hz":16000,"start_inclusive":true,"end_exclusive":true},"intervals":[{"speaker_id":1,"start_sample":160000,"end_sample":192000}]}
```

The compact UTF-8 JSON has one final LF. Bounds use inclusive starts and exclusive ends, lie wholly
inside the mask, and are sorted by start sample, speaker ID, then end sample. Same-speaker touching
or overlapping intervals merge; different speakers may overlap. Masking preserves surviving
positive Nemotron IDs without renumbering. Empty activity uses `"intervals":[]`. Endpoints convert
from seconds with nearest-sample ties-to-even rounding; the sample time base does not increase
model precision.

### Examples

Use the default device indices:

```bash
uv run transcriber-diarize /tmp/transcriber-jobs/sample-task
```

Use CPU for NeMo and Vulkan device zero for Community-1:

```bash
uv run transcriber-diarize /tmp/transcriber-jobs/sample-task \
  --nemo-gpu-index -1 --vulkan-gpu-index 0
```

Display help:

```bash
uv run transcriber-diarize --help
```

See the [CLI contract](../specs/004-diarization/contracts/cli.md),
[lifecycle contract](../specs/004-diarization/contracts/lifecycle.md) and
[artifact contract](../specs/004-diarization/contracts/diarization-json.md) for the full rules.
