"""The bound of one added mod (`add_bound`, #1072): the chance that an Exalted Orb passes a missing leaf, from ANY state of the shape.

The floors of the planner's offers (`planner/_offer_kinds`, pbar of an addition) need a number that is never below the chance of one use from
any state of the start's shape at which the leaf is not passing. Checked here: (1) on the small amulet pool, against the exact chance of the
kernel at every member state of the shape (every set of families and mods the item may hold besides its fractured one), and that the chance at
the bare item alone is NOT such a number (a member's chance is above it, so a bound read at the bare item would be caught by (1)); (2) the
Attack and Caster metamods, which take tagged mods out of the draw and so raise the share of the rest; (3) where the draw is not the same at
every state of the shape (a draw cut by Memory Strands), or the action is not one drawn mod, no bound is given and the offer stays terminal;
(4) through the planner's entry on R12 with the Exalted Orb offered: the orb's round ends on a lower figure at the plan's cost, and the plan is
as cheap as without the orb (it cannot help R12).

Every test here plans with the CLASSIC offers (`cli_support.CLASSIC_KINDS`, `CLASSIC_OFFERS` below): what a target with no
`actions:` was offered before #886 turned every beta method on, so its records of before hold. It is not a test of the default plan:
with every method on, a real route gives no plan within CI's time and memory, and the heavy benchmark records those plans.
"""

import dataclasses
import importlib
import itertools
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from abstraction_pool import (
    COLD_GEM,
    COLD_RESIST,
    DAMAGE_1,
    DAMAGE_2,
    FIRE_GEM,
    FIRE_RESIST,
    GEM,
    LEVEL,
    LIFE_1,
    LIFE_2,
    MANA_1,
    MANA_2,
    RESIST_2,
    SMALL,
    roll,
    small_item,
)
from abstraction_support import GOALS, PASSING, real_game_data
from items_support import AMULET

from crafting_system.abstraction import Abstraction, add_bound
from crafting_system.abstraction._bound import _added_chance
from crafting_system.actions import ExaltedOrb, HarvestAddRemove, NotApplicableError, PoolFamily, PoolMod
from crafting_system.items import Rarity, Side
from crafting_system.planner import _offer_kinds

CLASSIC_OFFERS = True  # tests/conftest.py: this module plans with `cli_support.CLASSIC_KINDS` (#886)

EXALTED = ExaltedOrb()
GEM_LEAF = 0  # GOALS["r12"] is (gem, resist); the fractured Lightning Resistance passes the second
PREFIXES = ((None, GEM, FIRE_GEM, COLD_GEM), (None, DAMAGE_1, DAMAGE_2), (None, LIFE_1, LIFE_2))
SUFFIXES = ((None, COLD_RESIST), (None, FIRE_RESIST), (None, MANA_1, MANA_2))
SUFFIX_ROOM = 2  # three suffixes, one of them the fractured resistance


def exalted_abstraction(*, metamods: bool = False) -> Abstraction:
    return Abstraction(SMALL, GOALS["r12"], AMULET, LEVEL, [EXALTED], metamods=metamods)


def members(ab: Abstraction):
    """Every rare amulet of the shape (Lightning Resistance fractured, nothing else fixed) without the gem mod, with the exact chance that one
    Exalted Orb puts the gem mod on it."""
    for combo in itertools.product(*PREFIXES, *SUFFIXES):
        mods = [mod for mod in combo if mod]
        if GEM in mods or sum(mod in (COLD_RESIST, FIRE_RESIST, MANA_1, MANA_2) for mod in mods) > SUFFIX_ROOM:
            continue
        item = small_item(roll(RESIST_2, fractured=True), *(roll(mod) for mod in mods))
        try:
            kernel = ab.kernel(ab.compress(item), EXALTED)
        except NotApplicableError:
            continue  # a full item: no chance at all
        yield tuple(mods), sum((chance for state, chance in kernel.items() if state.status[GEM_LEAF] == PASSING), Fraction(0))



def _raised_add(ab, state, chosen, action, level, pbar):
    """`_offer_kinds._raised_add` at the shape of `state` (its item read back from it), as `(kind, pbar, level)`."""
    item = ab._item_of(state, True)[0]
    view = _offer_kinds.ShapeView(ab, dataclasses.replace(state, slots=()), item, tuple(chosen))
    return _offer_kinds._raised_add(view, action, _offer_kinds.ADD, level, pbar)[:3]

def test_the_bound_is_never_below_the_exact_chance_at_any_member_and_the_chance_at_the_bare_item_is_no_bound():
    ab = exalted_abstraction()
    bare = ab.compress(small_item(roll(RESIST_2, fractured=True)))
    bound = add_bound(ab, bare, EXALTED, (GEM_LEAF,))
    chances = dict(members(ab))

    assert len(chances) > 100  # every set of families the shape may hold, full sides left out
    assert all(chance <= bound for chance in chances.values()), max(chances.items(), key=lambda pair: pair[1])
    at_bare = chances[()]
    assert at_bare == Fraction(1, 38)  # the gem mod's weight over the whole pool of the bare item
    higher = {mods: chance for mods, chance in chances.items() if chance > at_bare}
    assert higher  # members draw it more often: a bound read at the bare item alone is not one
    # the most favourable share is reached: the gem family alone left in the draw (both other prefixes held, the suffix side full), 1 in 3
    assert bound == max(chances.values()) == Fraction(1, 3)


def test_a_leaf_already_passing_everywhere_and_a_leaf_no_added_mod_passes_give_what_the_pool_says():
    ab = exalted_abstraction()
    bare = ab.compress(small_item(roll(RESIST_2, fractured=True)))
    # the resistance leaf: no Lightning Resistance can be added (the family is held), so the chance is 0 at every member
    assert add_bound(ab, bare, EXALTED, (1,)) == 0
    assert add_bound(ab, bare, EXALTED, (GEM_LEAF, 1)) == add_bound(ab, bare, EXALTED, (GEM_LEAF,))
    with pytest.raises(ValueError):
        add_bound(ab, bare, EXALTED, ())


def family(name: str, side: Side, weight: int, *, tags=(), wanted: bool = False) -> tuple[PoolFamily, dict[str, bool]]:
    mod = SimpleNamespace(id=name, implicit_tags=tuple(tags))
    return PoolFamily(name, side, (PoolMod(mod, Fraction(weight)),)), {name: wanted}


def pool_of(*families):
    return [entry for entry, _ in families], {key: value for _, flags in families for key, value in flags.items()}


def test_a_metamod_that_keeps_tagged_mods_out_raises_the_share_and_the_bound_takes_every_set_of_blocked_tags():
    # one free prefix: no family can be held besides the bare item's, so only the tags can take the caster family's weight out of the draw
    pool, passing = pool_of(
        family("wanted", Side.PREFIX, 1, wanted=True), family("spell", Side.PREFIX, 9, tags=("caster",)), family("hit", Side.SUFFIX, 5, tags=("attack",))
    )
    free = {Side.PREFIX: 1, Side.SUFFIX: 0}

    assert _added_chance(pool, free, None, frozenset(), passing) == Fraction(1, 10)
    assert _added_chance(pool, free, None, frozenset({"caster"}), passing) == 1
    # an open suffix side whose one family is held is closed again: holding it is one of the counts the bound ranges over
    assert _added_chance(pool, {Side.PREFIX: 1, Side.SUFFIX: 1}, None, frozenset(), passing) == Fraction(1, 10)
    # a draw of one tag (a Harvest addition) keeps only the mods of that tag
    assert _added_chance(pool, free, "caster", frozenset(), passing) == 0


def test_the_bound_with_metamods_modelled_is_never_below_the_bound_without():
    plain = exalted_abstraction()
    fine = exalted_abstraction(metamods=True)
    item = small_item(roll(RESIST_2, fractured=True))
    assert add_bound(fine, fine.compress(item), EXALTED, (GEM_LEAF,)) >= add_bound(plain, plain.compress(item), EXALTED, (GEM_LEAF,))


def test_a_draw_cut_by_memory_strands_gets_no_bound_and_its_offer_stays_terminal():
    # the uses before it spend strands by the number of mods held, so the states of the shape draw from other cuts than the bare item's
    ab = exalted_abstraction()
    bare = dataclasses.replace(ab.compress(small_item(roll(RESIST_2, fractured=True))), strands=10)
    assert add_bound(ab, bare, EXALTED, (GEM_LEAF,)) is None
    assert _raised_add(ab, bare, (GEM_LEAF,), EXALTED, 0, Fraction(1)) == (_offer_kinds.TERMINAL, Fraction(1), 1)


def test_an_action_that_is_not_one_drawn_mod_and_a_refusal_it_may_outgrow_leave_the_offer_terminal():
    ab = Abstraction(SMALL, GOALS["r12"], AMULET, LEVEL, [EXALTED, HarvestAddRemove("lightning")])
    bare = ab.compress(small_item(roll(RESIST_2, fractured=True)))
    # a Harvest add/remove also removes a mod: its result is not one drawn mod added to the mods kept
    held = ab.compress(small_item(roll(RESIST_2, fractured=True), roll(LIFE_1)))
    assert add_bound(ab, held, HarvestAddRemove("lightning"), (GEM_LEAF,)) is None
    assert _raised_add(ab, held, (GEM_LEAF,), HarvestAddRemove("lightning"), 0, Fraction(1))[0] == _offer_kinds.TERMINAL
    # at the bare item it has nothing to remove: refused there, which proves nothing for a state holding more mods (the catalog lists it for the
    # shape's item, a Rare one)
    assert _raised_add(ab, bare, (GEM_LEAF,), HarvestAddRemove("lightning"), 0, Fraction(1))[0] == _offer_kinds.TERMINAL
    # refused at the bare item of a Magic shape (a Magic item takes no Exalted Orb), which has the most room of the shape: an addition that keeps
    # every mod is refused at every state of the shape too, so it is set aside (#973: before, it stayed terminal at its price, as the Regal Orb
    # did on R05's Rare start); the Harvest add/remove above, which also removes a mod, stays terminal
    magic = ab.compress(small_item(roll(RESIST_2, fractured=True), rarity=Rarity.MAGIC))
    assert _raised_add(ab, magic, (GEM_LEAF,), EXALTED, 0, Fraction(1)) == (_offer_kinds.REFUSED, Fraction(1), 1)
    # at its top level an addition is not raised again
    assert _raised_add(ab, bare, (GEM_LEAF,), EXALTED, 1, Fraction(1, 3)) == (_offer_kinds.ADD, Fraction(1, 3), 1)
    assert _offer_kinds.raisable(_offer_kinds.ADD, 0) and not _offer_kinds.raisable(_offer_kinds.ADD, 1)


def test_through_the_entry_r12_with_the_exalted_orb_offered_gets_its_exact_plan_as_cheap_as_without(monkeypatch):
    # Before #1072 the Exalted Orb's floor was its price (it counted as finishing the item), the round's lower figure fell to one orb, and
    # R12 had no plan in 900 s (#1069, probe 3). The orb cannot help R12, so the plan is the one without it, proved exact.
    data = real_game_data()
    from crafting_system.budget import Budget
    from crafting_system.cli import _benchmark
    from crafting_system.planner import PlanSettings, plan_target
    from crafting_system.prices import load_price_file
    from crafting_system.targets import load_target

    root = Path(__file__).resolve().parents[1]
    bench = next(entry for entry in _benchmark.BENCHMARKS if entry.id == "R12")
    prices = load_price_file(root / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json")
    target = load_target(root / bench.target, data)
    settings = PlanSettings(recipe_starts=False, budget=Budget(aim_seconds=None, seconds=600, memory_mb=None))

    without = plan_target(data, target, prices, settings)
    catalog = importlib.import_module("crafting_system.actions.catalog")
    monkeypatch.setitem(catalog._KINDS, "exalted-orb", dataclasses.replace(catalog._KINDS["exalted-orb"], opt_in=False))
    with_orb = plan_target(data, target, prices, settings)

    search = with_orb.search
    assert search.stopped is None
    assert with_orb.mean_remaining == pytest.approx(without.mean_remaining, rel=1e-9)
    (exalted,) = [record for record in search.widening if "exalted-orb" in record.kinds]
    # the round's lower figure is the plan's cost (to the float slack of rho), not one orb's price: the round ends on it, it is not cut
    assert exalted.status in ("closed", "beaten") and exalted.lower >= search.upper * (1 - 1e-9)
    assert search.lower >= search.upper * (1 - 1e-9)
