# Essences

Update 2026-09-21: S21 plus PoEDB Screaming Essence of Sorrow (S63) confirm that all normal
essence tiers upgrade normal items; tier5/Screaming and above ALSO reforge rare items.
It is not a white-only/rare-only switch. No tier permits magic inputs (owner row8, S21).
The existing ordinary adapter already implements this boundary correctly; tier8 remains
separately gated by its special mapping rules. Confidence: documented; owner-confirmed magic ban.

## Rule

An essence upgrades a normal item to rare and applies one guaranteed affix. Tier 5 (Screaming) and higher can reforge a rare item in the same broad manner as Chaos while retaining the guaranteed affix. Lower tiers do not have that rare-item reforge operation. The Wiki page also says lower tiers cap the random modifier level when the item level is above that tier's cap.

| Tier | Name | Maximum random-mod level | Result's minimum required level (Wiki column) | Rare reforge |
|---:|---|---:|---:|---|
| 1 | Whispering | 35 | 1 | no |
| 2 | Muttering | 45 | 8 | no |
| 3 | Weeping | 60 | 20 | no |
| 4 | Wailing | 75 | 33 | no |
| 5 | Screaming | no cap | 46 | yes |
| 6 | Shrieking | no cap | 59 | yes |
| 7 | Deafening | no cap | 65 | yes |

The Wiki column is **minimum required level of the crafted item**, not a minimum input item
level. The earlier draft abbreviated it ambiguously. Do not use 1/8/20/33/46/59/65 as input
eligibility gates. Rechecked S21's rendered table on 2026-09-20.

S21 warns against meta-crafting modifiers such as Prefixes Cannot Be Changed and Cannot roll
Caster Modifiers. S17's specific Essence/Fossil example explicitly exempts multimod alone.
Apply the prohibition to outcome-affecting metamods; do not silently extend it to that exception.
S3 `poec_cmethods.essence` additionally excludes magic rarity and requires `is_essence` base
support. Full corrupted/mirrored/fractured legality remains Q9.

## Observed steps and numeric examples

S3 `poec_simApplyCraftGO`, essence branch, selects a forced mod/tier from the essence and base
mapping, rejects a conflicting fractured group, and calls a rare reroll with that forced mod.
The remaining pool and count are conditional on [affix generation](affix_generation.md).
The precise special-essence and item-flag matrix is not complete.

- For ordinary tier 4, a synthetic ilvl 86 input has random-mod cap min(86,75)=75; at ilvl 60
  the cap is min(60,75)=60. Arithmetic from S21, not actual item samples.
- Tier 4 rare reforge: rejected; tier 5 rare reforge: allowed by S21's tier condition, provided
  the other item eligibility checks pass. This does not claim all rare items are valid.
- S22 Helmet mapping for Shrieking Rage resolves to exactly 1 forced modifier ID, `Strength8`.

## Data mapping

`PoB data: sources/pob/Data/Essence.lua`, for example `Metadata/Items/Currency/CurrencyEssenceRage4`, identifies tier 6 Shrieking Essence of Rage and maps each base class to a forced modifier (`Helmet -> Strength8`). The accepted literal builder exports 105 records and 2310 class mappings to `data/pob_essences.json` (8d49e8f). All 622 distinct referenced IDs occur in local ModExplicit; this verifies links, not every action gate or probability.

Craft of Exile's dispatch in `sources/raw/coe/package.js` calls the essence reroll path with one forced modifier and a tier. That is implementation evidence, not a replacement for the PoB mapping. Its old prose says only Shrieking and Deafening can reforge rare items; the higher-ranked Wiki observation includes Screaming, so the disagreement is recorded as Q10.

## Sources and confidence

- `documented`: Wiki Essence, oldid 1700895, recorded as S21 in `docs/SOURCES.md`.
- `datamined`: `sources/pob/Data/Essence.lua`, S22.
- `reimplemented-from-CoE`: `sources/raw/coe/package.js`, S3, essence dispatch.

Open questions: Q9 full eligibility, Q10 recorded CoE disagreement.
