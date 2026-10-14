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
probability of its contributing recognition tokens.
_Avoid_: Unit, character, word

**Transcript**:
The ordered collection of scored normalization spans assembled from speech segments recognized in
Segment Manifest order. Text is derived by concatenating the spans' normalized text rather than
stored as a second source of truth.
_Avoid_: ASR output, transcription result

**Diarization**:
The assignment of speaker identities to speech regions on the complete Canonical Audio timeline.
_Avoid_: Speaker recognition, transcription alignment

**Diarization Task**:
One attempt to assign speaker identities across Canonical Audio and correct the speaker activity using the prepared speech regions.
_Avoid_: Diarization job, transcription task

**Speaker Activity**:
A time interval on Canonical Audio assigned to one recording-local speaker identity. Different speaker identities may have simultaneous activity.
_Avoid_: Utterance, Speech Segment

**Diarization Fusion**:
The combination that preserves the base prediction's active speakers and fills eligible empty regions from a second prediction after aligning speaker identities.
_Avoid_: Voting, speaker averaging

**Speaker Mapping Evidence**:
Agreement between two diarization predictions that supports or rejects a proposed recording-local identity correspondence.
_Avoid_: Speaker confidence, correctness probability

**Added Speaker Activity**:
Speaker activity contributed by the second prediction in regions where the base prediction contains no speaker activity.
_Avoid_: New speaker, corrected speaker
