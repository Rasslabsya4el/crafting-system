# An imprint is a snapshot held in the item state, and a restore is a move to it

ADR-0034 fixed what an imprint does and left the encoding open: how the compressed state holds the snapshots, and how a restore is priced so that the cost of building the snapshot state is not charged twice (ADR-0013 had called it "imprint as acquiring a copy"). [Ticket #218](https://github.com/Rasslabsya4el/crafting-system/issues/218) built a throwaway prototype of both shapes the ticket names and checked them against brute force. The prototype is `tests/imprint_prototype.py` (two layers over any solver model) with `tests/test_imprint_prototype.py` (85 tests, about a second); `research/218/growth.py` counts the states on the real routes.

## Decision

1. **The chosen shape is A: the snapshots are part of the item's state.** A state is `(s, H)`: the compressed state `s` of the item and the set `H` of the compressed states an imprint was made at, at most `max_imprints` of them. A snapshot is the compressed state itself: restoring returns the very item, and two items with one compressed state have one future (ADR-0009), so nothing else about the imprinted item needs keeping.
2. **Imprint and restore are two ordinary actions of the planner, with no input.**
   - `imprint`, offered when the item is imprintable (a magic item; a rare Talisman; not fractured, corrupted or mirrored; ADR-0034) and `s` is not already held. It costs the beast of the price file (Craicic Croaker for magic, Fenumal Plagued Arachnid for a rare Talisman), once, here. Outcome: `(s, H ∪ {s})` for certain. With `max_imprints` held it **replaces** one (one action per held snapshot): the cap bounds the state, not the game, and an old imprint costs nothing to throw away.
   - `restore h` for each `h ∈ H` with `h ≠ s`, offered when the item may be restored (not fractured, corrupted or mirrored). Outcome: `(h, H − {h})` for certain, so the imprint is used up. It costs nothing in the game and a nominal `RESTORE_COST = 1e-6` price units in the solver, which wants positive costs (the same convention as the unveil pick, ADR-0026). The restore is acyclic by itself, because it uses an imprint up and making one costs a beast.
   - Every other action moves `s` and keeps `H`. `H` becomes empty when the new state is not restorable (a Fracturing Orb, a corrupting action, ADR-0036: the held imprints could never be used) and when the action makes a new item (a recombination output, a split item; ADR-0033). An Awakener's Orb (ADR-0032) keeps the receiver's `H`, so a restore undoes it on the receiver; the donor is consumed with its own imprints, and a donor `Need` starts and ends with `H` empty (the imprint layer sits below the acquisition adapter of ADR-0022).
3. **The restore does not charge the cost of building the snapshot state again.** The snapshot is the item itself in an earlier state, so what it cost is the beast that made it, and that is paid when it is made. ADR-0013's reading, a restore that takes a `Need` for a second item in the snapshot state, charges that item's whole acquisition cost on every restore. In the toy loop below this makes the imprint worth nothing (68 with the charge, 68 with no imprint, 12 with this design). **ADR-0013 is amended** (a line there); the imprint is not an input in either shape.
4. **A set, not a multiset.** A second imprint of a state that is already held never helps: after the restore the item is back in that state and can make the imprint again at the same price. The prototype checks it: 24 random graphs, one and two imprints, the layer with sets equals a literal game that keeps a multiset and may throw imprints away (the optimum of the Bellman LP, to 1e-4).
5. **`max_imprints` is a setting of the planner, default 2.** The owner decided that several imprints of one item are allowed (ADR-0034), the gain of the second is small (see "How many imprints"), and each extra one multiplies the state (see "State growth"); the setting lets a route that does not fit the solver drop to 1, which loses at most the figure below.
6. **Imprints are not previewable and the layer refuses the coarse level.** A Peek never offers one (ADR-0055 lists every imprint craft among those applied blind, and using one ends the foresight); the coarse state of ADR-0023 is not offered with imprints until a ticket proves block invariance for them, as for Unveil.

## Why not shape B

Shape B is "imprint then try" as one macro-action: at an imprintable `s`, for each body (a fixed run of base actions) one action that makes the imprint, runs the body and returns to `s` where the end state is not accepted. Its cost is the beast plus the expected cost of the body, so it needs no restore cost, and its state does not grow. It is exact on a loop whose body is one risky action, and then it equals A. It fails where the routes need it:

- **A rare item that is not a Talisman cannot be imprinted again**, so on R15's bow the imprint made while the bow is magic is the only one the rare bow will ever have and can serve every step after the Regal (the guide uses it for the Annulment of step 3; the toy adds the Exalted slam that follows, the use R17 makes of its Talisman imprint). Shape B needs a body as long as that whole run; A needs nothing, because the held snapshot rides in the state and the policy restores at whichever step fails. Measured on the R15 toy below: B costs 63.3 with bodies of one action (no gain over no imprint), 36.7 with two, 29.3 with three, which is A's value; the macro-actions at the magic state number 1, 10, 71 and 440 for bodies of up to one, two, three and four actions of five. The real R14 offer list has 12.
- **Every body needs a rule for what to keep.** A macro must say which end states are accepted and which return to `s`; A leaves it to the values, at every state.
- An imprint left over after a success is lost in B and can serve a later step in A.
- B is a restriction of the game, so it can never beat A: checked on 12 random graphs with random bodies and random accept sets.

## Measured

Toy games in `tests/test_imprint_prototype.py`; prices in units; the imprint priced at 1; values include the nominal restore cost (a few millionths).

| Game | No imprint | A (shape A) | B |
|---|---|---|---|
| **Toy loop**: one risky action (cost 2, one time in four), a failure is undone by building the item again (20) | 68 | 12.000003 | 12 |
| **R15** at toy scale: 20 alterations to the wanted magic mod, Regal, Annulment (half lose it), Exalted slam (three in four succeed) | 63.33 | 29.33 | 29.33 with bodies of three, 36.67 with two, 63.33 with one |
| **R17** at toy scale: three Exalted slams on a rare Talisman, each lost to junk two times in three, a rebuild costs 50 | 1,339 | 18.000006 (6 per slam) | 18 |
| the same with five slams | 12,463 | 30.00001 | 30 |

- **The toy loop against brute force.** All stationary policies of the literal game (one and two imprints, exact fractions) give 12.000003, as do A and B; the closed form `(1 + 2 + 3/4 · ε) / (1/4)`. The imprint pays exactly while its price is below the expected rebuild, `(1 − p) · 20 = 15`: at 14 the value is 64, at 16 it is 68 and the policy never imprints. The policy of A at the loop is imprint, try, restore on failure.
- **R15 and R17 against the LP.** The Bellman LP of the literal game with one to three imprints matches A to 1e-4 on both. The policy of A on R15 holds the magic imprint through the rare states and restores after a failed slam, the loop of the guide.
- **A second imprint can pay, though rarely.** Over 1,500 random games two imprints beat one in two, by 0.019 and 0.0018 (0.08% and 0.03% of the value); three never beat two. The first of them is pinned in the tests.
- **The restore epsilon.** `solve` certifies the toy loop to 3.6e-8 relative with `RESTORE_COST = 1e-6`; the certificate's constant term in the cycle is the epsilon, so the bound grows like value over epsilon: 3.6e-5 at 1e-9, 0.037 at 1e-12. The values are right to three times the epsilon in each case; it is the certificate that loosens. A solver that takes zero-cost edges that cannot close a cycle can set the cost to zero.

## State growth

The held sets of a reachable state are sets of states the item was in when it was imprintable, so they stay small, but each is carried through every state after it. On the toy chain of `n` checkpoints (every checkpoint imprintable, a rare Talisman):

| imprints held at most | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| n = 3 | 6 | 24 | 42 | 48 |
| n = 5 | 10 | 60 | 160 | 260 |

One imprint multiplies the states by `n + 1`, the number of states an imprint can be made at plus one (exactly `2n (n + 1)` against `2n`, checked for n = 2 to 5); the second by 1.75 (n = 3) and 2.7 (n = 5), the third by 1.1 and 1.6. The growth per extra imprint is the number of imprintable states already passed, shared among the imprints (a held set is a set), so it rises with the length of the route and falls with each imprint.

REAL_GRAPHS

## One held imprint is a number

With one imprint held, the value of `(s, {h})` depends on `h` only through the number `V(h, nothing held)`: the game of the base states with one extra option, to give up for that number, has the same value at every state (12 random graphs, to 1e-9). The value is then the minimum over policies of `J(π) + q(π) · w`, concave and piecewise linear in the number `w`, with `q` the chance of using the restore. A solver that walks value functions (the envelope search of [#312](https://github.com/Rasslabsya4el/crafting-system/issues/312)) can carry that number instead of the state and meet no product at all. The design above does not depend on it.

## Independent of how the graph is walked

The layer is a pure successor function over `(s, H)`: it needs the base `actions(s)` of one state at a time, builds the outcomes of one state when asked, keeps no table of the whole graph and reads no component structure. Whole-graph enumeration, packed transitions or an envelope search can all call it. It has **no inputs**, so an imprint loop is an ordinary cyclic component and not a branching one: the answer to the question #179 left to this ticket for R15 and R17 is that there is no branching component, and the (G + 1) × S product of acquisition copies that ADR-0022 foresaw for "an imprint" does not occur. A donor built with imprints is a process of its own whose states carry their own sets (tested: a donor made with imprints costs 12 against 68, and the main item pays it once).

## What follows

- **T9 ([#219](https://github.com/Rasslabsya4el/crafting-system/issues/219))** builds the two kinds from this ADR: the held set in the compressed state when an imprint action is enabled (and only then, as for every part of the item state, ADR-0027), the imprintability and restorability tests, the clearing of the set, the beast prices, the claims, the setting `max_imprints`. Its "two imprints of one item can both be used" is the default of 2.
- **T13 ([#223](https://github.com/Rasslabsya4el/crafting-system/issues/223))** runs R15 and R17 end to end. The size of the real R15 graph with imprints is the open point: the base graph of R14, which R15 extends, holds at least 787,000 states and the held imprint rides along through all of them, so T13 plans with one imprint first and meets the ladder of ADR-0023 or the value-carrying form above if that does not fit.
- **The recombinator** keeps no imprint on its output (ADR-0034, not restorable); T5 ([#215](https://github.com/Rasslabsya4el/crafting-system/issues/215)) sets the clearing flag on its action.

Origin: [Grill B3](https://github.com/Rasslabsya4el/crafting-system/issues/94), [ticket #218](https://github.com/Rasslabsya4el/crafting-system/issues/218); ADR-0009, ADR-0013, ADR-0022, ADR-0026, ADR-0032, ADR-0033, ADR-0034.
