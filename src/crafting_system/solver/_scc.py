"""Strongly connected components, iterative (graphs reach 10^6 states)."""

from collections.abc import Iterable, Sequence


def strongly_connected_components(
    adjacency: Sequence[Sequence[int]], nodes: Iterable[int]
) -> list[list[int]]:
    """Tarjan's algorithm without recursion.

    Components come out sink-first, which is reverse topological order of the condensation: a
    component only has edges to components emitted before it. `nodes` fixes the roots and their
    order; every successor reachable from them must be a valid index into `adjacency`.
    """
    size = len(adjacency)
    order = [-1] * size
    low = [0] * size
    on_stack = [False] * size
    cursor = [0] * size
    components: list[list[int]] = []
    stack: list[int] = []
    counter = 0
    for root in nodes:
        if order[root] != -1:
            continue
        order[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack[root] = True
        calls = [root]
        while calls:
            v = calls[-1]
            edges = adjacency[v]
            if cursor[v] < len(edges):
                w = edges[cursor[v]]
                cursor[v] += 1
                if order[w] == -1:
                    order[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on_stack[w] = True
                    calls.append(w)
                elif on_stack[w] and order[w] < low[v]:
                    low[v] = order[w]
            else:
                calls.pop()
                if calls and low[v] < low[calls[-1]]:
                    low[calls[-1]] = low[v]
                if low[v] == order[v]:
                    component = []
                    while True:
                        w = stack.pop()
                        on_stack[w] = False
                        component.append(w)
                        if w == v:
                            break
                    components.append(component)
    return components
