"""The rows of the bound's model and the offers held at some keys only, packed in arrays (ticket #1366).

The model of the key (`_pattern.PatternModel`) has, at each key, a row of abstract actions `(offer index, kernel id)`, and since #1325 an offer
may be built at some keys only (`narrow`: offer -> the numbers of those keys). Both were Python objects: a tuple of two ints for each action of
a row, a frozenset of ints for each offer held at some keys, made twice (the model's, by offer index, and the bound's, by position), and the
search read the rows through two lists of one dict a key (`_envelope_plan.CraftingProblem.lowest`, and `closed_lowest` on a stopped build). On
R04's round of 1,309 offers (main 8a350184, `.claude/scratch/t1366/p1-R04`), whose growth built 1,245 offers at about 11,000 keys, they held,
for 14.19 million actions and 14.04 million (offer, key) pairs held: the rows 995 MB (14.19 million tuples), the model's narrow 989 MB, the
bound's 623 MB, `lowest` 759 MB and `closed_lowest` 759 MB: 4.1 GB, about 290 bytes for each action, where the build's keys, kernels and
index took 241 MB. Recording the next round's 13.8 million pairs as sets and lists took the process from 10.1 GB to 15.9 GB before one
action was built, and that is where the 12 GB net stopped the build; and since the small objects freed later stay in the allocator's arenas,
the search then walked the first plan with 10.5 GB held and was cut by the net.

Here an action is two 32-bit integers (`Rows`: `offer[ptr[k]:ptr[k+1]]`, `kernel[...]`), and a pair held one 32-bit integer by offer and one
by key (`Held`): about 16 bytes where there were about 290, the same model to the last action. Nothing is approximated and nothing is let go:
`Rows` and `Held` answer what the lists and sets answered (`Rows[k]` is the row as a list of tuples, `Held[p]` the sorted keys of offer `p`),
so every reader gets the same values; the readers that loop over every action read the arrays (`pack_pattern_model`, the search's backups).
The arrays of a held offer are never changed in place (`Held.add` makes a new one), so a snapshot of the model shares them with the builder
and stays what it was when the builder goes on.
"""

from __future__ import annotations

from array import array
from collections.abc import Iterable, Iterator, Mapping, Sequence

import numpy as np

INT = "i"  # a C int: 32 bits on every system the planner runs on (an offer index, a kernel id and a key number all fit: they count Python objects)
NP_INT = np.intc
_EMPTY = np.zeros(0, dtype=NP_INT)
_EMPTY.flags.writeable = False


def _frozen(values: np.ndarray) -> np.ndarray:
    values.flags.writeable = False
    return values


class Rows(Sequence):
    """The rows of a model, packed: the actions of key `k` are `offer[ptr[k]:ptr[k + 1]]` with `kernel[...]` (read-only arrays).

    `rows[k]` is the row as the list of `(offer index, kernel id)` it was, so a reader of one row reads what it read; `len`, iteration and `==`
    (with another `Rows` or a list of lists) are those of that list of rows."""

    __slots__ = ("ptr", "offer", "kernel")

    def __init__(self, ptr: np.ndarray, offer: np.ndarray, kernel: np.ndarray) -> None:
        self.ptr, self.offer, self.kernel = _frozen(ptr), _frozen(offer), _frozen(kernel)

    @classmethod
    def of(cls, rows: Iterable[Iterable[tuple[int, int]]]) -> "Rows":
        """The packed form of rows given as lists of `(offer index, kernel id)`."""
        store = RowStore()
        for row in rows:
            store.append(row)
        return store.frozen()

    def __len__(self) -> int:
        return len(self.ptr) - 1

    def __getitem__(self, k):  # type: ignore[override]
        if isinstance(k, slice):
            return [self[i] for i in range(*k.indices(len(self)))]
        if k < 0:
            k += len(self)
        if not 0 <= k < len(self):
            raise IndexError(k)
        a, b = int(self.ptr[k]), int(self.ptr[k + 1])
        return list(zip(self.offer[a:b].tolist(), self.kernel[a:b].tolist()))

    def __iter__(self) -> Iterator[list[tuple[int, int]]]:
        for k in range(len(self)):
            yield self[k]

    def __eq__(self, other) -> bool:
        if isinstance(other, Rows):
            return bool(np.array_equal(self.ptr, other.ptr) and np.array_equal(self.offer, other.offer) and np.array_equal(self.kernel, other.kernel))
        if isinstance(other, list):
            return list(self) == other
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]

    def size(self, k: int) -> int:
        """The number of actions of key `k`'s row."""
        return int(self.ptr[k + 1] - self.ptr[k])

    @property
    def entries(self) -> int:
        """The number of actions of every row."""
        return int(self.ptr[-1])

    def owner(self) -> np.ndarray:
        """The key number of each action, in order."""
        return np.repeat(np.arange(len(self), dtype=NP_INT), np.diff(self.ptr))

    def __repr__(self) -> str:
        return f"Rows({len(self)} keys, {self.entries} actions)"


class RowStore:
    """The rows of a model while it is built: one array of `offer, kernel, offer, kernel, ...` a key, appended to (`PatternBuilder`)."""

    __slots__ = ("_rows",)

    def __init__(self, keys: int = 0) -> None:
        self._rows: list[array] = [array(INT) for _ in range(keys)]

    def __len__(self) -> int:
        return len(self._rows)

    def append(self, row: Iterable[tuple[int, int]] = ()) -> None:
        """A new key, with `row` as its actions."""
        self._rows.append(array(INT))
        self.extend(len(self._rows) - 1, row)

    def add(self, k: int, offer: int, kernel: int) -> None:
        found = self._rows[k]
        found.append(offer)
        found.append(kernel)

    def extend(self, k: int, row: Iterable[tuple[int, int]]) -> None:
        found = self._rows[k]
        for offer, kernel in row:
            found.append(offer)
            found.append(kernel)

    def clear(self, k: int) -> None:
        self._rows[k] = array(INT)

    def size(self, k: int) -> int:
        return len(self._rows[k]) // 2

    def __getitem__(self, k: int) -> list[tuple[int, int]]:
        found = self._rows[k]
        return list(zip(found[0::2], found[1::2]))

    def frozen(self) -> Rows:
        """A packed copy of the rows as they are now (the store goes on independently)."""
        sizes = np.fromiter((len(row) // 2 for row in self._rows), dtype=np.int64, count=len(self._rows))
        ptr = np.zeros(len(self._rows) + 1, dtype=np.int64)
        np.cumsum(sizes, out=ptr[1:])
        flat = np.frombuffer(b"".join(row.tobytes() for row in self._rows), dtype=NP_INT)
        return Rows(ptr, flat[0::2].copy(), flat[1::2].copy())


class Held(Mapping):
    """The offers held at some keys only (#1325): offer -> the sorted numbers of the keys it is held at (a read-only array of 32-bit integers).

    `held[p]` and iteration are those of the dict of key sets it replaces (`k in held[p]` is true exactly for a key that holds `p`); `holds`
    asks one pair, and `offers_at` lists the offers a key holds (an index by key, made once after the offers last changed). `add` puts keys
    under an offer in a new array: a copy (`copy`, `renamed`) keeps the arrays it had, and so what it said."""

    __slots__ = ("_by_offer", "_by_key")

    def __init__(self, by_offer: Mapping[int, np.ndarray] | None = None) -> None:
        self._by_offer: dict[int, np.ndarray] = dict(by_offer or {})
        self._by_key: tuple[np.ndarray, np.ndarray] | None = None

    @classmethod
    def of(cls, held: "Mapping[int, Iterable[int]] | Held | None") -> "Held":
        """`held` as a `Held` (a dict of key sets, as the hand-worked tests give it; a `Held` is returned as it is)."""
        if isinstance(held, Held):
            return held
        found = cls()
        for p, keys in (held or {}).items():
            found.add(p, keys)
        return found

    def __getitem__(self, p: int) -> np.ndarray:
        return self._by_offer[p]

    def __iter__(self) -> Iterator[int]:
        return iter(self._by_offer)

    def __len__(self) -> int:
        return len(self._by_offer)

    def __contains__(self, p) -> bool:
        return p in self._by_offer

    def keys_of(self, p: int) -> np.ndarray:
        """The keys offer `p` is held at (none when it is not held at some keys only)."""
        return self._by_offer.get(p, _EMPTY)

    def holds(self, k: int, p: int) -> bool:
        """Whether offer `p`, held at some keys only, is held at key `k`."""
        keys = self._by_offer.get(p)
        if keys is None:
            return False
        at = int(np.searchsorted(keys, k))
        return at < len(keys) and int(keys[at]) == k

    def add(self, p: int, keys: Iterable[int] | np.ndarray) -> np.ndarray:
        """Hold offer `p` at `keys` too (an offer added with no key is held at none); the keys it was not held at before, sorted."""
        given = np.unique(np.asarray(keys if isinstance(keys, np.ndarray) else list(keys), dtype=NP_INT))
        before = self._by_offer.get(p)
        if before is None:
            self._by_offer[p] = _frozen(given)
            fresh = given
        else:
            fresh = given[~np.isin(given, before, assume_unique=True)]
            if len(fresh):
                self._by_offer[p] = _frozen(np.union1d(before, fresh).astype(NP_INT))
        if len(fresh):
            self._by_key = None
        return fresh

    def copy(self) -> "Held":
        return Held(self._by_offer)

    def renamed(self, names: Sequence[int]) -> "Held":
        """The same holdings with offer `p` called `names[p]` (the model's offer index -> its position in the offers given)."""
        return Held({names[p]: keys for p, keys in self._by_offer.items()})

    @property
    def pairs(self) -> int:
        """The number of (offer, key) pairs held."""
        return sum(len(keys) for keys in self._by_offer.values())

    def _index(self) -> tuple[np.ndarray, np.ndarray]:
        if self._by_key is None:
            if not self._by_offer:
                self._by_key = (np.zeros(1, dtype=np.int64), _EMPTY)
            else:
                keys = np.concatenate(list(self._by_offer.values()))
                offers = np.repeat(np.fromiter(self._by_offer, dtype=NP_INT, count=len(self._by_offer)), [len(v) for v in self._by_offer.values()])
                order = np.argsort(keys, kind="stable")
                counts = np.bincount(keys, minlength=int(keys.max()) + 1 if len(keys) else 0)
                ptr = np.zeros(len(counts) + 1, dtype=np.int64)
                np.cumsum(counts, out=ptr[1:])
                self._by_key = (ptr, _frozen(offers[order]))
        return self._by_key

    def offers_at(self, k: int) -> np.ndarray:
        """The offers key `k` holds of those held at some keys only."""
        ptr, offers = self._index()
        if k + 1 >= len(ptr):
            return _EMPTY
        return offers[ptr[k] : ptr[k + 1]]

    def counts(self) -> np.ndarray:
        """How many of these offers each key holds (index: the key number, up to the last key that holds one)."""
        ptr, _offers = self._index()
        return np.diff(ptr)

    def __eq__(self, other) -> bool:
        if isinstance(other, Mapping):
            if set(self) != set(other):
                return False
            return all(np.array_equal(self[p], np.unique(np.asarray(list(other[p]) if not isinstance(other[p], np.ndarray) else other[p]))) for p in self)
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"Held({len(self)} offers, {self.pairs} pairs)"


__all__ = ["Held", "RowStore", "Rows"]
