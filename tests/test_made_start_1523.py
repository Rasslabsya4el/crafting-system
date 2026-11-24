"""A bought Shaper/Elder start item is made by its recipe, an Awakener's Orb on two single-influence Normal bases (ticket #1523, OR-7, OR-16).

R20 starts from a Rare Shaper/Elder Eternal Burgonet whose mods the target does not name. No market line prices it: the guide makes it with an
Awakener's Orb from two single-influence helmets. The orb refuses a Normal item and an item with no influenced mod (ADR-0032), so each is a
Rare helmet of its influence holding a mod of that influence; the action of the catalog takes such a pair and gives a Rare Shaper/Elder helmet. The plan's start is that recipe, each good at its own price (`planner._made_start`), and the
route page's step 1 says what is bought, what the orb does and what it costs. The numbers below are worked by hand: 4 + 6 + 100 = 110 Chaos.
These run on the real 3.29.3.3 dump through the planner's entry and skip without it.
"""

import dataclasses
import datetime

import pytest
from abstraction_support import real_game_data

import crafting_system.cli  # noqa: F401  (names the page as the presenter of plans, #882)
from crafting_system.actions.errors import NotApplicableError
from crafting_system.actions.awakener import AwakenersOrb, _low_values, influence_mods
from crafting_system.cli._price_marks import price_uses
from crafting_system.items import ExplicitMod, Influence, Item, Rarity
from crafting_system.cli._route_view import build_section, route_input
from crafting_system.planner import RESTART, PlanError, PlanSettings, plan_target
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.targets import parse_target

SHAPER = "Eternal Burgonet (ilvl 86, Shaper), Rare with a Shaper mod"
ELDER = "Eternal Burgonet (ilvl 86, Elder), Rare with an Elder mod"
ORB = "Awakener's Orb"
HELMET = "Metadata/Items/Armours/Helmets/HelmetStr11"
LINE = "Eternal Burgonet, item level 86-100, Shaper/Elder influence"  # the key of the dual-influenced helmet itself
TARGET = """\
base: Eternal Burgonet
item_level: 86
influence: [shaper, elder]
requirements:
  - family: IncreasedLife
start_item:
  rarity: rare
start: bought
"""
SETTINGS = PlanSettings(methods=("chaos-orb",))


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def target(data):
    return parse_target(TARGET, data)


def prices(**lines: float) -> PriceFile:
    hand = {SHAPER: 4.0, ELDER: 6.0, ORB: 100.0}
    hand.update(lines)
    entries = {name: PriceEntry(chaos, "hand", None, None) for name, chaos in hand.items() if chaos is not None}
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 200.0, entries)


@pytest.fixture(scope="module")
def plan(data, target):
    return plan_target(data, target, prices(), SETTINGS)


def test_the_start_is_the_two_helmets_and_the_orb_each_at_its_own_price(plan):
    start = plan.start_price
    assert start.chaos == pytest.approx(110.0)  # 4 + 6 + 100
    assert start.made is not None
    assert start.made.goods == ((SHAPER, 1, 4.0, "hand"), (ELDER, 1, 6.0, "hand"), (ORB, 1, 100.0, "hand"))
    assert (start.made.receiver, start.made.donor) == (SHAPER, ELDER)
    restart = next(priced for priced in plan.offers if priced.label == RESTART)
    assert restart.cost == pytest.approx(110.0) and restart.parts == start.made.goods  # a restart makes it again from the same goods


def test_the_page_s_step_1_buys_the_goods_and_uses_the_orb(data, plan):
    row = build_section(route_input(plan), data).rows[0]
    assert row.title == "Make a Shaper/Elder Eternal Burgonet, item level 86, with an Awakener's Orb"
    fields = {field.label: [line.text for line in field.lines] for field in row.fields}
    assert "Trade" not in fields  # no trade link for a helmet the market has no line for
    assert len(fields["Buy"]) == 3
    assert fields["Buy"][0].startswith(f"1 × {SHAPER} 4")
    assert fields["Buy"][1].startswith(f"1 × {ELDER} 6")
    assert fields["Buy"][2].startswith("1 × Awakener's Orb 100")
    assert "becomes a Rare item with both influences" in fields["Use"][0] and "keeps one influenced mod of each helmet" in fields["Use"][0]
    assert "without the two kept influenced mods" in fields["Note"][0]  # what the plan reads of the made item, said (OR-23)
    assert fields["Cost per use"][0].startswith("110")
    assert row.cost == pytest.approx(110.0)


def test_the_price_list_names_each_good_and_counts_the_first_one_bought(plan):
    uses = {use.name: use for use in price_uses(plan, plan.view_policy, all_uses=True)}
    assert {SHAPER, ELDER, ORB} <= set(uses) and LINE not in uses
    assert [name for name in uses][:3] == [SHAPER, ELDER, ORB]
    for name in (SHAPER, ELDER, ORB):
        assert uses[name].uses is not None and uses[name].uses >= 1.0  # the first item is made once, before any restart


def test_a_cheaper_market_line_for_the_dual_helmet_wins_and_a_dearer_one_does_not(data, target):
    cheaper = plan_target(data, target, prices(**{LINE: 80.0}), SETTINGS)
    assert cheaper.start_price.made is None and cheaper.start_price.chaos == pytest.approx(80.0)
    dearer = plan_target(data, target, prices(**{LINE: 150.0}), SETTINGS)
    assert dearer.start_price.made is not None and dearer.start_price.chaos == pytest.approx(110.0)


def test_no_recipe_without_a_price_for_every_good_and_none_for_one_influence(data, target):
    with pytest.raises(PlanError, match="no price for the start item"):
        plan_target(data, target, prices(**{ELDER: None}), SETTINGS)
    single = dataclasses.replace(target, influences=frozenset(sorted(target.influences)[:1]))
    with pytest.raises(PlanError, match="no price for the start item"):
        plan_target(data, single, prices(), SETTINGS)


def test_the_catalog_s_orb_takes_the_two_rare_helmets_and_refuses_normal_ones(data):
    # the recipe the page prescribes is one the game takes: a Rare Shaper helmet with a Shaper mod receives an Elder donor's mod (ADR-0032)
    shaper_mod = influence_mods(data, HELMET, 86, Influence.SHAPER)[0]
    elder_mod = influence_mods(data, HELMET, 86, Influence.ELDER)[0]
    orb = AwakenersOrb(HELMET, 86, Influence.ELDER, elder_mod)
    receiver = Item.build(data, base_id=HELMET, item_level=86, rarity=Rarity.RARE, mods=(ExplicitMod(shaper_mod, _low_values(data, shaper_mod)),),
                          influences=frozenset({Influence.SHAPER}))  # fmt: skip
    for _, part in orb.outcomes(data, receiver).components:
        assert part.retained.rarity is Rarity.RARE and part.retained.influences == {Influence.SHAPER, Influence.ELDER}
        assert {entry.mod_id for entry in part.retained.mods} == {shaper_mod, elder_mod}  # one influenced mod of each is kept
    normal = Item.build(data, base_id=HELMET, item_level=86, rarity=Rarity.NORMAL, influences=frozenset({Influence.SHAPER}))
    with pytest.raises(NotApplicableError):
        orb.outcomes(data, normal)


def test_the_json_and_text_reports_name_the_goods(data, plan):
    from crafting_system.cli._report import build_report, policy_document, render_text

    report = build_report(plan, data)
    text = render_text(report)
    assert f"  1 {SHAPER}: 4" in text and f"  1 {ORB}: 100" in text
    made = policy_document(report)["start"]["made_by"]
    assert made["recipe"] == ORB and [good["name"] for good in made["goods"]] == [SHAPER, ELDER, ORB]
    assert sum(good["chaos"] for good in made["goods"]) == pytest.approx(110.0)
