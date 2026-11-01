# Exact merging, exact cuts and the size of R04, R14 and R08 with the Alchemy (ticket #312)

Question of the ticket (with the owner's two comments): are R04, R14 and R08-with-the-Alchemy big because of detail no decision sees, can the planner merge such states **exactly**, and what can it cut **by itself**, with a stated guarantee, instead of by a fixed number? Everything below was measured on GitHub runners (`research/312-measure`, through `heavy_dispatch.py`, nothing heavy on the owner's PC); the scripts are in `research/312/`. Numbers are the model's: the 3.29.3.3 data, the fixture prices of the routes (`routes-allflame-2026-10-31.json`), the offers of each route's target file.

## Short answer

1. **Exact merging is not what makes R04 and R14 big.** The coarsest exact partition (same goal status, same actions with the same costs and the same outcome chances over the classes, i.e. lumpability) merges R04 177,242 -> 89,778 states (2.0x; edges 3.1x) and R14 816,153 -> 589,930 (1.4x). It merges small routes enormously (R05 1,185 -> 10, R10 425 -> 3, R13 4,066 -> 79, R08 with the Alchemy 87 -> 5), where the planner already solves in seconds to minutes. The states of R04 and R14 differ because the junk mods are read by the Annulment, the Exalted Orb and the essences of those routes (numbered family types `~n`); the merge pass finds what is exactly redundant, and it is about half of R04 and a quarter of R14.
2. **What stopped R04 was the solver's memory, not the state count.** R04's walk takes 380 s and 1.3 GB. The classes, solved on flat numpy arrays by policy iteration, give **R04 = 69,716.06 chaos exactly** in 155 s and under 2 GB; **R14 = 5,786.62 chaos** in 19 s after a 29-minute walk. The production solver dies at 15.7 GB on R04 because it builds Python objects for 171 million edges.
3. **Cuts by cost bounds work only with a strong lower bound, and the cheap one is not strong.** "Luckiest path" plus Bellman sweeps cuts 0 of 414,544 actions of R04 after 32 sweeps (the bound is 0.6% of the cost) and about 0 of R14's. With a perfect bound an exact search would still need only 13% of R04's classes and 11% of R14's: the room is there. A coarse optimistic model (states told apart by the status of the wanted mods, the rarity and the number of mods per side) gives a bound of 97% of the cost on R13 but under 4% on R04 and R14, and cuts nothing there; most of the actions not chosen are within 1% of the best one and no bound short of the exact value can cut them.
4. **A fixed number is not safe, as the owner said.** A rail of 1,000 uses makes R11 (1,086 chaos) infinite; lumping outcomes below 1e-3 moves R13 from 6,300 to between 24 and 16,800 chaos and R08 with the Alchemy by +4.3%. 1e-4 and 1e-5 changed nothing on any route measured, but nothing in the route says why.
5. **Recommendation:** exact first, in this order: (a) a flat-array solve for big graphs (a ticket; R04 and R14 become exact in minutes); (b) a faster walk; (c) bound-guided expansion with an incumbent and a lower bound, an exact cut, once a bound is found that is strong on R04 and R14 (the lucky path and the coarse models tried here are not); (d) decision-relevance cuts only as a reported tolerance, and only once (c) gives bounds tight enough to settle choices (they settle none today); (e) time and memory limits that stop and say so, never a count or a chance that silently changes the answer. The draft is `docs/adr/0059-exact-cuts-and-flat-solving-for-big-graphs.md`.

## What the code does today of the two earlier notes' recommendations

`2026-10-30-2-state-compression.md` (compression) and `2026-10-30-4-solver-engineering.md` (solver):

| Recommendation | Today | Where |
| --- | --- | --- |
| Exact self-loop elimination ("repeat until it exits") | Done | `solver/_graph.py` (`self_loop`), the solve works on the exit chances |
| SCC condensation, reverse topological order | Done | `solver/_scc.py`, `_solve.py` |
| Policy iteration / sparse elimination inside a component | Done, but on Python objects | `solver/_component.py`, `_sparse.py` |
| Cache kernels by pool signature | Done | `Abstraction._prepared_by`, `tier_table`/`pool_candidates` caches (#118) |
| Equal kernels per state keep the cheapest | Done | `Abstraction.kernel_key`, `cli/_prune.py` (#118) |
| Behavioural group types for the junk (`~n` numbered family types, a multiset of slots) | Done | `abstraction/_state.py` `Slot`, `_kinds.py`; the junk is a family type only when an enabled action reads the pool (`Reads.pool_weight`), otherwise one kind `""` |
| Bound-based action elimination (FTVI) | Only for **offers**, once for the whole model, with a certificate; **not for states or branches** | ADR-0031, `abstraction/_bound.py`, `cli/_bound_prune.py` |
| `h_min`, the lucky-path lower bound | No (the offer bound uses `rho = cost / pbar` from the pool) | - |
| Lazy / heuristic expansion (LAO*) | No: the whole reachable graph is walked first, then solved | `solver/_graph.py` |
| Lumpability / bisimulation partition refinement | No in the product; `research/312/exact_classes.py` is the first code of it | - |
| Optimistic and pessimistic abstraction with certified bounds (game / interval abstraction) | Done, as "two bounds around one policy" (the variants level) | ADR-0023, `solver/_bounds.py`, `_minmax.py`; R04 has none (Fracturing Orb declares no variants) |
| Flat arrays / compiled Bellman kernels (Numba) | No: Python objects (12 bytes per transition in `Bellman`, but Python lists for the graph); no Numba in the project | `solver/_component.py` |
| Exact fixed-policy risk metrics after the mean-optimal policy | Done | `risk/` |

So of the compression note the code does the state typing and the kernel caches, not the quotienting; of the solver note the code does everything except action elimination on states, lazy expansion and the flat/compiled representation. The last two are what #312 shows to matter.

## What ran

| Run | What |
| --- | --- |
| `exact_classes.py` on R05, R10, R11, R12, R13 | Full walk with all twin-merged offers, exact classes, rails, lumping, quotient (runs 41323124419, 41323513241, 41326993936, 41327017816, 41327042685) |
| the same on R08 with the Alchemy as a planner action | Offers = the 128 the production R08 plan uses, plus the Alchemy and the restart (run 41325403247) |
| the same on R04 and R14, `--stop-after-quotient` | Full walks (41325482062, 41325723689), then `prune_analysis.py` on the quotient |
| `time_routes.py --route r08 --exact` | Today's production R08 for reference (41320747282) |
| R09 | The full walk with all twin offers did not finish in the 60-minute runner limit (cancelled); not measured |

`exact_classes.py` walks the exact graph the planner would (the same abstraction, offers and prices as `make_plan`), keeps it as arrays (one record per distinct `kernel_key`), and refines the partition (the `values` partition: the action set of a class is the set of (cost, distribution over classes) pairs, a dearer duplicate dropped). The value of the whole graph and of the quotient were compared on the small routes (R08 with the Alchemy: 74.904999259 on both, relative difference 1e-15). `prune_analysis.py` solves the quotient on flat arrays (self-loops eliminated, policy iteration from a proper start policy, BiCGSTAB for each evaluation, Bellman residual reported; it matches the production solver to 1e-12 on R05, R08 and the synthetic test) and measures the cuts.

## Exact classes

| Route | Offers | States | Exact classes | Factor | Edges before -> after | Exact mean cost (chaos) | Walk |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| R05 strength ring | 72 | 1,185 | 10 | 118x | 7.07 M -> 402 | 9.613 | 33 s |
| R10 fractured boots | 61 | 425 | 3 | 142x | 562 k -> 43 | 111.33 | 10 s |
| R11 reservation helmet | 59 | 18 | 2 | 9x | 7,921 -> 3 | 1,085.96 | 1 s |
| R12 lightning amulet | 62 | 33 | 3 | 11x | 10,301 -> 53 | 55.64 | 3 s |
| R13 life/resist belt | 10 | 4,066 | 79 | 51x | 38,285 -> 4,333 | 6,300.85 | 4 s |
| R08 + Alchemy (128 offers) | 128 | 87 | 5 | 17x | 326,456 -> 1,071 | 74.905 | 217 s |
| **R04 penetrating quiver** | 8 | 177,242 | **89,778** | 2.0x | 535.9 M -> 171.2 M | **69,716.06** | 380 s |
| **R14 hunter bow** | 12 | 816,153 | **589,930** | 1.4x | 9.65 M -> 6.90 M | **5,786.62** | 1,721 s |

(Production R08, Alchemy as the start item, today: 87 states, 158 s, 76.22 chaos; the ticket quotes 1,388 s for it, measured earlier.)

The merge changes no answer: it is lumpability with costs, so the mean, the odds, p50 and p90 of every policy are the same on the class and on its members. Checked by solving both graphs on R05, R10, R11, R12, R13 and R08 with the Alchemy (equal to 1e-12 and better).

**What makes merged states differ** (`explain`: for each part of the state, how many classes hold members that differ in it). On R04: the status vector differs inside 57,066 of the 89,778 classes, the slot contributions inside 49,212, the fractured mods' ids/contributions inside 11,881; the number of mods per side inside only 19 classes. On R14: only the junk slots' kinds (190,366 classes). On R05, R10, R13 and R08 with the Alchemy it is the junk slots and the status. So the states merged are those that differ in junk or in status the remaining policy cannot use; the reverse is that the rest of R04's and R14's states are distinguished by exactly what Annulment, Exalted Orb and the essences read.

## Where detail enters the state, and what a merge in the walk would need

`CompressedState` = flags (rarity, corruption, influences) + fractured mods + the status of each leaf + the other mods as **slots** (side, kind, contribution, crafted) + the optional implicits, quality and unveil offer. Detail enters in three places:

1. **The slot kind.** An ordinary mod's kind is `""` (side and contribution only) unless an enabled action reads the pool: then it is the numbered family type `~n` (`_kinds.py`). R04 and R14 enable the Annulment, the Exalted Orb or essences that keep junk, so their junk is typed; routes without them (R05, R10, R13, R08) have kind `""` and merge hugely. The Alchemy alone adds nothing: its 4 to 6 random mods become slots of kind `""` and the 87 states of R08 are the product of the status vectors and the mod counts per side.
2. **The contribution of each slot** (what the mod gives each leaf): it repeats part of the status.
3. **Fractured mods' ids**, kept by kind when an enabled action may fracture.

The exact partition says which of these differences are redundant: they are all present in the merged classes of R04. A merge inside the walk would need a **canonical key** for a state that is cheaper than the partition: two states have the same key only if they are in the same class. The partition shows no single projection that is exact on all routes (the candidate projections of `exact_classes.py`, e.g. "slots -> how many per side", merge R08 70 -> 70 but not R04's classes), and the whole gain is 2.0x on R04 and 1.4x on R14, so **a canonical key is not worth building**; the quotient stays a post-pass for checks and for the flat solve (it makes the solve 2x cheaper).

## The size is real; the tools that cut it are the solver and the walk

**Flat solve.** The class graph of R04 has 89,778 states, 414,544 actions, 171 M edges: 5 s to flatten, policy iteration 8 rounds, 155 s, 2 GB; the production solver cannot hold it. R14's has 589,930 states, 1.92 M actions, 6.9 M edges: 19 s. Both results carry the Bellman residual (3e-14 and 3e-13 of the start value). A certified bound (the production solver's `error_bound`) is a ticket, not done here.

**Walk.** R04: 380 s for 350,923 kernels; R14: 1,721 s for 1.58 M kernels and 816 k states, 2.1 ms per state with 12 offers, Python-bound. Nothing parallel exists in the walk; the 20 runners are idle during it.

## Cuts by cost bounds (the owner's correction, item 1)

Measured on the exact quotient with `prune_analysis.py`. An action of a state is **competitive** when its cost with the lower bounds of its outcomes does not exceed the best action's cost with the upper bounds; any other action is worse than a known one, so removing it changes no answer (branch and bound, ADR-0031 at the level of states). Incumbent: the start priced at f times its optimal value (f = 1 is a perfect incumbent), every other state one restart more (the route "buy the start item again, then follow the incumbent"); "perfect" means every state's upper bound is its own optimal value, the best case for any cut.

| Route | Bound | Bound / exact cost of the start | Competitive actions (of all) | Classes needed |
| --- | --- | ---: | --- | --- |
| R05 | luckiest path + 16 sweeps | 1.00 | 9 of 141 | 5 of 10 |
| R08 + Alchemy | luckiest path + 32 sweeps | 0.80 | 25 of 309 | 5 of 5 |
| R13 | luckiest path + 32 sweeps | 0.0004 | 280 of 281 | 79 of 79 |
| **R04** | luckiest path + 32 sweeps (45 s) | **0.0064** | **414,544 of 414,544** | 89,778 of 89,778 |
| **R14** | luckiest path + 32 sweeps (3 s) | **0.131** | **1,920,629 of 1,920,668** | 589,930 of 589,930 |
| R04 | a perfect bound | 1.00 | 89,777 (one per class) | **11,767 (13.1%)** |
| R14 | a perfect bound | 1.00 | 589,930 | **64,093 (10.9%; 85,633 of 816,153 states)** |

**A stronger bound: optimistic coarse models** (`exact_classes.py --coarse-lb`). States are told apart only by a cheap key; the coarse state offers every action of every member, so its optimal value is never above a member's exact value (a concrete policy is a policy of the coarse model that picks the action of the member it is in). A class takes the best of its members' coarse values. Value of the start over the exact cost, with the number of coarse states:

| Key | R13 | R04 | R14 |
| --- | --- | --- | --- |
| leaf status | 2.4% (204) | 1.4% (72) | 0.5% (48) |
| + rarity | 17% (240) | 1.4% (73) | 0.5% (64) |
| + mods per side | **97.4%** (470) | 1.6% (772) | 4.1% (365) |
| + fractured mods' ids | 97.4% (470) | 3.5% (5,030) | 4.1% (365) |

(R13 was run locally in 12 s; R04 and R14 on runners, runs 41329298116 and 41329407883.) On R13 the bound is almost the cost; on **R04 and R14 it stays under 4%** and, with it, **every action stays competitive** (414,544 of 414,544 on R04; 1,920,630 of 1,920,668 on R14), with the incumbent at f = 1, f = 1.5 or perfect. The cost of these two routes is the cost of rare events the keys tried here do not see: the optimistic model lets nature pick the luckiest junk, and the junk is what the Annulment, the Exalted Orb and the essences of R04 and R14 gamble on. A bound that works there must keep the junk's family types, which is the state that is too big; so the exact cut by cost, as measured here, **does not shrink R04 or R14**, and the first ticket to build is the flat solve and the faster walk, not the cut.

**Near ties.** Among the actions not chosen in the classes the optimal policy reaches, the share within 1% of the best one: R04 49,684 of 52,348 (42,845 within 0.1%, 6,839 within 1%, 2,459 within 3%, 169 within 10%, 32 within 30%, 4 worse); R14 112,438 of 148,596 (39,515 within 0.1%, 72,923 within 1%, 860 within 3%, 20,640 within 10%, 14,546 within 30%, 112 worse); R13 144 of 147. An exact cut removes an action only if the bound's error is below the action's gap, so these stay unless the bound is nearly exact.

**Cost of the bound.** A sweep is one pass over the edges: 1.4 s on R04's 171 M edges, 0.1 s on R14's; the coarse optimistic models are small (a few hundred to a few thousand states) and solve in well under a second. The production offer bound (ADR-0031) is the 707 s of the ticket's R08 figure; the flat bound is far cheaper once the graph exists, but it exists only after the walk. To cut the walk the bound must be available **before** the walk, from an abstraction that does not need the full graph (the variants level of ADR-0023 is that kind of thing). That is what the second ticket below builds and measures.

## Decision-relevance cuts (item 2)

An outcome is lumped when its swing `p * (UB - LB)` is below the allowance of its state, `margin / (2 * outcomes)`, where the margin is the gap between the best action's upper Q and the next one's lower Q. The two lumped models (the lumped mass to the goal, charged the upper bound = pessimistic, the lower bound = optimistic) bracket the exact value, and no choice with a positive margin can change.

Measured: with the cheap bounds the margin is **zero at every state of every route** (R04: 1 state with a forced choice, 0 settled; R14: 8 forced, 0 settled; R05, R10, R13, R08 with the Alchemy likewise), so nothing is lumped and the value is unchanged (the bracket is 0). With a perfect bound the swing is zero and everything could be lumped without error, which only restates that the cut is worth exactly as much as the bound. **The guarantee it can state:** `V_opt <= V* <= V_pess`, relative gap reported, every settled choice unchanged. It does not shrink anything until the bounds settle choices.

## Fixed rails and thresholds, for comparison (items 2 and 3 of the first comment)

Rails (ceiling on expected uses of an action in a row) and lumping below a chance, computed on the exact quotient of each route that solved (R04 and R14 only had the quotient analysed):

| Route | Rail 100,000 / 10,000 / 1,000 | Lump 1e-3 (pessimistic / optimistic) | Lump 1e-4 and 1e-5 |
| --- | --- | --- | --- |
| R05 | no change | 9.613 = exact / exact (raw states 1,185 -> 669) | no change |
| R10 | no change | exact / exact (425 -> 342) | no change |
| R11 | no change / no change / **infinite** | **infinite** / exact | no change |
| R12 | no change | exact / exact (33 -> 27) | no change |
| R13 | no change | **16,800 (+167%)** / **24 (-99.6%)** | no change |
| R08 + Alchemy | no change | **78.11 (+4.3%)** / 74.90 | no change |

A fixed 1e-3 shrinks the raw graph 10 to 44% on the routes where it is harmless and gives an answer that cannot be told from a wrong one on R13: it cannot be a default. The tail 1e-4 and 1e-5 changed nothing, but without the bracket the report could not say so. A 1,000-use rail removes R11's only route. These are the measurements behind "rails only as a stop-and-say-so safety net".

## Effect on the routes that already solve

R05, R10, R11, R12, R13 and R08 with the Alchemy: the exact merge leaves every value as it was (1e-12 and better); a flat solve of the class graph takes under a second where the production solve takes seconds to minutes; the cuts by bounds drop 141 -> 9 actions on R05 and 309 -> 25 on R08 with the Alchemy (after 16 and 32 sweeps) without touching the value. The production planner does not use any of these today; its own time on these routes is the walk (kernels) plus the offer bound, not the solve. R09 was not measured (its full walk did not finish in a 60-minute runner).

## Honest limits

- The quotient, the bounds and the coarse models are built **after** the full walk, so they measure how much a cut could remove, not the walk time it would save. The walk itself needs the bounds before it.
- `prune_analysis.py`'s value is policy iteration with a reported residual, not the certified bound the production solver gives; on R05, R08 and the synthetic graphs it matches the production solver to 1e-12.
- R14's first walk (a time-limited one) showed 1.0x merging (816,126 classes of 816,144 states): an unfinished walk keeps the frontier apart. The complete walk gives 589,930.
- R09, the other routes of the ticket's list (R06, R03, J01) and the production R08 with every offer were not measured.
- One price set (the fixture of 2026-10-31); a different price set changes which actions are near ties.
