"""The Peek kind of the solver (ADR-0054, ticket #293): the hand test, closed forms, the expansion and the edges.

The random models against the explicit product expansion, brute force and HiGHS are in `test_solver_peek_oracles.py`.
"""

import itertools
import math
import random
from fractions import Fraction

import pytest
from ssp_oracles import random_ssp, to_model

from crafting_system.solver import (
    MAIN,
    Acquisition,
    Action,
    ConvergenceError,
    ExpandedModel,
    Need,
    Outcome,
    Peek,
    PeekNode,
    TabularModel,
    peek_backup,
    solve,
    solve_peek,
)

GOAL, MIDDLE, BRICK = "goal", "middle", "brick"

# ADR-0054: states goal 0, middle 30, brick 400; A costs 1 and gives 20/50/30%, B costs 2 and gives 10/80/10%;
# without the Lock the best is B at 66; the fallback is some action that is not previewable and is worth 66.
A_KERNEL = ((GOAL, 20), (MIDDLE, 50), (BRICK, 30))
B_KERNEL = ((GOAL, 10), (MIDDLE, 80), (BRICK, 10))
VALUE = {GOAL: 0, MIDDLE: 30, BRICK: 400}


def hand_model(price, *, with_lock=True):
    a, b = Action("A", 1, A_KERNEL), Action("B", 2, B_KERNEL)
    bench = Action("bench", 66, ((GOAL, 1),))
    table = {
        MIDDLE: [Action("finish middle", 30, ((GOAL, 1),))],
        BRICK: [Action("finish brick", 400, ((GOAL, 1),))],
        "s": [a, b, bench, *([Peek("lock", price, (a, b), (bench,))] if with_lock else [])],
    }
    return TabularModel([GOAL], table)


def enumerate_min(options, limit):
    """`E[min(X_1, .., X_m, limit)]` in exact fractions by listing every combination of results."""
    total = Fraction(0)
    for combo in itertools.product(*options):
        chance = math.prod(Fraction(weight, sum(w for _, w in option)) for (_, weight), option in zip(combo, options))
        total += chance * min(min(value for value, _ in combo), limit)
    return total


def hand_options():
    return [
        [(cost + VALUE[state], weight) for state, weight in kernel]
        for cost, kernel in ((1, A_KERNEL), (2, B_KERNEL))
    ]


def test_the_hand_test_before_the_price_is_23_97_without_the_lock_66_and_break_even_42_03():
    before_the_price = enumerate_min(hand_options(), 66)

    assert before_the_price == Fraction(2397, 100)
    assert 66 - before_the_price == Fraction(4203, 100)
    assert peek_backup(hand_options(), 66) == pytest.approx(23.97, abs=1e-12)
    assert solve(hand_model(1, with_lock=False), ["s"]).values["s"] == pytest.approx(66.0, abs=1e-9)


def test_the_solver_pays_the_lock_below_the_break_even_and_not_above_it():
    cheap = solve_peek(hand_model(40), ["s"])
    dear = solve_peek(hand_model(45), ["s"])
    just_below = solve_peek(hand_model(42.02), ["s"])
    just_above = solve_peek(hand_model(42.04), ["s"])

    assert cheap.values["s"] == pytest.approx(40 + 23.97, abs=1e-9)
    assert cheap.policy["s"].label == "lock"
    assert dear.values["s"] == pytest.approx(66.0, abs=1e-9)
    assert dear.policy["s"].label == "B"
    assert just_below.policy["s"].label == "lock"
    assert just_below.values["s"] == pytest.approx(42.02 + 23.97, abs=1e-9)
    assert just_above.policy["s"].label == "B"
    assert just_above.values["s"] == pytest.approx(66.0, abs=1e-9)
    assert cheap.error_bound < 1e-9


def test_the_hand_test_value_is_the_exact_fraction_of_the_enumeration_at_every_price():
    for price in (Fraction(1, 2), Fraction(7), Fraction(21), Fraction(42)):
        expected = min(Fraction(66), price + Fraction(2397, 100))

        found = solve_peek(hand_model(float(price)), ["s"]).values["s"]

        assert found == pytest.approx(float(expected), rel=1e-12)


def one_option_model(price, kernel, cost, fallback_cost):
    option = Action("o", cost, tuple(kernel))
    table = {
        "s": [Peek("lock", price, (option,), (Action("f", fallback_cost, ((GOAL, 1),)),))],
        MIDDLE: [Action("finish middle", 30, ((GOAL, 1),))],
        BRICK: [Action("finish brick", 400, ((GOAL, 1),))],
    }
    return TabularModel([GOAL], table)


@pytest.mark.parametrize("seed", range(40))
def test_a_peek_of_one_option_is_its_closed_form(seed):
    rng = random.Random(seed)
    kernel = [(state, rng.randint(1, 9)) for state in (GOAL, MIDDLE, BRICK)]
    cost = rng.choice([0.5, 1.0, 3.0, 12.0])
    fallback = rng.choice([5.0, 40.0, 150.0, 900.0])
    price = rng.choice([0.25, 2.0, 10.0])
    total = sum(w for _, w in kernel)
    # the player takes the result when it is cheaper than giving up, so: price + E[min(cost + V(o), fallback)]
    closed = Fraction(price) + sum(
        Fraction(w, total) * min(Fraction(cost) + VALUE[state], Fraction(fallback)) for state, w in kernel
    )

    solution = solve_peek(one_option_model(price, kernel, cost, fallback), ["s"])

    assert solution.values["s"] == pytest.approx(float(closed), rel=1e-11)
    assert peek_backup([[(cost + VALUE[s], w) for s, w in kernel]], fallback) == pytest.approx(
        float(closed - Fraction(price)), rel=1e-12
    )


@pytest.mark.parametrize("seed", range(150))
def test_the_sorted_tail_sweep_equals_listing_every_combination(seed):
    rng = random.Random(seed)
    options = [
        [(rng.choice([1, 2, 3, 5, 8, 13, 100, 0.5]), rng.randint(1, 20)) for _ in range(rng.randint(1, 4))]
        for _ in range(rng.randint(1, 4))
    ]
    limit = rng.choice([math.inf, 1.0, 4.0, 10.0, 50.0, 1000.0])
    exact_limit = Fraction(10**18) if limit == math.inf else Fraction(limit)  # every value is below it
    expected = enumerate_min([[(Fraction(v), w) for v, w in option] for option in options], exact_limit)

    assert peek_backup(options, limit) == pytest.approx(float(expected), rel=1e-12)


def test_the_sweep_handles_infinite_values_and_an_infinite_limit():
    assert peek_backup([[(math.inf, 1)]], 7.0) == 7.0
    assert peek_backup([[(3.0, 1), (math.inf, 1)]], 7.0) == pytest.approx(5.0)
    assert peek_backup([[(3.0, 1), (math.inf, 1)]], math.inf) == math.inf
    assert peek_backup([[(3.0, 1), (5.0, 1)]], math.inf) == pytest.approx(4.0)
    assert peek_backup([[(3.0, 2), (5.0, 2)], [(4.0, 1)]], math.inf) == pytest.approx(3.5)


def test_two_options_with_equal_kernels_are_two_draws_and_cost_less_than_one():
    one = Action("a", 1, A_KERNEL)
    twin = Action("twin", 1, A_KERNEL)
    bench = Action("bench", 66, ((GOAL, 1),))

    def build(options):
        return TabularModel(
            [GOAL],
            {
                "s": [Peek("lock", 1, options, (bench,))],
                MIDDLE: [Action("m", 30, ((GOAL, 1),))],
                BRICK: [Action("b", 400, ((GOAL, 1),))],
            },
        )

    single = solve_peek(build((one,)), ["s"]).values["s"]
    double = solve_peek(build((one, twin)), ["s"]).values["s"]

    assert double < single - 1.0
    expected = enumerate_min(
        [[(1 + VALUE[s], w) for s, w in A_KERNEL]] * 2, Fraction(66)
    )
    assert double == pytest.approx(1 + float(expected), rel=1e-11)


def lock_outcomes(solution, state="s"):
    lock = solution.policy[state]
    return {node: weight for node, weight in lock.outcomes}


def test_the_policy_expands_into_ordinary_actions_with_m_plus_1_pseudo_states():
    solution = solve_peek(hand_model(10), ["s"])

    lock = solution.policy["s"]
    nodes = [node for node, _ in lock.outcomes]
    kinds = sorted((node.kind, node.option) for node in nodes)
    pseudo = [state for state in solution.policy if isinstance(state, PeekNode)]

    assert lock.label == "lock" and lock.cost == 10.0
    assert all(isinstance(node, PeekNode) and node.state == "s" for node in nodes)
    assert kinds == [("apply", 0), ("apply", 1), ("give up", -1)]
    assert len(pseudo) == 2 + 1  # m + 1 besides the Lock's own node
    assert solution.reactions["s"] == tuple(solution.reactions["s"])
    for node in pseudo:
        for action in solution.policy[node].outcomes:
            assert action.weight > 0
    assert all(solution.policy[PeekNode("s", "apply", a)].cost == (1.0, 2.0)[a] for a in (0, 1))
    assert solution.policy[PeekNode("s", "give up")].label == "bench"


def test_the_chance_that_an_option_wins_is_the_exact_chance_over_the_ranked_pairs():
    solution = solve_peek(hand_model(10), ["s"])
    ranked = solution.reactions["s"]  # (option index, result state), best first
    options = [A_KERNEL, B_KERNEL]
    weight_of = [dict(kernel) for kernel in options]
    totals = [100, 100]

    # the chance of each pair being the best accepted one, by listing every combination of throws
    win = {}
    for combo in itertools.product(*(kernel for kernel in options)):
        throws = {(a, state) for a, (state, _) in enumerate(combo)}
        chance = Fraction(math.prod(w for _, w in combo), math.prod(totals))
        best = next((pair for pair in ranked if pair in throws), None)
        win[best] = win.get(best, 0) + chance

    lock = lock_outcomes(solution)
    denominator = sum(lock.values())
    for node, weight in lock.items():
        if node.kind == "apply":
            assert Fraction(weight, denominator) == sum(
                w for pair, w in win.items() if pair is not None and pair[0] == node.option
            )
        else:
            assert Fraction(weight, denominator) == win.get(None, 0)
        if node.kind == "apply":
            step = solution.policy[node]
            here = sum(w for _, w in step.outcomes)
            for result, w in step.outcomes:
                assert Fraction(w, here) * sum(
                    q for pair, q in win.items() if pair is not None and pair[0] == node.option
                ) == win[(node.option, result)]
    assert weight_of  # both kernels are read as given


def test_the_ranking_is_strict_and_ties_go_to_the_state_id_then_the_option_order():
    same = Action("a", 1, ((GOAL, 1), (MIDDLE, 1)))
    twin = Action("b", 1, ((GOAL, 1), (MIDDLE, 1)))
    bench = Action("bench", 500, ((GOAL, 1),))
    model = TabularModel(
        [GOAL],
        {
            "s": [Peek("lock", 1, (same, twin), (bench,))],
            MIDDLE: [Action("m", 30, ((GOAL, 1),))],
        },
    )

    first = solve_peek(model, ["s"])
    second = solve_peek(model, ["s"])

    assert first.reactions == second.reactions and first.values == second.values
    ranked = first.reactions["s"]
    assert len(set(ranked)) == len(ranked) == 4
    assert [pair[1] for pair in ranked[:2]] == [GOAL, GOAL]  # the better result first
    assert [pair[0] for pair in ranked[:2]] == [0, 1]  # then the option order
    # the first pair is certain to win when it comes up; the twin's goal only wins when the first option throws middle
    lock = dict(first.policy["s"].outcomes)
    assert lock[PeekNode("s", "apply", 0)] > lock[PeekNode("s", "apply", 1)]


def trap_model(*, plain_way_out):
    bad = Action("to-dead", 1, (("dead", 1),))
    burn = Action("burn", 1, (("s", 1),))
    plain = [Action("slow", 50, ((GOAL, 1), ("s", 3)))] if plain_way_out else []
    return TabularModel([GOAL], {"s": [*plain, Peek("lock", 1, (bad,), (burn,))]})


def test_a_reaction_that_never_accepts_is_improper_and_reported_not_looped():
    model = trap_model(plain_way_out=False)

    never = solve(ExpandedModel(model, {"s": ()}), ["s"])
    solved = solve_peek(model, ["s"])

    assert never.values["s"] == math.inf and "s" not in never.policy
    assert solved.values["s"] == math.inf
    assert solved.rounds >= 1


def test_where_a_plain_way_out_exists_the_trap_is_never_played():
    model = trap_model(plain_way_out=True)

    solved = solve_peek(model, ["s"])

    assert solved.policy["s"].label == "slow"
    alone = TabularModel([GOAL], {"s": [Action("slow", 50, ((GOAL, 1), ("s", 3)))]})
    assert solved.values["s"] == solve(alone, ["s"]).values["s"]


def test_a_fixed_reaction_can_be_solved_on_its_own_and_is_never_better_than_the_best_one():
    best = solve_peek(hand_model(10), ["s"])
    model = hand_model(10)

    for reaction in (best.reactions["s"], (), ((0, GOAL),), ((1, MIDDLE), (0, GOAL))):
        fixed = solve(ExpandedModel(model, {"s": reaction}), ["s", MIDDLE, BRICK])
        assert fixed.values["s"] >= best.values["s"] - 1e-9
    same = solve(ExpandedModel(model, {"s": best.reactions["s"]}), ["s", MIDDLE, BRICK])
    assert same.values["s"] == pytest.approx(best.values["s"], rel=1e-12)


def test_the_lock_free_start_is_never_worse_than_the_answer_and_the_answer_never_exceeds_the_lock_free_value():
    for seed in range(60):
        rng = random.Random(seed)
        table = random_peek_free_model(rng)
        plain = solve(TabularModel([GOAL], table), ["a", "b"])
        peeked = solve_peek(model_with_lock(table, rng), ["a", "b"])
        for state in ("a", "b"):
            assert peeked.values[state] <= plain.values[state] * (1 + 1e-9)


def random_peek_free_model(rng):
    table = {
        "a": [Action("a.0", rng.randint(1, 8), (("b", rng.randint(1, 5)), (GOAL, rng.randint(1, 5))))],
        "b": [Action("b.0", rng.randint(1, 8), ((GOAL, rng.randint(1, 5)), ("a", rng.randint(1, 5))))],
    }
    return table


def model_with_lock(table, rng):
    options = tuple(
        Action(f"o{i}", rng.randint(1, 4), (("a", rng.randint(1, 4)), ("b", rng.randint(1, 4)), (GOAL, rng.randint(1, 4))))
        for i in range(rng.randint(1, 3))
    )
    fallback = (Action("f", rng.randint(1, 30), ((GOAL, 1),)),) if rng.random() < 0.7 else ()
    full = {state: list(actions) for state, actions in table.items()}
    full["a"].append(Peek("lock", rng.randint(1, 5), options, fallback))
    return TabularModel([GOAL], full)


@pytest.mark.parametrize("seed", range(120))
def test_a_model_with_no_peek_is_bit_identical_to_plain_solve(seed):
    spec = random_ssp(seed)
    size, _ = spec
    plain = solve(to_model(spec), range(size))

    found = solve_peek(to_model(spec), range(size))

    assert found.values == plain.values
    assert found.policy == plain.policy
    assert found.error_bound == plain.error_bound
    assert found.rounds == 0 and found.reactions == {}


def test_solve_refuses_a_peek_and_says_which_function_takes_it():
    with pytest.raises(TypeError, match="solve_peek"):
        solve(hand_model(10), ["s"])


def test_a_state_that_offers_two_peeks_is_refused():
    option = Action("o", 1, ((GOAL, 1),))
    model = TabularModel([GOAL], {"s": [Peek("p", 1, (option,)), Peek("q", 1, (option,))]})

    with pytest.raises(ValueError, match="more than one peek"):
        solve_peek(model, ["s"])


def test_a_peek_is_checked_when_it_is_made():
    option = Action("o", 1, ((GOAL, 1),))
    with pytest.raises(ValueError, match="at least one option"):
        Peek("p", 1, ())
    with pytest.raises(ValueError, match="cost"):
        Peek("p", 0, (option,))
    with pytest.raises(ValueError, match="cost"):
        Peek("p", math.inf, (option,))
    with pytest.raises(ValueError, match="extra inputs"):
        Peek("p", 1, (Action("o", 1, ((GOAL, 1),), (("x",))),))
    with pytest.raises(TypeError):
        Peek("p", 1, ("not an action",))
    assert Peek("p", 1, [option], None).fallback == ()
    assert Peek("p", 1, [option], option).fallback == (option,)


def test_an_acceptance_set_is_checked_when_it_is_expanded():
    model = hand_model(10)

    with pytest.raises(ValueError, match="no acceptance set"):
        solve(ExpandedModel(model, {}), ["s"])
    with pytest.raises(ValueError, match="no outcome"):
        solve(ExpandedModel(model, {"s": ((0, "nowhere"),)}), ["s"])
    with pytest.raises(ValueError, match="twice"):
        solve(ExpandedModel(model, {"s": ((0, GOAL), (0, GOAL))}), ["s"])


class Pooled:
    """A model that offers the solver's `prefetch` hook, as the planner's pool-backed model does (#250)."""

    def __init__(self, base):
        self.base = base
        self.batches = []

    def is_goal(self, state):
        return self.base.is_goal(state)

    def actions(self, state):
        return self.base.actions(state)

    def prefetch(self, states):
        self.batches.append(tuple(states))


def test_the_pool_hook_is_forwarded_for_base_states_only_and_the_answer_is_the_same():
    plain = solve_peek(hand_model(10), ["s"])
    pooled = Pooled(hand_model(10))

    solution = solve_peek(pooled, ["s"])

    assert solution.values == plain.values and solution.policy == plain.policy
    assert pooled.batches and not any(isinstance(s, PeekNode) for batch in pooled.batches for s in batch)
    assert {s for batch in pooled.batches for s in batch} >= {"s", MIDDLE, BRICK}


def test_states_only_a_peek_can_reach_are_valued_too():
    # the plain actions of "s" never lead to MIDDLE or BRICK; only the options do
    sure = Action("sure", 100, ((GOAL, 1),))
    option = Action("o", 1, ((GOAL, 1), (MIDDLE, 1), (BRICK, 1)))
    model = TabularModel(
        [GOAL],
        {
            "s": [sure, Peek("lock", 1, (option,), (sure,))],
            MIDDLE: [Action("m", 30, ((GOAL, 1),))],
            BRICK: [Action("b", 400, ((GOAL, 1),))],
        },
    )

    solution = solve_peek(model, ["s"])

    assert solution.values[MIDDLE] == pytest.approx(30.0) and solution.values[BRICK] == pytest.approx(400.0)
    expected = 1 + (1 / 3) * (1 + 0) + (1 / 3) * (1 + 30) + (1 / 3) * min(1 + 400, 100)
    assert solution.values["s"] == pytest.approx(expected, rel=1e-12)


def test_a_state_with_no_lock_free_policy_is_rescued_by_the_lock():
    # "s" has no plain action; the option may fall into "dead", and the way to give up is a burn back to "s"
    option = Action("o", 2, ((GOAL, 1), ("dead", 3)))
    burn = Action("burn", 1, (("s", 1),))
    model = TabularModel([GOAL], {"s": [Peek("lock", 1, (option,), (burn,))]})

    solution = solve_peek(model, ["s", "dead"])

    # each attempt costs 1 (the Lock) and ends with probability 1/4 in the goal after paying 2; a miss pays 1 for the burn
    # V = 1 + (1/4) * (2 + 0) + (3/4) * (1 + V)  ->  V / 4 = 1 + 1/2 + 3/4  ->  V = 9
    assert solution.values["s"] == pytest.approx(9.0, rel=1e-12)
    assert solution.values["dead"] == math.inf
    assert solution.reactions["s"] == ((0, GOAL),)


def test_a_state_cycle_that_only_the_lock_can_leave_is_solved_from_a_proper_start():
    # seed 57 of the oracle file in short: "s" has no plain action, its option returns to "s", giving up leads to "t",
    # and "t" can only leave through "s" or by a coin flip
    option = Action("o", 9 / 4, (("s", 1),))
    give_up = Action("fb", 17 / 4, (("t", 1),))
    model = TabularModel(
        [GOAL],
        {
            "s": [Peek("lock", 2, (option,), (give_up,))],
            "t": [Action("t.0", 19 / 4, (("s", 10), (GOAL, 7), ("u", 7)))],
            "u": [Action("u.0", 5, ((GOAL, 8),))],
        },
    )

    solution = solve_peek(model, ["s", "t", "u"])

    t_value = (19 / 4 + (10 / 24) * (2 + 17 / 4) + (7 / 24) * 5) / (1 - (10 / 24) * 1)  # t -> s -> lock -> give up -> t
    assert solution.values["t"] == pytest.approx(t_value, rel=1e-9)
    assert solution.values["s"] == pytest.approx(2 + 17 / 4 + t_value, rel=1e-9)
    assert solution.reactions["s"] == ()


def test_max_rounds_must_be_a_positive_integer():
    for bad in (0, -1, 1.5, True):
        with pytest.raises(ValueError, match="max_rounds"):
            solve_peek(hand_model(10), ["s"], max_rounds=bad)


def test_a_reaction_that_only_pays_after_another_lock_exists_is_found_in_a_later_round():
    # "hard" is worth 1000 without the Lock and 2 with it; "s" first sees 1001 for that result and gives it up
    go = Action("go", 1, ((GOAL, 1),))
    model = TabularModel(
        [GOAL],
        {
            "s": [Peek("lock s", 1, (Action("o", 1, ((GOAL, 1), ("hard", 1))),), (Action("f", 30, ((GOAL, 1),)),))],
            "hard": [Action("slow", 1000, ((GOAL, 1),)), Peek("lock hard", 1, (go,))],
        },
    )

    solution = solve_peek(model, ["s"])

    assert solution.values["hard"] == pytest.approx(2.0)
    assert solution.values["s"] == pytest.approx(1 + 0.5 * 1 + 0.5 * 3)
    assert solution.rounds >= 2
    assert ("hard" in {r for _, r in solution.reactions["s"]})


def test_acquisition_passes_a_peek_through_options_and_fallback():
    base = hand_model(10)

    product = Acquisition(base)
    lifted = solve_peek(product, [product.start("s")])
    direct = solve_peek(base, ["s"])

    assert lifted.values[product.start("s")] == direct.values["s"]
    assert lifted.reactions[product.start("s")] == tuple((a, ("in", MAIN, r)) for a, r in direct.reactions["s"])


def test_a_fallback_may_need_an_input_and_an_option_may_not():
    donor_goal = "made"
    option = Action("o", 1, ((GOAL, 1), (BRICK, 4)))
    craft = Action("craft", 5, ((GOAL, 1),), (Need("raw", donor_goal),))
    model = TabularModel(
        [GOAL],
        {
            "s": [Peek("lock", 1, (option,), (craft,))],
            BRICK: [Action("b", 400, ((GOAL, 1),))],
            "raw": [Action("make", 7, ((donor_goal, 1),))],
            donor_goal: [],
        },
    )
    product = Acquisition(model, reaches=lambda state, want: state == want or state == GOAL)

    solution = solve_peek(product, [product.start("s")])

    # the goal check of the item itself is MAIN; the donor is made once per craft: craft costs 5 + 7
    assert solution.values[product.start("s")] == pytest.approx(1 + (1 / 5) * 1 + (4 / 5) * min(1 + 400, 12), rel=1e-9)
    with pytest.raises(ValueError, match="extra inputs"):
        Peek("p", 1, (Action("o", 1, ((GOAL, 1),), (Need("raw", donor_goal),)),))


def random_many_peeks(rng):
    """Base states 0..n-1 and the goal n; one to three of them offer a Peek (up to 4 options, weights up to 10**6)."""
    size = rng.randint(3, 5)

    def kernel(count):
        return tuple(
            (rng.randint(0, size), rng.choice([1, 2, 3, 7, 10, 1000, 10**6])) for _ in range(rng.randint(1, count))
        )

    plain = {
        state: [Action(f"{state}.{i}", rng.randint(1, 20) / 4, kernel(3)) for i in range(rng.choice([0, 1, 1, 2]))]
        for state in range(size)
    }
    peeks = {}
    for state in rng.sample(range(size), rng.randint(1, 3)):
        options = tuple(
            Action(f"o{a}", rng.randint(1, 20) / 4, kernel(3))
            for a in range(rng.randint(1, 4))
        )
        if math.prod(len({s for s, _ in option.outcomes}) for option in options) > 24:
            options = options[:2]
        fallback = tuple(Action(f"f{i}", rng.randint(1, 20) / 4, kernel(2)) for i in range(rng.choice([0, 1, 1, 2])))
        peeks[state] = Peek(f"lock {state}", rng.randint(1, 20) / 4, options, fallback)
    return size, plain, peeks


def product_of_peeks(size, plain, peeks):
    """The explicit product expansion: each Lock leads to a react state per combination of one result per option."""
    table = {state: list(actions) for state, actions in plain.items()}
    for state, peek in peeks.items():
        merged = []
        for option in peek.options:
            kernel = {}
            for result, weight in option.outcomes:
                kernel[result] = kernel.get(result, 0) + weight
            merged.append(tuple(kernel.items()))
        outcomes = []
        for combo in itertools.product(*merged):
            node = ("react", state, tuple(result for result, _ in combo))
            outcomes.append(Outcome(node, math.prod(weight for _, weight in combo)))
            table[node] = [
                Action(option.label, option.cost, ((result, 1),)) for option, (result, _) in zip(peek.options, combo)
            ] + list(peek.fallback)
        table[state].append(Action(peek.label, peek.cost, tuple(outcomes)))
    return TabularModel([size], table)


@pytest.mark.parametrize("seed", range(400))
def test_several_peek_states_with_mutual_dependence_equal_the_product_expansion(seed):
    rng = random.Random(seed)
    size, plain, peeks = random_many_peeks(rng)
    model = TabularModel([size], {s: [*acts, *([peeks[s]] if s in peeks else [])] for s, acts in plain.items()})

    found = solve_peek(model, range(size))
    reference = solve(product_of_peeks(size, plain, peeks), range(size))

    for state in range(size):
        value, exact = found.values[state], reference.values[state]
        if exact == math.inf:
            assert value == math.inf, (seed, state)
        else:
            slack = (found.error_bound + reference.error_bound) * exact + 1e-12 * exact
            assert abs(value - exact) <= slack, (seed, state, value, exact)
