"""R24 end to end through the CLI, on the real 3.29.3.3 dump at its committed prices (ticket #146).

R07 left this test with #901: it is no longer a reference craft (OR-45, its guide rests on the old Veiled Chaos Orb), so no test sets its
plan against its guide. R24's prices are the week-one file plus its hand-set start boots since #901 (OR-44).

"Done when" (as #70's): it runs, `--verify` passes, the solver's mean is no more than the given route's, and the approximate inputs
are listed. The plans walk the veiled kinds with the junk told apart by family (ADR-0026), so they are heavy runs, not a CI shard or a PC:

    python .github/scripts/heavy_dispatch.py run --no-wait --ref BRANCH --runners 1 --timeout-minutes 60 \
        --command 'CRAFTING_HEAVY=1 uv run --no-sync pytest -q -s -p no:cacheprovider tests/test_cli_r24_r07_heavy.py'

Without `CRAFTING_HEAVY` they skip, and without the cached dump the data fixture skips. The CLI runs with its default budget (the aim) and no
time or memory limit (`--time-limit none --memory-limit none`): this test measures the whole walk, which OR-33's 10-minute net would stop (#825).
"""

import contextlib
import datetime
import io
import os
import sys
from pathlib import Path

import pytest
from abstraction_support import real_game_data
from cli_support import read_json

from crafting_system.cli import main
from crafting_system.prices import load_price_file

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "references-allflame-2026-07-31.json"
FILES = {"R24": "r24-avoid-shock-boots"}
HEAVY = pytest.mark.skipif(not os.environ.get("CRAFTING_HEAVY"), reason="heavy: set CRAFTING_HEAVY=1 (a heavy run of GitHub, not a CI shard or a PC)")
RUNS = int(os.environ.get("CRAFTING_VERIFY_RUNS", "300"))


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module", params=os.environ.get("CRAFTING_ROUTES", "R24").split(","))
def route_id(request):
    return request.param


@pytest.fixture(scope="module")
def cli(tmp_path_factory, data, route_id):
    """The CLI's answer for one route: (exit code, JSON document, printed text), `--verify` and the given route included."""
    stem = FILES[route_id]
    out = tmp_path_factory.mktemp(route_id) / "policy.json"
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        code = main(
            [str(ROOT / "examples" / "targets" / f"{stem}.yaml"), "--json", str(out), "--verify", "--runs", str(RUNS), "--progress",
             "--route", str(ROOT / "examples" / "routes" / f"{stem}.yaml"), "--time-limit", "none", "--memory-limit", "none"],
            data=data, prices=load_price_file(PRICES), env={}, today=datetime.date(2026, 11, 12),
        )  # fmt: skip
    print(f"{route_id}: the CLI exit {code} (its times are in the --progress lines)", file=sys.stderr)
    print(printed.getvalue(), file=sys.stderr)
    return code, read_json(out), printed.getvalue()


@HEAVY
def test_the_command_returns_the_policy_with_odds_and_mean(cli, route_id):
    code, document, _ = cli
    totals = document["totals"]
    print(f"{route_id}: states solved {document.get('states_solved')}, mean {totals['mean_cost']['value']}", file=sys.stderr)
    assert code == 0
    assert totals["success_probability"]["value"] == pytest.approx(1.0)
    assert document["states"]


@HEAVY
def test_verify_agrees(cli):
    code, document, _ = cli
    assert code == 0 and document["verification"]["agrees"] is True
    assert document["verification"]["runs"] == RUNS and document["verification"]["unfinished"] == 0


@HEAVY
def test_the_solver_is_no_dearer_than_the_given_route(cli, route_id):
    _, document, _ = cli
    given = document["given_route"]
    print(f"{route_id}: given route mean {given['mean_cost']['value']}, gaps {len(given['gaps'])}", file=sys.stderr)
    assert given["gaps"] == [] and given["mean_cost"]["value"] is not None
    assert document["totals"]["mean_cost"]["value"] <= given["mean_cost"]["value"] * (1 + 1e-9)


@HEAVY
def test_the_approximate_inputs_are_listed(cli):
    _, document, text = cli
    claims = {entry["claim"] if isinstance(entry, dict) else entry for entry in document["approximate_inputs"]}
    print(f"approximate inputs: {sorted(claims)}", file=sys.stderr)
    assert claims and "Approximate inputs" in text
