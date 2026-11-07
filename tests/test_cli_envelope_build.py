"""The bound's build under the net, and the offers it leaves out (ticket #626, OR-12, OR-13): a stop inside the build, a bound that stays a lower bound.

The world is the one of `test_cli_envelope_light.py` (about a hundred states, seven offers). Its exact values come from the full walk (`pattern_support.exact_values`),
which shares no code with the build.

* a net asked inside the build ends it between two offers (not only between two keys) and leaves the keys it did not expand as tips; the model is still a
  lower bound of the exact value of every state, and `envelope_result` returns a plan with `[LB, U]` around the exact cost and a limit that says the count was stopped;
* with the offers' floors on (the model built on a part of the offers, a floor action at every key for the rest) the value of every key is still at most
  the exact value of each state that has it, the value of the start equals the model on all the offers (the floor action is the cheapest nowhere at the end),
  and the envelope search gives the full walk's mean;
* a tip is not a dead end: a key the build did not reach keeps every offer as a candidate at its floor.
"""

import dataclasses

import pytest
from coarse_support import abstraction
from pattern_support import exact_values
from test_packed_walk_light import START_ITEM, make_offers

from crafting_system.abstraction import _pattern
from crafting_system.abstraction._pattern import Pattern, PatternBuilder, build_pattern_model
from crafting_system.cli import _packed, _pattern_bound
from crafting_system.cli import _envelope
from crafting_system.cli._envelope import Net, NoPolicy
from crafting_system.cli import _envelope_plan
from crafting_system.cli._envelope_plan import CraftingProblem, build_stop, certificate_text, envelope_limits, envelope_result
from crafting_system.cli._limits import limit_text
from crafting_system.cli._offer_floor import OfferFloors
from crafting_system.cli._pattern_bound import pattern_lower_bound, pattern_offers

TOLERANCE = 1e-9


@pytest.fixture(scope="module")
def world():
    ab = abstraction()
    start = ab.compress(START_ITEM)
    offers = make_offers()
    full = _packed.packed_result(ab, start, offers, solver="packed")
    exact = exact_values(ab, start, pattern_offers(offers))
    return ab, start, offers, full, exact, pattern_lower_bound(ab, start, offers)


def counting_stop(calls: int, reason: str = "the test net"):
    """A net that is reached on its `calls`-th question."""
    asked = []

    def stop():
        asked.append(1)
        return reason if len(asked) >= calls else None

    return stop


def assert_lower_bound(bound, ab, exact) -> None:
    """The value of the key of every state is at most that state's exact value (the model is a lower bound of the whole graph)."""
    pattern = Pattern(ab, tags=bound.model.keys[0].tags is not None)
    for state, value in exact.items():
        k = bound.model.index.get(pattern.key(state))
        if k is not None:
            assert bound.value[k] * (1 - bound.error_bound) <= value * (1 + TOLERANCE), (state, bound.value[k], value)


def test_a_net_asked_between_two_offers_ends_the_build_inside_a_key(world, monkeypatch):
    ab, start, offers, _, exact, _ = world
    monkeypatch.setattr(_pattern, "POLL_SECONDS", 0.0)
    # the 1st question is at the start key, the 2nd to 4th between its offers: the build stops with the first key half expanded
    bound = pattern_lower_bound(ab, start, offers, stop=counting_stop(4))
    assert bound.stopped == "the test net" and not bound.complete
    model = bound.model
    assert model.stopped == "the test net"
    assert not any(model.expanded), "the key that was half expanded is a tip, like the keys the build did not reach"
    assert model.actions[0] == [] and len(model.keys) >= 1
    assert bound.start_value > 0.0  # a tip is not a dead end: its floor action is the cheapest offer, so the value is finite
    assert bound.start_value == pytest.approx(min(p.cost for p in offers))
    assert_lower_bound(bound, ab, exact)


@pytest.mark.parametrize("calls", [10, 30, 90])
def test_a_build_stopped_after_some_keys_is_still_a_lower_bound_and_weaker_than_the_whole(world, monkeypatch, calls):
    ab, start, offers, _, exact, whole = world
    monkeypatch.setattr(_pattern, "POLL_SECONDS", 0.0)
    bound = pattern_lower_bound(ab, start, offers, stop=counting_stop(calls))
    if bound.complete:  # the world is small: a late stop may not be reached
        assert bound.start_value == pytest.approx(whole.start_value, rel=TOLERANCE)
        return
    assert any(bound.model.expanded)  # 8 questions are the start key's (one at its start, seven between its offers)
    assert not all(bound.model.expanded)
    assert bound.start_value <= whole.start_value * (1 + TOLERANCE)
    assert_lower_bound(bound, ab, exact)


def test_the_net_of_a_plan_binds_inside_the_build_and_the_plan_says_the_count_was_stopped(world, monkeypatch):
    ab, start, offers, full, _, _ = world
    exact = full.solution.values[start]
    monkeypatch.setattr(_pattern, "POLL_SECONDS", 0.0)
    monkeypatch.setattr(_envelope_plan, "build_stop", lambda net, began: counting_stop(12))  # the plan's net, reached inside the build
    fresh = abstraction()
    result = envelope_result(fresh, fresh.compress(START_ITEM), offers, net=Net(seconds=600.0))
    info = result.info["envelope"]
    assert info.bound_stopped == "the test net" and 0 < info.bound_expanded < info.bound_keys
    assert info.exact  # the search had time: a weaker count only costs it more states, never the answer
    assert result.solution.values[start] == pytest.approx(exact, rel=TOLERANCE)
    assert info.lower <= exact * (1 + TOLERANCE) and info.upper >= exact * (1 - TOLERANCE)
    # the search stopped too: [LB, U] around the exact cost, a limit that says so and one that says the count was stopped
    fresh = abstraction()
    result = envelope_result(fresh, fresh.compress(START_ITEM), offers, net=Net(states=100), bound=pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, stop=counting_stop(12)))
    info = result.info["envelope"]
    assert not info.exact and info.bound_stopped == "the test net"
    assert info.lower <= exact * (1 + TOLERANCE) <= info.upper * (1 + 2 * TOLERANCE)
    (limit,) = envelope_limits(info)
    assert "The search was stopped" in limit_text(limit)
    assert "count itself was stopped before it was finished" in certificate_text(info)


def test_a_plan_with_no_net_has_a_complete_build(world):
    _, start, offers, full, _, _ = world
    fresh = abstraction()
    info = envelope_result(fresh, fresh.compress(START_ITEM), offers).info["envelope"]
    assert info.bound_stopped is None and info.exact
    assert "count itself was stopped" not in certificate_text(dataclasses.replace(info, exact=False, stopped="x"))


def test_the_net_of_the_build_is_a_share_of_the_time_and_all_of_the_memory(monkeypatch):
    assert build_stop(None, 0.0) is None and build_stop(Net(), 0.0) is None
    import time

    began = time.perf_counter() - 10.0
    assert build_stop(Net(seconds=100.0), began)() is None  # 10 s of 100: under half
    assert "time limit" in build_stop(Net(seconds=15.0), began)()  # 10 s of 15: over half
    monkeypatch.setattr(_envelope_plan, "resident_mb", lambda: 5000.0)  # the process holds 5 GB (a runner's /proc, or none on this PC)
    assert "5,000 MB" in build_stop(Net(memory_mb=1000.0), time.perf_counter())()
    assert build_stop(Net(memory_mb=10_000.0), time.perf_counter())() is None


@pytest.fixture
def floors_on(monkeypatch):
    """The offers' floors on for the seven offers of the world (the product turns them on from 40 offers), the model starting on the Chaos Orb and the restart only."""
    monkeypatch.setattr(_pattern_bound, "MIN_OFFERS", 3)
    monkeypatch.setattr(OfferFloors, "initial", lambda self: [0, 6])


def test_the_model_on_part_of_the_offers_is_a_lower_bound_and_equals_the_whole_at_the_start(world, floors_on):
    ab, start, offers, _, exact, whole = world
    fresh = abstraction()
    bound = pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM)
    assert bound.complete and bound.floors is not None
    assert bound.rounds > 1 and len(bound.positions) > 2  # the floor action was the cheapest at some key, so offers joined the model
    assert bound.start_value == pytest.approx(whole.start_value, rel=1e-8)  # the floor action is the cheapest nowhere at the end
    assert_lower_bound(bound, ab, exact)


def test_the_floor_action_alone_is_a_lower_bound_whatever_part_of_the_offers_the_model_holds(world, floors_on, monkeypatch):
    """Cut the growth off: the model holds only its first offers, and the floor action stands for all the others. It must stay a lower bound (weaker)."""
    ab, start, offers, _, exact, whole = world
    monkeypatch.setattr(_pattern_bound, "_binding", lambda *args, **kwargs: [])
    fresh = abstraction()
    bound = pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM)
    assert bound.rounds == 1 and bound.positions == (0, 6)
    assert bound.start_value < whole.start_value  # strictly weaker: the crafts are carried by their floor
    assert_lower_bound(bound, ab, exact)


def test_the_envelope_search_with_the_floors_gives_the_full_walks_mean(world, floors_on):
    _, start, offers, full, _, _ = world
    fresh = abstraction()
    result = envelope_result(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM)
    info = result.info["envelope"]
    assert info.exact and info.bound_stopped is None
    assert result.solution.values[start] == pytest.approx(full.solution.values[start], rel=TOLERANCE)
    assert info.bound_offers <= len(offers)


def test_a_tip_keeps_every_offer_as_a_candidate_at_its_floor(world):
    ab, start, offers, _, _, _ = world
    fresh = abstraction()
    begin = fresh.compress(START_ITEM)
    bound = pattern_lower_bound(fresh, begin, offers, stop=counting_stop(1))  # stopped before the start key: every key is a tip
    problem = CraftingProblem(fresh, begin, offers, bound)
    labels = {position for _, position in problem.candidates(begin)}
    assert labels == {position for position, priced in enumerate(offers) if not (priced.label == "restart" and begin == problem.start)}
    least = min(low for low, _ in problem.candidates(begin))
    assert problem.lower(begin) <= least * (1 + 1e-12)  # consistent: the bound of the state is at most the least of its offers'


def canonical(model):
    """The model as a table that does not depend on the numbering of keys or kernels: key -> set of (offer index, ((successor key, weight), ...))."""
    table = {}
    for key, row, built in zip(model.keys, model.actions, model.expanded):
        table[key] = (
            built,
            {(oi, tuple(sorted((model.keys[s], w) for s, w in zip(*model.kernels[kid])))) for oi, kid in row},
        )
    return table


def test_a_model_grown_by_offers_is_the_model_built_on_all_of_them_at_once(world):
    ab, start, offers, _, _, _ = world
    all_offers = pattern_offers(offers)
    whole = build_pattern_model(abstraction(), start, all_offers)
    builder = PatternBuilder(abstraction(), start)
    builder.extend(all_offers[:2])
    first = builder.extend(all_offers[2:5])
    grown = builder.extend(all_offers[5:])
    assert canonical(grown) == canonical(whole)
    assert len(first.keys) <= len(grown.keys) and first.stopped is None
    assert all(len(a) <= len(b) for a, b in zip(first.actions, grown.actions))  # a snapshot stays what it was when the builder went on
    assert grown.stats.kernels == whole.stats.kernels  # each distinct kernel once, however the offers came


def test_a_round_stopped_while_offers_join_leaves_the_round_before_as_the_bound(world, floors_on, monkeypatch):
    ab, start, offers, _, exact, whole = world
    monkeypatch.setattr(_pattern, "POLL_SECONDS", 0.0)
    asked = []
    with monkeypatch.context() as inner:
        inner.setattr(_pattern_bound, "_binding", lambda *args, **kwargs: [])  # no growth: the questions of the first round alone
        fresh = abstraction()
        pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM, stop=lambda: asked.append(1) or None)
    first_round = len(asked)
    fresh = abstraction()
    bound = pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM, stop=counting_stop(first_round + 4))
    assert bound.stopped == "the test net" and bound.phase == "growth"
    assert bound.rounds == 1 and bound.positions == (0, 6) and bound.model.stopped is None and all(bound.model.expanded)
    assert_lower_bound(bound, ab, exact)


def test_the_net_of_the_search_is_asked_inside_a_round_that_expands_many_states(world, monkeypatch):
    ab, start, offers, full, _, _ = world
    exact = full.solution.values[start]
    outcomes = {}
    for poll in (1e9, 0.0):  # never inside a round (the net is asked between two rounds), and after every state
        monkeypatch.setattr(_envelope, "POLL_SECONDS", poll)
        fresh = abstraction()
        outcomes[poll] = envelope_result(fresh, fresh.compress(START_ITEM), offers, net=Net(states=100)).info["envelope"]
    between, inside = outcomes[1e9], outcomes[0.0]
    assert not between.exact and not inside.exact and "limit is 100" in inside.stopped
    assert inside.expanded < between.expanded  # the round that went over the limit was cut where the limit was passed, not at its end
    for info in (between, inside):
        assert info.lower <= exact * (1 + TOLERANCE) <= info.upper * (1 + 2 * TOLERANCE)


def test_a_search_stopped_before_a_plan_exists_says_the_lower_bound_it_reached(world):
    ab, start, offers, _, _, _ = world
    fresh = abstraction()
    given = [offer for offer in offers if offer.label != "restart"]  # no restart: no plan can be executed before the greedy policy closes
    with pytest.raises(NoPolicy, match=r"no plan costs less than [0-9]"):
        envelope_result(fresh, fresh.compress(START_ITEM), given, net=Net(states=12))
