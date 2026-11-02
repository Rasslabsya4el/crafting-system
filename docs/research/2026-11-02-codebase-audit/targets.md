# Audit TARGETS (ticket #396): how a target is read and what "met" means

Auditor: TARGETS. Read-only. Code read in full: `src/crafting_system/targets/*` (model, parse, resolve, floor, corrupted, enchantment, lines),
`abstraction/_goal.py`, `_state.py` (`status_of`), `_rolls.py`, the goal parts of `_kernel.py`, the tier-assigning code of `actions/`, the target
card of `cli/_route_card.py`, `cli/_plan.py` (`leaf_labels`, `resolve_start_price`), `cli/_start_options.py`. Every file of `examples/targets/` was
loaded against the real data (`local/cache/repoe-fork/3.29.3.3`) and every comment about a tier, a mod id, a range or a level was checked. Scripts
were run from the scratchpad (nothing in the repo changed); the numbers below come from those runs.

## What the code means, field by field (answer to the brief's first question)

| field / default | what the code does | where |
|---|---|---|
| `family: X` | every mod whose `groups` contain X, of ANY domain and generation type (uniques, implicit grades, crafted, unveiled, abyss/misc/sanctum, Influence). `AllDamage` = 229 mods, `IncreasedLife` = 340, `DefencesPercent` = 438 | `resolve.py:103`, `parse.py:404` |
| `stat: "text"` | every PREFIX or SUFFIX of any domain whose text equals the text after `(a-b)` -> `#` | `resolve.py:69-74` |
| `mod: id` | narrows the selector to that one mod; nothing checks that the base or the item level can ever hold it | `parse.py:410` |
| `min_tier` absent | ANY stored tier. There is no "top tier at the item level" in the code | `model.py:55`, `_state.py:280` |
| `min_tier: N` | stored `ExplicitMod.tier <= N`. The stored tier is whatever the producer wrote: table tier, or `1` for crafted, essence-only, aspect, Elevated, tierless unveiled/harvest/awakener/recombinator mods, or a hand number in a start item | see TARGETS-1, -5 |
| `not_crafted` absent | a crafted (bench/metamod) mod counts. Fractured, essence-forced, harvested, unveiled mods are always "not crafted" | `model.py:57` |
| `min_roll` | positional, one slot per stat of the mod, compares the stored base roll; a mod with another number of stats never matches. Drawn mods get an exact roll law; forced/crafted mods with a roll limit raise `OutOfScopeError` | `model.py:59-63`, `_kernel.py:948` |
| `at_least k of` | k members met; members are independent, one mod may serve two members (documented) | `model.py:82`, `_goal.py:93` |
| `implicits`, `min_grade`, `quality`, `sockets`, `corrupted` | checked on their own; grade is "higher is better", tier "lower is better"; presence variants of Eldritch implicits are skipped unless `mod:` names one | `model.py:96-255` |
| `start_price` absent | the start item is FREE (ADR-0008) | `_plan.py:216` |
| `start_item` absent | a fresh NORMAL item of the base, the target's level and influences | `parse.py:954` |
| start mod `tier:` | stored as written, never compared with the data | `parse.py:1075` |
| `actions` absent | the default planner kinds only (opt-in kinds such as Exalted, Annulment, Fracturing, fossils, veiled orbs are left out) | `catalog.py:132` |
| `item_level_floor` / `tiers_top_at_item_level` absent | the floor is derived from the tiers asked, so the planner may plan a LOWER item level than the guide's (floor is not wired into the planner yet, see TARGETS-3) | `floor.py:247` |
| sockets asked, start sockets absent | one white unlinked socket is assumed (marked in `start_sockets_assumed`) | `parse.py:1006` |

How each kind of mod is judged against a tier (what is stored on the item, and so what `min_tier` sees):

| mod kind | stored tier | site |
|---|---|---|
| rolled / drawn | table tier (`tiers_of`) | `outcomes.py:272`, `_kernel.py:909` |
| bench crafted, metamod | 1 (`CRAFTED_TIER`) | `bench.py:57,120,156`, `beast_mods.py:145` |
| beast aspect mod (flagged NOT crafted) | 1 (second `CRAFTED_TIER`) | `beasts.py:59,239` |
| essence-forced | table tier if the mod is in the table, else 1 | `outcomes.py:77,272` |
| unveiled | table tier among the unveiled group, else 1 | `veiled.py:444` |
| Elevated | 1 (`ELEVATED_TIER`) | `influence.py:114,315,336` |
| harvest-added, awakener-kept, beast-mod, recombinator | table tier, else 1 | `harvest_augment.py:175`, `awakener.py:188`, `beast_mods.py:240`, `recombinator.py:513` |
| veiled placeholder | 1 | `items/model.py:171` |
| fractured start mod | the number written in the YAML | `parse.py:1075` |
| state rebuilt from a compressed state | table tier, else 1 | `_kernel.py:346,1071,1088,1097,1104,1528` |
| Eldritch implicit | no tier; `grade` 0..6, compared with `min_grade` | `model.py:132` |
| corrupted implicit | no tier; judged by `mod_ids` of the corrupted pool and `item.corrupted` | `model.py:125` |

How "top tier at the item level" is applied: nowhere in code. Each target file re-derives it by hand (the author reads the ladder and writes `min_tier: N`
or pins `mod:`), and states it in a comment. `tiers_top_at_item_level: true` only stops the planner from lowering the item level; it does not change
what a requirement accepts. I checked all 14 files: every hand-written `min_tier` equals the top tier spawnable at the file's item level
(script `toptier.py`), so no file is wrong on this point today. It holds by the author's care only.

## Findings

### TARGETS-1: a mod with no tier in the table is judged "tier 1" on 27 lines in 14 files; essence-only Life of 61-75 passes "Life T1, not crafted"   [CONFIRMED] [impact: high]
- Where: `abstraction/_kernel.py:346,909,924,1071,1088,1097,1104,1528`; `actions/outcomes.py:77,272`; `actions/bench.py:57,120,156`; `actions/beasts.py:59,239`;
  `actions/influence.py:114`; `actions/veiled.py:444`; `actions/awakener.py:188`; `actions/harvest_augment.py:175`; `actions/beast_mods.py:145,240`;
  `actions/recombinator.py:513`; `items/model.py:171`; `targets/parse.py:1073`; `targets/floor.py:57,229`; `cli/_benchmark_outcomes.py:52`.
  The seed (`bench.py:57`, `floor.py:57`) is two of the 27 lines; `CRAFTED_TIER` (bench.py), `CRAFTED_TIER` (beasts.py), `ELEVATED_TIER` and `BENCH_TIER` are four hand
  copies of the same `1`, each with a comment saying `Item` needs a tier from 1.
- What it does: `Item` needs a tier from 1, so every producer of a mod that has no row in `tier_table` writes 1, and `Requirement._counts` / `status_of`
  read it as "best tier". The fallback is a type placeholder read as game meaning.
- What it should do: owner rule "a mod forced by an essence or bench craft is exactly that mod/tier" means such a mod meets a leaf that pins it with `mod:`
  and must not meet a `min_tier` leaf by being tierless. A tierless mod should give BELOW to every `min_tier` leaf (or get a tier from its range on the
  ladder of its mod type) and the function must say which.
- Evidence (run):
  - `ApplyEssence("Screaming Essence of Greed")` on Sorcerer Boots stores `IncreasedLifeEssence5 (+61-75) tier 1 crafted False`; with
    `family IncreasedLife / min_tier 1 / not_crafted` `Target.is_met_by` is True. The real T1 on these boots is `IncreasedLife8 +(115-129)` (T2 is 100-114).
  - `Abstraction._drawn_contribution` (the solver's goal) gives PASSING to `IncreasedLife8`, `IncreasedLifeEssence5 (61-75)`, `IncreasedLifeEssenceBootsGloves1 (91-105)`
    and BELOW to `IncreasedLife7` (100-114): the 61-75 essence mod "beats" a 100-114 natural one.
  - Prevalence (`ess_count.py`): per example base 30-44 rare-capable essences force a tierless mod (coded T1); 3-10 per base are weaker than the natural T1 of their
    own mod type (Lion Pelt: Greed Life 61-75/76-90/91-105 vs 130-144; Sorcerer Boots: Woe ES 27-45 vs 39-49; quiver: Contempt added physical 9-12/19-22 vs 17-23/34-39).
  - R05 target with `HelenaMasterIncreasedLife1` (+15-25 Life, crafted) is `is_met_by` True as "Life T1" (the seed, shown for completeness).
- Impact: any target with a `min_tier` leaf and default `actions` (R05, R06, R10, R11 use `actions` absent). None of the 10 benchmark routes exploits the essence case
  today (R10/R11 need a different essence for their other leaf), the seed's bench case is the live one. A new target "T1 Life + T1 resists" with default actions will
  be answered with a Greed essence. The simulator (`--verify`) cannot catch it: `Outcomes.sample` (`outcomes.py:272`) writes the same tier 1.
- Origin: `.get(mod.id, 1)` in the first compressed state (#24, 55f8109, 2026-10-30) and the essence kernels (#59, 98891b3); `outcomes.py:77` got its comment
  "an essence-only mod has no tier: 1" in #55 (6fc8eab, 2026-10-31, titled "document the tier fallback"); `CRAFTED_TIER` in #56 (d1e63ed); aspect/Elevated copies in
  #147/#154; `BENCH_TIER` in #352 (d7cf1b0). The #60 brief asked only that the solver's mean be "no more than the guide's given route", which a loose reading satisfies.
- Pattern: a type placeholder (`1` to satisfy "tier from 1") read later as game meaning; one fact (the value of "no tier") copied by hand onto 27 lines.

### TARGETS-2: the default requirement means "any tier, any source"; the owner's "unstated tier = top tier, rolled" exists only in file comments   [CONFIRMED] [impact: high]
- Where: `model.py:7,55-57` (docstring: "how a mod got onto the item matters only when `not_crafted` is set"), `parse.py:415-436`, ADR-0008 ("How a mod got onto the item ... does not
  matter unless a requirement is marked not crafted"), `floor.py:257-258` + `parse.py:226` (`tiers_top_at_item_level`), `examples/targets/r05-strength-ring.yaml:22-28`,
  `r06-strength-heavy-belt.yaml:30-32`, `r12-lightning-amulet.yaml:16` vs `:28`, `r03-avoid-shock-boots.yaml:46-49`.
- What it does: absent `min_tier` accepts every tier, absent `not_crafted` accepts the bench, `family:` accepts every mod of the family (TARGETS-1 explains why a craft
  passes a tier). The owner's rule is encoded per file by hand (a number or a `mod:` pin plus a comment). `tiers_top_at_item_level: true` is not that rule: it
  only blocks lowering the item level (`floor.py:257`).
- What it should do: owner rule: "An unstated tier is the TOP tier the item level allows, rolled, not from the bench". A leaf with no `min_tier`/`mod` should say which
  of the two readings it has; the parser (or a `tier: top` key) should compute the number from the ladder, and the default `not_crafted` for a leaf the guide gives
  without a craft should be true.
- Evidence:
  - R05 file lines 22-28 write the opposite of the rule in the same file: "a crafted Life or Resistance counts too ... a bench craft counts as tier 1 of what it
    crafts whatever its range" (and offer `not_crafted: true` as the owner's switch). R06 lines 30-32 do the same ("so a crafted one counts too").
  - R12 contradicts itself: line 16 "No tier is written, so each mod is the top tier the item level above allows (the owner's reading of an unstated tier)", line 28
    "Every tier of the mod counts, because no minimum tier is given". The code does the second (`min_tier None`, any tier).
  - R03 (lines 46-49) sets `tiers_top_at_item_level: true` and says "The tiers of this target are the top tiers the item level above allows", but its `FireResist7` is tier 2 where tier 1
    (`FireResist8`, lvl 84) is open at item level 100 (the guide states T2). The flag pins the level at 100 (floor lowest would be 85, `Suppress T1` needs 85).
  - The `-70-life` variant of R10 reads the same sentence of the guide the other way ("names no tier, so no tier is asked", any tier whose roll reaches 70) from the
    plain R10 file ("the owner's rule ... is the top tier"). Both are in `examples/targets/`.
  - All 14 files: each hand-written `min_tier` equals the top tier spawnable at the item level (`toptier.py`); nothing enforces it.
- Impact: every route whose goal reads "T1/top ..." relies on the author. The page shows the leaf as "T1 +(100-114)" while the code accepts a +(15-25) craft (the seed's
  12 c against 135 c).
- Origin: ADR-0008 (design grill, 2026-10-30) fixed "origin does not matter unless not_crafted"; the owner's tier rule was added later (R05/R10/R11 comments in f52d61b, #96,
  2026-10-31) without changing the parser; #60 asked for "each reading noted in the file", so the rule lives in comments.
- Pattern: a default (written before the owner's rule) that decides a game question, and the rule that should replace it kept as prose in 14 files.

### TARGETS-3: the item level floor reads the tier-1 placeholder and a source the kernel refuses, so it can lower a target to item level 1 (not wired yet)   [CONFIRMED] [impact: medium]
- Where: `floor.py:223-231` (`_gates`), `floor.py:57`, `_kernel.py:948-954` (`_guard_roll`); consumers: none (`item_level_options`, `floor_of`, `target_at_level` are not called outside `targets/` and tests; #359 is open).
- What it does: `forced = ... _within(wish, tier if tier is not None else 1) ... yield MIN_ITEM_LEVEL` so an essence-only mod gives a `min_tier` leaf "level 1". With a roll limit the
  forced gate uses `high=True` although the kernel raises `OutOfScopeError` for a roll limit on a forced mod.
- What it should do: ADR-0061 says the floor is "the lowest level at which every requirement can be met"; a source that does not meet the requirement (TARGETS-1) or that
  the planner cannot model must not set it.
- Evidence (`floor_repro.py`, `rollguard.py`): Sorcerer Boots, `family IncreasedLife min_tier 1 not_crafted`, item level 84:
  `actions: [chaos-orb]` -> floor 54 (`IncreasedLife8`, pool); `actions` absent or `+essence` -> floor 1 ("from IncreasedLifeEssence5 (forced mod)").
  `stat "+# to maximum Life" min_roll [70] not_crafted` -> floor 1 from the same essence, while `Abstraction.kernel(state, ApplyEssence("Screaming Essence of Greed"))`
  raises "a roll limit on a forced, crafted or fixed-result new mod is not modelled yet".
- Impact: latent. Once #359 plans the groups from the floor, an unpinned target with a tier-bound leaf and essences offered is planned on a base of item level 1
  (a pool in which the tier cannot occur), or the group is silently dropped. R13 and R08 (unpinned) are safe only because their `actions` leave essences out.
- Origin: #352 (d7cf1b0, 668bfea, 3420d4a), 2026-11-01; "the crafted mod counting as tier 1" is written in the module docstring (`floor.py:11`).
- Pattern: a derived rule built on a placeholder; a second module (floor) re-deciding what the planner can do instead of asking it.

### TARGETS-4: R13's "crafted damage modifier" is met by a rolled one; the test that says "exactly two crafts" runs on fixture data where it is true and on the real data where it is false   [CONFIRMED] [impact: medium]
- Where: `examples/targets/r13-life-resist-belt.yaml:53-66`, `tests/test_targets_files.py:67-83` (`test_the_r13_damage_families_are_damage_prefixes_the_bench_offers_on_a_belt_in_two_tiers`), `tests/targets_support.py` / `tests/items_support.py:8` (`DATA = fixture_game_data()`, a hand slice of the export).
- What it does: the group is `family AllDamage` or `family IncreasedWeaponElementalDamagePercent`, with no `min_tier` and no `not_crafted`; the file says "the bench copy is crafted by nature,
  so these two carry no not_crafted mark".
- What it should do: guide R13: "crafted damage modifier" / "Multi-mod damage". The leaf should be the two bench families as crafts (`mod:` pins or `crafted` only).
- Evidence (`r13dmg.py`): on a real Leather Belt (ilvl 86) `IncreasedWeaponElementalDamagePercent` has six NATURAL spawnable tiers, `WeaponElementalDamage1..6_` (5-10% up to 43-50%),
  and each satisfies the leaf; only the 4th mod of the item must be a craft so R13's plan is unchanged by luck of its action list (3 mods after Regal). The leaf holds 229 (`AllDamage`)
  and 71 mods; the fixture test asserts `offered == member.mod_ids` and passes because the fixture family holds 2 mods; the same assertion on the real data is False
  (2 bench belt prefixes vs 229 and 71).
- Impact: a variant of R13 with an Exalted Orb would be met by a rolled damage prefix; the file's claim "no other damage prefix" was never checked on real data.
- Origin: R13 file (#58/#60 era) and the fixture test; no real-data twin of that test exists.
- Pattern: an oracle that checks a claim in a toy world; a family used as if it were "the stat".

### TARGETS-5: the tier (and value) of a start-item mod is hand-written and never reconciled with the data; R12 writes tier 3 where the table says 7   [CONFIRMED] [impact: medium]
- Where: `parse.py:1075-1077` (only checks "whole number >= 1"), `items/model.py:213` (tier stored as given), `examples/targets/r12-lightning-amulet.yaml:48-49`,
  `tests/test_targets_files.py:35` (pins `ExplicitMod("LightningResist2", 3, ...)` on fixture data) and `tests/test_targets_goal.py:86`
  (`test_the_stored_tier_is_read_and_never_derived`, pins "the stored tier wins even when it contradicts the data").
- What it does: `LightningResist2` on a Paua Amulet is tier 7 (`tier_table`, lvl 13, 12-17 of eight tiers); the file says `tier: 3`. `compress(start)` and `min_tier` use the 3. The other
  five start mods (R03, R05, R10 x2, R11) match the table (`starttiers.py`); the file comment says "check it by hand".
- What it should do: the start tier is a derived fact; `Item.build` (or the parser) should take it from `tiers_of`, or refuse a mismatch. Same for the value vs the buy spec: the target says
  R05 `values: [14]` and the spec prices `minimum: 13`; R11 33 vs 31 (the item bought is not the item planned).
- Evidence: `starttiers.py`: `r12-lightning-amulet.yaml  LightningResist2  written tier=3 table tier=7  <<<< MISMATCH`. R12 has no `min_tier` on that leaf, so no output changes today;
  a `min_tier: 3` on it would pass (the real T7 should fail).
- Impact: low today, but a hand number inside a fractured mod decides `min_tier` leaves and the "T3" shown for the start item; the mod of a bought item should be "the tier priced on the trade site".
- Origin: ADR-0008 "tier taken as written" (tier derivation did not exist; `items/tiers.py` came with #23) and never revisited; the parse docstring `targets/__init__.py:56` still says
  "tier derivation is not built yet".
- Pattern: one fact written by hand in two places (YAML tier and tier table; YAML value and buy spec minimum) with a test that pins the hand copy.

### TARGETS-6: the target card on the route page hides `min_roll` and `not_crafted` of explicit requirements and shows an arbitrary family member for bench-only leaves   [CONFIRMED] [impact: medium]
- Where: `cli/_route_card.py:254-283` (`_leaf_slot`: takes `mod_ids`, `min_tier`, `item_level`; never `min_roll` or `not_crafted`), `:342-357` (`card_of_target`), `:411-418` (`_StateReader.leaf`).
  `_wanted_implicit` (`:372`) does print "roll N or more", so explicit and implicit leaves differ.
- What it does (`card.py`): R10-70 Life leaf (roll >= 70, not crafted) is drawn as `+# to maximum Life · any tier`. R14 `IncreasedAttackSpeed min_tier 1 not_crafted` is drawn "(17-19)% increased Attack Speed · T1" with no "rolled".
  R13's damage group is drawn `(11-15)% increased Damage` (= `AllDamageInfluence1`, an influence mod a belt cannot hold; the fallback sorts by `(domain, mod_id)` and takes the first) and
  `#% increased Elemental Damage with Attack Skills · any tier` instead of the bench crafts (12-14)/(15-17). R05's group is drawn as four separate lines with five suffix lines on a ring that holds three (the seed).
- What it should do: owner rule: show what a player does; the card must say the roll floor and "not crafted", and a leaf that only a craft can meet should name the craft.
- Impact: the owner reads a goal the code does not enforce (and the reverse). The solver and the simulator agree with each other (they share the check), so the page is the only place the
  target is mis-shown.
- Origin: `_leaf_slot` written for #78/#96 around `min_tier` only; roll limits arrived with #71 and `not_crafted` earlier, the card was not extended.
- Pattern: output that shows a different requirement from the one enforced; a "first by id" fallback shown as meaning.

### TARGETS-7: the bench item-level gate is documented in two places and enforced in neither action nor claims, while the floor still applies it   [CONFIRMED] [impact: medium]
- Where: `actions/bench.py:12-14` (header: a craft is refused "below the mod's required item level"), `targets/floor.py:10-11,227-228` (a bench source sits at "the mod's own required level"),
  `BenchCraft.outcomes` (`bench.py:207-244`, no level check), `rules/claims/bench_craft.yaml` (claim `needs_item_level` deleted).
- What it does: `BenchCraft("EinharMasterIncreasedLife4")` (needs 75) and `JunMaster2BaseLifeAndManaRegen3` (needs 81) are ALLOWED on an item of level 40 (`benchlvl.py`). The floor treats the same
  crafts as level-gated (it computes a floor from them).
- What it should do: one answer. b7cf22b (#56) deleted the gate "because no admitted source states one, and it would refuse R14's own +2 support gems craft on a level 78 bow" (that craft is
  level 80, the chaos DoT multi craft 81). That is an unresolved source conflict decided by removal; it is not marked approximate anywhere, and `bench.py`'s header (restored by 85b36ce, #334) still
  says the opposite (that sentence was written on 2026-11-01 in 85b36ce, a day after the gate was removed).
- Evidence: `benchlvl.py` output; `git show b7cf22b`; `JunMaster2LocalIncreaseSocketedSupportGemLevel2.required_level == 80`, `JunMaster2ChaosDamageOverTimeMultiplier3 == 81`, R14 item level 78.
- Impact: bench-heavy routes (R05, R10, R11, R13, R14, R03) may use crafts above the item level; if the game gates them, the plan is not executable; if it does not, the floor
  (TARGETS-3) over-raises levels. `level_groups` (`floor.py:281`) also ignores bench levels in its change points (only the random-draw pool is looked at), so two levels with different bench
  options would be one plan.
- Origin: #56 (b7cf22b, 2026-10-31); #352 (floor) written afterwards on the other reading.
- Pattern: a doc/claim and a code path that disagree, with a module (floor) built on the doc.

### TARGETS-8: "no `start_price`" means the start item is free; R06, R03 and J01 are planned from a free item   [CONFIRMED] [impact: low]
- Where: ADR-0008 ("Without it the start item counts as free"), `cli/_plan.py:216-231` (`resolve_start_price`, line 229 labels it "the target names no start price, so the start item counts as free"),
  `examples/targets/r06-strength-heavy-belt.yaml` (no `start_price`), `r03-avoid-shock-boots.yaml:39-40` (says so), `j01-cobalt-life-attack-speed.yaml`.
- What it does: the guide for R06 starts "Buy a Hunter- or Elder-influenced Heavy Belt of item level 75 or more"; the file has a fresh Normal Hunter belt and no price, so step 1 costs 0 Chaos.
  The text report marks it ("[the target names no start price ...]"), so this is a default that is marked, not hidden.
- What it should do: owner rule "a bought start item ... is the tier priced on the trade site"; an unpriced bought item should be refused or marked approximate on the route page too, not zero.
- Evidence: file contents; `resolve_start_price`.
- Impact: R06/R03/J01 are not in `BENCHMARKS` and R06/R03 cannot be planned yet (#159 open: implicits/quality), so no published number is wrong today.
- Origin: #26 (R12 end to end), ADR-0008.
- Pattern: a default that decides a money question.

### TARGETS-9: invented start items: an empty "rare" with the Alchemy folded into a price (R08, R09, J01)   [CONFIRMED] [impact: medium]
- Where: `examples/targets/r08-energy-shield-boots.yaml:36-51`, `r09-life-boots.yaml:33-45`, `j01-cobalt-life-attack-speed.yaml:16-19`, `examples/buy/r08-start-boots.yaml:6-8`.
- What it does: the start is `rarity: rare, mods: []` (no such item exists in the game), the Orb of Alchemy of the real route is added to the price of the bought white base and the file says
  the model "starts from the rare boots with no mod". J01 says "a rare one with no mod, which is what you hold after you scour a rare jewel"; an Orb of Scouring leaves a Normal item.
- What it should do: owner rule "show every in-game step; never hide one (a bought item drawn 'empty' ...)". The route must show buy -> Orb of Alchemy -> fossils, or the state must be a
  legal one.
- Evidence: file text; the R08 comment concedes the cost is "too high by at most about one use of the first fossil set" because the Alchemy draw is free.
- Impact: the R08/R09 pages draw an empty rare; the comment says the pricing is wrong in one direction; the Alchemy is not a visible step.
- Origin: #63 (ba122bf) chose it because a plan with the Alchemy "did not finish in 60 minutes on a GitHub runner".
- Pattern: a value invented to make the model small, read as the real start.

### TARGETS-10: `min_roll` is positional across mods that do not share stat meaning; the best-roll check ignores base and level   [SUSPECTED] [impact: low]
- Where: `parse.py:438-484` (`read_min_roll`), `model.py:59-63`.
- What it does: it refuses mods with different stat COUNTS only. 342 of 2,844 families that hold prefix/suffix mods have mods with the same count but different stat ids (`rollstat.py`):
  `Strength` (1 stat: `additional_strength` vs `..._and_dexterity`), `IncreasedLife` (2 stats: life+life%, life+mana, life+mana regen). `min_roll: [70, null]` on `family: IncreasedLife` would apply "70"
  to life in one mod and to whatever stat sits first in another. The upper bound is the best roll over every mod of the selector (uniques, Influence, other classes), not of the base.
- Evidence: script output; no example uses a multi-stat family roll (R10-70 uses `stat:` for this reason, `r10-fractured-boots-70-life.yaml:57-64`).
- Impact: latent; agents who write targets are told only "same number of stats".
- Pattern: a positional contract with no identity check.

### TARGETS-11: stale or false statements in target docs and comments   [CONFIRMED] [impact: low]
- `targets/__init__.py:56` "tier derivation is not built yet" (`items/tiers.py` exists since #23); `bench.py:12-14` (TARGETS-7); `floor.py` docstring calls the bench tier 1 "whatever its range"
  as a feature; R03 `tiers_top_at_item_level` claim (TARGETS-2); R12 lines 817 vs 829 (TARGETS-2); R13 "carry no not_crafted mark" (TARGETS-4); J01 scouring sentence (TARGETS-9).
- Pattern: comments carry the reading, and drift.

## Checked and found consistent (so the next reader does not redo it)

- Solver goal vs simulator goal: `Goal.from_target`/`status_of` (through `Abstraction.compress` + `is_goal`) and `Target.is_met_by` give the same answer on 400 random items per target for R05,
  R13, R08, R10-70, R04 (0 mismatches, 39 of the 2,000 items met their target, `equiv.py`), roll limit and k-of-n included. A small sample, but the two share one code reading
  (`status_of` vs `Requirement._counts`), so they cannot catch TARGETS-1/-2 (a circular oracle, not a fault of either).
- Every comment's numbers about tiers, mod ids, ranges, levels, weights in R03-R14, J01, V01 matched the data except the points above: ladders of Life/Resistance/All Attributes/Strength/Armour/
  Attributes, `MovementVelocity` bench crafts and their levels (68 / 81), `AvoidShockEldritchImplicit1-6` ranges, V01 weights (250 of 114,675; +2 mod 25), R06 `PercentageAllAttributesInfluence1/2`.
- With a hunter influence `tiers_of` changes only the influence mods themselves (R06, R14); no ordinary mod is renumbered.
- `Requirement` leaves in the examples never mix two spawnable mod types of one family on the base (only `GlobalDamageTypeGemLevel` on amulets, which tiers.py documents as 5 types x tier 1).

## Patterns seen in this area

1. A type placeholder read as game meaning: tier `1` for "no tier" (TARGETS-1, -3), an empty "rare" (TARGETS-9), "free" for "no price" (TARGETS-8).
2. A default that decides a game or money question and predates the owner's rule: `min_tier` absent = any, `not_crafted` absent = crafted counts, `start_price` absent = free, floor lowers the
   item level (TARGETS-2, -3, -8).
3. One fact written by hand in several places with nothing reconciling them: the value of "no tier" (27 lines), start tier vs table, start value vs buy spec, the bench level gate (code vs docs vs
   floor), the reading of a guide sentence in comments (TARGETS-1, -2, -5, -7).
4. An oracle that cannot fail: tests on fixture data for a claim about real data, a test that pins the hand tier, a success criterion "solver <= guide" that a looser reading satisfies (TARGETS-2, -4, -5).
5. Output that shows a different requirement from the one enforced (TARGETS-6, -4).
6. The owner's reading kept as prose in 14 files instead of a field (TARGETS-2, -11).
7. A feature built before its consumer exists, on an unchecked assumption (the item level floor: no caller outside tests, #359 open) (TARGETS-3, -7).
