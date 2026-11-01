"""How a plan says what it started from: the start options compared and the ones refused, in text and in JSON (ADR-0059, ticket #330).

Nothing is printed for a plan with no `starts` (the setting `recipe_starts` is off, or no recipe takes the target's base kind),
so those reports read as they did before the ticket. The first line of the block names the rule, the lines after it the
options in the order they were tried (the plain start item first), the refused recipes with their reasons and, when a rule axis
changes the cheapest total, the cheapest total at each of its readings with their range.
"""

import math

from ._start_step import FirstStep
from ._start_types import NO_TARGET_MOD, SOURCE_PLAIN, ConsideredStart, Reading, RefusedStart, StartChoice

OFF_HOW = "`--no-recipe-starts`, or recipe_starts = false under [planner] in crafting.toml, turns recipe starts off"


def money(chaos: float) -> str:
    return "never" if math.isinf(chaos) else f"{chaos:,.2f}"


def _number(value: float) -> float | None:
    return None if math.isinf(value) or math.isnan(value) else value


def reading_text(reading: Reading) -> str:
    """A reading in words: `elemental_cap = wiki` (several axes joined with a comma, none as "no rule axis")."""
    return ", ".join(f"{axis} = {value}" for axis, value in reading) or "no rule axis"


def _scope(axis: str | None, values: tuple[str, ...]) -> str:
    return "" if axis is None else f" (only at {axis} = {', '.join(values)})"


def _row(row: ConsideredStart) -> str:
    candidate = row.candidate
    name = f" ({candidate.price_name})" if candidate.source == SOURCE_PLAIN and candidate.price_name else ""
    scope = _scope(candidate.axis, candidate.reading_values)
    head = f"{candidate.label}{name}{scope}"
    if row.outcome in ("chosen", "planned"):
        assert row.total is not None and row.mean_remaining is not None
        approximate = ", approximate" if row.approximate else ""
        words = f"{money(row.total)} Chaos = start {money(candidate.price)} + crafting {money(row.mean_remaining)}{approximate}"
        return f"  {'chosen' if row.outcome == 'chosen' else 'planned'}: {head}: {words}"
    if row.outcome == "failed":
        return f"  failed: {head}: {row.note}"
    return f"  not planned: {head}: {row.note}" if row.note else f"  not planned: {head}"


def _refusal(refusal: RefusedStart) -> str:
    steps = f", {refusal.steps} steps" if refusal.steps else ""
    return f"  refused: {refusal.name} ({refusal.recipe}{steps}){_scope(refusal.axis, refusal.reading_values)}: {refusal.reason}: {refusal.detail}"


def _gives(text: str, note: str) -> str:
    return f"{text}, {note}" if note else text


def first_step_lines(step: FirstStep) -> list[str]:
    """The text block on the first step of a plan that starts from a vendor recipe (ASCII only): the bill, the recipes, the item back, the price."""
    lines = [f"First step, before S1: {step.title}", "  You hand the vendor:"]
    for good in step.hand:
        lines.append(f"    {good.label}: {money(good.chaos)} Chaos [{good.price_source}]")
    if len(step.rounds) > 1:
        lines.append("  Recipe by recipe (each takes the Magic item the recipe before made; the first takes the Normal base):")
    else:
        lines.append("  The recipe:")
    for each in step.rounds:
        label = f"recipe {each.number}: " if len(step.rounds) > 1 else ""
        lines.append(f"    {label}{each.hand} -> {_gives(each.gives, f'T{each.tier}')}")
    mods = " and ".join(_gives(text, note) for text, note in step.mods) or "no mod"
    item = f"{step.properties[0]} {step.base}" + "".join(f", {each}" for each in step.properties[1:])
    lines.append(f"  You get back: {item}, with only {mods} (the recipe wipes every other mod)")
    if step.roll_note:
        lines.append(f"  Roll: {step.roll_note}")
    lines.append(f"  Start price: {money(step.price)} Chaos = the goods above; a restart makes the item again at this price")
    return lines


def start_lines(choice: StartChoice) -> list[str]:
    """The text block on the start options (ASCII only); the chosen start's goods follow its row."""
    lines = [
        "Start options (the cheapest total of start price and expected cost to craft wins; the plain start item is always one; "
        f"{OFF_HOW}):"
    ]
    for row in choice.considered:
        lines.append(_row(row))
        if row.candidate.sourced is not None:
            lines.extend(f"      {text}" for text in row.candidate.sourced.lines())
    for refusal in choice.refused:
        if refusal.reason != NO_TARGET_MOD:
            lines.append(_refusal(refusal))
    unasked = sorted({refusal.recipe for refusal in choice.refused if refusal.reason == NO_TARGET_MOD})
    if unasked:  # one line: a target asks for few of the recipes' mods, and a line for each would bury the others
        lines.append(f"  refused ({NO_TARGET_MOD}): no requirement of the target asks for what these recipes make: {', '.join(unasked)}")
    if choice.reading_matters:
        low, high = choice.total_range
        lines.append("  Rule axis changes the cheapest total (ADR-0059); the plan is the first reading:")
        for entry in choice.by_reading:
            label = next((row.candidate.label for row in choice.considered if row.candidate.key == entry.key), "no start reaches the goal")
            lines.append(f"    {reading_text(entry.reading)}: {money(entry.total)} Chaos ({label})")
        lines.append(f"  Cheapest total over the readings: {money(low)} to {money(high)} Chaos")
    return lines


def _option(row: ConsideredStart) -> dict:
    candidate = row.candidate
    return {
        "key": candidate.key,
        "source": candidate.source,
        "label": candidate.label,
        "outcome": row.outcome,
        "recipe": candidate.recipe,
        "steps": candidate.steps,
        "start_price_chaos": _number(candidate.price),
        "goods": [
            {"name": name, "count": count, "chaos": chaos, "price_source": source} for name, count, chaos, source in candidate.goods
        ],
        "mean_cost_without_start": None if row.mean_remaining is None else _number(row.mean_remaining),
        "total_chaos": None if row.total is None else _number(row.total),
        "approximate": row.approximate,
        "rule_axis": candidate.axis,
        "rule_axis_values": list(candidate.reading_values),
        "note": row.note,
        **({"price": candidate.sourced.document()} if candidate.sourced is not None else {}),
    }


def start_document(choice: StartChoice, step: FirstStep | None = None) -> dict:
    """The JSON `start_options` block: every option with its goods and totals, the refused, the cheapest total per reading and,
    for a start made at a vendor, the first step (`first_step`, null otherwise)."""
    low, high = choice.total_range
    return {
        "first_step": None if step is None else first_step_document(step),
        "chosen": choice.chosen.key,
        "options": [_option(row) for row in choice.considered],
        "refused": [
            {
                "recipe": refusal.recipe,
                "name": refusal.name,
                "reason": refusal.reason,
                "detail": refusal.detail,
                "steps": refusal.steps,
                "rule_axis": refusal.axis,
                "rule_axis_values": list(refusal.reading_values),
            }
            for refusal in choice.refused
        ],
        "rule_axes": [{"axis": name, "readings": list(values)} for name, values in choice.axes],
        "by_reading": [
            {"reading": dict(entry.reading), "chosen": entry.key, "total_chaos": _number(entry.total)} for entry in choice.by_reading
        ],
        "total_range_chaos": {"low": _number(low), "high": _number(high)},
        "reading_matters": choice.reading_matters,
        "approximate_claims": list(choice.claims),
    }


def first_step_document(step: FirstStep) -> dict:
    """The JSON `first_step` block: the bill with roles, the recipes with tiers, the item that comes back, the price."""
    return {
        "recipe": step.recipe,
        "title": step.title,
        "hand": [
            {
                "role": good.role,
                "count": good.count,
                "name": good.name,
                "what": good.what,
                "chaos": good.chaos,
                "price_source": good.price_source,
            }
            for good in step.hand
        ],
        "recipes": [{"number": each.number, "hand": each.hand, "gives": each.gives, "tier": each.tier} for each in step.rounds],
        "gets": {
            "base": step.base,
            "properties": list(step.properties),
            "mods": [{"text": text, "tier": note} for text, note in step.mods],
        },
        "roll_note": step.roll_note,
        "price_chaos": step.price,
    }
