# Frozen 54-mod cross-check

Mechanical comparison of the lead-selected correspondences from `docs/specs/2026-09-20-mod-crosscheck.md`. It preserves source-native group labels and records observations only; it does not select a canonical alias.

| field | value |
| --- | --- |
| date read | 2026-09-20 |
| snapshot labels | owner-supplied S24, S4, S27, S28-S32 |
| selected PoB IDs | 54 |
| unique PoB IDs | 54 |
| emitted comparison rows | 54 |
| CoE unique ilvl matches | 54 |
| PoEDB unique normal Name/Level matches | 54 |
| level agreements | 54 |
| weight agreements | 54 |
| range agreements | 54 |
| side agreements | 54 |
| group agreements | 33 |
| group-label differences | 21 |
| deterministic two-run equality | true; CLI re-renders after re-reading all inputs before write |
| output SHA-256 | `1d180284f4926bbb0497c48adf901e8c4e4295c937a2a69602fe7027915d3218` |

The output hash is SHA-256 of this UTF-8/LF report after replacing the value in its self-reference row with `<OUTPUT-SHA256-CANONICALIZED>`.

## Source snapshots

| snapshot | path | SHA-256 | source count / role |
| --- | --- | --- | --- |
| S24 | `sources/pob/Data/ModExplicit.lua` | `6d400101f60ec48f854daad9a5ca2479b43e9e405f92724e80631b276eaf4568` | 4315 source lines |
| S24 | `data/pob_mod_explicit.json` | `23145ee027c0c7158921c5d02b920b9149227dcf653722b3550fc15bfdaa6050` | 4310 projected mod records |
| S4 | `sources/raw/coe/poec_data.json` | `2c770512d134fafc82f689fa65cc83a583cc63d9e9994b76aa7f17f8a896923a` | 4911 modifier rows; 4539 tier modifier IDs |
| S27 | `sources/pob/Data/Bases/helmet.lua` | `bb5f8a66c491ae5073350d9c5b0c45edafc137712d5a555435a9421d0419db8e` | provenance pointer; active tags remain fixed by the lead-supplied selection |
| S27 | `sources/pob/Data/Bases/bow.lua` | `ad420096d028a4aadaef230e880f7b9d5feb57fbe8613d8e3722b3b4238e38f0` | provenance pointer; active tags remain fixed by the lead-supplied selection |
| S27 | `sources/pob/Data/Bases/ring.lua` | `6db93137a173e81f2e16374ba96e845536004903bc01f12443bd754785bca86d` | provenance pointer; active tags remain fixed by the lead-supplied selection |
| S27 | `sources/pob/Data/Bases/body.lua` | `b764b6065a41af36d8433dd26838a6290ce0abd17431c3b7090ab935534f9557` | provenance pointer; active tags remain fixed by the lead-supplied selection |
| S27 | `sources/pob/Data/Bases/gloves.lua` | `6c251c4582062109de151ad9c7b5bf9583c4b51fb6fa27e7f9d1648d6ead2217` | provenance pointer; active tags remain fixed by the lead-supplied selection |
| S28 | `sources/raw/poedb/Helmets_str.html` | `41b793f58fb74c3ae8d3bb450db69d31f68b05c1cdfc8b1f8620939d792ad20b` | 125 normal rows |
| S29 | `sources/raw/poedb/Bows.html` | `bb515fa6f35eaa471472a7866cf5eb97d1a0c93d3b1e0af12346fd03a39e98c2` | 141 normal rows |
| S30 | `sources/raw/poedb/Rings.html` | `cd2a59059e375817c34062b1b71fe0c162c765c5e21fde2a45d2e1680273b929` | 207 normal rows |
| S31 | `sources/raw/poedb/Body_Armours_int.html` | `4ec519836677852231b21d5bc38c402e0aa5549516edc0f30d84c2919e29ba2b` | 125 normal rows |
| S32 | `sources/raw/poedb/Gloves_str.html` | `082f4aaa7cad9b5ae1dfab63d12c1775fe1fad11c7a30c00611c9fb2de81fc0f` | 146 normal rows |

## Per-class counts

| class | selected rows |
| --- | --- |
| Helmet | 10 |
| Bow | 10 |
| Ring | 14 |
| Body Armour | 11 |
| Gloves | 9 |

## Row comparison

PoB raw ranges come from the first unnamed quoted stat after `affix = ...` at the recorded S24 source line. CoE ranges are `nvalues`; PoEDB ranges are visible text after HTML parsing. CoE exact modifier/base IDs and PoEDB normal-row pointers are included for every row.

| class / base | PoB ID + source line | CoE modifier / base | PoEDB normal row | level PoB / CoE / PoEDB | weight PoB / CoE / PoEDB | range PoB / CoE / PoEDB | affix side PoB / CoE / PoEDB | source-native group PoB / CoE / PoEDB | differing fields |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Helmet / Iron Hat | `IncreasedLife0` / `ModExplicit.lua:47` | `1775` / `52` | `Helmets_str.html` normal[19] 'Hale' / 1 | 1 / 1 / 1 | 1000 / 1000 / 1000 | [[3,9]] / [[3,9]] / [[3,9]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["IncreasedLife"] / ["IncreasedLife"] / ["IncreasedLife"] | none |
| Helmet / Iron Hat | `IncreasedLife1` / `ModExplicit.lua:48` | `1775` / `52` | `Helmets_str.html` normal[20] 'Healthy' / 5 | 5 / 5 / 5 | 1000 / 1000 / 1000 | [[10,24]] / [[10,24]] / [[10,24]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["IncreasedLife"] / ["IncreasedLife"] / ["IncreasedLife"] | none |
| Helmet / Iron Hat | `IncreasedLife2` / `ModExplicit.lua:49` | `1775` / `52` | `Helmets_str.html` normal[21] 'Sanguine' / 11 | 11 / 11 / 11 | 1000 / 1000 / 1000 | [[25,39]] / [[25,39]] / [[25,39]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["IncreasedLife"] / ["IncreasedLife"] / ["IncreasedLife"] | none |
| Helmet / Iron Hat | `IncreasedLife3` / `ModExplicit.lua:50` | `1775` / `52` | `Helmets_str.html` normal[22] 'Stalwart' / 18 | 18 / 18 / 18 | 1000 / 1000 / 1000 | [[40,54]] / [[40,54]] / [[40,54]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["IncreasedLife"] / ["IncreasedLife"] / ["IncreasedLife"] | none |
| Helmet / Iron Hat | `IncreasedLife4` / `ModExplicit.lua:51` | `1775` / `52` | `Helmets_str.html` normal[23] 'Stout' / 24 | 24 / 24 / 24 | 1000 / 1000 / 1000 | [[55,69]] / [[55,69]] / [[55,69]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["IncreasedLife"] / ["IncreasedLife"] / ["IncreasedLife"] | none |
| Helmet / Iron Hat | `IncreasedLife5` / `ModExplicit.lua:52` | `1775` / `52` | `Helmets_str.html` normal[24] 'Robust' / 30 | 30 / 30 / 30 | 1000 / 1000 / 1000 | [[70,84]] / [[70,84]] / [[70,84]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["IncreasedLife"] / ["IncreasedLife"] / ["IncreasedLife"] | none |
| Helmet / Iron Hat | `IncreasedLife6` / `ModExplicit.lua:53` | `1775` / `52` | `Helmets_str.html` normal[25] 'Rotund' / 36 | 36 / 36 / 36 | 1000 / 1000 / 1000 | [[85,99]] / [[85,99]] / [[85,99]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["IncreasedLife"] / ["IncreasedLife"] / ["IncreasedLife"] | none |
| Helmet / Iron Hat | `IncreasedLife7` / `ModExplicit.lua:54` | `1775` / `52` | `Helmets_str.html` normal[26] 'Virile' / 44 | 44 / 44 / 44 | 1000 / 1000 / 1000 | [[100,114]] / [[100,114]] / [[100,114]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["IncreasedLife"] / ["IncreasedLife"] / ["IncreasedLife"] | none |
| Helmet / Iron Hat | `IncreasedLife8` / `ModExplicit.lua:55` | `1775` / `52` | `Helmets_str.html` normal[27] "Athlete's" / 54 | 54 / 54 / 54 | 1000 / 1000 / 1000 | [[115,129]] / [[115,129]] / [[115,129]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["IncreasedLife"] / ["IncreasedLife"] / ["IncreasedLife"] | none |
| Helmet / Iron Hat | `IncreasedLife9` / `ModExplicit.lua:56` | `1775` / `52` | `Helmets_str.html` normal[28] 'Fecund' / 64 | 64 / 64 / 64 | 1000 / 1000 / 1000 | [[130,144]] / [[130,144]] / [[130,144]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["IncreasedLife"] / ["IncreasedLife"] / ["IncreasedLife"] | none |
| Bow / Crude Bow | `LocalAddedFireDamageTwoHand1` / `ModExplicit.lua:438` | `1972` / `20` | `Bows.html` normal[34] 'Heated' / 1 | 1 / 1 / 1 | 1400 / 1400 / 1400 | [[3,5],[6,7]] / [[3,5],[6,7]] / [[3,5],[6,7]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | group |
| Bow / Crude Bow | `LocalAddedFireDamageTwoHand2` / `ModExplicit.lua:439` | `1972` / `20` | `Bows.html` normal[35] 'Smouldering' / 11 | 11 / 11 / 11 | 1400 / 1400 / 1400 | [[14,20],[29,33]] / [[14,20],[29,33]] / [[14,20],[29,33]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | group |
| Bow / Crude Bow | `LocalAddedFireDamageTwoHand3` / `ModExplicit.lua:440` | `1972` / `20` | `Bows.html` normal[36] 'Smoking' / 18 | 18 / 18 / 18 | 1400 / 1400 / 1400 | [[23,31],[47,54]] / [[23,31],[47,54]] / [[23,31],[47,54]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | group |
| Bow / Crude Bow | `LocalAddedFireDamageTwoHand4` / `ModExplicit.lua:441` | `1972` / `20` | `Bows.html` normal[37] 'Burning' / 26 | 26 / 26 / 26 | 1400 / 1400 / 1400 | [[32,44],[65,76]] / [[32,44],[65,76]] / [[32,44],[65,76]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | group |
| Bow / Crude Bow | `LocalAddedFireDamageTwoHand5` / `ModExplicit.lua:442` | `1972` / `20` | `Bows.html` normal[38] 'Flaming' / 33 | 33 / 33 / 33 | 1400 / 1400 / 1400 | [[45,61],[91,106]] / [[45,61],[91,106]] / [[45,61],[91,106]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | group |
| Bow / Crude Bow | `LocalAddedFireDamageTwoHand6` / `ModExplicit.lua:443` | `1972` / `20` | `Bows.html` normal[39] 'Scorching' / 42 | 42 / 42 / 42 | 1400 / 1400 / 1400 | [[63,85],[128,148]] / [[63,85],[128,148]] / [[63,85],[128,148]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | group |
| Bow / Crude Bow | `LocalAddedFireDamageTwoHand7` / `ModExplicit.lua:444` | `1972` / `20` | `Bows.html` normal[40] 'Incinerating' / 51 | 51 / 51 / 51 | 1400 / 1400 / 1400 | [[85,115],[172,200]] / [[85,115],[172,200]] / [[85,115],[172,200]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | group |
| Bow / Crude Bow | `LocalAddedFireDamageTwoHand8_` / `ModExplicit.lua:445` | `1972` / `20` | `Bows.html` normal[41] 'Blasting' / 62 | 62 / 62 / 62 | 1120 / 1120 / 1120 | [[110,150],[223,260]] / [[110,150],[223,260]] / [[110,150],[223,260]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | group |
| Bow / Crude Bow | `LocalAddedFireDamageTwoHand9` / `ModExplicit.lua:446` | `1972` / `20` | `Bows.html` normal[42] 'Cremating' / 74 | 74 / 74 / 74 | 490 / 490 / 490 | [[137,188],[279,325]] / [[137,188],[279,325]] / [[137,188],[279,325]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | group |
| Bow / Crude Bow | `LocalAddedFireDamageTwoHand10` / `ModExplicit.lua:447` | `1972` / `20` | `Bows.html` normal[43] 'Carbonising' / 82 | 82 / 82 / 82 | 126 / 126 / 126 | [[165,225],[335,390]] / [[165,225],[335,390]] / [[165,225],[335,390]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | group |
| Ring / Iron Ring | `ColdResist1` / `ModExplicit.lua:971` | `684` / `1` | `Rings.html` normal[148] 'of the Inuit' / 1 | 1 / 1 / 1 | 1000 / 1000 / 1000 | [[6,11]] / [[6,11]] / [[6,11]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["ColdResistance"] / ["ColdResistance"] / ["ColdResistance"] | none |
| Ring / Iron Ring | `ColdResist2` / `ModExplicit.lua:972` | `684` / `1` | `Rings.html` normal[149] 'of the Seal' / 14 | 14 / 14 / 14 | 1000 / 1000 / 1000 | [[12,17]] / [[12,17]] / [[12,17]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["ColdResistance"] / ["ColdResistance"] / ["ColdResistance"] | none |
| Ring / Iron Ring | `ColdResist3` / `ModExplicit.lua:973` | `684` / `1` | `Rings.html` normal[150] 'of the Penguin' / 26 | 26 / 26 / 26 | 1000 / 1000 / 1000 | [[18,23]] / [[18,23]] / [[18,23]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["ColdResistance"] / ["ColdResistance"] / ["ColdResistance"] | none |
| Ring / Iron Ring | `ColdResist4` / `ModExplicit.lua:974` | `684` / `1` | `Rings.html` normal[151] 'of the Yeti' / 38 | 38 / 38 / 38 | 1000 / 1000 / 1000 | [[24,29]] / [[24,29]] / [[24,29]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["ColdResistance"] / ["ColdResistance"] / ["ColdResistance"] | none |
| Ring / Iron Ring | `ColdResist5` / `ModExplicit.lua:975` | `684` / `1` | `Rings.html` normal[152] 'of the Walrus' / 50 | 50 / 50 / 50 | 1000 / 1000 / 1000 | [[30,35]] / [[30,35]] / [[30,35]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["ColdResistance"] / ["ColdResistance"] / ["ColdResistance"] | none |
| Ring / Iron Ring | `ColdResist6` / `ModExplicit.lua:976` | `684` / `1` | `Rings.html` normal[153] 'of the Polar Bear' / 60 | 60 / 60 / 60 | 1000 / 1000 / 1000 | [[36,41]] / [[36,41]] / [[36,41]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["ColdResistance"] / ["ColdResistance"] / ["ColdResistance"] | none |
| Ring / Iron Ring | `ColdResist7` / `ModExplicit.lua:977` | `684` / `1` | `Rings.html` normal[154] 'of the Ice' / 72 | 72 / 72 / 72 | 1000 / 1000 / 1000 | [[42,45]] / [[42,45]] / [[42,45]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["ColdResistance"] / ["ColdResistance"] / ["ColdResistance"] | none |
| Ring / Iron Ring | `ColdResist8` / `ModExplicit.lua:978` | `684` / `1` | `Rings.html` normal[155] 'of Haast' / 84 | 84 / 84 / 84 | 1000 / 1000 / 1000 | [[46,48]] / [[46,48]] / [[46,48]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["ColdResistance"] / ["ColdResistance"] / ["ColdResistance"] | none |
| Body Armour / Simple Robe | `LocalIncreasedEnergyShield1` / `ModExplicit.lua:129` | `2007` / `47` | `Body_Armours_int.html` normal[34] 'Shining' / 3 | 3 / 3 / 3 | 1000 / 1000 / 1000 | [[3,5]] / [[3,5]] / [[3,5]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | group |
| Body Armour / Simple Robe | `LocalIncreasedEnergyShield2` / `ModExplicit.lua:130` | `2007` / `47` | `Body_Armours_int.html` normal[35] 'Glimmering' / 11 | 11 / 11 / 11 | 1000 / 1000 / 1000 | [[6,11]] / [[6,11]] / [[6,11]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | group |
| Body Armour / Simple Robe | `LocalIncreasedEnergyShield3` / `ModExplicit.lua:131` | `2007` / `47` | `Body_Armours_int.html` normal[36] 'Glittering' / 17 | 17 / 17 / 17 | 1000 / 1000 / 1000 | [[12,16]] / [[12,16]] / [[12,16]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | group |
| Body Armour / Simple Robe | `LocalIncreasedEnergyShield4` / `ModExplicit.lua:132` | `2007` / `47` | `Body_Armours_int.html` normal[37] 'Glowing' / 23 | 23 / 23 / 23 | 1000 / 1000 / 1000 | [[17,23]] / [[17,23]] / [[17,23]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | group |
| Body Armour / Simple Robe | `LocalIncreasedEnergyShield5` / `ModExplicit.lua:133` | `2007` / `47` | `Body_Armours_int.html` normal[38] 'Radiating' / 29 | 29 / 29 / 29 | 1000 / 1000 / 1000 | [[24,30]] / [[24,30]] / [[24,30]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | group |
| Body Armour / Simple Robe | `LocalIncreasedEnergyShield6` / `ModExplicit.lua:134` | `2007` / `47` | `Body_Armours_int.html` normal[39] 'Pulsing' / 35 | 35 / 35 / 35 | 1000 / 1000 / 1000 | [[31,38]] / [[31,38]] / [[31,38]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | group |
| Body Armour / Simple Robe | `LocalIncreasedEnergyShield7` / `ModExplicit.lua:135` | `2007` / `47` | `Body_Armours_int.html` normal[40] 'Seething' / 43 | 43 / 43 / 43 | 1000 / 1000 / 1000 | [[39,49]] / [[39,49]] / [[39,49]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | group |
| Body Armour / Simple Robe | `LocalIncreasedEnergyShield8` / `ModExplicit.lua:136` | `2007` / `47` | `Body_Armours_int.html` normal[41] 'Blazing' / 51 | 51 / 51 / 51 | 1000 / 1000 / 1000 | [[50,61]] / [[50,61]] / [[50,61]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | group |
| Body Armour / Simple Robe | `LocalIncreasedEnergyShield9` / `ModExplicit.lua:137` | `2007` / `47` | `Body_Armours_int.html` normal[42] 'Scintillating' / 60 | 60 / 60 / 60 | 1000 / 1000 / 1000 | [[62,76]] / [[62,76]] / [[62,76]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | group |
| Body Armour / Simple Robe | `LocalIncreasedEnergyShield10` / `ModExplicit.lua:138` | `2007` / `47` | `Body_Armours_int.html` normal[43] 'Incandescent' / 69 | 69 / 69 / 69 | 1000 / 1000 / 1000 | [[77,90]] / [[77,90]] / [[77,90]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | group |
| Body Armour / Simple Robe | `LocalIncreasedEnergyShield11` / `ModExplicit.lua:139` | `2007` / `47` | `Body_Armours_int.html` normal[44] 'Resplendent' / 75 | 75 / 75 / 75 | 1000 / 1000 / 1000 | [[91,100]] / [[91,100]] / [[91,100]] | Prefix / prefix (Prefix) / 1 (Prefix) | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | group |
| Gloves / Iron Gauntlets | `Strength1` / `ModExplicit.lua:5` | `2336` / `33` | `Gloves_str.html` normal[0] 'of the Brute' / 1 | 1 / 1 / 1 | 1000 / 1000 / 1000 | [[8,12]] / [[8,12]] / [[8,12]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["Strength"] / ["Strength"] / ["Strength"] | none |
| Gloves / Iron Gauntlets | `Strength2` / `ModExplicit.lua:6` | `2336` / `33` | `Gloves_str.html` normal[1] 'of the Wrestler' / 11 | 11 / 11 / 11 | 1000 / 1000 / 1000 | [[13,17]] / [[13,17]] / [[13,17]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["Strength"] / ["Strength"] / ["Strength"] | none |
| Gloves / Iron Gauntlets | `Strength3` / `ModExplicit.lua:7` | `2336` / `33` | `Gloves_str.html` normal[2] 'of the Bear' / 22 | 22 / 22 / 22 | 1000 / 1000 / 1000 | [[18,22]] / [[18,22]] / [[18,22]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["Strength"] / ["Strength"] / ["Strength"] | none |
| Gloves / Iron Gauntlets | `Strength4` / `ModExplicit.lua:8` | `2336` / `33` | `Gloves_str.html` normal[3] 'of the Lion' / 33 | 33 / 33 / 33 | 1000 / 1000 / 1000 | [[23,27]] / [[23,27]] / [[23,27]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["Strength"] / ["Strength"] / ["Strength"] | none |
| Gloves / Iron Gauntlets | `Strength5` / `ModExplicit.lua:9` | `2336` / `33` | `Gloves_str.html` normal[4] 'of the Gorilla' / 44 | 44 / 44 / 44 | 1000 / 1000 / 1000 | [[28,32]] / [[28,32]] / [[28,32]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["Strength"] / ["Strength"] / ["Strength"] | none |
| Gloves / Iron Gauntlets | `Strength6` / `ModExplicit.lua:10` | `2336` / `33` | `Gloves_str.html` normal[5] 'of the Goliath' / 55 | 55 / 55 / 55 | 1000 / 1000 / 1000 | [[33,37]] / [[33,37]] / [[33,37]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["Strength"] / ["Strength"] / ["Strength"] | none |
| Gloves / Iron Gauntlets | `Strength7` / `ModExplicit.lua:11` | `2336` / `33` | `Gloves_str.html` normal[6] 'of the Leviathan' / 66 | 66 / 66 / 66 | 1000 / 1000 / 1000 | [[38,42]] / [[38,42]] / [[38,42]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["Strength"] / ["Strength"] / ["Strength"] | none |
| Gloves / Iron Gauntlets | `Strength8` / `ModExplicit.lua:12` | `2336` / `33` | `Gloves_str.html` normal[7] 'of the Titan' / 74 | 74 / 74 / 74 | 1000 / 1000 / 1000 | [[43,50]] / [[43,50]] / [[43,50]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["Strength"] / ["Strength"] / ["Strength"] | none |
| Gloves / Iron Gauntlets | `Strength9` / `ModExplicit.lua:13` | `2336` / `33` | `Gloves_str.html` normal[8] 'of the Gods' / 82 | 82 / 82 / 82 | 1000 / 1000 / 1000 | [[51,55]] / [[51,55]] / [[51,55]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["Strength"] / ["Strength"] / ["Strength"] | none |
| Ring / Iron Ring | `ChaosResist1` / `ModExplicit.lua:996` | `661` / `1` | `Rings.html` normal[164] 'of the Lost' / 16 | 16 / 16 / 16 | 250 / 250 / 250 | [[5,10]] / [[5,10]] / [[5,10]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["ChaosResistance"] / ["ChaosResistance"] / ["ChaosResistance"] | none |
| Ring / Iron Ring | `ChaosResist2` / `ModExplicit.lua:997` | `661` / `1` | `Rings.html` normal[165] 'of Banishment' / 30 | 30 / 30 / 30 | 250 / 250 / 250 | [[11,15]] / [[11,15]] / [[11,15]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["ChaosResistance"] / ["ChaosResistance"] / ["ChaosResistance"] | none |
| Ring / Iron Ring | `ChaosResist3` / `ModExplicit.lua:998` | `661` / `1` | `Rings.html` normal[166] 'of Eviction' / 44 | 44 / 44 / 44 | 250 / 250 / 250 | [[16,20]] / [[16,20]] / [[16,20]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["ChaosResistance"] / ["ChaosResistance"] / ["ChaosResistance"] | none |
| Ring / Iron Ring | `ChaosResist4` / `ModExplicit.lua:999` | `661` / `1` | `Rings.html` normal[167] 'of Expulsion' / 56 | 56 / 56 / 56 | 250 / 250 / 250 | [[21,25]] / [[21,25]] / [[21,25]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["ChaosResistance"] / ["ChaosResistance"] / ["ChaosResistance"] | none |
| Ring / Iron Ring | `ChaosResist5` / `ModExplicit.lua:1000` | `661` / `1` | `Rings.html` normal[168] 'of Exile' / 65 | 65 / 65 / 65 | 250 / 250 / 250 | [[26,30]] / [[26,30]] / [[26,30]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["ChaosResistance"] / ["ChaosResistance"] / ["ChaosResistance"] | none |
| Ring / Iron Ring | `ChaosResist6` / `ModExplicit.lua:1001` | `661` / `1` | `Rings.html` normal[169] 'of Bameth' / 81 | 81 / 81 / 81 | 250 / 250 / 250 | [[31,35]] / [[31,35]] / [[31,35]] | Suffix / suffix (Suffix) / 2 (Suffix) | ["ChaosResistance"] / ["ChaosResistance"] / ["ChaosResistance"] | none |

## Discrepant rows

| PoB ID | differing fields | source-native group triplet | observations |
| --- | --- | --- | --- |
| LocalAddedFireDamageTwoHand1 | group | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | none |
| LocalAddedFireDamageTwoHand2 | group | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | none |
| LocalAddedFireDamageTwoHand3 | group | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | none |
| LocalAddedFireDamageTwoHand4 | group | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | none |
| LocalAddedFireDamageTwoHand5 | group | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | none |
| LocalAddedFireDamageTwoHand6 | group | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | none |
| LocalAddedFireDamageTwoHand7 | group | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | none |
| LocalAddedFireDamageTwoHand8_ | group | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | none |
| LocalAddedFireDamageTwoHand9 | group | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | none |
| LocalAddedFireDamageTwoHand10 | group | ["LocalFireDamageTwoHand"] / ["FireDamage"] / ["FireDamage"] | none |
| LocalIncreasedEnergyShield1 | group | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | none |
| LocalIncreasedEnergyShield2 | group | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | none |
| LocalIncreasedEnergyShield3 | group | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | none |
| LocalIncreasedEnergyShield4 | group | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | none |
| LocalIncreasedEnergyShield5 | group | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | none |
| LocalIncreasedEnergyShield6 | group | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | none |
| LocalIncreasedEnergyShield7 | group | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | none |
| LocalIncreasedEnergyShield8 | group | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | none |
| LocalIncreasedEnergyShield9 | group | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | none |
| LocalIncreasedEnergyShield10 | group | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | none |
| LocalIncreasedEnergyShield11 | group | ["LocalEnergyShield"] / ["BaseLocalDefences"] / ["BaseLocalDefences"] | none |
