# Audit ticket #396: ACTIONS, PART 1 (common crafting actions and the shared action machinery)

Area: `src/crafting_system/actions/` files `contract.py catalog.py outcomes.py finite.py pool.py draw.py rolls.py cut.py metamods.py
mixture.py errors.py strand_use.py magic.py alchemy.py chaos.py exalted.py annul.py scour.py divine.py add.py bench.py essence.py fossil.py
fossil_weights.py harvest*.py fracture.py veiled.py quality_currency.py enchant.py` and their claims in `src/crafting_system/rules/claims/*.yaml`.
Read-only. Data: `local/cache/repoe-fork/3.29.3.3`. CONFIRMED means I reproduced it with a quick snippet (shown) or the cited lines say it
unambiguously. Line numbers are of the working tree at `86aa0b0`.

Read in full: every file above; the claim files `bench_craft essence fossils chaos_orb magic_orbs alchemy harvest_reforge harvest_augment unveil`
and the relevant claims of `divine_orb affix_count eldritch sockets`; `items/tiers.py`, `items/spawn.py`; the consumers `targets/model.py`,
`abstraction/_state.py` (`status_of`), `abstraction/_kernel.py` (`_drawn_contribution`, `_guard_roll`), `cli/_offers.py`, `cli/_marking.py`;
the contract suite `tests/test_actions_contract.py`, `tests/contract_support.py`.

Checked and found sound (so nobody repeats it): the pool/draw/weights engine (`pool.py`, `draw.py`, `fossil_weights.py`), the strand cut and guard
(`cut.py`, `contract.py` `_guarding_strands`), the refusals and results of Chaos, Alteration, Annulment, Scouring, Divine, Fracturing, the Harvest
reforges, the lock/tag logic of `metamods.py` read as written and agree with their claims. A Chaos/Scouring/Annulment/Exalted on an item holding a
placeholder plus an offer drops the offer correctly (run). The kernel refuses a roll limit on a crafted/forced/fixed-result new mod
(`abstraction/_kernel.py:948-954` `_guard_roll`, applied at `:1373` and `:1535`), so a roll requirement is refused, not misjudged at the lowest value.
Divine not rerolling base implicits agrees with the R06 guide (Blessed Orb exists for it). The faults below are at the seams: values the data
does not have (tiers), names, flags that are not the text, and what the tests compare against.

---

### ACT1-1: a bench craft is stored as tier 1 of whatever it crafts   [CONFIRMED] [impact: high]
- Where: `actions/bench.py:57` (`CRAFTED_TIER = 1`), `:120` (`BenchOutcomes.components`), `:156` (`sample`); readers `targets/model.py:56`
  (`mod.tier > self.min_tier`), `abstraction/_state.py:status_of`, `abstraction/_kernel.py:909` (`tiers.get(mod.id, 1)`); a second hand-written copy
  `targets/floor.py:57` (`BENCH_TIER = 1`, "`actions.bench.CRAFTED_TIER`").
- What it does: every crafted mod is written with tier 1, all 732 crafts, 141 of them on a ring. `family: IncreasedLife, min_tier: 1` is met by the
  cheapest craft (R05 ring: `HelenaMasterIncreasedLife1`, +(15-25), 1 Orb of Alteration; the ring's true top Life tier at item level 75 is +(100-114)).
- What it should do: a crafted mod has no tier in the data (it never spawns). Either it cannot satisfy a `min_tier` leaf (only `mod:` and `stat:`
  leaves name a craft) or it gets the tier its range would have in the family. Owner rule: a bench-forced mod is exactly that mod; an unstated tier is
  the top tier rolled, not from the bench.
- Evidence: `tier_table(data, ring)` holds no entry for any bench mod (domain `crafted`); the same constant is reused by `beasts.py:59`,
  `beast_mods.py:22,145`. Ticket #56's text lists refusals and costs, nothing about tiers.
- Impact: R05 (seed). Also every route whose leaf has `min_tier` and no `not_crafted`: R05, R06 (Life or armour `at_least`), R11 (`ChaosResistance
  min_tier 1`). R04, R08 to R10, R13, R14 write `not_crafted: true` on their tiered leaves and are protected by that, not by the model.
- Origin: `d1e63ed` "Bench crafts and Remove Crafted Mods as exact actions (#56)", 2026-10-31: `CRAFTED_TIER = 1  # ... Item needs one, from 1`.
  `targets/floor.py` copied the constant by hand in `d7cf1b0` (#352).
- Pattern: a type placeholder (`ExplicitMod.tier >= 1`) read later as game meaning.

### ACT1-2: every essence-only forced mod is stored as tier 1, although the data has no tier for it   [CONFIRMED] [impact: medium]
- Where: `actions/outcomes.py:77` (`tier_table(...).get(forced.id, 1)  # an essence-only mod has no tier: 1`) and `:272` (`self._tiers.get(mod.id, 1)`
  in `sample`). Reached by `ApplyEssence`, by the Hollow and Glyphic Fossil forced mod (`fossil.py:449` `retained_item`) and by the Veiled Chaos
  placeholder (`veiled.py:223`). The kernel repeats it: `abstraction/_kernel.py:909, 1071-1104, 1528` (`tiers.get(..., 1)`).
- What it does: the forced mod is written as tier 1 and `Requirement._counts` accepts it for `min_tier: 1`.
- What it should do: as ACT1-1.
- Evidence (run):
  ```
  ApplyEssence('Whispering Essence of Hatred').outcomes(data, normal Paua Amulet ilvl 84).retained.mods
    -> [('ColdDamagePercentEssence1', 1, (6,))]        # "(6-10)% increased Cold Damage", required level 1
  natural tiers of family ColdDamagePercentage on that amulet: T1 (23-26) lvl 64 ... T5 (10-12) lvl 12
  Requirement(family=ColdDamagePercentage, min_tier=1).is_met_by(a sampled result) -> True
  ```
  Of the 2,200 (essence, item class) forced mods in the data, 1,322 are absent from the tier table of a representative base; for 614 of them the level
  order gives a tier worse than 1 (Whispering to Wailing Hatred and Anger, Fear, Contempt, Dread, Doubt, Zeal ...).
- Impact: latent for today's benchmark targets (they name essence mods with `mod:`); wrong for any target that writes `family + min_tier` where an
  essence or a corrupted essence reaches the family.
- Origin: `b0e33b3` "Essences as exact actions (#55)": the ticket says only "The forced mod is the one essences.json mod id". Same placeholder.
- Pattern: a type placeholder read as game meaning.

### ACT1-3: an unveiled (Pick) mod gets the tier of a one-mod group, so a +(55-60) Life mod meets "Life tier 1"   [CONFIRMED] [impact: medium]
- Where: `actions/veiled.py:444` (`tier_table(data, item.base_id).get(chosen.id, 1)`); the table groups by `(mod.type, generation_type, domain)`
  (`items/tiers.py:54`) and the unveiled mods are a domain of their own, each its own type, so each is tier 1 of its group.
- What it does: `Pick` writes `JunMasterVeiledBaseLifeAndManaRegen_` (+(55-60) maximum Life, level 60) as tier 1. The target's `family: IncreasedLife`
  has 340 mod ids and includes it.
- What it should do: a mod's tier in a family is by level against the family's other mods (natural Life runs to +(160-174)); an unveiled mod cannot be
  "tier 1 of Life".
- Evidence (run): R09 target base (`BootsAtlas1`, ilvl 86), item with `VeiledPrefix` and offer `('JunMasterVeiledBaseLifeAndManaRegen_',)`;
  `Pick(1).outcomes(...)` result mod `('JunMasterVeiledBaseLifeAndManaRegen_', 1, (55, 320))`; the R09 leaf `IncreasedLife min_tier 1 not_crafted`
  `.is_met_by(result)` -> `True`. Six unveiled mods share a family with natural mods on boots (Life, Mana, Movement Speed x3, Energy Shield and Life).
- Impact: the veiled kinds are `opt_in`; a plan that names them counts a Life or Movement Speed tier 1 the game would not give.
- Origin: `a80f9b6` "Veiled Chaos, Veiled Exalted, Unveil and Pick as exact actions (#144)".
- Pattern: a type placeholder / a group definition read as game meaning.

### ACT1-4: Orb of Alchemy, Orb of Scouring and the two likelihood reforges are not planner kinds, the reason on file is stale, and no answer says they were never considered   [CONFIRMED the silence; SUSPECTED the cost effect] [impact: medium]
- Where: `actions/alchemy.py:71`, `actions/scour.py:133`, `actions/harvest_likelihood.py:103-108` (`planner=False, why_not="not in the B1 offer set; which
  actions a target needs is pruning (#118)"`); `cli/_offers.py:294-298` builds the "left out" list from `kinds(planner_only=True)` only; `_split_names`
  raises "cannot be used by the planner yet" if a target names them (`tests/test_cli_offers.py:181`).
- What it does: ADR-0013 lists Alchemy and Scouring among the ten B1 core actions; ADR-0024 says they are not usable yet. Ticket #118 (pruning) closed
  on 2026-11-01, the flags and reasons were not revisited. A report says "the plan is the cheapest among the named kinds" and lists skipped planner
  kinds; these three are not on that list because they are not planner kinds at all.
- What it should do: offer them (scour + alchemy gives the same 4/5/6 draw as a Chaos Orb and costs less whenever Scouring + Alchemy is cheaper than
  one Chaos Orb) or print them as "not considered" on every answer. Owner rule: say what is left out.
- Evidence: the lines cited. I did not solve a route to measure the price effect.
- Impact: every plan that rerolls a rare item; its cost can be overstated by the price difference; the owner is not told.
- Origin: `caf3bcb` (#108); never revisited after #118.
- Pattern: a silent exclusion whose stated reason went stale.

### ACT1-5: bench craft labels hide the tier, range and cost, and show an internal mod id when two crafts read alike   [CONFIRMED] [impact: medium]
- Where: `actions/bench.py:69-76,170-176` (`label` = `without_ranges(text)`), `cli/_offers.py:282-286` (appends `[variant]`, the mod id).
- What it does: `Bench craft +# to maximum Life` is three crafts on a ring: +(15-25) for 1 Orb of Alteration, +(26-40) for 6 Orbs of Transmutation,
  +(41-55) for 2 Orbs of Alchemy. The planner shows them as `Bench craft +# to maximum Life [HelenaMasterIncreasedLife1]`, `[EinharMasterIncreasedLife2]`,
  `[EinharMasterIncreasedLife3]` (run: `offers_for` on the R05 ring). Of the 1,853 (item class, label) pairs of the bench, 1,334 hold two to four
  crafts under one label; on boots 45 of 64 labels, on rings 45 of 80.
- What it should do: the label is what a player does ("+(41-55) to maximum Life"); a game-file id is not for the owner (brief: internal ids on the
  page). SUSPECTED: this is related to the seed where R05's bench step shows one range and its result another (the page rebuilds from the
  generic label and the state's representative mod); I did not trace the page.
- Evidence: run above. `test_actions_that_share_a_label_differ_in_their_variant` only checks `(label, variant)` is unique, which a mod id always is.
- Impact: every route page with a bench step; a given route's `do:` cannot say which craft.
- Origin: `d1e63ed` (#56) `without_ranges`; the suffix in `cli/_offers.py`.
- Pattern: a label derived from internal data instead of from what the action does.

### ACT1-6: Pick's simulated result never rolls the unveiled mod   [CONFIRMED] [impact: low]
- Where: `actions/veiled.py:427-445` returns a plain `Finite` (docstring of `finite.py`: "a new mod stays at its lowest values (`sample` rolls none)");
  the other value-carrying `Finite` actions use `RolledFinite` (`harvest_augment.py:73-95`) and the draws roll in `Outcomes.sample`.
- What it does: run, 20 seeds, `Pick(1)` on the offer above: values always `(55, 320)`; the mod is +(55-60) in the data.
- What it should do: roll 55..60 like the Harvest add and every drawn mod.
- Impact: only the simulator (`outcomes(...).sample`); the exact solver refuses a roll limit on it (`_guard_roll`).
- Origin: `a80f9b6` (#144).
- Pattern: a seed value ("lowest") that exists so the result is an `Item`, kept in the sampler.

### ACT1-7: six Harvest claims say APPROXIMATE (ADR-0028) in their text, but `approximate: true` is missing, so no answer lists them   [CONFIRMED] [impact: medium]
- Where: `rules/claims/harvest_augment.yaml` (`removal_uniform_among_removable`, `addition_weighted_by_tier_weight`), `rules/claims/harvest_swap.yaml`
  (`damage_source_stats`, `uniform_among_sources`, `respects_side_locks`, `fractured_and_crafted_mods_not_swapped`).
- What it does: the header of `harvest_augment.yaml` says "ticket #143 turns that sentence into the registry's `approximate` mark". The field exists
  (24 claim files use it, e.g. `unveil.yaml`) but these six do not carry it. `cli/_marking.py:217` keeps only `rule.approximate`.
- What it should do: carry the flag and a reason so the "Approximate inputs" of a route using a Harvest add/remove or swap name them.
- Evidence (run): load the registry, filter `not r.approximate and 'APPROXIMATE' in r.statement` -> exactly these six ids (other hits are
  `UNVERIFIED` research notes of other families).
- Impact: the 11 add/remove crafts and 12 swaps show no uncertainty although their own claims say the removal choice, the addition weights and the whole
  damage-swap set rest on Craft of Exile's code or a choice of the main chat only.
- Origin: `c9f6fb9` / `0c499a4` (#148). The prose marker was written; the field was never added.
- Pattern: a rule's status kept in prose, not in the field the machinery reads.

### ACT1-8: `Adds.keeps_crafted=False` ("erases the crafted mods") is false on an item with a Prefixes/Suffixes Cannot Be Changed metamod   [CONFIRMED] [impact: low-medium]
- Where: `chaos.py:63`, `scour.py:108`, `magic.py:98,136`, `alchemy.py:55`, `essence.py:69-72`, `fossil.py:300-304`, `harvest.py:74`, `harvest_influence.py:55`,
  `harvest_likelihood.py:70`; the lock logic `metamods.py:96-99` (`kept_by_reroll` keeps every mod of a locked side, crafted or not).
- What it does: the flag is declared once per action, not per item. `cli/_offers.py` (docstring of `offers_for`) leaves out a bench craft that
  counts for nothing "while every other offered action erases the crafted mods ... this is exact".
- What it should do: `keeps_crafted=True` where a lock can keep a crafted mod (or depend on the item).
- Evidence (run): boots with crafted `StrMasterItemGenerationCannotChangePrefixes` and crafted `HelenaMasterIncreasedLife1`: `ChaosOrb().adds(...).keeps_crafted`
  is False, yet the sampled Chaos Orb result and the Scouring result both keep `HelenaMasterIncreasedLife1` (crafted). `check_declarations_agree`
  ("an action that erases the crafted mods leaves none") passes because no fixture item holds a crafted mod on a locked side.
- Impact: plans with a lock metamod and a crafted mod on the locked side: the "craft that counts for nothing" pruning is not exact there.
- Origin: `6982b2c` (#108) introduced `keeps_crafted`; locks (#68, `83626ba`) later made the case possible without revisiting it.
- Pattern: a declaration true in the common case, with a fixture that never meets the other.

### ACT1-9: counts and ratios stated as sourced that the quoted source does not contain, not marked approximate   [SUSPECTED] [impact: medium]
- Where: `rules/claims/alchemy.yaml` `alchemy.count_like_chaos` (4/5/6 at 8:3:1 for Alchemy; essences on a normal item and Binding inherit it:
  `essence.forced_mod_counts_in_total`, `sockets.binding_rolls_like_alchemy`); `rules/claims/magic_orbs.yaml` `magic_orbs.magic_mod_count` (1 or 2 mods
  "each with chance 1/2", `value: {1: 1, 2: 1}`).
- What it does: the first says "the wiki says only 'from four to six'" and quotes a Craft of Exile line about scour-alching; the second quotes "one or two
  random explicit mods". Neither quote carries the weights (8:3:1, 1:1); both rest on "decision D3 / D1 of issue #28" and neither has the `approximate` mark.
  Alchemy, Transmutation and Alteration chances (every magic-item route: R13, R14, V01) are built on them.
- What it should do: a source for the weights, or `approximate: true` with the reason, so the answer lists it.
- Evidence: the claim texts. I could not open the wiki (Anubis block) to settle the true weights.
- Impact: unknown; if the true weights differ, every Transmutation/Alteration/Alchemy chance is off.
- Origin: research tickets #7, issue #28 decisions D1, D3.
- Pattern: a decision recorded with a source whose quote does not carry it.

### ACT1-10: the contract suite compares each action with itself, on three members per kind, on amulet fixtures with a goal that has no tier or roll   [CONFIRMED] [impact: medium]
- Where: `tests/contract_support.py:256-264` (`contract_pairs(per_kind=3)`), `:189` (`GOAL`: three plain `Wanted`, no `min_tier`, `min_roll`,
  `not_crafted`), `:194-197` (`_roll` writes `TIERS.get(mod_id, 1)`: the ACT1-1 placeholder again), `check_declarations_agree` (`:514`).
- What it does: every declaration (`Adds.named`, `keeps_crafted`, `single_draw`, `Reads.junk`) is checked against `outcomes` of the same action: the code
  defines both sides. Of 732 bench crafts, 12,696 fossil sets on boots and 106 essences, three are met per kind and item. No check asserts that a stored
  tier equals the tier table or that a tierless mod is marked (ACT1-1/2/3), that a label names one craft (ACT1-5), or that `approximate` agrees with the
  text (ACT1-7).
- What it should do: an invariant "every `ExplicitMod` an action creates has a tier from the table or is marked tierless"; a goal with tiers and rolls
  in the fixtures; classes other than amulets for the classes with their own rules (Dagger/Rune Dagger, Staff/Warstaff essences).
- Evidence: the lines cited; the seed bug (R05) passed this suite.
- Impact: why ~30,000 green tests did not see ACT1-1 to ACT1-8.
- Origin: `caf3bcb` (#108) design: the suite must meet every kind without edits, so it samples.
- Pattern: a test whose expected value comes from the code under test.

### ACT1-11: the bench module says a craft is refused below the mod's required item level; the code does not, and the claim was deleted so R14 would pass   [CONFIRMED doc/code mismatch; SUSPECTED game fact] [impact: low]
- Where: `actions/bench.py:12-14` (module docstring: "below the mod's required item level"), `:207-244` (no check); claim `bench_craft.needs_item_level`
  (deleted in `b7cf22b`).
- What it does: `b7cf22b`: "Bench: drop the item-level gate ... it would refuse R14's own +2 support gems craft on a level 78 bow". In the data the
  `required_level` of that mod (`JunMaster2LocalIncreaseSocketedSupportGemLevel2`) is 80 and of R14's chaos-DoT craft 81; 126 + 6 crafts are level 80/81.
  The R14 target pins item level 78 ("78 or more" in the guide). The deleted claim had said "no wiki or official sentence states it".
- What it should do: the docstring should match the code, and "no gate" should be a claim with a source. The Craft of Exile line quoted in
  `essence.forced_mod_ignores_item_level` is `if(htilvl<=crsim_settings.ilvl||mod.id_mgroup==11||mod.id_mgroup==13||mod.id_mgroup==10)`: it exempts three
  mod groups from an item-level test and does not show that bench mods are among them.
- Evidence: reading; the required levels printed from `data.mods`.
- Impact: crafts above the item level are offered everywhere; if the game gates them, R14-like routes are cheaper than possible.
- Origin: `b7cf22b`, 2026-10-31 (#56 review).
- Pattern: a rule dropped because a benchmark would fail, with no source, while the docs still describe it.

### ACT1-12: Harvest quality enchants are labelled from words cut out of the dump's record ids   [CONFIRMED] [impact: low]
- Where: `actions/harvest_quality.py:60-67,85-86` (`_words`).
- What it does: `Harvest Quality Enchant Increased Life` (the enchant grants "+1 to Maximum Life per 2% Quality"), `... Increased Mana`, `... Accuracy Rating
  Increase`, `... Melee Weapon Range`, `... Area Of Effect`, `... Increased Attack Speed` (run: all 14 labels printed beside their mod text).
- What it should do: use the text of the enchant, as the bench label does.
- Impact: the `do:` text of a Harvest enchant step.
- Origin: #240.
- Pattern: a label derived from internal data.

### ACT1-13: `Action.claims()` names claims by what a module imports, not by what the action cites   [CONFIRMED] [impact: low]
- Where: `contract.py:738-749,788-798` (`_module_claims`: constants of the class's module, its bases and, one step, the `actions` modules it imports
  names from), patched by `cli/_marking.py:211-214` (a special case for `enchantment.crafted_slot_with_multimod_takes_the_larger`, a `jewel.*` prefix filter).
- What it does (run): Chaos Orb lists 24 claims, Orb of Transmutation 40, the fossil set 70; every action lists the approximate `jewel.reroll_mod_count`;
  the Fracturing Orb lists `jewel.fracturing_orb_works_on_jewels`, a fossil set `jewel.fossils_work_on_jewels`. A claim read inside a function
  (`rule_by_id` in `metamods.crafted_limit_of`) is missing and was re-added by hand in the CLI.
- What it should do: each action declares its claims; the CLI needs no prefix filter or one-off.
- Impact: noise now; a missed approximate input the day a claim is read through a function.
- Origin: `caf3bcb` (#108): "leans to naming too many".
- Pattern: attribution by a heuristic instead of by declaration.

### ACT1-14: 25 claims are verified at patch 3.29.0.3 (Craft of Exile's package) while the pin is 3.29.3.3   [CONFIRMED] [impact: low]
- Where: `rules/claims/{beastcraft 4, dominance 3, harvest_augment 5, harvest_reforge 2, harvest_swap 2, influence 4, metamods 2, unveil 1, veiled 4}.yaml`.
- What it does: the Craft of Exile code read for the Harvest add/remove and swaps, the influence reforge and the veiled/unveil rules is a snapshot
  older than the data. Owner rule: stale sources lose. The patch is written; nothing re-checks them on a patch.
- What it should do: re-read on the patch (`patch-update` skill) and set the patch, or mark them.
- Impact: low; unknown drift.
- Pattern: a source version that is not the pinned version.

### ACT1-15: the contract cannot say "I read this family only as far as a later decision sees it", so every adding action splits states   [SUSPECTED, link to the brief's V01 seed] [impact: medium]
- Where: `contract.py:236-239` (`Reads.adding`), `magic.py:174-175,213-214` (Augmentation, Regal: `Reads.adding(variants=True)`), `exalted.py:61-62`.
- What it does: an adding action declares `junk=True, pool_weight=True`, so the state keeps a family type per junk family. That is exact (the next
  draw does depend on the family left in the pool) but it is the opposite of the owner's rule "detail no later decision sees is not tracked at all".
  The contract has two settings, exact weights or erase, and its docstring calls the first "exact".
- What it should do: a declaration (or ADR) saying which later decisions read a family, so the rest is merged; at least say in `Reads.adding` that
  exact tracking is a choice that costs states.
- Evidence: the contract text. The V01 symptom (eight identical "Regal Orb" steps) I did not reproduce; the abstraction is another auditor's.
- Origin: `contract.py` design of #108 / #67.
- Pattern: exactness where a decision-relevant approximation was wanted.

---

## Patterns seen in this area

1. **A type placeholder read as game meaning** (tier 1 for any tierless mod, "lowest values" for new mods): ACT1-1, ACT1-2, ACT1-3, ACT1-6. `ExplicitMod`
   needs a tier and values; when a mod has none in the data (crafted, essence-only, unveiled) the code writes 1 and the lowest roll, and
   `Requirement._counts` / `status_of` compare them. Nothing says "this mod is tierless".
2. **A label made from internal data** (mod ids, ranges stripped, words cut from record ids): ACT1-5, ACT1-12.
3. **Status kept in prose, not in the field the machinery reads** (APPROXIMATE only in the text; a stale `why_not`; a docstring describing a deleted rule;
   "ticket #143 turns that sentence into the mark"): ACT1-4, ACT1-7, ACT1-11.
4. **A declaration true in the common case, a fixture that never meets the other** (`keeps_crafted` vs locks): ACT1-8.
5. **A decision recorded as sourced although the quote does not carry it, and not marked; a source older than the pin**: ACT1-9, ACT1-14.
6. **Tests whose oracle is the code under test, on a thin sample**: ACT1-10 (and why ACT1-1 to ACT1-8 passed).
7. **Silent exclusion**: kinds that are not planner kinds (or are `opt_in`) never appear in "left out", so the owner cannot see what the "cheapest" plan
   did not consider: ACT1-4.
8. **Attribution by heuristic** (claims by import): ACT1-13.
9. **Exact where a decision-relevant approximation was wanted** (`Reads.adding`): ACT1-15.
