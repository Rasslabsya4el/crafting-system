# Items and modifiers: claims, confidence and open checks

Source note: `docs/poe2/research/items-and-modifiers.md` (PoE2 0.5.5.10, checked 2026-11-24), with the
datamined tables of `research/poe2/data/derived/`. Claims: `docs/poe2/claims/*.yaml` (families listed
below). Confidence is the note's scale: **H** official patch note, the item's own text or the data
export read directly; **M** two secondary sources agree, or one current database page; **L** one
secondary source, a wiki snippet or a player post. Every M and L claim carries `approximate: true`.

Quotes from poe2db and Maxroll were re-read on the live pages on 2026-11-24 (the wiki stays
bot-walled, so wiki-snippet quotes are the note's). Quotes from `mods.json` and `base_items.json`
are the JSON with its line breaks and indentation collapsed to single spaces. Patch labels: poe2db
pages and the export are "0.5.5.10" (current client); Maxroll Corruption Outcomes "0.4.0" (updated
for 0.4); Maxroll Reforging Bench and Crafting Overview "0.5.2"; Craft of Exile "0.5.5.5" (its data
version); undated wiki snippets "0.5.0", which may be too new (see the checks).

## Confidence per claim

| claim id | conf. | open question / in-game check |
|---|---|---|
| rarity.scroll_of_wisdom_identifies | H | |
| rarity.waystone_must_be_identified | H | |
| rarity.megalomaniac_drops_identified | H | |
| rarity.unidentified_tier_mod_level_floor | L | Check 5: thresholds 66/71/76/79 to 11/23/35/48 on 0.5 |
| rarity.exceptional_normal_drop | M | Check 10: item-level threshold (78?) and drop rate |
| item_level.mod_required_level | H | |
| item_level.required_levels_change_by_patch | H | |
| item_level.base_has_drop_level | H | |
| item_level.base_drops_at_or_above_drop_level | M | |
| item_level.tier_one_is_best | H | |
| affix_pool.spawn_weights_are_flags | H | |
| affix_pool.real_weights_not_in_client | H (that no statement was found: M) | |
| affix_pool.coe_weights_from_recombinators | H for what CoE says; weights themselves estimates | Conflict 5: how the 2026-09-03 Krakenbul data was gathered with the recombinator off |
| affix_pool.coe_weights_from_trade_listings | H for what CoE says; biased data | |
| affix_pool.first_match_spawn_tag | M (PoE1 rule) | |
| affix_pool.group_exclusion | M (PoE1 rule) | Check 12: two mods of one group via desecration or essence? |
| affix_pool.side_is_generation_type | M (PoE1 rule) | |
| affix_pool.local_mods_by_id | H | |
| affix_pool.class_census | M (depends on first-match) | |
| item_classes.armour_attribute_tags | H | |
| item_classes.culture_tags | H | |
| item_classes.implicits_by_class | H | |
| item_classes.charms_are_utility_flasks | H | |
| item_classes.released_flag_trap | M | Conflict 9 |
| quality.default_maximum_and_effects | H | Check 9: quality added per scrap or whetstone by rarity (fact 25, no source) |
| quality.jewellery_quality_replaces_other_types | H | |
| quality.jewel_catalysts_added | H | |
| quality.vaal_infuser_over_maximum | H | |
| quality.infuser_item_text | H | |
| quality.essence_of_the_breach_raises_maximum | H | |
| sockets.max_by_class | M | |
| sockets.corruption_socket_ignores_limit | M | |
| sockets.exceptional_extra_socket | H | |
| desecration.bone_item_classes | H | |
| desecration.bone_grades | H | Conflict 1 settled by the data: Preserved and Ancient have no item-level limit |
| desecration.bone_drop_levels | H | |
| desecration.unnamed_columns | L (meaning unknown) | |
| desecration.unrevealed_then_revealed | M | Check 4: number of reveal options (3?) and whether the Ancient level-40 floor holds for each |
| desecration.one_desecrated_mod | H | |
| desecration.mod_census | H | |
| desecration.no_instant_leech | H | |
| crafted_mod_limit.one_crafted_mod | H | |
| crafted_mod_limit.desecrated_separate | H | |
| crafted_mod_limit.one_essence_mod | L to M | Conflict 4, check 3: does an essence mod count as the one crafted mod (essence plus alloy on one item?) |
| reforging_bench.gear_three_to_one | M | Conflict 2, check 6: must the inputs be unidentified? |
| reforging_bench.lowest_item_level | M | |
| reforging_bench.three_affix_rares_give_four | M | Read on the Maxroll page, not in the note; affix count of a reforged rare in general |
| reforging_bench.other_inputs | M | |
| salvage_bench.alternate_quality_returns_catalysts | H | |
| salvage_bench.sockets_give_artificer_shards | M (sockets), L (quality) | Check 9: salvage yield per quality |
| recombinator.disabled | H for 0.5.0; M that it is still off on 0.5.5 | Check 2: still disabled in Standard and Forbidden Rites? |
| recombinator.classes_still_in_data | H (dormant data) | |
| verisium.runeforging_runic_ward | H | |
| verisium.base_conversion_table | H | |
| verisium.alloys_replace_a_mod | H | Check 11: alloy target classes and mod lists (poe2db /us/Alloys is 404) |
| verisium.alloy_names | M | Check 11 |
| verisium.fluxes_change_resistance_element | H | |
| verisium.remnants | H | |
| verisium.anvil_unlock_outside_league | H | |
| corruption.vaal_orb_corrupts | H | |
| corruption.final_for_currency | M to H | |
| corruption.magic_rare_gear_outcomes | M | Conflict 6, check 8: odds per class |
| corruption.unique_outcomes | M | Check 8 |
| corruption.jewel_outcomes | M | Check 8 |
| corruption.waystone_outcomes | M | Check 8 |
| corruption.charm_flask_gem_outcomes | M | Check 8 |
| corruption.outcome_odds_unknown | M (equal split L) | Conflict 6, check 8 |
| corruption.architects_orb_second_enchantment | M | Check 8: Architect's Orb 50/50 |
| corruption.corruption_altar_second_enchantment | M | Check 8: altar 50% destroy |
| corruption.temple_rooms | H | |
| corruption.ancient_infuser_tablets | M | |
| corruption.corrupted_implicit_mods | H | |
| sanctification.multiplies_each_mod | H | Conflict 3 (Mobalytics 80-120% is the older value) |
| sanctification.factor_steps | L | |
| sanctification.blocks_most_crafting | H | Which methods still work is not listed |
| jewels_and_others.jewel_affix_limit | L to M | Check 1: jewel cap 2+2 on 0.5.5 |
| jewels_and_others.tablet_affix_limit | H for 4; split unknown | Check 1: 2+2 or any split of 4? |
| jewels_and_others.tablet_arbiter_unlock | H | |
| jewels_and_others.tablet_takes_chance | H | |
| jewels_and_others.flask_charm_relic_magic_only | M | |
| jewels_and_others.jewel_bases_and_currencies | M | |
| jewels_and_others.liquid_emotions_on_time_lost_jewels | M to H | |
| jewels_and_others.waystone_limits | M | |
| jewels_and_others.waystone_chaos_omens | H | |
| jewels_and_others.charm_slot_cap | M | Conflict 8: cap 3 versus +2 Charm Slots on uniques |
| jewels_and_others.relic_bases | M | |
| uniques.chance_makes_unique_or_destroys | H for the text; odds unknown | |
| uniques.omen_of_chance_no_destroy | H | |
| uniques.omen_of_the_ancients_same_class | H | |
| uniques.ways_to_modify | M to H | |
| item_rules.rarity_affix_limits | H | |
| item_rules.rare_six_mods_item_text | H | |
| item_rules.greater_perfect_min_mod_level | H | |
| item_rules.fracturing_orb | H | |
| item_rules.hinekoras_lock | H | |
| item_rules.artificers_orb | H | |
| item_rules.jewellers_orbs | H | |
| item_rules.omen_of_the_blessed | H | |
| item_rules.desecration_lord_omens | H | |
| item_rules.desecration_side_omens | H | |
| item_rules.omen_of_putrefaction | H | |
| item_rules.essence_kinds | H | Essence-only item mods need the per-essence table, not the export flag |
| item_rules.essence_magic_to_rare | H | |
| item_rules.forbidden_rites_no_new_crafting | H (an absence) | |
| item_rules.coe_reveal_on_corrupted | H for what CoE does | Whether the game allows reveal on corrupted items is not checked |

## Not turned into claims

- **Item level requirement = 80% of the highest modifier level** (fact 13, L): no exact source text in
  the note; check 7.
- **Exceptional items need item level 78** (fact 9, L): no exact text; check 10.
- **Quality added per currency use by rarity** (fact 25): no source at all; check 9.
- **Unique Verisium runeforging below level 55** and the rune counts (13 Ancient, 13 Mythical,
  15 Meta, 15+ Runic Ward, 60+ from uniques) (fact 33): no exact quote in the note.
- **Genesis Tree** bases (6 rings, 4 amulets, 4 belts, fact 38): no exact quote in the note.
- **Omen of Corruption unobtainable since 0.5.0** (fact 29): no exact quote; the omen belongs to the
  omen family.
- **Azula's forum post on weights** (fact 19): a player post; no source kind fits it, kept here only.
- **Bone naming** (conflict 7): naming only, no rule.
