# The solver condenses SCCs, eliminates self-loops exactly, and starts in plain Python

The solver generates the reachable states, eliminates self-loops exactly, condenses strongly connected components and solves them in reverse topological order, with value or policy iteration inside a component and a Bellman-residual stopping bound. Risk is computed on the fixed policy (ADR-0006). Probabilities come from integer weights; the solver works in float64.

The code is Python first; numpy or numba only for hot loops a profile has found. Not in v1: FTVI-style bound pruning (unless fossil combinations make B1 too slow), numba before profiling, an LP solver in production. HiGHS LP and brute force are test oracles (ADR-0019). The goal is about 1 minute per benchmark query, tracked by the benchmark command and never asserted in tests (ADR-0014).

Two-input actions need a branching (least fixed point) solver; it arrives in B3 (ADR-0011).

Origin: [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q9 and "Settled before the grill" (Python first); [solver engineering research](../research/2026-10-30-4-solver-engineering.md).
