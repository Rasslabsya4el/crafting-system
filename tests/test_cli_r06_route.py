"""R06's given route on the real 3.29.3.3 dump, read against its target with nothing solved (ticket #901).

R06 is a reference craft that the planner cannot plan yet: its target asks for the Heavy Belt's Strength implicit and 20% Intrinsic
Catalyst quality; the quality is planned since #159, and `make_plan` refuses the base implicit (#516). Its route file holds the guide's steps 2 and 3;
step 4 (catalysts, Divine Orb, Blessed Orb, a bench craft) waits for route conditions on quality and the implicit roll. These check
that the refusal is still the reason R06 is not planned, and that the written rules read against the target's explicit mods and the
offers, so the file stays valid until it can be judged. They skip without the cached dump.
"""

import dataclasses
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.cli import load_route, make_plan
from crafting_system.planner import PlanError
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "examples" / "targets" / "r06-strength-heavy-belt.yaml"
ROUTE = ROOT / "examples" / "routes" / "r06-strength-heavy-belt.yaml"
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json"  # the week-one file (OR-44)
ROUTE_ACTIONS = {"Deafening Essence of Rage", "Exalted Orb", "Orb of Annulment"}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def target(data):
    return load_target(TARGET, data)


def test_r06_is_not_planned_while_the_planner_refuses_its_implicit(data, target):
    assert target.implicits and target.quality is not None
    # the catalyst quality is planned since #159; the base implicit is refused, as an implicit that is not an Eldritch one (#835)
    with pytest.raises(PlanError, match="implicit that is not an Eldritch one"):
        make_plan(data, target, load_price_file(PRICES), solve_it=False)


def test_without_its_implicit_r06_is_offered_the_intrinsic_catalyst_alone_of_the_catalysts(data, target):
    # the target asks for 20% Intrinsic quality: the Intrinsic Catalyst is offered, and no catalyst of another type, which would restart it (#159)
    quality_only = dataclasses.replace(target, implicits=(), actions=("catalyst",))  # named: the classic offers of a module's tests hold no catalyst
    plan = make_plan(data, quality_only, load_price_file(PRICES), solve_it=False, start_price=1.0)
    catalysts = {priced.label for priced in plan.offers if priced.label.endswith("Catalyst")}
    assert catalysts == {"Intrinsic Catalyst"}


def test_the_route_reads_against_the_explicit_mods_and_the_offers(data, target):
    explicit = dataclasses.replace(target, implicits=(), quality=None)
    plan = make_plan(data, explicit, load_price_file(PRICES), solve_it=False, start_price=1.0)
    route = load_route(ROUTE, plan, data)
    assert route.skip_refused
    assert ROUTE_ACTIONS <= {rule.do for rule in route.rules}
    assert ROUTE_ACTIONS <= {priced.label for priced in plan.offers}
