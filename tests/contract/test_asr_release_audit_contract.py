"""Release-audit structure is a reviewed, machine-checkable contract."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

AUDIT_PATH = Path("specs/002-segment-asr/evidence/T030-release-audit.md")
EXPECTED = {
    "FR": {f"FR-{number:03d}" for number in range(1, 27)},
    "SC": {f"SC-{number:03d}" for number in range(1, 7)},
    "WP": {f"WP{number}" for number in range(1, 8)},
    "T": {f"T{number:03d}" for number in range(1, 31)},
}
ROW = re.compile(r"^\| ([^|]+) \| (accepted|pending-review) \| `([^`]+)` \|$")
DECISION = re.compile(r"^S-ASR: (accepted|pending-review)$", re.MULTILINE)


def parse_audit(text: str) -> tuple[dict[str, tuple[str, Path]], str]:
    """Return unique audit rows and the sole supervisor decision."""
    rows: dict[str, tuple[str, Path]] = {}
    for line in text.splitlines():
        match = ROW.match(line)
        if match is None:
            continue
        identifier, state, evidence = match.groups()
        if identifier in rows:
            raise ValueError(f"duplicate audit row: {identifier}")
        rows[identifier] = (state, Path(evidence))

    decisions = DECISION.findall(text)
    if len(decisions) != 1:
        raise ValueError("audit must contain exactly one S-ASR decision")
    return rows, decisions[0]


def assert_audit_contract(text: str, *, draft: bool) -> None:
    rows, decision = parse_audit(text)
    expected_identifiers = set().union(*EXPECTED.values())
    assert set(rows) == expected_identifiers
    assert all(path.is_file() for _, path in rows.values())
    assert "## Non-goals" not in text
    assert "## Explicit non-goals" not in text

    pending = {identifier for identifier, (state, _) in rows.items() if state == "pending-review"}
    expected_pending = {"WP7", "T030"} if draft else set()
    assert pending == expected_pending
    assert decision == ("pending-review" if draft else "accepted")


def fixture_row(identifier: str, evidence: Path, *, draft: bool) -> str:
    state = "pending-review" if draft and identifier in {"WP7", "T030"} else "accepted"
    return f"| {identifier} | {state} | `{evidence}` |"


@pytest.mark.parametrize(
    ("draft", "expected_decision"),
    [
        (True, "pending-review"),
        (False, "accepted"),
    ],
)
def test_release_audit_parser_accepts_controlled_draft_and_final_states(
    tmp_path: Path, draft: bool, expected_decision: str
) -> None:
    evidence = tmp_path / "evidence.md"
    evidence.write_text("evidence\n")
    rows = [
        fixture_row(identifier, evidence, draft=draft)
        for identifiers in EXPECTED.values()
        for identifier in sorted(identifiers)
    ]
    fixture = "\n".join(rows + [f"S-ASR: {expected_decision}"])

    assert_audit_contract(fixture, draft=draft)


def test_release_audit_parser_rejects_a_duplicate_missing_path_non_goal_or_wrong_pending_state(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "evidence.md"
    evidence.write_text("evidence\n")
    rows = [
        fixture_row(identifier, evidence, draft=True)
        for identifiers in EXPECTED.values()
        for identifier in sorted(identifiers)
    ]
    complete = "\n".join(rows + ["S-ASR: pending-review"])
    invalid_audits = [
        "\n".join(rows + [rows[0], "S-ASR: pending-review"]),
        complete.replace(str(evidence), str(tmp_path / "missing.md"), 1),
        "\n".join(rows[1:] + ["S-ASR: pending-review"]),
        complete.replace("S-ASR: pending-review", "## Non-goals\nS-ASR: pending-review"),
        complete.replace("| WP7 | pending-review |", "| WP7 | accepted |"),
    ]

    for invalid in invalid_audits:
        with pytest.raises((AssertionError, ValueError)):
            assert_audit_contract(invalid, draft=True)


def test_final_release_audit_satisfies_the_parser_contract() -> None:
    assert_audit_contract(AUDIT_PATH.read_text(), draft=False)
