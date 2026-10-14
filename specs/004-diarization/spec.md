# Feature Specification: Fused Diarization

**Feature Branch**: `004-diarization` | **Created**: 2026-10-13 | **Status**: Design input extracted from the supplied plan

**Input**: [Diarization design](../../docs/plans/diarization.md), incorporating the user's interview answers and subsequent edits. This specification adds no new product scope.

## User Scenarios & Testing

### User Story 1 — Produce a speaker timeline (P1)

After media preparation, a user runs a separate diarization CLI command and receives speaker activity restricted to the prepared Speech Segments. The GUI can later sequence transcription independently.

**Independent test**: controlled engine predictions and a prepared work directory produce the contracted artifact without running VAD or ASR.

**Acceptance scenarios**:

1. Given overlapping Nemotron activity and an eligible Community-1 gap, when diarization completes, then fusion preserves Nemotron activity, fills the supported gap, and removes output outside Speech Segments.
2. Given matching evidence outside Speech Segments, when identities are aligned, then that evidence participates before final masking.
3. Given a successful rerun, when publication finishes, then the final artifact atomically replaces the previous complete result.

### User Story 2 — Avoid unnecessary secondary inference (P1)

A user with no prepared speech or at most one Nemotron speaker receives a valid result without loading Community-1.

**Independent test**: injected counters prove the appropriate engines and secondary prerequisite checks are untouched.

**Acceptance scenarios**:

1. Given an empty Speech Segment union, when the command runs, then common inputs are validated and empty activity is published without engine prerequisite checks.
2. Given zero or one distinct Nemotron speaker before masking, when Nemotron completes, then its masked activity is published without secondary inference or a fallback warning.

### User Story 3 — Continue after a secondary failure (P2)

A user receives masked Nemotron activity and an explicit warning when Community-1 is unavailable or fails.

**Independent test**: missing optional imports/assets, unavailable GPU, inference exceptions and malformed secondary results each exercise the fallback path.

**Acceptance scenarios**:

1. Given successful multi-speaker Nemotron output and an unusable secondary runtime, when inference is attempted, then the command warns and publishes masked Nemotron activity successfully.
2. Given cancellation, Nemotron failure, fusion failure, cleanup failure or publication failure, when the task exits, then the task fails and previous complete artifact bytes remain unchanged.

### User Story 4 — Select runtime GPUs (P2)

A user selects independent GPU indices for the two engines.

**Independent test**: CLI boundary tests verify defaults, valid index propagation and invalid argument rejection without real hardware.

## Requirements

- **FR-001**: Provide the separate CLI command and status/progress/result grammar in [the CLI contract](contracts/cli.md).
- **FR-002**: Validate the existing Segment Manifest and Canonical Audio; consume the complete recording with one shared decoded sample buffer.
- **FR-003**: Run Nemotron through its supported C ABI using the offline geometry preset and native interval results, as specified by [the native contract](contracts/native-runtimes.md).
- **FR-004**: Follow the empty-mask and zero/one-speaker skip branches in [the lifecycle contract](contracts/lifecycle.md).
- **FR-005**: When secondary inference is needed, call the pinned Community-1 library directly with both speaker-count bounds equal to Nemotron's observed count and the selected Vulkan index.
- **FR-006**: Fuse complete predictions using one-to-one single/single agreement, strongest-candidate acceptance, minimum agreement of 3 seconds and minimum support of 70%, with inclusive comparisons. The support denominator is the Community-1 identity's total single/single agreement. Preserve active Nemotron identities and fill only eligible single-speaker gaps; see [the fusion contract](contracts/fusion.md).
- **FR-007**: Apply the exact prepared Speech Segment union only after fusion and timestamp conversion. Preserve simultaneous speakers and recording-local Nemotron IDs.
- **FR-008**: Publish only the final artifact defined by [the JSON contract](contracts/diarization-json.md).
- **FR-009**: Automatically warn and use masked Nemotron activity for recoverable secondary failures; distinguish valid empty/no-mapping results from failure.
- **FR-010**: Clean up created native resources before atomic publication, including partial initialization. Failure and cancellation preserve previous complete output.
- **FR-011**: Use no fixed inference deadline. Support cooperative cancellation around native calls and library stages; the GUI owns work-directory sequencing.
- **FR-012**: Preserve the existing preparation and Transcript contracts. No runtime/model provisioning, GUI implementation, ASR changes, extra collar, engine CLI intermediates or user speaker-count hint belongs to this feature.

### Key Entities

Canonical Audio, Segment Manifest, Speaker Activity, engine predictions, Speaker Mapping Evidence, final sample intervals and Diarization Task. Fields and relationships are defined in [data-model.md](data-model.md).

### Edge cases

Empty masks/predictions; repeated same-speaker intervals; overlapping speakers; rectangular agreement matrices; threshold boundaries; insufficient Community-1 observations; clipping and collapsed sample intervals; invalid native status/result data; optional import failures; invalid/unavailable GPUs; interruption during partial initialization; cleanup/publication failures.

## Success Criteria

- **SC-001**: Controlled accepted gap fills satisfy the fusion rule and preserve the base active sets before correction; published intervals are wholly inside the exact mask.
- **SC-002**: Controlled skip scenarios prove that no prohibited engine call or secondary prerequisite check occurs.
- **SC-003**: CLI defaults, index validation, output grammar, warnings and all exit paths match their contracts.
- **SC-004**: Injected failures and cancellation never replace previous complete bytes; recorded cleanup ordering satisfies native ownership.
- **SC-005**: Artifact bytes and sample intervals are deterministic for the supported runtime/solver versions, including overlap and empty output.
- **SC-006**: Existing preparation/ASR tests and architecture, lint and type checks pass. Real integration checkpoints prove project-owned native invocation and mapping with supplied assets; missing assets leave those checkpoints incomplete rather than converting fallback into two-engine verification.

## Assumptions

One local recording per task; mono 16 kHz PCM16 Canonical Audio; preinstalled pinned runtimes/assets; recording-local identities; GUI sequencing; sufficient memory for the complete decoded recording. Research accuracy metrics are evidence for an earlier configuration, not guaranteed success criteria for the adapted thresholds.
