"""The two outputs of a plan: the short text tree for the terminal and the JSON policy (ADR-0015).

Both are built from the same `Report`. The JSON policy lists the states the policy can reach, numbered `S1`, `S2`, ... in
breadth-first order from the start (a goal is just "goal"), what is done in each, the chance of each
transition, the expected cost still to pay and the chance the policy ever gets there. The text tree is made of the steps of the route page
instead (`Report.steps`, `_report_steps`): one block for each action the player takes, with the exact mixture of the chances of the states that
take it (ticket #488, OR-18, OR-20). Text is ASCII only, so it prints on any console. Costs are in Chaos Orbs with a Divine Orb equivalent.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from fractions import Fraction

from crafting_system.abstraction import CompressedState, Status
from crafting_system.data import GameData
from crafting_system.items import Side
from crafting_system.risk import Estimate
from crafting_system.targets import KOfN, plain_base_names

from ._interval import IntervalAnswer
from ._limits import HEADING, PERCENTILE_WORDS, figures, limit_document, limit_text, ordered, unresolved
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
from ._route_card import leaf_sides
from ._reach import policy_states, reach_probabilities
from ._shares import WeightShare, start_shares
from ._start_report import first_step_document, first_step_lines, start_document, start_lines
from ._start_step import FirstStep, first_step
from ._verify import SIGMAS, Verification

FORMAT = "crafting-system-policy/3"  # /3: `requirements` keeps the k-of-n groups (ticket #630); /2 listed every leaf flat
POLICY_HEADING = "Policy (one block for each action you take, numbered as the steps of the route page; step 1 is the start item)"
GOAL = "goal"
DEAD_END = "dead end"
RESULT_ROWS = ("success", "mean", "p50", "p90")  # the rows of the result block, as the keys of `PERCENTILE_WORDS` name them
ROW_WIDTH = max(len(PERCENTILE_WORDS[name]) for name in RESULT_ROWS) + 2  # a row says its figure in words, then the value in this column


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
class StepOutcome:
    chance: float  # the exact mixture over the step's states of the chance of this branch for one use
    text: str  # what the branch does to the item, in the page's words, and the step it leads on to


@dataclass(frozen=True)
class ReportStep:
    """One block of the text tree: a step of the route page (`number` is its row, whose row 1 is the start item).

    `item` describes the item: the line of the state when exactly one takes the action here, else the parts of the line that all `items` states
    share (empty when they share none). A step with no action (`acts` False)
    says why in `reason` (empty when the policy gave none).
    `uses` is the expected number of uses in one run (None when not solved), `never` that the step cannot finish, `reached` the chance a run
    enters the step.
    """

    number: int
    title: str
    items: int
    item: str
    reason: str = ""
    acts: bool = True
    cost_parts: tuple[tuple[str, int, float, str], ...] = ()
    cost: float = 0.0
    uses: float | None = None
    step_cost: float | None = None
    never: bool = False
    reached: float | None = None
    outcomes: tuple[StepOutcome, ...] = ()


@dataclass(frozen=True)
class Report:
    plan: Plan
    ids: dict[CompressedState, str]
    states: tuple[PolicyState, ...]
    shares: tuple[tuple[WeightShare, float | None], ...]  # a share and the kernel's per-use chance of the leaf
    approximate_inputs: tuple[ApproximateInput, ...] = ()  # the approximate claims the policy's actions read (ADR-0028)
    first_step: FirstStep | None = None  # what is done before S1 when the start item is made at a vendor (ADR-0059, ticket #331)
    interval: IntervalAnswer | None = None  # the plan's interval over a rule axis it reads (ADR-0012, ticket #221); None when it reads none
    data: GameData | None = None  # the game data the text is worded from: a base id in brackets is said in words (#553, #604)
    steps: tuple[ReportStep, ...] = ()  # the blocks of the text tree, one for each step of the route page (ticket #488)
    step_of: Mapping[CompressedState, int] = field(default_factory=dict)  # the page's row of each item state the policy reaches


def with_interval(report: Report, interval: IntervalAnswer | None) -> Report:
    """The report of an answer that read a rule axis: the interval block is added and the approximate inputs are those of every route it shows.

    With `None` (the plan reads no axis) the report is returned as it is, so such an answer says nothing about any axis.
    """
    if interval is None:
        return report
    return replace(report, interval=interval, approximate_inputs=interval.approximate_inputs)


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


def requirements_parts(plan: Plan) -> tuple[list[str], list[dict]]:
    """The requirements of the target kept as the target holds them: (the plain ones, each group once).

    A group is `{"at_least": k, "of": [member, ...]}` and a member is `{"requirement": label, "side": "prefix" | "suffix"}` or, for a group in a
    group, a group. The side is said in words as the page's cards say it (OR-15). `plan.leaf_labels` lists the members of a group as plain
    leaves, so reading it as the requirements says that every member is required (#551, #630).
    """
    labels = iter(plan.leaf_labels)
    sides = iter(leaf_sides(plan.abstraction.data, plan.target))
    plain: list[str] = []
    groups: list[dict] = []

    def member(node) -> dict:
        if isinstance(node, KOfN):
            return {"at_least": node.at_least, "of": [member(each) for each in node.of]}
        return {"requirement": next(labels), "side": next(sides).value}

    for requirement in plan.target.requirements:
        if isinstance(requirement, KOfN):
            groups.append(member(requirement))
        else:
            plain.append(next(labels))
            next(sides)
    return plain, groups


def requirements_text(plan: Plan) -> str:
    """The requirements of the target as one line: the plain ones, then each k-of-n group once as "at least k of n of: a (prefix); b (suffix)".

    The words are the ones of the page's group heading (`_route_card.Group`), and a member says its side in words as it does there (OR-15).
    """

    def group_text(group: dict) -> str:
        members = "; ".join(f"({group_text(each)})" if "of" in each else f"{each['requirement']} ({each['side']})" for each in group["of"])
        return f"at least {group['at_least']} of {len(group['of'])} of: {members}"

    plain, groups = requirements_parts(plan)
    return "; ".join([*plain, *(group_text(group) for group in groups)])


def requirements_document(plan: Plan) -> dict:
    """The JSON `requirements`: `{"plain": [label, ...], "groups": [{"at_least": k, "of": [member, ...]}, ...]}` (schema `crafting-system-policy/3`)."""
    plain, groups = requirements_parts(plan)
    return {"plain": plain, "groups": groups}


def describe_state(plan: Plan, data: GameData, state: CompressedState) -> str:
    """One line on a state: its parts (`state_parts`) joined by "; "."""
    return "; ".join(state_parts(plan, data, state))


def state_parts(plan: Plan, data: GameData, state: CompressedState) -> list[str]:
    """The parts of the line on a state: rarity, the fractured mods, what each requirement leaf stands at, and the crafted and other mods.

    The mods besides the fractured ones show only when the model tracks them (a bench action is offered):
    the crafted mods by their text, and the rest as a count per side ("other mods: 1 prefix, 2 suffixes"). "Other" is meant: a mod that a
    "has ..." or "too weak: ..." part of the same line already names is not counted again (ticket #613).
    """
    parts = [state.flags.rarity.value]
    for entry in state.fractured:
        if entry.mod_id not in data.mods:  # held as its family type ("~n@attack"): the state does not say which mod it is
            parts.append("fractured mod of a family no requirement cares about")
            continue
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
    junk = _unnamed_mods(state)
    if junk:
        shown = [f"{n} {side.value}{'' if n == 1 else 'es'}" for side in Side if (n := sum(s.side is side for s in junk))]
        parts.append("other mods: " + ", ".join(shown))
    if state.offer:  # in the order of Pick 1, 2, 3 (ADR-0026): without it "Pick 2" names nothing
        offered = [_without_ranges(data.mods[entry.mod_id].text or data.mods[entry.mod_id].name) for entry in state.offer]
        parts.append("unveil offer: " + " | ".join(f"{number}. {text}" for number, text in enumerate(offered, 1)))
    return parts


def _unnamed_mods(state: CompressedState) -> list:
    """The held mods (not crafted, not fractured) that no requirement part of the state's line names.

    A leaf that stands at PASSING or BELOW names one mod: a fractured mod that gives it that standing, else a held mod that does (the
    first one found; a mod that gives two leaves their standing names both). A leaf that stands ABSENT names none. A crafted mod is named by its own
    part of the line ("crafted ..."), so a leaf it gives its standing to names no other mod.
    """
    left = [slot for slot in state.slots if not slot.crafted]
    named = [slot for slot in state.slots if slot.crafted]
    for leaf, status in enumerate(state.status):
        if status is Status.ABSENT or any(entry.contribution[leaf] is status for entry in state.fractured):
            continue
        if any(slot.contribution[leaf] is status for slot in named):  # a mod already named by another part of the line gives this leaf its standing
            continue
        for slot in left:
            if slot.contribution[leaf] is status:
                left.remove(slot)
                named.append(slot)
                break
    return left


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
    for state in policy_states(plan.start, plan.view_policy, plan.is_goal):
        if not plan.is_goal(state):
            ids[state] = f"S{len(ids) + 1}"
    return ids


def build_report(plan: Plan, data: GameData) -> Report:
    """Number the reachable states and collect what each one does."""
    order = policy_states(plan.start, plan.view_policy, plan.is_goal)
    ids = number_states(plan)
    reach = reach_probabilities(plan.start, plan.view_policy, plan.is_goal)

    states = []
    for state in order:
        action = plan.view_policy.get(state)
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
    from ._report_steps import report_steps  # it reads the route page's model, which imports this module

    steps, step_of = report_steps(plan, data)
    return Report(
        plan, ids, tuple(states), tuple((share, _leaf_chance(plan, share)) for share in shares),
        approximate_inputs(plan, plan.view_policy, data),
        None if plan.starts is None else first_step(plan.starts.chosen, data, plan.target),
        data=data, steps=steps, step_of=step_of,
    )  # fmt: skip


def _leaf_chance(plan: Plan, share: WeightShare) -> float | None:
    """The chance that one use of the share's action on the start state leaves the share's leaf met."""
    offer = next(p for p in plan.offers if p.label == share.action)
    leaf = plan.leaf_labels.index(share.leaf)
    try:
        kernel = plan.abstraction.kernel(plan.start, offer.offer.action)
    except ValueError:  # a refusal of either family or a kernel that cannot be asked: the chance of one use is left out of the line
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


UNRESOLVED = "not computed (the cost of the whole craft is far above its cheapest step)"


NOT_COMPUTED = {
    "subcritical": "not computed: the plan starts more runs of its inputs than it finishes, so its cost has no finite mean",
    "unordered": "not computed: the inputs of the plan depend on each other in a cycle",
    "improper": "not computed: the plan can reach a state from which it cannot finish, and its inputs depend on each other in a cycle",
}


def _row(name: str, value: str) -> str:
    """One row of the result block: the figure in the words of `PERCENTILE_WORDS`, then its value."""
    return f"  {PERCENTILE_WORDS[name]:<{ROW_WIDTH}}{value}"


def _quantile_text(risk, estimate: Estimate, shift: float, divine: float) -> str:
    if risk.grid.cause and math.isinf(estimate.value):  # its own cause (M7), not the grid's; a quantile the grid did compute is shown
        return NOT_COMPUTED[risk.grid.cause]
    return UNRESOLVED if unresolved(risk, estimate) else interval(_shifted(estimate, shift), divine)


def _shifted(estimate: Estimate, shift: float) -> Estimate:
    return Estimate(estimate.value + shift, estimate.low + shift, estimate.high + shift)


def free_action_lines(plan: Plan, risk) -> list[str]:
    """What the cost figures hold to when the plan has free actions (ticket #349): they are counted apart from the grid, and the bound is stated.

    The free actions are priced at an epsilon so that every step has a positive cost; the risk run counts them at that price but not on its
    grid, so the median cost and the cost 9 runs in 10 stay under are certified to within `free_allowance` Chaos, except with chance `free_tail`,
    and the average of the worst tenth to within `free_cvar_allowance`. The plan's own certified error (a relative figure) is given with it.
    Empty for a plan without free actions. The words are those of `PERCENTILE_WORDS` (#633).
    """
    if risk.grid.free_tail <= 0.0:
        return []
    return [
        f"  (free actions are counted at {money_small(free_action_price(plan))} Chaos each and added up apart from the other costs when the risk figures are worked out:",
        f"   {figures('p50', 'p90')} hold to within {money_small(risk.grid.free_allowance)} Chaos, except with chance {risk.grid.free_tail:.0e},",
        f"   and {PERCENTILE_WORDS['CVaR']} to within {money_small(risk.grid.free_cvar_allowance)} Chaos;",
        f"   the error bound of the plan's cost is {plan.solution.error_bound:.1e}, relative)",
    ]


def free_action_price(plan: Plan) -> float:
    """The price the planner gave the actions that consume nothing."""
    return max((entry.cost for entry in plan.offers if not entry.offer.resources), default=0.0)


def money_small(chaos: float) -> str:
    return f"{chaos:.2g}"


def limit_lines(plan: Plan) -> list[str]:
    """What the answer leaves out, one line to a limit in the order of the groups of `_limits`, each with what the answer still guarantees (OR-13)."""
    if not plan.limits:
        return []
    return [f"{HEADING}:", *(f"  {limit_text(limit)}" for limit in ordered(plan.limits))]


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
    if report.interval is not None:
        lines.extend(report.interval.text_lines(divine))
    lines.extend(approximate_lines(report.approximate_inputs))
    lines.append(f"Requirements: {requirements_text(plan)}")
    lines.append(
        f"Prices: league {plan.prices.league}, fetched {plan.prices.fetched_at:%Y-%m-%d}, "
        f"1 Divine = {divine:,.2f} Chaos"
    )
    name = f" ({plan.start_price.name})" if plan.start_price.name else ""
    if report.first_step is not None:
        # a start made at a vendor: the start item is what the recipe takes (the Normal base), and the recipe is a step of its own (below);
        # the item it gives back is never printed as the start item (#545, I7)
        base = report.first_step.hand[0]
        lines.append(f"Start item ({base.what}): {money(base.chaos)} Chaos [{base.price_source}]; the recipe below uses it up")
    elif plan.start_price.given:  # OR-6: nothing is paid for it, so no number is printed
        lines.append(f"Start item: {plan.start_price.source}")
    else:
        lines.append(f"Start item{name}: {money(shift)} Chaos [{plan.start_price.source}]")
    if plan.start_price.taken_for:
        lines.append(f"  {plan.start_price.taken_for}")
    if report.first_step is not None:
        lines.extend(first_step_lines(report.first_step))
    if plan.starts is not None:
        lines.extend(start_lines(plan.starts))
    lines.extend(limit_lines(plan))
    lines.append(f"Blocks solved: {plan.approximation.blocks:,}" if plan.approximation else f"States solved: {len(plan.solution.values)}")
    lines.append("")
    lines.append(POLICY_HEADING)
    for step in report.steps:
        lines.extend(_step_lines(step))
    if not report.steps:
        lines.append("  The start item already meets the target.")
    lines.append("")
    lines.append("Result")
    if risk is None:
        mean = Estimate(plan.mean_remaining + shift, plan.approximation.lower + shift, plan.approximation.upper + shift)
        lines.append(_row("mean", f"{interval(mean, divine)} (the policy's certified cost; see Answer)"))
        lines.extend(risk_lines())
        lines.append(f"  (the start item, {money(shift)} Chaos, is included)")
    else:
        lines.append(_row("success", percent(risk.success_probability.value)))
        lines.append(_row("mean", interval(_shifted(risk.mean, shift), divine)))
        lines.append(_row("p50", _quantile_text(risk, risk.p50, shift, divine)))
        lines.append(_row("p90", _quantile_text(risk, risk.p90, shift, divine)))
        lines.extend(free_action_lines(plan, risk))
        got = "making it at the vendor" if report.first_step is not None else "buying it"
        lines.append(f"  (the start item, {money(shift)} Chaos, is included; the cost left to pay after {got} is")
        lines.append(f"   {money(plan.mean_remaining)} Chaos as the plan counts it and {money(risk.mean.value)} as the risk figures count it)")
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
        lines.append(f"Run time: working out the plan took {plan.solve_seconds * 1000:.0f} ms")
    else:
        lines.append(f"Run time: working out the plan took {plan.solve_seconds * 1000:.0f} ms, the risk figures {plan.risk_seconds * 1000:.1f} ms")
    if verification is not None:
        lines.append("")
        lines.extend(verification_lines(verification) if plan.approximation else _verification_lines(verification, plan))
    text = "\n".join(lines) + "\n"
    return text if report.data is None else plain_base_names(report.data, text)  # a base by its game name, never its id (#553, #604)


def _step_lines(step: ReportStep) -> list[str]:
    """The block of one step: its title, the item, what it costs, how often it is used, and each branch with the exact mixture of its chance."""
    lines = [f"Step {step.number}: {step.title}"]
    if not step.acts:
        lines.append(f"  no action here: {step.reason}" if step.reason else "  no action here")
    if step.items == 1:
        lines.append(f"  the item: {step.item}")
    elif step.items > 1:
        shared = f"; what they all share: {step.item}" if step.item else ""
        lines.append(f"  {step.items:,} items take this action{shared}")
        lines.append("  (the chances below are the mixture of theirs)")
    if step.acts:
        parts = " + ".join(f"{count} {resource}" for resource, count, _, _ in step.cost_parts)
        if not step.cost_parts:  # an action that consumes nothing: the solver is given a negligible cost (ADR-0026)
            lines.append(f"  cost per use: free (counted at {step.cost:.1g} Chaos so that every step has a positive cost)")
        else:
            lines.append(f"  cost per use: {parts} = {money(step.cost)} Chaos")
        if step.never:
            lines.append("  never finishes from here")
        elif step.uses is not None:
            lines.append(f"  used {step.uses:,.2f} times on average, {money(step.step_cost)} Chaos in all")
    if step.reached is not None:
        lines.append(f"  a run enters this step with chance {percent(step.reached)}")
    for outcome in step.outcomes:
        lines.append(f"    {percent(outcome.chance):>8}  {outcome.text}")
    return lines


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
        f"  {PERCENTILE_WORDS['p90']}: simulated {money(p90.value)} Chaos, interval {money(p90.low)} to {money(p90.high)} "
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
        **_free_totals(plan, risk),
    }


def _free_totals(plan: Plan, risk) -> dict:
    """Only for a plan with free actions (ticket #349): their price, and how far the percentiles and the CVaR hold because of it."""
    if risk.grid.free_tail <= 0.0:
        return {}
    return {
        "free_action_cost": _number(free_action_price(plan)),
        "free_action_allowance": _number(risk.grid.free_allowance),
        "free_action_tail": _number(risk.grid.free_tail),
        "free_action_cvar_allowance": _number(risk.grid.free_cvar_allowance),
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
        **({"interval": report.interval.document()} if report.interval is not None else {}),
        "target": target_name,
        "requirements": requirements_document(plan),
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
            "given": plan.start_price.given,
        },
        **({"start_options": start_document(plan.starts, report.first_step)} if plan.starts is not None else {}),
        "limits": [limit_document(limit) for limit in ordered(plan.limits)],
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
