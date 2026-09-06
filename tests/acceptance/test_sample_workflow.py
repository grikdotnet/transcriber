from __future__ import annotations

import json
import socket
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import RealVadPaths, enforce_real_vad_prerequisites
from tests.support.process import FakeCompletedProcess, FakeProcessRunner
from transcriber.controller import cli
from transcriber.domain.audio import CanonicalAudio
from transcriber.domain.segments import SampleInterval, convert_sample_intervals
from transcriber.infrastructure.firered_ncnn import FireRedNcnnFailure, FireRedNcnnProcess
from transcriber.infrastructure.firered_postprocessing import FireRedPostprocessor
from transcriber.infrastructure.process import CompletedProcessData, SubprocessRunner
from transcriber.infrastructure.wave_files import WaveFileReader
from transcriber.protocol.firered_probabilities import decode_probability_document
from transcriber.protocol.manifest import ManifestSegment, decode_manifest

pytestmark = pytest.mark.real_vad


class RecordingProcessRunner:
    def __init__(self) -> None:
        self._delegate = SubprocessRunner()
        self.calls: list[tuple[tuple[str, ...], bool]] = []

    def run(
        self, argv: Sequence[str], *, shell: bool = False
    ) -> CompletedProcessData:
        command = tuple(argv)
        self.calls.append((command, shell))
        return self._delegate.run(command, shell=shell)


def _reference_diagnostic(
    actual: Sequence[ManifestSegment],
    reference: Sequence[ManifestSegment],
) -> str:
    paired_boundary_deltas = [
        {
            "index": index,
            "start_delta_samples": actual_segment.start_sample
            - reference_segment.start_sample,
            "end_delta_samples": actual_segment.end_sample - reference_segment.end_sample,
        }
        for index, (actual_segment, reference_segment) in enumerate(
            zip(actual, reference, strict=False)
        )
    ]
    payload = {
        "actual_segment_count": len(actual),
        "reference_segment_count": len(reference),
        "paired_boundary_deltas": paired_boundary_deltas,
    }
    return f"REFERENCE_DIAGNOSTIC={json.dumps(payload, separators=(',', ':'))}"


def _segment(index: int, start_sample: int, end_sample: int) -> ManifestSegment:
    return ManifestSegment(
        index=index,
        start_sample=start_sample,
        end_sample=end_sample,
        duration_samples=end_sample - start_sample,
        path=f"segments/segment-{index:04d}.wav",
    )


def _segments_from_reference(payload: Mapping[str, Any]) -> tuple[ManifestSegment, ...]:
    records = payload["segments"]
    assert isinstance(records, list)
    return tuple(
        _segment(index, int(record["start_sample"]), int(record["end_sample"]))
        for index, record in enumerate(records)
    )


def _assert_diagnostic_shape(line: str) -> None:
    prefix = "REFERENCE_DIAGNOSTIC="
    assert line.startswith(prefix)
    payload = json.loads(line.removeprefix(prefix))
    assert set(payload) == {
        "actual_segment_count",
        "reference_segment_count",
        "paired_boundary_deltas",
    }
    assert isinstance(payload["actual_segment_count"], int)
    assert isinstance(payload["reference_segment_count"], int)
    assert isinstance(payload["paired_boundary_deltas"], list)
    for pair in payload["paired_boundary_deltas"]:
        assert set(pair) == {
            "index",
            "start_delta_samples",
            "end_delta_samples",
        }
        assert all(isinstance(value, int) for value in pair.values())


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_connection(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the local preparation workflow must not use the network")

    monkeypatch.setattr(socket, "create_connection", reject_connection)
    monkeypatch.setattr(socket.socket, "connect", reject_connection)


def test_required_mode_fails_for_missing_provider_prerequisites(tmp_path: Path) -> None:
    paths = RealVadPaths.from_repository(tmp_path / "missing-repository")

    with pytest.raises(pytest.fail.Exception, match="required real VAD prerequisite"):
        enforce_real_vad_prerequisites(paths, required=True)


def test_malformed_provider_output_fails_at_probability_decode_boundary() -> None:
    paths = RealVadPaths.from_repository(Path(__file__).resolve().parents[2])
    process = FireRedNcnnProcess(
        paths.runner,
        paths.model_directory,
        FakeProcessRunner([FakeCompletedProcess(stdout="not-json")]),
        decode_probability_document,
    )

    with pytest.raises(FireRedNcnnFailure) as raised:
        process.run(paths.sample)

    assert raised.value.stage == "speech-detection"
    assert raised.value.operation == "decode-probabilities"


def test_real_provider_output_is_adapted_without_reinterpretation(
    real_vad_paths: RealVadPaths,
) -> None:
    runner = RecordingProcessRunner()
    process = FireRedNcnnProcess(
        real_vad_paths.runner,
        real_vad_paths.model_directory,
        runner,
        decode_probability_document,
    )

    document = process.run(real_vad_paths.sample)
    upstream_intervals = FireRedPostprocessor().process(
        document.frames.probabilities,
        max_speech_frame=3_000,
        total_samples=document.audio.total_samples,
    )
    segments = convert_sample_intervals(
        tuple(SampleInterval(start, end) for start, end in upstream_intervals),
        CanonicalAudio(document.audio.total_samples),
    )

    assert len(runner.calls) == 1
    argv, shell = runner.calls[0]
    assert argv[argv.index("--audio") + 1] == str(real_vad_paths.sample)
    assert shell is False
    assert document.frames.frame_count == len(document.frames.probabilities)
    assert tuple((segment.start_sample, segment.end_sample) for segment in segments) == (
        upstream_intervals
    )


def test_reference_diagnostic_pairs_same_indexes_through_shorter_list() -> None:
    actual = (
        _segment(0, 110, 260),
        _segment(1, 400, 580),
        _segment(2, 800, 900),
    )
    reference = (_segment(0, 100, 250), _segment(1, 420, 560))

    line = _reference_diagnostic(actual, reference)

    assert json.loads(line.removeprefix("REFERENCE_DIAGNOSTIC=")) == {
        "actual_segment_count": 3,
        "reference_segment_count": 2,
        "paired_boundary_deltas": [
            {"index": 0, "start_delta_samples": 10, "end_delta_samples": 10},
            {"index": 1, "start_delta_samples": -20, "end_delta_samples": 20},
        ],
    }


@pytest.mark.parametrize(
    ("actual", "reference", "actual_count", "reference_count"),
    [
        ((), (_segment(0, 100, 200),), 0, 1),
        ((_segment(0, 100, 200),), (), 1, 0),
        ((), (), 0, 0),
    ],
)
def test_reference_diagnostic_has_no_pairs_when_either_list_is_empty(
    actual: tuple[ManifestSegment, ...],
    reference: tuple[ManifestSegment, ...],
    actual_count: int,
    reference_count: int,
) -> None:
    line = _reference_diagnostic(actual, reference)

    assert json.loads(line.removeprefix("REFERENCE_DIAGNOSTIC=")) == {
        "actual_segment_count": actual_count,
        "reference_segment_count": reference_count,
        "paired_boundary_deltas": [],
    }


def test_complete_cli_workflow_publishes_corresponding_artifacts_and_one_diagnostic(
    real_vad_paths: RealVadPaths,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    no_network: None,
) -> None:
    task_directory = (tmp_path / "sample-task").resolve()

    status = cli.main([str(real_vad_paths.sample), str(task_directory)])

    captured = capsys.readouterr()
    manifest = decode_manifest((task_directory / "manifest.json").read_bytes())
    assert status == 0
    assert captured.err == ""
    assert captured.out == (
        f"task_work_directory={task_directory}\n"
        f"canonical_audio={task_directory / 'prepared.wav'}\n"
        f"manifest={task_directory / 'manifest.json'}\n"
        f"segment_count={len(manifest.segments)}\n"
    )

    assert all(
        right.start_sample >= left.end_sample
        for left, right in zip(manifest.segments, manifest.segments[1:], strict=False)
    )
    expected_files = {task_directory / segment.path for segment in manifest.segments}
    actual_files = set((task_directory / "segments").glob("segment-*.wav"))
    assert actual_files == expected_files
    assert all(
        WaveFileReader(path).metadata.frame_count == segment.duration_samples
        for path, segment in zip(
            (task_directory / item.path for item in manifest.segments),
            manifest.segments,
            strict=True,
        )
    )

    reference_payload = json.loads(
        (real_vad_paths.sample.parent / "manifest.json").read_text(encoding="utf-8")
    )
    diagnostic = _reference_diagnostic(
        manifest.segments,
        _segments_from_reference(reference_payload),
    )
    _assert_diagnostic_shape(diagnostic)
    with capsys.disabled():
        print(diagnostic, flush=True)


@pytest.mark.parametrize(
    ("source_kind", "expected_stage"),
    [("missing", "source-media"), ("existing-task", "task-directory")],
)
def test_cli_runtime_failures_stop_at_the_correct_stage(
    source_kind: str,
    expected_stage: str,
    real_vad_paths: RealVadPaths,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    no_network: None,
) -> None:
    source = real_vad_paths.sample
    task_directory = tmp_path / "sample-task"
    relevant_path = source
    if source_kind == "missing":
        source = tmp_path / "missing.wav"
        relevant_path = source
    else:
        task_directory.mkdir()
        relevant_path = task_directory

    status = cli.main([str(source), str(task_directory)])

    captured = capsys.readouterr()
    assert status == 1
    assert captured.out == ""
    assert captured.err.startswith(f"ERROR [{expected_stage}]: ")
    assert str(relevant_path) in captured.err
    assert captured.err.count("\n") == 1
    assert "Traceback" not in captured.err
