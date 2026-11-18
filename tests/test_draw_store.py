"""The exact draws a plan keeps so that none of its rounds makes one twice (`actions.draw.DrawStore`, `sharing`; ticket #1194).

Every round of a plan has a model of its own, whose caches start empty, so each round made again the draws of the round before it (R20:
about 6 s for each large one, in every round). Inside `sharing` the engine keeps each walk under what the walk reads, which is the pool
seen through the label as a partition, not the label's names. Everything here is counted (walks made, walks answered from the store,
pieces a counted search counts), never timed:

* a second build of the bound, for a model of more offers, makes no walk the first build made, and its bound is the one a build with no
  store gives; through the planner's entry, no round of a plan makes a walk an earlier round made, and the plan and its rounds' states are
  those of a plan with no store, counted in states or not;
* a call with other names for the same partition gets the kept walk renamed, equal to its own walk in chances and order; a label that
  tells the mods apart more finely is walked;
* a guaranteed tag, blocked tags, kept mods, views and floats are part of the key and of the result;
* under a search counted in states a kept walk counts what its making counted, and a walk that would be cut is cut as before;
* the store holds at most its limit of outcomes, the least recently used leaving first, and empties itself at its share of the run's
  memory net;
* `prime` sends no kept walk to a pool worker, and takes back the walks its workers made.
"""

import random
from contextlib import contextmanager
from fractions import Fraction

import pytest
from coarse_support import CHAOS, DATA, abstraction
from proto_draw_support import family
from test_draw_forward import LABELS, RARE, SMALL, real_pools, reweighed, tagged  # noqa: F401  (`real_pools` is a fixture)
from test_packed_walk_light import START_ITEM, make_offers
from test_planner_blocking_crafts import _prices, data, every_shared_kernel_checked  # noqa: F401  (fixtures)
from test_prime_light import POOLS, PoolSpy, one_per_pool
from test_stop_is_not_unreachable import _settings, _target

from crafting_system import budget, parallel
from crafting_system.abstraction import _prime
from crafting_system.actions import draw
from crafting_system.actions.draw import DrawStore, exact_distribution, exact_distributions, floating, guaranteed_candidates, shared_draws, sharing
from crafting_system.items import Side
from crafting_system.planner import _offers, _rounds, plan_target
from crafting_system.planner import _plan as planner_plan
from crafting_system.planner._pattern_bound import pattern_lower_bound

PREFIX, SUFFIX = Side.PREFIX, Side.SUFFIX
FREE = {PREFIX: 3, SUFFIX: 3}


def enabled(offers):
    """The actions a plan of `offers` builds its model with (`planner._plan._make_plan`): those that read the junk or the item's state."""
    return [p.offer.action for p in offers if (reads := p.offer.action.reads(DATA)).junk or reads.item_state]


def build(offers):
    """The bound of a model of `offers` alone, as a round of those offers builds it: a new abstraction, then its bound."""
    ab = abstraction(actions=enabled(offers))
    return pattern_lower_bound(ab, ab.compress(START_ITEM), offers)


# ---- the builds of two rounds -------------------------------------------------------------------------------------------------------------


def test_a_second_build_over_more_offers_makes_no_draw_the_first_made():
    # the world of `test_cli_envelope_light.py`: a Chaos Orb, four bench crafts, Remove Crafted Mods and the restart. The first round holds
    # the Chaos Orb, one craft and the restart; the second adds a second craft, the third every offer. Each round is a new model.
    offers = make_offers()
    rounds = [[offers[i] for i in chosen] for chosen in ((0, 1, 6), (0, 1, 2, 6), range(7))]
    alone = [build(chosen) for chosen in rounds]  # no store: every build makes its own draws
    with sharing() as store:
        store.keys = []
        made = []
        together = []
        for chosen in rounds:
            walks, hits = store.walks, store.hits
            together.append(build(chosen))
            made.append((store.walks - walks, store.hits - hits))
    # the first build walks its one pool (the Chaos Orb's: every state of the world redraws the whole item); the later ones walk nothing
    assert made == [(1, 0), (0, 1), (0, 1)]
    assert len(set(store.keys)) == len(store.keys) == 1  # no walk was made twice
    for with_store, without in zip(together, alone, strict=True):
        assert with_store.complete and without.complete
        assert list(with_store.value) == list(without.value) and with_store.model.keys == without.model.keys
        assert with_store.model.stats.kernels == without.model.stats.kernels  # the model asked for as many distributions: the store answered them


def test_outside_a_plan_nothing_is_kept():
    assert shared_draws() is None
    pool, label = SMALL["several-labels-in-a-family"]
    first = exact_distribution(tuple(pool), FREE, None, RARE, 0, label)
    assert shared_draws() is None and first == exact_distribution(tuple(pool), FREE, None, RARE, 0, label)
    with sharing(10) as outer, sharing(99) as inner:  # a plan inside a plan (a start option, a second item) shares the outer store
        assert inner is outer is shared_draws() and outer.limit == 10
    assert shared_draws() is None


# ---- a plan in rounds, through the planner's entry ------------------------------------------------------------------------------------------


def _rounds_by_hand(monkeypatch):
    """The belt of `test_planner_blocking_crafts` searched in rounds of three groups set by hand: the Exalted Orb, then one bench craft more, then the
    other bench crafts. Each round is a `_make_plan` of its own, with a model of its own. Returns the stores the plans opened, and the
    switch that plans with no store."""

    def groups(data, goal, target, grouped, route):
        crafts = tuple(i for i, offer in enumerate(grouped) if offer.kind == "bench-craft")
        exalts = tuple(i for i, offer in enumerate(grouped) if offer.kind == "exalted-orb")
        assert len(crafts) >= 2 and exalts
        return (
            _rounds.Group(exalts, ("exalted-orb",), frozenset()),
            _rounds.Group(crafts[:1], ("bench-craft",), frozenset()),
            _rounds.Group(crafts[1:], ("bench-craft",), frozenset()),
        )

    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    monkeypatch.setattr(planner_plan, "offer_groups", groups)
    opened = []

    @contextmanager
    def recorded():
        with sharing() as store:
            if store.keys is None:
                store.keys = []
                opened.append(store)
            yield store

    @contextmanager
    def no_store():
        yield None

    monkeypatch.setattr(planner_plan, "sharing", recorded)
    return opened, lambda: monkeypatch.setattr(planner_plan, "sharing", no_store)


def _read(plan):
    """What a plan says that a test may compare: its cost, and how each of its rounds ended and with how many states."""
    return plan.mean_remaining, [(record.status, record.states, record.reason) for record in plan.search.widening]


@pytest.mark.parametrize("states", [None, 400])
def test_through_the_entry_no_round_of_a_plan_makes_a_draw_an_earlier_round_made(tmp_path, data, monkeypatch, states):  # noqa: F811
    opened, without = _rounds_by_hand(monkeypatch)
    target = _target(tmp_path, data)
    plan = plan_target(data, target, _prices(), _settings(states))
    (store,) = opened  # one store for the plan and all its rounds
    assert len(plan.search.widening) >= 3 and all(record.status == _rounds.CLOSED for record in plan.search.widening)
    assert len(set(store.keys)) == len(store.keys) == store.walks  # no walk was made twice in the plan
    assert store.hits > store.walks  # the rounds after the first asked more draws from the store than the plan made in all
    assert shared_draws() is None  # the plan closed its store
    without()
    alone = plan_target(data, target, _prices(), _settings(states))
    assert _read(plan) == _read(alone)  # the same plan and the same rounds, counted in states or not: the store changes no figure
    assert plan.mean_remaining == pytest.approx(133.0)  # 3 (c + e) + 2 S, the belt's plan (`test_stop_is_not_unreachable`)


# ---- the key is the partition, not the names ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", SMALL)
def test_other_names_for_the_same_partition_get_the_kept_walk_renamed(name):
    pool, label = SMALL[name]
    pool = tuple(pool)
    other = lambda mod: ("kind", label(mod))  # noqa: E731  (the same partition, every label renamed)
    fresh, fresh_other = exact_distribution(pool, FREE, None, RARE, 0, label), exact_distribution(pool, FREE, None, RARE, 0, other)
    with sharing() as store:
        assert list(exact_distribution(pool, FREE, None, RARE, 0, label).items()) == list(fresh.items())
        renamed = exact_distribution(pool, FREE, None, RARE, 0, other)
        again = exact_distribution(pool, FREE, None, RARE, 0, label)
        assert (store.walks, store.hits, store.renamed) == (1, 2, 2)  # renamed for the second call, and back for the third
    assert list(renamed.items()) == list(fresh_other.items())  # the same outcomes, the same chances, in the same order
    assert list(again.items()) == list(fresh.items())
    assert all(type(chance) is Fraction for chance in renamed.values()) and sum(renamed.values()) == 1


def test_a_label_that_tells_more_apart_is_walked():
    pool = tuple(SMALL["several-labels-in-a-family"][0])
    by_family, by_id = (lambda mod: mod.families[0]), (lambda mod: mod.id)
    with sharing() as store:
        coarse = exact_distribution(pool, FREE, None, RARE, 0, by_family)
        fine = exact_distribution(pool, FREE, None, RARE, 0, by_id)
        assert (store.walks, store.hits, len(store)) == (2, 0, 2)
    assert coarse == exact_distribution(pool, FREE, None, RARE, 0, by_family) and fine == exact_distribution(pool, FREE, None, RARE, 0, by_id)
    assert len(fine) > len(coarse)


def test_a_result_handed_out_is_the_callers_own():
    pool, label = SMALL["families-of-one-class"]
    with sharing():
        first = exact_distribution(tuple(pool), FREE, None, RARE, 0, label)
        expected = dict(first)
        first.clear()  # a caller that empties what it was given changes nothing for the next
        assert exact_distribution(tuple(pool), FREE, None, RARE, 0, label) == expected


def test_what_the_walk_reads_is_in_the_key():
    # each call differs from the first in one thing the walk reads: none may be answered by another's walk
    pool = (
        tagged(family("A", PREFIX, ("A1", 100), ("A2", 300)), 1, "fire"),
        tagged(family("B", PREFIX, ("B1", 100), ("B2", 300)), 0, "fire", "attack"),
        tagged(family("C", SUFFIX, ("C1", 200)), 0, "fire"),
        family("D", SUFFIX, 400),
        family("E", PREFIX, 250),
    )
    by_id = lambda mod: mod.id  # noqa: E731
    calls = [
        (pool, FREE, None, RARE, 0, by_id, frozenset()),
        (pool, {PREFIX: 2, SUFFIX: 3}, None, RARE, 0, by_id, frozenset()),  # the free slots
        (pool, FREE, None, RARE, 1, by_id, frozenset()),  # the mods kept
        (pool, FREE, None, {3: Fraction(1)}, 0, by_id, frozenset()),  # the totals
        (pool, FREE, None, {3: Fraction(1, 2), 4: Fraction(1, 2)}, 0, by_id, frozenset()),  # their chances
        (pool, FREE, "fire", RARE, 0, by_id, frozenset()),  # a guaranteed tag
        (pool, FREE, "fire", RARE, 0, by_id, frozenset({"attack"})),  # the tags it may not pick
        (pool[:4], FREE, None, RARE, 0, by_id, frozenset()),  # the pool
        (pool[:3] + (family("D", SUFFIX, 500), pool[4]), FREE, None, RARE, 0, by_id, frozenset()),  # a weight
    ]
    fresh = [exact_distribution(*call) for call in calls]
    with sharing() as store:
        first = [exact_distribution(*call) for call in calls]
        second = [exact_distribution(*call) for call in calls]
        assert (store.walks, store.hits) == (len(calls), len(calls))
    for one, two, alone in zip(first, second, fresh, strict=True):
        assert list(one.items()) == list(two.items()) == list(alone.items())


@pytest.mark.parametrize("seed", range(8))
def test_the_views_of_a_kept_walk_are_those_of_its_own_walk(real_pools, seed):  # noqa: F811
    """The draws of `test_draw_forward`'s view test (a Fractured Fossil's walk: several coarser labels read out of one walk, one of them
    needing a mod): a kept walk gives every view as its own walk does, also under other names for the labels."""
    rng = random.Random(1194 * 1000 + seed)
    pool = rng.choice(real_pools)
    picked = reweighed(rng.sample(pool, min(len(pool), rng.randint(5, 10))), rng, rng.random() < 0.6)
    wanted = {fam.family for fam in rng.sample(picked, min(3, len(picked)))}
    one = sorted(wanted)[0]
    free = {PREFIX: rng.randint(0, 3), SUFFIX: rng.randint(1, 3)}
    tags = sorted({tag for fam in picked for entry in fam.mods for tag in entry.mod.implicit_tags})
    tag = rng.choice(tags) if tags and rng.random() < 0.5 else None
    if tag is not None and not guaranteed_candidates(picked, free, tag):
        tag = None
    fine = LABELS["by-mod"](wanted)
    ids = {entry.mod.id for fam in picked if fam.family == one for entry in fam.mods}

    def views(mark):
        coarse, single = LABELS["coarse"](wanted), LABELS["coarse"]({one})
        return [(lambda mod: (mark, coarse(mod)), None), (lambda mod: (mark, single(mod)), None), (lambda mod: mark, None), (lambda mod: (mark, single(mod)), lambda value: value in ids)]

    fresh = {mark: exact_distributions(picked, free, tag, RARE, 1, fine, views(mark)) for mark in ("a", "b")}
    with sharing() as store:
        kept = {mark: exact_distributions(picked, free, tag, RARE, 1, fine, views(mark)) for mark in ("a", "b", "a")}
        assert (store.walks, store.hits) == (1, 2)
    for mark in ("a", "b"):
        assert [list(shown.items()) for shown in kept[mark]] == [list(shown.items()) for shown in fresh[mark]]


def test_a_float_walk_and_an_exact_one_are_kept_apart(real_pools):  # noqa: F811
    rng = random.Random(11940)
    picked = reweighed(rng.sample(real_pools[0], 9), rng, True)
    label = LABELS["by-tier"]({picked[0].family, picked[1].family})
    exact = exact_distribution(picked, FREE, None, RARE, 0, label)
    with floating():
        rough = exact_distribution(picked, FREE, None, RARE, 0, label)
    with sharing() as store:
        assert exact_distribution(picked, FREE, None, RARE, 0, label) == exact
        with floating():
            first = exact_distribution(picked, FREE, None, RARE, 0, label)
            second = exact_distribution(picked, FREE, None, RARE, 0, label)
        assert exact_distribution(picked, FREE, None, RARE, 0, label) == exact
        assert (store.walks, store.hits) == (2, 2)
    assert list(first.items()) == list(second.items()) == list(rough.items())  # the same floats, to the last bit
    assert all(type(chance) is float for chance in first.values()) and all(type(chance) is Fraction for chance in exact.values())


# ---- a search counted in states ------------------------------------------------------------------------------------------------------------


def counted(given, call):
    """`call()` under a count of `given`: what it returned (or the cut it met) and what each stage counted, in the order the stages were met."""
    with budget.counting(given) as allowance:
        try:
            result = call()
        except budget.OutcomesCut as cut:
            result = (str(cut), cut.stage, cut.made)
    return result, list(allowance.made.items())


def test_a_kept_walk_counts_what_its_making_counted():
    pool, label = SMALL["several-labels-in-a-family"]
    call = lambda: exact_distribution(tuple(pool), FREE, None, RARE, 0, label)  # noqa: E731
    alone, counts = counted(10_000, call)
    assert counts and all(made > 0 for _, made in counts)
    with sharing() as store:
        assert counted(10_000, call) == (alone, counts)  # made, and its counts kept
        assert counted(10_000, call) == (alone, counts)  # answered from the store: the same result, the same counts in the same order
        assert (store.walks, store.hits) == (1, 1)
        # two makings on one allowance, as one kernel of two draws: the second adds its counts to the first's
        with budget.counting(10_000) as allowance:
            call(), call()
        assert list(allowance.made.items()) == [(stage, 2 * made) for stage, made in counts]


def test_a_kept_walk_that_would_be_cut_is_cut_as_its_own_walk_is():
    pool, label = SMALL["several-labels-in-a-family"]
    call = lambda: exact_distribution(tuple(pool), FREE, None, RARE, 0, label)  # noqa: E731
    _, counts = counted(10_000, call)
    largest = max(made for _, made in counts)
    cut_alone = counted(largest - 1, call)
    assert isinstance(cut_alone[0], tuple)  # one piece short: the walk is cut
    with sharing() as store:
        counted(10_000, call)
        assert counted(largest - 1, call) == cut_alone  # the same cut, at the same stage and count, with the same words
        assert counted(largest, call) == counted(10_000, call)[:1] + (counts,)  # exactly enough: answered whole
        assert store.walks == 1  # the cut walk kept nothing and counted as no walk


def test_a_walk_made_outside_a_count_is_made_again_inside_one():
    # the bound's build makes its draws uncounted; a search counted in states that then asks the same walk makes it, counted, as it did
    # before the store, and from then on the store answers with the counts
    pool, label = SMALL["a-family-on-both-sides"]
    call = lambda: exact_distribution(tuple(pool), FREE, None, RARE, 0, label)  # noqa: E731
    alone = counted(10_000, call)
    with sharing() as store:
        call()
        assert counted(10_000, call) == alone and (store.walks, store.hits) == (2, 0)
        assert counted(10_000, call) == alone and (store.walks, store.hits) == (2, 1)
        assert call() == alone[0] and store.hits == 2  # outside a count nothing is counted


# ---- memory ---------------------------------------------------------------------------------------------------------------------------------


def draws(count):
    """`count` draws of different walks (the free prefixes and the kept mods differ) and the number of outcomes each has."""
    pool, label = SMALL["several-labels-in-a-family"]
    calls = [(tuple(pool), {PREFIX: 1 + at % 3, SUFFIX: 3}, None, RARE, at // 3, label) for at in range(count)]
    return calls, [len(exact_distribution(*call)) for call in calls]


def test_the_store_holds_at_most_its_limit_and_drops_the_least_recently_used():
    calls, sizes = draws(4)
    limit = sizes[0] + sizes[1] + sizes[2] + 3  # room for the first three (an entry counts its outcomes and one more)
    with sharing(limit) as store:
        for call in calls[:3]:
            exact_distribution(*call)
        assert (len(store), store.held, store.dropped) == (3, limit, 0)
        exact_distribution(*calls[0])  # used again: the second is now the least recently used
        exact_distribution(*calls[3])
        assert store.held <= limit and store.dropped >= 1
        walks = store.walks
        exact_distribution(*calls[0])
        assert store.walks == walks  # still kept
        exact_distribution(*calls[1])
        assert store.walks == walks + 1  # it had left: walked again, the same result
    with sharing(sizes[0]) as small:  # a walk larger than the whole limit is not kept, and nothing leaves for it
        exact_distribution(*calls[0])
        assert (len(small), small.held, small.walks) == (0, 0, 1)


def test_the_limit_is_a_share_of_the_runs_memory_net():
    with budget.running(budget.Budget(None, 600.0, 2000.0).start()), sharing() as store:
        assert store.limit == int(2000 * draw.DRAWS_SHARE * 1024 * 1024 / draw.OUTCOME_BYTES) and store.memory_mb == 2000.0
    with budget.running(budget.Budget.in_states(100).start()), sharing() as store:  # a run counted in states has no memory net
        machine = budget.default_memory_mb()
        assert store.memory_mb is None
        assert store.limit == (draw.DRAWS_KEPT if machine is None else int(machine * draw.DRAWS_SHARE * 1024 * 1024 / draw.OUTCOME_BYTES))


def test_the_store_empties_itself_at_its_share_of_the_memory_net(monkeypatch):
    calls, _ = draws(3)
    held = [100.0]
    monkeypatch.setattr(budget.Clock, "memory", lambda self, fresh=False: held[0])
    with budget.running(budget.Budget(None, 600.0, 1000.0).start()), sharing() as store:
        exact_distribution(*calls[0])
        exact_distribution(*calls[1])
        assert len(store) == 2
        held[0] = draw.GIVE_WAY * 1000.0  # the process holds that share of the net: the store gives its memory back and keeps nothing
        expected = exact_distribution(*calls[2])
        assert (len(store), store.held, store.dropped) == (0, 0, 2)
        assert exact_distribution(*calls[2]) == expected and len(store) == 0
        held[0] = 100.0
        exact_distribution(*calls[2])
        assert len(store) == 1  # room again: it keeps again


# ---- the pool workers ---------------------------------------------------------------------------------------------------------------------



class ForkSpy(PoolSpy):
    """`test_prime_light.PoolSpy` (the real pool with one worker, in this process) that also leaves the plan's store as a fork would: what
    a worker keeps is kept in its own copy of the store and is lost when it ends, but for what it hands back."""

    def map(self, function, pieces, *, chunk=None):
        store = shared_draws()
        saved = None if store is None else (store.walks, store.hits, store.held, store.dropped, None if store.keys is None else list(store.keys), store._kept.copy())
        try:
            return super().map(function, pieces, chunk=chunk)
        finally:
            if store is not None:
                store.walks, store.hits, store.held, store.dropped, store.keys, store._kept = saved
                store.fresh = None


@pytest.fixture
def pool(monkeypatch):
    PoolSpy.made, PoolSpy.mapped = [], []
    monkeypatch.setattr(parallel, "WorkerPool", ForkSpy)
    monkeypatch.setattr(parallel, "can_inherit", lambda: True)
    return ForkSpy


def requests_of(ab):
    return [(state, CHAOS) for state in one_per_pool(ab)]


def test_prime_takes_back_its_workers_walks_and_sends_no_kept_walk_to_a_worker(pool):
    first, second = abstraction(), abstraction()
    alone = abstraction()
    for state, action in requests_of(alone):
        alone.kernel(state, action)
    pools = POOLS  # the six Chaos Orb pools of the fixture, counted by hand in `test_prime_light`
    assert len(alone._cache) == pools
    with sharing() as store:
        store.keys = []
        assert _prime.prime(first, requests_of(first), workers=4) == pools
        assert PoolSpy.mapped == [(pools, 1)]
        # the workers' walks are the plan's. Two of the six pools are one walk: the pool without the Cold Resistance family and the one
        # without the Fire Resistance family are each other's image (the two families have the same side and weights, and the same place in
        # the goal's hybrid craft), so the spy's one worker walked five and answered the sixth from its own copy of the store
        assert (store.walks, len(store)) == (pools - 1, pools - 1)
        assert len(set(store.keys)) == len(store.keys) == pools - 1
        # the model of the next round: every pool's walk is kept, so no pool is forked and the kernels copy
        assert _prime.prime(second, requests_of(second), workers=4) == 0
        assert PoolSpy.mapped == [(pools, 1)]
        for state, action in requests_of(second):
            assert second.kernel(state, action) == alone.kernel(state, action)
        assert (store.walks, store.hits) == (pools - 1, pools)
    assert first._cache == alone._cache == second._cache


def test_two_pools_that_are_each_others_image_are_one_walk():
    # the same two pools in one process: the second is answered by the first's walk, renamed, and its kernel is its own
    ab, alone = abstraction(), abstraction()
    expected = [alone.kernel(state, action) for state, action in requests_of(alone)]
    with sharing() as store:
        assert [ab.kernel(state, action) for state, action in requests_of(ab)] == expected
        assert (store.walks, store.hits) == (POOLS - 1, 1)
    assert ab._cache == alone._cache


def test_a_store_record_is_only_what_a_worker_added():
    store = DrawStore(100)
    store.keep("before", [("a",)], [{frozenset({("a", 1)}): Fraction(1)}], None)
    store.fresh = []
    store.keep("made", [("a",)], [{frozenset({("a", 2)}): Fraction(1)}], None)
    assert [key for key, _ in store.fresh] == ["made"]
    parent = DrawStore(100)
    parent.adopt(store.fresh)
    assert parent.holds("made") and not parent.holds("before") and (parent.walks, parent.held) == (1, 2)
    assert parent.find("made", [("b",)], None) == [{frozenset({("b", 2)}): Fraction(1)}]
