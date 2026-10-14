# Nemotron / pyannote gap-fill fusion: step by step

This algorithm preserves Nemotron's predictions and fills selected speech gaps using pyannote. Speaker identities are aligned using agreement between the two predictions. Reference annotations are used only for evaluating the completed output.

Implementation: [prediction_fusion.py](../scripts/prediction_fusion.py). Evaluation: [prediction-fusion-evaluation.md](prediction-fusion-evaluation.md).

## Inputs and outputs

Inputs are the two diarization predictions for the same recording and its full audio duration:

- Nemotron segments: `(start, end, speaker_label)`; this is the base prediction.
- Pyannote segments: `(start, end, speaker_label)`; this supplies candidate gap fills.
- Duration in seconds. Both predictions must use the same time origin and audio channel.

Labels are arbitrary within each system. A pyannote label such as `SPEAKER_00` does not automatically correspond to a Nemotron label such as `speaker_1`.

Outputs are the fused segments, identity-mapping evidence, and the added segments separately. Every output identity belongs to Nemotron's label set.

Default matching thresholds are **3 seconds minimum agreement** and **70% minimum support fraction**. Both comparisons are inclusive. The production plan uses 3 seconds of agreement and 70% support, while preserving strongest-candidate selection. The reported evaluation below used the original 10-second minimum and 80% support; those results do not validate the adapted thresholds.

## Step 1 — Build a shared timeline

Clip every segment to `[0, audio_duration]`, discarding segments with no positive duration after clipping.

Collect the start and end timestamps from both predictions, plus `0` and `audio_duration`. Sort the unique timestamps. Consecutive timestamps define elementary intervals `[start, end)` within which neither system's active speaker set changes.

For each interval, record:

- `N`: the set of active Nemotron labels.
- `P`: the set of active pyannote labels.
- `dt = end - start`: its duration.

An event sweep applies starts and ends at each timestamp. Counters handle overlapping or touching segments that carry the same label; the active count is the number of distinct labels, not the number of RTTM rows.

## Step 2 — Collect speaker-matching evidence

Use only intervals where both systems predict exactly one active speaker: `len(N) == 1` and `len(P) == 1`.

If pyannote predicts label `p` and Nemotron predicts label `n`, add the interval duration to an agreement matrix:

```text
agreement[p, n] += dt
```

Matrix rows represent pyannote labels and columns represent Nemotron labels. Each cell contains seconds of single/single agreement.

Intervals with silence in either system or multiple active labels in either system supply no matching evidence. The matrix therefore aligns identities using mutually predicted single-speaker periods rather than ambiguous overlaps. It does not establish whether those predictions are correct against a reference.

## Step 3 — Propose a one-to-one identity mapping

Apply the Hungarian assignment algorithm to maximize the sum of selected agreement durations.

Each pyannote label can be assigned to at most one Nemotron label, and each Nemotron label to at most one pyannote label. The matrix may be rectangular, so extra labels can remain unassigned.

The selected assignment is a proposal. It still needs to pass the evidence checks in the next step.

## Step 4 — Accept sufficiently supported assignments

For each proposed pair `p -> n`, calculate:

```text
paired_seconds = agreement[p, n]
total_agreement = sum(agreement[p, every Nemotron label])
support_fraction = paired_seconds / total_agreement
```

When there is no agreement, use a support fraction of zero.

Accept the pair only when all three conditions hold:

1. The assigned Nemotron label is a strongest candidate in that pyannote row: its agreement duration is the row maximum. Tied maxima are allowed; the implementation uses a `1e-9` seconds numerical tolerance.
2. `paired_seconds >= 3` seconds.
3. `support_fraction >= 0.70`.

The denominator is **that pyannote label's single/single agreement time**, not all of its predicted speech time. The fraction describes consistency of identity alignment; it is not a calibrated probability of correctness.

For example, 90 seconds paired with `speaker_1` out of 100 seconds of agreement gives a 90% support fraction and passes. A 50/50 split between two Nemotron identities fails even if there is ample total evidence.

Rejected or unassigned labels are excluded from the mapping. The current implementation does not rerun the assignment after rejecting a pair and does not allow several pyannote labels to map to one Nemotron label.

## Step 5 — Preserve every Nemotron-active interval

Traverse the shared timeline again. Whenever `N` is nonempty, copy all active Nemotron labels to the fused output for that interval.

This preserves Nemotron's single-speaker predictions and its simultaneous-speaker predictions. Pyannote does not replace, remove or add a label while Nemotron is active.

## Step 6 — Fill eligible gaps

When `N` is empty, inspect pyannote:

| Nemotron activity | Pyannote activity | Action |
| --- | --- | --- |
| One or more labels | Any | Keep all Nemotron labels |
| None | Exactly one accepted, mapped label | Add its corresponding Nemotron label |
| None | Exactly one unmatched or rejected label | Leave the interval empty |
| None | Two or more labels | Leave the interval empty |
| None | None | Leave the interval empty |

Formally, for interval `I`:

```text
if N is nonempty:
    fused[I] = N
elif P contains exactly one label p and p is accepted:
    fused[I] = {mapping[p]}
    added[I] = {mapping[p]}
else:
    fused[I] = empty
```

The rule uses pyannote's single-speaker prediction as evidence of speech in a Nemotron gap. Actual reference activity could still be silence, one speaker or several speakers.

There is no minimum gap length or minimum added-segment duration. The 3-second threshold applies to identity-matching evidence across the recording, not to an individual gap.

## Step 7 — Merge segments and save evidence

Group the generated segments by Nemotron identity. Merge overlapping or exactly touching intervals with the same identity. Keep positive-duration gaps and transitions between different identities.

Apply the same merging to the added segments separately. Sort the final output by start time, speaker label and end time.

The algorithm returns:

- Fused segments.
- Accepted mapping and per-label evidence: proposed pair, paired seconds, total agreement seconds, support fraction and acceptance result.
- Added segments, enabling inspection of precisely what changed.

The evaluation runner writes the fused RTTM and an additional `.added.rttm` file with timestamps formatted to four decimal places. No extra smoothing, padding or duration filtering is applied by fusion.

## Step 8 — Evaluate the completed prediction

Only after saving the fused RTTM, load the reference annotation and score the output. Reference labels, reference overlap, collars and annotation coverage do not participate in speaker matching or gap filling.

The evaluation checks that every interval originally containing Nemotron activity retains the same active label set. It then computes missed speech, speaker errors, confusion, false alarms and DER using the same scoring conditions as the individual systems.

The matching and fusion use the full recording. UEM limits and boundary collars apply only during evaluation.

## Worked example

Suppose the predictions are:

| Time | Nemotron | Pyannote |
| --- | --- | --- |
| 0–12 s | `N1` | `P2` |
| 12–15 s | Silence | `P2` |
| 15–27 s | `N2` | `P1` |
| 27–30 s | Silence | `P1` |

Single/single evidence gives `P2 -> N1` with 12 seconds support and `P1 -> N2` with 12 seconds support. Each pair has a 100% support fraction, so both pass.

The algorithm fills 12–15 s with `N1` and 27–30 s with `N2`. After merging, the final segments are:

```text
0–15 s:  N1
15–30 s: N2
```

If pyannote instead predicted both `P1` and `P2` inside either gap, that portion would remain empty. If its only label had an ambiguous mapping, the gap would also remain empty.

## Scope of the current algorithm

Matching uses the whole recording, including future predictions. This is an offline algorithm; a streaming version would need to accumulate evidence and decide when to accept or revise identities.

Fusion cannot remove Nemotron's extra speakers, correct its active-speaker identities, recover a speaker missing from Nemotron's label set, or recover gaps where pyannote predicts overlap. It can also add false alarms or incorrect identities when pyannote is wrong or an accepted mapping is wrong.

On the 18 development fixtures, the original rule with a 10-second minimum agreement and 80% support reduced pooled DER from **10.98% to 8.85%** and complete speech misses from **4.99% to 1.82%**, while false alarms increased from **1.94% to 2.53%**. See the evaluation report for per-recording results and scoring denominators.
