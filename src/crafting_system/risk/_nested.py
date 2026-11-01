"""The budget DP for a chain whose actions consume inputs: the distribution of the total cost on a grid.

An action with `extra_inputs` (ADR-0022) costs, on every execution at state s, `k_s` bins plus one
independent run per input copy (started at the input state, same policy, until a goal, retries pay
again) whose total costs are added; then the outcome is drawn. So the cost of one attempt at s is a
random increment: `k_s` plus the convolution of the pmfs of the total costs of its inputs. That is
well defined only when no run depends on itself, i.e. when no input edge lies inside a strongly
connected component of the dependency graph (the outcome edges of the states that can finish plus
the input edges). `BranchingError` is raised otherwise and the caller reports the quantiles as
unresolved.

Starts. The main start (index 0) and every distinct input state each get a run. A run's distribution
depends on the runs of the inputs of the states it reaches, so the starts are processed in an order
where a start comes after those it uses (a topological order of the dependency, which exists
exactly when there is no branching).

A pass with a horizon of H bins computes for every start its pmf `f[0..H]` of the grid total cost,
exact on [0, H], and the overflow (the mass that would end above H, i.e. in flight). The rest of
the unit mass is lost: it certainly never reaches a goal (it moved to a state that cannot finish,
or an input of it never finishes). Lost mass is never stored, since neither the cdf nor the
unresolved mass reads it, so `sum(f) + overflow + lost = 1`. The overflow is summed from its
parts (`fsum`), not found by subtraction, so it is exactly 0.0 when nothing is left. A pass is exact
on [0, H] because a total cost of at most H passes only through partial sums and input costs of at
most H.

Inside a run the arrivals are an array `A[s, b]` (mass that reaches state s having paid b bins),
kept for the states that can finish and are reached from the start; a goal and a state that cannot
finish are sinks. The attempt at s has the increment `x_s`: the convolution (direct, `np.convolve`)
of the pmfs of its input copies, cut where `k_s` plus the increment passes H, with `beyond_s` the
mass that passes H (a sum above H, or an input's overflow). The mass in which some input never
finishes is in neither part. A state without inputs has the delta at 0 and no convolution is made.
The bins are taken in blocks of `kmin` (the smallest bin cost of a state that can finish): every
attempt pays at least `kmin`, so the arrivals of a block depend only on earlier blocks. When a block
is complete, every state with mass in it convolves its arrival slice with `x_s`, and for each
outcome j with probability p the part that lands at or below H goes to the goal pmf (a goal) or to
the arrivals of j (a state that can finish); a state that cannot finish gets nothing, its share is
lost. As in `_budget`, a lost share is lost whatever the cost of the move; only the mass that stays
on a goal or a state that can finish and lands above H is overflow. Empty blocks are skipped.

Iterative deepening. The input pmfs are valid only up to H, so the horizon is found by trial: it
starts at `max(horizon, 64 kmin)` bins (`horizon` is the caller's estimate, `None` when unknown),
capped at `max_bins`, and doubles until the stop rule fires at some bin of the pass (then the cdf
up to that bin is exact) or the cap is reached. The stop rule is the one of `_budget`: with a
`target`, the first bin whose cdf is at least `target + rounding_allowance(bin)`; without one, the
first bin whose unresolved mass (the absorbed mass after it plus the overflow) is at most
`tail_mass`. The unresolved mass is the mass in flight, so unlike `_budget` it holds no mass that is
certainly lost but would be realised later in the run; for a chain without lost mass the two are
the same. A pass that leaves no overflow is complete: deeper passes cannot change it, so it is
returned at once, with the cdf cut after the last bin that holds mass.

The work of a pass is about (starts * states + extra input copies) * H^2 (a direct convolution per block and state), so it
suits runs of a few hundred bins; `nested_work` is that estimate.
"""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from math import fsum, prod

import numpy as np

from ._budget import BudgetRun, rounding_allowance
from ._chain import Chain

START_BINS = 64  # the first horizon is this many times kmin bins, unless the caller's estimate is longer
DELTA = np.ones(1)
TINY = 1e-150  # masses below this are dropped into the unresolved mass: a geometric tail would run into denormals, ~1000x slower


class BranchingError(ValueError):
    """An input edge lies inside a cycle of the dependency graph: a run's distribution depends on itself."""


def _clean(values: np.ndarray) -> float:
    """Zero the entries below `TINY` in place and return their total (to be counted as unresolved)."""
    small = values < TINY
    if not small.any():
        return 0.0
    dropped = fsum(values[small].tolist())
    values[small] = 0.0
    return dropped


def nested_work(chain: Chain, horizon_bins: int) -> float:
    """The cost of one pass at a horizon in convolution cells (an estimate).

    One convolution per start and state that can finish, one more per extra copy of an input.
    """
    finishing = chain.finishing_states()
    starts = {0}
    for i in finishing:
        starts.update(chain.inputs[i])
    joins = sum(max(len(chain.inputs[i]) - 1, 0) for i in finishing)
    return float(len(starts) * len(finishing) + joins) * float(horizon_bins) ** 2


def run_nested(
    chain: Chain,
    bin_cost: Sequence[int],
    *,
    target: float | None,
    tail_mass: float,
    max_bins: int,
    horizon: int | None = None,
) -> BudgetRun:
    """Run the nested DP with `bin_cost[i]` whole bins per step in state i, like `run_budget`.

    Raises `BranchingError` when a run depends on itself, `ValueError` when the start cannot finish.
    """
    _check_branching(chain)
    finishing = chain.finishing_states()
    if not finishing or not chain.can_finish[0]:
        raise ValueError("the start state cannot finish: there is no distribution to compute")
    kmin = min(int(bin_cost[i]) for i in finishing)
    if kmin < 1:
        raise ValueError(f"every state that can finish must cost at least one bin, got {kmin!r}")
    order = _order_of_starts(chain, finishing)
    horizon_bins = min(max_bins, max(horizon or 0, START_BINS * kmin))
    while True:
        run = _Pass(chain, finishing, bin_cost, horizon_bins).run(order)
        result = _stop(run, target, tail_mass)
        if result is not None:
            return result
        if horizon_bins >= max_bins:
            return _whole(run)
        horizon_bins = min(2 * horizon_bins, max_bins)


def _check_branching(chain: Chain) -> None:
    """Raise `BranchingError` when an input edge lies inside a strongly connected component (Tarjan)."""
    n = len(chain.states)
    expanded = [a is not None for a in chain.action]
    finishing = [expanded[i] and chain.can_finish[i] for i in range(n)]

    def onward(i: int) -> list[int]:
        if not expanded[i]:
            return []
        edges = [j for j, _ in chain.succ[i]] if finishing[i] else []
        return edges + list(chain.inputs[i])

    index = [-1] * n
    low = [0] * n
    component = [-1] * n
    on_stack = [False] * n
    stack: list[int] = []
    counter = 0
    components = 0
    walk: list[tuple[int, list[int], int]] = [(0, onward(0), 0)]
    index[0] = low[0] = counter
    counter += 1
    stack.append(0)
    on_stack[0] = True
    while walk:
        node, edges, position = walk.pop()
        if position < len(edges):
            walk.append((node, edges, position + 1))
            nxt = edges[position]
            if index[nxt] == -1:
                index[nxt] = low[nxt] = counter
                counter += 1
                stack.append(nxt)
                on_stack[nxt] = True
                walk.append((nxt, onward(nxt), 0))
            elif on_stack[nxt]:
                low[node] = min(low[node], index[nxt])
            continue
        if low[node] == index[node]:
            while True:
                member = stack.pop()
                on_stack[member] = False
                component[member] = components
                if member == node:
                    break
            components += 1
        if walk:
            parent = walk[-1][0]
            low[parent] = min(low[parent], low[node])
    for i in range(n):
        if index[i] == -1 or not expanded[i]:
            continue
        for y in chain.inputs[i]:
            if component[i] == component[y]:
                raise BranchingError(
                    f"state {chain.states[i]!r} consumes {chain.states[y]!r}, which depends on it: "
                    "the distribution of a run depends on itself"
                )


def _order_of_starts(chain: Chain, finishing: list[int]) -> list[int]:
    """The starts (the main one and every input of a state that can finish), each after the starts it uses."""
    can_move = set(finishing)
    starts = [0]
    seen = {0}
    queue = deque([0])
    uses: dict[int, set[int]] = {}
    while queue:
        y = queue.popleft()
        reached = {y}
        frontier = [y]
        needs: set[int] = set()
        while frontier:
            s = frontier.pop()
            if s not in can_move:
                continue
            needs.update(chain.inputs[s])
            for j, _ in chain.succ[s]:
                if j not in reached:
                    reached.add(j)
                    frontier.append(j)
        uses[y] = needs
        for z in sorted(needs):
            if z not in seen:
                seen.add(z)
                starts.append(z)
                queue.append(z)
    waiting = {y: len(uses[y]) for y in starts}
    users: dict[int, list[int]] = {y: [] for y in starts}
    for y in starts:
        for z in uses[y]:
            users[z].append(y)
    ready = deque(y for y in starts if waiting[y] == 0)
    order: list[int] = []
    while ready:
        z = ready.popleft()
        order.append(z)
        for y in users[z]:
            waiting[y] -= 1
            if waiting[y] == 0:
                ready.append(y)
    return order


@dataclass(frozen=True, slots=True)
class _Part:
    """The run from a start at a horizon: `pmf[0..H]`, the mass in it and the overflow."""

    pmf: np.ndarray
    mass: float
    overflow: float


@dataclass(frozen=True, slots=True)
class _Attempt:
    """One attempt at a state: `extra[t]` is the mass of an increment of t bins beyond the state's `k`."""

    k: int
    extra: np.ndarray
    inside: float  # the mass of `extra`
    beyond: float  # k plus the increment passes the horizon (or an input overflowed)


@dataclass(frozen=True, slots=True)
class _Moves:
    """Where the outcomes of a state go: goals and states that can finish; `stay` is their probability."""

    goals: tuple[float, ...]
    onward: tuple[tuple[int, float], ...]
    stay: float


class _Pass:
    def __init__(self, chain: Chain, finishing: Sequence[int], bin_cost: Sequence[int], horizon: int) -> None:
        self.chain = chain
        self.horizon = horizon
        self.k = {i: int(bin_cost[i]) for i in finishing}
        self.kmin = min(self.k.values())
        self.moves: dict[int, _Moves] = {}
        for i in finishing:
            goals: list[float] = []
            onward: list[tuple[int, float]] = []
            for j, p in chain.succ[i]:
                if chain.goal[j]:
                    goals.append(p)
                elif chain.can_finish[j]:
                    onward.append((j, p))
            self.moves[i] = _Moves(tuple(goals), tuple(onward), fsum([*goals, *(p for _, p in onward)]))
        self.parts: dict[int, _Part] = {}
        self.attempts: dict[int, _Attempt] = {}

    def run(self, order: list[int]) -> _Part:
        for y in order:
            self.parts[y] = self._run(y)
        return self.parts[0]

    def _attempt(self, s: int) -> _Attempt:
        if s in self.attempts:
            return self.attempts[s]
        k = self.k[s]
        copies = [self.parts[y] for y in self.chain.inputs[s]]
        if not copies:
            attempt = _Attempt(k, DELTA, 1.0, 0.0)
        else:
            keep = max(self.horizon - k + 1, 0)
            extra, beyond = copies[0].pmf[:keep].copy(), fsum(copies[0].pmf[keep:].tolist())
            for c in copies[1:]:  # cut at every step: the mass that passes the horizon only adds to `beyond`
                if extra.size == 0:
                    beyond *= c.mass
                    continue
                full = np.convolve(extra, c.pmf)
                beyond = beyond * c.mass + fsum(full[keep:].tolist())
                extra = full[:keep]
                beyond += _clean(extra)
            extra = np.trim_zeros(extra, "b")
            if any(c.overflow > 0.0 for c in copies):
                beyond += max(0.0, prod(c.mass + c.overflow for c in copies) - prod(c.mass for c in copies))
            attempt = _Attempt(k, extra, fsum(extra.tolist()), beyond)
        self.attempts[s] = attempt
        return attempt

    def _run(self, start: int) -> _Part:
        chain, horizon, kmin = self.chain, self.horizon, self.kmin
        pmf = np.zeros(horizon + 1)
        if chain.goal[start]:
            pmf[0] = 1.0
            return _Part(pmf, 1.0, 0.0)
        arrivals = {start: np.zeros(horizon + 1)}
        arrivals[start][0] = 1.0
        overflow: list[float] = []
        last = 0
        lo = 0
        while lo <= min(last, horizon):
            hi = min(lo + kmin, horizon + 1)
            for s in list(arrivals):
                slice_ = arrivals[s][lo:hi]
                if not slice_.any():
                    continue
                overflow.append(_clean(slice_))
                attempt = self._attempt(s)
                moves = self.moves[s]
                mass = fsum(slice_.tolist())
                base = lo + attempt.k
                room = horizon - base + 1
                if room <= 0 or attempt.extra.size == 0:
                    overflow.append(moves.stay * mass * (attempt.inside + attempt.beyond))
                    continue
                conv = slice_ if attempt.extra is DELTA else np.convolve(slice_, attempt.extra)
                overflow.append(moves.stay * (fsum(conv[room:].tolist()) + mass * attempt.beyond))
                inside = conv[:room]
                last = max(last, base + inside.size - 1)
                for p in moves.goals:
                    pmf[base : base + inside.size] += p * inside
                for j, p in moves.onward:
                    if j not in arrivals:
                        arrivals[j] = np.zeros(horizon + 1)
                    arrivals[j][base : base + inside.size] += p * inside
            lo += kmin
        overflow.append(_clean(pmf))
        return _Part(pmf, fsum(pmf.tolist()), fsum(overflow))


def _stop(run: _Part, target: float | None, tail_mass: float) -> BudgetRun | None:
    """The result if the stop rule fires within the pass (or the pass is complete), else `None`."""
    pmf = run.pmf
    cdf = np.cumsum(pmf)
    bins = pmf.size
    if target is not None:
        reached = np.flatnonzero(cdf >= target + np.array([rounding_allowance(b) for b in range(bins)]))
        if reached.size:
            return _cut(run, cdf, int(reached[0]))
    else:
        after = np.append(np.cumsum(pmf[::-1])[::-1][1:], 0.0) + run.overflow
        for s in np.flatnonzero(after <= tail_mass).tolist():
            if fsum([*pmf[s + 1 :].tolist(), run.overflow]) <= tail_mass:
                return _cut(run, cdf, s)
    if run.overflow == 0.0:
        nonzero = np.flatnonzero(pmf)
        return _cut(run, cdf, int(nonzero[-1]) if nonzero.size else 0)
    return None


def _whole(run: _Part) -> BudgetRun:
    return _cut(run, np.cumsum(run.pmf), run.pmf.size - 1)


def _cut(run: _Part, cdf: np.ndarray, stop: int) -> BudgetRun:
    return BudgetRun(cdf[: stop + 1].tolist(), fsum([*run.pmf[stop + 1 :].tolist(), run.overflow]))
