# Fused Diarization Validation Guide

Run from the repository root with the existing locked Python 3.12 environment. The recorded verification below covers the implemented feature.

## Prerequisites

Use the fixed paths in [the native contract](contracts/native-runtimes.md). See [the installation guide](../../docs/diarization-runtime-setup.md) for the existing dependency override and local Vulkan driver manifest. No engine/model setup is part of this feature.

```bash
uv lock --check
uv run python -c 'import ctypes; ctypes.CDLL("vendor/nemo-speech/install/lib/libnemo_speech_asr_c.dylib")'
uv run python -c 'from diarization.pipeline import Diarizer; import numpy, scipy; print(numpy.__version__, scipy.__version__)'
```

On the current Mac, select the already-created NCNN driver manifest before Vulkan import:

```bash
export VK_DRIVER_FILES="$PWD/.venv/share/vulkan/icd.d/ncnn_moltenvk.json"
```

If the manifest or assets are missing, have the installation owner supply them; this guide does not create or download them.

## Controlled verification

```bash
uv run pytest -m 'not real_vad and not real_asr and not real_diarization' -q
uv run ruff check .
uv run mypy src
```

The feature's controlled tests must prove the [lifecycle branches](contracts/lifecycle.md), including empty mask, zero/one-speaker skip, fusion, automatic fallback, fatal failures, cancellation and cleanup. Hardware/model accuracy is not their oracle.

## Local end-to-end run

Create a fresh preparation work directory; its parent must exist. Reuse an existing prepared directory instead if available.

```bash
uv run transcriber-prepare fixtures/sample/prepared.wav /tmp/transcriber-diarization-example
uv run transcriber-diarize /tmp/transcriber-diarization-example
```

Expected: stage messages and a final absolute `diarization=` path; `diarization.json` follows [the final artifact contract](contracts/diarization-json.md). A secondary failure may validly warn and succeed with Nemotron-only output. This is a workflow success, not proof of successful two-engine inference. Repeat only the diarization command to verify atomic replacement without repeating preparation.

Exercise independent index propagation:

```bash
uv run transcriber-diarize /tmp/transcriber-diarization-example --nemo-gpu-index -1 --vulkan-gpu-index 0
uv run transcriber-diarize /tmp/transcriber-diarization-example --vulkan-gpu-index -1
```

The first requests CPU NeMo and Vulkan secondary execution. The second exits with the argument-error code before inference. Full output/status rules are in [CLI](contracts/cli.md).

## Required real integration checkpoint

Run the required marker and flag together:

```bash
uv run pytest -m real_diarization --real-diarization-required -q
```

Run on a host exposing the selected GPU APIs; the Codex sandbox may not expose Metal devices. Checkpoint scenarios explicitly invoke both real adapters and their boundary mappings. The Community-1 adapter checkpoint can supply a controlled valid speaker count to test count propagation without asserting Nemotron's model accuracy. An empty-mask or zero/one-speaker workflow result cannot substitute for that secondary adapter checkpoint. Missing prerequisites or fallback fail required two-engine verification. Test first-party calls, arguments, result mapping and ownership; do not assert exact model/reference agreement.


## Recorded final verification — 2026-10-14

The final controlled run used the existing environment without synchronization:

```bash
UV_CACHE_DIR=/tmp/transcriber-uv-cache uv run --no-sync pytest -m 'not real_vad and not real_asr and not real_diarization' -q
UV_CACHE_DIR=/tmp/transcriber-uv-cache uv run --no-sync ruff check .
UV_CACHE_DIR=/tmp/transcriber-uv-cache uv run --no-sync mypy src
UV_CACHE_DIR=/tmp/transcriber-uv-cache uv lock --check
```

Results: **931 passed, 14 deselected in 3.21s**; Ruff passed; mypy passed for **44 source files**; the lock check resolved **31 packages** successfully. The controlled run includes existing preparation, ASR and recursive architecture checks; no separate duplicate regression suite was needed.

The Orchestrator ran the required checkpoint on the host with the existing Vulkan driver selection:

```bash
VK_DRIVER_FILES=$PWD/.venv/share/vulkan/icd.d/ncnn_moltenvk.json UV_CACHE_DIR=/tmp/transcriber-uv-cache uv run --no-sync pytest -m real_diarization --real-diarization-required -q
```

Result: **2 passed, 943 deselected in 17.09s**. Both actual adapters and Composition mappings completed, using NeMo GPU 0, Vulkan GPU 0 and Community-1 minimum/maximum speaker bounds of 2. Sandbox device unavailability does not invalidate this successful host checkpoint. The checkpoint verifies invocation, settings, mapping and ownership, without asserting model accuracy.

The installed console command was also verified with `uv run --locked transcriber-diarize --help`; only the local transcriber package was rebuilt, with no engine installation. See [task evidence](tasks.md#final-criteria-and-scope-review) for requirement and acceptance traceability.


### Convergence verification — 2026-10-14

After T018/T019 corrected exception-traceback resource retention, the same controlled commands passed: **975 tests passed, 14 deselected in 2.78s**; Ruff, mypy (44 source files) and lock validation passed. The required real checkpoint rerun on the host passed both adapters: **2 passed, 987 deselected in 0.82s**. See [Phase 8 completion evidence](tasks.md#phase-8-completion-evidence--2026-10-14) for independent review and regression details.
