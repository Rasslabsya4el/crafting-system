# Essences, socketables, corruption and Abyss claims: confidence and open checks

- **Source note:** `docs/poe2/research/essences-socketables-corruption-abyss.md` (PoE2 0.5.5.10, checked 2026-11-24).
- **Claims files:** `docs/poe2/claims/essence.yaml`, `docs/poe2/claims/alloy.yaml`, `docs/poe2/claims/rune.yaml`, `docs/poe2/claims/soul_core.yaml`, `docs/poe2/claims/idol.yaml`, `docs/poe2/claims/augment.yaml`, `docs/poe2/claims/distilled_emotion.yaml`, `docs/poe2/claims/abyss_reveal.yaml`, `docs/poe2/claims/breach_catalyst.yaml`, `docs/poe2/claims/reforging_recipes.yaml`, `docs/poe2/claims/corruption_outcomes.yaml`, `docs/poe2/claims/socketable_rules.yaml`.
- **Confidence:** high = current game data or official notes; medium = one current secondary source, community text or data whose meaning is inferred (marked `approximate`); low = a search snippet, an older patch only, or a default with no source (marked `approximate`).
- `socketable_rules.yaml` holds facts of this research that belong to families other agents write (omen, artificers_orb, sockets, temple_currency, desecration, crafted_mod_limit, reforging_bench, salvage_bench, recombinator, fracturing_orb, hinekora_lock, verisium); each statement starts with the family it belongs to in brackets.

## Needs an in-game check

1. Magic to Rare essence: are the magic mods kept and exactly one mod (the essence's) added? What if its side is full? Claims: `essence.magic_to_rare_keeps_existing_mods`.
2. Does an essence apply to an item whose item level is below its modifier's level (Greater Essence of the Body, level 54, on an item level 30 helmet)? Same for Perfect essences (72) and alloys (up to 65). Claims: `essence.item_level_does_not_gate`, `essence.poe2db_required_level_is_four_fifths`, `alloy.mod_level_and_side`.
3. Perfect/special essences and alloys: can the random removal hit a fractured mod? With a Crystallisation omen and no mod of that side, what happens? Do the Crystallisation omens work on alloys? Claims: `essence.removal_skips_fractured`, `essence.removed_mod_is_random`, `socketable_rules.crystallisation_omens`, `alloy.crystallisation_omens_not_assumed`.
4. What does the Mark of the Abyssal Lord (Essence of the Abyss) do to desecration and the reveal? Claims: `essence.abyss_mark_effect_unknown`, `essence.abyss_mark`.
5. Bonded modifiers: is Wisdom of the Maji the only switch (plus Fox Idol for idols)? Claims: `augment.bonded_lines`, `idol.fox_idol_turns_on_bonded`, `augment.bonded_lines_are_not_affixes`.
6. Masterwork Rune: Greater to Perfect? Effect on a Perfect rune or a Greater Tempered Rune (no Perfect tier)? Claims: `augment.masterwork_rune`.
7. Augment socket caps in 0.5 per slot, including wands and staves now open to the Artificer's Orb. Claims: `socketable_rules.socket_caps`, `socketable_rules.artificers_orb_targets`, `corruption_outcomes.extra_socket_classes`.
8. Vaal Orb in 0.5: the outcome list and probabilities on rare gear, uniques, jewels, waystones, gems; the multiplier range of the values outcome. Claims: `corruption_outcomes.equipment_outcomes`, `corruption_outcomes.values_outcome_multiplies`, `corruption_outcomes.equal_chances`, `corruption_outcomes.jewel_outcomes`, `corruption_outcomes.waystone_gem_flask_outcomes`.
9. Architect's Orb and Vaal infusers: chance of success / of corrupting. Claims: `socketable_rules.architects_orb`, `socketable_rules.vaal_infusers`, `socketable_rules.crystallised_corruption`.
10. Raven-Touched Shard: does it make the helmet instillable, as its data stat local_item_can_be_instilled suggests? Claims: `augment.raven_touched_shard_allows_instilling`.
11. Instilling: allowed on a corrupted amulet? Does a new instil replace the old one? Claims: `distilled_emotion.instil_replaces_and_corrupted`.
12. Emotion jewel craft: does it count against the one-crafted-mod limit? What if the jewel already has a crafted mod? Claims: `distilled_emotion.jewel_craft_counts_as_crafted`, `distilled_emotion.jewel_craft`.
13. Well of Souls: one of three offers in 0.5? Do the named (level 65) lord mods need item level 65? Claims: `abyss_reveal.reveal_at_the_well_of_souls`, `abyss_reveal.lord_mods_need_item_level_65`, `abyss_reveal.offers_may_be_base_mods`.
14. Runeforging a magic or rare armour: are its modifiers kept? Can a runeforged item still be crafted? Claims: `socketable_rules.verisium_runeforging`.
15. Reforging Bench: is there any gear-for-gear three-to-one recipe in 0.5? Does the waystone chain end at tier 15 or 16? Claims: `reforging_recipes.no_gear_three_to_one`, `reforging_recipes.waystones_three_to_one`.
16. Fracturing Orb against Perfect essences, desecration's removal of a random mod on a full item, and Chaos Orb. Claims: `socketable_rules.fracturing_orb`, `socketable_rules.desecration_mechanic`, `essence.removal_skips_fractured`.
17. Core Destabiliser: what outcomes on a soul core, with what chance of destruction? Claims: `soul_core.core_destabiliser`.

## Conflicts between sources

1. Essence count 82 (poe2db) against 84 (an earlier trade count): RESOLVED here; the trade site's static list of 2026-11-24 holds exactly the 82 essence names. Claims: `essence.families_and_tiers`.
2. Bonded activation: the PoE2 wiki snippet names the Shaman passive Wisdom of the Maji, another site a Druid node; game text confirms only the Fox Idol for idols. Claims: `augment.bonded_lines`.
3. Lady Hestra's Rune of Winter: patch note 'no longer grants Adds 19 to 28 Cold Damage' against the current text 'against Chilled Enemies': RESOLVED by the data stat (added cold damage versus chilled enemies); the line became conditional. Claims: `rune.lady_hestra_winter_conditional`.
4. Artificer's Orb targets: current text adds wand and staff; an older line and Maxroll 0.4 say martial weapon or armour. Current text taken. Claims: `socketable_rules.artificers_orb_targets`.
5. Vaal Orb values outcome: 0.4 'randomise 1 to 3 affixes' against 0.5 'multiplies each modifier'; 0.5 taken, the 0.4 wording kept as history. Claims: `corruption_outcomes.values_outcome_multiplies`.
6. Vaal probabilities: 'all equally likely' (Maxroll), '25% each' (another site), 'no change 50%' for unique jewels. Claims: `corruption_outcomes.equal_chances`, `corruption_outcomes.jewel_outcomes`.
7. Omen of Corruption is in the 0.5 data but 'can no longer be obtained'. Claims: `socketable_rules.omen_of_corruption`.
8. One desecrated mod per item (0.5) against Omen of Putrefaction ('up to 6 Unrevealed modifiers') and uniques with 1 to 4 custom desecrated mods. Claims: `socketable_rules.omen_of_putrefaction`, `socketable_rules.desecrated_not_crafted`.
9. Emotion waystone values: search snippets disagree; the game text is used. Claims: `distilled_emotion.waystone_effect`.
10. Reforging Bench 'three items to one' for gear: not in poe2db's 0.5 list. Claims: `reforging_recipes.no_gear_three_to_one`.
11. Tiers of one essence family do not share classes (Essence of the Body has a ring row, Greater does not). Claims: `essence.tiers_do_not_share_classes`.

## Found while writing the claims

1. The 'Required Level' poe2db prints beside an essence mod (and the note's Appendix A 'Mod level' column) is about four fifths of the modifier level in the data (43 against 54, 57 against 72); the data's level is the one to use. Claims: `essence.poe2db_required_level_is_four_fifths`, `essence.mod_level_and_side`.
2. The game's Essences table groups Essence of the Abyss and Essence of the Breach with the Perfect essences and alloys (tier 1), not with Hysteria, Delirium, Horror and Insanity (tier 2). Claims: `essence.tier_column`.
3. The alloys are trade-listed under Verisium; the three Tempered runes and Panther, Hawk and Stoat Idol are in the data but not on the trade site. Claims: `alloy.thirteen_alloys`, `rune.tempered_not_on_trade`, `idol.azmeri_augments`.

## Every claim and its confidence

### essence

| Claim | Confidence | Why not high |
|---|---|---|
| `essence.lower_tiers_turn_magic_into_rare` | high |  |
| `essence.perfect_and_special_reroll_one_mod_of_a_rare` | high |  |
| `essence.no_tier_crosses_rarity` | high |  |
| `essence.magic_to_rare_keeps_existing_mods` | medium | No source states what happens to the magic mods; inferred from the item text and common knowledge; the case of a full affix side is unknown. |
| `essence.families_and_tiers` | high |  |
| `essence.tier_column` | medium | The column is unnamed in meaning; read from its values. |
| `essence.guaranteed_mod_by_category` | high |  |
| `essence.guaranteed_mod_from_a_list` | medium | The data lists the outcome mods; the rule choosing among them is not stated for lists without weights. |
| `essence.item_categories` | high |  |
| `essence.mod_level_and_side` | high |  |
| `essence.poe2db_required_level_is_four_fifths` | medium | Read by comparing poe2db's numbers with the data's modifier levels; the four-fifths ratio is inferred. |
| `essence.item_level_does_not_gate` | low | No source says whether item level limits an essence; the default follows the item text, which names no limit. |
| `essence.perfect_tier_changes_class_and_mod` | high |  |
| `essence.tiers_do_not_share_classes` | high |  |
| `essence.removed_mod_is_random` | high |  |
| `essence.removal_skips_fractured` | medium | The general fractured rule is assumed; no source names essences. |
| `essence.hysteria_mods` | high |  |
| `essence.delirium_allocates_a_notable` | high |  |
| `essence.horror_boosts_augments` | high |  |
| `essence.insanity_two_enchantments` | high |  |
| `essence.abyss_mark` | high |  |
| `essence.abyss_mark_effect_unknown` | medium | No source describes the Mark's effect. |
| `essence.breach_raises_max_quality` | high |  |
| `essence.corrupting_essence_monsters` | medium | Maxroll's page is written for 0.4 and the quote is a summary read through a model, not verbatim. |

### alloy

| Claim | Confidence | Why not high |
|---|---|---|
| `alloy.thirteen_alloys` | high |  |
| `alloy.works_like_perfect_essence` | high |  |
| `alloy.guaranteed_mod_by_category` | high |  |
| `alloy.mod_level_and_side` | high |  |
| `alloy.crystallisation_omens_not_assumed` | medium | The omen text names only essences; whether alloys count as essences for it is untested. |

### rune

| Claim | Confidence | Why not high |
|---|---|---|
| `rune.tiered_families` | high |  |
| `rune.generic_rune_slots` | high |  |
| `rune.tiered_effects` | high |  |
| `rune.named_ezomyte_runes` | high |  |
| `rune.runes_of_the_ancients` | high |  |
| `rune.warding_runes` | high |  |
| `rune.aldurs_legacies` | high |  |
| `rune.required_levels` | high |  |
| `rune.limited_to_one` | high |  |
| `rune.lady_hestra_winter_conditional` | high |  |
| `rune.tempered_not_on_trade` | high |  |

### soul_core

| Claim | Confidence | Why not high |
|---|---|---|
| `soul_core.vaal_augments` | high |  |
| `soul_core.effects` | high |  |
| `soul_core.required_levels` | high |  |
| `soul_core.limited_to_one` | high |  |
| `soul_core.atziri_corruption_always_changes` | high |  |
| `soul_core.vaal_theses` | high |  |
| `soul_core.core_destabiliser` | high |  |

### idol

| Claim | Confidence | Why not high |
|---|---|---|
| `idol.azmeri_augments` | high |  |
| `idol.effects` | high |  |
| `idol.required_levels` | high |  |
| `idol.limited_to_one` | high |  |
| `idol.all_fit_sceptres` | high |  |
| `idol.fox_idol_turns_on_bonded` | high |  |
| `idol.formerly_talismans` | medium | The rename rests on one secondary guide; the weapon class is in the data. |

### augment

| Claim | Confidence | Why not high |
|---|---|---|
| `augment.five_kinds` | high |  |
| `augment.replace_not_remove` | high |  |
| `augment.replacing_destroys_old` | medium | One guide written for 0.4 says it; not re-read for 0.5. |
| `augment.socket_bound` | high |  |
| `augment.ancient_augment_limit` | high |  |
| `augment.ancient_augments` | high |  |
| `augment.bonded_lines` | low | Rests on a search snippet of the PoE2 wiki; the wiki page could not be opened; another site names a Druid node. |
| `augment.standard_rune_bonded_armour` | high |  |
| `augment.bonded_lines_are_not_affixes` | medium | Inferred from how augment lines work; no source says it. |
| `augment.serles_triumph_extra_suffix` | high |  |
| `augment.astrids_creativity_extra_crafted` | high |  |
| `augment.cadigans_epiphany_jewel_socket` | high |  |
| `augment.warping_runes_add_mod_families` | high |  |
| `augment.aldur_runes_convert_elements` | high |  |
| `augment.aldurs_legacy` | high |  |
| `augment.masterwork_rune` | medium | The upgrade step and its top end are not stated anywhere read. |
| `augment.raven_touched_shard_allows_instilling` | medium | The meaning is read from the stat name; the game text says only 'Raven-Touched'. |
| `augment.socketing_into_corrupted_items` | medium | One guide for 0.4 says it. |
| `augment.remnant_rewards` | high |  |

### distilled_emotion

| Claim | Confidence | Why not high |
|---|---|---|
| `distilled_emotion.names_and_tiers` | high |  |
| `distilled_emotion.instil_amulets` | high |  |
| `distilled_emotion.three_emotions_per_notable` | high |  |
| `distilled_emotion.strugglescream_three_more` | high |  |
| `distilled_emotion.instil_replaces_and_corrupted` | medium | Neither re-instilling nor corrupted amulets are covered by any source read. |
| `distilled_emotion.jewel_craft` | high |  |
| `distilled_emotion.jewel_craft_mods` | high |  |
| `distilled_emotion.jewel_craft_counts_as_crafted` | medium | That the emotion's mod falls under the crafted limit is an inference from the word 'Crafted' in its text. |
| `distilled_emotion.waystone_effect` | low | The lines are game text; the limit of three per waystone rests on search snippets. |
| `distilled_emotion.liquid_verisium_is_not_an_emotion` | high |  |

### abyss_reveal

| Claim | Confidence | Why not high |
|---|---|---|
| `abyss_reveal.reveal_at_the_well_of_souls` | low | The choice of one out of three rests on game-guide snippets; no game text gives it. |
| `abyss_reveal.bones_feed_the_reveal` | high |  |
| `abyss_reveal.offers_may_be_base_mods` | medium | Community text on poe2db, not game text. |
| `abyss_reveal.lord_mods_level_65` | high |  |
| `abyss_reveal.lord_mods_need_item_level_65` | low | The mod level is printed; whether the reveal respects item level is untested. |
| `abyss_reveal.no_armour_prefixes` | medium | Community notes on poe2db, not game text. |
| `abyss_reveal.jewel_and_waystone_pools` | high |  |
| `abyss_reveal.data_counts` | high |  |
| `abyss_reveal.no_instant_leech` | high |  |
| `abyss_reveal.altered_collarbone_otherworldly` | high |  |
| `abyss_reveal.abyssal_eyes` | high |  |

### breach_catalyst

| Claim | Confidence | Why not high |
|---|---|---|
| `breach_catalyst.jewellery_catalysts` | high |  |
| `breach_catalyst.refined_jewel_catalysts` | high |  |
| `breach_catalyst.only_from_the_genesis_tree` | high |  |
| `breach_catalyst.genesis_tree_wombgifts` | high |  |

### reforging_recipes

| Claim | Confidence | Why not high |
|---|---|---|
| `reforging_recipes.essences_three_to_one` | high |  |
| `reforging_recipes.no_recipe_to_perfect_or_special_essences` | high |  |
| `reforging_recipes.runes_three_to_one` | high |  |
| `reforging_recipes.named_runes_not_combined` | medium | Rests on a guide for 0.4 and on their absence from poe2db's recipe list. |
| `reforging_recipes.emotions_three_to_one` | high |  |
| `reforging_recipes.waystones_three_to_one` | medium | The note gives the range as tiers 1 to 15 without saying whether 15 is the last input or the last output. |
| `reforging_recipes.legacy_runes` | high |  |
| `reforging_recipes.equip_recipes` | high |  |
| `reforging_recipes.recipe_counts` | high |  |
| `reforging_recipes.no_gear_three_to_one` | low | Absence from poe2db's list only. |

### corruption_outcomes

| Claim | Confidence | Why not high |
|---|---|---|
| `corruption_outcomes.enchantment_pool_by_tag` | high |  |
| `corruption_outcomes.values_outcome_multiplies` | high |  |
| `corruption_outcomes.equipment_outcomes` | medium | The list is Maxroll's for 0.4; only the values outcome is confirmed changed for 0.5. |
| `corruption_outcomes.extra_socket_classes` | medium | Maxroll's 0.4 list, not re-checked for 0.5. |
| `corruption_outcomes.jewel_outcomes` | medium | Maxroll's 0.4 list, not re-checked for 0.5. |
| `corruption_outcomes.waystone_gem_flask_outcomes` | medium | Maxroll's 0.4 list, not re-checked for 0.5. |
| `corruption_outcomes.equal_chances` | low | No official probabilities; secondary sources for 0.4 disagree in detail. |

### socketable_rules

| Claim | Confidence | Why not high |
|---|---|---|
| `socketable_rules.crystallisation_omens` | high |  |
| `socketable_rules.abyssal_echoes_reroll` | high |  |
| `socketable_rules.lord_omens` | high |  |
| `socketable_rules.necromancy_omens` | high |  |
| `socketable_rules.omen_of_putrefaction` | high |  |
| `socketable_rules.omen_of_light` | high |  |
| `socketable_rules.abyss_omens_drop_level` | high |  |
| `socketable_rules.omen_of_corruption` | high |  |
| `socketable_rules.omen_of_catalysing_exaltation` | high |  |
| `socketable_rules.orb_of_extraction` | high |  |
| `socketable_rules.artificers_orb_targets` | high |  |
| `socketable_rules.socket_caps` | medium | Maxroll's 0.4 numbers, not re-checked for 0.5. |
| `socketable_rules.exceptional_items` | high |  |
| `socketable_rules.architects_orb` | medium | The 50/50 split is Maxroll's for 0.4; the item text gives no odds. |
| `socketable_rules.crystallised_corruption` | medium | The 50/50 split is Maxroll's for 0.4. |
| `socketable_rules.vaal_cultivation_orb` | high |  |
| `socketable_rules.vaal_infusers` | high |  |
| `socketable_rules.ancient_infuser` | medium | The outcome list is Maxroll's for 0.4. |
| `socketable_rules.vaal_temple_core` | low | A currency-selling site and a search snippet only. |
| `socketable_rules.desecration_mechanic` | high |  |
| `socketable_rules.desecrated_not_crafted` | high |  |
| `socketable_rules.one_crafted_modifier` | high |  |
| `socketable_rules.reforging_bench_at_sekhemas` | high |  |
| `socketable_rules.salvage_returns_catalysts` | high |  |
| `socketable_rules.salvage_gives_artificers_shards` | low | Guides for 0.4 and search snippets. |
| `socketable_rules.recombinator_disabled` | high |  |
| `socketable_rules.fracturing_orb` | high |  |
| `socketable_rules.hinekoras_lock` | high |  |
| `socketable_rules.verisium_runeforging` | high |  |
| `socketable_rules.fluxes` | high |  |

## Not turned into claims

- Drop rates and drop places (more essences in the campaign in 0.5.0, the Well of Souls in Act 2, Abyss omen drop areas beyond the level-65 line, Runeshape Combination levels other than the examples): not crafting rules.
- The full text of the 198 named desecrated modifiers (Appendix F of the note): only their counts and level are claimed (`abyss_reveal.lord_mods_level_65`); the modifiers themselves are in the game data (desecrated domain of mods.json).
- The 63 Legacy recipes one by one: one claim says each Legacy has its recipe (`reforging_recipes.legacy_runes`).
- Thaumaturgic Flux levels, Starlit ores, Kalguuran skills and supports, Exceptional/Mutated/Corrupted/Founders Verisium, Wombgift Hiveblood costs: Expedition and Breach item lists outside these families; only the fluxes, crests and runeforging got a claim in `socketable_rules`.
- The rune Bonded lines one by one (Appendix C game text): the derived data carries only the main lines; the bonded lines are not crafting modifiers (`augment.bonded_lines_are_not_affixes`).
- Unique Vaal Cultivation tables (48 uniques, 198 mods) and the custom desecrated modifiers of uniques: counts only.
