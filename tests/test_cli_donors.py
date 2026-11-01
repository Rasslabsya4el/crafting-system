"""The planner's actions with donors, solved by the lazy offer loop (ticket #212, B3 T2b; ADR-0062, ADR-0022, ADR-0031).

Done when: on the #210 toy (`ToyGraft`, defined only in tests) the solver gets its donors from the target alone and equals
brute force over all donors offered up front; the pruned run equals the unpruned run. The toy needs the forges of
`donor_toy_support` to make its donor; `ToyDearGraft` is the same graft with a donor that is dearer to make.
"""

import math

import pytest
from abstraction_pool import DAMAGE_1, LIFE_1, MANA_1
from contract_support import CONTRACT_DATA, fixture_items
from donor_toy_support import GOAL_PAIR, ToyDearGraft, dear_want, toy_kinds, toy_problem
from donor_world_support import product_spec
from inputs_support import ToyGraft, donor_want
from ssp_input_oracles import brute_force_inputs

from crafting_system.abstraction import Goal, Wanted
from crafting_system.actions import Need
from crafting_system.cli._donors import DonorModel, solve_with_donors, takes_inputs
from crafting_system.cli._offers import isolated_feeder


@pytest.fixture(scope="module", autouse=True)
def toy():
    with toy_kinds():
        yield


def everything(need):
    return True


# --- the seed ------------------------------------------------------------------------------------


def test_an_isolated_feeder_is_a_donor_made_only_of_mods_the_goal_names():
    seed = isolated_feeder(GOAL_PAIR)
    item = fixture_items()["rare_junk"]
    assert seed(ToyGraft().inputs(CONTRACT_DATA, item)[0])  # the damage and the mana leech: both are the target
    assert not seed(ToyDearGraft().inputs(CONTRACT_DATA, item)[0])  # a life prefix is not
    assert not isolated_feeder(Goal((Wanted(frozenset({DAMAGE_1})),)))(ToyGraft().inputs(CONTRACT_DATA, item)[0])
    assert isolated_feeder(Goal((Wanted(frozenset({DAMAGE_1, MANA_1, LIFE_1})),)))(Need(donor_want(), dear_want()))


def test_only_an_action_whose_kind_declares_inputs_is_asked_for_them():
    assert takes_inputs(ToyGraft()) and takes_inputs(ToyDearGraft())
    from crafting_system.actions import ChaosOrb

    assert not takes_inputs(ChaosOrb())


# --- the donors come from the target alone -------------------------------------------------------


def test_the_solver_gets_the_donor_of_the_toy_from_the_target_alone():
    abstraction, start, priced = toy_problem(names=("toy-graft", "toy-forge"))
    result = solve_with_donors(abstraction, start, priced)  # no seed, no donor list: the offers name the donor through `inputs`
    assert [p.label for p in priced] == ["Toy Graft", "Toy Forge"]
    # two grafts of 2 each, and a donor of three forges of 1 each for each graft: 2 x (2 + 3)
    assert result.value == pytest.approx(10.0, rel=1e-9)
    assert result.solution.policy[result.start].label == "Toy Graft"
    donor = abstraction.compress(donor_want())
    assert ("in", donor, abstraction.compress(ToyGraft().inputs(CONTRACT_DATA)[0].start)) in result.values  # the donor's process was solved
    assert result.solution.error_bound < 1e-9


def test_the_donor_model_asks_the_catalog_not_a_list():
    abstraction, start, priced = toy_problem()
    model = DonorModel(abstraction, start, priced)
    labels = {action.label: action for action in model.actions(start)}
    assert set(labels) == {"Toy Graft", "Toy Dear Graft"}  # the forges do not apply to the start item; the grafts name their donors
    graft = labels["Toy Graft"]
    assert graft.extra_inputs[0].want == abstraction.compress(donor_want())
    assert model.needs(start, graft) == ToyGraft().inputs(CONTRACT_DATA)
    assert labels["Toy Dear Graft"].outcomes == graft.outcomes  # equal kernels are both kept: the donors differ in price
    assert labels["Toy Dear Graft"].extra_inputs != graft.extra_inputs


def test_the_toy_equals_brute_force_over_all_donors_offered_up_front():
    abstraction, start, priced = toy_problem()
    lazy = solve_with_donors(abstraction, start, priced, seed=isolated_feeder(GOAL_PAIR))
    unpruned = solve_with_donors(abstraction, start, priced, seed=everything)
    spec = product_spec(unpruned.acquisition, unpruned.start)
    best = brute_force_inputs(spec)  # every stationary policy of the product with both donors offered
    assert unpruned.offered_pairs == unpruned.pairs == 6 and len(spec[1]) == len(unpruned.values) - sum(
        1 for state in unpruned.values if unpruned.acquisition.is_goal(state)
    )
    assert float(best[unpruned.start]) == pytest.approx(10.0, rel=1e-9)
    assert lazy.value == pytest.approx(float(best[lazy.start]), rel=1e-9)
    assert unpruned.value == pytest.approx(float(best[lazy.start]), rel=1e-9)
    for state, value in lazy.values.items():
        if state in best and best[state] is not None and math.isfinite(value):
            assert value == pytest.approx(float(best[state]), rel=1e-9), state


def test_a_donor_the_lower_bound_cannot_rule_out_is_offered_and_the_solve_then_leaves_it_unused():
    abstraction, start, priced = toy_problem(dear_forge=1.0)  # the determinized distance sees one forge of 1, not the hundred tries
    lazy = solve_with_donors(abstraction, start, priced, seed=isolated_feeder(GOAL_PAIR))
    unpruned = solve_with_donors(abstraction, start, priced, seed=everything)
    assert [(r.offered, r.added) for r in lazy.rounds] == [(3, 3), (6, 0)]  # the dear graft joined at the three states, in round 2
    assert lazy.value == pytest.approx(unpruned.value, rel=1e-12) == pytest.approx(10.0, rel=1e-9)
    assert all(action.label != "Toy Dear Graft" for action in lazy.solution.policy.values())


def test_a_donor_whose_cheapest_possible_cost_is_above_the_plan_is_proved_unneeded_and_the_value_is_unchanged():
    abstraction, start, priced = toy_problem(dear_forge=500.0)
    pruned = solve_with_donors(abstraction, start, priced, seed=isolated_feeder(GOAL_PAIR))
    unpruned = solve_with_donors(abstraction, start, priced, seed=everything)
    assert len(pruned.rounds) == 1 and pruned.offered_pairs == 3 and pruned.pairs == 6  # three states x the seeded graft
    assert pruned.value == unpruned.value == pytest.approx(10.0, rel=1e-9)
    for state, value in pruned.values.items():  # every value of the pruned run is the value of the unpruned one
        assert value == pytest.approx(unpruned.values[state], rel=1e-9, abs=1e-12)
    assert len(pruned.values) < len(unpruned.values)  # the dear donor's process was never built


def test_the_seed_changes_the_rounds_and_not_the_answer():
    abstraction, start, priced = toy_problem(dear_forge=500.0)
    bare = solve_with_donors(abstraction, start, priced)
    fed = solve_with_donors(abstraction, start, priced, seed=isolated_feeder(GOAL_PAIR))
    assert bare.value == pytest.approx(fed.value, rel=1e-12)
    assert len(fed.rounds) == 1 and len(bare.rounds) > 1  # with a seed of nothing the first solve has no graft, so no value, and everything is offered


def test_a_cheaper_donor_is_chosen_when_it_is_cheaper():
    # a dear forge that costs nothing extra makes the dear graft's donor cost 100 tries of 0.01 = 1, against 3 for the plain one
    abstraction, start, priced = toy_problem(dear_forge=0.01, forge=2.0)
    lazy = solve_with_donors(abstraction, start, priced, seed=isolated_feeder(GOAL_PAIR))
    unpruned = solve_with_donors(abstraction, start, priced, seed=everything)
    assert lazy.value == pytest.approx(unpruned.value, rel=1e-9)
    assert lazy.value == pytest.approx(2 * (2.0 + 1.0), rel=1e-9)  # the dear graft: a 100-try forge at 0.01
    assert lazy.solution.policy[lazy.start].label == "Toy Dear Graft"
    spec = product_spec(unpruned.acquisition, unpruned.start)
    assert float(brute_force_inputs(spec)[unpruned.start]) == pytest.approx(lazy.value, rel=1e-9)
