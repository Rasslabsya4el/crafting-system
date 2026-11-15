"""The crafted pattern: the key of a state and the optimistic model of the key, built from the abstraction alone (ticket #497, research #376).

A **pattern** is a function of the state. The **key** of this module is `(flags, fractured mods, status of the wanted mods, the item state beyond
the mods, the crafted slots, the ordinary mods per side)`, and with the metamods modelled also the **protected tags** of the ordinary mods per
side (`PatternKey`). The **optimistic model** of the key has one abstract state per key and, in it, the actions of the concrete states that have
it, seen through the key. A concrete policy is a policy of that model (it takes the action of the member it is in), so its optimal value never
exceeds the exact value of a member: `V_key(key(s)) <= V*(s)`. Research #376 measured this bound on the walked graphs (99.48% of the exact cost
on R04, 98.10% on R14, 99.99% with the tags, 100% on S02). This module builds the same model **without the walk**: `members(key, mode)`
makes the concrete states of a key from the key alone, `Pattern.expand` offers the kernels of those members, and `build_pattern_model` explores
the keys from the start key.

Admissible by construction (an action offered in a key is at least as good as the action of every concrete state of the key, for any values of
the successor keys; costs are the offers' own, the same for every member; no outcome is dropped, because the kernel of a member is the exact
kernel of `Abstraction`, pushed through the key, and chances that fall in one key add). What has to be argued is that the members offered
stand for all the members. The members of a key are the states with that key, and their ordinary mods differ in two ways.

* **Which goal-relevant mods they hold.** An ordinary slot is *relevant* unless its kind is a family type `~n` none of whose mods gives the
  goal anything ("pure junk"); relevant slots (those that give a leaf something, those of a family type that has such a mod, and the families an
  enabled action names) are enumerated exactly: every multiset consistent with the status, the counts and the tags. Nothing is assumed of them.
* **Which pure junk they hold.** A pure junk slot of side `s` and tag set `T` (its *class*) stands for one family of a family type of that class.
  The classes' counts are in the key (with the tags in it) or enumerated (without). Within a class the members differ in which types they hold,
  and so in the pool weight `H_c` the held families take out of the pool.

The member policy of an action (`Pattern.mode_of`) says which pure junk assignments are offered, and is the soundness argument of the action
class. In the notation `V` is any value of the successor keys and `backup_m(V)` is the chance-weighted sum for the member `m`:

* `ANY` (one member): an erasing reroll that reads no junk (Chaos, Alteration, Transmutation, an essence, a Harvest reforge), when the key holds
  no lock. Its outcome is a function of the flags, the fractured mods, the crafted slots and the item state (the pool excludes the fractured
  families only; the other mods are erased), all in the key (ADR-0023, "block-invariant", checked on the fixtures by the contract suite).
  **Proved** by the same argument as ADR-0023; with a lock it is not (the locked side keeps its junk through a reroll, the draw excludes
  those families, and several mods are drawn: the chance is a product of ratios, not a linear-fractional function), so a key that holds a lock
  uses `ALL`.
* `ONE` (one member for each relevant multiset and class composition): an action that reads the junk but is declared block-invariant and reads
  no pool weight (a bench craft, Remove Crafted Mods, the Annulment). Bench crafts read the families they name (relevant kinds, enumerated);
  Remove Crafted Mods reads nothing of the junk; the Annulment removes one removable slot uniformly, and the removable slots are counted by
  class (the tags are in the key, or the compositions are enumerated), so its pushed kernel is the same for every assignment of the pure junk
  of a class: the chance of a successor key is `(removable slots that lead to it) / (removable slots)`. **Proved** for the Annulment under
  protected tags when the tags are in the key or enumerated (an Attack/Caster metamod keeps the protected-tag slots out of the candidates, and
  that is a function of the class); the locked side is kept (a lock in the key makes the mode `ALL`).
  A reroll of values in place that reads nothing of the junk but its count (`Reads.rerolls_values`, a Divine Orb; #830) is `ONE` too: it keeps
  every slot and draws a new roll for each slot whose mod a roll limit tells apart. Those are relevant slots (a rollable mod is the kind
  `$<mod id>` and gives its leaf BELOW or PASSING, never nothing), enumerated exactly; a pure junk slot gives the goal nothing at any roll, so
  its roll is not in the state and it stays as it is. Its refusals read the rarity and whether a changeable mod is held, both functions of the
  key. So its pushed kernel is the same for every pure junk assignment. **Proved** so, and checked against every member on the fixtures
  (`tests/test_pattern_rolls.py`); under a lock the locked side keeps its rolls and the mode is `ALL`.
  The unveil, the picks and the Veiled Exalted Orb (#828) are `ONE` too, a lock or not, with the folded families of "The folded families"
  below. Each reads of the junk its count and the families it names (the unveiled pool's: told apart by name; a pure junk family type that
  holds a mod of one, a hybrid whose family key is not that family alone, makes the policy `ALL`, `Pattern._pure_holds`; 3.29.3.3 has none) and
  keeps the rest (`Reads.junk`, `Reads.families`). The unveil draws the offer from the unveiled pool less the families on the item, and a pick
  puts the k-th mod of the offer in place of the placeholder, refused when its family is on the item: both read only named families and the key
  (the placeholder, the offer, a lock), and change no ordinary slot. The Veiled Exalted Orb removes one removable slot uniformly (the locked side
  and the fractured mods are not removable, every other slot is, whatever its tags) and puts a placeholder on the side with room: the removable
  slots are counted by class, so the chance of a successor key is `(removable slots of that class) / (removable slots)`; it is refused when the
  key holds a veiled mod. **Proved** so, and checked against every member on the fixtures (`tests/test_pattern_veiled.py`).
* `ANY` for an action the abstraction gives a view of the item without its ordinary slots (`Abstraction._erases`: the action reads no junk and
  no lock keeps a side), whether or not it declares block invariance (the Veiled Chaos Orb, #828): every member has the same view, so the same
  kernel and the same refusals. **Proved** by the construction of the kernel (#827), not by a declaration.
* `EXTREMES` (the lightest and the heaviest assignment in each class that holds pure junk): an addition that keeps the mods (`Reads.variants`:
  Augmentation, Regal, Exalted; one mod drawn). The chance of a successor key is `(a + sum_c b_c H_c) / (W - H_rel - sum_c H_c)` with `H_c` the
  pool weight (under the protected tags the key's metamods impose) the held pure junk of class `c` takes out, `H_rel` that of the relevant slots
  (the same for every assignment) and `W` the pool total: a drawn pure junk mod of class `c'` lands in the same successor key whichever of its
  types it is, and the chance of that is `(W_c' - H_c') / (W - H)`. A linear-fractional function with a positive denominator is quasi-linear,
  so the least and the greatest backup over a box of `H_c` are reached at its corners; the achievable `H` vector is a subset of the box whose
  corners are achievable (the lightest and the heaviest fill of each class, independently), so the least backup over all members is reached at
  an offered one. **Proved for a single draw** (ADR-0023); **extended here to the protected tags** (the draw excludes the mods of the blocked
  tags and the held families take out their eligible weight) and checked against all members on the fixtures. A corner that two classes make
  impossible together (one family type shared by two tag kinds) is not offered: the key then falls back to `ALL`.
  An action that draws by tag or by item level (`Reads.draw_tags`, `Reads.draw_levels`) makes the family types differ by more than weight: `ALL`.
* `ALL` (every pure junk assignment): the Fracturing Orb (the successor key holds the type of the mod fractured, a function of which types the
  member holds: not of the weights), any action that is not declared one of the above, and an erasing reroll under a lock. **Unproved to be
  cheaper, and exact by construction.**

Every member offered is checked to be an item (`Abstraction._item_of`), so a member that no item has is never offered.

**The veiled slots (#828, ADR-0026).** The veiled placeholder and the mods unveiled from the pool (the kinds `VeiledPrefix`, `VeiledSuffix` and
`^<family>`) are held by the key exactly, as the crafted slots are (`PatternKey.veiled`), and are left out of its counts and tags; the universe
holds none of them, so a member holds the key's veiled slots and no other (never a double veil, which every veiled action refuses as a model
gap). The offer of an unveil is in the key's `held`, whole: the k-th mod is the one `Pick(k)` takes. The unveil's backup in the model is then
the expectation, over the offers, of the least backup of the picks at each offer key: a minimum inside the expectation, as in the exact graph.

**The folded families (#828).** The unveil and the picks name every family of the unveiled pool, so the abstraction tells apart by name each
ordinary family the unveiled pool shares (on the Warstaff of R24, 12 of the 33 ordinary families: attack speed, strength, physical damage, ...).
Held as relevant slots, those would be enumerated exactly in every key, for every action: about 244 members a key for an Exalted Orb where the
family types give a few. A family is *folded* (`Pattern._folded`) when only the veiled actions name it: no other enabled action that reads
the junk does, and none reads every family. A folded family that gives the goal nothing is pure junk of its class (side, tags), a type of one
family (`_PureType.named`), and its slots are left out of the relevant multisets. The key does not change: it counts the ordinary slots by
class already. What has to be argued is each action's policy with folded families among the pure junk.

* The actions that do not name a folded family (every action but the unveil and the picks, by the definition) see a folded family as a family
  type of one family. `ANY` and `ONE` read no pure junk but its count and class, so they hold as they did. `EXTREMES` holds as above: a folded
  family has the weight of its mods in the pool like a type, a drawn mod of it is pure junk of its class in the successor key, and the box of
  `H_c` keeps its corners (a type of capacity one is filled or not). The Veiled Exalted Orb names them, but reads no ordinary slot by family:
  its refusal reads the veiled slots, which the key holds, and its removal is uniform over the removable slots. `ALL` makes every assignment.
* The unveil and the picks read them, and only where they are live (`Pattern.named_of`, the members `Pattern.members(key, ONE, named)`).
  Both need the placeholder: at a key without it each is refused at every member, by the key. At a key with the placeholder and an offer, the
  unveil is refused at every member (the offer is drawn once), and a pick reads, of the ordinary slots, whether one shares a family with the
  mod it takes: `named` is the offer's families. At a key with the placeholder and no offer, the picks are refused at every member, and the
  unveil reads which families of the unveiled pool the item holds: `named` is every folded family it names. Those members are every way the
  pure junk of each class holds the folded families of `named` (each within its capacity), the other slots the lightest fill of the other kinds
  (`_named_fills`), and the kernel of the action at a member is a function of the key, the relevant slots and the folded families of `named`
  it holds: a family type's representative is never a family the abstraction tells apart by name (`Kinds._members_of`), and the action reads
  nothing else of the junk. So every member's kernel is the kernel of an offered member. **Proved** so.

Every member of a key is then matched, for each action, by an offered member with the same pushed kernel or one whose least backup is no
higher, and the induction of the first paragraph gives `V_key(key(s)) <= V*(s)`: the bound stays a lower bound. Checked against every member of
the walked keys and against the exact graph's values, with and without a lock, on the fixture of `tests/test_pattern_veiled.py`.

**Refusals.** An action that the game forbids at a member (`NotApplicableError`) is not an action of that member and is left out
of it. An action that raises a model gap at a member (`OutOfScopeError`: no admitted rule covers the item) is left out only when
no member of the key can take it (each is a game refusal or a gap: the exact model has no action at any state of the key, as the walk and the
planner treat a gap as unavailable). If another member can take it, the build refuses and names the offer and the key: the exact model drops
the action only at the states where the gap is, so leaving it out of the key could put the bound above the exact cost (`_gap_everywhere`). A
model gap in `_item_of` always refuses.

**The universe.** The members of a key are made of the ordinary slots an item can hold. They come from three places: the pool of an empty rare
item (every mod a draw can give, under a roll limit once for each outcome of its roll, #830; the pure junk types are made of these), what an offered action adds by name (`Adds.named`: an essence's forced
mod, which the pool does not list; `Universe._seed_named`), and every slot a kernel the build evaluates produces (`note`; a slot found this way
that the two others missed starts the build again on the grown universe, `stats.universe_growth`). A slot that a non-offered member's kernel would produce, and no
offered member's, cannot be one of the first two: a draw gives a mod of the pool, and a forced mod is the same at every member. What is left is
a draw from a pool wider than the empty rare item's (a fossil's added mods) at a member that is not offered, which `Adds` does not name: the
universe may miss that slot, and the members that hold it are not made (issue #520). No route of the benchmark has such an action.
"""

import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Sequence
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from enum import StrEnum
from fractions import Fraction
from functools import reduce
from itertools import product
from math import gcd, lcm
from typing import NamedTuple

from crafting_system.actions import BLOCKED_TAG, Action, NotApplicableError, OutOfScopeError, Reads, allowed_by_tags
from crafting_system.data import Mod
from crafting_system.items import Item, ItemError, Metamod, Rarity, Side
from crafting_system.items.model import VEILED_DOMAIN

from ._goal import Status
from ._kernel import Abstraction
from ._kinds import ALIKE, MOD_PREFIX, TYPE_PREFIX, UNVEILED_PREFIX, kind_families, kind_tags
from ._rolls import is_rollable
from ._state import CompressedState, Slot, best_of

# The two families of refusal an action raises (`actions/errors.py`, #506). A game refusal (`NotApplicableError`: the game forbids the action on that
# item) may drop the action at a member: it is not an action there. A model gap (`OutOfScopeError`: no admitted rule covers the item) may not: at a
# member that is not a state of the route it says nothing about the states that are, and dropping the action from the key could put the bound
# above the exact cost. The build refuses and says why. The clauses name the families themselves (`tests/test_cli_model_gaps.py` scans for them).

SINK = -1  # the successor of the mass an approximate kernel does not account for: a state that costs nothing (the goal)
SHRINK = Fraction(2**30 - 1, 2**30)  # every chance of a float kernel is taken this much lower; the float error is 1e-13, so no chance is above its exact one
PRIME_FROM = 16  # a key that is given at least this many offers at once primes their distributions in a process pool (fewer cost more in forks than they save: R14, 11 offers), in chunks of ...
PRIME_CHUNK = 32  # ... this many offers (the net is asked between two chunks)
POLL_SECONDS = 0.5  # how often a build asks its net (a clock and a memory read, cheap beside one offer)
SIDES = (Side.PREFIX, Side.SUFFIX)
LOCKS = frozenset({Metamod.PREFIXES_CANNOT_CHANGE.value, Metamod.SUFFIXES_CANNOT_CHANGE.value})
TAG_OF_METAMOD = {metamod.value: tag for metamod, tag in BLOCKED_TAG.items()}
COUNT_ONLY = Reads(junk=True, families=frozenset())  # what an action reads of the junk when it reads its count alone (Remove Crafted Mods, and a Divine Orb besides the rolls)


class Mode(StrEnum):
    """Which members of a key an action is offered at (see the module docstring)."""

    ANY = "any"
    ONE = "one"
    EXTREMES = "extremes"
    ALL = "all"


class PatternKey(NamedTuple):
    """The pattern of a state: what the optimistic model tells states apart by."""

    flags: object
    fractured: tuple
    status: tuple
    held: tuple
    crafted: tuple
    counts: tuple  # the ordinary (not crafted, not veiled) slots per side: (prefix, suffix)
    tags: tuple | None  # ((side index, protected tags), count) of the ordinary slots, or None when the key carries no tags
    veiled: tuple = ()  # the veiled placeholder and the mods unveiled from the pool, as slots, exactly (#828): never a member's choice


@dataclass(frozen=True)
class _PureType:
    """A family type none of whose mods gives the goal anything: `capacity` families of one `weight`, on a side.

    A folded family (`named` not empty, #828) is a family that only the veiled actions tell apart by name: one family, `capacity` 1, held
    among the pure junk of its class; `named` are its families, which an unveil or a pick live at a key enumerates (`Pattern.named_of`).
    """

    side: Side
    base: str
    capacity: int
    mods: tuple[Mod, ...]  # the mods of one family of the type, with the weight they have in the pool
    weights: tuple[Fraction, ...]
    named: frozenset[str] = frozenset()  # the families of a folded family; empty for a family type ("~n")

    def weight(self, blocked: frozenset[str]) -> Fraction:
        """The pool weight a family of this type takes out of a draw under the metamods that block `blocked` tags."""
        return sum((w for mod, w in zip(self.mods, self.weights) if allowed_by_tags(mod, blocked)), Fraction(0))


@dataclass(frozen=True)
class _PureKind:
    kind: str
    slot: Slot
    type: _PureType


class _Universe:
    """The ordinary slots an item with given influences can hold, split into relevant slots and pure junk kinds."""

    def __init__(self, pattern: "Pattern", influences: frozenset):
        ab = pattern.ab
        context = ab._context(influences)
        kinds = context.kinds
        zero = pattern.zero
        self.relevant: dict[Side, dict[Slot, None]] = {side: {} for side in SIDES}
        self.pure: dict[Side, dict[str, _PureType]] = {side: {} for side in SIDES}
        self.classes: dict[Side, dict[tuple, list[_PureKind]]] = {side: defaultdict(list) for side in SIDES}
        by_type: dict[tuple[Side, str], list] = defaultdict(list)  # (side, type kind) -> [(family, mod, slot)]
        for family in kinds._pool() if kinds.tracked else ():  # a state that keeps no junk holds no ordinary slot
            for entry in family.mods:
                kind = kinds.of(entry.mod)
                for contribution in _rolled_contributions(ab, entry.mod, influences):
                    by_type[(family.side, _base(kind))].append((family, entry.mod, Slot(family.side, kind, contribution)))
        folded = self.folded = pattern._folded(kinds)
        for (side, base), rows in by_type.items():
            silent = all(all(value is Status.ABSENT for value in slot.contribution) for _, _, slot in rows)
            named = _foldable(base, folded) if silent else frozenset()
            if not (silent and (base.startswith(TYPE_PREFIX) or named)):
                for _, _, slot in rows:
                    self.relevant[side][slot] = None
                continue
            families = {family.family: family for family, _, _ in rows}
            first = next(iter(families.values()))  # the families of one type have the same mods and weights (the type is made of them)
            kind_type = _PureType(
                side, base, len(families), tuple(entry.mod for entry in first.mods), tuple(entry.weight for entry in first.mods), named
            )
            self.pure[side][base] = kind_type
            for kind in sorted({slot.kind for _, _, slot in rows}):
                self.classes[side][_tagset(kind)].append(_PureKind(kind, Slot(side, kind, zero), kind_type))
        self.zero = zero
        self.influences = influences
        self.kinds = kinds
        self._seed_named(pattern, pattern.actions)

    def _seed_named(self, pattern: "Pattern", actions: Sequence[Action]) -> int:
        """Add the ordinary mods an offered action puts on the item by name and that the pool does not list (an essence's forced mod).

        `Adds.named` is the same on every use, so the slot is known before any kernel is run; this is what keeps a slot that only a member that
        is not offered would have produced from missing (see the module docstring, "The universe"). Returns how many slots the universe gained.
        """
        ab = pattern.ab
        influences, kinds = self.influences, self.kinds
        gained = 0
        probe = Item.build(ab.data, base_id=ab.base_id, item_level=ab.item_level, rarity=Rarity.RARE, influences=influences)
        for action in actions:
            try:
                adds = action.adds(ab.data, probe)
            except NotApplicableError:
                continue
            if adds.crafted:
                continue
            for mod_id in adds.named or ():
                mod = ab.data.mods.get(mod_id)
                if mod is None or mod.domain == "crafted" or mod.generation_type not in (side.value for side in SIDES):
                    continue
                gained += self.note(Slot(Side(mod.generation_type), kinds.of(mod), ab._drawn_contribution(mod, False, influences)))
        return gained

    def note(self, slot: Slot) -> bool:
        """Add a slot a kernel produced that the pool did not list; True when the universe grew."""
        if slot.crafted or slot.side not in self.relevant:
            return False
        base = _base(slot.kind)
        known_pure = self.pure[slot.side].get(base)
        if known_pure is not None and all(value is Status.ABSENT for value in slot.contribution):
            if any(item.kind == slot.kind for item in self.classes[slot.side][_tagset(slot.kind)]):
                return False
            self.classes[slot.side][_tagset(slot.kind)].append(_PureKind(slot.kind, Slot(slot.side, slot.kind, self.zero), known_pure))
            return True
        if slot in self.relevant[slot.side]:
            return False
        self.relevant[slot.side][slot] = None
        return True


def _rolled_contributions(ab: Abstraction, mod: Mod, influences: frozenset) -> list[tuple[Status, ...]]:
    """What a drawn `mod` can give the goal: at its low rolls, and, under a roll limit that its values decide, every outcome of its law (#830).

    A slot holds what its mod gives each leaf as it rolled, so a rollable mod is a slot for each outcome of its roll law (`_rolls.roll_law`;
    a reroll of values in place moves a slot between them). Without the outcomes here the universe would learn them from the kernels only, and
    each one learnt so begins the build again.
    """
    low = ab._drawn_contribution(mod, False, influences)
    if not ab._has_laws:
        return [low]
    cells = ab._law(mod, influences)
    if not is_rollable(cells):
        return [low]
    return list(dict.fromkeys([low, *(tuple(Status(value) for value in ints) for ints, _ in cells)]))


def _base(kind: str) -> str:
    from ._kinds import base_kind

    return base_kind(kind)


def _foldable(base: str, folded: frozenset[str]) -> frozenset[str]:
    """The families of a kind told apart by name that only the veiled actions read (`Pattern._folded`), or none for any other kind (#828)."""
    if not folded or base == ALIKE or base.startswith((TYPE_PREFIX, MOD_PREFIX, UNVEILED_PREFIX)):
        return frozenset()
    families = frozenset(kind_families(base))
    return families if families <= folded else frozenset()


def _placeholder_families(data) -> frozenset[str]:
    """The families of the veiled placeholders (domain `veiled`): the kind of a placeholder slot is its family key (`_kinds.Kinds.of`)."""
    return frozenset(family for mod in data.mods.values() if mod.domain == VEILED_DOMAIN for family in mod.families)


def _tagset(kind: str) -> tuple:
    return tuple(sorted(kind_tags(kind)))


def _slot_key(slot: Slot):
    return slot.key


@dataclass
class PatternStats:
    """What a build did, for the report (ticket #497: kernels evaluated against the walk's, time, memory)."""

    keys: int = 0
    goal_keys: int = 0
    members: int = 0  # concrete states offered an action, over all keys and modes (a member counted once per mode)
    pairs: int = 0  # (member, action) pairs whose kernel key was asked for
    kernels: int = 0  # distinct kernels computed (the walk's count is its distinct `kernel_key`s)
    abstract_actions: int = 0
    abstract_edges: int = 0
    refused_pairs: int = 0
    gap_pairs: int = 0  # pairs left out because the action is a model gap at every member of the key that is not a game refusal
    universe_growth: int = 0
    modes: Counter = field(default_factory=Counter)  # (member mode, label of the offer) -> keys it was expanded at
    seconds: float = 0.0
    fallbacks: int = 0  # keys whose extremes were impossible and used every member


@dataclass
class PatternModel:
    """The optimistic model of the key: state 0 is the start key; `actions[k]` are `(offer index, kernel id)` of key `k`."""

    keys: list[PatternKey]
    goal: list[bool]
    actions: list[list[tuple[int, int]]]
    kernels: list[tuple[tuple[int, ...], tuple[int, ...]]]  # (successor keys, integer weights)
    stats: PatternStats
    index: dict[PatternKey, int]
    expanded: list[bool] = field(default_factory=list)  # key -> whether its actions were built; a key the build did not reach is a tip (no actions, not a dead end)
    stopped: str | None = None  # why the build ended before every key was expanded (a net), None for a complete model


def pattern_refusal(abstraction: Abstraction) -> str | None:
    """Why the crafted-pattern bound cannot be built for `abstraction`, or None when it can (#497, #507).

    The one place that decides it: `Pattern.__init__` raises `OutOfScopeError` with this text, and `make_plan` asks it before any solve, so
    `solver="auto"` knows whether the envelope search is possible without starting it. The bound has no members for an enabled action that
    reads the imprints. A roll limit and a reroll of values have members since #830: the key's status holds what each wanted mod gives its leaf
    as it rolled, and a Divine Orb is an action of the model (`Pattern.mode_of`). The unveil offer has since #828: the key holds the veiled slots
    and the offer, and the veiled actions have member policies.
    """
    causes = refusal_causes(abstraction)
    if not causes:
        return None
    return f"the crafted-pattern bound has no members for it: {'; '.join(causes)} (#497)"


# what the bound has no members for: the abstraction's attribute, the cause in the refusal's text, and in a player's words where those differ
_CAUSES = (
    ("tracks_imprints", "an offered action reads the imprints", None),
)


def refusal_causes(abstraction: Abstraction, player: bool = False) -> tuple[str, ...]:
    """What of `abstraction` the crafted-pattern bound has no members for; empty when the bound can be built. `player`: each cause in the words
    an answer may show (`make_plan` says them when a net stops the walk that `solver="auto"` takes instead of the envelope search, #926)."""
    return tuple(shown if player and shown else text for name, text, shown in _CAUSES if getattr(abstraction, name))


class Pattern:
    """The key of a state and the members of a key, for one `Abstraction`.

    `tags` says whether the key carries the protected tags of the ordinary mods; it defaults to whether the abstraction models the metamods.
    Raises `OutOfScopeError` for an abstraction whose slots the key cannot yet enumerate: an enabled action that reads the imprints.
    """

    def __init__(self, abstraction: Abstraction, tags: bool | None = None, actions: Sequence[Action] = ()):
        refusal = pattern_refusal(abstraction)
        if refusal is not None:
            raise OutOfScopeError(refusal)
        self.ab = abstraction
        self.data = abstraction.data
        self.actions = tuple(actions)  # the offered actions: what they add by name joins the universe of slots
        self.tags = abstraction.models_metamods if tags is None else tags
        self.width = len(abstraction.goal.leaves)
        self.zero = (Status.ABSENT,) * self.width
        self._universes: dict[frozenset, _Universe] = {}
        self._reads: dict[Action, object] = {}
        self._feasible: dict[CompressedState, bool] = {}
        self._tag_kind: dict[str, tuple] = {}
        self._veiled_kind: dict[str, bool] = {}
        self._pure_reads: dict[tuple, bool] = {}
        self._placeholder_families = _placeholder_families(abstraction.data)
        self.grew = 0
        self.fallbacks = 0

    def keep_universes(self, before: "Pattern") -> None:
        """Take the universes of `before` (the slots its kernels found included), seeded with what this pattern's actions add by name."""
        for influences, universe in before._universes.items():
            self._universes[influences] = universe
            universe._seed_named(self, self.actions)

    def add_actions(self, actions: Sequence[Action]) -> None:
        """Offer more actions: what they add by name joins the universe, and a universe that gains a slot counts as growth (`grew`), as a kernel's slot does."""
        self.actions = (*self.actions, *actions)
        for universe in self._universes.values():
            self.grew += universe._seed_named(self, actions)

    # ---- the key ----------------------------------------------------------------------------------------------

    def key(self, state: CompressedState) -> PatternKey:
        counts = [0, 0]
        crafted = []
        veiled = []
        tags: Counter | None = Counter() if self.tags else None
        for slot in state.slots:
            if slot.crafted:
                crafted.append(slot)
                continue
            if self.is_veiled(slot):
                veiled.append(slot)
                continue
            side = 0 if slot.side is Side.PREFIX else 1
            counts[side] += 1
            if tags is not None:
                tagset = self._tag_kind.get(slot.kind)
                if tagset is None:
                    tagset = self._tag_kind[slot.kind] = _tagset(slot.kind)
                tags[(side, tagset)] += 1
        return PatternKey(
            state.flags, state.fractured, state.status, state.held, tuple(crafted), (counts[0], counts[1]),
            tuple(sorted(tags.items())) if tags is not None else None, tuple(veiled),
        )

    def is_veiled(self, slot: Slot) -> bool:
        """Whether an ordinary slot is the veiled placeholder or a mod unveiled from the pool (ADR-0026): a slot the key holds exactly (#828)."""
        found = self._veiled_kind.get(slot.kind)
        if found is None:
            base = _base(slot.kind)
            if base.startswith(UNVEILED_PREFIX):
                found = True
            elif base.startswith((TYPE_PREFIX, MOD_PREFIX)):  # a family type or one mod of the ordinary pool: never a placeholder
                found = False
            else:
                found = bool(kind_families(base) & self._placeholder_families)
            self._veiled_kind[slot.kind] = found
        return found

    def _pure_holds(self, influences: frozenset, families: frozenset[str]) -> bool:
        """Whether a pure junk type of the universe has a mod of one of `families` (a hybrid mod whose family key is not one of them alone).

        The member policy `ONE` of the veiled actions rests on the families they read being told apart by name; a pure junk slot of such a type
        could change their kernel between the members of a class, so the policy is then `ALL`. The data of 3.29.3.3 has no such mod.
        """
        found = self._pure_reads.get((influences, families))
        if found is None:
            universe = self.universe(influences)
            found = self._pure_reads[(influences, families)] = any(
                set(mod.families) & families
                for side in SIDES
                for kind_type in universe.pure[side].values()
                if not kind_type.named  # a folded family is told apart by name: `named_of` enumerates it where it is read
                for mod in kind_type.mods
            )
        return found

    def _veiled_reader(self, reads) -> bool:
        """Whether an action reads the junk as the unveil, the picks and the Veiled Exalted Orb do (#828): its count, and families it names of
        which the veiled ones are a part (or an offer), and nothing else (no draw, no weight, no reroll of values: those have policies of their own)."""
        others = reads.variants or reads.pool_weight or reads.fractures or reads.input_classes or reads.rerolls_values or reads.block_invariant
        return bool(
            reads.junk and reads.families is not None and not others and (reads.offer or reads.families & self._placeholder_families)
        )

    def _folded(self, kinds) -> frozenset[str]:
        """The families told apart by name only because a veiled action names them (#828): no other enabled action that reads the junk names
        them, and none reads every family. A folded family that gives the goal nothing is pure junk of its class (`_Universe`), not a relevant
        slot: an unveil and a pick enumerate it where they are live (`named_of`), the other actions do not read it (see the module docstring)."""
        veiled: set[str] = set()
        other: set[str] = set()
        for action in kinds.actions:
            reads = self.reads(action)
            if not reads.junk:
                continue
            if reads.families is None:
                return frozenset()
            (veiled if self._veiled_reader(reads) else other).update(reads.families)
        return frozenset(veiled - other - self._placeholder_families)

    def holds_placeholder(self, key: PatternKey) -> bool:
        """Whether the key holds the veiled placeholder (not a mod unveiled from the pool)."""
        return any(
            not _base(slot.kind).startswith(UNVEILED_PREFIX) and kind_families(_base(slot.kind)) & self._placeholder_families for slot in key.veiled
        )

    def named_of(self, action: Action, key: PatternKey) -> frozenset[str]:
        """The folded families whose holding the members of `key` must tell apart for `action` (#828): empty but for an unveil or a pick that is
        live at the key, see the module docstring ("The folded families").

        An action that reads the offer and needs the placeholder (an unveil, a pick) is refused at every member of a key without the placeholder.
        With an offer drawn, the unveil is refused at every member and a pick reads, of the ordinary slots, only whether one shares a family with
        the mod it takes: the offer's families. With no offer, the picks are refused at every member and the unveil reads which families of the
        unveiled pool the item holds: all it names. The Veiled Exalted Orb reads no ordinary family (its refusal reads the veiled slots alone).
        """
        reads = self.reads(action)
        if not (reads.offer and self._veiled_reader(reads)) or not self.holds_placeholder(key):
            return frozenset()
        folded = self.universe(key.flags.influences).folded
        if not folded:
            return frozenset()
        offer = CompressedState(key.flags, key.fractured, key.status, (), *key.held).offer
        if offer:
            return frozenset(family for entry in offer for family in self.data.mods[entry.mod_id].families) & folded
        return frozenset(reads.families) & folded

    def universe(self, influences: frozenset) -> _Universe:
        found = self._universes.get(influences)
        if found is None:
            found = self._universes[influences] = _Universe(self, influences)
        return found

    def note(self, state: CompressedState) -> None:
        """Learn the ordinary slots of a state a kernel produced (the pool may not list them)."""
        universe = self.universe(state.flags.influences)
        for slot in state.slots:
            if not slot.crafted and not self.is_veiled(slot) and universe.note(slot):  # a veiled slot is in the key, never a member's choice
                self.grew += 1

    # ---- the member policy of an action -----------------------------------------------------------------------

    def reads(self, action: Action):
        found = self._reads.get(action)
        if found is None:
            found = self._reads[action] = action.reads(self.data)
        return found

    def holds_lock(self, key: PatternKey) -> bool:
        """Whether the key holds a lock (`Prefixes` / `Suffixes Cannot Be Changed`), crafted or fractured: a reroll then keeps the locked side."""
        mods = self.data.mods
        ids = [slot.kind for slot in key.crafted] + [entry.mod_id for entry in key.fractured]
        return any(mod_id in mods and LOCKS & set(mods[mod_id].families) for mod_id in ids)

    def blocked_tags(self, key: PatternKey) -> frozenset[str]:
        """The tags the key's Attack and Caster metamods keep out of a draw and out of an Annulment."""
        mods = self.data.mods
        ids = [slot.kind for slot in key.crafted] + [entry.mod_id for entry in key.fractured]
        return frozenset(TAG_OF_METAMOD[family] for mod_id in ids if mod_id in mods for family in mods[mod_id].families if family in TAG_OF_METAMOD)

    def mode_of(self, action: Action, key: PatternKey) -> Mode:
        reads = self.reads(action)
        kinds = self.ab._context(key.flags.influences).kinds
        if reads.variants and reads.junk and reads.pool_weight and not reads.fractures:
            return Mode.ALL if kinds._tagged or kinds._levels else Mode.EXTREMES
        others = reads.variants or reads.pool_weight or reads.fractures or reads.input_classes
        if reads.block_invariant and not (others or reads.rerolls_values):
            if self.holds_lock(key):
                return Mode.ALL
            return Mode.ONE if reads.junk else Mode.ANY
        if reads.rerolls_values and replace(reads, rerolls_values=False) == COUNT_ONLY:
            # a reroll of values in place that reads nothing else of the junk than its count (a Divine Orb, #830): see the module text, `ONE`
            return Mode.ALL if self.holds_lock(key) else Mode.ONE
        if others or reads.rerolls_values:
            return Mode.ALL
        if not reads.junk and self._erases(action, key):
            # the abstraction gives the action a view of the item without its ordinary slots (a Veiled Chaos Orb, #828): see the module text, `ANY`
            return Mode.ANY
        if self._veiled_reader(reads):
            # an unveil, a pick, a Veiled Exalted Orb (#828): see the module text, `ONE` (with the folded families `named_of` gives), unless a
            # pure junk family type holds a family they read
            return Mode.ALL if self._pure_holds(key.flags.influences, reads.families) else Mode.ONE
        return Mode.ALL

    def policy(self, action: Action, key: PatternKey) -> tuple[Mode, frozenset[str]]:
        """The member policy of `action` at `key`: its mode, and the folded families its members must tell apart (`named_of`, with `ONE`)."""
        mode = self.mode_of(action, key)
        return mode, self.named_of(action, key) if mode is Mode.ONE else frozenset()

    def _erases(self, action: Action, key: PatternKey) -> bool:
        """Whether the abstraction makes the kernel of `action` at the members of `key` from a view without their ordinary slots (`Abstraction._erases`):
        it reads the lock from the crafted and the fractured mods alone, which the key holds."""
        probe = CompressedState(key.flags, key.fractured, key.status, tuple(key.crafted), *key.held)
        return self.ab._erases(probe, action)

    # ---- the members of a key ---------------------------------------------------------------------------------

    def members(self, key: PatternKey, mode: Mode, named: frozenset[str] = frozenset()) -> list[CompressedState]:
        """The concrete states of `key` that stand for all of its members for an action of the policy `mode`; each is an item.

        `named` (with `ONE`): the folded families the action reads at this key (`named_of`): every way the pure junk holds them is a member.
        """
        if not self.ab._context(key.flags.influences).kinds.tracked:
            # no enabled action reads the junk, so a state keeps none of it: its status is a fact about mods that are not stored, and the one
            # state the key stands for is the key itself (no ordinary slot to choose, nothing to check the status against)
            only = CompressedState(key.flags, key.fractured, key.status, tuple(sorted((*key.crafted, *key.veiled), key=_slot_key)), *key.held)
            return [only] if self._ok(only) else []
        universe = self.universe(key.flags.influences)
        blocked = self.blocked_tags(key)
        base = best_of(self.width, [slot.contribution for slot in (*key.crafted, *key.veiled)] + [entry.contribution for entry in key.fractured])
        found: dict[CompressedState, None] = {}
        for rel_p, rel_s in product(
            self._relevant(universe, Side.PREFIX, key.counts[0], key.status), self._relevant(universe, Side.SUFFIX, key.counts[1], key.status)
        ):
            relevant = rel_p + rel_s
            if best_of(self.width, [slot.contribution for slot in relevant] + [base]) != key.status:
                continue
            for compositions in self._compositions(universe, key, rel_p, rel_s):
                for state in self._assemble(universe, key, relevant, compositions, blocked, mode, named):
                    found[state] = None
                if mode is Mode.ANY and found:
                    return list(found)
        return list(found)

    def _relevant(self, universe: _Universe, side: Side, count: int, status: tuple) -> list[tuple[Slot, ...]]:
        """Every multiset of at most `count` relevant slots of `side` that none of its slots exceeds `status` in.

        Two slots that each stand for one mod (`$<mod id>`) of a shared family are never on one item, so no multiset holds them both: `_ok` would
        refuse every state made of it, and under a roll limit there are many (one slot per tier and per outcome of its roll, #830).
        """
        pool = sorted(
            (slot for slot in universe.relevant[side] if all(c <= s for c, s in zip(slot.contribution, status))), key=_slot_key
        )
        families = [self._families_of(slot) for slot in pool]
        out: list[tuple[Slot, ...]] = []

        def grow(start: int, chosen: tuple[Slot, ...], held: frozenset[str]) -> None:
            out.append(chosen)
            if len(chosen) == count:
                return
            for at in range(start, len(pool)):
                own = families[at]
                if own & held:
                    continue
                grow(at, (*chosen, pool[at]), held | own)

        grow(0, (), frozenset())
        return out

    def _families_of(self, slot: Slot) -> frozenset[str]:
        """The families of the one mod a slot stands for (a kind `$<mod id>`); empty for a slot that stands for a family or a type."""
        base = _base(slot.kind)
        if not base.startswith(MOD_PREFIX):
            return frozenset()
        mod = self.data.mods.get(base[len(MOD_PREFIX) :])
        return frozenset(mod.families) if mod is not None else frozenset()

    def _compositions(self, universe: _Universe, key: PatternKey, rel_p, rel_s) -> Iterator[dict[tuple, int]]:
        """The ways the pure junk slots split into classes (side index, tag set): fixed by the key's tags, enumerated without them."""
        have = Counter()
        for slot in (*rel_p, *rel_s):
            have[(0 if slot.side is Side.PREFIX else 1, _tagset(slot.kind))] += 1
        left = (key.counts[0] - len(rel_p), key.counts[1] - len(rel_s))
        if left[0] < 0 or left[1] < 0:
            return
        if key.tags is not None:
            need = {cls: count - have[cls] for cls, count in key.tags}
            for cls, count in have.items():
                if cls not in need:
                    return
            if any(count < 0 for count in need.values()):
                return
            need = {cls: count for cls, count in need.items() if count}
            if any(sum(c for (s, _), c in need.items() if s == side) != left[side] for side in (0, 1)):
                return
            yield need
            return
        per_side = []
        for index, side in enumerate(SIDES):
            classes = sorted(tagset for tagset, items in universe.classes[side].items() if items)
            per_side.append([{(index, tagset): n for tagset, n in zip(classes, split) if n} for split in _splits(left[index], len(classes))] if classes or not left[index] else [])
        for first, second in product(*per_side):
            yield {**first, **second}

    def _assemble(
        self, universe: _Universe, key: PatternKey, relevant, need: dict[tuple, int], blocked, mode: Mode, named: frozenset[str] = frozenset()
    ) -> Iterator[CompressedState]:
        options = []
        for (side_index, tagset), count in sorted(need.items()):
            side = SIDES[side_index]
            fills = _fills(universe.classes[side].get(tagset, []), count, blocked, mode, named)
            if not fills:
                return
            options.append(fills)
        corners = self._states(key, relevant, options)
        if mode is Mode.ALL or all(self._ok(state) for state in corners):
            yield from (state for state in corners if self._ok(state))
            return
        # a corner that two classes make impossible together (or no state at all): every assignment of this composition instead
        every = [_fills(universe.classes[SIDES[side_index]].get(tagset, []), count, blocked, Mode.ALL) for (side_index, tagset), count in sorted(need.items())]
        found = [state for state in self._states(key, relevant, every) if self._ok(state)]
        if found:
            self.fallbacks += 1
        yield from found

    def _states(self, key: PatternKey, relevant, options) -> list[CompressedState]:
        out = []
        for pick in product(*options) if options else [()]:
            slots = [*key.crafted, *key.veiled, *relevant]
            for part in pick:
                slots.extend(part)
            slots.sort(key=_slot_key)
            out.append(CompressedState(key.flags, key.fractured, key.status, tuple(slots), *key.held))
        return out

    def _ok(self, state: CompressedState) -> bool:
        """Whether the state is an item the abstraction can give to an action (every slot has a family of its own)."""
        found = self._feasible.get(state)
        if found is None:
            try:
                self.ab._item_of(state, False)
                found = True
            except OutOfScopeError:
                raise
            except (ValueError, ItemError):
                found = False
            self._feasible[state] = found
        return found


def _splits(total: int, parts: int) -> Iterator[tuple[int, ...]]:
    """Every way to write `total` as `parts` non-negative integers."""
    if parts == 0:
        if total == 0:
            yield ()
        return
    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in _splits(total - first, parts - 1):
            yield (first, *rest)


def _fills(items: Sequence[_PureKind], count: int, blocked: frozenset[str], mode: Mode, named: frozenset[str] = frozenset()) -> list[tuple[Slot, ...]]:
    """The ways `count` pure junk slots of one class sit on its kinds: the lightest, the heaviest, or every one, by the pool weight they take out.

    With `named` (`ONE` only), every way the slots hold the folded families of `named`, the rest the lightest fill of the other kinds.
    """
    if count == 0:
        return [()]
    order = sorted(items, key=lambda item: (item.type.weight(blocked), item.kind))
    if mode is Mode.ALL:
        return _all_fills(order, count)
    if named and mode is Mode.ONE:
        return _named_fills(order, count, named)
    lightest = _greedy(order, count)
    if mode is not Mode.EXTREMES:
        return [lightest] if lightest is not None else []
    heaviest = _greedy(order[::-1], count)
    out = [fill for fill in (lightest, heaviest) if fill is not None]
    return [out[0]] if len(out) == 2 and out[0] == out[1] else out


def _greedy(order: Sequence[_PureKind], count: int) -> tuple[Slot, ...] | None:
    used: Counter = Counter()
    chosen: list[Slot] = []
    for item in order:
        while len(chosen) < count and used[item.type.base] < item.type.capacity:
            used[item.type.base] += 1
            chosen.append(item.slot)
    return tuple(sorted(chosen, key=_slot_key)) if len(chosen) == count else None


def _named_fills(order: Sequence[_PureKind], count: int, named: frozenset[str]) -> list[tuple[Slot, ...]]:
    """Every choice of the kinds of folded families in `named` (each within its capacity) for some of the `count` slots, the others the
    lightest fill of the remaining kinds (none of which holds a family of `named`); a choice whose rest cannot be filled is no member."""
    read = [item for item in order if item.type.named & named]
    rest = [item for item in order if not item.type.named & named]
    out: dict[tuple[Slot, ...], None] = {}
    used: Counter = Counter()

    def grow(at: int, chosen: tuple[Slot, ...]) -> None:
        fill = _greedy(rest, count - len(chosen))
        if fill is not None:
            out[tuple(sorted((*chosen, *fill), key=_slot_key))] = None
        if len(chosen) == count:
            return
        for index in range(at, len(read)):
            item = read[index]
            if used[item.type.base] < item.type.capacity:
                used[item.type.base] += 1
                grow(index, (*chosen, item.slot))
                used[item.type.base] -= 1

    grow(0, ())
    return list(out)


def _all_fills(order: Sequence[_PureKind], count: int) -> list[tuple[Slot, ...]]:
    out: list[tuple[Slot, ...]] = []
    used: Counter = Counter()

    def grow(at: int, chosen: tuple[Slot, ...]) -> None:
        if len(chosen) == count:
            out.append(tuple(sorted(chosen, key=_slot_key)))
            return
        for index in range(at, len(order)):
            item = order[index]
            if used[item.type.base] < item.type.capacity:
                used[item.type.base] += 1
                grow(index, (*chosen, item.slot))
                used[item.type.base] -= 1

    grow(0, ())
    return out


# ---- the optimistic model -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PatternOffer:
    """An action of the plan: `action` is None for the restart (buy the start item again), which leads to the start key."""

    label: str
    action: Action | None
    cost: float


def build_pattern_model(
    abstraction: Abstraction,
    start: CompressedState,
    offers: Sequence[PatternOffer],
    *,
    tags: bool | None = None,
    progress=None,
    max_keys: int | None = None,
    stop: Callable[[], str | None] | None = None,
    approximate: bool = False,
) -> PatternModel:
    """The optimistic model of the key from the start key, with no walk of the concrete graph.

    For each key, not a goal, and each offer it is offered at the pushed kernel of every member of the policy of the action
    (`Pattern.mode_of`); members that the action refuses do not offer it, and a restart leads to the start key from every key but the start's.
    Two members with the same pushed kernel give one abstract action. If a kernel produces an ordinary slot the pool did not list, the
    universe grows and the build runs again (`stats.universe_growth` counts the restarts). Raises `OutOfScopeError` as `Pattern` does and
    `RuntimeError` when more than `max_keys` keys were found (a safety net the caller asks for, never a default).

    `stop` is the stop-and-say-so net of the build (OR-12, OR-13): it is asked between two offers of a key (so a key that holds thousands of
    offers is no longer one step) and returns the reason once a net is reached. The build then ends with `PatternModel.stopped` set. The key it was
    expanding is left a tip like the keys it had not reached: a tip has no actions in the model, which is not "the key has none", so the caller
    gives it a bound of its own (`_pattern_bound`, a floor action to the goal). If the universe had grown in that pass, the keys expanded before
    the growth lack the members that hold the new slot, so none of them is kept: every key is a tip.

    With `approximate` the distributions behind the kernels are made in floats (`Abstraction.approximate`), which costs a twentieth of the time. A kernel
    made so is not the exact one: each of its chances is shrunk by `SHRINK` (2^-30, above the float error of 1e-13, so no chance exceeds its exact value)
    and the mass that is then missing is the chance of the state `SINK` (a successor of -1, a goal that costs nothing). The expected value of any
    non-negative function of the successors is then at most the exact one, so a model built so is a lower bound of the model built exactly, and it differs
    from it by about 1e-9 of a value.
    """
    return PatternBuilder(abstraction, start, tags=tags, progress=progress, max_keys=max_keys, stop=stop, approximate=approximate).extend(offers)


class PatternBuilder:
    """The model of the key, built on a list of offers that can grow: `extend` adds offers and builds only what they add (ticket #626).

    A model built on a part of the offers and grown by the ones that turn out to matter would cost a whole build for each round if each round began
    again; here a key that is expanded keeps its actions, and an offer added later is offered at the keys already expanded (its members, its kernels,
    each distinct kernel once) and at the keys it finds. `extend` returns a snapshot of the model, so a model returned stays what it was when the builder
    goes on. A build that stops (`stop`) leaves the builder unusable: the keys it had expanded do not all hold the offers being added, so the caller keeps
    the model of the round before. A universe that grows (a slot no member held) begins the whole build again, as `build_pattern_model` always has.
    """

    def __init__(
        self,
        abstraction: Abstraction,
        start: CompressedState,
        *,
        tags: bool | None = None,
        progress=None,
        max_keys: int | None = None,
        stop=None,
        grow: bool = False,
        approximate: bool = False,
    ) -> None:
        self.approximate = approximate  # the kernels are made in floats, shrunk and completed with the sink (see `_lowered`): a lower bound of the exact model
        self.grow = grow  # the builder will be extended: the members of a key are kept (they are made again for each offer added otherwise, and cost most of a round)
        self.ab = abstraction
        self.start = start
        self.tags = tags
        self.progress = progress
        self.max_keys = max_keys
        self.stop = stop
        self.offers: list[PatternOffer] = []
        self.restarts = 0
        self.began = time.perf_counter()
        self.dead = False
        self._reset()

    def _reset(self) -> None:
        before = getattr(self, "pattern", None)
        self.pattern = Pattern(self.ab, self.tags, [offer.action for offer in self.offers if offer.action is not None])
        if before is not None:
            # the build begins again because the universe grew: it begins on the grown universe. Made afresh, the universe would lose the slots the
            # kernels found (a fossil's added mods, which the pool does not list), find them again in the same pass, and begin again forever (#829:
            # a fossil world with bench crafts, the build ran past 25 minutes on CI, 109 restarts in a minute here)
            self.pattern.keep_universes(before)
        self.stats = PatternStats()
        self.index: dict[PatternKey, int] = {}
        self.keys: list[PatternKey] = []
        self.goal: list[bool] = []
        self.rows: list[list[tuple[int, int]]] = []
        self.expanded: list[bool] = []
        self.kernel_ids: dict[tuple, int] = {}
        self.kernels: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
        self.computed: dict = {}  # kernel key of the abstraction -> kernel id of the model
        self.gaps: dict = {}  # (key, offer index) -> whether no member of the key can take the action (see `_gap_everywhere`)
        self.done = 0  # the number of offers every expanded key holds
        self.members_kept: dict[int, dict[tuple[Mode, frozenset[str]], list[CompressedState]]] = {}
        self.pattern.note(self.start)
        self.start_id = self._intern(self.start)

    def _intern(self, state: CompressedState) -> int:
        key = self.pattern.key(state)
        found = self.index.get(key)
        if found is None:
            found = self.index[key] = len(self.keys)
            self.keys.append(key)
            self.goal.append(self.ab.is_goal(state))
            self.rows.append([])
            self.expanded.append(False)
            if self.max_keys is not None and len(self.keys) > self.max_keys:
                raise RuntimeError(f"more than {self.max_keys} keys")
        return found

    def extend(self, offers: Sequence[PatternOffer]) -> PatternModel:
        """Add `offers` to the model and build what they add; the snapshot of the model, with `stopped` set if a net ended the build."""
        if self.dead:
            raise RuntimeError("the build was stopped; use the model of the round before")
        self.offers.extend(offers)
        if self.done == 0 and not any(self.expanded):
            # nothing is expanded yet: the names of the offers seed the universe before the first pass, as `build_pattern_model` always did. Seeding them
            # as an addition would count as growth and begin the whole first pass again (R04: a second pass of 280 s where the model takes 96 s).
            self._reset()
        else:
            self.pattern.grew = 0
            self.pattern.add_actions([offer.action for offer in offers if offer.action is not None])
        while True:  # each pass that grows the universe adds slots to a finite set, so this ends; a pass that adds none is the answer
            stopped = self._pass()
            if stopped is not None:
                self.dead = True
                if self.pattern.grew:
                    self.expanded = [False] * len(self.keys)
                    self.rows = [[] for _ in self.keys]
                return self._snapshot(stopped)
            if not self.pattern.grew:
                return self._snapshot(None)
            self.restarts += 1
            self._reset()
            self.pattern.grew = 0

    def _snapshot(self, stopped: str | None) -> PatternModel:
        stats = replace(self.stats)
        stats.keys = len(self.keys)
        stats.goal_keys = sum(self.goal)
        stats.fallbacks = self.pattern.fallbacks
        stats.universe_growth = self.restarts
        stats.abstract_actions = sum(len(row) for row in self.rows)
        stats.abstract_edges = sum(len(self.kernels[kid][0]) for row in self.rows for _, kid in row)
        stats.seconds = time.perf_counter() - self.began
        stats.modes = Counter(self.stats.modes)
        return PatternModel(
            list(self.keys), list(self.goal), [list(row) for row in self.rows], list(self.kernels), stats, dict(self.index), list(self.expanded), stopped
        )

    def _pass(self) -> str | None:
        """Expand every key for the offers it lacks; the reason a net ended it, or None when it ran to the end."""
        with self.ab.approximate() if self.approximate else nullcontext():
            return self._pass_keys()

    def _pass_keys(self) -> str | None:
        pattern, offers, stats, progress = self.pattern, self.offers, self.stats, self.progress
        last = polled = time.perf_counter()
        i = 0

        def tick(oi: int) -> None:
            """Between two offers: ask the net, and say where the build is every 30 seconds (a key can take minutes: no longer one silent step)."""
            nonlocal last, polled
            now = time.perf_counter()
            if now - polled < POLL_SECONDS:
                return
            polled = now
            if self.stop is not None:
                reason = self.stop()
                if reason is not None:
                    raise _Stopped(reason)
            if progress is not None and now - last >= 30:
                last = now
                progress(
                    f"keys found {len(self.keys):,} expanded {i:,} (now offer {oi + 1:,} of {len(offers):,} of key {i:,}) kernels {stats.kernels:,} members {stats.members:,}"
                )

        while i < len(self.keys):
            if self.stop is not None and (reason := self.stop()) is not None:
                return reason
            if not self.goal[i]:
                first = self.done if self.expanded[i] else 0
                if first < len(offers):
                    if not pattern.members(self.keys[i], Mode.ANY):
                        raise _no_member(self.keys[i])
                    try:
                        self._offers_of_key(i, first, tick)
                    except _Stopped as reached:
                        self.ab.release_prepared(keep_erased=True)
                        return reached.reason
                    self.ab.release_prepared(keep_erased=True)
            self.expanded[i] = True
            i += 1
            now = time.perf_counter()
            if progress is not None and now - last >= 30:
                last = now
                progress(f"keys found {len(self.keys):,} expanded {i:,} kernels {stats.kernels:,} members {stats.members:,}")
        self.done = len(offers)
        return None

    def _prime(self, key: PatternKey, lo: int, hi: int, by_mode: dict) -> None:
        """Make, side by side in a process pool, the exact distributions that the offers `lo` to `hi` need at the members of `key` (ticket #250, #626).

        The kernel of a fossil set is a distribution of seconds, computed once per pool and cached; a model built on hundreds of offers asked for them
        one after the other. Nothing is built here and nothing changes in the answer; with one worker, or no `fork`, this does nothing. A chunk is
        at most `PRIME_CHUNK` offers so that the net is asked between chunks; the pool's `map` cannot be interrupted, so a net is overshot by at most one chunk.
        """
        requests = []
        for offer in self.offers[lo:hi]:
            if offer.action is None or _refused_by_flags(offer.action, key):
                continue
            policy = self.pattern.policy(offer.action, key)
            members = by_mode.get(policy)
            if members is None:
                members = by_mode[policy] = self.pattern.members(key, *policy)
                self.stats.members += len(members)
            requests.extend((member, offer.action) for member in members)
        self.ab.prime(requests)

    def _offers_of_key(self, i: int, first: int, tick) -> None:
        """Add to the row of key number `i` the abstract actions of the offers from number `first` on (one `(offer index, kernel id)` for each distinct pushed kernel)."""
        pattern, ab, stats, offers = self.pattern, self.ab, self.stats, self.offers
        key = self.keys[i]
        by_mode: dict[tuple[Mode, frozenset[str]], list[CompressedState]] = self.members_kept.setdefault(i, {}) if self.grow else {}
        added: list[tuple[int, int]] = []
        for oi in range(first, len(offers)):
            offer = offers[oi]
            tick(oi)
            if (oi - first) % PRIME_CHUNK == 0 and len(offers) - first >= PRIME_FROM:
                self._prime(key, oi, min(oi + PRIME_CHUNK, len(offers)), by_mode)
            if offer.action is None:
                if i != self.start_id:
                    added.append((oi, _kernel_id(self.kernel_ids, self.kernels, {self.start_id: Fraction(1)})))
                continue
            if _refused_by_flags(offer.action, key):
                continue
            policy = pattern.policy(offer.action, key)
            members = by_mode.get(policy)
            if members is None:
                members = by_mode[policy] = pattern.members(key, *policy)
                stats.members += len(members)
            stats.modes[(policy[0].value + ("+named" if policy[1] else ""), offer.label)] += 1
            seen: set[int] = set()
            for member in members:
                stats.pairs += 1
                try:
                    ck = ab.kernel_key(member, offer.action)
                except NotApplicableError:
                    stats.refused_pairs += 1
                    continue
                except OutOfScopeError as gap:
                    if _gap_everywhere(pattern, self.gaps, key, offer):
                        stats.gap_pairs += 1
                        continue
                    raise _gap(offer, key, gap) from gap
                kid = self.computed.get(ck)
                if kid is None:
                    try:
                        exact = ab.kernel(member, offer.action)
                    except NotApplicableError:
                        stats.refused_pairs += 1
                        continue
                    except OutOfScopeError as gap:
                        if _gap_everywhere(pattern, self.gaps, key, offer):
                            stats.gap_pairs += 1
                            continue
                        raise _gap(offer, key, gap) from gap
                    stats.kernels += 1
                    pushed: dict[int, Fraction] = defaultdict(Fraction)
                    for successor, chance in exact.items():
                        pattern.note(successor)
                        pushed[self._intern(successor)] += chance
                    if self.approximate:
                        pushed = _lowered(pushed)
                    kid = self.computed[ck] = _kernel_id(self.kernel_ids, self.kernels, pushed)
                if kid not in seen:
                    seen.add(kid)
                    added.append((oi, kid))
        self.rows[i].extend(added)  # the row of a key is whole or untouched: a stop in the middle leaves it as it was


def _refused_by_flags(action: Action, key: PatternKey) -> bool:
    """Whether the game refuses `action` at every member of `key` by the key's flags alone: the draw of a bought listing's mods works only on the
    unopened listing and every other action only on an opened item (`Abstraction._prepare`), and whether the item is unopened is a flag of the key.

    No member is made for such an offer: the draw reads every family, so it made them all at every key (#830: 99,272 of the 103,250 pairs of
    divine-roll-limits/medium).
    """
    return bool(getattr(action, "opens_listing", False)) != bool(getattr(key.flags, "unopened", False))


class _Stopped(Exception):
    """Raised by the tick of a build when a net is reached, inside the expansion of one key."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _no_member(key: PatternKey) -> OutOfScopeError:
    """The refusal of a build that reached a non-goal key it can make no member of: a defect of the member builder, never a fact about the game.

    The concrete state that reached the key is itself an item of the key, so the key has a member. With none, the key would keep only the
    restart, and its value, and every value that leans on it, would sit above the exact cost: a bound that a cut would trust (OR-12, OR-13).
    """
    refusal = OutOfScopeError(
        f"the crafted-pattern bound reached a key it can make no member of (status {[int(v) for v in key.status]}, {len(key.crafted)} crafted, "
        f"counts {key.counts}, tags {key.tags}, rarity {key.flags.rarity.value}, {len(key.fractured)} fractured). That is a defect of the member "
        "builder, since the state that reached the key is a member of it; its value would sit above the exact cost, so the build refuses."
    )
    refusal.player = (  # type: ignore[attr-defined]  # what `make_plan` says under `solver="auto"` (#535, OR-13); the text above is the developer's
        "the planner met a fault of its own while working out the cheapest possible cost of each kind of item the crafting can reach"
    )
    return refusal


def _gap_everywhere(pattern: Pattern, memo: dict, key: PatternKey, offer: PatternOffer) -> bool:
    """Whether no member of the key can take the action: each is refused by the game or is a model gap.

    Then the exact model has no action at any state of the key either (a gap makes it unavailable, as the walk and the planner do), so leaving
    it out of the key is what the exact model does. If one member can take it, a gap at the member that was asked may not be left out.
    """
    found = memo.get((key, id(offer)))
    if found is None:
        found = True
        for member in pattern.members(key, Mode.ALL):
            try:
                pattern.ab.kernel_key(member, offer.action)
            except (NotApplicableError, OutOfScopeError):
                continue
            found = False
            break
        memo[(key, id(offer))] = found
    return found


def _gap(offer: PatternOffer, key: PatternKey, gap: Exception) -> OutOfScopeError:
    """The refusal of a build that met a model gap at a member: the action cannot be dropped from the key without risking a bound above the exact cost."""
    refusal = OutOfScopeError(
        f"{offer.label} raised a model gap at a member of a key (status {[int(v) for v in key.status]}, {len(key.crafted)} crafted, "
        f"counts {key.counts}) while another member of the key can take it: {gap}. The crafted-pattern bound cannot drop the action from the "
        "key (the exact model drops it only where the gap is), so it refuses the route instead of returning a bound that may be above the "
        "exact cost (OR-12, OR-13)."
    )
    refusal.player = (  # type: ignore[attr-defined]  # what `make_plan` says under `solver="auto"` (#535, OR-13); the text above is the developer's
        f"the planner has no rule for {offer.label} on some of the items the crafting can reach, while it has one on others like them, so it "
        "cannot work out the cheapest possible cost of that action there"
    )
    return refusal


def _lowered(pushed: dict[int, Fraction]) -> dict[int, Fraction]:
    """A kernel made in floats as a kernel that is below the exact one: each chance shrunk by `SHRINK`, the mass that is missing given to `SINK`.

    A kernel with no float in it (a deterministic result, or a draw made exactly) is the exact one and stays. The chances of a float kernel are
    positive sums and products of at most a few dozen steps, each with a relative error of 2^-53, so each is within 1e-13 of its exact value and
    `chance x SHRINK` is below the exact one; a total above one after the shrink would mean an error far above that, and is refused.
    """
    if not any(isinstance(chance, float) for chance in pushed.values()):
        return pushed
    lowered = {successor: Fraction(chance) * SHRINK for successor, chance in pushed.items()}
    missing = 1 - sum(lowered.values(), Fraction(0))
    if missing < 0:
        raise RuntimeError(f"a float kernel adds up to more than one after its chances were shrunk by 2^-30 (by {float(-missing):.3g}): its error is far above the float error")
    if missing:
        lowered[SINK] = missing
    return lowered


def _kernel_id(ids: dict[tuple, int], kernels: list, pushed: dict[int, Fraction]) -> int:
    """The id of a pushed kernel (successor keys with integer weights, gcd-reduced), interned."""
    items = sorted(pushed.items())
    common = lcm(*(chance.denominator for _, chance in items))
    weights = [chance.numerator * (common // chance.denominator) for _, chance in items]
    divisor = reduce(gcd, weights)
    entry = (tuple(k for k, _ in items), tuple(w // divisor for w in weights))
    found = ids.get(entry)
    if found is None:
        found = ids[entry] = len(kernels)
        kernels.append(entry)
    return found


__all__ = ["Mode", "Pattern", "PatternBuilder", "PatternKey", "PatternModel", "PatternOffer", "PatternStats", "build_pattern_model"]
