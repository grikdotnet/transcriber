"""Domain behavior for the structured, normalized Transcript artifact."""

from __future__ import annotations

import math

import icu
import pytest

from transcriber.domain.transcript import Transcript

_NFKC = icu.Normalizer2.getNFKCInstance()
_PENDING_SOURCE_SPAN_BYTE_LIMIT = 16_384
_NON_BOUNDARY_COMBINING_ACUTE = "\u0301"


def _append_segment(transcript: Transcript, *tokens: tuple[str, float]) -> None:
    """Append one provider-complete Speech Segment through the Domain seam."""
    for text, log_probability in tokens:
        transcript.append_token(text, log_probability)
    transcript.finish_segment()


def _installed_icu_spans(*tokens: tuple[str, float]) -> list[tuple[str, float]]:
    """Build source-span expectations using the installed ICU boundary oracle."""
    source: list[str] = []
    log_probabilities: list[float] = []
    expected: list[tuple[str, float]] = []

    def flush() -> None:
        if not source:
            return
        normalized = _NFKC.normalize("".join(source))
        if normalized:
            expected.append((normalized, math.exp(min(log_probabilities))))
        source.clear()
        log_probabilities.clear()

    for text, log_probability in tokens:
        for code_point in text:
            if source and _NFKC.hasBoundaryBefore(code_point):
                flush()
            source.append(code_point)
            log_probabilities.append(log_probability)
    flush()
    return expected


def _published_spans(transcript: Transcript) -> list[tuple[str, float]]:
    return [(span.text, span.probability) for span in transcript.spans]


def test_uses_icu_boundary_before_to_flush_cross_token_composition_with_minimum_score() -> None:
    transcript = Transcript()
    tokens = (("e", math.log(0.9)), ("\u0301.", math.log(0.7)))

    _append_segment(transcript, *tokens)

    assert _published_spans(transcript) == pytest.approx(_installed_icu_spans(*tokens))
    assert transcript.text == "é."


def test_one_recognition_token_can_contribute_to_multiple_normalization_spans() -> None:
    transcript = Transcript()
    tokens = (("A.B", math.log(0.42)),)

    _append_segment(transcript, *tokens)

    assert _published_spans(transcript) == pytest.approx(_installed_icu_spans(*tokens))
    assert transcript.text == _NFKC.normalize("A.B")


@pytest.mark.parametrize(
    "tokens",
    (
        (("ﬁ", math.log(0.8)),),
        (("\u1100", math.log(0.9)), ("\u1161", math.log(0.6))),
        (("ｶ", math.log(0.9)), ("ﾞ", math.log(0.6))),
        ((" \t", math.log(0.75)),),
    ),
    ids=("compatibility-expansion", "hangul-jamo", "halfwidth-katakana", "whitespace"),
)
def test_normalizes_unicode_source_spans_and_preserves_token_probability_provenance(
    tokens: tuple[tuple[str, float], ...],
) -> None:
    transcript = Transcript()

    _append_segment(transcript, *tokens)

    assert _published_spans(transcript) == pytest.approx(_installed_icu_spans(*tokens))
    assert transcript.text == _NFKC.normalize("".join(text for text, _ in tokens))


@pytest.mark.parametrize(
    "tokens",
    ((), (("", math.log(0.4)),)),
    ids=("no-tokens", "empty-token"),
)
def test_segment_without_text_publishes_no_normalization_span(
    tokens: tuple[tuple[str, float], ...],
) -> None:
    transcript = Transcript()

    _append_segment(transcript, *tokens)

    assert transcript.spans == ()
    assert transcript.text == ""
    assert transcript.encode() == b'{"text":[]}\n'


def test_flushes_each_speech_segment_before_the_next_segment_can_compose_with_it() -> None:
    transcript = Transcript()

    _append_segment(transcript, ("e", math.log(0.9)))
    _append_segment(transcript, ("\u0301", math.log(0.7)))

    assert _published_spans(transcript) == pytest.approx([("e", 0.9), ("\u0301", 0.7)])
    assert transcript.text == "e\u0301"


def test_recognition_context_uses_concatenated_normalized_span_text_without_separators() -> None:
    transcript = Transcript()

    _append_segment(transcript, ("first ", math.log(0.9)))
    _append_segment(transcript, ("second", math.log(0.8)))

    assert transcript.text == "first second"
    assert transcript.recognition_context() == "first second"
    assert transcript.recognition_context(8) == "second"


def test_recognition_context_returns_complete_unicode_text_at_or_below_the_limit() -> None:
    transcript = Transcript()

    _append_segment(transcript, ("甲" * 2047, math.log(0.9)))
    assert transcript.recognition_context() == "甲" * 2047

    transcript = Transcript()
    _append_segment(transcript, ("乙" * 2048, math.log(0.9)))

    assert transcript.recognition_context() == "乙" * 2048


def test_recognition_context_applies_existing_unicode_whitespace_fragment_rules() -> None:
    transcript = Transcript()
    _append_segment(transcript, (("甲" * 2047) + "\u2003" + ("乙" * 2044), math.log(0.9)))

    assert transcript.recognition_context() == "乙" * 2044


@pytest.mark.parametrize(
    ("recognized_text", "limit", "expected_context"),
    (
        ("alpha beta", 8, "beta"),
        ("alpha beta", 4, "beta"),
        ("alpha-beta", 4, ""),
        ("alpha,beta", 4, ""),
        ("甲乙丙丁", 3, ""),
    ),
)
def test_recognition_context_uses_only_unicode_whitespace_as_a_boundary(
    recognized_text: str, limit: int, expected_context: str
) -> None:
    transcript = Transcript()

    _append_segment(transcript, (recognized_text, math.log(0.9)))

    assert transcript.recognition_context(limit) == expected_context


def test_encodes_compact_two_field_utf8_json_with_one_final_line_feed() -> None:
    transcript = Transcript()

    _append_segment(transcript, ("e", math.log(0.9)), ("\u0301.", math.log(0.7)))

    assert transcript.encode() == (
        b'{"text":[{"text":"\xc3\xa9","probability":0.7},'
        b'{"text":".","probability":0.7}]}\n'
    )


def test_accepts_a_pending_source_span_at_the_exact_utf8_byte_limit() -> None:
    transcript = Transcript()
    source_text = _NON_BOUNDARY_COMBINING_ACUTE * (_PENDING_SOURCE_SPAN_BYTE_LIMIT // 2)

    assert len(source_text.encode()) == _PENDING_SOURCE_SPAN_BYTE_LIMIT
    assert not _NFKC.hasBoundaryBefore(_NON_BOUNDARY_COMBINING_ACUTE)

    _append_segment(transcript, (source_text, math.log(0.9)))

    assert transcript.text == source_text


def test_rejects_a_non_boundary_code_point_that_exceeds_the_pending_span_byte_limit() -> None:
    transcript = Transcript()
    source_text = _NON_BOUNDARY_COMBINING_ACUTE * (_PENDING_SOURCE_SPAN_BYTE_LIMIT // 2)

    transcript.append_token(source_text, math.log(0.9))

    with pytest.raises(ValueError, match="16,384"):
        transcript.append_token(_NON_BOUNDARY_COMBINING_ACUTE, math.log(0.8))

    transcript.finish_segment()

    assert transcript.text == source_text


def test_guaranteed_boundary_starts_a_fresh_pending_span_after_the_byte_limit() -> None:
    transcript = Transcript()
    source_text = _NON_BOUNDARY_COMBINING_ACUTE * (_PENDING_SOURCE_SPAN_BYTE_LIMIT // 2)

    assert _NFKC.hasBoundaryBefore("A")

    _append_segment(transcript, (source_text, math.log(0.9)), ("A", math.log(0.8)))

    assert _published_spans(transcript) == pytest.approx(
        [(source_text, 0.9), ("A", 0.8)]
    )


def test_speech_segment_completion_resets_the_pending_span_byte_limit() -> None:
    transcript = Transcript()
    source_text = _NON_BOUNDARY_COMBINING_ACUTE * (_PENDING_SOURCE_SPAN_BYTE_LIMIT // 2)

    _append_segment(transcript, (source_text, math.log(0.9)))
    _append_segment(transcript, (_NON_BOUNDARY_COMBINING_ACUTE, math.log(0.8)))

    assert _published_spans(transcript) == pytest.approx(
        [(source_text, 0.9), (_NON_BOUNDARY_COMBINING_ACUTE, 0.8)]
    )
