# Deep research 1 of 5: prior art and game data sources for a Path of Exile crafting route planner

## Context (read first)

We are building a crafting route planner for **Path of Exile 1** (not PoE 2).

**Input:** a target item: base type, item level, influence(s) if any, and a set of desired explicit modifiers,
each with a minimum tier or a minimum rolled value; optionally implicits.

**Output:** the cheapest crafting route, or the most likely one within a budget. It is expressed as a *policy*:
which action to take in every item state the route can reach ("spam X until Y, then lock prefixes, then slam;
if you miss, go back to step 3"). Every step carries exact probabilities and the expected and 90th-percentile cost.

How we model it:

- **A Markov decision process / stochastic shortest path problem.** State = a description of the current item.
  Action = one crafting operation with a price. Transition = the probability distribution of resulting items.
  Goal = any item that satisfies the target. The solver computes the expected remaining cost of every state and
  picks the best action per state (Bellman equation / value iteration). Routes are not enumerated as chains.
- **Data.** Mod pools, spawn weights, tiers, groups and tags come from Path of Building's exported game data
  (PoB v2.67.2, game patch 3.29; check whether a later patch changed crafting). Crafting rules come from
  primary sources: GGG patch notes, poewiki, datamined data. Craft of Exile is used only as an independent oracle
  to cross-check single-action probabilities; its code is never copied.
- **Actions in scope:**
  - currency: Orb of Transmutation, Orb of Alteration, Orb of Augmentation, Regal Orb, Orb of Alchemy, Chaos Orb,
    Exalted Orb, Orb of Annulment, Orb of Scouring, Divine Orb;
  - Essences, Fossils + Resonators, Harvest reforges;
  - crafting bench crafts, including the metamods "Prefixes Cannot Be Changed", "Suffixes Cannot Be Changed",
    "Can have up to 3 Crafted Modifiers", "Cannot roll Attack Modifiers", "Cannot roll Caster Modifiers";
  - Fracturing Orb;
  - Eldritch currency: Embers, Ichors, Eldritch Exalted / Chaos / Annulment, Orb of Conflict;
  - influence Exalted Orbs, Awakener's Orb;
  - Veiled Chaos Orb + unveiling;
  - beastcrafting;
  - Recombinators;
  - buying an intermediate item from trade.
- **Scale.** A concrete item state (exact mod ids and tiers) gives 10^8–10^11 possible items per base. A naive
  solver that kept concrete states hit a 100,000-state limit before finishing the outcome list of a single Orb of
  Alchemy. A compressed state — which target mods are present and at what tier, how many non-target "junk" mods per
  side, flags such as fractured / crafted / metamods / influence / Eldritch dominance — is ~10^4–10^6 states.
  Time budget: seconds to minutes per target item on a 12-core desktop, Python with numpy / numba.
- **Facts policy.** Only verified mechanics enter the model. Unverified numbers are flagged, never guessed.

## Rules for this research

- Cite every claim with a link. Tag each claim with its kind: `official` (GGG), `datamined`, `documented` (wiki),
  `player-experiment`, `tool-implementation`, `speculation`.
- Prefer primary sources and source code over blog summaries. Give the patch and the date of every crafting fact.
- If something cannot be found, say so explicitly. Do not fill gaps from memory or invent numbers.
- Output: Markdown, in English, with the tables asked for below.

## Questions

### 1. Open-source PoE crafting software

Find every project you can (GitHub, GitLab, Codeberg, npm, PyPI, forum posts, Discord bots with public code) that
simulates, calculates or optimises PoE crafting: single-action probability calculators, Monte-Carlo simulators,
"cost per success" estimators, and above all anything that *searches over multi-step routes* or computes an
optimal policy. Include PoE 2 tools, since their methods may transfer.

For each project report: URL; licence; language; last commit date; game (PoE 1 / PoE 2) and patch; which
mechanics it supports; method (closed form, exhaustive enumeration, simulation, dynamic programming / MDP,
heuristic search); whether it *plans* routes or only *evaluates* a route the user gives; its data source; known bugs
or inaccuracies reported by users; what we could reuse or learn from it.

### 2. Craft of Exile in depth

- How its emulator and its calculator work. It runs client-side JavaScript with data files; internal functions
  have names like `poec_computeFinalProbsV2`, `poec_computePermutationsV2`, `poec_simRecombinate`; there is a
  "methods" tree and a "cost per success" figure.
- What data it uses, where that data comes from, and how it is updated after a patch.
- Known disagreements between Craft of Exile and the live game, for example: the rare affix-count weights for
  Chaos / Alchemy, fossil weight stacking, the Recombinator algorithm, Harvest tag blocking.
- Whether the author published documentation, changelogs or explanations of the maths.
- Its terms of use or licence regarding reuse of data or code.
- Whether it has any route search or optimisation at all, or only evaluates a given method.

### 3. Non-PoE prior art with the same mathematical shape

The shape is: random upgrades with resource costs, retries, locks and stop conditions; choose the best policy.
Candidates: MapleStory Star Force and cubing calculators; Lost Ark ability-stone faceting optimisers; Last Epoch
forging; Diablo 4 tempering / masterworking; gacha pity calculators; Persona / Shin Megami Tensei / Monster Hunter
fusion calculators; any other you find.

Look specifically for tools and write-ups that solve the **optimal policy** with dynamic programming / MDP rather
than evaluating one fixed strategy. For each report: state representation, solver, state count, runtime, and the
lessons that transfer to PoE.

### 4. Write-ups on crafting as an MDP

Papers, theses, conference talks or blog posts with real maths that treat item crafting or upgrading as an MDP,
an optimal stopping problem, or stochastic shortest path. Summarise the model and the results of each.

### 5. Game data sources for mod generation

Cover: the PoB data export (`ModItem.lua`, `ModExplicit.lua`, base files), RePoE, PyPoE, poedb, and the poewiki
Cargo tables. For each, say which fields exist for: spawn weights per tag; generation weight multipliers
(e.g. `generation_weights`); tags that a mod *adds* to an item (e.g. `adds_tags`, `implicit_tags`); exclusion
groups / mod families; and the essence, fossil, Harvest and bench tables.

Then answer these precisely, with sources:

- **(a)** Does a tag added by one mod change the spawn weights of later draws on the same item? Which data field
  encodes that?
- **(b)** How exactly do "Cannot roll Attack Modifiers" and "Cannot roll Caster Modifiers" decide which mods are
  blocked? By the mod's own tags, by added tags, or by something else?
- **(c)** Do PoB's single `group` values match the game's exclusion rules, or can a mod belong to several families
  that block each other?
- **(d)** When a Chaos Orb or an Orb of Alchemy makes a rare, is the "4 / 5 / 6 mods with weights 8 / 3 / 1"
  distribution verified anywhere primary? What is the source of those numbers?
- **(e)** When several fossils change the weight of the same tag, do the multipliers add or multiply? Give the
  primary evidence.

## What to deliver

1. A table of PoE crafting tools with the columns from question 1.
2. A deep dive on Craft of Exile (question 2).
3. A table of non-PoE analogues (question 3) and a short summary of the write-ups (question 4).
4. A table of data sources × fields (question 5), followed by the answers to (a)–(e), each with its sources and
   claim kind.
5. A ranked list: the top 5 things we should reuse, or whose design we should copy, with one paragraph each on why.
