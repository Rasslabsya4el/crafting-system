# Path of Exile 1 Crafting-Route Benchmark Set

## Scope and validation basis

This benchmark contains **30 distinct source occurrences**. I prioritized text sources, as requested, and treated Path of Building v2.67.2 / patch 3.29 only as the compatibility target rather than a route source. The three SKRYAH examples are retained from your transcription; I did not spend research time reconstructing video slides.

For old routes, “still valid” means the **same material sequence is mechanically executable in 3.29**, not merely that a modern substitute exists. This distinction matters in 3.29 because the old Bestiary split crafts were replaced with Talisman-fracture recipes, Fractured Fossils now fracture rather than split, and several Betrayal/veiled systems changed across 3.24–3.26. citeturn229489search0turn229489search8 Veiled Chaos Orbs are once again distinct currency as of 3.26 and perform the old-style “reforge including a Veiled modifier” operation, while Veiled Exalted Orbs remove a modifier and then add a Veiled modifier. citeturn896539search2turn896539search3

A caution on exact target text: when a text source only says things such as “T1 Strength,” “T1 life,” or “T1 suppression,” I preserve that wording rather than inventing numerical ranges from another database. The benchmark planner should therefore treat those routes as target constraints at the tier level rather than as a tooltip transcription. Probabilities are included only where the route author/source states them.

## Summary table

| id | item | categories | steps | difficulty bucket | patch/source era | valid in 3.29 | source | confidence |
|---|---|---|---:|---|---|---|---|---|
| R01 | ES body armour / Grasping Mail transfer | recombinator, beast/split, fracture, eldritch | 8 | multi-item | SKRYAH, unknown | **no** | quiz transcription | medium |
| R02 | Archdemon Crown | essence, influence, harvest, veiled, bench | 7 | 6–10+ | SKRYAH, pre-3.29 | yes | quiz transcription | medium |
| R03 | Velour Boots | fracture, essence, beast, veiled, eldritch | 8 | 6–10+ | SKRYAH, pre-3.29 | yes | quiz transcription | medium |
| R04 | Penetrating Arrow Quiver | essence, fracture, tag-block, bench, trade | 9 | 6–10+ | 3.29 | yes | guide | high |
| R05 | Strength/all-attributes ring | fracture, essence, bench, trade | 3 | 3–5 | 3.29 | yes | guide | high |
| R06 | Hunter/Elder Heavy Belt | essence, influence, divine, bench | 4 | 3–5 | 3.29 | yes | guide | high |
| R07 | +2 minion Convoking Wand | fossil, veiled, metamod, bench | 5 | 3–5 | 3.25-era guide | yes | guide | high |
| R08 | ES boots | fossil, bench | 2 | 1–2 | modern guide | yes | guide | high |
| R09 | life boots | fossil, bench | 2 | 1–2 | modern guide | yes | guide | high |
| R10 | fractured movement-speed boots | fracture, essence, bench, trade | 2 | 1–2 | 3.26-era guide | yes | guide | high |
| R11 | reservation helmet | fracture, essence, bench, trade | 2 | 1–2 | 3.25 | yes | guide | high |
| R12 | +1 Lightning amulet | fracture, harvest | 2 | 1–2 | modern guide | yes | guide | high |
| R13 | T1 life / double-resist belt | alteration, augmentation/regal, multimod | 3 | 3–5 | 3.15 | yes | reddit | medium |
| R14 | Toxic Rain Hunter bow | alteration, regal, tag-block, multimod | 6 | 6–10+ | 3.25 | yes | reddit/guide transcription | high |
| R15 | ED/chaos bow | alteration, beast imprint, regal, tag-block, multimod, influence exalt | 9 | 6–10+ | 3.10 | mostly yes | reddit | high |
| R16 | +2 CF wand | alteration, regal, multimod, tag-block, harvest | 6 | 6–10+ | 3.21 | yes | reddit | high |
| R17 | +2 Lightning Talisman | alteration, regal, beast imprint, harvest, multimod | 10 | 6–10+ | 3.29 | yes | reddit | high |
| R18 | Crusader/Shaper ES ring | fossil, trade, Awakener's Orb, beast recovery | 8 | multi-item | 3.13 | yes with mod-text caveat | forum | high |
| R19 | dual-influence Cyclone ring | trade, Awakener's Orb, harvest, bench | 4 | multi-item | modern | yes | guide | high |
| R20 | Elder/Shaper RF helmet | essence, harvest, beast metamod, influence | 5 | 3–5 | 3.21 | yes | reddit | high |
| R21 | elevated RF helmet | essence, Harvest augment, influence elevation | 6 | 6–10+ | 3.13 | **no** | reddit | high |
| R22 | GG fractured-resistance boots | fracture, essence, beast, eldritch, veiled, conflict | 10 | 6–10+ | 3.25 | yes | reddit | high |
| R23 | fractured-suppression boots | fracture, essence, eldritch, veiled, bench | 8 | 6–10+ | 3.23 | yes | reddit | high |
| R24 | avoid-shock/suppression boots | fracture, essence, harvest, veiled, trade | 6 | 6–10+ | 3.29 | yes | reddit | high |
| R25 | generic triple-T1 prefixes | alteration, recombinator | 4 | multi-item | 3.25–3.29 | yes, unpredictable mode | reddit | high |
| R26 | five-mod Trickster Necrotic Armour | alteration, recombinator, multimod, beast aspect | 5 macro-steps | multi-item | 3.25 | yes, unpredictable mode | reddit guide | high |
| R27 | 3T1-prefix + T1-suffix chest | alteration, recombinator, Ducat | 5 | multi-item | 3.29 | yes | reddit | medium-high |
| R28 | +2 amulet via recombinators | alteration, recombinator | 5 | multi-item | 3.28 | yes | reddit | medium |
| R29 | Shaper/Elder VLS dagger | essence, recombinator, divine mid-route, harvest, locks | 10 | multi-item | 3.25 | mostly yes | reddit | medium-high |
| R30 | endgame fractured boots with Orb of Conflict | beast, veiled, eldritch, conflict | 5 | 3–5 | modern/Pohx | yes | guide | high |

The coverage target is met with overlap: essence ≥14 routes; alteration/augmentation/regal ≥8; fossils ≥5; Harvest tagged reforges ≥9; attack/caster tag-block ≥6; multimod ≥9; fracture ≥10; Eldritch currency ≥7; influence Exalted/Awakener ≥6; veiled crafting ≥9; Beastcrafting ≥8; recombinators ≥7; mid-route Divine ≥2 if counting R06 plus the explicitly locked-side R29 pattern; and trade/intermediate purchase ≥9. Current metamods and their crafting functions remain available in 3.29, including `Prefixes Cannot Be Changed`, `Suffixes Cannot Be Changed`, `Cannot roll Attack Modifiers`, `Cannot roll Caster Modifiers`, and `Can have up to 3 Crafted Modifiers`. citeturn896539search0turn160508search1

## Benchmark routes

### SKRYAH transcriptions

```json
{
  "id": "R01",
  "title": "Global Defences ES body via Grasping Mail recombination",
  "patch": "unknown, pre-3.29",
  "still_valid": "no",
  "validity_note": "The route relies on splitting the recombined body to isolate Global Defences. In 3.29 the old Bestiary split recipes were replaced with Talisman fracture recipes, and Fractured Fossils now fracture rather than split.",
  "item": {"class": "Body Armour", "base": "Energy Shield body armour", "item_level": null, "influence": []},
  "target": {
    "prefixes": [
      "50% increased Global Defences",
      "+97 to maximum Energy Shield (T1)",
      "74% increased Energy Shield (crafted)"
    ],
    "suffixes": [
      "+1 to Level of Socketed Intelligence Gems (T1)",
      "+35% to Cold Resistance",
      "+23% to Fire Resistance"
    ],
    "implicits": ["Searing Exarch implicit", "Eater of Worlds implicit"],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Get rare Grasping Mail with global def and mana prefix.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Get evasion body with mana and %evasion rating.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Recomb to get evasion chest with global def + % evasion.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":4,"action":"Split to isolate global def.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":5,"action":"Get ES body with flat armour (Dread essence).","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":6,"action":"Recomb.","repeat_until":"global def is transferred to ES body","on_fail":"Return to step 5.","probability":0.5,"probability_source":"SKRYAH slide transcription"},
    {"n":7,"action":"Fill suffixes with eldritch currency.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":8,"action":"Fracture.","repeat_until":"Global Defences fractures","on_fail":"Back to step 5 if you miss.","probability":null,"probability_source":""}
  ],
  "author_reasoning": "",
  "mechanics": ["essence","fracture","eldritch","beast","recombinator"],
  "stated_cost": {"amount":null,"currency":"","date":""},
  "source": {"url":"","author":"SKRYAH quiz","date":"","type":"quiz"},
  "confidence": "medium"
}
```

The 3.29 invalidation is explicit in the 3.29 item/mechanic changes: the old two- and three-way Bestiary split crafts were replaced, and Fractured Fossils changed function. citeturn229489search0

```json
{
  "id": "R02",
  "title": "Horror + Shaper Archdemon Crown",
  "patch": "pre-3.29",
  "still_valid": "yes",
  "validity_note": "Shaper's Exalted Orb, Essence of Horror, Harvest reforge crit, Suffixes Cannot Be Changed, Veiled Chaos Orb and bench blocking all exist in 3.29. Exact odds may differ from the original quiz patch.",
  "item": {"class": "Helmet", "base": "Archdemon Crown", "item_level": 100, "influence": ["Shaper"]},
  "target": {
    "prefixes": [
      "8% increased Area of Effect, +2 to Level of Socketed AoE Gems",
      "+45 to maximum Energy Shield (crafted)"
    ],
    "suffixes": [
      "Socketed Gems deal 30% more Elemental Damage",
      "Socketed Gems are Supported by Level 20 Hypothermia, 17% increased Effect of Cold Ailments",
      "Socketed Spells have +3% to Critical Strike Chance"
    ],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Shaper Exalted Orb.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Spam Essence of Horror until Hypothermia suffix.","repeat_until":"Hypothermia suffix","on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Lock suffix, Harvest reforge crit.","repeat_until":"Socketed Spells have +3% to Critical Strike Chance","on_fail":null,"probability":null,"probability_source":""},
    {"n":4,"action":"Lock suffix, Veiled Chaos.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":5,"action":"Block a prefix (Zombies).","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":6,"action":"Unveil +2 AoE.","repeat_until":"+2 AoE unveil","on_fail":"Repeat veiled stage.","probability":0.45,"probability_source":"SKRYAH slide transcription"},
    {"n":7,"action":"Craft prefix (flat ES).","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "",
  "mechanics": ["essence","bench","metamod","harvest","influence","veiled"],
  "stated_cost": {"amount":null,"currency":"","date":""},
  "source": {"url":"","author":"SKRYAH quiz","date":"","type":"quiz"},
  "confidence": "medium"
}
```

The modern wiki confirms Shaper/Elder/Conqueror Exalted currencies and the current Veiled Chaos operation; Harvest reforges continue to respect prefix/suffix locks. citeturn896539search6turn896539search3turn896539search7

```json
{
  "id": "R03",
  "title": "Avoid-shock suppression Velour Boots",
  "patch": "pre-3.29",
  "still_valid": "yes",
  "validity_note": "The route uses a fractured base, Essence of Torment, Wild Bristle Matron, Veiled Chaos and Eldritch Embers; these remain available in 3.29.",
  "item": {"class": "Boots", "base": "Velour Boots", "item_level": 100, "influence": []},
  "target": {
    "prefixes": [
      "30% increased Movement Speed, 10% increased Movement Speed if you haven't been Hit Recently",
      "+67 to maximum Life (crafted)"
    ],
    "suffixes": [
      "60% chance to Avoid being Shocked",
      "+13% chance to Suppress Spell Damage (T1)",
      "+43% to Fire Resistance (T2)"
    ],
    "implicits": ["40% chance to Avoid being Shocked (Searing Exarch implicit)"],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Get suppression fracture boot.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Spam Avoid Shock essence (Torment) until you hit fire resist.","repeat_until":"desired fire resistance","on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Lock suffixes (Wild Bristle Matron).","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":4,"action":"Veiled Chaos.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":5,"action":"Block prefix (ex. craft life).","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":6,"action":"Unveil move speed.","repeat_until":"movement-speed unveil","on_fail":"Repeat veiled stage.","probability":null,"probability_source":""},
    {"n":7,"action":"Craft life.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":8,"action":"Spam Grand Embers for avoid shock.","repeat_until":"desired Avoid Shock implicit","on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "",
  "mechanics": ["essence","bench","metamod","fracture","eldritch","veiled","beast","trade"],
  "stated_cost": {"amount":null,"currency":"","date":""},
  "source": {"url":"","author":"SKRYAH quiz","date":"","type":"quiz"},
  "confidence": "medium"
}
```

Wild Bristle Matron can force `Suffixes Cannot Be Changed` when all suffixes are occupied because it is the only metamod that is a prefix; that technique is independently documented by the community and current Bestiary references. citeturn549779reddit5turn229489search1

### Current and guide-derived routes

```json
{
  "id": "R04",
  "title": "Insanity-fractured additional-arrow Penetrating Arrow Quiver",
  "patch": "3.29",
  "still_valid": "yes",
  "validity_note": "Published for Curse of the Allflame 3.29.",
  "item": {"class": "Quiver", "base": "Penetrating Arrow Quiver", "item_level": 81, "influence": []},
  "target": {
    "prefixes": ["Maximum Life", "Increased Damage with Bow Skills"],
    "suffixes": ["Tier 1 Strength", "Bow Attacks fire an additional Arrow", "Projectiles Pierce 2 Additional Targets"],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Buy a Penetrating Arrow Quiver with item level 81 or higher; uncorrupted, unfractured and no influence.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Apply an Essence of Insanity to guarantee “Projectiles Pierce 2 Additional Targets”.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Use Orb of Annulment until the quiver has exactly 4 explicit modifiers.","repeat_until":"exactly 4 explicit modifiers","on_fail":"If Projectiles Pierce 2 Additional Targets is removed, return to step 2.","probability":null,"probability_source":""},
    {"n":4,"action":"Use a Fracturing Orb and attempt to fracture “Projectiles Pierce 2 Additional Targets”.","repeat_until":"desired modifier fractures","on_fail":"Return to step 1.","probability":0.25,"probability_source":"PoE Vault guide"},
    {"n":5,"action":"Use Deafening Essence of Rage until “Bow Attacks fire an additional Arrow”.","repeat_until":"Bow Attacks fire an additional Arrow","on_fail":null,"probability":null,"probability_source":""},
    {"n":6,"action":"Ensure at least one open suffix; annul if necessary.","repeat_until":"one open suffix","on_fail":"If Strength or additional Arrow is removed, return to step 5.","probability":null,"probability_source":""},
    {"n":7,"action":"Craft “Cannot roll Attack Modifiers”.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":8,"action":"Use two Exalted Orbs to guarantee Maximum Life and Increased Damage with Bow Skills as the remaining prefixes.","repeat_until":null,"on_fail":null,"probability":1.0,"probability_source":"PoE Vault guide"},
    {"n":9,"action":"Remove “Cannot roll Attack Modifiers” and craft a useful suffix such as Resistances or Attack Speed.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "Cannot roll Attack Modifiers removes the unwanted attack-tagged prefix pool so the two remaining prefix slams are forced.",
  "mechanics": ["essence","bench","metamod","fracture","trade"],
  "stated_cost": {"amount":null,"currency":"","date":"2026"},
  "source": {"url":"https://www.poe-vault.com/guides/shrapnel-ballista-hierophant-gear-flasks","author":"POEGuy / PoE Vault","date":"2026","type":"guide"},
  "confidence": "high"
}
```

The source explicitly gives all nine steps and the 25% fracture chance. citeturn758902search0

```json
{
  "id": "R05",
  "title": "Budget fractured all-attributes Strength ring",
  "patch": "3.29",
  "still_valid": "yes",
  "validity_note": "Published for 3.29.",
  "item": {"class": "Ring", "base": "Rare ring", "item_level": 75, "influence": []},
  "target": {
    "prefixes": ["Maximum Life or another useful prefix"],
    "suffixes": ["12-16 to All Attributes (fractured)", "Tier 1 Strength"],
    "implicits": [],
    "other": ["20% Intrinsic Catalyst quality"]
  },
  "steps": [
    {"n":1,"action":"Buy a rare item level 75+ ring with fractured “12-16 to All Attributes”.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Use Deafening Essence of Rage until extra useful modifiers such as Maximum Life or Resistances.","repeat_until":"acceptable remaining modifiers","on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Apply 20x Intrinsic Catalyst and use the Crafting Bench on any open modifier.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "The fracture and essence guarantee the two mandatory attribute mods.",
  "mechanics": ["essence","bench","fracture","trade"],
  "stated_cost": {"amount":null,"currency":"","date":"2026"},
  "source": {"url":"https://www.poe-vault.com/guides/shrapnel-ballista-hierophant-gear-flasks","author":"POEGuy / PoE Vault","date":"2026","type":"guide"},
  "confidence": "high"
}
```

citeturn758902search0

```json
{
  "id": "R06",
  "title": "Strength-stacking influenced Heavy Belt",
  "patch": "3.29",
  "still_valid": "yes",
  "validity_note": "Published for 3.29.",
  "item": {"class": "Belt", "base": "Heavy Belt", "item_level": 75, "influence": ["Hunter or Elder"]},
  "target": {
    "prefixes": ["Life / Armour as available"],
    "suffixes": ["Tier 1 % Increased Attributes", "Tier 1 Strength"],
    "implicits": ["42 to Strength"],
    "other": ["20% Intrinsic Catalyst quality"]
  },
  "steps": [
    {"n":1,"action":"Buy an item level 75+ Hunter- or Elder-influenced Heavy Belt.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Use Deafening Essence of Rage until Tier 1 % Increased Attributes.","repeat_until":"Tier 1 % Increased Attributes","on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Use Orb of Annulment to remove unwanted modifiers and Exalted Orb to add useful ones.","repeat_until":"acceptable affixes","on_fail":"If Strength or Increased Attributes is removed, return to step 2.","probability":null,"probability_source":""},
    {"n":4,"action":"Apply 20x Intrinsic Catalyst; use a Divine Orb until 14% Increased Attributes; use Blessed Orb until implicit is 42 Strength; bench-craft an open modifier.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "Essence fixes Strength while repeatedly fishing for the influenced % Attributes suffix.",
  "mechanics": ["essence","bench","influence","divine","trade"],
  "stated_cost": {"amount":null,"currency":"","date":"2026"},
  "source": {"url":"https://www.poe-vault.com/guides/shrapnel-ballista-hierophant-gear-flasks","author":"POEGuy / PoE Vault","date":"2026","type":"guide"},
  "confidence": "high"
}
```

citeturn758902search0

```json
{
  "id": "R07",
  "title": "+2 generic minion Convoking Wand",
  "patch": "3.25-era",
  "still_valid": "yes",
  "validity_note": "The fossil combination, prefix lock, Veiled Chaos and bench finish all remain possible in 3.29.",
  "item": {"class": "Wand", "base": "Convoking Wand", "item_level": 84, "influence": []},
  "target": {
    "prefixes": [
      "+1 to level of all Spell Skill Gems",
      "+1 to level of all Minion Skill Gems",
      "Minions deal #% increased Damage"
    ],
    "suffixes": [
      "Trigger a Socketed Spell on Using a Skill, with a # second Cooldown, Spells Triggered this way have 150% more Cost",
      "Zealotry has #% increased Aura Effect",
      "Minions have (14-15)% increased Attack Speed, Minions have (14-15)% increased Cast Speed"
    ],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Use Prime Chaotic Resonators with Corroded Fossil, Jagged Fossil, Shuddering Fossil and Metallic Fossil until the +1 Spell and +1 Minion prefixes are present; continue for desired minion-damage tier.","repeat_until":"desired prefixes","on_fail":null,"probability":null,"probability_source":"Guide states ~10-12 tries for gem-level modifiers; minion-damage prefix about 1/33."},
    {"n":2,"action":"If all suffixes are full, use Orb of Annulment to make room.","repeat_until":"open suffix","on_fail":"If a preferred prefix is removed, restart fossil step.","probability":null,"probability_source":""},
    {"n":3,"action":"Craft “Prefixes Cannot Be Changed” and use a Veiled Chaos Orb.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":4,"action":"Unveil Trigger a Socketed Spell; otherwise repeat or settle for bench-crafted Trigger.","repeat_until":"Trigger unveil or decision to settle","on_fail":"Repeat step 3.","probability":null,"probability_source":""},
    {"n":5,"action":"Craft “Minions have (14-15)% increased Attack Speed, Minions have (14-15)% increased Cast Speed” in a remaining suffix.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "The four-fossil combination sharply constrains the prefix pool and is used to force the two gem-level prefixes.",
  "mechanics": ["fossil","bench","metamod","veiled"],
  "stated_cost": {"amount":null,"currency":"","date":"2024"},
  "source": {"url":"https://www.poe-vault.com/guides/crafting-2-generic-minion-wand","author":"GhazzyTV","date":"2024-07-25","type":"guide"},
  "confidence": "high"
}
```

The guide states roughly 10–12 fossil attempts for the gem-level pair and about 1/33 for a minion-damage prefix. citeturn524167search3

```json
{
  "id": "R08",
  "title": "Dense + Shuddering Energy Shield boots",
  "patch": "modern",
  "still_valid": "yes",
  "validity_note": "",
  "item": {"class": "Boots", "base": "Sorcerer Boots", "item_level": 86, "influence": []},
  "target": {
    "prefixes": ["High Energy Shield", "35% increased Movement Speed or crafted Movement Speed"],
    "suffixes": [],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Use Potent Chaotic Resonators with Dense Fossil and Shuddering Fossil until high Energy Shield and desirable Movement Speed/modifiers.","repeat_until":"acceptable Energy Shield and Movement Speed","on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Bench-craft Movement Speed or additional Energy Shield if there is an appropriate open affix.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "Dense targets Energy Shield while Shuddering targets speed.",
  "mechanics": ["fossil","bench"],
  "stated_cost": {"amount":null,"currency":"","date":""},
  "source": {"url":"https://dev.poe-vault.com/guides/crafting-basic-boots","author":"PoE Vault","date":"2024","type":"guide"},
  "confidence": "high"
}
```

citeturn524167search4

```json
{
  "id": "R09",
  "title": "Pristine + Shuddering life boots",
  "patch": "modern",
  "still_valid": "yes",
  "validity_note": "",
  "item": {"class": "Boots", "base": "Two-Toned Boots or preferred Life base", "item_level": 86, "influence": []},
  "target": {
    "prefixes": ["High Life", "35% increased Movement Speed or crafted Movement Speed"],
    "suffixes": ["useful Resistances if rolled"],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Use 2-socket resonators with Pristine Fossil and Shuddering Fossil until high Life, Movement Speed and acceptable other modifiers.","repeat_until":"acceptable result","on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Bench-craft the missing useful modifier.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "Pristine biases Life while Shuddering biases speed.",
  "mechanics": ["fossil","bench"],
  "stated_cost": {"amount":null,"currency":"","date":""},
  "source": {"url":"https://dev.poe-vault.com/guides/crafting-basic-boots","author":"PoE Vault","date":"2024","type":"guide"},
  "confidence": "high"
}
```

citeturn524167search4

```json
{
  "id": "R10",
  "title": "Fractured Movement Speed intelligence boots",
  "patch": "3.26-era",
  "still_valid": "yes",
  "validity_note": "",
  "item": {"class": "Boots", "base": "Rare Boots", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["30%+ increased Movement Speed (fractured)", "+# to maximum Life, preferably at least 70"],
    "suffixes": ["48 Intelligence from Shrieking Essence of Spite", "open suffix for #% chance to Avoid Elemental Ailments"],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Buy boots with fractured Movement Speed and use Shrieking Essence of Spite until 48 Intelligence, Life and an open suffix.","repeat_until":"48 Intelligence + Life + open suffix","on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Craft #% chance to Avoid Elemental Ailments in the open suffix.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "The fracture guarantees Movement Speed while the essence guarantees Intelligence, leaving only Life and an open suffix to hit.",
  "mechanics": ["essence","bench","fracture","trade"],
  "stated_cost": {"amount":null,"currency":"","date":""},
  "source": {"url":"https://dev.poe-vault.com/guides/ice-shot-deadeye-gear-jewels-and-flasks","author":"PoE Vault","date":"2025","type":"guide"},
  "confidence": "high"
}
```

citeturn524167search8

```json
{
  "id": "R11",
  "title": "Fractured chaos-reservation helmet",
  "patch": "3.25",
  "still_valid": "yes",
  "validity_note": "",
  "item": {"class": "Helmet", "base": "Evasion Helmet", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["High Evasion", "+# to Maximum Life"],
    "suffixes": ["Fractured +% to Chaos Resistance", "#% Increased Mana Reservation Efficiency of Skills"],
    "implicits": ["#% Reduced Mana Cost of Attacks", "#% of Physical Damage from Hits taken as Lightning Damage"],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Buy a fractured Chaos Resistance base and use Essences of Loathing, at least Shrieking, until an open suffix and Evasion/Life prefixes you are happy with.","repeat_until":"acceptable Evasion/Life with open suffix","on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Finish with a crafted Resistance or Attribute as needed.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "Fractured Chaos Resistance plus Loathing permanently supplies two desired suffixes while rolling the defensive prefixes.",
  "mechanics": ["essence","bench","fracture","trade"],
  "stated_cost": {"amount":null,"currency":"","date":""},
  "source": {"url":"https://www.poe-vault.com/guides/elemental-hit-of-the-spectrum-gear-flasks","author":"TbXie","date":"2025","type":"guide"},
  "confidence": "high"
}
```

citeturn758902search6

```json
{
  "id": "R12",
  "title": "Fractured-lightning-resistance +1 Lightning amulet",
  "patch": "modern",
  "still_valid": "yes",
  "validity_note": "",
  "item": {"class": "Amulet", "base": "Amulet", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["+1 to Level of all Lightning Skill Gems"],
    "suffixes": ["Lightning Resistance (fractured)"],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Start from an amulet with Lightning Resistance fractured.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Harvest Reforge Lightning until +1 to Level of all Lightning Skill Gems.","repeat_until":"+1 Lightning Skill Gems","on_fail":null,"probability":0.0288,"probability_source":"PoE Vault example: 200 / 6,950 = 2.88% after fracturing Lightning Resistance"}
  ],
  "author_reasoning": "The fracture removes a large Lightning-tagged suffix from the eligible pool while Harvest guarantees a Lightning-tagged modifier, improving the stated chance from roughly 1/74 to about 1/34.",
  "mechanics": ["harvest","fracture"],
  "stated_cost": {"amount":null,"currency":"","date":""},
  "source": {"url":"https://www.poe-vault.com/guides/early-endgame","author":"PoE Vault","date":"2025","type":"guide"},
  "confidence": "high"
}
```

The guide explicitly gives 0.094% natural odds, 1.338% under Reforge Lightning, and 2.88% after fracturing Lightning Resistance. citeturn376101search6turn376101search8

### Alteration, metamod and influence routes

```json
{
  "id": "R13",
  "title": "Alt-Regal T1 life double-resist belt",
  "patch": "3.15",
  "still_valid": "yes",
  "validity_note": "Alteration, Regal and multimod remain unchanged for this purpose.",
  "item": {"class": "Belt", "base": "Rare Belt", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["T1 Life", "crafted damage modifier"],
    "suffixes": ["T1 Resistance", "T1 Resistance"],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Alt spam for T1 Life and a resist.","repeat_until":"T1 Life + desired resistance","on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Regal for another T1 resist.","repeat_until":"second T1 resistance","on_fail":"Restart if Regal result is unacceptable.","probability":null,"probability_source":""},
    {"n":3,"action":"Multi-mod damage.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "A simple deterministic finish once the rare three-mod core is hit.",
  "mechanics": ["bench","multimod"],
  "stated_cost": {"amount":null,"currency":"","date":"2021"},
  "source": {"url":"https://www.reddit.com/r/pathofexile/comments/pq4owv","author":"Reddit poster","date":"2021-09-18","type":"reddit"},
  "confidence": "medium"
}
```

citeturn160508reddit9

```json
{
  "id": "R14",
  "title": "Toxic Rain Hunter bow with guaranteed +1 and chaos DoT",
  "patch": "3.25",
  "still_valid": "yes",
  "validity_note": "The relevant metamods, Exalted Orb interactions and Alteration/Regal sequence still work in 3.29.",
  "item": {"class": "Bow", "base": "Thicket Bow", "item_level": 78, "influence": ["Hunter"]},
  "target": {
    "prefixes": ["+1 to Level of Socketed Gems", "Chaos Damage over Time modifier"],
    "suffixes": ["T1 Attack Speed", "crafted Chaos Damage over Time Multiplier"],
    "implicits": [],
    "other": ["crafted +2 to Level of Socketed Support Gems"]
  },
  "steps": [
    {"n":1,"action":"Alteration roll a Hunter Thicket Bow (ilvl 78+) for T1 attack speed.","repeat_until":"T1 attack speed","on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Regal Orb.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Annul until only attack speed remains.","repeat_until":"only T1 attack speed remains","on_fail":"If attack speed is annulled, restart at step 1.","probability":null,"probability_source":"Source states 33% or 50% failure depending on whether item has 3 or 2 mods."},
    {"n":4,"action":"Craft “Can have up to 3 Crafted Modifiers” and “Cannot roll Attack Modifiers”.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":5,"action":"Slam two Exalted Orbs to force +1 socketed gems and chaos damage over time.","repeat_until":null,"on_fail":null,"probability":1.0,"probability_source":"Source route"},
    {"n":6,"action":"Finish with +2 to Level of Socketed Support Gems and Chaos Damage over Time Multiplier bench crafts as slots permit.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "With suffix space blocked by multimod and attack-tagged mods excluded, the remaining non-attack prefixes are forced.",
  "mechanics": ["bench","metamod","multimod","influence"],
  "stated_cost": {"amount":3,"currency":"Divine Orb for the two listed metamods, excluding later crafts","date":"2024"},
  "source": {"url":"https://www.reddit.com/r/PathOfExileSSF/comments/1f6a963","author":"Peuget guide transcribed by Reddit poster","date":"2024","type":"reddit"},
  "confidence": "high"
}
```

The documented generic bow interaction—`Cannot roll Attack Modifiers` forcing `+1 to Level of Socketed Gems` when it is the only eligible prefix—is also confirmed by the current metamod documentation. citeturn160508reddit3turn896539search0turn896539search1

```json
{
  "id": "R15",
  "title": "ED bow: T1 DoT multi to +1/+2 multimod and Redeemer slam",
  "patch": "3.10",
  "still_valid": "yes",
  "validity_note": "Core Alteration, imprint, Regal, Cannot roll Attack Modifiers, multimod and Redeemer Exalted operations still exist. Exact desirable Redeemer outcome is build-era dependent.",
  "item": {"class": "Bow", "base": "Maraketh Bow", "item_level": 82, "influence": []},
  "target": {
    "prefixes": ["+1 to Level of Socketed Gems", "crafted +2 to Level of Socketed Support Gems"],
    "suffixes": ["T1 Damage over Time Multiplier", "crafted Chaos Damage over Time Multiplier", "Redeemer modifier"],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Get a non-influenced item level 82 Maraketh Bow.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Use Orb of Alteration until T1 DoT Multi suffix.","repeat_until":"T1 DoT Multi","on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Imprint, Regal, then Annul the Regal-added mod so only T1 DoT Multi remains.","repeat_until":"isolated DoT Multi","on_fail":"Restore imprint and retry.","probability":null,"probability_source":""},
    {"n":4,"action":"Craft “Can have up to 3 Crafted Modifiers” and “Cannot roll Attack Modifiers”.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":5,"action":"Exalted Orb for guaranteed +1 Level of Socketed Gems.","repeat_until":null,"on_fail":null,"probability":1.0,"probability_source":"Source"},
    {"n":6,"action":"Remove crafted modifiers.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":7,"action":"Craft “Can have up to 3 Crafted Modifiers”.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":8,"action":"Craft +2 to Level of Socketed Support Gems and Chaos Damage over Time Multiplier.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":9,"action":"Use a Redeemer's Exalted Orb and pray.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "Multimod is used before the +1 slam to occupy suffix capacity and prevent the Exalted Orb from choosing an unwanted suffix.",
  "mechanics": ["bench","metamod","multimod","beast","influence"],
  "stated_cost": {"amount":null,"currency":"","date":"2020"},
  "source": {"url":"https://www.reddit.com/r/pathofexile/comments/fko4ax","author":"Reddit poster","date":"2020-03-18","type":"reddit"},
  "confidence": "high"
}
```

citeturn160508reddit4

```json
{
  "id": "R16",
  "title": "+2 Corrupting Fever wand via Harvest augment Physical",
  "patch": "3.21",
  "still_valid": "yes",
  "validity_note": "Modern Harvest still has remove/add tagged crafts and respects metamods on the added modifier. Cost and exact pool should be re-evaluated in 3.29.",
  "item": {"class": "Wand", "base": "Fractured wand", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["+1 to Level of all Spell Skill Gems", "+1 Physical Skill Gems", "Spell Damage if available"],
    "suffixes": ["Physical Damage over Time Multiplier", "Attack Speed or crafted suffix"],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Alt-spam the fractured magic base for +1 all skill gems; Regal and annul the extra mod if it is not Spell Damage.","repeat_until":"+1 all Spell Skill Gems with usable rare state","on_fail":"Restart isolation if +1 is lost.","probability":null,"probability_source":""},
    {"n":2,"action":"Craft Multimod + Cannot Roll Attack Modifiers + a crafted prefix if the prefix slot is open.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Harvest Remove/Add Physical to get +1 Physical Skill Gems.","repeat_until":"+1 Physical Skill Gems","on_fail":null,"probability":0.75,"probability_source":"Reddit route states 75%."},
    {"n":4,"action":"With +2 Skill Gems and an open prefix, craft Multimod + Prefixes Cannot Be Changed + a crafted prefix.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":5,"action":"Harvest Reforge Physical for Physical Damage over Time Multiplier.","repeat_until":"acceptable Physical DoT Multiplier","on_fail":"Clean suffixes and repeat if desired.","probability":null,"probability_source":""},
    {"n":6,"action":"Optionally use a veiled step, then craft the missing Attack Speed or Spell Damage.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "Cannot Roll Attack Modifiers narrows the Physical augment so the +Physical-gem prefix has a high stated hit rate.",
  "mechanics": ["bench","metamod","multimod","harvest","fracture","veiled"],
  "stated_cost": {"amount":null,"currency":"","date":"2023"},
  "source": {"url":"https://www.reddit.com/r/PathOfExileBuilds/comments/12pwzb0","author":"Reddit commenter","date":"2023","type":"reddit"},
  "confidence": "high"
}
```

citeturn160508reddit5turn896539search7

```json
{
  "id": "R17",
  "title": "3.29 +2 Lightning rare Talisman with imprint loops",
  "patch": "3.29",
  "still_valid": "yes",
  "validity_note": "This is a 3.29 route built around the new rare-Talisman imprint ecosystem.",
  "item": {"class": "Amulet", "base": "Rare Talisman", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["+1 to Level of all Skill Gems", "+1 to Level of all Lightning Skill Gems", "additional desired exalted prefixes"],
    "suffixes": ["desired exalted suffixes"],
    "implicits": ["desired Talisman implicit after Ducat manipulation"],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Buy a bunch of +1 implicit Croaker Talismans.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Put Gilded Fossil on all of them.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Use Vesper to replace the implicit with Ukatoa's Ducat and hope to hit the desired implicit.","repeat_until":"desired implicit","on_fail":null,"probability":null,"probability_source":""},
    {"n":4,"action":"Alteration spam for +1 all skills.","repeat_until":"+1 all skills","on_fail":null,"probability":null,"probability_source":""},
    {"n":5,"action":"Regal to rare.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":6,"action":"Imprint and annul to a 1-mod item with only +1 all skills left.","repeat_until":"isolated +1 all skills","on_fail":"Restore imprint and retry.","probability":null,"probability_source":""},
    {"n":7,"action":"Craft Can have up to 3 Crafted Modifiers + Prefixes Cannot Be Changed + Cannot roll Attack Modifiers.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":8,"action":"Harvest augment a new Lightning modifier and remove a random modifier.","repeat_until":"+1 all Lightning skills","on_fail":null,"probability":null,"probability_source":""},
    {"n":9,"action":"Imprint the +2 state.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":10,"action":"Exalted Orb repeatedly, restoring the imprint on failures, to build desired prefixes first and then suffixes.","repeat_until":"desired final affixes","on_fail":"Restore imprint.","probability":null,"probability_source":""}
  ],
  "author_reasoning": "The rare-Talisman imprint lets the crafter repeatedly return to a valuable +2 checkpoint after failed Exalted slams.",
  "mechanics": ["bench","metamod","multimod","harvest","fossil","beast","trade"],
  "stated_cost": {"amount":null,"currency":"","date":"2026"},
  "source": {"url":"https://www.reddit.com/r/pathofexile/comments/1vtv3u0","author":"Reddit poster","date":"2026","type":"reddit"},
  "confidence": "high"
}
```

This route is particularly useful for a 3.29 benchmark because patch 3.29 explicitly reworked Bestiary around Talismans, while Craft of Exile’s 3.29 changelog says it implemented the new Talisman fracture crafts. citeturn160508reddit7turn229489search0turn229489search8

### Awakener and influenced-item routes

```json
{
  "id": "R18",
  "title": "Crusader %ES + Shaper Assassin's Mark ring",
  "patch": "3.13",
  "still_valid": "yes",
  "validity_note": "Awakener's Orb and the isolation principle remain valid. The historical Assassin's Mark modifier text may differ from the current mod pool, so validate the exact target mod against 3.29 data before scoring.",
  "item": {"class": "Ring", "base": "Moonstone Ring / Unset Ring / preferred ring", "item_level": 84, "influence": ["Crusader","Shaper"]},
  "target": {
    "prefixes": ["T1 #% increased maximum Energy Shield (Crusader)", "flat Energy Shield if available"],
    "suffixes": ["Trigger Level 12 Assassin's Mark when you Hit a Rare or Unique Enemy"],
    "implicits": [],
    "other": ["20% Tempering Catalyst quality"]
  },
  "steps": [
    {"n":1,"action":"Buy an item level ~84 Crusader ring as the destination base; scour and apply Tempering Catalysts.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Optionally use a Gilded Fossil for an extra implicit.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Craft with Dense Fossils or Chaos Orbs until T1 #% increased maximum Energy Shield.","repeat_until":"T1 % maximum Energy Shield","on_fail":null,"probability":null,"probability_source":""},
    {"n":4,"action":"Remove any other Crusader modifiers, using annul or prefix/suffix swap where appropriate.","repeat_until":"only desired Crusader influence modifier remains","on_fail":"Recraft if desired mod is lost.","probability":null,"probability_source":""},
    {"n":5,"action":"Buy a Shaper ring with only the Assassin's Mark influence modifier.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":6,"action":"Verify each input has exactly one influence modifier.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":7,"action":"Use Awakener's Orb on the Shaper donor first, then on the Crusader destination ring.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":8,"action":"Inspect the random remaining affixes and craft flat ES if an open prefix is available.","repeat_until":null,"on_fail":"Author suggests beast prefix/suffix swaps or annuls as risky recovery.","probability":null,"probability_source":""}
  ],
  "author_reasoning": "Ensuring exactly one influenced modifier on each input makes Awakener's Orb carry exactly the two wanted influence mods.",
  "mechanics": ["fossil","bench","influence","awakener","beast","trade"],
  "stated_cost": {"amount":null,"currency":"Exalted Orb era","date":"2020"},
  "source": {"url":"https://www.pathofexile.com/forum/view-thread/2920750","author":"PoE forum build author","date":"2020","type":"forum"},
  "confidence": "high"
}
```

citeturn376101search2

```json
{
  "id": "R19",
  "title": "Dual-influence Cyclone ring then caster reforge",
  "patch": "modern",
  "still_valid": "yes",
  "validity_note": "Awakener's Orb and Harvest Reforge Caster remain valid mechanics.",
  "item": {"class": "Ring", "base": "Rare Ring", "item_level": null, "influence": ["dual influence"]},
  "target": {
    "prefixes": ["-# to Total Mana Cost"],
    "suffixes": ["Attacks have +# to Critical Strike Chance", "caster-tagged desired outcome"],
    "implicits": [],
    "other": ["crafted Block Chance"]
  },
  "steps": [
    {"n":1,"action":"Buy two items, one with -# to Total Mana Cost and one with Attacks have +# to Critical Strike Chance.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Use an Awakener's Orb to combine them.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Craft “Suffixes Cannot Be Changed” and Harvest “Reforge Caster”.","repeat_until":"acceptable caster result","on_fail":null,"probability":null,"probability_source":""},
    {"n":4,"action":"Finish by crafting Block Chance.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "Awakener's Orb establishes the two influence mods; the metamod protects the suffix side during the tagged reforge.",
  "mechanics": ["bench","metamod","harvest","awakener","trade"],
  "stated_cost": {"amount":null,"currency":"","date":"2026"},
  "source": {"url":"https://dev.poe-vault.com/guides/murder-on-a-budget-cyclone-slayer-gear-jewels-flasks","author":"PoE Vault","date":"2026","type":"guide"},
  "confidence": "high"
}
```

citeturn758902search3

### RF helmet routes showing patch evolution

```json
{
  "id": "R20",
  "title": "Horror Trap-and-Mine RF helmet with Harvest Burning + Conc Effect",
  "patch": "3.21",
  "still_valid": "yes",
  "validity_note": "The essence, metamod and Harvest reforge sequence remains mechanically available. Influence-mod pools should be validated against 3.29.",
  "item": {"class": "Helmet", "base": "Eternal Burgonet", "item_level": null, "influence": ["Shaper","Elder"]},
  "target": {
    "prefixes": ["Socketed Gems are Supported by Concentrated Effect"],
    "suffixes": ["Socketed Gems deal 30% more Elemental Damage", "Socketed Gems are Supported by Trap and Mine Damage", "Socketed Gems are Supported by Burning Damage"],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Create a dual Shaper/Elder Eternal Burgonet base using Awakener's Orb.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Essence of Horror until the 30% more elemental damage essence mod and Trap and Mine suffix appear.","repeat_until":"Trap and Mine suffix","on_fail":null,"probability":null,"probability_source":"Author states ~70 essences on average."},
    {"n":3,"action":"If there is a third unwanted suffix, annul it.","repeat_until":"open suffix","on_fail":"If desired suffix is removed, return to step 2.","probability":null,"probability_source":""},
    {"n":4,"action":"Craft Suffixes Cannot Be Changed and Harvest Reforge Fire for Burning Damage.","repeat_until":"Burning Damage","on_fail":"Attempt annul to reopen suffix, otherwise return to essence stage.","probability":0.16,"probability_source":"Author states ~16% for any tier and ~5% for top tier."},
    {"n":5,"action":"Use Wild Bristle Matron for Suffixes Cannot Be Changed, then Harvest Reforge Influence for Concentrated Effect.","repeat_until":"Concentrated Effect","on_fail":"Repeat if prefixes remain recoverable.","probability":0.15,"probability_source":"Author gives ~15% for Concentrated Effect."}
  ],
  "author_reasoning": "Essence establishes two hard suffixes; tagged Fire reforge targets Burning Damage, then locked suffixes let influence reforges work only on prefixes.",
  "mechanics": ["essence","bench","metamod","harvest","influence","awakener","beast"],
  "stated_cost": {"amount":36,"currency":"Divine Orb average to three-suffix stage, author estimate","date":"2023"},
  "source": {"url":"https://www.reddit.com/r/pathofexile/comments/12vmj60","author":"Reddit poster","date":"2023-04-22","type":"reddit"},
  "confidence": "high"
}
```

citeturn509945reddit7

```json
{
  "id": "R21",
  "title": "Legacy elevated 7-link RF helmet",
  "patch": "3.13",
  "still_valid": "no",
  "validity_note": "The route uses old Harvest deterministic 'add fire' / remove-add style crafting and the historical Maven's Orb workflow. Modern Harvest no longer reproduces this exact sequence, so keep it as a legacy benchmark rather than a 3.29 executable route.",
  "item": {"class": "Helmet", "base": "Influenced Helmet", "item_level": null, "influence": ["Elder","Shaper or relevant second influence"]},
  "target": {
    "prefixes": ["Elevated Concentrated Effect", "T1 maximum Life", "+1 AoE Gems level"],
    "suffixes": ["Socketed Gems deal 30% more Elemental Damage", "T1 Burning Damage", "Nearby Enemies have -9% to Fire Resistance"],
    "implicits": [],
    "other": ["40% increased Righteous Fire damage enchant", "4 white sockets", "30% quality"]
  },
  "steps": [
    {"n":1,"action":"Use Essence of Horror or Glyphic Fossil until the 30% more damage essence mod and -9% fire resistance suffix are together.","repeat_until":"30% more Elemental Damage + nearby -9% Fire Resistance","on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Use old Harvest add Fire repeatedly for T1 Burning Damage; manipulate/remove Fire Resistance outcomes as described by the author.","repeat_until":"T1 Burning Damage","on_fail":"If removal hits the -9% resistance mod, return to step 1.","probability":null,"probability_source":""},
    {"n":3,"action":"Use old keep-suffixes/reroll-prefixes until T1 Concentrated Effect.","repeat_until":"T1 Concentrated Effect","on_fail":null,"probability":null,"probability_source":""},
    {"n":4,"action":"Add another influence modifier.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":5,"action":"Craft Suffixes Cannot Be Changed.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":6,"action":"Use Maven's Orb to elevate Concentrated Effect.","repeat_until":"elevated Concentrated Effect","on_fail":"Rebuild influence prefix stage.","probability":0.5,"probability_source":"Author states 1/2."}
  ],
  "author_reasoning": "Old Harvest let the suffixes be assembled almost deterministically before repeatedly targeting and elevating the support prefix.",
  "mechanics": ["essence","fossil","bench","metamod","harvest","influence"],
  "stated_cost": {"amount":null,"currency":"","date":"2021"},
  "source": {"url":"https://www.reddit.com/r/pathofexile/comments/lebaj9","author":"Reddit poster","date":"2021-02-07","type":"reddit"},
  "confidence": "high"
}
```

citeturn509945reddit5

### Eldritch and Veiled routes

```json
{
  "id": "R22",
  "title": "Fractured-resistance GG boots with Eldritch life and veiled movement",
  "patch": "3.25",
  "still_valid": "yes",
  "validity_note": "All core mechanics remain in 3.29.",
  "item": {"class": "Boots", "base": "Rare Boots", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["high-tier Life", "Movement Speed / Chance to Avoid Being Chilled unveil"],
    "suffixes": ["fractured Resistance", "essence Resistance", "Spell Suppression"],
    "implicits": ["desired Eater of Worlds implicit", "desired Searing Exarch implicit"],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Buy a fractured Resistance base.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Essence spam the other resistance until T1 Spell Suppression.","repeat_until":"T1 Spell Suppression","on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Wild Bristle Matron for Suffixes Cannot Be Changed, then Scour to remove prefixes.","repeat_until":"clean prefixes","on_fail":null,"probability":null,"probability_source":""},
    {"n":4,"action":"Make Searing Exarch dominant.","repeat_until":"Exarch dominant","on_fail":null,"probability":null,"probability_source":""},
    {"n":5,"action":"Bench-block Mana, Eldritch Exalted Orb for Life, and Eldritch Annul bad prefixes; repeat until acceptable Life.","repeat_until":"acceptable Life","on_fail":"Eldritch Annul and repeat.","probability":null,"probability_source":""},
    {"n":6,"action":"Wild Bristle Matron again for Suffixes Cannot Be Changed.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":7,"action":"Use Veiled Orb / current equivalent and hope it removes the metamod instead of Life.","repeat_until":"Life survives and a veiled prefix is added","on_fail":"Return to Eldritch Life stage.","probability":0.5,"probability_source":"Commenter describes it as 50/50."},
    {"n":8,"action":"Unveil a movement-speed modifier, preferably Movement Speed / Chance to Avoid Being Chilled.","repeat_until":"desired unveil","on_fail":"Repeat veiled stage.","probability":null,"probability_source":""},
    {"n":9,"action":"Bench-craft Chance to Avoid Being Frozen.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":10,"action":"Use Ichors and Embers for final implicits; use Orb of Conflict when a tier above Exceptional is required.","repeat_until":"desired implicit tiers","on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "Eldritch dominance lets only prefixes be added/removed while the finished suffixes stay untouched.",
  "mechanics": ["essence","bench","metamod","fracture","eldritch","veiled","beast","trade"],
  "stated_cost": {"amount":null,"currency":"","date":"2024"},
  "source": {"url":"https://www.reddit.com/r/pathofexile/comments/1f4gr9m","author":"Reddit commenter","date":"2024-08-30","type":"reddit"},
  "confidence": "high"
}
```

Eldritch Exalted/Annul/Chaos operations are controlled by which implicit is dominant, and Eldritch items cannot simultaneously carry Shaper/Elder/Conqueror influence. citeturn474476reddit5turn896539search4turn474476search1

```json
{
  "id": "R23",
  "title": "Fractured suppression ailment-avoid boots",
  "patch": "3.23",
  "still_valid": "yes",
  "validity_note": "The old suggestion of T4 Aisling is obsolete, but the source explicitly recommends Veiled Chaos as the alternative; Veiled Chaos exists again in 3.29.",
  "item": {"class": "Boots", "base": "Rare Boots", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["Movement Speed unveil", "crafted Life"],
    "suffixes": ["fractured chance to Suppress Spell Damage", "Essence elemental-avoidance suffix", "T1 Chaos Resistance"],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Buy fractured Suppress Spell Damage base.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Spam elemental-avoidance Essence until T1 Chaos Resistance.","repeat_until":"T1 Chaos Resistance","on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"If prefixes are full, use an Eldritch Annul to remove a prefix.","repeat_until":"open prefix","on_fail":null,"probability":null,"probability_source":""},
    {"n":4,"action":"Craft Suffixes Cannot Be Changed.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":5,"action":"Use Veiled Chaos Orb.","repeat_until":"veiled prefix","on_fail":null,"probability":null,"probability_source":""},
    {"n":6,"action":"Block Mana.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":7,"action":"Unveil Movement Speed.","repeat_until":"Movement Speed","on_fail":"Repeat veiled stage.","probability":null,"probability_source":""},
    {"n":8,"action":"Craft Life.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "",
  "mechanics": ["essence","bench","metamod","fracture","eldritch","veiled","trade"],
  "stated_cost": {"amount":null,"currency":"","date":"2024"},
  "source": {"url":"https://www.reddit.com/r/PathOfExileBuilds/comments/199642y","author":"Reddit commenter","date":"2024-01-17","type":"reddit"},
  "confidence": "high"
}
```

citeturn474476reddit7turn896539search3

```json
{
  "id": "R24",
  "title": "3.29 Mana-fractured Avoid Shock / Suppression boots",
  "patch": "3.29",
  "still_valid": "yes",
  "validity_note": "Contemporary April 2026 route.",
  "item": {"class": "Boots", "base": "Rare Boots", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["fractured Mana", "Movement Speed + Onslaught veil"],
    "suffixes": ["Avoid Shock essence modifier", "T1 Spell Suppression", "T2+ Elemental Resistance"],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Fracture or purchase Mana.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Spam Avoid Shock essence until T1 Suppress.","repeat_until":"T1 Suppress","on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Ensure one open prefix and one open suffix, annulling if necessary.","repeat_until":"one open prefix and suffix","on_fail":"If Suppress or Avoid Shock is annulled, return to step 2.","probability":null,"probability_source":""},
    {"n":4,"action":"Reforge Fire/Cold/Lightning for a T2+ Resistance.","repeat_until":"T2+ Resistance","on_fail":"Attempt to annul the bad Resistance; if a core suffix is lost, return to step 2.","probability":null,"probability_source":""},
    {"n":5,"action":"Lock suffixes.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":6,"action":"Veiled Chaos for Movement Speed + Onslaught.","repeat_until":"Movement Speed + Onslaught unveil","on_fail":"Repeat locked veiled stage.","probability":null,"probability_source":""}
  ],
  "author_reasoning": "",
  "mechanics": ["essence","metamod","harvest","fracture","veiled","trade"],
  "stated_cost": {"amount":20,"currency":"Divine Orb realistic estimate; commenter reports 30 Divines spent on a similar craft","date":"2026-04"},
  "source": {"url":"https://www.reddit.com/r/PathOfExileBuilds/comments/1sbqob9/how_would_i_craft_these_boots/","author":"Reddit commenter","date":"2026-04-03","type":"reddit"},
  "confidence": "high"
}
```

The thread gives both a best-case estimate around 8 Divines and a more realistic 20 Divine estimate; a commenter later reports spending about 30 Divines on a similar craft. citeturn540623reddit0

### Recombinator routes

```json
{
  "id": "R25",
  "title": "Generic triple-T1 prefix recombination by overlapping pairs",
  "patch": "3.25-3.29",
  "still_valid": "yes",
  "validity_note": "Applicable to current Unpredictable Recombination; current Recombinator also has a separate Predictable mode.",
  "item": {"class": "Weapon or Armour", "base": "same item class", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["T1 prefix A", "T1 prefix B", "T1 prefix C"],
    "suffixes": [],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Isolate single-mod feeder bases A, B and C, usually with Alteration/Augmentation.","repeat_until":"three isolated desired prefixes","on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Recombine A + B until AB survives.","repeat_until":"AB two-prefix feeder","on_fail":"Recycle surviving feeders.","probability":null,"probability_source":""},
    {"n":3,"action":"Recombine A + C until AC survives.","repeat_until":"AC two-prefix feeder","on_fail":"Recycle surviving feeders.","probability":null,"probability_source":""},
    {"n":4,"action":"Recombine AB + AC for ABC.","repeat_until":"all three desired prefixes","on_fail":"Reuse outputs containing useful overlapping pairs.","probability":null,"probability_source":""}
  ],
  "author_reasoning": "Doubling an overlapping desired mod in both inputs improves retention and avoids risking the rarest mod in unnecessary feeder construction.",
  "mechanics": ["recombinator"],
  "stated_cost": {"amount":null,"currency":"","date":"2026"},
  "source": {"url":"https://www.reddit.com/r/PathOfExileBuilds/comments/1t9bx0h/","author":"Reddit commenters","date":"2026-05-10","type":"reddit"},
  "confidence": "high"
}
```

The same AB/AC → ABC logic is independently described in both 2024 and 2026 recombination discussions; the current wiki confirms that Unpredictable Recombination still uses pooled prefixes/suffixes while Predictable Recombination is now separately selectable. citeturn540623reddit7turn540623reddit3turn896539search5

```json
{
  "id": "R26",
  "title": "Five-mod Trickster Necrotic Armour via exclusive-mod recombination",
  "patch": "3.25",
  "still_valid": "yes",
  "validity_note": "The route is for the post-3.25 recombinator rules and remains applicable to Unpredictable Recombination in 3.29.",
  "item": {"class": "Body Armour", "base": "Necrotic Armour", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["T1 flat Evasion and Energy Shield", "T1 % Evasion and Energy Shield", "T1 hybrid % Evasion and Energy Shield"],
    "suffixes": ["T1 chance to Suppress Spell Damage", "T1 Intelligence"],
    "implicits": ["Eldritch implicits to taste"],
    "other": ["crafted % Attributes"]
  },
  "steps": [
    {"n":1,"action":"Create five one-mod feeder Necrotic Armours by Alteration spamming the three desired prefixes, T1 Spell Suppression and T1 Intelligence.","repeat_until":"single-mod feeders","on_fail":null,"probability":null,"probability_source":"Author states ~1/19 for desired prefixes and ~1/48 for suffix feeders in Craft of Exile."},
    {"n":2,"action":"Recombine single-mod feeders into two-mod prefix feeders and a two-mod suffix feeder.","repeat_until":"required two-mod feeders","on_fail":"Recycle useful outputs.","probability":0.33,"probability_source":"Author gives 33% example for a simple two-prefix feeder; ~41% when exclusive mods are added."},
    {"n":3,"action":"Use Can have up to 3 Crafted Modifiers and Bestiary Aspect crafts to add exclusive mods, then recombine the two-mod prefix and suffix feeders into a four-desired-mod feeder.","repeat_until":"four desired natural mods","on_fail":"Keep useful three-mod outputs for alternate path.","probability":0.45,"probability_source":"Author says about 45% for the illustrated four-mod result."},
    {"n":4,"action":"Combine the four-mod feeder with another two-prefix feeder containing the missing hybrid prefix; add exclusive mods to both inputs first.","repeat_until":"all five desired natural mods","on_fail":"Recycle resulting four- or three-mod feeders.","probability":null,"probability_source":""},
    {"n":5,"action":"Craft % Attributes, then finish sockets, links, Divine rolls and Eldritch implicits to taste.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "Exclusive crafted and Bestiary Aspect mods increase the probability of selecting the desired number of prefixes/suffixes while being unable to coexist in the output.",
  "mechanics": ["bench","multimod","beast","recombinator","divine"],
  "stated_cost": {"amount":20,"currency":"Divine Orb, author's completed craft","date":"2024"},
  "source": {"url":"https://www.reddit.com/r/pathofexile/comments/1f5k4uq/guide_how_to_craft_bis_trickster_body_armour_for/","author":"Sheeepishly","date":"2024-08-31","type":"reddit"},
  "confidence": "high"
}
```

The author reports a 20 Divine completed cost versus a contemporary 100–125 Divine market price, and explicitly gives the one-mod feeder rates, 33/41% two-mod examples, and about 45% four-mod combination chance. citeturn348209view0 The underlying 3.25 recombinator research was based on roughly 500–800 tests and documents exclusive modifiers including crafted mods, metamods, Bestiary Aspects, essences and veiled mods. citeturn348209view1

```json
{
  "id": "R27",
  "title": "3.29 three-T1-prefix plus suppression chest using Ducat setup",
  "patch": "3.29",
  "still_valid": "yes",
  "validity_note": "Contemporary September 2026 route.",
  "item": {"class": "Body Armour", "base": "desired final body-armour base", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["T1 prefix A", "T1 prefix B", "T1 prefix C"],
    "suffixes": ["T1 Spell Suppression"],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Recombine a T1 prefix with T1 Spell Suppression to create a 1-prefix/1-suffix feeder.","repeat_until":"1p/1s feeder","on_fail":"Recycle outputs.","probability":null,"probability_source":""},
    {"n":2,"action":"Recombine the other two T1 prefixes into a 2-prefix feeder.","repeat_until":"2p feeder","on_fail":"Recycle outputs.","probability":null,"probability_source":""},
    {"n":3,"action":"Clear all other modifiers from the two feeders.","repeat_until":"only desired mods remain","on_fail":null,"probability":null,"probability_source":""},
    {"n":4,"action":"Add a Pantheon suffix with the boat to one of the items.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":5,"action":"Recombine the feeders and repeat until three T1 prefixes plus the T1 suffix survive.","repeat_until":"3 desired prefixes + desired suffix","on_fail":"Recycle 2p/1s and useful 2p outputs.","probability":0.1,"probability_source":"Commenter states 10% with only three prefixes in the pool; states 30% in the described 2p/1s + 2p/Pantheon setup."}
  ],
  "author_reasoning": "The Pantheon/Ducat setup manipulates the suffix side while keeping only the three desired prefixes in the prefix pool.",
  "mechanics": ["recombinator"],
  "stated_cost": {"amount":null,"currency":"~8000 Alteration Orbs and ~40 bases quoted by another commenter for a perfect 3p2s chest","date":"2026-09"},
  "source": {"url":"https://www.reddit.com/r/pathofexile/comments/1w9wdj0/","author":"Reddit commenter","date":"2026-09-07","type":"reddit"},
  "confidence": "medium"
}
```

citeturn540623reddit4

```json
{
  "id": "R28",
  "title": "Fully recombined +2 amulet",
  "patch": "3.28",
  "still_valid": "yes",
  "validity_note": "Current Recombinator still supports Unpredictable Recombination.",
  "item": {"class": "Amulet", "base": "Rare Amulet", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["two desired +1 skill-gem prefixes", "third desired prefix"],
    "suffixes": ["two desired suffixes"],
    "implicits": [],
    "other": []
  },
  "steps": [
    {"n":1,"action":"Buy many cheap rare amulet bases, scour them and make them magic.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Use Alteration Orbs to make one-affix feeder bases for each target mod.","repeat_until":"required one-affix feeders","on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Recombine feeders into two-suffix and two-prefix items.","repeat_until":"2s and 2p feeders","on_fail":"Recycle useful outputs.","probability":null,"probability_source":""},
    {"n":4,"action":"Recombine into a 2-prefix/2-suffix item.","repeat_until":"2p2s","on_fail":"Recycle useful outputs.","probability":null,"probability_source":""},
    {"n":5,"action":"Recombine onward until a 3-prefix/2-suffix finished amulet is produced.","repeat_until":"3p2s target","on_fail":"Recycle useful outputs.","probability":null,"probability_source":""}
  ],
  "author_reasoning": "The crafter built every target affix from isolated Alteration-rolled feeders rather than purchasing +1 bases.",
  "mechanics": ["recombinator","trade"],
  "stated_cost": {"amount":30000,"currency":"approximately Alteration Orbs, author's estimate","date":"2026-02"},
  "source": {"url":"https://www.reddit.com/r/pathofexile/comments/1r1l92p/crafting_2_amulet/","author":"Reddit poster","date":"2026-02-11","type":"reddit"},
  "confidence": "medium"
}
```

citeturn509945reddit12

### Divine-under-lock and high-end imprint routes

```json
{
  "id": "R29",
  "title": "Triple-prefix VLS dagger with prefix Divine, recombination and lock-fished suffixes",
  "patch": "3.25",
  "still_valid": "yes",
  "validity_note": "The recombinator, Divine, Prefixes Cannot Be Changed, Harvest Speed reforge and Hinekora's Lock pieces are still available. The historical runesmithing finish is league-specific and should be omitted or substituted when evaluating only permanent 3.29 systems.",
  "item": {"class": "Dagger", "base": "Ambusher", "item_level": null, "influence": ["Shaper","Elder"]},
  "target": {
    "prefixes": [
      "Essence lightning damage prefix",
      "Socketed Gems are Supported by Level 20 Elemental Damage with Attacks",
      "Socketed Skills deal 40% more Attack Damage"
    ],
    "suffixes": [
      "Socketed Gems are Supported by Level 20 Faster Attacks",
      "Socketed Gems are Supported by Level 20 Increased Critical Damage or Increased Critical Strikes",
      "the other Level 20 Increased Critical Damage or Increased Critical Strikes support"
    ],
    "implicits": [],
    "other": ["historical 100% Vaal soul reduction Runesmith enchant"]
  },
  "steps": [
    {"n":1,"action":"Prepare two Shaper/Elder Ambusher bases.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Use Deafening Essence of Wrath until Level 20 Elemental Damage with Attacks on one and Socketed Skills deal 40% more Attack Damage on the other.","repeat_until":"two required influence-prefix feeders","on_fail":null,"probability":null,"probability_source":""},
    {"n":3,"action":"Recombine until all three desired prefixes survive.","repeat_until":"three desired prefixes","on_fail":"Rebuild/recycle feeders.","probability":null,"probability_source":""},
    {"n":4,"action":"If extra suffixes remain, craft Prefixes Cannot Be Changed and annul until only the three prefixes remain.","repeat_until":"clean suffixes","on_fail":"Recraft metamod as necessary.","probability":null,"probability_source":""},
    {"n":5,"action":"Divine the three prefixes to desired rolls while the craft is still at the prefix-complete stage.","repeat_until":"desired prefix values","on_fail":null,"probability":null,"probability_source":""},
    {"n":6,"action":"Craft Prefixes Cannot Be Changed and Harvest Reforge Speed until Level 20 Faster Attacks.","repeat_until":"Level 20 Faster Attacks","on_fail":"Repeat metamod + reforge.","probability":null,"probability_source":""},
    {"n":7,"action":"Craft a Strength/Dexterity/Accuracy blocker and Exalted Orb for one of the Level 20 critical-support suffixes.","repeat_until":"one critical-support suffix","on_fail":"Repeat if recoverable.","probability":0.025,"probability_source":"Author estimates around 1 in 40."},
    {"n":8,"action":"Use Hinekora's Locks to preview Exalted slams until the other critical-support suffix is obtained.","repeat_until":"other critical-support suffix","on_fail":"Consume preview by changing item and retry lock.","probability":null,"probability_source":""},
    {"n":9,"action":"Apply the historical Runesmith Vaal soul reduction enchant.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":10,"action":"Finish item.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "The expensive prefix package is completed and divined before any suffix fishing; Prefixes Cannot Be Changed then turns later Harvest attempts into suffix-only work.",
  "mechanics": ["essence","bench","metamod","harvest","recombinator","divine"],
  "stated_cost": {"amount":null,"currency":"Author warns later suffix stage may exceed a Mirror","date":"2024"},
  "source": {"url":"https://www.reddit.com/r/PathOfExileBuilds/comments/1ft4402","author":"Reddit poster","date":"2024-09-30","type":"reddit"},
  "confidence": "medium"
}
```

A Divine Orb respects prefix/suffix metamods, which is why “finish one side, lock it, Divine the other side” is a valid general technique; Craft of Exile explicitly documents this interaction. citeturn549779reddit0turn474476search3

```json
{
  "id": "R30",
  "title": "Pohx advanced RF boots with forced veiled prefix and Conflict implicit",
  "patch": "modern",
  "still_valid": "yes",
  "validity_note": "The guide is current and uses modern Wild Bristle Matron, Veiled Chaos, Eldritch Annul and Orb of Conflict.",
  "item": {"class": "Boots", "base": "Rare Boots", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["preferred Movement Speed unveil", "final crafted prefix"],
    "suffixes": ["three completed suffixes"],
    "implicits": ["desired Eldritch implicits including improved maximum Fire Resistance"],
    "other": []
  },
  "steps": [
    {"n":1,"action":"With full suffixes and an open prefix, use Wild Bristle Matron to force “Suffixes Cannot Be Changed”.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":2,"action":"Use a Veiled Chaos Orb to add a veiled prefix; if all prefixes fill, use an Eldritch Annul on the random prefix.","repeat_until":"usable veiled prefix with open craft slot","on_fail":"If the veiled prefix is annulled, return to step 1.","probability":null,"probability_source":""},
    {"n":3,"action":"Craft Evasion Rating while Focused as an unveil block, then unveil the preferred Movement Speed modifier.","repeat_until":"preferred Movement Speed unveil","on_fail":"Repeat steps 1-3.","probability":null,"probability_source":""},
    {"n":4,"action":"Craft the final modifier.","repeat_until":null,"on_fail":null,"probability":null,"probability_source":""},
    {"n":5,"action":"Use Ichors and Embers for desired implicits; use Grand/Exceptional currency and Orb of Conflict to improve maximum Fire Resistance to +2.","repeat_until":"desired implicit tiers","on_fail":null,"probability":null,"probability_source":""}
  ],
  "author_reasoning": "Full suffixes force Wild Bristle Matron to add the suffix-lock prefix, after which a veiled prefix can be repeatedly targeted without rerolling the suffix package.",
  "mechanics": ["bench","metamod","eldritch","veiled","beast"],
  "stated_cost": {"amount":null,"currency":"","date":"current"},
  "source": {"url":"https://pohx.net/crafts/advanced-endgame-boots/","author":"Pohx","date":"","type":"guide"},
  "confidence": "high"
}
```

Pohx explicitly recommends Grand/Exceptional Eldritch currency plus Orb of Conflict for the high-tier maximum-Fire-Resistance implicit. citeturn474476search0 Orb-of-Conflict users likewise document that the opposite implicit should generally be kept at Exceptional or higher while pushing the desired side upward. citeturn474476reddit9

## Additional benchmark-worthy source occurrences

Several text sources contain useful variants that I did not promote to separate IDs only to keep the set at 30 rather than inflate it with near-duplicates. They are particularly useful when you later want to expand toward 40–50 routes.

The first is the 2026 strength-stacking Talisman route: Awakener Orb `% Attributes` and `% Strength` onto a Talisman, use repeated Talisman imprints plus annuls to isolate suffixes, `Suffixes Cannot Be Changed` plus `Reforge Attributes`, Genteel's Ducat to transform the attribute result, Wild Bristle Matron + Scour to clean prefixes, then repeated imprint → double Exalt → Reforge Influence loops for damage per Strength. It is one of the richest current examples of checkpoint-style beast crafting. citeturn348209view2

A second useful variant is the 2026 Faceted-fossil staff: `Faceted + Aetheric + Opulent` to obtain `+1 Intelligence` and `+1 Strength` gem modifiers, multimod to fill suffixes, `Suffixes Cannot Be Changed` + Veiled Chaos until Minion Life, replace multimod with `Cannot roll Attack Modifiers`, Exalted Orb for guaranteed socketed-gem level, then craft `+2 to Level of Socketed Support Gems`. citeturn775195reddit0

A third is the old four-fossil +2 minion-wand route: `Corroded + Metallic + Jagged + Shuddering` was reported to leave only the two +1 gem prefixes plus the minion/spell-damage family; one documented crafter then used `Prefixes Cannot Be Changed`, Scour and Multimod to finish. citeturn509945reddit10turn509945reddit11 This is valuable as a historical control because later guides use nearly the same fossil principle but a different finishing sequence.

## Richest sources to revisit after patches

The **Butsicles recombinator guide** is the strongest single source for post-3.25 Unpredictable Recombination mechanics: it explains exclusive modifiers, base selection, affix-count probabilities and feeder construction, and was based on hundreds of experiments. citeturn348209view1 The associated **Necrotic Armour guide by Sheeepishly** is the best worked example of those rules translated into an actual five-natural-mod item with explicit feeder stages, approximate probabilities and a stated completed cost. citeturn348209view0

**PoE Vault’s current build/crafting guides** were the richest source of reproducible beginner-to-midrange routes, especially because the 3.29 Shrapnel Ballista guide gives an unusually explicit fracture → essence → tag-block → forced-Exalt sequence and several simpler trade/fracture crafts in the same article. citeturn758902search0 Its dedicated minion-wand guide is similarly valuable because it states the fossil combination, rough iteration counts, suffix cleanup, Veiled Chaos branch and cheap bench alternative. citeturn524167search3

For **RF and Eldritch crafting**, Pohx’s craft pages are unusually maintainable patch-to-patch and give actual ordered recipes rather than generic mechanic explanations. citeturn474476search0 Reddit’s Rule-10 craft posts remain the richest source for expensive “what actually happened” routes, because authors often disclose recovery branches, failed attempts, approximate odds and costs—for example the dual-influence RF helmet’s ~70 Horror essences, ~16% Fire reforge and ~15% Concentrated Effect reforge figures. citeturn509945reddit7

For **mechanic-validity checks**, PoE Wiki and the official/current patch notes should remain the authority layer rather than the route layer. In particular, the 3.29 changes invalidate old Bestiary split workflows, while current Recombinator documentation distinguishes Predictable and Unpredictable modes and current Veiled currency documentation distinguishes Veiled Chaos from Veiled Exalted Orbs. citeturn229489search0turn896539search5turn896539search2turn896539search3