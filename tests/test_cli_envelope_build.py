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
import math
from fractions import Fraction
from types import SimpleNamespace

import pytest
from coarse_support import DATA, abstraction, item
from pattern_support import exact_values
from test_packed_walk_light import START_ITEM, make_offers

from crafting_system import parallel
from crafting_system.abstraction import _pattern
from crafting_system.abstraction._pattern import Pattern, PatternBuilder, build_pattern_model
from crafting_system.planner import _packed, _pattern_bound
from crafting_system.planner import _envelope
from crafting_system.planner._envelope import Net, NoPolicy
from crafting_system.planner import _envelope_plan
from crafting_system.planner._envelope_plan import CraftingProblem, build_stop, certificate_text, envelope_limits, envelope_result
from crafting_system.planner._limits import limit_text
from crafting_system.actions import NotApplicableError, OutOfScopeError
from crafting_system.planner._offer_floor import INSIDE, OTHER, OUTSIDE, UNOPENED, FloorsStopped, OfferFloors
from crafting_system.actions import unopened_listing
from crafting_system.planner._offers import BuyStartItem, listing_draw
from crafting_system.solver import ConvergenceError
from crafting_system.planner._pattern_bound import pattern_lower_bound, pattern_offers

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
    # the 1st question is at the start key, the next between its offers and its members: the build stops with the first key half expanded
    bound = pattern_lower_bound(ab, start, offers, stop=counting_stop(4))
    assert bound.stopped == "the test net" and not bound.complete
    model = bound.model
    assert model.stopped == "the test net"
    assert not any(model.expanded), "the key that was half expanded is a tip, like the keys the build did not reach"
    assert model.actions[0] == [] and len(model.keys) >= 1
    assert bound.start_value > 0.0  # a tip is not a dead end: its floor action is the cheapest offer, so the value is finite
    assert bound.start_value == pytest.approx(min(p.cost for p in offers))
    assert_lower_bound(bound, ab, exact)


def test_the_build_asks_its_net_between_every_two_members_of_a_key(world, monkeypatch):
    """#1179: the net was asked between two offers of a key only, and one offer over the members of a key (R14's Harvest swaps) ran minutes past
    the run's net. On the clock, a question now comes between every two (member, offer) pairs the build looks at."""
    _, _, offers, _, _, _ = world
    monkeypatch.setattr(_pattern, "POLL_SECONDS", 0.0)
    fresh = abstraction()
    events: list[str] = []
    real = fresh.kernel_key

    def kernel_key(state, action):
        events.append("pair")
        return real(state, action)

    monkeypatch.setattr(fresh, "kernel_key", kernel_key)
    build_pattern_model(fresh, fresh.compress(START_ITEM), pattern_offers(offers), stop=lambda: events.append("asked") or None)
    pairs = events.count("pair")
    assert pairs > len(offers)  # keys of more than one member were met
    assert "pair,pair" not in ",".join(events)


@pytest.mark.parametrize("calls", [40, 150, 600])  # the net is asked between two members of a key too (#1179): 30 questions for the start key
def test_a_build_stopped_after_some_keys_is_still_a_lower_bound_and_weaker_than_the_whole(world, monkeypatch, calls):
    ab, start, offers, _, exact, whole = world
    monkeypatch.setattr(_pattern, "POLL_SECONDS", 0.0)
    bound = pattern_lower_bound(ab, start, offers, stop=counting_stop(calls))
    if bound.complete:  # the world is small: a late stop may not be reached
        assert bound.start_value == pytest.approx(whole.start_value, rel=TOLERANCE)
        return
    assert any(bound.model.expanded)  # about 30 questions are the start key's (at its start, between its offers and between its members)
    assert not all(bound.model.expanded)
    assert bound.start_value <= whole.start_value * (1 + TOLERANCE)
    assert_lower_bound(bound, ab, exact)


def test_the_net_of_a_plan_binds_inside_the_build_and_the_plan_says_the_count_was_stopped(world, monkeypatch):
    ab, start, offers, full, _, _ = world
    exact = full.solution.values[start]
    monkeypatch.setattr(_pattern, "POLL_SECONDS", 0.0)
    monkeypatch.setattr(_envelope_plan, "build_stop", lambda net, began: counting_stop(40))  # the plan's net, reached inside the build
    fresh = abstraction()
    result = envelope_result(fresh, fresh.compress(START_ITEM), offers, net=Net(seconds=600.0))
    info = result.info["envelope"]
    assert info.bound_stopped == "the test net" and 0 < info.bound_expanded < info.bound_keys
    assert info.exact  # the search had time: a weaker count only costs it more states, never the answer
    assert result.solution.values[start] == pytest.approx(exact, rel=TOLERANCE)
    assert info.lower <= exact * (1 + TOLERANCE) and info.upper >= exact * (1 - TOLERANCE)
    # the search stopped too: [LB, U] around the exact cost, a limit that says so and one that says the count was stopped
    fresh = abstraction()
    result = envelope_result(fresh, fresh.compress(START_ITEM), offers, net=Net(states=100), bound=pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, stop=counting_stop(40)))
    info = result.info["envelope"]
    assert not info.exact and info.bound_stopped == "the test net"
    assert info.lower <= exact * (1 + TOLERANCE) <= info.upper * (1 + 2 * TOLERANCE)
    *walked, limit = envelope_limits(info)  # a stopped build with no order: the walk toward the goal gave the first plan, and says so (#1142)
    assert "The search was stopped" in limit_text(limit)
    assert [w.kind for w in walked] == (["plan-reached"] if info.reached else [])
    assert "count itself was stopped before it was finished" in certificate_text(info)


def test_a_plan_with_no_net_has_a_complete_build(world):
    _, start, offers, full, _, _ = world
    fresh = abstraction()
    info = envelope_result(fresh, fresh.compress(START_ITEM), offers).info["envelope"]
    assert info.bound_stopped is None and info.exact
    assert "count itself was stopped" not in certificate_text(dataclasses.replace(info, exact=False, stopped="x"))


def test_the_build_takes_a_quarter_of_the_time_and_all_of_the_memory(monkeypatch):
    """#825: the build stops once the time left is at most 3 times its own (a quarter of the net), set from the search/build ratio on R04 and R14."""
    assert build_stop(None, 0.0) is None and build_stop(Net(), 0.0) is None
    clock = SimpleNamespace(now=0.0)  # a clock set by hand (tests/test_no_timing.py)
    clock.perf_counter = lambda: clock.now
    monkeypatch.setattr(_envelope_plan, "time", clock)
    stop = build_stop(Net(seconds=600.0), 0.0)
    for now in range(10, 150, 10):  # steps of 10 s: at 140 s, 460 s are left, more than 3 x 140 = 420
        clock.now = float(now)
        assert stop() is None
    clock.now = 150.0  # 450 s left, 3 x 150 = 450: the search's room is reached
    assert stop() == (
        "stopped after 150 of the 600 seconds of the time limit, to leave the rest for the search for the plan, which takes several times as long as this count"
    )
    clock.now = 0.0
    assert build_stop(Net(seconds=0.0), 0.0)() == "the time limit of 0 seconds was reached"  # a net of 0 s: at the first ask
    monkeypatch.setattr(_envelope_plan, "resident_mb", lambda under=None: 5000.0)  # the process holds 5 GB (a runner's /proc, or none on this PC)
    assert "5,000 MB" in build_stop(Net(memory_mb=1000.0), 0.0)()
    assert build_stop(Net(memory_mb=10_000.0), 0.0)() is None


def test_the_memory_net_of_a_plan_watches_the_pool_workers_through_the_build_and_the_search(world, monkeypatch):
    """#626 (OR-12): the build primes the distributions in worker processes; the run's memory net is set for the build and the search, so the wait
    on the workers reads their memory too (`parallel.memory_net`), and it is lifted when the plan is made."""
    ab, start, offers, full, _, _ = world
    seen = []
    real = _envelope_plan.pattern_lower_bound

    def spy(*args, **kwargs):
        seen.append(parallel.active_memory_net())
        return real(*args, **kwargs)

    monkeypatch.setattr(_envelope_plan, "pattern_lower_bound", spy)
    fresh = abstraction()
    plan = envelope_result(fresh, fresh.compress(START_ITEM), offers, net=Net(memory_mb=50_000.0))
    assert seen == [50_000.0] and parallel.active_memory_net() is None
    assert plan.solution.values[start] == pytest.approx(full.solution.values[start], rel=TOLERANCE)


@pytest.fixture
def floors_on(monkeypatch):
    """The offers' floors on for the seven offers of the world (the product turns them on from 40 offers), the model starting on the Chaos Orb and the restart only."""
    monkeypatch.setattr(_pattern_bound, "MIN_OFFERS", 3)
    monkeypatch.setattr(OfferFloors, "initial", lambda self: [0, 6])


def test_the_model_on_part_of_the_offers_grows_until_it_equals_the_whole_at_the_start(world, floors_on):
    """#988: the model starts on the Chaos Orb and the restart; the crafts are left to the floor action, whose floor there is the craft's price (a craft
    has no chance to raise), so a model built once is capped by that price at every key. The floor action is the cheapest at keys the model's policy
    reaches, the crafts join, and at the end the start's value is the model of every offer's, which the full walk checks at every state."""
    ab, start, offers, _, exact, whole = world
    fresh = abstraction()
    said = []
    bound = pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM, progress=said.append)
    assert bound.complete and bound.floors is not None
    assert bound.start_value == pytest.approx(whole.start_value, rel=1e-8)  # the floor action is the cheapest nowhere at the end
    assert bound.rounds > 1 and len(bound.positions) > 2  # the floor action was the cheapest at some key, so offers joined the model
    assert sum(line.startswith("model ") and "solving the count" in line for line in said) == bound.rounds
    assert_lower_bound(bound, ab, exact)


def test_the_offers_that_join_are_built_only_at_the_keys_that_need_them_and_the_bound_stays_lower(world, floors_on):
    """#1325: the five crafts are needed at 6 of the 10 keys of the first model (the keys where the floor action is the cheapest and the policy
    goes, or of the start's shape); they are built there only, not at the 4 others nor at the keys found after, where the floor action keeps
    their floors, until a later round finds them needed there too (in this small world, by the end, everywhere). The model is a lower bound at every state all the same, and the start's value is the model of every offer's: at the end the
    floor action is the cheapest at no key that counts, so the policy is one of the whole model (`_binding`)."""
    ab, start, offers, _, exact, whole = world
    fresh = abstraction()
    said = []
    bound = pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM, progress=said.append)
    assert bound.complete and len(bound.narrow) == 5
    assert any("5 offers more join the model, at 6 keys that need them (30 offers at a key)" in line for line in said)
    expanded = [k for k, built in enumerate(bound.model.expanded) if built and not bound.model.goal[k]]
    for position, keys in bound.narrow.items():
        j = bound.positions.index(position)
        for k in expanded:  # a key that does not hold the offer has no row of it; one that holds it was given it
            assert any(index == j for index, _ in bound.model.actions[k]) <= (k in keys)
            assert bound.holds(k, position) == (k in keys)
    assert bound.start_value == pytest.approx(whole.start_value, rel=1e-8)
    assert_lower_bound(bound, ab, exact)


def test_the_search_on_the_floors_looks_at_no_more_states_than_on_the_model_of_every_offer(world, floors_on):
    """#988: the search on a bound whose model holds part of the offers expands the states the search on the model of every offer expands, and no
    more: the offers left out are where their floors rule them out. Before the fix the model stayed on its first two offers, its value at the start
    capped by the price of a craft, and the search expanded more states for the same mean."""
    _, start, offers, full, _, whole = world
    fresh = abstraction()
    on_floors = envelope_result(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM).info["envelope"]
    fresh = abstraction()
    on_all = envelope_result(fresh, fresh.compress(START_ITEM), offers, bound=whole).info["envelope"]
    assert on_floors.exact and on_all.exact
    assert on_floors.upper == pytest.approx(on_all.upper, rel=TOLERANCE) == pytest.approx(full.solution.values[start], rel=TOLERANCE)
    assert (on_floors.expanded, on_floors.realized) <= (on_all.expanded, on_all.realized), (on_floors, on_all)


def test_the_floor_action_alone_is_a_lower_bound_whatever_part_of_the_offers_the_model_holds(world, floors_on, monkeypatch):
    """Cut the growth off: the model holds only its first offers, and the floor action stands for all the others. It stays a lower bound, and it is
    strictly weaker: what the growth of #988 brings back."""
    ab, start, offers, _, exact, whole = world
    monkeypatch.setattr(_pattern_bound, "_binding", lambda *args, **kwargs: ([], {}))
    fresh = abstraction()
    bound = pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM)
    assert bound.rounds == 1 and bound.positions == (0, 6)
    assert bound.start_value < whole.start_value  # strictly weaker: the crafts are carried by their floor
    assert_lower_bound(bound, ab, exact)


def test_a_round_stopped_while_offers_join_leaves_the_round_before_as_the_bound(world, floors_on, monkeypatch):
    ab, start, offers, _, exact, whole = world
    monkeypatch.setattr(_pattern, "POLL_SECONDS", 0.0)
    asked = []
    with monkeypatch.context() as inner:
        inner.setattr(_pattern_bound, "_binding", lambda *args, **kwargs: ([], {}))  # no growth: the questions of the first round alone
        fresh = abstraction()
        pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM, stop=lambda: asked.append(1) or None)
    first_round = len(asked)
    fresh = abstraction()
    bound = pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM, stop=counting_stop(first_round + 4))
    assert bound.stopped == "the test net" and bound.phase == "growth"
    assert bound.rounds == 1 and bound.positions == (0, 6) and bound.model.stopped is None and all(bound.model.expanded)
    assert_lower_bound(bound, ab, exact)


def test_the_net_ends_the_examination_of_the_offers_outside_the_model_and_the_round_stands(world, floors_on, monkeypatch):
    ab, start, offers, _, exact, _ = world

    def stopped(self, position, limits):
        raise FloorsStopped("the test net")

    monkeypatch.setattr(OfferFloors, "needed", stopped)
    said = []
    fresh = abstraction()
    bound = pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM, progress=said.append)
    assert bound.phase == "growth" and bound.stopped == "the test net" and bound.rounds == 1 and bound.positions == (0, 6)
    assert any(line.startswith("binding: examining") for line in said)
    assert_lower_bound(bound, ab, exact)


@pytest.mark.parametrize("pieces, phase", [(1, "floors"), (2, "model"), (12, "model"), (30, "growth"), (10**6, "complete")])
def test_a_build_counted_in_pieces_of_work_stops_at_its_count_in_every_phase_whatever_the_clock_does(world, floors_on, monkeypatch, pieces, phase):
    """#1101: in a run counted in states the build counts its pieces of work (a (member, offer) pair it looks at, an offer's floor raised) and
    asks its net at every offer, never on the clock (`POLL_SECONDS` is not patched): the same count stops it at the same point, with the same
    bound, whether every reading of the clock moves it by 1,000 s or by nothing. The time net's stop (`build_stop`) is asked too, and decides
    nothing with no time net. The bound is a lower bound wherever it stopped."""
    from crafting_system import budget as budget_module

    ab, start, offers, _, exact, whole = world
    step, readings = [0.0], iter(range(10**9))
    monkeypatch.setattr(budget_module.time, "perf_counter", lambda: step[0] * next(readings))  # the one clock module every stage reads

    def built(seconds_per_reading: float):
        step[0] = seconds_per_reading
        fresh = abstraction()
        net = Net(states=10**6, pieces=pieces)
        return pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM, stop=build_stop(net, 0.0), pieces=net.pieces)

    slow, fast = built(1000.0), built(0.0)
    assert (slow.phase, slow.pieces, slow.share, slow.stopped, slow.rounds, slow.positions) == (fast.phase, fast.pieces, fast.share, fast.stopped, fast.rounds, fast.positions)
    assert slow.start_value == fast.start_value and slow.model.keys == fast.model.keys
    assert slow.phase == phase and slow.share == pieces
    if phase == "complete":
        assert slow.stopped is None and slow.pieces < pieces and slow.start_value == pytest.approx(whole.start_value, rel=1e-8)
    else:
        assert slow.pieces >= pieces and slow.stopped.startswith(f"it had done {slow.pieces:,} pieces of work, its allowance being {pieces:,} pieces of work, set from the run's states net")
    assert_lower_bound(slow, ab, exact)


def test_a_build_counted_in_pieces_of_work_counts_each_floor_the_binding_step_raises_and_stops_there():
    """#1101: the binding step examines the offers outside the model, and raising a reroll's floor is an exact chance (R09: 4,922 offers, about
    80 s a round). Each raise is one piece of work, and the count is asked before each: past it, the step stops (`FloorsStopped`, with the
    count's words), and the round's model stands (`pattern_lower_bound`)."""
    from crafting_system.abstraction._pattern import Tally
    from crafting_system.planner._offer_kinds import ONE

    offers = make_offers()
    fresh = abstraction()
    tally = Tally(10**6, lambda done, cap: f"{done:,} of {cap:,} pieces")
    floors = OfferFloors(fresh, fresh.compress(START_ITEM), offers, START_ITEM, tally, tally)
    reroll = floors.entries[0]  # the Chaos Orb, raised to its exact chance by `rho` (two pieces)
    assert (offers[0].label, reroll.level, tally.done) == ("Chaos Orb", 2, 2)
    limits = {INSIDE: math.inf, OUTSIDE: math.inf, OTHER: None, UNOPENED: None}  # every floor is needed: each level is raised
    reroll.level, reroll.pbar = 0, ONE  # back to its loose floor, as an offer the binding step meets first
    floors.needed(0, limits)
    assert (reroll.level, tally.done) == (2, 4)
    reroll.level, reroll.pbar = 0, ONE
    tally.cap = 5  # one more raise
    with pytest.raises(FloorsStopped, match="^5 of 5 pieces$"):
        floors.needed(0, limits)
    assert (reroll.level, tally.done) == (1, 5)


def test_the_net_is_asked_before_the_solve_of_a_round_that_grew_and_the_round_before_stands(world, floors_on, monkeypatch):
    ab, start, offers, _, exact, _ = world
    packed, solved = [], []
    real_pack, real_solve = _pattern_bound.pack_pattern_model, _pattern_bound.solve_packed

    def pack(*args, **kwargs):
        packed.append(1)
        return real_pack(*args, **kwargs)

    def solve(*args, **kwargs):
        solved.append(1)
        return real_solve(*args, **kwargs)

    monkeypatch.setattr(_pattern_bound, "pack_pattern_model", pack)
    monkeypatch.setattr(_pattern_bound, "solve_packed", solve)
    said = []
    fresh = abstraction()
    bound = pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM, progress=said.append, stop=lambda: "the test net" if len(packed) >= 2 else None)
    assert len(packed) == 2 and len(solved) == 1  # the second round was packed, and the net was reached before its solve
    assert bound.phase == "growth" and bound.stopped == "the test net" and bound.rounds == 1
    assert any("before the solve" in line for line in said) and any(line.startswith("model 1: solving the count") for line in said)
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


def test_the_net_of_the_search_is_asked_inside_a_round_that_expands_many_states(world, monkeypatch):
    ab, start, offers, full, _, _ = world
    exact = full.solution.values[start]
    outcomes = {}
    for net in (Net(seconds=1e9, states=100), Net(states=100)):  # a run on the clock; a run counted in states alone (`Budget.in_states`, #886)
        for poll in (1e9, 0.0):  # never inside a round (the net is asked between two rounds), and after every state
            monkeypatch.setattr(_envelope, "POLL_SECONDS", poll)
            fresh = abstraction()
            outcomes[net.seconds, poll] = envelope_result(fresh, fresh.compress(START_ITEM), offers, net=net).info["envelope"]
    between, inside = outcomes[1e9, 1e9], outcomes[1e9, 0.0]
    assert not between.exact and not inside.exact and "limit is 100" in inside.stopped
    assert inside.expanded < between.expanded  # the round that went over the limit was cut where the limit was passed, not at its end
    for info in (between, inside):
        assert info.lower <= exact * (1 + TOLERANCE) <= info.upper * (1 + 2 * TOLERANCE)
    # a states net alone is asked between rounds only: where the clock polls inside a round never changes where the search stops
    assert outcomes[None, 0.0].expanded == outcomes[None, 1e9].expanded == between.expanded


def test_a_search_stopped_before_a_plan_exists_says_the_lower_bound_it_reached(world):
    ab, start, offers, _, _, _ = world
    fresh = abstraction()
    given = [offer for offer in offers if offer.label != "restart"]  # no restart: no plan can be executed before the greedy policy closes
    with pytest.raises(NoPolicy, match=r"no plan costs less than [0-9]"):
        envelope_result(fresh, fresh.compress(START_ITEM), given, net=Net(states=12))


def test_a_stopped_plan_the_solver_cannot_certify_is_a_refusal_with_the_lower_bound(world, monkeypatch):
    ab, start, offers, _, _, _ = world

    def uncertified(self, deadline=None):
        raise ConvergenceError("the policy iteration on 533,666 states certifies only a relative bound of 2.07e-06", 2.07e-06)

    monkeypatch.setattr(_envelope.Search, "_upper", uncertified)  # every solve of the upper graph: the first plan's (not fatal) and the stopped plan's
    fresh = abstraction()
    with pytest.raises(NoPolicy, match=r"cannot be solved to a certified cost .*no plan costs less than [0-9]"):
        envelope_result(fresh, fresh.compress(START_ITEM), offers, net=Net(states=100))


def test_the_distributions_are_primed_in_chunks_and_the_model_is_the_same(world, monkeypatch):
    ab, start, offers, _, _, whole = world
    all_offers = pattern_offers(offers)
    plain = build_pattern_model(abstraction(), start, all_offers)
    calls = []
    fresh = abstraction()
    real = type(fresh).prime

    def recording(self, requests, **options):
        requests = list(requests)
        calls.append(len({id(action) for _, action in requests}))  # offers in the chunk
        return real(self, requests, **options)

    monkeypatch.setattr(type(fresh), "prime", recording)
    monkeypatch.setattr(_pattern, "PRIME_FROM", 2)
    monkeypatch.setattr(_pattern, "PRIME_CHUNK", 3)
    primed = build_pattern_model(fresh, start, all_offers)
    assert canonical(primed) == canonical(plain)
    assert calls and set(calls) <= {0, 1, 2, 3}  # chunks of at most 3 offers (the restart has no action: a chunk may hold fewer, or none)
    assert len(calls) >= 3 * len(primed.keys) // 2  # a chunk for each three offers of each key, about


def test_a_float_kernel_is_the_exact_one_to_float_error_and_never_leaks_into_an_exact_kernel(world):
    ab, start, offers, _, _, _ = world
    fresh = abstraction()
    begin = fresh.compress(START_ITEM)
    chaos = offers[0].offer.action
    exact = fresh.kernel(begin, chaos)
    with fresh.approximate():
        floats = fresh.kernel(begin, chaos)
    assert set(floats) == set(exact)
    assert any(isinstance(chance, float) for chance in floats.values())
    for state, chance in exact.items():
        assert float(floats[state]) == pytest.approx(float(chance), rel=1e-12)
    again = fresh.kernel(begin, chaos)  # outside the block the caches are the exact ones
    assert again == exact and all(isinstance(chance, Fraction) for chance in again.values()) and sum(again.values()) == 1


def test_lowering_a_float_kernel_puts_every_chance_below_the_exact_one_and_the_rest_in_the_sink():
    exact = {0: Fraction(1, 3), 1: Fraction(2, 3)}
    floats = {0: 1 / 3 * (1 + 1e-13), 1: 2 / 3 * (1 + 1e-13)}  # above the exact, by more than the float error of the engine
    lowered = _pattern._lowered(dict(floats))
    assert all(lowered[k] < exact[k] for k in exact)
    assert lowered[_pattern.SINK] > 0 and sum(lowered.values()) == 1
    assert _pattern._lowered({0: Fraction(1, 3), 1: Fraction(2, 3)}) == {0: Fraction(1, 3), 1: Fraction(2, 3)}  # an exact kernel stays
    with pytest.raises(RuntimeError, match="adds up to more than one"):
        _pattern._lowered({0: 1.0 + 1e-3})


def test_a_model_built_in_floats_is_below_the_exact_model_by_about_1e_9(world):
    ab, start, offers, _, exact, whole = world
    fresh = abstraction()
    begin = fresh.compress(START_ITEM)
    bound = pattern_lower_bound(fresh, begin, offers, approximate=True)
    assert bound.complete and any(_pattern.SINK in successors for successors, _ in bound.model.kernels)
    assert len(bound.value) == len(bound.model.keys) + 1 and bound.value[-1] == 0.0  # the sink last
    assert 0.0 < (whole.start_value - bound.start_value) / whole.start_value < 1e-7
    assert_lower_bound(bound, ab, exact)
    other = abstraction()
    plan = envelope_result(other, other.compress(START_ITEM), offers, bound=bound)  # the search on it still gives the full walk's mean
    assert plan.solution.values[start] == pytest.approx(world[3].solution.values[start], rel=TOLERANCE)


def test_the_floor_of_an_offer_is_below_its_exact_q_at_every_state_of_the_world_in_every_class(world):
    """`floors.lower(offer, klass of s) <= Q*(s, offer)` for each state of the walked graph and each offer the game allows there; `V*(s) >= rho` outside E."""
    ab, start, offers, _, exact, _ = world
    fresh = abstraction()
    floors = OfferFloors(fresh, fresh.compress(START_ITEM), offers, START_ITEM)
    assert floors.rho > 0 and floors.chosen
    for entry in floors.entries:
        if entry.kind == "reroll":
            floors._raise(entry, 2)  # the exact chance, the tightest floor
    seen = set()
    for state, value in exact.items():
        klass = floors.klass(state.flags, state.fractured, state.status, state.imprints)
        seen.add(klass)
        if ab.is_goal(state):
            continue
        if klass == OUTSIDE:
            assert value >= floors.rho * (1 - 1e-9), (state, value, floors.rho)
        for position, priced in enumerate(offers):
            action = priced.offer.action
            if isinstance(action, BuyStartItem):
                if state == start:
                    continue
                successors = {start: Fraction(1)}
            else:
                try:
                    successors = ab.kernel(state, action)
                except (NotApplicableError, OutOfScopeError):
                    continue
            q = priced.cost + float(sum(chance * exact[successor] for successor, chance in successors.items()))
            assert floors.lower(position, klass) <= q * (1 + 1e-9), (priced.label, klass, state)
    assert seen == {OTHER, INSIDE, OUTSIDE} or seen == {INSIDE, OUTSIDE}, seen  # the world has states in E and outside it
    assert floors.klass(start.flags, start.fractured, start.status, start.imprints) == OUTSIDE


def listing_world(restart_price: float = 3.0):
    """The light world from a bought start the market sells unopened (ADR-0064): the restart buys the listing and a draw opens it into the Rare."""
    opened = item()
    listing = unopened_listing(DATA, opened)
    offers = [dataclasses.replace(p, cost=restart_price) if isinstance(p.offer.action, BuyStartItem) else p for p in make_offers(listing)]
    offers.append(listing_draw(DATA, listing, opened.rarity, offers))
    ab = abstraction()
    start = ab.compress(listing)
    return ab, start, opened, offers, exact_values(ab, start, pattern_offers(offers))


@pytest.mark.parametrize("restart_price", [3.0, 0.05])
def test_the_floors_of_an_unopened_start_are_those_of_the_item_it_opens_into_and_stay_below_the_exact_q(restart_price):
    """#626/#731: a bought start is an unopened listing (ADR-0064) that no reroll touches; the floors are stated for the shape it opens into, as the
    pruned walk's are, so `rho` is finite and the listing itself is a state of another shape (its floor is the cost), never `rho` = 1e300 above its exact value.
    The restart buys the listing and its draw can land in E: with a cheap restart, buying again and drawing is the cheapest way into E, and `rho` counts it."""
    ab, start, opened, offers, exact = listing_world(restart_price)
    assert start.flags.unopened
    floors = OfferFloors(ab, start, offers, opened)
    fresh = abstraction()
    plain = OfferFloors(fresh, fresh.compress(opened), make_offers(opened), opened)
    assert floors.chosen == plain.chosen and 0 < floors.rho < 1e6
    if restart_price == 3.0:  # buying again is dearer than the Chaos Orb: `rho` is the reroll's, as from the opened start
        assert floors.rho == pytest.approx(plain.rho, rel=1e-12)
    else:  # the restart and its draw are the cheapest way into E, below the Chaos Orb's cost / chance
        assert floors.rho < plain.rho
    assert floors.klass(start.flags, start.fractured, start.status, start.imprints) == UNOPENED
    for position, priced in enumerate(offers):  # at the listing only the draw works, and the restart buys it again: every other offer is refused there
        action = priced.offer.action
        if getattr(action, "opens_listing", False):
            assert floors.lower(position, UNOPENED) == priced.cost
        elif isinstance(action, BuyStartItem):
            assert floors.lower(position, UNOPENED) == floors.entries[position].cost  # the restart counted with its draw
        else:
            assert floors.lower(position, UNOPENED) == float("inf")
            with pytest.raises(NotApplicableError):
                ab.kernel(start, action)
    shape = ab.compress(opened)
    assert floors.klass(shape.flags, shape.fractured, shape.status, shape.imprints) == OUTSIDE
    for entry in floors.entries:
        if entry.kind == "reroll":
            floors._raise(entry, 2)
    for state, value in exact.items():
        if ab.is_goal(state):
            continue
        klass = floors.klass(state.flags, state.fractured, state.status, state.imprints)
        if klass == OUTSIDE:
            assert value >= floors.rho * (1 - 1e-9), (state, value, floors.rho)
        for position, priced in enumerate(offers):
            action = priced.offer.action
            if isinstance(action, BuyStartItem):
                successors = {start: Fraction(1)}
            else:
                try:
                    successors = ab.kernel(state, action)
                except (NotApplicableError, OutOfScopeError):
                    continue
            q = priced.cost + float(sum(chance * exact[successor] for successor, chance in successors.items()))
            assert floors.lower(position, klass) <= q * (1 + 1e-9), (priced.label, klass, state)


@pytest.mark.parametrize("restart_price", [3.0, 0.05])
def test_the_envelope_search_from_an_unopened_start_with_the_floors_gives_the_full_walks_mean(restart_price, monkeypatch):
    """#626/#731 end to end: from a bought listing, with the floors on (the restart and the Chaos Orb first, the rest by the floors), the search gives
    the full walk's mean and its root's bound is finite; before, `rho` was 1e300 at the listing and the search refused it as an inconsistent bound."""
    monkeypatch.setattr(_pattern_bound, "MIN_OFFERS", 3)
    _, start, opened, offers, exact = listing_world(restart_price)
    listing = unopened_listing(DATA, opened)
    walk_ab = abstraction()
    full = _packed.packed_result(walk_ab, walk_ab.compress(listing), offers, solver="packed")
    fresh = abstraction()
    result = envelope_result(fresh, fresh.compress(listing), offers, item=opened)
    info = result.info["envelope"]
    assert info.exact and info.bound_stopped is None and math.isfinite(info.lower)
    assert result.solution.values[start] == pytest.approx(full.solution.values[start], rel=TOLERANCE) == pytest.approx(exact[start], rel=TOLERANCE)


def test_a_craft_has_no_floor_above_its_cost_inside_e_but_a_reroll_has(world):
    _, _, offers, _, _, _ = world
    fresh = abstraction()
    floors = OfferFloors(fresh, fresh.compress(START_ITEM), offers, START_ITEM)
    position = next(p for p, e in enumerate(floors.entries) if e.kind == "reroll")
    craft = next(p for p, e in enumerate(floors.entries) if e.kind == "craft")
    for level in (1, 2):
        floors._raise(floors.entries[position], level)
    reroll = floors.entries[position]
    assert reroll.pbar < 1
    assert floors.lower(position, INSIDE) == floors.lower(position, OUTSIDE) > reroll.cost
    assert floors.lower(craft, INSIDE) == floors.entries[craft].cost < floors.lower(craft, OUTSIDE)
    assert floors.lower(position, OTHER) == reroll.cost


def test_tighten_raises_a_reroll_a_level_at_a_time_only_until_its_floor_is_above_the_figure_asked(world):
    """`OfferFloors.tighten` (#829): a reroll's floor in a class of the start's shape is raised from its level, one level at a time, and stops at the
    first floor above the figure asked (or at the exact chance, level 2); a craft, and any offer in a class of another shape, keeps its floor."""
    _, _, offers, _, _, _ = world
    fresh = abstraction()
    begin = fresh.compress(START_ITEM)
    exact = OfferFloors(fresh, begin, offers, START_ITEM)
    reroll = next(p for p, e in enumerate(exact.entries) if e.kind == "reroll")  # the Chaos Orb, at level 2 already (`rho` worked it out)
    craft = next(p for p, e in enumerate(exact.entries) if e.kind == "craft")
    assert exact.entries[reroll].level == 2
    top = exact.lower(reroll, OUTSIDE)

    floors = OfferFloors(abstraction(), begin, offers, START_ITEM)
    entry = floors.entries[reroll]
    entry.level, entry.pbar = 0, Fraction(1)  # back to the loose floor, its price: a reroll `rho` did not need (R08: most of 3,938 sets)
    loose = floors.lower(reroll, OUTSIDE)
    assert loose < top
    assert floors.tighten(reroll, OUTSIDE, loose / 2) == loose and entry.level == 0  # already above: nothing worked out
    assert floors.tighten(reroll, OTHER, math.inf) == entry.cost and entry.level == 0  # another shape: the floor is the cost
    assert floors.tighten(reroll, OUTSIDE, math.inf) == pytest.approx(top, rel=1e-12) and entry.level == 2  # never above: the exact chance
    assert floors.tighten(reroll, OUTSIDE, math.inf) == pytest.approx(top, rel=1e-12)  # worked out once: the same floor for every later state
    assert floors.tighten(reroll, INSIDE, math.inf) == floors.lower(reroll, INSIDE)  # the chance is the offer's own: the other class reads it
    assert floors.tighten(craft, OUTSIDE, math.inf) == floors.lower(craft, OUTSIDE)


def test_needed_raises_a_reroll_only_as_far_as_the_limits_ask_and_a_floor_with_nothing_to_raise_is_its_price(world):
    """`OfferFloors.needed` (#988): an offer joins the bound's model when its floor in a class is not above that class's limit. In a class of another
    shape the floor is the price, with nothing to raise; in the start's shape a reroll is raised a level at a time and stops at the first floor above the
    limits, and the level it reached is the one `tighten` reads afterwards."""
    _, _, offers, _, _, _ = world
    begin = abstraction().compress(START_ITEM)
    exact = OfferFloors(abstraction(), begin, offers, START_ITEM)
    reroll = next(p for p, e in enumerate(exact.entries) if e.kind == "reroll")
    top = exact.lower(reroll, OUTSIDE)

    floors = OfferFloors(abstraction(), begin, offers, START_ITEM)
    entry = floors.entries[reroll]
    entry.level, entry.pbar = 0, Fraction(1)
    loose = floors.lower(reroll, OUTSIDE)
    none = dict.fromkeys((OTHER, INSIDE, OUTSIDE, UNOPENED))
    assert floors.needed(reroll, {**none, OTHER: entry.cost}) == entry.cost and entry.level == 0  # another shape: its price, nothing worked out
    assert floors.needed(reroll, {**none, OTHER: entry.cost * 0.5}) is None
    assert floors.needed(reroll, {**none, OUTSIDE: loose * 0.5}) is None and entry.level == 0  # above the limit at its loosest: not needed
    assert floors.needed(reroll, {**none, OUTSIDE: math.inf}) == pytest.approx(top, rel=1e-12) and entry.level == 2  # never above: the exact chance
    assert floors.tighten(reroll, OUTSIDE, math.inf) == pytest.approx(top, rel=1e-12)  # the search reads the level the growth reached


def test_the_search_primes_the_offers_it_is_about_to_build_and_the_answer_does_not_change(world, monkeypatch):
    _, start, offers, full, _, _ = world
    calls = []
    real = CraftingProblem.prime

    def recording(self, state, positions):
        calls.append(list(positions))
        return real(self, state, positions)

    monkeypatch.setattr(CraftingProblem, "prime", recording)
    fresh = abstraction()
    envelope_result(fresh, fresh.compress(START_ITEM), offers)
    assert not calls  # seven offers: a pool of processes costs more than it saves
    monkeypatch.setattr(_envelope, "PRIME_FROM", 2)
    fresh = abstraction()
    result = envelope_result(fresh, fresh.compress(START_ITEM), offers)
    assert calls and all(len(positions) >= 2 and len(set(positions)) == len(positions) for positions in calls)
    assert all(len(positions) <= _envelope.PRIME_AHEAD for positions in calls)
    assert result.solution.values[start] == pytest.approx(full.solution.values[start], rel=TOLERANCE)


def test_the_names_of_the_first_offers_seed_the_universe_before_the_first_pass_and_do_not_begin_it_again(world, monkeypatch):
    _, start, offers, _, _, _ = world
    all_offers = pattern_offers(offers)
    real = _pattern._Universe._seed_named
    passes = []

    def gaining(self, pattern, actions):
        real(self, pattern, actions)
        return len(actions)  # the offers' names add slots, as the fossils and essences of R04 do

    real_pass = PatternBuilder._pass

    def counted(self):
        passes.append(len(self.keys))
        return real_pass(self)

    monkeypatch.setattr(_pattern._Universe, "_seed_named", gaining)
    monkeypatch.setattr(PatternBuilder, "_pass", counted)
    model = PatternBuilder(abstraction(), start).extend(all_offers)
    assert len(passes) == 1 and model.stats.universe_growth == 0


def test_the_float_kernel_of_every_fossil_set_is_below_the_exact_one_after_the_shrink():
    """The float path through the fossils (plain and Fractured sets, three starts): no chance of the lowered kernel is above the exact chance of its state (ticket #626)."""
    import test_abstraction_fossil as fossil

    checked = 0
    for make in fossil.STARTS.values():
        for names in [*fossil.SETS, *fossil.FRACTURING]:
            action = fossil.fossils(*names)
            exact_ab = fossil.abstraction(action)
            try:
                exact = exact_ab.kernel(exact_ab.compress(make()), action)
            except (NotApplicableError, OutOfScopeError):
                continue  # the set cannot be used on this start (a Fractured Fossil on a fractured item): no kernel to compare
            float_ab = fossil.abstraction(action)
            with float_ab.approximate():
                made = float_ab.kernel(float_ab.compress(make()), action)
            assert set(made) == set(exact), names
            states = list(made)
            lowered = _pattern._lowered(dict(enumerate(made.values())))
            for index, state in enumerate(states):
                assert Fraction(lowered[index]) <= exact[state], (names, state)
                checked += 1
            assert sum(lowered.values()) == 1  # the missing mass went to the sink
    assert checked > 300


def build_world_offers(offers):
    """The offers of the world without the restart: no plan can be executed before the greedy policy closes."""
    return [offer for offer in offers if offer.label != "restart"]


def test_a_refusal_after_a_build_that_was_stopped_names_the_phase_and_the_sizes(world, monkeypatch):
    _, start, offers, _, _, _ = world
    monkeypatch.setattr(_pattern, "POLL_SECONDS", 0.0)
    given = build_world_offers(offers)
    fresh = abstraction()
    stopped = pattern_lower_bound(fresh, fresh.compress(START_ITEM), given, stop=counting_stop(12))
    assert stopped.phase == "model" and not stopped.complete
    with pytest.raises(NoPolicy) as refusal:
        envelope_result(fresh, fresh.compress(START_ITEM), given, net=Net(states=12), bound=stopped)
    text = str(refusal.value)
    assert "no plan costs less than" in text
    assert "was stopped (the test net) while counting the kinds of item the crafting can reach" in text
    assert f"worked through {sum(stopped.model.expanded):,} of the {stopped.model.stats.keys:,} kinds of item it had found" in text
    assert f"counted {len(stopped.positions):,} of the {len(given):,} actions offered" in text
    fresh = abstraction()
    complete = pattern_lower_bound(fresh, fresh.compress(START_ITEM), given)
    with pytest.raises(NoPolicy) as refusal:
        envelope_result(fresh, fresh.compress(START_ITEM), given, net=Net(states=12), bound=complete)
    assert "while" not in str(refusal.value) or "cheapest possible cost was stopped" not in str(refusal.value)  # a finished count adds nothing


def test_the_net_ends_the_offers_floors_and_the_bound_is_the_cheapest_offer_at_every_key(world, floors_on):
    ab, start, offers, _, exact, _ = world
    fresh = abstraction()
    bound = pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM, stop=counting_stop(2))
    assert bound.phase == "floors" and bound.stopped == "the test net" and bound.positions == () and bound.floors is None
    assert not any(bound.model.expanded)  # every key a tip
    assert_lower_bound(bound, ab, exact)
    with pytest.raises(NoPolicy, match="while working out the cheapest possible cost of each action"):
        fresh = abstraction()
        envelope_result(fresh, fresh.compress(START_ITEM), build_world_offers(offers), net=Net(states=12), bound=bound)


def new_names_gain(monkeypatch):
    """`_seed_named` counts every action new to a universe as a slot gained, as an essence's forced mod is (R11: four of its essences joined the model
    of the bound with a mod the pool does not list, each beginning the build again, #1086); the slots themselves are seeded as they are."""
    real = _pattern._Universe._seed_named
    seen: dict[int, tuple] = {}  # id of a universe -> (the universe, its actions): the universe is held, so a later one never takes its id

    def gaining(self, pattern, actions):
        real(self, pattern, actions)
        known = seen.setdefault(id(self), (self, set()))[1]
        new = [action for action in actions if action not in known]
        known.update(new)
        return len(new)

    monkeypatch.setattr(_pattern._Universe, "_seed_named", gaining)


def count_kernels_made(monkeypatch, ab, when=lambda: True):
    """Count the kernels the abstraction `ab` and its alike twins (an erasing kernel of the bound's build, #1146) are asked to make."""
    made = []

    def counting(on):
        real = on.kernel

        def counted(state, action):
            if when():
                made.append(1)
            return real(state, action)

        monkeypatch.setattr(on, "kernel", counted)
        return on

    real_twin = ab.alike_twin
    counting(ab)
    monkeypatch.setattr(ab, "alike_twin", lambda: counting(real_twin()))
    return made


def test_a_build_that_begins_again_makes_no_kernel_twice_and_ends_on_the_model_built_at_once(world, monkeypatch):
    """#1086: an offer that joins the model adds its forced mod to the universe, and a universe that grows begins the build again (R11: four times,
    27.6 s for a model that takes 7.7 s built at once). The keys and the kernels do not depend on the universe and are kept: the build that began
    again makes no kernel it made before, and it ends on the model built at once on every offer, with as many kernels made."""
    _, start, offers, _, _, _ = world
    all_offers = pattern_offers(offers)
    new_names_gain(monkeypatch)
    once = abstraction()
    once_made = count_kernels_made(monkeypatch, once)
    whole = build_pattern_model(once, start, all_offers)
    grown_ab = abstraction()
    grown_made = count_kernels_made(monkeypatch, grown_ab)
    builder = PatternBuilder(grown_ab, start, grow=True)
    builder.extend(all_offers[:2])
    builder.extend(all_offers[2:5])
    grown = builder.extend(all_offers[5:])
    assert builder.restarts > 0  # the names of the offers that join began the build again
    assert canonical(grown) == canonical(whole)
    assert len(grown_made) == len(builder.computed) == len(once_made) == grown.stats.kernels == whole.stats.kernels


def test_the_bound_whose_build_begins_again_is_the_model_of_every_offer_and_a_lower_bound(world, floors_on, monkeypatch):
    """#1086: with the offers' floors, offers join the bound's model round after round; each brings a name, so each round begins the build again.
    The start value is the model of every offer's, no kernel is made twice, and every key stays at most the exact value of each state that has it."""
    ab, _, offers, _, exact, whole = world
    new_names_gain(monkeypatch)
    fresh = abstraction()
    building = []  # the model builder's passes: the missing mods' table (#1496) makes kernels of its own, of the bare item, which are not counted
    real_pass = PatternBuilder._pass

    def passing(self):
        building.append(self)
        try:
            return real_pass(self)
        finally:
            building.pop()

    monkeypatch.setattr(PatternBuilder, "_pass", passing)
    made = count_kernels_made(monkeypatch, fresh, when=lambda: bool(building))
    bound = pattern_lower_bound(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM)
    assert bound.complete and bound.rounds > 1 and bound.model.stats.universe_growth > 0
    assert len(made) == bound.model.stats.kernels <= whole.model.stats.kernels
    assert bound.start_value == pytest.approx(whole.start_value, rel=1e-8)
    assert_lower_bound(bound, ab, exact)


def test_through_the_envelope_entry_a_bound_that_begins_again_gives_the_full_walks_plan(world, floors_on, monkeypatch):
    """#1086 through the search's entry: every name counted as a slot gained, the bound's rounds begin the build again, keep their kernels, and
    the plan is the full walk's mean."""
    _, start, offers, full, _, _ = world
    new_names_gain(monkeypatch)
    builders = []
    real_init = PatternBuilder.__init__

    def keep(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        builders.append(self)

    monkeypatch.setattr(PatternBuilder, "__init__", keep)
    fresh = abstraction()
    building = []
    real_pass = PatternBuilder._pass

    def passing(self):
        building.append(self)
        try:
            return real_pass(self)
        finally:
            building.pop()

    monkeypatch.setattr(PatternBuilder, "_pass", passing)
    made = count_kernels_made(monkeypatch, fresh, when=lambda: bool(building))
    result = envelope_result(fresh, fresh.compress(START_ITEM), offers, item=START_ITEM)
    info = result.info["envelope"]
    assert info.exact and info.bound_stopped is None and info.bound_rounds > 1
    assert any(builder.restarts for builder in builders)
    assert len(made) == sum(len(builder.computed) for builder in builders)  # no kernel made twice by the builds (the search makes its own)
    assert result.solution.values[start] == pytest.approx(full.solution.values[start], rel=TOLERANCE)


def test_a_search_given_its_first_plan_past_a_used_net_makes_it_and_stops_there(world):
    """#1135: a round whose bound's build, nearly done, went past its share has no seconds left for its search (`Net.seconds` 0), and still
    makes its first plan (`Net.first`): the chain is not asked the used net, then the search stops at it with that plan. A net of 0 s alone
    makes no plan. Neither reads a clock that moves anything: a limit of 0 s is reached at once, and one of 10^9 s never."""
    ab, start, offers, full, exact, bound = world
    planned = envelope_result(ab, start, offers, net=Net(seconds=0.0, first=1e9), bound=bound)
    info = planned.info["envelope"]
    assert not info.exact and info.stopped.startswith("the time limit of 0 seconds") and math.isfinite(planned.solution.values[start])
    assert info.first_upper is not None and planned.solution.values[start] >= full.solution.values[start] - 1e-6
    with pytest.raises(NoPolicy, match="the time limit of 0 seconds"):
        envelope_result(ab, start, offers, net=Net(seconds=0.0), bound=bound)


def test_a_bound_whose_build_went_past_the_round_s_share_leaves_its_search_the_rest_of_its_room_for_the_first_plan(world, monkeypatch):
    """#1135, on a hand clock (no real clock is read): a round's search with a plan in hand, a share of 10 s and room for one more past it
    (`Net.late` 1), whose bound (nearly done at 10 s) completed at 15 s. Its search has 0 s of its share left, and the first plan has the
    rest of the room, 2 * 10 - 15 = 5 s (`Net.first`); the search stops after it, saying the build had gone past the share. With a bound
    that did not go past, the search has no room past its share and makes no plan."""
    ab, start, offers, full, exact, bound = world
    readings = iter([0.0])  # the call's start; every later reading is 15 s
    monkeypatch.setattr(_envelope_plan.time, "perf_counter", lambda: next(readings, 15.0))
    nets = []
    real = _envelope_plan.Search

    def watched(problem, *, net, **kwargs):
        nets.append(net)
        return real(problem, net=net, **kwargs)

    monkeypatch.setattr(_envelope_plan, "Search", watched)
    planned = envelope_result(ab, start, offers, net=Net(seconds=10.0, held=True, late=1.0), bound=dataclasses.replace(bound, late=True))
    assert (nets[0].seconds, nets[0].first) == (0.0, 5.0)
    info = planned.info["envelope"]
    assert info.stopped.endswith("had gone on past it to finish") and math.isfinite(planned.solution.values[start])
    readings = iter([0.0])
    monkeypatch.setattr(_envelope_plan.time, "perf_counter", lambda: next(readings, 15.0))
    with pytest.raises(NoPolicy, match="the time limit of 0 seconds"):
        envelope_result(ab, start, offers, net=Net(seconds=10.0, held=True, late=1.0), bound=bound)
    assert nets[-1].first is None


def test_a_key_that_keeps_needing_offers_is_given_as_many_more_as_it_holds_the_least_floors_first():
    """#1325, `_doubled`, on hand-worked numbers. Key 1 holds offers 0, 1 and 2 and needs offer 3 this round: it is given 3 - 1 = 2 more, the
    two least floors it neither holds nor is given (offers 4 and 5, 1.1 and 1.2; offer 6 has no finite floor in its class), so it holds
    6 next round, twice its 3. Key 2 holds nothing and needs nothing: it is given nothing. Which offers a key holds changes only how many
    rounds the growth takes: the floor action of a key carries the least floor of every offer it does not hold (`_floor_of`)."""
    from types import SimpleNamespace

    import numpy as np

    from crafting_system.planner._pattern_bound import _doubled

    price = {3: 1.0, 4: 1.1, 5: 1.2, 6: float("inf"), 7: 1.5}
    floors = SimpleNamespace(lower=lambda position, klass: price[position])
    holders = {0: {1}, 1: {1}, 2: {1}}
    needs = {3: [1]}
    found = [(1.0, 3)]
    added = _doubled(needs, holders, {9: np.array([1, 2])}, [3, 4, 5, 6, 7], floors, found)
    assert added == 2
    assert {p: list(keys) for p, keys in needs.items()} == {3: [1], 4: [1], 5: [1]}
    assert sorted(found) == [(1.0, 3), (1.1, 4), (1.2, 5)]
    assert _doubled({3: [1]}, {}, {9: np.array([1, 2])}, [3, 4], floors, []) == 0  # nothing held at some keys only: nothing to double


def test_a_class_of_another_shape_found_binding_builds_its_offers_at_as_many_more_binding_keys_as_already_hold_them():
    """#1325, `_spread`, on hand-worked numbers. The policy reaches binding key 1 of a class of another shape (OTHER); keys 2 to 5 of that class
    are binding too, the policy does not reach them, and keys 1 and 2 already hold offers built at some keys only: 2 more keys are added, the
    two most binding (least ratio of the floor action to the model's best: key 5, 0.1, then key 3, 0.3). Key 6, of the start's shape (INSIDE),
    is not one of them (those keys count whether reached or not). With no offer held at some keys only, nothing is added: the first round
    builds at the reached keys alone, and the keys double from there."""
    from collections import defaultdict
    from types import SimpleNamespace

    from crafting_system.planner._offer_floor import INSIDE, OTHER
    from crafting_system.planner._pattern_bound import _spread

    klass = {1: OTHER, 2: OTHER, 3: OTHER, 4: OTHER, 5: OTHER, 6: INSIDE}
    model = SimpleNamespace(
        keys=[SimpleNamespace(flags=k, fractured=False, status=None, held=defaultdict(lambda: None)) for k in range(7)], expanded=[True] * 7
    )
    floors = SimpleNamespace(klass=lambda flags, *_: klass.get(flags, OTHER))
    ratio = {2: 0.5, 3: 0.3, 4: 0.9, 5: 0.1, 6: 0.05}.get
    by_class = {OTHER: [1]}
    _spread(by_class, [2, 3, 4, 5, 6], ratio, model, floors, {10: {1}, 11: {1, 2}})
    assert by_class == {OTHER: [1, 5, 3]}
    alone = {OTHER: [1]}
    _spread(alone, [2, 3, 4, 5, 6], ratio, model, floors, {})
    assert alone == {OTHER: [1]}


def test_the_floor_action_of_a_key_is_the_least_floor_of_the_offers_it_does_not_hold():
    """#1325, `_floor_of`, on hand-worked numbers. Offers 0 to 3, floors 5, 1, 2 and 3; offer 0 is outside the model, offers 1 and 2 are held at
    some keys only (1 at key 7, 2 at keys 7 and 8), offer 3 is held everywhere (not in `outside`, not in `holders`). Key 7 holds 1 and 2: its
    floor action is offer 0's 5. Key 8 holds 2 only: offer 1's 1. Key 9 holds neither: offer 1's 1. A tip (not expanded) carries the least floor
    of every offer, 1; a key with no floor below infinity has no floor action."""
    from collections import defaultdict
    from types import SimpleNamespace

    from crafting_system.planner._pattern_bound import _floor_of

    floor_of = {0: 5.0, 1: 1.0, 2: 2.0, 3: 3.0}
    floors = SimpleNamespace(
        classes=(0,), klass=lambda *_: 0, lower=lambda position, klass: floor_of[position],
        floor=lambda names, klass: min((floor_of[p] for p in names), default=float("inf")),
    )  # fmt: skip
    key = SimpleNamespace(flags=0, fractured=False, status=None, held=defaultdict(lambda: None))
    floor = _floor_of(floors, [0], [None] * 4, {1: {7}, 2: {7, 8}})
    assert [floor(k, key, True) for k in (7, 8, 9)] == [5.0, 1.0, 1.0]
    assert floor(7, key, False) == 1.0
    assert _floor_of(floors, [], [None] * 4, {1: {7}})(7, key, True) is None  # nothing outside, and it holds the one held at some keys only
