# Deep research 2 of 5: compressing the item state of a crafting MDP, with measured error

## Context (read first)

We are building a crafting route planner for **Path of Exile 1**. Given a target item (base, item level,
influence, a set of desired explicit modifiers with minimum tiers), it returns the cheapest crafting route as a
policy over a Markov decision process / stochastic shortest path problem. State = the current item; action = one
crafting operation with a price; transition = the distribution of resulting items; goal = the target is satisfied.
The solver computes the expected remaining cost of every state (value iteration). Routes are not enumerated as
chains. Language: Python with numpy / numba, one 12-core desktop, target runtime seconds to minutes per item. Game
data (mod pools, weights, tiers, groups, tags) comes from Path of Building's export for patch 3.29.

### The concrete model (exact, but too large)

- An item has up to 3 prefixes and 3 suffixes (rare), up to 1 + 1 (magic). Each explicit mod has an id, a tier,
  an exclusion group, tags, a spawn weight that depends on the base's tags, and a rolled value inside its tier's range.
- Adding a random mod (Exalted Orb, Regal Orb, Orb of Augmentation, the fill-up part of Chaos / Alchemy / Essence)
  is a weighted draw from the eligible pool: mods whose group is already on the item are removed, the full side is
  removed, and mods blocked by metamods ("Cannot roll Attack Modifiers", "Cannot roll Caster Modifiers") are removed
  by tag. Fossils multiply weights by tag. Harvest reforges force at least one mod with a given tag. Essences force
  one specific mod. Rerolls (Chaos, Alchemy) draw several mods in sequence without replacement.
- "Prefixes Cannot Be Changed" / "Suffixes Cannot Be Changed" protect one side from rerolls and removal.
  A fractured mod can never be removed or changed. A Divine Orb rerolls values inside tiers (respecting locks).
  Orb of Annulment removes a uniformly random removable mod.
- Size: per base, 10^8–10^11 distinct concrete mod sets (by tier), before flags and rolled values. A solver that
  kept concrete states hit a 100,000-state limit before it finished listing the outcomes of a single Orb of Alchemy
  (99,999 distinct outcomes).

### The compressed idea (small, but approximate)

For a target of k ≤ 6 mods, the future mostly depends on:

- which target mods are present, at what tier, and whether their roll is good enough;
- how many non-target ("junk") mods sit on each side;
- flags: rarity, which mod is fractured, crafted mod present, metamods present, influence, Eldritch dominance side.

That is ~10^4–10^6 states. **Where it is approximate:** the identity of a junk mod matters for the future.

- It blocks its own group from being rolled again.
- Its tags decide whether a Harvest reforge, a fossil or a metamod treats it differently.
- It changes what an Orb of Annulment can remove.

A real example from our own data: on a two-hand bow, blocking `attack` mods leaves exactly one prefix group out of
ten. A plain junk count cannot express that; junk split by "has the attack tag / does not" can.

## Rules for this research

Cite every claim (paper, book chapter, code). Explain each method in plain terms first, then formally. Say clearly
when a result is a guarantee and when it is a heuristic. If you cannot find something, say so. Output: Markdown in
English.

## Questions

### 1. Theory of state aggregation and abstraction

For each method below give: the definition in plain words; what guarantee it gives on the optimal cost or policy;
how to compute it; its computational cost; and pitfalls.

- exact and approximate lumpability of Markov chains (Kemeny–Snell; strong and weak lumpability);
- bisimulation for MDPs and bisimulation metrics (Givan–Dean–Greig 2003; Ferns–Panangaden–Precup);
- the abstraction hierarchy of Li–Walsh–Littman 2006 (model-irrelevance, Q*-irrelevance, a*-irrelevance);
- error bounds for value iteration with state aggregation (Van Roy 2006; Bertsekas & Tsitsiklis; Bertsekas'
  aggregation chapters);
- anything newer that is relevant.

### 2. Deriving the abstraction automatically from the concrete simulator

We can compute the exact transition distribution of any concrete state under any action. Which methods derive the
coarsest abstraction that keeps the optimal values exact, or within a stated error?

- partition refinement (bisimulation minimisation, Paige–Tarjan-style);
- feature / relevance selection;
- symmetry reduction: interchangeable junk mods as orbits of a permutation group;
- on-the-fly abstraction over reachable states only.

What do they cost at our scale? Which can run lazily without first building the concrete state space, which is too
large to build at all?

### 3. Concrete designs for this problem

Propose 2–3 compressed state designs and analyse each one. Starting points (improve them if you can):

- **(A)** target mods present / tier / roll-good-enough + junk count per side + flags;
- **(B)** A, with junk split into classes by the tags that interact with the available actions: attack / caster /
  other for metamods, the Harvest reforge tag categories, the fossil tags in use;
- **(C)** A, plus the set of exclusion groups currently blocked by junk.

For each design give:

- the state count for a 6-mod target (3 prefixes + 3 suffixes);
- which mechanics it represents exactly and which approximately;
- how to compute abstract transition probabilities from the concrete weights. Options: averaging over the
  conditional distribution of junk identities; multivariate Wallenius' noncentral hypergeometric distribution for
  weighted sampling without replacement; caching by a "pool signature" (open sides + blocked groups + tag filters).

### 4. Measuring what compression loses

A step-by-step procedure to estimate the error of a given abstraction.

- Evaluate the abstract policy on the concrete model by simulation, with sample-size guidance for rare events
  (e.g. a 0.1% step).
- Compute upper and lower bounds on the true optimal cost.
- Find the states where the error concentrates.
- Refine there: adaptive / progressive abstraction, counterexample-guided abstraction refinement (CEGAR).

How do people report the result so a human can trust it?

### 5. Pitfalls

Known failure modes of aggregation in practice: hidden history dependence, non-Markovian aggregates, policies that
are optimal for the abstraction but bad for the concrete model, numerical issues. How each is detected.

## What to deliver

1. A plain-language summary of each method from questions 1–2 (5–10 lines each).
2. A comparison table: method / guarantee / cost / works lazily (yes/no) / fits our problem (yes/no/partly, why).
3. The analysis of designs A, B, C (and any better one you propose), including the state counts.
4. Our recommended design with pseudo-code: the state type, the abstract transition function built from the
   concrete one, and the refinement loop.
5. The error-measurement procedure from question 4 as numbered steps.
6. A reference list.
