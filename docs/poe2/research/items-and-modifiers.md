# PoE2 items and modifiers: core rules for a crafting planner

- **Checked:** 2026-11-24.
- **Game state:** Path of Exile 2 Early Access, patch line 0.5.x. The data export used is repoe-fork "PoE2 version 0.5.5.10" (`https://repoe-fork.github.io/poe2/`, `mods.json` last modified 2026-11-19). Two leagues are live: **Runes of Aldur** (0.5.0, launched about 2026-05-29, still running) and the **Forbidden Rites** event league (0.5.5, launched 2026-09-04). Craft of Exile's PoE2 data was last updated to patch 0.5.5.5 on 2026-10-31.
- **Sources and how fresh they are:**
  - Official patch notes on pathofexile.com, all read in full:
    - 0.4.0 "The Last of the Druids" (thread 3883495, Dec 2025).
    - 0.5.0 "Return of the Ancients" (thread 3932540, May 2026).
    - 0.5.5 "Forbidden Rites" (thread 4000864, 2026-09-03).
    - 0.5.5 press release (thread 3999865, 2026-08-27).
  - poe2db.tw pages (they track the current client; their header shows "Runes of Aldur v0.5"): Currency, Omen, Crafting, Essence, Quality, Exceptional_Item, Sanctified_Items, Jewels, Charms, Relics, Fate_of_the_Vaal_league, Modifiers, Preserved_Jawbone.
  - Maxroll pages:
    - Corruption Outcomes, updated 2026-05-24.
    - Reforging Bench, updated 2026-06-15 for 0.5.2–0.5.4.
    - Crafting Overview, archived, updated 2026-06-17.
  - Craft of Exile's weightings page and its changelog.
  - repoe-fork export 0.5.5.10. I parsed `mods.json` and `base_items.json` myself.
  - Forum posts by players, marked as such where cited.
- **Refused or blocked:**
  - **www.poe2wiki.net and poe2wiki.net** returned an Anubis bot-wall ("Access Denied: error code 9e4edb5b6b850c41"). I did not try to get around it. Wiki facts below come only from search-engine snippets and are marked "wiki snippet". Some of those pages are 300–540 days old.
  - **mobalytics.gg** guide pages returned 403.
  - **game8.co** returned 403.
  - **maxroll.gg/poe2/resources/crafting-guide** returned 404.
- **Confidence scale:**
  - **H** means an official patch note, the item's own text, or the data export, read directly.
  - **M** means two secondary sources agree, or one current database page.
  - **L** means a single secondary source, a wiki snippet, or a player post.

---

## 1. Rarity and affix limits

1. **Magic items have at most 1 prefix and 1 suffix. Rare items have at most 3 prefixes and 3 suffixes, so 6 modifiers.**
   - Source: https://maxroll.gg/poe2/resources/path-of-exile-2-crafting-overview, page updated 2026-06-17.
   - Quote: "Magic items have up to 1 Prefix and 1 Suffix, whereas Rare items have up to 3 Prefixes and 3 Suffixes."
   - The Exalted Orb's own text (https://poe2db.tw/us/Exalted_Orb) agrees: "Rare items can have up to six random modifiers."
   - Patch: 0.5.x. Confidence: H.
2. **Jewels and Precursor Tablets are capped at 4 affixes, 2 prefixes and 2 suffixes.**
   - Source: wiki snippet of https://www.poe2wiki.net/wiki/Rarity: "Some item types, such as jewels and tablets, can only have up to four affixes (two prefixes and two suffixes)."
   - The 0.4.0 notes back the tablet cap (https://www.pathofexile.com/forum/view-thread/3883495): "Tablets now have a maximum of 4 modifiers." The same notes say "To unlock the ability to craft a tablet beyond 2 modifiers you need to have defeated the Arbiter of Ash."
   - The jewel cap is the wiki snippet only. Some uniques and jewel mods raise it: poe2db/Jewels lists "+1 Prefix Modifier allowed" and "+1 Suffix Modifier allowed". A Potent Liquid Emotion is also said to add a fifth affix slot (IGGM, single secondary source).
   - Patch: 0.4 to 0.5. Confidence: tablets H; jewels L–M.
3. **Flasks, charms and non-unique relics cannot be rare. They are capped at 2 modifiers, 1 prefix and 1 suffix.**
   - Source: wiki snippets of https://www.poe2wiki.net/wiki/Rarity ("Flasks and Charms cannot be of rare rarity") and https://www.poe2wiki.net/wiki/Item ("non-unique relics and flasks cannot be upgraded to rare as they are capped at 2 modifiers").
   - The data agrees: repoe 0.5.5.10 has flask-domain prefix and suffix mods only (70 prefixes, 35 suffixes) and relic-domain mods (`sanctum_relic`: 71 prefixes, 67 suffixes).
   - Patch: 0.5.x. Confidence: M.
4. **Waystones can be normal, magic or rare and use the 1+1 and 3+3 limits.**
   - Waystones have a corruption outcome that converts all affixes to prefixes or to suffixes, and another that adds random affixes to a rare waystone (Maxroll Corruption Outcomes, https://maxroll.gg/poe2/resources/corruption-outcomes).
   - Since 0.5.0: "Waystones must now be identified in order to activate them in the Map Device." (official 0.5.0 notes)
   - Patch: 0.5.0. Confidence: identification rule H; limits M.
5. **Desecrated mods count toward the normal prefix and suffix limits. Since 0.5.0 an item may hold only one desecrated modifier and only one crafted modifier.**
   - Source: official 0.5.0 notes, https://www.pathofexile.com/forum/view-thread/3932540.
   - Quotes: "All crafted modifiers are now guaranteed, but items can only have 1 crafted modifier at a time." and "Desecrated modifiers no longer count as crafted modifiers, but items are limited to 1 Desecrated modifier."
   - Omen of Putrefaction is an exception: it creates "up to 6 Unrevealed modifiers" and corrupts the item (poe2db Omen).
   - Patch: 0.5.0. Confidence: H.
6. **One essence modifier per item since 0.5.**
   - Source: Mobalytics essence guide snippet: "In PoE 2 0.5 … items are only able to have a single Essence modifier at a time". Not found verbatim in the official notes; it may be a reading of the one-crafted-modifier rule in fact 5.
   - Patch: 0.5. Confidence: L–M.
7. **Identification.** A Scroll of Wisdom "Identifies an item" (poe2db Currency). The Reforging Bench returns unidentified items (fact 34). The Megalomaniac unique jewel "now drops identified" (0.5.0 notes). Patch: 0.5.x. Confidence: H.
8. **Unidentified "Tier N" items (tiered rares).**
   - A higher tier sets a floor on the modifier level of the rolls made at identification. Wiki snippet table:

     | Unid tier | Needs item level | Mods clamped to level |
     |---|---|---|
     | 2 | 66 | 11+ |
     | 3 | 71 | 23+ |
     | 4 | 76 | 35+ |
     | 5 | 79 | 48+ |

   - The floor "does not affect modifiers added after the item is identified, such as through crafting". The wiki snippet also says the tiers do not change outcomes on magic items.
   - Source: search snippets of https://www.poe2wiki.net/wiki/Rare and the Tier page; player forum thread https://www.pathofexile.com/forum/view-thread/3825924 ("T1 suffix on a Tier 2 spear").
   - Patch: not dated; the snippet may predate 0.5. Confidence: L.
9. **Exceptional items.**
   - High-tier rares can instead drop as an **Exceptional Normal** item. It has either quality over the maximum (up to 30%) or one extra Augment Socket.
   - poe2db quote: "High Tier Rare Items found have a chance to instead drop as an Exceptional Normal Item."
   - Atlas passives gate them (Dressed in Fineries, Exceptional Footwear/Handiwork/Adornments/Armaments/Vestments, Fabled Treasures).
   - The wiki snippet adds "item level 78" and says the extra socket stacks with a corruption socket.
   - Source: https://poe2db.tw/us/Exceptional_Item. Patch: 0.5.x. Confidence: M; the ilvl 78 figure is L.
10. **Corrupted state.**
    - A Vaal Orb "Modifies an item unpredictably and Corrupts it" (poe2db Currency).
    - A corrupted item cannot take normal crafting currency. Only corruption-specific items work on it: Architect's Orb, the Corruption Altar, Omen of Putrefaction's output, desecration reveal (Craft of Exile enabled "desecration reveal on corrupted items" on 2026-08-01), and Vaal Cultivation Orb on Vaal uniques.
    - Patch: 0.4 to 0.5. Confidence: M–H.

## 2. Item level, modifier level, tiers, Greater and Perfect currency

11. **Each modifier has a required (spawn) level. It can roll only when the item level is at or above that level.**
    - Data example (repoe 0.5.5.10): `IncreasedLife1..13` on armour and jewellery have required levels 1, 6, 16, 24, 33, 38, 46, 54, 60, 65, 70, 75, 80, for values +10–19 up to +200–214 life.
    - The 0.5.0 notes change such levels directly, e.g. "The 'Precise' Accuracy modifier on Weapons now has a minimum level of 8 (previously 1)."
    - Patch: 0.5.5.10. Confidence: H.
12. **A base can drop only at or above its drop level. Chest and non-monster drops use the area level.**
    - Wiki snippet https://www.poe2wiki.net/wiki/Drop_level: "An item base type can only drop if the item level is equal to or greater than its minimum drop level."
    - Every base in repoe `base_items.json` has `drop_level`. Equipment bases also carry `requirements` {level, str, dex, int}.
    - Patch: 0.5.x. Confidence: M–H.
13. **An item's level requirement is raised to 80% of its highest modifier level.**
    - Sources: wiki and poedb snippets; a player's worked example (mod level 81 gives requirement 64).
    - Patch: PoE1 rule, not confirmed by GGG for PoE2. Confidence: L.
14. **Tier numbering in the advanced item description: Tier 1 is the best tier.**
    - The lowest tier number varies per mod, down to T10 or more.
    - The official 0.5.0 notes use the same convention: "+Level of all Melee Skills on Two Handed Attack Weapons now has a value of +5 at Tier 1 (previously +7)".
    - A 2024 player thread asked whether tiers were reversed (https://www.pathofexile.com/forum/view-thread/3616864, /3679890). The "Tier N" label on unidentified items (fact 8) and waystone tiers count the other way: higher is better.
    - Patch: 0.5.0. Confidence: H for mods.
15. **Greater and Perfect currency sets a minimum modifier level for what it adds.**
    - Source: poe2db Currency, https://poe2db.tw/us/Currency.

      | Currency | Greater | Perfect |
      |---|---|---|
      | Orb of Transmutation | 44 | 70 |
      | Orb of Augmentation | 44 | 70 |
      | Regal Orb | 35 | 50 |
      | Exalted Orb | 35 | 50 |
      | Chaos Orb | 35 | 50 |

    - 0.5.0 notes: "Greater Orbs of Transmutation and Greater Orbs of Augmentation now have a minimum Modifier Level of 44 (previously 55)", and "Greater and Perfect currencies have been made somewhat rarer".
    - Patch: 0.5.0 onward. Confidence: H.
16. **Ancient desecration bones give options of modifier level 40 or higher at reveal.**
    - Gnawed bones work only on items of item level ≤ 64. Preserved bones work at any item level. Bones drop at level 25 (Gnawed), 61 (Preserved) and 75 (Ancient).
    - Sources: wiki snippet https://www.poe2wiki.net/wiki/Ancient_Collarbone; u4n and timesaver guides; poe2db Preserved_Jawbone (drop level 61).
    - Patch: 0.3 onward. Confidence: M.

## 3. Spawn weights

17. **The PoE2 client data does not carry real spawn weights.**
    - In repoe-fork 0.5.5.10 `mods.json`, every spawn-weight entry is 0 or 1. Over 16,911 mods there are 7,933 entries of weight 1, 9,249 of weight 0, and no other value. I counted this myself.
    - Craft of Exile (https://craftofexile.com/weightings?game=poe2): "Unfortunaly the information regarding modifier weightings is not part of the game client's for Path of Exile 2."
    - So the export's 1/0 is effectively an allowed/forbidden flag per tag.
    - Patch: 0.5.5.10. Confidence: H.
18. **Craft of Exile estimates PoE2 weights in two ways.**
    - Recombinators, for most equipment: "have devised a way of finding them out using recombinators" (Krakenbul and the community).
    - Trade-site parsing, for charms, jewels, tablets and waystones: "The data is obtained from parsing trade-site listings."
    - The results are then normalised: "a normalization script is applied to apply breakpoints to the weighting numbers and create familiar curves". Known bias: "Items from the trade site can generally have a bias towards more desired mods and/or higher tier mods."
    - Changelog: "Updated PoE2 modifier weights using Krakenbul's gathered data" (2026-09-03). "Added notices to let the user know when modifiers have unknown weightings" (2026-04-07).
    - Note: the recombinator is disabled in 0.5 (fact 35), so the recombinator method cannot be repeated on 0.5 data.
    - Confidence: H for what CoE states.
19. **No GGG statement on PoE2 weights was found.**
    - A player wrote on the official forum (Azula, 2025-04-10, https://www.pathofexile.com/forum/view-thread/3754260): "We knew these mod weights in poe1 because they are available in the client files, but in poe2 they are not."
    - The same player reported "T1 flat phys are around 70/70,000 … Other mods like life tend to always have weights around 1,000 and not become more rare with better tiers". This is an inference from CoE's analysis, not a GGG statement.
    - poe2db Modifiers shows a "Level" column and, for map mods, weights like "_map_key_low_ 1 / _default_ 0", i.e. the same 1/0 flags.
    - Confidence: M that no official statement exists. I searched but did not search exhaustively.

## 4. Mod families, local/global, implicits, classes, bases, quality, sockets

20. **Mod groups give exclusivity: an item cannot hold two mods of the same group.**
    - Each repoe mod has `groups` (e.g. `IncreasedLife`), `type`, `generation_type` (prefix/suffix/unique/corrupted/essence/…), `domain`, `implicit_tags`, `required_level` and `spawn_weights` by tag.
    - Hybrid mods exist as single mods with several stats. Example: `SoulInfluenceIncreasedLifeAndMana` "+(19-189) to maximum Life / +(19-189) to maximum Mana", in group IncreasedLife. Another: the "Squire's" hybrid Physical Damage + Accuracy (0.5.0 notes).
    - Patch: 0.5.5.10. Confidence: H for the data; the exclusivity rule is M (PoE1 rule, not restated by GGG for PoE2).
21. **Local versus global mods.** The mod ids carry it (e.g. `CorruptionLocalIncreasedEvasionRatingPercent1` "(15-25)% increased Evasion Rating" on `dex_armour`). Local mods change the item's own properties. Quality likewise scales local defences and damage (fact 24). Confidence: H for the data.
22. **Implicits.**
    - In repoe 0.5.5.10, 27 of 28 Ring bases, all 25 Amulets, all 19 Belts and all 11 Quivers carry implicits.
    - Charms (class `UtilityFlask`, e.g. "Thawing Charm" with `CharmImplicitUseOnFreeze1`) and Tablets carry them too.
    - Only 93 of 368 Body Armours, 16 of 35 Bows, no Foci and no Life Flasks have implicits.
    - Omen of the Blessed: "your next Divine Orb will only reroll Implicit Modifiers" (poe2db Omen).
    - Confidence: H.
23. **Item classes and tags.**
    - Armour bases are tagged by attribute: `str_armour`, `dex_armour`, `int_armour`, `str_dex_armour`, `str_int_armour`, `dex_int_armour`, `str_dex_int_armour`.
    - Culture tags: `ezomyte_basetype`, `karui_basetype`, `maraketh_basetype`, `vaal_basetype`, plus `runeforged`.
    - Weapons carry e.g. `bow`, `ranged`, `two_hand_weapon`, `weapon`. Jewels: `strjewel`, `dexjewel`, `intjewel`, `radius_jewel`, `str_radius_jewel`.
    - Bases list `requirements` {level, strength, dexterity, intelligence}.
    - Caution: `release_state: released` in the export includes classes not in the game (One Hand Sword, Axe, Dagger, Claw, TrapTool). The 0.5.5 notes mention "Unique Swords, Axes and Daggers were able to drop" only as a bug.
    - Confidence: H for the data; which classes are live is M.
24. **Quality.**
    - Default maximum 20%. Per quality point: martial weapons +1% more physical damage; armour +1% more armour, evasion, energy shield and runic ward; flasks +1% more recovery; charms +1% increased duration.
    - Jewellery and jewels take quality only from Catalysts, which raise a matching modifier group ("Catalysts replace other quality types").
    - Source: https://poe2db.tw/us/Quality.
    - Vaal Infusers can go "up to 10% over the maximum" with a chance to corrupt. 0.5.0: "All Infusers can only be used on items at or above 20% Quality."
    - Catalysts: since 0.5.0 they come only from the Genesis Tree. "Added a new set of 12 Catalysts that can add new quality modifiers to Jewels."
    - Essence of the Breach on jewellery: "+20% to Maximum Quality" (poe2db Essence).
    - Patch: 0.5.0. Confidence: H.
25. **The amount of quality added per currency use, by rarity, was not found.** Confidence: none.
26. **Sockets.**
    - Rune sockets were renamed **Augment Sockets** in 0.4.0, and runes/soul cores became "Augments" (0.4.0 notes).
    - Body armour and two-handed weapons take up to 2 sockets; other armour and weapons take 1; quivers and jewellery take none. An item never has more sockets than inventory cells.
    - A corruption socket ignores the limit, an Exceptional item adds one, and the two stack.
    - Sources: Maxroll overview ("Chestpieces and 2-handed weapons can have 2 sockets, all other items can have 1"); wiki snippet https://www.poe2wiki.net/wiki/Augment_Socket.
    - Artificer's Orb: "Adds an Augment Socket to a Martial Weapon, wand, staff or Armour" (poe2db Currency).
    - Jeweller's Orbs set a skill gem to 3, 4 or 5 support sockets (Lesser, Greater, Perfect). Since 0.5.0 they also work on items with skills.
    - Patch: 0.4 to 0.5. Confidence: H for the item text; the limits are M.

## 5. Special mod domains

27. **Desecrated (Abyss) modifiers.**
    - Bones add an unrevealed desecrated modifier to a rare item:
      - Collarbone: amulet, ring, belt.
      - Jawbone: weapon, quiver.
      - Rib: armour.
      - Preserved Cranium: "Desecrates a Rare Jewel".
    - The mod is revealed at the Well of Souls. Secondary guides say the reveal offers a choice of 3 (Vulkk, Sportskeeda).
    - Omens:
      - Omen of the Sovereign (Ulaman), Liege (Amanamu) and Blackblooded (Kurgal): "your next Weapon or Jewellery Desecration attempt will guarantee a random Ulaman/Amanamu/Kurgal modifier".
      - Sinistral and Dextral Necromancy: prefix-only or suffix-only.
      - Abyssal Echoes: "reroll the options once".
      - Light: Annulment "will remove only Desecrated modifiers".
      - Putrefaction: up to 6 unrevealed mods, then corrupts.
    - Data: repoe `domain: desecrated` has 147 prefixes, 175 suffixes and 93 unique entries; map and jewel ones are included. Lord-specific item mods carry tags `kurgal_mod`, `amanamu_mod`, `ulaman_mod` and are required level 65. Example: `AbyssModAmuletUlamanSuffixGlobalLevelOfSkillGems` "+1 to Level of all Skills".
    - Limit of one per item: fact 5. Abyss became core in 0.4.0. "Desecrated Modifiers granting Instant Leech can no longer roll" (0.5.0).
    - Patch: 0.5.5.10. Confidence: H for the item texts and data; the 3-option reveal is M.
28. **Essences.**
    - Lesser, normal and Greater essences: "Upgrades a Magic item to a Rare item, adding a guaranteed modifier."
    - Perfect essences: "Removes a random modifier and augments a Rare item with a new guaranteed modifier."
    - Corrupted essences (Hysteria, Delirium, Horror, Insanity), Essence of the Abyss and Essence of the Breach work the same way as Perfect on rares, with slot-specific results ("Mark of the Abyssal Lord"; jewellery "+20% to Maximum Quality").
    - Omens of Sinistral and Dextral Crystallisation make a Perfect or Corrupted essence remove only a prefix or only a suffix.
    - Essence-only mods: repoe has `is_essence_only` set on few mods (e.g. `EssenceGrantedPassive`), and the `generation_type: essence` rows are monster-domain. **The essence-only item mods cannot be built from the flag alone.** Use poe2db's per-essence outcome table.
    - Source: https://poe2db.tw/us/Essence. Patch: 0.5.x. Confidence: H for the item texts.
29. **Corruption.** Source: Maxroll Corruption Outcomes, updated 2026-05-24 for 0.4.
    - **Vaal Orb on magic or rare gear:** nothing; or 1–3 affixes randomised; or a Corrupted enchantment is added; or a special result:
      - +1 socket ignoring the limit, on helmet, gloves, boots, body, shield, focus and martial weapons;
      - or quality up to 23% on wands and staves.
    - **Uniques:** nothing; or affixes multiplied by "0.78-1.22 current roll" (the 0.5.0 notes moved this to the multiplier method); or an enchantment; or a special result.
    - **Jewels:** nothing; 1–3 affixes randomised; an enchantment; or add/remove an affix "ignoring normal limits". **Unique jewels:** "No change (50%)" and the rest.
    - **Waystones:** ±1 tier (1–16); or all affixes become prefixes or suffixes; or affixes are added.
    - **Charms and flasks:** quality up to 23%. **Gems:** ±level, ±socket, quality.
    - The page gives no outcome probabilities ("currently unknown", Maxroll overview). Secondary guides say "four outcomes equally weighted" (L).
    - Omen of Corruption ("your next Vaal Orb will always result in change") can no longer be obtained since 0.5.0, except in Standard.
    - Corrupted implicit mods in the data: `generation_type: corrupted` (126 mods), e.g. `CorruptionLocalIncreasedEnergyShieldPercent1` on `int_armour`.
    - Confidence: M for the outcome list; probabilities are unknown.
30. **Second corruption.**
    - Architect's Orb: "Modifies a Corrupted Equipment or Jewel item unpredictably or destroys it". Maxroll says 50/50 between a second enchantment and destruction.
    - Temple **Corruption Altar**: "allows you to add a second enchantment to your already corrupted items, but beware, there is a 50% chance to destroy the item" (https://poe2db.tw/us/Fate_of_the_Vaal_league).
    - Vaal Cultivation Orb: "Replaces up to 2 modifiers on a Corrupted Vaal Unique". On non-Vaal uniques it makes a new corrupted unique of the same class (Maxroll).
    - Crystallised Corruption works on gems. Ancient Infuser works on tablets: add a mod past the limit, add uses, transform, or destroy.
    - Fate of the Vaal (Temple of Atziri) became core in 0.5 (u4n and Mobalytics summaries). The 0.5.5 notes still fix Fate of the Vaal atlas passives.
    - Confidence: M.
31. **Fractured.** Fracturing Orb: "Fracture a random modifier on a rare item with at least 4 modifiers, locking it in place." (poe2db Currency). Confidence: H.
32. **Sanctified (Ritual).**
    - Omen of Sanctification: "your next Divine Orb used on a Rare item will Sanctify it". The values are multiplied by 78–122%, and the item can then barely be changed: "Most methods of item crafting and modification cannot be used on Sanctified items" (https://poe2db.tw/us/Sanctified_Items).
    - The wiki snippet adds: each mod rolls independently, in steps of 0.01, rounded up.
    - 0.5.0: "Sanctifying an item now multiplies each modifier value based on the current value, instead of randomising values."
    - Mobalytics says 80–120% (outdated).
    - Confidence: H for the range from poe2db and the patch note.
33. **Runes of Aldur (0.5.0 league; continues alongside Forbidden Rites).**
    - **Verisium Runeforging:** adds Runic Ward to armour. "Armours above this level [55] trade some of their regular base defences for Runic Ward."
    - **Unique Verisium Runeforging** (Act 3): upgrades the base of uniques below level 55.
    - **13 Alloys:** "add various new crafted modifiers to items by replacing an existing modifier, similar to Perfect Essences". A poe2db snapshot lists Runic, Adaptive, Protective, Expansive, Swift, Cyclonic, Prismatic, Mystic, Sovereign, Celestial, Transcendent, The Runebinder's and The Runefather's Alloy.
    - **3 Fluxes:** "transform the resistances on your items from one element to another".
    - **Runes:** 13 Ancient, 13 Mythical, 15 Meta, 15+ Runic Ward runes, and 60+ runes made by destroying a unique.
    - **Remnants:** "start with any number of slots between 2 and 10", and they craft "an item of your choosing by using Runic Recipes".
    - Since 0.5.5, outside the league, "The Verisium Anvil is now unlocked by completing The Runeseeker quest in Act 4".
    - Sources: official 0.5.0 notes and 0.5.5 notes, https://www.pathofexile.com/forum/view-thread/4000864.
    - Confidence: H for the existence of each system; the per-alloy mods were not read.
34. **Forbidden Rites (0.5.5 event league)** is a Ritual variant: Ritual sites in every campaign area, Tribute, Sacred Blooms, the Viridian Wildwood, and uniques bought with tribute. The official 0.5.5 notes list **no new item-crafting mechanic** for it. Confidence: H.

## 6. Benches and stations

35. **Recombinator: disabled since 0.5.0.**
    - Quote: "The Recombinator has been disabled. The Omen of Recombination has been removed." Existing omens were deleted at login.
    - The 0.5.5 notes say nothing about turning it back on.
    - Confidence: H for 0.5.0. That it is still off in 0.5.5 is M; see "Needs an in-game check".
36. **Reforging Bench.** Source: Maxroll, 2026-06-15.
    - Three items of the same base type and rarity, none corrupted, give one unidentified item of that base and rarity at the **lowest item level** among them. Quote: "The item returned when reforging has the Item Level of the lowest Item Level you placed in the Reforging Bench."
    - Uniques: 3 copies of the same unique give a rerolled copy.
    - Waystones: 3 of one tier, any rarity, give one random waystone of the next tier at the lowest rarity among them.
    - Tablets: 3 of the same magic tablet.
    - Jewels: Ruby + Emerald + Sapphire give a Diamond; Diamonds can be reforged since 0.5.2.
    - Relics: 3 of the same relic.
    - Stackables: catalysts, essences ("very small chance" of a Greater), soul cores, distilled emotions (3 of one give 1 of the next tier), and runes (3 Lesser give 1 normal; 3 normal give 1 Greater).
    - Since 0.5.0 there is a bench at the Trial of the Sekhemas entrance.
    - Confidence: M.
37. **Salvage Bench.**
    - Gives 1 Artificer's Shard per socket; 10 shards make an Artificer's Orb. Socketed augments are destroyed.
    - Quality gives quality currency: about 1 per 5% quality, with a chance at an extra one (wiki snippet).
    - Since 0.5.0: "Alternate Quality items (from Breach Catalysts) may now be salvaged to return a portion of the Catalysts used."
    - Confidence: M for sockets; L for the quality amounts.
38. **Genesis Tree (Breach, 0.5.0).** It consumes Wombgifts and Hiveblood to make rings, amulets, belts and currency. It has 6 new ring bases, 4 amulets and 4 belts, all exclusive to it. Confidence: H.
39. **Liquid Emotions (Delirium) on jewels.** Ancient Diluted, Liquid and Potent emotions "Augments a Rare Time-Lost Jewel" by removing a random mod and adding a crafted one (poe2db Jewels). Since 0.4.0, "Waystones can no longer be instilled using Liquid Emotions." Confidence: M–H.
40. **Hinekora's Lock:** "Allows an item to foresee the result of the next Currency item used on it. Modifying the item in any way removes the ability to foresee" (poe2db Currency). Confidence: H.

## 7. Non-equipment classes

41. **Jewels.**
    - Bases: Ruby (`strjewel`), Emerald (`dexjewel`), Sapphire (`intjewel`), Diamond (all three), and Time-Lost Ruby, Emerald, Sapphire and Diamond (radius jewels). From repoe.
    - Normal currency works: Transmutation, Augmentation, Regal, Exalted, Chaos, Annulment. Desecration uses the Preserved Cranium. Liquid Emotions work on Time-Lost jewels.
    - Jewel catalysts exist since 0.5.0. The Vaal Orb has jewel-specific outcomes (fact 29).
    - Limit: 2+2 (fact 2).
    - Confidence: M.
42. **Charms and flasks.** Magic at most (fact 3). Quality via Glassblower's Bauble. The Vaal Orb can push quality to 23%. Charms are `UtilityFlask` class in the data and carry implicits. "The maximum number of Charm slots is capped at 3" (poe2db Charms). Confidence: M.
43. **Relics.** Seven bases (Urn, Amphora, Vase, Seal, Coffer, Tapestry, Incense), used in the Trial of the Sekhemas. Magic at most, 1+1. Reforgeable 3 to 1. Confidence: M.
44. **Waystones.** Tiers 1–16. Chaos Orb omens (Chaotic Rarity, Quantity, Monsters and, since 0.5.0, Effectiveness) "replace all Modifiers on a Waystone with Modifiers that do not grant …"; "Up to 3 of the above Omens may be used simultaneously." Waystones must be identified to run (0.5.0). Confidence: H.
45. **Precursor Tablets.** Max 4 mods, and going past 2 needs the Arbiter of Ash (0.4.0). "You can now use Orbs of Chance on Tablets." (0.5.0) Reforging takes 3 of the same magic tablet. The Ancient Infuser can add a mod past the limit. Tablets carry implicits of the form "Adds X to a Map, 10 uses remaining". Confidence: H.

## 8. Uniques

46. **Orb of Chance:** "Unpredictably either upgrades a Normal item to Unique rarity or destroys it."
    - Omen of Chance: "your next Orb of Chance will not destroy the Item".
    - Omen of the Ancients: "your next Orb of Chance will upgrade the Item to a random Unique of the same Item Class".
    - The odds are not published. Confidence: H for the texts.
47. **Ways to modify a unique:**
    - Divine Orb rerolls its values.
    - Vaal Orb multiplies the values by 0.78–1.22 or adds an enchantment or socket.
    - Vaal Cultivation Orb (fact 30).
    - Reforging 3 of the same unique.
    - Unique Verisium Runeforging (base upgrade, below level 55).
    - Destroying a unique to make a rune (Runes of Aldur).
    - Confidence: M–H.

---

## Conflicts

1. **Bone item-level limit.** Two guides say Preserved bones have "no item level limit". Another implies a limit. Gnawed ≤ 64 is consistent across sources.
2. **Reforging inputs.** A search-result guide says the three inputs must be **unidentified**. Maxroll only says the output is unidentified and states no input rule. Maxroll's page also has inconsistent version labels (0.5.4 in the title, "Updated for 0.5.2" in its changelog).
3. **Sanctify range.** poe2db and the wiki say 78–122%. Mobalytics says 80–120% (older).
4. **One essence mod per item.** Mobalytics states it for 0.5. The official 0.5.0 notes only state one *crafted* modifier and one *desecrated* modifier. Whether essence mods count as "crafted" is not settled.
5. **Recombinator.** The 0.5.0 notes disable it globally. Craft of Exile's weights method relies on recombinators, so its PoE2 weights date from before 0.5 or come from trade data. CoE was updated with "Krakenbul's gathered data" on 2026-09-03, and how that was collected without recombinators is not stated.
6. **Vaal Orb probabilities.** Secondary guides say 4 equal outcomes. Maxroll says the chances are "currently unknown".
7. **Bone naming.** Some guides call them "Ancient Bones"; poe2db uses Gnawed, Preserved and Ancient plus Collarbone, Jawbone, Rib and Cranium.
8. **Charm slot cap.** poe2db says "capped at 3", yet uniques add "+2 Charm Slots" on the same page.
9. **Item classes in the export.** repoe marks Swords, Axes, Daggers and Claws as `released`, but they are not obtainable (0.5.5 bug fix about "Unique Swords, Axes and Daggers").

## Needs an in-game check

1. The jewel affix cap (2+2) and the tablet cap (2+2, or 4 of any split?) on a 0.5.5 client.
2. Whether the Recombinator is still disabled in Standard and Forbidden Rites on 0.5.5.
3. Whether an essence mod counts as the item's single crafted modifier (an essence plus an alloy on one item?).
4. The Well of Souls reveal: number of options (3?), and whether the Ancient bone's minimum level 40 applies to every option.
5. The unidentified "Tier N" thresholds (66/71/76/79 → 11/23/35/48) on 0.5.
6. Whether the reforging inputs must be unidentified.
7. The 80% item-requirement rule from the highest mod level.
8. The Vaal Orb outcome odds per class, Architect's Orb 50/50, and the Corruption Altar 50% destroy.
9. The quality added per scrap or whetstone by rarity, and the salvage yield per quality.
10. The exact item-level threshold of Exceptional items (78?) and how often they drop.
11. Alloy target classes and their mod lists. The poe2db page `/us/Alloys` returned 404; find the right page.
12. Whether mod-group exclusivity holds unchanged in PoE2 (two mods of one group on one item via desecration or essence?).
