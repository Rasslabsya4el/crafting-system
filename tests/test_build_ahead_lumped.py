"""#1384: the keys of a bound's build expanded ahead in forked workers, where the twin makes the erasing kernels (#1146) and where the
kernels find slots the universe lacked (#1086): the model of one process, bit for bit, and the plan through the planner's entry.

A kernel the twin made in a worker is made again here from its outcomes, unnoted, as `_offers_of_key` makes it; a key whose kernels grew a
worker's universe is left to this process, which grows its own there, and the pool forked before it is closed."""

from collections import Counter

import numpy as np
import pytest
from test_abstraction_pattern import BOW, STARTS, build, world  # noqa: F401 (world: the fixture)
from test_cli_envelope_plan import coarse  # noqa: F401 (the fixture: the coarse world, a Chaos Orb and bench crafts)
from test_pattern_lumped import broad_offers
from coarse_support import DATA as COARSE

from crafting_system import parallel
from crafting_system.abstraction import _build_ahead, _pattern
from crafting_system.abstraction._pattern import PatternBuilder
from crafting_system.budget import Budget
from crafting_system.planner import PlanSettings, plan_target
from crafting_system.planner._pattern_bound import pack_pattern_model
from crafting_system.solver import solve_packed

pytestmark = pytest.mark.skipif(not parallel.can_inherit(), reason="no fork here: the build runs in one process (OR-57)")


def _model(model) -> tuple:
    rows = [list(model.actions[k]) for k in range(len(model.keys))]
    return (model.keys, model.goal, rows, model.kernels, model.index, model.expanded, model.stopped, model.ruined, model.stats.universe_growth)


@pytest.fixture
def pooled(monkeypatch):
    monkeypatch.setattr(_build_ahead, "ALWAYS", True)
    assert _pattern.LUMP_ERASING


def _build(data, ab, start, workers: int):
    builder = PatternBuilder(ab, ab.compress(build(data, BOW, STARTS[start])), tags=True, workers=workers)
    return builder.extend(broad_offers()), builder


@pytest.mark.parametrize("start", [0, 4], ids=["plain", "lock"])
def test_with_the_twin_a_model_built_with_workers_is_the_model_of_one_process(world, pooled, start, monkeypatch):  # noqa: F811
    data, ab, _ = world
    lumped = []
    real = _pattern.PatternBuilder._replay

    def replay(self, event):
        if event[1] == _pattern.MADE and event[5]:
            lumped.append(1)
        return real(self, event)

    monkeypatch.setattr(_pattern.PatternBuilder, "_replay", replay)
    alone, _ = _build(data, ab, start, 1)
    ahead, builder = _build(data, ab, start, 3)
    assert _model(ahead) == _model(alone)
    assert builder.ahead.taken > 0
    assert lumped, "no kernel of the twin came from a worker"
    offers = broad_offers()
    assert np.array_equal(solve_packed(pack_pattern_model(ahead, offers)).value, solve_packed(pack_pattern_model(alone, offers)).value)


def test_a_universe_that_grows_inside_a_pass_leaves_the_key_here_and_the_model_is_the_model_of_one_process(world, pooled, monkeypatch):  # noqa: F811
    # Every slot a kernel produces counts as growth the first time a process meets it: a worker that meets one leaves the key, this process
    # grows its universe there, the pool goes, and the pass begins again with a pool forked from the grown universe
    data, ab, _ = world
    real = _pattern._Universe.note
    met: Counter = Counter()

    def note(self, slot):
        grew = real(self, slot)
        met[slot] += 1
        return grew or met[slot] == 1

    monkeypatch.setattr(_pattern._Universe, "note", note)
    alone, one = _build(data, ab, 0, 1)
    met.clear()
    ahead, builder = _build(data, ab, 0, 3)
    assert alone.stats.universe_growth > 0
    assert _model(ahead) == _model(alone)
    assert builder.ahead.pools > 1 and builder.ahead.taken > 0  # pools closed by the growth, and forked again


def test_through_the_planners_entry_counted_in_states_with_the_twin_the_plan_with_workers_is_the_plan_of_one_process(coarse, pooled, monkeypatch):  # noqa: F811
    target, prices, _ = coarse
    taken = []
    real = PatternBuilder._apply
    monkeypatch.setattr(PatternBuilder, "_apply", lambda self, *args: (taken.append(1), real(self, *args))[1])
    plans = []
    for workers in ("1", "3"):
        monkeypatch.setenv(parallel.WORKERS_ENV, workers)
        plans.append(plan_target(COARSE, target, prices, PlanSettings(recipe_starts=False, start_price=5.0, solver="envelope", budget=Budget.in_states(10**5))))
    one, other = plans
    assert other.mean_remaining == one.mean_remaining
    assert other.solution.values == one.solution.values and other.solution.policy == one.solution.policy
    assert other.packed.info["envelope"].lower == one.packed.info["envelope"].lower
    assert taken  # rows came from the workers


def test_the_twins_distributions_are_primed_in_a_pool_and_the_model_is_the_same(world, monkeypatch):  # noqa: F811
    # The kernels the twin makes (an erasing draw, #1146) had no pool: R04's 1,245 fossil sets joining at one key were six minutes of the twin's
    # walks in one process. They are primed in the twin now, which changes nothing but where they are made (`_prime`, #250)
    from crafting_system.abstraction import _prime

    data, ab, _ = world
    alone, _ = _build(data, ab, 0, 1)
    primed = []
    real = _prime.prime

    def counting(abstraction, requests, **kwargs):
        made = real(abstraction, requests, **kwargs)
        primed.append((abstraction is not ab, made))
        return made

    monkeypatch.setattr(_prime, "prime", counting)
    monkeypatch.setattr(_prime, "WORTH", 0)
    monkeypatch.setattr(_pattern, "PRIME_FROM", 2)
    monkeypatch.setenv(parallel.WORKERS_ENV, "3")
    ahead, _ = _build(data, ab, 0, 1)
    assert _model(ahead) == _model(alone)
    assert any(twin and made for twin, made in primed), "no distribution of the twin was primed"
