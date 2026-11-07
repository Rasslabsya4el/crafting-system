"""The envelope search on real routes (ticket #377, ADR-0063 point 4, OR-12): the full walk's plan and mean, from a smaller expansion.

R05 and R13 are planned twice on the real 3.29.3.3 dump at the committed prices: `solver="packed"` (the full walk, every state) and `solver="envelope"`
(the walk-free bound of #497 and the search of `cli/_envelope.py`). The two give the same mean to 1e-9, the same action at every state the envelope's plan
reaches, and the envelope's plan reaches no state it has not expanded. R13's bound is its exact cost (100%), so the search expands 191 of 2,887 states.
R04 and R14 are compared in heavy runs (`.github/scripts/envelope_routes.py`; the numbers are in the pull request).

The control: R13's bound is raised above the exact cost at some keys and the same comparison fails, so a wrong cut cannot pass.

Needs the cached dump; skips cleanly without it (CI fetches it, ticket #165). Nothing here asserts a time (ADR-0014).
"""

import dataclasses
import sys
from pathlib import Path

import numpy as np
import pytest
from abstraction_support import real_game_data

from crafting_system.cli import make_plan
from crafting_system.cli._envelope_plan import BoundError, envelope_result
from crafting_system.cli._pattern_bound import pattern_lower_bound
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
ROUTES = {"R05": "r05-strength-ring", "R13": "r13-life-resist-belt"}
TARGET_R13 = ROOT / "examples" / "targets" / "r13-life-resist-belt.yaml"
TOLERANCE = 1e-9


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module", params=list(ROUTES))
def both(request, data):
    """(route id, full walk, envelope plan) of one route."""
    target = load_target(ROOT / "examples" / "targets" / f"{ROUTES[request.param]}.yaml", data)
    prices = load_price_file(PRICES)
    return (
        request.param,
        make_plan(data, target, prices, solver="packed", with_risk=False),
        make_plan(data, target, prices, solver="envelope", with_risk=False),
    )


def test_the_envelope_plan_has_the_full_walks_mean(both):
    _, full, envelope = both
    assert envelope.mean_remaining == pytest.approx(full.mean_remaining, rel=TOLERANCE)
    assert envelope.start == full.start


def test_the_envelope_plan_takes_the_full_walks_action_at_every_state_it_reaches(both):
    _, full, envelope = both
    assert len(envelope.policy) > 1
    for state, action in envelope.policy.items():
        assert state in full.policy, "the envelope plan reaches a state the full plan does not"
        assert action.label == full.policy[state].label
        assert envelope.solution.values[state] == pytest.approx(full.solution.values[state], rel=TOLERANCE)


def test_the_envelope_expands_fewer_states_than_the_walk_and_says_which_cut_ran(both):
    route, full, envelope = both
    info = envelope.packed.info["envelope"]
    assert info.exact and info.stopped is None and info.keys_missing == 0
    assert info.lower <= full.mean_remaining * (1 + 1e-9)
    assert info.lower == pytest.approx(full.mean_remaining, rel=1e-6)  # LB = UB: the mean is pinned
    assert info.expanded < len(full.solution.values)
    if route == "R13":  # its bound is its exact cost: the search looks at the policy and little else
        assert info.expanded <= len(full.solution.values) // 10
    assert any(limit.what.startswith("The search expanded only what could matter") for limit in envelope.limits)


@pytest.fixture(scope="module")
def r13_model(data):
    """R13's abstraction, start, priced offers, sound bound and exact mean, as the planted-bound tests need them."""
    if str(ROOT / "research" / "312") not in sys.path:
        sys.path.append(str(ROOT / "research" / "312"))
    import exact_classes as E

    _, _, _, abstraction, start, priced, _ = E.build_model(TARGET_R13, "twins", True, False)
    bound = pattern_lower_bound(abstraction, start, priced)
    exact = make_plan(data, load_target(TARGET_R13, data), load_price_file(PRICES), solver="packed", with_risk=False).mean_remaining
    return abstraction, start, priced, bound, exact


def planted(bound, every: int, factor: float):
    """The bound with every `every`-th key (from the second) raised `factor` times: above the exact value there, so not a lower bound."""
    raised = np.where(np.arange(len(bound.value)) % every == 1, factor, 1.0)
    return dataclasses.replace(bound, value=bound.value * raised)


def test_a_bound_raised_above_the_exact_cost_at_some_keys_is_caught(r13_model):
    """The control on a real route: the comparison that every run above passes fails for a wrong bound (one key in four raised tenfold)."""
    abstraction, start, priced, bound, exact = r13_model
    sound = envelope_result(abstraction, start, priced, bound=bound)
    assert sound.solution.values[start] == pytest.approx(exact, rel=TOLERANCE)
    wrong = planted(bound, 4, 10.0)
    with pytest.raises(BoundError, match="lower bound"):  # the guard sees this bound is not consistent as the search looks further ...
        envelope_result(abstraction, start, priced, bound=wrong)
    wrong_answer = envelope_result(abstraction, start, priced, bound=wrong, guard=False)  # ... and with the guard off the comparison with the full walk is what catches it
    assert abs(wrong_answer.solution.values[start] - exact) > 1e-3 * exact, "the planted bound did not change the answer: the comparison cannot fail"
    assert wrong_answer.info["envelope"].lower > exact  # and the bound it reports is above the exact cost, which no sound bound is


@pytest.mark.parametrize(("every", "factor"), [(3, 20.0), (3, 50.0), (5, 20.0), (5, 50.0)])
def test_every_planted_bound_is_refused_as_a_bound_error_whichever_way_it_would_have_failed(r13_model, every, factor):
    """Ticket #539: with the guard at the end of the run, these four ended in a ConvergenceError ("the policy is improper: its linear system is singular", or
    "certifies only a relative bound") after 60 rounds, or in the fall guard; the search now refuses each one at the state or the round that shows the fault."""
    abstraction, start, priced, bound, _ = r13_model
    with pytest.raises(BoundError, match="lower bound"):
        envelope_result(abstraction, start, priced, bound=planted(bound, every, factor))


def test_the_sound_bound_is_still_exact_with_the_guard_on(r13_model):
    abstraction, start, priced, bound, exact = r13_model
    result = envelope_result(abstraction, start, priced, bound=bound)
    assert result.solution.values[start] == pytest.approx(exact, rel=TOLERANCE) and result.info["envelope"].exact
