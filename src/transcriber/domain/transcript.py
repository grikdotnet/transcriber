"""Pure assembly of recognized Speech Segment text."""

from __future__ import annotations


class Transcript:
    """Accumulate non-empty recognized text in Segment Manifest order."""

    def __init__(self) -> None:
        self._parts: list[str] = []

    def append(self, result_text: str) -> None:
        """Add one successful recognition result when it contains text."""
        trimmed_text = result_text.strip()
        if trimmed_text:
            self._parts.append(trimmed_text)

    @property
    def text(self) -> str:
        """Return all recognized text joined by one ASCII space."""
        return " ".join(self._parts)

    def recognition_context(self, limit: int = 2048) -> str:
        """Return recent transcript text for the next Speech Segment."""
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
        """Return the exact transcript artifact bytes."""
        if not self.text:
            return b""
        return f"{self.text}\n".encode()
