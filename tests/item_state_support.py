"""Toy actions and fixture items for the implicits, the quality and the unveil offer of the contract (ticket #142, ADR-0027).

No action of B1 touches those three, so the contract and the compressed state are proved with toys defined here,
as ticket #108 proved the contract with `ToyAnnulment`. Each toy lists its results with `Finite` and subclasses
`Action` only; nothing in `src` changes for one:

* `ToyEmber(grade)`: puts a Searing Exarch implicit of that grade on boots, a mod drawn uniformly among the mods of
  the grade, replacing every implicit but the Eater of Worlds one (it declares `Adds.implicits`);
* `ToyConflict()`: raises the grade of one Eldritch implicit and lowers the other (it declares `Reads.implicits`);
* `ToyCatalyst()`: adds 5 or 10 points to the catalyst quality of an amulet, capped at 20, or restarts from 0 for
  another catalyst type (it declares `Reads.quality` and `Adds.quality`);
* `ToyUnveil()`: draws the offer of the veiled placeholder of an item (it declares `Adds.offer`);
* `ToyPick(k)`: takes the k-th mod of the offer in place of the placeholder (it declares `Reads.offer`).

The data is the contract suite's fixture data plus the hand-written boots, Eldritch, veiled and unveiled records of
`implicits_support`, with two more Eater of Worlds grades so that Conflict has a step to take on both sides.
"""

import dataclasses
from fractions import Fraction

from abstraction_pool import RESIST_2
from contract_support import CONTRACT_DATA
from implicits_support import BOOTS, HAND_MADE, SOME_BOOTS, _eldritch
from items_support import AMULET

from crafting_system.abstraction import Goal, ImplicitWanted, Wanted
from crafting_system.actions import Action, Adds, Finite, NotApplicableError, Reads, kinds
from crafting_system.data import GameData
from crafting_system.items import (
    CatalystType,
    EldritchSide,
    ExplicitMod,
    ImplicitMod,
    Item,
    Quality,
    Rarity,
    eldritch_grade,
    eldritch_side,
    tier_table,
)

EATER = "eater_of_worlds_implicit"
AVOID_SHOCK = ("AvoidShockEldritchImplicit1", "AvoidShockEldritchImplicit2", "AvoidShockEldritchImplicit3")
SHOCK_PROLIFERATION = "ShockProliferationEldritchImplicit1"
PINNACLE_2 = "AvoidShockEldritchImplicitPinnaclePresence2"
CHANCE_TO_SHOCK = ("ChanceToShockEldritchImplicit1", "ChanceToShockEldritchImplicit2", "ChanceToShockEldritchImplicit3")
PLACEHOLDER = "VeiledPrefix"
AILMENTS_1, AILMENTS_2 = "UnveiledPrefixAilments1", "UnveiledPrefixAilments2"
UNVEILED_LIFE, UNVEILED_MANA = "UnveiledPrefixLife1", "UnveiledPrefixMana1"
LEVEL = 84

_EXTRA = (
    _eldritch(CHANCE_TO_SHOCK[0], EATER, "ChanceToShock", [("base_chance_to_shock_%", 7, 7)]),
    _eldritch(CHANCE_TO_SHOCK[2], EATER, "ChanceToShock", [("base_chance_to_shock_%", 13, 13)]),
)
ITEM_DATA: GameData = dataclasses.replace(
    CONTRACT_DATA,
    mods={**CONTRACT_DATA.mods, **{mod.id: mod for mod in (*HAND_MADE, *_EXTRA) if mod.id != "ChanceToShockEldritchImplicitX"}},
    base_items={**CONTRACT_DATA.base_items, BOOTS: SOME_BOOTS},
)
AMULET_TIERS = tier_table(ITEM_DATA, AMULET)


def low(data: GameData, mod_id: str) -> tuple[int, ...]:
    return tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats)


def implicit(mod_id: str, data: GameData = ITEM_DATA) -> ImplicitMod:
    """The Eldritch implicit `mod_id` at its grade, rolled at the low end."""
    return ImplicitMod(mod_id, eldritch_grade(data.mods[mod_id]), low(data, mod_id))


def roll(mod_id: str, data: GameData = ITEM_DATA) -> ExplicitMod:
    return ExplicitMod(mod_id, AMULET_TIERS.get(mod_id, 1), low(data, mod_id))


def boots(*implicits: str, mods: tuple[ExplicitMod, ...] = (), rarity: Rarity = Rarity.RARE) -> Item:
    return Item.build(
        ITEM_DATA, base_id=BOOTS, item_level=LEVEL, rarity=rarity, mods=mods, implicits=tuple(implicit(i) for i in implicits)
    )


def amulet(*mods: ExplicitMod, rarity: Rarity = Rarity.RARE, **fields) -> Item:
    return Item.build(ITEM_DATA, base_id=AMULET, item_level=LEVEL, rarity=rarity, mods=mods, **fields)


def veiled(*mods: ExplicitMod, offer: tuple[str, ...] = ()) -> Item:
    """An amulet with the veiled placeholder, the given mods, and an unveil offer."""
    placeholder = ExplicitMod(PLACEHOLDER, 1, low(ITEM_DATA, PLACEHOLDER))
    return amulet(placeholder, *mods, veil_offer=offer)


def intrinsic(percent: int) -> Quality:
    return Quality(CatalystType.INTRINSIC, percent)


def exarch_goal(*mod_ids: str, min_grade: int | None = None, leaves: tuple = ()) -> Goal:
    """A goal that wants one Eldritch implicit among `mod_ids` (of at least `min_grade`), and the explicit `leaves`."""
    return Goal(leaves, (ImplicitWanted(frozenset(mod_ids), min_grade),))


def _eldritch_mods(data: GameData, side: EldritchSide, grade: int) -> list[str]:
    return sorted(
        mod.id
        for mod in data.mods.values()
        if eldritch_side(mod) is side and mod.id[-1:].isdigit() and eldritch_grade(mod) == grade
    )


@dataclasses.dataclass(frozen=True)
class ToyEmber(Action):
    """A Searing Exarch implicit of `grade`, drawn uniformly among the mods of that grade; the Eater of Worlds implicit stays."""

    grade: int = 1

    def label(self, data: GameData | None = None) -> str:
        return f"Toy Ember {self.grade}"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {"Toy Ember": 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset())  # it keeps the mods and reads none of them, nor any implicit

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset(), draws=False, implicits=True)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        if item.corrupted:
            raise NotApplicableError("a corrupted item takes no Ember")
        if data.base_items[item.base_id].item_class != "Boots":
            raise NotApplicableError("the toy works on boots")
        mods = _eldritch_mods(data, EldritchSide.EXARCH, self.grade)
        kept = tuple(entry for entry in item.implicits if eldritch_side(data.mods[entry.mod_id]) is EldritchSide.EATER)
        chance = Fraction(1, len(mods))
        return Finite(data, item, tuple((chance, item.changed(data, implicits=(*kept, implicit(mod, data)))) for mod in mods))


@dataclasses.dataclass(frozen=True)
class ToyConflict(Action):
    """On an item with both Eldritch implicits: one is raised a grade and the other lowered (a grade 0 is removed), each way 1/2."""

    def label(self, data: GameData | None = None) -> str:
        return "Toy Conflict"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {"Toy Conflict": 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset(), implicits=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset(), draws=False, implicits=True)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        held = item.eldritch_implicits(data)
        if len(held) != 2:
            raise NotApplicableError("the toy needs an implicit on both sides")
        results = []
        for raised in EldritchSide:
            lowered = next(side for side in EldritchSide if side is not raised)
            step = []
            for side, change in ((raised, 1), (lowered, -1)):
                entry = held[side]
                grade = entry.grade + change
                if grade >= 1:
                    mods = [mod for mod in _eldritch_mods(data, side, grade) if mod[:-1] == entry.mod_id[:-1]]
                    if not mods:
                        raise NotApplicableError(f"no grade {grade} of {entry.mod_id}")
                    step.append(implicit(mods[0], data))
            results.append((Fraction(1, 2), item.changed(data, implicits=tuple(step))))
        return Finite(data, item, tuple(results))


@dataclasses.dataclass(frozen=True)
class ToyCatalyst(Action):
    """Intrinsic quality: +5 or +10 points (1/2 each), capped at 20; another type restarts from 0."""

    def label(self, data: GameData | None = None) -> str:
        return "Toy Catalyst"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {"Toy Catalyst": 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset(), quality=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset(), draws=False, quality=True)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        if item.corrupted:
            raise NotApplicableError("a corrupted item takes no catalyst")
        held = item.quality
        base = held.percent if held is not None and held.type is CatalystType.INTRINSIC else 0
        if base >= 20:
            raise NotApplicableError("already at 20%")
        grown = sorted({min(20, base + 5), min(20, base + 10)})
        chance = Fraction(1, len(grown))
        return Finite(data, item, tuple((chance, item.changed(data, quality=intrinsic(percent))) for percent in grown))


@dataclasses.dataclass(frozen=True)
class ToyUnveil(Action):
    """Draws the offer of the placeholder: Ailments 1 with Life and Mana, or Ailments 2 with Life (1/2 each); once only."""

    def label(self, data: GameData | None = None) -> str:
        return "Toy Unveil"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {"Toy Unveil": 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset(), offer=True)  # it is refused when the offer is already drawn

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset(), draws=False, offer=True)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        if not any(data.mods[entry.mod_id].domain == "veiled" for entry in item.mods):
            raise NotApplicableError("the item holds no veiled placeholder")
        if item.veil_offer:
            raise NotApplicableError("the offer is drawn once")
        offers = ((AILMENTS_1, UNVEILED_LIFE, UNVEILED_MANA), (AILMENTS_2, UNVEILED_LIFE))
        return Finite(data, item, tuple((Fraction(1, 2), item.changed(data, veil_offer=offer)) for offer in offers))


@dataclasses.dataclass(frozen=True)
class ToyPick(Action):
    """Takes the `index`-th mod of the offer (in id order) in place of the placeholder, at its lowest values."""

    index: int = 0

    def label(self, data: GameData | None = None) -> str:
        return f"Toy Pick {self.index + 1}"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {"Toy Pick": 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset(), offer=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=None, draws=False, offer=True)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        if not item.veil_offer or self.index >= len(item.veil_offer):
            raise NotApplicableError("no such mod in the offer")
        chosen = item.veil_offer[self.index]
        mod = data.mods[chosen]
        tier = tier_table(data, item.base_id).get(chosen, 1)
        rest = tuple(entry for entry in item.mods if data.mods[entry.mod_id].domain != "veiled")
        if any(set(mod.families) & set(data.mods[entry.mod_id].families) for entry in rest):
            raise NotApplicableError("the picked mod clashes with a mod of the item")
        result = item.changed(data, mods=(*rest, ExplicitMod(chosen, tier, low(data, chosen))))
        return Finite(data, item, ((Fraction(1), result),))


def toy_actions() -> list[Action]:
    return [ToyEmber(1), ToyEmber(2), ToyConflict(), ToyCatalyst(), ToyUnveil(), ToyPick(0), ToyPick(1), ToyPick(2)]


def plain_goal(*leaves: Wanted) -> Goal:
    return Goal(tuple(leaves))


def check_kinds_declare_item_state() -> int:
    """Every registered kind declares no part of the item state, except the one a kind names in `reads_item_state_while_not_planner`.

    No planner kind touches the implicits, the quality or the offer: the planner and the cache see no change in any registered kind that
    is offered. A kind outside the planner may read one part (an influenced Exalted Orb reads the implicits, because it is refused on
    an Eldritch implicit, ticket #154) and then declares that part and no other, and changes none. The kind says so itself; no kind is
    named here. Returns the number of kinds checked.
    """
    checked = 0
    for kind in kinds():
        checked += 1
        for action in kind.members(ITEM_DATA, amulet(roll(RESIST_2))):
            reads, adds = action.reads(ITEM_DATA), action.adds(ITEM_DATA, None)
            part = kind.reads_item_state_while_not_planner
            if part == "any":  # a kind outside the planner that declares the item state it needs (the veiled orbs, #144)
                assert not kind.planner, kind.name
            elif part:
                assert not kind.planner and not adds.item_state, kind.name
                assert getattr(reads, part) and not any(getattr(reads, other) for other in {"implicits", "quality", "offer"} - {part}), kind.name
            else:
                assert not reads.item_state and not adds.item_state, kind.name
    return checked
