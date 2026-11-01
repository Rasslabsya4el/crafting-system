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

## Research task A: exact planning when the reachable state space and the branching factor are huge

We suspect the main waste is that we **materialise the whole reachable graph**, including huge regions that no good strategy ever visits, and that we **enumerate outcomes** which are indistinguishable for every later decision. Find the best known mathematics and algorithms for doing better while keeping guarantees.

### Rules

- Cite every claim: papers, textbooks, theses, library docs, benchmarks.
- Give measured numbers wherever the sources have them: states, branching, seconds, hardware. Separate measured results from claims.
- Say when something was not found.
- Prefer methods with proofs of optimality or of certified bounds for undiscounted SSP with positive costs. Flag the ones proven only for discounted MDPs; the 1/(1 − γ) bounds do not transfer.
- Output: Markdown, in English.

### Questions

1. **Lazy exploration with certified bounds.** Which algorithms solve an SSP exactly, or within a certified ε, while expanding only the states relevant to near-optimal strategies?
   - Candidates: LAO* and ILAO*, focused topological value iteration (FTVI), BRTDP, FRTDP, VPI-RTDP, LRTDP, "anytime" bound-and-prune schemes, and branch-and-bound over policies.
   - For each: the guarantee, its behaviour with near-1 self-loops and rare but important outcomes, memory, and published speed-ups. Which suits our structure best: deep "repeat until" loops, resets, and a few operations with thousands of outcomes?
2. **Cheap, strong bounds for this problem class.** How do we get a good admissible lower bound on the expected cost-to-goal, and a good feasible upper bound, quickly? The structure: collect a required set of elements by weighted random draws with group exclusion and slot capacities.
   - Candidates: relaxations that treat the required elements independently (coupon-collector style), determinisation and all-outcomes relaxations, abstraction heuristics (pattern databases and merge-and-shrink for probabilistic planning), LP and occupation-measure relaxations, Lagrangian relaxation of the slot capacities.
   - Which of these are provably admissible for SSP, and how tight are they in practice?
3. **Never enumerate equivalent outcomes.**
   - **On-the-fly minimisation.** Can a quotient (bisimulation, lumpability, MDP homomorphism, symmetry reduction) be computed during exploration, not after a full build? Cover the algorithms (Lee–Yannakakis online minimisation, Dean–Givan model minimisation, partition refinement, Givan–Dean–Greig) and their costs.
   - **Outcome distributions straight in the quotient.** For weighted sampling without replacement over groups with capacity constraints, can the distribution of the abstract outcome of a full reroll (which required elements appear, at which tier, plus junk counts per slot type) be computed in closed form? Consider generating functions, inclusion–exclusion, permanents and elementary symmetric polynomials of weights, and dynamic programming over groups. The aim is to avoid enumerating raw draws. What is the complexity?
   - **Symbolic and factored representations.** ADDs/SPUDD, factored MDPs, and decision-diagram value functions: do they fit a state that is a set of elements under capacity constraints?
4. **Exact elimination of irrelevant detail.**
   - **Erased detail.** A later operation erases everything, for example a full reroll. Is there theory for automatically detecting state features that are irrelevant because every path to the goal erases them before they matter? This includes model-irrelevance abstractions and "relevance" analysis in probabilistic planning.
   - **Making it automatic.** How do we derive the coarsest exact abstraction automatically from the operation definitions, not by hand?
5. **Decision-relevance with guarantees.**
   - **Anytime and certified stopping.** Which methods refine only where it can change the chosen first action or the reported value beyond a tolerance, while keeping a certified bound? Examples: bound-gap-driven expansion, action elimination when a lower bound on Q(s, a) exceeds an upper bound on V(s), and "best-action identification" for MDPs.
   - **Stopping when the decision is fixed.** How do we stop as soon as the decision is determined? We often only need to know which of 3 to 10 first-level strategies is cheapest, and by how much.
6. **Engineering evidence.** Find open-source implementations and measured results on problems with 10^5 to 10^7 states and branching in the thousands: probabilistic model checkers (PRISM, Storm, Modest), planners (FD-probabilistic, mdp-lib), and the IPPC competitions. What made the largest practical difference?

### Output wanted

- A ranked list of the 3 to 6 changes with the largest expected gain for our pipeline. For each: what it is, its guarantee, the expected effect on the hard cases above (estimated, and labelled as an estimate), implementation effort in Python/numba, and its risks.
- A table comparing the candidate algorithms on the criteria above.
- A references list with links.
