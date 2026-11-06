"""Helpers of the crafted-pattern tests (ticket #497): the exact graph of a small model, the brute force of a key's members, the checks.

`exact_values` walks every state a set of offers reaches from a start (the concrete graph the research walks) and solves it on the packed solver;
`all_members` lists the concrete states of a key by brute force (every item of the data that compresses to the key's slots), which is what the
member policies are compared with. Nothing here imports the member builder of the code under test but `Pattern`.
"""

import random
from collections import defaultdict
from fractions import Fraction

from crafting_system.abstraction import Abstraction, CompressedState, integer_weights
from crafting_system.abstraction._pattern import Pattern, PatternOffer
from crafting_system.actions import ActionError
from crafting_system.solver import PackedBuilder, solve_packed


def exact_values(ab: Abstraction, start: CompressedState, offers: list[PatternOffer]) -> dict[CompressedState, float]:
    """The exact value (mean cost to the goal) of every state `offers` reach from `start`, with the restart to `start` where an offer has no action."""
    states: list[CompressedState] = [start]
    index: dict[CompressedState, int] = {start: 0}

    def intern(state: CompressedState) -> int:
        found = index.get(state)
        if found is None:
            found = index[state] = len(states)
            states.append(state)
        return found

    builder = PackedBuilder()
    kernels: dict[tuple, int] = {}
    i = 0
    while i < len(states):
        state = states[i]
        goal = ab.is_goal(state)
        if not goal:
            for oi, offer in enumerate(offers):
                if offer.action is None:
                    if state == start:
                        continue
                    weights = {0: 1}
                else:
                    try:
                        weights = {intern(s): w for s, w in integer_weights(ab.kernel(state, offer.action)).items()}
                    except ActionError:
                        continue
                key = tuple(sorted(weights.items()))
                kid = kernels.get(key)
                if kid is None:
                    kid = kernels[key] = builder.kernel([k for k, _ in key], [w for _, w in key])
                builder.action(oi, offer.cost, kid)
        builder.close_state(goal)
        i += 1
    solved = solve_packed(builder.build(), merge=False)
    return {state: float(solved.value[k]) for k, state in enumerate(states)}


def all_members(pattern: Pattern, key) -> set[CompressedState]:
    """Every state of the key by the member builder in its exhaustive mode (the brute force that the other modes are compared with)."""
    from crafting_system.abstraction._pattern import Mode

    return set(pattern.members(key, Mode.ALL))


def pushed(pattern: Pattern, ab: Abstraction, state: CompressedState, action) -> dict | None:
    """The kernel of `action` on `state` seen through the key, or None when the action refuses the state."""
    try:
        kernel = ab.kernel(state, action)
    except ActionError:
        return None
    out: dict = defaultdict(Fraction)
    for successor, chance in kernel.items():
        out[pattern.key(successor)] += chance
    return dict(out)


def check_dominates(pattern: Pattern, ab: Abstraction, key, action, mode, rng: random.Random, trials: int = 30) -> tuple[int, int]:
    """The offered members of `mode` are at least as good as every member of the key, for random values of the successor keys.

    For `trials` random value functions, the least backup over the offered members must not exceed the backup of any member, and the action
    must be offered whenever some member can take it. Returns (members compared, offered members that could take the action).
    """
    members = all_members(pattern, key)
    offered = pattern.members(key, mode)
    assert set(offered) <= members, "an offered member is not a member of the key"
    kernels = {m: pushed(pattern, ab, m, action) for m in members}
    legal = {m: k for m, k in kernels.items() if k is not None}
    offered_legal = [pushed(pattern, ab, m, action) for m in offered]
    offered_legal = [k for k in offered_legal if k is not None]
    if not legal:
        return len(members), 0
    assert offered_legal, "the action is legal in some member but in none of those offered"
    targets = sorted({k for kernel in legal.values() for k in kernel}, key=repr)
    for _ in range(trials):
        value = {t: Fraction(rng.randint(0, 10_000), rng.randint(1, 100)) for t in targets}
        best_offered = min(sum((c * value[k] for k, c in kernel.items()), Fraction(0)) for kernel in offered_legal)
        for kernel in legal.values():
            assert best_offered <= sum((c * value[k] for k, c in kernel.items()), Fraction(0)), (key, action)
    return len(members), len(offered_legal)
