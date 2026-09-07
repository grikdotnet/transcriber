# Local Transcription

This context prepares source media into speech-focused audio artifacts and recognizes their
spoken content as text.

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

**ASR Task**:
One attempt to process every speech segment in a segment manifest with one selected ASR model.
_Avoid_: Recognition job, ASR run

**ASR Model**:
A supported speech-recognition model selected by its stable identity.
_Avoid_: Preset, engine

**ASR Model Manifest**:
The built-in description of an ASR model, its required artifacts, capabilities, source, and
execution provider.
_Avoid_: Preset, model configuration

**Execution Provider**:
A shipped runtime used by an ASR model to recognize speech segments.
_Avoid_: Engine, backend

**Recognition Context**:
Recent transcript text supplied while recognizing the next speech segment.
_Avoid_: Prompt, history

**Transcript**:
The text assembled from speech segments recognized in segment-manifest order.
_Avoid_: ASR output, transcription result
