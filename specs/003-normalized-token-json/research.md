# Research: Normalized Token JSON

## PyICU NFKC boundaries

**Decision**: Use `icu.Normalizer2.getNFKCInstance()`. Iterate Python Unicode code points in provider order; call `hasBoundaryBefore(character)` with a one-character string. If true and a source span is pending, flush that span before appending the character. Normalize the completed source span with `normalize(span)` and flush at every Speech Segment end.

**Rationale**: ICU guarantees that a reported boundary permits independent normalization of adjoining text. PyICU's binding accepts a one-code-point string, including supplementary characters. A reported boundary may be conservative, so tests should assert reconstruction and provenance against the installed ICU data, not a fixed boundary count for every Unicode version.

**Alternatives considered**: Python `unicodedata` does not provide ICU's NFKC boundary predicate and can use different Unicode data. Per-token NFKC breaks cross-token composition. Grapheme or word segmentation answers a different question.

**Sources**: [ICU Normalizer2](https://unicode-org.github.io/icu-docs/apidoc/released/icu4c/classNormalizer2.html), [PyICU normalizer binding](https://github.com/ovalhub/pyicu/blob/master/normalizer.cpp), [Unicode Normalization Forms](https://www.unicode.org/reports/tr15/).

## PyICU dependency

**Decision**: Pin PyICU 2.16.2 in `pyproject.toml` and resolve `uv.lock` during implementation. Make successful `import icu` and version display an explicit dependency gate before coding Domain tests.

**Rationale**: The project pins runtime dependencies. PyICU 2.16.2 currently distributes source, requiring ICU native headers/library and a C++ build environment. This checkout has `uv` but lacks `pkg-config`, so a local install may require environment provisioning.

**Alternatives considered**: Fallback to `unicodedata` cannot meet the specified ICU boundary behavior; a custom normalization algorithm would be larger and less reliable.

**Source**: [PyICU release files](https://pypi.org/project/PyICU/).

## llama.cpp chat log probabilities and completion

**Decision**: Keep the existing nonstreaming `/v1/chat/completions` request and add `"logprobs":true,"top_logprobs":1`. Parse `choices[0].logprobs.content` entries with `id`, Unicode `token`, and `logprob`; require one assistant choice and `finish_reason="stop"`. Reject absent or malformed required token fields. Use exposed Unicode token strings as the sole transcript source; do not reconstruct or compare them with final assistant content.

**Rationale**: Bundled llama.cpp maps `top_logprobs` to `n_probs`. `0` suppresses probability output, whereas a positive value produces the sampled token records. The final response reports `stop`, `length`, or `tool_calls`. Provider-exposed token strings define the feature's transcript and probability provenance. llama.cpp stop handling may make these strings diverge from final assistant content; the user accepted that limitation.

**Alternatives considered**: `top_logprobs:0` cannot deliver token records. A separate streaming parser adds complexity with no feature need. Reconstructing from raw bytes or hidden sampling internals contradicts the approved provider boundary. Comparing with final assistant content and rejecting mismatches was considered and explicitly rejected as unnecessary for this feature.

**Sources**: bundled `vendor/llama.cpp/tools/server/server-common.cpp` lines 1133–1141, `server-task.cpp` lines 306–325 and 438–460, and `server-context.cpp` lines 1807–1855 and 2114–2128. The bundled server may coalesce bytes and truncate an individual token's `token` to valid UTF-8; the adapter uses the Unicode strings actually exposed, without attempting to recover hidden sampled pieces.

The bundled server omits `choices[0].logprobs.content` when no token probability records remain (`server-task.cpp` lines 457–460). The approved contract interprets that whole-field absence after successful completion as an empty segment. It still rejects missing fields within a present transcript token; final assistant content is not used to distinguish the two cases.

## Qwen prefix removal and code switching

**Decision**: Discard Qwen's one initial `language VALUE<asr_text>` prefix as provider metadata without emitting a language value. Everything after the first `<asr_text>` delimiter is transcript text, including a later language-looking sequence. No provider language events or language field are part of the result contract. The requested-language input to the ASR provider remains unchanged.

**Rationale**: Qwen's official parser splits at the first delimiter and returns later content as transcription. Its training examples use one initial language prefix. The user's experiments found one marker per Speech Segment even for code-switched speech, so a language on every normalization span adds no useful precision.

**Alternatives considered**: Reinterpreting later `language VALUE<asr_text>` text as metadata would remove potentially spoken content. Publishing the single Qwen language on every span would repeat a value that does not identify code-switch boundaries. Rejecting later literal text would unnecessarily fail a completed response.

**Sources**: [Qwen ASR parser](https://github.com/QwenLM/Qwen3-ASR/blob/main/qwen_asr/inference/utils.py#L1822-L1931), [Qwen fine-tuning output examples](https://github.com/QwenLM/Qwen3-ASR/blob/main/finetuning/README.md#L214-L236).

The same Qwen parser treats initial `language None` as a prefix and retains any following transcript text. The adapter discards that prefix without storing a language value. The bundled llama.cpp `logprobs.content` record uses an integer token `id` (`vendor/llama.cpp/tools/server/server-task.cpp` lines 306–324; `include/llama.h` line 69). The provider-neutral contract keeps that ID in its original form rather than converting it for the JSON artifact.

## Architecture and publication

**Decision**: Keep Qwen JSON decoding in Protocol, provider lifecycle/result in Infrastructure, span normalization and JSON assembly in Domain, ordered workflow in Service, and cross-layer event mapping in Composition. Reuse `AtomicFileWriter` through `publish_transcript`, changing its destination to `transcript.json`.

**Rationale**: `architecture/layers.md` forbids Infrastructure importing Protocol and Domain importing Infrastructure. The existing service already waits for all segments and provider cleanup before publication, and the file adapter already publishes atomically.

**Alternatives considered**: Putting Qwen parsing in Domain leaks provider markup; having Infrastructure import the Protocol codec violates the layer gate; queue/thread processing contradicts the confirmed specification; writing segment artifacts would alter the output contract.

**Sources**: `architecture/layers.md`, `src/transcriber/service/recognize_segments.py`, `src/transcriber/infrastructure/asr_files.py`.
