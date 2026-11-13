"""Where a price came from, as data (#616, OR-7, OR-8, OR-23).

A price entry carries its provenance, not a note: the **source**, the **date and league** of the reading, the
**depth** and the **item** the price was taken for. The rule that reads it (`price_marks.py`) turns a price into
a plain fact or an approximate input; this module only holds the record, writes it to JSON and reads it back.

* `kind`: where the number is from (`KINDS`): the poe.ninja exchange overview of the league, the poe.ninja daily
  rows of the league (history), the poe.ninja rows of an earlier league (previous league, Standard), poe.watch,
  the trade site's instant-buyout listings, a hand price, a default, or the vendor upgrade recipe (a lower essence tier priced as
  one third of the next tier up, `essence_recipe.py`, #885: its `league` and `date` are those of the price it rests on), or an
  estimate (a number set by hand for an item no market lists, such as The Black Mórrígan, which poe.ninja has no line for: OR-23's
  best estimate, always marked; its `note` says what it rests on; `league` and `date` say for which economy and day it was set).
* `league`, `date`: the league and the UTC day the reading is of.
* `depth` and `depth_unit`: how much stood behind the number. For an exchange line it is the units traded on the day
  (poe.ninja's `volumePrimaryValue`, in Chaos, divided by the price), unit `units`. For a trade price it is the units
  held by the listings the mean is made of (a stack counts its size, any other item counts one), unit `units`;
  `listings` is how many listings that is. For a stash line it is poe.ninja's observation count, unit
  `observations`. `None` is "not recorded".
* `item`: `exact` when the price is of the item the plan buys, `wider` when it was read for a wider item (a stand-in).
  A wider item says which in `for_item`, and, when the exact item has listings of its own, how many (`exact_listings`)
  and what they ask (`exact_price`, in Chaos), so a reader sees both.
* `other`: the reading that was not taken, when two were compared (the same day's trade listings beside a thin
  exchange line, `{"kind", "chaos", "depth"}`).
* `market`: a trade reading of a thin market (#355: fewer than 10 offers in the book, or fewer than 3 priced), which OR-8 (#718)
  never shows as a plain price: `thin` (the mean of what there is) or `old` (the league's last deep price, `date` the day it was
  read); `book` is the offers the thin book held. None for a market with enough offers and for every other kind.
* `trade_unread`: why the trade site's offers were not read beside this price when the fetch meant to (the site blocked the
  run, or the request budget was spent); a plan that buys more than the price's depth says so.

An entry with no provenance block (a file written before #616, a hand-written test file) is read from its `source`
and `detail` as far as they go (`derive`), and is an approximate input: nothing was recorded to show it is of today's league,
of the exact item and deep enough (`price_marks`).
Nothing here reads the clock.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

EXCHANGE = "ninja-exchange"
HISTORY = "ninja-history"
STASH = "ninja-stash"
PREVIOUS_LEAGUE = "ninja-previous-league"
STANDARD = "ninja-standard"
WATCH = "poe-watch"
TRADE = "trade"
OVERRIDE = "override"
DEFAULT = "default"
RECIPE = "upgrade-recipe"
ESTIMATE = "estimate"
KINDS = (EXCHANGE, HISTORY, STASH, PREVIOUS_LEAGUE, STANDARD, WATCH, TRADE, OVERRIDE, DEFAULT, RECIPE, ESTIMATE)

UNITS = "units"
OBSERVATIONS = "observations"
DEPTH_UNITS = (UNITS, OBSERVATIONS)

EXACT = "exact"
WIDER = "wider"
ITEMS = (EXACT, WIDER)

THIN_MARKET = "thin"
OLD_PRICE = "old"
MARKETS = (THIN_MARKET, OLD_PRICE)

SOURCE_WORDS = {
    EXCHANGE: "poe.ninja exchange",
    HISTORY: "poe.ninja daily rows",
    STASH: "poe.ninja stash overview",
    PREVIOUS_LEAGUE: "poe.ninja, previous league",
    STANDARD: "poe.ninja, Standard",
    WATCH: "poe.watch",
    TRADE: "trade site, instant buyout",
    OVERRIDE: "hand price",
    DEFAULT: "default price",
    RECIPE: "vendor upgrade recipe",
    ESTIMATE: "estimate, no market lists it",
}  # in a player's words, for the page and the report

# the source strings of a price entry (`PriceEntry.source`) and the kind each one means
KIND_OF_SOURCE = {
    "poe.ninja": EXCHANGE,
    "poe.ninja-history": HISTORY,
    "poe.ninja-previous-league": PREVIOUS_LEAGUE,
    "poe.ninja-standard": STANDARD,
    "poe.watch": WATCH,
    "poe.watch-history": WATCH,
    "trade-api": TRADE,
    "override": OVERRIDE,
    "hand": OVERRIDE,
    "default": DEFAULT,
    "upgrade-recipe": RECIPE,
    "estimate": ESTIMATE,
}


@dataclass(frozen=True)
class Provenance:
    kind: str
    league: str
    date: str  # ISO UTC date of the reading
    depth: float | None = None
    depth_unit: str = UNITS
    listings: int | None = None  # a trade price: the listings the mean is made of
    item: str = EXACT
    for_item: str | None = None  # what a stand-in was read for, in words
    exact_listings: int | None = None  # a stand-in: the listings the exact item has
    exact_price: float | None = None  # a stand-in: what those listings ask, in Chaos (their mean)
    other: Mapping[str, Any] | None = None  # the reading not taken: {"kind", "chaos", "depth"}
    trade_unread: str | None = None  # why the trade site's offers were not read beside this price when a fetch meant to ("blocked", "request budget spent")
    market: str | None = None  # a thin market's reading (OR-8, #718): `thin` (its mean) or `old` (the league's last deep price)
    book: int | None = None  # a thin market: the offers in its book
    recorded: bool = True  # False for a provenance derived from a source string alone (`derive`)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"provenance kind must be one of {', '.join(KINDS)}, got {self.kind!r}")
        if self.item not in ITEMS:
            raise ValueError(f"provenance item must be one of {', '.join(ITEMS)}, got {self.item!r}")
        if self.market not in (None, *MARKETS):
            raise ValueError(f"provenance market must be one of {', '.join(MARKETS)}, got {self.market!r}")
        if self.depth_unit not in DEPTH_UNITS:
            raise ValueError(f"provenance depth_unit must be one of {', '.join(DEPTH_UNITS)}, got {self.depth_unit!r}")

    @property
    def words(self) -> str:
        """The source in a player's words, with its league and day: "poe.ninja exchange, Allflame, 2026-11-07"."""
        return f"{SOURCE_WORDS[self.kind]}, {self.league}, {self.date}"


def _number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value == value and abs(value) != float("inf")


def to_json(provenance: Provenance) -> dict[str, Any]:
    """The JSON object of a recorded provenance; fields at their default are left out."""
    out: dict[str, Any] = {"kind": provenance.kind, "league": provenance.league, "date": provenance.date}
    if provenance.depth is not None:
        out["depth"] = provenance.depth
        out["depth_unit"] = provenance.depth_unit
    if provenance.listings is not None:
        out["listings"] = provenance.listings
    if provenance.item != EXACT:
        out["item"] = provenance.item
    for key in ("for_item", "exact_listings", "exact_price", "other", "trade_unread", "market", "book"):
        value = getattr(provenance, key)
        if value is not None:
            out[key] = dict(value) if isinstance(value, Mapping) else value
    return out


def from_json(raw: object, where: str) -> Provenance:
    """A provenance from its JSON object; a bad shape is a `ValueError` that names `where`."""
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: provenance must be an object")
    unknown = sorted(set(raw) - {"kind", "league", "date", "depth", "depth_unit", "listings", "item", "for_item", "exact_listings", "exact_price", "other", "trade_unread", "market", "book"})
    if unknown:
        raise ValueError(f"{where}: provenance has an unknown key {unknown[0]!r}")
    for key in ("kind", "league", "date"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise ValueError(f"{where}: provenance {key} must be a non-empty string")
    for key in ("depth", "exact_price"):
        if key in raw and not (_number(raw[key]) and raw[key] >= 0):
            raise ValueError(f"{where}: provenance {key} must be a number, zero or more")
    for key in ("listings", "exact_listings", "book"):
        if key in raw and not (isinstance(raw[key], int) and not isinstance(raw[key], bool) and raw[key] >= 0):
            raise ValueError(f"{where}: provenance {key} must be a whole number, zero or more")
    if "for_item" in raw and not isinstance(raw["for_item"], str):
        raise ValueError(f"{where}: provenance for_item must be a string")
    if "trade_unread" in raw and not isinstance(raw["trade_unread"], str):
        raise ValueError(f"{where}: provenance trade_unread must be a string")
    if "market" in raw and not isinstance(raw["market"], str):
        raise ValueError(f"{where}: provenance market must be a string")
    if "other" in raw and not isinstance(raw["other"], dict):
        raise ValueError(f"{where}: provenance other must be an object")
    try:
        return Provenance(
            raw["kind"], raw["league"], raw["date"],
            None if raw.get("depth") is None else float(raw["depth"]),
            raw.get("depth_unit", UNITS), raw.get("listings"), raw.get("item", EXACT), raw.get("for_item"),
            raw.get("exact_listings"), None if raw.get("exact_price") is None else float(raw["exact_price"]), raw.get("other"), raw.get("trade_unread"),
            raw.get("market"), raw.get("book"),
        )  # fmt: skip
    except ValueError as error:
        raise ValueError(f"{where}: {error}") from None


def derive(source: str, detail: Mapping[str, Any] | None, league: str, day: str) -> Provenance | None:
    """What an entry with no provenance block says of itself: its `source` string and the league and date in its `detail`.

    `league` and `day` are the price file's, used when the entry's `detail` names none. None when the source is not one the
    code knows (a test's made-up source). The result is `recorded=False`: no depth was kept, so the rule does not judge it on depth.
    """
    kind = KIND_OF_SOURCE.get(source)
    if kind is None:
        return None
    detail = detail or {}
    where = detail.get("league") if isinstance(detail.get("league"), str) else league
    when = detail.get("date") if isinstance(detail.get("date"), str) else day
    return Provenance(kind, where, when, recorded=False)
