# Tasks: Normalized Token JSON

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, and `contracts/` in `specs/003-normalized-token-json/`.

**Tests**: Required by the project constitution and AGENTS.md. Add behavior tests before changing the corresponding production code. Tests verify project-owned behavior with controlled provider responses; they do not judge ASR accuracy or ICU correctness.

**Format**: Every checkbox gives an action, exact file path, dependencies, and a deterministic acceptance check. `[P]` means the task can run alongside other ready tasks that touch different files. `[US1]` and `[US2]` map to the two specification stories.

## Assumptions, ownership, and architecture

- Provider-exposed Unicode token strings, IDs, and log probabilities are authoritative. Final assistant content and raw bytes are outside transcript reconstruction. Qwen's initial language prefix is discarded; later language-looking text is literal. No language result field is published.
- A successful response with an absent or empty whole `logprobs.content` list is an empty segment. A malformed present list or token, and abnormal completion, fail. Existing requested-language input, lifecycle, timeouts, status, and offline behavior remain in force.
- Every Speech Segment is normalized synchronously and independently. No thread, queue, inserted separator, trimming, language detection, or parallel plain-text artifact is added. Existing `transcript.txt` files are not migrated or updated.
- Protocol owns Qwen request and response codecs; Infrastructure owns provider-neutral Recognition Token/Result, llama.cpp session, and atomic publication; Domain owns Normalization Span, Transcript, scores, context, and JSON bytes; Service owns segment order, progress, and cleanup; Composition maps Protocol tokens to Infrastructure tokens. Controller only reports the returned artifact path.
- The root agent is Orchestrator. For task `Tnnn`, assign a fresh Worker `Wnnn` (`gpt-5.6-terra`, `low`) and fresh Validator `Vnnn` (`gpt-5.6-sol`, `low`); the Validator reviews that Worker's code and checks against the specification, plan, tests, architecture, and scope. Keep each pair through revisions, with at most three Worker → Validator → Orchestrator cycles as required by the constitution. Parallel Workers must own disjoint files; sequence shared-file work. A task's implementation is accepted only after its Validator reports verification evidence and the Orchestrator accepts it.
- PyICU 2.16.2 may need native ICU headers and C++ build tools. The dependency gate must pass before Domain work. The real-provider checkpoint requires model assets for SC-006 and remains incomplete until they are available; controlled tests are also mandatory.

## Phase 1: Setup

**Goal**: Make the specified ICU API available from the locked environment.

- [X] T001 Pin PyICU 2.16.2 in `pyproject.toml` and resolve `uv.lock` (deps: none) -> verify: `uv lock --check` and `uv run python -c 'import icu; print(icu.VERSION, icu.ICU_VERSION)'` both succeed; if native build prerequisites are missing, provision them and rerun before marking T001 complete.

## Phase 2: Foundational provider result contract

**Goal**: Establish the shared typed result used by both user stories.

- [X] T002 Write provider-neutral token/result tests in `tests/unit/infrastructure/test_execution_provider.py` (deps: T001) -> verify: tests describe original non-null token ID, Unicode text, valid log probability including negative infinity, ordered tokens, and empty success before production changes.
- [X] T003 Replace text-only `RecognitionResult` with typed ordered Recognition Tokens in `src/transcriber/infrastructure/execution_provider.py` (deps: T002) -> verify: `uv run pytest tests/unit/infrastructure/test_execution_provider.py -q` passes and lifecycle behavior is unchanged.
- [X] T004 Update controlled token-result builders in `tests/support/asr.py` (deps: T003) -> verify: existing controlled sessions can return ordered token tuples and exceptions without changing provider call order.

**Checkpoint**: The provider-neutral result can represent zero or more scored Unicode tokens without a language value.

## Phase 3: User Story 1 — Consume normalized text with confidence (P1)

**Goal**: Publish ordered two-field NFKC spans with probabilities and derive subsequent segment context from their normalized text.

**Independent Test**: Use controlled tokens `e` at `ln(0.9)` and combining acute plus `.` at `ln(0.7)`; verify exact `é`/`.` JSON entries scored `0.7`, their concatenation, one progress event per segment, and an absolute `transcript.json` success path. Verify an empty success writes exactly `{"text":[]}\n`.

### Tests first

- [X] T005 [P] [US1] Write Domain span, score, context, and exact JSON tests in `tests/unit/domain/test_transcript.py` (deps: T001, T003) -> verify: cases cover ICU boundary-before, cross-token composition, one-token/multiple-span provenance, compatibility expansion, Hangul Jamo, halfwidth Katakana, whitespace, empty normalized output, per-segment flush, and two-field compact UTF-8 bytes against the installed ICU oracle.
- [X] T006 [P] [US1] Write Qwen request and successful-result tests in `tests/unit/protocol/test_qwen_asr.py` (deps: T003) -> verify: tests cover `logprobs:true`, `top_logprobs:1`, ordered `id`/`token`/`logprob`, initial `language VALUE<asr_text>` removal including `None`, mixed control/text tokens retaining ID and score, literal later marker, empty whole probability list, and final-content divergence.
- [X] T007 [P] [US1] Write llama.cpp callable-boundary tests in `tests/integration/infrastructure/test_llama_cpp.py` (deps: T003) -> verify: request encoding receives a `RecognitionRequest`, a controlled HTTP response decoder returns ordered provider-neutral tokens, and request timeout, loopback transport, process lifecycle, and bounded diagnostics remain as before.
- [X] T008 [P] [US1] Write publication-path and atomic-byte tests in `tests/integration/infrastructure/test_asr_task_files.py` (deps: T003) -> verify: `publish_transcript` returns the absolute `transcript.json` path, writes exact supplied bytes atomically, and does not update `transcript.txt`.

### Implementation

- [X] T009 [P] [US1] Implement the pending Normalization Span and Structured Transcript in `src/transcriber/domain/transcript.py` (deps: T005) -> verify: Domain tests pass; each segment flushes separately; `hasBoundaryBefore` determines spans; every contributing token supplies its log probability; JSON has only ordered `text` and `probability` members; context uses concatenated normalized text and existing 2,048-code-point/leading-fragment rules. T024 adds the span byte limit after T020 tests it.
- [X] T010 [P] [US1] Decode successful Qwen token records and strip only the initial provider prefix in `src/transcriber/protocol/qwen_asr.py` (deps: T006) -> verify: Protocol tests pass; Unicode `token` strings are authoritative; mixed metadata/text preserves original ID and score; final assistant content is neither reconstructed nor compared.
- [X] T011 [P] [US1] Change the atomic Transcript destination to `transcript.json` in `src/transcriber/infrastructure/asr_files.py` (deps: T008) -> verify: focused file-publication tests pass, including exact bytes and existing `transcript.txt` preservation.
- [X] T012 [US1] Use typed request/result callables in `src/transcriber/infrastructure/llama_cpp.py` (deps: T007, T010) -> verify: `uv run pytest tests/integration/infrastructure/test_llama_cpp.py -q` passes; remove Infrastructure's `QwenRequestEncoder` and `QwenResponseDecoder` interfaces, accept `Callable[[RecognitionRequest], bytes]` and `Callable[[bytes], RecognitionResult]`, and keep nonstreaming lifecycle and timeout behavior unchanged without importing Protocol.
- [X] T013 [P] [US1] Write Composition codec-wrapper tests in `tests/unit/composition/test_asr_application.py` (deps: T010, T012) -> verify: the request wrapper passes audio path, context, and requested language to the Qwen Protocol encoder; the response wrapper maps ordered Protocol token values to Infrastructure result values without an Infrastructure → Protocol import.
- [X] T014 [P] [US1] Write segment orchestration tests in `tests/unit/service/test_recognize_segments.py` (deps: T004, T009, T012) -> verify: controlled 1/100 segment cases assert independent normalization, manifest order, no separators or trimming, normalized context, one progress event per segment, publication after provider cleanup, and exact empty JSON.
- [X] T015 [US1] Wire Qwen request and response wrappers in `src/transcriber/composition/application.py` (deps: T013) -> verify: `uv run pytest tests/unit/composition/test_asr_application.py tests/architecture/test_layer_dependencies.py -q` passes; Composition maps Protocol token values into provider-neutral Recognition Tokens and keeps requested-language input unchanged.
- [X] T016 [US1] Consume each token result synchronously and publish Structured Transcript bytes in `src/transcriber/service/recognize_segments.py` (deps: T009, T011, T012, T014, T015) -> verify: focused Service tests pass and no token queue, normalization thread, segment separator, or per-token progress is introduced.
- [X] T017 [P] [US1] Update public artifact-path assertions in `tests/contract/test_asr_cli_contract.py`, `tests/unit/controller/test_asr_cli.py`, and `tests/unit/protocol/test_asr_cli.py` (deps: T016) -> verify: these tests report `transcript.json` through the existing success field without changing command grammar or status codes.
- [X] T018 [US1] Write successful workflow contract and acceptance cases in `tests/acceptance/test_asr_workflow.py` (deps: T016, T017) -> verify: controlled 1/100 segment runs and empty result prove FR-001–FR-008, FR-012–FR-015, FR-017, FR-019, FR-020, FR-022, FR-023 and SC-001–SC-003/SC-005, plus the successful-prefix and absent-list cases of FR-011/FR-025; all entries have exactly `text` and `probability`.

**Checkpoint**: User Story 1 independently demonstrates the successful JSON path with controlled provider responses. Do not treat this checkpoint as a releasable result until User Story 2 rejects malformed or partial responses.

## Phase 4: User Story 2 — Reject incomplete or misleading results (P2)

**Goal**: Reject malformed or partial provider output and oversized source spans while preserving a previous complete JSON Transcript.

**Independent Test**: Seed an existing `transcript.json`; run controlled malformed-token, abnormal-completion, span-overflow, provider-failure, and cancellation cases; verify non-success, unchanged prior bytes, and no attempt-created temporary Transcript file.

### Tests first

- [X] T019 [P] [US2] Add Qwen response validation matrix in `tests/unit/protocol/test_qwen_asr.py` (deps: T018) -> verify: tests distinguish absent/empty whole `logprobs.content` from a present non-array or malformed item; reject missing ID/text/logprob, booleans, positive/NaN/infinite-positive scores, empty-value or marker-only initial metadata, and missing/length/tool/error completion; retain a language-looking string without a complete initial prefix literally; accept negative infinity and zero.
- [X] T020 [P] [US2] Add 16,384-byte pending-span limit tests in `tests/unit/domain/test_transcript.py` (deps: T018) -> verify: an exactly bounded source span succeeds and the next non-boundary code point fails without text alteration; a guaranteed boundary permits a fresh span.
- [X] T021 [P] [US2] Add provider failure-mapping tests in `tests/integration/infrastructure/test_llama_cpp.py` (deps: T018) -> verify: malformed decoder results become bounded provider-response failures while existing startup, request, and cleanup failures retain their stages and deadlines.
- [X] T022 [P] [US2] Add preservation and cleanup tests in `tests/unit/service/test_recognize_segments.py` (deps: T018) -> verify: provider error, abnormal result, overflow, cancellation, progress callback failure, and cleanup failure never publish and leave a prior complete artifact unchanged.

### Implementation

- [X] T023 [P] [US2] Enforce explicit successful Qwen completion and strict present-token field validation in `src/transcriber/protocol/qwen_asr.py` (deps: T019) -> verify: focused Protocol tests pass; a missing whole list after `finish_reason="stop"` is empty success, but a malformed present list or token fails at the provider-response boundary.
- [X] T024 [P] [US2] Enforce the UTF-8 source-span limit in `src/transcriber/domain/transcript.py` (deps: T020) -> verify: focused Domain tests pass with no inserted or removed code point and no span across a segment boundary.
- [X] T025 [P] [US2] Preserve provider-response error translation in `src/transcriber/infrastructure/llama_cpp.py` (deps: T021, T023) -> verify: focused llama.cpp tests pass with a bounded public failure and no partial Recognition Result.
- [X] T026 [US2] Ensure failed normalization or cancellation bypasses publication in `src/transcriber/service/recognize_segments.py` (deps: T022, T024, T025) -> verify: focused Service tests pass and provider cleanup still occurs before return.
- [X] T027 [US2] Add controlled failure-matrix acceptance cases in `tests/acceptance/test_asr_workflow.py` (deps: T023–T026) -> verify: the malformed-prefix and malformed-present-list cases complete FR-011/FR-025 coverage; FR-009, FR-010, FR-016, FR-018, FR-021 and SC-004 pass with byte-for-byte prior-artifact preservation and no `.transcript.json.*.tmp` files.

**Checkpoint — MVP**: Both stories work with controlled provider responses; a failed task never replaces a complete JSON artifact. Complete the SC-006 real-provider checkpoint and final gates before feature acceptance.

## Phase 5: Polish and cross-cutting verification

- [X] T028 [P] Update artifact documentation in `docs/cli.md` and `README.md` (deps: T018) -> verify: examples show `transcript.json`, the two-field JSON shape, and no new CLI flag or parallel `transcript.txt` output.
- [X] T029 Update and execute the real-provider checkpoint in `tests/acceptance/test_asr_workflow.py` (deps: T027) -> verify: `uv run pytest tests/acceptance/test_asr_workflow.py -m real_asr -q` passes with a collected, non-skipped real-provider test using provisioned local model prerequisites; the checkpoint proves exposed IDs, Unicode token strings, log probabilities, explicit completion, and token-derived artifact reconstruction without asserting assistant-content equality or ASR accuracy.
- [X] T030 Run the controlled quickstart and regression gates in `specs/003-normalized-token-json/quickstart.md` (deps: T027, T028, T029) -> verify: `uv run pytest -m 'not real_asr' -q`, `uv run ruff check .`, `uv run mypy src`, `uv run pytest tests/architecture/test_layer_dependencies.py -q`, and `uv lock --check` pass; review the diff against FR-001–FR-025, SC-001–SC-006, and the stated non-goals.

## Dependencies and execution order

```text
T001 → T002 → T003 → T004
                 ├→ T005 → T009 ───────────────┐
                 ├→ T006 → T010 → T012 ────────┤
                 ├→ T007 ────────→ T012         ├→ T014 → T016 → T018
                 └→ T008 → T011 ────────────────┤         ↑
                                    T013 → T015 ┘         T017
T018 → (T019 → T023, T020 → T024, T021 → T025, T022) → T026 → T027
T018 → T028; T027 → T029; T027 + T028 + T029 → T030
```

The task-level `deps` clauses are authoritative where the compact graph omits an edge. Setup blocks Foundation; Foundation blocks both stories. US2 deliberately follows the US1 baseline because it strengthens the same Protocol, Domain, Infrastructure, Service, and acceptance files. Polish follows the relevant story tasks. Tests precede each production change; after any refactor, rerun the same focused tests.

## Parallel execution examples

- **US1 test writers**: Assign T005, T006, T007, and T008 to separate fresh Worker/Validator pairs after T003; all touch different test files. Assign T009, T010, and T011 after their respective tests; their production files are disjoint. T012 waits for T010; T013 and T014 then use separate test files.
- **US2 test writers**: Assign T019, T020, T021, and T022 to separate fresh pairs after T018; each owns a different test file. T023 and T024 can proceed in parallel after their tests. T025 waits for T023; T026 waits for T024 and T025.
- For each task, the named Validator independently checks acceptance criteria and sends evidence to the Orchestrator. Do not assign two active Workers to the same file, including the acceptance file shared by T018, T027, and T029.

## Implementation strategy

1. Complete Setup and Foundation, then US1 test tasks and their matching implementation tasks. Validate the US1 successful-path checkpoint with controlled responses.
2. Add US2 failure tests before tightening the corresponding production paths. Validate preservation and cleanup independently; US1 and US2 together form the MVP.
3. Update documentation, complete the real-provider checkpoint, then run the controlled full suite, type checks, lint, architecture gate, and lock check.
