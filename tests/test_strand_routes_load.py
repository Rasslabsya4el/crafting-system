"""The strand routes in today's route loader, with their strand words taken out (ticket #272).

`test_strand_routes.py` reads the files as text. This module goes further, on the real 3.29.3.3 dump: it takes the
strand words out of a test route and its target (the Orb of Remembrance and Unravelling are not in the catalog until B5-5
and B5-8, and the loader has no strand condition until B5-12), plans the target at a flat price of 1 chaos for every
currency, and reads the route with `parse_route`, so a `do` that is not an offer of the plan, a status condition that names
nothing, or a target the planner cannot reach is an error here.

S02, S11 and S13 pass. S12's rule is R05's, which `test_cli_routes_real.py` already plans. S01 cannot be planned before the
fossil set is a planner action (ticket #118): the test says so, so that the day it can be planned this test fails and
someone reads the route against the plan.

These plans solve the whole target, which takes minutes for the belt and the ring; run the module on GitHub
(`gh workflow run run.yml --ref <branch> -f command='uv run --no-sync pytest tests/test_strand_routes_load.py -q'`). Like every
real-data test it skips without the dump.
"""

import datetime
from pathlib import Path

import pytest
import yaml
from abstraction_support import real_game_data
from test_strand_routes import STRAND_ACTIONS, without_strand_words

from crafting_system.cli import make_plan
from crafting_system.cli._route import parse_route
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.targets import parse_target

ROOT = Path(__file__).resolve().parents[1]


class FlatPrices(dict):
    """Every currency costs 1 chaos."""

    def __contains__(self, name):
        return True

    def __getitem__(self, name):
        return PriceEntry(1.0, "test")

    def get(self, name, default=None):
        return PriceEntry(1.0, "test")


def flat_price_file() -> PriceFile:
    return PriceFile("Test", datetime.datetime(2026, 11, 1, tzinfo=datetime.UTC), 300.0, FlatPrices())


def without_strand_rules(text: str) -> str:
    """The route with every rule that uses a strand word removed, as the loader of today could read it."""
    document = yaml.safe_load(text)
    rules = [
        rule
        for rule in document["rules"]
        if rule["do"] not in STRAND_ACTIONS and not any(key.startswith("memory_strands") for key in rule.get("when", {}))
    ]
    return yaml.safe_dump({"name": document["name"], "rules": rules}, sort_keys=False)


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.mark.parametrize("stem", ["s02-fire-res-ring-showcase", "s11-remembrance-belt", "s13-unravelling-belt"])
def test_the_route_without_its_strand_rules_is_read_against_the_plan_of_its_target(stem, data):
    target = parse_target(
        without_strand_words((ROOT / "examples" / "targets" / f"{stem}.yaml").read_text(encoding="utf-8")),
        data,
        source=stem,
    )
    plan = make_plan(data, target, flat_price_file(), start_price=10.0)
    route_text = without_strand_rules((ROOT / "examples" / "routes" / f"{stem}.yaml").read_text(encoding="utf-8"))
    assert parse_route(route_text, plan, data, source=stem).rules


def test_s01_cannot_be_planned_until_the_fossil_set_is_a_planner_action(data):
    stem = "s01-es-ring-forum-guide"
    target = parse_target(
        without_strand_words((ROOT / "examples" / "targets" / f"{stem}.yaml").read_text(encoding="utf-8")),
        data,
        source=stem,
    )
    with pytest.raises(ValueError, match="fossil-set"):
        make_plan(data, target, flat_price_file(), start_price=10.0)
