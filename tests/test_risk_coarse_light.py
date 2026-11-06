"""The functions of `risk/_coarse.py` on chains of one to three states, with answers worked out by hand (ticket #413).

`test_risk_coarse.py` runs the coarse grid through `evaluate` on grids of thousands of bins; the measurement week (#399)
found that 29 of its 70 mutants survived it. Here each function is called on its own:

* `expected_visits` on chains whose visits are counted by hand (a geometric tail: a state is visited 1 / (1 - p) times);
* `whole_multiples`, `quantile_lower_bound`, `quantile_upper_bound` and the two grid tests on numbers in the module text;
* `choose_step` against an exact search written here from the module's own description (the steps `cost / m` of the
  costs that matter, the coarsest within `GAP_TARGET` of the mean, else the least gap within `GAP_LIMIT`), on `Fraction`s,
  with the costs powers of two so that no float rounding is in play, and on cases worked out by hand.
"""

import math
from fractions import Fraction

import numpy as np
import pytest
from risk_support import is_goal

from crafting_system.risk import _coarse
from crafting_system.risk._chain import build_chain
from crafting_system.solver import Action


def chain_of(policy):
    return build_chain(policy, "S", is_goal)


# Cost 0.5, success one time in two: 2 visits of S.
ONE_COST = {"S": Action("a", 0.5, (("goal", 1), ("S", 1)))}
# S costs 0.5 and leads to T; T costs 0.25 and ends in the goal or goes back to S, half and half: S and T are visited 2 times each.
TWO_COSTS = {"S": Action("a", 0.5, (("T", 1),)), "T": Action("b", 0.25, (("goal", 1), ("S", 1)))}
# A cheap orb (0.25) once per round, a dearer spam (0.5) that ends in the goal one time in two, else repeats, and a restart (1):
# per round S 1 visit, A 2 visits... worked out in `test_visits_of_a_chain_with_a_restart`.
CRAFT = {
    "S": Action("orb", 0.25, (("A", 1),)),
    "A": Action("spam", 0.5, (("goal", 1), ("A", 2), ("B", 1))),
    "B": Action("restart", 1.0, (("S", 1),)),
}


def test_visits_of_a_geometric_tail():
    states, visits = _coarse.expected_visits(chain_of(ONE_COST))

    assert states == [0]
    assert visits == pytest.approx([2.0], rel=1e-12)


def test_visits_of_a_chain_that_returns_to_its_start():
    states, visits = _coarse.expected_visits(chain_of(TWO_COSTS))

    assert states == [0, 1]
    assert visits == pytest.approx([2.0, 2.0], rel=1e-12)


def test_visits_of_a_chain_with_a_restart():
    # A is left to the goal, to B or to itself with chances 1/4, 1/4, 1/2: it is visited 2 times per entry and ends in B or
    # the goal half and half. A round visits S once, A twice, B half a time; rounds end in the goal with chance 1/2: twice as many.
    states, visits = _coarse.expected_visits(chain_of(CRAFT))

    assert states == [0, 1, 3]  # the states are numbered as met: S, A, the goal, B
    assert visits == pytest.approx([2.0, 4.0, 1.0], rel=1e-12)


def test_a_chain_where_no_state_can_finish_has_no_visits():
    assert _coarse.expected_visits(build_chain({}, "S", is_goal)) is None


def test_the_limit_on_the_number_of_states_is_inclusive(monkeypatch):
    monkeypatch.setattr(_coarse, "DENSE_STATES", 3)
    assert _coarse.expected_visits(chain_of(CRAFT)) is not None  # three states that can finish: at the limit

    monkeypatch.setattr(_coarse, "DENSE_STATES", 2)
    assert _coarse.expected_visits(chain_of(CRAFT)) is None


def test_a_state_that_never_leaves_in_floats_has_no_visits():
    policy = {"S": Action("use", 1.0, (("goal", 1), ("S", 10**30)))}  # leaves with chance 1e-30: 1 - p rounds to 0

    assert _coarse.expected_visits(chain_of(policy)) is None


# --- whole_multiples -----------------------------------------------------------------------------------------------


def test_a_cost_is_a_whole_multiple_when_it_is_at_least_one_step_and_a_whole_number_of_them():
    costs = np.array([0.1, 0.25, 0.3, 0.05, 0.0])

    found = _coarse.whole_multiples(costs, 0.1)

    assert found.tolist() == [True, False, True, False, False]  # 0.1 is one step, 0.25 two and a half, 0.3 three, 0.05 half a step, 0 none


def test_a_cost_equal_to_the_step_is_one_step():
    assert _coarse.whole_multiples(np.array([0.5]), 0.5).tolist() == [True]


def test_the_tolerance_is_relative_to_the_number_of_steps():
    # 1000.0000000001 steps is 1e-13 of 1000 away from a whole number: inside 1e-12 of the ratio, outside 1e-12 / ratio
    assert _coarse.whole_multiples(np.array([1000.0000000001]), 1.0).tolist() == [True]
    assert _coarse.whole_multiples(np.array([1000.00000001]), 1.0).tolist() == [False]  # 1e-11 of the ratio away


# --- the quantile bounds and the two grid tests ----------------------------------------------------------------------


def test_the_paley_zygmund_bound_on_a_constant_cost_is_the_cost_times_one_minus_the_root_of_one_minus_level():
    # variance 0: ratio = 1 - level = 0.25, root 0.5: the bound is mean / 2, lowered by 1e-9 of itself
    bound = _coarse.quantile_lower_bound(10.0, 0.0, 0.75)

    assert bound == pytest.approx(5.0 * (1 - 1e-9), rel=1e-15)
    assert bound < 5.0  # strictly below the true quantile, which is 10 (every cost is the mean)


def test_the_paley_zygmund_bound_with_a_variance():
    # E[C^2] = 200, ratio = 0.1 * 200 / 100 = 0.2
    assert _coarse.quantile_lower_bound(10.0, 100.0, 0.9) == pytest.approx(10.0 * (1 - math.sqrt(0.2)) * (1 - 1e-9), rel=1e-14)


def test_the_paley_zygmund_bound_is_zero_when_the_variance_is_too_large_to_say_anything():
    # ratio = 0.5 * (100 + 100) / 100 = 1.0 exactly (and larger for more variance): the bound is 0
    assert _coarse.quantile_lower_bound(10.0, 100.0, 0.5) == 0.0
    assert _coarse.quantile_lower_bound(10.0, 5000.0, 0.5) == 0.0


def test_the_cantelli_bound_is_the_mean_plus_the_root_of_variance_times_level_over_one_minus_level():
    assert _coarse.quantile_upper_bound(10.0, 100.0, 0.9) == pytest.approx(40.0, rel=1e-15)  # 10 + sqrt(100 * 9)
    assert _coarse.quantile_upper_bound(10.0, 0.0, 0.5) == 10.0


def test_the_ordinary_grid_may_miss_the_quantile_when_the_upper_bound_is_above_what_the_bins_cover():
    # the upper bound is 40
    assert _coarse.may_exceed_ordinary_grid(10.0, 100.0, 0.9, 0.5, 79) is True  # 79 bins of 0.5 cover 39.5
    assert _coarse.may_exceed_ordinary_grid(10.0, 100.0, 0.9, 0.5, 80) is False  # 40: it is covered
    assert _coarse.may_exceed_ordinary_grid(10.0, 100.0, 0.9, 0.5, 81) is False


def test_the_quantile_is_certainly_beyond_the_ordinary_grid_only_past_the_bins_with_a_hair_of_tolerance():
    lower = 5.0 * (1 - 1e-9)  # the Paley-Zygmund bound of mean 10, variance 0, level 0.75
    assert _coarse.beyond_ordinary_grid(10.0, 0.0, 0.75, 0.5, 9) is True  # 4.5 bins of cost are covered, 4.999999995 is certainly past
    assert _coarse.beyond_ordinary_grid(10.0, 0.0, 0.75, 0.5, 10) is False  # 5.0 is covered
    assert _coarse.beyond_ordinary_grid(10.0, 0.0, 0.75, lower, 1) is False  # equal to what the bins cover
    assert _coarse.beyond_ordinary_grid(10.0, 0.0, 0.75, lower * (1 - 1e-9), 1) is True
    assert _coarse.beyond_ordinary_grid(10.0, 0.0, 0.75, lower * (1 - 1e-13), 1) is False  # within the tolerance of 1e-12
    exactly = 4.999999994995  # x * (1 + 1e-12) is `lower` to the last bit: not past it, so not "certainly beyond"
    assert exactly * (1.0 + 1e-12) == lower
    assert _coarse.beyond_ordinary_grid(10.0, 0.0, 0.75, exactly, 1) is False


# --- choose_step against an exact search -----------------------------------------------------------------------------


def oracle_step(visits, mean, variance, level, max_bins, dense_work=1e11):
    """The step of the module text, by exact search: `visits` is {cost: expected visits}, all Fractions or ints.

    This re-implements the rule of the module text with the same constants (12 costs, 64 fractions, 0.02 and 0.1 of the mean, 1e11 cells),
    so it is a second reading of the text and not an independent source for the constants: a changed constant is told by the hand cases
    of this file (the cases above, and the tables `ONE_COST_BY_HAND` and `CRAFT_BY_HAND` below, worked out on paper), not by this oracle.
    """
    n = len(visits)
    horizon = mean + math.sqrt(variance * level / (1.0 - level))
    floor = horizon / max_bins
    shares = sorted(visits, key=lambda cost: -visits[cost] * cost)[:12]
    best = coarse = None
    for base in shares:
        for parts in range(1, 65):
            step = Fraction(base) / parts
            if float(step) < floor:
                break
            if horizon / float(step) * n * (n + 4) > dense_work:
                continue
            gap = float(step * sum(w for cost, w in visits.items() if not (cost / step >= 1 and cost / step == round(cost / step))))
            if best is None or gap < best[1]:
                best = (float(step), gap)
            if gap <= 0.02 * mean and (coarse is None or float(step) > coarse[0]):
                coarse = (float(step), gap)
    if coarse is not None:
        return coarse
    if best is not None and best[1] <= 0.1 * mean:
        return best
    return None


HALF, QUARTER = Fraction(1, 2), Fraction(1, 4)
ONE_COST_VISITS = {HALF: Fraction(2)}
TWO_COSTS_VISITS = {HALF: Fraction(2), QUARTER: Fraction(2)}
CRAFT_VISITS = {QUARTER: Fraction(2), HALF: Fraction(4), Fraction(1): Fraction(1)}
CHAINS = {"one": (ONE_COST, ONE_COST_VISITS), "two": (TWO_COSTS, TWO_COSTS_VISITS), "craft": (CRAFT, CRAFT_VISITS)}


def test_the_cost_of_the_chains_above_is_what_the_visits_say():
    # the means used below are the true means of these chains: 2 * 0.5; 2 * 0.5 + 2 * 0.25; 2 * 0.25 + 4 * 0.5 + 1
    assert sum(cost * visit for cost, visit in ONE_COST_VISITS.items()) == 1
    assert sum(cost * visit for cost, visit in TWO_COSTS_VISITS.items()) == Fraction(3, 2)
    assert sum(cost * visit for cost, visit in CRAFT_VISITS.items()) == Fraction(7, 2)


def test_one_cost_whose_every_fraction_is_whole_takes_the_coarsest_step_the_bins_allow():
    # every step cost / m is whole, gap 0: the coarsest is the cost itself (m = 1); a finer one is never taken instead
    assert _coarse.choose_step(chain_of(ONE_COST), 2.0, 0.0, 0.5, 4000) == (0.5, 0.0)


def test_a_step_below_horizon_over_bins_is_not_taken():
    assert _coarse.choose_step(chain_of(ONE_COST), 2.0, 0.0, 0.5, 3) is None  # floor 2/3 > 0.5: no step reaches it
    assert _coarse.choose_step(chain_of(ONE_COST), 2.0, 0.0, 0.5, 4) == (0.5, 0.0)  # floor 0.5: the step is not below it
    assert _coarse.choose_step(chain_of(ONE_COST), 2.0, 0.0, 0.5, 8) == (0.5, 0.0)


def test_the_variance_and_the_level_set_the_horizon():
    # horizon = 2 + sqrt(4 * 0.9 / 0.1) = 8, floor 8 / 16 = 0.5: the step 0.5 is just allowed; with a dividing variance it would be 2.1
    assert _coarse.choose_step(chain_of(ONE_COST), 2.0, 4.0, 0.9, 16) == (0.5, 0.0)
    assert _coarse.choose_step(chain_of(ONE_COST), 2.0, 4.0, 0.9, 15) is None  # floor 8 / 15 = 0.533 > 0.5
    assert _coarse.choose_step(chain_of(ONE_COST), 2.0, 4.0, 0.9, 40) == (0.5, 0.0)


def test_the_costs_are_ranked_by_visits_times_cost():
    # shares: the cost 0.5 (2 visits) 1.0, the cost 0.25 (2 visits) 0.5: the first one tried is 0.5. The gap of the step 0.5 is
    # 0.5 * 2 = 1.0 (0.25 is half a step): it is within 0.02 * 50 = 1.0 exactly, and the step 0.5 is coarser than 0.25
    assert _coarse.choose_step(chain_of(TWO_COSTS), 50.0, 0.0, 0.5, 100_000) == (0.5, 1.0)
    # a hair under: the gap 1.0 is then above 0.02 * 49.9, and the step 0.25 (gap 0) is the coarsest that is within the target
    assert _coarse.choose_step(chain_of(TWO_COSTS), 49.9, 0.0, 0.5, 100_000) == (0.25, 0.0)


def test_with_no_step_within_the_target_the_least_gap_within_the_limit_is_taken():
    # the quarter is in no list of steps once the floor is 0.4: only the step 0.5 (gap 1.0) is left. The target is 0.02 * 40 = 0.8,
    # the limit 0.1 * 40 = 4.0: the step is not within the target, but within the limit
    assert _coarse.choose_step(chain_of(TWO_COSTS), 40.0, 0.0, 0.5, 100) == (0.5, 1.0)
    # the limit is 0.1 * 10 = 1.0: the gap 1.0 is within it (inclusive); 0.1 * 9.9 = 0.99: it is not
    assert _coarse.choose_step(chain_of(TWO_COSTS), 10.0, 0.0, 0.5, 20) == (0.5, 1.0)
    assert _coarse.choose_step(chain_of(TWO_COSTS), 9.9, 0.0, 0.5, 20) is None


def test_the_fractions_of_a_cost_are_tried_up_to_sixty_four_of_them():
    # costs 1 and 65/64, one visit each... the only whole step below 1.0 within the target is 1/64 (gap 0): m = 64 of the cost 1
    policy = {"S": Action("a", 1.0, (("T", 1),)), "T": Action("b", 1.015625, (("goal", 1), ("S", 1)))}
    visits = {Fraction(1): Fraction(2), Fraction(65, 64): Fraction(2)}

    assert _coarse.choose_step(chain_of(policy), 0.4, 0.0, 0.5, 100_000) == oracle_step(visits, 0.4, 0.0, 0.5, 100_000) == (1 / 64, 0.0)


def line_of(costs):
    """A chain S -> s1 -> s2 ... -> goal, one deterministic action per state: every state is visited once."""
    policy = {}
    for i, cost in enumerate(costs):
        policy["S" if i == 0 else f"s{i}"] = Action(f"a{i}", cost, ((f"s{i + 1}" if i + 1 < len(costs) else "goal", 1),))
    return chain_of(policy)


def test_only_the_twelve_costs_with_the_most_visits_times_cost_give_steps():
    # thirteen costs, one visit each: the cheapest (0.125) is not tried. If the dearest were left out instead (ranking by visits / cost),
    # the coarsest step within the limit would be the cost 0.125 itself instead of 3/32 = 0.09375, a fraction of the cost 2.25
    costs = [0.125, 0.25, 0.375, 0.5625, 0.8125, 0.875, 0.9375, 1.0, 1.5, 1.75, 2.0625, 2.1875, 2.3125]
    visits = {Fraction(cost): Fraction(1) for cost in costs}

    found = _coarse.choose_step(line_of(costs), 8.0, 0.0, 0.5, 100)

    assert found == oracle_step(visits, 8.0, 0.0, 0.5, 100) == (0.09375, 0.75)


def test_the_sixty_fifth_fraction_of_a_cost_is_not_tried():
    # costs 65/64 and 33/32: both are whole multiples of 1/64, which is the 65th fraction of the first and the 66th of the second;
    # with a mean of 0.4 only a gap of 0 is within the target 0.008, and no step of the first 64 fractions has it
    costs = [65 / 64, 33 / 32]
    visits = {Fraction(cost): Fraction(1) for cost in costs}

    found = _coarse.choose_step(line_of(costs), 0.4, 0.0, 0.5, 100_000)

    assert found == oracle_step(visits, 0.4, 0.0, 0.5, 100_000)
    assert found is None or found[1] > 0  # not the gap-0 step 1/64


def test_with_no_step_in_the_target_the_first_of_two_equal_gaps_is_kept():
    # the means are made up to put every gap between the target and the limit; the step 0.625 (a fraction of 1.25) has the gap 1.25,
    # and the step 5/12 (a fraction of 1.25 too) has the same gap: the first one met stays
    found = _coarse.choose_step(line_of([1.0, 1.25, 1.875, 0.875]), 20.0, 0.0, 0.5, 50)

    assert found == (0.625, 1.25)


def test_with_no_step_in_the_target_a_gap_is_compared_with_the_best_gap_and_not_with_its_step():
    found = _coarse.choose_step(line_of([0.5, 0.75, 1.25, 0.125]), 30.0, 0.0, 0.5, 50)

    assert found == (0.625, 1.875)


@pytest.mark.parametrize("work,expected", [(239, None), (240, (0.5, 1.0)), (479, (0.5, 1.0)), (480, (0.5, 1.0))])
def test_the_dense_work_limit_is_inclusive_and_counts_cells_as_states_times_states_plus_four(monkeypatch, work, expected):
    # two states, horizon 10, the step 0.5: 10 / 0.5 = 20 bins * 2 * (2 + 4) cells = 240 multiply-adds; the step 0.25 costs twice that
    # and is the only finer step that is not ruled out by the gap (it would give gap 0)
    monkeypatch.setattr(_coarse, "DENSE_WORK", work)

    found = _coarse.choose_step(chain_of(TWO_COSTS), 10.0, 0.0, 0.5, 100_000)

    assert found == (expected if work < 480 else (0.25, 0.0))
    assert found == oracle_step(TWO_COSTS_VISITS, 10.0, 0.0, 0.5, 100_000, dense_work=work)


@pytest.mark.parametrize("name", sorted(CHAINS))
@pytest.mark.parametrize("mean", [0.5, 1.0, 1.5, 3.5, 12.0, 50.0, 400.0])
@pytest.mark.parametrize("variance,level,bins", [(0.0, 0.5, 40), (0.0, 0.9, 300), (2.0, 0.9, 80), (30.0, 0.99, 10_000)])
def test_choose_step_is_the_step_of_an_exact_search(name, mean, variance, level, bins):
    policy, visits = CHAINS[name]

    assert _coarse.choose_step(chain_of(policy), mean, variance, level, bins) == oracle_step(visits, mean, variance, level, bins)


def test_a_chain_with_no_visits_has_no_step():
    assert _coarse.choose_step(build_chain({}, "S", is_goal), 1.0, 0.0, 0.5, 100) is None


# --- the whole grid of settings by hand: two chains, every answer worked out on paper -----------------------------------------------

# The settings are (variance, level, bins); the horizon is mean + sqrt(variance * level / (1 - level)) and no step may be below horizon / bins.
SETTINGS = [(0.0, 0.5, 40), (0.0, 0.9, 300), (2.0, 0.9, 80), (30.0, 0.99, 10_000)]
MEANS = [0.5, 1.0, 1.5, 3.5, 12.0, 50.0, 400.0]

# ONE_COST: the one cost 1/2 is a whole multiple of each of its fractions 1/2 / m, so every step has the gap 0 and the coarsest is 1/2 itself;
# it is allowed when horizon / bins <= 1/2 (horizons: the mean, the mean, the mean + 4.24, the mean + 54.5; the answer is None otherwise).
ONE_COST_BY_HAND = {
    SETTINGS[0]: [(0.5, 0.0)] * 5 + [None, None],  # horizon = mean <= 20
    SETTINGS[1]: [(0.5, 0.0)] * 6 + [None],  # mean <= 150
    SETTINGS[2]: [(0.5, 0.0)] * 5 + [None, None],  # mean + 4.24 <= 40, so mean <= 35.7
    SETTINGS[3]: [(0.5, 0.0)] * 7,  # mean + 54.5 <= 5000
}

# CRAFT: costs 1/4 (2 visits), 1/2 (4) and 1 (1). The step 1 leaves the costs 1/4 and 1/2 off its multiples: gap 1 * (2 + 4) = 6; the step 1/2
# leaves the 1/4: gap 1/2 * 2 = 1; 1/3 gives 2; the step 1/4 is a whole divisor of all three: gap 0. The coarsest step with a gap of at most
# 0.02 * mean is 1/4 up to mean 12 (target 0.24), 1/2 at mean 50 (target 1.0, the gap 1 just fits), 1 at mean 400 (target 8 >= 6);
# when the floor horizon / bins is above 1/4 the step 1/4 is gone and the least gap within 0.1 * mean is taken.
CRAFT_BY_HAND = {
    SETTINGS[0]: [(0.25, 0.0)] * 4 + [(0.5, 1.0), None, None],  # mean 12: floor 12 / 40 = 0.3 > 1/4: the step 1/2, gap 1 <= 0.1 * 12 = 1.2
    SETTINGS[1]: [(0.25, 0.0)] * 5 + [(0.5, 1.0), None],  # mean 400: floor 4/3 > 1 = the coarsest step
    SETTINGS[2]: [(0.25, 0.0)] * 5 + [None, None],  # mean 50: floor (50 + 4.24) / 80 = 0.68, only the step 1 (gap 6 > 0.1 * 50 = 5)
    SETTINGS[3]: [(0.25, 0.0)] * 5 + [(0.5, 1.0), (1.0, 6.0)],
}


@pytest.mark.parametrize("setting", SETTINGS, ids=str)
@pytest.mark.parametrize("name,table", [("one", ONE_COST_BY_HAND), ("craft", CRAFT_BY_HAND)])
def test_choose_step_on_the_two_chains_is_the_table_worked_out_by_hand(name, table, setting):
    policy, _ = CHAINS[name]
    variance, level, bins = setting

    found = [_coarse.choose_step(chain_of(policy), mean, variance, level, bins) for mean in MEANS]

    assert found == table[setting]
