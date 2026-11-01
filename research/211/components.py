"""Strongly connected components of the product graph (outcome and input edges), and which of them are branching."""
import sys


def graph_of(acq, start):
    nodes, edges, input_edges = {}, [], set()
    order = [start]
    nodes[start] = 0
    adj = {}
    i = 0
    stats = dict(actions=0, transitions=0, input_edges=0)
    while i < len(order):
        x = order[i]; i += 1
        out = []
        if not acq.is_goal(x):
            for a in acq.actions(x):
                stats["actions"] += 1
                for o in a.outcomes:
                    stats["transitions"] += 1
                    out.append((o.state, False))
                for y in a.extra_inputs:
                    stats["input_edges"] += 1
                    out.append((y, True))
        adj[x] = out
        for y, _ in out:
            if y not in nodes:
                nodes[y] = len(order)
                order.append(y)
    return order, adj, stats


def sccs(order, adj):
    index, low, on, stack, comp = {}, {}, set(), [], {}
    counter = 0
    ncomp = 0
    for root in order:
        if root in index:
            continue
        work = [(root, iter(adj[root]))]
        index[root] = low[root] = counter; counter += 1
        stack.append(root); on.add(root)
        while work:
            v, it = work[-1]
            advanced = False
            for w, _ in it:
                if w not in index:
                    index[w] = low[w] = counter; counter += 1
                    stack.append(w); on.add(w)
                    work.append((w, iter(adj[w])))
                    advanced = True
                    break
                elif w in on:
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                u = work[-1][0]
                low[u] = min(low[u], low[v])
            if low[v] == index[v]:
                while True:
                    w = stack.pop(); on.discard(w)
                    comp[w] = ncomp
                    if w == v:
                        break
                ncomp += 1
    return comp, ncomp


def report(acq, start, limit=64):
    order, adj, stats = graph_of(acq, start)
    comp, n = sccs(order, adj)
    size, has_input = {}, set()
    for x in order:
        size[comp[x]] = size.get(comp[x], 0) + 1
        for y, is_input in adj[x]:
            if is_input and comp[y] == comp[x]:
                has_input.add(comp[x])
    branching = sorted((size[c] for c in has_input), reverse=True)
    plain = max((size[c] for c in size if c not in has_input), default=0)
    return dict(nodes=len(order), **stats, components=n, largest_plain=plain, branching_components=len(branching),
                largest_branching=branching[0] if branching else 0, branching_over_limit=sum(1 for b in branching if b > limit))
