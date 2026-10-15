from io import StringIO
from types import SimpleNamespace

from transcriber.controller import diarization_cli as cli
from transcriber.protocol.diarization_cli import (
    DiarizationFailure, DiarizationProgress, DiarizationWarning,
)


def test_progress_is_flushed_and_diagnostics_have_no_embedded_linebreaks(monkeypatch):
    class Output(StringIO):
        flushes = 0
        def flush(self):
            self.flushes += 1
    output = Output()
    errors = Output()
    monkeypatch.setattr('sys.stdout', output)
    monkeypatch.setattr('sys.stderr', errors)
    def build(**callbacks):
        callbacks['diarization_progress'](DiarizationProgress('validate'))
        assert output.getvalue() == 'stage=validate\n'
        assert output.flushes == 1
        callbacks['diarization_warning'](DiarizationWarning('inference\r\nfailed\u2028again'))
        return SimpleNamespace(diarize=lambda _: DiarizationFailure('mask', 'mask\nfailed'))
    monkeypatch.setattr(cli, 'build_application', build)
    assert cli.main(['work']) == 1
    assert errors.getvalue() == ('WARNING [community1]: inference failed again; '
        'using Nemotron-only diarization\nERROR [mask]: mask failed\n')
