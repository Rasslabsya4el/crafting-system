"""The steps of a policy: one step per player action (OR-18), its chances the exact mixture of its states (OR-20).

The expected values in these tests are computed in the tests themselves, by hand on small chains and by an exact
`Fraction` elimination (`exact_visits`) on random ones; the flow solves the same chain in floats.
"""

import math
import random
from collections import Counter
from fractions import Fraction

import pytest

from crafting_system.cli import _route_flow
from crafting_system.cli._reach import policy_states, reach_probabilities
from crafting_system.cli._route_flow import Edge, Flow, Step, build_flow
from crafting_system.risk import evaluate
from crafting_system.solver import Action, Outcome


def act(label, *outcomes, cost=1.0):
    return Action(label, cost, tuple(Outcome(state, weight) for state, weight in outcomes))


def is_goal(state):
    return state == "goal"


def step_with(flow: Flow, state) -> Step:
    return flow.steps[flow.step_of[state] - 1]


def edge_to(step: Step, target: int | None) -> Edge:
    (found,) = [edge for edge in step.edges if edge.to == target]
    return found


def exact_visits(start, policy) -> dict:
    """The expected visits of every state with an action from `start`, exactly: Gauss-Jordan over `Fraction`s on (I - Q)^T v = e_start.

    Only for a policy that always finishes (every state it reaches has an action and can reach the goal).
    """
    states = [s for s in policy_states(start, policy, is_goal) if not is_goal(s)]
    index = {s: k for k, s in enumerate(states)}
    size = len(states)
    rows = [[Fraction(0)] * size + [Fraction(1 if k == 0 else 0)] for k in range(size)]
    for state in states:
        total = sum(weight for _, weight in policy[state].outcomes)
        rows[index[state]][index[state]] += 1
        for successor, weight in policy[state].outcomes:
            if successor in index:
                rows[index[successor]][index[state]] -= Fraction(weight, total)
    for column in range(size):
        pivot = next(r for r in range(column, size) if rows[r][column] != 0)
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        rows[column] = [value / divisor for value in rows[column]]
        for r in range(size):
            if r != column and rows[r][column] != 0:
                factor = rows[r][column]
                rows[r] = [value - factor * other for value, other in zip(rows[r], rows[column])]
    return {state: rows[index[state]][size] for state in states}


def exact_mixture(step: Step, policy, visits) -> dict:
    """The chance per use of each outcome (successor state) mixed over the step's states by their exact visits."""
    total = sum(visits[state] for state in step.states)
    mixed: dict = {}
    for state in step.states:
        weight_total = sum(weight for _, weight in policy[state].outcomes)
        for successor, weight in policy[state].outcomes:
            mixed[successor] = mixed.get(successor, Fraction(0)) + visits[state] * Fraction(weight, weight_total) / total
    return mixed


def test_a_state_looping_on_itself_is_one_step_with_a_goal_edge_and_an_again_edge():
    policy = {"S": act("R12", ("S", 3), ("goal", 1))}

    flow = build_flow("S", policy, is_goal)

    assert len(flow.steps) == 1
    (step,) = flow.steps
    assert step.number == 1
    assert step.states == ("S",)
    assert step.action is policy["S"]
    assert step.reason is None
    assert [(edge.kind, edge.to) for edge in step.edges] == [("goal", None), ("again", 1)]
    assert step.edges[0].chance == pytest.approx(0.25)
    assert step.edges[0].states == ("goal",)
    assert step.edges[1].chance == pytest.approx(0.75)
    assert step.edges[1].states == ("S",)
    assert step.uses == pytest.approx(4.0)  # 1 / q
    assert step.reached == pytest.approx(1.0)
    assert flow.step_of == {"S": 1}


def test_a_start_that_is_a_goal_has_no_steps():
    flow = build_flow("goal", {}, is_goal)

    assert flow.steps == ()
    assert dict(flow.step_of) == {}


def test_a_chain_of_two_states_with_the_same_action_is_one_step_that_leads_to_itself_and_the_goal():
    policy = {"A": act("exalt", ("B", 1)), "B": act("exalt", ("goal", 1))}

    flow = build_flow("A", policy, is_goal)

    (step,) = flow.steps
    assert step.states == ("A", "B") and step.uses == pytest.approx(2.0)
    assert [(edge.kind, edge.to) for edge in step.edges] == [("goal", None), ("again", 1)]
    assert [edge.chance for edge in step.edges] == [pytest.approx(0.5), pytest.approx(0.5)]  # one finish in two uses


def test_look_alike_states_with_the_same_label_and_different_chances_are_one_step_with_their_reach_weighted_mixture():
    # S goes to A (1/4) or B (3/4). A: goal 1/2, else R. B: goal 1/4, else R. R restarts to S.
    # The cycle returns to S with 1/4 * 1/2 + 3/4 * 3/4 = 11/16, so S is visited 16/5 times, A 4/5 and B 12/5.
    # The mixture of "x" is then (4/5 * 1/2 + 12/5 * 1/4) / (16/5) = 5/16 for the goal, not 1/2 or 1/4 and not 3/8 (the plain mean).
    policy = {
        "S": act("go", ("A", 1), ("B", 3)),
        "A": act("x", ("goal", 1), ("R", 1)),
        "B": act("x", ("goal", 1), ("R", 3)),
        "R": act("restart", ("S", 1)),
    }

    flow = build_flow("S", policy, is_goal)

    assert flow.step_of["A"] == flow.step_of["B"]
    x = step_with(flow, "A")
    assert x.weights == (pytest.approx(0.8), pytest.approx(2.4))
    assert x.uses == pytest.approx(3.2)
    assert edge_to(x, None).chance == pytest.approx(5 / 16)
    assert edge_to(x, flow.step_of["R"]).chance == pytest.approx(11 / 16)
    assert len(flow.steps) == 3  # go, x, restart


def test_states_with_the_same_label_and_the_same_chances_into_the_same_successor_are_one_step():
    policy = {
        "S": act("go", ("A", 1), ("B", 1)),
        "A": act("x", ("goal", 1), ("dead", 1)),
        "B": act("x", ("goal", 2), ("dead", 2)),  # the same chances, other weights
    }

    flow = build_flow("S", policy, is_goal)

    assert flow.step_of["A"] == flow.step_of["B"]
    shared = step_with(flow, "A")
    assert shared.states == ("A", "B")  # breadth-first order
    assert [edge.kind for edge in shared.edges] == ["goal", "failure"]  # the dead end stops the route
    assert shared.edges[1].states == ("dead",)
    assert shared.uses == pytest.approx(1.0)  # one use, shared by the two states
    assert shared.reached == pytest.approx(1.0)
    assert len(flow.steps) == 3  # the start, the shared step, the dead end


def test_the_same_action_at_two_places_of_a_route_with_different_successors_is_one_step_with_a_branch_for_each():
    policy = {
        "S": act("essence", ("X", 1), ("Y", 1)),
        "X": act("annul", ("goal", 1), ("P", 1)),
        "Y": act("annul", ("goal", 1), ("Q", 1)),
        "P": act("fix", ("goal", 1)),
        "Q": act("other", ("goal", 1)),
    }

    flow = build_flow("S", policy, is_goal)

    assert flow.step_of["X"] == flow.step_of["Y"]
    annul = step_with(flow, "X")
    assert annul.action.label == "annul"
    assert [(edge.kind, edge.chance) for edge in annul.edges] == [
        ("goal", pytest.approx(0.5)),
        ("forward", pytest.approx(0.25)),
        ("forward", pytest.approx(0.25)),
    ]
    assert {edge_to(annul, flow.step_of["P"]).states, edge_to(annul, flow.step_of["Q"]).states} == {("P",), ("Q",)}


def test_the_same_action_with_equivalent_successors_is_one_step_even_when_the_successors_differ_as_states():
    policy = {
        "S": act("essence", ("X", 1), ("Y", 1)),
        "X": act("annul", ("goal", 1), ("P", 1)),
        "Y": act("annul", ("goal", 1), ("Q", 1)),
        "P": act("fix", ("goal", 1)),
        "Q": act("fix", ("goal", 1)),
    }

    flow = build_flow("S", policy, is_goal)

    assert flow.step_of["X"] == flow.step_of["Y"]
    assert flow.step_of["P"] == flow.step_of["Q"]
    assert len(flow.steps) == 3


def test_a_dead_end_state_is_a_step_with_no_action_and_its_reason():
    policy = {"S": act("go", ("goal", 1), ("stuck", 1), ("gap", 2))}
    reasons = {"stuck": "no rule matches this state", "gap": "no rule matches this state"}

    flow = build_flow("S", policy, is_goal, reasons)

    stuck = step_with(flow, "stuck")
    assert stuck.action is None
    assert stuck.reason == "no rule matches this state"
    assert stuck.edges == ()
    assert stuck.uses is None
    assert stuck.states == ("stuck", "gap")  # the same reason: one step
    assert stuck.reached == pytest.approx(0.75)
    assert [(edge.kind, edge.to) for edge in flow.steps[0].edges] == [("goal", None), ("failure", 2)]


def test_dead_ends_with_different_reasons_are_different_steps():
    policy = {"S": act("go", ("a", 1), ("b", 1))}
    reasons = {"a": "cannot be used here", "b": "no rule matches this state"}

    flow = build_flow("S", policy, is_goal, reasons)

    assert flow.step_of["a"] != flow.step_of["b"]
    assert step_with(flow, "a").reason == "cannot be used here"
    assert step_with(flow, "b").reason == "no rule matches this state"


def test_a_dead_end_without_a_given_reason_has_reason_none():
    flow = build_flow("S", {"S": act("go", ("dead", 1))}, is_goal)

    assert step_with(flow, "dead").action is None
    assert step_with(flow, "dead").reason is None


def test_a_start_with_no_action_is_one_step_reached_for_sure():
    flow = build_flow("S", {}, is_goal, {"S": "no rule matches this state"})

    (step,) = flow.steps
    assert (step.action, step.uses, step.reached, step.edges) == (None, None, 1.0, ())


def test_edges_are_failure_again_and_forward_with_the_goal_first():
    policy = {
        "A": act("a", ("B", 1)),
        "B": act("b", ("A", 1), ("B", 1), ("C", 1), ("goal", 1)),
        "C": act("c", ("goal", 1)),
    }

    flow = build_flow("A", policy, is_goal)

    b = step_with(flow, "B")
    assert [(edge.kind, edge.to) for edge in b.edges] == [("goal", None), ("forward", 1), ("again", 2), ("forward", 3)]
    assert math.fsum(edge.chance for edge in b.edges) == pytest.approx(1.0)


def test_step_numbers_follow_the_first_state_met_breadth_first():
    policy = {
        "S": act("s", ("B", 1), ("A", 1)),
        "B": act("b", ("goal", 1)),
        "A": act("a", ("goal", 1)),
    }

    flow = build_flow("S", policy, is_goal)

    assert [step.states for step in flow.steps] == [("S",), ("B",), ("A",)]
    assert flow.step_of == {"S": 1, "B": 2, "A": 3}


def test_reached_is_the_exact_chance_on_a_hand_computed_policy():
    # S: to A 1/4, to B 3/4. A: goal. B: goal 1/3, back to S 2/3 (so S is visited again).
    policy = {
        "S": act("s", ("A", 1), ("B", 3)),
        "A": act("a", ("goal", 1)),
        "B": act("b", ("goal", 1), ("S", 2)),
    }

    flow = build_flow("S", policy, is_goal)

    # A is entered on a pass through S with chance 1/4; a pass goes to B and back to S with 3/4 * 2/3 = 1/2.
    # P(ever A) = (1/4) / (1 - 1/2) = 1/2. B is missed only when the first pass goes to A, which ends the run: 3/4.
    assert step_with(flow, "S").reached == pytest.approx(1.0)
    assert step_with(flow, "A").reached == pytest.approx(0.5)
    assert step_with(flow, "B").reached == pytest.approx(0.75)
    expected = reach_probabilities("S", policy, is_goal)
    for state in ("S", "A", "B"):
        assert step_with(flow, state).reached == pytest.approx(expected[state])


def test_the_uses_of_a_step_are_the_expected_visits_of_its_states():
    policy = {
        "S": act("s", ("A", 1), ("B", 3)),
        "A": act("a", ("goal", 1)),
        "B": act("b", ("goal", 1), ("S", 2)),
    }

    flow = build_flow("S", policy, is_goal)

    # Visits of S: 1 / (1 - 3/4 * 2/3) = 2. A is left to once per visit of S with chance 1/4: 2 * 1/4 = 1/2. B: 3/2.
    assert step_with(flow, "S").uses == pytest.approx(2.0)
    assert step_with(flow, "A").uses == pytest.approx(0.5)
    assert step_with(flow, "B").uses == pytest.approx(1.5)


def test_the_uses_times_the_cost_of_the_steps_is_the_mean_cost_of_the_policy():
    policy = {
        "S": act("s", ("A", 1), ("B", 3), ("S", 2), cost=3.0),
        "A": act("a", ("goal", 1), ("B", 1), cost=5.0),
        "B": act("b", ("goal", 1), ("S", 2), ("B", 1), cost=2.0),
    }

    flow = build_flow("S", policy, is_goal)

    total = sum(step.uses * step.action.cost for step in flow.steps)
    assert total == pytest.approx(evaluate(policy, "S", is_goal).mean.value)


def test_states_that_the_policy_never_reaches_are_not_in_the_flow():
    policy = {"S": act("s", ("goal", 1)), "orphan": act("o", ("goal", 1))}

    flow = build_flow("S", policy, is_goal)

    assert "orphan" not in flow.step_of
    assert [step.states for step in flow.steps] == [("S",)]


def test_a_policy_that_can_never_finish_has_infinite_uses_and_does_not_crash():
    policy = {"S": act("restart", ("S", 1))}

    flow = build_flow("S", policy, is_goal)

    (step,) = flow.steps
    assert step.uses == math.inf
    assert step.reached == 1.0
    assert [(edge.kind, edge.chance) for edge in step.edges] == [("again", 1.0)]


def random_policy(rng: random.Random):
    size = rng.randint(2, 9)
    names = [f"s{i}" for i in range(size)]
    labels = ["a", "b", "c"]
    policy = {}
    for name in names:
        if rng.random() < 0.15:
            continue  # a dead end
        pool = [*names, "goal"]
        targets = rng.sample(pool, rng.randint(1, min(4, len(pool))))
        weights = [rng.choice([1, 1, 2, 3]) for _ in targets]
        policy[name] = act(rng.choice(labels), *zip(targets, weights))
    return names[0], policy


def test_every_reachable_non_goal_state_is_in_exactly_one_step_and_a_step_shares_one_action():
    rng = random.Random(78)
    for _ in range(200):
        start, policy = random_policy(rng)

        flow = build_flow(start, policy, is_goal)

        expected = [s for s in policy_states(start, policy, is_goal) if not is_goal(s)]
        listed = Counter(state for step in flow.steps for state in step.states)
        assert set(listed) == set(expected)
        assert all(count == 1 for count in listed.values())
        assert dict(flow.step_of) == {s: step.number for step in flow.steps for s in step.states}
        assert [step.number for step in flow.steps] == list(range(1, len(flow.steps) + 1))
        assert flow.step_of[start] == 1
        for step in flow.steps:
            labels = {policy[s].label if s in policy else None for s in step.states}
            assert len(labels) == 1


def finishing_policies(seed: int, wanted: int):
    """Random policies that always finish, as many as `wanted`."""
    rng = random.Random(seed)
    found = 0
    while found < wanted:
        start, policy = random_policy(rng)
        policy = {s: Action(a.label, 1.0 + int(s[1:]) % 3, a.outcomes) for s, a in policy.items()}
        if evaluate(policy, start, is_goal).success_probability.value == 1.0:
            found += 1
            yield start, policy


def test_the_chances_of_a_step_are_the_exact_reach_weighted_mixture_of_its_states():
    checked = 0
    for start, policy in finishing_policies(7878, 60):
        flow = build_flow(start, policy, is_goal)
        visits = exact_visits(start, policy)

        for step in flow.steps:
            mixed = exact_mixture(step, policy, visits)
            wanted = {}
            for successor, chance in mixed.items():
                where = None if is_goal(successor) else flow.step_of[successor]
                wanted[where] = wanted.get(where, 0.0) + float(chance)
            got = {}
            for edge in step.edges:
                got[edge.to] = got.get(edge.to, 0.0) + edge.chance
            assert got == pytest.approx(wanted, rel=1e-9, abs=1e-12)
            assert math.fsum(got.values()) == pytest.approx(1.0)
            assert step.uses == pytest.approx(float(sum(visits[s] for s in step.states)), rel=1e-9)
            assert step.weights == pytest.approx(tuple(float(visits[s]) for s in step.states), rel=1e-9)
            checked += 1
    assert checked >= 60


def test_two_steps_never_share_an_action_label():
    rng = random.Random(787)
    for _ in range(100):
        start, policy = random_policy(rng)

        flow = build_flow(start, policy, is_goal)

        labels = [step.action.label for step in flow.steps if step.action is not None]
        assert len(labels) == len(set(labels)), "one action split into two steps"


def test_the_flow_is_deterministic():
    rng = random.Random(1)
    start, policy = random_policy(rng)

    assert build_flow(start, policy, is_goal) == build_flow(start, policy, is_goal)


def test_uses_times_cost_is_the_mean_cost_on_random_policies_that_always_finish():
    for start, policy in finishing_policies(780, 40):  # a label can carry different costs here: the step's cost is their mixture
        flow = build_flow(start, policy, is_goal)

        total = sum(step.uses * step.cost for step in flow.steps)

        assert total == pytest.approx(evaluate(policy, start, is_goal).mean.value, rel=1e-6)


def test_an_edge_to_a_dearer_or_a_later_numbered_step_is_forward_not_a_failure():
    # W (worse) is met before G (good) breadth-first and is dear to finish; nothing wanted is lost on the way (PRES-6).
    policy = {
        "S": act("s", ("W", 3), ("G", 1)),
        "W": act("w", ("goal", 1), cost=20.0),
        "G": act("g", ("goal", 1)),
    }

    flow = build_flow("S", policy, is_goal)

    start = flow.steps[0]
    assert flow.step_of["W"] < flow.step_of["G"]
    assert [(edge.kind, edge.to) for edge in start.edges] == [("forward", 2), ("forward", 3)]
    assert edge_to(start, flow.step_of["W"]).chance == pytest.approx(0.75)


def test_a_use_that_loses_a_wanted_mod_is_a_failure_edge_apart_from_the_uses_that_do_not():
    # From S the use lands in K (kept) or L (lost), and in both cases in the same next step "c".
    policy = {
        "S": act("s", ("K", 3), ("L", 1)),
        "K": act("c", ("goal", 1)),
        "L": act("c", ("goal", 1)),
    }

    flow = build_flow("S", policy, is_goal, failed=lambda before, after: ("wanted mod",) if after == "L" else ())

    start = flow.steps[0]
    assert [(edge.kind, edge.to, edge.chance) for edge in start.edges] == [
        ("forward", 2, pytest.approx(0.75)),
        ("failure", 2, pytest.approx(0.25)),
    ]
    assert start.edges[1].states == ("L",) and start.edges[1].lost == ("wanted mod",)
    assert start.edges[0].lost == ()


def test_the_wanted_mods_lost_on_the_way_to_one_step_are_one_failure_edge_listing_all_of_them():
    policy = {
        "S": act("s", ("P", 1), ("Q", 1), ("R", 2)),
        "P": act("c", ("goal", 1)),
        "Q": act("c", ("goal", 1)),
        "R": act("c", ("goal", 1)),
    }

    flow = build_flow("S", policy, is_goal, failed=lambda before, after: {"P": ("life",), "Q": ("cold",)}.get(after, ()))

    start = flow.steps[0]
    assert [(edge.kind, edge.chance, edge.lost) for edge in start.edges] == [
        ("forward", pytest.approx(0.5), ()),
        ("failure", pytest.approx(0.5), ("cold", "life")),
    ]


def test_landing_in_a_step_that_restarts_or_has_no_action_is_a_failure_and_a_restart_edge_always_is():
    policy = {
        "S": act("go", ("T", 1), ("D", 1), ("goal", 1)),
        "T": act("restart", ("S", 1)),
    }

    flow = build_flow("S", policy, is_goal, is_restart=lambda action: action.label == "restart")

    assert [(edge.kind, edge.to) for edge in flow.steps[0].edges] == [("goal", None), ("failure", 2), ("failure", 3)]
    assert [(edge.kind, edge.to) for edge in step_with(flow, "T").edges] == [("failure", 1)]


@pytest.mark.parametrize("dense_limit", [1500, 0])
def test_the_chance_of_entering_a_step_is_the_same_by_the_inverse_and_by_one_solve_per_step_and_matches_the_older_dense_solve(monkeypatch, dense_limit):
    """#490: a policy above the (lowered) dense limit has the chance of entering each step, equal to an independent computation.

    The independent one: make the step's states dead ends (a run stops at the first of them), then the chance of ever visiting a state of the step is
    the sum of the visit chances `reach_probabilities` (the older dense solve of the text report) gives its states.
    """
    monkeypatch.setattr(_route_flow, "DENSE_LIMIT", dense_limit)
    checked = 0
    for start, policy in finishing_policies(490, 150):
        flow = build_flow(start, policy, is_goal)
        assert flow.measured and flow.entered
        for step in flow.steps[1:]:
            if step.reached is None or step.action is None:
                continue
            absorbing = {state: action for state, action in policy.items() if state not in set(step.states)}
            chances = reach_probabilities(start, absorbing, is_goal)
            expected = sum(chances.get(state, 0.0) for state in step.states)
            assert step.reached == pytest.approx(expected, rel=1e-8, abs=1e-12), (start, step.states)
            checked += 1
    assert checked > 100


def test_the_chance_of_entering_a_step_that_joins_states_is_one_chance_not_the_sum_of_theirs():
    # S reaches A with 1/4, and A always goes on to B; A and B share the action x, so the run enters the step once.
    policy = {
        "S": act("s", ("A", 1), ("goal", 3)),
        "A": act("x", ("B", 1)),
        "B": act("x", ("goal", 1)),
    }

    flow = build_flow("S", policy, is_goal)

    assert step_with(flow, "A").states == ("A", "B")
    assert step_with(flow, "A").reached == pytest.approx(0.25)
    assert step_with(flow, "A").uses == pytest.approx(0.5)  # A and B once each in a quarter of the runs


def test_an_edge_into_an_earlier_numbered_step_is_forward():
    policy = {
        "S": act("s", ("A", 1), ("B", 1)),
        "A": act("a", ("goal", 1)),
        "B": act("b", ("A", 1)),  # A is numbered before B
    }

    flow = build_flow("S", policy, is_goal)

    assert flow.step_of["A"] < flow.step_of["B"]
    assert [(edge.kind, edge.to) for edge in step_with(flow, "B").edges] == [("forward", flow.step_of["A"])]
    assert [edge.kind for edge in flow.steps[0].edges] == ["forward", "forward"]  # what a step costs to finish decides nothing


def test_every_edge_of_a_restart_is_a_failure():
    policy = {
        "S": act("go", ("X", 1), ("goal", 1), cost=1.0),
        "X": act("restart", ("S", 1), cost=1.0),
    }

    flow = build_flow("S", policy, is_goal, is_restart=lambda action: action.label == "restart")
    plain = build_flow("S", policy, is_goal)

    assert [edge.kind for edge in step_with(flow, "X").edges] == ["failure"]
    assert [edge.kind for edge in step_with(plain, "X").edges] == ["forward"]  # without the restart it is a step like any other


def test_a_step_whose_every_way_out_ends_in_a_step_with_no_action_never_finishes():
    policy = {"S": act("s", ("A", 1)), "A": act("a", ("gap", 1)), "T": act("t", ("goal", 1))}

    flow = build_flow("S", policy, is_goal, {"gap": "no rule matches this state"})

    assert [step.uses for step in flow.steps[:2]] == [math.inf, math.inf]
    assert flow.steps[0].reached == 1.0 and flow.steps[1].reached is None


def test_a_step_that_can_reach_the_goal_and_a_gap_keeps_its_finite_uses():
    policy = {"S": act("s", ("goal", 1), ("gap", 1))}

    (start, _gap) = build_flow("S", policy, is_goal).steps

    assert start.uses == pytest.approx(1.0)


def chain(length: int) -> dict[int, Action]:
    """A line of `length` states, each its own step (its own action), the last one reaching the goal; a miss goes back to 0."""
    policy = {i: act(f"a{i}", (i + 1, 99), (0, 1), cost=1.0 + i / 7) for i in range(length - 1)}
    policy[length - 1] = act(f"a{length - 1}", ("goal", 1), (0, 1))
    return policy


def test_a_chain_of_many_steps_is_solved_and_its_misses_go_back_to_the_start():
    policy = chain(300)

    flow = build_flow(0, policy, is_goal)

    assert len(flow.steps) == 300 and flow.measured
    first = flow.steps[0]
    assert [(edge.kind, edge.to) for edge in first.edges] == [("again", 1), ("forward", 2)]


def test_the_uses_of_a_chain_of_steps_add_up_to_the_mean_cost():
    policy = chain(40)

    flow = build_flow(0, policy, is_goal)

    assert sum(step.uses * step.action.cost for step in flow.steps) == pytest.approx(evaluate(policy, 0, is_goal).mean.value)


def test_a_chain_of_more_steps_than_the_old_cap_is_still_solved(monkeypatch):
    monkeypatch.setattr(_route_flow, "DENSE_LIMIT", 2000)  # one inverse for the 1,599 steps' entry chances, not 1,599 solves (this test is about the cap)
    policy = chain(1600)  # 1,600 steps: the old cap was 1,500 and left the uses and the costs out

    flow = build_flow(0, policy, is_goal)

    assert len(flow.steps) == 1600 and flow.measured
    assert all(step.uses is not None and math.isfinite(step.uses) for step in flow.steps)
    # every state goes on with 0.99 and back to 0 with 0.01, the last one reaches the goal with 1/2: a pass finishes with
    # 0.99^1599 / 2, so state i is visited 2 * 0.99^(i - 1599) times
    assert [step.uses for step in flow.steps[:3]] == pytest.approx([2 * 0.99 ** (i - 1599) for i in range(3)], rel=1e-6)
    assert flow.steps[-1].uses == pytest.approx(2.0, rel=1e-6)


def test_no_silent_limit_is_left_in_the_module():
    assert not hasattr(_route_flow, "MAX_STEPS") and not hasattr(_route_flow, "REFINE_WORK")


def test_a_chance_per_use_too_small_for_one_minus_p_in_floats_is_still_solved_because_no_one_minus_p_is_formed():
    policy = {"A": act("a", ("A", 10**17 - 1), ("goal", 1))}  # 1 - 1e-17 is 1.0 in floats: the inverse of I - Q is singular

    flow = build_flow("A", policy, is_goal)

    assert flow.measured and flow.entered
    (step,) = flow.steps
    assert step.uses == pytest.approx(1e17, rel=1e-9) and step.reached == 1.0  # one in 1e17 leaves: 1e17 uses, as the closed form says
    assert [(edge.kind, edge.to) for edge in step.edges] == [("goal", None), ("again", 1)]


def test_a_flow_whose_visits_no_solve_reaches_stays_unmeasured_instead_of_failing(monkeypatch):
    monkeypatch.setattr(_route_flow, "_linear", lambda *arguments: None)
    monkeypatch.setattr(_route_flow, "ACCEPT_RESIDUAL", -1.0)  # the dense inverse of the small chain is no longer accepted either
    policy = {"A": act("a", ("A", 1), ("goal", 1))}

    flow = build_flow("A", policy, is_goal)

    assert not flow.measured and not flow.entered
    (step,) = flow.steps
    assert step.uses is None and step.reached == 1.0


def line(length: int) -> dict[int, Action]:
    """A line of states sharing one action and cost: each goes on with 1/2, else to the goal (only the last differs)."""
    policy = {i: act("same", (i + 1, 1), ("goal", 1)) for i in range(length - 1)}
    policy[length - 1] = act("same", ("goal", 1))
    return policy


def test_a_line_of_look_alike_states_with_one_action_is_one_step_whatever_its_length():
    flow = build_flow(0, line(300), is_goal)

    (step,) = flow.steps  # no refinement, no per-state fall-back: the label is the step
    assert len(step.states) == 300 and flow.measured
    assert step.uses == pytest.approx(2.0, rel=1e-6)  # state i is visited with chance 2^-i: the sum is 2
