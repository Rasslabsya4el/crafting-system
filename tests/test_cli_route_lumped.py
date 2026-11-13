"""The route page on the plan's lumped chain (ticket #689, class C7 of #812).

The chain keeps each kernel once and every state names its kernel, so what a state costs in memory does not depend on the edges its
kernel has. Every quantity of the page is computed on lumped chains, never on a copy of the edges per state: the chances of entering the
steps on the chain lumped with the steps' labels (strong lumpability keeps hitting chances of unions of blocks), the visits of each state
from the visits of its kernel's class, and the chances of the edges from each (kernel, step, loss class) once. Checked against hand-worked
numbers and against exact `Fraction` elimination on random chains whose states share kernels.
"""

import math
import random
import tracemalloc
from fractions import Fraction

import numpy as np
import pytest

from crafting_system.cli import _route_flow
from crafting_system.cli._reach import policy_states
from crafting_system.cli._route_flow import Chain, Kernels, LossReader, flow_of, flow_limits
from crafting_system.risk import evaluate
from crafting_system.solver import Action, Outcome

GOAL = "goal"


def is_goal(state) -> bool:
    return state == GOAL


def kernels(rows: list[list[tuple[int, int]]]) -> Kernels:
    """A kernel table from rows of `(successor, integer weight)`."""
    ptr = np.concatenate(([0], np.cumsum([len(row) for row in rows]))).astype(np.int64)
    succ = np.array([s for row in rows for s, _ in row], dtype=np.int64)
    wt = np.array([w for row in rows for _, w in row], dtype=np.int64)
    prob = np.array([Fraction(w, sum(x for _, x in row)) for row in rows for _, w in row], dtype=float)
    return Kernels(ptr, succ, wt, prob)


# --- a hand-worked chain -----------------------------------------------------------------------------------------------------
#
# S (action a, 1 c) -> A 1/4, B 1/2, D 1/4.  A and B (action b, 2 c) share one kernel: the goal 1/4, back to S 3/4.  D (action d, 1 c): S 1/2, goal 1/2.
# A holds a wanted mod ("x") that S lacks, so A -> S loses it; B and D hold none.
#
# Visits: v_S = 1 + 3/4 (v_A + v_B) + 1/2 v_D with v_A = v_S / 4, v_B = v_S / 2, v_D = v_S / 4, so v_S = 1 + 11/16 v_S = 16/5; v_A = 4/5, v_B = 8/5, v_D = 4/5.
# Mean cost 16/5 + 2 (12/5) + 4/5 = 44/5. Entering b = {A, B}: h_S = 3/4 + 1/4 h_D, h_D = 1/2 h_S, so 6/7; entering d: h_S = 1/4 + 3/4 (3/4 h_S), so 4/7.
# The edges of b, mixed by the visits of A (4/5) and B (8/5): the goal 1/4; back to S losing x, from A: 3/4 x 1/3 = 1/4; back to S from B: 3/4 x 2/3 = 1/2.

NAMES = ["S", "A", "B", "D"]
LABELS = ("a", "b", "d")
COSTS = {"a": 1.0, "b": 2.0, "d": 1.0}
MARK = np.array([0, 1, 0, 0, 0])  # S, A, B, D, the goal: A holds x


def hand_chain() -> Chain:
    table = kernels([[(1, 1), (2, 2), (3, 1)], [(4, 1), (0, 3)], [(0, 1), (4, 1)]])
    kernel = np.array([0, 1, 1, 2])
    key = np.array([0, 1, 1, 2])

    def action_of(i: int) -> Action:
        k = int(kernel[i])
        lo, hi = int(table.k_ptr[k]), int(table.k_ptr[k + 1])
        everything = [*NAMES, GOAL]
        label = LABELS[int(key[i])]
        return Action(label, COSTS[label], tuple(Outcome(everything[int(s)], int(w)) for s, w in zip(table.k_succ[lo:hi], table.k_wt[lo:hi])))

    return Chain(NAMES, [GOAL], key, tuple(("action", label) for label in LABELS), np.array([1.0, 2.0, 2.0, 1.0]), kernel, table, action_of)


def lost_x(chain: Chain, src: np.ndarray, dst: np.ndarray):
    return ("x",), ((MARK[src] == 1) & (MARK[dst] == 0))[:, None]


MARKED = LossReader(lost_x, lambda chain: MARK[: chain.m])


def by_target(step) -> dict:
    return {(edge.to, edge.lost): edge.chance for edge in step.edges}


def test_the_steps_of_a_chain_whose_states_share_a_kernel_are_the_hand_worked_numbers():
    flow = flow_of(hand_chain(), loss=MARKED)

    a, b, d = flow.steps
    assert [step.action.label for step in flow.steps] == ["a", "b", "d"]
    assert flow.measured and flow.entered
    assert a.uses == pytest.approx(16 / 5, rel=1e-14) and b.uses == pytest.approx(12 / 5, rel=1e-14) and d.uses == pytest.approx(4 / 5, rel=1e-14)
    assert b.weights == pytest.approx((4 / 5, 8 / 5), rel=1e-14)
    assert sum(step.uses * step.cost for step in flow.steps) == pytest.approx(44 / 5, rel=1e-14)
    assert (a.reached, b.reached, d.reached) == (1.0, pytest.approx(6 / 7, rel=1e-14), pytest.approx(4 / 7, rel=1e-14))
    assert by_target(a) == {(2, ()): pytest.approx(3 / 4), (3, ()): pytest.approx(1 / 4)}
    assert by_target(b) == {(None, ()): pytest.approx(1 / 4), (1, ("x",)): pytest.approx(1 / 4), (1, ()): pytest.approx(1 / 2)}
    assert [edge.kind for edge in b.edges] == ["goal", "forward", "failure"]
    assert {edge.lost: edge.states for edge in b.edges if edge.to == 1} == {(): ("S",), ("x",): ("S",)}
    assert by_target(d) == {(None, ()): pytest.approx(1 / 2), (1, ()): pytest.approx(1 / 2)}


def test_the_page_lumping_puts_states_with_one_label_and_one_kernel_in_one_block():
    block = _route_flow._page_blocks(hand_chain())

    assert block[1] == block[2]  # A and B: the same step, the same kernel
    assert len({int(block[0]), int(block[1]), int(block[3])}) == 3


def test_a_loss_reader_without_classes_gives_the_same_steps_as_one_whose_loss_depends_on_a_class_only():
    with_classes = flow_of(hand_chain(), loss=MARKED)
    per_state = flow_of(hand_chain(), loss=lost_x)  # a plain function: every state its own class

    assert with_classes == per_state


def test_the_limits_of_the_hand_worked_chain_say_nothing():
    assert flow_limits(hand_chain()) == ()


# --- random chains whose states share kernels, against exact elimination ---------------------------------------------------


def shared_kernel_policy(rng: random.Random):
    """A random policy whose states draw their outcomes from a few shared kernels, with random labels and costs (a label may mix kernels and costs)."""
    size = rng.randint(3, 12)
    names = [f"s{i}" for i in range(size)]
    pool = []
    for _ in range(rng.randint(1, 4)):
        targets = rng.sample([*names, GOAL], rng.randint(1, min(5, size + 1)))
        pool.append(tuple(Outcome(t, rng.choice([1, 1, 2, 3, 7])) for t in targets))
    policy = {}
    for name in names:
        if rng.random() < 0.15:
            continue  # a dead end
        policy[name] = Action(rng.choice("abc"), float(rng.choice([1, 2, 5])), rng.choice(pool))
    return names[0], policy


def exact_visits(start, policy) -> dict:
    """Expected visits of every reachable state from `start` by `Fraction` elimination, for a policy that always finishes."""
    states = [s for s in policy_states(start, policy, is_goal) if not is_goal(s)]
    index = {s: k for k, s in enumerate(states)}
    n = len(states)
    rows = [[Fraction(0)] * n + [Fraction(1 if k == 0 else 0)] for k in range(n)]
    for state in states:
        total = sum(o.weight for o in policy[state].outcomes)
        rows[index[state]][index[state]] += 1
        for o in policy[state].outcomes:
            if o.state in index:
                rows[index[o.state]][index[state]] -= Fraction(o.weight, total)
    for c in range(n):
        pivot = next(r for r in range(c, n) if rows[r][c] != 0)
        rows[c], rows[pivot] = rows[pivot], rows[c]
        rows[c] = [v / rows[c][c] for v in rows[c]]
        for r in range(n):
            if r != c and rows[r][c] != 0:
                rows[r] = [a - rows[r][c] * b for a, b in zip(rows[r], rows[c])]
    return {s: rows[index[s]][n] for s in states}


def exact_hit(policy, start, members) -> Fraction:
    """The chance of ever reaching `members` from `start`, by `Fraction` elimination over the states that can reach them."""
    if start in members:
        return Fraction(1)
    reaching: set = set()
    while True:
        more = {s for s, a in policy.items() if s not in members and s not in reaching and any(o.state in members or o.state in reaching for o in a.outcomes)}
        if not more:
            break
        reaching |= more
    if start not in reaching:
        return Fraction(0)
    states = sorted(reaching)
    index = {s: i for i, s in enumerate(states)}
    n = len(states)
    rows = [[Fraction(0)] * (n + 1) for _ in range(n)]
    for s in states:
        total = sum(o.weight for o in policy[s].outcomes)
        rows[index[s]][index[s]] += 1
        for o in policy[s].outcomes:
            if o.state in members:
                rows[index[s]][n] += Fraction(o.weight, total)
            elif o.state in index:
                rows[index[s]][index[o.state]] -= Fraction(o.weight, total)
    for c in range(n):
        pivot = next(r for r in range(c, n) if rows[r][c] != 0)
        rows[c], rows[pivot] = rows[pivot], rows[c]
        rows[c] = [v / rows[c][c] for v in rows[c]]
        for r in range(n):
            if r != c and rows[r][c] != 0:
                rows[r] = [a - rows[r][c] * b for a, b in zip(rows[r], rows[c])]
    return rows[index[start]][n]


def marks_of(policy, rng: random.Random) -> dict:
    """A random wanted mark per state (1: it holds the wanted mod); the goal holds it."""
    return {**{s: rng.choice([0, 1]) for s in policy}, GOAL: 1}


def marked_reader(marks: dict) -> LossReader:
    """The loss of a use: the state held the mark and its landing does not. It depends on a state through its mark only."""

    def everything(chain):
        return np.array([marks.get(s, 0) for s in (*chain.states, *chain.goals)])

    def lost(chain, src, dst):
        mark = everything(chain)
        return ("x",), ((mark[src] == 1) & (mark[dst] == 0))[:, None]

    return LossReader(lost, lambda chain: everything(chain)[: chain.m])


def shared_policies(seed: int, wanted: int, finishing: bool):
    rng = random.Random(seed)
    found = 0
    while found < wanted:
        start, policy = shared_kernel_policy(rng)
        if start not in policy:
            continue
        if finishing and evaluate(policy, start, is_goal).success_probability.value != 1.0:
            continue
        found += 1
        yield start, policy, marks_of(policy, rng)


def can_finish(policy) -> set:
    """The states with an action from which some run reaches the goal through states that have an action."""
    found = {s for s, a in policy.items() if any(is_goal(o.state) for o in a.outcomes)}
    while True:
        more = {s for s, a in policy.items() if s not in found and any(o.state in found for o in a.outcomes)}
        if not more:
            return found
        found |= more


def exact_live_visits(start, policy) -> dict:
    """The expected visits from `start` of the states that can finish (the others 0), by `Fraction` elimination over those states alone (an edge into a
    state that cannot finish leaves the system); all 0 when the start cannot finish."""
    live = can_finish(policy)
    reached = [s for s in policy_states(start, policy, is_goal) if not is_goal(s)]
    visits = {s: Fraction(0) for s in reached}
    if start not in live:
        return visits
    states = [s for s in reached if s in live]
    index = {s: k for k, s in enumerate(states)}
    n = len(states)
    rows = [[Fraction(0)] * n + [Fraction(1 if s == start else 0)] for s in states]
    for s in states:
        total = sum(o.weight for o in policy[s].outcomes)
        rows[index[s]][index[s]] += 1
        for o in policy[s].outcomes:
            if o.state in index:
                rows[index[o.state]][index[s]] -= Fraction(o.weight, total)
    for c in range(n):
        pivot = next(r for r in range(c, n) if rows[r][c] != 0)
        rows[c], rows[pivot] = rows[pivot], rows[c]
        rows[c] = [v / rows[c][c] for v in rows[c]]
        for r in range(n):
            if r != c and rows[r][c] != 0:
                rows[r] = [a - rows[r][c] * b for a, b in zip(rows[r], rows[c])]
    return visits | {s: rows[index[s]][n] for s in states}


def test_on_random_chains_whose_states_share_kernels_every_page_quantity_equals_the_exact_unlumped_one():
    """Done when of #689: visits (the weights), uses, cost, every edge's chance, kind, loss and landing states, on the lumped chains, to 1e-12 of
    exact elimination. Dead ends, loops that never end and starts that cannot finish included: only the states that can finish are weighted,
    and a step with none of them is the plain mean of its states."""
    checked = lumped = mixed = never = 0
    for start, policy, marks in shared_policies(689, 600, finishing=False):
        chain = _route_flow.chain_of_policy(start, policy, is_goal)
        flow = flow_of(chain, loss=marked_reader(marks))
        visits = exact_live_visits(start, policy)
        assert flow.measured and flow.entered
        lumped += len(set(_route_flow._page_blocks(chain).tolist())) < chain.m
        for step in flow.steps:
            raw = sum(visits[s] for s in step.states)
            weight = {s: visits[s] if raw > 0 else Fraction(1) for s in step.states}
            total = sum(weight.values())
            assert step.weights == pytest.approx(tuple(float(weight[s]) for s in step.states), rel=1e-12)
            if step.action is None:
                assert step.uses is None and step.edges == ()
                checked += 1
                continue
            assert step.uses == (math.inf if raw == 0 else pytest.approx(float(raw), rel=1e-12))
            never += raw == 0
            mixed += raw > 0 and any(visits[s] == 0 for s in step.states)
            assert step.cost == pytest.approx(float(sum(weight[s] * Fraction(policy[s].cost) for s in step.states) / total), rel=1e-12)
            wanted: dict = {}
            landing: dict = {}
            for s in step.states:
                weight_total = sum(o.weight for o in policy[s].outcomes)
                for o in policy[s].outcomes:
                    to = None if is_goal(o.state) else flow.step_of[o.state]
                    loses = ("x",) if to is not None and marks[s] == 1 and marks.get(o.state, 0) == 0 else ()
                    wanted[(to, loses)] = wanted.get((to, loses), Fraction(0)) + weight[s] * Fraction(o.weight, weight_total) / total
                    landing.setdefault((to, loses), set()).add(o.state)
            assert by_target(step) == pytest.approx({k: float(v) for k, v in wanted.items()}, rel=1e-12, abs=1e-15)
            for edge in step.edges:
                assert set(edge.states) == landing[(edge.to, edge.lost)] and len(edge.states) == len(set(edge.states))
                there = None if edge.to is None else flow.steps[edge.to - 1]
                expected = "goal" if there is None else "failure" if edge.lost or there.action is None else "again" if there is step else "forward"
                assert edge.kind == expected
            checked += 1
    assert checked > 1000 and lumped > 200 and mixed > 10 and never > 100, (checked, lumped, mixed, never)


def test_a_kernel_whose_weights_pass_62_bits_is_exact_and_lumps_with_its_small_twin():
    """`k_big`: A's weights are W and 2W with W = 2^62 + 5, B's 1 and 2: the same chances, one block, the numbers of the all-small chain."""
    big = 2**62 + 5

    def policy(w: int) -> dict:
        return {
            "S": Action("a", 1.0, (Outcome("A", 1), Outcome("B", 1))),
            "A": Action("b", 2.0, (Outcome(GOAL, w), Outcome("S", 2 * w))),
            "B": Action("b", 2.0, (Outcome(GOAL, 1), Outcome("S", 2))),
        }

    chain = _route_flow.chain_of_policy("S", policy(big), is_goal)
    assert list(chain.kernels.k_big) == [int(chain.kernel[1])]
    block = _route_flow._page_blocks(chain)
    assert block[1] == block[2] != block[0]
    got, small = flow_of(chain), flow_of(_route_flow.chain_of_policy("S", policy(1), is_goal))
    for a, b in zip(got.steps, small.steps):
        assert a.weights == pytest.approx(b.weights, rel=1e-15) and a.reached == b.reached
        assert [e.chance for e in a.edges] == pytest.approx([e.chance for e in b.edges], rel=1e-15)
    assert got.steps[1].uses == pytest.approx(3.0, rel=1e-14)  # v_S = 1 + 2/3 (v_A + v_B) and v_A + v_B = v_S: 3, so b is used 3 times



def test_on_random_chains_whose_states_share_kernels_the_chance_of_entering_every_step_is_the_exact_hitting_chance():
    """Gaps, loops that never end and a start that cannot finish included: the hitting chances on the chain lumped with the steps' labels."""
    checked = no_action = 0
    for start, policy, _ in shared_policies(6890, 400, finishing=False):
        chain = _route_flow.chain_of_policy(start, policy, is_goal)
        if not _route_flow._solved(chain).finishing[0]:
            continue  # nothing is a run's business when the start cannot finish
        flow = flow_of(chain)
        assert flow.measured and flow.entered
        for step in flow.steps:
            assert step.reached == pytest.approx(float(exact_hit(policy, start, set(step.states))), rel=1e-12, abs=1e-14), (start, step.states)
            checked += 1
            no_action += step.action is None
    assert checked > 400 and no_action > 20


@pytest.mark.parametrize("dense_limit", [1500, 0])
def test_the_lumped_page_and_the_iteration_agree_with_the_dense_solves(monkeypatch, dense_limit):
    """The solves on the lumped chains go to BiCGSTAB above `DENSE_LIMIT`: a speed choice, no cut."""
    monkeypatch.setattr(_route_flow, "DENSE_LIMIT", dense_limit)
    for start, policy, marks in shared_policies(68, 40, finishing=True):
        flow = flow_of(_route_flow.chain_of_policy(start, policy, is_goal), loss=marked_reader(marks))
        visits = exact_visits(start, policy)
        for step in flow.steps:
            assert step.weights == pytest.approx(tuple(float(visits[s]) for s in step.states), rel=1e-9)
            assert step.reached == pytest.approx(float(exact_hit(policy, start, set(step.states))), rel=1e-9, abs=1e-12)


def test_states_with_the_same_outcomes_share_one_kernel_in_the_chain_of_a_policy():
    shared = (Outcome("B", 1), Outcome(GOAL, 1))
    policy = {"S": Action("a", 1.0, (Outcome("A", 1), Outcome("B", 1))), "A": Action("b", 1.0, shared), "B": Action("c", 2.0, shared)}

    chain = _route_flow.chain_of_policy("S", policy, is_goal)

    assert chain.kernel[1] == chain.kernel[2] != chain.kernel[0]
    assert len(chain.kernels.k_succ) == 4  # two kernels of two edges each


# --- memory: a state costs the same whatever its kernel's edges ----------------------------------------------------------


def wide_chain(states: int, edges: int, seed: int) -> Chain:
    """`states` states under 5 labels, sharing 3 kernels of `edges` random successors each (one of them the goal, with 5%)."""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(3):
        succ = rng.choice(states, size=edges - 1, replace=False)
        rows.append([(states, int(edges * 0.05) + 1), *((int(s), int(w)) for s, w in zip(succ, rng.integers(1, 20, size=edges - 1)))])
    table = kernels(rows)
    labels = tuple(("action", name) for name in "abcde")
    return Chain(
        list(range(states)), [GOAL], rng.integers(0, 5, size=states).astype(np.int64), labels, np.ones(states),
        rng.integers(0, 3, size=states).astype(np.int64), table, lambda i: Action("a", 1.0, ((GOAL, 1),)),
    )  # fmt: skip


def four_marks(states: int) -> LossReader:
    """4 loss classes: state i holds the wanted mods `i % 4`; a use loses what the landing does not hold of them."""
    mark = np.concatenate((np.arange(states) % 4, [3]))

    def lost(chain, src, dst):
        return (0, 1), np.stack([(mark[src] & 1) > (mark[dst] & 1), (mark[src] & 2) > (mark[dst] & 2)], axis=1)

    return LossReader(lost, lambda chain: mark[: chain.m])


def peak_of(work) -> int:
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    tracemalloc.reset_peak()
    work()
    peak = tracemalloc.get_traced_memory()[1] - before
    tracemalloc.stop()
    return peak


def test_what_the_page_holds_per_state_does_not_depend_on_the_edges_of_its_kernel(monkeypatch):
    """#689: R04's chain copied its kernel's edges to each of its 18,696 states (48.7 million edges). A state now names its kernel, and the page
    reads the kernels a chunk at a time: 5 steps x 4 loss classes x 3 kernels are 60 groups of edges, never all at once."""
    from crafting_system.solver import _packed_lump as lump_module

    states = 4000
    small, large = wide_chain(states, 500, 1), wide_chain(states, 3000, 1)
    assert len(large.kernels.k_succ) == 3 * 3000  # the edges are held once per kernel, not once per state
    monkeypatch.setattr(_route_flow, "CHUNK_EDGES", 20_000)
    monkeypatch.setattr(lump_module, "CHUNK_EDGES", 20_000)

    def page(chain):
        return lambda: (flow_of(chain, loss=four_marks(states)), flow_limits(chain))

    peak_small, peak_large = peak_of(page(small)), peak_of(page(large))
    copied = states * 3000 * 16  # what one copy of the edges per state would take (a successor and a chance per edge)
    assert peak_large < copied / 20, f"{peak_large:,} bytes"
    assert peak_large - peak_small < 2_000 * (3000 - 500) * 3, "the peak grows with the kernels' edges, not with the states times the edges"
    flow = flow_of(large, loss=four_marks(states))
    assert flow.measured and flow.entered and len(flow.steps) == 5 and all(math.isfinite(step.uses) for step in flow.steps)
    assert any(edge.lost for step in flow.steps for edge in step.edges)


def test_the_edges_read_in_tiny_chunks_give_the_same_steps(monkeypatch):
    """`CHUNK_EDGES` bounds the temporary arrays and decides no number: a chunk smaller than one kernel gives the same flow."""
    whole = flow_of(wide_chain(300, 120, 2), loss=four_marks(300))
    monkeypatch.setattr(_route_flow, "CHUNK_EDGES", 7)
    chunked = flow_of(wide_chain(300, 120, 2), loss=four_marks(300))
    for a, b in zip(whole.steps, chunked.steps):
        assert b.weights == pytest.approx(a.weights, rel=1e-12) and b.uses == pytest.approx(a.uses, rel=1e-12)
        assert [(e.kind, e.to, e.lost, e.states) for e in b.edges] == [(e.kind, e.to, e.lost, e.states) for e in a.edges]
        assert [e.chance for e in b.edges] == pytest.approx([e.chance for e in a.edges], rel=1e-12)


def test_a_packed_chain_keeps_a_big_integer_kernel_with_its_exact_weights():
    """`packed_chain` renumbers the kernels the policy uses; a kernel past 62 bits keeps its exact weights under its new number."""
    from crafting_system.cli._packed import Walked
    from crafting_system.cli._route_chain import packed_chain
    from crafting_system.cli._route_flow import build_flow
    from crafting_system.solver import TabularModel, pack_model

    big = 2**62 + 5
    table = {
        "S": [Action("a", 1.0, (Outcome("A", 1), Outcome("B", 1)))],
        "A": [Action("b", 2.0, (Outcome(GOAL, big), Outcome("S", 2 * big)))],
        "B": [Action("b", 2.0, (Outcome(GOAL, 1), Outcome("S", 3)))],
    }
    packed = pack_model(TabularModel([GOAL], table), ["S"])
    graph = packed.graph
    has = np.diff(graph.act_ptr) > 0
    action = np.where(has, graph.act_ptr[:-1], -1)
    names = ["a", "b"]
    label_ids = np.array([names.index(packed.actions[a].label) if a >= 0 else 0 for a in action.tolist()])
    chain = packed_chain(Walked(graph, packed.states, packed.index, (), 0.0), action, label_ids, names, graph.act_cost[np.maximum(action, 0)])

    a = packed.states.index("A")
    (held,) = chain.kernels.k_big.items()
    assert held[0] == int(chain.kernel[chain.states.index("A")]) and sorted(held[1]) == [big, 2 * big] and a >= 0
    got = flow_of(chain)
    expected = build_flow("S", {s: actions[0] for s, actions in table.items()}, is_goal)
    for x, y in zip(got.steps, expected.steps):
        assert x.weights == pytest.approx(y.weights, rel=1e-14) and x.uses == pytest.approx(y.uses, rel=1e-14) and x.reached == pytest.approx(y.reached, rel=1e-14)
        assert [e.chance for e in x.edges] == pytest.approx([e.chance for e in y.edges], rel=1e-14)
