# Data Model: Segment Speech Recognition

## Relationship overview

```text
ASR Command
  ├── selects one ASR Model Manifest by model_id
  │     └── depends on one Execution Provider registration
  └── identifies one existing Segment Manifest
        └── Domain decoding orders one or more Speech Segments

ASR Task
  ├── owns one Execution Provider Session
  ├── accumulates one Transcript
  ├── derives Recognition Context from that Transcript
  └── publishes one model-specific Transcript Artifact
```

## ASR Command

Validated request crossing from the CLI controller into the application.

The GUI creates this request only after the independent segmentation command succeeds. That GUI
state transition is outside the ASR Task; the command defensively validates the completed artifacts
it receives.

| Field | Type | Rules |
|---|---|---|
| `task_work_directory` | absolute path | Existing directory selected by the caller; must not be created by ASR |
| `model_id` | string | Must match the safe stable-ID grammar and resolve to one built-in model manifest |
| `language` | automatic or restricted language tag | Defaults to automatic; an explicit value must match the specified closed grammar |

Stable model-ID grammar: non-empty lowercase ASCII letter-or-digit components separated by a
single `-` or `.` character; no leading, trailing, repeated, or adjacent separator. This makes
`transcripts-{model_id}` safe by
construction.

The accepted language-tag surface is a closed grammar: a 2-8 letter ASCII primary subtag followed
by zero or more hyphen-separated 1-8 character ASCII alphanumeric subtags. Grandfathered and
private-use-only tags are outside this delivery.

## Segment Manifest

Domain entity decoded from the application's internal `manifest.json` content. Infrastructure reads
the file content without decoding it; Service passes the content to the Domain decoder. The decoder
performs no filesystem operation.

| Field | Type | Rules |
|---|---|---|
| `schema_version` | integer | Exactly `1` |
| `audio` | manifest audio facts | Pure values required by existing preparation behavior |
| `segments` | ordered tuple of Segment records | Non-empty for ASR; ordered by zero-based index |

Each Segment record contains its zero-based index, sample boundaries, `duration_samples`, and the
exact `segments/segment-NNNN.wav` filename. Domain decoding validates the internal schema, ordering,
duration arithmetic, and filename grammar without accessing the filesystem.

## ASR Model Manifest

Versioned built-in wire document describing one selectable ASR Model. It exists in application
resources even when model artifacts are absent.

| Field | Type | Rules |
|---|---|---|
| `schema_version` | integer | Exactly `1` |
| `id` | model ID | Must match its resource filename and stable-ID grammar |
| `display_name` | non-empty string | Human-readable; not used as identity |
| `source_url` | HTTPS URL | Provenance/download source only; ASR never fetches it |
| `execution_provider` | provider ID | Must resolve through the built-in provider registry |
| `capabilities.context` | boolean | Controls whether Recognition Context is supplied |
| `capabilities.language` | enum | Exactly `optional` or `required` |
| `artifacts.root` | safe relative directory | Resolved beneath the repository/application model root |
| `artifacts.files` | role-keyed object | Closed, non-empty object for this model's required file structure |

### Artifact record

| Field | Type | Rules |
|---|---|---|
| `path` | safe relative file path | Must remain beneath `artifacts.root`; unique across roles |
| `sha256` | lowercase hexadecimal string | Exactly 64 characters; installation metadata, not rehashed per ASR task |

The initial Qwen manifest has exactly these artifact roles:

| Role | Relative path | SHA-256 |
|---|---|---|
| `model` | `Qwen3-ASR-1.7B-Q8_0.gguf` | `58e22d0532d4eacaf034cfac17a6fed159f37c41390c710186783be439d1fc57` |
| `audio_projector` | `mmproj-Qwen3-ASR-1.7B-Q8_0.gguf` | `46c1d533af3f354ceb37ce855dbceff7da7fa7cf1e6a523df3b13440bd164c0d` |

Its root is `qwen3-asr-1.7b`, provider ID is `llama-cpp`, context is supported, and language is
optional.

## Execution Provider Registration

Built-in infrastructure registration connecting a provider ID to a fixed shipped path and adapter
factory.

| Field | Type | Rules |
|---|---|---|
| `id` | provider ID | Stable built-in identity |
| `executable` | absolute path | Resolved from the application root, never from host `PATH` |
| `factory` | adapter factory | Creates a fresh session for one ASR Task |

Initial registration:

| ID | Shipped path | Adapter |
|---|---|---|
| `llama-cpp` | `vendor/llama-server` | Qwen-compatible llama.cpp server adapter |

## ASR Task File Boundary

Infrastructure operations used by Service without exposing an aggregate preflight entity:

- `read_manifest_file(task_work_directory) -> bytes`: reads the existing `manifest.json` content
  without decoding it.
- `check_segment_files(task_work_directory, segment_filenames, expected_duration_samples) -> True`:
  checks the complete ordered arrays in one call. Success is exactly `True`. An array-length mismatch
  or the first invalid, missing, replaced, escaping, non-canonical, or duration-mismatched file raises
  one closed typed Infrastructure error that identifies the filename and reason. The operation
  returns no validated-segment collection.
- `publish_transcript(task_work_directory, model_id, transcript_bytes) -> absolute path`: derives
  `transcripts-{model_id}/transcript.txt` and atomically publishes the complete bytes.

Service performs no filesystem operation directly and completes the batch check before starting an
Execution Provider.

Speech Segment files are application-owned temporary artifacts. Mutation by an external actor after
the successful batch check is outside this feature's threat model.

## Recognition Request

Infrastructure value passed to an active Execution Provider Session.

| Field | Type | Rules |
|---|---|---|
| `segment_index` | integer | Zero-based manifest index |
| `audio_path` | absolute path | Speech Segment filename covered by the successful batch check |
| `context` | string | Empty or at most 2,048 Unicode code points |
| `language` | automatic or explicit tag | Already validated against model's required/optional behavior |

## Recognition Result

Project-owned adaptation of a successful provider response.

| Field | Type | Rules |
|---|---|---|
| `text` | string | Provider/model metadata removed; may be empty; service trims outer whitespace |

Detected language, token usage, timestamps, and provider timings are intentionally discarded.

## Transcript

Pure accumulated state owned by the ASR Task.

| Field | Type | Rules |
|---|---|---|
| `parts` | ordered strings | Only non-empty, outer-whitespace-trimmed recognition results |
| `text` | derived string | `parts` joined by one ASCII space |

Operations:

- `append(result_text)`: trim; append only when non-empty.
- `recognition_context(limit=2048)`: return empty when the model does not support context or no text
  exists. Otherwise, return the complete text at or below the limit; above the limit, take the
  trailing Unicode-code-point suffix. Python `str.isspace()` governs leading-fragment removal after
  a non-whitespace Unicode-code-point cut. When the cut falls between non-whitespace code points,
  discard the leading fragment through the first Unicode whitespace; return empty if no such
  whitespace exists. Remove remaining leading Unicode whitespace. Punctuation and hyphens do not
  create a Unicode-whitespace boundary.
- `encode()`: return zero bytes for empty text; otherwise UTF-8 text plus exactly one `\n`.

## ASR Task lifecycle

```text
arguments-validated
  -> model-resolved
  -> input-preflighted
  -> provider-starting
  -> provider-ready
  -> recognizing (repeats once per Speech Segment)
  -> transcript-published
  -> succeeded
```

Any active state may transition to `failed` or `cancelled`. Once provider startup is attempted,
every terminal path passes through provider cleanup. Transcript publication is the only operation
that may replace the durable output.

## Public results

### ASR Success

| Field | Type | Rules |
|---|---|---|
| `transcript` | absolute path | Exact model-specific transcript path |
| `recognized_segments` | integer | Equals non-zero manifest segment count, including empty results |

### ASR Failure

| Field | Type | Rules |
|---|---|---|
| `stage` | closed string enum | One documented failure stage |
| `message` | non-empty string | Application-owned explanation |
| `model_id` | model ID | Present after command validation |
| `segment_index` | optional integer | Present for segment-specific provider failures |
| `provider_diagnostic` | optional string | Present only when quoting provider-originated failure text |

Failure stages:

- `task-directory`
- `segment-manifest`
- `segment-files`
- `asr-model`
- `execution-provider`
- `provider-response`
- `transcript`
- `cancelled`

## Invariants across entities

1. A successful ASR Task has processed every Speech Segment exactly once and in manifest order.
2. Progress count equals the number of completed recognition calls, not the number of non-empty
   transcript parts.
3. Recognition Context is derived only from already accumulated Transcript text.
4. A model with `context=false` always receives empty Recognition Context.
5. A model with `language=required` never starts with automatic language handling.
6. A durable Transcript is published only after all recognition calls and provider responses
   succeed.
7. No model or provider source URL is contacted by the ASR Task.
