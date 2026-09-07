# Feature Specification: Segment Speech Recognition

**Feature Branch**: `002-segment-asr`

**Created**: 2026-09-06

**Status**: Draft

**Input**: User description: "Run ASR over the speech segments from a completed media preparation task, support built-in ASR models and their execution providers, and begin with Qwen3-ASR through llama.cpp."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create a transcript from prepared speech (Priority: P1)

A GUI starts an independent ASR task for an existing task work directory and a selected built-in
ASR model. The first production-usable path resolves the built-in Qwen3-ASR-1.7B model to the
shipped llama.cpp Execution Provider, reads the segment manifest, recognizes every speech segment
in order, and publishes one plain-text transcript without repeating media preparation.

**Why this priority**: Producing a usable transcript from the already-created speech segments is
the primary user value of the feature.

**Independent Test**: Given a controlled valid segment manifest, controlled speech-segment
artifacts, and a controlled execution provider, run the ASR command and verify ordered provider
invocation, progress, and exact transcript publication.

**Acceptance Scenarios**:

1. **Given** a valid task work directory with three speech segments and a supported ASR model,
   **When** the GUI starts an ASR task, **Then** all three segments are recognized in manifest
   order and their non-empty results are joined with one space in the model-specific transcript.
2. **Given** an existing complete transcript for the selected model, **When** a rerun succeeds,
   **Then** the new complete transcript atomically replaces the old transcript.
3. **Given** one segment whose successful recognition result is empty, **When** the ASR task
   completes, **Then** that segment counts as recognized and contributes neither text nor a
   separator.
4. **Given** the built-in Qwen3-ASR-1.7B manifest and its required local artifacts, **When** the GUI
   selects `qwen3-asr-1.7b`, **Then** the command resolves the fixed llama.cpp provider registration
   and can complete the production ASR path without a model download, provider build, or `PATH`
   search.

---

### User Story 2 - Preserve continuity and language intent (Priority: P2)

The GUI may select automatic language handling or provide a language tag. When the selected ASR
model supports recognition context, recent recognized text is supplied while processing the next
speech segment so sentences and terminology can continue across segmentation boundaries.

**Why this priority**: Segment boundaries are created for audio processing and should not
unnecessarily reduce transcript continuity.

**Independent Test**: Use a controlled context-capable model and provider to verify the exact
context and language value supplied for each ordered segment, including the 2,048-Unicode-code-point
boundary.

**Acceptance Scenarios**:

1. **Given** a context-capable ASR model, **When** more than 2,048 Unicode code points have
   accumulated, **Then** the next recognition receives the trailing 2,048-code-point suffix,
   unless leading-fragment removal is required after a non-whitespace Unicode-code-point cut, in
   which case the leading fragment through the first Unicode whitespace code point is discarded.
2. **Given** an ASR model without context support, **When** multiple segments are recognized,
   **Then** each recognition receives empty context.
3. **Given** a model whose language is optional, **When** the GUI omits an explicit language,
   **Then** automatic language handling is requested.
4. **Given** a model whose language is required, **When** the GUI requests automatic language
   handling, **Then** the command rejects the request before starting the execution provider.

---

### User Story 3 - Receive safe progress and actionable failures (Priority: P2)

The GUI receives one stable progress event after each successfully recognized speech segment and
a final transcript location on success. Failures identify the failed stage, selected model, and
segment when applicable, while preserving any prior complete transcript.

**Why this priority**: Recognition and model loading can take long enough that the GUI needs
reliable progress and errors without parsing execution-provider logs.

**Independent Test**: Drive each controlled failure boundary and cancellation point, verifying
status, bounded error output, provider cleanup, progress suppression after failure, and preservation
of an existing transcript.

**Acceptance Scenarios**:

1. **Given** ten valid speech segments, **When** the first three are recognized, **Then** the GUI
   receives exactly three monotonically increasing recognition progress events.
2. **Given** an execution-provider error on the Speech Segment with zero-based Segment Manifest index 3 (the fourth segment), **When** recognition fails, **Then** the command returns a runtime failure quoting the escaped, bounded provider message and publishes no replacement transcript.
3. **Given** an active ASR task, **When** the GUI cancels it, **Then** the execution provider is
   stopped, temporary output is removed, and any previous complete transcript remains unchanged.
4. **Given** a provider that does not become ready within 60 seconds or a segment that does not
   complete within 180 seconds, **When** the timeout expires, **Then** the task fails clearly and
   the provider is stopped.

---

### User Story 4 - Validate built-in model availability safely (Priority: P3)

After the production Qwen selection path exists, the system validates every built-in ASR Model
Manifest and local prerequisite deterministically. Unknown model IDs, invalid manifests, and
missing model or Execution Provider files fail before provider startup or Transcript mutation. The
same boundary can admit a later valid built-in model registration without changing Transcript
assembly behavior.

**Why this priority**: The US1 production path supplies the initial Qwen3-ASR value. This story
hardens availability and extension behavior without delaying that MVP.

**Independent Test**: Resolve controlled model manifests and Execution Provider registrations,
verifying every invalid manifest, missing artifact, missing provider, unknown model outcome, and a
second valid built-in registration without contacting a network service or changing Transcript
assembly behavior.

**Acceptance Scenarios**:

1. **Given** an unknown model ID, **When** an ASR task is requested, **Then** the command rejects it
   before reading or changing transcript output.
2. **Given** a known model whose required files or execution provider are missing, **When** an ASR
   task is requested, **Then** the command reports every missing prerequisite before provider
   startup, ordered as the provider executable followed by model artifacts in ASR Model Manifest
   declaration order.
3. **Given** a malformed built-in ASR Model Manifest, **When** application resources are loaded,
   **Then** its structural or semantic contract violation is rejected deterministically before
   artifact installation state is inspected.
4. **Given** another valid built-in ASR Model Manifest and compatible Execution Provider
   registration, **When** the model is selected, **Then** no ASR Task Transcript assembly rule
   changes.

### Edge Cases

- A valid Segment Manifest contains no Speech Segments; the command reports a runtime failure with public stage `segment-manifest` and does not start an Execution Provider or publish a Transcript.
- A segment path differs from its exact index-derived `segments/segment-NNNN.wav` form, resolves
  outside `TASK_WORK_DIRECTORY/segments/`, is missing, or does not match its
  manifest duration or canonical audio format; preflight fails before provider startup.
- Recognition succeeds for every segment but every result is empty; an empty transcript file is
  valid because input speech segments were processed.
- Provider output is malformed, omits transcript text, contains an unknown control prefix, or is
  not valid text; the task fails at the provider-response boundary.
- Provider diagnostics contain line breaks, quotes, control characters, or excessive output; the
  public error remains one bounded, escaped line.
- A model-specific transcript directory does not yet exist; it is created only as needed for final
  publication.
- Two commands operate on the same task directory and model at once; simultaneous invocation is
  unsupported and no locking behavior is promised.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose an independent ASR command that accepts an existing task work
  directory and a required ASR model ID. A model ID MUST consist of non-empty lowercase ASCII
  letter-or-digit components separated by a single hyphen or dot, with no leading, trailing,
  repeated, or adjacent separators.
- **FR-002**: The command MUST accept an optional language value of `auto` or a tag in the supported
  language-tag grammar, defaulting to `auto`. The supported grammar is an ASCII alphabetic primary
  subtag of 2-8 characters followed by zero or more hyphen-separated ASCII alphanumeric subtags of
  1-8 characters. Grandfathered and private-use-only forms are outside this feature.
- **FR-003**: The system MUST read and validate the task work directory's segment manifest without
  rerunning media preparation.
- **FR-004**: Before provider startup, the system MUST validate that every referenced segment path
  equals its exact index-derived `segments/segment-NNNN.wav` form, that its resolved filesystem
  target remains beneath `TASK_WORK_DIRECTORY/segments/`, and that the target exists with canonical
  audio properties and the exact manifest duration.
- **FR-005**: Before provider startup, the system MUST resolve the selected built-in ASR Model
  Manifest and its Execution Provider and report all missing required files. The failure MUST list
  the project-relative provider executable first, followed by missing project-relative model
  artifact paths in ASR Model Manifest declaration order, with every path JSON-string escaped.
- **FR-006**: A segment manifest containing zero speech segments MUST fail as missing input data.
- **FR-007**: The system MUST start one Execution Provider for the ASR task, process every valid
  Segment Manifest entry sequentially in segment-manifest order, and stop the provider in every
  terminal outcome. Provider shutdown MUST allow at most 60 seconds for graceful termination; if
  the provider remains alive, the system MUST force termination and reap the process within an
  additional 10 seconds. Controlled acceptance coverage of 1–100 Speech Segments MUST NOT impose
  a production segment-count cap.
- **FR-008**: The system MUST supply empty Recognition Context for the first segment and for every
  segment processed by a model without context support.
- **FR-009**: For a context-capable model, the system MUST derive Recognition Context from
  accumulated Transcript Unicode code points. If the Transcript contains at most 2,048 code
  points, the system MUST supply the complete Transcript. Otherwise, the system MUST take its
  trailing 2,048-code-point suffix. Python `str.isspace()` semantics govern leading-fragment
  removal after a non-whitespace Unicode-code-point cut. If the cut falls between two
  non-whitespace code points, the system MUST discard the leading fragment through the first
  Unicode whitespace character; if no such character exists, Recognition Context MUST be empty.
  The system MUST remove any remaining leading Unicode whitespace. Punctuation and hyphens do not
  create a Unicode-whitespace boundary. For example, with a limit of 8,
  `"alpha beta"` supplies `"beta"`; with a limit of 4, `"alpha beta"` supplies `"beta"`,
  `"alpha-beta"` supplies empty context, and `"甲乙丙丁"` supplies empty context when the limit
  is 3.
- **FR-010**: Each successful segment result MUST be trimmed; non-empty results MUST be joined with
  one ordinary space, while empty results MUST remain valid and contribute no separator.
- **FR-011**: A model whose language behavior is `required` MUST reject `auto`; a model whose
  language behavior is `optional` MUST allow automatic handling or an explicit language tag.
- **FR-012**: Language-to-model matching and a model-specific supported-language catalog MUST NOT
  be part of this feature.
- **FR-013**: After each successful segment, the command MUST emit exactly one recognition-progress
  record containing the completed and total segment counts.
- **FR-014**: On success, the system MUST atomically publish `transcript.txt` under the one-level
  directory `transcripts-{model-id}` and emit its absolute path.
- **FR-015**: A non-empty transcript MUST be UTF-8 text with exactly one trailing newline; a
  transcript assembled entirely from empty results MUST contain zero bytes.
- **FR-016**: A failed or cancelled task MUST NOT replace or remove a previous complete transcript
  and MUST remove temporary output created by the attempt.
- **FR-017**: Provider readiness MUST time out after 60 seconds and recognition of one speech
  segment MUST time out after 180 seconds.
- **FR-018**: A provider failure MUST identify the selected model and, when the failure is
  segment-specific, the zero-based Segment Manifest index. The complete public failure line MUST
  contain at most 1,023 Python Unicode code points excluding its terminating LF. The renderer MUST
  JSON-escape every dynamic string value. When truncating a quoted provider diagnostic, the
  renderer MUST preserve the closing quote and include the `...[truncated]` marker defined in the
  CLI contract.
- **FR-019**: Invalid command arguments, including a model ID that violates FR-001, MUST return
  status 2; a syntactically valid model ID that is not registered MUST reach application resolution
  and return runtime status 1; successful completion MUST return status 0.
- **FR-020**: Built-in ASR Model Manifests MUST declare `schema_version: 1` for this feature and remain available independently of model artifact installation. The schema version identifies the manifest contract; a separate model-artifact version field is outside this feature.
- **FR-021**: Each ASR Model Manifest MUST define a stable model ID conforming to FR-001, display
  name, source URL, required artifact file structure with artifact roles and checksums, Execution
  Provider ID, context support, and `optional` or `required` language behavior.
- **FR-022**: Execution Provider IDs MUST resolve through a built-in registry to fixed application-
  shipped paths; the command MUST NOT search the host's executable path.
- **FR-023**: The initial built-in model MUST be Qwen3-ASR-1.7B using the built-in llama.cpp
  Execution Provider.
- **FR-024**: The initial provider adapter MUST preserve Recognition Context, requested language,
  and speech-segment audio in its provider request and MUST return only recognized text, excluding
  provider/model control metadata.
- **FR-025**: The ASR task MUST operate without external network access.
- **FR-026**: Segmentation and ASR MUST remain separate commands. The GUI, rather than either
  command, owns sequencing and MUST make ASR available only after segmentation reports success.

### Key Entities

- **ASR Task**: One attempt to process every Speech Segment in a Segment Manifest with one selected
  ASR Model; it owns ordered progress, accumulated Transcript, provider lifecycle, and terminal
  success or failure.
- **ASR Model**: A supported speech-recognition model selected by stable model ID.
- **ASR Model Manifest**: The built-in description of an ASR Model, its required artifact file
  structure, capabilities, source, and Execution Provider dependency.
- **Execution Provider**: A shipped runtime that loads an ASR Model and recognizes Speech Segments.
- **Recognition Context**: Recent accumulated Transcript supplied when recognizing the next Speech
  Segment with a context-capable ASR Model.
- **Transcript**: Plain text assembled from successful segment recognition results in Segment
  Manifest order.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Controlled successful inputs spanning 1–100 Speech Segments prove that 100% of
  segments are processed exactly once in manifest order and the final Transcript matches the
  defined assembly rules. Production processes every valid Segment Manifest entry and has no
  100-segment cap.
- **SC-002**: Every successful task emits exactly one progress event per speech segment and one
  final transcript location; no failure emits a final transcript location.
- **SC-003**: A controlled failure matrix covering every documented preflight, startup, recognition,
  timeout, malformed-response, publication, and cancellation boundary demonstrates that 100% of
  cases preserve any previous complete Transcript and leave no temporary Transcript artifact.
- **SC-004**: Controlled-clock tests demonstrate that provider readiness reaches its deadline at 60
  seconds, one Speech Segment recognition reaches its deadline at 180 seconds, and both deadline
  paths begin provider cleanup without relying on wall-clock sleeps.
- **SC-005**: A new built-in model can be represented by one valid ASR Model Manifest and one
  existing or new Execution Provider registration without changing the ASR task's transcript
  assembly behavior.
- **SC-006**: The required real-provider integration run completes locally with the pinned Qwen3-ASR
  artifacts and shipped llama.cpp provider, proving invocation, request construction, response
  parsing, cleanup, and transcript publication without using model accuracy as an acceptance gate.

## Assumptions

- Media preparation has already completed and owns creation of the task work directory, segment
  manifest, and speech-segment WAV artifacts.
- GUI enablement logic uses the successful segmentation result to decide when ASR may be launched;
  implementing that GUI state transition is outside this middleware feature.
- Task work directories and model artifacts are local to the machine running the command.
- Speech Segment files are application-owned temporary artifacts. Mutation by an external actor
  after the successful pre-start batch validation is outside this feature's threat model.
- The GUI launches one ASR task for a given task directory and model at a time; simultaneous
  invocation is unsupported.
- Model downloading, model-to-language matching, Execution Provider installation, provider builds,
  distribution packaging, and release assembly are separate capabilities.
- Word timestamps, utterance timestamps, diarization, batching, concurrent recognition, model
  catalog listing, and combined preparation/recognition orchestration are outside this feature.
- Third-party ASR accuracy, quality, and performance are not first-party acceptance criteria;
  real-provider semantic tests do not assert recognized words, non-empty output, WER, language
  correctness, latency, throughput, or provider/model internals. Controlled fixtures retain exact
  Transcript-content and non-empty assembly assertions for project-owned behavior.
