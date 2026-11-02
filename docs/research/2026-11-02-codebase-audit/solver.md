# Audit (ticket #396): SOLVING AND CHECKING

Area: `solver/`, `risk/`, `simulator/`, and in `cli/`: `_packed.py`, `_bound_prune.py`, `_approx.py`, `_lift.py`, `_verify.py`,
`_decide.py`, `_shares.py`, `_reach.py`, `_route_sim.py` (plus the glue they call: `_plan.py`, `_offers.py`, `_prune.py`, `_marking.py`
where a finding needed it). ADRs read: 0001, 0006, 0010, 0011, 0012, 0019, 0022, 0023, 0026, 0028, 0031, 0035, 0058, 0063.
Read-only. Scratch scripts live in `.claude/scratch/audit/solver_tmp/` (nothing outside `.claude/scratch/audit/` was changed).
Runs I made were small (R10 29 s, R12 2 s, R13 17 s, R11 1 s, V01 1 to 5 s, three 22-state toy amulets); R09 and two toy fracturing
targets were started and killed as too heavy.

## Short answers to the four questions of the assignment

1. **What is minimised.** The expected total currency cost of a stationary, state-aware policy: the start item's price once, plus the price of
   every action used, with a `restart` (buy the start item again, outcome = the start state, cost = start price) offered in every non-start
   state (`cli/_plan.py:325-328`, `_prune.py:84`). That is what the owner means, with three silent exceptions: no restart exists when the start
   price is 0 (SOLVER-7), actions the model cannot evaluate in a state are dropped as if the game refused them (SOLVER-8), and the default CLI
   may answer with an interval instead (SOLVER-3, SOLVER-4). "Success" is `Abstraction.is_goal`; it can only be as right as the tier/status
   reading it is given (the seeds), and the solver adds no wrong-success path of its own: dead ends get value infinity, the policy must be proper
   (`solver/_graph.py:proper_states`), the restart is always there to leave a bricked item. Free actions cost 1e-6 of the cheapest paid offer
   (`_offers.py:23,130`), documented, bounded, but a placeholder (SOLVER-11).
2. **Is `--verify` independent?** Not in meaning. It re-implements the sampling and the goal predicate, but it shares the action classes,
   the pools, the tier tables, the stored `ExplicitMod.tier`, the `Reads` declarations, the prices, the compression and the restart object with
   the planner. I reproduced the seed class: a bench craft used as "Life tier 1", plan and `--verify` agree (SOLVER-1). Full list of shared
   functions there.
3. **Cuts, merges, approximations.** Exact (proved, mostly reported): twin merge, equal-kernel merge, bound pruning, corrupting/quality pruning,
   exact lumping in the packed solve. Answer-changing and hard-coded: the 60 s / 1% / 2 M-transition decision, the coarse ladders, the tail-cut
   thetas (SOLVER-3, 4, 14). Quantile cuts change only what is certified (SOLVER-6, 14). The exact lumping is computed and thrown away
   before the page (SOLVER-2). Nothing at the solver level uses a probability threshold to drop outcomes (ADR-0063's rule holds there); `value_ceiling`
   (1e12) and the 2 M-transition risk limit are the closest.
4. **p50/p90/CVaR.** Certified intervals normally; "unresolved" (infinite) when the cheapest action is far below the cost scale and no coarse grid fits;
   not computed at all when the packed chain has more than 2,000,000 transitions (R04) or inputs sit in a cycle; the route page shows only the
   mean and p90, and for all the missing cases it says "not resolved on the grid (#190)" (SOLVER-6).

---

### SOLVER-1: `--verify` can only agree with the planner on what the game means   [CONFIRMED] [impact: high]
- Where: `cli/_verify.py:36-58` (`Memoized`), `:117-137` (`verify`), `cli/_lift.py:32-38`; `simulator/_simulate.py` (needs `is_goal`, `policy`, `start`
  from the caller); the pair "solver mean / risk mean" printed at `cli/_report.py:385-386`.
- What it does: draws every click with `action.outcomes(data, item).sample(rng)` and judges the goal with `target.is_met_by(item)`, so it is a
  separate implementation of the sampling and of the goal predicate. But everything that decides *meaning* is common with the planner. Shared
  functions and data on the planner path and the verification path:
  1. `actions.*` classes and their `outcomes` object: the kernel imports `Outcomes, Rerolled, Fixed, Fractured, build_pool, tiers_of,
     partners, allowed_by_tags` (`abstraction/_kernel.py:11-33`) and `items.tier_table, spawn_weight`; `Outcomes.distribution` (kernel) and
     `Outcomes.sample` (simulator) differ only in `draw.exact_distribution` vs `draw.sample_new_mods`. Pool weights, conflicts, tier tables,
     rule claims (`rules/`) are the same objects.
  2. The tier stored on each mod: `ExplicitMod.tier` is written by the actions (`bench.py:57,120,156` `CRAFTED_TIER = 1`, `beasts.py:59`,
     `outcomes.py:77` `tier_table(...).get(forced.id, 1)` for an essence mod) and read by `Target.is_met_by` ("the tier is the one stored on the
     ExplicitMod, never derived here", `targets/model.py:5`) and by the kernel (`_kernel.py:762`, and the defaults `tiers.get(mod.id, 1)` at
     `:909,924,1071,1088,1097,1104,1528`). A placeholder tier is therefore accepted identically on both sides.
  3. `Requirement.mod_ids` (resolved once by `targets/resolve.py`) is both the goal's `Wanted.mod_ids` and the simulator's membership test.
  4. `action.reads(data)`: `Memoized` skips its cache only when `reads.junk or reads.item_state` (`_verify.py:48-51`); the abstraction decides what it may
     forget from the same declaration. An under-declared `Reads` is wrong in both places the same way.
  5. `plan.offer_of(action)`: the same `PricedOffer` objects, so every price, the free-action epsilon and the restart price are the planner's.
  6. `abstraction.compress(item)` in the lift (`_lift.py:32`): the concrete item is mapped by the planner's own compression to find its action.
  7. `BuyStartItem.sample` returns `target.start_item` (`_offers.py:188`): the restart is the planner's object.
  8. `plan.start_price.chaos` and `plan.mean_remaining` / `plan.risk.p90` (`_verify.py:131-132`): the number checked against is the solver's own
     value, and the risk run's mean is a second solve of the same costs on the same chain (`risk/_moments.py:solve_costs` calls `solve`), so the
     report line "X Chaos by the solver and Y by the risk run" is two outputs of one computation, not a cross-check.
  What is genuinely independent: the sampler of mod draws (`sample_new_mods`) against the exact distribution; the goal predicate as code
  (`Target.is_met_by` vs `Goal`/`status_of`); the lift (a state the policy table lacks stops the run and `--verify` says so); the policy's support.
- What it should do: ADR-0019 layer 2/4 promise "an independent simulator written from the rules registry and not from the kernel code". It
  checks the compression and the solver; nothing in it can notice that a rule, a tier or a price is not the game's. The output line "AGREES
  with the computed mean" reads as a statement about the item, not about the compression.
- Evidence (ran): target `tg/amulet-life-t1.yaml` (Paua Amulet 84, rare start, `actions: [chaos-orb, bench-craft, remove-crafted-mods]`,
  requirement `IncreasedLife min_tier: 1`). `make_plan(start_price=1.0)`: 22 states, mean left 1.635 Chaos, policy = `Chaos Orb` x10 and
  `Bench craft +# to maximum Life [EinharMasterIncreasedLife2]` x3. `verify(runs=2000)`: `agrees True`, simulated 2.6705, computed 2.6350, 2000 of
  2000 successes. The finished item holds a crafted Life mod "tier 1". Also `verify` detects only errors above `SIGMAS * SE / mean`
  (`Verification.detectable_error`, about 5% at 10,000 runs); the text says so.
- Impact: every benchmark route's "verified" status; the seeds of #396 are the kind of fault `--verify` cannot see (I did not run `--verify` on R05 itself, but the
  amulet above has the same mechanism). The simulation is also slow on a real route (R11, 10,000 runs, did not finish in 300 s here).
- Origin: ADR-0019 (grill round 3, #4) and #25 (`a8ce149`, simulator), #26 (`2dcbe31`, `--verify`); the "independence" test
  (`tests/test_simulator_independence.py`) only forbids imports of `abstraction/solver/risk`.
- Pattern: independent in code, shared in meaning (the checker and the checked read one stored fact).

### SOLVER-2: exact equivalence classes are computed, then discarded; the policy shown is per raw state   [CONFIRMED] [impact: high]
- Where: `solver/_packed_merge.py:exact_classes/quotient` (used only inside `solve_packed`, `solver/_packed_solve.py:solve_packed`);
  `cli/_packed.py:PackedPolicy` (keys = concrete states) vs `class_policy` (classes, used only for `risk`); `cli/_plan.py:402-406`;
  the object solver (`solver/_solve.py`) never merges.
- What it does: the solver can prove, by partition refinement, which states have the same goal status and the same (cost, distribution over
  classes) pairs ("lumpability with costs", `_packed_merge.py:1-12`). The result is used to make the solve and the risk run smaller. The policy
  that reaches the report, the JSON and the route page is the unmerged one, one entry per `CompressedState`, and the object solver (all
  routes under 2 M transitions) has no merge at all.
- What it should do: owner rule "detail no later decision sees is not tracked at all (an Alchemy before a fossil is one state)" and "never show
  the same route twice". ADR-0063 point 1 folds the merge in "because it costs little", as a speed device; point 6 declines an exact key in the
  walk. Nothing says the displayed policy should be the quotient.
- Evidence (ran): `make_plan(v01-minion-helmet.yaml, solver="packed")` on the plain start: 787 states walked, 248 reached by the policy, **31
  classes**, the risk chain has 30 classes (`plan.packed.info["classes"]`, `len(plan.packed.risk_policy)`); `restart` is the action in 158 of the
  248 states. The object solver gives 778 policy states for the same plan. The page built on the runner
  (`.claude/scratch/audit/pages/run-ubuntu-latest-2/V01-...route.html`) has "3. Regal Orb" to "10. Regal Orb" (8 rows) for the chosen vendor start;
  it is the seed "V01 eight identical Regal Orb steps".
- Impact: every route page and text tree: the number of rows and the "tree" are inflated by states that differ only in detail no decision reads
  (V01: 248 to 30). Also hides how many distinct situations a route really has.
- Origin: #374 (`8bb50d9`, Solver S1), ADR-0063 point 1 and 6; state design ADR-0009 (compressed state), ADR-0027 (what the state keeps).
- Pattern: state or output detail that no decision reads; a correct tool built for speed and not used for meaning.

### SOLVER-3: exact vs approximate vs refused is decided by a wall-clock forecast, and the refusal text is stale   [CONFIRMED] [impact: high]
- Where: `cli/_decide.py:47-54,73-86,150-196,255-289`, `cli/_plan.py:344-362`, `cli/_main.py:90-91,112-118`.
- What it does: `python -m crafting_system.cli <target>` runs `decide` with `--budget 60` unless `--exact`. `decide` measures `r_kernel` in a pilot and
  `r_solve` with a calibration solve (`calibrate_solve_rate`, `time.perf_counter`), forecasts the seconds, and: exact if it fits 60 s; else a coarse
  level; else, when the exact graph is "more than 2,000,000 transitions", **refuses** with "The exact run is not offered ... the solver has been run
  on at most 2,000,000 (its memory is not measured beyond). Offer a smaller list of crafts and run again." (`exact_offer`, `_decide.py:139-153`).
- What it should do: owner rules "exact among realistic routes", "no hard-coded cut-offs", "approximate with an interval reads as useless"; ADR-0010
  "nothing tied to one machine"; ADR-0063 (update of #374): R04 (536 M transitions), R14 and S02 *are* solved exactly (461-1,187 s, 2.4-8.4 GB).
- Evidence (ran, pilot only, `decide` spied): R14 `r14-hunter-bow.yaml`, budget 60: `refused`, predicted 8.0 s at 152,036 transitions (count stopped,
  `complete=False`), message ends "The exact run is not offered: the count stopped at 152,036 transitions and the graph is larger (the solver has been
  run on at most 2,000,000). Offer a smaller list of crafts and run again." and contains "(#69, ADR-0023)". R04: `refused`, predicted 58.96 s, 1,858,323
  transitions. `exact_offer(535_900_000, 460.0, True)` returns the "not offered" sentence. Both run exactly with `--exact` (the message never
  says so for >2 M). Run-to-run the predicted seconds differ (8.00788 vs 8.00712 for R14): the decision depends on the machine's speed that day.
  R05, R10, R11, R12, R13, R08, R09 decide `exact` (26.8, 0.87, 0.07, 0.06, 1.9, 1.4, 0.9 s predicted).
- Impact: the default command on the two heaviest benchmark routes ends in an error that tells the owner something false; a route that is
  borderline (forecast near 60 s) is exact on a fast machine and an interval on a slow one.
- Origin: #127 (`a25e785`, "Approximate answers C"), ADR-0023 "How the CLI decides"; owner #81 Q2 (2026-10-31, "(b) exact if it fits about a minute, past that
  approximate within 1%"). Nobody revisited it when #374/#312 made exact big solves possible (`EXACT_TRANSITIONS` still 2,000,000).
- Pattern: a threshold fixed by one measurement and kept after the measurement changed; a decision by machine speed.

### SOLVER-4: an approximate answer is an interval with no page, no risk and no `--route`; its constants are hard-coded   [CONFIRMED] [impact: medium]
- Where: `cli/_decide.py:47-48,73-86` (`TOLERANCE = 0.01`, `BUDGET_SECONDS = 60`, `LADDER`: groups of 8 and 4, tail cuts theta 1e-2/1e-3/1e-4,
  `SPREAD_LADDER`: 1000 and 500 weight units), `cli/_approx.py:77` (`LEVEL_ALLOWANCE = 10` budgets), `cli/_main.py:114-115,133-134`.
- What it does: when a level is chosen the result is `Approximation(lower, upper, gap)`; the text says "approximate (certified within X% of the
  exact mean)" and "the policy below costs no more than the upper figure"; there is no p50/p90/CVaR ("the chain on blocks is not Markov", `_marking.py:NO_RISK`);
  `main` prints "Route view not written: it is not built for an approximate answer yet." and refuses `--route`. The spread rungs 1000/500
  were "measured on a pool of 34 families of about 59,000 weight per side, not scaled to other bases" (ADR-0023 #172), so on another base the
  first rung may pool everything or nothing.
- What it should do: the owner's later notes (BRIEF): unknowns get a best estimate with an approximate mark, "approximate with an interval reads as
  useless", no fixed cut-offs, cuts must say what they still guarantee. The guarantee is stated (a certified gap) but the answer is not a route.
- Evidence: code above; ADR-0023 "Risk numbers of an approximate answer": no p90/CVaR by default. The certified interval itself is sound (proofs in
  the ADR, oracles in `tests/test_solver_minmax.py`, `test_solver_tail.py`).
- Impact: any query with a forecast above 60 s and a coarse level (R05-like with many crafts, big pools) returns an interval and no route page.
- Origin: #83/#127/#128/#129/#130/#172; owner #81 Q2. The 1% tolerance is the owner's own earlier number, so this is a conflict between two
  owner statements; the latest ones (BRIEF) win and the code was not updated.
- Pattern: a hard-coded tolerance and rungs standing in for a decision.

### SOLVER-5: the exact-run forecast does not predict the exact run   [CONFIRMED] [impact: low]
- Where: `cli/_plan.py:350-354` (forecast on `starting_offers`), `cli/_bound_prune.py:starting_offers`.
- What it does: with 40 or more offers (fossils) the forecast is made on the small first set of the bound pruning, "the rounds that follow add a few
  offers each"; the run then also pays for the bounds (`reach_bound` per offer) and the extra rounds.
- Evidence: `decide` for R09: `exact`, predicted 0.89 s, 16,696 transitions; the run took 88 s on a GitHub runner
  (`.claude/scratch/audit/pages/run-ubuntu-latest-1/R09.log`: "ok solve 88s"); R08 predicted 1.4 s, took 76 s. (My own R09 solve ran more than
  five minutes on this PC before I killed it.)
- Impact: "exact when a benchmark query fits in about a minute" (the owner's #81 rule) is applied to a number that is off by 60-100x for
  fossil routes; the answer is still exact, so only the stated contract is wrong.
- Origin: #118 (bound pruning) and #127 (forecast) developed separately; ADR-0023 "As built (#127)".
- Pattern: a forecast of a different quantity than the one the rule is about.

### SOLVER-6: when p50/p90/CVaR are missing the page says the wrong thing, shows an internal ticket number and hides the note; CVaR is never shown   [CONFIRMED] [impact: medium]
- Where: `cli/_plan.py:407-425` (`RISK_QUANTILE_TRANSITIONS = 2_000_000`, `packed_risk`), `risk/_evaluate.py:471-489` (`_unordered_report`),
  `cli/_report.py:236-246,381-382`, `cli/_route_view.py:529-533` (`goal_card`), `cli/_route_card.py` (no CVaR), `cli/_report.py` text has no CVaR line.
- What it does: p50/p90/CVaR have four states. (a) certified point or interval from the budget DP; (b) "unresolved" (infinite) when
  `2 * RISK_BINS * cheapest < mean` and no coarse grid within `GAP_LIMIT` of the mean exists (`_plan.py:evaluate_risk`, `risk/_coarse.py`; R14 per the ADR-0063 update, not run here); (c) not
  computed when the merged chain of a packed plan has more than 2,000,000 transitions (R04: 4.7 M, the DP ran out of 16 GB) or when donors sit in a
  cycle (`_unordered_report`); (d) none for an approximate answer. States (b), (c) and the cycle case all give `Estimate(inf, first, inf)` and
  the page prints for all of them `"9 runs in 10": not resolved on the grid (#190)` (`_route_view.py:532`); the text report prints
  `not resolved on the grid (the cost scale is far above the cheapest action, ticket #190)` (`_report.py:236`). The true reason for R04 is in
  `plan.note` ("The p50, p90 and CVaR are not computed: the policy's merged chain has N transitions ..."), which reaches the text report and the JSON
  (`_report.py:297`, `:505`) but not the route page (no `plan.note` in any `_route_*` file). The page has no p50 and no CVaR field at all; the
  JSON has `cvar` and `quantiles_resolved`. For an inexact grid `p90.value` is the midpoint of the certified interval, and the page prints it as
  "X or less" without the interval (`_route_view.py:531`).
- What it should do: owner rule "cuts must say what they still guarantee"; "an output that shows internals instead of what a player does".
- Evidence: R13 (ran): `p90 = Estimate(14584.02, 14454.34, 14713.70)`, page text "9 runs in 10 ≈ 14,600 c (39 Divine) or less" (the page built on the runner,
  `.../R13-...route.html`); certified upper end 14,713.7 is not on the page. R04 `_unordered_report` code path as above (not run: it is the heavy route).
  CVaR (0.9) is computed with the quantiles for every exact plan and shown nowhere except the JSON (R13: 20,917.9, certified 20,731.9 to 21,103.8).
- Impact: R04 and R14 pages (two of the ten benchmark routes) show a false reason and a ticket number instead of "not computed: too large; simulated
  p90 is X (not certified)"; every inexact-grid page shows a midpoint as if it were an upper bound.
- Origin: #190 (`d821f59`, risk cut for unresolved quantiles) and #374 (`ce22525`, packed plans keep exact moments and say so only in `note`); ADR-0063 update ("Open").
- Pattern: a limit reported where it is raised, not where the number is read; one message for three causes.

### SOLVER-7: with a start price of 0 there is no restart, so every action with a dead-end outcome becomes infeasible   [CONFIRMED] [impact: medium]
- Where: `cli/_plan.py:325-328` (`if price_of_start.chaos > 0:` offers `restart`), `cli/_plan.py:216-233` (`resolve_start_price`: "A target without
  `start_price` counts its start item as free"), `solver/_graph.py:proper_states` (an action that can fall into a state with no proper policy has
  infinite cost).
- What it does: a free start item (no `start_price` in the target, or `--start-price 0`) removes `restart` from the offers. A bricked item then has no
  action, and every action that can reach one with any positive chance is dead. Nothing marks that the plan avoids risk only because buying again was
  not modelled.
- What it should do: owner rule "restart = buying or making the start item again"; the cost of a free base is still near 0, not "impossible".
- Evidence (ran, `t12.py`, V01 helmet, four orbs, plain start): start price None (file price 2.0): mean left 1,346.94, `restart` in 688 of 778
  policy states; `start_price=0.0`: `PlanError: no policy of the offered actions reaches the goal from the start item`; `start_price=0.01`: mean left
  **186.04**, `restart` in 751 of 778 states. The same target is 7x cheaper at price 0.01 than at 2.0 and an error at 0.
- Impact: any target without a `start_price` (J01, R03, R06 examples have none) whose cheap route needs a restart is an error or, where a safe policy
  exists, a silently dearer policy. Today only J01 is plannable and it has no dead end, so the visible damage is latent.
- Origin: #60 (`3c123fc`, "target-aware offers, restart, bench-craft rule"); ADR-0011 "buying an item is an action".
- Pattern: a default (free = no action) that decides a game question.

### SOLVER-8: "the model cannot evaluate this" is treated as "the game refuses this", in eight places and in the report text   [CONFIRMED] [impact: medium]
- Where: `cli/_prune.py:86,129`, `cli/_packed.py:121`, `cli/_approx.py:137,189`, `cli/_donors.py:83`, `cli/_route.py:456`, `cli/_route_sim.py:48`, `cli/_bound_prune.py:423`
  (`except ActionError: return REFUSED, ONE, level`), report text `cli/_plan.py:492` "the game refuses it on this item wherever it can be";
  definitions in `actions/errors.py` (`NotApplicableError` = the game refuses; `OutOfScopeError` = "no admitted rule covers this state yet, the
  planner treats the action as unavailable").
- What it does: both subclasses are caught by `except ActionError` and the action is simply absent at that state. The optimum is taken over the
  smaller set; the plan, the page and the JSON do not count or name the (state, offer) pairs dropped as out of scope, and the bound-pruning left-out
  list files an out-of-scope offer under "the game refuses it".
- What it should do: owner rule "unknowns get the best estimate and an approximate mark; never silently"; ADR-0004 (binary admission, a rules registry).
- Evidence: code lines above. `errors.py` lists out-of-scope cases that exist in the model: influenced items of a class with no admitted influence key,
  a magic item whose Alteration keeps a metamod, jewels for most actions, "a pool mod with other than one family", Essence of Desolation, fractured
  mods that fill the forced mod's side. I did not find a counter or a report line for them (`grep OutOfScopeError cli/` finds only `_decide.py`).
- Impact: unknown in size; a route whose best action is out of scope at some state is silently priced without it.
- Origin: #56/#60 (the `ActionError` family and `solver_actions`), ADR-0004.
- Pattern: two different reasons collapsed into one branch; a gap in the model reported as a rule of the game.

### SOLVER-9: the text report's "single-draw weight share" ignores the tier, roll and crafted limits of the requirement   [CONFIRMED] [impact: medium]
- Where: `cli/_shares.py:weight_share/start_shares`, caller `cli/_report.py:87-100,191` (`_goal_leaf_nodes` passes `node.mod_ids` only), printed at
  `cli/_report.py:387-396`; `cli/_benchmark.py:562` for the published shares.
- What it does: `wanted` is the summed weight of every mod in `leaf.mod_ids` (all tiers of the family), `total` the pool; `min_tier`, `min_roll` and
  `not_crafted` of the leaf are dropped. The leaf label printed next to it does say "(tier 1 or better)".
- What it should do: ADR-0020 "the guide's way of quoting odds"; the owner's rule that an unstated tier is the top tier: a "tier 1 Life" share is the
  weight of tier 1.
- Evidence (ran, `t5.py` and `t13.py`, R05 ring): the block prints `Chaos Orb | family IncreasedLife (tier 1 or better) | 8000 / 149050 = 5.367 %`.
  The pool has eight Life tiers of weight 1000 each; tier 1 alone is 1000 / 149050 = 0.671%. Likewise `FireResistance (tier 2 or better)` prints
  7000 / 149050 = 4.696% while the top tier the ring allows (tier 2) is 1000 / 149050 = 0.671%; Cold and Lightning the same. The same block prints
  "chance of one use" from the kernel (which does honour tiers) next to it, so the two numbers sit side by side and disagree by 7 to 8 times.
- Impact: the "Single-draw weight shares" block of the text report for every target with a tier limit and a Chaos Orb/Harvest reforge offer (R05 is
  one; I did not check the others). Not on the route page.
- Origin: #26 (`2dcbe31`, R12 end to end: R12 has no tier limit, so the share was right then); targets gained `min_tier` in #60/#66 and the
  share code was not touched.
- Pattern: a number shown without the limits that define it.

### SOLVER-10: shared kernels and "exact" prunings rest on declarations that are only spot-checked   [SUSPECTED] [impact: medium]
- Where: `cli/_packed.py:48-49,112-125` (`VERIFY_FIRST = 20`, `VERIFY_EVERY = 4_096`), `cli/_prune.py:keyed_offers` (equal-kernel merge through
  `Abstraction.kernel_key`), `cli/_bound_prune.py` (assumption (2) of the module text: "an offer the game refuses on the bare item never applies at a state
  of that shape ... an assumption on the contract of `Reads`, not a check"; twins by `twin_key`).
- What it does: the packed walk builds one kernel per `kernel_key` and shares it across states; it recomputes a fresh kernel only for the first 20 shares
  and then one in 4,096 (R04: roughly 100 to 200 checks out of several hundred thousand shares), then prints "all equal". The same key drives the
  equal-kernel merge of the object path (the dearer of two offers with an equal key is never built). Twin merge and the bound prune depend on
  `twin_key`/`Reads`/`Adds`/`reach_bound` being true for every state.
- What it should do: ADR-0031 calls these exact; a wrong key would make a plan cheaper than the game allows with no sign. The checks are sampled
  oracles (tests on R10 samples, `tests/` property tests), not proofs, and the report does not list them as unverified.
- Evidence: code only (no counter-example found); I did not run a sweep.
- Impact: unknown; the failure would be silent. Same family as the seeds (a declaration read as truth).
- Origin: #118 (ADR-0031), #374 (`8bb50d9`).
- Pattern: trust by declaration with sampled checks.

### SOLVER-11: free actions are a numeric placeholder (1e-6 x the cheapest paid offer) and are recognised later by value   [CONFIRMED] [impact: low]
- Where: `cli/_offers.py:23,125-132` (`FREE_ACTION_SHARE`, `price_offers`), `risk/_free.py:is_free` (`cost <= free_cost * (1 + 1e-12)`), `cli/_plan.py:evaluate_risk`.
- What it does: an action that consumes nothing (unveil, pick) is given a cost of 1e-6 of the cheapest paid offer so that `Action.cost > 0`; the solver sums
  it into the mean and the risk run decides which states are free by comparing each action's cost with that number.
- What it should do: a free action should be free; the epsilon is documented (ADR-0026, #145, #349) and its effect on the mean is of order 1e-9 relative.
  The identification by value would misfire only if a paid action cost less than the epsilon (the restart price is appended after the epsilon is
  computed, `price_offers` runs before `restart` is added, so a start price below 1e-6 x the cheapest paid offer would be called free).
- Evidence: code only.
- Impact: negligible today; shows as `grid.free_allowance`/`free_tail` lines in the text report ("free actions are counted at 1e-06 Chaos each").
- Origin: #145 (`ca05208`), #349 (`31b6398`).
- Pattern: a value invented to satisfy a type, later read as meaning.

### SOLVER-12: `--verify` raises when the start item already meets the target   [CONFIRMED] [impact: low]
- Where: `cli/_verify.py:112` (`min(...)` over an empty policy in `max_steps_for`).
- Evidence (ran, `t7.py`): R12 with only the fractured requirement: plan is fine (`goal at start True`, policy size 0, mean 0); `verify(...)` raises
  `ValueError: min() iterable argument is empty`; the CLI prints "Error: min() arg is an empty sequence".
- Impact: only a degenerate target; shows that the path "start already a goal" is untested for `--verify`.
- Origin: #26.
- Pattern: edge never exercised.

### SOLVER-13: the hard-coded cut-offs of this area, and which of them change the answer   [CONFIRMED] [impact: medium]
Inventory (all read in code; "answer" = changes the mean or the policy shown, "width" = changes only how tight a certified interval is, "existence" = decides whether a number exists):

| constant | where | effect | reported? |
|---|---|---|---|
| `BUDGET_SECONDS = 60`, `TOLERANCE = 0.01`, `EXACT_TRANSITIONS = 2_000_000`, `SOLVE_RATE_CEILING`, `PILOT_*` | `_decide.py:47-54` | answer (exact vs interval vs refused), machine-dependent | yes for an interval, no for the refusal reason (SOLVER-3) |
| `LADDER` (groups of 8, 4; tail theta 1e-2/1e-3/1e-4), `SPREAD_LADDER` (1000, 500 weight units from one bow), `LEVEL_ALLOWANCE = 10` | `_decide.py:73-86`, `_approx.py:77` | width (certified) and whether a level is found | level named in the answer |
| `RISK_QUANTILE_TRANSITIONS = 2_000_000` | `_plan.py:407` | existence of p50/p90/CVaR | text/JSON note, not the page (SOLVER-6) |
| `RISK_BINS = 200_000`, `UNRESOLVED_BINS = 1_000`, `COARSE_BINS = 1_000_000` | `_plan.py:445-447` | existence/width of quantiles | partly |
| `GAP_TARGET = 0.02`, `GAP_LIMIT = 0.1`, `COSTS_TRIED`, `PARTS_TRIED`, `DENSE_*` | `risk/_coarse.py:35-41` | width (a coarse p90 may be 2-10% of the mean wide) | `grid` in JSON; page shows a midpoint |
| `HORIZON_SDS = 6`, `WORK_BUDGET = 3e8`, `tail_mass = 1e-9`, `FREE_TAIL = 1e-9`, `COUNT_BINS`, `PAID_STATES_LIMIT` | `risk/_evaluate.py`, `risk/_free.py` | width / existence | `grid.step`, `unresolved_mass` |
| `value_ceiling = 1e12` (Chaos) | `solver/_solve.py:solve` default | answer: a state of a branching component above it is declared dead | not reported |
| `ACCEPT_BOUND = 1e-6` | `solver/_packed_solve.py:41` | refuses to answer above it | ConvergenceError text |
| `STEPS_PER_MEAN = 50`, `MIN_STEPS = 100`, simulator `DEFAULT_MAX_STEPS = 100_000`, `_route_sim.DEFAULT_MAX_STEPS = 200_000` | `_verify.py:29-30`, `_simulate.py:53`, `_route_sim.py:19` | "unfinished" runs are cut and counted at the cost paid so far (censoring); the verdict is "does not agree" | `unfinished` count in the report |
| `MIN_OFFERS_TO_PRUNE = 40`, `SMALL_START = 8`, `PER_ROUND = 16`, `rounds = 8` | `_plan.py:43`, `_bound_prune.py` | speed only (the certificate decides) | `pruned.bounded` |
| `max_imprints = 1`, `memory_strands = off`, `recipe_starts`, `recombinator_junk_craft = false` | `config.py` | answer (model scope) | the strand line only |
- None of these drops outcomes by probability in the solver. ADR-0063 point 5 ("fixed rails and thresholds are not defaults") is still **Draft** ("Not accepted") while
  its point 1 is built (#374); the thresholds above are the very kind it lists.
- Origin: ADR-0023, ADR-0063, #190, #374, #127.
- Pattern: constants measured on one route used as rules for all.

### SOLVER-14: the recombinator is planned as "one reading plus an interval over alpha", the opposite of "best estimate with an approximate mark"   [SUSPECTED] [impact: low (not live)]
- Where: `risk/_readings.py` (module text), `cli/_interval.py`, ADR-0012 amendment / ADR-0033; `cli/_plan.py:329-336` raises `PlanError` if an offered action reads a rule axis.
- What it does: for rule axes (the selection exponent alpha, the Awakener's group conflict) the driver solves one model per reading, evaluates every
  optimum under every reading, reports the plan at alpha = 1, the plan's cost interval over the grid, "the route with the smallest worst case" and a
  certified bracket of the robust optimum. The interval is "the plan's cost at each reading and not a bound".
- What it should do: owner rules "unknowns get the best estimate and an approximate mark", "approximate with an interval reads to him as useless".
- Evidence: code and ADR text. Not wired into `make_plan` yet (waits for #217), so no page shows it today.
- Impact: future recombinator routes.
- Origin: grill B3 (#94), #220, #221.
- Pattern: an interval standing in for a decision.

### SOLVER-15: given-route evaluation by simulation censors long runs at a fixed number of uses   [SUSPECTED] [impact: low]
- Where: `cli/_route_sim.py:19` (`DEFAULT_MAX_STEPS = 200_000`), `simulator/_simulate.py:53` (`100_000`).
- What it does: a run that has not reached the goal after that many uses is `unfinished` and its cost so far enters the mean and quantiles. R13's plan has
  ~58,000 uses of one action; a route with that many mean uses loses a few percent of its runs to the cap (geometric tail beyond 3x the mean). `verify` computes its own limit
  (`max_steps_for`), so only `simulate_route` (R04/R14 given routes, scripts) and direct `simulate` callers see the fixed numbers.
- What it should do: owner rule "no fixed 100k-uses".
- Evidence: code; the count of unfinished runs is in the report.
- Impact: low (reported as `unfinished`, only used for routes too large to evaluate exactly).
- Origin: #70, #25.
- Pattern: a rail in a helper.

---

## Checked and found sound (so the synthesis does not re-open them)
- The cost model: one price per use, constant per unit; `restart` returns the start state at the start price and is available in all non-start states; sunk cost is not
  counted; the mean includes the first purchase once (`_verify.py:132`, `_plan.py:325-328`). It is the right quantity under ADR-0006 (the unit price is constant in volume, not marked).
- Proper-policy condition, certificate of every solve (`_certify.py`, `_packed_solve.py:certify`, run on the unmerged graph), the 1e-6 accept bound.
- Bound pruning argument (`_bound_prune.py`) and the tail-cut argument (`_tail.py`): I read the proofs; the assumptions are named in their text.
- The risk module's intervals are certified and it says when they are not (`unresolved_mass`, `grid.exact`); its failure is in the display (SOLVER-6).
- The lift of an approximate policy is sound only for block-invariant actions, and the code refuses the others (`BlockModel.__init__`, `coarsening.require_invariant`).

## Patterns seen in this area
1. **Independent in code, shared in meaning**: the check reads the same stored tiers, pools, prices, declarations, and compression as the thing it checks. SOLVER-1.
2. **Equivalence found, then not used for meaning**: exact lumping exists as a speed tool; the page shows the unlumped states. SOLVER-2.
3. **A decision by clock or by a constant measured once**: exact/approximate/refused, the ladders, the 2 M and 60 s and 1% limits, the forecast. SOLVER-3, 4, 5, 13.
4. **One reason for several causes, and internals in the owner's text**: "not resolved on the grid (#190)" for three causes; "(#69, ADR-0023)" in a refusal; "the game refuses" for a model gap. SOLVER-3, 6, 8.
5. **A default that decides a game question**: price 0 means no restart; an epsilon marks "free". SOLVER-7, 11.
6. **A number shown without its limits**: shares without the tier, p90 midpoint as "or less", exactness never stated on an exact page. SOLVER-6, 9.
7. **Trust by declaration with sampled checks**: `kernel_key`, `twin_key`, `Reads`. SOLVER-10.
8. **A Draft decision used as a spec for built code; later facts not propagated** (ADR-0063 Draft vs #374; the 2 M message after R04 solved). SOLVER-3, 13.
