"""`solve_bounds`: two models, one policy, a certified interval (ADR-0023, ADR-0019 layer 3).

The theorem `lower <= V* <= J(pi) <= upper` is checked in exact fractions, with no slack, against
brute force over every policy and against the HiGHS LP, on random block-structured models built the
way the ADR requires (`ssp_bounds.block_ssp`). With one model the result must equal `solve`.
"""

import dataclasses
import functools
import math
from fractions import Fraction

import pytest
from ssp_bounds import block_ssp, lifted_choice, pushed_kernel
from ssp_helpers import DIRECT_LIMITS, GOAL, CountingModel, act, model
from ssp_oracles import (
    brute_force,
    cost_spread_ssp,
    evaluate_exactly,
    lp_values,
    random_ssp,
    sparse_ssp,
    to_model,
)

from crafting_system.solver import Bounds, solve, solve_bounds
from crafting_system.solver._bounds import _gap, _lower_bound, _upper_bound

limits = pytest.mark.parametrize("limit", DIRECT_LIMITS.values(), ids=DIRECT_LIMITS.keys())
SEEDS = range(150)
LIMIT_SEEDS = range(0, 150, 5)
PROPER_SEEDS = range(40)
LP_TOLERANCE = 1e-7  # the LP's own accuracy, as in test_solver_oracles
EPSILON = 2.0**-52


@functools.cache
def exact_optimum(seed, safe=None):
    return brute_force(block_ssp(seed, safe=safe).exact)


@functools.cache
def lifted_bounds(seed, limit, safe=None):
    spec = block_ssp(seed, safe=safe)
    bounds = solve_bounds(
        to_model(spec.optimistic),
        to_model(spec.pessimistic),
        range(spec.nblocks),
        direct_solve_limit=limit,
    )
    return spec, bounds


def check_chain(seed, limit, *, safe=None, optimum=None):
    """The whole chain for one seed; `optimum` replaces brute force (the LP, with its slack)."""
    spec, bounds = lifted_bounds(seed, limit, safe)
    size, _ = spec.exact
    best = exact_optimum(seed, safe) if optimum is None else optimum
    slack = 0.0 if optimum is None else LP_TOLERANCE
    exact_cost = evaluate_exactly(spec.exact, lifted_choice(spec, bounds.policy))
    for state in range(size):
        block = spec.block_of[state]
        low, high = bounds.lower[block], bounds.upper[block]
        value = best[state]
        if value is None:
            # no policy reaches the goal: the pessimistic model cannot have one either
            assert high == math.inf
            continue
        assert low < math.inf
        assert Fraction(low) <= Fraction(value) * (1 + Fraction(slack))
        if high == math.inf:
            continue
        cost = exact_cost[state]
        assert cost is not None, "the pessimistic policy must be proper on every member"
        assert Fraction(value) * (1 - Fraction(slack)) <= cost <= Fraction(high)
        gap = bounds.gap_at(block)
        assert bounds.gap >= gap
        if gap != math.inf:
            assert cost / Fraction(value) - 1 <= (1 + Fraction(gap)) / (1 - Fraction(slack)) - 1


@pytest.mark.parametrize("seed", SEEDS)
def test_the_bounds_hold_around_the_exact_optimum_and_the_policy_cost(seed):
    check_chain(seed, 64)


@limits
@pytest.mark.parametrize("seed", LIMIT_SEEDS)
def test_the_bounds_hold_under_every_way_of_solving_a_component(seed, limit):
    check_chain(seed, limit)


@limits
@pytest.mark.parametrize("seed", PROPER_SEEDS)
def test_the_bounds_hold_around_the_highs_lp_optimum(seed, limit):
    spec, _ = lifted_bounds(seed, limit, True)
    check_chain(seed, limit, safe=True, optimum=lp_values(spec.exact))


@pytest.mark.parametrize("seed", range(15))
def test_the_lp_and_brute_force_agree_on_the_block_models_exact_side(seed):
    spec, _ = lifted_bounds(seed, 64, True)
    for state, reference in enumerate(lp_values(spec.exact)):
        best = float(exact_optimum(seed, True)[state])
        assert abs(reference - best) <= LP_TOLERANCE * best


def test_the_generator_builds_the_construction_it_claims():
    differing_costs = differing_legality = splits = 0
    for seed in SEEDS:
        spec = block_ssp(seed)
        for (block, kind), kernel in spec.kernels.items():
            members = spec.members[block]
            offered = [s for s in members if (s, kind) in spec.index_of]
            assert tuple(offered) == spec.legal[block, kind] and offered
            for s in offered:
                assert pushed_kernel(spec, s, kind) == kernel  # block-invariant
            differing_costs += len({spec.costs[s, kind] for s in members}) > 1
            differing_legality += len(offered) < len(members)
            splits += any(
                len(spec.exact[1][s][spec.index_of[s, kind]][2]) > len(kernel) for s in offered
            )
            # the pessimistic model: offered only if every member has it, at the worst cost
            pessimistic = [a for a in spec.pessimistic[1][block] if a[0] == (block, kind)]
            if len(offered) == len(members):
                assert [(a[1], dict(a[2])) for a in pessimistic] == [
                    (max(spec.costs[s, kind] for s in members), kernel)
                ]
            else:
                assert pessimistic == []
            # the optimistic model: every member's action, cost of that member, same block kernel
            union = [a for a in spec.optimistic[1][block] if a[0][:2] == (block, kind)]
            assert sorted(a[0][2] for a in union) == sorted(offered)
            assert all(dict(a[2]) == kernel for a in union)
            assert all(a[1] == spec.costs[a[0][2], kind] for a in union)
        assert sorted(s for group in spec.members for s in group) == list(range(spec.exact[0]))
    assert differing_costs and differing_legality and splits


def test_the_bounds_are_neither_always_trivial_nor_always_loose():
    gaps = [lifted_bounds(seed, 64)[1].gap for seed in SEEDS]
    assert sum(g > 1e-6 for g in gaps) >= 20  # a real gap
    assert sum(g < 1e-6 for g in gaps) >= 20  # a block-level model that loses nothing
    assert sum(g == math.inf for g in gaps) >= 1
    assert sum(lifted_bounds(seed, 64)[1].upper[0] < math.inf for seed in SEEDS) >= 100
    assert sum(lifted_bounds(seed, 64)[1].upper[0] == math.inf for seed in SEEDS) >= 1


def test_the_unsafe_seeds_include_blocks_without_a_pessimistic_policy():
    dead = [
        seed
        for seed in range(60)
        if any(
            v == math.inf for v in lifted_bounds(seed, 64, False)[1].upper.values()
        )
    ]
    assert dead
    for seed in dead[:10]:
        check_chain(seed, 64, safe=False)


def test_a_block_built_from_one_representative_member_breaks_the_bound():
    # ADR-0023: the first member's actions alone are not a pessimistic model of the block. The
    # theorem tests must be able to fail, so they must see this one fail.
    broken = 0
    for seed in SEEDS:
        spec = block_ssp(seed)
        first = {
            b: [(a[0][:2], a[1], a[2]) for a in actions if a[0][2] == spec.members[b][0]]
            for b, actions in spec.optimistic[1].items()
        }
        wrong = solve_bounds(
            to_model(spec.optimistic), to_model((spec.nblocks, first)), range(spec.nblocks)
        )
        for state, value in exact_optimum(seed).items():
            high = wrong.upper[spec.block_of[state]]
            broken += value is not None and high < math.inf and Fraction(high) < value
    assert broken > 0


# One model: the same answer as `solve`.
ONE_MODEL_SPECS = (
    [("random", seed, random_ssp(seed)) for seed in range(25)]
    + [("sparse", seed, sparse_ssp(seed, 20 + seed * 5)) for seed in range(5)]
    + [("spread", seed, cost_spread_ssp(seed)) for seed in (701582, 701779, 701945, 3, 4)]
)


@pytest.mark.parametrize(
    "spec", [s for _, _, s in ONE_MODEL_SPECS], ids=[f"{k}-{n}" for k, n, _ in ONE_MODEL_SPECS]
)
def test_with_one_model_the_values_policy_and_error_are_those_of_solve(spec):
    size, _ = spec
    starts = list(range(size))
    solution = solve(to_model(spec), starts)

    bounds = solve_bounds(to_model(spec), to_model(spec), starts)
    same = solve_bounds(m := to_model(spec), m, starts)

    assert bounds.policy == solution.policy == same.policy
    assert bounds.optimistic_error == bounds.pessimistic_error == solution.error_bound
    assert set(bounds.lower) == set(bounds.upper) == set(solution.values)
    for state, value in solution.values.items():
        assert bounds.lower[state] <= value <= bounds.upper[state]
        if 0.0 < value < math.inf:
            error = solution.error_bound
            assert abs(bounds.lower[state] - value * (1 - error)) <= 4 * EPSILON * value
            assert abs(bounds.upper[state] - value * (1 + error)) <= 4 * EPSILON * value
        else:
            assert bounds.lower[state] == bounds.upper[state] == value
    assert dataclasses.asdict(same) == dataclasses.asdict(bounds)
    for start in starts:
        assert bounds.gap_at(start) <= bounds.gap


def test_the_same_model_object_is_solved_once():
    spec = random_ssp(3)
    counting = CountingModel(to_model(spec))

    solve_bounds(counting, counting, range(spec[0]))

    assert len(counting.action_calls) == len(set(counting.action_calls))


def test_two_distinct_models_are_both_solved_with_the_same_options():
    spec = random_ssp(5, ensure_proper=True)
    first, second = CountingModel(to_model(spec)), CountingModel(to_model(spec))

    solve_bounds(first, second, [0], tolerance=1e-6, direct_solve_limit=0, max_sweeps=777)

    assert first.action_calls and second.action_calls


def test_the_options_reach_both_solves():
    spec = random_ssp(5, ensure_proper=True)
    loose = solve_bounds(to_model(spec), to_model(spec), [0], tolerance=1e-2, direct_solve_limit=0)
    tight = solve_bounds(to_model(spec), to_model(spec), [0])

    assert loose.optimistic_error >= tight.optimistic_error
    assert loose.pessimistic_error >= tight.pessimistic_error
    with pytest.raises(ValueError, match="tolerance"):
        solve_bounds(to_model(spec), to_model(spec), [0], tolerance=-1.0)


def test_starts_may_be_a_one_shot_iterator():
    spec = random_ssp(5, ensure_proper=True)

    bounds = solve_bounds(to_model(spec), to_model(spec), iter(range(spec[0])))

    assert set(bounds.lower) >= set(range(spec[0]))


# Safety and the edge cases.
def test_an_optimistic_model_above_the_pessimistic_one_is_refused():
    low = model({"a": [act("go", 1, (GOAL, 1))]})
    high = model({"a": [act("go", 5, (GOAL, 1))]})

    with pytest.raises(ValueError, match="'a'"):
        solve_bounds(high, low, ["a"])
    solve_bounds(low, high, ["a"])


def test_a_goal_start_has_value_zero_on_both_sides_and_gap_zero():
    bounds = solve_bounds(model({}), model({}), [GOAL])

    assert bounds.lower == bounds.upper == {GOAL: 0.0}
    assert bounds.gap == bounds.gap_at(GOAL) == 0.0


def test_a_start_with_no_proper_policy_in_both_models_is_infinite_with_gap_zero():
    stuck = model({"a": [act("loop", 1, ("a", 1))]})

    bounds = solve_bounds(stuck, stuck, ["a"])

    assert bounds.lower["a"] == bounds.upper["a"] == math.inf
    assert bounds.gap == bounds.gap_at("a") == 0.0
    assert dict(bounds.policy) == {}


def test_a_dead_pessimistic_model_with_a_live_optimistic_one_gives_an_infinite_gap():
    optimistic = model({"a": [act("go", 2, (GOAL, 1))]})
    pessimistic = model({"a": [act("loop", 2, ("a", 1))]})

    bounds = solve_bounds(optimistic, pessimistic, ["a"])

    assert 0.0 < bounds.lower["a"] <= 2.0
    assert bounds.upper["a"] == math.inf
    assert bounds.gap == bounds.gap_at("a") == math.inf
    assert dict(bounds.policy) == {}


def test_the_result_is_frozen_and_the_policy_is_the_pessimistic_one():
    optimistic = model({"a": [act("cheap", 1, (GOAL, 1))]})
    pessimistic = model({"a": [act("dear", 3, (GOAL, 1))]})

    bounds = solve_bounds(optimistic, pessimistic, ["a"])

    assert isinstance(bounds, Bounds)
    assert bounds.policy == solve(pessimistic, ["a"]).policy
    assert bounds.policy["a"].label == "dear"
    assert bounds.lower["a"] <= 1.0 and bounds.upper["a"] >= 3.0
    assert bounds.gap == bounds.gap_at("a") >= 2.0
    with pytest.raises(dataclasses.FrozenInstanceError):
        bounds.gap = 0.0


def test_each_side_covers_the_states_its_own_model_reaches():
    optimistic = model({"a": [act("x", 1, (GOAL, 1), ("b", 1))], "b": [act("y", 1, (GOAL, 1))]})
    pessimistic = model({"a": [act("x", 3, (GOAL, 1))]})

    bounds = solve_bounds(optimistic, pessimistic, ["a"])

    assert set(bounds.lower) == {"a", "b", GOAL}
    assert set(bounds.upper) == {"a", GOAL}
    assert bounds.gap_at("a") >= 0.0
    with pytest.raises(KeyError):
        bounds.gap_at("b")


# The helpers that make a bound certified.
@pytest.mark.parametrize("error", [0.0, 1e-300, 1e-16, 2e-16, 1e-10, 0.3, 0.999999, 1.0, 7.5])
@pytest.mark.parametrize("value", [1e-30, 0.1, 1.0, 1 / 3, 3.7, 12345.678, 1e30])
def test_rounding_never_moves_a_bound_inward(value, error):
    lower, upper = _lower_bound(value, error), _upper_bound(value, error)

    assert Fraction(lower) <= Fraction(value) * (1 - Fraction(error)) or lower == 0.0
    assert lower >= 0.0
    assert Fraction(upper) >= Fraction(value) * (1 + Fraction(error))
    assert lower <= value <= upper


def test_rounding_is_outward_by_one_step_not_more():
    value, error = 3.7, 0.25

    assert _lower_bound(value, error) == pytest.approx(value * 0.75, rel=4 * EPSILON)
    assert _upper_bound(value, error) == pytest.approx(value * 1.25, rel=4 * EPSILON)


@pytest.mark.parametrize("error", [0.0, 1e-9, 0.5, math.inf])
def test_zero_stays_zero_and_infinity_stays_infinity(error):
    assert _lower_bound(0.0, error) == 0.0 == _upper_bound(0.0, error)
    assert _lower_bound(math.inf, error) == math.inf == _upper_bound(math.inf, error)


def test_an_infinite_error_gives_zero_below_and_infinity_above_for_a_finite_value():
    assert _lower_bound(5.0, math.inf) == 0.0
    assert _upper_bound(5.0, math.inf) == math.inf
    assert _lower_bound(5.0, 1.0) == 0.0
    assert _lower_bound(5.0, 2.0) == 0.0


@pytest.mark.parametrize(
    ("lower", "upper", "expected"),
    [
        (0.0, 0.0, 0.0),
        (0.0, 3.0, math.inf),
        (math.inf, math.inf, 0.0),
        (2.0, math.inf, math.inf),
        (2.0, 2.0, 2.0**-52),  # the quotient is rounded up, so even equal bounds keep one step
        (1.0, 1.5, 0.5 + 2.0**-52),
    ],
)
def test_the_gap_rules(lower, upper, expected):
    assert _gap(lower, upper) == expected


@pytest.mark.parametrize("pair", [(0.3, 0.7), (1e-20, 3.3e-20), (5.0, 5.0), (1 / 3, 1 / 3 + 1e-15)])
def test_a_finite_gap_is_never_below_the_exact_quotient(pair):
    lower, upper = pair

    assert Fraction(_gap(lower, upper)) >= Fraction(upper) / Fraction(lower) - 1
