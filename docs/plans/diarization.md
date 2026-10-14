# Implementation plan: fused diarization

Created: 2026-10-08. Revised: 2026-10-13. Status: proposal awaiting approval. Implementation has not started.

## Overview

Add a Diarization Task between media preparation and transcription. Combine full-recording Nemotron and Community-1 predictions using [gap-fill fusion](../prediction-fusion-algorithm.md), restrict the result to the prepared Speech Segments, and publish a speaker timeline. Detailed behavior belongs to the contracts below.

## Algorithm contract

1. Validate predictions on the common Canonical Audio timeline -> verify: timestamps are finite and labels valid. Clip intervals to the recording duration and discard intervals with no positive duration after clipping; reject malformed results separately.
2. Build elementary intervals from both predictions' boundaries and the audio endpoints -> verify: each interval has constant active speaker sets. Per-label counters prevent duplicate or overlapping rows for one identity from counting as multiple speakers.
3. Accumulate agreement only where each engine has exactly one active identity -> verify: the agreement matrix excludes silence and ambiguous overlaps. Matching uses the complete recording, including activity outside Speech Segments.
4. Maximize total agreement with a one-to-one Hungarian assignment -> verify: rectangular matrices permit unassigned identities. Sort labels before the supported SciPy solver so equal-optimum cases are repeatable without score perturbation.
5. Accept a proposed pair only when the assigned Nemotron identity is a row maximum, paired agreement is at least **3 seconds**, and support is at least **70%** -> verify: duration and support comparisons are inclusive. Support divides paired agreement by that pyannote label's total single/single agreement, with zero support for a zero denominator. Reject unsupported pairs without rerunning assignment.
6. Preserve every active Nemotron identity; fill only Nemotron-empty intervals containing exactly one accepted, mapped Community-1 identity -> verify: unmatched labels and Community-1 overlaps leave gaps unassigned, and every output identity comes from Nemotron.
7. Merge overlapping or touching intervals per identity and sort by start, identity, then end -> verify: positive gaps and different-speaker overlap survive. Keep timestamps in seconds through matching and fusion.
8. Convert fused endpoints to the nearest 16 kHz sample using ties-to-even, clamp to audio bounds, and intersect with the union of exact Segment Manifest intervals -> verify: collapsed intervals are discarded and excluded gaps split activity. Existing VAD padding and merged pauses inside Speech Segments remain permitted. Merge/sort retained intervals again in the sample time base.

## Final artifact and lifecycle

Publish only `TASK_WORK_DIRECTORY/diarization.json`: compact UTF-8 JSON with one trailing LF and exactly the schema version, time base, and final intervals. Retain positive integer Nemotron speaker IDs without renumbering after masking.

```json
{"schema_version":1,"time_base":{"unit":"sample","sample_rate_hz":16000,"start_inclusive":true,"end_exclusive":true},"intervals":[{"speaker_id":1,"start_sample":160000,"end_sample":192000}]}
```

Empty output has the same schema with `"intervals":[]`. Intervals have positive duration within Canonical Audio bounds and the mask; ordering follows the algorithm contract.

Validate the Segment Manifest and Canonical Audio first. An empty Speech Segment union succeeds without checking engine/model prerequisites or running inference. Otherwise run Nemotron and validate its full-recording prediction. Count distinct speaker IDs in positive-duration intervals after clipping to Canonical Audio bounds, before applying the Speech Segment mask. If Nemotron finds zero or one speaker, skip Community-1 prerequisite checks, library imports, inference, and fusion; publish the masked Nemotron result without a fallback warning. Repeated intervals for one speaker still count as one speaker. Attempt Community-1 only when Nemotron succeeds and finds at least two distinct speakers.

Missing secondary packages/assets, unusable Vulkan, secondary inference exceptions, and invalid secondary results automatically produce a warning and masked Nemotron-only output. A valid empty secondary prediction or no accepted identity mapping is normal fusion behavior, not fallback. Invalid common inputs, Nemotron failure, cancellation, fusion failure, cleanup failure, and publication failure fail the task.

Before publishing, copy Nemotron intervals into Python-owned values, close every NeMo stream with `nemo_speech_diar_stream_close()`, and destroy the NeMo model with `nemo_speech_diar_destroy()`. Release all Community-1 model references before closing NCNN Vulkan with `close_vulkan()`, then release native output buffers and the shared decoded audio. Clean up only resources that were created, including partial initialization. Then atomically replace `diarization.json`. On failure or cancellation, perform the same cleanup and preserve the previous complete artifact.

Inference has no fixed deadline. Check cancellation before and after NeMo calls, Community-1 stages, and before publication; Ctrl-C follows the failure path. Native calls may defer Python interruption until returning. The GUI can terminate the whole CLI process and owns preventing concurrent commands for one work directory.

## Runtime and CLI contracts

Use the CLI command:

```text
transcriber-diarize TASK_WORK_DIRECTORY
  [--nemo-gpu-index INDEX] [--vulkan-gpu-index INDEX]
```

| Parameter | Default | Validation and target |
|---|---:|---|
| `--nemo-gpu-index` | 0 | Integer ≥ -1; forwarded to NeMo model configuration's `gpu` field. -1 selects CPU. |
| `--vulkan-gpu-index` | 0 | Non-negative integer; forwarded to Community-1's `gpu_index`. |

Validate argument types and ranges before inference; invalid arguments exit with the CLI contract's argument-error status. Actual device availability follows the lifecycle's engine-failure policy. Resolve prerequisite paths relative to the application checkout through Composition:

| Prerequisite | Location / setting |
|---|---|
| NeMo C library | `vendor/nemo-speech/install/lib/libnemo_speech_asr_c.dylib` on the inspected macOS installation; corresponding installed shared library on other supported platforms |
| Nemotron model | `models/Nemotron-3-Diarization.q8_0.gguf` |
| Community-1 assets | `models/pyannote-community1/` |
| Community-1 library | Preinstalled `diarization` package in transcriber's Python environment |
| Numerical runtime | Transcriber's pinned NumPy; SciPy 1.16.2 assignment solver |

Decode Canonical Audio once into a one-dimensional contiguous float32 array, scaling signed PCM16 samples by `1 / 32768`. Validate sample count and finite values; keep the array alive while native calls use its pointer. Both engines consume the same samples as read-only mono 16 kHz audio. Community-1's internal windows may copy data; the adapter does not decode the recording a second time.

Load NeMo through `ctypes` and its supported C ABI. Mirror the pinned headers' native-aligned field layouts, configure `argtypes`/`restype` for every function, and set size-prefixed structs' `size` to `ctypes.sizeof`. Model configuration sets the selected `gpu` index, `preset=b"v3-offline"`, and `left_context_frames=-1`; other geometry overrides remain at their documented keep-preset values. Zero left context is an explicit override and must not replace the offline preset's context.

Create the model, open one stream, push complete Canonical Audio with `nemo_speech_diar_stream_push_f32()` at 16 kHz, and call `nemo_speech_diar_stream_finish()`. Read segments with the two-call count/buffer pattern of `nemo_speech_diar_segments()`, using default segmentation settings. Copy `double` start/end seconds and one-based speaker IDs directly, without formatted timestamp conversion. On failed calls, translate status and immediately copy `nemo_speech_asr_last_error()`; native cancellation follows the task cancellation path.

The `v3-offline` preset uses the stateful streaming API across the full recording. It is distinct from `nemo_speech_diar_offline_f32()`, whose full-attention path has a positional-length limit. The plan selects the preset, not that limited-duration function. NeMo's `gpu` index uses ggml device enumeration; -1 selects CPU. Community-1's `gpu_index` uses NCNN Vulkan enumeration, so the two index spaces need not refer to the same device.

Construct Community-1's `Diarizer` with `minimum_speakers=N`, `maximum_speakers=N`, and the selected `gpu_index`, where N is Nemotron's observed count from the lifecycle. Both bounds request a hard final count, capped by usable observations; count constraints may split or merge groups, and insufficient observations can yield fewer identities. A valid result with fewer identities still follows normal fusion, rather than fallback. Call `segment`, `extract_embeddings`, `cluster`, and `reconstruct` synchronously. Validate returned Segment objects and keep timestamps in seconds. Models are not shared across threads. Import secondary dependencies lazily so missing optional modules reach the lifecycle's fallback path rather than blocking CLI startup. External package metadata must be reconciled during preinstallation with transcriber's NumPy pin.

| CLI output | Contract |
|---|---|
| Stage start on stdout | `stage=validate`, `stage=nemotron`, `stage=community1`, `stage=fusion`, `stage=mask`, or `stage=publish` |
| Success on stdout | Final line `diarization=ABSOLUTE_PATH` |
| Fallback on stderr | `WARNING [community1]: REASON; using Nemotron-only diarization` |
| Failure on stderr | `ERROR [STAGE]: MESSAGE`; stages above or `cancelled` |
| Exit status | 0 for fused/fallback/empty success; 1 for runtime/cancellation failure; 2 for invalid arguments |

Emit only stages that execute, following the lifecycle branches above. Warning reasons identify the failed secondary stage.

## Entities, architectural layers, and relationships

| Code entity / component | Layer | Responsibility |
|---|---|---|
| Speaker Activity and prediction types | Domain | Immutable intervals and recording-local identities; pure invariants |
| Timeline sweep, agreement matrix, mapping evidence | Domain | Derive active sets and identity agreement |
| Fusion Result and fusion/masking functions | Domain | Apply the algorithm contract |
| NeMo C ABI declarations | Protocol | Describe native structs, function signatures, and boundary validation without loading a library |
| Artifact codec | Protocol | Encode/decode the final artifact contract |
| CLI command/progress/result/failure types | Protocol | Validate public CLI boundary values |
| NeMo ctypes adapter and provider-neutral result types | Infrastructure | Load the C library, manage model/stream handles and buffers, and return validated Python-owned results |
| Community-1 adapter and provider-neutral result types | Infrastructure | Invoke the library, validate returned objects, manage GPU resources |
| Decoded audio buffer, input validation and publication functions | Infrastructure | Read inputs, own the shared sample array, validate WAV properties/sample count and safe paths, publish bytes |
| DiarizeAudio | Service | Orchestrate lifecycle and invoke Domain operations |
| Application builder and boundary mappers | Composition | Assemble components and map results into Domain predictions |
| CLI entry point | Controller | Parse invocation, call application, render output |

Composition supplies ABI declarations and boundary conversion callables to Infrastructure without adding an Infrastructure import of Protocol. Composition maps both engines' provider-neutral Infrastructure results into Domain values. The Domain matching function receives a typed assignment callable supplied by Composition. Provider types and model calls remain inside Infrastructure. Interfaces and implementations share a layer, following [the architecture gate](../../architecture/layers.md). Reuse the existing WAV reader and atomic-writer components where compatible.

## Assumptions and evidence

- Canonical Audio is complete mono 16 kHz PCM16. Manifest intervals use integer, start-inclusive/end-exclusive samples. Both engines use the same audio origin and channel; neither receives independently split Speech Segment audio.
- Speaker identities are local to a recording. The engines' label spelling supplies no identity correspondence.
- Runtime/model assets are preinstalled. One decoded recording is held in memory for both engines; no recording-size limit has been specified.
- Selected Community-1 source: `/opt/workspaces/pyannote-community1-plda-vbx`, inspected revision `34c8982e243eda9e42834ed255067ab727410379`. The library returns Segment objects directly; its serialized CLI precision is irrelevant to this integration.
- The inspected provider pins NumPy 2.3.3, NCNN 1.0.20260526, SciPy 1.16.2, SoundFile 0.13.1, and kaldi-native-fbank 1.22.3. The user selected transcriber's NumPy version; the real integration checkpoint verifies compatibility and Vulkan operation on the target platform.
- Secondary assets are `segmentation.param`, `segmentation.bin`, `embedding_encoder.param`, `embedding_encoder.bin`, `resnet_seg_1_weight.npy`, `resnet_seg_1_bias.npy`, `plda.npz`, and `xvec_transform.npz`. The provider's development manifest check also requires ONNX artifacts/imports, so runtime validation checks only the needed assets.
- NeMo checkout `083861c241061562b8ec29eb06d7f6cdc3af8775` and its installed C library are now present. The ABI contract comes from [the pinned public header](https://github.com/NVIDIA/NeMo-Speech.cpp/blob/083861c241061562b8ec29eb06d7f6cdc3af8775/include/nemo_speech/diar.h) and [C implementation](https://github.com/NVIDIA/NeMo-Speech.cpp/blob/083861c241061562b8ec29eb06d7f6cdc3af8775/src/asr/c_api.cpp). The local ggml build has Metal/CPU/BLAS rather than Vulkan; NCNN Vulkan is a separate secondary prerequisite. Secondary assets and the algorithm document's linked implementation/evaluation report were absent in the earlier inspection. Runtime checkpoints require supplied prerequisites.
- `nemo_speech_diar_num_speakers()` reports model capacity, not detected speakers. Count observed identities from complete segment results as required by the lifecycle; do not pass model capacity to Community-1.
- Preparation persists postprocessed Speech Segment boundaries and discards raw VAD probabilities. The selected mask needs no preparation schema change.
- The reported fusion metrics used the original agreement threshold. Accuracy for the adapted algorithm remains an evaluation question; deterministic acceptance tests verify project-owned behavior.

## Affected files

Add `domain/diarization.py`, `protocol/{nemo_diarization,diarization_json,diarization_cli}.py`, `infrastructure/{nemo_speech,pyannote,diarization_files}.py`, `service/diarize_audio.py`, and `controller/diarization_cli.py` beneath `src/transcriber/`. Extend Composition wiring, package CLI registration, and matching unit/contract/integration/acceptance tests. Update `docs/cli.md` and `README.md` with the public contract and prerequisites.

## Test-first tasks and parallel boundaries

Each task writes behavior tests before production code, then implements and verifies one independently reviewable outcome. Acceptance refers to the owning contracts above rather than redefining those contracts.

| Task | Owner / dependencies | Acceptance criteria; action -> verification |
|---|---|---|
| T1: Contract fixtures | W1 → V1; first | Write schema/CLI contracts and controlled provider fixtures -> verify: fixtures cover the artifact, runtime and lifecycle contracts and all planned entities have one layer. |
| T2: Domain fusion and masking | W2 → V2; after T1 | Write algorithm tests, then implement pure operations -> verify: Algorithm contract and test-plan cases 1–5 pass. Own Domain files. |
| T3: ABI declarations and artifact codec | W3 → V3; after T1 | Write native-layout/signature and artifact fixtures before declarations/codecs -> verify: ABI types match the supported header, artifact values round-trip, and malformed boundary values fail under the contracts. Own Protocol files. |
| T4: Nemotron ctypes adapter | W4 → V4; after T1 | Write controlled C-call tests before adapter -> verify: offline preset configuration, GPU propagation, buffer lifetime, segment count/buffer calls, status translation, cancellation and handle cleanup satisfy Runtime and Lifecycle contracts. Own Nemotron Infrastructure files. |
| T5: Community-1 adapter | W5 → V5; after T1 | Write library-boundary tests before adapter -> verify: stage calls, speaker-count bounds, GPU propagation, result validation, partial initialization, failures, cancellation and cleanup satisfy Runtime and Lifecycle contracts. Own secondary Infrastructure files. |
| T6: Input files and publication | W6 → V6; after T1 | Write filesystem tests before I/O -> verify: canonical properties/sample count, PCM16 conversion and one shared sample array, safe paths, reruns and failure preservation satisfy Lifecycle and Artifact contracts. Own filesystem adapter files. |
| T8: Optional prerequisites | W8 → V8; after T1 | Add lazy prerequisite checks and descriptions -> verify: fixed paths and optional import failures are correctly represented by the Runtime contract. Own prerequisite helpers. |
| T7: Workflow, Composition, CLI | W7 → V7; after T2–T6 and T8 | Write orchestration/CLI tests before wiring -> verify: controlled commands satisfy all lifecycle branches and exact public output/status contracts. Own Service, Composition, Controller and CLI registration. |
| T9: Acceptance and documentation | W9 → V9; after T7 | Add end-to-end fixtures, docs and real checkpoint -> verify: Test plan passes, documentation matches owning contracts, and supplied engines integrate successfully. |

T2–T6 and T8 can run in parallel after T1 on disjoint files, within available agent capacity. T7 integrates results sequentially. Root is Orchestrator; each Wn submits to its distinct Vn. Agent assignments and review cycles follow [the constitution](../../.specify/memory/constitution.md#sub-agents).

## Test plan

1. Timeline sweep -> verify: empty predictions, clipped endpoints, touching boundaries, duplicate same-label rows and true overlaps produce correct active sets.
2. Matching -> verify: only single/single evidence contributes; rectangular/zero-evidence matrices, strongest candidates, equal-optimum assignments and rejected pairs behave as the Algorithm contract specifies. Exercise values at and immediately below each acceptance threshold and verify the support denominator.
3. Gap filling -> verify: the algorithm's worked example yields N1 at 0–15 seconds and N2 at 15–30; unmatched identities and overlap leave gaps, while active Nemotron sets remain unchanged before masking.
4. Sample conversion and masking -> verify: ties-to-even rounding, collapsed intervals, clipping, splitting, same-identity merging, simultaneous speakers and mask idempotence. A Segment at 10–12 seconds permits only that interval.
5. Mask-order regression -> verify: agreement outside Speech Segments can make a mapping eligible, while final output still contains no activity outside the Segment union.
6. Boundaries/resources -> verify: malformed runtime/library results, missing assets/modules, unavailable GPU, partial initialization, C ABI status failures, preset configuration, GPU/count propagation, buffer lifetime, cancellation, cleanup failure and atomic publication against controlled fixtures/fakes.
7. CLI acceptance -> verify: GPU argument defaults, configured-index propagation and invalid argument rejection; fused success, automatic fallback, empty-mask skip and fatal failures produce the Lifecycle and CLI contracts' artifact bytes, messages and statuses. Exercise Nemotron predictions with zero speakers, repeated intervals for one speaker, and two distinct speakers; only the last attempts Community-1. Verify speaker counting precedes masking, the detected count supplies both secondary bounds, valid fewer-identity results still fuse, skipped secondary dependencies are untouched, and intentional skips emit no fallback warning or Community-1/fusion progress. Common input failure and cancellation preserve prior output.
8. Regression/architecture -> verify: `uv run pytest -m 'not real_vad and not real_asr and not real_diarization'`, `uv run ruff check .`, `uv run mypy src`, and layer-dependency checks pass. Introduce `real_diarization` and a required-check flag following existing conventions.
9. Real integration -> verify: supplied runtimes/assets support the project-owned invocation, direct library result mapping, selected NumPy/GPU configuration, offline preset, count-bound policy and final artifact. Missing prerequisites leave this checkpoint incomplete; controlled fallback success does not substitute for a successful two-engine checkpoint.

## Non-goals and limits

- No transcription changes or alignment, GUI implementation, runtime/model building, downloads or installation, or sibling-repository edits.
- No changes to Source Media, Canonical Audio, Segment Manifest, Speech Segment files or existing Transcript contracts.
- No user-supplied speaker-count hints, model/path/fallback flags, extra collar, smoothing, minimum gap/fill duration, VAD rerun or stricter raw-VAD mask.
- No engine CLI/JSON/RTTM intermediate integration, separate Python environment, CPU secondary retry, concurrent engine execution, shared model instances, or CLI work-directory locking.
- No named-person identification, cross-recording identity tracking, live fusion, many-to-one matching, assignment retries, new identities absent from Nemotron, active Nemotron identity corrections or Community-1 overlap fills.
- No inference-time reference annotations, evaluation collars or threshold tuning against references. Accuracy evaluation is separate from deterministic acceptance; manual reference turns are diagnostic rather than exact model-output oracles.
