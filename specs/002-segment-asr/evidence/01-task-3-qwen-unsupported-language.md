# Issue 01 — Task 3: unsupported Qwen language failure

## Red → green and characterization evidence

| Slice | Red command and result | Green command and result |
| --- | --- | --- |
| Typed protocol failure | `uv run pytest tests/unit/protocol/test_qwen_asr.py::test_unsupported_primary_language_tag_is_rejected_before_qwen_request_encoding -q` — exit 1; collection failed because `QwenUnsupportedLanguageError` was absent | Same command — exit 0; `1 passed in 0.01s` |
| Execution Provider transport suppression | `uv run pytest tests/integration/infrastructure/test_llama_cpp.py::test_unsupported_qwen_language_sends_no_recognition_http_request -q` — exit 1; `cy` propagated `QwenUnsupportedLanguageError` instead of the Execution Provider failure contract | Same command — exit 0; `1 passed in 0.01s`; the controlled transport recorded no recognition request |
| Real CLI failure flow | The focused affected suite was green before the cleanup: `223 passed, 1 deselected`. The first characterization attempt failed in the test setup because a wall-clock timeout was asserted as exactly `60.0`; no Qwen request was reached. After injecting a deterministic clock, `uv run pytest tests/acceptance/test_asr_workflow.py::test_asr_command_reports_unsupported_qwen_language_through_real_failure_flow -q` exited 0 with `1 passed`. The test observed no recognition HTTP request and the exact segment-specific diagnostic. | The same characterization test remained green after removing the unreachable controller catch and artificial controller test: exit 0; `1 passed in 0.05s`. |

## Final verification

| Command | Result |
| --- | --- |
| `uv run pytest tests/unit/protocol/test_qwen_asr.py tests/integration/infrastructure/test_llama_cpp.py tests/unit/controller/test_asr_cli.py tests/acceptance/test_asr_workflow.py::test_asr_command_reports_unsupported_qwen_language_through_real_failure_flow -q` | exit 0; `116 passed in 0.10s` |
| `uv run pytest tests/unit/protocol/test_qwen_asr.py tests/integration/infrastructure/test_llama_cpp.py tests/unit/service/test_recognize_segments.py tests/unit/controller/test_asr_cli.py tests/contract/test_asr_cli_contract.py tests/acceptance/test_asr_workflow.py tests/architecture/test_layer_dependencies.py -m 'not real_asr' -q` | exit 0; `223 passed, 1 deselected in 0.20s` |
| `uv run ruff check src/transcriber/protocol/qwen_asr.py src/transcriber/infrastructure/llama_cpp.py src/transcriber/controller/asr_cli.py tests/unit/protocol/test_qwen_asr.py tests/integration/infrastructure/test_llama_cpp.py tests/unit/controller/test_asr_cli.py tests/acceptance/test_asr_workflow.py` | exit 0; `All checks passed!` |
| `uv run mypy --strict src/transcriber/protocol/qwen_asr.py src/transcriber/infrastructure/llama_cpp.py src/transcriber/controller/asr_cli.py` | exit 0; `Success: no issues found in 3 source files` |
| `MYPYPATH=src uv run mypy --strict tests/acceptance/test_asr_workflow.py tests/unit/controller/test_asr_cli.py tests/integration/infrastructure/test_llama_cpp.py tests/unit/protocol/test_qwen_asr.py` | exit 1 with 31 pre-existing findings in the acceptance, Infrastructure, and Controller test modules; no finding points to the new characterization test. |

The Protocol layer owns the typed deterministic `cy` failure. The Execution Provider converts the
request-encoding failure to its existing failure contract before transport. `RecognizeSegments`
attaches Speech Segment index 0, and the Controller renders the returned `AsrFailure` without a
Qwen-specific import or exception branch. No public supported-language catalog or model-selection
behavior was added.
