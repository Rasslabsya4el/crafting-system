"""A family with mods on both sides, on hand-made pools (ticket #201, claim `affix_pool.family_may_span_both_sides`).

Five families of the base jewels (and one of the abyss jewels) have prefixes and suffixes. `group_pool` makes two
`PoolFamily` of one name for such a family, and the draw treats them as one unit: a draw picks one mod among the
sides that have room, and the unit leaves the pool on both sides. The oracle here walks every draw order over the
*mods* (not families, not classes), with `Fraction`s, and shares nothing with the engine but the pool it is given.
"""

import random
from collections import Counter
from fractions import Fraction

import pytest
from proto_draw_support import NO_CAP, PREFIX, SUFFIX, draws, family, synthetic_mod

from crafting_system.items import Side
from crafting_system.actions.draw import exact_distribution, guaranteed_candidates, sample_new_mods
from crafting_system.actions.pool import Candidate, PoolFamily, PoolMod, group_pool, partners


def two_sided(name: str, prefixes: dict[str, int], suffixes: dict[str, int]) -> tuple[PoolFamily, PoolFamily]:
    """One family with the given mods on each side: two `PoolFamily` of the same name."""
    return (
        PoolFamily(name, PREFIX, tuple(PoolMod(synthetic_mod(i, name, PREFIX), Fraction(w)) for i, w in prefixes.items())),
        PoolFamily(name, SUFFIX, tuple(PoolMod(synthetic_mod(i, name, SUFFIX), Fraction(w)) for i, w in suffixes.items())),
    )


def hand_distribution(pool, free, picks, tag=None):
    """The chance of each set of drawn mod ids, by walking every order of draws one mod at a time."""
    mods = [(f.family, f.side, e.mod.id, e.weight, tag is not None and tag in e.mod.implicit_tags) for f in pool for e in f.mods]
    found: Counter = Counter()

    def walk(drawn, names, room, left, chance, guaranteed):
        if left == 0:
            found[drawn] += chance
            return
        open_ = [m for m in mods if m[0] not in names and room[m[1]] > 0 and (not guaranteed or m[4])]
        if not open_:
            found[drawn] += chance
            return
        whole = sum(m[3] for m in open_)
        for name, side, mod_id, weight, _ in open_:
            walk(drawn | {mod_id}, names | {name}, {**room, side: room[side] - 1}, left - 1, chance * weight / whole, False)

    walk(frozenset(), frozenset(), dict(free), picks, Fraction(1), tag is not None)
    return found


def engine_distribution(pool, free, picks, tag=None):
    shown = exact_distribution(tuple(pool), free, tag, draws(picks), 0, lambda mod: mod.id)
    return {frozenset(label for label, _ in outcome): chance for outcome, chance in shown.items()}


POOLS = {
    "one two-sided family": [
        family("Lone", PREFIX, 3),
        *two_sided("Both", {"b-pre-1": 2, "b-pre-2": 1}, {"b-suf-1": 5}),
        family("Tail", SUFFIX, 4),
    ],
    "two interchangeable two-sided families": [
        *two_sided("A", {"a-pre": 2}, {"a-suf": 3}),
        *two_sided("B", {"b-pre": 2}, {"b-suf": 3}),
        family("Other", PREFIX, 1),
        family("Rest", SUFFIX, 2),
    ],
    "a two-sided family beside several one-sided ones": [
        family("P1", PREFIX, 4),
        family("P2", PREFIX, 1),
        *two_sided("Mix", {"m-pre": 3}, {"m-suf-1": 2, "m-suf-2": 2}),
        family("S1", SUFFIX, 5),
        family("S2", SUFFIX, 1),
    ],
}
FREES = {
    "open both": {PREFIX: 2, SUFFIX: 2},
    "one prefix, two suffixes": {PREFIX: 1, SUFFIX: 2},
    "no suffix room": {PREFIX: 2, SUFFIX: 0},
}


@pytest.mark.parametrize("pool_name", POOLS)
@pytest.mark.parametrize("free_name", FREES)
@pytest.mark.parametrize("picks", [1, 2, 3, 4])
def test_the_exact_distribution_equals_the_hand_walk_over_mods(pool_name, free_name, picks):
    pool, free = POOLS[pool_name], FREES[free_name]

    assert engine_distribution(pool, free, picks) == hand_distribution(pool, free, picks)


@pytest.mark.parametrize("pool_name", POOLS)
def test_a_family_is_never_drawn_twice_whatever_the_sides(pool_name):
    pool = POOLS[pool_name]
    owner = {entry.mod.id: family_.family for family_ in pool for entry in family_.mods}

    for drawn in engine_distribution(pool, NO_CAP, 4):
        names = [owner[mod_id] for mod_id in drawn]
        assert len(names) == len(set(names))


def test_a_draw_on_one_side_takes_the_family_out_of_the_other_side():
    pool = [*two_sided("Both", {"pre": 1}, {"suf": 1}), family("Other", SUFFIX, 1)]

    shown = engine_distribution(pool, {PREFIX: 0, SUFFIX: 2}, 2)

    assert shown == {frozenset({"suf", "Other"}): Fraction(1)}  # only the suffix part has room; then the family is spent


def test_the_two_sides_of_one_family_count_as_one_unit_for_a_closed_side():
    pool = [*two_sided("Both", {"pre": 3}, {"suf": 1}), family("P", PREFIX, 1)]

    shown = engine_distribution(pool, {PREFIX: 1, SUFFIX: 1}, 2)

    assert shown == hand_distribution(pool, {PREFIX: 1, SUFFIX: 1}, 2)
    assert frozenset({"pre", "suf"}) not in shown  # one mod of the family at most


GUARANTEED = "guaranteed"


def tagged(pool, *mod_ids):
    """`pool` where exactly the mods in `mod_ids` carry the guaranteed tag."""
    import dataclasses

    return [
        PoolFamily(
            f.family,
            f.side,
            tuple(
                PoolMod(dataclasses.replace(e.mod, implicit_tags=(GUARANTEED,)) if e.mod.id in mod_ids else e.mod, e.weight)
                for e in f.mods
            ),
        )
        for f in pool
    ]


@pytest.mark.parametrize("free_name", FREES)
@pytest.mark.parametrize("picks", [1, 2, 3])
def test_a_guaranteed_draw_from_a_two_sided_family_equals_the_hand_walk(free_name, picks):
    pool = tagged(POOLS["a two-sided family beside several one-sided ones"], "m-pre", "m-suf-1", "P2")
    free = FREES[free_name]
    if not guaranteed_candidates(pool, free, GUARANTEED):
        pytest.skip("no tagged mod has room")

    assert engine_distribution(pool, free, picks, GUARANTEED) == hand_distribution(pool, free, picks, GUARANTEED)


@pytest.mark.parametrize("pool_name", POOLS)
def test_the_sampler_follows_the_same_process_as_the_exact_engine(pool_name):
    pool, free = tuple(POOLS[pool_name]), {PREFIX: 2, SUFFIX: 2}
    exact = engine_distribution(pool, free, 3)
    floats = {entry.mod.id: float(entry.weight) for f in pool for entry in f.mods}
    rng, runs = random.Random(201), 30000
    seen: Counter = Counter()
    for _ in range(runs):
        seen[frozenset(m.mod.id for m in sample_new_mods(pool, free, None, 3, 0, rng, floats))] += 1

    assert set(seen) <= set(exact)
    for drawn, chance in exact.items():
        assert seen[drawn] / runs == pytest.approx(float(chance), abs=0.012)


def test_group_pool_makes_one_pool_family_per_side_of_a_two_sided_family():
    mods = [synthetic_mod("pre", "Both", PREFIX), synthetic_mod("suf", "Both", SUFFIX), synthetic_mod("solo", "Solo", PREFIX)]
    candidates = [Candidate(mod, Fraction(1), mod.families[0], Side(mod.generation_type)) for mod in mods]

    pool = group_pool(candidates)

    assert [(f.family, f.side) for f in pool] == [("Both", PREFIX), ("Both", SUFFIX), ("Solo", PREFIX)]
    assert set(partners(pool)) == {"Both"}
