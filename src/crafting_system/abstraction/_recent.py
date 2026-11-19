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
least once in every `size` writes stays. The rule is the same for every route and for every machine: a cache's size, not a cut of the
search (OR-12).
"""

from __future__ import annotations

from typing import Generic, Hashable, TypeVar

V = TypeVar("V")
_MISSING = object()


class Recent(Generic[V]):
    """A dict-like memo of the entries written or read in the last `size` to `2 * size` writes (module docstring)."""

    __slots__ = ("size", "young", "old", "generation", "dropped")

    def __init__(self, size: int) -> None:
        if size < 1:
            raise ValueError("a memo keeps at least one entry")
        self.size = size
        self.young: dict[Hashable, V] = {}
        self.old: dict[Hashable, V] = {}
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
        if len(young) >= self.size:
            self.dropped += len(self.old)
            self.old = young
            self.young = {}
            self.generation += 1

    def __len__(self) -> int:
        """The entries held (an entry read from the old generation is in both and counted twice)."""
        return len(self.young) + len(self.old)
