"""The shapes of the start options: what a plan can start from, what it was compared with, and what was refused (ADR-0059, ticket #330).

A **start candidate** is one priced item a plan can start from, with the **source** it comes from. Today there are two
sources: the target's own start item (`plain`) and the Magic item a vendor recipe makes from a Normal base and cheap goods
(`vendor recipe`); a third, the target's base bought at an item level of each equal-pool group (`bought base`, #351), is listed
but not yet planned (#359). The list is deliberately a list of priced candidates with a source and not a recipe-only code path:
research #337 asks whether the planner should choose what to buy at any state (the start item, the donors, mid-route), and
a bought item is one more source whose candidates are priced by a trade query. Such a source needs a function that returns a
`StartList` (`_start_options.StartSource`) and one entry in the list of sources; the choice (`_starts.plan_with_starts`)
and the report (`_start_report`) read only the fields below and never ask which source a candidate came from.

This module holds the records only; it imports nothing of the planner, so `Plan` can carry a `StartChoice`.
"""

from dataclasses import dataclass

from crafting_system.items import Item
from crafting_system.prices.price_source import SourcedPrice

SOURCE_PLAIN = "plain"
SOURCE_VENDOR_RECIPE = "vendor recipe"
SOURCE_BOUGHT_BASE = "bought base"

# why a recipe start is refused (`RefusedStart.reason`)
NO_TARGET_MOD = "no target mod"
CAP_BELOW_ASKED = "cap does not reach the asked tier"
ITEM_LEVEL_TOO_LOW = "item level below the mod's required level"
ROLL_NOT_GUARANTEED = "roll not guaranteed"
MOD_CANNOT_SPAWN = "mod cannot spawn on the base"
NO_PRICE = "no price"
DOMINATED = "dominated"
INVALID_ITEM = "the game data refuses the item"
NOT_A_PLAIN_BASE = "the start item is not a plain base"  # a bought-base start (#351): the start item carries what a base row does not price

Reading = tuple[tuple[str, str], ...]  # one (rule axis, value) per axis, sorted by axis; () when a run reads no axis
Goods = tuple[tuple[str, int, float, str], ...]  # (price name, count, Chaos for all of them, where the price came from)


@dataclass(frozen=True)
class NinjaRow:
    """The poe.ninja row of a bought base (ADR-0061): its name, its price and the observations it rests on (None when not recorded)."""

    name: str
    chaos: float
    observations: float | None


@dataclass(frozen=True)
class BoughtBase:
    """What a bought-base start option is (ticket #351, ADR-0061 decision 1): the cheapest priced row of one equal-pool group of levels.

    `group` is the item levels (lowest, highest) with one pool, so one plan; `level` is the row chosen, the cheapest of the group's
    priced levels (`priced`, every (level, Chaos) of the group with a price, lowest level first). `influences` are the row's influences in
    game order. `row_name` and `row_chaos` are the base's price name and price under the profile's price source. `ninja` is the base's
    poe.ninja row when present with at least 5 observations (or no recorded count); `trade_chaos` the trade price when the file has one.
    `input_marks` are the reasons the price is an approximate input (`prices.price_marks`, one unit bought); the OR-8 thin or old mark of a
    trade price is on the candidate (`StartCandidate.price_mark`) and in `StartCandidate.sourced`. `rarity_orb` is the orb that makes the
    Normal base the start item's rarity (Orb of Transmutation for Magic, Orb of Alchemy for Rare), priced in the candidate's `goods`.
    """

    level: int
    group: tuple[int, int]
    influences: tuple[str, ...]
    row_name: str
    row_chaos: float
    ninja: NinjaRow | None = None
    trade_chaos: float | None = None
    input_marks: tuple[str, ...] = ()
    rarity_orb: str | None = None
    priced: tuple[tuple[int, float], ...] = ()


@dataclass(frozen=True)
class StartCandidate:
    """One priced start item.

    `key` names the candidate in a run (`plain`, `vendor:weapon_fire:8`). `price` is the whole Chaos price of the item;
    for a recipe it is the sum of `goods`, for the plain start item the price of the target's bought item (0 when the target gives it),
    and None when a bought item has no price: an unpriced start option is reported as unpriced, never as an infinite price (#505). `price_name` and
    `price_source` are what the report prints on the start line. `claims` are the ids of the claims behind a recipe-made item
    that are marked `approximate` (ADR-0028). `sourced` is the price of a bought item under the profile's price source (ticket #357):
    the trade and poe.ninja prices side by side, the fallback mark and the gap flag; the report prints it under the option. A candidate that exists only at some values of a rule axis names the axis in
    `axis` and the values in `reading_values` (ADR-0059: the elemental cap); `axis` None means it exists at every reading.
    """

    key: str
    source: str
    label: str
    item: Item
    price: float | None
    price_name: str | None
    price_source: str
    goods: Goods = ()
    recipe: str | None = None
    steps: int = 0
    claims: tuple[str, ...] = ()
    axis: str | None = None
    reading_values: tuple[str, ...] = ()
    sourced: SourcedPrice | None = None
    given: bool = False  # the target gives this start item (OR-6): its cost is not counted, the price is 0 by definition
    price_mark: str | None = None  # the plain start item priced from a thin market (OR-8): the mark that goes with its price
    bought: BoughtBase | None = None  # a bought-base start option (#351): the row, its group of levels and the marks of its price
    warnings: tuple[str, ...] = ()  # words a later check adds without cutting the option (the realism rails of #353, OR-12)

    def exists_in(self, reading: Reading) -> bool:
        """Whether this candidate can be had at `reading` of the rule axes (one without an axis exists at every reading)."""
        if self.axis is None:
            return True
        return dict(reading).get(self.axis) in self.reading_values


@dataclass(frozen=True)
class RefusedStart:
    """A recipe start that was considered and not offered, with the reason in a short code and in words.

    `recipe` is the recipe id; `steps` the step count of a dominated start (0 otherwise); `axis` and `reading_values`
    say, as on a candidate, at which readings of a rule axis the refusal holds (no axis: at every reading).
    """

    recipe: str
    name: str
    reason: str
    detail: str
    steps: int = 0
    axis: str | None = None
    reading_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConsideredStart:
    """What became of one candidate: planned (with its mean cost), failed (with the error) or not planned (with why).

    `mean_remaining` is the solver's expected cost to pay after the start item is in hand and `total` is the start price
    plus that, the number the choice compares. Both are None for a candidate that was not planned or failed.
    """

    candidate: StartCandidate
    outcome: str  # "chosen" | "planned" | "failed" | "not planned"
    mean_remaining: float | None
    total: float | None
    approximate: bool
    note: str = ""


@dataclass(frozen=True)
class ReadingChoice:
    """The cheapest start at one reading of the rule axes, with its total (infinite when no start reaches the goal)."""

    reading: Reading
    key: str | None
    total: float


@dataclass(frozen=True)
class StartChoice:
    """The answer to "what do I start from": the start chosen at the plan reading, everything compared, everything refused.

    `chosen` is the candidate of the plan (the cheapest total at the plan reading, the first value of every rule axis).
    `considered` holds every candidate in the order they were tried, `refused` the recipe starts that were not offered,
    `by_reading` the cheapest start at each reading of the rule axes (one entry when there is no axis) and `claims` the ids
    of the `approximate` claims the answer rests on. `total_range` is the least and the greatest of the totals over the readings.
    """

    chosen: StartCandidate
    considered: tuple[ConsideredStart, ...]
    refused: tuple[RefusedStart, ...]
    axes: tuple[tuple[str, tuple[str, ...]], ...]
    by_reading: tuple[ReadingChoice, ...]
    claims: tuple[str, ...]

    @property
    def total(self) -> float:
        """The total of the chosen start at the plan reading."""
        return self.by_reading[0].total

    @property
    def total_range(self) -> tuple[float, float]:
        """The least and the greatest cheapest total over the readings of the rule axes."""
        totals = [entry.total for entry in self.by_reading]
        return (min(totals), max(totals))

    @property
    def reading_matters(self) -> bool:
        """Whether the cheapest total differs between readings (the rule axis changes the answer)."""
        low, high = self.total_range
        return high - low > 1e-9 * max(1.0, abs(high))
