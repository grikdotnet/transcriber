"""Structured Transcript assembly from recognized Speech Segment tokens."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

import icu  # type: ignore[import-untyped]

_NFKC = icu.Normalizer2.getNFKCInstance()
_PENDING_SOURCE_SPAN_BYTE_LIMIT = 16_384


@dataclass(frozen=True)
class NormalizationSpan:
    """One non-empty normalized source span with its derived probability."""

    text: str
    probability: float


class Transcript:
    """Accumulate scored, normalized spans in Speech Segment order."""

    def __init__(self) -> None:
        self._spans: list[NormalizationSpan] = []
        self._pending_source: list[str] = []
        self._pending_log_probabilities: list[float] = []
        self._pending_source_byte_count = 0

    def append_token(self, text: str, log_probability: float) -> None:
        """Add one Recognition Token to the current Speech Segment."""
        for code_point in text:
            if self._pending_source and _NFKC.hasBoundaryBefore(code_point):
                self._flush_pending_span()
            code_point_byte_count = len(code_point.encode())
            if (
                self._pending_source_byte_count + code_point_byte_count
                > _PENDING_SOURCE_SPAN_BYTE_LIMIT
            ):
                raise ValueError("Pending Normalization Span exceeds 16,384 UTF-8 bytes")
            self._pending_source.append(code_point)
            self._pending_log_probabilities.append(log_probability)
            self._pending_source_byte_count += code_point_byte_count

    def finish_segment(self) -> None:
        """Complete the current Speech Segment before processing the next one."""
        self._flush_pending_span()

    @property
    def spans(self) -> tuple[NormalizationSpan, ...]:
        """Return the ordered published Normalization Spans."""
        return tuple(self._spans)

    @property
    def text(self) -> str:
        """Return normalized span text without introducing separators."""
        return "".join(span.text for span in self._spans)

    def recognition_context(self, limit: int = 2048) -> str:
        """Return recent normalized transcript text for the next Speech Segment."""
        transcript_text = self.text
        if len(transcript_text) <= limit:
            return transcript_text

        context = transcript_text[-limit:]
        if not transcript_text[-limit - 1].isspace() and not context[0].isspace():
            for index, character in enumerate(context):
                if character.isspace():
                    context = context[index + 1 :]
                    break
            else:
                return ""
        return context.lstrip()

    def encode(self) -> bytes:
        """Return compact UTF-8 Structured Transcript JSON with one final line feed."""
        document = {
            "text": [
                {"text": span.text, "probability": span.probability} for span in self._spans
            ]
        }
        return (json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n").encode()

    def _flush_pending_span(self) -> None:
        if not self._pending_source:
            return

        normalized_text = _NFKC.normalize("".join(self._pending_source))
        if normalized_text:
            probability = math.exp(min(self._pending_log_probabilities))
            self._spans.append(NormalizationSpan(normalized_text, probability))
        self._pending_source.clear()
        self._pending_log_probabilities.clear()
        self._pending_source_byte_count = 0
