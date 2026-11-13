"""Property tests of the planner that need no reference answer (ticket #887): relations between two runs through `planner.plan_target`.

Nobody can say what the cheapest route of a target "should" cost, so these tests say how two answers of the planner must stand to
each other, on generated cases (`planner_relations_support`: the generator of the planning-speed family, at one and two wanted mods):

1. raising the price of one ingredient never lowers the plan's mean cost, lowering it never raises it;
2. allowing one more method never raises it, forbidding one never lowers it;
3. loosening the target (a wider tier range, one mod fewer) never raises it, tightening never lowers it;
4. scaling every price by one factor scales the cost by that factor and keeps the plan;
5. a guide's route is a valid policy, so the plan never costs more than the guide by the same rules;
6. the plan played by the simulator reaches the target, and its simulated mean agrees with the stated mean.

Every comparison gives the room `planner_relations_support.GAP` and no other. The second half breaks the planner on purpose (it drops an
offer, misprices an ingredient, misreads the target) and asserts that the relation then reports a violation: a relation that cannot fail
tests nothing. The breaks are monkeypatches of two names the planner calls, `_plan.price_offers` and `_entry.plan_with_starts`; no
code of the planner is changed for them.
"""

import dataclasses

import pytest
from abstraction_support import real_game_data

import planner_relations_support as R
from crafting_system.planner import _entry, _plan

# The generated cases: (method set, size, seed). Each relation runs on every one of them.
CASES = (
    ("magic-orbs", "one", 1),
    ("magic-orbs", "one", 2),
    ("magic-orbs", "two", 1),
    ("magic-and-regal", "one", 1),
    ("essences", "one", 1),
    ("essences", "two", 1),
    ("chaos-orb", "one", 2),
    ("chaos-orb", "two", 1),
)
BROKEN_ON = ("magic-orbs", "one", 1)  # the case each broken planner is shown on: three orbs, one wanted mod, a bought Normal base

named = pytest.mark.parametrize("name", CASES, ids=["/".join(map(str, name)) for name in CASES])


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def runs(data):
    """The plans of the planner as it is, shared by the relations: a case's own plan is made once."""
    return R.Runs(data)


@pytest.fixture(scope="module")
def case_of(data):
    made = {}

    def find(name):
        if name not in made:
            made[name] = R.case(data, *name)
        return made[name]

    return find


# -- the planner as it is -------------------------------------------------------------------------------------------------------------


@named
def test_every_case_is_the_generators_and_has_a_plan(runs, case_of, data, name):
    case = case_of(name)
    again = R.case(data, *name)
    assert again.generated.digest() == case.generated.digest()  # the same seed gives the same case
    assert case.generated.refused is None
    assert len(case.doc["requirements"]) == R.SIZES[name[1]].wanted[0]
    assert set(case.doc["actions"]) == set(R.METHODS[name[0]].method.actions)
    plan = runs.plan(case)
    assert plan is not None and 0 < R.total(plan) < float("inf")


def test_the_cases_differ():
    assert len({name[0] for name in CASES}) == len(R.METHODS)  # every method set
    assert {name[1] for name in CASES} == set(R.SIZES)  # at both sizes


@named
def test_a_dearer_ingredient_never_lowers_the_cost_and_a_cheaper_one_never_raises_it(runs, case_of, name):
    assert R.price_violations(runs, case_of(name)) == []


@named
def test_one_more_method_never_raises_the_cost_and_one_fewer_never_lowers_it(runs, case_of, name):
    assert R.method_violations(runs, case_of(name)) == []


@named
def test_a_looser_target_never_costs_more_than_a_tighter_one(runs, case_of, name):
    case = case_of(name)
    assert R.tier_changes(case.doc)  # every case has a tier to widen
    assert R.target_violations(runs, case) == []


@named
def test_every_price_scaled_scales_the_cost_and_keeps_the_plan(runs, case_of, name):
    assert R.scale_violations(runs, case_of(name)) == []


@named
def test_the_plan_never_costs_more_than_a_guide(runs, case_of, name):
    case = case_of(name)
    given = R.guides(runs, case)
    assert any(mean < float("inf") for _order, mean in given)  # a guide that finishes: the comparison is of two costs
    assert R.guide_violations(runs, case, given) == []


@named
def test_the_simulated_plan_reaches_the_target_at_the_stated_mean(runs, case_of, name):
    assert R.simulation_violations(runs, case_of(name)) == []


def test_the_scale_relation_is_the_whole_one_where_no_offer_takes_the_unit(runs, case_of):
    """The Chaos Orb cannot be scaled, so a plan that consumes it is held to a range; most cases must be held to the exact factor."""
    exact = [name for name in CASES if not any(part[0] == R.UNIT for priced in runs.plan(case_of(name)).offers for part in priced.parts)]
    assert {name[0] for name in exact} == {"magic-orbs", "magic-and-regal", "essences"}


# -- a planner broken on purpose: each relation reports it ----------------------------------------------------------------------------


def priced_by(monkeypatch, change):
    """Break the planner's pricing: `change` rewrites the priced offers `_plan.price_offers` returns."""
    real = _plan.price_offers

    def broken(offers, prices, price_source=None, *more):
        priced, dropped = real(offers, prices, *(() if price_source is None else (price_source,)), *more)
        return tuple(change(priced)), dropped

    monkeypatch.setattr(_plan, "price_offers", broken)


def target_read_by(monkeypatch, data, change):
    """Break the planner's reading of the target: it plans `change(data, target)` when asked for `target`."""
    real = _entry.plan_with_starts
    monkeypatch.setattr(_entry, "plan_with_starts", lambda data_, target, prices, **settings: real(data_, change(data, target), prices, **settings))


@pytest.fixture
def broken_case(case_of):
    return case_of(BROKEN_ON)


def test_a_planner_that_reads_prices_upside_down_breaks_the_price_relation(monkeypatch, data, broken_case):
    """Misprice the ingredients: every offer costs one over its price, so the dearer an orb the cheaper the planner takes it to be."""
    priced_by(monkeypatch, lambda priced: [dataclasses.replace(entry, cost=1 / entry.cost) for entry in priced])

    found = R.price_violations(R.Runs(data), broken_case)

    assert any("Orb of Alteration at 3 times its price lowers the mean cost" in line for line in found), found


def test_a_planner_that_ignores_the_price_file_breaks_the_scale_relation(monkeypatch, data, broken_case):
    """Misprice the ingredients: every offer costs 1 Chaos whatever the file says, so the cost does not follow the prices."""
    priced_by(monkeypatch, lambda priced: [dataclasses.replace(entry, cost=1.0) for entry in priced])

    found = R.scale_violations(R.Runs(data), broken_case)

    assert len(found) == len(R.SCALES) and all("every price times" in line for line in found), found


def test_a_planner_that_drops_an_offer_when_three_are_allowed_breaks_the_method_relation(monkeypatch, data, broken_case):
    """Drop an offer: with three or more offers the Orb of Augmentation is left out, so forbidding another orb brings it back."""
    priced_by(monkeypatch, lambda priced: [entry for entry in priced if len(priced) < 3 or entry.label != "Orb of Augmentation"])

    found = R.method_violations(R.Runs(data), broken_case)

    assert any("forbidding alteration-orb lowers the mean cost" in line for line in found), found


def test_a_planner_that_drops_an_offer_costs_more_than_a_guide_that_uses_it(monkeypatch, runs, data, broken_case):
    """Drop an offer: the planner never uses the Orb of Augmentation, and the guide that does is cheaper than its plan."""
    given = R.guides(runs, broken_case)  # the guides, by the rules as they are
    priced_by(monkeypatch, lambda priced: [entry for entry in priced if entry.label != "Orb of Augmentation"])

    found = R.guide_violations(R.Runs(data), broken_case, given)

    assert any("Orb of Augmentation > " in line for line in found), found


def test_a_planner_that_reads_the_tiers_upside_down_breaks_the_target_relation(monkeypatch, data, broken_case):
    """Misread the target: "tier 3 or better" is taken as "tier 3 or worse", so a wider tier range leaves fewer items that pass."""
    target_read_by(monkeypatch, data, R.tiers_upside_down)

    found = R.target_violations(R.Runs(data), broken_case)

    assert any("the looser target" in line for line in found), found


def test_a_planner_that_reads_the_tiers_upside_down_does_not_reach_the_target_in_the_simulator(monkeypatch, data, broken_case):
    """Misread the target: the plan stops on items of a worse tier, which the case's own target does not accept."""
    target_read_by(monkeypatch, data, R.tiers_upside_down)

    found = R.simulation_violations(R.Runs(data), broken_case)

    assert len(found) == 1, found


def test_the_breaks_are_undone(runs, data, broken_case):
    """After the broken planners the planner is itself again: a fresh run gives the shared run's plan."""
    assert R.Runs(data).cost(broken_case) == runs.cost(broken_case)
