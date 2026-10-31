"""A brute-force oracle for the compressed kernel of the R12 actions, independent of `crafting_system.abstraction`.

It lists every concrete finished item of a reroll with its exact probability, then compresses each
one with a caller's `compress` and adds up the probability per compressed state. Nothing here
touches `Outcomes.distribution`, `exact_distribution` or the lumping of `actions/draw.py`; the one
thing it takes from `actions` is `build_pool`: the candidate (mod, weight) pairs of a draw.

The rules it plays are the claims of the registry, written again as plain code: a reroll keeps the
fractured mods and drops the rest; the finished item holds 4, 5 or 6 mods in the ratio 8:3:1 and the
kept mods count inside that total; every draw picks one candidate mod in proportion to its weight
from both sides together; the family of a drawn mod leaves the pool; a side holds three mods and a
full side closes; a draw with no candidate left stops the reroll with fewer mods; a tagged reforge
first draws one mod with the tag, in proportion to the weight of the tagged mods, and that draw
counts inside the total too (and is made whatever the total is). An essence also puts its forced
mod on the item before any draw (a kept mod: it counts inside the total and its family and side slot
are used) and a low essence caps the required level of the drawn mods.

The bench is plain code here too: `crafted_item` puts a crafted mod on an item, `uncrafted_item`
takes every crafted mod off it.

The walk is over ordered draws, kept as a distribution over the set of mod ids drawn so far: the
chance of a set is the sum over the orders that reach it. A set with no candidate left stays as it
is. Every finished item is built as a validated `Item` (the tier of a drawn mod from `tier_table`,
every value at the low end of its range), so a draw that broke a capacity or a family rule would
fail here, not pass silently.
"""

from collections import Counter, defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.actions import PoolFamily, build_pool
from crafting_system.data import GameData, Mod
from crafting_system.items import ExplicitMod, Item, Rarity, tier_table

CAP = 3
SIDES = ("prefix", "suffix")
TOTALS = {4: Fraction(8, 12), 5: Fraction(3, 12), 6: Fraction(1, 12)}


@dataclass(frozen=True)
class Candidate:
    """One mod that a draw could pick, the family that its pick closes and its weight."""

    mod: Mod
    family: str
    side: str
    weight: Fraction


def guaranteed_tag(action: object) -> str | None:
    """The tag of the guaranteed mod: the one of a tagged Harvest reforge ("lightning"), None for a Chaos Orb."""
    return getattr(action, "tag", None)


def finished_items(
    data: GameData,
    start: Item,
    tag: str | None = None,
    *,
    forced: str | None = None,
    cap: int | None = None,
    pool: Iterable[PoolFamily] | None = None,
    totals: Mapping[int, Fraction] | None = None,
) -> list[tuple[Item, Fraction]]:
    """Every finished item of rerolling `start` (kept: its fractured mods) with its exact probability.

    `forced` is the id of the forced mod of an essence and `cap` the level cap of a low essence.
    `pool` replaces the candidates (a fossil pool with its weights); it must be built for the retained item.
    `totals` replaces the 8:3:1 chance of each total number of mods (a likelihood reforge draws a fixed number).
    Raises `ValueError` when `tag` is given and no tagged mod can be drawn first. `start` is taken to
    be an uncorrupted, uninfluenced item that the action accepts: refusals are not the oracle's business.
    """
    kept_mods = start.fractured_mods
    if forced is not None:
        low = tuple(min(stat.min, stat.max) for stat in data.mods[forced].stats)
        kept_mods = (*kept_mods, ExplicitMod(forced, tier_table(data, start.base_id).get(forced, 1), low))
    retained = start.changed(data, rarity=Rarity.RARE, mods=kept_mods)
    kept = len(retained.mods)
    room = {
        side: CAP - sum(data.mods[entry.mod_id].generation_type == side for entry in retained.mods)
        for side in SIDES
    }
    candidates = [
        Candidate(entry.mod, family.family, family.side.value, entry.weight)
        for family in (build_pool(data, retained, cap) if pool is None else pool)
        for entry in family.mods
    ]
    by_id = {candidate.mod.id: candidate for candidate in candidates}

    opened: dict[frozenset[str], list[Candidate]] = {}

    def options(drawn: frozenset[str]) -> list[Candidate]:
        if drawn not in opened:
            families = {by_id[mod_id].family for mod_id in drawn}
            used = Counter(by_id[mod_id].side for mod_id in drawn)
            opened[drawn] = [
                c for c in candidates if c.family not in families and used[c.side] < room[c.side]
            ]
        return opened[drawn]

    def advance(layer: Mapping[frozenset[str], Fraction]) -> dict[frozenset[str], Fraction]:
        following: dict[frozenset[str], Fraction] = defaultdict(Fraction)
        for drawn, chance in layer.items():
            open_now = options(drawn)
            if not open_now:
                following[drawn] += chance
                continue
            whole = sum((c.weight for c in open_now), Fraction(0))
            for c in open_now:
                following[drawn | {c.mod.id}] += chance * c.weight / whole
        return following

    layer: dict[frozenset[str], Fraction] = {frozenset(): Fraction(1)}
    if tag is not None:
        tagged = [c for c in candidates if tag in c.mod.implicit_tags and room[c.side] > 0]
        if not tagged:
            raise ValueError(f"no {tag} mod can be drawn first")
        whole = sum((c.weight for c in tagged), Fraction(0))
        layer = {frozenset({c.mod.id}): c.weight / whole for c in tagged}
    totals = TOTALS if totals is None else totals
    picks_of = {total: max(0, total - kept - (tag is not None)) for total in totals}
    layers = [layer]
    for _ in range(max(picks_of.values())):
        layers.append(advance(layers[-1]))

    outcome: dict[frozenset[str], Fraction] = defaultdict(Fraction)
    for total, chance in totals.items():
        for drawn, inner in layers[picks_of[total]].items():
            outcome[drawn] += chance * inner
    assert sum(outcome.values()) == 1
    tiers = tier_table(data, start.base_id)
    return [
        (retained.changed(data, mods=(*retained.mods, *(_drawn(data, tiers, mod_id) for mod_id in drawn))), chance)
        for drawn, chance in outcome.items()
    ]


def _drawn(data: GameData, tiers: Mapping[str, int], mod_id: str) -> ExplicitMod:
    stats = data.mods[mod_id].stats
    return ExplicitMod(mod_id, tiers.get(mod_id, 1), tuple(min(stat.min, stat.max) for stat in stats))


def crafted_item(data: GameData, start: Item, mod_id: str) -> Item:
    """`start` with the crafted mod `mod_id` added at the low end of its range."""
    low = tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats)
    return start.add_mod(data, ExplicitMod(mod_id, 1, low, crafted=True))


def uncrafted_item(data: GameData, start: Item) -> Item:
    """`start` without any crafted mod."""
    return start.changed(data, mods=tuple(entry for entry in start.mods if not entry.crafted))


def compressed_distribution(
    finished: list[tuple[Item, Fraction]], compress: Callable[[Item], Hashable]
) -> dict[Hashable, Fraction]:
    """The probability of each compressed state: the finished items passed through `compress`, added up."""
    result: dict[Hashable, Fraction] = defaultdict(Fraction)
    for item, chance in finished:
        result[compress(item)] += chance
    return dict(result)


def hold_chance(finished: list[tuple[Item, Fraction]], mod_ids: set[str]) -> Fraction:
    """The chance that the finished item holds every mod of `mod_ids`, kept or drawn."""
    return sum(
        (chance for item, chance in finished if mod_ids <= {entry.mod_id for entry in item.mods}),
        Fraction(0),
    )


def differences(actual: Mapping[Hashable, Fraction], expected: Mapping[Hashable, Fraction]) -> list[str]:
    """What is wrong with `actual` as the distribution `expected`; empty when the two are equal exactly.

    A probability must be a `Fraction` (a float that equals it is refused), nothing may be left out or
    added, no entry is zero, and the probabilities must add up to exactly 1.
    """
    problems = []
    for state, chance in actual.items():
        if type(chance) is not Fraction:
            problems.append(f"{state!r}: the probability {chance!r} is a {type(chance).__name__}, not a Fraction")
        elif chance == 0:
            problems.append(f"{state!r}: a zero probability is kept as an entry")
    for state in expected.keys() - actual.keys():
        problems.append(f"{state!r}: missing, expected {float(expected[state]):.6g}")
    for state in actual.keys() - expected.keys():
        problems.append(f"{state!r}: not expected, got {float(actual[state]):.6g}")
    for state in actual.keys() & expected.keys():
        if actual[state] != expected[state]:
            problems.append(
                f"{state!r}: got {float(actual[state]):.12g}, expected {float(expected[state]):.12g}"
            )
    if sum(actual.values(), Fraction(0)) != 1:
        problems.append(f"the probabilities add up to {float(sum(actual.values(), Fraction(0))):.12g}, not 1")
    return problems


def assert_same_distribution(actual: Mapping[Hashable, Fraction], expected: Mapping[Hashable, Fraction]) -> None:
    """Fail with the list of `differences` when `actual` is not exactly `expected`."""
    problems = differences(actual, expected)
    assert not problems, f"{len(problems)} difference(s):\n" + "\n".join(problems[:10])
