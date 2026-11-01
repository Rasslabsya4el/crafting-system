"""The strand routes in today's route loader, with their strand words taken out (ticket #272).

`test_strand_routes.py` reads the files as text. This module goes further, on the real 3.29.3.3 dump: it takes the
strand words out of a test route and its target (the Orb of Remembrance and Unravelling are not in the catalog until B5-5
and B5-8, and the loader has no strand condition until B5-12), plans the target at a flat price of 1 chaos for every
currency, and reads the route with `parse_route`, so a `do` that is not an offer of the plan, a status condition that names
nothing, or a target the planner cannot reach is an error here.

S02, S11 and S13 are checked (the files wait in docs/research/2026-11-01-strand-routes-files/ until B5-12, #292, teaches the loaders the strand words; the parse-all tests of examples/ must not meet them). S12's rule is R05's, which `test_cli_routes_real.py` already plans. S01 is not planned here: its fossil set is opt-in since the merge of main and its metamod lock is never offered (see
the route's header), and nobody has sized its plan.

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
FILES = ROOT / "docs" / "research" / "2026-11-01-strand-routes-files"


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


def without_strand_words_in_rules(text: str) -> str:
    """The route as the loader of today could read it: a rule that does a strand action is removed, and the strand
    conditions of the others are dropped (S02's Transmutation, which waits for 80 strands, then applies to every normal ring)."""
    document = yaml.safe_load(text)
    rules = []
    for rule in document["rules"]:
        if rule["do"] in STRAND_ACTIONS:
            continue
        when = {key: value for key, value in rule.get("when", {}).items() if not key.startswith("memory_strands")}
        rules.append({"when": when, "do": rule["do"]} if when else {"do": rule["do"]})
    return yaml.safe_dump({"name": document["name"], "rules": rules}, sort_keys=False)


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.mark.parametrize("stem", ["s02-fire-res-ring-showcase", "s11-remembrance-belt", "s13-unravelling-belt"])
def test_the_route_without_its_strand_rules_is_read_against_the_plan_of_its_target(stem, data):
    target = parse_target(
        without_strand_words((FILES / "targets" / f"{stem}.yaml").read_text(encoding="utf-8")),
        data,
        source=stem,
    )
    plan = make_plan(data, target, flat_price_file(), start_price=10.0)
    route_text = without_strand_words_in_rules((FILES / "routes" / f"{stem}.yaml").read_text(encoding="utf-8"))
    assert parse_route(route_text, plan, data, source=stem).rules
