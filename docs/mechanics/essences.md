# Essences

## Rule

An essence upgrades a normal item to rare and applies one guaranteed affix. Tier 5 (Screaming) and higher can reforge a rare item in the same broad manner as Chaos while retaining the guaranteed affix. Lower tiers do not have that rare-item reforge operation. The Wiki page also says lower tiers cap the random modifier level when the item level is above that tier's cap.

| Tier | Name | Maximum random-mod level | Minimum crafted item level | Rare reforge |
|---:|---|---:|---:|---|
| 1 | Whispering | 35 | 1 | no |
| 2 | Muttering | 45 | 8 | no |
| 3 | Weeping | 60 | 20 | no |
| 4 | Wailing | 75 | 33 | no |
| 5 | Screaming | no cap | 46 | yes |
| 6 | Shrieking | no cap | 59 | yes |
| 7 | Deafening | no cap | 65 | yes |

Essences cannot be used on an item carrying a meta-crafting modifier such as Prefixes Cannot Be Changed or Cannot roll Caster Modifiers. This is an eligibility rule observed on the Wiki page and must be represented as a rejection, not as a silent reroll.

## Data mapping

`PoB data: sources/pob/Data/Essence.lua`, for example `Metadata/Items/Currency/CurrencyEssenceRage4`, identifies tier 6 Shrieking Essence of Rage and maps each base class to a forced modifier (`Helmet -> Strength8`). The full table is the input for a future builder; this sheet does not copy the table into the engine.

Craft of Exile's dispatch in `sources/raw/coe/package.js` calls the essence reroll path with one forced modifier and a tier. That is implementation evidence, not a replacement for the PoB mapping. Its old prose says only Shrieking and Deafening can reforge rare items; the higher-ranked Wiki observation includes Screaming, so the disagreement is recorded as Q10.

## Sources and confidence

- `documented`: Wiki Essence, oldid 1700895, recorded as S21 in `docs/SOURCES.md`.
- `datamined`: `sources/pob/Data/Essence.lua`, S22.
- `reimplemented-from-CoE`: `sources/raw/coe/package.js`, S3, essence dispatch.

Open questions: exact interaction with every metamod, forced-mod tier selection for every base, and post-3.29 changes are not inferred here.
