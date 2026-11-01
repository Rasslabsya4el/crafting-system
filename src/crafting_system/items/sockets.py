"""The sockets of an item and the class maximum (ADR-0046).

An item stores its sockets as `Sockets`: one `SocketColour` per socket in socket order and the link groups as their sizes in
the same order, so `(3, 2, 1)` is sockets 1 to 3 linked, 4 and 5 linked, 6 alone. Fusing links by sequential group sizes from
the first socket (ADR-0047), so a group is always a contiguous run. An item with no sockets stores `None`, which is also what an
item built before B6 holds. How the socket orbs change sockets is a rule of `actions`, not of this module.

The **class maximum** is the most sockets an item of a class can have, read from the claim `sockets.class_maximum_sockets`: a
value for each of the 20 item classes the socket crafts of the bench are offered for, and the one base the wiki names as an
exception (the Gnarled Branch). The claim is marked approximate: the wiki admits unnamed exceptions for small low-level bases.
`class_maximum(base)` is None for a class outside the table (jewellery, quivers, flasks, ...): such an item holds no sockets
here, and a socket target on it is refused as out of scope. The item-level gate of the Jeweller's Orb is an action's rule.

A base with an Abyssal Socket (the stat `local_has_X_abyss_sockets`, on a unique or a Delve crafted mod, or as an implicit of
the base) is recognised by `has_abyssal_socket`; the item does not refuse it, a socket target on it is refused (ADR-0046).
"""

from dataclasses import dataclass
from enum import StrEnum

from crafting_system.data import BaseItem, GameData, Mod
from crafting_system.rules import get_rule

from .errors import SocketError

CLASS_MAXIMUM = get_rule("sockets.class_maximum_sockets")
MAX_SOCKETS = 6
ABYSSAL_SOCKET_STAT = "local_has_X_abyss_sockets"
SOCKET_ITEM_CLASSES = frozenset(CLASS_MAXIMUM.value["by_class"])


class SocketColour(StrEnum):
    """The colour of one socket. White is the colour of a fresh socket since 3.29.0 (ADR-0046)."""

    WHITE = "W"
    RED = "R"
    GREEN = "G"
    BLUE = "B"


@dataclass(frozen=True, slots=True)
class Sockets:
    """The sockets of an item: a colour per socket and the sizes of the link groups, both in socket order.

    The group sizes add up to the number of sockets. One to six sockets; no socket at all is `None` on the item.
    """

    colours: tuple[SocketColour, ...]
    links: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.colours, tuple) or not all(isinstance(entry, SocketColour) for entry in self.colours):
            raise SocketError("socket colours must be a tuple of SocketColour")
        if not isinstance(self.links, tuple) or not all(type(size) is int for size in self.links):
            raise SocketError("socket links must be a tuple of whole group sizes")
        if not 1 <= len(self.colours) <= MAX_SOCKETS:
            raise SocketError(f"{len(self.colours)} sockets is outside 1 to {MAX_SOCKETS}")
        if any(size < 1 for size in self.links):
            raise SocketError(f"link group sizes {self.links} must all be 1 or more")
        if sum(self.links) != len(self.colours):
            raise SocketError(
                f"link groups {self.links} add up to {sum(self.links)} sockets, but there are {len(self.colours)} sockets"
            )

    @classmethod
    def unlinked(cls, colours: tuple[SocketColour, ...]) -> "Sockets":
        """`colours` with every socket in a group of its own."""
        return cls(colours, (1,) * len(colours))

    @property
    def count(self) -> int:
        """The number of sockets."""
        return len(self.colours)

    def groups(self) -> tuple[tuple[SocketColour, ...], ...]:
        """The colours of each link group, in socket order."""
        found = []
        start = 0
        for size in self.links:
            found.append(self.colours[start : start + size])
            start += size
        return tuple(found)


def class_maximum(base: BaseItem) -> int | None:
    """The most sockets an item on `base` can have, or None when its item class has no socket table (jewellery and the like)."""
    by_base = CLASS_MAXIMUM.value["by_base"]
    if base.id in by_base:
        return by_base[base.id]
    return CLASS_MAXIMUM.value["by_class"].get(base.item_class)


def is_abyssal_socket_mod(mod: Mod) -> bool:
    """Whether `mod` gives an Abyssal Socket: it carries the stat `local_has_X_abyss_sockets`."""
    return any(stat.id == ABYSSAL_SOCKET_STAT for stat in mod.stats)


def has_abyssal_socket(data: GameData, base_id: str, mod_ids: tuple[str, ...]) -> bool:
    """Whether the base's own implicits or any of the mods `mod_ids` give an Abyssal Socket."""
    base = data.base_items[base_id]
    return any(
        is_abyssal_socket_mod(data.mods[mod_id]) for mod_id in (*base.implicits, *mod_ids) if mod_id in data.mods
    )
