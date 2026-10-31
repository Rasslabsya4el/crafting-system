"""The shared add: draw mods onto an item that keeps the mods it has (D1, D3, D14 of issue #28).

An Orb of Transmutation, Alteration, Augmentation, Regal Orb and Orb of Alchemy (and the Exalted
Orb, later) all do the same thing once the item is in the state the orb leaves it in before any
draw (`retained`): they draw mods one at a time from the pool of that item, up to a total number of
mods, with `Outcomes.fill`. The pool takes care of the rest: a family on the item is out of it, a
side that is full closes (`affix_pool.full_side_closes`), the draw is proportional to the weights
of both sides together. An action only chooses the retained item and the totals:

* `add_one_mod(data, item, what)`: one more mod on `item`, as it stands (Augmentation, and the Exalted Orb
  of ticket #67); `rarity` upgrades it first (Regal Orb: magic to rare, which opens the rare capacity).
* `draw_onto(data, retained, totals)`: any total, as the Transmutation and the Alteration (1 or 2 mods) do.
  (The Alchemy goes through `Outcomes.reroll`, the Chaos Orb's draw.)

An add of one mod that has no legal mod is refused with `NotApplicableError` and consumes nothing
(`magic_orbs.add_refused_when_no_legal_mod`); a draw that finds the pool dry stops with fewer mods
(`magic_orbs.dry_pool_leaves_fewer_mods`).
"""

from collections.abc import Mapping
from fractions import Fraction

from crafting_system.data import GameData
from crafting_system.items import Item, Rarity, Side
from crafting_system.rules import get_rule

from .errors import NotApplicableError
from .outcomes import Outcomes
from .pool import PoolFamily

ADD_REFUSED_WHEN_NO_LEGAL_MOD = get_rule("magic_orbs.add_refused_when_no_legal_mod")
FULL_SIDE_CLOSES = get_rule("affix_pool.full_side_closes")

ONE = Fraction(1)


def refuse_if_nothing_to_draw(
    data: GameData, retained: Item, pool: tuple[PoolFamily, ...], what: str
) -> None:
    """Raise `NotApplicableError` when no mod of `pool` fits a free slot of `retained`: the draw is refused.

    `what` names the action in the message ("an Orb of Augmentation").
    """
    free = {side: retained.free_slots(data, side) for side in Side}
    if not any(free.values()):
        raise NotApplicableError(
            f"{what} cannot add a mod: the {retained.rarity} item has no open prefix or suffix slot"
        )
    if not any(free[family.side] > 0 for family in pool):
        raise NotApplicableError(
            f"{what} cannot add a mod: no mod of the pool is legal on this item "
            "(every candidate of an open side is blocked by a family on the item or is above the item level)"
        )


def draw_onto(data: GameData, retained: Item, totals: Mapping[int, Fraction]) -> Outcomes:
    """The outcomes of drawing onto `retained` up to `totals`, whatever the pool holds.

    A draw with nothing to draw leaves `retained` as it is, like a Chaos Orb on an item whose slots
    are all fractured: only an add of exactly one mod is refused (`add_one_mod`).
    """
    return Outcomes.fill(data, retained, totals)


def add_one_mod(data: GameData, item: Item, what: str, rarity: Rarity | None = None) -> Outcomes:
    """The outcomes of adding exactly one mod to `item`, which keeps all it has (`rarity` replaces its rarity first).

    Raises `NotApplicableError` when the item has no open slot or no mod is legal for an open slot.
    `what` names the action in the message ("a Regal Orb").
    """
    retained = item if rarity is None else item.changed(data, rarity=rarity)
    result = Outcomes.fill(data, retained, {len(retained.mods) + 1: ONE})
    refuse_if_nothing_to_draw(data, retained, result.pool, what)
    return result
