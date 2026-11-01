"""The first step of a plan that starts from a start item made at a vendor: what is handed over, what comes back, what it costs (ADR-0059, ticket #331).

A plan that starts from a vendor recipe does not start from a bought item: before the first state of the policy the owner
makes the item. `first_step(candidate, data, target)` turns the chosen start candidate into that step, in words and numbers,
and the three places that print the plan read it: the text report (`_start_report.first_step_lines`), the JSON
(`_start_report.first_step_document`) and the route view (`_route_view`, row 1). It reads only the candidate and the recipe data,
never the solver, so it works the same for any plan.

* **Hand.** The whole bill, over all recipes of the chain: the Normal base, the flasks, the Orbs of Augmentation, the gems, each
  with its count, its price and where the price came from (the candidate's `goods`, which are the numbers the start price is the
  sum of).
* **Rounds.** A tier-up recipe is a chain: each recipe takes the Magic item the one before made (the first takes the Normal base),
  one flask and one Orb of Augmentation, and gives the next rung of the mod's ladder with its tier. A gem recipe is one round.
* **Gets.** The item the last round gives, as the start card of the route view draws it: the Magic base, its item level, and the one
  mod with its tier. The recipe wipes every other mod of the item it takes, which is why the item has just that mod.

A candidate of another source (the target's own start item, a bought item of research #337) has no first step here:
`first_step` returns None, and that source prints its own start line.
"""

from dataclasses import dataclass

from crafting_system.data import GameData
from crafting_system.items.vendor_recipes import RECIPES, GemInput, Recipe, RecipeStep
from crafting_system.targets import Target

from ._route_card import card_of_item, mod_text
from ._start_options import ORB_OF_AUGMENTATION, base_kind, good_name
from ._start_types import SOURCE_VENDOR_RECIPE, StartCandidate

ROLE_BASE = "base"
ROLE_FLASK = "flask"
ROLE_AUGMENTATION = "augmentation"
ROLE_GEMS = "gems"
GEMS_PREFIX = "Vendor recipe gems"


@dataclass(frozen=True)
class HandGood:
    """One line of the bill: `count` of a good, what it is in words, its price and where the price came from."""

    role: str
    count: int
    name: str  # the name in the price file
    what: str  # in words: "Sorcerer Boots (ilvl 84), a Normal base"
    chaos: float  # for all `count` of them
    price_source: str

    @property
    def label(self) -> str:
        """The good as one line of the bill: "5 Quicksilver Flask"; the gems are one priced set, so they carry no count."""
        return self.what if self.role == ROLE_GEMS else f"{self.count} {self.what}"


@dataclass(frozen=True)
class RecipeRound:
    """One recipe of the chain: what goes in besides the item of the round before, and the mod and tier that come out."""

    number: int
    hand: str  # "1 Quicksilver Flask + 1 Orb of Augmentation"
    gives: str  # "30% increased Movement Speed"
    tier: int  # counted from the top of the mod's ladder, T1 is the best


@dataclass(frozen=True)
class FirstStep:
    """What the owner does before the first state of the policy: the recipes, the bill, the item that comes back, its price."""

    recipe: str
    title: str
    hand: tuple[HandGood, ...]
    rounds: tuple[RecipeRound, ...]
    base: str  # the base type of the item that comes back
    properties: tuple[str, ...]  # "Magic", "item level 84"
    mods: tuple[tuple[str, str], ...]  # (the mod's text, its tier note "T2") of the item that comes back
    roll_note: str  # "" unless the last mod rolls inside a range
    price: float


def _gem_words(gems: GemInput) -> str:
    return f"{gems.count_min} or more uncorrupted skill gems with the {gems.tag.title()} tag, {gems.quality_total}% quality in all (the cheapest set)"


def _hand_of_round(step: RecipeStep) -> str:
    parts = []
    if step.flask:
        parts.append(f"1 {good_name(step.flask)}")
    if step.augmentations:
        parts.append(f"{step.augmentations} {ORB_OF_AUGMENTATION}")
    if step.gems is not None:
        parts.append(_gem_words(step.gems))
    return " + ".join(parts)


def _role(index: int, name: str) -> str:
    if index == 0:
        return ROLE_BASE  # `_start_options._goods` puts the base first
    if name == ORB_OF_AUGMENTATION:
        return ROLE_AUGMENTATION
    return ROLE_GEMS if name.startswith(GEMS_PREFIX) else ROLE_FLASK


def _steps_of(recipe: Recipe, candidate: StartCandidate, kind: str) -> tuple[RecipeStep, ...]:
    reading = candidate.reading_values[0] if candidate.axis is not None else None
    steps = recipe.steps(kind, reading)
    return steps[: candidate.steps] if recipe.kind == "tier_up" else steps[:1]


def first_step(candidate: StartCandidate, data: GameData, target: Target) -> FirstStep | None:
    """The first step of a plan that starts from `candidate`, or None when the candidate is not made at a vendor."""
    if candidate.source != SOURCE_VENDOR_RECIPE or candidate.recipe is None:
        return None
    recipe = RECIPES[candidate.recipe]
    steps = _steps_of(recipe, candidate, base_kind(data, target.base_id))
    base = data.base_items[target.base_id].name
    gems = steps[0].gems
    hand = []
    for index, (name, count, chaos, source) in enumerate(candidate.goods):
        role = _role(index, name)
        what = f"{name}, a Normal base" if role == ROLE_BASE else _gem_words(gems) if role == ROLE_GEMS and gems is not None else name
        hand.append(HandGood(role, count, name, what, chaos, source))
    rounds = tuple(
        RecipeRound(step.number, _hand_of_round(step), mod_text(data.mods[step.mod_id]), step.tier_from_top) for step in steps
    )
    card = card_of_item(data, candidate.item, tiers=True, rolled=False)
    mods = tuple((slot.text, slot.note) for slot in (*card.prefixes, *card.suffixes) if slot.tone in ("mod", "crafted"))
    last = data.mods[steps[-1].mod_id]
    rolls = any(stat.min != stat.max for stat in last.stats)
    roll_note = "the recipe rolls the mod inside that range; the plan counts the lowest roll, which every roll meets" if rolls else ""
    count = len(rounds)
    title = f"Vendor recipe: {recipe.name}, " + (f"{count} recipes in a row" if count > 1 else "1 recipe")
    return FirstStep(recipe.id, title, tuple(hand), rounds, card.name, card.properties, mods, roll_note, candidate.price)
