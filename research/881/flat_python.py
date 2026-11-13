"""The pool-signature loop on flat data in plain Python (ticket #881, a prototype; no `src/` change).

The same inputs as `flat_numba.signatures`, as Python lists: what the flat tables alone buy, before any compiler. A family type is the tuple
of its side and its sorted `label << 21 | weight << 1 | flag` values, a signature the tuple of the call's head and its sorted type ids; both
are interned in a dict, so equal contents get one id.
"""

GROUP_SHIFT = 42
TRIPLE_MASK = (1 << GROUP_SHIFT) - 1


def signatures(starts: list[int], entries: list[int], head: list[int], keys: list[int]) -> list[int]:
    types: dict[tuple, int] = {}
    found: dict[tuple, int] = {}
    out = []
    for call, first in enumerate(head):
        ordered = sorted([keys[entry] for entry in entries[starts[call] : starts[call + 1]]])
        kinds = []
        group = -1
        run: list[int] = []
        for key in ordered:
            if key >> GROUP_SHIFT != group:
                if run:
                    kinds.append(types.setdefault((group & 1, *run), len(types)))
                group = key >> GROUP_SHIFT
                run = []
            run.append(key & TRIPLE_MASK)
        if run:
            kinds.append(types.setdefault((group & 1, *run), len(types)))
        kinds.sort()
        out.append(found.setdefault((first, *kinds), len(found)))
    return out
