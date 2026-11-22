"""An offer set that cannot enter E is infinite to the bound, the search and the answer, never a finite stand-in (#1190, OR-13, OR-40).

The offers' floors (`_offer_kinds`, `_offer_floor`) bound the cost of a state of the start's shape outside E by `rho`, the least cost / pbar over
the offers. When no offer can enter E, every ratio is infinite, and `rho` was written as 1e300 "so that 0 * rho stays 0". That number reached the
bound's model as the cost of its floor action, the envelope search as the bound of the start, and the answer as a figure: R24's essence round
was refused with "a relative bound of inf" (the solver's residuals near 1e300 overflow), and its bench round said "no plan with them costs less
than 999,999,999,999,000,033,...,560.00 Chaos". Now `rho` is infinite, the floors' arithmetic keeps 0 for an offer that lands in E for sure
(`OfferFloors.after_leaving`), the model has no floor action at an infinite floor, and a search whose start's bound is infinite answers at once
that no plan of its offers reaches the goal.

The world is the hand-worked belt of `test_planner_blocking_crafts`: the goal is the top Life prefix, and the bench's filler crafts add only a
suffix of a family no draw gives, so a plan made only of them never reaches the goal (each filler: pbar 0, the restart: pbar 0, so rho is
infinite); an Exalted Orb does, at `V = 3(c + e) + 2S = 133` with the filler first. The product turns the floors on from 40 offers; here they
are on from one (`MIN_OFFERS`), and the bound's model starts on the restart alone (`OfferFloors.initial`), so every other offer is carried by
its floor: the case of R24's rounds, where most offers are left to the floor action.
"""

import math
from fractions import Fraction
from types import SimpleNamespace

import pytest
from test_planner_blocking_crafts import S, _prices, data, every_shared_kernel_checked  # noqa: F401 (fixtures)
from test_stop_is_not_unreachable import UNREACHABLE, _by_hand, _target

from crafting_system.budget import Budget
from crafting_system.planner import PlanError, PlanSettings, _offers, _pattern_bound, plan_target
from crafting_system.planner import _plan as planner_plan
from crafting_system.planner._offer_floor import INSIDE, OTHER, OUTSIDE, OfferFloors
from crafting_system.planner._offer_kinds import REFUSED, REROLL, RESTART_KIND, _Entry, best_first_rho
from crafting_system.planner import _growth

@pytest.fixture(autouse=True)
def _widening_alone(monkeypatch):
    """These tests are of the widening rounds' own mechanism (their shares, set-asides, give-way and words): the plan-led growth that runs
    before them (`_growth`, #1414) is off here; `tests/test_growth.py` tests it through the entry."""
    monkeypatch.setattr(_growth, "GROWS", False)


STAND_IN = ("1e+300", "9.99999999999e+299", "999,999,999,999", "inf")  # every way the stand-in, or its overflow, was printed


@pytest.fixture
def floors_from_one(monkeypatch):
    """The offers' floors on from one offer, and the bound's model starting on the restart alone (every other offer carried by its floor);
    the floors are recorded as they are made."""
    made: list[OfferFloors] = []
    built = OfferFloors.__init__

    def init(self, *args, **kwargs):
        built(self, *args, **kwargs)
        made.append(self)

    monkeypatch.setattr(_pattern_bound, "MIN_OFFERS", 1)
    monkeypatch.setattr(planner_plan, "MIN_OFFERS", 1)
    monkeypatch.setattr(OfferFloors, "__init__", init)
    monkeypatch.setattr(OfferFloors, "initial", lambda self: [entry.index for entry in self.entries if entry.kind == RESTART_KIND])
    return made


def _settings(states: int, methods: tuple[str, ...], build_per_state: float = 1.0) -> PlanSettings:
    """Counted in states (`Budget.in_states`): `states` for the searches, `build_per_state` pieces of work per state for the bound's build."""
    return PlanSettings(recipe_starts=False, start_price=S, budget=Budget.in_states(states, build_per_state=build_per_state), methods=methods)


def test_through_the_entry_one_search_of_offers_that_cannot_enter_e_is_the_proof_even_where_a_net_would_have_stopped_it(tmp_path, data, monkeypatch, floors_from_one):
    """One search over the fillers alone, with a net of 1 state and 1 piece of work: the build stops before the filler joins the model and the
    search before it expands anything. Before #1190 the floor action at 1e300 was the model's value at the start, and the answer said "stopped,
    no plan found yet ... no plan costs less than 1e+300". The floors prove that no filler can enter E (rho infinite), the start's bound is
    infinite, and the answer is that proof, which no net can make a stop."""
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)  # the fillers, offered by the rule: the only priced actions of a target naming the bench
    with pytest.raises(PlanError) as raised:
        plan_target(data, _target(tmp_path, data), _prices(), _settings(1, ("bench-craft",)))
    said = str(raised.value)
    assert said.startswith(UNREACHABLE) and "no plan found yet" not in said and "costs less than" not in said
    assert not any(figure in said for figure in STAND_IN)
    assert floors_from_one and all(made.rho == math.inf for made in floors_from_one)


@pytest.mark.parametrize("states", [2, 3])
def test_through_the_entry_rounds_of_offers_that_cannot_enter_e_are_the_proof_with_no_figure_in_chaos(tmp_path, data, monkeypatch, floors_from_one, states):
    """Round 1 the fillers alone, round 2 every offer again (`_by_hand`): no round reaches the goal. Before #1190, at 2 and 3 states, a round
    stopped "with no plan; no plan with them costs less than 999,999,999,999,000,033,...,560.00 Chaos", R24's line. Each round's floors are
    infinite, each round finishes with no plan, and the last held every offer: the answer is the proof."""
    _by_hand(monkeypatch, exalted=False)
    with pytest.raises(PlanError) as raised:
        plan_target(data, _target(tmp_path, data), _prices(), _settings(states, ("exalted-orb", "bench-craft")))
    said = str(raised.value)
    assert said.startswith(UNREACHABLE) and "no plan found yet" not in said
    assert not any(figure in said for figure in STAND_IN)
    assert floors_from_one and all(made.rho == math.inf for made in floors_from_one)


def test_through_the_entry_a_round_that_can_enter_e_keeps_its_finite_floors_and_the_hand_worked_plan(tmp_path, data, monkeypatch, floors_from_one):
    """Round 1 the fillers alone (rho infinite: no plan), round 2 adds the Exalted Orb, whose rho is finite: at the best state of the shape (the
    suffixes full) it adds a prefix for sure, Life 3 with chance 1,000 / 3,000 = 1/3, so pbar = 1/3 and rho = e / pbar = 30 (the fillers and the
    restart have pbar 0). The plan is the hand-worked 3 (c + e) + 2S = 133, and round 1 is named by what it proved."""
    _by_hand(monkeypatch, exalted=True)
    plan = plan_target(data, _target(tmp_path, data), _prices(), _settings(50, ("exalted-orb", "bench-craft"), build_per_state=100.0))
    assert plan.mean_remaining == pytest.approx(133.0)
    first, second = plan.search.widening
    assert first.status == "no plan" and first.lower in (None, math.inf) and second.status == "closed"
    assert [made.rho for made in floors_from_one][0] == math.inf
    assert floors_from_one[-1].rho == pytest.approx(30.0)


def _floors(rho: float, *entries: _Entry) -> OfferFloors:
    """Floors with a given `rho` over hand-made entries, without a world (the class's arithmetic alone)."""
    floors = OfferFloors.__new__(OfferFloors)
    floors.rho, floors.entries = rho, list(entries)
    return floors


def test_an_infinite_rho_gives_infinite_floors_outside_e_and_never_a_nan():
    """By hand, rho infinite: an offer the bare item refuses (kind REFUSED, pbar 1: not in the minimum that makes rho) costs at least V* = inf
    outside E, where `cost + (1 - 1) * inf` was `nan` in floats and `max(nan, inf)` is `nan`; inside E it costs its price, 3. A reroll that
    never lands in E (pbar 0) costs inf inside E as well (its use leaves E for a state no offer brings back); a reroll that lands in E for sure
    costs its price, 4, inside E. Of another shape every offer costs its price."""
    refused = _Entry(0, SimpleNamespace(cost=3.0), REFUSED, 0, Fraction(1))
    never = _Entry(1, SimpleNamespace(cost=2.0), REROLL, 2, Fraction(0))
    sure = _Entry(2, SimpleNamespace(cost=4.0), REROLL, 2, Fraction(1))
    floors = _floors(math.inf, refused, never, sure)
    assert [floors.lower(position, OUTSIDE) for position in range(3)] == [math.inf] * 3
    assert [floors.lower(position, INSIDE) for position in range(3)] == [3.0, math.inf, 4.0]
    assert [floors.lower(position, OTHER) for position in range(3)] == [3.0, 2.0, 4.0]
    assert floors.floor(range(3), OUTSIDE) == math.inf


def test_a_finite_rho_gives_the_hand_worked_floors():
    """By hand, rho 10: a reroll of price 2 and pbar 1/4 costs at least 2 + (3/4) 10 = 9.5 inside E and max(9.5, 10) = 10 outside; one of pbar 1
    costs its price, 4, inside and the price or rho, 10, outside."""
    quarter = _Entry(0, SimpleNamespace(cost=2.0), REROLL, 2, Fraction(1, 4))
    sure = _Entry(1, SimpleNamespace(cost=4.0), REROLL, 2, Fraction(1))
    floors = _floors(10.0, quarter, sure)
    assert floors.lower(0, INSIDE) == pytest.approx(9.5) and floors.lower(0, OUTSIDE) == pytest.approx(10.0)
    assert floors.lower(1, INSIDE) == 4.0 and floors.lower(1, OUTSIDE) == 10.0


def test_rho_is_infinite_when_no_offer_can_enter_e_and_a_refused_offer_does_not_make_it_finite():
    restart = _Entry(0, SimpleNamespace(cost=50.0), RESTART_KIND, 0, Fraction(0))
    refused = _Entry(1, SimpleNamespace(cost=3.0), REFUSED, 0, Fraction(1))
    craft = _Entry(2, SimpleNamespace(cost=600.0), "craft", 0, Fraction(0))
    assert best_first_rho([restart, refused, craft], lambda *_: None) == math.inf
