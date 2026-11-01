"""Benchmark route V01 on the real 3.29.3.3 dump: a Minion helmet whose best plan starts from the vendor recipe (ticket #331, ADR-0059).

The target is `examples/targets/v01-minion-helmet.yaml` (+1 to Level of all Minion Skill Gems and top Life on a Normal Lion Pelt,
four basic orbs), the prices are `tests/fixtures/prices/vendor-v01-2026-11-01.json` (the committed poe.ninja snapshot of the other
routes plus hand prices for the base, the Minion gems and the flask: the trade API does not price those lines yet, ticket #360).
These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`; point `CRAFTING_CACHE_DIR` at it) and skip cleanly without it;
CI fetches it. The route is planned once per process; it solves in a few seconds.

"Done when" of the ticket, line by line:

1. The new route's plan starts from the recipe, and its golden (text, JSON and route page) is committed:
   `test_the_plan_starts_from_the_recipe_made_helmet` and the three golden tests (`tests/golden/v01_minion_helmet.txt`, `.json`, `.html`;
   `UPDATE_GOLDEN=1` rewrites them).
2. The report names the recipe inputs with counts and the start price, and a test pins it:
   `test_the_report_names_the_base_and_the_gems_with_their_counts_the_item_back_and_the_start_price` (the toy boots do the same for a
   five-step chain in `test_vendor_report.py`).
3. The benchmark list includes the route, and CI runs it within the usual time:
   `test_the_benchmark_list_holds_v01_and_its_entry_records_the_expected_start` runs the benchmark's own `run_route` on it (a few seconds).
"""

import json
import os
import re
from fractions import Fraction
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from cli_support import TODAY
from route_view_support import GOLDEN, assert_golden

from crafting_system.cli import (
    StartContext,
    build_report,
    plan_with_starts,
    policy_document,
    render_text,
    vendor_recipe_starts,
)
from crafting_system.cli import _benchmark as benchmark_module
from crafting_system.cli._route_view import write_route_page
from crafting_system.cli._shares import weight_share
from crafting_system.cli._start_step import first_step
from crafting_system.config import load_config
from crafting_system.items import Rarity
from crafting_system.prices import PriceFile, load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "examples" / "targets" / "v01-minion-helmet.yaml"
PRICES = ROOT / "tests" / "fixtures" / "prices" / "vendor-v01-2026-11-01.json"
KEY = "vendor:minion_helmet:1"
MINION = "GlobalIncreaseMinionSpellSkillGemLevel1"
BASE_PRICE, GEMS_PRICE = 2.0, 6.0  # the hand prices of the fixture: "Lion Pelt (ilvl 84)" and "Vendor recipe gems (minion, 40% quality)"
GEMS_LINE = "Vendor recipe gems (minion, 40% quality)"


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def plan(data):
    return plan_with_starts(data, load_target(TARGET, data), load_price_file(PRICES))


@pytest.fixture(scope="module")
def report(plan, data):
    return build_report(plan, data)


def masked(text: str) -> str:
    return re.sub(r"^Run time:.*$", "Run time: <measured>", text, flags=re.MULTILINE)


# --- the plan starts from the recipe ------------------------------------------------------------------------------------------


def test_the_target_names_the_committed_price_file(data):
    target = load_target(TARGET, data)

    assert target.price_file is not None and target.price_file.resolve() == PRICES.resolve() and PRICES.is_file()
    assert target.start_price == "Lion Pelt (ilvl 84)" and target.start_price in load_price_file(PRICES).prices


def test_the_plan_starts_from_the_recipe_made_helmet(plan):
    choice = plan.starts

    assert choice.chosen.key == KEY and choice.chosen.recipe == "minion_helmet" and choice.chosen.steps == 0
    item = plan.target.start_item
    assert item.rarity is Rarity.MAGIC and item.item_level == 84
    assert [(mod.mod_id, mod.values) for mod in item.mods] == [(MINION, (1,))]  # one mod, the Minion gems, and nothing else
    assert plan.start_price.chaos == pytest.approx(BASE_PRICE + GEMS_PRICE)  # the sum of the recipe's inputs at the fixture prices
    assert plan.start_price.chaos == pytest.approx(sum(part[2] for part in choice.chosen.goods))


def test_the_recipe_start_costs_less_in_all_than_the_plain_start_and_the_refused_are_none(plan):
    by_key = {row.candidate.key: row for row in plan.starts.considered}

    assert by_key[KEY].outcome == "chosen" and by_key["plain"].outcome == "planned"
    assert by_key[KEY].total == pytest.approx(866.4, abs=0.1)  # start 8 + crafting 858.4
    assert by_key["plain"].total == pytest.approx(1348.9, abs=0.1)  # start 2 + crafting 1,346.9
    assert by_key[KEY].total < by_key["plain"].total
    assert plan.starts.refused == () and not plan.starts.reading_matters  # no rule axis: the elemental cap is not read here
    assert plan.risk is not None and plan.risk.success_probability.value == pytest.approx(1.0)  # the kept start has its risk, measured once


def test_the_reason_in_the_benchmark_is_the_weight_of_the_minion_mod_in_the_pool(plan, data):
    wanted, total = weight_share(data, load_target(TARGET, data).start_item, [MINION], None)  # one draw on the Normal Lion Pelt

    assert (wanted, total) == (250, 114_675) and float(Fraction(total, wanted)) == pytest.approx(458.7)
    bench = next(each for each in benchmark_module.BENCHMARKS if each.id == "V01")
    assert "250 of 114,675 weight" in bench.start.why and "one draw in 459" in bench.start.why


# --- the report ------------------------------------------------------------------------------------------------------------------


def test_the_report_names_the_base_and_the_gems_with_their_counts_the_item_back_and_the_start_price(report):
    text = render_text(report, target_name="v01-minion-helmet.yaml")
    lines = text.splitlines()

    first = lines.index("First step, before S1: Vendor recipe: Helmet with +1 to Minion Skill Gems, 1 recipe")
    assert lines[first + 1 :first + 6] == [
        "  You hand the vendor:",
        f"    1 Lion Pelt (ilvl 84), a Normal base: {BASE_PRICE:,.2f} Chaos [hand]",
        f"    2 or more uncorrupted skill gems with the Minion tag, 40% quality in all (the cheapest set): {GEMS_PRICE:,.2f} Chaos [hand]",
        "  The recipe:",
        "    2 or more uncorrupted skill gems with the Minion tag, 40% quality in all (the cheapest set) -> +1 to Level of all Minion Skill Gems, T2",
    ]
    assert lines[first + 6] == "  You get back: Magic Lion Pelt, item level 84, with only +1 to Level of all Minion Skill Gems, T2 (the recipe wipes every other mod)"
    assert lines[first + 7] == f"  Start price: {BASE_PRICE + GEMS_PRICE:,.2f} Chaos = the goods above; a restart makes the item again at this price"
    assert text.isascii()
    assert f"Start item (Helmet with +1 to Minion Skill Gems (vendor recipe)): {BASE_PRICE + GEMS_PRICE:,.2f} Chaos" in text
    assert "vendor.gem_qualification_is_uncorrupted_skill_gems" in text  # the approximate claim of the gem rule is listed with the answer


def test_the_first_step_is_built_from_the_chosen_candidate_alone(plan, data):
    step = first_step(plan.starts.chosen, data, plan.target)

    assert step is not None and [(good.role, good.count, good.name) for good in step.hand] == [
        ("base", 1, "Lion Pelt (ilvl 84)"),
        ("gems", 1, GEMS_LINE),
    ]
    assert step.mods == (("+1 to Level of all Minion Skill Gems", "T2"),) and step.roll_note == ""


# --- the goldens -----------------------------------------------------------------------------------------------------------------


def test_the_text_report_is_the_golden(report):
    assert_golden("v01_minion_helmet", masked(render_text(report, target_name="v01-minion-helmet.yaml")), extension="txt")


def rounded(value, digits: int = 9):
    """`value` with every float cut to `digits` significant digits: the last digits of a mean differ between CPUs (numpy sums), the golden says the rest."""
    if isinstance(value, float):
        return float(f"{value:.{digits}g}")
    if isinstance(value, dict):
        return {key: rounded(each, digits) for key, each in value.items()}
    if isinstance(value, list):
        return [rounded(each, digits) for each in value]
    return value


def test_the_json_policy_is_the_golden(report):
    document = policy_document(report, None, target_name="v01-minion-helmet.yaml")
    document.pop("timings_seconds")
    text = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path = GOLDEN / "v01_minion_helmet.json"
    if os.environ.get("UPDATE_GOLDEN"):
        path.write_text(text, encoding="utf-8", newline="\n")

    assert path.exists(), f"no golden file {path}; run with UPDATE_GOLDEN=1 to write it"
    assert rounded(json.loads(text)) == rounded(json.loads(path.read_text(encoding="utf-8")))  # floats to 9 digits, everything else exact


def test_the_route_page_is_the_golden(report, data, tmp_path):
    page = tmp_path / "v01.route.html"

    write_route_page(page, report, data, target_name="v01-minion-helmet.yaml")

    assert_golden("v01_minion_helmet", page.read_text(encoding="utf-8"))


# --- the benchmark ---------------------------------------------------------------------------------------------------------------


def test_the_benchmark_list_holds_v01_and_its_entry_records_the_expected_start(data):
    bench = next(each for each in benchmark_module.BENCHMARKS if each.id == "V01")
    assert bench.route is None and bench.start.key == KEY and bench.heavy is None

    entry, loaded = benchmark_module.run_route(bench, data, ROOT, load_config({}), None, TODAY)  # the prices are the ones the target names
    assert loaded is not None and loaded.league == "Allflame" and loaded.prices[GEMS_LINE].chaos == GEMS_PRICE

    assert entry["error"] is None and entry["given_route"] is None and entry["solver_not_dearer"] is None
    start = entry["start"]
    assert (start["expected"], start["chosen"], start["matches"]) == (KEY, KEY, True)
    assert start["why"] == bench.start.why and start["start_price"] == pytest.approx(BASE_PRICE + GEMS_PRICE)
    assert [(each["key"], each["outcome"]) for each in start["options"]] == [("plain", "planned"), (KEY, "chosen")]
    assert start["first_step"]["recipe"] == "minion_helmet" and start["first_step"]["price_chaos"] == pytest.approx(8.0)
    assert entry["solver"]["success"] == pytest.approx(1.0) and entry["solver"]["mean"] == pytest.approx(866.4, abs=0.1)
    summary = benchmark_module.render_summary({"machine": {"os": "x", "cpu_count": 1, "python": "y", "commit": "z" * 12}, "routes": [entry]})
    assert f"start        {KEY} (as expected; expected {KEY})" in summary and "why          The +1 Minion gems mod" in summary


def test_a_price_file_without_the_gem_line_refuses_the_recipe_and_says_which_line_is_missing(data):
    """No planning here: with the recipe refused the plain start is the answer, and measuring its risk takes minutes (the cheap orbs, ticket #190)."""
    target = load_target(TARGET, data)
    prices = load_price_file(PRICES)
    without = PriceFile(
        prices.league, prices.fetched_at, prices.chaos_per_divine, {name: entry for name, entry in prices.prices.items() if name != GEMS_LINE}
    )

    found = vendor_recipe_starts(StartContext(data, target, without))

    assert found.candidates == ()
    assert [(each.recipe, each.reason, GEMS_LINE in each.detail) for each in found.refused] == [("minion_helmet", "no price", True)]
