# A lower bound that sees the crafted mods: 99.5% of R04 and 98.1% to 99.99% of R14, and why it does not cut the walk (ticket #376)

Question of the ticket: build a lower bound on the remaining cost that sees the junk mod types (pattern databases, cost partitioning), without the full graph, and measure it on R04, R14 and S02 against the 13% / 11% prize of a perfect bound (ADR-0063 point 3, note `2026-11-01-exact-merging-and-cuts.md`). Done when it reaches half of the exact cost on R04 and R14, or a note says why it cannot. Rules read: OR-10 (no detail that no decision reads), OR-12 (the general rule is exact branch-and-bound against an incumbent, a fixed rail is only a safety net), OR-13 (a cut says what it guarantees), OR-14 (route-level pruning), OR-25 (research the method), OR-29 (open points become issues). Scripts: `research/376/junk_bound.py` (the measurement), `show.py` and `tables.py` (the tables below), `tests/test_research_376_bound.py` (the proof obligations on random graphs). No `src/` change.

## Short answer

1. **The half-of-the-exact-cost test is met, by a wide margin, and the junk types are not what it needed.** The optimistic abstraction whose key is *(status of the wanted mods, rarity, mods per side, fractured ids, the crafted mods)* is a lower bound of **99.48% of the exact cost on R04** (7,791 abstract states), **98.10% on R14** (850 states; **99.99%** with the protected tags of the junk, 1,969 states) and 100.00% on S02 (91 states). It is never above the exact value of any state (0 violations on all three routes, and on random graphs in the test). #312's cheap bounds were 1.4-4.1% on R04 and R14 because their key left out the **crafted mods**, the metamod "Cannot roll Attack Modifiers" above all: a state without it borrows, for free, the Exalted Orb of a state that holds it (whose pool has no attack mods). Adding the junk kinds, their pool weight or their tags adds at most 0.4% on R04 and 1.9% on R14.
2. **A strong bound does not make an exact cut strong.** What a bound cuts is set by the near ties, not by its ratio. On **R04** the bounds of 99.5% to 99.9% keep **78% to 98%** of the 177,242 walked states (perfect upper bound and the incumbent "buy again, then follow the best route"); a perfect bound keeps 10.7% and 21.2%. On **R14** the 99.99% bound keeps **12.7% to 21.6%** of the 816,153 states (perfect: 10.7% and 20.3%), the 98.1% bound 88%. So the pattern bound would cut R14's walk by about 80% and R04's by 2% to 22%, and only if it is built without the walk, which this research did not do (#497).
3. **What it is good for is a guarantee, not a cut.** A pruned search that ends with the cost `U` of the best route it kept can print that the best possible cost lies in `[LB, U]` (OR-13): 0.52% for R04's optimal policy, 0.01% for R14's with the tags (#499). That is what route-level pruning (audit step 6, OR-14) lacks and what an exact bound can give it.

## The bound

A **pattern** is a function `phi` of the state. The **optimistic abstraction** of `phi` has one state per value of `phi` and offers, in each, the action of every concrete state with that value, with its outcomes seen through `phi` (the pushed kernel, the dearer of two actions with one pushed kernel dropped). A concrete policy is a policy of the abstraction (it takes the action of the member it is in), so the abstraction's optimal value never exceeds the exact value of a member: `V_phi(phi(s)) <= V*(s)` for every `s`. This is the pattern database of the key; it is also ADR-0023's optimistic model (`V-`), with member-by-member kernels. The `tests/test_research_376_bound.py` property tests check on random shortest-path graphs that it never exceeds the exact value, is exact for the identity key, and is not stronger for a coarser key.

Cost partitioning was not needed: one pattern already gives 99.5%, and the sum of two patterns cannot exceed the exact cost. The same pattern's value is used for every state of a class (`max` over the members of the class, valid because `V*` is constant on an exact class).

The measured keys (`research/376/junk_bound.py`, `KEYS`): the existing `312-best` (status, rarity, sides, fractured ids) and `status`, then `+crafted` = `312-best` plus the multiset of crafted slots, then the junk added in several ways: the protected tags per side (`+crafted+tags`), the number of different junk types, the total pool weight of the held junk in 4 and 16 buckets, the exact kinds per side, the exact slots, the identity.

## What was measured

Ratio bound / exact cost of the start. Exact values (main of 2026-11-06, the packed solver's figures): R04 69,257.5365, R14 5,784.4887, S02 33,878.6728 (1-chaos prices, strand words removed). R04 and S02 are solved on their exact classes (89,778 and 20), R14 on its 816,153 states (unmerged). Runs on GitHub, ubuntu-latest, 4 vCPU, 16 GB, through `heavy_dispatch.py`.

| Key | R04 abstract states | R04 bound / exact | R14 abstract states | R14 bound / exact | S02 abstract states | S02 bound / exact |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `status` | 72 | 1.43% | 48 | 0.50% | 9 | 2.73% |
| `312-best` (#312's best key) | 5,030 | 3.50% | 365 | 3.67% | 91 | 100.00% |
| **`+crafted`** | **7,791** | **99.48%** | **850** | **98.10%** | 91 | 100.00% |
| `+crafted+tags` | 13,060 | 99.62% | 1,969 | **99.99%** | 91 | 100.00% |
| `+crafted+nkinds` | 10,428 | 99.48% | 1,259 | 98.10% | 183 | 100.00% |
| `+crafted+weight4` | 13,258 | 99.56% | 1,586 | 98.10% | 241 | 100.00% |
| `+crafted+weight16` | 30,428 | 99.85% | 4,903 | 98.11% | 720 | 100.00% |
| `+crafted+tags+weight16` | 58,428 | 99.92% | 12,101 | 99.99% | 720 | 100.00% |
| `+crafted+prefix-kinds` | 11,759 | 99.48% | 19,145 | 98.10% | 2,415 | 100.00% |
| `+crafted+suffix-kinds`, `+crafted+kinds`, `slots`, `identity` | 121,541 to 177,242 (not built: the abstract model passes 80 M edges) | - | 35,406 to 816,153 | **100.00%** | not built | - |
| `crafted-only` | 4 | 0.05% | 16 | 13.10% | 2 | 0.42% |
| `status+crafted` | 144 | 1.49% | 152 | 13.63% | 9 | 2.73% |
| `+crafted` without rarity | 7,790 | 99.48% | 816 | 94.95% | 86 | 100.00% |
| `+crafted` without mods per side | 1,778 | 3.23% | 175 | 15.57% | 15 | 100.00% |
| `+crafted` without fractured ids | 1,319 | 95.98% | 850 | 98.10% | 91 | 100.00% |

Reading it:

- **The crafted mods are the missing piece.** `312-best` plus the crafted multiset takes R04 from 3.5% to 99.5% and R14 from 3.7% to 98.1%. R13 (4,066 states) goes from 97.4% to 100% with it as well (a local run). The mods per side are needed too (without them R04 drops to 3.2%); the fractured ids add 3.5% on R04; the rarity matters only on R14 (3.2%).
- **The junk kinds are nearly irrelevant.** On R04 the exact kinds of the prefix side add nothing (99.48%), the pool weight 0.4%, the protected tags 0.14%. On R14 only the tags matter (98.10% to 99.99%); the identity-level keys, which tell every state apart, are the 100.00% reference. The 16 (R04) and 28 (R14) numbered junk types never needed to be told apart. The ticket's title assumed that the junk types are what the bound lacks; they are a 0.1% to 1.9% refinement.
- **Time and memory of the bound.** Given the walked graph, a key of 850 to 13,000 abstract states is built and solved in 0.5 to 1.5 s (R04 `+crafted` 0.5 s, 1.58 M abstract edges; R14 `+crafted+tags` 1.5 s, 4.7 M edges); the biggest R04 key (58,428 states, 46 M edges) takes 22 s. The memory is that of the walk (1.5 GB for R04 after the walk, 8-9 GB for R14's 1.58 M kernels) plus 1-3 GB for the packed kernels; the 11.3 GB peak of the R04 run is the exact solve of the 171 M-edge quotient, not the bound. The whole runs: R04 820 s (walk 361 s), R14 2,494 s (walk 2,221 s), S02 653 s (walk 640 s). The walk is the cost; the bound adds under a minute to it.

## What a bound cuts: the near ties set the floor

An action is *competitive* when its cost with the lower bounds of its outcomes does not exceed the best action's cost with upper bounds; any other action is in no optimal policy (OR-12's exact branch-and-bound at the level of states, the rule of #312). The table gives the classes reachable through competitive actions, after the walk, on the exact quotient. *Perfect* upper bound: every state's value (the least any bound-based cut leaves); *incumbent*: the start is priced at its optimal value and every other state at one restart more (the route "buy again, then follow the best route"). Bellman sweeps on top of the bound (8) change little.

| Route, bound | Bound / exact | Raw states kept, perfect upper bound | Raw states kept, incumbent |
| --- | ---: | ---: | ---: |
| R04, a perfect bound | 100% | 18,911 of 177,242 (10.7%) | 37,499 (21.2%) |
| R04, `+crafted` | 99.48% | 144,650 (81.6%) | 174,172 (98.3%) |
| R04, `+crafted+tags` | 99.62% | 138,810 (78.3%) | 145,995 (82.4%) |
| R04, `+crafted+weight16` | 99.85% | 138,810 (78.3%) | 140,754 (79.4%) |
| R04, `312-best` | 3.50% | 177,242 (100%) | 177,242 (100%) |
| R14, a perfect bound | 100% | 87,253 of 816,153 (10.7%) | 165,402 (20.3%) |
| R14, `+crafted` | 98.10% | 718,830 (88.1%) | 724,269 (88.7%) |
| **R14, `+crafted+tags`** | **99.99%** | **103,474 (12.7%)** | **176,279 (21.6%)**; 128,110 (15.7%) after 8 sweeps |
| R14, `312-best` | 3.67% | 816,153 (100%) | 816,153 (100%) |
| S02, any | 100% | 106,002 of 106,002 (100%) | 100% |

What error a bound may have before it stops cutting, from the exact values alone (the actions within `eps` of the best are kept; a bound with an error below `eps` everywhere cannot keep fewer):

| `eps` | R04 raw states kept | R14 raw states kept |
| --- | ---: | ---: |
| 0 | 18,911 (10.7%) | 87,253 (10.7%) |
| 0.001% | 18,911 (10.7%) | 88,879 (10.9%) |
| 0.01% | 58,384 (32.9%) | 93,140 (11.4%) |
| 0.03% | 138,635 (78.2%) | 133,971 (16.4%) |
| 0.1% | 138,810 (78.3%) | 606,707 (74.3%) |
| 1% | 177,242 (100%) | 606,782 (74.3%) |

- **R14: the pattern bound is as good as a perfect one.** At 99.99% (error 0.012%) it keeps the 12.7% of the states that the 0.01-0.03% row says it can; a perfect bound with the same incumbent keeps 20.3%, the pattern bound 21.6%. An envelope search on R14 with a bound of 1,969 abstract states would expand about a fifth of the walk.
- **R04: no bound that can be built here cuts it.** The near ties are everywhere (95% of the actions not chosen are within 1% of the best, #312), so a bound with error 0.03% or more keeps 78% of the states, and the cheap ones (error 0.4-0.5%) keep 78% to 98%. A cut needs an error below about 0.01% (33% kept) and a perfect bound is needed for 10.7%. The best R04 bound built (99.92%, 58,428 abstract states) is 8 times that error; the keys that tell the suffix junk apart (121,541 abstract states) are 265 M edges and did not fit. So the exact cut stays at about 80% of R04's walk, while the optimal policy itself uses 10.7% and the guide route 22 states (OR-14).
- **S02 has nothing to cut:** its optimal policy reaches all 20 classes. It is solved by merging; its 640 s are the walk.

## Compared with route-level pruning (audit step 6, OR-14)

| Route | Walked | An exact bound-based cut leaves | The optimal policy uses | The guide route uses |
| --- | ---: | ---: | ---: | ---: |
| R04 | 177,242 | 138,810 (78%) at best bound built; 37,499 (21%) only with a perfect bound | 18,911 (10.7%) | 22 |
| R14 | 816,153 | 103,474-176,279 (13-22%) with the 1,969-state bound | 87,253 (10.7%) | 946 |

An exact cut can only drop what no optimal policy needs *up to the bound's error*; route-level pruning drops what no realistic route uses, which is not exact but is two orders of magnitude smaller on R04. They do different jobs: the pruning decides the size of the search, the bound tells how much the pruning may have cost.

## Is it built without the full graph?

Not in this research, and the note says exactly how far it got.

- **Measured.** The bounds above are built from the *walked* graph (they offer every action of every walked state), so they show what a pattern can reach, not what it costs to get. The abstract models are small (850 to 13,060 states, 1.5 to 4.7 M edges for the keys that matter), so once the members' kernels are known they are solved in about a second.
- **What would build it without the walk.** ADR-0023's `Coarsening` builds an optimistic model from a block, with the kernels of the *extreme* members of an adding action (lightest and heaviest junk), not of every member. It refuses a block that holds a metamod (`BlockHoldsMetamod`) and has no kernel for the Fracturing Orb, the Annulment under a metamod or the essences that remove a mod, and those are the actions of R04 and R14. Extending it is #497.
- **Evidence that the extremes suffice.** Offering only the members of each key that hold the least or the most junk weight (per side and in total) reproduces the bound to 1e-12 on R14: 86,770 of 816,153 members (10.6%), 206,626 of 1,578,415 kernels for `+crafted` (133,300 members and 307,163 kernels for `+crafted+tags`), value 98.0955% and 99.9880% as before. On R04 every member is an extreme (junk is narrow: 18 distinct kinds, at most two junk mods a side), so it shows nothing there, and nothing is saved by the restriction. On S02 114 of 186 kernels. This is a test of the *reachable* members only; the unreachable members that a walk-free build must include (a superset of the reachable ones, so a weaker bound) are not measured, and neither is the proof for the actions other than the adding ones. Both are in #497.
- **So a walk-free build of the R14 bound would touch about 13-19% of the walk's kernels; on R04 it would touch as many as the walk.** R04's bound cuts almost nothing anyway.

## Recommendation

**For audit step 6 (route-level pruning).** Do not design it around an exact bound-based cut: on R04 it leaves 78% or more, on R14 about a fifth. Use the pattern bound for what OR-13 asks of any cut: the pruned plan states the cost `U` of the best route it kept and the lower bound `LB` of the whole graph, and the report says "the best possible cost is in `[LB, U]`". Today's numbers: 0.52% for R04's optimal policy (key `+crafted`, 7,791 states), 0.01% for R14 (`+crafted+tags`, 1,969 states), 0 for S02. The bound must be built from the abstraction, not the walk, or it is no certificate of a pruned search (#497, #499). The key to build is `(status, rarity, mods per side, fractured ids, crafted mods)` plus the protected tags of the junk when a metamod is possible; the junk kinds and weights need not be told apart (OR-10: the search keeps no detail that no decision reads, and these are measured to be below 2%).

**For S4 (#377, envelope search).** Its precondition ("a bound of at least half of the exact cost on R04 and R14") is met, but the payoff it was cut for is not: on R04 an envelope search that proves its answer expands 78% to 98% of the walk with any bound built here, on R14 about 13% to 22% with the `+crafted+tags` bound. If #377 is built it should be built for the R14 kind of route (few near ties, a bound within 0.03%), after #497, and measured on R14 and R05/R13, not promised for R04. The decision is #498; it also asks to correct ADR-0063 point 3 and the #312 note, which say the cheap bound lacked the junk mod types: it lacked the crafted mods.

## Limits

- The cut tables are the classes reachable after the walk, on the exact quotient. They say what a bound could leave, not the walk time an envelope search would save; that needs the walk-free build.
- The upper bound of the cuts is the oracle `V*` or the incumbent "restart plus the optimal value", as in #312; a real incumbent (a given route, a cheap first solve) is worse.
- The exact value of R04 and S02 is the solve of the exact classes (the packed solver's figures, matched), of R14 of its unmerged graph (5,784.4887, the packed figure). Values move with `main`.
- One price set (`tests/fixtures/prices/routes-allflame-2026-10-31.json`; S02 at 1-chaos prices with the strand words removed, as the loaders read it).
- `+crafted+suffix-kinds`, `+crafted+kinds`, `slots` and `identity` were not built on R04 and S02 (80 M-edge limit); the R04 bound above 99.92% was not reached.
- R05, R08 and the other routes were not run on GitHub; R10, R11, R12, R13 were run locally and give 100% with `+crafted` (R13: 100.00%, 517 states).

## Runs (all through `heavy_dispatch.py`, branch `claude/376-junk-bound`)

Final: R04 42249928560, R14 42250013561 (`--long`), S02 42249968425. Earlier, with the same keys on earlier commits of the script: R04 42235457062, 42243739076, 42246496986 (the weights of the named junk families, the table of junk kinds); R14 42235505423, 42243783957; S02 42240695743. Failed or cancelled: R04 42233188283 (a kernel weight beyond the range of a float; weights are now divided as integers) and S02 42233232490 (cancelled for the same bug). Reproduce: `python .github/scripts/heavy_dispatch.py run --ref <branch> --runners 1 --command 'uv run --no-sync python research/376/junk_bound.py examples/targets/r04-penetrating-quiver.yaml --out $OUT_DIR --cut-keys 312-best,+crafted,+crafted+tags,+crafted+weight16'` (R14 with `--long --timeout-minutes 150` and `--seconds 6000`; S02 with the target `docs/research/2026-11-01-strand-routes-files/targets/s02-fire-res-ring-showcase.yaml --strand-stripped --merge yes`), then `python research/376/tables.py R04=... R14=... S02=...`.

## Open points, filed (OR-29)

- [#497](https://github.com/Rasslabsya4el/crafting-system/issues/497): build the crafted-pattern bound from the abstraction, without the walk.
- [#498](https://github.com/Rasslabsya4el/crafting-system/issues/498): decision on ADR-0063 point 3 and S4 (#377) after this research.
- [#499](https://github.com/Rasslabsya4el/crafting-system/issues/499): route-level pruning reports a certified gap `[LB, U]`.
