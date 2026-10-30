"""Map repoe-fork mods and English stat texts to trade stat ids (#39).

The trade site lists every stat it can filter on at `GET /api/trade/data/stats`, in groups
(`explicit`, `fractured`, `implicit`, `pseudo`, `crafted`, ...). The same stat hash appears in
several groups, so the group decides the id: `explicit.stat_1671376347` and
`fractured.stat_1671376347` are the same stat on a normal and on a fractured mod.

repoe-fork texts carry roll ranges (`+(6-11)% to Lightning Resistance`), the trade site shows
`#` (`+#% to Lightning Resistance`). `normalize_text` turns both into one key. This module only
reads; the download of the stats list is `trade_http`'s job, refreshed per patch.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from ..data import Mod
from .trade_query import BuyMod, StatFilter, TradeSpecError

_NUMBER = r"\d+(?:\.\d+)?"
# A repoe range: (6-11), (-10--5), (1.5-2.5). Checked before plain numbers.
_RANGE = re.compile(rf"\(\s*-?{_NUMBER}\s*-\s*-?{_NUMBER}\s*\)")
_PLAIN_NUMBER = re.compile(_NUMBER)
_SPACES = re.compile(r"\s+")
_LINK_WITH_LABEL = re.compile(r"\[[^\]|]*\|([^\]]*)\]")  # repoe markup [Resistances|Lightning Resistance]
_LINK = re.compile(r"\[([^\]|]*)\]")


def normalize_text(text: str) -> str:
    """The match key of a stat text: lower case, every number or range as `#`, spaces collapsed.

    A repoe range such as `(6-11)`, `(-10--5)` or `(1.5-2.5)` becomes one `#`; so does a plain
    number (`40`, `1.5`). A leading `+` or `-` stays where the text shows it, so
    `+(6-11)% to Lightning Resistance` and `+#% to Lightning Resistance` both give
    `+#% to lightning resistance`. A repoe `Adds (3-5) to (6-7) Fire Damage` gives
    `adds # to # fire damage`, the trade site's `Adds # to # Fire Damage`. repoe's `[X|Y]` markup
    becomes `Y` and `[X]` becomes `X`, as in `targets` (the layering keeps this module from using it).
    """
    text = _LINK.sub(r"\1", _LINK_WITH_LABEL.sub(r"\1", text))
    text = _RANGE.sub("#", text)
    text = _PLAIN_NUMBER.sub("#", text)
    return _SPACES.sub(" ", text).strip().lower()


@dataclass(frozen=True)
class TradeStatEntry:
    group: str
    id: str
    text: str
    normalized: str


@dataclass(frozen=True)
class TradeStats:
    """The trade site's stat list, flattened to (group, id, text) entries."""

    entries: tuple[TradeStatEntry, ...]

    def ids_for(self, group: str, text: str) -> tuple[str, ...]:
        """The ids in `group` whose normalized text equals the normalized `text`, in list order.

        The site writes local mods with a suffix (`Adds # to # Lightning Damage (Local)`), repoe
        text has none: when nothing in the group matches, the text followed by ` (local)` is tried.
        """
        wanted = normalize_text(text)
        return self._ids(group, wanted) or self._ids(group, f"{wanted} (local)")

    def _ids(self, group: str, wanted: str) -> tuple[str, ...]:
        found: list[str] = []
        for entry in self.entries:
            if entry.group == group and entry.normalized == wanted and entry.id not in found:
                found.append(entry.id)
        return tuple(found)


def _bad(what: str) -> TradeSpecError:
    return TradeSpecError(f"trade stats list: {what}")


def parse_trade_stats(raw: object) -> TradeStats:
    """Read the answer of `/api/trade/data/stats`; a wrong shape raises `TradeSpecError` naming it."""
    if not isinstance(raw, dict):
        raise _bad(f"expected a JSON object with a result list, got {type(raw).__name__}")
    groups = raw.get("result")
    if not isinstance(groups, list):
        raise _bad("the 'result' key must hold a list of groups")
    entries: list[TradeStatEntry] = []
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            raise _bad(f"group {index} must be an object, got {type(group).__name__}")
        group_id = group.get("id")
        if not isinstance(group_id, str) or not group_id:
            raise _bad(f"group {index} has no text 'id'")
        listed = group.get("entries")
        if not isinstance(listed, list):
            raise _bad(f"group {group_id!r} must have an 'entries' list")
        for position, entry in enumerate(listed):
            where = f"entry {position} of group {group_id!r}"
            if not isinstance(entry, dict):
                raise _bad(f"{where} must be an object, got {type(entry).__name__}")
            entry_id = entry.get("id")
            if not isinstance(entry_id, str) or not entry_id:
                raise _bad(f"{where} has no text 'id'")
            text = entry.get("text")
            if not isinstance(text, str):
                raise _bad(f"{where} ({entry_id}) has no text 'text'")
            entries.append(TradeStatEntry(group_id, entry_id, text, normalize_text(text)))
    return TradeStats(tuple(entries))


def _shared_text(label: str, members: list[Mod]) -> str:
    """The single-line text shared by every mod in `members` (named `label` in errors); refuses the rest."""
    variants: dict[tuple[str, ...], str] = {}
    for mod in members:
        if mod.text is None:
            raise TradeSpecError(f"{label}: mod {mod.id} has no text to search the trade site by")
        lines = tuple(normalize_text(line) for line in mod.text.split("\n"))
        variants.setdefault(lines, mod.text)
    if len(variants) > 1:
        shown = "; ".join(" / ".join(lines) for lines in variants)
        raise TradeSpecError(
            f"{label} has mods with different texts: {shown}; "
            "name one of them by its exact stat text or its mod id instead"
        )
    (lines,) = variants
    if len(lines) > 1:
        raise TradeSpecError(f"{label} is a hybrid mod ({' / '.join(lines)}): hybrid mods are not supported")
    return next(iter(variants.values()))


def _named_text(name: str, game_mods: Iterable[Mod]) -> str | None:
    """The trade text of the mod(s) `name` names: a repoe family id, else a mod id; None if it is neither.

    A name that is both a family and a mod id means the family. Anything else is left to the caller
    as an English stat text.
    """
    mods = tuple(game_mods)
    members = [mod for mod in mods if name in mod.families]
    if members:
        return _shared_text(f"family {name!r}", members)
    members = [mod for mod in mods if mod.id == name]
    if members:
        return _shared_text(f"mod {name!r}", members)
    return None


def resolve_buy_mod(mod: BuyMod, game_mods: Iterable[Mod], stats: TradeStats) -> StatFilter:
    """The trade stat filter for a buy mod.

    `mod.stat` is a repoe family id (the text comes from the mods of that family), a mod id (the text
    comes from that one mod, so it can name one member of a family whose mods have different texts),
    or an English stat text such as `+1 to Level of all Lightning Skill Gems`. The group is
    `fractured` for a fractured mod, `explicit` otherwise; exactly one id in that group must carry
    the text.
    """
    text = _named_text(mod.stat, game_mods)
    if text is None:
        text = mod.stat
    group = "fractured" if mod.fractured else "explicit"
    ids = stats.ids_for(group, text)
    if not ids:
        hint = ""
        if text is mod.stat and mod.stat.isidentifier():
            hint = "; it is not a family id or mod id of the game data either, if it was meant as one"
        raise TradeSpecError(
            f"no trade stat has the text {mod.stat!r} in group {group!r} "
            f"(searched {normalize_text(text)!r}){hint}"
        )
    if len(ids) > 1:
        raise TradeSpecError(
            f"several trade stats in group {group!r} have the text {mod.stat!r}: {', '.join(ids)}"
        )
    return StatFilter(ids[0], min=mod.minimum)
