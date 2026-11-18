"""R06's given route on the real 3.29.3.3 dump, read against its target with nothing solved (ticket #901).

R06's target asks for the Heavy Belt's Strength implicit at its top roll and 20% Intrinsic Catalyst quality: the quality is planned since
#159 and the implicit since #1231, both as finishes after the mods (the Blessed Orb: `+(25-35) to Strength` at 35, a chance of 1/11 a use, so
11 orbs on average). R06 is not a planned reference yet: its start belt has no price (#483, #515), and its route file holds the guide's steps 2
and 3; step 4 (catalysts, Divine Orb, Blessed Orb, a bench craft) waits for route conditions on quality and the implicit roll (#1232). These
check that the missing price is now the reason R06 is not planned, that both finishes are planned, and that the written rules read against
the target's explicit mods and the offers, so the file stays valid until it can be judged. They skip without the cached dump.
"""

import dataclasses
from fractions import Fraction
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


def test_r06_is_refused_only_for_its_start_price(data, target):
    assert target.implicits and target.quality is not None
    with pytest.raises(PlanError, match="no price for the start item"):  # #483, #515: the implicit and the quality are planned (#159, #1231)
        make_plan(data, target, load_price_file(PRICES), solve_it=False)


def test_with_a_start_price_r06_finishes_its_implicit_with_eleven_blessed_orbs_and_its_quality_with_catalysts(data, target):
    named = ("catalyst", "blessed-orb", "exalted-orb")  # named: the classic offers of a module's tests hold neither finish's method
    plan = make_plan(data, dataclasses.replace(target, actions=named), load_price_file(PRICES), solve_it=False, start_price=1.0)
    implicit = plan.implicit_finish
    assert implicit is not None and implicit.orb.label == "Blessed Orb" and implicit.chance == Fraction(1, 11) and implicit.uses == 11
    assert plan.quality_finish is not None and plan.quality_finish.catalyst.label == "Intrinsic Catalyst"
    assert not any(priced.label in ("Blessed Orb", "Intrinsic Catalyst") for priced in plan.offers)  # the mods are planned without either
    (said,) = [limit for limit in plan.limits if limit.kind == "implicit-finish"]
    assert "+(25-35) to Strength rolls 35 or more" in said.why


def test_without_its_implicit_r06_finishes_its_quality_with_the_intrinsic_catalyst_alone_of_the_catalysts(data, target):
    # the target asks for 20% Intrinsic quality: it is finished after the mods with the Intrinsic Catalyst, and no catalyst of another type, which
    # would restart it, is offered (#159)
    named = ("catalyst", "exalted-orb")  # named: the classic offers of a module's tests hold no catalyst
    plan = make_plan(data, dataclasses.replace(target, implicits=(), actions=named), load_price_file(PRICES), solve_it=False, start_price=1.0)
    assert plan.quality_finish is not None and plan.quality_finish.catalyst.label == "Intrinsic Catalyst"
    assert not any(priced.label.endswith("Catalyst") for priced in plan.offers)  # the mods are planned without the quality
    (other,) = [limit for limit in plan.limits if limit.kind == "quality-type"]
    assert "Intrinsic Catalyst" not in other.labels and "Tempering Catalyst" in other.labels


def test_the_route_reads_against_the_explicit_mods_and_the_offers(data, target):
    explicit = dataclasses.replace(target, implicits=(), quality=None)
    plan = make_plan(data, explicit, load_price_file(PRICES), solve_it=False, start_price=1.0)
    route = load_route(ROUTE, plan, data)
    assert route.skip_refused
    assert ROUTE_ACTIONS <= {rule.do for rule in route.rules}
    assert ROUTE_ACTIONS <= {priced.label for priced in plan.offers}
