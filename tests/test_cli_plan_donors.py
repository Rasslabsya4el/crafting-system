"""The planner takes donors: a recombinator offered from the target and planned with its donors (ticket #225, ADR-0062, ADR-0033).

The world (`donor_plan_support`): boots whose pool is two prefixes A and B of weight 100, each its own family; nothing else spawns on them.
The target is A and B. The start is a given magic pair of boots with A. The offers are the Orb of Transmutation, the Orb of Alteration and the
recombinator; its donors are the target's isolated feeders (ADR-0062 decision 4): an item of A alone, of B alone, of A and B.

Worked by hand. A donor starts as normal boots: a Transmutation gives A or B, 1/2 each (the pool has no suffix, so a magic item holds one
prefix), and from A an Alteration gives B one time in two, so the donor B costs t + a on average. A recombination of A with B pools two prefixes:
it keeps both 33 times in 100 and one, A or B at equal weight, 67 times in 100 (the guide's table, ADR-0033); after one it is the same problem
again. So the plan's mean from the start is (r + t + a) / 0.33, and it is the same at every exponent alpha (the two weights are equal).
"""

import pytest
from donor_plan_support import A, B, PRICES, R, T, ALT, donor_target, world

from crafting_system.actions import Recombinator
from crafting_system.cli import make_plan
from crafting_system.cli._offers import offers_for
from crafting_system.abstraction import Goal


def test_the_recombinator_is_offered_with_the_targets_isolated_feeders_as_donors():
    data = world()
    target = donor_target(data)
    chosen = offers_for(data, Goal.from_target(target), target.base_id, target.start_item, target.actions)
    donors = sorted(
        tuple(sorted(entry.mod_id for entry in offer.action.donor.mods))
        for offer in chosen.offers
        if isinstance(offer.action, Recombinator)
    )
    assert donors == [(A,), (A, B), (B,)]


def test_a_plan_with_donors_costs_what_the_hand_worked_route_costs():
    data = world()
    plan = make_plan(data, donor_target(data), PRICES)

    assert plan.mean_remaining == pytest.approx((R + T + ALT) / 0.33, rel=1e-9)
    assert plan.policy[plan.start].label.startswith("Recombinator with a donor of")
    assert plan.donors is not None  # the donor processes are kept with the plan
    assert plan.risk is not None and plan.risk.mean.value == pytest.approx((R + T + ALT) / 0.33, rel=1e-6)


def test_the_interval_over_alpha_is_a_point_when_the_weights_are_equal():
    data = world()
    plan = make_plan(data, donor_target(data), PRICES)

    assert plan.readings is not None
    costs = [cost.value for cost in plan.readings.plan.costs.values()]
    assert costs == pytest.approx([(R + T + ALT) / 0.33] * 5, rel=1e-9)
    assert plan.readings.baseline is not None  # the best route without recombinators is beside it (ADR-0012)


def _label(plan, *mod_ids):
    """The label of the recombinator whose donor holds exactly `mod_ids`."""
    return next(
        offer.label
        for offer in plan.offers
        if isinstance(offer.offer.action, Recombinator) and sorted(e.mod_id for e in offer.offer.action.donor.mods) == sorted(mod_ids)
    )


def _route_text(plan, *, donor_rules: bool = True) -> str:
    rules = f"""
rules:
  - when:
      making: target
      requirements:
        - family: {A}
          status: passing
    do: "{_label(plan, B)}"
  - when:
      making: target
      requirements:
        - family: {B}
          status: passing
    do: "{_label(plan, A)}"
"""
    if donor_rules:
        rules += """  - when:
      rarity: normal
    do: Orb of Transmutation
  - when:
      rarity: magic
    do: Orb of Alteration
"""
    return rules


def test_a_given_route_with_second_items_costs_the_hand_worked_mean_and_does_not_part_from_the_plan():
    from crafting_system.cli._route import evaluate_route, parse_route

    data = world()
    plan = make_plan(data, donor_target(data), PRICES)
    result = evaluate_route(plan, parse_route(_route_text(plan), plan, data), data)

    assert result.gaps == ()
    assert result.risk.mean.value == pytest.approx((R + T + ALT) / 0.33, rel=1e-6)
    assert result.divergence is None
    assert result.product_policy is not None and len(result.product_policy) > len(result.policy)  # the second items' states are in it


def test_a_route_that_says_nothing_of_the_second_items_has_a_gap_where_they_are_made():
    from crafting_system.cli._route import evaluate_route, parse_route

    data = world()
    plan = make_plan(data, donor_target(data), PRICES)
    result = evaluate_route(plan, parse_route(_route_text(plan, donor_rules=False), plan, data), data)

    assert result.gaps and all("second item" in gap.reason for gap in result.gaps)
    assert result.risk.mean.value == float("inf")


def test_making_names_the_targets_mods_the_second_item_holds():
    from crafting_system.cli._route import parse_route

    data = world()
    plan = make_plan(data, donor_target(data), PRICES)
    route = parse_route(f"rules:\n  - when:\n      making:\n        - family: {B}\n    do: Orb of Alteration\n", plan, data)

    when = route.rules[0].when
    feeders = {tuple(sorted(e.mod_id for e in d.mods)): plan.abstraction.compress(d) for d in (o.offer.action.donor for o in plan.offers if isinstance(o.offer.action, Recombinator))}
    assert when.is_for(feeders[(B,)]) and not when.is_for(feeders[(A,)]) and not when.is_for(feeders[(A, B)])
    from crafting_system.solver import MAIN

    assert not when.is_for(MAIN)


def test_the_report_shows_the_interval_and_the_expected_recombinations_of_a_plan_with_second_items():
    from crafting_system.cli import build_report

    data = world()
    plan = make_plan(data, donor_target(data), PRICES)
    report = build_report(plan, data)

    assert report.interval is not None
    assert report.interval.recombinations.value == pytest.approx(1 / 0.33, rel=1e-6)  # a geometric number of combines, one in 0.33 a success
    assert report.interval.best.value == pytest.approx((R + T + ALT) / 0.33, rel=1e-9)
