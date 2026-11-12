"""The three corrupting actions sampled from the rules registry, not from the action code the kernel reads (ADR-0039, ADR-0019 layer 2; ticket #264).

`actions.VaalOrb`, `actions.LocusOfCorruption` and a resonator holding the Bloodstained Fossil list their results as exact fractions, and the
abstraction builds its kernel from those lists; their own `sample` draws from the same lists. A check of the kernel against them would check
the lists against themselves. The three samplers here are written again from the claims, so that a wrong list shows up as a disagreement:

* **The four outcomes** are the shares of the claims: `corruption.vaal_equipment_four_outcomes` (an implicit, a socket, the brick, nothing,
  1/4 each) and `corruption.jewel_vaal_outcomes` for a jewel (an implicit, the brick, a unique jewel, nothing; the unique exists on a Cobalt,
  a Crimson and a Viridian Jewel only, and is nothing elsewhere); for the Locus `corruption.locus_four_outcomes` with the two-implicit share
  `s` of `corruption.locus_two_implicit_share_decision` (the owner's 0.25) and `(1 - s) / 3` for each of the sockets, the influenced rare and
  the destruction.
* **The pool** (`corruption.implicit_pool_by_item_class`, `corruption.jewel_implicit_pool`): the mods of generation type `corrupted` in the
  domain of the base (an abyss jewel has its own), with the weight of the first spawn tag the base matches above 0 and a required level of at
  most the item level. It is computed here from the game data, not taken from `actions.corrupted_pool`.
* **The replacement**: the drawn implicit replaces one implicit of the item chosen uniformly, base and Eldritch ones alike
  (`corruption.implicit_replaces_existing`, `eldritch.vaal_replaces_one_implicit`), and is just added to an item with none; a Gilded Fossil
  in a Bloodstained set makes it replace them all (`fossils.bloodstained_gilded_replaces_all_implicits`). The Locus draws a first mod by
  weight and a second from the pool without the mods that share a family with the first (`corruption.locus_second_implicit_other_group`);
  the two replace two of three or more implicits chosen uniformly among the pairs, both of two, the one of one (`locus.replaces_two_implicits`).
* **The values**: each stat of a drawn mod rolls uniformly over its integers (`affix_pool.values_uniform_integers`).

What the samplers do not write again is the part that no claim of B4 adds. **The dead ends** (the Vaal Orb's brick, a unique jewel, the
Locus's influenced rare and destruction) are left as the item corrupted, a rare, with its fractured mods and nothing else: for a target that
asks for a corrupted implicit every one of them is final and holds no corrupted implicit, so what else the brick rolls cannot matter. A
target that only allows a corrupted item (whose brick is a full fill, ticket #260) is out of these samplers' reach. **The reroll** of a
Bloodstained resonator's other fossils is the fossil action's own (`BloodstainedOutcomes.reroll`, checked with the fossils); only the
implicit draw on top of it is written here (`corruption.bloodstained_fossil_implicit`, `corruption.bloodstained_never_fails`: it is always
added, independently of the reroll).

Each sampler fits the `Action` protocol of this package (`outcomes(data, item)` returns an object with `sample(rng)`), so a `Step` takes it. A corrupted
item is refused with `ValueError`, as is a base with no pool or an empty pool at the item level: the samplers model no refusal of the game,
they stand for an action the caller already knows applies.
"""

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

from crafting_system.data import GameData, Mod
from crafting_system.items import ImplicitMod, Item, Rarity, spawn_weight
from crafting_system.items.implicits import BASE_GRADE, corrupted_pool_domain
from crafting_system.rules import get_rule


__all__ = [
    "SampledBloodstained",
    "SampledLocus",
    "SampledVaalOrb",
    "corrupted_pool",
]

VAAL_FOUR = get_rule("corruption.vaal_equipment_four_outcomes")
JEWEL_FOUR = get_rule("corruption.jewel_vaal_outcomes")
LOCUS_FOUR = get_rule("corruption.locus_four_outcomes")
LOCUS_SHARE = get_rule("corruption.locus_two_implicit_share_decision")
CLAIMS = frozenset(
    {
        VAAL_FOUR.id,
        JEWEL_FOUR.id,
        LOCUS_FOUR.id,
        LOCUS_SHARE.id,
        "corruption.implicit_pool_by_item_class",
        "corruption.jewel_implicit_pool",
        "corruption.implicit_replaces_existing",
        "eldritch.vaal_replaces_one_implicit",
        "corruption.locus_second_implicit_other_group",
        "locus.replaces_two_implicits",
        "fossils.bloodstained_gilded_replaces_all_implicits",
        "corruption.bloodstained_fossil_implicit",
        "corruption.bloodstained_never_fails",
        "affix_pool.values_uniform_integers",
    }
)
"""The claims the samplers are written from; each is in the registry (`get_rule` raises otherwise, `tests/test_simulator_corruption.py`)."""

GENERATION_CORRUPTED = "corrupted"
EQUIPMENT_DOMAIN = "item"
UNIQUE_JEWELS = frozenset({"Cobalt Jewel", "Crimson Jewel", "Viridian Jewel"})


def corrupted_pool(data: GameData, item: Item) -> tuple[tuple[Mod, int], ...]:
    """The corrupted implicits `item` can draw, each with its weight, in the order of the game data; `ValueError` when there are none."""
    base = data.base_items[item.base_id]
    domain = corrupted_pool_domain(base)
    pool = []
    for mod in data.mods.values():
        if mod.generation_type != GENERATION_CORRUPTED or mod.domain != domain or mod.required_level > item.item_level:
            continue
        weight = spawn_weight(mod, base.tags)
        if weight > 0:
            pool.append((mod, weight))
    if not pool:
        raise ValueError(f"no corrupted implicit can be drawn on {item.base_id} at item level {item.item_level}")
    return tuple(pool)


def _drawn(rng: random.Random, pool: Sequence[tuple[Mod, int]]) -> Mod:
    """One mod of `pool`, by weight."""
    point = rng.randrange(sum(weight for _, weight in pool))
    for mod, weight in pool:
        point -= weight
        if point < 0:
            return mod
    raise AssertionError("unreachable: the point lies below the total weight")


def _rolled(rng: random.Random, mod: Mod) -> ImplicitMod:
    """`mod` as an implicit with each stat rolled uniformly over its integers."""
    return ImplicitMod(mod.id, BASE_GRADE, tuple(rng.randint(min(stat.min, stat.max), max(stat.min, stat.max)) for stat in mod.stats))


def _shares(rng: random.Random, shares: Mapping[str, Fraction]) -> str:
    """One outcome name, with the chance its share gives."""
    point = rng.random() * float(sum(shares.values()))
    for name, share in shares.items():
        point -= float(share)
        if point < 0.0:
            return name
    return name


def _dead(data: GameData, item: Item) -> Item:
    """A dead end: the item corrupted, a rare, holding its fractured mods and nothing else of the explicit ones."""
    return item.changed(data, rarity=Rarity.RARE, corrupted=True, mods=tuple(entry for entry in item.mods if entry.fractured))


def _fractions(value: Mapping[str, float]) -> dict[str, Fraction]:
    return {name: Fraction(str(share)) for name, share in value.items()}


def _refuse_corrupted(item: Item, label: str) -> None:
    if item.corrupted:
        raise ValueError(f"{label} is sampled on an uncorrupted item only")


@dataclass(frozen=True, eq=False)
class _VaalDraw:
    data: GameData
    item: Item
    pool: tuple[tuple[Mod, int], ...]
    shares: Mapping[str, Fraction]
    unique_kills: bool

    def sample(self, rng: random.Random) -> Item:
        outcome = _shares(rng, self.shares)
        if outcome == "implicit":
            held = list(self.item.implicits)
            if held:
                del held[rng.randrange(len(held))]
            drawn = _rolled(rng, _drawn(rng, self.pool))
            return self.item.changed(self.data, corrupted=True, implicits=(*held, drawn))
        if outcome == "brick" or (outcome == "unique" and self.unique_kills):
            return _dead(self.data, self.item)
        return self.item.changed(self.data, corrupted=True)  # nothing, a socket, a unique on a base that has none


@dataclass(frozen=True)
class SampledVaalOrb:
    """A Vaal Orb as the claims describe it, for the simulator."""

    def outcomes(self, data: GameData, item: Item) -> _VaalDraw:
        _refuse_corrupted(item, "a Vaal Orb")
        pool = corrupted_pool(data, item)
        base = data.base_items[item.base_id]
        if corrupted_pool_domain(base) == EQUIPMENT_DOMAIN:
            shares = _fractions(VAAL_FOUR.value)  # implicit, socket_colour, brick, nothing
            return _VaalDraw(data, item, pool, shares, unique_kills=False)
        # the jewel claim states four equal outcomes and carries no value: an implicit, a rare jewel (the brick), a unique, nothing
        shares = {"implicit": Fraction(1, 4), "brick": Fraction(1, 4), "unique": Fraction(1, 4), "nothing": Fraction(1, 4)}
        return _VaalDraw(data, item, pool, shares, unique_kills=base.name in UNIQUE_JEWELS)


@dataclass(frozen=True, eq=False)
class _LocusDraw:
    data: GameData
    item: Item
    pool: tuple[tuple[Mod, int], ...]
    shares: Mapping[str, Fraction]

    def sample(self, rng: random.Random) -> Item:
        outcome = _shares(rng, self.shares)
        if outcome == "sockets_non_white":
            return self.item.changed(self.data, corrupted=True)
        if outcome != "two_implicits":  # the influenced rare and the destruction
            return _dead(self.data, self.item)
        first = _drawn(rng, self.pool)
        rest = [(mod, weight) for mod, weight in self.pool if set(mod.families).isdisjoint(first.families)]
        if not rest:
            raise ValueError(f"no corrupted implicit of another group is left after {first.id}")
        second = _drawn(rng, rest)
        held = list(self.item.implicits)
        if len(held) <= 2:
            held = []
        else:
            gone = rng.choice(list(combinations(range(len(held)), 2)))
            held = [entry for index, entry in enumerate(held) if index not in gone]
        drawn = (_rolled(rng, first), _rolled(rng, second))
        return self.item.changed(self.data, corrupted=True, implicits=(*held, *drawn))


@dataclass(frozen=True)
class SampledLocus:
    """One use of the Locus of Corruption's altar as the claims describe it; `share` is the two-implicit share (the owner's decision by default)."""

    share: Fraction | None = None

    def outcomes(self, data: GameData, item: Item) -> _LocusDraw:
        _refuse_corrupted(item, "the Locus of Corruption")
        share = Fraction(str(LOCUS_SHARE.value["share"])) if self.share is None else Fraction(self.share)
        names = list(LOCUS_FOUR.value)  # two_implicits, sockets_non_white, influenced_rare, destroyed
        shares = {name: share if name == "two_implicits" else (1 - share) / 3 for name in names}
        return _LocusDraw(data, item, corrupted_pool(data, item), shares)


@dataclass(frozen=True, eq=False)
class _BloodstainedDraw:
    data: GameData
    reroll: object
    pool: tuple[tuple[Mod, int], ...]
    replaces_all: bool

    def sample(self, rng: random.Random) -> Item:
        rerolled = self.reroll.sample(rng)
        held = [] if self.replaces_all else list(rerolled.implicits)
        if held:
            del held[rng.randrange(len(held))]
        drawn = _rolled(rng, _drawn(rng, self.pool))
        return rerolled.changed(self.data, corrupted=True, implicits=(*held, drawn))


@dataclass(frozen=True)
class SampledBloodstained:
    """A resonator holding the Bloodstained Fossil: the reroll of `resonator` without it, then the implicit as the claims describe it.

    `resonator` is the `actions.ApplyFossils` set with the Bloodstained Fossil; the reroll of its other fossils and whether it holds a
    Gilded Fossil are read from its outcomes (`reroll`, `draw.replaces_all`), never its implicit draw.
    """

    resonator: object

    def outcomes(self, data: GameData, item: Item) -> _BloodstainedDraw:
        _refuse_corrupted(item, "a Bloodstained resonator")
        given = self.resonator.outcomes(data, item)
        reroll, draw = getattr(given, "reroll", None), getattr(given, "draw", None)
        if reroll is None or draw is None:
            raise ValueError(f"{self.resonator!r} holds no Bloodstained Fossil")
        return _BloodstainedDraw(data, reroll, corrupted_pool(data, item), bool(draw.replaces_all))
