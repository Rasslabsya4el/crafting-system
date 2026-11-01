"""The mass-closed pre-check and `banned` states of the finite-state analysis (#179, ADR-0022 guard 1).

Hand-built tiny graphs go through `build_graph` and `proper_states` (and `solve` for the values);
a naive repeated-pass version of the pre-check is the oracle of the fuzz.
"""

import math
import random
from fractions import Fraction

import pytest
from ssp_helpers import GOAL, act, model
from ssp_oracles import random_ssp, to_model

from crafting_system.solver import Action, TabularModel, solve
from crafting_system.solver._graph import _mass_closed, _settle, build_graph, proper_states

BIG = 1 << 70


def need(label, cost, outcomes, inputs):
    """An action with extra inputs: `need("a", 1, [(GOAL, 1)], ["Y", "Y"])` needs two copies of Y."""
    return Action(label, cost, tuple(outcomes), tuple(inputs))


def analyse(table, starts, banned=frozenset(), goals=(GOAL,)):
    """`(graph, alive, in_y)` and a helper mapping state names to their indices."""
    graph = build_graph(TabularModel(goals, table), starts)
    index = {state: i for i, state in enumerate(graph.states)}
    alive, in_y = proper_states(graph, {index[b] for b in banned})
    return graph, alive, in_y, index


def alive_labels(graph, alive):
    return {graph.label[k] for k in range(len(alive)) if alive[k]}


def buy(label, cost=5):
    return act(label, cost, (GOAL, 1))


def test_two_copies_of_each_other_are_infinite_without_a_sweep():
    # X needs two Y and Y needs X; both also reach the goal by their own outcome.
    table = {
        "X": [need("x", 1, [(GOAL, 1)], ["Y", "Y"])],
        "Y": [need("y", 1, [(GOAL, 1)], ["X"])],
    }
    graph, alive, in_y, index = analyse(table, ["X"])
    assert in_y[index[GOAL]] and not in_y[index["X"]] and not in_y[index["Y"]]
    assert not any(alive)

    solution = solve(model(table), ["X"], max_sweeps=1)  # one sweep would raise ConvergenceError

    assert solution.values["X"] == math.inf and solution.values["Y"] == math.inf
    assert solution.values[GOAL] == 0.0
    assert solution.policy == {}
    assert solution.error_bound == 0.0


def test_a_cycle_of_inputs_with_one_copy_each_is_infinite():
    table = {
        "X": [need("x", 1, [(GOAL, 1)], ["Y"])],
        "Y": [need("y", 1, [(GOAL, 1)], ["Z"])],
        "Z": [need("z", 1, [(GOAL, 1)], ["X"])],
    }
    graph, alive, in_y, index = analyse(table, ["X"])
    assert [in_y[index[s]] for s in "XYZ"] == [False] * 3

    solution = solve(model(table), ["X"], max_sweeps=1)

    assert [solution.values[s] for s in "XYZ"] == [math.inf] * 3


def test_a_donor_that_can_be_bought_breaks_the_cycle():
    # X needs one Y; Y has a buy action straight to the goal as well as one that needs X.
    table = {
        "X": [need("x", 2, [(GOAL, 1)], ["Y"])],
        "Y": [buy("buy-y"), need("y", 1, [(GOAL, 1)], ["X"])],
    }
    graph, alive, in_y, index = analyse(table, ["X"])
    assert in_y[index["X"]] and in_y[index["Y"]]
    assert alive_labels(graph, alive) == {"x", "buy-y", "y"}  # every action is still alive

    solution = solve(model(table), ["X"])

    assert solution.values["Y"] == pytest.approx(5.0)  # the cheaper action; going through X costs more
    assert solution.values["X"] == pytest.approx(7.0)


def test_inputs_can_carry_the_mass_that_leaks_through_the_outcomes():
    # X: weight 1 to the goal and 1 to T (outside D), L = 2, plus one input Y: mass W * 1 = 2 >= L.
    table = {
        "X": [need("x", 1, [(GOAL, 1), ("T", 1)], ["Y"])],
        "Y": [need("y", 1, [(GOAL, 1)], ["X"])],
        "T": [buy("buy-t")],
    }
    graph, alive, in_y, index = analyse(table, ["X"])
    assert not in_y[index["X"]] and not in_y[index["Y"]]
    assert in_y[index["T"]]
    assert _mass_closed(graph, *_settle(graph, frozenset())) == {index["X"], index["Y"]}
    assert solve(model(table), ["X"], max_sweeps=1).values["X"] == math.inf


def test_leaking_mass_without_enough_input_is_not_closed():
    # Same shape, but X leaves half of its weight to T and takes no input: the mass into D is 0.
    table = {
        "X": [need("x", 1, [("Y", 1), ("T", 3)], [])],
        "Y": [need("y", 1, [(GOAL, 1)], ["X"])],
        "T": [buy("buy-t")],
    }
    graph, alive, in_y, index = analyse(table, ["X"])
    assert in_y[index["X"]] and in_y[index["Y"]]
    assert _mass_closed(graph, *_settle(graph, frozenset())) == set()


def test_a_self_loop_does_not_stop_an_input_from_closing_the_action():
    # X: goal 1, self-loop 3, input Y: L = 1, W = 4, mass W * 1 >= L; Y needs X once.
    table = {
        "X": [need("x", 1, [(GOAL, 1), ("X", 3)], ["Y"])],
        "Y": [need("y", 1, [(GOAL, 1)], ["X"])],
    }
    graph, alive, in_y, index = analyse(table, ["X"])
    assert not in_y[index["X"]] and not in_y[index["Y"]]


def test_the_mass_closed_set_spans_two_components():
    # {A, B} is a cycle of inputs; C needs A in a component of its own, downstream of the cycle's
    # input edge; E reaches the goal alone and stays.
    table = {
        "C": [need("c", 1, [(GOAL, 1)], ["A"])],
        "A": [need("a", 1, [(GOAL, 1)], ["B"])],
        "B": [need("b", 1, [(GOAL, 1)], ["A"])],
        "E": [buy("buy-e")],
        "F": [need("f", 1, [(GOAL, 1)], ["E"])],
    }
    graph, alive, in_y, index = analyse(table, ["C", "E", "F"])
    settled = _settle(graph, frozenset())
    assert _mass_closed(graph, *settled) == {index[s] for s in "ABC"}
    assert [in_y[index[s]] for s in "ABC"] == [False] * 3
    assert in_y[index["E"]] and in_y[index["F"]]  # F needs E, E is finite
    assert alive_labels(graph, alive) == {"buy-e", "f"}

    values = solve(model(table), ["C", "E", "F"], max_sweeps=1).values
    assert [values[s] for s in "ABC"] == [math.inf] * 3
    assert values["E"] == 5.0 and values["F"] == 6.0


def test_a_state_needing_an_infinite_state_falls_even_when_not_closed_itself():
    # D is not closed under C (C reaches the goal on its own), yet C's only action needs A.
    table = {
        "A": [need("a", 1, [(GOAL, 1)], ["A2"])],
        "A2": [need("a2", 1, [(GOAL, 1)], ["A"])],
        "C": [
            need("c", 1, [(GOAL, 5), ("A", 1)], []),
            need("c2", 1, [(GOAL, 1)], ["A"]),
            buy("c-buy"),
        ],
    }
    graph, alive, in_y, index = analyse(table, ["C"])
    assert not in_y[index["A"]] and not in_y[index["A2"]]
    assert in_y[index["C"]]
    assert alive_labels(graph, alive) == {"c-buy"}  # c reaches A, c2 needs it; both die with A


def test_banned_state_kills_the_actions_that_use_it_and_the_states_left_bare():
    table = {
        "A": [buy("a0"), act("a1", 1, ("B", 1), (GOAL, 1))],
        "B": [buy("b0")],
        "C": [need("c0", 1, [(GOAL, 1)], ["B"])],
        "E": [act("e0", 1, ("A", 1), (GOAL, 1))],
        "F": [act("f0", 1, ("B", 1), (GOAL, 1))],
    }
    starts = ["A", "B", "C", "E", "F"]
    graph, alive, in_y, index = analyse(table, starts)
    assert all(in_y)

    graph, alive, in_y, index = analyse(table, starts, banned={"B"})

    assert not in_y[index["B"]]
    assert not in_y[index["C"]]  # its only action needs B
    assert not in_y[index["F"]]  # its only action has B as an outcome
    assert in_y[index["A"]] and in_y[index["E"]] and in_y[index[GOAL]]
    assert alive_labels(graph, alive) == {"a0", "e0"}  # a1 used B as an outcome


def test_an_empty_ban_is_the_plain_analysis():
    table = {"A": [buy("a0")]}
    graph, alive, in_y, _ = analyse(table, ["A"])
    again = proper_states(graph, [])
    assert again == (alive, in_y)


def test_banned_state_inside_a_cycle_component():
    # A -> B -> C -> A with a way out at A; banning A cuts the ring, banning B leaves A alone.
    table = {
        "A": [buy("a-out"), act("a-b", 1, ("B", 1))],
        "B": [act("b-c", 1, ("C", 1))],
        "C": [act("c-a", 1, ("A", 1))],
    }
    graph, alive, in_y, index = analyse(table, ["A"])
    assert all(in_y)

    graph, alive, in_y, index = analyse(table, ["A"], banned={"A"})
    assert not any(in_y[index[s]] for s in "ABC")
    assert not any(alive)

    graph, alive, in_y, index = analyse(table, ["A"], banned={"B"})
    assert in_y[index["A"]] and not in_y[index["B"]] and in_y[index["C"]]  # C still leaves by A
    assert alive_labels(graph, alive) == {"a-out", "c-a"}

    graph, alive, in_y, index = analyse(table, ["A"], banned={"C"})
    assert in_y[index["A"]] and not in_y[index["B"]] and not in_y[index["C"]]
    assert alive_labels(graph, alive) == {"a-out"}


def test_banned_state_inside_a_cycle_with_inputs():
    # P and Q need each other and can each be bought; R needs P and sits in the same component.
    table = {
        "P": [buy("buy-p"), need("p", 1, [(GOAL, 1), ("R", 1)], ["Q"])],
        "Q": [buy("buy-q"), need("q", 1, [(GOAL, 1)], ["P"])],
        "R": [need("r", 1, [("P", 1), (GOAL, 1)], [])],
    }
    graph, alive, in_y, index = analyse(table, ["P"])
    assert all(in_y)
    assert alive_labels(graph, alive) == {"buy-p", "p", "buy-q", "q", "r"}

    graph, alive, in_y, index = analyse(table, ["P"], banned={"Q"})
    assert in_y[index["P"]] and in_y[index["R"]] and not in_y[index["Q"]]
    assert alive_labels(graph, alive) == {"buy-p", "r"}  # p needs Q

    graph, alive, in_y, index = analyse(table, ["P"], banned={"R"})
    assert alive_labels(graph, alive) == {"buy-p", "buy-q", "q"}  # p has R as an outcome


def test_banned_without_inputs_keeps_the_existing_analysis_elsewhere():
    table = {
        "A": [act("a", 1, ("B", 1), (GOAL, 1))],
        "B": [act("b", 1, ("A", 1), (GOAL, 1))],
    }
    graph, alive, in_y, index = analyse(table, ["A"], banned={"A"})
    assert not in_y[index["A"]] and not in_y[index["B"]] and not any(alive)


def test_huge_weights_are_compared_as_integers():
    # X: Y with weight 2^70 and the goal with weight 1 (L = 2^70 + 1), one copy of Z outside D.
    # The mass into D is 2^70, one short of L; as floats the two would be equal.
    table = {
        "X": [need("x", 1, [("Y", BIG), (GOAL, 1)], ["Z"])],
        "Y": [need("y", 1, [("X", BIG), (GOAL, 1)], ["Z"])],
        "Z": [buy("buy-z")],
    }
    graph, alive, in_y, index = analyse(table, ["X"])
    assert in_y[index["X"]] and in_y[index["Y"]] and in_y[index["Z"]]
    assert graph.big_weights  # the weights live apart
    assert _mass_closed(graph, *_settle(graph, frozenset())) == set()


def test_huge_weights_that_close_the_mass_are_found():
    # Same, but X also takes one copy of Y: W * 1 = 2^70 + 1 makes the mass at least L.
    table = {
        "X": [need("x", 1, [("Y", BIG), (GOAL, 1)], ["Y"])],
        "Y": [need("y", 1, [(GOAL, 1)], ["X"])],
    }
    graph, alive, in_y, index = analyse(table, ["X"])
    assert not in_y[index["X"]] and not in_y[index["Y"]]
    # and with a self-loop of 2^65 beside weights of 2^70
    table = {
        "X": [need("x", 1, [(GOAL, BIG), ("X", 1 << 65)], ["Y"])],
        "Y": [need("y", 1, [(GOAL, 1)], ["X"])],
    }
    graph, alive, in_y, index = analyse(table, ["X"])
    assert not in_y[index["X"]] and not in_y[index["Y"]]


def test_a_closed_pair_is_dropped_while_a_cheap_donor_still_works():
    # Z needs one copy of the donor D1 (bought); the pair U, V is closed and falls.
    table = {
        "Z": [need("z", 1, [(GOAL, 1), ("Z", 2)], ["D1"])],
        "D1": [buy("buy-d1", 4)],
        "U": [need("u", 1, [(GOAL, 1)], ["V", "V"])],
        "V": [need("v", 1, [(GOAL, 1)], ["U"])],
    }
    graph, alive, in_y, index = analyse(table, ["Z", "U"])
    assert in_y[index["Z"]] and in_y[index["D1"]]
    assert not in_y[index["U"]] and not in_y[index["V"]]
    values = solve(model(table), ["Z", "U"]).values
    assert values["Z"] == pytest.approx(3.0 * (1 + 4.0))
    assert values["U"] == math.inf


# -- the input-free path ------------------------------------------------------------------------


def check_plain(graph):
    alive, in_y = proper_states(graph)
    assert (alive, in_y) == _settle(graph, frozenset())
    assert (alive, in_y) == proper_states(graph, frozenset())
    assert (alive, in_y) == proper_states(graph, banned=())
    return alive, in_y


def test_input_free_graphs_are_decided_by_the_plain_analysis():
    finite = infinite = 0
    for seed in range(300):
        spec = random_ssp(seed, ensure_proper=seed % 2 == 0)
        graph = build_graph(to_model(spec), range(spec[0]))
        alive, in_y = check_plain(graph)
        finite += all(in_y)
        infinite += not all(in_y)
    assert finite > 20 and infinite > 20


# -- the pre-check against a naive version ------------------------------------------------------


def naive_proper_states(graph):
    """`_settle` plus repeated full passes of the greatest fixpoint with exact `Fraction` rows."""
    index = {st: i for i, st in enumerate(graph.states)}
    banned = frozenset()
    while True:
        alive, in_y = _settle(graph, banned)
        d = {s for s in range(len(graph.states)) if in_y[s] and not graph.goal[s]}
        while True:
            drop = set()
            for s in d:
                for k in graph.state_actions[s]:
                    if not alive[k]:
                        continue
                    action = graph.original_action(k)
                    leave = sum(w for st, w in action.outcomes if st != graph.states[s])
                    total = sum(w for _, w in action.outcomes)
                    mass = sum(
                        Fraction(w, leave)
                        for st, w in action.outcomes
                        if st != graph.states[s] and index[st] in d
                    ) + sum(
                        Fraction(total, leave) for st in action.extra_inputs if index[st] in d
                    )
                    if mass < 1:
                        drop.add(s)
            if not drop:
                break
            d -= drop
        if not d:
            return alive, in_y
        banned |= d


def random_input_table(rng):
    n = rng.randint(2, 6)
    names = list(range(n))
    table = {}
    for s in names:
        actions = []
        for a in range(rng.choice((0, 1, 1, 2, 2, 3))):
            outcomes = [(rng.choice(names + [GOAL]), rng.randint(1, 3)) for _ in range(rng.randint(1, 3))]
            if rng.random() < 0.2:
                outcomes.append((GOAL, rng.choice((1, BIG))))
            inputs = [rng.choice(names) for _ in range(rng.choice((0, 0, 1, 1, 2)))]
            actions.append(Action(f"{s}.{a}", 1.0 + a, tuple(outcomes), tuple(inputs)))
        table[s] = actions
    return table, names


def test_fuzz_matches_the_naive_repeated_pass_version():
    rng = random.Random(17901)
    pruned = 0
    for _ in range(1500):
        table, names = random_input_table(rng)
        graph = build_graph(TabularModel([GOAL], table), names)
        alive, in_y = proper_states(graph)
        assert (alive, in_y) == naive_proper_states(graph)
        plain = _settle(graph, frozenset())
        pruned += plain[1] != in_y
    assert pruned > 50  # the generator does produce closed sets that the plain analysis keeps
