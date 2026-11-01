"""A given route next to the solver's policy: the text section and the `given_route` object of the JSON policy.

The route's numbers carry the start price like the policy's do. A state is named by the id the report
gives it (`S1`, ...); a gap on a state the policy never reaches has no such id and is named `R1`, `R2`, ...
"""

from crafting_system.abstraction import CompressedState
from crafting_system.data import GameData

from ._marking import approximate_inputs, approximate_inputs_document, approximate_lines
from ._report import UNRESOLVED, Report, _estimate, _shifted, describe_state, interval, percent, unresolved
from ._route import Route, RouteResult


def route_state_ids(report: Report, result: RouteResult) -> dict[CompressedState, str]:
    """The report's state ids, plus `R1`, `R2`, ... for the gaps of the route the policy never reaches."""
    ids = dict(report.ids)
    extra = 0
    for gap in result.gaps:
        if gap.state not in ids:
            extra += 1
            ids[gap.state] = f"R{extra}"
    return ids


def render_route_text(report: Report, route: Route, result: RouteResult, data: GameData, *, file_name: str) -> str:
    """The section printed after the policy: the totals side by side, the first divergence and the gaps."""
    plan = report.plan
    ids = route_state_ids(report, result)
    divine = plan.prices.chaos_per_divine
    shift = plan.start_price.chaos
    risk, solver = result.risk, plan.risk
    name = f"{route.name} ({file_name})" if route.name else file_name
    lines = [
        f"Given route: {name}",
        "  (the route is evaluated as a fixed policy at the same prices; the start item is included)",
        f"  success chance  {percent(risk.success_probability.value)}   (policy {percent(solver.success_probability.value)})",
    ]
    for label, given, found in (("mean cost", risk.mean, solver.mean), ("p50", risk.p50, solver.p50), ("p90", risk.p90, solver.p90)):
        lines.append(f"  {label:<15} {_interval(given, shift, divine, risk)}")
        lines.append(f"  {'':<15} (policy {_interval(found, shift, divine, solver)})")
    lines.extend(approximate_lines(approximate_inputs(plan, result.policy, data)))
    lines.append("")
    divergence = result.divergence
    if divergence is None:
        lines.append("No divergence: in every state of the policy's main line the route does what the policy does or has a gap.")
    else:
        lines.append(f"First divergence on the policy's main line: {ids[divergence.state]}")
        lines.append(f"  {describe_state(plan, data, divergence.state)}")
        lines.append(f"  policy does {divergence.solver_action}, route does {divergence.route_action}")
    lines.append("")
    if not result.gaps:
        lines.append("No gaps: every reachable state has an action in the route.")
    else:
        lines.append(f"Gaps: {len(result.gaps)} reachable state(s) where the route does nothing, so it never finishes from there")
        for gap in result.gaps:
            lines.append(f"  {ids[gap.state]}: {describe_state(plan, data, gap.state)}")
            lines.append(f"      {gap.reason}")
    lines.append(f"Route run time: risk.evaluate and route build {result.seconds * 1000:.1f} ms")
    return "\n".join(lines) + "\n"


def _interval(estimate, shift: float, divine: float, risk) -> str:
    return UNRESOLVED if unresolved(risk, estimate) else interval(_shifted(estimate, shift), divine)


def route_document(report: Report, route: Route, result: RouteResult, data: GameData, *, file_name: str) -> dict:
    """The `given_route` object of the JSON policy; costs in Chaos with the start price, `null` for infinity."""
    plan = report.plan
    ids = route_state_ids(report, result)
    shift = plan.start_price.chaos
    risk = result.risk
    divergence = result.divergence
    return {
        "name": route.name,
        "file": file_name,
        "success_probability": _estimate(risk.success_probability),
        "mean_cost": _estimate(risk.mean, shift),
        "p50": _estimate(risk.p50, shift),
        "p90": _estimate(risk.p90, shift),
        "quantiles_resolved": not (unresolved(risk, risk.p50) or unresolved(risk, risk.p90)),
        "approximate_inputs": approximate_inputs_document(approximate_inputs(plan, result.policy, data)),
        "first_divergence": None
        if divergence is None
        else {
            "state": ids[divergence.state],
            "description": describe_state(plan, data, divergence.state),
            "policy_action": divergence.solver_action,
            "route_action": divergence.route_action,
        },
        "gaps": [
            {"state": ids[gap.state], "description": describe_state(plan, data, gap.state), "reason": gap.reason}
            for gap in result.gaps
        ],
        "timings_seconds": {"route_evaluate": result.seconds},
    }
