# Data Model: Fused Diarization

Names follow [CONTEXT.md](../../CONTEXT.md). Runtime buffers/handles are Infrastructure values, not Domain entities. Serialization is owned by [the artifact contract](contracts/diarization-json.md).

## Domain entities

| Entity | Fields | Relationships / validation |
|---|---|---|
| Speaker Activity | `start_seconds: float`, `end_seconds: float`, `speaker_id: Label` | One interval assigned to one recording-local identity. `Label` is an integer for Nemotron and a string for Community-1; typed predictions do not mix label kinds. Finite times; source intervals are clipped/discarded by the fusion contract. Boolean values are not numeric identities. |
| Nemotron Prediction | ordered activity with positive integer identities | Complete recording output; observed count is the distinct identity set after clipping, before masking. |
| Community-1 Prediction | ordered activity with nonempty string identities | Complete secondary output; label spelling supplies no identity correspondence to Nemotron. |
| Elementary Interval | start/end seconds, active Nemotron identity set, active Community-1 identity set | Derived from ordered boundary events. Multiplicity counters keep repeated same-label rows from creating false overlap. |
| Agreement Matrix | sorted Community-1 labels, sorted Nemotron IDs, nonnegative finite duration cells | Accumulates only mutually single-speaker elementary intervals. Row sums define the support denominator. |
| Speaker Mapping Evidence | proposed pair, paired agreement, row agreement, support, row-maximum flag, acceptance | Recording-local evidence, not confidence. Accepted pairs form a partial injective mapping from strings to integer identities. |
| Fusion Result | fused activity with Nemotron identities | Derived from base preservation and supported gap filling. Added Speaker Activity is the portion contributed in base-empty regions; no intermediary artifact is stored. |
| Sample Speaker Activity | `speaker_id: int`, `start_sample: int`, `end_sample: int` | Final intervals on Canonical Audio. Integer IDs are positive; `0 <= start < end <= total_samples`; no boolean fields; merge/sort after exact masking. |

Pure functions in `domain/diarization.py` validate/clip predictions, sweep active sets, derive evidence, accept assignments, fuse, convert timestamps, intersect the mask, and merge/sort final intervals. A standard typed solver callable supplies assignments without importing a runtime adapter.

## Existing Domain input

Segment Manifest owns Canonical Audio metadata and ordered Speech Segment sample intervals. Reuse its closed-schema codec and invariants. Diarization consumes manifest boundaries and Canonical Audio only; the workflow need not open each Speech Segment WAV to construct the mask. A split boundary is not silence: touching manifest intervals belong to the same permitted union.

## Infrastructure values

- **DecodedAudio**: owning contiguous one-dimensional NumPy float32 samples and total sample count. The sample array is shared by identity between adapters; sample rate is the canonical constant. Empty arrays are permitted. Buffer ownership ends after engine cleanup; neither adapter mutates samples.
- **NemotronInterval / CommunityInterval**: immutable Python-owned start/end seconds and the respective identity type. No ctypes pointers or external Segment objects leave the adapter.
- **NeMo handle holders**: null-initialized native model/stream pointers retained until initialization/cleanup completes. Stream lifetime is contained within model lifetime; output arrays survive until copying completes.
- **Community-1 ownership state**: track constructed model references and whether NCNN Vulkan resources were created. Keep model objects, native arrays and library-stage objects inside Infrastructure.
- **Adapter failures**: translated operation/stage, status when applicable, and copied diagnostic text. Avoid retaining native-resource traceback references. Cancellation and cleanup failures remain distinct from recoverable secondary inference errors.

## Protocol values

- **DiarizationCommand**: absolute work directory plus independently validated NeMo/Vulkan indices; defaults/ranges belong to [CLI](contracts/cli.md).
- **NeMo ABI declarations**: native structs and function signature metadata. They contain no loader or inference calls. Layout/fields belong to [native-runtimes](contracts/native-runtimes.md).
- **DiarizationDocument / wire interval**: closed artifact values built from final Domain intervals by a Composition mapper. Protocol does not import Domain.
- **Progress / Warning / Success / Failure**: typed stage/result values rendered by Controller. Success carries an absolute artifact path; fallback mode is communicated by a warning, not intermediary artifact metadata.

## Task states

```text
validate -> empty mask -> mask -> cleanup -> publish -> success
validate -> decoded audio -> Nemotron -> observed count
  count <= 1 -> mask -> cleanup -> publish -> success
  count >= 2 -> Community-1
    valid result -> fusion -> mask -> cleanup -> publish -> success
    recoverable failure -> warning -> mask base -> cleanup -> publish -> success
any active state -> cancellation/fatal failure -> cleanup -> failure
cleanup failure -> failure (no publication)
publication failure -> failure (previous complete bytes preserved)
```

The detailed state transitions, output messages and ownership order are [lifecycle](contracts/lifecycle.md). The diagram is a map of those transitions, not a second definition of the policy.
