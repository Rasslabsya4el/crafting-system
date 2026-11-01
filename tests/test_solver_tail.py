"""`solve_tail_cut`: expand exactly where a coarse policy goes, bound the rest by the blocks (ADR-0023, ticket #129).

The theorem `lower <= V* <= J(policy) <= upper` is checked in exact fractions against brute force over every
policy, on the block-structured models of `ssp_bounds.block_ssp`, for every start and a sweep of `theta`; the
expanded set is compared with a closure of the coarse policy at `theta = 0`, and the entry counts of the rule with
hand-computed chains. The policy after the cut is the tail policy on the expanded states and the coarse policy
everywhere else.
"""

import functools
import math
from fractions import Fraction

import pytest
from ssp_bounds import block_ssp, lifted_choice
from ssp_oracles import brute_force, evaluate_exactly, to_model

from crafting_system.solver import Action, TabularModel, solve_bounds, solve_tail_cut

SEEDS = range(120)
THETAS = (math.inf, 2.0, 1.0, 0.75, 0.3, 0.1, 0.02, 1e-4, 0.0)  # largest first: the expanded sets grow
SLACK = Fraction(1, 10**9)  # the float64 rounding that `solve_bounds` already rounds outward for


@functools.cache
def lifted(seed):
    """The block-structured model, its two coarse models, the exact model with labels the coarse ones share, and its optimum."""
    spec = block_ssp(seed)
    size, table = spec.exact
    exact = TabularModel(
        [size],
        {
            s: [Action((spec.block_of[s], int(label.split(".")[1])), float(cost), tuple(outcomes)) for label, cost, outcomes in actions]
            for s, actions in table.items()
        },
    )
    return spec, to_model(spec.optimistic), to_model(spec.pessimistic), exact, brute_force(spec.exact)


def block_of(spec):
    size, _ = spec.exact
    return lambda state: spec.nblocks if state == size else spec.block_of[state]


def cut(seed, start, theta):
    spec, optimistic, pessimistic, exact, _ = lifted(seed)
    return solve_tail_cut(exact, optimistic, pessimistic, block_of(spec), start, theta)


def starts(seed):
    """The exact states whose block has a finite coarse upper bound."""
    spec, optimistic, pessimistic, _, _ = lifted(seed)
    coarse = solve_bounds(optimistic, pessimistic, range(spec.nblocks))
    return [s for s in range(spec.exact[0]) if coarse.upper[spec.block_of[s]] != math.inf]


def policy_closure(spec, found, start):
    """The states the coarse policy can reach from `start`, found by hand on the exact table."""
    size, table = spec.exact
    choice = lifted_choice(spec, found.coarse.policy)
    seen, queue = {start}, [start]
    while queue:
        state = queue.pop()
        for target, weight in table[state][choice[state]][2]:
            if weight > 0 and target != size and target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


@pytest.mark.parametrize("seed", SEEDS)
def test_the_bounds_hold_around_the_optimum_and_the_policy_cost_for_every_start_and_theta(seed):
    spec, _, _, _, best = lifted(seed)
    for start in starts(seed):
        for theta in THETAS:
            found = cut(seed, start, theta)
            choice = lifted_choice(spec, found.coarse.policy)
            for state, action in found.bounds.policy.items():
                choice[state] = spec.index_of[state, int(action.label[1])]
            cost = evaluate_exactly(spec.exact, choice)
            for state in {start, *found.expanded}:
                assert best[state] is not None
                assert Fraction(found.bounds.lower[state]) <= Fraction(best[state]) * (1 + SLACK)
                assert cost[state] is not None, "the composed policy must be proper"
                assert Fraction(best[state]) * (1 - SLACK) <= cost[state] <= Fraction(found.bounds.upper[state]) * (1 + SLACK)
            gap = found.bounds.gap_at(start)
            assert found.bounds.gap == gap
            assert cost[start] / Fraction(best[start]) - 1 <= (1 + Fraction(gap)) * (1 + SLACK) - 1


@pytest.mark.parametrize("seed", SEEDS)
def test_nothing_expanded_gives_the_coarse_bounds_and_the_bounds_tighten_as_the_expanded_set_grows(seed):
    spec, optimistic, pessimistic, _, _ = lifted(seed)
    for start in starts(seed):
        block = spec.block_of[start]
        coarse = solve_bounds(optimistic, pessimistic, [block])
        found = cut(seed, start, math.inf)
        assert found.expanded == frozenset() and found.leaves == 0 and dict(found.bounds.policy) == {}
        assert (found.bounds.lower[start], found.bounds.upper[start], found.bounds.gap) == (coarse.lower[block], coarse.upper[block], coarse.gap)
        before = None
        for theta in THETAS:
            found = cut(seed, start, theta)
            low, high = found.bounds.lower[start], found.bounds.upper[start]
            assert coarse.lower[block] * (1 - 1e-9) <= low and high <= coarse.upper[block] * (1 + 1e-9)
            if before is not None:
                assert before[0].expanded <= found.expanded
                assert before[1] <= low * (1 + 1e-9) and high <= before[2] * (1 + 1e-9)
            before = found, low, high


@pytest.mark.parametrize("seed", SEEDS)
def test_theta_zero_expands_exactly_the_states_the_coarse_policy_can_reach(seed):
    spec, *_ = lifted(seed)
    size, _ = spec.exact
    for start in starts(seed):
        found = cut(seed, start, 0.0)
        assert found.expanded == policy_closure(spec, found, start)
        assert size not in found.expanded


def chain(loop=Fraction(0)):
    """s0 -> s1 or the goal, each by a half; s1 stays with chance `loop`, else goes to s2 or the goal; s2 -> the goal.

    Returns the exact model, the coarse models (one block `B`, the goal `G`) and the map to blocks; a cut state
    is worth 1 in the optimistic model and 10 in the pessimistic one.
    """
    half = Fraction(1, 2)
    weights = lambda *chances: tuple((target, int(chance * 1000)) for target, chance in chances)  # noqa: E731
    table = {
        "s0": [Action("go", 1.0, weights(("s1", half), ("G", half)))],
        "s1": [Action("go", 1.0, weights(("s1", loop), ("s2", (1 - loop) * half), ("G", (1 - loop) * half)))],
        "s2": [Action("go", 1.0, (("G", 1),))],
    }
    exact = TabularModel(["G"], table)
    optimistic = TabularModel(["G"], {"B": [Action("go", 1.0, (("G", 1),))]})
    pessimistic = TabularModel(["G"], {"B": [Action("go", 10.0, (("G", 1),))]})
    return exact, optimistic, pessimistic, lambda state: "G" if state == "G" else "B"


@pytest.mark.parametrize(
    ("theta", "expanded"),
    [(0.0, {"s0", "s1", "s2"}), (0.2, {"s0", "s1", "s2"}), (0.25, {"s0", "s1"}), (0.4, {"s0", "s1"}), (0.5, {"s0"}), (0.99, {"s0"}), (1.0, set())],
)
def test_a_state_is_expanded_when_the_policy_enters_it_with_a_chance_above_theta(theta, expanded):
    found = solve_tail_cut(*chain(), "s0", theta)

    assert found.expanded == expanded  # s1 is entered with chance 1/2 and s2 with chance 1/4: "above" is strict


@pytest.mark.parametrize(("theta", "expanded"), [(0.2, {"s0", "s1", "s2"}), (0.25, {"s0", "s1"}), (0.5, {"s0"}), (0.6, {"s0"})])
def test_the_repeats_of_a_self_loop_are_not_entries_but_they_carry_the_mass_on(theta, expanded):
    # s1 is entered with chance 1/2 and, once it is left, goes to s2 with chance 1/2, however often it repeats
    found = solve_tail_cut(*chain(Fraction(1, 2)), "s0", theta)

    assert found.expanded == expanded


def test_a_cut_state_is_worth_the_bound_of_its_block_on_each_side():
    found = solve_tail_cut(*chain(), "s0", 0.5)

    # s0 costs 1 and then, by a half, a cut s1 that is worth 1 (lower) or 10 (upper)
    assert found.bounds.lower["s0"] == pytest.approx(1 + 0.5 * 1, rel=1e-9)
    assert found.bounds.upper["s0"] == pytest.approx(1 + 0.5 * 10, rel=1e-9)
    assert found.leaves == 1
    assert set(found.bounds.lower) == {"s0", "G"} and set(found.bounds.policy) == {"s0"}
    assert [outcome.state for outcome in found.bounds.policy["s0"].outcomes] == ["s1", "G"]  # the cut state, not a wrapper of it


def test_a_cut_state_in_a_block_the_pessimistic_model_does_not_reach_is_added_to_the_coarse_solve():
    exact, _, _, _ = chain()
    optimistic = TabularModel(["G"], {"B": [Action("go", 1.0, (("C", 1),))], "C": [Action("go", 1.0, (("G", 1),))]})
    pessimistic = TabularModel(["G"], {"B": [Action("go", 10.0, (("G", 1),))], "C": [Action("go", 4.0, (("G", 1),))]})
    block = lambda state: {"s0": "B", "G": "G"}.get(state, "C")  # noqa: E731

    found = solve_tail_cut(exact, optimistic, pessimistic, block, "s0", 0.5)

    assert found.coarse.upper["C"] == pytest.approx(4.0) and found.coarse.lower["C"] == pytest.approx(1.0)
    assert found.bounds.lower["s0"] == pytest.approx(1 + 0.5 * 1, rel=1e-9)
    assert found.bounds.upper["s0"] == pytest.approx(1 + 0.5 * 4, rel=1e-9)


def test_the_start_that_is_a_goal_has_value_zero():
    found = solve_tail_cut(*chain(), "G", 0.0)

    assert found.bounds.lower["G"] == found.bounds.upper["G"] == 0.0 and found.bounds.gap == 0.0 and not found.expanded


@pytest.mark.parametrize("theta", [-1.0, math.nan])
def test_a_theta_below_zero_or_not_a_number_is_refused(theta):
    with pytest.raises(ValueError, match="theta"):
        solve_tail_cut(*chain(), "s0", theta)


def test_a_start_with_no_proper_coarse_policy_is_refused():
    exact, optimistic, _, block = chain()
    pessimistic = TabularModel(["G"], {"B": []})

    with pytest.raises(ValueError, match="nothing to follow"):
        solve_tail_cut(exact, optimistic, pessimistic, block, "s0", 0.0)


def test_a_coarse_action_the_exact_model_does_not_offer_is_refused():
    exact, _, _, block = chain()
    optimistic = TabularModel(["G"], {"B": [Action("other", 1.0, (("G", 1),))]})
    pessimistic = TabularModel(["G"], {"B": [Action("other", 10.0, (("G", 1),))]})

    with pytest.raises(ValueError, match="does not offer"):
        solve_tail_cut(exact, optimistic, pessimistic, block, "s0", 0.0)


def test_two_exact_actions_with_the_label_of_the_coarse_action_are_refused():
    _, optimistic, pessimistic, block = chain()
    exact = TabularModel(["G"], {"s0": [Action("go", 1.0, (("G", 1),)), Action("go", 2.0, (("G", 1),))]})

    with pytest.raises(ValueError, match="must name one action"):
        solve_tail_cut(exact, optimistic, pessimistic, block, "s0", 0.0)


def graph(table):
    """An exact model from `{state: {successor: weight}}` (one action `go` of cost 1; "G" is the goal) and one coarse block `B`."""
    exact = TabularModel(["G"], {state: [Action("go", 1.0, tuple(chances.items()))] for state, chances in table.items()})
    optimistic = TabularModel(["G"], {"B": [Action("go", 1.0, (("G", 1),))]})
    pessimistic = TabularModel(["G"], {"B": [Action("go", 10.0, (("G", 1),))]})
    return exact, optimistic, pessimistic, lambda state: "G" if state == "G" else "B"


@pytest.mark.parametrize(("theta", "expanded"), [(0.3, {"s0", "a", "b", "c"}), (0.4, {"s0", "a", "b"}), (0.5, {"s0"})])
def test_the_entries_of_a_state_with_two_parents_add_up(theta, expanded):
    # a and b are each entered with chance 1/2; a goes on to c with chance 1/2 and b with 1/4: c is entered 1/4 + 1/8 = 3/8,
    # more than either parent alone gives and less than the 1/2 of a and b
    table = {"s0": {"a": 1, "b": 1}, "a": {"c": 1, "G": 1}, "b": {"c": 1, "G": 3}, "c": {"G": 1}}

    found = solve_tail_cut(*graph(table), "s0", theta)

    assert found.expanded == expanded


@pytest.mark.parametrize(("theta", "expanded"), [(0.3, {"s0", "p", "q", "r"}), (0.34, {"s0", "p", "q"})])
def test_the_entries_of_a_cycle_are_summed_over_its_laps(theta, expanded):
    # p goes to q by a half, to r by a quarter and to the goal; q back to p or the goal by a half. p is visited
    # 1 / (1 - 1/4) = 4/3 times, so q is entered 2/3 times and r 1/3 times; r's first entry (1/4) is below both thetas
    found = solve_tail_cut(*graph({"s0": {"p": 1}, "p": {"q": 2, "r": 1, "G": 1}, "q": {"p": 1, "G": 1}, "r": {"G": 1}}), "s0", theta)

    assert found.expanded == expanded


def test_mass_only_flows_through_expanded_states_so_the_entries_are_a_lower_bound():
    # q is entered once with chance 1/2 and, if it is not expanded, the lap back to p is not followed
    found = solve_tail_cut(*graph({"s0": {"p": 1}, "p": {"q": 1, "G": 1}, "q": {"p": 1, "G": 1}}), "s0", 0.6)

    assert found.expanded == {"s0", "p"}


def test_an_outcome_of_weight_zero_is_neither_a_leaf_nor_a_start_of_the_coarse_solve():
    exact, optimistic, pessimistic, block = graph({"s0": {"G": 1, "ghost": 0}})

    found = solve_tail_cut(exact, optimistic, pessimistic, block, "s0", 0.0)

    assert found.leaves == 0
    assert found.bounds.lower["s0"] == pytest.approx(1.0, rel=1e-12) and found.bounds.upper["s0"] == pytest.approx(1.0, rel=1e-12)
