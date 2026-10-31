"""An approximate answer: the two models of a coarse state, solved, and the facts that mark the answer (ADR-0023, ticket #127).

`solve_level` solves the optimistic and the pessimistic model of one `Candidate` (`solver.solve_bounds`) and
returns an `Approximation`: the certified interval of the mean cost, its gap, the pessimistic policy (an ordinary
policy of the exact problem, on blocks) and what level it came from. `climb` walks the ladder of a `Decision` and
stops at the first level whose certified gap is at most `TOLERANCE`; when none is, it keeps the narrowest interval
and says so. Nothing here reads the clock but the `perf_counter` around the solves.

The bounds are of the cost still to pay from the start item (`Plan.mean_remaining` is the upper one); the price of
the start item is added by whoever prints them.
"""

import time
from collections.abc import Iterable
from dataclasses import dataclass

from crafting_system.abstraction import CompressedState, integer_weights
from crafting_system.actions import ActionError
from crafting_system.solver import Action, Bounds, Outcome, Solution, solve_bounds

from ._decide import TOLERANCE, Candidate, Decision, exact_offer
from ._offers import BuyStartItem, PricedOffer


@dataclass(frozen=True)
class Approximation:
    """What marks an answer as approximate: the interval around the exact mean, the level, and the message if it is wide.

    `lower` and `upper` are certified bounds on the mean cost still to pay from the start item, `upper` being
    the cost of the policy shown; `gap = upper / lower - 1`, the solver's own error included. `message` is
    empty when the gap is within `tolerance`, otherwise it says that it is not and what to do.
    """

    lower: float
    upper: float
    gap: float
    level: str
    blocks: int
    tolerance: float
    coarsening: object  # the `Coarsening` that built the blocks (a later ticket lifts the policy through it)
    message: str = ""

    @property
    def within_tolerance(self) -> bool:
        return self.gap <= self.tolerance


@dataclass(frozen=True)
class Solved:
    """One level solved: the approximation, the pessimistic solution on blocks, the start block and the seconds spent."""

    approximation: Approximation
    solution: Solution[CompressedState]
    start: CompressedState
    seconds: float


class BlockModel:
    """The solver's view of the blocks of a coarse state under the offered actions, in the model of `bound`."""

    def __init__(self, coarsening, start: CompressedState, offers: Iterable[PricedOffer], bound: str) -> None:
        self.coarsening = coarsening
        self.start = start
        self.offers = tuple(offers)
        self.bound = bound
        for priced in self.offers:
            if not isinstance(priced.offer.action, BuyStartItem):
                coarsening.require_invariant(priced.offer.action)  # a refused action is not a model with fewer actions

    def is_goal(self, block: CompressedState) -> bool:
        return self.coarsening.is_goal(block)

    def actions(self, block: CompressedState) -> list[Action[CompressedState]]:
        found = []
        for priced in self.offers:
            if isinstance(priced.offer.action, BuyStartItem):
                if block != self.start:
                    found.append(Action(priced.label, priced.cost, (Outcome(self.start, 1),)))
                continue
            try:
                kernel = self.coarsening.kernel(block, priced.offer.action, self.bound)
            except ActionError:
                continue
            weights = integer_weights(kernel)
            found.append(Action(priced.label, priced.cost, tuple(Outcome(s, w) for s, w in weights.items())))
        return found


def solve_level(candidate: Candidate, start: CompressedState, offers: Iterable[PricedOffer]) -> Solved:
    """Solve the two models of the level and certify the interval of the start block."""
    coarsening = candidate.coarsening
    block = coarsening.coarsen(start)
    offers = tuple(offers)
    began = time.perf_counter()
    bounds: Bounds[CompressedState] = solve_bounds(
        BlockModel(coarsening, block, offers, "lower"), BlockModel(coarsening, block, offers, "upper"), [block]
    )
    seconds = time.perf_counter() - began
    if block not in bounds.upper:
        raise ValueError("the solver returned no value for the start block")
    solution = Solution(bounds.upper, bounds.policy, bounds.pessimistic_error)
    gap = bounds.gap_at(block)
    approximation = Approximation(
        bounds.lower[block], bounds.upper[block], gap, candidate.level.name, max(len(bounds.lower), len(bounds.upper)), TOLERANCE, coarsening
    )
    return Solved(approximation, solution, block, seconds)


def climb(decision: Decision, start: CompressedState, offers: Iterable[PricedOffer]) -> Solved:
    """Try the levels of `decision` in order; the first within the tolerance wins, else the narrowest interval, with a message.

    Raises `ValueError` when no level has a policy that reaches the goal (every upper bound is infinite).
    """
    offers = tuple(offers)
    best: Solved | None = None
    spent = 0.0
    for candidate in decision.levels:
        solved = solve_level(candidate, start, offers)
        spent += solved.seconds
        if best is None or solved.approximation.gap < best.approximation.gap:
            best = solved
        if solved.approximation.within_tolerance:
            break
    if best is None or best.approximation.upper == float("inf"):
        raise ValueError("no coarse level has a policy of the offered actions that reaches the goal; the exact run is needed")
    approximation = best.approximation
    if not approximation.within_tolerance:
        approximation = Approximation(
            approximation.lower, approximation.upper, approximation.gap, approximation.level, approximation.blocks,
            approximation.tolerance, approximation.coarsening,
            f"No level reaches {TOLERANCE:.0%}: the narrowest certified interval has a gap of {approximation.gap:.2%} "
            f"(level: {approximation.level}). " + exact_offer(decision.transitions, decision.predicted),
        )  # fmt: skip
    return Solved(approximation, best.solution, best.start, spent)
