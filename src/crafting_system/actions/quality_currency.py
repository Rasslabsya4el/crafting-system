"""The Blacksmith's Whetstone and the Armourer's Scrap: the currencies that put plain quality on a weapon or armour (ticket #229, B6 S3; ADR-0049).

`ApplyQualityCurrency(currency)` adds the quality of one Whetstone (weapons) or one Scrap (armour, shields included) to the item's `PlainQuality`.
Quality changes no odds of the mods, so the action only moves the quality; it is declared `Adds.only_quality`, which makes a planner offer it last, as it
offers a catalyst (ticket #158). The quality it gives is what the Chromatic Orb reads (`socket_colours.py`, ADR-0047) and what makes the Orb of Fusing
available (`socket_orbs.py`, from 20%), so the finish buys it before the orbs (ADR-0049).

**The gain** (`sockets.quality_currency_gain_by_item_level`): since 3.25.0 the amount of one currency item depends on the item level and not on the rarity, by
the formula of the catalysts (ADR-0029): `f = max(1, min(30 * e^(-item level / 30) - 0.3, 20))`, floored with the fraction as the chance of one more point
(`catalyst.gain_formula_and_rounding`, `approximate`; `catalyst.gain_law`). The draft's "+5% normal, +2% magic, +1% rare" is the rule of version 0.8.1. **The cap**
is 20% (the wiki; `catalyst.quality_capped_at_20`, `approximate`): the quality is `min(20, quality + gain)`, and a currency is refused on an item that already holds
20% or more (a start item may hold up to 30%). Unique items (never a start item or a target) are not modelled.
`expected_quality_currency(item_level, target, start)` is the exact mean number of currency items to a target quality: 9.5, 13.3 and 20 to 20% at item levels
75, 84 and 95 (the same law as `catalyst.expected_catalysts`).

**Refusals**, all `NotApplicableError` and spending nothing: a corrupted item, an item class that holds no plain quality, a Whetstone on an armour or a Scrap on
a weapon, and an item at 20% quality or more. **Prices**: `sockets.blacksmiths_whetstone_cost` and `sockets.armourers_scrap_cost` name the items the price file knows.
**Memory Strands** (ADR-0041): the currency neither cuts nor spends, as a catalyst.

**As a burn of Hinekora's Lock** (ticket #295, B8-3, ADR-0056): it changes no mod, so it declares `burn`. It is legal only where the compressed state keeps the
quality (a target names it, ticket #158) and not at 20% or more, where the use is refused: the burn then runs out, and burn and relock is a finite chain.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.data import GameData
from crafting_system.items import PLAIN_QUALITY_ITEM_CLASSES, Item, PlainQuality
from crafting_system.rules import get_rule

from .catalog import kind
from .catalyst import expected_catalysts, gain_law
from .contract import Action, Adds, BurnKeeps, Reads
from .errors import NotApplicableError
from .finite import Finite
from .strand_use import CUT_FOLLOWS_SPEND_TABLE, StrandUse

__all__ = [
    "ARMOUR_CLASSES",
    "ApplyQualityCurrency",
    "MAX_CURRENCY_QUALITY",
    "WEAPON_CLASSES",
    "expected_quality_currency",
    "quality_gain_law",
]

GAIN_BY_ITEM_LEVEL = get_rule("sockets.quality_currency_gain_by_item_level")
GAIN_FORMULA = get_rule("catalyst.gain_formula_and_rounding")
CAPPED_AT_20 = get_rule("catalyst.quality_capped_at_20")
WHETSTONE_COST = get_rule("sockets.blacksmiths_whetstone_cost")
SCRAP_COST = get_rule("sockets.armourers_scrap_cost")

MAX_CURRENCY_QUALITY = 20  # a Whetstone or a Scrap stops at 20% (the wiki, ADR-0049)
ARMOUR_CLASSES = frozenset({"Body Armour", "Boots", "Gloves", "Helmet", "Shield"})
WEAPON_CLASSES = PLAIN_QUALITY_ITEM_CLASSES - ARMOUR_CLASSES
WHETSTONE, SCRAP = "Blacksmith's Whetstone", "Armourer's Scrap"
COSTS = {WHETSTONE: WHETSTONE_COST, SCRAP: SCRAP_COST}
CLASSES = {WHETSTONE: WEAPON_CLASSES, SCRAP: ARMOUR_CLASSES}


def quality_gain_law(item_level: int) -> tuple[tuple[int, Fraction], ...]:
    """The points one Whetstone or Scrap adds at `item_level`, as `(points, probability)` pairs that sum to 1, smallest first (the catalysts' law)."""
    return gain_law(item_level)


def expected_quality_currency(item_level: int, target: int = MAX_CURRENCY_QUALITY, start: int = 0) -> Fraction:
    """The exact mean number of Whetstones or Scraps that take the plain quality from `start` percent to at least `target` (at most 20)."""
    if not 0 <= target <= MAX_CURRENCY_QUALITY:
        raise ValueError(f"the quality of a Whetstone or a Scrap stops at {MAX_CURRENCY_QUALITY}%, not {target}")
    return expected_catalysts(item_level, target, min(start, target))


@dataclass(frozen=True)
class ApplyQualityCurrency(Action):
    """One Blacksmith's Whetstone (`currency` is "Blacksmith's Whetstone", for weapons) or one Armourer's Scrap ("Armourer's Scrap", for armour)."""

    currency: str

    def __post_init__(self) -> None:
        if self.currency not in COSTS:
            raise ValueError(f"the quality currencies are {sorted(COSTS)}, not {self.currency!r}")

    def label(self, data: GameData | None = None) -> str:
        return self.currency

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.untouched(CUT_FOLLOWS_SPEND_TABLE)  # ADR-0041: it draws no mod and the wiki's strand table has no row for it

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COSTS[self.currency].value)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset(rule.id for rule in (GAIN_BY_ITEM_LEVEL, GAIN_FORMULA, CAPPED_AT_20, COSTS[self.currency]))

    def burn(self, data: GameData | None = None) -> bool:
        """A quality currency is a burn of Hinekora's Lock (ADR-0056): it changes no mod. It is legal only where the state keeps the quality (`burn_refusal`)."""
        return True

    def burn_refusal(self, data: GameData, item: Item, keeps: BurnKeeps) -> str | None:
        """A quality burn is legal only where the compressed state keeps the quality, and not at the maximum quality (the use refuses 20% or more).

        Where the state does not keep the quality it could not see the burn run out, and burn and relock would be a free loop (ADR-0056).
        """
        if not keeps.quality:
            return f"the state does not keep the quality, so a {self.currency} burn could not run out at {MAX_CURRENCY_QUALITY}% (ADR-0056)"
        return super().burn_refusal(data, item, keeps)

    def reads(self, data: GameData) -> Reads:
        """The quality (it grows from it and 20% refuses) and nothing of the mods, which stay: the junk is kept as counts."""
        return Reads(junk=True, families=frozenset(), quality=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset(), draws=False, quality=True)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The item with its plain quality grown by the gain of its item level, capped at 20%.

        Raises `NotApplicableError` for a corrupted item, a class that holds no plain quality, a Whetstone on an armour or a Scrap on a weapon,
        and an item at 20% quality or more.
        """
        item_class = data.base_items[item.base_id].item_class
        if item_class not in PLAIN_QUALITY_ITEM_CLASSES:
            raise NotApplicableError(f"a {self.currency} works on a weapon or armour, and this item is a {item_class}")
        if item_class not in CLASSES[self.currency]:
            raise NotApplicableError(f"a {self.currency} does not work on a {item_class}")
        if item.corrupted:
            raise NotApplicableError(f"the item is corrupted, and a corrupted item takes no {self.currency}")
        start = item.quality.percent if isinstance(item.quality, PlainQuality) else 0
        if start >= MAX_CURRENCY_QUALITY:
            raise NotApplicableError(f"the item already holds {start}% quality, and a {self.currency} stops at {MAX_CURRENCY_QUALITY}%")
        reached: dict[int, Fraction] = {}
        for points, chance in gain_law(item.item_level):
            percent = min(MAX_CURRENCY_QUALITY, start + points)
            reached[percent] = reached.get(percent, Fraction(0)) + chance
        return Finite(data, item, tuple((chance, item.changed(data, quality=PlainQuality(percent))) for percent, chance in sorted(reached.items())))


@kind(
    "quality-currency",
    order=106,
    planner=False,
    why_not="a step of the socket finish (ADR-0049), bought before the orbs; the finish is attached to the goal states by ticket #231 (B6 S5)",
    applies_only_to="weapon and armour",
    reads_item_state_while_not_planner="quality",  # it reads and adds the quality
    burns=True,  # a quality burn (ticket #295)
)
def _quality_currency(data: GameData, item: Item):
    base = data.base_items.get(item.base_id)
    if base is None or item.corrupted:
        return
    for currency, classes in CLASSES.items():
        if base.item_class in classes:
            yield ApplyQualityCurrency(currency)
