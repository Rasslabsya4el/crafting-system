# The finish is solved by value iteration over shared outcome tables, with the real colours kept

ADR-0045 left open how the socket finish is encoded: shared outcome tables handed to `solver.solve`, or a dedicated routine. [Ticket #230](https://github.com/Rasslabsya4el/crafting-system/issues/230) built a throwaway prototype of both on the kernels of ADR-0047 and measured them (times and memory on GitHub's runners; state, transition and sweep counts do not depend on the machine, and a few of them were counted on the development PC) (the prototype is `research/230/` in commit 6116ffa and its three follow-ups on the branch of the pull request; it is not in the tree). The decision is below; the numbers are under "Measured".

## Decision

1. **The finish is solved by its own value iteration inside `abstraction`, not by `solver.solve`.** Every state with the same link groups shares one outcome table for each Chromatic-type roll (the Chromatic Orb, the Omen of Trichromatism, the three bench colour crafts). A sweep computes one aggregate per table, `S = Σ P(c) · V(c)`, and every state reads it. The one outcome ADR-0047 excludes (the Chromatic Orb never returns the item's colours) is a per-state correction: with `e` the probability of the excluded outcome and `S` summed over all outcomes, the excluded one included at the state's own value, the backup of the action is `cost · (1 − e) + S`. That is exact: the excluded outcome is the state itself, and a self-loop with the cost scaled by `1 − e` is the same as drawing again without paying. The other actions (the Jeweller's Orb, the Orb of Fusing, the Omens of the Jeweller and Connections, the bench count and link crafts) have at most 32 outcomes and are listed explicitly. A sweep costs the states plus the table entries, not the states times the outcomes.
2. **The state keeps the real colours (white, red, green, blue) and the positions.** The two reductions ADR-0045 proposed are not exact and are dropped (ADR-0045 is amended); what stays is the one that is: link groups shorter than the group the target asks for are forgotten. See "What the state keeps".
3. **ADR-0010 is amended** (one paragraph there): `solver` is unchanged and stays standard-library only; the finish has its own routine in `abstraction`, which uses numpy as `risk` does, because a profile found the need. `abstraction` cannot import `solver` (ADR-0018), so nothing is shared with it, and the routine returns values and the greedy action, which is all S5 reads.

## Measured

Prototype on GitHub's `ubuntu-latest` runner, one process. Item level 84, 20% quality, from one white socket, three-attribute item (each colour a third of a coloured socket), every finish action of ADR-0045 offered, orbs priced 1 and the bench crafts at their orb counts. The Omens cost 50 in the group-of-five table and in the group of three, so that the plain rolls compete with them; the row "without Omens" offers none.

**Six sockets, three named colours, a group of five** (target: 6 sockets, 5 linked, one red, green and blue among them):

| | |
|---|---|
| reachable states | 13,552 (of 149,796 unreduced) |
| explicit transitions of the small actions | 157,200 |
| Chromatic-type state-actions / shared table entries | 67,632 / 79,443 |
| the dense product of states and outcomes | 205,209,564 |
| time to build / to solve | 0.9 s / 0.8 s (291 sweeps; plain iteration 576 sweeps, 1.0 s) |
| peak memory | 103 MB |
| the same without Omens | 13,552 states, 180,937,784 dense transitions, 378 sweeps, 1.0 s, 95 MB |

Other six-socket targets with three named colours: no link requirement 3,360 states (39,487,816 dense transitions); a group of 2 with red and green 16,729 (46,818,192); a group of 3 with red, green and blue 47,124 (713,592,728; 3.4 s to build, 2.3 s to solve, 325 MB, the largest found); a group of 4 25,264 (379,540,416); a group of 6 7,456 (111,686,424). The dense product of the group of five (2.05 × 10^8) is below the 5 × 10^8 of ADR-0045 because the state keeps only the long link groups; the group of three is above it.

**`solver.solve` on the same encodings** (the fixture of the next section at 4, 5 and 6 sockets: red, green and blue in a group of three, Orb of Fusing and Chromatic Orb only):

| sockets | states (the routine's, goals not counted) | dense transitions | `solver.solve` | peak memory | the routine |
|---|---|---|---|---|---|
| 4 | 916 | 236,376 | 10.1 s | 68 MB | 0.01 s, 35 MB |
| 5 | 6,010 | 6,183,342 | 136 s (shared tuples: 139 s) | 1.18 GB | 0.1 s, 38 MB |
| 6 | 38,784 | 159,213,984 | not run; about 1 hour and 30 GB by the ratio of the first two | | 0.9 s, 99 MB |

(`solve` reports 1,024 and 7,168 values because it also holds the goal states.) Handing `solve` one tuple of outcomes shared by all states of a shell changes nothing: it merges and walks the outcomes state by state, so the time is per transition (about 22 µs) and the memory too. The group of five would need about 75 minutes and 39 GB, the group of three about 4 hours and 135 GB, against the goal of a minute (ADR-0010). A zero-cost "table" node that all states of a shell point to would remove the walk, but `Action` requires a positive cost, and no positive split of the cost is exact because the self-loop scaling of the exclusion differs per state. So encoding 1 (shared tables through `solve`) fails on time and memory, and `solve` itself needs no change that would help.

**Convergence.** Plain value iteration needs about 5,600 sweeps when no Omen is offered (counted on the development PC, with Omens at 50 on the runner: 576 plain, 291 accelerated) (the optimal policy takes hundreds of orbs); Anderson acceleration with m = 6, accepted only when it lowers the Bellman residual, needs 378 and agrees with the plain result to 10^-12. The routine stops when the largest Bellman residual is below 10^-11 (about 10^-11 relative error in the value for prices of order 1). S5 may keep that, or use an exact policy evaluation; the prototype's numbers do not need it.

## Equal to the dense value iteration

The reference is the dense model with no reduction and no sharing: every state is a colour per socket and the link groups, every outcome of every action is listed (up to 256 Chromatic outcomes per state), the optimum is found by value iteration then policy iteration, and the Bellman residual of the result is checked (3 × 10^-15 on the fixture, checked on the development PC).

6,072 cases, 48 of which start at the goal: class maximum 4 (helmets) with starts of 1 and 4 white unlinked sockets and one that already has colours and a link, class maximum 3 with starts of 1 and 3; three colour weightings (equal thirds, a dexterity-intelligence item, a skewed one); equal prices and Omens at 30; the orbs only and every finish action; every target of count none or the class maximum, group none, 2, 3 or 4, and one to three of red, green and blue needed once or twice in the group (up to three needed in all). **The largest relative difference is 1.1 × 10^-11.** "Every case" is this grid: orbs priced alike or with Omens at 30, counts none or the class maximum, the starts above; the 48 cases that start at the goal are 0 on both sides without a comparison. It includes the three-linked red-green-blue group on four sockets (the next section) and 312 cases that name all three colours.

## What the state keeps

- **Unnamed colours are not merged with white.** The merged state (the colours the target does not name made white) was run against the same dense model: with all three colours named it is identical (it is the same state), with one or two named it differs from the dense value in 4,734 of 5,760 cases, by about 2% in the middle and up to 106%. The reason is the exclusion: which colours a Chromatic Orb cannot return depends on the item's real colours, and a state that forgot them cannot say. Keeping the real colours costs nothing against the worst case, which already has all three.
- **Positions are not dropped.** The whole-item quotient of ADR-0045 (only linked or unlinked and capped colour counts) cannot be exact because the Jeweller's Orb, when it lowers the count, removes the last sockets (ADR-0046): on a coloured item `(red, white)` and `(white, red)` have the same counts and different futures. Without the quotient a six-socket target with no link requirement and three named colours has 3,360 states, small enough.
- **Link groups shorter than the target's group are forgotten**, and nothing else: no later action grows a group or reads a short one (a reroll of the links replaces all groups; the Jeweller's Orb adds unlinked sockets and cuts groups from the end). A state with a group that already qualifies keeps its start and size.

## The fixture

Four white, unlinked sockets, item level 84, 20% quality, the three attribute requirements equal, Orb of Fusing at 20% quality and Chromatic Orb only, one orb each at a price of 1, red, green and blue needed in a group of at least three: the optimal policy costs **44.60 orbs**, links first and then colours costs **102.99 (103.0)**, 2.31 times more. The two are equal when the group is the whole item. The design's figures reproduce on this item, which ADR-0045 did not name. Its second pair (a two-linked group, 64.5 against 174.0) did not: on this item the two-linked groups cost 11.5 and 23.2 (red and green) and no other colour set or weighting tried gave 64.5, so its item is unknown and it stays out of the tests. `tests/test_socket_finish_reference.py` keeps the fixture: an oracle written from the formulas of ADR-0047 (it does not import the product), the 2,048 raw states, the exclusion and Fusing's group sizes, solved by policy iteration in seconds. S5's layer 3 runs against it.

## What follows

- **S5 (#231)** builds the finish routine from this ADR: the state, the shared tables and the per-state correction as above, values and the greedy action out. The `bound` flag of ADR-0048 and the second readings of ADR-0047 are further keys on the same routine (a second reading is the same policy evaluated with other tables, not a re-solve). The prototype stays in the notes folder of the sessions and in the commits named above.
- **Cost of a reduction that is not exact is paid in states, not answers**: the largest finish found has 47,124 states and solves in seconds.
- **No amendment of ADR-0047's marks.** The prototype used the ADR's inputs unchanged; the exclusion rule and the forced-socket rule are the ones it names.

Origin: [Design grill B6](https://github.com/Rasslabsya4el/crafting-system/issues/104) (departure 1 of the resolution); ADR-0010, ADR-0018, ADR-0019, ADR-0045, ADR-0046, ADR-0047.
