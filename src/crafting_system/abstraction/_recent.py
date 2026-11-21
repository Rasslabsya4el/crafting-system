"""A memo that keeps the entries used lately and lets the others go: the caches of a bound's build that grow with its members (#1335).

A bound's build asks two pure functions again and again: which kernel a kernel key has (`PatternBuilder.computed`), and whether a member is an
item (`Pattern._feasible`). Kept whole, their memos grew with every member the build made: on R04's 1,245-offer bound, 1,862 MB for 2.18
million kernel keys and 1,031 MB for 3.5 million members at 55 minutes, about 1.3 KB more for each kernel the build made, until the run's
memory net stopped it at 6.61 million kernels. Both answers are a function of the key alone, so an entry let go is only computed again when
it is asked again: a kernel made again is pushed onto the same keys and found in the model's kernels (`_kernel_id`), so it gets the same
kernel id, and the member is again an item or again not. No value of the model changes; what changes is the work, and that only for a key
asked again after it left.

`Recent` holds two generations of at most `size` entries each: entries are written into the young one; when it is full, the old one is let go
and the young one becomes the old one. An entry read from the old generation is written into the young one again, so an entry asked at
least once in every `size` writes stays. The rule is the same for every route: a cache's size, not a cut of the search (OR-12).

**The size follows the run's memory net** (`kept_entries`, OR-40): a memo may hold a stated share of the net, so a generation holds
`net * share / (2 * bytes of an entry)` entries; the bytes of an entry are a property of the entry's Python objects, the same on every route
(measured on R04, #1335). The net is the run's (`parallel.memory_net`), else the default net of this machine (`budget.default_memory_mb`).
"""

from __future__ import annotations

from typing import Callable, Generic, Hashable, TypeVar

from crafting_system import budget, parallel

V = TypeVar("V")
FEWEST_KEPT = 1 << 12  # a generation holds at least this many entries, on a machine whose memory cannot be read or a tiny net: a memo of a few MB
UNREAD_NET_MB = 4096.0  # the net taken where neither the run nor the machine says one (a memo of a few hundred MB at most)


def kept_entries(share: float, entry_bytes: float, net_mb: float | None = None) -> int:
    """The entries of one generation of a memo that may hold `share` of a memory net of `net_mb` MB (default: the run's net, else the machine's
    default net) in entries of about `entry_bytes` bytes each: two generations of them fill the share (module docstring)."""
    if net_mb is None:
        net_mb = parallel.active_memory_net() or budget.default_memory_mb() or UNREAD_NET_MB
    return max(FEWEST_KEPT, int(net_mb * (1 << 20) * share / (2 * entry_bytes)))
_MISSING = object()


class Recent(Generic[V]):
    """A dict-like memo of the entries written or read in the last `size` to `2 * size` writes (module docstring)."""

    __slots__ = ("size", "young", "old", "generation", "dropped", "weigh", "weight")

    def __init__(self, size: "int | Callable[[], int]", weigh: Callable[[V], int] | None = None) -> None:
        if not callable(size) and size < 1:
            raise ValueError("a memo keeps at least one entry")
        self.size = size  # or a function of nothing, read each time an entry is written: a share of the net that holds when it is written (`kept_entries`)
        self.young: dict[Hashable, V] = {}
        self.old: dict[Hashable, V] = {}
        self.weigh = weigh  # an entry's weight (a list of members: its length, #1341); None: each entry weighs 1, and `size` counts entries
        self.weight = 0  # the weight written into the young generation: it is full at `size`
        self.generation = 0  # how many times the old generation was let go
        self.dropped = 0  # how many entries were let go

    def get(self, key: Hashable, default=None):
        found = self.young.get(key, _MISSING)
        if found is not _MISSING:
            return found
        found = self.old.get(key, _MISSING)
        if found is _MISSING:
            return default
        self[key] = found  # asked again: it stays one generation more
        return found

    def __getitem__(self, key: Hashable) -> V:
        found = self.get(key, _MISSING)
        if found is _MISSING:
            raise KeyError(key)
        return found

    def __contains__(self, key: Hashable) -> bool:
        return key in self.young or key in self.old

    def __setitem__(self, key: Hashable, value: V) -> None:
        young = self.young
        young[key] = value
        self.weight += 1 if self.weigh is None else max(1, self.weigh(value))
        if self.weight >= (self.size() if callable(self.size) else self.size):
            self.dropped += len(self.old)
            self.old = young
            self.young = {}
            self.weight = 0
            self.generation += 1

    def clear(self) -> None:
        """Let every entry go (`Abstraction.release_memos`)."""
        self.dropped += len(self.young) + len(self.old)
        self.young, self.old, self.weight = {}, {}, 0

    def update(self, entries) -> None:
        for key, value in dict(entries).items():
            self[key] = value

    def keys(self):
        return self.items().keys()

    def values(self):
        return self.items().values()

    def items(self) -> dict[Hashable, V]:
        """Every entry held, the young generation's answer where a key is in both (a dict, for reading)."""
        return {**self.old, **self.young}

    def __iter__(self):
        return iter(self.items())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Recent):
            return self.items() == other.items()
        return NotImplemented

    __hash__ = None  # a memo changes: it is no key

    def distinct(self) -> int:
        """The keys held, each once (an entry read back from the old generation is in both)."""
        young = self.young
        return len(young) + sum(1 for key in self.old if key not in young)

    def __len__(self) -> int:
        """The entries held (an entry read from the old generation is in both and counted twice)."""
        return len(self.young) + len(self.old)
