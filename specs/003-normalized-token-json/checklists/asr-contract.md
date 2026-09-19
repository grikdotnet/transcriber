# ASR Contract Checklist: Normalized Token JSON

**Purpose**: Review the clarity and completeness of requirements for provider token adaptation, NFKC spans, control-prefix removal, and the published JSON Transcript.
**Created**: 2026-09-17
**Feature**: [spec.md](../spec.md)

**Note**: This checklist evaluates requirements wording and coverage. It does not test the implementation.

## Requirement Completeness

- [x] CHK001 Are the mandatory fields and ordering of provider Recognition Tokens fully specified, including which fields are needed for transcript scoring? [Completeness, Spec §FR-008–FR-010]
- [x] CHK002 Is the distinction between requested language as ASR input and the two-field Transcript result explicit? [Completeness, Spec §FR-003, §FR-023]
- [x] CHK003 Does the spec define which provider completion outcomes permit publication and which require failure? [Completeness, Spec §FR-018]
- [x] CHK004 Are the top-level and per-span JSON members, ordering, empty result, and final newline specified without relying on an example alone? [Completeness, Spec §FR-001–FR-004, §FR-020]

## Requirement Clarity

- [x] CHK005 Is “Normalization Span” defined precisely enough to distinguish an ICU-safe source span from a word, grapheme, or provider token? [Clarity, Spec §Key Entities, §FR-013–FR-015]
- [x] CHK006 Is the probability rule explicit for several tokens contributing to one span and one token contributing to several spans? [Clarity, Spec §FR-005, §FR-015]
- [x] CHK007 Is the treatment of negative infinity, zero, positive, missing, and NaN log probabilities unambiguous? [Clarity, Spec §FR-009–FR-010]
- [x] CHK008 Is it clear whether an empty token is ignored before or after provider metadata removal, and whether it contributes any score? [Clarity, Spec §FR-010–FR-012, §Edge Cases]
- [x] CHK009 Is the Qwen control syntax defined sufficiently to distinguish its initial discarded prefix from later literal text resembling `language VALUE<asr_text>`? [Clarity, Spec §FR-011, §Edge Cases]
- [x] CHK010 Does the spec explicitly make exposed Unicode token strings authoritative and state that final assistant content is neither used for reconstruction nor compared for mismatches? [Clarity, Spec §FR-007–FR-008, §Assumptions]

## Requirement Consistency

- [x] CHK011 Are the rule to preserve provider whitespace and the rule to concatenate normalized spans consistent with the context rule across Speech Segment boundaries? [Consistency, Spec §FR-007, §FR-014, §FR-019]
- [x] CHK012 Are the Normalization Span entity, JSON shape, and success criteria consistent in omitting any recognized-language field? [Consistency, Spec §FR-003, §Key Entities, §SC-006]
- [x] CHK013 Are provider-specific metadata removal and literal transcript preservation stated without conflicting interpretations for text that resembles markup? [Consistency, Spec §FR-011–FR-012, §Edge Cases]
- [x] CHK014 Are atomic publication and preservation of a prior artifact consistent across failure, cancellation, and successful rerun requirements? [Consistency, Spec §FR-001, §FR-018, §FR-021]

## Acceptance Criteria Quality

- [x] CHK015 Can each published span's probability be objectively derived from the required provider-exposed log probabilities, including normalization composition and expansion? [Measurability, Spec §FR-005, §SC-002]
- [x] CHK016 Can complete transcript reconstruction be objectively evaluated per Speech Segment without assuming a single whole-task normalization pass? [Measurability, Spec §FR-007, §FR-014, §SC-001]
- [x] CHK017 Is the success criterion for real-provider compatibility framed around exposed contract fields and token-derived artifact reconstruction, without requiring final-content equality, ASR accuracy, or probability calibration? [Measurability, Spec §SC-006, §Assumptions]

## Scenario and Edge Case Coverage

- [x] CHK018 Are requirements present for Qwen prefix removal when speech is code-switched or the prefix says `language None`, without adding a language result field? [Coverage, Spec §FR-003, §FR-011, §Edge Cases]
- [x] CHK019 Are requirements present for source spans that normalize to empty text, empty provider token text, and an entirely empty successful Transcript? [Coverage, Spec §Edge Cases, §FR-004, §FR-010]
- [x] CHK020 Are the exact 16,384-byte threshold and the outcome of crossing it specified without allowing an inserted boundary or altered character? [Edge Case, Spec §FR-016]
- [x] CHK021 Are malformed provider metadata, incomplete completion, provider failure, and cancellation covered with a defined artifact recovery outcome? [Coverage, Spec §User Story 2, §FR-018, §FR-021]

## Dependencies and Assumptions

- [x] CHK022 Is the authoritative source of token text and probability clearly limited to values exposed by the Execution Provider adapter? [Assumption, Spec §FR-008, §Assumptions]
- [x] CHK023 Are the dependency on PyICU's boundary behavior and the effect of changing ICU Unicode data documented at the required level? [Dependency, Spec §FR-013, §Assumptions]
- [x] CHK024 Is the relationship to the earlier `002-segment-asr` contract explicit about replaced and retained behavior? [Consistency, Spec §FR-023, §Assumptions]

## Ambiguities & Conflicts

- [x] CHK025 Does the spec distinguish a successful segment with zero exposed transcript tokens from a present transcript token missing probability data, given that final assistant content is ignored? [Clarity, Spec §FR-010, §FR-025, §Edge Cases]

## Notes

- CHK009 and CHK010 were resolved by the 2026-09-17 clarifications. Qwen's initial prefix alone is metadata; token strings are authoritative without final-content comparison.
- The 2026-09-17 scope change removed recognized-language output and its user story. Requested language remains an ASR input.
- CHK025 was resolved by treating absent `logprobs.content` as zero exposed tokens after successful completion, while rejecting missing fields inside a present transcript token.
- Mark an item complete only after reviewing the requirements text and recording any needed spec change.
