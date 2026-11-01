"""How often a fixed policy does something: the expected total of a weight over its executions (ticket #221).

Every execution of an action is a visit of a state of the chain the policy induces, in the main run and in every run of an
input (a donor) alike, so `sum over states of visits(s) * weight(action at s)` is the expected number of times the policy
does what the weight counts: weight 1 on the recombinations is the expected number of recombinations, the cost of a
recombination as weight is what they cost together. The visits are those of `evaluate`'s chain (`_inputs.expected_visits`)
with the same certificate, so the interval holds whatever the float rounding.
"""

import math
from collections.abc import Callable, Mapping

from ..solver import Action
from . import _inputs, _moments
from ._chain import build_chain
from ._mean import INFINITE, ZERO
from ._report import Estimate


def expected_total[S](
    policy: Mapping[S, Action[S]], start: S, is_goal: Callable[[S], bool], weight: Callable[[Action[S]], float]
) -> Estimate:
    """The expected `sum of weight(action)` over every execution of `policy` from `start`, runs of inputs included.

    `weight` is not negative (a negative one is `ValueError`). The answer is `Estimate(value, low, high)`; all infinite when the
    policy has no finite mean (it can get stuck, loops without a way out, or needs more runs than it makes), zero when `start`
    is a goal.
    """
    chain = build_chain(policy, start, is_goal)
    if chain.goal[0]:
        return ZERO
    if not chain.can_finish[0] or not chain.proper:
        return INFINITE
    weights = []
    for action in chain.action:
        found = 0.0 if action is None else float(weight(action))
        if found < 0.0 or math.isnan(found):
            raise ValueError(f"the weight of an action is not negative, got {found!r}")
        weights.append(found)
    try:
        values, error = _inputs.solve_costs(chain, _moments.real_costs(chain))
    except _inputs.NotSubcritical:
        return INFINITE
    return Estimate(*_inputs.weighted_visits(chain, values, error, weights))
