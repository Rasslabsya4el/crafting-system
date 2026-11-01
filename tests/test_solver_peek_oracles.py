"""`solve_peek` against independent oracles on 2000 seeded tiny Peek models (ticket #293, ADR-0054).

The oracle is the explicit product expansion (`peek_oracles.product_spec`): the Lock becomes an ordinary action
that leads to a "react" state for every combination of one result per option, so the Peek model is an ordinary
stochastic shortest path and the oracles of `ssp_oracles` apply to it. Four checks run on the base states:

* exact brute force over every policy of the product (Fractions), on every seed whose product has at most
  `BRUTE_LIMIT` policies (a fixed rule of the spec; the few seeds above it have more than a thousand policies and
  are left to the other checks);
* the existing plain `solve` on the product;
* the HiGHS Bellman LP on the product cut to its finite states (the LP is unbounded on a state with no proper
  policy, so the infinite states and the actions that touch them are cut; the optimum of the rest is unchanged);
* exact policy iteration in Fractions, where it applies (the first action of every state is proper).

Infinite values are checked on all seeds against a graph fixed point (`finite_states`), which brute force
confirms where it runs. The certificate is `solve_peek`'s own `error_bound`, as in `test_solver_oracles.py`.
"""

import functools
import math
import threading

import pytest
from peek_oracles import (
    FAMILIES,
    families,
    finite_states,
    peek_model,
    policy_count,
    product_spec,
    random_peek_spec,
    restricted_spec,
)
from ssp_oracles import brute_force, evaluate_exactly, exact_optimal_values, lp_values, to_model

from crafting_system.solver import PeekNode, solve, solve_peek

SEEDS = range(2000)
BRUTE_LIMIT = 1000
LP_TOLERANCE = 1e-7  # the LP's own accuracy, as in test_solver_oracles.py
FAMILY_MINIMUM = 100


@functools.cache
def spec_of(seed):
    return random_peek_spec(seed)


@functools.cache
def product_of(seed):
    return product_spec(spec_of(seed))


@functools.cache
def peeked(seed):
    spec = spec_of(seed)
    return solve_peek(peek_model(spec), range(spec.size))


@functools.cache
def planned(seed):
    spec = spec_of(seed)
    return solve(to_model(product_of(seed)), range(spec.size))


@functools.cache
def finite_of(seed):
    return finite_states(product_of(seed))


@functools.cache
def exact_of(seed):
    return brute_force(product_of(seed))


@functools.cache
def cut_of(seed):
    """The product cut to its finite states: `(spec, order)`, `order` the kept product states, in the new numbering."""
    return restricted_spec(product_of(seed), finite_of(seed))


BRUTE_SEEDS = [seed for seed in SEEDS if policy_count(product_of(seed)) <= BRUTE_LIMIT]


def certified(solution, value, exact):
    """`value` equals the exact float `exact` within the solver's own certificate."""
    return abs(value - exact) <= solution.error_bound * exact + 1e-12 * exact


@pytest.mark.parametrize("seed", SEEDS)
def test_infinite_values_are_exactly_those_without_a_proper_policy_in_the_product(seed):
    spec = spec_of(seed)
    finite = finite_of(seed)

    values = peeked(seed).values

    for state in range(spec.size):
        assert (values[state] < math.inf) == (state in finite), (seed, state, values[state])


@pytest.mark.parametrize("seed", BRUTE_SEEDS)
def test_values_equal_exact_brute_force_on_the_product_within_the_certified_bound(seed):
    spec = spec_of(seed)
    best = exact_of(seed)
    finite = finite_of(seed)
    solution = peeked(seed)

    for state in range(spec.size):
        assert (best[state] is not None) == (state in finite), "the graph test and brute force disagree"
        value = solution.values[state]
        if best[state] is None:
            assert value == math.inf, (seed, state)
        else:
            assert certified(solution, value, float(best[state])), (seed, state, value, float(best[state]))


@pytest.mark.parametrize("seed", SEEDS)
def test_values_equal_the_plain_solver_on_the_product(seed):
    spec = spec_of(seed)
    solution, plain = peeked(seed), planned(seed)

    for state in range(spec.size):
        value, reference = solution.values[state], plain.values[state]
        if reference == math.inf:
            assert value == math.inf, (seed, state)
        else:
            slack = (solution.error_bound + plain.error_bound) * reference + 1e-12 * reference
            assert abs(value - reference) <= slack, (seed, state, value, reference)


@pytest.mark.parametrize("seed", SEEDS)
def test_values_match_the_highs_lp_on_the_finite_part_of_the_product(seed):
    spec = spec_of(seed)
    cut, order = cut_of(seed)
    solution = peeked(seed)
    if not order:
        pytest.skip("no state has a finite value")

    reference = lp_values(cut)

    for new, state in enumerate(order):
        if state < spec.size:  # the react states are product-only
            value = solution.values[state]
            assert abs(value - reference[new]) <= (solution.error_bound + LP_TOLERANCE) * reference[new], (
                seed,
                state,
                value,
                reference[new],
            )


@pytest.mark.parametrize("seed", SEEDS)
def test_values_equal_exact_policy_iteration_where_it_applies(seed):
    spec = spec_of(seed)
    cut, order = cut_of(seed)
    solution = peeked(seed)
    if not order:
        pytest.skip("no state has a finite value")
    if any(value is None for value in evaluate_exactly(cut, dict.fromkeys(range(len(order)), 0)).values()):
        pytest.skip("the first action of every state is not proper")

    exact = exact_optimal_values(cut)

    for new, state in enumerate(order):
        if state < spec.size:
            assert certified(solution, solution.values[state], float(exact[new])), (seed, state)


def test_exact_policy_iteration_applies_to_many_seeds():
    # the check above would be empty if the first action were almost never proper
    applies = 0
    for seed in SEEDS:
        cut, order = cut_of(seed)
        if order and all(v is not None for v in evaluate_exactly(cut, dict.fromkeys(range(len(order)), 0)).values()):
            applies += 1
    assert applies > 500


def test_brute_force_runs_on_most_seeds():
    assert len(BRUTE_SEEDS) > 1700


def test_the_seeds_contain_every_family_many_times():
    counts = dict.fromkeys(FAMILIES, 0)
    without_peek = 0
    for seed in SEEDS:
        found = families(spec_of(seed))
        without_peek += spec_of(seed).state is None
        for family in found:
            counts[family] += 1
    for family, count in counts.items():
        assert count > FAMILY_MINIMUM, (family, count)
    assert without_peek > 20  # Peek-free models are in the mix too (rounds == 0)


def with_timeout(function, seconds=30):
    """Run `function` in a thread; fail if it does not return in time, re-raise what it raised."""
    outcome = []

    def run():
        try:
            outcome.append((True, function()))
        except BaseException as error:  # handed back to the caller's thread
            outcome.append((False, error))

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(seconds)
    assert outcome, f"did not return within {seconds} seconds"
    done, result = outcome[0]
    if not done:
        raise result
    return result


def trap_seeds_without_a_plain_way_out():
    found = []
    for seed in SEEDS:
        spec = spec_of(seed)
        if "trap" in families(spec) and spec.state not in finite_states((spec.size, spec.table)):
            found.append(seed)
    return found


TRAPS = trap_seeds_without_a_plain_way_out()


def test_there_are_many_traps_with_no_plain_way_out():
    assert len(TRAPS) > 40


@pytest.mark.parametrize("seed", TRAPS[:60])
def test_a_trap_that_never_accepts_has_an_infinite_value_and_returns(seed):
    spec = spec_of(seed)
    model = peek_model(spec)

    solution = with_timeout(lambda: solve_peek(model, range(spec.size)))

    assert solution.values[spec.state] == math.inf
    assert spec.state not in finite_of(seed)
    assert solution.rounds >= 1


@pytest.mark.parametrize("seed", TRAPS[:15])
def test_a_trap_is_infinite_for_brute_force_too(seed):
    spec = spec_of(seed)
    if policy_count(product_of(seed)) > BRUTE_LIMIT:
        pytest.skip("too many policies for brute force")

    assert exact_of(seed)[spec.state] is None


def plays_the_lock(seed):
    spec = spec_of(seed)
    try:
        action = peeked(seed).policy.get(spec.state)
    except Exception:  # the test of this seed then fails on its own and names it
        return True
    return action is not None and action.label == "lock"


JEWELS_WITH_A_LOCK = [seed for seed in SEEDS if "jewel" in families(spec_of(seed)) and plays_the_lock(seed)]


def test_the_lock_is_played_in_many_jewel_models():
    assert len(JEWELS_WITH_A_LOCK) > 30


@pytest.mark.parametrize("seed", JEWELS_WITH_A_LOCK)
def test_with_no_burn_the_lock_is_always_followed_by_an_accepted_result(seed):
    spec = spec_of(seed)
    solution = peeked(seed)
    lock = solution.policy[spec.state]
    accepted = set(solution.reactions[spec.state])  # (option index, result state)
    totals = math.prod(sum(w for _, w in outs) for _, _, outs in spec.options)

    assert sum(w for _, w in lock.outcomes) == totals, "some chance is left for giving up"
    for node, _ in lock.outcomes:
        assert isinstance(node, PeekNode) and node.kind == "apply"
        step = solution.policy[node]
        assert node.option >= 0
        for result, weight in step.outcomes:
            assert weight > 0
            assert (node.option, result) in accepted
            assert solution.values[result] < math.inf
    assert not any(isinstance(s, PeekNode) and s.kind == "give up" for s in solution.policy)


def test_a_model_without_a_peek_is_one_plain_solve():
    seeds = [seed for seed in SEEDS if spec_of(seed).state is None]
    assert seeds
    for seed in seeds:
        solution = peeked(seed)
        assert solution.rounds == 0 and not solution.reactions
        assert solution.values == planned(seed).values, seed
