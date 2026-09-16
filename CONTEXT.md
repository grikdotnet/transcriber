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

**Recognition Token**:
A provider-emitted ASR item with an exact text fragment and an exposed log probability. A token
can contribute to more than one normalization span, and a normalization span can draw from multiple
tokens.
_Avoid_: Transcript word, normalized unit

**Normalization Span**:
The maximal non-empty sequence of consecutive recognized Unicode code points between guaranteed
NFKC normalization boundaries within one speech segment. Its normalized text carries the minimum
probability of its contributing recognition tokens and the recognized language active for its
first code point.
_Avoid_: Unit, character, word

**Recognized Language**:
The most recent language value reported by an execution provider for following recognized text
within one speech segment. The value is unknown until that speech segment reports a language.
_Avoid_: Requested language, detected language

**Transcript**:
The ordered collection of scored normalization spans assembled from speech segments recognized in
Segment Manifest order. Text is derived by concatenating the spans' normalized text rather than
stored as a second source of truth.
_Avoid_: ASR output, transcription result
