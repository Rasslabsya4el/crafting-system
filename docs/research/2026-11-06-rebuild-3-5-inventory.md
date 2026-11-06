# Rebuild steps 3 and 5: the fact base (audit #396)

Date: 2026-11-06. Read-only inventory of `main` at `7c9e8df`, game data repoe-fork 3.29.3.3. It lists facts for the design of rebuild step 3 ("mod origin and 'no value' in the item model") and step 5 ("an answer envelope") of `docs/research/2026-11-02-codebase-audit.md`, classes 1 and 4. It decides nothing and changes no code.

## How it was made, and what it did not do

- The files the brief names were read from the first line to the last: `src/crafting_system/items/model.py` (lines 1 to 400, and every flag and tier line after it by search), `actions/bench.py`, `targets/model.py`, `targets/floor.py`, `cli/_plan.py`, `cli/_offers.py`, `cli/_report.py`, `cli/_marking.py`, `cli/_decide.py`, `cli/_main.py`, `cli/_reach.py` (top), and `tests/golden/reachability.md`. The route page (`cli/_route_view.py`) was read from line 100 to the end. `abstraction/_estimate.py` was read from line 1 to 290 and around lines 323-347 and 408-420.
- `risk/` (16 files), `solver/` (19 files), `simulator/` (5 files), `abstraction/_coarse.py`, `_estimate.py` and `_inputs.py` (10,246 lines in all) were scanned for every module constant, every `raise`, every `except`, and the words "cap", "limit", "gives up", "falls back", "refuse", "unresolved"; each hit was read in its context. The algorithms of these files were not read line by line, and the list of limits in 5.4 and 5.5 is only as complete as that scan.
- The rest of `src/` (198 files, 47,739 lines) and `tests/` were searched with complete patterns, not read line by line; the files that a search pointed to were read around the hit. The patterns are named at each list, so a reader can run them again. `ExplicitMod(`, `.crafted`, `fractured`, `tiers.get(`, `tier_table`, `OutOfScopeError`, `except ... ActionError`, `start_price`, `get_rule`, `Item.build(`, and every key of the 14 target files were each searched over all of `src/` and `tests/`. Where the brief asked for "read in full" and a list rests on a search, the list says so.
- Counts of leaves per target in section 3.7 were computed once with a read-only script against the cached 3.29.3.3 export (`tier_table`, `catalog(..., names={"bench-craft", "essence"})`). They say what the data and the catalog hold. They are not planner results, and no plan was solved.
- Numbers quoted from the audit are marked "audit" and were not measured again here, except where a line says "re-counted".
- Every file count states its pattern. The ones in Part C are collected in the table "Counts and the pattern behind them" at the end of that part; they were taken once with a script over `src/**/*.py` and `tests/**/*.py` after the merge of `main` at `7c9e8df`.
- Surfaces of the answer are abbreviated: **T** the text report (`render_text`), **J** the JSON policy (`policy_document`), **P** the route page (`write_route_page`), **E** the one `Error:` line on stderr (`cli/_main.py:171-173`).
- Rules cited: `OR-n` of `docs/owner-rules.md`. Issues: the contradiction issues #403 to #410, #415 to #418, #423, #425 to #429 (all open), and #411, #412, #414, #419 (closed) that they came from.

## Counts at a glance

| List | Rows |
|---|---|
| 3.1 Origin of a mod: stored | 11 |
| 3.1 Origin: decided (writers) | 21 |
| 3.1 Origin: read downstream | 26 |
| 3.1 Origin: lost | 8 |
| 3.2 Default tiers in `src/` (constants 4, fallbacks and literals 20, defaults on the target side 4) | 28 |
| 3.2 Places that derive a tier and refuse, skip or raise (not defaults) | 4 |
| 3.2 Default tiers in `tests/` (helper sites) | 35 |
| 3.3 Start items the code or a target file makes up | 13 |
| 3.4 Places where a price of 0 or no price means free or no restart | 20 |
| 3.5 Claims whose "approximate" lives only in their text | 15 |
| 5.1 Gates and constants of the planner entry | 24 |
| 5.2 Offer filters and withheld kinds (code places) | 17 |
| 5.2 Kinds withheld: `planner=False` 28, opt-in 17, needs strands 3, corrupting 1 (opt-in and strands overlap on one kind) | 59 kinds in the catalog; 28 closed by `planner=False`, 20 of the 31 planner kinds withheld by a flag, 11 offered by default |
| 5.3 Unpriced items and price-provenance facts | 17 |
| 5.4 Cuts and bounds of the search (C1 to C17 from the planner entry and the cli, C18 to C35 from `abstraction/_estimate.py`, `risk/`, `solver/`, `simulator/`; C35 is one row of implementation constants) | 35 |
| 5.5 Model gaps: `OutOfScopeError` raise sites | 84 (in 25 files) |
| 5.5 The second refusal family (`EstimateRefused`, `ConvergenceError`, `NoPolicyError`, `BlockHoldsMetamod`, `LevelTimeout`, `BranchingError`, `NotSubcritical`) | 7 |
| 5.5 Model gaps: `except` clauses on `ActionError` or its subclasses | 34 (27 treat both causes alike, 3 catch only the game's refusal, 4 only the model gap) |
| 5.6 Display limits | 9 |
| 5.7 Settings accepted and never read | 5 (of 24) |

### Owner rules the lists are measured against

| Rule | What it asks | Lists that bear on it |
|---|---|---|
| OR-1 | an unstated tier is the top tier the item level allows, rolled | 3.1 (C rows), 3.2 (T1 to T4, T24 to T26), 3.7 |
| OR-2 | a mod forced by an essence or a bench craft is exactly that mod | 3.2 (T7, T8, T23), 3.7 |
| OR-3 | the target, the buy spec and the price agree on the start item | 3.2 (T27), 3.3, 3.4 |
| OR-4 | the guide's own wording wins | 3.7 (targets with `min_tier: 1` for a "soft wish") |
| OR-5 | a target never restricts the actions; the answer shows a user's setting | 5.2 (K1, K4) |
| OR-6 | a start item is given or bought; how it was acquired is not modelled | 3.3 (I1 to I5) |
| OR-7, OR-8 | trade price: instant buyout only, mean of the cheapest few, a marked fallback may stand in | 5.3 |
| OR-10 | detail that no later decision reads is not tracked | 3.3 (I5: a bought item holds one mod only), 5.4 (C26) |
| OR-11 | the answer is exact among realistic routes, never an interval | 5.1 (G12, G22), 5.4 (C17, C20, C21, C28) |
| OR-12 | no hard-coded cut-offs; a fixed rail is a stop-and-say-so safety net | every constant of 5.4 (C1 to C35) and 5.1 (G14 to G16, G19, G20) |
| OR-13 | every cut says what it still guarantees | 5.1, 5.2 (K16, K17), 5.4, 5.5 |
| OR-15, OR-16, OR-17, OR-18 | one mod format; every in-game step shown; the bought item's other mods shown; one page step is one player step | 3.1 (D15 to D18), 3.3 (I3), 5.6 |
| OR-23 | an unknown gets the best estimate, marked approximate | 3.5, 5.2 (K12) |

## Part A. Step 3: mod origin and "no value"

### 3.0 What the type holds today

`ExplicitMod` (`items/model.py:103-116`) has five fields: `mod_id`, `tier`, `values`, `fractured`, `crafted`. There is no field for any other origin. Three further facts shape everything below:

- `tier` is "stored as given" (`items/model.py:23-24`). `Item.__post_init__` only checks that it is an integer of 1 or more (`items/model.py:209-214`). Nothing, at construction or in `Item.validate`, compares it with `tier_table`.
- `crafted` is stored twice. `Item.validate` requires `entry.crafted == (mod.domain == "crafted")` (`items/model.py:358-361`), so the flag always equals a fact of the game data.
- Every other origin is a fact of the data and not of the item: essence-only is `Mod.is_essence_only` (`data/model.py:51`, read from the export at `data/normalize.py:174`), veiled and unveiled are `Mod.domain` (`items/model.py:157-158`), Elevated is the word in the mod's name (`data/elevated.py:42-44`), an influence mod is a spawn weight on an influence tag (`actions/pool.py:118`, `influence_spawn_test`).
- An implicit keeps its origin in a number, `ImplicitMod.grade` (`items/implicits.py:63-72`): 0 for a base implicit, 1 (Lesser) to 6 (Perfect) for an Eldritch one. It has defaults too: a target's implicit with no grade gets `BASE_GRADE` unless the mod is Eldritch (`targets/parse.py:1135,1137`), and the state turns a base implicit back into an item at grade 0 (`abstraction/_kernel.py:1185`). Implicits are out of the planner until ticket #159 (gate G2); they are listed here only so that step 3 does not forget them.

`Requirement` (`targets/model.py:25-63`) judges a mod with `mod_id in mod_ids`, `mod.tier > min_tier`, `not_crafted and mod.crafted`, then `min_roll` (lines 52-63). The planner has a second copy of the same judgement, `status_of` (`abstraction/_state.py:269-289`), called from `abstraction/_kernel.py:811` (for a mod of a concrete item, with `entry.tier`), `abstraction/_kernel.py:960` (for a mod an action draws, with the table tier) and `abstraction/_rolls.py:124` (for the roll law). The goal oracle (`tests/oracle/goal_oracle.py`) is a third, independent copy; it reads the natural ladder from `tests/independent/ladder.py`. No test compares that ladder with `items/tiers.py` (`tests/independent/test_ladder_agreement.py` compares the oracle's and the reconcile package's former copies only).

### 3.1 The origin of a mod: stored, decided, read, lost

Search patterns: `ExplicitMod\(`, `\.crafted\b`, `crafted=`, `\.fractured\b`, `fractured=`, `is_essence_only`, `domain (==|!=|in)`, `is_elevated`, `CRAFTED_TIER|ELEVATED_TIER|BENCH_TIER`. Origin letters: R rolled, C bench-crafted, B beast-crafted, E essence-forced, F fractured, V veiled or unveiled, L Elevated.

**Stored (11).**

| ID | Place | Origin | What is stored |
|---|---|---|---|
| S1 | `items/model.py:115` | F | `ExplicitMod.fractured: bool`; a crafted mod can be fractured too (docstring 107-110) |
| S2 | `items/model.py:116` | C | `ExplicitMod.crafted: bool`, checked equal to the domain at `:358-361` |
| S3 | `items/model.py:113` | all | `ExplicitMod.tier: int`, unchecked against the data (`:209-214`) |
| S4 | `items/model.py:154-160` | C, V | `EXPLICIT_EXTRA_DOMAINS = {crafted, delve, veiled, unveiled}`: the domain is the only record that a mod is veiled, unveiled or crafted |
| S5 | `items/model.py:186` | V | `Item.veil_offer`, the three mods offered by one unveil |
| S6 | `data/model.py:51` | E | `Mod.is_essence_only` (export fact, no item field) |
| S7 | `data/elevated.py:44` | L | `is_elevated(mod)`: the word "Elevated" in the name; the mapping to the base mod is `elevated.json` (`actions/influence.py:303-304`) |
| S8 | `actions/contract.py:330,408,422` | C | `Adds.crafted` and `Adds.keeps_crafted`: an action declares that what it adds is crafted, and whether it keeps crafted mods |
| S9 | `abstraction/_state.py:73` | C | `Slot.crafted`: the state keeps the flag; a crafted slot's `kind` is the canonical mod id |
| S10 | `abstraction/_state.py:36-44` | F | `FracturedMod(mod_id, contribution)`: a fractured mod keeps its canonical id and what it gives each leaf, not its tier |
| S11 | `targets/model.py:40` | C | `Requirement.not_crafted`, the only target-side origin switch (the opposite of S2) |

**Decided: where a writer sets an origin or a tier for a new mod (21).**

| ID | Place | Origin | Tier written |
|---|---|---|---|
| W1 | `actions/bench.py:120` (`BenchOutcomes.components`) | C | `CRAFTED_TIER = 1` (`:57`) |
| W2 | `actions/bench.py:156` (`BenchOutcomes.sample`) | C | `CRAFTED_TIER`, rolled values |
| W3 | `actions/beast_mods.py:145` (Wild Bristle Matron) | C | `CRAFTED_TIER` imported from `bench.py:22` |
| W4 | `actions/beasts.py:239` (aspect craft) | B | `CRAFTED_TIER = 1` of its own (`beasts.py:59`), `crafted=False` |
| W5 | `actions/outcomes.py:77-79` (`retained_item`, forced essence mod) | E | `tier_table(...).get(forced.id, 1)`; comment "an essence-only mod has no tier: 1" |
| W6 | `actions/outcomes.py:267-275` (`Outcomes.sample`) | E | `self._tiers.get(mod.id, 1)` for the forced mod only |
| W7 | `actions/veiled.py:444` (pick) | V | `tier_table(...).get(chosen.id, 1)`; keeps `fractured` of the placeholder |
| W8 | `items/model.py:163-171` (`veiled_placeholder`) | V | tier 1, "a veiled mod has no spawn weight" |
| W9 | `targets/parse.py:1072-1073` (start item, veiled) | V | `placeholder.tier` (1) unless `tier:` is written |
| W10 | `actions/influence.py:315` (Dominance on an Elevated mod) | L | `ELEVATED_TIER = 1` (`:114`) |
| W11 | `actions/influence.py:336` (Dominance, top-tier mod) | L | `ELEVATED_TIER` |
| W12 | `actions/awakener.py:191` (donor's mod) | R | `tiers_of(...).get(mod.id, 1)` |
| W13 | `actions/beast_mods.py:240` (side swap, added mod) | R | `tiers.get(entry.mod.id, 1)` |
| W14 | `actions/harvest_augment.py:175` (Harvest add) | R | `tiers.get(mod.id, 1)` |
| W15 | `actions/recombinator.py:528` (`_complement` junk donor) | R | `tiers.get(mod_id, 1)` |
| W16 | `abstraction/_kernel.py:385` (`crafted_slot`) | C | tier 1 literal |
| W17 | `abstraction/_kernel.py:1142` (state to item, crafted slot) | C | `tiers.get(mod.id, 1)` |
| W18 | `abstraction/_kernel.py:1125` and `:1127-1128` (state to item, fractured) | F | `tiers.get(entry.mod_id, 1)`, `crafted` from the domain |
| W19 | `cli/_benchmark_outcomes.py:52` (published-odds items) | F, C | tier 1 literal, flags from the row |
| W20 | `targets/parse.py:1066-1088` (start mod) | F, C | `tier:` is a required hand-written key (`:1067`, `:1075`); `fractured:` and `crafted:` optional (`:1082-1087`) |
| W21 | `actions/fracture.py:103`, `actions/beasts.py:167`, `actions/mixture.py:88` | F | set `fractured=True` on an existing mod (Fracturing Orb, Talisman, Fractured Fossil); tier and crafted flag are kept |

**Read downstream (22).** What each reader does with the origin or the tier.

| ID | Place | Reads | Effect |
|---|---|---|---|
| D1 | `targets/model.py:55-58` | tier, crafted | goal check of a concrete item: tier worse than `min_tier` fails; `not_crafted` rejects a crafted mod |
| D2 | `abstraction/_state.py:280-282` (`status_of`) | tier, crafted | the same judgement for the state's three callers (`_kernel.py:811,960`, `_rolls.py:124`) |
| D3 | `abstraction/_kernel.py:958,973` | table tier, default 1 | what a drawn, forced or crafted mod gives each leaf; the roll law |
| D4 | `abstraction/_kernel.py:1583` | table tier, default 1 | canonical id of a fractured mod |
| D5 | `abstraction/_kernel.py:1032-1038,1090` | crafted | slot identity, canonical id; a crafted mod is never held as a family type |
| D6 | `abstraction/_kernel.py:1410-1434,1859-1880` | fractured, crafted | origin maps `(mod_id, fractured, crafted)` that tie a kept mod to its slot; Divine Orb refuses a crafted mod under a roll limit |
| D7 | `abstraction/_coarse.py:321-361,390-406,433-479,550-559` | `Slot.crafted` | crafted mods are never pooled in a coarse level |
| D8 | `abstraction/_estimate.py:129,201,212,271,311`; `abstraction/_inputs.py:131,146` | `Slot.crafted` | forecast keys and input placements keep crafted slots apart |
| D9 | `targets/floor.py:201-204,227-230,252` | crafted, forced, tier | the item-level floor: a bench mod counts as `BENCH_TIER = 1` (`:57`); a forced mod as its table tier or 1; start mods that are not crafted set a floor. Nothing calls `floor_of` (`tests/golden/reachability.md:191-199`) |
| D10 | `cli/_offers.py:242,254,389-392,398` | `not_crafted`, `Adds.crafted` | `counting` = every mod of a leaf that is not `not_crafted`: a bench craft is offered only when its mod is in `counting`; `usable_actions` keeps Remove Crafted Mods when a craft exists |
| D11 | `actions/bench.py:239,292-294`; `actions/beast_mods.py:127`; `actions/metamods.py` (`crafted_limit`) | crafted | crafted-mod limit, what Remove Crafted Mods removes |
| D12 | `actions/divine.py:112,165-167`; `actions/finite.py:75-80`; `actions/harvest_augment.py:243` | fractured, crafted | which mods a reroll or swap may change |
| D13 | `actions/annul.py:88`; `actions/awakener.py:253`; `actions/eldritch.py:358,448`; `actions/veiled.py:276`; `actions/metamods.py:99` | fractured | fractured mods are kept or refused |
| D14 | `actions/recombinator.py:253,406-408,428` | tier, crafted, fractured, essence-only | state key string; "exclusive" mod (crafted, essence-only, delve) drawn as weight 1000 |
| D15 | `cli/_benchmark_outcomes.py:49-75` | all | published odds computed on a made-up rare item |
| D16 | `cli/_report.py:121-127` | `Slot.crafted` | text: "crafted <mod text>" |
| D17 | `cli/_route_card.py:188,278,314-320,494-520` | crafted, fractured, essence-only, veiled, influence | page: marks "fractured", "crafted", "essence only", "veiled", "influence"; tier note `T<n>` from `tier_table`, or "crafted", or "essence only" |
| D18 | `cli/_route_view.py:259,284-288,404-407` | `Slot.crafted` | page: "crafted" gains, "Benchcraft:" titles |
| D19 | `cli/_route.py:15,81-90,293` | state crafted | a given route's `when: crafted_mods` key |
| D20 | `cli/_verify.py:59` | fractured, crafted | the simulator's key of a concrete item |
| D21 | `prices/trade_query.py:238,311`, `prices/trade_pricing.py:246`, `prices/trade_stats.py:171` | buy-side `BuyMod.fractured` | the trade search for a fractured start item; a second, separate record of "fractured" |
| D22 | `items/model.py:287-295` | fractured, crafted | the `fractured_mods` and `crafted_mods` properties |
| D23 | `abstraction/_kinds.py:227-228,432,444` | domain (unveiled, veiled) | a mod of the unveiled domain gets its own kind (`UNVEILED_PREFIX`), told apart from ordinary mods of its family; the representative of a class is chosen among the base's domain plus the extra domains, a signature placeholder after the generic one |
| D24 | `items/veiled.py:45,52,64,72,81` | domain (veiled, unveiled, crafted) | which families are veiled; the crafted bench mod of Jun that is the "craftable version" of an unveiled mod is found by its id prefix and its stat signature (`is_craftable_version`, `is_veiled_mod`): an origin derived from a pattern in the data |
| D25 | `items/model.py:483,495,626` | domain (veiled, unveiled) | the veil-offer checks: exactly one placeholder; an offered mod must be of the unveiled domain; `has_veiled` |
| D26 | `cli/_route_trade.py:89` | buy-side `BuyMod.fractured` | the trade-link line "fractured: <mod>" (second reader of the record of D21) |

**Lost (8).**

| ID | Place | What is lost |
|---|---|---|
| X1 | `abstraction/_kernel.py:1034` (`_slot_of`) | an essence-forced, Elevated, veiled-picked, aspect or Harvest-added mod becomes an ordinary `Slot(side, kind, contribution)`; only `crafted` survives |
| X2 | `abstraction/_kernel.py:809-813` (`_contribution`) | the contribution is fixed once from `entry.tier` and `entry.values`; the tier is not in the state |
| X3 | `abstraction/_kernel.py:1090-1094` | a fractured mod held as a family type (`"~n"`) keeps no mod id and no tier |
| X4 | `abstraction/_kernel.py:1096-1174` (`_item_of`) | a state turns back into an item with `tiers.get(mod.id, 1)` and low values (`:1125,1142,1151,1158`): the item is a representative, with the table tier, whatever the state came from |
| X5 | `actions/outcomes.py:79` (`retained_item`) | the forced mod enters the kept mods as an ordinary mod, tier from W5 |
| X6 | `items/model.py:304-320` (`Item.canonical`) | the veiled seed is set to its minimum |
| X7 | `abstraction/_state.py:36-44` | `FracturedMod` has no `crafted` flag; `_kernel.py:1121` re-derives it from the domain |
| X8 | `cli/_route_card.py:278,316-320` | the page re-derives "crafted"/"essence only"/"veiled" from the data, not from the state; "Elevated" and "aspect" have no mark |

Tests that pin origin and tier behaviour, by origin:

- **C, bench craft stored as tier 1 and meeting a leaf with no `not_crafted`**: `tests/test_targets_goal.py:62-70` (a crafted hybrid meets the roll limit by values), `:138-147` (`not_crafted` rejects a crafted mod; without it the crafted mod counts), `:210-225` (R13's crafted damage mod meets the belt target); `tests/test_targets_floor.py:98-106` and `tests/test_targets_floor_real.py:73` (BENCH_TIER in the floor); `tests/test_cli_offers.py:63-92,159,223-226` (`counting`); `tests/test_offers_wanted_only.py`; `tests/test_crafted_slot.py`; `tests/test_actions_bench.py`, `tests/test_actions_bench_real.py`; `tests/test_actions_beast_mods.py:87` (crafted, tier 1). `crafted=True` appears on 233 lines of 57 test `.py` files (the 776 matches of `grep -r` in `tests/` include 543 in the repr text of `tests/golden/plans_118.json`).
- **Strict xfails that name the disagreement**: `tests/test_goal_oracle_comparison.py:67-81` (12 classes of probes, issues #403 and #415, plus `UNMEETABLE` at `:145` for R13's All Damage), `tests/reconcile/known.py:71-72` (R12's start mod tier).
- **B, aspect tier 1, not crafted**: `tests/test_actions_beasts_aspects.py:87`.
- **L, Elevated tier 1**: `tests/test_actions_dominance.py:119`; `tests/test_abstraction_dominance.py`, `tests/test_abstraction_dominance_real.py`.
- **V, veiled placeholder and pick**: `tests/test_targets_start_item_b2.py:235` (placeholder tier 1), `tests/test_actions_veiled.py:164`, `tests/test_actions_veiled_real.py:170` (pick tier `.get(..., 1)`).
- **E, essence tier**: `tests/test_targets_floor.py:119,133` ("forced mod" source at level 1); `tests/test_cli_routes_real.py:224-242` (uses `tiers.get(m, 1)` itself at `:239`, and skips essence-only leaves).
- **F, fractured**: `tests/test_targets_goal.py:149-153` (a fractured mod meets `not_crafted`), `tests/test_actions_fracture.py`, `tests/test_actions_harvest_swap.py:505`.

### 3.2 Default tiers

A default tier is a tier number that did not come from `tier_table` for that mod on that base. Search: `tiers?\.get\(.*, 1\)`, `CRAFTED_TIER|ELEVATED_TIER|BENCH_TIER`, `ExplicitMod\(` with a literal `1`, and every use of `min_tier`.

**In `src/` (27).**

| ID | Place | Kind | Value | Used for |
|---|---|---|---|---|
| T1 | `actions/bench.py:57` | constant | 1 | bench crafts (W1, W2, W3) |
| T2 | `actions/beasts.py:59` | constant | 1 | aspect mods (W4) |
| T3 | `actions/influence.py:114` | constant | 1 | Elevated mods (W10, W11) |
| T4 | `targets/floor.py:57` | constant | 1 | `BENCH_TIER`, "a crafted mod counts as tier 1 of what it crafts, whatever its range" (D9) |
| T5 | `items/model.py:171` | literal | 1 | veiled placeholder |
| T6 | `targets/parse.py:1073` | fallback | placeholder's 1 | veiled start mod with no `tier:` (`veiled_placeholder`, T5) |
| T7 | `actions/outcomes.py:77` | fallback | `.get(forced.id, 1)` | forced essence mod in `retained_item` |
| T8 | `actions/outcomes.py:272` | fallback | `.get(mod.id, 1)` | forced mod in `Outcomes.sample` |
| T9 | `actions/veiled.py:444` | fallback | `.get(chosen.id, 1)` | unveiled pick |
| T10 | `actions/awakener.py:191` | fallback | `.get(mod.id, 1)` | donor mod |
| T11 | `actions/beast_mods.py:240` | fallback | `.get(entry.mod.id, 1)` | side-swap added mod |
| T12 | `actions/harvest_augment.py:175` | fallback | `.get(mod.id, 1)` | Harvest add |
| T13 | `actions/recombinator.py:528` | fallback | `.get(mod_id, 1)` | junk-craft donor |
| T14 | `abstraction/_kernel.py:385` | literal | 1 | `crafted_slot` |
| T15 | `abstraction/_kernel.py:958` | fallback | `tiers.get(mod.id, 1)` | `_drawn_contribution`: every drawn, forced or crafted mod |
| T16 | `abstraction/_kernel.py:973` | fallback | `tiers.get(mod.id, 1)` | `_law`, the roll law |
| T17 | `abstraction/_kernel.py:1125` | fallback | `tiers.get(entry.mod_id, 1)` | state to item, fractured |
| T18 | `abstraction/_kernel.py:1142` | fallback | `tiers.get(mod.id, 1)` | state to item, crafted |
| T19 | `abstraction/_kernel.py:1151` | fallback | `tiers.get(mod.id, 1)` | state to item, fractured family type |
| T20 | `abstraction/_kernel.py:1158` | fallback | `tiers.get(mod.id, 1)` | state to item, ordinary slot |
| T21 | `abstraction/_kernel.py:1583` | fallback | `tiers.get(mod.id, 1)` | `_canonical_of_mod` |
| T22 | `cli/_benchmark_outcomes.py:52` | literal | 1 | published-odds item |
| T23 | `targets/floor.py:229` | fallback | `tier if tier is not None else 1` | forced mod in the floor |
| T24 | `targets/model.py:38` | default | `min_tier = None` | "any tier": a leaf with no `min_tier` accepts every tier (`_counts` `:55`); parse default `targets/parse.py:415` |
| T25 | `abstraction/_goal.py:27,178` | default | `min_tier = None` | `Wanted` copies T24 |
| T26 | `targets/model.py:296` | default | `tiers_top_at_item_level = False` | the owner's "top tier" is an opt-in key of a target (`parse.py:226,244-248`); set in 11 of 14 targets (not J01, R08, R13) |
| T27 | `targets/parse.py:1067,1075` | required hand value | `tier:` | start mods carry a hand-written tier (6 start mods in 6 files; R12's is 3 where the data says 7, `tests/reconcile/known.py:71`) |
| T28 | `abstraction/_kernel.py:428-430` | fallback | `tier_table(data, base_id)` | when `tiers_of(probe)` raises `OutOfScopeError` (an item class with no influence key), the tiers of an influenced item are the base's, without the influence mods; the comment says every action that draws raises on such an item |

Places that derive a tier and refuse, skip or raise when there is none (the pattern the fallbacks above do not follow). They are not defaults and are not counted in T1 to T28:

| ID | Place | What happens with no tier |
|---|---|---|
| R1 | `items/tiers.py:66-77` (`mod_tier`, exported at `items/__init__.py:72,140`) | raises `TierError` ("it cannot spawn there"), `UnknownModError`, `UnknownBaseError`. Production code does not call it; 3 test files name it (`tests/test_items_tiers.py`, `tests/test_targets_files.py`, `tests/reconcile/test_reconcile_real.py`) |
| R2 | `actions/influence.py:316-317` | Orb of Dominance: a mod with no tier on the item raises `OutOfScopeError` ("its upgrade is not modelled"); `tests/test_actions_dominance.py:223-225` pins it |
| R3 | `actions/harvest_augment.py:245-247` | a swap skips a mod that is not in `tiers` (`entry.mod_id not in tiers`) |
| R4 | `cli/_start_options.py:205-207` | reads `tier_table(...).get(step.mod_id)` and, on `None`, refuses the recipe step with `MOD_CANNOT_SPAWN` (`cli/_start_types.py:27`) |

Re-count against the audit's "14 sites in `src`, 4 separate constants": four constants (T1 to T4); 20 places that write or fall back to a tier of 1 or to another table without the table of the mod (T5 to T23 and T28, in 11 files: `items/model.py`, `targets/parse.py`, `actions/outcomes.py`, `veiled.py`, `awakener.py`, `beast_mods.py`, `harvest_augment.py`, `recombinator.py`, `abstraction/_kernel.py`, `cli/_benchmark_outcomes.py`, `targets/floor.py`); and four defaults on the target side (T24 to T27). Tier numbers produced by `tiers_of` (`actions/pool.py:145`) and `tier_table` are derived, not defaults. The fallbacks of the form `.get(x, 1)` in T10 to T13 are not expected to fire, because the mod is taken from the pool the table is built from; this was not proved here and no test asserts it.

**In `tests/` (35 helper sites).** Test helpers that build a mod with tier 1 or `.get(mod_id, 1)`:

- Literal tier 1 (21): `tests/abstraction_oracle.py:148`, `tests/eldritch_support.py:162`, `tests/implicits_support.py:133`, `tests/test_abstraction_b1_real.py:33`, `tests/test_abstraction_implicit_rolls.py:197`, `tests/test_abstraction_recombinator.py:272`, `tests/test_abstraction_veiled.py:77`, `tests/test_actions_awakener_real.py:32`, `tests/test_actions_beasts_real.py:44`, `tests/test_actions_beast_mods_real.py:38`, `tests/test_actions_eldritch_real.py:75`, `tests/test_actions_essence_real.py:52`, `tests/test_actions_fossil.py:252`, `tests/test_actions_harvest_locked_real.py:62`, `tests/test_actions_harvest_reforges.py:280`, `tests/test_actions_metamods_real.py:51`, `tests/test_actions_metamods_reforges.py:47`, `tests/test_actions_rare_orbs_real.py:44`, `tests/test_actions_recombinator.py:80`, `tests/test_actions_veiled_real.py:50`, `tests/test_crafted_slot.py:75`.
- `.get(mod_id, 1)` (11): `tests/abstraction_adds_oracle.py:36`, `tests/abstraction_b2_support.py:44`, `tests/abstraction_oracle.py:142`, `tests/abstraction_veiled_support.py:74`, `tests/coarse_support.py:185`, `tests/contract_support.py:317`, `tests/recombinator_state_support.py:62`, `tests/test_abstraction_awakener.py:104`, `tests/test_abstraction_b2_real.py:79`, `tests/test_abstraction_beasts.py:51`, `tests/test_coe_emulator_record.py:64`.
- Parameter default `tier: int = 1` (3): `tests/items_support.py:13`, `tests/beasts_support.py:71`, `tests/beast_mods_support.py:60`.

The layer-1 oracles `tests/abstraction_oracle.py:142,148` and `tests/abstraction_adds_oracle.py:36` use the same fallback as `_kernel.py:958`. `tests/test_cli_routes_real.py:239` (the test #403 says passes at any `min_tier`) also uses `tiers.get(m, 1)`.

Which tests pin the constants: none imports `CRAFTED_TIER`, `ELEVATED_TIER` or `BENCH_TIER`; they pin the number through behaviour (list under 3.1). Which benchmark targets the defaults change is in 3.7.

### 3.3 Start items the code or a target file makes up

Search: every `Item.build(` and `Item(` in `src/` (19 sites), `start_item` in the 14 target files, `read_rarity`.

| ID | Place | What is made up | Benchmark targets | Issue |
|---|---|---|---|---|
| I1 | `targets/parse.py:954` | no `start_item:` key gives `fields = {"rarity": NORMAL}`: a fresh normal item of the base, item level and influences; its price is the target's `start_price` | R04, R06, R13, R14, V01 (`grep -L "^start_item"`) | #427 (R13, V01: no buy spec; R06: no price) |
| I2 | `targets/parse.py:1047` (`read_rarity`) | rarity defaults to RARE when mods are listed, NORMAL otherwise | R03, R05, R10 x2, R11, R12 (rare with 1 mod) | none |
| I3 | `examples/targets/r08-energy-shield-boots.yaml:45-47`, `r09-life-boots.yaml:40-42` | `start_item: rarity: rare, mods: []`: a rare item with no mod; the bought item is a Normal base and the Orb of Alchemy is folded into the price (comment `r08:36-44`) | R08, R09 | #417 (OR-16); audit TARGETS-9 |
| I4 | `examples/targets/j01-cobalt-life-attack-speed.yaml:18-19` | `start_item: rarity: rare`, no mod, "what you hold after you scour a rare jewel"; no price | J01 | #427 (no price) |
| I5 | `r03-avoid-shock-boots.yaml:87-98`, `r05-strength-ring.yaml:75-86`, `r10-fractured-boots.yaml:70-81`, `r10-fractured-boots-70-life.yaml:74-85`, `r11-reservation-helmet.yaml:69-80`, `r12-lightning-amulet.yaml:43-54` | a rare item that holds exactly one mod, fractured; the bought item's other mods are not tracked (OR-17 draws them "any mod or empty") | R03, R05, R10 x2, R11, R12 | #403 (R12 tier), #417 (R05, R12 base and level) |
| I6 | `targets/parse.py:1006-1007` | a target with `sockets` and no stated sockets gets one white unlinked socket; `Target.start_sockets_assumed` records it and nothing reads it (`tests/golden/reachability.md:223`) | none of the 14 | none |
| I7 | `cli/_start_options.py:167-173` (`_start_item`) | a Magic item holding the one mod of a vendor-recipe step, tier from `tier_table`, low or high roll | V01 (recipe start) | none |
| I8 | `cli/_benchmark_outcomes.py:60` (`item_of`) | a rare item built from the `held` mod ids of a published-odds row (tier 1 literal, W19) | R04 (5 rows) and R14 (6 rows), `cli/_benchmark.py:176-196,219-233` | #404 (wording only) |
| I9 | `actions/awakener.py:184-196` (`_donor`) | a Normal donor of the donor's influence, and the Rare "wanted" item that holds the donor mod alone | none (planner=False) | none |
| I10 | `actions/recombinator.py:338,532-536` (`_complement`) | the item a junk craft starts from; a donor of up to 2 prefixes and 2 suffixes of distinct families | none (planner=False) | none |
| I11 | `abstraction/_kernel.py:1160-1173` (`_item_of`) | a representative concrete item for a state: one mod per slot, distinct families, low values | every planned target | none |
| I12 | `abstraction/_kernel.py:208,424,795,1217,1299`; `abstraction/_kinds.py:217,332,401`; `abstraction/_inputs.py:118`; `abstraction/_coarse.py:129` | an empty rare item of the base, used as a probe of the pool | every planned target | none |
| I13 | `cli/_starts.py:55-57` | an unpriced plain start gets a price of infinity and "fails when planned" | any target whose `start_price` name is not in the price file | none |

Tests: I1 and I2 are pinned by `tests/test_targets_parse.py` and `tests/test_targets_start_item_b2.py` (start item reading); I3 by `tests/test_cli_r08_r09_real.py:76`; I6 by `tests/test_targets_sockets.py:92,100`; I9 and I10 by `tests/test_actions_awakener.py`, `tests/test_actions_recombinator.py`; I12 by every layer-1 abstraction test.

### 3.4 Where a price of 0, or no price, means free or means no restart

Why it is coupled: the solver refuses an action cost that is not above zero (`solver/_model.py:122`, "action cost must be finite and above zero"). So a start price of 0 cannot be offered as the `restart` action (`cli/_plan.py:340`), and an action that consumes nothing is given an epsilon price instead of 0 (`cli/_offers.py:23,128-131`). The price file refuses any price of 0 or less (`prices/price_file.py:92-98`, `is_price`; the overrides loader uses it at `:314`), so 0 can reach the planner only through the places below.

| ID | Place | What 0 or "none" means |
|---|---|---|
| P1 | `cli/_plan.py:243-244` (`resolve_start_price`) | no `start_price` on the target: `StartPrice(None, 0.0, "the target names no start price, so the start item counts as free")` |
| P2 | `cli/_plan.py:239-242` | `--start-price 0` (or any run override) is accepted; "zero or more" |
| P3 | `cli/_plan.py:340-344` | the `restart` offer exists only when `price_of_start.chaos > 0`: a free start item has no restart |
| P4 | `cli/_route.py:253-259` | a given route's `do: restart` is refused when the start price is not above 0 ("which is 0 here; the solver needs every action to cost more than 0") |
| P5 | `cli/_route.py:460` | a restart action in a given route is priced at `plan.start_price.chaos` |
| P6 | `cli/_route_view.py:467` | the page's buy row says "free" when the price is 0 |
| P7 | `cli/_report.py:309` | text: "Start item: 0.00 Chaos [the target names no start price, ...]" |
| P8 | `cli/_benchmark.py:458-459` | `_missing_start_price` returns nothing for a target with no `start_price`: no "missing price" error is possible |
| P9 | `cli/_benchmark.py:466` | the missing-price message tells the owner to write `"<name>" = 0` and then replace the 0 (the loader refuses a 0 left in place) |
| P10 | `cli/_benchmark.py:640` | `start["start_price"] or 0.0`: a missing value prints as 0 |
| P11 | `targets/parse.py:271` | `buys = start_price is not None or start_item.corrupted`: a target with no price counts as "does not buy" in the corruption check |
| P12 | `cli/_offers.py:128-131` | an offer with no resources costs `FREE_ACTION_SHARE` (1e-6) of the cheapest paid offer; recognised later by its value (`risk/_free.py:41-43`, `is_free`; `risk/_evaluate.py:195-198`) |
| P13 | `cli/_starts.py:55-57` | an unpriced start has price `math.inf` (a second sentinel) |
| P14 | `cli/_offers.py:115-116,120-121` | a Chaos Orb is worth 1 whether or not the file lists it (source "fixed"); a Divine Orb is priced from the rate (source "rate") |
| P15 | `cli/_report.py:293,505` | `shift = plan.start_price.chaos`: the start price, 0 for a free item, is added to every total of the text and the JSON |
| P16 | `cli/_route_report.py:31,71` | the same `shift` for a given route's report |
| P17 | `cli/_route_sim.py:72`, `cli/_verify.py:139-141,156` | `start_cost=plan.start_price.chaos` and the p90 `start_price.chaos + risk.p90`: the simulator pays the start price once per run, so a free start item makes a run start at 0 |
| P18 | `cli/_interval.py:345` | `shift = plan.start_price.chaos` for the interval answer |
| P19 | `cli/_starts.py:88` | a vendor-recipe start is planned with `start_price=None` and the price handed in (`start_price_of`), so the "no price means free" branch of P1 is skipped by construction |
| P20 | `risk/_evaluate.py:119-120,472-495` | `FREE_BINS = 0.1`, `FREE_SLACK = 1e-6`: a free state (a cost of 0 bins on the quantile grid) is charged 0.1 bins because the solver needs a positive cost, and the charge is taken off again (`_coarse_means`, `_regen_means`) |

Tests that pin P1 to P7 (P15 to P20 are covered by the same plans, `tests/test_cli_verify_approximate.py:127`, `tests/test_risk_free_actions.py`, `tests/test_risk_free_real.py`): `tests/test_cli_offers.py:129` (a free start item has no restart), `tests/test_cli_route.py:446` (a restart needs a start price above zero), `tests/test_cli_approximate.py:365` and `tests/test_cli_verify_approximate.py:127` (`--start-price 0`), `tests/test_vendor_starts.py:334,502` (`plan.start_price.chaos == 0.0`), `tests/test_cli_benchmark.py:112-144` (missing start price messages). P12: `tests/test_cli_free_actions.py`, `tests/test_risk_free_actions.py`, `tests/test_risk_unchanged_349.py`.

Benchmark targets: J01, R03, R06 have no `start_price` (P1: free, no restart). R03 and R06 are refused before pricing matters (`make_plan` gate G2, section 5.1). J01 is planned from a free rare jewel with no restart. All others carry a price.

Issues: #410 point 4 (the decision "a start price is required"), #427 (J01, R03, R06 priced nowhere; R13, V01 priced with no buy spec), #425, #426 (stand-in prices).

### 3.5 Claims whose "approximate" lives only in their text (15)

`approximate: true` with `approximate_reason` is the only form the report reads: `cli/_marking.py:216-221` skips every claim for which `rule.approximate` is false (`:217`). The 15 below have the word at the start of their statement, or inside it, and no field. Search: `APPROXIMATE|UNVERIFIED|not rechecked` (case-insensitive) in `src/crafting_system/rules/claims/*.yaml`, checked by loading the 606 claims (119 carry the field; 17 text matches without the field, of which 2 are `hinekora_lock.preview_independent_across_currencies` and `hinekora_lock.exalted_annulment_regal_previewed`, whose text says "not approximate").

| ID | Claim | File:line | Marker in text | Read by code | Test | Benchmark targets reaching it |
|---|---|---|---|---|---|---|
| A1 | `awakener.survivor_player_report_2020` | `awakener.yaml:128` | "UNVERIFIED by me" | none | `tests/test_actions_awakener.py:356` lists it in the registry only | none (`awakeners-orb` is `planner=False`) |
| A2 | `harvest_augment.removal_uniform_among_removable` | `harvest_augment.yaml:107` | "APPROXIMATE (ADR-0028)" | `actions/harvest_augment.py:56` | none | none (`harvest-add-remove` is opt-in, offered by no target) |
| A3 | `harvest_augment.addition_weighted_by_tier_weight` | `harvest_augment.yaml:115` | "APPROXIMATE (ADR-0028)" | `harvest_augment.py:57` | none | none |
| A4 | `harvest_swap.damage_source_stats` | `harvest_swap.yaml:47` | "APPROXIMATE (ADR-0028)" | `harvest_augment.py:63` | none | none (swaps are opt-in, offered by no target) |
| A5 | `harvest_swap.uniform_among_sources` | `harvest_swap.yaml:72` | "APPROXIMATE (ADR-0028)" | `harvest_augment.py:66` | none | none |
| A6 | `harvest_swap.respects_side_locks` | `harvest_swap.yaml:88` | marker in the middle of the statement (line 89) | `harvest_augment.py:68` | none | none |
| A7 | `harvest_swap.fractured_and_crafted_mods_not_swapped` | `harvest_swap.yaml:96` | marker in the middle (line 97) | `harvest_augment.py:69` | none | none |
| A8 | `imprint.consumed_on_restore` | `imprint.yaml:72` | "UNVERIFIED by me", "not rechecked for 3.29" | `actions/imprint.py:61` | `tests/test_actions_imprint.py:236-247` asserts the statement starts with "UNVERIFIED" and that none of the eleven claims is approximate ("the owner decided used up and several (grill B3)") | none (`imprint`, `restore` are `planner=False`) |
| A9 | `imprint.several_per_item` | `imprint.yaml:80` | same | `imprint.py:62` | same test | none |
| A10 | `imprint.allflame_copy_not_restorable` | `imprint.yaml:88` | "UNVERIFIED by me" | none | same test | none |
| A11 | `recombinator.weighted_report_3_27` | `recombinator.yaml:260` | "UNVERIFIED anecdote" | none | none | none (`recombinator` is `planner=False`) |
| A12 | `recombinator_cost.influence_plus_50_percent_3_25` | `recombinator_cost.yaml:68` | "UNVERIFIED" | none | none | none |
| A13 | `recombinator_cost.junk_craft_before_after_report_3_26` | `recombinator_cost.yaml:100` | "UNVERIFIED single report" | none | none | none |
| A14 | `recombinator_cost.dust_rule_average_tier_report` | `recombinator_cost.yaml:110` | "UNVERIFIED player assertion" | none | none | none |
| A15 | `recombinator_cost.idol_cost_cut_3_27` | `recombinator_cost.yaml:143` | "UNVERIFIED (read second-hand ...)" | none | none | none |

Read downstream: outside the registry, `Rule.approximate` is read at `cli/_marking.py:217` and `items/vendor_recipes.py:126`, and `approximate_reason` at `cli/_marking.py:220` and `cli/_start_options.py:367` (searched `\.approximate\b|approximate_reason` over `src/`).
- `cli/_marking.py:216-221` (`approximate_inputs_of`): for the claims that an action of the policy cites (`action.claims(data)`), plus `starts.claims` (`:209-210`); it skips every claim whose field is false (`:217`). This is the "Approximate inputs" block of the text (`_marking.py:224-233`), of the JSON `approximate_inputs` and of the page (`_route_view.py:540-554`).
- `items/vendor_recipes.py:123-126` (`Recipe.approximate_claims`): the claims behind a vendor recipe that carry the field. `cli/_start_options.py:354` stores their ids in the start candidate (`claims=`, which reach the block above through `starts.claims`), and `:366-367` (`claim_reason`) reads `approximate_reason`. So vendor start options already show their approximate claims; they are claims of `vendor.yaml`, and none of the 15 is one.
- `cli/_start_report.py:41,120` print "approximate" for a start option, but that is `ConsideredStart.approximate`, which `cli/_starts.py:93` sets from `plan.approximation is not None` (an approximate answer), not from a claim.

So no answer today could list any of the 15 even if a route reached them: the planner path would drop them at `_marking.py:217`. Seven of the 15 are cited by no `get_rule` call in `src/` at all (A1 and A10 to A15); the other eight (A2 to A9) are cited at the lines shown. Two claims put the marker inside the statement (A6, A7), so a check that tests only the start of a statement would miss them. The imprint test (A8 to A10) is the one test that asserts the opposite of the audit's finding, as a decision of the owner (grill B3).

The registry code is `rules/registry.py:188-189` (the two fields of `Rule`), `:195` (the allowed keys), `:261-275` (`_check_approximate`: requires a reason with `true`, refuses `false`, refuses a reason without `true`). It reads no text.

Neighbouring fact for #409: 27 claims carry `patch_verified: "3.29.0.3"` (the audit counted 25) against the 3.29.3.3 pin; 494 carry 3.29.3.3. They are in `beastcraft.yaml` (65, 75, 93, 160), `dominance.yaml` (26, 52, 78), `harvest_augment.yaml` (59, 67, 75, 107, 115), `harvest_reforge.yaml` (145, 197), `harvest_swap.yaml` (72, 80), `influence.yaml` (45, 53, 62, 102), `metamods.yaml` (38, 54), `unveil.yaml` (32), `veiled.yaml` (40, 52, 62, 98).

### 3.6 Which of these places an issue already names

| Site group | Named in |
|---|---|
| T1 to T4 (the four constants), D1 (`targets/model.py:7,57`) | #403 |
| T24 (`min_tier` None) | #403 (R12 comment), #410 point 1 (how to write "any tier"), #415 (R06) |
| R05, R06, R12, R13 target-file readings | #403, #415 |
| T27 (hand tier, R12) | #403, `tests/reconcile/known.py:71-72` |
| I3 (R08, R09 Alchemy in price) | #417 (OR-16), #408 |
| I1/I5 (buy spec and target disagree) | #417, #418, #428 |
| P1, P3 (price 0 / no restart) | #410 point 4, #427 |
| A1 to A15 | #409 |
| W5 to W8, T5 to T9 (essence, veiled), W12 to W15 (fallbacks), W16 to W19 | **no issue lists these lines** (the audit's class 1 names them: "essence-only mods", "veiled picks") |
| I2, I4, I6 to I13 | **no issue** (I4 is in #427 only as a missing price) |
| P2, P4 to P14 | **no issue lists these lines** (#427 names the targets, not the code) |
| Oracle cannot see beast, Elevated, Harvest, Awakener, recombinator, veiled paths | #416 |

### 3.7 What the defaults change in the benchmark targets (computed)

Method: for each of the 14 target files, the leaves (requirements, flattened through `at_least` groups) were read with `load_target`; the bench crafts and essence-forced mods that `catalog(data, start_item, planner_only=True, names={"bench-craft", "essence"})` can add for the target's base were intersected with each leaf's `mod_ids`. "Bench counted" is the number of such crafts a leaf with `not_crafted: false` counts, so each enters as `crafted=True, tier=1` and meets `min_tier` of any value. "Forced, no tier" is the number of offered essence-forced mods of the leaf that are not in `tier_table` of the base, so they enter as tier 1. These are counts of what the data holds. Whether the planner's plan uses them is not known from this; the targets that do not offer essences (`actions:` without `essence`: R08, R09, R13, R14, V01, J01) have their essence rows marked "not offered".

| Target | Leaf (min_tier, not_crafted) | Bench counted | Forced, no tier | Reading |
|---|---|---|---|---|
| R05 | Life T1, no `not_crafted` | 6 | 0 | a bench Life meets Life T1 (#403) |
| R05 | Fire, Cold, Lightning Resistance T2, no `not_crafted` | 2 + 2 + 2 | 0 | a bench resistance meets T2 (#403) |
| R06 | Life T1, Armour T3, no `not_crafted` | 6 + 6 | 0 and 1 (of 3 forced) | #415; refused by the gate G2, so only the oracle sees it |
| R12 | Lightning Resistance, no tier | 2 | 0 | #403 |
| R13 | All Damage, Elemental Damage with Attacks, no tier | 2 + 2 | 0 | #403 (OR-2) |
| R10, R10-70-life | Life (T1 / roll 70, `not_crafted`) | 0 (7 and 4 crafts exist; `not_crafted` refuses them) | 3 of 3 forced Life mods | an essence-forced Life without tier enters as T1 (essence is offered) |
| R11 | Life T1 `not_crafted` | 0 | 3 of 3 | the same (essence is offered) |
| R04 | Damage with Bow Skills T2 `not_crafted` | 0 | 2 of 7 | the same (essence offered) |
| R09 | Life T1, Movement Speed T1 | 0 | 3 of 3 and 1 of 3 | essence not offered by this target (`actions: [fossil-set, bench-craft]`) |
| R08 | Movement Speed T1 | 0 | 1 of 3 | not offered |
| R14 | Attack Speed T1 | 0 | 4 of 4 | not offered |
| V01 | Life T1 | 0 | 7 of 7 | not offered |
| R05 | Strength, `mod: StrengthEssence7_`, no `min_tier` | 0 | 1 of 1 | the leaf names the essence mod exactly (OR-2); no tier limit, so the stored tier 1 is not read; essence is offered |
| R04 | Strength, `mod: StrengthEssence7_`, no `min_tier` | 0 | 1 of 1 | the same; essence is offered |
| R03, R06, R11 | the avoid-shock implicit leaf of R03, the Strength leaf of R06, the Mana reservation leaf of R11 (all `mod:`, no `min_tier`) | 0 | 1 of 1 each | the same reading; R03 and R06 are refused by G2 |
| J01 | none | 0 | 0 | no bench craft or essence is offered for a jewel (`actions: [chaos-orb]`) |

Also: six target files name their bench craft exactly (`mod:`) and so read no default for it (R03: Life; R08, R09: Movement Speed; R10 and R10-70-life: Avoid Elemental Ailments; R14: two crafts). Targets whose start mod tier is hand-written: R03, R05, R10 x2, R11, R12 (one wrong, R12).

## Part B. Step 5: the answer envelope

### 5.0 What an answer carries today

`Plan` (`cli/_plan.py:85-107`) holds: `target`, `abstraction`, `leaf_labels`, `prices`, `start`, `start_price`, `offers`, `dropped`, `left_out`, `solution`, `risk`, `solve_seconds`, `risk_seconds`, `approximation`, `note`, `pruned`, `strands`, `starts`, `packed`. What each surface reads:

| `Plan` field | T | J | P |
|---|---|---|---|
| `left_out` | `_report.py:325-326` "Not offered, N actions: reason" | `:529-531` `left_out_actions` | not read |
| `dropped` | `:315-324` (grouped past 300, `MAX_DROPPED_LINES` `:45`) | `:528` `dropped_actions` | not read |
| `note` | `:301-302` "Note: ..." | `:513` `note` | not read (the page's own "Note" is another text, `_route_view.py:537,556`) |
| `strands` | `:281-285,310` one line | none | not read |
| `approximation` | `_marking.py:59-76` | `:510`, `_marking.py:84-103` | none: the page is not written (`_main.py:162-163`, one stdout line) |
| `pruned` | none directly; its three reasons are appended to `left_out` (`_plan.py:402,536-547`) | via `left_out` | not read |
| `packed`, `view_policy` | note only (`_plan.py:419-424`) | via `note` | the page draws the lumped chain (`_route_view.py:150`) with no word |
| `starts` | `_report.py:313-314`, `_start_report.py:79-103` | `:527`, `_start_report.py:105-150` | only the vendor first step: `_route_view.py:513-523` (considered rows, not the refused) |
| `start_price` | `:309` name, chaos, source | `:521-526` | `_route_view.py:387-400,466-474` (chaos and name; source never) |
| `prices` | `:304-307` one line league and fetch day | `:516-520` | `_route_view.py:555` one line |
| `offers` / per-resource parts | `:340-344` counts and Chaos, no source | `:532,541-544` with `price_source` | `_route_view.py:390` (the source is dropped: `for name, count_, chaos, _`) |
| `risk` (p50, p90) | `:387-391`, `UNRESOLVED` `:240` | `:471-481`, `quantiles_resolved` | `_route_view.py:533-534` "not resolved on the grid (#190)" |
| approximate claims | `_marking.py:224-233` | `:511`, `_marking.py:236-241` | `_route_view.py:540-554` |

Other surfaces: the stale-price warning goes to stderr only (`cli/_main.py:118-120`, `cli/_benchmark.py:378-380`, text from `prices/price_file.py:345-361`). The benchmark JSON (`cli/_benchmark.py:355-451`) carries a route's totals, its start options, `error` and `missing_price`, and no `left_out`, `dropped` or `note`.

Tests that pin what is shown: dropped lines `tests/test_cli_plan.py:137-168`, `tests/test_cli_real.py:113-122`; left-out lines `tests/test_cli_offers.py:63-92,159,223-226` and `tests/golden/v01_minion_helmet.txt:21`; strands line `tests/test_memory_strands_item.py:351,362,377`; page "Prices" field `tests/test_cli_route_view.py:219` and the goldens `tests/golden/real_r05.html`, `real_r10.html`, `real_r11.html`, `v01_minion_helmet.html` (each holds "league Allflame, fetched 2026-10-31"); text tree limit `tests/test_cli_decide.py:311-322`; approximate answer lines `tests/test_cli_approximate.py:379,393`.

### 5.1 Gates and constants of the planner entry (`make_plan`, `cli/_plan.py`)

Search: every `raise` and module constant of `_plan.py`, read in full.

| ID | Place | Limit | Kind | T | J | P | Tests | Issue |
|---|---|---|---|---|---|---|---|---|
| G1 | `_plan.py:304-309` | Memory Strands on: refused ("batch B5, tickets #275 onward") | refusal (model gap) | E; when off, line `_report.py:310` | no | no | `test_memory_strands_item.py:351,362,377` | #423 |
| G2 | `_plan.py:311-315` | implicits or quality: refused ("batch B2, #142 onward") | refusal (model gap) | E | no | no | `test_cli_plan.py:220` | #416 (oracle side) |
| G3 | `_plan.py:316-320` | sockets: refused (B6) | refusal (model gap) | E | no | no | `test_targets_sockets.py:994,1001` | none |
| G4 | `_plan.py:321-325` | enchantment: refused (B7) | refusal (model gap) | E | no | no | `test_targets_enchantment.py:246` | none |
| G5 | `_plan.py:346-353` | an offered action reads a rule axis: refused (#220) | refusal (model gap) | E | no | no | none found | none |
| G6 | `_plan.py:354-363` | `allow_inputs=False`: an action that consumes other items is refused by every kernel (`_kernel.py:1189-1194`) | gap, silent | no | no | no | `tests/test_abstraction_recombinator.py:251`, `tests/test_actions_inputs.py` | none (audit ACT2-11) |
| G7 | `_plan.py:334-337` | no action has a price: refused | refusal | E | no | no | `test_cli_plan.py:174` | #406 |
| G8 | `_plan.py:338-339`, `_offers.py:395-400` | actions that need a crafted mod are dropped when none can exist | silent filter | no | no | no | `test_cli_plan.py:179-181` | none |
| G9 | `_plan.py:340-344` | restart only when the start price is above 0 | silent (see P3) | no | no | no | `test_cli_offers.py:129` | #410 pt 4 |
| G10 | `_plan.py:310`, `:231-252` | the start price is any entry under the name | price fact (5.3) | source | `start.price_source` | name, chaos | `test_cli_plan.py:129` | #406 |
| G11 | `_plan.py:367-369` | `solve_it=False`: nothing solved, infinite value | internal | no | no | no | `test_reachability_report.py` | #414 |
| G12 | `_plan.py:370-393`, `_decide.py:47-54` | a budget (`BUDGET_SECONDS = 60`, `TOLERANCE = 0.01`, `EXACT_TRANSITIONS = 2_000_000`) chooses exact, approximate or refused | cut with a guarantee | "Answer:" lines, `_marking.py:59-76` | `answer` | none (page not built) | `test_cli_decide.py`, `test_cli_approximate*.py` | #407 |
| G13 | `_plan.py:379-384` | refused: no coarse level and a graph beyond what the solver was run on | refusal, then packed solve with `_packed_note` (`:432-438`) | `Note:` | `note` | no | `test_cli_decide.py:289-297` | #407 |
| G14 | `_plan.py:39` | `VIEW_FROM_STATES = 1_000`: a packed plan's policy is shown by its lumped chain | display cut | `Note` `:419-424` | `note` | drawn lumped, no word | the lump: `test_solver_packed_lump.py`; no test says the page names it | #407, #408 |
| G15 | `_plan.py:40-42` | `MERGE_EQUAL`, `PRUNE_CORRUPTING`, `PRUNE_BOUND`: exact prunings, switchable only by tests | exact cut | no | no | no | `test_prune_equal.py`, `test_prune_bound.py` | none |
| G16 | `_plan.py:43,398-402` | `MIN_OFFERS_TO_PRUNE = 40`; bound pruning leaves offers out of the solve | exact cut | `_pruned_left_out` `:536-547` in "Not offered" | `left_out_actions` | no | `test_prune_bound.py:374-386` | #405 |
| G17 | `_plan.py:403-406` | the packed path merges twins (`merge_twins`) and adds no `left_out` line | silent exact cut | no | no | no | `test_prune_forecast.py`, `test_bound_prune_light.py` test `merge_twins`; none asserts a `left_out` for a packed plan | none |
| G18 | `_plan.py:408-409` | no policy reaches the goal: refused | refusal | E | no | no | `test_cli_plan.py` | none |
| G19 | `_plan.py:441,467-472` | `RISK_QUANTILE_TRANSITIONS = 2_000_000`: no quantile grid for a larger merged chain | cut | `Note` | `note` | `risk` unresolved text | `test_packed_plan_real.py:139` | #407 |
| G20 | `_plan.py:489-491,520-533` | `RISK_BINS = 200_000`, `UNRESOLVED_BINS = 1_000`, `COARSE_BINS = 1_000_000`: a quantile the grid cannot reach is infinite | cut | `UNRESOLVED` `_report.py:240-249` | `quantiles_resolved` | `_route_view.py:534` | `test_cli_free_actions.py:251` | #407 |
| G21 | `_main.py:137-138` | `--route` with an approximate answer: refused | refusal | E | no | no | `test_cli_approximate.py:393` | none |
| G22 | `_main.py:162-164` | approximate answer: no route page | refusal | one stdout line | no | no page | `test_cli_approximate.py:379` | #408 |
| G23 | `_main.py:171-173` | `TargetError, DataError, PriceFileNotFound, PlanError, ActionError, ConvergenceError, ValueError, OSError` become one `Error:` line, exit code 1 | all refusals | E | no | no | many | none |
| G24 | `_plan.py:326-333` | `offers_for(...)` raising `ValueError` becomes `PlanError` | refusal | E | no | no | `test_cli_offers.py:181` | #405 |

### 5.2 Offer filters and withheld kinds

Search: `catalog`, `kinds(`, `opt_in`, `planner=`, `needs_strands`, `corrupting`, every filter in `offers_for`. `cli/_offers.py` read in full.

**Code places (17).**

| ID | Place | What is withheld, and when | Shown (T / J / P) | Tests | Issue |
|---|---|---|---|---|---|
| K1 | `actions/catalog.py:138-139` | an `opt_in` kind is listed only when the target's `actions:` names it. A target with no `actions:` key gets none of the 17, with no line | no / no / no | `test_actions_opt_in.py:54-70` | #405 (OR-5, OR-13) |
| K2 | `actions/catalog.py:112-115,133` | `planner=False` kinds (28) are left out of every planner catalog | no / no / no | `test_reachability_report.py` | #414 (closed) |
| K3 | `actions/catalog.py:135-136` | a `needs_strands` kind is listed only with strands | no / no / no | `test_memory_strands_item.py` | #423 |
| K4 | `_offers.py:293-302` | the "left out" line for kinds not named is written only when `kinds_named is not None` (a target with an `actions:` key) | yes (only then) / yes / no | `test_cli_offers.py:159` | #405 |
| K5 | `_offers.py:252-253,290-292` | a corrupting kind (the Vaal Orb) is skipped without a word for a target that takes no corrupted item | no / no / no | `test_offers_wanted_only.py`, `test_targets_corrupted.py` | none |
| K6 | `_offers.py:293,332-336` | kinds that need strands are not mentioned while the start item has none | no / no / no | none | #423 |
| K7 | `_offers.py:242,260-275,303-311` | a bench craft whose mod counts toward no leaf is left out; the reason differs by whether another action keeps crafted mods (`erased_by_all`) | yes / yes / no | `test_cli_offers.py:63-92` | #405 |
| K8 | `_offers.py:254-255,321-328` | an action that adds one fixed mod nobody wants (`Adds.wanted_only`, aspects) | yes / yes / no | `test_offers_wanted_only.py` | #405 |
| K9 | `_offers.py:256-257,312-320` | a value-reroll (`needs_roll_limit`, Divine Orb) without a roll limit; named only when the goal has a roll limit | yes (conditionally) / yes / no | `test_cli_offers_divine.py` | none |
| K10 | `_offers.py:395-400` | `usable_actions`: Remove Crafted Mods removed when no crafted mod can exist | no / no / no | `test_cli_plan.py:179-181` | none |
| K11 | `_offers.py:339-361` | `actions:` naming an unknown kind or a `planner=False` kind raises `ValueError` ("cannot be used by the planner yet") | E / no / no | `test_cli_offers.py:181` | #405 |
| K12 | `_offers.py:94-132` | an offer with an unpriced resource is dropped, not estimated (OR-23) | yes / yes / no | `test_cli_plan.py:137-168` | #406 |
| K13 | `cli/_prune.py:77,79` | corrupting and quality offers pruned at states that cannot use them | no / no / no | `test_actions_corrupting_toy.py:309` | none |
| K14 | `cli/_prune.py:84-87,127-130` | an offer for which the kernel raises `ActionError` at a state is skipped, game refusal and model gap alike | no / no / no | `test_prune_equal.py` | none |
| K15 | `_plan.py:536-547` | pruning reasons written as `LeftOut`: "same outcome as a cheaper offer", "the game refuses it on this item wherever it can be", "proved never better: even its best case costs more than the plan" | yes / yes / no | `test_prune_bound.py:374-386` | #405 |
| K16 | `_offers.py:143-149` | `LeftOut(reason, labels)` is the only record type for a deliberate omission: a reason and a list of labels, no field for what the answer still guarantees | (the carrier of K4, K7 to K9, K15) | `test_cli_offers.py` | #405, OR-13 |
| K17 | `_offers.py:300-302` | the only stated guarantee in the code: "the plan is the cheapest among the named ones" (written for the `actions:` case only; K7's reason adds one for the crafts case at `:304-310`) | T / J / no | `test_cli_offers.py:159`, `tests/golden/v01_minion_helmet.txt:21` | #405, OR-13 |

**Kinds withheld (59 kinds in the catalog; the counts reproduce `tests/golden/reachability.md:14-28`).** Run read-only on this tree: 59 kinds, 28 `planner=False`, 31 `planner=True` of which 17 `opt_in`, 3 `needs_strands`, 1 `corrupting`.

- `planner=False` (28), each with its `why_not` in `reachability.md:34-94`: `harvest-reforge-likelihood` (`actions/harvest_likelihood.py:103`), `harvest-quality-enchant` (`harvest_quality.py:125`), `alchemy-orb` (`alchemy.py:71`), `influenced-exalted-orb` (`influence.py:246`), `orb-of-dominance` (`influence.py:391`), `scouring-orb` (`scour.py:133`), `awakeners-orb` (`awakener.py:260`), `beast-influence-recipe` (`influence.py:467`), `blessed-orb` (`blessed.py:183`), `recombinator` (`recombinator.py:537`), `catalyst` (`catalyst.py:227`), `eldritch-implicit-currency` (`eldritch.py:293`), `eldritch-chaos-orb` (`:461`), `eldritch-exalted-orb` (`:473`), `eldritch-annulment-orb` (`:485`), `orb-of-conflict` (`:597`), `tempering` (`enchant.py:236`), `tailoring` (`:248`), `imprint` (`imprint.py:225`), `restore` (`:230`), `jewellers-orb` (`socket_orbs.py:464`), `orb-of-fusing` (`:472`), `bench-socket-count` (`:487`), `bench-socket-links` (`:493`), `chromatic-orb` (`socket_colours.py:368`), `bench-socket-colours` (`:385`), `quality-currency` (`quality_currency.py:139`), `re-anoint` (`burn.py:105`).
- `opt_in` (17), offered only when the target names them: `harvest-add-remove` (`harvest_augment.py:181`), `harvest-resistance-swap` (`:358`), `harvest-damage-swap` (`:365`), `corrupted-essence` (`essence.py:150`), `fossil-set` (`fossil.py:539`), `exalted-orb` (`exalted.py:83`), `veiled-chaos-orb` (`veiled.py:448`), `veiled-exalted-orb` (`:459`), `unveil` (`:470`), `pick` (`:481`), `annulment-orb` (`annul.py:105`), `fracturing-orb` (`fracture.py:109`), `talisman-fracture` (`beasts.py:173`), `aspect-beast` (`:243`), `beast-side-swap` (`beast_mods.py:246`), `wild-bristle-matron` (`:149`), `foulborn-exalted-orb` (`foulborn.py:146`). Five of the 17 are offered by some benchmark target (corrupted-essence R04; fossil-set R08, R09; exalted-orb R04, R14; annulment-orb R04, R14; fracturing-orb R04); 12 by none.
- `needs_strands` (3): `foulborn-augmentation-orb` (`foulborn.py:134`), `foulborn-regal-orb` (`:140`), `foulborn-exalted-orb` (`:146`). They are `planner=True` and can never be offered while G1 stands (#423).
- `corrupting` (1): `vaal` (`corruption.py:210`).
- The groups overlap: `foulborn-exalted-orb` is both opt-in and needs strands. Of the 31 planner kinds, 17 + 3 + 1 - 1 = 20 are withheld by a flag (opt-in, strands or corrupting) and 11 are offered by default; 28 + 20 = 48 kinds are withheld by a flag, not 49, and 11 kinds are offered by default.
- Planner kinds no benchmark target reaches: 16 (`reachability.md:17-18`).

### 5.3 Unpriced items and price provenance

| ID | Place | Fact the planner applies | T | J | P | Tests | Issue |
|---|---|---|---|---|---|---|---|
| U1 | `_offers.py:94-127` | an offer with a resource not in the file (and not Chaos or Divine) is dropped | per offer | `dropped_actions` | no | `test_cli_plan.py:137-168` | #406 |
| U2 | `_report.py:45,315-324` | more than 300 dropped offers are grouped by missing price, 3 labels shown | yes | full list | no | `test_cli_plan.py:154-168` | none |
| U3 | `_plan.py:248-251` | an unpriced start name is an error | E | no | no | `test_cli_plan.py:129` | #406 |
| U4 | `_plan.py:231-252`, `_offers.py:117-119` | the price is whatever entry carries the name: its `source` string is kept, its `note`, `detail` (age, league, sample) are not read | source only | `price_source` | no | `test_cli_plan.py` | #406, #426, #429 |
| U5 | `prices/price_file.py:52-76` | `PriceFile.markets` (thin or none trade searches) and `PriceFile.ninja` (poe.ninja rows beside trade prices) exist; nothing outside `prices/` reads them (searched `\.markets\b`, `\.ninja\b`) | no | no | no | `test_prices_*` | #406 |
| U6 | `prices/trade_market.py:83-138`, `prices/price_source.py:154-210` | the market rule (instant buyout, age 7 days, sample size) and the price-source rule (`ninja`/`trade`/`both`, fallback mark, gap flag) are built and not called by the planner (`reachability.md:181-190`) | no | no | no | `test_prices_trade_market.py`, `test_price_source.py` | #406 (OR-7) |
| U7 | `_starts.py:105-106,122`, `_start_options.py:62-75` | `price_source` and `price_gap_percent` settings reach `StartContext` and stop (`reachability.md:146-147,155`) | no | no | no | none | #406 |
| U8 | `_report.py:304-307` | league and fetch day: one line for every price, whatever its source or age | yes | `prices` | `_route_view.py:555` | `test_cli_route_view.py:219`, goldens | #406 (audit INPUTS-3) |
| U9 | `_main.py:118-120` | the 7-day staleness warning goes to stderr only | E | no | no | `test_prices_file.py` | #406 |
| U10 | `_offers.py:115-116,120-121` | Chaos Orb fixed at 1; Divine from the rate; sources "fixed", "rate" | no | `resources[].price_source` | no | `test_cli_plan.py` | none |
| U11 | `_offers.py:128-131` | free actions cost an epsilon | yes (`_report.py:341-342,256-269`) | `free_action_*` (`:486-495`) | no | `test_cli_free_actions.py` | none |
| U12 | `_report.py:340-344` | cost line: counts and Chaos, source not printed | no source | source in JSON | `_route_view.py:390` drops it | | #406 |
| U13 | `tests/reconcile/known.py:58-59,75,78` | start prices that are poe.ninja or hand stand-ins (R04, R13, V01) and a poe.ninja line of item level 85 for 81 | no | `price_source` only | no | strict xfails | #426, #425 |
| U14 | `_start_options.py:276-309,344` | a recipe with a missing price line is refused with the names missing (`NO_PRICE`) | yes | yes | the refused list is not shown | `test_vendor_starts.py` | none |
| U15 | `_start_types.py:44`, `_start_report.py:86-88,124` | `StartCandidate.sourced` (trade and poe.ninja side by side, fallback mark) is printed under a vendor option when present | yes | `price` | no | `test_price_source.py` | none |
| U16 | `_plan.py:239-242` | a run's `--start-price` wins; source text "given on the command line" | yes | yes | no | `test_cli_plan.py:104` | none |
| U17 | `prices/price_file.py:29`, `prices/trade_market.py:15` | `MAX_AGE_DAYS = 7` is used by `stale_warning` and by the unused market rule | E only | no | no | | #406, ADR-0007 line 7 |

### 5.4 Cuts and bounds of the search

| ID | Place | Cut or bound | Guarantee stated | T | J | P | Issue |
|---|---|---|---|---|---|---|---|
| C1 | `_decide.py:47` | `BUDGET_SECONDS = 60` ("about a minute (#81 Q2)") | exact, else a ladder | `Note` only when the query did not fit | `note` | no | #407 |
| C2 | `_decide.py:48` | `TOLERANCE = 0.01` ("the owner's tolerance") | certified gap | `Answer:` | `answer` | no | #407 |
| C3 | `_decide.py:49` | `EXACT_TRANSITIONS = 2_000_000` | exact only below | `Note`, E | `note` | no | #407 |
| C4 | `_decide.py:73-85` | the ladder: three group levels and three tail cuts (theta 1e-2, 1e-3, 1e-4); spread levels (1000, 500) | gap of the level | `Answer:` | `answer` | no | #407 |
| C5 | `_decide.py:50-54` | solve-rate and pilot constants | none | no | no | no | |
| C6 | `_approx.py:77` | `LEVEL_ALLOWANCE = 10` budgets for all levels; `LevelTimeout` | stopped | `Answer:` message | `message` | no | #407 |
| C7 | `_approx.py:321-323` | no level finished / no policy: `ValueError` | refusal | E | no | no | #407 |
| C8 | `_packed.py:47` | `OBJECT_SOLVER_EDGES = EXACT_TRANSITIONS`: above it the packed solver runs | exact | `Note` | `note` | no | #407 |
| C9 | `_bound_prune.py:105-108` | `SMALL_START = 8`, `PER_ROUND = 16`, `SLACK = 1e-12`, `HUGE = 1e300` | exact (search parameters) | no | no | no | none |
| C10 | `_plan.py:43` | `MIN_OFFERS_TO_PRUNE = 40` | exact | no | no | no | none |
| C11 | `simulator/_simulate.py:53`, `cli/_route_sim.py:19` | 100,000 and 200,000 uses per simulated run | a run is cut and counted `unfinished` | `--verify` lines | `verification.unfinished` | no | #407 |
| C12 | `cli/_verify.py:30-37` | `DEFAULT_RUNS = 10_000`, `STEPS_PER_MEAN = 50`, `MIN_STEPS = 100`, `SIGMAS = 5.0`, `SIMULATION_BLOCK = 2_000` | detectable error stated | yes | yes | no | none |
| C13 | `actions/imprint.py:65` | `DEFAULT_MAX_IMPRINTS = 1` (never read as a setting: 5.7) | none | no | no | no | #407 |
| C14 | `_report.py:42-43` | `MAX_TREE_DEPTH = 40`, `MAX_TREE_STATES = 1_000` | says where the rest is | `:364,366,376` | holds all states | holds all steps | #407 |
| C15 | `_reach.py:15,43` | `MAX_TRANSIENT = 400`: above it no "reached with chance" | not stated | silently absent (`_report.py:338`) | `reach_probability: null` | no | none |
| C16 | `_route_flow.py:50-51` | `MAX_STEPS = 1_500`, `REFINE_WORK = 250_000` (past `REFINE_WORK` every state is a step: R14's 87,272 steps) | for `MAX_STEPS` only: "how often a step is used and what it costs are left out" | no | no | `Note` (`_route_view.py:537,556`) for `MAX_STEPS` only | #407, #408 |
| C17 | `cli/_interval.py:328`, `cli/_report.py:78` | not a cut: the interval driver over rule axes (`build_interval_answer`, `with_interval`) has no caller in `src/`; tests call it (`tests/interval_support.py:122`) | n/a | `interval.text_lines` unreachable from the CLI | same | page code exists (`_route_view.py:539-546`) | #407 (ADR-0012, ADR-0023) |
| C18 | `abstraction/_estimate.py:49-50,343-344` | `DEFAULT_LIMIT = 400_000`, `ADDING_LIMIT = 20_000` states (and a `seconds` deadline) for the pilot walk; past them `complete=False` and every count is a lower bound | `choose` then never calls the graph small (`_decide.py:186,198`) and `exact_offer` says "the count stopped at N transitions" (`:154-158`) | `Note` | `note` | no | #407 |
| C19 | `abstraction/_estimate.py:149,248,264`; `cli/_decide.py:264-265` | `EstimateRefused` (rerolling action; a walked kernel that raises `ValueError`; a fractured family type): the pilot cannot count, `decide` returns `choose(None, ...)` = exact, message "the size of the exact graph could not be forecast, so it is built as it is" (`:183`). The text of the `EstimateRefused` itself is dropped (`except EstimateRefused:` binds nothing) | the cause is lost; the note says only that no forecast exists | `Note` | `note` | no | #407 |
| C20 | `risk/_coarse.py:36-41,47,101` | `DENSE_STATES = 2500`, `GAP_TARGET = 0.02`, `GAP_LIMIT = 0.1`, `COSTS_TRIED = 12`, `PARTS_TRIED = 64`, `DENSE_WORK = 1e11`: no coarse quantile grid if the best step leaves a gap above 10% of the mean, or above 2,500 states | the grid used is stated in `GridInfo` | quantile text | `quantiles_resolved` | `_route_view.py:534` | #407 |
| C21 | `risk/_evaluate.py:111-125` | `HORIZON_SDS = 6`, `COVERED_STEPS = 64`, `FINE_STEPS = 64`, `WORK_BUDGET = 3e8` (a larger policy gets a coarser grid), `SPREAD_SDS = 6`, `REGEN_PARTS = (4, 8, 16, 32)`, `REGEN_WIDTH = 0.03`, `REGEN_SECONDS = 600`, `REGEN_SLOWER = 3` | the quantile intervals report their own width (`certified`, `_report.py:230-237`) | yes | `low`/`high` | no | #407, OR-11 |
| C22 | `risk/_evaluate.py:112-113,220-225` | `MIN_COST = 1e-150`, `MAX_COST = 1e150`: a policy with a cost outside this range is refused (`ValueError`) | refusal | E | no | no | none |
| C23 | `risk/_free.py:35-38` | `FREE_TAIL = 1e-9`, `PAID_STATES_LIMIT = 600`, `COUNT_BINS = 100_000`, `PAID_CHARGE = 1e-3`: past 600 paying states the free-action count is not attempted and the ordinary grid is used | `free_action_*` allowances (`_report.py:256-269`) when it ran | yes | `free_action_*` | no | #407 |
| C24 | `risk/_fold.py:25` | `FOLD_LIMIT = 1500` states of the largest free component that is folded; past it `None` and the free-action path gives up | not stated | no | no | no | none |
| C25 | `risk/_regen.py:40-41` | `ATTEMPT_TAIL = 1e-13`, `MAX_MISSING = 1e-10`: the attempt-wise run is refused (`None`) when the cut attempts' mass is above `MAX_MISSING` | the ordinary grid is tried next | no | no | no | none |
| C26 | `risk/_nested.py:65-67` | `START_BINS = 64`, `TINY = 1e-150`: masses below `TINY` are dropped into the unresolved mass | counted as `unresolved_mass` (`risk/_report.py:22-33`) | no | `grid` info only | no | none |
| C27 | `risk/_dense.py:39`; `risk/_moments.py:28` | `DENSE_LIMIT = 50_000_000` cells for the dense engine (`ValueError` past it, `:79-80`); `PACKED_FROM_EDGES = 2_000_000` edges move the moments to packed arrays | not stated | no | no | no | none |
| C28 | `solver/_minmax.py:75-76` | `MAX_ROUNDS = 100` of nature's best response; the module says a stop "can cost tightness but never soundness" | the certified gap | via `solver_error_bound` | `solver_error_bound` | no | #407 |
| C29 | `solver/_component.py:11-20` | `MAX_POLICY_ITERATIONS = 100`, `SWEEPS_BEFORE_DIRECT = 300`, `MAX_SPARSE_POLICY_ITERATIONS = 1000`; a component that does not reach tolerance raises `ConvergenceError` (`solver/_solve.py:146`) | refusal | E | no | no | none |
| C30 | `solver/_packed_solve.py:41-43,204-208` | `ACCEPT_BOUND = 1e-6` (a certified relative bound above it raises `ConvergenceError`, `:404,454`), `DENSE_LIMIT = 1500`, `STAGNATION = 400`, `BICGSTAB_ITERATIONS = 4_000`, `BICGSTAB_RESTARTS = 3`, `DENSE_FALLBACK = 6_000` | refusal when the bound fails | E | no | no | #407 |
| C31 | `solver/_sparse.py:31` | `WORK_LIMIT = 200_000_000` multiply-adds one elimination may spend before it "gives up" (`solver/_sparse.py:31`, comment) | not stated | no | no | no | none |
| C32 | `solver/_packed_lump.py:34-35,230,263`; `solver/_packed_merge.py:164` | `CHECK_TOLERANCE = 1e-12`; a lumping that does not settle or disagrees with a state raises `ValueError`; an exact merge that does not settle in its rounds raises `ConvergenceError` | refusal | E | no | no | none |
| C33 | `solver/_tail.py:48` | `PUSH_FLOOR = 1e-3` of `theta`: mass below it waiting in an expanded state is not pushed on (the tail-cut levels of C4) | the level's gap | `Answer:` | `answer` | no | #407 |
| C34 | `simulator/_simulate.py:54,149-152` | `MAX_NESTING = 100` levels of inputs asking for inputs; a deeper chain is cut and the run is unfinished | `unfinished` in the verification | `--verify` lines | `verification.unfinished` | no | #407 |
| C35 | implementation constants, not limits of an answer | `risk/_budget.py:62-68`, `risk/_chain.py:21-22`, `risk/_inputs.py:52-54`, `risk/_moments.py:27,29`, `risk/_readings.py:60-61`, `risk/_regen.py:32`, `solver/_certify.py:57`, `solver/_graph.py:22-23,499`, `solver/_packed.py:27-28`, `solver/_packed_lump.py:33`, `solver/_packed_merge.py:27`, `solver/_peek.py:51-53`, `simulator/_estimate.py:13`, `abstraction/_coarse.py:77`: epsilons, chunk sizes, tolerances | none | no | no | no | none |

### 5.5 Model gaps and refusals

**The one error family.** `ActionError(ValueError)` (`actions/errors.py:33`) has two subclasses: `NotApplicableError` (the game refuses, `:37`) and `OutOfScopeError` (the model cannot say, `:41`). 

**Raise sites of `OutOfScopeError` (84 in 25 files)**, from `grep -rn "raise OutOfScopeError" src`:

- `abstraction/_bound.py`: 278, 283
- `abstraction/_coarse.py`: 119, 134, 262, 267, 274, 279, 281, 377
- `abstraction/_inputs.py`: 82, 85, 91, 121, 254
- `abstraction/_kernel.py`: 454, 493, 495, 686, 803, 860, 872, 893, 1001, 1192, 1270, 1284, 1302, 1331, 1352, 1418, 1612, 1845, 1878, 1889
- `actions/awakener.py`: 187, 254
- `actions/beast_mods.py`: 124, 126
- `actions/beasts.py`: 230
- `actions/bench.py`: 226, 230, 296
- `actions/blessed.py`: 163
- `actions/bloodstained.py`: 106
- `actions/contract.py`: 749, 839
- `actions/corrupted_pool.py`: 126
- `actions/corruption.py`: 186
- `actions/draw.py`: 93, 98, 106
- `actions/eldritch.py`: 275, 530
- `actions/enchant.py`: 104, 115, 123, 194
- `actions/essence.py`: 91, 112, 120
- `actions/fossil.py`: 379, 472, 485, 513, 533
- `actions/harvest_augment.py`: 259
- `actions/influence.py`: 138, 317, 332, 340, 363
- `actions/pool.py`: 110, 270
- `actions/recombinator.py`: 361, 426
- `actions/socket_colours.py`: 187, 195
- `actions/socket_orbs.py`: 149, 153, 338
- `actions/veiled.py`: 147, 149, 157

Their causes group as: normal or empty item with no admitted rule (`bench.py:226,230,296`, `beasts.py:230`, `beast_mods.py:124,126`, `essence.py:112`, `fossil.py:533`); unmodelled item class (`draw.py:93,98,106`, `pool.py:110`, `influence.py:138`, `enchant.py:104`, `corrupted_pool.py:126`); unmodelled state shape (`_kernel.py:803,1270,1284,1302,1331,1612`, `_coarse.py:134`, `_inputs.py:121`, `_bound.py:278`); a roll limit on a forced, crafted or fixed mod (`_kernel.py:1001,1418,1845,1878,1889`, `_bound.py:283`); input-consuming actions (`_kernel.py:1192`, `_inputs.py:82,85,91,254`, `contract.py:749`, `recombinator.py:361`); missing data or claim (`fossil.py:472,485,513`, `eldritch.py:275,530`, `influence.py:332,340`, `enchant.py:115,123`, `essence.py:91,120`); a strand declaration (`contract.py:839`); coarse-level invariance (`_coarse.py:119,262,267,274,279,281,377`); the rest are single cases.

**Where the cause is lost: the `except` clauses on the family (34, searched with `except[^:]*(OutOfScopeError|ActionError|NotApplicableError)`).** 27 catch `ActionError` or both subclasses and so treat a game refusal and a model gap alike; 3 catch only `NotApplicableError`; 4 catch only `OutOfScopeError`.

| Group | Places | Catches | What happens |
|---|---|---|---|
| planner path (6) | `cli/_prune.py:86,129`; `cli/_packed.py:124`; `cli/_bound_prune.py:423`; `cli/_donors.py:83`; `cli/_offers.py:385` | both | the offer is skipped at this state, or the proof says "refused"; nothing is recorded |
| coarse levels and forecast (8) | `cli/_approx.py:137,189`; `abstraction/_coarse.py:572,604`; `abstraction/_estimate.py:222,245`; `abstraction/_prime.py:61`; `abstraction/_kernel.py:767` | both | the action is skipped in the block, the forecast or the prime |
| a given route (4) | `cli/_route.py:464` (reported as "cannot be used here"); `cli/_route_sim.py:48`; `cli/_route_packed.py:78,87` | both | a gap in the route (`skip_refused`) |
| actions (6) | `actions/fossil.py:394,408,428`; `actions/contract.py:714`; `actions/recombinator.py:221`; `actions/socket_colours.py:268` | both | candidate filtering inside an action |
| targets (2) | `targets/corrupted.py:76`; `targets/floor.py:285` | both | the corruption check and the floor treat a gap as "cannot" |
| top (1) | `cli/_main.py:171-173` | both, among six other errors | one `Error:` line |
| game refusal only (3) | `abstraction/_inputs.py:253`; `abstraction/_kernel.py:1230,1268` | `NotApplicableError` | placement averaging; the representative's refusal |
| model gap only (4) | `abstraction/_bound.py:335`; `abstraction/_kernel.py:429`; `actions/awakener.py:271`; `cli/_decide.py:214` | `OutOfScopeError` | no bound given; tiers context falls back to the base's table; an item class with no influence key; the message of the first non-invariant action becomes the reason of the refusal |

Shown: only the top-level case (the target stops with one stderr line) and the `_decide.py:214` reason are ever shown. A gap hit inside a solve is skipped silently, so a plan can omit an action in a state where the model has no rule, and the answer does not say so (audit SOLVER-8, PLANNING-5). Tests: `OutOfScopeError` appears in 56 test files; none asserts that an answer reports a skipped model gap.

Messages that are shared: "not resolved on the grid (#190)" is the text for the p90 cut, the memory limit and donors in a cycle (`_report.py:240`, `_route_view.py:534`; audit SOLVER-6). "cannot plan yet" is shared by G1 to G4.

**The second refusal family: errors of the search and the solve, not of the game.** They are raised below `make_plan` and handled in different ways; none is an `ActionError`.

| ID | Error | Raised at | Handled at | What the answer says |
|---|---|---|---|---|
| M1 | `EstimateRefused(ValueError)` (`abstraction/_estimate.py:54`) | `_estimate.py:149` (an enabled action rerolls values), `:248` (a walked kernel raises `ValueError`), `:264` (a fractured family type) | `cli/_decide.py:264-265`: `except EstimateRefused:` returns `choose(None, 0.0, 0.0, budget)` = exact | the generic note of C19; its own text is dropped |
| M2 | `ConvergenceError(RuntimeError)` (`solver/_certify.py:60`) | `solver/_solve.py:146`; `solver/_packed_solve.py:313,338,404,454`; `solver/_packed_merge.py:164`; `solver/_peek.py:441` | swallowed at `cli/_decide.py:243` (the rate calibration falls back to `SOLVE_RATE_FALLBACK`, together with `ValueError`), at `cli/_approx.py:312` (a tail-cut level: `continue`; any other level re-raises) and at `cli/_bound_prune.py:363` (the reduced model: `fallback(...)` solves the whole model, `Pruned.fell_back = True`, `Pruned.why` = the message); otherwise it reaches `cli/_main.py:171` | the reduced-model case sets `Pruned.fell_back` and `Pruned.why`, which no renderer reads (searched `fell_back`, `\.why` in `src/crafting_system/cli/_report.py`, `_route_view.py`, `_plan.py`); the others print nothing, or one `Error:` line |
| M3 | `NoPolicyError(ValueError)` (`solver/_tail.py:51`) | `solver/_tail.py:118` (the coarse models have no proper policy from the start) | `cli/_approx.py:312`: for a tail-cut level `continue`, for any other level re-raised | the levels before it stand; the ladder note names no tail cut |
| M4 | `BlockHoldsMetamod` (`abstraction/_coarse.py:540`) | `_coarse.py:540` | `cli/_approx.py:135` (re-raised: "a model without them is no bound") and `:309` (`stopped = ... a block holds a metamod`, next level) | the `stopped` text enters the approximate answer's message (`_approx.py:324-330`) |
| M5 | `LevelTimeout(RuntimeError)` (`cli/_approx.py:298`) | `cli/_approx.py:298` (C6) | `cli/_approx.py:306-308` | the same `stopped` text |
| M6 | `BranchingError(ValueError)` (`risk/_nested.py:70`) | `risk/_nested.py:183` (inputs that depend on themselves) | not caught below `cli/_main.py:171` (a `ValueError`) | one `Error:` line |
| M7 | `NotSubcritical(Exception)` (`risk/_inputs.py:57`) | `risk/_inputs.py:192,195,213,215,233,235` | `risk/_evaluate.py:235` (the policy is called improper), `risk/_mean.py:34` and `risk/_visits.py:42` (the mean or the visits become `INFINITE`) | a quantile reported as unresolved; "not resolved on the grid" is shared with the p90 cut (audit SOLVER-6) |

Tests that touch this family: `tests/test_cli_decide.py:93` (an estimate that could not be made means the exact run), `tests/test_cli_approximate*.py`, `tests/test_solver_*.py`, `tests/test_risk_inputs*.py`; none asserts that an answer says why a forecast or a reduced model fell back.

### 5.6 Display limits

| ID | Place | Limit | Stated |
|---|---|---|---|
| V1 | `_report.py:42` | text tree depth 40 | "continues below" `:366` |
| V2 | `_report.py:43` | text tree 1,000 states | `:364,376` |
| V3 | `_report.py:45` | dropped offers grouped past 300 | `:318-324` |
| V4 | `_report.py:152-193` | `number_states` and `describe_state` show mods only when the model tracks them (junk as a count) | no |
| V5 | `_route_flow.py:50-51` | page step chain not solved above 1,500 steps; grouping stops at 250,000 | `Note` for the first only |
| V6 | `_route_view.py:564-575`, `_route_flow.py:194-235` | one page step per class of states with the same chance (audit PRES-1) | no (#407, #408) |
| V7 | `_plan.py:39,115-120` | lumped chain over 1,000 policy states | `note` |
| V8 | `_reach.py:15` | no reach probability above 400 transient states | no |
| V9 | `_route_view.py:515-523` | the page lists considered start options, never the refused | no |

### 5.7 Settings accepted and never read

From `reachability.md:137-173`: 24 settings and flags; 19 read; 5 never read: `recombinator_junk_craft` (`actions/recombinator.py`), `max_imprints` (`actions/imprint.py:65`), `price_source` and `price_gap_percent` (stop at `StartContext`, `cli/_starts.py:105-106,122`), `--price-source` (`cli/_main.py:101,134`). Two are read and turn every plan into a refusal: `memory_strands` and `--strands` (G1). Target keys nothing reads: `start_sockets_assumed`, `item_level_floor`, `tiers_top_at_item_level` (`reachability.md:223-225`). None of the five is shown in any answer. Issues: #406 (prices), #407 (imprints), audit PLANNING-6/7.

### 5.8 Status after #506

The two refusal families (5.5) and the rows of #467 and #480 below are done by #506. A row is either a `Limit` in `Plan.limits` (shown in the text, the JSON and the page) or marked as changing no answer, each with the test that shows it. The sources and their tests are listed in `tests/test_cli_limits_506.py`.

**The two families.** `ActionError` is no longer raised itself; every `except` clause that names a refusal names the family it means, and `tests/test_cli_model_gaps.py::CLAUSES` lists them all (the scan fails for a clause added, removed or changed). The 34 clauses of 5.5 became 41 handlers (a clause that records a gap is a pair), one more (`cli/_benchmark.py`, `ROUTE_ERRORS`, a tuple the search of 5.5 did not see) was found and narrowed, and `abstraction/_prime.py` (`ValueError`) is listed beside them. A game refusal stays silent. A model gap met by the walk or the solve is written in `Abstraction.gaps` and becomes the limit kind `model-gap`; the bound pruning no longer calls a model gap "the game refuses it wherever it can be".

| Row | Now | Test |
|---|---|---|
| K14, the silent skip of a model gap | limit `model-gap` ("Left out where the model has no rule"), the action and the number of states, the first causes | `test_cli_model_gaps.py` |
| G6 | limit `consumes-items` (the kernel raises `ConsumesInputsError`, a model gap of its own kind) | `test_g6_*` |
| G17 | the twins of the packed path and of an approximate answer are the limit of K15 | `test_prune_forecast.py::test_g17_*` |
| K13 | limit `proved-unneeded` ("Offered only once the rest of the target is met"), exact | `test_k13_*` (three files) |
| C15, V8 | limit `state-line` ("The chance of reaching each state is not shown") | `test_c15_*` |
| V4 | limit `state-line` ("A state does not list the other mods", or "only as a count per side") | `test_v4_*` |
| C19, M1 | the text of `EstimateRefused` is in the limit of the whole search | `test_m1_*` |
| M2 (rate) | limit `how-solved` ("The solver's speed was guessed") | `test_m2_rate_*` |
| M2 (bound pruning) | limit `how-solved` ("All the actions were solved") | `test_m2_prune_*` |
| M3 | limit `how-solved` ("Levels skipped") | `test_cli_approximate.py::test_m3_*` |
| M7 | the cause is `GridInfo.cause` (`subcritical` or, for inputs in a cycle, `unordered`), its own limit and its own quantile text | `test_risk_inputs.py::test_m7_*` |
| C24, C25, C27 (dense), and C23 | each source writes the words of its give-up in `GridInfo.gave_up`; the limit says the percentiles came from a slower method | `test_c24_*`, `test_c23_*`, `test_c25_*`, `test_c27_a_coarse_*` |

**Shown not to change an answer** (so not a limit): C26 (`TINY` drops mass below 1e-150 per cell and counts it as unresolved; the most it could drop is far below the rounding allowance; `test_risk_inputs.py::test_c26_*`), C27 (`PACKED_FROM_EDGES`: the packed moments are the same numbers, certified; `test_c27_the_packed_moments_*`), C31 (`WORK_LIMIT`: an elimination that gives up leaves the sweeps, which certify every value or end in `ConvergenceError`; `test_solver_branching.py::test_c31_*`).

**Not done here, filed (OR-29):** a model gap met while the actions of a kind are listed (`actions/fossil.py` three clauses, `actions/corruption.py` `_vaal_orb`, `actions/recombinator.py` `junk_craft_for`) still drops the action without a word: #511. The interval driver's mean and visits (`risk/_mean.py`, `risk/_visits.py`) and the route page's quantile text still lack the cause of M7: #512 (the page text is decided at page build time, with #489 and #481). `solve_pruned` reports `fell_back` for a pruning it never tried: #513. K5, K6 and K10 of #467 were done by #459; the page's own "Note" is #489.

## Part C. The smallest type or field changes that would carry this

Options only; nothing is chosen. Counts are of files that name the thing (`grep -l`), so they bound the edit and do not predict it. "Tests" counts test files; "goldens" counts files in `tests/golden/` (16 html, 8 json, 2 txt, 1 md).

### Step 3

**3-A. `ExplicitMod.tier: int | None`, with `None` meaning "no tier in the data".**
- Types: `items/model.py:113` and the check at `:209-214`.
- Writers to change (T1 to T23 and T28): 14 files in `src/` (bench, beasts, beast_mods, influence, outcomes, veiled, awakener, harvest_augment, recombinator, `items/model.py`, `abstraction/_kernel.py`, `cli/_benchmark_outcomes.py`, `targets/parse.py`, `targets/floor.py`).
- Readers that decide something with an item's stored tier: `targets/model.py:55` and `abstraction/_kernel.py:811` (into `status_of`, `_state.py:269-289`). The table tier is passed on by `_kernel.py:958,973` and `_rolls.py:104,124`; `recombinator.py:253` builds a key string.
- Needs a rule for what a `None` tier meets: the judgement `status_of` / `Requirement._counts` would change in two copies, and the oracle in `tests/oracle/goal_oracle.py` is a third reader. The places that already refuse when there is no tier (R1 to R4 in 3.2) would then have to say whether `None` is "no tier" or "cannot spawn".
- Tests: 31 files read `.tier`; 35 helper sites (3.2) default to 1; 88 files name `ExplicitMod`. The 12 strict xfail classes of `tests/test_goal_oracle_comparison.py:67-81` would turn into failures to delete; `tests/reconcile/known.py:71-72` is unaffected.
- Goldens: those that print a tier note (`T<n>` is computed from `tier_table`, not from the item) do not change.

**3-B. `ExplicitMod.origin: Origin` (an enum such as rolled, crafted, essence, veiled, elevated, beast), `fractured` kept as the second, independent flag.**
- Types: `items/model.py:103-116`, the domain check at `:358-361` becomes "origin agrees with the domain".
- If `crafted` stays only as a read-only property of `origin`, it can no longer be a constructor keyword, so every `ExplicitMod(..., crafted=...)` and every test helper `roll(..., crafted=True)` breaks, unless `crafted` is kept as an `InitVar` (or a custom `__init__`) that sets `origin`. The callers: 9 places in `src/` that pass `crafted=` to the constructor (`_kernel.py:385,1123-1129,1142`, `beasts.py:239`, `beast_mods.py:145`, `bench.py:120,156`, `_benchmark_outcomes.py:52`, `parse.py:1088` through `**flags`) and, in `tests/`, 233 lines with `crafted=True` in 57 `.py` files (75 test files pass `crafted=` in some form: 295 hits). The earlier figure of 776 counted `crafted=True` in every file of `tests/`; 543 of those 776 are repr text in `tests/golden/plans_118.json`, and the other 233 are the `.py` lines above. The readers D1 to D26 of the property do not change. Writers (W1 to W21) in 14 `src/` files must set `origin`.
- The state: `Slot.crafted` (`abstraction/_state.py:73`) and its readers in `_kernel.py`, `_coarse.py`, `_estimate.py`, `_inputs.py`, `_bound.py` (7 files in `abstraction/` mention the flags) change only if the state has to tell essence-forced or Elevated apart. That changes `CompressedState` equality and the two goldens that print states or hash them: `tests/golden/plans_118.json` (the reprs of the R05 policy states, among others) and `tests/golden/b1_unchanged_142.json` (hashes of kernels and offers).
- Existing derivable origins (S4 to S7) remain facts of the data.

**3-C. A target-side switch for "any tier".** A leaf's omitted `min_tier` stops meaning "any" (T24, T25, T26): `targets/parse.py:415-436`, `targets/model.py:25-63`, `abstraction/_goal.py:27,178`, `targets/floor.py:137,165`. Needs the syntax of #410 point 1. Files that name `min_tier` or `not_crafted`: 12 in `src/`, 42 in `tests/`; 14 target files; `Wanted(` is built in 1 `src/` file and 71 test files (317 hits), none edited if a field is added with a default.

**3-D. A start price that is a fact, not a number.** Options: (i) `Target.start_price` required (`targets/parse.py:221`), which changes three target files (J01, R03, R06) and the 40 test files that write target YAML with `start_price` text; (ii) split "free" from "not buyable": `StartPrice` (`_plan.py:76-82`) gains `restart: bool` or `chaos: float | None`, read at `_plan.py:340`, `_route.py:253,460`, `_route_view.py:388,467,527`, `_benchmark.py:458,640`, `_starts.py:55-57,89`. Tests: 13 files name `StartPrice` or `plan.start_price`; 6 tests pin P3 and P4 (3.4).

**3-E. Claims: `approximate` checked against the text.** `rules/registry.py` gains a check (a statement that starts with, or holds, `APPROXIMATE`/`UNVERIFIED` needs the field); the 15 claims get `approximate: true` and a reason in 6 YAML files (`awakener`, `harvest_augment`, `harvest_swap`, `imprint`, `recombinator`, `recombinator_cost`). Tests: `tests/test_actions_imprint.py:236-247` asserts the opposite for 3 claims; 12 test files load the registry. Two claims with the marker mid-statement (A6, A7) and two with "not approximate" in the text (hinekora) fix the shape of the check. No benchmark answer changes (3.5).

**3-F. Start item stated or made up.** A field on `Target` such as `start_item_source` (given, default normal, empty rare stated), like `start_sockets_assumed`, which nothing reads today. Types: `targets/model.py:262-296`, `targets/parse.py:229-231,954`. Tests: 11 files construct `Target(`, two goldens print a `Target` (`target_quality_plain.json:52`, `target_sockets_six_link_colours.json:85`). With a default value no test constructor changes.

### Step 5

**5-A. One record type, one field on `Plan`.** `Limit(kind, what, why, guarantee, labels)` and `Plan.limits: tuple[Limit, ...]`, filled by the places that today write `left_out` (K4, K7 to K9, K15), `dropped` (K12), `note` (G12 to G14, G19, C18, C19), `strands` (G1), `approximation`, plus the withheld kinds (K1 to K3, K5, K6, K10), the skipped offers (K13, K14), the silent cuts (G6, G17, C15, V8; the unread `Pruned.fell_back` and `Pruned.why`, M2), the limits of 5.4 and the price facts (5.3).
- Types: `cli/_plan.py:85-107`, `cli/_offers.py:143-158`.
- Renderers: `_report.py` (text near `:315-327`, JSON near `:528-532`), `_route_view.py` goal card (`:547-557`).
- `Plan(` is built in 3 places in `_plan.py` (`:369,390,426`) and in 5 test files; a field with the default `()` leaves them unchanged. 30 test files name `left_out` (pattern `left_out`; `LeftOut` itself is named by no test file, 3 `src/` files); 12 test files match `plan\.dropped|DroppedOffer|dropped=`.
- Goldens: 2 text/JSON (`v01_minion_helmet.txt/.json`), and the html pages that would gain a field, up to 16; a page whose `limits` are empty need not change if the field is dropped when empty (`_fields` already drops `None`). `tests/golden/b1_unchanged_142.json` hashes `repr(LeftOut)` (`tests/b1_unchanged_support.py:52,61-62`), so any new field on `LeftOut` changes that golden.
- JSON format name `crafting-system-policy/1` (`_report.py:39`) is read by 13 test files that call `policy_document` and by the scripts of `.github/scripts` (12 name `make_plan` or the policy JSON).

**5-B. Model gap as data, not as an exception caught.** Record, at the three main skip sites (`_prune.py:86,129`, `_packed.py:124`), the `OutOfScopeError` that was swallowed, with its action, count and message, into the plan. The 84 raise sites and the other 31 `except` clauses (5.5) keep their behaviour. The second refusal family (M1 to M7) needs its own record or the same one: `EstimateRefused` loses its text at `_decide.py:264`, and `Pruned.why` is set and not read. Tests: 57 test files name `OutOfScopeError` (pattern `OutOfScopeError`); none asserts reporting. The two subclasses already exist (`actions/errors.py:37,41`), so no hierarchy edit is needed to tell the causes apart; the 27 clauses that catch the parent are where it is lost.

**5-C. Price provenance carried to the answer.** `StartPrice` and the 4th element of `PricedOffer.parts` carry `PriceEntry.note` and `detail` (or `Plan.price_facts` beside them), and the page prints them. Types: `_plan.py:76-82,231-252`, `_offers.py:46-57,109-127`. Readers: `_report.py:304-310,340-344,516-526`, `_route_view.py:390,466-474,555`, `_interval.py:324`, `_start_step.py`, `_start_options.py`. Tests: 12 files name `PricedOffer`, 13 match `StartPrice|plan\.start_price`; `test_cli_route_view.py:219` and 4 route goldens print the one-line "league ..., fetched ..." text. U5 to U7 show the data exists in `prices/` and is not read.

**5-D. A cut that names its guarantee.** `Decision`, `Approximation`, `Pruned` and `LeftOut` each get a `guarantee: str`; today only the `actions:` case has one (K17, `_offers.py:300-302`). Types: `_decide.py:122-138`, `_approx.py:60-66`, `_bound_prune.py` (`Pruned`), `_offers.py:143-149`. Small on its own; it needs 5-A to be shown, and a new field on `LeftOut` changes `b1_unchanged_142.json` (see 5-A).

### Counts and the pattern behind them

Taken once with a script (`re` over every `.py` file under `src/` and under `tests/`, files that match at least once), on the tree of `7c9e8df`. Patterns are regular expressions. The counts in Part C use these and no others.

| Pattern | `src/` files | `tests/` files |
|---|---|---|
| `ExplicitMod` | 18 | 88 |
| `\.tier\b` | 8 | 31 |
| `min_tier\|not_crafted` | 12 | 42 |
| `[^a-zA-Z_]Wanted\(` | 1 | 71 (317 hits) |
| `[^a-zA-Z_]Target\(` | 1 | 11 |
| `start_price` | 16 | 40 |
| `StartPrice\|plan\.start_price` | 11 | 13 |
| `left_out` | 3 | 30 |
| `LeftOut` | 3 | 0 |
| `plan\.dropped\|DroppedOffer\|dropped=` | 6 | 12 |
| `[^a-z_]Plan\(` | 1 | 5 |
| `PricedOffer` | 10 | 12 |
| `policy_document` | 3 | 13 |
| `OutOfScopeError` | 38 | 57 |
| `crafted=True` | 4 (9 hits) | 57 (233 lines; 257 hits) |
| `crafted=` | 11 | 75 (295 hits) |
| `mod_tier` | 2 | 3 |

Other counts: 12 files of `.github/scripts` match `make_plan|policy\.json|left_out_actions|dropped_actions|"totals"` (searched with the `Grep` tool); `tests/golden/` holds 16 html, 8 json, 2 txt and 1 md file; 84 `raise OutOfScopeError` (`grep -rn "raise OutOfScopeError" src`); 34 `except` clauses matching `except[^:]*(OutOfScopeError|ActionError|NotApplicableError)`.

### What the options share

- Step 3's 3-D and step 5's 5-C change the same type, `StartPrice`.
- 5-A's `Limit` would carry the 3.4 and 3.5 facts as well (a free start item, an approximate claim) if those are to be shown.
- 3-B's `origin` enum and 5-B's recorded gap both touch `abstraction/_kernel.py`, the largest file (1,932 lines).
- All options leave `tests/golden/reachability.md` valid except where a kind's `why_not` text or the gate list changes.

## Left open by this inventory

- Row counts in the first table count rows of the lists above; a row with several line numbers (for example D7, D12) is one place of one kind.
- Not re-measured: the audit's 1,322 of 2,200 forced mods without a tier and 614 weaker than T1; the section 3.7 counts are per target leaf.
- Scanned for constants, `raise`, `except` and limit words, with each hit read in context, but whose algorithms were not read line by line: `risk/`, `solver/`, `simulator/`, `abstraction/_coarse.py`, `abstraction/_inputs.py` and lines 290-420 of `abstraction/_estimate.py` (lines 1-290 were read through). 5.4 and 5.5 are only as complete as that scan.
- Searched only: `cli/_route_card.py`, `cli/_route_flow.py`, `cli/_interval.py`, `prices/` outside `price_file.py`.
- The 14 `examples/targets/` files were searched for keys and read for start items, not re-read for guide wording (#404).

## Open points filed as issues (OR-29)

- Lines no issue covered (essence-forced and veiled tier-1 fallbacks, price-0 code places, made-up start items other than R08 and R09): #453.
- The imprint test that pins three "UNVERIFIED" claims as not approximate, against the audit and #409: #454.
- The interval driver (`build_interval_answer`, `with_interval`) with no caller in `src/`, rebuild step 7: #455.
- The silent cuts and refusals of step 5 that no issue lists (G6, G17, K5, K6, K10, K13, K14, C15, V8, C19, C24 to C27, C31, M1 to M3, M7 and the silent skip of a model gap): #467.
