# Brief: a crafting oracle for Path of Exile 1 (prototype)

Written 2026-09-20 by the lead of the parent project for the agent that builds the prototype. Read `AGENTS.md` first (the
rules of work), then this file, then `docs/background/2026-09-20-crafting-oracle-brainstorm.md`. If you have a subagent /
task tool, you are the LEAD and delegate code to workers exactly as `AGENTS.md` section 6 says.

## 1. Why this exists

The parent project builds Path of Exile characters by search, with Path of Building as the numeric judge. Its gear is limited
by typed "rails" (best of 200 random rolls, fixed tier positions) because nothing in it knows what an item COSTS TO GET. In
the game that cost is decided by crafting PATHS, not by mod weights alone: two rings with equal tiers and equal weights can
differ a thousandfold in difficulty, because one has a short road (an essence, a harvest reforge, a blocking bench craft
before an Exalted Orb, "cannot roll attack modifiers") and the other does not. The owner's goal: a system as proficient in
crafting as the parent is in Path of Building -- given an item, find HOW to craft it, from a white base to the finished item,
what it costs on average, and the best few ways. Later the two systems talk: the build asks only for gear that is certainly
craftable within a budget, and crafting methods and budgets are locked behind LOADOUTS (day 1: bench, essences, basic
currency; later: fossils, harvest, eldritch currency; endgame: fracturing, recombinators, double influence).

The final interface (NOT all of it in the prototype): `cost(item_spec, loadout) -> ranked strategies`, each with its steps,
expected cost, spread and success probability per attempt.

Example of an item spec the owner gave: helmet, item level 86, quality 20; prefixes: life T1; suffixes: chaos resistance T1,
one elemental resistance T1. The answer he wants: the five best ways to make it, start to finish.

## 2. What the thing is, mathematically (keep this picture; it decides the design)

Crafting is solitaire with known odds. State = the item (base, item level, influence / eldritch dominance, fractured mods,
explicit mods with tiers, crafted mod, quality, corrupted...). Action = a currency or bench operation with a price; it maps a
state to a probability distribution over states. The probabilities come from DATA (which mods can spawn on this base at this
item level, their spawn weights, mod groups that exclude each other, prefix / suffix limits) modified by the action's RULE
(a fossil multiplies weights by tag; an essence forces one mod; a harvest reforge forces a tag; a metamod protects prefixes
or forbids attack mods; an annulment removes one at random...). A strategy = a policy: which action to take in which state,
when to stop, when to start over. Its value = expected total price to reach the target set of states.

Consequences: (a) single-loop strategies (spam one action until the target appears) have an EXACT expected cost = price /
probability, and the probability is computable from the weights by enumeration -- no simulation needed; (b) multi-step
strategies are evaluated by chaining exact stage probabilities where stages are independent, and by Monte Carlo where they are
not; (c) a general optimal-policy solver is research and is NOT part of the prototype -- the prototype ranks a LIBRARY OF
STRATEGY TEMPLATES, each typed by mechanism, each instantiated for the target item.

## 3. Phases

### Phase 0 -- the knowledge harvest (most of the first days; the owner: "there is a huge amount of useful information there")

Goal: everything about how crafting works, in one place, as fact sheets with sources -- text first, code later.

1. **Craft of Exile** (https://www.craftofexile.com/ , PoE 1). Its computation runs in the visitor's browser: the page loads
   `/packages/package.js` (the application) and data files `/json/data/main/poec_data.json` (keys seen: `bitems, bases,
   bgroups, modifiers, mgroups, mtypes, fossils, catalysts, essences, maeven, aliases, tiers, basemods, modbases, mdefs`),
   `/json/data/affinities/poec_affinities.json`, `/json/data/exdata/poec_exdata.json`, `/json/data/poec_common.json`,
   `/json/data/poec_guides.json`, `/json/data/lang/poec_lang.us.json`. Functions seen in the page: `poec_simRollAffix`,
   `poec_simApplyCraft`, `poec_simRerollItem`, `poec_simRecombinate`, `poec_computeBestFossils`, `poec_simCheckHReroll`,
   `poec_simRollImplicits`, `poec_cmethods`, `poec_constants` ... Cache each file once (`AGENTS.md` 3) and READ:
   - the list of crafting methods it supports and every option of each (this is the action catalogue's first draft);
   - for every method: the rule as implemented (which pool, which weights, which exclusions, how many mods a reroll gives and
     with what distribution, how tiers are picked, what "harvest nerf" toggles, what recombinators do), the constants used;
   - its texts: basics, advanced notes, metamod rules, tooltips, the guides file -- a lot of crafting knowledge sits there as
     prose; extract it into the fact sheets with a pointer to where it was found;
   - how its CALCULATOR computes probabilities (it is the reference for our exact calculators) and how its SIMULATOR lets a
     user chain steps with conditions (it is the reference for our strategy templates).
2. **What Craft of Exile lacks or the owner doubts it has** -- collect from other sources into the same format: Awakener's
   Orb (double influence), eldritch currency (Eldritch Chaos / Exalted / Annulment, ichors and embers, dominance rules),
   fracturing orbs, veiled orb / unveiling, beast crafts (imprint, split, prefix <-> suffix swaps), Maven's orb / elevated
   mods, corruption outcomes (Vaal orb, double corruption), synthesis implicits, catalysts and quality rules, item level and
   mod level gates, influence mod pools, anything the wiki's "Crafting" pages list that the catalogue misses. Sources: PoEDB
   (https://poedb.tw/us/), the community wiki (https://www.poewiki.net/ -- it may refuse automated fetchers; then say so in
   `OPEN_QUESTIONS.md`, the lead can read it through a browser), official patch notes, GGG staff posts.
3. **The data**: mod pools and weights from Path of Building's data files (`sources/pob/Data/`, see `AGENTS.md` 1; format: `ModExplicit.lua`
   rows carry `type` Prefix / Suffix, `level`, `group`, `weightKey` / `weightVal` per base tag, `modTags`); base item tags from
   `Bases/*.lua`; essences from `Essence.lua`; bench crafts from `ModMaster.lua`; veiled, eldritch, corrupted, delve, synthesis
   mods from their files. Write `data/` builders that convert what we need into our own JSON (with the PoB version recorded).
   Cross-check a sample (at least 50 mods over 5 item classes) against Craft of Exile's numbers and PoEDB; every discrepancy
   is a row in `OPEN_QUESTIONS.md`. What PoB does not hold (fossil weight multipliers by tag, harvest weightings, the number-of-
   mods distribution of a Chaos / Alchemy, recombinator rules) comes from the other sources, with confidence labels.

**Fact sheet format** (`docs/mechanics/<action>.md`): what the action does in one paragraph; preconditions (rarity, item
level, influence, corrupted, fractured...); the exact rule as steps; the numbers with their sources and confidence; conditions
and exceptions; interactions with metamods and other actions; what Craft of Exile does differently from the documented rule,
if anything; worked examples with numbers (they become tests); open questions (ids).

Exit of phase 0: an action catalogue (`docs/mechanics/INDEX.md`: action, loadout tier guess, sheet status, confidence), at
least the sheets for: Transmute / Alteration / Augment / Regal / Alchemy / Chaos / Exalted / Annulment / Scouring / Divine,
bench crafts and the metamods (prefixes / suffixes cannot be changed, cannot roll attack / caster modifiers, can have multiple
crafted modifiers), essences, fossils and resonators, harvest reforges and augments as they exist today, eldritch currency,
Awakener's Orb, fracturing, veiled mods, recombinators, corruption. Depth beats breadth: a sheet that is honest about what it
does not know is worth more than a complete-looking guess.

### Phase 1 -- the engine core

- The item model and the mod-pool resolver: for (base, item level, influence, existing mods) -> the legal prefixes and
  suffixes with weights, respecting groups, tags, level gates, prefix / suffix limits.
- Actions as pure functions `apply(action, item, rng) -> item` implementing the fact sheets, one module per rule family.
- **Exact calculators**: the probability that one application of an action yields an item satisfying a target predicate
  (enumeration over the weighted draws; document the algorithm and its complexity; cache by pool signature). Expected cost of
  a spam loop = price / probability; also the distribution's spread (geometric).
- A Monte Carlo harness for anything the exact calculators do not cover; it must agree with them where both apply.
- Known-answer tests: at least 30 cases where the expected probability is known from an independent source (Craft of
  Exile's calculator output read by a human or derived from its formulas, the wiki's worked examples, hand computation on
  tiny synthetic pools). Record each case's source in the test's docstring.

### Phase 2 -- from an item spec to ranked strategies (the prototype's demo)

- The item spec: a small JSON / YAML: base or item class, item level, quality, influence, required mods (group + minimum
  tier, prefix / suffix), optional "any of" sets, how many open affixes may hold junk, whether a crafted (bench) mod may
  satisfy a requirement. Provide the owner's helmet example as `examples/helmet_life_chaos_res.yaml`.
- A price table (`data/prices.example.json`: currency -> price in one unit, e.g. chaos-equivalents) and a LOADOUT file
  (allowed actions + a budget). Prices are inputs, not facts: no trade-site scraping.
- The strategy-template library, each template = a parameterised recipe + how its cost is computed. Start with:
  1. one-action spam (Chaos; Alchemy + Scouring; essence; fossil combination chosen by the calculator; harvest reforge);
  2. Alteration -> Augment -> Regal (-> Exalted / bench) for one- or two-mod cores;
  3. "make one half, protect it, reroll the other": essence or fossil for the prefixes, then "prefixes cannot be changed" +
     a reforge / scour pattern for the suffixes (and the mirror image); finishing with bench craft(s), multimod when it pays;
  4. blocking: a bench craft that occupies a mod group before an Exalted Orb or a harvest augment;
  5. eldritch-currency finishing on a dominant side;
  6. fracture-then-spam (a fractured core + cheap rerolls);
  later (tasks, not the prototype's exit): recombinator ladders, Awakener's Orb merges, veiled-orb finishing.
- The ranker: instantiate every applicable template for the spec, compute expected cost (exact where possible, Monte Carlo
  otherwise, the method stated in the output), discard those outside the loadout, print the top five: steps in order, the
  per-stage success probability, expected number of attempts per stage, expected total cost, a 90% interval, what was
  assumed. The command: `python -m craftoracle plan examples/helmet_life_chaos_res.yaml --loadout data/loadouts/endgame.json`.
- Speed target: a plan for one item in under a minute on 2 processes. If a template cannot be evaluated in that time, say so
  in the output instead of silently skipping it.

### 3b. The contract with the build system (added 2026-09-20 evening; shapes the CORE, not an extra feature)

The build system will not always ask for one exact item. It will hand over a VALUE FUNCTION for a slot -- first as an affix value
table (mod group + tier -> how much it gives THIS build, measured by Path of Building; on weapons local mods multiply, so the
table is only a fast estimate and the exact value of a concrete item is a separate Path of Building call the lead wires later)
-- and wants back a FRONTIER, not one recipe: several policies with their expected value, expected cost, bad-case cost (90th
percentile), steps / decision points, risk of an irreversible failure, rare inputs needed. "Triple T1 flat + attack speed" at
100 units and "essence + two T2 + a crafted attack speed" at 93% of the value for 12 units are both answers; the build system
then splits a loadout's budget across slots. Players stop at "good enough": the stopping rule is part of the policy.

What this means for the prototype NOW: (1) calculators return the DISTRIBUTION of outcomes of a stage (probability per
resulting mod set, or at least per scored class), not only the probability of one exact target; "success" is then a predicate
or a score threshold over that distribution; (2) the item spec accepts either required mods OR a scoring table + a threshold
("stop when score >= X"); (3) the ranker's output already carries expected cost, 90th-percentile cost, steps and decision
points per strategy. The owner's helmet example stays the demo; add a second example with a scoring table
(`examples/bow_value_table.yaml`, numbers invented and marked as such). Terms to use in docs: policy (the sequence of actions
with conditions), outcome distribution, utility / value function, stopping rule, Pareto frontier.

### Not in the prototype

A general optimal-policy solver; trade prices; a user interface; Path of Exile 2; integration with the parent's gear optimizer
(the lead does that later: the contract to keep in mind is `cost(item_spec, loadout)`).

## 4. How the lead will judge the prototype on return (Thursday 2026-09-24 evening)

1. `docs/STATE.md` tells in two minutes what works, with commands that reproduce it.
2. Every number in a fact sheet has a source; `OPEN_QUESTIONS.md` is honest about what is unsourced or contradictory.
3. The exact calculator reproduces the known-answer cases; Monte Carlo agrees with it.
4. `python -m craftoracle plan` on the helmet example prints ranked strategies whose stages a player recognises as real.
5. Nothing outside `crafting/` was touched; nothing third-party was committed.

If time runs short, stop expanding and make what exists correct and documented. An honest phase 0 + a small exact calculator
is a better handover than a wide simulator nobody can trust.
