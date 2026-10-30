# The objective is mean cost; risk is measured on the fixed policy

The solver minimises the expected cost of reaching the target. Success chance, p50, p90, variance and CVaR are computed afterwards for the chosen policy and reported; they are never optimised. Expected cost adds up step by step, so the stochastic shortest path solves it exactly (ADR-0001, ADR-0010); a risk objective would not. "Maximum chance within a budget" is out of v1.

Origin: [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q4.
