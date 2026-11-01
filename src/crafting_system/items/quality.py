"""Quality on an item, in two kinds: the catalyst quality of jewellery (ADR-0029) and the plain quality of a weapon or armour (ADR-0049).

`Quality` is the catalyst kind: one catalyst type and a percent from 0 to 20, on a ring, an amulet or a belt. `PlainQuality` is the
weapon and armour kind: a percent from 0 to 30 (Blacksmith's Whetstones and Armourer's Scraps raise it to 20, a random drop can
carry up to 30) with no type, on the 20 item classes of the socket table. The two never share an item class, so an item holds one:
`Item` refuses a catalyst type on a weapon and a plain percent on a ring. `PlainQuality.type` is None, so code that asks a held
quality for its catalyst type reads "no catalyst" instead of failing.
"""

from dataclasses import dataclass
from enum import StrEnum

from .errors import QualityError
from .sockets import SOCKET_ITEM_CLASSES


class CatalystType(StrEnum):
    """The catalyst that gave the quality: the ten regular ones, Sinistral and Dextral."""

    ABRASIVE = "abrasive"
    ACCELERATING = "accelerating"
    FERTILE = "fertile"
    IMBUED = "imbued"
    INTRINSIC = "intrinsic"
    NOXIOUS = "noxious"
    PRISMATIC = "prismatic"
    TEMPERING = "tempering"
    TURBULENT = "turbulent"
    UNSTABLE = "unstable"
    SINISTRAL = "sinistral"
    DEXTRAL = "dextral"


MAX_QUALITY = 20
CATALYST_ITEM_CLASSES = frozenset({"Ring", "Amulet", "Belt"})
MAX_PLAIN_QUALITY = 30
PLAIN_QUALITY_ITEM_CLASSES = SOCKET_ITEM_CLASSES  # weapons and armour: the 20 classes the socket table and the bench socket crafts cover


@dataclass(frozen=True, slots=True)
class Quality:
    """The catalyst quality of an item: its type and a whole percent from 0 to `MAX_QUALITY`."""

    type: CatalystType
    percent: int

    def __post_init__(self) -> None:
        if not isinstance(self.type, CatalystType):
            raise QualityError(f"quality type {self.type!r} is not a CatalystType")
        if type(self.percent) is not int:
            raise QualityError(f"quality of {self.type.value} has percent {self.percent!r}, not an integer")
        if not 0 <= self.percent <= MAX_QUALITY:
            raise QualityError(f"quality of {self.type.value} has percent {self.percent}, outside 0 to {MAX_QUALITY}")


@dataclass(frozen=True, slots=True)
class PlainQuality:
    """The quality of a weapon or armour: a whole percent from 0 to `MAX_PLAIN_QUALITY`, no catalyst type."""

    percent: int

    def __post_init__(self) -> None:
        if type(self.percent) is not int:
            raise QualityError(f"plain quality has percent {self.percent!r}, not an integer")
        if not 0 <= self.percent <= MAX_PLAIN_QUALITY:
            raise QualityError(f"plain quality has percent {self.percent}, outside 0 to {MAX_PLAIN_QUALITY}")

    @property
    def type(self) -> None:
        """No catalyst type: this quality is not a catalyst's."""
        return None
