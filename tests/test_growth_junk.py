"""The junk a growth round carried (#1665, PR 1: J1 to J4; `planner/_growth.py`; OR-12, OR-39, OR-40, OR-55).

Each rule is read from the offers' data, never from a craft: hand-worked tables (`test_growth._table`) pin each, and the R17 and R24 tables
of the real 3.29.3.3 dump (they skip without it) show the offers each names there.

* J1. The move to an adder's shape is a plain one: an offer that forces a mod (an essence, whose other mods are a full random draw) is not
  a move a role names, though it is the cheapest way (Whispering Essence of Greed at 0.0027 c against the Orb of Alchemy on R17).
* J2. The hold-back class of an addition is also read at the shape's item with a mod on each side: one that removes a mod of one side
  only removes nothing at an item that holds none there.
* J3. An imprint brings the restores and the imprints made at its own shapes, not every imprint.
* J4. A bench lock brings the other lockers of its side only where a step of the plan in hand uses it.
"""

import dataclasses
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

from test_growth import MAGIC, RARE, A, _entry, _lock_world, _names, _table

from crafting_system.actions import NotApplicableError
from crafting_system.items import Rarity
from crafting_system.planner import _growth

NORMAL = Rarity.NORMAL
ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "references-allflame-2026-07-31.json"


# --- J1: the move to an adder's shape is a plain one -------------------------------------------------------------------------------------


def _move_world(*, alchemy: bool = True):
    """An adder of A at the rare shape ("exalt A", 1 Chaos, 1 in 2); a step that acts at the Normal shape. Two ways from Normal to rare: an
    essence that forces its own mod and draws the rest (0.0027 Chaos) and, when `alchemy`, the Orb of Alchemy (0.5 Chaos, forces none)."""
    entries = [
        _entry("exalt A", 1.0, at=RARE, chance={A: Fraction(1, 2)}),
        _entry("essence", 0.0027, kind="reroll", forces=True, leads={NORMAL: frozenset({RARE})}),
    ]
    if alchemy:
        entries.append(_entry("alchemy", 0.5, kind="reroll", leads={NORMAL: frozenset({RARE})}))
    table = _table(*entries)
    table.held_back = frozenset()
    return table


def test_the_move_a_role_names_to_an_adder_s_shape_forces_no_mod_though_an_essence_is_the_cheapest_way():
    table = _move_world()
    named = _names(table, table.roles({A}, set(), frozenset({NORMAL}), False, frozenset(), frozenset()))
    assert named == {"exalt A", "alchemy"}  # main: {"exalt A", "essence"}
    # where no plain way is found, the cheapest way of any offers is the move, as before
    table = _move_world(alchemy=False)
    assert _names(table, table.roles({A}, set(), frozenset({NORMAL}), False, frozenset(), frozenset())) == {"exalt A", "essence"}


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


def test_the_item_with_a_mod_on_each_side_is_made_from_the_item_s_own_pool_and_is_none_where_both_sides_hold_one():
    table, _at = _real_table("r17-lightning-talisman")
    data, rare = table.data, table.views[RARE]  # R17's rare shape: its item holds one suffix
    sides = lambda item: sorted(data.mods[m.mod_id].generation_type for m in item.mods)  # noqa: E731
    assert sides(rare) == ["suffix"]
    both = table._both_sides(rare)
    assert both is not None and sides(both) == ["prefix", "suffix"] and both.rarity is RARE
    assert table._both_sides(both) is None  # it holds one on each side already
    assert table._both_sides(table.views[NORMAL]) is None  # a Normal item has room for none


# --- J3: an imprint brings only the imprints made at its own shapes ----------------------------------------------------------------------


def _imprint_world():
    return _table(
        _entry("magic imprint", 3.0, kind="terminal", makes_imprint=True, draws=False, copies_at=frozenset({MAGIC})),
        _entry("magic imprint, replacing", 3.0, kind="terminal", makes_imprint=True, draws=False, copies_at=frozenset({MAGIC})),
        _entry("rare imprint", 9.0, kind="terminal", makes_imprint=True, draws=False, copies_at=frozenset({RARE})),
        _entry("rare imprint, replacing", 9.0, kind="terminal", makes_imprint=True, draws=False, copies_at=frozenset({RARE})),
        _entry("restore", 0.0, kind="refused", restores=True),
        _entry("other", 1.0),
    )


def test_an_imprint_brings_the_restore_and_the_imprints_of_its_own_shape_and_a_restore_alone_brings_every_imprint():
    table = _imprint_world()
    table.held_back = frozenset()
    assert _names(table, table.closure({2})) == {"rare imprint", "rare imprint, replacing", "restore"}  # main: every imprint
    assert _names(table, table.closure({0, 5})) == {"magic imprint", "magic imprint, replacing", "restore", "other"}
    assert _names(table, table.closure({4})) == {"magic imprint", "magic imprint, replacing", "rare imprint", "rare imprint, replacing", "restore"}


@dataclasses.dataclass(frozen=True)
class _View:
    rarity: Rarity
    imprints: tuple = ()


class _ReplacingImprint:
    """An imprint that replaces the one the item holds: refused on an item with room, made on one holding an imprint."""

    def imprint_move(self):
        return SimpleNamespace(restore=False, index=0)

    def outcomes(self, data, item):
        if not item.imprints:
            raise NotApplicableError("the item has room for another imprint")
        return SimpleNamespace(results=())


def test_an_imprint_that_replaces_one_is_read_as_made_at_the_shape_whose_item_holding_an_imprint_takes_it():
    table = _table()
    assert table._copies(_ReplacingImprint(), _View(MAGIC)) is True
    restore = SimpleNamespace(imprint_move=lambda: SimpleNamespace(restore=True, index=0))
    assert table._copies(restore, _View(MAGIC)) is False  # a restore makes no imprint


# --- J4: the other lockers come where a step of the plan uses the bench lock --------------------------------------------------------------


def test_a_bench_lock_brings_the_beast_lock_only_where_a_step_of_the_plan_in_hand_uses_it():
    table = _lock_world()
    table.held_back = frozenset()
    suffix_lock, beast = 1, 3
    assert _names(table, table.closure({suffix_lock})) == {"lock suffixes"}  # named as a protector, unused yet: main brought the beast
    assert _names(table, table.closure({suffix_lock}, frozenset({suffix_lock}))) == {"lock suffixes", "beast lock"}
    assert _names(table, table.closure({beast}, frozenset({beast}))) == {"beast lock"}  # a beast brings no bench lock


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


def test_on_r17_the_move_to_rare_is_the_alchemy_both_beast_swaps_are_held_back_and_the_fenumal_pair_comes_without_the_croaker_pair():
    table, at = _real_table("r17-lightning-talisman")
    held = _growth.Grower(table, ()).later_ones
    assert {at["Beastcraft Add Suffix Remove Prefix"], at["Beastcraft Add Prefix Remove Suffix"]} <= held  # main: the first escaped
    assert table.entries[at["Beastcraft Add Suffix Remove Prefix"]].fans == _growth.REMOVES_AND_ADDS
    assert _names(table, table.move_to(frozenset({NORMAL}), RARE)) == {"Orb of Alchemy"}  # main: Whispering Essence of Greed
    table.held_back = frozenset()
    fenumal = "Imprint with the Fenumal Plagued Arachnid"
    assert _names(table, table.closure({at[fenumal]})) == {fenumal, f"{fenumal}, replacing imprint 1", "Restore imprint 1"}


def test_on_r24_a_bench_lock_brings_the_matron_only_where_the_plan_in_hand_uses_it():
    table, at = _real_table("r24-avoid-shock-boots")
    matron, lock = "Beastcraft Wild Bristle Matron (add a metamod)", "Bench craft Suffixes Cannot Be Changed"
    table.held_back = frozenset()
    assert _names(table, table.closure({at[lock]})) == {lock}
    assert _names(table, table.closure({at[lock]}, frozenset({at[lock]}))) == {lock, matron}
