"""Representative assembled Diarization commands with controlled engine boundaries."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from _pytest.capture import CaptureResult
from numpy.typing import NDArray

from tests.support.diarization import (
    COMMUNITY_PREDICTION,
    NEMOTRON_PREDICTION,
    make_diarization_manifest,
    make_diarization_task_directory,
)
from transcriber.composition import application
from transcriber.controller import diarization_cli
from transcriber.domain.diarization import CommunityPrediction, NemotronPrediction, SpeakerActivity
from transcriber.infrastructure.diarization_provider import RecoverableDiarizationFailure
from transcriber.service.diarize_audio import DiarizeAudio

HEADER = (
    b'{"schema_version":1,"time_base":{"unit":"sample","sample_rate_hz":16000,'
    b'"start_inclusive":true,"end_exclusive":true},"intervals":['
)


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
        for path in root.rglob("*")
    }


def _prepare(
    tmp_path: Path, *, empty_mask: bool = False,
) -> tuple[Path, dict[str, bytes | None]]:
    root = make_diarization_task_directory(
        tmp_path,
        make_diarization_manifest(160000, () if empty_mask else ((60000, 80000), (128000, 160000))),
        [0] * 160000,
    )
    transcript_directory = root / "transcripts-qwen3-asr-1.7b"
    transcript_directory.mkdir()
    (transcript_directory / "transcript.json").write_bytes(
        b'{"text":[{"text":"Preserve this Transcript","probability":1.0}]}\n'
    )
    return root, _snapshot(root)


def _assert_preserved(root: Path, original: dict[str, bytes | None]) -> None:
    current = _snapshot(root)
    assert set(current) == {*original, "diarization.json"}
    assert {
        name: value for name, value in current.items() if name != "diarization.json"
    } == original


def _install_engines(
    monkeypatch: pytest.MonkeyPatch,
    nemotron: Callable[[NDArray[np.float32], int], NemotronPrediction],
    community1: Callable[[NDArray[np.float32], int, int], CommunityPrediction],
) -> None:
    # Keep the real Composition codecs, file validation, service and publication.
    build = application.build_diarization_service

    def controlled_build(**kwargs: Any) -> DiarizeAudio:
        return replace(
            build(**kwargs), nemotron=nemotron, community1=community1,
            solver=lambda _: ((0, 0), (1, 1)),
        )

    monkeypatch.setattr(application, "build_diarization_service", controlled_build)


def _base() -> NemotronPrediction:
    return NemotronPrediction(tuple(SpeakerActivity(*row) for row in NEMOTRON_PREDICTION))


def _assert_public(
    captured: CaptureResult[str], root: Path, stages: tuple[str, ...], warning: str = "",
) -> None:
    assert captured.out == "".join(f"stage={stage}\n" for stage in stages) + (
        f"diarization={root / 'diarization.json'}\n"
    )
    assert captured.err == warning


def test_fused_command_uses_evidence_outside_mask_preserves_overlap_and_replaces_on_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    root, original = _prepare(tmp_path)
    calls: list[str] = []
    shared: list[NDArray[np.float32]] = []
    rerun = False

    def nemotron(samples: NDArray[np.float32], gpu: int) -> NemotronPrediction:
        calls.append("nemotron")
        assert gpu == -1
        assert samples.shape == (160000,) and samples.dtype == np.float32
        assert samples.flags.c_contiguous
        shared[:] = [samples]
        if rerun:
            return NemotronPrediction((SpeakerActivity(0.0, 10.0, 7),))
        # a -> 1 has 3.5 seconds of agreement, all outside the prepared mask.
        # The second identity overlaps identity 1 and continues into the mask.
        return NemotronPrediction((*_base().activity, SpeakerActivity(3.5, 4.5, 2)))

    def community(samples: NDArray[np.float32], count: int, gpu: int) -> CommunityPrediction:
        calls.append("community1")
        assert samples is shared[0] and count == 2 and gpu == 3
        return CommunityPrediction(tuple(SpeakerActivity(*row) for row in COMMUNITY_PREDICTION))

    _install_engines(monkeypatch, nemotron, community)
    arguments = [str(root), "--nemo-gpu-index", "-1", "--vulkan-gpu-index", "3"]
    assert diarization_cli.main(arguments) == 0
    fused = HEADER + (
        b'{"speaker_id":1,"start_sample":60000,"end_sample":64000},'
        b'{"speaker_id":2,"start_sample":60000,"end_sample":72000},'
        b'{"speaker_id":1,"start_sample":72000,"end_sample":80000},'
        b'{"speaker_id":2,"start_sample":128000,"end_sample":160000}]}\n'
    )
    assert (root / "diarization.json").read_bytes() == fused
    _assert_public(capsys.readouterr(), root,
                   ("validate", "nemotron", "community1", "fusion", "mask", "publish"))
    _assert_preserved(root, original)

    rerun = True
    assert diarization_cli.main(arguments) == 0
    assert (root / "diarization.json").read_bytes() == HEADER + (
        b'{"speaker_id":7,"start_sample":60000,"end_sample":80000},'
        b'{"speaker_id":7,"start_sample":128000,"end_sample":160000}]}\n'
    )
    assert calls == ["nemotron", "community1", "nemotron"]
    _assert_public(capsys.readouterr(), root, ("validate", "nemotron", "mask", "publish"))
    _assert_preserved(root, original)


def test_empty_mask_command_validates_inputs_and_publishes_without_engines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    root, original = _prepare(tmp_path, empty_mask=True)

    def forbidden(*args: Any) -> Any:
        pytest.fail("An empty mask must not invoke an engine")

    _install_engines(monkeypatch, forbidden, forbidden)
    assert diarization_cli.main([str(root)]) == 0
    assert (root / "diarization.json").read_bytes() == HEADER + b']}\n'
    _assert_public(capsys.readouterr(), root, ("validate", "mask", "publish"))
    _assert_preserved(root, original)


def test_secondary_failure_command_warns_and_publishes_masked_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    root, original = _prepare(tmp_path)
    calls: list[str] = []

    def nemotron(samples: NDArray[np.float32], gpu: int) -> NemotronPrediction:
        calls.append("nemotron")
        return _base()

    def community(samples: NDArray[np.float32], count: int, gpu: int) -> CommunityPrediction:
        calls.append("community1")
        raise RecoverableDiarizationFailure(stage="community1", operation="model loading")

    _install_engines(monkeypatch, nemotron, community)
    assert diarization_cli.main([str(root)]) == 0
    assert (root / "diarization.json").read_bytes() == HEADER + (
        b'{"speaker_id":1,"start_sample":60000,"end_sample":64000},'
        b'{"speaker_id":2,"start_sample":128000,"end_sample":144000}]}\n'
    )
    assert calls == ["nemotron", "community1"]
    _assert_public(
        capsys.readouterr(), root, ("validate", "nemotron", "community1", "mask", "publish"),
        "WARNING [community1]: model loading failed at community1; "
        "using Nemotron-only diarization\n",
    )
    _assert_preserved(root, original)
