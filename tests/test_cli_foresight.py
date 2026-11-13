"""Hinekora's Lock in the plan (ticket #296, B8-4, ADR-0054 to ADR-0057): the options, the exact pruning, the second solve, N and the coarse refusal.

Three groups:

* the hand test of ADR-0054 and tiny models, against the explicit product expansion (`peek_oracles.product_spec`) solved with no Peek at all;
* a fuzz over the seeded Peek models of `peek_oracles`: the pruning (exact, and coarse: pessimistic values and a cheaper `c_min`) never removes a
  state where the oracle takes the Lock, and where it removes the Lock the plan is the Lock-free plan;
* the planner on the fixture data: R12, the coarse level of `test_cli_approximate`'s target, and toy previewable actions for the options.
"""

import dataclasses
import itertools
import math
from fractions import Fraction

import pytest
from cli_support import R12, price_file
from peek_oracles import product_spec, random_peek_spec
from ssp_oracles import to_model
from targets_support import DATA

from crafting_system.actions import Action as GameAction
from crafting_system.actions import ChaosOrb, Kind, Previewable, registered
from crafting_system.cli import PlanError, make_plan
from crafting_system.planner._foresight import (
    LOCK_KIND,
    LOCK_LABEL,
    LockModel,
    PlanSites,
    Site,
    Status,
    gain,
    lock_gain,
    survives,
)
from crafting_system.planner._offers import Offer, PricedOffer
from crafting_system.cli._report import build_report
from crafting_system.prices import PriceEntry
from crafting_system.solver import Action, Outcome, TabularModel, solve, solve_peek
from crafting_system.targets import load_target

LOCK = "Hinekora's Lock"
GOAL, S, MIDDLE, BRICK = "goal", "s", "middle", "brick"
OPTION_A = Action("A", 1.0, (Outcome(GOAL, 20), Outcome(MIDDLE, 50), Outcome(BRICK, 30)))
OPTION_B = Action("B", 2.0, (Outcome(GOAL, 10), Outcome(MIDDLE, 80), Outcome(BRICK, 10)))
BENCH = Action("bench", 66.0, (Outcome(GOAL, 1),))  # the fallback of the hand test: an action that is not previewable, worth 66 to finish
TABLE = {S: (OPTION_A, OPTION_B, BENCH), MIDDLE: (Action("finish middle", 30.0, (Outcome(GOAL, 1),)),), BRICK: (Action("finish brick", 400.0, (Outcome(GOAL, 1),)),)}
HAND_SITE = Site((OPTION_A, OPTION_B), (BENCH,))


def hand_model():
    return TabularModel([GOAL], TABLE)


def hand_peek_by_enumeration() -> Fraction:
    """E[min(min_a(c_a + V(o_a)), F)] of the hand test by the 9 pairs, in Fractions (ADR-0054: 23.97)."""
    value = {GOAL: 0, MIDDLE: 30, BRICK: 400}
    a = [(Fraction(w, 100), 1 + value[o]) for o, w in ((GOAL, 20), (MIDDLE, 50), (BRICK, 30))]
    b = [(Fraction(w, 100), 2 + value[o]) for o, w in ((GOAL, 10), (MIDDLE, 80), (BRICK, 10))]
    return sum(pa * pb * min(xa, xb, 66) for (pa, xa), (pb, xb) in itertools.product(a, b))


# --- the hand test and the product expansion --------------------------------------------------------------------


def test_the_hand_test_without_the_lock_is_b_at_66_and_n_is_its_break_even_42_03():
    first = solve(hand_model(), [S])
    assert first.values[S] == pytest.approx(66.0) and first.policy[S].label in {"B", "bench"}
    peek = hand_peek_by_enumeration()
    assert float(peek) == pytest.approx(23.97, abs=0.005)

    found = lock_gain([S, MIDDLE, BRICK], first.values, lambda state: HAND_SITE if state == S else None, c_min=1.0)

    assert found.n == pytest.approx(66 - float(peek), rel=1e-12) and found.n == pytest.approx(42.03, abs=0.005)
    assert found.state == S and found.exact and found.any_option


@pytest.mark.parametrize("lock", [0.5, 10.0, 42.0, 42.1, 100.0])
def test_the_plan_with_the_lock_equals_the_product_expansion_and_takes_it_only_below_n(lock):
    first = solve(hand_model(), [S])
    second = solve_peek(LockModel(hand_model(), lambda state: HAND_SITE if state == S else None, lock, lambda state: True), [S])
    spec = (
        3,
        {
            0: [("A", Fraction(1), [(3, 20), (1, 50), (2, 30)]), ("B", Fraction(2), [(3, 10), (1, 80), (2, 10)]), ("bench", Fraction(66), [(3, 1)])],
            1: [("m", Fraction(30), [(3, 1)])],
            2: [("b", Fraction(400), [(3, 1)])],
        },
    )
    product = _hand_product(spec, Fraction(lock).limit_denominator(10))
    oracle = solve(to_model(product), range(3)).values  # the product expansion holds no Peek: the plain solver is the oracle

    assert second.values[S] == pytest.approx(float(oracle[0]), rel=1e-9)
    takes = second.policy[S].label == LOCK_LABEL
    assert takes == (lock < 66 - float(hand_peek_by_enumeration()))
    assert takes == (second.values[S] < first.values[S])


def _hand_product(spec, lock):
    from peek_oracles import PeekSpec

    size, table = spec
    options = [("A", Fraction(1), [(3, 20), (1, 50), (2, 30)]), ("B", Fraction(2), [(3, 10), (1, 80), (2, 10)])]
    return product_spec(PeekSpec(size, table, 0, lock, options, [("bench", Fraction(66), [(3, 1)])], 0))


def test_two_currencies_with_equal_kernels_are_two_options_and_the_plan_costs_less_than_with_one():
    twin = dataclasses.replace(OPTION_A, label="A twin")
    one = Site((OPTION_A,), (BENCH,))
    two = Site((OPTION_A, twin), (BENCH,))

    def value(site):
        return solve_peek(LockModel(hand_model(), lambda state: site if state == S else None, 1.0, lambda state: True), [S]).values[S]

    assert value(two) < value(one) < 66.0
    first = solve(hand_model(), [S])
    assert gain(two, first.values[S], first.values) > gain(one, first.values[S], first.values)


# --- the fuzz: the pruning never removes a state where the oracle takes the Lock ----------------------------------

SEEDS = range(2000)


def _spec_parts(spec):
    def action(label, cost, outcomes):
        return Action(label, float(cost), tuple(Outcome(state, weight) for state, weight in outcomes))

    base = TabularModel([spec.size], {state: [action(*a) for a in plain] for state, plain in spec.table.items()})
    site = Site(tuple(action(*o) for o in spec.options), tuple(action(*f) for f in spec.fallback))
    c_min = min(float(cost) for _, cost, _ in (*spec.options, *spec.fallback))
    return base, site, c_min


@pytest.mark.parametrize("chunk", range(10))
def test_the_pruning_never_removes_a_state_where_the_oracle_takes_the_lock(chunk):
    checked = taken = 0
    for seed in SEEDS[chunk::10]:
        spec = random_peek_spec(seed)
        if spec.state is None:
            continue
        base, site, c_min = _spec_parts(spec)
        lock_free = solve(base, range(spec.size))
        oracle = solve(to_model(product_spec(spec)), range(spec.size)).values  # the product expansion: the Lock as an ordinary action
        state, value = spec.state, lock_free.values[spec.state]
        lock = float(spec.lock)
        checked += 1
        if oracle[state] < value * (1 - 1e-9):  # the oracle takes the Lock there
            taken += 1
            assert survives(lock, c_min, value), seed  # exact level
            assert survives(lock, c_min / 2, value * 1.5 if math.isfinite(value) else value), seed  # coarse: a cheaper c_min, a pessimistic value
        keep = survives(lock, c_min, value)
        model = LockModel(base, lambda s: site if s == state else None, lock, lambda s: keep)
        planned = solve_peek(model, range(spec.size))
        if not keep:  # pruned: the plan is the Lock-free plan, bit for bit
            assert planned.values == lock_free.values and planned.rounds == 0, seed
        else:
            for s in range(spec.size):
                assert planned.values[s] == pytest.approx(oracle[s], rel=1e-7) or (math.isinf(planned.values[s]) and math.isinf(oracle[s])), seed
    assert checked > 150 and taken > 10


# --- the planner on the fixture data ----------------------------------------------------------------------------


def with_lock(prices, price):
    return dataclasses.replace(prices, prices={**prices.prices, LOCK: PriceEntry(price, "test")})


@pytest.fixture(scope="module")
def r12():
    return load_target(R12, DATA)


@pytest.fixture(scope="module")
def lock_free(r12):
    return make_plan(DATA, r12, price_file())  # the fixture prices have no Lock: it is dropped, N is still found


def test_without_a_price_the_lock_is_dropped_and_n_is_still_found(lock_free):
    found = lock_free.foresight
    assert found.status is Status.NO_PRICE and found.price is None
    assert found.n is not None and found.n > 0 and found.best_state == lock_free.start


def test_with_a_very_dear_lock_the_plan_is_the_lock_free_plan_bit_for_bit_and_every_state_is_pruned(r12, lock_free):
    plan = make_plan(DATA, r12, with_lock(price_file(), 1e9))
    found = plan.foresight

    assert plan.solution.values == lock_free.solution.values and dict(plan.policy) == dict(lock_free.policy)
    assert plan.risk == lock_free.risk
    states = [state for state in plan.solution.values if not plan.is_goal(state)]
    assert found.status is Status.NOT_WORTH and found.kept == 0 and found.pruned == len(states) > 0
    assert found.n == lock_free.foresight.n and found.saving is None


def test_n_on_the_planner_is_the_break_even_of_the_lock(r12, lock_free):
    n = lock_free.foresight.n
    above = make_plan(DATA, r12, with_lock(price_file(), n * 1.01))
    below = make_plan(DATA, r12, with_lock(price_file(), n * 0.99))

    assert above.foresight.status is Status.NOT_WORTH and above.mean_remaining == lock_free.mean_remaining
    assert below.foresight.status is Status.USED and below.mean_remaining < lock_free.mean_remaining
    assert below.foresight.saving == pytest.approx(lock_free.mean_remaining - below.mean_remaining)
    assert any(action.label == LOCK_LABEL for action in below.policy.values())


def test_a_plan_with_the_lock_has_its_risk_and_the_report_refuses_it_in_words_until_ticket_298(r12):
    plan = make_plan(DATA, r12, with_lock(price_file(), 0.01))

    assert plan.foresight.status is Status.USED and plan.risk is not None
    assert plan.risk.mean.value == pytest.approx(plan.mean_remaining, rel=1e-6)
    with pytest.raises(PlanError, match="takes Hinekora's Lock"):
        build_report(plan, DATA)


def test_the_lock_is_on_by_default_and_the_targets_actions_drop_it_or_name_it(r12):
    prices = with_lock(price_file(), 0.01)
    dropped = make_plan(DATA, dataclasses.replace(r12, actions=("chaos-orb", "harvest-reforge")), prices)
    named = make_plan(DATA, dataclasses.replace(r12, actions=("chaos-orb", "harvest-reforge", LOCK_KIND)), prices)

    assert dropped.foresight.status is Status.SWITCHED_OFF and dropped.foresight.n is None
    assert named.foresight.status is Status.USED


# --- the coarse level ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def coarse():
    import test_cli_approximate as approx

    target = approx.parse_target(approx.TARGET, approx.DATA, source="t.yaml")
    exact = make_plan(approx.DATA, target, approx.PRICES, offers=approx.OFFERS, solver="object")
    forecast = exact.abstraction.estimate([exact.start], [offer.action for offer in approx.OFFERS])
    pooling = approx.Coarsening.pooling_irrelevant(exact.abstraction, None, exact.start)
    budget = (forecast.seconds(1.0, 1.0) + forecast.coarsened(pooling).seconds(1.0, 1.0)) / 2

    def plan(prices):
        return make_plan(approx.DATA, target, prices, offers=approx.OFFERS, budget=budget, rates=approx.RATES, solver="object")

    return approx.PRICES, plan


def test_a_lock_that_survives_the_pruning_on_the_coarse_bounds_has_no_approximate_level_and_says_why(coarse):
    prices, plan = coarse
    with pytest.raises(PlanError, match="Hinekora's Lock could pay") as refused:
        plan(with_lock(prices, 0.001))
    assert "`actions:`" in str(refused.value)


def test_a_lock_pruned_everywhere_keeps_the_level_with_the_bounds_of_no_lock(coarse):
    prices, plan = coarse
    without, dear = plan(prices), plan(with_lock(prices, 1e9))

    assert without.approximation is not None and without.foresight.status is Status.NO_PRICE
    same = ("lower", "upper", "gap", "level", "blocks", "tolerance", "message")
    assert [getattr(dear.approximation, key) for key in same] == [getattr(without.approximation, key) for key in same]
    assert dear.solution.values == without.solution.values and dict(dear.policy) == dict(without.policy)
    assert dear.foresight.status is Status.COARSE and dear.foresight.n is None and dear.foresight.pruned == len(dear.solution.values)


# --- the options: from the full catalog, one per currency item ------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ToyPreview(GameAction):
    """A Chaos Orb under another label and currency item, at another price: an option with the Chaos Orb's kernel."""

    name: str = "Toy"
    item: str = "Toy Orb"

    def label(self, data=None):
        return self.name

    def previewable(self, data=None):
        return Previewable.BY_ITEM_TEXT

    def currency_item(self, data=None):
        return self.item

    def resources(self, data=None):
        return {self.item: 1}

    def reads(self, data):
        return ChaosOrb().reads(data)

    def adds(self, data=None, item=None):
        return ChaosOrb().adds(data, item)

    def outcomes(self, data, item):
        return ChaosOrb().outcomes(data, item)


def _sites(plan, offers, plain):
    return PlanSites(plan.abstraction, offers, plain, plan.start, None)


def _priced(action, cost):
    return PricedOffer(Offer(action.label(), action, action.resources()), cost, ())


def test_a_state_has_one_option_per_currency_item_the_cheapest(lock_free):
    chaos = next(priced for priced in lock_free.offers if priced.label == "Chaos Orb")
    same_item = _priced(ToyPreview("Dear Chaos", "Chaos Orb"), 5.0)
    cheap_item = _priced(ToyPreview("Cheap Chaos", "Chaos Orb"), 0.5)
    other = _priced(ToyPreview("Other Orb", "Other Orb"), 3.0)

    site = _sites(lock_free, (chaos, same_item, cheap_item, other), (chaos,))(lock_free.start)

    assert [option.label for option in site.options] == ["Cheap Chaos", "Other Orb"]
    assert site.by_item_text == ("Cheap Chaos", "Other Orb")


def test_equal_kernels_and_offers_pruned_from_the_plain_solve_stay_options(lock_free):
    chaos = next(priced for priced in lock_free.offers if priced.label == "Chaos Orb")
    twin = _priced(ToyPreview("Twin Orb", "Twin Orb"), 1.0)  # the Chaos Orb's kernel: the equal-kernel merge keeps one of them as a plain action
    plain = tuple(priced for priced in lock_free.offers if priced.label != "Chaos Orb")  # the Chaos Orb pruned out of the plain solve

    site = _sites(lock_free, (*lock_free.offers, twin), plain)(lock_free.start)

    assert {option.label for option in site.options} == {"Chaos Orb", "Twin Orb"}
    assert site.options[0].outcomes == site.options[1].outcomes
    assert all(action.label not in {"Chaos Orb", "Twin Orb"} for action in site.fallback)
    assert site.fallback and all(not action.label.startswith(("Chaos", "Twin")) for action in site.fallback)  # the Harvest reforge (no restart at the start)


def test_a_toy_option_of_the_catalog_reaches_the_plan(r12, lock_free):
    with registered(Kind("toy-preview", lambda data, item: iter([ToyPreview()]), order=901)):
        plan = make_plan(DATA, r12, dataclasses.replace(with_lock(price_file(), 0.05), prices={**with_lock(price_file(), 0.05).prices, "Toy Orb": PriceEntry(1.0, "test")}))
    assert plan.foresight.status is Status.USED and plan.foresight.n > lock_free.foresight.n  # two independent previews are worth more than one
    assert plan.foresight.by_item_text == ("Toy",)


@dataclasses.dataclass(frozen=True)
class ToyBlind(GameAction):
    """A dear Chaos Orb that the Lock does not preview: one of the many offers that send a plan to the bound pruning (40 or more)."""

    index: int = 0

    def label(self, data=None):
        return f"Blind Chaos {self.index}"

    def resources(self, data=None):
        return {"Chaos Orb": 50 + self.index}

    def reads(self, data):
        return ChaosOrb().reads(data)

    def adds(self, data=None, item=None):
        return ChaosOrb().adds(data, item)

    def outcomes(self, data, item):
        return ChaosOrb().outcomes(data, item)


def test_on_the_bound_pruning_path_the_lock_plan_equals_the_one_solved_without_that_pruning(r12):
    from crafting_system.planner._offers import offers_for
    from crafting_system.abstraction import Goal

    base = offers_for(DATA, Goal.from_target(r12), r12.base_id, r12.start_item, r12.actions).offers
    offers = (*base, *(Offer(ToyBlind(i).label(), ToyBlind(i), ToyBlind(i).resources()) for i in range(40)))
    prices = with_lock(price_file(), 0.05)
    pruned = make_plan(DATA, r12, prices, offers=offers)
    whole = make_plan(DATA, r12, prices, offers=offers, solver="packed")  # every offer after the twins, no bound pruning

    assert pruned.pruned is not None and whole.pruned is None
    assert pruned.foresight.status is whole.foresight.status is Status.USED
    assert pruned.mean_remaining == pytest.approx(whole.mean_remaining, rel=1e-9)
    assert pruned.foresight.lock_free_mean == pytest.approx(whole.foresight.lock_free_mean, rel=1e-9)


def test_a_burn_is_a_fallback_that_leads_back_to_the_state_and_a_plan_with_it_solves(r12, lock_free):
    prices = dataclasses.replace(with_lock(price_file(), 0.05), prices={**with_lock(price_file(), 0.05).prices, "Clear Oil": PriceEntry(0.01, "test")})
    plan = make_plan(DATA, r12, prices)  # an amulet: the re-anoint (three Clear Oils) is its burn

    from crafting_system.planner._foresight import plan_burn

    burn = plan_burn(DATA, r12.start_item, plan.abstraction, prices)
    assert burn is not None and burn.label == "Burn with Re-anoint" and burn.cost == pytest.approx(0.03)
    site = PlanSites(plan.abstraction, plan.offers, plan.offers, plan.start, burn)(plan.start)
    loop = next(action for action in site.fallback if action.label == burn.label)
    assert [(state, weight) for state, weight in loop.outcomes] == [(plan.start, 1)]
    assert plan.foresight.status is Status.USED and plan.mean_remaining < lock_free.mean_remaining
