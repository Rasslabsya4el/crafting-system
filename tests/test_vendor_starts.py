"""Vendor recipes as priced start options, and the cheapest start wins (ticket #330, ADR-0059).

"Done when" of the ticket, line by line:

1. On a fixture where the target asks for 30% movement speed boots plus two other mods, the plan starts from the recipe-made
   boots and the answer's start price equals the sum of the recipe's inputs at the fixture prices:
   `test_the_plan_starts_from_the_recipe_made_boots_when_that_is_cheapest`.
2. Where the recipe inputs are priced high, the plain start wins and the recipe start is listed as considered:
   `test_dear_goods_leave_the_plain_start_the_winner_and_the_recipe_is_listed_as_planned` and
   `test_goods_dearer_than_the_best_total_are_listed_as_not_planned`.
3. Turning recipe starts off gives the same answer as before the ticket, byte for byte:
   `test_the_setting_off_returns_what_make_plan_returns`, the R12 route through the command (`test_r12_...`), and the real
   routes in `test_vendor_starts_real.py`.
4. The recipe starts considered and refused appear in the plan's explanation, with the reason:
   `test_the_refused_recipes_are_in_the_explanation_with_their_reasons`.

The rest pins the start-option list as a seam for research #337 (a source of priced candidates, each with its source), the elemental
cap as a rule axis with a range, and the setting. The toy game of `vendor_starts_support` has boots and a wand; the planner solves it
in well under a second.
"""

import dataclasses
import json
import re

import pytest
from cli_support import R12, TODAY, read_json
from cli_support import price_file as r12_prices
from cli_support import run as run_r12
from targets_support import DATA
from vendor_starts_support import (
    AUGMENTATION,
    AUGMENTATION_PRICE,
    BASE_PRICE,
    BOOTS_NAME,
    BOOTS_TARGET,
    FLASK_PRICE,
    QUICKSILVER,
    RUBY,
    TOY,
    TOY_BOOTS,
    WAND_TARGET,
    prices,
    toy_target,
)

from crafting_system.cli import (
    PlanError,
    StartCandidate,
    StartContext,
    StartList,
    build_report,
    main,
    make_plan,
    plan_with_starts,
    policy_document,
    render_text,
    vendor_recipe_starts,
)
from crafting_system.cli import _starts as starts_module
from crafting_system.cli._start_options import combine, gem_price_name, good_name
from crafting_system.cli._start_types import (
    CAP_BELOW_ASKED,
    DOMINATED,
    ITEM_LEVEL_TOO_LOW,
    NO_PRICE,
    NO_TARGET_MOD,
    ROLL_NOT_GUARANTEED,
    SOURCE_PLAIN,
    SOURCE_VENDOR_RECIPE,
)
from crafting_system.items import ExplicitMod, Item, Rarity
from crafting_system.items.vendor_recipes import RECIPES
from crafting_system.prices import load_prices, write_price_file
from crafting_system.targets import load_target, parse_target

FIVE_STEPS = BASE_PRICE + 5 * (FLASK_PRICE + AUGMENTATION_PRICE)  # the movement speed recipe to 30%: the base and five rounds of goods
BOOTS_KEY = "vendor:boots_movement_speed:5"
WANT_NO_SPEED = BOOTS_TARGET.replace("  - family: MovementVelocity\n    min_tier: 2\n", "")
ELEMENTAL_CLAIM = "vendor.weapon_elemental_damage_tier_up"
ITEM_LEVEL_CLAIM = "vendor.item_level_of_the_result_is_not_settled"
BASE_TYPE_CLAIM = "vendor.result_keeps_the_input_base_type"


def listing(target, price_file=None, data=TOY) -> StartList:
    return vendor_recipe_starts(StartContext(data, target, price_file if price_file is not None else prices()))


def asking(**changes: str) -> str:
    """The boots target with the movement speed lines changed (`tier` of the tier limit, `ilvl` of the item level)."""
    text = BOOTS_TARGET
    if "tier" in changes:
        text = text.replace("min_tier: 2", f"min_tier: {changes['tier']}")
    if "ilvl" in changes:
        text = text.replace("item_level: 86", f"item_level: {changes['ilvl']}")
    return text


def masked(text: str) -> str:
    """A report without the lines that hold a measured time."""
    return re.sub(r"^Run time:.*$", "Run time: <measured>", text, flags=re.MULTILINE)


def document_of(plan, data=TOY) -> dict:
    document = policy_document(build_report(plan, data), None, target_name="toy.yaml")
    document.pop("timings_seconds")
    return json.loads(json.dumps(document))


# --- the list of start options -------------------------------------------------------------------------------------------


def test_a_target_that_asks_30_percent_movement_speed_lists_the_five_step_boots_priced_by_their_goods():
    found = listing(toy_target())

    (candidate,) = found.candidates
    assert candidate.key == BOOTS_KEY and candidate.source == SOURCE_VENDOR_RECIPE
    assert candidate.recipe == "boots_movement_speed" and candidate.steps == 5
    assert candidate.item == Item.build(
        TOY, base_id=TOY_BOOTS, item_level=86, rarity=Rarity.MAGIC, mods=(ExplicitMod("MovementVelocity5", 2, (30,)),)
    )
    assert candidate.goods == (
        (BOOTS_NAME, 1, BASE_PRICE, "trade-api"),
        (QUICKSILVER, 5, 5 * FLASK_PRICE, "trade-api"),
        (AUGMENTATION, 5, 5 * AUGMENTATION_PRICE, "fixture"),
    )
    assert candidate.price == pytest.approx(FIVE_STEPS) == pytest.approx(sum(part[2] for part in candidate.goods))
    assert candidate.price_source == f"vendor recipe: 1 {BOOTS_NAME} + 5 {QUICKSILVER} + 5 {AUGMENTATION}"
    assert candidate.axis is None and candidate.claims == (ITEM_LEVEL_CLAIM, BASE_TYPE_CLAIM)
    assert found.refused == () and found.axes == ()


def test_only_the_step_counts_that_reach_an_accepted_tier_are_options_and_a_dearer_step_with_the_same_result_is_dominated():
    found = listing(toy_target(asking(tier=4)))  # T4 or better: 20%, 25% or 30% movement speed, steps 3, 4 and 5

    (candidate,) = found.candidates
    assert candidate.key == "vendor:boots_movement_speed:3" and candidate.steps == 3
    assert candidate.price == pytest.approx(BASE_PRICE + 3 * (FLASK_PRICE + AUGMENTATION_PRICE))
    assert candidate.item.mods == (ExplicitMod("MovementVelocity3", 4, (20,)),)
    assert [(each.reason, each.steps) for each in found.refused] == [(DOMINATED, 4), (DOMINATED, 5)]
    assert "3-step start" in found.refused[0].detail and "costs more" in found.refused[0].detail


def test_a_tier_the_cap_does_not_reach_is_refused_with_the_cap_named():
    found = listing(toy_target(asking(tier=1)))  # 35% movement speed: the recipe stops at 30%, T2

    assert found.candidates == ()
    (refusal,) = found.refused
    assert refusal.reason == CAP_BELOW_ASKED and refusal.recipe == "boots_movement_speed"
    assert "tier 2 from the top" in refusal.detail and "MovementVelocity5" in refusal.detail
    assert "family MovementVelocity (tier 1 or better)" in refusal.detail  # what the target asks, not the other requirements
    assert "IncreasedLife" not in refusal.detail


def test_a_target_that_asks_nothing_the_recipe_makes_is_refused_for_no_target_mod():
    found = listing(toy_target(WANT_NO_SPEED))

    assert found.candidates == ()
    (refusal,) = found.refused
    assert refusal.reason == NO_TARGET_MOD and refusal.recipe == "boots_movement_speed"
    assert "10% increased Movement Speed" in refusal.detail  # what the recipe makes, named by its first step


def test_a_k_of_n_requirement_counts_through_its_members():
    text = BOOTS_TARGET.replace(
        "  - family: MovementVelocity\n    min_tier: 2\n",
        "  - at_least: 1\n    of:\n      - family: MovementVelocity\n        min_tier: 2\n      - family: ToyJunkPrefix1\n",
    )

    (candidate,) = listing(toy_target(text)).candidates

    assert candidate.key == BOOTS_KEY


def test_the_item_level_limits_the_steps_to_the_mods_it_allows():
    price_file = prices(base=None, **{"Toy_Boots_(ilvl_35)": BASE_PRICE})
    found = listing(toy_target(asking(tier=5, ilvl=35)), price_file)  # T5 or better is 15% and up; level 35 allows 15% and 20%, not 25% (level 40)

    (candidate,) = found.candidates
    assert candidate.key == "vendor:boots_movement_speed:2"  # the cheapest step that meets the target
    assert candidate.item.item_level == 35 and candidate.price == pytest.approx(BASE_PRICE + 2 * (FLASK_PRICE + AUGMENTATION_PRICE))
    assert [(each.reason, each.steps) for each in found.refused] == [(DOMINATED, 3)]  # the 20% step; the 25% and 30% ones are not options at all


def test_a_step_whose_mod_needs_more_than_the_item_level_is_refused():
    price_file = prices(base=None, **{"Toy_Boots_(ilvl_35)": BASE_PRICE})
    found = listing(toy_target(asking(tier=3, ilvl=35)), price_file)  # T3 or better: 25% and up, which needs level 40

    assert found.candidates == ()
    (refusal,) = found.refused
    assert refusal.reason == ITEM_LEVEL_TOO_LOW
    assert "needs item level 40" in refusal.detail and "item level is 35" in refusal.detail


def test_a_recipe_with_a_missing_price_line_is_refused_with_the_names_that_are_missing():
    found = listing(toy_target(), prices(flask=None, base=None))

    assert found.candidates == ()
    (refusal,) = found.refused
    assert refusal.reason == NO_PRICE
    assert refusal.detail == f"no price for {QUICKSILVER}, {BOOTS_NAME}"  # sorted by name


def test_a_base_no_recipe_takes_lists_nothing_and_says_nothing():
    belt = parse_target("base: Leather Belt\nitem_level: 86\nrequirements:\n  - family: IncreasedLife\n", DATA, source="belt.yaml")

    assert listing(belt, data=DATA) == StartList()


def test_a_roll_the_recipe_does_not_promise_is_refused_and_a_roll_every_roll_meets_is_made_at_its_lowest():
    amulet = "base: Paua Amulet\nitem_level: 84\nrequirements:\n  - family: ChaosResistance\n    min_tier: 2\n    min_roll: {roll}\n"
    price_file = prices(base=None, flask=None, **{"Paua_Amulet_(ilvl_84)": 1.0, "Amethyst_Flask": 2.0})

    straddles = listing(parse_target(amulet.format(roll=28), DATA, source="a.yaml"), price_file, DATA)  # ChaosResist5 rolls 26 to 30
    promised = listing(parse_target(amulet.format(roll=25), DATA, source="a.yaml"), price_file, DATA)

    assert straddles.candidates == ()
    (refusal,) = [each for each in straddles.refused if each.recipe == "jewellery_chaos_resistance"]
    assert refusal.reason == ROLL_NOT_GUARANTEED and "ChaosResist5" in refusal.detail
    (candidate,) = promised.candidates
    assert candidate.key == "vendor:jewellery_chaos_resistance:5"
    assert candidate.item.mods == (ExplicitMod("ChaosResist5", 2, (26,)),)  # the lowest roll of the range meets the limit of 25


def test_a_hand_price_wins_over_the_trade_price_of_a_flask(tmp_path):
    write_price_file(tmp_path / "prices.json", prices())
    (tmp_path / "price_overrides.toml").write_text(f'[prices]\n"{QUICKSILVER}" = 7.0\n', encoding="utf-8")
    loaded = load_prices(tmp_path / "prices.json", tmp_path / "price_overrides.toml")

    (candidate,) = listing(toy_target(), loaded).candidates

    assert (QUICKSILVER, 5, 35.0, "override") in candidate.goods
    assert candidate.price == pytest.approx(BASE_PRICE + 35.0 + 5 * AUGMENTATION_PRICE)


def test_the_goods_of_a_recipe_are_named_as_the_price_file_names_them():
    assert good_name("quicksilver_flask") == "Quicksilver Flask"
    assert good_name("orb_of_augmentation") == "Orb of Augmentation"
    gems = RECIPES["minion_helmet"].steps("helmet")[0].gems
    assert gem_price_name(gems) == "Vendor recipe gems (minion, 40% quality)"


# --- the choice -----------------------------------------------------------------------------------------------------------


def test_the_plan_starts_from_the_recipe_made_boots_when_that_is_cheapest():
    target = toy_target()

    plan = plan_with_starts(TOY, target, prices())

    choice = plan.starts
    assert choice.chosen.key == BOOTS_KEY and choice.chosen.source == SOURCE_VENDOR_RECIPE
    assert plan.target.start_item == choice.chosen.item  # the plan starts from the recipe-made boots
    assert plan.target.start_item.rarity is Rarity.MAGIC and plan.target.start_item.mods[0].mod_id == "MovementVelocity5"
    assert plan.start_price.chaos == pytest.approx(FIVE_STEPS)  # the sum of the recipe's inputs at the fixture prices
    assert plan.start_price.chaos == pytest.approx(sum(part[2] for part in choice.chosen.goods))
    assert plan.start_price.source.startswith("vendor recipe: 1 Toy Boots (ilvl 86) + 5 Quicksilver Flask + 5 Orb of Augmentation")
    by_key = {row.candidate.key: row for row in choice.considered}
    assert by_key[BOOTS_KEY].outcome == "chosen" and by_key["plain"].outcome == "planned"
    assert by_key[BOOTS_KEY].total == pytest.approx(plan.start_price.chaos + plan.mean_remaining)
    assert by_key[BOOTS_KEY].total < by_key["plain"].total
    assert choice.total == by_key[BOOTS_KEY].total and not choice.reading_matters


def test_the_plan_of_the_chosen_start_is_the_plan_make_plan_gives_for_that_item():
    target = toy_target()
    plan = plan_with_starts(TOY, target, prices())

    alone = make_plan(
        TOY, dataclasses.replace(target, start_item=plan.starts.chosen.item), prices(), start_price_of=plan.start_price
    )

    assert alone.mean_remaining == plan.mean_remaining and alone.policy == plan.policy
    assert alone.risk.mean.value == plan.risk.mean.value


def test_the_report_and_the_json_say_what_the_plan_started_from():
    plan = plan_with_starts(TOY, toy_target(), prices())

    text = render_text(build_report(plan, TOY), target_name="toy.yaml")
    document = document_of(plan)

    assert text.isascii()
    assert f"Start item (Boots with movement speed (vendor recipe, 5 steps)): {FIVE_STEPS:,.2f} Chaos [vendor recipe:" in text
    assert "Start options (the cheapest total of start price and expected cost to craft wins" in text
    assert "chosen: Boots with movement speed (vendor recipe, 5 steps)" in text
    assert "hand the vendor: 1 Toy Boots (ilvl 86) = 1.00 [trade-api]; 5 Quicksilver Flask = 10.00 [trade-api]" in text
    assert "planned: the target's own start item" in text
    assert document["start"]["price_chaos"] == pytest.approx(FIVE_STEPS)
    options = document["start_options"]
    assert options["chosen"] == BOOTS_KEY
    chosen = next(each for each in options["options"] if each["key"] == BOOTS_KEY)
    assert chosen["outcome"] == "chosen" and chosen["source"] == SOURCE_VENDOR_RECIPE and chosen["steps"] == 5
    assert [(good["name"], good["count"]) for good in chosen["goods"]] == [(BOOTS_NAME, 1), (QUICKSILVER, 5), (AUGMENTATION, 5)]
    assert chosen["total_chaos"] == pytest.approx(document["totals"]["mean_cost"]["value"])
    assert options["approximate_claims"] == [ITEM_LEVEL_CLAIM, BASE_TYPE_CLAIM]
    assert {each["claim"] for each in document["approximate_inputs"]} == {ITEM_LEVEL_CLAIM, BASE_TYPE_CLAIM}
    assert "vendor.result_keeps_the_input_base_type" in text and "Approximate inputs" in text


def test_dear_goods_leave_the_plain_start_the_winner_and_the_recipe_is_listed_as_planned():
    cheap = plan_with_starts(TOY, toy_target(), prices())
    plain_total = next(row.total for row in cheap.starts.considered if row.candidate.key == "plain")

    plan = plan_with_starts(TOY, toy_target(), prices(flask=60.0))  # the goods cost 303.50 Chaos: under the plain total, over it with the crafting

    assert plan.starts.chosen.key == "plain" and plan.target.start_item == toy_target().start_item
    by_key = {row.candidate.key: row for row in plan.starts.considered}
    assert by_key[BOOTS_KEY].outcome == "planned"  # planned, and it lost
    assert by_key[BOOTS_KEY].candidate.price == pytest.approx(BASE_PRICE + 5 * (60.0 + AUGMENTATION_PRICE))
    assert by_key[BOOTS_KEY].candidate.price < plain_total < by_key[BOOTS_KEY].total
    assert plan.starts.total == pytest.approx(plain_total) and plan.start_price.chaos == 0.0
    text = render_text(build_report(plan, TOY))
    assert "chosen: the target's own start item" in text and "planned: Boots with movement speed (vendor recipe, 5 steps)" in text
    assert "Approximate inputs" not in text  # no recipe start in the answer, no recipe claim listed


def test_goods_dearer_than_the_best_total_are_listed_as_not_planned():
    plan = plan_with_starts(TOY, toy_target(), prices(flask=500.0))

    by_key = {row.candidate.key: row for row in plan.starts.considered}
    assert plan.starts.chosen.key == "plain"
    row = by_key[BOOTS_KEY]
    assert row.outcome == "not planned" and row.total is None
    assert "not below the best total found" in row.note
    assert "not planned: Boots with movement speed (vendor recipe, 5 steps): its start price 2,503.50 Chaos" in render_text(build_report(plan, TOY))


def test_a_tie_goes_to_the_plain_start():
    plain = starts_module.plain_candidate(toy_target(), prices(), None)
    twin = dataclasses.replace(plain, key="twin", source="bought", label="the same item, bought")

    plan = plan_with_starts(TOY, toy_target(), prices(), sources=(lambda context: StartList((twin,)),))

    assert plan.starts.chosen.key == "plain"
    assert {row.candidate.key: row.outcome for row in plan.starts.considered} == {"plain": "chosen", "twin": "planned"}


def test_the_refused_recipes_are_in_the_explanation_with_their_reasons():
    nothing = plan_with_starts(TOY, toy_target(WANT_NO_SPEED), prices())
    capped = plan_with_starts(TOY, toy_target(asking(tier=1)), prices())

    for plan, reason, recipe in ((nothing, NO_TARGET_MOD, "boots_movement_speed"), (capped, CAP_BELOW_ASKED, "boots_movement_speed")):
        assert plan.starts.chosen.key == "plain" and plan.target.start_item == toy_target().start_item
        (refusal,) = plan.starts.refused
        assert (refusal.reason, refusal.recipe) == (reason, recipe)
        assert [each["reason"] for each in document_of(plan)["start_options"]["refused"]] == [reason]
    assert f"refused ({NO_TARGET_MOD}): no requirement of the target asks for what these recipes make: boots_movement_speed" in render_text(build_report(nothing, TOY))
    text = render_text(build_report(capped, TOY))
    assert f"refused: Boots with movement speed (boots_movement_speed): {CAP_BELOW_ASKED}: the recipe stops at tier 2 from the top" in text


def test_the_setting_off_returns_what_make_plan_returns(monkeypatch):
    calls = []
    real = starts_module.make_plan

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(starts_module, "make_plan", spy)
    target = toy_target()

    plan = plan_with_starts(TOY, target, prices(), recipe_starts=False)

    assert len(calls) == 1 and calls[0][0][1] is target and calls[0][1]["start_price"] is None  # one plan, of the target as it is
    assert plan.starts is None
    direct = make_plan(TOY, target, prices())
    assert masked(render_text(build_report(plan, TOY), target_name="t")) == masked(render_text(build_report(direct, TOY), target_name="t"))
    assert document_of(plan) == document_of(direct) and "start_options" not in document_of(plan)


def test_a_target_no_recipe_takes_is_planned_as_before_even_with_the_setting_on(monkeypatch):
    calls = []
    real = starts_module.make_plan
    monkeypatch.setattr(starts_module, "make_plan", lambda *args, **kwargs: calls.append(1) or real(*args, **kwargs))
    belt = parse_target(
        "base: Leather Belt\nitem_level: 86\nstart_item:\n  rarity: rare\n  mods: []\nactions: [chaos-orb]\nrequirements:\n  - family: IncreasedLife\n",
        DATA, source="belt.yaml",
    )

    plan = plan_with_starts(DATA, belt, prices())

    assert len(calls) == 1 and plan.starts is None
    assert "Start options" not in render_text(build_report(plan, DATA))


def test_a_plan_whose_every_start_fails_raises_the_plain_starts_error():
    target = toy_target(BOOTS_TARGET.replace("start_item:", "start_price: Nowhere\nstart_item:"))  # a start price the file lacks

    with pytest.raises(PlanError, match="no price for the start item 'Nowhere'"):
        plan_with_starts(TOY, target, prices(base=None, flask=None))


def test_a_recipe_start_can_win_when_the_plain_start_has_no_price():
    target = toy_target(BOOTS_TARGET.replace("start_item:", "start_price: Nowhere\nstart_item:"))

    plan = plan_with_starts(TOY, target, prices())

    by_key = {row.candidate.key: row for row in plan.starts.considered}
    assert plan.starts.chosen.key == BOOTS_KEY
    assert by_key["plain"].outcome == "failed" and "no price for the start item 'Nowhere'" in by_key["plain"].note


# --- the seam for research #337 ------------------------------------------------------------------------------------------


def bought_boots(price: float) -> StartCandidate:
    """What a bought-item source (research #337) would offer: the same 30% boots, priced by a trade query."""
    item = Item.build(TOY, base_id=TOY_BOOTS, item_level=86, rarity=Rarity.MAGIC, mods=(ExplicitMod("MovementVelocity5", 2, (30,)),))
    return StartCandidate("bought:speed-boots", "bought", "bought 30% boots", item, price, "bought 30% boots", f"a trade query, {price:,.2f} Chaos")


def test_another_source_of_priced_candidates_joins_the_choice_and_can_win():
    seam = plan_with_starts(TOY, toy_target(), prices(), sources=(vendor_recipe_starts, lambda context: StartList((bought_boots(5.0),))))

    assert seam.starts.chosen.key == "bought:speed-boots" and seam.starts.chosen.source == "bought"
    assert seam.start_price.chaos == 5.0 and seam.start_price.source == "a trade query, 5.00 Chaos"
    keys = [row.candidate.key for row in seam.starts.considered]
    assert keys == ["plain", "bought:speed-boots", BOOTS_KEY] and {row.candidate.source for row in seam.starts.considered} == {
        SOURCE_PLAIN, "bought", SOURCE_VENDOR_RECIPE,
    }  # fmt: skip
    by_key = {row.candidate.key: row for row in seam.starts.considered}
    assert by_key[BOOTS_KEY].outcome == "planned" and by_key["bought:speed-boots"].total < by_key[BOOTS_KEY].total  # same item, dearer


def test_a_source_that_offers_a_candidate_with_a_taken_key_is_refused():
    one = StartList((bought_boots(5.0),))

    with pytest.raises(ValueError, match="share a key"):
        combine([one, one])


# --- the cap is a rule axis --------------------------------------------------------------------------------------------


def wand_prices(**more):
    return prices(base=None, flask=None, **{"Toy_Wand_(ilvl_86)": BASE_PRICE, "Ruby_Flask": FLASK_PRICE, **more})


def test_the_elemental_cap_lists_the_ninth_step_at_the_coe_reading_only_and_refuses_it_at_the_wiki_reading():
    found = listing(toy_target(WAND_TARGET), wand_prices())  # T2 fire damage: the wiki stops at T3 (8 steps), Craft of Exile at T2 (9)

    (candidate,) = [each for each in found.candidates if each.recipe == "weapon_fire"]
    assert candidate.key == "vendor:weapon_fire:9" and (candidate.axis, candidate.reading_values) == ("elemental_cap", ("coe",))
    assert candidate.price == pytest.approx(BASE_PRICE + 9 * (FLASK_PRICE + AUGMENTATION_PRICE))
    assert candidate.goods[1] == (RUBY, 9, 9 * FLASK_PRICE, "fixture")
    assert candidate.item.mods == (ExplicitMod("LocalAddedFireDamage9", 2, (90, 180)),)  # a two-stat mod, made at the lowest roll
    assert ELEMENTAL_CLAIM in candidate.claims
    (capped,) = [each for each in found.refused if each.reason == CAP_BELOW_ASKED]
    assert (capped.recipe, capped.axis, capped.reading_values) == ("weapon_fire", "elemental_cap", ("wiki",))
    assert found.axes == (("elemental_cap", ("wiki", "coe")),)
    assert not candidate.exists_in((("elemental_cap", "wiki"),)) and candidate.exists_in((("elemental_cap", "coe"),))


def test_the_answer_shows_the_cheapest_total_at_each_reading_of_the_cap_and_their_range(monkeypatch):
    calls = []
    real = starts_module.make_plan
    monkeypatch.setattr(starts_module, "make_plan", lambda *args, **kwargs: calls.append(args[1].start_item.rarity) or real(*args, **kwargs))

    plan = plan_with_starts(TOY, toy_target(WAND_TARGET), wand_prices())

    choice = plan.starts
    assert choice.chosen.key == "plain" and plan.start_price.chaos == 0.0  # the plan is the wiki reading, where only the plain start reaches T2
    (wiki, coe) = choice.by_reading
    assert (wiki.reading, wiki.key) == ((("elemental_cap", "wiki"),), "plain")
    assert (coe.reading, coe.key) == ((("elemental_cap", "coe"),), "vendor:weapon_fire:9")
    low, high = choice.total_range
    assert (low, high) == (coe.total, wiki.total) and low < high and choice.reading_matters
    assert len(calls) == 2  # the plain start once and the nine-step start once: nothing is planned for each reading again
    assert ELEMENTAL_CLAIM in choice.claims
    text = render_text(build_report(plan, TOY))
    assert "elemental_cap = wiki: " in text and "elemental_cap = coe: " in text and "Cheapest total over the readings:" in text
    assert f"only at elemental_cap = coe" in text and "vendor.weapon_elemental_damage_tier_up" in text
    document = document_of(plan)["start_options"]
    assert document["reading_matters"] and document["total_range_chaos"]["low"] == pytest.approx(low)
    assert [(each["reading"], each["chosen"]) for each in document["by_reading"]] == [
        ({"elemental_cap": "wiki"}, "plain"), ({"elemental_cap": "coe"}, "vendor:weapon_fire:9")
    ]  # fmt: skip


def test_a_tier_both_caps_reach_is_one_start_at_both_readings_and_the_range_is_a_point():
    target = toy_target(WAND_TARGET.replace("min_tier: 2", "min_tier: 3"))

    plan = plan_with_starts(TOY, target, wand_prices())

    choice = plan.starts
    assert choice.chosen.key == "vendor:weapon_fire:8" and choice.chosen.axis is None  # eight steps at either reading
    assert [entry.key for entry in choice.by_reading] == ["vendor:weapon_fire:8"] * 2
    assert not choice.reading_matters and choice.total_range[0] == choice.total_range[1]
    nine = [refusal for refusal in choice.refused if refusal.reason == DOMINATED]
    assert [(each.steps, each.axis, each.reading_values) for each in nine] == [(9, "elemental_cap", ("coe",))]
    assert "Rule axis changes" not in render_text(build_report(plan, TOY))


# --- the setting and the command ----------------------------------------------------------------------------------------


def run_command(tmp_path, *arguments, target=BOOTS_TARGET, data=TOY, price_file=None, env=None):
    path = tmp_path / "toy.yaml"
    path.write_text(target, encoding="utf-8")
    out = tmp_path / "policy.json"
    code = main(
        [str(path), "--json", str(out), *arguments], data=data, prices=price_file if price_file is not None else prices(),
        env=env if env is not None else {}, today=TODAY,
    )  # fmt: skip
    return code, out


def test_the_command_compares_the_start_options_by_default(tmp_path, capsys):
    code, out = run_command(tmp_path)

    document = read_json(out)
    assert code == 0 and document["start_options"]["chosen"] == BOOTS_KEY
    assert document["start"]["price_chaos"] == pytest.approx(FIVE_STEPS)
    assert "chosen: Boots with movement speed" in capsys.readouterr().out


def test_the_flag_no_recipe_starts_turns_them_off(tmp_path, capsys):
    code, out = run_command(tmp_path, "--no-recipe-starts")

    document = read_json(out)
    assert code == 0 and "start_options" not in document
    assert document["start"]["price_chaos"] == 0.0 and "Start options" not in capsys.readouterr().out


def test_the_setting_recipe_starts_false_in_the_config_file_turns_them_off(tmp_path):
    config = tmp_path / "crafting.toml"
    config.write_text("[planner]\nrecipe_starts = false\n", encoding="utf-8")

    code, out = run_command(tmp_path, env={"CRAFTING_CONFIG": str(config)})

    assert code == 0 and "start_options" not in read_json(out)


def test_the_setting_must_be_true_or_false(tmp_path, capsys):
    config = tmp_path / "crafting.toml"
    config.write_text('[planner]\nrecipe_starts = "no"\n', encoding="utf-8")

    code, _ = run_command(tmp_path, env={"CRAFTING_CONFIG": str(config)})

    error = capsys.readouterr().err
    assert code == 1 and "recipe_starts" in error and "true or false" in error


# --- B1 unchanged: R12 through the command -----------------------------------------------------------------------------


def without_timings(document: dict) -> dict:
    return {key: value for key, value in document.items() if key != "timings_seconds"}


def test_r12_with_recipe_starts_off_is_the_report_make_plan_gives_byte_for_byte(tmp_path, capsys):
    code, out = run_r12(tmp_path, "--no-recipe-starts", prices=r12_prices())
    printed = capsys.readouterr().out

    plan = make_plan(DATA, load_target(R12, DATA), r12_prices())
    report = build_report(plan, DATA)
    assert code == 0
    assert masked(printed).startswith(masked(render_text(report, target_name=R12.name)))  # the text, then where the files were written
    expected = json.loads(json.dumps(policy_document(report, None, target_name=R12.name)))
    assert without_timings(read_json(out)) == without_timings(expected)


def test_r12_with_recipe_starts_on_keeps_every_number_and_adds_only_the_explanation(tmp_path):
    code_off, off = run_r12(tmp_path, "--no-recipe-starts", prices=r12_prices())
    document_off = read_json(off)
    code_on, on = run_r12(tmp_path, prices=r12_prices())  # the amulet takes the chaos resistance recipe; the target asks for none of it
    document_on = read_json(on)

    assert code_off == code_on == 0
    explanation = document_on.pop("start_options")
    assert [(refusal["recipe"], refusal["reason"]) for refusal in explanation["refused"]] == [("jewellery_chaos_resistance", NO_TARGET_MOD)]
    assert explanation["chosen"] == "plain" and [row["outcome"] for row in explanation["options"]] == ["chosen"]
    assert without_timings(document_on) == without_timings(document_off)
