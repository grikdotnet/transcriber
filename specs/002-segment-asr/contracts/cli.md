# `transcriber-asr` CLI Contract

## Purpose and sequencing

`transcriber-asr` is independent from `transcriber-prepare`. The GUI enables this command only
after `transcriber-prepare` succeeds, then passes that completed task work directory to ASR. The ASR
command does not start, wait for, monitor, or repeat segmentation.

## Usage

```text
transcriber-asr TASK_WORK_DIRECTORY --model MODEL_ID [--language auto|LANGUAGE_TAG]
```

The command has no subcommands and no model-listing operation.

| Input | Required | Meaning |
|---|---:|---|
| `TASK_WORK_DIRECTORY` | yes | Existing directory created by successful media preparation |
| `--model MODEL_ID` | yes | Stable ID of one built-in ASR Model Manifest: non-empty lowercase ASCII letter-or-digit components separated by a single hyphen or dot, with no leading, trailing, repeated, or adjacent separators |
| `--language VALUE` | no | `auto` by default, or a restricted tag: a 2-8 letter ASCII primary subtag followed by zero or more hyphen-separated 1-8 character ASCII alphanumeric subtags |
| `-h`, `--help` | no | Print usage and exit |

Relative task paths are resolved to absolute paths before crossing the controller boundary.
Grandfathered and private-use-only language forms are outside this command contract.
A model ID that violates the stated grammar is an argument failure with status 2. A syntactically
valid model ID that is not registered reaches application resolution and is a runtime failure with
status 1.

## Input layout

```text
TASK_WORK_DIRECTORY/
├── prepared.wav
├── manifest.json
└── segments/
    ├── segment-0000.wav
    └── ...
```

The command reads the existing schema-v1 Segment Manifest. A valid but empty `segments` array is a
runtime missing-input failure.

The zero-segment missing-input case uses the public failure stage `segment-manifest`.

## Output layout

For model `qwen3-asr-1.7b`:

```text
TASK_WORK_DIRECTORY/
└── transcripts-qwen3-asr-1.7b/
    └── transcript.txt
```

The output directory is exactly one level beneath the task work directory and is derived only from
the validated built-in model ID.

`transcript.txt` is:

- zero bytes when every successfully recognized segment returns empty text;
- otherwise UTF-8 text with segment results joined by one ASCII space and exactly one final LF;
- atomically replaced only after every segment succeeds.

## Progress output

After each successfully processed segment, stdout receives exactly:

```text
recognized_segments=1 total_segments=10
```

`recognized_segments` is one-based completed work and includes successful empty results.
`total_segments` remains constant and equals the Segment Manifest count. There are no provider
startup, readiness, or publication events.

On success, stdout ends with exactly one absolute result path:

```text
transcript=/absolute/task/path/transcripts-qwen3-asr-1.7b/transcript.txt
```

No success line is emitted on failure or cancellation.

## Failure output

Failures use one bounded line on stderr:

```text
ERROR [STAGE] model=MODEL_ID: MESSAGE
```

Segment-specific failures include the zero-based Segment Manifest index:

```text
ERROR [execution-provider] model=qwen3-asr-1.7b segment=3: provider said "ESCAPED_DIAGNOSTIC"
```

The complete rendered line contains at most 1,023 Python Unicode code points excluding its
terminating LF, matching the existing preparation CLI. Every dynamic string value uses JSON string
escaping. Truncation preserves the closing quote and includes the `...[truncated]` marker.

Closed runtime stages:

- `task-directory`
- `segment-manifest`
- `segment-files`
- `asr-model`
- `execution-provider`
- `provider-response`
- `transcript`
- `cancelled`

A missing-prerequisite failure uses stage `asr-model` and this message shape:

```text
missing prerequisites: "PROJECT_RELATIVE_PATH", "PROJECT_RELATIVE_PATH"
```

The provider executable appears first when missing. Missing model artifact paths follow in ASR
Model Manifest declaration order. Every path is project-relative and JSON-string escaped; the
general 1,023-code-point failure-line bound still applies.

## Exit status

| Status | Meaning |
|---:|---|
| `0` | Every Speech Segment was processed and the complete Transcript was published |
| `1` | Runtime failure, timeout, or handled cancellation |
| `2` | Invalid command arguments, model-ID syntax, or language-tag syntax |

## Publication and reruns

- A successful rerun for the same task and model atomically replaces `transcript.txt`.
- Preflight, provider, timeout, response, publication, and cancellation failures leave a previous
  complete transcript unchanged.
- Temporary transcript output is removed after failure.
- Simultaneous invocation for the same task and model is unsupported; no lock or ordering guarantee
  is part of this contract.

## Examples

Automatic language handling:

```text
transcriber-asr /absolute/path/to/task --model qwen3-asr-1.7b
```

Explicit language:

```text
transcriber-asr /absolute/path/to/task --model qwen3-asr-1.7b --language en-GB
```

No command in this contract downloads model artifacts or Execution Providers.
