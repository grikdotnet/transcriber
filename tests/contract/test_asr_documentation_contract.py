from __future__ import annotations

from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ASR_DOCUMENTS = (
    "specs/002-segment-asr/contracts/cli.md",
    "README.md",
    "docs/cli.md",
    "specs/002-segment-asr/quickstart.md",
)


@pytest.mark.parametrize("relative_path", ASR_DOCUMENTS)
def test_asr_documents_state_the_public_command_contract(relative_path: str) -> None:
    text = " ".join((REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8").split())

    assert "GUI owns" in text
    assert (
        "transcriber-asr TASK_WORK_DIRECTORY --model MODEL_ID [--language auto|LANGUAGE_TAG]"
        in text
    )
    assert "vendor/llama-server" in text
    assert "models/qwen3-asr-1.7b/Qwen3-ASR-1.7B-Q8_0.gguf" in text
    assert "models/qwen3-asr-1.7b/mmproj-Qwen3-ASR-1.7B-Q8_0.gguf" in text
    assert "2-8 letter ASCII primary subtag" in text
    assert "TASK_WORK_DIRECTORY/segments/" in text
    assert "segments/segment-NNNN.wav" in text
    assert "exact index-derived" in text
    assert "resolved filesystem target remains beneath" in text
    assert "target exists" in text
    assert "canonical WAV" in text
    assert "exact manifest duration" in text
    assert "exact frame/sample count" in text
    assert "recognized_segments=1 total_segments=10" in text
    assert "transcript=" in text
    assert "ERROR [STAGE] model=MODEL_ID: MESSAGE" in text
    assert "| `0`" in text
    assert "| `1`" in text
    assert "| `2`" in text
    assert "does not download model artifacts or Execution Providers" in text
    assert "does not build an" in text
