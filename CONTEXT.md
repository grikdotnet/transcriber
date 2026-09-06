# Media Preparation

This context prepares source media into speech-focused audio artifacts that later transcription capabilities can consume.

## Language

**Media Preparation Task**:
One attempt to transform a source media item into canonical audio and speech segments.
_Avoid_: Job, run, transcription task

**Source Media**:
The user-supplied media item whose audio is being prepared.
_Avoid_: Input file, source file

**Canonical Audio**:
The normalized, complete audio timeline used for speech detection and segment creation.
_Avoid_: Prepared WAV, extracted audio, canonical sound file

**Detected Speech Interval**:
A chronological region of canonical audio identified as speech before it becomes an output artifact.
_Avoid_: Clip, chunk, segment

**Speech Segment**:
A validated, independently consumable portion of canonical audio corresponding to one detected speech interval.
_Avoid_: Chunk, slice

**Segment Manifest**:
The ordered description of the canonical audio and its speech segments, including references to their artifacts.
_Avoid_: Index file, metadata file

**Split Target**:
A preferred speech-segment duration that guides segmentation but does not impose a maximum duration.
_Avoid_: Maximum segment duration, duration limit