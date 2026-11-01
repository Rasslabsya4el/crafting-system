"""The lazy offer loop of ADR-0062 on the generic solver (ticket #212, B3 T2b).

`solve_lazily` takes the full model (every donor a candidate at every state), offers candidates as the solve needs them and
proves the rest unneeded with a lower bound. Done when, for the solver part: the pruned run equals the unpruned run (the
product with every candidate offered up front, which brute force and the linear programme agree with in
`test_donor_wants_reference.py`); the donors come from the model alone, with no seed; a bad bound is caught; the
`error_bound` it reports holds; and the loop refuses what it cannot read.
"""

import math

import pytest
from donor_world_support import TinyWorld, product_spec, world_of
from ssp_input_oracles import brute_force_inputs, lp_values_inputs

from crafting_system.solver import Action, LazySolution, Need, TabularModel, solve, solve_lazily

SEEDS = range(40)


def full_value(world):
    """The product with every donor offered up front: its values and its start."""
    solution, acquisition = world.solve(lambda state: world.donors())
    return solution, acquisition.start(())


def seeds(world):
    return {
        "none": None,
        "singles": lambda state, action: len(action.extra_inputs[0].want) == 1,
        "everything": lambda state, action: True,
    }


@pytest.mark.parametrize("name", ["none", "singles", "everything"])
@pytest.mark.parametrize("seed", SEEDS)
def test_the_lazy_run_equals_the_product_with_every_donor_offered_up_front(seed, name):
    world = world_of(seed)
    full, start = full_value(world)
    lazy = solve_lazily(world.full_model(), (), seed=seeds(world)[name])
    assert lazy.start == start
    if math.isinf(full.values[start]):
        assert math.isinf(lazy.value)
    else:
        assert lazy.value == pytest.approx(full.values[start], rel=1e-8)
    for state, value in lazy.values.items():  # every value the loop built is the value of the full model
        if math.isfinite(value) and state in full.values:
            assert value == pytest.approx(full.values[state], rel=1e-7, abs=1e-9)
    if name == "everything":  # nothing left to prove
        assert len(lazy.rounds) == 1 and lazy.offered_pairs == lazy.pairs
    assert lazy.offered_pairs <= lazy.pairs
    assert len(lazy.rounds) <= 4
    assert lazy.rounds[-1].added == 0 and all(round.added > 0 for round in lazy.rounds[:-1])


@pytest.mark.parametrize("seed", SEEDS)
def test_the_value_equals_brute_force_and_the_linear_programme_of_the_full_model(seed):
    world = world_of(seed)
    full, acquisition = world.solve(lambda state: world.donors())
    lazy = solve_lazily(world.full_model(), ())
    spec = product_spec(acquisition, acquisition.start(()))
    if all(math.isfinite(value) for value in full.values.values()):
        lp = lp_values_inputs(spec)
        assert lazy.value == pytest.approx(float(lp[lazy.start]), rel=1e-7)
    if math.prod(len(rows) for rows in spec[1].values()) <= 5000:  # brute force over every policy of a product this small
        best = brute_force_inputs(spec)
        if best[lazy.start] is not None:
            assert lazy.value == pytest.approx(float(best[lazy.start]), rel=1e-9)


def test_no_candidate_left_out_improves_any_value_of_the_lazy_solution():
    """The end test, from the other side: at every solved state each candidate the loop did not offer costs at least the value there."""
    for seed in SEEDS:
        world = world_of(seed)
        lazy = solve_lazily(world.full_model(), ())
        values, model = lazy.values, world.full_model()
        for (tag, want, state), value in values.items():
            if value == 0.0 or not math.isfinite(value):
                continue
            offered = lazy.offered.get(state, frozenset())
            for action in model.actions(state):
                if not action.extra_inputs or (action.label, action.extra_inputs) in offered:
                    continue
                total = sum(outcome.weight for outcome in action.outcomes)
                cost = action.cost + sum(values.get((tag, need.want, need.start), math.inf) for need in action.extra_inputs)
                cost += sum(outcome.weight / total * values.get((tag, want, outcome.state), math.inf) for outcome in action.outcomes)
                assert cost >= value * (1 - 1e-8) or not math.isfinite(cost) or all(
                    (tag, need.want, need.start) not in values for need in action.extra_inputs
                ), (seed, state, action.label)


def test_the_loop_leaves_donors_out_that_it_proves_unneeded():
    world = world_of(0)
    lazy = solve_lazily(world.full_model(), ())
    assert lazy.offered_pairs < lazy.pairs // 2


def test_the_seed_changes_the_rounds_and_never_the_answer():
    world = world_of(1)
    plain = solve_lazily(world.full_model(), ())
    fed = solve_lazily(world.full_model(), (), seed=lambda state, action: len(action.extra_inputs[0].want) == 1)
    assert plain.value == pytest.approx(fed.value, rel=1e-9)
    assert len(plain.rounds) >= len(fed.rounds)


def test_the_error_bound_covers_the_slack_and_a_slack_that_is_too_big_makes_a_visible_error():
    errors = []
    for seed in SEEDS:
        world = world_of(seed)
        full, start = full_value(world)
        for slack in (1e-9, 0.2, 0.9):
            lazy = solve_lazily(world.full_model(), (), slack=slack)
            assert lazy.slack == slack and lazy.error_bound == lazy.solution.error_bound + slack
            if math.isfinite(full.values[start]):
                error = abs(lazy.value - full.values[start]) / lazy.value  # the convention of `solve`: V (1 - e) <= V* <= V (1 + e)
                assert error <= lazy.error_bound
                if slack == 0.9:
                    errors.append(error)
    assert max(errors) > 1e-3  # the test does prune: with a slack of 0.9 some world loses a donor it needs


def test_a_donor_the_target_cannot_use_is_never_forced_in():
    """A want no sequence of actions reaches has an infinite value in the full model too; the loop does not offer donors to make it finite."""
    table = {
        "r": [Action("chaos", 1.0, (("g", 1), ("r", 1))), Action("graft", 1.0, (("g", 1),), (Need("start", "nowhere"),))],
        "start": [Action("again", 1.0, (("start", 1), ("other", 1)))],
        "other": [Action("again", 1.0, (("start", 1),))],
    }
    lazy = solve_lazily(TabularModel({"g"}, table), "r")
    assert lazy.value == pytest.approx(2.0)  # chaos until the goal, 1 / (1/2) tries
    assert lazy.offered_pairs == 0 and lazy.pairs == 1 and len(lazy.rounds) == 1


def test_a_candidate_the_solve_needs_is_offered_in_a_later_round_and_one_that_cannot_help_is_not():
    # r --cheap(1, goal 1/2, back 1/2) | graft(5 + the donor, goal)--> g; the donor is made in 3 (a bought item)
    def model(chaos_cost):
        return TabularModel(
            {"g"},
            {
                "r": [Action("chaos", chaos_cost, (("g", 1), ("r", 3))), Action("graft", 5.0, (("g", 1),), (Need("buy", "donor"),))],
                "buy": [Action("buy", 3.0, (("donor", 1),))],
            },
        )

    needed = solve_lazily(model(100.0), "r")  # chaos costs 100 x 4: the graft (5 + 3) wins, so it must be offered
    assert needed.value == pytest.approx(8.0) and len(needed.rounds) == 2 and needed.offered_pairs == 1
    unneeded = solve_lazily(model(1.0), "r")  # chaos costs 1 x 4 = 4: the graft's bound 5 + 3 is above it, so it stays out
    assert unneeded.value == pytest.approx(4.0) and len(unneeded.rounds) == 1 and unneeded.offered_pairs == 0
    assert needed.solution.policy["r" if False else needed.start].label == "graft"


def test_a_model_whose_every_policy_is_infinite_is_reported_infinite():
    # the only way to the goal needs two copies of what it makes
    table = {"a": [Action("make", 1.0, (("g", 1),), (Need("a", "b"), Need("a", "b")))], "b": [Action("make", 1.0, (("b", 1),))]}
    lazy = solve_lazily(TabularModel({"g"}, table), "a")
    full = solve(__import__("crafting_system.solver", fromlist=["Acquisition"]).Acquisition(TabularModel({"g"}, table)), [("in", __import__("crafting_system.solver", fromlist=["MAIN"]).MAIN, "a")])
    assert math.isinf(lazy.value) and math.isinf(next(iter(full.values.values())))


def test_what_the_loop_cannot_read_is_refused():
    base = {"r": [Action("graft", 1.0, (("g", 1),), (Need("r", "g"),))]}
    with pytest.raises(ValueError, match="slack"):
        solve_lazily(TabularModel({"g"}, base), "r", slack=1.0)
    with pytest.raises(ValueError, match="slack"):
        solve_lazily(TabularModel({"g"}, base), "r", slack=-0.1)
    with pytest.raises(TypeError, match="Need"):
        solve_lazily(TabularModel({"g"}, {"r": [Action("graft", 1.0, (("g", 1),), ("r",))]}), "r")
    twins = [Action("graft", 1.0, (("g", 1),), (Need("r", "g"),)), Action("graft", 2.0, (("g", 1),), (Need("r", "g"),))]
    with pytest.raises(ValueError, match="tell its candidates apart"):
        solve_lazily(TabularModel({"g"}, {"r": twins}), "r")


def test_the_result_is_a_value_of_the_main_target_with_its_product():
    world = world_of(2)
    lazy = solve_lazily(world.full_model(), (), seed=lambda state, action: True)
    assert isinstance(lazy, LazySolution)
    assert lazy.value == lazy.solution.values[lazy.start] == lazy.values[lazy.acquisition.start(())]
    assert lazy.rounds[0].product_states == len(lazy.values)
