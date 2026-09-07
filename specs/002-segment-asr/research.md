# Research: Segment Speech Recognition

## Decision 1: Keep ASR independent from media preparation

**Decision**: Add an independent ASR task that consumes an existing task work directory,
`manifest.json`, and its referenced Speech Segments. It does not invoke media extraction, VAD, or
segmentation. The GUI owns sequencing and enables ASR only after the separate segmentation command
reports success.

**Rationale**: Recognition can be repeated with another ASR Model without repeating deterministic
media preparation. The existing Segment Manifest already provides ordered, safe, sample-based
references to canonical WAV artifacts.

**Alternatives considered**:

- Continue automatically after `transcriber-prepare`: rejected because it couples model retries to
  unrelated and potentially expensive preparation.
- Make the ASR command orchestrate or monitor segmentation: rejected because command sequencing and
  enablement belong to the GUI.
- Accept arbitrary WAV paths: rejected because it bypasses the validated Segment Manifest contract.

## Decision 2: Model is the public choice; provider is its dependency

**Decision**: The GUI selects a built-in ASR Model by stable ID. A versioned ASR Model Manifest
declares that model's artifact tree, source, capabilities, and Execution Provider ID. A separate
built-in provider registry resolves the provider ID to a fixed shipped executable and adapter.

**Rationale**: Users care which recognition model processes their data. Model/runtime compatibility
is application-owned and must not be exposed as arbitrary combinations. Keeping the manifest
available without weights supports future GUI discovery and download work without adding downloads
to the ASR command.

**Alternatives considered**:

- User-selectable model/provider combinations: rejected because incompatible combinations would be
  representable.
- A user-editable preset file: rejected because provider arguments and paths are application
  internals.
- Search for executables on `PATH`: rejected because an unpinned provider can change protocol and
  parsing behavior.

## Decision 3: Use a stateful Execution Provider session

**Decision**: The application-facing provider seam has lifecycle operations equivalent to
`start(model, segment_root)`, `recognize(segment, context, language) -> text`, and `stop()`.
`RecognizeSegments` starts one provider, recognizes each Speech Segment sequentially, and stops it
in `finally`-equivalent cleanup for success, failure, timeout, and cancellation.

**Rationale**: llama.cpp must load a multi-gigabyte model once and serve multiple segment requests.
Future VibeASR.cpp and ONNX adapters can provide the same behavior without exposing HTTP, command
arguments, or tensors to the service layer.

**Alternatives considered**:

- Start one process per segment: rejected because repeated model loading dominates work and makes
  context continuity harder.
- Keep one external server running: rejected because it transfers lifecycle, ports, and stale
  process state to the user.
- Parallel recognition: explicitly out of scope; context-capable recognition is ordered.

## Decision 4: Use llama.cpp chat completions for Qwen context

**Decision**: The Qwen/llama.cpp adapter starts `vendor/llama-server` on loopback, limits its media
root to the validated `segments/` directory, polls `GET /health`, and posts chat-completion requests.
The system message contains Recognition Context and the user message contains one audio item. An
explicit language uses Qwen's assistant prefill. The adapter decodes the response and strips Qwen's
`language ...<asr_text>` control prefix.

**Rationale**: Qwen3-ASR's reference implementation places contextual text in the system message,
whereas llama.cpp's `/v1/audio/transcriptions` `prompt` field replaces the user instruction. The
chat endpoint supports typed audio content and therefore preserves Qwen's expected message roles.
A local spike with llama.cpp b9890 and the supplied Qwen3-ASR-1.7B Q8_0 artifacts confirmed both
contextual audio recognition and explicit-language assistant prefill. llama.cpp currently returns
the control prefix in response content, so first-party parsing is required.

**Primary sources**:

- [Qwen3-ASR inference implementation](https://github.com/QwenLM/Qwen3-ASR/blob/main/qwen_asr/inference/qwen3_asr.py)
- [Qwen3-ASR parsing and language definitions](https://github.com/QwenLM/Qwen3-ASR/blob/main/qwen_asr/inference/utils.py)
- [llama.cpp multimodal server contract](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- Repository-local `ep/llama.cpp/tools/server/server-chat.cpp` and
  `ep/llama.cpp/tools/server/server-task.cpp`

**Alternatives considered**:

- `/v1/audio/transcriptions` with prior text in `prompt`: rejected because it puts context in the
  wrong model role and replaces the default ASR instruction.
- Link llama.cpp as an in-process library: rejected because it broadens native integration and
  lifecycle scope beyond the shipped executable contract.
- Base64 audio in every request: rejected because `--media-path` permits a smaller local-only request
  while the server is restricted to validated Speech Segments.

## Decision 5: Keep language catalog and matching out of model manifests

**Decision**: An ASR Model Manifest declares only whether explicit language is `optional` or
`required`. The CLI accepts `auto` or a restricted language tag: a 2-8 letter ASCII primary subtag
followed by zero or more hyphen-separated 1-8 character ASCII alphanumeric subtags. Grandfathered
and private-use-only forms are rejected. Provider-specific translation belongs in the adapter and
is not used to advertise models, choose models, or maintain a public supported-language list.

**Rationale**: Language-to-model matching is a separate product capability. The initial Qwen adapter
still must translate common primary language subtags to Qwen's provider-specific canonical labels
when explicit language is requested; this is wire adaptation, not model selection.

**Alternatives considered**:

- Put every supported language in each model manifest: explicitly rejected as out of scope.
- Accept provider-native language names in the CLI: rejected because it leaks provider protocol into
  the GUI contract.

## Decision 6: Assemble one deterministic plain-text transcript

**Decision**: Trim each successful result and join non-empty results with one ASCII space. A
successful empty result advances progress but adds no text or separator. For context-capable models,
the next segment follows FR-009: at most the trailing 2,048 Unicode code points are considered,
Python `str.isspace()` governs leading-fragment removal after a non-whitespace Unicode-code-point
cut: a truncation-created leading fragment through the first Unicode whitespace is discarded,
remaining leading Unicode whitespace is removed, and no following whitespace produces empty
context. Punctuation and hyphens do not create a Unicode-whitespace boundary. Publish
UTF-8 with one trailing newline when non-empty and zero bytes when empty.

**Rationale**: Speech segmentation does not imply paragraph structure. The latest complete words are
the most relevant continuity aid. Plain text is the requested durable artifact; timing and speaker
records belong to later tasks.

**Alternatives considered**:

- One segment per line: rejected because it invents document structure from VAD boundaries.
- Persist segment-level JSON: rejected because timestamps and segment metadata are separate tasks.
- Treat an empty segment result as failure: rejected because non-lexical speech/noise can validly
  produce no text.

## Decision 7: Preflight all local inputs before model loading

**Decision**: Decode and validate the Segment Manifest, safe paths, segment existence, canonical WAV
metadata, duration correspondence, model manifest, model artifact existence, and provider executable
before provider startup. A zero-segment manifest is missing-input failure. Artifact checksums are
recorded in the ASR Model Manifest but are not recalculated for every ASR task.

**Rationale**: Model loading is expensive, and deterministic local errors should be reported first.
Multi-gigabyte checksum verification belongs to the separate installation/download workflow.

**Alternatives considered**:

- Validate each segment immediately before its request: rejected because late deterministic failures
  waste completed recognition and model time.
- Hash all weights on every command: rejected because it adds large avoidable startup I/O.

## Decision 8: Atomic publication with no partial transcript

**Decision**: Accumulate text in memory, stage the encoded result beside its destination, and
atomically replace `transcripts-{model-id}/transcript.txt` only after all segments succeed. Create
the model-specific output directory only when publication is needed. Preserve an existing complete
transcript through every failure and cancellation.

**Rationale**: The GUI should observe either the previous complete result or the new complete result,
never a partial file. The existing `AtomicFileWriter` establishes the repository's publication
pattern.

**Alternatives considered**:

- Append after each segment: rejected because readers can observe partial state and retries need
  recovery semantics.
- Store resumable intermediate recognition: rejected as unrequested complexity.

## Decision 9: Stable progress and bounded errors

**Decision**: Emit one `recognized_segments=N total_segments=M` line after each successful segment
and one final `transcript=ABSOLUTE_PATH` line on success. Provider startup and publication emit no
progress. Public failures remain a single bounded line; provider errors identify model and segment
when applicable and include a quoted, escaped diagnostic excerpt with an explicit truncation marker.
Reuse the existing CLI's status convention: success 0, runtime failure 1, argument failure 2.

**Rationale**: These records are sufficient for GUI progress without mixing provider logs into the
public protocol. Reusing status and line-bounding conventions keeps both commands coherent.

**Alternatives considered**:

- Forward provider logs: rejected because logs are unstable and not a GUI contract.
- Emit startup and publication stages: explicitly rejected.
- Structured JSON event stream: deferred because key/value lines satisfy the confirmed GUI need.

## Decision 10: Bound waits and clean up managed processes

**Decision**: Provider readiness is limited to 60 seconds and each segment request to 180 seconds.
On timeout or cancellation, terminate the provider, wait a short grace period, force termination if
needed, and remove staged output. Simultaneous commands for the same model/task are unsupported and
no lock file is introduced.

**Rationale**: Bounded waits prevent a wedged local server from hanging the GUI. Avoiding persistent
locks also avoids stale-lock recovery after crashes or power loss, a complexity explicitly deferred.

**Alternatives considered**:

- No timeouts: rejected because a provider failure could block indefinitely.
- Output lock file: explicitly deferred as disproportionate to the initial scope.

## Decision 11: Test first-party behavior, not ASR quality

**Decision**: Unit, contract, and integration tests use controlled provider responses to prove
context, ordering, request mapping, parsing, progress, failure handling, and publication. A marked
real-provider semantic test verifies that the shipped provider and supplied artifacts load and cross
the integration boundary; it does not assert transcript words, non-emptiness, WER, language
accuracy, throughput, or other model semantics. Controlled fixtures retain exact Transcript-content
and non-empty assembly assertions.

**Rationale**: Constitution v2.1.0 prohibits tests from asserting third-party model correctness,
accuracy, quality, performance, or internals. The project owns adapter behavior, not Qwen output.

**Alternatives considered**:

- WER threshold against the AMI reference: rejected as a constitution violation.
- Exact Qwen transcript snapshot: rejected because it tests model semantics and is brittle across a
  provider/model revision.
