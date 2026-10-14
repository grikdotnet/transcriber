# Research: Fused Diarization

Date: 2026-10-13. Source design: [diarization.md](../../docs/plans/diarization.md). Phase 0 is complete; product choices come from that design and the user's answers.

## Direct native NeMo integration

**Decision:** use `ctypes` with the installed C library at `vendor/nemo-speech/install/lib/libnemo_speech_asr_c.dylib`, pinned source revision `083861c241061562b8ec29eb06d7f6cdc3af8775`. Use the stateful stream API with `v3-offline`, not full-attention `offline_f32`.

**Rationale:** direct sample pointers and native segment arrays avoid engine JSON files and timestamp formatting. The named offline preset supports complete recordings. Set `left_context_frames=-1`: zero would explicitly override the preset's left context. Other geometry overrides use documented keep-preset values.

**Alternatives considered:** executable/JSON invocation was rejected by the user; full-attention inference has a positional-length limit; the low-latency preset was replaced by the preferred offline preset.

Evidence: installed `include/nemo_speech/diar.h`; [pinned header](https://github.com/NVIDIA/NeMo-Speech.cpp/blob/083861c241061562b8ec29eb06d7f6cdc3af8775/include/nemo_speech/diar.h), [C implementation](https://github.com/NVIDIA/NeMo-Speech.cpp/blob/083861c241061562b8ec29eb06d7f6cdc3af8775/src/asr/c_api.cpp), and [geometry definitions](https://github.com/NVIDIA/NeMo-Speech.cpp/blob/083861c241061562b8ec29eb06d7f6cdc3af8775/src/asr/diar/aosc_state.h). Exact signatures/ownership belong to [the native contract](contracts/native-runtimes.md).

## ABI placement and typed injection

**Decision:** Protocol owns native layouts, signature metadata and pure boundary conversion. Infrastructure owns `ctypes.CDLL`, native invocation, output buffers, handles and error retrieval. Composition injects factories, signatures and converters into a generic Infrastructure adapter.

**Rationale:** `architecture/layers.md` and its AST test prohibit Infrastructure imports of Protocol, including type-only imports. Factories/converters supplied through Composition follow the existing FireRed callback seam while preserving the supplied plan's classification. Protocol converters return only boundary values/primitives. Composition constructs immutable first-party Infrastructure results and maps those values into Domain predictions.

**Alternatives considered:** importing Protocol from Infrastructure fails the gate; moving all native declarations into Infrastructure changes the supplied design; a Protocol loader would mix boundary declarations and concrete I/O. An Infrastructure interface implemented in Composition would violate the interface/implementation layer rule. Use standard typed callables for assembly callbacks, not such an interface.

Evidence: `architecture/layers.md`, `tests/architecture/test_layer_dependencies.py`, `infrastructure/firered_ncnn.py` and Composition wiring. Entity assignments are in [plan.md](plan.md).

## One shared decoded audio buffer

**Decision:** Infrastructure reads canonical PCM once through the existing WaveFileReader and owns a contiguous one-dimensional float32 array passed to both engines. Scale little-endian signed PCM16 by `1 / 32768`; pass 16000 Hz to NeMo.

**Rationale:** native pointer lifetime and NumPy memory ownership belong outside Domain. Both engines accept the same mono samples. The zero-sample case needs explicit handling because the existing WAV slice reader rejects empty ranges. Check exact PCM byte count so a truncated WAV fails before inference.

**Alternatives considered:** Community-1 SoundFile loading decodes again; independent segment inference loses the full-recording time line. Do not mark the NumPy array non-writeable without validating third-party acceptance; both adapters treat the shared samples as read-only by contract.

## Community-1 library, bounds and GPU

**Decision:** use the installed `pyannote-ncnn-plda==0.1.0` package, Git revision `34c8982e243eda9e42834ed255067ab727410379`. Call library stages directly with both bounds equal to Nemotron's observed count and with the selected NCNN Vulkan index. Attempt it only on the lifecycle's multi-speaker branch.

**Rationale:** the API accepts a mono 16 kHz float32 array and returns Segment objects, preserving overlap and timestamps in seconds. No soft count hint exists. Equal bounds request a final count capped by usable observations; a valid result with fewer identities remains ordinary input to fusion. NeMo's capacity accessor is not a detected-count accessor.

**Alternatives considered:** isolated Python/CLI/RTTM integration was rejected. Minimum-only or maximum-only bounds do not carry the selected equal-count constraint. CPU retry is outside scope; unusable Vulkan follows automatic Nemotron fallback.

Evidence: sibling repository `pipeline.py`, `models.py`, `audio.py`, and its ADRs on speaker bounds. Runtime assets now exist under `models/pyannote-community1/`, including all eight required files. Earlier missing-assets statements in the installation guide are stale; update that guide during documentation work, without treating file presence as successful inference.

## Dependency resolution and runtime availability

**Decision:** retain existing pins and the existing `tool.uv.override-dependencies` choice of NumPy 2.4.2. Load optional secondary modules and the assignment solver only on branches requiring them.

**Rationale:** the current `pyproject.toml`/`uv.lock` already record the pinned package and override. Runtime absence can still occur in a damaged installation; skip branches must not import NCNN or invoke a GPU. SciPy 1.16.2's solver is used only for actual fusion, with sorted label order.

**Alternatives considered:** downgrade to upstream NumPy 2.3.3 and separate environments were rejected. Eager module loading prevents the agreed skip/fallback paths. No dependency installation or upstream metadata rewrite is needed in this feature.

Evidence: current package/lock files and [installed runtime guide](../../docs/diarization-runtime-setup.md). NeMo uses ggml device indices; this macOS build enables Metal. Community-1 uses a different NCNN Vulkan index space, justifying separate CLI parameters. The existing local Vulkan driver manifest is an installation prerequisite, not application configuration to invent in this feature.

## Resource ownership and cancellation

**Decision:** retain out-handle holders and clean populated handles even if initialization is interrupted; close streams before destroying models. Copy native error text before another call can overwrite it. Copy interval values before releasing native buffers. Release Community-1 model references before process-wide NCNN Vulkan teardown, including partial initialization. Preserve error messages without retaining exception tracebacks that keep native model references alive through teardown.

**Rationale:** native C calls can populate handles before Python observes their successful return. Cleanup functions are void; no native cleanup status must be invented. Wrapper cleanup failures are fatal. `KeyboardInterrupt` and application cancellation require cleanup despite not being ordinary recoverable secondary exceptions.

**Alternatives considered:** cleanup only after full construction leaks partial resources; catching every BaseException as fallback turns cancellation into success. Forced interruption inside a native call is unsupported. The C enum includes cancelled status, but this pinned diarizer has no cancel callback/function; cooperative checks around calls remain necessary.

Evidence: pinned `diar.h`/`c_api.cpp`, Community-1 `cli.py`/`models.py`. [Lifecycle](contracts/lifecycle.md) owns publication and fallback semantics.

## Fusion policy and acceptance oracles

**Decision:** implement the supplied asymmetric gap fill with the user's adapted acceptance policy, then mask in the sample time base. Preserve the documented row-maximum tolerance independently of the adapted duration/support thresholds. Use controlled sweeps/matrices to verify the first-party algorithms and integration fakes to verify invocation and lifecycle.

**Rationale:** reference annotations never participate in production matching. Reported research DER used earlier thresholds and cannot guarantee the adapted policy's accuracy. The current branch has no runnable research fusion script or linked evaluation report to reuse as an independent oracle.

**Alternatives considered:** symmetric voting, assignment retries, many-to-one mapping, reference-driven thresholds and model/reference equality are outside the agreed scope. Assert base active-set preservation before masking, not after intentional removal outside Speech Segments.

## Publication and real checkpoints

**Decision:** reuse AtomicFileWriter behind a diarization publication wrapper; translate its existing `manifest-creation` failure stage to `publish`. Add optional `real_diarization` tests and `--real-diarization-required`, following existing prerequisite conventions.

**Rationale:** changing the common writer's stage risks preparation regressions. Controlled tests cover every lifecycle branch; successful fallback does not prove the secondary engine works. Real checks validate project-owned C calls, library argument/result mapping, and resource ownership, without asserting third-party model accuracy.

**Alternatives considered:** ordinary write_text can expose partial output; claiming full integration from asset presence or GPU discovery would omit the intended inference boundary.

All technical questions needed for design are resolved. Runtime execution remains implementation verification, not an unresolved design choice.
