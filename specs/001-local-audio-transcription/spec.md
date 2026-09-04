# Feature Specification: Media Audio Segmentation Middleware

**Feature Branch**: `codex/media-audio-segmentation`

**Created**: 2026-08-15

**Updated**: 2026-09-04

**Status**: Draft

**Input**: User description: Middleware first validates a media file with the repository-bundled `vendor/ffmpeg` executable, creates a task work directory at a supplied path, extracts audio in the format required by Qwen-ASR, uses non-streaming FireRedVAD through NCNN inference to create a speech-segment manifest, and creates one WAV file per final segment. FireRedVAD model assets are supplied in `models/firered-vad.ncnn`. Detection runs on the complete audio timeline with a 10-millisecond frame shift and the upstream default `min_speech_frame=20` and `min_silence_frame=20` settings. The `--max-segment-duration-seconds` command parameter supplies a preferred FireRedVAD split target rather than a strict upper bound; a final segment may exceed that target. FireRedVAD's pinned preprocessing, inference, and postprocessing implementations are trusted third-party code and are used unchanged; the middleware adapts their inputs and outputs without correcting or independently redefining their internal frame-counting or mathematical behavior. The middleware exposes only a command-line interface. `fixtures/sample/prepared.wav` is the target audio sample for fixture-backed integration, while `fixtures/sample/manifest.json` is available only for a non-gating diagnostic comparison.

### Current Delivery Scope

This specification covers the first middleware delivery through a command-line interface only: media validation, canonical audio extraction, voice activity detection, final speech-segment planning, manifest creation, and segment WAV creation. Qwen-ASR transcription consumes these artifacts in a later roadmap phase and is not executed by this delivery.

## Clarifications

### Session 2026-08-31

- Q: Which serialization format should the segment manifest use? → A: One JSON document containing metadata and a `segments` array.
- Q: How should each segment store its start and end positions in the JSON manifest? → A: Integer start and end sample indexes.
- Q: Which task-level information should the JSON manifest contain in addition to the `segments` array? → A: Schema version and canonical-audio metadata only.
- Q: How should each segment be identified within the manifest? → A: A zero-based integer `index` matching its array position.
- Q: How should `schema_version` be represented and advanced? → A: A positive integer starting at `1`, incremented only for backward-incompatible schema changes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validate Media and Extract Canonical Audio (Priority: P1; Implementation Checkpoint)

As a middleware implementer, I can validate the media-ingestion boundary independently so that the complete CLI later verifies decodable audio and creates a configured sound file for the VAD and ASR phases. This checkpoint is not exposed as a separate supported CLI command.

**Why this priority**: Every later stage requires a verified source and a predictable sound format. This story provides a useful, independently testable media-ingestion capability.

**Independent Test**: Use controlled process results to verify the repository-bundled FFmpeg path, exact extraction configuration, decode-before-directory ordering, exclusive task-directory creation, and failure translation. Do not inspect FFmpeg-produced audio parameters or assert intrinsic properties of a user-supplied fixture.

**Acceptance Scenarios**:

1. **Given** a readable media file containing a decodable audio stream and an unused writable task path, **When** the user starts media preparation, **Then** the middleware validates audio decoding before creating the task directory and writes a canonical sound file inside that directory.
2. **Given** a missing, unreadable, corrupt, unsupported, or audio-free media file, **When** the user starts media preparation, **Then** validation fails with an actionable media error and the requested task directory is not created.
3. **Given** a valid media file but a task path that cannot be created safely, **When** validation succeeds and workspace creation begins, **Then** the operation fails with an actionable work-directory error and audio extraction does not begin.
4. **Given** a media file containing video and a decodable audio stream, **When** preparation succeeds, **Then** one audio stream is decoded without copying video into the task artifacts.

---

### User Story 2 - Create a Speech Manifest and Segment WAV Files (Priority: P2)

As a developer or later ASR stage, I receive a machine-readable manifest and speech-focused WAV files produced with a configurable advisory split target so they are suitable inputs for later transcription without promising a strict context-window fit.

**Why this priority**: Segmentation produces the direct inputs for Qwen-ASR and is the principal output of this roadmap phase.

**Independent Test**: Verify that the pinned upstream C++ frontend is compiled into the runner, the supplied `fixtures/sample/prepared.wav` path is handed to and accepted by the runner without an independent fixture-property inspection, and the supplied CMVN and NCNN assets load. For input longer than one internal inference chunk, verify only that the runner returns one schema-valid public probability document whose reported frame count equals its probability-array length. Verify that the middleware passes the returned probabilities and pinned settings once to the unchanged upstream postprocessor. Verify only middleware adaptation and output-artifact behavior, not fixture correctness, expected model output, FireRedVAD frame-count or chunking mathematics, probability ordering, or segmentation quality.

**Acceptance Scenarios**:

1. **Given** the supplied `fixtures/sample/prepared.wav`, pinned upstream C++ frontend, and supplied CMVN and NCNN assets, **When** the native runner executes, **Then** the fixture path crosses the boundary unchanged, the runner accepts it under its own input contract, and its public probability document is schema-valid with its reported frame count equal to the probability-array length.
2. **Given** a sound file for which the unchanged upstream FireRedVAD postprocessor returns no intervals, **When** segmentation completes, **Then** the manifest contains an empty segment list and no segment WAV files are created.
3. **Given** ordered valid intervals returned by the unchanged upstream postprocessor, including a short positive-duration remainder, **When** segment files are created, **Then** the middleware preserves every interval and its order, and every manifest record references one readable WAV file whose audio and duration match that record.
4. **Given** canonical input longer than one internal inference chunk, **When** the native runner executes, **Then** it returns one public probability document whose reported `frame_count` equals the number of serialized probabilities; the test does not derive an expected count or assert probability values or ordering.

### Edge Cases

- The source path is missing, unreadable, a directory, empty, corrupt, unsupported by the bundled media decoder, or contains no decodable audio stream.
- The repository-bundled `vendor/ffmpeg` executable is missing, not executable, or incompatible with the host; the task fails with an actionable dependency error and does not fall back to a system FFmpeg executable or library.
- The supplied task path already exists, is not a directory, is not writable, or has a missing or unwritable parent.
- Audio extraction starts but the source becomes unavailable, the decoder fails, or storage becomes full.
- FFmpeg reports successful extraction but the produced file cannot be opened by the native VAD runner; the task fails at the VAD input boundary without a separate middleware check of FFmpeg output parameters.
- A required FireRedVAD model asset or the NCNN inference dependency is missing, unreadable, incompatible, or fails during detection.
- Audio is longer than one FireRedVAD inference chunk; chunking must preserve one continuous frame timeline and postprocessing must not reset at chunk boundaries.
- The split-target argument is missing its value, is not numeric, is shorter than one 10-millisecond VAD frame shift, is infinite, or is not a number; argument validation fails before media validation or work-directory creation.
- The split-target argument is valid but not aligned to a whole 10-millisecond VAD frame shift; its effective FireRedVAD frame count is rounded down.
- The pinned upstream postprocessor returns an interval at a file edge, across a long silence, longer than the configured advisory split target, or near one of its internal decision boundaries; the middleware preserves that result unless it violates the middleware-owned interval invariants.
- VAD postprocessing produces overlapping, out-of-order, zero-duration, or out-of-file detected intervals; invalid detection output must not produce a successful manifest.
- A segment file cannot be created after its interval was planned; the task must not report success or leave a manifest that claims all files are complete.
- A command-line invocation fails after its task directory is created; it must return an unsuccessful completion status without presenting incomplete artifacts as successful.
- The target sample differs from `fixtures/sample/manifest.json`; the required non-gating diagnostic reports count and boundary differences, but those differences do not fail an acceptance test or alter generated output.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The middleware MUST accept a readable local media-file path and a caller-supplied task work-directory path for each preparation task.
- **FR-002**: The middleware MUST use the repository-bundled executable at `vendor/ffmpeg` to verify that the source is supported and that at least one audio stream can be decoded before creating the task work directory. Media validation and canonical audio extraction MUST invoke that repository-bundled executable.
- **FR-003**: Media validation MUST fail when audio stream metadata is present but audio samples cannot actually be decoded.
- **FR-004**: A media-validation failure MUST NOT create the requested task work directory or begin audio extraction.
- **FR-005**: After media validation succeeds, the middleware MUST create the task work directory at the exact caller-supplied path and MUST refuse to overwrite or reuse an existing path.
- **FR-006**: The middleware MUST extract one audio stream into one canonical sound file inside the task work directory without including video data. Selecting, comparing, or processing multiple source audio streams is outside the current delivery scope.
- **FR-007**: The canonical sound file MUST be mono, 16 kHz, signed 16-bit PCM WAV audio so it is directly usable by non-streaming FireRedVAD and the later Qwen-ASR phase.
- **FR-008**: After FFmpeg reports successful extraction, the middleware MUST pass the extracted file to the native VAD runner without independently inspecting or validating FFmpeg-produced sample rate, channel count, sample format, or duration. The native runner's canonical-input contract remains authoritative for accepting or rejecting VAD input.
- **FR-009**: The middleware MUST use the local non-streaming FireRedVAD model through a compatible NCNN inference dependency to produce speech probabilities for the canonical sound file.
- **FR-010**: The middleware MUST validate FireRedVAD postprocessed intervals as ordered, positive-duration ranges within the canonical sound-file bounds before deriving final segments.
- **FR-011**: The middleware MUST create the manifest as one JSON document with exactly three top-level fields: `schema_version`, `audio`, and `segments`. `schema_version` MUST be the positive integer `1` for the current schema and MUST increase only when a future schema change is backward-incompatible. The `audio` object MUST contain `path` as the canonical sound file's work-directory-relative path, `sample_rate_hz` as `16000`, `channels` as `1`, `sample_format` as `"pcm_s16le"`, and `total_samples` as a non-negative integer. The manifest MUST NOT contain a task identifier or source-media reference.
- **FR-012**: Every non-empty manifest record MUST contain a zero-based integer `index` equal to its position in the `segments` array, inclusive integer `start_sample`, exclusive integer `end_sample`, integer `duration_samples` equal to `end_sample - start_sample`, and `path` as the work-directory-relative path of its corresponding segment WAV file.
- **FR-013**: The middleware MUST create exactly one segment WAV file for every non-empty manifest record and MUST derive that file from the matching interval of the canonical sound file.
- **FR-014**: Every segment WAV file MUST retain the canonical sound file's mono, 16 kHz, signed 16-bit PCM WAV format.
- **FR-015**: On successful completion, every manifest file reference MUST resolve inside the task work directory to a readable segment WAV file, and no unreferenced segment WAV file may be reported as task output.
- **FR-016**: When no speech is detected, the middleware MUST create a valid manifest with an empty segment list and MUST create no segment WAV files.
- **FR-017**: The stages MUST run in this order: command-argument validation, media validation, task work-directory creation, canonical audio extraction, non-streaming FireRedVAD NCNN inference, unchanged FireRedVAD postprocessing with the configured settings, postprocessed-interval validation, in-memory manifest assembly, segment WAV creation and verification, and atomic manifest publication.
- **FR-018**: Failure at any stage MUST prevent all later stages from starting. Its message MUST identify the failed stage and the relevant failing path, asset, argument, or operation class; normal command-line failure output MUST contain neither a raw traceback nor unbounded external diagnostics.
- **FR-019**: The middleware MUST provide a command-line mode that runs the complete current-delivery workflow, accepts an optional `--max-segment-duration-seconds` parameter, and distinguishes success from failure through its process completion status. The parameter MUST default to `30.0` when omitted and MUST be rejected unless it is finite and at least one FireRedVAD frame shift (`0.01` seconds). A valid value not aligned to a whole 10-millisecond frame shift MUST be rounded down to the nearest whole-frame target before VAD postprocessing. Despite its historical name, this parameter is a preferred split target and MUST NOT be treated as a strict output-duration limit.
- **FR-020**: On successful completion, the command-line interface MUST report the task work directory, canonical sound file, manifest file, and number of segment WAV files.
- **FR-021**: A failure MUST identify whether it concerns command arguments, source media, task directory, audio extraction, FireRedVAD model assets, NCNN inference dependency, VAD inference, VAD postprocessing, interval planning, manifest creation, or segment-file creation.
- **FR-022**: The middleware MUST NOT download models, execution providers, decoders, or other assets and MUST NOT require a network connection for the current-delivery workflow.

### FireRedVAD Integration and Segment Boundary Rules

- **FR-023**: Every final speech segment MUST have a positive duration. The configured duration is an advisory split target, and a final segment MAY exceed it when returned by the pinned upstream FireRedVAD postprocessor.
- **FR-024**: The native runner MUST compile and invoke the preprocessing/frontend source from the pinned FireRedVAD revision unchanged; first-party code MUST be limited to input, asset, inference, and protocol adaptation.
- **FR-025**: The native runner MUST accept mono 16 kHz signed-16-bit PCM WAV input for the frontend and MUST reject input that does not satisfy its canonical-audio boundary contract.
- **FR-026**: The native runner MUST return one public probability document containing its reported input metadata, reported non-negative `frame_count`, and one finite probability array whose length equals that reported count. The middleware MUST validate this public-document coherence and MUST NOT independently derive an expected frame count from the input audio or FireRedVAD frontend mathematics.
- **FR-027**: First-party tests MUST validate the pinned frontend's source/build provenance, canonical input handoff, public probability schema, and reported-count/array-length coherence, including for input longer than one internal inference chunk. They MUST NOT reproduce or independently verify FireRedVAD or NCNN feature extraction, expected model output, inference values, frame-count or chunking mathematics, probability ordering, segmentation quality, or other numerical behavior.
- **FR-028**: The middleware MUST vendor or otherwise load the postprocessor source from the pinned FireRedVAD revision unchanged and invoke it through a thin adapter.
- **FR-029**: The middleware MUST pass `smooth_window_size=5`, `speech_threshold=0.4`, `min_speech_frame=20`, `min_silence_frame=20`, `merge_silence_frame=201`, `extend_speech_frame=50`, and the command-derived `max_speech_frame` to the unchanged upstream postprocessor.
- **FR-030**: Final segments MUST be ordered by `start_sample`, MUST NOT overlap, and MUST remain within the canonical sound-file bounds.
- **FR-031**: The middleware MUST preserve every upstream postprocessor interval, including a short positive-duration remainder, in its original order and with its original boundaries except for required frame-to-sample conversion and validation against positive-duration, ordering, non-overlap, and file-bound invariants.
- **FR-032**: The native runner MUST accept canonical input longer than one internal inference chunk and return one public probability document for that invocation. Middleware tests MUST verify only that the document is accepted under the public schema and its reported `frame_count` equals the probability-array length; they MUST NOT independently verify internal chunk boundaries, chunk concatenation, probability ordering, or expected frame count. The middleware MUST pass the returned probability array to postprocessing once.
- **FR-033**: The middleware MUST treat the pinned FireRedVAD preprocessing, NCNN inference, and postprocessing implementations as trusted third-party code. It MUST NOT reimplement, patch, correct, reinterpret, or add a second decision algorithm around their mathematical or state-machine behavior.
- **FR-034**: Tests of the postprocessor adapter MUST be limited to pinned-source provenance, exact configuration, complete chronological input handoff, primitive output shape/order preservation, and failure translation. They MUST NOT independently calculate or assert upstream threshold, minimum-frame, merge, extension, or split decisions.
- **FR-035**: The middleware MUST pass the effective whole-frame value derived from `--max-segment-duration-seconds` to the unchanged upstream postprocessor as `max_speech_frame` exactly once and MUST preserve the returned valid intervals without applying a first-party splitting algorithm or asserting how FireRedVAD chooses split boundaries.

### Integration Examples

1. If the unchanged upstream postprocessor returns no intervals, the middleware creates an empty manifest and zero segment WAV files.
2. If the unchanged upstream postprocessor returns a segment longer than the configured advisory split target, the middleware retains it when its interval is otherwise valid.
3. If a mocked upstream result contains an ordinary interval followed by a short positive-duration remainder, the middleware retains both intervals without testing or reconstructing FireRedVAD's splitting decision.
4. For any valid returned interval, the generated WAV has exactly the sample count declared by its manifest record.

### Required Non-Gating Sample Diagnostic

The required fixture-backed integration run MUST emit exactly one diagnostic line comparing the generated manifest with `fixtures/sample/manifest.json` in this form:

```text
REFERENCE_DIAGNOSTIC={"actual_segment_count":N,"reference_segment_count":M,"paired_boundary_deltas":[{"index":I,"start_delta_samples":S,"end_delta_samples":E}]}
```

Let `N` be the generated manifest's segment count and `M` the reference manifest's segment count. `paired_boundary_deltas` MUST contain one entry for every zero-based index `I` from `0` through `min(N, M) - 1`, in ascending order, pairing the generated and reference records at that same array index. `start_delta_samples` MUST equal `actual.start_sample - reference.start_sample`, and `end_delta_samples` MUST equal `actual.end_sample - reference.end_sample`. The array MUST be empty when `min(N, M) == 0`; unpaired trailing records are represented only by the two segment counts. The line uses compact JSON encoding. Controlled manifest data MUST verify this first-party diagnostic mapping, while numeric values from the fixture-backed run remain informational: segment-count or boundary differences MUST NOT determine acceptance-test status, change middleware output, or be presented as proof of FireRedVAD quality or correctness.

### Key Entities

- **Media Preparation Task**: One command-line invocation that transforms a source media file into ASR-ready local artifacts; includes its source path, task work-directory path, configured split target, stage, and final outcome.
- **Canonical Sound File**: The mono 16 kHz signed 16-bit PCM WAV audio requested from the one source audio stream used by this invocation and passed to the native VAD runner and segment cutting.
- **VAD Frame Probability**: One non-streaming FireRedVAD speech likelihood on the complete canonical-audio timeline, emitted every 10 milliseconds from a 25-millisecond analysis window and interpreted through the pinned FireRedVAD postprocessing settings.
- **Detected Speech Interval**: A start/end range returned by the unchanged pinned FireRedVAD postprocessor and validated only against middleware-owned ordering and file-bound invariants.
- **Final Speech Segment**: A valid chronological FireRedVAD interval converted to sample-aligned manifest boundaries without changing its boundaries; invalid, overlapping, non-positive, or out-of-file intervals are rejected. Its manifest identity is its zero-based array `index`, and its canonical boundaries are inclusive start and exclusive end sample indexes.
- **Segment Manifest**: One JSON document containing `schema_version`, canonical `audio` metadata, and an ordered `segments` array of final speech segments with their corresponding segment-file references; it excludes task and source-media identity, and an empty array represents valid no-speech input.
- **Segment WAV File**: A canonical-format audio slice whose boundaries and relative path match exactly one manifest record.

### Affected Product Components

- Command-line interaction for media-preparation tasks.
- FFmpeg media validation and canonical audio extraction boundary.
- Task work-directory and artifact management.
- Non-streaming FireRedVAD and NCNN inference boundary.
- Thin adaptation around unchanged FireRedVAD postprocessing, followed by middleware-owned speech-interval validation.
- Manifest serialization and WAV segment creation.
- Automated unit, contract, failure-path, and fixture-backed integration acceptance tests limited to middleware-owned boundary behavior.

### Dependencies

- The repository supplies the `vendor/ffmpeg` executable used for media validation, audio decoding, and canonical audio extraction.
- Non-streaming FireRedVAD NCNN assets are supplied locally at `models/firered-vad.ncnn`: `firered_vad_non_stream.ncnn.param`, `firered_vad_non_stream.ncnn.bin`, `cmvn_means.bin`, and `cmvn_istd.bin`.
- A compatible local NCNN runtime is required to load and execute the model. Its official build and runtime reference is [FireRedVAD NCNN Runtime](https://github.com/FireRedTeam/FireRedVAD/tree/main/runtime/ncnn).
- FireRedVAD's official non-streaming configuration and postprocessing behavior are defined by [FireRedVAD `vad.py`](https://github.com/FireRedTeam/FireRedVAD/blob/main/fireredvad/vad.py) and its associated postprocessor.
- Qwen-ASR model assets remain in `models/qwen-asr`; they define the downstream-compatible audio format but are not loaded in this delivery.
- The llama.cpp execution provider remains in `ep/llama.cpp`; it is not invoked in this delivery.
- `fixtures/sample/prepared.wav` is the supplied target audio fixture for integration and acceptance tests. Tests treat the fixture as supplied and do not independently assert its intrinsic audio parameters or duration.
- `fixtures/sample/manifest.json` is a human reference used for the required non-gating diagnostic line during fixture-backed integration; it is not an acceptance oracle.
- `fixtures/sample/segments/*.wav` are sample-exact reference slices for inspecting or diagnosing the target fixture; generated files are not required to match these files byte-for-byte.

### Explicit Non-Goals

- Qwen-ASR execution, transcript generation, transcript combination, or transcript-quality evaluation.
- Building, invoking, modifying, or maintaining the llama.cpp execution provider.
- Downloading, selecting, converting, training, or updating models or dependencies.
- Speaker diarization, speaker labels, language identification, translation, summarization, subtitles, or other enrichment.
- GUI, worker, or API interface design and implementation.
- Selection, comparison, simultaneous processing, or reporting of multiple source audio streams.
- Remote service deployment, authentication, multi-user access, persistent job scheduling, or parallel task execution.
- Retrying failed external operations automatically or resuming a partially completed task.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the required fixture-backed integration run using `fixtures/sample/prepared.wav` and valid local dependencies, the command-line interface creates a task directory, extracted sound file, schema-valid manifest containing ordered valid intervals, and matching segment WAV files without asserting expected FireRedVAD segmentation, independently testing the supplied fixture, or inspecting FFmpeg's output parameters.
- **SC-002**: In every successful run, every segment duration is greater than 0, every generated segment WAV matches its manifest interval, and every segment boundary matches the pinned FireRedVAD postprocessing result even when a duration exceeds the configured split target.
- **SC-003**: Automated integration tests verify the pinned upstream frontend is compiled unchanged, the supplied `prepared.wav` path is handed to and accepted by the runner without independent fixture inspection, all supplied CMVN and NCNN assets load, and the public probability document's reported count equals its probability-array length, including for long input. Exact postprocessor settings are passed once and returned intervals are preserved without a first-party decision algorithm, expected-output oracle, or chunk-order assertion.
- **SC-004**: Every tested missing, unreadable, corrupt, unsupported, and audio-free source fails media validation before the requested task work directory is created.
- **SC-005**: In 100% of successful non-empty tasks, the number of manifest records equals the number of reported segment files, every referenced file exists and is readable, and each file's duration matches its manifest interval within one audio sample.
- **SC-006**: All acceptance failures report the correct failed stage plus the relevant failing path, asset, argument, or operation class, contain no raw traceback, and do not report the task as successful.

## Assumptions

- This roadmap phase ends after segment WAV creation. Transcription is a later feature phase and will consume the manifest and segment files.
- The caller supplies the exact task work-directory path. Its parent exists and is writable, and the task path itself must not already exist.
- Each invocation extracts exactly one audio stream. The CLI exposes no stream-selection option, and selecting, comparing, processing, or reporting multiple source audio streams is outside scope.
- `vendor/ffmpeg` is resolved relative to the repository root, not relative to the caller's current working directory or through the operating-system executable search path.
- Mono 16 kHz signed 16-bit PCM WAV is the canonical format accepted by the supplied VAD model and expected by the later Qwen-ASR phase.
- Manifest segment boundaries are zero-based integer sample indexes relative to the start of the canonical sound file. `start_sample` is inclusive and `end_sample` is exclusive, allowing exact sample-aligned cuts without time rounding.
- The manifest is serialized as one JSON document. Its artifact filename will be fixed during planning; consumers rely on manifest fields and relative references rather than inferred filenames.
- The manifest is an audio-artifact contract rather than a task audit record, so source-media references remain in command-line task state rather than the manifest.
- The current manifest schema version is integer `1`; future backward-compatible changes retain the same version, while backward-incompatible changes increment it.
- FireRedVAD uses a 25-millisecond analysis window with a 10-millisecond frame shift. “Frame” in VAD threshold, merging, and extension requirements means the 10-millisecond decision cadence.
- The pinned unchanged FireRedVAD postprocessor receives a five-frame smoothing window, a `0.4` speech-probability threshold, `min_speech_frame=20`, `min_silence_frame=20`, `merge_silence_frame=201`, and `extend_speech_frame=50`; upstream semantics for those settings are authoritative.
- The preferred split target is configurable through `--max-segment-duration-seconds` and defaults to `30.0`. It is converted to a whole number of 10-millisecond frames and supplied as FireRedVAD's `max_speech_frame`; it is explicitly not a strict final-duration limit.
- The middleware does not translate `min_speech_frame=20` into a separate duration rule and does not filter short pieces returned by the upstream splitter.
- Arbitrarily long canonical audio may be divided into bounded inference chunks by the trusted provider. Middleware tests treat this as internal behavior and verify only one public document with `frame_count == len(probabilities)` for long input plus one postprocessor invocation with the returned array.
- The runner reports `audio.total_samples` and `frames.frame_count` in its public probability document. Middleware validation checks only that the document is schema-valid and `frame_count` equals the probability-array length; it does not derive the expected count from the audio timeline.
- The target sample and reference manifest remain immutable supplied fixtures. Their required diagnostic comparison uses the defined `REFERENCE_DIAGNOSTIC` line and cannot fail acceptance or trigger output correction because of segment-count or boundary differences.
- Third-party tools and supplied fixtures are trusted inputs. Tests cover middleware adaptation, configuration, failure translation, interval validation, and artifact correspondence; they do not independently test FFmpeg behavior, FireRedVAD/NCNN mathematics, or the intrinsic correctness of supplied fixtures.
- On a failure after task-directory creation, the task is unsuccessful and may retain completed intermediate artifacts for diagnosis, but no incomplete manifest may be presented as a successful result.
- The first delivery serves one local command-line user. Each invocation processes one task; internal parallel task execution is outside scope.
