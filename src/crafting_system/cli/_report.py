"""The two outputs of a plan: the short text tree for the terminal and the JSON policy (ADR-0015).

Both are built from the same `Report`: the states the policy can reach, numbered `S1`, `S2`, ... in
breadth-first order from the start (a goal is just "goal"), what is done in each, the chance of each
transition, the expected cost still to pay and the chance the policy ever gets there. Text is ASCII
only, so it prints on any console. Costs are in Chaos Orbs with a Divine Orb equivalent.
"""

import math
from dataclasses import dataclass
from fractions import Fraction

from crafting_system.abstraction import CompressedState, Status
from crafting_system.data import GameData
from crafting_system.items import Side
from crafting_system.risk import Estimate
from crafting_system.targets import KOfN

from ._marking import (
    ApproximateInput,
    approximate_inputs,
    approximate_inputs_document,
    approximate_lines,
    marking_document,
    marking_lines,
    risk_lines,
    verification_document,
    verification_lines,
)
from ._offers import without_ranges
from ._plan import Plan, chance
from ._reach import policy_states, reach_probabilities
from ._shares import WeightShare, start_shares
from ._verify import SIGMAS, Verification

FORMAT = "crafting-system-policy/1"
GOAL = "goal"
DEAD_END = "dead end"
MAX_TREE_DEPTH = 40

MAX_DROPPED_LINES = 8  # more dropped actions than this are told in one line per missing price


@dataclass(frozen=True)
class Transition:
    to: str  # a state id, GOAL or DEAD_END
    chance: float


@dataclass(frozen=True)
class PolicyState:
    id: str
    description: str
    action: str
    cost: float  # Chaos per use
    cost_parts: tuple[tuple[str, int, float, str], ...]
    remaining: float  # expected cost still to pay from here
    reach: float | None  # the chance the policy ever gets here
    per_use_goal: float  # the chance one use ends in a goal
    transitions: tuple[Transition, ...]


@dataclass(frozen=True)
class Report:
    plan: Plan
    ids: dict[CompressedState, str]
    states: tuple[PolicyState, ...]
    shares: tuple[tuple[WeightShare, float | None], ...]  # a share and the kernel's per-use chance of the leaf
    approximate_inputs: tuple[ApproximateInput, ...] = ()  # the approximate claims the policy's actions read (ADR-0028)


def _goal_leaf_nodes(plan: Plan) -> list[tuple[str, frozenset[str]]]:
    """(label, mod ids) of each requirement leaf of the target, in goal order."""
    leaves: list[frozenset[str]] = []

    def walk(node) -> None:
        if isinstance(node, KOfN):
            for member in node.of:
                walk(member)
        else:
            leaves.append(node.mod_ids)

    for requirement in plan.target.requirements:
        walk(requirement)
    return list(zip(plan.leaf_labels, leaves))


def describe_state(plan: Plan, data: GameData, state: CompressedState) -> str:
    """One line on a state: rarity, the fractured mods, what each requirement leaf stands at, and the crafted and other mods.

    The mods besides the fractured ones show only when the model tracks them (a bench action is offered):
    the crafted mods by their text, and the rest as a count per side ("junk: 1 prefix, 2 suffixes").
    """
    parts = [state.flags.rarity.value]
    for entry in state.fractured:
        mod = _fractured_mod_shown(plan, data, entry.mod_id)
        parts.append(f"fractured {_without_ranges(mod.text or mod.name)}")
    for label, status in zip(plan.leaf_labels, state.status):
        verb = {Status.PASSING: "has", Status.BELOW: "too weak:", Status.ABSENT: "lacks"}[status]
        parts.append(f"{verb} {label}")
    for slot in state.slots:
        if slot.crafted:
            mod = data.mods.get(slot.kind)
            if mod is None:  # a block pools the crafted mods of its irrelevant families under one kind
                parts.append(f"crafted mod of {slot.side.value} (a family no requirement cares about)")
            else:
                parts.append(f"crafted {_without_ranges(mod.text or mod.name)}")
    junk = [slot for slot in state.slots if not slot.crafted]
    if junk:
        shown = [f"{n} {side.value}{'' if n == 1 else 'es'}" for side in Side if (n := sum(s.side is side for s in junk))]
        parts.append("other mods: " + ", ".join(shown))
    return "; ".join(parts)


_without_ranges = without_ranges


def _fractured_mod_shown(plan: Plan, data: GameData, canonical_id: str):
    """The mod to show for a fractured entry of a state: the start item's own mod of that family when it has one.

    A state keeps the smallest id among equivalent mods, which can read quite unlike the mod on the item
    (another mod of the same family), so the start item's fractured mod is the better name for it.
    """
    families = data.mods[canonical_id].families
    for held in plan.target.start_item.fractured_mods:
        if data.mods[held.mod_id].families == families:
            return data.mods[held.mod_id]
    return data.mods[canonical_id]


def number_states(plan: Plan) -> dict[CompressedState, str]:
    """`S1`, `S2`, ... for the non-goal states the policy can reach, in breadth-first order from the start."""
    ids: dict[CompressedState, str] = {}
    for state in policy_states(plan.start, plan.policy, plan.is_goal):
        if not plan.is_goal(state):
            ids[state] = f"S{len(ids) + 1}"
    return ids


def build_report(plan: Plan, data: GameData) -> Report:
    """Number the reachable states and collect what each one does."""
    order = policy_states(plan.start, plan.policy, plan.is_goal)
    ids = number_states(plan)
    reach = reach_probabilities(plan.start, plan.policy, plan.is_goal)

    states = []
    for state in order:
        action = plan.policy.get(state)
        if plan.is_goal(state) or action is None:
            continue
        priced = plan.offer_of(action)
        total = sum(weight for _, weight in action.outcomes)
        transitions = []
        per_use_goal = 0.0
        for successor, weight in action.outcomes:
            if weight <= 0:
                continue
            if plan.is_goal(successor):
                target = GOAL
                per_use_goal += chance(weight, total)
            else:
                target = ids[successor]
            transitions.append(Transition(target, chance(weight, total)))
        transitions.sort(key=lambda t: (t.to != GOAL, -t.chance))
        states.append(
            PolicyState(
                ids[state], describe_state(plan, data, state), priced.label, priced.cost, priced.parts,
                plan.solution.values[state], None if reach is None else reach.get(state),
                per_use_goal, tuple(transitions),
            )
        )  # fmt: skip
    offers = [priced.offer for priced in plan.offers if priced.offer.shares]
    shares = start_shares(data, plan.target.start_item, offers, _goal_leaf_nodes(plan))
    return Report(
        plan, ids, tuple(states), tuple((share, _leaf_chance(plan, share)) for share in shares),
        approximate_inputs(plan, plan.policy, data),
    )  # fmt: skip


def _leaf_chance(plan: Plan, share: WeightShare) -> float | None:
    """The chance that one use of the share's action on the start state leaves the share's leaf met."""
    offer = next(p for p in plan.offers if p.label == share.action)
    leaf = plan.leaf_labels.index(share.leaf)
    try:
        kernel = plan.abstraction.kernel(plan.start, offer.offer.action)
    except ValueError:
        return None
    return float(sum((c for state, c in kernel.items() if state.status[leaf] is Status.PASSING), Fraction(0)))


# --- text ----------------------------------------------------------------------------------------


def money(chaos: float) -> str:
    return "never" if math.isinf(chaos) else f"{chaos:,.2f}"


def percent(value: float) -> str:
    """A chance as a percentage with enough digits to tell small chances apart."""
    if value >= 1.0 - 1e-12:
        return "100%"
    if value >= 0.01:
        return f"{value * 100:.2f}%"
    return f"{value * 100:.4g}%"


def interval(estimate: Estimate, divine: float) -> str:
    value = money(estimate.value)
    if math.isinf(estimate.value):
        return value
    text = f"{value} Chaos ({estimate.value / divine:.3g} Divine)"
    if estimate.high - estimate.low > 1e-6 * max(1.0, abs(estimate.value)):
        text += f", certified {money(estimate.low)} to {money(estimate.high)}"
    return text


UNRESOLVED = "not resolved on the grid (the cost scale is far above the cheapest action, ticket #190)"


def unresolved(risk, estimate: Estimate) -> bool:
    """Whether a quantile or CVaR is infinite only because the budget grid could not reach it: the odds are 1."""
    return math.isinf(estimate.value) and risk.success_probability.value >= 1.0


def _quantile_text(risk, estimate: Estimate, shift: float, divine: float) -> str:
    return UNRESOLVED if unresolved(risk, estimate) else interval(_shifted(estimate, shift), divine)


def _shifted(estimate: Estimate, shift: float) -> Estimate:
    return Estimate(estimate.value + shift, estimate.low + shift, estimate.high + shift)


def render_text(report: Report, verification: Verification | None = None, *, target_name: str = "") -> str:
    """The terminal report: inputs, the policy as a tree, the totals and, with `--verify`, the check."""
    plan = report.plan
    divine = plan.prices.chaos_per_divine
    risk = plan.risk
    shift = plan.start_price.chaos
    lines = []
    if target_name:
        lines.append(f"Target: {target_name}")
    lines.extend(marking_lines(plan.approximation, shift, divine))
    lines.extend(approximate_lines(report.approximate_inputs))
    if plan.note:
        lines.append(f"Note: {plan.note}")
    lines.append(f"Requirements: {'; '.join(plan.leaf_labels)}")
    lines.append(
        f"Prices: league {plan.prices.league}, fetched {plan.prices.fetched_at:%Y-%m-%d}, "
        f"1 Divine = {divine:,.2f} Chaos"
    )
    name = f" ({plan.start_price.name})" if plan.start_price.name else ""
    lines.append(f"Start item{name}: {money(shift)} Chaos [{plan.start_price.source}]")
    if len(plan.dropped) <= MAX_DROPPED_LINES:
        for dropped in plan.dropped:
            lines.append(f"Dropped for lack of a price: {dropped.label} (no price for {', '.join(dropped.missing)})")
    else:  # thousands of fossil sets can share one missing price: one line for each missing price
        by_missing: dict[tuple[str, ...], list[str]] = {}
        for dropped in plan.dropped:
            by_missing.setdefault(dropped.missing, []).append(dropped.label)
        for missing, labels in by_missing.items():
            shown = ", ".join(labels[:3]) + (", ..." if len(labels) > 3 else "")
            lines.append(f"Dropped for lack of a price, {len(labels)} actions (no price for {', '.join(missing)}): {shown}")
    for left in plan.left_out:
        lines.append(f"Not offered, {len(left.labels)} actions: {left.reason}")
    lines.append(f"Blocks solved: {plan.approximation.blocks:,}" if plan.approximation else f"States solved: {len(plan.solution.values)}")
    lines.append("")
    lines.append("Policy (S = a state of the item; the start is S1)")
    printed: set[str] = set()
    by_id = {state.id: state for state in report.states}
    pending: list[str] = [report.ids[plan.start]] if plan.start in report.ids else []

    def show(state_id: str, depth: int) -> None:
        state = by_id[state_id]
        pad = "    " * depth
        printed.add(state_id)
        reach = "" if state.reach is None else f", reached with chance {percent(state.reach)}"
        lines.append(f"{pad}{state.id}: {state.description}")
        parts = " + ".join(f"{count} {resource}" for resource, count, _, _ in state.cost_parts)
        lines.append(f"{pad}  do: {state.action} ({parts} = {money(state.cost)} Chaos each)")
        lines.append(f"{pad}  expected cost from here {money(state.remaining)} Chaos{reach}")
        later = []
        for transition in state.transitions:
            if transition.to == GOAL:
                what = "goal reached"
            elif transition.to == state.id:
                what = f"nothing gained, back to {state.id}"
            elif transition.to not in by_id:
                what = f"{transition.to} (a dead end: no action is left there)"
            elif transition.to in printed:
                what = f"{transition.to} (shown above)"
            else:
                what = transition.to
                later.append(transition.to)
            lines.append(f"{pad}  {percent(transition.chance):>8}  {what}")
        for child in later:
            if child in printed:
                continue
            if depth >= MAX_TREE_DEPTH:
                lines.append(f"{pad}  ... {child} continues below")
                pending.append(child)
            else:
                show(child, depth + 1)

    while pending:
        root = pending.pop(0)
        if root not in printed:
            show(root, 0)
    if not report.states:
        lines.append("  The start item already meets the target.")
    lines.append("")
    lines.append("Result")
    if risk is None:
        mean = Estimate(plan.mean_remaining + shift, plan.approximation.lower + shift, plan.approximation.upper + shift)
        lines.append(f"  mean cost       {interval(mean, divine)} (the policy's certified cost; see Answer)")
        lines.extend(risk_lines())
        lines.append(f"  (the start item, {money(shift)} Chaos, is included)")
    else:
        lines.append(f"  success chance  {percent(risk.success_probability.value)}")
        lines.append(f"  mean cost       {interval(_shifted(risk.mean, shift), divine)}")
        lines.append(f"  p50             {_quantile_text(risk, risk.p50, shift, divine)}")
        lines.append(f"  p90             {_quantile_text(risk, risk.p90, shift, divine)}")
        lines.append(f"  (the start item, {money(shift)} Chaos, is included; the cost left to pay after buying it is")
        lines.append(f"   {money(plan.mean_remaining)} Chaos by the solver and {money(risk.mean.value)} by the risk run)")
    if report.shares:
        lines.append("")
        lines.append("Single-draw weight shares on the start item, next to the chance of one use")
        lines.append("  (a share is the wanted weight over the candidate weight of ONE draw, as guides quote it;")
        lines.append("   the chance of one use counts every draw of the use and is not the guide's number)")
        for share, use in report.shares:
            weight = f"{_count(share.wanted)}/{_count(share.total)} = {percent(float(share.share))}"
            suffix = "" if use is None else f"; chance of one use {percent(use)}"
            lines.append(f"  {share.action}: {share.leaf}: {weight}{suffix}")
    lines.append("")
    if risk is None:
        lines.append(f"Run time: both solvers {plan.solve_seconds * 1000:.0f} ms")
    else:
        lines.append(f"Run time: solver {plan.solve_seconds * 1000:.0f} ms, risk.evaluate {plan.risk_seconds * 1000:.1f} ms")
    if verification is not None:
        lines.append("")
        lines.extend(verification_lines(verification) if plan.approximation else _verification_lines(verification, plan))
    return "\n".join(lines) + "\n"


def _count(value: Fraction) -> str:
    return f"{int(value):,}" if value.denominator == 1 else f"{float(value):,.3f}"


def _verification_lines(check: Verification, plan: Plan) -> list[str]:
    report = check.report
    cost = report.cost
    p90 = check.p90
    divine = plan.prices.chaos_per_divine
    computed_p90 = UNRESOLVED if unresolved(plan.risk, plan.risk.p90) else money(check.computed_p90)
    return [
        f"Verification by simulation ({check.runs:,} runs, seed {check.seed}, at most {check.max_steps:,} uses per run)",
        f"  simulated mean cost {money(cost.value)} Chaos, {report.confidence:.0%} interval "
        f"{money(cost.low)} to {money(cost.high)} (normal approximation)",
        f"  computed mean cost  {money(check.computed_mean)} Chaos ({check.computed_mean / divine:.3g} Divine)",
        f"  simulated p90       {money(p90.value)} Chaos, interval {money(p90.low)} to {money(p90.high)} "
        f"(simulated, not certified); computed {computed_p90}",
        f"  detectable error    a mean off by more than {check.detectable_error:.1%} is rejected "
        f"({SIGMAS:g} standard errors); a smaller error passes; more --runs see smaller ones",
        f"  successes {report.successes:,} of {report.runs:,}, mean uses per run {report.mean_steps:.1f}",
        "  " + ("AGREES with the computed mean" if check.agrees else f"DOES NOT AGREE: {check.reason}"),
    ]


# --- JSON ----------------------------------------------------------------------------------------


def _number(value: float) -> float | None:
    """A float for JSON: infinity has no JSON form, so it becomes null."""
    return None if math.isinf(value) or math.isnan(value) else value


def _estimate(estimate: Estimate, shift: float = 0.0) -> dict:
    return {
        "value": _number(estimate.value + shift),
        "low": _number(estimate.low + shift),
        "high": _number(estimate.high + shift),
    }


def _weight(value: Fraction) -> int | float:
    return int(value) if value.denominator == 1 else float(value)


def _totals(plan: Plan, shift: float, divine: float) -> dict:
    """The totals of the JSON: the odds and percentiles of an exact answer, only the certified interval of an approximate one."""
    risk = plan.risk
    if risk is None:
        mean = Estimate(plan.mean_remaining, plan.approximation.lower, plan.approximation.upper)
        return {
            "mean_cost": _estimate(mean, shift),
            "mean_cost_divine": _number((plan.mean_remaining + shift) / divine),
            "mean_cost_without_start": _number(plan.mean_remaining),
            "solver_error_bound": _number(plan.solution.error_bound),
        }
    return {
        "success_probability": _estimate(risk.success_probability),
        "mean_cost": _estimate(risk.mean, shift),
        "p50": _estimate(risk.p50, shift),
        "p90": _estimate(risk.p90, shift),
        "quantiles_resolved": not (unresolved(risk, risk.p50) or unresolved(risk, risk.p90)),
        "cvar_level": risk.cvar_level,
        "cvar": _estimate(risk.cvar, shift),
        "mean_cost_divine": _number((risk.mean.value + shift) / divine),
        "p90_divine": _number((risk.p90.value + shift) / divine),
        "mean_cost_without_start": _number(plan.mean_remaining),
        "solver_error_bound": _number(plan.solution.error_bound),
    }


def policy_document(report: Report, verification: Verification | None = None, *, target_name: str = "") -> dict:
    """The JSON policy: what to do in each reachable state, the transitions, and the totals.

    Every cost is in Chaos Orbs. `null` stands for infinity (JSON has none).
    """
    plan = report.plan
    risk = plan.risk
    shift = plan.start_price.chaos
    divine = plan.prices.chaos_per_divine
    document: dict = {
        "format": FORMAT,
        "unit": "chaos",
        "answer": marking_document(plan.approximation, shift),
        "approximate_inputs": approximate_inputs_document(report.approximate_inputs),
        "note": plan.note,
        "target": target_name,
        "requirements": list(plan.leaf_labels),
        "prices": {
            "league": plan.prices.league,
            "fetched_at": plan.prices.fetched_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "chaos_per_divine": divine,
        },
        "start": {
            "state": report.ids.get(plan.start, GOAL),
            "price_name": plan.start_price.name,
            "price_chaos": shift,
            "price_source": plan.start_price.source,
        },
        "dropped_actions": [{"action": drop.label, "missing_prices": list(drop.missing)} for drop in plan.dropped],
        "left_out_actions": [
            {"reason": left.reason, "count": len(left.labels), "actions": list(left.labels)} for left in plan.left_out
        ],
        "offered_actions": [priced.label for priced in plan.offers],
        "states_solved": len(plan.solution.values),
        "totals": _totals(plan, shift, divine),
        "states": [
            {
                "id": state.id,
                "description": state.description,
                "action": state.action,
                "cost_per_use": state.cost,
                "resources": [
                    {"name": name, "count": count, "chaos": chaos, "price_source": source}
                    for name, count, chaos, source in state.cost_parts
                ],
                "expected_remaining_cost": _number(state.remaining),
                "reach_probability": state.reach,
                "goal_chance_per_use": state.per_use_goal,
                "transitions": [{"to": t.to, "probability": t.chance} for t in state.transitions],
            }
            for state in report.states
        ],
        "single_draw_shares": [
            {
                "action": share.action,
                "requirement": share.leaf,
                "wanted_weight": _weight(share.wanted),
                "candidate_weight": _weight(share.total),
                "share": float(share.share),
                "chance_of_one_use": use,
            }
            for share, use in report.shares
        ],
        "timings_seconds": {"solver": plan.solve_seconds, "risk_evaluate": None if risk is None else plan.risk_seconds},
    }
    if verification is not None:
        sim = verification.report
        if plan.approximation is not None:
            document["verification"] = verification_document(verification)
            return document
        document["verification"] = {
            "runs": verification.runs,
            "seed": verification.seed,
            "max_steps": verification.max_steps,
            "interval": f"{sim.confidence:.0%}, normal approximation",
            "simulated_mean_cost": {
                "value": sim.cost.value,
                "standard_error": sim.cost.standard_error,
                "low": sim.cost.low,
                "high": sim.cost.high,
            },
            "computed_mean_cost": verification.computed_mean,
            "simulated_p90": {
                "value": verification.p90.value,
                "low": verification.p90.low,
                "high": verification.p90.high,
            },
            "computed_p90": None if verification.computed_p90 is None else _number(verification.computed_p90),
            "successes": sim.successes,
            "unfinished": sim.unfinished,
            "stopped": sim.stopped,
            "detectable_relative_error": verification.detectable_error,
            "agrees": verification.agrees,
            "reason": verification.reason,
        }
    return document
