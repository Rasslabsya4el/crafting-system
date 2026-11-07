"""Random stochastic shortest path graphs for the envelope search tests (ticket #377): the graph, an independent dense optimum, an explicit `Problem`.

`random_graph` makes a layered graph with cycles and a restart. The offers are global (each has one price), as in a plan; at a state an offer has its own
kernel or is refused. Every state has an offer that moves toward the goal with positive chance, so a proper policy exists, and further offers that
loop, jump back or return to the start (offer 0, the restart, at every state but the start). `dense_optimum` solves the whole graph by Howard's
policy iteration with `numpy.linalg.solve`, which shares no code with the packed solver or with the search under test. `ExplicitProblem` is the
`Problem` of the search over such a graph, with a lower bound `alpha * V*` (and `alpha * Q*` for each offer) that the test chooses: a strong one
(`alpha` near 1), a weak one (`alpha` small) or a wrong one (`alpha` above 1, the planted fault).
"""

import random
from dataclasses import dataclass, field

import numpy as np

from crafting_system.cli._envelope import Refused

OFFERS = 8


@dataclass
class Graph:
    """`actions[s]` maps an offer to its kernel `{successor: weight}` at state `s`; `costs[offer]` is its price; `mover[s]` is a proper offer of `s`."""

    n: int
    goal: set[int]
    costs: list[float]
    actions: list[dict[int, dict[int, int]]]
    mover: list[int]

    def reachable(self) -> set[int]:
        seen, queue = {0}, [0]
        for s in queue:
            if s in self.goal:
                continue
            for kernel in self.actions[s].values():
                for t in kernel:
                    if t not in seen:
                        seen.add(t)
                        queue.append(t)
        return seen


def random_graph(seed: int, n: int = 40) -> Graph:
    rng = random.Random(seed)
    goal = {n - 1, n - 2}
    costs = [rng.uniform(1.0, 6.0)] + [rng.uniform(0.5, 12.0) for _ in range(OFFERS - 1)]
    actions: list[dict[int, dict[int, int]]] = []
    mover = []
    for s in range(n):
        row: dict[int, dict[int, int]] = {}
        if s in goal:
            actions.append(row)
            mover.append(-1)
            continue
        if s != 0:
            row[0] = {0: 1}
        for offer in rng.sample(range(1, OFFERS), rng.randint(3, 5)):
            kernel: dict[int, int] = {}
            for _ in range(rng.randint(1, 4)):
                kind = rng.random()
                if kind < 0.45:
                    t = rng.randint(s + 1, n - 1)  # forward
                elif kind < 0.7:
                    t = rng.randint(0, n - 1)  # anywhere, so cycles
                else:
                    t = s  # a self-loop
                kernel[t] = kernel.get(t, 0) + rng.randint(1, 20)
            row[offer] = kernel
        step = rng.choice([o for o in row if o != 0])
        t = min(n - 1, s + rng.randint(1, 3))
        row[step] = {t: rng.randint(1, 9), s: rng.randint(1, 9)} if t != s else {t: 1}
        actions.append(row)
        mover.append(step)
    return Graph(n, goal, costs, actions, mover)


def dense_optimum(graph: Graph) -> tuple[np.ndarray, list[int]]:
    """The optimal value of every state and an optimal offer for each (Howard's policy iteration, from the moving-on policy)."""
    n = graph.n
    policy = list(graph.mover)
    for _ in range(10_000):
        a = np.eye(n)
        b = np.zeros(n)
        for s in range(n):
            if s in graph.goal:
                continue
            kernel = graph.actions[s][policy[s]]
            total = sum(kernel.values())
            for t, w in kernel.items():
                a[s, t] -= w / total
            b[s] = graph.costs[policy[s]]
        value = np.linalg.solve(a, b)
        changed = False
        for s in range(n):
            if s in graph.goal:
                continue
            q = {o: graph.costs[o] + sum(w * value[t] for t, w in k.items()) / sum(k.values()) for o, k in graph.actions[s].items()}
            best = min(q, key=q.get)
            if q[best] < q[policy[s]] - 1e-12 * max(1.0, abs(q[policy[s]])):
                policy[s] = best
                changed = True
        if not changed:
            return value, policy
    raise AssertionError("policy iteration did not settle")


def q_value(graph: Graph, value: np.ndarray, state: int, offer: int) -> float:
    kernel = graph.actions[state][offer]
    return graph.costs[offer] + sum(w * value[t] for t, w in kernel.items()) / sum(kernel.values())


@dataclass
class ExplicitProblem:
    """The search over a `Graph`; `alpha` scales the exact values into the lower bounds (1 would be a perfect bound)."""

    graph: Graph
    value: np.ndarray
    alpha: float
    planted: float = 0.0  # the fault: each offer's bound is raised by a fixed pseudo-random share of this, so the best offer can look dearer than a worse one
    start: int = 0
    restart: int | None = 0
    asked: list[tuple[int, int]] = field(default_factory=list)  # (state, offer) kernels the search built

    def is_goal(self, state: int) -> bool:
        return state in self.graph.goal

    def lower(self, state: int) -> float:
        return self.alpha * float(self.value[state]) * (1.0 + self.planted * ((state * 31) % 7) / 7.0)

    def candidates(self, state: int) -> list[tuple[float, int]]:
        return [(self.alpha * q_value(self.graph, self.value, state, offer) * self._plant(state, offer), offer) for offer in self.graph.actions[state]]

    def _plant(self, state: int, offer: int) -> float:
        return 1.0 + self.planted * ((state * 7919 + offer * 104729) % 1000) / 1000.0

    def cost(self, position: int) -> float:
        return self.graph.costs[position]

    def kernel_key(self, state: int, position: int):
        return None

    def kernel(self, state: int, position: int) -> dict[int, int]:
        if position not in self.graph.actions[state]:
            raise Refused
        self.asked.append((state, position))
        return dict(self.graph.actions[state][position])

    def release(self) -> None:
        pass
