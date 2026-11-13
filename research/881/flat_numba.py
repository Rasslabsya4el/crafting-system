"""The pool-signature loop on flat arrays, compiled by Numba (ticket #881, a prototype; no `src/` change).

The loop is the one `flat_python.signatures` and `flat_cython.signatures` run, on the same arrays (see `bench_kernels.py` for what they hold):
per call, the sort keys of the candidates present are sorted, each run of one family and side becomes a family type (interned by its content),
the types are sorted and, with the call's head, become the signature (interned by its content). No number is rounded: weights and labels are
integer ids, compared for equality only, and an id is found by comparing the whole content after the hash, so two calls get one signature id
exactly when their contents are equal.
"""

import numpy as np
from numba import njit

GROUP_SHIFT = 42  # a sort key is `group << 42 | label << 21 | weight << 1 | flag`
MIX = np.uint64(0x9E3779B97F4A7C15)
SEED = np.uint64(0xCBF29CE484222325)
SHIFT = np.uint64(29)
TRIPLE_MASK = np.uint64((1 << GROUP_SHIFT) - 1)
ONE = np.uint64(1)
GROUP_BITS = np.uint64(GROUP_SHIFT)


@njit(cache=True)
def _hash(values, begin, end):
    h = SEED
    for i in range(begin, end):
        h = (h ^ values[i]) * MIX
        h = h ^ (h >> SHIFT)
    return h


@njit(cache=True)
def _grow(slots, hashes, count):
    """A table twice the size holding the same ids."""
    bigger = np.full(slots.shape[0] * 2, -1, dtype=np.int64)
    mask = np.uint64(bigger.shape[0] - 1)
    for ident in range(count):
        at = np.int64(hashes[ident] & mask)
        while bigger[at] >= 0:
            at = (at + 1) & np.int64(mask)
        bigger[at] = ident
    return bigger


@njit(cache=True)
def _intern(scratch, length, slots, hashes, offsets, pool, counts):
    """The id of the content `scratch[:length]` in one table: the id it has, or a new one. `counts` holds (ids, values in the pool)."""
    h = _hash(scratch, 0, length)
    mask = np.int64(slots.shape[0] - 1)
    at = np.int64(h & np.uint64(mask))
    while True:
        ident = slots[at]
        if ident < 0:
            break
        if hashes[ident] == h:
            begin = offsets[ident]
            if offsets[ident + 1] - begin == length:
                same = True
                for i in range(length):
                    if pool[begin + i] != scratch[i]:
                        same = False
                        break
                if same:
                    return ident
        at = (at + 1) & mask
    ident = counts[0]
    begin = counts[1]
    for i in range(length):
        pool[begin + i] = scratch[i]
    hashes[ident] = h
    offsets[ident] = begin
    offsets[ident + 1] = begin + length
    counts[0] = ident + 1
    counts[1] = begin + length
    slots[at] = ident
    return ident


@njit(cache=True)
def signatures(starts, entries, head, keys):
    """The signature id of each call. `entries[starts[c]:starts[c + 1]]` are the candidates of call `c`, `keys[e]` the sort key of candidate `e`."""
    calls = head.shape[0]
    total = entries.shape[0]
    longest = 0
    for c in range(calls):
        longest = max(longest, starts[c + 1] - starts[c])
    out = np.empty(calls, dtype=np.int64)
    # the family types: at most one per candidate, their contents at most two values per candidate
    t_slots = np.full(1024, -1, dtype=np.int64)
    t_hashes = np.empty(total + 1, dtype=np.uint64)
    t_offsets = np.empty(total + 2, dtype=np.int64)
    t_pool = np.empty(2 * total + 2, dtype=np.uint64)
    t_counts = np.zeros(2, dtype=np.int64)
    # the signatures: at most one per call, their contents at most the head and one type per candidate
    s_slots = np.full(1024, -1, dtype=np.int64)
    s_hashes = np.empty(calls + 1, dtype=np.uint64)
    s_offsets = np.empty(calls + 2, dtype=np.int64)
    s_pool = np.empty(total + calls + 2, dtype=np.uint64)
    s_counts = np.zeros(2, dtype=np.int64)
    work = np.empty(longest + 1, dtype=np.uint64)
    scratch = np.empty(longest + 2, dtype=np.uint64)
    types = np.empty(longest + 1, dtype=np.uint64)
    for c in range(calls):
        begin = starts[c]
        size = starts[c + 1] - begin
        for i in range(size):
            work[i] = keys[entries[begin + i]]
        ordered = np.sort(work[:size])
        found = 0
        i = 0
        while i < size:
            group = ordered[i] >> GROUP_BITS
            scratch[0] = group & ONE  # the side
            length = 1
            while i < size and ordered[i] >> GROUP_BITS == group:
                scratch[length] = ordered[i] & TRIPLE_MASK
                length += 1
                i += 1
            if (t_counts[0] + 1) * 2 > t_slots.shape[0]:
                t_slots = _grow(t_slots, t_hashes, t_counts[0])
            types[found] = np.uint64(_intern(scratch, length, t_slots, t_hashes, t_offsets, t_pool, t_counts))
            found += 1
        kinds = np.sort(types[:found])
        scratch[0] = np.uint64(head[c])
        for i in range(found):
            scratch[i + 1] = kinds[i]
        if (s_counts[0] + 1) * 2 > s_slots.shape[0]:
            s_slots = _grow(s_slots, s_hashes, s_counts[0])
        out[c] = _intern(scratch, found + 1, s_slots, s_hashes, s_offsets, s_pool, s_counts)
    return out
