"""The vendor-recipe start options on the real 3.29.3.3 dump (ticket #330, ADR-0059).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`; point `CRAFTING_CACHE_DIR` at it) and skip cleanly without it;
CI fetches it. Nothing here solves a hard route: the options are listed (no solver), and the one route planned end to end is R12.

* The step tables agree with the tiers the planner counts: the tier of every step's mod on a real base is the step's `tier_from_top`,
  so "a step that reaches a tier the target accepts" means the same thing to the recipe and to the goal check.
* The B1 routes with a base a recipe takes (R08 to R10 boots, R12 amulet) list their refusals, and with the setting off
  R12 is the report `make_plan` gives, byte for byte.
* The gem recipes (a Minion helmet, a Fire spell-gem wand and staff) list a start item priced by the gem line.
"""

import json
import re
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from cli_support import price_file as r12_prices
from cli_support import read_json
from cli_support import run as run_r12

from crafting_system.cli import StartContext, build_report, make_plan, policy_document, render_text, vendor_recipe_starts
from crafting_system.cli._start_options import gem_price_name
from crafting_system.cli._start_types import CAP_BELOW_ASKED, NO_PRICE, NO_TARGET_MOD, ROLL_NOT_GUARANTEED
from crafting_system.items import ExplicitMod, Rarity, tier_table
from crafting_system.items.vendor_recipes import RECIPES
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.targets import load_target, parse_target

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "examples" / "targets"
LIFEFORCE_PRICE = 0.03458


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def price_lines(**lines: float) -> PriceFile:
    import datetime

    entries = {name.replace("_", " "): PriceEntry(chaos, "fixture") for name, chaos in lines.items()}
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, entries)


def listing(data, target, prices):
    return vendor_recipe_starts(StartContext(data, target, prices))


def slug(item_class: str) -> str:
    return item_class.lower().replace(" ", "_")


def masked(text: str) -> str:
    return re.sub(r"^Run time:.*$", "Run time: <measured>", text, flags=re.MULTILINE)


# --- the step tables and the tiers the goal check counts --------------------------------------------------------------------


def test_the_tier_of_every_step_on_a_real_base_is_the_steps_tier_from_the_top(data):
    checked = 0
    for recipe in RECIPES.values():
        for kind in recipe.base_kinds:
            bases = sorted(
                (base for base in data.base_items.values() if slug(base.item_class) == kind and base.domain == "item" and base.release_state == "released"),
                key=lambda base: base.drop_level,
            )  # fmt: skip
            assert bases, (recipe.id, kind)
            for base in (bases[0], bases[len(bases) // 2], bases[-1]):  # the lowest, a middle and the highest base of the class
                table = tier_table(data, base.id)
                for reading in recipe.readings or (None,):
                    for step in recipe.steps(kind, reading):
                        assert table.get(step.mod_id) == step.tier_from_top, (recipe.id, kind, base.name, step.mod_id)
                        checked += 1
    assert checked > 800


# --- the B1 routes ------------------------------------------------------------------------------------------------------------


def test_r09_asks_the_top_movement_speed_which_the_recipe_cannot_reach_and_says_so(data):
    target = load_target(TARGETS / "r09-life-boots.yaml", data)

    found = listing(data, target, price_lines())

    assert found.candidates == ()
    (refusal,) = found.refused
    assert refusal.reason == CAP_BELOW_ASKED and refusal.recipe == "boots_movement_speed"
    assert "tier 2 from the top (MovementVelocity5" in refusal.detail and "tier 1 or better" in refusal.detail


def test_r10_asks_the_30_percent_boots_so_the_recipe_start_is_an_option_priced_by_its_goods(data):
    target = load_target(TARGETS / "r10-fractured-boots.yaml", data)  # exactly MovementVelocity5, with three other mods
    prices = price_lines(**{"Sorcerer_Boots_(ilvl_84)": 3.0, "Quicksilver_Flask": 1.5, "Orb_of_Augmentation": 0.25})

    (candidate,) = listing(data, target, prices).candidates

    assert candidate.key == "vendor:boots_movement_speed:5"
    assert candidate.item.rarity is Rarity.MAGIC and candidate.item.item_level == 84
    assert candidate.item.mods == (ExplicitMod("MovementVelocity5", 2, (30,)),)  # the tier the target file writes for it by hand
    assert candidate.price == pytest.approx(3.0 + 5 * 1.5 + 5 * 0.25)


def test_a_recipe_start_without_prices_is_refused_not_guessed(data):
    target = load_target(TARGETS / "r10-fractured-boots.yaml", data)

    found = listing(data, target, price_lines())

    assert found.candidates == ()
    (refusal,) = found.refused
    assert refusal.reason == NO_PRICE and "Quicksilver Flask" in refusal.detail and "Sorcerer Boots (ilvl 84)" in refusal.detail


def test_r12_lists_the_chaos_resistance_recipe_as_asked_for_nothing(data):
    target = load_target(TARGETS / "r12-lightning-amulet.yaml", data)

    found = listing(data, target, price_lines())

    assert found.candidates == ()
    assert [(each.recipe, each.reason) for each in found.refused] == [("jewellery_chaos_resistance", NO_TARGET_MOD)]


def test_r13_belt_is_taken_by_no_recipe(data):
    target = load_target(TARGETS / "r13-life-resist-belt.yaml", data)

    found = listing(data, target, price_lines())

    assert (found.candidates, found.refused, found.axes) == ((), (), ())


def test_r12_with_recipe_starts_off_is_the_report_make_plan_gives_byte_for_byte(tmp_path, data, capsys):
    prices = r12_prices(lifeforce=LIFEFORCE_PRICE)

    code, out = run_r12(tmp_path, "--no-recipe-starts", data=data, prices=prices)
    printed = capsys.readouterr().out

    plan = make_plan(data, load_target(TARGETS / "r12-lightning-amulet.yaml", data), prices)
    report = build_report(plan, data)
    expected = json.loads(json.dumps(policy_document(report, None, target_name="r12-lightning-amulet.yaml")))
    document = read_json(out)
    assert code == 0
    assert masked(printed).startswith(masked(render_text(report, target_name="r12-lightning-amulet.yaml")))
    assert "Start options" not in printed and "start_options" not in document
    assert {key: value for key, value in document.items() if key != "timings_seconds"} == {
        key: value for key, value in expected.items() if key != "timings_seconds"
    }


def test_r12_with_recipe_starts_on_gives_the_same_plan_and_names_the_refused_recipe(tmp_path, data, capsys):
    prices = r12_prices(lifeforce=LIFEFORCE_PRICE)

    code, out = run_r12(tmp_path, data=data, prices=prices)
    printed = capsys.readouterr().out

    document = read_json(out)
    plan = make_plan(data, load_target(TARGETS / "r12-lightning-amulet.yaml", data), prices)
    assert code == 0
    assert document["totals"]["mean_cost"]["value"] == plan.risk.mean.value + plan.start_price.chaos
    assert [(each["recipe"], each["reason"]) for each in document["start_options"]["refused"]] == [("jewellery_chaos_resistance", NO_TARGET_MOD)]
    assert "refused (no target mod): no requirement of the target asks for what these recipes make: jewellery_chaos_resistance" in printed


# --- the gem recipes ------------------------------------------------------------------------------------------------------------


def gem_target(data, base: str, stat: str):
    text = f"base: {base}\nitem_level: 84\nrequirements:\n  - stat: \"{stat}\"\n"
    return parse_target(text, data, source="gem.yaml")


def test_a_minion_helmet_is_one_step_priced_by_the_base_and_the_gem_line(data):
    target = gem_target(data, "General's Helmet", "+1 to Level of all Minion Skill Gems")
    gems = gem_price_name(RECIPES["minion_helmet"].steps("helmet")[0].gems)
    prices = price_lines(**{"General's_Helmet_(ilvl_84)": 2.0, gems.replace(" ", "_"): 6.0})

    found = listing(data, target, prices)

    (candidate,) = found.candidates
    assert candidate.recipe == "minion_helmet" and candidate.steps == 0 and candidate.key == "vendor:minion_helmet:1"
    assert candidate.goods == (("General's Helmet (ilvl 84)", 1, 2.0, "fixture"), (gems, 1, 6.0, "fixture"))
    assert candidate.item.mods == (ExplicitMod("GlobalIncreaseMinionSpellSkillGemLevel1", 2, (1,)),)
    assert candidate.price == pytest.approx(8.0)
    assert "vendor.gem_qualification_is_uncorrupted_skill_gems" in candidate.claims
    assert found.refused == ()


def test_a_fire_spell_gem_wand_is_one_step_and_the_other_tags_are_asked_for_nothing(data):
    target = gem_target(data, "Profane Wand", "+1 to Level of all Fire Spell Skill Gems")
    prices = price_lines(**{"Profane_Wand_(ilvl_84)": 1.0, "Vendor_recipe_gems_(fire,_40%_quality)": 4.0})

    found = listing(data, target, prices)

    (candidate,) = found.candidates
    assert candidate.recipe == "spell_gem_fire" and candidate.price == pytest.approx(5.0)
    assert candidate.item.mods == (ExplicitMod("GlobalFireSpellGemsLevel1_", 1, (1,)),)
    refused = {each.recipe: each.reason for each in found.refused}
    assert refused["spell_gem_cold"] == refused["spell_gem_chaos"] == refused["weapon_physical"] == NO_TARGET_MOD
    assert "spell_gem_fire" not in refused


def test_a_staff_gets_plus_two_and_a_plus_three_is_beyond_the_recipe(data):
    gems = "Vendor_recipe_gems_(fire,_40%_quality)"
    prices = price_lines(**{"Eclipse_Staff_(ilvl_84)": 1.0, gems: 4.0})

    two = listing(data, gem_target(data, "Eclipse Staff", "+2 to Level of all Fire Spell Skill Gems"), prices)
    three = listing(data, gem_target(data, "Eclipse Staff", "+3 to Level of all Fire Spell Skill Gems"), prices)

    (candidate,) = two.candidates
    assert candidate.item.mods == (ExplicitMod("GlobalFireSpellGemsLevelTwoHand1__", 3, (2,)),)  # tier 3 from the top on a staff
    assert three.candidates == ()
    assert [(each.recipe, each.reason) for each in three.refused if each.recipe == "spell_gem_fire"] == [("spell_gem_fire", CAP_BELOW_ASKED)]


def test_a_roll_limit_inside_the_range_of_chaos_resistance_is_not_promised(data):
    text = "base: Amethyst Ring\nitem_level: 84\nrequirements:\n  - family: ChaosResistance\n    mod: ChaosResist5\n    min_roll: 28\n"
    prices = price_lines(**{"Amethyst_Ring_(ilvl_84)": 1.0, "Amethyst_Flask": 1.0, "Orb_of_Augmentation": 0.1})

    found = listing(data, parse_target(text, data, source="ring.yaml"), prices)

    assert found.candidates == ()
    assert [(each.recipe, each.reason) for each in found.refused if each.recipe == "jewellery_chaos_resistance"] == [
        ("jewellery_chaos_resistance", ROLL_NOT_GUARANTEED)
    ]


# --- the elemental cap on real wands --------------------------------------------------------------------------------------------


def test_the_real_fire_ladder_is_t3_at_the_wiki_cap_and_t2_at_the_coe_cap(data):
    target = parse_target(
        "base: Profane Wand\nitem_level: 84\nrequirements:\n  - stat: \"Adds # to # Fire Damage\"\n    min_tier: 2\n", data, source="wand.yaml"
    )
    prices = price_lines(**{"Profane_Wand_(ilvl_84)": 1.0, "Ruby_Flask": 1.0, "Orb_of_Augmentation": 0.1})

    found = listing(data, target, prices)

    (candidate,) = [each for each in found.candidates if each.recipe == "weapon_fire"]
    assert candidate.key == "vendor:weapon_fire:9" and candidate.reading_values == ("coe",)
    assert candidate.item.mods[0].mod_id == "LocalAddedFireDamage9" and candidate.item.mods[0].tier == 2
    assert [(each.recipe, each.reason, each.reading_values) for each in found.refused if each.recipe == "weapon_fire"] == [
        ("weapon_fire", CAP_BELOW_ASKED, ("wiki",))
    ]
