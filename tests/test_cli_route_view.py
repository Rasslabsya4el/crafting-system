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
from cli_support import START as START_KEY
from items_support import DATA, roll
from route_view_support import (
    COLD_REQ,
    DAMAGE,
    FRACTURED_COLD,
    HYSTERIA_REQ,
    LIFE,
    START_NAME,
    alike_key,
    assert_golden,
    belt,
    crafted_damage,
    hand_input,
)
from targets_support import EXAMPLES

from crafting_system.actions import HarvestReforge
from crafting_system.cli import _route_flow, evaluate_route, main, make_plan, parse_route
from crafting_system.cli._limits import STRANDS
from crafting_system.cli._reach import policy_states
from crafting_system.cli._report import build_report, render_text
from crafting_system.cli._route_flow import build_flow
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_trade import buy_step
from crafting_system.cli._route_view import (
    Field,
    Line,
    Page,
    PageError,
    RouteInput,
    RouteSection,
    StepRow,
    _View,
    build_section,
    chance_text,
    count,
    given_route_input,
    merge_sections,
    money,
    route_input,
    write_route_page,
)
from crafting_system.cli._route_tiers import TierLine, TierShare
from crafting_system.prices import PriceEntry, load_buy_spec
from crafting_system.prices.trade_query import build_query
from crafting_system.prices.trade_stats import parse_trade_stats, resolve_buy_mod
from crafting_system.risk import evaluate
from crafting_system.targets import Requirement, buy_spec_of, load_target, parse_target, start_price_key

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
    min_tier: any
start_item:
  rarity: rare
start: bought
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
    target = parse_target(TWO_LEAVES, DATA, source="two.yaml")
    prices = price_file(start=None)
    prices.prices[start_price_key(DATA, target)] = PriceEntry(4.0, "trade-api")  # the start item is priced under the key computed from the target
    return make_plan(DATA, target, prices)


def given(plan, text: str) -> RouteInput:
    route = parse_route(textwrap.dedent(text), plan, DATA, "route.yaml")
    return given_route_input(plan, route, evaluate_route(plan, route, DATA))


# --- the page of R12 -----------------------------------------------------------------------------------------


def test_r12_is_a_buy_and_one_step_that_loops_until_the_gem(r12_plan):
    q = float(HarvestReforge("lightning").outcomes(DATA, r12_plan.target.start_item).chance_all([GEM]))

    section = build_section(route_input(r12_plan), DATA)

    buy, reforge = section.rows
    assert [row.title for row in section.rows] == [f"Buy {START_KEY}", "Harvest Reforge Lightning"]
    assert labels_of(buy) == ["Accepts", "Cost per use"]
    assert lines_of(buy, "Cost per use") == ["4 c"]
    assert labels_of(reforge) == ["Goal", "Accepts", "Chance per use", "Tier chances", "Cost per use", "Uses on average", "Step cost"]
    assert lines_of(reforge, "Goal") == [f"{GEM_TEXT} · T1"]
    target, again = lines_of(reforge, "Chance per use")  # nothing is lost on a miss, so no "On failure": the miss is the step again
    assert target.startswith("the target: ") and float(target.split(": ")[1].strip("≈%")) / 100 == pytest.approx(q, rel=0.06)
    assert again.startswith("nothing gained, this step again: ")
    assert lines_of(reforge, "Cost per use") == ["50 × Primal Crystallised Lifeforce 0.5 c"]
    (uses,) = lines_of(reforge, "Uses on average")
    assert float(uses.strip("≈ ")) == pytest.approx(1 / q, rel=0.01)  # a geometric run
    (tier,) = lines_of(reforge, "Tier chances")  # the gem is one mod: its one tier is the chance of the target (OR-31)
    assert tier.startswith(f"{GEM_TEXT}: T1 ")
    assert float(tier.split("T1 ")[1].split("%")[0].strip("≈")) / 100 == pytest.approx(q, rel=0.06)
    assert reforge.final and not buy.final


def test_the_goal_card_gives_route_mean_p90_and_prices(r12_plan):
    risk = r12_plan.risk

    fields = {field.label: field.lines[0].text for field in build_section(route_input(r12_plan), DATA).goal.fields}

    assert list(fields) == ["Route", "Mean", "9 runs in 10", "Approximate inputs", "Prices"]  # no success line: it is 100%; the Harvest reforge reads an approximate claim (#197)
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


def test_golden_r12_through_the_command_the_buy_spec_is_computed_from_the_target(tmp_path, stats_cache, capsys):
    code, out = run_command(tmp_path, cache=stats_cache)

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
    assert html.count("What this answer leaves out") == 1  # the plan's limits are said once, in the planner's section
    ids = re.findall(r' id="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    assert set(re.findall(r'href="#([^"]+)"', html)) <= set(ids)


def test_the_command_writes_the_page_next_to_the_json(tmp_path, capsys):
    code, out = run_command(tmp_path)

    assert code == 0
    assert (out.parent / "r12-lightning-amulet.route.html").exists()
    assert "Route view written to" in capsys.readouterr().out
    assert "buy_spec" not in json.loads(out.read_text(encoding="utf-8"))  # the page is a view; the JSON policy is the same with or without it


def test_the_buy_step_of_a_bought_target_always_has_the_trade_link_and_without_the_stat_list_the_mod_is_named(tmp_path):
    run_command(tmp_path / "a")  # no stats.json in this cache

    page = (tmp_path / "a" / "out" / "r12-lightning-amulet.route.html").read_text(encoding="utf-8")

    assert "Accepts" in page and "Rare Paua Amulet" in page and "item level 84 or more" in page
    assert "fractured: +#% to Lightning Resistance (at least 12)" in page
    assert "not in the link: +#% to Lightning Resistance" in page and TRADE_LINK in page


def test_the_buy_spec_flag_is_gone_because_the_spec_is_computed_from_the_target(tmp_path):
    with pytest.raises(SystemExit) as stop:
        run_command(tmp_path, "--buy-spec", str(FIXTURES / "r12_buy_spec.yaml"))

    assert stop.value.code == 2


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


@pytest.mark.parametrize("name", ["essence", "branch", "remove_crafted_then_chaos"])
def test_the_goal_chances_times_the_uses_of_the_rows_add_up_to_one_finish_per_run(name):
    inp = INPUTS[name]()
    flow = build_flow(inp.plan.start, inp.policy, inp.plan.is_goal)

    # a run reaches the goal once; this holds only if each row's chances are the mixture weighted by its states' visits
    finishes = sum(edge.chance * step.uses for step in flow.steps for edge in step.edges if edge.kind == "goal")

    assert finishes == pytest.approx(1.0)


def test_a_use_that_loses_nothing_wanted_reads_under_chance_per_use_whatever_the_next_step_costs_and_on_failure_is_only_a_loss():
    section = build_section(INPUTS["branch"](), DATA)  # the essence gives life 84% of the time, else the item goes on to the Chaos Orb step

    essence = section.rows[1]
    target, onward = [line for field in essence.fields if field.label == "Chance per use" for line in field.lines]
    assert (target.text, onward.text, onward.href) == ("the target: ≈84%", "the item of step 3: ≈16%", "#s3")
    assert "On failure" not in labels_of(essence)  # the 16% lose no wanted mod (PRES-6: the cost to finish from there decides nothing)


def test_a_use_that_lowers_a_leaf_of_the_target_reads_under_on_failure_in_the_words_of_the_leaf():
    regeneration = Requirement("LifeRegeneration", None, frozenset({"LifeRegeneration1"}))  # the start belt holds it: a Chaos Orb can take it away
    section = build_section(hand_input(START, (COLD_REQ, LIFE, regeneration), chaos_for_life), DATA)

    chaos = section.rows[1]
    (failure,) = [field for field in chaos.fields if field.label == "On failure"]
    assert failure.tone == "warn" and any("Regenerate" in line.text and " lost" in line.text for line in failure.lines)  # the wanted mod the Chaos Orb took
    assert not any("lost" in line.text for field in chaos.fields if field.label == "Chance per use" for line in field.lines)


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
    assert lines_of_card(guide.goal, "Same as the planner") == ["step 1: the planner's step 1"]
    (shared,) = [field for field in guide.goal.fields if field.label == "Same as the planner"]
    assert shared.lines[0].href == "#s1"
    hrefs = [line.href for row in guide.rows for field in row.fields for line in field.lines if line.href]
    assert all(href.startswith(("#s", "#g-s")) for href in hrefs)
    html = render_page(Page("x", (drawn, guide)))
    assert all(f'id="{anchor}"' in html for anchor in {href[1:] for href in hrefs})


def hand_section(rows, prefix: str = "") -> RouteSection:
    """A section of made-up rows `(title, [(text, target number or None)])`, the item card after each from the branch policy."""
    base = build_section(INPUTS["branch"](), DATA)
    made = tuple(
        StepRow(
            number,
            title,
            (Field("On failure", tuple(Line(text, None if to is None else f"#{prefix}s{to}", "→ step 9" if to else "") for text, to in lines), "warn"),)
            if lines
            else (),
            base.rows[0].after,
            f"{prefix}s{number}",
        )
        for number, (title, lines) in enumerate(rows, 1)
    )
    return RouteSection("Hand", base.goal, made, "given" if prefix else "policy")


def test_a_step_with_the_same_words_but_another_follow_up_is_not_the_planners_step():
    policy = hand_section([("Buy", []), ("Chaos", [("life lost (50%)", 3)]), ("Alchemy", [])])
    given_route = hand_section([("Buy", []), ("Chaos", [("life lost (50%)", 3)]), ("Scour", []), ("Alchemy", [])], "g-")
    # the given route's Chaos says the same words, but its follow-up is a Scour, not the planner's Alchemy

    drawn, guide = merge_sections(policy, given_route, "the guide")

    assert [row.title for row in guide.rows] == ["Chaos", "Scour"]  # Chaos is not shared; Buy and Alchemy are
    assert lines_of_card(guide.goal, "Same as the planner") == ["step 1: the planner's step 1", "step 4: the planner's step 3"]


def test_a_shared_step_is_named_and_linked_by_the_planners_number_even_when_the_numbers_differ():
    policy = hand_section([("Buy", []), ("A", []), ("B", [("life lost (1%)", 2)])])
    given_route = hand_section([("Buy", []), ("B", [("life lost (1%)", 3)]), ("A", []), ("C", [("a miss (9%)", 2)])], "g-")

    drawn, guide = merge_sections(policy, given_route, "the guide")

    assert [row.title for row in guide.rows] == ["C"]
    (line,) = [line for field in guide.rows[0].fields for line in field.lines]
    assert (line.href, line.anchor) == ("#s3", "→ step 3")  # the given B is the planner's step 3
    shared = [field for field in guide.goal.fields if field.label == "Same as the planner"][0]
    assert [(l.text, l.href) for l in shared.lines] == [
        ("step 1: the planner's step 1", "#s1"),
        ("step 2: the planner's step 3", "#s3"),
        ("step 3: the planner's step 2", "#s2"),
    ]


def test_two_given_rows_that_repeat_one_planner_row_are_not_the_same_route():
    policy = hand_section([("Buy", []), ("A", []), ("B", [])])
    given_route = hand_section([("Buy", []), ("A", []), ("A", [])], "g-")

    assert len(merge_sections(policy, given_route, "the guide")) == 2


def test_when_the_chain_cannot_be_solved_in_floats_the_rows_have_no_uses_or_step_costs_and_the_step_says_so(monkeypatch):
    solved = _route_flow._visits

    def unsolvable(*arguments):  # the one place the numbers can still stop: a chance per use lost in the float
        visits, _, _ = solved(*arguments)
        return visits * 0.0, False, None

    monkeypatch.setattr(_route_flow, "_visits", unsolvable)

    section = build_section(INPUTS["branch"](), DATA)

    assert all("Uses on average" not in labels_of(row) and "Step cost" not in labels_of(row) for row in section.rows)
    assert lines_of(section.rows[1], "Cost per use") == ["1 × Essence of Hysteria 3 c"]
    joined = [row for row in section.rows if any("plain mean of its" in line for line in lines_of(row, "Note"))]
    assert joined  # said on a step that joins states (the goal card says it as a limit, `flow_limits`)


def test_the_page_of_a_policy_solved_by_the_iteration_instead_of_the_dense_solve_is_the_same_page(monkeypatch):
    """No size of policy leaves out the share of runs that enter a step (#490): the two ways to the same numbers give one page."""
    dense = build_section(INPUTS["branch"](), DATA)
    monkeypatch.setattr(_route_flow, "DENSE_LIMIT", 1)

    sparse = build_section(INPUTS["branch"](), DATA)

    assert [lines_of(row, "Uses on average") for row in sparse.rows] == [lines_of(row, "Uses on average") for row in dense.rows]
    assert lines_of(sparse.rows[1], "Chance per use")[0] == "the target: ≈84%"  # the mixture does not depend on it
    assert any("reached in" in line for row in sparse.rows for line in lines_of(row, "Uses on average"))


def test_a_step_with_several_branches_draws_the_card_of_each_whose_items_differ_from_the_card_after_it():
    section = build_section(INPUTS["branch"](), DATA)

    essence = section.rows[1]
    assert [branch.caption for branch in essence.branches] == ["the target (≈84%)", "the item of step 3 (≈16%)"]
    assert all(branch.card != essence.after for branch in essence.branches)
    html = render_page(Page("x", (section,)))
    assert html.count("the target (≈84%)") == 1 and html.count("the item of step 3 (≈16%)") == 1
    assert not build_section(INPUTS["bench"](), DATA).rows[1].branches  # one outcome: one card


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
    assert restart.title == f"Restart: buy {two_leaf_plan.start_price.name} again"
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
    visible = re.sub(r'What this answer leaves out.*?(?=<div class="cd tg">)', "", visible, flags=re.S)  # the kinds left out are named in game words ("Corrupted essences")
    assert "orrupted" not in visible and "nfluence" not in visible


def test_every_text_is_escaped():
    inp = INPUTS["bench"]()
    section = build_section(inp, DATA)
    nasty = Page("<b>x</b> & \"y\"", (section,))

    html = render_page(nasty)

    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt; &amp; &quot;y&quot;" in html


def test_a_tier_line_marks_the_tiers_of_the_target_ends_with_none_and_is_in_the_one_mod_format():
    line = TierLine("+# to maximum Life", (TierShare(1, 2 / 15, True), TierShare(2, 0.1, False), TierShare(3, 0.0, False)), 0.77)
    all_wanted = TierLine("#% increased Damage", (TierShare(1, 0.5, True), TierShare(2, 0.25, True)), 0.25)

    assert _View.tier_text(line) == "+# to maximum Life: T1 ≈13% (target) · T2 10% · T3 0% · none 77%"
    assert _View.tier_text(all_wanted) == "#% increased Damage: T1 50% · T2 25% · none 25% · every tier is the target"  # nothing to tell apart


def test_runs_of_tiers_with_the_same_chance_are_joined_and_the_target_tier_stays_apart_the_format_the_owner_chose_on_491():
    life = TierLine(
        "+# to maximum Life", tuple(TierShare(tier, 0.0143, tier == 1) for tier in range(1, 11)), 1 - 10 * 0.0143
    )  # Life on a helmet: ten tiers of the same weight
    two = TierLine("x", (TierShare(1, 0.1, False), TierShare(2, 0.1, False), TierShare(3, 0.2, False), TierShare(5, 0.1, False)), 0.5)
    both = TierLine("y", (TierShare(1, 0.1, True), TierShare(2, 0.1, True), TierShare(3, 0.1, False)), 0.7)

    assert _View.tier_text(life) == "+# to maximum Life: T1 ≈1.4% (target) · T2 to T10 ≈1.4% each · none ≈86%"
    assert _View.tier_text(two) == "x: T1 and T2 10% each · T3 20% · T5 10% · none 50%"  # a missing tier (T4 cannot spawn) breaks a run
    assert _View.tier_text(both) == "y: T1 and T2 10% each (target) · T3 10% · none 70%"  # the target's tiers never join the others


def test_two_branches_that_read_alike_say_what_the_player_does_next_and_the_plain_mean_is_said_on_its_step(monkeypatch):
    section = build_section(INPUTS["branch"](), DATA)
    for row in section.rows:  # no step prints two lines that read alike
        for field in row.fields:
            if field.label in ("Chance per use", "On failure"):
                texts = [alike_key(line.text) for line in field.lines]
                assert len(texts) == len(set(texts)), (row.title, texts)

    solved = _route_flow._visits

    def unsolvable(*arguments):
        visits, _, _ = solved(*arguments)
        return visits * 0.0, False, None

    monkeypatch.setattr(_route_flow, "_visits", unsolvable)
    rows = build_section(hand_input(START, LIFE_GOAL, chaos_for_life), DATA).rows
    joined = [row for row in rows if "Note" in labels_of(row)]
    assert joined and "plain mean of its" in lines_of(joined[0], "Note")[-1]  # on the step that joins states, not only on the goal card


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


# --- a price taken for a wider item says so next to the price (OR-3, OR-7) ----------------------------------------


def plan_with_a_wider_price():
    target = load_target(R12, DATA)
    spec = buy_spec_of(DATA, target)
    body = build_query(spec, [resolve_buy_mod(mod, list(DATA.mods.values()), STATS) for mod in spec.mods]).body()
    del body["query"]["filters"]["misc_filters"]["filters"]["ilvl"]  # the stored search had no item level at all
    prices = price_file(start=None)
    prices.prices[spec.name] = PriceEntry(4.0, "trade-api", "a note", {"query": body})
    return make_plan(DATA, target, prices)


def test_the_buy_step_prints_the_line_next_to_the_price_and_a_price_for_the_same_item_prints_none(r12_plan):
    wider = build_section(route_input(plan_with_a_wider_price()), DATA).rows[0]
    same = build_section(route_input(r12_plan), DATA).rows[0]

    assert lines_of(wider, "Cost per use") == ["4 c", "price taken for a wider item (any item level)"]
    assert lines_of(same, "Cost per use") == ["4 c"]


def test_the_text_report_prints_the_line_under_the_start_price():
    lines = render_text(build_report(plan_with_a_wider_price(), DATA)).splitlines()

    start = next(number for number, line in enumerate(lines) if line.startswith("Start item"))
    assert lines[start + 1] == "  price taken for a wider item (any item level)"


def test_the_buy_and_restart_titles_name_a_shared_base_in_words_and_never_by_its_id():
    """#553 (#481): a price key says which base is meant by its id (`Name [Id]`); the page says it in words, and the key stays what it was."""
    from crafting_system.cli._plan import StartPrice
    from route_view_support import BELT

    inp = hand_input(START, LIFE_GOAL, chaos_for_life)
    base = DATA.base_items[BELT]
    twin = dataclasses.replace(base, id=BELT + "Twin", item_class="Ring")  # the same name, another item class
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, twin.id: twin})
    key = f"{base.name} [{BELT.rsplit('/', 1)[-1]}], normal, item level 80"
    plan = dataclasses.replace(inp.plan, start_price=StartPrice(key, 6.0, "trade-api"))
    section = build_section(dataclasses.replace(inp, plan=plan), data)

    assert section.rows[0].title == f"Buy {base.name} (item class Belt), normal, item level 80"
    assert plan.start_price.name == key


def test_every_approximate_claim_the_plan_reads_has_its_line_on_the_goal_card_of_the_page(r12_plan):
    """OR-23 (#553): the claims of `approximate_inputs(plan)` are the lines of the goal card, each as its statement and its source."""
    from crafting_system.cli._marking import approximate_inputs, approximate_page_lines

    read = approximate_inputs(r12_plan, r12_plan.view_policy, DATA)
    card = {field.label: [line.text for line in field.lines] for field in build_section(route_input(r12_plan), DATA).goal.fields}

    assert read, "the Harvest reforge of R12 reads an approximate claim"
    assert card["Approximate inputs"] == approximate_page_lines(read)
    assert all(" Source: " in line and "harvest_reforge." not in line for line in card["Approximate inputs"])


# --- a page is drawn only from a plan with limits (ticket #550, OR-13) ---------------------------------------------


def test_the_page_builder_refuses_a_plan_with_no_limits_and_names_the_cause():
    inp = INPUTS["essence"]()
    assert inp.plan.limits  # the fixture's limits come from the planner's own functions (`plan_support.planner_plan`)
    bare = dataclasses.replace(inp, plan=dataclasses.replace(inp.plan, limits=()))

    with pytest.raises(PageError, match=r"no limits.*OR-13"):
        build_section(bare, DATA)


def test_a_plan_without_the_limit_every_planner_plan_has_is_refused_even_with_other_limits():
    inp = INPUTS["essence"]()
    other = tuple(limit for limit in inp.plan.limits if limit.kind != STRANDS)
    assert other  # the fixture has more than the Memory Strands limit
    odd = dataclasses.replace(inp, plan=dataclasses.replace(inp.plan, limits=other))

    with pytest.raises(PageError, match="Memory Strands"):
        build_section(odd, DATA)


def test_a_page_drawn_from_a_fixture_plan_has_the_part_what_this_answer_leaves_out():
    section = build_section(INPUTS["essence"](), DATA)

    assert section.goal.leaves_out
    assert "Memory Strands" in [field.label for field in section.goal.leaves_out]
