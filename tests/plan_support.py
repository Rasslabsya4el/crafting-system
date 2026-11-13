"""A hand-made plan for a test that draws a page, with the limits the planner gives a real one (ticket #550, OR-13).

A real plan always leaves something out: `plan_for` starts from `strands_limit()`, adds `start_limits(...)` for the start item and
`finished(...)` adds what only the finished policy can tell (the model gaps, the pruned offers, what a state line and the steps show). A
fixture that built `Plan(..., limits=())` drew pages no run could produce, and the route page then claimed "Cheapest policy of the
planner" with no part "What this answer leaves out". `planner_plan` takes every field of `Plan` but `limits` and gets them from the same
functions the planner uses; the page builder refuses a plan with none (`PageError`).

What a fixture still does not have is the limits of the offers it did not choose (`offers_for`), since it names its offers by hand: issue #638.
"""

from dataclasses import replace

from crafting_system.planner._plan import Plan, finished, start_limits, strands_limit


def planner_plan(**fields) -> Plan:
    """`Plan(**fields)` with `limits` as `plan_for` writes them for a plan whose offers were given."""
    bare = Plan(limits=(), **fields)
    return finished(replace(bare, limits=(strands_limit(), *start_limits(bare.start_price))))
