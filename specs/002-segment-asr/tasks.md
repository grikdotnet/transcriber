# Tasks: Segment Speech Recognition

**Input**: Design documents from `/opt/workspaces/transcriber/specs/002-segment-asr/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`,
`quickstart.md`, `/opt/workspaces/transcriber/.specify/memory/constitution.md`

**Tests**: Required by the project constitution. Each behavioral task contains its complete
test-first cycle: add the public-seam assertion, implement only enough production behavior to pass, then run the listed focused verification.

**Authority**: This file is authoritative for executable task IDs, order, dependencies, per-task acceptance criteria, and agent ownership. `plan.md` owns architectural work packages WP1-WP7 and maps those work packages to the task ranges below.

## Assumptions

- The GUI owns sequencing and enables ASR only after `transcriber-prepare` succeeds; middleware does
  not combine, start, wait for, or monitor Media Preparation Tasks.
- Segment Manifest paths already equal `segments/segment-NNNN.wav`; ASR additionally proves that
  resolved Speech Segment targets remain under `TASK_WORK_DIRECTORY/segments/` and match canonical
  WAV and duration facts.
- The supported language-tag grammar is a 2-8 letter ASCII primary subtag followed by zero or more
  1-8 character ASCII alphanumeric subtags. Grandfathered and private-use-only forms are rejected.
- `vendor/llama-server` and Qwen artifacts under `models/qwen3-asr-1.7b/` are supplied outside this
  feature. No download, build, installer, runtime checksum, or host `PATH` search is authorized.
- Loopback HTTP is permitted; external network access is prohibited.
- Speech Segment files are application-owned temporary artifacts. Mutation by an external actor
  after successful pre-start batch validation is outside this feature's threat model.
- Controlled acceptance coverage spans 1-100 Speech Segments. Each production ASR Task processes
  every valid Segment Manifest entry sequentially and has no 100-segment cap. Concurrent invocation
  for the same task/model remains unsupported and receives no lock semantics.
- Controlled tests verify project-owned invocation, mapping, parsing, lifecycle, and publication.
  Controlled fixtures retain exact Transcript-content and non-empty assembly assertions. No
  real-provider semantic test asserts transcript words, non-emptiness, WER, language accuracy,
  latency, throughput, or third-party internals.

## Architecture and Entity Relationships

| Entity | Layer | Relationship and boundary |
|---|---|---|
| `SegmentManifest`, Segment records, decoder | Domain | Internal manifest state and pure decoding; no filesystem access |
| `Transcript`, Recognition Context derivation | Domain | Pure text state; depends only on Domain |
| `AsrCommand`, `AsrProgress`, `AsrSuccess`, `AsrFailure` | Protocol | Closed public wire values; imports no higher layer |
| `AsrModelManifest`, artifacts, capabilities | Protocol | Decodes built-in JSON independently of artifact installation |
| Qwen request/response/error codecs | Protocol | Maps controlled wire bytes; exists before Composition injects it |
| `ExecutionProvider`, session/request primitives | Infrastructure | Runtime-neutral lifecycle using primitives and local paths |
| `LlamaCppExecutionProvider` | Infrastructure | Manages process and loopback transport; imports no Protocol |
| ASR task file reader, batch validator, and Transcript publisher | Infrastructure | Reads bytes, batch-checks primitive filenames/sample counts, returns `True` or raises a typed error, and atomically publishes complete bytes |
| Existing `WorkDirectory`, `AtomicFileWriter`, and filesystem failure types | Infrastructure | Retain workspace creation and atomic publication; expose only necessary shared file behavior to ASR task files |
| Existing `WaveMetadata`, `WaveFileReader`, `WaveSegmentWriter`, and WAV helpers | Infrastructure | Retain canonical WAV reading/writing and provide only necessary shared validation behavior |
| Existing `CompletedProcessData`, `ProcessRunner`, `SubprocessRunner`, and additive managed-process helpers | Infrastructure | Retain command execution and add managed lifecycle primitives without crossing the Infrastructure boundary |
| Existing `PrepareMedia`, `PreparationStage`, and preparation boundaries | Service | Retain Media Preparation Task orchestration while consuming the relocated Domain Segment Manifest entity and codec |
| `RecognizeSegments` | Service | Requests file I/O, invokes Domain decoding, orders provider lifecycle, submits results to Transcript, emits progress, and requests publication |
| Existing `RepositoryPaths`, `MediaDependencies`, `Application`, and composition builders | Composition | Preserve preparation assembly and facade behavior while adding fixed ASR paths, registrations, injected codecs, and ASR Service exposure |
| `asr_cli` | Controller | Parses arguments and renders stable progress, results, failures, cancellation |

The ASR Command selects one ASR Model Manifest, which selects one Execution Provider registration.
The ASR Task consumes one Segment Manifest, processes its Speech Segments through one provider
session, accumulates one Transcript, derives Recognition Context only from prior Transcript text,
and publishes one model-specific Transcript artifact. Service reads the Segment Manifest only
through Infrastructure, decodes the returned content through Domain, and makes one Infrastructure
batch-validation call before provider startup. Infrastructure never imports Protocol or Domain;
Composition injects Qwen codecs. The provider never publishes Transcript artifacts.

## Sub-agent Execution Policy

Every task `TNNN` receives a fresh Worker `W-TNNN` using `gpt-5.6-terra` with `medium` reasoning and a
fresh Validator `V-TNNN` using `gpt-5.6-sol` with `medium` reasoning. Shared Supervisor `S-ASR` uses
`gpt-5.6-sol` with `light` reasoning. The Worker records test-first and verification evidence and
submits both to the Validator. The Validator checks acceptance criteria, plan, tests, architecture,
and scope before reporting to `S-ASR`. Rejected work returns to the same Worker through the same
Validator. After three rejected cycles, stop and prepare the constitution-required manual-review
summary. `[P]` tasks have disjoint primary files and no incomplete declared dependency.

## Phase 1: Shared Contract Setup (WP1)

**Purpose**: Establish the closed GUI-facing values and the architecture enforcement needed by all
later work.

- [X] T001 Write failing public-constructor tests, then implement closed immutable `AsrCommand`, `AsrProgress`, `AsrSuccess`, and `AsrFailure` values in `tests/unit/protocol/test_asr_cli.py` and `src/transcriber/protocol/asr_cli.py`; owner W-T001 -> V-T001 -> S-ASR; depends on none; acceptance: absolute task paths, stable model IDs made of non-empty lowercase ASCII letter-or-digit components separated by a single hyphen or dot with no leading, trailing, repeated, or adjacent separators, automatic/explicit language, progress counts, closed stages, and optional segment/diagnostic fields are enforced without higher-layer imports; verify: `uv run pytest tests/unit/protocol/test_asr_cli.py -q` passes after the pre-implementation assertions target absent or incomplete behavior.
- [X] T002 Add controlled illegal-dependency fixtures and all planned ASR module classifications to `tests/architecture/test_layer_dependencies.py`; owner W-T002 -> V-T002 -> S-ASR; depends on T001; acceptance: synthetic Infrastructure-to-Protocol, Infrastructure-to-Domain, and Controller-to-Infrastructure imports fail while every permitted dependency passes, so absent modules are never accepted as boundary evidence; verify: `uv run pytest tests/architecture/test_layer_dependencies.py -q` passes.

**Checkpoint**: Public values and enforceable layer classifications are available.

---

## Phase 2: Foundational Domain and Infrastructure (WP1)

**Purpose**: Establish the internal Segment Manifest, base Transcript, complete task-file boundary,
and runtime-neutral Execution Provider seam.

**CRITICAL**: T003-T006 block the production User Story 1 convergence but may run in parallel.

- [X] T003 [P] Record controlled preparation regressions, write Domain/contract assertions before behavior change, then relocate the Segment Manifest entity plus `encode_manifest` and `decode_manifest` from `src/transcriber/protocol/manifest.py` to `src/transcriber/domain/manifest.py`, relocate `tests/unit/protocol/test_manifest_codec.py` to `tests/unit/domain/test_manifest.py`, and update every existing consumer, including `src/transcriber/composition/application.py`, `src/transcriber/service/prepare_media.py`, `tests/contract/test_manifest_contract.py`, `tests/unit/service/test_prepare_media.py`, and `tests/acceptance/test_sample_workflow.py`; owner W-T003 -> V-T003 -> S-ASR; depends on T002; acceptance: the relocated Domain codec preserves encoded bytes and existing internal schema/order/duration/filename invariants, Domain decoding performs no filesystem operation, the old Protocol manifest module is removed, and that removed module has no remaining import reference; Composition continues working before T011; pre-relocation verify: the controlled command `uv run pytest tests/unit/protocol/test_manifest_codec.py tests/contract/test_manifest_contract.py tests/unit/service/test_prepare_media.py tests/unit/composition/test_application.py tests/unit/controller/test_cli.py tests/contract/test_cli_contract.py tests/architecture/test_layer_dependencies.py -q` exits 0; post-relocation verify: `uv run pytest tests/unit/domain/test_manifest.py tests/contract/test_manifest_contract.py tests/unit/service/test_prepare_media.py tests/unit/composition/test_application.py tests/unit/controller/test_cli.py tests/contract/test_cli_contract.py tests/acceptance/test_sample_workflow.py tests/architecture/test_layer_dependencies.py -m "not real_vad" -q` exits 0 with `skipped=0`, `xfailed=0`, and `xpassed=0`, and `rg 'transcriber\\.protocol\\.manifest'` returns status 1 with no matches; real-VAD execution remains T029.
- [X] T004 [P] Write failing Transcript tests, then implement base trimming, empty-result handling, one-space joining, text access, and deterministic encoding in `tests/unit/domain/test_transcript.py` and `src/transcriber/domain/transcript.py`; owner W-T004 -> V-T004 -> S-ASR; depends on T002; acceptance: all-empty, whitespace-only, non-ASCII, and ordered non-empty results use no provider or filesystem and encode as zero bytes or UTF-8 plus exactly one LF; verify: `uv run pytest tests/unit/domain/test_transcript.py tests/architecture/test_layer_dependencies.py -q` passes.
- [ ] T005 [P] Create only the controlled Segment Manifest/file builders consumed by the task, write failing Infrastructure tests, then implement `read_manifest_file`, one-call `check_segment_files`, exact output derivation, and successful atomic publication in `tests/support/asr.py`, `tests/integration/infrastructure/test_asr_task_files.py`, and `src/transcriber/infrastructure/asr_files.py`, reusing only necessary code from `src/transcriber/infrastructure/filesystem.py` and `src/transcriber/infrastructure/wave_files.py`; owner W-T005 -> V-T005 -> S-ASR; depends on T002; acceptance: Infrastructure reads bytes without decoding, accepts ordered primitive filename/sample-count arrays, returns exactly `True` only after complete validation, raises one typed error on length mismatch or the first invalid/missing/replaced/escaping/format/duration failure, introduces no validated-segment collection, imports neither Domain nor Protocol, and atomically publishes only `transcripts-{model-id}/transcript.txt`; verify: `uv run pytest tests/integration/infrastructure/test_asr_task_files.py tests/integration/infrastructure/test_filesystem.py tests/integration/infrastructure/test_wave_files.py tests/architecture/test_layer_dependencies.py -q` passes and the focused test imports and consumes `tests.support.asr`.
- [ ] T006 [P] Write failing project-owned primitive/lifecycle tests, then implement Execution Provider interfaces, request/result primitives, lifecycle guards, and separately carried provider errors in `tests/unit/infrastructure/test_execution_provider.py` and `src/transcriber/infrastructure/execution_provider.py`; owner W-T006 -> V-T006 -> S-ASR; depends on T002; acceptance: fresh sessions, start-before-recognize, successful empty text, separate diagnostics, and idempotent stop use only primitives/local paths and no HTTP, Qwen internals, typing-machinery assertions, Domain, or Protocol imports; verify: `uv run pytest tests/unit/infrastructure/test_execution_provider.py tests/architecture/test_layer_dependencies.py -q` passes.

**Checkpoint**: WP1 is complete through four cohesive test-first lanes.

---

## Phase 3: User Story 1 - Baseline Qwen Model and Provider (Priority: P1) (WP2)

**Goal**: Supply the valid built-in Qwen resource, baseline Qwen codecs, and managed llama.cpp
happy path required by the production ASR command.

**Independent Test**: Decode the packaged Qwen manifest without installed weights, assert exact
controlled request/response bytes, and run a controlled managed provider through normal cleanup.

- [ ] T007 [P] [US1] Create ASR resource packages and package-data configuration, write failing valid-manifest/resource tests, then implement typed schema-v1 decoding and the Qwen manifest in `src/transcriber/resources/__init__.py`, `src/transcriber/resources/asr_models/__init__.py`, `src/transcriber/resources/asr_models/qwen3-asr-1.7b.json`, `src/transcriber/protocol/asr_model_manifest.py`, `pyproject.toml`, `tests/unit/test_package_metadata.py`, `tests/unit/protocol/test_asr_model_manifest.py`, and `tests/contract/test_asr_model_manifest_contract.py`; owner W-T007 -> V-T007 -> S-ASR; depends on T002; acceptance: exact Qwen ID/display/source/provider/capabilities/artifact roles/paths/checksums decode independently of `models/`, Protocol imports no higher layer, package metadata explicitly includes the JSON, and the built wheel contains it; verify: `uv run pytest tests/unit/test_package_metadata.py tests/unit/protocol/test_asr_model_manifest.py tests/contract/test_asr_model_manifest_contract.py tests/architecture/test_layer_dependencies.py -q`, `uv build --wheel`, and `unzip -l dist/transcriber-0.1.0-py3-none-any.whl | rg -F 'transcriber/resources/asr_models/qwen3-asr-1.7b.json'` all succeed.
- [ ] T008 [P] [US1] Write failing baseline Qwen codec tests, then implement automatic-language request, empty Recognition Context, local audio item, deterministic non-streaming sampling, control-prefix removal, empty success, malformed-response failure, and error extraction in `tests/unit/protocol/test_qwen_asr.py` and `src/transcriber/protocol/qwen_asr.py`; owner W-T008 -> V-T008 -> S-ASR; depends on T002; acceptance: exact controlled bytes are mapped without HTTP, process behavior, language catalogs, model semantics, or higher-layer imports, and only recognized text crosses the codec; verify: `uv run pytest tests/unit/protocol/test_qwen_asr.py tests/architecture/test_layer_dependencies.py -q` passes.
- [ ] T009 [US1] Create only the managed-process double consumed by the task, write failing happy-path tests using injected Qwen codecs, then implement llama.cpp startup, loopback health/recognition transport, and normal cleanup in `tests/support/managed_process.py`, `tests/integration/infrastructure/test_llama_cpp.py`, `src/transcriber/infrastructure/llama_cpp.py`, and only necessary additions to `src/transcriber/infrastructure/process.py`; owner W-T009 -> V-T009 -> S-ASR; depends on T006 and T008; acceptance: captured argv proves `shell=False`, fixed executable/model/projector paths, `127.0.0.1`, one slot, context size 8192, validated media root, disabled web UI, one load, sequential local requests, injected codec use, and normal reaping without real artifacts or non-loopback access; verify: `uv run pytest tests/integration/infrastructure/test_llama_cpp.py tests/integration/infrastructure/test_firered_ncnn.py tests/architecture/test_layer_dependencies.py -q` passes and the focused test imports and consumes `tests.support.managed_process`.

**Checkpoint**: WP2 supplies the packaged model contract, codec, and baseline managed provider.

---

## Phase 4: User Story 1 - Create a transcript from prepared speech (Priority: P1) MVP (WP3)

**Goal**: Deliver the production-usable built-in Qwen3-ASR/llama.cpp command that recognizes every
prepared Speech Segment in order and atomically publishes one exact Transcript.

**Independent Test**: Given controlled valid local prerequisites and provider responses, invoke
`transcriber-asr` for 1, 3, and 100 Speech Segments and verify exact-once order, valid empty results,
progress, one final absolute path, and exact atomic Transcript bytes.

- [ ] T010 [US1] Add the controlled model/provider/call-log builders first consumed here, write failing Service-seam tests, then implement the happy-path lifecycle in `tests/support/asr.py`, `tests/unit/service/test_recognize_segments.py`, and `src/transcriber/service/recognize_segments.py`; owner W-T010 -> V-T010 -> S-ASR; depends on T003-T007 and T009; acceptance: Service requests one manifest-byte read, invokes the Domain decoder, rejects zero segments, makes one Infrastructure batch call with all ordered filenames and expected sample counts, requires exactly `True`, starts no provider on typed validation error, performs no filesystem operation directly, recognizes every filename exactly once in manifest order, submits every result to Domain Transcript, advances progress for empty results, publishes only after all results, and always cleans a started session without any aggregate preflight entity or Media Preparation Task call; verify: `uv run pytest tests/unit/service/test_recognize_segments.py tests/architecture/test_layer_dependencies.py -q` passes and the focused test consumes every new support builder.
- [ ] T011 [US1] Write failing Composition tests, then implement the minimum built-in `qwen3-asr-1.7b` to `llama-cpp` registration and ASR facade in `tests/unit/composition/test_asr_application.py` and `src/transcriber/composition/application.py`; owner W-T011 -> V-T011 -> S-ASR; depends on T010; acceptance: Composition alone loads the package manifest without weights, injects existing Qwen codecs, resolves fixed model/provider paths from a foreign current directory without `PATH`, owns one baseline registration, and preserves the preparation facade; verify: `uv run pytest tests/unit/composition/test_asr_application.py tests/unit/composition/test_application.py tests/architecture/test_layer_dependencies.py -q` passes.
- [ ] T012 [US1] Write failing happy-path/model-ID grammar CLI unit and contract tests, then implement `transcriber-asr` parsing, FR-001 validation, Service invocation, progress/success rendering, and entry point in `tests/unit/controller/test_asr_cli.py`, `tests/contract/test_asr_cli_contract.py`, `src/transcriber/controller/asr_cli.py`, and `pyproject.toml`; owner W-T012 -> V-T012 -> S-ASR; depends on T011; acceptance: an existing task path and `--model` are required, language defaults to `auto`, model IDs accept single hyphen and dot separators but reject leading, trailing, repeated, and adjacent separators, invalid model IDs return status 2 before application resolution, a valid unregistered ID returns status 1 after resolution, relative task paths become absolute, each completed segment emits one exact progress line, success emits one final absolute `transcript=` line with status 0, and no combined preparation/model-list operation appears; verify: `uv run pytest tests/unit/controller/test_asr_cli.py tests/contract/test_asr_cli_contract.py tests/unit/controller/test_cli.py tests/contract/test_cli_contract.py -q` passes.
- [ ] T013 [US1] Add the controlled end-to-end MVP cases in `tests/acceptance/test_asr_workflow.py`; owner W-T013 -> V-T013 -> S-ASR; depends on T012; acceptance: parameterized 1- and 100-segment cases prove exact-once order and exact controlled Transcript assembly, a three-segment case proves an empty middle result adds no separator but advances progress, a rerun atomically replaces prior output, and the built-in Qwen path resolves to llama.cpp without download/build/`PATH` behavior; verify: `uv run pytest tests/acceptance/test_asr_workflow.py -m "not real_asr" -q` passes without real provider/model prerequisites.

**Checkpoint**: WP3 completes the independently testable production-usable US1 MVP.

---

## Phase 5: User Story 2 - Preserve continuity and language intent (Priority: P2) (WP4)

**Goal**: Supply bounded prior Transcript only to context-capable ASR Models and preserve automatic
or explicitly validated language intent through the Qwen request.

**Independent Test**: Controlled capable/disabled/required-language models prove exact context and
language values, including the 2,048-Unicode-code-point boundary and supported language grammar.

- [ ] T014 [P] [US2] Write failing Recognition Context boundary tests, then implement FR-009 derivation in `tests/unit/domain/test_transcript.py` and `src/transcriber/domain/transcript.py`; owner W-T014 -> V-T014 -> S-ASR; depends on T013; acceptance: literal 2,047/2,048/2,049+ cases, Unicode-whitespace cuts, leading-fragment removal, punctuation, hyphens, and the `"alpha beta"`, `"alpha-beta"`, and `"甲乙丙丁"` examples use Python `str.isspace()`, never exceed 2,048 code points, return empty when no post-cut boundary remains, and use no filesystem/provider dependency; verify: `uv run pytest tests/unit/domain/test_transcript.py tests/architecture/test_layer_dependencies.py -q` passes.
- [ ] T015 [P] [US2] Write failing Qwen context/explicit-language tests, then extend the codecs in `tests/unit/protocol/test_qwen_asr.py` and `src/transcriber/protocol/qwen_asr.py`; owner W-T015 -> V-T015 -> S-ASR; depends on T013; acceptance: supplied context occupies the system role, explicit `en-GB` becomes provider-native assistant prefill, request mapping matches the contract, and no public supported-language catalog or model-selection behavior appears; verify: `uv run pytest tests/unit/protocol/test_qwen_asr.py tests/architecture/test_layer_dependencies.py -q` passes.
- [ ] T016 [US2] Write cross-layer failing tests for context capability, accumulated prior text, optional/required language, and the exact CLI grammar, then thread the values through `tests/unit/service/test_recognize_segments.py`, `tests/unit/composition/test_asr_application.py`, `tests/unit/controller/test_asr_cli.py`, `src/transcriber/service/recognize_segments.py`, `src/transcriber/composition/application.py`, and `src/transcriber/controller/asr_cli.py`; owner W-T016 -> V-T016 -> S-ASR; depends on T012, T014, and T015; acceptance: first/context-disabled requests receive empty context, later requests derive context only from prior non-empty Transcript text, the already-generic provider request carries both values to its injected codec without provider-specific changes, required `auto` fails before file/provider work, valid 2/8-character primary and 1/8-character subsequent subtags pass, malformed/grandfathered/private-use-only forms return status 2 without crossing the application seam, and `auto` remains the default; verify: `uv run pytest tests/unit/domain/test_transcript.py tests/unit/protocol/test_qwen_asr.py tests/unit/service/test_recognize_segments.py tests/unit/composition/test_asr_application.py tests/unit/controller/test_asr_cli.py -q` passes.
- [ ] T017 [US2] Add controlled continuity and language acceptance cases in `tests/acceptance/test_asr_workflow.py`; owner W-T017 -> V-T017 -> S-ASR; depends on T016; acceptance: context-capable and context-disabled models receive exact values, explicit language is preserved, valid boundary tags pass, invalid tags return 2, and required automatic language fails before provider startup; verify: `uv run pytest tests/acceptance/test_asr_workflow.py -m "not real_asr" -q` passes.

**Checkpoint**: WP4 completes US2 without changing Transcript assembly or adding model-to-language matching.

---

## Phase 6: User Story 3 - Receive safe progress and actionable failures (Priority: P2) (WP5)

**Goal**: Emit stable progress and bounded failures while stopping the Execution Provider and
preserving prior complete Transcript bytes across the controlled failure matrix.

**Independent Test**: Drive every preflight, startup, recognition, deadline, malformed-response,
publication, signal, and cancellation boundary with controlled clocks/processes and verify progress,
status, diagnostics, cleanup, and prior-output preservation.

- [ ] T018 [P] [US3] Write failing managed-provider lifecycle tests, then implement child-exit handling, healthy readiness, the controlled 60-second startup deadline, endpoint collision/reselection, the controlled 180-second request deadline, HTTP/provider errors, diagnostic draining, and idempotent graceful/forced cleanup in `tests/integration/infrastructure/test_llama_cpp.py`, `src/transcriber/infrastructure/llama_cpp.py`, and `src/transcriber/infrastructure/process.py`; owner W-T018 -> V-T018 -> S-ASR; depends on T009; acceptance: injected clocks prove exact deadlines without wall-clock sleeps, including at most 60 seconds for graceful shutdown followed, when needed, by forced termination and reaping within 10 additional seconds; real startup, pipe deadlock, non-loopback access, and public log forwarding remain absent, and every stop reaps the process; verify: `uv run pytest tests/integration/infrastructure/test_llama_cpp.py tests/integration/infrastructure/test_firered_ncnn.py -q` passes.
- [ ] T019 [P] [US3] Write failing publication-failure tests, then implement staged write/flush/replace handling and cleanup in `tests/integration/infrastructure/test_asr_task_files.py`, `src/transcriber/infrastructure/asr_files.py`, and only necessary shared behavior in `src/transcriber/infrastructure/filesystem.py`; owner W-T019 -> V-T019 -> S-ASR; depends on T013; acceptance: only complete success replaces the destination, every injected failure preserves prior bytes and removes temporary artifacts, successful empty/non-empty publication remains exact, preflight never mutates output, and no lock appears; verify: `uv run pytest tests/integration/infrastructure/test_asr_task_files.py tests/integration/infrastructure/test_filesystem.py -q` passes.
- [ ] T020 [US3] Write failing Service tests for the complete closed failure matrix, then implement failure translation, progress timing, deadline/cancellation propagation, and guaranteed cleanup in `tests/unit/service/test_recognize_segments.py` and `src/transcriber/service/recognize_segments.py`; owner W-T020 -> V-T020 -> S-ASR; depends on T016, T018, and T019; acceptance: every SC-003 stage is named, segment failures carry the zero-based Segment Manifest index and separate diagnostics, one progress value follows each completed recognition, no progress/publication follows failure, controlled clocks cover SC-004, and every started provider stops; verify: `uv run pytest tests/unit/service/test_recognize_segments.py tests/architecture/test_layer_dependencies.py -q` passes.
- [ ] T021 [P] [US3] Write failing CLI failure/cancellation contract tests, then implement bounded rendering, diagnostic escaping, status mapping, and handled signals in `tests/unit/controller/test_asr_cli.py`, `tests/contract/test_asr_cli_contract.py`, and `src/transcriber/controller/asr_cli.py`; owner W-T021 -> V-T021 -> S-ASR; depends on T016 and T020; acceptance: the selected model and zero-based index appear when applicable, every dynamic string is JSON-escaped, the complete line is at most 1,023 Python code points excluding LF, quoted truncation retains its closing quote and `...[truncated]`, logs never leak, SIGINT/SIGTERM reach cleanup, runtime failures return 1, argument failures remain 2, and failure emits no `transcript=` line; verify: `uv run pytest tests/unit/controller/test_asr_cli.py tests/contract/test_asr_cli_contract.py tests/unit/controller/test_cli.py tests/contract/test_cli_contract.py -q` passes.
- [ ] T022 [US3] Add the complete controlled failure-matrix acceptance cases in `tests/acceptance/test_asr_workflow.py`; owner W-T022 -> V-T022 -> S-ASR; depends on T017 and T021; acceptance: every documented preflight/provider/response/deadline/publication/cancellation boundary preserves prior Transcript bytes, removes temporary output, stops any started provider, emits only completed progress, and returns no final path; verify: `uv run pytest tests/acceptance/test_asr_workflow.py -m "not real_asr" -q` passes without wall-clock sleeps.

**Checkpoint**: WP5 completes US3 and directly proves SC-003 and SC-004.

---

## Phase 7: User Story 4 - Validate built-in model availability safely (Priority: P3) (WP6)

**Goal**: Harden the existing US1 model boundary against invalid manifests, unknown identities, and
missing fixed prerequisites, and prove another valid registration leaves Transcript rules unchanged.

**Independent Test**: Controlled manifests and registrations exercise every invalid/availability
outcome before provider startup or Transcript mutation without recreating baseline Qwen assembly.

- [ ] T023 [P] [US4] Write failing structural/semantic manifest tests, then complete closed validation in `tests/unit/protocol/test_asr_model_manifest.py`, `tests/contract/test_asr_model_manifest_contract.py`, and `src/transcriber/protocol/asr_model_manifest.py`; owner W-T023 -> V-T023 -> S-ASR; depends on T007; acceptance: missing/unknown fields, wrong schema/type, unsafe IDs/paths, filename mismatch, duplicate resolved paths, non-HTTPS source, invalid checksums, empty artifacts, and invalid language values reject deterministically before installation state while valid resources remain artifact-independent; verify: `uv run pytest tests/unit/protocol/test_asr_model_manifest.py tests/contract/test_asr_model_manifest_contract.py tests/architecture/test_layer_dependencies.py -q` passes.
- [ ] T024 [P] [US4] Write failing Composition/Service availability tests, then harden the existing catalog and resolution flow in `tests/unit/composition/test_asr_application.py`, `tests/unit/service/test_recognize_segments.py`, `src/transcriber/composition/application.py`, and `src/transcriber/service/recognize_segments.py`; owner W-T024 -> V-T024 -> S-ASR; depends on T020 and T023; acceptance: unknown models fail before task/output access; every missing fixed model/provider path is aggregated before startup and rendered as project-relative JSON strings in `missing prerequisites: PATH, PATH`, with the provider executable first and artifacts in ASR Model Manifest declaration order; Qwen baseline assembly is reused rather than recreated, no runtime checksum/network/`PATH` work occurs, and a second compatible registration uses unchanged Transcript behavior; verify: `uv run pytest tests/unit/composition/test_asr_application.py tests/unit/service/test_recognize_segments.py tests/architecture/test_layer_dependencies.py -q` passes.
- [ ] T025 [US4] Add controlled availability-hardening acceptance cases in `tests/acceptance/test_asr_workflow.py`; owner W-T025 -> V-T025 -> S-ASR; depends on T022 and T024; acceptance: invalid manifest, unknown ID, missing artifacts/provider, and second valid registration outcomes match US4 without touching Transcript output or network; verify: `uv run pytest tests/acceptance/test_asr_workflow.py -m "not real_asr" -q` passes with network disabled.

**Checkpoint**: WP6 completes US4 without duplicating the US1 provider, codec, or registration.

---

## Phase 8: Polish and Cross-Cutting Verification (WP7)

**Purpose**: Prove deterministic prerequisite selection, documentation, controlled gates, required
local integration, and final traceability without expanding scope.

- [ ] T026 [P] Write failing controlled prerequisite-policy tests, then implement `RealAsrPaths`, optional skip, required failure, pytest option, fixture, and marker behavior in `tests/unit/test_real_asr_prerequisites.py`, `tests/conftest.py`, and `pyproject.toml`; additionally define the SC-006 test `test_real_asr_workflow`, marked `real_asr`, in `tests/acceptance/test_asr_workflow.py`; owner W-T026 -> V-T026 -> S-ASR; depends on T025; acceptance: controlled temporary paths prove optional mode skips, required mode fails with bounded missing-path details, present controlled paths proceed, and the task never needs real Qwen/llama.cpp artifacts; `test_real_asr_workflow` uses approved public seams and supplied local prerequisites, is collectable without installed artifacts, obtains prerequisites only during execution, invokes the production ASR path, verifies project-owned fixed-path invocation, request/response adaptation, progress, publication, and cleanup, makes no semantic quality/performance assertions, is defined but not executed by T026, and remains executed by T029; `RealAsrPaths` deterministically resolves the fixed provider and both Qwen artifact paths under an injected application root; T029 uses the same resolver against the supplied ignored artifacts. Verify: `uv run pytest tests/unit/test_real_asr_prerequisites.py -q` exits 0 with `skipped=0`, `xfailed=0`, and `xpassed=0`, and `uv run pytest --collect-only tests/acceptance/test_asr_workflow.py -m real_asr -q` exits 0 and lists `test_real_asr_workflow` without provider startup.
- [ ] T027 [P] Write failing documentation-contract tests, then align `tests/contract/test_asr_documentation_contract.py`, `specs/002-segment-asr/contracts/cli.md`, `README.md`, `docs/cli.md`, and `specs/002-segment-asr/quickstart.md`; owner W-T027 -> V-T027 -> S-ASR; depends on T025; acceptance: controlled reads prove every document states GUI-owned sequencing, canonical command grammar, fixed local prerequisites, exact language/Segment path rules, progress/success/failure formats, statuses 0/1/2, and no model/provider download or build procedure; verify: `uv run pytest tests/contract/test_asr_documentation_contract.py tests/contract/test_asr_cli_contract.py -q` passes.
- [ ] T028 Run the complete deterministic controlled suite and record commands/results in `specs/002-segment-asr/evidence/T028-controlled-gates.md`; owner W-T028 -> V-T028 -> S-ASR; depends on T026 and T027; acceptance: every controlled Test Plan command passes, every pytest gate records and validates `skipped=0`, `xfailed=0`, and `xpassed=0`, no real-provider/real-VAD/real-ASR command runs, and evidence records exact tool versions, commands, statuses, and counts; verify: every command in the controlled-only Test Plan subsections exits 0 and the evidence contains the required versions, commands, statuses, and zero counts.
- [ ] T029 Run the required existing real-VAD regression and required real-ASR checkpoint and record cleanup evidence in `specs/002-segment-asr/evidence/T029-real-checkpoints.md`; owner W-T029 -> V-T029 -> S-ASR; depends on T028 and supplied ignored Qwen/llama.cpp/real-VAD prerequisites; acceptance: both required checkpoints pass rather than skip, ASR uses loopback/fixed paths, no managed provider remains, and evidence makes no semantic-quality/performance claim; verify: `uv run pytest --real-vad-required -m real_vad tests/acceptance/test_sample_workflow.py -q` and `uv run pytest --real-asr-required -m real_asr tests/acceptance/test_asr_workflow.py -q -s` both exit 0.
- [ ] T030 Add failing release-audit contract tests, then create and review a Worker draft before creating the final audit in `tests/contract/test_asr_release_audit_contract.py` and `specs/002-segment-asr/evidence/T030-release-audit.md`; owner W-T030 -> V-T030 -> S-ASR; depends on T029; acceptance: parser tests cover draft and final states; the Worker draft has exactly one row for every FR-001-FR-026, SC-001-SC-006, WP1-WP7, and T001-T030, all evidence paths resolve, explicit non-goals are absent, only WP7/T030 can be pending-review, the draft decision is exactly `S-ASR: pending-review`, and the Validator checks the draft and reports to S-ASR without prior T030 acceptance; after Supervisor acceptance, S-ASR changes WP7/T030 to accepted and the final decision to exactly `S-ASR: accepted`; the final audit has only accepted rows, records architecture/contracts/test-first evidence/docs/unchanged preparation/no forbidden scope, and retains all existing audit coverage; verify: `uv run pytest tests/contract/test_asr_release_audit_contract.py tests/architecture/test_layer_dependencies.py -q` passes before submission with controlled draft/final fixtures, then the actual finalized audit validates with no pending, missing, duplicate, path, or non-goal defects.

---

## Dependencies and Execution Order

### Work-package crosswalk

| Work package | Executable tasks | Delivery |
|---|---|---|
| WP1 | T001-T006 | Shared contracts, architecture, Domain, and Infrastructure foundations |
| WP2 | T007-T009 | US1 valid manifest, baseline codecs, managed provider |
| WP3 | T010-T013 | US1 Service, Composition, CLI, controlled MVP |
| WP4 | T014-T017 | US2 context and language intent |
| WP5 | T018-T022 | US3 progress, failures, deadlines, cancellation |
| WP6 | T023-T025 | US4 availability and registration hardening |
| WP7 | T026-T030 | Controlled gates, real checkpoints, docs, audit |

### Capability order and safe overlap

```text
T001 -> T002 -> {T003, T004, T005, T006}
T002 -> {T007, T008}; {T006, T008} -> T009
{T003, T004, T005, T006, T007, T009} -> T010 -> T011 -> T012 -> T013

After the US1 MVP:
  {T014 Domain context, T015 Qwen extension, T019 publication failures}
may overlap with:
  T018 provider hardening (available after T009)
and:
  T023 manifest hardening (available after T007)

{T012, T014, T015} -> T016 -> T017
{T016, T018, T019} -> T020 -> {T021, T024}; T023 also gates T024
{T017, T021} -> T022; {T022, T024} -> T025
T025 -> {T026, T027} -> T028 -> T029 -> T030
```

Task-line dependencies are authoritative. `[P]` marks tasks whose primary files are disjoint from
other ready tasks; no marker authorizes overlapping edits to a shared file. Each story retains a
controlled independent checkpoint. Only T029 requires ignored local provider/model prerequisites.

### Requirement traceability

| Requirement area | Tasks |
|---|---|
| Independent command and GUI boundary (FR-001, FR-003, FR-026) | T010-T013, T027, T030 |
| Language input and capability (FR-002, FR-011, FR-012) | T008, T014-T017 |
| Segment/model/provider preflight (FR-004-FR-006, FR-020-FR-023) | T003, T005, T007, T010-T013, T023-T025 |
| Provider lifecycle, context, ordered recognition (FR-007-FR-010, FR-017, FR-024) | T004, T006, T008-T010, T014-T020 |
| Progress, publication, failures, status (FR-013-FR-019) | T001, T005, T010-T013, T018-T022 |
| Offline operation (FR-025) | T008-T013, T015-T019, T023-T030 |
| Measurable outcomes SC-001-SC-006 | T013, T017, T022, T025, T028-T030 |

---

## Parallel Execution Examples

### WP1 foundations

```text
W-T001 -> W-T002 -> {W-T003 Domain Manifest, W-T004 Transcript,
                     W-T005 files/publication, W-T006 provider contract}
```

### US1 baseline and MVP

```text
W-T007 valid manifest/resource || W-T008 baseline Qwen codecs
W-T006 + W-T008 -> W-T009 managed provider
All WP1/WP2 prerequisites -> W-T010 -> W-T011 -> W-T012 -> W-T013
```

### Post-MVP parallel wave

```text
W-T014 Recognition Context || W-T015 Qwen extension || W-T019 publication failures
W-T018 provider failures (may start after W-T009)
W-T023 manifest hardening (may start after W-T007)
```

### Story convergence and release

```text
W-T016 -> W-T017
W-T020 -> {W-T021 CLI failures, W-T024 availability flow}
W-T022 + W-T024 -> W-T025
W-T026 prerequisite policy || W-T027 documentation
Both accepted -> W-T028 -> W-T029 -> W-T030
```

---

## Test Plan

### Per-task test-first rule

1. Add one behavior assertion through an approved public seam -> **verify**: the narrow target fails
   for absent/incorrect behavior rather than fixture/setup failure; recording the red run is optional.
2. Add only enough production behavior for green -> **verify**: the narrow target passes.
3. Validator runs independent edge cases plus architecture/static checks -> **verify**: acceptance,
   plan, and scope match before reporting to `S-ASR`.
4. Refactor only after green -> **verify**: the same relevant tests remain green.

### Required controlled coverage

- Domain: Segment Manifest decoding/invariants, empty/non-empty Transcript accumulation, whitespace,
  joining, non-ASCII encoding, exact context boundaries, and `str.isspace()` fragment removal.
- Protocol: closed ASR values, valid/invalid ASR Model Manifest semantics, baseline/extended Qwen
  mapping, malformed responses, and provider-error extraction.
- Infrastructure: manifest-byte reading, one batch check returning exactly `True` or raising a typed
  error, exact Segment paths, containment, WAV mismatches, atomic publication/failure, exact argv,
  loopback-only transport, process races, port retry, deadlines, diagnostics, and termination.
- Service: lifecycle order, context on/off, required/optional language, empty results, progress,
  every failure stage, cancellation, no partial publication, and unknown/missing models.
- Composition/Controller: baseline registration, fixed paths from foreign CWD, exact grammar,
  CLI statuses/errors/signals, second registration, and preparation regression.
- Acceptance: controlled 1/3/100 Segment behavior, exact controlled Transcript content, the complete
  failure matrix, and availability hardening.

### Deterministic gates

```bash
uv run pytest -m "not real_vad and not real_asr"
uv run pytest tests/contract tests/architecture -q
uv run pytest tests/unit/controller/test_cli.py tests/unit/composition/test_application.py -q
uv run pytest tests/unit/test_real_asr_prerequisites.py -q
uv run mypy --strict src
uv run ruff check src tests
```

T028 runs only this controlled suite and the controlled package-resource verification below. For
every pytest command, T028 records and validates `skipped=0`, `xfailed=0`, and `xpassed=0`; any
nonzero count fails T028. T028 runs no real-provider, real-VAD, or real-ASR command.

### Package-resource verification (controlled only)

```bash
uv build --wheel
unzip -l dist/transcriber-0.1.0-py3-none-any.whl | rg -F 'transcriber/resources/asr_models/qwen3-asr-1.7b.json'
```

### Required local gates

```bash
uv run pytest --real-vad-required -m real_vad tests/acceptance/test_sample_workflow.py -q
uv run pytest --real-asr-required -m real_asr tests/acceptance/test_asr_workflow.py -q -s
```

The real-provider semantic test may assert fixed paths, startup, local request completion, codec
adaptation, progress, artifact existence, and cleanup. The real-provider semantic test must not
assert recognized words, non-emptiness, WER, language correctness, latency, throughput, or provider
internals. Controlled fixtures retain exact Transcript-content and non-empty assembly assertions.

---

## Implementation Strategy

### MVP first

1. Complete WP1 (T001-T006) -> verify: S-ASR accepts T001-T006 from their Validator reports and the controlled T001-T006 checkpoint evidence satisfies each task acceptance criterion.
2. Complete WP2 and WP3 (T007-T013) -> verify: S-ASR accepts T007-T013 from their Validator reports and the controlled T013 acceptance evidence satisfies the MVP acceptance criteria.
3. Stop and validate US1 as the production-usable controlled MVP -> verify: the controlled T013 checkpoint `uv run pytest tests/acceptance/test_asr_workflow.py -m "not real_asr" -q` exits 0 and S-ASR accepts T013.

### Incremental delivery

1. US1: deliver the valid Qwen resource, baseline codecs/provider, ordered recognition, and atomic Transcript (T007-T013) -> verify: S-ASR accepts T007-T013 and T013 controlled acceptance evidence satisfies the US1 criteria.
2. US2: deliver bounded Recognition Context and exact language intent (T014-T017) -> verify: S-ASR accepts T014-T017 and the controlled T017 acceptance evidence satisfies the US2 criteria.
3. US3: deliver stable progress, the complete failure matrix, deadlines, cancellation, and preservation (T018-T022) -> verify: S-ASR accepts T018-T022 and the controlled T022 acceptance evidence satisfies the US3 criteria.
4. US4: deliver exhaustive manifest and local-availability hardening without baseline duplication (T023-T025) -> verify: S-ASR accepts T023-T025 and the controlled T025 acceptance evidence satisfies the US4 criteria.
5. Release: deliver controlled policy, docs, deterministic gates, real checkpoints, and final audit (T026-T030) -> verify: S-ASR accepts T026-T030 after T028 controlled-gates evidence, T029 real-checkpoint evidence, and T030 final-audit evidence each satisfy their task acceptance criteria.

### Completion criteria

- T001-T030 are accepted through distinct Worker/Validator chains within the three-cycle limit.
- All controlled, architecture, typing, lint, existing real-VAD, and required real-ASR gates pass.
- CLI, manifest, provider contract, data model, quickstart, docs, and behavior are consistent.
- Final audit finds no missing requirement, architecture breach, model-quality test, duplicate US1/US4
  implementation, conditional controlled task, or explicit non-goal in the diff.

## Notes

- Explicit dependencies override broad phase order; `[P]` never authorizes overlapping-file edits.
- Tests observe approved public seams rather than private implementation state.
- New capability discovered during implementation requires an approved task update before coding.
