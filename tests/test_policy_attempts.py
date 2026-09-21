"""Mathematical fixtures for finite policy attempts and renewal costs.

All numbers in this file come from ``docs/design/parameter-search.md`` and
``docs/specs/2026-09-21-policy-attempt-kernel.md``.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from craftoracle.distributions import DrawEntry, OutcomeClass
from craftoracle.policy_attempts import (
    correlated_attempt_metrics,
    estimate_correlated_attempt_p90,
    estimate_protected_cycle_p90,
    evaluate_grouped_schedule,
    protected_cycle_metrics,
    terminal_cost_atoms,
)


def _entry(mod_id: str, group: str, weight: int, *, label: str | None = None) -> DrawEntry:
    return DrawEntry(mod_id, "Prefix", group, weight)


def _abc_entries() -> tuple[list[DrawEntry], dict[str, str]]:
    entries = [
        _entry("A", "A", 1),
        _entry("B", "B", 1),
        _entry("C", "C", 2),
    ]
    return entries, {entry.mod_id: entry.mod_id for entry in entries}


def _bounded_cdf(
    numerator: dict[int, float], recurrence: dict[int, float], maximum_cost: int
) -> list[float]:
    """Independent coefficient recurrence for a rational probability PGF."""
    masses = [0.0] * (maximum_cost + 1)
    for cost in range(maximum_cost + 1):
        masses[cost] = numerator.get(cost, 0.0) + math.fsum(
            coefficient * masses[cost - shift]
            for shift, coefficient in recurrence.items()
            if cost >= shift
        )
    return [math.fsum(masses[: cost + 1]) for cost in range(maximum_cost + 1)]


def test_gated_schedule_reports_unconditional_terminal_masses_and_paid_stages() -> None:
    entries, labels = _abc_entries()
    result = evaluate_grouped_schedule(
        entries,
        labels,
        stages=((1, 3, 3), (1, 3, 3)),
        continue_predicates=(lambda outcome: "A" in outcome.labels, None),
        target_predicate=lambda outcome: {"A", "C"}.issubset(outcome.labels),
    )

    assert result.success_by_stage[0] == {}
    assert result.success_by_stage[1] == {
        OutcomeClass(("A", "C"), 2, 0): pytest.approx(1 / 6)
    }
    assert result.failure_by_stage[0] == {
        OutcomeClass(("B",), 1, 0): pytest.approx(1 / 4),
        OutcomeClass(("C",), 1, 0): pytest.approx(1 / 2),
    }
    assert result.failure_by_stage[1] == {
        OutcomeClass(("A", "B"), 2, 0): pytest.approx(1 / 12)
    }
    assert result.stage_reach_probabilities == pytest.approx((1, 1 / 4))
    assert result.success_probability == pytest.approx(1 / 6)
    assert result.failure_probability == pytest.approx(5 / 6)
    assert result.peak_live_states == 3

    atoms = terminal_cost_atoms(result, (2, 3))
    assert atoms.unconditional_attempt_mean == pytest.approx(11 / 4)
    assert atoms.success_atoms == ((5.0, 1.0),)
    assert atoms.failure_atoms == ((2.0, pytest.approx(0.9)), (5.0, pytest.approx(0.1)))
    cost = correlated_attempt_metrics(
        atoms.success_probability,
        atoms.success_atoms,
        atoms.failure_atoms,
        reset_cost=1,
        setup_cost=7,
    )
    assert cost.mean_attempt_cost == pytest.approx(11 / 4)
    assert cost.mean_cost == pytest.approx(28.5)

    no_setup = correlated_attempt_metrics(
        atoms.success_probability, atoms.success_atoms, atoms.failure_atoms, reset_cost=1
    )
    assert no_setup.mean_cost == pytest.approx(21.5)
    estimate = estimate_correlated_attempt_p90(
        atoms.success_probability,
        atoms.success_atoms,
        atoms.failure_atoms,
        reset_cost=1,
        rng=np.random.default_rng(20260921),
    )
    cdf = _bounded_cdf({5: 1 / 6}, {3: 3 / 4, 6: 1 / 12}, 44)
    assert cdf[43] == pytest.approx(.8841585481908151)
    assert cdf[44] == pytest.approx(.9017383732824877)
    assert next(cost for cost, mass in enumerate(cdf) if mass >= .9) == 44
    assert estimate.interval_lower <= 44 <= estimate.interval_upper


def test_schedule_keeps_group_identity_through_projected_label_gate() -> None:
    entries = [
        _entry("gate-light", "light", 1),
        _entry("gate-heavy", "heavy", 2),
        _entry("target", "target", 1),
    ]
    labels = {"gate-light": "gate", "gate-heavy": "gate", "target": "target"}
    result = evaluate_grouped_schedule(
        entries,
        labels,
        stages=((1, 3, 3), (1, 3, 3)),
        continue_predicates=(lambda outcome: "gate" in outcome.labels, None),
        target_predicate=lambda outcome: {"gate", "target"}.issubset(outcome.labels),
    )

    assert result.success_by_stage[1] == {
        OutcomeClass(("gate", "target"), 2, 0): pytest.approx(1 / 3)
    }
    assert result.failure_by_stage[0] == {
        OutcomeClass(("target",), 1, 0): pytest.approx(1 / 4)
    }
    assert result.failure_by_stage[1] == {
        OutcomeClass(("gate", "gate"), 2, 0): pytest.approx(5 / 12)
    }


def test_early_stop_absorbs_success_before_gate_and_final_only_mode_delays_it() -> None:
    entries, labels = _abc_entries()
    full = evaluate_grouped_schedule(
        entries,
        labels,
        stages=((2, 3, 3),),
        target_predicate=lambda _outcome: False,
        early_stop=False,
    )
    early = evaluate_grouped_schedule(
        entries,
        labels,
        stages=((1, 3, 3), (1, 3, 3)),
        continue_predicates=(lambda _outcome: True, None),
        target_predicate=lambda outcome: "A" in outcome.labels,
        early_stop=True,
    )
    final_only = evaluate_grouped_schedule(
        entries,
        labels,
        stages=((1, 3, 3), (1, 3, 3)),
        continue_predicates=(lambda _outcome: True, None),
        target_predicate=lambda outcome: "A" in outcome.labels,
        early_stop=False,
    )

    assert sum(early.success_by_stage[0].values()) == pytest.approx(1 / 4)
    assert sum(early.success_by_stage[1].values()) == pytest.approx(1 / 3)
    assert early.stage_reach_probabilities == pytest.approx((1, 3 / 4))
    assert sum(final_only.success_by_stage[0].values()) == 0
    assert final_only.success_probability == pytest.approx(7 / 12)
    assert final_only.stage_reach_probabilities == pytest.approx((1, 1))
    assert full.failure_by_stage[0][OutcomeClass(("A", "C"), 2, 0)] == pytest.approx(5 / 12)


def test_schedule_rejects_bad_contracts() -> None:
    entries, labels = _abc_entries()
    with pytest.raises(ValueError, match="stages"):
        evaluate_grouped_schedule(entries, labels, (), (), lambda _outcome: False)
    with pytest.raises(ValueError, match="continue_predicates"):
        evaluate_grouped_schedule(
            entries,
            labels,
            ((1, 3, 3),),
            ("not callable",),  # type: ignore[arg-type]
            lambda _outcome: False,
        )
    with pytest.raises(ValueError, match="target_predicate"):
        evaluate_grouped_schedule(entries, labels, ((1, 3, 3),), (), None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="weight"):
        evaluate_grouped_schedule(
            [DrawEntry("bad", "Prefix", "bad", 0)],
            labels,
            ((1, 3, 3),),
            (),
            lambda _outcome: False,
        )
    with pytest.raises(ValueError, match="cannot shrink"):
        evaluate_grouped_schedule(
            entries,
            labels,
            ((1, 3, 3), (1, 2, 3)),
            target_predicate=lambda _outcome: False,
        )


def test_final_only_target_uses_the_last_reachable_exhausted_stage() -> None:
    result = evaluate_grouped_schedule(
        [_entry("A", "A", 1)],
        {"A": "A"},
        ((1, 3, 3), (1, 3, 3)),
        target_predicate=lambda outcome: "A" in outcome.labels,
        early_stop=False,
    )
    assert result.success_by_stage[0] == {OutcomeClass(("A",), 1, 0): pytest.approx(1)}
    assert result.failure_by_stage[0] == {}
    assert result.stage_reach_probabilities == pytest.approx((1, 0))
    assert terminal_cost_atoms(result, (2, 3)).unconditional_attempt_mean == 2


def test_correlated_attempt_exact_mean_p90_and_dkw_metadata() -> None:
    metrics = correlated_attempt_metrics(
        .5,
        ((4, 1),),
        ((1, 1),),
        reset_cost=1,
    )
    assert metrics.mean_attempt_cost == pytest.approx(2.5)
    assert metrics.mean_cost == pytest.approx(6)

    first = estimate_correlated_attempt_p90(
        .5,
        ((4, 1),),
        ((1, 1),),
        reset_cost=1,
        rng=np.random.default_rng(20260921),
    )
    second = estimate_correlated_attempt_p90(
        .5,
        ((4, 1),),
        ((1, 1),),
        reset_cost=1,
        rng=np.random.default_rng(20260921),
    )
    assert first == second
    assert first.p90 == 10
    assert first.interval_lower <= first.p90 <= first.interval_upper
    assert first.dkw_epsilon == pytest.approx(math.sqrt(math.log(200) / 100_000))
    assert abs(first.sample_mean - 6) <= 6 * first.sample_standard_error

    # Independent bounded CDF: cost is 4 + 2F, F ~ Geom(.5) - 1.
    assert sum(.5 ** (failures + 1) for failures in range(3)) < .9
    assert sum(.5 ** (failures + 1) for failures in range(4)) >= .9


def test_correlated_attempt_probability_one_and_unreachable_boundaries() -> None:
    deterministic = estimate_correlated_attempt_p90(
        1,
        ((2, 1) for _ in range(1)),
        iter(()),
        setup_cost=7,
        rng=np.random.default_rng(11),
    )
    assert deterministic.mean_cost == pytest.approx(9)
    assert deterministic.p90 == 9
    assert deterministic.interval_lower == 9
    assert deterministic.interval_upper == 9
    with pytest.raises(ValueError, match="unreachable"):
        correlated_attempt_metrics(0, ((2, 1),), ((1, 1),))
    with pytest.raises(ValueError, match="too small"):
        estimate_correlated_attempt_p90(
            1e-20,
            ((2, 1),),
            ((1, 1),),
            rng=np.random.default_rng(1),
        )


def test_protected_cycle_exact_fixture_and_actual_first_hit_costs() -> None:
    entries = [
        _entry("A", "L", 1),
        _entry("B", "L", 1),
        _entry("C", "X", 2),
        _entry("D", "Y", 2),
    ]
    labels = {entry.mod_id: entry.mod_id for entry in entries}
    for draws, expected in ((1, 1 / 6), (2, 1 / 3), (3, 1 / 2)):
        result = evaluate_grouped_schedule(
            entries,
            labels,
            ((draws, 3, 3),),
            target_predicate=lambda outcome: "A" in outcome.labels,
            early_stop=False,
        )
        assert result.success_probability == pytest.approx(expected)
    first_hit = evaluate_grouped_schedule(
        entries,
        labels,
        ((1, 3, 3), (1, 3, 3), (1, 3, 3)),
        target_predicate=lambda outcome: "A" in outcome.labels,
    )
    assert tuple(sum(stage.values()) for stage in first_hit.success_by_stage) == pytest.approx(
        (1 / 6, 1 / 6, 1 / 6)
    )
    assert first_hit.success_probability + first_hit.failure_probability == pytest.approx(1)

    first = protected_cycle_metrics(0, .5, 5, 1 / 6, 0, 12, ((12, 1),))
    second = protected_cycle_metrics(
        0, .5, 5, 1 / 3, 0, 14, ((12, 1 / 2), (14, 1 / 2))
    )
    third = protected_cycle_metrics(
        0,
        .5,
        5,
        .5,
        .5,
        16,
        ((12, 1 / 3), (14, 1 / 3), (16, 1 / 3)),
    )
    assert first.mean_cost == pytest.approx(82)
    assert second.mean_cost == pytest.approx(51)
    assert third.mean_cost == pytest.approx(50)
    assert second.expected_preparations == pytest.approx(2)
    assert second.expected_cycles == pytest.approx(3)
    assert third.early_completion_probability == 0
    assert third.via_cycle_probability == pytest.approx(1)

    assert protected_cycle_metrics(
        0, .5, 50, 1 / 3, 0, 14, ((12, .5), (14, .5))
    ).mean_cost == pytest.approx(141)
    assert protected_cycle_metrics(
        0, .5, 50, .5, .5, 16, ((12, 1 / 3), (14, 1 / 3), (16, 1 / 3))
    ).mean_cost == pytest.approx(230)

    first_hit_estimate = estimate_protected_cycle_p90(
        0,
        .5,
        5,
        1 / 3,
        0,
        14,
        ((12, 1 / 2), (14, 1 / 2)),
        rng=np.random.default_rng(20260921),
    )
    cdf = _bounded_cdf({17: 1 / 12, 19: 1 / 12}, {5: .5, 14: 2 / 3, 19: -1 / 3}, 97)
    assert cdf[96] == pytest.approx(.8986572140038259)
    assert cdf[97] == pytest.approx(.9014381387760283)
    assert next(cost for cost, mass in enumerate(cdf) if mass >= .9) == 97
    assert first_hit_estimate.interval_lower <= 97 <= first_hit_estimate.interval_upper


def test_protected_cycle_renewal_means_and_pure_preparation_p90() -> None:
    first = protected_cycle_metrics(0, .5, 5, .25, .25, 2, ((2, 1),))
    no_reset = protected_cycle_metrics(0, .5, 5, .25, 0, 2, ((2, 1),))
    early = protected_cycle_metrics(.1, .4, 5, .25, .25, 2, ((2, 1),))
    assert first.mean_cost == pytest.approx(28)
    assert first.expected_preparations == pytest.approx(4)
    assert first.expected_cycles == pytest.approx(4)
    assert no_reset.mean_cost == pytest.approx(18)
    assert early.mean_cost == pytest.approx(22)
    assert early.expected_preparations == pytest.approx(10 / 3)
    assert early.expected_cycles == pytest.approx(8 / 3)
    assert protected_cycle_metrics(0, .5, 5, .25, .25, 2, ((2, 1),), base_cost=7).mean_cost == pytest.approx(35)

    pure = estimate_protected_cycle_p90(
        .5, 0, 5, 0, 0, 0, (), rng=np.random.default_rng(20260921)
    )
    assert pure.mean_cost == pytest.approx(10)
    assert pure.expected_preparations == pytest.approx(2)
    assert pure.expected_cycles == 0
    assert pure.early_completion_probability == 1
    assert pure.via_cycle_probability == 0
    assert pure.p90 == 20
    assert sum(.5 ** attempts for attempts in range(1, 4)) < .9
    assert sum(.5 ** attempts for attempts in range(1, 5)) >= .9

    mixed_first = estimate_protected_cycle_p90(
        .1, .4, 5, .25, .25, 2, ((2, 1),), rng=np.random.default_rng(20260921)
    )
    mixed_second = estimate_protected_cycle_p90(
        .1, .4, 5, .25, .25, 2, ((2, 1),), rng=np.random.default_rng(20260921)
    )
    assert mixed_first == mixed_second
    assert mixed_first.mean_cost == pytest.approx(22)
    assert abs(mixed_first.sample_mean - 22) <= 6 * mixed_first.sample_standard_error
    cdf = _bounded_cdf({5: .1, 7: .05}, {2: .5, 5: .5, 7: -.15}, 45)
    assert cdf[44] == pytest.approx(.8965019744873047)
    assert cdf[45] == pytest.approx(.9019973991088868)
    assert next(cost for cost, mass in enumerate(cdf) if mass >= .9) == 45
    assert mixed_first.interval_lower <= 45 <= mixed_first.interval_upper


def test_protected_cycle_rejects_dead_end_and_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="unreachable"):
        protected_cycle_metrics(.1, .4, 5, 0, 0, 2, ((2, 1),))
    with pytest.raises(ValueError, match=r"u \+ v"):
        protected_cycle_metrics(.8, .3, 5, .5, 0, 2, ((2, 1),))
    with pytest.raises(ValueError, match="b"):
        protected_cycle_metrics(0, .5, 5, .25, .8, 2, ((2, 1),))
    with pytest.raises(ValueError, match="finite"):
        protected_cycle_metrics(5e-324, 0, 1, 0, 0, 0, ())
