"""`run_budget` against the pure-Python budget DP kept as an oracle (#82), on chains of `build_chain`.

The block size of the vectorised DP is the smallest bin cost of a state that can finish, so these
tests cover one-bin steps (blocks of one bin), a mix of bin costs, and a large smallest cost.
"""

import math
import random

import pytest
import risk_oracle_budget as old
from risk_support import is_goal

from crafting_system.risk import _budget as new
from crafting_system.risk._chain import build_chain
from crafting_system.solver import Action

GOAL = "goal"


@pytest.fixture(params=["default", "dense", "sorted", "sliced"])
def mode(request, monkeypatch):
    """`default` picks the plain loop for small chains; the others force the vectorised DP:
    with the dense merge, with the sorted merge, and with blocks expanded in slices of 7 entries."""
    if request.param != "default":
        monkeypatch.setattr(new, "PLAIN_LIMIT", -1)
        monkeypatch.setattr(new, "DENSE_RATIO", 0 if request.param == "sorted" else 10**9)
        monkeypatch.setattr(new, "DENSE_CELLS", 1 << 40)
        monkeypatch.setattr(new, "SLICE_ENTRIES", 7 if request.param == "sliced" else 1_000_000)
    return request.param


def chain_of(policy):
    return build_chain(policy, 0, is_goal)


def random_chain(rng: random.Random, size: int, dead_ends: bool):
    policy = {}
    for i in range(size):
        outcomes = []
        if rng.random() < 0.6:
            outcomes.append((i, rng.randint(1, 20)))
        outcomes.append((i + 1 if i + 1 < size else GOAL, rng.randint(5, 40)))
        if rng.random() < 0.4 and i + 2 < size:
            outcomes.append((i + 2, rng.randint(1, 15)))
        if rng.random() < 0.3 and i > 0:
            outcomes.append((rng.randrange(0, i), rng.randint(1, 12)))
        if rng.random() < 0.1:
            outcomes.append((GOAL, rng.randint(1, 10)))
        if dead_ends and rng.random() < 0.2:
            outcomes.append(("dead", rng.randint(1, 12)))
        policy[i] = Action(f"a{i}", 1.0, tuple(outcomes))
    return chain_of(policy)


def bin_costs(chain, rng: random.Random, low: int, high: int) -> list[int]:
    costs = [0] * len(chain.states)
    for i in chain.finishing_states():
        costs[i] = rng.randint(low, high)
    return costs


def costs_of(chain, bins_by_state: dict) -> list[int]:
    """Bin costs by the state's name (the chain indexes states in discovery order)."""
    return [bins_by_state.get(state, 0) for state in chain.states]


def assert_same_run(fast, slow) -> None:
    assert len(fast.cdf) == len(slow.cdf)
    assert fast.bins == slow.bins
    for i, (a, b) in enumerate(zip(fast.cdf, slow.cdf, strict=True)):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-13), f"cdf[{i}]: new {a!r}, old {b!r}"
    assert abs(fast.unresolved - slow.unresolved) <= fast.delta
    assert fast.delta == slow.delta
    for level in (0.1, 0.5, 0.9, 0.999999):
        assert fast.first_reaching(level) == slow.first_reaching(level)


def both(chain, costs, **arguments):
    return new.run_budget(chain, costs, **arguments), old.run_budget(chain, costs, **arguments)


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize(
    ("low", "high"), [(1, 1), (1, 4), (3, 9), (40, 70), (64, 64)], ids=["k1", "k1-4", "k3-9", "k40-70", "k64"]
)
def test_run_budget_matches_the_oracle(seed, low, high, mode):
    rng = random.Random(seed)
    chain = random_chain(rng, rng.randint(1, 25), dead_ends=rng.random() < 0.5)
    costs = bin_costs(chain, rng, low, high)
    proper = chain.proper
    arguments = {
        "target": rng.choice((0.5, 0.9, 0.999)) if proper else None,
        "tail_mass": rng.choice((1e-9, 1e-4)),
        "max_bins": rng.choice((30, 400, 5000)),
    }

    assert_same_run(*both(chain, costs, **arguments))


def test_a_chain_of_one_bin_steps_runs_block_by_block(mode):
    chain = chain_of({0: Action("go", 1.0, ((0, 1), (GOAL, 3)))})

    fast, slow = both(chain, costs_of(chain, {0: 1}), target=0.99, tail_mass=1e-9, max_bins=1000)

    assert fast.bins > 3
    assert_same_run(fast, slow)


def test_mixed_bin_costs_land_in_later_blocks_than_the_next_one(mode):
    policy = {
        0: Action("cheap", 1.0, ((0, 1), (1, 2), (GOAL, 1))),
        1: Action("dear", 1.0, ((0, 1), (1, 1), (GOAL, 3))),
    }
    chain = chain_of(policy)

    fast, slow = both(chain, costs_of(chain, {0: 3, 1: 11}), target=0.9999, tail_mass=1e-9, max_bins=3000)

    assert_same_run(fast, slow)


def test_a_large_smallest_cost_makes_wide_blocks(mode):
    policy = {
        0: Action("a", 1.0, ((0, 2), (1, 3), (GOAL, 1))),
        1: Action("b", 1.0, ((0, 1), (2, 3), (GOAL, 1))),
        2: Action("c", 1.0, ((1, 1), (GOAL, 4))),
    }
    chain = chain_of(policy)

    fast, slow = both(chain, costs_of(chain, {0: 200, 1: 201, 2: 250}), target=0.99, tail_mass=1e-9, max_bins=100_000)

    assert_same_run(fast, slow)


def test_a_cap_below_the_horizon_reports_the_mass_still_in_flight(mode):
    chain = chain_of({0: Action("go", 1.0, ((0, 9), (GOAL, 1)))})

    fast, slow = both(chain, costs_of(chain, {0: 5}), target=0.999, tail_mass=1e-9, max_bins=60)

    assert fast.bins == 60
    assert fast.unresolved == pytest.approx(0.9**12, rel=1e-9)
    assert_same_run(fast, slow)


def test_a_policy_that_loses_all_its_mass_stops_at_the_tail(mode):
    policy = {0: Action("go", 1.0, ((1, 1), ("dead", 3))), 1: Action("go", 1.0, ((GOAL, 1), ("dead", 1)))}
    chain = chain_of(policy)

    fast, slow = both(chain, costs_of(chain, {0: 2, 1: 7}), target=None, tail_mass=1e-9, max_bins=500)

    assert fast.absorbed == pytest.approx(1 / 8)
    assert_same_run(fast, slow)


def test_a_cap_too_large_for_the_keys_is_refused_by_the_vectorised_dp(monkeypatch):
    monkeypatch.setattr(new, "PLAIN_LIMIT", -1)
    chain = chain_of({0: Action("go", 1.0, ((0, 1), (GOAL, 1)))})

    with pytest.raises(ValueError, match="max_bins"):
        new.run_budget(chain, costs_of(chain, {0: 1}), target=0.5, tail_mass=1e-9, max_bins=2**61)
