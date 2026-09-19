# Implementation Plan: Normalized Token JSON

**Branch**: `003-normalized-token-json` | **Date**: 2026-09-16 | **Spec**: [spec.md](spec.md)

## Summary

Replace plain-text recognition with ordered provider tokens. The Qwen adapter requests provider log probabilities, validates explicit successful completion, strips provider-defined control data including the initial language prefix, and retains transcript token text with its original ID and score. A synchronous Domain accumulator uses PyICU NFKC boundaries to emit scored spans per Speech Segment, assemble compact two-field JSON, and derive context from normalized text. Service orders Speech Segments and publishes `transcript.json` atomically after all segments and provider cleanup succeed.

## Technical Context

**Language/Version**: Python 3.12 (`>=3.12,<3.13`).

**Primary Dependencies**: pinned NumPy; add pinned PyICU 2.16.2 and resolve `uv.lock`; bundled llama.cpp server. PyICU needs native ICU development headers and a C++ build environment. Current checkout has `uv` but no `pkg-config`; validate installation prerequisites before implementation tests.

**Storage**: local Segment Manifest/WAV files and atomic `transcripts-{model-id}/transcript.json`.

**Testing**: pytest 9.0.2 with controlled fixtures; ruff 0.15.5; mypy 1.19.1; architecture tests; required real-provider checkpoint for SC-006.

**Target Platform**: existing local/offline CLI environment.

**Project Type**: Python CLI/service with Protocol, Infrastructure, Domain, Service, Composition, Controller layers.

**Performance Goals**: one ordered pass over token text; pending source span bounded to 16,384 UTF-8 bytes; one progress event per segment. No throughput target specified.

**Constraints**: no normalization thread or queue; no invented separators, trimming, byte reconstruction, language detection, or hidden llama.cpp probabilities. Preserve existing timeouts, lifecycle, status codes, and prior complete artifact on failure.

**Scale/Scope**: one ASR Task over all manifest segments; controlled tests for 1–100 segments; normalization state resets for each segment.

**Clarification status**: No `NEEDS CLARIFICATION` remains in the feature contract. The Qwen adapter discards its initial language prefix without emitting a language event; later language-looking sequences are literal transcript text. Provider-exposed Unicode token strings are authoritative. Final assistant content is not reconstructed or compared with those strings; divergence caused by llama.cpp stop handling is accepted. Successful completion with no token-probability list is an empty segment; a present transcript token lacking a required field still fails.

## Constitution Check

**Before research — PASS**: Test-first work, single-layer ownership, typed boundary values, reuse of atomic publication, and synchronous processing require no exception.

**After design — PASS**: Protocol codecs and Infrastructure provider types meet through a Composition mapper; Service orchestrates and Domain normalizes. Every work item below has acceptance criteria, test-first checks, ownership, dependencies, and scope. Executable task IDs are in [tasks.md](tasks.md).

## Project Structure

```text
specs/003-normalized-token-json/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── execution-provider.md
    └── transcript-json.md
```

Affected code: `pyproject.toml`, `uv.lock`, `src/transcriber/protocol/qwen_asr.py`, `src/transcriber/infrastructure/{execution_provider,llama_cpp,asr_files}.py`, `src/transcriber/domain/transcript.py`, `src/transcriber/service/recognize_segments.py`, `src/transcriber/composition/application.py`, and the corresponding `tests/{unit,integration,contract,acceptance,architecture}` files and `tests/support/asr.py`. Update `docs/cli.md` and `README.md` where artifact paths are shown. The CLI controller changes only if it hard-codes the old filename.

**Structure decision**: Extend the existing single Python project. Add no layer, thread, queue, or provider-specific behavior to Domain.

## Entities, layers, relationships

| Entity or function | Layer | Responsibility and relationship |
|---|---|---|
| Qwen request/response codecs and typed Qwen token result | Protocol | Encode logprob request; decode one completed response, discard initial control prefix, validate token fields and order. |
| Recognition Token, Recognition Result, Execution Provider session | Infrastructure | Provider-neutral adapter result and lifecycle; Composition maps Qwen wire tokens into these types. |
| `LlamaCppExecutionProvider`, `HttpLoopbackTransport`, `publish_transcript` | Infrastructure | Use injected typed callables to encode requests and decode provider-neutral results; fetch the provider response, map errors, and atomically write final bytes. |
| Normalization Span and Transcript accumulator | Domain | Consume primitive token text/log probability; detect ICU boundaries; own source span, score, context, and exact JSON encoding. No provider or file I/O. |
| `RecognizeSegments` | Service | Consume results synchronously in manifest order; reset each segment; publish after cleanup; emit segment progress. |
| `build_application` | Composition | Map Protocol result to Infrastructure result and wire unchanged dependencies. |
| CLI result path | Controller/Protocol | Preserve command grammar/status; report new artifact path. |

The Qwen codec returns typed Protocol tokens. Composition maps tokens to the Infrastructure Recognition Result, preserving order and values; Infrastructure does not import Protocol. Replace the provider-specific `QwenRequestEncoder` and `QwenResponseDecoder` interfaces in Infrastructure with standard typed callables: `Callable[[RecognitionRequest], bytes]` for request encoding and `Callable[[bytes], RecognitionResult]` for response decoding. Composition supplies wrappers around the Qwen Protocol codecs, including the token mapping. This keeps the project-defined interface and implementation layer rule in `architecture/layers.md` intact. Service passes primitive token text/log probability to Domain, so Domain does not import Infrastructure. Each completed Normalization Span owns NFKC text and the minimum contributing log probability. Transcript owns ordered spans across segments. Requested language remains an input to the provider request and is not a result field.

## Implementation work items and parallel boundaries

The root agent is **Orchestrator**. For each separate `Tnnn` in [tasks.md](tasks.md), create a fresh Worker `Wnnn` and a distinct fresh Validator `Vnnn` with clean, task-specific context. Assign the Worker `gpt-5.6-terra` with `low` reasoning effort and the Validator `gpt-5.6-sol` with `low` reasoning effort, exactly as required by the constitution. Worker sends code and verification evidence to its Validator; Validator checks spec, plan, tests, architecture, and scope; Orchestrator accepts or returns findings. Keep the same pair for revisions, stop after three review cycles, and prepare the constitution's manual-review summary if unresolved. The rows below describe work streams and do not assign agents across multiple tasks.

| Order | Scope and dependencies | Acceptance and deterministic verification |
|---|---|---|
| 1 | PyICU dependency gate; no code dependency. | Pin PyICU in `pyproject.toml`/`uv.lock`; `uv run python -c 'import icu; print(icu.VERSION, icu.ICU_VERSION)'` and `uv lock --check` must pass before dependent tasks. If native prerequisites are missing, provision them and rerun; the gate remains incomplete until both checks pass. |
| 2a | Domain spans/Transcript; depends on 1; parallel with 2b/2c on disjoint files. | Write tests first for boundaries, cross-token scores, segment flush, two-field JSON/context; implement minimum Domain logic; `uv run pytest tests/unit/domain/test_transcript.py tests/architecture/test_layer_dependencies.py -q` passes. The 16 KiB limit is added test-first in the later failure-path work. |
| 2b | Qwen Protocol codec; independent of 2a/2c. | Write tests first for request, ordered tokens, stripping the initial language prefix, literal later language-looking text, metadata/text overlap, and absent whole `logprobs.content` as empty success; implement typed token result without final-content comparison; `uv run pytest tests/unit/protocol/test_qwen_asr.py -q` passes. Malformed present token fields and abnormal completion are added test-first in the later failure-path work. |
| 2c | Infrastructure result, llama adapter and publication; independent source files from 2a/2b. | Write tests first; preserve lifecycle, deadlines and bounded diagnostics; atomic `transcript.json`; focused Infrastructure tests pass. |
| 3 | Composition mapping and Service; depends on 2a–2c. | Write tests first for order, segment reset, context, progress, failures/cleanup/prior artifact; synchronous orchestration; focused Service/Composition/architecture tests pass. |
| 4 | Fixtures, public contract, docs, acceptance; depends on 3. | Exact two-field JSON, empty, multilingual token text, 1/100 segments and failure matrix pass via `uv run pytest tests/contract tests/acceptance/test_asr_workflow.py -m 'not real_asr' -q`. |
| 5 | Independent integration verification; depends on 4. | Run full non-real suite, ruff, mypy; inspect exact acceptance criteria and diff scope; complete the real-provider checkpoint for SC-006 using local model prerequisites, verifying exposed token fields and completion without comparing token text to final assistant content. Missing prerequisites block SC-006 completion. |

Each item follows `write behavior test → verify: focused test identifies unmet behavior; implement minimum change → verify: focused test passes; refactor if needed → verify: same tests pass`. Domain, Protocol, and Infrastructure work streams may run concurrently only on disjoint files; Composition/Service and acceptance run sequentially to avoid shared fixtures. For each `Tnnn`, Validator `Vnnn` receives Worker `Wnnn`'s result.

## Assumptions and non-goals

- Provider-emitted `token` is authoritative valid Unicode text; `bytes` and final assistant content are ignored for transcript construction and scoring. No token/content mismatch detection is planned.
- Qwen's initial language marker is discarded as control metadata, even when a phrase contains multiple languages. A later language-looking sequence is literal transcript text. No provider language events or output language values are part of this feature.
- Bundled llama.cpp stop handling may make final assistant content differ from exposed token strings. This is an accepted limitation, not a provider-response failure.
- An absent entire `logprobs.content` field with successful completion is zero exposed transcript tokens. Missing fields inside a present transcript token still fail.
- For the bundled nonstreaming response, only `finish_reason="stop"` succeeds.
- Span partition follows installed ICU data. Tests use the same PyICU normalizer for their whole-segment oracle.
- Requested ASR language remains an input and is not published in the Transcript.
- Existing `transcript.txt` is neither migrated nor published anew.
- No words, timestamps, speakers, alternatives, probability calibration, worker thread, queue, or application language detection.
- No alteration of model accuracy or hidden llama.cpp sampling.

## Test plan and independent verification

1. Write Domain tests before code → verify: exact NFKC text and token provenance for `e` plus combining acute and punctuation, compatibility expansion, Hangul Jamo, halfwidth Katakana, and whitespace; each JSON span has exactly `text` and `probability`. Add span-overflow tests before implementing the limit in the failure-path work.
2. Write Protocol/Infrastructure tests before code → verify: `logprobs:true` and `top_logprobs:1`; an absent whole `logprobs.content` field on successful completion is empty success, while a present transcript token with missing/positive/NaN log probability fails; malformed initial metadata and abnormal completion fail; mixed metadata/text retains ID and score; the initial Qwen language prefix is stripped without an event; later language-looking text remains literal; differing final assistant content does not change the token-derived result.
3. Write Service/publication tests before code → verify: prior complete bytes survive failures/cancellation, temporary files are absent, progress remains per segment, context concatenates normalized spans, and empty output is exactly `{"text":[]}\n`.
4. Run 1- and 100-segment controlled acceptance → verify: each segment's span concatenation equals that segment's whole-text ICU NFKC result, the complete Transcript joins these results without separators, every retained source code point contributes to exactly one source Normalization Span within its segment, and scores match fixtures; spans normalizing to empty text have no published entry.
5. Run `uv run pytest -m 'not real_asr' -q`, `uv run ruff check .`, `uv run mypy src`, and architecture tests → verify: no unaffected CLI/VAD regression or layer violation.
6. Complete the real-provider checkpoint after provisioning model prerequisites → verify: token IDs/text/log probabilities and successful completion are exposed; construct the artifact from retained token strings without comparing final assistant content; never assert ASR accuracy or score calibration. Missing model prerequisites leave SC-006 incomplete.

An independent Validator compares evidence and artifact bytes against FR-001–FR-025 and SC-001–SC-006, and reviews the diff for scope and layers.

## Complexity Tracking

No constitution violations or extra abstraction are planned.
