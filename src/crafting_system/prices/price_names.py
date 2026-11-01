"""The price-file names of bases and beasts (#40).

A beast is priced under its own name ("Wild Bristle Matron"). A base is priced per item level and
influence set, so its name carries both: "Stygian Vise (ilvl 85)", "Stygian Vise (ilvl 85, Hunter)",
"Vaal Regalia (ilvl 86, Elder/Warlord)". Influences are always written in the game's order (Shaper,
Elder, Crusader, Hunter, Redeemer, Warlord), whatever order a source used, so one base has one name.
Callers that price an item build the name with `base_price_name`.

The currencies, Omens and beasts of the socket family (batch B6, ticket #228) are priced under the name the game data gives the item, which
is also the name the actions of `actions/socket_orbs.py` and the claims `sockets.*_cost` use for what one use consumes. The constants below
are those names, in one place for the price layer; `tests/test_actions_sockets_claims.py` holds them equal to the claims.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

INFLUENCES = ("Shaper", "Elder", "Crusader", "Hunter", "Redeemer", "Warlord")

# The socket family's price names (ADR-0045 to ADR-0049): the orbs, the Omens, the two quality currencies and the three beasts.
JEWELLERS_ORB = "Jeweller's Orb"
ORB_OF_FUSING = "Orb of Fusing"
CHROMATIC_ORB = "Chromatic Orb"
ORB_OF_BINDING = "Orb of Binding"
OMEN_OF_THE_JEWELLER = "Omen of the Jeweller"
OMEN_OF_CONNECTIONS = "Omen of Connections"
OMEN_OF_TRICHROMATISM = "Omen of Trichromatism"
BLACKSMITHS_WHETSTONE = "Blacksmith's Whetstone"
ARMOURERS_SCRAP = "Armourer's Scrap"
THE_BLACK_MORRIGAN = "The Black Mórrígan"
CRAICIC_SHIELD_CRAB = "Craicic Shield Crab"
CRAICIC_SAND_SPITTER = "Craicic Sand Spitter"
SOCKET_PRICE_NAMES = (
    JEWELLERS_ORB,
    ORB_OF_FUSING,
    CHROMATIC_ORB,
    ORB_OF_BINDING,
    OMEN_OF_THE_JEWELLER,
    OMEN_OF_CONNECTIONS,
    OMEN_OF_TRICHROMATISM,
    BLACKSMITHS_WHETSTONE,
    ARMOURERS_SCRAP,
    THE_BLACK_MORRIGAN,
    CRAICIC_SHIELD_CRAB,
    CRAICIC_SAND_SPITTER,
)
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


def canonical_price_name(name: str) -> str:
    """`name` with the influences of a base price name in game order ("Hunter/Warlord"); other names unchanged."""
    key = parse_base_price_name(name)
    return name if key is None else base_price_name(key.name, key.item_level, key.influences)
