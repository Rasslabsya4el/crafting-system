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
from crafting_system.abstraction import Goal, Wanted
from crafting_system.abstraction._bound import Holdable, _added_chance, holdable
from crafting_system.actions import ExaltedOrb, HarvestAddRemove, NotApplicableError, OutOfScopeError, PoolFamily, PoolMod
from crafting_system.items import ExplicitMod, Item, ItemError, Rarity, Side
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
    held = singles(pool)

    assert _added_chance(pool, free, None, frozenset(), passing, held) == Fraction(1, 10)
    assert _added_chance(pool, free, None, frozenset({"caster"}), passing, held) == 1
    # an open suffix side whose one family is held is closed again: holding it is one of the counts the bound ranges over
    assert _added_chance(pool, {Side.PREFIX: 1, Side.SUFFIX: 1}, None, frozenset(), passing, held) == Fraction(1, 10)
    # a draw of one tag (a Harvest addition) keeps only the mods of that tag
    assert _added_chance(pool, free, "caster", frozenset(), passing, held) == 0


def singles(pool) -> dict[Side, Holdable]:
    """Each side able to hold a one-family mod of every family of `pool` on that side, and no mod of several families."""
    return {side: Holdable(frozenset(entry.family for entry in pool if entry.side is side), ()) for side in Side}


def test_a_held_mod_of_several_families_takes_them_all_out_and_a_hybrid_of_the_other_side_counts_on_this_one():
    # #1489, the checker's toy pool: four suffix families of one weight, FireRes wanted, room for one more suffix
    pool, passing = pool_of(*(family(name, Side.SUFFIX, 100, wanted=name == "FireRes") for name in ("Str", "Dex", "FireRes", "ColdRes")))
    free = {Side.PREFIX: 0, Side.SUFFIX: 2}
    one = singles(pool)
    two = {Side.PREFIX: Holdable(frozenset(), ()), Side.SUFFIX: Holdable(frozenset({"Str", "Dex", "FireRes", "ColdRes"}), (frozenset({"Str", "Dex"}),))}
    # one family per held slot gives 1/3; a Str/Dex hybrid held takes two out, FireRes then has half of the weight left
    assert _added_chance(pool, free, None, frozenset(), passing, one) == Fraction(1, 3)
    assert _added_chance(pool, free, None, frozenset(), passing, two) == Fraction(1, 2)
    # a prefix that holds suffix families (none in the game data, but the item model does not forbid one) takes them out of the suffix draw
    cross = {Side.PREFIX: Holdable(frozenset(), (frozenset({"Str", "Dex", "Mana"}),)), Side.SUFFIX: Holdable(frozenset(), ())}
    assert _added_chance(pool, {Side.PREFIX: 1, Side.SUFFIX: 1}, None, frozenset(), passing, cross) == Fraction(1, 2)
    # a family not in the draw takes nothing out of it: the count is the families of this draw only
    other = {Side.PREFIX: Holdable(frozenset(), ()), Side.SUFFIX: Holdable(frozenset({"Str"}), (frozenset({"Str", "Elsewhere"}),))}
    assert _added_chance(pool, free, None, frozenset(), passing, other) == Fraction(1, 3)


def brute_added_chance(pool, free, passing, mods_by_side) -> Fraction:
    """The largest chance of X over every set of held mods (each side at most its free slots, `mods_by_side` the family sets each side may
    hold, no family twice): the exact chance at each such item, with a side open while it holds fewer mods than its room."""
    best = Fraction(0)
    choices = {side: [()] + [combo for count in range(1, free[side] + 1) for combo in itertools.combinations(mods_by_side[side], count)] for side in Side}
    for prefixes in choices[Side.PREFIX]:
        for suffixes in choices[Side.SUFFIX]:
            groups = [*prefixes, *suffixes]
            gone = set().union(*groups) if groups else set()
            if sum(len(group) for group in groups) != len(gone):
                continue  # two held mods of one family: no such item
            open_sides = {side for side, held in ((Side.PREFIX, prefixes), (Side.SUFFIX, suffixes)) if len(held) < free[side]}
            left = [entry for entry in pool if entry.side in open_sides and entry.family not in gone]
            whole = sum((entry.weight for entry in left), Fraction(0))
            if whole:
                best = max(best, sum((entry.weight for entry in left if passing[entry.family]), Fraction(0)) / whole)
    return best


def test_the_bound_is_never_below_the_brute_force_over_random_pools_whose_sides_hold_hybrids():
    # #1489: random pools of both sides, each side able to hold every one-family mod of its families and a few hybrids (some of them across the
    # sides); the bound is never below the exact chance at any item of held mods, and is reached when the hybrids are the only way to it
    import random

    rng = random.Random(1489)
    reached = 0
    for _ in range(150):
        names = {side: [f"{side.value[0]}{index}" for index in range(rng.randint(1, 4))] for side in Side}
        entries = [family(name, side, rng.randint(1, 9), wanted=rng.random() < 0.3) for side in Side for name in names[side]]
        pool, passing = pool_of(*entries)
        free = {side: rng.randint(0, 2) for side in Side}
        everyone = [name for side in Side for name in names[side]]
        hybrids = {side: [frozenset(rng.sample(everyone, min(len(everyone), rng.randint(2, 3)))) for _ in range(rng.randint(0, 2))] for side in Side}
        mods_by_side = {side: [frozenset({name}) for name in names[side]] + hybrids[side] for side in Side}
        held = {side: Holdable(frozenset(names[side]), tuple(hybrids[side])) for side in Side}
        bound = _added_chance(pool, free, None, frozenset(), passing, held)
        exact = brute_added_chance(pool, free, passing, mods_by_side)
        assert exact <= bound, (names, free, hybrids)
        reached += exact == bound
    assert reached > 100  # the bound is loose only where the counts admit sets of families no held mods make


# The toy pool of #1489 on the real data: an amulet whose suffixes are Strength, Dexterity, Fire and Cold Resistance at one weight, a Lightning
# Resistance fractured (two suffix slots left), Life and Mana prefixes, and the crafted Strength and Dexterity suffix, which holds two families.
HYBRID = "JunMasterStrengthAndDexterity1"
TOY_SUFFIXES = ("Strength1", "Dexterity1", "FireResist1", "ColdResist1")
TOY_PREFIXES = ("IncreasedLife1", "IncreasedMana1")
TOY_FRACTURED = "LightningResist1"
REAL_AMULET = "Metadata/Items/Amulets/Amulet1"


def toy_data():
    from crafting_system.data.model import Weight

    data = real_game_data()
    mods = {}
    for mod_id in (*TOY_SUFFIXES, *TOY_PREFIXES, TOY_FRACTURED, HYBRID):
        mod = data.mods[mod_id]
        if mod.domain == "item":
            mod = dataclasses.replace(mod, spawn_weights=(Weight("amulet", 100), Weight("default", 0)))
        mods[mod_id] = mod
    return dataclasses.replace(data, mods=mods)


def toy_roll(data, mod_id: str, **flags) -> ExplicitMod:
    return ExplicitMod(mod_id, tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats), crafted=data.mods[mod_id].domain == "crafted", **flags)


def toy_item(data, *mod_ids: str) -> Item:
    mods = (toy_roll(data, TOY_FRACTURED, fractured=True), *(toy_roll(data, mod_id) for mod_id in mod_ids))
    return Item.build(data, base_id=REAL_AMULET, item_level=LEVEL, rarity=Rarity.RARE, mods=mods)


def toy_members(ab, data):
    """Every member of the toy shape without Fire Resistance (a suffix side full is left out: no Exalted Orb there), with the exact chance
    that one Exalted Orb puts Fire Resistance on it."""
    suffixes = [(), *((mod,) for mod in TOY_SUFFIXES if mod != "FireResist1"), (HYBRID,)]
    for prefixes in itertools.product(*((None, mod) for mod in TOY_PREFIXES)):
        for first, second in itertools.combinations_with_replacement(range(len(suffixes)), 2):
            held = [mod for mod in prefixes if mod] + [*suffixes[first], *suffixes[second]]
            if len(set(held)) != len(held) or (HYBRID in held and {"Strength1", "Dexterity1"} & set(held)):
                continue
            try:
                kernel = ab.kernel(ab.compress(toy_item(data, *held)), EXALTED)
            except NotApplicableError:
                continue
            yield tuple(held), sum((chance for state, chance in kernel.items() if state.status[0] == PASSING), Fraction(0))


def test_the_toy_pool_with_a_hybrid_held_through_the_bound_s_entry_and_every_member_of_its_shape():
    # #1489: before, the bound counted one family out per held slot and gave 1/3, below the 1/2 of the item that holds the hybrid
    data = toy_data()
    ab = Abstraction(data, Goal((Wanted(frozenset({"FireResist1"})),)), REAL_AMULET, LEVEL, [EXALTED])
    assert holdable(data, REAL_AMULET)[Side.SUFFIX].most(frozenset({"Strength", "Dexterity", "FireResistance", "ColdResistance"})) == 2
    bound = add_bound(ab, ab.compress(toy_item(data)), EXALTED, (0,))
    chances = dict(toy_members(ab, data))
    assert chances[(*TOY_PREFIXES, HYBRID)] == Fraction(1, 2)  # both prefixes held too: Fire and Cold Resistance alone are left in the draw
    assert chances[(HYBRID,)] == Fraction(1, 4)
    assert chances[()] == Fraction(1, 6)
    assert len(chances) > 20
    assert all(chance <= bound for chance in chances.values()), max(chances.items(), key=lambda pair: pair[1])
    assert bound == Fraction(1, 2) == max(chances.values())


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


# #1506: R20's Shaper/Elder Eternal Burgonet. A suffix of the Essence of Horror (family Supported) and a Crusader suffix (MinionLife) share a
# family with a Shaper prefix, so a held one takes that prefix out of the draw; #1490's count, read per base, raised every addition's bound
# to the Area Damage prefix at the magic shape, where neither can be held (an essence makes a rare; the shape's influences are Shaper and Elder).
R20_HELMET = "Metadata/Items/Armours/Helmets/HelmetStr11"
AREA_PREFIX = "AreaDamageSupportedUber3"
HORROR_SUFFIX = "SocketedGemsDealMoreElementalDamageEssence1"


def r20_item(data, rarity: Rarity, *mod_ids: str) -> Item:
    from crafting_system.items import Influence

    mods = tuple(toy_roll(data, mod_id) for mod_id in mod_ids)
    return Item.build(data, base_id=R20_HELMET, item_level=86, rarity=rarity, mods=mods, influences=frozenset({Influence.SHAPER, Influence.ELDER}))


def test_below_rare_the_held_mods_are_what_a_pool_draw_or_the_bench_gives_the_shape_and_its_own_mods():
    data = real_game_data()
    rare, magic = holdable(data, R20_HELMET), holdable(data, R20_HELMET, r20_item(data, Rarity.MAGIC))
    for family in ("Supported", "MinionLife"):
        assert rare[Side.SUFFIX].most(frozenset({family})) == 1
        assert magic[Side.SUFFIX].most(frozenset({family})) == 0
    assert holdable(data, R20_HELMET, r20_item(data, Rarity.RARE)) is rare  # a rare shape keeps #1490's count
    assert magic[Side.SUFFIX].most(frozenset({"Strength", "Dexterity"})) == 2  # the bench's hybrid attribute suffix is still held
    given = holdable(data, R20_HELMET, r20_item(data, Rarity.MAGIC), (HORROR_SUFFIX,))  # a mod the shape's item was given counts again
    assert given[Side.SUFFIX].most(frozenset({"Supported"})) == 1


def test_the_bound_on_r20_s_area_prefix_at_the_magic_shape_covers_every_member_and_the_order_s_figure_is_not_a_bound():
    from crafting_system.actions.magic import AugmentationOrb
    from crafting_system.actions.pool import item_tags
    from crafting_system.actions.scour import ScouringOrb
    from crafting_system.items.spawn import spawn_weight

    data = real_game_data()
    augment = AugmentationOrb()
    ab = Abstraction(data, Goal((Wanted(frozenset({AREA_PREFIX})),)), R20_HELMET, 86, [augment], metamods=True)
    plain = Abstraction(data, Goal((Wanted(frozenset({AREA_PREFIX})),)), R20_HELMET, 86, [augment])
    bare = r20_item(data, Rarity.MAGIC)
    tags = frozenset(item_tags(data, bare))
    klass = data.base_items[R20_HELMET].item_class
    crafted = {option.actions.add_explicit_mod for option in data.bench_options if klass in option.item_classes and option.actions.add_explicit_mod}
    suffixes = [mod.id for mod in data.mods.values() if mod.domain == "item" and mod.generation_type == "suffix" and spawn_weight(mod, tags) > 0]
    suffixes += sorted(mod_id for mod_id in crafted if data.mods[mod_id].generation_type == "suffix")
    # a rare with the Horror suffix and Suffixes Cannot Be Changed, scoured, is a magic helmet that holds the Horror suffix
    lock = next(mod.id for mod in data.mods.values() if mod.domain == "crafted" and "ItemGenerationCannotChangeSuffixes" in mod.families)
    scoured = ScouringOrb().outcomes(data, r20_item(data, Rarity.RARE, HORROR_SUFFIX, lock)).retained
    assert scoured.rarity is Rarity.MAGIC and [entry.mod_id for entry in scoured.mods] == [HORROR_SUFFIX]
    for abstraction in (ab, plain):
        bound = add_bound(abstraction, abstraction.compress(bare), augment, (0,))
        ranked = add_bound(abstraction, abstraction.compress(bare), augment, (0,), ranking=True)
        chances = {}
        for suffix in (None, HORROR_SUFFIX, *suffixes):  # every magic member with the prefix side open, the scoured one among them
            try:
                item = bare if suffix is None else r20_item(data, Rarity.MAGIC, suffix)
                kernel = abstraction.kernel(abstraction.compress(item), augment)
            except (ItemError, OutOfScopeError):  # a bench suffix this base refuses, a metamod the plain model leaves out
                continue
            chances[suffix] = sum((chance for state, chance in kernel.items() if state.status[0] == PASSING), Fraction(0))
        assert len(chances) > 50
        assert all(chance <= bound for chance in chances.values()), max(chances.items(), key=lambda pair: pair[1])
        assert ranked < bound  # the order's figure leaves the Horror suffix out of the magic shape (R20: 0.015362 against 0.019014)
        assert add_bound(abstraction, abstraction.compress(bare), augment, (0,)) == bound  # a ranking call leaves the bound's count as it was
        if abstraction is plain:
            # ... and so it is not a bound: below the chance at the scoured member (0.013968 against 0.013775), which is why no floor reads it
            assert ranked < chances[HORROR_SUFFIX]
