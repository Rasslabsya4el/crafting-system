"""The bound's build keeps the kernel keys and the members' answers it asked lately, not all of them (ticket #1335).

`PatternBuilder.computed` (kernel key -> kernel id) and `Pattern._feasible` (member -> whether it is an item) grew with every member a build
made, about 1.3 KB a kernel on R04's 1,245-offer bound, until the run's memory net stopped it. Both are now a `Recent` memo: two generations,
the older let go when the younger is full. An entry let go is computed again when it is asked again, and gives the same answer (a kernel made
again is found among the model's kernels and gets its id), so the model is the model of the build that kept everything.

* `Recent` keeps what was written or read in the last generation, lets the rest go, and counts what it let go.
* A memo's generation is a share of the run's memory net in entries of a stated size (`kept_entries`, OR-40): no figure sized for a machine.
* The model of the hand-worked bow world, built with one entry a generation (every answer let go almost at once), is the model of the build
  that keeps everything: the same keys, actions, kernels, values and start value, from more kernels made.
* The same on a real route up to a net of pairs (R13, as `test_pattern_items_kept`), with memos small enough that they let entries go.
* A bound whose model grows keeps the members of its keys lately expanded only (`members_kept`, #1341): a list let go is made again, the same;
  a key made again on a grown universe never reads a list made before.
"""

import contextlib

import pytest
from abstraction_support import real_game_data
from coarse_support import abstraction as coarse_abstraction
from test_abstraction_pattern import ACTIONS, BOW, GOAL, LEVEL, STARTS, build, offers_of, pattern_data
from test_abstraction_pattern_real import CASES, E
from test_cli_envelope_build import floors_on, world  # noqa: F401  (fixtures)
from test_packed_walk_light import START_ITEM
from test_pattern_items_kept import same_model

from crafting_system import parallel
from crafting_system.abstraction import Abstraction, _pattern
from crafting_system.abstraction._pattern import PatternBuilder, PatternOffer, build_pattern_model
from crafting_system.abstraction._recent import Recent, kept_entries
from crafting_system.planner._offer_floor import OfferFloors
from crafting_system.planner._pattern_bound import pack_pattern_model, pattern_lower_bound
from crafting_system.solver import solve_packed


def test_a_memo_keeps_what_was_used_in_the_last_generation():
    memo = Recent(2)
    memo["a"] = 1
    memo["b"] = 2  # the young generation is full: it becomes the old one
    assert memo.generation == 1 and memo.get("a") == 1  # read from the old generation: written into the young one again
    assert len(memo) == 3 and memo.distinct() == 2  # "a" is in both generations: held twice, one key (`Abstraction.memo_count`, #1366)
    memo["c"] = 3  # full again: "b", read in no generation since, is let go with the old one
    assert "a" in memo and "c" in memo and "b" not in memo and memo.get("b") is None
    assert memo.generation == 2 and memo.dropped == 2  # "a" and "b" were in the old generation; "a" stays in the young one
    with pytest.raises(KeyError):
        memo["b"]
    with pytest.raises(ValueError):
        Recent(0)


def test_a_memo_of_lists_counts_their_items():
    memo = Recent(5, weigh=len)  # a generation holds about 5 members, in lists (`PatternBuilder.members_kept`, #1341)
    memo["a"] = [1, 2]
    memo["b"] = [3, 4]
    assert memo.generation == 0  # 4 members: room for more
    memo["c"] = [5]  # 5: full, the young generation becomes the old one
    assert memo.generation == 1 and memo.weight == 0
    memo["d"] = []  # an empty list weighs one: a memo of them still lets go
    assert memo.get("a") == [1, 2] and memo.weight == 3
    memo["e"] = [6, 7]  # full again: "b", "c" go; "a" was read in this generation
    assert "a" in memo and "b" not in memo and memo.dropped == 3


@contextlib.contextmanager
def kept(keys: int | None, members: int | None, lists: int | None = None):
    """The build with memos of `keys` kernel keys, `members` members and `lists` members in the keys' lists a generation (None: as large as no
    build fills; `lists` None follows `members`)."""
    before = _pattern.KERNEL_KEYS_KEPT, _pattern.MEMBERS_KEPT, _pattern.LISTS_KEPT
    _pattern.KERNEL_KEYS_KEPT = keys or 1 << 62
    _pattern.MEMBERS_KEPT = members or 1 << 62
    _pattern.LISTS_KEPT = lists or members or 1 << 62
    try:
        yield
    finally:
        _pattern.KERNEL_KEYS_KEPT, _pattern.MEMBERS_KEPT, _pattern.LISTS_KEPT = before


def test_a_memo_holds_a_share_of_the_memory_net():
    # a 12 GB net (12,288 MB): `computed` may hold 1/12 of it, 1,024 MB, in two generations of 1 KB keys: 512 MB a generation, 2^19 keys
    assert kept_entries(_pattern.KERNEL_KEY_SHARE, _pattern.KERNEL_KEY_BYTES, 12_288) == 1 << 19
    # `_feasible` may hold 1/20 of it, 614.4 MB, in two generations of 300-byte members: 322,122,547 bytes a generation, 1,073,741 members
    assert kept_entries(_pattern.MEMBER_SHARE, _pattern.MEMBER_BYTES, 12_288) == 1_073_741
    # `members_kept` may hold 1/12 of it, 1,024 MB, in two generations of 300-byte members in the keys' lists: 1,789,569 members a generation
    assert kept_entries(_pattern.LISTS_SHARE, _pattern.LISTS_BYTES, 12_288) == 1_789_569
    assert kept_entries(1 / 12, 1024, 6_144) == 1 << 18  # half the net, half the memo
    assert kept_entries(1 / 12, 1024, 1) == 4_096  # a tiny net: the fewest a generation holds
    with parallel.memory_net(24_576):  # the run's net is the one read
        assert kept_entries(1 / 12, 1024) == 1 << 20


@pytest.mark.parametrize("tags", [True, False], ids=["tags", "no-tags"])
def test_the_build_that_lets_answers_go_is_the_build_that_keeps_them(tags):
    data = pattern_data()

    def made(keys, members):
        ab = Abstraction(data, GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
        start = ab.compress(build(data, BOW, STARTS[0]))
        with kept(keys, members):
            return build_pattern_model(ab, start, offers_of(), tags=tags)

    whole, small = made(None, None), made(1, 1)
    same_model(whole, small)
    assert small.stats.pairs == whole.stats.pairs > 100
    assert small.stats.kernels > whole.stats.kernels  # kernels let go were made again, and found the same ids


PIECES = 30_000  # the build stops after so many (member, offer) pairs, as in `test_pattern_items_kept`


@pytest.mark.parametrize(("route", "tags"), [case for case in CASES if case.id == "r13-auto"])
def test_the_bound_of_a_real_route_is_the_bound_that_keeps_every_answer(route, tags):
    real_game_data()  # skips without the dump

    def made(keys, members):
        _, _, _, abstraction, start, priced, _ = E.build_model(route, "twins", True, False)
        with kept(keys, members):
            return pattern_lower_bound(abstraction, start, priced, tags=tags, pieces=PIECES)

    whole, small = made(None, None), made(64, 256)
    same_model(whole.model, small.model)
    assert list(small.value) == list(whole.value)
    assert small.start_value == whole.start_value
    assert small.model.stats.kernels > whole.model.stats.kernels  # the small memos let kernel keys go that were asked again


def test_a_growing_bound_that_lets_its_keys_members_go_is_the_bound_that_keeps_them(world, floors_on, monkeypatch):
    """#1341: a bound whose model grows (the offers' floors on) kept every key's members for the offers that join later: 3,515 MB on R04's
    1,245-offer bound. Kept for one member a generation, each list is made again where an offer joins its key: the same model, values and start.
    The model starts on a bench craft and the restart: the crafts that join later ask the members the first one asked (29 lists here)."""
    offers = world[2]
    monkeypatch.setattr(OfferFloors, "initial", lambda self: [1, 6])

    def made(lists):
        fresh = coarse_abstraction()
        with kept(None, None, lists):
            return pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM)

    whole, small = made(None), made(1)
    assert whole.rounds > 1 and whole.floors is not None  # offers joined at keys expanded before: their members were asked again
    same_model(whole.model, small.model)
    assert list(small.value) == list(whole.value) and small.start_value == whole.start_value
    assert small.model.stats.members > whole.model.stats.members  # the lists let go were made again


@pytest.mark.parametrize("lists", [None, 2], ids=["kept", "let-go"])
def test_a_bound_that_begins_again_on_a_grown_universe_with_its_keys_members_let_go_is_the_bound_built_at_once(lists):
    """#1341: a key made again when the universe grows (`_begin_again`) takes no list of its members made before: its lists are kept under the
    times it was made again, so an older list is never read, kept or let go. Grown in two steps, with a memo that keeps the lists or one that
    lets them go almost at once, the model is the one built at once on every offer: the same keys and the same value at each."""
    data = pattern_data()
    offers = [*offers_of(), PatternOffer("essence-outside-pool", ACTIONS["essence-outside-pool"], 4.0)]

    def fresh():
        ab = Abstraction(data, GOAL, BOW, LEVEL, tuple(ACTIONS.values()), metamods=True)
        return ab, ab.compress(build(data, BOW, STARTS[0]))

    ab, start = fresh()
    whole = build_pattern_model(ab, start, offers)
    ab, start = fresh()
    with kept(None, None, lists):
        builder = PatternBuilder(ab, start, grow=True)
        builder.extend(offers[:-1])
        grown = builder.extend(offers[-1:])
    assert builder.restarts == 1 and 0 < grown.stats.restarted_keys < len(grown.keys)  # the keys the essence's slot fits began again
    assert set(grown.index) == set(whole.index)
    by_whole = solve_packed(pack_pattern_model(whole, offers)).value
    by_grown = solve_packed(pack_pattern_model(grown, offers)).value
    for key, k in whole.index.items():
        assert float(by_grown[grown.index[key]]) == pytest.approx(float(by_whole[k]), rel=1e-9), key
    if lists is not None:
        assert builder.members_kept.generation > 0  # lists were let go
