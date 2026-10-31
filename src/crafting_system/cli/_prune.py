"""The actions the solver sees at one state: the offers the game allows there, equal kernels merged (ticket #118).

Two offers with the same kernel at a state (the three levels of one essence, essences whose forced mod
the goal does not read, a Chaos Orb beside a reroll of an equal pool) have the same future from there,
so only the cheapest is offered: the dearer one is never chosen, and the optimal values are unchanged.
This is exact; it is a filter over what `Abstraction.kernel_key` says, with no class or action named here.
"""

from collections.abc import Iterable

from crafting_system.abstraction import Abstraction, CompressedState
from crafting_system.actions import ActionError
from crafting_system.solver import Action

from ._offers import RESTART, BuyStartItem, PricedOffer


def solver_actions(
    abstraction: Abstraction,
    offers: Iterable[PricedOffer],
    state: CompressedState,
    start: CompressedState,
    *,
    merge_equal: bool = True,
) -> list[Action[CompressedState]]:
    """The solver's actions at `state`: one per priced offer the game allows there, in the order of `offers`.

    `restart` is an action of every state but `start` and is never merged (it has no kernel). An offer
    the game refuses at `state`, or no admitted rule covers (`ActionError`), is skipped. With
    `merge_equal`, of the offers whose `Abstraction.kernel_key` is equal at `state` only the cheapest
    stays (on a tie the earliest in `offers`, the one the solver took before); the key is cheaper than
    the kernel, so the dearer ones are never built. Without it every allowed offer stays.
    """
    from ._plan import offer_action  # _plan imports this module

    allowed: list[tuple[PricedOffer, object]] = []  # (offer, kernel key or None for restart)
    for priced in offers:
        if priced.label == RESTART and state == start:
            continue
        if isinstance(priced.offer.action, BuyStartItem) or not merge_equal:
            allowed.append((priced, None))
            continue
        try:
            allowed.append((priced, abstraction.kernel_key(state, priced.offer.action)))
        except ActionError:  # the game refuses it here, or no admitted rule covers it
            continue

    cheapest: dict[object, PricedOffer] = {}
    for priced, key in allowed:
        if key is not None and (key not in cheapest or priced.cost < cheapest[key].cost):
            cheapest[key] = priced

    found = []
    for priced, key in allowed:
        if key is not None and cheapest[key] is not priced:
            continue
        try:
            found.append(offer_action(abstraction, priced, state, start))
        except ActionError:
            continue
    return found
