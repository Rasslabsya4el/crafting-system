"""Exact oracles for actions with inputs (not collected as tests), in the style of `ssp_oracles.py`.

A spec is `(goals, table)`: `goals` is a set of states (value 0, never expanded) and `table[s]` is a
list of `(label, cost, outcomes, inputs)` with `cost` a `Fraction`, `outcomes` a list of
`(state, weight)` (an outcome may be the state itself) and `inputs` a list of states (a repeated
state means that many copies; a goal as an input costs nothing). A state with an empty list has no
action: a dead end. A state that only appears as an outcome or an input and is not in the table is
a dead end too.

The value of a policy follows ADR-0022 as it was first written, with no self-loop elimination:

    J(s) = c + sum_j (w_j / W) J(j) + sum_y J(y)          (y over the input copies)

so every attempt, the retry after a self-loop included, pays for fresh inputs. This is the
Neumann series `sum_i M^i c` on the closure of the states reachable from `s` under the policy
(outcomes and inputs alike). It is finite exactly when `(I - M) y = c` has a strictly positive
solution on that closure (then the spectral radius of `M` is below one); otherwise the value is
infinite, even when the goal is reached with probability one (a state that needs two copies of
what it makes). The optimum is the minimum over every deterministic stationary policy.

The exact functions are `Fraction` arithmetic with no solver code; the only import from the
solver is the pair of classes `to_model` builds a model from. `lp_values_inputs` is the one float
oracle: the Bellman linear programme of these problems (ticket #179) solved by HiGHS.

* `random_input_spec`: seeded random small specs.
* `evaluate_policy_exactly`: the exact value of one given policy at one state.
* `policy_space`, `brute_force_inputs`: every policy, and the optimum per state.
* `to_model`: the solver model of a spec.
* `lp_values_inputs`: the Bellman LP (maximal subsolution) by HiGHS, for all-finite instances.
"""

import itertools
import random
from fractions import Fraction

import numpy as np

import highspy
from crafting_system.solver import Action, TabularModel


def random_input_spec(seed):
    """A seeded random spec: 3-6 non-goal states `0..size-1`, the one goal is `size`.

    Each state is a dead end (7%) or has 1-3 actions of 1-4 weighted outcomes (any state, the
    goal and the state itself included) with 0-2 inputs, drawn from any state too, so goal inputs,
    self inputs and duplicate inputs occur. A state may also have a `buy` action straight to the
    goal. With 30% a "trap" is planted: `a` needs two copies of `b` and `b` needs an `a`, both
    reach the goal, yet the cost is infinite. With 10% a state gets a `self2` action that needs
    two copies of itself.
    """
    rng = random.Random(seed)
    size = rng.randint(3, 6)
    p_input = rng.choice([0.15, 0.35, 0.6])
    p_buy = rng.choice([0.0, 0.3, 0.6])
    table = {}
    for s in range(size):
        if rng.random() < 0.07:
            table[s] = []
            continue
        actions = []
        for index in range(rng.randint(1, 3)):
            outcomes = [(rng.randint(0, size), rng.randint(1, 10)) for _ in range(rng.randint(1, 4))]
            inputs = []
            while len(inputs) < 2 and rng.random() < p_input:
                inputs.append(rng.randint(0, size))
            actions.append((f"{s}.{index}", Fraction(rng.randint(1, 20), 4), outcomes, inputs))
        if rng.random() < p_buy:
            actions.append((f"{s}.buy", Fraction(rng.randint(20, 80), 4), [(size, 1)], []))
        table[s] = actions
    if rng.random() < 0.3:
        a, b = rng.sample(range(size), 2)
        table[a] = [(f"{a}.trap", Fraction(1), [(size, 1), (a, rng.randint(0, 3))], [b, b])]
        table[b] = [(f"{b}.trap", Fraction(1), [(size, rng.randint(1, 3))], [a])]
    if rng.random() < 0.1:
        s = rng.randrange(size)
        table[s] = table[s] + [(f"{s}.self2", Fraction(1), [(size, 1)], [s, s])]
    return {size}, table


def to_model(spec):
    """The solver model of a spec (costs become floats)."""
    goals, table = spec
    return TabularModel(
        goals,
        {
            state: [
                Action(label, float(cost), tuple((s, w) for s, w in outcomes), tuple(inputs))
                for label, cost, outcomes, inputs in actions
            ]
            for state, actions in table.items()
        },
    )


def _solve_fractions(matrix, rhs):
    """Gaussian elimination in exact arithmetic; None when the matrix is singular."""
    size = len(rhs)
    rows = [list(row) + [value] for row, value in zip(matrix, rhs)]
    for column in range(size):
        pivot = next((r for r in range(column, size) if rows[r][column] != 0), None)
        if pivot is None:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        top = rows[column]
        for r in range(size):
            if r != column and rows[r][column] != 0:
                factor = rows[r][column] / top[column]
                rows[r] = [a - factor * b for a, b in zip(rows[r], top)]
    return [rows[r][size] / rows[r][r] for r in range(size)]


def _edges(action):
    """The `(state, coefficient)` pairs of one action: outcome probabilities, then one per input copy."""
    _, _, outcomes, inputs = action
    total = sum(w for _, w in outcomes)
    edges = [(s, Fraction(w, total)) for s, w in outcomes if w > 0]
    edges += [(y, Fraction(1)) for y in inputs]
    return edges


def _closure(spec, choice, start):
    """The non-goal states reachable from `start` under `choice`; None if one has no action."""
    goals, table = spec
    seen, stack = {start}, [start]
    while stack:
        s = stack.pop()
        pick = choice.get(s)
        if pick is None:
            return None
        for t, _ in _edges(table[s][pick]):
            if t not in goals and t not in seen:
                seen.add(t)
                stack.append(t)
    return seen


def evaluate_policy_exactly(spec, choice, start, memo=None):
    """The exact value (a `Fraction`) of `choice` (state -> action index) at `start`, None for infinity.

    `memo`, a dict, caches the linear systems across calls on the same spec.
    """
    goals, table = spec
    if start in goals:
        return Fraction(0)
    states = _closure(spec, choice, start)
    if states is None:
        return None
    order = sorted(states, key=repr)
    key = tuple((s, choice[s]) for s in order)
    if memo is not None and key in memo:
        solved = memo[key]
    else:
        position = {s: i for i, s in enumerate(order)}
        matrix = [[Fraction(int(i == j)) for j in range(len(order))] for i in range(len(order))]
        rhs = []
        for s in order:
            action = table[s][choice[s]]
            rhs.append(action[1])
            for t, coefficient in _edges(action):
                if t not in goals:
                    matrix[position[s]][position[t]] -= coefficient
        values = _solve_fractions(matrix, rhs)
        solved = None
        if values is not None and all(v > 0 for v in values):
            solved = dict(zip(order, values))
        if memo is not None:
            memo[key] = solved
    return None if solved is None else solved[start]


def policy_space(spec):
    """Every deterministic stationary policy as a dict state -> action index (None: no action)."""
    goals, table = spec
    states = sorted((s for s in table if s not in goals), key=repr)
    options = [list(range(len(table[s]))) or [None] for s in states]
    for combo in itertools.product(*options):
        yield dict(zip(states, combo))


def brute_force_inputs(spec):
    """The optimal exact value per non-goal state of the table (None = infinite) over every policy."""
    goals, table = spec
    states = [s for s in table if s not in goals]
    best = dict.fromkeys(states)
    memo = {}
    for choice in policy_space(spec):
        for s in states:
            value = evaluate_policy_exactly(spec, choice, s, memo)
            if value is not None and (best[s] is None or value < best[s]):
                best[s] = value
    return best


def lp_values_inputs(spec):
    """Optimal values from the Bellman LP of ADR-0022, for instances where every value is finite.

    The maximal subsolution: maximise the sum of `x_s` subject to, for every action `a` of every
    non-goal state `s` in the table, `x_s <= c_a + sum_t coefficient_t x_t` (the coefficients of
    `_edges`: outcome probabilities and one 1 per input copy, goals fixed at 0, no self-loop
    elimination, so the row of `s` carries `1 - p_self` on `x_s`), and `x >= 0`. When every optimal
    value V* is finite this is V* exactly. Returns `{state: float}`, or None when HiGHS does not
    report optimal: with an infinite V* the sum is unbounded (a state with no action, or one
    outside the table, is unbounded too).

    A non-None answer on an instance that has an infinite state is NOT V*; this function is only
    meaningful for all-finite instances, which the caller must establish otherwise (for example
    with `brute_force_inputs`).
    """
    goals, table = spec
    states = {s for s in table if s not in goals}
    for actions in table.values():
        for action in actions:
            states.update(t for t, _ in _edges(action) if t not in goals)
    order = sorted(states, key=repr)
    column = {s: i for i, s in enumerate(order)}
    start, index, value, upper = [0], [], [], []
    for state in order:
        for action in table.get(state, []):
            row = {column[state]: 1.0}
            for t, coefficient in _edges(action):
                if t not in goals:
                    row[column[t]] = row.get(column[t], 0.0) - float(coefficient)
            for position, coefficient in row.items():
                index.append(position)
                value.append(coefficient)
            start.append(len(index))
            upper.append(float(action[1]))
    size = len(order)
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
    if highs.getModelStatus() != highspy.HighsModelStatus.kOptimal:
        return None
    return dict(zip(order, highs.getSolution().col_value))
