"""The single-item beast crafts of 3.29 (ticket #147, rules of issues #88 and #93, ADR-0030).

A beast craft consumes red beasts (priced by name) and rare beasts of any kind: `recipe_resources` turns a
recipe of `beastcraft.recipe_beasts` into the resources of an action, the rare beasts at the setting
`rare_creature_price` (default `beastcraft.any_rare_creature_price`, 1 chaos each). The crafts here are the
Talisman fractures and the aspects; the Wild Bristle Matron and the two side-swap beasts are in `beast_mods`.
Several rules rest on Craft of Exile alone and carry the approximate mark (ADR-0028).
"""

from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from itertools import combinations

from crafting_system.data import GameData, Mod
from crafting_system.items import ExplicitMod, Item, Rarity, Side
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Reads
from .draw import Outcome
from .errors import NotApplicableError, OutOfScopeError
from .finite import Finite
from .fracture import FractureOutcomes
from .mixture import Fractured

RECIPE_BEASTS = get_rule("beastcraft.recipe_beasts")
DEFAULT_BEAST_LEVEL = get_rule("beastcraft.default_beast_level")
ANY_RARE_CREATURE_PRICE = get_rule("beastcraft.any_rare_creature_price")
TALISMAN_FRACTURE = get_rule("beastcraft.talisman_fracture")
TALISMAN_FRACTURE_REFUSED = get_rule("beastcraft.talisman_fracture_refused_on_fractured_or_influenced")
TALISMAN_FRACTURE_UNIFORM = get_rule("beastcraft.talisman_fracture_uniform")
ASPECT_MODS = get_rule("beastcraft.aspect_mods")
ASPECT_NEEDS_OPEN_SUFFIX = get_rule("beastcraft.aspect_needs_open_suffix")

ANY_RARE_CREATURE = "any_rare_creature"  # the key of `recipe_beasts` for the rare beasts of any kind
CHAOS_ORB = "Chaos Orb"  # the price-file name the rare beasts are paid in
TALISMAN_TAG = "talisman"  # the tag of the Talisman bases (bases of the amulet class)
ASPECT_WORDS = {"avian": "Bird", "cat": "Cat", "crab": "Crab", "spider": "Spider"}  # the aspect as it reads in the id of its mod
ASPECT_LEVELS = (20, 30)
CRAFTED_TIER = 1  # the aspect mods have no tier in the data (they never spawn); `Item` needs one, from 1


def recipe_resources(recipe: str, rare_creature_price: int = ANY_RARE_CREATURE_PRICE.value) -> Mapping[str, int]:
    """What one use of `recipe` consumes by price-file name: its named beasts, and the rare beasts as Chaos Orbs."""
    resources: dict[str, int] = {}
    for name, count in RECIPE_BEASTS.value[recipe].items():
        if name == ANY_RARE_CREATURE:
            resources[CHAOS_ORB] = count * rare_creature_price
        else:
            resources[name] = count
    return resources


def aspect_mod_id(aspect: str, level: int) -> str:
    """The id of the suffix that grants the aspect at the level, read from `beastcraft.aspect_mods`."""
    word = ASPECT_WORDS[aspect]
    for mod_id, granted in ASPECT_MODS.value.items():
        if granted == level and mod_id.startswith(f"Grants{word}Aspect"):
            return mod_id
    raise ValueError(f"the claim beastcraft.aspect_mods holds no mod for the aspect {aspect} at level {level}")


def _is_talisman(data: GameData, item: Item) -> bool:
    base = data.base_items.get(item.base_id)
    return base is not None and TALISMAN_TAG in base.tags


@dataclass(frozen=True, eq=False)
class TalismanFractureOutcomes(FractureOutcomes):
    """One result per mod (that mod fractured) or per pair of mods (both fractured), all equally likely; `fractures` is True.

    `distribution` shows no new mod (every mod was on the item): the outcome of a result is the set of
    `(Fractured(label(mod)), count)` of the mods it fractured, the count adding up when two share a label.
    """

    def distribution(self, label: Callable[[Mod], Hashable]) -> Mapping[Outcome, Fraction]:
        shown: dict[Outcome, Fraction] = {}
        for chance, result in self.results:
            counts: dict[Hashable, int] = {}
            for entry in result.mods:
                if entry.fractured:
                    key = Fractured(label(self.data.mods[entry.mod_id]))
                    counts[key] = counts.get(key, 0) + 1
            outcome = frozenset(counts.items())
            shown[outcome] = shown.get(outcome, Fraction(0)) + chance
        return shown


@dataclass(frozen=True)
class TalismanFracture(Action):
    """The beast recipe that fractures one (`count` 1) or two (`count` 2) modifiers of a rare Talisman."""

    count: int
    rare_creature_price: int = ANY_RARE_CREATURE_PRICE.value

    def __post_init__(self) -> None:
        if self.count not in (1, 2):
            raise ValueError(f"a Talisman fracture takes one or two mods, not {self.count}")

    @property
    def _recipe(self) -> str:
        return "fracture_one_talisman" if self.count == 1 else "fracture_two_talisman"

    @property
    def _min_mods(self) -> int:
        return TALISMAN_FRACTURE.value["one" if self.count == 1 else "two"]

    def label(self, data: GameData | None = None) -> str:
        return "Beastcraft Fracture a Talisman Modifier" if self.count == 1 else "Beastcraft Fracture two Talisman Modifiers"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return recipe_resources(self._recipe, self.rare_creature_price)

    def reads(self, data: GameData) -> Reads:
        return Reads()

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        # It draws nothing, but the fractured copy of a mod is not a mod "named" in advance: `named` stays None.
        return Adds(draws=False)

    def outcomes(self, data: GameData, item: Item) -> TalismanFractureOutcomes:
        """The outcomes of the recipe on `item`: one result per mod, or per pair of distinct mods, fractured.

        Raises `NotApplicableError` for an item that is not rare, is corrupted, is influenced, has a
        fractured mod, is not on a Talisman base, or has fewer mods than the recipe needs (4, or 6 for
        two). Every explicit mod counts, crafted mods and metamods included.
        """
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError(f"a Talisman fracture works on a rare item only, and this item is {item.rarity}")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no Talisman fracture")
        if item.influences or item.fractured_mods:
            raise NotApplicableError(
                "a Talisman fracture cannot be used on an influenced item or on one that already has a fractured mod"
            )
        if not _is_talisman(data, item):
            raise NotApplicableError(f"the item is on {item.base_id}, which is not a Talisman base")
        if len(item.mods) < self._min_mods:
            raise NotApplicableError(
                f"fracturing {self.count} mod(s) needs a Talisman with at least {self._min_mods} mods, "
                f"and this item has {len(item.mods)}"
            )
        indices = range(len(item.mods))
        picks = [(index,) for index in indices] if self.count == 1 else list(combinations(indices, 2))
        share = Fraction(1, len(picks))
        results = tuple(
            (share, item.changed(data, mods=tuple(replace(m, fractured=index in pick) for index, m in enumerate(item.mods))))
            for pick in picks
        )
        return TalismanFractureOutcomes(data, item, results)


@kind(
    "talisman-fracture",
    order=83,
    planner=False,
    why_not="no compressed-state kernel for the beast crafts yet (#149)",
)
def _talisman_fractures(data: GameData, item: Item):
    if item.rarity is Rarity.RARE and _is_talisman(data, item):
        yield TalismanFracture(1)
        yield TalismanFracture(2)


@dataclass(frozen=True)
class AspectBeast(Action):
    """The beast recipe that adds the suffix granting an aspect skill, at level 20 or (with The Black Mórrígan) 30."""

    aspect: str
    level: int
    rare_creature_price: int = ANY_RARE_CREATURE_PRICE.value

    def __post_init__(self) -> None:
        if self.aspect not in ASPECT_WORDS:
            raise ValueError(f"the aspect must be one of {sorted(ASPECT_WORDS)}, not {self.aspect!r}")
        if self.level not in ASPECT_LEVELS:
            raise ValueError(f"the aspect level must be one of {ASPECT_LEVELS}, not {self.level!r}")

    @property
    def mod_id(self) -> str:
        return aspect_mod_id(self.aspect, self.level)

    def label(self, data: GameData | None = None) -> str:
        return f"Beastcraft Aspect of the {self.aspect.capitalize()} (level {self.level})"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return recipe_resources(f"aspect_{self.aspect}_{self.level}", self.rare_creature_price)

    def _mod(self, data: GameData) -> Mod:
        mod = data.mods.get(self.mod_id)
        if mod is None:
            raise ValueError(f"the aspect {self.mod_id} is not a mod in the game data")
        return mod

    def reads(self, data: GameData) -> Reads:
        """The craft is refused when an aspect (the family `GrantedSkill`) is on the item, so it tells that family apart."""
        return Reads(junk=True, families=frozenset(self._mod(data).families), block_invariant=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        # an ordinary explicit mod, not a crafted one: the domain of the aspect suffixes is `item`
        return Adds(named=frozenset({self.mod_id}), crafted=False, draws=False, wanted_only=True)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        """The outcome of the recipe on `item`: the aspect suffix added at its lowest values, with probability 1.

        Raises `OutOfScopeError` for a normal or magic item (no admitted rule says what the recipe does
        there) and `NotApplicableError` for a corrupted item, one with no free suffix, or one that holds
        an aspect already (the family `GrantedSkill`). There is no item level gate.
        """
        mod = self._mod(data)
        if item.rarity is not Rarity.RARE:
            raise OutOfScopeError(f"the item is {item.rarity}; no admitted rule says what an aspect craft does to it")
        if item.corrupted:
            raise NotApplicableError("the item is corrupted, and a corrupted item takes no aspect craft")
        side = Side(mod.generation_type)
        if item.free_slots(data, side) <= 0:
            raise NotApplicableError(f"the item has no free {side.value} slot for the aspect {self.mod_id}")
        if item.blocks(data, mod):
            raise NotApplicableError(f"the item holds a mod that shares a family with the aspect {self.mod_id}")
        low = tuple(min(stat.min, stat.max) for stat in mod.stats)
        added = item.add_mod(data, ExplicitMod(mod.id, CRAFTED_TIER, low, crafted=False))
        return Finite(data, item, ((Fraction(1), added),))


@kind(
    "aspect-beast",
    order=84,
    planner=False,
    why_not="offered only when a target names an aspect, and no compressed-state kernel for the beast crafts yet (#149)",
)
def _aspect_beasts(data: GameData, item: Item):
    if item.rarity is not Rarity.RARE:
        return
    for aspect in ASPECT_WORDS:
        for level in ASPECT_LEVELS:
            if aspect_mod_id(aspect, level) in data.mods:
                yield AspectBeast(aspect, level)
