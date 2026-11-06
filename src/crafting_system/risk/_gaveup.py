"""What the faster methods of a risk run gave up on, written where they give up (ticket #506, OR-13).

`evaluate` tries the faster methods of the percentile grid first (the free-action count, the coarse grid, the attempt-by-attempt run) and falls
back to the ordinary grid when one cannot take the chain. Each of them has a size limit it states in its own module; when it reaches one it
returns `None` and the next method runs, which used to leave no trace. `note` writes the cause, `collected` gathers the notes of one `evaluate`
into `GridInfo.gave_up`, and `cli._limits.risk_limits` shows them: the answer says why its percentiles came from a slower method.

The notes are a module-level list that only `collected` opens, like `_regen.TRACE`; outside an `evaluate` a note is dropped.
"""

import functools
from contextlib import contextmanager
from dataclasses import replace

_NOTES: list[str] | None = None


def note(text: str) -> None:
    """Write that a faster method gave up, and why (once for the same words)."""
    if _NOTES is not None and text not in _NOTES:
        _NOTES.append(text)


@contextmanager
def collecting():
    """Gather the notes written inside the block; the notes of an outer block are kept apart."""
    global _NOTES
    outer, _NOTES = _NOTES, []
    try:
        yield _NOTES
    finally:
        _NOTES = outer


def collected(function):
    """`function` (returning a `RiskReport`) with the notes written during the call set in `report.grid.gave_up`."""

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        with collecting() as notes:
            report = function(*args, **kwargs)
        if notes:
            report = replace(report, grid=replace(report.grid, gave_up=tuple(notes)))
        return report

    return wrapper
