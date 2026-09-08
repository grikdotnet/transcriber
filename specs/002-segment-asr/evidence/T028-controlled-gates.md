# T028 controlled gates

**Run completed:** 2026-09-08T05:55:01Z  
**Scope:** deterministic controlled suite and package-resource inspection only. No real-provider,
real-VAD, or real-ASR command was run.

## Tool versions

| Tool | Exact version/output |
| --- | --- |
| uv | `uv 0.11.23 (3cdf50e09 2026-06-19 aarch64-apple-darwin)` |
| Python | `Python 3.12.13` |
| pytest | `pytest 9.0.2` |
| mypy | `mypy 1.19.1 (compiled: yes)` |
| ruff | `ruff 0.15.5` |
| unzip | `UnZip 6.00 of 20 April 2009, by Info-ZIP, with modifications by Apple Inc.` |

`uv build` does not support a `--version` flag in this installed uv release; the uv version above
is the version used to run the build.

## Deterministic controlled gates

| Command | Status | Result | Pytest outcomes and validation |
| --- | --- | --- | --- |
| `uv run pytest -m "not real_vad and not real_asr"` | exit 0 | `495 passed, 11 deselected in 2.57s` | `skipped=0`, `xfailed=0`, `xpassed=0`; pass. The summary contained none of these outcome labels. |
| `uv run pytest tests/contract tests/architecture -q` | exit 0 | `61 passed in 0.32s` | `skipped=0`, `xfailed=0`, `xpassed=0`; pass. The summary contained none of these outcome labels. |
| `uv run pytest tests/unit/controller/test_cli.py tests/unit/composition/test_application.py -q` | exit 0 | `26 passed in 0.04s` | `skipped=0`, `xfailed=0`, `xpassed=0`; pass. The summary contained none of these outcome labels. |
| `uv run pytest tests/unit/test_real_asr_prerequisites.py -q` | exit 0 | `8 passed in 0.01s` | `skipped=0`, `xfailed=0`, `xpassed=0`; pass. The summary contained none of these outcome labels. |
| `uv run mypy --strict src` | exit 0 | `Success: no issues found in 33 source files` | Not a pytest command. |
| `uv run ruff check src tests` | exit 0 | `All checks passed!` | Not a pytest command. |

For each pytest gate, any count other than zero for `skipped`, `xfailed`, or `xpassed` would fail
T028. All observed counts are zero, so the controlled pytest outcome gate passes.

## Controlled package-resource verification

| Command | Status | Result |
| --- | --- | --- |
| `uv build --wheel` | exit 0 | `Successfully built dist/transcriber-0.1.0-py3-none-any.whl` |
| `unzip -l dist/transcriber-0.1.0-py3-none-any.whl | rg -F 'transcriber/resources/asr_models/qwen3-asr-1.7b.json'` | exit 0 | `673  02-02-2020 00:00   transcriber/resources/asr_models/qwen3-asr-1.7b.json` |

The wheel contains the required ASR model manifest. These commands only build and inspect package
contents; neither command starts a provider nor executes a real-VAD or real-ASR test.
