---
status: superseded by ADR-0002
---

# Correct diarization against prepared speech regions with a collar

Diarization correction uses the persisted Speech Segment intervals, including VAD padding and merged pauses, expanded by an additional 250 ms on each side and clamped to the Canonical Audio timeline. The correction removes speaker activity outside the union of those expanded regions. The goal is to suppress hallucinations in long no-speech areas while retaining tolerance at speech boundaries; a strict frame-level VAD mask was rejected because exact boundary trimming is not the intended behavior.
