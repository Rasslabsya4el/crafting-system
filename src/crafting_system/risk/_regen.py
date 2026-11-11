"""Quantiles of a chain that starts over: one attempt at a time (ticket #70).

A craft that is bought again when it goes wrong (`restart`, ADR-0011) returns to its first state over and over. The
cost of the whole craft is then a sum of independent attempts: each attempt runs from the start until it reaches a goal (it
ends there) or comes back to the start (it failed and a new one begins). With g(x) the chance an attempt ends in a goal after
paying x bins and f(x) the chance it comes back to the start after x bins, the total T(x) = P(the craft ends at bin x) obeys the
renewal equation

    T(x) = g(x) + sum over y >= 1 of f(y) T(x - y)        (divided by 1 - f(0) when an attempt may fail for free).

The budget DP then runs on ONE attempt, whose cost is a small part of the whole (R14: a few thousand Chaos against a mean of
5,784 and a p90 of about 11,000), and the sum over attempts is a convolution recursion, not a state space. The attempt chain is
the policy's chain with every edge into the start sent to a sink, run twice: once with the goals as the absorbing states (g)
and once with the sink (f).

Bins are as in `_evaluate`: a step D, the lower chain pays floor(cost / D) bins, the upper one ceil(cost / D), the quantiles of the
two bracket the true one. A cost below D is free on the lower chain and is folded away (`_fold`). The attempt DPs run until the
mass still in flight is below `ATTEMPT_TAIL`, and the answer is refused (None) when the attempts that are cut (the missing mass
over the chance of success) could move a quantile by more than the rounding allowance.

A net bounds the time (ticket #535): the attempt runs of one step get a `deadline`, and a run that is still going then stops
at the last bin it finished, like a run at its cap. Its mass in flight then counts as cut, so the step is refused for it and
said (`TIME_NET`), and the caller keeps the coarser step it had (whose brackets still hold).
"""

import gc
import time
from collections import deque

import numpy as np

from .. import parallel
from ._budget import BudgetRun, run_budget
from ._chain import Chain
from ._fold import FOLD_GAVE_UP, FOLD_LIMIT, fold_free
from ._gaveup import note

TRACE = None  # a caller that wants to see each step of a long run sets this to a function of one line of text (never set by the library)


def trace(text: str) -> None:
    if TRACE is not None:
        TRACE(text)


ATTEMPT_TAIL = 1e-13  # the mass of an attempt that may stay in flight when its DP stops (below it the float sums of the lost mass no longer settle)
MAX_MISSING = 1e-10  # the cut attempts' mass over the chance of success must not exceed this
TIME_NET = "the attempt runs on a step of {:.4g} were stopped at the time limit of {:.0f} s with {:.1e} of an attempt's chance still in flight; this step's percentiles are not used (a coarser one's brackets stand)"


def regeneration_edges(chain: Chain) -> list[int]:
    """The states that can finish and move to the start (state 0) with some chance: where an attempt may end by coming back."""
    return [i for i in chain.finishing_states() if any(j == 0 for j, _ in chain.succ[i])]


def _reaches(succ: tuple[tuple[tuple[int, float], ...], ...], targets: list[int]) -> list[bool]:
    """Which states have a path to one of `targets` (reverse breadth first search)."""
    reverse: list[list[int]] = [[] for _ in succ]
    for i, edges in enumerate(succ):
        for j, _ in edges:
            reverse[j].append(i)
    reached = [False] * len(succ)
    queue = deque(targets)
    for t in targets:
        reached[t] = True
    while queue:
        j = queue.popleft()
        for i in reverse[j]:
            if not reached[i]:
                reached[i] = True
                queue.append(i)
    return reached


def attempt_chain(chain: Chain, *, success: bool) -> Chain:
    """One attempt of `chain`: edges into the start go to a new sink state; its goal states are the chain's (`success`) or the sink alone.

    In the other variant the goals and the states that cannot reach the absorbing state are plain stuck states (their mass is lost).
    """
    n = len(chain.states)
    succ = tuple(tuple((n if j == 0 else j, p) for j, p in edges) for edges in chain.succ) + ((),)
    if success:
        goal = (*chain.goal, False)
        targets = [i for i, flag in enumerate(goal) if flag]
    else:
        goal = (*([False] * n), True)
        targets = [n]
    can_finish = tuple(_reaches(succ, targets))
    # a goal state of the other variant is a state that absorbs nothing here: it keeps no action and cannot finish
    action = (*chain.action, None)
    if not success:
        action = tuple(None if chain.goal[i] else a for i, a in enumerate(chain.action)) + (None,)
        can_finish = tuple(flag and not (i < n and chain.goal[i]) for i, flag in enumerate(can_finish))
    return Chain(
        (*chain.states, None), goal, action, succ, can_finish, (*chain.inputs, ()), chain.packed_moments,
    )  # fmt: skip


def attempt_pmf(
    chain: Chain, bins: list[int], *, success: bool, max_bins: int, deadline: float | None = None
) -> tuple[np.ndarray, float] | None:
    """`(pmf over bins, mass that is neither in it nor lost)` of one attempt ending in a goal (`success`) or back at the start, or None.

    None when a free component is too large to fold (`_fold`). `deadline` (`time.monotonic()`) is the net of `run_budget`.
    """
    attempt = attempt_chain(chain, success=success)
    extended = [*bins, 0]
    if not attempt.can_finish[0]:
        return np.zeros(1), 0.0
    folded = fold_free(attempt, extended)
    if folded is None:
        return None
    run = run_budget(
        folded.chain, extended, target=None, tail_mass=ATTEMPT_TAIL, max_bins=max_bins, initial=folded.initial, goal_mass=folded.goal_mass,
        deadline=deadline,
    )
    cdf = np.asarray(run.cdf)
    trace(f"attempt run ({'goal' if success else 'back to the start'}): {len(cdf):,} bins, in flight at the end {run.unresolved:.3g}")
    return np.diff(cdf, prepend=0.0), run.unresolved


def renewal_cdf(g: np.ndarray, f: np.ndarray, target: float, max_bins: int, allowance) -> list[float]:
    """The cumulative distribution of the total, bin by bin, until it reaches `target` plus the rounding allowance or `max_bins`."""
    gl, fl = len(g), len(f)
    f_reversed = f[::-1].copy()
    stay = 1.0 - float(f[0])
    total = np.zeros(max_bins + 1)
    cdf: list[float] = []
    running = 0.0
    for x in range(max_bins + 1):
        m = min(x, fl - 1)
        value = float(g[x]) if x < gl else 0.0
        if m >= 1:
            value += float(np.dot(f_reversed[fl - 1 - m : fl - 1], total[x - m : x]))
        total[x] = value / stay
        running += total[x]
        cdf.append(running)
        if running >= target + allowance(x):
            break
    return cdf


def regenerative_runs(
    chain: Chain, low_bins: list[int], high_bins: list[int], target: float, max_bins: int, allowance, attempt_bins: int,
    *, seconds: float | None = None, step: float = 0.0,
) -> tuple[BudgetRun, BudgetRun] | None:
    """The lower and the upper chain's `BudgetRun` of the whole craft, from its attempts; None when they cannot be made.

    `seconds` is the time net of the attempt runs (`step` only names the grid in what is said when it stops them).

    Each run's `cdf` is the cumulative distribution of the total in bins up to `target` (or `max_bins`). `unresolved` is the mass beyond.
    """
    distinct = [low_bins] if low_bins == high_bins else [low_bins, high_bins]
    deadline = None if seconds is None else time.monotonic() + seconds
    options = {"max_bins": attempt_bins, "deadline": deadline}
    jobs = [(attempt_pmf, (chain, bins), {"success": success, **options}) for bins in distinct for success in (True, False)]
    found = run_jobs(jobs)  # the attempt runs share nothing: side by side when workers can be forked
    if any(each is None for each in found):
        note(FOLD_GAVE_UP.format(FOLD_LIMIT))  # an attempt cut short by `fold_free`; said here as well, since a forked worker's note is not seen
        return None
    runs: list[BudgetRun] = []
    for k in range(len(distinct)):
        (g, _), (f, _) = found[2 * k], found[2 * k + 1]
        chance = float(g.sum())
        missing = max(0.0, 1.0 - chance - float(f.sum()))
        if deadline is not None and time.monotonic() >= deadline and (chance <= 0.0 or missing > MAX_MISSING * chance):
            note(TIME_NET.format(step, seconds, missing))
            return None
        if chance <= 0.0 or float(f[0]) >= 1.0:
            return None
        if missing / chance > MAX_MISSING:
            note(f"the attempts cut short hold {missing / chance:.1e} of the chance of success, more than the {MAX_MISSING:.0e} the quicker method allows")
            return None
        cdf = renewal_cdf(g, f, target, max_bins, allowance)
        runs.append(BudgetRun(cdf, max(0.0, 1.0 - cdf[-1])))
    return runs[0], runs[-1]


def _held(jobs: dict) -> dict:
    return jobs


def _call(name: str):
    function, args, kwargs = parallel.context()[name]
    return function(*args, **kwargs)


def run_jobs(jobs: list[tuple]) -> list:
    """The results of `(function, args, kwargs)` jobs, in order: side by side in a pool when `CRAFTING_WORKERS` allows and workers can be forked.

    A job is a function of its arguments alone, so the list is the same either way (as `_evaluate._both`); a worker that fails sends the jobs
    back to a serial run here.
    """
    if len(jobs) > 1 and parallel.worker_count() >= 2 and parallel.can_inherit():
        names = [str(i) for i in range(len(jobs))]
        gc.collect()
        gc.freeze()  # the forked workers must not touch the parent's objects (a collection writes to every one of them: a plan holds gigabytes)
        try:
            with parallel.WorkerPool(_held, (dict(zip(names, jobs)),), workers=min(len(jobs), parallel.worker_count())) as pool:
                return pool.map(_call, names, chunk=1)
        except Exception:  # a worker failed or was killed: run them here
            pass
        finally:
            gc.unfreeze()
    return [function(*args, **kwargs) for function, args, kwargs in jobs]
