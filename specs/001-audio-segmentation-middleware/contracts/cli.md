# CLI Contract: `transcriber-prepare`

## Invocation

```text
transcriber-prepare SOURCE_MEDIA TASK_WORK_DIRECTORY
  [--max-segment-duration-seconds SECONDS]
```

No subcommands, GUI mode, worker mode, or API mode are part of this delivery.

## Arguments

| Argument | Required | Contract |
|---|---:|---|
| `SOURCE_MEDIA` | yes | Local file path. It is resolved to an absolute path; FFmpeg proves actual audio decoding before task-directory creation. |
| `TASK_WORK_DIRECTORY` | yes | Exact output path. Its parent must exist and be writable; the path itself must not exist. |
| `--max-segment-duration-seconds` | no | Finite number `>= 0.01`; default `30.0`. It is floored to a positive count of 10 ms frames and is an advisory FireRed split target, not a strict output-duration limit. |

Argument parsing or value failure must occur before media validation and before the task directory is created.

## Success output

Exit status: `0`  
Stream: stdout  
Format: exactly four UTF-8 `key=value` lines in this order:

```text
task_work_directory=/absolute/task/path
canonical_audio=/absolute/task/path/prepared.wav
manifest=/absolute/task/path/manifest.json
segment_count=6
```

The paths must be absolute. `segment_count` is a base-10 non-negative integer equal to the manifest array length.

## Failure output

Runtime exit status: `1`  
Argument/usage exit status: `2`  
Stream: stderr  
Runtime format:

```text
ERROR [stage]: actionable message
```

Allowed runtime `stage` values:

- `source-media`
- `task-directory`
- `audio-extraction`
- `firered-model`
- `ncnn-runtime`
- `vad-inference`
- `vad-postprocessing`
- `interval-validation`
- `manifest`
- `segment-files`

Argument errors use `argparse` usage/error formatting and status `2`. A runtime message identifies the relevant failing path, asset, or operation class for its stage. Normal failures must not print a Python traceback. Native stderr may be summarized in the message but must not be echoed as unbounded output.

## Artifact names

```text
TASK_WORK_DIRECTORY/
├── prepared.wav
├── manifest.json
└── segments/
    ├── segment-0000.wav
    ├── segment-0001.wav
    └── ...
```

`manifest.json` is atomically published only after every referenced segment file validates.
