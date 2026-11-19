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
"""

import contextlib

import pytest
from abstraction_support import real_game_data
from test_abstraction_pattern import ACTIONS, BOW, GOAL, LEVEL, STARTS, build, offers_of, pattern_data
from test_abstraction_pattern_real import CASES, E
from test_pattern_items_kept import same_model

from crafting_system import parallel
from crafting_system.abstraction import Abstraction, _pattern
from crafting_system.abstraction._pattern import build_pattern_model
from crafting_system.abstraction._recent import Recent, kept_entries
from crafting_system.planner._pattern_bound import pattern_lower_bound


def test_a_memo_keeps_what_was_used_in_the_last_generation():
    memo = Recent(2)
    memo["a"] = 1
    memo["b"] = 2  # the young generation is full: it becomes the old one
    assert memo.generation == 1 and memo.get("a") == 1  # read from the old generation: written into the young one again
    memo["c"] = 3  # full again: "b", read in no generation since, is let go with the old one
    assert "a" in memo and "c" in memo and "b" not in memo and memo.get("b") is None
    assert memo.generation == 2 and memo.dropped == 2  # "a" and "b" were in the old generation; "a" stays in the young one
    with pytest.raises(KeyError):
        memo["b"]
    with pytest.raises(ValueError):
        Recent(0)


@contextlib.contextmanager
def kept(keys: int | None, members: int | None):
    """The build with memos of `keys` kernel keys and `members` members a generation (None: as large as no build fills)."""
    before = _pattern.KERNEL_KEYS_KEPT, _pattern.MEMBERS_KEPT
    _pattern.KERNEL_KEYS_KEPT = keys or 1 << 62
    _pattern.MEMBERS_KEPT = members or 1 << 62
    try:
        yield
    finally:
        _pattern.KERNEL_KEYS_KEPT, _pattern.MEMBERS_KEPT = before


def test_a_memo_holds_a_share_of_the_memory_net():
    # a 12 GB net (12,288 MB): `computed` may hold 1/12 of it, 1,024 MB, in two generations of 1 KB keys: 512 MB a generation, 2^19 keys
    assert kept_entries(_pattern.KERNEL_KEY_SHARE, _pattern.KERNEL_KEY_BYTES, 12_288) == 1 << 19
    # `_feasible` may hold 1/20 of it, 614.4 MB, in two generations of 300-byte members: 322,122,547 bytes a generation, 1,073,741 members
    assert kept_entries(_pattern.MEMBER_SHARE, _pattern.MEMBER_BYTES, 12_288) == 1_073_741
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
