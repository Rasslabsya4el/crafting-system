# Craft of Exile method inventory (mechanical extraction)

This is syntax-level evidence from cached CoE application code. It does not approve mechanics, availability, or a crafting action catalogue.

| field | value |
| --- | --- |
| source | `sources/raw/coe/package.js` |
| source SHA-256 | `faa6a774f71e32ec261b754a22544826459309e0f894d95db717d6bbaa40f639` |
| extraction command | `python tools/coe_inventory.py --source sources/raw/coe/package.js --output docs/research/coe-method-inventory.md` |
| total named nodes | 95 |
| leaf nodes | 84 |
| custom subsets | 13 |
| options | 2 |
| option choices | 2 |

## Named method nodes

`required`, `cannot`, and `nosim` are local fields only. `absent` means no local field was present; the report makes no inherited-availability claim.

| key path | name | subset | subsim | required | cannot | nosim | options | source line |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| currency | Basic currency | dictionary | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.transmute | Orb of Transmutation | absent | absent | {"rarity":"normal"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.alteration | Orb of Alteration | absent | absent | {"rarity":"magic"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.augmentation | Orb of Augmentation | dictionary | absent | {"rarity":"magic","open":"any"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.augmentation.augmentation_normal | Orb of Augmentation | absent | absent | {"rarity":"magic","open":"any"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.augmentation.augmentation_foulborn | Foulborn Orb of Augmentation | absent | absent | {"rarity":"magic","open":"any"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.regal | Regal Orb | dictionary | absent | {"rarity":"magic","flags":["is_rare"]} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.regal.regal_normal | Regal Orb | absent | absent | {"rarity":"magic","flags":["is_rare"]} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.regal.regal_foulborn | Foulborn Regal Orb | absent | absent | {"rarity":"magic","flags":["is_rare"]} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.alchemy | Orb of Alchemy | absent | absent | {"rarity":"normal","flags":["is_rare"]} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.chaos | Chaos Orb | absent | absent | {"rarity":"rare","flags":["is_rare"]} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.exalted | Exalted Orb | dictionary | absent | {"rarity":"rare","flags":["is_rare"],"open":"any"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.exalted.exalted_normal | Exalted Orb | absent | absent | {"rarity":"rare","flags":["is_rare"],"open":"any"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.exalted.exalted_foulborn | Foulborn Exalted Orb | absent | absent | {"rarity":"rare","flags":["is_rare"],"open":"any"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.scour | Orb of Scouring | absent | absent | absent | {"rarity":"normal"} | absent | absent | `sources/raw/coe/package.js:5` |
| currency.annul | Orb of Annulment | absent | absent | {"affixes":1} | {"rarity":"normal"} | absent | absent | `sources/raw/coe/package.js:5` |
| currency.shaper | Shaper's Exalted Orb | absent | absent | {"rarity":"rare","ilvl":68,"flags":["is_influenced","is_rare"],"open":"any"} | {"influenced":true,"fractured":true,"eldritched":true} | absent | absent | `sources/raw/coe/package.js:5` |
| currency.elder | Elder's Exalted Orb | absent | absent | {"rarity":"rare","ilvl":68,"flags":["is_influenced","is_rare"],"open":"any"} | {"influenced":true,"fractured":true,"eldritched":true} | absent | absent | `sources/raw/coe/package.js:5` |
| currency.crusader | Crusader's Exalted Orb | absent | absent | {"rarity":"rare","ilvl":68,"flags":["is_influenced","is_rare"],"open":"any"} | {"influenced":true,"fractured":true,"eldritched":true} | absent | absent | `sources/raw/coe/package.js:5` |
| currency.hunter | Hunter's Exalted Orb | absent | absent | {"rarity":"rare","ilvl":68,"flags":["is_influenced","is_rare"],"open":"any"} | {"influenced":true,"fractured":true,"eldritched":true} | absent | absent | `sources/raw/coe/package.js:5` |
| currency.redeemer | Redeemer's Exalted Orb | absent | absent | {"rarity":"rare","ilvl":68,"flags":["is_influenced","is_rare"],"open":"any"} | {"influenced":true,"fractured":true,"eldritched":true} | absent | absent | `sources/raw/coe/package.js:5` |
| currency.warlord | Warlord's Exalted Orb | absent | absent | {"rarity":"rare","ilvl":68,"flags":["is_influenced","is_rare"],"open":"any"} | {"influenced":true,"fractured":true,"eldritched":true} | absent | absent | `sources/raw/coe/package.js:5` |
| currency.blessed | Blessed Orb | absent | absent | {"flags":["rollable_implicits"]} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.divine | Divine Orb | absent | absent | {"affixes":1} | {"rarity":"normal"} | absent | absent | `sources/raw/coe/package.js:5` |
| currency.woke | Awakener's Orb | absent | absent | {"ilvl":68,"woke":true,"flags":["is_influenced","is_rare"]} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.maven | Orb of Dominance | absent | absent | {"ilvl":68,"influenced":true,"flags":["is_influenced","is_rare"]} | {"rarity":"normal"} | absent | absent | `sources/raw/coe/package.js:5` |
| currency.fracturing | Fracturing Orb | absent | absent | {"flags":["is_rare"]} | {"influenced":true,"fractured":true,"eldritched":true} | absent | absent | `sources/raw/coe/package.js:5` |
| currency.vaal | Vaal Orb | absent | absent | absent | {"bgroup":"\|10\|13\|14\|"} | absent | absent | `sources/raw/coe/package.js:5` |
| currency.veiled | Veiled Exalted Orb | absent | absent | {"rarity":"rare","bgroup":poec_constants.constraints.veil_bgroups,"flags":["is_rare"]} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| currency.veiledchaos | Veiled Chaos Orb | absent | absent | {"rarity":"rare","bgroup":poec_constants.constraints.veil_bgroups,"flags":["is_rare"]} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| fossil | Fossil | custom | "fossils" | {"flags":["is_fossil"]} | {"rarity":"magic","meta":true} | absent | absent | `sources/raw/coe/package.js:5` |
| harvest | Harvest crafting | dictionary | absent | absent | {"bgroup":"\|14\|"} | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.haugment | Add/Remove | custom | "harvest_basic_noinf" | {"open":"any"} | {"rarity":"normal"} | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hreplace | Replace | custom | absent | absent | {"rarity":"normal"} | true | absent | `sources/raw/coe/package.js:5` |
| harvest.hnonto | Non-type to type | custom | "harvest_basic" | {"affixes":1} | {"rarity":"normal"} | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hannul | Annul | custom | absent | {"affixes":1} | {"rarity":"normal"} | true | absent | `sources/raw/coe/package.js:5` |
| harvest.hdivine | Divine | custom | absent | {"affixes":1} | {"rarity":"normal"} | true | absent | `sources/raw/coe/package.js:5` |
| harvest.hreroll | Reforge | custom | "harvest_basic" | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hrerollp | Reforge+ | custom | "harvest_basic" | absent | absent | true | absent | `sources/raw/coe/package.js:5` |
| harvest.hresist | Resists | dictionary | absent | absent | {"rarity":"normal"} | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hresist.hrftc | Fire > Cold | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hresist.hrftl | Fire > Lightning | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hresist.hrctf | Cold > Fire | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hresist.hrctl | Cold > Lightning | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hresist.hrltf | Lightning > Fire | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hresist.hrltc | Lightning > Cold | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hhight | High-tier | dictionary | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hhight.htnmo | Normal to magic > one mod | absent | absent | {"rarity":"normal"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hhight.htnmt | Normal to magic > two mod | absent | absent | {"rarity":"normal"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hhight.htmrt | Magic to rare > two mod | absent | absent | {"rarity":"magic"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hhight.htmrr | Magic to rare > three mod | absent | absent | {"rarity":"magic"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hhight.htmrf | Magic to rare > four mod | absent | absent | {"rarity":"magic"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hother | Other | dictionary | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hother.hresf | Reforge keeping prefixes | absent | absent | absent | absent | true | absent | `sources/raw/coe/package.js:5` |
| harvest.hother.hrepf | Reforge keeping suffixes | absent | absent | absent | absent | true | absent | `sources/raw/coe/package.js:5` |
| harvest.hother.rfmlk | Reforge more likely | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hother.rfllk | Reforge less likely | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| harvest.hother.hrrvpsi | Divine all lucky | absent | absent | absent | absent | true | absent | `sources/raw/coe/package.js:5` |
| harvest.hother.hrrvp | Divine prefixes lucky | absent | absent | absent | absent | true | absent | `sources/raw/coe/package.js:5` |
| harvest.hother.hrrvs | Divine suffixes lucky | absent | absent | absent | absent | true | absent | `sources/raw/coe/package.js:5` |
| essence | Essence | custom | "essences" | {"flags":["is_essence"]} | {"rarity":"magic","meta":true} | absent | absent | `sources/raw/coe/package.js:5` |
| catalyst | Catalyst | custom | "catalysts" | {"flags":["is_catalyst"]} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| beast_crafting | Beast crafting | dictionary | absent | absent | {"rarity":"normal"} | absent | absent | `sources/raw/coe/package.js:5` |
| beast_crafting.pretosuf | Prefix > Suffix | absent | absent | absent | {"rarity":"magic"} | absent | absent | `sources/raw/coe/package.js:5` |
| beast_crafting.suftopre | Suffix > Prefix | absent | absent | absent | {"rarity":"magic"} | absent | absent | `sources/raw/coe/package.js:5` |
| beast_crafting.imprint | Imprint | absent | absent | {"rarity":"magic"} | {"bgroup":"\|14\|","fractured":true} | absent | absent | `sources/raw/coe/package.js:5` |
| beast_crafting.restimprint | Restore imprint | absent | absent | absent | {"bgroup":"\|14\|"} | absent | absent | `sources/raw/coe/package.js:5` |
| beast_crafting.breroll | Reroll values | absent | absent | {"rarity":"rare"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| beast_crafting.bcat | Cat | absent | absent | {"bgroup":poec_constants.constraints.beast_bgroups,"open":"suffix"} | {"aspect":true} | absent | absent | `sources/raw/coe/package.js:5` |
| beast_crafting.bavian | Avian | absent | absent | {"bgroup":poec_constants.constraints.beast_bgroups,"open":"suffix"} | {"aspect":true} | absent | absent | `sources/raw/coe/package.js:5` |
| beast_crafting.bspider | Spider | absent | absent | {"bgroup":poec_constants.constraints.beast_bgroups,"open":"suffix"} | {"aspect":true} | absent | absent | `sources/raw/coe/package.js:5` |
| beast_crafting.bcrab | Crab | absent | absent | {"bgroup":poec_constants.constraints.beast_bgroups,"open":"suffix"} | {"aspect":true} | absent | absent | `sources/raw/coe/package.js:5` |
| eldritch | Eldritch crafting | dictionary | absent | {"bgroup":poec_constants.constraints.eldritch_bgroups} | {"influenced":true} | absent | absent | `sources/raw/coe/package.js:5` |
| eldritch.eldritchchaos | Chaos | absent | absent | {"eldritched":true,"dominance":true} | {"rarity":"normal"} | absent | absent | `sources/raw/coe/package.js:5` |
| eldritch.eldritchexalt | Exalted | absent | absent | {"eldritched":true,"dominance":true,"open":"any"} | {"rarity":"normal"} | absent | absent | `sources/raw/coe/package.js:5` |
| eldritch.eldritchannul | Annul | absent | absent | {"eldritched":true,"dominance":true} | {"rarity":"normal"} | absent | absent | `sources/raw/coe/package.js:5` |
| eldritch.eldritchconflict | Orb of Conflict | absent | absent | {"eldritched":true,"dualeldritch":true} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| eldritch.eldritchemberlesser | Lesser Ember | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| eldritch.eldritchembergreater | Greater Ember | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| eldritch.eldritchembergrand | Grand Ember | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| eldritch.eldritchemberexceptional | Exceptional Ember | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| eldritch.eldritchichorlesser | Lesser Ichor | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| eldritch.eldritchichorgreater | Greater Ichor | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| eldritch.eldritchichorgrand | Grand Ichor | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| eldritch.eldritchichorexceptional | Exceptional Ichor | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| scourge | Scourge crafting | dictionary | absent | absent | absent | true | absent | `sources/raw/coe/package.js:5` |
| scourge.scourgetogglecorrupt | Corruption | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| scourge.scourgettexalt | Tainted Exalted Orb | absent | absent | {"rarity":"magic"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| scourge.scourgettdivine | Tainted Divine Teardrop | absent | absent | {"rarity":"magic"} | absent | absent | absent | `sources/raw/coe/package.js:5` |
| corruption_altar | Locus of Corruption | absent | absent | absent | {"bgroup":"\|10\|11\|13\|14\|"} | absent | absent | `sources/raw/coe/package.js:5` |
| vendor | Vendor recipees | custom | absent | absent | absent | true | absent | `sources/raw/coe/package.js:5` |
| bench | Bench crafting | custom | "benchcraft" | {"flags":["is_craftable"]} | absent | absent | "bmd" (default "normal"; choices "normal", "skipf") | `sources/raw/coe/package.js:5` |
| check | Condition check | absent | absent | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |
| modunveil | Unveil modifier | absent | absent | {"bgroup":poec_constants.constraints.veil_bgroups} | absent | absent | "udnpm" (default false; choices absent) | `sources/raw/coe/package.js:5` |
| metamethod | Meta methods | custom | "metamethod" | absent | absent | absent | absent | `sources/raw/coe/package.js:5` |

## Requested declaration anchors

This table records declaration locations only; it does not infer a call graph.

| name | declaration line |
| --- | --- |
| poec_simApplyCraftGO | 2228 |
| poec_simRerollItem | 2428 |
| poec_simRollAffix | 2475 |
| poec_simRemoveAffix | 2499 |
| poec_simClearItem | 2519 |
| poec_simRerollValues | 2529 |
| poec_simRecombinate | 1888 |
| poec_simCheckHReroll | 2751 |
| poec_computeBestFossils | 1494 |
| poec_simRollImplicits | 2819 |
| poec_nsimExecute | absent |
| poec_simApplyBenchCraft | 3319 |
