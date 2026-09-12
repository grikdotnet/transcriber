# Issue 01 — Task 1: English Qwen language mappings

## Scope

Task 1 changes only the Qwen protocol request encoder and its approved protocol-seam tests.
The controller and ASR Task continue to pass the selected language tag unchanged.

## Red → green evidence

| Slice | Red command and result | Green command and result |
| --- | --- | --- |
| Explicit `en` | `uv run pytest tests/unit/protocol/test_qwen_asr.py::test_explicit_english_primary_tag_encodes_canonical_qwen_label -q` — exit 1; `ValueError: Qwen request supports automatic language or en-GB` | Same command — exit 0; `1 passed in 0.01s` |
| `en-GB` and `en-US` primary extraction | `uv run pytest tests/unit/protocol/test_qwen_asr.py::test_explicit_english_regional_tags_encode_canonical_qwen_label -q` — exit 1; `en-GB` passed and `en-US` raised `ValueError: Qwen request supports automatic language or English` | Same command — exit 0; `2 passed in 0.01s` |
| Case-insensitive primary subtag | `uv run pytest tests/unit/protocol/test_qwen_asr.py::test_explicit_language_primary_subtag_is_case_insensitive -q` — exit 1; `EN-us` raised `ValueError: Qwen request supports automatic language or English` | Same command — exit 0; `1 passed in 0.01s` |

## Final verification

| Command | Result |
| --- | --- |
| `uv run pytest tests/unit/protocol/test_qwen_asr.py -q` | exit 0; `35 passed in 0.01s` |
| `uv run ruff check src/transcriber/protocol/qwen_asr.py tests/unit/protocol/test_qwen_asr.py` | exit 0; `All checks passed!` |
| `uv run mypy --strict src/transcriber/protocol/qwen_asr.py tests/unit/protocol/test_qwen_asr.py` | exit 0; `Success: no issues found in 2 source files` |

The existing automatic-language exact-byte test remains in the complete module and passed during
final verification. The expected request values are independent literal provider-wire bytes.
