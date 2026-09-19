# Quickstart: validate normalized token JSON

Run these commands from the repository root after implementation. The artifact contract is in [contracts/transcript-json.md](contracts/transcript-json.md); entity rules are in [data-model.md](data-model.md).

## Prerequisites

- Python 3.12 and `uv`.
- Native ICU development headers/library and C++ build tools for PyICU. This checkout currently lacks `pkg-config`; provision it if the PyICU source build requires it.
- For the required SC-006 real-provider checkpoint: the bundled llama.cpp executable and Qwen model artifacts already used by the existing ASR workflow. Provision these before marking the feature complete.

```bash
uv sync --locked
uv run python -c 'import icu; print(icu.VERSION, icu.ICU_VERSION)'
```

Expected: dependency sync succeeds and prints PyICU and ICU versions. No network is needed for runtime ASR after dependencies and model artifacts are installed.

## Controlled validation

```bash
uv run pytest tests/unit/domain/test_transcript.py tests/unit/protocol/test_qwen_asr.py -q
uv run pytest tests/unit/service/test_recognize_segments.py tests/integration/infrastructure/test_asr_task_files.py -q
uv run pytest tests/contract tests/acceptance/test_asr_workflow.py -m 'not real_asr' -q
uv run pytest tests/architecture/test_layer_dependencies.py -q
uv run ruff check .
uv run mypy src
```

Expected: all commands pass. Controlled cases cover cross-token composition and scoring, Qwen prefix removal, exact two-field JSON bytes, 1–100 Speech Segments, context/progress, and preservation of a prior complete artifact after malformed or incomplete provider results. The tests assert application-owned behavior, not ASR model accuracy or ICU correctness.

## End-to-end local ASR

Prepare a task with the existing `transcriber-prepare` workflow described in `docs/cli.md`, then run:

```bash
uv run transcriber-asr /absolute/path/to/task --model qwen3-asr-1.7b
uv run python -m json.tool /absolute/path/to/task/transcripts-qwen3-asr-1.7b/transcript.json
```

Expected: the CLI reports success and a `transcript=.../transcript.json` path. The JSON reader succeeds; each `text` entry has only `text` and `probability`. Concatenating entry text requires no added separator. A successful response with no `logprobs.content` field contributes an empty segment; missing or invalid fields within a present transcript token and abnormal completion fail at the provider-response boundary. Token strings are authoritative even if llama.cpp stop handling makes final assistant content differ. The real-provider run does not assert token/content equality or transcription accuracy.

Run the SC-006 checkpoint and confirm the real-provider test is collected and not skipped:

```bash
uv run pytest tests/acceptance/test_asr_workflow.py -m real_asr -q
```

## Empty and failure checks

With the controlled empty-result fixture, expected artifact bytes are exactly `{"text":[]}\n`. With controlled malformed token, abnormal completion, span overflow, cancellation, and provider-failure fixtures, expected behavior is a non-success status, no temporary `transcript.json` output, and unchanged bytes for any previous complete `transcript.json`.
