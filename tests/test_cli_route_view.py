"""The route view (ticket #78, piece C): the page model of a plan, the HTML page, golden pages and the CLI line.

Model-level tests read `build_section` directly; golden pages (`tests/golden/*.html`) pin the whole page of
R12 on the fixture data (through the command), of hand-made policies on the fixture belt (an essence, a bench
craft, Remove Crafted Mods, look-alike states that branch) and of given routes on the amulet (a restart with a
trade link, a gap). Expected numbers come from the definitions (`Outcomes.chance_all`, the risk run), not from
the view. The rows are written to be read by the owner, so the golden files are read once by a person too.
"""

import dataclasses
import json
import math
import re
import textwrap
from pathlib import Path
from urllib.parse import unquote

import pytest
from cli_support import R12, TODAY, price_file
from items_support import DATA, roll
from route_view_support import (
    COLD_REQ,
    DAMAGE,
    FRACTURED_COLD,
    HYSTERIA_REQ,
    LIFE,
    START_NAME,
    assert_golden,
    belt,
    crafted_damage,
    hand_input,
)
from targets_support import EXAMPLES

from crafting_system.actions import HarvestReforge
from crafting_system.cli import _route_flow, evaluate_route, main, make_plan, parse_route
from crafting_system.cli._reach import policy_states
from crafting_system.cli._report import build_report
from crafting_system.cli._route_flow import build_flow
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_trade import buy_step
from crafting_system.cli._route_view import (
    Page,
    RouteInput,
    build_section,
    chance_text,
    count,
    given_route_input,
    merge_sections,
    money,
    route_input,
    write_route_page,
)
from crafting_system.prices import load_buy_spec
from crafting_system.prices.trade_stats import parse_trade_stats
from crafting_system.risk import evaluate
from crafting_system.targets import Requirement, load_target, parse_target

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "trade"
SPEC = load_buy_spec(FIXTURES / "r12_buy_spec.yaml")
STATS_FILE = FIXTURES / "stats_excerpt.json"
STATS = parse_trade_stats(json.loads(STATS_FILE.read_text(encoding="utf-8")))
ROUTE = EXAMPLES.parents[0] / "routes" / "r12-lightning-amulet.yaml"
GEM = "GlobalLightningGemLevel1"
GEM_TEXT = "+1 to Level of all Lightning Skill Gems"
DAMAGE_REQ = Requirement("AllDamage", None, frozenset({DAMAGE}))
MODS = tuple(DATA.mods.values())
TRADE_LINK = "https://www.pathofexile.com/trade/search/"


def page_of(*inputs: RouteInput, buy=None) -> str:
    sections = tuple(
        build_section(inp, DATA, buy, prefix="" if k == 0 else "g-", anchor="policy" if k == 0 else "given")
        for k, inp in enumerate(inputs)
    )
    return render_page(Page("Test page", sections))


def lines_of(row, label: str) -> list[str]:
    for field in row.fields:
        if field.label == label:
            return [line.text for line in field.lines]
    return []


def labels_of(row) -> list[str]:
    return [field.label for field in row.fields]


# --- the policies of the tests -----------------------------------------------------------------------------


def chaos_for_life(state, ab):
    return "Chaos Orb"


def essence_for_hysteria(state, ab):
    return "Essence of Hysteria"


def bench_damage(state, ab):
    return "Benchcraft: All Damage"


def remove_then_chaos(state, ab):
    return "Remove Crafted Mods" if state.crafted else "Chaos Orb"


def junk_decides(state, ab):
    """Look-alike states (the life mod absent in both): the essence while there is little junk, else a Chaos Orb."""
    return "Chaos Orb" if len(state.slots) >= 2 else "Essence of Hysteria"


def dead_end_on_junk(state, ab):
    return None if len(state.slots) >= 2 else "Chaos Orb"


def chaos_at_the_start_only(state, ab):
    return "Chaos Orb" if not state.slots else None


START = belt(FRACTURED_COLD, roll("LifeRegeneration1"))
LIFE_GOAL = (COLD_REQ, LIFE)

INPUTS = {
    "essence": lambda: hand_input(belt(FRACTURED_COLD), (COLD_REQ, HYSTERIA_REQ, LIFE), essence_for_hysteria),
    "bench": lambda: hand_input(START, (COLD_REQ, DAMAGE_REQ), bench_damage),
    "remove_crafted_then_chaos": lambda: hand_input(crafted_damage(START), LIFE_GOAL, remove_then_chaos),
    "branch": lambda: hand_input(START, LIFE_GOAL, junk_decides),
    "dead_end": lambda: hand_input(belt(FRACTURED_COLD), LIFE_GOAL, dead_end_on_junk),
}


@pytest.fixture(scope="module")
def r12_plan():
    return make_plan(DATA, load_target(R12, DATA), price_file())


TWO_LEAVES = f"""\
base: Paua Amulet
item_level: 84
requirements:
  - stat: "{GEM_TEXT}"
  - family: LightningResistance
start_item:
  rarity: rare
start_price: R12 start amulet
"""
RESTART_ROUTE = f"""\
name: Restart on a lone gem
rules:
  - when:
      requirements:
        - stat: "{GEM_TEXT}"
          status: passing
        - family: LightningResistance
          status: absent
    do: restart
  - do: Chaos Orb
"""
GAP_ROUTE = f"""\
name: Chaos until the gem
rules:
  - when:
      requirements:
        - stat: "{GEM_TEXT}"
          status: absent
    do: Chaos Orb
"""


@pytest.fixture(scope="module")
def two_leaf_plan():
    return make_plan(DATA, parse_target(TWO_LEAVES, DATA, source="two.yaml"), price_file())


def given(plan, text: str) -> RouteInput:
    route = parse_route(textwrap.dedent(text), plan, DATA, "route.yaml")
    return given_route_input(plan, route, evaluate_route(plan, route, DATA))


# --- the page of R12 -----------------------------------------------------------------------------------------


def test_r12_is_a_buy_and_one_step_that_loops_until_the_gem(r12_plan):
    q = float(HarvestReforge("lightning").outcomes(DATA, r12_plan.target.start_item).chance_all([GEM]))

    section = build_section(route_input(r12_plan), DATA)

    buy, reforge = section.rows
    assert [row.title for row in section.rows] == ["Buy R12 start amulet", "Harvest Reforge Lightning"]
    assert labels_of(buy) == ["Accepts", "Cost per use"]
    assert lines_of(buy, "Cost per use") == ["4 c"]
    assert labels_of(reforge) == ["Goal", "Accepts", "Chance per use", "Cost per use", "Uses on average", "Step cost", "On failure"]
    assert lines_of(reforge, "Goal") == [f"{GEM_TEXT} · T1"]
    (chance,) = lines_of(reforge, "Chance per use")
    assert float(chance.strip("≈%")) / 100 == pytest.approx(q, rel=0.06)
    assert lines_of(reforge, "Cost per use") == ["50 × Primal Crystallised Lifeforce 0.5 c"]
    (uses,) = lines_of(reforge, "Uses on average")
    assert float(uses.strip("≈ ")) == pytest.approx(1 / q, rel=0.01)  # a geometric run
    (failure,) = lines_of(reforge, "On failure")
    assert failure.startswith("nothing gained (") and failure.endswith("): this step again")
    assert reforge.final and not buy.final


def test_the_goal_card_gives_route_mean_p90_and_prices(r12_plan):
    risk = r12_plan.risk

    fields = {field.label: field.lines[0].text for field in build_section(route_input(r12_plan), DATA).goal.fields}

    assert list(fields) == ["Route", "Mean", "9 runs in 10", "Prices"]  # no success line: it is 100%
    assert fields["Route"] == "Cheapest policy of the planner"
    assert fields["Mean"] == f"{money(risk.mean.value + 4.0)} ({risk.mean.value / 300 + 4 / 300:.2g} Divine)"
    assert fields["9 runs in 10"].endswith(" or less") and money(risk.p90.value + 4.0) in fields["9 runs in 10"]
    assert fields["Prices"] == "league Test, fetched 2026-10-30"


def test_the_target_card_of_the_goal_row_is_the_target_item(r12_plan):
    card = build_section(route_input(r12_plan), DATA).goal.target

    assert card.name == "Paua Amulet"
    assert card.prefixes[0].text == GEM_TEXT
    assert card.suffixes[0].text == "+#% to Lightning Resistance" and card.suffixes[0].note == "any tier"


def run_command(tmp_path: Path, *arguments: str, cache: Path | None = None):
    out = tmp_path / "out" / "policy.json"
    cache = cache if cache is not None else tmp_path / "cache"
    code = main(
        [str(R12), "--json", str(out), *arguments],
        data=DATA,
        prices=price_file(),
        env={"CRAFTING_CACHE_DIR": str(cache)},
        today=TODAY,
    )
    return code, out


@pytest.fixture
def stats_cache(tmp_path) -> Path:
    cache = tmp_path / "cache"
    (cache / "trade").mkdir(parents=True)
    document = {"fetched_at": "2026-10-31T00:00:00+00:00", "stats": json.loads(STATS_FILE.read_text(encoding="utf-8"))}
    (cache / "trade" / "stats.json").write_text(json.dumps(document), encoding="utf-8")
    return cache


def test_golden_r12_through_the_command_with_a_buy_spec(tmp_path, stats_cache, capsys):
    code, out = run_command(tmp_path, "--buy-spec", str(FIXTURES / "r12_buy_spec.yaml"), cache=stats_cache)

    assert code == 0
    page = out.parent / "r12-lightning-amulet.route.html"
    assert f"Route view written to {page}" in capsys.readouterr().out
    assert_golden("r12_fixture", page.read_text(encoding="utf-8"))


def test_golden_r12_with_a_given_route_that_is_the_same_draws_one_section(tmp_path, capsys):
    code, out = run_command(tmp_path, "--route", str(ROUTE))

    assert code == 0
    html = (out.parent / "r12-lightning-amulet.route.html").read_text(encoding="utf-8")
    assert_golden("r12_fixture_given_route", html)
    assert "<h2>" not in html and "<nav>" not in html
    ids = re.findall(r' id="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    assert set(re.findall(r'href="#([^"]+)"', html)) <= set(ids)


def test_golden_a_given_route_that_differs_is_a_second_section_with_its_differing_steps(two_leaf_plan):
    policy = build_section(route_input(two_leaf_plan), DATA, anchor="policy")
    drawn = build_section(given(two_leaf_plan, RESTART_ROUTE), DATA, prefix="g-", anchor="given", route_field=False)

    html = render_page(Page("Test page", merge_sections(policy, drawn, "Restart on a lone gem")))

    assert_golden("given_route_differs", html)
    assert html.count("<h2>") == 2 and "<nav>" in html
    ids = re.findall(r' id="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    assert set(re.findall(r'href="#([^"]+)"', html)) <= set(ids)


def test_the_command_writes_the_page_next_to_the_json_and_changes_nothing_else(tmp_path, capsys):
    code, out = run_command(tmp_path / "a")
    plain_text = capsys.readouterr().out
    plain_json = json.loads(out.read_text(encoding="utf-8"))
    code2, out2 = run_command(tmp_path / "b", "--buy-spec", str(FIXTURES / "r12_buy_spec.yaml"))
    text_with = capsys.readouterr().out

    assert code == code2 == 0
    page = out.parent / "r12-lightning-amulet.route.html"
    assert page.exists() and (out2.parent / "r12-lightning-amulet.route.html").exists()
    kept = [line for line in plain_text.splitlines() if not line.startswith(("Run time", "JSON policy", "Route view"))]
    kept_with = [line for line in text_with.splitlines() if not line.startswith(("Run time", "JSON policy", "Route view"))]
    assert kept == kept_with
    plain_json.pop("timings_seconds")
    other = json.loads(out2.read_text(encoding="utf-8"))
    other.pop("timings_seconds")
    assert plain_json == other


def test_without_a_buy_spec_the_buy_step_has_no_trade_field_and_without_the_stat_list_the_mod_is_named(tmp_path):
    run_command(tmp_path / "a")
    run_command(tmp_path / "b", "--buy-spec", str(FIXTURES / "r12_buy_spec.yaml"))  # no stats.json in this cache

    plain = (tmp_path / "a" / "out" / "r12-lightning-amulet.route.html").read_text(encoding="utf-8")
    unresolved = (tmp_path / "b" / "out" / "r12-lightning-amulet.route.html").read_text(encoding="utf-8")

    assert "Trade" not in plain and "http" not in plain
    assert "Accepts" in plain and "fractured: +14% to Lightning Resistance" in plain  # the start item as the target gives it
    assert "not in the link: +#% to Lightning Resistance" in unresolved and TRADE_LINK in unresolved


def test_a_missing_buy_spec_file_is_an_error_not_a_crash(tmp_path, capsys):
    code, _ = run_command(tmp_path, "--buy-spec", str(tmp_path / "nope.yaml"))

    assert code == 1 and "Error:" in capsys.readouterr().err


# --- hand-made policies -------------------------------------------------------------------------------------


def test_golden_an_essence_step_on_the_belt():
    assert_golden("essence", page_of(INPUTS["essence"]()))


def test_golden_a_bench_craft():
    assert_golden("bench_craft", page_of(INPUTS["bench"]()))


def test_golden_remove_crafted_mods_then_chaos():
    assert_golden("remove_crafted_then_chaos", page_of(INPUTS["remove_crafted_then_chaos"]()))


def test_golden_look_alike_states_that_need_different_actions_branch():
    assert_golden("branch", page_of(INPUTS["branch"]()))


def test_the_titles_are_the_exact_actions():
    essence = build_section(INPUTS["essence"](), DATA).rows[1]
    bench = build_section(INPUTS["bench"](), DATA).rows[1]
    removal = build_section(INPUTS["remove_crafted_then_chaos"](), DATA).rows

    assert essence.title == "Essence of Hysteria"
    assert bench.title == f"Benchcraft: {DATA.mods[DAMAGE].text}"
    assert [row.title for row in removal] == [f"Buy {START_NAME}", "Benchcraft: Remove Crafted Mods", "Chaos Orb"]
    assert lines_of(removal[1], "Goal") == ["crafted mods removed"]
    assert lines_of(removal[1], "Chance per use") == []  # one outcome of chance 1 says nothing
    assert lines_of(bench, "Goal") == [f"{DATA.mods[DAMAGE].text} · crafted"]  # the crafted mod, named once


def test_a_bench_row_shows_the_price_of_each_resource_and_the_sum():
    section = build_section(INPUTS["bench"](), DATA)

    assert lines_of(section.rows[1], "Cost per use") == ["1 × Divine Orb 300 c"]
    assert lines_of(section.rows[1], "Step cost") == ["300 c"]
    assert section.rows[1].after.prefixes[0].marks == ("crafted",)


def test_a_policy_taking_one_action_in_look_alike_states_is_one_row_and_two_actions_are_two_rows():
    one = build_section(hand_input(START, LIFE_GOAL, chaos_for_life), DATA)
    two = build_section(INPUTS["branch"](), DATA)

    assert [row.title for row in one.rows] == [f"Buy {START_NAME}", "Chaos Orb"]
    assert [row.title for row in two.rows] == [f"Buy {START_NAME}", "Essence of Hysteria", "Chaos Orb"]


def test_a_miss_into_a_later_numbered_row_reads_under_on_failure_with_its_chance_not_as_a_chance_per_use():
    section = build_section(INPUTS["branch"](), DATA)  # the essence gives life 84% of the time, else the item goes on to the Chaos Orb step

    essence = section.rows[1]
    assert lines_of(essence, "Chance per use") == ["≈84%"]
    failure = [field for field in essence.fields if field.label == "On failure"][0]
    assert failure.tone == "warn"
    assert [(line.text, line.href, line.anchor) for line in failure.lines] == [("the item of step 3 (≈16%)", "#s3", "")]


def test_a_craft_step_with_several_outcomes_says_what_it_accepts_and_a_sure_one_does_not():
    branch = build_section(INPUTS["branch"](), DATA)
    bench = build_section(INPUTS["bench"](), DATA)

    essence, chaos = branch.rows[1], branch.rows[2]
    assert labels_of(essence)[:3] == ["Goal", "Accepts", "Chance per use"]  # between the goal and the chances
    assert lines_of(essence, "Accepts") == ["4 or 5 mods", "other mods: any"]
    assert lines_of(chaos, "Accepts") == ["4 or 5 mods", "other mods: any"]
    assert all("Accepts" not in labels_of(row) for row in bench.rows[1:])  # a bench craft has one outcome


def test_the_route_field_of_the_goal_card_is_left_out_when_the_page_has_a_heading_with_it():
    one = build_section(INPUTS["branch"](), DATA)
    stacked = build_section(INPUTS["branch"](), DATA, route_field=False)

    assert [field.label for field in one.goal.fields][0] == "Route"
    assert "Route" not in [field.label for field in stacked.goal.fields]


def test_the_command_with_a_route_the_same_as_the_policy_draws_it_once_and_says_so(tmp_path):
    code, out = run_command(tmp_path, "--route", str(ROUTE))

    html = (out.parent / "r12-lightning-amulet.route.html").read_text(encoding="utf-8")
    assert code == 0 and html.count("<section") == 1
    assert "Same as the given route (R12, PoE Vault guide)" in html and html.count(">Route<") == 1


def test_a_given_route_the_same_as_the_policy_is_not_drawn_again(r12_plan):
    policy = build_section(route_input(r12_plan), DATA, anchor="policy", route_field=False)
    given_section = build_section(
        given(r12_plan, ROUTE.read_text(encoding="utf-8")), DATA, prefix="g-", anchor="given", route_field=False
    )

    (merged,) = merge_sections(policy, given_section, "the guide")

    assert merged.rows == policy.rows
    assert [field.label for field in merged.goal.fields][:2] == ["Route", "Given route"]
    assert lines_of_card(merged.goal, "Given route") == ["Same as the given route (the guide)"]


def lines_of_card(goal, label: str) -> list[str]:
    return [line.text for field in goal.fields if field.label == label for line in field.lines]


def test_a_given_route_that_differs_is_drawn_with_its_differing_steps_only_and_links_to_the_shared_ones(two_leaf_plan):
    policy = build_section(route_input(two_leaf_plan), DATA, anchor="policy")
    given_section = build_section(
        given(two_leaf_plan, RESTART_ROUTE), DATA, prefix="g-", anchor="given", route_field=False
    )

    drawn, guide = merge_sections(policy, given_section, "restart route")

    assert drawn is policy
    assert [row.number for row in guide.rows] == [row.number for row in given_section.rows if row.number != 1]  # the buy is shared
    assert lines_of_card(guide.goal, "Same as the planner") == ["step 1"]
    (shared,) = [field for field in guide.goal.fields if field.label == "Same as the planner"]
    assert shared.lines[0].href == "#s1"
    hrefs = [line.href for row in guide.rows for field in row.fields for line in field.lines if line.href]
    assert "#g-s1" not in hrefs and all(href.startswith(("#s", "#g-s")) for href in hrefs)
    html = render_page(Page("x", (drawn, guide)))
    assert all(f'id="{anchor}"' in html for anchor in {href[1:] for href in hrefs})


def test_above_the_cap_the_rows_have_no_uses_or_step_costs_and_the_goal_card_says_so(monkeypatch):
    monkeypatch.setattr(_route_flow, "MAX_STEPS", 1)

    section = build_section(INPUTS["branch"](), DATA)

    assert all("Uses on average" not in labels_of(row) and "Step cost" not in labels_of(row) for row in section.rows)
    assert lines_of(section.rows[1], "Cost per use") == ["1 × Essence of Hysteria 3 c"]
    note = [field for field in section.goal.fields if field.label == "Note"][0]
    assert note.lines[0].text.startswith("how often a step is used and what it costs are left out")


@pytest.mark.parametrize("name", INPUTS)
def test_every_reachable_state_is_in_exactly_one_step_and_a_step_has_one_action(name):
    inp = INPUTS[name]()
    plan = inp.plan

    flow = build_flow(plan.start, inp.policy, plan.abstraction.is_goal, inp.reasons)

    reachable = [s for s in policy_states(plan.start, inp.policy, plan.is_goal) if not plan.is_goal(s)]
    assert set(flow.step_of) == set(reachable)
    assert sum(len(step.states) for step in flow.steps) == len(reachable)
    for step in flow.steps:
        assert {inp.policy[s].label for s in step.states if s in inp.policy} <= {step.action.label if step.action else None}
        assert {flow.step_of[s] for s in step.states} == {step.number}
    assert len(build_section(inp, DATA).rows) == len(flow.steps) + 1


@pytest.mark.parametrize("name", ["essence", "bench", "remove_crafted_then_chaos", "branch"])
def test_the_buy_and_the_step_costs_add_up_to_the_risk_mean_and_the_start_price(name):
    inp = INPUTS[name]()
    risk = evaluate(inp.policy, inp.plan.start, inp.plan.is_goal)

    section = build_section(inp, DATA)

    assert sum(row.cost for row in section.rows) == pytest.approx(risk.mean.value + 6.0, rel=1e-9)


def test_the_sum_identity_holds_for_r12_and_for_a_given_route_with_a_restart(r12_plan, two_leaf_plan):
    for inp in (route_input(r12_plan), given(two_leaf_plan, RESTART_ROUTE)):
        section = build_section(inp, DATA)

        assert sum(row.cost for row in section.rows) == pytest.approx(inp.risk.mean.value + 4.0, rel=1e-9)


# --- given routes: a restart and a gap ---------------------------------------------------------------------


def test_golden_a_given_route_with_a_restart_and_a_trade_link(two_leaf_plan):
    buy = buy_step(SPEC, "Test", MODS, STATS)
    assert_golden("restart", page_of(given(two_leaf_plan, RESTART_ROUTE), buy=buy))


def test_a_restart_row_buys_again_and_goes_back_to_the_first_step(two_leaf_plan):
    buy = buy_step(SPEC, "Test", MODS, STATS)

    section = build_section(given(two_leaf_plan, RESTART_ROUTE), DATA, buy)

    (restart,) = [row for row in section.rows if row.title.startswith("Restart")]
    assert restart.title == "Restart: buy R12 start amulet again"
    assert labels_of(restart) == ["Trade", "Cost per use", "Uses on average", "Step cost", "On failure"]
    assert lines_of(restart, "Cost per use") == ["4 c"]
    failure = restart.fields[-1].lines[0]
    assert failure.text.startswith("the start item bought again (100%)") and failure.href == "#s2"
    # a bought rare: the other mods are not known
    assert restart.after.suffixes[0].text == "any mod or empty" and restart.after.properties == ("Rare", "item level 84")
    assert section.goal.fields[0].lines[0].text == "Given route: Restart on a lone gem"


def test_golden_a_gap_of_a_given_route_is_a_row_with_no_action(two_leaf_plan):
    assert_golden("gap", page_of(given(two_leaf_plan, GAP_ROUTE)))


def test_a_gap_row_says_why_and_the_route_never_finishes(two_leaf_plan):
    section = build_section(given(two_leaf_plan, GAP_ROUTE), DATA)

    gap = section.rows[-1]
    assert gap.title == "No action" and labels_of(gap) == ["Why"]
    assert lines_of(gap, "Why") == ["no rule matches this state"]
    mean = {field.label: field.lines[0].text for field in section.goal.fields}["Mean"]
    assert mean == "never finishes: the route has gaps"
    assert "Success chance" in [field.label for field in section.goal.fields]
    assert not any(field.label == "Step cost" for field in gap.fields)


def test_a_step_from_which_no_run_finishes_says_so_without_cost_numbers(two_leaf_plan):
    only_restart = "rules:\n  - do: restart\n"

    section = build_section(given(two_leaf_plan, only_restart), DATA)

    row = section.rows[1]
    assert row.title.startswith("Restart")
    assert lines_of(row, "Uses on average") == ["never finishes from here"]
    assert "Step cost" not in labels_of(row) and row.cost is None
    assert {field.label: field.lines[0].text for field in section.goal.fields}["Mean"] == "never finishes"


def test_a_step_whose_every_exit_is_a_gap_says_it_never_finishes_without_cost_numbers():
    inp = hand_input(belt(FRACTURED_COLD), (COLD_REQ, HYSTERIA_REQ, LIFE), chaos_at_the_start_only)  # a Chaos Orb cannot give the essence mod

    section = build_section(inp, DATA)

    chaos, gap = section.rows[1], section.rows[-1]
    assert chaos.title == "Chaos Orb" and gap.title == "No action"
    assert lines_of(chaos, "Uses on average") == ["never finishes from here"]
    assert "Step cost" not in labels_of(chaos) and chaos.cost is None
    assert {field.label: field.lines[0].text for field in section.goal.fields}["Mean"] == "never finishes"


def test_a_dead_end_of_the_planners_own_policy_is_a_no_action_row_too():
    section = build_section(INPUTS["dead_end"](), DATA)

    assert section.rows[-1].title == "No action"
    assert lines_of(section.rows[-1], "Why") == ["no action is available here"]


def test_a_start_that_already_meets_the_goal_is_the_buy_row_alone():
    inp = hand_input(belt(FRACTURED_COLD), (COLD_REQ,), chaos_for_life)

    section = build_section(inp, DATA)

    assert [row.title for row in section.rows] == [f"Buy {START_NAME}"] and section.rows[0].final


# --- the page ------------------------------------------------------------------------------------------------


def all_pages(r12_plan, two_leaf_plan) -> list[str]:
    buy = buy_step(SPEC, "Test", MODS, STATS)
    pages = [page_of(inp()) for inp in INPUTS.values()]
    pages.append(page_of(route_input(r12_plan), given(r12_plan, ROUTE.read_text(encoding="utf-8")), buy=buy))
    pages.append(page_of(given(two_leaf_plan, RESTART_ROUTE), given(two_leaf_plan, GAP_ROUTE), buy=buy))
    return pages


def test_a_page_is_self_contained_and_makes_no_request(r12_plan, two_leaf_plan):
    for html in all_pages(r12_plan, two_leaf_plan):
        assert "<script" not in html and "src=" not in html and "@import" not in html and "url(" not in html
        assert 'name="viewport"' in html and html.startswith("<!doctype html>")
        addresses = re.findall(r"https?://[^\"'<> ]+", html)
        assert all(address.startswith(TRADE_LINK) for address in addresses)
        for tag in re.findall(r"<a [^>]*href=\"https?://[^>]*>", html):
            assert 'rel="noopener noreferrer"' in tag and 'target="_blank"' in tag


def test_a_page_shows_nothing_absent_and_no_stray_python_values(r12_plan, two_leaf_plan):
    for html in all_pages(r12_plan, two_leaf_plan):
        text = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
        assert not re.search(r"\bNone\b|\bnan\b|\binf\b", text)


def test_nothing_is_shown_as_absent_outside_the_buy_filter(r12_plan):
    buy = buy_step(SPEC, "Test", MODS, STATS)
    html = page_of(route_input(r12_plan), buy=buy)

    accepts = html[html.index(">Accepts<") : html.index(">Trade<")]
    assert "no influence" in accepts and "not corrupted" in accepts
    assert html.count("no influence") == 1 and html.count("not corrupted") == 1
    visible = re.sub(r'href="[^"]*"', "", html.replace(accepts, ""))  # the link's query names the filter, the page does not
    assert "orrupted" not in visible and "nfluence" not in visible


def test_every_text_is_escaped():
    inp = INPUTS["bench"]()
    section = build_section(inp, DATA)
    nasty = Page("<b>x</b> & \"y\"", (section,))

    html = render_page(nasty)

    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt; &amp; &quot;y&quot;" in html


def test_the_same_model_renders_the_same_bytes():
    inp = INPUTS["branch"]()

    assert page_of(inp) == page_of(inp)


def test_a_route_view_page_row_has_its_anchor_and_every_link_inside_goes_to_a_row(r12_plan):
    html = page_of(INPUTS["branch"]())

    assert 'id="s1"' in html and 'id="s2"' in html and 'id="s3"' in html
    assert 'href="#s3"' in html


def test_write_route_page_without_a_stat_list_in_the_cache_writes_the_page(tmp_path, r12_plan):
    report = build_report(r12_plan, DATA)

    path = write_route_page(tmp_path / "deep" / "x.route.html", report, DATA, buy_spec=SPEC, cache_dir=tmp_path / "none")

    assert path.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert "not in the link: +#% to Lightning Resistance" in path.read_text(encoding="utf-8")


def test_a_damaged_stat_list_in_the_cache_is_ignored(tmp_path, r12_plan):
    (tmp_path / "trade").mkdir()
    (tmp_path / "trade" / "stats.json").write_text("{not json", encoding="utf-8")
    report = build_report(r12_plan, DATA)

    path = write_route_page(tmp_path / "x.route.html", report, DATA, buy_spec=SPEC, cache_dir=tmp_path)

    assert "not in the link" in path.read_text(encoding="utf-8")


# --- the numbers ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "chance, text",
    [
        (1.0, "100%"),
        (0.5, "50%"),
        (0.37, "37%"),
        (1 / 3, "≈33%"),
        (0.043, "4.3%"),
        (0.0426, "≈4.3%"),
        (0.00093, "0.093%"),
        (1e-7, "< 0.001%"),
        (0.99999, "> 99.9%"),
        (0.9951, "≈99.5%"),
    ],
)
def test_chances_are_percentages_with_an_approximately_sign_only_when_rounded(chance, text):
    assert chance_text(chance) == text


@pytest.mark.parametrize(
    "chaos, text",
    [(1.0, "1 c"), (0.5, "0.5 c"), (4.0, "4 c"), (58.52, "≈ 58.5 c"), (1234.0, "≈ 1,230 c"), (300.0, "300 c"), (1000.0, "1,000 c")],
)
def test_money_has_three_significant_digits_commas_and_an_approximately_sign_only_when_rounded(chaos, text):
    assert money(chaos) == text


def test_uses_have_three_significant_digits():
    assert (count(2.0), count(1.0999), count(25.0), count(math.pi)) == ("2", "≈ 1.1", "25", "≈ 3.14")


def test_a_mod_of_the_family_without_a_text_does_not_stop_the_trade_link(tmp_path, r12_plan):
    """The real dump has `IzaroLightningResistanceBuff1` in the family of the fractured resistance, with no text."""
    textless = dataclasses.replace(DATA.mods["LightningResist1"], id="IzaroLightningResistanceBuff1", text=None)
    data = dataclasses.replace(DATA, mods={**DATA.mods, textless.id: textless})
    (tmp_path / "trade").mkdir()
    (tmp_path / "trade" / "stats.json").write_text(
        json.dumps({"stats": json.loads(STATS_FILE.read_text(encoding="utf-8"))}), encoding="utf-8"
    )
    report = build_report(r12_plan, data)

    path = write_route_page(tmp_path / "x.route.html", report, data, buy_spec=SPEC, cache_dir=tmp_path)

    html = path.read_text(encoding="utf-8")
    assert "not in the link" not in html and "fractured.stat_1671376347" in unquote(html)
