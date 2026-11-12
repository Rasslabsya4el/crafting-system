"""The Orb of Remembrance: it sets the Memory Strand count of a normal equipment item to a new random number (ADR-0043, ticket #278).

* **What it accepts.** A normal-rarity equipment item that is not corrupted (claim `memory_strands.remembrance_action`). A jewel is refused:
  the wiki says "equipment" and treats jewels as a class apart, and no player reports one (claim `memory_strands.remembrance_classes_observed`,
  `approximate`). A flask, a map or any base outside the item domain is no equipment and is refused too. A magic or rare item is refused: a
  further re-roll after the first craft needs a Scouring Orb first, which keeps the strands (ADR-0041).
* **What it does.** It keeps the item as it is and sets the count to a number drawn from `remembrance_table()`, whatever the count was: it adds
  strands to an item with none and re-rolls an item that has some. The result does not depend on the old count (claim
  `memory_strands.remembrance_independent_of_old_count`, `approximate`). After one orb the item is still normal, so another may follow: the
  state graph has the self-loop, and the solver finds the stop threshold itself (the cheapest policy accepts a count when a re-roll is dearer in
  expectation). The orb is a re-roll that can be repeated, an inference from the wiki's "randomises" (`approximate`).
* **The table.** `x ~ N(35, 25)`, accepted when `10 <= x < 100.5` and redrawn otherwise, the result `round(x)` (claim
  `memory_strands.remembrance_distribution`, `approximate`): 91 probabilities for the counts 10 to 100, computed once from the claim's values to
  twelve digits and held as fractions that sum to exactly 1. Its mean is 41.84 (ADR-0043); against the author's 2,255 results its chi-square is
  7.2 on 17 degrees of freedom (`tests/test_remembrance.py`).
* **The price** is the orb's own from the price file, `Orb of Remembrance`. The 56 Chaos of a search snippet is no design number.

The kind exists only in a plan that considers Memory Strands (`needs_strands`, ADR-0040). Its claims are strand claims (`strand_claims`, looked up
by id inside the declaration, not module constants), so an answer that does not consider strands never names them.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from types import MappingProxyType

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .errors import NotApplicableError
from .scour import ScourOutcomes
from .strand_use import Recounted, StrandUse

__all__ = [
    "ORB_OF_REMEMBRANCE",
    "RemembranceOrb",
    "is_equipment",
    "remembrance_refusal",
    "remembrance_table",
]

ORB_OF_REMEMBRANCE = "Orb of Remembrance"  # the price-file name
EQUIPMENT_DOMAIN = "item"  # the domain of every equipment base in the game data (a flask's is `flask`, a jewel's `misc` or `abyss_jewel`)
_DIGITS = 12  # the table is computed to twelve digits (ADR-0043)


def _jewel_classes() -> frozenset[str]:
    return frozenset(get_rule("affix_count.rare_jewel_max_per_side").value["item_classes"])


def _claims() -> tuple[str, ...]:
    return (
        "memory_strands.remembrance_action",
        "memory_strands.remembrance_distribution",
        "memory_strands.remembrance_independent_of_old_count",
        "memory_strands.remembrance_classes_observed",
    )


@cache
def remembrance_table() -> Mapping[int, Fraction]:
    """The chance of each count 10 to 100 after one Orb of Remembrance, as exact fractions that sum to 1 (claim `memory_strands.remembrance_distribution`).

    The mass of the normal on the cell of each count (`[k - 0.5, k + 0.5)` cut to the accepted range) is computed in floats and rounded to
    twelve digits; the table is those whole numbers over their sum, so it sums to exactly 1 and each chance is the claim's to about twelve digits.
    """
    value = get_rule("memory_strands.remembrance_distribution").value
    if value["rounding"] != "nearest":
        raise ValueError(f"the Remembrance table rounds to the nearest whole number; the claim says {value['rounding']!r}")
    mean, sd, low, high = value["mean"], value["sd"], value["accept_from"], value["accept_below"]

    def below(x: float) -> float:
        return 0.5 * (1 + math.erf((x - mean) / (sd * math.sqrt(2))))

    masses: dict[int, int] = {}
    for count in range(math.ceil(low - 0.5), math.floor(high - 0.5) + 1):
        start, end = max(count - 0.5, low), min(count + 0.5, high)
        if end > start:
            masses[count] = round((below(end) - below(start)) * 10**_DIGITS)
    total = sum(masses.values())
    return MappingProxyType({count: Fraction(mass, total) for count, mass in masses.items() if mass})  # cached and shared: read-only


def is_equipment(data: GameData, item: Item) -> bool:
    """Whether `item` is equipment: a base of the item domain that is not a jewel."""
    base = data.base_items.get(item.base_id)
    return base is not None and base.domain == EQUIPMENT_DOMAIN and base.item_class not in _jewel_classes()


def remembrance_refusal(data: GameData, item: Item) -> str | None:
    """Why an Orb of Remembrance cannot be used on `item`, or None when it can."""
    base = data.base_items.get(item.base_id)
    if base is not None and base.item_class in _jewel_classes():
        return "an Orb of Remembrance works on equipment only, and a jewel is not equipment (the wiki's word; no player reports one)"
    if not is_equipment(data, item):
        return f"an Orb of Remembrance works on equipment only, and this item is a {base.item_class if base else item.base_id}"
    if item.corrupted:
        return "the item is corrupted, and a corrupted item takes no Orb of Remembrance"
    if item.rarity is not Rarity.NORMAL:
        return f"an Orb of Remembrance works on a normal item only, and this item is {item.rarity}"
    return None


@dataclass(frozen=True)
class RemembranceOrb(Action):
    """One Orb of Remembrance: the item stays as it is, its strand count becomes a draw from `remembrance_table()`."""

    def label(self, data: GameData | None = None) -> str:
        return ORB_OF_REMEMBRANCE

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return {ORB_OF_REMEMBRANCE: 1}

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.recounting(remembrance_table(), *(get_rule(claim) for claim in _claims()))

    def reads(self, data: GameData) -> Reads:
        return Reads.nothing(block_invariant=True)  # a normal item holds no mod to read; the count it had does not matter

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        # It adds no mod and draws none; `named` stays None (not the empty set of a craft that adds nothing, which a planner may leave out
        # as useless): what it changes is the strand count, which `strand_use` declares.
        return Adds(named=None, draws=False)

    def outcomes(self, data: GameData, item: Item) -> Recounted:
        """The item unchanged, its count set by the table. Raises `NotApplicableError` for a jewel, a non-equipment item, a corrupted or a non-normal one."""
        refusal = remembrance_refusal(data, item)
        if refusal is not None:
            raise NotApplicableError(refusal)
        # one result with chance 1, the item as it stands (the `ScourOutcomes` shape: a fixed result, no new mod); the count is `Recounted`'s
        return Recounted(ScourOutcomes(data, item), data, remembrance_table())


@kind("orb-of-remembrance", order=103, needs_strands=True)
def _orb_of_remembrance(data: GameData, item: Item):
    if remembrance_refusal(data, item) is None:
        yield RemembranceOrb()
