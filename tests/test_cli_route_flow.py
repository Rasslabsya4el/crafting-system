"""The steps of a policy: the coarsest grouping of its states by action and by exact outcome chances."""

import math
import random
from collections import Counter
from fractions import Fraction

import pytest

from crafting_system.cli._reach import policy_states, reach_probabilities
from crafting_system.cli import _route_flow
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


def test_a_chain_of_two_states_with_the_same_action_but_different_successors_is_two_steps():
    policy = {"A": act("exalt", ("B", 1)), "B": act("exalt", ("goal", 1))}

    flow = build_flow("A", policy, is_goal)

    assert [step.states for step in flow.steps] == [("A",), ("B",)]
    assert [(edge.kind, edge.to) for edge in flow.steps[0].edges] == [("forward", 2)]
    assert [(edge.kind, edge.to) for edge in flow.steps[1].edges] == [("goal", None)]
    assert [step.uses for step in flow.steps] == [pytest.approx(1.0), pytest.approx(1.0)]


def test_look_alike_states_with_the_same_label_but_different_chances_are_two_steps():
    policy = {
        "S": act("go", ("A", 1), ("B", 1)),
        "A": act("x", ("goal", 1), ("dead", 1)),
        "B": act("x", ("goal", 1), ("dead", 3)),
    }

    flow = build_flow("S", policy, is_goal)

    assert flow.step_of["A"] != flow.step_of["B"]
    assert step_with(flow, "A").edges[0].chance == pytest.approx(0.5)
    assert step_with(flow, "B").edges[0].chance == pytest.approx(0.25)


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
    assert [edge.kind for edge in shared.edges] == ["goal", "miss"]  # the dead end is a miss, not progress
    assert shared.edges[1].states == ("dead",)
    assert shared.uses == pytest.approx(1.0)  # one use, shared by the two states
    assert shared.reached == pytest.approx(1.0)
    assert len(flow.steps) == 3  # the start, the shared step, the dead end


def test_the_same_action_at_two_places_of_a_route_with_different_successors_is_two_steps():
    policy = {
        "S": act("essence", ("X", 1), ("Y", 1)),
        "X": act("annul", ("goal", 1), ("P", 1)),
        "Y": act("annul", ("goal", 1), ("Q", 1)),
        "P": act("fix", ("goal", 1)),
        "Q": act("other", ("goal", 1)),
    }

    flow = build_flow("S", policy, is_goal)

    assert flow.step_of["X"] != flow.step_of["Y"]
    assert step_with(flow, "X").action.label == step_with(flow, "Y").action.label == "annul"


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
    assert [(edge.kind, edge.to) for edge in flow.steps[0].edges] == [("goal", None), ("miss", 2)]


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


def test_edges_are_miss_again_and_forward_with_the_goal_first():
    policy = {
        "A": act("a", ("B", 1)),
        "B": act("b", ("A", 1), ("B", 1), ("C", 1), ("goal", 1)),
        "C": act("c", ("goal", 1)),
    }

    flow = build_flow("A", policy, is_goal)

    b = step_with(flow, "B")
    assert [(edge.kind, edge.to) for edge in b.edges] == [("goal", None), ("miss", 1), ("again", 2), ("forward", 3)]
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


def test_the_states_of_a_step_have_the_same_chance_into_every_target_step():
    rng = random.Random(7878)
    for _ in range(200):
        start, policy = random_policy(rng)

        flow = build_flow(start, policy, is_goal)

        for step in flow.steps:
            if step.action is None:
                assert step.edges == ()
                continue
            wanted = {edge.to: edge.chance for edge in step.edges}
            assert math.fsum(wanted.values()) == pytest.approx(1.0)
            for state in step.states:
                outcomes = policy[state].outcomes
                total = sum(weight for _, weight in outcomes)
                chances: dict[int | None, Fraction] = {}
                for successor, weight in outcomes:
                    target = None if is_goal(successor) else flow.step_of[successor]
                    chances[target] = chances.get(target, Fraction(0)) + Fraction(weight, total)
                assert {t: float(c) for t, c in chances.items()} == pytest.approx(wanted)


def test_the_steps_are_the_coarsest_grouping():
    rng = random.Random(787)
    for _ in range(100):
        start, policy = random_policy(rng)

        flow = build_flow(start, policy, is_goal)

        # Two different steps with an action never have the same label and the same chances into the same steps.
        seen = {}
        for step in flow.steps:
            if step.action is None:
                continue
            key = (step.action.label, tuple((edge.to, round(edge.chance, 12)) for edge in step.edges))
            assert key not in seen, "two steps that could have been one"
            seen[key] = step.number


def test_the_flow_is_deterministic():
    rng = random.Random(1)
    start, policy = random_policy(rng)

    assert build_flow(start, policy, is_goal) == build_flow(start, policy, is_goal)


def test_uses_times_cost_is_the_mean_cost_on_random_policies_that_always_finish():
    rng = random.Random(780)
    checked = 0
    for _ in range(300):
        start, policy = random_policy(rng)
        policy = {s: Action(a.label, 1.0 + int(s[1:]) % 3, a.outcomes) for s, a in policy.items()}
        risk = evaluate(policy, start, is_goal)
        if risk.success_probability.value != 1.0:
            continue
        flow = build_flow(start, policy, is_goal)

        total = sum(step.uses * step.action.cost for step in flow.steps)

        assert total == pytest.approx(risk.mean.value, rel=1e-6)
        checked += 1
    assert checked >= 20


def test_a_miss_into_a_later_numbered_step_is_a_miss_not_a_forward_edge():
    # S is step 1, W (worse) is met before G (good) breadth-first, so W is step 2 and G step 3. W is dear to finish.
    policy = {
        "S": act("s", ("W", 3), ("G", 1)),
        "W": act("w", ("goal", 1), cost=20.0),
        "G": act("g", ("goal", 1)),
    }

    flow = build_flow("S", policy, is_goal)

    start = flow.steps[0]
    assert flow.step_of["W"] < flow.step_of["G"]
    assert [(edge.kind, edge.to) for edge in start.edges] == [("miss", 2), ("forward", 3)]
    assert edge_to(start, flow.step_of["W"]).chance == pytest.approx(0.75)


def test_an_edge_into_an_earlier_numbered_step_is_forward_when_that_step_is_nearer_the_goal():
    policy = {
        "S": act("s", ("A", 1), ("B", 1)),
        "A": act("a", ("goal", 1)),
        "B": act("b", ("A", 1)),  # A is numbered before B
    }

    flow = build_flow("S", policy, is_goal)

    assert flow.step_of["A"] < flow.step_of["B"]
    assert [(edge.kind, edge.to) for edge in step_with(flow, "B").edges] == [("forward", flow.step_of["A"])]
    # S: the item is expected to be 1.5 c from the goal after the use; A is 1 c away, B 2 c
    assert edge_to(flow.steps[0], flow.step_of["A"]).kind == "forward"
    assert edge_to(flow.steps[0], flow.step_of["B"]).kind == "miss"


def test_every_edge_of_a_restart_is_a_miss():
    policy = {
        "S": act("go", ("X", 1), ("goal", 1), cost=1.0),
        "X": act("restart", ("S", 1), cost=1.0),
    }

    flow = build_flow("S", policy, is_goal, is_restart=lambda action: action.label == "restart")
    plain = build_flow("S", policy, is_goal)

    assert [edge.kind for edge in step_with(flow, "X").edges] == ["miss"]
    assert [edge.kind for edge in step_with(plain, "X").edges] == ["forward"]  # cheaper to finish from the start


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


def test_above_the_cap_the_chain_is_not_solved_and_the_edges_are_told_by_the_distance_to_the_goal(monkeypatch):
    monkeypatch.setattr(_route_flow, "MAX_STEPS", 50)
    policy = chain(80)

    flow = build_flow(0, policy, is_goal)

    assert not flow.measured and len(flow.steps) == 80
    assert flow.steps[0].reached == 1.0
    assert all(step.uses is None and step.reached is None for step in flow.steps[1:])
    assert [edge.kind for edge in step_with(flow, 3).edges] == ["miss", "forward"]
    assert [edge.kind for edge in step_with(flow, 79).edges] == ["goal", "miss"]
    assert flow.steps[0].edges[0].kind == "again" and flow.steps[0].edges[1].kind == "forward"
