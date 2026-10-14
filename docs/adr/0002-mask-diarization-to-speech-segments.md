# Mask diarization to exact Speech Segment intervals

Diarization output is restricted to the union of persisted Speech Segment intervals, with no additional collar. ASR consumes those same Speech Segments, so speaker activity beyond those intervals cannot contribute to the transcription workflow; expanding the mask by 250 ms provides no benefit for that use case. Existing VAD padding and merged pauses inside Speech Segments remain allowed. This decision supersedes ADR-0001; full-recording identity matching and fusion precede masking, so the mask does not change identity evidence.
