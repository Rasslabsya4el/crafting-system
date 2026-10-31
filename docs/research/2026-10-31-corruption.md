# Corruption and Tainted currencies in 3.29 (ticket #92)

Question: how do corruption and the Tainted currencies work in PoE 1 3.29 (inventory rows M-47 to M-57 without M-52)?
Checked 2026-10-31 against patch 3.29.3.3. Written for the B4 design grill (#95). Owner scope from #81: equipment, jewellery and jewels;
unique items are never a target; catalyst quality is a target. Data file for the corrupted-implicit pools:
[`2026-10-31-corruption-implicit-pools.json`](2026-10-31-corruption-implicit-pools.json) (generated from repoe-fork 3.29.3.3).

## 1. The answer in one table

| Row | Rule | Chances | Status |
|---|---|---|---|
| M-47 Vaal Orb, equipment | Corrupts, plus exactly one of four outcomes: a corrupted implicit; one white socket turns non-white (3.29.0); the item becomes a rare of the same base with six random affixes and random sockets and links ("brick"); nothing. | 1/4 each, no source shows otherwise. | Rule: wiki + CoE code. Equal weights: wiki citing old GGG/Reddit statements (2014, 2015) and CoE's code. Not re-measured in 3.29. |
| Corrupted implicit pool | One implicit drawn by weight from the mods whose spawn tag (first matching tag of the mod) fits the item class and whose `required_level` is at most the item level; it replaces the item's implicit (one at random if there are several). | Weights 1000, 500, 250 or 200 per mod (tier counted as a mod). 19 to 39 mods per class (section 4). | Datamined (repoe 3.29.3.3), equal to CoE's data for ring, amulet, belt. |
| M-48 Locus of Corruption | Corrupts, plus one of four: two corrupted implicits; every white socket turns non-white (3.29.0); the item becomes an influenced rare with random affixes; the item is destroyed. | 1/4 each. | Wiki. CoE code agrees on the four branches. No Hinekora preview (3.23.0). |
| M-49 Tainted Chaos Orb | On a corrupted rare: reforges it, or removes all mods (fractured mods stay; the item drops to the lowest rarity they allow). | **Unpublished.** | Wiki + item text. No branch weights anywhere. |
| M-50 Tainted Exalted Orb | On a corrupted rare: adds or removes one mod; never changes rarity. | **Unpublished.** | Wiki + item text. |
| M-51 Tainted Divine Teardrop | On a corrupted rare: each mod goes up one tier, down one tier or stays; not below the lowest tier, not above the highest tier the base can have; crafted mods are not touched; ignores metamods. | **Unpublished.** | Wiki (3.16.1 fix). |
| M-53 Tainted Jeweller's, M-54 Tainted Fusing | Add or remove one socket / one link (of the largest group). New sockets are white (3.29.0). Jeweller's cannot reach six sockets under item level 50. | 50% / 50% each. | Wiki citing a community direct test (Prohibited Library, 2024-02, Discord, **not opened**); odds were changed in 3.19.0 and 3.19.1. Sample size unknown. |
| M-55 Tainted Chromatic | Rerolls socket colours ignoring attribute requirements; forces at least one non-white (3.29.0); quality raises the chance of more non-white. | Colour chances unpublished. | Patch notes 3.29.0. B6. |
| M-56 Tainted Armourer's Scrap, Whetstone, Catalyst | Corrupted armour / weapon: random quality, maximum 20%. Corrupted ring, amulet, belt: random catalyst type and amount, maximum 20%, replaces other quality types. Tainted Catalyst drops only from the Ultimatum Trialmaster. | Distribution of amount and type **unpublished**. | Item text (datamined) + wiki. Maxroll's "0 to 29%" is wrong for 3.29 (older). |
| M-57 Bench on corrupted items | Only socket number, socket colour and link crafts, each costing the usual currency **plus the same number of Vaal Orbs**. No mod crafts. | Deterministic. | Wiki (Corrupted, Vaal Orb). |
| Bloodstained Fossil | Item is rerolled by the other fossils as usual, becomes corrupted and gets one corrupted implicit like the Vaal Orb's implicit outcome (not affected by other fossils). | Same pool as the Vaal Orb. | Wiki, since 3.16.0. |

None of the reference routes of #5 uses corruption (the words "Corrupting Fever" and "Vaal soul" in them are a wand name and a removed Runesmith enchant).
The prototype (`archive/prototype:docs/mechanics/corruption.md`) already holds the four-branch shape and flags the 3.29 socket change; this note adds the pools, the Tainted rules and the source comparison.

## 2. Rules with provenance

Source kinds: official / wiki / datamined / experiment / coe / owner. "Read" is the date I read the page; patch is 3.29.3.3 unless said.

### 2.1 Vaal Orb on equipment (M-47)

- **Four equal outcomes** (wiki, read 2026-10-31, https://www.poewiki.net/wiki/Vaal_Orb#Equipment): "Using a Vaal Orb on a piece of equipment will corrupt it and apply one of four possible outcomes. Each outcome has an equal chance of occurring." The wiki cites chris_wilson (Reddit, 2015-07-16; 2014-03-26, GGG staff statements). CoE's simulator does the same: `poec_simCorrupt` draws `poec_rand(0, tbl.length)` over `crsim_vaaltbl = ["white sockets","implicit","brick","nothing"]` (`sources/raw/coe/package.js`, 2026-09-20 copy). Nothing in the 3.29.0 to 3.29.3 notes changes the split. No source gives a large count.
- **3.29.0 change** (official notes as copied by the wiki, https://www.poewiki.net/wiki/Version_3.29.0, Stacey_GGG 2026-07-16, GGG thread 3985332): "The Corruption outcome from Vaal Orbs that changes a Socket on a piece of Equipment to a White Socket has been removed. This outcome instead now turns a random White Socket on the item to be a Non-White Socket." The wiki's Vaal Orb page adds: it "ignores colour weights from attribute requirements" and "may occur even if the item has no sockets, in which case it will have no effect". CoE's table still says "white sockets" (label only; no socket state is simulated), so CoE is out of date on the wording and agrees on the weight. The GGG forum itself (Cloudflare check) could not be opened by me; the wiki copy is what I read, and the earlier session S39 read the forum page on 2026-09-20.
- **Brick** (wiki Vaal Orb): "The item may become a rare item of the same base type, rolling six random affixes (explicit modifiers), and randomizing its sockets and links." "This outcome does respect metamods when rolling affixes. The item will retain all of its other properties, including enchantments, quality, memory strands, base defense values and inventory icon". Six linked sockets after a brick: "1 in 144" (chris_wilson 2014; before the 3.29 socket rework, so stale for colours and probably for counts). Works on normal and magic items as well (the item becomes rare).
- **Implicit replacement** (wiki Corrupted, "Corrupted modifiers replace one (or two with double-corrupted) implicit modifier(s) from an item ... Synthesised items or items with Eldritch implicit modifiers ... will only lose one random implicit modifier"; Vaal Orb: "If the item already has an implicit modifier, it will be replaced ... If it has more than one, one of them will be replaced at random.") CoE's `poec_simRollImplicits` agrees: it replaces random existing implicit slots first and appends the rest.
- **Vaal Orb does not work with Allflame crafting** ("The Vaal Orb is intentionally incompatible with Allflame crafting", wiki Allflame_crafting, citing the 3.29 Q&A). Allflame crafting also refuses corrupted items, Tainted currency, quality and socket currency.
- **Jewels** (wiki Vaal Orb): four equal outcomes: a jewel corrupted implicit; a rare jewel of the same base; a corruption-exclusive unique jewel (only Cobalt, Crimson, Viridian have one, other bases give "no effect"); nothing. A unique result is a failed try (#81). The number of affixes of the rare jewel is not stated (a jewel holds at most 4); CoE rolls "6" capped by the jewel limit, unverified. Corrupted implicit pools: 21 mods with weight above 0 for ordinary jewels (domain `misc`, tag `jewel`) and 21 for abyss jewels, all with weight 1000 (the other 22 and 16 listed mods have weight 0), see section 4.
- **Eligibility**: any uncorrupted equipment, jewellery, quiver, jewel; not corrupted items; unique items are out of scope (#81).

### 2.2 Corrupted implicit pools (datamined)

- repoe-fork 3.29.3.3 `mods.json`: 372 mods have `generation_type: corrupted`, `domain: item` (equipment, jewellery, quivers), 238 of them have a spawn weight above 0 on at least one tag. Every one of them has `generation_weights: []` and a `spawn_weights` list; the first entry whose tag the item has decides the weight (leftmost match), as for any mod.
- Per base item the pool depends only on the item class (checked on every base item in the dump: one pool per class; Warstaff has two, 9 ordinary Warstaves and the 3 experimental "Rod" bases).
- The item level gate is the mod's `required_level`: CoE keeps a corrupted mod only if its tier `ilvl <= item level` (`htilvl<=iLvl` in the pool builder; the corrupted modifiers sit in CoE's group 1, which is not exempt). The wiki says the same in words: "Corrupted modifiers are implicit modifiers from a pool dependent on the item's item category and item level". The highest `required_level` in any class is 85, so an item of level 86 or more sees the whole pool.
- Cross-check with Craft of Exile's data (`poec_data.json`, 2026-09-20 copy): Ring 39 mods, total weight 31,850; Amulet 30 mods, 28,500; Belt 19 mods, 18,500. These equal the repoe numbers exactly, mod by mod for the ring.
- Mods of one family are separate draws, each with its own weight: a ring holds 3 "Added Cold Damage" mods (weights 1000, 1000, 250), so the family has weight 2250 out of 31,850. The three "% increased Dexterity / Strength / Intelligence pair" mods and the "Mana Reservation Efficiency" mods (10 aura mods on rings) are separate mods with weight 1000 each.
- 3.29.0 changed the pool (new implicits, removed ones, new values; list in the wiki Version_3.29.0 "Added the following new Corruption Implicit Modifiers"). The 3.29.3.3 data already contains these. Earlier changes: 3.25.0 removed item-quantity implicits, 3.10.0 made belt attribute implicits mutually exclusive.
- The item's explicit mods do not enter the draw, and the implicit outcome never touches them.

### 2.3 Locus of Corruption (M-48)

- Wiki https://www.poewiki.net/wiki/Locus_of_Corruption (read 2026-10-31): the Corruption Altar in the tier 3 Incursion room (Temple of Atzoatl, Paquate) corrupts one item; "one of four possible outcomes ... Each has an equal chance": two corrupted implicits ("These will replace implicit modifiers already on the item. An item with three or more implicit modifiers will have two of them replaced at random."); "the colour of all of its sockets become non-white" (3.29.0 text: "turns all White Sockets on the item to be Non-White"); "an influenced rare item of the same base type, with random affix modifiers" (respects metamods); destroyed. "The Corruption Altar device cannot be used on an item that is already corrupted." Works on weapons, armour, jewellery, quivers, jewels.
- The brick keeps nothing else stated. CoE sets one random influence of the six (Shaper, Elder, Crusader, Hunter, Redeemer, Warlord, uniform) when the base can be influenced, then rerolls to a rare with 6 affixes.
- Two implicits: CoE draws the second from the pool minus the mods that share a mod group with the first (`modgroups` test in `poec_simRollImplicits`). The wiki does not say. In repoe the shared groups are, for example, the three attribute-pair mods (`IncreasedAttributesCorrupted`) and the ten aura-efficiency mods (`ReducedManaReservationsCost`), plus the three tiers of each Added-damage family. Probability of getting two named mods A and B of different groups: `wA/W * wB/(W - gA) + wB/W * wA/(W - gB)` with `gX` the total weight of X's group (CoE's implementation, not tested in game).
- No Hinekora's Lock preview of the altar (3.23.0). The cost of a Locus use is the temple itself, not a currency; nothing prices it.

### 2.4 Tainted currencies on a corrupted item (M-49 to M-56)

- **Source of the currencies**: "Tainted Currency have a chance to drop from Beyond monsters, and is guaranteed to drop several random Tainted Currency from Beyond bosses" (wiki, each Tainted page). **Tainted Catalyst** and **Tainted Oil** are the exceptions: Catalyst "can be obtained as a boss drop from the Trialmaster in an Ultimatum encounter" (wiki); since 3.29.0 Ultimatum is the only source of catalysts (notes).
- **Tainted Chaos Orb** (wiki + repoe item text): "Unpredictably either reforges a corrupted rare item with new random modifiers or removes all of its modifiers". Removing all: the item becomes Normal and cannot be modified again, except fractured mods stay: one fractured prefix or suffix leaves a magic item; two fractured on one side leaves a rare, "allowing it to be safely rerolled using Tainted Chaos Orbs". The affix-count ratio of the reforge (the ordinary Chaos Orb has 4:5:6 = 8:3:1), whether the reforge keeps fractured mods and respects metamods: not stated.
- **Tainted Exalted Orb**: "Unpredictably adds or removes a modifier on a corrupted rare item"; "It cannot upgrade or downgrade the rarity of an item" (wiki). What happens at 6 mods (add impossible) or at 1 mod (removal would leave a magic item): not stated. Whether the removal respects side locks or fractured mods: not stated. Whether the new mod follows the ordinary pool and weights: not stated (assumed).
- **Tainted Divine Teardrop**: "randomly increases the tier of each mod on an item by 1 tier, decreases it by 1 tier, or does nothing. It cannot decrease a modifier below the lowest tier or increase it past a tier usually obtainable on that base type. It cannot modify crafted modifiers. It ignores metamods." (wiki). Whether "obtainable" means by item level, whether fractured and influence mods move, and the three chances: not stated. 3.16.1 removed crafted mods from its effect.
- **Tainted Jeweller's / Tainted Fusing**: "The chance to add or remove a socket are both 50%" / "a link are both 50%" (wiki; reference: "Confirmed through direct testing by Prohibited Library (community)", a Discord link I did not open). Version history: 3.19.0 "Adjustments have been made to the outcome odds ... in order for these items to be suitable for core availability"; 3.19.1 "Improved the outcome odds". So the 2022 Reddit guess of about 30% to go up (u/SingleInfinity, 2022-10-17) is stale. The wiki also writes: Fusing: reach four links at the bench, then use Tainted Fusing, "average cost of 5 Tainted Orb of Fusing to get a six link, ... 99% chance of success before spending 35" (B6).
- **Tainted Chromatic**: 3.29.0 notes: "Chromatic Orbs and Tainted Chromatic Orbs now force one of the Sockets on the item to be Non-White, while the rest of the Sockets on the item will roll colours normally. Higher Quality on items increases the chance for Non-White Sockets to appear." 3.29.2 fixed the guarantee on items with Abyssal Sockets. 3.29.0 also: "Currency that adds Sockets to items such as Jeweller's Orbs, Tainted Jeweller's Orbs and Orbs of Binding will always generate the added sockets as White. This includes adding sockets through the Crafting Bench."
- **Quality**: item text in repoe 3.29.3.3: Armourer's Scrap and Whetstone "Randomises the quality of a corrupted armour/weapon ... The maximum random quality is 20%."; Tainted Catalyst "Applies a random quality type and amount of quality to a Corrupted ring, amulet or belt. Replaces other quality types ... The maximum quality is 20%." The wiki lists the catalyst types on its Catalyst page; no source gives the weights of the type or the amount (uniform is a guess). Maxroll (2025-02-08) says 0% to 29% for the scrap and the whetstone; the 3.29.3.3 item text says 20%, so Maxroll loses.
- **Not Tainted but relevant**: Tainted Oil (anoint corrupted ring or amulet, B7), Tainted Blessing (removed with the Divine Font enchants, X-18), Tainted Mythic (out, #81), Volatile Vaal Orb (unique equipment only).

### 2.5 Bench on corrupted items (M-57)

- Wiki Corrupted: "You can modify the socket colour, number, and links of a corrupted item using the Crafting Bench at your Hideout. It will cost additional Vaal Orbs equal to the number of currency items the recipe normally requires." Vaal Orb page: "You can still craft sockets and links at a Crafting Bench by using Vaal Orbs in addition to the requirements."
- repoe 3.29.3.3 bench options (765) carry only `actions`, `cost`, `item_classes`, `bench_tier`; the corrupted rule and the extra Vaal Orbs are not in the data, so the planner has to add them. 3.29.0 added bench options "At Least Two / Three / Four Non-White Sockets" costing 5 / 20 / 75 Chromatic Orbs; with the rule above a corrupted item pays the same number of Vaal Orbs on top (my reading, not stated for these three).
- Every mod craft and every other currency is refused on a corrupted item (wiki: "Corrupted items cannot be modified again").

### 2.6 Bloodstained Fossil

- Wiki Bloodstained_Fossil: "A resonator containing a Bloodstained Fossil has the effect of corrupting the item it is used on, adding a corruption implicit modifier ... it will also attempt to add a corrupted implicit modifier similar to the outcome of using a Vaal Orb and receiving a corrupted implicit." The fossil's implicit is "not affected by other fossils". With a Gilded Fossil it "will replace all existing implicit modifiers". 3.16.0: "now Corrupt an Item, granting them a Corrupted Implicit Modifier (previously granted a Vaal Modifier)". Obtained from Stonewood Hollow nodes in Petrified Forest biomes of the Azurite Mine, or from Niko for 1,000,000 Azurite (wiki).
- "Attempt" is the wiki's word: whether it can fail (no implicit) is not stated. #61 left Bloodstained out of scope (OutOfScope in `ApplyFossils`); the remaining modelling choice is whether the implicit is drawn uniformly from the Vaal pool (assumed).

## 3. Where the sources disagree or are old

| Point | Source A | Source B | Verdict |
|---|---|---|---|
| Vaal socket outcome | CoE label "white sockets"; wiki Corrupted intro and the achievement "Corrupt an item to have a white socket" (old text) | 3.29.0 notes | 3.29.0 notes win (turn one white socket non-white). |
| Brick and metamods | Wiki: "does respect metamods"; Reddit "TIL Double corruption respects metamods" (srmark, 2022-04-02), "PREFIXES CANNOT BE CHANGED" video (demi, 2017) | CoE code passes `metaprot = false` and `remfrac = true` to its reroll, which removes fractured mods and protected sides | Unresolved. Wiki is based on player tests; CoE is code. See open point 1. |
| Tainted scrap and whetstone maximum | Maxroll 2025: 0 to 29% | repoe 3.29.3.3 item text and wiki: maximum 20% | Item text wins. |
| Tainted Fusing odds | Reddit 2022: about 30% up | wiki: 50% / 50% since 3.19.0 and 3.19.1 | Wiki wins (newer); sample size unknown. |
| Locus brick | inventory M-48 said "random rare" | wiki, Maxroll, CoE: influenced rare | Influenced rare. |
| Catalyst source | inventory (M-56) said Beyond | wiki: Trialmaster only | Trialmaster, Ultimatum. |

## 4. Corrupted implicit pools per item class (3.29.3.3)

W = total weight, at item level 86 or more. Every mod's weight is 1000, 500, 250 or 200 (see JSON for each mod: id, family group, required level, weight, text).

| Class | Mods | Families | W | Class | Mods | Families | W |
|---|---|---|---|---|---|---|---|
| Ring | 39 | 22 | 31,850 | Amulet | 30 | 28 | 28,500 |
| Belt | 19 | 16 | 18,500 | Body Armour | 21 | 21 | 20,500 |
| Boots | 25 | 22 | 21,500 | Gloves | 28 | 26 | 27,500 |
| Helmet | 29 | 29 | 27,750 | Shield | 27 | 26 | 26,500 |
| Quiver | 25 | 17 | 19,850 | Bow | 27 | 18 | 21,900 |
| Claw | 16 | 10 | 13,750 | Dagger | 20 | 12 | 17,000 |
| Rune Dagger | 27 | 16 | 20,250 | Wand | 24 | 14 | 17,250 |
| Sceptre | 20 | 12 | 14,750 | Staff | 28 | 22 | 24,250 |
| Warstaff | 24 | 15 | 21,000 | One Hand Axe | 12 | 9 | 11,250 |
| One Hand Mace | 11 | 8 | 10,250 | One Hand Sword | 12 | 9 | 11,250 |
| Thrusting 1H Sword | 9 | 9 | 9,000 | Two Hand Axe | 18 | 15 | 17,250 |
| Two Hand Mace | 15 | 12 | 14,250 | Two Hand Sword | 15 | 12 | 13,750 |
| Fishing Rod | 5 | 5 | 5,000 | | | | |

Jewels: 21 mods (W = 21,000, all weight 1000) for ordinary jewels and 21 (W = 21,000) for abyss jewels; four of each need item level 33, 40, 40 or 60. Their lists are in `mods.json`, domains `misc` and `abyss_jewel`; the JSON file holds equipment, jewellery and quivers only.

Worked numbers, ring of level 83 or more: the pool is 31,850 wide. "+14-16% to all Elemental Resistances" has weight 1000: 3.14% of an implicit draw, so 0.78% per Vaal Orb (a quarter of the orbs draw an implicit): about 127 Vaal Orbs per hit on average, and the other outcomes (brick, 1/4) destroy the explicit mods on the way. "+1 to Maximum Frenzy Charges" has weight 200: 0.63% per draw, 0.16% per orb, about 637 orbs. A ring of level 80 loses the three level 81 to 83 Added-damage tiers (3 x 250), so W is 31,100.

## 5. Gaps and measurements (with sample sizes)

Sample sizes are two-sided 95% (z = 1.96). For a split p: n = z² p(1-p) / h² for half-width h.

| # | Unknown | What to do in game | Sample needed |
|---|---|---|---|
| 1 | Does a Vaal brick keep fractured mods, and the sides locked by "Prefixes / Suffixes cannot be changed"? (wiki says metamods respected, CoE says no) | Corrupt items that carry one fractured prefix, a "Suffixes cannot be changed" metamod and some suffix mods. Each brick shows both answers at once. | 1 observed brick settles it (each brick is deterministic). 11 Vaal Orbs on 11 prepared items give a 95.8% chance to see at least one brick (0.75^11 = 4.2%). |
| 2 | Are the four Vaal outcomes still equal in 3.29? | Vaal Orbs on items with 4 white sockets (so socket and nothing are told apart). | ±5 points per outcome: 289 orbs. ±3 points: 801. To tell 25% from 20% with 80% power: 563. |
| 3 | Tainted Chaos: share of "remove all" and the reforge's affix count | Corrupted rares with two fractured affixes on one side (they never fall to Normal); count removal vs reforge. | ±5 points on the 50/50 guess: 385 orbs. 194 orbs tell 50% from 40% with 80% power. If the item is not protected, each removal ends the item: roughly half of the orbs need a fresh item. |
| 4 | Tainted Exalted: share of add vs remove, and behaviour at 6 mods and at 1 mod | One corrupted rare kept at 3 or 4 mods; also runs at 6 mods and at 1 mod. | ±5 points: 385 orbs at 3 to 4 mods; 30 orbs each at 6 mods and at 1 mod show the edge rule. |
| 5 | Teardrop up / down / same per mod | Corrupted rare with six mods in the middle tiers (so no boundary), count each mod separately. | About 350 mod-draws for ±5 points on one third (z² (1/3)(2/3) / 0.05² = 342). Mods drift to the ends, so about 100 orbs on 6-mod items rather than 58. |
| 6 | Tainted Catalyst type and amount; scrap and whetstone amount | Use on corrupted jewellery / armour / weapons, record type and quality. | Amount (shape unknown; if uniform from 1 to 20, a 5-point band is 1/4): 450 uses for ±4 points per band. Type (about 10 types, so 1/10 each if equal): 385 uses for ±3 points. Prices unknown. |
| 7 | Tainted Jeweller's / Fusing 50% | Re-test with the same rule as in #4 (a corrupted socketed item). | ±5 points: 385 orbs each. The wiki's own sample size is unknown. B6 may defer this. |
| 8 | Locus (four equal outcomes; the influenced rare; the destroyed share) | Needs an Incursion temple and one item per try. | ±5 points: 289 tries. Not practical; accept the wiki. |

Free of any test: the corrupted implicit pools (datamined and equal in two sources), the 3.29.0 socket rule, the bench rule, the Bloodstained rule.

## 6. What this means for B4 (facts for the grill, no decision)

- Corruption is a last step. A corrupted item takes no ordinary currency; the only later actions are the Tainted ones and the three bench socket crafts. The planner needs a `corrupted` flag on the item (exists: a fossil refusal already reads it) and a rule that every non-Tainted, non-socket-bench action is `NotApplicable` on a corrupted item.
- The Vaal Orb as an action has four branches of 1/4. The implicit branch is a weighted draw from the class pool (section 4), filtered by item level, that **replaces** the base implicit. A target that wants a specific corrupted implicit needs its own requirement kind; one that does not care sees three of the four branches as "item unchanged" (implicit, socket, nothing) and the fourth as a loss of every explicit mod. The brick can also be used as a terminal reroll of a corrupted rare, but it produces a rare with six random mods and no way to roll again except by the Tainted currencies.
- The Locus is the same plus a 1/4 destruction branch and two implicits (distinct groups by CoE). It needs a per-use price from the user; none exists in any source.
- The unpublished Tainted odds block exact planning for Tainted Chaos, Exalted and Teardrop. The planner can offer them with a flagged assumption (50/50 for the two-branch ones, 1/3 each for the Teardrop) only if the owner accepts a result marked as unverified; otherwise they stay out until measured.
- Quality as a target (#81) does not need Tainted Catalyst: an ordinary catalyst applied before the Vaal Orb keeps its quality through a corruption according to the wiki ("The item will retain all of its other properties, including ... quality") on the brick branch; the other three branches do not touch quality. Not tested for catalyst quality types.

## 7. Questions for the owner (each with my recommendation)

1. **Can a corrupted implicit be part of a target** (for example a ring with "+1 to maximum Frenzy Charges" or "all elemental resistances" as the implicit)? It decides whether B4 plans around the pool tables above or only around the Tainted tools. *Recommendation: yes.* It is the main reason players corrupt; the data is complete and free of unknowns.
2. **How should the planner treat the three Tainted currencies whose odds nobody published (Chaos, Exalted, Teardrop)?** (a) leave them out until someone measures them (section 5, rows 3 to 5, 385 / 385 / about 100 orbs each); (b) offer them with a "50/50 assumed, not verified" warning on the result. *Recommendation: (a) for B4's first release, (b) not at all;* a route that rests on an invented split would look exact and not be. Tainted Jeweller's and Fusing (50/50, community-tested) can go in with their source shown, in B6.
3. **Do you want the Locus of Corruption in the plans?** It needs an Incursion temple with a tier 3 Corruption room and has no currency price. *Recommendation: include it as an optional action with a price per use that you enter yourself (default: not available).* The 1/4 destruction chance is then shown as a risk.
4. **A fact only you may know, or a test of 11 Vaal Orbs:** when a Vaal Orb "bricks" an item that has a fractured mod, does the fractured mod stay? And does a "Prefixes cannot be changed" metamod keep the prefixes? *Recommendation: say what you remember; if unsure, I treat both as "unknown" and the planner refuses to corrupt fractured or metamod items with a warning (nothing guessed).* The test is in section 5, row 1.
5. **Quality from catalysts:** is it enough that the plan puts the ordinary catalyst on before the Vaal Orb, with the Tainted Catalyst, Armourer's Scrap and Whetstone left out? Their amount and type are random and unpublished. *Recommendation: yes, leave them out.*

## 8. Draft claims for `src/crafting_system/rules/claims/` (files `corruption.yaml`, `tainted.yaml`)

```yaml
# corruption.yaml
rules:
  - id: corruption.vaal_equipment_four_outcomes
    statement: A Vaal Orb on equipment corrupts it and applies exactly one of four outcomes with equal chance: a corrupted implicit, one white socket turns non-white, a reroll into a rare of the same base with six random affixes and random sockets and links, nothing. The 1/4 split rests on old GGG statements and on Craft of Exile's code; no 3.29 count exists.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Vaal_Orb#Equipment
    quote: "Using a Vaal Orb on a piece of equipment will corrupt it and apply one of four possible outcomes. Each outcome has an equal chance of occurring."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
    value: {implicit: 0.25, socket_colour: 0.25, brick: 0.25, nothing: 0.25}

  - id: corruption.vaal_equal_in_coe_code
    statement: Craft of Exile draws the Vaal Orb's outcome uniformly from four entries; its socket entry is a label only.
    source_kind: coe
    url: https://www.craftofexile.com/
    quote: "crsim_vaaltbl=[\"white sockets\",\"implicit\",\"brick\",\"nothing\"]; var rolled=poec_rand(0,tbl.length,!0)"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: corruption.vaal_socket_outcome_3_29
    statement: Since 3.29.0 the socket outcome of the Vaal Orb turns one random white socket non-white (ignoring attribute colour weights); with no white socket, or no socket, it changes nothing. It no longer makes a socket white.
    source_kind: official
    url: https://www.pathofexile.com/forum/view-thread/3985332
    quote: "This outcome instead now turns a random White Socket on the item to be a Non-White Socket."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
    note: read through the wiki's copy https://www.poewiki.net/wiki/Version_3.29.0 (Cloudflare blocked the forum page)

  - id: corruption.vaal_brick_rare_six_mods
    statement: The brick outcome makes the item a rare of the same base with six random affixes, randomises sockets and links, respects metamods when rolling, and keeps quality, enchantments, memory strands and base values. Whether fractured mods and metamod-locked sides survive is unresolved (the wiki says metamods respected, Craft of Exile removes fractured mods and protection).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Vaal_Orb#Equipment
    quote: "This outcome does respect metamods when rolling affixes. The item will retain all of its other properties, including enchantments, quality, memory strands"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
    value: {affixes: 6}

  - id: corruption.implicit_replaces_existing
    statement: A corrupted implicit replaces the item's existing implicit; if the item has several, one is replaced at random (double corruption: two). Explicit mods are not touched.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Corrupted#Mechanics
    quote: "Synthesised items or items with Eldritch implicit modifiers can also have more than one implicit modifier, and will only lose one random implicit modifier if corrupted via a Vaal Orb."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: corruption.implicit_pool_by_item_class
    statement: The corrupted implicit is drawn by weight from the mods with generation_type corrupted whose first matching spawn tag gives a weight above 0 and whose required_level is at most the item level. The pool depends only on the item class; per-class pools are in docs/research/2026-10-31-corruption-implicit-pools.json.
    source_kind: datamined
    url: https://github.com/lvlvllvlvllvlvl/RePoE
    quote: "372 mods with generation_type corrupted and domain item; spawn_weights e.g. {ring: 250, default: 0} for V2AddedColdDamageCorrupted3 (required_level 81)"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: corruption.implicit_pool_matches_coe
    statement: Craft of Exile's corrupted pools equal the repoe pools for ring (39 mods, weight 31850), amulet (30, 28500) and belt (19, 18500); CoE keeps a corrupted tier only if its ilvl is at most the item level.
    source_kind: coe
    url: https://www.craftofexile.com/
    quote: "htilvl<=iLvl||mod.id_mgroup==11||mod.id_mgroup==13||mod.id_mgroup==10; corrupted modifiers have id_mgroup 1"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: corruption.locus_four_outcomes
    statement: The Locus of Corruption's altar corrupts an uncorrupted item and applies one of four equal outcomes: two corrupted implicits, every white socket turns non-white (3.29.0), the item becomes an influenced rare with random affixes (respecting metamods), the item is destroyed.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Locus_of_Corruption
    quote: "In addition to corrupting the item, one of four possible outcomes will be applied to it. Each has an equal chance of occurring."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
    value: {two_implicits: 0.25, sockets_non_white: 0.25, influenced_rare: 0.25, destroyed: 0.25}

  - id: corruption.locus_second_implicit_other_group
    statement: In Craft of Exile's code the second implicit of a double corruption is drawn from the pool without the mods that share a mod group with the first. The wiki does not say.
    source_kind: coe
    url: https://www.craftofexile.com/
    quote: "if(m>0){var nmodpool=[]; ... for(var zy=0;zy<vmp[i].modgroups.length;zy++){...if(vmp[i].modgroups[zy]==affix.modgroups[zw]){mconflict=!0}"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: corruption.locus_no_preview
    statement: Hinekora's Lock cannot foresee the result of corrupting an item at the altar.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Locus_of_Corruption#Version_history
    quote: "Hinekora's Lock can no longer foresee the result of corrupting an item at the Altar of Corruption."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: corruption.corrupted_blocks_currency_except
    statement: A corrupted item takes no ordinary currency or mod craft. The exceptions are Tainted currency, Tainted Oil and Tainted Catalyst, and bench crafts of socket number, socket colour and links, each costing the usual currency plus the same number of Vaal Orbs.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Corrupted#Mechanics
    quote: "It will cost additional Vaal Orbs equal to the number of currency items the recipe normally requires."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: corruption.bloodstained_fossil_implicit
    statement: A resonator with a Bloodstained Fossil corrupts the item and adds a corrupted implicit like the Vaal Orb's implicit outcome; other fossils do not change that implicit.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Bloodstained_Fossil
    quote: "it will also attempt to add a corrupted implicit modifier similar to the outcome of using a Vaal Orb and receiving a corrupted implicit"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
```

```yaml
# tainted.yaml
rules:
  - id: tainted.chaos_reforge_or_clear
    statement: A Tainted Chaos Orb on a corrupted rare either reforges it or removes all its mods (fractured mods stay; the item takes the lowest rarity they allow). The branch chances are not published.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Tainted_Chaos_Orb
    quote: "fractured mods will not be removed, leaving the item at the lowest eligible rarity"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: tainted.exalted_add_or_remove
    statement: A Tainted Exalted Orb on a corrupted rare adds or removes one mod and never changes the rarity. The branch chances are not published.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Tainted_Exalted_Orb
    quote: "Tainted Exalted Orb is a currency item that unpredictably adds or removes a modifier on a corrupted item. It cannot upgrade or downgrade the rarity of an item."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: tainted.divine_teardrop_tier_step
    statement: A Tainted Divine Teardrop moves each mod's tier by +1, -1 or 0 within the tiers the base can have; it skips crafted mods and ignores metamods. The chances are not published.
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Tainted_Divine_Teardrop
    quote: "randomly increases the tier of each mod on an item by 1 tier, decreases it by 1 tier, or does nothing"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: tainted.jeweller_fusing_even
    statement: Tainted Jeweller's and Tainted Fusing add or remove one socket or link with 50% each (community test; the odds were changed in 3.19.0 and 3.19.1). Sockets added are white since 3.29.0.
    source_kind: experiment
    url: https://www.poewiki.net/wiki/Tainted_Orb_of_Fusing
    quote: "The chance to add or remove a link are both 50%."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
    value: {add: 0.5, remove: 0.5}

  - id: tainted.chromatic_forces_non_white
    statement: Tainted Chromatic Orbs ignore attribute requirements and force at least one non-white socket; quality raises the chance of more.
    source_kind: official
    url: https://www.pathofexile.com/forum/view-thread/3985332
    quote: "Chromatic Orbs and Tainted Chromatic Orbs now force one of the Sockets on the item to be Non-White"
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
    note: read through https://www.poewiki.net/wiki/Version_3.29.0

  - id: tainted.quality_orbs_random_max_20
    statement: Tainted Armourer's Scrap and Blacksmith's Whetstone set a random quality up to 20% on a corrupted armour or weapon; Tainted Catalyst sets a random catalyst type and amount up to 20% on a corrupted ring, amulet or belt and replaces other quality types. The distributions are not published. Tainted Catalyst drops only from the Ultimatum Trialmaster.
    source_kind: datamined
    url: https://github.com/lvlvllvlvllvlvl/RePoE
    quote: "Randomises the quality of a corrupted armour ... The maximum random quality is 20%."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31

  - id: tainted.source_beyond
    statement: Tainted currency drops from Beyond monsters and bosses; Tainted Catalyst is the exception (Ultimatum Trialmaster).
    source_kind: wiki
    url: https://www.poewiki.net/wiki/Tainted_Chaos_Orb#Item_acquisition
    quote: "Tainted Currency have a chance to drop from Beyond monsters, and is guaranteed to drop several random Tainted Currency from Beyond bosses."
    patch_verified: "3.29.3.3"
    date_checked: 2026-10-31
```

## 9. Open points

1. Fractured mods and metamod-locked sides through a Vaal brick (wiki vs CoE): one observed brick settles it (section 5 row 1).
2. Branch chances of Tainted Chaos, Exalted, Teardrop; edge rules of Tainted Exalted (6 mods, 1 mod) and Teardrop (does "obtainable" use the item level; fractured and influence mods).
3. Distribution of Tainted Catalyst type and amount, and of the two quality scraps.
4. Number of affixes of a Vaal-bricked rare jewel (a jewel holds at most 4).
5. 3.29 socket maths of the brick (number and links; the "1 in 144" is from 2014) and of Tainted Chromatic: B6.
6. Whether Bloodstained's implicit can fail, and whether it uses the Vaal pool uniformly (assumed).
7. Whether the three new 3.29.0 bench options cost extra Vaal Orbs on a corrupted item (assumed by the general rule).
8. Allflame crafting (3.29.0): Merrick's Ducat is said by the wiki to craft a rare Abyss jewel to an extra explicit mod and corrupt it; this is a separate mechanic outside #92 and probably belongs in a row of its own (jewels are in scope).
9. Hinekora's Lock on a Vaal Orb use of an uncorrupted item: belongs to the Lock's own ticket.

## 10. How this was gathered, and what failed

- Wiki pages read in the built-in browser pane, 2026-10-31: Vaal_Orb, Locus_of_Corruption, Corrupted, Bloodstained_Fossil, Allflame_crafting, the five Tainted Orb pages, Tainted Armourer's Scrap, Whetstone, Catalyst, Version_3.29.0 / 3.29.1 / 3.29.2 / 3.29.3. PoEDB Tainted Chaos Orb (no odds). Maxroll "Corruption Explained" (2025-02-08).
- repoe-fork 3.29.3.3 (`.claude/scratch/real-cache/repoe-fork/3.29.3.3`): `mods.json`, `base_items.json`, `crafting_bench_options.json`. Craft of Exile copy of 2026-09-20 in `sources/raw/coe/`.
- **Not done**: the GGG forum page of the 3.29.0 notes sits behind a Cloudflare check I did not pass; the Discord posts cited by the wiki were not opened. **Reddit**: four runs of `gpt-research` (terra, luna) all failed (timed out or the worker died), so no Reddit count backs any Tainted chance; `WebSearch` cannot reach reddit.com. The old Reddit references are quoted from the wiki's own reference list, not re-read.
