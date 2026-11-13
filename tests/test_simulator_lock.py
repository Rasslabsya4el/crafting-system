"""The simulator's Lock step (ticket #297, ADR-0057 layer 2, ADR-0054): every option is thrown on a copy of the item, then the acceptance set is applied.

* The mechanics on hand-made steps: every option draws on the item in hand on every Lock, the Lock's price is paid each
  time and an option's only when it is used, the best accepted result wins (ties to the earlier option), the fallback
  acts on the item as it was, a Lock with nothing accepted and no fallback stops the run, and the step budget counts the
  Lock and the use as one click each.
* Layer 2 (Done when): the solver's plan with a Lock (`solve_peek` on tiny Peek models: the hand test of ADR-0054 and seeded
  random models) is played on state-items, and the simulated mean lies within five standard errors of the solver's value.
* A burn loop (Done when): the fallback only returns to the Lock's state; the runs all end, and the simulated mean matches
  the solver's value and the closed form of the geometric number of Locks.

The simulator imports nothing of the solver; `lock_support` composes them. Seeds are fixed; five standard errors fail about
once in 1.7 million runs for another seed.
"""

from fractions import Fraction

import pytest
from lock_support import Draw, Kernel, burn_spec, simulator_lock_policy
from peek_oracles import PeekSpec, peek_model, random_peek_spec

from crafting_system.simulator import Lock, Step, simulate
from crafting_system.solver import solve_peek

RUNS = 20_000
SIGMAS = 5.0


class Recording:
    """A fake action that records the items it was asked about and draws from `row`."""

    def __init__(self, row, seen):
        self.row, self.seen = tuple(row), seen

    def outcomes(self, data, item):
        self.seen.append(item)
        return Draw(self.row)


def is_goal(item):
    return item == "goal"


# -- the mechanics ------------------------------------------------------------------------------------------------------


def test_every_option_is_thrown_on_the_item_in_hand_each_lock():
    seen = []
    a = Step(Recording((("goal", 1),), seen), 2.0)
    b = Step(Recording((("x", 1),), seen), 5.0)
    lock = Lock(10.0, (a, b), lambda option, item: 0 if item == "goal" else None)
    report = simulate(None, {"s": lock}.get, "s", is_goal, runs=3, seed=1)
    assert seen == ["s", "s"] * 3  # both options drawn on "s", every Lock
    assert report.costs == (12.0, 12.0, 12.0)  # the Lock and the used option only; b is looked at for free
    assert report.mean_steps == 2.0  # the Lock and the use


def test_the_best_accepted_result_wins_and_ties_go_to_the_earlier_option():
    first = Step(Kernel((("mid", 1),)), 1.0)
    second = Step(Kernel((("goal", 1),)), 3.0)
    rank = {(0, "mid"): 1, (1, "goal"): 0}
    report = simulate(None, {"s": Lock(10.0, (first, second), lambda a, item: rank.get((a, item)))}.get, "s", is_goal, runs=2, seed=1)
    assert report.costs == (13.0, 13.0)  # the second option holds the better pair
    tie = Lock(10.0, (Step(Kernel((("goal", 1),)), 1.0), Step(Kernel((("goal", 1),)), 3.0)), lambda a, item: 0)
    report = simulate(None, {"s": tie}.get, "s", is_goal, runs=2, seed=1)
    assert report.costs == (11.0, 11.0)


def test_the_fallback_acts_on_the_item_as_it_was():
    seen = []
    option = Step(Kernel((("bad", 1),)), 1.0)
    fallback = Step(Recording((("goal", 1),), seen), 4.0)
    report = simulate(None, {"s": Lock(10.0, (option,), lambda a, item: None, fallback)}.get, "s", is_goal, runs=2, seed=1)
    assert seen == ["s", "s"]
    assert report.costs == (14.0, 14.0)
    assert report.successes == 2


def test_nothing_accepted_and_no_fallback_stops_the_run():
    lock = Lock(10.0, (Step(Kernel((("bad", 1),)), 1.0),), lambda a, item: None)
    report = simulate(None, {"s": lock}.get, "s", is_goal, runs=2, seed=1)
    assert report.stopped == 2
    assert report.costs == (10.0, 10.0)


def test_the_step_budget_counts_the_lock_and_the_use():
    lock = Lock(10.0, (Step(Kernel((("goal", 1),)), 1.0),), lambda a, item: 0)
    report = simulate(None, {"s": lock}.get, "s", is_goal, runs=2, seed=1, max_steps=1)
    assert report.unfinished == 2  # the Lock took the one click; the use is not made
    assert report.costs == (10.0, 10.0)


def test_a_lock_checks_its_arguments():
    option = Step(Kernel((("goal", 1),)), 1.0)
    with pytest.raises(ValueError):
        Lock(10.0, (), lambda a, item: 0)
    with pytest.raises(ValueError):
        Lock(-1.0, (option,), lambda a, item: 0)
    with pytest.raises(ValueError):
        Lock(10.0, (option,), None)
    with pytest.raises(ValueError):
        Lock(10.0, ("not a step",), lambda a, item: 0)
    with pytest.raises(ValueError):
        Lock(10.0, (option,), lambda a, item: 0, "not a step")


# -- layer 2: the solver's plan with a Lock, played on items ------------------------------------------------------------


# ADR-0054's hand test: goal 0, middle 30, brick 400; A costs 1 (20/50/30%), B costs 2 (10/80/10%); a fallback worth 66
HAND = PeekSpec(
    3,
    {0: [], 1: [("finish", Fraction(30), [(3, 1)])], 2: [("restart", Fraction(400), [(3, 1)])]},
    0,
    Fraction(1),
    [("A", Fraction(1), [(3, 20), (1, 50), (2, 30)]), ("B", Fraction(2), [(3, 10), (1, 80), (2, 10)])],
    [("bench", Fraction(66), [(3, 1)])],
    0,
)


def actions_of(spec):
    model = peek_model(spec)
    return {state: tuple(model.actions(state)) for state in range(spec.size)}


_SOLVED = {}


def solved(spec):
    key = repr(spec)  # a spec holds lists and dicts: cached by its text
    if key not in _SOLVED:
        _SOLVED[key] = solve_peek(peek_model(spec), [0] if spec.state is None else [spec.state, *range(spec.size)])
    return _SOLVED[key]


def check_layer_two(spec, start, seed):
    solution = solved(spec)
    value = solution.values[start]
    policy = simulator_lock_policy(actions_of(spec), solution)
    report = simulate(None, policy, start, lambda item: item == spec.size, runs=RUNS, seed=seed)
    assert report.successes == RUNS
    assert report.cost.agrees_with(value, sigmas=SIGMAS), (report.cost, value)
    return report, solution


def test_the_hand_test_of_adr_0054_on_items():
    report, solution = check_layer_two(HAND, 0, seed=7)
    assert solution.values[0] == pytest.approx(24.97)  # 23.97 before the Lock's price of 1
    assert solution.policy[0].label == "lock"


def lock_taken(spec):
    if spec.state is None or spec.state not in solved(spec).reactions:
        return False
    action = solved(spec).policy.get(spec.state)
    return action is not None and action.label == "lock"


def finite_lock_seeds(count):
    found = []
    for seed in range(5000):
        spec = random_peek_spec(seed)
        if lock_taken(spec) and solved(spec).values[spec.state] < float("inf"):
            found.append(seed)
        if len(found) == count:
            return found
    raise AssertionError("too few seeded models take the Lock")


@pytest.mark.parametrize("seed", finite_lock_seeds(12))
def test_seeded_lock_plans_match_their_simulation(seed):
    spec = random_peek_spec(seed)
    check_layer_two(spec, spec.state, seed=seed)


# -- the burn loop ------------------------------------------------------------------------------------------------------


def test_a_burn_loop_ends_and_matches():
    spec = burn_spec(lock=Fraction(3), success=1, failure=4, option_cost=Fraction(1), burn=Fraction(1, 2))
    report, solution = check_layer_two(spec, 0, seed=11)
    assert solution.policy[0].label == "lock"
    # Locks ~ Geometric(1/5): mean 5 Locks, 4 burns and one use: 5 * 3 + 4 * 0.5 + 1 = 18
    assert solution.values[0] == pytest.approx(18.0)
    assert report.unfinished == 0 and report.stopped == 0
    assert report.mean_steps == pytest.approx(10.0, rel=0.05)  # a Lock and a burn per miss, a Lock and the use at the end


def test_simulation_is_repeatable():
    spec = burn_spec()
    policy = simulator_lock_policy(actions_of(spec), solved(spec))
    first = simulate(None, policy, 0, lambda item: item == 2, runs=500, seed=3)
    again = simulate(None, policy, 0, lambda item: item == 2, runs=500, seed=3)
    assert first.costs == again.costs
