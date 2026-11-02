"""The exact lumping of a policy's chain on packed arrays (ticket #70, ADR-0063).

A fixed policy turns the (merged) graph into a Markov chain with a cost on every state. Two states can be told apart by nothing
the total cost sees when they pay the same and, for every block of a partition, move into that block with the same chance: then
the blocks form a chain of their own (ordinary lumpability) and the cost to reach a goal from a state has the very distribution
it has from its block. The coarsest such partition is found by refining it from "goal or not, and the cost paid" until no block
splits. The chances are integers, compared as integers (reduced by their common divisor), and a final pass checks every state's row
against its block's row (`CHECK_TOLERANCE`), so a hash collision or a bug cannot pass unnoticed.

It is much smaller than the graph's own merge (`_packed_merge`), which asks for the same future under EVERY action: the chain of one
policy only has to agree on the action the policy takes. R04's optimal chain has 11,767 states and 17.1 million transitions (an
essence reroll leads to 4,034 states that differ in junk the policy never tells apart) and lumps to 552 blocks with 2,746
transitions; the budget DP of the risk run fits in memory on the blocks, not on the states.

Chances. A state's kernel is a list of successors with integer weights. Under the block map, the weights of the successors in one
block add up, and the state's row over blocks is (block, summed weight) pairs with a total. Two rows are the same distribution
exactly when they are the same pairs after dividing every summed weight and the total by their common divisor. A kernel whose
weights do not fit 62 bits (`PackedGraph.k_big`) is not handled: `lump_policy` returns None and the caller keeps the chain whole.
The kernels are read in chunks of at most `CHUNK_EDGES` edges, so a route that visits ten times the classes of the optimal policy
(its kernels hold 100 million edges) needs the memory of one chunk, not of all.

The generic part of `solver/`: nothing here knows the game. Uses numpy, so it is a `_packed*.py` file (ADR-0010 amended).
"""

from dataclasses import dataclass

import numpy as np

from ._packed import PackedGraph, expand_ranges
from ._packed_solve import policy_reach

CHUNK_EDGES = 4_000_000  # edges of the kernels handled at once
CHECK_TOLERANCE = 1e-12  # the most a state's chance into a block may differ from its block's (float division of equal integers)


@dataclass(frozen=True, slots=True, eq=False)
class LumpedChain:
    """The lumped chain: block `b` pays `cost[b]` and moves to the blocks `succ[b]` with the integer weights `weight[b]`.

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
    weight: tuple[np.ndarray, ...]
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


class _Rows:
    """The rows over blocks of the kernels the policy uses, read in chunks under one block map."""

    def __init__(self, graph: PackedGraph, kernels: np.ndarray) -> None:
        self.graph = graph
        self.kernels = kernels
        self.sizes = graph.kernel_sizes()[kernels]
        self.cum = np.concatenate(([0], np.cumsum(self.sizes)))

    def chunks(self):
        """Ranges `(a, b)` of positions in `kernels` holding at most `CHUNK_EDGES` edges (one kernel at least)."""
        count = len(self.kernels)
        a = 0
        while a < count:
            b = int(np.searchsorted(self.cum, self.cum[a] + CHUNK_EDGES, side="right")) - 1
            b = min(max(b, a + 1), count)
            yield a, b
            a = b

    def groups(self, a: int, b: int, block_of_class: np.ndarray, count: int):
        """`(kernel_starts, block, summed weight, total)` of kernels `a:b`: per (kernel, block) the summed weight, per kernel its total."""
        graph = self.graph
        picked = self.kernels[a:b]
        sizes = self.sizes[a:b]
        edge = expand_ranges(graph.k_ptr[picked], sizes)
        owner = np.repeat(np.arange(b - a, dtype=np.int64), sizes)
        key = owner * count + block_of_class[graph.k_succ[edge]].astype(np.int64)
        order = np.argsort(key, kind="stable")
        key_sorted = key[order]
        starts = np.flatnonzero(np.concatenate(([True], key_sorted[1:] != key_sorted[:-1])))
        summed = np.add.reduceat(graph.k_wt[edge][order], starts)
        group_key = key_sorted[starts]
        group_owner = group_key // count
        kernel_starts = np.flatnonzero(np.concatenate(([True], group_owner[1:] != group_owner[:-1])))
        total = np.add.reduceat(summed, kernel_starts)
        return kernel_starts, group_key % count, summed, total

    def signatures(self, block_of_class: np.ndarray, count: int) -> np.ndarray:
        """An id per kernel: equal for kernels with the same row (the same pairs once divided by their common divisor), by a 128-bit hash."""
        n = len(self.kernels)
        h1 = np.zeros(n, dtype=np.uint64)
        h2 = np.zeros(n, dtype=np.uint64)
        for a, b in self.chunks():
            kernel_starts, block, summed, total = self.groups(a, b, block_of_class, count)
            lengths = np.diff(np.append(kernel_starts, len(block)))
            divisor = np.gcd(np.gcd.reduceat(summed, kernel_starts), total)
            canon = summed // np.repeat(divisor, lengths)
            reduced_total = total // divisor
            h1[a:b] = np.add.reduceat(_mix(block, canon, 0x1234567), kernel_starts) + _mix(reduced_total, lengths, 0x2468ACE)
            h2[a:b] = np.add.reduceat(_mix(block, canon, 0x7654321), kernel_starts) + _mix(reduced_total, lengths, 0x13579BD)
        order = np.lexsort((h2, h1))
        same = (h1[order][1:] == h1[order][:-1]) & (h2[order][1:] == h2[order][:-1])
        ids = np.zeros(n, dtype=np.int64)
        ids[order[1:]] = np.cumsum(~same)
        return ids

    def deviation(self, block_of_class: np.ndarray, count: int, slot_of_state: np.ndarray, block_of_state: np.ndarray, succ, weight) -> float:
        """The largest difference between the chance of a state into a block and its block's chance, over all states that act.

        `slot_of_state[i]` is the position in `kernels` of the kernel state `i` uses (-1 for none) and `block_of_state[i]` its block;
        `succ[b]` and `weight[b]` are the block's row. A row that goes to other blocks than its block's differs by 1.
        """
        worst = 0.0
        wanted = np.flatnonzero(slot_of_state >= 0)
        pairs = np.unique(np.stack([slot_of_state[wanted], block_of_state[wanted]], axis=1), axis=0)
        by_slot = pairs[np.argsort(pairs[:, 0], kind="stable")]
        position = 0
        for a, b in self.chunks():
            kernel_starts, block, summed, total = self.groups(a, b, block_of_class, count)
            ends = np.append(kernel_starts, len(block))
            while position < len(by_slot) and by_slot[position, 0] < b:
                slot, owner_block = int(by_slot[position, 0]), int(by_slot[position, 1])
                position += 1
                k = slot - a
                low, high = int(ends[k]), int(ends[k + 1])
                row_blocks, row_weights = block[low:high], summed[low:high]
                want_blocks, want_weights = succ[owner_block], weight[owner_block]
                if not np.array_equal(row_blocks, want_blocks):
                    return 1.0
                if len(want_weights):
                    # equal integers over equal integers: compare the exact fractions' float values
                    differ = np.abs(row_weights / float(total[k]) - want_weights / float(want_weights.sum()))
                    worst = max(worst, float(differ.max()))
        return worst


def lump_policy(graph: PackedGraph, action: np.ndarray, start: int, *, max_rounds: int = 10_000) -> LumpedChain | None:
    """The coarsest lumping of the chain of policy `action` (an action index of `graph` per state, -1 for none) from `start`.

    Returns None when a kernel the policy uses has weights beyond 62 bits. A state with no action that is not a goal (a dead end)
    stays a block of its own kind: it is a block without successors that is not a goal. Raises `ValueError` when the final check
    finds a state whose chances differ from its block's by more than `CHECK_TOLERANCE`.
    """
    reached = policy_reach(graph, action, start)
    acts = action[reached]
    taking = acts >= 0
    if not taking.any():  # nothing to do anywhere (the start already is a goal): one block
        block_of_class = np.full(graph.n, -1, dtype=np.int64)
        block_of_class[reached] = 0
        return LumpedChain(
            block_of_class, 0, graph.goal[reached][:1], np.zeros(1), np.full(1, -1, dtype=np.int64), reached[:1],
            (np.zeros(0, dtype=np.int64),), (np.zeros(0, dtype=np.int64),), 0,
        )  # fmt: skip
    used = np.unique(graph.act_kernel[acts[taking]])
    if any(int(k) in graph.k_big for k in used.tolist()):
        return None
    rows = _Rows(graph, used)
    kernel_slot = np.full(graph.num_kernels, -1, dtype=np.int64)
    kernel_slot[used] = np.arange(len(used))
    cost = np.where(taking, graph.act_cost[np.maximum(acts, 0)], 0.0)
    kind = np.where(graph.goal[reached], 1, np.where(taking, 0, 2))  # 1 goal, 2 dead end
    _, first = np.unique(np.stack([kind.astype(np.float64), cost], axis=1), axis=0, return_inverse=True)
    block = first.reshape(-1).astype(np.int64)
    count = int(block.max()) + 1
    slot = np.where(taking, kernel_slot[graph.act_kernel[np.maximum(acts, 0)]], -1)
    on_class = np.full(graph.n, -1, dtype=np.int64)  # class -> block, for the classes reached
    rounds = 0
    while True:
        rounds += 1
        on_class[reached] = block
        ids = rows.signatures(on_class, count)
        sig = np.where(slot >= 0, ids[np.maximum(slot, 0)], -1)
        _, new = np.unique(np.stack([block, sig], axis=1), axis=0, return_inverse=True)
        new = new.reshape(-1).astype(np.int64)
        grown = int(new.max()) + 1
        if grown == count:
            break
        if rounds >= max_rounds:
            raise ValueError(f"the lumping did not settle in {max_rounds} rounds")
        block, count = new, grown
    on_class[reached] = block
    rep_index = np.full(count, len(reached), dtype=np.int64)
    np.minimum.at(rep_index, block, np.arange(len(reached)))
    rep = reached[rep_index]
    rep_action = action[rep]
    goal = graph.goal[rep]
    succ: list[np.ndarray] = []
    weight: list[np.ndarray] = []
    for b in range(count):
        a = int(rep_action[b])
        if a < 0 or goal[b]:
            succ.append(np.zeros(0, dtype=np.int64))
            weight.append(np.zeros(0, dtype=np.int64))
            continue
        lo, hi = int(graph.k_ptr[graph.act_kernel[a]]), int(graph.k_ptr[graph.act_kernel[a] + 1])
        target = on_class[graph.k_succ[lo:hi]]
        order = np.argsort(target, kind="stable")
        ts = target[order]
        starts = np.flatnonzero(np.concatenate(([True], ts[1:] != ts[:-1])))
        succ.append(ts[starts])
        weight.append(np.add.reduceat(graph.k_wt[lo:hi][order], starts))
    deviation = rows.deviation(on_class, count, np.where(slot >= 0, slot, -1), block, succ, weight)
    if deviation > CHECK_TOLERANCE:
        raise ValueError(f"the lumped chain disagrees with a state it stands for by {deviation:.3g} in chance: the lumping cannot be trusted")
    out_cost = np.where(rep_action >= 0, graph.act_cost[np.maximum(rep_action, 0)], 0.0)
    block_of_class = np.full(graph.n, -1, dtype=np.int64)
    block_of_class[reached] = block
    return LumpedChain(block_of_class, int(on_class[start]), goal, out_cost, rep_action, rep, tuple(succ), tuple(weight), rounds, deviation)


__all__ = ["LumpedChain", "lump_policy"]
