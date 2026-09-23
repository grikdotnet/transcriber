# T045 Deterministic Quality-Suite Evidence

All commands ran from `/opt/workspaces/transcriber` with
`UV_CACHE_DIR=/tmp/transcriber-uv-cache`.

## Non-real pytest suite

```text
uv run pytest -m "not real_vad"
```

Result: exit 0; 212 collected, 202 selected and passed, 10 real-provider tests deselected.
No selected test was skipped.

## Strict typing

```text
uv run mypy --strict src
```

Result: exit 0; no issues in 22 source files.

## Lint

```text
uv run ruff check src tests
```

Result: exit 0; all checks passed.
