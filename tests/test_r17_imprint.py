"""R17 end to end: the +2 Lightning rare Talisman made with the rare-Talisman imprint, on the real 3.29.3.3 dump (ticket #223).

"Done when" of #223: at the same prices the solver's route costs no more than the given route; the published odds match (the guide of
R17 publishes none, so its benchmark entry checks none); the beast's price is taken from the price file.

The quick tests read the target, its price file and the given route and make the plan's offers without solving (`solve_it=False`). The
benchmark entry solves the whole imprint loop (`run_route`), which is a heavy run, not a CI shard or a PC:

    python .github/scripts/heavy_dispatch.py run --ref BRANCH --runners 1 --timeout-minutes 60 \
        --command 'CRAFTING_HEAVY=1 uv run --no-sync pytest -q -p no:cacheprovider -s tests/test_r17_imprint.py -k benchmark'

Without `CRAFTING_HEAVY` the benchmark test skips, and without the cached dump the data fixture skips every test. It does not pass
yet: the exact walk of the imprint loop passed 2.76 million states in an hour and did not end (heavy run 43308613718); #223 stays open until
the solver can hold the held imprint (ADR-0060, "One held imprint is a number"; #817).
"""

import dataclasses
import os
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import Imprint, Restore, imprints_held_at_most
from crafting_system.cli import RouteError, load_route, make_plan
from crafting_system.cli._benchmark import BENCHMARKS, run_route
from crafting_system.config import find_project_root, load_config
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target, start_price_key

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "examples" / "targets" / "r17-lightning-talisman.yaml"
ROUTE = ROOT / "examples" / "routes" / "r17-lightning-talisman.yaml"
PRICES = ROOT / "tests" / "fixtures" / "prices" / "r17-allflame-2026-11-10.json"
ARACHNID, CROAKER = "Fenumal Plagued Arachnid", "Craicic Croaker"
HEAVY = pytest.mark.skipif(not os.environ.get("CRAFTING_HEAVY"), reason="heavy: set CRAFTING_HEAVY=1 (a heavy run of GitHub, not a CI shard or a PC)")


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def target(data):
    return load_target(TARGET, data)


@pytest.fixture(scope="module")
def prices():
    return load_price_file(PRICES)


@pytest.fixture(scope="module")
def plan(data, target, prices):
    return make_plan(data, target, prices, solve_it=False, judges_route=True)


def test_the_target_reads_its_own_price_file_and_the_start_talisman_is_priced_there(data, target, prices, plan):
    assert target.price_file is not None and Path(target.price_file).resolve() == PRICES.resolve()
    key = start_price_key(data, target)
    assert key == "Croaker Talisman, normal, item level 85"
    assert plan.start_price.chaos == prices.prices[key].chaos and plan.start_price.name == key


def test_each_imprint_costs_its_beast_at_the_price_of_the_price_file(data, prices, plan):
    imprints = {priced.offer.action.beast_name: priced for priced in plan.offers if isinstance(priced.offer.action, Imprint)}
    assert set(imprints) == {ARACHNID, CROAKER}  # the Croaker for a Magic Talisman, the Arachnid for a rare one (ADR-0034)
    for beast, priced in imprints.items():
        assert priced.offer.resources == {beast: 1}
        assert priced.cost == prices.prices[beast].chaos  # read from the file, never typed: it moves with the snapshot
    (restore,) = [priced for priced in plan.offers if isinstance(priced.offer.action, Restore)]
    assert restore.offer.resources == {} and 0 < restore.cost < 1e-3 * min(priced.cost for priced in imprints.values())  # the imprint was paid when made


def test_another_beast_price_moves_the_imprint_cost_and_a_missing_beast_leaves_it_unpriced(data, target, prices):
    dearer = dataclasses.replace(prices, prices={**prices.prices, ARACHNID: dataclasses.replace(prices.prices[ARACHNID], chaos=1.0)})
    cheap = make_plan(data, target, dearer, solve_it=False, judges_route=True)
    assert [priced.cost for priced in cheap.offers if priced.label == "Imprint with the Fenumal Plagued Arachnid"] == [1.0]

    without = dataclasses.replace(prices, prices={name: entry for name, entry in prices.prices.items() if name != ARACHNID})
    bare = make_plan(data, target, without, solve_it=False, judges_route=True)
    assert not [priced for priced in bare.offers if priced.label.startswith("Imprint with the Fenumal")]
    assert any(ARACHNID in limit.names for limit in bare.limits)
    with pytest.raises(RouteError, match="has no price: missing Fenumal Plagued Arachnid"):
        load_route(ROUTE, bare, data)


def test_the_given_route_reads_against_the_plan(data, plan):
    route = load_route(ROUTE, plan, data)
    done = {rule.do for rule in route.rules}
    assert {"Imprint with the Fenumal Plagued Arachnid", "Restore imprint 1", "Orb of Annulment", "Harvest Add Remove Lightning"} <= done
    assert any(rule.when.imprints == 1 for rule in route.rules) and any(rule.when.imprints == 0 for rule in route.rules)


def test_the_setting_max_imprints_reaches_the_offers(data, target, prices):
    with imprints_held_at_most(2):
        two = make_plan(data, target, prices, solve_it=False, judges_route=True)
    labels = {priced.label for priced in two.offers}
    assert {"Restore imprint 1", "Restore imprint 2"} <= labels


def test_the_guide_of_r17_publishes_no_odds():
    (bench,) = [bench for bench in BENCHMARKS if bench.id == "R17"]
    assert bench.odds == () and bench.outcomes == ()  # nothing to recompute: the post gives no number (docs/research/2026-10-30-5-reference-routes.md, R17)


@HEAVY
def test_the_benchmark_of_r17_finds_the_solver_no_dearer_than_the_guide(data, prices):
    (bench,) = [bench for bench in BENCHMARKS if bench.id == "R17"]
    config = load_config({})
    with imprints_held_at_most(config.max_imprints):
        entry, used = run_route(bench, data, find_project_root(), config, prices, None, heavy=True)
    print({key: entry[key] for key in ("solver", "given_route", "completed_route", "solver_not_dearer", "solver_not_dearer_than_completed", "timings_seconds")})
    assert entry["error"] is None and used is prices
    assert entry["solver_not_dearer"] is True
    if bench.completed is not None:
        assert entry["solver_not_dearer_than_completed"] is True
