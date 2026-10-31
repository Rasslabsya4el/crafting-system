"""A brute-force oracle for the compressed kernel of the magic-item orbs, independent of `crafting_system.abstraction` (ticket #65).

Like `abstraction_oracle.py` for the rerolls, it lists every concrete finished item of an orb with its
exact probability; the test compresses each one with `Abstraction.compress` and adds up the
probability per compressed state. The one thing it takes from `actions` is `build_pool`: the
candidate (mod, weight) pairs of a draw. Nothing here touches `Outcomes.distribution`.

The rules it plays are the claims of the registry, written again as plain code. A draw picks one
candidate mod in proportion to its weight from both sides together; the family of a drawn mod leaves
the pool; a magic item holds one prefix and one suffix, a rare item three of each, and a full side
closes; a draw with no candidate left stops with fewer mods. A Transmutation and an Alteration end
with 1 or 2 mods (1/2 each, the fractured mods counting inside) and an Alteration keeps the fractured
mods only; an Augmentation adds one mod to the item as it is; a Regal Orb first makes the item rare
and then adds one; an Orb of Scouring leaves the fractured mods and the rarity they allow
(normal for none, magic for one, rare for two or more). The Alchemy is the 4/5/6 draw of a rare item
with no mod, which `abstraction_oracle.finished_items` plays.
"""

from collections import Counter, defaultdict
from collections.abc import Mapping
from fractions import Fraction

from abstraction_oracle import Candidate
from crafting_system.actions import build_pool
from crafting_system.data import GameData
from crafting_system.items import ExplicitMod, Item, Rarity, tier_table

CAP = {Rarity.MAGIC: 1, Rarity.RARE: 3}
HALF = Fraction(1, 2)
SIDES = ("prefix", "suffix")


def _drawn(data: GameData, tiers: Mapping[str, int], mod_id: str) -> ExplicitMod:
    """A drawn mod at its table tier with every value at the low end of its range."""
    stats = data.mods[mod_id].stats
    return ExplicitMod(mod_id, tiers.get(mod_id, 1), tuple(min(stat.min, stat.max) for stat in stats))


def drawn_items(
    data: GameData, retained: Item, totals: Mapping[int, Fraction]
) -> list[tuple[Item, Fraction]]:
    """Every finished item of drawing onto `retained` up to `totals`, with its exact probability.

    `retained` is the item before any draw, with the rarity that decides the capacity; `totals` is
    the probability of each total number of mods of the finished item (the mods of `retained` counted).
    """
    cap = CAP[retained.rarity]
    room = {
        side: cap - sum(data.mods[entry.mod_id].generation_type == side for entry in retained.mods)
        for side in SIDES
    }
    candidates = [
        Candidate(entry.mod, family.family, family.side.value, entry.weight)
        for family in build_pool(data, retained)
        for entry in family.mods
    ]
    by_id = {candidate.mod.id: candidate for candidate in candidates}

    def options(drawn: frozenset[str]) -> list[Candidate]:
        families = {by_id[mod_id].family for mod_id in drawn}
        used = Counter(by_id[mod_id].side for mod_id in drawn)
        return [c for c in candidates if c.family not in families and used[c.side] < room[c.side]]

    layer: dict[frozenset[str], Fraction] = {frozenset(): Fraction(1)}
    layers = [layer]
    picks = {total: max(0, total - len(retained.mods)) for total in totals}
    for _ in range(max(picks.values())):
        following: dict[frozenset[str], Fraction] = defaultdict(Fraction)
        for drawn, chance in layers[-1].items():
            open_now = options(drawn)
            if not open_now:
                following[drawn] += chance
                continue
            whole = sum((c.weight for c in open_now), Fraction(0))
            for c in open_now:
                following[drawn | {c.mod.id}] += chance * c.weight / whole
        layers.append(following)

    outcome: dict[frozenset[str], Fraction] = defaultdict(Fraction)
    for total, chance in totals.items():
        for drawn, inner in layers[picks[total]].items():
            outcome[drawn] += chance * inner
    assert sum(outcome.values()) == 1
    tiers = tier_table(data, retained.base_id)
    return [
        (retained.changed(data, mods=(*retained.mods, *(_drawn(data, tiers, mod_id) for mod_id in drawn))), chance)
        for drawn, chance in outcome.items()
    ]


def transmuted(data: GameData, start: Item) -> list[tuple[Item, Fraction]]:
    """A normal item made magic with 1 or 2 mods."""
    return drawn_items(data, start.changed(data, rarity=Rarity.MAGIC), {1: HALF, 2: HALF})


def altered(data: GameData, start: Item) -> list[tuple[Item, Fraction]]:
    """A magic item rerolled to 1 or 2 mods; the fractured mods stay and count inside."""
    return drawn_items(data, start.changed(data, mods=start.fractured_mods), {1: HALF, 2: HALF})


def augmented(data: GameData, start: Item) -> list[tuple[Item, Fraction]]:
    """One more mod on a magic item, which keeps everything it has."""
    return drawn_items(data, start, {len(start.mods) + 1: Fraction(1)})


def regaled(data: GameData, start: Item) -> list[tuple[Item, Fraction]]:
    """A magic item made rare with one more mod; the mods it has stay."""
    rare = start.changed(data, rarity=Rarity.RARE)
    return drawn_items(data, rare, {len(rare.mods) + 1: Fraction(1)})


def scoured(data: GameData, start: Item) -> list[tuple[Item, Fraction]]:
    """The item with its fractured mods only, in the rarity they allow."""
    kept = start.fractured_mods
    rarity = Rarity.NORMAL if not kept else Rarity.MAGIC if len(kept) == 1 else Rarity.RARE
    return [(start.changed(data, rarity=rarity, mods=kept), Fraction(1))]
