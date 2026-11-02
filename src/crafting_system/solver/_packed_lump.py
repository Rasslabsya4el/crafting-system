"""The exact lumping of a policy's chain on packed arrays (ticket #70, ADR-0063).

A fixed policy turns the (merged) graph into a Markov chain with a cost on every state. Two states can be told apart by nothing
the total cost sees when they pay the same and, for every block of a partition, move into that block with the same chance: then
the blocks form a chain of their own (ordinary lumpability) and the cost to reach a goal from a state has the very distribution
it has from its block. The coarsest such partition is found by refining it from "goal or not, and the cost paid" until no block
splits. It is exact (the chances are compared as integers, never as floats and never by a hash alone) and costs the edges of the
chain a few times over.

It is much smaller than the graph's own merge (`_packed_merge`), which asks for the same future under EVERY action: the chain of one
policy only has to agree on the action the policy takes. R04's optimal chain has 11,767 states and 17.1 million transitions (an
essence reroll leads to 4,034 states that differ in junk the policy never tells apart) and lumps to 552 blocks with 2,746
transitions; the budget DP of the risk run fits in memory on the blocks, not on the states.

Chances. A state's kernel is a list of successors with integer weights. Under the block map, the weights of the successors in one
block add up, and the state's row over blocks is (block, summed weight) pairs with a total. Two rows are the same distribution
exactly when they are the same pairs after dividing every summed weight and the total by their common divisor. A kernel whose
weights do not fit 62 bits (`PackedGraph.k_big`) is not handled: `lump_policy` returns None and the caller keeps the chain whole.

The generic part of `solver/`: nothing here knows the game. Uses numpy, so it is a `_packed*.py` file (ADR-0010 amended).
"""

from dataclasses import dataclass

import numpy as np

from ._packed import PackedGraph, expand_ranges
from ._packed_solve import policy_reach

_MASK = np.uint64(0xFFFFFFFFFFFFFFFF)


@dataclass(frozen=True, slots=True, eq=False)
class LumpedChain:
    """The lumped chain: block `b` pays `cost[b]` and moves to the blocks `succ[b]` with the integer weights `weight[b]`.

    `goal[b]` blocks absorb (no successors). `block[c]` is the block of class `c` of the graph (-1 for a class the policy does not
    reach); `start` is the block of the start class; `rep[b]` is a class of the block (the first); `action[b]` is the graph action its
    representative takes (-1 for a goal).
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
    """The rows over blocks of the kernels the policy uses, under one block map: canonical (block, weight) pairs and a total per kernel."""

    def __init__(self, graph: PackedGraph, kernels: np.ndarray) -> None:
        sizes = graph.kernel_sizes()[kernels]
        self.kernels = kernels
        self.sizes = sizes
        self.edge = expand_ranges(graph.k_ptr[kernels], sizes)
        self.owner = np.repeat(np.arange(len(kernels), dtype=np.int64), sizes)
        self.succ = graph.k_succ[self.edge]
        self.wt = graph.k_wt[self.edge]

    def canonical(self, block_of_class: np.ndarray, count: int):
        """`(group start, block, summed weight, owner, total)` per (kernel, block) group, the weights divided by the kernel's divisor."""
        b = block_of_class[self.succ].astype(np.int64)
        key = self.owner * count + b
        order = np.argsort(key, kind="stable")
        key_sorted = key[order]
        first = np.concatenate(([True], key_sorted[1:] != key_sorted[:-1]))
        starts = np.flatnonzero(first)
        summed = np.add.reduceat(self.wt[order], starts)
        group_key = key_sorted[starts]
        owner = group_key // count
        block = group_key % count
        kernel_first = np.concatenate(([True], owner[1:] != owner[:-1]))
        kernel_starts = np.flatnonzero(kernel_first)
        total = np.add.reduceat(summed, kernel_starts)
        divisor = np.gcd(np.gcd.reduceat(summed, kernel_starts), total)
        divisor = np.where(divisor == 0, 1, divisor)
        per_group = np.repeat(divisor, np.diff(np.append(kernel_starts, len(summed))))
        return kernel_starts, block, summed // per_group, owner, total // divisor

    def signatures(self, block_of_class: np.ndarray, count: int) -> np.ndarray:
        """An id per kernel, equal exactly for kernels with the same canonical row (checked, not assumed)."""
        kernel_starts, block, canon, owner, total = self.canonical(block_of_class, count)
        n = len(self.kernels)
        h1 = np.add.reduceat(_mix(block, canon, 0x1234567), kernel_starts)
        h2 = np.add.reduceat(_mix(block, canon, 0x7654321), kernel_starts)
        h1 = h1 + _mix(total, np.diff(np.append(kernel_starts, len(block))), 0x2468ACE)
        h2 = h2 + _mix(total, np.diff(np.append(kernel_starts, len(block))), 0x13579BD)
        order = np.lexsort((h2, h1))
        same = (h1[order][1:] == h1[order][:-1]) & (h2[order][1:] == h2[order][:-1])
        ids = np.zeros(n, dtype=np.int64)
        ids[order[1:]] = np.cumsum(~same)
        # a hash collision would merge two different rows: compare each kernel with the first of its id exactly
        lengths = np.diff(np.append(kernel_starts, len(block)))
        reference = order[np.concatenate(([True], ~same))][ids]
        for kernel in np.flatnonzero(reference != np.arange(n)):
            other = reference[kernel]
            a0, b0 = kernel_starts[kernel], kernel_starts[other]
            n0 = lengths[kernel]
            if (
                lengths[other] != n0
                or total[kernel] != total[other]
                or not np.array_equal(block[a0 : a0 + n0], block[b0 : b0 + n0])
                or not np.array_equal(canon[a0 : a0 + n0], canon[b0 : b0 + n0])
            ):
                raise ValueError("two different rows of the policy chain have the same hash: the lumping cannot be trusted")
        return ids


def lump_policy(graph: PackedGraph, action: np.ndarray, start: int, *, max_rounds: int = 10_000) -> LumpedChain | None:
    """The coarsest lumping of the chain of policy `action` (an action index of `graph` per state, -1 for none) from `start`.

    Returns None when a kernel the policy uses has weights beyond 62 bits. A state with no action that is not a goal (a dead end)
    stays a block of its own kind: it is a block without successors that is not a goal.
    """
    reached = policy_reach(graph, action, start)
    acts = action[reached]
    taking = acts >= 0
    used = np.unique(graph.act_kernel[acts[taking]]) if taking.any() else np.zeros(0, dtype=np.int64)
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
        ids = rows.signatures(on_class, count) if len(used) else np.zeros(0, dtype=np.int64)
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
    out_cost = np.where(rep_action >= 0, graph.act_cost[np.maximum(rep_action, 0)], 0.0)
    block_of_class = np.full(graph.n, -1, dtype=np.int64)
    block_of_class[reached] = block
    return LumpedChain(block_of_class, int(on_class[start]), goal, out_cost, rep_action, rep, tuple(succ), tuple(weight), rounds)


__all__ = ["LumpedChain", "lump_policy"]
