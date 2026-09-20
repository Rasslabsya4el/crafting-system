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
| Awakener's Orb | endgame | [awakener_orb.md](awakener_orb.md) | partial dispatch notes | reimplemented-from-CoE |
| Fracturing Orb | endgame | [fracturing.md](fracturing.md) | inventory only | reimplemented-from-CoE |
| Veiled modifiers and Veiled Chaos | endgame | [veiled.md](veiled.md) | data example / inventory only | datamined + reimplemented-from-CoE |
| Recombinators | endgame | [recombinators.md](recombinators.md) | inventory only | reimplemented-from-CoE |
| Corruption (Vaal and Locus) | endgame | [corruption.md](corruption.md) | inventory only | reimplemented-from-CoE |
| Beast crafts: imprint, restore, prefix/suffix swap, aspects | later | pending; inventory `beast_crafting.*` | not reviewed | unsourced rules; S3 names only |
| Orb of Dominance / elevated modifiers | endgame | pending; inventory `currency.maven` | not reviewed | unsourced rules; S3 names only |
| Influence Exalted orbs | endgame | pending; inventory `currency.shaper` through `currency.warlord` | not reviewed | unsourced rules; S3 names only |
| Blessed Orb | day 1 / later | pending; inventory `currency.blessed` | not reviewed | unsourced rules; S3 names only |
| Catalysts and quality | later | pending; inventory `catalyst`; BRIEF phase 0 | not reviewed | unsourced |
| Synthesis implicits | endgame | pending; BRIEF phase 0 / S1 ModSynthesis data | not reviewed | unsourced rules |
| Item/mod levels, base tags and influence pools | all | [pool_resolution.md](pool_resolution.md), affix sheet | ordered weights/gates reviewed; families/multipliers/influence incomplete | documented + datamined; Q16/Q17 |
| Tainted/Scourge, vendor, legacy Harvest, Foulborn and other mixed-game entries | undecided | mechanical inventory only | classify against Q3 before inclusion | unsourced current availability |

No probability or eligibility not backed by a source is implied by a row. Unresolved claims remain in `docs/OPEN_QUESTIONS.md`.
