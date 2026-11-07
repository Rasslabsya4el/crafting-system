"""The diagonal of the fundamental matrix of a chain from the cycles of the chain (the identities are exact; the numbers carry the rounding of dense inverses) (tickets #572 and #490).

A chain with transient states and the chances `Q[s, t]` among them (the rest of each row leaks to a goal or to a state the run cannot finish
from) has the fundamental matrix `N = (I - Q)^-1`: `N[s, t]` is the expected number of visits to `t` of a run that starts in `s`. The chance
that a run from `s` ever visits `t` is `N[s, t] / N[t, t]`, so the visit chance of a state needs the diagonal of `N`, which a single sparse
solve (one right-hand side) does not give, and one solve per state is too slow for thousands of states in a chain of 10^5.

No `1 - p` is formed: each row is divided by the chance to leave its state (`leave[s] = 1 - Q[s, s]`, a sum of the other terms), which takes the
self-loops out, and `P[s, t] = Q[s, t] / leave[s]` is what is solved with; N = (I - P)^-1 diag(1 / leave). The sentences below speak of `P`.

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
BLOCK_CELLS = 10_000_000  # the cells (edges or states x right-hand sides) held at once by a gather or a block of solves: 80 MB of float64 (a block of solves holds about six of them)
CUT_BATCH = 40  # a round cuts the 1/40 of a component's states that most cycles run through, and looks again
WOODBURY_CELLS = 600_000_000  # the cells the Woodbury step may hold, all counted (4.8 GB of float64): what a runner (16 GB) has over a plan of R14 (8.5 GB), with a margin; past it the cycles are too tangled to put back and `CyclesTooTangled` says so


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
    leave: np.ndarray,
    invert_limit: int | None = None,
    start: int = 0,
    start_row: np.ndarray | None = None,
    progress: Callable[[str], None] | None = None,
    leak: np.ndarray | None = None,
) -> tuple[np.ndarray, float]:
    """`(diagonal of N = (I - Q)^-1, deviation)` for the chain `Q` (CSR, self-loops included), exact up to the rounding of the dense inverses.

    `weight[e]` is `Q[s, col[e]]` for the edges `e` of row `s` (`ptr`); `leave[s]` is the chance to leave `s` for any other state (a goal, or a
    state that cannot finish, too): `1 - Q[s, s]` with the sum made of positive terms, so that no `1 - p` is formed. The system is solved with each
    row divided by `leave`, that is for `P[s, t] = Q[s, t] / leave[s]` without the self-loops, and the answer scaled back: N = (I - P)^-1 diag(1/leave).
    A component of `P` of at most `invert_limit` states is inverted whole; above that the rows that several states share (compared as `Q` rows,
    self-loop included, so a reroll that some of its takers are among the outcomes of is still one row) are cut first and the Woodbury step of the
    module text is made.

    `leak[s]` is the chance that `s` goes to a state outside the chain (a goal, a state that cannot finish), a sum of positive terms; the row of `s`
    in `Q` and `leak[s]` add to 1. It is needed only to put the cut rows back without forming `1 - p` (see `_woodbury`); when it is not given it is
    `1 - sum of the row`, which is as good as the rows are away from stiff.

    The check. When the row `start_row` of N for the state `start` is known from another method (a sparse solve whose true residual was
    measured), the same pieces give that row too, and `deviation` is the largest relative difference between the two over the states whose
    diagonal the cut changes (0 when no row is given): a wrong dense inverse, block or identity shows there, not only in a diagonal nobody has
    another figure for.
    """
    limit = INVERT_LIMIT if invert_limit is None else invert_limit
    say = progress or (lambda _text: None)
    began = time.perf_counter()
    row = np.repeat(np.arange(n), np.diff(ptr))
    off = row != col
    p_ptr = np.concatenate(([0], np.cumsum(np.bincount(row[off], minlength=n))))
    p_col, p_weight = col[off], weight[off] / leave[row[off]]
    label, count = components(n, p_ptr, p_col)
    sizes = np.bincount(label, minlength=count)
    big = sizes[label] > limit
    say(f"cycles: {n:,} states, {count:,} components, the biggest {int(sizes.max()) if count else 0:,} ({time.perf_counter() - began:.1f} s)")
    scale = 1.0 / leave
    if not big.any():
        base = Triangular(n, p_ptr, p_col, p_weight, label, count)
        say(f"cycles: every component inverted whole ({time.perf_counter() - began:.1f} s)")
        found = base.solve_transposed(_unit(n, start)) * scale if start_row is not None else None
        return base.diagonal() * scale, _deviation(found, start_row, np.arange(n))
    cut = _cut_rows(n, ptr, col, weight, p_ptr, p_col, big, limit)
    say(f"cycles: {int(cut.sum()):,} rows cut from {int(big.sum()):,} states in components above {limit:,} ({time.perf_counter() - began:.1f} s)")
    if leak is None:
        leak = np.maximum(0.0, 1.0 - np.bincount(row, weights=weight, minlength=n))
    return _woodbury(n, ptr, col, weight, p_ptr, p_col, p_weight, scale, cut, big, start, start_row, say, leak)


def _unit(n: int, at: int) -> np.ndarray:
    out = np.zeros(n)
    out[at] = 1.0
    return out


def _deviation(computed: np.ndarray | None, expected: np.ndarray | None, states: np.ndarray) -> float:
    """The largest relative difference between two rows of N over `states` (the row `expected` is positive wherever the start can go)."""
    if computed is None or expected is None or not len(states):
        return 0.0
    a, b = computed[states], expected[states]
    floor = np.maximum(np.abs(b), 1e-9 * float(np.max(np.abs(b))))  # a state visited a billion times less than the likeliest is not a witness
    return float(np.max(np.abs(a - b) / np.where(floor > 0, floor, 1.0)))


def _row_groups(ptr: np.ndarray, col: np.ndarray, weight: np.ndarray, states: np.ndarray) -> list[list[int]]:
    """The states of `states` grouped by identical rows."""
    groups: dict[bytes, list[int]] = {}
    for s in states.tolist():
        a, b = int(ptr[s]), int(ptr[s + 1])
        if b > a:  # an empty row cuts nothing
            groups.setdefault(col[a:b].tobytes() + weight[a:b].tobytes(), []).append(s)
    return list(groups.values())


def _without_rows(ptr: np.ndarray, col: np.ndarray, weight: np.ndarray, cut: np.ndarray):
    """The chain with the rows of the states `cut` (a boolean mask) emptied: `(ptr, col, weight)`."""
    sizes = np.diff(ptr)
    keep = ~np.repeat(cut, sizes)
    return np.concatenate(([0], np.cumsum(np.where(cut, 0, sizes)))), col[keep], weight[keep]


def _cut_rows(n, ptr, col, weight, p_ptr, p_col, big: np.ndarray, limit: int) -> np.ndarray:
    """A boolean mask of states of the big components whose rows are cut so that no component of the rest has more than `limit` states."""
    cut = np.zeros(n, dtype=bool)
    for members in _row_groups(ptr, col, weight, np.flatnonzero(big)):
        if len(members) > 1:
            cut[members] = True
    while True:
        new_ptr, new_col, _ = _without_rows(p_ptr, p_col, p_col, cut)
        label, count = components(n, new_ptr, new_col)
        sizes = np.bincount(label, minlength=count)
        over = np.flatnonzero(sizes > limit)
        if not len(over):
            return cut
        row = np.repeat(np.arange(n), np.diff(new_ptr))
        inside = label[row] == label[new_col]
        entered = np.bincount(new_col[inside], minlength=n)  # the edges of its own component that enter each state
        leaving = np.bincount(row[inside], minlength=n)  # ... and that leave it: a state many cycles run through has both
        score = entered.astype(float) * leaving
        for c in over.tolist():
            members = np.flatnonzero(label == c)
            order = members[np.argsort(-score[members], kind="stable")]
            cut[order[: max(1, len(members) // CUT_BATCH)]] = True


def _woodbury(n, ptr, col, weight, p_ptr, p_col, p_weight, scale, cut, big, start, start_row, say, leak) -> tuple[np.ndarray, float]:
    """`(diagonal, deviation)` of N = (I - Q)^-1 by cutting the rows `cut` of Q out and putting them back (module text).

    With A = I - Q_B, where Q_B is Q with the rows `cut` emptied, A^-1 = (I - P_B)^-1 diag(r) with r = 1/leave on the rows kept and 1 on the rows cut
    (a cut row of A is the unit row), and N = A^-1 + A^-1 U (I - K A^-1 U)^-1 K A^-1 on the states of the `big` components; elsewhere N is A^-1.

    I - K A^-1 U is not formed as a difference. A cut state that stays with chance 1 - 1e-13 has a row of K whose entry on itself times (A^-1 U)
    on itself is 1 - 1e-13, and 1 minus that has no digits left. A row `a` of K and its leak add to 1, so M[a, b] = [a = b] leak(a) + sum over
    the entries c of the row of K[a, c] ([a = b] - (A^-1 U)[c, b]), and for a cut state c of the group `a` the term is exactly 0.
    """
    new_ptr, new_col, new_weight = _without_rows(p_ptr, p_col, p_weight, cut)
    label, count = components(n, new_ptr, new_col)
    sizes = np.bincount(label, minlength=count)
    base = Triangular(n, new_ptr, new_col, new_weight, label, count)
    r = np.where(cut, 1.0, scale)  # the rows of A: each divided by leave, a cut row not at all
    diagonal = base.diagonal() * r  # A^-1[s, s]
    groups = _row_groups(ptr, col, weight, np.flatnonzero(cut))
    q = len(groups)
    say(f"cycles: the chain without the cut rows has {count:,} components, the biggest {int(sizes.max()):,}; {q:,} distinct rows are cut")
    rows = [(col[ptr[g[0]] : ptr[g[0] + 1]], weight[ptr[g[0]] : ptr[g[0] + 1]]) for g in groups]  # the rows of K, self-loops included
    wanted = np.flatnonzero(big)
    block = max(1, BLOCK_CELLS // max(1, n))
    # everything that is held at once: A^-1 U and K A^-1 on the wanted states, K A^-1 U and its inverse, the blocks of a solve (the right-hand
    # side, its scaled copy, the answer, the answer's copy and the gathers: six), and a chunk of the sum below
    cells = (2 * len(wanted) + 2 * q) * q + 6 * min(BLOCK_CELLS, n * q) + min(BLOCK_CELLS, len(wanted) * q)
    if cells > WOODBURY_CELLS:
        raise CyclesTooTangled(
            f"putting back {q:,} distinct cut rows for {len(wanted):,} states needs {cells:,} cells, past the {WOODBURY_CELLS:,} the memory of a run allows"
        )
    y_w = np.zeros((len(wanted), q))  # A^-1 U on the wanted states
    m = np.zeros((q, q))  # I - K A^-1 U, term by term (see the text above)
    z_w = np.zeros((q, len(wanted)))  # K A^-1 on the wanted states
    y_start = np.zeros(q)  # A^-1 U on the start
    for lo in range(0, q, block):
        hi = min(q, lo + block)
        rhs = np.zeros((n, hi - lo))
        for g in range(lo, hi):
            rhs[groups[g], g - lo] = 1.0
        y = base.solve(rhs * r[:, None])  # A^-1 = (I - P_B)^-1 diag(r)
        say(f"cycles: solves {lo + 1:,} to {hi:,} of {q:,} done")
        y_w[:, lo:hi] = y[wanted]
        y_start[lo:hi] = y[start]
        for a, (cols, vals) in enumerate(rows):
            m[a, lo:hi] = -(vals @ y[cols])
            if lo <= a < hi:
                m[a, a] = leak[groups[a][0]] + float(np.sum(vals * (1.0 - y[cols, a - lo])))
        rhs = np.zeros((n, hi - lo))
        for g in range(lo, hi):
            np.add.at(rhs[:, g - lo], rows[g][0], rows[g][1])  # (a row may name a state twice: its entries add)
        z_w[lo:hi, :] = (r[:, None] * base.solve_transposed(rhs))[wanted].T  # column a is A^-T of the row a of K, that is row a of K A^-1
    middle = np.linalg.inv(m)
    chunk = max(1, BLOCK_CELLS // max(1, q))  # the sum over a and b of y[w, a] middle[a, b] z[b, w], some states at a time: its first product is a chunk x q block
    for lo in range(0, len(wanted), chunk):
        part = slice(lo, min(len(wanted), lo + chunk))
        diagonal[wanted[part]] += np.einsum("wa,aw->w", y_w[part] @ middle, z_w[:, part])
    deviation = 0.0
    if start_row is not None:
        row = r * base.solve_transposed(_unit(n, start))  # A^-1[start, :]
        row[wanted] += (y_start @ middle) @ z_w
        deviation = _deviation(row, start_row, wanted)
    return diagonal, deviation
