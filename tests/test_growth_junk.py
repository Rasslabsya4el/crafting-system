"""The junk a growth round carried (#1665, PR 1: J2 and J4; `planner/_growth.py`; OR-12, OR-39, OR-40, OR-55).

J1 (the plain move) and J3 (an imprint's own shape) were tried and left out: on R17 the Orb of Alchemy made the second round 3.5 times
slower, and the Croaker pair main's plan uses was named by no role. Each rule is read from the offers' data, never from a craft:
hand-worked tables (`test_growth._table`) pin each, and the R17, R24 and R14 tables of the real 3.29.3.3 dump (they skip without it)
show the offers each names there.

* J2. The hold-back class of an addition is also read at the shape's item with a mod on each side: one that removes a mod of one side
  only removes nothing at an item that holds none there.
* J4. A lock the protector names comes with the other ways of making that same lock (the Wild Bristle Matron where every outcome of its
  draw at the item the step holds is that lock), and the closure brings no locker: on R24 the Matron is the suffix lock's other way; on
  R17 with its prefixes full it is not the prefix lock's; on R14 its draw makes neither lock. A lock group names every locker, as before.
"""

import dataclasses
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

from test_growth import RARE, _lock_world, _names, _table

from crafting_system.items import Rarity
from crafting_system.planner import _growth

NORMAL = Rarity.NORMAL
ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "references-allflame-2026-07-31.json"


# --- J2: the hold-back class is read at an item holding a mod on each side ---------------------------------------------------------------


def _mod(mod_id, fractured=False):
    return SimpleNamespace(mod_id=mod_id, fractured=fractured)


class _OneSideRemover:
    """Beastcraft Add Suffix Remove Prefix as `_fans_at` reads it: it adds the suffix S9 and takes a random prefix off (the prefixes start
    with P); at an item with no prefix it removes nothing."""

    def outcomes(self, data, item):
        held = [m.mod_id for m in item.mods]
        prefixes = [m for m in held if m.startswith("P")]
        results = [tuple(m for m in held if m != p) + ("S9",) for p in prefixes] or [(*held, "S9")]
        return SimpleNamespace(results=tuple((Fraction(1, len(results)), SimpleNamespace(mods=tuple(_mod(m) for m in mods))) for mods in results))

    def added_draw(self, data, item):
        return None


def test_an_addition_that_removes_a_mod_of_one_side_is_held_back_though_the_shape_s_item_holds_none_there():
    table = _table()
    view = SimpleNamespace(mods=(_mod("S1"),), rarity=RARE)  # the one item the rare shape gives holds a suffix alone (R17's)
    both = SimpleNamespace(mods=(_mod("P1"), _mod("S1")), rarity=RARE)
    table._both_sides = lambda item: both if item is view else None
    assert table._removes_at(_OneSideRemover(), view) is False  # read at the shape's item alone, nothing is removed (main's reading)
    assert table._fans_at(_OneSideRemover(), view) == _growth.REMOVES_AND_ADDS  # main: ""
    # a beast swap's outcomes are a mixture: one part for each mod it may take off, read by the item each part keeps before its draw
    mixture = SimpleNamespace(outcomes=lambda data, item: SimpleNamespace(components=((Fraction(1), SimpleNamespace(retained=SimpleNamespace(mods=(_mod("S1"),)))),)))
    assert table._removes_at(mixture, both) is True and table._removes_at(mixture, view) is False


def test_the_item_with_a_mod_on_each_side_is_made_from_the_item_s_own_pool_and_is_none_where_both_sides_hold_one():
    table, _at = _real_table("r17-lightning-talisman")
    data, rare = table.data, table.views[RARE]  # R17's rare shape: its item holds one suffix
    sides = lambda item: sorted(data.mods[m.mod_id].generation_type for m in item.mods)  # noqa: E731
    assert sides(rare) == ["suffix"]
    both = table._both_sides(rare)
    assert both is not None and sides(both) == ["prefix", "suffix"] and both.rarity is RARE
    assert table._both_sides(both) is None  # it holds one on each side already
    assert table._both_sides(table.views[NORMAL]) is None  # a Normal item has room for none


# --- J4: a named lock comes with the other ways of making that same lock ------------------------------------------------------------------


def test_a_bench_lock_brings_no_locker_through_the_closure():
    table = _lock_world()
    table.held_back = frozenset()
    suffix_lock, beast = 1, 3
    assert _names(table, table.closure({suffix_lock})) == {"lock suffixes"}  # main: {"lock suffixes", "beast lock"}
    assert _names(table, table.closure({beast})) == {"beast lock"}


# --- the real tables ----------------------------------------------------------------------------------------------------------------------


def _real_table(name: str):
    from abstraction_support import real_game_data

    from crafting_system.abstraction._goal import Goal
    from crafting_system.planner._plan import cheapest_per_class, offers_for, price_offers
    from crafting_system.prices import load_price_file
    from crafting_system.targets import load_target

    data = real_game_data()
    target = dataclasses.replace(load_target(ROOT / "examples" / "targets" / f"{name}.yaml", data), actions=None)
    goal = Goal.from_target(target)
    priced, _dropped = price_offers(offers_for(data, goal, target.base_id, target.start_item, target.actions).offers, load_price_file(PRICES), "test")
    priced, _same = cheapest_per_class(priced)
    table = _growth.growth_table(data, goal, target, priced, None)
    return table, {entry.label: entry.position for entry in table.entries}


def test_on_r17_both_beast_swaps_are_held_back():
    table, at = _real_table("r17-lightning-talisman")
    held = _growth.Grower(table, ()).later_ones
    assert {at["Beastcraft Add Suffix Remove Prefix"], at["Beastcraft Add Prefix Remove Suffix"]} <= held  # main: the first escaped
    assert table.entries[at["Beastcraft Add Suffix Remove Prefix"]].fans == _growth.REMOVES_AND_ADDS


def test_the_matron_is_the_other_way_of_a_lock_only_where_its_draw_makes_that_lock_alone_r24_r17_r14():
    matron, lock = "Beastcraft Wild Bristle Matron (add a metamod)", "Bench craft Suffixes Cannot Be Changed"
    table, at = _real_table("r24-avoid-shock-boots")
    table.held_back = frozenset()
    side = lambda name: frozenset(leaf for leaf in range(len(table.goal.leaves)) if table.side_of(leaf) == name)  # noqa: E731
    assert _names(table, table.lock_ways("suffix", frozenset({RARE}), side("suffix"))) == {matron}
    assert _names(table, table.closure({at[lock]})) == {lock}
    table, _at = _real_table("r17-lightning-talisman")  # its prefixes full, the Matron's draw is the prefix lock or a suffix metamod: not the same lock
    table.held_back = frozenset()
    assert table.lock_ways("prefix", frozenset({RARE}), side("prefix")) == set()
    assert table.lock_ways("suffix", frozenset({RARE}), side("suffix")) != set()
    table, _at = _real_table("r14-hunter-bow")  # at its rare item holding either side's wanted mods, the Matron's draw makes no lock
    table.held_back = frozenset()
    for name in ("prefix", "suffix"):
        assert table.lock_ways(name, frozenset({RARE}), side(name)) == set()


def test_through_the_protector_the_matron_is_named_with_r24_s_suffix_lock_and_not_with_r17_s_prefix_lock():
    matron, suffix_lock, prefix_lock = "Beastcraft Wild Bristle Matron (add a metamod)", "Bench craft Suffixes Cannot Be Changed", "Bench craft Prefixes Cannot Be Changed"
    table, _at = _real_table("r24-avoid-shock-boots")
    table.held_back = frozenset()
    suffixes = {leaf for leaf in table.open if table.side_of(leaf) == "suffix"}
    prefixes = {leaf for leaf in table.open if table.side_of(leaf) == "prefix"}
    # R24's round 3: the Veiled Exalted Orb at the rare item waits for nothing and can lose the three wanted suffixes
    named = _names(table, table.roles(set(), suffixes, frozenset({RARE}), False, frozenset(), frozenset()))
    assert {suffix_lock, matron} <= named
    table, _at = _real_table("r17-lightning-talisman")
    table.held_back = frozenset()
    suffixes = {leaf for leaf in table.open if table.side_of(leaf) == "suffix"}
    prefixes = {leaf for leaf in table.open if table.side_of(leaf) == "prefix"}
    # a step that waits for a suffix and can lose the prefixes names the prefix lock; the Matron's draw is not that lock there
    named = _names(table, table.roles(suffixes, prefixes, frozenset({RARE}), False, frozenset(), frozenset()))
    assert prefix_lock in named and matron not in named
