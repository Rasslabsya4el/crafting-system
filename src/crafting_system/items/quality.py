"""Catalyst quality on an item (ADR-0029): one catalyst type and a percent from 0 to 20."""

from dataclasses import dataclass
from enum import StrEnum

from .errors import QualityError


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
