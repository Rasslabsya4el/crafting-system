"""Design D, compression, family types, pool signatures, the cached kernel (ADR-0009). May import only: data, rules, items, actions.

An `Abstraction(data, goal, base_id, item_level, actions, *, metamods=False, enchantment=None)` turns a concrete `Item` into a
`CompressedState` and gives the exact kernel of an action on it. An action is anything that meets the
contract of `actions` (`Action`: a Chaos Orb, a Harvest reforge, an essence, a resonator, a bench craft,
a toy defined in a test): the kernel is built from its `outcomes` alone, and what a state keeps is read
from the action's own declaration `reads(data)`. `actions` are the enabled actions that read the mods
besides the fractured ones (none by default): they decide what a state keeps. No concrete action class
is imported or tested for here.

* `Goal`: the requirements as `Wanted` leaves (`mod_ids`, `min_tier`, `min_roll`, `not_crafted`)
  and `AtLeast(k, members)` groups; `Goal.from_target(target)` reads a target by duck typing and
  imports nothing of `targets`. `Goal.leaves` is the depth-first, file-order list of leaves and the
  order of `CompressedState.status`; `Goal.is_met(statuses)` needs `Status.PASSING` for a leaf.
* `Status`: ABSENT < BELOW < PASSING, what an item gives one leaf; the best of several mods wins.
* `CompressedState(flags, fractured, status, slots, implicits, quality, offer)`: `Flags` (rarity, corrupted, influences), the
  fractured mods as `FracturedMod(canonical id, contribution to each leaf)` sorted, the status of
  each leaf over the whole item, and the `Slot`s, a sorted multiset of the other mods (below). The last three
  are the item state beyond the explicit mods (ADR-0027, ticket #142), empty unless an enabled action reads or
  changes that part: `implicits` the Eldritch pair, one `ImplicitSide(grade, contribution)` for the Searing Exarch
  and one for the Eater of Worlds (the contribution is to each `Goal.implicits` leaf, an `ImplicitWanted`);
  `quality` the catalyst `Quality` as the item stores it; `offer` the mods of the unveil offer, each an
  `OfferedMod(canonical id, contribution)`. `Abstraction.tracks_implicits`, `tracks_quality` and `tracks_offer` say
  which are kept; they follow the `Reads` and `Adds` declarations of the enabled actions (`implicits`, `quality`,
  `offer`) and, for the implicits, whether the goal asks for one. `is_goal` also needs, for each implicit wanted,
  a side that passes it. A corrupted state is a goal only when `Goal.takes_corrupted` (the target asks for a corrupted implicit or
  allows a corrupted item, ADR-0036) and a state that is not corrupted is no goal of a target that asks; `meets_requirements` is the
  check without the corruption. The corrupted implicit an action adds is not kept in the state, the action decides it.
  `CompressedState.crafted` says a slot is crafted; `count(side)` counts the slots of a side.
* `Slot(side, kind, contribution, crafted)`: a mod that is not fractured, by its side, its kind and
  what it gives each leaf. The kind is "" for a family that every enabled action treats alike (a
  family type), the family key for a family told apart, the canonical mod id for a crafted mod.
* `Abstraction.compress(item)`, `is_goal(state)`, `kernel(state, action)` (exact `Fraction`s that
  sum to 1, no zero entries), `signature(state, action)`, `reachable(starts, actions)` (breadth-first
  closure; an action that raises an `ActionError` in a state is skipped there),
  `family_types(tag, fossils)` (the families of the empty pool grouped by family type: the "family types
  of the amulet's junk"; with a resonator, of the pool its fossils make), `stats` (`CacheStats(kernels, hits)`).
* `reach_bound(abstraction, state, action, leaves, exact=False)`: an upper bound, from the pool alone, on the
  chance that one use of an erasing reroll makes every leaf of `leaves` PASSING (the exact chance with
  `exact=True`; None for an action it cannot bound); the argument is in `_bound.py` (#118).
* `keeps_shape(abstraction, state, action)`: whether every outcome of the action keeps the flags and the
  fractured mods of the state (what a bound read at one state needs to hold at the next; #118).
* `Coarsening(abstraction, groups)` (`_coarse.py`, ADR-0023): the coarse state. Junk families that no requirement
  cares about are pooled into groups (a pool is made of kinds: told-apart families and whole family types `~n`);
  `coarsen(state)` maps an exact state to its `Block` (a `CompressedState` whose pooled slots have the kind of
  their pool) and `kernel(block, action, bound)` is the kernel of an action in the optimistic (`"lower"`) or
  pessimistic (`"upper"`) model, per member. A block-invariant action (`Reads.block_invariant`: an erasing reroll,
  a bench craft, Remove Crafted Mods, Annulment) has one kernel. An action that adds mods and keeps the junk
  (`Reads.variants`: Augmentation, Regal, Exalted) has up to `2^p` variant kernels, those of the members that hold
  the lightest or the heaviest pool weight in each of the `p` pools: `variants(block, action, bound)` lists them
  (the optimistic model takes the cheapest backup, the pessimistic the dearest) and `kernel` returns the one when
  there is one. An action that declares neither raises `OutOfScopeError`. `Coarsening.pooling_irrelevant(abstraction,
  size)` and `Coarsening.pooling_by_spread(abstraction, spread)` build the groups (the second pools consecutive kinds
  by per-family weight, for the additions).
* `Abstraction.estimate(starts, actions)` (`_estimate.py`, ADR-0023): the pilot count. The states and transitions of the
  exact graph, found with one kernel per (reroll, key) and the bench legality by sets of families and free slots; an
  `Estimate` also forecasts a coarse level (`coarsened`) and gives a closed prefix of the graph for a calibration
  solve (`first_layers`). An action with no closed form (an addition, Annulment) is walked with its real kernel on
  every state (`Estimate.walked`): `needs_walk(abstraction, actions)` says so beforehand and `ADDING_LIMIT` is the
  smaller state limit for such a walk. `EstimateRefused` is raised when a walked kernel cannot be computed.
* `Abstraction(..., reading=...)` (ticket #210): the ordinary model of one `Reading` of the rule axes the enabled actions read
  (`actions.model_readings`); every kernel is taken at it. `Abstraction.inputs(state, action)` gives the `Need`s of an action on
  the item a state stands for, and `allow_inputs=False` (the planner's) refuses an action that has some (`OutOfScopeError`).
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
by their canonical mod id; a reroll drops them (an ordinary crafted mod is erased like any other,
a lock or an Attack/Caster metamod too: see "Metamods" below). A new action that
reads the mods says how it tells families apart in its `reads` (`Reads.families`); one that says nothing
tells every family apart (exact, but the state count can blow up).

An action runs on a concrete item that the state stands for: its fractured mods, its crafted mods and
one mod of a distinct family of the right side and kind for every other slot. The outcomes come from
the action itself, so no rule is decided here. They are a mixture of parts (`components`): a fixed
result (`Fixed`: the mods that stay and the new ones, as in a bench craft) or a pool draw (`Outcomes`:
the retained mods, the forced mod and the new draws, each a slot of its side and kind, seen through the
label of the draw: what it gives each leaf, its side and its kind). A mod of a part that the item given
to the action held is the state's own fractured mod or slot; any other is new.

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

An action that adds mods and keeps the junk (Augmentation, Regal, later Exalted) makes the outcome
depend on the weights of the junk families too: a family on the item leaves the pool. It declares
`Reads.adding()` (`pool_weight`), and every family that no enabled action tells apart by name then
gets the kind of its family type, `"~n"`: its side, and the sorted (what each mod gives the goal,
weight) of its mods in the pool of an empty rare item. Two junk families of one type leave the same
pool, so the states merge exactly. A magic item needs nothing else: the rarity is a flag and the
capacity (1 + 1 for magic, 3 + 3 for rare) is in the free slots of the pool signature. A
Transmutation, an Alteration, an Alchemy and a Scouring erase the junk and add no slot.

Roll requirements (#71). A leaf with `min_roll` (a roll limit) is passed by a mod only when its values reach every wanted
number. A mod an action draws from a pool rolls its values: each stat takes every integer of its range with the same
chance, the stats independently (with `Outcomes.rolls_lucky`, a Sanctified Fossil, each value is rolled twice and the one
nearer the stat's `max` kept). `_rolls.py` builds the exact roll law of a mod: the distribution, over what the mod gives every
leaf, of its values being rolled (cut into cells at the wanted numbers, so two leaves on one mod share the one roll). A mod
whose law has several outcomes is rollable and its label is the law (`RollLaw`); the engine counts mods per label and
`_distribution` spreads n mods of one law over its outcomes by the multinomial, so the drawn slots carry the contribution of
the roll they got. A mod with one outcome keeps the label it always had, so a goal without roll limits is unchanged. When an
enabled action rerolls values in place (`Reads.rerolls_values`, a Divine Orb: its result is a `Rerolled` part), every family
with a rollable mod is told apart by mod (the kind `"$" + mod id`) and the kernel of the part gives each rerolled slot of such
a mod a fresh contribution drawn from its law; the fractured mods and the mods of a locked side (not in `changed`) keep theirs.
Out of scope, all `OutOfScopeError`: a `min_roll` on a mod that an action forces (an essence), crafts or puts on the item as a
fixed result (a bench craft); a Divine Orb on a crafted slot that a roll limit looks at (the range of the real mod is not known
from its canonical id); a draw that fractures one of its mods (a Fractured Fossil) from a pool with a rollable mod; and, as
refusals of the planner's helpers, `reach_bound` (None), the pilot count (`EstimateRefused`) and `Coarsening` with a Divine
Orb enabled. A concrete item's mod is judged by its stored tier and values.

Metamods, removals, new fractures and influence (#69). `metamods=True` (forced when an enabled action adds a lock
or an Attack/Caster metamod by name) lets items hold them: every mod is then kept as a slot told apart by family
type, and its kind also carries the tags an Attack or Caster metamod looks at (`"~3@attack"`; the number of
the family type, `"~3"`, has none, but the type is told from another by the tags of its mods). No action
then erases the junk: the item given to a reroll or a Scouring holds every slot, and what the action keeps (the fractured mods and the mods of a locked side) is read back, the rest is
dropped. `compress` of an item that holds a lock or an Attack/Caster metamod raises `OutOfScopeError` when
`metamods` is False. The multimod ("Can have up to 3 Crafted Modifiers") is only a bench limit.
The start item's enchantment (`enchantment`, a mod id) is a constant of the problem and is not in the state (ADR-0050, ADR-0053): no
action adds or removes one. The items the kernel rebuilds hold it, so the limit of crafted mods an action reads from the item (one,
two with the enchantment of the extra crafted slot, three with the multimod, three with both) is the one the pilot count uses
(`crafted_limit_of`); `compress` refuses an item whose enchantment is another.
An Orb of Annulment reads the count of the junk and, through the sides, tags and locks, which mods it may remove:
its parts are fixed results and the removed mod's slot just disappears. A Fracturing Orb is a fixed result too:
the slot of the fractured mod becomes a fractured mod. When an enabled action declares `Reads.fractures`, a
fractured mod of a family told apart only by its family type is stored as that type's kind (`FracturedMod.mod_id`
`"~3"`, not a mod id), which `compress` gives the concrete fractured mod too; the pilot count and the family-group
level refuse such a state. The tiers come from the pool of the item's influences (`actions.tiers_of`), so an
influence mod has its own tier, and the family types are those of the pool with the influence tags: one context
(tiers, kinds, labels) per set of influences, built when first needed; the family type numbers are shared, so one
`"~n"` is one family type in every context and equal pools share one cached distribution.

Veils and the unveil offer (#145, ADR-0026). A veiled placeholder is a slot of the kind of its family (`VeiledPrefix`, `VeiledSuffix`);
a mod unveiled from the pool is a slot of the kind `^<family>`, never an ordinary mod of the same family (Movement Speed on boots); the
craftable version of one is a crafted slot kept apart from the other crafted mods of its family while an enabled action reads a
placeholder family. An item with a signature placeholder or a double veil is `OutOfScopeError` at `compress` when the model tracks the offer.
A state that holds an offer is a choice node: `kernel` raises `NotApplicableError` for any action that does not read the offer (a pick
does), so the pilot count, the bound pruning and the solver's actions never offer another there. The offer is kept in the item's order
(`Pick(k)` takes the k-th), each entry by the canonical id of its kind, and the representative item is given ids that rise as the
entries do. `Reads.families` of `Unveil` and `Pick` lists the families of the unveiled pool, so the junk that blocks an offer is told apart.

No mechanic is decided here: this module only recombines the results of `actions`, so it reads no
claim of the rules registry.
"""

from ._bound import keeps_shape, reach_bound
from ._coarse import Block, BlockHoldsMetamod, Coarsening
from ._estimate import ADDING_LIMIT, DEFAULT_LIMIT, Estimate, EstimateRefused, needs_walk
from ._goal import AtLeast, Goal, ImplicitWanted, Status, Wanted
from ._kernel import Abstraction, CacheStats, FamilyType, integer_weights
from ._state import CompressedState, Flags, FracturedMod, ImplicitSide, OfferedMod, Slot

__all__ = [
    "ADDING_LIMIT",
    "DEFAULT_LIMIT",
    "Abstraction",
    "AtLeast",
    "Block",
    "CacheStats",
    "Coarsening",
    "CompressedState",
    "Estimate",
    "EstimateRefused",
    "FamilyType",
    "Flags",
    "FracturedMod",
    "ImplicitSide",
    "ImplicitWanted",
    "OfferedMod",
    "Slot",
    "Goal",
    "Status",
    "Wanted",
    "integer_weights",
    "keeps_shape",
    "reach_bound",
    "BlockHoldsMetamod",
    "needs_walk",
]
