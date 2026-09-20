# Beast crafting: imprint, affix exchange, aspects and legacy splitting

Read 2026-09-20. Confidence: `documented` for S44 Beastcrafting/S45 Imprint and S39
3.29 changes; `reimplemented-from-CoE` for the frozen algorithms below. This sheet covers
equipment transformations, not monster combat or the reward-generation recipes.

## Effect and preconditions
- Imprint: S44 lists magic-item and rare-Talisman recipes separately. S45 restricts restoration
  to the original item. Fractured items cannot be imprinted or restored, including an item
  fractured after its imprint was made. Corrupted/mirrored items are excluded unless a modifier
  explicitly permits modifying that type. Influenced, synthesised and eldritch items are allowed.
- Prefix/suffix exchange: S44 requires rare rarity. The added modifier uses the main beast's
  level, ignoring the item's ilvl; other mod-adding beast recipes use item ilvl normally.
- Aspects: S44 lists four ordinary skills and separate level-30 recipes requiring Black Morrigan.
  S3 requires a free suffix and rejects an existing aspect (2395-2396).
- Wild Bristle Matron: S44 requires a non-unique item, a free affix slot and permission to add
  a bench craft without removing an existing craft. Five ordinary mods plus one crafted mod
  is explicitly not eligible. It chooses among the five metamods subject to those restrictions.
- Splitting is legacy for the 3.29 target: S39 replaces two/three-way crafts with rare-Talisman
  fracture recipes (4/6 minimum modifiers). See patch_3_29.md. Do not present old split as available.

## Rule steps and state conditions
1. An imprint stores a recoverable original state. S45 explicitly includes implicits, explicits,
   enchantments, quality amount/type, base defence percentile, Memory Strands, Intangibility
   and Crucible tree. Restoration consumes the operation on that original identity; item identity
   must therefore be part of any future policy state, not just the displayed mod set.
2. A recombined or split output is a new item and cannot use the original imprint (S45).
   Awakener restoration recovers the receiver only; the destroyed donor remains lost.
   Imprinting removes Hinekora's Lock foresight, and restoration does not restore that effect.
3. Frozen S3 exchange (2393-2394) first checks a removable source side and an open destination
   side, draws one destination affix, then removes one source affix. Its addition uses the
   shared item pool; no beast-level input appears in this dispatcher. This differs from S44 (Q25).
4. S3 imprint (2391-2392) copies influence, affixes, implicits, catalyst, eldritch, corruption,
   quality and side counts. This narrower simulator snapshot is not proof it models every S45 field.
5. S3 aspects add a non-bench suffix with level 20 (2396). This does not implement S44's level-30
   recipe or prove that every aspect-related limitation is covered.

## Numbers, examples and metamods
- S44/S11: full 3 suffixes and an available prefix, with no blocking crafted allowance, forces
  Matron's only prefix metamod, Suffixes Cannot Be Changed. Identity probability is 1 in this
  stated singleton case; unrestricted five-way odds are not supplied by the page.
- S44 beast-level example (invented levels): a level-80 beast on ilvl-60 equipment gates the
  exchanged added mod at beast level 80. This does not raise the item's stored ilvl to 80.
- CoE exchange with 2 prefixes/2 suffixes gives 1 prefix/3 suffixes for `pretosuf`, provided
  both draws succeed (2393). Locks/removal filtering still apply; a blocked removal must not
  be treated as a successful game action merely because the dispatcher sets success.
- The Imprint examples have deterministic identity effects, not a free reset: a fractured result
  has 0 legal imprint restores; an Awakener receiver can restore while 1 donor remains destroyed.

## Differences and unknowns
S3's older beast names/cost references and split actions lag S39/S44. Frozen CoE's exchange
beast-level omission is Q25. Exact current removal probabilities and the complete side-lock /
attack-caster matrix, Talisman fracture odds, aspect exclusions and exceptional modifiable-corrupted
states remain Q9/Q12. Only the conditions explicitly sourced here may enter a future spec.

Sources: S44 https://www.poewiki.net/index.php?title=Beastcrafting&oldid=1673867,
S45 https://www.poewiki.net/index.php?title=Imprint&oldid=1702288; S3 package.js:2391-2399;
S39 official 3.29 notes. All read 2026-09-20.
