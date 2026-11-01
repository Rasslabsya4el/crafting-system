"""The measurement script of the variants level (ticket #172, `.github/scripts/measure_variants.py`) on the small committed fixture.

The script is run on GitHub runners on the real bow (docs/ci.md); here the same functions run on the amulet of
`coarse_support.py` with tiny spreads, so that its lines, its arguments and its refusals are checked without the real data
or a heavy run. No time is asserted (ADR-0014): the seconds are only required to be there.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from abstraction_pool import LEVEL, LIVES, RESISTS
from coarse_support import DATA, item
from items_support import AMULET

from crafting_system.abstraction import Coarsening, Goal, Wanted
from crafting_system.actions import (
    AlchemyOrb,
    AnnulmentOrb,
    AugmentationOrb,
    ExaltedOrb,
    FracturingOrb,
    RegalOrb,
    ScouringOrb,
    TransmutationOrb,
)
from crafting_system.cli._decide import Rates
from crafting_system.items import Rarity

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "measure_variants.py"
spec = importlib.util.spec_from_file_location("measure_variants", SCRIPT)
measure = importlib.util.module_from_spec(spec)
sys.modules["measure_variants"] = measure  # a dataclass of the script looks its module up
spec.loader.exec_module(measure)

ORBS = (TransmutationOrb(), AugmentationOrb(), RegalOrb(), AnnulmentOrb(), ExaltedOrb(), ScouringOrb())
SPREADS = (0, 500, 3000)  # none, one pool of two kinds, two pools (the weights of the small pool differ by 400 to 1400)
LEVEL_FIELDS = {
    "case", "route", "spread", "pools", "pooled_families", "blocks", "lower", "upper", "gap", "within_tolerance",
    "seconds", "pooling_seconds", "wall_seconds", "models",
}  # fmt: skip


def amulet_case(actions=ORBS) -> "measure.Case":
    goal = Goal((Wanted(RESISTS), Wanted(LIVES)))
    offers = tuple((action, float(number)) for number, action in enumerate(actions, start=1))
    return measure.Case("amulet", DATA, goal, AMULET, LEVEL, item(rarity=Rarity.NORMAL), offers)


@pytest.fixture(scope="module")
def levels():
    return measure.run_levels(amulet_case(), SPREADS, measure.Report("levels"))


@pytest.fixture(scope="module")
def exact():
    return measure.run_exact(amulet_case(), measure.Report("exact"))


# --- levels ---------------------------------------------------------------------------------------------------------


def test_levels_gives_one_line_per_spread_with_the_fields_and_an_ordered_interval(levels):
    assert [row["spread"] for row in levels] == list(SPREADS)
    for row in levels:
        assert set(row) == LEVEL_FIELDS
        assert 0 < row["lower"] <= row["upper"] and row["gap"] >= 0
        assert row["blocks"] > 0 and row["seconds"] >= 0 and row["wall_seconds"] >= row["seconds"]
        assert set(row["models"]) == {"lower", "upper"}


def test_a_spread_that_pools_something_has_variants_and_one_that_pools_nothing_has_none(levels):
    by_spread = {row["spread"]: row for row in levels}

    assert by_spread[0]["pools"] == 0 and "variant_actions" not in by_spread[0]["models"]["lower"]
    for spread in (500, 3000):
        row = by_spread[spread]
        assert row["pools"] >= 1 and row["pooled_families"] >= 2
        assert row["models"]["lower"]["variant_actions"] > 0 and row["models"]["lower"]["variant_edges"] > 0
        assert row["blocks"] < by_spread[0]["blocks"]


def test_every_interval_brackets_the_exact_value_of_the_same_route(levels, exact):
    for row in levels:
        assert row["lower"] <= exact["value"] * (1 + 1e-9) and exact["value"] <= row["upper"] * (1 + 1e-9)
    assert exact["states"] >= levels[0]["blocks"] > 0  # spread 0 pools nothing: its blocks are the exact states


def test_the_counting_view_does_not_change_the_answer(levels):
    ab = amulet_case().abstraction()
    start = ab.compress(amulet_case().start_item)
    plain = measure.solve_level(
        measure.Candidate(measure.Level("spread", 500, "plain"), None, Coarsening.pooling_by_spread(ab, 500, start)),
        start,
        amulet_case().priced(),
    )

    row = next(row for row in levels if row["spread"] == 500)

    assert (plain.approximation.lower, plain.approximation.upper, plain.approximation.blocks) == (row["lower"], row["upper"], row["blocks"])


def test_a_spread_the_product_refuses_is_a_line_and_the_next_spread_still_runs():
    case = amulet_case((*ORBS, FracturingOrb()))  # declares neither block invariance nor variants
    report = measure.Report("refused")

    rows = measure.run_levels(case, (500, 1000), report)

    assert rows == [] and [row["spread"] for row in report.rows] == [500, 1000]
    assert all(row["refused"] == "OutOfScopeError" and "Fracturing Orb" in row["message"] for row in report.rows)


# --- exact, end to end, the lines on disk -----------------------------------------------------------------------------


def test_exact_counts_states_edges_and_the_value(exact):
    assert exact["case"] == "exact" and exact["value"] > 0 and exact["error_bound"] < 1e-6
    assert exact["states"] > 0 and exact["edges"] > 0 and exact["expanded"] <= exact["states"]
    assert exact["kernel_seconds"] >= 0 and exact["solve_seconds"] <= exact["seconds"]


def test_a_decision_over_the_budget_is_climbed_and_its_answer_brackets_the_exact_value(exact):
    case = amulet_case()
    ab = case.abstraction()
    start = ab.compress(case.start_item)
    pilot = ab.estimate([start], case.actions)
    coarse = pilot.coarsened(Coarsening.pooling_by_spread(ab, 1000, start))
    rates = Rates(1.0, 1.0)
    budget = (pilot.seconds(1.0, 1.0) + coarse.seconds(1.0, 1.0)) / 2
    report = measure.Report("endtoend")

    decision = measure.run_decision(case, report, budget, rates)

    assert decision is not None and decision.action == "approximate"
    decided, answer = report.rows
    assert decided["case"] == "decision" and decided["action"] == "approximate" and decided["levels"] == len(decided["level_names"]) >= 1
    assert decided["pilot_complete"] is True and decided["pilot_seconds"] >= 0 and decided["predicted_seconds"] > budget
    assert answer["case"] == "answer" and answer["lower"] <= exact["value"] * (1 + 1e-9) and exact["value"] <= answer["upper"] * (1 + 1e-9)
    assert answer["blocks"] > 0 and bool(answer["message"]) == (not answer["within_tolerance"])


def test_a_decision_inside_the_budget_is_exact_and_gets_no_answer_line():
    report = measure.Report("endtoend")

    decision = measure.run_decision(amulet_case(), report, 1e9, Rates(1e-6, 1e-6))

    assert decision.action == "exact" and [row["case"] for row in report.rows] == ["decision"]


def test_a_query_with_an_action_that_declares_nothing_is_a_decision_line_with_the_reason_not_a_crash():
    report = measure.Report("refused")

    decision = measure.run_decision(amulet_case((*ORBS, AlchemyOrb())), report, 0.0, Rates(1.0, 1.0))

    assert decision is not None and [row["case"] for row in report.rows] == ["decision"]
    assert report.rows[0]["levels"] == 0 and "Alchemy" in report.rows[0]["message"]


def test_the_lines_go_to_the_console_and_to_a_file_of_the_output_folder(tmp_path, capsys):
    report = measure.Report("levels-test", tmp_path / "out")

    measure.run_levels(amulet_case(), (500,), report)

    printed = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    written = [json.loads(line) for line in (tmp_path / "out" / "levels-test.jsonl").read_text(encoding="utf-8").splitlines()]
    assert printed == written == report.rows and written[0]["spread"] == 500


# --- the command line -------------------------------------------------------------------------------------------------


def test_the_arguments_of_each_case_parse():
    args = measure.parser().parse_args(["levels", "--prices", "cheap", "--goal", "B", "--spreads", "3000,500", "--out", "somewhere"])

    assert (args.case, args.prices, args.goal, args.spreads, args.out) == ("levels", "cheap", "B", (3000, 500), Path("somewhere"))
    assert measure.parser().parse_args(["endtoend"]).budget == 60.0
    assert measure.parser().parse_args(["exact"]).yes_exact is False and measure.parser().parse_args(["exact", "--yes-exact"]).yes_exact
    assert measure.parser().parse_args(["refusals"]).case == "refusals"
    with pytest.raises(SystemExit):
        measure.parser().parse_args(["levels", "--prices", "dear"])


def test_the_exact_case_does_not_run_without_the_flag(capsys):
    assert measure.main(["exact"]) == 0

    printed = json.loads(capsys.readouterr().out)
    assert printed["case"] == "exact" and "--yes-exact" in printed["skipped"]


def test_the_prices_and_goals_of_the_adr_are_the_ones_the_script_uses():
    assert measure.PRICES["default"] == {"transmute": 0.1, "alter": 0.2, "augment": 0.2, "regal": 1, "annul": 20, "exalt": 15, "scour": 1}
    assert {name: measure.PRICES["cheap"][name] for name in ("regal", "annul", "exalt", "scour")} == {"regal": 0.5, "annul": 2, "exalt": 2, "scour": 0.5}
    assert list(measure.ORBS) == list(measure.PRICES["default"]) and measure.SPREADS == (3000, 2000, 1500, 1000, 500)
    assert [family for family, _ in measure.GOALS["A"]] == ["IncreaseSocketedGemLevel", "ChaosDamageHybrid", "IncreasedAttackSpeed"]
    assert [family for family, _ in measure.GOALS["B"]] == ["PhysicalDamage", "CriticalStrikeMultiplier", "IncreasedAttackSpeed"]
