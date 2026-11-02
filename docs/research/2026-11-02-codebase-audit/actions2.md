# Audit #396: ACTIONS, PART 2 (the special mechanics)

Area: `src/crafting_system/actions/` awakener, beast_mods, beasts, blessed, bloodstained, catalyst, corrupted_pool, corruption, eldritch,
foulborn, hinekora_lock, imprint, influence, recombinator, socket_colours, socket_orbs; their claims in `rules/claims/*.yaml`; ADRs
0025 0027 0029 0030 0032 0033 0035 0036 0037 0041 0043 0045 0047 0054 0055 0060 0062.

Read in full: all 16 modules (4,726 lines), the claim files awakener, beastcraft, blessed_orb, catalyst, corruption, dominance, eldritch,
foulborn, hinekora_lock, imprint, influence, influence_beast, recombinator, recombinator_cost, sockets, vaal_orb, and the parts of
memory_strands that name these actions. Reproduction scripts (read-only, under a minute each) are in this folder:
`_a2_awk.py`, `_a2_awk2.py`, `_a2_beast.py`, `_a2_claims.py`, `_a2_elev.py`, `_a2_eld.py`, `_a2_sample.py`, `_a2_tier.py`,
`_a2_vaal.py`, `_a2_rec.py` (run with `PYTHONPATH=src python .claude/scratch/audit/<name>`).

What I found about the area as a whole: the exact mechanics that ARE built are careful (probabilities sum to 1, refusals are loud, rule
axes are named). The big problem is not wrong numbers in these actions, it is that almost none of them can be reached by a plan today
(section "Capabilities missing"), and that several rules they stand on are weak sources admitted without the approximate mark.
Placeholders of the seed kind exist here too (donor tier 1, Elevated tier 1, crafted tier 1) but mostly in actions no plan reaches yet.

---

## Capabilities missing from every plan today (planner=False, "not offered until #N", or refused by `make_plan`)

`make_plan` (cli/_plan.py:290-310) refuses with `PlanError` a target that names implicits or quality (:296, #159), sockets (:301, #231),
an enchantment (:306, #242), or strands (:290, #277); and builds the abstraction with `allow_inputs=False` (cli/_plan.py:347), so any action
that takes a second item is never offered; and refuses any offered action that reads a rule axis (cli/_plan.py:334-338). That is loud,
not silent. The catalog kinds below are therefore alive in tests only.

| Owner-visible capability | Kind(s) in my area | Blocked by | Benchmark routes that need it |
|---|---|---|---|
| Eldritch Embers/Ichors (put an implicit), Eldritch Chaos/Exalted/Annulment, Orb of Conflict | eldritch-implicit-currency, eldritch-chaos-orb, eldritch-exalted-orb, eldritch-annulment-orb, orb-of-conflict (`planner=False`) | target with `implicits:` is refused (#159 open) | R01, R03 (`examples/targets/r03-avoid-shock-boots.yaml` has `implicits:`), R22, R23, R30 |
| Blessed Orb, catalysts (quality line) | blessed-orb, catalyst | target with `implicits:` or `quality:` refused (#159 open) | R05 catalyst line (left out of the R05 target), R06 (`r06-strength-heavy-belt.yaml` has both) |
| Awakener's Orb | awakeners-orb | two-input actions: `allow_inputs=False`; receiver/donor state #214 open; end-to-end #224 open | R18, R19 |
| Recombinator (+ junk-craft variant) | recombinator | `allow_inputs=False`; compressed state #217 open; end-to-end #223/#225/#226 | R01, R25, R26, R27, R28, R29 |
| Imprint / Restore (beast imprints) | imprint, restore | end-to-end #223 open; strand declaration #291 open | R15, R17 |
| Influenced Exalted Orbs (6), Orb of Dominance, beast influence recipes | influenced-exalted-orb, orb-of-dominance, beast-influence-recipe | a goal built from a target does not name an influenced/Elevated mod yet | R02, R06, R20, R21 |
| Sockets, links, colours (Jeweller, Fusing, Chromatic, Omens, bench count/links/colours) | jewellers-orb, orb-of-fusing, bench-socket-count, bench-socket-links, chromatic-orb, bench-socket-colours | target with `sockets:` refused; finish #231 open | any socket target (R31-R33) |
| Orb of Binding, Black Mórrígan socket recipes | not built | #232 open | R31-R33 |
| Hinekora's Lock (look, then choose) | `HinekoraLock` is not an Action and is in no catalog | B8-3..B8-8 (#295-#299) open; the abstraction of `make_plan` has no Lock (cli/_packed.py:18), only the solver's `Peek` model exists | R29 and every Lock-priced route |
| Foulborn Exalted/Regal/Augmentation, the strand tier cut, Remembrance, Unravelling | foulborn-* (`needs_strands`) | strands are refused by `make_plan` (#277 open); the kinds are not even listed without `strands=True` | any stranded item |
| Locus of Corruption (two corrupted implicits) | not built | #262 open | corruption routes |
| Corrupt for a chosen implicit (Vaal, Bloodstained resonator) | vaal (`planner=True`) | corrupted-implicit targets are `implicits:`, refused (#159); the brick is a dead end until #260 | see ACT2-2 |
| Opt-in only: Wild Bristle Matron, Wolf/Lynx side swaps, aspects, Talisman fractures | `opt_in=True` | offered only if the target names them in `actions:` | R20, R22, R26, R30 |

Every row but the last is a ticket that is still open; none is an accident. What the owner should know: **today the planner can
plan fossils, essences, bench, Harvest, alteration/regal/exalt/annul/scour/divine/fracture/veiled and the opt-in beast crafts; it
cannot plan anything on the Eldritch, influence, implicit, quality, socket, recombinator, Awakener, imprint, strand or Lock axes.**

---

### ACT2-1: Two planner kinds that no useful plan can use: the Vaal Orb and the Bloodstained resonator   [CONFIRMED] [impact: medium]
- Where: actions/corruption.py:121-123 `dead_end`, :199-207; actions/bloodstained.py; cli/_plan.py:296 (implicits refused); ADR-0037 "The brick, in two cases".
- What it does: `vaal` is `planner=True`. For a target that asks for a corrupted implicit (`implicits:` with `corrupted: true`) `make_plan`
  refuses the target (PlanError "asks for implicits or quality"). For a target with only `allow_corrupted: true`, the brick (1/4 of every
  Vaal) is a dead end although ADR-0037 says it "can be the goal, and its chance is a draw ... six affixes means a full item"; the
  other three outcomes leave the explicit mods as they were. So the only plan that contains a Vaal Orb corrupts an item that already met
  the target and gains nothing. Same for a fossil set with the Bloodstained Fossil (`ImplicitDraw`: "the compressed state keeps no corrupted implicit").
- What it should do: either offer "corrupt for implicit X" (needs #159) or say, in the answer, that corruption is not planned yet.
- Evidence: corruption.py docstring: "The brick is a dead end for a target that allows a corrupted item too until ticket #260 ... which errs
  high on the cost". That sentence is in a docstring only; `grep -rn brick src/crafting_system/cli` finds nothing that tells the owner.
- Impact: any `allow_corrupted` target is priced as if the brick never happens to be a good item; the Vaal Orb can never lower a cost.
- Origin: #259 (Vaal), #261 (Bloodstained), ADR-0036/0037; the gap is #260 and #159.
- Pattern: a kind registered as ready whose only reachable use is empty; the shortfall is stated in a docstring, not in the output.

### ACT2-2: Default beast level 83 and "rare beast = 1 chaos" are defaults that decide game questions and carry no approximate mark   [CONFIRMED] [impact: medium]
- Where: rules/claims/beastcraft.yaml `beastcraft.default_beast_level` (value 83), `beastcraft.any_rare_creature_price` (value 1); actions/beast_mods.py:227-228 (pool built with `item_level=self.beast_level`); beasts.py:44-45.
- What it does: a Farric Wolf/Lynx side swap draws its added mod from the pool at beast level 83, whatever the item level. The claim says
  "Where a bought beast's level comes from is not documented, and poe.ninja prices a beast by name only", source `owner`, `approximate` absent.
- Evidence (`_a2_beast.py`, Sorcerer Boots ilvl 86): the pool has 115 mods at item level 86 and 109 at beast level 83. The six that a default
  Wolf/Lynx can never add: ColdResist8, FireResist8, LightningResist8 (T1 resistances, level 84), LocalIncreasedEnergyShieldPercent7 (T1 ES%, 84),
  EnergyShieldRechargeRate5 (85), **MovementVelocity6 (T1 movement speed, 86)**.
- What it should do: unknown = best estimate + approximate mark (owner rule). The level is a game fact the sources do not give; a plan that
  silently treats T1 resistance/movement speed as unreachable for the beast (or reachable, if the beast is really 86) is wrong without saying so.
  Likewise 3 rare beasts per recipe at 1 chaos each is a made-up price.
- Impact: R22/R30-style boots routes that use a beast to add a prefix/suffix: the beast cannot add the top-tier movement speed or resistances.
- Origin: #147, grill B2 (#93) owner comment "Beast level 83 when a target names none; ... both settings."
- Pattern: a default that decides a game question, not marked approximate.

### ACT2-3: Beast actions name approximate claims they never read   [CONFIRMED] [impact: medium]
- Where: actions/contract.py:738-749 (`Action.claims` default = every Rule constant of the module of the class and of the modules it imports names from); beast_mods.py imports from beasts.py.
- What it does (`_a2_claims.py`): `WildBristleMatron().claims()` and `BeastSideSwap().claims()` have 33 ids, 6 approximate:
  aspect_needs_open_suffix, talisman_fracture_uniform, side_swap_added_mod_is_a_draw, side_swap_removal_uniform, side_swap_refused_without_removable_mod,
  metamod_odds_uniform. The Matron reads only the last; the Wolf only the three side-swap ones. `TalismanFracture` and `AspectBeast` (16 ids) name
  `jewel.fracturing_orb_works_on_jewels` and each other's approximate claims.
- What it should do: ADR-0028 / the docstring itself say "a module that holds several actions reading different claims should override
  this with the exact ids". Beasts, influence (`_claims_of`) and Eldritch did; beast_mods.py and beasts.py did not.
- Impact: a route that uses a Matron lists four approximate inputs it does not depend on (and a Talisman fracture lists the aspect and jewel
  rules). The owner reads "approximate" and cannot tell which of them moved the price.
- Origin: #147 (module-level default), contract.py default.
- Pattern: output that lists internals (module layout) instead of what the step depends on.

### ACT2-4: Awakener donor mods without a tier get tier 1 (placeholder read as meaning)   [CONFIRMED] [impact: medium]
- Where: actions/awakener.py:188 `ExplicitMod(mod.id, tiers_of(data, start).get(mod.id, 1), ...)`; `influence_mods` (:97-119) lists weight-0 mods deliberately; kernel `_drawn_contribution` abstraction/_kernel.py:909 `tiers.get(mod.id, 1)`.
- What it does: `tiers_of` is defined as "mods that cannot spawn on it are absent", but `influence_mods` includes influence mods "whatever their weight". For
  a Shaper ring ilvl 84 (`_a2_awk.py`): 14 of 29 Shaper donor mods have no tier in the table (Elder 20 of 34, Hunter 8 of 22, Crusader 4 of 25,
  Redeemer 2 of 22, Warlord 1 of 23) and get tier 1, e.g. `ReducedCurseEffectUber1_` and all three tiers of `SpellDamageRingUber1/2/3`.
  `_a2_awk2.py`: the result item holds `('ReducedCurseEffectUber1_', 1)` while `tiers_of(result)` says `None`.
- What it should do: a tier that is unknown is unknown (refuse a tier condition on it, or take the tier from the mod's own type chain
  by required level as Dominance does), not 1. R18's whole donor mod, the Assassin's Mark (`CurseOnHitAssassinsMarkUber2`, weight 0 on `ring_shaper`, ADR-0032 "As built"), is in this class.
- Impact: a target `tier:` on such a mod is judged against 1. Bounded: only weight-0 influence mods, and the Awakener is not a planner kind.
- Origin: #213 (61da11b), ADR-0032 "As built".
- Pattern: a type placeholder (tier 1) read as game meaning.

### ACT2-5: Awakener keeps the tier number of the donor's own pool, the result's table says another   [CONFIRMED inconsistency] [impact: low]
- Where: awakener.py:188 (donor tier from `tiers_of(start)` with the donor's influence only), :222 (`replace(entry, values=...)` keeps the receiver's tier); kernel recomputes from the result's influences (`_kernel.py:909`).
- Evidence (`_a2_tier.py`): for the pairs of influences where two influence mods share a `type`, the tier of the same mod differs between the one-influence
  and the two-influence table: Amethyst Ring 26 of 60,960 (mod, pair) cases (CriticalStrikeChanceUber1: Shaper-only T3, Shaper+Crusader T5), Sorcerer
  Boots 8, Vaal Regalia 34.
- What it should do: one number for one fact. The concrete item and the compressed state disagree on the tier of a kept mod after an Awakener.
- Impact: tiny today (0.04% of cases), but the contract suite compares concrete and compressed; this is the kind of case it would miss.
- Origin: #213; the question "is tier counted across influences" is `tiers_of` (pool.py:145-161), another area.
- Pattern: the same fact computed in two contexts.

### ACT2-6: Imprint and Restore stand on two UNVERIFIED 2014 forum answers that are not marked approximate   [CONFIRMED] [impact: medium]
- Where: rules/claims/imprint.yaml `imprint.consumed_on_restore` (patch_verified 1.1.0) and `imprint.several_per_item` (1.1.0); actions/imprint.py Restore/Imprint; also `imprint.allflame_copy_not_restorable`.
- What it does: the statements start with "UNVERIFIED by me (the forum is behind a Cloudflare challenge; quote relayed by the GPT researcher) ... 2014 player answer
  (not rechecked for 3.29), one source". `approximate` is absent. `Restore.claims()` cites `CONSUMED_ON_RESTORE`; the whole value of an imprint (a restore uses it up) and
  the ADR-0060 state `(s, H)` rest on it.
- What it should do: owner rule "stale sources lose; unknowns get an approximate mark". A 2014 relay is both stale and unverified. Nine claims in the repo carry
  "UNVERIFIED" and no approximate flag (`python` scan of rules/claims): awakener.survivor_player_report_2020, imprint.consumed_on_restore, imprint.several_per_item,
  imprint.allflame_copy_not_restorable, recombinator.weighted_report_3_27, recombinator_cost.influence_plus_50_percent_3_25, recombinator_cost.junk_craft_before_after_report_3_26,
  recombinator_cost.dust_rule_average_tier_report, recombinator_cost.idol_cost_cut_3_27.
- Impact: R15/R17 (imprint routes) will print an exact-looking plan on a 2014 rule. Not reachable yet (planner=False).
- Origin: #219, research #90.
- Pattern: weak evidence admitted as an exact rule; the unverified status lives in prose, not in the field the report reads.

### ACT2-7: Other admitted rules with a weak or conflicting source and no mark   [CONFIRMED] [impact: medium]
- `blessed_orb.previous_value_can_repeat` (source owner): the wiki says the same value cannot roll; CoE and the owner say it can. The claim file itself says the owner "settled the wiki's rule against it". No approximate flag. Blessed is planner=False.
- `sockets.chromatic_nonwhite_chance`: the data sample item levels 2-50, 85, 100, qualities 0-20 and 60, six sockets only; "between item level 51 and 84, for qualities 30 to 59 and for fewer than six sockets the formula interpolates, which the owner accepts without a mark". That sentence is the owner rule broken on purpose.
- `eldritch.exalted_adds_one_to_dominant_side` is source `coe` and unmarked (its sibling `annul_removes_one_from_dominant_side` from the same code is marked).
- `corruption.vaal_equipment_four_outcomes` states "no 3.29 count exists" and is deliberately unmarked (ADR-0037); the three recombinator claims `pools_per_side`, `memory_strands_stay_with_base`, `exclusive_counting_report` are `owner`, `patch_verified: 3.26.0` (the pin is 3.29.3.3) and unmarked.
- Origin: #157 (Blessed), ADR-0047 (sockets), #151, ADR-0037, #213-#215.
- Pattern: the approximate mark is applied by a rule of thumb (CoE-only = approximate) that the claim author did not apply uniformly.

### ACT2-8: Recombinator price is a constant inside a tenfold interval, and the Gold default price is 90% of it   [CONFIRMED] [impact: medium]
- Where: actions/recombinator.py:290-304 `_resources`; claims recombinator_cost.dust_per_combine_reports_3_26 (point 100,000, range 25,000-250,000) and gold_per_combine_reports_3_26 (point 12,000, range 8,000-20,000); prices/default_prices.py:12-24 (Dust 150,000 per chaos, Gold 500 chaos per million).
- What it does: every combine costs 100,000 Dust + 12,000 Gold, whatever the two items hold. Default price: 0.667 + 6.000 = 6.667 chaos, of which Gold is 90%. The claims
  themselves say the cost "depends on the item level and the modifiers of the two inputs" (`recombinator_cost.currencies`), that Dust is not a sum over mods (42 Dust for two empty
  wands, 217 for one mod each, 438 for two mods on one input, `dust_not_a_sum_3_25`) and that Gold grows by 323.5 per mod (`gold_linear_in_mod_count_3_25`), but the per-mod
  Gold is used only for the two junk-craft mods. The point values are "a round figure inside" the reports.
- What it should do: the price of a combine is the biggest unknown of a recombinator route; the unit price of Gold is a made-up number (neither is on the market). The interval is carried (`resource_bounds`), but the Gold/Dust unit price has no interval at all.
- Impact: R25-R29 would show a combine cost within a factor of ~3-10 and a unit price from a default; still small against a T1-mod item, but the answer reads as exact.
- Origin: #216, ADR-0035.
- Pattern: a made-up constant standing in for a formula nobody has; a default price that decides ~all of a cost.

### ACT2-9: Recombinator count table is not reproduced by the claim's own event counts   [CONFIRMED arithmetic] [impact: low]
- Where: rules/claims/recombinator.yaml `count_table` vs `count_table_sample_sizes`; recombinator.py:143-150 (renormalises rows 3 and 4, which sum to 101).
- Evidence: counts [0,1,2,3 kept] row 2 = 196/84 (70.0% / 30.0%), table 67/33; row 3 = 124/171/26 (38.6/53.3/8.1), table 39/52/10; row 4 = 47/241/136 (11.1/56.8/32.1), table 11/59/31.
  The gaps are within sampling error (row 3, the 3-mod cell, 1.3 SE), so this is not a wrong number, but nothing reconciles the two claims and the action silently divides rows 3 and 4 by 101.
- Origin: #215. Pattern: one fact written twice (the percent table and the counts) with nothing tying them.

### ACT2-10: Rule-axis intervals are built for four actions; the owner's rule says an interval reads as useless, and the refusal message cites a closed ticket   [CONFIRMED] [impact: medium]
- Where: Awakener `awakener.group_conflict`; Recombinator `recombinator.alpha` (grid 0.4-1.6); Chromatic `chromatic_forced_colour`; Jeweller `jeweller_table`; cli/_interval.py (the "plan's cost interval over the whole grid"); cli/_plan.py:334-338.
- What it does: `make_plan` raises PlanError "the planner does not solve a reading of it with the interval yet (ticket #220)". #220 is CLOSED (2026-11-01); the interval report exists in `cli/_interval.py`
  but `make_plan` still refuses. The design (ADR-0012/0023/0033) answers these four open rules with a cost interval over readings.
- What it should do: brief owner rules: "'Approximate with an interval' reads to him as useless; unknowns get the best estimate and an approximate mark." The plan reading (receiver
  survives, Siveran weights, wiki table, alpha 1) is already a best estimate; the interval is the part he rejects. The refusal message points the owner/agent at the wrong ticket.
- Origin: ADR-0012, ADR-0033, ADR-0047, #220/#221.
- Pattern: a design built for a different owner expectation than the one now stated.

### ACT2-11: Stale reasons in `planner=False` kinds   [CONFIRMED] [impact: low]
- Where: awakener.py:83 `WHY_NOT_PLANNER` and docstring line 32-33; recombinator.py:136-139; cli/_plan.py:337.
- What it does: both say "the solver takes no donors yet (#211, #212) and the interval ... (#220) does not exist". #211, #212 and #220 are all CLOSED (2026-11-01). The real blockers are `allow_inputs=False`, #214/#217 (compressed state) and the end-to-end tickets. `why_not` is what a user is told when they name the kind in `actions:`.
- Pattern: a "not yet" note that outlived the ticket it cites.

### ACT2-12: `sample()` of Embers/Ichors and the Orb of Conflict returns the implicit at its lowest value; the siblings roll   [CONFIRMED] [impact: medium]
- Where: eldritch.py:282-290 and :586-594 return plain `Finite`; finite.py:140 `Finite.sample` picks a result and rolls nothing; blessed.py:91 and corruption.py:96 override `sample` to roll.
- Evidence (`_a2_sample.py`): 2,000 samples of a Grand Exarch Ember on boots give 54 mods with a ranged value, and for every one the value equals the range minimum (FireGolemBuffEffect... (49-51) always 49).
- What it should do: the exact `chance_all`/kernel path uses a law for the roll (eldritch.implicit_value_range), but the simulator (layer 2 of ADR-0019: "action.outcomes().sample(rng)") sees the minimum. For
  R03 ("40% Avoid Shock", grade 3 is 39-41) the simulator can never see a 40 from a grade 3, the kernel says 2/3. The `--verify` of such a route will disagree with the plan for a reason in the sample, not the plan.
  Conflict's `_sibling` and Dominance's upgraded mod have the same shape.
- Origin: #151, #152, #158; `Finite` docstring "a new mod stays at its lowest values (`sample` rolls none)".
- Pattern: a placeholder value (lowest roll) in an exact result that a second consumer reads as a real roll.

### ACT2-13: Placeholder tier 1 for crafted, aspect, metamod and Elevated mods, copied in four places and read as T1   [CONFIRMED] [impact: low-medium]
- Where: bench.py:57 `CRAFTED_TIER = 1`; beasts.py:59 `CRAFTED_TIER = 1` (a second copy) used at :239 for the aspect; beast_mods.py:22 imports bench's for the Matron metamod (:145); targets/floor.py:57 `BENCH_TIER = 1` (a third, "mirrors actions.bench.CRAFTED_TIER", read at floor.py:227); influence.py:114 `ELEVATED_TIER = 1`; kernel `tiers.get(mod.id, 1)` (_kernel.py:909, 924, 1088, 1097, 1104, 1528: it also rebuilds concrete items from states with tier 1 for any mod missing from the table).
- What it does: all are "a mod with no tier in the data" given 1, which `Requirement._counts` / `status_of` compare as `tier <= min_tier`. In my area it is harmless in practice: aspect and metamod are alone in their family; an Elevated mod counts as T1 of its family
  (family selectors include it, resolve.py:77-82), which is the right direction. It is the same seed that made a bench craft T1 of anything, in the same shape; only the families differ.
- What it should do: one definition, one name (a "no tier" value that a tier test refuses), not four constants that agree by accident. Elevated cannot be told from a true T1 by a tier condition.
- Origin: #56 (CRAFTED_TIER), #147, #154/#155.
- Pattern: a type placeholder read as game meaning.

### ACT2-14: Orb of Dominance cannot upgrade 41 of the 247 Elevated mods, and the mapping is a table older than the export   [CONFIRMED count] [impact: low-medium]
- Where: data/elevated.json (made from CoE `poecd.maeven.bmods`), influence.py:330-336; claim dominance.elevated_mapping_is_coe_table (approximate).
- Evidence (`_a2_elev.py`): 247 Elevated mods in the pinned export; the mapping links 206; 41 are linked from no top-tier mod (e.g. LifeRegenerationRatePercentUberMaven, PhysicalDamageCannotBeReflectedPercentInfluenceMaven). For those, `OrbOfDominance.outcomes` raises OutOfScopeError at the moment a top-tier mod of that kind is a candidate.
  `_upgraded` also takes the "next tier" only among mods that can spawn (`tiers`), so a higher tier of weight 0 is skipped and the top spawnable mod is treated as the top tier.
- Impact: Dominance (not a planner kind) is refused for about 1 in 6 Elevated targets, and a wrong link would be silent (the table "is older than the export, so some mods changed").
- Origin: #154, dominance.yaml. Pattern: an external table with a known gap used as the only link.

### ACT2-15: Hard-coded cut: at most one imprint per item by default   [SUSPECTED] [impact: low]
- Where: imprint.py:65 `DEFAULT_MAX_IMPRINTS = 1`; ADR-0060 point 5.
- What it does: "the gain of the second was 0.08% at best in 1,500 random games ... The evidence for one is the random games and the state count, not a real route". It is a cut chosen by state-space size; a route that wants two imprints is solved as if it could not.
- What it should do: owner rule "no hard-coded cut-offs; cuts must say what they still guarantee". The ADR says it, the answer would have to.
- Pattern: a cut chosen for speed on evidence that is not a route.

### ACT2-16: A mirrored (or unmodifiable) item is accepted silently by every refusal list that mentions it   [CONFIRMED] [impact: low]
- Where: hinekora_lock.py:53-66 (flags `mirrored=False, unmodifiable=False` are caller arguments), awakener.py:23, corruption.py:32, imprint.py:24, enchant.py, fracture.py, divine.py.
- What it does: the item model has no mirrored flag, so every action that "refuses a mirrored item" cannot. The leak is closed upstream for bought items: `prices/trade_query.py:310` always sends `mirrored=False`. It stays open for a start item the owner or an agent writes by hand and for a vendor-recipe start (ADR-0059), where nothing says "not mirrored".
- Pattern: an item-model gap that changes behaviour instead of refusing, mitigated in one input path only.

### ACT2-17: `CORRUPTING_KINDS` / `DEFAULT_CORRUPTING_KINDS` already name "locus" though no such kind exists   [CONFIRMED] [impact: low]
- Where: corrupted_pool.py:53-55; targets/corrupted.py:228-257.
- What it does: a target that asks for two corrupted implicits and leaves out `actions:` passes the "can the actions give that many" check because the Locus (2 implicits) is in the default list; no action will ever give it (Locus is #262, open). The error comes later, at plan time, as the generic "asks for implicits".
- Pattern: a constant that names a feature before it exists.

### ACT2-18: Awakener donor model: "holds `donor_mod` alone", "nothing else of the donor matters"   [SUSPECTED] [impact: low-medium]
- Where: awakener.py:165-172 and :188-190; ADR-0032 "What this changes" ("whatever else it holds").
- What it does: the donor `want` is a rare with exactly one mod and the same base and item level as the receiver. The orb draws the pair uniformly among the donor's influenced mods; a donor bought with a second influenced mod keeps the wanted one only half of the time. The ADR text says the want is met "at the first donor with that projection, whatever else it holds", which contradicts the orb's own rule unless the projection includes the donor's number of influenced mods (ADR-0062 / #214).
- What to check: that #214 puts "the donor's influenced-mod count" into the projection before Awakener becomes a planner kind.
- Pattern: a projection that drops a detail the action reads.

### ACT2-19: Same helper written in six places; one function twice   [CONFIRMED] [impact: low]
- "The lowest value of each stat" is written eight times in this area: `_low_values` awakener.py:93 and eldritch.py:210, `_low` beast_mods.py:49 and influence.py:126, `_lowest` blessed.py:72, inline at bloodstained.py:133, beasts.py:238, recombinator.py:513 (and again in harvest_augment.py:98). `_is_talisman` and `TALISMAN_TAG` are in both beasts.py:56,82 and imprint.py:69,72. Identical today; no test pins them together.
- Pattern: one fact written by hand in several places.

### ACT2-20: One white socket assumed for a start item with no stated sockets   [SUSPECTED] [impact: low]
- Where: targets/model.py:275-294 `start_sockets_assumed`; socket_orbs.py:13 docstring.
- What it does: a bought item that states no sockets is given "the one white, unlinked socket" when the target names sockets. A real bought rare body armour or bow nearly always has more sockets and some colours; the finish starts from the worst case and the report says so. Not planned yet (#231), but the default decides the largest cost in the sockets finish (bench count, links) and is not marked.
- Pattern: a default start state that decides cost.

### ACT2-21: Wild Bristle Matron is listed only for rare items   [SUSPECTED] [impact: low]
- Where: beast_mods.py:149-152 (kind yields for `Rarity.RARE` only) vs beastcraft.metamod_one_of_five_if_allowed ("a non-Unique item"), and `outcomes` accepts MAGIC.
- What it does: a magic item with a free slot on the metamod's side is never offered a Matron. A capability gap that is not listed anywhere. Low: metamods are mostly used on rares.

---

## Patterns seen in this area

1. **A type placeholder read as game meaning**: tier 1 for any mod without a tier (donor weight-0 mods ACT2-4, crafted/aspect/metamod/Elevated ACT2-13, `tiers.get(.., 1)` in the kernel); lowest roll standing for a roll in an exact result that `sample` also returns (ACT2-12). Four copies of one constant (ACT2-13).
2. **A default or made-up number that decides a game question without the approximate mark**: beast level 83 and 1-chaos rare beasts (ACT2-2), Dust 100,000 / Gold 12,000 and the Gold unit price (ACT2-8), the one white start socket (ACT2-20), at most one imprint (ACT2-15).
3. **Weak, stale or conflicting evidence admitted as an exact rule**: 2014 forum relays marked UNVERIFIED in prose (ACT2-6), owner overrides of the wiki (Blessed), interpolation "accepted without a mark" (ACT2-7), 3.26 owner claims against a 3.29 pin.
4. **Capabilities built and tested but not reachable**: 13 kinds + the Lock + Locus + Binding (table above). Loud (PlanError), but the planner=True kinds that do exist (Vaal, Bloodstained) are empty in practice (ACT2-1), and the reasons printed to the user are stale (ACT2-11).
5. **Output lists internals instead of what the step depends on**: claim lists by module layout (ACT2-3); "ticket #220" in a refusal (ACT2-10).
6. **One fact written in several places with nothing tying them**: helper copies (ACT2-19), the count table and its counts (ACT2-9), the placeholder tier (ACT2-13).
7. **Designs that conflict with a stated owner rule**: cost intervals over rule axes (ACT2-10), hard-coded cut (ACT2-15).
8. **Item-model gaps closed in one input path only**: mirrored (ACT2-16).
9. **Same fact computed in two contexts**: a kept mod's tier in the donor's pool and in the result's pool (ACT2-5).
