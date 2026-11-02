"""R04 and R14 end to end through the CLI and `benchmark`, on the real 3.29.3.3 dump at the committed prices (ticket #70).

"Done when": the CLI returns both policies (R14 Hunter Thicket Bow, R04 Penetrating Arrow Quiver) with odds, mean and p90, and
`--verify` agrees; at the same prices the solver's mean is no more than each given route's; times and state counts are in the PR.

The graphs are R04's 177,242 states and 536 million transitions and R14's 816,153 states (minutes to half an hour, 6 to 9 GB), so
these tests run in a heavy run, not in a CI shard or on a PC:

    python .github/scripts/heavy_dispatch.py run --ref BRANCH --runners 4 --timeout-minutes 60 \
        --command 'CRAFTING_HEAVY=1 uv run --no-sync pytest -q -p no:cacheprovider tests/test_cli_r04_r14_heavy.py -k "<route>-<kind>"'

(`<route>` is R04 or R14 and `<kind>` `cli` or `benchmark`: four runners, each plans its route once.) Without `CRAFTING_HEAVY` they skip, and
without the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`) the data fixture skips.

The CLI runs WITHOUT `--exact`: the default budget of 60 seconds finds no approximate level (a route with an Attack/Caster metamod has none)
and the planner goes on to the packed solver (`make_plan`, ticket #70). The given route is the guide's with a last rule that restarts, so
its mean is finite; the guide's own route has gaps and is checked by `benchmark`, whose entry also holds the completed one.
"""

import contextlib
import datetime
import io
import json
import os
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from cli_support import read_json

from crafting_system.cli import main
from crafting_system.cli._benchmark import BENCHMARKS, run_route
from crafting_system.config import find_project_root, load_config
from crafting_system.prices import load_price_file

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
GOLDEN = json.loads((ROOT / "tests" / "golden" / "packed_values.json").read_text(encoding="utf-8"))["routes"]
FILES = {
    "R04": ("r04-penetrating-quiver", 9.0),
    "R14": ("r14-hunter-bow", 13.0),
}
HEAVY = pytest.mark.skipif(not os.environ.get("CRAFTING_HEAVY"), reason="heavy: set CRAFTING_HEAVY=1 (a heavy run of GitHub, not a CI shard or a PC)")
RUNS = int(os.environ.get("CRAFTING_VERIFY_RUNS", "300"))  # simulated crafts of --verify (a craft is thousands of uses)
P90_WIDTH = 0.05  # the certified bracket of the p90 is at most this share of it wide


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module", params=["R04", "R14"])
def route_id(request):
    return request.param


@pytest.fixture(scope="module")
def cli(tmp_path_factory, data, route_id):
    """The CLI's answer for one route: (exit code, JSON document, printed text), `--verify` and the completed given route included."""
    stem, _ = FILES[route_id]
    out = tmp_path_factory.mktemp(route_id) / "policy.json"
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        code = main(
            [str(ROOT / "examples" / "targets" / f"{stem}.yaml"), "--json", str(out), "--verify", "--runs", str(RUNS),
             "--route", str(ROOT / "examples" / "routes" / f"{stem}-restart.yaml")],
            data=data, prices=load_price_file(PRICES), env={}, today=datetime.date(2026, 11, 1),
        )  # fmt: skip
    return code, read_json(out), printed.getvalue()


@HEAVY
def test_the_default_budget_run_reaches_the_packed_solver_and_says_so(cli, route_id):
    _, document, _ = cli

    assert "packed solver" in document["note"] and "No approximate level exists" in document["note"]
    assert document["states_solved"] == GOLDEN[route_id]["states"]


@HEAVY
def test_the_command_returns_the_policy_with_odds_mean_and_a_certified_p90(cli, route_id):
    code, document, text = cli
    totals = document["totals"]
    start_price = FILES[route_id][1]

    assert code == 0
    assert totals["success_probability"]["value"] == pytest.approx(1.0)
    assert totals["mean_cost"]["value"] == pytest.approx(GOLDEN[route_id]["mean_remaining"] + start_price, rel=1e-9)
    assert totals["quantiles_resolved"] is True
    p90 = totals["p90"]
    assert p90["low"] <= p90["value"] <= p90["high"] and p90["high"] - p90["low"] <= P90_WIDTH * p90["value"]
    assert totals["mean_cost"]["value"] < p90["value"] < 4 * totals["mean_cost"]["value"]
    assert totals["p50"]["value"] < totals["mean_cost"]["value"] < p90["value"]
    assert document["states"] and "not resolved on the grid" not in text


@HEAVY
def test_verify_agrees(cli):
    code, document, _ = cli

    assert code == 0 and document["verification"]["agrees"] is True
    assert document["verification"]["runs"] == RUNS and document["verification"]["unfinished"] == 0


@HEAVY
def test_the_solver_is_no_dearer_than_the_guides_route_completed_with_a_restart(cli):
    _, document, _ = cli
    given = document["given_route"]

    assert given["gaps"] == [] and given["mean_cost"]["value"] is not None
    assert document["totals"]["mean_cost"]["value"] <= given["mean_cost"]["value"] * (1 + 1e-9)


@pytest.fixture(scope="module")
def bench(data, route_id):
    entry, _ = run_route(
        next(b for b in BENCHMARKS if b.id == route_id), data, find_project_root(), load_config({}), load_price_file(PRICES),
        datetime.date(2026, 11, 1), heavy=True,
    )  # fmt: skip
    return entry


@HEAVY
def test_benchmark_solves_the_route_and_compares_it_with_the_guides_route_as_written_and_completed(bench, route_id):
    assert bench["error"] is None
    assert bench["solver"]["mean"] == pytest.approx(GOLDEN[route_id]["mean_remaining"] + FILES[route_id][1], rel=1e-9)
    assert bench["solver"]["p90"] is not None
    assert bench["given_route"]["gaps"] > 0 and bench["given_route"]["mean"] is None  # the guide's own steps leave gaps: it never finishes with certainty
    assert bench["solver_not_dearer"] is True
    completed = bench["completed_route"]
    assert completed["gaps"] == 0 and completed["mean"] is not None
    assert bench["solver"]["mean"] <= completed["mean"] * (1 + 1e-9) and bench["solver_not_dearer_than_completed"] is True


@HEAVY
def test_benchmark_records_the_published_odds(bench, route_id):
    odds = bench["published_odds"]

    assert len(odds) == (5 if route_id == "R04" else 6)
    assert [row["matches"] for row in odds if row["published"] in ("25%", "33%", "50%")] == [True] * (1 if route_id == "R04" else 2)
