"""The steps of the text report: the blocks of its tree are the steps of the route page (ticket #488, OR-18, OR-20).

A block is one player action: the item states on which the policy takes the same action, with the exact mixture of their chances and the
branches grouped by the step they lead to. They are made by the page's own code (`_route_view._View`, which reads `_route_flow`), never by a
second pass over the policy, so the report and the page cannot disagree: same steps, same numbers (a step is numbered as the page's row, whose
row 1 is the start item), same titles, same words for what a branch does to the item.

This module is the only reader of `_route_view` that `_report` needs. `_route_view` imports `_report`, so `_report.build_report` imports this
module when it is called and not at the top.
"""

from crafting_system.abstraction import CompressedState
from crafting_system.data import GameData
from crafting_system.planner import Plan

from ._report import ReportStep, StepOutcome, state_parts
from ._route_view import _View, route_input

NO_ACTION = "no action"


def report_steps(plan: Plan, data: GameData) -> tuple[tuple[ReportStep, ...], dict[CompressedState, int]]:
    """One `ReportStep` for each step of the plan's policy, in the page's order (none when the start item already meets the target), and the
    page's row of every item state the policy reaches."""
    view = _View(route_input(plan), data, None, "", False)
    return tuple(_step(view, step) for step in view.flow.steps), {state: number + 1 for state, number in view.flow.step_of.items()}


def _title(view: _View, number: int) -> str:
    """The title of the step with the flow number `number` (from 1), as the page's row is titled."""
    action = view.flow.steps[number - 1].action
    return NO_ACTION if action is None else view.title(action)


def _step(view: _View, step) -> ReportStep:
    plan, data = view.plan, view.data
    number = step.number + 1
    items = len(step.states)
    item = _shared_parts(plan, data, step.states)
    if step.action is None:
        return ReportStep(number, "No action", items, item, reason=step.reason or "", acts=False, reached=step.reached)
    return ReportStep(
        number, _ascii(view.title(step.action)), items, item,
        cost_parts=plan.offer_of(step.action).parts, cost_marks=plan.offer_of(step.action).marks, cost=step.cost,
        uses=step.uses, step_cost=step.step_cost, never=step.never_finishes, reached=step.reached,
        outcomes=tuple(StepOutcome(edge.chance, _outcome(view, step, edge)) for edge in step.edges),
    )  # fmt: skip


def _shared_parts(plan: Plan, data: GameData, states) -> str:
    """The parts of the line on an item that all of `states` have, in the order of the first (the whole line for one state)."""
    common = state_parts(plan, data, states[0])
    for state in states[1:]:
        if not common:
            break
        parts = set(state_parts(plan, data, state))
        common = [part for part in common if part in parts]
    return "; ".join(common)


def _ascii(text: str) -> str:
    """The page's words in the report's ASCII: the dot between a mod and its tier ("... Life · T1") is a comma."""
    return text.replace(" · ", ", ")


def _outcome(view: _View, step, edge) -> str:
    """What one branch of the step does, in the page's words, and the step it leads on to."""
    what, names_row = view.edge_phrase(step, edge)
    if edge.to is None or edge.kind == "again":
        return _ascii(what)
    there = f"step {edge.to + 1}: {_title(view, edge.to)}"
    return _ascii(there if names_row else f"{what}; next {there}")  # a phrase that only names the step ("the item of step 4", "the item is restarted") is the step
