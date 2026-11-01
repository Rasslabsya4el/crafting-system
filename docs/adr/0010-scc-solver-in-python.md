# The solver condenses SCCs, eliminates self-loops exactly, and starts in plain Python

The solver generates the reachable states, eliminates self-loops exactly, condenses strongly connected components and solves them in reverse topological order, with value or policy iteration inside a component and a Bellman-residual stopping bound. Risk is computed on the fixed policy (ADR-0006). Probabilities come from integer weights; the solver works in float64.

The code is Python first; numpy or numba only for hot loops a profile has found. Not in v1: FTVI-style bound pruning (unless fossil combinations make B1 too slow), numba before profiling, an LP solver in production. HiGHS LP and brute force are test oracles (ADR-0019). numpy is now a dependency, used by `risk` and, for one matrix inverse, by the route view's flow (`cli/_route_flow.py`: the inverse of the chain of steps, where a profile of ticket #96 found the pure-Python dense inverse taking 2.8 s at 300 steps; `numpy.linalg.inv` takes 0.5 s at 1000). For `risk` the profile of ticket #82 found the budget DP of `risk.evaluate` (one step per state and cost bin) spending its time in Python loops, and vectorising it gave about a tenfold gain. `solver` stays stdlib-only. The DP's work grows with states times the cost spread in bins, so for a large policy `evaluate` raises the grid step until the work fits a budget (default 3e8 entries); the intervals widen and stay certified, and `grid.step` reports it. The solver's dead-end search settles the strongly connected components sink first, so chains no longer cost a rescan per dead end.

The goal is about 1 minute per benchmark query, tracked by the benchmark command and never asserted in tests (ADR-0014).

Two-input actions need a branching (least fixed point) solver; it arrives in B3 (ADR-0011).

Origin: [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q9 and "Settled before the grill" (Python first); [solver engineering research](../research/2026-10-30-4-solver-engineering.md).

## Amendment: the Peek kind (B8, [Grill B8](https://github.com/Rasslabsya4el/crafting-system/issues/106), 2026-11-01)

`solver` gains one kind beside `Action`: `Peek(label, cost, options, fallback)`, stdlib, with a non-linear but monotone and continuous backup computed by a sorted-tail sweep (ADR-0054). Value iteration from zero, policy iteration under a fixed acceptance set and the certificate stay as written; the exact self-loop elimination does not apply to a burn that returns to the Lock's own state, which the policy expansion turns into an ordinary cycle; a reaction that never accepts is an improper policy. `solver` still knows nothing of Path of Exile.
