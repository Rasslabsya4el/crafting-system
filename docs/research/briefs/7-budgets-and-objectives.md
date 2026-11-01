# The abstract problem

We plan optimal strategies for a stochastic combinatorial process. The application is item crafting in a video game; the mathematics is what matters. Treat it purely as a mathematical and algorithmic problem.

## The object

- An **object** has up to 6 slots: at most 3 of type P and at most 3 of type S.
- Each slot holds at most one **element** drawn from a finite pool:
  - about 100 to 400 elements;
  - grouped into about 50 to 150 mutually exclusive **groups**, at most one element per group on the object;
  - each element has a positive integer **weight**, a type (P or S), a "tier" (a quality level) and a set of tags.
- The object also carries a few flags, for example "side P is protected" or "the object has been finalized".

## Operations

There are about 20 to 100 operation types. With combinations (sets of up to 4 modifiers chosen from about 25), the count rises to about 10,000. Every operation has a known positive price.

The probability of every outcome of every operation is known exactly from the weights. There is no hidden information. The typical effects are:

1. **Full reroll.** Clear all unprotected slots, then draw k new elements, k random in {4, 5, 6} with known probabilities. Drawing is weighted sampling without replacement over groups: once a group is drawn, its whole group leaves the pool, and slot-type capacities must hold. Variants:
   - force one specific element in first;
   - multiply the weights of elements with some tag by a factor;
   - ban a tag.
2. **Add one.** Add one random element to a free slot, weighted among the groups not yet present.
3. **Remove one.** Remove one random unprotected element.
4. **Re-roll values only.** Re-roll the numeric values inside the elements present, without changing which elements they are.
5. **Deterministic.** Add a chosen element from a short menu, with limits on how many such elements the object may hold, or remove all such elements.
6. **Flag operations.** For example "protect side P from removal and rerolls", "make one present element permanent", or an irreversible "finalize" step with random results.
7. **Two-input operations.** Combine two objects into one. Each element of either input survives with some probability. Each input is itself produced by a strategy.
8. **Peek-then-choose.** See the outcome of the next operation before deciding whether to apply it. This is a chance node followed by a choice node.

## Goal and objective

- **Goal:** a set of 2 to 6 required elements, sometimes with minimum tiers or values. The other slots do not matter, or must merely be "free" or "not a specific element".
- **Objective:** minimise the expected total price until the goal is reached. A starting object can also be bought at a market price. Risk is reported as well: p50, p90 and CVaR of the total price.
- This is a **stochastic shortest path (SSP) problem** with strictly positive costs. Many operations are "repeat until success" with per-try success chances as low as 0.1% to 0.3%, so near-1 self-loops are common.

## What we do today

1. **Abstract state.** The state keeps exactly the goal-relevant facts: which required elements are present, at which tier, plus the flags. The irrelevant ("junk") content is summarised by counts per slot type and by "behavioural group types": groups that every enabled operation treats identically are interchangeable.
2. **Build the whole graph.** Generate the full reachable abstract state graph under all enabled operations.
3. **Eliminate self-loops** analytically: an action with stay-probability p becomes a macro-action costing c / (1 − p).
4. **Solve.** Decompose into strongly connected components (SCCs) and solve them in topological order: value iteration or policy iteration inside each component, with a certified Bellman-residual stopping test.
5. **Prune.** Before solving, prune whole first-level operation choices ("offers") by lower and upper bounds, exactly. This check alone takes about half the runtime on one case.
6. **Approximate answers.** When the exact model is too big, solve two models on a coarse partition of states: an optimistic one giving a lower bound and a pessimistic one giving an executable policy with an upper bound. The answer is accepted when the certified gap is at most 1%.

## Measured scale, on a 4-vCPU, 16 GB machine in Python with numpy

| Case | Abstract states | Transitions | Result |
|---|---|---|---|
| Easy cases (R13, R05, R10) | thousands | — | solved exactly in 10 to 40 s |
| Medium case (R08) | — | — | exact in 25 minutes |
| Case with an initial "make it rare" full reroll before an operation that erases everything anyway | — | — | did not finish in 60 minutes |
| Hard case R04 (7 first-level choices) | 177,242 | 535.9 million, about 3,000 per state | building the graph alone took 3,526 s and 6.3 GB; the solve ran out of memory at 15.7 GB |
| Hard case R14 | at least 787,605 | — | not solvable |

In R04, two full-reroll operations each produce about 1,500 distinct successor abstract states.

## What we want

1. **Exactness.** Answers that are provably optimal among the strategies the user's configuration admits, or provably within a stated small bound. Not heuristics without guarantees, and not Monte Carlo estimates as the answer. Monte Carlo is fine as a sanity check.
2. **No hand-tuned thresholds.** No "ignore outcomes below 1e-4" and no "never more than 100,000 uses". Every cut must follow from a general principle with a guarantee: bounds, dominance, equivalence, or decision relevance.
3. **Speed.** Seconds to about a minute per query on a consumer PC (4 to 16 cores, 8 to 32 GB), in Python with numpy and numba, possibly with small C extensions.
4. **User configuration.** For example: "I own 80,000 of operation A and 30,000 of operation B; plan within that", "never spend more than X", or "minimise p90 rather than the mean".

## Research task B: user budgets, inventory limits, multiple objectives and "realism" without hand-tuned thresholds

Users want to plan within what they really have and accept. For example:
- "I own 80,000 of operation A and 30,000 of operation B, and at most 500 units of money";
- "minimise the mean but keep p90 under X";
- "I accept at most N operations in total".

Strategies that would need far more than any real person can do, such as 100,000 uses of one operation in one stage, should drop out **because they violate the user's configured limits or are dominated**, not because of a hard-coded cut-off. Find the best known mathematics for this.

### Rules

- Cite every claim: papers, textbooks, library docs.
- Give measured numbers where available. Separate proven from conjectured.
- Say when something was not found.
- Focus on undiscounted SSP with positive costs; flag discounted-only results.
- Output: Markdown, in English.

### Questions

1. **Formulations.** Compare the ways to plan under resource limits:
   - constrained MDPs (Altman), with occupation-measure LPs and Lagrangian duality;
   - budget-augmented state (the remaining inventory as part of the state);
   - MaxProb: maximise the probability of reaching the goal before resources run out, and SSPs with dead ends (fSSPUDE, iSSPUDE, GUBS);
   - chance-constrained policies;
   - knapsack-like and multi-resource formulations.

   For each:
   - what exactly it optimises;
   - whether the optimal policy needs memory or randomisation;
   - its computational complexity;
   - how it scales when inventories are large, for example 80,000 units: discretisation, aggregation, monotonicity or concavity of the value in the budget.
2. **Expected value or probability.** With a hard inventory, which questions are meaningful?
   - Should we report "probability of success within the inventory", "expected cost given success", or both?
   - How do we compute them exactly for a fixed policy, and how do we optimise them?
3. **Risk objectives.** Exact or certified methods to:
   - optimise, not only evaluate, p90/VaR/CVaR of the total cost in SSPs: mean-CVaR trade-offs, cost-distribution DP, and how practical the published CVaR-SSP algorithms are at 10^5 to 10^6 states;
   - compute the Pareto front of mean against risk against operation count;
   - present a small set of non-dominated strategies to a user.
4. **Limits used for pruning.** How do user limits prune the search exactly?
   - Bounds on the expected number of uses of each operation under any policy reaching the goal from a state, and dominance arguments.
   - "This branch cannot finish within the inventory with probability above q", and the guarantees such pruning keeps.
5. **Realism without thresholds.** Is there principled theory for discarding strategies that are technically optimal but absurd to execute, without an arbitrary threshold?
   - Candidates: costs of executing an operation such as time or effort as a second resource, Pareto filtering, satisficing, regret bounds against simpler strategy classes, "simple" policy classes with proven small loss.
   - What does each guarantee?
6. **Configuration design.** Which knobs should a planner expose (inventories, money budget, risk level, maximum total operations, a time value per operation), and how should it report which constraint was binding and what relaxing it would gain? Shadow prices and Lagrange multipliers count here.

### Output wanted

- A recommended formulation, or a layered combination, for a planner whose default is "minimise expected price" but which accepts the limits above. Give its guarantees, its complexity, and how it plugs into an SCC/value-iteration solver with lower and upper bounds.
- A table of formulations and their properties.
- A references list with links.
