"""`run_dense` against the plain budget DP and `run_budget` (#190), and against exact `Fraction` enumeration.

The dense engine moves the mass of a whole cost class by one matrix-vector product per bin, so
these tests cover one-bin steps, bin costs from 1 to 150, dead ends (lost mass), a cap that
overflows, a run from several states at once and the refusals (a zero-bin state, a chain too big).
"""

import math
import random
from fractions import Fraction

import pytest
from risk_support import is_goal

from crafting_system.risk import _budget as budget
from crafting_system.risk import _dense as dense
from crafting_system.risk._chain import Chain, build_chain
from crafting_system.solver import Action

GOAL = "goal"


def random_policy(rng: random.Random, size: int, dead_ends: bool) -> dict:
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
    return policy


def costs_by_name(chain: Chain, bins: dict) -> list[int]:
    return [bins.get(state, 0) for state in chain.states]


def assert_same_run(fast, slow) -> None:
    assert len(fast.cdf) == len(slow.cdf)
    for i, (a, b) in enumerate(zip(fast.cdf, slow.cdf, strict=True)):
        assert abs(a - b) <= 1e-12, f"cdf[{i}]: dense {a!r}, plain {b!r}"
    assert abs(fast.unresolved - slow.unresolved) <= 1e-12
    assert fast.delta == slow.delta


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize(
    ("low", "high"), [(1, 1), (1, 4), (3, 9), (1, 150), (40, 70)], ids=["k1", "k1-4", "k3-9", "k1-150", "k40-70"]
)
@pytest.mark.parametrize("vectorised", [False, True], ids=["plain", "blocks"])
def test_run_dense_from_the_start_equals_the_budget_dp(seed, low, high, vectorised, monkeypatch):
    rng = random.Random(seed)
    chain = build_chain(random_policy(rng, rng.randint(1, 25), dead_ends=rng.random() < 0.5), 0, is_goal)
    costs = [0] * len(chain.states)
    for i in chain.finishing_states():
        costs[i] = rng.choice((1, rng.randint(low, high))) if (low, high) == (1, 150) else rng.randint(low, high)
    arguments = {
        "target": rng.choice((0.5, 0.9, 0.999)) if chain.proper and rng.random() < 0.7 else None,
        "tail_mass": rng.choice((1e-9, 1e-4)),
        "max_bins": rng.choice((30, 400, 3000)),
    }
    if vectorised:
        monkeypatch.setattr(budget, "PLAIN_LIMIT", -1)

    fast = dense.run_dense(chain, costs, initial=[(0, 1.0)], **arguments)

    assert_same_run(fast, budget._run_plain(chain, costs, arguments["target"], arguments["tail_mass"], arguments["max_bins"]))
    assert_same_run(fast, budget.run_budget(chain, costs, **arguments))


def test_a_cap_below_the_horizon_reports_the_mass_in_flight():
    chain = build_chain({0: Action("go", 1.0, ((0, 9), (GOAL, 1)))}, 0, is_goal)

    fast = dense.run_dense(chain, [5], initial=[(0, 1.0)], target=0.999, tail_mass=1e-9, max_bins=60)

    assert fast.bins == 60
    assert fast.unresolved > 0.2
    assert_same_run(fast, budget._run_plain(chain, [5], 0.999, 1e-9, 60))


def test_a_state_costing_more_than_the_cap_overflows_at_once():
    policy = {0: Action("far", 1.0, ((1, 1), (GOAL, 1))), 1: Action("near", 1.0, ((0, 1), (GOAL, 3)))}
    chain = build_chain(policy, 0, is_goal)
    costs = costs_by_name(chain, {0: 10**9, 1: 2})

    fast = dense.run_dense(chain, costs, initial=[(0, 1.0)], target=None, tail_mass=1e-9, max_bins=50)

    assert_same_run(fast, budget._run_plain(chain, costs, None, 1e-9, 50))
    assert fast.cdf[-1] == 0.0
    assert math.isclose(fast.unresolved, 1.0, abs_tol=1e-12)


def mixture_oracle(policy: dict, bins: dict, starts: dict, goal_mass: float, max_bins: int) -> list[float]:
    """goal_mass + sum of mass * cdf of the single start run, each run to the cap (or until nothing is left)."""
    total = [goal_mass] * (max_bins + 1)
    for state, mass in starts.items():
        chain = build_chain(policy, state, is_goal)
        run = budget._run_plain(chain, costs_by_name(chain, bins), None, -1.0, max_bins)
        padded = run.cdf + [run.cdf[-1]] * (max_bins + 1 - len(run.cdf))
        total = [t + mass * c for t, c in zip(total, padded, strict=True)]
    return total


@pytest.mark.parametrize("seed", range(12))
def test_several_initial_states_are_the_mixture_of_the_single_start_runs(seed):
    rng = random.Random(seed)
    size = rng.randint(4, 14)
    policy = random_policy(rng, size, dead_ends=seed % 2 == 0)
    chain = build_chain(policy, 0, is_goal)
    bins = {i: rng.choice((1, 1, 2, rng.randint(1, 40))) for i in range(size)}
    starts = {s: rng.random() for s in rng.sample(range(size), 3)}
    scale = rng.uniform(0.3, 0.9) / sum(starts.values())
    starts = {s: m * scale for s, m in starts.items()}
    goal_mass = rng.uniform(0.0, 0.05)
    max_bins = 120
    index = {state: i for i, state in enumerate(chain.states)}

    run = dense.run_dense(
        chain,
        costs_by_name(chain, bins),
        initial=[(index[s], m) for s, m in starts.items()],
        goal_mass=goal_mass,
        target=None,
        tail_mass=-1.0,
        max_bins=max_bins,
    )

    expected = mixture_oracle(policy, bins, starts, goal_mass, max_bins)
    assert run.cdf[0] >= goal_mass
    assert len(run.cdf) <= max_bins + 1
    padded = run.cdf + [run.cdf[-1]] * (max_bins + 1 - len(run.cdf))
    for i, (a, b) in enumerate(zip(padded, expected, strict=True)):
        assert abs(a - b) <= 1e-12, f"cdf[{i}]: dense {a!r}, mixture {b!r}"


def test_a_tiny_chain_from_two_states_matches_exact_fractions():
    policy = {
        "A": Action("a", 1.0, (("A", 1), ("B", 2), (GOAL, 1))),
        "B": Action("b", 1.0, (("A", 1), (GOAL, 2))),
    }
    chain = build_chain(policy, "A", is_goal)
    index = {state: i for i, state in enumerate(chain.states)}
    bins = {"A": 1, "B": 2}
    steps = {"A": {"A": Fraction(1, 4), "B": Fraction(1, 2)}, "B": {"A": Fraction(1, 3)}}
    absorbed = {"A": Fraction(1, 4), "B": Fraction(2, 3)}
    start = {"A": Fraction(1, 2), "B": Fraction(1, 4)}
    goal_mass = Fraction(1, 8)  # and 1/8 is lost at bin 0
    max_bins = 40

    pending = {0: dict(start)}
    pmf = [Fraction(0)] * (max_bins + 1)
    pmf[0] = goal_mass
    in_flight = Fraction(0)
    for b in range(max_bins):
        for state, mass in pending.pop(b, {}).items():
            ahead = b + bins[state]
            if ahead > max_bins:
                in_flight += mass * (absorbed[state] + sum(steps[state].values()))
                continue
            pmf[ahead] += mass * absorbed[state]
            for nxt, p in steps[state].items():
                pending.setdefault(ahead, {})
                pending[ahead][nxt] = pending[ahead].get(nxt, Fraction(0)) + mass * p
    in_flight += sum((m for slot in pending.values() for m in slot.values()), Fraction(0))

    run = dense.run_dense(
        chain,
        costs_by_name(chain, bins),
        initial=[(index["A"], 0.5), (index["B"], 0.25)],
        goal_mass=0.125,
        target=None,
        tail_mass=-1.0,
        max_bins=max_bins,
    )

    assert len(run.cdf) == max_bins + 1
    cumulative = Fraction(0)
    for i, got in enumerate(run.cdf):
        cumulative += pmf[i]
        assert abs(got - float(cumulative)) <= 1e-14, f"cdf[{i}]"
    assert abs(run.unresolved - float(in_flight)) <= 1e-14


def test_a_finishing_state_with_no_bins_is_refused():
    chain = build_chain({0: Action("free", 1.0, ((0, 1), (GOAL, 1)))}, 0, is_goal)

    with pytest.raises(ValueError, match="at least one bin, got 0"):
        dense.run_dense(chain, [0], initial=[(0, 1.0)], target=0.9, tail_mass=1e-9, max_bins=100)


def test_an_onward_successor_that_is_not_a_finishing_state_is_refused():
    chain = Chain(
        states=("a", "b", GOAL),
        goal=(False, False, True),
        action=(Action("a", 1.0, (("b", 1), (GOAL, 1))), None, None),
        succ=(((1, 0.5), (2, 0.5)), (), ()),
        can_finish=(True, True, True),
        inputs=((), (), ()),
    )

    with pytest.raises(ValueError, match="cannot move its mass"):
        dense.run_dense(chain, [1, 0, 0], initial=[(0, 1.0)], target=0.9, tail_mass=1e-9, max_bins=100)


def test_an_initial_state_that_cannot_finish_is_refused():
    chain = build_chain({0: Action("go", 1.0, ((GOAL, 1), ("dead", 1)))}, 0, is_goal)

    with pytest.raises(ValueError, match="initial state"):
        dense.run_dense(chain, [1, 0, 0], initial=[(1, 1.0)], target=0.9, tail_mass=1e-9, max_bins=100)


def test_a_ring_buffer_over_the_limit_is_refused():
    policy = {0: Action("slow", 1.0, ((0, 1), (GOAL, 1)))}
    chain = build_chain(policy, 0, is_goal)

    assert dense.fits_dense(chain, [10], 1000)
    assert not dense.fits_dense(chain, [60_000_000], 100_000_000)
    with pytest.raises(ValueError, match="cells"):
        dense.run_dense(chain, [60_000_000], initial=[(0, 1.0)], target=0.9, tail_mass=1e-9, max_bins=100_000_000)


def test_fits_dense_caps_a_move_at_the_budget_and_follows_the_limit(monkeypatch):
    chain = build_chain({0: Action("slow", 1.0, ((0, 1), (GOAL, 1)))}, 0, is_goal)

    assert dense.fits_dense(chain, [30_000_000], 100)  # a move past the cap needs only max_bins + 2 rows
    monkeypatch.setattr(dense, "DENSE_LIMIT", 11)
    assert dense.fits_dense(chain, [10], 1000)  # 11 rows x 1 state
    assert not dense.fits_dense(chain, [11], 1000)


def test_a_dense_chain_of_cheap_and_dear_states_resolves():
    rng = random.Random(7)
    size = 150
    policy = {}
    for i in range(size):
        targets = rng.sample(range(size), 60)
        outcomes = [(j, rng.randint(1, 10)) for j in targets] + [(GOAL, rng.randint(15, 30))]
        policy[i] = Action(f"a{i}", 1.0, tuple(outcomes))
    chain = build_chain(policy, 0, is_goal)
    costs = [0] * len(chain.states)
    for i in chain.finishing_states():
        costs[i] = 100 if rng.random() < 0.1 else 1

    run = dense.run_dense(chain, costs, initial=[(0, 1.0)], target=0.9, tail_mass=1e-9, max_bins=200_000)

    assert run.first_reaching(0.9) is not None
    assert run.unresolved < 0.1 + run.delta
