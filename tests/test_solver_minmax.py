"""The min-max solve and `solve_bounds` with variants (ADR-0023 "When the members differ: variants", #172).

The oracle of the prototype (#130, part A) as a test: random min-max models against brute force over
EVERY stationary policy and EVERY choice of the variant, for the optimistic model (nature helps) and
the pessimistic one (nature hurts), both bounds around the brute-force value, and the identity of
ADR-0010 for the min-max operator. Then the cases the ADR names: the two-member block, a nature that
traps the controller, a variant that only one choice of nature reaches, a certificate that refuses.
"""

import math

import pytest
from ssp_bounds import block_ssp
from ssp_helpers import GOAL, CountingModel, act, model
from ssp_minmax import (
    backup,
    brute_optimistic,
    brute_pessimistic,
    random_game,
    smallest_cost,
    to_game_model,
)
from ssp_oracles import to_model

from crafting_system.solver import (
    Action,
    Bounds,
    ConvergenceError,
    VariantAction,
    solve,
    solve_bounds,
    solve_variants,
)
from crafting_system.solver import _minmax
from crafting_system.solver._bounds import _gap, _lower_bound, _upper_bound

SLACK = 1e-12  # the float noise of the oracle's own linear solves
AGREEMENT = 1e-9


def variant(label, cost, *variants):
    """`variant("a", 1, [("goal", 1)], [("B", 9), ("goal", 1)])`: a variant action from outcome lists."""
    return VariantAction(label, cost, tuple(tuple(outcomes) for outcomes in variants))


# --- the action itself ------------------------------------------------------------------------


def test_a_variant_action_keeps_its_variants_as_normalised_tuples():
    action = variant("a", 2, [("x", 1), ("goal", 3)], [("goal", 1)])

    assert action.cost == 2.0
    assert action.variants == ((("x", 1), ("goal", 3)), (("goal", 1),))
    assert action.variants[0][0].state == "x"
    assert action.extra_inputs == ()


@pytest.mark.parametrize(
    ("cost", "variants"),
    [
        (1, ()),
        (1, ([("goal", 0)],)),
        (1, ([("goal", 1)], [])),
        (1, ([("goal", -1), ("x", 2)],)),
        (1, ([("goal", True)],)),
        (1, ([("goal", 1.5)],)),
        (0, ([("goal", 1)],)),
        (-1, ([("goal", 1)],)),
        (math.inf, ([("goal", 1)],)),
        (math.nan, ([("goal", 1)],)),
        (True, ([("goal", 1)],)),
        ("1", ([("goal", 1)],)),
    ],
)
def test_a_variant_action_rejects_what_an_action_rejects(cost, variants):
    with pytest.raises(ValueError):
        VariantAction("a", cost, tuple(tuple(outcomes) for outcomes in variants))


def test_plain_solve_refuses_a_variant_action_and_says_what_to_use():
    table = model({"A": [variant("a", 1, [(GOAL, 1)])]})

    with pytest.raises(TypeError, match="solve_variants"):
        solve(table, ["A"])


def test_a_variant_action_with_extra_inputs_is_refused_like_an_action():
    action = VariantAction("a", 1, (((GOAL, 1),), ((GOAL, 2),)), extra_inputs=("other",))

    with pytest.raises(NotImplementedError):
        solve_variants(model({"A": [action]}), ["A"])


@pytest.mark.parametrize(
    "options",
    [{"tolerance": 0}, {"tolerance": math.nan}, {"max_sweeps": 0}, {"direct_solve_limit": -1}],
)
def test_solve_variants_checks_the_options_of_solve(options):
    with pytest.raises(ValueError):
        solve_variants(model({"A": [act("a", 1, (GOAL, 1))]}), ["A"], **options)


# --- the oracle: random min-max models against brute force ------------------------------------


@pytest.mark.parametrize("seed", range(70))
def test_both_bounds_bracket_the_brute_force_value_of_a_random_min_max_model(seed):
    game = random_game(seed)
    table = to_game_model(game, plain_if_single=seed % 2 == 0)  # the mix of both kinds, and variants only
    starts = range(game.size)

    bounds = solve_bounds(table, table, starts)
    pessimistic = brute_pessimistic(game)
    optimistic = brute_optimistic(game)

    for state in starts:
        # the bounds hold, with the oracle's own noise
        assert bounds.lower[state] <= optimistic[state] * (1 + SLACK)
        assert bounds.upper[state] >= pessimistic[state] * (1 - SLACK)
        # and they are tight where the models are solved to tolerance
        assert bounds.lower[state] >= optimistic[state] * (1 - AGREEMENT)
        assert bounds.upper[state] <= pessimistic[state] * (1 + AGREEMENT)
        assert optimistic[state] <= pessimistic[state] * (1 + SLACK)
    assert bounds.pessimistic_error <= AGREEMENT
    assert bounds.optimistic_error <= AGREEMENT


@pytest.mark.parametrize("seed", range(70, 100))
def test_the_min_max_solve_agrees_with_brute_force_and_its_policy_is_the_best_policy(seed):
    game = random_game(seed, max_states=5, max_actions=2, max_variants=2)
    table = to_game_model(game, plain_if_single=False)
    starts = range(game.size)

    solution = solve_variants(table, starts)
    pessimistic = brute_pessimistic(game)

    assert 0.0 <= solution.error_bound <= AGREEMENT
    for state in starts:
        assert solution.values[state] == pytest.approx(pessimistic[state], rel=AGREEMENT)
        # the certified upper bound is on the cost of the policy, which is the best one
        certified = solution.values[state] * (1 + solution.error_bound)
        assert certified >= pessimistic[state] * (1 - SLACK)
        assert certified / pessimistic[state] - 1 <= AGREEMENT
    assert solution.values[game.goal] == 0.0


def test_a_larger_random_game_agrees_with_value_iteration():
    # no brute force at this size: the pessimistic backup iterated to its fixed point is the oracle
    for seed in (3, 11):
        game = random_game(seed, max_states=10, max_actions=3, max_variants=3)
        starts = range(game.size)
        value = [0.0] * (game.size + 1)
        for _ in range(4000):
            nxt = backup(game, value)
            done = max(abs(nxt[i] - value[i]) for i in range(game.size + 1)) < 1e-13
            value = nxt
            if done:
                break

        solution = solve_variants(to_game_model(game, plain_if_single=False), starts)

        for state in starts:
            assert solution.values[state] == pytest.approx(value[state], rel=1e-9)


@pytest.mark.parametrize("seed", range(40))
def test_the_identity_of_the_certificate_holds_for_the_min_max_operator(seed):
    import random

    import numpy as np

    game = random_game(seed)
    g = smallest_cost(game)
    rng = random.Random(seed)
    for _ in range(5):
        value = np.array([rng.uniform(0.1, 8.0) for _ in range(game.size)] + [0.0])
        base = backup(game, value)
        grow = 1 + 3 * rng.random()  # a >= 1
        shrink = rng.random()  # a <= 1
        up = backup(game, grow * value)
        down = backup(game, shrink * value)
        states = range(game.size)

        assert all(up[s] <= grow * base[s] - (grow - 1) * g + SLACK for s in states)
        assert all(down[s] >= shrink * base[s] + (1 - shrink) * g - SLACK for s in states)


# --- plain models are as they were ------------------------------------------------------------


def reference_bounds(optimistic, pessimistic, starts):
    """What `solve_bounds` did before variants: `solve` twice (once when the model is one)."""
    below = solve(optimistic, starts)
    above = below if optimistic is pessimistic else solve(pessimistic, starts)
    lower = {s: _lower_bound(v, below.error_bound) for s, v in below.values.items()}
    upper = {s: _upper_bound(v, above.error_bound) for s, v in above.values.items()}
    gap = max((_gap(lower[s], upper[s]) for s in starts), default=0.0)
    return Bounds(lower, upper, above.policy, gap, below.error_bound, above.error_bound)


@pytest.mark.parametrize("seed", range(40))
def test_a_model_without_variants_gives_bit_for_bit_the_result_of_solve(seed):
    spec = block_ssp(seed)
    starts = list(range(spec.nblocks))
    optimistic, pessimistic = to_model(spec.optimistic), to_model(spec.pessimistic)

    assert solve_bounds(optimistic, pessimistic, starts) == reference_bounds(optimistic, pessimistic, starts)
    assert solve_bounds(optimistic, optimistic, starts) == reference_bounds(optimistic, optimistic, starts)
    assert solve_variants(pessimistic, starts) == solve(pessimistic, starts)


def test_a_one_variant_action_is_the_plain_action():
    one = model({"A": [variant("a", 2, [("B", 1), (GOAL, 1)])], "B": [variant("b", 3, [(GOAL, 1)])]})
    plain = model({"A": [act("a", 2, ("B", 1), (GOAL, 1))], "B": [act("b", 3, (GOAL, 1))]})

    ours = solve_variants(one, ["A"])
    theirs = solve(plain, ["A"])

    assert ours.values == theirs.values
    assert ours.error_bound <= 1e-14


# --- the game itself --------------------------------------------------------------------------


def block_example():
    """ADR-0023: a block of two members; one reaches the goal at cost 1, the other loops with 0.9."""
    return model({"B": [variant("go", 1, [(GOAL, 1)], [("B", 9), (GOAL, 1)])]})


def test_the_two_member_block_is_ten_for_nature_and_one_for_the_optimist():
    table = block_example()

    bounds = solve_bounds(table, table, ["B"])
    solution = solve_variants(table, ["B"])

    assert solution.values["B"] == pytest.approx(10.0, rel=1e-12)
    assert bounds.upper["B"] == pytest.approx(10.0, rel=1e-9)
    assert bounds.upper["B"] >= 10.0
    assert bounds.lower["B"] == pytest.approx(1.0, rel=1e-9)
    assert bounds.lower["B"] <= 1.0
    assert bounds.gap == pytest.approx(9.0, rel=1e-9)
    assert isinstance(bounds.policy["B"], VariantAction)
    assert bounds.policy["B"].label == "go"


def test_two_different_models_give_the_same_bounds_as_one():
    one = block_example()
    optimistic = block_example()

    assert solve_bounds(one, one, ["B"]) == solve_bounds(optimistic, one, ["B"])


def test_a_variant_that_makes_the_goal_unreachable_gives_infinity():
    table = model({"B": [variant("go", 1, [(GOAL, 1)], [("B", 1)])]})

    bounds = solve_bounds(table, table, ["B"])
    solution = solve_variants(table, ["B"])

    assert solution.values["B"] == math.inf
    assert solution.policy == {}
    assert bounds.upper["B"] == math.inf
    assert bounds.lower["B"] == pytest.approx(1.0, rel=1e-9)
    assert bounds.gap == math.inf


def test_a_trap_through_two_states_is_found_by_the_rounds_of_nature():
    # nature starts with the variant that reaches the goal; only after the first solve does the
    # other variant (back to A, which has no way out) look worse for the controller, then infinite
    table = model(
        {
            "A": [act("step", 1, ("B", 1))],
            "B": [variant("go", 1, [(GOAL, 1)], [("A", 1)])],
        }
    )

    bounds = solve_bounds(table, table, ["A", "B"])

    assert bounds.upper["A"] == math.inf
    assert bounds.upper["B"] == math.inf
    assert bounds.lower["A"] == pytest.approx(2.0, rel=1e-9)
    assert bounds.lower["B"] == pytest.approx(1.0, rel=1e-9)


def test_the_controller_avoids_the_action_nature_can_trap():
    table = model(
        {
            "B": [
                variant("risky", 1, [(GOAL, 1)], [("B", 1)]),
                act("safe", 5, (GOAL, 1)),
            ]
        }
    )

    bounds = solve_bounds(table, table, ["B"])

    assert bounds.upper["B"] == pytest.approx(5.0, rel=1e-9)
    assert bounds.lower["B"] == pytest.approx(1.0, rel=1e-9)
    assert bounds.policy["B"].label == "safe"
    assert isinstance(bounds.policy["B"], Action)


def test_states_that_only_one_variant_reaches_are_solved_and_certified():
    table = model(
        {
            "A": [variant("a", 1, [(GOAL, 1)], [("X", 1), (GOAL, 1)])],
            "X": [act("b", 5, (GOAL, 1))],
        }
    )

    solution = solve_variants(table, ["A"])

    assert solution.values["A"] == pytest.approx(3.5, rel=1e-12)
    assert solution.values["X"] == pytest.approx(5.0, rel=1e-12)


def test_only_the_certified_states_are_returned():
    table = model(
        {
            "A": [
                variant("direct", 1, [(GOAL, 1)], [(GOAL, 3)]),
                act("detour", 4, ("T", 1)),
                act("dead", 1, ("D", 1)),
            ],
            "T": [act("t", 1, (GOAL, 1))],
        }
    )

    solution = solve_variants(table, ["A"])

    assert solution.values == {"A": pytest.approx(1.0), GOAL: 0.0, "D": math.inf}
    assert "T" not in solution.values  # finite, but the policy never reaches it
    assert set(solution.policy) == {"A"}
    assert solution.policy["A"] is table.actions("A")[0]  # the caller's own object


def test_a_start_that_is_a_goal_is_certified_as_zero():
    table = model({"A": [variant("a", 1, [(GOAL, 1)], [(GOAL, 2)])]})

    solution = solve_variants(table, [GOAL, "A", "A"])

    assert solution.values[GOAL] == 0.0
    assert solution.values["A"] == pytest.approx(1.0)
    assert solve_variants(table, []).values == {}


def test_a_cycle_through_the_variants_converges_with_the_rounds_of_nature():
    # the worst variant is the one that leads back, in a state reached from another cycle
    table = model(
        {
            "A": [variant("a", 1, [("B", 1), (GOAL, 3)], [("A", 1), ("B", 2), (GOAL, 1)])],
            "B": [variant("b", 2, [(GOAL, 1), ("A", 1)], [("A", 3), (GOAL, 1)]), act("c", 7, (GOAL, 1))],
        }
    )

    solution = solve_variants(table, ["A", "B"])
    again = solve_variants(table, ["A", "B"], direct_solve_limit=0)

    # B: min(2 + worst(...), 7); check the fixed point by hand: V_B = 2 + V_A * 3/4 (variant 2) vs 7
    v_a, v_b = solution.values["A"], solution.values["B"]
    q_a = max(1 + v_b / 4, 1 + (v_a + 2 * v_b) / 4)
    q_b = min(max(2 + v_a / 2, 2 + 3 * v_a / 4), 7)
    assert v_a == pytest.approx(q_a, rel=1e-9)
    assert v_b == pytest.approx(q_b, rel=1e-9)
    assert again.values["A"] == pytest.approx(v_a, rel=1e-8)


def test_the_models_actions_are_asked_once_per_state():
    table = CountingModel(
        model(
            {
                "A": [variant("a", 1, [("B", 1)], [(GOAL, 1)])],
                "B": [variant("b", 1, [(GOAL, 1)], [("A", 1), (GOAL, 1)])],
            }
        )
    )

    solve_bounds(table, table, ["A"])
    shared = list(table.action_calls)

    assert sorted(shared) == ["A", "B"]

    optimistic = CountingModel(table.inner)
    pessimistic = CountingModel(table.inner)
    solve_bounds(optimistic, pessimistic, ["A"])

    assert sorted(optimistic.action_calls) == ["A", "B"]
    assert sorted(pessimistic.action_calls) == ["A", "B"]

    alone = CountingModel(table.inner)
    solve_variants(alone, ["A"])

    assert sorted(alone.action_calls) == ["A", "B"]


def test_the_plain_pessimistic_model_is_asked_once_per_state_too():
    spec = block_ssp(5)
    plain = CountingModel(to_model(spec.pessimistic))

    solve_bounds(to_model(spec.optimistic), plain, list(range(spec.nblocks)))

    assert len(plain.action_calls) == len(set(plain.action_calls))


# --- the certificate refuses, and stays sound -------------------------------------------------


def test_the_loop_is_capped_without_losing_the_bound(monkeypatch):
    # no round of nature at all: the values are those of the first variants (1 for the block), and the
    # residual against the other variant (1.9) is below the cost 1, so the bound is still a true bound
    monkeypatch.setattr(_minmax, "MAX_ROUNDS", 0)
    table = block_example()

    bounds = solve_bounds(table, table, ["B"])

    assert bounds.upper["B"] >= 10.0 * (1 - 1e-12)
    assert bounds.upper["B"] < math.inf
    assert bounds.pessimistic_error == pytest.approx(9.0, rel=1e-6)


def test_a_residual_as_large_as_the_smallest_cost_gives_no_certificate(monkeypatch):
    monkeypatch.setattr(_minmax, "MAX_ROUNDS", 0)
    table = model(
        {
            "A": [variant("a", 1, [(GOAL, 1)], [("X", 1)])],
            "X": [act("b", 5, (GOAL, 1))],
        }
    )

    solution = solve_variants(table, ["A"])
    bounds = solve_bounds(table, table, ["A"])

    assert solution.error_bound == math.inf
    assert solution.values["A"] == 1.0  # the values are still returned
    assert bounds.upper["A"] == math.inf  # and the bound says nothing
    assert bounds.lower["A"] == pytest.approx(1.0, rel=1e-9)
    assert bounds.gap == math.inf


def test_with_the_rounds_the_same_model_is_certified():
    table = model(
        {
            "A": [variant("a", 1, [(GOAL, 1)], [("X", 1)])],
            "X": [act("b", 5, (GOAL, 1))],
        }
    )

    solution = solve_variants(table, ["A"])

    assert solution.values["A"] == pytest.approx(6.0, rel=1e-12)
    assert solution.error_bound <= 1e-12


def test_a_component_that_does_not_converge_raises_like_solve():
    table = model(
        {
            "A": [variant("a", 1, [("B", 1), (GOAL, 1)], [("B", 99), (GOAL, 1)])],
            "B": [act("b", 1, ("A", 99), (GOAL, 1))],
        }
    )

    with pytest.raises(ConvergenceError):
        solve_variants(table, ["A"], direct_solve_limit=0, max_sweeps=2, tolerance=1e-14)


def test_solve_bounds_reports_the_error_bound_of_the_min_max_solve():
    game = random_game(5)
    table = to_game_model(game, plain_if_single=False)

    solution = solve_variants(table, range(game.size))
    bounds = solve_bounds(table, table, range(game.size))

    assert bounds.pessimistic_error == solution.error_bound
    assert bounds.policy == solution.policy
