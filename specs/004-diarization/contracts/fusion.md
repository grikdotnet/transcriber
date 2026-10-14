# Fusion and Mask Contract

Policy thresholds are defined by FR-006 in [spec.md](../spec.md). Inputs are two complete predictions on the same Canonical Audio origin, with integer Nemotron IDs and string Community-1 labels. Matching never uses reference annotations.

1. Validate finite times and label types. Clip intervals to `[0, duration_seconds]`; discard nonpositive intervals after clipping. A finite out-of-bounds interval is not a malformed response.
2. Collect all boundaries plus audio start/end, and sweep consecutive half-open intervals. Active sets contain distinct labels; counters handle duplicate/overlapping rows with the same label.
3. When each active set has exactly one label, add elapsed time to `agreement[community_label, nemotron_id]`. Silence and real overlap add nothing. Use the full recording, including evidence outside prepared Speech Segments.
4. Sort labels/IDs and call the pinned Hungarian solver to maximize total agreement. Matrices can be rectangular; assignments are partial and one-to-one. For no relevant labels/evidence, accept no mappings.
5. For each proposed pair, calculate paired seconds, the Community-1 row sum and support (zero for zero denominator). Accept only a row-maximum candidate meeting both inclusive FR-006 thresholds. Preserve the research algorithm's `1e-9` seconds tolerance when testing whether paired agreement equals the row maximum; this tolerance does not relax duration or support thresholds. Do not rerun after rejection or perturb scores to change ties.
6. Where Nemotron is active, copy every active integer identity. Where Nemotron is empty, fill only if Community-1 has exactly one accepted mapped label. Unmatched labels, rejected labels, Community-1 overlaps and mutual silence remain empty. No new identity can be introduced.
7. Merge overlapping/touching intervals per integer identity and sort by start, identity, end. Keep timestamps in seconds throughout matching and fusion.
8. Convert endpoints to samples using nearest ties-to-even rounding, clamp to audio bounds, discard collapsed intervals, and intersect each speaker's activity with the exact union of manifest Speech Segment intervals. Split at excluded gaps. Merge/sort again in the sample time base.

Base-preservation assertions apply before masking. Published output intentionally excludes Nemotron activity outside the permitted union. Touching manifest intervals are one permitted region; segment splitting does not create silence. Existing VAD padding/merged pauses are retained because they belong to the prepared intervals; no extra collar is added.

A count-constrained Community-1 result with fewer identities is valid. Insufficient matching evidence simply accepts no fills. Nemotron zero/one-speaker skips and secondary failure fallback are workflow decisions in [lifecycle](lifecycle.md), not changes to this pure algorithm.
