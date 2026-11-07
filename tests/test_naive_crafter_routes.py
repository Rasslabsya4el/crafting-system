"""The naive crafter plays the guides' routes; its mean cost against `risk.evaluate`'s mean of the given route (ticket #555, audit TESTS-22 part 2).

`risk.evaluate` costs a given route on the planner's own outcomes (`cli/_route.py`, `evaluate_route`). `tests/naive_crafter/` plays the same
route file on concrete items by Monte Carlo with rules written from the published mechanics (it imports nothing of the planner; its guard is
`tests/naive_crafter/test_naive_independence.py`), at the same prices, from the same target file. The two must agree:

* the mean cost of the route (the start item bought at the start is not counted, a `restart` is), within `K` = 4 of the simulation's own
  standard errors, stated in `naive_crafter/tally.py`;
* the spend of each step of the route, the same, where the exact side is the planner's policy chain: the expected visits of each state
  (the linear equations of the chain) times the price of the action taken there, added up by action label.

A disagreement is a failing test that names the step. Nothing is widened to pass.

Covered, because their steps are plain spam: R05 (Deafening Essence of Rage), R10 (Shrieking Essence of Spite and a bench craft), R11
(Shrieking Essence of Loathing), R13 (Orbs of Alteration and Regal on a bought Magic belt since #576, a restart, a bench craft). The others are listed in
`NOT_COVERED` with the mechanic each lacks; a test makes the naive crafter refuse each of them with a message that names it, and another
makes the two lists together hold every route file of `examples/routes/`.

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
from naive_crafter.play import Judge, Player, lacking, read_route
from naive_crafter.world import load_world

from crafting_system.cli import evaluate_route, load_route, make_plan
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-11-07.json"
KEYS = ROOT / "tests" / "reconcile" / "expected_keys.txt"
TARGETS = ROOT / "examples" / "targets"
ROUTES = ROOT / "examples" / "routes"

#            route id: (target and route file stem, plays in this file's run)
COVERED = {
    "R05": ("r05-strength-ring", 3000),
    "R10": ("r10-fractured-boots", 3000),
    "R11": ("r11-reservation-helmet", 3000),
    "R13": ("r13-life-resist-belt", 16),
}
# the routes this player cannot play yet, with the mechanic each lacks (the message of `Unsupported` must say it); filed as issues (OR-29):
# fossils (R08, R09) #608, the Harvest reforge (R12) #609, Exalted, Annulment, Fracturing, metamods and Remove Crafted Mods (R04, R14) #610
NOT_COVERED = {
    "R04": ("r04-penetrating-quiver", ("Exalted Orb", "metamods", "Orb of Annulment", "Fracturing Orb")),
    "R04 with restart": ("r04-penetrating-quiver-restart", ("Exalted Orb", "metamods", "Orb of Annulment", "Fracturing Orb")),
    "R08": ("r08-energy-shield-boots", ("fossils",)),
    "R09": ("r09-life-boots", ("fossils",)),
    "R12": ("r12-lightning-amulet", ("Harvest reforge",)),
    "R14": ("r14-hunter-bow", ("Exalted Orb", "metamods", "Orb of Annulment", "Remove Crafted Mods")),
    "R14 with restart": ("r14-hunter-bow-restart", ("Exalted Orb", "metamods", "Orb of Annulment", "Remove Crafted Mods")),
}
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

    world = load_world(TARGETS / f"{stem}.yaml", PRICES, KEYS)
    judge = Judge(world)
    route = read_route((ROUTES / f"{stem}.yaml").read_text(encoding="utf-8"), world, judge)
    runs = RUNS_OVERRIDE or plays
    tally = t.simulate(Player(world, route, judge), runs, seed=555 * 1000 + SEED)
    if OUT is not None:
        OUT.mkdir(parents=True, exist_ok=True)
        document = {"route": route_id, "exact_mean": result.risk.mean.value, "exact_spend": spend, "seed": SEED, "tally": tally.to_dict()}
        (OUT / f"naive-{route_id}-{SEED}.json").write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    return Played(route_id, result.risk.mean.value, spend, tally)


# --- the route's mean ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("played", list(COVERED), indirect=True)
def test_the_naive_mean_is_the_planners_mean_of_the_given_route(played):
    verdict = t.verdict_on(f"{played.route}, the mean cost of the given route", played.exact_mean, played.tally.mean_se())

    assert verdict.agrees, str(verdict)


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

    assert set(played.exact_spend) <= set(route_labels(stem))


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
]


@pytest.mark.parametrize(("played", "name", "laws"), [(route, name, laws) for name, laws, route in MUTATIONS], indirect=["played"])
def test_each_rule_of_the_draw_turned_off_moves_a_cheap_route_past_the_line(played, name, laws):
    stem, _ = COVERED[played.route]
    world = load_world(TARGETS / f"{stem}.yaml", PRICES, KEYS, laws=laws)
    judge = Judge(world)
    route = read_route((ROUTES / f"{stem}.yaml").read_text(encoding="utf-8"), world, judge)
    wrong = t.simulate(Player(world, route, judge), 3000, seed=7)
    verdict = t.verdict_on(f"{played.route} with {name}", played.exact_mean, wrong.mean_se())

    assert not verdict.agrees, str(verdict)



# --- the routes it cannot play -------------------------------------------------------------------------------


def test_the_covered_and_the_listed_routes_are_every_route_file():
    stems = {path.stem for path in ROUTES.glob("*.yaml")}
    listed = {stem for stem, _ in COVERED.values()} | {stem for stem, _ in NOT_COVERED.values()}

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
