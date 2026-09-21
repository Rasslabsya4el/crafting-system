"""Indexed hand-computed known answers for the public probability APIs.

Each ``KnownAnswer.derivation`` is the parameter description for its individual
pytest node.  The only source is the synthetic arithmetic in
``docs/mechanics/affix_generation.md``,
``docs/specs/2026-09-21-known-answers.md``,
``docs/specs/2026-09-21-loop-costs.md``, and
``docs/design/build_contract.md``; no game data is used here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest

from craftoracle.costs import chain_cost, compound_geometric_cost, geometric_cost
from craftoracle.distributions import (
    DrawEntry,
    OutcomeClass,
    draw_distribution,
    expected_value,
    mixture_distribution,
    probability,
    scheduled_distribution,
)


@dataclass(frozen=True)
class KnownAnswer:
    """One independently collected hand value and its calculation source."""

    identifier: str
    derivation: str
    expected: float


def _entry(mod_id: str, side: str, group: str, weight: int) -> DrawEntry:
    return DrawEntry(mod_id, side, group, weight)


def _exact(distribution: dict[OutcomeClass, float], *labels: str) -> float:
    return distribution.get(OutcomeClass(tuple(sorted(labels)), len(labels), 0), 0.0)


def _label_mass(distribution: dict[OutcomeClass, float], *labels: str) -> float:
    required = tuple(sorted(labels))
    return probability(
        distribution,
        lambda outcome: all(
            outcome.labels.count(label) >= required.count(label) for label in set(required)
        ),
    )


@pytest.fixture
def abc_two_draws() -> dict[OutcomeClass, float]:
    return draw_distribution(
        [
            _entry("A", "Prefix", "group-A", 1),
            _entry("B", "Prefix", "group-B", 1),
            _entry("C", "Prefix", "group-C", 2),
        ],
        2,
        {"A": "A", "B": "B", "C": "C"},
    )


@pytest.mark.parametrize(
    "answer, measure",
    [
        pytest.param(
            KnownAnswer("KA01", "AB = 1/4*1/3 + 1/4*1/3", 1 / 6),
            lambda distribution: _exact(distribution, "A", "B"),
            id="KA01",
        ),
        pytest.param(
            KnownAnswer("KA02", "AC by the two weighted draw orders", 5 / 12),
            lambda distribution: _exact(distribution, "A", "C"),
            id="KA02",
        ),
        pytest.param(
            KnownAnswer("KA03", "BC by symmetry with AC", 5 / 12),
            lambda distribution: _exact(distribution, "B", "C"),
            id="KA03",
        ),
        pytest.param(
            KnownAnswer("KA04", "P(A) = 1 - (1/4*2/3 + 2/4*1/2)", 7 / 12),
            lambda distribution: _label_mass(distribution, "A"),
            id="KA04",
        ),
        pytest.param(
            KnownAnswer("KA05", "P(B) by A/B symmetry", 7 / 12),
            lambda distribution: _label_mass(distribution, "B"),
            id="KA05",
        ),
        pytest.param(
            KnownAnswer("KA06", "P(C) = 1 - P(AB)", 5 / 6),
            lambda distribution: _label_mass(distribution, "C"),
            id="KA06",
        ),
        pytest.param(
            KnownAnswer("KA07", "P(no A) = P(BC)", 5 / 12),
            lambda distribution: 1 - _label_mass(distribution, "A"),
            id="KA07",
        ),
        pytest.param(
            KnownAnswer("KA08", "P(A and not B) = P(AC)", 5 / 12),
            lambda distribution: _exact(distribution, "A", "C"),
            id="KA08",
        ),
    ],
)
def test_abc_two_weighted_draw_known_answers(
    abc_two_draws: dict[OutcomeClass, float],
    answer: KnownAnswer,
    measure: Callable[[dict[OutcomeClass, float]], float],
) -> None:
    """Source: affix_generation.md weighted draws; each parameter carries its derivation."""
    assert measure(abc_two_draws) == pytest.approx(answer.expected)


@pytest.fixture
def four_equal_three_draws() -> dict[OutcomeClass, float]:
    return draw_distribution(
        [_entry(label, "Prefix", f"group-{label}", 1) for label in "ABCD"],
        3,
        {label: label for label in "ABCD"},
    )


@pytest.mark.parametrize(
    "answer, measure",
    [
        pytest.param(
            KnownAnswer("KA09", "Three of four equal groups contain A in 3/4 outcomes", 3 / 4),
            lambda distribution: _label_mass(distribution, "A"),
            id="KA09",
        ),
        pytest.param(
            KnownAnswer("KA10", "A and B appear in 2 of 4 omitted-group outcomes", 1 / 2),
            lambda distribution: _label_mass(distribution, "A", "B"),
            id="KA10",
        ),
        pytest.param(
            KnownAnswer("KA11", "Exact ABC means D is the omitted equal group", 1 / 4),
            lambda distribution: _exact(distribution, "A", "B", "C"),
            id="KA11",
        ),
    ],
)
def test_four_equal_group_known_answers(
    four_equal_three_draws: dict[OutcomeClass, float],
    answer: KnownAnswer,
    measure: Callable[[dict[OutcomeClass, float]], float],
) -> None:
    """Source: known-answers.md equal-group permutations; parameter holds the derivation."""
    assert measure(four_equal_three_draws) == pytest.approx(answer.expected)


@pytest.fixture
def group_internal_two_draws() -> dict[OutcomeClass, float]:
    return draw_distribution(
        [
            _entry("A1", "Prefix", "group-X", 1),
            _entry("A2", "Prefix", "group-X", 3),
            _entry("B", "Prefix", "group-B", 2),
            _entry("C", "Prefix", "group-C", 2),
        ],
        2,
        {"A1": "hit", "B": "B", "C": "C"},
    )


@pytest.mark.parametrize(
    "answer, measure",
    [
        pytest.param(
            KnownAnswer("KA12", "P(group X in two draws)=5/6, then hit share=1/4", 5 / 24),
            lambda distribution: _label_mass(distribution, "hit"),
            id="KA12",
        ),
        pytest.param(
            KnownAnswer("KA13", "P(hit+B) from group-X share and pair selection", 5 / 48),
            lambda distribution: _label_mass(distribution, "hit", "B"),
            id="KA13",
        ),
        pytest.param(
            KnownAnswer("KA14", "P(B+C) by the two weighted draw orders", 1 / 6),
            lambda distribution: _label_mass(distribution, "B", "C"),
            id="KA14",
        ),
    ],
)
def test_group_internal_known_answers(
    group_internal_two_draws: dict[OutcomeClass, float],
    answer: KnownAnswer,
    measure: Callable[[dict[OutcomeClass, float]], float],
) -> None:
    """Source: group exclusion arithmetic in affix_generation.md; derivation is parameterized."""
    assert measure(group_internal_two_draws) == pytest.approx(answer.expected)


@pytest.fixture
def magic_count_mixture() -> dict[OutcomeClass, float]:
    entries = [_entry("A", "Prefix", "group-A", 1), _entry("B", "Suffix", "group-B", 3)]
    labels = {"A": "A", "B": "B"}
    return mixture_distribution(
        [
            (1, draw_distribution(entries, 1, labels, prefix_cap=1, suffix_cap=1)),
            (1, draw_distribution(entries, 2, labels, prefix_cap=1, suffix_cap=1)),
        ]
    )


@pytest.mark.parametrize(
    "answer, measure",
    [
        pytest.param(
            KnownAnswer("KA15", "Half count-1 mass times P(A)=1/4", 1 / 8),
            lambda distribution: probability(distribution, lambda outcome: outcome.labels == ("A",)),
            id="KA15",
        ),
        pytest.param(
            KnownAnswer("KA16", "Half count-1 mass times P(B)=3/4", 3 / 8),
            lambda distribution: probability(distribution, lambda outcome: outcome.labels == ("B",)),
            id="KA16",
        ),
        pytest.param(
            KnownAnswer("KA17", "Count-2 branch always has A and B", 1 / 2),
            lambda distribution: _label_mass(distribution, "A", "B"),
            id="KA17",
        ),
        pytest.param(
            KnownAnswer("KA18", "P(A)=1/8 + 1/2", 5 / 8),
            lambda distribution: _label_mass(distribution, "A"),
            id="KA18",
        ),
        pytest.param(
            KnownAnswer("KA19", "E[count]=(1 + 2)/2", 3 / 2),
            lambda distribution: expected_value(
                distribution, lambda outcome: outcome.prefixes + outcome.suffixes
            ),
            id="KA19",
        ),
    ],
)
def test_magic_count_mixture_known_answers(
    magic_count_mixture: dict[OutcomeClass, float],
    answer: KnownAnswer,
    measure: Callable[[dict[OutcomeClass, float]], float],
) -> None:
    """Source: known-answers.md count-1/count-2 half mixture; derivation is parameterized."""
    assert measure(magic_count_mixture) == pytest.approx(answer.expected)


@pytest.fixture
def staged_four_groups() -> dict[OutcomeClass, float]:
    return scheduled_distribution(
        [
            _entry("A", "Prefix", "group-A", 1),
            _entry("B", "Prefix", "group-B", 1),
            _entry("C", "Suffix", "group-C", 1),
            _entry("D", "Suffix", "group-D", 1),
        ],
        [(2, 1, 1), (1, 3, 3)],
        {label: label for label in "ABCD"},
    )


@pytest.mark.parametrize(
    "answer, measure",
    [
        pytest.param(
            KnownAnswer("KA20", "Four equiprobable three-label stage outcomes: ABC", 1 / 4),
            lambda distribution: probability(
                distribution, lambda outcome: outcome.labels == ("A", "B", "C")
            ),
            id="KA20",
        ),
        pytest.param(
            KnownAnswer("KA21", "Four equiprobable three-label stage outcomes: ABD", 1 / 4),
            lambda distribution: probability(
                distribution, lambda outcome: outcome.labels == ("A", "B", "D")
            ),
            id="KA21",
        ),
        pytest.param(
            KnownAnswer("KA22", "A is absent only from BCD", 3 / 4),
            lambda distribution: _label_mass(distribution, "A"),
            id="KA22",
        ),
    ],
)
def test_scheduled_stage_known_answers(
    staged_four_groups: dict[OutcomeClass, float],
    answer: KnownAnswer,
    measure: Callable[[dict[OutcomeClass, float]], float],
) -> None:
    """Source: known-answers.md staged 2-at-1/1 then 1-at-3/3 permutations."""
    assert measure(staged_four_groups) == pytest.approx(answer.expected)


@pytest.fixture
def side_capped_two_draws() -> dict[OutcomeClass, float]:
    return draw_distribution(
        [
            _entry("A", "Prefix", "group-A", 1),
            _entry("B", "Prefix", "group-B", 3),
            _entry("C", "Suffix", "group-C", 2),
        ],
        2,
        {label: label for label in "ABC"},
        prefix_cap=1,
        suffix_cap=1,
    )


@pytest.mark.parametrize(
    "answer, measure",
    [
        pytest.param(
            KnownAnswer("KA23", "AC = A-first 1/6 + C-first 1/3*1/4", 1 / 4),
            lambda distribution: probability(
                distribution, lambda outcome: outcome.labels == ("A", "C")
            ),
            id="KA23",
        ),
        pytest.param(
            KnownAnswer("KA24", "BC is the remaining side-capped mass", 3 / 4),
            lambda distribution: probability(
                distribution, lambda outcome: outcome.labels == ("B", "C")
            ),
            id="KA24",
        ),
    ],
)
def test_side_capped_known_answers(
    side_capped_two_draws: dict[OutcomeClass, float],
    answer: KnownAnswer,
    measure: Callable[[dict[OutcomeClass, float]], float],
) -> None:
    """Source: known-answers.md side-cap calculation; parameter carries each arithmetic result."""
    assert measure(side_capped_two_draws) == pytest.approx(answer.expected)


@pytest.fixture
def blocked_a_one_draw() -> dict[OutcomeClass, float]:
    return draw_distribution(
        [
            _entry("A", "Prefix", "group-A", 1),
            _entry("B", "Prefix", "group-B", 1),
            _entry("C", "Prefix", "group-C", 2),
        ],
        1,
        {label: label for label in "ABC"},
        blocked_groups=("group-A",),
    )


@pytest.mark.parametrize(
    "answer, label",
    [
        pytest.param(KnownAnswer("KA25", "Blocked A leaves B:C weights 1:2", 1 / 3), "B", id="KA25"),
        pytest.param(KnownAnswer("KA26", "Blocked A leaves B:C weights 1:2", 2 / 3), "C", id="KA26"),
    ],
)
def test_blocked_group_known_answers(
    blocked_a_one_draw: dict[OutcomeClass, float], answer: KnownAnswer, label: str
) -> None:
    """Source: known-answers.md blocked-group single-draw ratio; derivation is parameterized."""
    assert _label_mass(blocked_a_one_draw, label) == pytest.approx(answer.expected)


@pytest.fixture
def utility_distribution() -> dict[OutcomeClass, float]:
    return {
        OutcomeClass(("A",), 1, 0): 1 / 2,
        OutcomeClass(("B",), 1, 0): 1 / 3,
        OutcomeClass(("C",), 1, 0): 1 / 6,
    }


@pytest.mark.parametrize(
    "answer, measure",
    [
        pytest.param(
            KnownAnswer("KA27", "0*1/2 + 6*1/3 + 10*1/6", 11 / 3),
            lambda distribution: expected_value(
                distribution, lambda outcome: {"A": 0, "B": 6, "C": 10}[outcome.labels[0]]
            ),
            id="KA27",
        ),
        pytest.param(
            KnownAnswer("KA28", "P(value >= 6) = 1/3 + 1/6", 1 / 2),
            lambda distribution: probability(
                distribution, lambda outcome: {"A": 0, "B": 6, "C": 10}[outcome.labels[0]] >= 6
            ),
            id="KA28",
        ),
        pytest.param(
            KnownAnswer("KA29", "P(value >= 10) = 1/6", 1 / 6),
            lambda distribution: probability(
                distribution, lambda outcome: {"A": 0, "B": 6, "C": 10}[outcome.labels[0]] >= 10
            ),
            id="KA29",
        ),
    ],
)
def test_utility_known_answers(
    utility_distribution: dict[OutcomeClass, float],
    answer: KnownAnswer,
    measure: Callable[[dict[OutcomeClass, float]], float],
) -> None:
    """Source: build_contract.md synthetic utility distribution; each parameter shows arithmetic."""
    assert measure(utility_distribution) == pytest.approx(answer.expected)


@pytest.mark.parametrize(
    "answer, attribute",
    [
        pytest.param(KnownAnswer("KA30", "E[N] = 1/(1/2)", 2), "expected_attempts", id="KA30"),
        pytest.param(KnownAnswer("KA31", "E[C] = 2*E[N]", 4), "expected_cost", id="KA31"),
        pytest.param(KnownAnswer("KA32", "Geom(1/2) first CDF >= .9 is N=4", 4), "attempts_p90", id="KA32"),
        pytest.param(KnownAnswer("KA33", "p90 cost = 2*4", 8), "cost_p90", id="KA33"),
    ],
)
def test_half_price_two_geometric_known_answers(answer: KnownAnswer, attribute: str) -> None:
    """Source: docs/specs/2026-09-21-loop-costs.md; parameter carries the formula."""
    assert getattr(geometric_cost(1 / 2, 2), attribute) == pytest.approx(answer.expected)


@pytest.mark.parametrize(
    "answer, attribute",
    [
        pytest.param(KnownAnswer("KA34", "E[C] = 2/(1/6)", 12), "expected_cost", id="KA34"),
        pytest.param(KnownAnswer("KA35", "Geom(1/6) p90 attempts=13, cost=2*13", 26), "cost_p90", id="KA35"),
    ],
)
def test_sixth_price_two_geometric_known_answers(answer: KnownAnswer, attribute: str) -> None:
    """Source: docs/specs/2026-09-21-loop-costs.md p=1/6 bounds; derivation is parameterized."""
    assert getattr(geometric_cost(1 / 6, 2), attribute) == pytest.approx(answer.expected)


@pytest.mark.parametrize(
    "answer, attribute",
    [
        pytest.param(KnownAnswer("KA36", "Two independent E[Geom(1/2)] costs: 2+2", 4), "expected_cost", id="KA36"),
        pytest.param(
            KnownAnswer("KA37", "Chain CDF6=57/64<.9 and CDF7=15/16>=.9", 7),
            "cost_p90",
            id="KA37",
        ),
    ],
)
def test_two_stage_chain_known_answers(answer: KnownAnswer, attribute: str) -> None:
    """Source: docs/specs/2026-09-21-loop-costs.md chain values; derivation is parameterized."""
    result = chain_cost([(1 / 2, 1, 0, 0), (1 / 2, 1, 0, 0)])
    assert getattr(result, attribute) == pytest.approx(answer.expected)


@pytest.mark.parametrize(
    "answer, attribute",
    [
        pytest.param(
            KnownAnswer("KA38", "E[attempt price]=(1+2)/2; E[C]=2*3/2", 3),
            "expected_cost",
            id="KA38",
        ),
        pytest.param(
            KnownAnswer("KA39", "Compound CDF5=.8798828125 < .9 <= CDF6=.924072265625", 6),
            "cost_p90",
            id="KA39",
        ),
    ],
)
def test_compound_geometric_known_answers(answer: KnownAnswer, attribute: str) -> None:
    """Source: docs/specs/2026-09-21-loop-costs.md compound CDF; derivation is parameterized."""
    result = compound_geometric_cost(1 / 2, [(1, 1), (2, 1)])
    assert getattr(result, attribute) == pytest.approx(answer.expected)


@pytest.mark.parametrize(
    "answer, attribute",
    [
        pytest.param(
            KnownAnswer("KA40", "7 + 2*E[N] + 3*(E[N]-1)", 14),
            "expected_cost",
            id="KA40",
        ),
        pytest.param(
            KnownAnswer("KA41", "setup 7 + 2*4 + 3*(4-1)", 24),
            "cost_p90",
            id="KA41",
        ),
    ],
)
def test_geometric_reset_setup_known_answers(answer: KnownAnswer, attribute: str) -> None:
    """Source: docs/specs/2026-09-21-loop-costs.md reset/setup formula; derivation is parameterized."""
    result = geometric_cost(1 / 2, 2, reset_cost=3, setup_cost=7)
    assert getattr(result, attribute) == pytest.approx(answer.expected)
