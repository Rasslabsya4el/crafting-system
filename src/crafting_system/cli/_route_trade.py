"""The buy step of the route view: what the buy accepts and a link to the search on the official trade site.

The link is built from the buy spec with the query code of `prices` (`build_query`, `resolve_buy_mod`) and the
trade site's stat list; this module sends nothing. The owner opens the link in a browser: the page itself makes
no request (it has no script and no external file). A mod the stat list cannot resolve (no list at hand, or the
text is not on it) is left out of the query and named in `BuyStep.unresolved`, so the page says so.
"""

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import quote

from crafting_system.data import Mod
from crafting_system.prices import BuyMod, BuySpec, TradeSpecError
from crafting_system.prices.trade_query import StatFilter, build_query
from crafting_system.prices.trade_stats import TradeStats, named_mods, resolve_buy_mod

TRADE_SEARCH = "https://www.pathofexile.com/trade/search"
RANGE = re.compile(r"\(-?\d+(?:\.\d+)?--?\d+(?:\.\d+)?\)")
MARKUP_LABEL = re.compile(r"\[[^\]|]*\|([^\]]*)\]")
MARKUP = re.compile(r"\[([^\]|]*)\]")


@dataclass(frozen=True)
class BuyStep:
    """A buy spec as the page shows it: the filter in words, the search link and the mods the link cannot filter on."""

    name: str
    url: str
    accepts: tuple[str, ...]
    unresolved: tuple[str, ...]


def buy_step(spec: BuySpec, league: str, game_mods: Iterable[Mod], stats: TradeStats | None) -> BuyStep:
    """The buy step for `spec`: `stats` is the trade site's stat list, None when it is not at hand."""
    mods = tuple(game_mods)
    filters: list[StatFilter] = []
    unresolved: list[str] = []
    for mod in spec.mods:
        text = buy_mod_text(mod, mods)
        try:
            if stats is None:
                raise TradeSpecError("no stat list")
            filters.append(resolve_buy_mod(mod, mods, stats))
        except TradeSpecError:
            unresolved.append(text)
    body = build_query(spec, filters).body()
    link = f"{TRADE_SEARCH}/{quote(league, safe='')}?q={quote(json.dumps(body, separators=(',', ':')), safe='')}"
    return BuyStep(spec.name, link, _accepts(spec, mods), tuple(unresolved))


def buy_mod_text(mod: BuyMod, game_mods: Iterable[Mod]) -> str:
    """The mod a buy spec asks for as the game words it, with `#` for the roll; a minimum is appended."""
    text = _named_text(mod.stat, named_mods(mod, game_mods)) or mod.stat
    text = RANGE.sub("#", MARKUP.sub(r"\1", MARKUP_LABEL.sub(r"\1", text))).replace("\n", " / ")
    if mod.minimum is not None:
        text += f" (at least {mod.minimum:g})"
    return text


def _named_text(name: str, mods: tuple[Mod, ...]) -> str | None:
    """The text of the family `name`, else of the mod id `name`; None when it is neither (an English stat text)."""
    for mod in mods:
        if name in mod.families and mod.text:
            return mod.text
    for mod in mods:
        if mod.id == name and mod.text:
            return mod.text
    return None


def _accepts(spec: BuySpec, mods: tuple[Mod, ...]) -> tuple[str, ...]:
    lines = [spec.rarity.capitalize()]
    if spec.item_level_min is not None and spec.item_level_max is not None:
        lines.append(f"item level {spec.item_level_min} to {spec.item_level_max}")
    elif spec.item_level_min is not None:
        lines.append(f"item level {spec.item_level_min} or more")
    elif spec.item_level_max is not None:
        lines.append(f"item level {spec.item_level_max} or less")
    if spec.influences:
        lines.extend(f"{name.capitalize()} influence" for name in spec.influences)
    else:
        lines.append("no influence")
    lines.append("corrupted" if spec.corrupted else "not corrupted")
    for mod in spec.mods:
        text = buy_mod_text(mod, mods)
        lines.append(f"fractured: {text}" if mod.fractured else f"implicit: {text}" if mod.implicit else text)
    return tuple(lines)
