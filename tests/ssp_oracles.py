"""Independent oracles for the solver tests (not collected as tests).

* `random_ssp`: seeded random small SSPs as plain data.
* `brute_force`: every deterministic stationary policy, each evaluated in exact `Fraction`
  arithmetic; the optimum is the minimum over policies.
* `evaluate_exactly`: the exact value of one given policy.
* `lp_values`: the Bellman linear programme solved by HiGHS.

A spec is `(size, table)`: states `0..size-1` are not goals, the one goal is `size`, and
`table[s]` is a list of `(label, cost, outcomes)` with `cost` a `Fraction` and `outcomes` a list of
`(state, weight)`.
"""

import itertools
import random
from fractions import Fraction

import numpy as np

import highspy
from crafting_system.solver import Action, TabularModel


def random_ssp(
    seed, *, min_states=3, max_states=6, max_actions=3, ensure_proper=False, weight_choices=None
):
    """A seeded random SSP. With `ensure_proper` every state has a proper policy.

    Weights are 1..10, or drawn from `weight_choices` when given (to stress rounding).
    """
    rng = random.Random(seed)
    draw = (lambda r: r.randint(1, 10)) if weight_choices is None else (lambda r: r.choice(weight_choices))
    size = rng.randint(min_states, max_states)
    table = {}
    for state in range(size):
        roll = rng.random()
        if not ensure_proper and roll < 0.08:
            table[state] = []  # a dead end: no action at all
            continue
        if not ensure_proper and roll < 0.18:
            # only an improper action: it never leaves the non-goal states
            table[state] = [(f"{state}.0", Fraction(rng.randint(1, 20), 4), _trap(rng, size, state))]
            continue
        actions = []
        for index in range(rng.randint(1, max_actions)):
            outcomes = [
                (rng.randint(0, size), draw(rng)) for _ in range(rng.randint(1, 4))
            ]
            if ensure_proper and index == 0:
                outcomes.append((state + 1, draw(rng)))  # a path towards the goal
            actions.append((f"{state}.{index}", Fraction(rng.randint(1, 20), 4), outcomes))
        table[state] = actions
    return size, table


def _trap(rng, size, state):
    return [(rng.choice([state, rng.randrange(size)]), rng.randint(1, 10)) for _ in range(2)]


def sparse_ssp(seed, states):
    """A larger sparse SSP with a proper policy everywhere (a chain towards the goal plus noise)."""
    rng = random.Random(seed)
    table = {}
    for state in range(states):
        actions = []
        for index in range(rng.randint(1, 3)):
            outcomes = [(rng.randint(0, states), rng.randint(1, 10)) for _ in range(rng.randint(1, 3))]
            if index == 0:
                outcomes.append((min(state + rng.randint(1, 3), states), rng.randint(1, 10)))
            actions.append((f"{state}.{index}", Fraction(rng.randint(1, 20), 4), outcomes))
        table[state] = actions
    return states, table


def to_model(spec):
    size, table = spec
    return TabularModel(
        [size],
        {
            state: [
                Action(label, float(cost), tuple((s, w) for s, w in outcomes))
                for label, cost, outcomes in actions
            ]
            for state, actions in table.items()
        },
    )


def _solve_fractions(matrix, rhs):
    """Gaussian elimination in exact arithmetic."""
    size = len(rhs)
    rows = [list(row) + [value] for row, value in zip(matrix, rhs)]
    for column in range(size):
        pivot = next(r for r in range(column, size) if rows[r][column] != 0)
        rows[column], rows[pivot] = rows[pivot], rows[column]
        top = rows[column]
        for r in range(size):
            if r != column and rows[r][column] != 0:
                factor = rows[r][column] / top[column]
                rows[r] = [a - factor * b for a, b in zip(rows[r], top)]
    return [rows[r][size] / rows[r][r] for r in range(size)]


def evaluate_exactly(spec, choice):
    """Exact value of the policy `choice` (state -> action index, or None for no action).

    A state's value is None (infinite) unless every state reachable from it under the policy can
    reach the goal.
    """
    size, table = spec
    edges = {}
    for state in range(size):
        pick = choice.get(state)
        edges[state] = [] if pick is None else [s for s, w in table[state][pick][2] if w > 0]
    # states that can reach the goal
    reaches = {size}
    grew = True
    while grew:
        grew = False
        for state in range(size):
            if state not in reaches and any(s in reaches for s in edges[state]):
                reaches.add(state)
                grew = True
    # a state is finite when nothing reachable from it is stuck
    stuck = {s for s in range(size) if s not in reaches}
    grew = True
    while grew:
        grew = False
        for state in range(size):
            if state not in stuck and any(s in stuck for s in edges[state]):
                stuck.add(state)
                grew = True
    finite = [s for s in range(size) if s not in stuck]
    position = {s: i for i, s in enumerate(finite)}
    matrix = [[Fraction(int(i == j)) for j in range(len(finite))] for i in range(len(finite))]
    rhs = []
    for state in finite:
        _, cost, outcomes = table[state][choice[state]]
        total = sum(w for _, w in outcomes)
        for s, w in outcomes:
            if s != size:
                matrix[position[state]][position[s]] -= Fraction(w, total)
        rhs.append(cost)
    solved = _solve_fractions(matrix, rhs) if finite else []
    return {s: (solved[position[s]] if s in position else None) for s in range(size)}


def brute_force(spec):
    """Optimal exact value per non-goal state (None = infinite) by trying every policy."""
    size, table = spec
    options = [list(range(len(table[s]))) or [None] for s in range(size)]
    best = dict.fromkeys(range(size))
    for combo in itertools.product(*options):
        values = evaluate_exactly(spec, dict(enumerate(combo)))
        for state, value in values.items():
            if value is not None and (best[state] is None or value < best[state]):
                best[state] = value
    return best


def lp_values(spec):
    """Optimal values from the Bellman LP: maximise the sum of V with V <= c + P V per action."""
    size, table = spec
    start, index, value, upper = [0], [], [], []
    for state in range(size):
        for _, cost, outcomes in table[state]:
            total = sum(w for _, w in outcomes)
            row = {state: 1.0}
            for s, w in outcomes:
                if s != size:
                    row[s] = row.get(s, 0.0) - w / total
            for column, coefficient in row.items():
                index.append(column)
                value.append(coefficient)
            start.append(len(index))
            upper.append(float(cost))
    lp = highspy.HighsLp()
    lp.num_col_ = size
    lp.num_row_ = len(upper)
    lp.col_cost_ = -np.ones(size)
    lp.col_lower_ = np.zeros(size)
    lp.col_upper_ = np.full(size, highspy.kHighsInf)
    lp.row_lower_ = np.full(len(upper), -highspy.kHighsInf)
    lp.row_upper_ = np.array(upper)
    lp.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
    lp.a_matrix_.start_ = np.array(start, dtype=np.int32)
    lp.a_matrix_.index_ = np.array(index, dtype=np.int32)
    lp.a_matrix_.value_ = np.array(value)
    highs = highspy.Highs()
    highs.setOptionValue("output_flag", False)
    highs.setOptionValue("primal_feasibility_tolerance", 1e-10)
    highs.setOptionValue("dual_feasibility_tolerance", 1e-10)
    highs.passModel(lp)
    highs.run()
    assert highs.getModelStatus() == highspy.HighsModelStatus.kOptimal
    return list(highs.getSolution().col_value)


FUZZ_COSTS = [0.001, 0.01, 0.1, 0.3, 1.0, 2.5, 7.0, 30.0, 100.0, 333.3, 1000.0]


def cost_spread_ssp(seed):
    """A seeded chain of 2-4 small cyclic components with costs from 0.001 to 1000.

    Each state has a forward action that leaves its component only at the last state, plus a
    few random back or self actions; weights come from {1, 2, 5, 1000}. Values reach about 1e4
    while the cheapest action costs 0.001.
    """
    rng = random.Random(seed)
    components, size = [], 0
    count = rng.randint(2, 4)
    for _ in range(count):
        width = rng.randint(2, 8) if count <= 2 else rng.randint(2, 5)
        components.append(list(range(size, size + width)))
        size += width
    goal = size

    def weight():
        return rng.choice([1, 2, 5, 10**3])

    table = {}
    for index, component in enumerate(components):
        later = [s for other in components[index + 1 :] for s in other] + [goal]
        for position, state in enumerate(component):
            outs = []
            if position + 1 < len(component):
                outs.append((component[position + 1], weight()))
            else:
                outs.extend((rng.choice(later), weight()) for _ in range(rng.randint(1, 3)))
            outs.extend((rng.choice(component), weight()) for _ in range(rng.randint(0, 3)))
            actions = [(f"{state}.f", outs)]
            for extra in range(rng.randint(0, 3)):
                outs = [(rng.choice(component), weight()) for _ in range(rng.randint(1, 3))]
                if rng.random() < 0.5:
                    outs.extend((rng.choice(later), weight()) for _ in range(rng.randint(1, 3)))
                if all(t == state for t, _ in outs) and rng.random() < 0.7:
                    outs.append((rng.choice(later), weight()))
                actions.append((f"{state}.{extra}", outs))
            table[state] = [
                (label, Fraction(rng.choice(FUZZ_COSTS)), outs) for label, outs in actions
            ]
    return size, table


def exact_optimal_values(spec):
    """Optimal values by policy iteration in exact fractions (every state needs a proper policy).

    Starts from the first action everywhere, which `cost_spread_ssp` makes proper.
    """
    size, table = spec
    policy = dict.fromkeys(range(size), 0)

    def q(state, index, values):
        _, cost, outcomes = table[state][index]
        total = sum(w for _, w in outcomes)
        return cost + sum(Fraction(w, total) * values.get(s, 0) for s, w in outcomes)

    for _ in range(500):
        matrix = [[Fraction(int(i == j)) for j in range(size)] for i in range(size)]
        rhs = []
        for state in range(size):
            _, cost, outcomes = table[state][policy[state]]
            total = sum(w for _, w in outcomes)
            for s, w in outcomes:
                if s != size:
                    matrix[state][s] -= Fraction(w, total)
            rhs.append(cost)
        values = dict(enumerate(_solve_fractions(matrix, rhs)))
        changed = False
        for state in range(size):
            current = q(state, policy[state], values)
            for index in range(len(table[state])):
                candidate = q(state, index, values)
                if candidate < current:
                    policy[state], current, changed = index, candidate, True
        if not changed:
            return values
    raise RuntimeError("exact policy iteration did not settle")
