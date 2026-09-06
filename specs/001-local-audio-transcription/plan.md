# Implementation Plan: Media Audio Segmentation Middleware

**Branch**: `codex/media-audio-segmentation` | **Date**: 2026-09-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-local-audio-transcription/spec.md`

## Summary

Build a local Python 3.12 CLI that validates media through the repository-bundled FFmpeg, creates one exclusive task work directory, requests canonical mono 16 kHz signed-16-bit PCM WAV extraction through fixed FFmpeg arguments, passes the result directly to non-streaming FireRedVAD through a pinned NCNN native provider, invokes the pinned upstream FireRedVAD postprocessor unchanged through a thin adapter, writes sample-aligned segment WAVs, and atomically publishes a versioned JSON manifest. Tests cover first-party integration boundaries and do not independently inspect FFmpeg output parameters, derive FireRedVAD frame counts, inspect chunk ordering, assert third-party segmentation output, or inspect supplied fixture properties. The NCNN integration is a small first-party layered C++ subprocess application with a closed JSON probability contract that reports its own frame count; no Python NCNN, PyTorch, GUI, API, downloading, transcription, or diarization is included.

## Technical Context

**Language/Version**: Python 3.12 for middleware; C++14 for the native FireRedVAD/NCNN runner  
**Primary Dependencies**: Python standard library plus NumPy required by the pinned upstream FireRedVAD postprocessor; pinned FireRedVAD Python postprocessor source; pinned NCNN `20260113` static CPU library; repository `vendor/ffmpeg`; Hatchling/uv for packaging; pytest, mypy, and Ruff for development  
**Storage**: Local files only (`prepared.wav`, `segments/*.wav`, `manifest.json`); no database  
**Testing**: pytest unit/architecture/contract/integration/acceptance suites; strict mypy; Ruff; subprocess-level native and CLI checks  
**Target Platform**: Local macOS development/packaging, initially Darwin ARM64; the current x86_64 bundled FFmpeg is accepted only when its startup check succeeds on the host  
**Project Type**: Single local CLI with a native execution-provider helper  
**Performance Goals**: No additional normative latency target; bound each NCNN inference call to at most 30,000 frames while preserving one continuous probability timeline  
**Constraints**: Offline task execution; repository-bundled FFmpeg; no runtime downloads; exact local asset paths; fixed canonical extraction arguments; no independent FFmpeg-result or fixture-property assertions; unchanged upstream-authoritative postprocessing; advisory rather than strict split target; no manifest published before all segments validate  
**Scale/Scope**: One local task and one extracted audio stream per invocation; no multi-stream selection or processing; no product-level input-duration ceiling, subject to local memory/disk; one CLI operation and manifest schema v1

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle/gate | Pre-research result | Evidence |
|---|---|---|
| I. Test-First Development | PASS | Every implementation workstream below starts with a named failing test and requires recorded red/green evidence before validation. |
| II. Enforced Architectural Boundaries | PASS | All production entities are classified in [data-model.md](data-model.md); layer packages are separate; Controller does not import Infrastructure; Domain remains pure. |
| III. Simplicity First | PASS | One command, standard-library Python runtime, concrete adapters, no speculative ports/frameworks, and one subprocess native boundary. |
| IV. Scope Traceability | PASS | Workstreams map only to FR-001–FR-035 and SC-001–SC-006; explicit non-goals are repeated below. |
| V. Complete and Verifiable Plans | PASS | Assumptions, intended behavior, affected files, tests, roles, dependencies, acceptance criteria, deterministic verification, and three-cycle escalation are defined. |
| Planning Architecture Gate | PASS | Each new class/function/package has one layer; the first-party C++ provider separates Infrastructure, Protocol, Service, Composition, and Controller; copied third-party source and tests are exempt. |

No constitutional exception or complexity waiver is required.

## Phase 0 Research Outcome

[research.md](research.md) resolves all technical unknowns and records:

- Python 3.12, `uv`, Hatchling, standard-library runtime, and test tooling.
- A repository-owned native subprocess rather than an unstable Python NCNN binding or diagnostic-output parser.
- Pinned upstream FireRedVAD frontend provenance, NCNN integration boundaries, postprocessing order, chunking, build pins, hashes, and licenses.
- Unchanged use of the pinned upstream FireRedVAD postprocessor and its native frame-counting semantics.
- Advisory split-target conversion and exact `max_speech_frame` handoff without a first-party splitting policy.
- FFmpeg argv, WAV slicing, manifest publication, platform limits, and the unproven fixture acceptance risk.

Independent validation accepted Phase 0 in cycle 1 after the corrections above. No unresolved technical question remains.

## Project Structure

### Documentation (this feature)

```text
specs/001-local-audio-transcription/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── evidence/                # one red/green or review record per evidence-producing task
│   ├── T017-media-ingestion.md
│   ├── T042-real-provider.md
│   ├── T045-quality-suite.md
│   └── T047-release-review.md
├── implementation-evidence.md  # final aggregation created after all task records
├── contracts/
│   ├── cli.md
│   ├── manifest.schema.json
│   ├── manifest.md
│   ├── firered-probabilities.schema.json
│   └── firered-runner.md
└── tasks.md                 # created later by $speckit-tasks
```

### Source Code (repository root)

```text
pyproject.toml
uv.lock

src/transcriber/
├── __init__.py
├── infrastructure/
│   ├── __init__.py
│   ├── process.py
│   ├── ffmpeg.py
│   ├── firered_ncnn.py
│   ├── firered_postprocessing.py
│   ├── filesystem.py
│   └── wave_files.py
├── protocol/
│   ├── __init__.py
│   ├── cli.py
│   ├── firered_probabilities.py
│   └── manifest.py
├── domain/
│   ├── __init__.py
│   ├── audio.py
│   └── segments.py
├── service/
│   ├── __init__.py
│   └── prepare_media.py
├── composition/
│   ├── __init__.py
│   └── application.py
└── controller/
    ├── __init__.py
    ├── __main__.py
    └── cli.py

native/firered_vad_ncnn/
├── CMakeLists.txt
├── LICENSE
├── NOTICE.md
├── infrastructure/
│   ├── firered_frontend_adapter.cpp
│   ├── firered_frontend_adapter.hpp
│   ├── ncnn_inference.cpp
│   └── ncnn_inference.hpp
├── protocol/
│   ├── probability_json.cpp
│   ├── probability_json.hpp
│   ├── runner_command.cpp
│   └── runner_command.hpp
├── service/
│   ├── run_inference.cpp
│   └── run_inference.hpp
├── composition/
│   ├── application.cpp
│   └── application.hpp
└── controller/
    └── main.cpp

third_party/firered-vad/
├── LICENSE
├── NOTICE.md
├── manifest.json
├── runtime-common-frontend/  # pinned upstream feature/WAV sources
└── fireredvad/
    └── vad.py                # pinned unchanged upstream postprocessor

third_party/ncnn/
├── LICENSE.txt
└── manifest.json

scripts/
└── build-firered-vad-ncnn-macos.sh

tests/
├── conftest.py
├── support/
│   ├── audio.py
│   ├── process.py
│   └── call_log.py
├── architecture/
│   └── test_layer_dependencies.py
├── unit/
│   ├── test_package_metadata.py
│   ├── domain/
│   │   ├── test_audio.py
│   │   └── test_segments.py
│   ├── protocol/
│   │   ├── test_cli.py
│   │   ├── test_probability_codec.py
│   │   └── test_manifest_codec.py
│   ├── composition/
│   │   └── test_application.py
│   ├── service/
│   │   └── test_prepare_media.py
│   └── controller/
│       └── test_cli.py
├── integration/
│   ├── native/
│   │   ├── test_firered_runner.py
│   │   └── test_build_firered_runner.py
│   └── infrastructure/
│       ├── test_ffmpeg.py
│       ├── test_filesystem.py
│       ├── test_media_ingestion_boundary.py
│       ├── test_firered_ncnn.py
│       ├── test_firered_postprocessing.py
│       └── test_wave_files.py
├── contract/
│   ├── test_cli_contract.py
│   └── test_manifest_contract.py
└── acceptance/
    └── test_sample_workflow.py
```

**Structure Decision**: Use one `src/` Python distribution with one package per architecture layer. Keep the custom C++ provider under `native/firered_vad_ncnn/`, with its thin first-party integration code split into the same five participating layers. Compile the pinned, trusted upstream FireRedVAD frontend sources from architecture-exempt `third_party/`; do not recreate their signal-processing implementation in first-party code. Build output goes to ignored `vendor/firered-vad-ncnn`; model weights remain unchanged under ignored `models/firered-vad.ncnn`.

## Intended Behavior

1. Parse and validate paths and the advisory split target before any external work.
2. Resolve and startup-check repository `vendor/ffmpeg`; never search `PATH`.
3. Fully decode one source audio stream to a null sink before creating the requested work directory; do not inspect, compare, or report alternative streams.
4. Create the exact unused task path, then extract that one stream as `prepared.wav` with fixed canonical settings.
5. Pass the extracted WAV directly to the native runner, whose canonical-input contract accepts valid input and rejects invalid input without a separate middleware inspection of FFmpeg output parameters.
6. Resolve/check the four pinned model assets and `vendor/firered-vad-ncnn`.
7. Pass the WAV through the compiled pinned FireRedVAD C++ frontend and supplied CMVN/NCNN assets. For input longer than one internal inference chunk, accept the runner's single closed probability document and validate only its reported-count/array-length coherence without deriving an expected frame count or checking chunk order.
8. Pass the returned probability sequence and pinned settings, including the command-derived `max_speech_frame`, once to the unchanged upstream FireRedVAD postprocessor; adapt its returned intervals without correcting, reinterpreting, or duplicating its state-machine, merge, extension, or split behavior.
9. Accept ordered positive in-file sample intervals unchanged, reject invalid intervals, and build a manifest entity in memory.
10. Write and reopen every segment WAV, then atomically publish the manifest.
11. Return the four-line success contract or one actionable stage error with the documented status.

## Assumptions

- The supported initial host is macOS and can execute the bundled FFmpeg; cross-platform artifacts are out of scope.
- Python 3.12 is installed or provisioned by `uv`; the host system Python is not used implicitly.
- NCNN `20260113` has been built locally and exposed through `NCNN_ROOT` before building the native runner.
- FireRedVAD source is pinned at `c30ec49e8cc69642b0ee65362eba11b9d11c6e54`; NCNN is pinned at `e956fbf9bd97fe945df35d736747dc816f8b5f42`.
- The native provider remains a separately licensed executable with FireRedVAD/NCNN notices and is not linked into the GPL-2.0 Python process; distributions require a license/notice review.
- The four model files and bundled executables are local prerequisites and are not downloaded by tests or runtime.
- FireRedVAD's pinned C++ audio frontend, Python postprocessor, NCNN, NumPy, and their mathematical/state-machine implementations are trusted third-party code. First-party tests validate only source/build provenance, adaptation, configuration, canonical input, asset loading, public-document coherence, and preservation of mocked returned intervals; they do not reproduce, correct, or independently prove upstream frame counting, chunk ordering, probability values, or segmentation behavior.
- The 30-second default is advisory. First-party code passes its whole-frame value as `max_speech_frame` and accepts valid returned intervals even when segment duration crosses the target.
- Each invocation extracts one audio stream. Multi-stream selection, comparison, simultaneous processing, and reporting are outside scope.
- FFmpeg, FireRedVAD/NCNN, and user-supplied fixtures are trusted at their respective boundaries. Tests assert first-party invocation/configuration, input/output handoff, failure translation, interval validity, and generated-artifact correspondence; they do not assert FFmpeg-produced audio parameters or fixture-intrinsic properties.
- The reference manifest is immutable during this feature and may be read only for a non-gating diagnostic report. Its segment count and boundaries never determine acceptance status or trigger output correction.
- Intermediate files may remain after failure, but an incomplete manifest is never published.

## Success Criteria Traceability

| Spec criterion | Planned proof |
|---|---|
| SC-001 | One required fixture-backed integration run verifies task, extracted-audio, schema-valid ordered manifest, and segment artifact correspondence without checking expected FireRedVAD segmentation, FFmpeg output parameters, or fixture properties. |
| SC-002 | Adapter preservation, interval-invariant, and WAV/manifest correspondence tests prove positive duration and unchanged pinned FireRed boundaries. |
| SC-003 | Native black-box tests prove pinned frontend provenance, canonical input handoff, supplied asset loading, public probability schema, and reported-count/array-length coherence for ordinary and long input; postprocessor adapter tests prove exact configuration and unchanged mocked-output handoff without an expected-output or chunk-order oracle. |
| SC-004 | FFmpeg integration/failure tests cover missing, unreadable, corrupt, unsupported, and audio-free input before directory creation. |
| SC-005 | Manifest/WAV contract tests prove one-to-one references and sample-exact duration equality. |
| SC-006 | Service and CLI parameterized failure tests prove correct stage, terminal failure, status, and no false success. |

## Functional Requirement Traceability

Every normative requirement is assigned to an implementation workstream and a deterministic proof. A workstream is not accepted until all requirements in its row have passing evidence.

| Requirements | Owning workstreams | Deterministic proof |
|---|---|---|
| FR-001, FR-019, FR-020, FR-021 | W1, W6 | Package/entry-point smoke test plus CLI contract tests for arguments, optional split target, exact success fields, failure labels, and statuses. |
| FR-002, FR-003, FR-004, FR-006, FR-007, FR-008 | W4, W6 | FFmpeg boundary tests assert repository-absolute `vendor/ffmpeg` argv, full-decode and canonical extraction arguments, process/failure handoff, and absence of the task path after validation failure; they do not inspect FFmpeg-produced sound parameters or fixture properties. The native runner separately enforces its input contract. |
| FR-005 | W4, W6 | Exclusive-directory adapter tests and Service failure-prefix tests prove exact-path creation only after decode and refusal to reuse a target. |
| FR-009, FR-022, FR-024, FR-025, FR-026, FR-027, FR-032 | W2, W5 | Native-provider tests prove pinned frontend provenance, canonical WAV input handoff, public probability schema, reported-count/array-length coherence for ordinary and long input, and offline execution without calculating an expected FireRedVAD frame count or asserting probability values or chunk ordering. Supplied NCNN/CMVN asset loading remains part of the integration acceptance boundary rather than a separate functional requirement. |
| FR-010 | W3, W6 | Domain interval-invariant tests and Service call-order tests reject unordered, empty, overlapping, or out-of-bounds intervals before artifact creation. |
| FR-011, FR-012, FR-016 | W3, W6 | Manifest schema/semantic contract tests prove exact fields, sample arithmetic, safe paths, and the empty-speech result. |
| FR-013, FR-014, FR-015 | W4, W6, W7 | Synthetic-input WAV-slice integration tests prove format preservation and one exact generated file per record; orchestration and end-to-end boundary tests prove complete in-directory correspondence before publication without inspecting FFmpeg output parameters. |
| FR-017, FR-018 | W6 | Parameterized Service call-log tests prove the full stage sequence and that each failure stops the exact remaining suffix. |
| FR-023, FR-028, FR-029, FR-030, FR-031, FR-033, FR-034, FR-035 | W3, W5 | Black-box adapter tests prove exact upstream settings, including the advisory `max_speech_frame`, are passed once, canonical `total_samples / 16000` is supplied as upstream `wav_dur`, the pinned postprocessor is loaded from its recorded source, and returned timestamps are mechanically represented as exact 16 kHz sample boundaries in order; Domain tests validate and copy `SampleInterval` values using only middleware-owned positive-duration, bounds, ordering, and non-overlap rules. No upstream algorithm is reimplemented, corrected, or asserted. |

## Explicit Non-Goals

- Qwen-ASR execution, transcript generation, transcript assembly, or quality scoring.
- llama.cpp build or invocation.
- Model/runtime/FFmpeg downloading, conversion, selection, training, or updating.
- Speaker diarization, language detection, translation, subtitles, or enrichment.
- GUI, worker, API, remote deployment, authentication, scheduling, multi-user operation, or parallel task execution.
- Multiple-audio-stream selection, comparison, simultaneous processing, or reporting.
- Streaming VAD, automatic retries, partial-task resume, Windows/Linux packaging, or GPU/Vulkan acceleration.
- Treating the sample reference manifest as an acceptance oracle, correcting output toward that reference, or adding speculative provider interfaces.

## Test Plan

### TDD evidence rule

For every behavioral workstream, the Worker records: `(1)` the focused test command failing for the intended missing behavior, `(2)` the minimal production change, and `(3)` the same focused test plus relevant regression suite passing. Each evidence-producing gate writes its own file under `specs/001-local-audio-transcription/evidence/`; the final aggregation task creates `implementation-evidence.md` from those immutable task records. A Validator rejects work without red/green evidence. Refactoring occurs only after green and ends with the same tests green.

### Test layers

| Layer | Scope | Deterministic verification |
|---|---|---|
| Architecture | AST import scan across `src/transcriber` | `uv run pytest tests/architecture` reports no forbidden dependency. |
| Domain unit | Validation and unchanged copying of `SampleInterval` values already adapted from upstream FireRedVAD timestamps | Controlled sample-interval vectors prove only middleware-owned positive-duration, bounds, ordering, non-overlap, and rejection without clamping. Infrastructure adapter tests separately prove exact timestamp-to-16-kHz-sample representation. |
| Protocol unit/contract | CLI DTOs, probability JSON, manifest JSON/schema and semantic constraints | Closed objects, exact constants, count/path/index/duration checks, invalid/nonfinite rejection. |
| Infrastructure integration | Exact repository-bundled FFmpeg argv, exclusive directory, WAV slicing, native runner process classification, and unchanged upstream postprocessor adapter | Tests use process doubles plus sentinel probability and interval values to validate adaptation, configuration, failure translation, and I/O without inspecting FFmpeg-produced audio properties or encoding upstream decision rules. |
| Service unit | Required stage order, terminal failures, in-memory manifest before slices, publication after verification | Parameterized fakes fail each stage; call log equals expected prefix and no later calls occur. |
| Controller/CLI contract | Parser, four-line success, stage error, statuses 0/1/2 | In-process and subprocess tests compare exact stdout/stderr/status. |
| Native-provider integration | Pinned upstream frontend is compiled; canonical WAV boundary; supplied CMVN/weight loading; full-precision schema; reported frame-count/array-length coherence for ordinary and long input; invalid asset/audio exits | Black-box runner tests validate first-party adaptation, configuration, and observable public I/O without deriving expected FireRedVAD frame counts, asserting probability values/order, or independently testing trusted upstream mathematics. |
| Fixture-backed integration acceptance | One complete `fixtures/sample/prepared.wav` workflow | Successful dependency invocation, schema-valid ordered intervals, and generated WAV/manifest correspondence; no expected segment count, reference-boundary tolerance, supplied-fixture property, or FFmpeg-output assertion. |
| Required non-gating sample diagnostic | Generated manifest compared with `fixtures/sample/manifest.json` | Controlled manifest pairs verify same-index pairing through the shorter list, ascending indexes, `actual - reference` start/end sample deltas, and an empty pair array when either list is empty. During the fixture-backed run, verify that exactly one compact `REFERENCE_DIAGNOSTIC={...}` line matches the defined JSON shape while its numeric values have no assertion, exit-status impact, output correction, or release-gating effect. |
| Static quality | Types and lint | `uv run mypy --strict src` and `uv run ruff check src tests`. |

### Required edge vectors

- Empty/shorter-than-400-sample canonical input and short probability documents at the runner/protocol boundary.
- Sentinel complete-timeline probability input, empty/ordered upstream interval output, an arbitrary-millisecond short positive-duration final remainder, non-frame-aligned split-target configuration, and upstream intervals over the advisory target. These vectors test exact representation and preservation only, not FireRedVAD's splitting algorithm.
- NaN/infinite/out-of-range probabilities, mismatch between the runner-reported frame count and probability-array length, malformed JSON, invalid returned intervals, and escaping paths.
- Existing/unwritable work path, missing/incompatible executables/assets, decode failure, disk/write failure, and manifest publication failure.

## Implementation Workstreams and Agent Plan

### Role protocol

- **Worker**: writes the failing tests first, records red/green commands and outputs, implements only the assigned scope, and submits evidence to the Validator.
- **Validator**: a different agent independently checks acceptance criteria, tests, architecture, type/lint status, simplicity, and spec traceability; it reports evidence to the Supervisor.
- **Supervisor**: a third agent accepts the Validator report or returns actionable feedback to the Worker.
- A work item may have at most three Worker → Validator → Supervisor cycles. If cycle 3 is not accepted, all work on that item stops and the Supervisor prepares the constitution-required manual-review summary.
- With four available agent slots, up to three independent Workers may run concurrently. Validation begins after Worker submission and is performed by an agent that did not implement that item; the root agent acts as Supervisor.

### Workstream table

| ID | Owner roles | Dependencies | Safe parallelism | Files/components | Test-first action and deterministic verification | Acceptance criteria |
|---|---|---|---|---|---|---|
| W1 — Project and architecture scaffold | Worker `W-Scaffold`; Validator `V-Common`; Supervisor `S-Root` | None | Must complete first | `pyproject.toml`, `uv.lock`, package directories, `tests/architecture`, `tests/unit/test_package_metadata.py`, pytest configuration | Add failing package-metadata and architecture tests before the packages/entry point exist, then add the minimal scaffold -> verify: `uv run pytest tests/architecture tests/unit/test_package_metadata.py -q` passes with no skipped or expected failures. | Python 3.12 project syncs reproducibly; console entry point resolves; every package maps to one layer; Controller has no Infrastructure import; no runtime Python dependency beyond the pinned NumPy dependency required by the unchanged upstream postprocessor is added. |
| W2 — Native FireRed/NCNN provider | Worker `W-Native`; Validator `V-Common`; Supervisor `S-Root` | W1 plus W3 probability-protocol checkpoint | Parallel with remaining W3 and W4 work after the protocol checkpoint | `native/firered_vad_ncnn/{infrastructure,protocol,service,composition,controller}`, pinned upstream sources in `third_party/firered-vad`, `third_party/ncnn`, build script, native/Python integration tests | First write black-box tests proving the pinned upstream frontend is compiled, the supplied `prepared.wav` path is handed off and accepted without independent fixture inspection, supplied CMVN/weights load, and the public document reports a frame count equal to its probability-array length for ordinary and long input; then add only runner adaptation, configuration, wire protocol, and build glue -> verify: build with explicit `NCNN_ROOT`; `uv run pytest tests/integration/native tests/integration/infrastructure/test_firered_ncnn.py -q` passes. | Build downloads nothing; first-party code does not recreate the upstream frontend; tests trust third-party mathematics and fixture inputs and cover only provenance/configuration/public-boundary behavior; executable is host-native and machine-only on stdout; native Controller imports no Infrastructure; exit classes match contract; no test asserts chunk boundaries, probability ordering, or an expected frame count; provider license/notices, pins, and hashes are recorded and reviewed. |
| W3 — Protocol, upstream postprocessor adapter, and segment Domain | Worker `W-Domain`; Validator `V-Common`; Supervisor `S-Root` | W1 | Parallel with W2 and W4 | `src/transcriber/protocol`, `src/transcriber/infrastructure/firered_postprocessing.py`, pinned `third_party/firered-vad/fireredvad/{vad.py,core/vad_postprocessor.py}`, `src/transcriber/domain/audio.py`, `src/transcriber/domain/segments.py`, unit/contract/integration tests | Add failing codec tests, a controlled canonical-timeline invariant test, black-box postprocessor adapter tests, and pure interval/sample invariant tests; then stage the unchanged pinned upstream postprocessor and implement only the adapter/codecs/Domain validation -> verify: `uv run pytest tests/unit/domain tests/unit/protocol tests/contract/test_manifest_contract.py tests/integration/infrastructure/test_firered_postprocessing.py -q` passes. | Closed wire objects validate; exact upstream settings are supplied once; returned intervals remain authoritative and chronological; no upstream comparison, smoothing, merge, extension, split, or minimum-frame behavior is reimplemented or corrected; middleware-owned manifest and segment invariants hold. |
| W4 — Media, filesystem, and WAV Infrastructure | Worker `W-Media`; Validator `V-Common`; Supervisor `S-Root` | W1 plus W3 canonical-audio/test-support checkpoint | Parallel with later W2 and W3 work after the checkpoint | `src/transcriber/infrastructure/process.py`, `ffmpeg.py`, `filesystem.py`, `wave_files.py`, integration tests | Add failing repository-bundled exact-argv, process/failure-handoff, exclusive-create, segment-slice, atomic-write, and no-hidden-directory-side-effect adapter tests, then implement adapters -> verify: `uv run pytest tests/integration/infrastructure/test_ffmpeg.py tests/integration/infrastructure/test_media_ingestion_boundary.py tests/integration/infrastructure/test_filesystem.py tests/integration/infrastructure/test_wave_files.py -q`. | All FFmpeg paths are repository-derived absolute paths and use `shell=False`; tests validate configured invocation rather than FFmpeg behavior or output sound parameters; media-validation adapters never create the task path; generated slices correspond to requested intervals; existing targets are untouched; atomic publication cannot expose partial JSON. |
| W5 — Early real-provider integration checkpoint | Worker `W-Gate`; Validator `V-Common`; Supervisor `S-Root` | W2, W3 | May run while W4 finishes; blocks W6 | `tests/conftest.py`; minimal acceptance harness using native provider + Domain; `tests/acceptance/test_sample_workflow.py` provider boundary case | Register `--real-vad-required`, assemble the provider/Domain integration case from already-tested components, and run the green checkpoint -> verify: the dedicated command passes for successful invocation, public-document coherence, and ordered valid interval adaptation, while controlled prerequisite/malformed-output cases fail at their documented boundary. | This checkpoint adds no production behavior and therefore does not manufacture a new red phase after implementation. Prerequisites are never silently skipped in required mode; no assertion fixes an expected FireRedVAD segment count, frame count, probability value/order, or reference boundary. |
| W6 — Service, Composition, and CLI | Worker `W-App`; Validator `V-Common`; Supervisor `S-Root` | W3, W4, W5 | Sequential integration point | `service/prepare_media.py`, `composition/application.py`, `controller`, service/controller/CLI tests | Add parameterized failing Service call-log tests and CLI subprocess contract tests before orchestration, including a decode-success event immediately before exclusive work-directory creation, then wire concrete lower layers -> verify: `uv run pytest tests/unit/service tests/unit/controller tests/contract/test_cli_contract.py -q`. | The complete call log proves media decode completes before work-directory creation; every failure is terminal and correctly labeled; manifest entity precedes slices but publication follows verification; stdout/stderr/status match contract; repository paths work from a non-repository CWD. |
| W7 — Full acceptance, quality, and documentation alignment | Worker `W-Acceptance`; Validator `V-Release`; Supervisor `S-Root` | W6 | Final | End-to-end acceptance tests, required non-gating diagnostic output, per-task evidence records, final evidence aggregation, `fixtures/sample/README.md`, root `README.md`, quickstart consistency | Complete the single-run fixture-backed integration and failure-path tests without adding expected FireRedVAD output, fixture-property, or FFmpeg-output assertions, run them red for the incomplete CLI workflow, implement only required fixes, emit the defined diagnostic line, then update fixture prose and aggregate separately recorded task evidence -> verify: all commands in [quickstart.md](quickstart.md), full pytest, strict mypy, Ruff, and the required real-provider integration run pass; diagnostic values never affect status. | SC-001–SC-006 all have recorded boundary evidence; the `REFERENCE_DIAGNOSTIC` line is present; no network use; fixture docs describe FireRedVAD, the advisory target, and the non-gating reference consistently; no out-of-scope code/assets change; review finds no complexity or architecture violation. |

### Dependency and verification flow

```text
W1 ── W3 foundation/protocol
        ├── after canonical-audio/test-support checkpoint ── W4 ─────┐
        ├── after probability-protocol checkpoint ── W2 ──┐         │
        └── remaining W3 work ─────────────────────────────┴── W5 ──┼── W6 ── W7
                                                                    │
                                                                    └──────────
```

Each arrow means the named predecessor or checkpoint has been approved by `S-Root`. W2 and W4 overlap only with the remaining independent W3 work after their explicit task-level checkpoints. W5 is an early integration gate and may not be bypassed.

## Phase 1 Design Outputs

- [data-model.md](data-model.md): entities, fields, relationships, validation, layers, and lifecycle.
- [contracts/cli.md](contracts/cli.md): command, output, stage errors, artifacts, and exit status.
- [contracts/manifest.schema.json](contracts/manifest.schema.json): closed manifest schema v1.
- [contracts/manifest.md](contracts/manifest.md): cross-field, filesystem correspondence, codec, and publication semantics for manifest v1.
- [contracts/firered-probabilities.schema.json](contracts/firered-probabilities.schema.json): closed native probability schema v1.
- [contracts/firered-runner.md](contracts/firered-runner.md): native invocation, I/O, semantic checks, statuses, and versioning.
- [quickstart.md](quickstart.md): reproducible build, deterministic middleware-boundary tests, required real-provider integration and non-gating sample diagnostic, CLI run, and failure checks.

## Planned Implementation Evidence Outputs

- `evidence/*.md`: task-local red/green and review records created during implementation.
- `implementation-evidence.md`: final release aggregation generated only after all task-local evidence records are complete.

## Post-Design Constitution Re-check

| Gate | Result | Design evidence |
|---|---|---|
| Test-first | PASS | Every workstream names the failing test first, focused green command, and regression/static verification. |
| Architecture | PASS | Data model and source tree classify all Python and native entities; native Controller has no Infrastructure dependency; Protocol is closed wire data; Domain is pure. |
| Simplicity | PASS | One CLI, one native executable, concrete collaborators, standard-library runtime, and no speculative API/port hierarchy. |
| Scope traceability | PASS | Success table and workstream acceptance map directly to the approved requirements; non-goals remain excluded. |
| Complete/verifiable plan | PASS | Roles, order, parallel boundaries, three-cycle gate, assumptions, files, tests, and deterministic acceptance are explicit. |

Phase 1 introduces no constitutional violation. Complexity Tracking remains empty.

## Complexity Tracking

No violations require justification.
