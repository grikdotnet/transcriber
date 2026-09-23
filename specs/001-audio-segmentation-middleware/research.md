# Phase 0 Research: Media Audio Segmentation Middleware

**Date**: 2026-09-04  
**Specification**: [spec.md](spec.md)  
**Research gate**: Complete; no unresolved technical questions remain.

## Decision 1: Python and project tooling

**Decision**: Implement the middleware in Python 3.12 with a `src/` package layout, PEP 621 metadata in `pyproject.toml`, Hatchling as the build backend, and `uv` for environment and lock-file management. Runtime Python code uses the standard library plus the NumPy dependency required by the pinned unchanged upstream FireRedVAD postprocessor. Development dependencies are `pytest`, `mypy`, and `ruff`.

**Rationale**: The repository has no existing Python package to preserve, its local `.venv` is Python 3.12.13, and `uv` is already available. A standard-library CLI (`argparse`, `pathlib`, `subprocess`, `wave`, `json`, `dataclasses`, and `enum`) is sufficient. A `src/` layout makes accidental repository-root imports and architecture violations easier to detect.

**Alternatives considered**:

- System Python 3.9: rejected because it is the host OS Python rather than a project-controlled runtime.
- Click or Typer: rejected because one command does not justify a CLI framework.
- Poetry or PDM: rejected because neither is established in the repository and `uv` already supplies reproducible environment management.
- General-purpose audio frameworks: rejected because they add unnecessary runtime weight around the selected NCNN provider.

## Decision 2: FireRedVAD/NCNN integration boundary

**Decision**: Add a repository-owned C++ executable, built to `vendor/firered-vad-ncnn`, that adapts FireRedVAD's non-streaming NCNN example. Python invokes it with an argument vector and `shell=False`. The executable emits a versioned, full-precision JSON probability document on stdout and diagnostics only on stderr. Python owns artifact orchestration but delegates postprocessing unchanged to the pinned upstream FireRedVAD implementation.

**Rationale**: Upstream builds `test_vad_non_stream` but exposes a shared C API only for streaming VAD. The test executable's human-oriented, four-decimal stdout is not a stable contract and loses precision at the `0.4` speech threshold. A process boundary isolates native crashes and ABI differences while avoiding the fragile macOS ARM Python NCNN wheel. Invoking the pinned upstream postprocessor avoids a second, subtly different first-party state machine.

**Alternatives considered**:

- Parse `test_vad_non_stream` output: rejected because the output is diagnostic, rounded, and not versioned.
- Direct Python NCNN binding: rejected because macOS ARM wheel availability has been unreliable and would bypass the approved pinned upstream C++ frontend integration.
- New non-streaming C ABI plus `ctypes`: viable later, but rejected for this delivery because it introduces an ABI and native-memory lifecycle without a second caller.
- PyTorch FireRedVAD: rejected because the approved execution provider is NCNN.

**Authoritative references**:

- [FireRedVAD NCNN runtime](https://github.com/FireRedTeam/FireRedVAD/tree/main/runtime/ncnn)
- [FireRedVAD non-streaming NCNN example](https://github.com/FireRedTeam/FireRedVAD/blob/main/runtime/ncnn/examples/test_vad_non_stream.cpp)
- [NCNN project](https://github.com/Tencent/ncnn)

## Decision 3: Reproducible native build and provenance

**Decision**: Pin FireRedVAD commit `c30ec49e8cc69642b0ee65362eba11b9d11c6e54` and NCNN tag `20260113` (`e956fbf9bd97fe945df35d736747dc816f8b5f42`). Build a CPU-only static runner during development or packaging, never during a preparation task. The build accepts an explicit `NCNN_ROOT`; it does not download dependencies. Preserve FireRedVAD Apache-2.0 notices and NCNN BSD-3-Clause plus applicable third-party notices. Keep the native provider as a separately licensed executable invoked across a process boundary rather than linking Apache-2.0/NCNN sources into the GPL-2.0 Python middleware; require notice/license review before binary distribution.

**Rationale**: The repository has model files but no NCNN runtime. Pinning source inputs and build flags prevents mutable upstream behavior. A static CPU runner avoids runtime library search paths and does not require Vulkan. The separate-program boundary also preserves clear component provenance in this multi-license repository. Runtime downloading is prohibited by the specification.

**Required build inputs**:

- CMake 3.10 or later and a C++14 compiler.
- NCNN headers and `libncnn.a` from the pinned tag.
- FireRed frontend sources used by the non-streaming example (`fbank`, `fft`, and WAV parsing).
- Optional OpenMP only when the selected NCNN build requires it.

**Pinned local model assets**:

| File | SHA-256 |
|---|---|
| `cmvn_istd.bin` | `0f577337a74e728118f323ea6a64d269de85d29d40f4a60b57cabc960ca13add` |
| `cmvn_means.bin` | `3c80c1c51be7d363f1d64a1d52687df163f60a060384058a83422a22bd80b5c7` |
| `firered_vad_non_stream.ncnn.bin` | `c58c3fae3cc083d7686b8508b08d436791e29da3d2b0c9687b42193eecc671a0` |
| `firered_vad_non_stream.ncnn.param` | `e8857e956f9f8b86a6ef741ab8ab70c83ee5051e2078d7854f1c6618f9dbd0c9` |

**Alternatives considered**:

- Dynamic NCNN linking: rejected because it adds deployment search-path and versioning failures.
- Network download in the CLI or build wrapper: rejected because model and dependency downloading are explicit non-goals.
- Unpinned Homebrew NCNN: acceptable for an exploratory build only, not for acceptance evidence.

## Decision 4: Trusted upstream frontend and model I/O boundary

**Decision**: The runner accepts only mono, 16 kHz, signed 16-bit PCM WAV and compiles/delegates preprocessing to FireRedVAD's pinned supplied C++ frontend. First-party code is limited to adaptation and configuration around that code, the supplied CMVN files, NCNN model loading, inference chunking, and the JSON process boundary. The upstream frontend feeds NCNN blob `in0` as a float32 matrix with `w=80`, `h=T`; the runner reads one probability per chronological frame from `out0`.

**Observable integration contract**:

- The build provenance identifies the pinned upstream frontend sources actually compiled into the runner.
- The input boundary rejects anything other than mono, 16 kHz, signed 16-bit PCM WAV.
- The runner loads the supplied `cmvn_means.bin`, `cmvn_istd.bin`, NCNN parameter, and NCNN weight files from explicit paths.
- The runner's closed public document reports the accepted audio metadata, `frame_count`, and probability array; consumers verify that the reported count equals the array length without deriving an expected count from FireRedVAD's frame mathematics.
- For ordinary and long input, black-box tests verify only that the runner emits one document conforming to the closed wire schema and that its reported `frame_count` equals the probability-array length. They do not assert internal chunk boundaries, concatenation order, probability ordering, or an independently calculated frame count.
- Tests do not assert filterbank coefficients, FFT/mel mathematics, intermediate feature values, or numerical parity with an independently implemented frontend. Those are trusted upstream behavior.

**Rationale**: Compiling the official pinned frontend avoids numerical drift and duplicated signal-processing code. Black-box boundary tests protect the middleware's adaptation and configuration without turning third-party mathematics into first-party maintenance responsibility.

**Alternatives considered**:

- Python reimplementation of the filterbank: rejected because it adds numerical-parity risk and either a NumPy dependency or substantial new signal-processing code.
- `kaldi-native-fbank`: rejected because the approved NCNN runtime already supplies a compatible C++ frontend.

## Decision 5: Trusted upstream FireRed postprocessing

**Decision**: Vendor the postprocessor source from the pinned FireRedVAD revision unchanged and invoke it through a thin Infrastructure adapter. Supply the approved upstream settings (`smooth_window_size=5`, `speech_threshold=0.4`, `min_speech_frame=20`, `min_silence_frame=20`, `merge_silence_frame=201`, `extend_speech_frame=50`, and the command-derived `max_speech_frame`) once over the complete chronological probability sequence. Pass canonical `total_samples / 16000` as the unchanged postprocessor's `wav_dur` so its own EOF handling remains authoritative. The adapter mechanically represents each returned timestamp as its exact 16 kHz integer sample boundary, including an endpoint such as `0.335` seconds as sample `5360`. Domain treats the resulting `SampleInterval` values as authoritative, subject only to middleware-owned ordering, positive-duration, non-overlap, and file-bound validation.

No first-party code duplicates or corrects upstream smoothing, threshold comparison, minimum-frame counting, start compensation, silence merging, extension, or splitting. Exact timestamp-to-sample representation is not a decision algorithm and does not round timestamps to VAD frame boundaries. Tests check the adapter's pinned-source provenance, exact configuration, input/output shapes, representation, ordering, and error translation; they do not assert an independently calculated upstream result at disputed frame-count boundaries.

**Rationale**: This follows the project rule that third-party dependencies are trusted and prevents a subtly divergent first-party postprocessor. Fixture-backed acceptance therefore validates only project-owned handoff, contract, and artifact behavior.

**Alternatives considered**:

- Port or patch the state machine in first-party Python: rejected because it interferes with trusted upstream semantics.
- Add a second duration/minimum-frame filter after upstream postprocessing: rejected because it changes authoritative third-party output.
- Reimplement postprocessing in C++: rejected because it duplicates upstream behavior and creates numerical/semantic drift.

## Decision 6: Advisory split target

**Decision**: Convert `--max-segment-duration-seconds` to `floor(seconds / 0.01)` and pass that positive frame count to the unchanged upstream postprocessor as `max_speech_frame`. The value is configuration supplied at the integration boundary, not a strict manifest-duration invariant or a specification of FireRedVAD's splitting algorithm. Postprocessing output is authoritative; no later first-party splitter replaces or adjusts it.

**Rationale**: This preserves the pinned upstream behavior and the user's explicit acceptance that a final segment may cross the nominal 30-second value without requiring first-party knowledge of FireRedVAD's split mathematics.

**Alternatives considered**:

- Exact split-from-start intervals: rejected by the approved specification revision.
- Search for or replace upstream boundaries in first-party code: rejected because it diverges from the pinned dependency.
- Enforce the target after upstream postprocessing: rejected because the target is advisory.

## Decision 7: Arbitrary-duration policy

**Decision**: Support audio without a product-level duration limit, subject to local memory and disk. The native runner extracts the complete feature timeline, performs NCNN inference in chronological chunks of at most 30,000 frames (300 seconds), concatenates full-precision probabilities, and emits one document. Python applies postprocessing once across the combined timeline.

**Rationale**: This mirrors FireRed's documented non-streaming chunk policy and prevents a fixed model-duration rejection. One postprocessing pass preserves speech/silence decisions across inference-chunk boundaries.

**Alternatives considered**:

- One unbounded NCNN tensor: rejected because memory grows with duration.
- Streaming VAD: rejected because the selected model and requirement are non-streaming.
- Overlapping inference chunks: rejected because it changes official behavior and needs an unrequested reconciliation policy.

**Known limitation**: Inference chunks are independent and the official frontend still materializes the full audio/features. “Arbitrary duration” therefore means no configured duration ceiling, not unbounded memory.

## Decision 8: FFmpeg, WAV slicing, and artifact publication

**Decision**: Resolve `vendor/ffmpeg` from the repository root and invoke it with `shell=False`. Decode one `0:a:0` stream completely to a null sink before creating the work directory, then request extraction of that one stream as `prepared.wav` in mono 16 kHz `pcm_s16le`. The fixed map constrains output to one stream; the CLI exposes no stream selector, and tests validate only first-party invocation/failure boundaries, not FFmpeg behavior, produced sound parameters, or fixture properties. Pass `prepared.wav` directly to the native runner, whose canonical-input contract is authoritative. Use Python's `wave` module later for generated segment slicing and artifact correspondence. Build and validate the manifest entity in memory before segment creation, as required by the logical stage order; write and verify every generated segment before atomically publishing the already-created manifest document.

**Rationale**: Exact argument vectors prove that the configured repository executable is invoked. Python WAV slicing produces sample-exact files without a second media-decoder dependency. Publishing the manifest last prevents an unsuccessful task from claiming missing segment files.

**Selected FFmpeg operations**:

```text
vendor/ffmpeg -nostdin -v error -i SOURCE -map 0:a:0 -f null -
vendor/ffmpeg -nostdin -v error -i SOURCE -map 0:a:0 -vn -ac 1 -ar 16000 -c:a pcm_s16le prepared.wav
```

**Alternatives considered**:

- Select FFmpeg from `PATH`: rejected because FR-002 selects the repository-bundled executable.
- Cut every segment with FFmpeg: rejected because the canonical WAV can be sliced more simply and exactly.
- Publish the manifest before segment files: rejected because a later write failure would leave a false success contract.

## Decision 9: Sample reference is diagnostic-only

**Decision**: Keep `fixtures/sample/prepared.wav` and `fixtures/sample/manifest.json` immutable during this feature. The real-provider acceptance command must require all local dependencies, but it validates only successful project-owned invocation, public probability-document coherence, ordered valid interval adaptation, and generated WAV/manifest correspondence. It emits exactly one compact `REFERENCE_DIAGNOSTIC={...}` line containing actual/reference segment counts and same-index boundary pairs through the shorter list. Each delta is generated minus reference in samples; the pair array is empty when either list is empty, and the counts alone expose unpaired trailing records. Controlled manifests verify this first-party mapping, while the real provider's numeric differences never affect test status or generated output.

**Rationale**: The sample exercises the complete local integration without turning third-party model quality into a first-party contract. The reference remains useful to humans investigating dependency or configuration changes, but it is not an acceptance oracle.

**Alternatives considered**:

- Gate on the reference segment count or boundary tolerance: rejected because it asserts the semantic quality of trusted third-party model output.
- Silently skip the real-provider test: rejected because it would leave the required integration boundary unverified.
- Compare generated WAV bytes with reference WAVs: rejected because project-owned generated-manifest consistency is sufficient.

**Diagnostic policy**: Build and run the native-provider integration before downstream orchestration. Missing dependencies, malformed public output, invalid interval adaptation, or artifact mismatch fail the gate. Differences from the sample reference are reported only for diagnosis and do not fail it.

## Decision 10: Initial platform scope

**Decision**: Target local macOS development and packaging first. The native runner is built for the host architecture. The existing x86_64 `vendor/ffmpeg` is accepted only after its startup check succeeds on the host. Cross-platform binaries are a later feature.

**Rationale**: The current repository includes a macOS FFmpeg provisioning script and no Windows/Linux native assets. The reference host is Darwin ARM64 and currently runs the pinned x86_64 FFmpeg through host translation.

**Alternatives considered**:

- Claim general desktop support: rejected because the repository does not contain corresponding FFmpeg or NCNN artifacts.
- Replace the bundled FFmpeg during this feature: rejected because the specification selects the existing repository-bundled executable.

## Independent research validation

A separate Validator checked both Worker reports against the specification, constitution, `architecture/layers.md`, local assets, and upstream sources. Validation cycle 1 accepted the subprocess boundary, Python 3.12/tooling, trusted upstream frontend and postprocessor integration contracts, 30,000-frame chunking, advisory target, pinned build inputs, CLI shape, and WAV slicing. It required the following corrections, all incorporated above and in the Phase 1 design:

- The pinned upstream postprocessor's minimum-frame semantics are authoritative; the middleware adds no compatibility correction, second threshold, or parallel state machine.
- Speech extension always preserves the input decision-array length for audio shorter than 101 frames.
- Manifest construction remains logically before segment creation, while filesystem publication occurs only after every segment validates.
- The first-party C++ provider is a separate layered subprocess application: NCNN, feature, and WAV adapters are Infrastructure; command/JSON shapes are Protocol; orchestration, assembly, and entry point remain Service, Composition, and Controller respectively. Copied upstream sources and notices remain under architecture-exempt `third_party/` paths.
- The real FireRed fixture is an integration input, while its reference segmentation is diagnostic-only and never a release gate.

**Supervisor decision**: Accept validation cycle 1. Phase 0 passes with no unresolved clarification; the required fixture run gates only project-owned integration behavior.
