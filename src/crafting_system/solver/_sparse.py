"""Sparse direct solution of V = c + P V for a substochastic P, without subtractions.

Large stiff components (an expected cost near 1e5 steps, as a belt that restarts from every
state) defeat sweeps, and dense elimination is cubic. Eliminating states one by one in a
minimum-degree order keeps the fill small on the sparse graphs the solver sees.

The elimination is the GTH form. A row r keeps its probabilities p_rj to the states still in the
system and its `leak` l_r, the probability to leave the component. Eliminating k with
d = sum_{j != k} p_kj + l_k (the chance to move on from k, a sum of positive terms, never 1 - p_kk) gives,
for every row r with p_rk > 0:

    p_rj += p_rk * p_kj / d  (j != k)        l_r += p_rk * l_k / d        c_r += p_rk * c_k / d

Every number stays positive, so nothing cancels however close to 1 the row sums are. The values
come back in the reverse order: V_k = (c_k + sum_j p_kj V_j) / d over the states eliminated after k.
"""

import heapq
import math

WORK_LIMIT = 200_000_000  # multiply-adds one elimination may spend before it gives up


def solve_substochastic(
    rows: list[dict[int, float]], leak: list[float], base: list[float], work_limit: int = WORK_LIMIT
) -> list[float] | None:
    """Solve V = base + P V, where `rows[s]` holds the probabilities p_sj of the states j still inside
    and `leak[s]` the probability to leave; None if a pivot is zero (an improper policy, a state that
    never leaves) or the work passes `work_limit`. The arguments are consumed.
    """
    size = len(rows)
    preds: list[set[int]] = [set() for _ in range(size)]
    for r, row in enumerate(rows):
        for j in row:
            if j != r:
                preds[j].add(r)

    def degree(k: int) -> int:
        """Fill-in bound of eliminating k: predecessors times successors (a self-loop is no successor)."""
        return len(preds[k]) * (len(rows[k]) - (k in rows[k]))

    heap = [(degree(k), k) for k in range(size)]
    heapq.heapify(heap)
    done = bytearray(size)
    steps: list[tuple[int, float, float, dict[int, float]]] = []
    work = 0
    while heap:
        cost, k = heapq.heappop(heap)
        if done[k] or cost != degree(k):
            continue  # eliminated, or stale: a fresher entry was pushed when the degree changed
        row_k = rows[k]
        row_k.pop(k, None)
        work += cost + len(row_k)
        if work > work_limit:
            return None
        d = sum(row_k.values()) + leak[k]
        if not d > 0.0:
            return None
        done[k] = 1
        steps.append((k, d, base[k], row_k))
        for j in row_k:
            preds[j].discard(k)
        l_k, c_k = leak[k], base[k]
        touched = set(row_k)
        for r in preds[k]:
            row_r = rows[r]
            factor = row_r.pop(k) / d
            for j, p in row_k.items():
                if j in row_r:
                    row_r[j] += factor * p
                else:
                    row_r[j] = factor * p
                    if j != r:
                        preds[j].add(r)
            leak[r] += factor * l_k
            base[r] += factor * c_k
            touched.add(r)
        for t in touched:
            heapq.heappush(heap, (degree(t), t))
    values = [0.0] * size
    for k, d, c_k, row_k in reversed(steps):
        total = c_k
        for j, p in row_k.items():
            total += p * values[j]
        values[k] = total / d
    return values
