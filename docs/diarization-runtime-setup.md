# Installed diarization runtimes

Installed on 2026-10-13, macOS ARM64, Python 3.12.

## NeMo-Speech

Source: `vendor/nemo-speech/`, revision `083861c241061562b8ec29eb06d7f6cdc3af8775` of NVIDIA/NeMo-Speech.cpp, including pinned submodules. CLI version: 0.2.0.

| Component | Installed path |
|---|---|
| CLI | `vendor/nemo-speech/install/bin/nemo-speech` |
| C API library | `vendor/nemo-speech/install/lib/libnemo_speech_asr_c.dylib` |
| Native implementation | `vendor/nemo-speech/install/lib/libnemo_speech_asr.dylib` |
| Public headers | `vendor/nemo-speech/install/include/nemo_speech/` |
| CMake package | `vendor/nemo-speech/install/lib/cmake/NeMoSpeech/` |

The release build enables diarization and Metal acceleration. Diarization uses the shared ASR runtime library, although the transcribe CLI/API surface and TTS are disabled. SentencePiece is built locally from the upstream helper's pinned revision `31646a467d2051eb904e0b45de3a73e91fe1c1e3`, beneath `vendor/nemo-speech/.deps/`; no system package installation was needed.

Rebuild from the existing checkout:

```bash
PATH="$PWD/.venv/bin:$PATH" JOBS=4 \
  bash vendor/nemo-speech/scripts/build_sentencepiece_static.sh
cmake -S vendor/nemo-speech -B vendor/nemo-speech/build \
  -DCMAKE_BUILD_TYPE=Release \
  -DNEMO_SPEECH_BUILD_ASR=OFF -DNEMO_SPEECH_BUILD_TTS=OFF \
  -DNEMO_SPEECH_BUILD_DIAR=ON -DNEMO_SPEECH_BUILD_MIC_CAPTURE=OFF \
  -DGGML_METAL=ON
cmake --build vendor/nemo-speech/build --parallel 4
cmake --install vendor/nemo-speech/build \
  --prefix "$PWD/vendor/nemo-speech/install"
```

Native source and build artifacts are covered by the existing `vendor/` ignore rule. Record the revision above when recreating the checkout.

## Python library and dependencies

The `.venv` contains `pyannote-ncnn-plda==0.1.0`, exposing `diarization.pipeline.Diarizer`. `pyproject.toml` pins the Git source revision `34c8982e243eda9e42834ed255067ab727410379`; `uv.lock` captures its runtime dependencies.

Installed principal versions:

- NumPy 2.4.2
- SciPy 1.16.2
- NCNN 1.0.20260526
- SoundFile 0.13.1
- kaldi-native-fbank 1.22.3
- Ninja 1.13.2, in the development dependency group for the native build

The upstream package metadata requests NumPy 2.3.3. `[tool.uv].override-dependencies` explicitly selects transcriber's NumPy 2.4.2 instead, as requested. The upstream repository and installed distribution metadata are not rewritten. Use `uv` to synchronize this environment; a resolver that ignores the override will report the upstream metadata conflict.

```bash
uv sync --locked
.venv/bin/python -c 'from diarization.pipeline import Diarizer; import numpy, scipy, ncnn, soundfile, kaldi_native_fbank; print(numpy.__version__, scipy.__version__)'
```

During this setup, commands used `UV_CACHE_DIR=/private/tmp/transcriber-uv-cache` because the sandbox cannot write the normal user cache. This does not change where packages are installed.

## NCNN Vulkan on this Mac

The installed NCNN wheel includes Vulkan APIs and a bundled MoltenVK library. Default driver discovery also finds Homebrew's MoltenVK, causing duplicate Objective-C class warnings. The local manifest `.venv/share/vulkan/icd.d/ncnn_moltenvk.json` selects the wheel's driver alone. Use this setting before importing NCNN:

```bash
export VK_DRIVER_FILES="$PWD/.venv/share/vulkan/icd.d/ncnn_moltenvk.json"
```

The manifest contains an absolute path to the bundled library. Recreate it if `.venv` is replaced or the project moves:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
import sys

prefix = Path(sys.prefix)
library = prefix / 'lib/python3.12/site-packages/ncnn/.dylibs/libMoltenVK.dylib'
assert library.is_file(), library
manifest = prefix / 'share/vulkan/icd.d/ncnn_moltenvk.json'
manifest.parent.mkdir(parents=True, exist_ok=True)
manifest.write_text(json.dumps({
    'file_format_version': '1.0.0',
    'ICD': {'library_path': str(library), 'api_version': '1.4.0', 'is_portability_driver': True}
}, indent=2) + '\n')
PY
```

## Verification and remaining assets

- Native build/install and CLI help/version succeeded; the C API library loads through Python `ctypes`.
- A five-second fixture excerpt was processed successfully with the existing Nemotron GGUF on Metal, producing JSON speaker intervals.
- Python dependency imports, a SciPy assignment call, and `uv lock --check` passed. The four existing package-metadata tests passed.
- NCNN Vulkan detected GPU 0, Apple M5, without duplicate driver loading when using the manifest. GPU checks ran outside the Codex sandbox, which does not expose Metal devices.
- Community-1 weights are not installed under `models/pyannote-community1/`. Full Community-1 inference remains unverified until those separate assets are supplied; library installation and GPU discovery are verified.
