"""The Blessed Orb: rerolls the values of an item's implicits, inside each implicit's own range (ticket #157, ADR-0027).

It changes the rolled values of implicits and nothing else: no explicit mod is added or removed, no implicit changes
its identity (`blessed_orb.rerolls_implicit_values_only`). Every implicit that has a range gets a fresh value per stat,
uniform over the integers of the stat's range, both ends included, independently per stat
(`blessed_orb.new_value_uniform_in_range`, approximate). **The previous value can roll again**
(`blessed_orb.previous_value_can_repeat`, the owner's answer, against the wiki's exclusion), so the law of the new value
does not depend on the old one, whatever the item held.

The implicits that count are the item's own (`Item.implicits`) and the ranged implicits of its base: an item built
without them still has the base's implicit in the game, so the Orb stores it, freshly rolled, on the result. A base
implicit with no range (every stat fixed) is not rerolled and not stored.

Refusals, in this order:

* `NotApplicableError`: the item is corrupted (`blessed_orb.refused_on_corrupted`), or it has no implicit with a
  range of values (`blessed_orb.needs_ranged_implicit`).
* `OutOfScopeError`: the item holds an Eldritch implicit. The wiki lets the Orb be used on such an item
  (`blessed_orb.special_implicits_allowed`) but does not say whether both Eldritch implicits are rerolled, and no
  admitted claim does, so by ADR-0004 and ADR-0027 the action is not offered there. It is checked before the
  ranged-implicit test, because the Eldritch implicit may be the only one.

The exact result is a `BlessedOutcomes`: one `Fixed` part of probability 1 (the exact result holds no value: the new
implicit values stand at their lowest, like the mods a `Finite` adds), `chance_all` and `distribution` as for any
action that adds no mod, `sample` which rolls the values, and `value_law(mod_id, index)`, the exact law of one rolled
value, for a requirement on an implicit roll (ticket #158). `Reads.implicits` and `Adds.implicits` are declared, so the
compressed state keeps the implicits: until #158 it refuses an item that holds a base implicit (`OutOfScopeError`),
and the kind is not a planner kind. A Blessed Orb on an item with no implicit stored, or one that stores a base implicit,
is therefore tested here on the outcomes themselves and not through the kernel of `abstraction`.
"""

import random
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.data import GameData, Mod, StatRange
from crafting_system.items import ImplicitMod, Item, eldritch_side
from crafting_system.items.implicits import BASE_GRADE
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .errors import NotApplicableError, OutOfScopeError
from .finite import Finite
from .rolls import roll_values

NEEDS_RANGED_IMPLICIT = get_rule("blessed_orb.needs_ranged_implicit")
REFUSED_ON_CORRUPTED = get_rule("blessed_orb.refused_on_corrupted")
REROLLS_VALUES_ONLY = get_rule("blessed_orb.rerolls_implicit_values_only")
SPECIAL_IMPLICITS_ALLOWED = get_rule("blessed_orb.special_implicits_allowed")
NEW_VALUE_UNIFORM = get_rule("blessed_orb.new_value_uniform_in_range")
PREVIOUS_VALUE_CAN_REPEAT = get_rule("blessed_orb.previous_value_can_repeat")
COST = get_rule("blessed_orb.cost")
ONE = Fraction(1)


def has_range(mod: Mod) -> bool:
    """Whether some stat of `mod` rolls over more than one value."""
    return any(stat.min != stat.max for stat in mod.stats)


def value_law(stat: StatRange) -> dict[int, Fraction]:
    """The law of one value rolled by a Blessed Orb: uniform over the integers of the stat's range, both ends included."""
    low, high = min(stat.min, stat.max), max(stat.min, stat.max)
    return {value: Fraction(1, high - low + 1) for value in range(low, high + 1)}


def _lowest(mod: Mod) -> tuple[int, ...]:
    return tuple(min(stat.min, stat.max) for stat in mod.stats)


@dataclass(frozen=True, eq=False)
class BlessedOutcomes(Finite):
    """What a Blessed Orb leaves behind: the item with the values of `rerolled` (mod ids of implicits) rolled afresh.

    One result of probability 1 (see `Finite`), whose implicit values stand at their lowest; `sample` rolls them.
    """

    rerolled: tuple[str, ...] = ()

    def value_law(self, mod_id: str, index: int) -> dict[int, Fraction]:
        """The exact law of the value of stat `index` of the rerolled implicit `mod_id`, whatever it was before."""
        if mod_id not in self.rerolled:
            raise ValueError(f"implicit {mod_id} is not rerolled by this Blessed Orb")
        return value_law(self.data.mods[mod_id].stats[index])

    def sample(self, rng: random.Random) -> Item:
        """The item with every rerolled implicit's values rolled (each stat uniform over its range); the rest as it was."""
        ((_, result),) = self.results
        implicits = tuple(
            ImplicitMod(entry.mod_id, entry.grade, roll_values(rng, self.data.mods[entry.mod_id]))
            if entry.mod_id in self.rerolled
            else entry
            for entry in result.implicits
        )
        return result.changed(self.data, implicits=implicits)


@dataclass(frozen=True)
class BlessedOrb(Action):
    """One Blessed Orb."""

    def label(self, data: GameData | None = None) -> str:
        return "Blessed Orb"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return dict(COST.value)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        # exactly the claims this file cites: the helpers it imports (`finite`, `rolls`) hold none of their own
        return frozenset(
            rule.id
            for rule in (
                NEEDS_RANGED_IMPLICIT, REFUSED_ON_CORRUPTED, REROLLS_VALUES_ONLY, SPECIAL_IMPLICITS_ALLOWED, NEW_VALUE_UNIFORM,
                PREVIOUS_VALUE_CAN_REPEAT, COST,
            )
        )

    def reads(self, data: GameData) -> Reads:
        # It reads which implicits the item holds (an Eldritch one refuses it) and nothing of the explicit mods, which stay
        # as they are: the junk is kept as counts, no family is told apart.
        return Reads(junk=True, families=frozenset(), implicits=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        # No mod is added; the values of implicits change, so it matters only for a requirement on an implicit roll.
        return Adds(named=None, draws=False, needs_roll_limit=True, implicits=True)

    def outcomes(self, data: GameData, item: Item) -> BlessedOutcomes:
        """The outcomes of using the orb on `item`: its ranged implicits rerolled.

        Raises `NotApplicableError` for a corrupted item and for one with no implicit that has a range, and
        `OutOfScopeError` for one that holds an Eldritch implicit.
        """
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Blessed Orb")
        stored = {entry.mod_id: entry for entry in item.implicits}
        for entry in item.implicits:
            if eldritch_side(data.mods[entry.mod_id]) is not None:
                raise OutOfScopeError(
                    f"the item holds the Eldritch implicit {entry.mod_id}: a Blessed Orb may be used on it, but no admitted "
                    "claim says what it does to an Eldritch implicit, so the action is not offered (ADR-0027)"
                )
        base = data.base_items[item.base_id]
        kept = tuple(entry for entry in item.implicits if not has_range(data.mods[entry.mod_id]))
        ranged = [mod_id for mod_id in base.implicits if mod_id in data.mods and has_range(data.mods[mod_id])]
        ranged += [mod_id for mod_id, entry in stored.items() if has_range(data.mods[mod_id]) and mod_id not in ranged]
        if not ranged:
            raise NotApplicableError(
                "a Blessed Orb cannot be used here: the item has no implicit with a range of values"
            )
        rolled = tuple(
            ImplicitMod(mod_id, stored[mod_id].grade if mod_id in stored else BASE_GRADE, _lowest(data.mods[mod_id]))
            for mod_id in sorted(ranged)
        )
        result = item.changed(data, implicits=(*kept, *rolled))
        return BlessedOutcomes(data, item, ((ONE, result),), tuple(sorted(ranged)))


@kind(
    "blessed-orb",
    order=88,
    planner=False,
    why_not="a requirement on the roll of an implicit, and the compressed state of a base implicit, are ticket #158",
)
def _blessed_orb(data: GameData, item: Item):
    base = data.base_items.get(item.base_id)
    if base is None or item.corrupted:
        return
    if any(eldritch_side(data.mods[entry.mod_id]) is not None for entry in item.implicits):
        return  # not offered: no admitted claim says what the Orb does to an Eldritch implicit (`outcomes` refuses it too)
    stored = (data.mods[entry.mod_id] for entry in item.implicits)
    if any(has_range(mod) for mod in stored) or any(mod_id in data.mods and has_range(data.mods[mod_id]) for mod_id in base.implicits):
        yield BlessedOrb()
