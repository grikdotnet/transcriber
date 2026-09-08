# T029 real checkpoints

**Run completed:** 2026-09-08T10:20:51Z  
**Scope:** supplied local prerequisites and the two required real-provider commands. No download
or build was performed.

## Prerequisite inspection

| Checkpoint | Fixed prerequisite paths | Result |
| --- | --- | --- |
| real VAD | `vendor/firered-vad-ncnn`, `fixtures/sample/prepared.wav`, and the four fixed files under `models/firered-vad.ncnn/` | Present as regular files. |
| real ASR | `vendor/llama-server`, `models/qwen3-asr-1.7b/Qwen3-ASR-1.7B-Q8_0.gguf`, `models/qwen3-asr-1.7b/mmproj-Qwen3-ASR-1.7B-Q8_0.gguf`, and `fixtures/sample/prepared.wav` | Present as regular files. |

The built server was validated as an executable (`llama-server` version 9959, arm64) and moved
from `ep/llama.cpp/build-macos-memdebug-static/bin/llama-server` to the fixed provider path
`vendor/llama-server`. The supplied Qwen files were validated and moved from `models/qwen-asr/`
to their fixed paths under `models/qwen3-asr-1.7b/`. The former server and model paths are absent.

## Required real-VAD checkpoint

| Command | Status | Result |
| --- | --- | --- |
| `uv run pytest --real-vad-required -m real_vad tests/acceptance/test_sample_workflow.py -q` | exit 0 | `10 passed in 0.94s` |

The command ran in required mode and did not skip. Its real-provider acceptance test checks the
project-owned local invocation boundary and interval adaptation without using provider output as a
semantic oracle. The recorded process invocation uses the supplied local runner with `shell=False`.

## Required real-ASR checkpoint

| Command | Status | Result |
| --- | --- | --- |
| `uv run pytest --real-asr-required -m real_asr tests/acceptance/test_asr_workflow.py -q -s` | exit 0 | `1 passed, 35 deselected in 9.71s` |

The required ASR checkpoint ran rather than skipped. The `real_asr` acceptance case uses the
fixed executable and artifact paths, captures local request and response adaptation, and checks
the production command's progress and publication boundary. No replacement provider, model,
download, or build was used.

## Cleanup evidence

The completed real-VAD checkpoint invokes the local provider through the project-owned process
adapter. The completed real-ASR acceptance case records the managed provider lifecycle and requires
both `terminate` and `wait=60.0` events before it can pass; its passing result is cleanup evidence
for that started provider. The test also reaches final Transcript publication only after that
cleanup path. A direct operating-system process listing is unavailable in this environment
(`pgrep` reports that the process list cannot be obtained), so no independent process-list claim is
made.

## Task status

Both required checkpoints passed in required mode with no skipped result. S-ASR accepted T029.
This evidence makes no claim about transcription semantics, quality, language accuracy, throughput,
or performance.
