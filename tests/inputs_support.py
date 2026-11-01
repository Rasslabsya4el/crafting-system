"""Toy actions for the contract of inputs and rule axes (ticket #210): defined only in tests, nothing in `src` names them.

`ToyGraft` is a two-input action in the spirit of ADR-0024's toy, without the simulator: it consumes a donor (a `Need`
from a magic amulet to a rare one that holds a Lightning damage prefix and a mana leech suffix) and adds one of the donor's
two mods to the rare item in hand. Which one is a rule the sources leave open, the axis `toy.pick`: the chance of the
damage mod is 1/4, 1/2 (the plan) or 3/4, so the same item has three kernels. A mod whose family the item already
holds, or whose side is full, cannot be added, and the other is then certain whatever the reading.

`ToyCoin` is an input-free action with an axis of its own (`toy.coin`, 1/3 or 1/2 for heads), so the product of the axes
of both is six readings. Heads removes a random removable mod, tails the first one.
"""

import dataclasses
from fractions import Fraction

from abstraction_pool import DAMAGE_1, LIFE_1, MANA_1, RESIST_2
from contract_support import CONTRACT_DATA, _item, _roll

from crafting_system.actions import Action, Adds, Axis, Finite, Kind, Need, NotApplicableError, Reading, Reads
from crafting_system.data import GameData
from crafting_system.items import Item, Rarity

TOY_ORB = "Toy Graft Orb"
TOY_COIN = "Toy Coin"

PICK = Axis("toy.pick", (Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)), Fraction(1, 2))
COIN = Axis("toy.coin", (Fraction(1, 3), Fraction(1, 2)), Fraction(1, 2))


def donor_start() -> Item:
    """What the donor begins as: a magic amulet with the damage prefix."""
    return _item(Rarity.MAGIC, _roll(DAMAGE_1))


def donor_want() -> Item:
    """What the donor must become: a rare amulet with the damage prefix and the mana leech suffix."""
    return _item(Rarity.RARE, _roll(DAMAGE_1), _roll(MANA_1))


@dataclasses.dataclass(frozen=True)
class ToyGraft(Action):
    """Adds the damage mod or the mana mod of its donor to a rare item, when it fits; `with_axis` False pins the pick at 1/2."""

    with_axis: bool = True

    def label(self, data: GameData | None = None) -> str:
        return "Toy Graft"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {TOY_ORB: 1}

    def reads(self, data: GameData) -> Reads:
        families = frozenset(family for mod_id in (DAMAGE_1, MANA_1) for family in data.mods[mod_id].families)
        return Reads(junk=True, families=families, input_mods=True)  # which families it holds; the donor's two mods

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(draws=False)

    def inputs(self, data: GameData, item: Item | None = None) -> tuple[Need, ...]:
        return (Need(donor_start(), donor_want()),)

    def rule_axes(self, data: GameData) -> tuple[Axis, ...]:
        return (PICK,) if self.with_axis else ()

    def outcomes(self, data: GameData, item: Item, reading: Reading | None = None) -> Finite:
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError("the toy graft works on a rare item only")
        damage = (reading or Reading()).get(PICK.name, PICK.plan) if self.with_axis else PICK.plan
        (need,) = self.inputs(data, item)
        families = {family for entry in item.mods for family in data.mods[entry.mod_id].families}
        fits = []
        donor = {entry.mod_id: entry for entry in need.want.mods}
        for donor_mod, chance in ((donor[DAMAGE_1], damage), (donor[MANA_1], 1 - damage)):
            mod = data.mods[donor_mod.mod_id]
            side = [e for e in item.mods if data.mods[e.mod_id].generation_type == mod.generation_type]
            if not families & set(mod.families) and len(side) < 3:
                fits.append((chance, donor_mod))
        if not fits:
            raise NotApplicableError("neither mod of the donor fits")
        total = sum(chance for chance, _ in fits)
        return Finite(data, item, tuple((chance / total, item.changed(data, mods=(*item.mods, mod))) for chance, mod in fits))


@dataclasses.dataclass(frozen=True)
class ToyCoin(Action):
    """Heads: removes one removable mod, each with the same chance; tails: removes the first one. No input."""

    def label(self, data: GameData | None = None) -> str:
        return "Toy Coin"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {TOY_COIN: 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset())

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.removal()

    def rule_axes(self, data: GameData) -> tuple[Axis, ...]:
        return (COIN,)

    def outcomes(self, data: GameData, item: Item, reading: Reading | None = None) -> Finite:
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError("the toy coin works on a rare item only")
        removable = [entry for entry in item.mods if not entry.fractured]
        if not removable:
            raise NotApplicableError("the item holds no mod to remove")
        heads = (reading or Reading()).get(COIN.name, COIN.plan)
        chances = {index: heads / len(removable) for index in range(len(removable))}
        chances[0] += 1 - heads
        return Finite(
            data,
            item,
            tuple(
                (chance, item.changed(data, mods=tuple(e for e in item.mods if e is not removable[index])))
                for index, chance in chances.items()
            ),
        )


def graft_members(data: GameData, item: Item):
    if item.rarity is Rarity.RARE:
        yield ToyGraft()


def coin_members(data: GameData, item: Item):
    if item.rarity is Rarity.RARE:
        yield ToyCoin()


GRAFT_KIND = Kind("toy-graft", graft_members, order=901)
COIN_KIND = Kind("toy-coin", coin_members, order=902)

__all__ = ["CONTRACT_DATA", "COIN", "COIN_KIND", "GRAFT_KIND", "LIFE_1", "PICK", "RESIST_2", "ToyCoin", "ToyGraft", "donor_start", "donor_want"]
