"""The vendor recipes' claims and step tables (ticket #329, ADR-0059).

* The ADR is in `docs/adr/` and ADR-0008 and ADR-0043 link to it.
* `vendor.yaml` loads in the rules registry, and every claim in it is cited by some recipe.
* The step tables of the five recipes agree with the research note's numbers: boots movement speed per tier up
  to 30%, weapon flat physical up to T2, flat elemental at both cap readings, chaos resistance up to 26-30%, and
  the gem level +1 (+2 on a staff) of the spell-gem weapon and the minion helmet.
* A recipe asked for a base kind it does not take, a reading it has not got, or an id it has not got, is refused
  with a clear error.
* The tables agree with the pinned dump (skipped when it is not cached; CI fetches it): the mods exist, the
  levels and rolls match and the mod can spawn on a base of every kind the recipe takes.
"""

import re
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.items.vendor_recipes import (
    ELEMENTS,
    GEM_TAGS,
    RECIPES,
    BaseKindError,
    ReadingError,
    UnknownRecipeError,
    cited_claim_ids,
    recipe,
)
from crafting_system.rules import load_registry

ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "docs" / "adr" / "0059-vendor-recipes-are-start-item-sources.md"
LINKING_ADRS = (
    ROOT / "docs" / "adr" / "0008-targets-and-start-items.md",
    ROOT / "docs" / "adr" / "0043-getting-strands-and-the-foulborn-orbs.md",
)
DRAFT = ROOT / "docs" / "research" / "2026-10-31-vendor-claims-draft" / "vendor.yaml"

ONE_HAND_KINDS = ("claw", "dagger", "one_hand_axe", "one_hand_mace", "one_hand_sword", "rune_dagger", "sceptre",
                  "thrusting_one_hand_sword", "wand")  # fmt: skip
TWO_HAND_KINDS = ("bow", "staff", "two_hand_axe", "two_hand_mace", "two_hand_sword", "warstaff")


def summary(steps):
    return [(step.number, step.mod_id, step.tier_from_top, step.roll) for step in steps]


# --- the ADR and the registry ---------------------------------------------------------------------------------


def test_the_adr_is_in_the_folder_and_linked_from_adr_0008_and_adr_0043():
    assert ADR.is_file()
    text = ADR.read_text(encoding="utf-8")
    assert text.startswith("# ")
    for link_to in LINKING_ADRS:
        assert f"]({ADR.name})" in link_to.read_text(encoding="utf-8"), link_to.name
    assert "ADR-0043" in text  # the ADR names the one it amends
    assert "elemental_cap" in text and "approximate" in text


def test_the_adr_records_the_five_decisions():
    text = ADR.read_text(encoding="utf-8")
    for needle in ("start-item source", "outside the solver", "T3", "T2", "base type", "item level", "trade API", "hand price"):
        assert needle in text, needle


def test_vendor_yaml_loads_in_the_registry_and_every_claim_is_cited_by_a_recipe():
    registry = load_registry()
    vendor = {claim_id for claim_id in registry if claim_id.startswith("vendor.")}
    assert vendor, "vendor.yaml is empty"
    assert len(vendor) == 14
    assert cited_claim_ids() == vendor


def test_every_claim_keeps_its_quote_and_source_and_the_approximate_ones_say_why():
    registry = load_registry()
    approximate = set()
    for claim_id, rule in registry.items():
        if not claim_id.startswith("vendor."):
            continue
        assert rule.quote and rule.url.startswith("https://")
        assert rule.patch_verified == "3.29.3.3"
        if rule.approximate:
            approximate.add(claim_id)
            assert rule.approximate_reason
    assert approximate == {
        "vendor.item_level_of_the_result_is_not_settled",
        "vendor.result_keeps_the_input_base_type",
        "vendor.weapon_elemental_damage_tier_up",
        "vendor.gem_qualification_is_uncorrupted_skill_gems",
    }


def test_every_claim_comes_from_the_research_draft_or_is_one_of_the_three_added_ones():
    import yaml

    draft_entries = {entry["id"]: entry for entry in yaml.safe_load(DRAFT.read_text(encoding="utf-8"))["rules"]}
    draft = set(draft_entries)
    registry = load_registry()
    vendor = {claim_id for claim_id in registry if claim_id.startswith("vendor.")}
    added = vendor - draft
    assert added == {
        "vendor.result_keeps_the_input_base_type",
        "vendor.weapon_elemental_damage_tier_up",
        "vendor.gem_qualification_is_uncorrupted_skill_gems",
    }
    for claim_id in vendor & draft:  # the source and the quote of a promoted claim are the research's own
        draft_entry = draft_entries[claim_id]
        assert registry[claim_id].url == draft_entry["url"]
        assert registry[claim_id].source_kind.value == draft_entry["source_kind"]


def test_the_recipe_ids_cover_the_five_recipes():
    assert set(RECIPES) == {
        "boots_movement_speed",
        "weapon_physical",
        "weapon_fire",
        "weapon_cold",
        "weapon_lightning",
        "jewellery_chaos_resistance",
        *(f"spell_gem_{tag}" for tag in GEM_TAGS),
        "minion_helmet",
    }
    for each in RECIPES.values():
        assert each.keeps_item_level and each.keeps_base_type
        assert each.claim_ids and len(set(each.claim_ids)) == len(each.claim_ids)


# --- the step tables ------------------------------------------------------------------------------------------


def test_boots_movement_speed_gives_the_next_tier_per_step_up_to_thirty_per_cent():
    boots = recipe("boots_movement_speed")
    steps = boots.steps("boots")

    assert summary(steps) == [
        (1, "MovementVelocity1", 6, (10, 10)),
        (2, "MovementVelocity2", 5, (15, 15)),
        (3, "MovementVelocity3", 4, (20, 20)),
        (4, "MovementVelocity4", 3, (25, 25)),
        (5, "MovementVelocity5", 2, (30, 30)),
    ]
    for step in steps:
        assert (step.flask, step.augmentations, step.gems) == ("quicksilver_flask", 1, None)
    assert [step.required_level for step in steps] == [1, 15, 30, 40, 55]
    assert boots.base_kinds == ("boots",)
    assert [claim.id for claim in boots.approximate_claims] == [
        "vendor.item_level_of_the_result_is_not_settled",
        "vendor.result_keeps_the_input_base_type",
    ]


@pytest.mark.parametrize("kind", ONE_HAND_KINDS)
def test_weapon_flat_physical_runs_from_t9_to_t2_on_a_one_hand_weapon(kind):
    steps = recipe("weapon_physical").steps(kind)

    assert [step.tier_from_top for step in steps] == [9, 8, 7, 6, 5, 4, 3, 2]
    assert steps[0].mod_id == "LocalAddedPhysicalDamage1"
    assert steps[-1].mod_id == "LocalAddedPhysicalDamage8" and steps[-1].required_level == 65
    assert steps[-1].roll is None  # a two-stat mod: its rolls come from the mod data
    assert {(step.flask, step.augmentations) for step in steps} == {("granite_flask", 1)}


@pytest.mark.parametrize("kind", TWO_HAND_KINDS)
def test_weapon_flat_physical_uses_the_two_hand_ladder_on_a_two_hand_weapon(kind):
    steps = recipe("weapon_physical").steps(kind)

    assert [step.tier_from_top for step in steps] == [9, 8, 7, 6, 5, 4, 3, 2]
    assert steps[0].mod_id == "LocalAddedPhysicalDamageTwoHand1"
    assert steps[-1].mod_id == "LocalAddedPhysicalDamageTwoHand8"


ELEMENT_TOP_RUNG = {"fire": 10, "cold": 10, "lightning": 10}
FLASKS = {"fire": "ruby_flask", "cold": "sapphire_flask", "lightning": "topaz_flask"}


@pytest.mark.parametrize("element", ELEMENTS)
def test_weapon_flat_elemental_is_t3_by_the_wiki_and_t2_by_craft_of_exile(element):
    elemental = recipe(f"weapon_{element}")

    assert elemental.axis == "elemental_cap"
    assert elemental.readings == ("wiki", "coe")  # the plan's reading first
    wiki = elemental.steps("one_hand_sword")
    wiki_explicit = elemental.steps("one_hand_sword", "wiki")
    coe = elemental.steps("one_hand_sword", "coe")

    assert wiki == wiki_explicit
    assert [step.tier_from_top for step in wiki] == [10, 9, 8, 7, 6, 5, 4, 3]
    assert [step.tier_from_top for step in coe] == [10, 9, 8, 7, 6, 5, 4, 3, 2]
    assert coe[: len(wiki)] == wiki  # the other reading is one recipe longer
    assert {(step.flask, step.augmentations) for step in coe} == {(FLASKS[element], 1)}
    assert re.fullmatch(rf"LocalAdded{element.capitalize()}Damage8", wiki[-1].mod_id)
    assert re.fullmatch(rf"LocalAdded{element.capitalize()}Damage9", coe[-1].mod_id)
    assert (wiki[-1].required_level, coe[-1].required_level) in {(62, 74), (63, 75), (63, 74)}


def test_the_fire_cap_levels_are_the_researchs_62_and_74_and_two_hand_has_its_own_ladder():
    fire = recipe("weapon_fire")

    assert [fire.steps("wand", reading)[-1].required_level for reading in ("wiki", "coe")] == [62, 74]
    two_hand = fire.steps("bow", "coe")
    assert two_hand[0].mod_id == "LocalAddedFireDamageTwoHand1"
    assert two_hand[-1].mod_id == "LocalAddedFireDamageTwoHand9"
    assert fire.steps("bow", "wiki")[-1].mod_id == "LocalAddedFireDamageTwoHand8_"


def test_jewellery_chaos_resistance_runs_from_5_10_to_26_30():
    chaos = recipe("jewellery_chaos_resistance")
    for kind in ("ring", "amulet"):
        steps = chaos.steps(kind)
        assert summary(steps) == [
            (1, "ChaosResist1", 6, (5, 10)),
            (2, "ChaosResist2", 5, (11, 15)),
            (3, "ChaosResist3", 4, (16, 20)),
            (4, "ChaosResist4", 3, (21, 25)),
            (5, "ChaosResist5", 2, (26, 30)),
        ]
        assert {(step.flask, step.augmentations) for step in steps} == {("amethyst_flask", 1)}


@pytest.mark.parametrize("tag", GEM_TAGS)
def test_spell_gem_weapon_gives_plus_one_and_plus_two_on_a_staff(tag):
    gems = recipe(f"spell_gem_{tag}")

    for kind in ("wand", "rune_dagger") + (() if tag == "chaos" else ("sceptre",)):
        (step,) = gems.steps(kind)
        assert step.roll == (1, 1) and step.tier_from_top == 1 and step.required_level == 2
        assert (step.flask, step.augmentations) == (None, 0)
        assert (step.gems.tag, step.gems.count_min, step.gems.quality_total) == (tag, 2, 40)
        assert step.gems.kinds == ("skill",) and step.gems.corrupted is False
    (staff,) = gems.steps("staff")
    assert staff.roll == (2, 2) and staff.tier_from_top == 3
    assert staff.mod_id.startswith(f"Global{tag.capitalize()}SpellGemsLevelTwoHand1")


def test_minion_helmet_gives_plus_one_for_two_minion_gems_of_forty_per_cent():
    (step,) = recipe("minion_helmet").steps("helmet")

    assert step.mod_id == "GlobalIncreaseMinionSpellSkillGemLevel1"
    assert (step.roll, step.tier_from_top, step.required_level) == ((1, 1), 2, 14)
    assert (step.gems.tag, step.gems.count_min, step.gems.quality_total) == ("minion", 2, 40)
    assert (step.flask, step.augmentations) == (None, 0)


def test_the_approximate_claims_of_a_gem_recipe_and_an_elemental_recipe_are_named():
    assert [claim.id for claim in recipe("weapon_cold").approximate_claims] == [
        "vendor.weapon_elemental_damage_tier_up",
        "vendor.item_level_of_the_result_is_not_settled",
        "vendor.result_keeps_the_input_base_type",
    ]
    assert "vendor.gem_qualification_is_uncorrupted_skill_gems" in {
        claim.id for claim in recipe("minion_helmet").approximate_claims
    }
    assert "vendor.weapon_elemental_damage_tier_up" not in {
        claim.id for claim in recipe("weapon_physical").approximate_claims
    }


# --- refusals ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("recipe_id", "kind"),
    [
        ("boots_movement_speed", "helmet"),
        ("boots_movement_speed", "Boots"),
        ("weapon_physical", "ring"),
        ("weapon_fire", "boots"),
        ("jewellery_chaos_resistance", "belt"),
        ("spell_gem_fire", "warstaff"),  # the wiki: "Cannot use warstaff or generic dagger"
        ("spell_gem_fire", "dagger"),
        ("spell_gem_chaos", "sceptre"),  # the data has no Mad Lord's for a sceptre
        ("minion_helmet", "boots"),
    ],
)
def test_a_recipe_asked_for_a_base_kind_it_does_not_take_is_refused_with_a_clear_error(recipe_id, kind):
    with pytest.raises(BaseKindError) as refused:
        recipe(recipe_id).steps(kind)

    message = str(refused.value)
    assert recipe_id in message and repr(kind) in message and "it takes:" in message
    assert kind not in recipe(recipe_id).base_kinds


def test_the_error_names_the_base_kinds_the_recipe_takes():
    with pytest.raises(BaseKindError, match="it takes: boots$"):
        recipe("boots_movement_speed").steps("ring")
    with pytest.raises(BaseKindError, match="it takes: amulet, ring$"):
        recipe("jewellery_chaos_resistance").steps("boots")


def test_a_reading_the_recipe_does_not_have_is_refused():
    with pytest.raises(ReadingError, match="no rule axis"):
        recipe("boots_movement_speed").steps("boots", "wiki")
    with pytest.raises(ReadingError, match="elemental_cap"):
        recipe("weapon_fire").steps("wand", "forum")


def test_an_unknown_recipe_is_refused_and_the_ids_are_listed():
    with pytest.raises(UnknownRecipeError, match="boots_movement_speed"):
        recipe("whetstone_physical")


# --- against the pinned dump -------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def slug(item_class: str) -> str:
    return item_class.lower().replace(" ", "_")


def spawns_on(mod, tags) -> bool:
    """Whether the mod can spawn on an item with `tags`: the first spawn weight whose tag the item has decides."""
    for weight in mod.spawn_weights:
        if weight.tag in tags:
            return weight.weight > 0
    return False


def classes_of_kind(data, kind):
    return [base for base in data.base_items.values() if slug(base.item_class) == kind and base.domain == "item"
            and base.release_state == "released"]  # fmt: skip


def all_steps():
    for each in RECIPES.values():
        for kind in each.base_kinds:
            for reading in each.readings or (None,):
                yield each, kind, reading


def test_every_step_names_a_real_mod_with_the_stated_level_and_roll_that_spawns_on_the_kind(data):
    checked = 0
    for each, kind, reading in all_steps():
        bases = classes_of_kind(data, kind)
        assert bases, f"{each.id}: the dump has no released base of kind {kind}"
        for step in each.steps(kind, reading):
            mod = data.mods[step.mod_id]
            assert mod.generation_type in {"prefix", "suffix"}
            assert mod.required_level == step.required_level, (each.id, kind, step.mod_id)
            if step.roll is not None:
                assert len(mod.stats) == 1
                assert (mod.stats[0].min, mod.stats[0].max) == step.roll, (each.id, kind, step.mod_id)
            assert any(spawns_on(mod, set(base.tags)) for base in bases), (each.id, kind, step.mod_id)
            checked += 1
    assert checked > 300


def test_a_chain_climbs_one_rung_of_one_family_at_a_time(data):
    for each, kind, reading in all_steps():
        steps = each.steps(kind, reading)
        if each.kind != "tier_up":
            continue
        levels = [step.required_level for step in steps]
        assert levels == sorted(levels) and len(set(levels)) == len(levels)
        assert len({data.mods[step.mod_id].families for step in steps}) == 1
        assert [step.tier_from_top for step in steps] == sorted((step.tier_from_top for step in steps), reverse=True)
        assert [step.number for step in steps] == list(range(1, len(steps) + 1))


def test_the_tier_counts_agree_with_the_ladders_of_the_data(data):
    """A rung's tier from the top is the number of rungs above it that spawn on the same base, and the ladder
    lengths are the ones `vendor.tier_caps_match_the_datamined_ladders` states."""
    claimed = load_registry()["vendor.tier_caps_match_the_datamined_ladders"].value["ladder_tiers"]
    sample = {"boots_movement_speed": ("boots", "movement_speed"), "jewellery_chaos_resistance": ("ring", "chaos_resistance"),
              "weapon_physical": ("wand", "physical"), "weapon_fire": ("wand", "fire"), "weapon_cold": ("wand", "cold"),
              "weapon_lightning": ("wand", "lightning")}  # fmt: skip
    for recipe_id, (kind, name) in sample.items():
        steps = recipe(recipe_id).steps(kind, "coe" if recipe_id not in ("boots_movement_speed", "jewellery_chaos_resistance", "weapon_physical") else None)
        prefix = re.sub(r"\d+_*$", "", steps[0].mod_id)
        bases = classes_of_kind(data, kind)
        ladder = sorted(
            (mod for mod in data.mods.values() if re.fullmatch(prefix + r"\d+_*", mod.id) and mod.domain == "item"
             and any(spawns_on(mod, set(base.tags)) for base in bases)),
            key=lambda mod: mod.required_level,
        )  # fmt: skip
        assert len(ladder) == claimed[name], recipe_id
        for step in steps:
            place = [mod.id for mod in ladder].index(step.mod_id)
            assert len(ladder) - place == step.tier_from_top, (recipe_id, step.mod_id)
