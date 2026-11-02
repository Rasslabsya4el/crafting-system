"""The layer 1 oracle for the beast and Harvest crafts in the compressed state (ticket #149, ADR-0019, ADR-0030).

Layer 1 (ADR-0019) says: the kernel of the state of a concrete item equals the finished items of the action on that item, each compressed
on its own and the chances added up exactly. The finished items are listed from the action itself (`finished_at_tiers`, `contract_support.finished`
with the tier of a drawn mod taken from the pool of the item it is drawn onto, as the action's sampler gives it, ticket #155); nothing
here reads a kernel. `closure` lists the concrete items that a set of actions reaches from some starts, so the check runs over every
state the crafts can lead to, not only over hand-picked ones; `check_layer_1` compares one action on one item and says whether it applied.
"""

from collections import defaultdict, deque
from collections.abc import Iterable
from fractions import Fraction

import pytest
from contract_support import finished

from crafting_system.abstraction import Abstraction
from crafting_system.actions import ActionError, Fixed, Rerolled, tiers_of
from crafting_system.items import ExplicitMod, Item


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
                ExplicitMod(mod_id, tiers.get(mod_id, 1), tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats))
                for mod_id, count in sorted(outcome)
                for _ in range(count)
            )
            items.append((share * chance, part.retained.changed(data, mods=(*part.retained.mods, *added))))
    return items


def concrete_pushforward(ability: Abstraction, data, item: Item, action) -> dict:
    """The exact kernel of `action` on `item` as its finished items give it: each compressed by `ability`, the chances added up.

    Raises what `action.outcomes` raises when the game refuses the item.
    """
    expected: dict = defaultdict(Fraction)
    for chance, result in finished_at_tiers(action.outcomes(data, item), data):
        expected[ability.compress(result)] += chance
    return dict(expected)


def closure(data, starts: Iterable[Item], actions, *, limit: int = 4000) -> list[Item]:
    """Every concrete item that `actions` reach from `starts` (the starts included), in the order found; at most `limit`.

    An action that refuses an item (`ActionError`) is skipped there.
    """
    seen: dict[Item, None] = dict.fromkeys(starts)
    queue = list(seen)
    while queue and len(seen) < limit:
        item = queue.pop(0)
        for action in actions:
            try:
                results = finished_at_tiers(action.outcomes(data, item), data)
            except ActionError:
                continue
            for _, result in results:
                if result not in seen:
                    seen[result] = None
                    queue.append(result)
    return list(seen)


def check_layer_1(ability: Abstraction, data, item: Item, action) -> bool:
    """The kernel of `item`'s state equals the compressed finished items of `action` on `item`; where the game refuses, so does the kernel.

    The kernel refuses with the same kind of error the action does. Returns whether the action applied (False: it refused, and the kernel refused too).
    """
    state = ability.compress(item)
    try:
        expected = concrete_pushforward(ability, data, item, action)
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
