"""What the report and the route page cannot show of a finished plan, as the limits the planner writes into `Plan.limits` (ticket #880, issue #882).

The chance of reaching each state is not computed above `_reach.MAX_TRANSIENT` states that can be left (C15, V8), and the steps of the
policy have numbers the page cannot give (`_route_flow.flow_limits`, #466). The planner asks for them when a plan is finished
(`planner.present_with`, named in this package's `__init__`), because the maths is the page's and lives here.
"""

from crafting_system.planner import Limit, Plan

from ._reach import reach_limit
from ._route_chain import chain_of_plan
from ._route_flow import flow_limits


def page_limits(plan: Plan) -> tuple[Limit, ...]:
    """The reach limit of `plan`'s policy, when it has one, then what the route page cannot say of its steps."""
    reach = reach_limit(plan.start, plan.view_policy, plan.is_goal)
    return (*(() if reach is None else (reach,)), *flow_limits(chain_of_plan(plan)))
