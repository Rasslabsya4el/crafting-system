"""The upper bound on reaching goal leaves with one reroll (`reach_bound`, ticket #118, verification layer 1).

Three checks. (1) On the fixture pools (the small amulet pool and the belt) the exact value
(`exact=True`) equals the brute-force oracle's chance, and the bound is never below it, for the actions
the fixtures use, for single leaves and subsets of leaves, and for states that hold 0 to 3 fractured
mods (some of which fill a side). (2) On 400 random small synthetic pools, the bound of the pool
alone is never below the exact chance of `exact_distribution`. (3) On the real Sorcerer Boots, a
tightness report (printed, not asserted) against the exact chance for a Chaos Orb and for fossil sets;
it needs the cached dump and skips without it.
"""

import itertools
import random
from fractions import Fraction
from types import SimpleNamespace

import pytest
from abstraction_oracle import finished_items
from abstraction_pool import (
    COLD_RESIST,
    FIRE_RESIST,
    GEM,
    LIFE_1,
    MANA_1,
    RESIST_1,
    RESIST_2,
    fractured_item,
    small_item,
)
from abstraction_pool import LEVEL as AMULET_LEVEL
from abstraction_pool import roll as small_roll
from abstraction_support import (
    CHAOS,
    DAMAGE_LEAF,
    GEM_LEAF,
    LIFE_LEAF as AMULET_LIFE_LEAF,
    MANA_LEAF,
    PASSING,
    REFORGE,
    RESIST_LEAF,
    RESIST_TIER_2,
    abstraction,
    expected_kernel,
    real_game_data,
)
from items_support import DATA
from items_support import roll as belt_roll
from test_abstraction_b1 import (
    COLD,
    COLD_LEAF,
    DAMAGE,
    FIRE,
    HATRED,
    HYSTERIA,
    HYSTERIA_LEAF,
    HYSTERIA_MOD,
    LIFE,
    LIFE_LEAF,
    LIGHTNING,
    SHIELD_LEAF,
    belt,
)
from test_abstraction_b1 import BELT
from test_abstraction_b1 import LEVEL as BELT_LEVEL

from crafting_system.abstraction import Abstraction, Goal, Wanted, reach_bound
from crafting_system.abstraction._bound import (
    _draw_chance,
    _guaranteed_chance,
    _joint_hits,
    _leaf_bound,
    _part_bound,
    _sides,
)
from crafting_system.actions import ActionError, ApplyFossils, ChaosOrb, PoolFamily, PoolMod, build_pool
from crafting_system.actions.draw import exact_distribution
from crafting_system.actions.fossil import fossil_actions
from crafting_system.items import Item, Rarity, Side

ZERO, ONE = Fraction(0), Fraction(1)

# --- layer 1 on the fixture pools -----------------------------------------------------------------

AMULET_LEAVES = (GEM_LEAF, RESIST_LEAF, RESIST_TIER_2, DAMAGE_LEAF, MANA_LEAF, AMULET_LIFE_LEAF)
AMULET_GOAL = Goal(AMULET_LEAVES)
SUBSETS = [
    *((i,) for i in range(6)),
    *itertools.combinations(range(6), 2),
    (0, 1, 3),
    (0, 1, 2, 3, 4, 5),
]
AMULET_STARTS = {
    "empty": lambda level: small_item(level=level),
    "one-resist": lambda level: fractured_item(RESIST_1, level=level),
    "tier-1-resist-and-mana": lambda level: fractured_item(RESIST_2, MANA_1, level=level),
    "full-suffixes": lambda level: fractured_item(RESIST_1, COLD_RESIST, FIRE_RESIST, level=level),
    "gem-and-life": lambda level: fractured_item(GEM, LIFE_1, level=level),
    "mixed": lambda level: fractured_item(GEM, COLD_RESIST, level=level),
    "junk-too": lambda level: small_item(small_roll(RESIST_1, fractured=True), small_roll(LIFE_1), level=level),
}


def oracle_chance(ab, start, action, leaves, **oracle) -> Fraction:
    """The brute-force chance that every leaf of `leaves` is PASSING after the action."""
    return sum(
        (
            chance
            for state, chance in expected_kernel(ab, start, action, **oracle).items()
            if all(state.status[index] is PASSING for index in leaves)
        ),
        ZERO,
    )


def check_all_subsets(ab, start, action, subsets, **oracle) -> int:
    """For each subset: exact equals the oracle, the bound is at least that and at most 1. Returns the count."""
    state = ab.compress(start)
    for leaves in subsets:
        exact = reach_bound(ab, state, action, leaves, exact=True)
        bound = reach_bound(ab, state, action, leaves)
        want = oracle_chance(ab, start, action, leaves, **oracle)
        assert exact == want, f"{leaves}: exact {exact} but the oracle says {want}"
        assert want <= bound <= 1, f"{leaves}: bound {float(bound)} below the exact {float(want)}"
    return len(subsets)


@pytest.mark.parametrize("level", [AMULET_LEVEL, 70])
@pytest.mark.parametrize("name", AMULET_STARTS)
@pytest.mark.parametrize("action", [CHAOS, REFORGE], ids=["chaos", "reforge"])
def test_exact_equals_the_oracle_and_the_bound_is_not_below_on_the_small_amulet(action, name, level):
    ab = abstraction(AMULET_GOAL, level)
    start = AMULET_STARTS[name](level)
    try:
        action.outcomes(ab.data, start)
    except ActionError:
        pytest.skip("the action refuses this item")

    assert check_all_subsets(ab, start, action, SUBSETS) == len(SUBSETS)


BELT_LEAVES = (LIFE_LEAF, COLD_LEAF, SHIELD_LEAF, HYSTERIA_LEAF)
BELT_SUBSETS = [*((i,) for i in range(4)), *itertools.combinations(range(4), 2), (0, 1, 2), (0, 1, 2, 3)]
BELT_STARTS = {
    "empty": lambda: belt(),
    "fractured-fire": lambda: belt(belt_roll(FIRE, fractured=True)),
    "fractured-fire-and-cold-with-junk": lambda: belt(
        belt_roll(FIRE, fractured=True), belt_roll(COLD, fractured=True), belt_roll(LIFE)
    ),
    "fractured-life": lambda: belt(belt_roll(LIFE, fractured=True)),
    "full-suffixes": lambda: belt(
        belt_roll(FIRE, fractured=True), belt_roll(COLD, fractured=True), belt_roll(LIGHTNING, fractured=True)
    ),
}


@pytest.mark.parametrize("name", BELT_STARTS)
@pytest.mark.parametrize("action", ["chaos", "hysteria"])
def test_exact_equals_the_oracle_and_the_bound_is_not_below_on_the_belt(name, action):
    ab = Abstraction(DATA, Goal(BELT_LEAVES), BELT, BELT_LEVEL)
    start = BELT_STARTS[name]()
    oracle = {"data": DATA}
    if action == "hysteria":
        act, oracle["forced"] = HYSTERIA, HYSTERIA_MOD
    else:
        act = ChaosOrb()
    try:
        act.outcomes(DATA, start)
    except ActionError:
        pytest.skip("the action refuses this item")

    check_all_subsets(ab, start, act, BELT_SUBSETS, **oracle)


def test_a_low_essence_on_a_normal_item_has_an_exact_value_and_a_bound():
    ab = Abstraction(DATA, Goal(BELT_LEAVES), BELT, BELT_LEVEL)
    start = belt(rarity=Rarity.NORMAL)

    check_all_subsets(ab, start, HATRED, BELT_SUBSETS, data=DATA, forced=COLD, cap=35)

    state = ab.compress(start)
    assert reach_bound(ab, state, HATRED, [1]) == 1  # the forced cold resistance makes that leaf PASSING


def test_a_leaf_a_kept_mod_already_passes_costs_nothing():
    ab = abstraction(AMULET_GOAL)
    state = ab.compress(fractured_item(RESIST_1))

    assert reach_bound(ab, state, CHAOS, [1]) == 1
    assert reach_bound(ab, state, CHAOS, [1, 0]) == reach_bound(ab, state, CHAOS, [0])
    assert reach_bound(ab, state, CHAOS, [1, 0], exact=True) == reach_bound(ab, state, CHAOS, [0], exact=True)


def test_an_unspawnable_leaf_gets_zero():
    ab = abstraction("unspawnable")
    state = ab.compress(small_item())

    assert reach_bound(ab, state, CHAOS, [1]) == 0 == reach_bound(ab, state, CHAOS, [1], exact=True)


def test_a_roll_limit_on_a_mod_in_the_pool_gives_none():
    ab = abstraction(Goal((Wanted(frozenset({GEM}), min_roll=(1,)), GEM_LEAF)))
    state = ab.compress(small_item())

    assert reach_bound(ab, state, CHAOS, [0]) is None
    assert reach_bound(ab, state, CHAOS, [0], exact=True) is None
    assert reach_bound(ab, state, CHAOS, [1]) is not None  # the roll limit is on the other leaf


def test_a_bench_craft_reads_the_junk_so_it_gives_none():
    from crafting_system.actions import BenchCraft

    craft = BenchCraft(DAMAGE)
    ab = Abstraction(DATA, Goal(BELT_LEAVES), BELT, BELT_LEVEL, [craft])

    assert reach_bound(ab, ab.compress(belt()), craft, [0]) is None


def test_an_empty_or_out_of_range_leaves_is_refused():
    ab = abstraction()
    state = ab.compress(small_item())

    with pytest.raises(ValueError):
        reach_bound(ab, state, CHAOS, [])
    with pytest.raises(ValueError):
        reach_bound(ab, state, CHAOS, [5])


# --- the pieces ------------------------------------------------------------------------------------


def family(name, side, *entries):
    """A synthetic family of `(weight, in X, tagged)` mods; the mods are stand-ins with an id and tags."""
    mods = tuple(
        PoolMod(SimpleNamespace(id=f"{name}.{i}", implicit_tags=("t",) if tagged else ()), Fraction(weight))
        for i, (weight, _, tagged) in enumerate(entries)
    )
    return PoolFamily(name, side, mods), {f"{name}.{i}": in_x for i, (_, in_x, _) in enumerate(entries)}


def pool_of(*specs):
    families, passing = [], {}
    for spec in specs:
        fam, flags = family(*spec[:2], *spec[2:])
        families.append(fam)
        passing.update(flags)
    return tuple(families), passing


FREE_2_2 = {Side.PREFIX: 2, Side.SUFFIX: 2}


def test_one_draw_from_a_pool_is_the_weight_share():
    pool, passing = pool_of(("a", Side.PREFIX, (3, True, False)), ("b", Side.PREFIX, (7, False, False)))
    free = {Side.PREFIX: 1, Side.SUFFIX: 0}

    assert _leaf_bound(pool, free, {1: ONE}, 0, None, passing) == Fraction(3, 10)


def test_the_guaranteed_draw_is_the_tagged_share_on_the_sides_with_room():
    pool, passing = pool_of(
        ("a", Side.PREFIX, (2, True, True)),
        ("b", Side.PREFIX, (6, False, True)),
        ("c", Side.SUFFIX, (50, True, True)),  # its side is closed
        ("d", Side.PREFIX, (100, True, False)),  # carries no tag
    )
    free = {Side.PREFIX: 1, Side.SUFFIX: 0}

    assert _guaranteed_chance(pool, free, "t", passing) == Fraction(2, 8)


def test_draws_that_cannot_happen_add_nothing():
    pool, passing = pool_of(("a", Side.PREFIX, (1, True, False)), ("b", Side.SUFFIX, (1, False, False)))
    free = {Side.PREFIX: 1, Side.SUFFIX: 1}

    assert _draw_chance(2, free, _sides(pool, passing)) == 0  # two earlier draws fill both sides
    assert _leaf_bound(pool, free, {6: ONE}, 0, None, passing) == 1


def test_a_mod_that_nothing_can_hit_with_gives_zero_and_a_hopeless_pool_gives_one():
    pool, none = pool_of(("a", Side.PREFIX, (1, False, False)), ("b", Side.SUFFIX, (1, False, False)))
    assert _leaf_bound(pool, FREE_2_2, {4: ONE}, 0, None, none) == 0
    only, passing = pool_of(("a", Side.PREFIX, (1, True, False)))
    assert _leaf_bound(only, FREE_2_2, {4: ONE}, 0, None, passing) == 1


# --- layer 1 on random synthetic pools ------------------------------------------------------------

TOTAL_SETS = [
    {4: Fraction(8, 12), 5: Fraction(3, 12), 6: Fraction(1, 12)},
    {2: ONE},
]


def random_case(rng):
    """A random pool with its free slots, kept mods, totals and tag: `(pool, passing, free, kept, tag, totals)`."""
    specs = []
    for index in range(rng.randint(3, 7)):
        side = rng.choice([Side.PREFIX, Side.SUFFIX])
        entries = [
            (rng.randint(1, 40), rng.random() < 0.35, rng.random() < 0.4) for _ in range(rng.randint(1, 3))
        ]
        specs.append((f"f{index}", side, *entries))
    pool, passing = pool_of(*specs)
    free = {Side.PREFIX: rng.randint(0, 3), Side.SUFFIX: rng.randint(0, 3)}
    kept = (3 - free[Side.PREFIX]) + (3 - free[Side.SUFFIX]) + rng.randint(0, 1)
    tag = "t" if rng.random() < 0.5 else None
    return pool, passing, free, kept, tag, rng.choice(TOTAL_SETS)


def hit_chance(pool, passing, free, kept, tag, totals) -> Fraction:
    """The exact chance, from the exact engine, that a drawn mod is in X."""
    shown = exact_distribution(pool, free, tag, totals, kept, lambda mod: passing[mod.id])
    return sum((chance for outcome, chance in shown.items() if any(flag for flag, _ in outcome)), ZERO)


def joint_chance(pool, passings, free, kept, tag, totals) -> Fraction:
    """The exact chance, from the exact engine, that the drawn mods hit every X of `passings`."""
    shown = exact_distribution(
        pool, free, tag, totals, kept, lambda mod: tuple(passing[mod.id] for passing in passings)
    )
    return sum(
        (
            chance
            for outcome, chance in shown.items()
            if all(any(flags[k] for flags, _ in outcome) for k in range(len(passings)))
        ),
        ZERO,
    )


def test_the_joint_bound_is_never_below_the_exact_chance_on_random_pools():
    rng = random.Random(1180)
    checked = disjoint = 0
    for _ in range(600):
        pool, passing, free, kept, tag, totals = random_case(rng)
        if tag is not None and not any(
            free[family.side] > 0 and any(entry.mod.implicit_tags for entry in family.mods) for family in pool
        ):
            continue
        shapes = rng.choice(["free", "disjoint", "nested"])
        second = {
            mod_id: (rng.random() < 0.35 and not (shapes == "disjoint" and flag)) or (shapes == "nested" and flag)
            for mod_id, flag in passing.items()
        }
        third = {mod_id: rng.random() < 0.3 and not flag and not second[mod_id] for mod_id, flag in passing.items()}
        passings = rng.choice([[passing, second], [passing, second, third]])
        exact = joint_chance(pool, passings, free, kept, tag, totals)
        bound = _part_bound(pool, free, totals, kept, tag, passings)
        assert exact <= bound <= 1, f"joint bound {float(bound)} below exact {float(exact)}"
        singles = [_leaf_bound(pool, free, totals, kept, tag, each) for each in passings]
        assert bound <= min(singles)
        checked += 1
        disjoint += shapes == "disjoint"
    assert checked >= 200 and disjoint >= 50


def test_two_disjoint_leaves_need_two_different_draws():
    one = [Fraction(1, 2), Fraction(1, 2)]

    assert _joint_hits([one, one], 1) == 0  # a single draw cannot hit two disjoint sets
    assert _joint_hits([one, one], 2) == Fraction(1, 2)  # 2 * (1/2 * 1/2)
    assert _joint_hits([one, one, one], 2) == 0


def test_the_bound_is_never_below_the_exact_chance_on_random_pools():
    rng = random.Random(118)
    checked = tight = 0
    for _ in range(600):
        pool, passing, free, kept, tag, totals = random_case(rng)
        if tag is not None and not any(
            free[family.side] > 0 and any(entry.mod.implicit_tags for entry in family.mods) for family in pool
        ):
            continue  # a tagged reforge needs a tagged mod it can draw first
        exact = hit_chance(pool, passing, free, kept, tag, totals)
        bound = _leaf_bound(pool, free, totals, kept, tag, passing)
        assert exact <= bound <= 1, f"bound {float(bound)} below exact {float(exact)}: {pool} {free} {kept} {tag} {totals}"
        checked += 1
        tight += exact == bound
    assert checked >= 200
    print(f"\nrandom pools: {checked} checked, {tight} where the bound is exact")


# --- the tightness report on the real boots -------------------------------------------------------

BOOTS = "Metadata/Items/Armours/Boots/BootsInt1"  # Sorcerer Boots
BOOTS_LEVEL = 86


def timed(function):
    """The value of `function()`; the milliseconds are not measured here (no test reads a clock, ADR-0014)."""
    return function(), 0.0


def test_tightness_on_the_real_sorcerer_boots():
    data = real_game_data()
    start = Item.build(data, base_id=BOOTS, item_level=BOOTS_LEVEL, rarity=Rarity.RARE)
    pool = build_pool(data, start)

    def family_ids(name):
        return frozenset(entry.mod.id for fam in pool if fam.family == name for entry in fam.mods)

    # The boots pool has no family named IncreasedEnergyShield (that is the amulet's); the energy shield
    # of boots is the local percent family DefencesPercent (7 tiers).
    shield = Wanted(family_ids("DefencesPercent"), min_tier=3)
    speed = Wanted(family_ids("MovementVelocity"), min_tier=1)
    ab = Abstraction(data, Goal((shield, speed)), BOOTS, BOOTS_LEVEL, [])
    state = ab.compress(start)
    names = {(0,): "ES t3", (1,): "MS t1", (0, 1): "both"}
    rng = random.Random(118)
    sets = rng.sample([a for a in fossil_actions(data, start) if "Bloodstained Fossil" not in a.fossils], 20)  # the report is about the reroll; a Bloodstained set corrupts too
    actions = [("Chaos", ChaosOrb()), *((" + ".join(name.removesuffix(" Fossil") for name in a.fossils), a) for a in sets)]

    print()
    for label, action in actions:
        for leaves, nick in names.items():
            bound, ms_bound = timed(lambda: reach_bound(ab, state, action, leaves))
            exact, ms_exact = timed(lambda: reach_bound(ab, state, action, leaves, exact=True))
            if bound is None or exact is None:
                assert bound is None and exact is None
                print(f"{label[:60]:60} {nick:6} none")
                continue
            assert exact <= bound <= 1
            ratio = float(bound / exact) if exact else float("inf")
            print(
                f"{label[:60]:60} {nick:6} bound {float(bound):.5f} exact {float(exact):.5f} "
                f"ratio {ratio:6.3f}  bound {ms_bound:7.1f} ms  exact {ms_exact:8.1f} ms"
            )


def test_a_fractured_fossil_set_gives_none_on_the_real_boots():
    data = real_game_data()
    start = Item.build(data, base_id=BOOTS, item_level=BOOTS_LEVEL, rarity=Rarity.RARE)
    ab = Abstraction(data, Goal((Wanted(frozenset({"MovementVelocity1"})),)), BOOTS, BOOTS_LEVEL, [])
    action = ApplyFossils(("Fractured Fossil",))

    assert action.outcomes(data, start).fractures
    assert reach_bound(ab, ab.compress(start), action, [0]) is None
    assert reach_bound(ab, ab.compress(start), action, [0], exact=True) is None
