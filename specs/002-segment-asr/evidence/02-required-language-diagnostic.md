# Issue 02 — Required ASR language diagnostic

## Red → green evidence

| Slice | Red command and result | Green command and result |
| --- | --- | --- |
| Required language Controller diagnostic | `uv run pytest tests/unit/controller/test_asr_cli.py::test_required_model_automatic_language_returns_two_before_task_or_provider_work -q` — exit 1; status remained 2, but stderr was empty instead of the required `ERROR [asr-model]` line | Same command — exit 0; `1 passed in 0.03s` |

## Final verification

| Command | Result |
| --- | --- |
| `uv run pytest tests/unit/controller/test_asr_cli.py tests/unit/composition/test_asr_application.py -q` | exit 0; `40 passed in 0.05s` |
| `uv run pytest tests/unit/controller/test_asr_cli.py tests/unit/composition/test_asr_application.py tests/unit/service/test_recognize_segments.py tests/contract/test_asr_cli_contract.py tests/acceptance/test_asr_workflow.py tests/architecture/test_layer_dependencies.py -m 'not real_asr' -q` | exit 0; `148 passed, 1 deselected in 0.15s` |
| `uv run ruff check src/transcriber/controller/asr_cli.py tests/unit/controller/test_asr_cli.py` | exit 0; `All checks passed!` |
| `uv run mypy --strict src/transcriber/controller/asr_cli.py` | exit 0; `Success: no issues found in 1 source file` |
| `MYPYPATH=src uv run mypy --strict tests/unit/controller/test_asr_cli.py` | exit 1 with two pre-existing findings at lines 375 and 392; neither finding points to the changed required-language test |

The Controller catches the Composition-owned `RequiredAsrLanguageError`, converts the error to an
`AsrFailure` at the closed `asr-model` stage, and delegates escaping and bounding to the existing
failure renderer. The status remains 2, stdout remains empty, and the ASR Service remains outside
the rejection path.
