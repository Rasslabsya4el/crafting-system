"""The interval driver over rule axes (`risk.solve_readings`, ticket #220; ADR-0012 amended, ADR-0022 reworded).

The cases, by the ticket's "Done when":

* the tiny recombinator case of the prototype (PR #116) reproduces its tables: W* = 23 for price set A, the interval
  [19; 23] for set B against 42 without recombinators;
* a case with a real gap (the best route for each reading is not the robust one) reports the gap;
* the interior extremes of the research #90 note (a route whose minimum, or maximum, sits at an inner grid point)
  are found, because the whole grid is evaluated;
* with no axis (one model) the result equals the plain solve.

Behind them a fuzz against exact brute force over every policy (`ssp_input_oracles`), on models whose readings differ in
weights and in which outcomes are possible.
"""

import itertools
import math
import random
from fractions import Fraction

import pytest
from ssp_input_oracles import evaluate_policy_exactly, policy_space, random_input_spec
from ssp_input_oracles import to_model as spec_model

from crafting_system.risk import has_inputs, solve_readings
from crafting_system.solver import Acquisition, Action, ConvergenceError, Need, TabularModel, solve

# the tiny recombinator case of the prototype: four item states, three readings of the selection rule (kQ, kP)
READINGS = {"equal (1,1)": (1, 1), "rare x2 (2,1)": (2, 1), "rare x5 (5,1)": (5, 1)}
PRICES_A = {"cc": 1, "bP": 3, "bQ": 8, "cr": 1, "cs": 2}
PRICES_B = {"cc": 2, "bP": 2, "bQ": 8, "cr": 1, "cs": 2}


class Tiny:
    """States E (empty), P, Q and PQ (the goal); a recombination needs the other prefix as a donor built from E."""

    def __init__(self, rule, prices, recombine=True):
        self.rule, self.p, self.recombine = rule, prices, recombine

    def is_goal(self, state):
        return state == "PQ"

    def actions(self, state):
        kq, kp = self.rule
        p = self.p
        if state == "E":
            return (
                Action("craft P", p["cc"], (("P", 1), ("E", 9))),
                Action("craft Q", p["cc"], (("Q", 1), ("E", 9))),
                Action("buy P", p["bP"], (("P", 1),)),
                Action("buy Q", p["bQ"], (("Q", 1),)),
            )
        if state in ("P", "Q"):
            other = "Q" if state == "P" else "P"
            found = [Action("craft " + other, p["cc"], (("PQ", 1), (state, 19)))]
            if self.recombine:
                outcomes = (("PQ", kq + kp), ("Q", 2 * kq), ("P", 2 * kp))
                found.append(Action("recombine", p["cr"], outcomes, (Need("E", other),)))
            found.append(Action("scour", p["cs"], (("E", 1),)))
            return tuple(found)
        return ()


def tiny_models(prices):
    acquisitions = {name: Acquisition(Tiny(rule, prices)) for name, rule in READINGS.items()}
    return {name: a for name, a in acquisitions.items()}, next(iter(acquisitions.values())).start("E")


def reachable_spec(model, start):
    """The `(goals, table)` of `ssp_input_oracles` for the states a product model reaches from `start`."""
    goals, table = set(), {}
    stack, seen = [start], {start}
    while stack:
        state = stack.pop()
        if model.is_goal(state):
            goals.add(state)
            continue
        entries = []
        for action in model.actions(state):
            entries.append(
                (action.label, Fraction(action.cost), [(t, w) for t, w in action.outcomes], list(action.extra_inputs))
            )
            for target in (*(t for t, w in action.outcomes if w), *action.extra_inputs):
                if target not in seen:
                    seen.add(target)
                    stack.append(target)
        table[state] = entries
    return goals, table


def robust_optimum(models, start):
    """`W*`: the least over every deterministic stationary policy of the largest exact cost over the readings."""
    specs = [reachable_spec(m, start) for m in models.values()]
    memos = [{} for _ in specs]
    best = math.inf
    for choice in policy_space(specs[0]):
        worst = Fraction(0)
        for spec, memo in zip(specs, memos):
            cost = evaluate_policy_exactly(spec, choice, start, memo)
            if cost is None:
                worst = math.inf
                break
            worst = max(worst, cost)
        best = min(best, worst)
    return float(best)


class TestTinyRecombinatorCase:
    def test_price_set_a_reproduces_the_prototype_tables(self):
        models, start = tiny_models(PRICES_A)
        report = solve_readings(models, start, plan="equal (1,1)", without=has_inputs)
        assert report.readings == ("equal (1,1)", "rare x2 (2,1)", "rare x5 (5,1)")
        assert {r: round(e.value, 9) for r, e in report.values.items()} == {
            "equal (1,1)": 23.0,
            "rare x2 (2,1)": 23.0,
            "rare x5 (5,1)": 21.666666667,
        }
        rows = {c: [round(report.table[c][r].value, 9) for r in report.readings] for c in report.readings}
        assert rows == {
            "equal (1,1)": [23.0, 23.0, 23.0],
            "rare x2 (2,1)": [23.0, 23.0, 23.0],
            "rare x5 (5,1)": [25.0, 23.333333333, 21.666666667],
        }
        assert report.plan.interval == pytest.approx((23.0, 23.0))
        assert report.robust.reading == "equal (1,1)"
        assert not report.robust_differs
        assert report.lower.value == pytest.approx(23.0)
        assert report.upper.value == pytest.approx(23.0)
        assert report.gap == pytest.approx(0.0, abs=1e-9)
        assert report.proven_optimal
        assert report.baseline.value.value == pytest.approx(23.0)

    def test_price_set_b_interval_against_the_route_without_recombinators(self):
        models, start = tiny_models(PRICES_B)
        report = solve_readings(models, start, plan="equal (1,1)", without=has_inputs)
        assert report.plan.interval == pytest.approx((19.0, 23.0))
        assert report.plan.best_reading == "rare x5 (5,1)"
        assert report.plan.worst_reading == "equal (1,1)"
        assert report.baseline.value.value == pytest.approx(42.0)
        assert report.baseline.value.value > report.plan.worst.value
        assert (report.lower.value, report.upper.value) == pytest.approx((23.0, 23.0))
        assert report.proven_optimal
        # the plan's route buys P and recombines: the baseline never touches an input
        assert report.plan.policy[("in", next(iter(models.values())).start("E")[1], "P")].label == "recombine"
        assert all(not a.extra_inputs for a in report.baseline.policy.values())

    @pytest.mark.parametrize("prices", [PRICES_A, PRICES_B], ids=["A", "B"])
    def test_the_bracket_holds_the_true_robust_optimum(self, prices):
        models, start = tiny_models(prices)
        report = solve_readings(models, start)
        w_star = robust_optimum(models, start)
        assert w_star == pytest.approx(23.0)
        assert report.lower.value <= w_star + 1e-9
        assert w_star <= report.upper.value + 1e-9
        assert report.lower.low <= w_star <= report.upper.high
        assert report.baseline is None

    def test_the_solves_and_the_plain_solve_agree(self):
        models, start = tiny_models(PRICES_B)
        report = solve_readings(models, start)
        for reading, model in models.items():
            alone = solve(model, [start])
            assert report.values[reading].value == alone.values[start]
            assert report.table[reading][reading].value == pytest.approx(alone.values[start], rel=1e-9)
            assert report.routes[reading].policy == alone.policy


# a state S with a gamble (cost 1, ends with weight w out of 10, else tries again: mean 10 / w) and a safe action
def gamble_model(w, safe=6):
    return TabularModel(
        ["goal"],
        {"S": [Action("gamble", 1, (("goal", w), ("S", 10 - w))), Action("safe", safe, (("goal", 1),))]},
    )


GRID = (0.4, 0.7, 1.0, 1.3, 1.6)


def grid_models(weights, safe=6):
    """A plan at alpha = 1 first, then the rest of the grid, each model the gamble with that reading's weight."""
    return {alpha: gamble_model(w, safe) for alpha, w in zip(GRID, weights)}


class TestInteriorExtremes:
    def test_a_minimum_at_an_inner_grid_point_is_found(self):
        # gamble cost 10 / w: 10, 2, 5, 10, 10. At alpha = 1 it costs 5 (plan: gamble, 5 < 6); the least cost is at 0.7
        report = solve_readings(grid_models([1, 5, 2, 1, 1]), "S", plan=1.0)
        assert report.plan.policy["S"].label == "gamble"
        assert report.plan.costs[1.0].value == pytest.approx(5.0)
        assert report.plan.best_reading == 0.7
        assert report.plan.interval == pytest.approx((2.0, 10.0))
        # the two ends alone give [10; 10] (a wrong answer) and the plan reading alone [5; 5]
        assert report.plan.costs[0.4].value == pytest.approx(10.0)
        assert report.plan.costs[1.6].value == pytest.approx(10.0)

    def test_a_maximum_at_an_inner_grid_point_is_found_and_names_a_better_worst_case(self):
        # gamble cost 10 / w: 2, 10, 10/3, 2, 2: the worst reading of the plan's route is 0.7, an inner point
        report = solve_readings(grid_models([5, 1, 3, 5, 5]), "S", plan=1.0)
        assert report.plan.policy["S"].label == "gamble"
        assert report.plan.worst_reading == 0.7
        assert report.plan.interval == pytest.approx((2.0, 10.0))
        # the safe action costs 6 under every reading: it has the smallest worst case
        assert report.robust_differs
        assert report.robust.reading == 0.7
        assert report.robust.policy["S"].label == "safe"
        assert report.robust.interval == pytest.approx((6.0, 6.0))
        assert report.upper.value == pytest.approx(6.0)
        assert report.lower.value == pytest.approx(6.0)
        assert report.proven_optimal

    def test_a_tie_in_the_worst_case_keeps_the_plan(self):
        report = solve_readings(grid_models([2, 2, 2, 2, 2]), "S", plan=1.0)
        assert report.robust.reading == 1.0
        assert not report.robust_differs


class TestARealGap:
    """Reading 1 prefers A (10 against 14), reading 2 prefers B; C costs 12 under both. The optimum of each reading
    costs 14 under the other, so the candidates give 14; the true robust optimum is 12 (the policy C); the bracket
    is [10; 14] and the report says so instead of claiming a route optimal."""

    @staticmethod
    def models():
        def one(a, b):
            return TabularModel(
                ["goal"],
                {
                    "S": [
                        Action("A", a, (("goal", 1),)),
                        Action("B", b, (("goal", 1),)),
                        Action("C", 12, (("goal", 1),)),
                    ]
                },
            )

        return {"r1": one(10, 14), "r2": one(14, 10)}

    def test_the_gap_is_reported(self):
        report = solve_readings(self.models(), "S")
        assert report.lower.value == pytest.approx(10.0)
        assert report.upper.value == pytest.approx(14.0)
        assert report.gap == pytest.approx(4.0)
        assert not report.proven_optimal
        assert report.robust.policy["S"].label == "A"
        assert report.plan.interval == pytest.approx((10.0, 14.0))
        assert report.table["r2"]["r1"].value == pytest.approx(14.0)
        # the true optimum lies inside the bracket
        w_star = robust_optimum(self.models(), "S")
        assert w_star == pytest.approx(12.0)
        assert report.lower.value <= w_star <= report.upper.value


class TestNoAxis:
    def test_one_model_gives_the_plain_solve_on_random_models(self):
        compared = 0
        for seed in range(80):
            spec = random_input_spec(seed)
            model = spec_model(spec)
            try:
                alone = solve(model, [0])
            except ConvergenceError:
                continue
            report = solve_readings({None: model}, 0)
            assert report.values[None].value == alone.values[0]
            assert report.plan.reading is None
            assert report.plan.policy == alone.policy
            assert report.robust is report.plan
            assert report.baseline is None
            if math.isinf(alone.values[0]):
                assert math.isinf(report.plan.interval[1])
                continue
            compared += 1
            assert report.plan.costs[None].value == pytest.approx(alone.values[0], rel=1e-8)
            assert report.plan.interval[0] == report.plan.interval[1]
            assert report.lower.value == alone.values[0]
            assert report.upper.value == pytest.approx(alone.values[0], rel=1e-8)
            assert report.proven_optimal
        assert compared > 30

    def test_the_plan_is_the_only_solve(self):
        calls = []

        class Counting:
            def is_goal(self, state):
                return state == "goal"

            def actions(self, state):
                calls.append(state)
                return (Action("go", 2, (("goal", 1), ("S", 1))),)

        report = solve_readings({"only": Counting()}, "S")
        assert calls == ["S"]
        assert report.plan.interval == pytest.approx((4.0, 4.0))


class TestReadingsThatDiffer:
    def test_a_state_only_one_reading_reaches_is_added_to_the_candidates(self):
        # reading r2 can also land on state T; the candidate of r1 never saw T and must be completed
        def model(extra):
            table = {
                "S": [Action("go", 1, (("goal", 1), ("S", 1), ("T", extra)))],
                "T": [Action("fix", 3, (("goal", 1),)), Action("worse", 5, (("goal", 1),))],
            }
            return TabularModel(["goal"], table)

        report = solve_readings({"r1": model(0), "r2": model(2)}, "S")
        assert report.values["r1"].value == pytest.approx(2.0)
        assert report.table["r1"]["r1"].value == pytest.approx(2.0)
        assert math.isfinite(report.table["r1"]["r2"].value)
        # r2: S -> goal 1/4, S 1/4, T 1/2: V = (1 + 0.5 * 3) / 0.75... solved exactly: V_S = 1 + 0.25 V_S + 0.5 (3)
        assert report.values["r2"].value == pytest.approx((1 + 0.5 * 3) / 0.75)
        assert report.table["r1"]["r2"].value == pytest.approx((1 + 0.5 * 3) / 0.75)

    def test_an_action_missing_under_another_reading_leaves_the_candidate_stuck_there(self):
        only_r1 = TabularModel(
            ["goal"], {"S": [Action("special", 1, (("goal", 1),)), Action("plain", 9, (("goal", 1),))]}
        )
        only_plain = TabularModel(["goal"], {"S": [Action("plain", 9, (("goal", 1),))]})
        report = solve_readings({"r1": only_r1, "r2": only_plain}, "S")
        assert report.values["r1"].value == pytest.approx(1.0)
        assert math.isinf(report.table["r1"]["r2"].value)
        assert report.plan.interval[1] == math.inf
        # the other candidate (plain) works under both: the robust route
        assert report.robust.reading == "r2"
        assert report.upper.value == pytest.approx(9.0)
        assert report.lower.value == pytest.approx(9.0)

    def test_an_infinite_reading_makes_the_bracket_infinite(self):
        dead = TabularModel(["goal"], {"S": []})
        fine = TabularModel(["goal"], {"S": [Action("go", 1, (("goal", 1),))]})
        report = solve_readings({"a": fine, "b": dead}, "S")
        assert math.isinf(report.lower.value) and math.isinf(report.upper.value)
        assert report.gap == 0.0
        assert not report.proven_optimal  # nothing can be built under reading b: no route is "optimal"
        assert report.plan.worst.value == math.inf

    def test_labels_that_name_different_actions_are_refused(self):
        one = TabularModel(["goal"], {"S": [Action("x", 1, (("goal", 1),)), Action("x", 2, (("goal", 1),))]})
        two = TabularModel(["goal"], {"S": [Action("x", 1, (("goal", 1),))]})
        with pytest.raises(ValueError, match="share the label"):
            solve_readings({"a": two, "b": one}, "S")

    def test_the_start_may_be_a_goal(self):
        report = solve_readings({"a": gamble_model(5), "b": gamble_model(2)}, "goal")
        assert report.plan.interval == (0.0, 0.0)
        assert report.proven_optimal


class TestArguments:
    def test_no_model_is_refused(self):
        with pytest.raises(ValueError, match="at least one"):
            solve_readings({}, "S")

    def test_an_unknown_plan_reading_is_refused(self):
        with pytest.raises(ValueError, match="plan reading"):
            solve_readings({"a": gamble_model(5)}, "S", plan="b")

    def test_none_can_be_a_reading_and_the_default_plan_is_the_first(self):
        report = solve_readings({"a": gamble_model(5), None: gamble_model(2)}, "S")
        assert report.plan.reading == "a"
        report = solve_readings({"a": gamble_model(5), None: gamble_model(2)}, "S", plan=None)
        assert report.plan.reading is None

    def test_the_plan_comes_first_whatever_the_order_given(self):
        report = solve_readings({"a": gamble_model(5), "b": gamble_model(2), "c": gamble_model(4)}, "S", plan="b")
        assert report.readings == ("b", "a", "c")
        assert report.plan.reading == "b"


def reading_specs(seed, count=3):
    """`count` readings of one random spec: the same states and labels, weights and supports redrawn per reading."""
    goals, table = random_input_spec(seed)
    rng = random.Random(f"readings-{seed}")
    specs = [(goals, table)]
    for _ in range(count - 1):
        other = {}
        for state, actions in table.items():
            redrawn = []
            for label, cost, outcomes, inputs in actions:
                weights = [rng.choice([0, 0, 1, 2, 5, 9]) for _ in outcomes]
                if not any(weights):
                    weights[rng.randrange(len(weights))] = 1
                redrawn.append((label, cost, [(t, w) for (t, _), w in zip(outcomes, weights)], list(inputs)))
            other[state] = redrawn
        specs.append((goals, other))
    return specs


@pytest.mark.parametrize("seed", range(120))
def test_fuzz_against_brute_force(seed):
    specs = reading_specs(seed)
    models = {f"r{i}": spec_model(spec) for i, spec in enumerate(specs)}
    start = 0
    try:
        report = solve_readings(models, start)
    except ConvergenceError:
        pytest.skip("the solver cannot decide a component of this instance")
    memos = [{} for _ in specs]
    names = list(models)

    def exact(spec, memo, choice):
        return evaluate_policy_exactly(spec, choice, start, memo)

    # the optimum of every reading, and the exact cost of every candidate under every reading
    for k, (spec, memo) in enumerate(zip(specs, memos)):
        best = min(
            (c for c in (exact(spec, memo, ch) for ch in policy_space(spec)) if c is not None), default=None
        )
        got = report.values[names[k]].value
        if best is None:
            assert math.isinf(got)
        else:
            assert got == pytest.approx(float(best), rel=1e-8)
    for c, c_name in enumerate(names):
        route = report.routes[c_name]
        choice = {
            state: next(i for i, a in enumerate(specs[c][1][state]) if a[0] == action.label)
            for state, action in route.policy.items()
        }
        for r, r_name in enumerate(names):
            spec = specs[r]
            full = {s: choice.get(s) for s in spec[1]}
            if math.isinf(report.values[c_name].value):
                continue  # no policy of that reading: nothing to compare
            truth = exact(spec, memos[r], full)
            ours = report.table[c_name][r_name].value
            if truth is None:
                assert math.isinf(ours)
            else:
                assert ours == pytest.approx(float(truth), rel=1e-8)
    # the bracket holds the true robust optimum
    w_star = math.inf
    for choice in policy_space(specs[0]):
        worst = Fraction(0)
        for spec, memo in zip(specs, memos):
            cost = exact(spec, memo, choice)
            if cost is None:
                worst = math.inf
                break
            worst = max(worst, cost)
        w_star = min(w_star, float(worst))
    assert report.lower.value <= w_star * (1 + 1e-8) + 1e-12
    assert w_star <= report.upper.value * (1 + 1e-8) + 1e-12
    # every candidate's table row is its cost: the upper end is the best worst case among the candidates
    worst_cases = [max(report.table[c][r].value for r in names) for c in names]
    assert report.upper.value == pytest.approx(min(worst_cases), rel=1e-9) or math.isinf(report.upper.value)
    # the plan's interval is the range of its row
    row = [report.table[names[0]][r].value for r in names]
    assert report.plan.interval == (min(row), max(row))
    for a, b in itertools.combinations(names, 2):
        assert report.table[a][b].low <= report.table[a][b].value <= report.table[a][b].high
