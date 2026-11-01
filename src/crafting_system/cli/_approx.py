"""An approximate answer: the two models of a coarse state, solved, and the facts that mark the answer (ADR-0023, ticket #127).

`solve_level` solves the optimistic and the pessimistic model of one `Candidate` (`solver.solve_bounds`) and
returns an `Approximation`: the certified interval of the mean cost, its gap, the pessimistic policy (an ordinary
policy of the exact problem, on blocks) and what level it came from. A tail-cut level (kind "tail") runs
`solver.solve_tail_cut` over the coarse state it sits on: its policy holds the expanded exact states, and the
other states it reaches are blocks that follow the coarse policy. `climb` walks the ladder of a `Decision` and
stops at the first level whose certified gap is at most `TOLERANCE`; when none is, it keeps the narrowest interval
and says so. Nothing here reads the clock but the `perf_counter` around the solves.

The bounds are of the cost still to pay from the start item (`Plan.mean_remaining` is the upper one); the price of
the start item is added by whoever prints them.
"""

import time
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from crafting_system.abstraction import CompressedState, integer_weights
from crafting_system.actions import ActionError
from crafting_system.solver import (
    Action,
    Bounds,
    ConvergenceError,
    NoPolicyError,
    Outcome,
    Solution,
    TailCut,
    solve_bounds,
    solve_tail_cut,
)

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
    expanded: int = 0  # the exact states a tail cut expanded (0 for a coarse level)

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
        self.known: dict[CompressedState, list[Action[CompressedState]]] = {}  # the tail-cut levels solve the same blocks again
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
        if block not in self.known:
            self.known[block] = self._actions(block)
        return self.known[block]

    def _actions(self, block: CompressedState) -> list[Action[CompressedState]]:
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


class ExactModel:
    """The exact compressed states under the offered actions (the tail cut expands them), remembering their actions."""

    def __init__(self, abstraction, start: CompressedState, offers: Iterable[PricedOffer]) -> None:
        self.abstraction = abstraction
        self.start = start
        self.offers = tuple(offers)
        self.known: dict[CompressedState, list[Action[CompressedState]]] = {}

    def is_goal(self, state: CompressedState) -> bool:
        return self.abstraction.is_goal(state)

    def actions(self, state: CompressedState) -> list[Action[CompressedState]]:
        if state not in self.known:
            found = []
            for priced in self.offers:
                if isinstance(priced.offer.action, BuyStartItem):
                    if state != self.start:
                        found.append(Action(priced.label, priced.cost, (Outcome(self.start, 1),)))
                    continue
                try:
                    weights = integer_weights(self.abstraction.kernel(state, priced.offer.action))
                except ActionError:
                    continue
                found.append(Action(priced.label, priced.cost, tuple(Outcome(s, w) for s, w in weights.items())))
            self.known[state] = found
        return self.known[state]


class Models:
    """What the levels of one `climb` share: the models of each coarse state and the exact model, so nothing is built twice."""

    def __init__(self, start: CompressedState, offers: Iterable[PricedOffer]) -> None:
        self.start = start
        self.offers = tuple(offers)
        self.blocks: dict[int, tuple[object, BlockModel, BlockModel]] = {}
        self.exact: ExactModel | None = None

    def of(self, coarsening) -> tuple[BlockModel, BlockModel]:
        block = coarsening.coarsen(self.start)
        found = self.blocks.setdefault(
            id(coarsening),
            (coarsening, BlockModel(coarsening, block, self.offers, "lower"), BlockModel(coarsening, block, self.offers, "upper")),
        )
        return found[1], found[2]

    def exact_model(self, abstraction) -> ExactModel:
        if self.exact is None:
            self.exact = ExactModel(abstraction, self.start, self.offers)
        return self.exact


def solve_level(candidate: Candidate, start: CompressedState, offers: Iterable[PricedOffer], models: Models | None = None) -> Solved:
    """Solve the level and certify the interval of the start: two models on blocks, or the tail cut over them."""
    models = models or Models(start, offers)
    if candidate.level.kind == "tail":
        return solve_tail_level(candidate, start, models)
    coarsening = candidate.coarsening
    block = coarsening.coarsen(start)
    began = time.perf_counter()
    lower, upper = models.of(coarsening)
    bounds: Bounds[CompressedState] = solve_bounds(lower, upper, [block])
    seconds = time.perf_counter() - began
    if block not in bounds.upper:
        raise ValueError("the solver returned no value for the start block")
    solution = Solution(bounds.upper, bounds.policy, bounds.pessimistic_error)
    gap = bounds.gap_at(block)
    approximation = Approximation(
        bounds.lower[block], bounds.upper[block], gap, candidate.level.name, max(len(bounds.lower), len(bounds.upper)), TOLERANCE, coarsening
    )
    return Solved(approximation, solution, block, seconds)


def solve_tail_level(candidate: Candidate, start: CompressedState, models: Models) -> Solved:
    """The tail cut at the level's `theta` over its coarse state; the exact start is the start of the policy it returns.

    The policy has an action for each expanded exact state and for each block the cut states fall in (the
    coarse policy), so it can be walked from the start; a cut state is shown as its block.
    """
    coarsening, theta = candidate.coarsening, candidate.level.theta
    began = time.perf_counter()
    lower, upper = models.of(coarsening)
    found: TailCut[CompressedState, CompressedState] = solve_tail_cut(
        models.exact_model(coarsening.abstraction), lower, upper, coarsening.coarsen, start, theta
    )
    seconds = time.perf_counter() - began
    coarse = found.coarse
    block_start = coarsening.coarsen(start)

    def shown(state: CompressedState) -> CompressedState:
        return state if state in found.expanded or coarsening.is_goal(state) else coarsening.coarsen(state)

    policy = dict(coarse.policy)
    if not found.expanded and block_start in coarse.policy:  # nothing expanded: the start item follows the coarse policy of its block
        policy[start] = coarse.policy[block_start]
    for state, action in found.bounds.policy.items():
        merged: defaultdict[CompressedState, int] = defaultdict(int)
        for outcome in action.outcomes:
            merged[shown(outcome.state)] += outcome.weight
        policy[state] = Action(action.label, action.cost, tuple(Outcome(s, w) for s, w in merged.items()))
    values = {**coarse.upper, **found.bounds.upper}
    solution = Solution(values, policy, found.bounds.pessimistic_error)
    low, high = found.bounds.lower[start], found.bounds.upper[start]
    approximation = Approximation(
        low, high, found.bounds.gap_at(start), candidate.level.name, len(coarse.lower) + len(found.expanded), TOLERANCE, coarsening,
        expanded=len(found.expanded),
    )
    return Solved(approximation, solution, start, seconds)


def climb(decision: Decision, start: CompressedState, offers: Iterable[PricedOffer]) -> Solved:
    """Try the levels of `decision` in order; the first within the tolerance wins, else the narrowest interval, with a message.

    Raises `ValueError` when no level has a policy that reaches the goal (every upper bound is infinite).
    """
    offers = tuple(offers)
    models = Models(start, offers)
    best: Solved | None = None
    spent = 0.0
    for candidate in decision.levels:
        try:
            solved = solve_level(candidate, start, offers, models)
        except (NoPolicyError, ConvergenceError):
            if candidate.level.kind != "tail":
                raise
            continue  # a tail cut that has no policy to follow or does not converge leaves the levels before it as they are
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
            f"(level: {approximation.level}). " + exact_offer(decision.transitions, decision.predicted, decision.estimate is None or decision.estimate.complete),
            approximation.expanded,
        )  # fmt: skip
    return Solved(approximation, best.solution, best.start, spent)
