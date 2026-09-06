from __future__ import annotations

from collections.abc import Iterator


class CallLog:
    """Ordered event recorder for workflow and boundary fakes."""

    def __init__(self) -> None:
        self._events: list[str] = []

    def record(self, event: str) -> None:
        self._events.append(event)

    @property
    def events(self) -> tuple[str, ...]:
        return tuple(self._events)

    def __iter__(self) -> Iterator[str]:
        return iter(self._events)

    def __len__(self) -> int:
        return len(self._events)
