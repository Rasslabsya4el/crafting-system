"""The naive crafter plays the guides' routes; its mean cost against `risk.evaluate`'s mean of the given route (ticket #555, audit TESTS-22 part 2).

`risk.evaluate` costs a given route on the planner's own outcomes (`cli/_route.py`, `evaluate_route`). `tests/naive_crafter/` plays the same
route file on concrete items by Monte Carlo with rules written from the published mechanics (it imports nothing of the planner; its guard is
`tests/naive_crafter/test_naive_independence.py`), at the same prices, from the same target file. The two must agree:

* the mean cost of the route (the start item bought at the start is not counted, a `restart` is), within `K` = 4 of the simulation's own
  standard errors, stated in `naive_crafter/tally.py`;
* the spend of each step of the route, the same, where the exact side is the planner's policy chain: the expected visits of each state
  (the linear equations of the chain) times the price of the action taken there, added up by action label.

A disagreement is a failing test that names the step. Nothing is widened to pass.

Covered with an exact planner side computed in the test: R05 (Deafening Essence of Rage), R08 and R09 (two fossils in a Chaotic resonator, a bench craft; #608), R10
(Shrieking Essence of Spite and a bench craft), R11 (Shrieking Essence of Loathing), R12 (the Harvest reforge of Lightning; #609), R13 (Orbs of Alteration and Regal on a
bought Magic belt since #576, a restart, a bench craft).

Covered with the planner's mean from the benchmark's heavy run (#610): R04 with restart (the Insanity and Rage essences, the Fracturing, Annulment and Exalted Orbs, the
metamod `Cannot roll Attack Modifiers`, Remove Crafted Mods) and R14 with restart (Alteration and Regal on a Magic Hunter bow, a restart, the metamods `Can have up to 3
Crafted Modifiers` and `Cannot roll Attack Modifiers`, the Exalted and Annulment Orbs, three bench crafts). The planner's side of these two is a solve of 177,242 and 816,153
states (`benchmark`: about 10 and 35 minutes on a runner), so the test reads the numbers a heavy run of `tests/naive_planner_side.py` wrote, recorded in
`tests/fixtures/naive_crafter/benchmark_means.json` with the run, the game-data pin and what they were computed from (the hashes of the target and route files and the cost of
each action of the route at the price file). The mean is recorded WITHOUT the price of the bought start item (`mean_without_start`), as the naive mean is: `benchmark` prints
`mean + start price`, so the record keeps `mean_with_start` and `start_price` beside it and a test checks that they add up. A quick test in every CI run fails when the route or
target hash, an action cost or the pin differs from the record (the numbers are stale: record them again); it does not see a change of the planner's code (issue filed in the PR).
The mean comparison itself plays few plays in CI and its 4 standard errors catch only a gross error; the heavy run (`NAIVE_HEAVY=1`) plays enough for a few per cent. Only the mean
is compared there, not the steps (the planner's route result is a lumped chain, not a policy of item states).

The routes with gaps, R04 and R14 as the guides wrote them (`GAPPED`): a state has no rule, or the game refuses the rule's action, so the chance of finishing is below 1 and the
mean of the route is never, so the mean is not compared. The planner's number for the chance (`success_probability.value`, which `benchmark` prints as "success") is the LOW END of a
bracket `(low, high)` from a cost grid whose horizon is 64 of the smallest costs when the policy is not proper (`risk/_evaluate.py`, its docstring), and R14's is 0 although its
own uses say about 10% of plays reach the last two crafts (issue #683). The tests: the share of naive plays that finish lies inside the recorded bracket (widened by K standard
errors), the share of the recorded heavy run too, and a strict xfail tied to #683 says that the planner's printed value equals the heavy share (it flips when the fix is recorded).

The routes the naive crafter cannot play are listed in `NOT_COVERED` with the mechanic each lacks (R24 and R07, #775); a test makes it refuse each with a message that names the
mechanic, and another makes the lists together hold every route file of `examples/routes/`.

R13 plays about 100,000 orb uses per finish (its mean is 12,000 Chaos), so the run of this file plays only `CI_RUNS` of it and its standard
error is about a quarter of the mean (one play has a standard deviation about equal to the mean), so 4 standard errors catch only an error of about two to three times, and R13 is checked by the heavy run, not by CI; the real precision is a heavy run on GitHub through the dispatcher, which runs this file with
`NAIVE_RUNS` plays per runner, `NAIVE_SEED` (the runner's index) and `NAIVE_OUT` (a folder where each route leaves its tally), and
`python -m naive_crafter merge <folder>` pools the runners and judges the pool (docs/ci.md). #576 changes the start of R13 and R14 (their
targets); R13 is written here against main and stays valid when its mean moves, because the exact side is computed from the target as it is.

Rules: OR-4 (a target and a route take the guide's words; the goal is judged by the goal oracle), OR-20 (a known mechanic has one exact
chance, so the means are exact on the planner's side), OR-22 (the rules of the naive crafter carry their sources), OR-26 (a disagreement
is traced to a rule, not patched per case), OR-29 (an open disagreement is a strict xfail that names its issue).
Needs the cached dump (`CRAFTING_CACHE_DIR`); CI fetches it.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
import yaml
from abstraction_support import real_game_data
from naive_crafter import tally as t
from naive_crafter.craft import Laws, Unsupported
from naive_crafter.play import Gap, Judge, Player, lacking, read_route
from naive_crafter.world import load_world
from naive_planner_side import data_pin, inputs_of

from crafting_system.actions import DRAW_LABEL
from crafting_system.cli import evaluate_route, load_route, make_plan
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json"
KEYS = ROOT / "tests" / "reconcile" / "expected_keys.txt"
TARGETS = ROOT / "examples" / "targets"
ROUTES = ROOT / "examples" / "routes"

#            route id: (target and route file stem, plays in this file's run)
COVERED = {
    "R05": ("r05-strength-ring", 3000),
    "R08": ("r08-energy-shield-boots", 3000),
    "R09": ("r09-life-boots", 3000),
    "R10": ("r10-fractured-boots", 3000),
    "R11": ("r11-reservation-helmet", 3000),
    "R12": ("r12-lightning-amulet", 3000),
    "R13": ("r13-life-resist-belt", 16),
}
# the planner's mean of these two comes from the benchmark's heavy run (see the module docstring); plays in CI
BENCHMARKED = {
    "R04 with restart": ("r04-penetrating-quiver-restart", 12),
    "R14 with restart": ("r14-hunter-bow-restart", 100),
}
# the routes as the guides wrote them: a state has no rule or the game refuses the rule's action, so the route finishes with a chance below 1; plays in CI
GAPPED = {
    "R04": ("r04-penetrating-quiver", 2000),
    "R14": ("r14-hunter-bow", 2000),
}
# the routes this player cannot play yet, with the mechanic each lacks (the message of `Unsupported` must say it); filed as issues (OR-29).
NOT_COVERED: dict[str, tuple[str, tuple[str, ...]]] = {
    "R24": ("r24-avoid-shock-boots", ("Veiled Chaos Orb", "Unveil", "lock a side", "Harvest Add Remove Fire")),  # #775
    "R07": ("r07-minion-wand", ("Veiled Chaos Orb", "Unveil", "lock a side", "Corroded Fossil", "no bench option")),  # #775
}
RECORDED = ROOT / "tests" / "fixtures" / "naive_crafter" / "benchmark_means.json"
HEAVY = bool(os.environ.get("NAIVE_HEAVY"))
RUNS_OVERRIDE = int(os.environ["NAIVE_RUNS"]) if os.environ.get("NAIVE_RUNS") else None
SEED = int(os.environ.get("NAIVE_SEED", "0"))
OUT = Path(os.environ["NAIVE_OUT"]) if os.environ.get("NAIVE_OUT") else None


def route_labels(stem: str) -> list[str]:
    """The action labels of a route file, in the order the rules name them (plain YAML)."""
    document = yaml.safe_load((ROUTES / f"{stem}.yaml").read_text(encoding="utf-8"))
    seen: list[str] = []
    for rule in document["rules"]:
        if rule["do"] not in seen:
            seen.append(rule["do"])
    return seen


STEPS = [(route, label) for route, (stem, _) in COVERED.items() for label in route_labels(stem)]


@dataclass
class Played:
    route: str
    exact_mean: float
    exact_spend: dict[str, float]
    tally: t.Tally


def expected_spend(plan, policy) -> dict[str, float]:
    """The expected spend of each action label under the policy: the expected visits of each state times the cost of its action.

    The visits solve `N = e_start + P^T N` over the states of the policy; a successor that is not a state of the policy (the goal) absorbs.
    """
    states = list(policy)
    index = {state: i for i, state in enumerate(states)}
    transition = np.zeros((len(states), len(states)))
    for state, action in policy.items():
        total = sum(weight for _, weight in action.outcomes)
        for successor, weight in action.outcomes:
            if successor in index:
                transition[index[state], index[successor]] += weight / total
    start = np.zeros(len(states))
    start[index[plan.start]] = 1.0
    visits = np.linalg.solve((np.eye(len(states)) - transition).T, start)
    spend: dict[str, float] = {}
    for state, action in policy.items():
        spend[str(action.label)] = spend.get(str(action.label), 0.0) + float(visits[index[state]]) * action.cost
    return spend


@pytest.fixture(scope="module")
def played(request) -> Played:
    route_id = request.param
    stem, plays = COVERED[route_id]
    data = real_game_data()
    target = load_target(TARGETS / f"{stem}.yaml", data)
    plan = make_plan(data, target, load_price_file(PRICES), solve_it=False)
    result = evaluate_route(plan, load_route(ROUTES / f"{stem}.yaml", plan, data), data)
    assert result.gaps == () and result.risk.success_probability.value == pytest.approx(1.0), route_id
    spend = expected_spend(plan, result.policy)
    assert sum(spend.values()) == pytest.approx(result.risk.mean.value, rel=1e-9), "the chain's visits do not add up to risk.evaluate's mean"
    # The draw of a bought item's mods (ADR-0064) is free in the game and in the naive crafter (`World.opened_start`); the planner charges it 0.1 of the cheapest orb so that
    # the solver certifies (#657). The exact side leaves that price out, so both sides are of the same process; #657 removes it (R13: 0.0016 Chaos a draw).
    drawn = spend.get(DRAW_LABEL, 0.0)

    world = load_world(TARGETS / f"{stem}.yaml", PRICES, KEYS)
    judge = Judge(world)
    route = read_route((ROUTES / f"{stem}.yaml").read_text(encoding="utf-8"), world, judge)
    runs = RUNS_OVERRIDE or plays
    tally = t.simulate(Player(world, route, judge), runs, seed=555 * 1000 + SEED)
    if OUT is not None:
        OUT.mkdir(parents=True, exist_ok=True)
        document = {"route": route_id, "exact_mean": result.risk.mean.value - drawn, "exact_spend": {label: spent for label, spent in spend.items() if label != DRAW_LABEL}, "seed": SEED, "tally": tally.to_dict()}
        (OUT / f"naive-{route_id.replace(' ', '_')}-{SEED}.json").write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    return Played(route_id, result.risk.mean.value - drawn, spend, tally)


def recorded_for(route_id: str) -> dict:
    """The benchmark's numbers for a route (`benchmark_means.json`, written from a heavy run's `benchmark.json`)."""
    if not RECORDED.is_file():
        pytest.skip("tests/fixtures/naive_crafter/benchmark_means.json is not there yet")
    return json.loads(RECORDED.read_text(encoding="utf-8"))["routes"][route_id]


def play_world(stem: str, laws: Laws | None = None):
    world = load_world(TARGETS / f"{stem.removesuffix('-restart')}.yaml", PRICES, KEYS, laws=laws)
    judge = Judge(world)
    route = read_route((ROUTES / f"{stem}.yaml").read_text(encoding="utf-8"), world, judge)
    return Player(world, route, judge)


def leave_tally(route_id: str, document: dict) -> None:
    """Write the tally of a heavy run's runner for `python -m naive_crafter merge`."""
    if OUT is not None:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"naive-{route_id.replace(' ', '_')}-{SEED}.json").write_text(json.dumps({"route": route_id, "seed": SEED, **document}, sort_keys=True), encoding="utf-8")


@pytest.fixture(scope="module")
def benchmarked(request) -> Played:
    """A route whose planner mean is the benchmark's: the recorded number, and the naive tally."""
    route_id = request.param
    stem, plays = BENCHMARKED[route_id]
    real_game_data()
    recorded = recorded_for(route_id)
    tally = t.simulate(play_world(stem), RUNS_OVERRIDE or plays, seed=555 * 1000 + SEED)
    # The recorded mean carries the planner's price of the draw (ADR-0064, #657: 0.1 of the cheapest orb, 0.0016 Chaos for R14) once for each start of a play, about 18 starts: 0.03 Chaos of
    # 12,939, 2e-6 of the mean and 0.0004 of the standard error of the heavy run. It is not taken off here, because the record has no count of the starts; #657 removes it.
    leave_tally(route_id, {"exact_mean": recorded["mean_without_start"], "exact_spend": {}, "tally": tally.to_dict()})
    return Played(route_id, recorded["mean_without_start"], {}, tally)


@pytest.fixture(scope="module")
def gapped(request) -> tuple[str, dict, t.Tally]:
    """A route with gaps: the planner's recorded bracket of the chance of finishing, and the naive tally with its stuck plays."""
    route_id = request.param
    stem, plays = GAPPED[route_id]
    real_game_data()
    recorded = recorded_for(route_id)
    tally = t.simulate_finishing(play_world(stem), RUNS_OVERRIDE or plays, seed=555 * 1000 + SEED)
    leave_tally(route_id, {"exact_success": recorded["success_low"], "tally": tally.to_dict()})
    return route_id, recorded, tally


# --- the route's mean ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("played", list(COVERED), indirect=True)
def test_the_naive_mean_is_the_planners_mean_of_the_given_route(played):
    verdict = t.verdict_on(f"{played.route}, the mean cost of the given route", played.exact_mean, played.tally.mean_se())

    assert verdict.agrees, str(verdict)


@pytest.mark.parametrize("benchmarked", list(BENCHMARKED), indirect=True)
def test_the_naive_mean_is_the_benchmarks_mean_of_the_completed_route(benchmarked):
    verdict = t.verdict_on(f"{benchmarked.route}, the mean cost of the given route (the benchmark's)", benchmarked.exact_mean, benchmarked.tally.mean_se())

    assert verdict.agrees, str(verdict)


@pytest.mark.parametrize("gapped", list(GAPPED), indirect=True)
def test_the_share_of_plays_that_finish_lies_inside_the_planners_bracket(gapped):
    """The bracket is the planner's own `(low, high)` of its success probability (`risk/_evaluate.py`); the share is widened by K standard errors at the end it is outside of."""
    route_id, recorded, tally = gapped
    finished, total = tally.finishing()
    verdict = t.finishing_verdict(f"{route_id} as the guide wrote it, the chance of finishing", recorded["success_low"], finished, total, high=recorded["success_high"])

    assert verdict.agrees, str(verdict)


@pytest.mark.parametrize("route_id", list(GAPPED))
def test_the_naive_share_recorded_from_the_heavy_run_lies_inside_the_planners_bracket(route_id):
    recorded = recorded_for(route_id)
    heavy = recorded["naive_heavy"]
    verdict = t.finishing_verdict(
        f"{route_id}, the heavy run {heavy['run']}", recorded["success_low"], heavy["finished"], heavy["plays"], high=recorded["success_high"]
    )

    assert verdict.agrees, str(verdict)


@pytest.mark.xfail(strict=True, reason="#683: the planner prints the low end of its bracket as the success chance (0% for R14, whose own uses say about 10%); it flips when the fix is recorded")
@pytest.mark.parametrize("route_id", list(GAPPED))
def test_the_planners_printed_success_chance_is_the_naive_share(route_id):
    """The planner's printed success (`success_value`, recorded from its run) against the share of the heavy naive run, within K standard errors of that share."""
    recorded = recorded_for(route_id)
    heavy = recorded["naive_heavy"]
    share = heavy["finished"] / heavy["plays"]
    spread = (share * (1 - share) / heavy["plays"]) ** 0.5
    verdict = t.verdict_on(f"{route_id} as written, the planner's printed success", share, (recorded["success_value"], spread))

    assert verdict.agrees, str(verdict)


@pytest.mark.parametrize("route_id", list(BENCHMARKED))
def test_a_recorded_mean_is_without_the_start_price_as_the_naive_mean_is(route_id):
    """`benchmark` prints `mean + start price`; the naive mean leaves the first purchase out. The record keeps both and the start price, and they must add up."""
    recorded = recorded_for(route_id)

    assert "mean" not in recorded, "name the field: mean_without_start"
    assert recorded["start_price"] > 0
    assert recorded["mean_with_start"] - recorded["start_price"] == pytest.approx(recorded["mean_without_start"], rel=1e-9)
    assert recorded["inputs"]["costs"]["restart"] == pytest.approx(recorded["start_price"], rel=1e-9), "the start price is the price of a restart in this route"


@pytest.mark.parametrize("route_id", [*BENCHMARKED, *GAPPED])
def test_the_recorded_planner_numbers_are_of_the_game_data_pin_as_it_is(route_id):
    assert recorded_for(route_id)["pin"] == data_pin(), "the game data moved: record the planner side again"


@pytest.mark.parametrize("route_id", [*BENCHMARKED, *GAPPED])
def test_the_recorded_planner_numbers_are_of_the_files_and_prices_as_they_are(route_id):
    """Quick, so it runs in every CI run: the route file and the target by hash, and what one use of each action of the route costs. It does not see a change of the planner's code."""
    stem = {**BENCHMARKED, **GAPPED}[route_id][0]

    real_game_data()
    assert recorded_for(route_id)["inputs"] == inputs_of(stem), "the recorded planner numbers are of other files or prices: record them again (docs/ci.md)"


@pytest.mark.parametrize("benchmarked", list(BENCHMARKED), indirect=True)
def test_the_benchmarked_simulation_is_long_enough_to_say_something(benchmarked):
    mean, se = benchmarked.tally.mean_se()
    limit = 0.05 if HEAVY else 0.5  # a play of these has a standard deviation about equal to its mean: CI catches only a gross error, the heavy run a few per cent

    assert se <= limit * mean, f"{benchmarked.route}: {benchmarked.tally.n} plays give {mean:.5g} +- {se:.3g}"


# --- each step of the route ---------------------------------------------------------------------------------


@pytest.mark.parametrize(("played", "label"), [(route, label) for route, label in STEPS], indirect=["played"])
def test_each_step_costs_what_the_planner_says(played, label):
    """The spend of one action label (all its uses in a play): the step a disagreement would name."""
    exact = played.exact_spend.get(label, 0.0)
    verdict = t.verdict_on(f"{played.route}, step {label!r}", exact, played.tally.spend_mean_se(label))

    assert verdict.agrees, str(verdict)


@pytest.mark.parametrize("played", list(COVERED), indirect=True)
def test_the_planners_policy_takes_only_the_actions_the_route_file_names(played):
    stem, _ = COVERED[played.route]

    assert set(played.exact_spend) - {DRAW_LABEL} <= set(route_labels(stem))  # the draw of a bought item's mods is the market's, not a step the route file names (ADR-0064)


@pytest.mark.parametrize("played", list(COVERED), indirect=True)
def test_the_simulation_is_long_enough_to_say_something(played):
    """A standard error that is a fifth of the mean or more says nothing; the heavy run (NAIVE_RUNS) is for the longest route."""
    mean, se = played.tally.mean_se()
    limit = 0.5 if played.route == "R13" else 0.1  # R13 is judged by its heavy run (CI plays 16, a quarter of the mean, 4 standard errors catch only a factor of 2 to 3); the rest to a tenth

    assert se <= limit * mean, f"{played.route}: {played.tally.n} plays give {mean:.5g} +- {se:.3g}"


# --- the test can fail ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("played", ["R05", "R10", "R11"], indirect=True)
def test_a_wrong_count_of_mods_for_the_rare_reroll_makes_the_route_disagree_with_the_planner(played):
    """If the law of 4, 5 or 6 mods were 1:1:1 instead of 8:3:1, the naive mean would be far from the planner's: the comparison has the power to see it."""
    stem, _ = COVERED[played.route]
    world = load_world(TARGETS / f"{stem}.yaml", PRICES, KEYS, laws=Laws(rare=((4, 1), (5, 1), (6, 1))))
    judge = Judge(world)
    route = read_route((ROUTES / f"{stem}.yaml").read_text(encoding="utf-8"), world, judge)
    wrong = t.simulate(Player(world, route, judge), 3000, seed=7)
    verdict = t.verdict_on(f"{played.route} with the wrong law", played.exact_mean, wrong.mean_se())

    assert not verdict.agrees, str(verdict)
    assert verdict.distance > 10

# The rules of the draw, each turned off in turn, and a cheap covered route that must leave the 4-standard-error line because of it. Measured at
# 3,000 plays and seed 7 (distance in standard errors): no level gate moves R05 by 24 (R10 0.0, R11 1.6); no family exclusion moves R10 by 7.8
# and R11 by 11 (R05 3.4); a side chosen first instead of one pool moves R11 by 14.5 (R10 0.1, R05 1.2). Each rule moves at least one cheap route,
# so none is a rule the comparison cannot see; the routes that do not move are named so that nobody counts them as evidence for that rule.
MUTATIONS = [
    ("no level gate", Laws(level_gate=False), "R05"),
    ("no family exclusion", Laws(family_exclusion=False), "R10"),
    ("no family exclusion", Laws(family_exclusion=False), "R11"),
    ("a side chosen first, not one pool", Laws(one_pool=False), "R11"),
    # the laws of #608 and #609. R09 does not move when the block is off (0.66 standard errors at 3,000 plays and seed 7: the blocked Defence mods are few next to the boosted
    # Life ones), so the block is shown by R08 and by `test_naive_mechanics.py`, and R09 is not counted as evidence for it.
    ("no fossil boost", Laws(fossil_boost=False), "R08"),
    ("no fossil boost", Laws(fossil_boost=False), "R09"),
    ("no fossil block", Laws(fossil_block=False), "R08"),
    ("no Harvest guarantee", Laws(harvest_guarantee=False), "R12"),
]


@pytest.mark.parametrize(("played", "name", "laws"), [(route, name, laws) for name, laws, route in MUTATIONS], indirect=["played"])
def test_each_rule_of_the_draw_turned_off_moves_a_cheap_route_past_the_line(played, name, laws):
    stem, _ = COVERED[played.route]
    world = load_world(TARGETS / f"{stem}.yaml", PRICES, KEYS, laws=laws)
    judge = Judge(world)
    route = read_route((ROUTES / f"{stem}.yaml").read_text(encoding="utf-8"), world, judge)
    wrong = t.simulate(Player(world, route, judge), 3000, seed=7)
    verdict = t.verdict_on(f"{played.route} with {name}", played.exact_mean, wrong.mean_se())
    print(verdict)  # the distance, shown with -rP

    assert not verdict.agrees, str(verdict)



# The laws of #610 on the two routes that use them. A play of these is long, so the heavy run judges them (`NAIVE_HEAVY=1`, `NAIVE_MUT_RUNS` plays each, default 300); the units of
# `naive_crafter/test_naive_mechanics.py` show each law with an exact answer on a tiny ring. A mutated route that cannot finish (a play that goes on for `MUTANT_USES` uses, or
# meets a gap) is as far from the planner as a route can be and counts as killed.
MUTANT_USES = 3_000_000
# The Annulment one plays 1,000 (not 300): at 60 plays it was 2.14 standard errors from the planner's mean, so 300 plays are about 4.8, too near the line of 4 to be a test.
MUTATIONS_HEAVY = [
    ("no multimod", Laws(multimod=False), "R14 with restart", None),
    ("no metamod filter", Laws(metamod_filter=False), "R14 with restart", None),
    ("an Annulment may remove the fractured mod", Laws(annul_spares_fractured=False), "R04 with restart", 1000),
    ("no metamod filter", Laws(metamod_filter=False), "R04 with restart", None),
]
# Not here, because the two routes never reach the case (the heavy run of this PR gave the same mean to the last digit with each turned off): `fracture_needs_four`
# (the route annuls down to four mods and fractures there, so an item of fewer is never offered the orb) and `metamod_refuses_rerolls` (the rule of the essence asks for no crafted mod). Their mutation tests are the
# units of `naive_crafter/test_naive_mechanics.py`, with an exact answer on a tiny ring, and a route that reached the case would need one more rule of the guide's.


@pytest.mark.skipif(not HEAVY, reason="long: the heavy run judges these (NAIVE_HEAVY=1)")
@pytest.mark.parametrize(("benchmarked", "name", "laws", "runs"), [(route, name, laws, runs) for name, laws, route, runs in MUTATIONS_HEAVY], indirect=["benchmarked"])
def test_each_law_of_the_metamod_routes_turned_off_moves_the_route_past_the_line(benchmarked, name, laws, runs):
    stem, _ = BENCHMARKED[benchmarked.route]
    runs = runs or int(os.environ.get("NAIVE_MUT_RUNS", "300"))
    try:
        wrong = t.simulate(play_world(stem, laws), runs, seed=7 + SEED, max_uses=MUTANT_USES)  # a runner's own seed, so the pooled runners are independent samples
    except Gap as stuck:
        print(f"{benchmarked.route} with {name}: cannot finish ({stuck})")
        return
    verdict = t.verdict_on(f"{benchmarked.route} with {name}", benchmarked.exact_mean, wrong.mean_se())
    print(verdict)  # the distance, shown with -rP

    assert not verdict.agrees, str(verdict)


# --- the routes it cannot play -------------------------------------------------------------------------------


def test_the_covered_and_the_listed_routes_are_every_route_file():
    stems = {path.stem for path in ROUTES.glob("*.yaml")}
    listed = {stem for group in (COVERED, BENCHMARKED, GAPPED, NOT_COVERED) for stem, *_ in group.values()}

    assert stems == listed


@pytest.mark.parametrize("route", list(NOT_COVERED))
def test_a_route_with_a_mechanic_the_naive_crafter_lacks_is_refused_naming_it(route):
    stem, mechanics = NOT_COVERED[route]
    real_game_data()  # skips without the game data
    world = load_world(TARGETS / f"{stem.removesuffix('-restart')}.yaml", PRICES, KEYS)
    text = (ROUTES / f"{stem}.yaml").read_text(encoding="utf-8")

    missing = lacking(text, world)
    for mechanic in mechanics:
        assert any(mechanic in message for message in missing.values()), (mechanic, missing)
    with pytest.raises(Unsupported, match="lacks|does not know|no bench option"):
        read_route(text, world, Judge(world))
