# Synthesised items and implicit replacement

Read 2026-09-20. Confidence: `documented` S39/S44/S50; definitions `datamined` S1 ModSynthesis.
Keep synthesised base status separate from its current implicit list. A data definition is not
evidence that a current non-unique crafting action can generate it.

## Effect and preconditions
S50 describes 1-3 synthesis implicits replacing the base implicits. For 3.29, S39/S50 remove
direct creation of new non-unique synthesised items; outside Standard, the stated path is
corrupting a synthesised unique into a non-unique. Harvest synthesis is removed. Vivid Vulture's
reroll now requires unique rarity (S39/S44). Existing legacy bases remain version-scoped inputs.

## Steps and exceptions
1. For the current unique beast recipe, choose one synthesis implicit to replace; S44 says
   random, but does not supply equal selection odds or replacement pool weights. Preserve
   non-synthesis implicits, including Gilded Fossil's vendor-value implicit.
2. Corruption can replace synthesis implicits individually (S50); see corruption.md for
   category chances and version changes. Mixed corrupted/synthesis implicits can exist.
3. Eldritch implicits can replace all existing synthesis implicits; they cannot coexist with
   them. The base remains synthesised and still cannot be fractured (S50). This is not ordinary
   conventional influence, which the page disallows on synthesised items.
4. S50 permits enchanting and imprinting; vendor recipes which modify the item remove synthesis
   implicits. Chance cannot turn a normal synthesised base into unique. Detailed recipe selection
   and legacy exceptions require separate specs, not a universal reset operation.

## Numbers and examples
- A source state with 3 synthesis implicits losing 1 to a corruption replacement retains 2
  synthesis implicits and gains 1 corrupted implicit (S50). Which original is selected follows
  corruption.md, not an assumed beast-reroll selection rule.
- S50 gives mod-level 56 -> required character level 44 in its 80% example. This is about
  equip requirements, NOT a rule allowing an ilvl-44 item to roll a level-56 mod.
- ModSynthesis.lua:5 SynthesisImplicitLife1 has stat '+(8-10) to maximum Life', level 1 and
  empty weightKey/weightVal arrays. Empty arrays do not mean equal probability or an impossible
  Vulture roll. A separate source for the generating pool is needed (Q12).

## CoE comparison and open questions
S3's frozen synthesis/legacy inventory is not a current 3.29 availability list (Q19).
Exact Vulture selection/weights, per-base eligibility and count generation remain Q12.
The source distinguishes historical Harvest/imprint interactions from currently available
actions. No synthesis calculator is authorized by this sheet.

Sources: S50 https://www.poewiki.net/index.php?title=Synthesised_item&oldid=1675552;
S44 Beastcrafting, Harvest beast recipes; S39 official 3.29 notes; S1 ModSynthesis.lua, named key.
