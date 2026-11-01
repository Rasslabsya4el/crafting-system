"""The Divine Orb: rerolls the values of the mods an item holds, in place (ticket #71).

It changes values and nothing else: no mod is added or removed, no tier changes. The mods it changes are the
explicit mods that are not fractured (`divine_orb.fractured_mods_stay`) and not on a side that `Prefixes` or
`Suffixes Cannot Be Changed` locks (`divine_orb.locks_protect_existing_mods`); a crafted mod is one of them
(`divine_orb.rerolls_crafted_mods`, approximate) and so is a metamod on the open side. Each value is a uniform
integer over its stat's range, independently per stat (`affix_pool.values_uniform_integers`,
`divine_orb.hybrid_stats_roll_independently`, approximate).

Refusals, all `NotApplicableError` (nothing is consumed): a normal item (`divine_orb.accepts_magic_rare_unique`; the
item model holds no unique item), a corrupted one (`divine_orb.refused_on_corrupted`), and an item with no mod
to change (`divine_orb.refused_without_changeable_mod`). A mirrored item is not in the item model.

The result is a `Rerolled` part: the compressed state of `abstraction` reads it from `ActionOutcomes.components`.
`Reads.rerolls_values` tells `abstraction` to tell apart the mods that a roll requirement of the goal looks at.
`Adds.needs_roll_limit` tells a planner to offer it only for a target with such a requirement.
"""

import random
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import cached_property

from crafting_system.data import GameData, Mod, conflicts
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads, Rerolled
from .draw import Outcome
from .errors import NotApplicableError
from .metamods import locked_sides, on_locked_side
from .rolls import roll_values

ACCEPTS_MAGIC_RARE_UNIQUE = get_rule("divine_orb.accepts_magic_rare_unique")
REROLLS_WITHIN_THE_TIER = get_rule("divine_orb.rerolls_values_within_the_tier")
REROLLS_CRAFTED_MODS = get_rule("divine_orb.rerolls_crafted_mods")
HYBRID_STATS_INDEPENDENT = get_rule("divine_orb.hybrid_stats_roll_independently")
FRACTURED_MODS_STAY = get_rule("divine_orb.fractured_mods_stay")
LOCKS_PROTECT_EXISTING_MODS = get_rule("divine_orb.locks_protect_existing_mods")
REFUSED_ON_CORRUPTED = get_rule("divine_orb.refused_on_corrupted")
REFUSED_WITHOUT_CHANGEABLE_MOD = get_rule("divine_orb.refused_without_changeable_mod")
VALUES_UNIFORM_INTEGERS = get_rule("affix_pool.values_uniform_integers")
COST = get_rule("divine_orb.cost")
JEWELS_TAKE_THE_ORBS = get_rule("jewel.ordinary_orbs_work_on_jewels")
CLAIMS = frozenset(
    rule.id
    for rule in (
        ACCEPTS_MAGIC_RARE_UNIQUE, REROLLS_WITHIN_THE_TIER, REROLLS_CRAFTED_MODS, HYBRID_STATS_INDEPENDENT,
        FRACTURED_MODS_STAY, LOCKS_PROTECT_EXISTING_MODS, REFUSED_ON_CORRUPTED, REFUSED_WITHOUT_CHANGEABLE_MOD,
        VALUES_UNIFORM_INTEGERS, COST, JEWELS_TAKE_THE_ORBS,
    )
)
ONE = Fraction(1)


@dataclass(frozen=True, eq=False)
class DivineOutcomes:
    """What a Divine Orb leaves behind on `given`: the same mods, the values of `changed` rerolled.

    `changed` are `(mod id, fractured, crafted)` keys of the mods of `given`. It is one `Rerolled` part of
    probability 1; `distribution` has the one empty outcome (no mod is new) and `chance_all` is 1 for
    mods the item holds and 0 otherwise.
    """

    data: GameData
    given: Item
    changed: frozenset[tuple[str, bool, bool]]

    @cached_property
    def components(self) -> tuple[tuple[Fraction, Rerolled], ...]:
        return ((ONE, Rerolled(self.data, self.given, self.changed)),)

    @property
    def fractures(self) -> bool:
        return False

    def chance_all(self, mod_ids: Iterable[str]) -> Fraction:
        """1 when the item holds all of `mod_ids` (they stay), 0 when it does not or two share a family."""
        wanted = set(mod_ids)
        unknown = sorted(wanted - self.data.mods.keys())
        if unknown:
            raise ValueError(f"mod {unknown[0]} is not in the game data")
        mods = [self.data.mods[mod_id] for mod_id in sorted(wanted)]
        if any(conflicts(a, b) for index, a in enumerate(mods) for b in mods[index + 1 :]):
            return Fraction(0)
        return ONE if wanted <= {entry.mod_id for entry in self.given.mods} else Fraction(0)

    def distribution(self, label: Callable[[Mod], Hashable]) -> Mapping[Outcome, Fraction]:
        """No mod is new: one empty outcome of probability 1, whatever the label."""
        return {frozenset(): ONE}

    def sample(self, rng: random.Random) -> Item:
        """The item with every changed mod's values rolled (each stat uniform over its range); the rest as it was."""
        mods = tuple(
            replace(entry, values=roll_values(rng, self.data.mods[entry.mod_id]))
            if (entry.mod_id, entry.fractured, entry.crafted) in self.changed
            else entry
            for entry in self.given.mods
        )
        return self.given.changed(self.data, mods=mods)


@dataclass(frozen=True)
class DivineOrb(Action):
    """One Divine Orb."""

    def label(self, data: GameData | None = None) -> str:
        return "Divine Orb"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        # exactly the claims this file cites: the helpers it imports (`draw`, `metamods`) hold the rules of other actions
        return CLAIMS

    def reads(self, data: GameData) -> Reads:
        # It reads how many mods there are per side (the junk stays, as a state of counts), no family by name and no
        # pool weight; `rerolls_values` makes the state tell apart the mods whose roll a requirement looks at.
        return Reads(junk=True, families=frozenset(), rerolls_values=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.rerolling()

    def outcomes(self, data: GameData, item: Item) -> DivineOutcomes:
        """The outcomes of using the orb on `item`: the same mods, the values of the changeable ones rerolled.

        Raises `NotApplicableError` for a normal or a corrupted item and for an item with no mod to change
        (none, or every one fractured or on a side that a lock protects).
        """
        if item.rarity is Rarity.NORMAL:
            raise NotApplicableError("a Divine Orb works on a magic, rare or unique item only, and this item is normal")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Divine Orb")
        locked = locked_sides(data, item)
        changed = frozenset(
            (entry.mod_id, entry.fractured, entry.crafted)
            for entry in item.mods
            if not entry.fractured and not on_locked_side(data, entry, locked)
        )
        if not changed:
            raise NotApplicableError(
                "a Divine Orb cannot be used here: the item has no mod that is not fractured "
                "and not on a locked side to reroll"
            )
        return DivineOutcomes(data, item, changed)


@kind("divine-orb", order=87)
def _divine_orb(data: GameData, item: Item):
    if item.rarity is not Rarity.NORMAL:
        yield DivineOrb()
