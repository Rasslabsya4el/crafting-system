"""The envelope search on the crafting problem of the fixture world (ticket #377, OR-12, OR-13): the plan and the mean against the full packed walk.

The world is the one of `test_packed_walk_light.py` (a Mana Leech amulet, the Chaos Orb, four bench crafts, Remove Crafted Mods, a restart: about a hundred
states). Its crafted-pattern bound (#497) is weak (about 61% of the exact cost), so the search expands nearly all of it: this file checks the exactness
of the crafting adapter (`cli/_envelope_plan.py`) where the cut does little. A strong bound on real routes is `tests/test_cli_envelope_real.py`, and the
generic search on random graphs, with a strong bound, a weak one and a planted fault, is `tests/test_cli_envelope.py`.

* the mean and the value of every state of the plan equal the full walk's, and the plan takes an optimal action at each state it reaches;
* the lower bound the search reports is the bound of the model, never above the exact cost, and equals the mean when the search is exact;
* the limit the report shows says which cut ran (exact, and what it still guarantees); a net that stops the search gives an executable plan, bounds
  `[LB, U]` around the exact cost, and a limit that says it is not shown to be the best;
* a bound planted above the exact cost is caught by the same comparison;
* the incumbent's chain gives a finite upper bound before the first round and changes nothing in the answer.
"""

import dataclasses

import numpy as np
import pytest
from coarse_support import abstraction
from test_packed_walk_light import START_ITEM, make_offers

from crafting_system.cli import _packed
from crafting_system.cli._envelope import Net, NoPolicy
from crafting_system.cli._envelope_plan import envelope_limits, envelope_result
from crafting_system.cli._limits import SOLVE, limit_document, limit_text
from crafting_system.cli._pattern_bound import pattern_lower_bound

TOLERANCE = 1e-9


@pytest.fixture(scope="module")
def world():
    ab = abstraction()
    start = ab.compress(START_ITEM)
    offers = make_offers()
    full = _packed.packed_result(ab, start, offers, solver="packed")
    bound = pattern_lower_bound(ab, start, offers)
    return ab, start, offers, full, bound


def fresh(world, **options):
    _, _, offers, _, bound = world
    ab = abstraction()  # a search notes its prunings and gaps on its abstraction
    return ab, envelope_result(ab, ab.compress(START_ITEM), offers, bound=options.pop("bound", bound), **options)


def exact_policy_check(result, full, start) -> None:
    mean = result.solution.values[start]
    assert mean == pytest.approx(full.solution.values[start], rel=TOLERANCE)
    for state in result.solution.policy:
        assert result.solution.values[state] == pytest.approx(full.solution.values[state], rel=TOLERANCE)  # the states of the plan are valued as the full walk does


def test_the_plan_and_the_mean_are_the_full_walks(world):
    _, start, _, full, bound = world
    ab, result = fresh(world)
    info = result.info["envelope"]
    assert info.exact and info.stopped is None
    exact_policy_check(result, full, start)
    for state, action in result.solution.policy.items():
        assert full.solution.policy[state].label == action.label or result.solution.values[state] == pytest.approx(
            full.solution.values[state], rel=TOLERANCE
        )
    assert info.lower <= full.solution.values[start] * (1 + 1e-12)
    assert info.lower == pytest.approx(full.solution.values[start], rel=1e-6)  # LB = UB: the mean of the plan is pinned
    assert bound.start_value <= info.upper  # the model's own value is below the answer
    assert info.expanded <= info.touched <= len(full.solution.values)


def test_the_limit_says_which_cut_ran_and_what_it_guarantees(world):
    _, result = fresh(world)
    (limit,) = envelope_limits(result.info["envelope"])
    assert limit.kind == SOLVE
    text = limit_text(limit)
    assert "expanded only what could matter" in text and "an action it did not build costs more" in text
    assert "The plan is the cheapest among the methods offered." in text
    assert "nothing was left out for being unlikely or by a tolerance" in text
    assert limit_document(limit)["guarantee"] == limit.guarantee


def test_a_net_gives_an_executable_plan_bounds_around_the_cost_and_a_limit_that_says_so(world):
    _, start, _, full, _ = world
    exact = full.solution.values[start]
    _, result = fresh(world, net=Net(states=100))
    info = result.info["envelope"]
    assert not info.exact and "limit is 100" in info.stopped
    assert info.lower <= exact * (1 + 1e-9) and info.upper >= exact * (1 - 1e-9)
    assert result.solution.values[start] == info.upper
    (limit,) = envelope_limits(info)
    text = limit_text(limit)
    assert "The search was stopped" in text and "not shown to be the best" in text and "restarts from the start item" in text
    assert f"{info.lower:,.2f}" in text and f"{info.upper:,.2f}" in text
    assert "cheapest" not in limit.guarantee  # a stopped search claims no optimum


def test_a_net_that_stops_the_search_before_any_plan_exists_raises_and_says_so(world):
    with pytest.raises(NoPolicy, match="before any policy that can be executed was found"):
        fresh(world, net=Net(states=12))


def test_a_bound_planted_above_the_exact_cost_is_caught(world):
    """A bound raised far above the exact cost at some keys (not at all of them: a uniform rise keeps the order of the offers and changes nothing)."""
    _, start, _, full, bound = world
    exact = full.solution.values[start]
    rng = np.random.default_rng(377)
    caught = 0
    for top in (20.0, 100.0):
        for _ in range(10):
            raised = (top - 1.0) * rng.random(len(bound.value)) * (rng.random(len(bound.value)) < 0.5)
            _, result = fresh(world, bound=dataclasses.replace(bound, value=bound.value * (1.0 + raised)))
            wrong = abs(result.solution.values[start] - exact) > TOLERANCE * exact
            caught += wrong or result.info["envelope"].lower > exact * (1 + 1e-9)
    assert caught >= 10, f"only {caught} of 20 planted bounds changed the answer or the bound: the comparison cannot fail often enough"


def test_an_incumbent_gives_an_upper_bound_before_the_first_round(world):
    _, start, _, full, _ = world

    def optimal(state):
        return [full.solution.policy[state].label] if state in full.solution.policy else []

    _, result = fresh(world, incumbent=optimal)
    info = result.info["envelope"]
    assert info.incumbent and info.first_upper == pytest.approx(full.solution.values[start], rel=TOLERANCE)  # the optimal policy as the incumbent: U = V*
    exact_policy_check(result, full, start)
    _, result = fresh(world, incumbent=lambda _state: ["Chaos Orb"])  # a policy that never reaches the goal has no upper bound, and the answer is the same
    assert result.info["envelope"].first_upper is None
    exact_policy_check(result, full, start)
