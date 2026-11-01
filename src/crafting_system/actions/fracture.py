"""The Fracturing Orb: fractures one explicit mod of a rare item with 4 or more mods, uniformly.

The orb needs a rare item with at least 4 mods that is not influenced, fractured or corrupted
(synthesised and mirrored items are not in the item model). Every explicit mod has the same chance
1/n to be the one fractured (D6 of issue #28), a crafted mod or a metamod included; a fractured crafted
mod stays on the item like any fractured mod (the item model holds it since ticket #68).
"""

from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass, replace
from fractions import Fraction

from crafting_system.data import GameData, Mod
from crafting_system.items import Item, Rarity
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .draw import Outcome
from .errors import NotApplicableError
from .finite import Finite
from .mixture import Fractured

ACCEPTS_RARE_ONLY = get_rule("fracturing_orb.accepts_rare_only")
NEEDS_FOUR_MODS = get_rule("fracturing_orb.needs_four_mods")
REFUSED_ON_INFLUENCED_OR_FRACTURED = get_rule("fracturing_orb.refused_on_influenced_or_fractured")
REFUSED_ON_CORRUPTED = get_rule("fracturing_orb.refused_on_corrupted")
FRACTURES_ONE_MOD_UNIFORMLY = get_rule("fracturing_orb.fractures_one_mod_uniformly")
COST = get_rule("fracturing_orb.cost")

MIN_MODS = 4


@dataclass(frozen=True, eq=False)
class FractureOutcomes(Finite):
    """One result per explicit mod, that mod fractured, each with chance 1/n; `fractures` is True.

    `distribution` shows no new mod (every mod was on the item): the outcome of a result is the one
    pair `(Fractured(label(mod)), 1)` of the mod that was fractured, as for a Fractured Fossil.
    """

    @property
    def fractures(self) -> bool:
        return True

    def distribution(self, label: Callable[[Mod], Hashable]) -> Mapping[Outcome, Fraction]:
        shown: dict[Outcome, Fraction] = {}
        for chance, result in self.results:
            entry = next(entry for entry in result.mods if entry.fractured)
            outcome = frozenset({(Fractured(label(self.data.mods[entry.mod_id])), 1)})
            shown[outcome] = shown.get(outcome, Fraction(0)) + chance
        return shown


@dataclass(frozen=True)
class FracturingOrb(Action):
    """One Fracturing Orb."""

    def label(self, data: GameData | None = None) -> str:
        return "Fracturing Orb"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def reads(self, data: GameData) -> Reads:
        return Reads()

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        # It draws nothing, but the fractured copy of a mod is not a mod "named" in advance: `named` stays None.
        return Adds(draws=False)

    def outcomes(self, data: GameData, item: Item) -> FractureOutcomes:
        """The outcomes of using the orb on `item`: one result per explicit mod, that mod fractured.

        Raises `NotApplicableError` for an item that is not rare, is corrupted, is influenced or has a
        fractured mod, or has fewer than 4 mods. Crafted mods and metamods are candidates like the rest.
        """
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError(f"a Fracturing Orb works on a rare item only, and this item is {item.rarity}")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Fracturing Orb")
        if item.influences or item.fractured_mods:
            raise NotApplicableError("a Fracturing Orb cannot be used on an influenced item or on one that already has a fractured mod")
        if len(item.mods) < MIN_MODS:
            raise NotApplicableError(
                f"a Fracturing Orb needs a rare item with at least {MIN_MODS} mods, and this item has {len(item.mods)}"
            )
        share = Fraction(1, len(item.mods))
        results = tuple(
            (share, item.changed(data, mods=tuple(replace(m, fractured=m is entry) for m in item.mods)))
            for entry in item.mods
        )
        return FractureOutcomes(data, item, results)


@kind(
    "fracturing-orb",
    order=82,
    planner=False,
    why_not="no compressed-state kernel for a fracture of a mod the item already holds yet (#69)",
)
def _fracturing_orb(data: GameData, item: Item):
    if item.rarity is Rarity.RARE:
        yield FracturingOrb()
