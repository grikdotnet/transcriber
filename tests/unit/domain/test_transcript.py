from __future__ import annotations

import pytest

from transcriber.domain.transcript import Transcript


def test_joins_trimmed_non_empty_recognition_results_in_append_order() -> None:
    transcript = Transcript()

    transcript.append("  first result  ")
    transcript.append("second result")

    assert transcript.text == "first result second result"


def test_omits_empty_and_whitespace_only_recognition_results() -> None:
    transcript = Transcript()

    transcript.append("")
    transcript.append(" \t\n ")

    assert transcript.text == ""
    assert transcript.encode() == b""


def test_encodes_ordered_non_ascii_text_as_utf8_with_one_trailing_line_feed() -> None:
    transcript = Transcript()

    transcript.append("  café  ")
    transcript.append("世界")

    assert transcript.text == "café 世界"
    assert transcript.encode() == b"caf\xc3\xa9 \xe4\xb8\x96\xe7\x95\x8c\n"


def test_empty_result_between_recognized_results_contributes_no_separator() -> None:
    transcript = Transcript()

    transcript.append("first")
    transcript.append("\n\t")
    transcript.append("second")

    assert transcript.text == "first second"


def test_recognition_context_returns_complete_unicode_text_at_or_below_the_limit() -> None:
    transcript = Transcript()

    transcript.append("甲" * 2047)
    assert transcript.recognition_context() == "甲" * 2047

    transcript = Transcript()
    transcript.append("乙" * 2048)

    assert transcript.recognition_context() == "乙" * 2048


def test_recognition_context_discards_leading_fragment_at_unicode_whitespace_boundary() -> None:
    transcript = Transcript()

    transcript.append("甲abc\u2003" + "乙" * 2044)

    assert transcript.recognition_context() == "乙" * 2044


def test_recognition_context_removes_unicode_whitespace_at_the_cut() -> None:
    transcript = Transcript()

    transcript.append("a \u2003beta")

    assert transcript.recognition_context(5) == "beta"


@pytest.mark.parametrize(
    ("recognized_text", "limit", "expected_context"),
    [
        ("alpha beta", 8, "beta"),
        ("alpha beta", 4, "beta"),
        ("alpha-beta", 4, ""),
        ("alpha,beta", 4, ""),
        ("甲乙丙丁", 3, ""),
    ],
)
def test_recognition_context_uses_only_unicode_whitespace_as_a_boundary(
    recognized_text: str, limit: int, expected_context: str
) -> None:
    transcript = Transcript()

    transcript.append(recognized_text)

    assert transcript.recognition_context(limit) == expected_context
