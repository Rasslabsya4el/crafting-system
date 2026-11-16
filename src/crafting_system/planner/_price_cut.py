"""The exact price cut (#1069, OR-12, OR-13): an offer that costs at least as much as buying the start item again and following a plan already known
is never better than that restart, so it is left out before the model of the item is built.

**The argument.** Let `p` be the price of the bought start item and `U` the mean cost (after the start item) of an executable plan from the start
`s0`, made of offers that are all offered here, taken with its certified error added, so that `U >= V*(s0)`, the cheapest cost from the start with
every offer. Costs are never negative, so `V* >= 0`. Let `a` be an offer whose own price is `c(a) >= p + U`.

* At a state `s` that is not the start, the restart is offered (`_envelope_plan.CraftingProblem.candidates`, `_prune.keyed_offers`: a bought start
  is offered again at every state but the start, whatever the state holds: an unopened listing, a fractured mod, an imprint), and
  `Q*(s, restart) = p + V*(s0) <= p + U <= c(a) <= c(a) + E[V*(s')] = Q*(s, a)`. So `a` is never strictly better than the restart at `s`.
* At the start itself the restart is not offered, but `Q*(s0, a) >= c(a) >= p + U >= U >= V*(s0)` (`p > 0`): `a` is never strictly better than
  the best action there either.

Dropping `a` from every state therefore leaves `V*` unchanged at every state: the cut is exact, and a tie (`c(a) = p + U`) keeps the value too.
Nothing here depends on what `a` is, so every offer is judged, not only the blocking crafts that motivated it; the restart itself is never cut.

**Where the premise fails, nothing is cut.** A given start (`StartPrice.given`, OR-6) has no restart: an item it cannot buy again may be worth an
offer dearer than any plan from the start, so no offer is dropped. A plan made once per reading of a rule axis has a different `U` per reading, so the
planner does not cut there either. An Awakener's Orb's donor and an offer that takes donors search a second item whose restart is not this
start item's, and a route judged against the plan is a fixed policy that may name the offer: no cut there either (`_plan.price_cut_applies`).
Hinekora's Lock: `U` is the mean of a plan without the Lock, so `U >= V*` without it `>= V*` with it (`V` below). A peek at `a` from a state `s`
costs the Lock's price `L` and then `min(c(a) + V(s'), V(s))` for the outcome `s'` seen, and `c(a) >= p + U >= V(s)` at every `s` but the start
(and above `V(s0)` there), so the minimum is `V(s)` and the peek costs `L + V(s) >= V(s)`: never better either. `U` must be the mean of a plan of the same game: the planner takes it from a plan of a subset of the
offers, which is a plan of the whole set too: today the offers without the metamod crafts that the rule of blocking crafts offers unasked (#886),
which make the model track every mod's protected tags on every state (`_plan.known_upper`).
"""

import math
from collections.abc import Sequence

from . import _limits
from ._limits import Limit
from ._offers import BuyStartItem, PricedOffer


def restart_dominated(priced: Sequence[PricedOffer], start_price: float, upper: float) -> tuple[tuple[PricedOffer, ...], tuple[PricedOffer, ...]]:
    """(`priced` without the offers whose price is at least `start_price + upper`, those offers), the restart always kept (the module text).

    `upper` is a certified upper figure of the cheapest cost from the start after the start item (at least the mean of an executable plan, its error
    added); a figure that is not finite cuts nothing."""
    if not math.isfinite(upper) or not math.isfinite(start_price):
        return tuple(priced), ()
    ceiling = start_price + upper
    kept = tuple(each for each in priced if isinstance(each.offer.action, BuyStartItem) or each.cost < ceiling)
    held = {id(each) for each in kept}  # by identity: a test of membership in `kept` compared every pair (9,000 fossil sets: 12 s, #1073)
    cut = tuple(each for each in priced if id(each) not in held)
    return kept, cut


def price_cut_limit(cut: Sequence[PricedOffer], start_price: float, upper: float) -> Limit:
    """The limit of the offers `restart_dominated` left out (OR-13): why each can never help, and that the plan is unaffected."""
    return Limit(
        _limits.PROVED,
        "Not searched",
        f"each costs at least {start_price + upper:,.2f} Chaos a use: buying the start item again ({start_price:,.2f}) and following a plan already "
        f"found ({upper:,.2f} on average) costs no more, from any item the craft can reach",
        "The plan is unaffected: buying the start item again is never dearer than any of these actions, so leaving them out changes no cost.",
        tuple(sorted({each.label for each in cut})),
    )


__all__ = ["price_cut_limit", "restart_dominated"]
