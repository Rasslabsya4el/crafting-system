# Action catalogue

The catalogue records the intended scope. Loadout tiers are planning guesses from BRIEF, not
game facts. A `partial` sheet permits only explicitly scoped, sourced worker specs; unknown
paths remain unsupported. An inventory-only sheet approves no game rule. The complete frozen
method tree (95 named nodes, including legacy/mixed-game entries and options) is in
[the mechanical inventory](../research/coe-method-inventory.md), S3 `poec_cmethods`, line 5.

| Action / rule family | Loadout tier guess | Fact sheet | Status | Confidence |
|---|---|---|---|---|
| Transmutation, Alteration, Augmentation, Regal, Alchemy, Chaos, Exalted, Annul, Scour, Divine | day 1 / mapping | [basic_currency.md](basic_currency.md), [affix_generation.md](affix_generation.md) | reviewed, partial | reimplemented-from-CoE |
| Bench crafts and metamods | day 1 / endgame | [bench_metamods.md](bench_metamods.md) | reviewed, partial | datamined + documented + reimplemented-from-CoE |
| Essences | day 1 / mapping | [essences.md](essences.md) | reviewed, partial | documented + datamined + reimplemented-from-CoE |
| Fossils and resonators | mapping / endgame | [fossils_resonators.md](fossils_resonators.md) | weight path reviewed, partial | reimplemented-from-CoE + documented metamod exception |
| Harvest reforges and augments | endgame | [harvest.md](harvest.md) | partial | documented + reimplemented-from-CoE |
| Eldritch currency and Orb of Conflict | endgame | [eldritch_currency.md](eldritch_currency.md) | partial | documented + reimplemented-from-CoE |
| Awakener's Orb | endgame | [awakener_orb.md](awakener_orb.md) | eligibility and selection reviewed; Q20 conflict discrepancy | documented + reimplemented-from-CoE |
| Fracturing Orb | endgame | [fracturing.md](fracturing.md) | eligibility and selection reviewed, partial | documented + reimplemented-from-CoE |
| Veiled Exalted, Veiled Chaos and unveiling | endgame | [veiled.md](veiled.md) | effects and side selection reviewed; offer probabilities open | documented + datamined + reimplemented-from-CoE |
| Recombinators | endgame | [recombinators.md](recombinators.md) | modes and source differences reviewed; exact odds open | documented + player-report + reimplemented-from-CoE |
| Corruption (Vaal and Locus) | endgame | [corruption.md](corruption.md) | category distribution reviewed; detailed transitions partial; Q18 version difference | documented + reimplemented-from-CoE |
| Beast crafts: imprint, restore, prefix/suffix swap, aspects | later | [beast_crafting.md](beast_crafting.md) | reviewed conditions and source differences; Q25 | documented + reimplemented-from-CoE |
| Orb of Dominance / elevated modifiers | endgame | [dominance.md](dominance.md) | reviewed transformation/CoE selection; full mapping open | documented + reimplemented-from-CoE |
| Influence Exalted orbs | endgame | [influence_orbs.md](influence_orbs.md) | reviewed, item-specific gates partial; Q27 | documented + reimplemented-from-CoE |
| Blessed Orb | day 1 / later | [blessed_orb.md](blessed_orb.md) | reviewed; old-value conflict Q24 | documented + reimplemented-from-CoE |
| Catalysts and quality | later | [quality_catalysts.md](quality_catalysts.md) | reviewed; increment conflict Q23 | documented + reimplemented-from-CoE |
| Synthesis implicits | endgame | [synthesis.md](synthesis.md) | reviewed 3.29 conditions; generation weights open | documented + datamined definitions |
| Item/mod levels, base tags and influence pools | all | [pool_resolution.md](pool_resolution.md), affix sheet | ordered weights/gates reviewed; families/multipliers/influence incomplete | documented + datamined; Q16/Q17 |
| Tainted/Scourge, vendor, legacy Harvest, Foulborn and other mixed-game entries | undecided | mechanical inventory only | classify against Q3 before inclusion | unsourced current availability |
| 3.29 bench rerolls, Talisman fracture/imprint and changed Fractured Fossil | undecided | [patch_3_29.md](patch_3_29.md) | availability/gates recorded; algorithms open | documented patch deltas |

For a 3.29 target, read [patch_3_29.md](patch_3_29.md) before using the older beast/synthesis/
socket inventory. S39 removes or replaces several actions still present in S3 (Q18/Q19).

No probability or eligibility not backed by a source is implied by a row. Unresolved claims remain in `docs/OPEN_QUESTIONS.md`.
