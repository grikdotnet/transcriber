"""Controlled end-to-end acceptance coverage for the ASR Task MVP."""

from __future__ import annotations

import json
import math
import socket
from collections.abc import Callable, Sequence
from pathlib import Path
from shutil import copyfile
from typing import Literal, NoReturn

import pytest

from tests.conftest import RealAsrPaths
from tests.support.asr import (
    ControlledExecutionProvider,
    make_asr_task_directory,
    make_segment_manifest,
    write_speech_segment,
)
from tests.support.call_log import CallLog
from tests.support.managed_process import ManagedProcessDouble, ManagedProcessStarterDouble
from transcriber.composition import application
from transcriber.controller import asr_cli
from transcriber.domain.manifest import encode_manifest
from transcriber.domain.transcript import Transcript
from transcriber.infrastructure import filesystem
from transcriber.infrastructure.asr_files import (
    check_segment_files,
    publish_transcript,
    read_manifest_file,
)
from transcriber.infrastructure.execution_provider import (
    ExecutionProvider,
    ExecutionProviderFailure,
    RecognitionRequest,
    RecognitionResult,
    RecognitionToken,
)
from transcriber.infrastructure.llama_cpp import LlamaCppExecutionProvider
from transcriber.infrastructure.wave_files import WaveFileReader
from transcriber.protocol.asr_model_manifest import AsrModelCapabilities
from transcriber.protocol.qwen_asr import decode_qwen_response, encode_qwen_request
from transcriber.service.recognize_segments import RecognizeSegments

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


ControlledResponse = str | tuple[RecognitionToken, ...] | Exception


def _tokenize_responses(
    responses: tuple[ControlledResponse, ...],
) -> tuple[tuple[RecognitionToken, ...] | Exception, ...]:
    """Map legacy text fixtures to scored provider-neutral Recognition Tokens."""
    tokenized_responses: list[tuple[RecognitionToken, ...] | Exception] = []
    for index, response in enumerate(responses):
        if isinstance(response, str):
            tokens = () if not response else (RecognitionToken(index, response, 0.0),)
            tokenized_responses.append(tokens)
        else:
            tokenized_responses.append(response)
    return tuple(tokenized_responses)


def _controlled_provider(
    responses: tuple[ControlledResponse, ...], log: CallLog
) -> ControlledExecutionProvider:
    return ControlledExecutionProvider(_tokenize_responses(responses), log)


def _controlled_application(
    responses: tuple[ControlledResponse, ...],
    log: CallLog,
    *,
    context_supported: bool = True,
    language_behavior: Literal["optional", "required"] = "optional",
    provider: ExecutionProvider | None = None,
    missing_prerequisites: Callable[[], Sequence[str]] = lambda: (),
) -> application.Application:
    controlled_provider = provider or _controlled_provider(responses, log)
    return application.Application(
        service=object(),  # type: ignore[arg-type]
        asr_service=RecognizeSegments(
            read_manifest_file=read_manifest_file,
            manifest_decoder=application.decode_manifest,
            check_segment_files=check_segment_files,
            provider=controlled_provider,
            publish_transcript=publish_transcript,
            progress=lambda progress: asr_cli._render_progress(progress),
            context_supported=context_supported,
            missing_prerequisites=missing_prerequisites,
        ),
        asr_model_id="qwen3-asr-1.7b",
        asr_capabilities=AsrModelCapabilities(
            context=context_supported,
            language=language_behavior,
        ),
    )


def _write_controlled_task(tmp_path: Path, segment_count: int) -> Path:
    durations = tuple(index + 1 for index in range(segment_count))
    task_work_directory = make_asr_task_directory(
        tmp_path,
        encode_manifest(make_segment_manifest(*durations)),
    )
    for index, duration in enumerate(durations):
        write_speech_segment(task_work_directory, index, duration)
    return task_work_directory


def _application_for_qwen_response(response: bytes) -> application.Application:
    """Run controlled Qwen bytes through llama.cpp and Transcript publication."""

    class ControlledLoopbackTransport:
        def health(self, *, host: str, port: int, timeout_seconds: float) -> bool:
            assert (host, port, timeout_seconds) == ("127.0.0.1", 43127, 60.0)
            return True

        def recognize(
            self, *, host: str, port: int, payload: bytes, timeout_seconds: float
        ) -> bytes:
            assert (host, port, timeout_seconds) == ("127.0.0.1", 43127, 180.0)
            assert json.loads(payload)["logprobs"] is True
            return response

    def decode_response(payload: bytes) -> RecognitionResult:
        qwen_result = decode_qwen_response(payload)
        return RecognitionResult(
            tokens=tuple(
                RecognitionToken(token.token_id, token.text, token.log_probability)
                for token in qwen_result.tokens
            )
        )

    provider = LlamaCppExecutionProvider(
        executable=REPOSITORY_ROOT / "vendor" / "llama-server",
        model_path=REPOSITORY_ROOT / "models" / "qwen3-asr-1.7b" / "model.gguf",
        audio_projector_path=REPOSITORY_ROOT / "models" / "qwen3-asr-1.7b" / "projector.gguf",
        process_starter=ManagedProcessStarterDouble(ManagedProcessDouble()),
        transport=ControlledLoopbackTransport(),
        encode_request=lambda request: encode_qwen_request(
            audio_path=request.audio_path,
            recognition_context=request.recognition_context,
            language=request.language,
        ),
        decode_response=decode_response,
        endpoint_port=lambda: 43127,
        monotonic_clock=lambda: 0.0,
        sleeper=lambda _seconds: None,
    )
    return _controlled_application((), CallLog(), provider=provider)


@pytest.mark.parametrize("segment_count", [1, 100])
def test_asr_command_recognizes_each_speech_segment_once_in_manifest_order(
    segment_count: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_work_directory = _write_controlled_task(tmp_path, segment_count)
    log = CallLog()
    responses = tuple(
        (
            RecognitionToken(index * 2, "e", math.log(0.9)),
            RecognitionToken(index * 2 + 1, "\u0301.", math.log(0.7)),
        )
        for index in range(segment_count)
    )
    built = _controlled_application(responses, log)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 0

    transcript = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    expected_document = {
        "text": [
            span
            for _ in range(segment_count)
            for span in (
                {"text": "é", "probability": 0.7},
                {"text": ".", "probability": 0.7},
            )
        ]
    }
    assert transcript.read_bytes() == (
        json.dumps(expected_document, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    assert json.loads(transcript.read_bytes()) == expected_document
    assert log.events == (
        "provider.create",
        "provider.start",
        *(f"provider.recognize.{index}" for index in range(segment_count)),
        "provider.stop",
    )
    assert capsys.readouterr() == (
        "".join(
            f"recognized_segments={index + 1} total_segments={segment_count}\n"
            for index in range(segment_count)
        )
        + f"transcript={transcript}\n",
        "",
    )


def test_asr_command_counts_an_empty_middle_result_without_a_transcript_separator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_work_directory = _write_controlled_task(tmp_path, 3)
    log = CallLog()
    built = _controlled_application((" first", "", "last "), log)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 0

    transcript = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    document = json.loads(transcript.read_bytes())
    assert "".join(span["text"] for span in document["text"]) == " firstlast "
    assert transcript.read_bytes().endswith(b"\n")
    assert transcript.read_bytes() != b'{"text":[]}\n'
    assert log.events == (
        "provider.create",
        "provider.start",
        "provider.recognize.0",
        "provider.recognize.1",
        "provider.recognize.2",
        "provider.stop",
    )
    assert capsys.readouterr() == (
        "recognized_segments=1 total_segments=3\n"
        "recognized_segments=2 total_segments=3\n"
        "recognized_segments=3 total_segments=3\n"
        f"transcript={transcript}\n",
        "",
    )


def test_asr_command_publishes_the_exact_empty_structured_transcript(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_work_directory = _write_controlled_task(tmp_path, 1)
    log = CallLog()
    built = _controlled_application(((),), log)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 0

    transcript = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    assert transcript.read_bytes() == b'{"text":[]}\n'


@pytest.mark.parametrize(
    ("provider_response", "expected_bytes"),
    (
        (
            {
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "ignored"},
                        "finish_reason": "stop",
                        "logprobs": {
                            "content": [
                                {
                                    "id": 7,
                                    "token": "language English<asr_text>hé",
                                    "logprob": math.log(0.8),
                                }
                            ]
                        },
                    }
                ]
            },
            '{"text":[{"text":"h","probability":0.8},{"text":"é","probability":0.8}]}\n'.encode(),
        ),
        (
            {
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "unexposed text"},
                        "finish_reason": "stop",
                    }
                ]
            },
            b'{"text":[]}\n',
        ),
    ),
)
def test_asr_command_accepts_qwen_prefix_and_absent_token_list_as_success(
    provider_response: dict[str, object],
    expected_bytes: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Qwen metadata is removed, while omitted token data produces an empty success."""

    task_work_directory = _write_controlled_task(tmp_path, 1)
    built = _application_for_qwen_response(json.dumps(provider_response).encode())
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 0
    assert (
        task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    ).read_bytes() == expected_bytes


def test_asr_command_rerun_replaces_the_prior_complete_transcript(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_work_directory = _write_controlled_task(tmp_path, 1)
    transcript = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    transcript.parent.mkdir()
    transcript.write_bytes(b'{"text":[{"text":"previous","probability":1}]}\n')
    log = CallLog()
    applications = iter(
        (
            _controlled_application(("replacement one",), log),
            _controlled_application(("replacement two",), log),
        )
    )
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: next(applications))

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 0
    assert "".join(span["text"] for span in json.loads(transcript.read_bytes())["text"]) == (
        "replacement one"
    )
    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 0

    assert "".join(span["text"] for span in json.loads(transcript.read_bytes())["text"]) == (
        "replacement two"
    )


def test_asr_command_supplies_exact_continuity_context_to_a_context_capable_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_work_directory = _write_controlled_task(tmp_path, 3)
    log = CallLog()
    first_result = "alpha"
    second_result = "β" * 2049 + " boundary"
    provider = _controlled_provider((first_result, second_result, "third"), log)
    built = _controlled_application((), log, provider=provider)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 0

    assert [request.recognition_context for request in provider.session.requests] == [
        "",
        "alpha",
        "boundary",
    ]


def test_asr_command_supplies_empty_context_to_a_context_disabled_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_work_directory = _write_controlled_task(tmp_path, 3)
    log = CallLog()
    provider = _controlled_provider(("first", "second", "third"), log)
    built = _controlled_application(
        (), log, context_supported=False, provider=provider
    )
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 0

    assert [request.recognition_context for request in provider.session.requests] == [
        "",
        "",
        "",
    ]


@pytest.mark.parametrize("language", ["ab", "abcdefgh", "ab-a", "abcdefgh-12345678"])
def test_asr_command_preserves_each_valid_boundary_language_tag(
    language: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_work_directory = _write_controlled_task(tmp_path, 1)
    log = CallLog()
    provider = _controlled_provider(("recognized",), log)
    built = _controlled_application((), log, provider=provider)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert (
        asr_cli.main(
            [
                str(task_work_directory),
                "--model",
                "qwen3-asr-1.7b",
                "--language",
                language,
            ]
        )
        == 0
    )
    assert [request.language for request in provider.session.requests] == [language]


def test_asr_command_reports_unsupported_qwen_language_through_real_failure_flow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class ControlledLoopbackTransport:
        def __init__(self) -> None:
            self.recognition_calls: list[bytes] = []

        def health(self, *, host: str, port: int, timeout_seconds: float) -> bool:
            assert host == "127.0.0.1"
            assert port == 43127
            assert timeout_seconds == 60.0
            return True

        def recognize(
            self, *, host: str, port: int, payload: bytes, timeout_seconds: float
        ) -> bytes:
            self.recognition_calls.append(payload)
            return b'{"choices":[]}'

    task_work_directory = _write_controlled_task(tmp_path, 1)
    process = ManagedProcessDouble()
    transport = ControlledLoopbackTransport()
    provider = LlamaCppExecutionProvider(
        executable=REPOSITORY_ROOT / "vendor" / "llama-server",
        model_path=(
            REPOSITORY_ROOT
            / "models"
            / "qwen3-asr-1.7b"
            / "Qwen3-ASR-1.7B-Q8_0.gguf"
        ),
        audio_projector_path=(
            REPOSITORY_ROOT
            / "models"
            / "qwen3-asr-1.7b"
            / "mmproj-Qwen3-ASR-1.7B-Q8_0.gguf"
        ),
        process_starter=ManagedProcessStarterDouble(process),
        transport=transport,
        encode_request=lambda request: encode_qwen_request(
            audio_path=request.audio_path,
            recognition_context=request.recognition_context,
            language=request.language,
        ),
        decode_response=lambda payload: RecognitionResult(
            tokens=tuple(
                RecognitionToken(token.token_id, token.text, token.log_probability)
                for token in decode_qwen_response(payload).tokens
            )
        ),
        endpoint_port=lambda: 43127,
        monotonic_clock=lambda: 0.0,
        sleeper=lambda _seconds: None,
    )
    built = _controlled_application((), CallLog(), provider=provider)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert (
        asr_cli.main(
            [
                str(task_work_directory),
                "--model",
                "qwen3-asr-1.7b",
                "--language",
                "cy",
            ]
        )
        == 1
    )

    assert transport.recognition_calls == []
    assert process.terminate_calls == 1
    assert capsys.readouterr() == (
        "",
        'ERROR [execution-provider] model="qwen3-asr-1.7b" segment=0: '
        "Qwen ASR does not support language tag: cy\n",
    )


@pytest.mark.parametrize("language", ["a", "abcdefghi", "ab-", "ab--cd", "ab_12", "en_US"])
def test_asr_command_rejects_invalid_language_tags_before_provider_startup(
    language: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_work_directory = _write_controlled_task(tmp_path, 1)
    log = CallLog()
    built = _controlled_application(("unreachable",), log)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert (
        asr_cli.main(
            [
                str(task_work_directory),
                "--model",
                "qwen3-asr-1.7b",
                "--language",
                language,
            ]
        )
        == 2
    )
    assert log.events == ()


def test_asr_command_rejects_automatic_language_for_a_required_model_before_provider_startup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_work_directory = _write_controlled_task(tmp_path, 1)
    log = CallLog()
    built = _controlled_application(
        ("unreachable",), log, language_behavior="required"
    )
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 2
    assert log.events == ()


def _qwen_response(
    *,
    probability_content: object = (),
    finish_reason: object = "stop",
    include_finish_reason: bool = True,
) -> bytes:
    """Build one controlled completed Qwen response with mutable result fields."""
    choice: dict[str, object] = {
        "message": {"role": "assistant", "content": "ignored"},
        "logprobs": {"content": probability_content},
    }
    if include_finish_reason:
        choice["finish_reason"] = finish_reason
    return json.dumps(
        {
            "choices": [choice]
        }
    ).encode()


@pytest.mark.parametrize(
    "response",
    (
        _qwen_response(
            probability_content=[{"id": 1, "token": "<asr_text>", "logprob": -0.1}]
        ),
        _qwen_response(probability_content={}),
    ),
    ids=("malformed-initial-marker", "malformed-present-token-list"),
)
def test_asr_command_rejects_invalid_qwen_responses_without_replacing_a_transcript(
    response: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Malformed provider data crosses the real adapter boundary before publication."""
    task_work_directory = _write_controlled_task(tmp_path, 1)
    transcript = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    transcript.parent.mkdir()
    previous_bytes = b'{"text":[{"text":"previous","probability":1}]}\n'
    transcript.write_bytes(previous_bytes)
    built = _application_for_qwen_response(response)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith('ERROR [provider-response] model="qwen3-asr-1.7b" segment=0:')
    assert transcript.read_bytes() == previous_bytes
    assert list(transcript.parent.glob(".transcript.json.*.tmp")) == []


def test_asr_command_preserves_a_transcript_after_normalization_overflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_work_directory = _write_controlled_task(tmp_path, 1)
    transcript = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    transcript.parent.mkdir()
    previous_bytes = b'{"text":[{"text":"previous","probability":1}]}\n'
    transcript.write_bytes(previous_bytes)
    log = CallLog()
    overflowing_tokens = (RecognitionToken(1, "\u0301" * 8193, -0.1),)
    provider = _controlled_provider((overflowing_tokens,), log)
    built = _controlled_application((), log, provider=provider)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("ERROR [execution-provider]")
    assert transcript.read_bytes() == previous_bytes
    assert list(transcript.parent.glob(".transcript.json.*.tmp")) == []
    assert log.events == (
        "provider.create",
        "provider.start",
        "provider.recognize.0",
        "provider.stop",
    )


@pytest.mark.parametrize(
    ("boundary", "expected_stage", "completed_segments", "provider_started"),
    (
        ("task-directory", "task-directory", 0, False),
        ("segment-manifest", "segment-manifest", 0, False),
        ("segment-files", "segment-files", 0, False),
        ("provider-create", "execution-provider", 0, False),
        ("provider-startup-deadline", "execution-provider", 0, True),
        ("provider-response", "provider-response", 1, True),
        ("recognition-deadline", "execution-provider", 0, True),
        ("publication", "transcript", 2, True),
        ("cancellation", "cancelled", 1, True),
    ),
)
def test_asr_command_failure_matrix_preserves_complete_transcript_and_cleans_up(
    boundary: str,
    expected_stage: str,
    completed_segments: int,
    provider_started: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Each public failure boundary retains prior output and emits completed progress only."""
    task_work_directory = _write_controlled_task(tmp_path, 2)
    transcript = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    transcript.parent.mkdir()
    previous_bytes = b"previous complete transcript\n"
    transcript.write_bytes(previous_bytes)
    log = CallLog()
    responses: tuple[ControlledResponse, ...] = ("first", "second")
    if boundary == "provider-response":
        responses = (
            "first",
            ExecutionProviderFailure(
                message="provider response failed", diagnostic="malformed response"
            ),
        )
    elif boundary == "recognition-deadline":
        responses = (ExecutionProviderFailure(message="recognition request timed out"),)
    provider = _controlled_provider(responses, log)
    built = _controlled_application((), log, provider=provider)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    if boundary == "task-directory":
        (task_work_directory / "manifest.json").unlink()
    elif boundary == "segment-manifest":
        (task_work_directory / "manifest.json").write_bytes(b"invalid manifest")
    elif boundary == "segment-files":
        (task_work_directory / "segments" / "segment-0000.wav").unlink()
    elif boundary == "provider-create":
        def fail_create(*, segment_root: Path) -> NoReturn:
            del segment_root
            raise RuntimeError("controlled create failure")

        provider.create = fail_create  # type: ignore[method-assign]
    elif boundary == "provider-startup-deadline":
        def startup_deadline(*, readiness_timeout_seconds: float) -> None:
            assert readiness_timeout_seconds == 60.0
            log.record("provider.start")
            raise ExecutionProviderFailure(message="provider startup timed out")

        provider.session._start = startup_deadline  # type: ignore[method-assign]
    elif boundary == "publication":
        def fail_replace(_: Path, __: Path) -> None:
            raise OSError("controlled replacement failure")

        monkeypatch.setattr(filesystem.os, "replace", fail_replace)
    elif boundary == "cancellation":
        original_recognize = provider.session._recognize

        def cancel_second(
            request: RecognitionRequest, *, timeout_seconds: float
        ) -> RecognitionResult:
            if request.segment_index == 1:
                log.record("provider.recognize.1")
                raise KeyboardInterrupt
            return original_recognize(request, timeout_seconds=timeout_seconds)

        provider.session._recognize = cancel_second  # type: ignore[method-assign]

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 1

    captured = capsys.readouterr()
    assert captured.out == "".join(
        f"recognized_segments={index} total_segments=2\n"
        for index in range(1, completed_segments + 1)
    )
    assert captured.err.startswith(f"ERROR [{expected_stage}]")
    assert "transcript=" not in captured.out
    assert transcript.read_bytes() == previous_bytes
    assert list(transcript.parent.glob(".transcript.json.*.tmp")) == []
    if provider_started:
        assert log.events.count("provider.start") == 1
        assert log.events.count("provider.stop") == 1
    else:
        assert "provider.start" not in log.events
        assert "provider.stop" not in log.events


def test_asr_command_rejects_zero_segments_without_provider_or_transcript_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_work_directory = _write_controlled_task(tmp_path, 0)
    transcript = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    transcript.parent.mkdir()
    previous_bytes = b"previous complete transcript\n"
    transcript.write_bytes(previous_bytes)
    log = CallLog()
    built = _controlled_application(("unreachable",), log)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("ERROR [segment-manifest]")
    assert transcript.read_bytes() == previous_bytes
    assert list(transcript.parent.glob(".transcript.json.*.tmp")) == []
    assert log.events == ()


def test_asr_command_rejects_an_unknown_model_before_task_or_transcript_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Unknown model resolution is an availability boundary, not task processing."""
    task_work_directory = _write_controlled_task(tmp_path, 1)
    transcript = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    transcript.parent.mkdir()
    previous_bytes = b"previous complete transcript\n"
    transcript.write_bytes(previous_bytes)
    log = CallLog()
    built = _controlled_application(("unreachable",), log)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "unknown-asr"]) == 1

    assert capsys.readouterr() == (
        "",
        'ERROR [asr-model] model="unknown-asr": unregistered ASR Model: unknown-asr\n',
    )
    assert transcript.read_bytes() == previous_bytes
    assert log.events == ()


def test_asr_command_reports_all_missing_prerequisites_before_provider_or_transcript_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Availability reports fixed provider and artifact paths before service startup."""
    task_work_directory = _write_controlled_task(tmp_path, 1)
    transcript = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    transcript.parent.mkdir()
    previous_bytes = b"previous complete transcript\n"
    transcript.write_bytes(previous_bytes)
    log = CallLog()
    provider = _controlled_provider(("unreachable",), log)
    built = _controlled_application(
        (),
        log,
        provider=provider,
        missing_prerequisites=lambda: (
            "vendor/llama-server",
            "models/qwen3-asr-1.7b/Qwen3-ASR-1.7B-Q8_0.gguf",
            "models/qwen3-asr-1.7b/mmproj-Qwen3-ASR-1.7B-Q8_0.gguf",
        ),
    )
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 1

    assert capsys.readouterr() == (
        "",
        'ERROR [asr-model] model="qwen3-asr-1.7b": missing prerequisites: '
        '\\"vendor/llama-server\\", \\"models/qwen3-asr-1.7b/Qwen3-ASR-1.7B-Q8_0.gguf\\", '
        '\\"models/qwen3-asr-1.7b/mmproj-Qwen3-ASR-1.7B-Q8_0.gguf\\"\n',
    )
    assert transcript.read_bytes() == previous_bytes
    assert log.events == ()


def test_invalid_packaged_asr_manifest_is_rejected_before_provider_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed built-in metadata is rejected without files, network, or provider startup."""
    provider_registrations = 0

    class InvalidManifestResource:
        def joinpath(self, _: str) -> InvalidManifestResource:
            return self

        def read_bytes(self) -> bytes:
            return b'{"schema_version": 999}'

    class UnexpectedLlamaCppExecutionProvider:
        def __init__(self, **_: object) -> None:
            nonlocal provider_registrations
            provider_registrations += 1

    def unexpected_network(*_: object, **__: object) -> NoReturn:
        raise AssertionError("manifest validation must not contact the network")

    monkeypatch.setattr(application, "files", lambda _: InvalidManifestResource())
    monkeypatch.setattr(socket, "create_connection", unexpected_network)
    monkeypatch.setattr(
        application,
        "LlamaCppExecutionProvider",
        UnexpectedLlamaCppExecutionProvider,
    )

    with pytest.raises(ValueError):
        application.build_application()

    assert provider_registrations == 0


def test_second_valid_registration_uses_the_unchanged_transcript_assembly_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A compatible registration changes selection only, never Transcript assembly."""
    task_work_directory = _write_controlled_task(tmp_path, 2)
    log = CallLog()
    provider = _controlled_provider(("first", "second"), log)
    baseline = _controlled_application((), log, provider=provider)
    built = application.Application(
        service=baseline.service,
        asr_service=baseline.asr_service,
        asr_model_id=baseline.asr_model_id,
        asr_capabilities=baseline.asr_capabilities,
        asr_registrations=(
            application.AsrRegistration(
                model_id="second-asr",
                capabilities=AsrModelCapabilities(context=True, language="optional"),
                service=baseline.asr_service,
            ),
        ),
    )
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "second-asr"]) == 0

    transcript = task_work_directory / "transcripts-second-asr" / "transcript.json"
    assert "".join(span["text"] for span in json.loads(transcript.read_bytes())["text"]) == (
        "firstsecond"
    )
    assert capsys.readouterr() == (
        "recognized_segments=1 total_segments=2\n"
        "recognized_segments=2 total_segments=2\n"
        f"transcript={transcript}\n",
        "",
    )
    assert log.events == (
        "provider.create",
        "provider.start",
        "provider.recognize.0",
        "provider.recognize.1",
        "provider.stop",
    )


def test_asr_command_stops_provider_after_non_timeout_startup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_work_directory = _write_controlled_task(tmp_path, 1)
    transcript = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    transcript.parent.mkdir()
    previous_bytes = b"previous complete transcript\n"
    transcript.write_bytes(previous_bytes)
    log = CallLog()
    provider = _controlled_provider(("unreachable",), log)

    def fail_start(*, readiness_timeout_seconds: float) -> None:
        assert readiness_timeout_seconds == 60.0
        log.record("provider.start")
        raise ExecutionProviderFailure(
            message="provider startup failed", diagnostic="controlled bind failure"
        )

    provider.session._start = fail_start  # type: ignore[method-assign]
    built = _controlled_application((), log, provider=provider)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        'ERROR [execution-provider] model="qwen3-asr-1.7b": '
        'provider startup failed: provider said "controlled bind failure"\n'
    )
    assert transcript.read_bytes() == previous_bytes
    assert list(transcript.parent.glob(".transcript.json.*.tmp")) == []
    assert log.events == ("provider.create", "provider.start", "provider.stop")


def test_asr_command_reports_non_timeout_recognition_failure_with_index_and_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_work_directory = _write_controlled_task(tmp_path, 2)
    transcript = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    transcript.parent.mkdir()
    previous_bytes = b"previous complete transcript\n"
    transcript.write_bytes(previous_bytes)
    log = CallLog()
    provider = _controlled_provider(
        (
            "first",
            ExecutionProviderFailure(
                message="provider request failed", diagnostic='controlled "request" failure'
            ),
        ),
        log,
    )
    built = _controlled_application((), log, provider=provider)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 1

    captured = capsys.readouterr()
    assert captured.out == "recognized_segments=1 total_segments=2\n"
    assert captured.err == (
        'ERROR [execution-provider] model="qwen3-asr-1.7b" segment=1: '
        'provider request failed: provider said "controlled \\"request\\" failure"\n'
    )
    assert transcript.read_bytes() == previous_bytes
    assert list(transcript.parent.glob(".transcript.json.*.tmp")) == []
    assert log.events == (
        "provider.create",
        "provider.start",
        "provider.recognize.0",
        "provider.recognize.1",
        "provider.stop",
    )


def test_asr_command_cleanup_failure_retains_prior_transcript_after_completed_recognition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task_work_directory = _write_controlled_task(tmp_path, 1)
    transcript = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    transcript.parent.mkdir()
    previous_bytes = b"previous complete transcript\n"
    transcript.write_bytes(previous_bytes)
    log = CallLog()
    provider = _controlled_provider(("replacement",), log)

    def fail_stop(*_: object, **__: object) -> object:
        log.record("provider.stop")
        raise ExecutionProviderFailure(
            message="provider cleanup failed", diagnostic="controlled reap failure"
        )

    provider.session._stop = fail_stop  # type: ignore[method-assign]
    built = _controlled_application((), log, provider=provider)
    monkeypatch.setattr(asr_cli, "build_application", lambda **_: built)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 1

    captured = capsys.readouterr()
    assert captured.out == "recognized_segments=1 total_segments=1\n"
    assert captured.err == (
        'ERROR [execution-provider] model="qwen3-asr-1.7b": '
        'provider cleanup failed: provider said "controlled reap failure"\n'
    )
    assert transcript.read_bytes() == previous_bytes
    assert list(transcript.parent.glob(".transcript.json.*.tmp")) == []


@pytest.mark.real_asr
def test_real_asr_workflow(
    real_asr_paths: RealAsrPaths,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exercise the shipped Qwen path without treating model output as an oracle."""
    task_work_directory = tmp_path / "asr-task"
    segment_directory = task_work_directory / "segments"
    segment_directory.mkdir(parents=True)
    segment = segment_directory / "segment-0000.wav"
    copyfile(real_asr_paths.sample, segment)
    duration_samples = WaveFileReader(segment).metadata.frame_count
    (task_work_directory / "manifest.json").write_bytes(
        encode_manifest(make_segment_manifest(duration_samples))
    )

    captured_provider_arguments: dict[str, object] = {}
    request_payloads: list[bytes] = []
    response_payloads: list[bytes] = []
    decoded_responses: list[RecognitionResult] = []
    exposed_token_records: list[dict[str, object]] = []
    process_events: list[str] = []
    started_argv: list[tuple[str, ...]] = []
    provider_class = application.LlamaCppExecutionProvider
    process_starter_class = application.SubprocessManagedProcessStarter

    class CapturingLlamaCppExecutionProvider(provider_class):
        def __init__(self, **kwargs: object) -> None:
            captured_provider_arguments.update(kwargs)
            super().__init__(**kwargs)  # type: ignore[arg-type]

    def capture_request(*, audio_path: Path, recognition_context: str, language: str) -> bytes:
        payload = encode_qwen_request(
            audio_path=audio_path,
            recognition_context=recognition_context,
            language=language,
        )
        request_payloads.append(payload)
        return payload

    def capture_response(payload: bytes) -> RecognitionResult:
        response_payloads.append(payload)
        response = json.loads(payload)
        assert isinstance(response, dict)
        choices = response["choices"]
        assert isinstance(choices, list)
        assert len(choices) == 1
        choice = choices[0]
        assert isinstance(choice, dict)
        assert choice["finish_reason"] == "stop"
        logprobs = choice.get("logprobs")
        assert isinstance(logprobs, dict)
        token_records = logprobs.get("content")
        assert isinstance(token_records, list)
        assert token_records
        assert all(isinstance(record, dict) for record in token_records)
        exposed_token_records.extend(token_records)
        qwen_result = decode_qwen_response(payload)
        result = RecognitionResult(
            tokens=tuple(
                RecognitionToken(token.token_id, token.text, token.log_probability)
                for token in qwen_result.tokens
            )
        )
        decoded_responses.append(result)
        return result

    class RecordingManagedProcess:
        def __init__(self, delegate: object) -> None:
            self._delegate = delegate

        @property
        def diagnostic(self) -> str:
            return self._delegate.diagnostic  # type: ignore[union-attr]

        def poll(self) -> int | None:
            return self._delegate.poll()  # type: ignore[union-attr]

        def terminate(self) -> None:
            process_events.append("terminate")
            self._delegate.terminate()  # type: ignore[union-attr]

        def kill(self) -> None:
            process_events.append("kill")
            self._delegate.kill()  # type: ignore[union-attr]

        def wait(self, *, timeout: float) -> int:
            process_events.append(f"wait={timeout}")
            return self._delegate.wait(timeout=timeout)  # type: ignore[union-attr]

    class RecordingProcessStarter:
        def __init__(self) -> None:
            self._delegate = process_starter_class()

        def start(self, argv: Sequence[str], *, shell: bool = False) -> RecordingManagedProcess:
            started_argv.append(tuple(argv))
            return RecordingManagedProcess(self._delegate.start(argv, shell=shell))

    monkeypatch.setattr(
        application, "LlamaCppExecutionProvider", CapturingLlamaCppExecutionProvider
    )
    monkeypatch.setattr(application, "encode_qwen_request", capture_request)
    monkeypatch.setattr(application, "decode_qwen_response", capture_response)
    monkeypatch.setattr(application, "SubprocessManagedProcessStarter", RecordingProcessStarter)

    assert asr_cli.main([str(task_work_directory), "--model", "qwen3-asr-1.7b"]) == 0

    transcript = task_work_directory / "transcripts-qwen3-asr-1.7b" / "transcript.json"
    assert captured_provider_arguments["executable"] == real_asr_paths.provider
    assert captured_provider_arguments["model_path"] == real_asr_paths.model
    assert captured_provider_arguments["audio_projector_path"] == real_asr_paths.audio_projector
    assert len(request_payloads) == 1
    assert len(response_payloads) == 1
    assert all(
        isinstance(record["id"], int) and not isinstance(record["id"], bool)
        for record in exposed_token_records
    )
    assert all(
        isinstance(record["token"], str)
        and record["token"].encode("utf-8").decode("utf-8") == record["token"]
        for record in exposed_token_records
    )
    assert all(
        isinstance(record["logprob"], (int, float))
        and not isinstance(record["logprob"], bool)
        and not math.isnan(float(record["logprob"]))
        and float(record["logprob"]) <= 0
        for record in exposed_token_records
    )
    request = json.loads(request_payloads[0])
    assert request["messages"] == [
        {"role": "system", "content": ""},
        {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {"url": "file://segment-0000.wav"},
                }
            ],
        },
    ]
    assert request["stream"] is False
    assert request["temperature"] == 0
    assert request["cache_prompt"] is False
    expected_transcript = Transcript()
    for token in decoded_responses[0].tokens:
        expected_transcript.append_token(token.text, token.log_probability)
    expected_transcript.finish_segment()
    assert transcript.is_file()
    assert transcript.read_bytes() == expected_transcript.encode()
    assert started_argv[0][0] == str(real_asr_paths.provider)
    assert "terminate" in process_events
    assert "wait=60.0" in process_events
    assert capsys.readouterr().out == (
        "recognized_segments=1 total_segments=1\n"
        f"transcript={transcript}\n"
    )
