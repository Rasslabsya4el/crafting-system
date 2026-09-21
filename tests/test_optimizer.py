"""Regression checks for the bounded policy-parameter optimizer.

The gate fixture is the hand-computed review1 case from
``docs/specs/2026-09-21-template-optimizer.md`` and the lead's 2026-09-21
review correction.  It is mathematical policy input, not a game fact.
"""

from __future__ import annotations

import pytest

from craftoracle.distributions import DrawEntry, OutcomeClass
from craftoracle.optimizer import (
    _magic_prefix_distribution,
    _normalized_distribution,
    parse_item_level_range,
)
from craftoracle.policy_attempts import evaluate_grouped_schedule


def test_magic_gate_rejection_cannot_reenter_terminal_completion() -> None:
    # First two draws have AC=1/8, AD=1/8, BC=3/8, BD=3/8.  C alone is
    # utility 60, but the two-desired-label gate deliberately rejects BC.
    entries = (
        DrawEntry("A", "Prefix", "A", 1),
        DrawEntry("B", "Prefix", "B", 3),
        DrawEntry("C", "Suffix", "C", 2),
        DrawEntry("D", "Suffix", "D", 2),
    )
    labels = {entry.mod_id: entry.mod_id for entry in entries}
    schedule = evaluate_grouped_schedule(
        entries,
        labels,
        ((2, 1, 1), (1, 3, 3)),
        (lambda outcome: sum(label in {"A", "C"} for label in outcome.labels) >= 2, None),
        # Threshold 60 accepts C alone; the policy gate remains stricter.
        lambda outcome: "C" in outcome.labels,
        early_stop=False,
    )

    first_failure = schedule.failure_by_stage[0]
    assert first_failure[OutcomeClass(("B", "C"), 1, 1)] == pytest.approx(3 / 8)
    terminal = _normalized_distribution({
        outcome: mass
        for stage in schedule.success_by_stage
        for outcome, mass in stage.items()
    })
    assert sum(terminal.values()) == pytest.approx(1)
    assert all({"A", "C"}.issubset(outcome.labels) for outcome in terminal)

    class Target:
        threshold = None
        required_mods = ()
        any_of = ()
        value_table = None

        @staticmethod
        def matches(outcome: OutcomeClass) -> bool:
            return "C" in outcome.labels

    Target.labels = labels

    gates = (
        lambda outcome: sum(label in {"A", "C"} for label in outcome.labels) >= 2,
        None,
    )
    first = _magic_prefix_distribution(
        {}, entries, labels, frozenset({"A", "C"}), ((2, 1, 1), (1, 3, 3)), gates, Target(), False, 0
    )
    second = _magic_prefix_distribution(
        {}, entries, labels, frozenset({"A", "C"}), ((2, 1, 1), (1, 3, 3)), gates, Target(), False, 1
    )
    assert first[OutcomeClass(("A", "C"), 1, 1)] == pytest.approx(1 / 8)
    assert first[OutcomeClass(("B", "C"), 1, 1)] == pytest.approx(3 / 8)
    assert all({"A", "C"}.issubset(outcome.labels) for outcome in second)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10:25", (10, 25)),
        ((10, 25), (10, 25)),
    ],
)
def test_item_level_range_is_explicit_and_inclusive(value: object, expected: tuple[int, int]) -> None:
    assert parse_item_level_range(value) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ("10", "25:10", "x:25", (True, 25)))
def test_item_level_range_rejects_invalid_endpoints(value: object) -> None:
    with pytest.raises(ValueError, match="item level range"):
        parse_item_level_range(value)  # type: ignore[arg-type]
