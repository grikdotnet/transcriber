# Implement Qwen language mappings for supported language tags

## Status

Open

## Feature

`002-segment-asr`

## Problem

Feature 002 accepts `auto` or a syntactically valid language tag at the public CLI boundary.
The Qwen execution-provider contract promises to translate common BCP 47 primary subtags into
Qwen's canonical language labels before encoding an explicit-language recognition request.

`encode_qwen_request()` currently accepts only `auto` and `en-GB`. Other valid values pass public
CLI validation and fail later while encoding the first Speech Segment. Examples include `en`,
`nl`, and `pt-BR`.

The late failure violates the provider contract and makes public language handling depend on an
undocumented adapter restriction.

The initial Task 3 implementation also tested an artificial failure path: the controller test
replaced the Application with a test double that raised `QwenUnsupportedLanguageError` directly.
In the shipped path, the llama.cpp Execution Provider converts that Protocol error to
`ExecutionProviderFailure`, and `RecognizeSegments` returns a segment-specific `AsrFailure` for
the controller to render. The direct controller exception branch is therefore unreachable and
does not prove the `segment=0` diagnostic required by FR-018.

## Authoritative requirements

- `specs/002-segment-asr/spec.md` FR-002 defines the accepted language-tag grammar.
- `specs/002-segment-asr/spec.md` FR-011 defines `auto` behavior for optional and required ASR
  Models.
- `specs/002-segment-asr/spec.md` FR-012 excludes model-to-language matching and a public
  model-specific language catalog.
- `specs/002-segment-asr/contracts/execution-provider.md` requires common BCP 47 primary subtags
  to be translated internally to Qwen canonical language labels.

## Intended behavior

1. `auto` continues to omit the assistant language continuation.
2. An explicit language tag is parsed by taking its ASCII case-insensitive primary subtag.
3. A supported primary subtag is translated to the exact Qwen canonical label and encoded as
   `language {ProviderLanguage}<asr_text>`.
4. Region and variant subtags do not change the mapping. For example, `en`, `en-GB`, and `en-US`
   map to `English`; `pt` and `pt-BR` map to `Portuguese`.
5. A syntactically valid tag with an unsupported primary subtag fails at the Qwen protocol
   boundary with a deterministic, actionable error before an HTTP request is sent.
6. The llama.cpp Execution Provider translates that error to its provider failure contract;
   `RecognizeSegments` attaches the active Speech Segment index; and the controller renders the
   returned `AsrFailure` as one bounded `execution-provider` diagnostic.
7. The controller does not import or catch `QwenUnsupportedLanguageError`.
8. The mapping remains an internal provider wire concern. The CLI, ASR Model Manifest, and public
   model-selection behavior do not gain a supported-language catalog.

## Supported mappings

The initial mapping follows Qwen3-ASR's documented canonical language list:

| Primary subtag | Qwen label | Primary subtag | Qwen label |
| --- | --- | --- | --- |
| `zh` | `Chinese` | `en` | `English` |
| `yue` | `Cantonese` | `ar` | `Arabic` |
| `de` | `German` | `fr` | `French` |
| `es` | `Spanish` | `pt` | `Portuguese` |
| `id` | `Indonesian` | `it` | `Italian` |
| `ko` | `Korean` | `ru` | `Russian` |
| `th` | `Thai` | `vi` | `Vietnamese` |
| `ja` | `Japanese` | `tr` | `Turkish` |
| `hi` | `Hindi` | `ms` | `Malay` |
| `nl` | `Dutch` | `sv` | `Swedish` |
| `da` | `Danish` | `fi` | `Finnish` |
| `pl` | `Polish` | `cs` | `Czech` |
| `fil` | `Filipino` | `fa` | `Persian` |
| `el` | `Greek` | `ro` | `Romanian` |
| `hu` | `Hungarian` | `mk` | `Macedonian` |

Source: [QwenLM/Qwen3-ASR supported-language definitions](https://github.com/QwenLM/Qwen3-ASR/blob/main/qwen_asr/inference/utils.py).

## Domain entities, layers, and relationships

- **Language tag**: public CLI value validated by the existing protocol parser.
- **Provider language**: Qwen-specific canonical label used only on the provider wire.
- **Recognition request**: provider request containing Recognition Context, Speech Segment
  reference, and the optional provider-language continuation.
- **Protocol layer**: `transcriber.protocol.qwen_asr` owns primary-subtag extraction, mapping, and
  deterministic request encoding.
- **Service layer**: `RecognizeSegments` continues to pass the selected language unchanged and
  remains provider-independent.
- **Controller layer**: the ASR CLI continues to validate grammar and render protocol failures; it
  does not own Qwen mappings.

Relationship: the controller supplies a validated language tag to the ASR Task; the service passes
the language tag to the Execution Provider; the Qwen protocol adapter translates the primary
subtag into a provider language while encoding each recognition request.

## Affected files and components

- `src/transcriber/protocol/qwen_asr.py`: Qwen primary-subtag translation, provider request
  encoding, and the public protocol error for an unmapped primary subtag.
- `src/transcriber/infrastructure/llama_cpp.py`: only if the existing Execution Provider boundary
  does not already prevent transport after request-encoding failure.
- `src/transcriber/controller/asr_cli.py`: remove the Qwen-specific import and unreachable
  exception branch; render only the application-owned result.
- `tests/unit/protocol/test_qwen_asr.py`: exact request-encoding and unsupported-language tests.
- `tests/integration/infrastructure/test_llama_cpp.py`: controlled Execution Provider boundary
  tests.
- `tests/unit/controller/test_asr_cli.py`: remove the test that directly raises the Qwen Protocol
  error from a replacement Application.
- `tests/acceptance/test_asr_workflow.py`: controlled public CLI test through the real
  Application, Service, and llama.cpp Execution Provider adapter.
- `specs/002-segment-asr/evidence/`: truthful red/green and final verification records.

No Domain entity, ASR Model Manifest schema, service interface, or public CLI grammar is changed.

## Architecture classifications

- **Primary-subtag translator**: Protocol-layer standalone function; converts a public language
  tag into a Qwen provider-wire label and has no filesystem, process, HTTP, or CLI responsibility.
- **Unsupported Qwen language error**: Protocol-layer typed error; represents failure to encode a
  syntactically valid public value for this Execution Provider.
- **Qwen request encoder**: Existing Protocol-layer function; remains the public test seam and owns
  deterministic wire bytes.
- **Execution Provider failure propagation**: Infrastructure-layer behavior; prevents an HTTP
  recognition request when protocol encoding fails and does not reinterpret the language tag.
- **ASR failure mapping**: Service-layer behavior; converts the Execution Provider failure into a
  segment-specific `AsrFailure`.
- **CLI error rendering**: Controller-layer behavior; renders the application-owned `AsrFailure`
  through the existing bounded public diagnostic without depending on Qwen-specific errors.

The design keeps one responsibility per entity: Protocol translates and encodes, Infrastructure
transports, Service maps failures, and Controller renders. No new interface or extension point is
authorized.

## Assumptions

- Qwen's canonical labels and documented 30-language set are stable for the shipped
  `qwen3-asr-1.7b` integration.
- Public language-tag validation remains syntax-only, as required by FR-012.
- Primary subtags are compared case-insensitively even though the existing CLI may normalize or
  preserve the caller's spelling.
- Dialect names without distinct BCP 47 primary subtags are outside this issue.
- No ASR Model Manifest schema change is required.
- No model-selection, download, GUI, or public catalog behavior is added.

## Explicit non-goals

- Publishing supported languages through the CLI or ASR Model Manifest.
- Matching an ASR Model to a requested language.
- Adding another ASR Model or Execution Provider.
- Recognizing Qwen dialect names that do not have a documented primary-subtag mapping.
- Testing Qwen's recognition quality, language accuracy, or other third-party semantics.
- Refactoring unrelated request, response, service, or CLI code.
- Adding configuration, user-editable mappings, plugin mechanisms, or speculative provider
  abstractions.

## Test seams

Tests exercise behavior only through existing public project interfaces:

- **Qwen protocol seam:** `encode_qwen_request()` observes exact provider request bytes without
  testing a private translation helper.
- **Execution Provider seam:** the controlled Qwen/llama.cpp adapter observes the request sent to
  the external provider boundary without making a real network request.
- **CLI seam:** `transcriber-asr` observes exit status and bounded stderr output.

Tests do not inspect a private mapping constant, replace the Application or Service with test
doubles, or assert Qwen recognition accuracy. The CLI test controls only external process and HTTP
boundaries.

These seams are part of the approved plan. Any proposed test at another seam requires a plan
update and project-owner approval before test creation.

## Plan roles and delivery rules

- Worker A, Worker B, and Worker C are newly created `gpt-5.6-terra` agents with `light` reasoning
  effort and clean task-specific contexts.
- Validator A, Validator B, and Validator C are newly created `gpt-5.6-sol` agents with `light`
  reasoning effort and clean task-specific contexts.
- The root process is the Orchestrator for all three tasks. The Orchestrator is distinct from every
  Worker and Validator and does not receive a separate sub-agent model assignment.
- Worker A submits Task 1 implementation and evidence to Validator A; Worker B submits Task 2 to
  Validator B; Worker C submits Task 3 to Validator C. Each Validator reports findings and
  evidence to the root Orchestrator.
- Worker and Validator assignments remain stable for the task lifecycle. Each task is limited to
  three Worker -> Validator -> Orchestrator cycles. The Orchestrator accepts the task or returns
  actionable feedback to the same Worker through the same Validator. Failure to obtain acceptance
  after cycle 3 halts the task, and the Orchestrator produces the constitution-required
  manual-review summary.

## Execution order and safe parallelization boundaries

The functionality tasks execute in order: Task 1 -> Task 2 -> Task 3. Production changes are not
safe to parallelize because all tasks may change `qwen_asr.py`, and Task 3 depends on the complete
mapping behavior from Task 2. A Validator may inspect a completed Worker submission while the
Worker waits, but the next Worker does not start until the Orchestrator accepts the preceding task.

Evidence formatting and source-link checks may run in parallel with final static checks after Task
3 reaches green, provided those activities do not modify production code or tests.

## Test-first implementation plan

Each task delivers user-visible or caller-visible functionality. Tests are not separate tasks.
Within every task, complete one red -> green cycle at a time: create the named failing test, run it
to record the expected failure, add only the production behavior needed to pass that test, and run
the test again before starting the next cycle.

### Task 1 — Accept English primary, regional, and case variants

**Functionality:** Explicit English tags accepted by FR-002 encode Qwen's canonical `English`
provider label instead of failing after CLI validation.

**Owner:** Worker A  
**Validator:** Validator A  
**Orchestrator:** Root process  
**Dependencies:** None

**Tests to create, in implementation order:**

1. `test_explicit_english_primary_tag_encodes_canonical_qwen_label` in
   `tests/unit/protocol/test_qwen_asr.py`, asserting exact request bytes for `en`.
2. `test_explicit_english_regional_tags_encode_canonical_qwen_label`, parameterized with `en-GB`
   and `en-US` and independent literal expected bytes.
3. `test_explicit_language_primary_subtag_is_case_insensitive`, asserting `EN-us` encodes
   `English` if the public parser preserves that spelling.

**Implementation sequence:**

1. Create test 1 -> verify red -> add the minimum English primary-subtag mapping -> verify green.
2. Create test 2 -> verify red for `en-US` -> add primary-subtag extraction -> verify green.
3. Create test 3 -> verify red -> add case-insensitive primary-subtag matching -> verify green.

**Acceptance criteria:**

- `en`, `en-GB`, and `en-US` produce the exact `language English<asr_text>` continuation.
- Primary-subtag comparison follows the case behavior accepted by the public language parser.
- `auto` still produces no assistant continuation and its existing exact-byte test remains green.
- Translation remains owned by the Qwen protocol layer.

### Task 2 — Support every documented Qwen language mapping

**Functionality:** Every primary subtag in this issue's supported-mappings table encodes the exact
canonical label documented by Qwen. Region and variant subtags use their primary subtag.

**Owner:** Worker B  
**Validator:** Validator B  
**Orchestrator:** Root process  
**Dependencies:** Task 1

**Tests to create, in implementation order:**

1. `test_explicit_portuguese_regional_tag_reaches_provider_as_canonical_language` in
   `tests/integration/infrastructure/test_llama_cpp.py`, using `pt-BR` and asserting the controlled
   outbound request contains the literal `language Portuguese<asr_text>` continuation.
2. `test_supported_primary_language_tag_encodes_canonical_qwen_label` in
   `tests/unit/protocol/test_qwen_asr.py`, parameterized with independent literal pairs for:
   `zh/Chinese`, `yue/Cantonese`, `ar/Arabic`, `de/German`, `fr/French`, `es/Spanish`,
   `pt/Portuguese`, `id/Indonesian`, `it/Italian`, `ko/Korean`, `ru/Russian`, `th/Thai`,
   `vi/Vietnamese`, `ja/Japanese`, `tr/Turkish`, `hi/Hindi`, `ms/Malay`, `nl/Dutch`,
   `sv/Swedish`, `da/Danish`, `fi/Finnish`, `pl/Polish`, `cs/Czech`, `fil/Filipino`,
   `fa/Persian`, `el/Greek`, `ro/Romanian`, `hu/Hungarian`, and `mk/Macedonian`.
3. `test_supported_language_regional_and_variant_subtags_use_primary_mapping` in
   `tests/unit/protocol/test_qwen_asr.py`, parameterized with `pt-BR/Portuguese` and at least one
   three-part tag whose primary subtag is supported by the public grammar.

**Implementation sequence:**

1. Create test 1 -> verify red -> add only the Portuguese mapping -> verify green.
2. Add one case to test 2 -> verify red -> add only that mapping entry -> verify green; repeat this
   red -> green cycle separately for every listed primary subtag.
3. Create test 3 -> verify whether Task 1's primary extraction already satisfies the behavior; if
   the new test is red, add only the missing variant handling -> verify green.

**Acceptance criteria:**

- Every mapping in the supported-mappings table has a failing-before-implementation test record
  and passes after its mapping entry is added.
- The controlled provider request for `pt-BR` contains Qwen's canonical `Portuguese` label.
- The mapping has one immutable source of truth with no duplicate condition chain.
- The CLI, ASR Model Manifest, and service layer do not acquire a public supported-language
  catalog or Qwen-specific mapping logic.

### Task 3 — Reject unsupported explicit languages through the CLI contract

**Functionality:** A syntactically valid tag whose primary subtag is not supported by the shipped
Qwen adapter fails deterministically before recognition transport and produces the established
bounded CLI diagnostic.

**Owner:** Worker C  
**Validator:** Validator C  
**Orchestrator:** Root process  
**Dependencies:** Task 2

**Tests to create, in implementation order:**

1. `test_unsupported_primary_language_tag_is_rejected_before_qwen_request_encoding` in
   `tests/unit/protocol/test_qwen_asr.py`, using the syntactically valid unsupported tag `cy` and
   asserting the public exception type and deterministic message.
2. `test_unsupported_qwen_language_sends_no_recognition_http_request` in
   `tests/integration/infrastructure/test_llama_cpp.py`, using a controlled provider transport and
   asserting that no recognition request crosses the external boundary.
3. `test_asr_command_reports_unsupported_qwen_language_through_real_failure_flow` in
   `tests/acceptance/test_asr_workflow.py`, using the real Application, Service, and llama.cpp
   adapter with controlled external process and HTTP boundaries. The test asserts exit status,
   exact public stage, model ID, `segment=0`, one stderr line, no stdout, and no recognition HTTP
   request.

**Implementation sequence:**

1. Create test 1 -> verify red -> add the minimum protocol error for an unmapped primary subtag ->
   verify green.
2. Create test 2 -> verify red -> stop unsupported-language processing before recognition
   transport -> verify green.
3. Record the existing focused suite green -> create test 3 as a characterization of the shipped
   failure mapping -> verify the test is green before refactoring -> remove the unreachable
   Qwen-specific controller catch and artificial controller test -> verify test 3 remains green.

**Acceptance criteria:**

- Unsupported `cy` sends no recognition HTTP request.
- The CLI reports one bounded, actionable error line through the established public renderer,
  including `segment=0`.
- The error distinguishes a syntactically valid but provider-unsupported language from invalid
  language-tag syntax.
- The controller does not import, name, or catch `QwenUnsupportedLanguageError`.
- Existing provider cleanup guarantees remain green.
- No test asserts third-party model behavior.

## Test plan

1. Execute each mapping test individually for its red -> green cycle and retain the command and
   result in feature 002 implementation evidence. For the behavior-preserving Controller cleanup,
   record the focused suite and new characterization test green before refactoring.
2. After each task, run the complete changed test module before handing the result to its
   Validator.
3. After Task 3, run all Qwen codec, Execution Provider, ASR service, ASR controller, CLI contract,
   acceptance, and architecture tests with real-model tests excluded.
4. Run Ruff and strict mypy for production code and every changed test file.
5. Do not use a real Qwen model as a semantic oracle; controlled tests verify only project-owned
   mapping, request construction, transport suppression, and error rendering.

## Independent validation

For each task, the assigned Validator independently performs these checks without relying on the
Worker's conclusions:

1. Read this approved issue and the task's recorded red/green evidence -> verify: every production
   behavior traces to the task functionality and every named test was created before its
   corresponding production change.
2. Run the task's named tests and relevant unchanged regression tests -> verify: results satisfy
   the task acceptance criteria and overall success criteria.
3. Inspect changed entities against the architecture classifications -> verify: Protocol,
   Infrastructure, and Controller responsibilities remain separated and no unapproved entity or
   dependency was introduced.
4. Run Ruff and strict mypy on changed files -> verify: all changed production and test files pass.
5. Compare the diff with assumptions and explicit non-goals -> verify: no public language catalog,
   model selection, third-party semantic assertion, or speculative abstraction was added.
6. Submit findings and command evidence to the root Orchestrator -> verify: the Orchestrator either
   records acceptance against this approved plan or returns actionable feedback to the same Worker
   within the three-cycle limit.

## Success criteria

- All acceptance criteria above pass.
- The controlled suite is green.
- Each behavioral production change has a named test in its red -> green cycle,
  with the expected pre-fix failure recorded for this bug fix.
- All new or changed functions declare parameter and return types.
- The implementation remains confined to the Qwen protocol boundary except for tests and truthful
  evidence updates, the minimum pre-authorized Infrastructure failure handling proven necessary by
  Task 3's provider test, and the behavior-preserving removal of the unreachable Controller path.
- The public CLI test covers Protocol -> Infrastructure -> Service -> Controller behavior, and the
  controller has no Qwen-specific dependency or unreachable unsupported-language exception path.
- Review confirms compliance with FR-002, FR-011, FR-012, and the execution-provider contract.
- No public supported-language catalog or model-to-language selection behavior is introduced.
- Independent validation confirms scope traceability, simplicity, type correctness, responsibility
  boundaries, architecture classifications, and conformance to this approved plan.
