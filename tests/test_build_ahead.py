"""#1384: the keys of a bound's build expanded ahead in forked workers (`abstraction._build_ahead`) give the model of one process, bit for bit.

The builds here fork a pool at every pass (`ALWAYS`), so the rule that decides it on the clock is never read: what they compare is what a pool
changes, which must be nothing but which process made a key's row. Compared: the keys and their numbers, the goal flags, the rows, the kernels
and their numbers, the keys expanded, the offers held at some keys, the start value and the value of every key, and the plan through
`plan_target`.
"""

import dataclasses

import numpy as np
import pytest
from test_cli_envelope_build import START_ITEM, abstraction, floors_on, world  # noqa: F401  (fixtures)
from test_planner_blocking_crafts import S, _prices, data, target  # noqa: F401  (the fixtures)

from crafting_system import budget, parallel
from crafting_system.abstraction import _build_ahead
from crafting_system.abstraction._pattern import PatternBuilder
from crafting_system.budget import Budget
from crafting_system.planner import PlanSettings, _envelope_plan, _offers, _pattern_bound, plan_target
from crafting_system.planner._pattern_bound import pattern_lower_bound, pattern_offers

pytestmark = pytest.mark.skipif(not parallel.can_inherit(), reason="no fork here: the build runs in one process (OR-57)")


def _model(model) -> tuple:
    rows = [list(model.actions[k]) for k in range(len(model.keys))]
    narrow = {p: np.asarray(keys).tolist() for p, keys in model.narrow.items()}
    return (model.keys, model.goal, rows, model.kernels, model.index, model.expanded, model.stopped, narrow, model.ruined)


def _counts(stats) -> tuple:
    """What a build counted that does not hang on its memos (the members made and the kernels made do: a member list or a kernel let go
    is made again, in a worker or here)."""
    return (stats.keys, stats.goal_keys, stats.pairs, stats.shared_pairs, stats.refused_pairs, stats.gap_pairs, stats.view_pairs, stats.kept_pairs, dict(stats.modes))


def _same_bound(one, other) -> None:
    assert _model(other.model) == _model(one.model)
    assert _counts(other.model.stats) == _counts(one.model.stats)
    assert other.start_value == one.start_value  # the same bits: the same model solved the same way
    assert np.array_equal(other.value, one.value)
    assert (other.rounds, other.positions, other.stopped, other.phase, other.pieces) == (one.rounds, one.positions, one.stopped, one.phase, one.pieces)


@pytest.fixture
def pooled(monkeypatch):
    monkeypatch.setattr(_build_ahead, "ALWAYS", True)


def _grown(workers: int, **options):
    fresh = abstraction()
    builders = []
    real = PatternBuilder.__init__

    def init(self, *args, **kwargs):
        real(self, *args, **{**kwargs, "workers": workers})
        builders.append(self)

    PatternBuilder.__init__ = init
    try:
        bound = pattern_lower_bound(fresh, fresh.compress(START_ITEM), options.pop("offers"), item=START_ITEM, **options)
    finally:
        PatternBuilder.__init__ = real
    return bound, builders[-1]


@pytest.mark.parametrize("workers", [2, 3, 5])
def test_a_grown_model_built_with_workers_is_the_model_of_one_process_and_its_rows_came_from_them(world, floors_on, pooled, workers):  # noqa: F811
    # The model starts on the Chaos Orb and the restart, and grows as the floor action binds (#988, #1325): passes of new keys and passes of
    # offers added at keys expanded before.
    offers = world[2]
    alone, one = _grown(1, offers=offers)
    ahead, other = _grown(workers, offers=offers)
    _same_bound(alone, ahead)
    assert alone.rounds > 1
    assert one.ahead.pools == 0 and one.ahead.taken == 0
    # a pool a pass (the next forks from this process, whose `computed` holds the pass's kernel keys), and rows taken from them
    assert other.ahead.pools >= alone.rounds and other.ahead.taken > 0 and other.ahead.left == 0
    assert not other.ahead.open  # closed once the bound was built


def test_a_build_counted_in_pieces_stops_where_one_process_stops_with_workers(world, floors_on, pooled):  # noqa: F811
    # A run counted in pieces of work (`Tally`, #1101) asks its net at every offer: the pieces a worker counted are added offer by offer, so the
    # build stops at the same offer of the same key, in each phase
    offers = world[2]
    for pieces in (40, 400, 4_000):
        alone, _ = _grown(1, offers=offers, pieces=pieces)
        ahead, _ = _grown(3, offers=offers, pieces=pieces)
        _same_bound(alone, ahead)


def test_a_model_built_at_once_with_workers_is_the_model_of_one_process(world, pooled):  # noqa: F811
    ab, start, offers = world[:3]
    models = []
    for workers in (1, 4):
        fresh = abstraction()
        builder = PatternBuilder(fresh, fresh.compress(START_ITEM), workers=workers)
        models.append((builder.extend(pattern_offers(offers)), builder))
    assert _model(models[1][0]) == _model(models[0][0])
    assert _counts(models[1][0].stats) == _counts(models[0][0].stats)
    assert models[1][1].ahead.taken > 0 and models[1][1].ahead.left == 0  # every key sent came back with its row


def test_a_pool_that_meets_the_memory_net_is_dropped_and_the_build_goes_on_alone(world, floors_on, pooled, monkeypatch):  # noqa: F811
    def reached(self, futures, stop=None):
        raise parallel.MemoryNetReached("this process and its workers held 9 MB, the limit is 8 MB; the workers were stopped")

    monkeypatch.setattr(parallel.WorkerPool, "gather", reached)
    offers = world[2]
    alone, _ = _grown(1, offers=offers)
    ahead, builder = _grown(3, offers=offers)
    _same_bound(alone, ahead)
    # a pool of three met the net: one of two forked next, met it too: none again
    assert builder.ahead.stopped is not None and builder.ahead.pools == 2 and builder.ahead.count == 1 and builder.ahead.taken == 0


def test_a_row_made_on_a_universe_that_grew_since_the_fork_is_not_taken(world, pooled, monkeypatch):  # noqa: F811
    # A worker's members are those of the universe at the fork: once this process's universe grew, its rows are left and the key is expanded here
    ab, start, offers = world[:3]
    fresh = abstraction()
    builder = PatternBuilder(fresh, fresh.compress(START_ITEM), workers=3)
    real = PatternBuilder._apply
    refused = []

    def apply(self, i, given, made, tick):
        if i % 3 == 0:
            self.pattern.grew += 1  # as a slot found by a kernel made here would count
            try:
                taken = real(self, i, given, made, tick)
            finally:
                self.pattern.grew -= 1
            refused.append(taken)
            return taken
        return real(self, i, given, made, tick)

    monkeypatch.setattr(PatternBuilder, "_apply", apply)
    model = builder.extend(pattern_offers(offers))
    fresh_one = abstraction()
    alone = PatternBuilder(fresh_one, fresh_one.compress(START_ITEM), workers=1).extend(pattern_offers(offers))
    assert refused and not any(refused)
    assert _model(model) == _model(alone)


def _bounds(monkeypatch) -> list:
    made = []
    real = _envelope_plan.pattern_lower_bound

    def bound(*args, **kwargs):
        found = real(*args, **kwargs)
        made.append(found)
        return found

    monkeypatch.setattr(_envelope_plan, "pattern_lower_bound", bound)
    return made


@pytest.mark.parametrize("budget", [None, Budget.in_states(2_000)], ids=["no-net", "counted"])
def test_a_plan_with_workers_is_the_plan_of_one_process_and_its_bounds_models_the_same(data, target, pooled, monkeypatch, budget):  # noqa: F811
    # Through the planner's entry, on the hand-worked belt of the blocking crafts (#886): one worker, then three, the bounds of every round compared
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    taken = []
    real = PatternBuilder._apply
    monkeypatch.setattr(PatternBuilder, "_apply", lambda self, *args: (taken.append(1), real(self, *args))[1])
    results = []
    for workers in ("1", "3"):
        monkeypatch.setenv(parallel.WORKERS_ENV, workers)
        bounds = _bounds(monkeypatch)
        settings = PlanSettings(recipe_starts=False, start_price=S, solver="envelope")
        if budget is not None:
            settings = dataclasses.replace(settings, budget=budget)
        plan = plan_target(data, target, _prices(), settings)
        results.append((plan, list(bounds)))
    (one, one_bounds), (other, other_bounds) = results
    assert other.mean_remaining == one.mean_remaining
    assert other.solution.values == one.solution.values and other.solution.policy == one.solution.policy
    assert len(other_bounds) == len(one_bounds) and one_bounds
    for alone, ahead in zip(one_bounds, other_bounds):
        _same_bound(alone, ahead)
    assert taken  # rows came from the workers


def test_the_rule_forks_no_pool_with_one_worker_or_before_a_key_was_measured(world):  # noqa: F811
    fresh = abstraction()
    builder = PatternBuilder(fresh, fresh.compress(START_ITEM), workers=1)
    assert not builder.ahead._pays(0)
    builder = PatternBuilder(fresh, fresh.compress(START_ITEM), workers=4)
    assert not builder.ahead._pays(0)  # nothing measured yet
    builder.ahead.spent, builder.ahead.keys, builder.ahead.since = 1.0, 10, 1.0  # 0.1 s a key, and keys left: it pays
    builder.extend  # (a built pattern is not needed for the rule)
    builder.keys_to_expand = lambda i: 1_000
    assert builder.ahead._pays(0)
    builder.ahead.since = 1.0
    builder.keys_to_expand = lambda i: 1  # one key of 0.1 s left: 0.075 s saved, four forks cost more
    builder.ahead.fork = 0.05
    assert not builder.ahead._pays(0)


def test_a_growing_builder_forks_a_pool_a_pass_and_closes_it_at_the_pass_end(world, pooled):  # noqa: F811
    offers = pattern_offers(world[2])
    models = []
    for workers in (1, 3):
        fresh = abstraction()
        builder = PatternBuilder(fresh, fresh.compress(START_ITEM), workers=workers, grow=True)
        first = builder.extend(offers[:2])
        pools = builder.ahead.pools
        assert not builder.ahead.open
        second = builder.extend(offers[2:])
        assert builder.ahead.pools > pools or workers == 1
        assert not builder.ahead.open
        models.append((first, second))
    for one, other in zip(*models):
        assert _model(other) == _model(one)


def test_a_net_reached_only_with_the_workers_alive_stops_the_workers_and_not_the_build(world, pooled, monkeypatch):  # noqa: F811
    # The build's net reads the workers' memory too: where it is reached with a pool open, the pool goes (one worker fewer next time) and
    # the net is asked again (R17: a bound one process built whole was stopped at 12,543 MB with six workers beside it, #1384)
    from crafting_system.abstraction import _pattern

    monkeypatch.setattr(_pattern, "POLL_SECONDS", 0.0)  # the net asked at every key and offer, never on the clock's pace
    offers = pattern_offers(world[2])
    built = []

    def stop():
        return "the process held 13,000 MB, the limit is 12,288 MB" if built and built[0].ahead.open else None

    fresh = abstraction()
    alone = PatternBuilder(fresh, fresh.compress(START_ITEM), workers=1).extend(offers)
    fresh = abstraction()
    builder = PatternBuilder(fresh, fresh.compress(START_ITEM), workers=3, stop=stop)
    built.append(builder)
    model = builder.extend(offers)
    assert model.stopped is None and _model(model) == _model(alone)
    assert builder.ahead.pools >= 1 and builder.ahead.count < 3


def test_a_pool_whose_rows_cost_here_what_a_worker_spends_is_idle(world):  # noqa: F811
    # `_idle` (R17's keys of 100,000 kernels, #1384): measured on the rows the workers made and the seconds taking them took here
    fresh = abstraction()
    ahead = PatternBuilder(fresh, fresh.compress(START_ITEM), workers=4).ahead
    ahead._size = lambda: 10  # windows of 10 keys: told over 40 rows, from the second window on
    ahead.gathered = 2
    ahead.worker_keys, ahead.useful = 100, 1.0  # 10 ms a key in a worker
    ahead.replayed, ahead.replay = 50, 0.5  # 10 ms a row here: as slow as one process
    assert ahead._idle()
    ahead.replay = 0.4  # 8 ms a row here: the pool still goes at this process's pace, faster than one process
    assert not ahead._idle()
    ahead.replay = 0.1  # 2 ms a row here
    assert not ahead._idle()
    ahead.replayed, ahead.replay = 30, 0.5  # fewer rows than four windows: not yet told
    assert not ahead._idle()
