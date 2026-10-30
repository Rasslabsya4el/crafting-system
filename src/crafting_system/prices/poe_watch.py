"""poe.watch for the current league: `/exchange/ratios`, then `/get`, then `/history` (#40).

The stage runs after poe.ninja's history and prices only what is still a gap, in three steps:

- `/exchange/ratios` answers `{"items": [{id, name, price: {chaos, lowConfidence, window}, ...}]}`
  for currency-like items, matched by exact name. It is fetched once, and only when some gap is
  neither a base nor a stash beast. An item may have no `price` block at all.
- `/get?category=C` answers a list of items with a daily `mean`: `bases` for a base gap (matched by
  name, item level and influence set), `beast` for a stash beast, `currency`, `essence` and `beast`
  in turn for the rest. Each category is fetched at most once, and `bases` (about 12 MB) only when
  a base gap is left.
- `/history?id=N` answers dated rows of one item. It is asked for the gaps still unpriced whose
  poe.watch id was seen in the steps above, even on a low-confidence or price-less row.

A price counts when poe.watch does not flag it `lowConfidence` (the owner's rule: a minimum
sample). A request that fails or answers in an unexpected shape gives nothing and the gap stays.
Nothing reads the clock: `context.today` dates a current snapshot and ends the history window.
"""

import statistics
import urllib.parse
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any

from .fallbacks import HISTORY_DAYS, Context, Gap, StageResult, stamped_entry
from .http_json import GetJson, SourceError
from .ninja_history import window_ending
from .price_file import PriceEntry, is_price

BASE_URL = "https://api.poe.watch"
SOURCE = "poe.watch"
HISTORY_SOURCE = "poe.watch-history"
GAME = "poe1"
GET_CATEGORIES = ("currency", "essence", "beast")  # tried in this order for a gap that is not a base or a beast


def chaos_text(chaos: float) -> str:
    """A chaos price for a warning: two decimals at most, no trailing zeros (2.27, 135.1, 500)."""
    return f"{chaos:.2f}".rstrip("0").rstrip(".")


def _categories(gap: Gap) -> tuple[str, ...]:
    """The `/get` categories a gap could be in; empty when poe.watch cannot be asked about it."""
    if gap.base is not None:
        return ("bases",)
    if gap.stash_kind == "Beast":
        return ("beast",)
    if gap.stash_kind == "BaseType":  # a base without its key has no item level to match
        return ()
    return GET_CATEGORIES


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _influences(text: object) -> frozenset[str] | None:
    """The influence set of a poe.watch row ("hunter,redeemer", "" for none); None for a changed shape."""
    if not isinstance(text, str):
        return None
    return frozenset(part.strip().lower() for part in text.split(",") if part.strip())


def _row_matches(gap: Gap, row: dict[str, Any]) -> bool:
    base = gap.base
    if base is None:
        return row.get("name") == gap.name
    return (
        row.get("name") == base.name
        and row.get("itemLevel") == base.item_level
        and _is_int(row.get("itemLevel"))
        and _influences(row.get("influences")) == frozenset(i.lower() for i in base.influences)
    )


def _day_of(text: object) -> date | None:
    """The UTC date of an ISO timestamp like 2026-10-29T23:32:56.315097Z; None when it is not one."""
    if not isinstance(text, str):
        return None
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    return stamp.astimezone(UTC).date() if stamp.tzinfo else stamp.date()


class _Run:
    """One run of the stage: the gaps still open, what was priced and the poe.watch ids seen per name."""

    def __init__(self, get_json: GetJson, context: Context, gaps: Sequence[Gap]):
        self.get_json = get_json
        self.context = context
        self.open = list(gaps)
        self.prices: dict[str, PriceEntry] = {}
        self.warnings: list[str] = []
        self.ids: dict[str, list[int]] = {}
        self.history: dict[int, list[tuple[date, float]]] = {}

    def run(self) -> StageResult:
        if any(_categories(gap) == GET_CATEGORIES for gap in self.open):
            self._ratios()
        self._get()
        self._history()
        return StageResult(self.prices, self.warnings)

    def _fetch(self, route: str, **params: object) -> Any:
        """The parsed answer of `route`, or None when the request failed."""
        query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        try:
            return self.get_json(f"{BASE_URL}/{route}?{query}")
        except SourceError:
            return None

    def _note_id(self, name: str, item_id: object) -> None:
        if _is_int(item_id) and item_id not in self.ids.setdefault(name, []):
            self.ids[name].append(item_id)

    def _price(self, gap: Gap, chaos: float, source: str, day: date, note: str, how: str) -> None:
        self.prices[gap.name] = stamped_entry(chaos, source, self.context.league, day, note)
        self.warnings.append(
            f"{gap.name}: no usable poe.ninja price; used poe.watch {chaos_text(chaos)} Chaos "
            f"({how}, league {self.context.league}, {day.isoformat()})"
        )
        self.open = [other for other in self.open if other.name != gap.name]

    def _ratios(self) -> None:
        wanted = {gap.name: gap for gap in self.open if _categories(gap) == GET_CATEGORIES}
        data = self._fetch("exchange/ratios", league=self.context.league, game=GAME)
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return
        for item in items:
            name = item.get("name") if isinstance(item, dict) else None
            gap = wanted.get(name) if isinstance(name, str) else None
            if gap is None or gap.name in self.prices:
                continue
            self._note_id(gap.name, item.get("id"))
            price = item.get("price")
            if not isinstance(price, dict) or price.get("lowConfidence") is not False:
                continue
            if not is_price(price.get("chaos")):
                continue
            window = price.get("window")
            hours = window.get("hours") if isinstance(window, dict) else None
            note = "poe.watch /exchange/ratios"
            if _is_int(hours) and hours > 0:
                note += f", {hours}-hour window"
            self._price(gap, float(price["chaos"]), SOURCE, self.context.today, note, "exchange ratio")

    def _get(self) -> None:
        for category in ("bases", *GET_CATEGORIES):
            asked = [gap for gap in self.open if category in _categories(gap)]
            if not asked:
                continue
            data = self._fetch("get", league=self.context.league, category=category)
            rows = [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []
            for gap in asked:
                matching = [row for row in rows if _row_matches(gap, row)]
                for row in matching:
                    self._note_id(gap.name, row.get("id"))
                means = [
                    float(row["mean"])
                    for row in matching
                    if row.get("lowConfidence") is False and is_price(row.get("mean"))
                ]
                if means:
                    note = f"poe.watch /get category {category}, mean"
                    self._price(
                        gap, statistics.median(means), SOURCE, self.context.today, note, f"/get category {category}"
                    )

    def _history_rows(self, item_id: int) -> list[tuple[date, float]]:
        """Usable (day, mean) rows of one poe.watch item inside the window; asked once per id."""
        if item_id not in self.history:
            first, last = window_ending(self.context.today)
            data = self._fetch("history", league=self.context.league, id=item_id)
            rows = []
            for row in data if isinstance(data, list) else []:
                if not isinstance(row, dict) or row.get("lowConfidence") is not False:
                    continue
                day = _day_of(row.get("date"))
                if day is not None and first <= day <= last and is_price(row.get("mean")):
                    rows.append((day, float(row["mean"])))
            self.history[item_id] = rows
        return self.history[item_id]

    def _history(self) -> None:
        last = window_ending(self.context.today)[1]
        for gap in list(self.open):
            for item_id in self.ids.get(gap.name, ()):
                rows = self._history_rows(item_id)
                if not rows:
                    continue
                day = max(day for day, _ in rows)
                note = f"median of {len(rows)} poe.watch history rows in the {HISTORY_DAYS} days ending {last.isoformat()}"
                how = f"history, median of {len(rows)} rows"
                self._price(gap, statistics.median(mean for _, mean in rows), HISTORY_SOURCE, day, note, how)
                break


def poe_watch_stage(get_json: GetJson, context: Context, gaps: Sequence[Gap]) -> StageResult:
    """Price the gaps from poe.watch for `context.league`; see the module docstring."""
    return _Run(get_json, context, gaps).run()
