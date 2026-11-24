# PoE2 currency and omens: confidence and open questions of the claims

- **Date:** 2026-11-24. **Research note:** `docs/poe2/research/currency-and-omens.md` (PoE2 0.5.5.10 game data, 0.5.0 patch notes, Craft of Exile beta 0.5.5.5).
- **Claims:** `docs/poe2/claims/` families affix_limits, modifier_level, transmutation, augmentation, regal_orb, alchemy, exalted_orb, chaos_orb, annulment_orb, divine_orb, vaal_orb, orb_of_chance, fracturing_orb, mirror, hinekora_lock, artificers_orb, jewellers_orb, quality_currency, catalyst, shards, temple_currency, omen.
- **Confidence** follows the note: **high** = in-game text (repoe-fork export or poe2db) or official patch notes; **medium** = one community model (Craft of Exile) or guide (Maxroll), nothing against it; **low** = sources disagree, or the fact is inferred. Every medium or low claim carries `approximate: true` with its page wording.

## Sources the claims cite

- Game data: `https://repoe-fork.github.io/poe2/base_items.json` (0.5.5.10); the Greater/Perfect minimum levels from the `TieredCurrency` table of `https://github.com/repoe-fork/dat-export` (0.5.5.10, extract `research/poe2/data/derived/tiered-currency.md`).
- Craft of Exile code: `https://beta.craftofexile.com/packages/files/package_poe2.js?v=1795533925` (data 0.5.5.5); the quotes are exact fragments of the minified file.
- Patch notes: 0.3.0 `https://www.pathofexile.com/forum/view-thread/3826682`, 0.4.0 `https://www.pathofexile.com/forum/view-thread/3883495`, 0.5.0 `https://www.pathofexile.com/forum/view-thread/3932540` (quotes re-read 2026-11-24).
- poe2db: `https://poe2db.tw/us/Sanctified_Items`, `https://poe2db.tw/us/Fate_of_the_Vaal` (Theses). Maxroll: `https://maxroll.gg/poe2/resources/corruption-outcomes`.
- The `.cost` claims quote the metadata id and name of the item in the export, as the PoE1 cost claims do.

## Conflicts (from the note's "Conflicts")

1. **Quality per use.** Craft of Exile's item-level formula against guides' 5/2/1 by rarity; unresolved. Claims: `quality_currency.amount_by_item_level` (low), `catalyst.cap_and_amount` (medium).
2. **Vaal Orb on jewels.** Maxroll and Craft of Exile list different outcomes; no odds. Claim: `vaal_orb.jewel_outcomes` (low).
3. **Vaal infusers.** A 0.4 guide (+1 to 2% up to 30%, or corrupt) against Craft of Exile (item-level amount, cap max +10, 5% corruption per point above the maximum); 0.5.0 added the 20% floor. Claims: `temple_currency.infuser_corruption_chance` (low), `temple_currency.infuser_needs_20_quality` (high).
4. **Vaal Siphoner.** The siphoned modifier is removed or drops one tier; the others rise to 110% of their maximum or "up to 10% above max". Claim: `temple_currency.vaal_siphoner` (high for the text only; the numbers are not in a claim).
5. **Sanctify range.** 0.78 to 1.22 (poe2db, wiki, Craft of Exile) against 0.8 to 1.2 (older guides); the newer figure is the claim. Claims: `omen.sanctification`, `omen.sanctify_multiplies_current`.
6. **Chaotic waystone omens in Craft of Exile.** Craft of Exile still models the pre-0.5 "guarantee the type" and has no Chaotic Effectiveness; game text wins. Claims: `omen.chaotic_rarity`, `omen.chaotic_quantity`, `omen.chaotic_monsters`, `omen.chaotic_effectiveness`, `omen.incompatible_pairs` (whose value leaves the Chaotic group out for this reason).
7. **Trade list against game data.** Omen of Corruption and both Homogenising omens are on the trade list but cannot be obtained in the 0.5 leagues (Standard only). Claims: `omen.corruption`, `omen.corruption_unobtainable`, `omen.homogenising_exaltation`, `omen.homogenising_coronation`, `omen.homogenising_disabled`. They stay in `omen.cost`'s price map; a planner for a 0.5 league should not offer them.
8. **Refined catalyst count.** 0.5.0 notes say 12, the data 13. Claims: `catalyst.refined_jewel_typed_quality` (value 13), `catalyst.jewel_catalysts_added`.
9. **Jiquani's Thesis helmet.** "per 3 Item Armour" (poe2db) against "per 2 Item Energy Shield" (a guide snippet). Claim: `temple_currency.jiquanis_thesis` (poe2db wording).
10. **Artificer's Orb targets.** Game text (Martial Weapon, wand, staff or Armour) wins over one poe2db section. Claim: `artificers_orb.adds_socket`.

## Needs an in-game check (from the note), tied to the claims

1. Quality per use of each scrap, whetstone, etcher, bauble and prism on Normal, Magic and Rare items at a low and a high item level; catalyst quality per use by item level. `quality_currency.amount_by_item_level`, `quality_currency.gemcutters_prism`, `catalyst.cap_and_amount`.
2. Omen of Greater Exaltation on a Rare with exactly 1 open affix: blocked, adds 1, or replaces a modifier? `omen.greater_exaltation`.
3. Greater Exaltation with Sinistral/Dextral Exaltation: are both on that side, and does it need 2 open slots there? `omen.greater_exaltation`, `omen.sinistral_exaltation`, `omen.dextral_exaltation`.
4. Homogenising "same type": a shared tag (Craft of Exile) or the same modifier group? Standard only now. `omen.homogenising_tag_rule`.
5. Catalysing Exaltation multiplier `1 + 0.2*Q`. `omen.catalysing_exaltation_weight`.
6. Whittling: what "level" is, tie-breaking, interaction with Erasure. `omen.whittling`, `omen.whittling_ties_and_erasure`.
7. Chaos with Erasure: may the added modifier land on the other side? `omen.erasure_add_side_free`, `chaos_orb.added_mod_either_side`.
8. The minimum-level exception on one Perfect Exalted roll. `modifier_level.top_tier_exception` (and every `*_min_level` claim that points to it).
9. Orb of Chance success odds per base, and the result of a failed roll under Omen of Chance. `orb_of_chance.odds_by_class`, `omen.chance`.
10. Vaal Orb outcome odds per class, the jewel list, and the 0.5 "multiply current value" range. `vaal_orb.equipment_outcomes`, `vaal_orb.unique_equipment_outcomes`, `vaal_orb.jewel_outcomes`, `vaal_orb.unique_jewel_outcomes`, `vaal_orb.waystone_outcomes`, `vaal_orb.tablet_outcomes`, `vaal_orb.skill_gem_outcomes`, `vaal_orb.flask_charm_quality`, `vaal_orb.multiplies_current_value`.
11. Architect's Orb, Crystallised Corruption, Core Destabiliser, Ancient Infuser: the 50% destroy and the 25% figures. `temple_currency.architects_orb_odds`, `temple_currency.crystallised_corruption_odds`, `temple_currency.core_destabiliser`, `temple_currency.ancient_infuser`, `vaal_orb.tablet_outcomes`.
12. Vaal infusers: amount per use and corruption chance. `temple_currency.infuser_corruption_chance`.
13. Vaal Siphoner: kill threshold, siphon rule, improvement numbers. `temple_currency.vaal_siphoner`.
14. Hinekora's Lock: what the preview shows, whether a locked item can be traded or mirrored, whether the lock survives a declined currency use. `hinekora_lock.foresee_next`, `hinekora_lock.added_0_3_0`.
15. Fracturing Orb: whether revealed Desecrated and crafted modifiers can be fractured, whether unrevealed ones are excluded. `fracturing_orb.uniform_unrevealed_excluded`.
16. Artificer's Orb socket maxima per class, especially foci and sceptres. `artificers_orb.socket_maximum`.
17. Gemcutter's Prism quality per use. `quality_currency.gemcutters_prism`.
18. Omen of Putrefaction: the exact count of unrevealed modifiers ("up to 6") and the side split. `omen.putrefaction`, `omen.putrefaction_sides_and_level`.
19. Forbidden Rites (0.5.5): confirm no crafting changes. No claim: only a summary was read, and "nothing changed" is not a fact a claim can hold. Every claim with `patch_verified` 0.5.0 or 0.3.0 rests on that.

## What the note says that is not a claim

- Scroll of Wisdom (identification, not crafting), Cryptic Key: no claim.
- The legacy shards not on the trade list (Alteration, Alchemy, Annulment, Binding, Horizon, Harbinger's, Engineer's, Ancient, Chaos, Mirror, Exalted, Fracturing) and the removed Orb of Alteration, Orb of Scouring, Orb of Regret and Chromatic Orb: no claim (PoE2 has no Alteration and no Scouring); a planner must not offer them.
- Drop levels, stack sizes (except omens 10 and Fate of the Vaal 5,000) and trade ids: not claims.
- Desecration context in the note's §6c (ancient bones' minimum level 40, Gnawed bones at item level 64 or less, a desecration on a full item removing a random modifier): belongs to the desecration family of the items-and-modifiers note; only `affix_limits.one_desecrated_mod` is here.
- The Vaal Siphoner and Core Destabiliser numbers: unknown, so only the text is claimed.

## Confidence per claim

### affix_limits

| claim | confidence |
|---|---|
| `affix_limits.magic_two_mods` | high |
| `affix_limits.rare_six_mods` | high |
| `affix_limits.corrupted_not_modified` | high |
| `affix_limits.sanctified_not_modified` | high |
| `affix_limits.mirrored_not_modified` | high |
| `affix_limits.fractured_never_removed` | medium |
| `affix_limits.one_desecrated_mod` | high |

### modifier_level

| claim | confidence |
|---|---|
| `modifier_level.greater_perfect_minimums` | high |
| `modifier_level.applies_to_added_mod` | high |
| `modifier_level.top_tier_exception` | medium |
| `modifier_level.item_level_caps` | high |
| `modifier_level.weight_pick_filtered_not_reweighted` | medium |

### transmutation

| claim | confidence |
|---|---|
| `transmutation.normal_to_magic_one_mod` | high |
| `transmutation.accepts_normal_only` | high |
| `transmutation.greater_min_level` | high |
| `transmutation.perfect_min_level` | high |
| `transmutation.cost` | high |
| `transmutation.greater_cost` | high |
| `transmutation.perfect_cost` | high |

### augmentation

| claim | confidence |
|---|---|
| `augmentation.adds_one_mod_to_magic` | high |
| `augmentation.greater_min_level` | high |
| `augmentation.perfect_min_level` | high |
| `augmentation.cost` | high |
| `augmentation.greater_cost` | high |
| `augmentation.perfect_cost` | high |

### regal_orb

| claim | confidence |
|---|---|
| `regal_orb.magic_to_rare_adds_one` | high |
| `regal_orb.greater_min_level` | high |
| `regal_orb.perfect_min_level` | high |
| `regal_orb.cost` | high |
| `regal_orb.greater_cost` | high |
| `regal_orb.perfect_cost` | high |

### alchemy

| claim | confidence |
|---|---|
| `alchemy.makes_rare_with_four_mods` | high |
| `alchemy.current_mods_not_retained` | high |
| `alchemy.sides_random_within_limits` | medium |
| `alchemy.cost` | high |

### exalted_orb

| claim | confidence |
|---|---|
| `exalted_orb.adds_one_mod_to_rare` | high |
| `exalted_orb.accepts_rare_only` | high |
| `exalted_orb.greater_min_level` | high |
| `exalted_orb.perfect_min_level` | high |
| `exalted_orb.cost` | high |
| `exalted_orb.greater_cost` | high |
| `exalted_orb.perfect_cost` | high |

### chaos_orb

| claim | confidence |
|---|---|
| `chaos_orb.removes_one_adds_one` | high |
| `chaos_orb.accepts_rare_only` | high |
| `chaos_orb.removal_uniform` | medium |
| `chaos_orb.added_mod_either_side` | medium |
| `chaos_orb.greater_min_level` | high |
| `chaos_orb.perfect_min_level` | high |
| `chaos_orb.cost` | high |
| `chaos_orb.greater_cost` | high |
| `chaos_orb.perfect_cost` | high |

### annulment_orb

| claim | confidence |
|---|---|
| `annulment_orb.removes_one_mod` | high |
| `annulment_orb.accepts_magic_or_rare` | high |
| `annulment_orb.uniform_over_removable` | medium |
| `annulment_orb.cost` | high |

### divine_orb

| claim | confidence |
|---|---|
| `divine_orb.rerolls_values` | high |
| `divine_orb.cost` | high |

### vaal_orb

| claim | confidence |
|---|---|
| `vaal_orb.corrupts` | high |
| `vaal_orb.equipment_outcomes` | medium |
| `vaal_orb.unique_equipment_outcomes` | low |
| `vaal_orb.jewel_outcomes` | low |
| `vaal_orb.unique_jewel_outcomes` | medium |
| `vaal_orb.waystone_outcomes` | medium |
| `vaal_orb.tablet_outcomes` | medium |
| `vaal_orb.skill_gem_outcomes` | medium |
| `vaal_orb.flask_charm_quality` | low |
| `vaal_orb.multiplies_current_value` | high |
| `vaal_orb.cost` | high |

### orb_of_chance

| claim | confidence |
|---|---|
| `orb_of_chance.unique_or_destroyed` | high |
| `orb_of_chance.accepts_normal` | high |
| `orb_of_chance.tablets` | high |
| `orb_of_chance.odds_by_class` | low |
| `orb_of_chance.cost` | high |

### fracturing_orb

| claim | confidence |
|---|---|
| `fracturing_orb.fractures_one_mod` | high |
| `fracturing_orb.not_on_fractured` | high |
| `fracturing_orb.uniform_unrevealed_excluded` | medium |
| `fracturing_orb.atlas_specialisation` | high |
| `fracturing_orb.cost` | high |

### mirror

| claim | confidence |
|---|---|
| `mirror.creates_mirrored_copy` | high |
| `mirror.cost` | high |

### hinekora_lock

| claim | confidence |
|---|---|
| `hinekora_lock.foresee_next` | high |
| `hinekora_lock.added_0_3_0` | high |
| `hinekora_lock.cost` | high |

### artificers_orb

| claim | confidence |
|---|---|
| `artificers_orb.adds_socket` | high |
| `artificers_orb.socket_maximum` | medium |
| `artificers_orb.cost` | high |

### jewellers_orb

| claim | confidence |
|---|---|
| `jewellers_orb.lesser_three` | high |
| `jewellers_orb.greater_four` | high |
| `jewellers_orb.perfect_five` | high |
| `jewellers_orb.items_with_skills` | high |
| `jewellers_orb.lesser_cost` | high |
| `jewellers_orb.greater_cost` | high |
| `jewellers_orb.perfect_cost` | high |

### quality_currency

| claim | confidence |
|---|---|
| `quality_currency.armourers_scrap` | high |
| `quality_currency.blacksmiths_whetstone` | high |
| `quality_currency.arcanists_etcher` | high |
| `quality_currency.glassblowers_bauble` | high |
| `quality_currency.gemcutters_prism` | high |
| `quality_currency.cap_20` | high |
| `quality_currency.amount_by_item_level` | low |
| `quality_currency.armourers_scrap_cost` | high |
| `quality_currency.blacksmiths_whetstone_cost` | high |
| `quality_currency.arcanists_etcher_cost` | high |
| `quality_currency.glassblowers_bauble_cost` | high |
| `quality_currency.gemcutters_prism_cost` | high |

### catalyst

| claim | confidence |
|---|---|
| `catalyst.ring_amulet_typed_quality` | high |
| `catalyst.refined_jewel_typed_quality` | high |
| `catalyst.genesis_tree_only` | high |
| `catalyst.jewel_catalysts_added` | high |
| `catalyst.cap_and_amount` | medium |
| `catalyst.cost` | high |

### shards

| claim | confidence |
|---|---|
| `shards.transmutation` | high |
| `shards.chance` | high |
| `shards.regal` | high |
| `shards.artificers` | high |

### temple_currency

| claim | confidence |
|---|---|
| `temple_currency.architects_orb` | high |
| `temple_currency.architects_orb_odds` | medium |
| `temple_currency.crystallised_corruption` | high |
| `temple_currency.crystallised_corruption_odds` | medium |
| `temple_currency.core_destabiliser` | high |
| `temple_currency.ancient_infuser` | high |
| `temple_currency.vaal_cultivation_orb` | high |
| `temple_currency.yaomacs_orb_of_sacrifice` | high |
| `temple_currency.kopecs_orb_of_sacrifice` | high |
| `temple_currency.kamasas_orb_of_sacrifice` | high |
| `temple_currency.yuguls_orb_of_sacrifice` | high |
| `temple_currency.sacrifice_needs_upgradable_enchant` | medium |
| `temple_currency.vaal_armourers_infuser` | high |
| `temple_currency.vaal_blacksmiths_infuser` | high |
| `temple_currency.vaal_arcanists_infuser` | high |
| `temple_currency.vaal_catalysing_infuser` | high |
| `temple_currency.infuser_needs_20_quality` | high |
| `temple_currency.infuser_corruption_chance` | low |
| `temple_currency.orb_of_extraction` | high |
| `temple_currency.vaal_siphoner` | high |
| `temple_currency.stack_5000` | high |
| `temple_currency.guatelitzis_thesis` | high |
| `temple_currency.citaqualotls_thesis` | high |
| `temple_currency.jiquanis_thesis` | high |
| `temple_currency.quipolatls_thesis` | high |
| `temple_currency.cost` | high |

### omen

| claim | confidence |
|---|---|
| `omen.activation` | high |
| `omen.stack_10` | high |
| `omen.incompatible_pairs` | medium |
| `omen.greater_exaltation` | high |
| `omen.sinistral_exaltation` | high |
| `omen.dextral_exaltation` | high |
| `omen.homogenising_exaltation` | high |
| `omen.homogenising_tag_rule` | medium |
| `omen.homogenising_disabled` | high |
| `omen.catalysing_exaltation` | high |
| `omen.catalysing_exaltation_weight` | low |
| `omen.homogenising_coronation` | high |
| `omen.sinistral_coronation` | high |
| `omen.dextral_coronation` | high |
| `omen.whittling` | high |
| `omen.whittling_ties_and_erasure` | medium |
| `omen.sinistral_erasure` | high |
| `omen.dextral_erasure` | high |
| `omen.erasure_add_side_free` | medium |
| `omen.greater_annulment` | high |
| `omen.sinistral_annulment` | high |
| `omen.dextral_annulment` | high |
| `omen.light` | high |
| `omen.sinistral_alchemy` | high |
| `omen.dextral_alchemy` | high |
| `omen.retired_0_3_0` | high |
| `omen.blessed` | high |
| `omen.sanctification` | high |
| `omen.sanctify_multiplies_current` | high |
| `omen.corruption` | high |
| `omen.corruption_unobtainable` | high |
| `omen.chance` | high |
| `omen.ancients` | high |
| `omen.sinistral_crystallisation` | high |
| `omen.dextral_crystallisation` | high |
| `omen.abyssal_echoes` | high |
| `omen.sovereign` | high |
| `omen.liege` | high |
| `omen.blackblooded` | high |
| `omen.putrefaction` | high |
| `omen.putrefaction_sides_and_level` | medium |
| `omen.sinistral_necromancy` | high |
| `omen.dextral_necromancy` | high |
| `omen.necromancy_full_side_removes` | medium |
| `omen.abyss_level_65` | high |
| `omen.chaotic_rarity` | high |
| `omen.chaotic_quantity` | high |
| `omen.chaotic_monsters` | high |
| `omen.chaotic_effectiveness` | high |
| `omen.chaotic_up_to_three` | high |
| `omen.recombination_removed` | high |
| `omen.refreshment` | high |
| `omen.resurgence` | high |
| `omen.amelioration` | high |
| `omen.answered_prayers` | high |
| `omen.secret_compartments` | high |
| `omen.hunt` | high |
| `omen.reinforcements` | high |
| `omen.gambling` | high |
| `omen.bartering` | high |
| `omen.expedition_sagas` | high |
| `omen.cost` | high |
