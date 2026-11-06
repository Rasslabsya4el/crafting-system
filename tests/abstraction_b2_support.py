"""The layer 1 oracle for the beast and Harvest crafts in the compressed state (ticket #149, ADR-0019, ADR-0030).

Layer 1 (ADR-0019) says: the kernel of the state of a concrete item equals the finished items of the action on that item, each compressed
on its own and the chances added up exactly. The finished items are listed from the action itself (`finished_at_tiers`, `contract_support.finished`
with the tier of a drawn mod taken from the pool of the item it is drawn onto, as the action's sampler gives it, ticket #155); nothing
here reads a kernel. `closure` lists the concrete items that a set of actions reaches from some starts, so the check runs over every
state the crafts can lead to, not only over hand-picked ones; `check_layer_1` compares one action on one item and says whether it applied.
"""

import itertools
from collections import defaultdict, deque
from collections.abc import Iterable
from fractions import Fraction

import pytest
from contract_support import finished

from crafting_system.abstraction import Abstraction
from crafting_system.actions import ActionError, Fixed, Rerolled, tiers_of
from crafting_system.items import ExplicitMod, ImplicitMod, Item, is_corrupted_implicit


class _Part:
    """One part of some outcomes, alone: what `finished` reads of an outcomes object."""

    def __init__(self, part):
        self.components = ((Fraction(1), part),)


def finished_at_tiers(outcomes, data) -> list[tuple[Fraction, Item]]:
    """`contract_support.finished`, except that a mod a pool draw adds has the tier of the pool of the item it is drawn onto (`tiers_of`).

    `finished` gives every drawn mod the tier it has on an amulet, which is wrong for another base and for an influenced item (the tier of an
    influence mod counts among the mods of its type that can spawn with the influence tag); the sampler of the action uses `tiers_of`.
    """
    items: list[tuple[Fraction, Item]] = []
    for share, part in outcomes.components:
        if isinstance(part, Fixed | Rerolled):
            items.extend((share * chance, result) for chance, result in finished(_Part(part), data))
            continue
        tiers = tiers_of(data, part.retained)
        for outcome, chance in part.distribution(lambda mod: mod.id).items():
            added = tuple(
                ExplicitMod(mod_id, tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats))
                for mod_id, count in sorted(outcome)
                for _ in range(count)
            )
            items.append((share * chance, part.retained.changed(data, mods=(*part.retained.mods, *added))))
    return items


def rolled(outcomes, data, given: Item) -> list[tuple[Fraction, Item]]:
    """`finished_at_tiers`, with every implicit that the action rolls afresh listed at every value it can roll (ticket #158).

    An implicit of a result is rolled afresh when `given` did not hold its mod, or when the outcomes name it in `rerolled` (a Blessed Orb's, an
    Ember's); each stat takes every integer of its range with the same chance, the stats independently. Nothing here reads a kernel or a
    roll law of `abstraction`: the values are enumerated one by one.
    """
    held = {entry.mod_id for entry in given.implicits}
    rerolled = frozenset().union(*(frozenset(getattr(part, "rerolled", ())) for _, part in outcomes.components))
    items: list[tuple[Fraction, Item]] = []
    for chance, result in finished_at_tiers(outcomes, data):
        fresh = [
            entry
            for entry in result.implicits
            if not is_corrupted_implicit(data.mods[entry.mod_id]) and (entry.mod_id not in held or entry.mod_id in rerolled)
        ]
        ranges = [
            [range(min(stat.min, stat.max), max(stat.min, stat.max) + 1) for stat in data.mods[entry.mod_id].stats] for entry in fresh
        ]
        combinations = list(itertools.product(*(list(itertools.product(*each)) for each in ranges)))
        for combination in combinations:
            changed = {entry.mod_id: ImplicitMod(entry.mod_id, entry.grade, tuple(values)) for entry, values in zip(fresh, combination)}
            implicits = tuple(changed.get(entry.mod_id, entry) for entry in result.implicits)
            items.append((chance / len(combinations), result.changed(data, implicits=implicits)))
    return items


def concrete_pushforward(ability: Abstraction, data, item: Item, action, *, rolls: bool = False) -> dict:
    """The exact kernel of `action` on `item` as its finished items give it: each compressed by `ability`, the chances added up.

    With `rolls` the implicits the action rolls afresh are listed at every value (`rolled`). Raises what `action.outcomes` raises when the game refuses the item.
    """
    expected: dict = defaultdict(Fraction)
    outcomes = action.outcomes_under(data, item, ability.reading)  # at the reading the abstraction's kernels are taken at (ticket #214)
    for chance, result in rolled(outcomes, data, item) if rolls else finished_at_tiers(outcomes, data):
        expected[ability.compress(result)] += chance
    return dict(expected)


def closure(data, starts: Iterable[Item], actions, *, limit: int = 4000, rolls: bool = False, reading=None) -> list[Item]:
    """Every concrete item that `actions` reach from `starts` (the starts included), in the order found; at most `limit`.

    An action that refuses an item (`ActionError`) is skipped there. With `rolls` the implicits an action rolls afresh are followed at every value, and with a `reading` the actions with rule axes are taken at it.
    """
    seen: dict[Item, None] = dict.fromkeys(starts)
    queue = list(seen)
    while queue and len(seen) < limit:
        item = queue.pop(0)
        for action in actions:
            try:
                outcomes = action.outcomes_under(data, item, reading)
                results = rolled(outcomes, data, item) if rolls else finished_at_tiers(outcomes, data)
            except ActionError:
                continue
            for _, result in results:
                if result not in seen:
                    seen[result] = None
                    queue.append(result)
    return list(seen)


def check_layer_1(ability: Abstraction, data, item: Item, action, *, rolls: bool = False) -> bool:
    """The kernel of `item`'s state equals the compressed finished items of `action` on `item`; where the game refuses, so does the kernel.

    The kernel refuses with the same kind of error the action does. Returns whether the action applied (False: it refused, and the kernel refused too).
    With `rolls` the oracle lists every value of the implicits the action rolls afresh (`rolled`, ticket #158).
    """
    state = ability.compress(item)
    try:
        expected = concrete_pushforward(ability, data, item, action, rolls=rolls)
    except ActionError as refusal:
        with pytest.raises(type(refusal)):
            ability.kernel(state, action)
        return False
    kernel = ability.kernel(state, action)
    assert dict(kernel) == expected, f"{action.label(data)} on {[(e.mod_id, e.fractured, e.crafted) for e in item.mods]}"
    assert sum(kernel.values()) == 1 and all(type(chance) is Fraction and chance > 0 for chance in kernel.values())
    return True


def real_graph(ability: Abstraction, starts: Iterable, actions) -> tuple[set, int]:
    """The states the solver graph holds from `starts` (a goal is not expanded) and the number of its transitions, from the real kernels."""
    starts = list(starts)
    seen, queue, transitions = set(starts), deque(starts), 0
    while queue:
        state = queue.popleft()
        if ability.is_goal(state):
            continue
        for action in actions:
            try:
                kernel = ability.kernel(state, action)
            except ActionError:
                continue
            transitions += len(kernel)
            for successor in kernel:
                if successor not in seen:
                    seen.add(successor)
                    queue.append(successor)
    return seen, transitions


def disagrees(ability: Abstraction, data, item: Item, action) -> bool:
    """Whether the kernel of `item`'s state differs from the compressed finished items of `action`, or refuses where the game applies (or the reverse)."""
    state = ability.compress(item)
    try:
        expected = concrete_pushforward(ability, data, item, action)
    except ActionError as refusal:
        try:
            ability.kernel(state, action)
        except ActionError as raised:
            return type(raised) is not type(refusal)
        return True
    try:
        return dict(ability.kernel(state, action)) != expected
    except ActionError:
        return True
