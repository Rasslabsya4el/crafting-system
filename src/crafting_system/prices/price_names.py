"""The price-file names of bases and beasts (#40).

A beast is priced under its own name ("Wild Bristle Matron"). A base is priced per item level and
influence set, so its name carries both: "Stygian Vise (ilvl 85)", "Stygian Vise (ilvl 85, Hunter)",
"Vaal Regalia (ilvl 86, Elder/Warlord)". Influences are always written in the game's order (Shaper,
Elder, Crusader, Hunter, Redeemer, Warlord), whatever order a source used, so one base has one name.
Callers that price an item build the name with `base_price_name`.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

INFLUENCES = ("Shaper", "Elder", "Crusader", "Hunter", "Redeemer", "Warlord")
_BY_LOWER = {name.lower(): name for name in INFLUENCES}
_NAME = re.compile(r"(?P<name>.+) \(ilvl (?P<level>\d+)(?:, (?P<influences>[A-Za-z/]+))?\)")


@dataclass(frozen=True)
class BaseKey:
    """A base as the price file names it: base name, item level and influences (canonical order)."""

    name: str
    item_level: int
    influences: tuple[str, ...] = ()


def canonical_influences(influences: Iterable[str]) -> tuple[str, ...]:
    """Influence names, any case, as a tuple in game order without repeats; unknown ones raise ValueError."""
    found = set()
    for influence in influences:
        name = _BY_LOWER.get(influence.strip().lower())
        if name is None:
            raise ValueError(f"unknown influence {influence!r}; known: {', '.join(INFLUENCES)}")
        found.add(name)
    return tuple(name for name in INFLUENCES if name in found)


def base_price_name(name: str, item_level: int, influences: Iterable[str] = ()) -> str:
    """The price-file name of a base: "Stygian Vise (ilvl 85, Hunter)"."""
    shown = canonical_influences(influences)
    suffix = f", {'/'.join(shown)}" if shown else ""
    return f"{name} (ilvl {item_level}{suffix})"


def parse_base_price_name(price_name: str) -> BaseKey | None:
    """The `BaseKey` of a name made by `base_price_name`, or None when it is not one (a beast, a currency)."""
    match = _NAME.fullmatch(price_name)
    if match is None:
        return None
    try:
        influences = canonical_influences((match["influences"] or "").split("/") if match["influences"] else ())
    except ValueError:
        return None
    return BaseKey(match["name"], int(match["level"]), influences)
