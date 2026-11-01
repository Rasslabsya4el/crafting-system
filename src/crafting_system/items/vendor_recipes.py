"""The five vendor recipes of v1 as start-item sources: their inputs and step tables (ADR-0059).

A vendor recipe is not an action of a route. It makes a priced start item outside the solver (ADR-0043,
amended): the input base, a bag of ingredients and a chain of steps go in, a Magic item with one mod comes out.
This module only says what goes in at every step and what comes out; the start options built from it and their
prices are tickets #330 and #331.

The tables are read from the claims of `vendor.yaml` (ADR-0004) and hold no number of their own. A tier-up
recipe (boots movement speed, weapon flat damage, jewellery chaos resistance) is a chain: from a Normal base,
one flask and one Orb of Augmentation per step give the next rung of the mod's ladder, up to the cap. A gem
recipe (a spell-gem weapon, a minion helmet) is one step: a Normal base and two or more quality gems of one tag
with 40% quality in all.

Three claims behind the result are `approximate` (ADR-0028), and `Recipe.approximate_claims` names them for the
answer: the item level and the base type of the result are the input's, and the elemental cap is a rule axis of
two readings, `wiki` (T3, the plan's) and `coe` (T2).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from crafting_system.rules import Rule, get_rule

MAGIC_ITEM_WITH_ONE_MOD = get_rule("vendor.recipe_makes_a_new_magic_item_with_one_mod")
REFUSED_ON_FRACTURED_AND_CORRUPTED = get_rule("vendor.refused_on_fractured_and_corrupted_inputs")
ITEM_LEVEL_OF_THE_RESULT = get_rule("vendor.item_level_of_the_result_is_not_settled")
BASE_TYPE_OF_THE_RESULT = get_rule("vendor.result_keeps_the_input_base_type")
MOVEMENT_SPEED_TIER_UP = get_rule("vendor.movement_speed_boots_tier_up")
FLAT_PHYSICAL_TIER_UP = get_rule("vendor.weapon_flat_damage_tier_up")
FLAT_ELEMENTAL_TIER_UP = get_rule("vendor.weapon_elemental_damage_tier_up")
CHAOS_RESISTANCE_TIER_UP = get_rule("vendor.jewellery_chaos_resistance_tier_up")
TIER_CAPS_ON_THE_LADDERS = get_rule("vendor.tier_caps_match_the_datamined_ladders")
SPELL_GEM_WEAPON = get_rule("vendor.spell_gem_level_weapon_recipe")
STAFF_GIVES_PLUS_TWO = get_rule("vendor.staff_spell_gem_recipe_gives_plus_two")
GEM_MODS_IN_THE_DATA = get_rule("vendor.spell_gem_level_mods_in_the_data")
MINION_HELMET = get_rule("vendor.helmet_minion_gem_recipe")
GEM_QUALIFICATION = get_rule("vendor.gem_qualification_is_uncorrupted_skill_gems")

ELEMENTS = ("fire", "cold", "lightning")
GEM_TAGS = ("physical", "fire", "cold", "lightning", "chaos")
COMMON_CLAIMS = (REFUSED_ON_FRACTURED_AND_CORRUPTED, ITEM_LEVEL_OF_THE_RESULT, BASE_TYPE_OF_THE_RESULT)
TIER_UP_CLAIMS = (MAGIC_ITEM_WITH_ONE_MOD, TIER_CAPS_ON_THE_LADDERS, *COMMON_CLAIMS)
GEM_CLAIMS = (GEM_MODS_IN_THE_DATA, GEM_QUALIFICATION, *COMMON_CLAIMS)


class VendorRecipeError(ValueError):
    """A recipe was asked something it does not answer."""


class UnknownRecipeError(VendorRecipeError):
    """No recipe has this id."""


class BaseKindError(VendorRecipeError):
    """The recipe does not take this base kind."""


class ReadingError(VendorRecipeError):
    """The recipe has no rule axis, or not this reading of it."""


@dataclass(frozen=True)
class GemInput:
    """The gems of a gem recipe: at least `count_min` quality gems carrying `tag`, `quality_total` per cent in all."""

    tag: str
    count_min: int
    quality_total: int
    kinds: tuple[str, ...]
    corrupted: bool


@dataclass(frozen=True)
class RecipeStep:
    """One recipe of a chain, counted from 1: what goes in besides the item, and the mod and tier that come out.

    `flask` and `augmentations` are the flask and the Orbs of Augmentation of a tier-up step (a gem step has
    neither); `gems` is the gem input of a gem step. `mod_id` is the mod of the pinned data the item holds after
    the step, `tier_from_top` its tier counted from the top of its ladder (T1 is the best) and `required_level`
    the mod's required level. `roll` is the range of a single-valued mod (movement speed and chaos resistance in
    per cent, a gem mod's level), `None` where the mod has two stats (flat damage) and the rolls come from the
    mod data. Every step after the first takes the Magic item the step before made.
    """

    number: int
    flask: str | None
    augmentations: int
    gems: GemInput | None
    mod_id: str
    tier_from_top: int
    required_level: int
    roll: tuple[int, int] | None


@dataclass(frozen=True)
class Recipe:
    """A recipe: the base kinds it takes, the claims it rests on and its step tables.

    `chains` maps each base kind to its step table at every reading of the recipe's rule axis (`readings`, the
    plan's first; `axis` is `None` and `readings` empty for a recipe with none). The input is Normal (a tier-up
    recipe may also start from a Magic or Rare item that already holds the previous rung, which a start option
    never needs) and neither fractured nor corrupted. The result keeps the input's item level and base type, both
    `approximate`.
    """

    id: str
    name: str
    kind: str
    base_kinds: tuple[str, ...]
    claims: tuple[Rule, ...]
    axis: str | None
    readings: tuple[str, ...]
    chains: Mapping[str, Mapping[str | None, tuple[RecipeStep, ...]]]
    keeps_item_level: bool
    keeps_base_type: bool

    @property
    def claim_ids(self) -> tuple[str, ...]:
        return tuple(rule.id for rule in self.claims)

    @property
    def approximate_claims(self) -> tuple[Rule, ...]:
        """The claims behind this recipe that are marked `approximate`, in the order they are cited."""
        return tuple(rule for rule in self.claims if rule.approximate)

    def steps(self, base_kind: str, reading: str | None = None) -> tuple[RecipeStep, ...]:
        """The step table for `base_kind`, at `reading` of the rule axis (the plan's reading when left out).

        Raises `BaseKindError` for a base kind the recipe does not take and `ReadingError` for a reading the
        recipe's axis does not have (a recipe with no axis takes no reading).
        """
        if base_kind not in self.chains:
            raise BaseKindError(
                f"the vendor recipe {self.id} does not take base kind {base_kind!r}; it takes: {', '.join(self.base_kinds)}"
            )
        by_reading = self.chains[base_kind]
        if self.axis is None:
            if reading is not None:
                raise ReadingError(f"the vendor recipe {self.id} has no rule axis, so it takes no reading (got {reading!r})")
            return by_reading[None]
        chosen = self.readings[0] if reading is None else reading
        if chosen not in by_reading:
            raise ReadingError(
                f"the vendor recipe {self.id} has the rule axis {self.axis} with readings {', '.join(self.readings)}, not {reading!r}"
            )
        return by_reading[chosen]


def _step(
    number: int, flask: str | None, orb: str | None, gems: GemInput | None, rung: Mapping[str, Any], tier: int
) -> RecipeStep:
    roll = rung.get("roll")
    return RecipeStep(
        number=number,
        flask=flask,
        augmentations=0 if orb is None else 1,
        gems=gems,
        mod_id=rung["mod_id"],
        tier_from_top=tier,
        required_level=rung["required_level"],
        roll=None if roll is None else (roll[0], roll[1]),
    )


def _chain(ladder: tuple[Mapping[str, Any], ...], flask: str, orb: str, cap: int) -> tuple[RecipeStep, ...]:
    """The rungs of `ladder` from the lowest while their tier counted from the top is at least `cap`."""
    tiers = [(len(ladder) - place, rung) for place, rung in enumerate(ladder)]
    kept = [(tier, rung) for tier, rung in tiers if tier >= cap]
    return tuple(_step(number, flask, orb, None, rung, tier) for number, (tier, rung) in enumerate(kept, start=1))


def _no_axis(table: Mapping[str, tuple[RecipeStep, ...]]) -> Mapping[str, Mapping[str | None, tuple[RecipeStep, ...]]]:
    return MappingProxyType({kind: MappingProxyType({None: steps}) for kind, steps in table.items()})


def _tier_up_recipe(recipe_id: str, name: str, rule: Rule, ladders: Mapping[str, tuple[Mapping[str, Any], ...]],
                    kinds_of: Mapping[str, tuple[str, ...]], flask: str, cap: int) -> Recipe:
    """A recipe with a fixed cap; `ladders` and `kinds_of` are keyed by ladder name (the base kinds it serves)."""
    orb = rule.value["orb"]
    table = {
        kind: _chain(ladders[ladder_name], flask, orb, cap)
        for ladder_name, kinds in kinds_of.items()
        for kind in kinds
    }
    return Recipe(
        id=recipe_id, name=name, kind="tier_up", base_kinds=tuple(sorted(table)),
        claims=(rule, *TIER_UP_CLAIMS), axis=None, readings=(), chains=_no_axis(table),
        keeps_item_level=ITEM_LEVEL_OF_THE_RESULT.value["result_item_level"] == "input",
        keeps_base_type=BASE_TYPE_OF_THE_RESULT.value["result_base_type"] == "input",
    )  # fmt: skip


def _build_boots() -> Recipe:
    value = MOVEMENT_SPEED_TIER_UP.value
    ladders = {"boots": tuple(value["ladder"])}
    return _tier_up_recipe(
        "boots_movement_speed", "Boots with movement speed", MOVEMENT_SPEED_TIER_UP, ladders,
        {"boots": tuple(value["base_kinds"])}, value["flask"], value["max_tier_from_top"],
    )  # fmt: skip


def _build_chaos_resistance() -> Recipe:
    value = CHAOS_RESISTANCE_TIER_UP.value
    ladders = {"jewellery": tuple(value["ladder"])}
    return _tier_up_recipe(
        "jewellery_chaos_resistance", "Ring or amulet with chaos resistance", CHAOS_RESISTANCE_TIER_UP, ladders,
        {"jewellery": tuple(value["base_kinds"])}, value["flask"], value["max_tier_from_top"],
    )  # fmt: skip


def _build_physical() -> Recipe:
    value = FLAT_PHYSICAL_TIER_UP.value
    ladders = {hand: tuple(value["ladders"][hand]) for hand in ("one_hand", "two_hand")}
    return _tier_up_recipe(
        "weapon_physical", "Weapon with added Physical Damage", FLAT_PHYSICAL_TIER_UP, ladders,
        {hand: tuple(value["base_kinds"][hand]) for hand in ("one_hand", "two_hand")},
        value["flask"], value["max_tier_from_top"],
    )  # fmt: skip


def _build_elemental(element: str) -> Recipe:
    value = FLAT_ELEMENTAL_TIER_UP.value
    entry = value["elements"][element]
    caps = value["max_tier_from_top"]
    readings = (value["plan_reading"], *(name for name in caps if name != value["plan_reading"]))
    table: dict[str, dict[str | None, tuple[RecipeStep, ...]]] = {}
    for hand in ("one_hand", "two_hand"):
        ladder = tuple(entry["ladders"][hand])
        for kind in value["base_kinds"][hand]:
            table[kind] = {
                reading: _chain(ladder, entry["flask"], value["orb"], caps[reading]) for reading in readings
            }
    return Recipe(
        id=f"weapon_{element}", name=f"Weapon with added {element.capitalize()} Damage", kind="tier_up",
        base_kinds=tuple(sorted(table)), claims=(FLAT_ELEMENTAL_TIER_UP, *TIER_UP_CLAIMS),
        axis=value["axis"], readings=readings,
        chains=MappingProxyType({kind: MappingProxyType(by_reading) for kind, by_reading in table.items()}),
        keeps_item_level=ITEM_LEVEL_OF_THE_RESULT.value["result_item_level"] == "input",
        keeps_base_type=BASE_TYPE_OF_THE_RESULT.value["result_base_type"] == "input",
    )  # fmt: skip


def _gem_recipe(recipe_id: str, name: str, kind_claims: tuple[Rule, ...], gems: GemInput,
                mods: Mapping[str, tuple[Mapping[str, Any], ...]]) -> Recipe:
    """A one-step recipe; `mods` maps a base kind to the (one) mod entry it gets from the gem claim."""
    table = {
        base_kind: (
            RecipeStep(
                number=1, flask=None, augmentations=0, gems=gems, mod_id=entry["mod_id"],
                tier_from_top=entry["tier_from_top"], required_level=entry["required_level"],
                roll=(entry["gem_level"], entry["gem_level"]),
            ),
        )
        for base_kind, (entry,) in mods.items()
    }  # fmt: skip
    return Recipe(
        id=recipe_id, name=name, kind="gem", base_kinds=tuple(sorted(table)),
        claims=(*kind_claims, *GEM_CLAIMS), axis=None, readings=(), chains=_no_axis(table),
        keeps_item_level=ITEM_LEVEL_OF_THE_RESULT.value["result_item_level"] == "input",
        keeps_base_type=BASE_TYPE_OF_THE_RESULT.value["result_base_type"] == "input",
    )  # fmt: skip


def _gem_input(tag: str, recipe_value: Mapping[str, Any]) -> GemInput:
    return GemInput(
        tag=tag,
        count_min=recipe_value["gem_count_min"],
        quality_total=recipe_value["gem_quality_total"],
        kinds=tuple(GEM_QUALIFICATION.value["gem_kinds"]),
        corrupted=GEM_QUALIFICATION.value["corrupted_gems"],
    )


def _build_spell_gem(tag: str) -> Recipe:
    recipe_value = SPELL_GEM_WEAPON.value
    entries = GEM_MODS_IN_THE_DATA.value["spell_gem_tags"][tag]
    allowed = set(recipe_value["bases"])
    mods = {
        base_kind: (entries[which],)
        for which in ("one_hand", "staff")
        for base_kind in entries[which]["base_kinds"]
        if base_kind in allowed
    }
    return _gem_recipe(
        f"spell_gem_{tag}", f"Weapon with +1 to {tag.capitalize()} Spell Skill Gems",
        (SPELL_GEM_WEAPON, STAFF_GIVES_PLUS_TWO), _gem_input(tag, recipe_value), mods,
    )  # fmt: skip


def _build_minion_helmet() -> Recipe:
    entry = GEM_MODS_IN_THE_DATA.value["minion_helmet"]
    recipe_value = MINION_HELMET.value
    mods = {base_kind: (entry,) for base_kind in entry["base_kinds"] if base_kind in recipe_value["bases"]}
    return _gem_recipe(
        "minion_helmet", "Helmet with +1 to Minion Skill Gems", (MINION_HELMET,),
        _gem_input(recipe_value["tag"], recipe_value), mods,
    )  # fmt: skip


def _build_all() -> Mapping[str, Recipe]:
    recipes = [_build_boots(), _build_physical(), *(_build_elemental(element) for element in ELEMENTS)]
    recipes += [_build_chaos_resistance(), *(_build_spell_gem(tag) for tag in GEM_TAGS), _build_minion_helmet()]
    return MappingProxyType({recipe.id: recipe for recipe in recipes})


RECIPES: Mapping[str, Recipe] = _build_all()


def recipe(recipe_id: str) -> Recipe:
    """The recipe with this id; `UnknownRecipeError` lists the ids when there is none."""
    try:
        return RECIPES[recipe_id]
    except KeyError:
        raise UnknownRecipeError(f"no vendor recipe {recipe_id!r}; the recipes are: {', '.join(RECIPES)}") from None


def cited_claim_ids() -> frozenset[str]:
    """The ids of every claim some recipe rests on."""
    return frozenset(claim_id for each in RECIPES.values() for claim_id in each.claim_ids)
