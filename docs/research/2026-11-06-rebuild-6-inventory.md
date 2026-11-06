# Fact base for rebuild step 6: route-level pruning, and the route in the player's words

Date: 2026-11-06. Read-only reading of `main` at `7c9e8df`; every `file:line` below is of that tree. This is the fact base for designing item 6 of the audit's "Rebuild proposal, per root" ([#396](https://github.com/Rasslabsya4el/crafting-system/issues/396), `docs/research/2026-11-02-codebase-audit.md`: "Minimal state and a route model"). It makes no decision and changes no code. Nothing was re-measured: every number is taken from a run, a note or an ADR named beside it.

Rules it measures against are in `docs/owner-rules.md`: OR-5 (a target never restricts the actions), OR-10 (detail no later decision reads is not tracked), OR-11 (exact, never an interval), OR-12 (no hard-coded cut-offs), OR-13 (a cut says what it still guarantees), OR-14 (cut across the whole route), OR-15 to OR-17 (page format, every step, the bought item), OR-18 (one page step is one player step), OR-19 (the same route is never shown twice), OR-20 (a fully known mechanic is never a range). The owner's decisions are on #396 (point 3: "a page like R14's must not exist; unrealistic and useless branches are cut across the whole route, under the same realism rules"; point 5: a display merge of states that take the same action is exact and needs no bound). Open points sit in [#405](https://github.com/Rasslabsya4el/crafting-system/issues/405) (actions), [#407](https://github.com/Rasslabsya4el/crafting-system/issues/407) (search), [#408](https://github.com/Rasslabsya4el/crafting-system/issues/408) (page) and [#410](https://github.com/Rasslabsya4el/crafting-system/issues/410) (point 3: non-exact merges before solving are "not needed now").

## 0. How to read the numbers

Three different things are all called "states" in the sources. Each number below says which.

- **item state**: a `CompressedState` (`src/crafting_system/abstraction/_state.py:161`), what the walk makes.
- **class**: the exact merge of item states that have the same future under every action (`solver/_packed_merge.py:151`, `exact_classes`). Used inside the solve and then dropped.
- **block**: the exact lumping of the optimal policy's chain (`solver/_packed_lump.py:190`, `lump_policy`): states that pay the same and lead to the same blocks with the same chances. It is what a big policy is shown by.

Sources of the measured numbers:

| Code | Source |
|---|---|
| M1 | Run 41490953015, `measure/full`, 2026-11-02, commit `de80240` (before the PR of #70 reached `main`, so the policy of a packed plan was still the class policy and a given route was still read on item states). Artifact `measure-report` (bloat, routes). Posted on the diary issue [#398](https://github.com/Rasslabsya4el/crafting-system/issues/398). R04 is missing there (no artifact). |
| M2 | Run 41589844469, heavy run on `claude/399-measure`, 2026-11-03, commit `961cc76` (after #70): `state_bloat.py` and `measure_routes.py` for R04 alone. Artifacts `run-ubuntu-latest-1`, `-2` (downloaded to the scratch folder, not committed). |
| M3 | Note of [#312](https://github.com/Rasslabsya4el/crafting-system/issues/312), `docs/research/2026-11-01-exact-merging-and-cuts.md` (research walker with all twin-merged offers; runs listed there). |
| M4 | ADR-0063 and its two updates (#374, #70), numbers from production runs on GitHub runners. |
| M5 | The audit, `docs/research/2026-11-02-codebase-audit/*.md`, taken on `main` at `86aa0b0` (2026-11-02, 09:36 +01:00, before the lumped view of #70). |
| M6 | Owner-side summary comment on #396 ("Measurement week results", [#399](https://github.com/Rasslabsya4el/crafting-system/issues/399)). |

## 1. The walk

### 1.1 Where states are made and expanded (14 places)

1. **The start item becomes the start state.** `make_plan` builds the `Abstraction` (`cli/_plan.py:354-363`) and `abstraction.compress(target.start_item)` (`_plan.py:364`; `abstraction/_kernel.py:434`). The `enabled` list it gets (`_plan.py:346`) decides what a state keeps: if any offered action reads the junk mods (`Reads.junk`) the state keeps every non-fractured mod as a slot (`abstraction/_kinds.py:166`, `Kinds.tracked`); if one is an addition (`Reads.adding`: Augmentation, Regal, Exalted: `actions/magic.py:175,214`, `actions/exalted.py:62`, `actions/contract.py:256`) the junk slot's kind is its numbered family type `~n`.
2. **What a state holds.** `CompressedState` = flags, fractured mods, the status of each goal leaf, slots (side, kind, contribution, crafted), and optional implicits, quality, unveil offer, imprints (`abstraction/_state.py:161-196`; `Slot` at `:58`).
3. **The goal is the only terminal.** `Abstraction.is_goal` (`_kernel.py:543`); a goal state gets no actions in either walk (`cli/_packed.py:102`, `solver/_graph.py:197-200`).
4. **Which offers a state gets.** `keyed_offers` (`cli/_prune.py:58-93`), called by the packed walk (`_packed.py:103`) and, through `solver_actions` (`_prune.py:96`) and `_Model.actions` (`_plan.py:181`), by the object walk.
5. **The successors of one offer at one state.** `Abstraction.kernel` (`_kernel.py:587`) goes to `_mixture_kernel` (`:1337`), which makes the new `CompressedState` objects in `_add_fixed` (`:1484`, state built at `:1498`), `_add_drawn` (`:1500`, built at `:1521`: the drawn junk slot joins the state here), `_add_fractured` (`:1526`), `_add_rerolled` (`:1899`); imprints in `_imprint_kernel` (`:610`).
6. **The production walk of a big graph (packed).** `walk` (`cli/_packed.py:66-146`): a list `states` as the breadth-first queue, a dict `index`, `intern` (`:91`), the loop at `:99-131`. One kernel is stored per `Abstraction.kernel_key` and shared by all (state, offer) pairs with that key (`:110-127`); the first 20 and then one in 4,096 shared kernels are checked against a fresh one (`VERIFY_FIRST`, `VERIFY_EVERY`, `:51-52`, `:113-120`). The abstraction's per-state cache is cleared after each state (`:130`).
7. **The object walk.** `build_graph` (`solver/_graph.py:162-273`): queue loop at `:191`, `model.actions(state)` at `:202`, successors interned at `:214-219`. `_Model.prefetch` (`_plan.py:159`) primes label distributions of the next 4,096 queued states in a process pool (`_graph.py:22,188-194`; `Abstraction.prime`, `_kernel.py:636`, `abstraction/_prime.py:35`); the graph is the same.
8. **Small graphs are walked twice.** `packed_result` (`_packed.py:301-323`) walks packed first; a graph of at most `OBJECT_SOLVER_EDGES` = 2,000,000 transitions (`:47`) returns `None` and `make_plan` solves it again with the object walk (`_plan.py:405-406`).
9. **Bound pruning walks again, up to 8 rounds.** `solve_pruned` / `_run` (`cli/_bound_prune.py:215-414`) solves the model on a small set of offers, tests the rest, adds some, solves again (`rounds=8`, `:221`; each solve is an object walk through `_Model`, with one shared action cache, `:280-283`). Only for 40 or more priced offers and only when the solver is not forced to "packed" (`_plan.py:43,398-403`).
10. **The forecast walks too.** `Abstraction.estimate` (`_kernel.py:775`; `abstraction/_estimate.py`, `_Pilot` at `:144`) walks the states without building kernels where a closed form exists, and with real kernels for additions and Annulment (`_estimate.py:118-133`). It only counts.
11. **Approximate levels.** A coarse state (`abstraction/_coarse.py:101`, `Coarsening`) and the tail cut (`solver/_tail.py:90`, expands exactly only the states above a visit threshold). Used only when the forecast does not fit the budget (`cli/_decide.py:168-202`, ladder at `:73-80`).
12. **Lazy donors.** `solve_lazily` (`solver/_lazy.py`) builds states with consumed inputs on demand. The planner never reaches it: `make_plan` passes `allow_inputs=False` (`_plan.py:362`).
13. **A given route is read by a second walk.** `evaluate_route` (`cli/_route.py:471-500`, breadth first over the states the route's rules reach, on item states); for a packed plan `_route_packed.py:92-129` reads the route on the already walked graph instead.
14. **The states the policy reaches.** `PackedPolicy.__init__` (`_packed.py:155-177`) uses `policy_reach` (`solver/_packed_solve.py:488`); the object side uses `policy_states` (`cli/_reach.py:18`). Everything shown to the player starts from this set.

### 1.2 What is pruned today (20 items)

"Exact" means the optimal value is unchanged by the cut (the argument is in the ADR or the module text named). Items 1 to 6 act before the walk, 7 to 12 inside it, 13 to 15 after it, 16 to 19 are the approximate path and the start options, 20 is what does not exist.

| # | What is cut | How | Where | Exact? | Shown to the player how |
|---|---|---|---|---|---|
| 1 | Kinds the target does not name | The target's `actions:` key lists the allowed kinds; others are skipped (7 targets carry it: J01, R04, R08, R09, R13, R14, V01) | `cli/_offers.py:218-224,243,289-302`; targets `j01...:23`, `r04...:45`, `r08...:55`, `r09...:48`, `r13...:29`, `r14...:39`, `v01...:44` | No (a restriction, OR-5) | A "Not offered" line only when the key exists (`_report.py:325`, JSON `left_out_actions` `:529`); the route page shows nothing |
| 2 | Opt-in kinds when the key is absent | `catalog(..., names=None)` leaves out the 17 `opt_in=True` kinds (Exalted Orb, Annulment, Fracturing Orb, the veiled orbs, Harvest add/remove ...) | `actions/catalog.py:138` | No | Nothing (#405) |
| 3 | Kinds closed for graph size | `planner=False` with `why_not` "pruning (#118)": `alchemy-orb` (`actions/alchemy.py:71`), `scouring-orb` (`actions/scour.py:133`), `harvest-reforge-likelihood` (`actions/harvest_likelihood.py:107`); the full list of 28 `planner=False` kinds is `tests/golden/reachability.md` | | No | `tests/golden/reachability.md` only |
| 4 | Crafts that count for nothing, rolls, corruption, "wanted only" | Filters over `Adds` | `_offers.py:250-275` (crafts at `:261-273`; exact only while every other offered kind erases crafted mods, else the plan is "cheapest among the offered crafts", `:303-311`) | Mostly | `left_out` lines (`_offers.py:303-328`) |
| 5 | Actions that need a crafted mod nobody makes | `usable_actions` | `_offers.py:395-399`, applied at `_offers.py:275` and `_plan.py:338-339` | Yes | Nothing |
| 6 | Offers with no price | `price_offers` drops them | `_offers.py:94-134`; `Plan.dropped` | No (PLANNING-4) | "Dropped for lack of a price" lines (`_report.py:315-324`); not on the page |
| 7 | Restart at the start state | Skipped | `_prune.py:75-76` | Yes | |
| 8 | Offers the game refuses at a state | `ActionError` from `kernel_key` skips the offer there | `_prune.py:84-87`; `_packed.py:124-125` | Yes | |
| 9 | Corrupting offers where the goal cannot use them | `corrupting_offer_pruned` (ADR-0036) | `_prune.py:77-78,137-147` | Yes (ADR-0031) | |
| 10 | Quality-only offers where they cannot help | `Abstraction.quality_offer_pruned` | `_prune.py:79-80`; `_kernel.py:574-585` | Yes | |
| 11 | Offers whose kernel at the state equals a cheaper offer's | Keep the cheapest per `kernel_key` (not for the options of a Lock) | `_prune.py:89-93`; `_kernel.py:646-697`; ADR-0031 and its amendment | Yes | |
| 12 | Goal states and "repeat forever" actions | A goal is not expanded; an action that can only loop at positive cost is dropped | `_packed.py:102`; `_graph.py:197-200,221-224` | Yes | |
| 13 | Twins (offers with equal `twin_key`, e.g. fossil sets) | Keep the cheapest | `_bound_prune.py:185-212`; used at `_plan.py:375,404` and `_bound_prune.py:277` | Yes (ADR-0031) | `left_out` "same outcome as a cheaper offer" (`_plan.py:540`) |
| 14 | Offers proved never better (certificate) | `reach_bound` (`abstraction/_bound.py:286`) gives a lower bound `rho`; solve on a few offers, test the rest, add, repeat; fall back to the whole model when the argument does not apply | `_bound_prune.py:248-414` (fixed numbers: `SMALL_START` 8, `PER_ROUND` 16, `rounds` 8, `MIN_OFFERS_TO_PRUNE` 40, `_plan.py:43`); object solver only (ADR-0063, update #374: "not routed to the packed solve") | Yes, with fall-back | `left_out` "proved never better" (`_plan.py:543-546`) |
| 15 | States merged after the walk | Exact partition refinement inside the solve; then `lump_policy` of the optimal chain | `_packed_solve.py:434-435`; `_packed.py:258-263` | Yes (lumpability) | The classes are dropped; blocks reach the player only when the policy visits more than 1,000 item states (`_plan.py:39,113-125`) |
| 16 | Coarse state pooled by junk family groups ("family groups of 8 / 4 / all in one") | Optimistic and pessimistic model around one policy | `_decide.py:73-80`; `_approx.py`; ADR-0023 | No (an interval, OR-11) | "approximate" marking (`_marking.py`) |
| 17 | Tail cut at theta 1e-2, 1e-3, 1e-4 | Follow a coarse policy, expand only states entered above theta | `_decide.py:77-79`; `solver/_tail.py` | No (an interval) | same |
| 18 | The choice between approximate and exact | 60 s budget, 1% tolerance, 2,000,000 transitions | `_decide.py:47-49,176-202` | No (OR-11, OR-12; #407) | `Plan.note` |
| 19 | Start options | A candidate whose price is not below the best total is not planned; refusals "no target mod", "cap below asked", "item level too low", "roll not guaranteed", "mod cannot spawn", "no price", "dominated" | `_starts.py:138-139`; `_start_types.py:23-30` | Yes for the price rule (ADR-0059) | `plan.starts` in the report |
| 20 | **Not present anywhere** | A cut of a state by its cost bound; a cut by the chance of reaching it; a walk guided by a route or an incumbent; a liveness rule for junk no later action reads (STATE-4, STATE-6) | | | |

Fixed numbers that act as limits on the answer rather than on the speed of a proof: items 1, 2 (the target's choice), 16 to 18 (60 s, 1%, theta), and in the model `DEFAULT_MAX_IMPRINTS = 1` (`actions/imprint.py:65`). `RISK_QUANTILE_TRANSITIONS = 2,000,000` (`_plan.py:441`) cuts the quantiles of a big chain, not the walk.

### 1.3 What decides when the walk stops (8 rules)

1. **Only an empty queue.** The packed loop is `while i < len(states)` (`_packed.py:100`), the object loop the same (`_graph.py:191`). Every non-goal state is expanded with every offer item 7 to 11 above leave it.
2. **There is no time, memory or count limit in the exact walk.** Searched `cli/_packed.py`, `solver/_packed*.py`, `solver/_graph.py`, `cli/_plan.py` for timeout, deadline, memory limit: nothing. `REPORT_EVERY = 30` seconds (`_packed.py:50`) only prints a progress line. A runner that runs out of memory simply dies (the object solver died at 15.7 GB on R04, ADR-0063 "What the measurements say about each part"; the first research run on S02 died after the walk when the production solver was asked to solve the whole graph, M3).
3. **The forecast can keep the walk from starting.** `decide` (`_decide.py:248-291`) counts with the pilot (state limit `DEFAULT_LIMIT` = 400,000, `ADDING_LIMIT` = 20,000 when real kernels are called, `abstraction/_estimate.py:49-50`) and `choose` (`_decide.py:168-202`) returns exact, approximate or refused. `make_plan` turns "refused" into the packed solver when no approximate level exists (`_plan.py:379-384`; R04 and R14 have an Attack/Caster metamod, so no level).
4. **A refusal by the game is local.** `ActionError` skips one action at one state (`_prune.py:84-87`, `_packed.py:124-125`); `OutOfScopeError` or `ValueError` from a kernel ends the whole plan and `_main.py:171-173` prints it as an error.
5. **After the walk, size picks the solver, not the walk.** At most 2,000,000 transitions go to the object solver (`_packed.py:321-322`); the packed solve refuses its own result if the certified bound exceeds `ACCEPT_BOUND` = 1e-6 (`_packed_solve.py:41,453-458`).
6. **Bound pruning stops after 8 rounds** and falls back to the whole model (`_bound_prune.py:414`).
7. **The approximate path has a time allowance:** `LEVEL_ALLOWANCE` = ten budgets (`_approx.py:77,293-298`, `LevelTimeout`). It is the only time limit on a solve (the forecast has its own, `PILOT_SHARE`, `_decide.py:51,262`).
8. **A stop-and-say-so safety net does not exist.** "A binding time or memory limit makes the plan say 'not exact, stopped at ...'" is the Done-when of [#378](https://github.com/Rasslabsya4el/crafting-system/issues/378), open.

### 1.4 Measured numbers

**Table 1. Walked, used by the best policy, used by the guide route** (10 routes). Units in the cells; codes are the sources of section 0.

| Route | Walked (item states) | Best policy: item states / classes / blocks | Guide route | Time and memory |
|---|---|---|---|---|
| R04 | 177,242 (M2, M4) | 18,696 item states (M4, update #70); 11,767 classes (M3); 551 blocks (M2) | **22 blocks**, 13 gaps (M2: `route_states` is the length of the lumped view; the raw count was not measured) | 425 s, 3.4 GB (M2 routes step); 461 to 650 s, 5.9 GB (M4) |
| R14 | 816,153 (M1) | 87,251 item states (M4); **65,147 classes** (M1 `policy_states`); 14,742 blocks (M1) | **946 item states**, 19 blocks, 1 gap (M1, object evaluation of the route) | 2,305 s, 8.3 GB (M1) |
| R05 | 761 (M1); 1,185 with all twin offers (M3) | 29 item states, 3 blocks (M1); 10 classes (M3) | 29 item states, 1 block (M1) | 33 s, 1.1 GB |
| R10 | 425 (M1, M3) | 17 item states, 2 blocks (M1); 3 classes (M3) | 17, 2 | 23 s, 273 MB |
| R12 | 23 (M1); 33 on `86aa0b0` (M5) | 7 item states, 1 block | 7, 1 | 1.5 s |
| R11 | 18 (M1, M3) | 9 item states, 1 block | 9, 1 | 0.9 s |
| R13 | 4,066 (M1, M3) | 191 item states, 7 blocks; 79 classes (M3) | 191, 5 | 24 s |
| R08 | 87 (M1, M3) | 46 item states, 2 blocks | 46, 2 | 107 s |
| R09 | 87 (M1) | 46 item states, 2 blocks | 29, 2 | 65 s |
| V01 | 786 (M5, and `states_solved` in `tests/golden/v01_minion_helmet.json`) | 88 item states (the golden JSON: 1 Augmentation, 8 Regal Orb, 79 restart; 3 distinct actions); 91 after the exact merge of dead ends (M5, STATE-4); 248 states in 30 classes (M5, SOLVER-2) | none (no guide writes a route for a recipe-made start) | 2.8 s |

Notes on Table 1 that the design must not skip:

- **The three figures on R14 and R04 in the owner's comment on #396 are not in one unit.** R14's "65,147" is the policy's classes (M1 ran before #70, when a packed plan's risk policy was the class policy, `git show de80240:src/crafting_system/cli/_packed.py`, `class_policy` at line 201); R14's "946" is item states of the guide route read the old way; R04's "22" is blocks of the guide route read the new way (`_route_packed.py:163-167`, `lumped_view`). The raw item states of R04's optimal policy are 18,696 (M4) and of R14's 87,251 (M4); the raw item states of the guide route on R04 are not measured. As ratios: R14 policy 10.7% of walked item states, R04 10.5%, R05 3.8%, R10 4.0%, R13 4.7%, R12 30%, R11 50%, R08 and R09 53%.
- The walked count depends on the offers: R05 is 761 on the production offers of M1 and 1,185 with every twin offer in M3; R12 was 33 on `86aa0b0` and is 23 in M1.
- Removing `actions:` from a target (OR-5) multiplies the offers and so the walk, and no measurement of that exists: R04's header says "a quiver takes about fifty [essences] and the plan with all of them is far beyond what a graph can hold" (`examples/targets/r04-penetrating-quiver.yaml:41-43`), R13's says a belt with the Chaos Orb has "more than 43,000 [states] after four minutes" (`r13-life-resist-belt.yaml:24-28`).
- Means are not in doubt: the simulation on concrete items agrees on all 10 routes, largest |z| = 2.01 (run 41591954486, M6).

**Table 2. Other routes measured by the research walker (M3).**

| Route | Item states | Exact classes | Edges before to after |
|---|---|---|---|
| R08 with the Alchemy (128 offers) | 87 | 5 | 326,456 to 1,071 |
| S13 (strand words removed) | 4,066 | 13 | 38,285 to 87 |
| S11 | 4,066 | 13 | not solved |
| S02 | 106,002 | 20 | 76.6 G to 94 |

(R04 merges 177,242 to 89,778 classes, 2.0x, edges 535.9 M to 171.2 M; R14 816,153 to 589,930, 1.4x.)

**Table 3. What projecting one part of the state away does (M1 for R14 and the small routes, M2 for R04).** Merged states are grouped; a group "changes the decision" when its members' optimal values differ (relative difference over 1e-9) or their optimal first actions differ. The cells give the groups with a different value / with a different first action.

| Route | Walked | Part dropped | States left | Groups with a different value / first action |
|---|---|---|---|---|
| R14 | 816,153 | flags | 815,809 | 343 / 331 |
| | | slots | 64 | 37 / 37 |
| | | fractured, status, implicits, quality, offer, imprints, junk names | 816,153 (no merge) | 0 / 0 |
| R04 | 177,242 | flags | 177,241 | 0 / 0 |
| | | fractured | 83,727 | 17,408 / 17,408 |
| | | slots | 966 | 105 / 103 (largest value difference 25%) |
| | | status, implicits, quality, offer, imprints, junk names | 177,242 (no merge) | 0 / 0 |
| R10 | 425 | junk names | 132 | 2 / 2 |
| | | slots | 12 | 1 / 1 |
| R05 | 761 | junk names | 557 | 0 / 0 (largest difference 2.2e-14) |
| R13 | 4,066 | flags | 3,949 | 117 / 117 |
| | | slots | 240 | 7 / 7 |

Reading (M6 and M3, stated there): the bloat is in the walk, not in the state; no single part of the state can be dropped on R04 or R14 without changing a decision; the exact partition merges only 2.0x and 1.4x there but 51x on R13, 118x on R05, 142x on R10, 313x on S13 and 5,300x on S02. The optimal policy touches about a tenth of the walked item states on the two big routes, and "the actions within 0.1% of optimal already reach 78% of R04's states and 74% of R14's" (M3, table "The envelope"): near ties are everywhere (95% of R04's unchosen actions are within 1% of the best), so an exact cut cannot remove them.

## 2. From policy to page

### 2.1 Where an internal distinction becomes a separate step or line (26 places)

Page (14, `cli/_route_view.py` unless named):

1. **One step per exact chance vector.** `_route_flow.py:207-211` starts the partition at `("action", label, cost)`, `:219-230` refines until every state of a block has the same exact `Fraction` chance into every block. One action with eight different Regal chances is eight steps. V01: the golden page has 11 rows (`tests/golden/v01_minion_helmet.html`, anchors `s1` to `s11`) for 3 actions; 8 of them are "Regal Orb" with chances 0.8857% and up (`tests/golden/v01_minion_helmet.txt:408,453`). Pinned by `tests/test_cli_route_flow.py:73,87,307,330` (and ADR-0015 line 5). The cause upstream is items 1 and 5 of section 1.1: Regal reads the family type `~k` of the junk suffix an Augmentation drew, so the eight successors are eight states.
2. **A silent fall-back to one step per state.** `_route_flow.py:216-218`: when `passes x states` passes `REFINE_WORK` = 250,000 every state is its own step, with no mark on the page.
3. **A cap on how much of the page is explained.** Above `MAX_STEPS` = 1,500 steps (`_route_flow.py:50,274-275`) uses and step costs are dropped, and an edge is "forward" by edges-to-goal; the goal card says "how often a step is used and what it costs are left out: the policy is too large to solve here" (`_route_view.py:537,556`).
4. **One row per step.** `build_section` (`:561-577`) and `step_row` (`:476-511`); row number = step number + 1.
5. **One "Chance per use" line per forward edge.** `chance_lines` (`:333-350`); an edge is a target step, so a split target (item 1) is a split line; when no leaf or mod differs the text is "the item of step N" (`:349`).
6. **One "On failure" line per failing edge.** `failure_lines` (`:352-367`), text "the item of step N" at `:366`. Forward or miss is decided by the expected cost to finish at the target against the use (`_route_flow.py:173-179,233-306`), not by what happened to the item; a cost-to-go is thus labelled "On failure" (PRES-6).
7. **"Goal" and "appeared" read the difference of the states.** `gains` (`:266-301`) and `appeared` (`:315-329`) compare the compressed states on either side; a crafted slot is printed by its class representative's id (`:284-286`; `_route_card.py:461-463`), so a bench craft can show a different mod from the one crafted (PRES-2, #408).
8. **"Accepts" counts slots.** `accepts` (`:369-384`) prints "2, 3 or 4 mods" from the sizes of the landing states.
9. **The item card is the join of the states of a step.** `card_of_states` (`_route_card.py:561-593`), `_join_rows` (`:535-545`), "in some" (`:524-525`), the junk-count spread turned into "any mod or empty" rows (`:578-583`) (PRES-8).
10. **Family-type junk is printed as "any mod".** `_StateReader.read` (`_route_card.py:488-521`), `family` (`:465-486`).
11. **A block is shown by its first member.** `lumped_view` (`cli/_packed.py:266-282`: shown state = first member of the representative class); `Plan.view_policy` swaps the policy for it above `VIEW_FROM_STATES` = 1,000 item states (`_plan.py:39,113-125`) and `route_input` draws the view (`_route_view.py:148-150`).
12. **The goal card prints internal grid limits and sources.** "9 runs in 10: not resolved on the grid (#190)" (`:534`), one league and one fetch date for every price (`:555`, INPUTS-3), claim ids in "Approximate inputs" (`:540-545`).
13. **The planner's route and the guide's route are compared by words.** `_row_key`, `_same_steps`, `merge_sections` (`:594-674`): a row repeats only if title, fields and card are equal, so a one-number difference redraws it (PRES-18).
14. **The start rows.** `buy_row`, `vendor_row` (`:446-474`).

Text report (7, `cli/_report.py` unless named):

15. **One block of text per view state**, ids `S1..Sn` (`number_states` `:153-159`, `build_report` `:162-200`, `render_text` `:329-376`). V01: 88 of them, 79 are "restart".
16. **Junk is a count.** `describe_state` (`:104-134`): "other mods: 1 prefix, 2 suffixes".
17. **The tree stops at `MAX_TREE_STATES` = 1,000** and `MAX_TREE_DEPTH` = 40 (`:42-43`, `:363-376`); the rest is "in the JSON policy".
18. **"States solved: N"** (`:327`) is the number of walked item states (`len(plan.solution.values)`): 786 on V01, 816,153 on R14.
19. **"Not offered, N actions"** and "Dropped for lack of a price" lines (`:315-326`): the only place the search's cuts appear, including the bound pruning's (`_plan.py:536-547`).
20. **The packed note** "The policy visits N item states; the tree below shows M groups" (`_plan.py:419-424`).
21. **The given route's gaps, one line each**, ids `R1..` (`cli/_route_report.py:15-60`).

JSON (5, `cli/_report.py` and `_route_report.py`):

22. **`states`**: one entry per view state (`_report.py:535-551`).
23. **`states_solved`** (`:533`): the walked count.
24. **`dropped_actions`, `left_out_actions`, `offered_actions`** (`:528-532`).
25. **`given_route`** (`_route_report.py:67-`), per-state ids.
26. **`single_draw_shares`** (`_report.py:552-562`): the guide's single-draw share next to the chance of one use.

### 2.2 What grouping exists today (9)

1. **Junk family types** in the state (`~n`, or `""` when no enabled action reads the pool): exact, ADR-0009; the cause of the eight Regal states.
2. **Shared kernels** per `kernel_key` in the packed walk (`_packed.py:110-127`): storage only.
3. **Exact classes** (`_packed_merge.py:151`): inside the solve; the page never sees them (SOLVER-2).
4. **Lumped blocks** of the policy chain (`_packed_lump.py:190`): reach the page only through `view_policy` above 1,000 item states. The seed of the partition is "goal or not, and the cost paid", not the action label (module text, `_packed_lump.py:1-25`); the shown action is the representative's.
5. **Flow steps** (`_route_flow.py:105-191`): the coarsest partition by (label, cost, exact chances into steps). On a view the steps are the blocks (a finer seed cannot merge what the block partition keeps apart).
6. **Item card join** per step (item 9 above).
7. **Given-route merge** (`merge_sections`, `_route_view.py:639-674`): "Same as the given route" when the rows match one for one (OR-19).
8. **Text and JSON**: no grouping; one entry per view state.
9. **Start options**: compared as whole plans (`_starts.py:96-170`), shown as a list in the goal card (`_route_view.py:513-523`).

### 2.3 Where a player sees one step with branches today (4)

1. A step whose states have the same action and the same chances into the same steps has one `Step` with several `Edge`s (`_route_flow.py:71-90,145-179`), drawn as one row with "Chance per use" lines and an "On failure" list: this is the one-step-with-branches form OR-18 asks for. What is missing is that steps with the same action and different chances (item 1 above) are never joined.
2. The branch lines name the target by the difference of the landing states (`appeared`, `lost`, `_route_view.py:303-329`) and fall back to "the item of step N" when nothing differs.
3. `Edge.states` keeps the landing states (`_route_flow.py:60-69`), so a branch can be given its own item; the page does not do it (the join of item 9 draws one card for all branches).
4. The forward or miss kind is by cost-to-go, not by what changed on the item (item 6).

### 2.4 What a page of a big policy is today (derived from the code, not measured)

The 87,272 steps (151 MB) of OR-14's counter-example and of audit ROUTES-15 were built on `86aa0b0`, from the unlumped policy. Since #70 `route_input` draws `Plan.view_policy` (`_route_view.py:148-150`), which for R14 and R04 is the lumped view: at most 14,743 (R14) and 552 (R04) item states. By the argument in section 2.2 item 5 the flow then has as many steps as blocks. That would be about 14.7 thousand rows for R14, with the flow unmeasured (above 1,500 steps, `_route_flow.py:274`) and possibly every state its own step (the refinement stops at `REFINE_WORK`, `:216-218`), and about 550 rows for R04. **No run in the artifacts built the page after #70 and counted it:** the heavy CLI test (`tests/test_cli_r04_r14_heavy.py`) calls `main`, which writes the page (`cli/_main.py:166-170`), but nothing in the file reads or counts it.

## 3. The routes we already hold

| | The given route (the guide's) | The completed route | The policy |
|---|---|---|---|
| What it is | An ordered list of rules `when` (rarity, corrupted, fractured families, crafted, open slots, status of a requirement) `do` (an offer label or `restart`); the first matching rule acts (`cli/_route.py:1-29`, `When` `:73-111`, `Rule` `:115`, `Route` `:124`) | The given route plus one last rule `do: restart` and `skip_refused: true`, written by hand for R04 and R14 only | The solver's action at each reached item state |
| Where it is written | 11 files `examples/routes/*.yaml` (R04, R05, R08, R09, R10, R11, R12, R13, R14, and the two completed ones); V01 has none (`BenchmarkRoute.route = None`, `cli/_benchmark.py:83-98`) | `examples/routes/r04-penetrating-quiver-restart.yaml`, `r14-hunter-bow-restart.yaml` (146 and 137 lines); named in `BenchmarkRoute.completed` (`_benchmark.py:199,238`) | `Plan.solution.policy`: a dict (object solver) or the lazy `PackedPolicy` (`_packed.py:155`); `Plan.view_policy` (`_plan.py:113`) |
| Where it is built | `load_route` / `parse_route` (`_route.py:164,178`); evaluated by `evaluate_route` (`:471`, item states, gaps, risk, first divergence) or `evaluate_route_packed` (`_route_packed.py:140-167`: the walked graph restricted to the route's actions, `restricted` `:132`, merged, lumped, risk on blocks) | Evaluated like any route (`_benchmark.py:400-404`); no code makes a completed route | `make_plan` (`_plan.py:255`); `packed_result` / `solve_walked` (`_packed.py:239-263`) |
| What it holds | For every state it reaches: an action or a gap with a reason; the risk of the route; the first state where it differs from the policy (one only) | A finite mean; the 4.3x and 2.3x gaps of #389 (M6) are against these | Action, expected cost to go, chances; no names for branches |
| Size (Table 1) | R14 946 item states, 19 blocks, 1 gap; R04 22 blocks, 13 gaps; R05 29, R10 17, R13 191, R12 7, R11 9, R08 46, R09 29 | not measured separately | 87,251 / 18,696 item states on the two big routes |
| What it leaves out | Steps the model cannot hold sit in file comments (R08/R09 Alchemy, R05 catalysts, R11 finishing craft: #408); no numbers of its own | The restart is the file's reading, not the guide's | |

Where route-level pruning could hook in (8 places; facts, not a choice):

1. **The offer filter at each walked state:** `keyed_offers` call (`_packed.py:103`) and `solver_actions` (`_prune.py:96`). A rule `When.matches(state, data)` (`_route.py:85`) can be asked for any walked state.
2. **The route lookup on the walked graph:** `_Reading.choose` and `.action` (`_route_packed.py:46-89`), including the twin-kernel fall-back when the walk kept a cheaper offer with the same `kernel_key`.
3. **The restricted graph:** `restricted` (`_route_packed.py:132-137`): the graph cut to one action per state; a "route and its sensible branches" graph would need a second action set per state.
4. **The single policy source of the display:** `Plan.view_policy` / `lumped_view` (`_plan.py:113`, `_packed.py:266`): report, JSON and page all read it.
5. **The step builder:** `build_flow(start, policy, is_goal, reasons, is_restart)` (`_route_flow.py:105`) takes any policy mapping; the guide's flow and the planner's flow are already the same type.
6. **The comparison of two routes:** `merge_sections` (`_route_view.py:639`), "only the steps that differ".
7. **An incumbent value inside the exact cut:** `_run` takes J from a solve on few offers and tests the rest against it (`_bound_prune.py:373-375`); the same role for a route's mean is the "executable upper bound" of ADR-0063 point 3 ([#377](https://github.com/Rasslabsya4el/crafting-system/issues/377)); the benchmark already evaluates the guide's and the completed route's means (`_benchmark.py:394-404`).
8. **The carrier of a cut and its reason:** `LeftOut(reason, labels)` (`_offers.py:145`), `Plan.left_out` (`_plan.py:97`), rendered at `_report.py:325` and JSON `:529`; not read by the page (#405).

## 4. Overlap with the map

The audit's step 5 ("An answer envelope") makes the answer carry its limits as data: kinds left out and why, unpriced items, model gaps, cuts with their guarantee, price provenance; and renders them on the page and in the report. Step 6 builds a minimal state, route-level pruning and the route model.

| Ticket | State today | What it builds | Overlaps step 6 | Overlaps step 5 |
|---|---|---|---|---|
| [#375](https://github.com/Rasslabsya4el/crafting-system/issues/375) S2 packed, parallel walk | open, not blocked | States and kernels as arrays, walk split over processes; Done when R14 is under 10 minutes and 4 GB on a 4-vCPU runner | Same loop (`cli/_packed.py:99-131`) and same types (`Walked`, `PackedPolicy`, which `_route_packed.py` and `view_policy` read). Any filter step 6 puts in the walk (section 3, hook 1) must be in the parallel walk too. ADR-0063 point 6: no merge inside the walk | None directly |
| [#376](https://github.com/Rasslabsya4el/crafting-system/issues/376) research: a lower bound that sees the junk types | open, blocks #377 | A bound at least half of the exact cost on R04 and R14, or a note that none exists | The exact form of route-level cutting (OR-12: branch and bound against an incumbent) is gated by it. Measured so far: luckiest path with 32 sweeps 0.64% (R04) and 13% (R14) of the exact cost; coarse optimistic models 97% on R13 but 0.5% to 4.1% on R04 and R14; a perfect bound would still need 13% of R04's and 11% of R14's classes (M3) | No |
| [#377](https://github.com/Rasslabsya4el/crafting-system/issues/377) S4 envelope search | open, blocked by #376 | iLAO*-style expansion from the start with the bound and an executable upper bound; per-state action elimination; stop when the root decision is proved; measured on R05, R13, R04, R14 | Direct: this is a route-level (state-level) cut by cost; it shrinks the walk and so the policy and page source. It does not shrink the optimal policy itself (18,696 and 87,251 item states) | It must report its cut and what it guarantees: that is #378 |
| [#378](https://github.com/Rasslabsya4el/crafting-system/issues/378) S5 report the cuts and the limits | open, not blocked | The report lists which cut kinds ran, the tolerance and what it guarantees, and the binding limits; no cut by a fixed count or chance; a binding time or memory limit gives "not exact, stopped at ..." | Only as the consumer: every route-level cut step 6 adds must register here | Direct: this is step 5's "cuts with their guarantee" and the stop-and-say-so net of OR-12 (section 1.3, rule 8); also carries `left_out` (#405) |
| [#379](https://github.com/Rasslabsya4el/crafting-system/issues/379) research (optional): an exact key in the walk | open | A key from `Reads`/`Adds` equal to the exact partition on S02, R13, R05, or a note | Direct for the first bullet of step 6 (merge exactly what no later decision distinguishes): same question at state level. Measured: exact partition 2.0x (R04), 1.4x (R14), up to 5,300x (S02); none of nine simple projections is both exact and merging (M3, ADR-0063 point 6). #396 comment: route-level pruning comes before this | No |
| [#353](https://github.com/Rasslabsya4el/crafting-system/issues/353) Buying V1-3 realism rails and the cut report | open, blocked by #351, blocks #359; **not built**: `listing_count_min` and `max_wanted_mods` appear nowhere in `src` | Two settings (10 listings, 1 wanted mod) applied to every bought-start option; the plan report lists each option left out with the rail and its value | The cut is on the roots of the route (which start items are planned), in the seam of `plan_with_starts` (`_starts.py:48,96-170`, `SOURCES`). Fixed rails as cut-offs are what #407 lists against OR-12 (ADR-0061 decisions 4 and 5) unless they are only a stop-and-say-so net | Direct: "each option left out with the rail that cut it" is the cut report of step 5, on top of `ConsideredStart` / `RefusedStart` (`_start_types.py:71-104`) |

## 5. Design options for step 6 (no decision)

Counts are of files that name the thing today (grep on `7c9e8df`), so they are an upper bound of what a change must read, not of what it must edit. "Rules" are those the option serves.

| Option | What it is | Source files touched | Test files touched | Rules served | What it does not do |
|---|---|---|---|---|---|
| A. A page-only route model | After the solve, build the page from player actions: join steps with the same action (the exact mixture of their chances, OR-20), draw branches inside one step, and give each branch its own item; walk and solve unchanged | 3 to 5: `_route_flow.py`, `_route_view.py`, `_route_card.py`, optionally `_route_html.py`, `_report.py` | `test_cli_route_flow.py` (34 tests, 4 pin the grouping by chance), `test_cli_route_view.py` (49), `test_cli_routes_real.py` (12); 9 test files name the page API (those three among them), plus `tests/route_view_support.py`; 16 `.html` and the V01 `.txt`/`.json` goldens | OR-18, OR-20, OR-19, OR-15 to OR-17, OR-14 (page size) | Nothing about the walk: R14 still walks 816,153 item states; OR-10, OR-12 untouched |
| B. One lumped policy for every plan | Make `lump_policy` the source of report, JSON and page for object-solved plans too (today only packed plans above 1,000 item states) | 6 to 8: `_plan.py`, `_packed.py`, `_report.py`, `_route_view.py`, `_route_packed.py`, `solver/_packed_lump.py`, plus either routing small plans through the packed path or an object-side lump | `test_packed_walk_light.py` (36), `test_solver_packed_lump.py` (9), `test_packed_plan_real.py` (9), `test_risk_r04_r14_chains.py`, 23 files that name the report API; the 27 files of `tests/golden` | OR-10 (exact), OR-14, partly OR-18 and OR-20 | A block is still drawn as its first member (PRES-2, PRES-8); the walk is unchanged |
| C. Exact branch and bound with an incumbent | Expand states from the start with a lower bound and the guide's or a first solve's mean as the upper bound; per-state action elimination; stop when the root decision is proved (#376, #377) | 5 to 7: `_packed.py`, `_bound_prune.py`, `abstraction/_bound.py`, a new bound module, `_plan.py`, solver files | `test_prune_bound.py` (29), `test_prune_equal.py` (14), 8 test files import the packed modules; heavy runs only (`CRAFTING_HEAVY`: 3 files) | OR-12, OR-14, OR-11 (exact), OR-5 (every kind offered, pruning decides); needs #378 for OR-13 | Gated: Done-when of #376 is a bound of at least half the exact cost; the cheap bounds measured give 0.5% to 4.1% on R04 and R14 and cut nothing (M3). It does not shrink the optimal policy |
| D. A cut with a derived tolerance and a stated guarantee | ADR-0063 point 4: lump an outcome only when `p x (UB - LB)` is below the margin the bounds leave the choice; report `V_opt <= V* <= V_pess` | 4 to 6: `solver/_packed*.py`, `_bound_prune.py`, report files | New tests only for the cut; the report goldens | OR-12 (tolerance from whether it could change the best route), OR-13 | Reads as an interval, which OR-11 calls useless unless the bracket is zero; #410 point 3 says non-exact merges are "not needed now". Measured: every state settled on R05 and R10, none on R04 (M3) |
| E. A guide-guided walk | Treat the guide's route (and the completed one) as the frame: offer at each state the route's action and a defined set of neighbours, and take the guide's mean as the incumbent | 5 to 6: `_packed.py`, `_route.py`, `_route_packed.py`, `_plan.py`, `_main.py`, `_benchmark.py` | `test_cli_route.py`, `test_cli_route_flow.py`, `test_packed_walk_light.py`, `test_cli_r04_r14_real.py`, `test_cli_r04_r14_heavy.py`, benchmark tests | OR-14 ("keep only what the given route and its sensible branches need") | Needs a route for every target (V01 has none; OR-27: agents write them); the restriction comes from a route, not from the target, but the answer is then the cheapest near the guide, not exact among realistic routes (OR-11) unless a bound proves it, and OR-13 needs the statement. Defining "sensible branch" is open |
| F. A reach threshold on the page | Fold or drop branches whose chance of being reached is below a value; `Step.reached` is already computed (`_route_flow.py:297`) | 3: `_route_flow.py`, `_route_view.py`, `_report.py` | the same route-flow and route-view tests as A | OR-14 (page size) | A fixed value is a hard-coded cut-off (OR-12's counter-example) unless it is derived from a bound; `reached` exists only when the flow is measured (at most 1,500 steps), which R14's page is not (section 2.4) |
| G. A minimal state | Exact merge in the walk for the known cases (dead ends that differ only in junk, status that the next reroll erases: V01 786 to 91; R10 425 to 2) or from `Reads`/`Adds` (#379) | 4 to 6 around `abstraction/_kernel.py` (1,932 lines), `_state.py`, `_kinds.py`, `_estimate.py`, `_coarse.py` | 13 files name `CompressedState`, 79 name `Abstraction`, 8 name `kernel_key`; all goldens that print state counts | OR-10 | Measured to merge R04 only 2.0x and R14 1.4x even for the full exact partition, and no single part of the state can be dropped there without changing a decision (Table 3); #396 comment puts it after route-level pruning |
| H. The policy as rules in the guide's own language | Summarise the policy as an ordered list of `when` / `do` rules over rarity, fractured, crafted, open slots and requirement status (the language of `cli/_route.py`), so the planner's route and the guide's route are the same type and `merge_sections` compares like with like | a new module in `cli/`, reuse of `_route.py`, `_route_view.py`, `_route_flow.py` | new tests; the route-flow and route-view tests as A | OR-18, OR-19, OR-16 (rules name every action) | Whether a rule list can name all of a big policy's states exactly is not known; a state the rules cannot tell apart would need the exact lumping (option B) beneath it |

Which options sit on which side of the audit's own order: A, F, H act after the solve and are step 6's second bullet (the route model); B is between; C, D, E act inside the walk and are the first bullet (route-level pruning, with G the state-level minimal state). C and D need the cut report of #378 (step 5) before they can state their guarantee. A, B and H are exact by construction and need no bound (#396 point 5).

## 6. Facts not established, and findings of this reading (8)

1. **R14's page after #70 has not been counted** (section 2.4). OR-14's counter-example (87,272 steps) and ROUTES-15 describe the code of `86aa0b0`; the derived size from today's code is about 14.7 thousand rows, not 87 thousand. A measurement is one heavy run of the CLI on R14 and a count of the rows.
2. **Unlike units in one comment** (Table 1 notes): R14 65,147 (classes) beside 946 (item states), R04 22 (blocks).
3. **R04's guide route in item states is not measured**; only the 22 blocks are.
4. **V01 is not in the bloat step** (its table has R12 to R14 without V01), so its projections are not measured; its numbers are the audit's (`86aa0b0`).
5. **The effect of removing `actions:` (OR-5) on the walk is not measured** for any route; it is the reason route-level pruning must exist before #405 can be closed.
6. **#353 is unbuilt**, so there is no code to read for the buying rails; only its text and ADR-0061 decisions 4 and 5.
7. **No test reads a big route's page.** The only test of the page for R04 and R14 is the call to `main` in the heavy test.
8. **Two findings of this reading are not filed as issues**: item 1 (the stale counter-example in `docs/owner-rules.md` OR-14 and OR-18 against the post-#70 code) and item 2 (unlike units). Under OR-29 they are filed before this PR lands; the main chat decides whether to file them now.
