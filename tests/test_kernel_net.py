"""The run's net asked inside the making of one kernel and of one key's members (tickets #1238, #1217; OR-39, OR-40).

R20 with the Orb of Dominance offered (#1195): the listing draw of an unopened Shaper/Elder helmet under `Reads.influenced` grew past 12 GB inside
one kernel (`through_listing` -> `Abstraction.kernel`), and the planner's net of 3,000 MB was never asked there. The net of a stage on the clock
(`budget.asking`) is now asked at most every `budget.ASK_SECONDS`, the clock looked at every `budget.ASK_EVERY` pieces a making makes: by the offers' floors, by the bound's build (inside a kernel and
inside the listing of a key's members) and by the envelope search. A count (`Budget.in_states`, a build counted in pieces) is never asked inside:
its stop points stay where they were.

Every test here counts: the nets are functions that give their reason only while a making is in progress (a flag set by a wrapped `kernel` or
`members`), so a test passes only when the net is asked inside it, and fails on the code before #1238 (which asked between two makings only).
No test reads the clock.
"""

import pytest
from coarse_support import abstraction
from test_cli_envelope_build import listing_world
from test_packed_walk_light import START_ITEM, make_offers

from crafting_system import budget
from crafting_system.abstraction import Abstraction, _pattern
from crafting_system.abstraction._pattern import Pattern, PatternBuilder, Tally, build_pattern_model
from crafting_system.planner import _envelope
from crafting_system.planner._envelope import Net, NoPolicy
from crafting_system.planner._envelope_plan import envelope_result
from crafting_system.planner._offer_floor import FloorsStopped, OfferFloors
from crafting_system.planner._pattern_bound import pattern_offers

REASON = "the test net"


@pytest.fixture(autouse=True)
def every_piece_asks(monkeypatch):
    monkeypatch.setattr(budget, "ASK_EVERY", 1)
    monkeypatch.setattr(budget, "ASK_SECONDS", 0.0)  # no clock: every piece asks


class Inside:
    """A flag up while one of the wrapped makings runs, and a net that gives its reason only then."""

    def __init__(self) -> None:
        self.depth = 0
        self.asked = 0  # questions asked while a making ran

    def wrap(self, function):
        def wrapped(*args, **kwargs):
            self.depth += 1
            try:
                return function(*args, **kwargs)
            finally:
                self.depth -= 1

        return wrapped

    def net(self) -> str | None:
        if self.depth:
            self.asked += 1
            return REASON
        return None


# ---- the allowance, on hand-counted pieces -----------------------------------------------------------------------------------------------------


def test_asking_asks_once_every_so_many_pieces_and_stops_on_a_reason():
    asked = []
    with budget.asking(lambda: asked.append(1) or None, every=4) as allowance:
        for _ in range(10):
            allowance.add("state")
        allowance.tick(3)
    assert len(asked) == 3  # at pieces 4, 8 and 12 (10 outcomes, then 3 members)
    assert allowance.made == {}  # nothing counted: a net on the clock holds no `given`
    reasons = iter([None, "stop now"])
    with pytest.raises(budget.NetReached) as reached, budget.asking(lambda: next(reasons), every=2) as allowance:
        for _ in range(4):
            allowance.add("way")
    assert reached.value.reason == "stop now"
    assert isinstance(reached.value, BaseException) and not isinstance(reached.value, Exception)  # no `except Exception` inside a making swallows it


def test_a_net_is_not_asked_more_often_than_its_seconds(monkeypatch):
    monkeypatch.setattr(budget, "ASK_SECONDS", 1e9)  # never that long between two makings: the gate holds every question back
    asked = []
    with budget.asking(lambda: asked.append(1) or "stop", every=1) as allowance:
        for _ in range(100):
            allowance.add("state")
    assert asked == []


def test_counting_inside_asking_counts_and_is_not_asked():
    with budget.asking(lambda: "never") as outer:
        with budget.counting(3) as counted:
            assert counted.ask is None and budget.counts()
            with pytest.raises(budget.OutcomesCut):
                for _ in range(4):
                    counted.add("state")
        assert budget.allowed() is outer and not budget.counts()


def test_a_count_is_never_asked_inside_and_no_net_opens_nothing():
    with budget.counting(100) as counted, budget.asking(lambda: "never") as inner:
        assert inner is counted and counted.ask is None and budget.counts()
        for _ in range(50):
            counted.add("state")  # no question: the run counted in states keeps its stop points
    with budget.asking(None) as none:
        assert none is None and budget.allowed() is None and not budget.counts()


# ---- the offers' floors: the listing draw of `through_listing` -------------------------------------------------------------------------------


def test_the_floors_stop_at_their_net_inside_the_listing_draws_kernel(monkeypatch):
    ab, start, opened, offers, _ = listing_world()
    inside = Inside()
    monkeypatch.setattr(ab, "kernel", inside.wrap(ab.kernel))
    with pytest.raises(FloorsStopped) as stopped:
        OfferFloors(ab, start, offers, opened, stop=inside.net)
    assert stopped.value.reason == REASON and inside.asked == 1
    # nothing half made was kept: the same abstraction, asked again with no net, gives the floors of a fresh one
    again = OfferFloors(ab, start, offers, opened)
    fresh_ab, fresh_start, _, fresh_offers, _ = listing_world()
    fresh = OfferFloors(fresh_ab, fresh_start, fresh_offers, opened)
    assert again.rho == fresh.rho and [e.pbar for e in again.entries] == [e.pbar for e in fresh.entries]


def test_floors_counted_in_pieces_are_not_asked_inside_a_kernel(monkeypatch):
    ab, start, opened, offers, _ = listing_world()
    inside = Inside()
    monkeypatch.setattr(ab, "kernel", inside.wrap(ab.kernel))
    tally = Tally(10**9, lambda done, cap: "pieces", inside.net)  # the clock's net behind the count, as `offers_floor` makes it
    counted = OfferFloors(ab, start, offers, opened, stop=tally, tally=tally)
    assert inside.asked == 0
    fresh_ab, fresh_start, _, fresh_offers, _ = listing_world()
    assert counted.rho == OfferFloors(fresh_ab, fresh_start, fresh_offers, opened).rho


# ---- the bound's build: one kernel and one key's members (#1217) -------------------------------------------------------------------------------


def test_the_build_stops_at_its_net_inside_one_kernel(monkeypatch):
    monkeypatch.setattr(_pattern, "POLL_SECONDS", 0.0)
    ab = abstraction()
    inside = Inside()
    monkeypatch.setattr(Abstraction, "kernel", inside.wrap(Abstraction.kernel))  # the class: the pattern's twin makes the Chaos Orb's kernels
    model = build_pattern_model(ab, ab.compress(START_ITEM), pattern_offers(make_offers()), stop=inside.net)
    assert model.stopped == REASON and inside.asked == 1
    assert not any(model.expanded)  # the key whose kernel was being made is a tip, its row untouched


def test_the_build_stops_at_its_net_inside_the_listing_of_a_keys_members(monkeypatch):
    monkeypatch.setattr(_pattern, "POLL_SECONDS", 0.0)
    ab = abstraction()
    inside = Inside()
    monkeypatch.setattr(Pattern, "members", inside.wrap(Pattern.members))
    model = build_pattern_model(ab, ab.compress(START_ITEM), pattern_offers(make_offers()), stop=inside.net)
    assert model.stopped == REASON and inside.asked == 1
    assert not any(model.expanded)


def test_a_build_counted_in_pieces_is_not_asked_inside(monkeypatch):
    ab = abstraction()
    inside = Inside()
    monkeypatch.setattr(Abstraction, "kernel", inside.wrap(Abstraction.kernel))
    monkeypatch.setattr(Pattern, "members", inside.wrap(Pattern.members))
    tally = Tally(10**9, lambda done, cap: "pieces", inside.net)
    model = PatternBuilder(ab, ab.compress(START_ITEM), stop=tally, tally=tally).extend(pattern_offers(make_offers()))
    assert model.stopped is None and inside.asked == 0 and all(model.expanded[i] or model.goal[i] for i in range(len(model.keys)))


# ---- the envelope search on the clock --------------------------------------------------------------------------------------------------------


def test_the_search_stops_at_its_memory_net_inside_one_kernel_and_says_so(monkeypatch):
    """The memory the search reads is high only while a kernel is being made (`resident_mb` of the search, patched): the code before #1238 asked
    its net between two kernels only and ran to its exact plan; now the making asks it, and the search stops inside the first kernel it makes."""
    ab = abstraction()
    inside = Inside()
    monkeypatch.setattr(Abstraction, "kernel", inside.wrap(Abstraction.kernel))
    monkeypatch.setattr(_envelope, "resident_mb", lambda under=None: 10_000.0 if inside.depth else 1.0)  # the search's reading; the build reads its own
    with pytest.raises(NoPolicy) as stopped:
        envelope_result(ab, ab.compress(START_ITEM), make_offers(), net=Net(memory_mb=5_000.0))
    assert "10,000 MB" in str(stopped.value.stopped) and "inside the making" in str(stopped.value.stopped)
