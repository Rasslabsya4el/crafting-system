"""The exact lumping of a policy's chain on packed arrays (ticket #70, ADR-0063).

A fixed policy turns the (merged) graph into a Markov chain with a cost on every state. Two states can be told apart by nothing
the total cost sees when they pay the same and, for every block of a partition, move into that block with the same chance: then
the blocks form a chain of their own (ordinary lumpability) and the cost to reach a goal from a state has the very distribution
it has from its block. The coarsest such partition is found by refining it from "goal or not, and the cost paid" until no block
splits.

It is much smaller than the graph's own merge (`_packed_merge`), which asks for the same future under EVERY action: the chain of one
policy only has to agree on the action the policy takes. R04's optimal chain has 11,767 states and 17.1 million transitions (an
essence reroll leads to 4,034 states that differ in junk the policy never tells apart) and lumps to 552 blocks with 2,746
transitions; the budget DP of the risk run fits in memory on the blocks, not on the states.

Chances. A state's kernel is a list of successors with integer weights (a kernel whose weights do not fit 62 bits keeps them as Python
integers, `PackedGraph.k_big`; R04's essence rerolls are such). Under the block map the weights of the successors in one block add up, and
the state's chance into the block is that sum over the kernel's total. Two states have the same row exactly when these rationals agree for
every block. They are compared by their residues modulo two primes of 31 bits (the sum times the inverse of the total, modulo each), which
are equal for equal rationals and differ for different ones except with chance about 2**-62 per pair, hashed to one 128-bit signature per
kernel. The result is then checked against the float chances of the graph: every state's chance into every block must be its block's
within `CHECK_TOLERANCE`, so a collision or a bug cannot pass unnoticed. The kernels are read in chunks of at most `CHUNK_EDGES` edges,
so a route that visits ten times the classes of the optimal policy needs the memory of one chunk, not of all.

`lump_states` is the same refinement for any chain whose states share kernels, started from labels the caller gives (ticket #689): the route
page lumps the plan's item chain with the labels of its steps, and the chance of entering a step, a union of blocks, is solved on the blocks.

The generic part of `solver/`: nothing here knows the game. Uses numpy, so it is a `_packed*.py` file (ADR-0010 amended).
"""

from dataclasses import dataclass

import numpy as np

from ._packed import PackedGraph, expand_ranges
from ._packed_solve import policy_reach

CHUNK_EDGES = 4_000_000  # edges of the kernels handled at once
CHECK_TOLERANCE = 1e-12  # the most a state's chance into a block may differ from its block's (float division of equal integers)
PRIMES = (2_147_483_647, 2_147_483_629)  # two primes below 2**31: a product of two residues fits an int64


@dataclass(frozen=True, slots=True, eq=False)
class LumpedChain:
    """The lumped chain: block `b` pays `cost[b]` and moves to the blocks `succ[b]` with the integer weights `weight[b]` (Python integers).

    `goal[b]` blocks absorb (no successors). `block[c]` is the block of class `c` of the graph (-1 for a class the policy does not
    reach); `start` is the block of the start class; `rep[b]` is a class of the block (the first); `action[b]` is the graph action its
    representative takes (-1 for a goal); `deviation` is the largest difference found by the final check.
    """

    block: np.ndarray
    start: int
    goal: np.ndarray
    cost: np.ndarray
    action: np.ndarray
    rep: np.ndarray
    succ: tuple[np.ndarray, ...]
    weight: tuple[tuple[int, ...], ...]
    rounds: int
    deviation: float = 0.0

    @property
    def count(self) -> int:
        return len(self.goal)

    @property
    def transitions(self) -> int:
        return sum(len(s) for s in self.succ)


def _mix(block: np.ndarray, value: np.ndarray, seed: int) -> np.ndarray:
    """A 64-bit mix of (block, value) pairs (splitmix64 finalizer over a linear combination), as uint64."""
    with np.errstate(over="ignore"):
        z = block.astype(np.uint64) * np.uint64(0x9E3779B97F4A7C15) + value.astype(np.uint64) * np.uint64(0xC2B2AE3D27D4EB4F) + np.uint64(seed)
        z ^= z >> np.uint64(30)
        z *= np.uint64(0xBF58476D1CE4E5B9)
        z ^= z >> np.uint64(27)
        z *= np.uint64(0x94D049BB133111EB)
        z ^= z >> np.uint64(31)
    return z


def _inverse(value: np.ndarray, prime: int) -> np.ndarray:
    """`value ** -1 mod prime` for residues (0 for a residue that is 0), by square and multiply on int64 (a product of two residues fits)."""
    result = np.ones_like(value)
    base = value % prime
    exponent = prime - 2
    while exponent:
        if exponent & 1:
            result = result * base % prime
        base = base * base % prime
        exponent >>= 1
    return np.where(value % prime == 0, 0, result)


class _Rows:
    """The rows over blocks of the kernels the policy uses, read in chunks under one block map."""

    def __init__(self, graph: PackedGraph, kernels: np.ndarray) -> None:
        self.graph = graph
        self.kernels = kernels
        self.sizes = graph.kernel_sizes()[kernels]
        self.cum = np.concatenate(([0], np.cumsum(self.sizes)))
        self.big = {int(k): np.array([[w % p for w in graph.k_big[int(k)]] for p in PRIMES], dtype=np.int64) for k in kernels.tolist() if int(k) in graph.k_big}

    def chunks(self):
        """Ranges `(a, b)` of positions in `kernels` holding at most `CHUNK_EDGES` edges (one kernel at least)."""
        count = len(self.kernels)
        a = 0
        while a < count:
            b = int(np.searchsorted(self.cum, self.cum[a] + CHUNK_EDGES, side="right")) - 1
            b = min(max(b, a + 1), count)
            yield a, b
            a = b

    def residues(self, a: int, b: int, edge: np.ndarray):
        """The weights of the edges of kernels `a:b` modulo each prime (two int64 arrays)."""
        graph = self.graph
        weights = graph.k_wt[edge]
        out = [weights % p for p in PRIMES]
        if self.big:
            offset = 0
            for position in range(a, b):
                size = int(self.sizes[position])
                held = self.big.get(int(self.kernels[position]))
                if held is not None:
                    for i in range(len(PRIMES)):
                        out[i][offset : offset + size] = held[i]
                offset += size
        return out

    def groups(self, a: int, b: int, block_of_class: np.ndarray, count: int, values: list[np.ndarray] | None = None):
        """Per (kernel, block) of kernels `a:b`: `(kernel_starts, block, sums, totals)`, the sums of each array in `values` (default: the residues)."""
        graph = self.graph
        picked = self.kernels[a:b]
        sizes = self.sizes[a:b]
        edge = expand_ranges(graph.k_ptr[picked], sizes)
        owner = np.repeat(np.arange(b - a, dtype=np.int64), sizes)
        key = owner * count + block_of_class[graph.k_succ[edge]].astype(np.int64)
        order = np.argsort(key, kind="stable")
        key_sorted = key[order]
        starts = np.flatnonzero(np.concatenate(([True], key_sorted[1:] != key_sorted[:-1])))
        arrays = self.residues(a, b, edge) if values is None else [v[edge] for v in values]
        sums = [np.add.reduceat(array[order], starts) for array in arrays]
        group_key = key_sorted[starts]
        group_owner = group_key // count
        kernel_starts = np.flatnonzero(np.concatenate(([True], group_owner[1:] != group_owner[:-1])))
        totals = [np.add.reduceat(s, kernel_starts) for s in sums]
        return kernel_starts, group_key % count, sums, totals

    def signatures(self, block_of_class: np.ndarray, count: int) -> np.ndarray:
        """An id per kernel: equal for kernels with the same row (the same chances into every block), by a 128-bit signature."""
        n = len(self.kernels)
        h = [np.zeros(n, dtype=np.uint64) for _ in PRIMES]
        for a, b in self.chunks():
            kernel_starts, block, sums, totals = self.groups(a, b, block_of_class, count)
            lengths = np.diff(np.append(kernel_starts, len(block)))
            for i, prime in enumerate(PRIMES):
                inverse = _inverse(totals[i] % prime, prime)
                chance = (sums[i] % prime) * np.repeat(inverse, lengths) % prime
                h[i][a:b] = np.add.reduceat(_mix(block, chance, 0x1234567 + i), kernel_starts) + _mix(lengths, lengths, 0x2468ACE + i)
        order = np.lexsort((h[1], h[0]))
        same = (h[0][order][1:] == h[0][order][:-1]) & (h[1][order][1:] == h[1][order][:-1])
        ids = np.zeros(n, dtype=np.int64)
        ids[order[1:]] = np.cumsum(~same)
        return ids

    def deviation(self, block_of_class: np.ndarray, count: int, slot_of_state: np.ndarray, block_of_state: np.ndarray, succ, chance) -> float:
        """The largest difference between the chance of a state into a block and its block's chance, over all states that act.

        `slot_of_state[i]` is the position in `kernels` of the kernel state `i` uses (-1 for none) and `block_of_state[i]` its block;
        `succ[b]` and `chance[b]` are the block's row as blocks and float chances. A row that goes to other blocks than its block's differs by 1.
        """
        worst = 0.0
        wanted = np.flatnonzero(slot_of_state >= 0)
        pairs = np.unique(np.stack([slot_of_state[wanted], block_of_state[wanted]], axis=1), axis=0)
        by_slot = pairs[np.argsort(pairs[:, 0], kind="stable")]
        position = 0
        for a, b in self.chunks():
            kernel_starts, block, sums, _ = self.groups(a, b, block_of_class, count, values=[self.graph.k_prob])
            ends = np.append(kernel_starts, len(block))
            while position < len(by_slot) and by_slot[position, 0] < b:
                slot, owner_block = int(by_slot[position, 0]), int(by_slot[position, 1])
                position += 1
                k = slot - a
                low, high = int(ends[k]), int(ends[k + 1])
                if not np.array_equal(block[low:high], succ[owner_block]):
                    return 1.0
                if high > low:
                    worst = max(worst, float(np.abs(sums[0][low:high] - chance[owner_block]).max()))
        return worst


def _settle(rows: _Rows, slot: np.ndarray, block: np.ndarray, block_of: np.ndarray, where, max_rounds: int) -> tuple[np.ndarray, int, int]:
    """`(block, count, rounds)`: the partition `block` of the states `where` refined until no block splits.

    `slot[i]` is the position in `rows.kernels` of the kernel state `i` moves by (-1: none); `block_of` is the map from the kernels' successors to
    their blocks, written here (successors outside `where` keep what it holds).
    """
    count = int(block.max()) + 1
    rounds = 0
    while True:
        rounds += 1
        block_of[where] = block
        ids = rows.signatures(block_of, count)
        sig = np.where(slot >= 0, ids[np.maximum(slot, 0)], -1)
        _, new = np.unique(np.stack([block, sig], axis=1), axis=0, return_inverse=True)
        new = new.reshape(-1).astype(np.int64)
        grown = int(new.max()) + 1
        if grown == count:
            break
        if rounds >= max_rounds:
            raise ValueError(f"the lumping did not settle in {max_rounds} rounds")
        block, count = new, grown
    block_of[where] = block
    return block, count, rounds


def lump_states(table, slot: np.ndarray, label: np.ndarray, *, max_rounds: int = 10_000) -> np.ndarray:
    """The block of every state in the coarsest lumping of a chain that keeps states of different `label` apart (ticket #689).

    State `i` moves by kernel `slot[i]` of `table` (anything with the kernel arrays of `PackedGraph`: `k_ptr`, `k_succ`, `k_wt`, `k_prob`,
    `k_big`, `kernel_sizes()`), whose successors are state numbers, or stops there when `slot[i] < 0` (a goal or a dead end: give them labels
    of their own). The states are `0..len(slot) - 1`; the kernels are read once per round whatever the number of states that share them.
    The blocks are numbered by the first state of each. Checked like `lump_policy`: raises `ValueError` when a state's chance into a block
    differs from its block's by more than `CHECK_TOLERANCE`, or when the refinement does not settle in `max_rounds`.
    """
    n = len(slot)
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    taking = slot >= 0
    _, first = np.unique(np.asarray(label), return_inverse=True)
    if not taking.any():  # nothing moves: the labels are the blocks
        first = first.reshape(-1).astype(np.int64)
        rep = np.full(int(first.max()) + 1, n, dtype=np.int64)
        np.minimum.at(rep, first, np.arange(n))
        renumber = np.empty(len(rep), dtype=np.int64)
        renumber[np.argsort(rep, kind="stable")] = np.arange(len(rep))
        return renumber[first]
    used = np.unique(slot[taking])
    rows = _Rows(table, used)
    position = np.full(int(used.max()) + 1, -1, dtype=np.int64)
    position[used] = np.arange(len(used))
    at = np.where(taking, position[np.maximum(slot, 0)], -1)
    block_of = np.full(n, -1, dtype=np.int64)
    block, count, _ = _settle(rows, at, first.reshape(-1).astype(np.int64), block_of, slice(None), max_rounds)
    rep = np.full(count, n, dtype=np.int64)
    np.minimum.at(rep, block, np.arange(n))
    succ: list[np.ndarray] = []
    chance: list[np.ndarray] = []
    for b in range(count):
        k = int(slot[rep[b]])
        if k < 0:
            succ.append(np.zeros(0, dtype=np.int64))
            chance.append(np.zeros(0))
            continue
        lo, hi = int(table.k_ptr[k]), int(table.k_ptr[k + 1])
        target = block[table.k_succ[lo:hi]]
        order = np.argsort(target, kind="stable")
        ts = target[order]
        starts = np.flatnonzero(np.concatenate(([True], ts[1:] != ts[:-1])))
        succ.append(ts[starts])
        chance.append(np.add.reduceat(table.k_prob[lo:hi][order], starts))
    deviation = rows.deviation(block_of, count, at, block, succ, chance)
    if deviation > CHECK_TOLERANCE:
        raise ValueError(f"the lumped chain disagrees with a state it stands for by {deviation:.3g} in chance: the lumping cannot be trusted")
    renumber = np.empty(count, dtype=np.int64)
    renumber[np.argsort(rep, kind="stable")] = np.arange(count)
    return renumber[block]


def lump_policy(graph: PackedGraph, action: np.ndarray, start: int, *, max_rounds: int = 10_000) -> LumpedChain:
    """The coarsest lumping of the chain of policy `action` (an action index of `graph` per state, -1 for none) from `start`.

    A state with no action that is not a goal (a dead end) stays a block of its own kind: it is a block without successors that is
    not a goal. Raises `ValueError` when the final check finds a state whose chances differ from its block's by more than
    `CHECK_TOLERANCE`, or when the refinement does not settle in `max_rounds`.
    """
    reached = policy_reach(graph, action, start)
    acts = action[reached]
    taking = acts >= 0
    if not taking.any():  # nothing to do anywhere (the start already is a goal): one block
        block_of_class = np.full(graph.n, -1, dtype=np.int64)
        block_of_class[reached] = 0
        return LumpedChain(
            block_of_class, 0, graph.goal[reached][:1], np.zeros(1), np.full(1, -1, dtype=np.int64), reached[:1],
            (np.zeros(0, dtype=np.int64),), ((),), 0,
        )  # fmt: skip
    used = np.unique(graph.act_kernel[acts[taking]])
    rows = _Rows(graph, used)
    kernel_slot = np.full(graph.num_kernels, -1, dtype=np.int64)
    kernel_slot[used] = np.arange(len(used))
    cost = np.where(taking, graph.act_cost[np.maximum(acts, 0)], 0.0)
    kind = np.where(graph.goal[reached], 1, np.where(taking, 0, 2))  # 1 goal, 2 dead end
    _, first = np.unique(np.stack([kind.astype(np.float64), cost], axis=1), axis=0, return_inverse=True)
    slot = np.where(taking, kernel_slot[graph.act_kernel[np.maximum(acts, 0)]], -1)
    on_class = np.full(graph.n, -1, dtype=np.int64)  # class -> block, for the classes reached
    block, count, rounds = _settle(rows, slot, first.reshape(-1).astype(np.int64), on_class, reached, max_rounds)
    rep_index = np.full(count, len(reached), dtype=np.int64)
    np.minimum.at(rep_index, block, np.arange(len(reached)))
    rep = reached[rep_index]
    rep_action = action[rep]
    goal = graph.goal[rep]
    succ: list[np.ndarray] = []
    weight: list[tuple[int, ...]] = []
    chance: list[np.ndarray] = []
    for b in range(count):
        a = int(rep_action[b])
        if a < 0 or goal[b]:
            succ.append(np.zeros(0, dtype=np.int64))
            weight.append(())
            chance.append(np.zeros(0))
            continue
        kernel = int(graph.act_kernel[a])
        lo, hi = int(graph.k_ptr[kernel]), int(graph.k_ptr[kernel + 1])
        target = on_class[graph.k_succ[lo:hi]]
        order = np.argsort(target, kind="stable")
        ts = target[order]
        starts = np.flatnonzero(np.concatenate(([True], ts[1:] != ts[:-1])))
        succ.append(ts[starts])
        chance.append(np.add.reduceat(graph.k_prob[lo:hi][order], starts))
        weights = graph.kernel_weights(kernel)  # Python integers, the exact ones
        summed: dict[int, int] = {}
        for t, w in zip(target.tolist(), weights):
            summed[t] = summed.get(t, 0) + w
        weight.append(tuple(summed[t] for t in ts[starts].tolist()))
    deviation = rows.deviation(on_class, count, slot, block, succ, chance)
    if deviation > CHECK_TOLERANCE:
        raise ValueError(f"the lumped chain disagrees with a state it stands for by {deviation:.3g} in chance: the lumping cannot be trusted")
    out_cost = np.where(rep_action >= 0, graph.act_cost[np.maximum(rep_action, 0)], 0.0)
    block_of_class = np.full(graph.n, -1, dtype=np.int64)
    block_of_class[reached] = block
    return LumpedChain(block_of_class, int(on_class[start]), goal, out_cost, rep_action, rep, tuple(succ), tuple(weight), rounds, deviation)


__all__ = ["LumpedChain", "lump_policy", "lump_states"]
