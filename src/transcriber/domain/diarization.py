"""Pure full-recording speaker agreement, gap filling and exact sample masking."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from math import isfinite

from transcriber.domain.manifest import SegmentManifest


@dataclass(frozen=True, slots=True)
class SpeakerActivity[Label: (int, str)]:
    start_seconds: float
    end_seconds: float
    speaker_id: Label


@dataclass(frozen=True, slots=True)
class NemotronPrediction:
    activity: tuple[SpeakerActivity[int], ...]


@dataclass(frozen=True, slots=True)
class CommunityPrediction:
    activity: tuple[SpeakerActivity[str], ...]


@dataclass(frozen=True, slots=True)
class SampleSpeakerActivity:
    speaker_id: int
    start_sample: int
    end_sample: int


type AssignmentSolver = Callable[[tuple[tuple[float, ...], ...]], Iterable[tuple[int, int]]]


@dataclass(frozen=True, slots=True)
class _ElementaryInterval:
    start: float
    end: float
    base: frozenset[int]
    secondary: frozenset[str]


def _clip[Label: (int, str)](
    activity: tuple[SpeakerActivity[Label], ...], duration: float, label_type: type[Label]
) -> tuple[SpeakerActivity[Label], ...]:
    if not isfinite(duration) or duration < 0:
        raise ValueError("duration must be finite and nonnegative")
    result = []
    for row in activity:
        label = row.speaker_id
        if (
            not isinstance(label, label_type)
            or isinstance(label, bool)
            or (isinstance(label, int) and label <= 0)
            or (isinstance(label, str) and not label)
            or not isfinite(row.start_seconds)
            or not isfinite(row.end_seconds)
        ):
            raise ValueError("invalid speaker activity")
        start, end = max(0.0, row.start_seconds), min(duration, row.end_seconds)
        if start < end:
            result.append(SpeakerActivity(start, end, label))
    return tuple(result)


def _merge[Label: (int, str)](
    activity: Iterable[SpeakerActivity[Label]],
) -> tuple[SpeakerActivity[Label], ...]:
    result: list[SpeakerActivity[Label]] = []
    for row in sorted(
        activity, key=lambda row: (row.speaker_id, row.start_seconds, row.end_seconds)
    ):
        if (
            result
            and result[-1].speaker_id == row.speaker_id
            and row.start_seconds <= result[-1].end_seconds
        ):
            previous = result.pop()
            result.append(
                SpeakerActivity(
                    previous.start_seconds,
                    max(previous.end_seconds, row.end_seconds),
                    row.speaker_id,
                )
            )
        else:
            result.append(row)
    return tuple(
        sorted(result, key=lambda row: (row.start_seconds, row.speaker_id, row.end_seconds))
    )


def clip_nemotron_prediction(
    prediction: NemotronPrediction, duration_seconds: float
) -> NemotronPrediction:
    """Return clipped, merged activity; distinct IDs supply the observed count."""
    return NemotronPrediction(_merge(_clip(prediction.activity, duration_seconds, int)))


def _sweep(
    base: tuple[SpeakerActivity[int], ...],
    secondary: tuple[SpeakerActivity[str], ...],
    duration: float,
) -> tuple[_ElementaryInterval, ...]:
    base_events: dict[float, Counter[int]] = defaultdict(Counter)
    secondary_events: dict[float, Counter[str]] = defaultdict(Counter)
    for row in base:
        base_events[row.start_seconds][row.speaker_id] += 1
        base_events[row.end_seconds][row.speaker_id] -= 1
    for secondary_row in secondary:
        secondary_events[secondary_row.start_seconds][secondary_row.speaker_id] += 1
        secondary_events[secondary_row.end_seconds][secondary_row.speaker_id] -= 1
    boundaries = sorted({0.0, duration, *base_events, *secondary_events})
    active_base: Counter[int] = Counter()
    active_secondary: Counter[str] = Counter()
    result = []
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        active_base.update(base_events[start])
        active_secondary.update(secondary_events[start])
        result.append(
            _ElementaryInterval(
                start,
                end,
                frozenset(k for k, v in active_base.items() if v > 0),
                frozenset(k for k, v in active_secondary.items() if v > 0),
            )
        )
    return tuple(result)


def _is_row_maximum(paired: float, row: tuple[float, ...]) -> bool:
    return abs(paired - max(row)) <= 1e-9


def fuse_predictions(
    base: NemotronPrediction,
    secondary: CommunityPrediction,
    duration_seconds: float,
    solver: AssignmentSolver,
) -> tuple[SpeakerActivity[int], ...]:
    """Maximize agreement once through solver(matrix), then filter proposed pairs.

    Matrix rows use sorted Community-1 labels; columns use sorted Nemotron IDs.
    The injected solver returns (row, column) pairs for a rectangular maximum
    assignment. Solver execution failures propagate to the workflow.
    """
    primary = _clip(base.activity, duration_seconds, int)
    community = _clip(secondary.activity, duration_seconds, str)
    intervals = _sweep(primary, community, duration_seconds)
    ids = sorted({row.speaker_id for row in primary})
    labels = sorted({row.speaker_id for row in community})
    agreement = {label: dict.fromkeys(ids, 0.0) for label in labels}
    for interval in intervals:
        if len(interval.base) == len(interval.secondary) == 1:
            agreement[next(iter(interval.secondary))][next(iter(interval.base))] += (
                interval.end - interval.start
            )
    matrix = tuple(tuple(agreement[label][identity] for identity in ids) for label in labels)
    accepted: dict[str, int] = {}
    if any(any(row) for row in matrix):
        used_rows: set[int] = set()
        used_columns: set[int] = set()
        for row_index, column_index in solver(matrix):
            if (
                not (0 <= row_index < len(labels) and 0 <= column_index < len(ids))
                or row_index in used_rows
                or column_index in used_columns
            ):
                raise ValueError("solver must return a partial one-to-one assignment")
            used_rows.add(row_index)
            used_columns.add(column_index)
            row = matrix[row_index]
            paired, denominator = row[column_index], sum(row)
            if (
                paired >= 3.0
                and denominator > 0
                and paired / denominator >= 0.70
                and _is_row_maximum(paired, row)
            ):
                accepted[labels[row_index]] = ids[column_index]
    fused: list[SpeakerActivity[int]] = []
    for interval in intervals:
        active = interval.base
        if not active and len(interval.secondary) == 1:
            identity = accepted.get(next(iter(interval.secondary)))
            if identity is not None:
                active = frozenset((identity,))
        fused.extend(SpeakerActivity(interval.start, interval.end, identity) for identity in active)
    return _merge(fused)


def mask_activity(
    activity: tuple[SpeakerActivity[int], ...], manifest: SegmentManifest
) -> tuple[SampleSpeakerActivity, ...]:
    """Round seconds ties-to-even, clamp, and intersect the exact prepared union."""
    total = manifest.audio.total_samples
    rate = manifest.audio.sample_rate_hz
    clipped = _clip(activity, total / rate, int)
    samples: list[SampleSpeakerActivity] = []
    for row in clipped:
        start, end = (
            max(0, min(total, round(row.start_seconds * rate))),
            max(0, min(total, round(row.end_seconds * rate))),
        )
        for region in manifest.segments:
            left, right = max(start, region.start_sample), min(end, region.end_sample)
            if left < right:
                samples.append(SampleSpeakerActivity(row.speaker_id, left, right))
    merged: list[SampleSpeakerActivity] = []
    for sample_row in sorted(
        samples,
        key=lambda sample_row: (
            sample_row.speaker_id,
            sample_row.start_sample,
            sample_row.end_sample,
        ),
    ):
        if (
            merged
            and merged[-1].speaker_id == sample_row.speaker_id
            and sample_row.start_sample <= merged[-1].end_sample
        ):
            previous = merged.pop()
            merged.append(
                SampleSpeakerActivity(
                    sample_row.speaker_id,
                    previous.start_sample,
                    max(previous.end_sample, sample_row.end_sample),
                )
            )
        else:
            merged.append(sample_row)
    return tuple(
        sorted(
            merged,
            key=lambda sample_row: (
                sample_row.start_sample,
                sample_row.speaker_id,
                sample_row.end_sample,
            ),
        )
    )
