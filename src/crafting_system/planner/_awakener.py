"""The Awakener's Orb (B3) in the one envelope search: each donor is an acquisition of its own, searched by the same search (ticket #832, ADR-0022, ADR-0032).

An `AwakenersOrb` consumes a second item, its donor: an item of another influence whose only influence mod is the orb's `donor_mod` (the want of
`Abstraction.donor_key`, ADR-0062 decision 1). ADR-0022 prices such an action by the value of the donor's acquisition: one use costs the orb plus
`V(donor)`, a retry pays both again. This module makes that value with the planner's own search and folds it into the offer's cost, so the
target's search (and, for a check, the full walk) sees an ordinary action with a price:

* **The donor's search.** `solve_donor` runs `_envelope_plan.envelope_result` on an abstraction of the donor's own: the target's base and
  item level, the offered actions (the Awakener's Orb enabled, so the states tell influence mods apart, `Reads.influenced`, but not offered),
  and the goal "holds `donor_mod`". Its goal states are the states with the want's key (`goal=`), so a donor that holds the mod and another
  influence mod goes on (the bound's goal keys are tips there, `CraftingProblem`). The donor starts as the normal base of its influence
  (`AwakenersOrb.inputs`) and its restart buys that base again (`donor_base_cost`).
* **Its bound.** The donor's `lower` is the bound of that search with its error taken off: the goal "holds `donor_mod`" holds every state with
  the want's key, so the least cost to reach it is at most the least cost to reach the want (fewer goal states never cost less). Its `upper` is
  the exact mean of the executable donor plan the search returns (`PackedResult.solution.values[start]`).
* **The target's search** takes the orb at `cost + upper` (`fold`). Its plan is executable: every use makes a donor by the donor's plan, whose
  mean is `upper`, and the runs are independent (ADR-0022, "Risk and simulator follow the policy tree"), so the target's mean is exact for the
  plan of the target and its donors together.
* **The lower bound of the whole.** For donor prices `c` (one per donor) let `V(c)` be the cheapest target cost; `V(c) = min_pi (a_pi + sum_d
  n_pi,d c_d)`, with `n_pi,d` the expected uses of donor `d` under policy `pi`, so `V` is nondecreasing in each `c_d`. The true optimum is
  `V(V*_d) >= V(L_d)`, and for the policy `pi'` optimal at `L`: `V(U) <= a_pi' + sum_d n_d U_d = V(L) + sum_d n_d (U_d - L_d)`. Each use of
  donor `d` costs at least `o_d + L_d` (its orb and its donor), so `n_d (U_d - L_d) <= n_d (o_d + L_d) r` with `r = max_d (U_d - L_d) / (o_d +
  L_d)`, and `sum_d n_d (o_d + L_d) <= V(L)`. Hence `V(L) >= V(U) / (1 + r)`: the target's search, run at the upper prices, proves a bound `LB`
  of `V(U)`, and `LB / (1 + r)` is a lower bound of the true cost (`whole_lower`). With every donor exact, `r` is 0 and the target's bound is
  the bound of the whole. `tests/test_awakener_search.py` checks it against the exact product of ADR-0022 (`solver.Acquisition`) on a small pool.
* **The least fixed point.** A donor never takes an Awakener's Orb: `solve_donor` leaves the orbs out of the donor's offers, and none could
  serve (the orb's result holds two influences, the want one, and no offered action removes an influence), so no donor's plan reads a donor's
  value and the system of ADR-0022 is solved in one pass, donors first.
* **Where the effort goes.** A donor's search stops as the target's does (`_plan.search_gap`): exact under the plan's aim, at a proved gap past
  it, and each donor gets an equal share of the time left with the target (`_plan.search_net`), so the donors never leave the target nothing
  (OR-33). A donor stopped at a gap or a net leaves its `[lower, upper]`, and `r` carries it into the bound of the whole. Effort is not yet
  moved between the donors and the target by their share of the gap (#832's "refinement", #1001).

Only donors whose mod the target names are offered (`_offers`): a donor mod the target does not ask for gives the item nothing it wants.
"""

import dataclasses
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import Action, OutOfScopeError

from ._limits import CONSUMES, DISPLAY, Limit, claim
from ._offers import AWAKENER_KIND, DRAW_COST_SHARE, RESTART, BuyStartItem, Offer, PricedOffer, donor_wants, takes_inputs

DONOR_PART = "second item"  # the part of a folded offer that is its donor's run


@dataclass(frozen=True)
class Donor:
    """One donor's search: the orb it serves, the bound and the exact mean of its plan, and how the search ended."""

    action: Action
    lower: float  # no plan of this donor costs less (its bound with its error taken off)
    upper: float  # the exact mean of the donor plan the target's plan uses
    exact: bool
    stopped: str | None
    states: int  # the states of the donor plan's reach
    seconds: float
    mod: str = ""  # the donor's mod, as the plan names it

    @property
    def share(self) -> float:
        """`(upper - lower) / lower`, 0 for an exact donor."""
        return 0.0 if self.exact else max(self.upper - self.lower, 0.0) / max(self.lower, 1e-300)


def awakener_offers(priced: Sequence[PricedOffer]) -> tuple[PricedOffer, ...]:
    return tuple(p for p in priced if p.offer.kind == AWAKENER_KIND)


def donor_base_cost(priced: Sequence[PricedOffer]) -> float:
    """What the donor's restart is charged: the base it buys again is not priced (`donor_base_limit`), and a restart that is free would lie on a
    cycle of no cost, which the solvers cannot certify; it takes the share of the cheapest paid offer that the draw of a bought listing takes."""
    paid = [p.cost for p in priced if p.cost > 0 and p.offer.resources]
    return DRAW_COST_SHARE * min(paid) if paid else 1.0


def donor_abstraction(target_abstraction: Abstraction, action: Action) -> Abstraction:
    """The abstraction a donor of `action` is searched on: the target's base, item level and enabled actions, the goal "holds `donor_mod`" (the
    mods of the `want` of the orb's one input)."""
    ab = target_abstraction
    found = donor_wants(ab.data, action)
    if found is None:
        action.inputs(ab.data)  # raises what the action says of its donor
        raise OutOfScopeError(f"{action.label(ab.data)} names no one second item")  # left out with its limit (`solve_donors`)
    goal = Goal((Wanted(found[1]),))
    return Abstraction(
        ab.data, goal, ab.base_id, ab.item_level, ab._actions, metamods=ab.models_metamods, enchantment=ab.enchantment, allow_inputs=False,
        weights=ab._weights,
    )


def solve_donor(
    target_abstraction: Abstraction,
    action: Action,
    priced: Sequence[PricedOffer],
    *,
    net=None,
    tolerance: float = 1e-10,
    progress: Callable[[str], None] | None = None,
    gap: float = 0.0,
    gap_after: float | None = None,
) -> tuple[Donor, object]:
    """Search the donor of `action` with the offers of the target (the Awakener's Orbs and the target's restart left out); returns the `Donor`
    and the search's `PackedResult`. Exact unless `gap`/`gap_after` (the target's stop, `envelope_result`) or `net` stops it. Raises what
    `envelope_result` raises (`NoPolicy` when no donor plan reaches the want, or the net stopped it before one)."""
    from ._envelope_plan import envelope_result

    import time

    began = time.perf_counter()
    ab = donor_abstraction(target_abstraction, action)
    (need,) = action.inputs(ab.data)
    start = ab.compress(need.start)
    want = ab.donor_key(ab.compress(need.want), action)
    restart = PricedOffer(Offer(RESTART, BuyStartItem(need.start), {}, shares=False), donor_base_cost(priced), ())
    offers = (*(p for p in priced if _applies_to_donors(p)), restart)
    packed = envelope_result(
        ab, start, offers, net=net, tolerance=tolerance, progress=progress, gap=gap, gap_after=gap_after,
        goal=lambda state: ab.donor_key(state, action) == want,
    )  # fmt: skip
    info = packed.info["envelope"]
    upper = float(packed.solution.values[start])
    lower = upper if info.exact else min(float(info.lower), upper)  # the search's certified bound, as the target's is read (`_plan`)
    mod = ", ".join(sorted(m.mod_id for m in need.want.mods))
    donor = Donor(action, lower, upper, bool(info.exact), info.stopped, len(packed.solution.policy), time.perf_counter() - began, mod)
    return donor, packed


def solve_donors(
    target_abstraction: Abstraction,
    awakened: Sequence[PricedOffer],
    priced: Sequence[PricedOffer],
    *,
    net: Callable[[int], object] | None = None,
    stop: Callable[[], tuple[float, float | None]] | None = None,
) -> tuple[tuple[Donor, ...], tuple[Limit, ...]]:
    """Each orb's donor by `solve_donor`; an orb whose donor no plan makes is left out and the plan says why (`no_donor_limit`, OR-13).

    `net(searches)` is the net of a donor's search when `searches` searches are still to run, the target's included (`_plan.search_net`: an
    equal share of the time left, so the donors never leave the target nothing, OR-33); `stop()` is the target's stop at the moment each donor's
    search starts (`_plan.search_gap`: the aim the run has not yet spent), exact when None."""
    from crafting_system.actions import NotApplicableError, OutOfScopeError
    from crafting_system.solver import ConvergenceError

    from ._envelope import NoPolicy
    from ._envelope_plan import BoundError

    donors, left_out = [], []
    for done, orb in enumerate(awakened):
        searches = len(awakened) - done + 1
        gap, gap_after = (0.0, None) if stop is None else stop()
        try:
            donor, _ = solve_donor(
                target_abstraction, orb.offer.action, priced, net=None if net is None else net(searches), gap=gap, gap_after=gap_after
            )
        except (NoPolicy, BoundError, ConvergenceError, OutOfScopeError, NotApplicableError) as error:  # either family: the orb is left out, said
            left_out.append(no_donor_limit(orb.label, str(error)))
            continue
        donors.append(donor)
    return tuple(donors), tuple(left_out)


def _applies_to_donors(priced: PricedOffer) -> bool:
    """Whether a target's offer is offered to a donor: not the target's restart (the donor buys its own base), not an offer that opens the
    target's bought listing (ADR-0064), and no action that consumes a second item (an Awakener's Orb: a donor never takes one)."""
    action = priced.offer.action
    return not isinstance(action, BuyStartItem) and not action.opens_listing and not takes_inputs(action)


def fold(priced: Sequence[PricedOffer], donors: Sequence[Donor]) -> tuple[PricedOffer, ...]:
    """The offers with each Awakener's Orb priced at its orb and its donor's mean (`Donor.upper`), the donor a part of its own."""
    by_action = {donor.action: donor for donor in donors}
    out = []
    for p in priced:
        donor = by_action.get(p.offer.action)
        if donor is None:
            out.append(p)
            continue
        part = (DONOR_PART, 1, donor.upper, "made by its own plan")
        out.append(dataclasses.replace(p, cost=p.cost + donor.upper, parts=(*p.parts, part)))
    return tuple(out)


def whole_lower(lower: float, priced: Sequence[PricedOffer], donors: Sequence[Donor]) -> float:
    """The lower bound of the target and its donors from the target's bound `lower` at the upper donor prices (see the module text). A donor
    whose use is proved to cost nothing (`o_d + L_d` 0) proves nothing of the whole: the bound is 0."""
    orb = {p.offer.action: p.cost for p in priced}
    r = 0.0
    for donor in donors:
        if donor.exact:
            continue
        floor = orb.get(donor.action, 0.0) + donor.lower
        r = max(r, max(donor.upper - donor.lower, 0.0) / floor if floor > 0.0 else math.inf)
    if not math.isfinite(lower):
        return lower
    return 0.0 if math.isinf(r) else lower / (1.0 + r)


def whole_info(info, priced: Sequence[PricedOffer], donors: Sequence[Donor]):
    """The target search's `EnvelopeInfo` as the answer of the target and its donors: its bound `whole_lower`, exact only when every donor is,
    and, for a target that closed exactly beside a donor that did not, the stop said as the donor's (OR-13)."""
    if not donors:
        return info
    stopped = [d for d in donors if not d.exact]
    found = dataclasses.replace(info, lower=whole_lower(info.lower, priced, donors), exact=info.exact and not stopped)
    if info.exact and stopped:
        said = "; ".join(f"the search of the second item for {d.mod} stopped ({d.stopped})" for d in stopped)
        found = dataclasses.replace(found, stopped=f"the plan's own search closed, but {said}")
    return found


def no_donor_limit(label: str, why: str) -> Limit:
    """An Awakener's Orb left out because no plan makes its donor (OR-13)."""
    return Limit(
        CONSUMES,
        "An Awakener's Orb is not offered",
        f"{label}: no plan of the offered actions makes its second item ({why})",
        **claim("the plans without this Awakener's Orb", "A plan with it could be cheaper."),
    )


def donor_limits(donors: Sequence[Donor], stand_in: float) -> tuple[Limit, ...]:
    """What a plan with Awakener's Orbs says (OR-13): the donor's base has a stand-in price (`stand_in`, `donor_base_cost`), the donors are the
    target's own mods, how a donor is made is not drawn, and a donor whose search a net stopped carries its gap into the plan's."""
    found = [
        Limit(
            CONSUMES,
            "A second item's base is a stand-in price",
            "each Awakener's Orb takes a second item of another influence, made from a Normal base of that influence; the planner has no price for "
            f"that base: the first one is not counted and each one bought again is counted at a stand-in of {stand_in:,.2f} Chaos (a tenth of the "
            "cheapest paid action)",
            "The plan costs at least what it says less the stand-ins, plus the price of each influenced Normal base it buys.",
        ),
        Limit(
            CONSUMES,
            "Awakener's Orbs only with second items of wanted mods",
            "an Awakener's Orb is offered only with a second item whose influence mod the target asks for",
            **claim(
                "the plans whose Awakener's Orbs carry over a mod the target asks for",
                "An Awakener's Orb with a second item of some other mod could in principle be cheaper.",
            ),
        ),
        Limit(
            DISPLAY,
            "How each second item is made is not shown",
            "the steps show the target's own item; an Awakener's Orb's second item is made by its own run of orbs, which the steps do not draw yet",
            "The costs count every second item and every orb used to make it, at its average cost.",
        ),
    ]
    stopped = [d for d in donors if not d.exact]
    if stopped:
        found.append(
            Limit(
                CONSUMES,
                "A second item's plan is not proved the cheapest",
                "; ".join(f"the second item for {d.mod} stopped ({d.stopped}) at {d.upper:,.2f} Chaos, at least {d.lower:,.2f}" for d in stopped),
                "The lower figure of the plan allows for it.",
            )
        )
    return tuple(found)
