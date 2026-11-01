"""The strand routes in today's route loader, with their strand words taken out (ticket #272).

`test_strand_routes.py` reads the files as text. This module goes further, on the real 3.29.3.3 dump: it takes the
strand words out of a test route and its target (the Orb of Remembrance and Unravelling are not in the catalog until B5-5
and B5-8, and the loader has no strand condition until B5-12), builds the plan of the target at a flat price of 1 chaos for
every currency, and reads the route with `parse_route`, so a `do` that is not an offer of the plan or a status condition
that names nothing is an error here.

The plan is built by `make_plan` with the solve left out (the offers, their prices, the abstraction and the start state
are the real ones; the solution is empty). `parse_route` reads only those, never the policy. The solve is what a CI
slot did not carry: the first version of this module solved the whole target of S02, S11 and S13, and the runner died with
"the runner has received a shutdown signal" before the first plan finished, after 12 minutes in a heavy run (41323663427) and
14 minutes in a CI shard (41319160989), on Windows the slot hit its 25 minute limit. So this module does not check that
the planner reaches these targets; `test_cli_routes_real.py` and `test_cli_r13_real.py` solve R05 and R13, whose targets
S12 and S11/S13 reuse.

S02, S11 and S13 are checked (the files wait in docs/research/2026-11-01-strand-routes-files/ until B5-12, #292, teaches the loaders the strand words; the parse-all tests of examples/ must not meet them). S12's rule is R05's, which `test_cli_routes_real.py` already plans. S01 is not read here: its fossil set is opt-in since the merge of main and its metamod lock is never offered (see
the route's header).

Like every real-data test it skips without the dump.
"""

import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from abstraction_support import real_game_data
from test_strand_routes import STRAND_ACTIONS, without_strand_words

from crafting_system.cli import _plan, make_plan
from crafting_system.cli._route import parse_route
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.solver import Solution
from crafting_system.targets import parse_target

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "docs" / "research" / "2026-11-01-strand-routes-files"
CHECKED = ["s02-fire-res-ring-showcase", "s11-remembrance-belt", "s13-unravelling-belt"]


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


@pytest.fixture
def no_solve(monkeypatch):
    """`make_plan` up to the solve, then a plan with an empty solution and no risk (see the module docstring)."""

    def solved_nothing(start):
        return Solution({start: 0.0}, {}, 0.0)

    def solve_whole(model, starts, **_):
        return solved_nothing(model.start)

    def solve_pruned_nothing(abstraction, start, priced, item, **_):
        return SimpleNamespace(solution=solved_nothing(start), twins=(), inapplicable=(), bounded=())

    monkeypatch.setattr(_plan, "solve", solve_whole)
    monkeypatch.setattr(_plan, "solve_pruned", solve_pruned_nothing)
    monkeypatch.setattr(_plan, "evaluate_risk", lambda *_: None)


@pytest.mark.parametrize("stem", CHECKED)
def test_the_route_without_its_strand_rules_is_read_against_the_offers_of_its_target(stem, data, no_solve):
    target = parse_target(
        without_strand_words((FILES / "targets" / f"{stem}.yaml").read_text(encoding="utf-8")),
        data,
        source=stem,
    )
    plan = make_plan(data, target, flat_price_file(), start_price=10.0)
    assert plan.offers
    route_text = without_strand_words_in_rules((FILES / "routes" / f"{stem}.yaml").read_text(encoding="utf-8"))
    assert parse_route(route_text, plan, data, source=stem).rules
