"""The actions the solver sees at one state: the offers the game allows there, equal kernels merged (ticket #118).

Two offers with the same kernel at a state (the three levels of one essence, essences whose forced mod
the goal does not read, a Chaos Orb beside a reroll of an equal pool) have the same future from there,
so only the cheapest is offered: the dearer one is never chosen, and the optimal values are unchanged.
This is exact; it is a filter over what `Abstraction.kernel_key` says, with no class or action named here.

A second filter is over what the offers declare. For a target that asks for a corrupted implicit, an action that corrupts and keeps
the explicit mods (`Adds.corrupts` and `Adds.keeps_mods`: a Vaal Orb, the Locus) is an action of a state only if every other
requirement of the goal already passes there (ADR-0036). Its outcome is final and every outcome that can be the goal holds the
mods the state holds, so from any other state it only adds a dead end, which a restart reaches as cheaply: the optimal values
are unchanged (ADR-0031). A target that only allows a corrupted item has no such pruning, because the brick can end in the goal.
"""

from collections.abc import Iterable

from crafting_system.abstraction import Abstraction, CompressedState
from crafting_system.actions import ActionError
from crafting_system.solver import Action

from ._offers import RESTART, BuyStartItem, PricedOffer


def chosen_offers(
    abstraction: Abstraction,
    offers: Iterable[PricedOffer],
    state: CompressedState,
    start: CompressedState,
    *,
    merge_equal: bool = True,
    prune_corrupting: bool = True,
) -> list[PricedOffer]:
    """The offers whose actions the solver sees at `state`, in the order of `offers`: the allowed ones, equal kernels merged.

    This is the choice `solver_actions` makes before it builds any kernel (the key is cheaper than the kernel).
    `restart` is an action of every state but `start` and is never merged (it has no kernel). An offer the game refuses at
    `state`, or no admitted rule covers (`ActionError`), is skipped. With `merge_equal`, of the offers whose
    `Abstraction.kernel_key` is equal at `state` only the cheapest stays (on a tie the earliest in `offers`, the one the
    solver took before); without it every allowed offer stays.

    With `prune_corrupting` (the default) the corrupting offers that `corrupting_offer_pruned` names are skipped at `state`;
    without it they stay, which is the reference a test compares the values against.
    """
    return [
        priced
        for _, priced, _ in keyed_offers(
            abstraction, offers, state, start, merge_equal=merge_equal, prune_corrupting=prune_corrupting
        )
    ]


def keyed_offers(
    abstraction: Abstraction,
    offers: Iterable[PricedOffer],
    state: CompressedState,
    start: CompressedState,
    *,
    merge_equal: bool = True,
    prune_corrupting: bool = True,
) -> list[tuple[int, PricedOffer, object]]:
    """`chosen_offers` with the position of each offer in `offers` and its `Abstraction.kernel_key` at `state`.

    The key is None for `restart` (and for every offer when `merge_equal` is off: no key is built then). The packed walk
    (`_packed.py`) shares one kernel between all the (state, offer) pairs that have the same key.
    """
    allowed: list[tuple[int, PricedOffer, object]] = []  # (position, offer, kernel key or None for restart)
    for position, priced in enumerate(offers):
        if priced.label == RESTART and state == start:
            continue
        if prune_corrupting and corrupting_offer_pruned(abstraction, priced, state):
            continue
        if isinstance(priced.offer.action, BuyStartItem) or not merge_equal:
            allowed.append((position, priced, None))
            continue
        try:
            allowed.append((position, priced, abstraction.kernel_key(state, priced.offer.action)))
        except ActionError:  # the game refuses it here, or no admitted rule covers it
            continue

    cheapest: dict[object, PricedOffer] = {}
    for _, priced, key in allowed:
        if key is not None and (key not in cheapest or priced.cost < cheapest[key].cost):
            cheapest[key] = priced
    return [(position, priced, key) for position, priced, key in allowed if key is None or cheapest[key] is priced]


def solver_actions(
    abstraction: Abstraction,
    offers: Iterable[PricedOffer],
    state: CompressedState,
    start: CompressedState,
    *,
    merge_equal: bool = True,
    prune_corrupting: bool = True,
    cache: dict | None = None,
    chosen: list[PricedOffer] | None = None,
) -> list[Action[CompressedState]]:
    """The solver's actions at `state`: one per priced offer the game allows there, in the order of `offers`.

    `restart` is an action of every state but `start` and is never merged (it has no kernel). An offer
    the game refuses at `state`, or no admitted rule covers (`ActionError`), is skipped. With
    `merge_equal`, of the offers whose `Abstraction.kernel_key` is equal at `state` only the cheapest
    stays (on a tie the earliest in `offers`, the one the solver took before); the key is cheaper than
    the kernel, so the dearer ones are never built. Without it every allowed offer stays.

    `cache`, when given, holds the built solver action of each `(state, label, cost)`, so that solving
    again with more offers does not build a kernel twice (the choice among equal kernels is still made
    on every call; only the action is reused). `chosen` is the result of `chosen_offers` when the caller has it already.
    """
    from ._plan import offer_action  # _plan imports this module

    if chosen is None:
        chosen = chosen_offers(abstraction, offers, state, start, merge_equal=merge_equal, prune_corrupting=prune_corrupting)
    found = []
    for priced in chosen:
        built = None if cache is None else cache.get((state, priced.label, priced.cost))
        if built is None:
            try:
                built = offer_action(abstraction, priced, state, start)
            except ActionError:
                continue
            if cache is not None:
                cache[(state, priced.label, priced.cost)] = built
        found.append(built)
    return found


def corrupting_offer_pruned(abstraction: Abstraction, priced: PricedOffer, state: CompressedState) -> bool:
    """Whether the offer is a corrupting one that the target that asks for a corrupted implicit never needs at `state` (ADR-0036).

    True for an action that corrupts and keeps the explicit mods when the goal asks for a corrupted implicit and `state` does not
    meet every other requirement (`Abstraction.meets_requirements`: the explicit mods and the Eldritch implicits wanted; the quality
    is paid on each try and is not in the state, ADR-0039). A corrupted state refuses every action anyway.
    """
    if not abstraction.goal.asks_corrupted or isinstance(priced.offer.action, BuyStartItem):
        return False
    adds = priced.offer.action.adds(abstraction.data)
    return adds.corrupts and adds.keeps_mods and not abstraction.meets_requirements(state)
