"""The guard of the envelope search on R13's real bound (ticket #539, OR-12, OR-13): a planted bound is a `BoundError` whichever way it would have failed.

R13's walk-free bound (#497) is raised 20 or 50 times at every third or fifth key, so it is above the exact value there and not a lower bound. Before the ticket
three of these four ended in a `ConvergenceError` ("the policy is improper: its linear system is singular", or "certifies only a relative bound") after up to
60 rounds, because the only guard was a check at the end of the run; the fourth was the fall guard. Now each is refused as it is seen, in seconds. The sound
bound is not refused and gives the exact mean. The random-graph version of the guard is `tests/test_cli_envelope_guard.py`.

Needs the cached dump; skips cleanly without it (CI fetches it, ticket #165).
"""

import dataclasses
import sys
from pathlib import Path

import numpy as np
import pytest
from abstraction_support import real_game_data

from crafting_system.cli import _plan, make_plan
from crafting_system.cli._envelope_plan import BoundError, envelope_result
from crafting_system.cli._pattern_bound import pattern_lower_bound
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json"
TARGET_R13 = ROOT / "examples" / "targets" / "r13-life-resist-belt.yaml"
TOLERANCE = 1e-9


@pytest.fixture(scope="module")
def r13():
    """R13's abstraction, start, priced offers, sound bound and exact mean (the full walk's)."""
    data = real_game_data()
    if str(ROOT / "research" / "312") not in sys.path:
        sys.path.append(str(ROOT / "research" / "312"))
    import exact_classes as E

    _, _, _, abstraction, start, priced, _ = E.build_model(TARGET_R13, "twins", True, False)
    bound = pattern_lower_bound(abstraction, start, priced)
    with pytest.MonkeyPatch.context() as patch:  # the research model starts from the item with no mods, so the exact mean is the plan's without the draw of a bought item's mods (ADR-0064)
        patch.setattr(_plan, "unopened_listing", lambda data, start: None)
        exact = make_plan(data, load_target(TARGET_R13, data), load_price_file(PRICES), solver="packed", with_risk=False).mean_remaining
    return abstraction, start, priced, bound, exact


def planted(bound, every: int, factor: float):
    """The bound with every `every`-th key (from the second) raised `factor` times."""
    raised = np.where(np.arange(len(bound.value)) % every == 1, factor, 1.0)
    return dataclasses.replace(bound, value=bound.value * raised)


@pytest.mark.parametrize(("every", "factor"), [(3, 20.0), (3, 50.0), (5, 20.0), (5, 50.0)])
def test_every_planted_bound_is_refused_as_a_bound_error_whichever_way_it_would_have_failed(r13, every, factor):
    abstraction, start, priced, bound, _ = r13
    with pytest.raises(BoundError, match="lower bound"):
        envelope_result(abstraction, start, priced, bound=planted(bound, every, factor))


def test_the_sound_bound_is_still_exact_with_the_guard_on(r13):
    abstraction, start, priced, bound, exact = r13
    result = envelope_result(abstraction, start, priced, bound=bound)
    assert result.solution.values[start] == pytest.approx(exact, rel=TOLERANCE) and result.info["envelope"].exact
