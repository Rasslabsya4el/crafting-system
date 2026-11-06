"""The optimistic pattern bound of research/376/junk_bound.py (ticket #376): admissible on any shortest-path graph, exact for the identity key.

A random stochastic shortest-path graph is built in the shape of the research walker's `Graph`; its exact value comes from the
policy iteration of research/312/prune_analysis.py. For every random grouping of the states (a key) the optimistic abstraction's
value in each member's abstract state must not exceed the member's exact value; for the grouping that tells every state apart it
must equal it. This is the property the ticket's measurements rely on (a bound that cut a state the optimum uses is a finding, not a result).
"""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "research" / "312", ROOT / "research" / "376"):
    if str(extra) not in sys.path:
        sys.path.append(str(extra))

import exact_classes as E  # noqa: E402
import junk_bound as J  # noqa: E402
import prune_analysis as P  # noqa: E402


def random_graph(seed: int, n: int = 40) -> E.Graph:
    """State 0 is the start, state n - 1 the goal; every other state has an action that reaches the goal with a positive chance."""
    rng = np.random.default_rng(seed)
    g = E.Graph()
    g.states = list(range(n))
    g.goal = bytearray(n)
    g.goal[n - 1] = 1
    g.expanded = n
    for s in range(n):
        if s == n - 1:
            g.act_ptr.append(len(g.act_offer))
            continue
        for a in range(int(rng.integers(1, 4))):
            width = int(rng.integers(1, 6))
            succ = rng.choice(n, size=width, replace=False).astype(np.int32)
            if a == 0 and (n - 1) not in succ:
                succ[0] = n - 1  # a proper action
            weights = rng.integers(1, 20, size=width).astype(np.int64)
            g.k_succ.append(succ)
            g.k_wt.append(weights)
            g.k_big.append(False)
            g.act_offer.append(a)
            g.act_cost.append(float(rng.integers(1, 30)))
            g.act_kernel.append(len(g.k_succ) - 1)
        g.act_ptr.append(len(g.act_offer))
    return g


def exact_values(g: E.Graph) -> np.ndarray:
    """Exact value of every state reachable from the start (NaN elsewhere: the research solver values only the live states)."""
    flat = P.flatten({
        "n": g.expanded, "goal": bytes(g.goal), "act_ptr": g.act_ptr, "act_offer": g.act_offer, "act_cost": g.act_cost,
        "act_kernel": g.act_kernel, "k_succ": g.k_succ, "k_wt": g.k_wt,
    })
    value, _ = P.solve_values(flat, flat["cost"], flat["p"], np.ones(len(flat["cost"]), dtype=bool), 0, lambda _t: None)
    seen = P.reach(flat, 0, np.ones(len(flat["cost"]), dtype=bool))
    return np.where(seen, value, np.nan)


def live(exact: np.ndarray) -> np.ndarray:
    return ~np.isnan(exact)


def bound(g: E.Graph, cmap: np.ndarray) -> np.ndarray:
    value, info = J.optimistic_value(g, J.pack_kernels(g), J.action_arrays(g), cmap, int(cmap.max()) + 1, 0.0, 10**9)
    assert value is not None, info
    return value[cmap]


@pytest.mark.parametrize("seed", range(6))
def test_optimistic_bound_never_exceeds_the_exact_value(seed):
    g = random_graph(seed)
    exact = exact_values(g)
    rng = np.random.default_rng(100 + seed)
    for groups in (2, 5, 12):
        cmap = rng.integers(0, groups, size=g.expanded).astype(np.int64)
        cmap[g.expanded - 1] = groups  # the goal is its own abstract state, as the key of the research always has the goal flag
        cmap[0] = rng.integers(0, groups)
        lower = bound(g, cmap)
        assert np.all(~live(exact) | (lower <= exact * (1 + 1e-9) + 1e-9)), (groups, float(np.nanmax(lower - exact)))


@pytest.mark.parametrize("seed", range(6))
def test_the_identity_key_gives_the_exact_value(seed):
    g = random_graph(seed)
    exact = exact_values(g)
    lower = bound(g, np.arange(g.expanded, dtype=np.int64))
    assert lower[live(exact)] == pytest.approx(exact[live(exact)], rel=1e-9, abs=1e-9)


def test_a_coarser_key_never_gives_a_stronger_bound():
    g = random_graph(11)
    rng = np.random.default_rng(5)
    fine = rng.integers(0, 10, size=g.expanded).astype(np.int64)
    fine[g.expanded - 1] = 10
    fine[0] = 0
    coarse = fine // 4  # a coarsening: every abstract state of `coarse` is a union of those of `fine`
    coarse[g.expanded - 1] = int(coarse.max()) + 1
    assert bound(g, coarse)[0] <= bound(g, fine)[0] * (1 + 1e-9) + 1e-9


def test_weights_beyond_the_range_of_a_float_are_divided_as_integers():
    """The essence rerolls of R04 have kernels whose weights are Python ints beyond 10**308 (a float conversion overflows)."""
    g = random_graph(3)
    huge = 10**400
    g.k_succ[0] = np.array([5, g.expanded - 1], dtype=np.int32)
    g.k_wt[0] = np.array([3 * huge, huge], dtype=object)
    exact = exact_values(g)
    lower = bound(g, np.arange(g.expanded, dtype=np.int64))
    assert lower[live(exact)] == pytest.approx(exact[live(exact)], rel=1e-9, abs=1e-9)
