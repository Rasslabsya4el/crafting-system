"""The stop at a proved gap on the crafting problem, and what the plan says of it (ticket #826, OR-32, OR-13, OR-33).

The worlds are the fixture worlds of `test_cli_envelope_light.py` (about a hundred states, a bound at about 61% of the exact cost) and of
`test_cli_envelope_plan.py` (the coarse fixture, about 200 states, a bound at about 73%), each with the full packed walk's optimum beside it. The
full walk is the oracle here because these worlds are small; nothing else is built on it.

* for gaps from 1% to 100%, with the stop applying from the first round, the plan's mean is at most `(1 + gap)` times the walk's optimum, the lower
  figure is at most the optimum, and the mean shown is the exact mean of the plan shown (solved again from its own chain, with no code of the search);
* a gap of 0 and no budget are the exact search: the walk's mean to 1e-9; under a budget the stop applies whatever the time (OR-39);
* the limit of a search that stopped at a gap says so in a player's words, with the plan's exact mean, the figure no plan costs less than and the gap
  proved; no limit of that plan claims "the cheapest";
* the settings: `Budget.gap` (a share, zero or more; `search_gap`), `--gap` on the command line;
* a watcher given to `make_plan` and to `plan_target` is told the best plan's cost and the lower figure from the first plan on.

The generic search on hand-worked worlds and random graphs is `tests/test_envelope_gap_stop.py`; the generated family and the benchmark routes are
measured on runners (`.github/scripts/family_bench.py`).
"""

import dataclasses
import json
import re

import numpy as np
import pytest
from cli_support import R12, price_file
from coarse_support import CRAFTS, REMOVE, abstraction
from coarse_support import DATA as COARSE
from targets_support import DATA
from test_cli_approximate import PRICES as APPROX_PRICES
from test_cli_approximate import TARGET as APPROX_TARGET
from test_packed_walk_light import START_ITEM, make_offers

from crafting_system.budget import PROOF_GAP, Budget
from crafting_system.cli import _main, build_report, make_plan, policy_document, render_text
from crafting_system.config import Config
from crafting_system.planner import PlanSettings, Standing, _packed, plan_target
from crafting_system.planner._envelope_plan import EnvelopeInfo, certificate_gap, certificate_gap_text, envelope_limits, envelope_result
from crafting_system.planner._limits import SOLVE, WITHIN_GAP, limit_text
from crafting_system.planner._offers import offer_of
from crafting_system.planner._pattern_bound import pattern_lower_bound
from crafting_system.planner._plan import search_gap
from crafting_system.prices import PriceEntry
from crafting_system.targets import load_target, parse_target

GAPS = [0.01, 0.05, 0.2, 0.7, 1.0]


class HandClock:
    """A clock that only moves when the test says so."""

    def __init__(self) -> None:
        self.now = 1000.0

    def perf_counter(self) -> float:
        return self.now


def at_once(gap: float) -> Budget:
    """A run with no net and this gap: the stop at `gap` applies from the first round, as under any budget (OR-39)."""
    return Budget(aim_seconds=0.0, seconds=None, memory_mb=None, gap=gap)


# ---- the light world, through `envelope_result` -----------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def light():
    ab = abstraction()
    start = ab.compress(START_ITEM)
    offers = make_offers()
    full = _packed.packed_result(ab, start, offers, solver="packed")
    return start, offers, full.solution.values[start], pattern_lower_bound(ab, start, offers)


def searched(light, **options):
    start, offers, _, bound = light
    ab = abstraction()
    return envelope_result(ab, ab.compress(START_ITEM), offers, bound=bound, **options)


def chain_mean(result, start) -> float:
    """The mean of the plan's own chain, solved densely: the policy's action at each state it reaches, nothing of the search or the packed solver."""
    policy = result.solution.policy
    states = [start]
    index = {start: 0}
    for state in states:
        action = policy.get(state)
        if action is None:
            continue
        for outcome in action.outcomes:
            if outcome.state not in index:
                index[outcome.state] = len(states)
                states.append(outcome.state)
    a = np.eye(len(states))
    b = np.zeros(len(states))
    for state, i in index.items():
        action = policy.get(state)
        if action is None:
            continue  # a goal
        total = sum(outcome.weight for outcome in action.outcomes)
        for outcome in action.outcomes:
            a[i, index[outcome.state]] -= outcome.weight / total
        b[i] = action.cost
    return float(np.linalg.solve(a, b)[0])


@pytest.mark.parametrize("gap", GAPS)
def test_the_light_worlds_plan_is_within_its_gap_of_the_walks_optimum_and_its_mean_is_its_own(light, gap):
    start, _, optimum, _ = light
    result = searched(light, gap=gap, gap_after=0.0)
    info = result.info["envelope"]
    mean = result.solution.values[start]
    assert mean <= (1.0 + gap) * optimum * (1 + 1e-9)
    assert info.lower <= optimum * (1 + 1e-9) <= mean * (1 + 2e-9)
    assert info.upper == mean
    assert mean == pytest.approx(chain_mean(result, start), rel=1e-9)  # the mean of the plan shown, not an estimate
    if info.exact:
        assert info.within is None and mean == pytest.approx(optimum, rel=1e-9)
    else:
        assert info.within == gap and info.stopped is None and info.restarts
        assert certificate_gap(info) <= gap


def test_a_wide_gap_stops_the_light_world_before_the_exact_search_would(light):
    exact = searched(light).info["envelope"]
    loose = searched(light, gap=1.0, gap_after=0.0).info["envelope"]
    assert exact.exact and not loose.exact
    assert loose.rounds < exact.rounds and loose.realized < exact.realized


@pytest.mark.parametrize("options", [{}, {"gap": 0.0, "gap_after": 0.0}, {"gap": 1.0}, {"gap": 1.0, "gap_after": 1e9}])
def test_no_gap_or_no_aim_is_the_exact_search_with_the_walks_mean(light, options):
    start, _, optimum, _ = light
    result = searched(light, **options)
    assert result.info["envelope"].exact and result.solution.values[start] == pytest.approx(optimum, rel=1e-9)


def test_the_aim_counts_the_bounds_build(light, monkeypatch):
    """`gap_after` is of the whole call: a build that took longer than the aim leaves the search to stop at the gap from its first round."""
    start, offers, _, bound = light
    from crafting_system.planner import _envelope_plan

    clock = HandClock()
    monkeypatch.setattr(_envelope_plan, "time", clock)  # the clock of `envelope_result`, set by hand: no test reads the time (`tests/test_no_timing.py`)

    def slow_build(*_args, **_kwargs):
        clock.now += 50.0
        return bound

    monkeypatch.setattr(_envelope_plan, "pattern_lower_bound", slow_build)
    ab = abstraction()
    stopped = envelope_result(ab, ab.compress(START_ITEM), offers, gap=1.0, gap_after=40.0)
    assert stopped.info["envelope"].within == 1.0
    ab = abstraction()
    exact = envelope_result(ab, ab.compress(START_ITEM), offers, gap=1.0, gap_after=1e9)
    assert exact.info["envelope"].exact


# ---- the limit ------------------------------------------------------------------------------------------------------------------------


def test_the_limit_of_a_stop_at_a_gap_says_so_with_the_plans_mean_the_proof_figure_and_the_gap_proved(light):
    info = searched(light, gap=1.0, gap_after=0.0).info["envelope"]
    (limit,) = envelope_limits(info)
    text = limit_text(limit)
    assert limit.kind == SOLVE and limit.what == "The search stopped once the plan was proved close to the cheapest"
    assert "the search stopped by itself" in text and "at most 100.00% more than the cheapest possible (the gap this run allows)" in text
    assert "buying the start item again wherever it had not looked" in text
    assert f"The plan is {WITHIN_GAP}: it costs {info.upper:,.2f} Chaos on average after the start item, and that figure is the average of the plan shown itself, not an estimate of the cheapest." in text
    assert f"[{info.lower:,.2f}, {info.upper:,.2f}]" in text and f"costs less than {info.lower:,.2f} on average" in text
    assert f"The plan costs at most {certificate_gap_text(certificate_gap(info))} more than the best possible cost." in text
    assert "not shown to be the best" not in text and "was stopped" not in text  # a net's words
    assert "is the cheapest" not in limit.guarantee
    assert limit.guarantee.endswith(".") and limit.guarantee[0].isupper()
    assert not re.search(r"[a-z]+-[a-z]+-?[a-z]*|_|`|#\d|ticket|ADR|OR-\d|kind=", limit.guarantee), limit.guarantee  # player words, as every limit (`test_cli_limits`)
    assert not re.search(r"graph|lower bound|lower end|optimistic|walk|pattern|kernel|states?", limit.guarantee, re.I), limit.guarantee  # "the stated gap" is a player's word


def test_the_limit_says_when_the_stop_waited_for_a_cost_it_could_certify_and_when_the_plan_buys_no_new_start_item():
    waited = EnvelopeInfo(False, None, 99.3, 100.0, 4, 30, 20, 25, 60, 0, False, None, 9, 0.0, 0.0, None, within=0.01, restarts=False, upper_refused=2)
    text = limit_text(envelope_limits(waited)[0])
    assert "in 2 of its rounds the plan in hand could not be worked out to a certified cost, and the search went on until one could" in text
    assert "buying the start item again" not in text
    assert "at most 1.00% more than the cheapest possible" in text and "at most 0.70% more than the best possible cost" in text
    stopped = EnvelopeInfo(False, "the time limit of 600 seconds was reached", 99.3, 100.0, 4, 30, 20, 25, 60, 0, False, None, 9, 0.0, 0.0, None, restarts=False)
    text = limit_text(envelope_limits(stopped)[0])
    assert "The search was stopped" in text and "restarts from the start item" not in text and "100.00 Chaos on average after the start item, the average of the plan shown itself" in text


# ---- the coarse fixture, through `make_plan` --------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def coarse():
    names = set()
    for action in (*CRAFTS, REMOVE):
        names |= set(offer_of(action, action.label(COARSE), COARSE).resources)
    prices = dataclasses.replace(APPROX_PRICES, prices={name: PriceEntry(2.0, "test") for name in names})
    keys = json.dumps(["chaos-orb", "remove-crafted-mods", *(craft.label(COARSE) for craft in CRAFTS)])
    text = APPROX_TARGET.replace("start: given", "start: bought") + f"actions: {keys}\n"
    target = parse_target(text, COARSE, source="t.yaml")
    return target, prices, make_plan(COARSE, target, prices, start_price=5.0, solver="packed", with_risk=False).mean_remaining


def planned(coarse, **options):
    target, prices, _ = coarse
    return make_plan(COARSE, target, prices, start_price=5.0, solver="envelope", with_risk=False, **options)


@pytest.mark.parametrize("gap", GAPS)
def test_a_plan_past_its_aim_is_within_the_budgets_gap_of_the_walks_optimum(coarse, gap):
    _, _, optimum = coarse
    plan = planned(coarse, budget=at_once(gap))
    info = plan.search
    assert plan.approximation is None  # not the ladder's approximate answer: the mean is the mean of the plan shown
    assert plan.mean_remaining == info.upper and plan.mean_remaining <= (1.0 + gap) * optimum * (1 + 1e-9)
    assert info.lower <= optimum * (1 + 1e-9) <= plan.mean_remaining * (1 + 2e-9)
    assert info.exact or info.within == gap


def test_the_plan_of_a_stop_at_a_gap_claims_no_cheapest_plan_in_any_limit_and_says_the_stop_everywhere(coarse):
    target, prices, _ = coarse
    plan = make_plan(COARSE, target, prices, start_price=5.0, solver="envelope", budget=at_once(0.2))  # with its risk: the text report prints it
    assert not plan.search.exact and plan.search.within == 0.2
    assert not [limit for limit in plan.limits if "is the cheapest" in limit.guarantee], "a limit still claims the cheapest plan"
    assert any(WITHIN_GAP in limit.guarantee for limit in plan.limits)
    (cut,) = [limit for limit in plan.limits if limit.kind == SOLVE and limit.what.startswith("The search stopped once")]
    report = build_report(plan, COARSE)
    assert limit_text(cut) in render_text(report)
    assert any(entry["what"] == cut.what and entry["guarantee"] == cut.guarantee for entry in policy_document(report)["limits"])
    assert not [limit for limit in plan.limits if limit.what.startswith("Stopped by a time or memory limit")]  # no net bound: the stop is not one


@pytest.mark.parametrize("budget", [None, Budget.unlimited(), at_once(0.0), Budget(aim_seconds=60.0, seconds=600.0, gap=0.0)])
def test_no_budget_and_a_gap_of_zero_are_exact_with_the_walks_mean(coarse, budget):
    _, _, optimum = coarse
    plan = planned(coarse, budget=budget)
    assert plan.search.exact and plan.search.within is None
    assert plan.mean_remaining == pytest.approx(optimum, rel=1e-9)
    assert any("The plan is the cheapest among" in limit.guarantee for limit in plan.limits)


def test_a_search_a_net_stopped_claims_no_cheapest_plan_either(coarse):
    from crafting_system.planner._envelope import Net

    plan = planned(coarse, net=Net(states=96))
    assert not plan.search.exact and plan.search.stopped and plan.search.within is None
    assert not [limit for limit in plan.limits if "is the cheapest" in limit.guarantee]


def test_a_watcher_is_told_the_first_plan_and_then_each_round(coarse):
    _, _, optimum = coarse
    seen: list[Standing] = []
    plan = planned(coarse, budget=at_once(0.0), watch=seen.append)
    assert plan.search.exact and len(seen) == plan.search.rounds + 1
    assert seen[0].rounds == 0 and seen[0].upper is not None and seen[0].upper >= optimum * (1 - 1e-9)  # a plan, before any round
    assert all(standing.lower <= optimum * (1 + 1e-9) for standing in seen)
    assert seen[-1].gap == pytest.approx(0.0, abs=1e-6) and seen[-1].upper == pytest.approx(plan.mean_remaining, rel=1e-6)


def test_the_planners_entry_passes_the_watcher_on():
    seen: list[Standing] = []
    plan = plan_target(DATA, load_target(R12, DATA), price_file(), PlanSettings(recipe_starts=False, solver="envelope", watch=seen.append))
    assert seen and seen[-1].upper == pytest.approx(plan.mean_remaining, rel=1e-6) and plan.search.exact


# ---- the settings -----------------------------------------------------------------------------------------------------------------------


def test_the_gap_is_a_named_setting_of_the_budget_with_a_default_of_one_percent():
    assert PROOF_GAP == 0.01 and Budget().gap == PROOF_GAP and Budget.default().gap == PROOF_GAP
    assert Budget(gap=0.0).gap == 0.0
    for wrong in (-0.5, float("inf"), float("nan")):
        with pytest.raises(ValueError, match="gap"):
            Budget(gap=wrong)


def test_the_stop_applies_whatever_the_time_and_never_without_a_gap():
    """OR-39: the minute is the time a plan aims at, not the switch between two kinds of answer."""
    assert search_gap(None) == (0.0, None)
    assert search_gap(Budget.unlimited().start()) == (0.0, None) and Budget.unlimited().gap == 0.0  # a measurement or a test of the exact answer
    assert search_gap(Budget(aim_seconds=60.0, gap=0.0).start()) == (0.0, None)
    assert search_gap(Budget(aim_seconds=60.0, gap=0.02).start()) == (0.02, 0.0)  # from the first round, a minute or not
    assert search_gap(Budget(aim_seconds=None, seconds=600.0).start()) == (PROOF_GAP, 0.0)  # with no aim too


def test_a_plan_under_a_budget_stops_at_the_gap_long_before_its_aim(coarse):
    plan = planned(coarse, budget=Budget(aim_seconds=1e9, seconds=None, gap=0.2))
    assert not plan.search.exact and plan.search.within == 0.2 and plan.search.rounds == 1


def test_the_command_line_has_the_gap_as_a_percent(tmp_path):
    config = Config(tmp_path, tmp_path, tmp_path)
    assert _main.run_budget(config, 60.0).gap == PROOF_GAP
    assert _main.run_budget(config, 60.0, gap=0.05).gap == 0.05
    assert _main._percent("2.5") == 2.5 and _main._percent("0") == 0.0
    for wrong in ("-1", "nan", "inf"):
        with pytest.raises(Exception, match="percent"):
            _main._percent(wrong)
    with pytest.raises(ValueError):  # not a number: the argument parser words it
        _main._percent("one")


# ---- a net's stop on a plan the solver cannot certify, and the start options ------------------------------------------------------------


def test_a_net_stop_whose_last_plan_cannot_be_certified_gives_the_plan_before_it_and_says_so(light, monkeypatch):
    from test_envelope_gap_stop import refuse_upper_solves

    from crafting_system.planner._envelope import Net

    start, _, optimum, _ = light
    refuse_upper_solves(monkeypatch, 2)  # the first plan is certified, the plan in hand at the net is not
    result = searched(light, net=Net(states=100))
    info = result.info["envelope"]
    assert not info.exact and info.held and "limit is 100" in info.stopped
    mean = result.solution.values[start]
    assert mean == info.upper and mean >= optimum * (1 - 1e-9) and info.lower <= optimum * (1 + 1e-9)
    assert mean == pytest.approx(chain_mean(result, start), rel=1e-9)
    text = limit_text(envelope_limits(info)[0])
    assert "could not be worked out to a certified figure, so the plan shown is the one before it" in text


def test_a_start_option_whose_plan_is_only_proved_within_a_gap_says_so_and_the_answer_claims_no_cheapest_plan(monkeypatch):
    """A start not chosen whose plan is within 1% of its cheapest could be cheaper than shown by that much: its row says what was proved, and no
    limit of the answer claims the cheapest plan. The toy world's plans are all proved exact, so the row's words are planted here."""
    from test_vendor_starts import TOY, bought_boots, prices, toy_target, vendor_recipe_starts

    from crafting_system.cli import StartList, plan_with_starts
    from crafting_system.cli._start_report import _row
    from crafting_system.planner import _starts

    sources = (vendor_recipe_starts, lambda context: StartList((bought_boots(5.0),)))
    exact = plan_with_starts(TOY, toy_target(), prices(), sources=sources)
    assert all(not row.note for row in exact.starts.considered if row.outcome in ("chosen", "planned"))
    assert any("is the cheapest" in limit.guarantee for limit in exact.limits)
    monkeypatch.setattr(_starts, "_proved", lambda plan: "" if plan.start_price.chaos == exact.start_price.chaos else "proved at most 0.70% above the cheapest plan from it")
    loose = plan_with_starts(TOY, toy_target(), prices(), sources=sources)
    noted = [row for row in loose.starts.considered if row.note and row.outcome == "planned"]
    assert noted and all("(proved at most 0.70% above the cheapest plan from it)" in _row(row) for row in noted)
    assert not [limit for limit in loose.limits if "is the cheapest" in limit.guarantee]
    assert loose.mean_remaining == exact.mean_remaining
    (cut,) = [limit for limit in loose.limits if limit.what == "The search expanded only what could matter"]  # the chosen start's own search was exact
    assert cut.guarantee.startswith(f"The plan is {WITHIN_GAP} among the methods offered. This search left nothing out")
    assert "best plan from this start item; another start item that was compared has a plan proved only to within its gap." in cut.guarantee
    assert "The cut is exact" not in cut.guarantee  # the exact search's own sentence would contradict "within the stated gap"


def test_what_a_start_options_row_says_of_a_plan_not_proved_the_cheapest():
    from types import SimpleNamespace

    from crafting_system.planner._starts import _proved

    def plan(info):
        return SimpleNamespace(search=info)

    exact = EnvelopeInfo(True, None, 99.5, 99.5, 4, 30, 20, 25, 60, 0, False, None, 9, 0.0, 0.0, None)
    within = EnvelopeInfo(False, None, 99.3, 100.0, 4, 30, 20, 25, 60, 0, False, None, 9, 0.0, 0.0, None, within=0.01)
    no_figure = EnvelopeInfo(False, "the time limit of 600 seconds was reached", 0.0, 100.0, 4, 30, 20, 25, 60, 0, False, None, 9, 0.0, 0.0, None)
    assert _proved(plan(None)) == "" and _proved(plan(exact)) == ""
    assert _proved(plan(within)) == "the crafting cost is the cost of the plan found from this start, proved at most 0.70% above the cheapest plan from it"
    assert _proved(plan(no_figure)).endswith("which is not proved the cheapest")


def test_the_pages_start_line_says_what_a_start_options_plan_proved():
    """The route page's "Start" field lists the start options compared; a row whose plan the search did not prove the cheapest appends what it proved."""
    from types import SimpleNamespace

    from crafting_system.cli._route_view import _View

    def row(outcome, total, note):
        candidate = SimpleNamespace(label="a Magic helmet from the recipe", given=False, price=12.0)
        return SimpleNamespace(outcome=outcome, total=total, mean_remaining=None if total is None else total - 12.0, candidate=candidate, note=note)

    rows = [row("chosen", 61.0, ""), row("planned", 84.0, "the crafting cost is the cost of the plan found from this start, proved at most 0.70% above the cheapest plan from it"), row("failed", None, "x")]
    view = SimpleNamespace(first=object(), plan=SimpleNamespace(starts=SimpleNamespace(considered=rows)))
    field = _View.start_field(view)
    texts = [line.text for line in field.lines]
    assert len(texts) == 2 and texts[0].startswith("chosen: ") and "proved" not in texts[0] and texts[0].endswith(")")
    assert texts[1].startswith("planned: ") and texts[1].endswith("; the crafting cost is the cost of the plan found from this start, proved at most 0.70% above the cheapest plan from it)")
