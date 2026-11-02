# Audit PLANNING (ticket #396): what the planner offers and where it starts

Scope read in full: `cli/_main.py _plan.py _offers.py _prune.py _starts.py _start_options.py _start_step.py _start_types.py _donors.py _inputs.py _marking.py _route.py _benchmark.py _benchmark_outcomes.py`, `config.py`, `examples/routes/*.yaml`, `examples/targets/*.yaml`, `examples/buy/*.yaml`; read for context: `_bound_prune.py`, `targets/floor.py`, `actions/{bench,errors,catalog}.py`, `items/vendor_recipes.py`, `prices/price_source.py`, ADR-0011/0013/0061, the reference-routes research, the tests that pin the benchmark.
Reproduction scripts (each under a minute, one process, fixture prices `tests/fixtures/prices/routes-allflame-2026-10-31.json`) are in `.claude/scratch/audit/planning_work/` (`offers.py`, `r12.py`, `r13.py`, `r13lvl.py`, `oos.py`, `tiers.py`, `v01.py`); run them with `PYTHONPATH=src python <file> [target-stem]`.

Counts: 3 high, 9 medium, 5 low (17 findings).

---

### PLANNING-1: a target without `actions:` is planned without every opt-in kind and without the five metamods, and the report says nothing about it   [CONFIRMED] [impact: high]
- Where: `cli/_offers.py:289-302` (the "kinds not named" `LeftOut` is built only `if kinds_named is not None:`); `cli/_offers.py:264-275` (a bench craft that "counts toward no requirement" is left out); `actions/*.py` `@kind(..., opt_in=True)` (17 kinds: `exalted-orb annulment-orb fracturing-orb talisman-fracture fossil-set harvest-add-remove harvest-resistance-swap harvest-damage-swap veiled-chaos-orb veiled-exalted-orb unveil pick aspect-beast beast-side-swap wild-bristle-matron corrupted-essence foulborn-exalted-orb`).
- What it does: with no `actions:` key `offers_for` lists only the non-opt-in kinds (Chaos Orb, Harvest reforges, essences, counting bench crafts, Remove Crafted Mods, the four basic orbs, Divine when a roll limit exists). Exalted, Annulment, Fracturing, fossils, Harvest add/remove, beasts, veiled orbs are absent, and `plan.left_out` has no line for them. The five metamods (Prefixes/Suffixes Cannot Be Changed, Can have up to 3 Crafted Modifiers, Cannot roll Attack/Caster Modifiers) are never offered unless the target names each by label, because "its mod counts toward no requirement".
- What it should do: the answer is "the cheapest policy"; either offer the kind or say in the answer which kinds were not searched (the code already does this for a target WITH `actions:`: "the plan is the cheapest among the named ones"). Owner rule: cuts must say what they still guarantee.
- Evidence: `PYTHONPATH=src python .claude/scratch/audit/planning_work/offers.py r05-strength-ring` prints 90 offers, no label containing Exalted/Annulment/Fractur/Fossil, and `left_out count 1` (only the 129 counting-less bench crafts). `offers.py r14-hunter-bow` (target `actions` ignored): `offered metamod? []`, and the left-out crafts contain all five metamods under the reason "its mod counts toward no requirement ... could still pay off by clearing a family from the pool". The reason text itself admits the plan is "the cheapest among the offered crafts only", but nothing tells the owner the crafts that make R04/R14-type routes work (metamod + Exalted slam) were never candidates.
- Impact: R05, R10, R11, R12 (and R03/R06) are planned without Exalted/Annulment/Fracturing/fossils; any target an agent writes without `actions:` is planned without metamods, so a metamod route can only appear if the author already knows to name the five labels (as R04/R14 do). Size of the miss is unmeasured; the omission is structural.
- Origin: `d2432f4` (#70, Exalted/Annulment/Fracturing "named-only planner kinds"), `ba122bf` (#63, fossil sets opt-in), `d505bf2` (R13 `actions` key: the left-out line was written only for the named case). The docstring of `offers_for` says "REVISIT with the Exalted Orb and Annulment Orb (#67) and the metamods (#68)"; the revisit never happened.
- Pattern: a limit applied silently on the default path while the same limit is reported on the explicit path.

### PLANNING-2: Orb of Scouring and Orb of Alchemy are not planner actions and are never mentioned; "buy the start item again" stands in for them   [CONFIRMED] [impact: medium]
- Where: `actions/scour.py:133`, `actions/alchemy.py:71` (`planner=False, why_not="not in the B1 offer set; which actions a target needs is pruning (#118)"`); `cli/_offers.py:293-298` (the "kinds not named" list is built from `kinds(planner_only=True)` only); `cli/_plan.py:325-329` (restart).
- What it does: naming either in `actions:` raises "action kind(s) scouring-orb cannot be used by the planner yet". They appear in no `left_out` line, in no report line, in nothing the owner reads. Every reset of a bricked item is a repurchase of the start item at the trade price.
- What it should do: ADR-0013 lists Alchemy and Scouring in B1's action set; the owner's rule "an essence that reforges a rare without Scouring must be said" assumes Scouring is a real alternative. A reset by Scouring (0.37 c in the fixture) plus the first orb is far cheaper than a new belt (10 c).
- Evidence: `python .claude/scratch/audit/planning_work/r13.py`: R13 mean_remaining 6300.85 with restart at the belt price 10.0, 5826.48 with restart at 0.3732 (Scouring + Transmutation), same policy structure, same 4066 states: the missing action alone moves R13 by 7.5% and the solver prints no hint. `catalog` shows `planner: False` for `alchemy-orb` and `scouring-orb`.
- Impact: every plan whose policy contains `restart` (R04, R13, R14, R10-R12 when an essence misses is not affected, but any Normal-start route is) is over-priced, by more where the base is dear (R08/R09 bases 29.8 c / 5 c, R04 quiver). Normal-start routes can only become Rare through Regal or an essence, never Alchemy, which is why R08/R09 carry the placeholder start of PLANNING-9.
- Origin: `caf3bcb` (#108 catalog), the R13 ticket #66 ("WIP #66"); ticket #64 ("Orb of Alchemy and Scouring as exact actions") built the actions and #118's pruning was left to decide the offer set.
- Pattern: an action that exists in the catalog but is withheld for performance, with no word in any output.

### PLANNING-3: the limits of a plan (actions: list, unpriced drops, pruning, notes) are printed in the text report and the JSON only; the route page says "Cheapest policy of the planner"   [CONFIRMED] [impact: high]
- Where: `cli/_report.py:311-323` (Dropped for lack of a price / Not offered), `:505-524` (JSON); nothing in `cli/_route_view.py`, `_route_report.py`, `_route_flow.py`, `_route_card.py` reads `plan.left_out`, `plan.dropped`, `plan.note`, `plan.pruned`, `plan.strands`.
- What it does: the route page (the thing the owner opens) never shows which kinds the target's `actions:` removed, which actions were dropped for want of a price, or the plan note.
- Evidence: `python .claude/scratch/audit/planning_work/r12.py` renders R12's page: 0 occurrences of "Dropped", "Not offered", "left out", "Harvest Reforge Fire", while the text report of the same plan lists 19 "Dropped for lack of a price" lines and two "Not offered" lines (148 crafts, 50 offers "proved never better"); the page heading is "Cheapest policy of the planner". 6 of the 10 benchmark targets (R04, R08, R09, R13, R14, V01; also J01) carry an `actions:` list "to keep the graph small" (R13's own comment: Chaos Orb would give more than 43,000 states).
- Impact: the owner reads only the page; for 6 of 10 benchmark routes the headline "cheapest" is "cheapest among the kinds an agent chose for the state-space budget".
- Origin: `d505bf2` (R13 `actions` key) and the route-view tickets #96/#298 (B8-6 "Report, route page and given routes" is still open); the report channel was text first.
- Pattern: a guarantee stated where the owner does not read.

### PLANNING-4: an action with an unpriced resource is dropped, not estimated   [CONFIRMED] [impact: medium]
- Where: `cli/_offers.py:94-132` (`price_offers`: `missing.append(name)` then the offer goes to `dropped`), `cli/_plan.py:319-322`.
- What it does: any offer whose resources are not all in the price file vanishes before pruning and equal-kernel merging; the plan is the cheapest among the survivors and carries no approximate mark.
- What it should do: owner rule "unknowns get the best estimate and an approximate mark". ADR-0007 says "never guessed", which is older than that rule.
- Evidence: `r12.py` output: `Dropped for lack of a price: Harvest Reforge Fire (no price for Wild Crystallised Lifeforce)`, 11 more Harvest reforges, and `Screaming Essence of Greed/Sorrow/Wrath/Doubt/Scorn, Shrieking Essence of Doubt/Dread`. `tests/test_cli_routes_real.py` pins exactly these 7 essences as `UNPRICED_ESSENCES` for R10/R11/R05; `tests/test_cli_r04_r14_real.py` asserts `dropped == ()` only for R04/R14.
- Impact: a dropped essence tier or reforge can be the cheapest way for the target; the plan is silently dearer. The effect is only visible in the text report/JSON (PLANNING-3).
- Origin: `price_offers` since `2dcbe31` (#26, R12), ADR-0007.
- Pattern: a missing input treated as "action not available" instead of "estimate and mark".

### PLANNING-5: a model gap (`OutOfScopeError`, "no admitted rule covers it") is swallowed as if the game refused the action   [CONFIRMED] [impact: medium]
- Where: `cli/_prune.py:86` and `:129`, `cli/_donors.py:83`, `cli/_packed.py:121`, `cli/_approx.py:137,189`, `cli/_bound_prune.py:423` (an `OutOfScopeError` on a reroll becomes `REFUSED`, worded to the owner as "the game refuses it on this item wherever it can be", `_plan.py:491-492`); the raise sites: `actions/bench.py:226-231` (a bench craft on a Normal item, or on an item with no mod), `actions/errors.py` (`OutOfScopeError`: "no admitted rule covers yet").
- What it does: `except ActionError: continue` catches `NotApplicableError` (the game refuses) and `OutOfScopeError` (the model cannot say) alike. The action is not a candidate at that state and nothing is recorded.
- What it should do: a model gap must refuse the plan, or mark it approximate and name the state class; it must not read as a game rule.
- Evidence: `python .claude/scratch/audit/planning_work/oos.py r13-life-resist-belt` wraps `Abstraction.kernel_key` and counts: `('BenchCraft','OOS') 8`, sample `the item is normal; no admitted rule says what a bench craft does to a normal item` (the R13 start state is a Normal belt; all 8 counting bench crafts are silently unavailable there). R12 has 0 OOS hits. The R08/R09 start item is `rare` with no mods: `bench.py:230` says "holds no mod, which no admitted rule covers", so bench crafts are unavailable at that start too.
- Impact: unmeasured; the omission is exactly at the start state of every Normal-start route (R04, R13, R14, V01 plain) and at R08/R09's start. For a bench craft on a Normal item the code does not even claim the game refuses it.
- Origin: `bae8e7c` (#118, "the game refuses it here, or no admitted rule covers it" comment), `ab77c77` (#23, the two error classes).
- Pattern: two different meanings (game says no / model cannot say) behind one exception handler.

### PLANNING-6: the `price_source` setting, `price_gap_percent` and `--price-source` are read by nothing; the plain start item is priced by whatever entry the price file holds, and R04's is a poe.ninja line of another item level   [CONFIRMED] [impact: medium]
- Where: `config.py:25-30,65-66,111-112`; `cli/_main.py:89,111-112`; `cli/_starts.py:105-106,122`; `cli/_start_options.py:62-75` (`StartContext.price_source/gap_percent/today`, never read by `vendor_recipe_starts`); `prices/price_source.py` `source_price` (exported, called from nowhere in `src/`); `cli/_plan.py:216-237` (`resolve_start_price`).
- What it does: the three settings are validated, documented ("says which price a bought start item is priced with"), passed down, and ignored. `SOURCES = (vendor_recipe_starts,)`: the bought-item source of #337 does not exist. A start item is priced by `prices.prices[name]`; `stale_warning` is a stderr line only.
- What it should do: ADR-0061 d2 and its #357 amendment: trade price when a market exists, poe.ninja as the marked fallback, both side by side with a gap flag. The owner's trade rule: instant buyout, any age, mean of the cheapest few.
- Evidence: `grep -rn "source_price(" src` finds only the definition and the re-export. `tests/test_cli_r04_r14_real.py:43`: `START["R04"] = ("Penetrating Arrow Quiver (ilvl 81)", "poe.ninja", 9.0)`; `examples/buy/r04-start-quiver.yaml` says the trade search of this very spec found "3 listings (mean 130 Chaos)" and the committed price is "the poe.ninja line of the cheapest normal quiver of item level 81 or more ... item level 85, 43 observations". So R04 plans a level-81 quiver (`item_level: 81`) priced as a level-85 one, from the source the owner's rule excludes, 14x below the trade number.
- Impact: every benchmark start price is a hand-curated fixture entry; R04's 25% fracture loop buys quivers repeatedly, so its mean moves with that 9 c vs 130 c choice; the settings give the owner a switch that does nothing.
- Origin: `5b124ec` (#357, 2026-11-01); consumer tickets #351, #354, #359 are open.
- Pattern: a setting accepted and documented before the thing it controls exists.

### PLANNING-7: other planner settings and keys are accepted, documented as acting, and have no effect or always fail   [CONFIRMED] [impact: low]
- Where: `config.py:11-23` and `_read_planner`: `max_imprints` (`actions/imprint.py:210` is the only consumer, `imprint` is `planner=False`), `recombinator_junk_craft` (`recombinator` is `planner=False`; the contextvar is set by tests only), `memory_strands` (`cli/_plan.py:289-294` raises `PlanError` for any run where it is on). The docstring of `config.py` says it "turns the Memory Strands of the planner on: the Orb of Remembrance, the Foulborn orbs...".
- Evidence: `grep -rn "max_imprints\|recombinator_junk_craft" src --include=*.py` shows no use under `cli/`; `memory_strands = true` makes every plan end in "Memory Strands are on ... which the planner cannot plan yet".
- Impact: a default that "decides a game question" (one imprint per item, no junk craft before a recombinator) is decided for nothing; harmless today, a trap when #223/#217 land.
- Origin: `1d11219` (#219, ADR-0060), #216/#217, #275.
- Pattern: same as PLANNING-6.

### PLANNING-8: ADR-0061 d1 and the glossary say the item level is a floor and "the planner plans one option per group"; the CLI plans at exactly the file's `item_level`   [CONFIRMED] [impact: medium]
- Where: `GLOSSARY.md` ("Item level floor", "Level group"), `docs/adr/0061-*.md` decision 1, `targets/floor.py` (`item_level_options`, `target_at_level`): no caller in `src/` outside `targets/`; `targets/__init__.py:77-80` documents `item_level_floor`; ticket #359 ("Plan the start options and choose the cheapest") is open.
- What it does: `make_plan` and `plan_with_starts` use `target.item_level`; `item_level_floor` is parsed and never read by the planner, `tiers_top_at_item_level` only by `floor.py`.
- Evidence: `python .claude/scratch/audit/planning_work/r13lvl.py`: the derived floor of R13 is 84 (`FireResist8`); planning R13 at 86 (the file, and the CLI) gives mean_remaining 6300.8, at 84 gives 5888.9, same prices (-6.5%; ADR-0061 itself measured 5,492 at 84 against 6,311 at 86 with level-priced belts). R13's `item_level: 86` was chosen by the agent (the guide says null).
- Impact: R13, R08, R10, R11, R12 (all "guide gives none" levels) are planned at an invented level; the page does not say a lower level is cheaper.
- Origin: `d7cf1b0` (#352) built the floor and left planning to #359.
- Pattern: a decided behaviour documented in the present tense that the pipeline does not use.

### PLANNING-9: R08 and R09 start from an item that does not exist: a Rare with no mods, with the Alchemy folded into the price   [CONFIRMED] [impact: medium]
- Where: `examples/targets/r08-energy-shield-boots.yaml` and `r09-life-boots.yaml` (`start_item: rarity: rare, mods: []`, comment "the model starts from the rare boots with no mod and the price of the start item includes the Alchemy"); fixture price `R08 start boots` = 29.82716 = trade price 29.8 of a Normal base + 0.02716 (one Orb of Alchemy); `examples/buy/r08-start-boots.yaml` searches `rarity: normal`.
- What it does: the card of step 1 shows a bought Rare item with no mods (an item no market sells); the Alchemy click is not a step; a real Alchemy gives 4-6 random mods, which may already hold the target's mods (the model ignores that chance, the comment calls it "at most one fossil use"). Combined with PLANNING-5 no bench craft is possible at that start.
- What it should do: owner rule "show every in-game step; never hide one (a bought item drawn 'empty')".
- Evidence: the target comments; fixture price note "the start item is that base made rare; see the target".
- Impact: R08/R09 pages draw a hidden step and an impossible bought item; mean overstated by up to one first fossil use (the files' own estimate: 1.6 c solver, 35-38 c in the guide's pair, so the "solver <= guide" gap is also biased).
- Origin: `ba122bf` (#63): a plan with Alchemy as an action "did not finish in 60 minutes on a GitHub runner".
- Pattern: a placeholder item invented to keep the state space small, then drawn as meaning.

### PLANNING-10: the start item is described twice, by hand, and nothing reconciles the two: R09, R12, R14, R04 besides the seed R05   [CONFIRMED] [impact: medium]
- Where: `examples/targets/*.yaml` (`base`, `item_level`, `start_item`, `start_price` name) against `examples/buy/*.yaml` and the price-file entry; no code compares them (`cli/_route_trade.py` never reads `target.base_id` or `item_level`; no test cross-checks).
- Evidence, route by route (modelled item -> what is priced):
  - R05: Amethyst Ring, level 75 -> any ring, level >= 75 (the seed).
  - R09: base `BootsAtlas1` (Evasion/ES Two-Toned Boots), level 86 -> query `type: 'Two-Toned Boots'` with no defence filter in the fixture (`R09 start boots`, 37 listings): the three game bases named Two-Toned Boots (Armour/Evasion, Armour/ES, Evasion/ES) all match, the target file itself notes the three exist.
  - R12: `Paua Amulet`, level 84 -> `category: accessory.amulet`, `item_level_min: 75`, any Lightning Resistance fractured (909 listings, 1.0 c). R10 and R11 specs say "the item level is the one of the target, so the item bought is the item the planner starts from"; R12's does not, and a level-75 amulet has the smaller pool the planner does not model (its 2.88% is computed at 84).
  - R14: Normal Thicket Bow, Hunter -> `rarity: nonunique` (normal, magic and rare listings; the file comment says "as it drops (normal)").
  - R04: Penetrating Arrow Quiver level 81 -> poe.ninja line of level 85 (PLANNING-6).
  - R08, R10, R11, R13: match in base and level.
- Impact: start prices of five of ten routes are for an item other than the one planned; sign unknown, size small for R05/R09/R12/R14 (a few chaos), larger for R04.
- Origin: `3c123fc` (#60, "every plain ring has the same pool of mods") for the pattern; ADR-0061 intends the planner to pick the base from a priced list (#351/#354/#359 open), so the specs were written for a planner that does not exist yet while the targets pin one base.
- Pattern: one fact written by hand in two places with nothing reconciling them.

### PLANNING-11: a start mod's `tier:` is hand-written and never checked against the game data; R12's is wrong   [CONFIRMED] [impact: low]
- Where: `examples/targets/r12-lightning-amulet.yaml` (`LightningResist2`, `tier: 3`); `targets/parse.py:1066-1088` (`read_start_mod`: tier "taken as written"); `abstraction/_kernel.py:762` (`status_of(leaf, entry.mod_id, entry.tier, ...)` reads the stored tier).
- Evidence: `python .claude/scratch/audit/planning_work/tiers.py` and the all-targets loop: every start mod matches `tier_table` (R05 T1, R10 T2, R11 T1, R03 T1) except R12: written 3, data 7. The R12 page prints "T7 fractured" (derived) while the state's status was computed with 3.
- Impact: R12's requirement has no `min_tier`, so the answer is unchanged; any tier-limited requirement on a hand-written start mod would be judged on the wrong number. The comment in the file ("until the planner can derive tiers ... ticket #23") is stale.
- Origin: #26 (R12) wrote it before `tier_table` existed.
- Pattern: a hand-written value that duplicates derivable data.

### PLANNING-12: the benchmark's "solver mean <= given route mean" cannot fail on a model fault, and for R04 and R14 it is vacuous   [CONFIRMED] [impact: high]
- Where: `cli/_benchmark.py:394,525-531` (`_not_dearer`: `if given_mean is None: return True`), `:107-252` (`BENCHMARKS`: R04 -> `r04-penetrating-quiver.yaml`, R14 -> `r14-hunter-bow.yaml`, the routes WITHOUT the final `restart`), `:9` ("It NEVER fails a route"); `docs/adr/0013-*.md` ("recorded, never a failing test"); tests `tests/test_cli_routes_real.py::test_the_solver_is_no_dearer_than_the_guides_given_route`, `tests/test_cli_benchmark.py:69,208`.
- What it does: (a) both sides are evaluated on the same offers, kernels and prices, so "optimal policy <= a policy of the same model" holds by optimality whatever the model says about the game; it tests the solver, not the model. (b) A fault that makes the model cheaper (the bench `CRAFTED_TIER = 1` of the seed) only widens the margin; R05's given route is one rule (`rare -> Deafening Essence of Rage`, no bench) so any fault that gives the solver a craft makes it pass. (c) The solver searches the kinds the guide uses (`actions:`), so "no dearer than the guide" is also nearly by construction. (d) For R04 and R14 the as-written routes have gaps ("what they leave out is a gap", `test_the_guides_route_and_its_completed_form_...`), so the given mean is infinite -> `None` -> `_not_dearer` returns True. (e) the published-odds rows that DIFFER are pinned as expected in tests: `("Exalted Orb","100%","13%",False)`, `("Exalted Orb","100%","20%",False)` for R04 and `55%`, `10%` for R14; a test that expects the mismatch cannot catch it getting worse.
- What it should do: a check that can fail on the model: compare against a number a guide states (R12's 2.88% / 1.338% do this and are a good oracle), or against the game, not against a policy of the same model.
- Evidence: reading the code and tests above; `_not_dearer(100.0, None)` is `True`.
- Impact: the pass rule of ADR-0013 reports green for R05 with the seed fault and for R04/R14 with a given route that never finishes. The only independent oracles in the benchmark are the published odds (R12 two numbers; R04 25%/33%/50% rows).
- Origin: `6d13ab3` (#57, 2026-10-31); ADR-0013 pass rule.
- Pattern: a check whose two sides share the code under test (circular oracle).

### PLANNING-13: a start item with price 0 (or no `start_price`) silently turns restart off   [CONFIRMED] [impact: medium]
- Where: `cli/_plan.py:325` (`if price_of_start.chaos > 0:` the `restart` offer), `:228-229` ("A target without `start_price` counts its start item as free"); `cli/_route.py:246-252` (a given route refuses `restart` for a 0 price and says why).
- What it does: free start -> no way to buy again -> bricked states are dead ends. The report line says only "the start item counts as free".
- Evidence: `make_plan(R13, start_price=0.0)` raises "no policy of the offered actions reaches the goal from the start item"; for a target that can reach the goal without bricking (no failing step) the mean omits all repurchase cost though the start is "free" (R03, R06, J01 have no `start_price`).
- Impact: R03/R06/J01 plans (not in the benchmark list) understate the mean whenever a policy could brick; the route page shows a free buy.
- Origin: `3c123fc` (#60 restart), #26.
- Pattern: a placeholder (0) read as meaning ("free" and "cannot be bought again" are different statements).

### PLANNING-14: target readings change what the benchmark measures, and the omitted tails are not on the page   [SUSPECTED] [impact: medium]
- Where: `examples/targets/r10-fractured-boots.yaml` (Life `min_tier: 1`; the guide says "preferably at least 70"; `r10-fractured-boots-70-life.yaml` reads it but is not in `BENCHMARKS`); `r04-penetrating-quiver.yaml` and `r14-hunter-bow.yaml` (the guide's "two Exalted Orbs guarantee Life and Bow damage" is a 100% step; at the owner's top tiers it is 13% and 20% (R04), 55% and 10% (R14), `_benchmark.py:172-233`); omitted tails: R04 step 9 (remove the metamod, craft a suffix), R11 step 2 (finish craft) and the two Eldritch implicits, R05's 20% catalyst (ticket #159 open), R12/R10/R11 levels invented ("guide gives none").
- What it does: the benchmark's "R04 mean" is the cost of a harder item than the guide's route makes; the benchmark records the mismatch (good) but the owner-facing page of such a route shows no sign that the guide's own final steps are not priced.
- Evidence: the target comments; `tests/test_cli_r04_r14_real.py` pinned rows.
- Impact: the comparison "our route vs the guide's cost" mixes target reading with route quality; unmeasured.
- Origin: #60/#70/#71, owner tier rule.
- Pattern: a reading choice (documented in a YAML comment) not carried to the page.

### PLANNING-15: the default `--budget` of 60 s decides the product question "exact or approximate with an interval", and `--route` silently switches recipe starts off   [CONFIRMED] [impact: low]
- Where: `cli/_decide.py:47` (`BUDGET_SECONDS = 60.0`), `cli/_main.py:114-115,132-133` ("Route view not written: it is not built for an approximate answer yet"), `cli/_main.py:108-113` (`recipe_starts=config.recipe_starts and not args.no_recipe_starts and not args.route`); `tests/test_cli_r04_r14_real.py::test_the_default_run_is_refused_with_the_reason`.
- What it does: a plan forecast above a minute is answered "within a certified 1%" and gets no route page; R04/R14 are refused outright by default. The owner's note: "approximate with an interval reads to him as useless". `--route` changes which start items are compared with no message.
- Impact: for the harder routes the default invocation yields no page; `--exact` is the only way to see one.
- Origin: #81 Q2, ADR-0023, ADR-0059.
- Pattern: a performance default that decides a product question.

### PLANNING-16: the bench tier placeholder is copied by hand into two more places   [CONFIRMED] [impact: low]
- Where: `targets/floor.py` `BENCH_TIER = 1  # actions.bench.CRAFTED_TIER: a crafted mod counts as tier 1 ... whatever its range` (the item-level floor is derived as if a bench craft meets any tier limit); `cli/_benchmark_outcomes.py:52` (`rolled()` builds every held mod with tier `1`).
- Evidence: the two lines; both repeat the seed's `actions/bench.py:57 CRAFTED_TIER = 1` instead of reading it, so fixing the seed in `bench.py` leaves the floor and the benchmark items on the old meaning. `r05-strength-ring.yaml` even documents "a bench craft counts as tier 1 of what it crafts whatever its range" as the reading.
- Impact: low alone; it is why the seed will not be fully fixed by one edit.
- Origin: `d7cf1b0` (#352), `d2432f4` (#70).
- Pattern: a type placeholder read as game meaning, copied by hand.

### PLANNING-17: the benchmark and the CLI plan the same target through different entry points   [SUSPECTED] [impact: low]
- Where: `cli/_benchmark.py:380` (`make_plan` unless the route has an `ExpectedStart`, then `plan_with_starts` with default arguments) against `cli/_main.py:109` (`plan_with_starts` with `config.recipe_starts`, `price_source`, ...).
- What it does: if a vendor-recipe start ever wins for a benchmark target, the page the owner opens (CLI) and the benchmark entry (plain start) are different plans. Today R12 chooses the plain start (`r12.py`: "chosen: the target's own start item ... 56.63 Chaos"); R13/R10/R11 have no matching recipe.
- Impact: none observed; a future divergence the benchmark would not show.
- Origin: `bae8e7c`/#331.
- Pattern: two paths to one answer.

---

## Checked and found sound (so nobody re-checks)

- Equal-kernel merge (`_prune.keyed_offers`): keys are the outcome distribution at the state, restart is never merged, ties go to the earlier offer; the cheaper of equal futures is kept. Sound as documented. The only visible effect is which essence tier/set is named on the page.
- Corrupting prune (`corrupting_offer_pruned`): only for a target that asks a corrupted implicit and only for actions that corrupt and keep mods from states that do not meet the other requirements; a corrupted item is final, so the argument holds.
- `plan_with_starts`: ordering, tie to the earlier (plain wins ties), the "price not below best total" shortcut, per-reading handling, and the recipe-start item (Magic, one mod, lowest roll, dominated steps) are consistent with ADR-0059; the recipe items carry their `approximate` claims into the answer.
- `restart` as an action of every state but the start, priced with the start price, ending in the start state (`_plan.py:325-329`, `_prune.py:75`): consistent with ADR-0011/0061 d7 for a priced start.
- Bound prune (`_bound_prune.py`, 40-offer threshold): a performance threshold with a certificate, falls back to the full set when it cannot close; the dropped offers are reported in text/JSON (`_pruned_left_out`) except the wording issue of PLANNING-5. I did not re-derive the proof.
- The given routes encode the guides step by step (R04 rules map to guide steps 2 to 8 incl. the three "leave 2 slots free" cases of `open_*` as "at least"; R08/R09/R10/R12/R13/R14 likewise); the differences are in what the targets leave out (PLANNING-14), not in the rules.
- The published-odds oracles of R12 (2.88%, 1.338%) and the R04/R14 outcome rows (25%, 33%, 50%) come from the guides and are independent of the code; they are the one real check in the benchmark.

---

## Patterns seen in this area

1. **A limit that is applied but not said, or said where the owner does not read.** The default offer set (PLANNING-1), the unbuilt Scouring/Alchemy (PLANNING-2), the `actions:` lists, unpriced drops and pruning in the text report only (PLANNING-3, PLANNING-4), model gaps shown as game refusals (PLANNING-5).
2. **A setting, key or ADR decision written before the thing it controls exists.** `price_source`/`price_gap_percent` (PLANNING-6), `max_imprints`, `recombinator_junk_craft`, `memory_strands` (PLANNING-7), the item-level floor (PLANNING-8). The docs and flags read as live behaviour.
3. **One fact written by hand in two places, with nothing reconciling them.** Target start item against buy spec against price-file name (PLANNING-10), the start mod tier (PLANNING-11), the bench tier (PLANNING-16), the pinned test rows that repeat the odds (PLANNING-12e).
4. **A placeholder drawn as meaning.** The empty Rare start of R08/R09 (PLANNING-9), the free start with no restart (PLANNING-13), tier 1 for any crafted or benchmark mod (PLANNING-16).
5. **A check whose two sides share the code under test.** The solver-versus-given-route rule and the golden pages (PLANNING-12): it can only fail when the solver is wrong, never when the model is.
6. **A performance choice that decides a product question.** The 60 s budget, the state-space-driven `actions:` lists, Alchemy and Scouring withheld for graph size (PLANNING-1, 2, 15).
