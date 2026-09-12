# Issue 01 — Task 2: documented Qwen language mappings

## Red → green evidence

| Slice | Red command and result | Green command and result |
| --- | --- | --- |
| `pt-BR` provider boundary | `uv run pytest tests/integration/infrastructure/test_llama_cpp.py::test_explicit_portuguese_regional_tag_reaches_provider_as_canonical_language -q` — exit 1; `pt-BR` raised `ValueError: Qwen request supports automatic language or English` before transport | Same command — exit 0; `1 passed in 0.01s` |
| `zh` / `Chinese` | `uv run pytest tests/unit/protocol/test_qwen_asr.py::test_supported_primary_language_tag_encodes_canonical_qwen_label -q` — exit 1; `zh` raised the unmapped-language `ValueError` | Same command — exit 0 |
| `yue` / `Cantonese` | Same command — exit 1; newly added `yue` case raised the unmapped-language `ValueError` | Same command — exit 0 |
| `ar` / `Arabic` | Same command — exit 1; newly added `ar` case raised the unmapped-language `ValueError` | Same command — exit 0 |
| `de` / `German` | Same command — exit 1; newly added `de` case raised the unmapped-language `ValueError` | Same command — exit 0 |
| `fr` / `French` | Same command — exit 1; newly added `fr` case raised the unmapped-language `ValueError` | Same command — exit 0 |
| `es` / `Spanish` | Same command — exit 1; newly added `es` case raised the unmapped-language `ValueError` | Same command — exit 0 |
| `pt` / `Portuguese` | Provider-boundary slice above supplied the red result and production entry; added protocol-table case is green | Same command — exit 0 |
| `id`, `it`, `ko`, `ru`, `th`, `vi`, `ja`, `tr`, `hi`, `ms`, `nl`, `sv`, `da`, `fi`, `pl`, `cs`, `fil`, `fa`, `el`, `ro`, `hu`, `mk` | For each entry, the same command was run immediately after adding that one parameter: exit 1, with the new case raising the unmapped-language `ValueError` | After adding only that entry to the immutable provider mapping, the same command exited 0 |
| Regional and variant primary extraction | `uv run pytest tests/unit/protocol/test_qwen_asr.py::test_supported_language_regional_and_variant_subtags_use_primary_mapping -q` — Task 1 primary extraction already satisfied the new `pt-BR` and `zh-Hans-CN` cases | Same command — exit 0; `2 passed in 0.01s` |

The individual red→green cycles for `id` through `mk` were run in table order. The protocol
parameter list holds independent primary-subtag/canonical-label literals; `pt` is covered by the
earlier provider-boundary red cycle because adding its protocol-table case correctly did not turn
the already-installed behavior red.

## Final verification

| Command | Result |
| --- | --- |
| `uv run pytest tests/unit/protocol/test_qwen_asr.py tests/integration/infrastructure/test_llama_cpp.py -q` | exit 0; `80 passed in 0.03s` |
| `uv run ruff check src/transcriber/protocol/qwen_asr.py tests/unit/protocol/test_qwen_asr.py tests/integration/infrastructure/test_llama_cpp.py` | exit 0; `All checks passed!` |
| `uv run mypy --strict src/transcriber/protocol/qwen_asr.py tests/unit/protocol/test_qwen_asr.py tests/integration/infrastructure/test_llama_cpp.py` | exit 1; eight pre-existing errors in `tests/integration/infrastructure/test_llama_cpp.py` at lines 108, 242, 244, 309, 364, 412, and 415. The changed protocol module and protocol test module have no reported errors. |

The final mapping is a single `MappingProxyType` at the Qwen protocol boundary. No CLI, ASR
Model Manifest, service, or public language catalog changed.
