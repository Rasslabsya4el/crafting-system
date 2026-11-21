"""The exact solve of a graph whose float64 certificate cannot reach its values: policy iteration in rational numbers on the exact quotient (#1380).

A plan that needs about `N` attempts carries values `N` times the cost of a step, and float64 holds a value only to `eps` of itself: once
`eps * N` is near the share the certificate asks (1e-3 under a gap, 1e-6 exact), the residual of the rounding alone is larger than the margin
of a step, and `solve_graph` refuses the solve whatever its values. R17's whole Talisman (#1289) is the case: an Alchemy round reaches the
target with a chance of 2.4e-14 an Orb, the restart of 533 c makes every miss go back to the start, and the plan costs 2.26e16 c, a value no
computation in float64 certifies closer than 0.18 of itself. The model is right (its odds are the game's), its arithmetic is not enough.

The graph of such a round merges into a handful of classes (`exact_classes`: R17's rounds 1 to 10 into 3 to 9), whose kernels keep their
integer weights. On them the Bellman equation of a fixed policy is a small linear system with rational coefficients (the costs are float64,
dyadic rationals, the chances `weight / total`), solved here exactly in `fractions.Fraction`; the policy is improved while some action is
cheaper in exact arithmetic (policy iteration on a stochastic shortest path whose costs are all above zero ends at the optimum from any proper
policy, every policy it passes through proper). What comes out is the optimum exactly: the values are the exact rationals rounded once to
float64, so the certified relative error is one rounding (`EPS`), and no tolerance is asked or loosened.

The work grows with the cube of the classes held at once and with the digits of the weights (Gauss-Jordan elimination of fractions), so it is
tried only on a quotient of at most `EXACT_CLASSES` classes (the merge stops counting past it) whose work, counted from its classes and the bits of its largest
kernel total, is at most `EXACT_WORK` (#868's Chaos Orb kernels reach 22,965-bit totals, on which 20 classes did not end in 150 s); otherwise the solve is
refused as before, by the caller's float64 certificate, and its refusal says the exact solve did not apply. It runs only where that
certificate refused, so a solve that certified keeps its numbers to the bit.
"""

from fractions import Fraction

import numpy as np

from ._packed import PackedGraph, kernel_any
from ._packed_merge import exact_classes, quotient

EXACT_CLASSES = 64  # the merge stops counting past this many classes: no quotient this large is within `EXACT_WORK` (with 40-bit weights, 63
# classes took 8.9 s on the server)
EXACT_WORK = 1e10  # the work of the elimination, counted as classes^3 * (classes * bits of the largest kernel total)^1.5 (each of its m^3 steps
# multiplies fractions that grow to about m b bits). Measured on the server, every class reaching every other: 31 classes of 127 bits (7e9):
# 1.05 s; 30 of 2,000 bits (4e11): 44 s, 20 of 20,000 bits (2e12): not ended in 150 s (#1380's checker); R17's refused rounds, 3 to 9 classes
# of up to 3,113 bits (at most 1e8): milliseconds. A choice of the arithmetic, not a cut: a larger work is refused as before
FLOAT_MAX = Fraction(np.finfo(np.float64).max)


def exact_quotient(graph: PackedGraph, inside: np.ndarray) -> tuple[np.ndarray, np.ndarray, PackedGraph, np.ndarray, np.ndarray, np.ndarray] | None:
    """The exact optimum of `graph` over the states `inside` (the others are dead: an action that may reach one is not taken), or None when the
    quotient has more than `EXACT_CLASSES` classes or its work is above `EXACT_WORK`, when an action it may take is free (cost 0: an unveil, a pick; policy iteration is exact only
    where every cost is above zero, so that no policy that never finishes costs less than one that does), or when none of its policies over
    `inside` reaches the goal from every state of it.

    Returns `(value, solved, reduced, kernel_map, cls, class_action)`: the value of every state of `graph` (the exact rational rounded once,
    infinite outside `inside`), the states solved, and the quotient with its policy for `_packed_solve.lift_policy`."""
    classes = exact_classes(graph, most=EXACT_CLASSES)
    if classes is None or classes.count > EXACT_CLASSES:
        return None
    reduced, kernel_map = quotient(graph, classes)
    cls = classes.cls
    m = reduced.n
    live = np.zeros(m, dtype=bool)
    live[cls[inside]] = True  # an exact class holds states of one future: inside together or dead together
    live |= reduced.goal
    bad = kernel_any(reduced, ~live)
    weights = [reduced.kernel_weights(k) for k in range(reduced.num_kernels)]
    digits = max((sum(wt).bit_length() for k, wt in enumerate(weights) if not bad[k]), default=1)
    if m**3 * (m * digits) ** 1.5 > EXACT_WORK:
        return None  # the fractions would grow past what a solve may take (module text)
    chances = []
    for k, wt in enumerate(weights):
        total = sum(wt)
        succ = reduced.k_succ[reduced.k_ptr[k] : reduced.k_ptr[k + 1]].tolist()
        chances.append([(int(t), Fraction(w, total)) for t, w in zip(succ, wt)])
    acts: list[list[tuple[int, Fraction, int]]] = [[] for _ in range(m)]  # per class: (action, cost, kernel)
    for s in range(m):
        if reduced.goal[s] or not live[s]:
            continue
        for a in range(int(reduced.act_ptr[s]), int(reduced.act_ptr[s + 1])):
            k = int(reduced.act_kernel[a])
            if not bad[k]:
                if not reduced.act_cost[a] > 0.0:
                    return None  # a free action: a free cycle can keep a run from the goal at no cost, and policy iteration needs every cost above zero
                acts[s].append((a, Fraction(float(reduced.act_cost[a])), k))
    states = [s for s in range(m) if live[s] and not reduced.goal[s]]
    if any(not acts[s] for s in states):
        return None
    policy = _proper_policy(states, acts, chances, reduced.goal)
    if policy is None:
        return None
    while True:
        value = _evaluate(states, policy, chances)
        changed = False
        for s in states:
            best, best_q = policy[s], value[s]
            for a, cost, k in acts[s]:
                q = cost + sum((p * value.get(t, 0) for t, p in chances[k]), Fraction(0))
                if q < best_q:
                    best, best_q = (a, cost, k), q
            if best is not policy[s]:
                policy[s], changed = best, True
        if not changed:
            break
    out = np.full(m, np.inf)
    out[reduced.goal] = 0.0
    class_action = np.full(m, -1, dtype=np.int64)
    if any(value[s] > FLOAT_MAX for s in states):
        return None  # a value past the range of float64 (no caller could hold it)
    for s in states:
        out[s] = float(value[s])  # (`float` of a Fraction is correctly rounded)
        class_action[s] = policy[s][0]
    solved = live[cls]
    return out[cls], solved, reduced, kernel_map, cls, class_action


def _proper_policy(states, acts, chances, goal) -> dict | None:
    """A policy over `states` that reaches the goal from each of them (backward from the goals: each state takes an action with a successor
    already settled; a proper policy, since every state's chosen action leads closer to the goal with positive chance). None when some state
    has no such action."""
    settled = {s for s in range(len(goal)) if goal[s]}
    policy: dict = {}
    left = set(states)
    while left:
        grew = False
        for s in sorted(left):
            for each in sorted(acts[s], key=lambda x: x[1]):
                if any(t in settled for t, _ in chances[each[2]]):
                    policy[s] = each
                    break
            if s in policy:
                settled.add(s)
                grew = True
        left -= settled
        if not grew:
            return None
    return policy


def _evaluate(states: list[int], policy: dict, chances: list) -> dict[int, Fraction]:
    """The exact values of `policy`: Gauss-Jordan elimination of `(I - P) V = c` over `states` in fractions (the goals are 0)."""
    index = {s: i for i, s in enumerate(states)}
    n = len(states)
    rows = []
    for s in states:
        _, cost, k = policy[s]
        row = [Fraction(0)] * (n + 1)
        row[index[s]] += 1
        for t, p in chances[k]:
            if t in index:
                row[index[t]] -= p
        row[n] = cost
        rows.append(row)
    for c in range(n):
        pivot = next(r for r in range(c, n) if rows[r][c] != 0)  # a proper policy's system is regular: some row has it
        rows[c], rows[pivot] = rows[pivot], rows[c]
        lead = rows[c][c]
        rows[c] = [x / lead for x in rows[c]]
        for r in range(n):
            if r != c and rows[r][c] != 0:
                f = rows[r][c]
                rows[r] = [x - f * y for x, y in zip(rows[r], rows[c])]
    return {s: rows[index[s]][n] for s in states}
