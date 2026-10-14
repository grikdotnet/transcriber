# Diarization runtime setup

Date: 2026-10-13. Scope: the user has now authorized installing the runtime prerequisites previously excluded from the diarization implementation task.

Status: S1–S3 complete. Installed paths, source revisions, smoke checks, Vulkan driver selection, and remaining model assets are recorded in [the installation record](../diarization-runtime-setup.md).

## Assumptions

Use the existing Python 3.12 `.venv` on macOS ARM64, preserve transcriber's NumPy pin, and install the selected Community-1 source revision. Model weights are separate from this request. Build the NeMo library and CLI under `vendor/nemo-speech/`.

## Components and relationships

NeMo source, its GGML dependency, native build artifacts, and the Community-1 distribution are external runtime dependencies. Python package requirements and `uv.lock` describe the application environment. Build/installation orchestration is outside the code-layer classification; this setup adds no Domain, Service, Protocol or Controller behavior. Runtime adapters planned in `diarization.md` will consume these installed components later.

## Tasks, acceptance, and verification

| Task | Owner / dependencies | Acceptance criteria; action -> verification |
|---|---|---|
| S1: Native runtime | Root; independent of S2 | Clone pinned NeMo source and submodules, configure/build library and CLI -> verify: build succeeds, CLI help exposes diarization, and the local Nemotron model loads in a smoke run. |
| S2: Python runtime | Root; independent of S1 | Add the pinned Community-1 library and runtime dependencies to the project environment, explicitly override its NumPy metadata pin -> verify: `uv.lock` remains consistent, `.venv` imports NumPy, SciPy, Community-1 and required native modules, and NumPy retains transcriber's version. |
| S3: Installation record | Root; after S1/S2 | Record paths, source revisions, commands and limitations -> verify: record matches installed files and smoke-check evidence. |

S1 and S2 may run in parallel. If delegated, a fresh Worker W1 reports S1 to Validator V1, and Worker W2 reports S2 to Validator V2, with Root as Orchestrator; follow the repository constitution. This run uses Root directly.

## Test plan

Define smoke checks before installation: native CLI availability and real model invocation; Python imports and version inspection; NCNN Vulkan API/device inspection; lockfile consistency. Run the checks after setup. No production behavior changes or model-accuracy tests are involved. If Community-1 weights or Vulkan support are unavailable, report those limitations explicitly rather than claiming complete two-engine inference.
