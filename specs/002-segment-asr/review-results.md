# Feature 002 Review Results

**Review date:** 2026-09-12  
**Branch:** `002-segment-asr`  
**Reviewed commit:** `ed8f21c` plus the current working-tree corrections

## Scope

This review reassesses the actionable findings from the consolidated Feature 002 review and the
Qwen language-mapping follow-up review. The review incorporates the project owner's decisions
about intentional architecture and accepted risk.

The following items are explicitly excluded from the review result:

- missing test-first commit history;
- the `docs/cli.md` documentation-contract failure.

## Result

No blocking finding remains within the agreed review scope. The Qwen language mapping, real
unsupported-language failure flow, and required-language diagnostic satisfy their applicable
requirements. The native Composition boundary and the current encoder `ValueError` conversion are
accepted design decisions.

## Finding dispositions

### Resolved — valid Qwen language tags

`transcriber.protocol.qwen_asr` defines all 30 documented Qwen language mappings and performs an
ASCII case-insensitive primary-subtag lookup. Primary, regional, and variant forms such as `en`,
`EN-us`, `pt-BR`, and `zh-Hans-CN` map to the expected canonical Qwen labels. `auto` continues to
omit the assistant language continuation.

Evidence:

- `src/transcriber/protocol/qwen_asr.py`
- `tests/unit/protocol/test_qwen_asr.py`
- `specs/002-segment-asr/evidence/01-task-1-qwen-english-language-mappings.md`
- `specs/002-segment-asr/evidence/01-task-2-qwen-supported-language-mappings.md`

### Resolved — real unsupported-Qwen-language CLI failure flow

The public CLI coverage now uses a real `Application`, `RecognizeSegments`, and
`LlamaCppExecutionProvider`, while controlling only the external process and HTTP boundaries. An
unsupported `cy` language reaches Qwen request encoding for Speech Segment 0, sends no recognition
HTTP request, cleans up the Execution Provider, returns status 1, and renders exactly one bounded
`execution-provider` diagnostic containing `segment=0`.

The controller no longer imports or catches `QwenUnsupportedLanguageError`; the controller renders
the application-owned `AsrFailure` returned through the normal failure path.

Evidence:

- `src/transcriber/controller/asr_cli.py`
- `tests/acceptance/test_asr_workflow.py::test_asr_command_reports_unsupported_qwen_language_through_real_failure_flow`
- `specs/002-segment-asr/evidence/01-task-3-qwen-unsupported-language.md`

### Resolved — required-language rejection diagnostic

When an ASR Model with required language behavior receives `--language auto`, the Application
rejects the command before ASR Service or Execution Provider work. The controller now renders one
bounded diagnostic and retains status 2:

```text
ERROR [asr-model] model="qwen3-asr-1.7b": ASR Model requires an explicit language
```

Evidence:

- `specs/002-segment-asr/issues/02-required-language-diagnostic.md`
- `src/transcriber/controller/asr_cli.py`
- `tests/unit/controller/test_asr_cli.py::test_required_model_automatic_language_returns_two_before_task_or_provider_work`
- `specs/002-segment-asr/evidence/02-required-language-diagnostic.md`

### Accepted design — native Composition boundary

`native/firered_vad_ncnn/composition/application.cpp` intentionally preserves a distinct
Composition layer between the Controller and Service. The small forwarding function expresses the
architectural boundary and is not treated as a Middle Man defect.

### Accepted risk — encoder `ValueError` conversion

`LlamaCppExecutionProvider` currently converts request-encoder `ValueError` instances to
`ExecutionProviderFailure`. With the production Qwen encoder, the only normally reachable
request-encoding `ValueError` is `QwenUnsupportedLanguageError`. The broader catch therefore has
little immediate behavioral impact and is accepted without a separate finding.

The Standards and Spec observations about this catch described the same concern and are recorded
once here rather than counted twice.

## Verification

| Check | Result |
| --- | --- |
| Required-language Controller and Application tests | `2 passed` |
| Qwen Protocol, Infrastructure, and real CLI failure-flow tests | `83 passed` |
| Ruff on affected production and test files | Passed |
| Mypy on affected production modules | Passed |

## Final assessment

Feature 002 passes this resolution review under the stated scope and accepted design decisions.
