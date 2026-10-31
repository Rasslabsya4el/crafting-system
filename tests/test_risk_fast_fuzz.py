"""The vectorised budget DP gives the same `RiskReport` as the pure-Python one kept as an oracle (#82).

`risk_oracle_evaluate` is the pre-#82 `risk.evaluate`, copied verbatim. Many seeded random
policies, small and mid-size, proper and not proper (stuck states, trapped cycles), on exact grids
and on float-cost grids that are inexact, with different levels, caps, tail masses and
resolutions, must give the same estimates, the same grid and the same unresolved mass.
"""

import math
import random

import pytest
from risk_oracle_evaluate import evaluate as old_evaluate
from risk_support import is_goal

from crafting_system.risk import _budget as budget
from crafting_system.risk import evaluate
from crafting_system.solver import Action

GOAL = "goal"


@pytest.fixture(params=["default", "dense", "sorted", "sliced"])
def mode(request, monkeypatch):
    """`default` picks the plain loop for small chains; the others force the vectorised DP:
    with the dense merge, with the sorted merge, and with blocks expanded in slices of 7 entries."""
    if request.param != "default":
        monkeypatch.setattr(budget, "PLAIN_LIMIT", -1)
        monkeypatch.setattr(budget, "DENSE_RATIO", 0 if request.param == "sorted" else 10**9)
        monkeypatch.setattr(budget, "DENSE_CELLS", 1 << 40)
        monkeypatch.setattr(budget, "SLICE_ENTRIES", 7 if request.param == "sliced" else 1_000_000)
    return request.param
DEAD = "dead"  # a reachable state without a policy entry: stuck
LOOP = "loop"  # a trapped state: its only outcome is itself

EXACT_COSTS = (0.5, 1.0, 1.5, 2.0, 3.0)
REL = 1e-9


def random_policy(rng: random.Random, floaty: bool, improper: bool, size: int) -> dict:
    """States 0..size-1 with forward moves, back moves (cycles), self-loops and goal exits."""
    policy = {}
    for i in range(size):
        cost = rng.uniform(0.4, 3.5) if floaty else rng.choice(EXACT_COSTS)
        outcomes = []
        if rng.random() < 0.6:
            outcomes.append((i, rng.randint(1, 20)))
        outcomes.append((i + 1 if i + 1 < size else GOAL, rng.randint(5, 40)))
        if rng.random() < 0.4 and i + 2 < size:
            outcomes.append((i + 2, rng.randint(1, 15)))
        if rng.random() < 0.3 and i > 0:
            outcomes.append((rng.randrange(0, i), rng.randint(1, 12)))
        if rng.random() < 0.15:
            outcomes.append((GOAL, rng.randint(1, 10)))
        if improper and rng.random() < 0.25:
            outcomes.append((rng.choice((DEAD, LOOP)), rng.randint(1, 12)))
        policy[i] = Action(f"a{i}", cost, tuple(outcomes))
    if improper:
        policy[LOOP] = Action("loop", rng.choice(EXACT_COSTS), ((LOOP, 1),))
    return policy


def pick_arguments(rng: random.Random, policy: dict) -> dict:
    costs = [a.cost for a in policy.values()]
    arguments = {
        "quantile_levels": tuple(sorted(rng.sample((0.05, 0.25, 0.5, 0.75, 0.9, 0.99, 0.999), rng.randint(1, 3)))),
        "cvar_level": rng.choice((0.5, 0.9, 0.95)),
        "tail_mass": rng.choice((1e-9, 1e-6, 1e-3)),
        "max_bins": rng.choice((40, 300, 2500)),
    }
    if rng.random() < 0.4:
        arguments["resolution"] = min(costs) / rng.randint(1, 12)
    return arguments


def same_number(new: float, old: float) -> bool:
    if math.isinf(old) or math.isinf(new):
        return new == old
    return math.isclose(new, old, rel_tol=REL, abs_tol=1e-12)


def assert_same_estimate(new, old, what: str) -> None:
    for part in ("value", "low", "high"):
        a, b = getattr(new, part), getattr(old, part)
        assert same_number(a, b), f"{what}.{part}: new {a!r}, old {b!r}"


def assert_same_report(new, old) -> None:
    assert_same_estimate(new.success_probability, old.success_probability, "success")
    assert_same_estimate(new.mean, old.mean, "mean")
    assert_same_estimate(new.variance, old.variance, "variance")
    assert_same_estimate(new.cvar, old.cvar, "cvar")
    assert new.cvar_level == old.cvar_level
    assert new.quantiles.keys() == old.quantiles.keys()
    for level in old.quantiles:
        assert_same_estimate(new.quantiles[level], old.quantiles[level], f"quantile {level}")
    assert new.grid.step == old.grid.step
    assert new.grid.exact == old.grid.exact
    assert new.grid.bins == old.grid.bins
    assert new.grid.rounding == old.grid.rounding
    assert abs(new.grid.unresolved_mass - old.grid.unresolved_mass) <= old.grid.rounding


def compare(policy: dict, arguments: dict) -> None:
    try:
        old = old_evaluate(policy, 0, is_goal, **arguments)
    except ValueError:
        with pytest.raises(ValueError):
            evaluate(policy, 0, is_goal, **arguments)
        return
    assert_same_report(evaluate(policy, 0, is_goal, **arguments), old)


@pytest.mark.parametrize("seed", range(120))
def test_small_random_policies_match_the_oracle(seed, mode):
    rng = random.Random(seed)
    policy = random_policy(rng, floaty=rng.random() < 0.5, improper=rng.random() < 0.4, size=rng.randint(1, 8))

    compare(policy, pick_arguments(rng, policy))


@pytest.mark.parametrize("seed", range(40))
def test_mid_size_random_policies_match_the_oracle(seed, mode):
    rng = random.Random(1000 + seed)
    policy = random_policy(rng, floaty=rng.random() < 0.6, improper=rng.random() < 0.4, size=rng.randint(15, 60))
    arguments = pick_arguments(rng, policy)

    compare(policy, arguments)


def test_the_fuzz_covers_every_kind_of_grid_and_policy():
    kinds = set()
    for seed in range(120):
        rng = random.Random(seed)
        policy = random_policy(rng, floaty=rng.random() < 0.5, improper=rng.random() < 0.4, size=rng.randint(1, 8))
        report = old_evaluate(policy, 0, is_goal, **pick_arguments(rng, policy))
        kinds.add((report.grid.exact, report.success_probability.value == 1.0))

    assert kinds == {(True, True), (True, False), (False, True), (False, False)}
