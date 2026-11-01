"""The catalysts: the ten regular ones and the Sinistral and Dextral put quality on a ring, an amulet or a belt (ticket #157, ADR-0029).

`ApplyCatalyst(catalyst)` adds the quality of one catalyst of that type. The quality changes no odds (it is a finish
cost, ADR-0029), so the action only moves the item's `Quality`; the compressed state keeps it because the action
declares `Reads.quality` and `Adds.quality` (ADR-0027).

* **One quality type** (`catalyst.single_quality_type`): a catalyst of another type than the item's quality restarts it
  from 0%; one of the same type adds to it.
* **The gain** (`catalyst.gain_formula_and_rounding`, `catalyst.gain_depends_on_item_level`, approximate): with
  `f = max(1, min(30 * e^(-ilvl / 30) - 3/10, 20))`, one catalyst adds `floor(f)` points with probability `1 - frac(f)`
  and `floor(f) + 1` with probability `frac(f)`. The probabilities are exact rationals: `f` is computed with 60 decimal
  digits (`Decimal.exp` is correctly rounded, so every machine gets the same fractions) and taken as the exact
  rational of that decimal. The wiki's table (ilvl 75: +2 83.75%, +3 16.25%; ilvl 84: +1 47.57%, +2 52.43%) is this
  law to two decimals.
* **The cap** (`catalyst.quality_capped_at_20`, approximate): the quality is `min(20, quality + gain)`. A catalyst is
  refused on an item that already holds 20% of its type: nothing would change and nothing is consumed.
* **Refusals**, all `NotApplicableError`: an item that is not a ring, an amulet or a belt
  (`catalyst.thirteen_items_for_jewellery`), a corrupted item (`catalyst.refused_on_corrupted`; the Tainted Catalyst is
  not modelled), and 20% already.
* **The finish cost**: `expected_catalysts(item_level, target, start)` is the exact mean number of catalysts to reach
  `target` percent from `start` (9.53, 13.35, 14.42 and 20 to 20% at item level 75, 84, 86 and 95, the research's
  figures); `expected_catalysts_for(item, catalyst, target)` reads the start from the item.
* **Scaling** (`catalyst.magnitude_multiplier`, `catalyst.rounding_floor`, approximate): a modifier a catalyst
  boosts has its stored value multiplied by `(100 + quality) / 100` and rounded down, once per modifier:
  `scale_value(v, q) = v * (100 + q) // 100`. Which modifiers a regular catalyst boosts follows from the modifier's
  `implicit_tags` (`catalyst.match_by_implicit_tags`: the claim's value is the table); a Sinistral Catalyst boosts
  prefixes and a Dextral one suffixes (`catalyst.sinistral_dextral_by_side`, approximate: an implicit is neither).
  A target written in displayed values becomes a base roll with `base_roll_for(displayed, q)`.

The kind is not a planner kind: the planner adds the finish cost to a goal state (ADR-0029) and offers a catalyst
only when everything else of the target is met, which is ticket #158.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal, localcontext
from fractions import Fraction
from functools import cache

from crafting_system.data import GameData, Mod
from crafting_system.items import CATALYST_ITEM_CLASSES, MAX_QUALITY, CatalystType, Item, Quality
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .errors import NotApplicableError
from .finite import Finite

JEWELLERY_ONLY = get_rule("catalyst.thirteen_items_for_jewellery")
SINGLE_TYPE = get_rule("catalyst.single_quality_type")
GAIN_BY_ITEM_LEVEL = get_rule("catalyst.gain_depends_on_item_level")
CAPPED_AT_20 = get_rule("catalyst.quality_capped_at_20")
MAGNITUDE = get_rule("catalyst.magnitude_multiplier")
ROUNDING_FLOOR = get_rule("catalyst.rounding_floor")
MATCH_BY_TAGS = get_rule("catalyst.match_by_implicit_tags")
BY_SIDE = get_rule("catalyst.sinistral_dextral_by_side")
GAIN_FORMULA = get_rule("catalyst.gain_formula_and_rounding")
NO_ODDS_CHANGE = get_rule("catalyst.consumption_stopped_in_3_15")  # why the action moves the quality and nothing else (ADR-0029)
REFUSED_ON_CORRUPTED = get_rule("catalyst.refused_on_corrupted")
COST = get_rule("catalyst.cost")
CLAIMS = frozenset(
    rule.id
    for rule in (
        JEWELLERY_ONLY, SINGLE_TYPE, GAIN_BY_ITEM_LEVEL, CAPPED_AT_20, MAGNITUDE, ROUNDING_FLOOR, MATCH_BY_TAGS, BY_SIDE,
        GAIN_FORMULA, NO_ODDS_CHANGE, REFUSED_ON_CORRUPTED, COST,
    )
)
ONE = Fraction(1)
__all__ = [
    "ApplyCatalyst",
    "base_roll_for",
    "boosts",
    "expected_catalysts",
    "expected_catalysts_for",
    "gain_law",
    "scale_value",
    "scaled_values",
]
PRECISION = 60  # decimal digits of the gain formula: far below any probability this project tells apart
SIDE_OF = {CatalystType.SINISTRAL: "prefix", CatalystType.DEXTRAL: "suffix"}


# --- the gain ------------------------------------------------------------------------------------------


@cache
def gain_law(item_level: int) -> tuple[tuple[int, Fraction], ...]:
    """The points one catalyst adds on an item of `item_level`, as `(points, probability)` pairs that sum to 1, smallest first.

    `f = max(1, min(30 * e^(-item_level / 30) - 3/10, 20))`; the gain is `floor(f)` with probability `1 - frac(f)` and
    `floor(f) + 1` with probability `frac(f)`; a whole `f` gives its value with probability 1.
    """
    with localcontext() as context:
        context.prec = PRECISION
        raw = Decimal(30) * (Decimal(-item_level) / Decimal(30)).exp() - Decimal("0.3")
        f = max(Decimal(1), min(raw, Decimal(MAX_QUALITY)))
        floor = int(f.to_integral_value(rounding=ROUND_FLOOR))
        fraction = Fraction(f) - floor
    if fraction == 0:
        return ((floor, ONE),)
    return ((floor, ONE - fraction), (floor + 1, fraction))


def mean_gain(item_level: int) -> Fraction:
    """The mean points one catalyst adds at `item_level`: `f` itself."""
    return sum((points * chance for points, chance in gain_law(item_level)), Fraction(0))


@cache
def expected_catalysts(item_level: int, target: int = MAX_QUALITY, start: int = 0) -> Fraction:
    """The exact mean number of catalysts of one type that take the quality from `start` percent to at least `target`.

    The quality is `min(20, quality + gain)` after each catalyst, so it grows by at least one point per catalyst and
    the mean follows by walking down from `target`: `E[q] = 1 + sum p(g) * E[min(20, q + g)]`, `E[q] = 0` from `target`.
    """
    if not 0 <= start <= MAX_QUALITY or not 0 <= target <= MAX_QUALITY:
        raise ValueError(f"the quality runs from 0 to {MAX_QUALITY}, not {start} to {target}")
    law = gain_law(item_level)
    mean = [Fraction(0)] * (MAX_QUALITY + 1)
    for quality in range(target - 1, -1, -1):
        mean[quality] = 1 + sum(
            (chance * (mean[quality + points] if quality + points < target else 0) for points, chance in law), Fraction(0)
        )
    return mean[start] if start < target else Fraction(0)


def expected_catalysts_for(item: Item, catalyst: CatalystType, target: int = MAX_QUALITY) -> Fraction:
    """The mean number of `catalyst`s that take `item` to `target` percent: its quality counts only when it is of that type."""
    held = item.quality
    start = held.percent if held is not None and held.type is catalyst else 0
    return expected_catalysts(item.item_level, target, min(start, target))


# --- the scaling of a modifier -------------------------------------------------------------------------


def boosts(mod: Mod, catalyst: CatalystType) -> bool:
    """Whether a catalyst of this type scales `mod`: a regular one when a tag of its list is among the mod's `implicit_tags`,
    Sinistral when it is a prefix and Dextral when it is a suffix (an implicit is neither)."""
    side = SIDE_OF.get(catalyst)
    if side is not None:
        return mod.generation_type == side
    return any(tag in mod.implicit_tags for tag in MATCH_BY_TAGS.value[catalyst.value])


def scale_value(value: int, percent: int) -> int:
    """A stored value under `percent` quality of a matching catalyst: times `(100 + percent) / 100`, rounded down."""
    return value * (100 + percent) // 100


def scaled_values(mod: Mod, values: tuple[int, ...], quality: Quality | None) -> tuple[int, ...]:
    """The values of `mod` as the item shows them under `quality`: scaled when its catalyst boosts the mod, as they are otherwise."""
    if quality is None or quality.type is None or not boosts(mod, quality.type):  # a plain quality (type None) scales nothing
        return values
    return tuple(scale_value(value, quality.percent) for value in values)


def base_roll_for(displayed: int, percent: int) -> int:
    """The smallest stored value that shows at least `displayed` under `percent` quality: `ceil(100 * displayed / (100 + percent))`.

    Exact for stats displayed as their stored integer; a stat displayed in another unit (life regeneration per second, leech) rounds
    in the stored unit first (`catalyst.rounding_floor`), so a target on it is turned into stored units by its own caller.
    """
    return -(-100 * displayed // (100 + percent))


# --- the action ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ApplyCatalyst(Action):
    """One catalyst of the type `catalyst`."""

    catalyst: CatalystType

    def label(self, data: GameData | None = None) -> str:
        return COST.value[self.catalyst.value]

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {COST.value[self.catalyst.value]: 1}

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        # exactly the claims this file cites: the helpers it imports (`finite`) hold none of their own
        return CLAIMS

    def reads(self, data: GameData) -> Reads:
        # The result depends on the quality (the same type adds, another restarts, 20% is refused) and on nothing of the mods,
        # which stay: the junk is kept as counts, no family is told apart.
        return Reads(junk=True, families=frozenset(), quality=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset(), draws=False, quality=True)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The outcomes of using the catalyst on `item`: its quality of this type grown by the gain, capped at 20%.

        Raises `NotApplicableError` for an item that is no ring, amulet or belt, for a corrupted item and for one that
        already holds 20% of this type.
        """
        item_class = data.base_items[item.base_id].item_class
        if item_class not in CATALYST_ITEM_CLASSES:
            raise NotApplicableError(f"a catalyst works on a ring, an amulet or a belt, and this item is a {item_class}")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no regular catalyst")
        held = item.quality
        start = held.percent if held is not None and held.type is self.catalyst else 0
        if start >= MAX_QUALITY:
            raise NotApplicableError(f"the item already holds {MAX_QUALITY}% {self.catalyst.value} quality")
        reached: dict[int, Fraction] = {}
        for points, chance in gain_law(item.item_level):
            percent = min(MAX_QUALITY, start + points)
            reached[percent] = reached.get(percent, Fraction(0)) + chance
        return Finite(
            data, item, tuple((chance, item.changed(data, quality=Quality(self.catalyst, percent))) for percent, chance in sorted(reached.items()))
        )


@kind(
    "catalyst",
    order=90,
    planner=False,
    why_not="catalysts are a finish cost added to a goal state, offered when everything else of the target is met: ticket #158",
    reads_item_state_while_not_planner="any",  # it reads and adds the quality
)
def _catalysts(data: GameData, item: Item):
    base = data.base_items.get(item.base_id)
    if base is not None and base.item_class in CATALYST_ITEM_CLASSES and not item.corrupted:
        for catalyst in CatalystType:
            yield ApplyCatalyst(catalyst)
