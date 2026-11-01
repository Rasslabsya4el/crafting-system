"""Listing the start options of a target: the recipe-made start items that can help, priced, and the ones refused (ADR-0059, ticket #330).

A vendor recipe is not an action of a route; it makes a start item (ADR-0059). For a target whose base kind a recipe takes,
`vendor_recipe_starts` lists the Magic items the recipe can make that carry a mod the target asks for, each priced from
its goods, and the recipes it considered and refused, each with the reason. Nothing here solves anything: the planner plans each
option and keeps the cheapest total (`_starts.plan_with_starts`).

* **Which steps are options.** A tier-up recipe is a chain (five recipes in a row for 30% movement speed); the item after
  step `n` carries the `n`-th rung of the mod's ladder. A step is an option when the item it makes meets some requirement of
  the target on its own (`Requirement.is_met_by`: the mod, the tier and the roll limit all hold), so only the step counts that
  reach a tier the target accepts are listed. Among the steps that meet the same requirements only the cheapest is
  planned: a later step costs more and leaves the target the same item, and the report says so (reason `dominated`).
* **Rolls.** A recipe rolls the mod at random inside the rung's range, and a start item is one concrete item. A step is an
  option when it meets the requirement at the lowest roll of its range, which then meets it at every roll; the item is
  made at that roll. A rung whose range straddles the target's roll limit is refused (`roll not guaranteed`).
* **Item level.** The result keeps the input's item level (claim `vendor.item_level_of_the_result_is_not_settled`, `approximate`),
  and a mod needs its required level. A step whose mod needs more than the target's item level is refused.
* **The rule axis.** Each step table is read at every reading of the recipe's axis (the elemental cap: `wiki` T3, `coe` T2). A
  candidate or a refusal says at which values of the axis it holds.
* **Price.** The base is a Normal base priced by `base_price_name` (the result keeps its level and influences), plus the flasks,
  the Orbs of Augmentation and the gems at the price file's lines (a trade price or a hand override on top, as for every
  price). A recipe with a missing line is refused and the names that are missing are listed.

The sources are functions of a `StartContext` that return a `StartList`; a bought-item source (research #337) is another such
function.
"""

import dataclasses
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from crafting_system.data import GameData
from crafting_system.items import ExplicitMod, Item, ItemError, Rarity, tier_table
from crafting_system.items.vendor_recipes import RECIPES, GemInput, Recipe, RecipeStep
from crafting_system.prices import PriceFile, base_price_name
from crafting_system.prices.price_source import DEFAULT_GAP_PERCENT, DEFAULT_PRICE_SOURCE
from crafting_system.rules import rule_by_id
from crafting_system.targets import KOfN, Requirement, Target

from ._plan import leaf_labels
from ._start_types import (
    CAP_BELOW_ASKED,
    DOMINATED,
    INVALID_ITEM,
    ITEM_LEVEL_TOO_LOW,
    MOD_CANNOT_SPAWN,
    NO_PRICE,
    NO_TARGET_MOD,
    ROLL_NOT_GUARANTEED,
    SOURCE_VENDOR_RECIPE,
    Goods,
    RefusedStart,
    StartCandidate,
)

ORB_OF_AUGMENTATION = "Orb of Augmentation"


@dataclass(frozen=True)
class StartContext:
    """What a start source needs: the game data, the target and the prices (hand overrides on top).

    `price_source`, `gap_percent` and `today` are the profile setting of ticket #357: a source that buys an item prices it with
    `prices.price_source.source_price(prices, name, price_source, today, gap_threshold=gap_percent)` and puts the result on
    its candidate (`StartCandidate.sourced`). The recipe source prices goods from the file as before and reads none of them.
    """

    data: GameData
    target: Target
    prices: PriceFile
    price_source: str = DEFAULT_PRICE_SOURCE
    gap_percent: float = DEFAULT_GAP_PERCENT
    today: date | None = None


@dataclass(frozen=True)
class StartList:
    """What one source offers: priced candidates, the options it refused, and the rule axes its candidates read."""

    candidates: tuple[StartCandidate, ...] = ()
    refused: tuple[RefusedStart, ...] = ()
    axes: tuple[tuple[str, tuple[str, ...]], ...] = ()


StartSource = Callable[[StartContext], StartList]


def combine(lists: list[StartList]) -> StartList:
    """The candidates, refusals and rule axes of several sources, in the order given (an axis with two sets of readings is an error)."""
    candidates: list[StartCandidate] = []
    refused: list[RefusedStart] = []
    axes: dict[str, tuple[str, ...]] = {}
    for each in lists:
        candidates.extend(each.candidates)
        refused.extend(each.refused)
        for name, readings in each.axes:
            if axes.setdefault(name, readings) != readings:
                raise ValueError(f"the rule axis {name} has two sets of readings: {axes[name]} and {readings}")
    keys = [candidate.key for candidate in candidates]
    if len(set(keys)) != len(keys):
        raise ValueError(f"two start candidates share a key: {sorted(key for key in set(keys) if keys.count(key) > 1)}")
    return StartList(tuple(candidates), tuple(refused), tuple(sorted(axes.items())))


def base_kind(data: GameData, base_id: str) -> str:
    """The base kind the recipes name: the item class in lower case with underscores ("One Hand Sword" is `one_hand_sword`)."""
    return data.base_items[base_id].item_class.lower().replace(" ", "_")


def leaf_requirements(target: Target) -> tuple[Requirement, ...]:
    """The requirement leaves of the target in the order `leaf_labels` names them (k-of-n members included, depth first)."""
    found: list[Requirement] = []

    def walk(node: Requirement | KOfN) -> None:
        if isinstance(node, KOfN):
            for member in node.of:
                walk(member)
        else:
            found.append(node)

    for requirement in target.requirements:
        walk(requirement)
    return tuple(found)


def good_name(identifier: str) -> str:
    """The price-file name of a good of a recipe: `quicksilver_flask` is "Quicksilver Flask", `orb_of_augmentation` "Orb of Augmentation"."""
    return " ".join(word if word == "of" else word.capitalize() for word in identifier.split("_"))


def gem_price_name(gems: GemInput) -> str:
    """The price line of the cheapest set of quality gems of a gem recipe: "Vendor recipe gems (fire, 40% quality)".

    One line stands for the cheapest set of `count_min` or more uncorrupted skill gems carrying the tag whose quality adds
    up to `quality_total`. The trade-API fetcher writes it when the owner starts it; a hand price in `price_overrides.toml` wins.
    """
    return f"Vendor recipe gems ({gems.tag}, {gems.quality_total}% quality)"


@dataclass(frozen=True)
class _Kept:
    """A step count that is an option: the item that many steps make."""

    number: int
    item: Item


@dataclass(frozen=True)
class _Refusal:
    reason: str
    detail: str
    steps: int = 0


@dataclass(frozen=True)
class _Examined:
    kept: tuple[_Kept, ...]
    refusals: tuple[_Refusal, ...]


def _roll(mod, high: bool) -> tuple[int, ...]:
    return tuple(max(stat.min, stat.max) if high else min(stat.min, stat.max) for stat in mod.stats)


def _start_item(context: StartContext, step: RecipeStep, tier: int, values: tuple[int, ...]) -> Item:
    target = context.target
    return Item.build(
        context.data, base_id=target.base_id, item_level=target.item_level, rarity=Rarity.MAGIC,
        mods=(ExplicitMod(step.mod_id, tier, values),), influences=target.influences,
    )  # fmt: skip


def _touching(data: GameData, steps: tuple[RecipeStep, ...], leaves: tuple[Requirement, ...], labels: tuple[str, ...]) -> tuple[str, ...]:
    """The labels of the requirements that count a mod of the ladder the recipe climbs, at any tier (a cap above the ladder still touches).

    A ladder is the mods of one mod type (the scope of a tier, `items.tiers`); the family is too wide, because the "+N to Level of
    all X Skill Gems" mods of every tag share one family.
    """
    types = {data.mods[step.mod_id].type for step in steps if step.mod_id in data.mods}
    return tuple(
        label
        for leaf, label in zip(leaves, labels, strict=True)
        if any(data.mods[mod_id].type in types for mod_id in leaf.mod_ids if mod_id in data.mods)
    )


def _examine(
    context: StartContext, recipe: Recipe, kind: str, reading: str | None, leaves: tuple[Requirement, ...], labels: tuple[str, ...]
) -> _Examined:
    """Which step counts of `recipe` are options at `reading` of its rule axis, and why none is when none is."""
    data, target = context.data, context.target
    steps = recipe.steps(kind, reading)
    table = tier_table(data, target.base_id)
    signatures: dict[tuple[bool, ...], int] = {}
    kept: list[_Kept] = []
    refusals: list[_Refusal] = []
    too_low: list[RecipeStep] = []
    straddles: list[RecipeStep] = []
    above: list[RecipeStep] = []  # meets the target except that its roll limit is above every roll of the rung
    unlimited = tuple(dataclasses.replace(leaf, min_roll=None) for leaf in leaves)
    cannot_spawn: list[RecipeStep] = []
    for step in steps:
        tier = table.get(step.mod_id)
        if tier is None:
            cannot_spawn.append(step)
            continue
        mod = data.mods[step.mod_id]
        try:
            low = _start_item(context, step, tier, _roll(mod, high=False))
            high = low if _roll(mod, high=True) == _roll(mod, high=False) else _start_item(context, step, tier, _roll(mod, high=True))
        except ItemError as problem:
            refusals.append(_Refusal(INVALID_ITEM, f"step {step.number}: {problem}"))
            continue
        passes = tuple(leaf.is_met_by(low) for leaf in leaves)
        if any(passes):
            if step.required_level > target.item_level:
                too_low.append(step)
            elif passes in signatures:
                refusals.append(
                    _Refusal(DOMINATED, f"it gives the target the same as the {signatures[passes]}-step start and costs more", step.number)
                )
            else:
                signatures[passes] = step.number
                kept.append(_Kept(step.number, low))
        elif any(leaf.is_met_by(high) for leaf in leaves):
            straddles.append(step)
        elif any(leaf.is_met_by(low) for leaf in unlimited):
            above.append(step)
    if kept:
        return _Examined(tuple(kept), tuple(refusals))
    last = steps[-1]
    asked = _touching(data, steps, leaves, labels)
    if not asked:
        first = steps[0].mod_id  # the same at every reading of a rule axis
        made = ((data.mods[first].text if first in data.mods else None) or first).replace("\n", ", ")
        refusals.append(_Refusal(NO_TARGET_MOD, f"no requirement of the target asks for what this recipe makes ({made})"))
    elif too_low:
        step = too_low[0]
        refusals.append(
            _Refusal(
                ITEM_LEVEL_TOO_LOW,
                f"step {step.number} gives {step.mod_id}, which needs item level {step.required_level}; the target's item level is {target.item_level}",
            )
        )  # fmt: skip
    elif straddles:
        step = straddles[0]
        refusals.append(
            _Refusal(
                ROLL_NOT_GUARANTEED,
                f"step {step.number} ({step.mod_id}) rolls inside its range and the target's roll limit lies inside that range, "
                "so the recipe does not promise it",
            )
        )  # fmt: skip
    elif above:
        step = above[-1]
        refusals.append(
            _Refusal(
                ROLL_NOT_GUARANTEED,
                f"the target's roll limit is above every roll of step {step.number} ({step.mod_id}), the last step that has the mod and tier it asks",
            )
        )  # fmt: skip
    elif len(cannot_spawn) == len(steps):
        refusals.append(_Refusal(MOD_CANNOT_SPAWN, f"the mods of this recipe ({last.mod_id} and the others) cannot spawn on this base"))
    else:
        refusals.append(
            _Refusal(
                CAP_BELOW_ASKED,
                f"the recipe stops at tier {last.tier_from_top} from the top ({last.mod_id}, step {last.number}); the target asks {'; '.join(asked)}",
            )
        )  # fmt: skip
    return _Examined((), tuple(refusals))


def _goods(context: StartContext, recipe: Recipe, steps: tuple[RecipeStep, ...]) -> tuple[Goods, tuple[str, ...]]:
    """The priced goods of a recipe made of `steps` and the names the price file lacks."""
    target = context.target
    base = context.data.base_items[target.base_id]
    wanted: list[tuple[str, int]] = [(base_price_name(base.name, target.item_level, [each.value for each in target.influences]), 1)]
    for flask, count in Counter(step.flask for step in steps if step.flask).items():
        wanted.append((good_name(flask), count))
    augmentations = sum(step.augmentations for step in steps)
    if augmentations:
        wanted.append((ORB_OF_AUGMENTATION, augmentations))
    wanted.extend((gem_price_name(step.gems), 1) for step in steps if step.gems is not None)
    goods: list[tuple[str, int, float, str]] = []
    missing: list[str] = []
    for name, count in wanted:
        entry = context.prices.prices.get(name)
        if entry is None:
            missing.append(name)
        else:
            goods.append((name, count, count * entry.chaos, entry.source))
    return tuple(goods), tuple(missing)


def _label(recipe: Recipe, number: int) -> str:
    steps = f", {number} step{'' if number == 1 else 's'}" if recipe.kind == "tier_up" else ""
    return f"{recipe.name} (vendor recipe{steps})"


def _scope(recipe: Recipe, found: list[str | None]) -> tuple[str | None, tuple[str, ...]]:
    """The rule axis and its values a fact holds at: none when it holds at every reading of the recipe's axis."""
    if recipe.axis is None or len(found) == len(recipe.readings):
        return None, ()
    return recipe.axis, tuple(value for value in found if value is not None)


def vendor_recipe_starts(context: StartContext) -> StartList:
    """The recipe-made start items that can help the target, priced, and the recipes refused with their reasons.

    Only the recipes that take the target's base kind are considered. For a recipe with a rule axis the step table is read at
    every reading; a candidate or a refusal that holds at some readings only says which.
    """
    data = context.data
    kind = base_kind(data, context.target.base_id)
    leaves = leaf_requirements(context.target)
    labels = leaf_labels(context.target)
    candidates: list[StartCandidate] = []
    refused: list[RefusedStart] = []
    axes: dict[str, tuple[str, ...]] = {}
    for recipe in RECIPES.values():
        if kind not in recipe.base_kinds:
            continue
        if recipe.axis is not None:
            axes[recipe.axis] = recipe.readings
        items: dict[int, Item] = {}
        counts_at: dict[int, list[str | None]] = {}
        refusals_at: dict[_Refusal, list[str | None]] = {}
        for reading in recipe.readings or (None,):
            result = _examine(context, recipe, kind, reading, leaves, labels)
            for each in result.kept:
                items.setdefault(each.number, each.item)
                counts_at.setdefault(each.number, []).append(reading)
            for refusal in result.refusals:
                refusals_at.setdefault(refusal, []).append(reading)
        for number, found in sorted(counts_at.items()):
            axis, values = _scope(recipe, found)
            steps = recipe.steps(kind, found[0])[:number]
            goods, missing = _goods(context, recipe, steps)
            if missing:
                refused.append(
                    RefusedStart(recipe.id, recipe.name, NO_PRICE, f"no price for {', '.join(sorted(missing))}", axis=axis, reading_values=values)
                )
                continue
            label = _label(recipe, number)
            candidates.append(
                StartCandidate(
                    key=f"vendor:{recipe.id}:{number}", source=SOURCE_VENDOR_RECIPE, label=label, item=items[number],
                    price=sum(part[2] for part in goods), price_name=label,
                    price_source="vendor recipe: " + " + ".join(f"{count} {name}" for name, count, _, _ in goods),
                    goods=goods, recipe=recipe.id, steps=number if recipe.kind == "tier_up" else 0,
                    claims=tuple(rule.id for rule in recipe.approximate_claims), axis=axis, reading_values=values,
                )  # fmt: skip
            )
        for refusal, found in refusals_at.items():
            axis, values = _scope(recipe, found)
            refused.append(
                RefusedStart(recipe.id, recipe.name, refusal.reason, refusal.detail, steps=refusal.steps, axis=axis, reading_values=values)
            )
    return StartList(tuple(candidates), tuple(refused), tuple(sorted(axes.items())))


def claim_reason(claim_id: str) -> str:
    """The reason a claim is marked `approximate` (for the report)."""
    return rule_by_id(claim_id).approximate_reason
