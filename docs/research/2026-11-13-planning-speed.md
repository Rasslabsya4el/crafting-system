# Planning speed: why a plan takes minutes, and what to change (research, 2026-11-13)

Question (the main chat's brief of 2026-11-12, with the owner's added requirement of the same day): why does planning take so much time and memory; is the cause still "we do not discard branches of the route that are clearly bad"; is the design itself right (walk or search the reachable states, merge them, solve for the mean-cost-optimal policy, then risk and the route page on the chain); what should replace it, in what order, and what proves it works on crafts of any complexity, not tuned to the benchmark routes. The design must hold for every crafting method in v1 scope (batches B1 to B8), including the ones not built yet.

Rules read: OR-10 (no detail no decision reads), OR-11 (an exact answer, never an interval), OR-12 (exact branch-and-bound against an incumbent; a fixed rail only as a stop-and-say-so net), OR-13 (a cut says what it guarantees), OR-14 (prune across the whole route), OR-25 (the owner's opinion on a method is not a source: research it), OR-26 (roots, not patches), OR-29 (open points become issues), OR-30 (a rebuild is accepted by measuring again). Inputs: ADR-0001, 0006, 0010, 0022, 0023, 0026, 0031, 0054, 0058 and ADR-0063 with all its updates; research #312, #376, #497 and the three outside reports of 2026-11-01; the measurement week #398; the classification #812; the open issues of the envelope search. Script: `research/planning-speed/gap_trace.py` (no `src/` change). Nothing heavy ran on the owner's PC: R04, R14 and R08 ran on GitHub runners through `heavy_dispatch.py`; J01 and R13 ran locally in seconds.

## Short answer

1. **On the planner's fast path the best plan is found in seconds; the minutes go to proving it is exactly the cheapest, and to work after the plan.** On R04 the walk-free bound's own greedy plan, built in 12 s on 15,003 states, *is* the optimal plan (189,226.5674 Chaos, to every digit), and the bound alone proves it within 0.49%. Today's search then expands 165,980 states for 364-510 s to raise its lower figure from 99.51% to 100%. On R14 the greedy plan (37 s, 86,045 states) is 0.0004% from the optimum and proved within 0.09%; the search adds 231-238 s and 185,490 states. Of what the search expands, 91% (R04) and 54% (R14) lie outside the plan, and 75% and 83% are items whose best action is to throw them away and buy a new base. After the plan, R04 spends about 251 s on the route steps' chances over its unlumped item chain and R14 380 s on percentiles. (Section 2, 3; heavy runs 42955861457, 43317321351, 43319820843.)
2. **So the owner's memory is half right.** The search never expands a branch its bound already shows to be bad (section 4). But most of what it expands does turn out to be bad, because a bound 0.1-0.5% below the truth cannot tell those items apart from good ones without looking, and an exact proof must look at every one of them. That is the price of proving the exact optimum among many near-equal plans (near ties), and a stronger bound does not remove it (#376; Helmert and Röger 2008).
3. **Off the fast path the old cause stands as it was.** Every method the walk-free bound cannot model yet (unveil, roll limits and the Divine Orb, imprints), and every switch around the search (40 offers or more, a rule axis such as the recombinator's, a judged route, the Lock's second solve) builds every reachable state, clearly bad ones included. Those are the 30-to-50-minute and out-of-memory runs: R07 15.7 GB at 7 minutes, R24 1,838 s and 1.14 M states without a certified answer, R08/R09 unfinished at today's prices, R10 10 minutes, R25/R28 cancelled after 50 minutes (section 1).
4. **The model is right; the stopping rule, the missing upper side and the two-architecture split are not.** Crafting as a stochastic shortest path with restarts, minimising the mean, is right (ADR-0001, every outside report). The walk-free bound is strong (99.5-99.99%). What should change: (a) an executable plan from the start, evaluated exactly on its own reach, as the upper side (the bound's greedy plan, or a given route); (b) a stop when that plan is proved within a stated share `eps` of the cheapest, or exact when it fits in the time budget; (c) refinement where the gap times the chance of getting there is largest, as BRTDP and FRTDP do; (d) one path for every method, each family made fast by its own bound; (e) the percentiles and the route page on the shown plan's lumped chain only (section 6).
5. **Measured effect, and what it needs.** With `eps` of 1%: R04's plan, the same as today's, in about 2 to 3 minutes instead of 12 to 17 (bound 99-148 s, greedy plan 12 s, solve and lumping seconds, risk 9 s), once the route steps' chances run on the lumped chain (C7; today they add 250-340 s); R14's in about 1 minute to the plan (bound 23 s, greedy plan 37 s), with its percentiles still costing about 6 minutes until they get a cheaper method (sections 3 and 11). The bound's build is then most of what is left, which is C1's work. Nothing in either answer changes except how it is proved.
6. **Every v1 method fits** (section 7): each keeps a monotone backup, so bounds and pruning stay sound; the hardest family is the two-input actions (recombinators, Awakener's Orb), handled as nested searches whose bounds compose; nothing in v1 breaks the design.
7. **#812's classes:** C2 (what gets walked) goes away, C3 is replaced by the new guidance, C4 mostly goes away; C1, C5, C6, C7 stay and C8 (one budget) becomes central (section 8). **The stopped tickets:** close #375; keep #738/#744 as C5, #769 as C6, #689 as C7 (section 9).
8. **The owner decides** whether the planner may stop at a proved 1% (his own rule of #81, which OR-11 later replaced), how long one plan may take, and how precise p50 and p90 must be (section 11). The proof that it works beyond the benchmarks is a generated family of targets of growing size, with acceptance by rules, not by routes (section 10).

## 1. Which path each route takes today, and what it costs

`make_plan(solver="auto")` has one fast path and several fallbacks (`cli/_plan.py:481-551`). The fast path is the envelope search of #377 on the walk-free bound of #497. It is taken only when the bound can be built (`abstraction/_pattern.py:283-290`) and no switch routes around it. Every fallback builds the whole reachable graph, or solves on the object solver.

| Route | Path under `auto` (why) | Last measured | Outcome | Source |
| --- | --- | --- | --- | --- |
| R04 penetrating quiver | envelope search | 729 s in all: bound 99 s, search 364 s, merge + solve + certificate 4 s, **the route steps' chances on the item chain about 251 s**, risk 9 s; 2.7 GB | exact | heavy run 42955861457 (2026-11-10 prices) |
| R14 hunter bow | envelope search | 650 s in all: bound 22 s, search 238 s, merge + solve 5 s, **risk 380 s**; 2.5 GB main, risk workers up to 4.2 GB | exact; p50 bracket ±9% | heavy run 42955861457 |
| R13, J01, V01, R12 | envelope search | 0.4 to 6 s | exact | PR #614, #666; local runs here |
| R07 minion wand | full walk (unveil offer: the bound refuses it, #507) | died at 7 min, 15.7 GB of 16 GB | out of memory | #770, heavy run 43255914334 |
| R24 avoid-shock boots | full walk (unveil offer) | 1,838 s, 1.14 M states, 1.28 G transitions, 4.9 GB | not certified (1.5e-3 against 1e-6) | PR #771, run 43255914334 |
| R08, R09 fossil boots | bound pruning `solve_pruned` (40 offers or more, `MIN_OFFERS_TO_PRUNE`) on the object solver | 45-48 s at the 2026-10-31 prices; not finished in 8-10 min at the 2026-11-10 prices; 15.9 GB at the 2026-11-08 prices | runner shut down / not finished | #626, #702, #799 |
| R10 fractured boots (70 life), R11 | full walk (a roll limit and the Divine Orb: the bound refuses both) | 565-628 s (R10) | finished on Ubuntu, Windows slot killed at 25 min | #743 |
| R25, R28 (recombinator donors) | object solver once per reading of the rule axis | two runs cancelled after about 50 min | not finished | #225 |
| S02 (strands) | refused by `make_plan` with strands on; only the research walker ran | 828-1,156 s, 106,002 states, 2.7 GB (they merge into 20 exact classes) | walk only | ADR-0063 |
| any route with `--route` or `benchmark` | full walk (`judges_route`) | the walk's time | | #535, #732 |
| any plan that takes Hinekora's Lock | a second solve on the object solver over the whole graph | "hours and many GB" on R04 | | #755 |

The route page adds to this: on R04's item chain (18,696 states, 48.7 million edges) the chances of entering the steps took 250 s of a 790 s plan, one linear solve of the whole chain per step, and the page's steps peak 2.8 GB above the plan (#689, #680; heavy run 42400486309).

**Reading it.** The routes that take tens of minutes or run out of memory (R07, R24, R08/R09 at today's prices, R10, R25/R28, any judged route, any Lock plan) are all on a fallback that builds every reachable state. On the fast path the small routes take seconds and R04 and R14 take 11 to 12 minutes; there the time is the search's proof, the route steps' chances (R04) and the percentiles (R14).

## 2. Where the time goes on the fast path

The log of heavy run 42955861457 (R04 and R14 at the 2026-11-10 prices, `packed_routes.py plan --solver auto`) prints the lower figure `L(root)` after every round of the search: no plan of the offered methods costs less than `L(root)`.

| | R04 | R14 |
| --- | ---: | ---: |
| Walk-free bound: abstract states, build time | 13,060 keys, 99 s | 1,969 keys, 22 s |
| `L(root)` before the search expands anything | 188,299.94 | 9,372.81 |
| Exact mean at the end | 189,226.57 | 9,381.10 |
| **Bound before any search, share of the exact mean** | **99.510%** | **99.912%** |
| Rounds of the search | 77 | 26 |
| States known / expanded | 170,781 / 165,980 | 294,317 / 185,490 |
| Actions realized (kernels built at a state) | 754,755 | 312,963 |
| Search time | 364 s | 238 s |
| What the search moved `L(root)` by | +0.49% | +0.09% |
| Merge, policy iteration, certificate | 4 s | 5 s |
| Optimal policy's chain lumped | 607 blocks, 3,135 transitions | 14,940 blocks, 81,359 transitions |
| After the solve: the plan's limits, chiefly the chances of entering each route step on the item chain (`flow_limits`, #689) | about 251 s | about 5 s |
| Risk (p50, p90, CVaR) | 9 s | 380 s (three grid steps, four workers, up to 4.2 GB) |
| **Whole plan** | **729 s** | **650 s** |

So on the fast path the walk-free bound already knows the cost of the best plan to within half a percent (R04) or a tenth of a percent (R14) before the search starts. Everything the search does after that, 364 s and 165,980 states on R04, 238 s and 185,490 states on R14, buys the last 0.49% and 0.09%: it is the proof of which of the near-equal plans is exactly the cheapest. The rest of the time is not the search at all: on R04 a third of the run is the route steps' chances on the unlumped item chain (C7 of #812), on R14 more than half is the percentiles (C5).

## 3. The gap trace: what a stop at a stated gap would have cost

`research/planning-speed/gap_trace.py` runs the planner's own search and adds two figures from outside (the script's docstring has the details):

- **`U` after each round**: the exact mean of the best plan that can be executed with what the search has built so far, buying a new base wherever it has not looked. A search that stops when `U <= (1 + eps) L(root)` would have stopped at the first round where that holds.
- **The bound's own greedy plan**, before any search: from the start, at each state take the offer whose lower bound `la` is least, build only that offer's outcomes, follow them, and evaluate the plan exactly on its reach (with buying a new base allowed at every state). This is the cheapest executable plan one can get from the bound alone.

**R04** (heavy run 43317321351, 2026-11-10 prices, the same answer as the planner's: 189,226.5674):

| | Rounds | Search time | States expanded | Actions built | `L(root)` / `U` |
| --- | ---: | ---: | ---: | ---: | --- |
| Before the search | 0 | 0 s | 0 | 0 | 188,299.95 / none |
| **The bound's greedy plan, evaluated exactly** | (none) | **12 s** | **15,003 states, 4,038 kernels** | | **U = 189,226.5674: the optimum itself** |
| The search's own `U` first finite | 5 | 11 s | 14,746 | 14,746 | 188,301 / 1,534,791 (+715%) |
| The search's own `U` reaches the optimum; a stop at 1% | 9 | 26 s | 17,358 | 36,258 | 188,304 / 189,226.57 (gap 0.49%) |
| A stop at 0.1% | 71 | 492 s | 164,661 | 741,115 | 189,043 / 189,226.57 |
| The exact stop (today) | 77 | 510 s | 165,980 | 754,755 | 189,226.55 / 189,226.55 |

(The search took 510 s on this runner against 364 s on the runner of heavy run 42955861457; runners differ by up to 1.9x, ADR-0063. The `U` solves, 78 s, are taken off. The traced search expanded the same number of states round by round as the untraced run 42955861457, on R04 and on R14, so the measurement did not change the search.)

What it shows:

1. **The answer was known before the search began.** The bound's own greedy plan is the optimal plan of R04, to every digit printed, and it took 12 s and 15,003 states, the reach of the optimal plan itself. Its mean is 0.49% above `L(root)`, so with the bound alone it is proved within 0.5% of the cheapest.
2. **Today's search found the same plan at round 9, in 26 s, and then spent 68 rounds, 485 s and 148,622 more states proving it.** All of that raised `L(root)` from 99.51% to 100%; the plan and its mean did not change.
3. **What those states were.** Of the 165,980 states expanded, 150,990 (91%) are outside the optimal plan's reach (the outcomes of the alternatives the plan does not take), and 125,323 (75%) are items whose best action is to buy a new base. The search had to look at them because its bound could not tell, without looking, that those items are worth less than a new base: they are hopeless only once examined. This is the owner's "branches that are clearly bad" in practice, with one correction: they are not clearly bad to the bound, which puts each of them within half a percent of a good plan.
4. **The proof does not shrink with a tighter tolerance until the very end.** A stop at 0.1% would still have taken 71 of the 77 rounds: the lower figure rises slowly and almost all of its rise comes in the last rounds. Only a tolerance at or above the bound's own error (0.49% here) removes the proof.

**R14** (heavy run 43319820843, the same prices; the planner's answer 9,381.0965):

| | Rounds | Search time | States expanded | Actions built | `L(root)` / `U` |
| --- | ---: | ---: | ---: | ---: | --- |
| Before the search | 0 | 0 s | 0 | 0 | 9,372.81 / none |
| **The bound's greedy plan, evaluated exactly** | (none) | **37 s** | **90,666 states, 21,673 kernels (reach 86,045)** | | **U = 9,381.1351: 0.0004% above the optimum** |
| The search's own `U` first finite | 6 | 18 s | 24,390 | 25,716 | 9,373.95 / 15,894.96 (+70%) |
| A stop at 1% or at 0.1% | 7 | 30 s | 82,544 | 85,319 | 9,374.60 / 9,381.15 (gap 0.07%) |
| A stop at 0.01% | 21 | 201 s | 181,218 | 295,408 | 9,380.39 / 9,381.10 |
| The exact stop (today) | 26 | 231 s | 185,490 | 312,963 | 9,381.09 / 9,381.09 |

The bound's greedy plan is not the optimal plan here but is 0.0004% from it, and the bound alone proves it within 0.09%. Today's search holds a plan within 0.07% at round 7 (30 s) and spends 19 more rounds and 200 s on the proof. Of the 185,490 states expanded, 99,443 (54%) are outside the optimal plan's reach and 153,606 (83%) are items whose best action is to buy a new base.

**R08** (fossil sets, 40 offers or more; the envelope search forced, since `auto` takes the bound pruning there): heavy run 43320834722 was still waiting for a runner when this note was first pushed; its result is added below when it lands.

**What the two traces say together.** On both routes a plan within the bound's own error of the optimum exists before the search starts and costs seconds to build and evaluate (12 s and 37 s), and on both the search spends most of its rounds after it already holds that plan. The figure that decides how much proof can be skipped is the bound's error at the start (0.49% on R04, 0.09% on R14): a stated tolerance at or above it skips the whole proof; one below it skips little with today's expansion order.

## 4. What the search expands, and why: items that look as good as the best until they are examined

**Branches that the bound already shows to be bad are not expanded on the fast path. This follows from the search's own rule.** A tip is expanded only when the greedy policy of the lower graph reaches it, and that policy's value in the lower graph is `L(root) <= V*(root)` (module text of `cli/_envelope.py`, "Why the mean is exact"). So every state the search expands lies on a plan whose optimistic cost is at most the optimum. A branch whose best case is already dearer than the best plan is never expanded, and an offer whose lower bound exceeds `V*(s)` is never built.

**Yet most of what it expands turns out to be bad.** On R04, 91% of the expanded states are outside the optimal plan's reach and 75% are items worth less than a new base; on R14, 54% and 83% (section 3). They are the outcomes of the alternatives the plan does not take. The bound, 0.49% below the truth, cannot tell them from good items without looking, so a proof of the exact optimum has to look at each of them. The owner's memory is right about where the work goes and wrong about why: the planner does not keep branches it knows are bad, it examines branches whose badness only examination can show, and it does so only to prove a plan it already holds.

**Why there are so many: near ties.** With a bound that is 0.49% below the optimum, every partial plan whose optimistic cost falls in that last 0.49% must be looked at before the search can prove the best one, and crafting has many: on R04, 95% of the actions the optimal policy does not take are within 1% of the best action at their state, 82% within 0.1% (#312, "Near ties", at the 2026-10-31 prices; not measured again at today's). With an error of 0.03% a bound already keeps 78% of R04's states; only an error near 0.001% keeps fewer than a third (#376, the table of the floor). The same holds in the general theory of admissible search: with a consistent bound, A* is optimally efficient among the admissible algorithms of its kind (Dechter and Pearl 1985), because an algorithm that skips a node whose lower bound is below the optimum can miss the optimum; and even an "almost perfect" bound, off by a small constant, can leave exponentially many such nodes (Helmert and Röger 2008). A better bound does not remove the near ties; only a different stopping rule does.

**What the earlier diagnosis said, and where it still holds.** The measurement week (#398) found "the bloat is the walk": R14 walked 816,153 states while its optimal policy uses 87,251 and the guide 946. That was true of the full walk, and the envelope search (#377, #535) fixed it on the fast path. It is still true of every fallback in section 1: there the planner builds every reachable state, the clearly bad ones included, because the bound cannot be built for the method (#507: a roll limit, the Divine Orb, an unveil offer, imprints) or a switch sends the plan around the search (40 offers or more, a rule axis, a judged route, the Lock's second solve). Those fallbacks are where the 15.7 GB and the 50-minute runs are.

**States walked, used by the optimal policy, and used by a sensible player.**

| | R04 | R14 |
| --- | ---: | ---: |
| Reachable (the full walk) | 177,242 | 816,153 |
| Expanded by the envelope search, 2026-10-31 prices | 138,795 (78%) | 92,691-101,757 (11-12%) |
| Expanded by the envelope search, 2026-11-10 prices | 165,980 (94%) | 185,490 (23%) |
| Reached by the optimal policy (2026-11-10 prices) | 15,003 | 86,048 |
| Built by the bound's greedy plan (section 3) | 15,003 | 90,666 |
| Expanded but outside the optimal policy's reach | 150,990 (91% of expanded) | 99,443 (54%) |
| Expanded where the best action is to buy a new base (a hopeless item) | 125,323 (75%) | 153,606 (83%) |
| The optimal policy's chain, lumped exactly | 607 blocks | 14,940 blocks |
| The guide route (acting states, then blocks) | 18,629 states, 22 blocks | 946 states, 19 blocks |

(The guide figures are OR-14's, on the 2026-11-06 main; the rest are 2026-11-10 prices.)

## 5. What the literature offers, against this problem

Crafting is a stochastic shortest path problem with restarts (ADR-0001; Bertsekas and Tsitsiklis 1991): minimise the expected cost of reaching the target, where buying a new base returns to the start. Every outside report and every measurement since 2026-11-01 agrees the model is right; the question is the method.

| Method | What it guarantees | What it costs | What it needs here | Fit, and the effect on R04 / R14 |
| --- | --- | --- | --- | --- |
| Full value or policy iteration on the walked graph (today's fallbacks; ADR-0010) | the exact optimum | the whole reachable graph | nothing | the cause of every out-of-memory run; keep only as the reference on small models |
| LAO*, iLAO* (Hansen and Zilberstein 2001): expand the best partial plan's tips until it closes | the exact optimum with an admissible bound | every state on a partial plan whose bound is below the optimum | an admissible bound | this is today's envelope search (#377); R04 94% and R14 23% of the walk at today's prices, because of the near ties |
| CG-iLAO* (Schmalz and Trevizan 2024): do not evaluate an action until it can matter | the same as iLAO* | fewer action evaluations (they report up to 57% of iLAO*'s actions skipped, 3x faster) | per-action lower bounds | already partly in the search (an offer is built only while its bound is below the best built one); the rest is C3 of #812 |
| LRTDP (Bonet and Geffner 2003): sampled trials with "solved" labels | the exact optimum in the limit, a labelled stop | trials; rare outcomes are sampled slowly | an admissible bound | worse than envelope expansion where a 0.1% outcome decides the cost (dr-1); not recommended |
| BRTDP (McMahan, Likhachev and Gordon 2005), FRTDP (Smith and Simmons 2006): keep a lower and an upper bound at every state, explore where the gap times the chance of getting there is largest, stop when the gap at the start is below a stated epsilon | the plan returned is within epsilon of the optimum; its upper bound is the value of an executable plan | only the states where the gap matters; FRTDP up to 6x fewer backups than HDP | an admissible lower bound and a proper executable plan for the upper one (here: buy a new base and follow the plan) | **the missing half of today's search**: the upper side and the stop at a stated gap. Effect: section 3 |
| FTVI (Dai, Mausam, Weld and Goldsmith 2011): eliminate actions by bounds, then solve components in order | exact | needs the relevant graph first | bounds | the existing SCC solver already plays this part on the graph the search ends with |
| Partial exploration in model checking (Brázdil et al. 2014; Křetínský and Meggendorfer 2019, "cores"): bounds computed on an explored part of the model, the rest provably reached with small probability | certified lower and upper values from a partial model | the explored part | bounds | the same principle as BRTDP, used for verification with certified answers: support for stopping on a stated gap and for computing risk on the reached part only |
| Interval iteration, optimistic value iteration (Haddad and Monmege 2018; Hartmanns and Kaminski 2020) | sound stopping of iterative solves: a value bracketed from both sides | a few more sweeps | a lower and an upper start | the certificate side (C6 of #812): what makes "the mean of the shown plan is exact" a proved statement |
| Exact lumping, bisimulation (Givan, Dean and Greig 2003) | the same values and policies on a smaller model | a partition refinement | the graph (or a key that equals the partition) | already used after the search (R04 170,781 states to 85,827 classes) and on the policy's chain (607 blocks); a key in the walk was measured not to pay on R04/R14 (#312, #379) |
| Approximate abstraction (Abel, Hershkowitz and Littman 2016); bounded-parameter MDPs (Givan, Leach and Dean 2000) | a bounded loss from merging nearly-equal states, or an interval value over a family of models | small | a merge rule with a stated error | the walk-free bound of #497 is the optimistic member of this family; the pessimistic member (ADR-0023's "two bounds around one policy") exists for some routes; the executable plan of section 6 gives the upper side without it |
| Pattern databases and occupation-measure heuristics for SSPs (Klößner and Hoffmann 2021; Trevizan, Thiébaux and Haslum 2017) | admissible lower bounds that keep the probabilities | small abstract models | a choice of pattern | the #497 bound is a probabilistic pattern database; it already reaches 99.5-99.99% on R04/R14 (#376), so a better bound is not the lever (section 4) |
| Dominance pruning (Torralba and Hoffmann 2015) | prune a state when another state is provably at least as good | a simulation relation | a proof that one item is never worse than another | weighted draws depend on every mod on the item, so no general simulation relation is known; the pattern bound already captures what dominance would; not recommended |
| Symmetry, MDP homomorphisms (Ravindran and Barto 2002) | exact reduction by symmetries | small | a symmetry group | already used: junk mods are counted by family type, not by mod (ADR-0009) |
| Factored MDPs (Guestrin, Koller, Parr and Venkataraman 2003) | approximate value functions with bounds on large factored models | LPs over local factors | local transitions | crafting draws are global (affix limits, weights over all mods, family exclusion), so the local structure these methods need is missing; not recommended |
| Dead ends (Kolobov, Mausam and Weld 2012) | well-defined values when some states cannot reach the goal | | | crafting has no true dead end while a new base can be bought: the restart turns a hopeless item into "buy again", which is how the planner already models it |
| Numerical inversion of a characteristic function (Hughett 1998) | a quantile with a stated error bound | one linear solve per frequency on the plan's lumped chain | the lumped chain | a candidate for percentiles whose error does not grow with the number of steps, unlike today's cost grid (section 6, risk) |
| Crafting calculators: Craft of Exile, POE2Crafting, pyoe2-craftpath (prior-art note of 2026-10-30) | Craft of Exile: the chance and the average cost of one chosen method, no search over policies; POE2Crafting: value iteration over a tabular state; pyoe2-craftpath: route search with "happy-path" pruning | | | none plans an adaptive policy at this scale; pyoe2-craftpath's author documents that its pruning loses routes that pass through a temporarily bad item, which is why any cut here must be sound (OR-12) |

## 6. The recommended design

**Keep:** the model (SSP with restarts, mean cost minimised, ADR-0001, ADR-0006); the compressed state and its kernels; the walk-free bound and the lower graph of the envelope search; the packed solver, its warm start and its certificate; exact lumping of the shown plan's chain.

**Change: one anytime, two-sided search for every method, that stops at a stated gap.**

1. **Lower side** (exists): the optimistic pattern model gives `LB(s)` at every state and `la(s, a)` for every offer (#497); the lower graph gives `L(root)`.
2. **Upper side** (new): an executable plan from the start, evaluated exactly on its own reach. The first one is the bound's own greedy plan (at each state the offer with the least `la`), or a given route (#536); buying a new base is always executable when the start is bought. Its exact mean is `U`. Section 3 measures how good this first plan is.
3. **Stop** (new): when `U <= (1 + eps) L(root)`, or the exact stop `U = L(root)` if it comes within the time budget. The answer is the plan with its exact mean `U` (a point, certified by the solver, OR-11), and the statement "no way of crafting this item with the offered methods costs less than `L(root)`" (OR-13), which `certificate_text` already writes for a stopped search.
4. **Refine where the gap is** (new control): instead of expanding the whole frontier of the optimistic plan each round, expand the states where the chance of reaching them times `U(s) - L(s)` is largest (FRTDP's priority), and never build an offer whose `la(s, a)` is above `U(s)` (BRTDP's cut, ADR-0031 raised to every state). `U` only falls and `L` only rises, so the gap closes monotonically and the search is anytime: a net (C8) can stop it at any round with a plan and its gap.
5. **One path.** A plan that offers a method the pattern model cannot model yet runs the same search with the trivial bound (zero at every state, each offer's own price as its `la`). It cannot keep the pattern bound at the other states: a model that leaves out an action can sit above the true cost wherever that action is a shortcut, which is why #497 refuses rather than drops (ADR-0063, update #497). With the trivial bound the search is sound and no faster than the walk, but it already has the upper side, the stop at a gap and the report. Each fallback pipeline of section 1 is removed when its family's bound lands (section 7, ticket 4 of section 9), not before: the bound pruning of fossil sets, for one, is faster today than a search with the trivial bound would be.
6. **After the plan.** The route page and the percentiles read only the shown plan's chain, lumped exactly with the labels the page needs (C7 of #812). The percentiles get a precision target and a memory estimate instead of a fixed ladder of grid steps (C5). Today's grid rounds every step's cost to the grid, so its bracket grows with the number of steps of a run: on R14 a step of 0.61 Chaos still leaves ±9% on p50, about a thousand times the step. A method whose error does not grow with the number of steps (characteristic-function inversion, Hughett 1998) is a research spike, not a commitment.

**What it guarantees.** The mean shown is exact for the plan shown; the plan is within `eps` of the cheapest plan of the offered methods, proved by the lower bound; with `eps = 0` it is today's exact answer. Nothing is cut by a count or a chance (OR-12): the stop is a stated tolerance on the proof, written next to the answer (OR-13).

**What it costs.** The bound's model (13,060 keys on R04, 1,969 on R14), the reach of the shown plan, and the refinement the gap needs. It no longer grows with the number of near-equal plans, which is what makes R04's exact proof expensive.

**Why the brief's stopping rule matters more than any speed-up of the same design.** Since 2026-11-01 the fixes were speed-ups of exhaustive work: a packed solver, a walk-free bound, an envelope search, a warm start, shared sums. Each was right, and each left the work proportional to the near ties or to the reachable graph. The stop at a stated gap changes what is computed. The outside report dr-1 already proposed it on 2026-11-01 ("continue only until `U(s0) - L(s0) <= 0.01 L(s0)`"); the project built the lower half and kept the exact stop because OR-11 asks for the exact answer. Whether the planner may stop at a stated gap is the owner's question 1 (section 11).

## 7. Every v1 method under the design

The search needs three things of a method: a state, the kernels of its actions, and an admissible bound. Pruning stays sound as long as the backup is monotone in the values of the successors, which holds for a plain expectation, for the expectation of a minimum (the Lock's preview, unveil's pick) and for the least fixed point of two-input actions (ADR-0022: `T` is monotone and continuous). The argument of #497 then carries over to any such backup: if the optimistic model's backup is never above the concrete backup at any member of a key, and both are monotone, the model's least fixed point is below the exact value at every state, and an action whose lower cost is above an upper bound of its state is in no optimal plan.

| Family (batch) | State today | Bound today | What the design needs | Stress | Source |
| --- | --- | --- | --- | --- | --- |
| Basic orbs, Annulment, Scouring, Alchemy (B1) | item (`slots`, `fractured`, `status`) | built (#497); Alchemy offered at every member (`ALL`) | nothing new | kernel work per state (C1) | `abstraction/_pattern.py:382-391` |
| Essences (B1) | item | built (`ANY`) | kernels by the families the goal can tell apart (C1) | big kernels: V01's essence kind reached 7.3 M states on the walk (#637) | #637, #770 |
| Fossils, fossil sets, resonators (B1) | item | built (`ANY`; `ALL` with Bloodstained); the bound build stalls with 10,672 offers (#626) | a cheap per-offer floor, so most sets are never built into the model; then the 40-offer switch and `solve_pruned` go | **the number of actions** (120 to 12,696 sets) | #626, #696, #742 |
| Harvest reforges, add/remove, swaps (B1, B2) | item | built; add and swaps at every member (#508) | fewer members (#508) | bound build time | `actions/harvest_augment.py` |
| Bench crafts, metamods (B1) | item, `crafted`, protected tags in the key | built | nothing new; the metamod is what makes R04's bound strong (#376) | | #376 |
| Fracturing Orb, beasts (B1, B2) | item, `fractured` | built, `ALL` members (#508) | fewer members | bound build | #508 |
| Imprints (B3) | item plus a snapshot of an earlier item (`imprints`, ADR-0060) | refused (#507): full walk | a bound that sees the snapshot: an item with an imprint costs at least the lesser of finishing without it and restoring it (`min(LB(s), c_restore + LB(imprint))`, since a restore puts the snapshot in hand and consumes it); to be proved in its ticket | a pair-like state | #507 |
| Eldritch implicits (B2) | `implicits` per side | target implicits refused before the solve (`cli/_plan.py:407`) | the implicit grades of the target's sides in the key | | ADR-0025 |
| Unveil and veiled mods (B2) | item plus the offer (chance node, then a choice node of up to 546 offers) | refused (#507): full walk | the offer's status against the goal in the key; the pick's backup is a minimum inside the expectation (monotone) | **R07 out of memory, R24 1.14 M states** | ADR-0026, #770, PR #771 |
| Awakener's Orb, recombinators (B3) | the main item, and each donor as its own acquisition process (`Need`, ADR-0022), solved as a least fixed point; the recombinator's selection exponent is a rule axis of 5 readings | refused (rule axis): object solver per reading | a bound per process with the donor's value at its own lower bound; the upper side uses executable donor plans; refinement chooses the donor or the main item by its share of the gap; 5 readings are 5 searches | **the hardest case**: two items, huge outcome sets, a fixed point that is not a contraction, 5 readings | ADR-0012, 0022, 0033, 0035, #94, #225 |
| Memory Strands, Remembrance, Unravelling, Foulborn (B5) | item plus the strand count | strands refused by `make_plan` today; the count is fixed per key (`_pattern.py:400`) | nothing new for the bound; Unravelling's 866,052 possible items need kernels by the families the goal can tell apart (C1) | outcome sets (#800); states multiplied by the count (#746) | ADR-0040, #800 |
| Corruption, Vaal, Locus, Bloodstained (B4) | `corrupted`, `replaced` | built (`ONE`) | nothing new: corruption is a last step (ADR-0036) | | ADR-0036, #750 |
| Hinekora's Lock and previews (B8) | none stored (ADR-0054): a peek action whose backup is `L + E[min(options, fallback)]` | a second solve on the object solver over the whole graph ("hours" on R04, #755) | the peek as one more action of the same search: the expectation of a minimum of independent previews is computed from the options' value tails, and its lower bound is the same backup over the lower values | today a whole second pipeline | ADR-0054, #755 |
| Sockets, links, colours (B6) | a finish problem of its own (ADR-0045), not built in code | refused before the solve | a separate small SSP solved once and added at the goal; where it meets corruption, the chain's last steps | small (63 to 149,796 colour states) | ADR-0045, #104 |
| Enchants (B7), catalysts and quality (B2) | finish steps (ADR-0050, 0029), not built in code | refused before the solve | as sockets | small | ADR-0050, 0029 |
| Influence (B2) | `flags` | built | nothing new | | ADR-0030 |
| Vendor recipes, bought starts, start options | outside the solve: one plan per option (`cli/_start_options.py`) | | branch-and-bound over the options: an option whose lower bound is above the best option's `U` is never searched | opening draws can be large (R07: 338,549 outcomes, 97 s, #770) | ADR-0059, 0061, 0064 |
| Roll limits and the Divine Orb | values in the state | refused (#507): full walk | the roll status in the key | R10 10 minutes | #743 |

**The hardest case is the two-input family (recombinators, Awakener's Orb)**: the second item is a whole acquisition process, the processes can need each other, the fixed point is not a contraction, the outcome sets are large and an unknown rule multiplies the work by five. The design handles it as nested searches whose bounds compose (a main action's lower cost uses each donor's lower bound, its upper cost an executable donor plan), and the refinement spends effort on the donor or on the main item by its share of the gap. No v1 method breaks the design: each keeps a monotone backup. What would break it is outside v1: correlated previews of the Lock (the owner's rule says they are independent, ADR-0054), a budget limit on spending (ADR-0006: out of v1; a hard budget in the state also breaks the self-loop formula, dr-2), or a risk objective such as minimising p90 instead of the mean (ADR-0006).

## 8. The eight classes of #812 under the design

| Class | Under the design | Why |
| --- | --- | --- |
| C1, the work of one (state, action) pair | **stays**, and becomes the constant factor of everything | fewer pairs are built, but each still costs a full outcome enumeration; the bound's build (R04 99 s) is all C1 |
| C2, what gets walked | **goes away** on every family with a bound | no walk on the one path; the fallbacks disappear as section 7's bounds land; a judged route reads the route's own reach (#732) |
| C3, the search's guidance | **replaced**: the upper side, the gap stop and the priority are the new guidance | the 40-offer switch and `solve_pruned` go with the fossil floors; #508's members stay |
| C4, state storage | **mostly goes away** | the search holds the states it expands, a fraction of the walk; the parallel packed walk (#375) is not needed |
| C5, the risk grid | **stays** | it reads the shown plan's chain whatever found the plan; it needs a precision target and a memory estimate |
| C6, the linear solves and the certificate | **stays**, and matters more | the gap stop compares two certified values; a free action or a stiff chain must still certify |
| C7, the route page on the full chain | **stays** | lumping the shown plan's chain with the page's labels is independent of the search |
| C8, one budget | **stays, and becomes central** | an anytime search is stopped by the budget; the report names what bound it |

## 9. The tickets, in order (proposed on #822; not created until the owner has answered)

Each ticket is accepted on the generated family of section 10, and the benchmark routes are measured after it, never the acceptance (#812). At most five tickets with heavy runs at once (CLAUDE.md).

**Effort, estimated** from the comparable tickets (from filing to closing: the walk-free bound #497 five hours, the switch of the default to the envelope search #535 four and a half days, the envelope search #377 six days including its wait on #376 and #497): tickets 1 to 3 about three to five days in all, after which R04 and R14 plan in minutes once C7 has landed too; ticket 4 one to three days per family, eight families, at most five at once, so about two to four weeks; tickets 5 to 7 and the three reshaped tickets about a week, partly beside ticket 4. These are estimates, not measurements.

1. **The generated-family benchmark** (research tooling, first). The generator and the measurements of section 10, run through `make_plan` on runners; it records today's behaviour as the baseline. Every later ticket is accepted on it.
2. **The upper side and the stop at a stated gap** (`cli/_envelope.py`, `_envelope_plan.py`). The bound's greedy plan (or a given route, #536) evaluated exactly on its reach as the first `U`; `U` kept as the search goes (realized actions plus the incumbent's action plus the restart); the stop at `U <= (1 + eps) L(root)`, or exact within the time budget; the report says which (OR-13). `eps` is a setting whose default the owner sets (question 1); with `eps = 0` nothing changes. Rules: OR-11, OR-12, OR-13.
3. **One budget** (C8: #378, #537, #540, #745). The time and memory budget the stop of ticket 2 uses, passed to every stage, read on Windows too, with one list of the limits that bound. Small; can go beside 2.
4. **Bounds for the families on a fallback**, one ticket each, in the order of the harm measured in section 1. Each ends one fallback path, and is done when that family's routes go through the one search and the generated family with that method passes:
   1. unveil and veiled offers (R07 out of memory, R24 not certified; #507);
   2. fossil sets: a per-offer floor cheap enough for thousands of sets, then the 40-offer switch and `solve_pruned` removed (R08, R09; #626, #696, #742, #799);
   3. roll limits and the Divine Orb (R10, R11; #507, #743);
   4. Hinekora's Lock as a peek action inside the search, ending the second object solve (#755);
   5. two-input actions (Awakener's Orb, recombinators): nested searches whose bounds compose, one per reading of the rule axis (R25, R28; #225);
   6. imprints (#507);
   7. strands, with the Orb of Remembrance and of Unravelling when they are built (#278, #281, #746, #800);
   8. target implicits and the finishes (sockets, enchants, quality) as they are built (ADR-0045, 0050, 0029).
5. **The work of one (state, action) pair** (C1 of #812). Kernels and kernel keys by the projection of what the action reads, cached across states. It speeds the bound's build (R04: 99 s) and every expansion; it can run beside ticket 4.
6. **Refinement by the gap** (the priority and the upper-bound cut of section 6, point 4), after ticket 2's measurement shows where the remaining gap sits.
7. **A given route judged without the walk** (#732): the route's own reach, and the planner's decision only at the states it reaches.

**What the four stopped tickets become.**

- **#375 (a packed, parallel walk): close as not planned.** Its reason, R14's walk at 8 GB, is gone on the fast path (R14's search holds 2.5 GB), and the walk stays only on the fallbacks that ticket 4 removes; a parallel version of a path to be retired is wasted work. If ticket 1 shows that the search's own states cost too much memory, packing the search's states goes into ticket 6.
- **#738 and #744 (the risk's memory): keep, reshaped as C5 of #812.** The grid chosen by a precision target and a memory estimate per step and per worker, the attempt chain shared as arrays; take #739 and #622 with it. Independent of the search; resume after ticket 2 lands. The precision target is the owner's question 3.
- **#769 (the certificate of a free action): keep as C6.** Certifying against the scale of the terms is needed by any search, and more by ticket 2, whose stop compares two certified values.
- **#689 (the chances of the route page's steps): keep, reshaped as C7.** The page's quantities on the plan's chain lumped with the page's labels (R04: 18,696 states lump to 607 blocks), not a faster solve of the 48.7-million-edge chain.

## 10. What proves it works on crafts of any complexity

A benchmark route is a measurement, never the acceptance (#812). The proof is a family of generated targets of growing size, run through the planner itself:

- **Generator.** From the pinned game data: bases of every item class in scope; 1 to 6 wanted families with tiers T1 to T3 and roll limits; prefix and suffix mixes; with and without metamods; method sets growing by batch (basic orbs; plus essences; plus fossil sets with 10 to 1,000 sets; plus Harvest; plus unveil; plus the Lock; plus donors; plus strands 0 to 100); start options (a bought base, a fractured base, a vendor recipe, a given item). Prices: the committed snapshots, and each currency scaled by a random factor between 0.3 and 3, because prices decide where the near ties are (R04's expanded share went from 78% to 94% between two snapshots).
- **Measured per target:** time and peak memory per stage; states expanded, actions built, the bound's keys; the reach of the shown plan; `L(root)`, `U` and the gap at the stop.
- **Accepted when:** (1) on every generated target the walk can still hold, `L(root) <= V*` and `U <= (1 + eps) V*` against the full walk's optimum, and with `eps = 0` the mean equals the walk's to 1e-9; (2) on all targets, the shown plan's mean agrees with a simulation of the plan (|z| <= 4, OR-30); (3) the time and memory follow a stated relation to the bound's keys, the plan's reach and the actions built, fitted on the generated family and holding on R04, R14, R07, R24, R08, R10, R25 measured after, with no constant chosen per route; (4) a target past the budget always returns a plan with its gap, never a refusal, when a new base can be bought.

## 11. Questions only the owner can answer

**Question 1. May the planner stop when its plan is proved within a stated share of the cheapest, instead of proving it is exactly the cheapest?**

Context. The record disagrees with itself. The owner's answer on #81 (2026-10-31) was "exact when it fits in about a minute, otherwise an approximate answer marked as such, with an error of at most 1%". OR-11 (2026-11-01) replaced it with "exact among realistic routes, never an interval", and the search was built to prove the exact optimum. Proving it is what takes the time on the fast path (sections 2 and 3), and the difference it buys is below how much prices move: between the two committed snapshots ten days apart, the Exalted Orb moved +58%, the Orb of Annulment +230% and the Fracturing Orb +164%, and R04's expanded share moved from 78% to 94%. Under every option the mean shown is exact for the plan shown; what changes is how close to the cheapest that plan is proved to be.

- (a) Exact always (today). R04's search keeps its 364-510 s and R14's its 231-238 s of proof; ticket 2 still helps only where the search can be skipped entirely.
- (b) Exact when it fits in about a minute; otherwise stop when the plan is proved within 1% of the cheapest, and say so ("this plan costs X on average; no plan costs less than Y"). Measured: R04's plan is proved within 0.49% after the bound (99-148 s) and its greedy plan (12 s), and it is the same plan as today's exact one; R14's within 0.09% after 23 s and 37 s, a plan 0.0004% dearer than today's. The search's proof (hundreds of seconds) is skipped on both.
- (c) The same with 0.1%. R14 as in (b). R04's bound alone leaves 0.49%, so the search must still raise the lower figure: today's search reaches 0.1% at round 71 of 77 (492 s of 510 s); a search that refines where the gap is may do better, not measured.

Under all three, the methods without a bound yet (unveil, roll limits, many fossil sets, the Lock, donors, imprints) stay slow until ticket 4 lands for them.

Recommendation: (b). It is the owner's own rule of #81, it keeps OR-11's point answer (the plan and its exact mean; the bound is a certificate beside it, as #376 and #499 already decided), and a 1% difference is far below the price movement above.

**Question 2. How long may one plan take on the website before it stops and shows the best plan found so far?**

Context. With the stop of ticket 2 the search can stop at any round with a plan and its proved gap (when the start item is bought). Until the families of ticket 4 have their bounds, plans with unveil, roll limits, many fossil sets, the Lock or donors still walk, and can take tens of minutes or run out of memory.

- (a) 1 minute: fast pages; until ticket 4 lands, those families answer with a wide gap or "stopped".
- (b) 10 minutes: most fallback routes finish, but the website waits.
- (c) No limit (today): the answer always comes when it fits in memory, after any time.

Recommendation: (a) as the goal, with (b) as the stop-and-say-so net (OR-12) until ticket 4 lands.

**Question 3. How precise must p50 and p90 be?**

Context. The percentiles are computed after the plan, on its chain. Today's method halves its grid step until a net stops it, and its bracket shrinks only as fast as the step: on R14 at the 2026-11-10 prices p50 was bracketed ±28% after 52 s, ±17% after 154 s and ±9% after 378 s (heavy run 42955861457), and ±4.8% at the next step, with the whole plan at 869-1,331 s and the runner near its 16 GB (heavy run 42967824661, #744). The owner chose on #709 to print the bracket.

- (a) ±5%: today's finest step; R14's percentiles take 10 to 17 minutes and nearly the whole runner.
- (b) ±10%: about 6 minutes of percentiles on R14, well inside the memory (what R14 gets today).
- (c) ±20%: about 2.5 minutes on R14; a bracket like "p50 between 5,900 and 8,800" says little.
- In every case the plan itself need not wait: the page can show the plan and its exact mean first and the percentiles when they are done.

Recommendation: (b) for now, with the plan shown before the percentiles, and the research spike of section 6 (a method whose error does not grow with the number of steps), which could make ±5% or ±1% cheap later.

## 12. Limits of this research

- The gap trace measures today's search with an upper figure added from outside; it shows what a stop at a gap would have expanded with today's expansion order, not what a search built for the gap would expand (that can only be less or equal, since it expands where the gap is).
- The first executable plan is one simple choice (the bound's greedy plan); a given route (#536) or a few rounds of improvement on its reach are the obvious alternatives and were not measured.
- One price snapshot for the traces (2026-11-10). Near ties move with prices.
- The per-method table is from the ADRs and the issues; the bounds proposed for imprints, unveil, donors and the Lock are sketches with a soundness argument, to be proved and tested in their tickets.
- No generated family was run here; section 10 is the acceptance design, not a result.

## Runs and scripts

All on GitHub runners (ubuntu-latest, 4 vCPU, 16 GB) through `heavy_dispatch.py`, branch `research/planning-speed`, prices `tests/fixtures/prices/routes-allflame-2026-11-10.json`:

- R04: heavy run 43317321351, `ROUTE_PRICES=tests/fixtures/prices/routes-allflame-2026-11-10.json uv run --no-sync python -u research/planning-speed/gap_trace.py --route r04 --out $OUT_DIR`.
- R14: heavy run 43319820843, the same with `--route r14`.
- R08: heavy run 43320834722, the same with `--route r08` (`solver="envelope"` forced; `auto` takes the bound pruning at 40 offers or more).
- Read from earlier runs, not run again: heavy run 42955861457 (R04 and R14 through `packed_routes.py plan --solver auto` at the same prices, with the risk), 42967824661 (R14 at the finest risk step), 42400486309 (R04's route page, #689, #680).
- Locally (one process, seconds): J01 and R13 with the same script; the bound's greedy plan equals the optimum there too (J01 34,288.31, 8 states; R13 14,960.48, 194 states), and their bounds are exact (100.00%), so they are not evidence of anything harder. V01 has no start price in the 2026-11-10 snapshot and was not run.

Reproduce: the command above with `--route r04|r14|r08|r13|j01`; the summary tables come from the `*.trace.json` each run writes.

## Sources

- Bertsekas, D. P., Tsitsiklis, J. N. (1991). An analysis of stochastic shortest path problems. *Mathematics of Operations Research* 16(3): 580-595. https://pubsonline.informs.org/doi/10.1287/moor.16.3.580 (preprint https://dspace.mit.edu/bitstream/handle/1721.1/3088/P-1815-19107256.pdf)
- Hansen, E. A., Zilberstein, S. (2001). LAO*: A heuristic search algorithm that finds solutions with loops. *Artificial Intelligence* 129(1-2): 35-62. https://dblp.org/rec/journals/ai/HansenZ01a
- Bonet, B., Geffner, H. (2003). Labeled RTDP: Improving the convergence of real-time dynamic programming. ICAPS 2003. https://aaai.org/papers/icaps-03-002-labeled-rtdp-improving-the-convergence-of-real-time-dynamic-programming/
- McMahan, H. B., Likhachev, M., Gordon, G. J. (2005). Bounded real-time dynamic programming: RTDP with monotone upper bounds and performance guarantees. ICML 2005. https://dev.icml.cc/Conferences/2005/proceedings/papers/072_BoundedRTDP_McMahanEtAl.pdf
- Smith, T., Simmons, R. (2006). Focused real-time dynamic programming for MDPs: squeezing more out of a heuristic. AAAI 2006. https://cdn.aaai.org/AAAI/2006/AAAI06-192.pdf
- Dai, P., Mausam, Weld, D. S., Goldsmith, J. (2011). Topological value iteration algorithms. *JAIR* 42: 181-209. https://jair.org/index.php/jair/article/view/10725
- Schmalz, J., Trevizan, F. (2024). Efficient constraint generation for stochastic shortest path problems. AAAI 2024. https://ojs.aaai.org/index.php/AAAI/article/view/30005 (extended: https://arxiv.org/abs/2401.14636)
- Brázdil, T., Chatterjee, K., Chmelík, M., Forejt, V., Křetínský, J., Kwiatkowska, M., Parker, D., Ujma, M. (2014). Verification of Markov decision processes using learning algorithms. ATVA 2014. https://www.cs.ox.ac.uk/David.Parker/papers/atva14.pdf
- Křetínský, J., Meggendorfer, T. (2020). Of cores: a partial-exploration framework for Markov decision processes. *LMCS* 16(4). https://arxiv.org/abs/1906.06931
- Haddad, S., Monmege, B. (2018). Interval iteration algorithm for MDPs and IMDPs. *Theoretical Computer Science* 735: 111-131. https://hal.archives-ouvertes.fr/hal-01809094
- Hartmanns, A., Kaminski, B. L. (2020). Optimistic value iteration. CAV 2020. https://arxiv.org/abs/1910.01100
- Givan, R., Dean, T., Greig, M. (2003). Equivalence notions and model minimization in Markov decision processes. *Artificial Intelligence* 147. https://doi.org/10.1016/S0004-3702(02)00376-4
- Givan, R., Leach, S., Dean, T. (2000). Bounded-parameter Markov decision processes. *Artificial Intelligence* 122: 71-109. https://doi.org/10.1016/S0004-3702(00)00047-3
- Abel, D., Hershkowitz, D. E., Littman, M. L. (2016). Near optimal behavior via approximate state abstraction. ICML 2016. https://proceedings.mlr.press/v48/abel16.html
- Klößner, T., Hoffmann, J. (2021). Pattern databases for stochastic shortest path problems. SoCS 2021. https://ojs.aaai.org/index.php/SOCS/article/view/18561
- Trevizan, F., Thiébaux, S., Haslum, P. (2017). Occupation measure heuristics for probabilistic planning. ICAPS 2017. https://ojs.aaai.org/index.php/ICAPS/article/view/13840
- Torralba, Á., Hoffmann, J. (2015). Simulation-based admissible dominance pruning. IJCAI 2015. https://ijcai.org/Abstract/15/241
- Ravindran, B., Barto, A. G. (2002). Model minimization in hierarchical reinforcement learning. SARA 2002. https://link.springer.com/doi/10.1007/3-540-45622-8_15
- Guestrin, C., Koller, D., Parr, R., Venkataraman, S. (2003). Efficient solution algorithms for factored MDPs. *JAIR* 19: 399-468. https://jair.org/index.php/jair/article/view/10341
- Kolobov, A., Mausam, Weld, D. S. (2012). A theory of goal-oriented MDPs with dead ends. UAI 2012. https://www.auai.org/uai2012/papers/306.pdf
- Dechter, R., Pearl, J. (1985). Generalized best-first search strategies and the optimality of A*. *Journal of the ACM* 32(3): 505-536. https://ics.uci.edu/~dechter/publications/r0.pdf (a scanned copy; the result as summarised in https://en.wikipedia.org/wiki/A*_search_algorithm, "Optimal efficiency")
- Helmert, M., Röger, G. (2008). How good is almost perfect? AAAI 2008. https://mlanthology.org/aaai/2008/helmert2008aaai-good
- Hughett, P. (1998). Error bounds for numerical inversion of a probability characteristic function. *SIAM J. Numer. Anal.* 35(4): 1368-1392. https://epubs.siam.org/doi/10.1137/S003614299631085X
- Crafting tools (Craft of Exile, POE2Crafting, pyoe2-craftpath): the repository's prior-art note `docs/research/2026-10-30-1-prior-art-and-data.md`, sections "Craft of Exile in depth" and the tool table.
- In this repository: ADR-0063 and its updates; `docs/research/2026-11-01-exact-merging-and-cuts.md` (#312), `2026-11-06-376-junk-aware-bound.md` (#376), `2026-11-06-497-walk-free-bound.md` (#497), `2026-11-01-dr-1-exact-planning-at-scale.md`; issues #398, #812, #507, #535, #626, #637, #680, #689, #696, #702, #738, #743, #744, #755, #770, #799, #225, PR #771.
