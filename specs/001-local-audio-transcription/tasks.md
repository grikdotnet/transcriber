# Tasks: Media Audio Segmentation Middleware

**Input**: Design documents from `specs/001-local-audio-transcription/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Mandatory. Every behavioral task follows red-green-refactor and records the focused failing command before production code is changed.

**Organization**: Tasks are grouped by user story. User Story 1 is an independently testable media-ingestion implementation checkpoint. The provider, protocol, and postprocessor portion of User Story 2 may proceed in parallel after Foundation; its final application integration depends on the US1 kernel and completes the delivery MVP through the CLI, FireRedVAD manifest, and segment WAV files.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Safe to run in parallel after the stated dependencies are accepted because files and incomplete dependencies do not conflict.
- **[Story]**: The user story served by the task.
- Every task names its Worker, dependencies, acceptance condition, exact file path, and deterministic verification.

## Execution and Review Protocol

- `W-Scaffold`, `W-Media`, `W-Domain`, `W-Native`, `W-Gate`, `W-App`, and `W-Acceptance` are Worker families; `-A`/`-B`/`-C` suffixes identify distinct parallel Worker instances when shown below.
- `V-Common` validates T001–T042. `V-Release` validates T043–T048. Neither Validator may implement the item it validates.
- `S-Root` supervises all items and may accept the Validator report or return actionable findings.
- A Worker records the focused red command and expected missing-behavior failure, implements only the task scope, records the green command, and submits both results to the assigned Validator.
- A cycle is Worker → Validator → Supervisor. After three unaccepted cycles, work stops and `S-Root` prepares the constitution-required manual-review summary.
- Acceptance for every task includes: its stated `verify` command has the stated result, architecture boundaries remain legal, and no out-of-scope behavior is added.

## Phase 1: Setup (Shared Project Structure)

**Purpose**: Establish reproducible Python 3.12 packaging, layer packages, and test/static-analysis tooling.

- [ ] T001 [P] Owner W-Scaffold; depends on none; add a failing Python-version, package-metadata, and `transcriber-prepare` entry-point test in `tests/unit/test_package_metadata.py` -> verify: `uv run pytest tests/unit/test_package_metadata.py -q` fails only because project metadata/package entry points are absent.
- [ ] T002 [P] Owner W-Scaffold; depends on none; add a failing Python-import/C++-include dependency-direction test for `src/transcriber/{infrastructure,protocol,domain,service,composition,controller}` and the native layer directories in `tests/architecture/test_layer_dependencies.py` -> verify: `uv run pytest tests/architecture/test_layer_dependencies.py -q` fails only because the planned packages/directories are absent.
- [ ] T003 Owner W-Scaffold; depends on T001 and T002; create the Python 3.12 Hatchling metadata in `pyproject.toml`, declare `transcriber-prepare`, add `src/transcriber/{__init__.py,infrastructure/__init__.py,protocol/__init__.py,domain/__init__.py,service/__init__.py,composition/__init__.py,controller/__init__.py}`, and add `native/firered_vad_ncnn/{infrastructure,protocol,service,composition,controller}/.gitkeep` -> verify: `uv run pytest tests/unit/test_package_metadata.py tests/architecture/test_layer_dependencies.py -q` passes.
- [ ] T004 Owner W-Scaffold; depends on T003; pin NumPy for the unchanged upstream FireRedVAD postprocessor plus pytest, mypy, and Ruff development configuration, then produce the reproducible environment lock in `./pyproject.toml` and `./uv.lock` -> verify: `uv sync --group dev`, `uv run python -c "import numpy"`, `uv run mypy --strict src`, and `uv run ruff check src tests` all exit 0.

**Checkpoint**: The package installs, the console entry point resolves, and the empty architecture passes its dependency gate.

---

## Phase 2: Foundational (Blocking Shared Contracts and Test Support)

**Purpose**: Add shared deterministic fixtures, CLI wire entities, and the provider-reported canonical timeline entity needed before story work.

**⚠️ CRITICAL**: No user-story implementation begins until this phase is accepted.

- [ ] T005 [P] Owner W-Scaffold; depends on T004; add deterministic synthetic PCM/WAV builders and fake completed-process/call-log helpers in `tests/support/audio.py`, `tests/support/process.py`, and `tests/support/call_log.py` -> verify: `uv run python -c "from tests.support.audio import make_pcm_wav; from tests.support.process import FakeProcessRunner; from tests.support.call_log import CallLog"` exits 0 without reading network or system tools.
- [ ] T006 Owner W-Domain; depends on T004; write failing Protocol tests for `PrepareCommand`, split-target default/finite/minimum/flooring rules, `PrepareSuccess`, and closed failure-stage labels in `tests/unit/protocol/test_cli.py` -> verify: `uv run pytest tests/unit/protocol/test_cli.py -q` fails only because `src/transcriber/protocol/cli.py` is absent.
- [ ] T007 Owner W-Domain; depends on T006; implement typed Protocol wire entities and validation in `src/transcriber/protocol/cli.py` -> verify: `uv run pytest tests/unit/protocol/test_cli.py tests/architecture -q` passes, including `30.009 -> 3000` frames and rejection of NaN, infinity, and values below `0.01`.
- [ ] T008 [P] Owner W-Domain; depends on T007; write failing pure validation tests for the provider-reported `CanonicalAudio.total_samples` timeline value using controlled primitives in `tests/unit/domain/test_audio.py` -> verify: `uv run pytest tests/unit/domain/test_audio.py -q` fails only because `src/transcriber/domain/audio.py` is unimplemented and never opens an FFmpeg result or supplied fixture.
- [ ] T009 [P] Owner W-Domain; depends on T008; implement the pure `CanonicalAudio.total_samples` timeline invariant in `src/transcriber/domain/audio.py` -> verify: `uv run pytest tests/unit/domain/test_audio.py tests/architecture -q` passes using controlled primitives only.

**Checkpoint**: Shared test data, command/result wire contracts, and the provider-reported canonical timeline type are usable without I/O.

---

## Phase 3: User Story 1 — Validate Media and Extract Canonical Audio (Priority: P1; Implementation Checkpoint)

**Goal**: Validate that a local source contains decodable audio before creating the exact requested directory, then invoke repository-bundled FFmpeg with the configured one-stream canonical extraction arguments.

**Independent Test**: Use controlled process results to prove repository-absolute FFmpeg invocation, exact decode/extraction arguments, decode-before-directory ordering, exclusive path creation, and failure translation. Do not execute assertions against FFmpeg-produced sound parameters or intrinsic properties of `fixtures/sample/prepared.wav`.

### Tests for User Story 1 — write and record RED before implementation

- [ ] T010 [P] [US1] Owner W-Media; depends on T005 and T009; write failing boundary tests for exact argv, `shell=False`, repository-absolute `vendor/ffmpeg`, startup/failure translation, full-decode arguments, and one-stream extraction arguments in `tests/integration/infrastructure/test_ffmpeg.py` -> verify: `uv run pytest tests/integration/infrastructure/test_ffmpeg.py -q` fails only because `process.py` and `ffmpeg.py` are unimplemented; controlled results explicitly cover corrupt, unsupported, and audio-free sources without executing FFmpeg, inspecting extracted sound parameters, validating fixture properties, or selecting among multiple streams.
- [ ] T011 [P] [US1] Owner W-Media; depends on T005 and T009; write failing exclusive task-directory and atomic-file publication tests in `tests/integration/infrastructure/test_filesystem.py` -> verify: `uv run pytest tests/integration/infrastructure/test_filesystem.py -q` fails only because `src/transcriber/infrastructure/filesystem.py` is unimplemented and performs no audio-content assertion.
- [ ] T012 [P] [US1] Owner W-Media; depends on T005 and T009; write the failing controlled media-ingestion boundary journey in `tests/integration/infrastructure/test_media_ingestion_boundary.py`, covering decode-before-create call order, extraction invocation, video exclusion arguments, explicit missing/unreadable source cases, and the corrupt/unsupported/audio-free process outcomes from T010 leaving the requested path absent -> verify: `uv run pytest tests/integration/infrastructure/test_media_ingestion_boundary.py -q` fails on missing first-party adapter behavior, covers all five SC-004 source classes using filesystem/process doubles, and contains no real FFmpeg, fixture-property, or extracted-audio-parameter assertion.
- [ ] T013 [P] [US1] Owner W-App; depends on T009; write a failing non-repository-CWD path-resolution test in `tests/unit/composition/test_application.py` that requires the configured repository-local FFmpeg, model, and provider paths -> verify: `uv run pytest tests/unit/composition/test_application.py -q` fails only because `src/transcriber/composition/application.py` is unimplemented.

### Implementation for User Story 1 — make the focused tests GREEN

- [ ] T014 [P] [US1] Owner W-Media; depends on T010; implement Infrastructure-only process execution and bundled FFmpeg validation/extraction with fixed canonical argv in `src/transcriber/infrastructure/process.py` and `src/transcriber/infrastructure/ffmpeg.py` -> verify: `uv run pytest tests/integration/infrastructure/test_ffmpeg.py -q` passes and captured argv starts with the configured repository-absolute `vendor/ffmpeg` path.
- [ ] T015 [P] [US1] Owner W-Media; depends on T011; implement Infrastructure `WorkDirectory` and `AtomicFileWriter` without Domain imports in `src/transcriber/infrastructure/filesystem.py` -> verify: `uv run pytest tests/integration/infrastructure/test_filesystem.py tests/architecture -q` passes without inspecting audio contents.
- [ ] T016 [US1] Owner W-App; depends on T013, T014, and T015; implement repository-root resolution and concrete media dependency construction without Controller-to-Infrastructure imports in `src/transcriber/composition/application.py` -> verify: `uv run pytest tests/unit/composition/test_application.py tests/architecture -q` passes from both repository and temporary working directories.
- [ ] T017 [US1] Owner W-Media; depends on T012, T014, T015, and T016; execute the unchanged controlled media-ingestion boundary gate and record its red/green command evidence only in `specs/001-local-audio-transcription/evidence/T017-media-ingestion.md` -> verify: `uv run pytest tests/integration/infrastructure/test_media_ingestion_boundary.py tests/integration/infrastructure/test_ffmpeg.py tests/integration/infrastructure/test_filesystem.py -q` passes, negative validation cases leave the task path absent, no test executes FFmpeg or inspects extracted sound/fixture properties, and the task-local evidence file contains the red and green command results.

**Checkpoint**: User Story 1 is independently testable as the media-ingestion kernel. It does not yet publish the final CLI success result because the only supported command runs the complete User Story 2 workflow.

---

## Phase 4: User Story 2 — Create a Speech Manifest and Segment WAV Files (Priority: P2)

**Goal**: Run pinned non-streaming FireRedVAD through NCNN over the complete canonical timeline, invoke the pinned upstream postprocessor unchanged, create exact segment WAVs, atomically publish manifest v1, and expose the complete workflow through the CLI.

**Independent Test**: Black-box adapter tests must prove that the complete probability array and exact pinned settings are passed once to the unchanged upstream FireRedVAD postprocessor and that mocked returned intervals are preserved in order. A required real-provider integration run over `fixtures/sample/prepared.wav` must verify successful dependency invocation, public probability-document coherence, ordered valid intervals, and exact generated WAV/manifest correspondence without asserting an expected FireRedVAD frame count, segment count, probability value/order, or boundary. The required `REFERENCE_DIAGNOSTIC` comparison with `fixtures/sample/manifest.json` is informational and cannot affect test status.

### Protocol and Domain tests — write and record RED before implementation

- [ ] T018 [P] [US2] Owner W-Domain; depends on T009; write failing closed-schema, public constants, reported-count/array-length coherence, finite-range, extra-field, and malformed JSON tests for `FireRedProbabilityDocument` in `tests/unit/protocol/test_probability_codec.py` -> verify: `uv run pytest tests/unit/protocol/test_probability_codec.py -q` fails only because `src/transcriber/protocol/firered_probabilities.py` is unimplemented; no test derives an expected frame count from audio duration or frontend mathematics.
- [ ] T019 [P] [US2] Owner W-Domain; depends on T009; write failing schema-v1 and intrinsic manifest semantic tests—exact fields, indexes, bounds, arithmetic, ordering, safe paths, empty speech, deterministic newline—in `tests/unit/protocol/test_manifest_codec.py` and `tests/contract/test_manifest_contract.py` -> verify: `uv run pytest tests/unit/protocol/test_manifest_codec.py tests/contract/test_manifest_contract.py -q` fails only because `src/transcriber/protocol/manifest.py` is unimplemented.
- [ ] T020 [P] [US2] Owner W-Domain; depends on T009; write failing black-box adapter tests for pinned upstream source loading, exact postprocessor settings, one complete chronological probability input, primitive ordered interval output including a short positive-duration final remainder, and failure translation in `tests/integration/infrastructure/test_firered_postprocessing.py` -> verify: `uv run pytest tests/integration/infrastructure/test_firered_postprocessing.py -q` fails only because the pinned upstream source and `src/transcriber/infrastructure/firered_postprocessing.py` are absent; tests accept mocked FireRedVAD output without reinterpretation and contain no parallel state machine or expected-value implementation of upstream behavior.
- [ ] T021 [P] [US2] Owner W-Domain; depends on T009; write failing middleware-owned frame/sample conversion and final-segment invariant tests for mocked upstream-returned intervals, including preservation of a short positive-duration remainder, timestamp conversion, acceptance of valid intervals unchanged, rejection of out-of-file/zero/overlapping/out-of-order intervals, and permitted over-target duration in `tests/unit/domain/test_segments.py` -> verify: `uv run pytest tests/unit/domain/test_segments.py -q` fails only because `src/transcriber/domain/segments.py` is unimplemented; no assertion reconstructs FireRedVAD's splitting algorithm and no case expects clamping.

### Protocol and Domain implementation

- [ ] T022 [P] [US2] Owner W-Domain; depends on T018; implement the typed closed probability codec in `src/transcriber/protocol/firered_probabilities.py` -> verify: `uv run pytest tests/unit/protocol/test_probability_codec.py tests/architecture -q` passes and rejects NaN, infinity, out-of-range values, count mismatch, and unsupported version.
- [ ] T023 [P] [US2] Owner W-Domain; depends on T019; implement typed manifest entities and deterministic codec with Protocol-only intrinsic validation in `src/transcriber/protocol/manifest.py` -> verify: `uv run pytest tests/unit/protocol/test_manifest_codec.py tests/contract/test_manifest_contract.py tests/architecture -q` passes without Protocol filesystem access.
- [ ] T024 [P] [US2] Owner W-Domain; depends on T020; stage the pinned upstream `vad.py` unchanged and implement only primitive configuration/input/output adaptation in `third_party/firered-vad/fireredvad/vad.py` and `src/transcriber/infrastructure/firered_postprocessing.py` -> verify: `uv run pytest tests/integration/infrastructure/test_firered_postprocessing.py tests/architecture -q` passes, source provenance matches the pinned revision, and no first-party smoothing, threshold, minimum-frame, merge, extension, or split algorithm exists.
- [ ] T025 [P] [US2] Owner W-Domain; depends on T021 and T024; implement pure validation and sample-aligned `FrameInterval`/`FinalSpeechSegment` conversion for already-postprocessed upstream intervals in `src/transcriber/domain/segments.py` -> verify: `uv run pytest tests/unit/domain/test_segments.py tests/integration/infrastructure/test_firered_postprocessing.py tests/architecture -q` passes while preserving ordered valid output and short positive-duration remainders without asserting, modifying, or reinterpreting upstream postprocessor internals.

### Native provider tests and implementation

- [ ] T026 [US2] Owner W-Native; depends on T022; write failing black-box integration tests proving that the build uses the pinned upstream FireRedVAD C++ frontend, the supplied `fixtures/sample/prepared.wav` path is handed to and accepted by the runner without independent fixture inspection, controlled noncanonical WAV is rejected at the first-party boundary, supplied CMVN/NCNN assets load, and ordinary plus over-30,000-frame input each produce one public document whose reported frame count equals its probability-array length in `tests/integration/native/test_firered_runner.py` -> verify: `uv run pytest tests/integration/native/test_firered_runner.py -q` fails only because the runner is absent; no test derives an expected frame count from the audio or asserts chunk boundaries/order, supplied-fixture properties, expected model output, intermediate feature values, segmentation quality, or upstream mathematics.
- [ ] T027 [US2] Owner W-Native; depends on T026; stage the unmodified pinned FireRed frontend sources plus FireRed commit/NCNN tag manifests and license notices in `third_party/firered-vad/{LICENSE,NOTICE.md,manifest.json,runtime-common-frontend/}` and `third_party/ncnn/{LICENSE.txt,manifest.json}` -> verify: recorded file hashes/source revisions match `research.md`, and `rg -n 'curl|wget|git clone' third_party scripts native` finds no runtime/build download step.
- [ ] T028 [US2] Owner W-Native; depends on T027; integrate the pinned upstream frontend through thin first-party WAV/CMVN/NCNN adapters and implement the closed JSON runner across `native/firered_vad_ncnn/{infrastructure,protocol,service,composition,controller}` with `native/firered_vad_ncnn/CMakeLists.txt` -> verify: `uv run pytest tests/integration/native/test_firered_runner.py -q` passes all provenance, canonical-input handoff, supplied-asset, ordinary/long-input reported-count/array-length, schema, and failure-boundary cases without a chunk-order assertion, expected-output oracle, or independent mathematical parity test.
- [ ] T029 [US2] Owner W-Native; depends on T028; write failing Python process-adapter tests for exact absolute argv, `shell=False`, stdout/stderr separation, closed probability decoding handoff, and native failure classification in `tests/integration/infrastructure/test_firered_ncnn.py` -> verify: `uv run pytest tests/integration/infrastructure/test_firered_ncnn.py -q` fails only because `src/transcriber/infrastructure/firered_ncnn.py` is absent.
- [ ] T030 [US2] Owner W-Native; depends on T029; implement Infrastructure `FireRedNcnnProcess` with absolute local model/provider paths and no dependency fallback in `src/transcriber/infrastructure/firered_ncnn.py` -> verify: `uv run pytest tests/integration/infrastructure/test_firered_ncnn.py tests/architecture -q` passes.
- [ ] T031 [US2] Owner W-Native; depends on T028; write failing offline build-wrapper and binary-provenance tests in `tests/integration/native/test_build_firered_runner.py` -> verify: `uv run pytest tests/integration/native/test_build_firered_runner.py -q` fails only because `scripts/build-firered-vad-ncnn-macos.sh` and distribution metadata are absent.
- [ ] T032 [US2] Owner W-Native; depends on T030 and T031; implement the explicit-`NCNN_ROOT`, no-download host build wrapper and distribution metadata in `scripts/build-firered-vad-ncnn-macos.sh` and `native/firered_vad_ncnn/{LICENSE,NOTICE.md}` -> verify: `uv run pytest tests/integration/native tests/integration/infrastructure/test_firered_ncnn.py tests/architecture -q` passes, `file vendor/firered-vad-ncnn` reports a host-runnable executable, and no test reimplements or independently verifies FireRedVAD/NCNN mathematics.

### Required provider gate, segment artifacts, orchestration, and CLI

- [ ] T033 [US2] Owner W-Gate; depends on T024, T025, and T032; register `--real-vad-required` and assemble the non-skippable provider/Domain integration checkpoint from the already-tested components in `tests/conftest.py` and `tests/acceptance/test_sample_workflow.py` without adding production behavior -> verify: `uv run pytest --real-vad-required -m real_vad tests/acceptance/test_sample_workflow.py -q` passes for successful invocation, coherent public output, and valid interval adaptation; controlled missing-prerequisite and malformed-output cases fail at their documented boundary, never on expected FireRedVAD output and never as skipped.
- [ ] T034 [P] [US2] Owner W-Media; depends on T014 and T025; write failing generated-artifact boundary tests for `WaveFileReader`/`WaveSegmentWriter` using synthetic controlled WAV input in `tests/integration/infrastructure/test_wave_files.py` -> verify: `uv run pytest tests/integration/infrastructure/test_wave_files.py -q` fails only because slicing is not implemented; assertions cover requested interval-to-generated-file correspondence and preservation of the controlled source format, and never inspect an FFmpeg result or supplied fixture.
- [ ] T035 [P] [US2] Owner W-App; depends on T023, T025, and T032; write failing parameterized Service call-log tests for the complete stage order, decode-before-create, direct extracted-file handoff to the native runner, primitive Protocol/Domain mapping, in-memory manifest-before-slices, publication-after-generated-artifact verification, every terminal failure suffix and resource/operation detail, no-speech behavior, and artifact correspondence in `tests/unit/service/test_prepare_media.py` -> verify: `uv run pytest tests/unit/service/test_prepare_media.py -q` fails only because `src/transcriber/service/prepare_media.py` is unimplemented and contains no separate FFmpeg-output parameter-check stage.
- [ ] T036 [P] [US2] Owner W-App; depends on T007; write failing parser/render/status/non-repository-CWD CLI contract tests, including bounded stage-specific failure details with no raw traceback, in `tests/unit/controller/test_cli.py` and `tests/contract/test_cli_contract.py` -> verify: `uv run pytest tests/unit/controller/test_cli.py tests/contract/test_cli_contract.py -q` fails only because Controller and complete Composition are unimplemented.
- [ ] T037 [P] [US2] Owner W-Acceptance; depends on T033, T034, T035, and T036; complete the initially failing end-to-end boundary assertions for exact CLI output shape, schema-valid ordered intervals, generated manifest/WAV correspondence, no network, correct stage failures, and one compact `REFERENCE_DIAGNOSTIC={...}` line in `tests/acceptance/test_sample_workflow.py`; use controlled manifests to verify same-index pairing through the shorter list, ascending indexes, `actual - reference` boundary deltas, and an empty pair array when either list is empty -> verify: the single required real-provider integration run fails because the complete CLI workflow is still incomplete; it asserts only one diagnostic line matching the defined JSON shape rather than expected numeric values, and does not independently validate supplied fixtures, expected FireRedVAD output, or FFmpeg-produced sound parameters.
- [ ] T038 [P] [US2] Owner W-Media; depends on T034; implement primitive-offset `WaveFileReader`/`WaveSegmentWriter` slicing and generated-segment `WaveMetadata` correspondence in `src/transcriber/infrastructure/wave_files.py` -> verify: `uv run pytest tests/integration/infrastructure/test_wave_files.py tests/architecture -q` passes against synthetic controlled input without inspecting an FFmpeg result or supplied fixture.
- [ ] T039 [US2] Owner W-App; depends on T023, T025, T032, T035, and T038; implement the typed `PreparationStage` lifecycle and `PrepareMedia` use case in `src/transcriber/service/prepare_media.py` -> verify: `uv run pytest tests/unit/service/test_prepare_media.py tests/architecture -q` passes, every injected failure stops the later call-log suffix, and no incomplete manifest is published.
- [ ] T040 [US2] Owner W-App; depends on T016, T037, and T039; complete concrete offline application assembly for FFmpeg, model assets, native provider, WAV/filesystem adapters, Domain processing, and manifest codec in `src/transcriber/composition/application.py` -> verify: `uv run pytest tests/unit/composition/test_application.py tests/unit/service/test_prepare_media.py tests/architecture -q` passes from a non-repository CWD, then `uv run pytest --real-vad-required -m real_vad tests/acceptance/test_sample_workflow.py -q` fails only on the still-unimplemented Controller behavior.
- [ ] T041 [US2] Owner W-App; depends on T036 and T040; implement Controller parsing, four-line success output, bounded stage-specific errors, and statuses 0/1/2 in `src/transcriber/controller/cli.py` and `src/transcriber/controller/__main__.py` -> verify: `uv run pytest tests/unit/controller/test_cli.py tests/contract/test_cli_contract.py tests/acceptance/test_sample_workflow.py tests/architecture -q` passes with Controller importing only Composition and Protocol.
- [ ] T042 [US2] Owner W-Gate; depends on T033, T037, T038, T039, T040, and T041; execute the unchanged fixture-backed integration workflow and record its red/green command evidence only in `specs/001-local-audio-transcription/evidence/T042-real-provider.md` without changing or independently validating the supplied fixtures -> verify: one `uv run pytest --real-vad-required -m real_vad tests/acceptance/test_sample_workflow.py -q -s` integration run passes with successful dependency invocation, coherent public probability output, ordered valid segments, and generated WAV/manifest correspondence without an expected model-output, reference-boundary, or FFmpeg-output assertion; exactly one defined `REFERENCE_DIAGNOSTIC` line appears and its numeric differences do not affect status, and the task-local evidence file contains the red and green command results.

**Checkpoint**: User Stories 1 and 2 work together through the only supported CLI; integration-boundary checks and the mandatory real fixture both pass without independently testing upstream mathematics.

---

## Phase 5: Polish and Cross-Cutting Release Verification

**Purpose**: Align documentation/licensing, prove all success criteria, and close architecture/scope review without adding behavior.

- [ ] T043 [P] Owner W-Acceptance; depends on T042; align fixture guidance with the FireRedVAD advisory-target behavior, mark the sample manifest as diagnostic-only, and document only the supported CLI workflow in `fixtures/sample/README.md` and `README.md` -> verify: all segmentation claims and documented commands match `spec.md` and `quickstart.md`, no reference count or boundary is described as an acceptance oracle, and no other VAD or runtime dependency is added.
- [ ] T044 [P] Owner W-Native; depends on T042; complete the separately-executed provider distribution and license/notice review in `native/firered_vad_ncnn/NOTICE.md`, `third_party/firered-vad/NOTICE.md`, and `third_party/ncnn/manifest.json` -> verify: every copied source and linked binary dependency has a recorded origin, revision, license, and distribution notice, with no claim that the review changes the repository's existing license.
- [ ] T045 Owner W-Acceptance; depends on T042; run the complete deterministic quality suite and record its command/status evidence only in `specs/001-local-audio-transcription/evidence/T045-quality-suite.md` without changing behavior -> verify: `uv run pytest -m "not real_vad"`, `uv run mypy --strict src`, and `uv run ruff check src tests` all exit 0 with no skipped required non-real test, and the task-local evidence file records each command and status.
- [ ] T046 Owner W-Acceptance; depends on T043, T044, and T045; execute every applicable command in `specs/001-local-audio-transcription/quickstart.md`, including the required real-provider command and manual CLI artifact inventory -> verify: commands produce the documented four stdout lines, `prepared.wav`, `manifest.json`, the reported non-negative number of segment files, the same number of corresponding manifest records, exact generated segment durations, exactly one defined `REFERENCE_DIAGNOSTIC` line, and no network access; diagnostic values are visibly non-gating, and inspection does not assert expected FireRedVAD output, FFmpeg-produced sound parameters, or supplied-fixture properties.
- [ ] T047 Owner W-Acceptance; depends on T046; perform final FR-001–FR-035 and SC-001–SC-006 evidence, architecture, TDD-record, simplicity, non-goal, and workspace-diff review against `specs/001-local-audio-transcription/plan.md` and record it only in `specs/001-local-audio-transcription/evidence/T047-release-review.md` -> verify: every requirement links to a passing command/task, `uv run pytest tests/architecture -q` exits 0, no acceptance check asserts third-party semantic output, no unapproved file/capability appears, the task-local review record is complete, and V-Release reports ACCEPTED to S-Root.
- [ ] T048 Owner W-Acceptance; depends on T017, T042, T045, and T047; aggregate the completed task-local evidence records without altering their contents into `specs/001-local-audio-transcription/implementation-evidence.md` -> verify: the aggregation links `evidence/T017-media-ingestion.md`, `evidence/T042-real-provider.md`, `evidence/T045-quality-suite.md`, and `evidence/T047-release-review.md`, maps FR-001–FR-035 and SC-001–SC-006 to accepted evidence, and contains no unreferenced or missing evidence-producing task.

---

## Dependencies and Execution Order

### Phase dependencies

- **Phase 1 — Setup**: Starts immediately. T001 and T002 run in parallel; T003 then T004 serialize shared metadata changes.
- **Phase 2 — Foundational**: T005 and T006 may start after T004; T007–T009 complete the shared contracts and block both stories.
- **Phase 3 — User Story 1**: Depends on T005–T009. Its tests T010–T013 can run concurrently; implementations T014–T016 follow their corresponding red tests; T017 is the story gate.
- **Phase 4 — User Story 2**: T018–T033 may begin after Foundation and run in parallel with US1 according to their individual dependencies. T034 and later integration work follow their explicit US1/US2 prerequisites. Each implementation follows its corresponding red test: T034 → T038, T035 → T039, T037 plus T039 → T040, and T036 plus T040 → T041. T042 is the story gate.
- **Phase 5 — Polish**: Depends on T042. Documentation and notice work T043–T044 may run concurrently; T045–T048 close sequentially.

### User-story dependency graph

```text
Setup T001–T004
        │
Foundation T005–T009
        ├── US1 Media Ingestion T010–T017 ─────────────┐
        └── US2 Provider/Domain T018–T033 ─────────────┤
                                                       └── US2 Integration + Complete CLI T034–T042
                                                                                  │
                                                       Release Verification T043–T048
```

- **US1 (P1)**: Begins after Foundation and is independently verified at T017.
- **US2 (P2)**: Provider/Domain tasks T018–T033 can proceed independently after Foundation; artifact and complete-CLI integration reuse the accepted US1 media/filesystem infrastructure.

### Entity and layer ownership

| Layer | Entities/files | First story |
|---|---|---|
| Infrastructure | `CompletedProcessData`, `WaveMetadata`, `FfmpegProcess`, `WorkDirectory`, `WaveFileReader`, `WaveSegmentWriter`, `AtomicFileWriter`, `FireRedNcnnProcess`, `FireRedPostprocessor` adapter | US1, extended by US2 |
| Protocol/Wire | `PrepareCommand`, `PrepareSuccess`, `PrepareFailure`, `FireRedProbabilityDocument`, `SegmentManifest` | Foundation, extended by US2 |
| Domain/Model | `CanonicalAudio`, `VadSettings`, `VadFrameProbability`, `FrameInterval`, `FinalSpeechSegment`; no postprocessing algorithm | Foundation, extended by US2 |
| Service | `PreparationStage`, `PrepareMedia` | US2 |
| Composition | `Application`, `build_application` | US1 path resolution, completed by US2 |
| Controller | parser and `main` | US2 |
| Native layers | trusted upstream frontend adapter/WAV/NCNN Infrastructure; command/JSON Protocol; inference Service; application Composition; `main` Controller | US2 |

## Parallel Execution Examples

### User Story 1

```text
Worker W-Media-A: T010 → T014
Worker W-Media-B: T011 → T015
Worker W-App-A: T013 → T016
After one slot frees, Worker W-Media-C completes T012/T017
```

The separate chains touch different production/test files. The acceptance gate is serialized after all dependencies.

### User Story 2

```text
Worker W-Domain-A: T018 → T022
Worker W-Domain-B: T019 → T023
Worker W-Domain-C: T020 → T024 → T025 (after T021), integrating the unchanged upstream postprocessor rather than recreating it
Then Worker W-Native: T026 → T027 → T028 → (T029 → T030 || T031) → T032
Then Worker W-Gate: T033
Then in parallel: W-Media T034 → T038; W-App T035/T036 → T039; W-Acceptance T037
After T037 and T039: W-App T040 → T041
Finally Worker W-Gate: T042
```

No Validator implements an item it validates, and `S-Root` remains the distinct Supervisor.

## Implementation Strategy

### Implementation checkpoint — User Story 1

1. Complete Setup and Foundation.
2. Write all US1 tests and record the expected red failures.
3. Implement only the media/file/audio entities needed to make those tests green.
4. Validate the ingestion kernel independently at T017; this checkpoint is not a delivered CLI MVP and does not block already-independent T018–T033 work.

### Delivery MVP — User Stories 1 and 2

The minimum deliverable is the complete CLI through T042: media ingestion from US1 plus FireRedVAD integration, manifest creation, and segment WAV creation from US2.

### Incremental delivery

1. **US1**: trusted canonical `prepared.wav` from supported media.
2. **US2 Domain/Protocol**: unchanged upstream postprocessor integration plus middleware-owned interval, segment, and manifest contracts.
3. **US2 Native gate**: pinned real FireRed/NCNN results before application orchestration.
4. **US2 complete CLI**: artifacts, errors, publication, and one required fixture-backed integration run limited to project-owned boundary behavior.
5. **Release**: documentation, licensing, per-task static/test evidence, final independent validation, and evidence aggregation.

## Notes

- `[P]` never overrides a stated dependency; it means safe concurrency only after that dependency is accepted.
- The historical `--max-segment-duration-seconds` name denotes an advisory FireRed split target. Tests must accept authoritative segments longer than the target.
- No task authorizes Qwen-ASR execution, llama.cpp invocation, model/runtime downloads, diarization, GUI/API workers, streaming, or alternate FFmpeg selection.
- The real-provider gate is non-skippable in required mode. Missing dependencies or invalid project-owned boundary behavior fails the gate; sample-reference differences are diagnostic-only and never trigger fixture mutation or output correction.
