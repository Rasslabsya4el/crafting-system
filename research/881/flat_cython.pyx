# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True, initializedcheck=False
"""The pool-signature loop on flat arrays, compiled ahead of time by Cython (ticket #881, a prototype; no `src/` change).

The same loop as `flat_numba.signatures` on the same arrays: see that module. Built by `build_cython.py`.
"""

import numpy as np

from libc.stdint cimport int32_t, int64_t, uint64_t
from libc.stdlib cimport qsort

cdef uint64_t MIX = 0x9E3779B97F4A7C15ULL
cdef uint64_t SEED = 0xCBF29CE484222325ULL
cdef int GROUP_SHIFT = 42
cdef uint64_t TRIPLE_MASK = ((<uint64_t>1) << 42) - 1


cdef int _compare(const void* left, const void* right) noexcept nogil:
    cdef uint64_t a = (<const uint64_t*>left)[0]
    cdef uint64_t b = (<const uint64_t*>right)[0]
    return (a > b) - (a < b)


cdef inline uint64_t _hash(uint64_t* values, Py_ssize_t length) noexcept nogil:
    cdef uint64_t h = SEED
    cdef Py_ssize_t i
    for i in range(length):
        h = (h ^ values[i]) * MIX
        h = h ^ (h >> 29)
    return h


cdef class _Table:
    """Contents interned by value: `slots` is an open-addressing table of ids, `pool[offsets[id]:offsets[id + 1]]` the content of an id."""

    cdef object slots_array, hashes_array, offsets_array, pool_array
    cdef int64_t[::1] slots
    cdef uint64_t[::1] hashes
    cdef int64_t[::1] offsets
    cdef uint64_t[::1] pool
    cdef Py_ssize_t count, used

    def __init__(self, Py_ssize_t most_ids, Py_ssize_t most_values):
        self.slots_array = np.full(1024, -1, dtype=np.int64)
        self.hashes_array = np.empty(most_ids + 1, dtype=np.uint64)
        self.offsets_array = np.empty(most_ids + 2, dtype=np.int64)
        self.pool_array = np.empty(most_values + 2, dtype=np.uint64)
        self.slots = self.slots_array
        self.hashes = self.hashes_array
        self.offsets = self.offsets_array
        self.pool = self.pool_array
        self.count = 0
        self.used = 0

    cdef void grow(self):
        cdef Py_ssize_t size = self.slots.shape[0] * 2
        cdef object bigger_array = np.full(size, -1, dtype=np.int64)
        cdef int64_t[::1] bigger = bigger_array
        cdef uint64_t mask = <uint64_t>(size - 1)
        cdef Py_ssize_t ident, at
        for ident in range(self.count):
            at = <Py_ssize_t>(self.hashes[ident] & mask)
            while bigger[at] >= 0:
                at = (at + 1) & <Py_ssize_t>mask
            bigger[at] = ident
        self.slots_array = bigger_array
        self.slots = bigger

    cdef int64_t intern(self, uint64_t* scratch, Py_ssize_t length):
        cdef uint64_t h
        cdef Py_ssize_t mask, at, begin, i
        cdef int64_t ident
        cdef bint same
        if (self.count + 1) * 2 > self.slots.shape[0]:
            self.grow()
        h = _hash(scratch, length)
        mask = self.slots.shape[0] - 1
        at = <Py_ssize_t>(h & <uint64_t>mask)
        while True:
            ident = self.slots[at]
            if ident < 0:
                break
            if self.hashes[ident] == h:
                begin = self.offsets[ident]
                if self.offsets[ident + 1] - begin == length:
                    same = True
                    for i in range(length):
                        if self.pool[begin + i] != scratch[i]:
                            same = False
                            break
                    if same:
                        return ident
            at = (at + 1) & mask
        ident = self.count
        begin = self.used
        for i in range(length):
            self.pool[begin + i] = scratch[i]
        self.hashes[ident] = h
        self.offsets[ident] = begin
        self.offsets[ident + 1] = begin + length
        self.count = ident + 1
        self.used = begin + length
        self.slots[at] = ident
        return ident


def signatures(int64_t[::1] starts, int32_t[::1] entries, int64_t[::1] head, uint64_t[::1] keys):
    """The signature id of each call. `entries[starts[c]:starts[c + 1]]` are the candidates of call `c`, `keys[e]` the sort key of candidate `e`."""
    cdef Py_ssize_t calls = head.shape[0]
    cdef Py_ssize_t total = entries.shape[0]
    cdef Py_ssize_t longest = 0
    cdef Py_ssize_t c, i, begin, size, found, length
    cdef uint64_t group
    for c in range(calls):
        if starts[c + 1] - starts[c] > longest:
            longest = starts[c + 1] - starts[c]
    out_array = np.empty(calls, dtype=np.int64)
    cdef int64_t[::1] out = out_array
    cdef _Table types = _Table(total, 2 * total)
    cdef _Table sigs = _Table(calls, total + calls)
    work_array = np.empty(longest + 1, dtype=np.uint64)
    scratch_array = np.empty(longest + 2, dtype=np.uint64)
    kinds_array = np.empty(longest + 1, dtype=np.uint64)
    cdef uint64_t[::1] work = work_array
    cdef uint64_t[::1] scratch = scratch_array
    cdef uint64_t[::1] kinds = kinds_array
    for c in range(calls):
        begin = starts[c]
        size = starts[c + 1] - begin
        for i in range(size):
            work[i] = keys[entries[begin + i]]
        qsort(&work[0], size, sizeof(uint64_t), _compare)
        found = 0
        i = 0
        while i < size:
            group = work[i] >> GROUP_SHIFT
            scratch[0] = group & 1  # the side
            length = 1
            while i < size and work[i] >> GROUP_SHIFT == group:
                scratch[length] = work[i] & TRIPLE_MASK
                length += 1
                i += 1
            kinds[found] = <uint64_t>types.intern(&scratch[0], length)
            found += 1
        qsort(&kinds[0], found, sizeof(uint64_t), _compare)
        scratch[0] = <uint64_t>head[c]
        for i in range(found):
            scratch[i + 1] = kinds[i]
        out[c] = sigs.intern(&scratch[0], found + 1)
    return out_array
