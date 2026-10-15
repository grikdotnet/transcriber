# Translated adapter faults exercise Service policy; native teardown is adapter-owned.
import asyncio
import weakref
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from tests.support.diarization import make_diarization_manifest
from transcriber.domain.diarization import CommunityPrediction, NemotronPrediction, SpeakerActivity
from transcriber.domain.manifest import decode_manifest, encode_manifest
from transcriber.infrastructure.diarization_files import DecodedAudio
from transcriber.infrastructure.diarization_provider import (
    DiarizationCancelled,
    DiarizationCleanupFailure,
    RecoverableDiarizationFailure,
)
from transcriber.protocol.diarization_cli import (
    DiarizationCommand,
    DiarizationFailure,
    DiarizationSuccess,
    DiarizationWarning,
)
from transcriber.service.diarize_audio import DiarizeAudio


def test_full_recording_fusion_shared_audio_cleanup_and_repeat_publication(tmp_path: Path) -> None:
    manifest = make_diarization_manifest(160000, ((64000, 80000), (144000, 160000)))
    events = []
    refs = []

    def decode(path, count):
        events.append("decode")
        samples = np.zeros(count, dtype=np.float32)
        refs.append(weakref.ref(samples))
        return DecodedAudio(samples, count)

    def nemo(samples, gpu):
        events.append("nemo-cleaned")
        assert samples is refs[-1]()
        return NemotronPrediction(
            tuple(
                SpeakerActivity(*row)
                for row in ((-1.0, 4.0, 7), (0.0, 4.0, 7), (5.0, 9.0, 12), (11.0, 12.0, 99))
            )
        )

    def community(samples, count, gpu):
        events.append("community-cleaned")
        assert samples is refs[-1]()
        assert count == 2
        return CommunityPrediction(
            (SpeakerActivity(0.0, 5.0, "a"), SpeakerActivity(5.0, 10.0, "b"))
        )

    def solver(matrix):
        events.append("fusion")
        assert matrix == ((4.0, 0.0), (0.0, 4.0))
        return ((0, 0), (1, 1))

    def encode(rows):
        assert [(r.speaker_id, r.start_sample, r.end_sample) for r in rows] == [
            (7, 64000, 80000),
            (12, 144000, 160000),
        ]
        return b"complete\n"

    def publish(path, payload):
        assert refs[-1]() is None
        events.append("publish")
        destination = path / "diarization.json"
        destination.write_bytes(payload)
        return destination

    service = DiarizeAudio(
        read_manifest_file=lambda _: encode_manifest(manifest),
        manifest_decoder=decode_manifest,
        decode_audio=decode,
        nemotron=nemo,
        community1=community,
        solver=solver,
        encode_result=encode,
        publish=publish,
        progress=lambda p: events.append(p.stage),
    )
    for _ in range(2):
        assert service.diarize(DiarizationCommand(tmp_path)) == DiarizationSuccess(
            tmp_path / "diarization.json"
        )
    assert events[:12] == [
        "validate",
        "decode",
        "nemotron",
        "nemo-cleaned",
        "community1",
        "community-cleaned",
        "fusion",
        "fusion",
        "mask",
        "publish",
        "publish",
        "validate",
    ]


def test_empty_union_validates_and_releases_audio_without_runtime_calls(tmp_path: Path) -> None:
    from unittest.mock import Mock

    manifest = make_diarization_manifest(4, ())
    events = []
    refs = []

    def decode(path, count):
        events.append("decode")
        samples = np.zeros(count, dtype=np.float32)
        refs.append(weakref.ref(samples))
        return DecodedAudio(samples, count)

    def publish(path, payload):
        assert refs[0]() is None
        assert payload == b"empty"
        return path / "diarization.json"

    forbidden = Mock(side_effect=AssertionError("runtime must be skipped"))
    service = DiarizeAudio(
        read_manifest_file=lambda _: events.append("manifest") or encode_manifest(manifest),
        manifest_decoder=decode_manifest,
        decode_audio=decode,
        nemotron=forbidden,
        community1=forbidden,
        solver=forbidden,
        encode_result=lambda rows: b"empty" if rows == () else b"wrong",
        publish=publish,
        progress=lambda progress: events.append(progress.stage),
        warning=forbidden,
    )
    assert isinstance(service.diarize(DiarizationCommand(tmp_path)), DiarizationSuccess)
    assert events == ["validate", "manifest", "decode", "mask", "publish"]
    forbidden.assert_not_called()


def test_observed_count_uses_clipped_distinct_ids_before_mask(tmp_path: Path) -> None:
    from unittest.mock import Mock

    # ID 12 is outside the mask but still requests the second engine. ID 99
    # disappears on clipping, and repeated ID 7 rows contribute one identity.
    cases = (
        ((), 0),
        (((-3.0, -1.0, 99), (10.0, 12.0, 98), (2.0, 2.0, 97)), 0),
        (((-1.0, 2.0, 7), (1.0, 3.0, 7), (11.0, 12.0, 99)), 1),
        (((0.0, 2.0, 7), (0.0, 2.0, 7), (5.0, 9.0, 12), (11.0, 12.0, 99)), 2),
    )
    manifest = make_diarization_manifest(160000, ((0, 32000),))
    for rows, count in cases:
        stages = []
        warning = Mock()
        secondary = Mock(return_value=CommunityPrediction(()))
        solver = Mock(return_value=())
        encoded = []
        service = DiarizeAudio(
            read_manifest_file=lambda _: encode_manifest(manifest),
            manifest_decoder=decode_manifest,
            decode_audio=lambda _, total: DecodedAudio(np.zeros(total, dtype=np.float32), total),
            nemotron=lambda _, gpu, rows=rows: NemotronPrediction(
                tuple(SpeakerActivity(*row) for row in rows)
            ),
            community1=secondary,
            solver=solver,
            encode_result=lambda activity, encoded=encoded: encoded.append(activity) or b"complete",
            publish=lambda path, payload: path / "diarization.json",
            progress=lambda progress, stages=stages: stages.append(progress.stage),
            warning=warning,
        )
        assert isinstance(service.diarize(DiarizationCommand(tmp_path)), DiarizationSuccess)
        assert stages == (
            ["validate", "nemotron", "community1", "fusion", "mask", "publish"]
            if count == 2
            else ["validate", "nemotron", "mask", "publish"]
        )
        warning.assert_not_called()
        if count == 2:
            assert secondary.call_args.args[1] == 2
        else:
            secondary.assert_not_called()
            solver.assert_not_called()
        assert [(row.speaker_id, row.start_sample, row.end_sample) for row in encoded[0]] == (
            [(7, 0, 32000)] if count else []
        )


def fault_service(tmp_path):
    manifest = make_diarization_manifest(160000, ((0, 160000),))
    refs = []

    def decode(_, count):
        samples = np.zeros(count, dtype=np.float32)
        refs.append(weakref.ref(samples))
        return DecodedAudio(samples, count)

    artifact = tmp_path / "diarization.json"
    artifact.write_bytes(b"previous")
    publish = Mock(return_value=artifact)
    warning = Mock()
    service = DiarizeAudio(
        read_manifest_file=lambda _: encode_manifest(manifest),
        manifest_decoder=decode_manifest,
        decode_audio=decode,
        nemotron=lambda *_: NemotronPrediction(
            (SpeakerActivity(0.0, 4.0, 1), SpeakerActivity(5.0, 9.0, 2))
        ),
        community1=lambda *_: CommunityPrediction(()),
        solver=lambda _: (),
        encode_result=lambda rows: b"base",
        publish=publish,
        warning=warning,
    )
    return service, artifact, publish, warning, refs


def test_recoverable_secondary_warns_then_publishes_masked_base(tmp_path):
    service, _, publish, warning, refs = fault_service(tmp_path)
    fault = RecoverableDiarizationFailure(
        stage="community1", operation="inference", diagnostic="bad"
    )
    events = []

    def secondary(samples, *_):
        raise fault

    def encode(rows):
        assert [(r.speaker_id, r.start_sample, r.end_sample) for r in rows] == [
            (1, 0, 64000),
            (2, 80000, 144000),
        ]
        events.append("mask")
        return b"base"

    service = replace(
        service,
        community1=secondary,
        encode_result=encode,
        warning=lambda value: events.append(value),
    )
    assert isinstance(service.diarize(DiarizationCommand(tmp_path)), DiarizationSuccess)
    assert events == [DiarizationWarning(str(fault)), "mask"]
    assert refs[0]() is None
    publish.assert_called_once()


@pytest.mark.parametrize(
    "point",
    [
        "read_manifest_file",
        "manifest_decoder",
        "decode_audio",
        "nemotron",
        "community1",
        "solver",
        "encode_result",
        "publish",
    ],
)
def test_firstparty_and_mandatory_failures_are_fatal(tmp_path, point):
    service, artifact, publish, warning, refs = fault_service(tmp_path)
    stage = {
        "read_manifest_file": "validate",
        "manifest_decoder": "validate",
        "decode_audio": "validate",
        "solver": "fusion",
        "encode_result": "mask",
    }.get(point, point)

    def fail(*_):
        raise RuntimeError("fault")

    # Ensure fusion actually invokes the solver.
    secondary = CommunityPrediction(
        (SpeakerActivity(0.0, 4.0, "a"), SpeakerActivity(5.0, 9.0, "b"))
    )
    service = (
        replace(service, community1=lambda *_: secondary, **{point: fail})
        if point != "community1"
        else replace(service, community1=fail)
    )
    result = service.diarize(DiarizationCommand(tmp_path))
    assert result == DiarizationFailure(stage, "fault")
    warning.assert_not_called()
    publish.assert_not_called()
    assert artifact.read_bytes() == b"previous"
    assert all(ref() is None for ref in refs)


@pytest.mark.parametrize(
    "fault",
    [
        KeyboardInterrupt(),
        asyncio.CancelledError(),
        DiarizationCancelled(stage="community1", operation="cancel"),
        *[
            DiarizationCleanupFailure(stage=owner, operation="cleanup")
            for owner in ("nemotron", "community1", "mask")
        ],
    ],
)
@pytest.mark.parametrize("point", ["nemotron", "community1", "encode_result"])
def test_cancellation_and_cleanup_use_fatal_owner_stage(tmp_path, fault, point):
    service, artifact, publish, warning, refs = fault_service(tmp_path)

    def fail(*_):
        raise fault

    result = replace(service, **{point: fail}).diarize(DiarizationCommand(tmp_path))
    assert isinstance(result, DiarizationFailure)
    assert result.stage == (
        fault.stage if isinstance(fault, DiarizationCleanupFailure) else "cancelled"
    )
    publish.assert_not_called()
    warning.assert_not_called()
    assert artifact.read_bytes() == b"previous"
    assert all(ref() is None for ref in refs)


@pytest.mark.parametrize(
    "rows",
    [
        (),
        (SpeakerActivity(0.0, 4.0, "a"),),
        (SpeakerActivity(9.0, 10.0, "a"), SpeakerActivity(9.0, 10.0, "b")),
    ],
)
def test_valid_secondary_results_always_fuse_without_warning(tmp_path, monkeypatch, rows):
    from transcriber.service import diarize_audio

    service, _, publish, warning, _ = fault_service(tmp_path)
    fusion = Mock(return_value=())
    monkeypatch.setattr(diarize_audio, "fuse_predictions", fusion)
    service = replace(service, community1=lambda *_: CommunityPrediction(rows))
    assert isinstance(service.diarize(DiarizationCommand(tmp_path)), DiarizationSuccess)
    fusion.assert_called_once()
    warning.assert_not_called()
    publish.assert_called_once()


@pytest.mark.parametrize(
    "function, stage", [("fuse_predictions", "fusion"), ("mask_activity", "mask")]
)
def test_domain_failures_are_fatal(tmp_path, monkeypatch, function, stage):
    from transcriber.service import diarize_audio

    service, artifact, publish, warning, refs = fault_service(tmp_path)
    monkeypatch.setattr(diarize_audio, function, Mock(side_effect=ValueError("domain fault")))
    assert service.diarize(DiarizationCommand(tmp_path)) == DiarizationFailure(
        stage, "domain fault"
    )
    publish.assert_not_called()
    warning.assert_not_called()
    assert artifact.read_bytes() == b"previous"
    assert refs[0]() is None


@pytest.mark.parametrize("checkpoint", range(1, 12))
def test_cooperative_cancellation_checkpoints_prevent_publication(tmp_path, checkpoint):
    service, artifact, publish, warning, refs = fault_service(tmp_path)
    calls = 0

    def cancel():
        nonlocal calls
        calls += 1
        if calls == checkpoint:
            raise asyncio.CancelledError()

    result = replace(service, check_cancelled=cancel).diarize(DiarizationCommand(tmp_path))
    assert isinstance(result, DiarizationFailure) and result.stage == "cancelled"
    publish.assert_not_called()
    warning.assert_not_called()
    assert artifact.read_bytes() == b"previous"
    assert all(ref() is None for ref in refs)


@pytest.mark.parametrize(
    "point, stage", [("nemotron", "nemotron"), ("solver", "fusion"), ("encode_result", "mask")]
)
def test_recoverable_type_outside_secondary_attempt_is_fatal(tmp_path, point, stage):
    service, artifact, publish, warning, _ = fault_service(tmp_path)
    fault = RecoverableDiarizationFailure(stage="community1", operation="misplaced")

    def fail(*_):
        raise fault

    if point == "solver":
        service = replace(
            service,
            community1=lambda *_: CommunityPrediction(
                (SpeakerActivity(0.0, 4.0, "a"), SpeakerActivity(5.0, 9.0, "b"))
            ),
        )
    result = replace(service, **{point: fail}).diarize(DiarizationCommand(tmp_path))
    assert isinstance(result, DiarizationFailure) and result.stage == stage
    publish.assert_not_called()
    warning.assert_not_called()
    assert artifact.read_bytes() == b"previous"
