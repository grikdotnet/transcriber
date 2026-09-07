# Quickstart: Segment Speech Recognition

This guide validates the independent ASR command after the independent segmentation command has
completed successfully. In the product, the GUI owns this sequencing and enables ASR only after it
receives segmentation success.

## Prerequisites

- Python 3.12 project environment installed with development dependencies
- Existing media-preparation prerequisites
- Shipped llama.cpp Execution Provider at `vendor/llama-server`
- Qwen3-ASR artifacts installed at:
  - `models/qwen3-asr-1.7b/Qwen3-ASR-1.7B-Q8_0.gguf`
  - `models/qwen3-asr-1.7b/mmproj-Qwen3-ASR-1.7B-Q8_0.gguf`

Provider installation, model downloading, and release packaging are outside this feature.

## Install the project environment

```bash
uv sync --group dev
```

## Run the deterministic test-first suite

The default suite uses controlled provider doubles. It proves project-owned behavior without
loading an ASR model or judging third-party transcription quality.

```bash
uv run pytest -m "not real_vad and not real_asr"
uv run mypy --strict src
uv run ruff check src tests
```

Expected result: all selected tests pass, no selected required test is skipped, strict typing is
clean, and lint is clean.

## Prepare, then recognize

Run segmentation as its own command:

```bash
TASK_PARENT="$(mktemp -d)"
TASK_DIRECTORY="$TASK_PARENT/sample-task"

uv run transcriber-prepare \
  fixtures/sample/prepared.wav \
  "$TASK_DIRECTORY"
```

Proceed only after `transcriber-prepare` returns status `0`. Then run ASR independently:

```bash
uv run transcriber-asr \
  "$TASK_DIRECTORY" \
  --model qwen3-asr-1.7b \
  --language auto
```

Expected stdout shape for a task with `N` segments:

```text
recognized_segments=1 total_segments=N
...
recognized_segments=N total_segments=N
transcript=/absolute/path/to/sample-task/transcripts-qwen3-asr-1.7b/transcript.txt
```

There are no startup or publication progress records.

Inspect the artifact:

```bash
test -f "$TASK_DIRECTORY/transcripts-qwen3-asr-1.7b/transcript.txt"
```

The test proves publication, not the correctness or quality of Qwen's words.

## Run with an explicit language

```bash
uv run transcriber-asr \
  "$TASK_DIRECTORY" \
  --model qwen3-asr-1.7b \
  --language en-GB
```

The GUI-facing value remains a language tag; the provider adapter owns any model-specific wire
translation.

## Verify atomic replacement

After one successful run, record the existing transcript checksum. Force a controlled provider
failure through the integration-test fixture and verify the checksum is unchanged. The automated
contract is exercised with:

```bash
uv run pytest tests/integration/infrastructure/test_asr_task_files.py \
  tests/unit/service/test_recognize_segments.py -q
```

Expected result: failure and cancellation cases leave the previous transcript untouched and remove
temporary output.

## Run the real-provider integration checkpoint

```bash
uv run pytest \
  --real-asr-required \
  -m real_asr \
  tests/acceptance/test_asr_workflow.py -q -s
```

This checkpoint requires the shipped provider and supplied Qwen artifacts. It verifies:

- fixed-path provider and model resolution;
- provider readiness and cleanup;
- ordered local segment requests;
- context and language request construction;
- provider response parsing;
- progress and atomic Transcript publication;
- no external network access.

The real-provider semantic test must not compare recognized words with
`fixtures/sample/transcript.json`, assert non-empty output, calculate WER, assert language
accuracy, or use model quality/performance as pass/fail evidence. Controlled fixtures retain exact
Transcript-content and non-empty assembly assertions.

## Representative failures

Unknown model IDs and invalid language syntax fail before provider startup:

```bash
uv run transcriber-asr "$TASK_DIRECTORY" --model unknown-model
uv run transcriber-asr "$TASK_DIRECTORY" --model qwen3-asr-1.7b --language not_a_tag
```

A task directory with a valid manifest but zero Speech Segments returns status `1` with stage
`segment-manifest`. Missing or mismatched WAV files return status `1` with stage `segment-files`.

Provider failures include a quoted, escaped, bounded provider diagnostic and identify the zero-based
segment index when recognition had started. No failure emits a final `transcript=` line.

## Scope reminders

- Segmentation and ASR remain separate commands; the GUI owns enablement and sequencing.
- Simultaneous ASR invocations for one task/model are unsupported and are not tested.
- Model downloads, provider builds, catalog listing, timestamps, diarization, batching, and
  VibeVoice/Canary adapters are not part of this delivery.
