"""The diagonal of the fundamental matrix of a chain, exactly, from the cycles of the chain (tickets #572 and #490).

A chain with transient states and the chances `P[s, t]` among them (the rest of each row leaks to a goal or to a state the run cannot finish
from) has the fundamental matrix `N = (I - P)^-1`: `N[s, t]` is the expected number of visits to `t` of a run that starts in `s`. The chance
that a run from `s` ever visits `t` is `N[s, t] / N[t, t]`, so the visit chance of a state needs the diagonal of `N`, which a single sparse
solve (one right-hand side) does not give, and one solve per state is too slow for thousands of states in a chain of 10^5.

What is exact and cheap is the structure of the cycles. `N[t, t]` only depends on the strongly connected component of `t`: a run that leaves
it never comes back. A state in a component of its own (no cycle through it) has `N[t, t] = 1`; a small component is inverted whole. In a
crafting policy the big components come from a few rows that many states share: a reroll sends every state that takes it to the same
thousands of outcomes, and a restart sends every one back to the start. Cutting the rows of a set `C` of states leaves a chain `B` whose
components are small. The cut rows are `U K` with `K` holding one row for each distinct row of `C` (`q` of them) and `U` saying which state has
which, so the Woodbury identity gives, exactly,

    N = N_B + N_B U (I - K N_B U)^-1 K N_B

and `N_B` is a block-triangular solve: the components of `B` in order, each a dense inverse. The work is `q` solves with `B` (and `q` with
its transpose) and one `q x q` inverse, however many states ask. When the components of `P` already are small, `C` is empty and no
Woodbury step is made. When a component stays big after the shared rows are cut, the most entered states of it are cut too (each its own
row), until none is.

Nothing here knows the game. Uses numpy, so it is a `_packed*.py` file (ADR-0010 amended).
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from ._packed import expand_ranges

INVERT_LIMIT = 4_000  # a component of at most this many states is inverted whole (a dense inverse of 4,000 states: 0.13 GB, a second or two); a bigger one is cut
BLOCK_CELLS = 40_000_000  # the cells (edges or states x right-hand sides) held at once by a gather or a block of solves: 320 MB of float64
WOODBURY_CELLS = 500_000_000  # the cells the Woodbury step may hold (4 GB of float64): derived from the memory of a runner (16 GB), the one resource it needs; past it the cycles are too tangled to put back and `CyclesTooTangled` says so


class CyclesTooTangled(ValueError):
    """The cut rows of a chain are too many to put back within `WOODBURY_CELLS`: the chances that need them are not measured, never guessed."""


def components(n: int, ptr: np.ndarray, col: np.ndarray) -> tuple[np.ndarray, int]:
    """`(label, count)`: the strongly connected components of the graph in CSR form, numbered sink-first (a component only has edges to lower numbers)."""
    index = np.full(n, -1, dtype=np.int64)
    low = np.zeros(n, dtype=np.int64)
    on = np.zeros(n, dtype=bool)
    label = np.full(n, -1, dtype=np.int64)
    count = 0
    counter = 0
    stack: list[int] = []
    for root in range(n):
        if index[root] >= 0:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on[root] = True
        calls: list[list] = [[root, _unvisited(ptr, col, root, index, on, low)]]
        while calls:
            v, children = calls[-1]
            descended = False
            for w in children:
                if index[w] >= 0:
                    continue
                index[w] = low[w] = counter
                counter += 1
                stack.append(w)
                on[w] = True
                calls.append([w, _unvisited(ptr, col, w, index, on, low)])
                descended = True
                break
            if descended:
                continue
            calls.pop()
            if calls and low[v] < low[calls[-1][0]]:
                low[calls[-1][0]] = low[v]
            if low[v] == index[v]:
                while True:
                    w = stack.pop()
                    on[w] = False
                    label[w] = count
                    if w == v:
                        break
                count += 1
    return label, count


def _unvisited(ptr, col, v, index, on, low):
    """The successors of `v` not yet visited, as an iterator; lowers `low[v]` by the successors on the stack (all that Tarjan's test needs of them)."""
    nb = col[ptr[v] : ptr[v + 1]]
    if not len(nb):
        return iter(())
    seen = index[nb]
    held = on[nb]
    if held.any():
        low[v] = min(low[v], int(seen[held].min()))
    return iter(nb[seen < 0].tolist())


@dataclass(frozen=True, slots=True)
class _Level:
    """States solved at the same depth: they read nothing but the states of the levels before."""

    nodes: np.ndarray  # first the states alone in their component, then the members of each cyclic component
    cyclic: tuple[tuple[int, int, np.ndarray], ...]  # (start, stop, inverse) of each cyclic component, positions in `nodes`
    ptr: np.ndarray  # the edges that leave the component of each node: offsets into `dep` and `weight`
    dep: np.ndarray  # the state each edge reads
    weight: np.ndarray


class Triangular:
    """Solves `(I - B) x = b` and `(I - B)^T z = b` for a chain `B` in CSR form (no entries on the diagonal), component by component.

    The equation of a state is `x[s] = b[s] + sum over t of B[s, t] x[t]`. The components are met sinks first; the edges that stay inside a
    component are handled by its dense inverse, the edges that leave it by a gather. States met at the same depth are done together.
    """

    def __init__(self, n: int, ptr: np.ndarray, col: np.ndarray, weight: np.ndarray, label: np.ndarray, count: int):
        self.n = n
        self.sizes = np.bincount(label, minlength=count)
        row = np.repeat(np.arange(n), np.diff(ptr))
        self._members = np.argsort(label, kind="stable")
        self._starts = np.concatenate(([0], np.cumsum(self.sizes)))
        self.inverse: dict[int, np.ndarray] = {}
        inside = np.flatnonzero(label[row] == label[col])
        inside = inside[np.argsort(label[row[inside]], kind="stable")]
        position = np.empty(n, dtype=np.int64)
        position[self._members] = np.arange(n) - self._starts[label[self._members]]
        owner = label[row[inside]]
        bounds = np.searchsorted(owner, np.arange(count + 1))
        for c in np.flatnonzero(self.sizes > 1).tolist():
            edges = inside[bounds[c] : bounds[c + 1]]
            matrix = np.eye(int(self.sizes[c]))
            np.subtract.at(matrix, (position[row[edges]], position[col[edges]]), weight[edges])
            self.inverse[c] = np.linalg.inv(matrix)
        leaves = label[row] != label[col]
        self._forward = self._levels(row[leaves], col[leaves], weight[leaves], label, count)
        self._backward = self._levels(col[leaves], row[leaves], weight[leaves], label, count)

    def _levels(self, own: np.ndarray, dep: np.ndarray, weight: np.ndarray, label: np.ndarray, count: int) -> list[_Level]:
        """The levels of the solve in which the state `own[e]` reads the state `dep[e]`, for the edges that leave a component."""
        n, members, starts = self.n, self._members, self._starts
        own_comp, dep_comp = label[own], label[dep]
        pending = np.bincount(own_comp, minlength=count)  # the edges a component still waits for
        by_dep = np.argsort(dep_comp, kind="stable")
        dep_ptr = np.searchsorted(dep_comp[by_dep], np.arange(count + 1))
        by_own = np.argsort(own, kind="stable")
        own_ptr = np.searchsorted(own[by_own], np.arange(n + 1))
        e_dep, e_weight = dep[by_own], weight[by_own]
        levels: list[_Level] = []
        ready = np.flatnonzero(pending == 0)
        while len(ready):
            alone = ready[self.sizes[ready] == 1]
            cyclic = ready[self.sizes[ready] > 1]
            parts = [members[starts[alone]]]
            spans = []
            at = len(parts[0])
            for c in cyclic.tolist():
                group = members[starts[c] : starts[c + 1]]
                spans.append((at, at + len(group), self.inverse[c]))
                parts.append(group)
                at += len(group)
            order = np.concatenate(parts)
            per_node = own_ptr[order + 1] - own_ptr[order]
            idx = expand_ranges(own_ptr[order], per_node)
            levels.append(_Level(order, tuple(spans), np.concatenate(([0], np.cumsum(per_node))), e_dep[idx], e_weight[idx]))
            freed = expand_ranges(dep_ptr[ready], dep_ptr[ready + 1] - dep_ptr[ready])
            if not len(freed):
                break
            waiting = own_comp[by_dep[freed]]
            pending = pending - np.bincount(waiting, minlength=count)
            ready = np.unique(waiting)
            ready = ready[pending[ready] == 0]
        return levels

    def _solve(self, levels: list[_Level], rhs: np.ndarray, transpose: bool) -> np.ndarray:
        x = np.array(rhs, dtype=np.float64, copy=True)
        width = 1 if x.ndim == 1 else x.shape[1]
        room = max(1, BLOCK_CELLS // width)  # edges gathered at once
        for level in levels:
            nodes, ptr = level.nodes, level.ptr
            first = 0
            while first < len(nodes):
                last = int(np.searchsorted(ptr, ptr[first] + room, side="right")) - 1  # the nodes whose edges fit in `room`
                last = min(len(nodes), max(last, first + 1))
                lo, hi = int(ptr[first]), int(ptr[last])
                if hi > lo:
                    shape = (-1,) + (1,) * (x.ndim - 1)
                    terms = level.weight[lo:hi].reshape(shape) * x[level.dep[lo:hi]]
                    sizes = np.diff(ptr[first : last + 1])
                    some = np.flatnonzero(sizes > 0)
                    sums = np.zeros((last - first,) + x.shape[1:])
                    sums[some] = np.add.reduceat(terms, ptr[first:last][some] - lo, axis=0)
                    x[nodes[first:last]] += sums
                first = last
            for a, b, inverse in level.cyclic:
                block = nodes[a:b]
                x[block] = (inverse.T if transpose else inverse) @ x[block]
        return x

    def solve(self, rhs: np.ndarray) -> np.ndarray:
        """`x` with `(I - B) x = rhs`; `rhs` is `n` or `n x k`."""
        return self._solve(self._forward, rhs, False)

    def solve_transposed(self, rhs: np.ndarray) -> np.ndarray:
        """`z` with `(I - B)^T z = rhs`; `rhs` is `n` or `n x k`."""
        return self._solve(self._backward, rhs, True)

    def diagonal(self) -> np.ndarray:
        """`N[s, s]` of every state: 1 for a state alone in its component, the diagonal of the component's inverse otherwise."""
        out = np.ones(self.n)
        for c, inverse in self.inverse.items():
            out[self._members[self._starts[c] : self._starts[c + 1]]] = np.diag(inverse)
        return out


def inverse_diagonal(
    n: int,
    ptr: np.ndarray,
    col: np.ndarray,
    weight: np.ndarray,
    invert_limit: int | None = None,
    start: int = 0,
    start_row: np.ndarray | None = None,
    progress: Callable[[str], None] | None = None,
) -> tuple[np.ndarray, float]:
    """`(diagonal of N = (I - P)^-1, deviation)` for the chain `P` (CSR, no entries on the diagonal), exact up to the rounding of the dense inverses.

    `weight[e]` is `P[s, col[e]]` for the edges `e` of row `s` (`ptr`). A component of at most `invert_limit` states is inverted whole;
    above that the rows that several states share are cut first and the Woodbury step of the module text is made.

    The check. When the row `start_row` of N for the state `start` is known from another method (a sparse solve whose true residual was
    measured), the same pieces give that row too, and `deviation` is the largest relative difference between the two over the states whose
    diagonal the cut changes (0 when no row is given): a wrong dense inverse, block or identity shows there, not only in a diagonal nobody has
    another figure for.
    """
    limit = INVERT_LIMIT if invert_limit is None else invert_limit
    say = progress or (lambda _text: None)
    began = time.perf_counter()
    label, count = components(n, ptr, col)
    sizes = np.bincount(label, minlength=count)
    big = sizes[label] > limit
    say(f"cycles: {n:,} states, {count:,} components, the biggest {int(sizes.max()) if count else 0:,} ({time.perf_counter() - began:.1f} s)")
    if not big.any():
        base = Triangular(n, ptr, col, weight, label, count)
        say(f"cycles: every component inverted whole ({time.perf_counter() - began:.1f} s)")
        return base.diagonal(), _deviation(base.solve_transposed(_unit(n, start)) if start_row is not None else None, start_row, np.arange(n))
    cut = _cut_rows(n, ptr, col, weight, big, limit)
    say(f"cycles: {int(cut.sum()):,} rows cut from {int(big.sum()):,} states in components above {limit:,} ({time.perf_counter() - began:.1f} s)")
    return _woodbury(n, ptr, col, weight, cut, big, start, start_row, say)


def _unit(n: int, at: int) -> np.ndarray:
    out = np.zeros(n)
    out[at] = 1.0
    return out


def _deviation(computed: np.ndarray | None, expected: np.ndarray | None, states: np.ndarray) -> float:
    """The largest relative difference between two rows of N over `states` (the row `expected` is positive wherever the start can go)."""
    if computed is None or expected is None or not len(states):
        return 0.0
    a, b = computed[states], expected[states]
    scale = np.maximum(np.abs(b), 1e-9 * float(np.max(np.abs(b))))  # a state visited a billion times less than the likeliest is not a witness
    return float(np.max(np.abs(a - b) / np.where(scale > 0, scale, 1.0)))


def _row_groups(ptr: np.ndarray, col: np.ndarray, weight: np.ndarray, states: np.ndarray) -> list[list[int]]:
    """The states of `states` grouped by identical rows."""
    groups: dict[bytes, list[int]] = {}
    for s in states.tolist():
        a, b = int(ptr[s]), int(ptr[s + 1])
        if b > a:  # an empty row cuts nothing
            groups.setdefault(col[a:b].tobytes() + weight[a:b].tobytes(), []).append(s)
    return list(groups.values())


def _without_rows(n: int, ptr: np.ndarray, col: np.ndarray, weight: np.ndarray, cut: np.ndarray):
    """The chain with the rows of the states `cut` (a boolean mask) emptied: `(ptr, col, weight)`."""
    sizes = np.diff(ptr)
    keep = ~np.repeat(cut, sizes)
    return np.concatenate(([0], np.cumsum(np.where(cut, 0, sizes)))), col[keep], weight[keep]


def _cut_rows(n: int, ptr: np.ndarray, col: np.ndarray, weight: np.ndarray, big: np.ndarray, limit: int) -> np.ndarray:
    """A boolean mask of states of the big components whose rows are cut so that no component of the rest has more than `limit` states."""
    cut = np.zeros(n, dtype=bool)
    for members in _row_groups(ptr, col, weight, np.flatnonzero(big)):
        if len(members) > 1:
            cut[members] = True
    while True:
        new_ptr, new_col, _ = _without_rows(n, ptr, col, weight, cut)
        label, count = components(n, new_ptr, new_col)
        sizes = np.bincount(label, minlength=count)
        over = np.flatnonzero(sizes > limit)
        if not len(over):
            return cut
        row = np.repeat(np.arange(n), np.diff(new_ptr))
        entered = np.bincount(new_col[label[row] == label[new_col]], minlength=n)  # the edges of its own component that enter each state
        for c in over.tolist():
            members = np.flatnonzero(label == c)
            order = members[np.argsort(-entered[members], kind="stable")]
            cut[order[: max(1, -(-len(members) // (4 * limit)))]] = True


def _woodbury(
    n: int,
    ptr: np.ndarray,
    col: np.ndarray,
    weight: np.ndarray,
    cut: np.ndarray,
    big: np.ndarray,
    start: int,
    start_row: np.ndarray | None,
    say: Callable[[str], None],
) -> tuple[np.ndarray, float]:
    """`(diagonal, deviation)` of N for the chain with the rows `cut` put back: N_B on the small components, N_B + N_B U (I - K N_B U)^-1 K N_B on `big`."""
    new_ptr, new_col, new_weight = _without_rows(n, ptr, col, weight, cut)
    label, count = components(n, new_ptr, new_col)
    sizes = np.bincount(label, minlength=count)
    base = Triangular(n, new_ptr, new_col, new_weight, label, count)
    diagonal = base.diagonal()
    groups = _row_groups(ptr, col, weight, np.flatnonzero(cut))
    q = len(groups)
    say(f"cycles: the chain without the cut rows has {count:,} components, the biggest {int(sizes.max()):,}; {q:,} distinct rows are cut")
    rows = [(col[ptr[g[0]] : ptr[g[0] + 1]], weight[ptr[g[0]] : ptr[g[0] + 1]]) for g in groups]  # the rows of K
    wanted = np.flatnonzero(big)
    cells = (2 * len(wanted) + 2 * q) * q  # N_B U and K N_B on the wanted states, K N_B U and its inverse
    if cells > WOODBURY_CELLS:
        raise CyclesTooTangled(
            f"putting back {q:,} distinct cut rows for {len(wanted):,} states needs {cells:,} cells, past the {WOODBURY_CELLS:,} the memory of a run allows"
        )
    block = max(1, BLOCK_CELLS // max(1, n))
    y_w = np.zeros((len(wanted), q))  # N_B U on the wanted states
    t = np.zeros((q, q))  # K N_B U
    z_w = np.zeros((q, len(wanted)))  # K N_B on the wanted states
    y_start = np.zeros(q)  # N_B U on the start
    for lo in range(0, q, block):
        hi = min(q, lo + block)
        rhs = np.zeros((n, hi - lo))
        for g in range(lo, hi):
            rhs[groups[g], g - lo] = 1.0
        y = base.solve(rhs)
        say(f"cycles: solves {lo + 1:,} to {hi:,} of {q:,} done")
        y_w[:, lo:hi] = y[wanted]
        y_start[lo:hi] = y[start]
        for a, (cols, vals) in enumerate(rows):
            t[a, lo:hi] = vals @ y[cols]
        rhs = np.zeros((n, hi - lo))
        for g in range(lo, hi):
            rhs[rows[g][0], g - lo] = rows[g][1]
        z_w[lo:hi, :] = base.solve_transposed(rhs)[wanted].T  # column a is N_B^T of the row a of K, that is row a of K N_B
    middle = np.linalg.inv(np.eye(q) - t)
    diagonal[wanted] += np.einsum("wa,ab,bw->w", y_w, middle, z_w, optimize=True)
    deviation = 0.0
    if start_row is not None:
        row = base.solve_transposed(_unit(n, start))  # N_B[start, :]
        row[wanted] += (y_start @ middle) @ z_w
        deviation = _deviation(row, start_row, wanted)
    return diagonal, deviation
