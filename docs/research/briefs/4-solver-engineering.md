# Deep research 4 of 5: engineering a fast, exact stochastic-shortest-path solver for crafting routes

## Context (read first)

We are building a crafting route planner for **Path of Exile 1**. Given a target item, it returns the cheapest
crafting route as an optimal policy of a stochastic shortest path (SSP) problem. All action costs are positive.
State = a compressed description of the current item. Action = one crafting operation with a price (currency
orbs, essences, fossils, Harvest reforges, bench crafts, Fracturing Orb, etc.). Transition = an exact probability
distribution computed from the game's mod weights. Goal = the target is satisfied. Routes are not enumerated as
chains: the solver computes the expected remaining cost of every reachable state and picks the best action per state.

Expected problem size:

- **States:** 10^4–10^6 reachable compressed states per target item, up to ~10^7 in the widest searches.
- **Actions per state:** ~20–100. Fossil combinations can add up to ~4,000 candidate actions before pruning.
- **Outcomes per action:** ~5–50 after compression.
- **Transitions per sweep:** therefore ~10^8.

Structure:

- **Many near-self-loops.** "Spam Essence until the target mod appears" has a success chance per try as low as
  0.26% or 0.1%. Naive value iteration then converges by only that fraction per sweep.
- **Mostly forward progress with some resets.** Chaos Orb rerolls, a failed fracture returns to an earlier stage,
  scouring.
- **Probabilities are exact rationals or floats** computed from integer weights.

Tooling: Python, numpy / scipy / numba allowed, one 12-core / 32 GB desktop (later a server). Target runtime:
seconds to minutes per item. We also want to predict the runtime before solving, and to report risk, not only the
mean.

## Rules for this research

Cite every claim: papers, textbooks, library docs, benchmarks. Give numbers (states, transitions, seconds, hardware)
wherever sources have them. Separate measured performance from claims. If something is not found, say so.
Output: Markdown in English.

## Questions

### 1. Solution methods for SSP with positive costs

Compare these methods. For each give: convergence speed on large sparse problems; stopping criteria with error
bounds; behaviour with near-1 self-loop probabilities; memory; ease of implementation.

- value iteration, Gauss–Seidel VI, prioritized sweeping;
- topological value iteration (Dai, Mausam, Weld 2011) and SCC decomposition;
- policy iteration and modified policy iteration;
- linear programming formulations: which LP solver, at what size;
- heuristic search that only explores reachable states: LAO*, LRTDP, FRET.

### 2. Self-loops and "repeat until" structure

- Analytic elimination of self-loops. For a state whose best action leaves it unchanged with probability p, the
  geometric-series closed form applies (expected cost = c / (1 − p)).
- Solving strongly connected components exactly (small linear systems) and in topological order.
- How much these reduce the sweep count in practice.

### 3. Beyond the mean

- Computing the full cost distribution of a fixed policy: absorbing Markov chain, fundamental matrix,
  phase-type distributions, discretised cost convolution. How to get p50 / p90 / CVaR exactly or with bounds.
- Optimising for "probability to finish within budget B". The budget goes into the state: what does that cost and
  how is the budget discretised?
- Mean-versus-p90 Pareto policies, risk-sensitive SSP, chance constraints.
- Which of these are tractable at our scale.

### 4. Python implementation

- Data structures for 10^5–10^7 states × ~50 actions × ~20 outcomes: CSR sparse matrices per action, a flat
  edge list, a numba kernel. Memory per layout.
- Expected seconds per sweep for scipy.sparse versus numba versus pure Python, with any published benchmarks.
- Parallelism on 12 cores: Jacobi-style sweeps, numba `prange`, multiprocessing overhead.
- Libraries worth using or copying: pymdptoolbox / mdptoolbox, MDPtoolbox (MATLAB), JAX, OR-Tools / HiGHS for LP,
  any SSP-specific code.
- Caching transition distributions that repeat across many states (same "pool signature").
- Floating-point issues: summing probabilities to 1, tiny probabilities, `inf` for unreachable goals.

### 5. Predicting runtime before solving

- Counting reachable states and transitions cheaply (a BFS over the compressed graph).
- Calibrating the cost of one transition on the machine.
- Estimating the number of sweeps from the observed convergence rate after the first few sweeps.
- How accurate such ETAs are in practice.

### 6. Validating a solver

- A test plan: hand-solvable cases; agreement between VI, PI and LP on random small SSPs; simulating the found
  policy and comparing the mean cost with the computed value; property tests (monotonicity, bounds).
- Known bugs that SSP solvers typically have: improper policies, zero-cost cycles, unreachable goals.

## What to deliver

1. A method comparison table (question 1), with a recommendation for our structure.
2. The recommended solver stack: algorithm + data structure + library, with pseudo-code. Include the self-loop
   elimination and the risk metrics.
3. A performance table: problem size / method / implementation / seconds / hardware / source.
4. The runtime-prediction procedure as numbered steps.
5. The validation test plan as a checklist.
6. A reference list.
