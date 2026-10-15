"""Hand-calculated full-recording agreement and gap policy."""

from collections.abc import Iterable

import pytest

from tests.support.diarization import COMMUNITY_PREDICTION, NEMOTRON_PREDICTION
from transcriber.domain.diarization import (
    CommunityPrediction,
    NemotronPrediction,
    SpeakerActivity,
    clip_nemotron_prediction,
    fuse_predictions,
)


def base(*rows: tuple[float, float, int]) -> NemotronPrediction:
    return NemotronPrediction(tuple(SpeakerActivity(*row) for row in rows))


def secondary(*rows: tuple[float, float, str]) -> CommunityPrediction:
    return CommunityPrediction(tuple(SpeakerActivity(*row) for row in rows))


def solver(matrix: tuple[tuple[float, ...], ...]) -> Iterable[tuple[int, int]]:
    return tuple((i, i) for i in range(min(len(matrix), len(matrix[0]))))


def test_shared_full_recording_example_fills_both_gaps() -> None:
    assert fuse_predictions(
        base(*NEMOTRON_PREDICTION), secondary(*COMMUNITY_PREDICTION), 10, solver
    ) == (
        SpeakerActivity(0, 5, 1),
        SpeakerActivity(5, 10, 2),
    )


def test_sweep_clips_counts_duplicates_and_excludes_true_overlap() -> None:
    matrices = []

    def capture(matrix: tuple[tuple[float, ...], ...]) -> Iterable[tuple[int, int]]:
        matrices.append(matrix)
        return ((0, 0),)

    result = fuse_predictions(
        base((-2, 4, 1), (1, 3, 1), (3, 5, 2), (8, 8, 9), (12, 14, 8)),
        secondary((-1, 6, "a"), (1, 2, "a"), (4, 5, "b")),
        7,
        capture,
    )
    assert matrices == [((3.0, 0.0), (0.0, 0.0))]
    assert result == (SpeakerActivity(0, 4, 1), SpeakerActivity(3, 5, 2), SpeakerActivity(5, 6, 1))


def test_sorted_rectangular_matrix_and_partial_assignment() -> None:
    def capture(matrix: tuple[tuple[float, ...], ...]) -> Iterable[tuple[int, int]]:
        assert matrix == ((0, 3), (3, 0), (0, 0))
        return ((0, 1), (1, 0))

    assert fuse_predictions(
        base((0, 3, 2), (4, 7, 1)), secondary((0, 4, "a"), (4, 8, "b"), (8, 9, "c")), 9, capture
    ) == (
        SpeakerActivity(0, 4, 2),
        SpeakerActivity(4, 8, 1),
    )


@pytest.mark.parametrize("seconds,accepted", [(3, True), (3 - 1e-10, False)])
def test_duration_threshold_is_inclusive_without_tolerance(seconds: float, accepted: bool) -> None:
    result = fuse_predictions(base((0, seconds, 1)), secondary((0, 5, "a")), 5, solver)
    assert result == (SpeakerActivity(0, 5 if accepted else seconds, 1),)


@pytest.mark.parametrize("paired,other,accepted", [(7, 3, True), (7 - 1e-10, 3 + 1e-10, False)])
def test_support_uses_row_agreement_not_secondary_duration(
    paired: float, other: float, accepted: bool
) -> None:
    result = fuse_predictions(
        base((0, paired, 1), (paired, paired + other, 2)), secondary((0, 20, "a")), 20, solver
    )
    expected = [SpeakerActivity(0, paired, 1), SpeakerActivity(paired, paired + other, 2)]
    if accepted:
        expected.append(SpeakerActivity(10, 20, 1))
    assert result == tuple(expected)


def test_rejected_hungarian_pair_is_not_reassigned() -> None:
    calls = []

    def assigned(matrix: tuple[tuple[float, ...], ...]) -> Iterable[tuple[int, int]]:
        calls.append(matrix)
        return ((0, 1), (1, 0))

    # a prefers 1, but assignment reserves 1 for b; a is rejected without retry.
    result = fuse_predictions(
        base((0, 8, 1), (8, 12, 2), (13, 18, 1)),
        secondary((0, 13, "a"), (13, 19, "b")),
        19,
        assigned,
    )
    assert len(calls) == 1
    assert result == (
        SpeakerActivity(0, 8, 1),
        SpeakerActivity(8, 12, 2),
        SpeakerActivity(13, 19, 1),
    )


def test_secondary_overlap_and_unmapped_labels_do_not_fill() -> None:
    assert fuse_predictions(
        base((0, 4, 1)), secondary((0, 8, "a"), (5, 6, "b"), (8, 9, "c")), 10, solver
    ) == (
        SpeakerActivity(0, 5, 1),
        SpeakerActivity(6, 8, 1),
    )


@pytest.mark.parametrize(
    "primary,community",
    [
        (base(), secondary()),
        (base((0, 3, 1)), secondary((3, 5, "a"))),
        (base((0, 5, 1), (0, 5, 2)), secondary((0, 5, "a"))),
    ],
)
def test_no_evidence_never_calls_solver(
    primary: NemotronPrediction, community: CommunityPrediction
) -> None:
    def forbidden(matrix: tuple[tuple[float, ...], ...]) -> Iterable[tuple[int, int]]:
        raise AssertionError("solver called without evidence")

    assert (
        fuse_predictions(primary, community, 5, forbidden)
        == clip_nemotron_prediction(primary, 5).activity
    )


@pytest.mark.parametrize(
    "row", [(float("nan"), 2, 1), (0, float("inf"), 1), (0, 1, True), (0, 1, 0), (0, 1, "x")]
)
def test_invalid_base_values_rejected(row: tuple[float, float, int]) -> None:
    with pytest.raises(ValueError):
        clip_nemotron_prediction(base(row), 5)


@pytest.mark.parametrize("label", ["", 1, True])
def test_invalid_secondary_labels_rejected(label: str) -> None:
    with pytest.raises(ValueError):
        fuse_predictions(base(), secondary((0, 1, label)), 5, solver)


def test_clip_observed_id_input_discards_collapsed_and_outside_rows() -> None:
    assert clip_nemotron_prediction(base((-1, 2, 2), (1, 3, 2), (4, 4, 3), (6, 7, 4)), 5) == base(
        (0, 3, 2)
    )


@pytest.mark.parametrize("difference,expected", [(0.0, True), (5e-10, True), (2e-9, False)])
def test_row_maximum_near_tie_tolerance(difference: float, expected: bool) -> None:
    # Near ties cannot pass .70 support; inspect the independent maximum predicate.
    from transcriber.domain.diarization import _is_row_maximum

    assert _is_row_maximum(4.0, (4.0, 4.0 + difference)) is expected


def test_wide_rectangular_assignment_preserves_unmatched_base_identities() -> None:
    def capture(matrix: tuple[tuple[float, ...], ...]) -> Iterable[tuple[int, int]]:
        assert matrix == ((1.0, 4.0, 0.0),)
        return ((0, 1),)

    assert fuse_predictions(
        base((0, 1, 1), (1, 5, 2), (7, 8, 3)),
        secondary((0, 6, "a")),
        9,
        capture,
    ) == (SpeakerActivity(0, 1, 1), SpeakerActivity(1, 6, 2), SpeakerActivity(7, 8, 3))


def test_empty_secondary_preserves_all_clipped_overlapping_base_activity() -> None:
    assert fuse_predictions(
        base((-1, 4, 2), (1, 3, 1), (2, 6, 2), (2, 5, 3)),
        secondary(),
        5,
        solver,
    ) == (SpeakerActivity(0, 5, 2), SpeakerActivity(1, 3, 1), SpeakerActivity(2, 5, 3))


@pytest.mark.parametrize("duration", [-1.0, float("nan"), float("inf")])
def test_invalid_recording_duration_is_rejected(duration: float) -> None:
    with pytest.raises(ValueError):
        clip_nemotron_prediction(base(), duration)


def test_nonfinite_secondary_time_is_rejected_even_without_base_activity() -> None:
    with pytest.raises(ValueError):
        fuse_predictions(base(), secondary((0, float("nan"), "a")), 5, solver)
