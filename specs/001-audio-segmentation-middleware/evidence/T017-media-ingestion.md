# T017 Media-Ingestion Gate Evidence

## RED

An isolated repository containing the unchanged three boundary tests and test helpers, but no
Infrastructure production package, was executed with Python 3.12 and pytest 9.0.2:

```text
PYTHONPATH=/private/tmp/transcriber-t017-red.YCTJP1/src \
  /opt/workspaces/transcriber/.venv/bin/python -m pytest \
  tests/integration/infrastructure/test_media_ingestion_boundary.py \
  tests/integration/infrastructure/test_ffmpeg.py \
  tests/integration/infrastructure/test_filesystem.py -q
```

Result: exit 2 during collection with exactly three `ModuleNotFoundError` failures for the absent
`transcriber.infrastructure` package. No production adapter was available in the isolated tree.

## GREEN

```text
UV_CACHE_DIR=/tmp/transcriber-uv-cache uv run pytest \
  tests/integration/infrastructure/test_media_ingestion_boundary.py \
  tests/integration/infrastructure/test_ffmpeg.py \
  tests/integration/infrastructure/test_filesystem.py -q
```

Result: exit 0; `19 passed in 0.01s`.

The controlled tests cover exact bundled-FFmpeg argument vectors, `shell=False`, decode-before-create
ordering, exclusive work-directory creation, atomic publication, and missing, unreadable, corrupt,
unsupported, and audio-free source outcomes. They do not execute FFmpeg or inspect extracted audio
or supplied fixture properties.
