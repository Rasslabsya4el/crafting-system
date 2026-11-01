"""Embers, Ichors, the three Eldritch orbs and the Orb of Conflict as exact actions (ticket #151, ADR-0025, ADR-0027).

An item holds at most one Eldritch implicit per side, Searing Exarch (the prefix side) and Eater of Worlds (the suffix
side), each with a grade 1 Lesser to 6 Perfect. **Dominance** is derived from the two grades and never stored
(`items.dominant_side`): the higher grade wins, a lone implicit is dominant by itself, equal grades or none give nothing.

* `EldritchImplicitCurrency(side, grade)`: an Ember (Exarch) or an Ichor (Eater) of grade 1 to 4. It puts an implicit of
  that side and grade on a normal, magic or rare body armour, boots, gloves or helmet, replacing every implicit but the
  other side's. The mod is drawn by the spawn weight of the item class among the mods of the side and the grade, so the
  "Unique Enemy" variants join from grade 2 (they weigh half) and the "Pinnacle Boss" variants from grade 3 (a fifth),
  all read from the game data. The same mod may come back (`eldritch.ember_may_return_same_family`, approximate); there is
  no item-level gate. Its result is a `Finite` list, one item per mod of the pool, each implicit at its lowest values.
* `EldritchChaosOrb()`: on a rare item with a dominant side, removes the modifiers of that side that are not fractured and
  draws new ones onto it. The count is Craft of Exile's (approximate): the total of 4, 5 or 6 (8:3:1) less the mods that
  stay, clamped to the free slots of the side. It ignores the lock metamods and keeps the Attack/Caster ones.
* `EldritchExaltedOrb()`: on a rare item with a dominant side that has a free slot, adds one mod to that side by the
  ordinary affix draw restricted to it. An open slot of a locked side fills.
* `EldritchAnnulmentOrb()`: on a magic or rare item with a dominant side, removes one mod of that side, uniformly among the
  mods that are not fractured, not on a locked side and not protected by an Attack/Caster metamod (approximate).
* `OrbOfConflict()`: on an item with both implicits, raises one by a grade and lowers the other by a grade. The higher
  implicit is raised with a probability from a logistic fit to a player sample (`conflict_raise_chance`), the lower one
  with the rest, and each with 1/2 at equal grades. Raising a Perfect implicit does nothing and the other is still lowered;
  a lowered Lesser implicit is removed. Every answer that reads it carries the approximate marks of its claims.

Every one of them refuses a corrupted item, an influenced item (Eldritch implicits and influence exclude each other) and
an item class other than the four above. Nothing here is block-invariant (ADR-0023): the coarse state refuses them.

A raised or lowered implicit is the mod of the same family and variant one grade away (the id ends in the grade); a
mod the data does not have there is `OutOfScopeError`. A lowered "Unique Enemy" or "Pinnacle Boss" variant may land on a
grade whose weight is 0 (a variant no Ember draws); the data has the mod and no source says the game refuses it, so
Conflict keeps it.

The Eldritch currency (`eldritch.py`, ticket #151, ADR-0025): `EldritchImplicitCurrency(side, grade)` (an Ember or an Ichor of grade 1 to
4: an implicit drawn by the spawn weight of the item class, replacing every implicit but the other side's), `EldritchChaosOrb()`,
`EldritchExaltedOrb()` and `EldritchAnnulmentOrb()` (they act on the dominant side, derived from the two grades: `item_dominant_side`) and
`OrbOfConflict()` (raises one implicit by a grade and lowers the other, odds `conflict_raise_chance(difference)`). They work on a body
armour, boots, gloves or helmet that is not corrupted and not influenced, and none is a planner kind yet.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction

from crafting_system.data import BaseItem, GameData, Mod
from crafting_system.items import (
    EldritchSide,
    ImplicitMod,
    Item,
    Rarity,
    Side,
    UnknownBaseError,
    dominant_side,
    eldritch_grade,
    eldritch_side,
    spawn_weight,
)
from crafting_system.rules import get_rule

from .add import refuse_if_nothing_to_draw
from .catalog import kind
from .contract import Action, Adds, Reads
from .errors import NotApplicableError, OutOfScopeError
from .finite import Finite
from .metamods import allowed_by_tags, blocked_tags, locked_sides, on_locked_side
from .outcomes import Outcomes
from .pool import PoolFamily, build_pool

__all__ = [
    "EldritchAnnulmentOrb",
    "EldritchChaosOrb",
    "EldritchExaltedOrb",
    "EldritchImplicitCurrency",
    "OrbOfConflict",
    "conflict_raise_chance",
    "implicit_pool",
    "item_dominant_side",
]

TARGETS = get_rule("eldritch.ember_ichor_targets")
RARITY_AND_INFLUENCE = get_rule("eldritch.ember_ichor_rarity_and_influence")
NOT_INFLUENCE = get_rule("eldritch.not_influence")
EMBER_REPLACES_IMPLICITS = get_rule("eldritch.ember_replaces_implicits")
MAY_RETURN_SAME_FAMILY = get_rule("eldritch.ember_may_return_same_family")
GRADE_IS_TIER = get_rule("eldritch.grade_is_tier")
POOL_BY_ITEM_CLASS = get_rule("eldritch.implicit_pool_by_item_class")
PRESENCE_VARIANT_WEIGHTS = get_rule("eldritch.presence_variant_weights")
NO_ITEM_LEVEL_GATE = get_rule("eldritch.no_item_level_gate")
DOMINANCE_HIGHER_TIER = get_rule("eldritch.dominance_higher_tier")
DOMINANCE_SOLE_IMPLICIT = get_rule("eldritch.dominance_sole_implicit")
DOMINANT_SIDE = get_rule("eldritch.dominant_side")
ACCEPTS_RARITY = get_rule("eldritch.chaos_accepts_rare_only")
CHAOS_REROLLS_DOMINANT_SIDE = get_rule("eldritch.chaos_rerolls_dominant_side")
CHAOS_COUNT = get_rule("eldritch.chaos_count_follows_craft_of_exile")
EXALTED_ADDS_ONE = get_rule("eldritch.exalted_adds_one_to_dominant_side")
ANNUL_REMOVES_ONE = get_rule("eldritch.annul_removes_one_from_dominant_side")
METAMOD_INTERACTION = get_rule("eldritch.metamod_interaction")
CONFLICT_REQUIRES_BOTH = get_rule("eldritch.conflict_requires_both")
CONFLICT_RAISE_ONE_LOWER_OTHER = get_rule("eldritch.conflict_raise_one_lower_other")
CONFLICT_ODDS_FIT = get_rule("eldritch.conflict_odds_fit")
CONFLICT_MEASURED_ODDS = get_rule("eldritch.conflict_measured_odds")
CONFLICT_TOP_TIER_NOOP = get_rule("eldritch.conflict_top_tier_raise_is_noop")
CONFLICT_KEEPS_VARIANT = get_rule("eldritch.conflict_keeps_the_variant_it_moves_to")
IMPLICIT_VALUE_RANGE = get_rule("eldritch.implicit_value_range")
COST = get_rule("eldritch.cost")
KEPT_MODS_COUNT_IN_TOTAL = get_rule("chaos_orb.kept_mods_count_in_total")
RARE_REROLL_RATIO = get_rule("affix_count.rare_reroll_ratio")

SIDE_OF: Mapping[EldritchSide, Side] = {EldritchSide.EXARCH: Side.PREFIX, EldritchSide.EATER: Side.SUFFIX}
"""The explicit side an Eldritch side acts on: Searing Exarch dominant means the prefixes, Eater of Worlds the suffixes."""
OTHER = {EldritchSide.EXARCH: EldritchSide.EATER, EldritchSide.EATER: EldritchSide.EXARCH}
MIN_GRADE, MAX_CURRENCY_GRADE, MAX_GRADE = 1, 4, 6
ONE = Fraction(1)
HALF = Fraction(1, 2)
CURRENCY_KEY = {EldritchSide.EXARCH: "ember", EldritchSide.EATER: "ichor"}


# --- eligibility ---------------------------------------------------------------------------------------------------


def eligible_class(data: GameData, item: Item) -> bool:
    """Whether `item` is a body armour, boots, gloves or helmet of the game data (the classes of the Eldritch currency)."""
    base = data.base_items.get(item.base_id)
    return base is not None and base.item_class in TARGETS.value


def _refuse_ineligible(data: GameData, item: Item, what: str) -> BaseItem:
    """Raise `NotApplicableError` when `what` cannot be used on `item` at all; return the item's base otherwise."""
    base = data.base_items.get(item.base_id)
    if base is None:
        raise UnknownBaseError(f"item on {item.base_id}: the base is not in the game data")
    if item.corrupted:
        raise NotApplicableError(f"the item is corrupted, and a corrupted item takes no {what}")
    if base.item_class not in TARGETS.value:
        raise NotApplicableError(
            f"{what} works on a {', '.join(TARGETS.value)} only, and this item is a {base.item_class}"
        )
    if item.influences:
        raise NotApplicableError(f"{what} cannot be used on an influenced item: Eldritch implicits and influence exclude each other")
    return base


def item_dominant_side(data: GameData, item: Item) -> EldritchSide | None:
    """The dominant Eldritch side of `item`, derived from the grades of its two implicits; None for none."""
    held = item.eldritch_implicits(data)
    exarch, eater = held.get(EldritchSide.EXARCH), held.get(EldritchSide.EATER)
    return dominant_side(0 if exarch is None else exarch.grade, 0 if eater is None else eater.grade)


def _require_dominance(data: GameData, item: Item, what: str) -> EldritchSide:
    side = item_dominant_side(data, item)
    if side is None:
        raise NotApplicableError(
            f"{what} needs a dominant Eldritch side, and this item has none "
            "(no Eldritch implicit, or the two implicits have the same grade)"
        )
    return side


# --- the implicit pool ---------------------------------------------------------------------------------------------

_INDEX_LIMIT = 8
_INDEX: dict[int, tuple[GameData, Mapping[tuple[EldritchSide, int], tuple[Mod, ...]]]] = {}


def _eldritch_index(data: GameData) -> Mapping[tuple[EldritchSide, int], tuple[Mod, ...]]:
    """Every Eldritch implicit mod of `data` by (side, grade), in data order; cached per game data object."""
    found = _INDEX.get(id(data))
    if found is not None and found[0] is data:
        return found[1]
    grouped: dict[tuple[EldritchSide, int], list[Mod]] = {}
    for mod in data.mods.values():
        side = eldritch_side(mod)
        if side is not None:
            grouped.setdefault((side, eldritch_grade(mod)), []).append(mod)
    index = {key: tuple(mods) for key, mods in grouped.items()}
    if len(_INDEX) >= _INDEX_LIMIT:
        _INDEX.clear()
    _INDEX[id(data)] = (data, index)
    return index


def implicit_pool(data: GameData, base: BaseItem, side: EldritchSide, grade: int) -> tuple[tuple[Mod, int], ...]:
    """The mods an Ember or an Ichor of `grade` can give a `base`, each with its spawn weight, in data order.

    The mods of the side and the grade with a positive spawn weight on the base's tags. The weight is that of the item
    class and does not depend on the item level (`eldritch.no_item_level_gate`); the Unique-Presence and Pinnacle-Presence
    variants are in the pool exactly where the data gives them a weight (`eldritch.presence_variant_weights`).
    """
    weighted = ((mod, spawn_weight(mod, base.tags)) for mod in _eldritch_index(data).get((side, grade), ()))
    return tuple((mod, weight) for mod, weight in weighted if weight > 0)


def _low_values(mod: Mod) -> tuple[int, ...]:
    return tuple(min(stat.min, stat.max) for stat in mod.stats)


def _implicit(mod: Mod) -> ImplicitMod:
    """The Eldritch implicit `mod` at its grade, every value at its lowest (a result of an exact action holds no roll)."""
    return ImplicitMod(mod.id, eldritch_grade(mod), _low_values(mod))


# --- Embers and Ichors ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EldritchImplicitCurrency(Action):
    """One Ember (`side` Searing Exarch) or Ichor (`side` Eater of Worlds) of `grade` 1 Lesser to 4 Exceptional."""

    side: EldritchSide
    grade: int

    def __post_init__(self) -> None:
        if not isinstance(self.side, EldritchSide):
            raise ValueError(f"side {self.side!r} is not an EldritchSide")
        if type(self.grade) is not int or not MIN_GRADE <= self.grade <= MAX_CURRENCY_GRADE:
            raise ValueError(
                f"an Ember or an Ichor has a grade from {MIN_GRADE} to {MAX_CURRENCY_GRADE} "
                f"(grades 5 and 6 come only from the Orb of Conflict), got {self.grade!r}"
            )

    def label(self, data: GameData | None = None) -> str:
        return COST.value[CURRENCY_KEY[self.side]][self.grade]

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {self.label(): 1}

    def reads(self, data: GameData) -> Reads:
        # The mods of the item are kept and never looked at; the result depends on the other side's implicit, which stays.
        return Reads(junk=True, families=frozenset(), implicits=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset(), draws=False, implicits=True)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset(
            rule.id
            for rule in (
                TARGETS, RARITY_AND_INFLUENCE, NOT_INFLUENCE, EMBER_REPLACES_IMPLICITS, MAY_RETURN_SAME_FAMILY, GRADE_IS_TIER,
                POOL_BY_ITEM_CLASS, PRESENCE_VARIANT_WEIGHTS, IMPLICIT_VALUE_RANGE, NO_ITEM_LEVEL_GATE, COST,
            )
        )

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """One result per mod of the pool, with the chance `weight / total weight`.

        Raises `NotApplicableError` for a corrupted or an influenced item and for a class other than the four; the
        rarity and the item level do not matter. The other side's implicit stays, every other implicit goes.
        """
        base = _refuse_ineligible(data, item, self.label())
        pool = implicit_pool(data, base, self.side, self.grade)
        if not pool:
            raise OutOfScopeError(
                f"the game data holds no {self.side.value} implicit of grade {self.grade} with a spawn weight on a {base.item_class}"
            )
        kept = tuple(
            entry for entry in item.eldritch_implicits(data).values() if eldritch_side(data.mods[entry.mod_id]) is OTHER[self.side]
        )
        total = sum(weight for _, weight in pool)
        return Finite(
            data,
            item,
            tuple(
                (Fraction(weight, total), item.changed(data, implicits=(*kept, _implicit(mod)))) for mod, weight in pool
            ),
        )


@kind(
    "eldritch-implicit-currency",
    order=90,
    planner=False,
    applies_only_to="armour",
    why_not="a target cannot name an Eldritch implicit yet, and the dominance-limited kernels are ticket #152",
)
def _implicit_currency(data: GameData, item: Item):
    if eligible_class(data, item) and not item.corrupted and not item.influences:
        for side in EldritchSide:
            for grade in range(MIN_GRADE, MAX_CURRENCY_GRADE + 1):
                yield EldritchImplicitCurrency(side, grade)


# --- the three Eldritch orbs ---------------------------------------------------------------------------------------


def _dominant_pool(data: GameData, retained: Item, side: Side) -> tuple[PoolFamily, ...]:
    """The pool of the ordinary affix draw on `retained`, restricted to the families of `side`."""
    return tuple(family for family in build_pool(data, retained) if family.side is side)


@dataclass(frozen=True)
class EldritchChaosOrb(Action):
    """One Eldritch Chaos Orb."""

    def label(self, data: GameData | None = None) -> str:
        return COST.value["chaos"]

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {self.label(): 1}

    def reads(self, data: GameData) -> Reads:
        # The other side's mods stay and block families of the draw, so they are told apart one by one.
        return Reads(junk=True, implicits=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset())

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset(
            rule.id
            for rule in (
                NOT_INFLUENCE, DOMINANCE_HIGHER_TIER, DOMINANCE_SOLE_IMPLICIT, DOMINANT_SIDE, ACCEPTS_RARITY, CHAOS_REROLLS_DOMINANT_SIDE,
                CHAOS_COUNT, METAMOD_INTERACTION, KEPT_MODS_COUNT_IN_TOTAL, RARE_REROLL_RATIO, COST,
            )
        )

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """The modifiers of the dominant side that are not fractured go, then the total of 4, 5 or 6 less the mods that stay is drawn onto it.

        Raises `NotApplicableError` for an item that is not rare, is corrupted, is influenced, is of another class or has
        no dominant side. The lock metamods do not protect the side; an Attack or Caster metamod that stays on the
        item filters the draw, and one that goes with the side does not.
        """
        _refuse_ineligible(data, item, self.label())
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError(f"an Eldritch Chaos Orb works on a rare item only, and this item is {item.rarity}")
        side = SIDE_OF[_require_dominance(data, item, self.label())]
        kept = tuple(entry for entry in item.mods if entry.fractured or data.mods[entry.mod_id].generation_type != side.value)
        retained = item.changed(data, mods=kept)
        return Outcomes.over(data, retained, _dominant_pool(data, retained, side), None, None)


@dataclass(frozen=True)
class EldritchExaltedOrb(Action):
    """One Eldritch Exalted Orb."""

    def label(self, data: GameData | None = None) -> str:
        return COST.value["exalted"]

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {self.label(): 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset(), pool_weight=True, implicits=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset())

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset(
            rule.id
            for rule in (
                NOT_INFLUENCE, DOMINANCE_HIGHER_TIER, DOMINANCE_SOLE_IMPLICIT, DOMINANT_SIDE, ACCEPTS_RARITY, EXALTED_ADDS_ONE,
                METAMOD_INTERACTION, COST,
            )
        )

    def outcomes(self, data: GameData, item: Item) -> Outcomes:
        """One more mod on the dominant side, drawn by weight from the ordinary pool of that side.

        Raises `NotApplicableError` for an item that is not rare, is corrupted, is influenced, is of another class, has
        no dominant side, or whose dominant side has no free slot or no legal mod. An open slot of a locked side still
        fills, and the Attack and Caster metamods keep the mods with their tag out of the pool.
        """
        _refuse_ineligible(data, item, self.label())
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError(f"an Eldritch Exalted Orb works on a rare item only, and this item is {item.rarity}")
        side = SIDE_OF[_require_dominance(data, item, self.label())]
        pool = _dominant_pool(data, item, side)
        if item.free_slots(data, side) <= 0:
            raise NotApplicableError(f"an Eldritch Exalted Orb cannot add a mod: the dominant {side.value} side is full")
        result = Outcomes(data, item, pool, {len(item.mods) + 1: ONE}, None, None)
        refuse_if_nothing_to_draw(data, item, pool, "an Eldritch Exalted Orb")
        return result


@dataclass(frozen=True)
class EldritchAnnulmentOrb(Action):
    """One Eldritch Orb of Annulment."""

    def label(self, data: GameData | None = None) -> str:
        return COST.value["annulment"]

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {self.label(): 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset(), implicits=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.removal()

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset(
            rule.id
            for rule in (
                NOT_INFLUENCE, DOMINANCE_HIGHER_TIER, DOMINANCE_SOLE_IMPLICIT, DOMINANT_SIDE, ACCEPTS_RARITY, ANNUL_REMOVES_ONE,
                METAMOD_INTERACTION, COST,
            )
        )

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """One result per removable mod of the dominant side, each with chance 1/n; the rarity stays.

        Raises `NotApplicableError` for a normal, corrupted or influenced item, one of another class, one with no
        dominant side, and one whose dominant side has no mod that is not fractured, not on a locked side and not
        protected by an Attack or Caster metamod.
        """
        _refuse_ineligible(data, item, self.label())
        if item.rarity is Rarity.NORMAL:
            raise NotApplicableError("an Eldritch Orb of Annulment works on a magic or rare item only, and this item is normal")
        side = SIDE_OF[_require_dominance(data, item, self.label())]
        locked, blocked = locked_sides(data, item), blocked_tags(data, item)
        removable = [
            entry
            for entry in item.mods
            if data.mods[entry.mod_id].generation_type == side.value
            and not entry.fractured
            and not on_locked_side(data, entry, locked)
            and allowed_by_tags(data.mods[entry.mod_id], blocked)
        ]
        if not removable:
            raise NotApplicableError(
                f"an Eldritch Orb of Annulment cannot be used here: the dominant {side.value} side has no mod that is not "
                "fractured, not on a locked side and not protected by a tag metamod to remove"
            )
        share = Fraction(1, len(removable))
        return Finite(data, item, tuple((share, item.remove_mod(data, entry.mod_id)) for entry in removable))


@kind(
    "eldritch-chaos-orb",
    order=91,
    planner=False,
    applies_only_to="armour",
    why_not="a target cannot name an Eldritch implicit yet, and the dominance-limited kernels are ticket #152",
)
def _eldritch_chaos(data: GameData, item: Item):
    if eligible_class(data, item) and not item.corrupted and not item.influences and item.rarity is Rarity.RARE:
        yield EldritchChaosOrb()


@kind(
    "eldritch-exalted-orb",
    order=92,
    planner=False,
    applies_only_to="armour",
    why_not="a target cannot name an Eldritch implicit yet, and the dominance-limited kernels are ticket #152",
)
def _eldritch_exalted(data: GameData, item: Item):
    if eligible_class(data, item) and not item.corrupted and not item.influences and item.rarity is Rarity.RARE:
        yield EldritchExaltedOrb()


@kind(
    "eldritch-annulment-orb",
    order=93,
    planner=False,
    applies_only_to="armour",
    why_not="a target cannot name an Eldritch implicit yet, and the dominance-limited kernels are ticket #152",
)
def _eldritch_annulment(data: GameData, item: Item):
    if eligible_class(data, item) and not item.corrupted and not item.influences and item.rarity is not Rarity.NORMAL:
        yield EldritchAnnulmentOrb()


# --- the Orb of Conflict -------------------------------------------------------------------------------------------


def conflict_raise_chance(difference: int) -> Fraction:
    """The chance that an Orb of Conflict raises the higher implicit, `difference` = its grade less the lower one's, 0 or more.

    `p = 1 / (1 + exp(-(intercept - slope * difference)))` rounded to `places` decimals (the claim `eldritch.conflict_odds_fit`,
    computed in decimal arithmetic so that it is the same on every machine); at equal grades each side is raised with
    probability 1/2. The lower implicit is raised with `1 - p`.
    """
    if difference < 0:
        raise ValueError(f"the difference is the higher grade less the lower one, at least 0, got {difference}")
    if difference == 0:
        return HALF
    fit = CONFLICT_ODDS_FIT.value
    scale = 10 ** fit["places"]
    with localcontext() as context:
        context.prec = 60
        exponent = -(Decimal(fit["intercept"]) - Decimal(fit["slope"]) * difference)
        chance = 1 / (1 + exponent.exp())
        return Fraction(int((chance * scale).to_integral_value()), scale)


def conflict_is_extrapolated(difference: int) -> bool:
    """Whether a grade difference lies outside the sample the fit rests on (the answer marks it)."""
    return difference > CONFLICT_ODDS_FIT.value["last_sampled_difference"]


def _sibling(data: GameData, entry: ImplicitMod, grade: int) -> ImplicitMod:
    """The Eldritch implicit of the same family and variant as `entry`, at `grade`, at its lowest values."""
    mod_id = entry.mod_id[:-1] + str(grade)
    mod = data.mods.get(mod_id)
    if mod is None or eldritch_side(mod) is not eldritch_side(data.mods[entry.mod_id]) or eldritch_grade(mod) != grade:
        raise OutOfScopeError(f"the game data holds no grade {grade} of the Eldritch implicit {entry.mod_id}")
    return _implicit(mod)


@dataclass(frozen=True)
class OrbOfConflict(Action):
    """One Orb of Conflict."""

    def label(self, data: GameData | None = None) -> str:
        return COST.value["conflict"]

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {self.label(): 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset(), implicits=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset(), draws=False, implicits=True)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset(
            rule.id
            for rule in (
                NOT_INFLUENCE, CONFLICT_REQUIRES_BOTH, CONFLICT_RAISE_ONE_LOWER_OTHER, CONFLICT_ODDS_FIT, CONFLICT_MEASURED_ODDS,
                CONFLICT_TOP_TIER_NOOP, CONFLICT_KEEPS_VARIANT, GRADE_IS_TIER, IMPLICIT_VALUE_RANGE, COST,
            )
        )

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """Two results: the Searing Exarch implicit is raised and the Eater one lowered, or the other way round.

        Raises `NotApplicableError` for a corrupted or an influenced item, one of another class, and one that does not
        hold an implicit on both sides. The side raised is the higher implicit with `conflict_raise_chance`, the lower one
        with the rest; a raise of a Perfect implicit changes nothing, and a lowered Lesser implicit is removed.
        """
        _refuse_ineligible(data, item, self.label())
        held = item.eldritch_implicits(data)
        if len(held) != 2:
            raise NotApplicableError("an Orb of Conflict needs a Searing Exarch and an Eater of Worlds implicit, and this item lacks one")
        exarch, eater = held[EldritchSide.EXARCH], held[EldritchSide.EATER]
        higher = dominant_side(exarch.grade, eater.grade)
        if higher is None:
            raised_chance = {EldritchSide.EXARCH: HALF, EldritchSide.EATER: HALF}
        else:
            chance = conflict_raise_chance(abs(exarch.grade - eater.grade))
            raised_chance = {higher: chance, OTHER[higher]: ONE - chance}
        results = []
        for raised, chance in raised_chance.items():
            lowered = OTHER[raised]
            changed: dict[EldritchSide, ImplicitMod | None] = {raised: held[raised], lowered: None}
            if held[raised].grade < MAX_GRADE:
                changed[raised] = _sibling(data, held[raised], held[raised].grade + 1)
            if held[lowered].grade > MIN_GRADE:
                changed[lowered] = _sibling(data, held[lowered], held[lowered].grade - 1)
            others = tuple(entry for entry in item.implicits if entry not in held.values())
            implicits = (*others, *(entry for entry in changed.values() if entry is not None))
            results.append((chance, item.changed(data, implicits=implicits)))
        return Finite(data, item, tuple(results))


@kind(
    "orb-of-conflict",
    order=94,
    planner=False,
    applies_only_to="armour",
    why_not="a target cannot name an Eldritch implicit yet, and the dominance-limited kernels are ticket #152",
)
def _orb_of_conflict(data: GameData, item: Item):
    if eligible_class(data, item) and not item.corrupted and not item.influences:
        yield OrbOfConflict()
