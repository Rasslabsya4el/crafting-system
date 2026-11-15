"""The crafted-pattern bound against the walked graph of a real route (ticket #497): never above the exact cost, at any state.

For a route of `examples/targets/` the research walker (research/312) walks the concrete graph with the plan's offers and prices, the exact value of
every state is solved on it (research/312 `prune_analysis`), and the optimistic model built from the abstraction alone (`pattern_lower_bound`, no
walk) must give, at the key of every walked state, a value that is not above the state's exact value, and must have a key for every walked state.
It is the test `tests/test_research_376_bound.py` makes on random graphs, made on the real route, for the key with the protected tags (when the
metamods are modelled) and without them. R04, R14 and the strand route S02 are too long for the suite: `research/497/pattern_bound.py --check`
makes the same comparison on them in a heavy run (the numbers are in the pull request of #497 and `docs/research/2026-11-06-497-walk-free-bound.md`).
Needs the cached dump; skips without it (CI fetches it, ticket #165). Nothing here asserts a time (ADR-0014).
"""

import sys
from pathlib import Path

import numpy as np
import pytest
from abstraction_support import real_game_data

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "research" / "312", ROOT / "research" / "376"):
    if str(extra) not in sys.path:
        sys.path.append(str(extra))

import exact_classes as E  # noqa: E402
import prune_analysis as P  # noqa: E402

from crafting_system.abstraction._pattern import Pattern  # noqa: E402
from crafting_system.planner._pattern_bound import pattern_lower_bound  # noqa: E402

# (target, tags): R13 with the key the route calls for and without the tags, R05 (72 offers, no action reads the junk: a state keeps none of it) with the key it calls for.
# R05 is the ring as it was read before #895 ("at least 1 of Life and the three resistances"): its walk has 78 states; the benchmark's R05 has 6 since #895.
EXAMPLES = ROOT / "examples" / "targets"
CASES = [
    pytest.param(EXAMPLES / "r13-life-resist-belt.yaml", None, id="r13-auto"),
    pytest.param(EXAMPLES / "r13-life-resist-belt.yaml", False, id="r13-no-tags"),
    pytest.param(ROOT / "tests" / "real_targets" / "r05-life-or-resistance.yaml", None, id="r05-auto"),
]


@pytest.mark.parametrize(("route", "tags"), CASES)
def test_the_bound_is_never_above_the_exact_cost_on_the_walked_graph(route, tags):
    real_game_data()  # skips without the dump
    data, target, goal, abstraction, start, priced, info = E.build_model(route, "twins", True, False)
    bound = pattern_lower_bound(abstraction, start, priced, tags=tags)
    g, reason, _ = E.walk(abstraction, start, priced, 0.0, float("inf"), 1e9, 1_000_000, 0)  # no clock: the walk of these routes is short
    assert reason == "finished"
    n = g.expanded
    flat = P.flatten(
        {"n": n, "goal": bytes(g.goal[:n]), "act_ptr": g.act_ptr[: n + 1], "act_offer": g.act_offer, "act_cost": g.act_cost, "act_kernel": g.act_kernel, "k_succ": g.k_succ, "k_wt": g.k_wt}
    )
    exact, _ = P.solve_values(flat, flat["cost"], flat["p"], np.ones(len(flat["cost"]), dtype=bool), 0, lambda _t: None)
    pattern = Pattern(abstraction, tags)
    compared = 0
    for r in range(n):
        key = pattern.key(g.states[r])
        assert key in bound.model.index, f"the walk met a state whose key the model never reached: {g.states[r]}"
        if np.isfinite(exact[r]) and exact[r] < E.BIG / 10:
            value = float(bound.value[bound.model.index[key]])
            assert value <= exact[r] * (1 + 1e-7) + 1e-9, (g.states[r], value, exact[r])
            compared += 1
    assert compared > 50
    assert bound.start_value <= exact[0] * (1 + 1e-7)
    assert bound.start_value >= 0.99 * exact[0]  # on these routes the key tells apart all that matters: the bound is the exact cost
    assert bound.model.stats.keys <= n  # and it has no more keys than the walk has states (a route that keeps no junk has a key for each state)
