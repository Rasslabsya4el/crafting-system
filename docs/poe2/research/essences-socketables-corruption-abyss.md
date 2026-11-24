# PoE2 crafting: essences, socketables (augments), corruption, emotions, desecration, league crafts

- **Checked:** 2026-11-24 (all fetches made that day, between about 22:00 and 23:30 UTC).
- **Patch:** Path of Exile 2 0.5.x ("Return of the Ancients", league "Runes of Aldur"); game data export 0.5.5.10 (RePoE-fork index header "RePoE - PoE2 version 0.5.5.10").
- **Scope:** essences; runes, soul cores, idols, abyssal eyes and other augments; corruption and Vaal currency; liquid emotions and instilling; desecration (Abyss); Expedition/Runeforging, reforging bench, salvage, Breach (Genesis Tree, catalysts), recombinator; Fracturing Orb, Hinekora's Lock. Basic currency orbs and the general omen list belong to a separate note (another agent); omens are named here only where they change one of the mechanics above.

## Sources and their freshness

| Id | Source | URL | Freshness / patch it speaks for |
|---|---|---|---|
| S1 | poe2db, Essence list | https://poe2db.tw/us/Essence | live site, read 2026-11-24; generated from current game files (league badges up to "Runes of Aldur v0.5"); no patch number on the page |
| S2 | poe2db, one page per essence and alloy (95 pages, e.g. Greater Essence of the Body) | https://poe2db.tw/us/Greater_Essence_of_the_Body | same; these pages give class, prefix/suffix and required (modifier) level per class |
| S3 | poe2db, Augment (all socketables) | https://poe2db.tw/us/Augment | same |
| S4 | poe2db, Rune | https://poe2db.tw/us/Rune | same |
| S5 | GGG official 0.5.0 patch notes (forum thread 3932540) | https://www.pathofexile.com/forum/view-thread/3932540 | 0.5.0 (May 2026). Read with WebFetch; a plain `curl` got HTTP 403 and was not retried around |
| S6 | Maxroll, "Corruption Outcomes" | https://maxroll.gg/poe2/resources/corruption-outcomes | updated 2026-05-24, written for 0.4 ("Updated for new corruption outcomes from the 0.4 Fate of the Vaal League") |
| S7 | Maxroll, "Runes and Soul Cores" | https://maxroll.gg/poe2/resources/runes-and-soul-cores | updated 2026-05-21, "Updated in Patch 0.4.0" |
| S8 | poe2db, Abyss and Desecrated Modifiers | https://poe2db.tw/us/Abyss , https://poe2db.tw/us/Desecrated_Modifiers | live, 2026-11-24 |
| S9 | poe2db, Liquid Emotions and Diluted Liquid Ire | https://poe2db.tw/us/Liquid_Emotions , https://poe2db.tw/us/Diluted_Liquid_Ire | live, 2026-11-24 |
| S10 | poe2db, Reforging Bench recipes | https://poe2db.tw/us/Reforging_Bench | live, 2026-11-24 |
| S11 | RePoE-fork PoE2 export 0.5.5.10 (mods, base items) | https://repoe-fork.github.io/poe2/mods.min.json , https://repoe-fork.github.io/poe2/base_items.min.json | 0.5.5.10 |
| S12 | poe2db item pages: Vaal Orb, Vaal Cultivation Orb, Architect's Orb, Crystallised Corruption, Ancient Infuser, Vaal * Infusers, Orb of Extraction, Artificer's Orb/Shard, Fracturing Orb, Hinekora's Lock, Masterwork Rune, Fluxes, Verisium kinds, Crests, Starlit Ores, Omens (Corruption, Light, Abyssal Echoes, Dextral Crystallisation), Catalysts, Wombgifts, Hiveblood, Runeshape Combinations, Recombinator, Salvage Bench | https://poe2db.tw/us/<Item_Name> | live, 2026-11-24 |
| S13 | U4N, "PoE 2 0.5 Vaal temple to core" | https://www.u4n.com/news/poe-2-05-vaal-temple-to-core.html | published 2026-06-03, updated 2026-11-24; a currency-selling site, secondary |
| S14 | Icy Veins / poe-vault, Runes of Aldur league guide | https://www.poe-vault.com/poe2/guides/runes-of-aldur-league-guide | pre-launch 0.5 guide, no date shown; secondary |
| S15 | Web search snippets only (pages not opened): mein-mmo "Bonded Modifiers", poe2wiki "Aldur rune"/"Legacy rune", poe2wiki "Annoint", PC Gamer / Sportskeeda "Well of Souls", Videogamer / Sportskeeda salvage guides | see Conflicts | weakest evidence; marked "low" where used |

**Refused or not used.**
- `www.poe2wiki.net` answered every fetch with an Anubis bot-protection page ("Access Denied", Anubis v1.27.0). Not bypassed. Wiki statements below come only from search snippets (S15) and are marked low confidence.
- `mobalytics.gg` returned HTTP 403 to WebFetch. Not bypassed; nothing from it is used except through search snippets.
- `pathofexile.com/forum` returned 403 to `curl` but answered WebFetch; S5 is that WebFetch read (two passes, offsets 0 and 100000, so the whole thread was read through the model's extraction, not verbatim by me).
- Craft of Exile (PoE2 mode) was not consulted: it is a script page, and the repository's own emulator check (`coe-emulator-check` skill) is the right tool for it.

**How to read a fact.** Each fact gives: the statement; the source id (URL in the table above, or given inline); the patch the source speaks for; confidence (high = current game data or official notes; medium = one current secondary source or data whose meaning I inferred; low = snippet, older patch, or conflicting); a short exact quote where there is one. Quotes from poe2db are game text.

---

## 1. Essences

**1.1 Tiers and what they do.** Lesser, normal and Greater essences turn a **Magic** item into a **Rare** item and add one guaranteed modifier. Perfect essences and the six corrupted essences work on a **Rare** item: they remove one random modifier and add the guaranteed one. S1, S2; 0.5.5.10 data; high.
Quotes: Lesser/normal/Greater: "Upgrades a Magic item to a Rare item, adding a guaranteed modifier"; "Right click this item then left click a Magic item to apply it." Perfect/corrupted: "Removes a random modifier and augments a Rare item with a new guaranteed modifier"; "Right click this item then left click a Rare item to apply it."

**1.2 None of the low three tiers works on a Rare, and none of the Perfect/corrupted works on a Magic item.** Follows from the apply text in 1.1 (S2, high). What happens to the *other* modifiers on a Magic→Rare essence (the item keeps its 1–2 magic mods and gains the essence mod; no extra random mods) is the established PoE2 behaviour but no page I could read states it in words: **medium**, listed under "Needs an in-game check".

**1.3 Family list (19 families) and tiers.** Body (life), Mind (mana), Enhancement (defences), Abrasion (phys), Flames, Ice, Electricity, Ruin (chaos res), Battle (accuracy / attack levels), Sorcery (spell damage / spell levels), Haste (attack speed), the Infinite (attributes), Seeking (crit), Insulation (fire res), Thawing (cold res), Grounding (lightning res), Alacrity (cast speed / mana cost efficiency), Opulence (rarity / gold), Command (allies / aura magnitude). Each has Lesser, normal, Greater and Perfect: 76 essences. Plus 6 corrupted: Hysteria, Delirium, Horror, Insanity, the Abyss, the Breach. Total **82 essences** on poe2db (S1 lists "Essence /95", the extra 13 are Expedition Alloys, §1.10). S1; 0.5.5.10; high.
Conflict noted: the coordinator's count from the trade API is 84; poe2db lists 82. Not resolved (see Conflicts).

**1.4 Guaranteed mod per item class, affix side and modifier level.** Full table in **Appendix A** (130 rows: every essence × class group, with prefix/suffix, the required level of the essence's modifier as poe2db prints it, the essence's drop level, and the first 3-to-1 reforge recipe printed on its page). S2; 0.5.5.10; high.
Pattern (from Appendix A): Lesser mods are level 4–17; normal 30–36; Greater 36–48 (e.g. Greater Body "+(100—119) to maximum Life | Prefix | 43"); Perfect and corrupted mods mostly level 57 (some corrupted mods 4–57: Hysteria helmet minion levels is level 4, Hysteria boots movement speed 52). Corrupted-essence special mods (Delirium, Horror, Insanity, Abyss, Breach) are listed at level 0.

**1.5 What the "required level" means for crafting.** poe2db labels the column "Required Level". For ordinary mods poe2db's equivalent column is the modifier level, which an item needs as item level to roll. Whether an essence refuses an item whose item level is below this number, or applies regardless, no source states. **Medium/unknown**; see "Needs an in-game check".

**1.6 Perfect essences change the item class and the mod compared with the lower tiers.** E.g. Perfect Body is only for Body Armour, "(8—10)% increased maximum Life" (Prefix, level 57); Perfect Mind only Ring "(4—6)% increased maximum Mana"; Perfect Battle "+2 to Level of all Attack Skills" on one-handers/bows and "+3" on two-handers/crossbows; Perfect Sorcery Wand "+3", Staff "+5" to spell skills; Perfect Insulation/Thawing/Grounding give "(26—30)% of <element> Damage taken Recouped as Life" on Belt/Helmet/Gloves. S2; 0.5.5.10; high.
S5 (0.5.0): "The Perfect Essence of Battle now provides +3 to Level of all Attack Skills on Two Hand Melee Weapons or Crossbows" — matches S2.

**1.7 How Perfect/corrupted essences pick the mod to remove.** Random among the item's modifiers ("Removes a random modifier"). Omens restrict the side: **Omen of Dextral Crystallisation** — "your next Perfect or Corrupted Essence will remove only Suffix modifiers"; **Omen of Sinistral Crystallisation** — "...will remove only Prefix modifiers". S12 (https://poe2db.tw/us/Omen_of_Dextral_Crystallisation, https://poe2db.tw/us/Omen); 0.5.5.10; high. Whether the removed mod can be a fractured mod (no, by the usual rule that fractured mods cannot be removed) and what happens when the essence's mod would go on a full side are not stated in any source I could read → "Needs an in-game check".

**1.8 Corrupted essences (exact mods).** S2; 0.5.5.10; high.
- Hysteria: Helmet "+1 to Level of all Minion Skills" (Suffix, 4); Body Armour "(64—97) to (98—145) Physical Thorns damage" (Prefix, 50); Gloves "(25—29)% increased Critical Damage Bonus" (Suffix, 36); Boots "30% increased Movement Speed" (Prefix, 52); Ring "(50—59)% increased Mana Regeneration Rate" (Suffix, 44); Amulet "(19—21)% of Damage taken Recouped as Life" (Suffix, 54); Belt "+(254—304) to Stun Threshold" (Suffix, 57); Shield/Buckler "(20—24)% increased Block chance" (Prefix, 26); Quiver "(43—50)% increased Damage with Bow Skills" (Prefix, 48); Focus "(20—23)% increased Energy Shield Recharge Rate" (Suffix, 52). S5 (0.5.0) confirms the Focus line: "Essence of Hysteria now grants 20-23% increased Energy Shield Recharge Rate when applied to Foci".
- Delirium: Body Armour "Allocates a random Notable Passive Skill" (Prefix).
- Horror: Gloves or Boots "60% increased effect of Socketed Augment Items" (Suffix). RePoE id `EssenceLocalRuneAndSoulCoreEffect1`.
- Insanity: Belt "On Corruption, Item gains two Enchantments" (Suffix). RePoE id `EssenceCorruptForTwoEnchantments1`.
- the Abyss: any equipment, "Mark of the Abyssal Lord", as a Prefix (`EssenceAbyssPrefix`) or a Suffix (`EssenceAbyssSuffix`); text in data: "Bears the Mark of the Abyssal Lord". What the Mark does in crafting (it is understood to interact with desecration) is not stated on any page I could read → "Needs an in-game check".
- the Breach: Ring or Amulet "+20% to Maximum Quality" (Prefix). RePoE id `EssenceBreach`.

**1.9 Making essences: 3-to-1 at the Reforging Bench.** Three Lesser give one normal; three normal give one Greater, for every family (all 19). There is no bench recipe to Perfect and none for corrupted essences. S10 ("X of a Kind Recipe /93", e.g. "Lesser Essence of the Body x3 | Essence of the Body x1", "Essence of the Body x3 | Greater Essence of the Body x1"); 0.5.5.10; high.
Corrupting an essence monster (imprisoned essence) with a Vaal Orb can upgrade essences or turn them into corrupted essences — S6 (0.4): "Change the number of Essences; reroll all to the same type; or upgrade Essences to Greater, then Corrupted (Hysteria, Delirium, Horror, Insanity)" (model's summary of the page, not verbatim); medium. S5 (0.5.0) bug fix: "Fixed a bug where corrupting Essences could sometimes remove the Essence."

**1.10 Expedition Alloys work like Perfect essences.** 13 Alloys (Runic, Adaptive, Protective, Expansive, Swift, Cyclonic, Prismatic, Mystic, Sovereign, Celestial, Transcendent, the Runebinder's, the Runefather's) all read "Removes a random modifier and augments a Rare item with a new guaranteed modifier". Full table **Appendix B** (class, mod, prefix/suffix, level). S1, S2; 0.5.5.10; high. S5 (0.5.0): "Added 13 new Alloy currency items, which can be unlocked through Remnant encounters after completing Farrow's quest in Act 2." Whether the Crystallisation omens also restrict Alloys is not stated (the omen text names only "Perfect or Corrupted Essence") → in-game check.

**1.11 0.5.0 general essence change.** "The overall number of Essences found in the campaign has been increased." S5; 0.5.0; high (drop rates, not mechanics).

## 2. Augments (runes, soul cores, idols, abyssal eyes, other socketables)

**2.1 Augment is the umbrella name; there are five kinds.** "The current types of Augment are: Rune, Soul Core, Idol, Abyssal Eye, Congealed Mist" (poe2db community text). Game text: "Runes are Augments of Kalguuran origin and make."; "Soul Cores are artifacts of the ancient Vaal empire and function as a type of Augment."; "Idols are a type of Augment fashioned by the Azmeri."; "Abyssal Eyes are artifacts recovered from Abyssals which function as a type of Augment."; Congealed Mist: "A mysterious Augment that shifts and shimmers." S3; 0.5.5.10; high. "Idols" were called Talismans before 0.4.0 (S7: "called Talismans prior to 0.4.0"; medium). Today "Talisman" in PoE2 is a two-handed weapon class, not a socketable (S2/S11 list "Talismans" among weapon classes; high).

**2.2 Socketing and removal.** "Augments are items which can be placed into Augment sockets, usually on Equipment items. Once socketed, they can be replaced by other Augments, but cannot be removed by normal means." Each augment states the equipment it fits and the effect there. S3; 0.5.5.10; high. Replacing destroys the old augment (S7: "can only be replaced, which destroys the previous Augment"; 0.4; medium).

**2.3 Socket-bound augments** "permanently fill any Augment Socket they are placed into. Once Socketed, they cannot be removed, replaced or extracted by any means." S3; high. Socket-bound ones in data: the four Aldur runes (Passion/Breath/Ire/Betrayal of Aldur), Serle's Triumph, Cadigan's Epiphany, Uhtred's Sidereus, Kolr's Hunt, Vorana's Carnage, Thrud's Might, Medved's Tending, Katla's Gloom, the four Atziri's Soul Cores, Raven-Touched Shard. (Astrid's Creativity is *not* socket-bound.) S3; high.

**2.4 Orb of Extraction** "Destroys an Equipment item, returning any non Socket-Bound Augments socketed in it". Two base items exist in data (a bench craft and a currency: `CurrencyIncursionExtractAllSocketablesBench`, `...Currency`). S12, S11; high.

**2.5 Adding sockets: Artificer's Orb** "Adds an Augment Socket to a Martial Weapon, wand, staff or Armour" (current item text). An older reference line on the same page still says "a Martial Weapon or Armour", so wands/staves were added at some point (probably 0.5) — current text wins; high. Ten Artificer's Shards make one Orb ("A stack of 10 shards becomes an Artificer's Orb."). S12; high.
Socket caps (S7, 0.4, medium): Body Armour 2, Two-Handed Weapon 2, One-Handed Weapon 1, Helmet 1, Gloves 1, Boots 1; some uniques have more. Not re-confirmed for 0.5 (wands/staves are new to the Artificer's Orb and their cap is not stated anywhere I could read) → in-game check. Jewellery and belts take no augment socket by currency (the Orb's text excludes them); the unique belt Darkness Enthroned has "2 Augment Sockets (Hidden)" (S3).

**2.6 Corruption can add a socket** beyond the normal limit (S6: "+1 Socket (ignoring limit)" for Helmet, Gloves, Boots, Chestpiece, Shield, Focus and Martial Weapons; caster weapons, amulets, belts, rings cannot get one); 0.4; medium. Exceptional items: "Exceptional Items have Quality over maximum or an additional Augment Socket. High Tier Rare Items found have a chance to instead drop as an Exceptional Normal Item." (S3, high). In 0.5 they need an Atlas specialisation (S5: "Some items and content now require you to specialise in them through Atlas Passive Skills including Exceptional Items, Fracturing Orbs"; high).

**2.7 Which classes take what (per-slot effect).** Each rune lists effects for "Martial Weapon", "Wand or Staff" and "Armour" (generic runes), or for one specific slot (named runes, idols, soul cores). Generic tiered runes fit any weapon or armour; most named runes, idols and soul cores fit one or two slot types. Idols: S5 (0.5.0) "All Idols can now also be socketed into Sceptres."; "Idol of Grold now is socketed into Boots."; "Fox Idol now has a limit of 1."; "Stag Idol now has a limit of 1." Full per-slot list: **Appendix C**. S3, S4; high.

**2.8 "Limited to: 1".** Many named runes, soul cores and idols carry "Limited to: 1" (one such augment of that name per character). Ancient Augments (Abyssal Eyes "…'s Gaze", Vaal Theses, Emergent/Carved augments): "You may not have more than one Augment of this type socketed at a time." Aldur's Legacies: "You may not have more than one Augment of this type socketed at a time." S3; high.

**2.9 Bonded modifiers (new in 0.5).** Runes and idols carry a second block "Bonded:". These lines are active only for a character with the Shaman ascendancy passive **Wisdom of the Maji** (poe2wiki snippet: Bonded modifiers "are only active while equipped on a character with this passive"; S15; low), and for idols also inside a Body Armour holding a **Fox Idol** ("Idols socketed in this item gain the benefits of their Bonded modifiers" — S3; high). The generic armour Bonded line of the standard runes is "+20 to maximum Life, +20 to maximum Mana" (S3; S5: "Standard Rune Bonded Modifiers now grant 20 Life and 20 Mana when socketed in Armour items"; high). Bonded lines do not change crafting (they are not item modifiers that occupy affixes) — inference, medium.

**2.10 Rune upgrading.**
- Reforging Bench 3-to-1: Lesser→normal and normal→Greater for Desert, Glacial, Storm, Iron, Body, Mind, Rebirth, Inspiration, Stone, Vision, Robust, Adept, Resolve, Tempered, Ward, Charging. No bench recipe makes a Perfect rune. S10; high. Endgame/named runes cannot be combined (S7, medium).
- **Masterwork Rune**: "All Equipment: Upgrades a socketed Rune"; "Place into an Augment Socket containing any tiered Rune to upgrade that Rune." Tempered runes exist only as Lesser, normal and Greater (no Perfect Tempered Rune in data). S12, S4; high. Whether Masterwork lifts Greater→Perfect, and what it does on a Perfect rune, is not stated → in-game check.
- No "rune combining" other than the 3-to-1 bench and Masterwork exists in data I read.

**2.11 Crafting augments (Kalguuran "crafting Augments" change what can roll).** Game text, S3/S4; 0.5.5.10; high:
- Serle's Triumph (socket-bound): "All Equipment: +1 Suffix Modifier allowed".
- Astrid's Creativity: "All Equipment: Can have 1 additional Crafted Modifiers" (relevant since 0.5: "All crafted modifiers are now guaranteed, but items can only have 1 crafted modifier at a time." — S5).
- Cadigan's Epiphany (socket-bound): "Gloves: Destroys all Augment Sockets on the item to create a Jewel Socket".
- Uhtred's Sidereus / Kolr's Hunt / Vorana's Carnage / Thrud's Might / Medved's Tending / Katla's Gloom (all socket-bound): Boots "Can roll Chronomancy modifiers" / Gloves "Can roll Marksman modifiers" / Helmets "Can roll Berserking modifiers" / Weapon "Can roll Destruction modifiers" / Body Armours "Can roll Soul modifiers" / Gloves "Can roll Decay modifiers". These add a new mod family to the item's pool.
- Aldur runes (socket-bound, weapons): Passion "Transforms all Cold and Lightning modifiers on the item into equivalent Fire modifiers"; Breath (to Cold); Ire (to Lightning); Betrayal "Transforms all Fire, Cold and Lightning modifiers on the item into equivalent Chaos modifiers".
- Aldur's Legacy: "When socketed into a Unique Kalguuran or Ezomyte item, destroys the item to create a Rune imbued with that item's power" — 63 "Legacy of <unique>" runes (Appendix C.7); also a Reforging Bench recipe "Legacy of X = 1x Aldur's Legacy + 1x <unique>" (S10).
- Raven-Touched Shard (Congealed Mist, socket-bound, Helmets): "Raven-Touched"; RePoE base id `AugmentAnoint` (an anoint-like augment) — effect beyond the keyword not given; in-game check.
These are drops/rewards of Runic Remnants ("Runeshape Combinations", S12: e.g. "Serle's Triumph Lv70+", "Medved's Tending Lv70+").

**2.12 Atziri's Soul Cores (socket-bound)**: Helmets/Body/Gloves/Boots "+X per Corrupted Item Equipped", each with "Corrupting will always result in change" — i.e. socketing one makes the next Vaal Orb on that item never give "no change" (inference from wording; same text as Omen of Corruption). S3; high for text, medium for the reading.

**2.13 Counts in Appendix C** (from S3 "Augment Item /313", DNT/unused entries removed): 146 runes and Kalguuran augments (incl. 55 tiered runes of 14 families, 4 Greater "of Leadership/Tithing/Alacrity/Nobility", 21 named Ezomyte/Kalguuran runes, 8 Ward/Charging, 17 Warding runes, 4 Aldur runes, 13 Ancient runes, 13 "Rune of X" (0.5), 9 Kalguuran crafting augments, Masterwork Rune, Aldur's Legacy; 55+4+21+8+17+4+13+13+11 = 146), 63 Aldur's Legacies, 48 soul cores, 31 idols, 4 abyssal eyes, 4 Vaal Theses, 8 Emergent/Carved ancient augments, 1 Congealed Mist. The coordinator's trade count of 213 runes is close to 146+63 = 209 plus a few trade-only entries; not reconciled exactly.

## 3. Corruption

**3.1 Vaal Orb.** "Modifies an item unpredictably and Corrupts it"; "Corrupted items cannot be modified again." poe2db: "Most methods of item crafting and modification cannot be used on Corrupted items." S12; high. Exceptions in 0.4 text: augments can still be socketed and corrupted gems levelled (S6 quote: "You can socket new Runes or Soul cores or level up a Corrupted Skill Gem"; medium).

**3.2 Outcomes by item type** (S6, 0.4, medium; no probabilities in S6 except as noted):
- Rare/Magic gear: nothing happens; 1–3 affixes' values randomised ("Randomizing up to 3 affixes on a Rare item"); a corrupted enchantment (implicit); +1 socket on Helmet, Gloves, Boots, Body, Shield, Focus, Martial weapons ("ignoring limit"); wands and staves gain quality up to 23%.
- Uniques: same, plus "Affixes divined (up to 0.78-1.22 current roll)".
- Jewels (magic/rare): nothing; 1–3 affixes randomised; corrupted enchantment; add or remove an affix "ignoring normal limits". Unique jewels: "No change (50%)", enchantment, or 0.78–1.22× magnitude.
- Waystones: nothing; "+1 Tier/-1 Tier (Min 1, max 16)"; convert all affixes to prefixes or suffixes; add random affixes to a rare waystone.
- Skill gems: nothing; ±1 level; ±1 socket; "-7% to +3% quality".
- Flasks, charms: quality changes up to 23%.
- Essence monsters: see 1.9.
- Probabilities: S6 says the results are "all equally likely" in general; U4N snippets claim 25% per outcome for gems and uniques (S15, low). **No current official probabilities.**
- 0.5.0 change (S5, high): "The Corruption outcome that randomises the numeric values of the modifiers on an item beyond the normal range now multiplies each modifier" — so the S6 "randomised" outcome is now a multiplier on each modifier (range for non-uniques not stated in what I read; in-game check).

**3.3 Corrupted enchantments (implicits).** 114 corruption modifiers with item spawn tags in RePoE 0.5.5.10 (`generation_type: corrupted`); poe2db lists 125 "Corrupted Mods" including monster/relic ones. Full list with the item tags each can roll on: **Appendix D** (S11; high). Examples: body armour "(10-20)% of Damage taken Recouped as Life"; ring/amulet "(10-15)% increased Rarity of Items found"; "+1 to Level of all Skills"; "Bow Attacks fire 1 additional Arrows"; jewels "+(4—6) to Strength" etc.

**3.4 Omen of Corruption** — "your next Vaal Orb will always result in change" (S12; high). In 0.5.0: "Omen of Corruption can no longer be obtained." and it appears on the Currency Exchange only in Standard (S5; high). So in the current league it is not a usable step for a new route except with old stock in Standard.

**3.5 Double corruption: Architect's Orb** — "Modifies a Corrupted Equipment or Jewel item unpredictably or destroys it" (S12; high); S6 (0.4): "has a 50/50 chance to add a second Enchantment"; on failure "the item being destroyed" (medium). **Crystallised Corruption** — "Modifies a Corrupted Skill Gem unpredictably or destroys it" (S12); "50/50 chance to destroy the gem" (S6; medium). **Essence of Insanity** belt mod gives "two Enchantments" on corruption (1.8).

**3.6 Vaal Cultivation Orb** — "Replaces up to 2 modifiers on a Corrupted Vaal Unique"; "Replaces other Uniques with a Corrupted Unique of the same Item Class" (S12; high). Outcome tables changed in 0.5.0 ("Some of the possible outcomes from applying to Vaal Cultivation Orbs to Unique Items have been updated", S5). poe2db lists "Cultivated Uniques /48", "Cultivated Mods /198".

**3.7 Vaal Infusers (four kinds, 0.5).** Arcanist's (wand, staff, sceptre), Armourer's (armour), Blacksmith's (martial weapon), Catalysing (ring or amulet): "Improves the quality of a <class>, exceeding maximum quality by up to 10% with a chance of Corrupting it"; "Can only be used on items at or above maximum quality." S12; high. S13: "existing Vaal Infusers are now Vaal Armourer's Infusers"; "All Infusers can only be used on items at or above 20% Quality" (medium). The chance of corruption per use is not given anywhere I read.

**3.8 Ancient Infuser (tablets)** — "Modifies a Tablet unpredictably and Corrupts it" (S12; high). Outcomes (S6, 0.4): add a random modifier, add up to 10 uses, change the tablet type, or destroy it (medium).

**3.9 Temple of Atziri / Vaal temple** is core in 0.5 (S13 and Mobalytics snippet: "In patch 0.5, the Fate of the Vaal league mechanic will now be a part of the core game"; medium). It is the source of the Vaal crafting currency above; the item-crafting functions of its rooms in 0.5 were not described by any source I could open → in-game check.

## 4. Liquid (Distilled) emotions and instilling

**4.1 Name.** PoE2 now calls them **Liquid Emotions** (base class `DistilledEmotion`; older name "Distilled Emotions"). "Liquid Emotions are Currency items that are exclusive drops from the Delirium mechanic. Liquid Emotions allow you to instil an amulet with a Notable Passive Skill from the Passive Tree. Instilling a Notable Passive Skill which you have already allocated normally will not grant its effects a second time." S9; high.

**4.2 Instilling amulets (anoint).** Done at **The Withered Willow**: "Can be used at The Withered Willow to Instil Amulets with a Notable Passive Skill." Each notable has a recipe of three emotions (e.g. "Insulated Treads — Liquid Emotions: Ire, Ire, Ire"); 875 notables can be instilled, 17 only by emotions (e.g. "Zarokh's Gift — Sinister Jewel Socket", "Augmented Flesh — Grants 2 additional Skill Slots"). Strugglescream (unique amulet): "Can have 3 additional Instilled Modifiers". S9; high. Instilled mod is an enchant-like extra; whether re-instilling replaces it and whether it is allowed on corrupted amulets: not stated → in-game check.

**4.3 Emotions as jewel crafts (new in 0.5).** Every emotion now also reads "Removes a random modifer and Augments a Rare Basic Jewel with a new guaranteed Crafted modifier", with a different mod per jewel type (Ruby/Sapphire/Emerald, and Diamond for Isolation). "Ancient" emotions do the same on **Time-Lost** jewels. S9; high. S5 (0.5.0): "Liquid Emotions can now be used to craft additional mods on Jewels." Because the added mod is a *crafted* mod, the 0.5 rule "items can only have 1 crafted modifier at a time" (S5) applies (inference; medium). Full list of the 27 emotions with their jewel mods: **Appendix E**.

**4.4 Emotion tiers.** Diluted Ire < Diluted Guilt < Diluted Greed < Paranoia < Envy < Disgust < Despair < Concentrated Fear < Concentrated Suffering < Concentrated Isolation (10 core), plus 3 Potent (Melancholy, Ferocity, Contempt) from Delirious map bosses (S5: "Map bosses of Delirious Maps can additionally drop a new set of 3 Potent emotions"), plus the Ancient versions of all 13 (S5: "There is new set of 10 Ancient Emotions that can drop if unlocked by the Atlas Tree"; S9 lists 13 Ancient incl. 3 Ancient Potent). 3-to-1 at the Reforging Bench along the 10-step chain (S10: "Diluted Liquid Ire x3 | Diluted Liquid Guilt x1" … "Concentrated Liquid Suffering x3 | Concentrated Liquid Isolation x1"); no bench recipe for Potent or Ancient. High.
Notable jewel crafts: Potent Liquid Contempt — "+1 Suffix Modifier allowed" (on a prefix slot) or "+1 Prefix Modifier allowed" (on a suffix slot); Potent Liquid Ferocity — "(40—60)% increased Effect of Suffixes/Prefixes"; Ancient Potent Liquid Melancholy — "Upgrades Radius to Very Large". S9; high.

**4.5 Emotions on waystones.** The first lines of each emotion ("Players in Area are 7% Delirious", "20% increased Magic Monsters") are what it adds to a waystone (up to three per waystone, per search snippets of poe2wiki/kimuraa; S15; low–medium). Values per emotion are in Appendix E (game text, high). Tablets: no emotion use found in data.

**4.6 Liquid Verisium** is filed with emotions on poe2db but is an Expedition item: "Immediately start a Runic Remnant Encounter with a random Runic Inscription". S12; high. Not a crafting currency.

## 5. Desecration (Abyss)

**5.1 Mechanic.** "Desecrating an item adds an Unrevealed Desecrated modifier. If modifiers are full then a random modifier is also removed. These modifiers can be revealed at the Well of Souls. Items with Desecrated Modifiers cannot be Desecrated again." S8; high.

**5.2 0.5.0 changes.** "Desecrated modifiers no longer count as crafted modifiers, but items are limited to 1 Desecrated modifier." "Desecrated Modifiers granting Instant Leech can no longer roll" S5; high. (So since 0.5 a desecrated mod and a crafted mod can coexist; before, they shared the crafted limit.)

**5.3 Bones (the desecration currencies).** S8, S12; 0.5.5.10; high:

| Bone | Targets | Restriction |
|---|---|---|
| Gnawed Jawbone | Rare Weapon or Quiver | "Maximum Item Level: 64" |
| Preserved Jawbone | Rare Weapon or Quiver | none stated |
| Ancient Jawbone | Rare Weapon or Quiver | "Minimum Modifier Level: 40" |
| Gnawed Rib | Rare Armour | "Maximum Item Level: 64" |
| Preserved Rib | Rare Armour | none |
| Ancient Rib | Rare Armour | "Minimum Modifier Level: 40" |
| Gnawed Collarbone | Rare Amulet, Ring or Belt | "Maximum Item Level: 64" |
| Preserved Collarbone | Rare Amulet, Ring or Belt | none |
| Ancient Collarbone | Rare Amulet, Ring or Belt | "Minimum Modifier Level: 40" |
| Altered Collarbone | Rare Amulet, Ring or Belt | "with a chance for otherworldly modifiers" (poe2db: Otherworldly Amulet 4 / Ring 16 / Belt 16 mods) |
| Preserved Cranium | Rare Jewel | none |
| Preserved Vertebrae | Rare Waystone | none |

All stack to 20. The coordinator's "Gnawed/Preserved/Ancient" set matches.

**5.4 Well of Souls reveal.** Choose 1 of 3 offered modifiers (S15 snippets: PC Gamer/Sportskeeda/Game8 "pick from three offered modifiers"; low–medium; no game text found). poe2db note: "Reveal desecrated modifiers may include base modifiers. Unless you use Omen to guarantee named modifiers." (S8, poe2db community text, medium). Location: Act 2 (Mastodon Badlands per snippet; low).

**5.5 Desecration omens** (S8, S12; high; text exact):
- Omen of Abyssal Echoes: "the next time you reveal Desecrated modifiers you can reroll the options once".
- Omen of the Sovereign / the Liege / the Blackblooded: "your next Weapon or Jewellery Desecration attempt will guarantee a random Ulaman / Amanamu / Kurgal modifier" (weapon or jewellery only).
- Omen of Sinistral / Dextral Necromancy: next desecration "will add only prefix / suffix modifiers".
- Omen of Putrefaction: next desecration "will replace all modifiers on the item creating an item with up to 6 Unrevealed modifiers and Corrupting the item".
- Omen of Light: "your next Orb of Annulment will remove only Desecrated modifiers".
- 0.5.0: "Abyss Omens no longer drop in areas below level 65." (S5).

**5.6 Named desecrated modifiers.** poe2db "Desecrated Mods /198" (S8): Amanamu's 26 prefixes, Kurgal's 23 prefixes, Ulaman's 22 prefixes, "of Amanamu" 44 suffixes, "of Kurgal" 39 suffixes, "of Ulaman" 44 suffixes; every one at level **65**. Jewels: 29 "Lightless" prefixes + 3 "of the Abyss" suffixes at level 1. Waystones: 19 "Abyssal" mods. Notes (poe2db community text): "Body Armour, Gloves, Boots and Helmet do not have Prefix desecrated modifiers." "Sceptres do not have exclusive desecrated modifiers." "Jewel exclusive modifiers only roll on regular jewels, not Time-Lost jewels." RePoE 0.5.5.10 has 147 desecrated prefixes and 175 suffixes and 93 unique ones (S11). Full named list: **Appendix F**. Level 65 is printed as the mod level; whether that is a minimum item level for the named mods to be offered is not stated → in-game check.

**5.7 Item level limits.** Gnawed bones only on items of item level ≤64; Ancient bones force a modifier level ≥40; named mods are level 65 (5.3, 5.6). High for the text; the interaction (Ancient + named) is not stated.

**5.8 Abyssal Eyes (augments from Abyss)**: Amanamu's, Tecrod's, Kurgal's, Ulaman's Gaze, each an Ancient Augment for helmets/body/gloves/boots (Appendix C.4). S3; high.

## 6. League crafting in the core game: Expedition 0.5, reforging bench, salvage, Breach, recombinator

**6.1 Recombinator: disabled in 0.5.** "The Recombinator has been disabled. The Omen of Recombination has been removed." and "/reclaimexpeditioninventories" returns items "including those of the Recombinator and Expedition Vendors". S5; 0.5.0; high. poe2db's Recombinator page marks "Path of Exile 2: 0" (S12). **Not a crafting method in 0.5.**

**6.2 Expedition in 0.5 = Runic Remnants + Verisium Runeforging.** S5 (0.5.0; high): "New Crafting System: Verisium Runeforging"; "After unlocking Verisum Runeforging in Act 1 this system allows you to add Runic Ward to your armours by spending verisium."; "After unlocking Unique Verisium Runeforging in Act 3 you can upgrade the base type of Unique Weapons and Armours"; "Monsters raised by Remnants can drop Verisium metal, a new currency." Runeforging is done at the **Verisium Anvil** (hideout object `HideoutVerisiumCraftingBench`; S12). poe2db lists "Runeforging /409" (normal bases) and "Unique Runeforging /309" (S12).
- Normal runeforging: base → "Runeforged <base>" with lower defences and Runic Ward, cost "<base>, Verisium xN" (e.g. "Runeforged Iron Cuirass … Armour: 115 … Runic Ward: 43 … Cost: Iron Cuirass, Verisium x30"). Some cost **Exceptional Verisium**. S12; high. What happens to the item's modifiers is not stated (the recipe lists only the base) → in-game check.
- Unique runeforging: unique → "Runeforged" → "Runemastered" versions, cost Verisium plus one **Crest**: Medved's Crest of the Circle, Vorana's Crest of the Scythe, Uhtred's Crest of the Chalice, Olroth's Crest of the Sun ("Can be used at the Verisium Anvil to transform Unique items."). E.g. "Runeforged Morning Star — Cost: Brutus' Lead Sprinkler Morning Star, Exceptional Verisium x3, Uhtred's Crest of the Chalice x1". S12; high.
- **Starlit Ore** (Starlit, Revered, Venerable, Veridical, Warding): "Can be used at the Verisium Anvil to forge a new Unique item." — each makes one named unique (Serle's Grit, The Unleashed, Eyes of the Runefather, Eventide Petals, Duality). S12; high.
- **Verisium kinds** in data (S11): Verisium, Exceptional Verisium, Mutated Verisium, Corrupted Verisium, Founders Verisium, Liquid Verisium. poe2db marks **Mutated, Corrupted and Founders Verisium "Acquisition: Not in game"** (S12; high) — present in files, not obtainable now.
- **Fluxes**: Blazing / Chilling / Crackling / Void Flux: "Transforms all Cold and Lightning Resistance modifiers on an item to equivalent Fire Resistance modifiers" (Blazing; Chilling→Cold, Crackling→Lightning; Void: "all Fire, Cold and Lightning Resistance modifiers … to equivalent Chaos resistance modifiers"), on "a magic or rare item". **Perfect Flux**: "Upgrades the Skills on an item to Level 20". **Thaumaturgic Flux (Level 1…20)**: 20 items, base ids `CurrencySetKalguuranSkillGemLevelN` (sets a Kalguuran skill gem to level N; inference from id). S12, S11; high for text, medium for Thaumaturgic.
- All of the above are Remnant rewards ("Runeshape Combinations /322": Alloys 14, Currency 93, Gems 61, Runes 131, Uniques 23; e.g. "Hinekora's Lock Lv70+", "Mirror of Kalandra Lv70+", "Perfect Flux Lv70+"). S12; high.
- Kalguuran skills/supports: S5 "Added 23 Kalguuran Skills that can be crafted from Remnants" and "Added 7 Kalguuran Supports that can be crafted from remnants".
- Runic Ward and Kalguuran skills: S14 (secondary): runeforged armour "has its base defenses reduced and gains Runic Ward"; "Runic Ward is consumed AFTER your Life is depleted" (medium).

**6.3 Reforging Bench.** Recipes on poe2db (S10; high): "Forge Recipe /93", "Equip Recipe /68", "Gem Recipe /2", "Unique Item Recipe /2", "X of a Kind Recipe /93". X-of-a-kind: 3 runes/essences/emotions/waystones of one tier → 1 of the next (sections 1.9, 2.10, 4.4; waystones T1→T15). Equip recipes include "Pearlescent Amulet = Jade + Amber + Lapis Amulet", "Diamond = Ruby + Emerald + Sapphire", "Time-Lost Diamond = Time-Lost Ruby + Emerald + Sapphire", the 63 Legacy runes, "Grasping Mail Item (rare, unidentified) = 60x Breach Ring" (at the Genesis Tree). S5 (0.5.0): "Added a Reforging Bench to the entrance of the Trial of the Sekhemas." The classic "3 same-base items → 1" reforge of gear (the coordinator's "3 items → 1") is **not** in the 0.5 recipe list I read; the 3-to-1 recipes are for stackables and waystones. Medium (poe2db may omit the generic rule) → in-game check.

**6.4 Salvage Bench.** Hideout object `HideoutTransmutationBench` (S12). Mechanics from secondary sources (S15/S7; medium): salvaging gear with quality gives quality currency (armour/off-hand → Armourer's Scrap, martial weapons → Blacksmith's Whetstone, wands/staves/sceptres → Arcanist's Etcher), and "Every Socketed item Salvaged and destroyed at this bench awards an Artificer's Shard" (S7). Socketed augments are destroyed when salvaged (poe2wiki snippet; low). 0.5.0: "Alternate Quality items (from Breach Catalysts) may now be salvaged to return a portion of the Catalysts used." (S5; high).

**6.5 Breach crafting (Genesis Tree, catalysts).** S5 (0.5.0; high): "The Genesis Tree allows consuming of Wombgifts and Hiveblood to create Rings, Amulets, Belts and Currency."; "Catalysts can no longer drop from Monsters, these are now solely obtained from the Genesis Tree." Wombgifts (S12; high): Lavish → currency, Ornate → amulet, Banded → belt, Signet → ring, Revelatory → Breachstone ("Can grow into a <x> on the Genesis Tree"; "Requires # Hiveblood"); Hiveblood max 100,000, Genesis Tree in the Monastery of the Keepers. Catalysts (S12; high): 13 for rings/amulets (Flesh=Life, Neural=Mana, Carapace=Armour/Evasion/ES, Uul-Netol's=Physical, Xoph's=Fire, Tul's=Cold, Esh's=Lightning, Chayula's=Chaos, Reaver=Attack, Sibilant=Caster, Skittering=Speed, Adaptive=Attribute, Necrotic=Minion) and 13 "Refined" versions for jewels; each "Adds quality that enhances <type> modifiers on a ring or amulet / on a jewel"; "Replaces other quality types". **Omen of Catalysing Exaltation**: "your next Exalted Orb will consume all Catalyst Quality to increase the chance of the corresponding type of Modifier". Essence of the Breach raises max quality of jewellery to +20% (1.8), and Vaal Catalysing Infuser exceeds jewellery max quality by up to 10% (3.7).

**6.6 Ritual and other league crafts.** Not part of this note's scope beyond what touches the mechanics above (Ritual omens are in the omen note).

## 7. Fracturing Orb and Hinekora's Lock

**7.1 Fracturing Orb**: "Fracture a random modifier on a rare item with at least 4 modifiers, locking it in place."; "Cannot be used on Fractured items." S12; 0.5.5.10; high. Fracturing Shards exist (`CurrencyFractureRareShard`, S11). 0.5.0: Fracturing Orbs now need Atlas specialisation to obtain (S5 quote in 2.6). How a fractured mod acts (cannot be removed or changed by currency; counts toward its affix side) is the general rule but not worded on any page I read → in-game check of edge cases (Perfect essence / desecration removal, Chaos Orb).

**7.2 Hinekora's Lock**: "Allows an item to foresee the result of the next Currency item used on it"; "Modifying the item in any way removes the ability to foresee". Drop level 46; also a Runic Remnant reward ("Hinekora's Lock Lv70+"). S12; 0.5.5.10; high. Tracking items count it (S5: the Tracking Scroll of Crafting now tracks "Hinekora's Lock and Fracturing Orb items").

---

## Conflicts

1. **Essence count**: poe2db lists 82 essences (19×4 + 6); the trade API static list (per the coordinator) has 84. Unresolved; maybe trade lists two extra entries (e.g. old names). Low impact.
2. **Bonded activation**: poe2wiki snippet says Bonded mods are active only with the Shaman passive Wisdom of the Maji; mein-mmo says you need a Druid ascendancy node. Consistent if Shaman is the Druid ascendancy that holds it; game text only confirms Fox Idol for idols. Unverified.
3. **Lady Hestra's Rune of Winter**: 0.5.0 notes "no longer grants Adds 19 to 28 Cold Damage", but current poe2db text is "Martial Weapon: Adds 19 to 28 Cold Damage against Chilled Enemies". Likely the unconditional line became conditional (notes truncated by the reader), but not confirmed.
4. **Artificer's Orb targets**: current text "Martial Weapon, wand, staff or Armour" vs. older poe2db reference line "Martial Weapon or Armour" and S7 (0.4). Current text taken. Socket caps (S7, 0.4) not re-checked for 0.5; wand/staff cap unknown.
5. **Vaal Orb value outcome**: S6 (0.4) "randomised (1–3 affixes)" vs. 0.5.0 notes "now multiplies each modifier". The 0.5 wording wins; its range for non-uniques is unknown.
6. **Vaal probabilities**: S6 "all equally likely", U4N "25% each" for gems/uniques, S6 "No change (50%)" for unique jewels. No official numbers.
7. **Omen of Corruption**: exists in 0.5 data and on poe2db, but 0.5.0 notes say it "can no longer be obtained" and trades only in Standard.
8. **Desecrated mod limit**: 0.5.0 "limited to 1 Desecrated modifier" vs. Omen of Putrefaction ("up to 6 Unrevealed modifiers") and uniques that "Can gain 1–4 custom Desecrated Modifiers" — exceptions by explicit text; how Putrefaction squares with the 1-limit is untested.
9. **Emotion waystone values**: snippets disagree (e.g. Greed 10% vs 15% Delirious). Game text on poe2db (Appendix E) is the one to use: Diluted Liquid Greed "Players in Area are 10% Delirious".
10. **Reforging bench "3 items → 1"**: not in the 0.5 poe2db recipe list for gear; may be a PoE1/0.1 memory or a rule poe2db does not list.
11. **Essence of the Body tiers**: normal tier lists Ring among the smaller-life classes, Greater does not (Amulet/Boots/Gloves only). Data, not a conflict between sources, but a trap for a planner that assumes tiers share classes.

## Needs an in-game check

1. Magic→Rare essence: are the existing magic mods kept and is exactly one mod (the essence mod) added? What if the essence mod's side is full?
2. Does an essence apply to an item whose item level is below the essence mod's printed level (e.g. Greater Body level 43 on an ilvl 30 helmet)? Same for Perfect (57) and Alloys.
3. Perfect/corrupted essences and Alloys: can the random removal hit a fractured mod? With Dextral/Sinistral Crystallisation, if no mod of that side exists, what happens? Do the Crystallisation omens work on Alloys?
4. Mark of the Abyssal Lord (Essence of the Abyss): what it does to desecration/reveal.
5. Bonded modifiers: exact activation condition (Wisdom of the Maji only? Fox Idol for idols?).
6. Masterwork Rune: Greater→Perfect? Effect on a Perfect rune or on Tempered (no Perfect tier)?
7. Augment socket caps in 0.5 per slot, including the new wand/staff use of Artificer's Orb.
8. Vaal Orb 0.5 outcome list and probabilities on rare gear, uniques, jewels, waystones, gems; the multiplier range of the value outcome.
9. Architect's Orb, Vaal Infusers: chance of success/corruption.
10. Raven-Touched Shard: what "Raven-Touched" does (base id `AugmentAnoint`).
11. Instilling: allowed on corrupted amulets? Replaces an existing instil?
12. Emotion jewel craft: does it count against the 1-crafted-mod limit; can it hit a full item (it removes a random mod first)?
13. Well of Souls: confirm 1-of-3 choice in 0.5; whether named (level 65) mods need item level 65.
14. Runeforging a rare/magic armour: are its modifiers kept? Can a runeforged item still be crafted normally?
15. Reforging Bench: any gear-for-gear 3-to-1 recipe in 0.5?
16. Fracturing Orb interaction with Perfect essences, desecration removal ("If modifiers are full then a random modifier is also removed") and Chaos Orb.

---

## Appendix A. Essences: guaranteed mod per class (82 essences, 130 rows)

Source S2 (one poe2db page per essence), 0.5.5.10. Columns: essence; item classes as poe2db names them; modifier; affix side; "Required Level" printed for the modifier; the essence's drop level; the first 3-to-1 recipe printed on the page (a Lesser page shows the recipe it feeds, a normal or Greater page the one that makes it; Perfect, corrupted and Alloy pages show none).

| Essence | Classes | Modifier | Side | Mod level | Drop level | 3-to-1 recipe on page |
|---|---|---|---|---|---|---|
| Lesser Essence of the Body | Helmets, Body Armours, Gloves, Boots, Shields, Belts, Bucklers, Foci | +(30—39) to maximum Life | Prefix | 12 | 25 |  Lesser Essence of the Body x3 -> Essence of the Body x1 |
| Lesser Essence of the Body | Rings, Amulets | +(20—29) to maximum Life | Prefix | 4 | 25 |  Lesser Essence of the Body x3 -> Essence of the Body x1 |
| Lesser Essence of the Mind | Belts, Boots, Gloves, Helmets, Amulets, Rings | +(25—34) to maximum Mana | Prefix | 12 | 25 |  Lesser Essence of the Mind x3 -> Essence of the Mind x1 |
| Lesser Essence of Enhancement | Helmets, Body Armours, Gloves, Boots, Shields, Bucklers, Foci | (27—42)% increased Armour, Evasion and Energy Shield | Prefix | 12 | 20 |  Lesser Essence of Enhancement x3 -> Essence of Enhancement x1 |
| Lesser Essence of Abrasion | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Adds (4—6) to (7—11) Physical Damage | Prefix | 6 | 25 |  Lesser Essence of Abrasion x3 -> Essence of Abrasion x1 |
| Lesser Essence of Abrasion | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Adds (5—8) to (10—15) Physical Damage | Prefix | 6 | 25 |  Lesser Essence of Abrasion x3 -> Essence of Abrasion x1 |
| Lesser Essence of Flames | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Adds (4—6) to (7—10) Fire Damage | Prefix | 6 | 25 |  Lesser Essence of Flames x3 -> Essence of Flames x1 |
| Lesser Essence of Flames | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Adds (6—9) to (10—16) Fire Damage | Prefix | 6 | 25 |  Lesser Essence of Flames x3 -> Essence of Flames x1 |
| Lesser Essence of Ice | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Adds (3—5) to (6—9) Cold Damage | Prefix | 6 | 25 |  Lesser Essence of Ice x3 -> Essence of Ice x1 |
| Lesser Essence of Ice | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Adds (5—8) to (9—14) Cold Damage | Prefix | 6 | 25 |  Lesser Essence of Ice x3 -> Essence of Ice x1 |
| Lesser Essence of Electricity | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Adds 1 to (13—19) Lightning Damage | Prefix | 6 | 25 |  Lesser Essence of Electricity x3 -> Essence of Electricity x1 |
| Lesser Essence of Electricity | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Adds (1—2) to (19—27) Lightning Damage | Prefix | 6 | 25 |  Lesser Essence of Electricity x3 -> Essence of Electricity x1 |
| Lesser Essence of Ruin | Helmets, Body Armours, Gloves, Boots, Shields, Rings, Amulets, Belts, Bucklers, Foci | +(4—7)% to Chaos Resistance | Suffix | 12 | 25 |  Lesser Essence of Ruin x3 -> Essence of Ruin x1 |
| Lesser Essence of Battle | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Bows, Quarterstaves, Daggers, Crossbows, Flails, Talismans | +(61—84) to Accuracy Rating | Prefix | 14 | 20 |  Lesser Essence of Battle x3 -> Essence of Battle x1 |
| Lesser Essence of Sorcery | Foci, Wands | (35—44)% increased Spell Damage | Prefix | 6 | 20 |  Lesser Essence of Sorcery x3 -> Essence of Sorcery x1 |
| Lesser Essence of Sorcery | Staves | (69—88)% increased Spell Damage | Prefix | 6 | 20 |  Lesser Essence of Sorcery x3 -> Essence of Sorcery x1 |
| Lesser Essence of Haste | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Quarterstaves, Daggers, Flails, Talismans | (11—13)% increased Attack Speed | Suffix | 17 | 25 |  Lesser Essence of Haste x3 -> Essence of Haste x1 |
| Lesser Essence of Haste | Bows, Crossbows | (8—10)% increased Attack Speed | Suffix | 8 | 25 |  Lesser Essence of Haste x3 -> Essence of Haste x1 |
| Lesser Essence of the Infinite | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Bows, Quarterstaves, Daggers, Helmets, Body Armours, Gloves, Boots, Shields, Staves, Wands, Sceptres, Rings, Amulets, Belts, Quivers, Crossbows, Flails, Talismans, Foci, Bucklers | +(9—12) to Strength, Dexterity or Intelligence | Suffix | 8 | 20 |  Lesser Essence of the Infinite x3 -> Essence of the Infinite x1 |
| Essence of the Body | Belts, Body Armours, Helmets, Shields, Bucklers | +(85—99) to maximum Life | Prefix | 36 | 40 |  Lesser Essence of the Body x3 -> Essence of the Body x1 |
| Essence of the Body | Amulets, Boots, Gloves, Rings | +(70—84) to maximum Life | Prefix | 30 | 40 |  Lesser Essence of the Body x3 -> Essence of the Body x1 |
| Essence of the Mind | Boots, Gloves, Helmets, Belts | +(65—79) to maximum Mana | Prefix | 30 | 40 |  Lesser Essence of the Mind x3 -> Essence of the Mind x1 |
| Essence of the Mind | Rings, Amulets | +(80—89) to maximum Mana | Prefix | 36 | 40 |  Lesser Essence of the Mind x3 -> Essence of the Mind x1 |
| Essence of Enhancement | Helmets, Body Armours, Gloves, Boots, Shields, Bucklers, Foci | (56—67)% increased Armour, Evasion and Energy Shield | Prefix | 36 | 40 |  Lesser Essence of Enhancement x3 -> Essence of Enhancement x1 |
| Essence of Abrasion | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Adds (10—15) to (18—26) Physical Damage | Prefix | 36 | 40 |  Lesser Essence of Abrasion x3 -> Essence of Abrasion x1 |
| Essence of Abrasion | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Adds (14—21) to (25—37) Physical Damage | Prefix | 36 | 40 |  Lesser Essence of Abrasion x3 -> Essence of Abrasion x1 |
| Essence of Flames | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Adds (20—24) to (32—37) Fire Damage | Prefix | 36 | 40 |  Lesser Essence of Flames x3 -> Essence of Flames x1 |
| Essence of Flames | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Adds (30—37) to (45—56) Fire Damage | Prefix | 36 | 40 |  Lesser Essence of Flames x3 -> Essence of Flames x1 |
| Essence of Ice | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Adds (17—20) to (26—32) Cold Damage | Prefix | 36 | 40 |  Lesser Essence of Ice x3 -> Essence of Ice x1 |
| Essence of Ice | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Adds (25—30) to (38—46) Cold Damage | Prefix | 36 | 40 |  Lesser Essence of Ice x3 -> Essence of Ice x1 |
| Essence of Electricity | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Adds (1—3) to (55—60) Lightning Damage | Prefix | 36 | 40 |  Lesser Essence of Electricity x3 -> Essence of Electricity x1 |
| Essence of Electricity | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Adds (1—4) to (80—88) Lightning Damage | Prefix | 36 | 40 |  Lesser Essence of Electricity x3 -> Essence of Electricity x1 |
| Essence of Ruin | Helmets, Body Armours, Gloves, Boots, Shields, Rings, Amulets, Belts, Bucklers, Foci | +(8—11)% to Chaos Resistance | Suffix | 24 | 40 |  Lesser Essence of Ruin x3 -> Essence of Ruin x1 |
| Essence of Battle | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Bows, Quarterstaves, Daggers, Crossbows, Flails, Talismans | +(124—167) to Accuracy Rating | Prefix | 28 | 40 |  Lesser Essence of Battle x3 -> Essence of Battle x1 |
| Essence of Sorcery | Foci, Wands | (55—64)% increased Spell Damage | Prefix | 26 | 40 |  Lesser Essence of Sorcery x3 -> Essence of Sorcery x1 |
| Essence of Sorcery | Staves | (109—128)% increased Spell Damage | Prefix | 26 | 40 |  Lesser Essence of Sorcery x3 -> Essence of Sorcery x1 |
| Essence of Haste | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Quarterstaves, Daggers, Flails, Talismans | (17—19)% increased Attack Speed | Suffix | 29 | 40 |  Lesser Essence of Haste x3 -> Essence of Haste x1 |
| Essence of Haste | Bows, Crossbows | (11—13)% increased Attack Speed | Suffix | 17 | 40 |  Lesser Essence of Haste x3 -> Essence of Haste x1 |
| Essence of the Infinite | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Bows, Quarterstaves, Daggers, Helmets, Body Armours, Gloves, Boots, Shields, Staves, Wands, Sceptres, Rings, Amulets, Belts, Quivers, Crossbows, Flails, Talismans, Foci, Bucklers | +(17—20) to Strength, Dexterity or Intelligence | Suffix | 26 | 40 |  Lesser Essence of the Infinite x3 -> Essence of the Infinite x1 |
| Greater Essence of the Body | Belts, Body Armours, Helmets, Shields, Bucklers | +(100—119) to maximum Life | Prefix | 43 | 60 |  Essence of the Body x3 -> Greater Essence of the Body x1 |
| Greater Essence of the Body | Amulets, Boots, Gloves | +(85—99) to maximum Life | Prefix | 36 | 60 |  Essence of the Body x3 -> Greater Essence of the Body x1 |
| Greater Essence of the Mind | Boots, Gloves, Helmets, Belts | +(80—89) to maximum Mana | Prefix | 36 | 60 |  Essence of the Mind x3 -> Greater Essence of the Mind x1 |
| Greater Essence of the Mind | Rings, Amulets | +(90—104) to maximum Mana | Prefix | 43 | 60 |  Essence of the Mind x3 -> Greater Essence of the Mind x1 |
| Greater Essence of Enhancement | Helmets, Body Armours, Gloves, Boots, Shields, Bucklers, Foci | (68—79)% increased Armour, Evasion and Energy Shield | Prefix | 43 | 60 |  Essence of Enhancement x3 -> Greater Essence of Enhancement x1 |
| Greater Essence of Abrasion | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Adds (16—24) to (28—42) Physical Damage | Prefix | 48 | 60 |  Essence of Abrasion x3 -> Greater Essence of Abrasion x1 |
| Greater Essence of Abrasion | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Adds (23—35) to (39—59) Physical Damage | Prefix | 48 | 60 |  Essence of Abrasion x3 -> Greater Essence of Abrasion x1 |
| Greater Essence of Flames | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Adds (35—44) to (56—71) Fire Damage | Prefix | 48 | 60 |  Essence of Flames x3 -> Greater Essence of Flames x1 |
| Greater Essence of Flames | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Adds (56—70) to (84—107) Fire Damage | Prefix | 48 | 60 |  Essence of Flames x3 -> Greater Essence of Flames x1 |
| Greater Essence of Ice | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Adds (31—38) to (47—59) Cold Damage | Prefix | 48 | 60 |  Essence of Ice x3 -> Greater Essence of Ice x1 |
| Greater Essence of Ice | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Adds (46—57) to (70—88) Cold Damage | Prefix | 48 | 60 |  Essence of Ice x3 -> Greater Essence of Ice x1 |
| Greater Essence of Electricity | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Adds (1—6) to (85—107) Lightning Damage | Prefix | 48 | 60 |  Essence of Electricity x3 -> Greater Essence of Electricity x1 |
| Greater Essence of Electricity | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Adds (1—8) to (128—162) Lightning Damage | Prefix | 48 | 60 |  Essence of Electricity x3 -> Greater Essence of Electricity x1 |
| Greater Essence of Ruin | Helmets, Body Armours, Gloves, Boots, Shields, Rings, Amulets, Belts, Bucklers, Foci | +(16—19)% to Chaos Resistance | Suffix | 44 | 60 |  Essence of Ruin x3 -> Greater Essence of Ruin x1 |
| Greater Essence of Battle | Gloves, Quivers, One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Bows, Quarterstaves, Daggers, Crossbows, Flails, Talismans | +(237—346) to Accuracy Rating | Prefix | 46 | 60 |  Essence of Battle x3 -> Greater Essence of Battle x1 |
| Greater Essence of Sorcery | Foci, Wands | (75—89)% increased Spell Damage | Prefix | 48 | 60 |  Essence of Sorcery x3 -> Greater Essence of Sorcery x1 |
| Greater Essence of Sorcery | Staves | (149—188)% increased Spell Damage | Prefix | 48 | 60 |  Essence of Sorcery x3 -> Greater Essence of Sorcery x1 |
| Greater Essence of Haste | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Quarterstaves, Daggers, Flails, Talismans | (23—25)% increased Attack Speed | Suffix | 48 | 60 |  Essence of Haste x3 -> Greater Essence of Haste x1 |
| Greater Essence of Haste | Bows, Crossbows | (14—16)% increased Attack Speed | Suffix | 24 | 60 |  Essence of Haste x3 -> Greater Essence of Haste x1 |
| Greater Essence of the Infinite | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Bows, Quarterstaves, Daggers, Helmets, Body Armours, Gloves, Boots, Shields, Staves, Wands, Sceptres, Rings, Amulets, Belts, Quivers, Crossbows, Flails, Talismans, Foci, Bucklers | +(25—27) to Strength, Dexterity or Intelligence | Suffix | 44 | 60 |  Essence of the Infinite x3 -> Greater Essence of the Infinite x1 |
| Perfect Essence of the Body | Body Armours | (8—10)% increased maximum Life | Prefix | 57 | 72 |  |
| Perfect Essence of the Mind | Rings | (4—6)% increased maximum Mana | Prefix | 57 | 72 |  |
| Perfect Essence of Enhancement | Amulets | (20—30)% increased Global Armour, Evasion and Energy Shield | Prefix | 57 | 72 |  |
| Perfect Essence of Abrasion | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Gain (15—20)% of Damage as Extra Physical Damage | Prefix | 57 | 72 |  |
| Perfect Essence of Abrasion | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Gain (25—33)% of Damage as Extra Physical Damage | Prefix | 57 | 72 |  |
| Perfect Essence of Flames | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Gain (15—20)% of Damage as Extra Fire Damage | Prefix | 57 | 72 |  |
| Perfect Essence of Flames | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Gain (25—33)% of Damage as Extra Fire Damage | Prefix | 57 | 72 |  |
| Perfect Essence of Ice | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Gain (15—20)% of Damage as Extra Cold Damage | Prefix | 57 | 72 |  |
| Perfect Essence of Ice | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Gain (25—33)% of Damage as Extra Cold Damage | Prefix | 57 | 72 |  |
| Perfect Essence of Electricity | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | Gain (15—20)% of Damage as Extra Lightning Damage | Prefix | 57 | 72 |  |
| Perfect Essence of Electricity | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | Gain (25—33)% of Damage as Extra Lightning Damage | Prefix | 57 | 72 |  |
| Perfect Essence of Ruin | Body Armours | (10—15)% of Physical Damage from Hits taken as Chaos Damage | Prefix | 57 | 72 |  |
| Perfect Essence of Battle | One Hand Swords, One Hand Axes, One Hand Maces, Spears, Daggers, Bows, Flails | +2 to Level of all Attack Skills | Suffix | 57 | 72 |  |
| Perfect Essence of Battle | Two Hand Swords, Two Hand Axes, Two Hand Maces, Quarterstaves, Crossbows, Talismans | +3 to Level of all Attack Skills | Suffix | 57 | 72 |  |
| Perfect Essence of Sorcery | Wands | +3 to Level of all Spell Skills | Suffix | 57 | 72 |  |
| Perfect Essence of Sorcery | Staves | +5 to Level of all Spell Skills | Suffix | 57 | 72 |  |
| Perfect Essence of Haste | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Bows, Quarterstaves, Daggers, Crossbows, Flails, Talismans | (20—25)% chance to gain Onslaught on Killing Hits with this Weapon | Suffix | 57 | 72 |  |
| Perfect Essence of the Infinite | Amulets | (7—10)% increased Strength, Dexterity or Intelligence | Suffix | 57 | 72 |  |
| Lesser Essence of Seeking | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Bows, Quarterstaves, Daggers, Crossbows, Flails, Talismans | +(1.51—2.1)% to Critical Hit Chance | Suffix | 16 | 20 |  Lesser Essence of Seeking x3 -> Essence of Seeking x1 |
| Lesser Essence of Seeking | Foci, Wands | (34—39)% increased Critical Hit Chance for Spells | Suffix | 16 | 20 |  Lesser Essence of Seeking x3 -> Essence of Seeking x1 |
| Lesser Essence of Seeking | Staves | (50—59)% increased Critical Hit Chance for Spells | Suffix | 16 | 20 |  Lesser Essence of Seeking x3 -> Essence of Seeking x1 |
| Essence of Seeking | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Bows, Quarterstaves, Daggers, Crossbows, Flails, Talismans | +(2.11—2.7)% to Critical Hit Chance | Suffix | 24 | 40 |  Lesser Essence of Seeking x3 -> Essence of Seeking x1 |
| Essence of Seeking | Foci, Wands | (40—46)% increased Critical Hit Chance for Spells | Suffix | 22 | 40 |  Lesser Essence of Seeking x3 -> Essence of Seeking x1 |
| Essence of Seeking | Staves | (60—69)% increased Critical Hit Chance for Spells | Suffix | 22 | 40 |  Lesser Essence of Seeking x3 -> Essence of Seeking x1 |
| Greater Essence of Seeking | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Bows, Quarterstaves, Daggers, Crossbows, Flails, Talismans | +(3.11—3.8)% to Critical Hit Chance | Suffix | 35 | 60 |  Essence of Seeking x3 -> Greater Essence of Seeking x1 |
| Greater Essence of Seeking | Foci, Wands | (47—53)% increased Critical Hit Chance for Spells | Suffix | 32 | 60 |  Essence of Seeking x3 -> Greater Essence of Seeking x1 |
| Greater Essence of Seeking | Staves | (70—79)% increased Critical Hit Chance for Spells | Suffix | 32 | 60 |  Essence of Seeking x3 -> Greater Essence of Seeking x1 |
| Perfect Essence of Seeking | Body Armours | Hits against you have (40—50)% reduced Critical Damage Bonus | Suffix | 57 | 72 |  |
| Essence of Hysteria | Helmets | +1 to Level of all Minion Skills | Suffix | 4 | 1 |  |
| Essence of Hysteria | Body Armours | (64—97) to (98—145) Physical Thorns damage | Prefix | 50 | 1 |  |
| Essence of Hysteria | Gloves | (25—29)% increased Critical Damage Bonus | Suffix | 36 | 1 |  |
| Essence of Hysteria | Boots | 30% increased Movement Speed | Prefix | 52 | 1 |  |
| Essence of Hysteria | Rings | (50—59)% increased Mana Regeneration Rate | Suffix | 44 | 1 |  |
| Essence of Hysteria | Amulets | (19—21)% of Damage taken Recouped as Life | Suffix | 54 | 1 |  |
| Essence of Hysteria | Belts | +(254—304) to Stun Threshold | Suffix | 57 | 1 |  |
| Essence of Hysteria | Shields, Bucklers | (20—24)% increased Block chance | Prefix | 26 | 1 |  |
| Essence of Hysteria | Quivers | (43—50)% increased Damage with Bow Skills | Prefix | 48 | 1 |  |
| Essence of Hysteria | Foci | (20—23)% increased Energy Shield Recharge Rate | Suffix | 52 | 1 |  |
| Essence of Delirium | Body Armours | Allocates a random Notable Passive Skill | Prefix | 0 | 1 |  |
| Essence of Horror | Gloves, Boots | 60% increased effect of Socketed Augment Items | Suffix | 0 | 1 |  |
| Essence of Insanity | Belts | On Corruption, Item gains two Enchantments | Suffix | 0 | 1 |  |
| Essence of the Breach | Rings, Amulets | +20% to Maximum Quality | Prefix | 0 | 1 |  |
| Lesser Essence of Insulation | Helmets, Body Armours, Gloves, Boots, Shields, Rings, Amulets, Belts, Bucklers, Foci | +(11—15)% to Fire Resistance | Suffix | 9 | 1 |  Lesser Essence of Insulation x3 -> Essence of Insulation x1 |
| Essence of Insulation | Helmets, Body Armours, Gloves, Boots, Shields, Rings, Amulets, Belts, Bucklers, Foci | +(21—25)% to Fire Resistance | Suffix | 28 | 1 |  Lesser Essence of Insulation x3 -> Essence of Insulation x1 |
| Greater Essence of Insulation | Helmets, Body Armours, Gloves, Boots, Shields, Rings, Amulets, Belts, Bucklers, Foci | +(31—35)% to Fire Resistance | Suffix | 48 | 1 |  Essence of Insulation x3 -> Greater Essence of Insulation x1 |
| Perfect Essence of Insulation | Belts | (26—30)% of Fire Damage taken Recouped as Life | Suffix | 57 | 1 |  |
| Lesser Essence of Thawing | Helmets, Body Armours, Gloves, Boots, Shields, Rings, Amulets, Belts, Bucklers, Foci | +(11—15)% to Cold Resistance | Suffix | 11 | 1 |  Lesser Essence of Thawing x3 -> Essence of Thawing x1 |
| Essence of Thawing | Helmets, Body Armours, Gloves, Boots, Shields, Rings, Amulets, Belts, Bucklers, Foci | +(21—25)% to Cold Resistance | Suffix | 30 | 1 |  Lesser Essence of Thawing x3 -> Essence of Thawing x1 |
| Greater Essence of Thawing | Helmets, Body Armours, Gloves, Boots, Shields, Rings, Amulets, Belts, Bucklers, Foci | +(31—35)% to Cold Resistance | Suffix | 48 | 1 |  Essence of Thawing x3 -> Greater Essence of Thawing x1 |
| Perfect Essence of Thawing | Helmets | (26—30)% of Cold Damage taken Recouped as Life | Suffix | 57 | 1 |  |
| Lesser Essence of Grounding | Helmets, Body Armours, Gloves, Boots, Shields, Rings, Amulets, Belts, Bucklers, Foci | +(11—15)% to Lightning Resistance | Suffix | 10 | 1 |  Lesser Essence of Grounding x3 -> Essence of Grounding x1 |
| Essence of Grounding | Helmets, Body Armours, Gloves, Boots, Shields, Rings, Amulets, Belts, Bucklers, Foci | +(21—25)% to Lightning Resistance | Suffix | 29 | 1 |  Lesser Essence of Grounding x3 -> Essence of Grounding x1 |
| Greater Essence of Grounding | Helmets, Body Armours, Gloves, Boots, Shields, Rings, Amulets, Belts, Bucklers, Foci | +(31—35)% to Lightning Resistance | Suffix | 48 | 1 |  Essence of Grounding x3 -> Greater Essence of Grounding x1 |
| Perfect Essence of Grounding | Gloves | (26—30)% of Lightning Damage taken Recouped as Life | Suffix | 57 | 1 |  |
| Lesser Essence of Alacrity | Foci, Wands | (13—16)% increased Cast Speed | Suffix | 12 | 1 |  Lesser Essence of Alacrity x3 -> Essence of Alacrity x1 |
| Lesser Essence of Alacrity | Staves | (20—25)% increased Cast Speed | Suffix | 12 | 1 |  Lesser Essence of Alacrity x3 -> Essence of Alacrity x1 |
| Essence of Alacrity | Foci, Wands | (17—20)% increased Cast Speed | Suffix | 24 | 1 |  Lesser Essence of Alacrity x3 -> Essence of Alacrity x1 |
| Essence of Alacrity | Staves | (26—31)% increased Cast Speed | Suffix | 24 | 1 |  Lesser Essence of Alacrity x3 -> Essence of Alacrity x1 |
| Greater Essence of Alacrity | Foci, Wands | (25—28)% increased Cast Speed | Suffix | 48 | 1 |  Essence of Alacrity x3 -> Greater Essence of Alacrity x1 |
| Greater Essence of Alacrity | Staves | (38—43)% increased Cast Speed | Suffix | 48 | 1 |  Essence of Alacrity x3 -> Greater Essence of Alacrity x1 |
| Perfect Essence of Alacrity | Foci, Wands | (18—20)% increased Mana Cost Efficiency | Suffix | 57 | 1 |  |
| Perfect Essence of Alacrity | Staves | (28—32)% increased Mana Cost Efficiency | Suffix | 57 | 1 |  |
| Lesser Essence of Opulence | Helmets, Rings, Amulets, Boots, Gloves | (6—10)% increased Rarity of Items found | Suffix | 2 | 1 |  Lesser Essence of Opulence x3 -> Essence of Opulence x1 |
| Essence of Opulence | Helmets, Rings, Amulets, Boots, Gloves | (11—14)% increased Rarity of Items found | Suffix | 19 | 1 |  Lesser Essence of Opulence x3 -> Essence of Opulence x1 |
| Greater Essence of Opulence | Helmets, Rings, Amulets, Boots, Gloves | (15—18)% increased Rarity of Items found | Suffix | 32 | 1 |  Essence of Opulence x3 -> Greater Essence of Opulence x1 |
| Perfect Essence of Opulence | Gloves | (10—15)% increased Quantity of Gold Dropped by Slain Enemies | Suffix | 57 | 1 |  |
| Lesser Essence of Command | Sceptres | Allies in your Presence deal (35—44)% increased Damage | Prefix | 6 | 1 |  Lesser Essence of Command x3 -> Essence of Command x1 |
| Essence of Command | Sceptres | Allies in your Presence deal (55—64)% increased Damage | Prefix | 26 | 1 |  Lesser Essence of Command x3 -> Essence of Command x1 |
| Greater Essence of Command | Sceptres | Allies in your Presence deal (75—89)% increased Damage | Prefix | 48 | 1 |  Essence of Command x3 -> Greater Essence of Command x1 |
| Perfect Essence of Command | Sceptres | Aura Skills have (15—20)% increased Magnitudes | Suffix | 57 | 1 |  |
| Essence of the Abyss | all equipment classes (27 classes listed: weapons, armour, jewellery, belts, quivers, foci, bucklers) | Mark of the Abyssal Lord (rolls as a Prefix or as a Suffix; poe2db lists both rows per class) | Prefix or Suffix | 0 | 1 |  |

## Appendix B. Expedition Alloys (13 alloys, 48 rows)

Source S2, 0.5.5.10. All: "Removes a random modifier and augments a Rare item with a new guaranteed modifier". Same columns as Appendix A (Celestial and Transcendent rows typed from their pages, where one mod has two lines).

| Alloy | Classes | Modifier | Side | Mod level | Drop level | recipe |
|---|---|---|---|---|---|---|
| Runic Alloy | Rings | +(37—49) to maximum Runic Ward | Prefix | 10 | 13 |  |
| Runic Alloy | Amulets | (6—10)% increased maximum Runic Ward | Prefix | 10 | 13 |  |
| Runic Alloy | Belts | (15—20)% increased Runic Ward Regeneration Rate | Prefix | 10 | 13 |  |
| Adaptive Alloy | Staves | Gain (42—52)% of Damage as Extra Fire Damage while you are missing Runic Ward | Prefix | 20 | 23 |  |
| Adaptive Alloy | Wands | Gain (21—26)% of Damage as Extra Fire Damage while you are missing Runic Ward | Prefix | 20 | 23 |  |
| Adaptive Alloy | Sceptres | (30—50)% Surpassing Chance to gain a Puppet Master stack whenever you use a Command Skill | Prefix | 20 | 23 |  |
| Adaptive Alloy | Gloves | (10—15)% increased Attack Speed while missing Runic Ward | Suffix | 20 | 23 |  |
| Protective Alloy | Belts | Recover (32—45) Runic Ward when a Charm is used | Prefix | 20 | 23 |  |
| Protective Alloy | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Bows, Quarterstaves, Daggers, Crossbows, Flails, Talismans, Sceptres, Staves, Wands | +(51—74) to maximum Runic Ward | Suffix | 20 | 23 |  |
| Protective Alloy | Shields, Bucklers | Recover (10—15) Runic Ward when you Block | Suffix | 10 | 23 |  |
| Expansive Alloy | Gloves | Remnants can be collected from (35—50)% further away | Suffix | 20 | 23 |  |
| Expansive Alloy | Body Armours | (35—50)% increased Presence Area of Effect | Suffix | 20 | 23 |  |
| Expansive Alloy | Helmets | (18—29)% increased Mana Cost Efficiency | Prefix | 20 | 23 |  |
| Expansive Alloy | Boots | Temporary Minion Skills have +(1—2) to Limit of Minions summoned | Suffix | 20 | 23 |  |
| Swift Alloy | Gloves | (9—12)% increased Cast Speed | Suffix | 36 | 45 |  |
| Swift Alloy | Rings | (7—9)% increased Attack Speed | Suffix | 36 | 45 |  |
| Swift Alloy | Belts | Flasks gain (0.75—1) charges per Second | Suffix | 36 | 45 |  |
| Swift Alloy | Shields, Bucklers, Foci | (30—49)% increased Totem Placement speed | Suffix | 36 | 45 |  |
| Cyclonic Alloy | Body Armours | (15—30)% reduced Slowing Potency of Debuffs on You | Suffix | 36 | 45 |  |
| Cyclonic Alloy | Boots | (15—19)% increased Skill Effect Duration | Suffix | 36 | 45 |  |
| Cyclonic Alloy | Gloves | (20—25)% increased Duration of Damaging Ailments on Enemies | Suffix | 36 | 45 |  |
| Cyclonic Alloy | Helmets | (35—42)% increased Archon Buff duration | Suffix | 36 | 45 |  |
| Prismatic Alloy | Gloves | Damage Penetrates (9—15)% Elemental Resistances | Prefix | 36 | 45 |  |
| Prismatic Alloy | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Bows, Quarterstaves, Daggers, Crossbows, Flails, Talismans | (20—30)% increased Magnitude of Ailments you inflict | Suffix | 36 | 45 |  |
| Prismatic Alloy | Staves, Wands, Foci | (40—50)% increased Exposure Effect | Suffix | 36 | 45 |  |
| Prismatic Alloy | Sceptres | Minions have (40—49)% increased Magnitude of Damaging Ailments | Suffix | 36 | 45 |  |
| Mystic Alloy | Helmets | Spell Skills have (10—15)% increased Area of Effect | Suffix | 36 | 45 |  |
| Mystic Alloy | Gloves | (10—15)% increased Area of Effect for Attacks | Suffix | 36 | 45 |  |
| Mystic Alloy | Boots | +(10—15) to Spirit | Suffix | 36 | 45 |  |
| Mystic Alloy | Quivers | (25—35)% chance to Chain an additional time | Suffix | 36 | 45 |  |
| Mystic Alloy | Staves, Wands, Sceptres | +1 to maximum number of Elemental Infusions | Suffix | 36 | 45 |  |
| Sovereign Alloy | One Hand Swords, One Hand Axes, One Hand Maces, Two Hand Swords, Two Hand Axes, Two Hand Maces, Spears, Bows, Quarterstaves, Daggers, Crossbows, Flails, Talismans, Sceptres, Staves, Wands | (20—30)% increased effect of Socketed Augment Items | Suffix | 52 | 65 |  |
| Sovereign Alloy | Helmets, Body Armours, Gloves, Boots, Shields, Bucklers, Foci | (24—30)% increased Runic Ward | Prefix | 20 | 65 |  |
| Sovereign Alloy | Rings, Amulets, Belts | (20—30)% increased Explicit Resistance Modifier magnitudes | Prefix | 52 | 65 |  |
| The Runebinder's Alloy | Staves | (25—50)% chance to gain Nature's Archon when your Plants Overgrow | Suffix | 52 | 65 |  |
| The Runebinder's Alloy | Wands | +1 to Limit for Elemental Skills | Suffix | 52 | 65 |  |
| The Runebinder's Alloy | Sceptres | +(4—5) maximum stacks of Puppet Master | Suffix | 52 | 65 |  |
| The Runebinder's Alloy | Crossbows | +2 to maximum number of Summoned Ballista Totems | Suffix | 52 | 65 |  |
| The Runebinder's Alloy | Bows | (40—50)% increased Effect of your Mark Skills | Suffix | 52 | 65 |  |
| The Runefather's Alloy | One Hand Maces, Two Hand Maces | (60—75)% chance for Skills to retain 40% of Glory on use | Suffix | 52 | 65 |  |
| The Runefather's Alloy | Quarterstaves | Tempest Bells are destroyed after an additional (4—5) Hits | Suffix | 52 | 65 |  |
| The Runefather's Alloy | Spears | +(8—10) to Weapon Range | Suffix | 52 | 65 |  |
| The Runefather's Alloy | Talismans | Lightning Damage from Hits also Contributes to Flammability and Ignite Magnitudes | Suffix | 52 | 65 |  |
| Celestial Alloy | Staves, Wands | +(142—188) to maximum Mana and +1 to Level of all Spell Skills (one mod) | Prefix | 52 | see page |  |
| Celestial Alloy | martial weapons (One/Two Hand Swords, Axes, Maces, Spears, Bows, Quarterstaves, Daggers, Crossbows, Flails, Talismans) | +(327—427) to Accuracy Rating and (5—8)% increased Attack Speed (one mod) | Prefix | 52 | see page |  |
| Transcendent Alloy | Staves | (39—47)% increased Cast Speed and Gain (11—16)% of Elemental Damage as Extra Cold Damage (one mod) | Suffix | 52 | see page |  |
| Transcendent Alloy | Foci, Wands | (26—31)% increased Cast Speed and Gain (7—11)% of Elemental Damage as Extra Cold Damage (one mod) | Suffix | 52 | see page |  |
| Transcendent Alloy | martial weapons | (15—20)% increased Physical Damage and +(7—10) to all Attributes (one mod) | Suffix | 52 | see page |  |

## Appendix C. Augments (game text, poe2db Augment page S3, 0.5.5.10)

Each row: name | requirement and effect per slot type, "Bonded:" lines after the marker (active only under the Bonded condition, section 2.9). "Limited to: 1" = one per character. Entries marked [DNT-Unused] in the data are left out.

### C.1 Runes and Kalguuran augments

| Name | Text |
|---|---|
| Desert Rune | Requires: Level 15 ; Martial Weapon: Adds 7 to 11 Fire Damage ; Wand or Staff: Gain 8% of Damage as Extra Fire Damage ; Armour: +14% to Fire Resistance ; Bonded: ; Martial Weapon: 30% increased Ignite Magnitude ; Wand or Staff: 30% increased Ignite Magnitude ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Glacial Rune | Requires: Level 15 ; Martial Weapon: Adds 6 to 10 Cold Damage ; Wand or Staff: Gain 8% of Damage as Extra Cold Damage ; Armour: +14% to Cold Resistance ; Bonded: ; Martial Weapon: 30% increased Freeze Buildup ; Wand or Staff: 30% increased Freeze Buildup ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Storm Rune | Requires: Level 15 ; Martial Weapon: Adds 1 to 20 Lightning Damage ; Wand or Staff: Gain 8% of Damage as Extra Lightning Damage ; Armour: +14% to Lightning Resistance ; Bonded: ; Martial Weapon: 30% increased Magnitude of Shock you inflict ; Wand or Staff: 30% increased Magnitude of Shock you inflict ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Iron Rune | Requires: Level 15 ; Martial Weapon: 16% increased Physical Damage ; Wand or Staff: 25% increased Spell Damage ; Armour: 16% increased Armour, Evasion and Energy Shield ; Bonded: ; Martial Weapon: 20% increased effect of Fully Broken Armour ; Wand or Staff: Break Armour on Critical Hit with Spells equal to 12% of Physical Damage dealt ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Body Rune | Requires: Level 15 ; Martial Weapon: Leeches 4% of Physical Damage as Life ; Wand or Staff: +40 to maximum Energy Shield ; Armour: +45 to maximum Life ; Bonded: ; Martial Weapon: 5% increased maximum Life ; Wand or Staff: 5% increased maximum Life ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Mind Rune | Requires: Level 15 ; Martial Weapon: Leeches 3% of Physical Damage as Mana ; Wand or Staff: +60 to maximum Mana ; Armour: +30 to maximum Mana ; Bonded: ; Martial Weapon: 5% increased maximum Mana ; Wand or Staff: 5% increased maximum Mana ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Rebirth Rune | Requires: Level 15 ; Martial Weapon: Gain 25 Life per enemy killed ; Wand or Staff: 8% increased Energy Shield Recharge Rate ; Armour: Regenerate 0.4% of maximum Life per second ; Bonded: ; Martial Weapon: Regenerate 0.4% of maximum Life per second ; Wand or Staff: 8% of Damage taken Recouped as Life ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Inspiration Rune | Requires: Level 15 ; Martial Weapon: Gain 20 Mana per enemy killed ; Wand or Staff: 25% increased Mana Regeneration Rate ; Armour: 15% increased Mana Regeneration Rate ; Bonded: ; Martial Weapon: 12% of Skill Mana Costs Converted to Life Costs ; Wand or Staff: 16% increased Mana Cost Efficiency ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Stone Rune | Requires: Level 15 ; Martial Weapon: Causes 30% increased Stun Buildup ; Wand or Staff: Gain additional Stun Threshold equal to 12% of maximum Energy Shield ; Armour: +75 to Stun Threshold ; Bonded: ; Martial Weapon: 40% increased Damage against Immobilised Enemies ; Wand or Staff: 30% increased Immobilisation buildup ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Vision Rune | Requires: Level 15 ; Martial Weapon: +90 to Accuracy Rating ; Wand or Staff: 20% increased Critical Hit Chance for Spells ; Armour: 12% increased Life and Mana Recovery from Flasks ; Bonded: ; Martial Weapon: Attacks have +1% to Critical Hit Chance ; Wand or Staff: 25% increased Critical Damage Bonus ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Lesser Desert Rune | Martial Weapon: Adds 4 to 6 Fire Damage ; Wand or Staff: Gain 6% of Damage as Extra Fire Damage ; Armour: +10% to Fire Resistance ; Bonded: ; Martial Weapon: 30% increased Ignite Magnitude ; Wand or Staff: 30% increased Ignite Magnitude ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Lesser Glacial Rune | Martial Weapon: Adds 3 to 5 Cold Damage ; Wand or Staff: Gain 6% of Damage as Extra Cold Damage ; Armour: +10% to Cold Resistance ; Bonded: ; Martial Weapon: 30% increased Freeze Buildup ; Wand or Staff: 30% increased Freeze Buildup ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Lesser Storm Rune | Martial Weapon: Adds 1 to 10 Lightning Damage ; Wand or Staff: Gain 6% of Damage as Extra Lightning Damage ; Armour: +10% to Lightning Resistance ; Bonded: ; Martial Weapon: 30% increased Magnitude of Shock you inflict ; Wand or Staff: 30% increased Magnitude of Shock you inflict ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Lesser Iron Rune | Martial Weapon: 14% increased Physical Damage ; Wand or Staff: 20% increased Spell Damage ; Armour: 14% increased Armour, Evasion and Energy Shield ; Bonded: ; Martial Weapon: 20% increased effect of Fully Broken Armour ; Wand or Staff: Break Armour on Critical Hit with Spells equal to 12% of Physical Damage dealt ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Lesser Body Rune | Martial Weapon: Leeches 3% of Physical Damage as Life ; Wand or Staff: +30 to maximum Energy Shield ; Armour: +30 to maximum Life ; Bonded: ; Martial Weapon: 5% increased maximum Life ; Wand or Staff: 5% increased maximum Life ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Lesser Mind Rune | Martial Weapon: Leeches 2% of Physical Damage as Mana ; Wand or Staff: +45 to maximum Mana ; Armour: +20 to maximum Mana ; Bonded: ; Martial Weapon: 5% increased maximum Mana ; Wand or Staff: 5% increased maximum Mana ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Lesser Rebirth Rune | Martial Weapon: Gain 15 Life per enemy killed ; Wand or Staff: 6% increased Energy Shield Recharge Rate ; Armour: Regenerate 0.35% of maximum Life per second ; Bonded: ; Martial Weapon: Regenerate 0.4% of maximum Life per second ; Wand or Staff: 8% of Damage taken Recouped as Life ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Lesser Inspiration Rune | Martial Weapon: Gain 10 Mana per enemy killed ; Wand or Staff: 20% increased Mana Regeneration Rate ; Armour: 12% increased Mana Regeneration Rate ; Bonded: ; Martial Weapon: 12% of Skill Mana Costs Converted to Life Costs ; Wand or Staff: 16% increased Mana Cost Efficiency ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Lesser Stone Rune | Martial Weapon: Causes 20% increased Stun Buildup ; Wand or Staff: Gain additional Stun Threshold equal to 10% of maximum Energy Shield ; Armour: +50 to Stun Threshold ; Bonded: ; Martial Weapon: 40% increased Damage against Immobilised Enemies ; Wand or Staff: 30% increased Immobilisation buildup ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Lesser Vision Rune | Martial Weapon: +60 to Accuracy Rating ; Wand or Staff: 16% increased Critical Hit Chance for Spells ; Armour: 8% increased Life and Mana Recovery from Flasks ; Bonded: ; Martial Weapon: Attacks have +1% to Critical Hit Chance ; Wand or Staff: 25% increased Critical Damage Bonus ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Greater Desert Rune | Requires: Level 30 ; Martial Weapon: Adds 13 to 16 Fire Damage ; Wand or Staff: Gain 10% of Damage as Extra Fire Damage ; Armour: +18% to Fire Resistance ; Bonded: ; Martial Weapon: 30% increased Ignite Magnitude ; Wand or Staff: 30% increased Ignite Magnitude ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Greater Glacial Rune | Requires: Level 30 ; Martial Weapon: Adds 9 to 15 Cold Damage ; Wand or Staff: Gain 10% of Damage as Extra Cold Damage ; Armour: +18% to Cold Resistance ; Bonded: ; Martial Weapon: 30% increased Freeze Buildup ; Wand or Staff: 30% increased Freeze Buildup ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Greater Storm Rune | Requires: Level 30 ; Martial Weapon: Adds 1 to 30 Lightning Damage ; Wand or Staff: Gain 10% of Damage as Extra Lightning Damage ; Armour: +18% to Lightning Resistance ; Bonded: ; Martial Weapon: 30% increased Magnitude of Shock you inflict ; Wand or Staff: 30% increased Magnitude of Shock you inflict ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Greater Iron Rune | Requires: Level 30 ; Martial Weapon: 18% increased Physical Damage ; Wand or Staff: 30% increased Spell Damage ; Armour: 18% increased Armour, Evasion and Energy Shield ; Bonded: ; Martial Weapon: 20% increased effect of Fully Broken Armour ; Wand or Staff: Break Armour on Critical Hit with Spells equal to 12% of Physical Damage dealt ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Greater Body Rune | Requires: Level 30 ; Martial Weapon: Leeches 5% of Physical Damage as Life ; Wand or Staff: +50 to maximum Energy Shield ; Armour: +60 to maximum Life ; Bonded: ; Martial Weapon: 5% increased maximum Life ; Wand or Staff: 5% increased maximum Life ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Greater Mind Rune | Requires: Level 30 ; Martial Weapon: Leeches 4% of Physical Damage as Mana ; Wand or Staff: +75 to maximum Mana ; Armour: +40 to maximum Mana ; Bonded: ; Martial Weapon: 5% increased maximum Mana ; Wand or Staff: 5% increased maximum Mana ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Greater Rebirth Rune | Requires: Level 30 ; Martial Weapon: Gain 35 Life per enemy killed ; Wand or Staff: 10% increased Energy Shield Recharge Rate ; Armour: Regenerate 0.45% of maximum Life per second ; Bonded: ; Martial Weapon: Regenerate 0.4% of maximum Life per second ; Wand or Staff: 8% of Damage taken Recouped as Life ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Greater Inspiration Rune | Requires: Level 30 ; Martial Weapon: Gain 30 Mana per enemy killed ; Wand or Staff: 30% increased Mana Regeneration Rate ; Armour: 18% increased Mana Regeneration Rate ; Bonded: ; Martial Weapon: 12% of Skill Mana Costs Converted to Life Costs ; Wand or Staff: 16% increased Mana Cost Efficiency ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Greater Stone Rune | Requires: Level 30 ; Martial Weapon: Causes 40% increased Stun Buildup ; Wand or Staff: Gain additional Stun Threshold equal to 14% of maximum Energy Shield ; Armour: +100 to Stun Threshold ; Bonded: ; Martial Weapon: 40% increased Damage against Immobilised Enemies ; Wand or Staff: 30% increased Immobilisation buildup ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Greater Vision Rune | Requires: Level 30 ; Martial Weapon: +120 to Accuracy Rating ; Wand or Staff: 24% increased Critical Hit Chance for Spells ; Armour: 16% increased Life and Mana Recovery from Flasks ; Bonded: ; Martial Weapon: Attacks have +1% to Critical Hit Chance ; Wand or Staff: 25% increased Critical Damage Bonus ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Perfect Desert Rune | Requires: Level 50 ; Martial Weapon: Adds 17 to 20 Fire Damage ; Wand or Staff: Gain 12% of Damage as Extra Fire Damage ; Armour: +22% to Fire Resistance ; Bonded: ; Martial Weapon: 30% increased Ignite Magnitude ; Wand or Staff: 30% increased Ignite Magnitude ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Perfect Glacial Rune | Requires: Level 50 ; Martial Weapon: Adds 16 to 20 Cold Damage ; Wand or Staff: Gain 12% of Damage as Extra Cold Damage ; Armour: +22% to Cold Resistance ; Bonded: ; Martial Weapon: 30% increased Freeze Buildup ; Wand or Staff: 30% increased Freeze Buildup ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Perfect Storm Rune | Requires: Level 50 ; Martial Weapon: Adds 1 to 40 Lightning Damage ; Wand or Staff: Gain 12% of Damage as Extra Lightning Damage ; Armour: +22% to Lightning Resistance ; Bonded: ; Martial Weapon: 30% increased Magnitude of Shock you inflict ; Wand or Staff: 30% increased Magnitude of Shock you inflict ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Perfect Iron Rune | Requires: Level 50 ; Martial Weapon: 20% increased Physical Damage ; Wand or Staff: 35% increased Spell Damage ; Armour: 20% increased Armour, Evasion and Energy Shield ; Bonded: ; Martial Weapon: 20% increased effect of Fully Broken Armour ; Wand or Staff: Break Armour on Critical Hit with Spells equal to 12% of Physical Damage dealt ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Perfect Body Rune | Requires: Level 50 ; Martial Weapon: Leeches 6% of Physical Damage as Life ; Wand or Staff: +60 to maximum Energy Shield ; Armour: +75 to maximum Life ; Bonded: ; Martial Weapon: 5% increased maximum Life ; Wand or Staff: 5% increased maximum Life ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Perfect Mind Rune | Requires: Level 50 ; Martial Weapon: Leeches 5% of Physical Damage as Mana ; Wand or Staff: +90 to maximum Mana ; Armour: +50 to maximum Mana ; Bonded: ; Martial Weapon: 5% increased maximum Mana ; Wand or Staff: 5% increased maximum Mana ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Perfect Rebirth Rune | Requires: Level 50 ; Martial Weapon: Gain 45 Life per enemy killed ; Wand or Staff: 12% increased Energy Shield Recharge Rate ; Armour: Regenerate 0.5% of maximum Life per second ; Bonded: ; Martial Weapon: Regenerate 0.4% of maximum Life per second ; Wand or Staff: 8% of Damage taken Recouped as Life ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Perfect Inspiration Rune | Requires: Level 50 ; Martial Weapon: Gain 40 Mana per enemy killed ; Wand or Staff: 35% increased Mana Regeneration Rate ; Armour: 21% increased Mana Regeneration Rate ; Bonded: ; Martial Weapon: 12% of Skill Mana Costs Converted to Life Costs ; Wand or Staff: 16% increased Mana Cost Efficiency ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Perfect Stone Rune | Requires: Level 50 ; Martial Weapon: Causes 50% increased Stun Buildup ; Wand or Staff: Gain additional Stun Threshold equal to 16% of maximum Energy Shield ; Armour: +125 to Stun Threshold ; Bonded: ; Martial Weapon: 40% increased Damage against Immobilised Enemies ; Wand or Staff: 30% increased Immobilisation buildup ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Perfect Vision Rune | Requires: Level 50 ; Martial Weapon: +150 to Accuracy Rating ; Wand or Staff: 28% increased Critical Hit Chance for Spells ; Armour: 20% increased Life and Mana Recovery from Flasks ; Bonded: ; Martial Weapon: Attacks have +1% to Critical Hit Chance ; Wand or Staff: 25% increased Critical Damage Bonus ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Lesser Robust Rune | All Equipment: +6 to Strength ; Bonded: ; Martial Weapon: Adds 6 to 10 Physical Damage to Attacks, Adds 6 to 10 Fire damage to Attacks ; Wand or Staff: +100 to Armour ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Robust Rune | Requires: Level 15 ; All Equipment: +9 to Strength ; Bonded: ; Martial Weapon: Adds 6 to 10 Physical Damage to Attacks, Adds 6 to 10 Fire damage to Attacks ; Wand or Staff: +100 to Armour ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Greater Robust Rune | Requires: Level 30 ; All Equipment: +12 to Strength ; Bonded: ; Martial Weapon: Adds 6 to 10 Physical Damage to Attacks, Adds 6 to 10 Fire damage to Attacks ; Wand or Staff: +100 to Armour ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Perfect Robust Rune | Requires: Level 50 ; All Equipment: +15 to Strength ; Bonded: ; Martial Weapon: Adds 6 to 10 Physical Damage to Attacks, Adds 6 to 10 Fire damage to Attacks ; Wand or Staff: +100 to Armour ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Lesser Adept Rune | All Equipment: +6 to Dexterity ; Bonded: ; Martial Weapon: Adds 6 to 10 Physical Damage to Attacks, Adds 1 to 16 Lightning damage to Attacks ; Wand or Staff: +80 to Evasion Rating ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Adept Rune | Requires: Level 15 ; All Equipment: +9 to Dexterity ; Bonded: ; Martial Weapon: Adds 6 to 10 Physical Damage to Attacks, Adds 1 to 16 Lightning damage to Attacks ; Wand or Staff: +80 to Evasion Rating ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Greater Adept Rune | Requires: Level 30 ; All Equipment: +12 to Dexterity ; Bonded: ; Martial Weapon: Adds 6 to 10 Physical Damage to Attacks, Adds 1 to 16 Lightning damage to Attacks ; Wand or Staff: +80 to Evasion Rating ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Perfect Adept Rune | Requires: Level 50 ; All Equipment: +15 to Dexterity ; Bonded: ; Martial Weapon: Adds 6 to 10 Physical Damage to Attacks, Adds 1 to 16 Lightning damage to Attacks ; Wand or Staff: +80 to Evasion Rating ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Lesser Resolve Rune | All Equipment: +6 to Intelligence ; Bonded: ; Martial Weapon: Adds 6 to 10 Physical Damage to Attacks, Adds 5 to 8 Cold damage to Attacks ; Wand or Staff: +50 to maximum Energy Shield ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Resolve Rune | Requires: Level 15 ; All Equipment: +9 to Intelligence ; Bonded: ; Martial Weapon: Adds 6 to 10 Physical Damage to Attacks, Adds 5 to 8 Cold damage to Attacks ; Wand or Staff: +50 to maximum Energy Shield ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Greater Resolve Rune | Requires: Level 30 ; All Equipment: +12 to Intelligence ; Bonded: ; Martial Weapon: Adds 6 to 10 Physical Damage to Attacks, Adds 5 to 8 Cold damage to Attacks ; Wand or Staff: +50 to maximum Energy Shield ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Perfect Resolve Rune | Requires: Level 50 ; All Equipment: +15 to Intelligence ; Bonded: ; Martial Weapon: Adds 6 to 10 Physical Damage to Attacks, Adds 5 to 8 Cold damage to Attacks ; Wand or Staff: +50 to maximum Energy Shield ; Armour: +20 to maximum Life, +20 to maximum Mana |
| Lesser Tempered Rune | Martial Weapon: Adds 3 to 4 Physical Damage ; Armour: 6 to 9 Physical Thorns damage |
| Tempered Rune | Requires: Level 15 ; Martial Weapon: Adds 6 to 9 Physical Damage ; Armour: 14 to 21 Physical Thorns damage |
| Greater Tempered Rune | Requires: Level 30 ; Martial Weapon: Adds 9 to 12 Physical Damage ; Armour: 31 to 52 Physical Thorns damage |
| Greater Rune of Leadership | Martial Weapon: Minions gain 10% of their Physical Damage as Extra Lightning Damage ; Armour: Minions take 10% of Physical Damage as Lightning Damage ; Bonded: ; Martial Weapon: Minions deal 20% increased Damage ; Armour: Minions have +10% to all Elemental Resistances |
| Greater Rune of Tithing | Martial Weapon: Meta Skills gain 10% increased Energy ; Armour: 1 to 100 Lightning Thorns damage ; Bonded: ; Martial Weapon: Invocated Spells have 25% chance to consume half as much Energy ; Armour: 15% increased Thorns damage |
| Greater Rune of Alacrity | Martial Weapon: 8% increased Skill Speed ; Armour: Debuffs on you expire 8% faster ; Bonded: ; Martial Weapon: 15% increased Reservation Efficiency of Herald Skills ; Armour: 15% increased Elemental Ailment Threshold |
| Greater Rune of Nobility | Martial Weapon: Attacks with this Weapon have 10% chance to inflict Exposure ; Armour: 10% reduced effect of Shock on you ; Bonded: ; Martial Weapon: 20% increased Exposure Effect ; Armour: 10% reduced Shock duration on you |
| Hedgewitch Assandra's Rune of Wisdom | Limited to: 1 ; Requires: Level 50 ; Wand or Staff: +1 to Level of all Spell Skills ; Bonded: ; Wand or Staff: Archon recovery period expires 30% faster |
| Saqawal's Rune of the Sky | Limited to: 1 ; Requires: Level 50 ; Martial Weapon: Gain 5% of Damage as Extra Damage of all Elements ; Wand or Staff: Gain 5% of Damage as Extra Damage of all Elements ; Bonded: ; Martial Weapon: 8% chance to gain an additional random Charge when you gain a Charge ; Wand or Staff: 12% chance when collecting an Elemental Infusion to gain an ; additional Elemental Infusion of the same type |
| Fenumus' Rune of Agony | Limited to: 1 ; Requires: Level 50 ; Martial Weapon: Gain 13% of Damage as Extra Chaos Damage ; Wand or Staff: Gain 13% of Damage as Extra Chaos Damage ; Bonded: ; Martial Weapon: Gain 8% of Damage as Extra Physical Damage ; Wand or Staff: Gain 8% of Damage as Extra Physical Damage |
| Farrul's Rune of Grace | Limited to: 1 ; Requires: Level 50 ; Boots: 8% increased Deflection Rating while moving ; Bonded: ; Boots: Prevent +3% of Damage from Deflected Hits |
| Farrul's Rune of the Chase | Limited to: 1 ; Requires: Level 50 ; Boots: 5% increased Movement Speed ; Bonded: ; Boots: 10% increased Cooldown Recovery Rate |
| Craiceann's Rune of Warding | Limited to: 1 ; Requires: Level 50 ; Body Armours: 50% reduced effect of Curses on you ; Bonded: ; Body Armours: 8% increased Curse Magnitudes |
| Saqawal's Rune of Memory | Limited to: 1 ; Requires: Level 50 ; Helmets: 2% increased Experience gain ; Bonded: ; Helmets: +10% to all Elemental Resistances |
| Saqawal's Rune of Erosion | Limited to: 1 ; Requires: Level 50 ; Helmets: 25% increased Exposure Effect ; Bonded: ; Helmets: 15% increased Magnitude of Non-Damaging Ailments you inflict |
| Farrul's Rune of the Hunt | Limited to: 1 ; Requires: Level 50 ; Martial Weapon: 50% increased Attack Damage against Rare or Unique Enemies ; Bonded: ; Martial Weapon: +1 to Level of all Attack Skills |
| Craiceann's Rune of Recovery | Limited to: 1 ; Requires: Level 50 ; Body Armours: 30% increased Energy Shield Recharge Rate ; Bonded: ; Body Armours: Gain additional Ailment Threshold equal to 50% of maximum Energy Shield, Gain additional Stun Threshold equal to 50% of maximum Energy Shield |
| Courtesan Mannan's Rune of Cruelty | Limited to: 1 ; Requires: Level 50 ; Gloves: 20% increased Magnitude of Damaging Ailments you inflict ; Bonded: ; Gloves: 15% increased Duration of Damaging Ailments on Enemies |
| Thane Grannell's Rune of Mastery | Limited to: 1 ; Requires: Level 50 ; Gloves: 30% increased Magnitude of Non-Damaging Ailments you inflict ; Bonded: ; Gloves: 15% increased Duration of Elemental Ailments on Enemies |
| Fenumus' Rune of Spinning | Limited to: 1 ; Requires: Level 50 ; Gloves: 8% increased Cast Speed ; Bonded: ; Gloves: 20% increased Mana Cost Efficiency while on Low Mana |
| Countess Seske's Rune of Archery | Limited to: 1 ; Requires: Level 50 ; Bows: Bow Attacks fire 1 additional Arrows ; Bonded: ; Bows: 20% increased Projectile Speed |
| Thane Girt's Rune of Wildness | Limited to: 1 ; Requires: Level 50 ; Wand or Staff: 25% chance for Spell Skills to fire 2 additional Projectiles ; Bonded: ; Wand or Staff: Every Rage also grants 1% increased Spell Damage |
| Fenumus' Rune of Draining | Limited to: 1 ; Requires: Level 50 ; Gloves: 20% increased Withered Magnitude ; Bonded: ; Gloves: +7% to Chaos Resistance |
| Thane Myrk's Rune of Summer | Limited to: 1 ; Requires: Level 50 ; Martial Weapon: Adds 23 to 34 Fire Damage to Attacks against Ignited Enemies ; Bonded: ; Martial Weapon: +2% to Maximum Fire Resistance |
| Lady Hestra's Rune of Winter | Limited to: 1 ; Requires: Level 50 ; Martial Weapon: Adds 19 to 28 Cold Damage against Chilled Enemies ; Bonded: ; Martial Weapon: +2% to Maximum Cold Resistance |
| Thane Leld's Rune of Spring | Limited to: 1 ; Requires: Level 50 ; Martial Weapon: Adds 1 to 60 Lightning Damage against Shocked Enemies ; Bonded: ; Martial Weapon: +2% to Maximum Lightning Resistance |
| The Greatwolf's Rune of Claws | Limited to: 1 ; Requires: Level 50 ; Gloves: Adds 5 to 12 Physical Damage to Attacks ; Bonded: ; Gloves: Fissure Skills have +2 to Limit |
| The Greatwolf's Rune of Willpower | Limited to: 1 ; Requires: Level 50 ; Body Armours: 15% of Damage is taken from Mana before Life ; Bonded: ; Body Armours: 8% of Maximum Life Converted to Energy Shield |
| Masterwork Rune | All Equipment: Upgrades a socketed Rune |
| Lesser Ward Rune | Armour: +15 to maximum Runic Ward ; Bonded: ; Armour: 15% increased Global Armour, Evasion and Energy Shield |
| Ward Rune | Requires: Level 15 ; Armour: +20 to maximum Runic Ward ; Bonded: ; Armour: 15% increased Global Armour, Evasion and Energy Shield |
| Greater Ward Rune | Requires: Level 30 ; Armour: +25 to maximum Runic Ward ; Bonded: ; Armour: 15% increased Global Armour, Evasion and Energy Shield |
| Perfect Ward Rune | Requires: Level 50 ; Armour: +30 to maximum Runic Ward ; Bonded: ; Armour: 15% increased Global Armour, Evasion and Energy Shield |
| Lesser Charging Rune | Armour: 8% increased Runic Ward Regeneration Rate ; Bonded: ; Armour: Regenerate 10 Runic Ward per second |
| Charging Rune | Requires: Level 15 ; Armour: 12% increased Runic Ward Regeneration Rate ; Bonded: ; Armour: Regenerate 15 Runic Ward per second |
| Greater Charging Rune | Requires: Level 30 ; Armour: 16% increased Runic Ward Regeneration Rate ; Bonded: ; Armour: Regenerate 20 Runic Ward per second |
| Perfect Charging Rune | Requires: Level 50 ; Armour: 20% increased Runic Ward Regeneration Rate ; Bonded: ; Armour: Regenerate 25 Runic Ward per second |
| Warding Rune of Reinforcement | Requires: Level 15 ; Armour: 20% increased Runic Ward ; Bonded: ; Armour: Gain 2% of maximum Life as Extra maximum Runic Ward |
| Warding Rune of Protection | Limited to: 1 ; Requires: Level 15 ; Armour: Every 4 seconds, gain Guard equal to 20% of maximum Runic Ward for 2 seconds ; Bonded: ; Armour: 8% increased Guard gained |
| Warding Rune of Disintegration | Requires: Level 15 ; Martial Weapon: Attacks Break Armour equal to 15% of maximum Runic Ward ; Bonded: ; Martial Weapon: Break 10% increased Armour |
| Warding Rune of Desperation | Requires: Level 15 ; Wand or Staff: Spell damage Penetrates 25% of enemy Elemental Resistances while on Low Runic Ward ; Bonded: ; Wand or Staff: 12% increased Elemental Damage |
| Warding Rune of Symbiosis | Limited to: 1 ; Requires: Level 30 ; Boots: 1% increased Energy Shield Recharge Rate per 30 maximum Runic Ward ; Bonded: ; Boots: Regenerate 1% of maximum Energy Shield per second |
| Warding Rune of Courage | Requires: Level 15 ; Helmets: 25% increased Armour and Evasion Rating while on Low Runic Ward ; Bonded: ; Helmets: 20% increased Armour and Evasion Rating when on Low Life |
| Warding Rune of Stability | Requires: Level 30 ; Shields and Bucklers: +4 to Stun Threshold per 10 maximum Runic Ward ; Bonded: ; Shields and Bucklers: 15% increased Stun buildup while Shapeshifted |
| Warding Rune of Glancing | Requires: Level 30 ; Body Armours: +3 to Deflection Rating per 10 maximum Runic Ward ; Bonded: ; Body Armours: Prevent +1% of Damage from Deflected Hits |
| Warding Rune of Heart | Limited to: 1 ; Requires: Level 30 ; Body Armours: Gain 5% of maximum Life as Extra maximum Runic Ward ; Bonded: ; Body Armours: 1% more Runic Ward Regeneration rate per 2% of maximum Runic Ward lost from Hits Recently, up to 100% more |
| Warding Rune of Nourishment | Limited to: 1 ; Requires: Level 15 ; Armour: 15% Life Recovery from Flasks also applies to Runic Ward ; Bonded: ; Armour: 15% increased Life Recovery from Flasks |
| Warding Rune of Annihilation | Limited to: 1 ; Requires: Level 30 ; Martial Weapon: Attacks spend 5% of your maximum Runic Ward if possible to gain that much added Physical damage ; Bonded: ; Martial Weapon: 10% reduced Runic Ward Cost Efficiency |
| Warding Rune of Armature | Limited to: 1 ; Requires: Level 45 ; Martial Weapon: Gain maximum Runic Ward equal to 15% of this Weapon's maximum damage ; Bonded: ; Martial Weapon: 5% increased Attack Speed while missing Runic Ward |
| Warding Rune of Obsession | Limited to: 1 ; Requires: Level 45 ; Wands: All damage taken bypasses Runic Ward, Runic Ward Regeneration Rate is doubled ; Bonded: ; Wands: 12% increased maximum Runic Ward |
| Warding Rune of Equinox | Limited to: 1 ; Requires: Level 45 ; Caster Weapon: 40% less Mana Regeneration Rate, Mana Recovery from Regeneration is also applied to Runic Ward ; Bonded: ; Caster Weapon: 20% increased Runic Ward Regeneration Rate if you've dealt a Critical Hit Recently |
| Warding Rune of Salvaging | Limited to: 1 ; Requires: Level 30 ; Sceptres: Recover 3% of maximum Runic Ward when one of your Reviving Minions is Killed ; Bonded: ; Sceptres: Recover 3% of maximum Life when one of your Minions is Revived |
| Warding Rune of Bodyguards | Limited to: 1 ; Requires: Level 45 ; Sceptres: Minions in your Presence have Onslaught while you are on Low Runic Ward ; Bonded: ; Sceptres: Damage of Enemies Hitting you is Unlucky if ; your Runic Ward has been damaged Recently |
| Warding Rune of Hollowing | Limited to: 1 ; Requires: Level 45 ; Caster Weapon: Gain 15% of maximum Life as Extra maximum Runic Ward, 15% less maximum Life ; Bonded: ; Caster Weapon: +1% to all Maximum Elemental Resistances while on full Runic Ward |
| Passion of Aldur | Socket-bound ; Weapon: Transforms all Cold and Lightning modifiers on the item into equivalent Fire modifiers ; Bonded: ; Weapon: 25% increased Fire Damage |
| Breath of Aldur | Socket-bound ; Weapon: When socketed, transforms all Fire and Lightning modifiers to equivalent Cold modifiers ; Bonded: ; Weapon: 25% increased Cold Damage |
| Ire of Aldur | Socket-bound ; Weapon: Transforms all Fire and Cold modifiers on the item into equivalent Lightning modifiers ; Bonded: ; Weapon: 25% increased Lightning Damage |
| Betrayal of Aldur | Socket-bound ; Weapon: Transforms all Fire, Cold and Lightning modifiers on the item into equivalent Chaos modifiers ; Bonded: ; Weapon: 25% increased Chaos Damage |
| Ancient Rune of Splinters | Limited to: 1 ; Requires: Level 30 ; Bows: +50% Surpassing chance to fire an additional Arrow ; Bonded: ; Bows: 30% increased Projectile Speed |
| Ancient Rune of Dueling | Limited to: 1 ; Requires: Level 30 ; Bucklers: 30% increased Parried Debuff Magnitude ; Bonded: ; Bucklers: 15% increased Block chance |
| Ancient Rune of the Titan | Limited to: 1 ; Requires: Level 30 ; Two Hand Maces: 10% chance for Slam Skills you use yourself to cause an additional Aftershock ; Bonded: ; Two Hand Maces: 15% increased Area of Effect for Attacks |
| Ancient Rune of Shattering | Limited to: 1 ; Requires: Level 30 ; One Hand Maces: 40% increased effect of Fully Broken Armour ; Bonded: ; One Hand Maces: Break 50% increased Armour |
| Ancient Rune of Prowess | Limited to: 1 ; Requires: Level 30 ; Spears: 30% chance when you gain a Charge to gain an additional Charge ; Bonded: ; Spears: 30% increased Endurance, Frenzy and Power Charge Duration |
| Ancient Rune of Control | Limited to: 1 ; Requires: Level 30 ; Quarterstaves: 50% increased Immobilisation buildup ; Bonded: ; Quarterstaves: 30% increased Damage against Immobilised Enemies |
| Ancient Rune of Discovery | Limited to: 1 ; Requires: Level 30 ; Staves: 30% chance to create an additional Remnant ; Bonded: ; Staves: +1 to maximum number of Elemental Infusions |
| Ancient Rune of Decay | Limited to: 1 ; Requires: Level 30 ; Wands: 25% increased Withered Magnitude ; Bonded: ; Wands: 15% chance that when Volatility on you explodes, you regain an equivalent amount of Volatility |
| Ancient Rune of Witchcraft | Limited to: 1 ; Requires: Level 30 ; Foci: 40% increased Area of Effect of Curses ; Bonded: ; Foci: 15% faster Curse Activation |
| Ancient Rune of the Horde | Limited to: 1 ; Requires: Level 30 ; Sceptres: Minions have 8% increased Attack and Cast Speed ; Bonded: ; Sceptres: Minions have 10% increased Movement Speed |
| Ancient Rune of Animosity | Limited to: 1 ; Requires: Level 30 ; Talismans: Gain 2 Druidic Prowess when you Heavy Stun a Rare or Unique Enemy ; Bonded: ; Talismans: 40% increased Stun Buildup |
| Ancient Rune of Detonation | Limited to: 1 ; Requires: Level 30 ; Crossbows: Grenades have 10% chance to activate a second time ; Bonded: ; Crossbows: 40% increased Crossbow Reload Speed |
| Ancient Rune of Retaliation | Limited to: 1 ; Requires: Level 30 ; Shields: 8% increased Attack Speed if you have Blocked Recently ; Bonded: ; Shields: +3% to maximum Block chance |
| Rune of Vitality | Limited to: 1 ; Requires: Level 15 ; Weapon: +80 to maximum Life ; Shields and Bucklers: Recover 15 Life when you Block ; Bonded: ; Weapon: 15% increased amount of Life Leeched ; Shields and Bucklers: 5% increased maximum Life |
| Rune of the Hunt | Limited to: 1 ; Requires: Level 15 ; Boots: 8% increased Movement Speed while Sprinting ; Sceptres: Companions deal 30% increased Damage ; Bonded: ; Boots: 50% increased Stun Recovery ; Sceptres: 8% increased Mana Recovery rate while your Companion is in your Presence |
| Rune of Acrobatics | Limited to: 1 ; Requires: Level 15 ; Weapon: Flasks gain 0.2 charges per Second ; Boots: +0.3 metres to Dodge Roll distance ; Bonded: ; Weapon: Charms gain 0.25 charges per Second ; Boots: 30% increased Armour if you haven't Dodge Rolled Recently |
| Rune of Culmination | Limited to: 1 ; Requires: Level 15 ; Gloves: 50% chance to build an additional Combo on Hit ; One Hand Mace or Quarterstaff: Rolls only the minimum or maximum Damage value for Physical Damage ; Bonded: ; Gloves: 5% increased Attack Speed ; One Hand Mace or Quarterstaff: 20% increased Bleeding Duration |
| Rune of Renown | Limited to: 1 ; Requires: Level 15 ; Gloves: 50% increased Glory generation ; Caster Weapon: Archon recovery period expires 30% faster ; Bonded: ; Gloves: Banner Skills have 20% increased Aura Magnitudes ; Caster Weapon: 30% increased Archon Buff duration |
| Rune of Accumulation | Limited to: 1 ; Requires: Level 15 ; Gloves: Gain 3 Life per Enemy Hit with Attacks, Gain 1 Mana per Enemy Hit with Attacks ; Crossbow, Bow or Spear: On Hitting an enemy, gains maximum added Cold damage equal to the enemy's Power for 20 seconds, up to a total of 32 ; Bonded: ; Gloves: +30 to maximum Life, +30 to maximum Mana ; Crossbow, Bow or Spear: 30% increased Freeze Buildup |
| Rune of Foundations | Limited to: 1 ; Requires: Level 15 ; Body Armours: +30 to Armour, +30 to Evasion Rating, +10 to maximum Energy Shield ; Bonded: ; Body Armours: +20 to maximum Life, +20 to maximum Mana |
| Rune of the Prism | Limited to: 1 ; Requires: Level 15 ; Body Armours: -10% to all Maximum Elemental Resistances, +20% to all Elemental Resistances ; Bonded: ; Body Armours: 20% of Damage is taken from Mana before Life |
| Rune of the Blossom | Limited to: 1 ; Requires: Level 15 ; Body Armours: +50 to Spirit, -1 to Spirit per 2 Levels ; Bonded: ; Body Armours: 5% increased Spirit Reservation Efficiency of Skills |
| Rune of Consistency | Limited to: 1 ; Requires: Level 15 ; Helmets: 200% increased Critical Hit Chance, You have no Critical Damage Bonus ; Caster Weapon: 50% increased Spell Damage while your Companion is in your Presence ; Bonded: ; Helmets: Hits against you have 25% reduced Critical Damage Bonus ; Caster Weapon: 8% increased Mana Recovery rate while your Companion is in your Presence |
| Rune of Reach | Limited to: 1 ; Requires: Level 15 ; Helmets: Remnants you create have 15% increased effect ; Wand or Staff: Remnants can be collected from 50% further away, Remnants you create have 25% reduced effect ; Bonded: ; Helmets: Recover 3% of Maximum Mana when you collect a Remnant ; Wand or Staff: 20% increased Exposure Effect |
| Rune of Vital Flame | Limited to: 1 ; Requires: Level 15 ; One Hand Mace, Two Hand Mace or Talisman: Adds 13 to 16 Fire Damage, 15% of Skill Mana Costs Converted to Life Costs ; Bonded: ; One Hand Mace, Two Hand Mace or Talisman: 30% increased Ignite Magnitude |
| Rune of Confrontation | Limited to: 1 ; Requires: Level 15 ; Quarterstaff or Spear: Gain 4 Rage on Melee Hit, -10 to Maximum Rage ; Bonded: ; Quarterstaff or Spear: rage effect +% [10] |
| Serle's Triumph | Limited to: 1 ; Socket-bound ; All Equipment: +1 Suffix Modifier allowed, local maximum mods allowed + [1] |
| Cadigan's Epiphany | Limited to: 1 ; Socket-bound ; Gloves: Destroys all Augment Sockets on the item to create a Jewel Socket |
| Astrid's Creativity | Limited to: 1 ; All Equipment: Can have 1 additional Crafted Modifiers |
| Uhtred's Sidereus | Limited to: 1 ; Socket-bound ; Boots: Can roll Chronomancy modifiers ; Bonded: ; Boots: 10% increased Cooldown Recovery Rate |
| Kolr's Hunt | Limited to: 1 ; Socket-bound ; Gloves: Can roll Marksman modifiers ; Bonded: ; Gloves: 20% increased Projectile Damage |
| Vorana's Carnage | Limited to: 1 ; Socket-bound ; Helmets: Can roll Berserking modifiers ; Bonded: ; Helmets: Gain 2 Rage on Melee Hit |
| Thrud's Might | Limited to: 1 ; Socket-bound ; Weapon: Can roll Destruction modifiers ; Bonded: ; Weapon: +5% to all Elemental Resistances |
| Medved's Tending | Limited to: 1 ; Socket-bound ; Body Armours: Can roll Soul modifiers ; Bonded: ; Body Armours: 3% increased maximum Life, 3% increased maximum Mana |
| Katla's Gloom | Limited to: 1 ; Socket-bound ; Gloves: Can roll Decay modifiers ; Bonded: ; Gloves: 25% reduced Effect of Non-Damaging Ailments on you |
| Aldur's Legacy | All Equipment: When socketed into a Unique Kalguuran or Ezomyte item, destroys the item to create a Rune imbued with that item's power |

### C.2 Soul cores

| Name | Text |
|---|---|
| Hayoxi's Soul Core of Heatproofing | Limited to: 1 ; Requires: Level 50 ; Helmets: +40% of Armour also applies to Cold Damage |
| Zalatl's Soul Core of Insulation | Limited to: 1 ; Requires: Level 50 ; Boots: +40% of Armour also applies to Lightning Damage |
| Topotante's Soul Core of Dampening | Limited to: 1 ; Requires: Level 50 ; Gloves: +40% of Armour also applies to Fire Damage |
| Atmohua's Soul Core of Retreat | Limited to: 1 ; Requires: Level 50 ; Body Armours: 40% increased Energy Shield from Equipped Focus ; Foci: 30% increased Energy Shield from Equipped Body Armour |
| Quipolatl's Soul Core of Flow | Limited to: 1 ; Requires: Level 50 ; Helmets: 8% increased Skill Effect Duration, 8% increased Cooldown Recovery Rate |
| Tzamoto's Soul Core of Ferocity | Limited to: 1 ; Requires: Level 50 ; Helmets: +4 to Maximum Rage |
| Uromoti's Soul Core of Attenuation | Limited to: 1 ; Requires: Level 50 ; Boots: 20% increased Curse Duration, 20% increased Poison Duration |
| Opiloti's Soul Core of Assault | Limited to: 1 ; Requires: Level 50 ; Martial Weapon: 50% chance when you gain a Frenzy Charge to gain an additional Frenzy Charge ; Wand or Staff: 50% chance when you gain a Frenzy Charge to gain an additional Frenzy Charge |
| Guatelitzi's Soul Core of Endurance | Limited to: 1 ; Requires: Level 50 ; Martial Weapon: 50% chance when you gain an Endurance Charge to gain an additional Endurance Charge ; Wand or Staff: 50% chance when you gain an Endurance Charge to gain an additional Endurance Charge |
| Xopec's Soul Core of Power | Limited to: 1 ; Requires: Level 50 ; Martial Weapon: 50% chance when you gain a Power Charge to gain an additional Power Charge ; Wand or Staff: 50% chance when you gain a Power Charge to gain an additional Power Charge |
| Estazunti's Soul Core of Convalescence | Limited to: 1 ; Requires: Level 50 ; Boots: 15% increased speed of Recoup Effects ; Helmets: 10% of Damage taken Recouped as Life |
| Tacati's Soul Core of Affliction | Limited to: 1 ; Requires: Level 50 ; Helmets: Enemies you Curse have -5% to Chaos Resistance |
| Cholotl's Soul Core of War | Limited to: 1 ; Requires: Level 50 ; Bows: Projectiles have 20% chance to Chain an additional time from terrain |
| Citaqualotl's Soul Core of Foulness | Limited to: 1 ; Requires: Level 50 ; Martial Weapon: Adds 19 to 29 Chaos damage |
| Xipocado's Soul Core of Dominion | Limited to: 1 ; Requires: Level 50 ; Wand or Staff: Minions deal 40% increased Damage with Command Skills ; Sceptres: Minions deal 40% increased Damage with Command Skills |
| Jiquani's Soul Core of Automation | Limited to: 1 ; Requires: Level 50 ; Weapon: +1 to Level of all Totem Skill Gems |
| Jiquani's Soul Core of Malediction | Limited to: 1 ; Requires: Level 50 ; Weapon: +1 to Level of all Curse Skills |
| Jiquani's Soul Core of Targeting | Limited to: 1 ; Requires: Level 50 ; Weapon: +1 to Level of all Mark Skills |
| Jiquani's Soul Core of Rallying | Limited to: 1 ; Requires: Level 50 ; Weapon: +1 to Level of all Warcry Skill Gems |
| Jiquani's Soul Core of Radiance | Limited to: 1 ; Requires: Level 50 ; Weapon: +1 to Level of all Herald Skill Gems |
| Jiquani's Soul Core of Severing | Limited to: 1 ; Requires: Level 50 ; Weapon: +1 to Level of all Strike Skill Gems |
| Jiquani's Soul Core of Rippling | Limited to: 1 ; Requires: Level 50 ; Weapon: +1 to Level of all Nova Skill Gems |
| Jiquani's Soul Core of Quaking | Limited to: 1 ; Requires: Level 50 ; Weapon: +1 to Level of all Slam Skill Gems |
| Jiquani's Soul Core of Munitions | Limited to: 1 ; Requires: Level 50 ; Weapon: +1 to Level of all Grenade Skill Gems |
| Jiquani's Soul Core of Snares | Limited to: 1 ; Requires: Level 50 ; Weapon: +1 to Level of all Hazard Skill Gems |
| Jiquani's Soul Core of Abundance | Limited to: 1 ; Requires: Level 50 ; Weapon: +1 to Level of all Plant Skill Gems |
| Jiquani's Soul Core of Squalls | Limited to: 1 ; Requires: Level 50 ; Weapon: +1 to Level of all Wind Skill Gems |
| Jiquani's Soul Core of Thundering | Limited to: 1 ; Requires: Level 50 ; Weapon: +1 to Level of all Storm Skill Gems |
| Atziri's Soul Core of Devotion | Limited to: 1 ; Requires: Level 50 ; Socket-bound ; Helmets: 1% increased Spirit for each Corrupted Item Equipped, Corrupting will always result in change |
| Atziri's Soul Core of Vitality | Limited to: 1 ; Requires: Level 50 ; Socket-bound ; Body Armours: 1% increased Maximum Life for each Corrupted Item Equipped, Corrupting will always result in change |
| Atziri's Soul Core of Alacrity | Limited to: 1 ; Requires: Level 50 ; Socket-bound ; Gloves: 1% increased Skill Speed for each Corrupted Item Equipped, Corrupting will always result in change |
| Atziri's Soul Core of Inoculation | Limited to: 1 ; Requires: Level 50 ; Socket-bound ; Boots: +2% to Chaos Resistance for each Corrupted Item Equipped, Corrupting will always result in change |
| Soul Core of Vizoma | Limited to: 1 ; Martial Weapon: +150 to Accuracy Rating ; Wand or Staff: 30% increased Critical Hit Chance for Spells |
| Soul Core of Tacati | Martial Weapon: 25% increased Magnitude of Poison you inflict ; Armour: +13% to Chaos Resistance |
| Soul Core of Opiloti | Limited to: 1 ; Martial Weapon: 40% increased Magnitude of Bleeding you inflict ; Helmets: 25% increased Pin duration |
| Soul Core of Jiquani | Limited to: 1 ; Martial Weapon: Recover 5% of maximum Life on Kill ; Body Armours: 5% increased maximum Life |
| Soul Core of Zalatl | Limited to: 1 ; Martial Weapon: Recover 4% of maximum Mana on Kill ; Helmets: 5% increased maximum Mana |
| Soul Core of Citaqualotl | Martial Weapon: 40% increased Elemental Damage with Attacks ; Armour: +6% to all Elemental Resistances |
| Soul Core of Puhuarte | Limited to: 1 ; Martial Weapon: 40% increased Ignite Magnitude ; Gloves: +2% to Maximum Fire Resistance |
| Soul Core of Tzamoto | Limited to: 1 ; Martial Weapon: 60% increased Freeze Buildup ; Helmets: +2% to Maximum Cold Resistance |
| Soul Core of Xopec | Limited to: 1 ; Martial Weapon: 25% increased Magnitude of Shock you inflict ; Boots: +2% to Maximum Lightning Resistance |
| Soul Core of Azcapa | Martial Weapon: +15 to Spirit ; Gloves: 10% increased Quantity of Gold Dropped by Slain Enemies |
| Soul Core of Topotante | Limited to: 1 ; Martial Weapon: Attacks with this Weapon Penetrate 25% Elemental Resistances ; Boots: 25% reduced Effect of Non-Damaging Ailments on you |
| Soul Core of Quipolatl | Martial Weapon: 5% increased Attack Speed ; Boots: 15% reduced Slowing Potency of Debuffs on You |
| Soul Core of Ticaba | Limited to: 1 ; Martial Weapon: +5% to Critical Damage Bonus ; Body Armours: Hits against you have 50% reduced Critical Damage Bonus ; Shields and Bucklers: Hits against you have 50% reduced Critical Damage Bonus |
| Soul Core of Atmohua | Martial Weapon: Convert 40% of Requirements to Strength ; Armour: Convert 40% of Requirements to Strength |
| Soul Core of Cholotl | Martial Weapon: Convert 40% of Requirements to Dexterity ; Armour: Convert 40% of Requirements to Dexterity |
| Soul Core of Zantipi | Martial Weapon: Convert 40% of Requirements to Intelligence ; Armour: Convert 40% of Requirements to Intelligence |

### C.3 Idols

| Name | Text |
|---|---|
| Idol of Sirrius | Limited to: 1 ; Requires: Level 50 ; Gloves: 8% increased Attack Speed ; Sceptres: Allies in your Presence have 8% increased Movement Speed ; Bonded: ; Gloves: 20% reduced Slowing Potency of Debuffs on You ; Sceptres: 4% increased Movement Speed |
| Idol of Thruldana | Limited to: 1 ; Requires: Level 50 ; Martial Weapon: 25% reduced Poison Duration, Targets can be affected by +1 of your Poisons at the same time ; Sceptres: Allies in your Presence deal 13 to 27 added Attack Chaos Damage ; Bonded: ; Martial Weapon: Gain 13% of Physical Damage as extra Chaos Damage ; Sceptres: 15% increased Withered Magnitude |
| Idol of Grold | Limited to: 1 ; Requires: Level 50 ; Boots: 50% increased total Power counted by Warcries ; Sceptres: 15% increased Damage per each different Companion in your Presence ; Bonded: ; Boots: 30% increased Glory generation ; Sceptres: 15% increased Reservation Efficiency of Companion Skills |
| Idol of Eeshta | Limited to: 1 ; Requires: Level 50 ; Helmets: 15% increased Cost Efficiency ; Sceptres: 15% increased Mana Recovery rate while your Companion is in your Presence ; Bonded: ; Helmets: Meta Skills have 15% increased Reservation Efficiency ; Sceptres: 8% increased Life Recovery Rate while your Companion is in your Presence |
| Idol of Egrin | Limited to: 1 ; Requires: Level 50 ; Helmets: Enemies you Curse take 6% increased Damage ; Sceptres: 20% increased Curse Duration ; Bonded: ; Helmets: 20% increased Area of Effect of Curses ; Sceptres: Curse zones erupt after 20% reduced delay |
| Idol of Maxarius | Limited to: 1 ; Requires: Level 50 ; Body Armours: +1 Charm Slots ; Sceptres: Flasks gain 0.2 charges per Second ; Bonded: ; Body Armours: Storm Skills have +1 to Limit ; Sceptres: 20% increased Life and Mana Recovery from Flasks |
| Idol of Ralakesh | Limited to: 1 ; Requires: Level 50 ; Helmets: 8% increased Reservation Efficiency of Minion Skills ; Sceptres: 40% increased Armour, Evasion and Energy Shield while your Companion is in your Presence ; Bonded: ; Helmets: Minions Revive 8% faster ; Sceptres: Companions have 25% increased maximum Life |
| Idol of Greust | Limited to: 1 ; Requires: Level 50 ; Shields: +25% of Armour also applies to Elemental Damage ; Bucklers: Gain Deflection Rating equal to 20% of Evasion Rating ; Sceptres: Companions deal 10% more Damage for each different type of dead Companion you have ; Bonded: ; Shields: 12% increased Damage for each type of Elemental Ailment on Enemy ; Bucklers: 12% increased Damage for each type of Elemental Ailment on Enemy ; Sceptres: Recover 3% of maximum Life when one of your Minions is Revived |
| Idol of Yeena | Limited to: 1 ; Requires: Level 50 ; Boots: 30% increased Skill Effect Duration with Plant Skills ; Sceptres: Plants have a 25% chance to immediately Overgrow when they enter your Presence for the first time ; Bonded: ; Boots: Plants have a 25% chance to immediately Overgrow when they enter your Presence for the first time ; Sceptres: 30% increased Skill Effect Duration with Plant Skills |
| Idol of Eramir | Limited to: 1 ; Requires: Level 50 ; Body Armours: Skills have 10% chance to not remove Charges but still count as consuming them ; Sceptres: Allies in your Presence share Charges with you ; Bonded: ; Body Armours: 15% chance for Charms you use to not consume Charges ; Sceptres: 25% increased Endurance, Frenzy and Power Charge Duration |
| Idol of Oak | Limited to: 1 ; Requires: Level 50 ; Boots: 15% chance when you gain an Endurance Charge to gain an additional Endurance Charge ; Sceptres: If you would gain an Endurance Charge, Allies in your Presence gain that Charge instead ; Bonded: ; Boots: +1 to Maximum Endurance Charges ; Sceptres: 40% increased Armour if you've consumed an Endurance Charge Recently |
| Idol of Alira | Limited to: 1 ; Requires: Level 50 ; Helmets: 15% chance when you gain a Power Charge to gain an additional Power Charge ; Sceptres: If you would gain a Power Charge, Allies in your Presence gain that Charge instead ; Bonded: ; Helmets: +1 to Maximum Power Charges ; Sceptres: 40% increased maximum Energy Shield if you've consumed a Power Charge Recently |
| Idol of Kraityn | Limited to: 1 ; Requires: Level 50 ; Gloves: 15% chance when you gain a Frenzy Charge to gain an additional Frenzy Charge ; Sceptres: If you would gain a Frenzy Charge, Allies in your Presence gain that Charge instead ; Bonded: ; Gloves: +1 to Maximum Frenzy Charges ; Sceptres: 40% increased Evasion Rating if you've consumed a Frenzy Charge Recently |
| Idol of Silk | Limited to: 1 ; Requires: Level 50 ; Shields: 15% increased Block chance while your Companion is in your Presence ; Bucklers: companions gain onslaught when you parry [1] ; Sceptres: Companions in your Presence gain 1 Rage on hit ; Bonded: ; Shields: +3% to maximum Block chance ; Bucklers: 30% increased Parry Range ; Sceptres: Companions have 30% increased Area of Effect |
| Idol of the Sycophant | Limited to: 1 ; Requires: Level 50 ; Martial Weapon, Wand or Staff: -20% to all Elemental Resistances, Gain 20% of Damage as Extra Damage of a random Element ; Sceptres: Companions in your Presence have -20% to all Elemental Resistances, Companions in your Presence Gain 20% of Damage as Extra Damage of a random Element ; Bonded: ; Martial Weapon, Wand or Staff: -20% to Chaos Resistance, Gain 20% of Damage as Extra Chaos Damage ; Sceptres: Allies in your Presence Gain 20% of Damage as Extra Chaos Damage, Companions in your Presence have -20% to Chaos Resistance |
| Idol of the Martyr | Limited to: 1 ; Requires: Level 50 ; Martial Weapon, Wand or Staff: 25% reduced Spirit, Meta Skills gain 40% increased Energy ; Sceptres: 40% reduced Presence Area of Effect, Aura Skills have 25% increased Magnitudes ; Bonded: ; Martial Weapon, Wand or Staff: Invocated skills have 25% increased Maximum Energy, Meta Skills have 25% reduced Reservation Efficiency ; Sceptres: Allies in your Presence Regenerate 3% of your Maximum Life per second, 25% reduced Life Regeneration rate |
| Idol of the Pharisee | Limited to: 1 ; Requires: Level 50 ; Martial Weapon, Wand or Staff: 30% reduced maximum Mana, Gain 2% of Damage as Extra Physical Damage per ten percent missing Mana ; Sceptres: 30% reduced Mana Cost Efficiency of Command Skills, Minions deal 60% increased Damage with Command Skills ; Bonded: ; Martial Weapon, Wand or Staff: 30% reduced Mana Cost Efficiency, 12% increased Skill Speed while on Low Mana ; Sceptres: 25% reduced Reservation Efficiency of Minion Skills, Temporary Minion Skills have +2 to Limit of Minions summoned |
| Panther Idol | Limited to: 1 ; Requires: Level 50 ; Body Armours: +10% of Armour also applies to Chaos Damage ; Sceptres: Minions have +20% to Chaos Resistance ; Bonded: ; Body Armours: +8% to Chaos Resistance ; Sceptres: Minions have 20% additional Physical Damage Reduction |
| Hawk Idol | Limited to: 1 ; Requires: Level 50 ; Body Armours: 10% increased Deflection Rating ; Sceptres: Companions have 12% increased Attack Speed ; Bonded: ; Body Armours: +12% to Cold Resistance ; Sceptres: 8% increased Attack Speed while your Companion is in your Presence |
| Stoat Idol | Limited to: 1 ; Requires: Level 50 ; Body Armours: 5% of Damage taken bypasses Energy Shield ; Sceptres: Companions have 25% increased maximum Life ; Bonded: ; Body Armours: +12% to Lightning Resistance ; Sceptres: 25% increased Damage while your Companion is in your Presence |
| Snake Idol | Gloves: 8% increased Curse Magnitudes ; Sceptres: Allies in your Presence have 10% increased Attack Speed ; Bonded: ; Gloves: Remnants you create have 15% increased effect ; Sceptres: 10% increased Skill Speed while Shapeshifted |
| Primate Idol | Helmets: Minions have 15% increased maximum Life ; Sceptres: Allies in your Presence deal 40% increased Damage ; Bonded: ; Helmets: Remnants can be collected from 30% further away ; Sceptres: 40% increased Damage while Shapeshifted |
| Owl Idol | Foci: 12% increased Cooldown Recovery Rate ; Sceptres: Allies in your Presence have 10% increased Cast Speed ; Bonded: ; Foci: 20% increased effect of Archon Buffs on you ; Sceptres: 10% increased Skill Speed while Shapeshifted |
| Cat Idol | Gloves: 25% increased Accuracy Rating ; Sceptres: Allies in your Presence have 14% increased Critical Hit Chance ; Bonded: ; Gloves: 30% increased Charm Charges gained ; Sceptres: 25% increased Critical Hit Chance while Shapeshifted |
| Wolf Idol | Gloves: 15% increased Magnitude of Bleeding you inflict ; Sceptres: Allies in your Presence have 20% increased Critical Damage Bonus ; Bonded: ; Gloves: 25% reduced Magnitude of Bleeding on You ; Sceptres: 25% increased Critical Hit Chance while Shapeshifted |
| Stag Idol | Limited to: 1 ; Helmets: Projectiles have 15% chance to Fork ; Sceptres: Allies in your Presence deal 1 to 40 added Attack Lightning Damage ; Bonded: ; Helmets: Projectiles have 25% chance for an additional Projectile when Forking ; Sceptres: 40% increased Attack Damage while Shapeshifted |
| Boar Idol | Gloves: Gain 1 Rage on Melee Hit ; Sceptres: Allies in your Presence Regenerate 0.5% of your Maximum Life per second ; Bonded: ; Gloves: 25% increased Warcry Cooldown Recovery Rate ; Sceptres: 25% increased Life Regeneration rate while Shapeshifted |
| Bear Idol | Helmets: 10% increased Area of Effect ; Sceptres: Allies in your Presence deal 12 to 18 added Attack Physical Damage ; Bonded: ; Helmets: 12% increased Reservation Efficiency of Companion Skills ; Sceptres: 40% increased Attack Damage while Shapeshifted |
| Ox Idol | Shields and Bucklers: 15% increased Block chance ; Sceptres: Allies in your Presence have +12% to all Elemental Resistances ; Bonded: ; Shields and Bucklers: 15% chance for Damage of Enemies Hitting you to be Unlucky ; Sceptres: +20% of Armour also applies to Elemental Damage while Shapeshifted |
| Rabbit Idol | Limited to: 1 ; Body Armours: 12% increased Rarity of Items found ; Sceptres: 15% increased Spirit ; Bonded: ; Body Armours: 10% increased Quantity of Gold Dropped by Slain Enemies ; Sceptres: Minions have 30% increased Cooldown Recovery Rate for Command Skills |
| Fox Idol | Limited to: 1 ; Body Armours: Idols socketed in this item gain the benefits of their Bonded modifiers, display additional socketable mods for idols [1] ; Sceptres: 50% increased Presence Area of Effect ; Bonded: ; Body Armours: +5% to Quality of all Skills ; Sceptres: Minions have 30% increased Area of Effect |

### C.4 Abyssal Eyes

| Name | Text |
|---|---|
| Amanamu's Gaze | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Helmets: Remove a Damaging Ailment when you use a Command Skill ; Body Armours: +2 to Armour per 1 Spirit ; Boots: 1% increased Movement Speed per 15 Spirit, up to a maximum of 40% ; Other Modifiers to Movement Speed except for Sprinting do not apply |
| Tecrod's Gaze | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Body Armours: Regenerate 1.5% of maximum Life per second ; Gloves: 25% increased Life Cost Efficiency ; Boots: 10% increased Movement Speed when on Low Life |
| Kurgal's Gaze | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Helmets: Increases and Reductions to Life Regeneration Rate also apply to Mana Regeneration Rate ; Gloves: 40% increased effect of Arcane Surge on you ; Boots: 15% increased Mana Cost Efficiency if you haven't Dodge Rolled Recently |
| Ulaman's Gaze | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Helmets: +1 to Accuracy Rating per 1 Item Evasion Rating on Equipped Helmet ; Gloves: Critical Hit chance is Lucky against Parried enemies ; Body Armours: Prevent +3% of Damage from Deflected Hits |

### C.5 Vaal Theses (soul-core class, Ancient Augment)

| Name | Text |
|---|---|
| Guatelitzi's Thesis | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Helmets: Gain Armour equal to 35% of Life Lost from Hits in the past 8 seconds ; Body Armours: 10% of Physical Damage prevented Recouped as Life ; Boots: Lose 5% of maximum Life per second while Sprinting, 25% increased Movement Speed while Sprinting |
| Citaqualotl's Thesis | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Body Armours: You Recoup 50% of Damage taken by your Offerings as Life ; Gloves: One of your Persistent Minions revives when an Offering expires ; Boots: Sacrifice 10% of maximum Life to gain that much Guard when you Dodge Roll |
| Jiquani's Thesis | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Helmets: +1 to maximum Mana per 3 Item Armour on Equipped Helmet ; Gloves: Energy Shield Recharge starts after spending a total of ; 2000 Mana, no more than once every 2 seconds ; Boots: Increases and Reductions to Movement Speed also ; apply to Energy Shield Recharge Rate |
| Quipolatl's Thesis | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Helmets: A random Skill that requires Glory generates 50% of its maximum Glory when your Marks Activate ; Gloves: Your Energy Shield Recharge starts when your Minions are Reformed ; Body Armours: +75% of Armour also applies to Chaos Damage while on full Energy Shield |

### C.6 Emergent and Carved ancient augments

| Name | Text |
|---|---|
| Emergent Vigour | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Helmets: +1 to maximum Life per 8 Armour on Equipped Helmet ; Body Armours: Gain Maximum Energy Shield equal to 50% of total ; Strength Requirements of Equipped Armour Items ; Boots: Hits against you have no Critical Damage Bonus while on Consecrated Ground ; Bonded: ; Helmets: +20 to Spirit ; Body Armours: +20 to Strength ; Boots: 20% increased Effect of Consecrated Ground you create |
| Emergent Possibility | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Body Armours: 15% of Chaos Damage from Hits taken as Damage of a random Element ; Gloves: Gain 1% of Damage as Extra Damage of a random Element per ; Rune Socketed in Equipped Items ; Boots: 50% increased Runic Ward Regeneration Rate while Sprinting ; Bonded: ; Body Armours: +13% to Chaos Resistance ; Gloves: 20% increased Elemental Damage ; Boots: 15% increased Runic Ward Cost Efficiency |
| Emergent Protection | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Helmets: Gain 1 Endurance Charge on reaching Low Life, only once every 2 seconds ; Gloves: Banners also grant 2% of Life Regenerated per second to affected targets ; Boots: When you stop Sprinting, gain Guard equal to 4% of maximum Life per second spent Sprinting, up to a maximum of 20%, for 4 seconds ; Bonded: ; Helmets: 40% increased Endurance Charge Duration ; Gloves: Regenerate 0.5% of maximum Life per second ; Boots: 20% increased Guard gained |
| Emergent Instinct | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Helmets: Targets that are Blinded, Maimed, and Bleeding cannot Evade your Hits ; Gloves: Regenerate 5% of maximum Life per Second if you have used a Command Skill Recently ; Body Armours: Thorns Damage is Lucky against targets with Fully Broken Armour ; Bonded: ; Helmets: 30% increased Immobilisation buildup ; Gloves: 20% increased Life Regeneration rate ; Body Armours: 30% increased Thorns damage |
| Carved Cunning | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Helmets: Enemies which are on Full Life cannot Evade your Hits ; Body Armours: Prevent +5% of Damage from Deflected Hits if you've ; Deflected no Hits Recently ; Boots: Gain Onslaught for 4 seconds when your Marks Activate ; Bonded: ; Helmets: 30% increased Accuracy Rating ; Body Armours: 8% increased Deflection Rating ; Boots: Buffs on you expire 10% slower |
| Carved Majesty | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Body Armours: +3 to Spirit per Idol socketed in your Equipment ; Gloves: Companions gain Onslaught for 4 seconds on Hitting your Marked targets ; Boots: 1% increased Movement Speed while Sprinting per Persistent Minion ; Bonded: ; Body Armours: 5% increased Spirit ; Gloves: Companions deal 30% increased Damage ; Boots: Minions have 12% increased maximum Life |
| Carved Mischief | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Helmets: Gain Guard equal to 10% of maximum Life for 4 seconds on taking Savage Hit ; Gloves: +5% to maximum Block chance if you've Blocked with a raised Shield Recently ; Body Armours: 200% increased Stun Threshold if you've been Stunned Recently ; Bonded: ; Helmets: Buffs on you expire 10% slower ; Gloves: 20% increased Block chance ; Body Armours: 25% increased Stun Threshold |
| Carved Tenacity | Limited to: 1 Ancient Augment ; Requires: Level 60 ; Helmets: Enemies have no Critical Damage Bonus for 4 seconds after you Blind them ; Gloves: Enemies you Critically Hit get 100% reduced Life Regeneration Rate for 4 seconds ; Boots: Your speed is Unaffected by Slows while Sprinting ; Bonded: ; Helmets: 20% increased Blind Effect ; Gloves: 15% increased Critical Hit Chance ; Boots: 8% increased Movement Speed while Sprinting |

### C.7 Aldur's Legacies (runes made from Kalguuran/Ezomyte uniques)

| Name | Text |
|---|---|
| Legacy of Bramblejack | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Body Armours: 250% of Melee Physical Damage taken reflected to Attacker ; Bonded: ; Body Armours: Regenerate 3% of maximum Life per second while Surrounded |
| Legacy of Blackbraid | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Body Armours: +50% of Armour also applies to Elemental Damage ; Bonded: ; Body Armours: +15% to all Elemental Resistances |
| Legacy of Edyrn's Tusks | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Body Armours: 50% chance to inflict Bleeding on Hit, 50% reduced Slowing Potency of Debuffs on You ; Bonded: ; Body Armours: 35% increased Thorns damage |
| Legacy of Kingsguard | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Body Armours: Recover 5% of maximum Life for each Endurance Charge consumed ; Bonded: ; Body Armours: +30 to maximum Life |
| Legacy of Bristleboar | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Body Armours: Gain 10 Rage when Critically Hit by an Enemy, Gain 5 Rage when Hit by an Enemy ; Bonded: ; Body Armours: +3 to Maximum Rage |
| Legacy of Foxshade | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Body Armours: 10% increased Movement Speed when on Full Life, 100% increased Evasion Rating when on Full Life ; Bonded: ; Body Armours: 20% increased Evasion Rating |
| Legacy of Ashrend | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Body Armours: Cannot be Ignited, -10 Physical Damage taken from Attack Hits ; Bonded: ; Body Armours: +35% to Fire Resistance |
| Legacy of Briskwrap | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Body Armours: Gain Deflection Rating equal to 30% of Evasion Rating ; Bonded: ; Body Armours: 35% increased Flask Mana Recovery rate |
| Legacy of The Unleashed | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Body Armours: 25% of Damage taken from Hits bypasses Energy Shield if Energy Shield is below half ; Bonded: ; Body Armours: 20% increased Armour while Shapeshifted |
| Legacy of Horns of Bynden | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Helmets: Every Rage also grants 1% increased Armour, Gain 1 Rage on Melee Hit ; Bonded: ; Helmets: +3 to Maximum Rage |
| Legacy of Wings of Caelyn | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Helmets: Gain 1 Rage on Melee Hit, Every Rage also grants 1% increased Stun Threshold ; Bonded: ; Helmets: Every five Rage also grants you 1% increased Movement Speed |
| Legacy of Ezomyte Peak | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Helmets: 15% increased Area of Effect, Unwavering Stance ; Bonded: ; Helmets: 50% reduced Slowing Potency of Debuffs on You |
| Legacy of Deidbell | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Helmets: Warcries Explode Corpses dealing 10% of their Life as Physical Damage ; Bonded: ; Helmets: Warcry Skills have 20% increased Area of Effect |
| Legacy of Elevore | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Helmets: Charms gain 1 charge per Second, +1 Charm Slots ; Bonded: ; Helmets: Charms gain 0.5 charges per Second |
| Legacy of Starkonja's Head | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Helmets: 100% increased Global Evasion Rating when on Low Life, 5% of Damage from Hits is taken from your Damageable Companion's Life before you ; Bonded: ; Helmets: 5% of Damage from Hits is taken from your Damageable Companion's Life before you |
| Legacy of Crown of Thorns | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Helmets: Pain Attunement ; Bonded: ; Helmets: 17 to 26 Physical Thorns damage |
| Legacy of Greymake | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Helmets: +50 to all Attributes ; Bonded: ; Helmets: +1 Maximum Life per Level |
| Legacy of Erian's Cobble | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Helmets: +30 to Accuracy Rating, +10 to maximum Life, +10 to maximum Mana, 10% increased Rarity of Items found, 10% increased Critical Hit Chance, +5 to all Attributes, +5% to all Elemental Resistances, 3 Life Regeneration per second ; Bonded: ; Helmets: +20 to Armour, +20 to Evasion Rating, +20 to maximum Energy Shield |
| Legacy of The Smiling Knight | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Helmets: Aggravate Bleeding on targets you Critically Hit with Attacks ; Bonded: ; Helmets: 20% increased Critical Hit Chance |
| Legacy of The Vile Knight | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Helmets: Deal 4% increased Damage with Hits to Rare or Unique Enemies for each second they've ever been in your Presence, up to a maximum of 200% ; Bonded: ; Helmets: 20% increased Presence Area of Effect |
| Legacy of Northpaw | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Gloves: Base Critical Hit Chance for Attacks with Weapons is 7% ; Bonded: ; Gloves: 15% increased Critical Damage Bonus |
| Legacy of Candlemaker | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Gloves: 40% increased Fire Damage, Flammability Magnitude is doubled ; Bonded: ; Gloves: 20% increased Ignite Duration on Enemies |
| Legacy of Deathblow | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Gloves: Culling Strike ; Bonded: ; Gloves: Gain 30 Life per enemy killed |
| Legacy of Legionstride | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Boots: +10% to Block chance ; Bonded: ; Boots: 10% reduced Damage taken from Projectile Hits |
| Legacy of Trampletoe | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Boots: Deal 10% of Overkill damage to enemies within 2 metres of the enemy killed ; Bonded: ; Boots: 15% increased Global Physical Damage |
| Legacy of Briarpatch | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Boots: +15% to Thorns Critical Hit Chance ; Bonded: ; Boots: 15% increased Thorns Critical Damage Bonus |
| Legacy of Bushwhack | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Boots: Physical Damage is Pinning ; Bonded: ; Boots: +20 to Dexterity |
| Legacy of Wanderlust | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Boots: Your speed is unaffected by Slows ; Bonded: ; Boots: 5% increased Movement Speed |
| Legacy of The Knight-errant | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Boots: Iron Reflexes ; Bonded: ; Boots: 25% increased Elemental Ailment Threshold |
| Legacy of Obern's Bastion | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Boots: 200% increased Stun Recovery ; Bonded: ; Boots: 40% reduced Chill Duration on you, 40% reduced Freeze Duration on you |
| Legacy of Dionadair | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Shields: Double Stun Threshold while Shield is Raised ; Bonded: ; Shields: 15% increased Stun Threshold |
| Legacy of Wulfsbane | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Shields: Intimidate Enemies on Block for 8 seconds ; Bonded: ; Shields: +25 to Strength |
| Legacy of Chernobog's Pillar | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Shields: Gain 1% of damage as Fire damage per 2% Chance to Block ; Bonded: ; Shields: +30% to Chaos Resistance |
| Legacy of Alkem Eira | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Shields: 30% of damage Blocked is Recouped as Mana ; Bonded: ; Shields: 20% of damage Blocked is Recouped as Mana |
| Legacy of Oaksworn | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Shields: 50% increased Life Regeneration rate ; Bonded: ; Shields: 50 Life Regeneration per second |
| Legacy of Dunkelhalt | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Bucklers: 50% increased Parried Debuff Magnitude ; Bonded: ; Bucklers: 50% increased Parry Damage |
| Legacy of Rondel de Ezo | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Bucklers: Curse Enemies with Enfeeble on Block ; Bonded: ; Bucklers: 100% increased Block chance against Projectiles |
| Legacy of Brynhand's Mark | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; One Hand Maces: Causes Double Stun Buildup ; Bonded: ; One Hand Maces: Adds 14 to 20 Physical Damage |
| Legacy of Trenchtimbre | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; One Hand Maces: Increases and Reductions to Minion Attack Speed also affect you ; Bonded: ; One Hand Maces: +1 to Level of all Minion Skills |
| Legacy of Mjölner | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; One Hand Maces: +200 Intelligence Requirement, +3 to Level of all Lightning Skills ; Bonded: ; One Hand Maces: +1 to Level of all Lightning Skills |
| Legacy of Twisted Empyrean | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Two Hand Maces: Attacks with this Weapon have Added Cold Damage equal to 6% to 10% of maximum Mana ; Bonded: ; Two Hand Maces: 15% of Damage is taken from Mana before Life |
| Legacy of Hoghunt | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Two Hand Maces: +5% to Critical Hit Chance, Maim on Critical Hit ; Bonded: ; Two Hand Maces: 25% increased Attack Damage against Maimed Enemies |
| Legacy of Hrimnor's Hymn | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Two Hand Maces: 25% chance for Slam Skills you use yourself to cause an additional Aftershock ; Bonded: ; Two Hand Maces: 15% chance for Slam Skills you use yourself to cause an additional Aftershock |
| Legacy of Brain Rattler | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Two Hand Maces: All damage with this Weapon causes Electrocution buildup ; Bonded: ; Two Hand Maces: Damage Penetrates 10% Lightning Resistance |
| Legacy of Lifesprig | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Wands: +2 to Level of all Spell Skills ; Bonded: ; Wands: Leeches 1% of maximum Life when you Cast a Spell |
| Legacy of Duality | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Quarterstaves: Gain 250 Guard for 0.5 seconds per Combo expended when using Skills ; Bonded: ; Quarterstaves: Gain Finality for 0.2 seconds per Combo expended when using Skills |
| Legacy of Tyranny's Grip | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Spears: Strikes deal Splash Damage ; Bonded: ; Spears: Knocks Enemies Back on Hit |
| Legacy of The Sentry | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Quarterstaves: Adds 23 to 34 Fire damage to Attacks, 100% increased Flammability Magnitude ; Bonded: ; Quarterstaves: +2% to Maximum Fire Resistance |
| Legacy of Adonia's Ego | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Wands: +1 to Maximum Power Charges ; Bonded: ; Wands: +65 to maximum Mana |
| Legacy of Cursecarver | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Wands: +3 to Level of all Curse Skills ; Bonded: ; Wands: 35% increased Mana Regeneration Rate |
| Legacy of Dusk Vigil | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Staves: Gain 30% of Physical Damage as Extra Fire Damage ; Bonded: ; Staves: Triggered Spells deal 20% increased Spell Damage |
| Legacy of The Blood Thorn | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Quarterstaves: Adds 4 to 8 Physical Damage, Causes Bleeding on Hit ; Bonded: ; Quarterstaves: 10% increased Magnitude of Bleeding you inflict |
| Legacy of Quill Rain | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Bows: 50% increased Attack Speed, 20% less Attack Damage ; Bonded: ; Bows: 70% increased Arrow Speed |
| Legacy of Ironbound | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Bows: Hits with this weapon have 1 to 3 Added Physical Damage per 1% Block Chance ; Bonded: ; Bows: 3% increased Block chance per 100 total Item Armour on Equipped Armour Items |
| Legacy of Amor Mandragora | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Talismans: Gain 1 Druidic Prowess for every 20 total Rage spent ; Bonded: ; Talismans: Enemies in your Presence are Hindered |
| Legacy of Spiteful Floret | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Talismans: Every 5 Rage also grants 5% of Damage taken Recouped as Life ; Bonded: ; Talismans: Attacks have 20% chance to cause Bleeding |
| Legacy of Svalinn | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Shields: Chance to Block Damage is Lucky, You take 20% of damage from Blocked Hits ; Bonded: ; Shields: +50 to maximum Runic Ward |
| Legacy of Keeper of the Arc | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Helmets: Alternating every 5 seconds: ; Take 20% less Damage from Hits ; Take 20% less Damage over time ; Bonded: ; Helmets: 25% increased Mana Regeneration Rate |
| Legacy of Olrovasara | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; One Hand Maces: On Hitting an enemy, gains maximum added Lightning damage equal to ; the enemy's Power for 20 seconds, up to a total of 120 ; Bonded: ; One Hand Maces: 15% increased Attack Speed |
| Legacy of A Worthy Foe | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Shields: Off-hand Hits inflict Runefather's Challenge ; Bonded: ; Shields: +45% to Cold Resistance |
| Legacy of Serle's Grit | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; One Hand Maces: Maximum Quality is 40% ; Bonded: ; One Hand Maces: Skills which Empower an Attack have 20% chance to not count that Attack |
| Legacy of Runeseeker's Call | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Wands: 75% increased effect of Socketed Runes ; Bonded: ; Wands: +100 to maximum Mana |
| Legacy of Facebreaker | Limited to: 1 Aldur's Legacy ; Requires: Level 65 ; Gloves: +1 to Armour per Strength ; Bonded: ; Gloves: 1% increased Damage per 15 Strength |

### C.8 Congealed Mist

| Name | Text |
|---|---|
| Raven-Touched Shard | Limited to: 1 ; Requires: Level 60 ; Socket-bound ; Helmets: Raven-Touched |

## Appendix D. Corruption enchantments (implicits) by item tag

Source S11 (RePoE-fork 0.5.5.10 mods, generation_type corrupted, tags with weight > 0). Tags: str_armour etc. = armour bases by attribute; warstaff = quarterstaff. Columns: domain | text | tags | required level | mod id.

| Domain | Text | Tags | Level | Id |
|---|---|---|---|---|
| item | (10-15) Mana gained when you Block | shield | 1 | CorruptionGainManaOnBlock1 |
| item | (10-15)% chance to Maim on Hit | bow,crossbow | 1 | CorruptionLocalChanceToMaim1 |
| item | (10-15)% chance to Poison on Hit with this weapon | sword,spear,dagger,warstaff | 1 | CorruptionLocalChanceToPoison1 |
| item | (10-15)% chance to cause Bleeding on Hit | mace,sword,axe,flail | 1 | CorruptionLocalChanceToBleed1 |
| item | (10-15)% increased Block chance | shield | 1 | CorruptionLocalBlockChance1 |
| item | (10-15)% increased Cast Speed | wand,staff | 1 | CorruptionIncreasedCastSpeed1 |
| item | (10-15)% increased Rarity of Items found | ring,amulet | 1 | CorruptionItemFoundRarityIncrease1 |
| item | (10-20)% increased Melee Strike Range with this weapon | mace,sword,axe,flail,warstaff,dagger,spear | 1 | CorruptionLocalWeaponRangeIncrease1 |
| item | (10-20)% of Damage taken Recouped as Life | body_armour | 1 | CorruptionDamageTakenGainedAsLife1 |
| item | (10-20)% of Damage taken Recouped as Mana | body_armour | 1 | CorruptionDamageTakenGainedAsMana1 |
| item | (15-20)% increased Critical Damage Bonus | ring,quiver | 1 | CorruptionCriticalStrikeMultiplier1 |
| item | (15-25)% increased Armour | belt | 1 | CorruptionIncreasedPhysicalDamageReductionRatingPercent1 |
| item | (15-25)% increased Armour | str_armour | 1 | CorruptionLocalIncreasedPhysicalDamageReductionRatingPercent1 |
| item | (15-25)% increased Armour and Energy Shield | str_int_armour | 1 | CorruptionLocalIncreasedArmourAndEnergyShield1 |
| item | (15-25)% increased Armour and Evasion | str_dex_armour | 1 | CorruptionLocalIncreasedArmourAndEvasion1 |
| item | (15-25)% increased Energy Shield | int_armour | 1 | CorruptionLocalIncreasedEnergyShieldPercent1 |
| item | (15-25)% increased Evasion Rating | belt | 1 | CorruptionIncreasedEvasionRatingPercent1 |
| item | (15-25)% increased Evasion Rating | dex_armour | 1 | CorruptionLocalIncreasedEvasionRatingPercent1 |
| item | (15-25)% increased Evasion and Energy Shield | dex_int_armour | 1 | CorruptionLocalIncreasedEvasionAndEnergyShield1 |
| item | (15-25)% increased Life Regeneration rate | helmet,ring | 1 | CorruptionLifeRegenerationRate1 |
| item | (15-25)% increased Physical Damage | weapon | 1 | CorruptionLocalIncreasedPhysicalDamagePercent1 |
| item | (15-25)% increased Spirit | sceptre | 1 | CorruptionLocalIncreasedSpiritPercent1 |
| item | (15-25)% increased maximum Energy Shield | belt | 1 | CorruptionIncreasedEnergyShieldPercent1 |
| item | (20-10)% reduced Attribute Requirements | armour,weapon,wand,staff,sceptre | 1 | CorruptionReducedLocalAttributeRequirements1 |
| item | (20-25) Life gained when you Block | shield | 1 | CorruptionGainLifeOnBlock1 |
| item | (20-30)% chance to Pierce an Enemy | quiver | 1 | CorruptionChanceToPierce1 |
| item | (20-30)% increased Critical Hit Chance for Spells | wand,staff | 1 | CorruptionSpellCriticalStrikeChance1 |
| item | (20-30)% increased Damage | ring,quiver | 1 | CorruptionAllDamage1 |
| item | (20-30)% increased Elemental Damage with Attacks | bow,one_hand_weapon | 1 | CorruptionWeaponElementalDamage1 |
| item | (20-30)% increased Flammability Magnitude | wand,staff | 1 | CorruptionIgniteChanceIncrease1 |
| item | (20-30)% increased Freeze Buildup | wand,staff | 1 | CorruptionFreezeDamageIncrease1 |
| item | (20-30)% increased Freeze Threshold | boots | 1 | CorruptionIncreasedFreezeThreshold1 |
| item | (20-30)% increased Mana Regeneration Rate | helmet,ring | 1 | CorruptionManaRegeneration1 |
| item | (20-30)% increased Spell Damage | wand,focus | 1 | CorruptionSpellDamageOnWeapon1 |
| item | (20-30)% increased Stun Threshold | boots | 1 | CorruptionIncreasedStunThreshold1 |
| item | (20-30)% increased chance to Shock | wand,staff | 1 | CorruptionShockChanceIncrease1 |
| item | (3-5)% additional Physical Damage Reduction | body_armour | 1 | CorruptionAdditionalPhysicalDamageReduction1 |
| item | (3-5)% increased Movement Speed | boots | 1 | CorruptionMovementVelocity1 |
| item | (30-20)% reduced Slowing Potency of Debuffs on You | boots | 1 | CorruptionSlowPotency1 |
| item | (4-6)% increased Skill Speed | ring,quiver | 1 | CorruptionIncreasedSkillSpeed1 |
| item | (40-50)% increased Elemental Damage with Attacks | two_hand_weapon | 1 | CorruptionWeaponElementalDamageTwoHand1 |
| item | (40-50)% increased Thorns damage | body_armour,shield | 1 | CorruptionThornsDamageIncrease1 |
| item | (40-60)% increased Spell Damage | staff | 1 | CorruptionSpellDamageOnTwoHandWeapon1 |
| item | (5-10)% chance to Blind Enemies on hit | bow,crossbow | 1 | CorruptionLocalChanceToBlind1 |
| item | (5-10)% increased Quantity of Gold Dropped by Slain Enemies | gloves | 1 | CorruptionGoldFoundIncrease1 |
| item | (6-8)% increased Attack Speed | weapon | 1 | CorruptionLocalIncreasedAttackSpeed1 |
| item | +(1-3)% to Maximum Cold Resistance | helmet | 1 | CorruptionMaximumColdResistance1 |
| item | +(1-3)% to Maximum Fire Resistance | belt | 1 | CorruptionMaximumFireResistance1 |
| item | +(1-3)% to Maximum Lightning Resistance | boots | 1 | CorruptionMaximumLightningResistance1 |
| item | +(10-15) to Dexterity | belt,ring,amulet | 1 | CorruptionDexterity1 |
| item | +(10-15) to Intelligence | belt,ring,amulet | 1 | CorruptionIntelligence1 |
| item | +(10-15) to Strength | belt,ring,amulet | 1 | CorruptionStrength1 |
| item | +(13-19)% to Chaos Resistance | body_armour,ring | 1 | CorruptionChaosResistance1 |
| item | +(20-25) to maximum Mana | focus,quiver,ring | 1 | CorruptionIncreasedMana1 |
| item | +(20-25)% to Cold Resistance | boots,belt | 1 | CorruptionColdResistance1 |
| item | +(20-25)% to Fire Resistance | boots,belt | 1 | CorruptionFireResistance1 |
| item | +(20-25)% to Lightning Resistance | boots,belt | 1 | CorruptionLightningResistance1 |
| item | +(20-30) to Spirit | helmet | 1 | CorruptionIncreasedSpirit1 |
| item | +(30-40) to maximum Life | body_armour,belt | 1 | CorruptionIncreasedLife1 |
| item | +(5-10)% to Critical Damage Bonus | weapon | 1 | CorruptionLocalCriticalStrikeMultiplier1 |
| item | +(5-10)% to all Elemental Resistances | ring,amulet | 1 | CorruptionAllResistances1 |
| item | +(50-100) to Accuracy Rating | helmet,quiver | 1 | CorruptionIncreasedAccuracy1 |
| item | +1 to Level of all Chaos Spell Skills | wand,staff | 1 | CorruptionGlobalChaosSpellGemsLevel1 |
| item | +1 to Level of all Cold Spell Skills | wand,staff | 1 | CorruptionGlobalColdSpellGemsLevel1 |
| item | +1 to Level of all Fire Spell Skills | wand,staff | 1 | CorruptionGlobalFireSpellGemsLevel1 |
| item | +1 to Level of all Lightning Spell Skills | wand,staff | 1 | CorruptionGlobalLightningSpellGemsLevel1 |
| item | +1 to Level of all Melee Skills | gloves | 1 | CorruptionGlobalMeleeSkillGemsLevel1 |
| item | +1 to Level of all Minion Skills | helmet | 1 | CorruptionGlobalMinionSkillGemsLevel1 |
| item | +1 to Level of all Physical Spell Skills | wand,staff | 1 | CorruptionGlobalPhysicalSpellGemsLevel1 |
| item | +1 to Level of all Skills | amulet | 1 | CorruptionGlobalSkillGemLevel1 |
| item | +1 to Maximum Endurance Charges | belt | 1 | CorruptionMaximumEnduranceCharges1 |
| item | +1 to Maximum Frenzy Charges | gloves | 1 | CorruptionMaximumFrenzyCharges1 |
| item | +1 to Maximum Power Charges | helmet | 1 | CorruptionMaximumPowerCharges1 |
| item | +1% to all Maximum Elemental Resistances | body_armour,amulet | 1 | CorruptionMaximumElementalResistance1 |
| item | +3% to maximum Block chance | shield | 1 | CorruptionMaximumBlockChance1 |
| item | Adds (1-2) to (29-43) Lightning Damage | bow,one_hand_weapon | 1 | CorruptionLocalAddedLightningDamage1 |
| item | Adds (1-3) to (41-61) Lightning Damage | two_hand_weapon | 1 | CorruptionLocalAddedLightningDamageTwoHand1 |
| item | Adds (10-16) to (17-25) Chaos damage | two_hand_weapon | 1 | CorruptionLocalAddedChaosDamageTwoHand1 |
| item | Adds (11-17) to (18-26) Cold Damage | two_hand_weapon | 1 | CorruptionLocalAddedColdDamageTwoHand1 |
| item | Adds (13-20) to (21-31) Fire Damage | two_hand_weapon | 1 | CorruptionLocalAddedFireDamageTwoHand1 |
| item | Adds (7-11) to (12-18) Chaos damage | bow,one_hand_weapon | 1 | CorruptionLocalAddedChaosDamage1 |
| item | Adds (8-12) to (13-19) Cold Damage | bow,one_hand_weapon | 1 | CorruptionLocalAddedColdDamage1 |
| item | Adds (9-14) to (15-22) Fire Damage | bow,one_hand_weapon | 1 | CorruptionLocalAddedFireDamage1 |
| item | Allies in your Presence deal (20-30)% increased Damage | sceptre | 1 | CorruptionAlliesInPresenceAllDamage1 |
| item | Allies in your Presence have (10-15)% increased Critical Damage Bonus | sceptre | 1 | CorruptionAlliesInPresenceCriticalStrikeMultiplier1 |
| item | Allies in your Presence have (5-10)% increased Attack Speed | sceptre | 1 | CorruptionAlliesInPresenceIncreasedAttackSpeed1 |
| item | Allies in your Presence have (5-10)% increased Cast Speed | sceptre | 1 | CorruptionAlliesInPresenceIncreasedCastSpeed1 |
| item | Bow Attacks fire an additional Arrow | bow | 1 | CorruptionAdditionalArrows1 |
| item | Break (10-15)% increased Armour | gloves | 1 | CorruptionArmourBreak1 |
| item | Causes (20-30)% increased Stun Buildup | mace,sword,axe,flail,warstaff,dagger,spear | 1 | CorruptionLocalStunDamageIncrease1 |
| item | Charms gain (0.08-0.17) charges per Second | amulet | 1 | CorruptionCharmChargeGeneration1 |
| item | Damage Penetrates (10-15)% Cold Resistance | gloves | 1 | CorruptionColdPenetration1 |
| item | Damage Penetrates (10-15)% Fire Resistance | gloves | 1 | CorruptionFirePenetration1 |
| item | Damage Penetrates (10-15)% Lightning Resistance | gloves | 1 | CorruptionLightningPenetration1 |
| item | Gain (10-15) Mana per enemy killed | wand,staff,quiver | 1 | CorruptionManaGainedFromEnemyDeath1 |
| item | Gain (20-25) Life per enemy killed | wand,staff,quiver | 1 | CorruptionLifeGainedFromEnemyDeath1 |
| item | Grants 1 Rage on Hit | mace,sword,axe,flail,warstaff,dagger,spear | 1 | CorruptionLocalRageOnHit1 |
| item | Leech 2% of Physical Attack Damage as Mana | amulet | 1 | CorruptionManaLeech1 |
| item | Leech 3% of Physical Attack Damage as Life | amulet | 1 | CorruptionLifeLeech1 |
| item | Life Flasks gain (0.08-0.17) charges per Second | amulet | 1 | CorruptionLifeFlaskChargeGeneration1 |
| item | Loads an additional bolt | crossbow | 1 | CorruptionAdditionalAmmo1 |
| item | Mana Flasks gain (0.08-0.17) charges per Second | amulet | 1 | CorruptionManaFlaskChargeGeneration1 |
| item | Projectiles have (10-20)% chance to Chain an additional time from terrain | quiver | 1 | CorruptionChainFromTerrain1 |
| misc | +(3-7)% to Chaos Resistance | default | 1 | CorruptionJewelChaosResist1 |
| misc | +(4-6) to Dexterity | default | 1 | CorruptionJewelDexterity1 |
| misc | +(4-6) to Intelligence | default | 1 | CorruptionJewelIntelligence1 |
| misc | +(4-6) to Strength | default | 1 | CorruptionJewelStrength1 |
| misc | +(5-10)% to Cold Resistance | default | 1 | CorruptionJewelColdResist1 |
| misc | +(5-10)% to Fire Resistance | default | 1 | CorruptionJewelFireResist1 |
| misc | +(5-10)% to Lightning Resistance | default | 1 | CorruptionJewelLightningResist1 |
| misc | Cannot be Blinded | default | 1 | CorruptionJewelBlindImmunity1 |
| misc | Corrupted Blood cannot be inflicted on you | default | 1 | CorruptionJewelCorruptedBloodImmunity1 |
| misc | Immune to Maim | default | 1 | CorruptionJewelMaimImmunity1 |
| misc | You cannot be Hindered | default | 1 | CorruptionJewelHinderImmunity1 |

## Appendix E. Liquid emotions (27) with waystone lines and jewel crafts

Source S9, 0.5.5.10 game text. The first lines ("Players in Area are X% Delirious", …) are the waystone effect; the rest is the jewel craft (Ruby/Sapphire/Emerald/Diamond = jewel type).

| Emotion | Text |
|---|---|
| Diluted Liquid Ire | Players in Area are 7% Delirious ; 20% increased Magic Monsters ; Removes a random modifer and Augments a Rare Basic Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: (10—20)% increased Armour ; Sapphire Prefix: (10—20)% increased maximum Energy Shield ; Emerald Prefix: (10—20)% increased Evasion Rating |
| Diluted Liquid Guilt | Players in Area are 9% Delirious ; 8% increased Pack Size ; Removes a random modifer and Augments a Rare Basic Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: (5—15)% increased Fire Damage ; Sapphire Prefix: (5—15)% increased Cold Damage ; Emerald Prefix: (5—15)% increased Lightning Damage |
| Diluted Liquid Greed | Players in Area are 10% Delirious ; 8% increased Rarity of Items found ; Removes a random modifer and Augments a Rare Basic Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: (5—15)% increased Global Physical Damage ; Sapphire Prefix: (7—13)% increased Chaos Damage ; Emerald Prefix: (5—15)% increased Elemental Damage |
| Liquid Paranoia | Players in Area are 12% Delirious ; 15% increased Rare Monsters ; Removes a random modifer and Augments a Rare Basic Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: (5—15)% increased Attack Damage ; Sapphire Suffix: (2—4)% increased Cast Speed ; Emerald Suffix: (2—4)% increased Attack Speed |
| Liquid Envy | Players in Area are 15% Delirious ; 30% increased Waystones found in Area ; Removes a random modifer and Augments a Rare Basic Jewel with a ; new guaranteed Crafted modifier ; Ruby Suffix: (4—6)% of Skill Mana Costs Converted to Life Costs ; Sapphire Prefix: (5—15)% increased Spell Damage ; Emerald Suffix: (3—5)% increased Cooldown Recovery Rate |
| Liquid Disgust | Players in Area are 18% Delirious ; 30% increased Tablets found in Area ; Removes a random modifer and Augments a Rare Basic Jewel with a ; new guaranteed Crafted modifier ; Ruby Suffix: (5—10)% increased Life Regeneration rate ; Sapphire Suffix: Recover (1—2)% of maximum Mana on Kill ; Emerald Suffix: Recover (1—2)% of maximum Life on Kill |
| Liquid Despair | Players in Area are 20% Delirious ; 30% increased Stack size of Simulacrum Splinters found in your Maps ; Removes a random modifer and Augments a Rare Basic Jewel with a ; new guaranteed Crafted modifier ; Ruby Suffix: Gain 1 Rage on Melee Hit ; Sapphire Suffix: (5—15)% increased Critical Hit Chance for Spells ; Emerald Suffix: (6—16)% increased Critical Hit Chance for Attacks |
| Concentrated Liquid Fear | Players in Area are 22% Delirious ; Rare Monsters have a 25% Surpassing chance to have an additional Modifier ; Removes a random modifer and Augments a Rare Basic Jewel with a ; new guaranteed Crafted modifier ; Ruby Suffix: (10—20)% increased Warcry Speed ; Sapphire Suffix: (10—20)% increased Critical Spell Damage Bonus ; Emerald Suffix: (10—20)% increased Critical Damage Bonus for Attack Damage |
| Concentrated Liquid Suffering | Players in Area are 25% Delirious ; Unique Monsters in your Maps have 1 additional Rare Modifiers ; Removes a random modifer and Augments a Rare Basic Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: +(1—2) to Maximum Rage ; Sapphire Prefix: (4—6)% increased Area of Effect ; Emerald Suffix: (1—2)% increased Movement Speed |
| Concentrated Liquid Isolation | Players in Area are 50% Delirious ; Removes a random modifer and Augments a Rare Basic Jewel with a ; new guaranteed Crafted modifier ; Ruby Suffix: +1% to Maximum Fire Resistance ; Sapphire Suffix: +1% to Maximum Cold Resistance ; Emerald Suffix: +1% to Maximum Lightning Resistance ; Diamond Suffix: +1% to Maximum Chaos Resistance |
| Ancient Diluted Liquid Ire | Removes a random modifer and Augments a Rare Time-Lost Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: Small Passive Skills in Radius also grant (2—3)% increased Armour ; Sapphire Prefix: Small Passive Skills in Radius also grant (2—3)% increased maximum Energy Shield ; Emerald Prefix: Small Passive Skills in Radius also grant (2—3)% increased Evasion Rating |
| Ancient Diluted Liquid Guilt | Removes a random modifer and Augments a Rare Time-Lost Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: Small Passive Skills in Radius also grant (1—2)% increased Fire Damage ; Sapphire Prefix: Small Passive Skills in Radius also grant (1—2)% increased Cold Damage ; Emerald Prefix: Small Passive Skills in Radius also grant (1—2)% increased Lightning Damage |
| Ancient Diluted Liquid Greed | Removes a random modifer and Augments a Rare Time-Lost Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: Small Passive Skills in Radius also grant (1—2)% increased Global Physical Damage ; Sapphire Prefix: Small Passive Skills in Radius also grant (1—2)% increased Chaos Damage ; Emerald Prefix: Small Passive Skills in Radius also grant (1—2)% increased Elemental Damage |
| Ancient Liquid Paranoia | Removes a random modifer and Augments a Rare Time-Lost Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: Small Passive Skills in Radius also grant (1—2)% increased Attack Damage ; Sapphire Suffix: Notable Passive Skills in Radius also grant (1—2)% increased Cast Speed ; Emerald Suffix: Notable Passive Skills in Radius also grant (1—2)% increased Attack Speed |
| Ancient Liquid Envy | Removes a random modifer and Augments a Rare Time-Lost Jewel with a ; new guaranteed Crafted modifier ; Ruby Suffix: Notable Passive Skills in Radius also grant (2—3)% of Skill Mana Costs Converted to Life Costs ; Sapphire Prefix: Small Passive Skills in Radius also grant (1—2)% increased Spell Damage ; Emerald Suffix: Notable Passive Skills in Radius also grant (1—3)% increased Cooldown Recovery Rate |
| Ancient Liquid Disgust | Removes a random modifer and Augments a Rare Time-Lost Jewel with a ; new guaranteed Crafted modifier ; Ruby Suffix: Notable Passive Skills in Radius also grant (3—5)% increased Life Regeneration rate ; Sapphire Suffix: Notable Passive Skills in Radius also grant Recover 1% of maximum Mana on Kill ; Emerald Suffix: Notable Passive Skills in Radius also grant Recover 1% of maximum Life on Kill |
| Ancient Liquid Despair | Removes a random modifer and Augments a Rare Time-Lost Jewel with a ; new guaranteed Crafted modifier ; Ruby Suffix: Notable Passive Skills in Radius also grant Gain 1 Rage on Melee Hit ; Sapphire Suffix: Notable Passive Skills in Radius also grant (3—7)% increased Critical Hit Chance for Spells ; Emerald Suffix: Notable Passive Skills in Radius also grant (3—7)% increased Critical Hit Chance for Attacks |
| Ancient Concentrated Liquid Fear | Removes a random modifer and Augments a Rare Time-Lost Jewel with a ; new guaranteed Crafted modifier ; Ruby Suffix: Small Passive Skills in Radius also grant (2—3)% increased Warcry Speed ; Sapphire Suffix: Notable Passive Skills in Radius also grant (5—10)% increased Critical Spell Damage Bonus ; Emerald Suffix: Notable Passive Skills in Radius also grant (5—10)% increased Critical Damage Bonus for Attack Damage |
| Ancient Concentrated Liquid Suffering | Removes a random modifer and Augments a Rare Time-Lost Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: Notable Passive Skills in Radius also grant +1 to Maximum Rage ; Sapphire Prefix: Notable Passive Skills in Radius also grant (2—3)% increased Area of Effect ; Emerald Suffix: Notable Passive Skills in Radius also grant 1% increased Movement Speed |
| Ancient Concentrated Liquid Isolation | Removes a random modifer and Augments a Rare Time-Lost Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: Increases and Reductions to ; Cold and Lightning Damage in Radius are transformed to apply to Fire Damage ; Sapphire Prefix: Increases and Reductions to ; Fire and Lightning Damage in Radius are transformed to apply to Cold Damage ; Emerald Prefix: Increases and Reductions to ; Cold and Fire Damage in Radius are transformed to apply to Lightning Damage |
| Potent Liquid Melancholy | Players in Area are 50% Delirious ; Removes a random modifer and Augments a Rare Basic Jewel with a ; new guaranteed Crafted modifier ; Ruby Suffix: Debilitate Enemies on Hit while you have an Emerald and a Sapphire socketed in your tree ; Sapphire Suffix: Inflict Elemental Exposure on Hit while you have a Ruby and an Emerald socketed in your tree ; Emerald Suffix: Blind Enemies on Hit while you have a Ruby and a Sapphire socketed in your tree |
| Potent Liquid Ferocity | Players in Area are 50% Delirious ; Removes a random modifer and Augments a Rare Basic Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: (40—60)% increased Effect of Suffixes ; Ruby Suffix: (40—60)% increased Effect of Prefixes ; Sapphire Prefix: (40—60)% increased Effect of Suffixes ; Sapphire Suffix: (40—60)% increased Effect of Prefixes ; Emerald Prefix: (40—60)% increased Effect of Suffixes ; Emerald Suffix: (40—60)% increased Effect of Prefixes ; Diamond Prefix: (40—60)% increased Effect of Suffixes ; Diamond Suffix: (40—60)% increased Effect of Prefixes |
| Potent Liquid Contempt | Players in Area are 50% Delirious ; Removes a random modifer and Augments a Rare Basic Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: +1 Suffix Modifier allowed ; Ruby Suffix: +1 Prefix Modifier allowed ; Sapphire Prefix: +1 Suffix Modifier allowed ; Sapphire Suffix: +1 Prefix Modifier allowed ; Emerald Prefix: +1 Suffix Modifier allowed ; Emerald Suffix: +1 Prefix Modifier allowed ; Diamond Prefix: +1 Suffix Modifier allowed ; Diamond Suffix: +1 Prefix Modifier allowed |
| Ancient Potent Liquid Melancholy | Removes a random modifer and Augments a Rare Time-Lost Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: Upgrades Radius to Very Large ; local jewel effect base radius [500] ; Sapphire Prefix: Upgrades Radius to Very Large ; local jewel effect base radius [500] ; Emerald Prefix: Upgrades Radius to Very Large ; local jewel effect base radius [500] ; Diamond Prefix: Upgrades Radius to Very Large ; local jewel effect base radius [500] |
| Ancient Potent Liquid Ferocity | Removes a random modifer and Augments a Rare Time-Lost Jewel with a ; new guaranteed Crafted modifier ; Ruby Suffix: Notable Passive Skills in Radius also grant +(5—7)% to Fire Resistance ; Sapphire Suffix: Notable Passive Skills in Radius also grant +(5—7)% to Cold Resistance ; Emerald Suffix: Notable Passive Skills in Radius also grant +(5—7)% to Lightning Resistance ; Diamond Suffix: Notable Passive Skills in Radius also grant +(4—5)% to Chaos Resistance |
| Ancient Potent Liquid Contempt | Removes a random modifer and Augments a Rare Time-Lost Jewel with a ; new guaranteed Crafted modifier ; Ruby Prefix: +1 Suffix Modifier allowed ; Ruby Suffix: +1 Prefix Modifier allowed ; Sapphire Prefix: +1 Suffix Modifier allowed ; Sapphire Suffix: +1 Prefix Modifier allowed ; Emerald Prefix: +1 Suffix Modifier allowed ; Emerald Suffix: +1 Prefix Modifier allowed ; Diamond Prefix: +1 Suffix Modifier allowed ; Diamond Suffix: +1 Prefix Modifier allowed |
| Liquid Verisium | Immediately start a Runic Remnant Encounter with a random Runic Inscription |

## Appendix F. Named desecrated modifiers (Amanamu, Kurgal, Ulaman; 198 rows)

Source S8 (poe2db "Desecrated Mods /198"), 0.5.5.10. Columns as poe2db prints them: name | level | side | text and tags (the trailing words are poe2db's mod tags).

| Name | Level | Side | Text and tags |
|---|---|---|---|
| Amanamu's | 65 | Prefix | Attacks with this Weapon Penetrate (15—25)% Fire Resistance amanamu Damage Elemental Fire Attack |
| Amanamu's | 65 | Prefix | Charms gain (0.1—0.2) charges per Second Charm amanamu |
| Amanamu's | 65 | Prefix | (12—23)% increased Area of Effect for Attacks amanamu Attack |
| Amanamu's | 65 | Prefix | 2 to 4 Fire Thorns damage per 100 maximum Life amanamu Elemental Fire |
| Amanamu's | 65 | Prefix | (10—18)% chance for Charms you use to not consume Charges Charm amanamu |
| Amanamu's | 65 | Prefix | Companions deal (40—59)% increased Damage / (40—59)% increased Damage while your Companion is in your Presence amanamu |
| Amanamu's | 65 | Prefix | Gain (40—50)% of Damage as Extra Chaos Damage amanamu Damage Chaos |
| Amanamu's | 65 | Prefix | (74—89)% increased Elemental Damage amanamu Damage Elemental Fire Cold Lightning |
| Amanamu's | 65 | Prefix | (55—64)% increased Spell Damage / Minions deal (55—64)% increased Damage amanamu Caster Minion |
| Amanamu's | 65 | Prefix | (74—89)% increased Spell Damage with Spells that cost Life amanamu |
| Amanamu's | 65 | Prefix | +(35—50) to Spirit amanamu |
| Amanamu's | 65 | Prefix | (148—178)% increased Spell Damage with Spells that cost Life amanamu |
| Amanamu's | 65 | Prefix | (86—99)% increased Fire Damage / (14—23)% increased Ignite Magnitude amanamu Elemental Fire Ailment |
| Amanamu's | 65 | Prefix | (15—25)% increased Global Armour, Evasion and Energy Shield amanamu |
| Amanamu's | 65 | Prefix | (35—50)% increased Armour from Equipped Body Armour amanamu Armour |
| Amanamu's | 65 | Prefix | (101—121)% increased Grenade Damage / (20—30)% increased Grenade Duration amanamu Damage |
| Amanamu's | 65 | Prefix | Minions deal (60—79)% increased Damage if you've Hit Recently amanamu Damage Minion |
| Amanamu's | 65 | Prefix | (86—99)% increased Damage against Enemies with Fully Broken Armour amanamu Damage |
| Amanamu's | 65 | Prefix | Minions deal (15—25)% increased Damage if you've Hit Recently amanamu Damage Minion |
| Amanamu's | 65 | Prefix | Remnants you create have (8—15)% increased effect amanamu |
| Amanamu's | 65 | Prefix | (20—30)% increased Magnitude of Ignite if you've consumed an Endurance Charge Recently amanamu Ailment |
| Amanamu's | 65 | Prefix | Projectiles deal (20—30)% increased Damage with Hits against Enemies within 2m amanamu Damage |
| Amanamu's | 65 | Prefix | Grenade Skills have +1 Cooldown Uses amanamu |
| Amanamu's | 65 | Prefix | (8—16)% increased Curse Magnitudes amanamu Caster Curse |
| Amanamu's | 65 | Prefix | (41—59)% increased Damage against Enemies with Fully Broken Armour amanamu Damage |
| Amanamu's | 65 | Prefix | Offering Skills have (12—20)% increased Buff effect amanamu |
| Kurgal's | 65 | Prefix | (20—30)% increased Freeze Buildup if you've consumed an Power Charge Recently kurgal Ailment |
| Kurgal's | 65 | Prefix | Spell Skills have (10—20)% increased Area of Effect kurgal Caster |
| Kurgal's | 65 | Prefix | Invocated Spells have (10—20)% chance to consume half as much Energy kurgal Caster |
| Kurgal's | 65 | Prefix | (35—50)% increased Energy Shield from Equipped Body Armour kurgal Energy Shield |
| Kurgal's | 65 | Prefix | Projectiles deal (85—109)% increased Damage with Hits against Enemies within 2m kurgal Damage |
| Kurgal's | 65 | Prefix | Invocated Spells deal (61—79)% increased Damage kurgal Caster |
| Kurgal's | 65 | Prefix | Projectiles deal (20—30)% increased Damage with Hits against Enemies further than 6m kurgal |
| Kurgal's | 65 | Prefix | Gain (6—12)% of Maximum Mana as Armour kurgal Mana Armour |
| Kurgal's | 65 | Prefix | Mana Flasks gain (0.1—0.2) charges per Second kurgal |
| Kurgal's | 65 | Prefix | (4—5)% increased Spell Damage per 100 maximum Mana kurgal Mana Damage Caster |
| Kurgal's | 65 | Prefix | (15—25)% increased Spell Damage while on Full Energy Shield kurgal Damage Caster |
| Kurgal's | 65 | Prefix | (10—15)% chance for Flasks you use to not consume Charges kurgal |
| Kurgal's | 65 | Prefix | (86—99)% increased Cold Damage / (14—23)% increased Freeze Buildup kurgal Elemental Cold Ailment |
| Kurgal's | 65 | Prefix | Empowered Attacks deal (86—99)% increased Damage kurgal Damage Attack |
| Kurgal's | 65 | Prefix | Attacks with this Weapon Penetrate (15—25)% Cold Resistance kurgal Damage Elemental Cold Attack |
| Kurgal's | 65 | Prefix | +(1—2) to maximum number of Elemental Infusions kurgal Elemental |
| Kurgal's | 65 | Prefix | Empowered Attacks deal (41—59)% increased Damage kurgal Damage Attack |
| Kurgal's | 65 | Prefix | Invocated Spells deal (75—89)% increased Damage kurgal Caster |
| Kurgal's | 65 | Prefix | Warcries Empower (1—2) additional Attacks kurgal Attack |
| Kurgal's | 65 | Prefix | (110—154)% increased Physical Damage / 15% reduced Attack Speed kurgal Physical Attack Speed |
| Kurgal's | 65 | Prefix | (30—40)% increased bonuses gained from Equipped Quiver kurgal |
| Kurgal's | 65 | Prefix | Projectiles have (25—35)% chance to Chain an additional time from terrain kurgal |
| Kurgal's | 65 | Prefix | (60—79)% increased Melee Damage if you've dealt a Projectile Attack Hit in the past eight seconds kurgal |
| Ulaman's | 65 | Prefix | (35—50)% increased Evasion Rating from Equipped Body Armour ulaman Evasion |
| Ulaman's | 65 | Prefix | Spell Skills have +1 to maximum number of Summoned Totems ulaman Caster |
| Ulaman's | 65 | Prefix | (61—79)% increased Spell Damage while wielding a Melee Weapon ulaman Caster |
| Ulaman's | 65 | Prefix | (20—30)% chance for Skills to retain 40% of Glory on use ulaman |
| Ulaman's | 65 | Prefix | Melee Attack Skills have +1 to maximum number of Summoned Totems ulaman |
| Ulaman's | 65 | Prefix | (10—20)% increased Deflection Rating ulaman Evasion |
| Ulaman's | 65 | Prefix | (10—18)% chance for Flasks you use to not consume Charges ulaman |
| Ulaman's | 65 | Prefix | (41—59)% increased Damage while you have a Totem ulaman Damage |
| Ulaman's | 65 | Prefix | Increases and Reductions to Projectile Speed also apply to Damage with Bows ulaman |
| Ulaman's | 65 | Prefix | (20—30)% increased Magnitude of Shock if you've consumed a Frenzy Charge Recently ulaman Ailment |
| Ulaman's | 65 | Prefix | (15—25)% increased Attack Damage while on Low Life ulaman |
| Ulaman's | 65 | Prefix | +1 to maximum number of Summoned Ballista Totems ulaman |
| Ulaman's | 65 | Prefix | (86—99)% increased Damage while you have a Totem ulaman Damage |
| Ulaman's | 65 | Prefix | (27—38)% increased Magnitude of Bleeding you inflict ulaman Damage Physical Attack Ailment |
| Ulaman's | 65 | Prefix | Attacks with this Weapon Penetrate (15—25)% Lightning Resistance ulaman Damage Elemental Lightning Attack |
| Ulaman's | 65 | Prefix | (20—30)% increased Life Regeneration rate during Effect of any Life Flask ulaman |
| Ulaman's | 65 | Prefix | Projectiles deal (60—79)% increased Damage with Hits against Enemies further than 6m ulaman |
| Ulaman's | 65 | Prefix | (4—5)% increased Spell Damage per 100 Maximum Life ulaman Life Damage Caster |
| Ulaman's | 65 | Prefix | (40—64)% increased Magnitude of Damaging Ailments you inflict ulaman Ailment |
| Ulaman's | 65 | Prefix | Life Flasks gain (0.1—0.2) charges per Second ulaman |
| Ulaman's | 65 | Prefix | Gain (21—25)% of Damage as Extra Physical Damage ulaman Damage Physical |
| Ulaman's | 65 | Prefix | (86—99)% increased Lightning Damage / (14—23)% increased Magnitude of Shock you inflict ulaman Elemental Lightning Ailment |
| of Amanamu | 65 | Suffix | Break Armour equal to (2—4)% of Physical Damage dealt amanamu Damage Physical |
| of Amanamu | 65 | Suffix | (16—23)% chance for Mace Slam Skills you use yourself to cause an additional Aftershock amanamu Attack |
| of Amanamu | 65 | Suffix | Skills which create Fissures have a (15—25)% chance to create an additional Fissure amanamu Attack |
| of Amanamu | 65 | Suffix | (10—16)% chance for Mace Slam Skills you use yourself to cause an additional Aftershock amanamu Attack |
| of Amanamu | 65 | Suffix | +(20—25)% to Block chance amanamu |
| of Amanamu | 65 | Suffix | Break Armour equal to (4—7)% of Physical Damage dealt amanamu Damage Physical |
| of Amanamu | 65 | Suffix | Skills which create Fissures have a (25—31)% chance to create an additional Fissure amanamu Attack |
| of Amanamu | 65 | Suffix | Remnants can be collected from (20—30)% further away amanamu |
| of Amanamu | 65 | Suffix | (12—20)% increased amount of Life Leeched amanamu Life |
| of Amanamu | 65 | Suffix | (25—35)% increased Archon Buff duration amanamu |
| of Amanamu | 65 | Suffix | Equipment and Skill Gems have (10—15)% reduced Attribute Requirements amanamu |
| of Amanamu | 65 | Suffix | (25—35)% of Spell Mana Cost Converted to Life Cost amanamu Life Caster |
| of Amanamu | 65 | Suffix | Spell Skills have (8—16)% increased Area of Effect amanamu Caster |
| of Amanamu | 65 | Suffix | (5—10)% increased Cost Efficiency / (15—25)% of Spell Mana Cost Converted to Life Cost amanamu Life Caster |
| of Amanamu | 65 | Suffix | (25—40)% chance to build an additional Combo on Hit amanamu |
| of Amanamu | 65 | Suffix | Enemies Hindered by you take (4—7)% increased Elemental Damage amanamu |
| of Amanamu | 65 | Suffix | Aura Skills have (8—16)% increased Magnitudes amanamu |
| of Amanamu | 65 | Suffix | (5—10)% increased Spirit Reservation Efficiency of Skills amanamu |
| of Amanamu | 65 | Suffix | (40—60)% chance to Pierce an Enemy amanamu |
| of Amanamu | 65 | Suffix | (6—12)% increased Spirit Reservation Efficiency of Skills amanamu |
| of Amanamu | 65 | Suffix | +(13—17)% to Fire and Chaos Resistances amanamu Elemental Fire Chaos Resistance |
| of Amanamu | 65 | Suffix | +(9—15) to Strength and Intelligence amanamu Attribute |
| of Amanamu | 65 | Suffix | (25—35)% reduced effect of Curses on you amanamu Caster Curse |
| of Amanamu | 65 | Suffix | (10—20)% of Damage taken Recouped as Life amanamu Life |
| of Amanamu | 65 | Suffix | +(2—4)% to Thorns Critical Hit Chance amanamu Damage Critical |
| of Amanamu | 65 | Suffix | +(0.1—0.2) metres to Dodge Roll distance amanamu |
| of Amanamu | 65 | Suffix | (12—20)% reduced Slowing Potency of Debuffs on You amanamu |
| of Amanamu | 65 | Suffix | (12—18)% increased Attack Speed / Companions have (12—18)% increased Attack Speed amanamu |
| of Amanamu | 65 | Suffix | (8—12)% increased Skill Effect Duration amanamu |
| of Amanamu | 65 | Suffix | (20—30)% reduced Ignite Duration on you amanamu Elemental Fire Ailment |
| of Amanamu | 65 | Suffix | (10—20)% increased Immobilisation buildup amanamu |
| of Amanamu | 65 | Suffix | (8—15)% of Leech is Instant amanamu |
| of Amanamu | 65 | Suffix | (10—20)% chance to Daze on Hit amanamu |
| of Amanamu | 65 | Suffix | (12—20)% increased Area of Effect of Curses amanamu Caster Curse |
| of Amanamu | 65 | Suffix | (25—35)% increased Presence Area of Effect amanamu Aura |
| of Amanamu | 65 | Suffix | (10—20)% increased Glory generation amanamu |
| of Amanamu | 65 | Suffix | (4—8)% increased Spirit Reservation Efficiency of Skills amanamu |
| of Amanamu | 65 | Suffix | (10—20)% faster Curse Activation amanamu Caster Curse |
| of Amanamu | 65 | Suffix | +(1—2) to Level of all Minion Skills amanamu Minion Gem |
| of Amanamu | 65 | Suffix | Shield Skills fully Break Armour when they Heavy Stun targets amanamu |
| of Amanamu | 65 | Suffix | Your Heavy Stun buildup empties (30—40)% faster amanamu |
| of Amanamu | 65 | Suffix | +1% to all maximum Resistances amanamu Resistance |
| of Amanamu | 65 | Suffix | Grenades have (15—25)% chance to activate a second time amanamu |
| of Amanamu | 65 | Suffix | Projectiles have (18—26)% increased Critical Damage Bonus against Enemies within 2m amanamu |
| of Kurgal | 65 | Suffix | (25—34)% increased Immobilisation buildup kurgal |
| of Kurgal | 65 | Suffix | (20—30)% reduced Duration of Bleeding on You kurgal Physical Ailment |
| of Kurgal | 65 | Suffix | (15—25)% chance when collecting an Elemental Infusion to gain an / additional Elemental Infusion of the same type kurgal |
| of Kurgal | 65 | Suffix | (8—15)% increased Cast Speed when on Full Life kurgal Caster Speed |
| of Kurgal | 65 | Suffix | (10—15)% chance to Gain Arcane Surge when you deal a Critical Hit kurgal Critical |
| of Kurgal | 65 | Suffix | (3—5)% increased Cast Speed for each different Non-Instant Spell you've Cast Recently kurgal |
| of Kurgal | 65 | Suffix | Enemies Hindered by you take (4—7)% increased Chaos Damage kurgal |
| of Kurgal | 65 | Suffix | Projectiles have (18—26)% increased Critical Hit Chance against Enemies further than 6m kurgal |
| of Kurgal | 65 | Suffix | Recover (2—3)% of maximum Mana on Kill kurgal Mana |
| of Kurgal | 65 | Suffix | Projectiles have (25—34)% increased Critical Hit Chance against Enemies further than 6m kurgal |
| of Kurgal | 65 | Suffix | (25—31)% increased Warcry Cooldown Recovery Rate kurgal |
| of Kurgal | 65 | Suffix | (8—15)% increased Cost Efficiency of Attacks kurgal Attack |
| of Kurgal | 65 | Suffix | +(13—17)% to Cold and Chaos Resistances kurgal Elemental Cold Chaos Resistance |
| of Kurgal | 65 | Suffix | (20—30)% increased effect of Arcane Surge on you kurgal Mana Caster |
| of Kurgal | 65 | Suffix | (8—12)% increased Cooldown Recovery Rate kurgal |
| of Kurgal | 65 | Suffix | (10—15)% increased Exposure Effect kurgal Elemental Fire Cold Lightning |
| of Kurgal | 65 | Suffix | (39—51)% increased Critical Hit Chance against Marked Enemies kurgal Critical |
| of Kurgal | 65 | Suffix | (6—10)% increased Mana Cost Efficiency kurgal Mana |
| of Kurgal | 65 | Suffix | +(9—15) to Dexterity and Intelligence kurgal Attribute |
| of Kurgal | 65 | Suffix | (40—50)% increased Energy Shield Recharge Rate if you've Blocked Recently kurgal Energy Shield |
| of Kurgal | 65 | Suffix | (15—20)% chance when you Reload a Crossbow to be immediate kurgal |
| of Kurgal | 65 | Suffix | Minions have (12—20)% increased Cooldown Recovery Rate kurgal Minion |
| of Kurgal | 65 | Suffix | (8—16)% of Damage is taken from Mana before Life kurgal Life Mana |
| of Kurgal | 65 | Suffix | +(3—5)% to Quality of all Skills kurgal Gem |
| of Kurgal | 65 | Suffix | (10—20)% of Damage is taken from Mana before Life kurgal Life Mana |
| of Kurgal | 65 | Suffix | +(23—31)% of Armour also applies to Chaos Damage kurgal |
| of Kurgal | 65 | Suffix | (10—20)% of Elemental Damage taken Recouped as Energy Shield kurgal |
| of Kurgal | 65 | Suffix | (10—20)% of Damage taken Recouped as Mana kurgal Life Mana |
| of Kurgal | 65 | Suffix | (6—12) Mana gained when you Block kurgal Mana |
| of Kurgal | 65 | Suffix | (12—20)% increased amount of Mana Leeched kurgal Mana |
| of Kurgal | 65 | Suffix | (30—40)% increased Mana Regeneration Rate kurgal Mana |
| of Kurgal | 65 | Suffix | Recover (4—6)% of Maximum Mana when you expend at least 10 Combo kurgal Mana |
| of Kurgal | 65 | Suffix | (40—50)% increased Mana Regeneration Rate while stationary kurgal Mana |
| of Kurgal | 65 | Suffix | Archon recovery period expires (25—35)% faster kurgal |
| of Kurgal | 65 | Suffix | (26—36)% increased Cast Speed while on Full Mana kurgal Mana Caster Speed |
| of Kurgal | 65 | Suffix | +(3—4) maximum stacks of Puppet Master kurgal Minion |
| of Kurgal | 65 | Suffix | (8—12)% increased Mana Cost Efficiency if you have Dodge Rolled Recently kurgal Mana |
| of Kurgal | 65 | Suffix | (17—25)% increased Warcry Cooldown Recovery Rate kurgal |
| of Kurgal | 65 | Suffix | (17—25)% increased Reload Speed kurgal Attack Speed |
| of Ulaman | 65 | Suffix | +(13—17)% to Lightning and Chaos Resistances ulaman Elemental Lightning Chaos Resistance |
| of Ulaman | 65 | Suffix | (40—50)% increased Life Regeneration Rate while moving ulaman Life |
| of Ulaman | 65 | Suffix | Gain (3—6) Rage on Melee Hit kurgal Attack |
| of Ulaman | 65 | Suffix | Recover (6—12)% of Maximum Life when you expend at least 10 Combo ulaman Life |
| of Ulaman | 65 | Suffix | (8—13)% increased Attack Speed / (8—13)% increased Attack Speed while your Companion is in your Presence ulaman |
| of Ulaman | 65 | Suffix | Projectile Attacks have a (10—18)% chance to fire two additional Projectiles while moving ulaman |
| of Ulaman | 65 | Suffix | Projectiles have (27—38)% increased Critical Damage Bonus against Enemies within 2m ulaman |
| of Ulaman | 65 | Suffix | Attacks Chain 1 additional times ulaman |
| of Ulaman | 65 | Suffix | (8—12)% increased Skill Speed if you've consumed a Frenzy Charge Recently ulaman Speed |
| of Ulaman | 65 | Suffix | +(1—2)% to maximum Block chance ulaman |
| of Ulaman | 65 | Suffix | (12—18)% increased Reservation Efficiency of Companion Skills ulaman |
| of Ulaman | 65 | Suffix | Prevent +(3—5)% of Damage from Deflected Hits ulaman |
| of Ulaman | 65 | Suffix | Hits have (17—25)% reduced Critical Hit Chance against you ulaman Critical |
| of Ulaman | 65 | Suffix | (17—25)% reduced Slowing Potency of Debuffs on You if you've used a Charm Recently Charm ulaman |
| of Ulaman | 65 | Suffix | (6—10)% reduced Movement Speed Penalty from using Skills while moving ulaman Speed |
| of Ulaman | 65 | Suffix | Corrupted Blood cannot be inflicted on you ulaman Physical Ailment |
| of Ulaman | 65 | Suffix | (20—30)% reduced Poison Duration on you ulaman Chaos Ailment |
| of Ulaman | 65 | Suffix | (20—30)% increased Parried Debuff Magnitude ulaman |
| of Ulaman | 65 | Suffix | (15—25)% chance for Attack Hits to apply Incision ulaman Physical Ailment |
| of Ulaman | 65 | Suffix | (20—30)% increased chance to inflict Bleeding ulaman |
| of Ulaman | 65 | Suffix | (20—30)% increased chance to Poison ulaman |
| of Ulaman | 65 | Suffix | (10—20)% increased Magnitude of Ailments you inflict ulaman Damage Ailment |
| of Ulaman | 65 | Suffix | (8—12)% increased Life Cost Efficiency ulaman Life |
| of Ulaman | 65 | Suffix | (13—20)% increased Critical Damage Bonus ulaman Damage Critical |
| of Ulaman | 65 | Suffix | Enemies you Mark take (4—8)% increased Damage ulaman |
| of Ulaman | 65 | Suffix | +(9—15) to Strength and Dexterity ulaman Attribute |
| of Ulaman | 65 | Suffix | (10—20)% increased Reservation Efficiency of Herald Skills ulaman |
| of Ulaman | 65 | Suffix | (17—25)% increased Totem Placement speed ulaman Speed |
| of Ulaman | 65 | Suffix | (15—20)% of Skill Mana Costs Converted to Life Costs ulaman Life |
| of Ulaman | 65 | Suffix | Enemies Hindered by you take (4—7)% increased Physical Damage ulaman |
| of Ulaman | 65 | Suffix | Break Armour on Critical Hit with Spells equal to (11—18)% of Physical Damage dealt ulaman Caster Critical |
| of Ulaman | 65 | Suffix | Break (31—39)% increased Armour ulaman |
| of Ulaman | 65 | Suffix | (25—35)% chance for Spell Skills to fire 2 additional Projectiles ulaman Caster |
| of Ulaman | 65 | Suffix | (30—40)% increased Cast Speed when on Low Life ulaman Caster Speed |
| of Ulaman | 65 | Suffix | +1 to Level of all Skills ulaman Gem |
| of Ulaman | 65 | Suffix | (25—31)% increased Totem Placement speed ulaman Speed |
| of Ulaman | 65 | Suffix | Recover (2—3)% of maximum Life on Kill ulaman Life |
| of Ulaman | 65 | Suffix | (3—6)% increased Skill Speed ulaman Speed |
| of Ulaman | 65 | Suffix | (10—14)% of Skill Mana Costs Converted to Life Costs ulaman Life |
| of Ulaman | 65 | Suffix | Projectile Attacks have a (8—12)% chance to fire two additional Projectiles while moving ulaman |
| of Ulaman | 65 | Suffix | (10—16)% chance for Spell Skills to fire 2 additional Projectiles ulaman Caster |
| of Ulaman | 65 | Suffix | (10—20)% of Spell Mana Cost Converted to Life Cost ulaman Life Caster |
| of Ulaman | 65 | Suffix | (30—40)% of Physical Damage taken as Lightning while your Shield is raised / You take (8—15)% of damage from Blocked Hits with a raised Shield ulaman Physical Elemental Lightning |
| of Ulaman | 65 | Suffix | (25—35)% increased Parried Debuff Duration ulaman |
