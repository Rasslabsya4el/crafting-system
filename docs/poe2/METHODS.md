# Every PoE2 crafting method (0.5.5.10) and its proposed batch

Mirror of `docs/research/2026-10-30-crafting-methods-inventory.md` for Path of Exile 2. Date checked 2026-11-24. Game data 0.5.5.10 (patch line 0.5.5h, leagues Runes of Aldur and Forbidden Rites). **PoE2 1.0 launches on 2026-12-11** with a new "Reforging" system (Crimson Iron, fractured replacement mods): rows marked †  are expected to change then, and the whole table must be re-checked against the 1.0 patch notes (`docs/poe2/research/patch-history.md`, 1.0.0).

Sources: the research notes in `docs/poe2/research/` (keys S… are theirs) and the datamined extracts in `research/poe2/data/`. The claims behind each row are in `docs/poe2/claims/<family>.yaml`. Confidence and open questions per claim are in `docs/poe2/notes/`.

**Answer.** PoE2 0.5 has **52 item-crafting methods** (P2-01 to P2-52) plus 14 rows that exist in the files but are removed, disabled or not crafting (P2X-01 to P2X-14). Compared with PoE1 3.29: no Scouring, Alteration, fossils, Harvest, crafting bench, influence, Eldritch, beasts, Memory Strands, sockets/links/colours or Tempering/Tailoring; the recombinator exists in the files but is disabled since 0.5.0. New: three grades of the core orbs (a lowest modifier level), omens as modifiers of the next orb, desecration with a reveal choice, alloys, Liquid Emotions on jewels, augments in augment sockets, Temple of Atziri benches (double corruption), Verisium runeforging, the reforging bench.

Columns: **ID**; **Method**; **Preconditions**; **Outcome** (as far as known; "uniform" is Craft of Exile's model unless the game states it); **Cost unit**; **Weights** (does the outcome need the hidden spawn weights?); **Batch** proposed with the PoE1 batch logic of ADR-0013 (P1 = core single-item actions, P2 = single-item additions, P3 = two-input, P4 = corruption, P6 = augments and gem sockets, P7 = enchants/anoints, P8 = foresight).

## 1. Rarity and mods (P1 core)

| ID | Method | Preconditions | Outcome | Cost unit | Weights | Batch |
|---|---|---|---|---|---|---|
| P2-01 | Orb of Transmutation (plain, Greater, Perfect) | Normal item | Magic with 1 mod; Greater: mod level ≥ 44, Perfect ≥ 70 (the top tier the item level allows stays eligible) | 1 orb | yes | P1 |
| P2-02 | Orb of Augmentation (3 grades) | Magic with an open side (magic is 1 prefix + 1 suffix) | adds 1 mod on the open side; min level 44 / 70 | 1 orb | yes | P1 |
| P2-03 | Regal Orb (3 grades) | Magic | Rare, keeps its mods, adds 1; min level 35 / 50 | 1 orb | yes | P1 |
| P2-04 | Orb of Alchemy | Normal **or magic** item | Rare with exactly 4 random mods; current mods not kept | 1 orb | yes | P1 |
| P2-05 | Exalted Orb (3 grades) | Rare with an open slot (3+3) | adds 1 mod; min level 35 / 50 | 1 orb | yes | P1 |
| P2-06 | Chaos Orb (3 grades) | Rare with a removable mod | removes 1 random non-fractured mod (uniform), adds 1 (min level 35 / 50 on the added mod) | 1 orb | yes | P1 |
| P2-07 | Orb of Annulment | Magic or rare with a removable mod | removes 1 random non-fractured mod (uniform) | 1 orb | no | P1 |
| P2-08 | Divine Orb | Item with mods | rerolls every value within its tier | 1 orb | no | P1 |
| P2-09 | Fracturing Orb | Rare, ≥ 4 mods, not fractured | fractures 1 random explicit mod (uniform; unrevealed mods excluded) | 1 orb | no | P1 |
| P2-10 | Essences, Lesser / plain / Greater (19 families × 3) | Magic item | Rare: keeps its 1–2 mods, adds the guaranteed mod of its item category | 1 essence | no (the essence mod is fixed) | P1 |
| P2-11 | Perfect essences (19) and corrupted essences (Hysteria, Delirium, Horror, Insanity, the Abyss, the Breach) | Rare | removes 1 random mod, adds the guaranteed one (the Abyss: a Mark, 50/50 prefix or suffix) | 1 essence | no | P1 |
| P2-12 | Alloys (13, Runes of Aldur) | Rare | removes 1 random mod, adds a guaranteed mod (like a Perfect essence) | 1 alloy | no | P1 † |
| P2-13 | Omens of the Exalted Orb: Greater Exaltation (2 mods), Sinistral / Dextral Exaltation (side), Homogenising Exaltation (same type as an existing mod; Standard only), Catalysing Exaltation (consumes catalyst quality, weight ×(1+0.2·Q)) | an Exalted Orb use | changes the next Exalted Orb | 1 omen + the orb | yes | P1 (an omen is a parameter of the orb's action) |
| P2-14 | Omens of the Regal Orb: Homogenising Coronation | a Regal use | same type as an existing mod | 1 omen | yes | P1 |
| P2-15 | Omens of the Chaos Orb: Whittling (removes the lowest-level mod), Sinistral / Dextral Erasure (removes from one side) | a Chaos use | changes the removal | 1 omen | yes (the add) | P1 |
| P2-16 | Omens of Annulment: Sinistral / Dextral Annulment (side), Light (desecrated only) | an Annulment use | changes the removal | 1 omen | no | P1 |
| P2-17 | Omens of essences: Sinistral / Dextral Crystallisation | a Perfect or corrupted essence (alloys per Craft of Exile only) | removal from one side | 1 omen | no | P1 |
| P2-18 | Buy item (the Currency Exchange, the trade site) | – | a start item | market price | – | P1 (planner action, ADR-0011) |
| P2-19 | Hinekora's Lock | any item | the next currency's result is shown before it is kept; any change ends it | 1 lock | – | P8 |

## 2. Desecration (P2)

| ID | Method | Preconditions | Outcome | Cost unit | Weights | Batch |
|---|---|---|---|---|---|---|
| P2-20 | Abyss bones: Gnawed / Preserved / Ancient Jawbone (weapon, quiver), Rib (armour), Collarbone (jewellery); Altered Collarbone; Preserved Cranium (jewel); Preserved Vertebrae (waystone) | Rare of the bone's classes, no desecrated mod yet; Gnawed: item level ≤ 64; Ancient: modifier level ≥ 40 | adds 1 unrevealed desecrated mod (removes a random mod first when full); at most 1 per item | 1 bone | yes (reveal) | P2 |
| P2-21 | Reveal at the Well of Souls | an unrevealed desecrated mod | the player picks 1 of 3 options (ordinary mods and the lords' level-65 mods) | free | yes (option draw) | P2 (a chance node then a choice node, as ADR-0026's unveil) |
| P2-22 | Omens of desecration: Abyssal Echoes (one reroll of the options), Sovereign / Liege / Blackblooded (a random Ulaman / Amanamu / Kurgal mod, weapon or jewellery), Sinistral / Dextral Necromancy (side), Putrefaction (all mods replaced by up to 6 unrevealed, corrupts) | a bone use or a reveal | as stated | 1 omen | yes | P2 |

## 3. Other single-item changes (P2)

| ID | Method | Preconditions | Outcome | Cost unit | Weights | Batch |
|---|---|---|---|---|---|---|
| P2-23 | Omen of the Blessed + Divine Orb | item with implicits | rerolls implicit values only | omen + orb | no | P2 |
| P2-24 | Omen of Sanctification + Divine Orb | rare | each value × U(0.78, 1.22) of its current value; item becomes Sanctified (no further change) | omen + orb | no | P2 (a finish) |
| P2-25 | Catalysts (13 ring/amulet + 13 Refined for jewels) | ring, amulet (jewel for Refined) | adds catalyst quality of one tag; feeds Catalysing Exaltation | catalysts | no | P2 |
| P2-26 | Quality currency: Armourer's Scrap, Blacksmith's Whetstone, Arcanist's Etcher, Glassblower's Bauble | its item kind, quality < 20% | + quality (amount by item level or rarity: open) | 1 item | no | P2 |
| P2-27 | Liquid Emotions on jewels (0.5) | rare basic jewel (Ancient emotions: Time-Lost jewels) | removes 1 random mod, adds a guaranteed crafted mod (one crafted mod per item) | 1 emotion | no | P2 |
| P2-28 | Fluxes (Blazing, Chilling, Crackling, Void) | item with resistance mods | converts resistance mods to one element (Void: chaos). Thaumaturgic Flux (levels 2–20) levels Kalguuran gems and Perfect Flux sets an item's skills to level 20: not mod crafts | 1 flux | no | P2 † |
| P2-29 | Reforging bench, equipment recipes | 3 items of one base and rarity | 1 item of that base at the lowest item level among them (details open) | 3 items | yes | P3 (multi-input) † |
| P2-30 | Reforging bench, 3-to-1 of a kind | 3 essences / runes / emotions / waystones of one tier | 1 of the next tier | 3 inputs | no | input source (like a vendor recipe) |
| P2-31 | Verisium runeforging (Verisium Anvil) | an armour base | a "Runeforged" base with Runic Ward and lower defences; mods kept? (open) | Verisium ×N | no | P2 † |

## 4. Corruption (P4)

| ID | Method | Preconditions | Outcome | Cost unit | Weights | Batch |
|---|---|---|---|---|---|---|
| P2-32 | Vaal Orb | not corrupted | equipment: no change / reroll 1–3 mods / a corruption enchantment / +1 augment socket (caster weapons: quality); uniques: values ×0.78–1.22; odds unpublished (Craft of Exile: 25% each) | 1 orb | yes (reroll, enchant) | P4 |
| P2-33 | Corruption Altar (Temple, Act 3 and normal) | as the Vaal Orb | as the Vaal Orb | Vaal Orb | yes | P4 |
| P2-34 | Architect's Orb (Corruption Instiller) | corrupted equipment or jewel | modifies unpredictably or destroys (50/50 per community) | 1 orb | yes | P4 |
| P2-35 | Orbs of Sacrifice (Yaomac's weapon/quiver, Kopec's armour, Kamasa's jewellery, Yugul's jewel) | corrupted rare with a corruption enchantment | upgrades the enchantment, removes 1 random mod | 1 orb | no | P4 |
| P2-36 | Vaal Infusers (Armourer's, Blacksmith's, Arcanist's, Catalysing) | item at or above max quality (≥ 20%) | quality beyond the maximum up to +10%, chance to corrupt | 1 infuser | no | P4 |
| P2-37 | Vaal Cultivation Orb (Morphology Mechanism) | corrupted Vaal unique / other unique | replaces up to 2 mods / turns into a corrupted unique of the class | 1 orb | – | P4 (uniques) |
| P2-38 | Vaal Siphoner | corrupted rare jewellery | adds a kill threshold; at the threshold siphons a random mod and improves the others | 1 siphoner | no | P4 (a use-time effect: probably out) |
| P2-39 | Essence of Insanity (belt) | belt | "On Corruption, Item gains two Enchantments" | essence | no | P4 |

## 5. Augments and gem sockets (P6)

| ID | Method | Preconditions | Outcome | Cost unit | Weights | Batch |
|---|---|---|---|---|---|---|
| P2-40 | Artificer's Orb | martial weapon, wand, staff or armour below its socket maximum (2 on body armour and two-handers, 1 elsewhere) | +1 augment socket | 1 orb | no | P6 |
| P2-41 | Socket an augment: runes (Lesser to Perfect, named, Warding, Aldur's Legacy), soul cores (incl. Atziri's, Jiquani's, Theses), idols, Abyssal Eyes (Gaze), Emergent/Carved augments, Raven-Touched Shard | an empty augment socket of a fitting slot | a fixed stat per slot category (Bonded lines conditional) | 1 augment | no | P6 |
| P2-42 | Core Destabiliser (Soul Core Infuser) | a soul core | modifies it unpredictably or destroys it | 1 item | – | P6 (input source) |
| P2-43 | Orb of Extraction (Extraction Workbench) | equipment with augments | destroys the item, returns the augments | 1 orb | no | P6 (out of a route) |
| P2-44 | Jeweller's Orbs (Lesser 3, Greater 4, Perfect 5 support sockets) | skill gem (since 0.5.0 also items with granted skills) | sets the support socket count | 1 orb | no | P6 (gems: probably out) |

## 6. Enchants, anoints, uniques (P7 and out)

| ID | Method | Preconditions | Outcome | Cost unit | Weights | Batch |
|---|---|---|---|---|---|---|
| P2-45 | Instilling an amulet (Liquid Emotions ×3 at the Withered Willow) | amulet | a chosen notable passive (875 notables) | 3 emotions | no | P7 |
| P2-46 | Orb of Chance (+ Omen of Chance, Omen of the Ancients) | normal item (since 0.5.0 also tablets) | a unique of the base, or destroyed; odds unpublished | 1 orb | – | out (uniques) |
| P2-47 | Divine Orb on a unique | unique | rerolls values | 1 orb | no | out (uniques) |
| P2-48 | Mirror of Kalandra | equippable non-unique | a mirrored copy | 1 mirror | – | out (a sale, not a step) |
| P2-49 | Starlit Ore, Crests (Verisium Anvil) | – / a unique | a named unique / a Runeforged or Runemastered unique | ore, crest, Verisium | – | out (uniques) † |
| P2-50 | Waystone crafting: Transmutation…Chaos, Chaotic omens (0.5: exclude a mod type), Vaal Orb, Preserved Vertebrae, emotions on waystones, 3-to-1 tier upgrade | waystone | map mods | currency | yes | out (maps; owner's call) |
| P2-51 | Precursor tablet crafting: Orb of Chance (0.5), Ancient Infuser, Vaal Orb, reforging | tablet | tablet mods / uses | currency | yes | out (atlas; owner's call) |
| P2-52 | Crystallised Corruption, Gemcutter's Prism, uncut gems | gems | gem changes | currency | – | out (gems) |

## 7. In the files but not usable now (P2X)

| ID | Item or method | State | Source |
|---|---|---|---|
| P2X-01 | Expedition recombinator, Omen of Recombination | disabled in 0.5.0 ("The Recombinator has been disabled") | patch notes 0.5.0 |
| P2X-02 | Orb of Scouring, Orb of Alteration, Orb of Regret, Chromatic Orb | not in the game (records remain in the data) | poe2db, trade list |
| P2X-03 | Omens of Sinistral / Dextral Alchemy, Sinistral / Dextral Coronation, Greater Annulment | retired 0.3.0 | patch notes 0.3.0 |
| P2X-04 | Omen of Corruption | cannot be obtained since 0.5.0 (Standard exchange only) | patch notes 0.5.0 |
| P2X-05 | Omens of Homogenising Exaltation / Coronation | disabled from dropping 0.4.0; Standard exchange only | patch notes 0.4.0, 0.5.0 |
| P2X-06 | Mutated, Corrupted, Founders Verisium | "Acquisition: Not in game" | poe2db |
| P2X-07 | Fossils, resonators, Awakener's Orb, influenced Exalted Orbs, beasts nets, Delve and Heist items | PoE1 records in the PoE2 files, not in the game | export vs trade list |
| P2X-08 | Crafting bench (`crafted` domain: metamods, "Can have up to 3 Crafted Modifiers") | PoE1 records; PoE2 has no crafting bench | export vs trade list |
| P2X-09 | Bases of Swords, Axes, Daggers, Claws | marked released in repoe, not obtainable | items note |
| P2X-10 | Shards of Alteration, Alchemy, Annulment, Chaos, Exalted, Mirror, Fracturing, Binding, Horizon, Harbinger, Engineer, Ancient | in the data, not on the trade list | currency note |
| P2X-11 | Non-crafting omens (Refreshment, Resurgence, Amelioration, Answered Prayers, Secret Compartments, the Hunt, Reinforcements, Gambling, Bartering) | omens with no item effect | currency note |
| P2X-12 | Expedition Sagas (Aldur's, Medved's, Vorana's, Uhtred's, Olroth's) | logbook omens | currency note |
| P2X-13 | Cryptic Key, Scroll of Wisdom | not crafting (strongbox; identification) | currency note |
| P2X-14 | Chaotic waystone omens before 0.5.0 (guaranteed a type) | inverted in 0.5.0 | patch notes 0.5.0 |
