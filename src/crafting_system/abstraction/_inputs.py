"""The kernel of an action with an input, averaged over the names its item and its input could hold (ticket #217, ADR-0062 decision 3).

An action that declares `Reads.input_classes` (the recombinator) reads the mods of the item in hand and of its input through their *classes*:
the compressed state tells a junk mod by its family type and its place in the type (`Slot.kind` `"~n%p"`, `_kinds.py`), not by its family. The
result still depends on which families the two inputs hold, because a mod on both inputs enters the pool twice and a pick closes the family of
the other input's mod. The planner cannot tell the families of a class apart (a policy that does not look at junk names does not), so the
kernel is the average over where the names lie: **each input holds its class slots in families of their type, uniformly among the injective
placements that leave out the families its own crafted and named mods hold, and the two inputs are placed independently**.

Only the overlap of the two placements matters to the action. In one family type with `N` families let the item's crafted and named mods
hold the families `A_R` and the input's `A_D`; `f = N - |A_R union A_D|` families are free, `d = |A_D - A_R|` are held only by the input's
named mods and `r = |A_R - A_D|` only by the item's. A class slot of the item sits in one of the `d + f` families outside `A_R`, one of the
input sits in one of the `r + f` outside `A_D`. A pattern is the set of class slots of the item that sit in a family of the input's named
mods (each in its own), the same for the input's, and the set of pairs of class slots that sit in one free family. With `k_R` and `k_D` class
slots on the two sides, `a_R` and `a_D` of them on named families, and `j` shared free pairs, the chance of one such pattern is

    (f)_(k_R - a_R) / (d + f)_(k_R)  *  (f)_(k_D - a_D) / (r + f)_(k_D)  *  (f - k_R + a_R)_(k_D - a_D - j) / (f)_(k_D - a_D)

((n)_m the falling factorial n (n-1) ... (n-m+1)): the item's free slots take `k_R - a_R` of the `f` free families, and the input's `k_D - a_D`
free slots take `j` of those and the others from the rest. With no crafted or named mod it is `(N - k_R)_(k_D - j) / (N)_(k_D)`. Slots of
different types never share a family. The kernel adds up, over the patterns (grouped by the kinds and families in them, since slots of one
kind are alike), the chance of the pattern times the kernel of the action run on an item and an input that have that pattern and no other
overlap. That run is the action's own `outcomes` on concrete items (`Action.with_inputs` gives the action its other input), so no rule is
decided here, and the oracle of the tests is the same average taken over every concrete item the two states stand for.

Refused (`OutOfScopeError`): an input with other influences than the item (the weights of the mods under the other influences are not in the
classes), another base or item level (no state), more than one input, and a pool with a family that has mods on both sides.
"""

import itertools
from collections import defaultdict
from collections.abc import Iterator
from fractions import Fraction

from crafting_system.actions import Action, NotApplicableError, OutOfScopeError, build_pool, partners
from crafting_system.items import Item, Rarity, Side

from ._kinds import MOD_PREFIX, base_kind, held_families
from ._state import CompressedState

Entry = tuple[str, int, str]  # ("slot" | "fractured", index in the state, class kind)
Spec = tuple[tuple[tuple[Entry, Entry], ...], tuple[tuple[Entry, str], ...], tuple[tuple[Entry, str], ...]]
# (class slots of the item and of the input in one free family, class slots of the item in a family the input's named mods hold, and the reverse)


def _falling(n: int, m: int) -> int:
    """`n (n-1) ... (n-m+1)`: 1 for `m` = 0, and 0 when `m > n`."""
    found = 1
    for step in range(m):
        found *= n - step
        if found <= 0:
            return 0
    return found


class _Type:
    """The class slots of the item and of the input in one family type, and the families of the type that each input's named mods hold."""

    def __init__(self, side: Side, base: str, families: list[str]):
        self.side, self.base, self.families = side, base, families
        self.mine: list[Entry] = []
        self.theirs: list[Entry] = []
        self.held: tuple[set[str], set[str]] = (set(), set())  # the families held by the named mods of the item and of the input

    @property
    def free(self) -> list[str]:
        return [family for family in self.families if family not in self.held[0] and family not in self.held[1]]


def input_kernel(ability, state: CompressedState, action: Action, prepared) -> dict[CompressedState, Fraction]:
    """The kernel of `action` on `state` with its input, averaged over the families of the class slots (see the module docstring).

    `prepared` is the action's outcomes on the one item `ability._prepare` builds for the state: it has been made already, so the
    game's refusals (which do not depend on the families) and a result in another item space have been raised.
    """
    cached = ability._input_kernels.get((state, action))
    if cached is not None:
        return cached
    data = ability.data
    wants = tuple(need.want for need in action.inputs(data, prepared.item))
    if len(wants) != 1:
        raise OutOfScopeError(f"the kernel averages over one input, and {action.label(data)} has {len(wants)}")
    donor = wants[0]
    if (donor.base_id, donor.item_level) != (ability.base_id, ability.item_level):
        raise OutOfScopeError(
            f"the input is an item on {donor.base_id} at item level {donor.item_level}, and this abstraction stands for items on "
            f"{ability.base_id} at item level {ability.item_level}: an input of another base or item level has no compressed state"
        )
    want = ability.compress(donor)
    if want.flags.influences != state.flags.influences:
        raise OutOfScopeError(
            "the input holds other influences than the item in hand: the weights of the mods under the other influences are not in the classes of the state"
        )
    _refuse_partner_families(ability)
    kinds = ability._context(state.flags.influences).kinds
    types = _types(ability, kinds, state, want)
    patterns = [_patterns(kinds, each) for each in types]
    result: dict[CompressedState, Fraction] = defaultdict(Fraction)
    for combination in itertools.product(*patterns):
        chance = Fraction(1)
        specs: list[Spec] = []
        for each_chance, each_spec in combination:
            chance *= each_chance
            specs.append(each_spec)
        if chance == 0:
            continue
        for found, share in _kernel_of(ability, state, want, action, types, specs).items():
            result[found] += chance * share
    kernel = dict(result)
    assert sum(kernel.values()) == 1
    ability._input_kernels[(state, action)] = kernel
    return kernel


def _refuse_partner_families(ability) -> None:
    """Raise `OutOfScopeError` for a pool with a family that has mods on both sides (holding one side holds the other: the placements are not independent)."""
    if ability._has_partners is None:
        empty = Item.build(ability.data, base_id=ability.base_id, item_level=ability.item_level, rarity=Rarity.RARE)
        ability._has_partners = bool(partners(build_pool(ability.data, empty)))
    if ability._has_partners:
        raise OutOfScopeError("the pool has a family with mods on both sides: the placement of the class slots in families is not modelled")


def _entries(kinds, state: CompressedState) -> list[Entry]:
    """The class slots of a state: its fractured mods and its slots whose kind is a family type with a place."""
    found: list[Entry] = []
    for index, held in enumerate(state.fractured):
        if kinds.is_class(held.mod_id):
            found.append(("fractured", index, held.mod_id))
    for index, slot in enumerate(state.slots):
        if not slot.crafted and kinds.is_class(slot.kind):
            found.append(("slot", index, slot.kind))
    return found


def _named_families(ability, kinds, state: CompressedState) -> set[str]:
    """The families the crafted and named mods of a state hold (a name is a crafted mod's canonical id, or a mod the pool of its family lacks).

    A fractured mod that is not a class slot is named too: its id is a real mod's (a fractured crafted mod, a fractured mod no pool lists).
    """
    found: set[str] = set()
    for held in state.fractured:
        if not kinds.is_class(held.mod_id):
            found |= held_families(ability.data.mods[held.mod_id])
    for slot in state.slots:
        if slot.crafted:
            found |= held_families(ability.data.mods[slot.kind])
        elif slot.kind.startswith(MOD_PREFIX):
            found |= held_families(ability.data.mods[base_kind(slot.kind)[len(MOD_PREFIX) :]])
    return found


def _types(ability, kinds, state: CompressedState, want: CompressedState) -> list[_Type]:
    """The family types in which the item or the input holds a class slot, with the slots and the families their named mods hold."""
    found: dict[tuple[Side, str], _Type] = {}
    for index, held in enumerate((state, want)):
        for entry in _entries(kinds, held):
            side = kinds.side_of(entry[2]) if entry[0] == "fractured" else held.slots[entry[1]].side
            base = base_kind(entry[2])
            each = found.get((side, base))
            if each is None:
                each = found[side, base] = _Type(side, base, kinds.families_of_type(side, base))
            (each.mine, each.theirs)[index].append(entry)
    for index, held in enumerate((state, want)):
        named = _named_families(ability, kinds, held)
        for each in found.values():
            each.held[index].update(named & set(each.families))
    for each in found.values():
        if len(each.mine) > len(each.families) - len(each.held[0]) or len(each.theirs) > len(each.families) - len(each.held[1]):
            raise ValueError(f"more slots of the family type {each.base} than the pool has families for them")
    return list(found.values())


def _partial_injections(entries: list[Entry], targets: list[str]) -> Iterator[tuple[tuple[tuple[Entry, str], ...], list[Entry]]]:
    """Every way to put some of `entries` into distinct `targets`: the entries placed (each with its target) and the entries left."""

    def extend(index: int, used: frozenset[str], placed: tuple[tuple[Entry, str], ...]) -> Iterator[tuple[tuple[tuple[Entry, str], ...], list[Entry]]]:
        if index == len(entries):
            yield placed, [entry for entry in entries if entry not in {each for each, _ in placed}]
            return
        yield from extend(index + 1, used, placed)
        for target in targets:
            if target not in used:
                yield from extend(index + 1, used | {target}, (*placed, (entries[index], target)))

    return extend(0, frozenset(), ())


def _patterns(kinds, each: _Type) -> list[tuple[Fraction, Spec]]:
    """The patterns of overlap in one family type with their chance, equal ones (by the kinds and families in them) added up (see the module docstring)."""
    free = len(each.free)
    available = (len(each.families) - len(each.held[0]), len(each.families) - len(each.held[1]))
    onto_theirs = sorted(each.held[1] - each.held[0])  # families only the input's named mods hold: a class slot of the item may sit in one
    onto_mine = sorted(each.held[0] - each.held[1])
    seen: dict[tuple, tuple[Fraction, Spec]] = {}
    for mine_placed, mine_free in _partial_injections(each.mine, onto_theirs):
        for theirs_placed, theirs_free in _partial_injections(each.theirs, onto_mine):
            chance = Fraction(
                _falling(free, len(mine_free)) * _falling(free, len(theirs_free)),
                _falling(available[0], len(each.mine)) * _falling(available[1], len(each.theirs)),
            )
            if chance == 0:
                continue
            for shared in _matchings(mine_free, theirs_free):
                overlap = Fraction(_falling(free - len(mine_free), len(theirs_free) - len(shared)), _falling(free, len(theirs_free)))
                spec: Spec = (tuple(shared), mine_placed, theirs_placed)
                label = (
                    tuple(sorted((a[0], a[2], b[0], b[2]) for a, b in shared)),
                    tuple(sorted((a[0], a[2], family) for a, family in mine_placed)),
                    tuple(sorted((a[0], a[2], family) for a, family in theirs_placed)),
                )
                before = seen.get(label)
                seen[label] = (chance * overlap + (before[0] if before else 0), before[1] if before else spec)
    return list(seen.values())


def _matchings(mine: list[Entry], theirs: list[Entry]) -> Iterator[list[tuple[Entry, Entry]]]:
    """Every set of pairs `(slot of the item, slot of the input)` in which no slot is twice."""

    def extend(index: int, used: frozenset[int], pairs: list[tuple[Entry, Entry]]) -> Iterator[list[tuple[Entry, Entry]]]:
        if index == len(mine):
            yield pairs
            return
        yield from extend(index + 1, used, pairs)
        for other, entry in enumerate(theirs):
            if other not in used:
                yield from extend(index + 1, used | {other}, [*pairs, (mine[index], entry)])

    return extend(0, frozenset(), [])


def _kernel_of(ability, state, want, action, types: list[_Type], specs: list[Spec]) -> dict[CompressedState, Fraction]:
    """The kernel of `action` run on an item and an input that overlap as `specs` say (one pattern per family type) and in no other family."""
    from ._kernel import _Prepared

    placed: tuple[dict, dict] = ({}, {})
    for each, (shared, mine_placed, theirs_placed) in zip(types, specs):
        fresh = iter(each.free)
        for first, second in shared:  # one free family holds both
            placed[0][first[:2]] = placed[1][second[:2]] = next(fresh)
        for entry, family in mine_placed:
            placed[0][entry[:2]] = family
        for entry, family in theirs_placed:
            placed[1][entry[:2]] = family
        for index, group in enumerate((each.mine, each.theirs)):
            for entry in group:
                if entry[:2] not in placed[index]:
                    placed[index][entry[:2]] = next(fresh)
    mine_item, origins = ability._item_of(state, False, placement=placed[0])
    theirs_item, _ = ability._item_of(want, False, placement=placed[1])
    try:
        outcomes = action.with_inputs((theirs_item,)).outcomes_under(ability.data, mine_item, ability._reading)
    except NotApplicableError as refusal:  # the game's refusal of the representative has been raised by `_prepare`: this is another placement's
        raise OutOfScopeError(
            f"the game refuses {action.label(ability.data)} for some placements of the names and not for others ({refusal}): the average over them is not defined"
        ) from refusal
    ability._check_type_blind(state, outcomes)
    ability._check_fracture_without_partners(state, outcomes)
    ability._check_same_item_space(outcomes)
    prepared = _Prepared(outcomes, origins, item=mine_item, imprints=state.imprints, donors=(theirs_item,))
    return ability._mixture_kernel(state, prepared)
