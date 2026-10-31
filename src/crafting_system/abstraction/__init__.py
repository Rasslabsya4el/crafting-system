"""Design D, compression, family types, pool signatures, the cached kernel (ADR-0009). May import only: data, rules, items, actions.

An `Abstraction(data, goal, base_id, item_level, actions)` turns a concrete `Item` into a
`CompressedState` and gives the exact kernel of an action on it: the rerolls `ChaosOrb()`,
`HarvestReforge("lightning")`, `ApplyEssence(name)` and the fossil sets `ApplyFossils(names)`, the
bench's `BenchCraft(mod_id)` and `RemoveCraftedMods()`. `actions` are the enabled actions that read the mods besides the fractured
ones (the bench; none by default): they decide what a state keeps.

* `Goal`: the requirements as `Wanted` leaves (`mod_ids`, `min_tier`, `min_roll`, `not_crafted`)
  and `AtLeast(k, members)` groups; `Goal.from_target(target)` reads a target by duck typing and
  imports nothing of `targets`. `Goal.leaves` is the depth-first, file-order list of leaves and the
  order of `CompressedState.status`; `Goal.is_met(statuses)` needs `Status.PASSING` for a leaf.
* `Status`: ABSENT < BELOW < PASSING, what an item gives one leaf; the best of several mods wins.
* `CompressedState(flags, fractured, status, slots)`: `Flags` (rarity, corrupted, influences), the
  fractured mods as `FracturedMod(canonical id, contribution to each leaf)` sorted, the status of
  each leaf over the whole item, and the `Slot`s, a sorted multiset of the other mods (below).
  `CompressedState.crafted` says a slot is crafted; `count(side)` counts the slots of a side.
* `Slot(side, kind, contribution, crafted)`: a mod that is not fractured, by its side, its kind and
  what it gives each leaf. The kind is "" for a family that every enabled action treats alike (a
  family type), the family key for a family told apart, the canonical mod id for a crafted mod.
* `Abstraction.compress(item)`, `is_goal(state)`, `kernel(state, action)` (exact `Fraction`s that
  sum to 1, no zero entries), `signature(state, action)`, `reachable(starts, actions)` (breadth-first
  closure; an action that raises an `ActionError` in a state is skipped there),
  `family_types(tag, fossils)` (the families of the empty pool grouped by family type: the "family types
  of the amulet's junk"; with a resonator, of the pool its fossils make), `stats` (`CacheStats(kernels, hits)`).
* `integer_weights(kernel)`: the kernel as integers with a common denominator, gcd-reduced; the
  form the solver takes.

What is stored and what is merged away. A Chaos Orb, a Harvest reforge and an essence erase every mod
that is not fractured and redraw it (an essence also forces one mod, which stays; a resonator does the
same with the weights of its fossils, and a Hollow or Glyphic Fossil forces one), so their outcome
depends only on the fractured mods (families, sides, count), the base, the item level, the flags
and the action. With only those enabled, the junk that is not fractured is not stored: merging it is
exact, and a state is the fractured mods, the flags and the status of each leaf. A fractured mod is
stored by a canonical id (the smallest id among the mods with the same families, side, domain and
contribution) so that, say, two tiers of one resistance are one state when no tier is asked.

The bench reads the junk: a craft needs a free slot on the side of its mod and no family in common
with a mod on the item, and Remove Crafted Mods needs a mod left. With one enabled, every mod that
is not fractured is a `Slot`, counted per side and kind. A family type is the families that every
enabled action treats alike; a family that an enabled craft would clash with is told apart (its kind
is the family key), as is a family the pool does not list. Crafted mods are always slots, told apart
by their canonical mod id; a reroll drops them (an ordinary crafted mod is erased like any other),
and a state with a crafted metamod is refused by the rerolls as `OutOfScopeError`. A new action that
reads the mods must say how it tells families apart, in `Kinds`; an unknown one tells every family
apart (exact, but the state count can blow up).

An action runs on a concrete item that the state stands for: its fractured mods, its crafted mods and
one mod of a distinct family of the right side and kind for every other slot. `Outcomes` and
`BenchOutcomes` come from the action itself, so no rule is decided here. A reroll's outcome is the
fractured mods, the forced mod of an essence and the new draws, each a slot of its side and kind
(seen through the label of the draw: what it gives each leaf, its side and its kind); a bench action
adds a crafted slot or drops the crafted ones.

The cache. What decides the distribution of the new mods, seen through the label, is the guaranteed
tag, how many mods are kept (the forced mod of an essence included), the free slots per side, the
totals, and the multiset of family types of the pool, a family type being its side and the (label,
weight, tagged) of its mods. That tuple is the signature; two states with an equal signature share
one distribution, computed once. A low essence caps the level of the pool, which shows in the weights;
the forced mod is not in the signature because it cannot change the draw once the pool, the kept
count and the free slots are known. The cost of a distribution is that of `Outcomes.distribution`
(see `actions`): it grows with the number of distinct (side, weight, label) classes in the pool, about
0.3 to 3 s for a real amulet with a coarse label, paid once per signature. A bench action draws
nothing and has no cache.

A resonator needs nothing more: the factors and blocks of its fossils are in the weights of the pool
it builds, and the weights are in the family types, so the signature is set-independent. Sets with an
equal pool (a fossil that touches no mod of the base, two sets that weigh the pool alike, a Chaos Orb)
share one distribution. A Tangled or Glyphic Fossil makes a mixture of pools; each pool is cached by
its own signature and the kernel is the sum over the pools by their probability. A Fractured
Fossil fractures one finished mod, so the state records which one: the mod joins `fractured` by its
canonical id. The engine counts classes, not families, so the fractured mod is found with one run per
family type (that type's mods marked), cached by the pool signature and the label of the forced mod; it
costs the number of family types times a plain distribution, which is why the action set of a target
needs pruning (see ADR-0009).

Widening for the rest of B1: an action that adds or removes one mod (Exalted, Annulment, Regal)
makes the outcome depend on the weights of the junk families too, so its family types must
add the pool weights; that is done in `Kinds` when the action is added.

Out of scope: a `min_roll` on a mod that an action draws, forces or crafts. Its value is rolled and no
exact roll distribution is built yet, so such a mod raises `OutOfScopeError`. A concrete item's mod is
judged by its stored tier and values. A metamod has no reroll kernel: the rerolls refuse it. The
multimod ("Can have up to 3 Crafted Modifiers") makes the bench refuse as well until its limit is
modelled.

No mechanic is decided here: this module only recombines the results of `actions`, so it reads no
claim of the rules registry.
"""

from ._goal import AtLeast, Goal, Status, Wanted
from ._kernel import Abstraction, CacheStats, FamilyType, integer_weights
from ._state import CompressedState, Flags, FracturedMod, Slot

__all__ = [
    "Abstraction",
    "AtLeast",
    "CacheStats",
    "CompressedState",
    "FamilyType",
    "Flags",
    "FracturedMod",
    "Slot",
    "Goal",
    "Status",
    "Wanted",
    "integer_weights",
]
