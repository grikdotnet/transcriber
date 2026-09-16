# Feature Specification: Normalized Token JSON

**Feature Branch**: `003-normalized-token-json`

**Created**: 2026-09-16

**Status**: Draft

**Input**: User description: "Replace the plain-text ASR result with scored NFKC-normalized text
spans derived from provider-emitted recognition tokens, and publish the spans as JSON."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consume normalized text with confidence (Priority: P1)

A GUI starts an ASR Task and receives one JSON Transcript containing recognized text as ordered
Normalization Spans. Each span contains NFKC-normalized text, a probability derived from the
Execution Provider's token log probabilities, and the provider-reported language applicable to the
span. A consumer can reconstruct the complete normalized transcript without parsing plain text or
repeating Unicode normalization.

**Why this priority**: The normalized, scored JSON Transcript is the primary result of recognition
and replaces the existing plain-text artifact.

**Independent Test**: Supply controlled Recognition Tokens whose text crosses normalization
boundaries, complete one ASR Task, and verify the exact ordered JSON entries, normalized text,
probabilities, languages, and reconstructed Transcript.

**Acceptance Scenarios**:

1. **Given** Recognition Token `e` with log probability `ln(0.9)` followed by Recognition Token
   `◌́.` with log probability `ln(0.7)`, **When** the Speech Segment completes, **Then** the JSON
   Transcript contains `é` with probability `0.7` followed by `.` with probability `0.7`.
2. **Given** several Recognition Tokens that contribute text to one Normalization Span, **When**
   the span is published, **Then** its probability is the exponential of the minimum contributing
   token log probability.
3. **Given** one Recognition Token whose text contributes to multiple Normalization Spans, **When**
   the spans are published, **Then** that token's log probability contributes to the score of every
   such span.
4. **Given** ordered non-empty span texts, **When** a consumer concatenates them without inserting
   separators, **Then** the result equals NFKC normalization of the retained provider transcript
   text in Speech Segment order.

---

### User Story 2 - Preserve provider language changes (Priority: P2)

An Execution Provider may report no language, one language, or several language changes within one
Speech Segment. Each Normalization Span identifies the most recent provider-reported language that
applies to its text, allowing consumers to handle multilingual phrases without assuming that one
language describes the entire Transcript.

**Why this priority**: Language can change within a phrase, while some ASR Models do not report a
language at all. Span-level language preserves available information without inventing it.

**Independent Test**: Supply controlled language changes interleaved with Recognition Tokens and
verify each span's language, including unknown language and a change while a span is pending.

**Acceptance Scenarios**:

1. **Given** no provider-reported language at the start of a Speech Segment, **When** text is
   normalized, **Then** each span before the first language value has `language: null`.
2. **Given** provider-reported language `English` followed later by `Spanish`, **When** text follows
   each value, **Then** the resulting spans carry `English` and `Spanish` respectively.
3. **Given** a language change after the first code point of a pending Normalization Span, **When**
   that span is completed, **Then** the span retains the language active for its first code point
   and the new language applies to following spans.
4. **Given** a new Speech Segment after one that ended with a known language, **When** recognition
   begins, **Then** the new Speech Segment starts with unknown language until its provider reports a
   value.
5. **Given** the Qwen ASR prefix `language English<asr_text>` followed by `I'm trying`, **When** the
   adapter processes the provider result, **Then** the prefix is absent from Transcript text and the
   following spans carry language `English`.

---

### User Story 3 - Reject incomplete or misleading results (Priority: P2)

The GUI receives a clear ASR failure instead of an incomplete or incorrectly scored Transcript
when an Execution Provider returns malformed Recognition Tokens, generation ends abnormally, or a
pending Normalization Span exceeds its resource limit. Any previous complete JSON Transcript
remains available.

**Why this priority**: Missing token probabilities and partial generations would make transcript
confidence misleading.

**Independent Test**: Drive each invalid provider field, abnormal completion, normalization-span
limit, provider failure, and cancellation boundary; verify failure, cleanup, and preservation of a
previous complete Transcript.

**Acceptance Scenarios**:

1. **Given** a transcript Recognition Token missing its token ID, token text, or log probability,
   **When** the provider result is processed, **Then** the ASR Task fails without replacing a
   previous complete Transcript.
2. **Given** a Recognition Token whose log probability is positive or not a number, **When** it is
   processed, **Then** the ASR Task fails at the provider-response boundary.
3. **Given** provider generation that ends because of a length limit, a tool call, or a stream
   error, **When** the provider result ends, **Then** the ASR Task rejects the partial result.
4. **Given** a pending source span whose UTF-8 representation would exceed 16,384 bytes before the
   next guaranteed normalization boundary, **When** the limit is reached, **Then** the ASR Task
   fails without altering the text to force a boundary.

### Edge Cases

- A successfully recognized Speech Segment contains no transcript Recognition Tokens; the segment
  counts as completed and contributes no JSON entry.
- Every Speech Segment produces no non-empty normalized text; the successful artifact is
  `{"text":[]}` subject to the serialization rule.
- NFKC maps one source code point to several result code points, such as a compatibility ligature;
  the complete normalized result remains one span and has one probability and language value.
- Several source code points compose into one result code point, including a base letter plus a
  combining mark, Hangul Jamo, or halfwidth Katakana plus a voiced mark; all contributing
  Recognition Tokens participate in the span probability.
- NFKC produces empty text for a completed source span; no empty JSON entry is published.
- A provider emits whitespace at a Speech Segment boundary; the exact whitespace is retained.
- Adjacent Speech Segments contain text that could interact under normalization if concatenated;
  each Speech Segment is flushed independently, so no Normalization Span crosses the boundary.
- A provider token contains both provider-defined metadata and transcript text; the adapter removes
  the metadata, retains the transcript substring, and preserves the token's original ID and log
  probability for that substring.
- Transcript text resembles provider markup but is not a provider-defined control sequence; the
  text is retained literally.
- A log probability is negative infinity; the published probability is `0`. A log probability is
  exactly `0`; the published probability is `1`.
- The provider emits a valid Recognition Token with empty token text; the token is ignored and does
  not contribute a probability.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A successful ASR Task MUST publish `transcript.json` in the selected ASR Model's
  Transcript directory instead of publishing or updating `transcript.txt`.
- **FR-002**: The JSON Transcript MUST be an object containing exactly one top-level member named
  `text`, whose value is an array of zero or more Normalization Span entries.
- **FR-003**: Each Normalization Span entry MUST contain exactly three members named `text`,
  `probability`, and `language`, in that order.
- **FR-004**: A span's `text` MUST be its complete NFKC-normalized text. The system MUST omit an
  entry when normalization produces empty text.
- **FR-005**: A span's `probability` MUST equal
  `exp(minimum log_probability among all Recognition Tokens contributing text to the source span)`.
  The published value MUST be a finite JSON number from `0` through `1`, inclusive.
- **FR-006**: A span's `language` MUST be the exact non-empty language value most recently reported
  by the Execution Provider when the span's first code point arrived, or JSON `null` when no
  language has been reported for the current Speech Segment.
- **FR-007**: The Transcript array MUST preserve Segment Manifest order across Speech Segments and
  provider emission order within each Speech Segment.
- **FR-008**: Concatenating every published span's `text` without adding a separator MUST reproduce
  the NFKC-normalized retained transcript text in Speech Segment order. The system MUST preserve
  provider-emitted whitespace exactly and MUST NOT trim Speech Segment edges, normalize
  whitespace, or add word separators.
- **FR-009**: Each provider adapter MUST expose each transcript Recognition Token with its original
  token ID, authoritative Unicode token text, and provider-supplied log probability. Execution
  Provider behavior beneath those emitted values is outside this feature.
- **FR-010**: A transcript Recognition Token's log probability MUST be a real value less than or
  equal to `0`, including negative infinity. Positive values and not-a-number values MUST fail the
  ASR Task at the provider-response boundary. Negative infinity MUST convert to probability `0`.
- **FR-011**: A transcript Recognition Token missing a token ID, Unicode token text, or log
  probability MUST fail the ASR Task. A valid Recognition Token with empty token text MUST be
  ignored.
- **FR-012**: A provider adapter MUST remove only provider-defined metadata, language markers,
  control tokens, and stop markers from transcript text. Text that merely resembles metadata MUST
  remain literal unless the provider contract defines that sequence as control data.
- **FR-013**: When one provider-emitted token contains both provider metadata and transcript text,
  the provider adapter MUST retain the transcript substring with the original token ID and log
  probability.
- **FR-014**: Provider-reported language changes MUST remain ordered relative to Recognition
  Tokens. A language marker MUST contribute no transcript text and no probability.
- **FR-015**: Provider language state MUST begin as unknown for each Speech Segment. A language
  change MUST apply to following recognized code points. If the change occurs while a
  Normalization Span is pending, the pending span MUST retain the language active for its first
  code point.
- **FR-016**: Within each Speech Segment, the system MUST process recognized Unicode code points in
  provider order. Before appending a next code point for which the NFKC normalizer guarantees a
  boundary before that code point, the system MUST normalize and complete the non-empty pending
  source span. The system MUST flush the final pending source span when that Speech Segment ends.
- **FR-017**: A Normalization Span MUST NOT cross a Speech Segment boundary. Provider metadata,
  control sequences, empty Recognition Tokens, and language changes MUST NOT themselves create a
  normalization boundary.
- **FR-018**: Every Recognition Token that contributes one or more code points to a source span
  MUST contribute its log probability to that span. One token MAY contribute its log probability
  to multiple spans, and one span MAY use log probabilities from multiple tokens.
- **FR-019**: The pending source span MUST be limited to 16,384 bytes when encoded as UTF-8. If
  appending a code point would exceed the limit before a guaranteed NFKC boundary, the ASR Task
  MUST fail. The system MUST NOT insert, replace, or remove a character to force a boundary.
- **FR-020**: Recognition Token adaptation and normalization MUST occur synchronously as part of
  ordered Speech Segment recognition. This feature MUST NOT introduce a separate normalization
  thread or an inter-thread Recognition Token queue.
- **FR-021**: Provider completion MUST be explicit and successful. Completion caused by a length
  limit, tool call, provider error, malformed terminal event, or missing successful terminal event
  MUST fail the ASR Task without publishing a partial Transcript.
- **FR-022**: Recognition Context for the next Speech Segment MUST be derived from the concatenated
  normalized span text of completed Speech Segments, without inserted separators, before applying
  the existing context length and leading-fragment rules.
- **FR-023**: The complete Transcript MUST be valid UTF-8 JSON, use a compact representation with
  the member ordering defined by FR-002 and FR-003, and end with exactly one line-feed character.
  Equivalent alternate whitespace or member ordering MUST NOT be published.
- **FR-024**: Publication MUST be atomic. A failed or cancelled ASR Task MUST preserve any previous
  complete `transcript.json` and remove temporary output created by the attempt.
- **FR-025**: Successful Speech Segment progress MUST remain one event per recognized Speech
  Segment, not one event per Recognition Token or Normalization Span.
- **FR-026**: The ASR command, model selection, requested-language handling, Segment Manifest
  preflight, Execution Provider lifecycle, timeouts, status codes, bounded public errors, and
  offline behavior defined by `002-segment-asr` MUST remain unchanged except where this
  specification replaces the provider-result, Recognition Context source, and Transcript
  contracts.
- **FR-027**: Recognition Token timestamps, word boundaries, speaker attribution, alternative
  hypotheses, language detection added by the application, and confidence derived from provider
  internals that the Execution Provider does not expose MUST NOT be part of this feature.

### Key Entities

- **Recognition Token**: One ordered item emitted by an Execution Provider adapter for transcript
  scoring. It carries the provider's token ID, authoritative Unicode token text, and exposed log
  probability. It may contribute to one, several, or no published spans.
- **Normalization Span**: The maximal non-empty sequence of consecutive recognized Unicode code
  points between NFKC boundaries guaranteed by the selected normalizer within one Speech Segment.
  Its published form contains NFKC-normalized text, one derived probability, and one language value.
- **Recognized Language**: The most recent language value reported by an Execution Provider for
  following text within one Speech Segment. It is unknown at the beginning of every segment.
- **Structured Transcript**: The complete JSON result of one successful ASR Task. It owns the
  ordered Normalization Span array and replaces the plain-text Transcript artifact.
- **ASR Task**: One attempt to recognize every Speech Segment in Segment Manifest order, normalize
  Recognition Token text, assemble the Structured Transcript, and publish it atomically.
- **Execution Provider**: The runtime whose adapter removes provider-specific metadata and exposes
  ordered Recognition Tokens, language changes, and an explicit successful completion outcome.
- **Recognition Context**: Text derived from completed Normalization Spans and supplied while
  recognizing the next Speech Segment when the ASR Model supports context.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across controlled inputs covering composition, compatibility expansion, combining
  mark reordering, Hangul Jamo, halfwidth Katakana, punctuation, whitespace, and empty normalized
  text, concatenating published span text matches whole-segment NFKC output in 100% of cases.
- **SC-002**: Across controlled inputs in which tokens and normalization spans have one-to-one,
  one-to-many, and many-to-one relationships, 100% of span probabilities equal the exponential of
  the minimum log probability exposed for their contributing Recognition Tokens.
- **SC-003**: Controlled multilingual inputs demonstrate that 100% of spans carry the language
  active for their first code point, including unknown language, multiple changes within a phrase,
  a change during a pending span, and reset at each Speech Segment.
- **SC-004**: Controlled successful inputs spanning 1–100 Speech Segments prove that every retained
  source code point appears in exactly one published span, no separator is invented, and every
  Speech Segment produces exactly one progress event.
- **SC-005**: A validation matrix covering missing token fields, invalid log probabilities,
  malformed provider metadata, abnormal provider completion, normalization-span overflow,
  provider failure, and cancellation demonstrates that 100% of cases preserve a prior complete
  Transcript and leave no temporary Transcript artifact.
- **SC-006**: Every successful ASR Task produces one JSON document that a standards-conforming JSON
  reader can consume, including the exact empty result `{"text":[]}` when no non-empty spans exist.
- **SC-007**: A controlled real-provider integration demonstrates that the selected Execution
  Provider exposes token IDs, Unicode token text, log probabilities, provider language when
  available, and successful completion, and that the resulting artifact can be reconstructed
  without asserting ASR accuracy or model confidence quality.

## Assumptions

- This feature builds on `002-segment-asr`; requirements not explicitly replaced remain in force.
- The provider adapter, rather than the normalization domain, understands provider-specific
  metadata and control sequences such as Qwen ASR's language prefix and `<asr_text>` marker.
- The Execution Provider exposes complete Unicode token strings. Partial UTF-8 byte processing and
  recovery are outside the application contract for this feature.
- A Recognition Token is the item exposed by the Execution Provider adapter. Sampled tokens or
  probabilities hidden or coalesced inside llama.cpp or another provider are outside this feature.
- NFKC boundary detection and normalization use PyICU's NFKC normalizer and
  `hasBoundaryBefore(code_point)` behavior. Provider token boundaries are not normalization
  boundaries.
- Exact Normalization Span partitioning follows the shipped ICU Unicode data. The invariant is the
  reconstructed normalized text and its token provenance; migration across future ICU data changes
  is outside this feature.
- Existing `transcript.txt` artifacts are not migrated. New successful tasks publish
  `transcript.json`, and maintaining a parallel plain-text artifact is outside this feature.
- Word timestamps, word-level results, forced alignment, diarization, application-provided
  language detection, and probability calibration are outside this feature.
- Third-party ASR accuracy and the semantic quality or calibration of provider probabilities are
  not first-party acceptance criteria. Tests verify application-owned adaptation, normalization,
  scoring, validation, and publication behavior.
