"""The forward draw engine of `actions.draw.exact_distribution` against the backward walk it replaced, exactly (ticket #934).

`exact_distribution` used to walk the states of a draw (how many families of each class are drawn) backward and keep with each the
distribution of the labels still to come. It now walks the same states forward, one number per state, and spreads the labels at the end
(its docstring says why that is the same number). `backward` below is the earlier engine, kept here as the oracle: every distribution the
new engine gives must equal its distribution exactly, as a dict of `Fraction`s (the same outcomes, the same chances), on small hand-made
worlds that reach every branch (two-sided families, a guaranteed tag and blocked tags, kept mods, a dry pool, a full side, several labels in
one family, weights that are not integers, a zero weight) and on pools of the real game data with fossil-like weights. In the planner's float
mode (`floating`) the two agree to the float error.
"""

import dataclasses
import random
from collections import defaultdict
from collections.abc import Callable, Hashable
from fractions import Fraction
from functools import cache

import pytest
from abstraction_support import real_game_data
from proto_draw_support import family, synthetic_mod

from crafting_system.actions import draw
from crafting_system.actions.draw import exact_distribution, floating, guaranteed_candidates, total_distribution
from crafting_system.actions.pool import PoolFamily, PoolMod, build_pool
from crafting_system.items import Item, Rarity, Side

PREFIX, SUFFIX = Side.PREFIX, Side.SUFFIX


def backward(pool, free, tag, totals, kept, label, blocked=frozenset()):
    """The engine of `exact_distribution` before #934, unchanged but for its name: the oracle."""
    number = draw.NUMBER
    labels: list[Hashable] = []
    label_index: dict[Hashable, int] = {}
    classes: dict[tuple, int] = {}
    class_parts: list = []
    class_count: list[int] = []
    class_of: dict[str, int] = {}
    mod_label: dict[str, int] = {}
    units: dict[str, list[PoolFamily]] = defaultdict(list)
    for fam in pool:
        units[fam.family].append(fam)
    for name, sides in units.items():
        parts = []
        for fam in sides:
            by_label: dict[int, Fraction] = defaultdict(number)
            for entry in fam.mods:
                value = label(entry.mod)
                index = label_index.setdefault(value, len(label_index))
                if index == len(labels):
                    labels.append(value)
                mod_label[entry.mod.id] = index
                by_label[index] += number(entry.weight)
            weights = tuple(sorted(by_label.items()))
            parts.append((fam.side is Side.PREFIX, weights, sum((w for _, w in weights), number(0))))
        key = tuple(sorted(parts))
        if key not in classes:
            classes[key] = len(class_parts)
            class_parts.append(key)
            class_count.append(0)
        class_count[classes[key]] += 1
        class_of[name] = classes[key]
    width = len(labels)

    @cache
    def walk(drawn, room_prefix, room_suffix, picks):
        nothing = {(0,) * width: number(1)}
        if picks == 0:
            return nothing
        open_weight = {}
        for index, taken in enumerate(drawn):
            if class_count[index] > taken:
                weight = sum((total for on_prefix, _, total in class_parts[index] if (room_prefix if on_prefix else room_suffix) > 0), number(0))
                if weight:
                    open_weight[index] = weight
        if not open_weight:
            return nothing
        total = sum(((class_count[i] - drawn[i]) * weight for i, weight in open_weight.items()), number(0))
        result: dict = defaultdict(number)
        for index in open_weight:
            remaining = class_count[index] - drawn[index]
            for on_prefix, weights, _ in class_parts[index]:
                if (room_prefix if on_prefix else room_suffix) <= 0:
                    continue
                child = walk(drawn[:index] + (drawn[index] + 1,) + drawn[index + 1 :], room_prefix - on_prefix, room_suffix - (not on_prefix), picks - 1)
                for lab, weight in weights:
                    step = remaining * weight / total
                    for tally, chance in child.items():
                        result[tally[:lab] + (tally[lab] + 1,) + tally[lab + 1 :]] += step * chance
        return dict(result)

    start = (0,) * len(class_count)
    guaranteed = []
    if tag is not None:
        groups: dict = defaultdict(int)
        for fam, entry in guaranteed_candidates(pool, free, tag, blocked):
            groups[(class_of[fam.family], fam.side is Side.PREFIX, mod_label[entry.mod.id], entry.weight)] += 1
        tagged_total = sum((n * number(weight) for (_, _, _, weight), n in groups.items()), number(0))
        guaranteed = [(cls, on_prefix, lab, n * number(weight) / tagged_total) for (cls, on_prefix, lab, weight), n in groups.items()]
    tallies: dict = defaultdict(number)
    for total, chance in totals.items():
        chance = number(chance)
        picks = max(0, total - kept - (tag is not None))
        if tag is None:
            for tally, inner in walk(start, free[Side.PREFIX], free[Side.SUFFIX], picks).items():
                tallies[tally] += chance * inner
            continue
        for cls, on_prefix, lab, step in guaranteed:
            inner_all = walk(start[:cls] + (1,) + start[cls + 1 :], free[Side.PREFIX] - on_prefix, free[Side.SUFFIX] - (not on_prefix), picks)
            for tally, inner in inner_all.items():
                tallies[tally[:lab] + (tally[lab] + 1,) + tally[lab + 1 :]] += chance * step * inner
    return {frozenset((labels[i], count) for i, count in enumerate(tally) if count): chance for tally, chance in tallies.items()}


def same(pool, free, tag, totals, kept, label: Callable, blocked=frozenset()) -> dict:
    """Both engines on one draw; they must give the same dict, exactly, and sum to exactly one."""
    new = exact_distribution(pool, free, tag, totals, kept, label, blocked)
    old = {outcome: chance for outcome, chance in backward(pool, free, tag, totals, kept, label, blocked).items() if chance}
    assert new == old
    assert sum(new.values()) == 1
    return new


def tagged(fam: PoolFamily, mod_index: int, *tags: str) -> PoolFamily:
    """`fam` with its mod number `mod_index` carrying the implicit tags `tags`."""
    mods = list(fam.mods)
    mods[mod_index] = PoolMod(dataclasses.replace(mods[mod_index].mod, implicit_tags=tags), mods[mod_index].weight)
    return PoolFamily(fam.family, fam.side, tuple(mods))


def by_family(mod) -> str:
    return mod.families[0]


def by_id(mod) -> str:
    return mod.id


# ---- small worlds: one branch of the engine each ---------------------------------------------------------------------------------------

RARE = total_distribution()

SMALL = {
    "one-label-many-classes": ([family(f"P{i}", PREFIX, 100 * (i + 1)) for i in range(4)] + [family(f"S{i}", SUFFIX, 150 * (i + 1)) for i in range(4)], lambda mod: "any"),
    "families-of-one-class": ([family(f"P{i}", PREFIX, 500) for i in range(4)] + [family(f"S{i}", SUFFIX, 500) for i in range(3)], by_family),
    "several-labels-in-a-family": (
        [family("A", PREFIX, ("A1", 100), ("A2", 300), ("A3", 50)), family("B", PREFIX, ("B1", 100), ("B2", 300), ("B3", 50)), family("C", SUFFIX, ("C1", 70), ("C2", 30)), family("D", SUFFIX, 400)],
        by_id,
    ),
    "a-family-on-both-sides": ([family("Both", PREFIX, ("BothP", 200)), family("Both", SUFFIX, ("BothS", 300)), family("P", PREFIX, 250), family("S", SUFFIX, 125), family("T", SUFFIX, 125)], by_id),
    "weights-that-are-not-integers": ([family("A", PREFIX, 1), family("B", PREFIX, 3), family("C", SUFFIX, 2)], by_family),
}
SMALL["weights-that-are-not-integers"] = (
    [PoolFamily(f.family, f.side, tuple(PoolMod(e.mod, e.weight / 7 * (i + 2)) for e in f.mods)) for i, f in enumerate(SMALL["weights-that-are-not-integers"][0])],
    by_family,
)


@pytest.mark.parametrize("name", SMALL)
@pytest.mark.parametrize(("free", "kept", "totals"), [((3, 3), 0, RARE), ((1, 3), 2, RARE), ((2, 0), 0, {3: Fraction(1)}), ((3, 3), 0, {1: Fraction(1, 2), 9: Fraction(1, 2)})])
def test_the_forward_engine_equals_the_backward_walk_on_small_worlds(name, free, kept, totals):
    pool, label = SMALL[name]
    same(tuple(pool), {PREFIX: free[0], SUFFIX: free[1]}, None, totals, kept, label)


def test_a_dry_pool_leaves_fewer_mods_in_both_engines():
    pool = (family("A", PREFIX, 100), family("B", SUFFIX, 300))  # two families, four or more mods asked
    shown = same(pool, {PREFIX: 3, SUFFIX: 3}, None, RARE, 0, by_family)
    assert shown == {frozenset({("A", 1), ("B", 1)}): 1}


def test_a_family_of_no_weight_is_never_drawn():
    pool = (family("A", PREFIX, 100), PoolFamily("Z", PREFIX, (PoolMod(synthetic_mod("Z", "Z", PREFIX), Fraction(0)),)), family("B", SUFFIX, 300))
    shown = same(pool, {PREFIX: 3, SUFFIX: 3}, None, {2: Fraction(1)}, 0, by_family)
    assert all(label != "Z" for outcome in shown for label, _ in outcome)


@pytest.mark.parametrize("blocked", [frozenset(), frozenset({"attack"})])
def test_a_guaranteed_tag_is_drawn_first_in_both_engines(blocked):
    pool = (
        tagged(family("A", PREFIX, ("A1", 100), ("A2", 300)), 1, "fire"),
        tagged(family("B", PREFIX, ("B1", 100), ("B2", 300)), 0, "fire", "attack"),
        tagged(family("C", SUFFIX, ("C1", 200)), 0, "fire"),
        family("D", SUFFIX, 400),
        family("E", PREFIX, 250),
        tagged(family("Both", PREFIX, ("BothP", 200)), 0, "fire"),
        family("Both", SUFFIX, ("BothS", 300)),
    )
    for free in ((3, 3), (0, 2), (2, 0)):
        same(pool, {PREFIX: free[0], SUFFIX: free[1]}, "fire", RARE, 1, by_id, blocked)


# ---- worlds drawn at random from the real pools, with fossil-like weights -----------------------------------------------------------------

BASES = ("Metadata/Items/Weapons/TwoHandWeapons/Staves/Staff4", "Metadata/Items/Armours/Boots/BootsInt1", "Metadata/Items/Amulets/Amulet1")


@pytest.fixture(scope="module")
def real_pools():
    data = real_game_data()
    return [build_pool(data, Item.build(data, base_id=base, item_level=84, rarity=Rarity.RARE)) for base in BASES]


def reweighed(pool, rng: random.Random, whole: bool) -> tuple[PoolFamily, ...]:
    """The pool with each family's weights times a factor of its own, as fossils make them (an integer, or a fraction when not `whole`)."""
    out = []
    for fam in pool:
        factor = rng.choice((0, 1, 1, 2, 10)) if whole else Fraction(rng.choice((1, 3, 7)), rng.choice((2, 5)))
        if factor:
            out.append(PoolFamily(fam.family, fam.side, tuple(PoolMod(entry.mod, entry.weight * factor) for entry in fam.mods)))
    return tuple(out)


LABELS = {
    "coarse": lambda wanted: (lambda mod: (mod.families[0] in wanted, mod.generation_type)),
    "by-tier": lambda wanted: (lambda mod: (mod.families[0] if mod.families[0] in wanted else "", mod.required_level >= 60)),
    "by-mod": lambda wanted: (lambda mod: mod.id if mod.families[0] in wanted else mod.generation_type),
}


@pytest.mark.parametrize("seed", range(12))
def test_the_forward_engine_equals_the_backward_walk_on_real_pools(real_pools, seed):
    rng = random.Random(934 * 100 + seed)
    whole = rng.random() < 0.6
    pool = rng.choice(real_pools)
    picked = rng.sample(pool, min(len(pool), rng.randint(5, 11)))
    picked = reweighed(picked, rng, whole) or tuple(picked)
    wanted = {fam.family for fam in rng.sample(picked, min(2, len(picked)))}
    label = LABELS[rng.choice(sorted(LABELS))](wanted)
    free = {PREFIX: rng.randint(0, 3), SUFFIX: rng.randint(1, 3)}
    kept = rng.randint(0, 2)
    tags = sorted({tag for fam in picked for entry in fam.mods for tag in entry.mod.implicit_tags})
    tag = rng.choice(tags) if tags and rng.random() < 0.4 else None
    if tag is not None and not guaranteed_candidates(picked, free, tag):
        tag = None
    same(picked, free, tag, RARE, kept, label)


def test_the_two_engines_agree_in_floats(real_pools):
    rng = random.Random(9340)
    picked = reweighed(rng.sample(real_pools[0], 9), rng, True)
    label = LABELS["by-tier"]({picked[0].family, picked[1].family})
    free = {PREFIX: 3, SUFFIX: 3}
    with floating():
        new = exact_distribution(picked, free, None, RARE, 0, label)
        old = backward(picked, free, None, RARE, 0, label)
    assert new.keys() == {outcome for outcome, chance in old.items() if chance}
    assert all(abs(new[outcome] - old[outcome]) <= 1e-12 * old[outcome] for outcome in new)
    assert abs(sum(new.values()) - 1) <= 1e-12


def test_a_whole_real_pool_with_a_coarse_label_draws_exactly(real_pools):
    """The whole pool of a staff under fossil-like weights, the shape that cost the fossil plans most (#934): one outcome per label count."""
    rng = random.Random(93401)
    pool = reweighed(real_pools[0], rng, True)
    wanted = {pool[0].family}
    shown = exact_distribution(pool, {PREFIX: 3, SUFFIX: 3}, None, RARE, 0, LABELS["coarse"](wanted))
    assert sum(shown.values()) == 1
    assert len(shown) <= 3 * 4 * 2  # wanted or not, per side, at most six mods
