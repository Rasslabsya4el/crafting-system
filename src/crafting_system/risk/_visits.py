"""How often a fixed policy does something: the expected total of a weight over its executions (ticket #221).

Every execution of an action is a visit of a state of the chain the policy induces, in the main run and in every run of an
input (a donor) alike, so `sum over states of visits(s) * weight(action at s)` is the expected number of times the policy
does what the weight counts: weight 1 on the recombinations is the expected number of recombinations, the cost of a
recombination as weight is what they cost together. The visits are those of `evaluate`'s chain (`_inputs.expected_visits`)
with the same certificate, so the interval holds whatever the float rounding.
"""

import math
from collections.abc import Callable, Mapping, Sequence

from ..solver import Action
from . import _inputs, _moments
from ._chain import build_chain
from ._mean import ZERO, no_mean
from ._report import Estimate, Expected


def expected_total[S](
    policy: Mapping[S, Action[S]], start: S, is_goal: Callable[[S], bool], weight: Callable[[Action[S]], float]
) -> Expected:
    """The expected `sum of weight(action)` over every execution of `policy` from `start`, runs of inputs included.

    `weight` is not negative (a negative one is `ValueError`). The answer is an `Expected` of `Estimate(value, low, high)`; all infinite,
    with the cause, when the policy has no finite mean (it can get stuck or loops without a way out, `STUCK`; it needs more runs than it
    makes, `SUBCRITICAL`; the arithmetic could not certify it, `UNDECIDED`: M7, #512), zero when `start` is a goal.
    """
    chain = build_chain(policy, start, is_goal)
    if chain.goal[0]:
        return Expected(ZERO)
    if not chain.can_finish[0] or not chain.proper:
        return no_mean(None)
    weights = []
    for action in chain.action:
        found = 0.0 if action is None else float(weight(action))
        if found < 0.0 or math.isnan(found):
            raise ValueError(f"the weight of an action is not negative, got {found!r}")
        weights.append(found)
    try:
        values, error = _inputs.solve_costs(chain, _moments.real_costs(chain))
    except _inputs.NotSubcritical as stopped:
        return no_mean(stopped)
    return Expected(Estimate(*_inputs.weighted_visits(chain, values, error, weights)))


def expected_totals[S](
    policy: Mapping[S, Action[S]], start: S, is_goal: Callable[[S], bool], weights: Sequence[Callable[[Action[S]], float]]
) -> list[Expected]:
    """`expected_total` for several weights from one solve of the visits: one `Expected` per weight, in order."""
    chain = build_chain(policy, start, is_goal)
    if chain.goal[0]:
        return [Expected(ZERO) for _ in weights]
    if not chain.can_finish[0] or not chain.proper:
        return [no_mean(None) for _ in weights]
    arrays = []
    for weight in weights:
        column = []
        for action in chain.action:
            found = 0.0 if action is None else float(weight(action))
            if found < 0.0 or math.isnan(found):
                raise ValueError(f"the weight of an action is not negative, got {found!r}")
            column.append(found)
        arrays.append(column)
    try:
        values, error = _inputs.solve_costs(chain, _moments.real_costs(chain))
    except _inputs.NotSubcritical as stopped:
        return [no_mean(stopped) for _ in weights]
    return [Expected(Estimate(*each)) for each in _inputs.weighted_visits_many(chain, values, error, arrays)]
