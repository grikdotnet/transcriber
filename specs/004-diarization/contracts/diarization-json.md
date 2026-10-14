# Final Diarization JSON Contract

Destination: `TASK_WORK_DIRECTORY/diarization.json`. This is the only published diarization artifact.

```json
{"schema_version":1,"time_base":{"unit":"sample","sample_rate_hz":16000,"start_inclusive":true,"end_exclusive":true},"intervals":[{"speaker_id":1,"start_sample":160000,"end_sample":192000}]}
```

- Root keys are exactly `schema_version`, `time_base`, `intervals`, in that encoding order.
- Schema version is integer 1. The time-base object has exactly the four constants shown above, in that order. Integers exclude booleans.
- `intervals` is an array; each object has exactly `speaker_id`, `start_sample`, `end_sample`, in that order.
- Speaker IDs are positive integer Nemotron identities. Removal of an identity during masking does not renumber surviving identities.
- Sample bounds satisfy `0 <= start_sample < end_sample <= manifest.audio.total_samples`. Every interval lies wholly inside the exact manifest Speech Segment union.
- Different speakers may overlap. Per speaker, overlapping/touching intervals merge. Sort final intervals by start sample, speaker ID and end sample.
- Encode compact UTF-8 JSON with one final LF. Empty activity uses `"intervals":[]` without changing the schema.

Preserve timestamps in seconds until [fusion](fusion.md) completes. Convert each endpoint with nearest sample rounding, ties-to-even, then clamp, discard collapsed intervals and mask. The sample time base does not claim increased model precision.

Publication is atomic after [cleanup](lifecycle.md). Existing complete bytes survive failed runs. No raw predictions, mappings, added-only intervals, evaluation data, speaker names, mode metadata or transcript content is included.
