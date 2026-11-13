"""What the presenter of a plan cannot show of it: the seam through which those limits reach `Plan.limits` (ticket #880, issue #882).

A finished plan lists, among its limits, what the report and the route page leave out of the chance of reaching a state and of the
steps of the policy (`_plan.display_limits`; C15, V8, #466). The maths that finds them is the page's own (`cli/_reach.py`,
`cli/_route_flow.py`, `cli/_route_chain.py`); it stays in `cli` until it gets its own ticket, and the planner may not import `cli`
(ADR-0018). So the presenter hands the planner the function: `cli` calls `present_with` when it is imported, and a finished plan
asks `presenter_limits`. With no presenter named, finishing a plan is an error and not a plan with fewer limits: the same target must give
the same `Plan.limits` wherever it is planned, and a caller that presents nothing says so itself (`present_with(lambda plan: ())`).
"""

from collections.abc import Callable, Iterable
from typing import Any

from ._limits import Limit

_SOURCE: Callable[[Any], Iterable[Limit]] | None = None  # set once, by the presenter's package when it is imported; never by the planner


def present_with(source: Callable[[Any], Iterable[Limit]] | None) -> None:
    """Name the function that tells, for a finished plan, what its presenter cannot show of it (None: no presenter is named any more)."""
    global _SOURCE
    _SOURCE = source


def presenter_limits(plan: Any) -> tuple[Limit, ...]:
    """The limits the presenter states for `plan`, in its order. Raises `RuntimeError` when no presenter is named (a fault of the caller's
    set-up, not a refusal of the target, so it is no `PlanError`)."""
    if _SOURCE is None:
        raise RuntimeError(
            "no presenter of plans is named: a finished plan lists what its presenter cannot show of it (issue #882). "
            "Import `crafting_system.cli`, which names its page, or call `crafting_system.planner.present_with` before planning"
        )
    return tuple(_SOURCE(plan))
