"""#1467: the risk of a plan of 10^11 steps keeps the certified error of its mean, it does not refuse the plan.

On R17 (tmeas7, a808862e) the planner certified its plan of 23,030,110,242.55 c to 2.33e-05, inside the run's allowance of 0.001, and then the
risk evaluation solved the same merged chain again with the solver's default refusal of 1e-06 and raised `ConvergenceError`: the run ended with
no plan after an hour. The risk's moment solves take every figure with its error (`_moments.interval`), so no bound needs refusing there.

The toy: a ring of `N` states at 0.07 c a step whose one exit, at state 0, has the chance `1 / (W + 1)`. From state 0 the expected steps are
`E = 1 + (1 - q)(N - 1 + E)`, so `E = (W + 1) + W (N - 1)` with `q = 1 / (W + 1)`: about 3e11 steps at N = 300, W = 10^9, past what float64
certifies to 1e-6 against a step of 0.07 c.
"""

import pytest

from crafting_system.risk import evaluate
from crafting_system.solver import Action, Outcome, TabularModel, solve_packed_model
from crafting_system.solver._certify import ACCEPT_BOUND, ConvergenceError

N, W, STEP = 300, 10**9, 0.07
GOAL = "goal"


def ring() -> dict:
    policy = {s: Action("step", STEP, (Outcome((s + 1) % N, 1),)) for s in range(1, N)}
    policy[0] = Action("try", STEP, (Outcome(1, W), Outcome(GOAL, 1)))
    return policy


EXACT = STEP * ((W + 1) + W * (N - 1))


def test_the_solver_alone_cannot_certify_the_ring_to_its_default():
    """The premise: the packed solve refuses this chain at its default acceptance, and gives it with its error when asked to."""
    model = TabularModel([GOAL], {s: [a] for s, a in ring().items()})
    with pytest.raises(ConvergenceError) as refused:
        solve_packed_model(model, [0])
    assert refused.value.error_bound > ACCEPT_BOUND
    solution = solve_packed_model(model, [0], refuse_above=float("inf"))
    assert ACCEPT_BOUND < solution.error_bound < 1e-2
    value = solution.values[0]
    assert value * (1 - solution.error_bound) <= EXACT <= value * (1 + solution.error_bound)


def test_the_risk_of_a_long_chain_keeps_its_mean_with_the_certified_error():
    report = evaluate(ring(), 0, lambda s: s == GOAL, packed_moments=True, resolve_quantiles=False)
    mean = report.mean
    assert mean.low <= EXACT <= mean.high
    assert mean.low < mean.value < mean.high
    assert (mean.high - mean.low) / mean.value < 1e-2  # the interval is the certified one, not [0, inf]
    assert report.success_probability.value == 1.0


def test_the_plan_says_how_far_the_risk_mean_is_worked_out_not_that_it_is_exact():
    """The planner's packed risk (`_plan.packed_risk`) with the toy's chain: no limit calls the figures exact, one says the mean's error (OR-13)."""
    from types import SimpleNamespace

    from crafting_system.planner import _limits
    from crafting_system.planner._plan import packed_risk

    packed = SimpleNamespace(risk_policy=ring(), risk_start=0, risk_is_goal=lambda s: s == GOAL)
    risk, limits = packed_risk(packed, EXACT, None)
    assert risk.mean.low <= EXACT <= risk.mean.high
    guarantees = [limit.guarantee for limit in limits]
    assert not any(sentence in guarantees for sentence in _limits.EXACT_MEAN_SENTENCES)
    assert any("worked out only to within" in text for text in guarantees)
