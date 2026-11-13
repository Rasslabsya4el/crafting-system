"""A start item is given or bought, and a bought one must have a price (#505, OR-6, OR-13; audit #396 class 2, #453 point 2, #494 point 1).

One test per rule of the ticket, on the fixture amulet of R12 (a bought start item) and its given copy:

* the key `start: bought | given` is required (`test_the_key_is_required_*`; the parser's own cases are in `test_targets_parse.py`);
* a bought start item with no price is refused and the error names its key (`test_a_bought_start_item_with_no_price_*`);
* `--start-price` must be above 0 (`test_a_start_price_*`);
* a restart exists only for a bought start item, whatever the price file holds (`test_a_restart_*`; P3, P4, P5);
* a given start item reads "given: its cost is not counted, and the plan never buys another" in the text, the JSON, the page and the limit
  (`test_a_given_start_item_*`; P1, P6, P7);
* the corruption check reads given or bought (`test_the_corruption_check_*`; P11);
* the benchmark refuses a missing price and writes no 0 placeholder (`test_the_benchmark_*`; P8, P9, P10);
* an unpriced start option is reported as unpriced, not priced at infinity (`test_an_unpriced_start_option_*`; P13).
"""

import json
import math
import re
from pathlib import Path

import pytest
from cli_support import R12, START, given, price_file, read_json
from cli_support import run as run_command
from start_support import with_start
from targets_support import DATA, parse, parse_error

from crafting_system.cli import RESTART, build_report, make_plan, policy_document, render_text
from crafting_system.cli import _benchmark
from crafting_system.planner._plan import GIVEN_SOURCE, PlanError, StartPrice, resolve_start_price
from crafting_system.cli._route_view import build_section, route_input
from crafting_system.planner._starts import plain_candidate, plan_with_starts
from crafting_system.cli._start_report import start_document, start_lines
from crafting_system.targets import StartKind, TargetError, load_target

GIVEN_WORDS = "given: its cost is not counted, and the plan never buys another"


@pytest.fixture(scope="module")
def bought_target():
    return load_target(R12, DATA)


@pytest.fixture(scope="module")
def given_target(bought_target):
    return given(bought_target)


@pytest.fixture(scope="module")
def bought_plan(bought_target):
    return make_plan(DATA, bought_target, price_file(start=4.0))


@pytest.fixture(scope="module")
def given_plan(given_target):
    return make_plan(DATA, given_target, price_file(start=4.0))  # the file prices the item; a given item is not bought, so it is not read


def lines_of(row, label: str) -> list[str]:
    return [line.text for field in row.fields if field.label == label for line in field.lines]


# -- the key is required ---------------------------------------------------------------------------------------------------------------


def test_the_key_is_required_in_a_target_file(tmp_path):
    path = tmp_path / "no-start.yaml"
    path.write_text(re.sub(r"(?m)^start:.*\n", "", R12.read_text(encoding="utf-8")), encoding="utf-8")

    with pytest.raises(TargetError) as caught:
        load_target(path, DATA)

    message = str(caught.value)
    assert "start: this key is required but missing" in message and "start: bought" in message and "start: given" in message


def test_the_key_is_required_whatever_else_the_file_says():
    assert "start: this key is required" in parse_error("requirements:\n  - family: IncreasedLife\nstart_item:\n  rarity: rare\n", start=None)


def test_the_example_r12_says_bought_and_its_given_copy_says_given(bought_target, given_target):
    assert bought_target.start is StartKind.BOUGHT and given_target.start is StartKind.GIVEN
    assert re.search(r"(?m)^start: bought$", R12.read_text(encoding="utf-8"))


# -- a bought start item must have a price ---------------------------------------------------------------------------------------------


def test_a_bought_start_item_with_no_price_is_refused_and_the_error_names_its_key(bought_target):
    with pytest.raises(PlanError) as caught:
        make_plan(DATA, bought_target, price_file(start=None))

    message = str(caught.value)
    assert repr(START) in message and "must have a price" in message
    assert "`trade` command" in message and "--start-price" in message  # what to do, in the words of the report (#586)
    assert "python" not in message and ".toml" not in message


def test_the_price_of_a_bought_start_item_is_read_under_the_key_computed_from_the_target(bought_target):
    found = resolve_start_price(DATA, bought_target, price_file(start=4.0), None)

    assert (found.name, found.chaos, found.source, found.given) == (START, 4.0, "trade-api", False)


def test_a_bought_start_item_is_never_free_by_construction():
    for chaos in (0.0, -1.0, math.inf, math.nan):
        with pytest.raises(ValueError, match="above 0"):
            StartPrice("x", chaos, "test")
    assert StartPrice("x", 1.0, "test").bought


# -- --start-price must be above 0 -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", [0.0, -3.0, math.nan, math.inf])
def test_a_start_price_that_is_not_above_zero_is_refused(bought_target, value):
    with pytest.raises(PlanError, match="above 0"):
        make_plan(DATA, bought_target, price_file(), start_price=value)


def test_a_start_price_of_zero_on_the_command_line_is_refused_with_an_error_and_no_policy(tmp_path, capsys):
    code, out = run_command(tmp_path, "--start-price", "0", prices=price_file())

    assert code == 1 and not out.exists()
    assert "the start price must be a number of Chaos above 0" in capsys.readouterr().err


def test_a_start_price_above_zero_on_the_command_line_wins(tmp_path):
    code, out = run_command(tmp_path, "--start-price", "10", prices=price_file())

    document = read_json(out)
    assert code == 0 and document["start"]["price_chaos"] == 10.0 and document["start"]["given"] is False


def test_a_start_price_has_nothing_to_set_on_a_given_start_item(given_target):
    with pytest.raises(PlanError, match="given.*--start-price"):
        make_plan(DATA, given_target, price_file(), start_price=5.0)


# -- a restart exists only for a bought start item ----------------------------------------------------------------------------------------


def test_a_restart_is_offered_for_a_bought_start_item_at_its_price(bought_plan):
    restart = next(priced for priced in bought_plan.offers if priced.label == RESTART)

    assert restart.cost == 4.0 and restart.parts == ((START, 1, 4.0, "trade-api"),)
    assert bought_plan.start_price.bought and not [limit for limit in bought_plan.limits if limit.kind == "start-item"]


def test_a_restart_is_never_offered_for_a_given_start_item_whatever_the_price_file_holds(given_plan):
    assert all(priced.label != RESTART for priced in given_plan.offers)
    assert given_plan.start_price.given and given_plan.start_price.chaos == 0.0


def test_a_restart_is_not_decided_by_the_number_the_price_file_holds():
    cheap = make_plan(DATA, load_target(R12, DATA), price_file(start=0.0001))

    assert any(priced.label == RESTART for priced in cheap.offers)  # a tiny price is still a bought item


def test_a_given_route_cannot_restart_a_given_start_item_and_a_bought_one_can(bought_plan, given_plan):
    from crafting_system.cli import RouteError, parse_route

    assert parse_route("rules:\n  - do: restart\n", bought_plan, DATA, "route.yaml").rules[0].do == RESTART
    with pytest.raises(RouteError, match="never bought again"):
        parse_route("rules:\n  - do: restart\n", given_plan, DATA, "route.yaml")


# -- a given start item: text, JSON, page, limit -------------------------------------------------------------------------------------------


def test_a_given_start_item_reads_given_in_the_text_and_prints_no_price(given_plan):
    text = render_text(build_report(given_plan, DATA))

    assert f"Start item: {GIVEN_WORDS}" in text.splitlines()
    assert "Start item: 0.00 Chaos" not in text and "free" not in text.lower().split("start item")[1].splitlines()[0]


def test_a_bought_start_item_reads_its_price_and_source_in_the_text(bought_plan):
    text = render_text(build_report(bought_plan, DATA))

    assert f"Start item ({START}): 4.00 Chaos [trade-api]" in text.splitlines()


def test_a_given_start_item_is_marked_in_the_json(given_plan, bought_plan):
    document = policy_document(build_report(given_plan, DATA), None, target_name="t.yaml")

    assert document["start"] == {"state": "S1", "price_name": None, "price_chaos": 0.0, "price_source": GIVEN_WORDS, "given": True}
    assert policy_document(build_report(bought_plan, DATA), None, target_name="t.yaml")["start"]["given"] is False


def test_a_given_start_item_reads_given_on_the_page_with_no_trade_link_and_no_price(given_plan):
    section = build_section(route_input(given_plan), DATA)

    first = section.rows[0]
    assert first.title == "Start item (given)"
    assert [field.label for field in first.fields] == ["Start item", "Cost per use"]
    assert lines_of(first, "Cost per use") == [GIVEN_WORDS]


def test_a_bought_start_item_reads_its_price_on_the_page_under_a_buy_title(bought_plan):
    first = build_section(route_input(bought_plan), DATA).rows[0]

    assert first.title == f"Buy {START}" and lines_of(first, "Cost per use") == ["4 c"]


def test_a_given_start_item_limit_says_what_the_answer_still_guarantees(given_plan):
    (limit,) = [found for found in given_plan.limits if found.kind == "start-item"]

    assert limit.what == "The start item is given" and limit.why == "the target says the player already holds it"
    assert limit.guarantee == "The plan is the cheapest among the plans that never start over. The cost of the start item is not counted, and the plan never buys another."


def test_the_limit_of_a_given_start_item_is_in_the_text_and_the_json(given_plan):
    text = render_text(build_report(given_plan, DATA))
    document = policy_document(build_report(given_plan, DATA), None, target_name="t.yaml")

    assert "The start item is given" in text and "the plan never buys another" in text
    assert [limit["what"] for limit in document["limits"] if limit["kind"] == "start-item"] == ["The start item is given"]


# -- the corruption check reads given or bought -------------------------------------------------------------------------------------------

def test_the_corruption_check_refuses_a_given_start_item_that_cannot_reach_the_goal_and_lets_a_bought_one_through():
    from targets_corrupted_support import parse as parse_ring
    from targets_corrupted_support import parse_error as ring_error
    from test_targets_corrupted import TWO

    asking = TWO + "actions: [vaal]" + chr(10)  # two corrupted implicits, and the only corrupting action gives one

    assert "asks for 2 corrupted implicits" in ring_error(asking, start="given")
    assert len(parse_ring(asking, start="bought").implicits) == 2  # a bought item may come corrupted already: nothing is checked


def test_the_corruption_check_reads_the_key_and_not_a_price():
    from targets_corrupted_support import parse as parse_ring
    from test_targets_corrupted import TWO

    assert parse_ring(TWO + "actions: [vaal]" + chr(10) + "start: bought" + chr(10)).bought  # the key alone decides: no price file exists at parse time


# -- the benchmark ----------------------------------------------------------------------------------------------------------------------------


def test_the_benchmark_refuses_a_bought_start_item_with_no_price_and_writes_no_zero_placeholder(bought_target, tmp_path):
    from crafting_system.config import load_config

    missing = _benchmark._missing_start_price(DATA, bought_target, price_file(start=None), tmp_path, load_config({}), "examples/targets/r12-lightning-amulet.yaml")

    assert missing is not None and missing["name"] == START
    message = _benchmark._missing_message(missing)
    assert "a bought start item must have a price above 0" in message and START in message
    assert " = 0" not in message and " = 0" not in missing["override_line"]


def test_the_benchmark_finds_nothing_to_price_for_a_given_start_item_or_a_priced_one(bought_target, given_target, tmp_path):
    from crafting_system.config import load_config

    config = load_config({})
    assert _benchmark._missing_start_price(DATA, given_target, price_file(start=None), tmp_path, config, "t.yaml") is None
    assert _benchmark._missing_start_price(DATA, bought_target, price_file(start=4.0), tmp_path, config, "t.yaml") is None


def test_the_benchmark_summary_names_a_given_start_without_a_zero():
    start = {"chosen": "plain", "matches": True, "expected": "plain", "start_price": None, "given": True, "options": [], "refused": [], "why": "x"}

    (line, *_) = _benchmark._start_summary(start)

    assert "start price given, not counted" in line and "0.00" not in line
    assert "start price no price" in _benchmark._start_summary({**start, "given": False})[0]


# -- an unpriced start option --------------------------------------------------------------------------------------------------------------------


def test_an_unpriced_start_option_is_reported_as_unpriced_not_priced_at_infinity(bought_target):
    candidate = plain_candidate(DATA, bought_target, price_file(start=None), None)

    assert candidate.price is None and not candidate.given
    assert candidate.price_name == START and "must have a price" in candidate.price_source


def test_an_unpriced_start_option_has_a_null_price_in_the_json_and_no_infinity_anywhere(bought_target):
    from crafting_system.planner._start_types import ConsideredStart, ReadingChoice, StartChoice

    candidate = plain_candidate(DATA, bought_target, price_file(start=None), None)
    choice = StartChoice(candidate, (ConsideredStart(candidate, "failed", None, None, False, candidate.price_source),), (), (), (ReadingChoice((), None, math.inf),), ())

    (option,) = start_document(choice)["options"]
    assert option["start_price_chaos"] is None and option["given"] is False and option["outcome"] == "failed"
    assert "inf" not in json.dumps(start_document(choice)).lower().replace("information", "")
    assert any("failed:" in line and "must have a price" in line for line in start_lines(choice))


def test_a_given_plain_start_option_is_given_not_priced_zero(given_target):
    candidate = plain_candidate(DATA, given_target, price_file(), None)

    assert candidate.given and candidate.price == 0.0 and candidate.price_source == GIVEN_SOURCE


def test_planning_with_a_bought_start_that_has_no_price_fails_with_the_plain_start_error(bought_target):
    from crafting_system.planner._start_types import SOURCE_PLAIN  # noqa: F401  (the plain source is the only one with a price in the file)

    with pytest.raises(PlanError, match="must have a price"):
        plan_with_starts(DATA, bought_target, price_file(start=None))
