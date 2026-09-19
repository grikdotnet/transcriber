# Data Model: Normalized Token JSON

## Recognition Token

One provider-exposed transcript item: `token_id` (original, non-null, provider-native identifier; an integer for bundled llama.cpp), `text` (authoritative valid Unicode string), and `log_probability` (real number ≤ 0, including negative infinity; never a boolean). Missing fields, booleans masquerading as numbers, positive values, and NaN fail at the provider-response boundary. Empty text is skipped. After provider control removal, an item with no remaining transcript text contributes no probability; a mixed control/transcript item retains its original ID and score for the remaining text. A token may contribute to zero, one, or several source spans; no byte reconstruction occurs.

The ordered exposed token strings, after defined control removal, are the transcript source. Final assistant content does not correct, validate, or replace token text. llama.cpp stop handling may leave the two representations different; that divergence is accepted.

## Recognition Result

One complete Speech Segment response containing ordered Recognition Tokens and an explicit successful provider completion. Only a complete result enters Domain processing. An absent complete token-probability list on a successful provider response represents zero exposed tokens and an empty segment; it does not waive required fields for an item that is present. Final assistant content is not inspected to infer tokens. Provider controls, metadata, and stop markers are absent. Qwen's one initial language prefix is removed without producing a language event. A mixed metadata/transcript provider item retains the transcript substring with its original token ID and log probability.

## Pending Normalization Span

Transient maximal consecutive source-code-point sequence since the previous guaranteed NFKC boundary within one Speech Segment. Fields: source text, UTF-8 byte count (0–16,384), and minimum contributing token log probability. A new code point with `NFKC.hasBoundaryBefore(character)` first completes any pending span. Provider token boundaries and control metadata never complete a span. Segment completion flushes the final span; exceeding the byte bound fails without editing the source text.

## Published Normalization Span

Fields in order: `text` (non-empty NFKC result of one source span) and `probability` (`exp(minimum log_probability)` as a finite JSON number in [0,1]). Negative infinity maps to 0. A completed source span whose NFKC result is empty has no published entry. Scores attach to whole normalized spans, even where normalization expands or composes code points. No language field is published.

## Structured Transcript

One ordered list of published spans across Segment Manifest order. It owns exact compact UTF-8 JSON bytes: one top-level `text` array and one final LF. Empty success is `{"text":[]}\n`. Concatenated span text forms recognition context for subsequent segments, subject to the existing 2,048-code-point context and leading-fragment behavior. No separator is introduced.

Each Speech Segment is normalized independently. Transcript text is the concatenation of those per-segment results; joining source text across segment boundaries and then normalizing it would be a different operation.

## State transitions and ownership

`new segment → empty pending span → ordered tokens → flush on ICU boundary → flush at segment end → append published spans → one progress event → next segment`. After all segments and successful provider cleanup, Service asks Infrastructure to atomically publish the Transcript. Any error before publication leaves a prior complete JSON artifact unchanged.

Protocol validates provider wire values and discards Qwen's initial language prefix. Composition maps Protocol tokens to Infrastructure provider-neutral tokens. Service passes token primitives into Domain. Domain owns normalization/scoring/serialization; Infrastructure owns provider I/O and atomic file publication. Requested language remains part of the provider request, outside the result model.
