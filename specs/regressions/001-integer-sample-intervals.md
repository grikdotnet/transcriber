# Regression: Rounded VAD EOF Exceeds Canonical Audio

## Issue

`transcriber-prepare` fails at `interval-validation` when speech continues to the
end of Canonical Audio whose duration is not an exact millisecond:

```console
$ uv run transcriber-prepare fixtures/fabian_cut.16.wav /tmp/transcriber/fabian
ERROR [interval-validation]: validate-intervals: /private/tmp/transcriber/fabian/prepared.wav
```

The Canonical Audio contains `41,871,896` samples. The upstream
`VadPostprocessor.decision_to_segment()` clamps the final Detected Speech
Interval to `2616.9935` seconds, then rounds the timestamp to `2616.994`
seconds. `FireRedPostprocessor` converts that rounded value back to
`41,871,904` samples. Domain validation correctly rejects the final endpoint
because the endpoint exceeds Canonical Audio by 8 samples.

The lossy path is:

```text
41,871,896 samples
-> 2616.9935 seconds
-> 2616.994 seconds
-> 41,871,904 samples
```

## Required Outcome

Map upstream binary frame decisions directly to integer sample positions.
The preparation path must contain no seconds representation, millisecond
rounding, or seconds-to-samples conversion between FireRedVAD decisions and
`SampleInterval` construction.

The existing feature specification is historical input and remains unchanged.
This regression document is the source of truth for the corrective change.

## Design

### Entities and layers

- **Canonical Audio** owns the exact `total_samples` bound.
- **Detected Speech Interval** is a half-open integer sample interval
  `[start_sample, end_sample)` on the Canonical Audio timeline.
- **Speech Segment** remains the Domain-validated artifact derived from a
  Detected Speech Interval.
- The Infrastructure `FireRedPostprocessor` adapter invokes the pinned upstream
  state machine and maps its binary decisions to primitive integer pairs.
- The Service constructs `SampleInterval` entities from those pairs.
- Domain validates positive duration, ordering, non-overlap, and Canonical Audio
  bounds without correcting Infrastructure output.

### Integer mapping

Keep the public `FireRedPostprocessor.process(probabilities,
max_speech_frame, total_samples)` interface and its
`tuple[tuple[int, int], ...]` result unchanged. Replace the call to upstream
`decision_to_segment()` with a private integer mapper over the decisions
returned by upstream `process()`.

Use adapter-local private constants `FRAME_SHIFT_SAMPLES = 160` and
`FRAME_LENGTH_SAMPLES = 400`:

- A transition from silence to speech at decision index `t` starts an interval
  at `t * FRAME_SHIFT_SAMPLES`.
- A transition from speech to silence at decision index `t` ends the interval
  at `t * FRAME_SHIFT_SAMPLES`.
- Speech that remains active through the last decision ends at
  `min(len(decisions) * FRAME_SHIFT_SAMPLES + FRAME_LENGTH_SAMPLES,
  total_samples)`.
- An empty decision sequence produces no intervals.
- Decision values must be the integers `0` or `1`; reject other values at the
  Infrastructure seam.

The pinned files under `third_party/firered-vad` remain byte-for-byte unchanged.
Only the upstream state-machine `process()` method remains part of the adapter's
interface; its presentation-oriented `decision_to_segment()` method is not
called.

## Implementation Plan

### Task 1A: Adapter regression tests — owner W-Adapter-Tests, parallel with Task 1B

Change
`tests/integration/infrastructure/test_firered_postprocessing.py` first:

- Change `test_passes_complete_probabilities_and_exact_settings_once` so
  `FakeUpstream.process()` returns decisions containing two closed speech runs.
  Remove `FakeUpstream.decision_to_segment()`. Assert the exact constructor
  settings, one call containing the complete probability list, no call through
  an upstream timestamp method, and integer intervals calculated from decision
  indexes.
- Rename
  `test_passes_canonical_duration_and_preserves_short_eof_remainder` to
  `test_maps_trailing_speech_to_exact_canonical_audio_end`. Remove the fake
  timestamp method and assert that an all-speech decision sequence ends at the
  supplied `total_samples`, including a Canonical Audio length that is not a
  frame-shift or millisecond boundary.
- Add `test_maps_empty_and_all_silence_decisions_to_no_intervals`.
- Add `test_maps_multiple_closed_speech_runs_to_integer_sample_intervals` with
  decisions such as `[0, 1, 1, 0, 0, 1, 0]`; assert
  `((160, 480), (800, 960))`.
- Add `test_rejects_non_binary_upstream_decisions`, parametrized with a boolean,
  negative integer, integer greater than one, float, and string. Assert a
  `FireRedPostprocessingError` rather than truthiness-based interpretation.
- Keep `test_loads_pinned_upstream_postprocessor_from_its_actual_source`,
  `test_translates_upstream_failures`, and
  `test_rejects_invalid_canonical_sample_count`. These tests require no semantic
  changes and continue protecting provenance and failure translation.

**Acceptance criteria:** The controlled EOF test fails with the current
implementation because the result ends beyond Canonical Audio. The tests
require integer sample positions and contain no seconds-to-samples conversion.

### Task 1B: Workflow regression test — owner W-Workflow-Test, parallel with Task 1A

Add the exact workflow regression to
`tests/acceptance/test_sample_workflow.py`:

- Add `test_non_millisecond_eof_source_completes_cli_workflow` using
  `fixtures/fabian_cut.16.wav` as Source Media and a fresh `tmp_path` Media
  Preparation Task directory.
- Assert CLI status `0`, empty stderr, the existing four-line success output,
  `manifest.audio.total_samples == 41_871_896`, every interval lies within
  Canonical Audio, and the final interval ends at `41_871_896`.
- Assert every generated Speech Segment exists and its WAV frame count equals
  the corresponding Segment Manifest duration.

The acceptance test is the red test that reproduces the reported failure:
before the fix the CLI returns status `1`, reports `interval-validation`, and
does not publish `manifest.json`; after the fix the success assertions pass.

**Acceptance criteria:** The Fabian workflow fails for the documented reason
before implementation and succeeds afterward. The Segment Manifest requires
exactly `41,871,896`, never `41,871,904`, as the final endpoint.

### Task 2: Integer adapter — owner W-Implementation, depends on Tasks 1A and 1B

Change only
`src/transcriber/infrastructure/firered_postprocessing.py` in production code:

- Narrow `_UpstreamPostprocessor` to `__init__()` and
  `process(probabilities) -> list[int]`; remove `decision_to_segment()` from the
  protocol.
- Define adapter-local private `FRAME_LENGTH_SAMPLES = 400` and
  `FRAME_SHIFT_SAMPLES = 160` constants rather than importing Protocol
  constants.
- Add private function
  `_decisions_to_sample_intervals(decisions: list[int], total_samples: int) ->
  tuple[tuple[int, int], ...]`. The function validates binary decisions, scans
  once from left to right, opens an interval on a `0 -> 1` transition, closes
  the interval on a `1 -> 0` transition, and applies the documented trailing
  interval formula when speech remains open.
- Change `FireRedPostprocessor.process()` to pass the complete probabilities to
  upstream `process()` exactly once and return
  `_decisions_to_sample_intervals(decisions, total_samples)`.
- Delete `_seconds_to_sample`, `Decimal`, `total_samples / 16_000`, timestamp
  iteration, and the call to upstream `decision_to_segment()`.
- Preserve `_load_postprocessor`, all seven upstream constructor settings,
  input validation for Split Target and `total_samples`, pinned-source checks,
  and translation of internal failures to `FireRedPostprocessingError`.

No changes are required in:

- `src/transcriber/service/prepare_media.py`: `PostprocessorBoundary` already
  consumes integer pairs and constructs `SampleInterval` entities.
- `src/transcriber/domain/segments.py`: Domain validation already enforces the
  correct Canonical Audio invariants.
- `src/transcriber/composition/application.py`: construction of
  `FireRedPostprocessor` is unchanged.
- `src/transcriber/protocol/firered_probabilities.py`: the required frame
  constants already exist.
- `third_party/firered-vad/**`: vendored code and hashes remain unchanged.
- `specs/001-local-audio-transcription/**`: the feature specification remains
  unchanged.

**Acceptance criteria:** All adapter tests pass; ordinary boundaries remain
frame-shift aligned; trailing speech ends at the exact Canonical Audio bound;
the Domain layer receives integers and performs its existing validation.

### Task 3: Validation — owner W-Validator, depends on Task 2

Run these existing tests without changing their assertions:

- `tests/unit/domain/test_segments.py`: continues proving that valid integer
  intervals are copied unchanged and invalid intervals are rejected.
- `tests/unit/service/test_prepare_media.py`, especially
  `test_complete_service_order_maps_protocol_primitives_to_domain_and_artifacts`
  and `test_invalid_intervals_stop_before_manifest_or_segment_creation`:
  continues proving the Service consumes integer pairs and Domain remains the
  invariant gate.
- `tests/architecture`: continues enforcing layer dependencies.
- `test_pinned_upstream_vad_source_is_unchanged` and
  `test_loads_pinned_upstream_postprocessor_from_its_actual_source`: continue
  proving that vendored files were not edited.

Run the focused suites first:

```console
uv run pytest tests/integration/infrastructure/test_firered_postprocessing.py tests/unit/domain/test_segments.py tests/unit/service/test_prepare_media.py tests/architecture -q
uv run pytest tests/acceptance/test_sample_workflow.py -q --real-vad-required
```

Then run the full test suite and the reported CLI command against a fresh task
directory. Inspect the resulting Segment Manifest and Speech Segment files.

**Acceptance criteria:** The full suite passes; the Fabian preparation command
succeeds; every Detected Speech Interval is ordered, non-overlapping, and within
`41,871,896` samples; generated Speech Segment durations match the Segment
Manifest; the vendored FireRedVAD hashes remain unchanged.

## Test Plan

| File | Test | Required check |
| --- | --- | --- |
| `tests/integration/infrastructure/test_firered_postprocessing.py` | `test_passes_complete_probabilities_and_exact_settings_once` | Exact settings and complete probabilities cross the upstream seam once; returned decisions become integer intervals without calling `decision_to_segment()`. |
| same | `test_maps_empty_and_all_silence_decisions_to_no_intervals` | Empty and all-zero decisions return no intervals. |
| same | `test_maps_multiple_closed_speech_runs_to_integer_sample_intervals` | Transition indexes map with the 160-sample frame shift and preserve order. |
| same | `test_maps_trailing_speech_to_exact_canonical_audio_end` | Trailing frame coverage is capped at exact `total_samples`, including a non-millisecond endpoint. |
| same | `test_rejects_non_binary_upstream_decisions` | Invalid decision types and values become `FireRedPostprocessingError`. |
| same | existing provenance and validation tests | Vendored hashes, source loading, input validation, and exception translation remain unchanged. |
| `tests/acceptance/test_sample_workflow.py` | `test_real_provider_output_is_adapted_without_reinterpretation` | Rename to `test_real_provider_output_maps_to_valid_integer_sample_intervals`; assert integer, ordered, non-overlapping, in-bounds intervals copied unchanged by Domain. |
| same | `test_non_millisecond_eof_source_completes_cli_workflow` | Reproduce the Fabian failure end to end and require exact EOF plus consistent artifacts. |
| `tests/unit/domain/test_segments.py` | existing tests, unchanged | Domain continues rejecting zero-duration, overlapping, out-of-order, and out-of-bounds intervals without clamping. |
| `tests/unit/service/test_prepare_media.py` | existing complete-service and invalid-interval tests, unchanged | Service continues passing primitive integer pairs into Domain and reporting true invalid output as `interval-validation`. |
| `tests/architecture` | existing tests, unchanged | Infrastructure remains isolated and may depend only on Infrastructure; Domain and Service dependency directions remain valid. |

## Assumptions

- The probability protocol remains fixed at a 400-sample frame length and a
  160-sample frame shift for 16 kHz Canonical Audio.
- The upstream state machine continues returning one binary decision per
  probability frame.
- The public CLI, probability document, Segment Manifest, and Domain entity
  interfaces remain unchanged.
- This correction changes Infrastructure adaptation only; it does not change
  speech detection, split behavior, or Domain validation policy.
- Existing feature specification files are not edited or regenerated as part of
  this regression.

## Non-functional constraints

- Keep the corrective change local to the Infrastructure adapter; public CLI,
  protocol, Service, Domain, and Segment Manifest interfaces remain compatible.
- Preserve the pinned FireRedVAD files and their recorded hashes.
- Keep this regression document as the single description of the defect and
  correction. Runtime-facing documentation changes only if implementation
  uncovers a directly contradictory statement outside the existing feature
  specification; the current `README.md` and `docs/` contain none.
- Preserve linear `O(n)` processing over decisions and bounded state independent
  of Canonical Audio duration, excluding the returned interval collection.
