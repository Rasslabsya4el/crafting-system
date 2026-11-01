"""The packed graph: a state graph held as flat numpy arrays, kernels shared (ticket #374, ADR-0063 point 1).

The object solver (`_graph.py`) holds a transition per (state, action, outcome): about 32 bytes each, 17 GB for the
536 million transitions of R04. Most of those transitions repeat: many (state, action) pairs have the very same
successor distribution (a KERNEL: the successors and their integer weights). The packed graph stores each kernel once and
each action as a (tag, cost, kernel) triple:

* states `0..n-1`: `goal[s]`, and the actions of `s` are `act_ptr[s]:act_ptr[s+1]`;
* action `a`: `act_tag[a]` (opaque to the solver: the caller's identity of the action, e.g. an offer number),
  `act_cost[a]` (finite, above zero) and `act_kernel[a]`;
* kernel `k`: the edges `k_ptr[k]:k_ptr[k+1]` of `k_succ` (successor states), `k_wt` (integer weights, above zero) and
  `k_prob` (weight / total, correctly rounded). A kernel whose total weight is 2^62 or more keeps its exact weights in
  `k_big[k]` (`k_wt` is zero there) and its probabilities from exact integer division.

The module is generic like the rest of `solver/`: nothing here knows the game. It is the only place of `solver/` that
uses numpy (ADR-0010 amended by ADR-0063).
"""

from array import array
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import numpy as np

from ._model import Action, Model, Outcome, Peek, VariantAction

BIG_TOTAL = 1 << 62  # a kernel whose weights add up to this much is kept apart (exact Python integers)
CHUNK_EDGES = 4_000_000  # edges handled at once by the vectorised passes (bounds their temporary arrays)


@dataclass(frozen=True, slots=True, eq=False)
class PackedGraph:
    """The arrays described in the module docstring. Built by `PackedBuilder.build`; never changed afterwards."""

    goal: np.ndarray  # bool (n,)
    act_ptr: np.ndarray  # int64 (n + 1,)
    act_tag: np.ndarray  # int32 (A,)
    act_cost: np.ndarray  # float64 (A,)
    act_kernel: np.ndarray  # int32 (A,)
    k_ptr: np.ndarray  # int64 (K + 1,)
    k_succ: np.ndarray  # int32 (E,)
    k_wt: np.ndarray  # int64 (E,)
    k_prob: np.ndarray  # float64 (E,)
    k_big: dict[int, tuple[int, ...]] = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.goal)

    @property
    def num_actions(self) -> int:
        return len(self.act_cost)

    @property
    def num_kernels(self) -> int:
        return len(self.k_ptr) - 1

    @property
    def num_edges(self) -> int:
        """Edges stored (each kernel once)."""
        return len(self.k_succ)

    def kernel_sizes(self) -> np.ndarray:
        return np.diff(self.k_ptr)

    def edges_counted(self) -> int:
        """Transitions the way the object solver would hold them: every action's kernel counted for that action."""
        return int(self.kernel_sizes()[self.act_kernel].sum()) if self.num_actions else 0

    def action_state(self) -> np.ndarray:
        """The state of every action (int32, length A)."""
        return np.repeat(np.arange(self.n, dtype=np.int32), np.diff(self.act_ptr))

    def kernel_weights(self, kernel: int) -> tuple[int, ...]:
        """The exact integer weights of one kernel."""
        big = self.k_big.get(kernel)
        if big is not None:
            return big
        return tuple(int(w) for w in self.k_wt[self.k_ptr[kernel] : self.k_ptr[kernel + 1]])


def kernel_chunks(k_ptr: np.ndarray, limit: int = CHUNK_EDGES):
    """Ranges `(k0, k1)` of consecutive kernels holding at most `limit` edges each (one kernel at least)."""
    count = len(k_ptr) - 1
    k0 = 0
    while k0 < count:
        k1 = int(np.searchsorted(k_ptr, k_ptr[k0] + limit, side="right")) - 1
        k1 = min(max(k1, k0 + 1), count)
        yield k0, k1
        k0 = k1


def expand_ranges(starts: np.ndarray, sizes: np.ndarray) -> np.ndarray:
    """The concatenation of `range(start, start + size)` for each pair (int64)."""
    total = int(sizes.sum())
    if total == 0:
        return np.zeros(0, dtype=np.int64)
    lead = np.concatenate(([0], np.cumsum(sizes)[:-1]))
    return np.repeat(starts.astype(np.int64) - lead, sizes) + np.arange(total, dtype=np.int64)


def probabilities(k_ptr: np.ndarray, k_wt: np.ndarray, k_big: dict[int, tuple[int, ...]]) -> np.ndarray:
    """`weight / total` of every edge, per kernel (exact integer division for the big kernels)."""
    prob = np.empty(len(k_wt), dtype=np.float64)
    for k0, k1 in kernel_chunks(k_ptr):
        lo, hi = int(k_ptr[k0]), int(k_ptr[k1])
        sizes = np.diff(k_ptr[k0 : k1 + 1])
        totals = np.add.reduceat(k_wt[lo:hi], k_ptr[k0:k1] - lo)
        with np.errstate(divide="ignore", invalid="ignore"):
            prob[lo:hi] = k_wt[lo:hi] / np.repeat(totals, sizes)
    for kernel, weights in k_big.items():
        total = sum(weights)
        prob[k_ptr[kernel] : k_ptr[kernel + 1]] = [w / total for w in weights]  # int / int is correctly rounded
    return prob


class PackedBuilder:
    """Collects kernels and then actions state by state, in state order, and builds the `PackedGraph`.

        kernel = builder.kernel(successors, weights)   # once per distinct distribution
        builder.action(tag, cost, kernel)               # the actions of the current state
        builder.close_state(is_goal)                    # next state

    States are numbered by the order of `close_state`; the caller interns them and must close every state it handed out
    as a successor (a state that is never closed has no row, and `build` refuses).
    """

    def __init__(self) -> None:
        self._goal = bytearray()
        self._ptr = array("q", [0])
        self._tag = array("i")
        self._cost = array("d")
        self._kernel = array("i")
        self._succ: list[np.ndarray] = []
        self._wt: list[np.ndarray | None] = []
        self._big: dict[int, tuple[int, ...]] = {}
        self._sizes = array("q")
        self.edges = 0  # transitions counted per action (a kernel counts once for each action that uses it)
        self._max_successor = -1

    @property
    def states_closed(self) -> int:
        return len(self._goal)

    @property
    def kernels(self) -> int:
        return len(self._succ)

    def kernel(self, successors: Sequence[int] | np.ndarray, weights: Sequence[int]) -> int:
        """Add a distribution: distinct successor states and positive integer weights; return its id."""
        succ = np.asarray(successors, dtype=np.int32)
        if len(succ) == 0 or len(succ) != len(weights):
            raise ValueError("a kernel needs as many weights as successors, and at least one")
        total = 0
        for w in weights:
            total += w
        kernel = len(self._succ)
        if total >= BIG_TOTAL:
            self._big[kernel] = tuple(int(w) for w in weights)
            self._wt.append(None)
        else:
            self._wt.append(np.asarray(weights, dtype=np.int64))
        self._succ.append(succ)
        self._sizes.append(len(succ))
        self._max_successor = max(self._max_successor, int(succ.max()))
        return kernel

    def action(self, tag: int, cost: float, kernel: int) -> None:
        self._tag.append(tag)
        self._cost.append(cost)
        self._kernel.append(kernel)
        self.edges += self._sizes[kernel]

    def close_state(self, is_goal: bool) -> None:
        self._goal.append(1 if is_goal else 0)
        self._ptr.append(len(self._tag))

    def build(self) -> PackedGraph:
        n = len(self._goal)
        if self._max_successor >= n:
            raise ValueError(f"a kernel names state {self._max_successor} but only {n} states were closed")
        sizes = np.frombuffer(self._sizes, dtype=np.int64) if len(self._sizes) else np.zeros(0, dtype=np.int64)
        k_ptr = np.concatenate(([0], np.cumsum(sizes))).astype(np.int64)
        k_succ = np.concatenate(self._succ) if self._succ else np.zeros(0, dtype=np.int32)
        parts = [w if w is not None else np.zeros(len(s), dtype=np.int64) for w, s in zip(self._wt, self._succ)]
        k_wt = np.concatenate(parts) if parts else np.zeros(0, dtype=np.int64)
        self._succ, self._wt = [], []
        graph = PackedGraph(
            goal=np.frombuffer(bytes(self._goal), dtype=np.uint8).astype(bool),
            act_ptr=np.frombuffer(self._ptr, dtype=np.int64).copy(),
            act_tag=np.frombuffer(self._tag, dtype=np.int32).copy() if len(self._tag) else np.zeros(0, dtype=np.int32),
            act_cost=np.frombuffer(self._cost, dtype=np.float64).copy() if len(self._cost) else np.zeros(0),
            act_kernel=np.frombuffer(self._kernel, dtype=np.int32).copy() if len(self._kernel) else np.zeros(0, dtype=np.int32),
            k_ptr=k_ptr,
            k_succ=k_succ,
            k_wt=k_wt,
            k_prob=probabilities(k_ptr, k_wt, self._big),
            k_big=dict(self._big),
        )
        return graph


def assemble(
    goal: np.ndarray,
    act_ptr: np.ndarray,
    act_tag: np.ndarray,
    act_cost: np.ndarray,
    act_kernel: np.ndarray,
    kernel_succ: list[np.ndarray],
    kernel_wt: list,
) -> PackedGraph:
    """A graph from per-kernel arrays; an entry of `kernel_wt` that is a tuple of Python ints is a big kernel."""
    k_big: dict[int, tuple[int, ...]] = {}
    parts = []
    for kernel, (succ, wt) in enumerate(zip(kernel_succ, kernel_wt)):
        if isinstance(wt, tuple):
            k_big[kernel] = wt
            parts.append(np.zeros(len(succ), dtype=np.int64))
        else:
            parts.append(np.asarray(wt, dtype=np.int64))
    sizes = np.array([len(s) for s in kernel_succ], dtype=np.int64)
    k_ptr = np.concatenate(([0], np.cumsum(sizes))).astype(np.int64)
    k_wt = np.concatenate(parts) if parts else np.zeros(0, dtype=np.int64)
    return PackedGraph(
        goal=goal,
        act_ptr=act_ptr,
        act_tag=act_tag,
        act_cost=act_cost,
        act_kernel=act_kernel,
        k_ptr=k_ptr,
        k_succ=np.concatenate(kernel_succ).astype(np.int32) if kernel_succ else np.zeros(0, dtype=np.int32),
        k_wt=k_wt,
        k_prob=probabilities(k_ptr, k_wt, k_big),
        k_big=k_big,
    )


@dataclass(frozen=True, slots=True, eq=False)
class PackedModel[S]:
    """A generic `Model` walked into a packed graph: `states[i]` is state `i`, `actions[a]` the model's action `a`."""

    graph: PackedGraph
    states: list[S]
    index: dict[S, int]
    actions: list[Action[S]]


def pack_model[S](model: Model[S], starts: Iterable[S]) -> PackedModel[S]:
    """Explore a `Model` from `starts` (breadth first, `model.actions` once per non-goal state) into a packed graph.

    Kernels are shared between actions with the same successors and weights. Repeated successors of an action are
    merged by summing, zero weights dropped. Actions with `extra_inputs`, `VariantAction`s and `Peek`s are refused
    (`ValueError`): those stay with the object solver.
    """
    states: list[S] = []
    index: dict[S, int] = {}

    def intern(state: S) -> int:
        found = index.get(state)
        if found is None:
            found = index[state] = len(states)
            states.append(state)
        return found

    for start in starts:
        intern(start)
    builder = PackedBuilder()
    kernels: dict[tuple, int] = {}
    kept: list[Action[S]] = []
    i = 0
    while i < len(states):
        state = states[i]
        goal = model.is_goal(state)
        if not goal:
            for action in model.actions(state):
                if isinstance(action, (VariantAction, Peek)) or not isinstance(action, Action):
                    raise ValueError(f"the packed solve takes plain actions only, got {action!r}")
                if action.extra_inputs:
                    raise ValueError(f"the packed solve takes no extra inputs, got {action.label!r}")
                merged: dict[int, int] = {}
                for outcome in action.outcomes:
                    if outcome.weight:
                        target = intern(outcome.state)
                        merged[target] = merged.get(target, 0) + outcome.weight
                key = tuple(sorted(merged.items()))
                kernel = kernels.get(key)
                if kernel is None:
                    kernel = kernels[key] = builder.kernel([t for t, _ in key], [w for _, w in key])
                builder.action(len(kept), action.cost, kernel)
                kept.append(action)
        builder.close_state(goal)
        i += 1
    return PackedModel(builder.build(), states, index, kept)


def kernel_sums(graph: PackedGraph, f: np.ndarray) -> np.ndarray:
    """For every kernel: the sum of `prob * f[successor]` over its edges (float64, in chunks)."""
    out = np.empty(graph.num_kernels, dtype=np.float64)
    k_ptr = graph.k_ptr
    for k0, k1 in kernel_chunks(k_ptr):
        lo, hi = int(k_ptr[k0]), int(k_ptr[k1])
        out[k0:k1] = np.add.reduceat(graph.k_prob[lo:hi] * f[graph.k_succ[lo:hi]], k_ptr[k0:k1] - lo)
    return out


def kernel_any(graph: PackedGraph, flags: np.ndarray) -> np.ndarray:
    """For every kernel: whether `flags[successor]` holds for some successor."""
    out = np.empty(graph.num_kernels, dtype=bool)
    k_ptr = graph.k_ptr
    for k0, k1 in kernel_chunks(k_ptr):
        lo, hi = int(k_ptr[k0]), int(k_ptr[k1])
        out[k0:k1] = np.logical_or.reduceat(flags[graph.k_succ[lo:hi]], k_ptr[k0:k1] - lo)
    return out


def kernel_min(graph: PackedGraph, f: np.ndarray) -> np.ndarray:
    """For every kernel: the least `f[successor]`."""
    out = np.empty(graph.num_kernels, dtype=np.float64)
    k_ptr = graph.k_ptr
    for k0, k1 in kernel_chunks(k_ptr):
        lo, hi = int(k_ptr[k0]), int(k_ptr[k1])
        out[k0:k1] = np.minimum.reduceat(f[graph.k_succ[lo:hi]], k_ptr[k0:k1] - lo)
    return out


__all__ = [
    "BIG_TOTAL",
    "PackedBuilder",
    "PackedGraph",
    "PackedModel",
    "assemble",
    "expand_ranges",
    "kernel_any",
    "kernel_chunks",
    "kernel_min",
    "kernel_sums",
    "pack_model",
    "probabilities",
]
