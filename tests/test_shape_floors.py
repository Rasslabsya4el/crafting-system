"""The offers' floors are stated for every shape the offers turn the start item into (ticket #973, OR-12, OR-13): an offer that leaves the start's
shape is a move, priced with the floor of the shape it lands in, not a cut at its own price.

Once the Orb of Scouring is offered, it leaves R05's, R10's and R12's fractured Rare start Magic. The floors were stated for the start's shape
alone, so the Scouring was a terminal offer and its price, 0.35 Chaos, was the floor `rho` of every round: the rounds could not be told apart
and each search was led by a bound near 0 (R05 120.56 Chaos against main's 92.77, R10 504.57 against 38.72). Now the Scouring is a move into
the Magic shape, whose own floor is read from its own offers (`_offer_kinds`, THE SHAPES), and `rho` is the least fixed point of the shapes'
system (`shape_rhos`), which no true floor is below.

* The fixed point, by hand, on two shapes (`shape_rhos`): a move with pbar 0 costs its price plus the floor it lands in; a move that may land
  in E is never charged more than repeating it alone (c / pbar), which keeps the floors in order and below the exact fixed point.
* Through the planner's entry, on R12's fixture amulet (the worlds of `test_planner_wipe`, each mean worked by hand from one draw's chance):
  the fractured start's floor is the Scouring plus the Alterations' Wald floor on the Magic amulet, which is the whole plan's mean; the plain
  Rare start's is the Scouring plus the Alchemy's c / p on the Normal amulet, below the mean (s + a) / p.
"""

import dataclasses
import math
from pathlib import Path
from fractions import Fraction
from types import SimpleNamespace

import pytest
from abstraction_support import real_game_data
from cli_support import R12, given
from targets_support import DATA, EXAMPLES
from test_planner_wipe import ALCHEMY, ALTERATION, SCOURING, chance, plan

import crafting_system.cli  # noqa: F401 - names the presenter of plans (`planner.present_with`, issue #882)
from crafting_system.abstraction import Goal
from crafting_system.actions import AlchemyOrb, AlterationOrb, ChaosOrb, ScouringOrb
from crafting_system.items import Rarity
from crafting_system.planner import _pattern_bound
from crafting_system.planner import _plan as planner_plan
from crafting_system.planner._offer_floor import INSIDE, OUTSIDE, OfferFloors
from crafting_system.planner._offer_kinds import MOVE, REROLL, SLACK, TERMINAL, _Entry, shape_rhos
from crafting_system.targets import load_target


def _entry(index: int, cost: float, kind: str, pbar: Fraction, dests: frozenset[int] = frozenset(), level: int = 2) -> _Entry:
    return _Entry(index, SimpleNamespace(cost=cost), kind, level, pbar, dests=dests)


def _never(*_args) -> None:
    raise AssertionError("an offer at its top level is never raised")


def test_by_hand_a_move_of_pbar_0_costs_its_price_plus_the_floor_it_lands_in():
    """Shape 0: a reroll of cost 10 and pbar 1/10 (Wald floor 100), and a move of cost 1 into shape 1 that never lands in E. Shape 1: a reroll of
    cost 2 and pbar 1/20 (40), and a move of cost 3 back into shape 0. The system: rho_1 = min(40, 3 + rho_0), rho_0 = min(100, 1 + rho_1), whose
    least fixed point is rho_1 = 40, rho_0 = 41. Before #973 the move was terminal, and rho_0 was its price, 1."""
    zero = [_entry(0, 10.0, REROLL, Fraction(1, 10)), _entry(1, 1.0, MOVE, Fraction(0), frozenset({1}))]
    one = [_entry(0, 2.0, REROLL, Fraction(1, 20)), _entry(1, 3.0, MOVE, Fraction(0), frozenset({0}))]
    settled, _rest = shape_rhos([zero, one], _never, until=None)
    assert settled == pytest.approx([41.0, 40.0], rel=1e-9)
    cut = [_entry(0, 10.0, REROLL, Fraction(1, 10)), _entry(1, 1.0, TERMINAL, Fraction(1))]
    assert shape_rhos([cut], _never)[0][0] == pytest.approx(1.0)  # the cut it replaces


def test_by_hand_a_move_that_may_land_in_e_is_never_charged_above_repeating_it_alone():
    """Shape 0: a reroll of Wald floor 100, a move of cost 1 into shape 1 with pbar 0. Shape 1: nothing of its own, a move of cost 4 back with pbar
    1/2. The exact fixed point is rho_1 = 4 + rho_0 / 2, rho_0 = 1 + rho_1: rho_0 = 10, rho_1 = 9. The move back is taken as min(4 + rho_0 / 2,
    4 / (1/2) = 8) so that the shapes settle in order: rho_1 = 8, rho_0 = 9, below the exact 10 and 9 (a lower bound, as every floor must be)."""
    zero = [_entry(0, 10.0, REROLL, Fraction(1, 10)), _entry(1, 1.0, MOVE, Fraction(0), frozenset({1}))]
    one = [_entry(0, 4.0, MOVE, Fraction(1, 2), frozenset({0}))]
    settled, _rest = shape_rhos([zero, one], _never, until=None)
    assert settled == pytest.approx([9.0, 8.0], rel=1e-9)
    assert settled[0] <= 10.0 and settled[1] <= 9.0


def test_by_hand_the_shapes_settle_lazily_and_a_shape_never_settled_is_unreachable():
    """A reroll at level 0 is raised only when it is the least key (its pbar falls from 1 to 1/4 at level 1 and to 1/5 at level 2, so its floor
    rises 3, 12, 15); a move into a shape with no way into E is infinite through it, and that shape's floor is infinite (UNREACHABLE, #1190).
    Stopping at shape 0, the floor of a shape not settled is at least the last key settled."""
    raised = []

    def lift(shape: int, entry: _Entry, level: int) -> None:
        raised.append((shape, entry.index, level))
        entry.level, entry.pbar = level, {1: Fraction(1, 4), 2: Fraction(1, 5)}[level]

    zero = [_entry(0, 3.0, REROLL, Fraction(1), level=0), _entry(1, 0.5, MOVE, Fraction(0), frozenset({1}))]
    one = [_entry(0, 7.0, REROLL, Fraction(0))]  # no way into E from shape 1
    settled, rest = shape_rhos([zero, one], lift, until=0)
    assert settled[0] == pytest.approx(15.0) and settled[1] is None and rest == settled[0]
    assert raised == [(0, 0, 1), (0, 0, 2)]
    assert shape_rhos([[_entry(0, 7.0, REROLL, Fraction(0))]], _never, until=None)[0] == [math.inf]


@pytest.fixture
def floors_on(monkeypatch):
    """The offers' floors on from one offer (the product turns them on from `MIN_OFFERS` = 40), recorded as they are made."""
    made: list[OfferFloors] = []
    built = OfferFloors.__init__

    def init(self, *args, **kwargs):
        built(self, *args, **kwargs)
        made.append(self)

    monkeypatch.setattr(_pattern_bound, "MIN_OFFERS", 1)
    monkeypatch.setattr(planner_plan, "MIN_OFFERS", 1)
    monkeypatch.setattr(OfferFloors, "__init__", init)
    return made


def _holding(made: list[OfferFloors], labels: set[str]) -> list[OfferFloors]:
    found = [floors for floors in made if labels <= {entry.priced.label for entry in floors.entries}]
    assert found
    return found


def test_through_the_entry_r12s_fractured_start_is_floored_by_the_scouring_and_the_magic_amulets_alterations(floors_on):
    """R12's Rare start, its Lightning Resistance fractured, with Chaos Orbs, Scourings and Alterations. The Scouring leaves the Magic amulet
    holding that suffix, where the Alteration rerolls the prefix: the Magic shape's floor is alt / p_alt (the Scouring there keeps the shape and
    never lands in E), and the start's is min(1 / p_chaos, s + alt / p_alt) = s + alt / p_alt: the hand-worked mean of the plan itself, so the
    floor is exact here. Before #973 the Scouring was a terminal offer and the floor was its price, s = 0.05."""
    target = given(load_target(R12, DATA))
    goal = Goal.from_target(target)
    scoured = ScouringOrb().outcomes(DATA, target.start_item).retained
    assert scoured.rarity is Rarity.MAGIC
    p_alt = chance(AlterationOrb().outcomes(DATA, scoured), goal)
    p_chaos = chance(ChaosOrb().outcomes(DATA, target.start_item), goal)
    floor = SCOURING + ALTERATION / p_alt
    assert floor < 1 / p_chaos

    wiped = plan(target, ("chaos-orb", "scouring-orb", "alteration-orb"))

    assert wiped.mean_remaining == pytest.approx(floor, rel=1e-9)
    for floors in _holding(floors_on, {"Orb of Scouring", "Orb of Alteration", "Chaos Orb"}):
        assert floors.rho == pytest.approx(floor, rel=1e-9) and floors.rho <= wiped.mean_remaining * (1 + 1e-12)
        assert [view.item.rarity for view in floors.views] == [Rarity.RARE, Rarity.MAGIC]
        scouring = next(position for position, entry in enumerate(floors.entries) if entry.priced.label == "Orb of Scouring")
        assert floors.entries[scouring].kind == MOVE and floors.entries[scouring].dests == frozenset({1})
        assert floors.lower(scouring, OUTSIDE) == pytest.approx(floor, rel=1e-9)  # its price and the Magic shape's floor
        assert floors.lower(scouring, INSIDE) == pytest.approx(floor, rel=1e-9)


def test_through_the_entry_a_plain_rare_start_is_floored_by_the_scouring_and_the_alchemys_own_floor_on_the_normal_item(floors_on):
    """R12's amulet as a Rare with no mod, with Chaos Orbs, Scourings and Alchemies: an Alchemy on the Normal amulet draws as a Chaos Orb on the
    Rare one, chance p, and the plan scours and alchemises at (s + a) / p. The Normal shape's floor is the Alchemy's own c / p = a / p (a move into
    the Rare shape that lands in E with chance p), and the Rare start's is min(1 / p, s + a / p) = s + a / p: below the mean, as a floor must be,
    and not the Scouring's price s, which it was before #973."""
    r12 = load_target(R12, DATA)
    bare = r12.start_item.changed(DATA, rarity=Rarity.RARE, mods=())
    target = given(dataclasses.replace(r12, start_item=bare))
    p = chance(ChaosOrb().outcomes(DATA, bare), goal := Goal.from_target(target))
    normal = ScouringOrb().outcomes(DATA, bare).retained
    assert normal.rarity is Rarity.NORMAL and chance(AlchemyOrb().outcomes(DATA, normal), goal) == pytest.approx(p, rel=1e-12)

    wiped = plan(target, ("chaos-orb", "scouring-orb", "alchemy-orb"))

    assert wiped.mean_remaining == pytest.approx((SCOURING + ALCHEMY) / p, rel=1e-9)
    for floors in _holding(floors_on, {"Orb of Scouring", "Orb of Alchemy", "Chaos Orb"}):
        assert floors.rho == pytest.approx((SCOURING + ALCHEMY / p) * (1 - SLACK), rel=1e-9)
        assert floors.rho <= wiped.mean_remaining
        assert floors.rhos[1] == pytest.approx(ALCHEMY / p, rel=1e-9)


CLASSIC_OFFERS = True  # plans a real route's target (R05's) in CI: the classic offers, though the methods are named below (`tests/test_classic_offers.py`)


class _Made(BaseException):
    """Ends a plan once the offers' floors of its first search are made: what is checked is the floors, not the plan."""


def test_r05s_magic_ring_holds_the_essence_only_strength_dead_so_the_regal_orb_back_is_no_way_into_e(monkeypatch):
    """R05's fractured Rare start, with essences, Scourings, Alterations and Regal Orbs, at the routes' fixture prices. Its goal needs the
    essence-only Strength mod (`StrengthEssence7_`), which no Magic ring holds and no offer on the Magic ring gives: it is a dead leaf of the
    Magic shape. So an Alteration there never lands in E (pbar 0), nor does the Regal Orb that turns it Rare again (a MOVE_ADD: it adds one mod,
    which cannot be that one), and every way out of the Magic shape goes back to the Rare one. The floor is then the essence's own Wald floor on
    the Rare ring, which it was before the Scouring was offered, never the Scouring's price (0.35 Chaos: R05's 120.56 Chaos instead of 92.77
    before #973's floors) nor the Scouring and the Regal Orb (0.54)."""
    from crafting_system.budget import Budget
    from crafting_system.planner import PlanSettings, plan_target
    from crafting_system.planner._offer_kinds import MOVE_ADD
    from crafting_system.prices import load_price_file

    made: list[OfferFloors] = []
    built = OfferFloors.__init__

    def init(self, *args, **kwargs):
        built(self, *args, **kwargs)
        if {"Orb of Scouring", "Regal Orb"} <= {entry.priced.label for entry in self.entries}:
            made.append(self)
            raise _Made()

    monkeypatch.setattr(OfferFloors, "__init__", init)
    data = real_game_data()
    target = load_target(EXAMPLES / "r05-strength-ring.yaml", data)
    prices = load_price_file(Path(__file__).parent / "fixtures" / "prices" / "routes-allflame-2026-07-31.json")
    with pytest.raises(_Made):
        plan_target(data, target, prices, PlanSettings(budget=Budget.in_states(10_000), methods=("essence", "scouring-orb", "alteration-orb", "regal-orb")))
    (floors,) = made
    magic = next(index for index, view in enumerate(floors.views) if view.item.rarity is Rarity.MAGIC)
    strength = next(index for index in floors.chosen if floors.ab.goal.leaves[index].mod_ids == frozenset({"StrengthEssence7_"}))
    assert strength in floors.views[magic].dead
    scouring = next(entry for entry in floors.entries if entry.priced.label == "Orb of Scouring")
    regal = next(entry for entry in floors.shape_entries[magic] if entry.priced.label == "Regal Orb")
    floors._lift(magic, regal, 1)
    assert regal.kind == MOVE_ADD and regal.pbar == 0 and regal.dests == frozenset({0})
    essences = [entry for entry in floors.entries if entry.kind == REROLL and "Essence" in entry.priced.label and entry.level == 2]
    assert essences and floors.rho == pytest.approx(min(entry.ratio for entry in essences) * (1 - SLACK), rel=1e-12)
    assert floors.rho > 100 > scouring.cost + regal.cost
