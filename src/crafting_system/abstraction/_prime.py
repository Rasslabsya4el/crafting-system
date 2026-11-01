"""Label distributions computed ahead of the kernels that need them, in a process pool (ticket #250).

Nearly all the time of a kernel is the exact distribution of the new mods of one pool (`Abstraction._distribution`, or
`_fracture_entries` for a Fractured Fossil), computed once per pool signature and cached. The pools of different
signatures are independent, and a query asks for hundreds of them (R08: every fossil set at the first state). `prime` takes
the (state, action) pairs a caller is about to ask `kernel` for, finds the signatures whose distribution is not cached,
computes them in worker processes and stores them in the caches the kernels read; the serial code that follows finds them
ready. A distribution is a function of its pool alone, so the cache holds the same values whichever process made them
and in whatever order, and `kernel` returns the same dict: nothing here can change an answer.

Workers are forked, one pool per call, so they inherit the abstraction as it is (its caches warm) and the jobs without
pickling anything that goes out; only the distributions come back. Where there is no fork (Windows) `prime` does nothing.
"""

from collections.abc import Iterable

from crafting_system import parallel
from crafting_system.actions import Action, ActionError, Fixed, Rerolled

MIN_JOBS = 2  # fewer uncached pools than this are computed by the kernel call itself


def _hold(abstraction, jobs: list) -> tuple:
    return abstraction, jobs


def _compute(index: int):
    abstraction, jobs = parallel.context()
    (kind, key), (part, signature) = jobs[index]
    if kind == "draw":
        return abstraction._distribution(signature, part)
    return abstraction._fracture_entries(part, signature)


def prime(abstraction, requests: Iterable[tuple[object, Action]], *, workers: int | None = None) -> int:
    """Compute in the pool the distributions that `kernel(state, action)` of these requests needs; return how many.

    A request that `kernel` would refuse is left to `kernel`, which raises it in its own order.
    """
    workers = parallel.worker_count() if workers is None else workers
    if workers < 2 or not parallel.can_inherit():
        return 0
    jobs: dict[tuple, tuple] = {}
    for state, action in requests:
        try:
            abstraction._check_enabled(action)
            prepared = abstraction._prepared(state, action)
            outcomes = prepared.outcomes
            abstraction._check_parts(outcomes)
            signatures = abstraction._signatures_of(prepared)
            for (_, part), signature in zip(outcomes.components, signatures):
                if isinstance(part, (Fixed, Rerolled)):
                    continue
                if outcomes.fractures:
                    abstraction._refuse_rollable_fracture(part, signature)
                    key = (signature, abstraction._forced_label(part))
                    if key not in abstraction._fractures:
                        jobs.setdefault(("fracture", key), (part, signature))
                elif signature not in abstraction._cache:
                    jobs.setdefault(("draw", signature), (part, signature))
        except (ActionError, ValueError):
            continue
    if len(jobs) < MIN_JOBS:
        return 0
    listed = list(jobs.items())
    with parallel.WorkerPool(_hold, (abstraction, listed), workers=min(workers, len(listed))) as pool:
        results = pool.map(_compute, range(len(listed)), chunk=1)
    for ((kind, key), _), result in zip(listed, results):
        if kind == "draw":
            abstraction._cache[key] = result
        else:
            abstraction._fractures[key] = result
        abstraction._kernels += 1
    return len(listed)
