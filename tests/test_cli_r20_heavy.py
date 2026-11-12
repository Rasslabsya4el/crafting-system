"""R20 end to end through the CLI, on the real 3.29.3.3 dump at its committed prices (ticket #150).

"Done when": R20 runs, `--verify` passes, the solver's mean is no more than the given route's, and the guide author's 16% and 15% are
reported beside ours (the chances themselves are pinned by the quick `tests/test_cli_r20_real.py`; this run prints them beside the
route's means). The plan reforges an influenced rare helmet with the junk kept for the bench and the Matron, so it is a heavy run, not
a CI shard or a PC:

    python .github/scripts/heavy_dispatch.py run --no-wait --ref BRANCH --runners 1 --timeout-minutes 60 \
        --command 'CRAFTING_HEAVY=1 uv run --no-sync pytest -q -s -p no:cacheprovider tests/test_cli_r20_heavy.py'

Without `CRAFTING_HEAVY` they skip, and without the cached dump the data fixture skips. The CLI runs with its default budget.
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
from test_cli_r20_real import GUIDE

from crafting_system.cli import main
from crafting_system.prices import load_price_file

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "b2-r20-beasts-2026-11-12.json"
STEM = "r20-rf-helmet"
HEAVY = pytest.mark.skipif(not os.environ.get("CRAFTING_HEAVY"), reason="heavy: set CRAFTING_HEAVY=1 (a heavy run of GitHub, not a CI shard or a PC)")
RUNS = int(os.environ.get("CRAFTING_VERIFY_RUNS", "300"))


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def cli(tmp_path_factory, data):
    """The CLI's answer for R20: (exit code, JSON document, printed text), `--verify` and the given route included."""
    out = tmp_path_factory.mktemp("r20") / "policy.json"
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        code = main(
            [str(ROOT / "examples" / "targets" / f"{STEM}.yaml"), "--json", str(out), "--verify", "--runs", str(RUNS), "--progress",
             "--route", str(ROOT / "examples" / "routes" / f"{STEM}.yaml")],
            data=data, prices=load_price_file(PRICES), env={}, today=datetime.date(2026, 11, 12),
        )  # fmt: skip
    print(f"R20: the CLI exit {code} (its times are in the --progress lines)", file=sys.stderr)
    print(printed.getvalue(), file=sys.stderr)
    return code, read_json(out), printed.getvalue()


@HEAVY
def test_the_command_returns_the_policy_with_odds_and_mean(cli):
    code, document, _ = cli
    totals = document["totals"]
    print(f"R20: states solved {document.get('states_solved')}, mean {totals['mean_cost']['value']}", file=sys.stderr)
    assert code == 0
    assert totals["success_probability"]["value"] == pytest.approx(1.0)
    assert document["states"]


@HEAVY
def test_verify_agrees(cli):
    code, document, _ = cli
    assert code == 0 and document["verification"]["agrees"] is True
    assert document["verification"]["runs"] == RUNS and document["verification"]["unfinished"] == 0


@HEAVY
def test_the_solver_is_no_dearer_than_the_given_route(cli):
    _, document, _ = cli
    given = document["given_route"]
    print(f"R20: given route mean {given['mean_cost']['value']}, gaps {len(given['gaps'])}", file=sys.stderr)
    for step, (any_tier, top_tier) in GUIDE.items():
        print(f"R20 {step}: the guide says {any_tier:.0%}{'' if top_tier is None else f' ({top_tier:.0%} top tier)'}; ours: tests/test_cli_r20_real.py", file=sys.stderr)
    assert given["gaps"] == [] and given["mean_cost"]["value"] is not None
    assert document["totals"]["mean_cost"]["value"] <= given["mean_cost"]["value"] * (1 + 1e-9)


@HEAVY
def test_the_approximate_inputs_are_listed(cli):
    _, document, text = cli
    claims = {entry["claim"] if isinstance(entry, dict) else entry for entry in document["approximate_inputs"]}
    print(f"approximate inputs: {sorted(claims)}", file=sys.stderr)
    assert claims and "Approximate inputs" in text
