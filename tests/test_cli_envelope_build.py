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
from fractions import Fraction
from types import SimpleNamespace

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
from crafting_system.actions import NotApplicableError, OutOfScopeError
from crafting_system.cli._offer_floor import INSIDE, OTHER, OUTSIDE, FloorsStopped, OfferFloors
from crafting_system.cli._offers import BuyStartItem
from crafting_system.solver import ConvergenceError
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
    clock = SimpleNamespace(now=10.0)  # a clock set by hand: ten seconds have passed since the build began (tests/test_no_timing.py)
    clock.perf_counter = lambda: clock.now
    monkeypatch.setattr(_envelope_plan, "time", clock)
    assert build_stop(Net(seconds=100.0), 0.0)() is None  # 10 s of 100: under half
    assert "time limit" in build_stop(Net(seconds=15.0), 0.0)()  # 10 s of 15: over half
    monkeypatch.setattr(_envelope_plan, "resident_mb", lambda: 5000.0)  # the process holds 5 GB (a runner's /proc, or none on this PC)
    assert "5,000 MB" in build_stop(Net(memory_mb=1000.0), 0.0)()
    assert build_stop(Net(memory_mb=10_000.0), 0.0)() is None


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
    monkeypatch.setattr(_pattern_bound, "_binding", lambda *args, **kwargs: ([], {}))
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
        inner.setattr(_pattern_bound, "_binding", lambda *args, **kwargs: ([], {}))  # no growth: the questions of the first round alone
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


def test_a_stopped_plan_the_solver_cannot_certify_is_a_refusal_with_the_lower_bound(world, monkeypatch):
    ab, start, offers, _, _, _ = world

    def uncertified(self):
        raise ConvergenceError("the policy iteration on 533,666 states certifies only a relative bound of 2.07e-06", 2.07e-06)

    monkeypatch.setattr(_envelope.Search, "upper_value", uncertified)
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
        klass = floors.klass(state.flags, state.fractured, state.status)
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
    assert floors.klass(start.flags, start.fractured, start.status) == OUTSIDE


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
