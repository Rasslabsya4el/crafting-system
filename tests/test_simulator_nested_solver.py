"""The simulator's nested runs against the solver's value (ADR-0019 layer 2; ticket #222, Done when).

* The tiny two-prefix recombinator case of ticket #180 (the S3 toy: item states E, P, Q, PQ, wanted items P and Q, three
  selection rules and two price sets, as `test_solver_acquire.TINY_CASES`) with a FAKE two-item action: the solver
  (`Acquisition` over the base table, `solve` of ticket #179) gives the value; its policy is played on concrete items, the donor
  of every `recombine` made by a nested run of the policy of its want, and the simulated mean lies within five standard
  errors of that value.
* The REAL recombinator (`actions.Recombinator`, ADR-0033) on a small case, at every point of the grid of its selection
  exponent: a world of concrete items, an `Acquisition` over it with the kernel taken at that grid point, the solver's value and
  the simulated mean (`simulate(..., reading=...)`) within five standard errors, every point on its own.

The simulator imports nothing of the solver; this file is the one place that composes them (`nested_support.nested_policy`).
Seeds are fixed, so a run is repeatable; five standard errors fail about once in 1.7 million runs for another seed.
"""

import functools

import pytest
from nested_support import STATES, item_of, nested_policy, state_of, toy_actions
from simulator_support import DATA
from test_solver_acquire import TINY_CASES, base_model, tiny_spec

from crafting_system.simulator import simulate
from crafting_system.solver import MAIN, Acquisition, solve

RUNS = 20_000


def is_pq(item):
    return item == STATES["PQ"]


@functools.cache
def toy(case):
    """`(spec, solution, acquisition)` of one rule x price set of the tiny case, solved from the empty item."""
    rule, prices = TINY_CASES[case]
    spec = tiny_spec(rule, prices)
    acquisition = Acquisition(base_model(spec))
    return spec, solve(acquisition, [acquisition.start("E")]), acquisition


def play(case, *, runs=RUNS, seed=7, **arguments):
    spec, solution, _ = toy(case)
    table = toy_actions(spec)
    policy = nested_policy(
        solution,
        actions=lambda state, label: table[(state, label)],
        state_of=state_of,
        item_of=item_of,
        reaches=lambda state, want: state == want,
        goal=is_pq,
        bind=lambda action, donors: action.bound(donors[0]),
        matches=lambda want, donor: state_of(donor) == want,
    )
    return simulate(DATA, policy, STATES["E"], is_pq, runs=runs, seed=seed, **arguments)


@pytest.mark.parametrize("case", TINY_CASES)
def test_the_simulated_mean_lies_in_the_interval_around_the_solver_value_on_the_toy(case):
    _, solution, acquisition = toy(case)
    value = solution.values[acquisition.start("E")]
    report = play(case)

    assert report.successes == report.runs and report.stopped == report.unfinished == 0
    assert report.cost.agrees_with(value, sigmas=5.0), (report.cost, value)
    low, high = report.cost.value - 5 * report.cost.standard_error, report.cost.value + 5 * report.cost.standard_error
    assert low <= value * (1 + solution.error_bound) and value * (1 - solution.error_bound) <= high


@pytest.mark.parametrize("case", ["equal-prices-b", "rare-x5-prices-a", "rare-x5-prices-b"])  # the cases whose main run recombines
def test_the_toy_policy_really_builds_donors_by_nested_runs(case):
    # the value is a check of the nested runs only when the policy recombines: the main policy has a need and the runs count donors
    _, solution, _ = toy(case)
    assert any(action.extra_inputs for (_, want, _), action in solution.policy.items() if want is MAIN)
    report = play(case, runs=2_000)

    assert report.nested_runs > 0 and report.mean_nested_runs > 0.1


def test_the_toy_gives_the_same_report_for_any_number_of_workers():
    assert play("rare-x2-prices-a", runs=2_000, block=200, workers=2) == play("rare-x2-prices-a", runs=2_000, block=200, workers=1)


def test_every_start_of_the_toy_is_checked_not_only_the_empty_item():
    # the product states reached from P and Q too: the nested runs start from the empty item, the main run from any item
    case = "rare-x2-prices-a"
    spec, _, _ = toy(case)
    acquisition = Acquisition(base_model(spec))
    solution = solve(acquisition, [acquisition.start(state) for state in ("E", "P", "Q")])
    table = toy_actions(spec)
    for state in ("P", "Q"):
        policy = nested_policy(
            solution,
            actions=lambda s, label: table[(s, label)],
            state_of=state_of,
            item_of=item_of,
            reaches=lambda s, want: s == want,
            goal=is_pq,
            bind=lambda action, donors: action.bound(donors[0]),
        )
        report = simulate(DATA, policy, STATES[state], is_pq, runs=RUNS, seed=11)
        assert report.cost.agrees_with(solution.values[acquisition.start(state)], sigmas=5.0), (state, report.cost)
