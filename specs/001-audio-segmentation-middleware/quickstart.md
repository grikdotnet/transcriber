# Quickstart and Validation Guide

This guide describes the expected commands after implementation. It validates the CLI, the bundled FFmpeg boundary, the native FireRedVAD/NCNN provider, the manifest contract, and real-audio segmentation.

## Prerequisites

- macOS development host capable of executing the checked-in `vendor/ffmpeg` artifact.
- Python 3.12 and `uv`.
- CMake 3.10+, a C++14 compiler, and a local static NCNN `20260113` installation.
- The four model files under `models/firered-vad.ncnn/`.
- No network connection is required or used by preparation tasks.

The local NCNN installation must expose headers, `libncnn.a`, and its CMake package under one absolute directory. Follow the official [FireRedVAD NCNN runtime guide](https://github.com/FireRedTeam/FireRedVAD/tree/c30ec49e8cc69642b0ee65362eba11b9d11c6e54/runtime/ncnn) and pinned [NCNN 20260113 build guide](https://github.com/Tencent/ncnn/blob/20260113/docs/how-to-build/how-to-build.md) outside the middleware workflow.

## Verify local assets

From the repository root:

```bash
./vendor/ffmpeg -version

shasum -a 256 \
  models/firered-vad.ncnn/cmvn_istd.bin \
  models/firered-vad.ncnn/cmvn_means.bin \
  models/firered-vad.ncnn/firered_vad_non_stream.ncnn.bin \
  models/firered-vad.ncnn/firered_vad_non_stream.ncnn.param
```

Expected model hashes, in the same order:

```text
0f577337a74e728118f323ea6a64d269de85d29d40f4a60b57cabc960ca13add
3c80c1c51be7d363f1d64a1d52687df163f60a060384058a83422a22bd80b5c7
c58c3fae3cc083d7686b8508b08d436791e29da3d2b0c9687b42193eecc671a0
e8857e956f9f8b86a6ef741ab8ab70c83ee5051e2078d7854f1c6618f9dbd0c9
```

Any missing or mismatched prerequisite blocks the real-provider acceptance run. Do not substitute a system FFmpeg or another VAD model.

## Create the Python environment

```bash
uv sync --group dev
uv run python --version
```

Expected Python version: `3.12.x`.

## Build the native provider

Set `NCNN_ROOT` to the pinned local NCNN installation and run the project build wrapper:

```bash
NCNN_ROOT=/absolute/path/to/ncnn-20260113/install \
  scripts/build-firered-vad-ncnn-macos.sh

file vendor/firered-vad-ncnn
```

The build must create `vendor/firered-vad-ncnn` for the host architecture without downloading files. The native wire contract is [contracts/firered-runner.md](contracts/firered-runner.md).

## Fast deterministic verification

Run tests that use controlled probabilities, synthetic WAVs, and fake process results:

```bash
uv run pytest -m "not real_vad"
uv run mypy --strict src
uv run ruff check src tests
```

Expected outcome: all tests pass; no layer dependency violation, type error, or lint error is reported.

This suite must cover:

- The runner build contains the pinned unchanged FireRedVAD C++ frontend.
- Supplied `prepared.wav` path handoff, runner acceptance, CMVN/NCNN asset loading, public probability schema, and reported-count/array-length coherence for ordinary and long input, without deriving an expected FireRedVAD frame count, inspecting chunk order, asserting probability ordering, or asserting fixture properties.
- The pinned unchanged upstream postprocessor is loaded and receives the exact configured settings, including `min_speech_frame=20` and `min_silence_frame=20`.
- Postprocessor output order and interval shape are preserved without a first-party threshold or frame-count correction.
- Advisory target conversion and handoff, empty upstream output, invalid probability documents, invalid returned intervals, and segment/manifest invariants.
- Generated-segment format and sample-range correspondence using synthetic controlled WAV input only.
- Exact repository-bundled FFmpeg argv and decode-before-directory ordering.
- Failure-stop behavior for every service stage.
- CLI stdout/stderr and exit-status contracts.

These checks validate first-party provenance, adaptation, configuration, and boundary behavior only. They do not independently calculate FireRedVAD preprocessing, inference, or postprocessing results.
They also do not execute assertions against FFmpeg-produced sound parameters or the intrinsic properties of supplied fixtures.

## Required fixture-backed integration acceptance test

```bash
uv run pytest \
  --real-vad-required \
  -m real_vad \
  tests/acceptance/test_sample_workflow.py \
  -q -s
```

This command must fail, not skip, if FFmpeg, the native runner, model assets, or fixture files are unavailable. Expected result:

- `fixtures/sample/prepared.wav` is processed once through the complete CLI workflow.
- The runner's public probability document is schema-valid and its reported frame count equals the probability-array length.
- The Infrastructure adapter represents returned timestamps as exact 16 kHz sample boundaries; Domain accepts valid ordered `SampleInterval` values without clamping or changing those boundaries.
- Every generated WAV's sample count exactly matches its generated manifest interval.
- No outbound network request occurs.
- Exactly one compact `REFERENCE_DIAGNOSTIC={...}` line is printed.

The fixture-backed test treats `fixtures/sample/prepared.wav` as a supplied input. It does not independently validate the source fixture's format or duration, derive an expected FireRedVAD frame count, assert an expected segment count or boundary, or inspect the sound parameters produced by FFmpeg.

Missing dependencies, malformed public output, invalid interval adaptation, or generated artifact mismatch fail this command. FireRedVAD segmentation quality does not.

## Required non-gating sample diagnostic

The acceptance run prints exactly one compact JSON line in this form:

```text
REFERENCE_DIAGNOSTIC={"actual_segment_count":N,"reference_segment_count":M,"paired_boundary_deltas":[{"index":I,"start_delta_samples":S,"end_delta_samples":E}]}
```

Let `N` and `M` be the actual and reference segment counts. The array pairs records at the same zero-based index from `0` through `min(N, M) - 1` in ascending order. Each start/end delta is the actual sample index minus the reference sample index. The pair array is empty when either manifest has no segments, and the counts indicate any unpaired trailing records. Controlled manifest data verifies this diagnostic mapping; for the fixture-backed run, tests assert only that exactly one line matching the defined JSON shape is present. Its numeric values are for human investigation only and cannot change command status, modify generated output, or serve as release evidence for FireRedVAD quality.

## Run the CLI manually

```bash
TASK_PARENT="$(mktemp -d)"
TASK_DIRECTORY="$TASK_PARENT/sample-task"

uv run transcriber-prepare \
  fixtures/sample/prepared.wav \
  "$TASK_DIRECTORY"
```

Expected stdout shape:

```text
task_work_directory=/absolute/path/to/sample-task
canonical_audio=/absolute/path/to/sample-task/prepared.wav
manifest=/absolute/path/to/sample-task/manifest.json
segment_count=<non-negative integer>
```

Validate the artifact tree:

```bash
uv run python -m json.tool "$TASK_DIRECTORY/manifest.json"
find "$TASK_DIRECTORY" -maxdepth 2 -type f -print | sort
```

The output contract is [contracts/cli.md](contracts/cli.md); manifest shape and cross-field semantics are defined by [contracts/manifest.schema.json](contracts/manifest.schema.json) and [contracts/manifest.md](contracts/manifest.md).

## Failure-path spot checks

An unsupported or audio-free source must fail before creating the requested work directory:

```bash
FAILURE_PARENT="$(mktemp -d)"
FAILURE_TASK="$FAILURE_PARENT/should-not-exist"

uv run transcriber-prepare README.md "$FAILURE_TASK"
test ! -e "$FAILURE_TASK"
```

Expected stderr starts with:

```text
ERROR [source-media]:
```

An existing task directory, missing model asset, incompatible native runner, or segment-write failure must return status `1`, identify the correct stage, start no later stage, and never publish a successful-looking `manifest.json`.
