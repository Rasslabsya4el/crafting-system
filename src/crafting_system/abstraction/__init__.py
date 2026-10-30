"""Design D, compression, family types, pool signatures, the cached kernel (ADR-0009). May import only: data, rules, items, actions.

An `Abstraction(data, goal, base_id, item_level)` turns a concrete `Item` into a `CompressedState` and
gives the exact kernel of a rerolling action on it: `ChaosOrb()` and `HarvestReforge("lightning")`,
or any hashable object with `outcomes(data, item) -> Outcomes`.

* `Goal`: the requirements as `Wanted` leaves (`mod_ids`, `min_tier`, `min_roll`, `not_crafted`)
  and `AtLeast(k, members)` groups; `Goal.from_target(target)` reads a target by duck typing and
  imports nothing of `targets`. `Goal.leaves` is the depth-first, file-order list of leaves and the
  order of `CompressedState.status`; `Goal.is_met(statuses)` needs `Status.PASSING` for a leaf.
* `Status`: ABSENT < BELOW < PASSING, what an item gives one leaf; the best of several mods wins.
* `CompressedState(flags, fractured, status)`: `Flags` (rarity, corrupted, influences, crafted),
  the fractured mods as `FracturedMod(canonical id, contribution to each leaf)` sorted, and the
  status of each leaf over the whole item.
* `Abstraction.compress(item)`, `is_goal(state)`, `kernel(state, action)` (exact `Fraction`s that
  sum to 1, no zero entries), `signature(state, action)`, `reachable(starts, actions)` (breadth-first
  closure; an action that raises an `ActionError` in a state is skipped there),
  `family_types(tag)` (the families of the empty pool grouped by family type: the "family types of
  the amulet's junk"), `stats` (`CacheStats(kernels, hits)`).
* `integer_weights(kernel)`: the kernel as integers with a common denominator, gcd-reduced; the
  form the solver takes.

What is stored and what is merged away. A Chaos Orb and a Harvest reforge erase every mod that is
not fractured and redraw it. The outcome therefore depends only on the fractured mods (their
families, sides and count), the base, the item level, the flags and the action. The junk that is not
fractured is not stored: it is erased by every action here, so merging it is exact. The goal needs
only the status of each leaf, which is kept. A fractured mod is stored by a canonical id (the
smallest id among the mods with the same families, side, domain and contribution) so that, say,
two tiers of one resistance are one state when no tier is asked.

The cache. The retained item of a state is rebuilt and the action gives its `Outcomes`. What decides
the distribution of the new mods, seen through the label (a mod's contribution to every leaf), is the
guaranteed tag, how many mods are kept, the free slots per side, the totals, and the multiset of
family types of the pool, a family type being its side and the (label, weight, tagged) of its mods.
That tuple is the signature; two states with an equal signature share one distribution, computed once.
Fractured junk of two different families with the same shape is such a pair. The cost of a
distribution is that of `Outcomes.distribution` (see `actions`): it grows with the number of distinct
(side, weight, label) classes in the pool, about 0.3 to 3 s for a real amulet with a coarse label,
paid once per signature.

Widening for B1: an action that does not erase the junk (a Chaos Orb that keeps some mods, a
craft that adds one) makes the outcome depend on the junk families too, so the junk family types
must be added to the state as a multiset before such an action is admitted.

Out of scope: a `min_roll` on a mod that an action draws. Its value is rolled and no exact roll
distribution is built yet, so the label of such a mod raises `OutOfScopeError`. A concrete item's mod
is judged by its stored tier and values. A state with a crafted mod or metamod has no kernel: the
actions refuse it, and the state keeps only the flag.

No mechanic is decided here: this module only recombines the results of `actions`, so it reads no
claim of the rules registry.
"""

from ._goal import AtLeast, Goal, Status, Wanted
from ._kernel import Abstraction, CacheStats, FamilyType, integer_weights
from ._state import CompressedState, Flags, FracturedMod

__all__ = [
    "Abstraction",
    "AtLeast",
    "CacheStats",
    "CompressedState",
    "FamilyType",
    "Flags",
    "FracturedMod",
    "Goal",
    "Status",
    "Wanted",
    "integer_weights",
]
