"""The certificate of `cli/_bound_prune.py` on made-up offers, solver and bounds, with every decision worked out by hand (ticket #413).

The measurement week (#399) found 147 of the 206 mutants of `_bound_prune.py` alive: the light suite proves the pieces and the
exactness on a real world, and the choices in between (which offer joins the set, when a round is the last, what each fallback
says) are left to routes. Rebuild step 6 changes exactly this code. Here `solve_pruned` runs on stub actions with the solver and the
two bounds replaced by tables, so each round's numbers are the ones written in the test:

* the tables give each reroll the loose bound `reach_bound` has at level 1 and the exact chance at level 2;
* the stub solver returns the values the scenario says, for the set of offers it is asked about;
* rho is the least cost / pbar, worked out here, and the test T = J (1 + error bound) + 1e-9 that decides who is proved needless.

World W (SMALL_START = 2, PER_ROUND = 2 where the module's own 8 and 16 would hide the choice), the goal one leaf `m1`:

    label  kind     cost  pbar at level 1 (loose)  pbar at level 2 (exact)
    restart restart  10   0                          .
    X       craft     4   0 (adds a mod of no leaf)  .
    a       reroll    1   1/2                        1/4         ratios 1, 2, 4
    b       reroll    2   1/2                        1/2         ratios 2, 4, 4
    c       reroll    3   1/3                        1/6         ratios 3, 9, 18
    d       reroll    5   1/2                        1/2         ratios 5, 10, 10
    e       reroll    6   1                          1           ratios 6, 6, 6

The least ratio is 4 (a and b at their exact bound), so rho = 4 (1 - 1e-12) and the first set S is restart, X, a and b.
"""

import dataclasses
import math
from fractions import Fraction
from types import SimpleNamespace

import pytest

from crafting_system import parallel
from crafting_system.abstraction import AtLeast, Goal, Status, Wanted
from crafting_system.actions import ActionError
from crafting_system.cli import _bound_prune as bp
from crafting_system.cli import _plan
from crafting_system.cli._bound_prune import (
    CRAFT,
    REFUSED,
    REROLL,
    RESTART_KIND,
    TERMINAL,
    _Entry,
    _finite,
    _kind_of,
    _largest,
    _lower,
    _raised,
    best_first_rho,
    goal_set,
    merge_twins,
    necessary_leaves,
    solve_pruned,
    starting_offers,
)
from crafting_system.cli._offers import BuyStartItem, Offer, PricedOffer
from crafting_system.solver import ConvergenceError

ZERO, ONE = Fraction(0), Fraction(1)
RHO = 4.0 * (1 - bp.SLACK)


def leaf(*mods):
    return Wanted(frozenset(mods))


# --- the small pieces ---------------------------------------------------------------------------------------------------


def stub_entry(index, cost, kind=REROLL, pbar=ONE, level=0):
    return _Entry(index, SimpleNamespace(cost=cost, label=f"x{index}"), kind, level, pbar)


def test_the_ratio_of_an_entry_is_its_cost_over_its_pbar_and_infinite_for_a_pbar_of_zero():
    assert stub_entry(0, 3.0, pbar=Fraction(1, 2)).ratio == 6.0
    assert stub_entry(0, 3.0, pbar=Fraction(1, 4)).ratio == 12.0
    assert stub_entry(0, 3.0).ratio == 3.0
    assert stub_entry(0, 3.0, pbar=ZERO).ratio == math.inf


def test_the_lower_bound_of_using_an_offer_is_its_cost_plus_rho_for_the_chance_of_staying_off_the_target():
    assert _lower(stub_entry(0, 3.0, pbar=Fraction(1, 3)), 4.0) == pytest.approx(3.0 + (2 / 3) * 4.0, rel=1e-15)
    assert _lower(stub_entry(0, 3.0), 4.0) == 3.0  # pbar 1: it may land on the target for certain
    assert _lower(stub_entry(0, 3.0, pbar=ZERO), 4.0) == 7.0


def test_finite_is_neither_infinity_nor_not_a_number():
    assert _finite(0.0) and _finite(12.5) and not _finite(math.inf) and not _finite(math.nan)


def test_the_largest_value_is_over_the_finite_states_that_are_not_goals():
    solution = SimpleNamespace(values={"a": 3.0, "goal": 99.0, "c": math.inf, "d": math.nan, "e": 7.5})
    ab = SimpleNamespace(is_goal=lambda s: s == "goal")

    assert _largest(solution, ab) == 7.5
    assert _largest(SimpleNamespace(values={"goal": 5.0, "x": math.inf}), ab) == 0.0


def test_necessary_leaves_are_those_under_the_requirements_or_under_all_of_n_nodes():
    a, b, c, d, e, f = (leaf(name) for name in "abcdef")
    goal = Goal((a, AtLeast(2, (b, c)), AtLeast(2, (d, AtLeast(1, (e, f))))))

    assert necessary_leaves(goal) == (0, 1, 2, 3)  # a, b, c, d; e and f sit under an AtLeast(1 of 2)


def test_leaves_are_counted_past_the_ones_that_are_not_necessary():
    a, b, c, d = (leaf(name) for name in "abcd")

    assert necessary_leaves(Goal((AtLeast(1, (a, b)), c, d))) == (2, 3)  # c and d are the third and fourth leaves
    assert necessary_leaves(Goal((AtLeast(1, (AtLeast(2, (a, b)), c)), d))) == (3,)
    assert necessary_leaves(Goal((AtLeast(2, (a, AtLeast(1, (b, c)))), d))) == (0, 3)


def test_goal_set_leaves_out_the_leaves_passing_at_the_start_and_the_ones_a_bench_craft_finishes_unless_nothing_would_remain():
    goal = Goal((leaf("a"), leaf("b"), leaf("c")))
    start = SimpleNamespace(status=(Status.PASSING, Status.ABSENT, Status.BELOW))

    assert goal_set(goal, start, frozenset()) == (1, 2)
    assert goal_set(goal, start, frozenset({"b"})) == (2,)
    assert goal_set(goal, start, frozenset({"b", "c"})) == (1, 2)  # all would go: keep them all
    assert goal_set(goal, start, frozenset({"a"})) == (1, 2)  # a passes already


def twin_offer(label, cost, key):
    action = SimpleNamespace(twin_key=lambda data, item, key=key: key)
    return PricedOffer(Offer(label, action, {}), cost, ())


def test_twins_keep_the_cheapest_and_the_earliest_on_a_tie():
    restart = PricedOffer(Offer("restart", BuyStartItem(None), {}), 1.0, ())
    offers = [twin_offer("p", 3.0, "K"), restart, twin_offer("q", 3.0, "K"), twin_offer("r", 2.0, "K"), twin_offer("s", 5.0, None), twin_offer("t", 1.0, None), twin_offer("u", 9.0, "L")]

    kept, twins = merge_twins(None, None, offers)

    assert [o.label for o in kept] == ["restart", "r", "s", "t", "u"]  # p, q dropped; s and t have no key: both stay
    assert twins == [("q", "p"), ("p", "r")]  # (dropped, kept): q equals p in cost and loses by coming later; r is cheaper than p


def test_twins_of_equal_cost_keep_the_first():
    kept, twins = merge_twins(None, None, [twin_offer("p", 3.0, "K"), twin_offer("q", 3.0, "K")])

    assert [o.label for o in kept] == ["p"] and twins == [("q", "p")]


def stub_action(name, *, junk=False, item_state=False, named=None, draws=True, fractures=False, keeps_crafted=False, needs_crafted=False, twin=None):
    return SimpleNamespace(
        name=name,
        reads=lambda data: SimpleNamespace(item_state=item_state, junk=junk, needs_crafted=needs_crafted),
        adds=lambda data, item: SimpleNamespace(fractures=fractures, draws=draws, named=named, keeps_crafted=keeps_crafted),
        twin_key=lambda data, item: twin,
    )


def priced_of(action, cost=1.0, label=None):
    return PricedOffer(Offer(label or action.name, action, {}), cost, ())


def test_the_kind_of_an_offer_comes_from_what_its_action_declares():
    restart = PricedOffer(Offer("restart", BuyStartItem(None), {}), 1.0, ())

    assert _kind_of(None, None, restart) == (RESTART_KIND, frozenset())
    assert _kind_of(None, None, priced_of(stub_action("s", item_state=True))) == (TERMINAL, frozenset())
    assert _kind_of(None, None, priced_of(stub_action("s", item_state=True, junk=True))) == (TERMINAL, frozenset())
    assert _kind_of(None, None, priced_of(stub_action("r"))) == (REROLL, frozenset())
    craft = stub_action("c", junk=True, draws=False, named=frozenset({"m1", "m2"}))
    assert _kind_of(None, None, priced_of(craft)) == (CRAFT, frozenset({"m1", "m2"}))
    assert _kind_of(None, None, priced_of(stub_action("c", junk=True, draws=False, named=frozenset()))) == (CRAFT, frozenset())


@pytest.mark.parametrize("fields", [{"fractures": True}, {"draws": True}, {"named": None}])
def test_a_junk_reading_action_is_a_craft_only_when_it_adds_named_mods_without_drawing_or_fracturing(fields):
    base = {"junk": True, "draws": False, "named": frozenset({"m"})}

    assert _kind_of(None, None, priced_of(stub_action("c", **{**base, **fields}))) == (TERMINAL, frozenset())
    assert _kind_of(None, None, priced_of(stub_action("c", **base)))[0] == CRAFT


# --- best_first_rho -----------------------------------------------------------------------------------------------------


def ladder(table):
    """A `raise_level` that gives entry i the loose bound table[i][0] at level 1 and the exact chance table[i][1] at level 2."""
    asked = []

    def raise_level(entry, level):
        asked.append((entry.index, level))
        entry.level = level
        entry.pbar = table[entry.index][0] if level == 1 else table[entry.index][1]

    return asked, raise_level


def test_the_best_first_rho_raises_each_reroll_one_level_at_a_time_until_a_level_two_reroll_is_the_least():
    table = {0: (Fraction(1, 2), Fraction(1, 4)), 1: (Fraction(1, 2), Fraction(1, 2)), 2: (Fraction(1, 3), Fraction(1, 6))}
    entries = [stub_entry(0, 1.0), stub_entry(1, 2.0), stub_entry(2, 3.0)]
    asked, raise_level = ladder(table)

    rho = best_first_rho(entries, raise_level)

    assert asked == [(0, 1), (0, 2), (1, 1), (2, 1)]  # ratios 1 -> 2 -> 4 (a, level 2), b: 2 -> 4, c: 3 -> 9; then a at level 2 is the least
    assert rho == 4.0 * (1 - bp.SLACK)


def test_the_best_first_rho_stops_at_a_craft_and_skips_a_refused_offer():
    entries = [stub_entry(0, 1.0, kind=REFUSED), stub_entry(1, 2.0, kind=CRAFT), stub_entry(2, 3.0)]
    asked, raise_level = ladder({})

    assert best_first_rho(entries, raise_level) == 2.0 * (1 - bp.SLACK)  # the refused 1.0 is passed over
    assert asked == []


def test_the_best_first_rho_of_offers_that_can_never_reach_the_target_is_huge_not_infinite():
    entries = [stub_entry(0, 1.0, kind=RESTART_KIND, pbar=ZERO), stub_entry(1, 2.0, kind=CRAFT, pbar=ZERO)]

    assert best_first_rho(entries, ladder({})[1]) == bp.HUGE * (1 - bp.SLACK)


def test_the_best_first_rho_is_zero_when_every_offer_is_refused():
    assert best_first_rho([stub_entry(0, 1.0, kind=REFUSED)], ladder({})[1]) == 0.0


def test_the_best_first_rho_stops_at_a_reroll_already_at_level_two():
    entries = [stub_entry(0, 1.0, level=2, pbar=Fraction(1, 2)), stub_entry(1, 3.0, level=1, pbar=Fraction(1, 1))]
    asked, raise_level = ladder({})

    assert best_first_rho(entries, raise_level) == 2.0 * (1 - bp.SLACK) and asked == []


# --- _raised -------------------------------------------------------------------------------------------------------------


@pytest.fixture
def bounds(monkeypatch):
    """`keeps_shape` and `reach_bound` replaced by tables on the action's name; `calls` records the questions asked."""
    state = SimpleNamespace(refused=set(), moves=set(), loose={}, exact={}, calls=[])

    def keeps_shape(abstraction, bare, action):
        if action.name in state.refused:
            raise ActionError("refused")
        return action.name not in state.moves

    def reach_bound(abstraction, bare, action, chosen, exact=False):
        state.calls.append((action.name, exact))
        return (state.exact if exact else state.loose).get(action.name)

    monkeypatch.setattr(bp, "keeps_shape", keeps_shape)
    monkeypatch.setattr(bp, "reach_bound", reach_bound)
    return state


AB = SimpleNamespace(data=None)


def raised(action, kind=REROLL, level=0, pbar=ONE, target=1, chosen=(0,)):
    return _raised(AB, "bare", None, chosen, action, kind, level, pbar, target)


def test_an_offer_the_game_refuses_on_the_bare_item_is_refused_at_level_zero(bounds):
    bounds.refused.add("r")

    assert raised(stub_action("r")) == (REFUSED, ONE, 0)
    assert bounds.calls == []


@pytest.mark.parametrize(
    "fields,moves",
    [({}, True), ({"fractures": True}, False), ({"keeps_crafted": True}, False), ({"needs_crafted": True}, False)],
)
def test_a_reroll_that_moves_the_shape_fractures_or_keeps_or_needs_crafted_mods_is_terminal(bounds, fields, moves):
    if moves:
        bounds.moves.add("r")
    bounds.loose["r"] = Fraction(1, 2)

    assert raised(stub_action("r", **fields)) == (TERMINAL, ONE, 0)
    assert bounds.calls == []


def test_a_reroll_with_no_goal_leaf_to_reach_has_pbar_zero_and_asks_no_bound(bounds):
    assert raised(stub_action("r"), chosen=()) == (REROLL, ZERO, 1)
    assert raised(stub_action("r"), chosen=(), target=2) == (REROLL, ZERO, 2)
    assert bounds.calls == []


def test_a_reroll_without_a_bound_is_terminal_at_level_one(bounds):
    assert raised(stub_action("r")) == (TERMINAL, ONE, 1)
    assert bounds.calls == [("r", False)]


def test_level_one_is_the_loose_bound_and_level_two_the_exact_chance_when_it_is_lower(bounds):
    bounds.loose["r"], bounds.exact["r"] = Fraction(1, 2), Fraction(1, 4)

    assert raised(stub_action("r")) == (REROLL, Fraction(1, 2), 1)
    assert bounds.calls == [("r", False)]
    bounds.calls.clear()
    assert raised(stub_action("r"), target=2) == (REROLL, Fraction(1, 4), 2)
    assert bounds.calls == [("r", False), ("r", True)]


def test_the_exact_chance_replaces_the_loose_bound_only_when_it_is_lower(bounds):
    bounds.loose["r"], bounds.exact["r"] = Fraction(1, 2), Fraction(1, 2)
    assert raised(stub_action("r"), target=2) == (REROLL, Fraction(1, 2), 2)
    bounds.exact["r"] = Fraction(3, 4)
    assert raised(stub_action("r"), target=2) == (REROLL, Fraction(1, 2), 2)
    bounds.exact["r"] = None
    assert raised(stub_action("r"), target=2) == (REROLL, Fraction(1, 2), 2)


def test_an_offer_already_at_level_one_goes_straight_to_the_exact_chance(bounds):
    bounds.exact["r"] = Fraction(1, 5)

    assert raised(stub_action("r"), level=1, pbar=Fraction(1, 2), target=2) == (REROLL, Fraction(1, 5), 2)
    assert bounds.calls == [("r", True)]


def test_an_offer_already_at_the_asked_level_or_not_a_reroll_is_left_as_it_is(bounds):
    bounds.exact["r"] = Fraction(1, 5)

    assert raised(stub_action("r"), level=2, pbar=Fraction(1, 2), target=2) == (REROLL, Fraction(1, 2), 2)
    assert raised(stub_action("r"), level=1, pbar=Fraction(1, 2), target=1) == (REROLL, Fraction(1, 2), 1)
    assert raised(stub_action("r"), kind=TERMINAL, level=1, pbar=ONE, target=2) == (TERMINAL, ONE, 1)
    assert bounds.calls == []


def test_the_exact_chance_of_a_pool_with_no_goal_leaf_is_zero(bounds):
    assert raised(stub_action("r"), level=1, pbar=Fraction(1, 2), target=2, chosen=()) == (REROLL, ZERO, 2)


# --- the rounds ---------------------------------------------------------------------------------------------------------


class State:
    """A made-up state: hashable, with the fields the module reads."""

    def __init__(self, name, flags="F", fractured=()):
        self.name, self.flags, self.fractured = name, flags, fractured

    def __repr__(self):
        return self.name


@dataclasses.dataclass(frozen=True)
class Start:
    status: tuple = (Status.ABSENT,)
    flags: str = "F"
    fractured: tuple = ()
    slots: tuple = ("junk",)


START = Start()
GOAL = State("goal")
LIVE = State("live")  # a reachable state other than the start


class Harness:
    """What the scenario decides: the solver's answer for a set of offers, the bounds of each reroll, which offers are what."""

    def __init__(self, monkeypatch):
        self.monkeypatch = monkeypatch
        self.answers = {}  # frozenset of labels -> (values by state, error bound) or an exception
        self.default = None
        self.asked_sets = []
        self.pool_made = []
        self.pool_mapped = []

    def solver(self, model, starts):
        labels = frozenset(o.label for o in model.offers)
        self.asked_sets.append(labels)
        answer = self.answers.get(labels, self.default)
        if isinstance(answer, Exception):
            raise answer
        values, error_bound = answer(labels) if callable(answer) else answer
        return SimpleNamespace(values=dict(values), policy={}, error_bound=error_bound)


def values_of(j, *, extra=None, error_bound=0.0, start=None):
    """Values with J = j at the live state, the start at j / 2 and the goal at 0."""
    values = {START: j / 2, LIVE: j, GOAL: 0.0, **(extra or {})}
    return values, error_bound


def world(monkeypatch, *, refused=(), moves=(), loose=None, exact=None, small_start=2, per_round=2, extra_offers=()):
    """The stub world W of the module text; returns (harness, bounds, offers)."""
    harness = Harness(monkeypatch)
    state = SimpleNamespace(calls=[], chosen=[])
    loose = {"a": Fraction(1, 2), "b": Fraction(1, 2), "c": Fraction(1, 3), "d": Fraction(1, 2), "e": ONE, **(loose or {})}
    exact = {"a": Fraction(1, 4), "b": Fraction(1, 2), "c": Fraction(1, 6), "d": Fraction(1, 2), "e": ONE, **(exact or {})}

    def keeps_shape(abstraction, bare, action):
        if action.name in refused:
            raise ActionError("refused")
        return action.name not in moves

    def reach_bound(abstraction, bare, action, chosen, exact_chance=False, **kw):
        exact_asked = kw.get("exact", exact_chance)
        state.calls.append((action.name, exact_asked))
        state.chosen.append(chosen)
        return (exact if exact_asked else loose)[action.name]

    monkeypatch.setattr(bp, "keeps_shape", keeps_shape)
    monkeypatch.setattr(bp, "reach_bound", reach_bound)
    monkeypatch.setattr(bp, "solve", harness.solver)
    monkeypatch.setattr(_plan, "_Model", lambda abstraction, start, offers, cache=None: SimpleNamespace(offers=list(offers)))
    monkeypatch.setattr(bp, "SMALL_START", small_start)
    monkeypatch.setattr(bp, "PER_ROUND", per_round)
    offers = [
        PricedOffer(Offer("restart", BuyStartItem(None), {}), 10.0, ()),
        priced_of(stub_action("X", junk=True, draws=False, named=frozenset({"zz"})), 4.0),
        *(priced_of(stub_action(name), cost) for name, cost in (("a", 1.0), ("b", 2.0), ("c", 3.0), ("d", 5.0), ("e", 6.0))),
        *extra_offers,
    ]
    return harness, state, offers


AB_WORLD = SimpleNamespace(data=None, goal=Goal((leaf("m1"),)), is_goal=lambda s: s is GOAL)


def run(offers, **options):
    return solve_pruned(AB_WORLD, START, offers, None, min_offers=1, **options)


def labels(pruned_offers):
    return {o.label for o in pruned_offers}


S1 = frozenset({"restart", "X", "a", "b"})


def test_when_every_offer_outside_the_set_costs_more_than_the_values_the_certificate_closes_in_one_round(monkeypatch):
    harness, state, offers = world(monkeypatch)
    harness.default = values_of(5.5)  # T = 5.5 (1 + 1e-9) + 1e-9: c (5.67 > T), d (5 + (1/2) 4 = 7 > T once raised) and e (6) are proved needless

    found = run(offers)

    assert found.rho == RHO and found.j_max == 5.5 and found.rounds == 1 and found.fell_back is False and found.why == ""
    assert labels(found.used) == S1 and harness.asked_sets == [S1]
    assert found.bounded == ("c", "d", "e") and found.inapplicable == () and found.twins == ()
    assert found.solution.values[LIVE] == 5.5
    # the bounds asked, in order: the best-first search raised a (loose, exact), b and c (loose); the test raised d (loose)
    assert state.calls == [("a", False), ("a", True), ("b", False), ("c", False), ("d", False)]


def test_each_bound_is_raised_one_level_at_a_time_and_only_when_the_test_needs_it(monkeypatch):
    harness, _, offers = world(monkeypatch)
    harness.default = values_of(6.5)
    harness.answers[S1 | {"c", "e"}] = values_of(4.5)
    raised_calls = []
    real = bp._raised
    monkeypatch.setattr(bp, "_raised", lambda ab, bare, item, chosen, action, kind, level, pbar, target: raised_calls.append((action.name, level, target)) or real(ab, bare, item, chosen, action, kind, level, pbar, target))

    run(offers)

    assert raised_calls == [
        ("a", 0, 1), ("a", 1, 2), ("b", 0, 1), ("c", 0, 1),  # best first: the search for rho
        ("c", 1, 2), ("d", 0, 1), ("e", 0, 1), ("e", 1, 2),  # round 1: c to its exact chance, d and e one level and two
    ]  # (round 2: d's raised bound 7 is over T = 4.5: nothing to raise)


def test_an_offer_that_cannot_be_proved_needless_joins_the_set_and_the_next_round_solves_again(monkeypatch):
    harness, state, offers = world(monkeypatch)
    harness.default = values_of(6.5)
    harness.answers[S1] = values_of(6.5)
    harness.answers[S1 | {"c", "e"}] = values_of(4.5)  # e (6.0) and c (6.33 at its exact chance) fail the first test; d (7) is proved

    found = run(offers)

    assert harness.asked_sets == [S1, S1 | {"c", "e"}]
    assert found.rounds == 2 and found.bounded == ("d",) and found.j_max == 4.5 and labels(found.used) == S1 | {"c", "e"}
    assert ("c", True) in state.calls and ("e", True) in state.calls  # both were brought to the exact chance before they were let in


def test_only_the_per_round_cheapest_failing_offers_join_unless_it_is_the_last_round(monkeypatch):
    harness, _, offers = world(monkeypatch, per_round=1)
    harness.default = values_of(4.5)
    harness.answers[S1] = values_of(6.5)

    found = run(offers, rounds=4)

    assert harness.asked_sets[:2] == [S1, S1 | {"e"}]  # one offer joins, the one of least lower bound: e (6.0) before c (6.33)
    assert found.rounds >= 2

    harness, _, offers = world(monkeypatch, per_round=1)
    harness.default = values_of(4.5)
    harness.answers[S1] = values_of(6.5)
    found = run(offers, rounds=2)

    assert harness.asked_sets[:2] == [S1, S1 | {"c", "e"}]  # the last round (rounds - 1) takes all that fail


def test_rounds_run_out_when_the_certificate_does_not_close(monkeypatch):
    harness, _, offers = world(monkeypatch, per_round=1)
    harness.default = values_of(6.5)  # every set leaves some offer failing

    found = run(offers, rounds=1)

    assert found.fell_back is True and found.why == "the certificate did not close within 1 rounds" and found.rounds == 2  # one solve and the fallback solve
    assert harness.asked_sets[-1] == frozenset(o.label for o in offers)  # the fallback solves everything left after the twins
    assert found.bounded == () and found.rho == 0.0 and labels(found.used) == labels(offers)


def test_the_first_set_holds_restart_the_crafts_and_the_rerolls_of_least_ratio(monkeypatch):
    harness, _, offers = world(monkeypatch)
    harness.default = values_of(1.0)

    found = run(offers)

    assert harness.asked_sets[0] == S1
    assert [o.label for o in found.used] == ["restart", "X", "a", "b"]  # in the order of the offers
    monkeypatch.setattr(bp, "SMALL_START", 3)
    harness.asked_sets.clear()
    assert run(offers).used and harness.asked_sets[0] == S1 | {"d"}  # after a and b (ratio 4) comes d (5), not e (6) or c (9)


def test_the_test_value_is_the_largest_finite_value_times_one_plus_the_error_bound_plus_a_hair(monkeypatch):
    # e's lower bound is 6 (1 - 1e-12) whatever its level. It fails the test when T is above that, so with one round it ends in the fallback.
    def ends_in_the_fallback(j, error_bound, extra=None):
        harness, _, offers = world(monkeypatch)
        harness.default = values_of(j, error_bound=error_bound, extra=extra)
        found = run(offers, rounds=1)
        return found.fell_back

    # no error bound: the floor 1e-9 applies, T = J (1 + 1e-9) + 1e-9; J = 5.999999994 puts T at 6.000000001, above e's 5.999999999994
    assert ends_in_the_fallback(5.999999994, 0.0) is True
    assert ends_in_the_fallback(5.999999992, 0.0) is False  # T = 5.999999999: now below it, so e is proved needless too
    assert ends_in_the_fallback(5.999999994, 0.0, extra={State("small"): 5.0}) is True  # J is the largest, not the last or the first
    # an error bound of 20% widens T by that much: 5.4 * 1.2 = 6.48 is above 6 (and 6.33), and without it 5.4 is below
    assert ends_in_the_fallback(5.4, 0.2) is True
    assert ends_in_the_fallback(5.4, 0.0) is False
    # the floor wins over a smaller bound
    assert ends_in_the_fallback(5.999999994, 1e-12) is True


def test_an_infinite_value_among_the_reachable_states_brings_in_the_cheapest_offers_whatever_they_bound(monkeypatch):
    harness, _, offers = world(monkeypatch)
    harness.default = values_of(4.5)
    harness.answers[S1] = values_of(4.5, extra={State("dead"): math.inf})

    found = run(offers)

    assert harness.asked_sets[:2] == [S1, S1 | {"c", "d"}]  # c (cost 3) and d (cost 5) of the offers outside, cheapest first, PER_ROUND = 2
    assert found.rounds == 2 and labels(found.used) == S1 | {"c", "d"}


def test_an_infinite_value_with_nothing_left_to_add_is_a_dead_state_of_the_full_model_too(monkeypatch):
    harness, _, offers = world(monkeypatch, small_start=5)
    harness.default = values_of(4.5, extra={State("dead"): math.inf})

    found = run(offers)

    assert found.fell_back and found.why == "a reachable state has no proper policy" and found.rounds == 2


def test_an_offer_that_moves_the_item_to_another_shape_drops_the_bound(monkeypatch):
    for moved in (State("moved", flags="G"), State("moved", fractured=("m",))):
        harness, _, offers = world(monkeypatch)
        harness.default = values_of(5.5, extra={moved: 1.0})

        found = run(offers)

        assert found.fell_back and found.why == "an offer moves the item to another shape (flags or fractured mods)" and found.rounds == 2
        assert found.bounded == () and found.rho == 0.0


def test_a_goal_state_of_another_shape_is_no_reason_to_drop_the_bound(monkeypatch):
    harness, _, offers = world(monkeypatch)
    other_goal = State("goal", flags="G")
    harness.default = ({START: 2.75, LIVE: 5.5, other_goal: 0.0}, 0.0)
    ab = SimpleNamespace(data=None, goal=AB_WORLD.goal, is_goal=lambda s: getattr(s, "name", None) == "goal")

    found = solve_pruned(ab, START, offers, None, min_offers=1)

    assert not found.fell_back and found.rounds == 1


def test_a_value_that_cannot_be_certified_drops_the_bound(monkeypatch):
    harness, _, offers = world(monkeypatch)
    harness.default = values_of(5.5, error_bound=math.inf)

    found = run(offers)

    assert found.fell_back and found.why == "the solver could not certify its values"
    harness.default = values_of(5.5, error_bound=math.nan)
    assert run(offers).why == "the solver could not certify its values"


def test_a_solve_that_does_not_converge_drops_the_bound_and_says_why(monkeypatch):
    harness, _, offers = world(monkeypatch)
    harness.default = values_of(5.5)
    harness.answers[S1] = ConvergenceError("no luck", 0.5)

    found = run(offers)

    assert found.fell_back and found.why.startswith("the solver could not converge on the reduced model (") and "no luck" in found.why
    assert found.rounds == 2 and found.twins == () and found.solution.values[LIVE] == 5.5


def test_an_offer_the_game_refuses_on_the_bare_item_is_set_aside_and_named(monkeypatch):
    harness, _, offers = world(monkeypatch, refused={"a"})
    harness.default = values_of(1.0)

    found = run(offers)

    assert found.inapplicable == ("a",) and "a" not in found.bounded and "a" not in labels(found.used)
    assert found.rho == RHO  # b at its exact chance, 2 / (1/2)


def test_with_nothing_to_reach_rho_is_zero_and_no_bound_is_asked(monkeypatch):
    harness, state, offers = world(monkeypatch)
    harness.default = values_of(1.5)
    passing = Start(status=(Status.PASSING,))

    found = solve_pruned(AB_WORLD, passing, offers, None, min_offers=1)

    assert found.rho == 0.0 and state.calls == []  # a pool with no leaf to reach gives pbar 0 without asking reach_bound
    assert found.rounds == 1 and found.fell_back is False


def test_with_no_restart_craft_or_reroll_the_set_starts_from_the_cheapest_offers(monkeypatch):
    harness, _, _ = world(monkeypatch)
    harness.default = values_of(1.0)
    offers = [priced_of(stub_action(name, item_state=True), cost) for name, cost in (("p", 9.0), ("q", 3.0), ("r", 5.0), ("s", 3.0))]

    found = run(offers)

    assert harness.asked_sets[0] == {"q", "s"}  # the two cheapest, the earlier first on a tie
    assert labels(found.used) == {"q", "s"} and not found.fell_back


def test_few_offers_are_all_kept_and_solved_once(monkeypatch):
    harness, _, offers = world(monkeypatch)
    harness.default = values_of(8.0)

    found = solve_pruned(AB_WORLD, START, offers, None, min_offers=len(offers) + 1)

    assert found.fell_back and found.why == f"fewer than {len(offers) + 1} offers: nothing to gain"
    assert found.rounds == 1 and found.rho == 0.0 and found.j_max == 8.0 and found.used == tuple(offers) and found.bounded == ()
    assert harness.asked_sets == [labels(offers)]
    equal = solve_pruned(AB_WORLD, START, offers, None, min_offers=len(offers))
    assert not equal.why.startswith("fewer")  # exactly the minimum is enough to try


def test_the_starting_offers_are_the_first_set_of_the_run(monkeypatch):
    harness, _, offers = world(monkeypatch)
    harness.default = values_of(8.0)

    first = starting_offers(AB_WORLD, START, offers, None, min_offers=1)

    assert [o.label for o in first] == ["restart", "X", "a", "b"] and harness.asked_sets == []  # nothing is solved
    assert starting_offers(AB_WORLD, START, offers, None, min_offers=len(offers) + 1) == offers
    assert starting_offers(AB_WORLD, START, offers, None, min_offers=len(offers)) != offers  # at the minimum it prunes


def test_twins_are_merged_before_anything_and_reported(monkeypatch):
    harness, _, offers = world(monkeypatch)
    harness.default = values_of(5.5)
    twin = priced_of(stub_action("dup", twin="K"), 7.0)
    twin2 = priced_of(stub_action("dup2", twin="K"), 6.5)

    found = run([*offers, twin, twin2])

    assert found.twins == (("dup", "dup2"),) and "dup" not in labels(found.used)
    assert "dup" not in found.bounded and "dup2" in found.bounded and "dup2" not in labels(found.used)  # the cheaper twin is bounded, not used


# --- the clock and the progress lines -----------------------------------------------------------------------------------


class Clock:
    def __init__(self, step):
        self.step, self.now = step, -step

    def perf_counter(self):
        self.now += self.step
        return self.now


def test_each_phase_is_timed_by_the_clock_and_named(monkeypatch):
    harness, _, offers = world(monkeypatch)
    harness.default = values_of(5.5)
    monkeypatch.setattr(bp, "time", Clock(2.5))
    said = []
    monkeypatch.setattr(bp, "PROGRESS", said.append)

    found = run(offers)

    names = [name for name, _ in found.phases]
    assert names == ["twins", "classify", "bounds (rho)", "solve 1 (4 offers, 3 states)", "test 1"]
    assert [seconds for _, seconds in found.phases] == [2.5] * 5
    assert said == [f"{name}: 2.5 s" for name in names]


def test_a_fallback_has_its_own_phases_and_a_counted_solve(monkeypatch):
    harness, _, offers = world(monkeypatch)
    harness.default = values_of(5.5, error_bound=math.inf)

    found = run(offers)

    assert [name for name, _ in found.phases][-1] == "fallback solve" and found.phases[0][0] == "twins"


def test_no_progress_is_said_when_the_module_has_none(monkeypatch):
    harness, _, offers = world(monkeypatch)
    harness.default = values_of(5.5)

    assert run(offers).bounded and bp.PROGRESS is None


# --- the offers' bounds side by side in a pool -------------------------------------------------------------------------


class PoolSpy(parallel.WorkerPool):
    """The real pool with one worker (in this process), noting the number of workers asked for and the pieces mapped."""

    made: list = []
    mapped: list = []
    jobs: list = []
    returned: list = []

    def __init__(self, factory, args=(), *, workers=None):
        PoolSpy.made.append(workers)
        PoolSpy.jobs.append([(job[0].name, job[4]) for job in args[4]])  # (offer, level asked) of each piece
        super().__init__(factory, args, workers=1)

    def map(self, function, pieces, *, chunk=None):
        pieces = list(pieces)
        PoolSpy.mapped.append((len(pieces), chunk))
        found = super().map(function, pieces, chunk=chunk)
        PoolSpy.returned.append(len(found))  # only when every piece ran: a piece that raises never gets here
        return found


def with_pool(monkeypatch, workers="2", inherit=True):
    PoolSpy.made, PoolSpy.mapped, PoolSpy.jobs, PoolSpy.returned = [], [], [], []
    monkeypatch.setenv("CRAFTING_WORKERS", workers)
    monkeypatch.setattr(parallel, "can_inherit", lambda: inherit)
    monkeypatch.setattr(parallel, "WorkerPool", PoolSpy)


def parallel_world(monkeypatch, j=6.5, **options):
    harness, state, offers = world(monkeypatch, **options)
    harness.default = values_of(j)
    harness.answers[S1] = values_of(j)
    harness.answers[S1 | {"c", "e"}] = values_of(4.5)
    return harness, state, offers


def test_the_bounds_of_the_offers_outside_the_set_are_raised_a_level_at_a_time_side_by_side(monkeypatch):
    harness, _, offers = parallel_world(monkeypatch)
    serial = run(offers)
    with_pool(monkeypatch, workers="8")
    harness2, _, offers2 = parallel_world(monkeypatch)

    found = run(offers2)

    # level 1: d and e (c is at level 1 already) pass the quick test lower <= T = 6.5; level 2: c and e (d's raised bound 7 is above T)
    assert PoolSpy.made == [2, 2] and PoolSpy.mapped == [(2, 1), (2, 1)]  # min(workers, jobs) each; one piece at a time
    assert PoolSpy.jobs == [[("d", 1), ("e", 1)], [("c", 2), ("e", 2)]]
    assert PoolSpy.returned == [2, 2]  # every piece ran in the pool, none failed and fell back to this process
    assert (found.rounds, found.bounded, found.j_max, found.rho) == (serial.rounds, serial.bounded, serial.j_max, serial.rho)
    assert labels(found.used) == labels(serial.used) == S1 | {"c", "e"}


def test_the_quick_test_that_picks_the_batch_takes_the_slack_off_the_lower_bound(monkeypatch):
    # T = 5.999999999997 is between e's 6 (1 - 1e-12) = 5.999999999994 and 6: e is in the batch (and d, whose lower bound is 5)
    with_pool(monkeypatch)
    harness, _, offers = parallel_world(monkeypatch, j=(5.999999999997 - 1e-9) / (1 + 1e-9))

    run(offers, rounds=1)

    assert PoolSpy.jobs[0] == [("d", 1), ("e", 1)]


def test_a_batch_of_one_is_raised_in_this_process(monkeypatch):
    with_pool(monkeypatch)
    harness, _, offers = parallel_world(monkeypatch, j=5.9)  # level 1: d (5) and e (6 > 5.9: not in the batch)... c is at 1; only d: a batch of one

    run(offers)

    assert PoolSpy.made == []


@pytest.mark.parametrize("workers,inherit", [("1", True), ("2", False)])
def test_with_one_worker_or_no_fork_the_offers_are_raised_in_this_process(monkeypatch, workers, inherit):
    with_pool(monkeypatch, workers=workers, inherit=inherit)
    harness, _, offers = parallel_world(monkeypatch)

    run(offers)

    assert PoolSpy.made == []


def test_a_worker_that_fails_leaves_the_offers_to_be_raised_in_this_process(monkeypatch):
    with_pool(monkeypatch)
    monkeypatch.setattr(PoolSpy, "map", lambda self, function, pieces, *, chunk=None: (_ for _ in ()).throw(RuntimeError("died")))
    harness, _, offers = parallel_world(monkeypatch)

    found = run(offers)

    assert found.bounded == ("d",) and found.rounds == 2


def test_no_offers_are_raised_side_by_side_while_a_value_is_infinite(monkeypatch):
    with_pool(monkeypatch)
    harness, _, offers = world(monkeypatch)
    harness.default = values_of(4.5)
    harness.answers[S1] = values_of(8.0, extra={State("dead"): math.inf})  # d (5) and e (6) are under T = 8: they would be batched if J counted

    found = run(offers)

    assert PoolSpy.made == [] and found.rounds == 2 and labels(found.used) == S1 | {"c", "d"}


def test_two_workers_are_enough_for_a_pool(monkeypatch):
    with_pool(monkeypatch, workers="2")
    harness, _, offers = parallel_world(monkeypatch)

    run(offers)

    assert PoolSpy.made == [2, 2]


# --- more of the choices in a round ----------------------------------------------------------------------------------------


def test_a_craft_that_finishes_a_leaf_outside_the_goal_set_has_pbar_zero(monkeypatch):
    # two leaves m1 and m2; the craft Y adds m1, so m1 is left out of U (a craft can finish it) and U = {m2}: Y is no way to reach U
    harness, state, offers = world(monkeypatch, extra_offers=[priced_of(stub_action("Y", junk=True, draws=False, named=frozenset({"m1"})), 2.5)])
    harness.default = values_of(5.5)
    ab = SimpleNamespace(data=None, goal=Goal((leaf("m1"), leaf("m2"))), is_goal=lambda s: s is GOAL)

    found = solve_pruned(ab, Start(status=(Status.ABSENT, Status.ABSENT)), offers, None, min_offers=1)

    assert found.rho == RHO  # not 2.5 (1 - 1e-12), which is what Y would give with pbar 1
    assert set(map(tuple, state.chosen)) == {(1,)}  # the bounds are asked for the leaf m2 only


def test_a_craft_that_names_a_mod_of_the_goal_set_has_pbar_one(monkeypatch):
    harness, state, offers = world(monkeypatch, extra_offers=[priced_of(stub_action("Y", junk=True, draws=False, named=frozenset({"m1"})), 2.5)])
    harness.default = values_of(5.5)

    found = run(offers)

    assert found.rho == 2.5 * (1 - bp.SLACK)  # only leaf m1: the craft that names it can reach it for certain: ratio 2.5, below a's 4


def test_an_offer_that_the_game_refuses_when_its_bound_is_first_asked_is_not_tried_and_is_named(monkeypatch):
    harness, _, offers = world(monkeypatch, refused={"d"})
    harness.default = values_of(5.5)

    found = run(offers)

    assert found.inapplicable == ("d",) and found.bounded == ("c", "e") and found.rounds == 1


def test_a_terminal_offer_cheap_enough_to_matter_joins_the_set(monkeypatch):
    terminal = priced_of(stub_action("t", item_state=True), 5.0)
    harness, _, offers = world(monkeypatch, extra_offers=[terminal])
    harness.default = values_of(4.5)
    harness.answers[S1] = values_of(5.5)  # T = 5.5: the terminal offer costs 5 (its pbar is 1: no discount) and fails

    found = run(offers)

    assert harness.asked_sets[:2] == [S1, S1 | {"t"}]
    assert found.rounds == 2 and "t" in labels(found.used)


def test_a_terminal_offer_dearer_than_the_values_is_proved_needless(monkeypatch):
    terminal = priced_of(stub_action("t", item_state=True), 7.0)
    harness, _, offers = world(monkeypatch, extra_offers=[terminal])
    harness.default = values_of(5.5)

    found = run(offers)

    assert found.bounded == ("c", "d", "e", "t") and found.rounds == 1


def test_the_test_keeps_an_offer_whose_lower_bound_is_within_the_slack_of_the_test_value(monkeypatch):
    # e's lower bound is 6 and the test compares 6 (1 - 1e-12) = 5.999999999994 with T. Put T at 5.999999999997, between
    # 5.999999999994 and 6: the offer fails the test, and would not if the slack were added instead of taken off.
    target = 5.999999999997
    j = (target - 1e-9) / (1 + 1e-9)
    harness, _, offers = world(monkeypatch)
    harness.default = values_of(j)

    assert run(offers, rounds=1).fell_back is True


def test_an_infinite_value_in_a_state_other_than_the_start_is_still_infinite(monkeypatch):
    harness, _, offers = world(monkeypatch)
    harness.default = values_of(4.5)
    harness.answers[S1] = ({START: math.inf, LIVE: 1.0, GOAL: 0.0}, 0.0)

    found = run(offers)

    assert harness.asked_sets[1] == S1 | {"c", "d"}
