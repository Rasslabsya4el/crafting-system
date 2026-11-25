"""What a crafted mod that the target does not ask is for, said on its step (#1629, #1632).

A plan crafts mods the target never asks: R11 crafts `+(50-75) to Armour` on an Evasion helmet before each Exalted Orb, R14 crafts `Cannot
roll Attack Modifiers` right after the Regal Orb and pays it 8.44 times. A player reads either as a mistake. What the craft does is in the
plan's own data, and the page now says it in four parts, each a general rule over that data:

* `blocks`: what the mod keeps off the item while it is on. A crafted mod blocks its family (`Mod.families`): the natural mods of that family
  the base can roll are named. A metamod that keeps a tag out of a draw (`BLOCKED_TAG`: Cannot roll Attack or Caster Modifiers) keeps those
  mods out of what is added and, by the same rule, out of what an Orb of Annulment removes (claim `metamods.annulment_respects_locks_and_tags`);
  a lock (`LOCKED_SIDE`) keeps its side.
* `effects`: for each later step whose items hold the mod, the chance one use there makes or loses a wanted mod, on those items with the mod
  and on the same items without it (the abstraction's kernel on the state with the crafted slot taken out), each item by its expected visits.
  The wanted mod said is the one whose chance moves most; a step where no chance moves by half a point is not said.
* `again`: a craft an item comes to more than once in a run is made again after each step that took it off: how many times after each step
  (the visits of the steps that lead into it), and for a step whose items hold it, the share of its uses that takes it off.
* `instead`: the plan's own price of not making it here: on the item the step sees most, each other action the plan prices there (its
  outcomes all have a value in the plan's solution), its cost then the plan's, against the craft's. An action whose outcomes the plan never
  priced is said as not priced: the plan's data holds no figure for it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import replace

from crafting_system.abstraction import CompressedState, Status
from crafting_system.actions import BLOCKED_TAG, LOCKED_SIDE, NotApplicableError, OutOfScopeError, crafted_limit_of
from crafting_system.items import spawn_weight
from crafting_system.items.model import Metamod

from ._route import RESTART
from ._route_card import _hashes, mod_text

MOVED = 0.005  # a chance that moves by less than half a point is not said
SAID_STATES = 0.99  # the states of a step read, by weight, at most `MOST_STATES` of them
MOST_STATES = 300
NAMED = 3  # the natural mods a blocked family names, the rest counted


def added_crafts(view, step, unasked: bool = True) -> list[str]:
    """The crafted mods a step adds (their canonical mod ids), in the order they appear; with `unasked`, only those that meet no leaf of
    the target."""
    before = {slot.kind for state in step.states for slot in state.slots if slot.crafted}
    found = []
    for edge in step.edges:
        if edge.kind not in ("forward", "goal"):
            continue
        for state in edge.states:
            for slot in state.slots:
                if slot.crafted and slot.kind not in before and slot.kind in view.data.mods:
                    if not unasked or all(status is not Status.PASSING for status in slot.contribution):
                        found.append(slot.kind)
    return list(dict.fromkeys(found))


def holds(state: CompressedState, kind: str) -> bool:
    return any(slot.crafted and slot.kind == kind for slot in state.slots)


def without(state: CompressedState, kind: str) -> CompressedState:
    """The state with one crafted slot of `kind` taken out: the same item had the craft not been made."""
    slots = list(state.slots)
    for i, slot in enumerate(slots):
        if slot.crafted and slot.kind == kind:
            del slots[i]
            break
    return replace(state, slots=tuple(slots))


def can_hold(view, state: CompressedState) -> bool:
    """Whether an item can hold the crafted mods of `state` (`crafted_limit_of`): the state without the multimod is no item when it holds
    two crafted mods besides, so a craft is never compared with an item the game cannot have."""
    crafted = [slot.kind for slot in state.slots if slot.crafted]
    multimod = any(Metamod.MULTIPLE_CRAFTED_MODS.value in view.data.mods[kind].families for kind in crafted if kind in view.data.mods)
    return len(crafted) <= crafted_limit_of(view.data, multimod=multimod, enchantment=view.start_item.enchantment)


def blocks(data, base_id: str, item_level: int, kind: str) -> str | None:
    """What the crafted mod `kind` keeps off an item of `base_id` and `item_level` while it is on, in words."""
    mod = data.mods[kind]
    tags = [tag for metamod, tag in BLOCKED_TAG.items() if metamod.value in mod.families]
    if tags:
        named = " or ".join(tags)
        return f"while it is on, no {named} mod is added to the item and an Orb of Annulment removes none of its {named} mods"
    sides = [side for metamod, side in LOCKED_SIDE.items() if metamod.value in mod.families]
    if sides:
        return f"while it is on, the {sides[0].value}es cannot be changed"
    base = data.base_items[base_id]
    natural = [
        other
        for other in data.mods.values()
        if other.id != kind
        and other.domain == base.domain
        and other.generation_type in ("prefix", "suffix")
        and set(other.families) & set(mod.families)
        and other.required_level <= item_level
        and spawn_weight(other, base.tags) > 0
    ]
    names = list(dict.fromkeys(_hashes(mod_text(other)) for other in natural))
    if not names:
        return None
    said = " / ".join(names[:NAMED]) + (f" and {len(names) - NAMED} more" if len(names) > NAMED else "")
    return f"it takes the family of {said}: while it is on, no such mod can be added"


def _read(states: Sequence[CompressedState], weights: Sequence[float]) -> list[tuple[CompressedState, float]]:
    """The states of most weight, covering `SAID_STATES` of it, at most `MOST_STATES` of them, with their weights."""
    order = sorted(range(len(states)), key=lambda i: -weights[i])
    whole = math.fsum(weights) or 1.0
    taken, sum_ = [], 0.0
    for i in order[:MOST_STATES]:
        if sum_ >= SAID_STATES * whole:
            break
        taken.append((states[i], weights[i]))
        sum_ += weights[i]
    return taken


def chances(ab, state: CompressedState, action) -> tuple[list[float], list[float]] | None:
    """Per leaf, the chance one use of `action` on `state` makes it PASSING (a leaf it is not) and loses it (a leaf it is), from the
    abstraction `ab`'s kernel; None where the action has no outcome there."""
    try:
        kernel = ab.kernel(state, action)
    except (NotApplicableError, OutOfScopeError, ValueError):
        return None
    if not kernel:
        return None
    leaves = len(state.status)
    made, lost = [0.0] * leaves, [0.0] * leaves
    for outcome, chance in kernel.items():
        for i in range(leaves):
            if state.status[i] is not Status.PASSING and outcome.status[i] is Status.PASSING:
                made[i] += float(chance)
            if state.status[i] is Status.PASSING and outcome.status[i] is not Status.PASSING:
                lost[i] += float(chance)
    return made, lost


def effects(view, kind: str) -> tuple[list[str], set[str]]:
    """For each step whose items hold `kind`: the wanted mod whose chance to be made, then to be lost, moves most with the mod on; and the
    actions of those steps (what the craft is made before)."""
    lines, used = [], set()
    for step in view.flow.steps:
        action = step.action
        if action is None or action.label == RESTART or not step.states:
            continue
        weights = step.weights or (1.0,) * len(step.states)
        held = [(state, weight) for state, weight in zip(step.states, weights, strict=True) if holds(state, kind)]
        if not held:
            continue
        used.add(action.label)
        acting = view.plan.offer_of(action).offer.action
        leaves = len(view.plan.leaf_labels)
        sums = {"made": [[0.0, 0.0] for _ in range(leaves)], "lost": [[0.0, 0.0] for _ in range(leaves)]}
        whole = 0.0
        for state, weight in _read([s for s, _ in held], [w for _, w in held]):
            bare = without(state, kind)
            if not can_hold(view, bare):
                continue
            on, off = chances(view.ab, state, acting), chances(view.ab, bare, acting)
            if on is None or off is None:
                continue
            whole += weight
            for name, part in (("made", 0), ("lost", 1)):
                for i in range(leaves):
                    sums[name][i][0] += weight * on[part][i]
                    sums[name][i][1] += weight * off[part][i]
        if not whole:
            continue
        said = []
        for name, verb in (("made", "is made"), ("lost", "is lost")):
            moved = [(abs(a - b) / whole, i, a / whole, b / whole) for i, (a, b) in enumerate(sums[name])]
            gap, i, on, off = max(moved)
            if gap >= MOVED:
                said.append(f"{view.leaf_text(i)} {verb} on {_percent(on)} of uses with it, {_percent(off)} without")
        if said:
            lines.append(f"step {step.number + 1} ({view.title_of(step.number + 1)}): " + "; ".join(said))
    return lines, used


def _words():
    """The page's own ways of writing a chance, a count and a sum of Chaos (`_route_view`, which imports this module)."""
    from . import _route_view

    return _route_view.chance_text, _route_view.count, _route_view.money


def _percent(chance: float) -> str:
    return "0%" if chance == 0 else _words()[0](chance)


def again(view, step, kind: str) -> str | None:
    """How many times a run that reaches the step makes the craft, after which step each time, and the share of a step's uses that takes it
    off when its items hold it. None for a craft made once."""
    if step.uses is None or not step.reached or not math.isfinite(step.uses) or step.uses / step.reached < 1.05:
        return None  # `uses` counts every run, `reached` the share of runs that come here
    arrivals: dict[int, float] = {}
    for other in view.flow.steps:
        if other.uses is None or not math.isfinite(other.uses) or other.number == step.number:
            continue
        for edge in other.edges:
            if edge.to == step.number:
                arrivals[other.number] = arrivals.get(other.number, 0.0) + other.uses * edge.chance
    if not arrivals:
        return None
    parts = []
    for number, count in sorted(arrivals.items(), key=lambda kv: -kv[1]):
        if count / step.reached < 0.005:
            continue
        source = next(other for other in view.flow.steps if other.number == number)
        said = f"{_count(count / step.reached)} after step {number + 1} ({view.title_of(number + 1)})"
        share = _takes_off(view, source, kind)
        if share is not None and share >= MOVED:
            said += f", whose uses take it off {_percent(share)} of the time while it is on"
        parts.append(said)
    return f"made {_count(step.uses / step.reached)} times in a run that reaches this step: " + "; ".join(parts)


def _count(value: float) -> str:
    return _words()[1](value)


def _takes_off(view, step, kind: str) -> float | None:
    """The share of a step's uses on items holding `kind` that take it off; None when its items never hold it."""
    action = step.action
    if action is None or action.label == RESTART:
        return None
    weights = step.weights or (1.0,) * len(step.states)
    held = [(state, weight) for state, weight in zip(step.states, weights, strict=True) if holds(state, kind)]
    if not held:
        return None
    acting = view.plan.offer_of(action).offer.action
    total = off = 0.0
    for state, weight in _read([s for s, _ in held], [w for _, w in held]):
        try:
            kernel = view.ab.kernel(state, acting)
        except (NotApplicableError, OutOfScopeError, ValueError):
            continue
        total += weight
        off += weight * math.fsum(float(chance) for outcome, chance in kernel.items() if not holds(outcome, kind))
    return off / total if total else None


def instead(view, step, against: set[str]) -> list[str]:
    """On the item the step sees most: the cheapest other action the plan prices there, its cost then the plan's against the craft's; and
    the actions the craft is made before (`against`) that the plan never priced there, named as such."""
    values = getattr(getattr(view.plan, "solution", None), "values", None)
    if not values or not step.states:
        return []
    weights = step.weights or (1.0,) * len(step.states)
    state = max(zip(step.states, weights, strict=True), key=lambda pair: pair[1])[0]
    mine = values.get(state)
    if mine is None or not math.isfinite(mine):
        return []
    priced, unpriced = [], []
    for offer in view.plan.offers:
        if offer.label == step.action.label or offer.label == RESTART:
            continue
        try:
            kernel = view.ab.kernel(state, offer.offer.action)
        except (NotApplicableError, OutOfScopeError, ValueError):
            continue
        stay = float(kernel.get(state, 0))
        if not kernel or stay >= 1:
            continue
        if any(outcome != state and outcome not in values and not view.ab.is_goal(outcome) for outcome in kernel):
            if offer.label in against:
                unpriced.append(offer.label)
            continue
        rest = math.fsum(float(chance) * (0.0 if view.ab.is_goal(outcome) else values[outcome]) for outcome, chance in kernel.items() if outcome != state)
        cost = (offer.cost + rest) / (1 - stay)
        if math.isfinite(cost):
            priced.append((cost, offer.label))
    lines = []
    if priced:
        cost, label = min(priced)
        lines.append(
            f"not made here: on the item this step sees most, the cheapest other action the plan prices there, {label} then the plan, leaves "
            f"{_words()[2](cost)} to pay against {_words()[2](mine)} with the craft"
        )
    if unpriced:
        lines.append(f"{' or '.join(dict.fromkeys(unpriced))} there first, before the craft: not priced, the plan's search never followed it from that item")
    return lines


def purpose_lines(view, step) -> list[str]:
    """The lines of a step that crafts a mod the target does not ask, or takes such a mod off (empty for any other step)."""
    action = step.action
    if action is None or action.label == RESTART:
        return []
    lines, against = [], set()
    for kind in added_crafts(view, step):
        if said := blocks(view.data, view.ab.base_id, view.ab.item_level, kind):
            lines.append(said)
        made, used = effects(view, kind)
        lines += made
        against |= used
    if lines:
        lines += instead(view, step, against)
    return lines + freed(view, step)


def freed(view, step) -> list[str]:
    """For a step whose every use takes off a crafted mod the target does not ask (a sure use: Remove Crafted Mods): which, the step that
    made it, and what may roll again. A reroll that also takes it off (an essence) is not said: what it is used for is the reroll."""
    if not view.sure(step.action):
        return []
    kept = {tuple(slot for slot in state.slots if not slot.crafted) for state in step.states}
    landing = [state for edge in step.edges if edge.kind in ("forward", "goal") for state in edge.states]
    if any(tuple(slot for slot in state.slots if not slot.crafted) not in kept for state in landing):
        return []  # it changes more than the crafted mods (a Scouring): what it is used for is that
    held = {slot.kind for state in step.states for slot in state.slots if slot.crafted and slot.kind in view.data.mods and all(x is not Status.PASSING for x in slot.contribution)}
    lines = []
    for kind in sorted(held):
        if not landing or any(holds(state, kind) for state in landing):
            continue
        makers = [other.number + 1 for other in view.flow.steps if other.action is not None and kind in added_crafts(view, other)]
        where = f" (crafted in step {makers[0]})" if makers else ""
        said = f"it takes off {_hashes(mod_text(view.data.mods[kind]))}{where}"
        if (blocked := blocks(view.data, view.ab.base_id, view.ab.item_level, kind)) and blocked.startswith("it takes the family of "):
            said += f": {blocked.removeprefix('it takes the family of ').split(':')[0]} can roll again"
        lines.append(said)
    return lines
