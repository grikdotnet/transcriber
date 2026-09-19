# Result Contract Checklist: Normalized Token JSON

**Purpose**: Review requirements quality after removing recognized-language output from the normalized Transcript.
**Created**: 2026-09-17
**Feature**: [spec.md](../spec.md)

**Note**: These questions evaluate the written requirements and design artifacts, not the implementation.

## Requirement Completeness

- [x] CHK001 Are the top-level JSON member and the exact two members of every non-empty span specified, including member order and exclusion of language? [Completeness, Spec §FR-002–FR-003]
- [x] CHK002 Is the requested-language option explicitly retained as ASR input while recognized-language output is excluded? [Completeness, Spec §FR-023]
- [x] CHK003 Are the rules for omitting empty normalized spans and publishing an entirely empty result both documented? [Completeness, Spec §FR-004, §FR-025, §Edge Cases]
- [x] CHK004 Are provider completion outcomes and the treatment of an absent, empty, or malformed token-probability list distinguished? [Completeness, Spec §FR-018, §FR-025]

## Requirement Clarity

- [x] CHK005 Is the Qwen initial `language VALUE<asr_text>` prefix clearly defined as discarded metadata, including `language None`, without a language result value? [Clarity, Spec §FR-011]
- [x] CHK006 Is the treatment of a later language-looking sequence clear enough to preserve literal transcript text? [Clarity, Spec §FR-011, §Edge Cases]
- [x] CHK007 Is the boundary between control-only items and mixed control/transcript items clear about retained text and probability provenance? [Clarity, Spec §FR-010–FR-012]
- [x] CHK008 Is “Normalization Span” defined precisely enough to distinguish a safe NFKC source sequence from a provider token, word, or Speech Segment? [Clarity, Spec §Key Entities, §FR-013–FR-015]
- [x] CHK009 Is the 16,384-byte source-span limit stated with an unambiguous failure outcome and no invented normalization boundary? [Clarity, Spec §FR-016]

## Requirement Consistency

- [x] CHK010 Do the spec, data model, provider contract, and JSON contract consistently exclude recognized-language state, events, and output fields? [Consistency, Spec §FR-003, §FR-011, §Key Entities]
- [x] CHK011 Does the plan consistently omit language-state handling, including its scale/scope description of per-segment resets? [Conflict, Plan §Technical Context, Spec §FR-003]
- [x] CHK012 Are the rules for preserving source whitespace and independently normalizing each Speech Segment consistent with Transcript reconstruction and Recognition Context? [Consistency, Spec §FR-007, §FR-014, §FR-019]
- [x] CHK013 Are exact JSON serialization and atomic replacement requirements consistent between the specification and artifact contract? [Consistency, Spec §FR-020–FR-021]

## Acceptance Criteria Quality

- [x] CHK014 Can each span probability be objectively derived from the minimum exposed log probability when tokens and spans have many-to-one or one-to-many relationships? [Measurability, Spec §FR-005, §FR-015, §SC-002]
- [x] CHK015 Can success be measured for one to 100 Speech Segments without assuming language labels or inserted word separators? [Measurability, Spec §SC-001, §SC-003]
- [x] CHK016 Is the real-provider success criterion limited to exposed token fields, successful completion, and token-derived artifact construction rather than ASR accuracy or final-content equality? [Measurability, Spec §SC-006]

## Scenario and Edge Case Coverage

- [x] CHK017 Are code-switched speech, an initial Qwen language prefix, and transcript text resembling a later prefix covered without implying a language field? [Coverage, Spec §FR-003, §FR-011, §Edge Cases]
- [x] CHK018 Are invalid token fields, abnormal completion, cancellation, and span overflow covered with preservation of a prior complete Transcript? [Coverage, Spec §FR-009–FR-010, §FR-016, §FR-018, §FR-021]

## Notes

- This is a new checklist for the reduced result contract. The earlier `asr-contract.md` and `requirements.md` remain available.
- CHK011 was resolved by removing the stale language-reset phrase from `plan.md`.
- Mark an item complete only after reviewing the written requirements and any cross-artifact findings.
