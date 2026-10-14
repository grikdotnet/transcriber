# Diarization Lifecycle Contract

## Input validation

Read and decode the existing closed Segment Manifest. Resolve the task root and use its schema-fixed `prepared.wav` path. Require a regular Canonical Audio file, reject a symlink at that path, and verify that the resolved file remains inside the resolved task root. Validate mono 16 kHz PCM16 properties, exact manifest frame count and complete PCM bytes. Read/decode the complete recording once into the shared float32 buffer described in [native-runtimes](native-runtimes.md). Handle valid zero-sample audio explicitly; no nonempty slice read is required. The workflow need not validate/open individual Speech Segment WAVs to construct the mask.

## Branches

| Condition after common validation | Behavior |
|---|---|
| Empty Speech Segment union | Skip all engine/model/solver prerequisite checks and inference; produce empty final activity. |
| Nonempty union | Run Nemotron, validate/clip its full result, and count distinct IDs in positive-duration intervals before masking. |
| Nemotron count <= 1 | Skip Community-1 checks/imports/inference and fusion; mask base activity with no fallback warning. Repeated rows of one ID count once. |
| Nemotron count >= 2 | Attempt Community-1 with the runtime/count configuration in [native-runtimes](native-runtimes.md). |
| Valid secondary result, including empty or fewer identities | Perform [fusion](fusion.md); no warning merely because mappings are absent. |
| Recoverable secondary failure | Warn and mask Nemotron-only activity. |

Recoverable secondary failures are absent/unloadable package or model assets, unusable NCNN Vulkan, inference exceptions, and malformed returned intervals. Missing secondary prerequisites are checked only on the attempted branch. Loading the solver belongs to that secondary capability check so missing SciPy cannot break skipped branches or become an unclassified fusion error.

Invalid common inputs, Nemotron failures, cancellation, first-party fusion/mask failures, cleanup failures and publication failures are fatal. Do not hide first-party logic errors as secondary fallback. Native NeMo cancelled status and Python/application cancellation follow the fatal cancellation path.

## Ownership and publication

Before publication:

1. Copy native Nemotron intervals into Python-owned values -> verify: no output value depends on a native pointer.
2. Close every created NeMo stream, then destroy its model -> verify: model outlives streams; populated out handles are cleaned even after partial initialization/interruption.
3. Release all Community-1 model references, then call NCNN `close_vulkan()` if that resource was created -> verify: teardown runs after model references are released, including failed construction paths.
4. Release caller-owned native result buffers and shared decoded audio -> verify: neither engine still uses those buffers.
5. Atomically replace `diarization.json` through the existing writer -> verify: new complete bytes become visible only after cleanup succeeds.

Adapters may release their owned native resources immediately after copying results; all cleanup must be complete before publication. On failure/cancellation, run applicable cleanup and preserve previous complete artifact bytes. NeMo destroy/close functions return void; no invented native cleanup status is required. Wrapper-level cleanup exceptions fail the task. Report NeMo handle/result-buffer cleanup failures as `nemotron`, Community-1/Vulkan cleanup failures as `community1`, and shared decoded-audio release failures as `mask`; no new cleanup stage or fallback is introduced. Translate the existing writer's failure to the public `publish` stage without changing shared preparation behavior.

No fixed inference deadline is imposed. Check cancellation before/after native calls, Community-1 stages and before publication. Native calls can defer Python interruption until return. The GUI may terminate the whole CLI process and owns work-directory concurrency. Unique writer temporary files remain private; no engine intermediate files are created.

Public messages, skipped-stage behavior and exit codes belong to [CLI](cli.md). Input and Transcript artifacts are never modified.
