"""R25 and R28 end to end through `benchmark`, on the real 3.29.3.3 dump at the committed prices (ticket #225).

"Done when" (#225, as #223): at the same prices the solver's route costs no more than the given route and the published odds match (the
two guides publish none); the answer is marked approximate and its interval over alpha is shown; the plan equals the guide's route or is
cheaper. R25 is the triple tier-1 prefix Vaal Regalia by overlapping pairs, R28 the +2 Onyx Amulet whose five mods are made one by one and
recombined. Each plan is the product of the target and its second items solved at the five readings of alpha, minutes on a runner, so
these tests run in a heavy run, not in a CI shard or on a PC:

    python .github/scripts/heavy_dispatch.py run --ref BRANCH --runners 2 --timeout-minutes 60 \
        --command 'CRAFTING_ROUTES=R25 CRAFTING_HEAVY=1 uv run --no-sync pytest -q -p no:cacheprovider tests/test_cli_r25_r28_heavy.py'

(`CRAFTING_ROUTES` is `R25`, `R28` or both.) The recorded numbers are `tests/golden/donor_values_<route>.json` (`UPDATE_GOLDEN=1` writes them
in the same run). Without `CRAFTING_HEAVY` they skip, and without the cached dump the data fixture skips.
"""

import json
import os
from pathlib import Path

import golden_diff
import pytest
from abstraction_support import real_game_data

from crafting_system.cli._benchmark import BENCHMARKS, run_route
from crafting_system.config import find_project_root, load_config
from crafting_system.prices import load_price_file

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-11-10.json"
GOLDEN = ROOT / "tests" / "golden"  # donor_values_<route>.json, one file a route so that two runners never write one file
HEAVY = pytest.mark.skipif(not os.environ.get("CRAFTING_HEAVY"), reason="heavy: set CRAFTING_HEAVY=1 (a heavy run of GitHub, not a CI shard or a PC)")


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module", params=os.environ.get("CRAFTING_ROUTES", "R25,R28").split(","))
def route_id(request):
    return request.param


@pytest.fixture(scope="module")
def entry(data, route_id):
    bench = next(each for each in BENCHMARKS if each.id == route_id)
    found, _ = run_route(bench, data, find_project_root(), load_config({}), load_price_file(PRICES), None, heavy=True)
    return found


@HEAVY
def test_the_benchmark_plans_the_route_and_judges_the_guide_with_no_error(entry):
    assert entry["error"] is None, entry["error"]
    assert entry["solver"]["success"] == pytest.approx(1.0)
    assert entry["given_route"]["gaps"] == 0
    assert entry["given_route"]["success"] == pytest.approx(1.0)


@HEAVY
def test_the_solver_is_no_dearer_than_the_guide_at_the_same_prices(entry):
    assert entry["solver_not_dearer"] is True
    assert entry["solver"]["mean"] <= entry["given_route"]["mean"] * (1 + 1e-9)


@HEAVY
def test_the_answer_is_approximate_and_shows_its_interval_over_alpha(entry):
    interval = entry["interval"]
    assert interval is not None and interval["approximate"] is True
    assert [axis["axis"] for axis in interval["rule_axes"]] == ["recombinator.alpha"]
    assert len(interval["readings"]) == 5
    spread = interval["plan_interval"]
    assert spread["best"]["value"] <= interval["plan_cost"]["value"] <= spread["worst"]["value"]
    assert interval["plan_cost"]["value"] == pytest.approx(entry["solver"]["mean"], rel=1e-9)
    assert interval["recombinations"] is not None and interval["recombinations"]["expected"]["value"] > 0


@HEAVY
def test_the_recorded_numbers(entry, route_id):
    found = {
        "solver_mean": entry["solver"]["mean"],
        "given_route_mean": entry["given_route"]["mean"],
        "interval": [row["plan_cost"]["value"] for row in entry["interval"]["readings"]],
        "without_recombinators": None if entry["interval"]["without_recombinators"] is None else entry["interval"]["without_recombinators"]["value"],
    }
    path = GOLDEN / f"donor_values_{route_id}.json"
    if os.environ.get("UPDATE_GOLDEN"):
        path.write_text(json.dumps(found, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert path.exists(), f"no recorded numbers {path.name}; run with UPDATE_GOLDEN=1"
    golden_diff.check_objects(json.loads(path.read_text(encoding="utf-8")), found, f"{route_id}: the numbers differ from {path.name}", rel=1e-9)
