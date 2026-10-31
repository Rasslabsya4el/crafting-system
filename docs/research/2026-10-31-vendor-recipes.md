# Vendor recipes as start-item sources in 3.29 (research for ticket #102)

Ticket: https://github.com/Rasslabsya4el/crafting-system/issues/102 (map #1, inventory row M-41, round 2 of [#81](https://github.com/Rasslabsya4el/crafting-system/issues/81)). Date checked: 2026-10-31. Patch: 3.29.3.3 (pinned dump `.claude/scratch/real-cache/repoe-fork/3.29.3.3/`, https://repoe-fork.github.io/mods.json, `base_items.json`). Scope of the owner (#81): equipment, jewellery and jewels; flasks, gems and maps are not targets; no unique is a target; quality from catalysts is a target. Currency-exchange and gem recipes are skipped, as the ticket says.

**Answer in one paragraph.** Seven vendor recipes still change or create a chosen mod on equipment in 3.29, and all are deterministic. Four are "tier-up" chains: a Normal item (or a Magic/Rare one that already holds the mod) + a coloured flask + an Orb of Augmentation gives a **new Magic item that holds only that one mod, one tier higher**, up to a cap. They cover movement speed on boots (5 recipes from Normal to 30%, T2), flat added Physical Damage on weapons (8 recipes to T2), flat added Fire, Cold or Lightning on weapons (8 recipes to T3 by the wiki; Craft of Exile says T2, see O-1) and chaos resistance on rings and amulets (5 recipes to T2, 26-30%). Three more are one-shot: a Normal wand, sceptre, dagger or staff + two gems of one tag with 40% quality in total gives a Magic weapon with **+1 (staff +2) to Level of all Spell Skill Gems of that tag**, and a Normal helmet + two Minion gems with 40% gives **+1 to Level of all Minion Skill Gems**. The Whetstone recipes (increased Physical or Spell Damage) give only low tiers. The "full rare set", "X of a kind" and quality recipes give **currency**, not items, the 5-to-1 recipes give a **random** item of the same base, and **there is no recipe for jewels** that picks a mod. Craft of Exile's vendor table is stale (it still holds recipes removed in 3.19 and 3.21), so the wiki page is the source. Each recipe is an ordinary deterministic multi-input action (ADR-0011): its cost is the price of its ingredients, so it needs no chance node and no new action format.

Reddit could not be read: two `gpt-research` runs failed with a timeout (job ids `20261031-140226-5de4` and `20261031-140636-2179`), the same failure the other round-2 research sessions report. Nothing below rests on a post I did not see; the gap is open point O-3.

## What the recipes do (admitted claims)

Evidence kinds: **wiki** (poewiki.net, read in the built-in browser pane 2026-10-31; the page `Vendor_recipe_system` is the only list and its version history cites the patch notes), **official** (patch notes of pathofexile.com, read through the wiki's Version pages which quote them), **datamined** (repoe-fork 3.29.3.3), **coe** (Craft of Exile's `package.js`, local copy `sources/raw/coe/package.js`, fetched 2026-09-20). The claim ids are those of the draft file.

### Shared rules

**VEN-01** (`vendor.recipe_makes_a_new_magic_item_with_one_mod`) The recipes that "create a new item" return a new Magic item with only the recipe's mod, whatever the rarity or the other mods of the input; quality, sockets, links, item level and influences are kept; enchantments, Eldritch and Synthesised implicits, Incubators and Crucible trees are removed. Kind: wiki. URL: https://www.poewiki.net/wiki/Vendor_recipe_system. Quote: "All recipes of this type create a new base item (with randomized base defences)." and "The following are retained: quality, sockets, links, item level, influences". The Quicksilver Flask page says it outright: "This recipe outputs Magic Boots with 5% higher movement speed (and no other modifiers)" (https://www.poewiki.net/wiki/Quicksilver_Flask). Whether the **base type** stays is not stated (O-2).

**VEN-02** (`vendor.refused_on_fractured_and_corrupted_inputs`) Fractured and corrupted items cannot be used as the base item of these recipes. Kind: wiki, same page, quote "Fractured items and corrupted items cannot be used as base items for these recipes." (3.25.0 fixed "a bug where some vendor recipes could un-Fracture Fractured Items", same page's version history.)

**VEN-03** (`vendor.item_level_kept_by_modifying_recipes`) A recipe that modifies mods keeps the input's item level; only the 5-to-1 recipe takes the lowest ilvl of its inputs. Kind: wiki. URL: https://www.poewiki.net/wiki/Item_level. Quote: "Recipes that modify an item's modifiers typically keep the original item's ilvl." "Typically": the flask's item level is not said to matter (O-4).

### The tier-up chains (deterministic)

| Recipe | Input | Other ingredients | Output | Cap (wiki) | Recipes from Normal |
|---|---|---|---|---|---|
| Movement speed (`vendor.movement_speed_boots_tier_up`, VEN-04) | Boots: Normal for the lowest tier, Normal/Magic/Rare with the explicit mod for the next | Quicksilver Flask, Orb of Augmentation | Magic boots, only the movement speed mod, one tier higher | T2, 30% (Cheetah's) | 5 (10, 15, 20, 25, 30) |
| Flat Physical (VEN-05) | Weapon, same rule | Granite Flask, Orb of Augmentation | Magic weapon, only added Physical Damage, one tier higher | T2 | 8 (T9 to T2) |
| Flat Fire / Cold / Lightning (VEN-05) | Weapon, same rule | Ruby / Sapphire / Topaz Flask, Orb of Augmentation | Magic weapon, only that added damage, one tier higher | T3 | 8 (T10 to T3) |
| Chaos resistance (`vendor.jewellery_chaos_resistance_tier_up`, VEN-06) | Ring or Amulet, same rule | Amethyst Flask, Orb of Augmentation | Magic jewellery, only chaos resistance, one tier higher | T2, 26-30% | 5 (T6 to T2) |

Provenance: kind wiki, https://www.poewiki.net/wiki/Vendor_recipe_system, quote "Magic Boots with % increased Movement Speed one tier higher Maximum tier is Tier 2 (30% increased Movement Speed)", "Magic Weapon with x added Fire Damage one tier higher Maximum tier is Tier 3", "Magic Amulet or Ring with x% to Chaos Resistance one tier higher Maximum tier is Tier 2 ((26–30)% to Chaos Resistance)"; the movement speed cap is repeated on the Quicksilver Flask page. "Hybrid weapon local damage mod does not work." The first recipe from a Normal item gives the lowest tier ("or Normal rarity for adding lowest tier mod"); the chain is run by feeding each Magic result back in.

**VEN-07** (`vendor.tier_caps_match_the_datamined_ladders`) The caps land on real mods in the 3.29.3.3 data. Kind: datamined. URL: https://repoe-fork.github.io/mods.json. Counted from the top of each ladder on one base (boots, Driftwood Sceptre, Coral Ring, Onyx Amulet, first spawn-weight tag that matches):

| Ladder | Tiers | Lowest (required level) | Cap reached by the vendor | Not reachable |
|---|---|---|---|---|
| Movement speed (`MovementVelocity1..6`) | 6 | Runner's 10% (1) | T2 `MovementVelocity5` Cheetah's 30% (55) | T1 `MovementVelocity6` Hellion's 35% (86) |
| Flat Physical, weapon (`LocalAddedPhysicalDamage1..9`) | 9 | Glinting (2) | T2 `LocalAddedPhysicalDamage8` Tempered (65) | T1 Flaring (77) |
| Flat Fire (`LocalAddedFireDamage1..10`) | 10 | Heated (1) | T3 `LocalAddedFireDamage8` Blasting (62) | T2 Cremating (74), T1 Carbonising (82) |
| Flat Cold / Lightning | 10 | Frosted (2) / Humming (3) | T3 Polar (63) / Discharging (63) | T2 (75/74), T1 (82) |
| Chaos resistance (`ChaosResist1..6`) | 6 | of the Lost 5-10% (16) | T2 `ChaosResist5` of Exile 26-30% (65) | T1 of Bameth 31-35% (81) |

The caps fit the data (the wiki's "Tier 2" for physical and movement speed, "Tier 3" for the elemental ladders that have two more tiers on top). The mods are all prefixes except chaos resistance (suffix). Two-hand weapons have their own flat-damage ladders (the Iron Staff fire ladder also starts at level 82 at the top); the tier numbers above are for one-hand weapons and the vendor's "tier" on a two-hand weapon is read on its own ladder, which was not checked tier by tier.

### The one-shot recipes

**VEN-08** (`vendor.spell_gem_level_weapon_recipe`) Normal Rune Dagger, Sceptre, Staff or Wand + 2 or more quality gems with a combined 40% quality that all carry the tag (Physical, Fire, Cold, Lightning, Chaos) give a Magic weapon with +1 to Level of all Spell Skill Gems of that tag (staff +2); a generic dagger and a warstaff cannot be used. Kind: wiki. Quote for the 3.29 change: "The lowest tier for + physical/fire/cold/lightning/chaos skills on staff is now +2 instead of +(1-2), so the vendor recipe for a + skill level staff now always gives a +2 staff." Mods: `GlobalFireSpellGemsLevel1_` Flame Shaper's, `GlobalColdSpellGemsLevel1_` Frost Singer's, `GlobalLightningSpellGemsLevel1`, `GlobalPhysicalSpellGemsLevel1`, `GlobalChaosSpellGemsLevel1` (all prefixes, required level 2, a single tier each; weights wand/sceptre/dagger 250 (physical 200), staff two-hand versions 1000 (physical 750), chaos has no sceptre version). The wiki is not clear whether the tag must be on the gem or whether support gems count; the gems used are "skill gems with the tag" in practice (O-9).

**VEN-09** (`vendor.helmet_minion_gem_recipe`) Normal Helmet + 2 or more quality gems with a combined 40% and the Minion tag give a Magic helmet with +1 to Level of all Minion Skill Gems (`GlobalIncreaseMinionSpellSkillGemLevel1` Taskmaster's, prefix, required level 14, helmet weight 250). Kind: official (via the wiki Version page). URL: https://www.poewiki.net/wiki/Version_3.19.0. Quote: "The Vendor Recipe for a Helmet with a +1 to Level of socketed Minion Gems modifier has been replaced with a new recipe."

**VEN-10** (`vendor.whetstone_weapon_recipes_low_tier`) Weapon (any rarity) + Rustic Sash + Blacksmith's Whetstone gives a Magic weapon with increased Physical Damage by the sash's rarity: Magic sash Heavy 40-49%, Rare sash Serrated 50-64%, Unique sash Wicked 65-84%; Rune Dagger, Sceptre, Wand or generic Staff + Chain Belt + Whetstone give Apprentice's, Adept's or Scholar's increased Spell Damage the same way. In the data these are T16, T14 and T12 of the 16-tier local physical ladder (required levels 1, 11, 23; the wiki table says 1, 8, 18, which the data does not support) and T14, T12, T10 of the spell damage ladder. Low value (O-8).

### Recipes that do not give a chosen mod

**VEN-11** (`vendor.five_to_one_is_a_random_unidentified_item`) Five Magic or five Rare items of the same base give one unidentified Magic or Rare item of that base, lowest ilvl, random mods, no influence; Cluster Jewels get a random number of passives and small passive type. This is the only recipe that touches jewels. It is a random item (a "buy a rare of this base" substitute), which a start item cannot be: the solver needs a known item.

**VEN-12** (`vendor.onyx_amulet_recipes_keep_influence`) Amulet (corrupted allowed) + red, green and blue gem gives a Normal Onyx Amulet that keeps the influence of the input and is not corrupted; Astrolabe Amulet + the three gems gives a double-influenced Onyx Amulet (random influences). Kind: wiki. Quote: "any influence present on the input amulet will persist to the resulting Onyx Amulet". Useful only as a cheap way to un-corrupt an influenced amulet or to get an influenced Onyx base; the double-influence outcome is random and its odds are not published.

**Currency, not items** (out of the start-item scope, listed so nobody asks): the "full set of rare items" recipes return Orbs of Chance (lowest ilvl 1-59), Chaos (60-74) or Regal Orbs (75-100), 1 to 3 by identified/quality state; the full influenced set returns 1 Exalted Orb (2 Exalted Shards before 3.28.0, "1 Exalted Orb" since); X of a kind and the straight flush recipes return Orbs of Chance, Alchemy, Augmentation, Regal; the quality recipes (a Normal item of 20% quality or items with a total 40%) return Armourer's Scrap, Whetstone, Glassblower's Bauble, Gemcutter's Prism or a **Catalyst from jewellery** (and the Ultimatum recipe returns a Catalyst of the quality type of the jewellery used). The Catalyst recipe is a way to get catalysts, not an item; a later pricing ticket can read it. Socket recipes (6-link, RGB, 6 sockets) return Fusing, Chromatic or Jeweller's Orbs; 3.28.0 swapped the priorities of the Chromatic and Jeweller's recipe, and Chromatic Orbs are no longer sold by vendors since 3.29.0 (notes quoted in the wiki's Version 3.29.0 page).

### Recipes that no longer exist (stale in Craft of Exile)

**VEN-13** (`vendor.flat_elemental_damage_to_spells_recipe_removed`) Official 3.21.0: "The Vendor Recipe granting flat Elemental Damage to Spells no longer exists." (https://www.poewiki.net/wiki/Version_3.21.0, section "Wand and Vendor Recipe changes"). Craft of Exile still lists it (`mwcs`, `mwfs`, `mwls`: Magic Sceptre, Wand or Rune Dagger + elemental Ring + Alteration), and the helmet "+1 Minion Gems" recipe (`mhmg`, socketed gems) that 3.19.0 replaced.

**VEN-14** (`vendor.coe_vendor_table_is_stale`) Craft of Exile's `crsim_vendor` holds 27 entries; 3 + 1 of them are the removed recipes above, every `+` (tier-up) entry has `"maxtier":2` (the wiki says 3 for Fire, Cold and Lightning), and the key `mwls` is declared twice (flat Lightning to spells and "% phys. dmg."), so the second hides the first. The table has no Onyx amulet and no 5-to-1 recipe. Kind: coe. URL: https://www.craftofexile.com/packages/package.js. Quote: `"mwcs":{"name":"Flat cold dmg to spells","desc":"Magic Weapon with Adds # to # Cold Damage to Spells"`. Where the two sources disagree the wiki wins here, because its version history dates the change and the CoE entries predate 3.19.

## Is it useful as a start-item source

A recipe is useful when it gives a mod that is rare or costly by other means for a small, certain price.

| Rank | Recipe | Why |
|---|---|---|
| 1 | +1 / +2 spell gems on a weapon (VEN-08) | The mod is a one-tier prefix with spawn weight 200-250 (staff 750-1000), a small share of the weapon's prefix pool; the recipe makes it certain for two cheap quality gems and a Normal base. |
| 2 | Movement speed 30% on boots (VEN-04) | Certain T2 prefix for 5 Augmentations and 5 Quicksilver Flasks; every boots craft wants it. |
| 3 | Flat Physical T2 / flat elemental T3 on weapons (VEN-05) | Certain mid-high tier damage prefix for 8 Augmentations and 8 flasks; the elemental cap (T3) is below the T1/T2 the best crafts use. |
| 4 | Chaos resistance T2 on rings/amulets (VEN-06) | Certain suffix for 5 Augmentations and 5 Amethyst Flasks; a modest mod. |
| 5 | +1 Minion Gems helmet (VEN-09) | Same shape as 1 for minion builds. |
| low | Whetstone recipes (VEN-10), Onyx amulets (VEN-12) | Low tiers of mods that an Alteration spam reaches cheaply; influence is the only point of the Onyx recipe. |
| none | 5-to-1, full sets, quality recipes, socket recipes | Random item or currency. |

Two caveats the solver must respect. First, the output is a **Magic item with one mod**: the recipe wipes every other mod, so inside a route it is only ever the first step on a Normal (or any, but pointless) item; after it the route continues with Regal/Chaos/Exalted-type actions (Regal keeps the one mod and adds one). Second, **jewels**: no recipe places a mod on a jewel, so jewels get no start item from vendors.

## How the cost would be priced

Everything the recipes consume is cheap and in the price file's vocabulary except the quality gems:

- **Orb of Augmentation**: `poe.ninja` currency line (a vendor can also sell it: 4 Orbs of Transmutation at an Act 1 vendor, 28 Portal Scrolls, per the wiki's Vendor page, so the market price cannot exceed that; not recomputed here).
- **Coloured flasks** (Quicksilver, Granite, Ruby, Sapphire, Topaz, Amethyst): Normal utility flasks of a base type, sold by town vendors ("currency, wands, flasks, jewellery, and gems" vendors, https://www.poewiki.net/wiki/Vendor; a vendor sells items up to the area level of its town, at most 69). I did not find a poe.ninja line for ordinary flasks. Recommended price source: the trade API (a Normal flask of the base type) with a hand override as fallback, as for the bases of ADR-0007 (Q-3).
- **Quality gems** for the +1 recipes: two gems of the tag with a combined 40% quality. Recommended: the cheapest pair of gems of that tag with 20% quality or more from the trade API; gem prices are not in the scope of the other tickets, so this is the one new price line (Q-3).
- **The Normal base** itself: priced like any base (poe.ninja stash overview, ADR-0007), with the item level the target needs (VEN-03: the recipe keeps it).
- **Time and clicks**: free, as in ADR-0007. The recipe is not random, so the expected cost of a chain is the sum of its steps: for movement speed boots `base + 5 * price(Augmentation) + 5 * price(Quicksilver Flask)`, for physical `base + 8 * (Augmentation + Granite Flask)`.

How it fits the model: a vendor recipe is a deterministic action with several inputs (ADR-0011): the item and a bag of purchased ingredients, output a new state with the base, item level, quality, sockets, links and influences of the input and a single Magic mod. It has no chance node, no branching, and ordinary "buy" actions already compete with it (the cheaper of crafting and buying is the acquisition cost). Putting it in the action list therefore gives the start-item behaviour without a separate start-item-source type. The tier of the mod is part of the state only for the one family the item holds, so a chain of five recipes is five actions on a one-mod item.

## Open points

- **O-1 Elemental cap: T3 (wiki) or T2 (Craft of Exile)?** The wiki says "Maximum tier is Tier 3" for Fire, Cold and Lightning and T2 for Physical; CoE has `maxtier: 2` for all, counting from the top of ladders that include the level 82 tier. The wiki's version is the more recent one and matches caps by level (about 62), but it is not a patch note. *Recommended: use the wiki (T3) and mark the claim "wiki only"; one in-game chain of eight Ruby Flask recipes would settle it (Q-1).*
- **O-2 Does the result keep the base type?** "Create a new base item (with randomized base defences)" can mean the same base type with new defence rolls (the recipes name their output "Magic Boots", "Magic Weapon") or any base of the class. *Recommended: same base type; defence rolls are not targets (#81 item 5), so only the base type matters, and a mistake would show at the first in-game use.*
- **O-3 Reddit not read.** Two runs failed. *Recommended: rerun `gpt-research` when the worker is stable, aimed at O-2, O-4 and O-6, and at any 3.25-3.29 post that says a recipe changed.*
- **O-4 The flask ingredient.** The wiki does not say whether the flask may be of any rarity, quality or item level, or whether its item level can lower the result's ilvl (the generic sentence of the wiki page says the result takes the lowest ilvl of the inputs). `Item_level` says modifying recipes "typically keep the original item's ilvl". *Recommended: assume any flask of the base type and an unchanged item level; check with the same in-game chain as O-1 (Q-1).*
- **O-5 Which mods count as "the" mod of the input.** Does a crafted (bench) mod, a Veiled/unveiled mod or a multi-stat mod of the family count? Not stated. *Recommended: only plain explicit mods of the family, as the wiki says ("explicit mod").*
- **O-6 Input above the cap.** An input with the top-tier mod (35% movement speed, T1 physical) gives what? Not stated. *Recommended: treat as "recipe unavailable" (a route never needs it).*
- **O-7 3.28.0 "Added 1 new Vendor Recipe".** The wiki's version history does not say which; none of the recipes above are marked new. *Recommended: ignore; the page was read in full, and the recipe is not item-modifying or it would be listed.*
- **O-8 The wiki's Whetstone mod levels (1, 8, 18) and the data's (1, 11, 23) disagree.** Data wins; the recipes are low value anyway.
- **O-9 Gem qualification.** "Quality gems with the tag" lists no rule for support gems, awakened gems or corrupted ones. *Recommended: skill gems only, uncorrupted, until tested.*
- **O-10 Unknown on influenced inputs.** The wiki says influence is kept; whether an influenced Magic item can then be made Rare normally is the ordinary rule, not tested.

## Questions for the owner (the main chat asks him)

**Q-1 Do you want one short in-game check of the recipe chain?** It settles O-1 (T3 or T2 for Fire damage), O-2 (same base type?) and O-4 (does the flask matter). Option A: no check; the wiki's caps are used and the claims stay marked "wiki only". Option B: you or a tester run one chain in the Hideout or any town: a Normal one-hand sword, eight Ruby Flasks and eight Orbs of Augmentation, vendor each result back in, and note the last mod and the base name. The cost of B is about 15 minutes and a few chaos of currency; the cost of A is that a wrong cap makes the solver offer a Fire mod one tier too high or too low at the start of a route. *Recommendation: A for now, B before the vendor action is merged into the solver.*

**Q-2 Which recipes go into round 2?** Option A: the five valuable ones (spell gem weapons, movement speed, flat damage, chaos resistance, minion helmet), skipping Whetstone, Onyx and everything random. Option B: all that give a chosen mod, Whetstone included. Option C: only the first two. *Recommendation: A. The Whetstone and Onyx recipes add rules and prices for mods an Alteration spam reaches for pennies.*

**Q-3 How should the flasks and the quality gems be priced?** Option A: flasks and gems from the trade API (a Normal flask of the base type; the cheapest gem pair of the tag with 20% quality), with a hand override; this needs a new gem price line. Option B: the flasks at a fixed small hand-set price and the gems from the API. Option C: count flasks as free (the amount is small, the recipes are dominated by the Augmentations and, for gems, the gems). *Recommendation: B, because flasks are vendor goods with no market line, and the trade-API fetcher runs only when you start it (ADR-0007).*

## Draft claims for `src/crafting_system/rules/claims/`

14 draft rules in `docs/research/2026-10-31-vendor-claims-draft/vendor.yaml` (family `vendor`), same text as the resolution comment on #102. The real registry loader (`crafting_system.rules.registry.load_registry`) accepts the folder (14 rules loaded); the Craft of Exile quote is a substring of `package.js`. Claim ids map to the numbered claims above: `vendor.recipe_makes_a_new_magic_item_with_one_mod` VEN-01, `vendor.refused_on_fractured_and_corrupted_inputs` VEN-02, `vendor.item_level_kept_by_modifying_recipes` VEN-03, `vendor.movement_speed_boots_tier_up` VEN-04, `vendor.weapon_flat_damage_tier_up` VEN-05, `vendor.jewellery_chaos_resistance_tier_up` VEN-06, `vendor.tier_caps_match_the_datamined_ladders` VEN-07, `vendor.spell_gem_level_weapon_recipe` VEN-08, `vendor.helmet_minion_gem_recipe` VEN-09, `vendor.whetstone_weapon_recipes_low_tier` VEN-10, `vendor.five_to_one_is_a_random_unidentified_item` VEN-11, `vendor.onyx_amulet_recipes_keep_influence` VEN-12, `vendor.flat_elemental_damage_to_spells_recipe_removed` VEN-13, `vendor.coe_vendor_table_is_stale` VEN-14.

## Method and limits

- Wiki pages read 2026-10-31 in the built-in browser pane: Vendor_recipe_system (in full), Quicksilver_Flask, Vendor, Item_level, Version_3.19.0, Version_3.21.0, Version_3.29.0 (the Cloudflare check cleared by itself once; nothing was clicked). No `oldid` captured.
- Craft of Exile: `crsim_vendor` extracted from `sources/raw/coe/package.js` (27 entries) and its mod ids matched to `poec_data.json` (e.g. 2135 movement speed, 1972 fire, 661 chaos resistance); its tier lists agree with the datamined ladders.
- Datamined ladders: `mods.json` of 3.29.3.3, domain `item`, generation type prefix/suffix, ranked by required level among the mods whose first positive-weight spawn tag matches one representative base (Driftwood Sceptre, Iron Staff, Coral Ring, Onyx Amulet, a boots base).
- Not read: GGG's forum posts directly (the wiki's Version pages quote them), the PoE 1 trade site, poe.ninja (the price lines above are described, not measured), Reddit (failed). No recipe was run in game.
