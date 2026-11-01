"""The simulator's nested runs against the solver on the REAL recombinator, at every grid point (ticket #222, ADR-0019 layer 2).

A small world of concrete items on the fixture amulets of `test_actions_recombinator` (two prefixes, `RP25` of weight 25 and
`RP1000a` of weight 1000, both wanted):

* from the empty item `E` the player can buy `A` (a magic amulet holding `RP25`, 40 chaos) or craft `B` (a magic amulet holding
  `RP1000a`, 3 chaos, chance 1/4, else nothing happens);
* from `A` the recombinator with a donor `B` (6 chaos, a real `actions.Recombinator`) and from `B` the recombinator with a donor
  `A`; the donor is a `Need` that begins as the bare base (`E`) and must become the wanted item, as the action's `inputs` say;
* the target holds both prefixes. The recombinator keeps one of the two (67%) or both (33%) and, when one, the weight at the
  exponent decides which: so the value of every state follows the grid point, and a retry that lands on the other item is a
  new state.

For each point of the grid of the selection exponent (`recombinator.alpha`, five values, ADR-0033) the world is solved with the
kernel taken at that point (`Acquisition` over the concrete items, `solve`) and the solver's policy is played on concrete items:
each donor is made by a nested run of the policy of its want, the recombinator is applied to the item in hand and the donor
that run made (the action holds the donor it was priced with and the input's `matches` checks the donor against it), and the
simulator samples every action at that reading (`simulate(..., reading=...)`). The simulated mean lies within five standard
errors of the solver's value at every point, and the values differ between points, so each point is a model of its own.
"""

import functools
from fractions import Fraction
from math import lcm

import pytest
from nested_support import nested_policy
from simulator_support import Draw
from test_actions_recombinator import ALPHA, DATA, make

from crafting_system.actions import Reading, Recombinator
from crafting_system.actions.recombinator import ALPHA_AXIS
from crafting_system.items import Rarity
from crafting_system.simulator import simulate
from crafting_system.solver import Acquisition, Action, Need, solve

GRID = ALPHA_AXIS.readings
RUNS = 20_000
WANTED = frozenset({"RP25", "RP1000a"})

EMPTY = make([], Rarity.NORMAL)
HAS_A = make(["RP25"], Rarity.MAGIC)
HAS_B = make(["RP1000a"], Rarity.MAGIC)
BOTH = make(["RP25", "RP1000a"], Rarity.RARE)

BUY_COST, CRAFT_COST, COMBINE_COST = 40.0, 3.0, 6.0
CRAFT_B = ((HAS_B, 1), (EMPTY, 3))
RECOMBINATORS = {"combine with B": Recombinator(HAS_B), "combine with A": Recombinator(HAS_A)}


def ids(item):
    return frozenset(entry.mod_id for entry in item.mods)


def is_target(item):
    return WANTED <= ids(item)


def reaches(item, want):
    return ids(item) == ids(want)


class Cached:
    """A recombinator that remembers its outcomes per item and reading: the result is the same, the runs are affordable."""

    def __init__(self, action):
        self.action, self.cache = action, {}

    def outcomes(self, data, item):
        return self.outcomes_under(data, item, None)

    def outcomes_under(self, data, item, reading):
        key = (item, reading)
        if key not in self.cache:
            self.cache[key] = self.action.outcomes_under(data, item, reading)
        return self.cache[key]


class Fixed:
    """A fake action (a purchase, a craft): one of `((item, weight), ...)`."""

    def __init__(self, row):
        self.row = row

    def outcomes(self, data, item):
        return Draw([item for item, _ in self.row], [weight for _, weight in self.row])


FAKE = {("buy A", EMPTY): Fixed(((HAS_A, 1),)), ("craft B", EMPTY): Fixed(CRAFT_B)}


def scaled(results):
    """Integer weights, in proportion, of the `(chance, item)` pairs of exact outcomes, equal items merged."""
    merged = {}
    for chance, item in results:
        merged[item] = merged.get(item, Fraction(0)) + chance
    denominator = lcm(*(chance.denominator for chance in merged.values()))
    return tuple((item, int(chance * denominator)) for item, chance in merged.items())


class World:
    """The solver's model of the world at one reading of the exponent: states are concrete items."""

    def __init__(self, reading):
        self.reading = reading

    def is_goal(self, state):
        return is_target(state)

    def actions(self, state):
        if state == EMPTY:
            return (
                Action("buy A", BUY_COST, ((HAS_A, 1),)),
                Action("craft B", CRAFT_COST, CRAFT_B),
            )
        label = {HAS_A: "combine with B", HAS_B: "combine with A"}.get(state)
        if label is None:
            return ()  # an item the player cannot use: a dead end (the recombinator never makes one here)
        action = RECOMBINATORS[label]
        outcomes = action.outcomes_under(DATA, state, self.reading)
        needs = tuple(Need(need.start, need.want) for need in action.inputs(DATA, state))
        return (Action(label, COMBINE_COST, scaled(outcomes.results), needs),)


def reading_at(alpha):
    return Reading.of({ALPHA: alpha})


@functools.cache
def solved(alpha):
    acquisition = Acquisition(World(reading_at(alpha)), reaches=reaches)
    return solve(acquisition, [acquisition.start(EMPTY)]), acquisition


def play(alpha, *, runs=RUNS, seed=3, **arguments):
    solution, _ = solved(alpha)
    actions = {label: Cached(action) for label, action in RECOMBINATORS.items()}
    policy = nested_policy(
        solution,
        actions=lambda state, label: actions[label] if label in actions else FAKE[(label, state)],
        state_of=lambda item: item,
        item_of=lambda state: state,
        reaches=reaches,
        goal=is_target,
        matches=lambda want, donor: ids(donor) == ids(want),
    )
    arguments.setdefault("reading", reading_at(alpha))
    return simulate(DATA, policy, EMPTY, is_target, runs=runs, seed=seed, **arguments)


@pytest.mark.parametrize("alpha", GRID, ids=lambda alpha: f"alpha={alpha}")
def test_the_simulated_mean_is_within_five_standard_errors_of_the_solver_at_every_grid_point(alpha):
    solution, acquisition = solved(alpha)
    value = solution.values[acquisition.start(EMPTY)]
    report = play(alpha)

    assert solution.error_bound < 1e-9
    assert report.successes == report.runs and report.stopped == report.unfinished == 0
    assert report.cost.agrees_with(value, sigmas=5.0), (report.cost, value)


@pytest.mark.parametrize("alpha", GRID, ids=lambda alpha: f"alpha={alpha}")
def test_the_policy_recombines_so_that_the_nested_runs_are_what_is_checked(alpha):
    solution, _ = solved(alpha)
    report = play(alpha, runs=2_000)

    assert any(action.extra_inputs for action in solution.policy.values())
    assert report.mean_nested_runs > 0.3  # a donor is made by a nested run, more than once in three runs


def test_the_value_follows_the_grid_point():
    values = [solved(alpha)[0].values[solved(alpha)[1].start(EMPTY)] for alpha in GRID]

    assert len(set(values)) == len(GRID)  # five readings, five models
    assert values == sorted(values) or values == sorted(values, reverse=True)  # the exponent moves the value one way


def test_the_grid_is_the_axis_of_the_action_and_the_donor_need_is_the_contract_s():
    assert GRID == (Fraction(2, 5), Fraction(7, 10), Fraction(1), Fraction(13, 10), Fraction(8, 5))
    need = RECOMBINATORS["combine with B"].inputs(DATA, HAS_A)[0]
    assert need.want == HAS_B and need.start == make([], Rarity.NORMAL)


def test_without_the_reading_the_plan_is_sampled_and_misses_an_off_plan_grid_point():
    alpha = GRID[0]
    solution, acquisition = solved(alpha)
    value = solution.values[acquisition.start(EMPTY)]
    plan = play(alpha, reading=None)  # sampled at the plan (alpha 1), not at 2/5

    assert not plan.cost.agrees_with(value, sigmas=5.0)
    assert plan.cost.value > value  # the plan's own optimum is the dearer one of the two readings (150.0 against 140.8)


def test_the_real_recombinator_gives_the_same_report_for_any_number_of_workers():
    one = play(Fraction(1), runs=2_000, block=200, workers=1)
    two = play(Fraction(1), runs=2_000, block=200, workers=2)

    assert one == two
