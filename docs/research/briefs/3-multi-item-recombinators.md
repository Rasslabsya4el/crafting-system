# Deep research 3 of 5: planning crafts where one action consumes two items (Path of Exile Recombinators)

## Context (read first)

We are building a crafting route planner for **Path of Exile 1**. Given a target item (base, item level,
influence, a set of desired explicit modifiers with minimum tiers), it returns the cheapest crafting route as a
policy over a Markov decision process / stochastic shortest path problem. State = the current item; action = one
crafting operation with a price; transition = the distribution of resulting items; goal = the target is satisfied.
The solver computes the expected remaining cost of every state (value iteration). Python with numpy / numba, one
12-core desktop, target runtime seconds to minutes per item.

Most actions take one item and return one item. **Recombinators take two items and return one**, so a route
becomes a *tree* of items rather than a chain.

A real expert route (from a crafting quiz), for a body armour:

1. Get a rare Grasping Mail with Global Defences and a mana prefix.
2. Get an evasion body with mana and % Evasion Rating.
3. Recombine to get an evasion chest with Global Defences + % Evasion.
4. Split to isolate Global Defences.
5. Get an Energy Shield body with flat Armour (Dread essence).
6. Recombine (50/50 to get Global Defences on the ES body).
7. Fill the suffixes with Eldritch currency.
8. Fracture (back to step 5 if you miss).

Note the helper mods (mana, % Evasion): they never reach the final item; they exist only to make an intermediate
recombination work.

### What we know about Recombinators (with uncertainty)

- Two magic or rare items of the same item class are consumed; one item is produced.
- The output base is one of the two input bases, about 50/50 (player experiments, patch 3.25).
- The output item level follows a stated formula (wiki).
- Per side, the mods of both inputs form a pool. The number of mods kept is drawn from a table that depends on the
  pool size. Player measurements, rounded (3.25):

  | mods in pool | keep 1 | keep 2 | keep 3 |
  |---|---|---|---|
  | 2 | 67% | 33% | — |
  | 4 | 11% | 59% | 31% |
  | 6 | — | 28% | 72% |

  Craft of Exile's table differs: pool 4 → keep 3 = 35%, pool 6 → keep 3 = 70%.
- Exclusive mods count at most once per side (3.26 change); NNN mods (non-native natural mods) have special rules.
- **Which mods are kept** is not established. We will assume a uniform choice among eligible pooled mods, and label
  every route that relies on that assumption.
- Since 3.26 there is also a *selected-mod* mode: the player picks mods, a success chance is displayed, and on
  failure the item is destroyed and both inputs are lost.
- A failed outcome (e.g. AB instead of ABC) is itself a usable input for another recombination ("recycling").
- Other two-input or splitting actions may exist (beastcraft split; check whether it is valid in 3.29). Buying an
  intermediate item from trade at a market price is always an option.

### Scale

A rough count of possible donor item classes (subset of target mods + subset of helper mods + junk count per side,
per base):

| case | donor classes | donor pairs |
|---|---|---|
| 3 T1 prefixes, suffixes = junk, 1 base | 80 | 3,240 |
| 3 prefixes + 3 suffixes, 1 base | 400 | 80,200 |
| + 5 helper mods per side | 19,600 | ~1.9×10^8 |
| + 4 bases | 78,400 | ~3×10^9 |

Every pair also has its own outcome distribution: up to 2^6 outcomes per side.

## Rules for this research

Cite every claim. Explain algorithms in plain terms first, then formally, with complexity. State guarantees
precisely: optimal / bounded error / heuristic. If something cannot be found, say so. Output: Markdown in English.

## Questions

### 1. Algorithms for "two inputs, one random output" planning

For each method explain: how it works; its guarantees; its complexity; whether it handles **cycles** (failed
outputs feeding back as inputs) and **stochastic** outcomes.

- AND/OR graph search: AO*, and LAO* for cyclic graphs;
- Knuth's 1977 generalisation of Dijkstra's algorithm (superior functions / the grammar problem);
- shortest hyperpaths in directed hypergraphs (Gallo, Longo, Pallottino, Nguyen 1993) and their stochastic variants;
- dynamic programming over subsets (Held–Karp-style) with pruning;
- probabilistic planning with resource-producing actions: factored MDPs, recipe / crafting planners.

### 2. Combining with the single-item MDP

How to combine the tree layer with the single-item MDP into one fixed point.

- Define V(S) = the expected cost to obtain an item of class S, where S is a base + a mod set.
- A recombination edge then costs V(A) + V(B) + price, plus the outcome distribution over classes.
- Single-item crafting edges stay as they are.

Questions: does an iteration of this system converge, and how fast? How should we handle "both inputs are consumed
on failure"? And the selected-mod mode with item destruction?

### 3. Pruning at scale

The donor space can reach ~78,000 classes and ~3×10^9 pairs. Which pruning methods keep optimality or bounded
error?

- dominance: never use a donor that is costlier and strictly worse;
- admissible lower bounds: A*-style;
- only pairs whose pooled mods advance the target;
- lazy generation of classes;
- choosing helper mods automatically from data (cheap to obtain, and changing the recombination odds);
- beam search as a fallback, with its error.

Give expected pair counts after pruning where the literature allows.

### 4. Prior art in games

How existing tools search fusion / recipe spaces: Persona / Shin Megami Tensei fusion calculators, Monster Hunter
decoration or melding, Minecraft / Factorio recipe planners, PoE Recombinator calculators and spreadsheets (PoE 1
and PoE 2), any crafting-tree optimiser. Report what they optimise, how, and at what scale.

### 5. Risk and reporting

How to report a tree route to a human. Expected total cost, p90, the number of intermediate items needed and their
own costs, the failure branches. How the literature computes the distribution of total cost for AND/OR policies.

## What to deliver

1. An algorithm comparison table: method / optimal or not / handles cycles / handles stochastic outcomes /
   complexity / fit for us.
2. The recommended approach with pseudo-code, integrated with a single-item value-iteration solver.
3. A complexity estimate at our scale (the four rows of the scale table), before and after pruning.
4. A prior-art summary (question 4).
5. A reference list.
