# Every crafting method in 3.29 and its batch (research for ticket #29)

Ticket: https://github.com/Rasslabsya4el/crafting-system/issues/29 (map #1). Date checked: 2026-10-30. Patch: 3.29.3.3, ordinary (non-Ruthless). Evidence rule: ADR-0005 (best information available today, no fixed source ranking, stale sources lose, every claim keeps its source).

**Answer.** 3.29 has **83 item-crafting methods** (rows M-01 to M-83 below; 12 of them marked `ask` because the item class or target kind is the owner's call), plus 28 rows that are out of scope, unobtainable or removed (X-01 to X-28). Most of the 83 already sit in B1 to B4 (ADR-0013). What the owner added on 2026-10-30 needs four new batches, because those methods do not change the item the way B1 to B4 assume:

- **B5, tier tilt**: Memory Strands (Orb of Remembrance, Orb of Unravelling) and the three Foulborn orbs. They change the tier odds of every other action, so the state gains a strand count.
- **B6, sockets, links and colours**: Jeweller's, Fusing, Chromatic, Binding, the bench socket crafts, the Black Mórrígan beast, three Omens. 3.29 reworked colours (sockets are white by default, Chromatic forces one non-white socket).
- **B7, enchantments**: Tempering Orb, Tailoring Orb and the Harvest quality enchants.
- **B8, foresight**: Hinekora's Lock, which turns a random action into a choice (preview, then decide).

Owner's list against 3.29, in one line each: **Runesmithing does not exist** (removed in 3.26; Tempering and Tailoring Orbs are a different mechanic from Heist and do exist). **Synthesis cannot be crafted any more** (the Harvest craft was removed in 3.29.0), so B4 is corruption only. **Incubators are gone** (3.29.0), **the Eternal Orb is drop-disabled**, **the Mirage items (Volatile Vaal Orb, Refracting Fog, Crystallised Rancour) cannot be obtained**. Everything else the owner named exists and is obtainable. Nobody had yet named: vendor recipes, anointing, Locus of Corruption double corruption, the Genesis Tree, Reflecting Mist, Sacred Orb, Hollow/Gilded fossils, Ancient Orb, the Black Mórrígan crafts, Kingsmarch disenchanting, flask enchants, gem and map crafts.

Rog's craft list (M-83) and the player-measured details marked "RS" come from Reddit; see section 6 for what is still open.

## 1. How to read the tables

Columns: **ID**; **Method**; **What it does**; **Inputs**; **3.29 status** with source keys (section 7); **Scope**: `in` (owner's rule, issue #29: everything except Necropolis gravecrafting and Allflame), `out` (owner's rule), `ask` (in scope by the rule, but the item class or target kind is the owner's call, see section 5); **Batch**: B1 to B4 as in ADR-0013, `B5` to `B8` proposed.

"Obtainable" means a player of an ordinary 3.29 league can get the input in game (a drop, a vendor, the Currency Exchange, a beast, a bench). A source that says "Ruthless only" or "drop disabled" counts as not obtainable.

Item classes below mean equipment, jewellery and jewels unless a row says otherwise.

## 2. Methods in scope (M rows)

### 2.1 Rarity, add and remove modifiers (B1 core)

| ID | Method | What it does | Inputs | 3.29 status | Scope | Batch |
|---|---|---|---|---|---|---|
| M-01 | Orb of Transmutation | Normal item to magic with 1 or 2 random mods. | 1 item (normal) | Core currency [W1, PDB] | in | B1 |
| M-02 | Orb of Alchemy | Normal item to rare. | 1 item (normal) | Core currency [W1, PDB] | in | B1 |
| M-03 | Regal Orb | Magic item to rare, adds one mod, keeps the others. | 1 item (magic) | Core currency [W1, PDB] | in | B1 |
| M-04 | Orb of Alteration | Rerolls all mods of a magic item. | 1 item (magic) | Core currency [W1, PDB] | in | B1 |
| M-05 | Orb of Augmentation | Adds one mod to a magic item with an open slot. | 1 item (magic) | Core currency [W1, PDB] | in | B1 |
| M-06 | Exalted Orb | Adds one mod to a rare item with an open slot. | 1 item (rare) | Core currency [W1, PDB] | in | B1 |
| M-07 | Chaos Orb | Rerolls all mods of a rare item. | 1 item (rare) | Core currency [W1, PDB] | in | B1 |
| M-08 | Orb of Annulment | Removes one random mod from a magic or rare item. | 1 item | Core currency [W1, PDB] | in | B1 |
| M-09 | Orb of Scouring | Removes all mods; rarity falls to the lowest possible (fractured mods stay). | 1 item | Core currency [W1, PDB] | in | B1 |
| M-10 | Divine Orb | Rerolls the numeric values of explicit mods within their tier. | 1 item | Core currency [W1, PDB] | in | B1 |
| M-11 | Essences, tiers 1 to 7 | Normal item to rare with one guaranteed essence mod (tiers 1 to 4); tiers 5 to 7 and corrupted essences also reforge a rare. | 1 item + 1 essence | Core; details in #8 [W1, PDB] | in | B1 |
| M-12 | Fossils + Chaotic resonators (25 fossils; Hollow adds an abyssal socket, Gilded adds a vendor-value implicit, Fractured changed in 3.29) | Reforges a rare with tag weights changed by the fossils; resonator sets how many fossils. | 1 item + 1 to 4 fossils + resonator | Core; details in #9; the Alchemical resonator is unobtainable [W1, PDB] | in | B1 |
| M-13 | Harvest reforges (16 tagged crafts + "more likely / less likely same types") | Reforges a rare, guaranteeing one mod of a tag (Fire, Cold, ..., Drop); respects Attack/Caster/Prefix/Suffix metamods since 3.27. | 1 item + Lifeforce | Core; details in #10 [W2, N3.27] | in | B1 |
| M-14 | Fracturing Orb | Fractures one random explicit mod of a rare with 4+ mods; the mod cannot change afterwards. | 1 item | Core currency [W1, PDB]; details in #12 | in | B1 |
| M-15 | Bench crafted mods (732 options, one crafted mod, or three with the multimod) | Adds a chosen crafted mod. | 1 item + currency | Always available; every craft counted as unlocked (#28) [W4, bench export in #11] | in | B1 |
| M-16 | Bench metamods (5): Prefixes Cannot Be Changed, Suffixes Cannot Be Changed, Cannot roll Attack Modifiers, Cannot roll Caster Modifiers, Can have up to 3 Crafted Modifiers | Locks sides or tag groups, or allows 3 crafted mods, for later crafting. | 1 item + 1 to 2 Divine Orbs | Core [W4, #11] | in | B1 |
| M-17 | Bench: reroll 3 random mods (3 Chaos) / reroll 1 random mod (8 Chaos) | Partial rerolls of a rare. New in 3.29.0. | 1 item + Chaos Orbs | 3.29.0 note, in the bench export [N3.29, #11] | in | B1 |
| M-18 | Bench: Remove Crafted Mods; Remove Enchantments; Reroll the Rarity of a non-unique item | Removes crafted mods (1 Scouring); removes enchants (3 Scouring); acts as an Orb of Chance plus Scouring (1 Chance). | 1 item | Always available [W4] | in | B1 (the rarity reroll also belongs to M-27) |
| M-19 | Buy item | Start from a market item (base, mods, fractured, influenced, strands). | Chaos-priced item | Planner action, not a game mechanic (ADR-0011) | in | B1 |

### 2.2 Single-item additions (B2)

| ID | Method | What it does | Inputs | 3.29 status | Scope | Batch |
|---|---|---|---|---|---|---|
| M-20 | Blessed Orb | Rerolls the implicit mod values. | 1 item | Core currency [W1, PDB] | in | B2 |
| M-21 | Shaper's, Elder's, Crusader's, Hunter's, Redeemer's, Warlord's Exalted Orb (6 orbs) | On a rare without influence/fracture/synthesis: adds that influence and one influenced mod. | 1 item | Core [W1, PDB] | in | B2 |
| M-22 | Orb of Dominance | On body armour, boots, gloves or helmet with 2+ influenced mods: removes one, upgrades another; the top tier becomes Elevated. | 1 item | Core [W1, PDB] | in | B2 |
| M-23 | Eldritch Embers (4 grades) and Ichors (4 grades) | Adds an Exarch or Eater implicit to body armour, boots, gloves or helmet. | 1 item + ember or ichor | Core [W1, PDB]; design in ADR-0002 | in | B2 |
| M-24 | Eldritch Chaos / Exalted / Annulment Orb | Reroll / add / remove prefixes or suffixes, side set by the dominant Exarch or Eater implicit. | 1 item | Core [W1, PDB] | in | B2 |
| M-25 | Orb of Conflict | Raises one Exarch/Eater implicit tier, lowers the other. | 1 item | Core [W1, PDB] | in | B2 |
| M-26 | Veiled Chaos Orb; Veiled Exalted Orb; unveiling | Chaos-like reroll with one veiled mod; remove a mod and add a veiled mod; unveiling shows the veiled mod's options and the player picks one (CoE `modunveil`). | 1 item | Core; Veiled Chaos is again its own currency since 3.26 [W1, PDB, N3.26, CoE] | in | B2 |
| M-27 | Orb of Chance (with Omen of Fortune, and "scour-chancing" with Orb of Scouring or the 1-Chance bench craft) | Normal item to magic, rare or unique at random; unique odds depend on the unique's tier; the Omen forces a unique when the base can be one. | 1 item (normal), optional Omen | Core currency [W1, PDB, W-chance]; Omen from Ritual rewards [W5] | in | B2 (new; the unique result is a failure unless the owner wants unique targets, section 5) |
| M-28 | Catalysts (13) | Add quality of a type to jewellery; boosts mods of a tag. | Jewellery + catalyst | Exist [PDB]; since 3.29 Ultimatum is the only source [N3.29] | in | B2 |
| M-29 | Harvest: add a tagged mod and remove a random mod (11 crafts, non-influenced items) | Replaces one random mod with one of the chosen tag. | 1 item + Lifeforce | Core [W2] | in | B2 (new) |
| M-30 | Harvest: swap resistance element (6 crafts) | Turns one resistance mod into another element, same tier. | 1 item + Lifeforce | Core [W2] | in | B2 (new) |
| M-31 | Harvest: swap added damage element (6 crafts) | Turns added fire/cold/lightning damage into another element, same tier; not on crit multiplier mods (3.28.0 hotfix 8). | 1 item + Lifeforce | Core [W2] | in | B2 (new) |
| M-32 | Harvest: reroll influences with new mods; reforge an influenced rare keeping an influence mod | Randomises the influence types and rerolls; or rerolls guaranteeing an influenced mod. | 1 influenced item + Lifeforce | Core [W2] | in | B2 (new) |
| M-33 | Beast: Add a Prefix, Remove a Random Suffix; Add a Suffix, Remove a Random Prefix | Swaps a side; mod level uses the beast's level, not the item's. | 1 rare + 1 beast | Core [W3] | in | B2 |
| M-34 | Beast: Add a Mod to a Shaper / Elder / Crusader / Hunter / Redeemer / Warlord Item (6 recipes) | Adds an influenced mod of that influence. | 1 influenced item + 2 beasts | Core [W3] | in | B2 |
| M-35 | Beast: add a crafted metamod to a non-unique item | Picks one of the five metamods at random; needs an empty slot. | 1 item + Wild Bristle Matron | Core [W3] | in | B2 |
| M-36 | Beast: craft an Aspect skill (4 aspects, level 20 or level 30 with The Black Mórrígan) | Adds a suffix giving an Aspect skill. | 1 item + beasts | Core [W3] | in | B2 |
| M-37 | Beast: flask suffixes (11 recipes) | Adds a chosen ailment-immunity suffix to a flask with no suffix. | 1 flask + 1 beast | Core [W3] | ask | B2 if flasks are in |
| M-38 | Beast: Fracture a modifier on a rare Talisman with 4+ mods; two mods with 6+ (with The Black Mórrígan) | Fracture on a Talisman only; replaced the Split recipes in 3.29.0. | 1 Talisman + beasts | 3.29.0 [W3, N3.29] | in | B2 |
| M-39 | Beast: reroll a Talisman base type | Keeps implicit and explicit mods. | 1 Talisman + Craicic Squid | 3.29.0 [W3] | in | B2 |
| M-40 | Beast: Reroll a Watcher's Eye modifier | Rerolls one aura-dependent mod (not life, mana, ES). | 1 Watcher's Eye + beast | Core [W3] | ask | B2 if jewels with unique bases are in |
| M-41 | Vendor recipes (item-modifying: tier-up a magic item's mod, make a magic item with a given mod, "full rare set" outputs) | Deterministic or semi-deterministic item changes from the vendor. | Items | Core [W-vendor, CoE "Vendor recipees"]; not read in detail | ask | B2 start-item source (low priority) |
| M-42 | Sacred Orb | Rerolls base defence values of armour (not mods). | Armour | Core, since 3.16 [W1, PDB] | ask | B2 only if a target names a base defence roll |

### 2.3 Two-input actions (B3)

| ID | Method | What it does | Inputs | 3.29 status | Scope | Batch |
|---|---|---|---|---|---|---|
| M-43 | Awakener's Orb | Destroys one item, merges its influence into another of the same class; the result is rerolled with both influences. | 2 items | Core [W1, PDB] | in | B3 |
| M-44 | Recombinators: predictable and unpredictable modes (armour, weapon, jewellery) | Merges the mods of two items into a new one (ADR-0012). | 2 items + Thaumaturgic Dust | Core since 3.26 [W1, N3.26] | in | B3 |
| M-45 | Beast: Imprint of a Magic item; of a Rare Talisman | Stores the item state for later restoration (not for fractured or corrupted items). | 1 item + beast, then Imprint | 3.29.0 for talismans [W3, W-imprint]; the Eternal Orb is drop-disabled, see X-05 | in | B3 |
| M-46 | Kingsmarch disenchanting (Rog, the Disenchanter) | Turns items into Thaumaturgic Dust, the recombinator's cost. | Items | In Kingsmarch and via Rog in towns and hideouts since 3.27 [W-rog, N3.27] | in | B3 (a price input only) |

### 2.4 Corruption (B4)

| ID | Method | What it does | Inputs | 3.29 status | Scope | Batch |
|---|---|---|---|---|---|---|
| M-47 | Vaal Orb on equipment | Corrupts; four equally likely outcomes: nothing changes, a corrupted implicit, a white socket turns non-white (3.29.0), or a reroll to a rare with 6 random mods, sockets and links ("brick"). | 1 item | Core [W-vaal, N3.29] | in | B4 |
| M-48 | Locus of Corruption double corruption | Four equally likely outcomes: two corrupted implicits, all white sockets turn non-white (3.29.0), reroll into a random rare, or destroyed. | 1 item at the altar | Core (Incursion temple room) [W-locus, N3.29] | in | B4 |
| M-49 | Tainted Chaos Orb | On a corrupted rare: reforges, or removes all mods (fractured mods stay). | Corrupted item | Beyond drops [W-tainted] | in | B4 |
| M-50 | Tainted Exalted Orb | On a corrupted rare: adds or removes a mod. | Corrupted item | Beyond drops [W-tainted] | in | B4 |
| M-51 | Tainted Divine Teardrop | Each mod's tier goes up one, down one or stays; ignores crafted mods and metamods. | Corrupted rare | Beyond drops [W-tainted] | in | B4 |
| M-52 | Tainted Mythic Orb | Turns a corrupted non-unique to unique or destroys it; needs a base with a drop-anywhere unique. | Corrupted item | Beyond drops [W-tainted] | ask | B4 if unique targets are in |
| M-53 | Tainted Jeweller's Orb | Adds or removes a socket (50/50). | Corrupted item | Beyond drops [W-tainted] | in | B4 (sockets part in B6) |
| M-54 | Tainted Orb of Fusing | Adds or removes a link (50/50). | Corrupted item | Beyond drops [W-tainted] | in | B4 (links part in B6) |
| M-55 | Tainted Chromatic Orb | Rerolls colours, ignoring attribute bias; forces one non-white. | Corrupted item | Beyond drops [W1, PDB] | in | B4 (colour part in B6) |
| M-56 | Tainted Armourer's Scrap; Tainted Blacksmith's Whetstone; Tainted Catalyst | Randomise quality of corrupted armour (1 to 20%), weapons (1 to 20%), jewellery (quality and type). | Corrupted item | Beyond drops (Tainted Catalyst and Oil do not drop from Beyond demons) [W-tainted] | ask | B4 only if quality is a target |
| M-57 | Bench on corrupted items | Socket crafts allowed with extra Vaal Orbs; mod crafts follow the unmodifiable rule. | Corrupted item | Core [W4] | in | B4 |

### 2.5 Tier tilt (proposed B5)

| ID | Method | What it does | Inputs | 3.29 status | Scope | Batch |
|---|---|---|---|---|---|---|
| M-58 | Memory Strands on an item | Items with strands roll higher mod tiers in every later action: `rollable_tiers = floor((100/(2.5 * strands + 147.5)) * (total_tiers - 1)) + 1`; each currency spends a number of strands (essences 0 to 80, Orb of Unravelling all). | State of the item | Core since 3.26; larger effect since 3.28 [MS, W-mem, N3.26, N3.28] | in | B5 |
| M-59 | Orb of Remembrance | Randomises the strand count of a normal equipment item. | 1 item (normal) | Drops from the Incarnation of Neglect and the Scholar's Vault [W-mem] | in | B5 |
| M-60 | Orb of Unravelling | Spends all strands to try to raise explicit mod tiers; ignores the prefix/suffix metamods; cannot raise influenced mods to Elevated. | 1 item with strands | Drops from the Incarnation of Dread [W-mem, MS] | in | B5 |
| M-61 | Foulborn Orb of Augmentation | Augmentation with the lower mod tiers culled: tiers kept = `ceil(N/2)` for N ≤ 6, `floor(N/2)+1` above; weights of the kept tiers scaled by N/K. Same effect as +30 strands. | 1 item (magic) | Genesis Tree, from a Lavish Wombgift [W-foul] | in | B5 |
| M-62 | Foulborn Regal Orb | Regal with the same tier cull. | 1 item (magic) | Genesis Tree [W-foul] | in | B5 |
| M-63 | Foulborn Exalted Orb | Exalted with the same tier cull. | 1 item (rare) | Genesis Tree [W-foul] | in | B5 |
| M-64 | Genesis Tree (equipment womb) | Births items from Wombgifts with the passive-tree tilt (mod types up to 300%, tier rating); also births the Foulborn orbs. | Wombgift + Hiveblood | Core; the 3.29.0 notes cut points to 16 [W-gen, N3.29] | ask | B5 as a "buy item" source |

### 2.6 Sockets, links and colours (proposed B6)

| ID | Method | What it does | Inputs | 3.29 status | Scope | Batch |
|---|---|---|---|---|---|---|
| M-65 | Jeweller's Orb | Rerolls the number of sockets; quality and item level raise the odds. | 1 item | Core [W1, PDB] | in | B6 |
| M-66 | Orb of Fusing | Rerolls the links. | 1 item | Core [W1, PDB] | in | B6 |
| M-67 | Chromatic Orb | Rerolls colours, forces one non-white socket (3.29.0); rarer, no longer sold by vendors. | 1 item | Core [W1, N3.29] | in | B6 |
| M-68 | Orb of Binding | Normal item to rare with up to four linked sockets; extra sockets are lost. | 1 item (normal) | Currency Exchange (20 gold) and a 2-orb beast recipe; the wiki's "Harbinger drop" text is stale since 3.28 [PDB, W-bind, W3, N3.28] | in | B6 |
| M-69 | Bench socket crafts (number 2 to 6; links 2 to 6; "at least 2 / 3 / 4 non-white sockets" for 5 / 20 / 75 Chromatic Orbs) | Deterministic number or links; colour crafts replaced the red/green/blue crafts in 3.29.0. | 1 item + currency | Core [W4, N3.29] | in | B6 |
| M-70 | Beast: Black Mórrígan max links; max sockets; Four-Linked Helmet; Fully-linked Six-socket Rare | Gives the maximum links or sockets, or a ready rare. | Item + beasts | Core; The Black Mórrígan spawns rarely in tier 14+ maps [W3, N3.29] | in | B6 |
| M-71 | Omen of the Jeweller / Connections / Trichromatism | The next Jeweller's / Fusing / Chromatic Orb gives max sockets / max links / at least one red, green and blue. | Omen + orb | Ritual rewards, Omen Cairns [W5] | in | B6 |
| M-72 | Vorici's Fortification Safehouse bench | Rank 1: reforge the number of sockets 100 times and keep the best. | 1 item, safehouse reward | 3.29.0 reworked; temporary bench [N3.29, W1] | ask | B6 (probably out, it is a temporary reward) |
| M-73 | Hollow Fossil abyssal socket | Adds an Abyssal Socket mod, may replace a socket and break links. | Fossil step | Core, covered in #9 [W1] | in | B1 (fossils) with a B6 interaction |
| M-74 | Quality on items (Armourer's Scrap, Blacksmith's Whetstone) | Raises item quality; since 3.29 quality also raises the odds of non-white sockets and links. | 1 item | Core [W1, N3.25, N3.29] | in | B6 |

### 2.7 Enchantments (proposed B7)

| ID | Method | What it does | Inputs | 3.29 status | Scope | Batch |
|---|---|---|---|---|---|---|
| M-75 | Tempering Orb | Adds or replaces a weapon enchantment from a weighted pool (for example "Can have 1 additional Crafted Modifier", weight 80; "+N% explicit X modifier magnitudes" with or without a downside); may reforge the sockets. | 1 weapon | Drops from Curio Displays in the last room of any Grand Heist [W-temper] | in | B7 |
| M-76 | Tailoring Orb | Same for body armour; not usable on items with fixed sockets. | 1 body armour | Grand Heist Curio Displays [W-temper] | in | B7 |
| M-77 | Harvest quality enchants (8 body armour, 6 weapon) | Quality stops adding defences or physical damage and gives another stat (life, mana, attributes, a resistance; range, area, accuracy, attack speed, crit, elemental damage). | 1 item + Lifeforce | Core [W2] | in | B7 |
| M-78 | Instilling Orb, Enkindling Orb, bench flask enchants | Flask enchantments (flasks only). | 1 utility flask | Core; the Harvest flask enchants were removed in 3.28.0 [W1, W2] | ask | B7 if flasks are in |
| M-79 | Anointing (oils at Cassia or the Blight tab; Prismatic and Tainted Oil) | Adds a notable passive enchant to an amulet, ring or belt. | Item + 2 to 3 oils | Core [W1, PDB] | ask | B7, only if a target names an anoint |

### 2.8 Foresight and information (proposed B8)

| ID | Method | What it does | Inputs | 3.29 status | Scope | Batch |
|---|---|---|---|---|---|---|
| M-80 | Hinekora's Lock | Lets one item preview the outcome of the next currency used on it; any change to the item ends the preview; not for gems or corrupted items; no preview for bench, Harvest, recombinator, beastcrafting or the Locus. | 1 item (any non-corrupted) | Drops anywhere since 3.23; divination card recipes; Black Mórrígan beast recipe for a magic item [W-lock] | in | B8 |

### 2.9 Remaining methods that act on the item

| ID | Method | What it does | Inputs | 3.29 status | Scope | Batch |
|---|---|---|---|---|---|---|
| M-81 | Mirror of Kalandra | Copies an item; the copy is mirrored (no more crafting). | 1 item | Core [W1, PDB] | ask | out of the planner (a terminal sale, not a route step) |
| M-82 | Reflecting Mist | Splits a rare ring or amulet into two mirrored items with enhanced, possibly inverted mods (3.29.0 reduced the enhancement). | 1 rare ring or amulet | Drops from a Reflecting Mist encounter in an Atlas anomaly [W-mist, N3.29] | ask | B3-like (one input, two outputs), proposed late |
| M-83 | Rog, the Dealer (Expedition) | After a purchase, offers crafts for Order Artifacts: add, remove or reroll mods in set ways; offers can be skipped but not twice in a row. | A bought rare item + Order Artifacts | Core Expedition; the "random Incubator" craft was removed in 3.29.0 [W-rog, N3.29]; craft list: see section 6 | in | B2 once the list is known |


## 3. Not in scope, unobtainable or removed (X rows)

| ID | Method | Status in 3.29 | Source |
|---|---|---|---|
| X-01 | Necropolis gravecrafting (corpses) | Out by the owner's rule; not core either. | owner, W1 |
| X-02 | Allflame crafting: Dead Man's Sulphur, ghostly copies, Intangibility, and the ten Ducats (Brinehook's, Cyaxan's, Kishara's, Genteel's, Rotmother's, Merrick's, Katakohi's, Telesia's, Tzamoto's, Ukatoa's) | Out by the owner's rule; league mechanic. | owner, W1 |
| X-03 | Runesmithing (runes, enchant weapons at a table) | **Does not exist.** Settlers-only 3.25; removed in 3.26.0; all runes deleted in 3.25.3g; replaced by Runegrafts (passive tree, not an item craft). | W-rune, N3.26 |
| X-04 | Incubators, "Rog random Incubator craft" | Removed in 3.29.0; cannot be obtained. | N3.29 |
| X-05 | Eternal Orb (imprint) | Drop-disabled in core, Ruthless only. Imprints come only from the two beast recipes (M-45). | W-eternal, W-imprint |
| X-06 | Synthesis as a craft (Harvest "Synthesise an item") | Removed in 3.29.0. Synthesised items still drop (synthesised maps, 3.28.0 notes); the beast reroll of a synthesis implicit now works on uniques only. | W2, N3.29, N3.28 |
| X-07 | Splitting items (beast or Fractured Fossil) | Replaced in 3.29.0 by Talisman fracture and a changed Fractured Fossil. | W3, N3.29 |
| X-08 | Harvest craft: reforge keeping all prefixes / suffixes | Removed (the wiki labels it "removed"); CoE still lists it (`hresf`, `hrepf`). | W2, CoE |
| X-09 | Harvest crafts: annul of a type, divine of a type, non-type to type, "high-tier" crafts | Removed in 3.14.0 and 3.19.0; CoE still lists them. | W2, CoE |
| X-10 | Harvest craft: fracture a random mod | Removed in 3.20.0 (the Fracturing Orb replaced it). | W2 |
| X-11 | Harvest flask enchants; Harvest Synthesise; Harvest recolour of one socket | Removed in 3.28.0 / 3.29.0. | W2, N3.29 |
| X-12 | Mirage items: Volatile Vaal Orb, Refracting Fog, Crystallised Rancour crafts, Djinn-Touched Vaal Orb | Not obtainable: Mirage is not core. The Djinn-Touched Vaal Orb is only a Leo bench item (Leo's bench was removed before 3.19). | W-mirage, W-djinn, N3.28 |
| X-13 | Coins of Power, Skill, Knowledge (gem imbue corruption, 3.28) | Gem crafting; origin Mirage; obtainability not verified. | N3.28, PDB |
| X-14 | Sentinels and Power Cores | Not an item mod craft (data exists, no item mods). | PDB |
| X-15 | Orb of Horizons, Harbinger's Orb, Engineer's Orb, Infused Engineer's Orb | Removed (3.28.0, and Infused Engineer's Orb unusable in 3.28.0). | W1 |
| X-16 | Syndicate benches of Aisling, Hillock, Jorgin, Leo, Rin | Removed in 3.15 to 3.28. | W1 |
| X-17 | Beast "Create a Rare Talisman", "Amulet to Talisman" | Replaced in 3.29.0. | W3, N3.29 |
| X-18 | Divine Font enchants for gloves, boots, helmets, belts | Removed in 3.23.0; the Font now serves gems. | W1 |
| X-19 | Old Recombinator currency (Sentinel era) | Replaced by the Kingsmarch recombinator in 3.25/3.26. | W1, N3.26 |
| X-20 | Tainted Blessing; Breach Blessings | Breach Blessings removed in 3.27.0, replaced by Flesh of Xesht (Breach uniques only). | W1, N3.28 |
| X-21 | Alchemical resonator | Unobtainable (#9). | #9 |
| X-22 | Provisioning Wombgifts for weapons and quivers; implant currency (graft) | Keepers league items, did not go core. | W1 |
| X-23 | Map Device crafting options | Removed in 3.28.0. | N3.28 |
| X-24 | Incursion unique upgrades (vials), Coin of Restoration, Coin of Desecration, Flesh of Xesht, Ancient Orb, "unique to another unique" beast | Unique-item transformations: obtainable but not mod crafting of a rare. | W1, W3 |
| X-25 | Item generation: "Create a Unique <class>" beasts, "Create a Corrupted Gem", "Create a Scarab/Map" | Output is a drop-like item, not a craft of an existing item. | W3 |
| X-26 | Gem crafting: Gemcutter's Prism, Lapidary Lens, Divine Font gem options, Facetor's Lens, Regrading Lenses, Gemcutter's Lens, Vaal on gems | Exists; not an item with mods. Section 5, question 1. | W1, PDB |
| X-27 | Map and strongbox crafting: Chisels, Orb of Intention (more strands on map drops), Delirium Orbs, Scarabs, Sextants (gone), Harvest map crafts, beast map mod crafts, Orb of Intention | Exists; not equipment. Section 5, question 1. | W1, W3, PDB |
| X-28 | Shard conversions (Alchemy Shard, Chaos Shard, etc.), Orb of Regret, Orb of Unmaking, Scroll of Wisdom (identify, free in towns since 3.27.0) | Currency exchange, passive refunds or identification; no decision. | PDB, N3.27 |

## 4. Check of the owner's list

| Owner named | Exists in 3.29? | Where it sits |
|---|---|---|
| Orb of Chance | Yes | M-27 (with Omen of Fortune and scour-chancing); B2 |
| Sockets, links, colours | Yes, reworked in 3.29.0 | M-65 to M-74, M-53 to M-55; B6 |
| Harvest crafts other than reforges | Yes: 11 add-remove, 6 resistance swaps, 6 damage swaps, 1 influence reroll, 1 influenced reforge, 14 quality enchants | M-29 to M-32, M-77; B2 and B7 |
| Rog (Expedition) | Yes | M-83; B2 |
| Runesmithing | **No** (removed 3.26.0) | X-03; nothing to build |
| Tempering Orb, Tailoring Orb | Yes (Heist), a different mechanic from Runesmithing | M-75, M-76; B7 |
| Foulborn currencies | Yes (3 orbs) | M-61 to M-64; B5 |
| Memory Strands, Orb of Remembrance | Yes | M-58 to M-60; B5 |
| Hinekora's Lock | Yes | M-80; B8 |
| Tainted currencies | Yes (11 items incl. Catalyst and Oil) | M-49 to M-56; B4 |
| Orb of Unravelling | Yes (not named, but Memory Strands need it) | M-60; B5 |

## 5. Questions only the owner can answer

1. **Which item types are in v1?** The inventory assumes equipment, jewellery and jewels. Flasks (beast suffixes, Instilling), gems (Prism, Lapidary, Coins) and maps (Chisels, Delirium, map mods) have their own crafts. Recommendation: equipment, jewellery and jewels only, since the target language is mods.
2. **Are unique items ever a target?** It matters for the Orb of Chance (a unique result), Omen of Fortune, Tainted Mythic Orb, Ancient Orb and the beast "Create a Unique". Recommendation: no; a unique result of an Orb of Chance counts as a failed try.
3. **Hinekora's Lock changes how a plan is read** (the plan can preview and then decide, so it is a different kind of plan). Do you want it in v1 as a real peek-then-decide option? Recommendation: yes, in the last batch (B8), after everything else is stable.
4. **Targets beyond mods:** quality, an anoint, a base defence roll (Sacred Orb), an enchant stat. Recommendation: quality only as it affects sockets (B6), enchants in B7, anoints and base defence not at all.
5. **Genesis Tree, vendor recipes, Vorici bench, Reflecting Mist:** include as ways to get a start item, or leave out? Recommendation: Genesis Tree and vendor recipes as "buy item" sources later; the Vorici bench is a temporary reward, leave out; Reflecting Mist only after B3.
6. **Memory Strands and the start item.** ADR-0008 says start items carry no strands. The owner added Memory Strands to v1; should a plan be allowed to start with strands bought on an item, and use Remembrance on a fresh base? Recommendation: yes, both.

## 6. What is still open (Reddit and unchecked facts)

- **Rog's craft list** is not on the wiki or PoEDB. M-83 therefore has no list yet; the list and the odds are taken from Reddit, section 8 (to be completed).
- **Orb of Chance's odds** of rarity and unique by unique tier (wiki says tier-dependent): not measured here.
- **3.29 socket numbers** (Jeweller's, Fusing and Chromatic odds after the rework; bench 6-link/6-socket costs) are not read yet; the wiki mechanics pages may lag the 3.29.0 notes.
- **Tainted outcome odds** besides the 50/50 on sockets and links (Tainted Chaos reforge vs remove, Divine Teardrop up/down/same) are not known.
- **Tempering/Tailoring pool weights**: summed from the wiki tables on 2026-10-30 (the weight column has a blank header and is not filtered by weapon class): the Tempering Orb table has 136 enchants with total weight 6,160, so "Can have 1 additional Crafted Modifier" (weight 80) is 80/6,160 = 1.3% if every enchant can roll on the weapon; the Tailoring Orb table has 75 enchants with total 3,376. Which enchants a given weapon class or body armour can really roll, and whether the 3.29.0 removal of white-socket and all-one-colour enchants changed the weights, is not checked.
- **Syndicate benches still running in 3.29** (Guff's Fading Reflecting Mist, Vorici's rank rewards): the wiki names only the removed ones.
- **Vendor recipes:** the wiki list was only skimmed; a ticket of its own is needed if the owner wants them.

## 7. Sources

Wiki pages read in the built-in browser on 2026-10-30 (https://www.poewiki.net/wiki/...), page revisions as served that day:

- W1 `Crafting` (all families, current to 3.29).
- W2 `Harvest_crafting` (full craft list, costs, version history to 3.29.0).
- W3 `Beastcrafting` (recipe list, 3.29.0 changes).
- W4 `Crafting_Bench` (socket, metamod and other crafts).
- W5 `Omen` (12 omens, how to obtain, 3.24 core).
- W-foul `Foulborn_currency_item`, `Foulborn_Regal_Orb`.
- W-temper `Tempering_Orb`, `Tailoring_Orb`.
- W-rune `Runesmithing` (version history), W-rog `Rog`, W-lock `Hinekora's_Lock`, W-mem `Orb_of_Remembrance`, `Orb_of_Unravelling`.
- W-eternal `Eternal_Orb`, W-imprint `Imprint`, W-bind `Orb_of_Binding`, W-mirage `Mirage`, W-refrac `Refracting_Fog`, W-djinn `Djinn-Touched_Vaal_Orb`, W-mist `Reflecting_Mist`.
- W-tainted `Tainted_Chaos_Orb`, `Tainted_Exalted_Orb`, `Tainted_Divine_Teardrop`, `Tainted_Mythic_Orb`, `Tainted_Jeweller's_Orb`, `Tainted_Orb_of_Fusing`.
- W-vaal `Vaal_Orb`, W-locus `Locus_of_Corruption`, W-gen `The_Genesis_Tree`, W-chance `Orb_of_Chance`, W-vendor `Vendor_recipe_system` (skimmed).
- N3.25 to N3.29: `Version_3.25.0` to `Version_3.29.0` on the wiki (patch notes, 3.29.0 for the socket rework, Incubators, Talisman revamp, Rog, Harvest, bench rerolls).
- PDB: PoEDB currency list https://poedb.tw/us/Stackable_Currency and `Orb_of_Binding` (item data, 3.29).
- CoE: the Craft of Exile emulator's method tree (`poec_cmethods`), https://www.craftofexile.com/?a=emulator, read 2026-10-30: currency (27 entries incl. Awakener, Dominance, Fracturing, Vaal, Veiled), Fossil, Harvest (add/remove, replace, non-type, annul, divine, reforge, resists, high-tier, other), Essence, Catalyst, Beast crafting (prefix to suffix, suffix to prefix, imprint, restore imprint, reroll values, aspects), Eldritch (12), Scourge (Tainted Exalted, Tainted Divine Teardrop, corruption), Locus, Vendor, Bench, Condition check, Unveil, Meta, plus Graveyard and Genesis Tree. The Harvest "annul / divine / non-type / high-tier / keep prefixes" entries, the beast "reroll values" entry and the Graveyard are stale or out (X-01, X-08, X-09).
- MS: the existing Memory Strands report on branch `research/reddit-sources`, https://github.com/Rasslabsya4el/crafting-system/blob/research/reddit-sources/docs/research/2026-10-30-memory-strands.md (reused, not redone).
- #7 to #12, #27, #28: earlier research tickets on the same map for B1 mechanics.

## 8. Reddit findings (gpt-research)

To be completed (job `20261030-205628-b3eb`): Rog craft list; Harvest and beast confirmations; Orb of Chance odds; 3.29 socket math; Tempering/Tailoring use; Hinekora's Lock; Tainted outcomes; Foulborn and Genesis Tree; anything missing.
