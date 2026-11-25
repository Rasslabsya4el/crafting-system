"""When a price is a plain fact and when it is an approximate input (#616, OR-12, OR-23).

A price is a **plain fact** only when it is today's league, of the exact item, and deep enough for what the plan buys of it:
its depth in units is at least the units the plan expects to use. Every other price is an **approximate input**, and
`price_marks` says why, in the words the page and the report print:

* "price on N units" (the depth is below the plan's expected uses, or no depth was recorded);
* "previous league's price" (a price of an earlier league or of Standard);
* "price of a wider item; the exact item has K listings at P" (a stand-in);
* "price of league X", "price of an earlier day", or a price of a day more than a week after the file's (a snapshot of an earlier
  day that keeps a later reading as its stand-in, #838);
* "few offers: the mean of the cheapest units of the N offers there are" and "old price, read on <date>, the market has few
  offers now" (a thin trade book, OR-8 as amended by #718: its own mean, or the league's last deep price in its place);
* "priced from the vendor recipe: one third of <the next tier up>" (a lower essence tier, `essence_recipe.py`, #885), and beside it
  every reason against the market price its chain rests on (the anchor: its league, its day, its depth), each said with the
  anchor's name. One unit of a tier `k` tiers below the anchor is a `3**k`-th of an anchor unit, so the anchor's depth is
  compared with the plan's uses divided by that;
* "a price set by hand: ..." (OR-44) (a number the tests' price file sets by hand where the market is plainly not what a player pays,
  #483); one set from a wider item's search says so with the stand-in's words, and its reading day is not judged against the file's;
  one set for the item the plan buys from the listings of a wider search (the provenance's `for_item` names it, its `item` is exact)
  says "a price set by hand from the listings of a wider search, <that search>; no search of this item alone was read" (#1472: R10's and R11's starts, planned at item
  level 85, priced from the search for 84 or more); one with neither says "a price set by hand";
* "an estimate: no market lists this item" (a number set by hand where neither poe.ninja nor the trade history has the item, #885;
  unlike a hand override it is not the user's own number, so it is never a plain fact);
* "the trade offers beside it were not read: <why>" (beside any other reason, a previous league's price included, when the recorded price carries `trade_unread`; a deep-enough plain fact needs none).

There is no fixed cut that drops a route (OR-12): a price on few units is kept, marked, and the plan is solved with it.
A price with no recorded provenance (`recorded` False: a file written before #616, a test's price) is an approximate input too,
never a plain fact: nothing shows it is of today's league, of the exact item and deep enough. Its reason is "where this price comes
from is not recorded"; the source it names is read from its source string alone. A hand price and a default are the user's and
the model's own numbers and need no record.
Pure: no I/O, no clock; the plan's expected uses are the caller's number.
"""

from dataclasses import dataclass
from datetime import date

from .price_file import MAX_AGE_DAYS, PriceEntry, PriceFile
from .provenance import (
    DEFAULT,
    ESTIMATE,
    HAND_SET,
    EXCHANGE,
    HISTORY,
    OBSERVATION_CAP,
    OBSERVATIONS,
    OLD_PRICE,
    OVERRIDE,
    PREVIOUS_LEAGUE,
    RECIPE,
    STANDARD,
    STASH,
    THIN_MARKET,
    TRADE,
    WATCH,
    WIDER,
    Provenance,
    derive,
)

MARKET_KINDS = (EXCHANGE, HISTORY, STASH, WATCH, TRADE)  # the kinds that rest on a count of trades or listings
EARLIER_LEAGUE = (PREVIOUS_LEAGUE, STANDARD)

DEPTH = "depth"
EARLIER = "earlier-league"
STAND_IN = "wider-item"
OTHER_LEAGUE = "other-league"
OLD = "old"
LATER = "later-day"
NO_DEPTH = "no-depth"
NOT_RECORDED = "not-recorded"
NOT_RECORDED_WORDS = "where this price comes from is not recorded"
TRADE_UNREAD = "trade-unread"
THIN = "thin-market"
OLD_THIN = "old-price"
FROM_RECIPE = "upgrade-recipe"
ESTIMATED = "estimate"
HAND_SET_MARK = "hand-set"
# OR-44, #1472: a number set by hand for the item the plan buys, from the listings a search of a wider item read (no search of the item
# alone); the provenance's `for_item` names that search and where its cheapest listings were (crafter, #1472: the player sees the
# item level he buys beside the one searched, and must be told they are two searches)
HAND_SET_EXACT_WORDS = "a price set by hand from the listings of a wider search, {search}; no search of this item alone was read"


@dataclass(frozen=True)
class PriceMark:
    """One reason a price is an approximate input: a `code` (one of the constants above) and the words that say it."""

    code: str
    reason: str


def provenance_of(entry: PriceEntry, price_file: PriceFile) -> Provenance | None:
    """The entry's provenance as recorded, else what its source and detail say of it (`recorded` False), else None (an unknown source)."""
    if entry.provenance is not None:
        return entry.provenance
    return derive(entry.source, entry.detail, price_file.league, price_file.fetched_at.date().isoformat())


def units_text(depth: float) -> str:
    """A depth in words: whole numbers with thousands separators from 10 up, one decimal below ("3.3 units", "1,546 units")."""
    if depth >= 10:
        return f"{depth:,.0f}"
    text = f"{depth:.1f}"
    return text[:-2] if text.endswith(".0") else text


def chaos_text(chaos: float) -> str:
    return f"{chaos:,.0f}" if chaos >= 100 else f"{chaos:.3g}"


def price_marks(entry: PriceEntry, price_file: PriceFile, uses: float | None) -> tuple[PriceMark, ...]:
    """The reasons `entry` is an approximate input for a plan that expects to use `uses` units of it; empty for a plain fact.

    `uses` is None when the plan's uses were not solved: at least one unit is then taken as bought, which is all a plan that
    takes the action can be said to buy.
    """
    p = provenance_of(entry, price_file)
    if p is not None and p.kind in (OVERRIDE, DEFAULT):
        return ()  # a hand price and a default are the user's and the model's own numbers; the page names their source
    found: list[PriceMark] = []
    if p is None:
        return (PriceMark(NOT_RECORDED, NOT_RECORDED_WORDS),)
    if p.kind == RECIPE:
        return _recipe_marks(entry, price_file, uses)
    if p.kind == ESTIMATE:
        return (PriceMark(ESTIMATED, "an estimate: no market lists this item"),)
    if p.kind == HAND_SET:  # OR-44: set by hand and marked; a number set from a wider item's search names that item and the exact one's listings
        if p.item == WIDER:
            hand = PriceMark(HAND_SET_MARK, "a price set by hand: the exact item's own listings (few or none) are not what a player pays")
            return (hand, PriceMark(STAND_IN, _stand_in_words(p)))
        if p.for_item:  # #1472: the number of the item planned, set from the listings of a wider search that was read (`for_item` names it)
            return (PriceMark(HAND_SET_MARK, HAND_SET_EXACT_WORDS.format(search=p.for_item)),)
        return (PriceMark(HAND_SET_MARK, "a price set by hand"),)
    if p.kind == PREVIOUS_LEAGUE:
        found.append(PriceMark(EARLIER, f"previous league's price ({p.league}, {p.date})"))
    elif p.kind == STANDARD:
        found.append(PriceMark(EARLIER, f"Standard's price, a different economy ({p.date})"))
    elif p.league != price_file.league:
        found.append(PriceMark(OTHER_LEAGUE, f"price of league {p.league} ({p.date})"))
    elif p.recorded and p.market != OLD_PRICE and _days_before(p.date, price_file) > MAX_AGE_DAYS:  # an old price says its day in its own mark
        found.append(PriceMark(OLD, f"price of {p.date}, {_days_before(p.date, price_file)} days before the file"))
    elif p.recorded and p.market != OLD_PRICE and -_days_before(p.date, price_file) > MAX_AGE_DAYS:  # a snapshot of an earlier day keeping a later reading (#838)
        found.append(PriceMark(LATER, f"price of {p.date}, {-_days_before(p.date, price_file)} days after the file"))
    if p.recorded and p.market == THIN_MARKET:
        found.append(PriceMark(THIN, f"few offers: the mean of the cheapest units of the {p.book} {'offer' if p.book == 1 else 'offers'} there are"))
    elif p.recorded and p.market == OLD_PRICE:
        found.append(PriceMark(OLD_THIN, f"old price, read on {p.date}, the market has few offers now"))
    if p.recorded and p.item == WIDER:
        found.append(PriceMark(STAND_IN, _stand_in_words(p)))
    if p.recorded and p.kind in MARKET_KINDS and p.kind not in EARLIER_LEAGUE and p.market != OLD_PRICE:  # an old price's depth was not kept; its mark says what it is
        if p.depth is None:
            found.append(PriceMark(NO_DEPTH, "price with no recorded depth"))
        elif p.depth < (1.0 if uses is None else uses):
            noun = "observations" if p.depth_unit == OBSERVATIONS else "units"
            if p.depth_unit == OBSERVATIONS and p.depth >= OBSERVATION_CAP:  # poe.ninja counts no further: the depth is not known (#930)
                found.append(PriceMark(DEPTH, f"price on at least {units_text(p.depth)} observations, poe.ninja's count stops there: whether the market holds what the plan buys is not known"))
            else:
                found.append(PriceMark(DEPTH, f"price on {units_text(p.depth)} {noun}"))
    if p.recorded and p.trade_unread is not None and found:  # beside every other reason, a previous league's included; a plain fact needs none
        found.append(PriceMark(TRADE_UNREAD, f"the trade offers beside it were not read: {p.trade_unread}"))
    if not p.recorded:
        found.append(PriceMark(NOT_RECORDED, NOT_RECORDED_WORDS))
    return tuple(found)


MAX_RECIPE_STEPS = 16  # more tiers than any chain has; a row that says more is not believed


def recipe_anchor(entry: PriceEntry, price_file: PriceFile) -> tuple[str, PriceEntry, float] | None:
    """What a row the upgrade recipe wrote rests on (`essence_recipe.py`): (the anchor's name, its row in the file, how many units of
    this tier one anchor unit is worth: 3 per tier between them); None for any other row, or when the file no longer holds the anchor
    (it is missing, or is itself a recipe row). A row whose record of the tiers is unreadable counts one for one."""
    detail = entry.detail or {}
    name, steps, per = detail.get("anchor"), detail.get("steps"), detail.get("per")
    if entry.source != RECIPE or not isinstance(name, str):
        return None
    anchor = price_file.prices.get(name)
    if anchor is None or anchor.source == RECIPE:
        return None
    whole = all(isinstance(value, int) and not isinstance(value, bool) for value in (steps, per)) and 0 <= steps <= MAX_RECIPE_STEPS and 1 <= per <= MAX_RECIPE_STEPS
    return name, anchor, float(per**steps) if whole else 1.0


def judged_depth(entry: PriceEntry, price_file: PriceFile) -> float | None:
    """The depth a plan's uses of `entry` are compared with, in units of the entry's own name: its recorded depth, and for a row the
    upgrade recipe wrote the depth of its anchor times the units of this tier one anchor unit is worth. None when none is recorded."""
    rests_on = recipe_anchor(entry, price_file)
    if rests_on is not None:
        _, anchor, per_anchor = rests_on
        p = provenance_of(anchor, price_file)
        return None if p is None or not p.recorded or p.depth is None else p.depth * per_anchor
    p = provenance_of(entry, price_file)
    return None if p is None or not p.recorded else p.depth


def _recipe_marks(entry: PriceEntry, price_file: PriceFile, uses: float | None) -> tuple[PriceMark, ...]:
    """The marks of a row the upgrade recipe wrote (`essence_recipe.py`): what it is a third of, then every reason against the market
    price its chain rests on, judged for the anchor units the plan's uses come to (`uses` None is one unit of this tier, as for any
    price); a row whose anchor the file no longer holds says so."""
    upper = (entry.detail or {}).get("of")
    found = [PriceMark(FROM_RECIPE, f"priced from the vendor recipe: one third of {upper if isinstance(upper, str) else 'the next tier up'}")]
    rests_on = recipe_anchor(entry, price_file)
    if rests_on is None:
        found.append(PriceMark(NOT_RECORDED, "the market price the recipe price rests on is not in the file"))
        return tuple(found)
    name, anchor, per_anchor = rests_on
    found.extend(PriceMark(mark.code, f"{name}: {mark.reason}") for mark in price_marks(anchor, price_file, (1.0 if uses is None else uses) / per_anchor))
    return tuple(found)


def _days_before(day: str, price_file: PriceFile) -> int:
    try:
        return (price_file.fetched_at.date() - date.fromisoformat(day)).days
    except ValueError:
        return 0


def _stand_in_words(p: Provenance) -> str:
    if p.exact_listings is None:
        return "price of a wider item; the exact item's listings were not read"
    plural = "listing" if p.exact_listings == 1 else "listings"
    if p.exact_listings == 0 or p.exact_price is None:
        return f"price of a wider item; the exact item has {p.exact_listings} {plural}"
    return f"price of a wider item; the exact item has {p.exact_listings} {plural} at {chaos_text(p.exact_price)} Chaos"
