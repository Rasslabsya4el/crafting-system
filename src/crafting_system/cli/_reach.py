"""The chance that a policy ever reaches each state, from its start.

For the transient states T (not a goal, with an action) of the chain the policy induces, N =
(I - Q)^-1 where Q holds the transition chances among them. The chance of ever visiting a transient
state s from the start is N[start][s] / N[s][s]; an absorbing state (a goal, or a state with no
action) is reached with the chance of stepping into it from the visited states. Dense Gauss-Jordan
in plain Python, O(n^3): enough for the small policies of the slice, and skipped (None) above
`MAX_TRANSIENT` states.
"""

from collections.abc import Callable, Hashable, Mapping

from crafting_system.solver import Action

MAX_TRANSIENT = 400


def policy_states[S: Hashable](
    start: S, policy: Mapping[S, Action[S]], is_goal: Callable[[S], bool]
) -> list[S]:
    """The states the policy can reach from `start`, in breadth-first order (the start first)."""
    order = [start]
    seen = {start}
    index = 0
    while index < len(order):
        state = order[index]
        index += 1
        if is_goal(state) or state not in policy:
            continue
        for successor, weight in policy[state].outcomes:
            if weight > 0 and successor not in seen:
                seen.add(successor)
                order.append(successor)
    return order


def reach_probabilities[S: Hashable](
    start: S, policy: Mapping[S, Action[S]], is_goal: Callable[[S], bool]
) -> dict[S, float] | None:
    """State -> the chance the policy ever visits it, or None when there are too many transient states."""
    states = policy_states(start, policy, is_goal)
    transient = [s for s in states if not is_goal(s) and s in policy]
    if len(transient) > MAX_TRANSIENT:
        return None
    position = {s: i for i, s in enumerate(transient)}
    size = len(transient)

    # (I - Q), then inverted in place next to an identity matrix.
    matrix = [[0.0] * size + [1.0 if i == j else 0.0 for j in range(size)] for i in range(size)]
    for state in transient:
        i = position[state]
        matrix[i][i] += 1.0
        total = sum(weight for _, weight in policy[state].outcomes)
        for successor, weight in policy[state].outcomes:
            j = position.get(successor)
            if j is not None and weight > 0:
                matrix[i][j] -= weight / total
    inverse = _invert(matrix, size)

    start_row = inverse[position[start]] if start in position else None
    reach: dict[S, float] = {start: 1.0}
    if start_row is None:  # the start is a goal or has no action: nothing else is reached
        return reach
    for state in transient:
        i = position[state]
        reach[state] = min(1.0, max(0.0, start_row[i] / inverse[i][i]))
    for state in states:
        if state in position or state == start:
            continue
        stepped = 0.0
        for source in transient:
            total = sum(weight for _, weight in policy[source].outcomes)
            into = sum(weight for successor, weight in policy[source].outcomes if successor == state)
            if into:
                stepped += start_row[position[source]] * into / total
        reach[state] = min(1.0, max(0.0, stepped))
    return reach


def _invert(matrix: list[list[float]], size: int) -> list[list[float]]:
    """Gauss-Jordan with partial pivoting on `[A | I]`; returns the right half."""
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(matrix[row][column]))
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        divisor = matrix[column][column]
        matrix[column] = [value / divisor for value in matrix[column]]
        for row in range(size):
            if row != column and matrix[row][column] != 0.0:
                factor = matrix[row][column]
                source = matrix[column]
                matrix[row] = [value - factor * other for value, other in zip(matrix[row], source)]
    return [row[size:] for row in matrix]
