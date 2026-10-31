"""Exact or approximate: the decision of ADR-0023, as a pure function of a forecast and two rates (ticket #127).

`choose(estimate, r_kernel, r_solve, budget)` reads no clock and no machine: the pilot count
(`Abstraction.estimate`) says how many kernel outcomes a build computes and how many edges `solve` meets, the
rates say what one of each costs, and the budget (about a minute, the owner's tolerance of #81) is the time
the exact run may take. The rule:

* the forecast fits the budget: **exact**;
* it does not: the **ladder** of coarse levels, in order, each kept only if its own forecast fits the budget (a
  level with no forecast is kept: it is built and its size is known only then). The caller tries them in order and
  stops at the first whose certified gap is at most `TOLERANCE`;
* an enabled or offered action that is not block-invariant leaves no level (`refusal`), and so does a ladder that
  fits nowhere: the query is exact, if the exact graph is within `EXACT_TRANSITIONS` (the largest size the solver
  has been run on), otherwise **refused** with "no approximate level available".

`decide` is the CLI's glue around it: it runs the pilot, measures `r_kernel` (in the pilot) and `r_solve` (a short
calibration solve on the first layers of the pilot's own graph) unless the caller injects them, and builds the
candidate levels. Tests inject the rates; no test depends on a machine (ADR-0014).

The ladder is one tuple, `LADDER`: a new kind of level (the tail cut) is a new entry with a builder in `_approx`.
"""

import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from crafting_system.abstraction import Abstraction, Coarsening, CompressedState, Estimate, EstimateRefused
from crafting_system.actions import Action, OutOfScopeError
from crafting_system.solver import Action as SolverAction
from crafting_system.solver import ConvergenceError, Outcome, TabularModel, solve

from ._offers import BuyStartItem, PricedOffer

BUDGET_SECONDS = 60.0  # "about a minute" (#81 Q2)
TOLERANCE = 0.01  # the owner's tolerance: a certified gap of at most 1%
EXACT_TRANSITIONS = 2_000_000  # the largest graph the product `solve` has been run on here (ADR-0023)
SOLVE_RATE_CEILING = 5e-5  # seconds per edge: seven times what R05 measured; a query that fits at this rate is not calibrated
SOLVE_RATE_FALLBACK = 2e-5  # used when the calibration has too little to measure
CALIBRATION_EDGES = 60_000


@dataclass(frozen=True)
class Level:
    """One rung of the ladder: a coarse state with the irrelevant families in groups of `size` (None: all in one)."""

    kind: str
    size: int | None
    name: str


LADDER: tuple[Level, ...] = (
    Level("groups", None, "family groups, all irrelevant families in one group"),
    Level("groups", 8, "family groups of 8"),
    Level("groups", 4, "family groups of 4"),
)


@dataclass(frozen=True)
class Rates:
    """Seconds per kernel outcome and per solved edge; None leaves the one to be measured."""

    kernel: float | None = None
    solve: float | None = None


@dataclass(frozen=True)
class Candidate:
    """A level and its own forecast (None when none could be made); `coarsening` is what `decide` built it with."""

    level: Level
    estimate: Estimate | None
    coarsening: Coarsening | None = None


@dataclass(frozen=True)
class Decision:
    """What to do with a query.

    `action` is "exact", "approximate" (try `levels` in order) or "refused" (`message` says why). `message` is
    a plain-English reason for any of them, empty when the exact run simply fits. `predicted` is the forecast
    seconds of the exact run and `transitions` its predicted size, None when the pilot could not count.
    """

    action: Literal["exact", "approximate", "refused"]
    levels: tuple[Candidate, ...] = ()
    message: str = ""
    predicted: float | None = None
    transitions: int | None = None
    estimate: Estimate | None = None


def minutes(seconds: float) -> str:
    """Seconds as the unit a person reads."""
    if seconds < 90:
        return f"{seconds:.0f} s"
    if seconds < 5400:
        return f"{seconds / 60:.0f} min"
    return f"{seconds / 3600:.1f} h"


def exact_offer(transitions: int | None, predicted: float | None, complete: bool = True) -> str:
    """The sentence that offers the exact run, or says why it is not offered (ADR-0023); `complete` false: the count is a lower bound."""
    if transitions is None:
        return "The exact run has no forecast, so its size is unknown."
    if not complete:
        return (
            f"The exact run is not offered: the count stopped at {transitions:,} transitions and the graph is larger "
            f"(the solver has been run on at most {EXACT_TRANSITIONS:,}). Offer a smaller list of crafts and run again."
        )
    if transitions <= EXACT_TRANSITIONS:
        when = "" if predicted is None else f", predicted at about {minutes(predicted)}"
        return f"The exact answer is available: run again with --exact ({transitions:,} transitions{when})."
    return (
        f"The exact run is not offered: it is predicted at {transitions:,} transitions and the solver has been run on "
        f"at most {EXACT_TRANSITIONS:,} (its memory is not measured beyond). Offer a smaller list of crafts and run again."
    )


def choose(
    estimate: Estimate | None,
    r_kernel: float,
    r_solve: float,
    budget: float,
    *,
    levels: Sequence[Candidate] = (),
    refusal: str | None = None,
) -> Decision:
    """Exact when the forecast fits `budget` seconds, otherwise the levels that fit, otherwise exact or a refusal.

    `refusal` is the reason no coarse level exists (an action that is not block-invariant); `levels` are the
    candidates in ladder order, each with its own forecast. No clock is read: the rates are arguments.
    """
    if estimate is None:
        return Decision("exact", message="the size of the exact graph could not be forecast, so it is built as it is")
    predicted = estimate.seconds(r_kernel, r_solve)
    size = estimate.transitions
    if predicted <= budget and estimate.complete:
        return Decision("exact", predicted=predicted, transitions=size, estimate=estimate)
    fits = tuple(
        found
        for found in levels
        if found.estimate is None or found.estimate.seconds(r_kernel, r_solve) <= budget
    )
    if refusal is None and fits:
        return Decision("approximate", fits, predicted=predicted, transitions=size, estimate=estimate)
    why = refusal or (
        "no coarse level fits the time" if levels else "the irrelevant families are too few to pool, so no coarse level differs from the exact one"
    )
    if size <= EXACT_TRANSITIONS and estimate.complete:  # a cut-short count is only a lower bound: it never shows the exact run to be small
        message = f"no approximate level available ({why}); the exact run is predicted at about {minutes(predicted)} and is run as it is"
        return Decision("exact", message=message, predicted=predicted, transitions=size, estimate=estimate)
    message = f"no approximate level available ({why}). " + exact_offer(size, predicted, estimate.complete)
    return Decision("refused", message=message, predicted=predicted, transitions=size, estimate=estimate)


# --- the glue: pilot, rates, candidates --------------------------------------------------------------------


def coarse_refusal(abstraction: Abstraction, actions: Iterable[Action]) -> str | None:
    """Why no coarse level exists for `actions`: the first of them that does not declare itself block-invariant (None if all do)."""
    try:
        probe = Coarsening(abstraction)
        for action in actions:
            probe.require_invariant(action)
    except OutOfScopeError as refusal:
        return str(refusal)
    return None


def calibrate_solve_rate(
    abstraction: Abstraction,
    start: CompressedState,
    estimate: Estimate,
    costs: dict[Action, float],
    clock: Callable[[], float] = time.perf_counter,
) -> float:
    """Seconds per edge of `solve`, measured on the first layers of the pilot's own graph (a closed prefix, true weights)."""
    layers = estimate.first_layers(CALIBRATION_EDGES)
    table = {
        state: [
            SolverAction(action.label(abstraction.data), costs.get(action, 1.0), tuple(Outcome(s, w) for s, w in outcomes))
            for action, outcomes in offered
        ]
        for state, offered in layers.items()
    }
    edges = sum(len(action.outcomes) for offered in table.values() for action in offered)
    if edges < 100:
        return SOLVE_RATE_FALLBACK
    seen = set(table) | {s for offered in table.values() for action in offered for s, _ in action.outcomes}
    model = TabularModel([state for state in seen if abstraction.is_goal(state)], table)
    began = clock()
    try:
        solve(model, [start])
    except (ConvergenceError, ValueError):
        return SOLVE_RATE_FALLBACK
    return (clock() - began) / edges


def decide(
    abstraction: Abstraction,
    start: CompressedState,
    priced: Iterable[PricedOffer],
    budget: float,
    rates: Rates | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> Decision:
    """Run the pilot on the model of `priced` and `choose`; the exact run when the pilot cannot count it."""
    offered = [p for p in priced if not isinstance(p.offer.action, BuyStartItem)]
    actions = [p.offer.action for p in offered]
    try:
        estimate = abstraction.estimate([start], actions, clock=clock)
    except EstimateRefused:
        return choose(None, 0.0, 0.0, budget)
    rates = rates or Rates()
    r_kernel = estimate.kernel_rate if rates.kernel is None else rates.kernel
    r_solve = rates.solve
    if r_solve is None:
        r_solve = SOLVE_RATE_CEILING
        if estimate.seconds(r_kernel, r_solve) > budget:
            costs = {p.offer.action: p.cost for p in offered}
            r_solve = calibrate_solve_rate(abstraction, start, estimate, costs, clock)
    refusal = coarse_refusal(abstraction, actions)
    candidates = []
    if refusal is None and estimate.seconds(r_kernel, r_solve) > budget:
        tried = set()
        for level in LADDER:
            pooling = Coarsening.pooling_irrelevant(abstraction, level.size, start)
            if pooling.groups and frozenset(pooling.groups) not in tried:  # a finer rung that cuts nothing new is the same level
                tried.add(frozenset(pooling.groups))
                candidates.append(Candidate(level, estimate.coarsened(pooling), pooling))
    return choose(estimate, r_kernel, r_solve, budget, levels=candidates, refusal=refusal)
