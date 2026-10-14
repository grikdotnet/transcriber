# Diarization CLI Contract

## Invocation

```text
uv run transcriber-diarize TASK_WORK_DIRECTORY
  [--nemo-gpu-index INDEX] [--vulkan-gpu-index INDEX]
```

`TASK_WORK_DIRECTORY` is an existing media preparation directory. Resolve relative invocation paths to absolute paths before constructing the command value. The runtime/model paths are application-relative prerequisites, not caller-relative paths.

| Argument | Default | Validation / effect |
|---|---:|---|
| `--nemo-gpu-index` | 0 | Integer >= -1; pass to NeMo configuration `gpu`. -1 selects CPU; nonnegative indices use ggml enumeration. |
| `--vulkan-gpu-index` | 0 | Nonnegative integer; pass to Community-1 `gpu_index` in NCNN's independent enumeration. |
| `--help` / `-h` | — | Display help and exit 0 without reading inputs or loading engines. |

Malformed integers, out-of-range values, unknown options and positional grammar errors exit 2 before inference. Runtime device availability is not argument validation: unusable Nemotron devices fail; unusable secondary devices follow [lifecycle](lifecycle.md). There is no user speaker-count, model/path, timeout or fallback-enable parameter.

## Public output

| Event | Stream / exact grammar |
|---|---|
| Stage starts | stdout: `stage=validate`, `stage=nemotron`, `stage=community1`, `stage=fusion`, `stage=mask`, `stage=publish` |
| Success | final stdout line `diarization=ABSOLUTE_PATH` |
| Secondary fallback | stderr: `WARNING [community1]: REASON; using Nemotron-only diarization` |
| Failure | stderr: `ERROR [STAGE]: MESSAGE` |

Failure stages are `validate`, `nemotron`, `community1`, `fusion`, `mask`, `publish`, or `cancelled`. Diagnostics rendered in a public line must not contain embedded line breaks. Identify the failed operation in the warning reason. Only stages actually attempted are emitted; progress is flushed so the GUI can observe stage starts. Private native diagnostics must not replace the public result/failure grammar.

| Exit code | Meaning |
|---:|---|
| 0 | Complete fused, Nemotron-only or empty artifact published; help also exits 0. |
| 1 | Common input failure, mandatory runtime failure, cancellation, fusion/mask failure, cleanup failure or publication failure. |
| 2 | Invalid command arguments. |

A directory/manifest/audio error encountered after parsing is a `validate` failure, not an argument-parser failure. Success publishes [diarization.json](diarization-json.md). The command operates offline with preinstalled prerequisites; the GUI owns sequencing and preventing concurrent commands on the same directory.
