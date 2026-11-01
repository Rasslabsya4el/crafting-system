"""The budget DP: the distribution of the total cost on a grid, for the chain of a fixed policy.

Costs are floats, so cost is counted in whole steps of a grid step D. Every state that can still
finish pays a positive whole number of bins `k`, which makes the dependency of (state, bins paid)
on earlier bins acyclic even when the state graph has cycles. The DP is forward: an entry
(bins paid `b`, state, mass) is popped, and its mass moves `k` bins ahead: the part that reaches a
goal is added to the absorbed mass `pmf[b + k]`, the part that stays on a state that can still
finish becomes entries at `b + k`, and the part that goes to a stuck or trapped state is lost.
Mass that would land above the cap `max_bins` is not stored; it is counted as unresolved. An
entry is processed once, so the work is O(entries) with one entry per reachable (bins paid,
state) pair, and the memory is the entries in flight (at most the longest move, in bins, ahead)
plus O(bins) floats for the cumulative distribution that quantiles and CVaR are read from.

Vectorised in blocks (ADR-0010, ticket #82). `kmin` is the smallest bin cost of a state that can
finish, so mass popped at bin b lands at b + kmin or later and the bins [q kmin, (q + 1) kmin)
(block q) do not depend on each other. Pending entries are numpy arrays of keys
`bin << shift | state` and masses, kept as chunks per destination block. A block is processed at
once: its chunks are concatenated, equal keys are merged (a dense `bincount` over the block's
range when it is not much wider than the number of entries, else a sort and a segmented sum),
and the entries are expanded along the onward edges of the policy (a CSR of the chain) with
`repeat` and gathers. Blocks with no entries are skipped. The result equals the plain bin by bin
DP up to the float rounding of the order of additions. A chain of few states and bins of one or a
few steps has too little work per block for numpy to pay; it runs the plain bin by bin loop
(`_run_plain`, a dict per bin), which gives the same answer.

The run stops when the target is met (proper policy: the cumulative absorbed mass reaches the
highest asked level plus the rounding allowance; otherwise: the mass still in flight is at most
`tail_mass`), when the cap is reached, or when no mass is left. The stop is searched at the bins
`s` that are final: with `e` the earliest bin of an entry not yet processed, the lost mass of the
sources below `e` and the absorbed mass `pmf[s]` for `s <= e` no longer change, so the rules are
evaluated for those `s` (vectorised, the first bin that meets one wins). It never truncates
silently: `unresolved` is the probability still in flight at the stop `s`, i.e. what is neither in
`cdf[s]` nor lost from a source below `s`: the absorbed mass after `s`, the lost mass of the
sources from `s` on, the mass that overflowed the cap and the masses of the entries not yet
processed. So the absorbed mass and the absorbed mass plus the unresolved mass bracket the
success probability of the chain. It is summed from those parts (`fsum`), not found by
subtraction, so it is exactly 0.0 when nothing is left.

No entry is dropped. A profile of wide generated policies (1,000 states, 11.6M entries) found no
dust to prune: the median entry holds 7e-7 of mass, and a pruning budget of 1e-6 in total would
drop 0.8% of the entries (1e-9: 0.1%), because the entries are a broad cloud over (state, bin)
pairs. So there is no pruned mass to add to the rounding allowance and the bounds stay as they
were.

Rounding. The cumulative F is a running float sum, so each F(i) carries an error of a few eps per
bin run. `delta = 1e-12 + 4 eps bins` is the allowance: "level L reached" means F >= L - delta at
the low end of an interval and F >= L + delta at the high end. All bounds therefore hold up to
ties within delta in probability.
"""

import heapq
import sys
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from math import fsum

import numpy as np

from ._chain import Chain

EPS = sys.float_info.epsilon
BASE_DELTA = 1e-12
LOST_FLOOR = 1e-15  # a smaller remainder of the starting mass is float noise, not lost mass
PLAIN_LIMIT = 300  # a chain with at most this many (states that can finish) * kmin runs the plain loop
SLICE_ENTRIES = 1 << 14  # a block is expanded this many entries at a time: arrays that stay in the CPU cache
DENSE_CELLS = 1 << 24  # the widest block range merged by a dense bincount (a float per cell)
DENSE_RATIO = 32  # ... and only when it has at most this many cells per entry; a sort is cheaper otherwise


def rounding_allowance(bins: int) -> float:
    return BASE_DELTA + 4.0 * EPS * bins


@dataclass(frozen=True, slots=True)
class BudgetRun:
    """`cdf[i]` is P(grid cost <= i bins) for i = 0..bins; `unresolved` is the mass still in flight."""

    cdf: list[float]
    unresolved: float

    @property
    def bins(self) -> int:
        return len(self.cdf) - 1

    @property
    def absorbed(self) -> float:
        return self.cdf[-1]

    @property
    def delta(self) -> float:
        return rounding_allowance(self.bins)

    def first_reaching(self, threshold: float) -> int | None:
        """The first bin count whose cumulative mass is at least `threshold`, or `None` if the run never got there."""
        i = bisect_left(self.cdf, threshold)
        return i if i < len(self.cdf) else None


def run_budget(
    chain: Chain,
    bin_cost: Sequence[int],
    *,
    target: float | None,
    tail_mass: float,
    max_bins: int,
    initial: Sequence[tuple[int, float]] | None = None,
    goal_mass: float = 0.0,
) -> BudgetRun:
    """Run the DP with `bin_cost[i]` whole bins per step in state i.

    `target` is the highest level to certify (a proper policy) or `None` to run until the mass
    in flight is at most `tail_mass`. The run starts from state 0 with mass 1, or, with `initial`, from
    the given (state, mass) pairs at bin 0 (states that can finish and have an action) with `goal_mass`
    already absorbed there; what is left of 1 is lost at bin 0 (the start of a chain whose free states
    were folded away, `_fold`).
    """
    finishing = chain.finishing_states()
    if not finishing or not chain.can_finish[0]:
        raise ValueError("the start state cannot finish: there is no distribution to compute")
    kmin = min(bin_cost[i] for i in finishing)
    if kmin < 1:
        raise ValueError(f"every state that can finish must cost at least one bin, got {kmin!r}")
    if initial is not None:
        initial = tuple(initial)
        expanded = set(finishing)
        for state, _ in initial:
            if state not in expanded:
                raise ValueError(f"initial state {state!r} cannot finish: it is not a state the DP moves")
    if len(finishing) * kmin <= PLAIN_LIMIT:
        return _run_plain(chain, bin_cost, target, tail_mass, max_bins, initial, goal_mass)
    return _Dp(chain, finishing, bin_cost, target, tail_mass, max_bins, initial, goal_mass).run()


def _run_plain(
    chain: Chain,
    bin_cost: Sequence[int],
    target: float | None,
    tail_mass: float,
    max_bins: int,
    initial: Sequence[tuple[int, float]] | None = None,
    goal_mass: float = 0.0,
) -> BudgetRun:
    """The bin by bin DP on dicts: quicker than numpy when a bin holds only a few entries."""
    moves: dict[int, tuple[float, list[tuple[int, float]], float, float]] = {}
    for i in chain.finishing_states():
        absorbed = 0.0
        onward: list[tuple[int, float]] = []
        lost = 0.0
        for j, p in chain.succ[i]:
            if chain.goal[j]:
                absorbed += p
            elif chain.can_finish[j]:
                onward.append((j, p))
            else:
                lost += p
        moves[i] = (absorbed, onward, lost, absorbed + fsum(p for _, p in onward))

    pending: dict[int, dict[int, float]] = {0: {0: 1.0}}
    pmf = [0.0]
    lost_total = 0.0
    if initial is not None:
        pending = {0: {}}
        for state, mass in initial:
            pending[0][state] = pending[0].get(state, 0.0) + mass
        pmf = [goal_mass]
        remainder = 1.0 - goal_mass - fsum(mass for _, mass in initial)
        lost_total = remainder if remainder > LOST_FLOOR else 0.0
    cdf: list[float] = []
    overflow = 0.0
    running = 0.0
    b = 0
    while True:
        if b < len(pmf):
            running += pmf[b]
        cdf.append(running)
        if b >= max_bins or (not pending and b + 1 >= len(pmf)):
            break
        if target is not None:
            if running >= target + rounding_allowance(b):
                break
        elif 1.0 - lost_total - running <= tail_mass:
            break
        for i, mass in pending.pop(b, {}).items():
            absorbed, onward, lost, stay = moves[i]
            lost_total += mass * lost
            ahead = b + bin_cost[i]
            if ahead > max_bins:
                overflow += mass * stay
                continue
            if absorbed:
                if ahead >= len(pmf):
                    pmf.extend([0.0] * (ahead + 1 - len(pmf)))
                pmf[ahead] += mass * absorbed
            if onward:
                slot = pending.setdefault(ahead, {})
                for j, p in onward:
                    slot[j] = slot.get(j, 0.0) + mass * p
        b += 1
    unresolved = fsum(m for slot in pending.values() for m in slot.values()) + fsum(pmf[b + 1 :]) + overflow
    return BudgetRun(cdf, unresolved)


@dataclass(frozen=True, slots=True)
class _Moves:
    """The chain as arrays: per state its bins, the split of its mass and the CSR of its onward edges.

    `absorbed` goes to a goal, `lost` to a stuck or trapped state, `stay` is `absorbed` plus the
    onward probabilities (what leaves the state toward something that can still finish), and
    the edges `first[i]:first[i + 1]` of `dst` / `prob` are the onward ones. `kmin` is the
    smallest `k` of a state that can finish.
    """

    k: np.ndarray
    absorbed: np.ndarray
    lost: np.ndarray
    stay: np.ndarray
    degree: np.ndarray
    first: np.ndarray
    dst: np.ndarray
    prob: np.ndarray
    kmin: int


def _moves(chain: Chain, finishing: Sequence[int], bin_cost: Sequence[int], max_bins: int) -> _Moves:
    n = len(chain.states)
    k = np.zeros(n, dtype=np.int64)
    absorbed = np.zeros(n)
    lost = np.zeros(n)
    stay = np.zeros(n)
    degree = np.zeros(n, dtype=np.int64)
    dst: list[int] = []
    prob: list[float] = []
    kmin = max_bins + 1
    for i in finishing:
        gone = 0.0
        goal = 0.0
        onward: list[float] = []
        for j, p in chain.succ[i]:
            if chain.goal[j]:
                goal += p
            elif chain.can_finish[j]:
                dst.append(j)
                prob.append(p)
                onward.append(p)
            else:
                gone += p
        bins = min(bin_cost[i], max_bins + 1)  # a move past the cap overflows, however long it is
        kmin = min(kmin, bins)
        k[i] = bins
        absorbed[i], lost[i], stay[i], degree[i] = goal, gone, goal + fsum(onward), len(onward)
    first = np.zeros(n + 1, dtype=np.int64)
    np.cumsum(degree, out=first[1:])
    return _Moves(k, absorbed, lost, stay, degree, first, np.asarray(dst, dtype=np.int64), np.asarray(prob), kmin)


class _Pending:
    """Entries not yet processed: chunks of (key, mass) per block of `kmin` bins, `key = bin << shift | state`."""

    def __init__(self, kmin: int, shift: int) -> None:
        self.kmin = kmin
        self.shift = shift
        self.chunks: dict[int, list[tuple[np.ndarray, np.ndarray]]] = {}
        self.floor: dict[int, int] = {}  # the smallest bin of each block
        self.heap: list[int] = []  # the blocks that have chunks

    def add(self, keys: np.ndarray, mass: np.ndarray) -> None:
        """Store entries, given as the key and the mass of each."""
        if keys.size == 0:
            return
        bins = keys >> self.shift
        blocks = bins if self.kmin == 1 else bins // self.kmin
        lo, hi = int(blocks.min()), int(blocks.max())
        if lo == hi:
            self._put(lo, int(bins.min()), keys, mass)
            return
        relative = blocks - lo
        narrow = relative.astype(np.int16) if hi - lo < 32000 else relative  # int16 sorts by radix
        order = np.argsort(narrow, kind="stable")
        ends = np.cumsum(np.bincount(relative, minlength=hi - lo + 1)).tolist()
        keys, mass = keys[order], mass[order]
        start = 0
        for step, end in enumerate(ends):
            if end > start:
                group = keys[start:end]
                self._put(lo + step, int(group.min()) >> self.shift, group, mass[start:end])
            start = end

    def _put(self, block: int, floor: int, keys: np.ndarray, mass: np.ndarray) -> None:
        if block in self.chunks:
            self.chunks[block].append((keys, mass))
            self.floor[block] = min(self.floor[block], floor)
        else:
            self.chunks[block] = [(keys, mass)]
            self.floor[block] = floor
            heapq.heappush(self.heap, block)

    def earliest(self) -> int | None:
        """The smallest bin of an entry not yet processed."""
        return self.floor[self.heap[0]] if self.heap else None

    def pop(self) -> tuple[int, np.ndarray, np.ndarray]:
        """The earliest block and its entries as `(block, keys, mass)`, equal keys not merged."""
        block = heapq.heappop(self.heap)
        del self.floor[block]
        chunks = self.chunks.pop(block)
        if len(chunks) == 1:
            return block, chunks[0][0], chunks[0][1]
        return block, np.concatenate([c[0] for c in chunks]), np.concatenate([c[1] for c in chunks])

    def mass(self) -> float:
        return fsum(float(m.sum()) for chunks in self.chunks.values() for _, m in chunks)


def _merge(keys: np.ndarray, mass: np.ndarray, base: int, cells: int) -> tuple[np.ndarray, np.ndarray]:
    """The sorted distinct keys of a block and the summed mass of each.

    The keys lie in `[base, base + cells)`. A range that is not much wider than the number of
    entries is summed in place by `bincount`; otherwise the entries are sorted.
    """
    if cells <= DENSE_CELLS and cells <= DENSE_RATIO * keys.size:
        total = np.bincount(keys - base, weights=mass, minlength=cells)
        index = np.flatnonzero(total)
        return index + base, total[index]
    order = np.argsort(keys)
    keys, mass = keys[order], mass[order]
    new = np.empty(keys.size, dtype=bool)
    new[0] = True
    np.not_equal(keys[1:], keys[:-1], out=new[1:])
    starts = np.flatnonzero(new)
    if starts.size == keys.size:
        return keys, mass
    return keys[starts], np.add.reduceat(mass, starts)


def _grown(array: np.ndarray, size: int) -> np.ndarray:
    if array.size >= size:
        return array
    bigger = np.zeros(max(size, 2 * array.size))
    bigger[: array.size] = array
    return bigger


class _Dp:
    def __init__(
        self,
        chain: Chain,
        finishing: Sequence[int],
        bin_cost: Sequence[int],
        target: float | None,
        tail_mass: float,
        max_bins: int,
        initial: Sequence[tuple[int, float]] | None = None,
        goal_mass: float = 0.0,
    ) -> None:
        self.shift = max(1, (len(chain.states) - 1).bit_length())  # key = bin << shift | state
        if (max_bins + 1).bit_length() + self.shift > 62:
            raise ValueError(f"max_bins {max_bins!r} is too large for {len(chain.states)} states: a key must fit 62 bits")
        self.moves = _moves(chain, finishing, bin_cost, max_bins)
        self.target = target
        self.tail_mass = tail_mass
        self.max_bins = max_bins
        self.any_lost = bool(self.moves.lost.any())
        self.pending = _Pending(self.moves.kmin, self.shift)
        self.pmf = np.zeros(1024)  # absorbed mass per bin
        self.lost = np.zeros(1024)  # mass lost from the sources of each bin
        if initial is None:
            self.pending.add(np.zeros(1, dtype=np.int64), np.ones(1))
        else:
            self.pending.add(
                np.asarray([state for state, _ in initial], dtype=np.int64), np.asarray([mass for _, mass in initial], dtype=float)
            )
            self.pmf[0] = goal_mass
            remainder = 1.0 - goal_mass - fsum(mass for _, mass in initial)
            self.lost[0] = remainder if remainder > LOST_FLOOR else 0.0
        self.pmf_end = 1  # one past the last bin an absorbing move has reached
        self.last = -1  # the last bin with a processed entry
        self.overflow = 0.0  # mass whose move would end above the cap
        self.held = 0.0  # mass of the entries at the cap: they are never processed
        self.checked = 0  # the bins below it have their cdf
        self.running = 0.0  # the cdf at `checked - 1`
        self.lost_sum = 0.0  # the lost mass of the sources below `lost_at`
        self.lost_at = 0

    def run(self) -> BudgetRun:
        parts: list[np.ndarray] = []
        while True:
            earliest = self.pending.earliest()
            if self.held > 0.0:
                earliest = self.max_bins if earliest is None else min(earliest, self.max_bins)
            quiet = earliest is None
            if quiet:
                final = min(self.max_bins, max(self.last + 1, self.pmf_end - 1))
            else:
                final = earliest
            stop = self._scan(max(final, self.checked), quiet, parts)
            if stop is not None:
                break
            self._process()
        cdf = np.concatenate(parts)[: stop + 1]
        return BudgetRun(cdf.tolist(), self._unresolved(stop))

    def _scan(self, hi: int, quiet: bool, parts: list[np.ndarray]) -> int | None:
        """Evaluate the stop rules at the bins `checked..hi`; return the first bin that stops the run."""
        lo = self.checked
        self.pmf = _grown(self.pmf, hi + 1)
        self.lost = _grown(self.lost, hi + 1)
        window = self.pmf[lo : hi + 1].copy()
        window[0] += self.running
        running = np.cumsum(window)
        losses = self.lost[self.lost_at : hi].copy()
        if losses.size:
            losses[0] += self.lost_sum
            prefix = np.concatenate(([self.lost_sum], np.cumsum(losses)))
        else:
            prefix = np.array([self.lost_sum])
        before = prefix[lo - self.lost_at :]  # the lost mass of the sources below each bin
        bins = np.arange(lo, hi + 1)
        stop = bins >= self.max_bins
        if quiet:
            stop |= (bins > self.last) & (bins + 1 >= self.pmf_end)
        if self.target is not None:
            stop |= running >= self.target + (BASE_DELTA + 4.0 * EPS * bins)
        else:
            stop |= (1.0 - before - running) <= self.tail_mass
        if stop.any():
            index = int(np.argmax(stop))
            parts.append(running[: index + 1])
            return lo + index
        parts.append(running)
        self.running = float(running[-1])
        self.lost_sum, self.lost_at = float(prefix[-1]), hi
        self.checked = hi + 1
        return None

    def _process(self) -> None:
        kmin, shift = self.moves.kmin, self.shift
        block, keys, mass = self.pending.pop()
        keys, mass = _merge(keys, mass, (block * kmin) << shift, kmin << shift)
        bins = keys >> shift
        states = keys & ((1 << shift) - 1)
        live = bins < self.max_bins
        if not live.all():
            self.held += float(mass[~live].sum())
            bins, states, mass = bins[live], states[live], mass[live]
        if bins.size == 0:
            return
        self.last = max(self.last, int(bins[-1]))
        self.lost = _grown(self.lost, int(bins[-1]) + 1)
        for a in range(0, bins.size, SLICE_ENTRIES):
            self._expand(bins[a : a + SLICE_ENTRIES], states[a : a + SLICE_ENTRIES], mass[a : a + SLICE_ENTRIES])

    def _expand(self, bins: np.ndarray, states: np.ndarray, mass: np.ndarray) -> None:
        moves = self.moves
        if self.any_lost:
            low = int(bins[0])
            gone = np.bincount(bins - low, weights=mass * moves.lost[states])
            self.lost[low : low + gone.size] += gone
        ahead = bins + moves.k[states]
        over = ahead > self.max_bins
        if over.any():
            self.overflow += float((mass[over] * moves.stay[states[over]]).sum())
            keep = ~over
            states, mass, ahead = states[keep], mass[keep], ahead[keep]
        share = moves.absorbed[states]
        reaching = share > 0.0
        if reaching.any():
            landing = ahead[reaching]
            first, end = int(landing.min()), int(landing.max())
            got = np.bincount(landing - first, weights=mass[reaching] * share[reaching])
            self.pmf = _grown(self.pmf, end + 1)
            self.pmf[first : first + got.size] += got
            self.pmf_end = max(self.pmf_end, end + 1)
        degree = moves.degree[states]
        moving = degree > 0
        if not moving.any():
            return
        if not moving.all():
            states, mass, ahead, degree = states[moving], mass[moving], ahead[moving], degree[moving]
        total = int(degree.sum())
        offsets = np.cumsum(degree) - degree
        edge = np.repeat(moves.first[states] - offsets, degree)
        edge += np.arange(total)
        new_keys = np.repeat(ahead << self.shift, degree)
        new_keys |= moves.dst[edge]
        new_mass = np.repeat(mass, degree)
        new_mass *= moves.prob[edge]
        self.pending.add(new_keys, new_mass)

    def _unresolved(self, stop: int) -> float:
        """What is in flight at `stop`: the absorbed mass after it, the lost mass of the sources from it on, and what was never moved."""
        return fsum(
            (
                fsum(self.pmf[stop + 1 : self.pmf_end].tolist()),
                fsum(self.lost[stop : self.last + 1].tolist()),
                self.overflow,
                self.held,
                self.pending.mass(),
            )
        )


def tail_mean(run: BudgetRun, step: float, level: float, mean: float) -> tuple[float, float, float] | None:
    """`(cvar, t, allowance)` of the grid cost at `level`, or `None` when the run never reached the level.

    Rockafellar-Uryasev: CVaR = t + (E[X] - E[min(X, t)]) / (1 - level) at t, the quantile, with
    E[min(X, t)] = step * sum_{i < k} (1 - F(i)) for t = k * step (atoms at t are handled). `mean`
    is E[X]. `allowance` is the outward widening for the rounding of F, delta * (t + E[X]) / (1 - level).
    """
    k = run.first_reaching(level - run.delta)
    if k is None:
        return None
    t = k * step
    clipped = step * fsum(1.0 - run.cdf[i] for i in range(k))
    allowance = run.delta * (t + mean) / (1.0 - level)
    return t + (mean - clipped) / (1.0 - level), t, allowance
