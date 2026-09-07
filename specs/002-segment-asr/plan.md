# Implementation Plan: Segment Speech Recognition

**Branch**: `002-segment-asr` | **Date**: 2026-09-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-segment-asr/spec.md`

## Summary

Add `transcriber-asr` as an independent command that the GUI enables only after the separate
segmentation command succeeds. It reads the completed Segment Manifest, validates every Speech
Segment and local prerequisite, resolves the selected built-in ASR Model and its Execution Provider,
processes segments sequentially with bounded prior Transcript context, and atomically publishes one
model-specific plain-text Transcript. The first built-in model is Qwen3-ASR-1.7B through a managed
`vendor/llama-server` process; provider and model internals remain behind injected protocol codecs
and an Infrastructure-layer provider interface.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Python standard library (`argparse`, `dataclasses`, `http.client` or
`urllib`, `importlib.resources`, `json`, `pathlib`, `socket`, `subprocess`, `tempfile`, `threading`,
`time`); existing project modules; shipped `vendor/llama-server`; no new runtime package

**Storage**: Existing Segment Manifest and WAV files; built-in JSON ASR Model Manifests; atomic
UTF-8 `transcript.txt`

**Testing**: pytest 9, controlled fakes/stubs, opt-in required real-provider checkpoint, mypy strict,
Ruff, existing architecture dependency tests

**Target Platform**: Local macOS desktop application middleware; provider executable and model
artifacts are supplied by application packaging/installation

**Project Type**: Layered Python CLI middleware launched by a GUI

**Performance Goals**: One progress record after every completed Speech Segment; model loaded once
per ASR Task; provider readiness bounded at 60 seconds; one segment request bounded at 180 seconds;
provider shutdown permits 60 seconds for graceful termination and 10 additional seconds for forced
termination and reaping

**Constraints**: Offline except loopback provider communication; sequential processing; no partial
Transcript; no model/provider download or build; real-provider semantic tests make no
quality/accuracy assertions against third-party ASR output; no simultaneous-invocation guarantee

**Scale/Scope**: One task work directory and one selected model. Controlled acceptance coverage
spans 1–100 ordered Speech Segments; production processes every valid Segment Manifest entry with
no 100-segment cap. One initial Qwen/llama.cpp adapter has seams for later built-in providers.

## Constitution Check

*GATE: Passed before Phase 0 research, passed again after Phase 1 design, and revalidated against
constitution v2.1.0 on 2026-09-07.*

| Principle | Pre-design gate | Post-design evidence |
|---|---|---|
| I. Test-First Development | PASS | Every work package specifies red-before-green behavior at an approved public seam. Controlled provider data tests project-owned request/response mapping. The real-provider checkpoint explicitly excludes words, WER, language accuracy, throughput, and third-party internals. |
| II. Enforced Architectural Boundaries | PASS | Every planned entity is classified below. Infrastructure imports only Infrastructure; Protocol codecs do not import higher layers; Composition injects Protocol codecs into Infrastructure adapters and assembles all concrete dependencies. |
| III. Simplicity First | PASS | One command, one text artifact, one built-in model, standard-library transport, sequential processing, no download path, no locks, no batching, and no speculative provider capabilities. |
| IV. Scope Traceability | PASS | Tasks map to FR-001-FR-026 and SC-001-SC-006. Explicit non-goals prevent GUI orchestration, diarization, timestamps, downloads, provider builds, and future provider implementations from entering this delivery. |
| V. Complete and Verifiable Plans | PASS | The plan defines entities, layers, relationships, assumptions, acceptance criteria, test seams, deterministic checks, dependencies, parallel waves, and distinct Worker/Validator/Supervisor assignments using the constitution-mandated models and reasoning efforts. |

No constitution exception or complexity justification is required.

## Project Structure

### Documentation for this feature

```text
specs/002-segment-asr/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── evidence/
│   ├── T028-controlled-gates.md
│   ├── T029-real-checkpoints.md
│   └── T030-release-audit.md
├── checklists/
│   └── requirements.md
└── contracts/
    ├── asr-model-manifest.schema.json
    ├── asr-model-manifest.md
    ├── cli.md
    └── execution-provider.md
```

### Planned source and test changes

```text
CONTEXT.md                                      # resolved ASR vocabulary (already updated)
pyproject.toml                                  # transcriber-asr entry point, real_asr marker
README.md                                       # public ASR summary and GUI-owned sequencing

docs/
└── cli.md                                      # detailed ASR CLI and local prerequisites

src/transcriber/
├── domain/
│   ├── manifest.py                            # Segment Manifest entity and internal decoder
│   └── transcript.py                          # Transcript assembly and Recognition Context
├── protocol/
│   ├── asr_cli.py                             # ASR command/success/failure/progress wire values
│   ├── asr_model_manifest.py                  # closed model-manifest entities and codec
│   └── qwen_asr.py                            # Qwen request/response and error codecs
├── infrastructure/
│   ├── asr_files.py                           # task input preflight and Transcript publication
│   ├── execution_provider.py                  # provider interfaces and primitive request values
│   ├── llama_cpp.py                           # managed server lifecycle and loopback transport
│   └── process.py                             # additive managed-process support if required
├── service/
│   ├── prepare_media.py                       # use Domain-owned Segment Manifest after relocation
│   └── recognize_segments.py                  # ordered ASR Task orchestration
├── composition/
│   └── application.py                         # built-in model/provider assembly and facade
├── controller/
│   └── asr_cli.py                             # argument parsing and stable GUI-facing output
└── resources/
    ├── __init__.py
    └── asr_models/
        ├── __init__.py
        └── qwen3-asr-1.7b.json

tests/
├── conftest.py                                # real-ASR options, fixtures, and marker policy
├── architecture/
│   └── test_layer_dependencies.py             # ASR classifications and forbidden imports
├── support/
│   ├── asr.py                                 # controlled models/providers and manifests
│   └── managed_process.py                     # provider process double if needed
├── unit/
│   ├── domain/test_manifest.py
│   ├── domain/test_transcript.py
│   ├── protocol/test_asr_cli.py
│   ├── protocol/test_asr_model_manifest.py
│   ├── protocol/test_qwen_asr.py
│   ├── infrastructure/test_execution_provider.py
│   ├── service/test_prepare_media.py
│   ├── service/test_recognize_segments.py
│   ├── composition/test_asr_application.py
│   ├── controller/test_asr_cli.py
│   ├── test_package_metadata.py
│   └── test_real_asr_prerequisites.py
├── integration/
│   └── infrastructure/
│       ├── test_asr_task_files.py
│       └── test_llama_cpp.py
├── contract/
│   ├── test_asr_cli_contract.py
│   ├── test_asr_documentation_contract.py
│   ├── test_manifest_contract.py
│   ├── test_asr_release_audit_contract.py
│   └── test_asr_model_manifest_contract.py
└── acceptance/
    ├── test_sample_workflow.py
    └── test_asr_workflow.py
```

The Domain migration removes `src/transcriber/protocol/manifest.py` and relocates its unit coverage
from `tests/unit/protocol/test_manifest_codec.py`; the listed Domain path is the replacement.

**Structure Decision**: Extend the existing six-layer Python package. Keep the internal Segment
Manifest plus pure text/context rules in Domain, serialized public/provider/model contracts in Protocol, concrete file/process/HTTP behavior
and its interfaces in Infrastructure, orchestration in Service, dependency/model/provider assembly
in Composition, and CLI behavior in Controller. Model JSON is package data so the catalog remains
available when ignored `models/` artifacts are absent. Do not add native code or modify the
experimental `ep/llama.cpp` checkout.

## Architecture Classification and Relationships

| Entity | Layer | Responsibility | Depends on |
|---|---|---|---|
| `SegmentManifest`, segments, and decoder | Domain | Represent and decode the application's internal ordered Segment Manifest without I/O | Domain only |
| `Transcript` and context-window function | Domain | Trim, join, encode, and derive bounded Recognition Context | Domain only |
| `AsrCommand`, `AsrProgress`, `AsrSuccess`, `AsrFailure` | Protocol/Wire | Closed values crossing Controller/Service and rendered publicly | Protocol only |
| `AsrModelManifest`, artifacts, capabilities, decoder | Protocol/Wire | Validate closed built-in model JSON independently of filesystem state | Protocol only |
| Qwen request/response/error codecs | Protocol/Wire | Encode/decode provider wire messages and remove Qwen control metadata | Protocol only |
| `ExecutionProvider`, session/request primitives | Infrastructure | Runtime-agnostic lifecycle interface using only primitives and local paths | Infrastructure only |
| `LlamaCppExecutionProvider` | Infrastructure | Process lifecycle, loopback health/request transport, timeouts, diagnostic capture | Infrastructure only; receives codecs as callables |
| ASR task file access/validator/publisher | Infrastructure | Read manifest bytes, batch-check primitive segment filenames and expected sample counts, return `True` or raise a typed error, and atomically publish bytes | Infrastructure only |
| Existing `WorkDirectory`, `AtomicFileWriter`, and filesystem failure types | Infrastructure | Preserve workspace creation and atomic-publication behavior while sharing only necessary file helpers with ASR task files | Infrastructure only |
| Existing `WaveMetadata`, `WaveFileReader`, `WaveSegmentWriter`, and WAV helpers | Infrastructure | Preserve canonical WAV inspection and writing while sharing only necessary validation behavior with ASR task files | Infrastructure only |
| Existing `CompletedProcessData`, `ProcessRunner`, `SubprocessRunner`, and additive managed-process helpers | Infrastructure | Preserve command execution and add only the process lifecycle primitives required by the managed provider | Infrastructure only |
| Existing `PrepareMedia`, `PreparationStage`, and preparation boundaries | Service | Preserve the Media Preparation Task workflow while switching its Segment Manifest dependency to the Domain-owned entity and codec | Infrastructure, Protocol, Domain, Service |
| `RecognizeSegments` and lifecycle | Service | Resolve configured model, request file operations, invoke the Domain decoder, order provider calls, submit results to Transcript, emit progress, and map failures | Infrastructure, Protocol, Domain, Service |
| Existing `RepositoryPaths`, `MediaDependencies`, `Application`, and composition builders | Composition | Preserve preparation assembly and facade methods while adding fixed ASR paths, registrations, injected codecs/adapters, and ASR facade methods | All lower layers |
| `asr_cli` | Controller | Parse command, map signals/cancellation, render stable output/status | Protocol, Service, Composition, Controller |

Critical relationship rules:

1. The GUI invokes `transcriber-prepare` and, only after status 0, enables and separately invokes
   `transcriber-asr`; no middleware entity orchestrates both commands.
2. Infrastructure never imports Protocol or Domain. Composition injects Qwen encoder/decoder
   callables into the llama.cpp adapter, following the existing generic decoder pattern in
   `FireRedNcnnProcess`.
3. The provider adapter never writes Transcript files; the service publishes only after every
   ordered recognition succeeds.
4. The ASR Model Manifest points to an Execution Provider ID; users never supply a provider ID.
5. Context capability belongs to the ASR Model Manifest. The service derives context; the provider
   merely carries the supplied value into its native protocol.

## Intended Behavior

1. Parse the existing task work directory, required model ID, and optional language before any I/O.
   A model ID consists of non-empty lowercase ASCII letter-or-digit components separated by a
   single hyphen or dot, with no leading, trailing, repeated, or adjacent separators. Explicit
   language tags use the supported grammar: a 2-8
   letter ASCII primary subtag followed by zero or more 1-8 character ASCII alphanumeric subtags;
   grandfathered and private-use-only forms are rejected as outside scope. An invalid model ID or
   language argument returns status 2 before crossing an application seam.
2. Resolve one syntactically valid built-in model manifest and its composition-owned provider
   registration; an unregistered valid model ID reaches application resolution and returns runtime
   status 1, while an invalid required/automatic language combination returns status 2.
3. Service asks Infrastructure to read `manifest.json`, passes the returned content to the Domain
   Segment Manifest decoder, and rejects zero segments. Service then makes one Infrastructure batch
   call with the ordered segment filenames and expected duration sample counts. Infrastructure
   returns `True` only after every resolved target remains beneath the exact `segments/` directory,
   equals its index-derived `segments/segment-NNNN.wav` value, and has canonical WAV properties and
   the expected frame count; otherwise Infrastructure raises one typed file-validation error. No
   aggregate preflight entity or validated-segment collection exists, and Service performs no
   filesystem operation directly. The complete batch check finishes before loading a model.
4. Aggregate and report missing model artifacts or the fixed provider executable; order the
   project-relative paths with the provider executable first and model artifacts in ASR Model
   Manifest declaration order, and render each path as a JSON string in the message
   `missing prerequisites: PATH, PATH`; do not hash model files, search `PATH`, download, or build
   anything.
5. Start one provider process, choose a loopback endpoint, restrict local media to `segments/`, and
   wait no longer than 60 seconds for health readiness.
6. For each manifest segment in order, derive Recognition Context using FR-009's exact
   Unicode-code-point and `str.isspace()` boundary algorithm, invoke the provider with a
   180-second deadline, parse only recognized text, append non-empty trimmed text, and emit one
   completed-count progress record. Controlled acceptance coverage spans 1–100 Speech Segments;
   production continues through every valid Segment Manifest entry without a 100-segment cap.
7. Accept successful empty segment results. Continue processing and count them in progress.
8. Encode the final Transcript as zero bytes when empty or UTF-8 plus one LF when non-empty; create
   `transcripts-{model-id}` as needed and atomically replace only `transcript.txt`.
9. Stop and reap the provider on success, all failures, timeouts, interruption, and cancellation.
   Allow at most 60 seconds for graceful termination, then force termination and require reaping
   within an additional 10 seconds.
10. Render exactly one final Transcript path on success or one bounded actionable error on failure.
    A segment-specific failure identifies the zero-based Segment Manifest index. The complete
    failure line contains at most 1,023 Python Unicode code points excluding its terminating LF,
    JSON-escapes every dynamic string value, and, when a quoted provider diagnostic is truncated,
    preserves the closing quote and includes the established `...[truncated]` marker. Provider logs
    are never forwarded.

## Assumptions

- The GUI, outside this repository feature, gates ASR availability on successful completion of the
  independent segmentation command.
- A published schema-v1 Segment Manifest is the durable indication that segmentation reached its
  final publication stage, but ASR still validates all consumed artifacts defensively.
- Speech Segment files are application-owned temporary artifacts. Mutation by an external actor
  after the successful pre-start batch validation is outside this feature's threat model.
- `vendor/llama-server` and future provider executables are built and installed by separate release
  work; this feature only requires fixed paths and reports missing prerequisites.
- Qwen files are installed beneath `models/qwen3-asr-1.7b/`; `models/` and `vendor/` remain ignored.
- Release packaging supplies a llama.cpp build compatible with the documented health and
  chat-completion endpoints; host `PATH` is irrelevant.
- The initial GUI uses the supported language-tag grammar defined in the specification. This is an
  intentionally closed subset rather than a claim of complete BCP 47 validation.
- Qwen-specific language-label translation is internal wire adaptation and is not exposed as a
  supported-language catalog or used to choose a model.
- One command processes one task/model at a time. If callers violate the unsupported simultaneous-
  invocation condition, the last successful atomic replacement may win.
- Loopback HTTP is local execution-provider communication and does not violate the external-network
  prohibition.
- The supplied Qwen weights, llama.cpp runtime, and their semantic output are trusted third-party
  dependencies; first-party code owns only integration and adaptation.

## Explicit Non-Goals

- GUI enablement implementation or a combined prepare-and-ASR command
- VibeVoice/VibeASR.cpp, Canary/ONNX, or a second ASR Model implementation
- Model downloads, provider builds, provider downloads, provenance fetching, release packaging
- Model catalog/list CLI, user-editable manifests, arbitrary model/provider combinations
- Model-to-language matching or public supported-language lists
- Word/utterance timestamps, forced alignment, diarization, speaker attribution
- Batch, concurrent, resumable, or streaming recognition
- Lock files or stale-lock recovery for simultaneous invocation
- Partial Transcript publication or per-segment durable recognition records
- ASR quality, WER, accuracy, language-ID, latency, or throughput acceptance gates
- Provider/model checksum calculation during each ASR Task

## Approved Test Seams

The grilling session confirmed these public seams before test planning:

1. **CLI seam**: arguments, progress lines, final path, bounded errors, and status codes.
2. **Service seam**: one ASR Command produces ASR Success/Failure while controlled collaborators
   expose ordered lifecycle calls and progress.
3. **Domain seam**: Transcript append/context/encoding behavior through public methods/functions.
4. **Model-manifest seam**: JSON bytes decode to a closed typed contract or fail.
5. **Qwen protocol seam**: controlled request values encode correctly and controlled response bytes
   return text or a closed decode failure.
6. **Execution Provider seam**: a controlled child process and loopback server expose startup,
   readiness, request, timeout, diagnostic, and stop behavior.
7. **Filesystem seam**: controlled task trees prove one manifest-byte read and one batch segment-file
   check returning `True` or raising a typed error before provider startup; publication atomically
   preserves prior output. Service performs no filesystem operation directly.

Tests must observe these seams rather than private methods or implementation state.

## Implementation Work-Package Plan

`plan.md` owns architectural work packages `WP1`-`WP7`. `tasks.md` is the sole authority for
executable task IDs, task order, dependencies, per-task acceptance criteria, and per-task agent
ownership. Work packages group executable tasks for design traceability; work packages are not a
second executable task system.

All behavioral work uses vertical red-green cycles: add one assertion through an approved public
seam, add only enough production behavior for green, and refactor only while the relevant tests
remain green. Controlled tests never require local ignored Qwen or llama.cpp artifacts.

### Sub-agent execution policy

| Role | Required model | Reasoning effort | Responsibility |
|---|---|---|---|
| Worker `W-TNNN` | `gpt-5.6-terra` | `medium` | Implement one executable task from `tasks.md`, record verification evidence, and submit both to `V-TNNN`. |
| Validator `V-TNNN` | `gpt-5.6-sol` | `medium` | Independently check TNNN against its acceptance criteria, this plan, tests, architecture, and scope, then report to `S-ASR`. |
| Supervisor `S-ASR` | `gpt-5.6-sol` | `light` | Review Validator evidence and accept TNNN or return actionable feedback to its Worker. |

Every executable task receives a newly created Worker and Validator with clean task-specific
context. A Worker or Validator is never reused for another executable task. A rejected task returns
to the same Worker through the same Validator. After three rejected Worker -> Validator ->
Supervisor cycles, work halts and `S-ASR` prepares the constitution-required manual-review summary.

### Deterministic verification policy

- Package-data configuration is checked directly and the built wheel is inspected only after the
  Qwen JSON resource exists.
- Test-support modules are verified by explicit import or by a focused test that consumes them;
  broad test collection is not evidence that an otherwise unused support module imports.
- Architecture tests use controlled illegal-dependency fixtures or real created modules; absence of
  a planned module is not treated as boundary evidence.
- `--real-asr-required` option semantics are tested with controlled present/absent prerequisite
  paths. That controlled task has one deterministic passing test command.
- Real-ASR path resolution is deterministic: `RealAsrPaths` resolves the application root, `vendor/llama-server`, `models/qwen3-asr-1.7b/Qwen3-ASR-1.7B-Q8_0.gguf`, and `models/qwen3-asr-1.7b/mmproj-Qwen3-ASR-1.7B-Q8_0.gguf`. Controlled tests inject a temporary root and assert these resolved paths; T029 uses the same resolver for supplied local artifacts. `--real-asr-required` changes only missing-prerequisite policy.
- Only the final real-provider checkpoint depends on ignored local Qwen and llama.cpp artifacts.
  The dependency is explicit, and its required command must exit 0 rather than skip.

### WP1 - Setup and shared foundations (`T001`-`T006`)

**Scope**: Closed public values, architecture enforcement, Domain-owned Segment Manifest decoding,
base Transcript assembly, exact batch Segment-file/WAV validation, and runtime-neutral Execution
Provider primitives.

**Action**: Establish public values and the architecture gate, then complete four parallel
test-first tasks for Domain manifest relocation, base Transcript behavior, Infrastructure file
access/batch validation, and the Execution Provider contract -> **verify**: focused Protocol,
Domain, Infrastructure, preparation-regression, and architecture tests pass without Qwen/llama.cpp
prerequisites.

**Acceptance criteria**:

- ASR public values are closed and typed; Transcript encoding is deterministic.
- Service reads Segment Manifest content only through Infrastructure and decodes the content through
  Domain. One Infrastructure call batch-checks every ordered filename and expected sample count,
  returns `True` only for complete success, and otherwise raises a typed error before provider work.
- Existing Segment Manifest paths must already equal `segments/segment-NNNN.wav`; resolved targets
  remain under the exact `segments/` directory and match canonical WAV/duration facts. No aggregate
  preflight result or validated-segment collection is introduced.
- `tests/unit/infrastructure/test_execution_provider.py` covers only project-owned primitive values
  and lifecycle guards, not Python typing machinery or provider internals.
- Test-support builders are created only in the first task that consumes them, and each support
  module has a direct focused consumer.

### WP2 - US1 baseline Qwen model and provider (`T007`-`T009`)

**Dependencies**: Manifest/package and codec tasks may start after the architecture gate; the
managed-provider task additionally depends on the WP1 Execution Provider contract. WP3 convergence
waits for all WP1 and WP2 tasks.

**Scope**: Valid built-in Qwen manifest/resource, baseline Qwen request/response codecs, and managed
llama.cpp happy-path transport. Baseline codecs support empty Recognition Context and automatic
language before any Composition task may inject them.

**Action**: Complete the valid manifest/package-data and codec tasks in parallel before the
llama.cpp task consumes injected codec callables -> **verify**: controlled manifest, exact Qwen byte
mapping, and managed-provider happy-path tests pass; wheel inspection finds the JSON resource.

**Acceptance criteria**:

- Qwen manifest data exactly matches the approved artifact/source/provider contract and loads when
  `models/` is absent.
- Qwen codecs exist before Composition, remove provider control metadata, accept empty recognized
  text, and import no higher layer.
- The adapter invokes the fixed executable with the approved loopback-only argv, loads once, serves
  ordered local requests, and reaps on normal completion.

### WP3 - US1 production-usable command (`T010`-`T013`)

**Dependencies**: WP1 and WP2 accepted.

**Scope**: Happy-path Service lifecycle, minimum built-in Qwen/llama.cpp registration, fixed-path
Composition, GUI-facing CLI, and controlled end-to-end MVP acceptance.

**Action**: Compose the already-existing Qwen codecs and provider behind the Service, then expose the
independent CLI -> **verify**: Service, Composition, Controller, contract, preparation-regression,
and controlled 1/3/100-segment acceptance tests pass.

**Acceptance criteria**:

- The US1 checkpoint is production-usable when supplied local Qwen/llama.cpp prerequisites exist;
  it is not merely a controlled-provider abstraction.
- Composition alone owns the minimum `qwen3-asr-1.7b` -> `llama-cpp` registration and fixed path
  resolution; later work may validate or extend registrations but does not recreate this assembly.
- Every Speech Segment is recognized exactly once in manifest order, empty results count in progress,
  and complete Transcript bytes are published atomically.
- `transcriber-asr` remains independent from `transcriber-prepare` and preserves preparation behavior.

### WP4 - US2 continuity and language intent (`T014`-`T017`)

**Dependencies**: WP3 accepted.

**Scope**: Bounded Recognition Context, explicit-language Qwen mapping, required/optional language
behavior, exact supported language-tag grammar, and controlled story acceptance.

**Action**: Extend Domain and Qwen codecs in parallel, then perform one cohesive cross-layer
Service/Composition/Controller test-first integration task -> **verify**:
2,047/2,048/2,049-code-point boundaries, explicit `en-GB`, context-disabled models,
required-language rejection, and FR-009's whitespace, punctuation, hyphen, and no-whitespace
examples all pass.

**Acceptance criteria**:

- Supported tags have a 2-8 letter ASCII primary subtag and optional 1-8 character ASCII
  alphanumeric subtags; `auto` remains the default.
- Context follows FR-009's exact Unicode-code-point and `str.isspace()` algorithm, including
  leading-fragment removal after a non-whitespace Unicode-code-point cut, remaining leading
  whitespace removal, and empty context when no whitespace follows a truncation-created cut.
- Required automatic language fails before file/provider work; no supported-language catalog or
  model-to-language matching appears.

### WP5 - US3 safe progress and failures (`T018`-`T022`)

**Dependencies**: Provider hardening may start after WP2; publication hardening may start after WP3;
Service convergence depends on the WP4 integration task and both Infrastructure hardening tasks.

**Scope**: Provider deadlines/cleanup, atomic failure preservation, Service failure translation,
bounded CLI errors/signals, and the complete controlled failure matrix.

**Action**: Build provider and publisher test-first tasks alongside the disjoint WP4 Domain/Protocol
work, then converge in Service, CLI, and acceptance -> **verify**: controlled clocks reach
60/180-second deadlines without wall-clock sleeps; all documented failure boundaries preserve prior
output and remove temporary artifacts.

**Acceptance criteria**:

- One progress event follows each completed Speech Segment and no success line follows a failure.
- Provider diagnostics are separate and quoted. Segment-specific failures identify the zero-based
  Segment Manifest index; the complete public failure line is at most 1,023 Python Unicode code
  points excluding its terminating LF, JSON-escapes every dynamic string value, and preserves the
  closing quote with the established `...[truncated]` marker when truncation is necessary.
- Startup, request, publication, interruption, and cancellation paths stop and reap the provider.
- The SC-003 controlled matrix covers every documented boundary; SC-004 uses controlled clocks.

### WP6 - US4 built-in availability hardening (`T023`-`T025`)

**Dependencies**: Manifest hardening may start after WP2's valid-manifest task; registry/Service
hardening depends on the WP5 Service convergence and manifest hardening; the acceptance checkpoint
is serialized after the US3 acceptance task because both modify the same file.

**Scope**: Exhaustive invalid-manifest rejection, unknown model behavior, aggregate missing fixed
prerequisites, and proof that another valid built-in registration does not change Transcript rules.

**Action**: Harden the existing US1 registry and valid decoder without recreating baseline Qwen
assembly -> **verify**: all controlled structural/semantic invalid forms and availability outcomes
pass without network access or Transcript mutation.

**Acceptance criteria**:

- US4 does not duplicate US1's Qwen codec, provider adapter, or fixed registration implementation.
- Unknown models fail before task/output access; every missing model/provider path is reported before
  provider startup; model files are not rehashed.
- A second valid manifest and compatible registration use the unchanged Transcript assembly Service.

### WP7 - Controlled gates, real checkpoint, docs, and audit (`T026`-`T030`)

**Dependencies**: WP6 accepted. Only the final real checkpoint also depends on supplied ignored Qwen,
llama.cpp, and existing real-VAD prerequisites.

**Scope**: Controlled pytest-option behavior, real integration test definition, documentation,
deterministic gates, required local checkpoints, and final traceability audit.

**Action**: First prove required/optional real-ASR selection with controlled paths, then run all
controlled gates; run real checkpoints only in the explicit prerequisite-dependent task ->
**verify**: controlled suites/static checks and both required real checkpoints exit 0, followed by a
zero-gap FR/SC/scope/architecture audit.

**Acceptance criteria**:

- Missing prerequisites produce a controlled required-mode failure and optional-mode skip without
  making an earlier task conditionally acceptable.
- The real ASR checkpoint proves only project-owned fixed-path invocation, local request/response
  adaptation, progress, publication, and cleanup.
- Documentation contains no model/provider download or build instructions and states GUI-owned
  sequencing.
- No real-provider semantic test asserts recognized words, non-empty text, WER, language
  correctness, latency, throughput, or provider/model internals. Controlled fixtures retain exact
  Transcript-content and non-empty assembly assertions for project-owned behavior.

### Work-package to executable-task crosswalk

| Work package | Executable tasks in `tasks.md` | Primary delivery |
|---|---|---|
| WP1 | T001-T006 | Shared contracts, architecture, Domain, and Infrastructure foundations |
| WP2 | T007-T009 | US1 valid manifest, baseline codecs, managed provider |
| WP3 | T010-T013 | US1 Service, Composition, CLI, controlled MVP |
| WP4 | T014-T017 | US2 context and language intent |
| WP5 | T018-T022 | US3 progress, failures, deadlines, cancellation |
| WP6 | T023-T025 | US4 availability and registration hardening |
| WP7 | T026-T030 | Controlled gates, real checkpoints, docs, audit |

## Parallelization Map

```text
WP1 foundations
  T001 public values -> T002 architecture gate
  T002 -> {T003 Domain Manifest, T004 Transcript,
           T005 Segment/files, T006 Provider contract}

WP2/WP3 US1
  T002 -> {T007 Manifest/package, T008 Qwen codec}
  {T006, T008} -> T009 Provider
  {T003-T007, T009} -> T010 Service -> T011 Composition -> T012 CLI -> T013 MVP

Post-MVP parallel wave
  T013 -> {T014 Context, T015 Qwen extension, T019 Publication failures}
  T009 -> T018 Provider failures
  T007 -> T023 Manifest hardening

Story convergence
  {T012, T014, T015} -> T016 US2 integration -> T017 US2 acceptance
  {T016, T018, T019} -> T020 Service failures -> {T021 CLI failures, T024 Availability}
  {T017, T021} -> T022 US3 acceptance
  {T020, T023} -> T024; {T022, T024} -> T025 US4 acceptance

WP7 release
  T025 -> {T026 controlled real-option behavior, T027 documentation}
  {T026, T027} -> T028 controlled gates -> T029 real gates -> T030 audit
```

Tasks marked `[P]` in `tasks.md` own disjoint primary files and have no incomplete dependency. Shared
Service, Composition, Controller, acceptance, and documentation files are serialized at the
convergence points above. The diagram shows capability order; the explicit dependency on each task
line remains authoritative.

## Test Plan

### Test-first execution

For every behavioral executable task, each listed behavior is a separate tracer cycle:

1. Add one assertion through an approved seam -> verify: the assertion names one task acceptance criterion and recorded test output shows the project-owned behavior is absent rather than a setup failure.
2. Run the narrowest red target -> verify: the recorded command exits nonzero for the new assertion alone and identifies the expected missing behavior.
3. Add the minimum green behavior -> verify: the implementation change is limited to the acceptance criterion named by the assertion and makes that assertion pass.
4. Rerun the narrow target -> verify: recorded output exits 0 for the focused test with no skipped, xfailed, or xpassed result where the task acceptance criteria require those counts to be zero.
5. Continue to the next non-speculative behavior -> verify: the task record maps the next assertion to a remaining acceptance criterion and records no behavior outside the approved task scope.
6. Validator checks edge cases and architecture/static rules -> verify: the Validator report records the required edge-case, architecture, and static-rule commands passing against the task acceptance criteria.

### Deterministic controlled suite

```bash
uv run pytest -m "not real_vad and not real_asr"
uv run mypy --strict src
uv run ruff check src tests
```

T028 runs only the controlled commands in this section and the controlled-only sections below; it
does not run a real-provider command, real-VAD command, or real-ASR command. For every pytest
command in T028, T028 records the pytest outcome counts and validates `skipped=0`, `xfailed=0`, and
`xpassed=0`; recording counts without rejecting any nonzero count does not satisfy the gate.

Required coverage:

- Domain: Segment Manifest decoding and invariants; empty/non-empty accumulation, whitespace,
  joining, 2,047/2,048/2,049 Unicode-code-point windows,
  leading-fragment removal after a non-whitespace Unicode-code-point cut using `str.isspace()`,
  non-ASCII Unicode code points, deterministic encoding.
- Protocol: closed ASR values, model manifest schema/semantic path rules, Qwen automatic/explicit
  request bytes, all documented output forms, malformed response/error extraction.
- Infrastructure: manifest-byte reading, one complete batch check before provider work, `True` or a
  typed validation error, safe paths/symlinks, all WAV mismatches,
  atomic replacement/failure, exact provider argv, loopback-only transport, health/process races,
  port retry, timeouts, bounded termination, diagnostic capture.
- Service: lifecycle ordering, context on/off, required/optional language, empty results, monotonic
  progress, failure translation at every stage, cancellation, no partial publication.
- Controller/Composition: exact CLI contract and statuses, signal handling, fixed paths from foreign
  CWD, package resources without weights, preparation regression.
- Architecture: every planned entity imports only allowed layers; interfaces and implementations
  share Infrastructure classification.

### Controlled real-ASR prerequisite behavior

```bash
uv run pytest tests/unit/test_real_asr_prerequisites.py -q
```

Controlled temporary paths prove that optional mode skips and `--real-asr-required` mode fails with
a bounded prerequisite message when artifacts are absent. This test never needs the real provider or
model and gives T026 one deterministic passing verification command.

### Package-resource verification (controlled only)

```bash
uv build --wheel
unzip -l dist/transcriber-0.1.0-py3-none-any.whl \
  | rg -F 'transcriber/resources/asr_models/qwen3-asr-1.7b.json'
```

These commands verify package contents only. They do not invoke a real provider, require model
artifacts, or run the real-VAD or real-ASR checkpoints reserved for T029.

### Existing real-VAD regression

```bash
uv run pytest --real-vad-required -m real_vad tests/acceptance/test_sample_workflow.py -q
```

This proves ASR additions do not alter segmentation behavior.

### Required real-ASR integration

```bash
uv run pytest \
  --real-asr-required \
  -m real_asr \
  tests/acceptance/test_asr_workflow.py -q -s
```

The real-provider semantic test may assert fixed-path resolution, successful provider startup,
local request completion, schema/metadata adaptation, progress count matching manifest count,
atomic artifact existence, and provider cleanup. The real-provider semantic test must not assert
transcript words, non-emptiness, WER, language correctness, model latency/throughput, or internal
llama.cpp/Qwen behavior. Controlled fixtures retain exact Transcript-content and non-empty assembly
assertions.

### Contract regression

```bash
uv run pytest tests/contract tests/architecture -q
uv run pytest tests/unit/controller/test_cli.py tests/unit/composition/test_application.py -q
```

The first command protects both public command contracts and layer rules. The second protects the
existing preparation command/application facade while Composition is extended.

## Requirement-to-Task Traceability

| Requirement area | Tasks |
|---|---|
| Independent command and GUI sequencing boundary (FR-001, FR-003, FR-026) | WP3, WP7; T010-T013, T027, T030 |
| Language input and model capability (FR-002, FR-011, FR-012) | WP2, WP4; T008, T014-T017 |
| Manifest/segment/model/provider preflight (FR-004-FR-006, FR-020-FR-023) | WP1-WP3, WP6; T003, T005, T007, T010-T013, T023-T025 |
| Provider lifecycle, context, and ordered recognition (FR-007-FR-010, FR-017, FR-024) | WP1-WP5; T004, T006, T008-T010, T014-T020 |
| Progress, publication, failures, and status (FR-013-FR-019) | WP1, WP3, WP5; T001, T005, T010-T013, T018-T022 |
| Offline execution (FR-025) | WP2-WP7; T008-T013, T015-T019, T023-T030 |
| Measurable outcomes SC-001-SC-006 | WP3-WP7; T013, T017, T022, T025, T028-T030 |

## Risks and Mitigations

| Risk | Mitigation and verification |
|---|---|
| llama.cpp changes the Qwen response prefix or error body | Keep response parsing in one Protocol codec; controlled variants and malformed forms are contract-tested; shipped provider is fixed. |
| Child logs fill a pipe and deadlock | Drain to a bounded/captured sink independent of public output; stress with controlled large diagnostics. |
| Ephemeral port is claimed between selection and child bind | Detect address-in-use/failed readiness and retry endpoint selection within the 60-second startup budget. |
| Cancellation leaves a child process | Centralize idempotent stop/reap in provider cleanup; allow 60 seconds for graceful termination, then force termination and require reaping within 10 additional seconds under controlled-clock tests. |
| Prior Transcript is lost during failure | Never open destination for truncation; stage and atomically replace only after complete success; inject write/replace failures. |
| Context begins after a non-whitespace Unicode-code-point cut | Domain boundary tests use worked 2,049+ Unicode-code-point literals and verify the exact expected suffix. |
| Model manifest becomes a speculative plugin system | Keep schema closed, resources built-in, and no user file path or list/download operation. |
| Real test becomes a model-quality oracle | Validator rejects expected words, WER, non-empty output, performance thresholds, or semantic comparisons per constitution v2.1.0. |

## Completion Conditions

Implementation is complete only when:

1. WP1-WP7 are complete because authoritative executable tasks T001-T030 in `tasks.md` are accepted
   through their distinct Worker/Validator/Supervisor chains within the three-cycle limit.
2. All deterministic, architecture, typing, and lint gates pass.
3. Existing required segmentation acceptance remains green.
4. Required real-ASR integration passes with supplied local prerequisites and no semantic quality
   assertion.
5. CLI, model manifest, provider, data model, quickstart, root docs, and implementation behavior are
   consistent.
6. Review confirms that GUI sequencing remains external and no explicit non-goal entered the diff.

## Complexity Tracking

No constitution violations require justification.
