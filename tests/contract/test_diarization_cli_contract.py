from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriber.controller import diarization_cli as cli
from transcriber.protocol.diarization_cli import (
    DiarizationCommand, DiarizationFailure, DiarizationProgress, DiarizationSuccess,
    DiarizationWarning,
)


@pytest.mark.parametrize('arguments', [[], ['a', 'b'], ['a', '--unknown'],
    ['a', '--nemo-gpu-index', '-2'], ['a', '--vulkan-gpu-index', '-1'],
    ['a', '--nemo-gpu-index', '1.2'], ['a', '--vulkan-gpu-index', 'true']])
def test_invalid_arguments_never_build_application(arguments, monkeypatch, capsys):
    monkeypatch.setattr(cli, 'build_application', lambda **_: pytest.fail('assembled'))
    assert cli.main(arguments) == 2


def test_help_never_builds_application(monkeypatch, capsys):
    monkeypatch.setattr(cli, 'build_application', lambda **_: pytest.fail('assembled'))
    assert cli.main(['--help']) == 0
    assert 'TASK_WORK_DIRECTORY' in capsys.readouterr().out


@pytest.mark.parametrize('options,expected', [([], (0, 0)),
    (['--nemo-gpu-index', '-1', '--vulkan-gpu-index', '3'], (-1, 3))])
def test_success_contract(options, expected, monkeypatch, capsys, tmp_path):
    def build(**callbacks):
        def diarize(command):
            assert command == DiarizationCommand(Path('work').resolve(), *expected)
            for stage in ('validate', 'nemotron', 'community1', 'fusion', 'mask', 'publish'):
                callbacks['diarization_progress'](DiarizationProgress(stage))
            callbacks['diarization_warning'](DiarizationWarning('inference failed'))
            return DiarizationSuccess(tmp_path / 'diarization.json')
        return SimpleNamespace(diarize=diarize)
    monkeypatch.setattr(cli, 'build_application', build)
    assert cli.main(['work', *options]) == 0
    captured = capsys.readouterr()
    assert captured.out == ''.join(f'stage={stage}\n' for stage in
        ('validate', 'nemotron', 'community1', 'fusion', 'mask', 'publish')) + f'diarization={tmp_path}/diarization.json\n'
    assert captured.err == 'WARNING [community1]: inference failed; using Nemotron-only diarization\n'


@pytest.mark.parametrize('stage', ['validate', 'nemotron', 'community1', 'fusion', 'mask', 'publish', 'cancelled'])
def test_failure_contract(stage, monkeypatch, capsys):
    monkeypatch.setattr(cli, 'build_application', lambda **_: SimpleNamespace(
        diarize=lambda _: DiarizationFailure(stage, 'operation failed')))
    assert cli.main(['work']) == 1
    assert capsys.readouterr().err == f'ERROR [{stage}]: operation failed\n'


@pytest.mark.parametrize('nemo,vulkan', [(True, 0), (0, False), (1.5, 0), (0, -1), (-2, 0)])
def test_command_rejects_invalid_gpu_values(nemo, vulkan):
    with pytest.raises(ValueError):
        DiarizationCommand(Path('/work'), nemo, vulkan)


def test_controlled_us1_cli_publishes_fused_artifact(monkeypatch, tmp_path, capsys):
    import numpy as np
    from tests.support.diarization import make_diarization_manifest
    from transcriber.composition import application
    from transcriber.domain.diarization import CommunityPrediction, NemotronPrediction, SpeakerActivity
    from transcriber.domain.manifest import encode_manifest
    from transcriber.infrastructure.diarization_files import DecodedAudio
    from transcriber.protocol.diarization_json import decode_diarization

    manifest = make_diarization_manifest(160000, ((0, 160000),))
    monkeypatch.setattr(application, 'read_manifest_file', lambda _: encode_manifest(manifest))
    monkeypatch.setattr(application, 'decode_canonical_audio', lambda _, count:
        DecodedAudio(np.zeros(count, dtype=np.float32), count))
    original = application.build_diarization_service
    def controlled(**kwargs):
        from dataclasses import replace
        return replace(original(**kwargs),
            nemotron=lambda *_: NemotronPrediction((SpeakerActivity(0., 4., 7), SpeakerActivity(5., 9., 12))),
            community1=lambda *_: CommunityPrediction((SpeakerActivity(0., 5., 'a'), SpeakerActivity(5., 10., 'b'))),
            solver=lambda _: ((0, 0), (1, 1)))
    monkeypatch.setattr(application, 'build_diarization_service', controlled)
    assert cli.main([str(tmp_path)]) == 0
    result = decode_diarization((tmp_path / 'diarization.json').read_bytes())
    assert [(row.speaker_id, row.start_sample, row.end_sample) for row in result.intervals] == [
        (7, 0, 80000), (12, 80000, 160000)]
    assert capsys.readouterr().out.endswith(f'diarization={tmp_path}/diarization.json\n')


@pytest.mark.parametrize('option', ['--nemo-gpu', '--vulkan-gpu'])
def test_abbreviated_options_are_unknown_before_assembly(option, monkeypatch, capsys):
    monkeypatch.setattr(cli, 'build_application', lambda **_: pytest.fail('assembled'))
    assert cli.main(['work', option, '0']) == 2


@pytest.mark.parametrize('failure', [OSError('permission denied'), RuntimeError('symlink loop'), ValueError('invalid path')])
def test_work_path_resolution_failure_is_validate_failure(failure, monkeypatch, capsys):
    def resolve(_):
        raise failure
    monkeypatch.setattr(Path, 'resolve', resolve)
    monkeypatch.setattr(cli, 'build_application', lambda **_: pytest.fail('assembled'))
    assert cli.main(['work']) == 1
    assert capsys.readouterr().err == f'ERROR [validate]: {failure}\n'


def test_symlink_loop_is_validate_failure(monkeypatch, tmp_path, capsys):
    loop = tmp_path / 'loop'
    loop.symlink_to(loop)
    monkeypatch.setattr(cli, 'build_application', lambda **_: pytest.fail('assembled'))
    assert cli.main([str(loop)]) == 1
    assert capsys.readouterr().err.startswith('ERROR [validate]: ')


@pytest.mark.parametrize('options,expected', [
    ([], (0, 0)),
    (['--nemo-gpu-index', '2', '--vulkan-gpu-index', '5'], (2, 5)),
    (['--nemo-gpu-index', '-1', '--vulkan-gpu-index', '3'], (-1, 3)),
])
def test_assembled_cli_routes_independent_gpu_indices_to_native_boundaries(
    options: list[str], expected: tuple[int, int], monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    from typing import Any

    from tests.support.diarization import (
        COMMUNITY_PREDICTION,
        NEMOTRON_PREDICTION,
        make_diarization_manifest,
        make_diarization_task_directory,
    )
    from tests.unit.infrastructure.test_nemo_speech import Symbol
    from transcriber.infrastructure import nemo_speech, pyannote
    from transcriber.infrastructure.diarization_prerequisites import CommunityPrerequisites
    from transcriber.protocol.nemo_diarization import NATIVE_SIGNATURES

    work = make_diarization_task_directory(
        tmp_path, make_diarization_manifest(160000, ((0, 160000),)), [0] * 160000,
    )
    nemo_indices: list[int] = []
    community_arguments: list[dict[str, int]] = []

    def invoke(name: str, *args: Any) -> int:
        if name == 'nemo_speech_diar_create':
            nemo_indices.append(args[0]._obj.gpu)
            args[1]._obj.value = 11
        elif name == 'nemo_speech_diar_stream_open':
            args[1]._obj.value = 22
        elif name == 'nemo_speech_diar_segments':
            args[4]._obj.value = len(NEMOTRON_PREDICTION)
            if args[2] is not None:
                for segment, (start, end, speaker) in zip(
                    args[2], NEMOTRON_PREDICTION, strict=True,
                ):
                    segment.start_time, segment.end_time, segment.speaker = start, end, speaker
        return 0

    native = SimpleNamespace(**{
        name: Symbol(lambda *args, name=name: invoke(name, *args))
        for name, _, _ in NATIVE_SIGNATURES
    })
    # Replace only the adapter's native loader; CLI, Composition and both adapters run normally.
    monkeypatch.setitem(
        nemo_speech.NemoSpeechAdapter.__init__.__kwdefaults__, 'load_library', lambda _: native,
    )

    class Diarizer:
        def __init__(self, models_dir: Path, **kwargs: int) -> None:
            community_arguments.append(kwargs)

        def segment(self, audio: Any) -> object:
            return object()

        def extract_embeddings(self, audio: Any, segmentation: Any) -> object:
            return object()

        def cluster(self, segmentation: Any, embeddings: Any) -> object:
            return object()

        def reconstruct(self, audio: Any, segmentation: Any, clustering: Any) -> list[Any]:
            return [SimpleNamespace(start=start, end=end, speaker=speaker)
                    for start, end, speaker in COMMUNITY_PREDICTION]

    capabilities = CommunityPrerequisites(Diarizer, object(), lambda: None, lambda: None)
    monkeypatch.setattr(pyannote, 'check_community_prerequisites', lambda _: capabilities)
    monkeypatch.setattr(pyannote, 'check_vulkan_device', lambda *_: None)

    assert cli.main([str(work), *options]) == 0
    assert nemo_indices == [expected[0]]
    assert community_arguments == [dict(
        minimum_speakers=2, maximum_speakers=2, gpu_index=expected[1],
    )]
    captured = capsys.readouterr()
    assert 'stage=community1\n' in captured.out
    assert captured.err == ''
    assert (work / 'diarization.json').is_file()
