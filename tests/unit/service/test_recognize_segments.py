from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import pytest

from tests.support.asr import (
    ControlledExecutionProvider,
    make_asr_command,
    make_segment_manifest,
)
from tests.support.call_log import CallLog
from transcriber.domain.manifest import SegmentManifest, encode_manifest
from transcriber.infrastructure.asr_files import AsrTaskFilesFailure
from transcriber.infrastructure.execution_provider import ExecutionProviderFailure, RecognitionToken
from transcriber.protocol.asr_cli import AsrCommand, AsrFailure, AsrProgress, AsrSuccess
from transcriber.service.recognize_segments import RecognizeSegments


class _Files:
    def __init__(self, manifest_bytes: bytes, log: CallLog) -> None:
        self.manifest_bytes = manifest_bytes
        self.log = log
        self.batch_arguments: list[tuple[Path, tuple[str, ...], tuple[int, ...]]] = []
        self.published: list[tuple[Path, str, bytes]] = []

    def read_manifest(self, task_work_directory: Path) -> bytes:
        self.log.record("manifest.read")
        return self.manifest_bytes

    def check_segments(
        self,
        task_work_directory: Path,
        filenames: Sequence[str],
        durations: Sequence[int],
    ) -> Literal[True]:
        self.log.record("segments.check")
        self.batch_arguments.append((task_work_directory, tuple(filenames), tuple(durations)))
        return True

    def publish(self, task_work_directory: Path, model_id: str, content: bytes) -> Path:
        self.log.record("transcript.publish")
        self.published.append((task_work_directory, model_id, content))
        return task_work_directory / f"transcripts-{model_id}" / "transcript.json"


def _tokens(*texts: str) -> tuple[RecognitionToken, ...]:
    return tuple(
        RecognitionToken(token_id=index, text=text, log_probability=math.log(0.9))
        for index, text in enumerate(texts)
    )


def test_recognizes_segments_in_manifest_order_without_separators_or_trimming(
    tmp_path: Path,
) -> None:
    log = CallLog()
    segment_texts = ("e", "\u0301", " ")
    segment_count = len(segment_texts)
    manifest = make_segment_manifest(*(10 for _ in range(segment_count)))
    files = _Files(encode_manifest(manifest), log)
    provider = ControlledExecutionProvider(tuple(_tokens(text) for text in segment_texts), log)
    progress: list[AsrProgress] = []
    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=files.publish,
        progress=progress.append,
    )
    command = make_asr_command(tmp_path)

    result = service.recognize(command)

    assert result == AsrSuccess(
        transcript=tmp_path / "transcripts-controlled-asr" / "transcript.json",
        recognized_segments=segment_count,
    )
    assert files.batch_arguments == [
        (
            tmp_path,
            tuple(f"segments/segment-{index:04d}.wav" for index in range(segment_count)),
            tuple(10 for _ in range(segment_count)),
        )
    ]
    assert [request.audio_path for request in provider.session.requests] == [
        *(tmp_path / f"segments/segment-{index:04d}.wav" for index in range(segment_count)),
    ]
    assert [request.segment_index for request in provider.session.requests] == list(
        range(segment_count)
    )
    assert progress == [
        AsrProgress(recognized_segments=index + 1, total_segments=segment_count)
        for index in range(segment_count)
    ]
    assert files.published == [
        (
            tmp_path,
            "controlled-asr",
            b'{"text":['
            + b",".join(
                b'{"text":' + json.dumps(text, ensure_ascii=False).encode() + b',"probability":0.9}'
                for text in segment_texts
            )
            + b"]}\n",
        )
    ]
    assert log.events[-2:] == ("provider.stop", "transcript.publish")


def test_context_capable_model_receives_only_accumulated_prior_transcript_text(
    tmp_path: Path,
) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10, 20, 30)), log)
    provider = ControlledExecutionProvider((_tokens("e", "\u0301"), _tokens(), _tokens("x")), log)
    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=files.publish,
        progress=lambda _: None,
        context_supported=True,
    )

    service.recognize(AsrCommand(tmp_path, model_id="controlled-asr", language="en-GB"))

    assert [request.recognition_context for request in provider.session.requests] == [
        "",
        "é",
        "é",
    ]
    assert [request.language for request in provider.session.requests] == [
        "en-GB",
        "en-GB",
        "en-GB",
    ]


def test_context_disabled_model_receives_empty_context_for_every_segment(tmp_path: Path) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10, 20)), log)
    provider = ControlledExecutionProvider((_tokens("first"), _tokens("second")), log)
    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=files.publish,
        progress=lambda _: None,
        context_supported=False,
    )

    service.recognize(make_asr_command(tmp_path))

    assert [request.recognition_context for request in provider.session.requests] == ["", ""]


def test_rejects_empty_segment_manifest_before_preflight_or_provider_start(tmp_path: Path) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest()), log)
    provider = ControlledExecutionProvider((), log)
    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=files.publish,
        progress=lambda _: None,
    )

    assert service.recognize(make_asr_command(tmp_path)) == AsrFailure(
        stage="segment-manifest",
        message="Segment Manifest must contain at least one Speech Segment",
        model_id="controlled-asr",
    )

    assert log.events == ("manifest.read", "manifest.decode")
    assert files.batch_arguments == []
    assert provider.segment_roots == []


def test_missing_fixed_prerequisites_fail_before_task_or_output_access(tmp_path: Path) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10)), log)
    provider = ControlledExecutionProvider((_tokens("recognized"),), log)

    def missing_prerequisites() -> tuple[str, ...]:
        log.record("prerequisites.check")
        return (
            "vendor/llama-server",
            "models/controlled-asr/model.gguf",
            "models/controlled-asr/projector.gguf",
        )

    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=files.publish,
        progress=lambda _: None,
        missing_prerequisites=missing_prerequisites,
    )

    assert service.recognize(make_asr_command(tmp_path)) == AsrFailure(
        stage="asr-model",
        message=(
            'missing prerequisites: "vendor/llama-server", '
            '"models/controlled-asr/model.gguf", '
            '"models/controlled-asr/projector.gguf"'
        ),
        model_id="controlled-asr",
    )
    assert log.events == ("prerequisites.check",)
    assert provider.segment_roots == []
    assert files.published == []


def test_typed_segment_validation_failure_does_not_start_provider(tmp_path: Path) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10)), log)
    provider = ControlledExecutionProvider((_tokens("recognized"),), log)

    def reject_segments(*_: object) -> Literal[True]:
        log.record("segments.check")
        raise AsrTaskFilesFailure(
            filename="segments/segment-0000.wav",
            reason="missing",
            path=tmp_path / "segments/segment-0000.wav",
        )

    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=reject_segments,
        provider=provider,
        publish_transcript=files.publish,
        progress=lambda _: None,
    )

    assert service.recognize(make_asr_command(tmp_path)) == AsrFailure(
        stage="segment-files",
        message="missing: segments/segment-0000.wav",
        model_id="controlled-asr",
    )

    assert log.events == ("manifest.read", "manifest.decode", "segments.check")
    assert provider.segment_roots == []


@pytest.mark.parametrize("validation_result", (False, 1))
def test_non_true_segment_validation_result_does_not_start_provider(
    tmp_path: Path, validation_result: object
) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10)), log)
    provider = ControlledExecutionProvider((_tokens("recognized"),), log)

    def non_true_segments(*_: object) -> object:
        log.record("segments.check")
        return validation_result

    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=non_true_segments,  # type: ignore[arg-type]
        provider=provider,
        publish_transcript=files.publish,
        progress=lambda _: None,
    )

    assert service.recognize(make_asr_command(tmp_path)) == AsrFailure(
        stage="segment-files",
        message="segment-file validation must return exactly True",
        model_id="controlled-asr",
    )

    assert log.events == ("manifest.read", "manifest.decode", "segments.check")
    assert provider.segment_roots == []
    assert provider.session.requests == []
    assert files.published == []


def test_recognition_exception_stops_provider_once_without_publication_or_suffix_progress(
    tmp_path: Path,
) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10, 20, 30)), log)
    failure = RuntimeError("controlled recognition failure")
    provider = ControlledExecutionProvider((_tokens("first"), failure, _tokens("third")), log)
    progress: list[AsrProgress] = []
    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=files.publish,
        progress=progress.append,
    )

    assert service.recognize(make_asr_command(tmp_path)) == AsrFailure(
        stage="execution-provider",
        message="Execution Provider failed",
        model_id="controlled-asr",
        segment_index=1,
    )
    assert progress == [AsrProgress(recognized_segments=1, total_segments=3)]
    assert files.published == []
    assert log.events == (
        "manifest.read",
        "manifest.decode",
        "segments.check",
        "provider.create",
        "provider.start",
        "provider.recognize.0",
        "provider.recognize.1",
        "provider.stop",
    )


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        (
            "task-directory",
            AsrFailure(
                stage="task-directory",
                message="task directory is unavailable",
                model_id="controlled-asr",
            ),
        ),
        (
            "segment-manifest",
            AsrFailure(
                stage="segment-manifest",
                message="Segment Manifest is invalid",
                model_id="controlled-asr",
            ),
        ),
        (
            "execution-provider",
            AsrFailure(
                stage="execution-provider",
                message="provider startup failed",
                model_id="controlled-asr",
                provider_diagnostic="bind denied",
            ),
        ),
        (
            "provider-response",
            AsrFailure(
                stage="provider-response",
                message="provider response failed",
                model_id="controlled-asr",
                segment_index=0,
                provider_diagnostic="invalid JSON",
            ),
        ),
        (
            "transcript",
            AsrFailure(
                stage="transcript",
                message="transcript publication failed",
                model_id="controlled-asr",
            ),
        ),
        (
            "cancelled",
            AsrFailure(
                stage="cancelled",
                message="task cancelled",
                model_id="controlled-asr",
            ),
        ),
    ],
)
def test_translates_every_remaining_closed_failure_stage(
    operation: str, expected: AsrFailure, tmp_path: Path
) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10)), log)
    provider = ControlledExecutionProvider((_tokens("recognized"),), log)

    if operation == "task-directory":
        def read_manifest(_: Path) -> bytes:
            raise FileNotFoundError
    else:
        read_manifest = files.read_manifest

    if operation == "segment-manifest":
        def decode_manifest(_: bytes) -> SegmentManifest:
            raise ValueError("bad manifest")
    else:
        def decode_manifest(content: bytes) -> SegmentManifest:
            return _decode(content, log)

    if operation == "execution-provider":
        provider = ControlledExecutionProvider(
            (
                ExecutionProviderFailure(
                    message="provider startup failed", diagnostic="bind denied"
                ),
            ),
            log,
        )
        provider.session._responses = iter(())
        def start_failure(*, readiness_timeout_seconds: float) -> None:
            log.record("provider.start")
            raise ExecutionProviderFailure(
                message="provider startup failed", diagnostic="bind denied"
            )
        provider.session._start = start_failure  # type: ignore[method-assign]
    elif operation == "provider-response":
        provider = ControlledExecutionProvider(
            (
                ExecutionProviderFailure(
                    message="provider response failed", diagnostic="invalid JSON"
                ),
            ),
            log,
        )

    if operation == "transcript":
        def publish(_: Path, __: str, ___: bytes) -> Path:
            log.record("transcript.publish")
            raise OSError("disk full")
    else:
        publish = files.publish

    if operation == "cancelled":
        provider = ControlledExecutionProvider((_tokens("unreachable"),), log)

        def cancelled_recognition(*_: object, **__: object) -> object:
            log.record("provider.recognize.0")
            raise KeyboardInterrupt

        provider.session._recognize = cancelled_recognition  # type: ignore[method-assign]

    service = RecognizeSegments(
        read_manifest_file=read_manifest,
        manifest_decoder=decode_manifest,
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=publish,
        progress=lambda _: None,
    )

    assert service.recognize(make_asr_command(tmp_path)) == expected
    if operation == "transcript":
        assert log.events[-2:] == ("provider.stop", "transcript.publish")
    elif operation in {"execution-provider", "provider-response", "cancelled"}:
        assert log.events[-1] == "provider.stop"
    else:
        assert provider.segment_roots == []


def test_passes_controlled_start_and_recognition_deadlines_and_stops_after_timeout(
    tmp_path: Path,
) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10)), log)
    provider = ControlledExecutionProvider(
        (ExecutionProviderFailure(message="recognition request timed out"),), log
    )
    deadlines: list[tuple[str, float]] = []
    original_start = provider.session._start
    original_recognize = provider.session._recognize

    def record_start(*, readiness_timeout_seconds: float) -> None:
        deadlines.append(("start", readiness_timeout_seconds))
        original_start(readiness_timeout_seconds=readiness_timeout_seconds)

    def record_recognize(request: object, *, timeout_seconds: float) -> object:
        deadlines.append(("recognize", timeout_seconds))
        return original_recognize(request, timeout_seconds=timeout_seconds)  # type: ignore[arg-type]

    provider.session._start = record_start  # type: ignore[method-assign]
    provider.session._recognize = record_recognize  # type: ignore[method-assign]
    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=files.publish,
        progress=lambda _: None,
    )

    result = service.recognize(make_asr_command(tmp_path))

    assert result == AsrFailure(
        stage="execution-provider",
        message="recognition request timed out",
        model_id="controlled-asr",
        segment_index=0,
    )
    assert deadlines == [("start", 60.0), ("recognize", 180.0)]
    assert log.events[-1] == "provider.stop"


@pytest.mark.parametrize("operation", ("create", "start", "recognize"))
def test_generic_provider_errors_use_one_safe_message_without_segment_or_diagnostic(
    operation: str, tmp_path: Path
) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10)), log)
    provider = ControlledExecutionProvider((RuntimeError("private provider detail"),), log)

    if operation == "create":
        def create(*_: object, **__: object) -> object:
            raise RuntimeError("private provider detail")

        provider.create = create  # type: ignore[method-assign]
    elif operation == "start":
        def start(*_: object, **__: object) -> object:
            log.record("provider.start")
            raise RuntimeError("private provider detail")

        provider.session._start = start  # type: ignore[method-assign]

    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=files.publish,
        progress=lambda _: None,
    )

    expected_segment_index = 0 if operation == "recognize" else None
    assert service.recognize(make_asr_command(tmp_path)) == AsrFailure(
        stage="execution-provider",
        message="Execution Provider failed",
        model_id="controlled-asr",
        segment_index=expected_segment_index,
    )
    if operation != "create":
        assert log.events[-1] == "provider.stop"


def test_progress_callback_error_is_reraised_only_after_provider_cleanup(tmp_path: Path) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10)), log)
    provider = ControlledExecutionProvider((_tokens("recognized"),), log)
    callback_error = RuntimeError("private callback detail")

    def fail_progress(_: AsrProgress) -> None:
        raise callback_error

    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=files.publish,
        progress=fail_progress,
    )

    with pytest.raises(RuntimeError) as raised:
        service.recognize(make_asr_command(tmp_path))

    assert raised.value is callback_error
    assert files.published == []
    assert log.events[-1] == "provider.stop"


def test_cleanup_failure_overrides_progress_callback_error_without_reraising_callback(
    tmp_path: Path,
) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10)), log)
    provider = ControlledExecutionProvider((_tokens("recognized"),), log)
    callback_error = RuntimeError("private callback detail")

    def fail_progress(_: AsrProgress) -> None:
        raise callback_error

    def fail_stop(*_: object, **__: object) -> object:
        log.record("provider.stop")
        raise ExecutionProviderFailure(
            message="provider response failed", diagnostic="reap failed"
        )

    provider.session._stop = fail_stop  # type: ignore[method-assign]
    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=files.publish,
        progress=fail_progress,
    )

    assert service.recognize(make_asr_command(tmp_path)) == AsrFailure(
        stage="execution-provider",
        message="provider cleanup failed",
        model_id="controlled-asr",
        provider_diagnostic="reap failed",
    )


@pytest.mark.parametrize("recognition_error", (RuntimeError("private"), KeyboardInterrupt()))
def test_cleanup_failure_has_priority_over_recognition_or_cancellation(
    recognition_error: BaseException, tmp_path: Path
) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10)), log)
    provider = ControlledExecutionProvider((_tokens("recognized"),), log)

    def fail_recognition(*_: object, **__: object) -> object:
        log.record("provider.recognize.0")
        raise recognition_error

    def fail_stop(*_: object, **__: object) -> object:
        log.record("provider.stop")
        raise ExecutionProviderFailure(message="provider cleanup failed", diagnostic="reap failed")

    provider.session._recognize = fail_recognition  # type: ignore[method-assign]
    provider.session._stop = fail_stop  # type: ignore[method-assign]
    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=files.publish,
        progress=lambda _: None,
    )

    assert service.recognize(make_asr_command(tmp_path)) == AsrFailure(
        stage="execution-provider",
        message="provider cleanup failed",
        model_id="controlled-asr",
        provider_diagnostic="reap failed",
    )


def test_cleanup_failure_prevents_transcript_publication_and_retains_prior_bytes(
    tmp_path: Path,
) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10)), log)
    provider = ControlledExecutionProvider((_tokens("replacement"),), log)
    transcript = tmp_path / "transcripts-controlled-asr" / "transcript.json"
    transcript.parent.mkdir()
    previous_bytes = b"previous complete transcript\n"
    transcript.write_bytes(previous_bytes)

    def fail_stop(*_: object, **__: object) -> object:
        log.record("provider.stop")
        raise ExecutionProviderFailure(
            message="provider cleanup failed", diagnostic="reap failed"
        )

    def publish(_: Path, __: str, content: bytes) -> Path:
        log.record("transcript.publish")
        transcript.write_bytes(content)
        return transcript

    provider.session._stop = fail_stop  # type: ignore[method-assign]
    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=publish,
        progress=lambda _: None,
    )

    assert service.recognize(make_asr_command(tmp_path)) == AsrFailure(
        stage="execution-provider",
        message="provider cleanup failed",
        model_id="controlled-asr",
        provider_diagnostic="reap failed",
    )
    assert transcript.read_bytes() == previous_bytes
    assert "transcript.publish" not in log.events
    assert log.events.count("provider.stop") == 1


def test_progress_cancellation_skips_publication_after_provider_cleanup(
    tmp_path: Path,
) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10)), log)
    provider = ControlledExecutionProvider((_tokens("recognized"),), log)

    def cancel_progress(_: AsrProgress) -> None:
        raise asyncio.CancelledError

    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=files.publish,
        progress=cancel_progress,
    )

    assert service.recognize(make_asr_command(tmp_path)) == AsrFailure(
        stage="cancelled",
        message="task cancelled",
        model_id="controlled-asr",
    )

    assert files.published == []
    assert log.events.count("provider.stop") == 1


def test_normalization_span_overflow_skips_publication_after_provider_cleanup(
    tmp_path: Path,
) -> None:
    log = CallLog()
    files = _Files(encode_manifest(make_segment_manifest(10)), log)
    overflowing_source = "\u0301" * 8_193
    provider = ControlledExecutionProvider((_tokens(overflowing_source),), log)
    service = RecognizeSegments(
        read_manifest_file=files.read_manifest,
        manifest_decoder=lambda content: _decode(content, log),
        check_segment_files=files.check_segments,
        provider=provider,
        publish_transcript=files.publish,
        progress=lambda _: None,
    )

    assert service.recognize(make_asr_command(tmp_path)) == AsrFailure(
        stage="execution-provider",
        message="Execution Provider failed",
        model_id="controlled-asr",
        segment_index=0,
    )

    assert files.published == []
    assert log.events.count("provider.stop") == 1


def _decode(content: bytes, log: CallLog) -> SegmentManifest:
    log.record("manifest.decode")
    from transcriber.domain.manifest import decode_manifest

    return decode_manifest(content)
