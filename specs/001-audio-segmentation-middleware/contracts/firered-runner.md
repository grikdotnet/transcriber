# Native Provider Contract: `firered-vad-ncnn`

## Purpose

The first-party native runner integrates the pinned upstream FireRedVAD C++ audio frontend with the supplied CMVN files and non-streaming NCNN weights. It owns only the adaptation, configuration, process protocol, and inference lifecycle around those trusted third-party implementations. It does not recreate or independently validate their signal-processing mathematics, apply speech/silence postprocessing, create task directories, write manifests, or cut segments.

## Invocation

```text
vendor/firered-vad-ncnn \
  --audio /absolute/task/prepared.wav \
  --model-param /absolute/repo/models/firered-vad.ncnn/firered_vad_non_stream.ncnn.param \
  --model-bin /absolute/repo/models/firered-vad.ncnn/firered_vad_non_stream.ncnn.bin \
  --cmvn-means /absolute/repo/models/firered-vad.ncnn/cmvn_means.bin \
  --cmvn-istd /absolute/repo/models/firered-vad.ncnn/cmvn_istd.bin \
  --chunk-max-frames 30000
```

Python supplies absolute paths, invokes without a shell, and captures stdout/stderr separately.

## Input requirements

- `--audio` is readable mono, 16 kHz, signed 16-bit PCM WAV.
- All four model/CMVN files are readable and match the pinned provenance manifest.
- `--chunk-max-frames` is a positive integer; production supplies `30000`.
- Unknown or duplicate options are rejected.

## Successful output

Exit status: `0`  
stdout: exactly one UTF-8 JSON document conforming to [firered-probabilities.schema.json](firered-probabilities.schema.json), followed by one newline.  
stderr: empty unless bounded informational diagnostics are explicitly enabled at build time; production builds keep them disabled.

Probabilities are emitted with enough decimal digits to round-trip the native float value. Array order is chronological. The compiled upstream frontend produces one continuous model-input timeline; the runner performs NCNN inference in chunks of at most 30,000 frames and concatenates chunk outputs before serialization.

Public-contract validations not expressible in JSON Schema:

- `frames.frame_count == len(frames.probabilities)`.
- Every probability is finite.
- NCNN output count equals input feature-frame count.

The runner owns its reported `frame_count`; Python validates only its equality with the serialized probability-array length. Black-box integration tests cover source/build provenance, canonical input handoff, explicit CMVN/model loading, output schema, and reported-count/array-length coherence for ordinary and long input. They do not derive an expected frame count from the audio, assert probability values or ordering, inspect internal chunk boundaries or concatenation, compare expected segmentation, inspect intermediate features, or independently test upstream FFT, filterbank, mel, windowing, normalization, inference, or postprocessing mathematics.

## Failure statuses

| Status | Class | stderr requirement |
|---:|---|---|
| `2` | Invalid arguments | Concise usage or invalid-option message. |
| `3` | Invalid/unreadable audio | Identifies audio validation failure. |
| `4` | Missing/incompatible model or CMVN | Identifies the failing asset class without dumping binary content. |
| `5` | Upstream preprocessing or NCNN inference failure | Identifies the failed native stage. |
| `6` | Output serialization failure | Identifies serialization failure. |

On failure, stdout must be empty so partial JSON cannot be mistaken for valid inference output.

## Versioning

`schema_version` starts at integer `1`. Backward-compatible additions are prohibited for version 1 because both schemas use closed objects. Any wire-shape change therefore increments the version and requires a corresponding Python codec change.
