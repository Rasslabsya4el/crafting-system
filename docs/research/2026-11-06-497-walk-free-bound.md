# The crafted-pattern lower bound, built from the abstraction without the walk (ticket #497)

Question of the ticket: build the lower bound of research #376 (the optimistic model of the key *status of the wanted mods, rarity, mods per side, fractured ids, crafted mods*, with the protected tags of the junk when a metamod is possible) from `Abstraction` alone, with no walk of the concrete graph, and say for each action class why the model offers an action at least as good as every concrete state's (ADR-0063 point 3; decision #498). Rules read: OR-10 (no detail that no decision reads), OR-11 (the answer is exact among realistic routes), OR-12 (no fixed rail or tolerance cut: the bound is the lower side of an exact branch-and-bound, and a safety net says so), OR-13 (a cut says what it guarantees: this bound is what `[LB, U]` needs), OR-26 (the defect behind the numbers is traced to its root, not patched per case), OR-29 (open points become issues, below).

Code: `src/crafting_system/abstraction/_pattern.py` (the key, its members, the model; the soundness argument is its module docstring), `src/crafting_system/cli/_pattern_bound.py` (the offers, the packed graph, the solve). Tests: `tests/test_abstraction_pattern.py` (every action class against brute force on a fixture bow), `tests/test_abstraction_pattern_real.py` (R05 and R13 against their walked graphs). Measurement: `research/497/pattern_bound.py`.

## Short answer

RESULT_TABLE_PLACEHOLDER

## What is built

`build_pattern_model(abstraction, start, offers)` explores the keys from the key of the start. In a key that is not a goal it offers, for each priced offer, the exact kernel (`Abstraction.kernel`) of the **members** that the offer's action class stands for, pushed through the key; two members with equal pushed kernels give one abstract action; a member that the action refuses does not offer it; a restart leads to the start key. The model is solved on the packed solver (`solve_packed`), and `PatternBound.lower` is the start value less the solver's certified error. Nothing walks the concrete graph: the members of a key are *made* from the key (`Pattern.members`), as items the abstraction can give to an action (`Abstraction._item_of` is the test), not found.

**The key.** `PatternKey = (flags, fractured mods, status, the item state beyond the mods, the crafted slots, ordinary mods per side, the protected tags of the ordinary mods per side)`; the last is left out when the key is built `tags=False`, and is on by default when the abstraction models the metamods. The flags, the fractured mods and the item state are the whole `CompressedState` fields (not only the rarity and the ids), so the key is as fine as the research's or finer; on the three routes they are constants of the route and the number of abstract states is the research's.

**The members.** An ordinary slot is *pure junk* when its kind is a family type `~n` none of whose mods gives the goal anything; every other ordinary slot is *relevant* (it gives a leaf something, or it is of a family type that has such a mod, or an enabled action names its family). The relevant slots of a key are enumerated exactly (every multiset consistent with the status, the counts and the tags). A pure junk slot belongs to a **class**: its side and its protected tags. The class counts are in the key (with the tags) or enumerated (without); inside a class the members differ in which family types they hold, and so in the pool weight `H_c` the held families take out of a draw (under the key's blocked tags: a held family takes out only the weight of the mods the draw can still roll).

**The member policy of an action class** (`Pattern.mode_of`; the argument for each is in the module docstring, here is its state):

| Class (how it is told) | Offered members | Soundness |
| --- | --- | --- |
| Erasing reroll that reads no junk: Chaos, Alteration, Transmutation, essences, Harvest reforges (`block_invariant`, `junk=False`), key without a lock | one (`ANY`) | Proved: ADR-0023 (block invariance), checked by the contract suite |
| Bench craft, Remove Crafted Mods, Annulment (`block_invariant`, reads the junk, no pool weight), key without a lock | one for each relevant multiset and class composition (`ONE`) | Proved: bench crafts read the families they name (relevant kinds); the Annulment removes one removable slot uniformly and the removable slots are counted by class, so the pushed kernel does not depend on which types the pure junk of a class holds. **Extended here to the Annulment under protected tags**: with the tags in the key (or the compositions enumerated) the removable count by class is fixed |
| Addition of one mod that keeps the junk: Augmentation, Regal, Exalted (`variants`) | the lightest and the heaviest fill of each class (`EXTREMES`) | Proved for one draw by ADR-0023 (the chance of a successor key is linear-fractional in the held weights, so the least backup over a box is at a corner, and a corner is a member). **Extended here to the protected tags** (the held weight of a class under the key's blocked tags; the argument is in the docstring) and tested against every member of a key |
| Fracturing Orb, an erasing reroll under a lock, any action that is not declared one of the above, an addition that draws by tag or level | every member (`ALL`) | By construction (every member is offered), **not proved to need fewer**: the Fracturing Orb's successor key holds the type fractured, a function of which types the member holds, not of their weights; a reroll under a lock keeps the junk of its side and draws several mods from a pool without it, so its chance is a product of ratios, not a linear-fractional function |

If two classes make a corner impossible together (one family type shared by two tag kinds), the composition uses every member: `stats.fallbacks` counts them.

**What is trusted.** The classification reads the action's own declaration (`Reads.block_invariant`, `variants`, `pool_weight`, `fractures`, `junk`), as `Coarsening` does (ADR-0023): an action that declares block invariance wrongly makes the bound wrong, and the contract suite is what checks a declaration. An abstraction with a roll limit on the goal, an action that rerolls values, an unveil offer or imprints is refused (`OutOfScopeError`): the slots of such a state are not enumerable from the pool.

## Tests

- **Every action class against brute force** (`tests/test_abstraction_pattern.py`, a fixture Thicket Bow with five attack-tagged prefix families of four weights, three suffix families, the lock, the Attack and the Caster metamods; the Exalted Orb, the Annulment, the Fracturing Orb, a Chaos Orb and Remove Crafted Mods; keys of states a seeded random walk met, with the tags in the key and without): every walked state is a member of its key (the brute force is complete); for random values of the successor keys, the least backup over the offered members is at most the backup of every member of the key, and the action is offered whenever a member can take it. The comparison can fail: the lightest member alone fails it for the Exalted Orb, and one member fails it for a Chaos Orb under a lock (that is why those two classes are not `ANY`/`ONE`). The extremes are fewer than every member on the keys with a choice of junk.
- **Never above the exact cost, at every state** (`tests/test_abstraction_pattern.py`, the fixture's exact graph; `tests/test_abstraction_pattern_real.py`, R13 with and without the tags and R05, against the research walker's graph): the value at the key of every walked state is at most the state's exact value, and no walked state has a key the model never reached. `research/497/pattern_bound.py --check` makes the same comparison on R04, R14 and S02 in a heavy run (below).

CHECK_PLACEHOLDER

## Limits

LIMITS_PLACEHOLDER

## Open points, filed (OR-29)

ISSUES_PLACEHOLDER
