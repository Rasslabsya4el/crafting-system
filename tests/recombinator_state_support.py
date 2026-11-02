"""The layer 1 oracle for an action that declares `Reads.input_classes` (the recombinator, ticket #217, ADR-0019, ADR-0062 decision 3).

The compressed state tells a junk mod by its class, so the kernel of the recombinator on `(state of the item, state of the donor)` is the
average of the action over the concrete items the two states stand for. This module lists those items **one by one** and runs the action
on every pair, compressing each finished item on its own and adding the chances up exactly; it reads no hypergeometric law, no placement
and no kernel of `abstraction`. An item of a state is a set of pool mods whose kinds are the state's, no two of one family, with the
crafted and named mods the state holds; every such item is as likely as any other (the placements of the class slots in the families of a
type are uniform, and the two inputs are independent).

`check_input_classes_kernel` is the check the contract suite makes for the recombinator in place of the plain brute force on the one item
and donor it was given (that pair is one of the pairs averaged).
"""

import itertools
from collections import defaultdict
from fractions import Fraction

import pytest
from contract_support import finished

from crafting_system.abstraction import Abstraction, CompressedState, FracturedMod
from crafting_system.actions import OutOfScopeError, tiers_of
from crafting_system.items import ExplicitMod, Item, Rarity


def _low(data, mod_id: str) -> tuple[int, ...]:
    return tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats)


def _is_class(kinds, origin) -> bool:
    """Whether the slot or fractured mod the representative mod stands for is a class kind."""
    return kinds.is_class(origin.mod_id if isinstance(origin, FracturedMod) else origin.kind)


def items_of(ab: Abstraction, data, state: CompressedState) -> list[Item]:
    """Every concrete item `state` stands for (each different set of mods once), found by trying every mod of each class kind."""
    representative, origins = ab._item_of(state, False)
    kinds = ab._context(state.flags.influences).kinds
    wanted: list[tuple[str, str]] = [("fractured", held.mod_id) for held in state.fractured if kinds.is_class(held.mod_id)]
    wanted += [("slot", slot.kind) for slot in state.slots if not slot.crafted and kinds.is_class(slot.kind)]
    fixed = [
        entry
        for entry in representative.mods
        if not _is_class(kinds, origins[(entry.mod_id, entry.fractured, entry.crafted)])
    ]
    probe = Item.build(data, base_id=ab.base_id, item_level=ab.item_level, rarity=Rarity.RARE, influences=state.flags.influences)
    tiers = tiers_of(data, probe)
    candidates: dict[str, list[str]] = {}
    for _, kind in wanted:
        if kind not in candidates:
            candidates[kind] = sorted(mod_id for mod_id, mod in data.mods.items() if kinds.of(mod) == kind and not kinds.is_influenced(mod))
            assert candidates[kind], f"no mod has the class kind {kind}"
    taken_by_fixed = set().union(*(set(data.mods[entry.mod_id].families) or {entry.mod_id} for entry in fixed)) if fixed else set()
    found: dict[frozenset, Item] = {}
    for choice in itertools.product(*(candidates[kind] for _, kind in wanted)):
        families: list[str] = []
        for mod_id in choice:
            families += list(data.mods[mod_id].families) or [mod_id]
        if len(set(families)) != len(families) or set(families) & taken_by_fixed:
            continue
        mods = [
            ExplicitMod(mod_id, tiers.get(mod_id, 1), _low(data, mod_id), fractured=where == "fractured")
            for (where, _), mod_id in zip(wanted, choice)
        ]
        key = frozenset((entry.mod_id, entry.fractured) for entry in (*fixed, *mods))
        if key not in found:
            found[key] = representative.changed(data, mods=(*fixed, *mods))
    items = list(found.values())
    assert items, "the state stands for no item"
    for item in items:
        assert ab.compress(item) == state, "every item built from the classes compresses back to the state"
    return items


def averaged_pushforward(ab: Abstraction, data, state: CompressedState, want: CompressedState, action, reading=None) -> dict:
    """The kernel the state of the item and the state of the donor must have: the action on every pair of items, compressed, the chances added up."""
    mine, theirs = items_of(ab, data, state), items_of(ab, data, want)
    total: dict = defaultdict(Fraction)
    for given in mine:
        for donor in theirs:
            for chance, result in finished(action.with_inputs((donor,)).outcomes_under(data, given, reading), data):
                total[ab.compress(result)] += chance
    pairs = len(mine) * len(theirs)
    return {found: chance / pairs for found, chance in total.items()}


def check_input_classes_kernel(ab: Abstraction, data, item: Item, action, reading=None) -> None:
    """The kernel of the state of `item` with the donor of `action` equals the average of the action over the items of the two states."""
    state = ab.compress(item)
    donor = action.inputs(data, item)[0].want
    if donor.influences != item.influences:  # the classes carry the weights under the item's own influences only: the kernel refuses
        with pytest.raises(OutOfScopeError, match="other influences"):
            ab.kernel(state, action)
        return
    expected = averaged_pushforward(ab, data, state, ab.compress(donor), action, reading)
    kernel = ab.kernel(state, action)
    assert dict(kernel) == expected, "the kernel equals the action averaged over the items of the two states"
    assert sum(kernel.values()) == 1 and all(type(chance) is Fraction and chance > 0 for chance in kernel.values())
