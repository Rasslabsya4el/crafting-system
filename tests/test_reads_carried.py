"""The contract of `Reads.carried` (#1192): an action that carries the ordinary mods of a side reads none of them beyond its count.

On the contract's fixture items, each junk mod on a carried side swapped for another ordinary mod of that side gives the outcomes of the
item before, with the one mod swapped in each result that keeps it (the same chances, the same refusal); a wrong declaration is caught.
"""

import dataclasses
from collections import Counter

import pytest
from contract_support import CONTRACT_DATA, contract_pairs, fixture_items

from crafting_system.actions.beast_mods import BeastSideSwap
from crafting_system.actions.errors import ActionError, NotApplicableError
from crafting_system.actions.finite import Finite
from crafting_system.actions.pool import build_pool, partners
from crafting_system.items import ExplicitMod, Item, ItemError, Side
from crafting_system.items.model import UNVEILED_DOMAIN, VEILED_DOMAIN


def _answer(action, data, item) -> Counter | str:
    """The results of `action` on `item` as a multiset of their mods (each with its chance), or the kind of the game's refusal."""
    try:
        found = action.outcomes_under(data, item)
    except ActionError as refusal:
        return type(refusal).__name__
    assert isinstance(found, Finite), "the contract of `Reads.carried` is checked on actions that answer with `Finite`"
    out: Counter = Counter()
    for chance, result in found.results:
        out[(result.rarity, tuple(sorted(result.mods, key=repr)))] += chance
    return out


def _swapped_in(answer: Counter | str, old: ExplicitMod, new: ExplicitMod) -> Counter | str:
    if isinstance(answer, str):
        return answer
    out: Counter = Counter()
    for (rarity, mods), chance in answer.items():
        out[(rarity, tuple(sorted((new if entry == old else entry for entry in mods), key=repr)))] += chance
    return out


def _carried_junk(data, item: Item, sides) -> list[int]:
    return [
        index
        for index, entry in enumerate(item.mods)
        if not (entry.fractured or entry.crafted)
        and data.mods[entry.mod_id].domain not in (VEILED_DOMAIN, UNVEILED_DOMAIN)
        and Side(data.mods[entry.mod_id].generation_type) in sides
    ]


def carried_swaps(action, item: Item, data, per_mod: int = 8) -> tuple[list[tuple[str, str]], int]:
    """For `action` declaring `Reads.carried`: each junk mod of `item` on a carried side swapped for up to `per_mod` ordinary mods of that side,
    where the answer is not the answer before with the mod swapped: (the mod, its swap); and how many swaps were tried. An item whose pool
    holds a family on both sides is not tried (the declaration excludes it)."""
    sides = action.reads(data).carried
    if partners(build_pool(data, item)):
        return [], 0
    before = _answer(action, data, item)
    changed, tried_all = [], 0
    for index in _carried_junk(data, item, sides):
        entry = item.mods[index]
        mod = data.mods[entry.mod_id]
        tried = 0
        for other in data.mods.values():
            if tried >= per_mod:
                break
            if other.id == mod.id or other.generation_type != mod.generation_type or other.domain != mod.domain:
                continue
            new = ExplicitMod(other.id, tuple(min(stat.min, stat.max) for stat in other.stats))
            try:
                swapped = dataclasses.replace(item, mods=(*item.mods[:index], new, *item.mods[index + 1 :]))
                swapped.validate(data)
            except (ItemError, ValueError):
                continue
            tried += 1
            tried_all += 1
            if _answer(action, data, swapped) != _swapped_in(before, entry, new):
                changed.append((mod.id, other.id))
    return changed, tried_all


DECLARING = [(kind, action, name) for kind, action, name in contract_pairs() if action.reads(CONTRACT_DATA).carried]
TRIED: dict[str, int] = {}


def test_the_side_swaps_are_the_actions_that_declare_a_carried_side():
    assert {type(action) for _, action, _ in DECLARING} == {BeastSideSwap}
    assert all(action.reads(CONTRACT_DATA).carried == frozenset({action.remove_side}) for _, action, _ in DECLARING)


@pytest.mark.parametrize(("kind", "action", "name"), DECLARING, ids=[f"{kind}-{name}-{i}" for i, (kind, _, name) in enumerate(DECLARING)])
def test_a_carried_mod_swapped_for_another_of_its_side_is_swapped_in_every_result(kind, action, name):
    changed, tried = carried_swaps(action, fixture_items()[name], CONTRACT_DATA)
    assert changed == []
    TRIED[name] = TRIED.get(name, 0) + tried


def test_the_swaps_were_tried_on_items_that_hold_carried_junk():
    for _, action, name in DECLARING:
        if name not in TRIED:
            TRIED[name] = carried_swaps(action, fixture_items()[name], CONTRACT_DATA)[1]
    assert TRIED.get("rare_junk", 0) > 0 and TRIED.get("rare_four", 0) > 0


def test_a_wrong_declaration_is_caught():
    """A swap refused on an item that holds one given junk mod of the side it carries: swapping that mod away changes the answer."""
    item = fixture_items()["rare_four"]
    for side in Side:
        carried = _carried_junk(CONTRACT_DATA, item, {side})
        if not carried:
            continue
        junk = item.mods[carried[0]].mod_id

        @dataclasses.dataclass(frozen=True)
        class Picky(BeastSideSwap):
            def outcomes(self, data, item):
                if any(entry.mod_id == junk for entry in item.mods):
                    raise NotApplicableError("a mod the declaration says is carried")
                return super().outcomes(data, item)

        wrong = Picky(Side.PREFIX if side is Side.SUFFIX else Side.SUFFIX)
        assert wrong.reads(CONTRACT_DATA).carried == frozenset({side})
        changed, tried = carried_swaps(wrong, item, CONTRACT_DATA)
        assert tried and changed != []
        return
    raise AssertionError("the fixture item holds no junk")
