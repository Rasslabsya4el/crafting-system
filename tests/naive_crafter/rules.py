"""The rules of the mechanics the naive crafter plays, each with its source (OR-22, ticket #555).

A rule here is a published statement about the game and what the player does with it. Each carries what the other registries
carry: where it came from (`kind`, `url`), the words of the source (`quote`), and the date it was checked. The quotes and dates were
taken from the pages and the Craft of Exile code on the days given; the project's claim files hold the same quotes
(`tests/naive_crafter/test_naive_sources.py` reads those files as plain YAML and checks that every quote here is one of theirs, so
a quote cannot drift; the two rules marked `in_claims=False` were read first-hand in the local copy of the emulator, and their "quote" is the emulator's own notice text or a description of the place, because Craft of Exile's code is never quoted into this repository); this package reads nothing else of the planner.

`kind` is the source kind of the registry: `wiki` (poewiki.net), `coe` (Craft of Exile's page or its code), `datamined` (the
repoe-fork export), `experiment` (a large-sample measurement by players) or `owner`. OR-21: all of them count, and a source that
the current data shows out of date loses; the data of this run is the pinned export 3.29.3.3.

What a rule fixes is in the code that uses it; `USED_BY` says which action reads which rules, so a rule nothing reads, or a read of a
rule that is not here, fails `test_naive_sources.py`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Cite:
    id: str
    statement: str
    kind: str
    url: str
    quote: str
    date_checked: str
    patch: str = "3.29.3.3"
    approximate: bool = False
    in_claims: bool = True  # False: the quote is not one of the claim files' (a notice text or a description of a place in Craft of Exile's code, never code)


def _cite(*items: Cite) -> dict[str, Cite]:
    found = {item.id: item for item in items}
    assert len(found) == len(items), "a rule id is used twice"
    return found


RULES = _cite(
    Cite(
        "magic_mod_count",
        "A magic item made by an Orb of Transmutation or rerolled by an Orb of Alteration ends with 1 mod or 2 mods, each with chance 1/2.",
        "coe",
        "https://www.craftofexile.com/basics#Crafting_Currency",
        "Will turn a normal item into a magic item (with one or two random explicit mods).",
        "2026-10-31",
    ),
    Cite(
        "rare_mod_count",
        "A Chaos Orb (and an essence on a rare or normal item) leaves a rare item with 4, 5 or 6 mods in the ratio 8:3:1.",
        "wiki",
        "https://www.poewiki.net/wiki/Chaos_Orb#Mechanics",
        "For regular items, Chaos Orbs result in a rare item with an affix count of 4, 5, or 6 at a ratio of 8:3:1.",
        "2026-10-30",
    ),
    Cite(
        "capacity",
        "A normal item holds no explicit mod, a magic item at most 1 prefix and 1 suffix, a rare item at most 3 prefixes and 3 suffixes.",
        "wiki",
        "https://www.poewiki.net/wiki/Modifier#Explicit_modifiers",
        "Magic - random modifiers based on conditions: (0 to 1) prefix and (0 to 1) suffix ... Rare - random modifiers based on conditions: (1 to 3) prefixes and (1 to 3) suffixes",
        "2026-10-30",
    ),
    Cite(
        "normal_has_no_mods",
        "A normal item holds no explicit mods, so its prefix and suffix capacity is 0.",
        "wiki",
        "https://www.poewiki.net/wiki/Rarity",
        'Normal items (also called base items) are the "default" state of items without any explicit modifiers/affixes.',
        "2026-10-30",
    ),
    Cite(
        "family_exclusion",
        "An item never holds two mods of the same group (family), so a random add cannot pick a mod that shares a group with a mod on the item.",
        "wiki",
        "https://www.poewiki.net/wiki/Modifier#Group/family",
        "Only one modifier from any given group may appear on an object; in other words, all modifiers belonging to a group are mutually exclusive with one another.",
        "2026-10-30",
    ),
    Cite(
        "domain_match",
        "A random add picks only mods whose domain is the domain of the item's base.",
        "wiki",
        "https://www.poewiki.net/wiki/Modifier#Mechanics_overview",
        "Mod domain governs the type of entity the modifier is going to appear and may confer some specific rules (such as the number of affixes)",
        "2026-10-30",
    ),
    Cite(
        "side_is_generation_type",
        "Only mods of generation type prefix or suffix enter a random add, and that value is the side the mod takes.",
        "wiki",
        "https://www.poewiki.net/wiki/Modifier#Mechanics_overview",
        "Mod generation type determines how the modifier is generated, for example whether it's a prefix, suffix, corrupted or always applied (like on unique items)",
        "2026-10-30",
    ),
    Cite(
        "level_gate",
        "A mod can be added only if its required level is at most the item level.",
        "wiki",
        "https://www.poewiki.net/wiki/Item_level#What_item_level_affects",
        "Magic and Rare items can only receive affixes which require a level less than or equal to the item's item level.",
        "2026-10-30",
    ),
    Cite(
        "spawn_weight_first_match",
        "The spawn weight of a mod on an item is the weight of the first entry of the mod's own spawn-weight list whose tag the item has; weight 0 removes the mod.",
        "wiki",
        "https://www.poewiki.net/wiki/Modifier#Spawn_weight_tag",
        "If multiple tags apply, the left-most tags are most important, where the right most tags are the least.",
        "2026-10-30",
    ),
    Cite(
        "generation_weight_multiplier",
        "The generation weights of a mod are an ordered list read first-match like the spawn weights; the value found multiplies the spawn weight by value/100. "
        "An owner decision of issue #28 (the official note only says that some weapon classes roll attack mods less often), not a statement of a first-hand source; "
        "Craft of Exile's emulator builds its pool weights from its own tier weighting, not from this field of the export, and no first-hand text for the multiplier has been found.",
        "owner",
        "https://github.com/Rasslabsya4el/crafting-system/issues/28",
        "`generation_weights` as a ×value/100 multiplier",
        "2026-10-31",
        approximate=True,
    ),
    Cite(
        "draw_proportional_to_weight",
        "Among the mods that can still be added, the chance of each is its weight over the sum of the weights of all of them.",
        "wiki",
        "https://www.poewiki.net/wiki/Weight#Overview",
        "if a modifier with a weight of 1000, and a total weight of 40,000, that modifier has a 2.5% chance to roll (1000/40,000)",
        "2026-10-30",
    ),
    Cite(
        "one_pool_for_both_sides",
        "While both sides have an open slot, one add draws from the prefixes and suffixes together, in one sum, with no first choice of a side.",
        "coe",
        "https://www.craftofexile.com/packages/package.js",
        "var tmodpool=tmodp_pre.concat(tmodp_suf)",
        "2026-10-31",
    ),
    Cite(
        "full_side_closes",
        "When an item holds as many prefixes (or suffixes) as its capacity allows, no mod of that side can be added and the other side is the whole pool.",
        "coe",
        "https://www.craftofexile.com/packages/package.js",
        "if(useaffbt.prefix>=usemaxaffgrp.prefix){blkdata.blktype.prefix=!0}",
        "2026-10-31",
    ),
    Cite(
        "values_uniform_integers",
        "Each stat of a drawn mod rolls a uniform integer from its minimum to its maximum, both included; the stats of one mod roll independently.",
        "wiki",
        "https://www.poewiki.net/wiki/Modifier#Mechanics_overview",
        "the actual value of the stat in the cases where minimum and maximum are not the same will be randomized within with equal chances",
        "2026-10-30",
    ),
    Cite(
        "royale_copies_do_not_spawn",
        'A mod of the export whose id holds the word "Royale" is a Battle Royale copy and is not rolled by the game (four of them carry a spawn weight in the export).',
        "experiment",
        "https://docs.google.com/spreadsheets/d/1UKTS29e1XghGTQQJBiu7TR3vrancnZxiyN3tBzj30WI/",
        "426,52,Foulborn Orb of Augmentation,of Grandmastery,1,4,252.5,0.2836879433,1",
        "2026-11-01",
        approximate=True,
    ),
    Cite(
        "transmutation_normal_only",
        "An Orb of Transmutation can be used on a normal item only, and the result is a magic item.",
        "datamined",
        "https://repoe-fork.github.io/base_items.json",
        "Right click this item then left click a normal item to apply it.",
        "2026-10-31",
    ),
    Cite(
        "alteration_magic_only",
        "An Orb of Alteration can be used on a magic item only.",
        "datamined",
        "https://repoe-fork.github.io/base_items.json",
        "Right click this item then left click a magic item to apply it.",
        "2026-10-31",
    ),
    Cite(
        "alteration_rerolls_all_mods",
        "An Orb of Alteration removes every explicit mod of the magic item that is not fractured (a crafted mod too) and draws new ones like a Transmutation Orb.",
        "coe",
        "https://www.craftofexile.com/basics#Crafting_Currency",
        "It will reroll a magic rarity item into a new magic item, removing all old explicits on it",
        "2026-10-31",
    ),
    Cite(
        "augmentation_adds_one",
        "An Orb of Augmentation adds exactly one random mod to a magic item that has an open prefix or suffix, drawn from the pool of the open side.",
        "coe",
        "https://www.craftofexile.com/basics#Crafting_Currency",
        "Will add a new random explicit mod to a magic item that is missing a prefix or suffix.",
        "2026-10-31",
    ),
    Cite(
        "regal_magic_only",
        "A Regal Orb can be used on a magic item only, and the result is a rare item.",
        "wiki",
        "https://www.poewiki.net/wiki/Regal_Orb",
        "Regal Orbs can only be used on magic items.",
        "2026-10-31",
    ),
    Cite(
        "regal_keeps_and_adds_one",
        "A Regal Orb keeps every mod of the magic item and adds one random mod, drawn with the capacity of a rare item.",
        "datamined",
        "https://repoe-fork.github.io/base_items.json",
        "Current modifiers are retained and a new one is added.",
        "2026-10-31",
    ),
    Cite(
        "chaos_rare_only",
        "A Chaos Orb can be used on a rare item only.",
        "datamined",
        "https://repoe-fork.github.io/base_items.json",
        "Right click this item then left click a rare item to apply it.",
        "2026-10-30",
    ),
    Cite(
        "chaos_rerolls_all_mods",
        "A Chaos Orb rerolls every modifier of the rare item and the number of modifiers too, except the modifiers that cannot change (fractured mods); a crafted mod goes with the rest.",
        "wiki",
        "https://www.poewiki.net/wiki/Chaos_Orb#Mechanics",
        "they reroll all modifiers (and the number of modifiers) on a rare item",
        "2026-10-30",
    ),
    Cite(
        "fractured_mods_kept",
        "A fractured mod stays on the item, in its slot, through an Alteration, a Chaos Orb or an essence; its group then blocks the new draws as any group on the item does.",
        "wiki",
        "https://www.poewiki.net/wiki/Fractured_item#Mechanics",
        "These mods cannot be removed (by Orb of Annulment or Orb of Scouring, etc.) or have its values changed by Divine Orb.",
        "2026-10-30",
    ),
    Cite(
        "kept_mods_count_in_total",
        "The drawn total of a reroll includes the fractured mods that stay (and the forced mod of an essence); only the rest is drawn, and nothing is drawn when the kept mods already reach the total.",
        "coe",
        "https://www.craftofexile.com/packages/package.js",
        'poec_simRollAffix(null,null,null,fossil,noaffix-prmods,!0,!1,enforcetag,igcrca,rfmlk,rfmlkt,rfmlkv,!1,"|",graveyard,overrideMaxAff)',
        "2026-10-31",
    ),
    Cite(
        "dry_pool_leaves_fewer_mods",
        "When no mod can be added any more before the total is reached, the reroll stops and the item keeps the mods it has.",
        "coe",
        "https://www.craftofexile.com/packages/package.js",
        "(a place, not a quote: the emulator's function that rolls one affix ends without adding a mod when the summed weight of the eligible pool is zero; "
        "the local copy is in the git-ignored .claude/scratch/coe/site/packages/package.js, function poec_simRollAffix)",
        "2026-11-07",
        patch="3.29.0.3",
        in_claims=False,
    ),
    Cite(
        "add_refused_when_no_legal_mod",
        "An add that has no legal mod (no open slot, or every candidate of an open side blocked) is refused and consumes nothing.",
        "coe",
        "https://www.craftofexile.com/packages/package.js",
        "Could not generate mod (the notice the emulator shows when a craft produces no mod; the item is left as it was; "
        "the local copy is in the git-ignored .claude/scratch/coe/site/packages/package.js, function poec_simApplyCraftGO)",
        "2026-11-07",
        patch="3.29.0.3",
        in_claims=False,
    ),
    Cite(
        "essence_forced_mod_by_item_class",
        "The forced mod of an essence on an item is the one mod that the essence record gives for the item class; a class with no entry takes no essence.",
        "datamined",
        "https://repoe-fork.github.io/essences.json",
        'CurrencyEssenceHatred1: "mods": {"Amulet": "ColdDamagePercentEssence1", "Belt": "ColdResist1", "Body Armour": "ColdResist1"',
        "2026-10-30",
    ),
    Cite(
        "essence_normal_becomes_rare",
        "An essence used on a normal item makes a rare item with the forced mod and random mods drawn as an Orb of Alchemy does (4, 5 or 6 in all).",
        "wiki",
        "https://www.poewiki.net/wiki/Essence#Crafting",
        "All essences can be used to upgrade a piece of normal rarity equipment to rare, similar to an Orb of Alchemy, and apply one guaranteed affix.",
        "2026-10-31",
    ),
    Cite(
        "essence_reforges_rare",
        "An essence of record level 5 (Screaming) or more also reforges a rare item like a Chaos Orb and guarantees the forced mod.",
        "wiki",
        "https://www.poewiki.net/wiki/Essence#Crafting",
        "Essences of tier 5 (Screaming) and above can also be used to reforge the affixes of rare equipment, like a Chaos Orb, with a guaranteed affix.",
        "2026-10-31",
    ),
    Cite(
        "essence_low_levels_cap_random_mods",
        "An essence of level 1 to 4 limits the random mods to a required level of at most its cap (the record's item_level_restriction) or the item level when that is lower; the forced mod is not subject to it.",
        "wiki",
        "https://www.poewiki.net/wiki/Essence#Crafting",
        "Low tier essences restrict the pool of random modifiers that can roll when using the essence up to a certain maximum level, if the maximum modifier level is lower than the item's actual item level.",
        "2026-10-31",
    ),
    Cite(
        "essence_forced_mod_ignores_item_level",
        "The forced mod of an essence applies even when its required level is above the item level.",
        "coe",
        "https://www.craftofexile.com/packages/package.js",
        "if(htilvl<=crsim_settings.ilvl||mod.id_mgroup==11||mod.id_mgroup==13||mod.id_mgroup==10)",
        "2026-10-31",
    ),
    Cite(
        "essence_refused_on_family_clash",
        "An essence is refused, and nothing is consumed, when its forced mod shares a group with a fractured mod on the item.",
        "coe",
        "https://www.craftofexile.com/packages/package.js",
        'if(efail){var errtxt=applyLang("The item already has a mod of this type")',
        "2026-10-31",
    ),
    Cite(
        "bench_option_adds_one_fixed_mod",
        "A bench option with add_explicit_mod adds that one named crafted mod, never one drawn at random; its side is its generation type.",
        "datamined",
        "https://repoe-fork.github.io/crafting_bench_options.json",
        'bench[760].actions.add_explicit_mod="StrMasterItemGenerationCannotChangePrefixes"; 732 records with add_explicit_mod, 732 distinct ids, generation_weights [] for all 732',
        "2026-10-30",
    ),
    Cite(
        "bench_option_item_classes",
        "A bench option is offered for the item classes in its item_classes list and for no other.",
        "datamined",
        "https://repoe-fork.github.io/crafting_bench_options.json",
        "item_classes lists the equipment classes an option is offered for; the five metamods and remove_crafted_mods use the same 24 classes (bench[20], bench[760]..bench[764])",
        "2026-10-30",
    ),
    Cite(
        "bench_option_cost",
        "The price of a bench option is its cost map, currency base item ids with whole counts; a craft is paid once per use.",
        "datamined",
        "https://repoe-fork.github.io/crafting_bench_options.json",
        'bench[20].actions.remove_crafted_mods=true, cost={"Metadata/Items/Currency/CurrencyConvertToNormal":1}, bench_tier=0',
        "2026-10-30",
    ),
    Cite(
        "bench_follows_affix_rules",
        "A bench craft follows the ordinary affix rules: the item cannot already hold a mod of the crafted mod's group, and a slot must be open on the crafted mod's side.",
        "wiki",
        "https://www.poewiki.net/wiki/Crafting_Bench#Using_the_crafting_bench",
        "Crafting a mod follows the normal affix rules. Specifically: * The item cannot already have a mod of that type. * The item must have a prefix or suffix slot open as appropriate.",
        "2026-10-30",
    ),
    Cite(
        "bench_one_crafted_mod",
        "An item holds one crafted mod by default; a craft on an item that already holds one is refused.",
        "wiki",
        "https://www.poewiki.net/wiki/Crafting_Bench#Using_the_crafting_bench",
        "Typically, only one crafted modifier may be added to an item",
        "2026-10-30",
    ),
    Cite(
        "currency_cost",
        "One use of an orb consumes one item of that orb, priced under the name the game data gives it.",
        "datamined",
        "https://repoe-fork.github.io/base_items.json",
        'Metadata/Items/Currency/CurrencyUpgradeToMagic: name "Orb of Transmutation"; CurrencyRerollMagic: "Orb of Alteration"; CurrencyAddModToMagic: "Orb of Augmentation"; CurrencyUpgradeMagicToRare: "Regal Orb"',
        "2026-10-31",
    ),
    Cite(
        "chaos_cost",
        "One use of a Chaos Orb consumes one Chaos Orb item.",
        "datamined",
        "https://repoe-fork.github.io/base_items.json",
        'Metadata/Items/Currency/CurrencyRerollRare: name "Chaos Orb"',
        "2026-10-31",
    ),
    Cite(
        "essence_cost",
        "One use of an essence consumes one item of that essence, priced under the name of its record.",
        "datamined",
        "https://repoe-fork.github.io/base_items.json",
        'Metadata/Items/Currency/CurrencyEssenceSpite3: name "Shrieking Essence of Spite"',
        "2026-10-31",
    ),
)

# the rules each kind of action (and the draw they share) reads, by Cite id
DRAW = (
    "domain_match",
    "side_is_generation_type",
    "level_gate",
    "spawn_weight_first_match",
    "generation_weight_multiplier",
    "draw_proportional_to_weight",
    "one_pool_for_both_sides",
    "full_side_closes",
    "family_exclusion",
    "values_uniform_integers",
    "royale_copies_do_not_spawn",
    "capacity",
    "normal_has_no_mods",
    "dry_pool_leaves_fewer_mods",
)
USED_BY = {
    "draw": DRAW,
    "transmutation": ("transmutation_normal_only", "magic_mod_count", "currency_cost"),
    "alteration": ("alteration_magic_only", "alteration_rerolls_all_mods", "magic_mod_count", "fractured_mods_kept", "kept_mods_count_in_total", "currency_cost"),
    "augmentation": ("augmentation_adds_one", "add_refused_when_no_legal_mod", "currency_cost"),
    "regal": ("regal_magic_only", "regal_keeps_and_adds_one", "add_refused_when_no_legal_mod", "currency_cost"),
    "chaos": ("chaos_rare_only", "chaos_rerolls_all_mods", "rare_mod_count", "fractured_mods_kept", "kept_mods_count_in_total", "chaos_cost"),
    "essence": (
        "essence_forced_mod_by_item_class",
        "essence_normal_becomes_rare",
        "essence_reforges_rare",
        "essence_low_levels_cap_random_mods",
        "essence_forced_mod_ignores_item_level",
        "essence_refused_on_family_clash",
        "rare_mod_count",
        "fractured_mods_kept",
        "kept_mods_count_in_total",
        "essence_cost",
    ),
    "bench": ("bench_option_adds_one_fixed_mod", "bench_option_item_classes", "bench_option_cost", "bench_follows_affix_rules", "bench_one_crafted_mod"),
}

# how many of 1, 2, ... mods: the weights of the laws above
MAGIC_COUNTS = {1: 1, 2: 1}
RARE_COUNTS = {4: 8, 5: 3, 6: 1}
CAPACITY = {"normal": 0, "magic": 1, "rare": 3}  # per side
