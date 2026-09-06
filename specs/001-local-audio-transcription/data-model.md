# Phase 1 Data Model: Media Audio Segmentation Middleware

**Date**: 2026-09-04  
**Specification**: [spec.md](spec.md)  
**Architecture rules**: [architecture/layers.md](../../architecture/layers.md)

## Layer relationships

```text
Controller ──> Composition ──> Service ──> Domain
     │              │             ├──────> Protocol
     │              │             └──────> Infrastructure
     │              └────────────────────> Infrastructure
     └────────────────────────────> Protocol

Infrastructure: subprocess, native runtime, filesystem and WAV I/O
Protocol/Wire: CLI/result DTOs, native probability JSON, manifest JSON
Domain/Model: pure VAD settings, probabilities, intervals and invariants
Service: preparation workflow and lifecycle
Composition: repository-relative dependency assembly
Controller: argparse entry point, rendering and exit status
```

Each production entity below belongs to exactly one layer. The first-party C++ NCNN provider is a separate subprocess application whose entities are classified across Infrastructure, Protocol, Service, Composition, and Controller below. Copied upstream sources, licenses, build manifests, tests, and fixtures are excluded from layer classification by `architecture/layers.md`.

## Protocol/Wire entities

### PrepareCommand

Represents validated user intent at the controller boundary.

| Field | Type | Rules |
|---|---|---|
| `source_media` | path string | Non-empty; converted to an absolute path before service invocation. Existence/readability is checked by Infrastructure. |
| `task_work_directory` | path string | Non-empty absolute target; must not exist when work-directory creation begins. |
| `split_target_seconds` | decimal number | Finite and `>= 0.01`; defaults to `30.0`. |
| `split_target_frames` | integer | `floor(split_target_seconds / 0.01)` and `>= 1`. |

### PrepareSuccess

| Field | Type | Rules |
|---|---|---|
| `task_work_directory` | absolute path string | The created work directory. |
| `canonical_audio` | absolute path string | Resolves to `prepared.wav`. |
| `manifest` | absolute path string | Resolves to the published `manifest.json`. |
| `segment_count` | non-negative integer | Equals the manifest segment count. |

### PrepareFailure

| Field | Type | Rules |
|---|---|---|
| `stage` | stage label | One of the documented CLI failure stages. |
| `message` | string | Non-empty; identifies the relevant failing path, asset, argument, or operation class; free of raw tracebacks and unbounded external diagnostics in normal CLI output. |

### FireRedProbabilityDocument

Decoded form of the native provider's versioned JSON stdout.

| Field | Type | Rules |
|---|---|---|
| `schema_version` | integer | Exactly `1`. |
| `audio.sample_rate_hz` | integer | Exactly `16000`. |
| `audio.channels` | integer | Exactly `1`. |
| `audio.sample_format` | string | Exactly `pcm_s16le`. |
| `audio.total_samples` | non-negative integer | Reported by the native runner for the accepted input timeline. |
| `frames.frame_length_samples` | integer | Exactly `400`. |
| `frames.frame_shift_samples` | integer | Exactly `160`. |
| `frames.frame_count` | non-negative integer | Runner-reported public-contract value; equals the probability-array length. Middleware code does not derive it from audio duration or frontend mathematics. |
| `frames.probabilities` | ordered array of numbers | Each value is finite and in `[0.0, 1.0]`. |

The codec rejects missing/extra top-level members, unsupported versions, invalid constants, noncontiguous data, count mismatches, non-finite values, and out-of-range probabilities.

### ManifestAudio

| Field | Type | Rules |
|---|---|---|
| `path` | relative path string | Exactly `prepared.wav` for this delivery; cannot escape the task directory. |
| `sample_rate_hz` | integer | Exactly `16000`. |
| `channels` | integer | Exactly `1`. |
| `sample_format` | string | Exactly `pcm_s16le`. |
| `total_samples` | non-negative integer | Equals the native probability document's accepted-input sample count. |

### ManifestSegment

| Field | Type | Rules |
|---|---|---|
| `index` | non-negative integer | Equals its zero-based position in the manifest array. |
| `start_sample` | non-negative integer | Inclusive; `< end_sample`. |
| `end_sample` | positive integer | Exclusive; `<= audio.total_samples`. |
| `duration_samples` | positive integer | Exactly `end_sample - start_sample`. |
| `path` | relative path string | Exactly `segments/segment-NNNN.wav` for its index; cannot escape the task directory. |

### SegmentManifest

| Field | Type | Rules |
|---|---|---|
| `schema_version` | integer | Exactly `1`. |
| `audio` | `ManifestAudio` | Required. |
| `segments` | ordered array of `ManifestSegment` | May be empty; indexes contiguous; intervals ordered and non-overlapping. |

The serialized document has exactly the top-level fields `schema_version`, `audio`, and `segments`. It contains no task identifier or source-media reference.

## Domain/Model entities

### CanonicalAudio

Accepted native-runner timeline facts used by pure segmentation logic. This entity does not independently certify FFmpeg output parameters.

| Field | Type | Rules |
|---|---|---|
| `total_samples` | non-negative integer | Taken from the validated native probability document. |

### VadSettings

Immutable settings for one preparation task.

| Field | Value/rule |
|---|---|
| `smooth_window_size` | `5` frames |
| `speech_threshold` | `0.4`, interpreted only by the unchanged upstream postprocessor |
| `min_speech_frames` | `20`, interpreted only by the unchanged upstream postprocessor |
| `min_silence_frames` | `20`, interpreted only by the unchanged upstream postprocessor |
| `merge_silence_frames` | `201`, interpreted only by the unchanged upstream postprocessor |
| `extend_speech_frames` | `50` |
| `split_target_frames` | Positive command-derived integer |
| `frame_length_samples` | `400` |
| `frame_shift_samples` | `160` |

### VadFrameProbability

| Field | Type | Rules |
|---|---|---|
| `frame_index` | non-negative integer | Contiguous and equal to array position. |
| `probability` | float | Finite and in `[0.0, 1.0]`. |

### SampleInterval

Intermediate speech interval after the Infrastructure adapter mechanically converts the
upstream postprocessor's timestamps to exact 16 kHz integer sample boundaries.

| Field | Type | Rules |
|---|---|---|
| `start_sample` | non-negative integer | Inclusive. |
| `end_sample` | positive integer | Exclusive and `> start_sample`. |

The Infrastructure conversion is a representation change only: it does not clamp, round to a
10-millisecond frame boundary, split, merge, or otherwise reinterpret the upstream result.
Domain accepts these intervals as authoritative and validates only positive duration, chronology,
non-overlap, and canonical-file bounds. Their internal upstream derivation remains outside the
first-party Domain model.

### FinalSpeechSegment

Manifest-ready output derived from a validated `SampleInterval`.

| Field | Type | Rules |
|---|---|---|
| `index` | non-negative integer | Contiguous in chronological order. |
| `start_sample` | non-negative integer | Inclusive; copied unchanged from `SampleInterval`; rejected if outside audio bounds. |
| `end_sample` | positive integer | Exclusive; copied unchanged from `SampleInterval`; rejected if it exceeds `total_samples`. |
| `duration_samples` | positive integer | `end_sample - start_sample`. |

The configured split target is not a maximum-duration invariant. Segment duration may exceed it if that is the pinned FireRed result.

## Infrastructure entities

### CompletedProcessData

Captures argv, completion status, stdout bytes, and stderr bytes without exposing `subprocess` objects outside Infrastructure.

### WaveMetadata

Infrastructure-local facts read while slicing or reopening a generated segment WAV: frame count, sample rate, channel count, sample width, and compression type. These facts support generated-artifact correspondence and are not used to independently validate FFmpeg's extracted output. Infrastructure never imports or constructs a Domain entity.

### FfmpegProcess

Owns absolute `vendor/ffmpeg` resolution, startup validation, decode validation, and canonical extraction. It never searches `PATH`, invokes a shell, or falls back to a library.

### FireRedNcnnProcess

Owns absolute `vendor/firered-vad-ncnn` resolution, model-asset argv construction, process execution, and native failure classification. It returns stdout/stderr bytes; it does not decode Protocol or create Domain entities.

### FireRedPostprocessor

Thinly adapts primitive probability/configuration values to the pinned unchanged upstream FireRedVAD Python postprocessor, supplies canonical duration as `wav_dur`, and returns exact adapted 16 kHz sample-boundary pairs for construction as `SampleInterval` values. It does not import Domain entities and does not reimplement, correct, clamp, or add filters around upstream state-machine behavior.

### WorkDirectory

Creates the exact task path with exclusive semantics, creates `segments/`, and refuses existing targets. It never chooses a different task identifier or location.

### WaveFileReader

Opens the extracted WAV only when segment slicing is required and exposes bounded PCM blocks. It does not perform a separate post-FFmpeg audio-parameter validation stage.

### WaveSegmentWriter

Accepts primitive `start_sample`, `end_sample`, and output-path values supplied by Service, writes one canonical-format WAV slice, then reopens it into `WaveMetadata` so Service can verify format and exact sample count. It does not import or accept `FinalSpeechSegment`.

### AtomicFileWriter

Writes a temporary file inside the task directory, flushes it, and replaces the final manifest path atomically. It is used only after all segment files validate.

## Native runner entities by layer

The first-party C++ provider follows the same layer rules as Python. Small typed functions are preferred over class hierarchies.

### Native Infrastructure

- **CanonicalWaveReader**: validates/reads canonical PCM and returns native Infrastructure metadata/sample buffers.
- **FireRedFrontendAdapter**: thinly adapts canonical PCM and explicit CMVN paths to the pinned upstream FireRedVAD C++ frontend compiled from `third_party/`. It contains no independently implemented filterbank, FFT, mel, windowing, or normalization mathematics.
- **NcnnInference**: loads the model, executes at most 30,000 frames per call, concatenates chronological probabilities, and returns an Infrastructure-local result.

These entities know nothing about command-line syntax or JSON. FireRedVAD and NCNN internals are trusted third-party implementations; only the adapter's provenance, configuration, input checks, asset use, and observable output boundary are first-party responsibilities.

### Native Protocol/Wire

- **NativeRunnerCommand**: closed validated command fields produced from controller inputs.
- **ProbabilityJsonEncoder**: accepts primitive metadata fields and the probability sequence, then writes the versioned JSON contract. It does not import Native Infrastructure types.

### Native Service

- **RunFireRedInference**: coordinates the three Native Infrastructure functions, validates counts, unpacks primitive result values, and passes them to `ProbabilityJsonEncoder`.

### Native Composition

- **build_native_application**: assembles the Native Service with concrete lower-layer functions.

### Native Controller

- **main / argument parser**: parses process arguments into `NativeRunnerCommand`, obtains the application from Composition, invokes it, and maps failures to native process status. It imports no Native Infrastructure entity.

## Service entities

### PreparationStage

```text
ARGUMENTS_VALIDATED
MEDIA_VALIDATED
WORK_DIRECTORY_CREATED
AUDIO_EXTRACTED
VAD_INFERRED
VAD_POSTPROCESSED
INTERVALS_VALIDATED
MANIFEST_CREATED
SEGMENTS_CREATED
MANIFEST_PUBLISHED
SUCCEEDED
FAILED
```

### PrepareMedia

The single use case. It receives a `PrepareCommand`, coordinates concrete lower-layer collaborators in the required order, returns a `PrepareSuccess` or `PrepareFailure`, and starts no later stage after failure.

## Composition and Controller entities

### Application / build_application

Composition entities resolve the repository root and assemble absolute model, FFmpeg, native-runner, and artifact paths. They construct `PrepareMedia` with concrete lower-layer collaborators. No downloading or fallback discovery occurs.

### CLI parser / main

Controller entities parse arguments into `PrepareCommand`, invoke `Application`, render the documented success/error text, and select process status. Controller imports Composition and Protocol only; it never imports Infrastructure.

## Aggregate relationships

```text
PrepareCommand
    └─ PrepareMedia
       ├─ FfmpegProcess ──> prepared.wav
       ├─ WorkDirectory
       ├─ FireRedNcnnProcess ──> JSON bytes
       ├─ probability codec ──> FireRedProbabilityDocument
       │                              └─ accepted timeline metadata ──> CanonicalAudio
       ├─ FireRedPostprocessor ──> primitive upstream timestamps
       │                              └─ Infrastructure maps exactly ──> SampleInterval[]
       ├─ Domain validates/copies ──> FinalSpeechSegment[]
       ├─ manifest codec ──> SegmentManifest (in memory)
       ├─ Service unpacks sample/path primitives
       │     └─ WaveFileReader / WaveSegmentWriter ──> segment WAV files + WaveMetadata
       └─ AtomicFileWriter ──> manifest.json
```

## State transitions and failure invariants

The happy path follows `PreparationStage` order exactly. `FAILED` is terminal and reachable from every nonterminal stage. No transition may skip a required predecessor.

- Failure before `WORK_DIRECTORY_CREATED` leaves the requested path absent.
- Failure after directory creation may leave completed diagnostic artifacts.
- `manifest.json` is never published unless every referenced segment exists and validates.
- An in-memory `SegmentManifest` is created and validated before segment writing, preserving the logical stage order.
- `SUCCEEDED` requires a published manifest and a `PrepareSuccess` whose segment count matches it.
