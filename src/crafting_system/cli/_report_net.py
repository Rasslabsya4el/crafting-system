"""The memory net of the report and the route page of a finished plan (ticket #1381; OR-39, OR-40, OR-56).

The planner stops each of its phases at the run's memory net and says so (`budget`, #825). The report, the JSON policy and the route page of
the plan are built after the planner has returned, so its net no longer watched them: R20's plan of 2026-11-21 (570,663 item states, a lumped
view of 28,773 blocks) was made in 3 h 50 min under a net of 12 GB, and the kernel then killed the run at 16.7 GB while its report was built
(the expected uses of the prices, solved dense on each cycle of the view, #1381). The answer was lost with nothing said.

So the plan's record is written first, from the plan alone (`_report.plan_record`), and the outputs are then built inside `report_net`, which
holds the run's own memory net (the planner settings of the machine, OR-40: never a figure sized for one machine). Their loops ask it
(`ask`) as the planner's phases ask theirs, with the same clock and the same words (`budget.Clock.check`): past the net they stop with
`BudgetExceeded`, whose binding says where ("the report and the route page stopped at the memory limit of 12,288 MB (12,301 MB held): ..."),
and the caller says so beside the record it wrote. Outside `report_net` (the planner's own call of the page's maths for the limits of a
finished plan, `_page_limits`, and every test) `ask` does nothing: the planner's net and clock are not this one, and a time net the plan has
spent must not stop the report.

Only memory is watched: the plan is made, and building what shows it takes seconds to minutes, not a share of the time net (OR-39).
"""

import contextlib
import contextvars
from collections.abc import Iterator

from crafting_system.budget import Budget, BudgetExceeded, Clock

STAGE = "the report and the route page"
KEPT = "the plan's record is written; what was not built is not shown"  # what a stop leaves (OR-13)

_clock: contextvars.ContextVar[Clock | None] = contextvars.ContextVar("crafting_system_report_net", default=None)


@contextlib.contextmanager
def report_net(memory_mb: float | None) -> Iterator[Clock | None]:
    """Watch the memory of the block against `memory_mb` (None: no net, `ask` does nothing). The clock of the block has no time net."""
    if memory_mb is None:
        yield None
        return
    clock = Budget(aim_seconds=None, seconds=None, memory_mb=memory_mb).start()
    token = _clock.set(clock)
    try:
        yield clock
    finally:
        _clock.reset(token)


def ask(what: str = KEPT, *, fresh: bool = False) -> None:
    """Raise `BudgetExceeded` when the process holds the report's memory net or more, read at most every `budget.MEMORY_POLL_SECONDS` in a
    loop, and read now with `fresh` (the start of each output: the report, the page, what a benchmark adds); nothing outside `report_net`."""
    clock = _clock.get()
    if clock is not None:
        if fresh:
            clock.memory(fresh=True)
        clock.check(STAGE, what)


__all__ = ["KEPT", "STAGE", "BudgetExceeded", "ask", "report_net"]
