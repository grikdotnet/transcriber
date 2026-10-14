# Native Runtime Contract

Supported initial target: the current macOS ARM64 installation. Preinstalled source revisions and dependency evidence are in [research.md](../research.md); this feature installs nothing.

## Shared audio

Infrastructure owns one contiguous one-dimensional `numpy.float32` array, at 16000 samples/second. Decode canonical little-endian PCM16 with `sample / 32768`, preserving exact frame count and finite values. Pass the same owning array to both adapters; treat samples as read-only and retain ownership while native pointers are in use. Empty input is handled without asking the existing slice reader for a zero-length range.

## NeMo C ABI

Library: `vendor/nemo-speech/install/lib/libnemo_speech_asr_c.dylib`. Public header: installed `include/nemo_speech/diar.h`; supported source revision `083861c241061562b8ec29eb06d7f6cdc3af8775`.

Protocol declares native-aligned structs; Infrastructure loads/configures/calls the library. Protocol conversion helpers return Protocol values or primitives only. Composition constructs the provider-neutral Infrastructure intervals and injects struct/config/array factories, signature metadata and result-copy callables. Infrastructure has no source-level import/type reference to Protocol. Use standard typed callables and confine dynamic ctypes symbol handling to the Infrastructure boundary.

| Native struct | Fields in order |
|---|---|
| Model config | `size: size_t`, `model_path: char*`, `gpu: int32_t`, `preset: char*`, then `chunk_frames`, `right_context_frames`, `left_context_frames`, `fifo_frames`, `spkcache_frames`, `update_period_frames`: `int32_t` |
| Segment | `start_time: double`, `end_time: double`, `speaker: int32_t` |
| Segmentation config | `size: size_t`, `onset: float`, `offset: float`, then `pad_onset_sec`, `pad_offset_sec`, `min_gap_sec`, `min_duration_sec`: `double` |

Use `ctypes.c_size_t`, `c_char_p`, `c_int32`, `c_float`, `c_double` and native alignment, not packed structs. Set size prefixes using `ctypes.sizeof`. On the inspected 64-bit ARM ABI, model/segment/segmentation structs have sizes 56/24/48 and alignment 8; these are checkpoint observations, not portable hardcoded sizes.

Model configuration uses the absolute GGUF path `models/Nemotron-3-Diarization.q8_0.gguf`, selected CLI NeMo index, `preset=b"v3-offline"`, `left_context_frames=-1`, and zero for the remaining geometry overrides. Keep encoded strings alive through creation; the native implementation copies configuration. `v3-offline` uses stateful processing of the complete recording; do not use duration-limited `nemo_speech_diar_offline_f32`. Pass null segmentation config to segment accessors to preserve library defaults.

Configure all function `argtypes` and `restype` before calling:

| C function suffix (`nemo_speech_`) | Arguments | Return |
|---|---|---|
| `diar_create` | model-config pointer, model-out handle pointer | status |
| `diar_destroy` | model handle | void |
| `diar_stream_open` | model handle, stream-out handle pointer | status |
| `diar_stream_push_f32` | stream, float pointer, `size_t` sample count, `int32_t` rate | status |
| `diar_stream_finish` | stream | status |
| `diar_segments` | stream, segmentation-config pointer, segment pointer, `size_t` capacity, count-out pointer | status |
| `diar_stream_close` | stream | void |
| `asr_last_error` | none | `char*` |

Handles are `c_void_p`; status is the C status enum represented by `c_int`. Null-initialize out handles and track actual populated values through partial construction and interruption. Model outlives its streams.

Call create → open → push complete audio at 16000 Hz → finish → query count with null output → allocate caller-owned segment array → fetch with capacity → copy Python interval values. A zero count produces empty prediction without requiring a populated segment buffer. Segment count/fetch occurs after finish on one thread, without intervening mutation. Full segments remain available even when a long stream compacts old frame probabilities.

Native intervals preserve double-precision seconds and positive, one-based integer speaker IDs. `diar_num_speakers` describes model capacity; the workflow must derive observed count from valid/clipped segments. No frame-probability output is required.

Status values: 0 success, 1 invalid argument, 2 out of memory, 3 runtime error, 4 cancelled. After failure, copy thread-local `asr_last_error` immediately before another API/cleanup call. Unknown nonzero statuses are runtime failures. Cancelled status/application interruption follows [lifecycle](lifecycle.md), not fallback. The pinned diarization ABI provides no cancellation callback/function.

Keep audio, handle holders and segment buffers alive until the corresponding native calls/copies complete. Cleanup order is defined by [lifecycle](lifecycle.md); void destroy/close functions have no native status to check.

## Community-1 Python library

Package: `pyannote-ncnn-plda==0.1.0`, exposing `diarization.pipeline.Diarizer` from Git revision `34c8982e243eda9e42834ed255067ab727410379`. Models directory: `models/pyannote-community1/`.

Construct with `minimum_speakers=N`, `maximum_speakers=N` and the selected CLI Vulkan index, where N is the Nemotron observed count supplied by the lifecycle. Call the stages `segment`, `extract_embeddings`, `cluster`, `reconstruct` synchronously on the shared audio. Stage objects and external model types stay inside Infrastructure. Each returned Segment's `start`, `end` and `speaker` fields are copied into immutable first-party values; require finite numeric times and nonempty string identities. Clip/discard finite intervals in the pure algorithm rather than confusing out-of-bounds intervals with malformed objects.

Equal bounds request a hard final identity count, capped by usable observations. A valid output with fewer identities remains normal fusion input. Bounds can split/merge groups; mapping evidence still decides which correspondences to accept.

Required assets are segmentation and embedding `.param`/`.bin` files, projection weight/bias `.npy`, `plda.npz`, and `xvec_transform.npz`. Validate needed runtime files rather than the upstream development ONNX inventory. Import the library, NCNN and other dependencies only when this engine is attempted. The existing uv override retains transcriber's NumPy; do not invoke a package resolver or alter environment configuration from the command.

Community-1's NCNN index is independent of NeMo's ggml enumeration. Missing Vulkan binding/device or invalid actual device selection is a recoverable secondary error. Keep the installed Vulkan driver selection as an external prerequisite; the application does not install drivers or create manifests.

The adapter owns model references and process-wide NCNN Vulkan teardown. Track partial initialization, release model references before teardown, and avoid retaining those references through exception tracebacks. No shared models across threads, secondary CPU retry, or intermediary RTTM is used.
