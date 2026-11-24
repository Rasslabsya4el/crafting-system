# PoE2 crafting currency and omens: exact mechanics

- **Date checked:** 2026-11-24.
- **Patch:** Path of Exile 2 0.5.x. The game data is 0.5.5.10 (the repoe-fork export). The live leagues are "Runes of Aldur" (0.5.0, 2026-05-29) and "Forbidden Rites" (0.5.5 event league, 2026-09-04).
- **Scope:** every entry of the trade API groups `Currency` and `Vaal`, and every Omen in the game data. Essences, runes, soul cores other than the Theses, abyss bones and the catalyst list are covered by another note. Catalysts appear here only for how quality works and for the Omen of Catalysing Exaltation.

## Sources and their freshness

| Id | Source | What it gave | Freshness |
|---|---|---|---|
| S1 | repoe-fork PoE2 export, `https://repoe-fork.github.io/poe2/base_items.json` (page title "RePoE - PoE2 version 0.5.5.10") | Metadata ids, in-game description and directions text, drop level, stack size | 0.5.5.10, fetched 2026-11-24 |
| S2 | Official trade API `api/trade2/data/static`. The copy was read by the coordinator on 2026-11-24 and is saved in this session's scratchpad. | Which items are currently tradeable: 40 entries in `Currency`, 68 in `Vaal`, 40 Omens in `Ritual` | 2026-11-24 |
| S3 | poe2db.tw: `/us/Currency`, `/us/Omen`, `/us/Catalysts`, `/us/Quality`, `/us/Sanctified_Items`, `/us/Fate_of_the_Vaal`, and item pages (Vaal_Orb, Orb_of_Chance, Fracturing_Orb, Hinekoras_Lock, Architects_Orb, Artificers_Orb, Greater_Exalted_Orb, Omen_of_Recombination, Omen_of_Homogenising_Exaltation, Armourers_Scrap) | Effect text, minimum modifier levels, metadata ids, Sanctify range, Thesis effects | Live site with a "Runes of Aldur v0.5" banner. No per-item patch is shown. Fetched 2026-11-24. |
| S4 | Craft of Exile (CoE) beta, PoE2 emulator: `beta.craftofexile.com/json/poe2/0.5.5.5/data.json` and `packages/files/package_poe2.js?v=1795533925` | The emulator's rules: preconditions per method, min-level filter, omen logic, Vaal outcome lists, quality formula, Catalysing weight formula | CoE data labelled 0.5.5.5, fetched 2026-11-24. CoE is a community model, not game code. |
| S5 | Official patch notes 0.3.0 "The Third Edict", `pathofexile.com/forum/view-thread/3826682` | Greater/Perfect orbs added, 15 omens added, 5 omens retired, Hinekora's Lock added, 20% quality-currency cap | 2025-08-29 |
| S6 | Official patch notes 0.4.0 "The Last of the Druids", `pathofexile.com/forum/view-thread/3883495` | Homogenising omens disabled from dropping | 2025-12-12 |
| S7 | Official patch notes 0.5.0 "Return of the Ancients", `pathofexile.com/forum/view-thread/3932540` (also mirrored at kami-labs.fr) | Greater Transmutation/Augmentation 55→44, Sanctify and corruption multiply, Omen of Corruption retired, Recombination removed, Chaotic omens inverted, Infuser changes, Jeweller's on skill items, Chance on Tablets | 2026-05-22 notes with updates to 2026-05-26 |
| S8 | 0.5.5 / Forbidden Rites: announcement `pathofexile.com/forum/view-thread/3999865` and summary `patched.gg/.../path-of-exile-2-forbidden-rites-patch-notes-and-item-filter-information` | No crafting-currency or omen changes found | 2026-09 |
| S9 | Forum thread `pathofexile.com/forum/view-thread/3863566` (players, no staff reply) | The minimum-level exception: the highest tier of a mod stays eligible | 2025-10-03 (0.3.1) |
| S10 | Maxroll "Corruption Outcomes", `maxroll.gg/poe2/resources/corruption-outcomes` | Vaal outcome lists per item type, Architect's Orb, Crystallised Corruption, Ancient Infuser, Infuser | Updated 2026-05-24 |

Sites that refused:

- **www.poe2wiki.net:** every page returned "Access Denied" (Anubis bot protection). It was not bypassed. Wiki wording reaches this note only through search snippets and is marked as such.
- **mobalytics.gg:** HTTP 403. Not bypassed.
- **www.craftofexile.com (the main site):** served an empty shell, so the beta's JSON and JS were read instead (S4).

Confidence used below:

- **high:** in-game text (S1 or S3) or official patch notes say it.
- **medium:** one community model (S4) or guide (S10) says it and nothing contradicts it.
- **low:** sources disagree, or the fact is inferred.

## General rules (apply to every table)

1. **Affix limits** (S1 directions text, S4).
   - A Magic item has at most 2 explicit modifiers: 1 prefix and 1 suffix.
   - A Rare item has at most 6: 3 prefixes and 3 suffixes.
   - Jewels and some bases have their own limits, which are not covered here.
   - Confidence: high.
2. **Minimum Modifier Level** of Greater and Perfect orbs (S3, S4, S9).
   - The orb only adds a tier whose level requirement is at least N.
   - Exception: for each mod family, the highest tier the item level allows always stays eligible, even when its level is below N. The wiki's phrasing, from a search snippet: "at least one tier of each mod will always be eligible to roll, respecting item level". Example from S9: a Perfect Exalted Orb (N=50) added Energy Shield Recharge whose top tier is level 48.
   - The rule is per mod family, not per tag group.
   - Item level still caps everything: a tier above the item level never rolls.
   - CoE code (S4): a tier is excluded when `tier.minlvl < N` and it is not the highest tier with `minlvl ≤ ilvl`.
   - Confidence: high for N. Medium for the exception: game text does not show it, S9 is a player thread, and CoE implements it.
3. **Item level.** Every added mod must have a tier level ≤ item level. Greater and Perfect orbs do not raise that cap (S4). Confidence: high.
4. **Weights.** Each candidate is picked by its spawn weight among all eligible tiers. An omen that restricts the side (prefix or suffix) or the type filters this pool; it does not reweight it. The exception is Catalysing Exaltation, which reweights. Source: S4. Confidence: medium.
5. **Fractured mods** are never removed by Annulment, Chaos or Whittling (S4 `getRemovableModifiers` skips `fractured`). Confidence: medium. That fractured mods are locked is high (in-game Fracturing Orb text).
6. **Corrupted and Sanctified items** cannot be modified by the ordinary orbs (S1 Vaal directions "Corrupted items cannot be modified again"; S3 Sanctified). The Vaal-group ("Temple") currencies below are the exception for corrupted items. Confidence: high.
7. **Omen use** (S1 omen directions; S5).
   - An omen is right-clicked to make it active in the inventory. It is consumed when its trigger fires.
   - Omens stack to 10 since 0.3.0.
   - Several omens can be active at once.
   - CoE treats these pairs as mutually exclusive (S4 `omenIncompatibilities`): Sinistral/Dextral of the same currency; Erasure pairs; Necromancy pairs; Crystallisation pairs; the three lich omens.
   - Up to 3 Chaotic waystone omens may be used at once (S7).
   - Confidence: high for activation and stacking, medium for the exclusivity pairs.
8. **Cost unit.** Every item below is used one at a time, so the cost of one use is the item's market price. A Shard is 1/10 of an orb: a stack of 10 becomes one orb (S1).

## 1. Basic orbs (no tiers)

| Name | Metadata id | Effect | Preconditions | Numbers | Source | Patch | Conf. |
|---|---|---|---|---|---|---|---|
| Scroll of Wisdom | `Metadata/Items/Currency/CurrencyIdentification` | "Identifies an item" | Unidentified item | Stack 40 | S1 | 0.5.5.10 | high |
| Orb of Alchemy | `Metadata/Items/Currency/CurrencyUpgradeToRare` | "Upgrades a Normal or Magic item to a Rare item with 4 random modifiers". Current modifiers are not retained (directions text, truncated in S1). | Normal or Magic, a base that can be Rare (S4 `can_be_rare`) | Exactly 4 mods, sides random within 3/3. With Sinistral/Dextral Alchemy (retired omens): the maximum on that side (3), the rest on the other. | S1, S4 | 0.5.5.10 | high (count), medium (side split) |
| Orb of Chance | `Metadata/Items/Currency/CurrencyUpgradeRandomly` | "Unpredictably either upgrades a Normal item to Unique rarity or destroys it" | Normal item. Since 0.5.0 also Tablets (S7). | **Odds not published.** They depend on the relative rarity of the uniques of that base. 0.3.0: "more likely to succeed on Amulets, Rings, Belts and Charms" (S5). With Omen of Chance it is not destroyed. With Omen of the Ancients it becomes a random unique of the same class. Stack 10. | S1, S3, S5, S7 | 0.5.0 | high (text), low (odds) |
| Orb of Annulment | `Metadata/Items/Currency/CurrencyRemoveMod` | "Removes a random modifier from an item" | Magic or Rare with ≥1 removable explicit mod (S1 directions, S4) | 1 mod, uniform over removable explicit mods. Fractured mods are excluded. Omens: Sinistral/Dextral (side), Greater (2 mods, retired), Light (Desecrated only). | S1, S4 | 0.5.5.10 | high (text), medium (uniform, fractured excluded) |
| Divine Orb | `Metadata/Items/Currency/CurrencyModValues` | "Randomises the numeric values of modifiers on an item" | An item with modifiers. CoE: rarity not Normal. Used on uniques to update to new ranges (patch notes). | Rerolls each value within its tier range. With Omen of the Blessed: implicits only. With Omen of Sanctification on a Rare: Sanctify (×0.78–1.22, see Omens). Stack 10. | S1, S4, S6, S7 | 0.5.5.10 | high |
| Vaal Orb | `Metadata/Items/Currency/CurrencyCorrupt` | "Modifies an item unpredictably and Corrupts it". "Corrupted items cannot be modified again." | Not corrupted. A corruptable base. | Outcomes per item type are listed after this table. 125 corruption mods are listed on S3. Stack 20. | S1, S3, S4, S10 | 0.5.0 | see below |
| Fracturing Orb | `Metadata/Items/Currency/CurrencyFractureRare` | "Fracture a random modifier on a rare item with at least 4 modifiers, locking it in place." "Cannot be used on Fractured items." | Rare. ≥4 explicit mods. Not already fractured. CoE: not a strongbox, and Unrevealed (Desecrated, unrevealed) mods are excluded from the pick. | 1 mod, uniform over explicit mods (S4). 0.5.0: Fracturing Orbs now need an Atlas Passive specialisation to be found (S7). Stack 20. | S1, S3, S4, S7 | 0.5.0 | high (text), medium (uniform, unrevealed excluded) |
| Mirror of Kalandra | `Metadata/Items/Currency/CurrencyDuplicate` | "Creates a Mirrored copy of an item". "Mirrored copies cannot be modified." | An equippable non-unique item (S1 directions) | Stack 10 | S1 | 0.5.5.10 | high |
| Hinekora's Lock | `Metadata/Items/Currency/CurrencyHinekorasLock` | "Allows an item to foresee the result of the next Currency item used on it". "Modifying the item in any way removes the ability to foresee". | Any item ("left click an item") | Added 0.3.0 (S5). Stack 10. How the preview is shown and whether a locked item can be traded are not documented. | S1, S5 | 0.5.5.10 | high (text) |
| Artificer's Orb | `Metadata/Items/Currency/CurrencyAddEquipmentSocket` | "Adds an Augment Socket to a Martial Weapon, wand, staff or Armour" | Item below its socket maximum (S4 `not_maximum_sockets`) | Max sockets per base (S4 data): **2** for body armours, two-hand weapons, bows, crossbows, quarterstaves, staves, talismans and Grasping Mail. **1** for helmets, gloves, boots, shields, bucklers, foci, one-hand weapons, spears, wands and sceptres. **0** for jewellery, quivers and flasks. Vaal Orb's socket outcome can exceed it by 1. Stack 20. | S1, S4 | 0.5.5.10 | high (text), medium (maxima) |
| Lesser Jeweller's Orb | `Metadata/Items/Currency/CurrencyAddSkillGemSocket3` | "Sets a Skill Gem to have 3 Support Gem Sockets" | Skill gem with fewer than 3. Since 0.5.0 also items with granted skills (S7). | Stack 20, drop level 25 | S1, S7 | 0.5.0 | high |
| Greater Jeweller's Orb | `Metadata/Items/Currency/CurrencyAddSkillGemSocket4` | "Sets a Skill Gem to have 4 Support Gem Sockets" | Fewer than 4 | Drop level 45 | S1 | 0.5.5.10 | high |
| Perfect Jeweller's Orb | `Metadata/Items/Currency/CurrencyAddSkillGemSocket5` | "Sets a Skill Gem to have 5 Support Gem Sockets" | Fewer than 5 | Drop level 65 | S1 | 0.5.5.10 | high |
| Transmutation Shard | `Metadata/Items/Currency/CurrencyUpgradeToMagicShard` | 10 shards become an Orb of Transmutation | – | 1/10 orb | S1 | 0.5.5.10 | high |
| Chance Shard | `Metadata/Items/Currency/CurrencyUpgradeRandomlyShard` | 10 shards become an Orb of Chance | – | 1/10 | S1 | 0.5.5.10 | high |
| Regal Shard | `Metadata/Items/Currency/CurrencyUpgradeMagicToRareShard` | 10 shards become a Regal Orb | – | 1/10 | S1 | 0.5.5.10 | high |
| Artificer's Shard | `Metadata/Items/Currency/CurrencyAddEquipmentSocketShard` | 10 shards become an Artificer's Orb | – | 1/10 | S1 | 0.5.5.10 | high |

Other shards are in the game data but **not** on the trade list (S2): Alteration, Alchemy, Annulment (20), Binding, Horizon, Harbinger's, Engineer's, Ancient, Chaos (20), Mirror (20), Exalted (20), Fracturing (20). These are legacy or unused.

**Removed currencies.** Orb of Alteration (`CurrencyRerollMagic`) and Orb of Scouring (`CurrencyConvertToNormal`) are still in the data files, but poe2db lists them as removed and they are absent from S2. Orb of Regret and Chromatic Orb are also removed (S3). **PoE2 has no Scouring and no Alteration.** The "Orb of Extraction" here is the Vaal socket-recovery item (§5), not a mod remover.

### Vaal Orb outcomes (S4 lists, S10 descriptions; each list is drawn uniformly in CoE)

| Item type | Outcomes | Odds | Conf. |
|---|---|---|---|
| Equipment: Normal, Magic or Rare armour, weapons, jewellery | (1) no change; (2) 1–3 explicit mods removed and re-added (reroll); (3) add a Corruption enchantment; (4) +1 socket ignoring the limit. Wands and staves get quality up to 23% instead of the socket, per S10. S10 also says caster weapons, amulets, belts and rings cannot get sockets. | 25% each in CoE. S10: "equally likely". | medium |
| Unique equipment | no change; values ×0.78–1.22 of the current roll; add a Corruption enchantment; socket or quality as above | 25% each (u4n guide; CoE does not separate uniques) | low–medium |
| Jewels, Rare or Magic | no change; 1–3 mods rerolled; add an enchantment; add or remove an affix ignoring limits (S10). CoE has a different list: [no change, add corrupted mod, ×0.78–1.23 values, no change]. | not published | low (sources differ) |
| Unique jewels | no change 50%; add an enchantment; ×0.78–1.22 explicit values (S10) | 50/25/25 | medium |
| Waystones | no change; tier +1 or −1 (between 1 and 16); turn all affixes into one side (CoE: suffixes become prefixes); add up to 4 random affixes, up to 8 in total (4 prefixes and 4 suffixes) | 25% each (CoE) | medium |
| Tablets (Vaal Orb or Ancient Infuser) | add a random modifier past the limit; +10 uses; turn into a random tablet type with the same mod count; destroy | 25% each (CoE) | medium |
| Skill gems | no change; ±1 level; ±1 socket; quality −7% to +3% | not published | medium (S10) |
| Flasks and charms | quality changes by −10 to +10, capped at 23% (CoE) | – | low |

- **0.5.0** (S7): the outcome that pushes values beyond their range "multiplies each modifier from its current value rather than re-rolling it". Confidence: high.
- **Omen of Corruption** removes the "no change" outcome (S1 text "will always result in change"). It can no longer be obtained since 0.5.0 (S7).

## 2. Tiered orbs (Normal, Greater, Perfect)

| Name | Metadata id | Effect (identical across tiers) | Preconditions | Minimum Modifier Level | Source | Patch | Conf. |
|---|---|---|---|---|---|---|---|
| Orb of Transmutation | `…/CurrencyUpgradeToMagic` | "Upgrades a Normal item to a Magic item with 1 modifier" | Normal item | none (only ilvl) | S1, S3, S4 | 0.5.5.10 | high |
| Greater Orb of Transmutation | `…/CurrencyUpgradeToMagic2` | same | same | **44** (55 before 0.5.0). Drops from Act 4. Drop level 46. | S3, S4, S7 | 0.5.0 | high |
| Perfect Orb of Transmutation | `…/CurrencyUpgradeToMagic3` | same | same | **70**. Drop level 72. | S3, S4 | 0.5.5.10 | high |
| Orb of Augmentation | `…/CurrencyAddModToMagic` | "Augments a Magic item with a new random modifier" | Magic with an open affix (fewer than 2 mods). The new mod goes to the open side. | none | S1, S4 | 0.5.5.10 | high |
| Greater Orb of Augmentation | `…/CurrencyAddModToMagic2` | same | same | **44** (55 before 0.5.0) | S3, S4, S7 | 0.5.0 | high |
| Perfect Orb of Augmentation | `…/CurrencyAddModToMagic3` | same | same | **70** | S3, S4 | 0.5.5.10 | high |
| Regal Orb | `…/CurrencyUpgradeMagicToRare` | "Upgrades a Magic item to a Rare item, adding 1 modifier". Current mods are retained. | Magic, a base that can be Rare | none | S1, S4 | 0.5.5.10 | high |
| Greater Regal Orb | `…/CurrencyUpgradeMagicToRare2` | same | same | **35** | S3, S4 | 0.5.5.10 | high |
| Perfect Regal Orb | `…/CurrencyUpgradeMagicToRare3` | same | same | **50** | S3, S4 | 0.5.5.10 | high |
| Exalted Orb | `…/CurrencyAddModToRare` | "Augments a Rare item with a new random modifier". "Rare items can have up to six random modifiers." | Rare, at least one open affix | none | S1, S4 | 0.5.5.10 | high |
| Greater Exalted Orb | `…/CurrencyAddModToRare2` | same | same | **35**. Drop level 72. | S3, S4 | 0.5.5.10 | high |
| Perfect Exalted Orb | `…/CurrencyAddModToRare3` | same | same | **50**. Drop level 79. | S3, S4, S9 | 0.5.5.10 | high |
| Chaos Orb | `…/CurrencyRerollRare` | "Removes a random modifier and augments a Rare item with a new random modifier" | Rare, at least 1 removable mod | none. Removal is uniform over non-fractured explicit mods. The added mod may land on either side that has room (S4). | S1, S4 | 0.5.5.10 | high (text), medium (sides) |
| Greater Chaos Orb | `…/CurrencyRerollRare2` | same | same | **35**, applying to the added mod only | S3, S4 | 0.5.5.10 | high |
| Perfect Chaos Orb | `…/CurrencyRerollRare3` | same | same | **50** | S3, S4 | 0.5.5.10 | high |

All ids are prefixed `Metadata/Items/Currency/`.

- PoE2's Chaos Orb is a one-mod swap, not a full reroll (S1). The Greater and Perfect tiers were added in 0.3.0 (S5).
- The minimum-level exception of General rule 2 applies to every Greater and Perfect orb.

## 3. Quality currency and catalysts

| Name | Metadata id | Effect | Preconditions | Numbers | Source | Patch | Conf. |
|---|---|---|---|---|---|---|---|
| Armourer's Scrap | `…/CurrencyArmourQuality` | "Improves the quality of an armour" | Armour below max quality | Cap 20% ("Quality currency still cannot apply more than 20% Quality", 0.3.0). The amount per use is disputed (see Conflicts). | S1, S5 | 0.3.0 / 0.5.5.10 | high (cap), low (amount) |
| Blacksmith's Whetstone | `…/CurrencyWeaponQuality` | "Improves the quality of a martial weapon" | Martial weapon, not a caster weapon | same | S1, S4 | 0.5.5.10 | same |
| Arcanist's Etcher | `…/CurrencyMagicQuality` | "Improves the quality of a wand, staff or sceptre" | Caster weapon | same | S1 | 0.5.5.10 | same |
| Glassblower's Bauble | `…/CurrencyFlaskQuality` | "Improves the quality of a flask" | Flask | same | S1 | 0.5.5.10 | same |
| Gemcutter's Prism | `…/CurrencyGemQuality` | "Improves the quality of a Skill Gem" | Skill gem | Amount not found | S1 | 0.5.5.10 | high (text) |
| Catalysts, ring/amulet (13: Flesh, Neural, Carapace, Uul-Netol's, Xoph's, Tul's, Esh's, Chayula's, Reaver, Sibilant, Skittering, Adaptive, Necrotic) | `…/CurrencyJewelleryQuality{Life,Mana,Defences,Physical,Fire,Cold,Lightning,Chaos,Attack,Caster,Speed,Attribute,Minion}` | "Adds quality that enhances [tag] modifiers on a ring or amulet. Replaces other quality types" | Ring or amulet. Grasping Mail is also accepted in CoE. | Quality multiplies the matching mods' values. Changing the type resets quality to 0 and starts the new type. Cap 20%, more on Breach rings (+20 or +25 max quality). Since 0.5.0 obtained only from the Genesis Tree. | S1, S3, S4, S7 | 0.5.0 | high (text), medium (amount) |
| Refined catalysts, jewel (13, same tags) | `…/CurrencyJewelQuality{…}` | "…modifiers on a jewel" | Jewel | New in 0.5.0 (S7 says "12 Catalysts"; S1 and S3 list 13) | S1, S3, S7 | 0.5.0 | high |

- **Quality per use in CoE (S4)**, applied to the scraps, whetstones, etchers, baubles and catalysts alike: `amount = floor(clamp(30·e^(−ilvl/30) − 0.3, 1, 20))`, and when the result is 1 there is a 20% chance of 2.
  - Examples: ilvl 1 → 20; ilvl 30 → 10; ilvl 45 → 6; ilvl 60 → 3; ilvl 75 → 2; ilvl ≥ 79 → 1 (20%: 2).
  - Search snippets agree in direction: "lower item level = more quality per use" (catalyst guides).
- **Vaal infusers:** see §5.

## 4. Socket currency

Artificer's Orb and the Jeweller's Orbs are in §1. Vaal Orb's +1 socket is in §1. Orb of Extraction is in §5.

## 5. "Vaal" group (Fate of the Vaal / Temple currencies, core since 0.5.0)

| Name | Metadata id | Effect | Preconditions | Numbers | Source | Patch | Conf. |
|---|---|---|---|---|---|---|---|
| Architect's Orb | `…/CurrencyIncursionDoubleCorrupt` | "Modifies a Corrupted Equipment or Jewel item unpredictably or destroys it" | Corrupted equipment or jewel | 50%: adds a second Corruption enchantment. 50%: the item is destroyed. Only adds enchantments. | S1, S4, S10 | 0.4/0.5 | medium |
| Crystallised Corruption | `…/CurrencyIncursionDoubleCorruptGem` | "Modifies a Corrupted Skill Gem unpredictably or destroys it" | Corrupted skill gem | A second corruption outcome that differs from the first, or destroyed at 50% | S1, S10 | 0.4/0.5 | medium |
| Core Destabiliser | `…/CurrencyIncursionModifySoulCore` | "Modifies a Soul Core unpredictably, with a chance to destroy it" | Soul Core | Turns it into another Soul Core (poe-vault, per search). Odds unknown. | S1 | 0.5.5.10 | high (text), low (odds) |
| Ancient Infuser | `…/CurrencyIncursionCorruptTablet` | "Modifies a Tablet unpredictably and Corrupts it" | Tablet | Same 4 outcomes as the Vaal Orb on tablets (§1), 25% each in CoE | S1, S4, S10 | 0.4/0.5 | medium |
| Vaal Cultivation Orb | `…/CurrencyIncursionMutateUnique` | "Replaces up to 2 modifiers on a Corrupted Vaal Unique / Replaces other Uniques with a Corrupted Unique of the same Item Class" | Unique | Vaal uniques draw from a hidden special list. Outcomes changed in 0.5.0 (S7). | S1, S7, S10 | 0.5.0 | high (text) |
| Yaomac's Orb of Sacrifice | `…/CurrencyIncursionMutateCorruptionEnchantWeapon` | "Upgrades a Corruption Enchantment on a Rare Weapon or Quiver and removes a random Modifier" | Corrupted Rare weapon or quiver with an upgradable enchantment | Removes 1 random non-fractured explicit mod (S4) | S1, S4 | 0.5.5.10 | high (text), medium (rule) |
| Kopec's Orb of Sacrifice | `…/CurrencyIncursionMutateCorruptionEnchantArmour` | same, for a Rare Armour | same | same | S1, S4 | 0.5.5.10 | same |
| Kamasa's Orb of Sacrifice | `…/CurrencyIncursionMutateCorruptionEnchantJewellery` | same, for a Rare Amulet, Ring or Belt | same | same | S1, S4 | 0.5.5.10 | same |
| Yugul's Orb of Sacrifice | `…/CurrencyIncursionMutateCorruptionEnchantJewel` | same, for a Rare Jewel | same | same | S1, S4 | 0.5.5.10 | same |
| Vaal Armourer's Infuser | `…/CurrencyIncursionWeaponOrArmourQualityHigh` | "Improves the quality of an Armour, exceeding maximum quality by up to 10% with a chance of Corrupting it" | Armour, **quality ≥ 20%** (0.5.0) | Cap: max quality +10. Corruption chance: CoE uses 5% × points of quality above the maximum before use. S10 (0.4) says +1–2% up to 30%, or corrupts. | S1, S3, S4, S7, S10 | 0.5.0 | high (text), low (odds) |
| Vaal Blacksmith's Infuser | `…/CurrencyIncursionMartialWeaponQuality` | same, for a Martial Weapon | same | same | S1, S7 | 0.5.0 | same |
| Vaal Arcanist's Infuser | `…/CurrencyIncursionCasterWeaponQuality` | same, for a wand, staff or sceptre | same | same | S1, S7 | 0.5.0 | same |
| Vaal Catalysing Infuser | `…/CurrencyIncursionJewelleryQuality` | same, for a ring or amulet | same | same | S1, S7 | 0.5.0 | same |
| Orb of Extraction | `…/CurrencyIncursionExtractAllSocketablesCurrency` (also `…ExtractAllSocketablesBench`, no text) | "Destroys an Equipment item, returning any non Socket-Bound Augments socketed in it" | Equipment with socketed Augments | – | S1 | 0.5.5.10 | high |
| Vaal Siphoner | `…/CurrencyIncursionVaalIncubator` (item class IncubatorStackable) | "Adds a kill threshold to a Corrupted Rare Jewellery item, when threshold is met Siphons a random modifier and improves the numeric values of other modifiers" | Corrupted Rare ring, amulet or belt | Disputed: the siphoned mod is removed, or drops one tier. The others go up to 110% of their maximum. | S1 + search snippets | 0.5.5.10 | high (text), low (numbers) |
| Guatelitzi's Thesis | `Metadata/Items/SoulCores/ThesisOfBlood` | Ancient Augment, "Limited to: 1", requires level 60. Helmet: "Gain Armour equal to 35% of Life Lost from Hits in the past 8 seconds" (0.5.0). Body: "10% of Physical Damage prevented Recouped as Life". Boots: "Lose 5% of maximum Life per second while Sprinting, 25% increased Movement Speed while Sprinting". | An Augment socket in that slot | – | S3, S7 | 0.5.0 | high |
| Citaqualotl's Thesis | `Metadata/Items/SoulCores/ThesisOfSacrifice` | Body: "You Recoup 50% of Damage taken by your Offerings as Life". Gloves: "One of your Persistent Minions revives when an Offering expires". Boots: "Sacrifice 10% of maximum Life to gain that much Guard when you Dodge Roll". | same | – | S3 | 0.5.x | high |
| Jiquani's Thesis | `Metadata/Items/SoulCores/ThesisOfSouls` | Helmet: "+1 to maximum Mana per 3 Item Armour on Equipped Helmet". Gloves: "Energy Shield Recharge starts after spending a total of 2000 Mana, no more than once every 2 seconds". Boots: "Increases and Reductions to Movement Speed also apply to Energy Shield Recharge Rate". | same | – | S3 | 0.5.x | high (a guide says per 2 Item ES: conflict) |
| Quipolatl's Thesis | `Metadata/Items/SoulCores/ThesisOfExperiments` | Helmet: "A random Skill that requires Glory generates 50% of its maximum Glory when your Marks Activate" (0.5.0). Gloves: "Your Energy Shield Recharge starts when your Minions are Reformed". Body: "+75% of Armour also applies to Chaos Damage while on full Energy Shield". | same | – | S3, S7 | 0.5.0 | high |

All ids without a full path are prefixed `Metadata/Items/Currency/`.

- Fate of the Vaal currencies have a maximum stack of 5,000 since 0.5.0 (S7).
- The S1 export gives a stack of 10 per item, which is the inventory stack.

## 6. Omens

All ids are `Metadata/Items/Currency/<id>` (S1). Every omen's text begins "While this item is active in your inventory …" and it is consumed when triggered. Drop level is 75 where poe2db shows one.

"Tradeable" means present in the trade API's Ritual group on 2026-11-24 (S2). There are 40 such omens. The game data has 45 omens plus 5 Expedition Sagas.

### 6a. Crafting omens: Exalted, Regal, Chaos, Annulment, Alchemy

| Name | Id | Effect (game text) | Preconditions / exact rule | Numbers | Tradeable | Source | Patch | Conf. |
|---|---|---|---|---|---|---|---|---|
| Omen of Greater Exaltation | `OmenOnExaltAddTwoMods` | "your next Exalted Orb will add two random modifiers" | Rare with an open affix. Behaviour with only 1 open slot is unknown (CoE simply rolls 2; see in-game checks). Works with Greater and Perfect Exalted Orbs and their minimum level. | 2 mods | yes | S1, S4 | 0.5.5.10 | high (text) |
| Omen of Sinistral Exaltation | `OmenOnExaltAddPrefixes` | "…Exalted Orb will add only prefix modifiers" | Needs an open prefix | Pool limited to prefixes, weights unchanged | yes | S1, S4 | 0.5.5.10 | high |
| Omen of Dextral Exaltation | `OmenOnExaltAddSuffixes` | "…only suffix modifiers" | Needs an open suffix | same | yes | S1, S4 | 0.5.5.10 | high |
| Omen of Homogenising Exaltation | `OmenOnExaltAddExistingModType` | "…will add a Modifier of the same type as an existing Modifier on the Item" | CoE reading: the pool is limited to mods that share at least one mod tag with an existing explicit mod | – | yes, but disabled from dropping (0.4.0). Standard-only on the Currency Exchange (0.5.0). | S1, S4, S6, S7 | 0.5.0 | high (text), medium (tag rule) |
| Omen of Catalysing Exaltation | `OmenOnExaltConsumeQuality` | "…will consume all Catalyst Quality … to increase the chance of the corresponding type of Modifier" | Ring, amulet or jewel with catalyst quality | CoE: the weight of mods with the catalyst's tag is multiplied by `1 + 0.2·Q` for Q ≤ 20 (Q = 20 gives ×5). Above 20: `1 + 0.2·20 + 0.12·(Q−20)`. Quality is set to 0 afterwards. | yes | S1, S3, S4 | 0.5.5.10 | high (text), low (multiplier) |
| Omen of Homogenising Coronation | `OmenOnRegalAddExistingModType` | "your next Regal Orb will add a Modifier of the same type as an existing Modifier on the Item" | Magic item. Tag rule as above. | – | yes, but disabled from dropping (0.4.0). Standard-only exchange (0.5.0). | S1, S4, S6, S7 | 0.5.0 | high |
| Omen of Sinistral Coronation | `OmenOnRegalPrefix` | "…Regal Orb will add only prefix modifiers" | – | – | **no**: retired 0.3.0 | S1, S5 | 0.3.0 | high |
| Omen of Dextral Coronation | `OmenOnRegalSuffix` | "…only suffix modifiers" | – | – | **no**: retired 0.3.0 | S1, S5 | 0.3.0 | high |
| Omen of Whittling | `OmenOnChaosLowestLevelMod` | "your next Chaos Orb will remove the lowest level modifier" | Rare. "Level" is the level requirement of the mod's tier. Ties are broken at random. Fractured mods are skipped. With an Erasure omen the pick is limited to that side (CoE). | – | yes | S1, S4 | 0.5.5.10 | high (text), medium (ties, combination) |
| Omen of Sinistral Erasure | `OmenOnChaosPrefix` | "your next Chaos Orb will remove only prefix modifiers" | Needs a removable prefix. The added mod is not side-restricted (CoE). | – | yes | S1, S4 | 0.5.5.10 | high (text), medium (add side) |
| Omen of Dextral Erasure | `OmenOnChaosSuffix` | "…remove only suffix modifiers" | same | – | yes | S1, S4 | 0.5.5.10 | same |
| Omen of Greater Annulment | `OmenOnAnnulRemoveTwoMods` | "your next Orb of Annulment will remove two modifiers" | – | 2 mods | **no**: retired 0.3.0 | S1, S5 | 0.3.0 | high |
| Omen of Sinistral Annulment | `OmenOnAnnulRemovePrefixes` | "…Orb of Annulment will remove only prefix modifiers" | A removable prefix | Uniform over non-fractured prefixes | yes | S1, S4 | 0.5.5.10 | high |
| Omen of Dextral Annulment | `OmenOnAnnulRemoveSuffixes` | "…remove only suffix modifiers" | A removable suffix | same | yes | S1, S4 | 0.5.5.10 | high |
| Omen of Light | `OmenOnAnnulRemoveAbyssMod` | "your next Orb of Annulment will remove only Desecrated modifiers" | A Desecrated mod, revealed or unrevealed (CoE) | – | yes | S1, S4 | 0.5.5.10 | high |
| Omen of Sinistral Alchemy | `OmenOnAlchemyMaximumPrefixes` | "your next Orb of Alchemy will result in the maximum number of prefix modifiers" | – | 3 prefixes + 1 suffix | **no**: retired 0.3.0 | S1, S4, S5 | 0.3.0 | high |
| Omen of Dextral Alchemy | `OmenOnAlchemyMaximumSuffixes` | "…maximum number of suffix modifiers" | – | 1 prefix + 3 suffixes | **no**: retired 0.3.0 | S1, S4, S5 | 0.3.0 | high |

### 6b. Divine, Vaal, Chance and Essence omens

| Name | Id | Effect (game text) | Preconditions / exact rule | Numbers | Tradeable | Source | Patch | Conf. |
|---|---|---|---|---|---|---|---|---|
| Omen of the Blessed | `OmenOnDivineRerollImplicits` | "your next Divine Orb will only reroll Implicit Modifiers" | Item with implicits | – | yes | S1, S4 | 0.5.5.10 | high |
| Omen of Sanctification | `OmenOnDivineSanctify` | "your next Divine Orb used on a Rare item will Sanctify it" | Rare | Each mod's value is multiplied by its own random factor between **0.78 and 1.22** in 0.01 steps, then rounded up (wiki snippet). Since 0.5.0 the factor multiplies the **current** value instead of rerolling (S7). The item then becomes Sanctified and cannot be modified. Older figure: 0.8–1.2. | yes | S1, S3, S7 | 0.5.0 | high |
| Omen of Corruption | `OmenOnVaalRemoveDoNothingOutcome` | "your next Vaal Orb will always result in change" | – | Removes the "no change" outcome | **yes on the trade list**, but "can no longer be obtained" (0.5.0) and Standard-only on the exchange | S1, S7 | 0.5.0 | high |
| Omen of Chance | `OmenOnChanceNotDestroy` | "your next Orb of Chance will not destroy the Item" | Normal item | Does not guarantee a unique. What happens on a failed roll is not stated. | yes | S1 | 0.5.5.10 | high (text) |
| Omen of the Ancients | `OmenOnChanceAncientOrb` | "your next Orb of Chance will upgrade the Item to a random Unique of the same Item Class" | Normal item | The class (e.g. any belt), not the exact base | yes | S1 | 0.5.5.10 | high |
| Omen of Sinistral Crystallisation | `OmenOnPerfectEssencePrefix` | "your next Perfect or Corrupted Essence will remove only Prefix modifiers" | Rare. CoE also applies it to Alloys. | – | yes | S1, S4 | 0.5.5.10 | high |
| Omen of Dextral Crystallisation | `OmenOnPerfectEssenceSuffix` | "…remove only Suffix modifiers" | same | – | yes | S1, S4 | 0.5.5.10 | high |

### 6c. Desecration (Abyss) omens

Abyss omens do not drop in areas below level 65 (0.5.0, S7).

| Name | Id | Effect (game text) | Preconditions / exact rule | Numbers | Tradeable | Source | Patch | Conf. |
|---|---|---|---|---|---|---|---|---|
| Omen of Abyssal Echoes | `OmenOnAbyssRerollOptions` | "the next time you reveal Desecrated modifiers you can reroll the options once" | An unrevealed mod being revealed | Revealing shows 3 options (CoE `veiledPicksNumber: 3`) | yes | S1, S4 | 0.5.5.10 | high |
| Omen of the Sovereign | `OmenOnAbyssGuarenteeLichTypeMod1` | "your next Weapon or Jewellery Desecration attempt will guarantee a random Ulaman modifier" | Weapon or jewellery | – | yes | S1 | 0.5.5.10 | high |
| Omen of the Liege | `OmenOnAbyssGuarenteeLichTypeMod2` | "…guarantee a random Amanamu modifier" | same | – | yes | S1 | 0.5.5.10 | high |
| Omen of the Blackblooded | `OmenOnAbyssGuarenteeLichTypeMod3` | "…guarantee a random Kurgal modifier" | same | – | yes | S1 | 0.5.5.10 | high |
| Omen of Putrefaction | `OmenOnAbyssVeilAllAndCorrupt` | "your next Desecration attempt will replace all modifiers on the item creating an item with up to 6 Unrevealed modifiers and Corrupting the item" | Rare that can be desecrated | Up to 6 unrevealed mods. Sides are random within 3/3 (CoE). The ancient-bone minimum level is ignored (S9). | yes | S1, S4, S9 | 0.5.5.10 | high (text), medium (rest) |
| Omen of Sinistral Necromancy | `OmenOnAbyssAddPrefixes` | "your next Desecration attempt will add only prefix modifiers" | CoE: when no prefix is open, a random prefix is removed first | – | yes | S1, S4 | 0.5.5.10 | high (text), medium (removal) |
| Omen of Dextral Necromancy | `OmenOnAbyssAddSuffixes` | "…add only suffix modifiers" | same for suffixes | – | yes | S1, S4 | 0.5.5.10 | same |

Desecration rules from S4 and S7, for context:

- Items are limited to 1 Desecrated mod, and since 0.5.0 Desecrated mods no longer count as crafted.
- Ancient bones carry a minimum modifier level of **40** (CoE).
- Gnawed bones work only on items of level ≤ 64.
- A desecration on a full item first removes a random mod.

### 6d. Waystone omens (Chaos Orb)

| Name | Id | Effect (game text, 0.5) | Rule | Tradeable | Source | Patch | Conf. |
|---|---|---|---|---|---|---|---|
| Omen of Chaotic Rarity | `OmenOnChaosMapItemRarity` | "your next Chaos Orb will replace all Modifiers on a Waystone with Modifiers that do not grant Item Rarity" | **Inverted in 0.5.0**: it used to guarantee the type, now it excludes it. Up to 3 Chaotic omens at once. | yes | S1, S7 | 0.5.0 | high |
| Omen of Chaotic Quantity | `OmenOnChaosMapPackSize` | "…that do not grant Pack Size" | same | yes | S1, S7 | 0.5.0 | high |
| Omen of Chaotic Monsters | `OmenOnChaosMapMonsterRarity` | "…that do not grant Monster Rarity" | same | yes | S1, S7 | 0.5.0 | high |
| Omen of Chaotic Effectiveness | `OmenOnChaosMapMonsterEffectiveness` | "…that do not grant Monster Effectiveness" | New in 0.5.0 | yes | S1, S7 | 0.5.0 | high |

### 6e. Removed and non-crafting omens (listed for completeness)

| Name | Id | Effect | Tradeable | Source | Conf. |
|---|---|---|---|---|---|
| Omen of Recombination | `OmenRecombination` | No text. **Removed in 0.5.0**: "The Recombinator has been disabled", and existing omens "will be deleted upon logging in". | no | S1, S3, S7 | high |
| Omen of Refreshment | `OmenOnLowLifeRecoverCharges` | Recovers flask and charm charges at Low Life | yes | S1 | high |
| Omen of Resurgence | `OmenOnLowLifeFullyHeal` | Recovers Life, Mana and ES at Low Life | yes | S1 | high |
| Omen of Amelioration | `OmenOnDeathPreventExpLoss` | Prevents 75% of experience loss on death | yes | S1 | high |
| Omen of Answered Prayers | `OmenShrineAdditionalEffect` | The next Shrine grants an additional effect | yes | S1 | high |
| Omen of Secret Compartments | `OmenStrongboxOpenableAgain` | The next Strongbox can be reopened | yes | S1 | high |
| Omen of the Hunt | `OmenTormentedMonsterReleased` | The next Possessed monster releases all Azmeri Spirits | yes | S1 | high |
| Omen of Reinforcements | `OmenRogueExileSummonsPartyMember` | The next Rogue Exile summons an ally | yes | S1 | high |
| Omen of Gambling | `OmenGambleNoGoldCost` | The next Gamble purchase has a 50% chance of costing no Gold and not consuming the omen | yes | S1 | high |
| Omen of Bartering | `OmenSellVendorRandomise` | The next sold item's Gold value is "incorrectly assessed" | yes | S1 | high |
| Aldur's, Medved's, Vorana's, Uhtred's, Olroth's Saga | `Metadata/Items/Expedition/Expedition2Logbook{Special,Medved,Vorana,Uhtred,Olroth}` | Logbook omens (class Omen); poe2db counts them among its 50 | not in the Ritual group | S1, S3 | high |

## Conflicts

1. **Quality per use.**
   - CoE (S4) uses one item-level formula for every quality currency and catalyst: 20 at ilvl 1, 10 at ilvl 30, about 1 at ilvl ≥ 79.
   - Guides (from search) give a PoE1-style 5% / 2% / 1% for Normal / Magic / Rare. CoE's code also contains a 5/2/1 by-rarity function, but its quality currencies do not call it.
   - Neither poe2db nor the game export shows the table. **Unresolved.**
2. **Vaal Orb on jewels.**
   - S10 lists: no change, reroll 1–3, enchant, add or remove an affix.
   - CoE lists: no change ×2, enchant, ×0.78–1.23 values.
   - Odds are not published by either.
3. **Vaal infuser.**
   - S10 (0.4): +1–2% quality up to 30%, or corrupt.
   - CoE (0.5.5.5): the item-level quality amount, cap max +10, corruption chance 5% per point above the maximum.
   - 0.5.0 also added "only at or above 20% Quality" (S7).
4. **Vaal Siphoner.**
   - The siphoned modifier is either removed (poe-vault, pre-launch) or lowered one tier (Mobalytics, per snippet).
   - The others go up to 110% of their maximum (Mobalytics) or are "randomised up to 10% above max" (poe2db snippet).
5. **Sanctify range.** 0.78–1.22 (poe2db, wiki snippet, CoE) against 0.8–1.2 (older guides). The newer figure wins.
6. **Chaotic waystone omens in CoE.** CoE (S4) still models the pre-0.5 "guarantee the type" meaning and has no handler for Chaotic Effectiveness. Game text and the 0.5.0 notes say "do not grant". Game text wins.
7. **Trade list against game data.**
   - S2 lists Omen of Corruption, Homogenising Exaltation and Homogenising Coronation as tradeable.
   - 0.4.0 and 0.5.0 say they no longer drop and appear on the Currency Exchange only in Standard leagues.
   - The trade site is not split by league in the static list, so the items exist but cannot be obtained in the 0.5 leagues.
8. **Refined catalyst count.** The 0.5.0 notes say "a new set of 12 Catalysts" for jewels. The game data and poe2db list 13.
9. **Jiquani's Thesis helmet.** "+1 maximum Mana per 3 Item Armour" (poe2db) against "per 2 Item Energy Shield" (Mobalytics snippet).
10. **Artificer's Orb targets.** The in-game text says "Martial Weapon, wand, staff or Armour". One reference section on poe2db omits wands and staves. Game text wins.

## Needs an in-game check

1. **Quality per use** of each scrap, whetstone, etcher, bauble and prism on a Normal, a Magic and a Rare item of a low and a high item level (Conflict 1). Also catalyst quality per use by item level.
2. **Omen of Greater Exaltation on a Rare with exactly 1 open affix:** blocked, adds 1, or replaces a mod?
3. **Omen of Greater Exaltation combined with Sinistral/Dextral Exaltation:** are both mods on that side, and does it need 2 open slots on that side?
4. **Homogenising "same type":** a shared mod tag (CoE) or the same mod group? Which tags count? This only matters in Standard now.
5. **Catalysing Exaltation multiplier:** the CoE formula `1 + 0.2·Q` is unverified.
6. **Whittling:** what counts as "level" (tier level requirement, assumed), tie-breaking, and the interaction with Erasure omens.
7. **Chaos with Erasure:** may the added mod land on the other side?
8. **The minimum-level exception** (the highest tier of a family stays eligible): confirm on one Perfect Exalted roll. This decides whether Perfect orbs can add low-tier-only families.
9. **Orb of Chance:** success odds per base, and what happens under Omen of Chance on a failed roll (item unchanged?).
10. **Vaal Orb outcome odds** for each item class (equal 25% assumed by CoE), the jewel outcome list, and the 0.5 "multiply current value" range.
11. **Architect's Orb, Crystallised Corruption, Core Destabiliser, Ancient Infuser:** confirm the 50% destroy and the 25% figures.
12. **Vaal infusers:** the amount per use and the corruption chance.
13. **Vaal Siphoner:** kill threshold, the siphon rule, and the improvement numbers.
14. **Hinekora's Lock:** what the preview shows, whether a locked item can be traded or mirrored, and whether the lock survives a currency use that is declined.
15. **Fracturing Orb:** whether Desecrated (revealed) and crafted mods can be fractured, and whether unrevealed mods are excluded.
16. **Artificer's Orb socket maxima** per class (CoE data), especially foci and sceptres.
17. **Gemcutter's Prism:** quality per use on skill gems.
18. **Omen of Putrefaction:** the exact number of unrevealed mods ("up to 6") and the side split.
19. **Forbidden Rites (0.5.5):** confirm that no crafting changes were made. Only a summary (S8) was read; the full official 0.5.5 notes were not found.
