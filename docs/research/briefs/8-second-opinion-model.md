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

## Research task C: a second opinion — is this the right mathematical model, and what have other fields already solved?

We modelled the problem as an SSP over an abstract state, solved by full graph construction, then self-loop elimination, then SCC decomposition and value or policy iteration. Before investing further, we want an outside view from all of mathematics and operations research. Have we framed the problem in a way that makes it harder than it is? And where are the known limits?

### Rules

- Cite every claim: papers, books, theses.
- Distinguish proven results, measured results and folklore.
- Say when something was not found.
- Output: Markdown, in English.

### Questions

1. **Related fields.** Which fields have studied processes of this shape: random draws without replacement into capacity-limited slots, with exclusion groups, repeated until a required subset is present, choosing among many priced random operations?
   - Look at urn models, weighted coupon-collector problems, sequential testing and search theory, stochastic scheduling and reliability, optimal stopping, Gittins-index and multi-armed-bandit structures, stochastic knapsack, and Markov-chain absorption theory.
   - For each relevant field: the key known results, closed forms and algorithms that could replace parts of a generic MDP solve.
2. **Closed forms.** For "repeat operation X until the object contains at least the required set R", with weighted sampling without replacement over groups and slot capacities:
   - What is known in closed form, or computable in polynomial time? This covers the success probability per try, the expected number of tries, and the distribution of the junk left behind.
   - Can whole sub-strategies (a "repeat until" phase followed by a deterministic finish) be priced in closed form, so the solver only chooses among phases?
3. **Structural results.**
   - When are optimal strategies **stage-structured**, a short sequence of phases each of the form "repeat A until a condition, then do B"? Are there monotonicity or threshold-policy theorems for this kind of MDP that let us search over phase sequences instead of over states?
   - Is there an index policy, Gittins-like, or an interchange argument that orders operations?
4. **Complexity limits.**
   - What are the known hardness results: PSPACE or EXP-completeness of factored or succinct MDPs, and hardness of the abstraction problems?
   - Which special structures make planning provably tractable? We want to know which goals are impossible in general, and which structural restrictions of ours rescue tractability.
5. **Critique of our pipeline.** Given the "What we do today" section and the measured scale:
   - Which design decisions look most costly?
   - What would an expert in probabilistic planning or model checking do differently first?
   - What is the most likely reason a 177,000-state, 536-million-transition model arises from a goal of 3 to 6 required elements, and how would one shrink it exactly?
6. **Verification at scale.** We cannot check optimality by brute force on big cases. What are the accepted ways to give confidence?
   - Exact solving of small instances against an LP oracle, certificates such as dual feasibility and Bellman residual bounds, independent re-implementation, property-based testing, and statistical model checking of a fixed policy.
   - What does the probabilistic model-checking community consider sufficient evidence?

### Output wanted

- A one-page verdict: are we on the right track, and what are the 3 to 5 highest-leverage changes, ranked?
- For each relevant field: what to borrow, with references.
- A references list with links.
