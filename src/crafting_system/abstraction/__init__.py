"""Design D, compression, family types, pool signatures, the cached kernel (ADR-0009). May import only: data, rules, items, actions.

An `Abstraction(data, goal, base_id, item_level, actions, *, metamods=False, enchantment=None)` turns a concrete `Item` into a
`CompressedState` and gives the exact kernel of an action on it. An action is anything that meets the
contract of `actions` (`Action`: a Chaos Orb, a Harvest reforge, an essence, a resonator, a bench craft,
a toy defined in a test): the kernel is built from its `outcomes` alone, and what a state keeps is read
from the action's own declaration `reads(data)`. `actions` are the enabled actions that read the mods
besides the fractured ones (none by default): they decide what a state keeps. No concrete action class
is imported or tested for here.

* `Goal`: the requirements as `Wanted` leaves (`mod_ids`, `min_tier`, `min_roll`, `not_crafted`, and `tier_ok`, the mods the tier limit
  accepts by their natural tier in the game data). `status_of` is the one judgement of a mod against a leaf (ticket #457); a target's
  `Requirement` uses it too
  and `AtLeast(k, members)` groups; `Goal.from_target(target)` reads a target by duck typing and
  imports nothing of `targets`. `Goal.leaves` is the depth-first, file-order list of leaves and the
  order of `CompressedState.status`; `Goal.is_met(statuses)` needs `Status.PASSING` for a leaf.
* `Status`: ABSENT < BELOW < PASSING, what an item gives one leaf; the best of several mods wins.
* `CompressedState(flags, fractured, status, slots, implicits, quality, offer, imprints, strands, replaced)`: `Flags` (rarity, corrupted, influences), the
  fractured mods as `FracturedMod(canonical id, contribution to each leaf)` sorted, the status of
  each leaf over the whole item, and the `Slot`s, a sorted multiset of the other mods (below). The last four
  are the item state beyond the explicit mods (ADR-0027, ticket #142), empty unless an enabled action reads or
  changes that part: `implicits` the Eldritch pair, one `ImplicitSide(grade, contribution)` for the Searing Exarch
  and one for the Eater of Worlds (the contribution is to each `Goal.implicits` leaf, an `ImplicitWanted`, the roll included; with an action that declares
  `Reads.implicit_lines`, an Orb of Conflict, a side also keeps its `line` when a requirement names a mod of it, ticket #152), then one
  `ImplicitSide` for each implicit of the base that a requirement names (ticket #158: a Blessed Orb rolls it afresh and the kernel spreads the
  state over the law of the roll; an implicit rolled afresh by any fixed result, an Ember's or a Conflict's, is spread the same way);
  `quality` the catalyst or plain quality as the item stores it; `offer` the mods of the unveil offer, each an
  `OfferedMod(canonical id, contribution)`; `imprints` (ADR-0060, ticket #219) the set of states an imprint of the item was made at, in the
  stable order of `CompressedState.order_key`, each holding none of its own. `Abstraction.tracks_implicits`, `tracks_quality`, `tracks_offer` and
  `tracks_imprints` say which are kept; they follow the `Reads` and `Adds` declarations of the enabled actions (`implicits`, `quality`,
  `offer`, `imprints`) and, for the implicits, whether the goal asks for one. `is_goal` also needs, for each implicit wanted,
  a side that passes it. A corrupted state is a goal only when `Goal.takes_corrupted` (the target asks for a corrupted implicit or
  allows a corrupted item, ADR-0036) and a state that is not corrupted is no goal of a target that asks; `meets_requirements` is the
  check without the corruption. The quality (`Goal.quality`, a `QualityWanted`) is the last requirement (ADR-0029, ticket #158):
  `meets_all_but_quality` is every other requirement, and `quality_offer_pruned(state, action)` says that an action which only sets
  the quality (`Adds.only_quality`, a catalyst) is not an action of a state that fails another requirement. The corrupted implicit an action adds is not kept in the state, the action decides it.
  `CompressedState.crafted` says a slot is crafted; `count(side)` counts the slots of a side.
* `Slot(side, kind, contribution, crafted)`: a mod that is not fractured, by its side, its kind and
  what it gives each leaf. The kind is "" for a family that every enabled action treats alike (a
  family type), the family key for a family told apart, the canonical mod id for a crafted mod.
* `Abstraction.compress(item)`, `is_goal(state)`, `kernel(state, action)` (exact `Fraction`s that
  sum to 1, no zero entries), `signature(state, action)`, `reachable(starts, actions)` (breadth-first
  closure; an action that the game refuses in a state, or the model has no rule for there, is skipped there),
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
* `Pattern(abstraction)` and `build_pattern_model(abstraction, start, offers)` (`_pattern.py`, ticket #497, research #376): the optimistic model of the
  key `(flags, fractured mods, status, item state, crafted slots, ordinary mods per side, with the metamods modelled their protected tags)`, built
  from the abstraction alone, with no walk of the concrete graph. `Pattern.key(state)` is the key; `Pattern.members(key, mode)` makes the concrete
  states of a key that an action stands for (`Pattern.mode_of`: one member for an erasing reroll, one per class for the Annulment and the bench, the
  lightest and the heaviest junk of each class for an addition, every member for the Fracturing Orb and for anything undeclared), and the model
  offers, in a key, the kernel of each such member seen through the key. Its value at a key is at most the exact cost of every state with that key
  (the module docstring has the argument for each action class). `cli/_pattern_bound.py` solves it.
  `pattern_refusal(abstraction)` is the one check of whether the bound can be built (None) or why not (a text): `Pattern` raises it, and `make_plan` asks it before any solve to route `solver="auto"` (#535).
* `Abstraction.estimate(starts, actions)` (`_estimate.py`, ADR-0023): the pilot count. The states and transitions of the
  exact graph, found with one kernel per (reroll, key) and the bench legality by sets of families and free slots; an
  `Estimate` also forecasts a coarse level (`coarsened`) and gives a closed prefix of the graph for a calibration
  solve (`first_layers`). An action with no closed form (an addition, Annulment) is walked with its real kernel on
  every state (`Estimate.walked`): `needs_walk(abstraction, actions)` says so beforehand and `ADDING_LIMIT` is the
  smaller state limit for such a walk. `EstimateRefused` is raised when a walked kernel cannot be computed.
* `Abstraction(..., reading=...)` (ticket #210): the ordinary model of one `Reading` of the rule axes the enabled actions read
  (`actions.model_readings`); every kernel is taken at it. `Abstraction.inputs(state, action)` gives the `Need`s of an action on
  the item a state stands for, and `allow_inputs=False` (the planner's) refuses an action that has some (`OutOfScopeError`).
  `Abstraction.donor_key(state, action)` is what the action reads of an input in that state (ADR-0062, ticket #214: the influences, the corruption and the influence mods of the
  donor for an action that declares `Reads.input_influenced`; ticket #217: the compressed donor without its rarity, offer and imprints for one that declares
  `Reads.input_classes`; the whole state otherwise) and `reaches_donor(action)` the want predicate built from it.
* Two-input actions that read the mods of both inputs by class (`Reads.input_classes`, the recombinator, ticket #217, ADR-0062): a junk mod is the
  kind `"~n%p"`, its family type and its place in it (the weights of the family's mods, and which one this is), and
  `kernel(state, action)` is the action run on the concrete items the item's state and the donor's state stand for, averaged over where the
  names lie (`_inputs.py`; the two inputs placed independently, uniformly, no two slots of one input in a family). The implicits and
  the quality of the chosen base are in the states and copied by the action.
* Memory Strands (ticket #277, ADR-0040, ADR-0042). `CompressedState.strands` is the item's count, exact (the spend depends on the
  exact count), kept for every item: a count that no action changes stays the start item's and adds no state, and at 0 the hash, the
  order key and the text of a state are what they were before. The items the kernel rebuilds hold the count, so an action that cuts
  draws from the pool cut at the count before the craft (`Action.cut_of`); a spending action's result (`actions.Spent`) is spread over
  the counts its spend leaves (`Spent.strands_after`, independent of the mods drawn), an Orb of Remembrance's (`actions.Recounted`) over
  the table of its new count (ticket #278), and any other result keeps the count of its retained item. The label distribution is cached by pool signature, and the signature reads the cut pool: the counts of one cut class
  share one distribution. `Abstraction(..., weights=...)` is what the kept tiers weigh in every cutting draw (`actions.cut.WeightReading`;
  the plan reading of the claim `memory_strands.weights_of_kept_tiers` by default), passed to the pool through `kept_tier_weights`. The
  pattern bound, the pilot count and the coarse state carry the count as part of `CompressedState.held`; the cut classes as coarse blocks
  are ticket #283.
* The base implicits of a corrupted item (ticket #528). `CompressedState.replaced` names the implicits of the base that no requirement
  names and that a corrupted item lost to a corrupted implicit while it holds no Eldritch implicit (the state keeps no corrupted
  implicit, ADR-0036); it is empty for every other item, and then the hash, the order key and the text of a state are what they were
  before. `_item_of` gives the base implicits by the one rule, `items.with_base_implicits`, with those it names left out.
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
(`crafted_limit_of`); `compress` refuses an item whose enchantment is another, unless an enabled action declares
`Adds.enchantment` (a finish step such as a Tempering Orb, ticket #238): then it accepts one, and the state is the same
either way. `Reads.enchantment` and `Adds.enchantment` are not `item_state`: no declaration of them makes a state hold the enchantment.
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
from ._gaps import PRUNED_CORRUPTING, PRUNED_QUALITY, Gap, ModelGaps, Prunings
from ._goal import AtLeast, Goal, ImplicitWanted, QualityWanted, Status, Wanted
from ._kernel import Abstraction, CacheStats, FamilyType, integer_weights
from ._pattern import Pattern, PatternKey, PatternModel, PatternOffer, PatternStats, build_pattern_model, pattern_refusal
from ._state import CompressedState, Flags, FracturedMod, ImplicitSide, OfferedMod, Slot, status_of

__all__ = [
    "ADDING_LIMIT",
    "PRUNED_CORRUPTING",
    "PRUNED_QUALITY",
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
    "Gap",
    "Flags",
    "FracturedMod",
    "ImplicitSide",
    "ImplicitWanted",
    "ModelGaps",
    "Prunings",
    "QualityWanted",
    "OfferedMod",
    "Pattern",
    "PatternKey",
    "PatternModel",
    "PatternOffer",
    "PatternStats",
    "Slot",
    "Goal",
    "Status",
    "Wanted",
    "integer_weights",
    "keeps_shape",
    "reach_bound",
    "status_of",
    "BlockHoldsMetamod",
    "build_pattern_model",
    "pattern_refusal",
    "needs_walk",
]
