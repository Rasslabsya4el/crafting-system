# Deep research 5 of 5: a benchmark set of real Path of Exile 1 crafting routes

## Context (read first)

We are building a crafting route planner for **Path of Exile 1** (not PoE 2). Given a target item (base, item
level, influence, desired explicit mods with minimum tiers), it computes the cheapest crafting route by itself, as
an optimal policy over the game's real mod weights. To test it we need a **benchmark set of real routes** that
experienced crafters consider good or optimal. The planner will get each route's target item and must find the
same route or a cheaper one by its own calculation. If it finds a different route, we compare both in the same model.

The person running this project knows only simple one- or two-step crafts. So this research must collect the
routes, from simple to very complex, with enough detail to reproduce them.

Our data is from Path of Building v2.67.2, game patch 3.29. Routes from older patches are welcome, but each must be
marked with its patch and whether it still works in 3.29 (or the current patch, if newer).

## What to collect

Collect **30–50 routes**.

- **Coverage:** at least 2 routes per category below.
- **Difficulty spread:** about a quarter each:
  - 1–2 steps (e.g. essence spam + bench craft);
  - 3–5 steps;
  - 6–10+ steps;
  - multi-item (Recombinators or other two-input actions).

Categories:

1. Essence spam + crafting bench finish.
2. Orb of Alteration / Orb of Augmentation / Regal Orb (magic → rare) routes.
3. Fossil + Resonator routes.
4. Harvest reforge (tagged) routes, including under "Prefixes Cannot Be Changed" / "Suffixes Cannot Be Changed".
5. **Tag-block slams**: crafting "Cannot roll Attack Modifiers" and / or "Cannot roll Caster Modifiers" (often
   with "Can have up to 3 Crafted Modifiers") so that an Exalted Orb can only hit the wanted mod. Example the
   project owner remembers: on a bow, after the right mods, multimod + "Cannot roll Caster Modifiers" +
   "Cannot roll Attack Modifiers", then an Exalted Orb guaranteed the +levels prefix.
6. Multimod bench finishing.
7. Fracturing-based routes: buy or make a base with a key mod, then fracture it.
8. Eldritch currency: Embers / Ichors for implicits; Eldritch Exalted / Chaos / Annulment with Exarch / Eater
   dominance; Orb of Conflict.
9. Influence Exalted Orbs and Awakener's Orb.
10. Veiled Chaos Orb + unveiling, including blocking a prefix or suffix to steer the unveil options.
11. Beastcrafting: locks, imprints, split (if valid), prefix / suffix swaps.
12. Recombinator routes: triple T1 prefixes or suffixes; moving mods to a better base; isolating a mod;
    recycling failed outputs.
13. Divine Orb in the middle of a route under a lock (divine only one side, then finish the other).
14. Routes that start by buying an intermediate item from trade.

## Where to look

- **Crafting quizzes with "optimal route" answers.** The three examples below come from a streamer crafting quiz:
  the slides are labelled "SKRYAH", the item tooltips say "Crafting Project". Find that series and collect *all*
  its questions and answers.
- Craft of Exile community crafts and its crafting methods pages.
- poewiki Crafting pages and per-mechanic pages.
- Reddit r/pathofexile and r/PathOfExileBuilds crafting guides and "how was this crafted" threads.
- The official PoE forum crafting section.
- Maxroll and poe-vault crafting guides.
- YouTube crafting guides and crafting streams.
- Anywhere else with documented step-by-step routes and stated odds or costs.

## Rules

- Do not invent routes, steps, probabilities or costs. If a source gives no probability, leave it `null`.
- Transcribe step text in English, as close to the source as possible. Game terms exactly as the game writes them.
- One route per source occurrence. If two sources disagree on the same craft, keep both and note the difference.
- For each route, record the author's one-line reason why this order is good, if given.
- Mark legacy routes: patch, and whether the route still works now, with the reason (mechanic removed or changed, etc.).

## Output format

First a summary table: id / item / categories / steps count / patch / still valid / source type / confidence.

Then one fenced JSON block per route:

```json
{
  "id": "R01",
  "title": "short name",
  "patch": "3.xx",
  "still_valid": "yes | no | unknown",
  "validity_note": "",
  "item": {"class": "", "base": "", "item_level": null, "influence": []},
  "target": {
    "prefixes": ["exact mod text"],
    "suffixes": ["exact mod text"],
    "implicits": [],
    "other": []
  },
  "steps": [
    {
      "n": 1,
      "action": "exact step text",
      "repeat_until": null,
      "on_fail": null,
      "probability": null,
      "probability_source": ""
    }
  ],
  "author_reasoning": "",
  "mechanics": ["essence", "bench", "metamod", "harvest", "fossil", "fracture", "eldritch", "influence",
                "awakener", "veiled", "beast", "recombinator", "divine", "trade"],
  "stated_cost": {"amount": null, "currency": "", "date": ""},
  "source": {"url": "", "author": "", "date": "", "type": "quiz | guide | video | forum | reddit | tool"},
  "confidence": "high | medium | low"
}
```

## Three examples of the expected detail

These are transcribed from the quiz slides, so use them as the format reference. The quiz answers are the step lists.

### Example 1: Energy Shield body armour

**Final item, explicits:**
- fractured prefix: 50% increased Global Defences;
- prefix: +97 to maximum Energy Shield (T1);
- crafted prefix: 74% increased Energy Shield;
- suffix: +1 to Level of Socketed Intelligence Gems (T1);
- suffix: +35% to Cold Resistance;
- suffix: +23% to Fire Resistance.

**Implicits:** a Searing Exarch implicit and an Eater of Worlds implicit.

**Route:**
1. Get rare Grasping Mail with global def and mana prefix.
2. Get evasion body with mana and %evasion rating.
3. Recomb to get evasion chest with global def + % evasion.
4. Split to isolate global def.
5. Get ES body with flat armour (Dread essence).
6. Recomb (50/50 to get global def on ES body).
7. Fill suffixes with eldritch currency.
8. Fracture (back to step 5 if you miss).

### Example 2: Archdemon Crown, item level 100

**Final item, explicits:**
- veiled prefix: 8% increased Area of Effect, +2 to Level of Socketed AoE Gems;
- essence suffix: Socketed Gems deal 30% more Elemental Damage;
- Shaper suffix: Socketed Gems are Supported by Level 20 Hypothermia, 17% increased Effect of Cold Ailments;
- Shaper suffix: Socketed Spells have +3% to Critical Strike Chance;
- crafted prefix: +45 to maximum Energy Shield.

**Route:**
1. Shaper Exalted Orb.
2. Spam Essence of Horror until Hypothermia suffix.
3. Lock suffix, Harvest reforge crit.
4. Lock suffix, Veiled Chaos.
5. Block a prefix (Zombies).
6. Unveil +2 AoE (~45% chance).
7. Craft prefix (flat ES).

### Example 3: Velour Boots, item level 100

**Final item, explicits:**
- veiled prefix: 30% increased Movement Speed, 10% increased Movement Speed if you haven't been Hit Recently;
- essence suffix: 60% chance to Avoid being Shocked;
- suffix: +13% chance to Suppress Spell Damage (T1);
- suffix: +43% to Fire Resistance (T2);
- crafted prefix: +67 to maximum Life.

**Implicit:** a Searing Exarch implicit, 40% chance to Avoid being Shocked.

**Route:**
1. Get suppression fracture boot.
2. Spam Avoid Shock essence (Torment) until you hit fire resist.
3. Lock suffixes (Wild Bristle Matron).
4. Veiled Chaos.
5. Block prefix (ex. craft life).
6. Unveil move speed.
7. Craft life.
8. Spam Grand Embers for avoid shock.

## What to deliver

1. The summary table.
2. The JSON blocks, one per route, including the three examples above, completed with any details the original
   source adds (stated odds, cost, date, link).
3. A short list of the sources that were richest in routes, so we can return to them after each patch.
