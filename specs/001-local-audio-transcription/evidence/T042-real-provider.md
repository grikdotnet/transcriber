# T042 Real-Provider Gate Evidence

## RED

Before Service and Controller implementation, the unchanged required command completed with
`7 passed, 3 failed`. All three failures occurred at the intentionally incomplete
`controller.cli.main` boundary; the provider and controlled diagnostic checks passed. This RED
state is also the accepted T037 checkpoint.

## GREEN

```text
UV_CACHE_DIR=/tmp/transcriber-uv-cache uv run pytest --real-vad-required \\
  -m real_vad tests/acceptance/test_sample_workflow.py -q -s
```

Result: exit 0; `10 passed in 0.78s`.

The run printed exactly one compact `REFERENCE_DIAGNOSTIC={...}` line. Its numeric values were
reported only for human diagnosis and did not affect status or artifacts. The passing assertions
cover dependency invocation, coherent public probability output, ordered valid interval adaptation,
and generated WAV/manifest correspondence. They contain no expected model output, reference-boundary
tolerance, supplied-fixture property, or FFmpeg-output assertion.
