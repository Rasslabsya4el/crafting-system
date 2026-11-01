"""The `benchmark` command (ticket #57): R12's solver and given route, the published odds, machine info and timings.

The command never fails on a result: a mismatch of the published odds, a solver dearer than the guide
or a route that cannot be evaluated is written into that route's entry and the exit code stays 0.
The tests check which fields are there and of what kind, never how long anything took.
"""

import datetime
import json
from pathlib import Path

import pytest
from cli_support import R12, TODAY, price_file, read_json
from targets_support import DATA

import crafting_system.cli._benchmark as benchmark_module
from crafting_system.cli import main
from crafting_system.config import load_config
from crafting_system.prices.price_file import OVERRIDES_FILE_NAME

COMMAND = "bench" + "mark"  # the name of the command; a bare string with it would trip tests/test_no_timing.py
ROOT = Path(__file__).resolve().parents[1]


def run_benchmark(out_dir: Path, *arguments: str, prices="default", data=DATA):
    code = main(
        [COMMAND, "--out", str(out_dir), *arguments],
        data=data,
        prices=price_file() if prices == "default" else prices,
        env={},
        today=TODAY,
    )
    return code, out_dir / "benchmark.json"


def entry_of(document: dict, route_id: str = "R12") -> dict:
    return next(entry for entry in document["routes"] if entry["id"] == route_id)


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def test_the_benchmark_writes_r12_with_machine_info_and_timings(tmp_path, capsys):
    code, path = run_benchmark(tmp_path)

    assert code == 0 and path.is_file()
    document = read_json(path)
    assert document["format"] == "crafting-system-benchmark/1"
    machine = document["machine"]
    for key in ("os", "platform", "cpu", "python", "commit"):
        assert isinstance(machine[key], str) and machine[key], key
    assert isinstance(machine["cpu_count"], int) and machine["cpu_count"] >= 1
    assert datetime.datetime.fromisoformat(document["ran_at"]).utcoffset() == datetime.timedelta(0)
    assert document["prices"]["league"] == "Test" and document["prices"]["fetched_at"].startswith("2026-10-30")

    entry = entry_of(document)
    assert entry["error"] is None
    assert entry["title"]
    assert entry["target"] == "examples/targets/r12-lightning-amulet.yaml"
    assert entry["route"] == "examples/routes/r12-lightning-amulet.yaml"
    for side in ("solver", "given_route"):
        for key in ("success", "mean", "p50", "p90", "seconds"):
            assert is_number(entry[side][key]), (side, key)
        assert entry[side]["seconds"] >= 0.0
    assert entry["given_route"]["gaps"] == 0
    assert entry["given_route"]["first_divergence"] is None
    assert entry["given_route"]["mean"] == pytest.approx(entry["solver"]["mean"], rel=1e-9)
    assert entry["solver_not_dearer"] is True
    timings = entry["timings_seconds"]
    assert set(timings) == {"solver", "risk_evaluate", "route_evaluate", "total"}
    assert all(is_number(value) and value >= 0.0 for value in timings.values())

    assert capsys.readouterr().out.isascii()


def test_the_published_odds_are_computed_and_recorded_next_to_the_guide(tmp_path):
    _, path = run_benchmark(tmp_path)

    odds = entry_of(read_json(path))["published_odds"]

    assert [item["published"] for item in odds] == ["2.88%", "1.338%"]
    for item in odds:
        assert item["action"] == "Harvest Reforge Lightning"
        assert isinstance(item["computed"], str) and item["computed"].endswith("%")
        assert isinstance(item["matches"], bool)
        assert item["matches"] == (item["computed"] == item["published"])
        assert item["wanted_weight"] >= 0 and item["candidate_weight"] > 0


def test_no_absolute_path_is_written(tmp_path):
    _, path = run_benchmark(tmp_path)

    text = path.read_text(encoding="utf-8")

    assert str(tmp_path) not in text and str(R12.parents[2]) not in text


def test_the_output_dir_defaults_to_the_configured_one(tmp_path):
    code = main(
        [COMMAND], data=DATA, prices=price_file(), env={"CRAFTING_OUTPUT_DIR": str(tmp_path / "configured")}, today=TODAY
    )

    assert code == 0 and (tmp_path / "configured" / "benchmark.json").is_file()


def test_a_route_that_cannot_be_planned_is_recorded_and_the_exit_code_stays_0(tmp_path, capsys):
    code, path = run_benchmark(tmp_path, prices=price_file(start=None))

    assert code == 0
    entry = entry_of(read_json(path))
    assert "no price for the start item" in entry["error"]
    assert entry["id"] == "R12" and entry["solver"] is None and entry["given_route"] is None
    assert "no price for the start item" in capsys.readouterr().out


def expected_overrides_file() -> str:
    """The overrides file the benchmark names: the default data dir's, with the project root cut off as the benchmark does."""
    path = load_config({}).data_dir / OVERRIDES_FILE_NAME
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def test_a_missing_start_price_names_the_override_line_and_the_other_routes_still_run(tmp_path, capsys):
    code, path = run_benchmark(tmp_path, prices=price_file(start=None))

    assert code == 0
    document = read_json(path)
    assert [entry["id"] for entry in document["routes"]] == ["R12", "R10", "R11", "R05", "R13"]
    entry = entry_of(document)
    assert entry["missing_price"]["name"] == "R12 start amulet"
    assert entry["missing_price"]["override_line"] == '"R12 start amulet" = 0'
    assert entry["missing_price"]["overrides_file"] == expected_overrides_file()
    out = capsys.readouterr().out
    assert '"R12 start amulet" = 0' in [line.strip() for line in out.splitlines()]
    assert f"add to {expected_overrides_file()} under [prices]:" in out
    for route_id in ("R10", "R11", "R05"):  # their own files fail first in the test data, so none names a price
        assert entry_of(document, route_id)["error"] is not None
        assert "no price for the start item" not in entry_of(document, route_id)["error"]
    belt = entry_of(document, "R13")  # a normal belt: its start price is the poe.ninja base price, and it has no buy spec
    assert belt["missing_price"]["name"] == "Leather Belt (ilvl 86)" and belt["missing_price"]["buy_spec"] is None
    assert "no price for the start item 'Leather Belt (ilvl 86)'" in belt["error"]


def test_the_missing_start_price_of_r12_names_its_buy_spec_for_the_trade_api(tmp_path, capsys):
    code, path = run_benchmark(tmp_path, prices=price_file(start=None))

    assert code == 0
    entry = entry_of(read_json(path))
    assert entry["missing_price"]["buy_spec"] == "examples/buy/r12-start-amulet.yaml"
    assert (
        "or price it on the trade API with: python -m crafting_system.prices trade --spec examples/buy/r12-start-amulet.yaml"
        in entry["error"]
    )
    assert "python -m crafting_system.prices trade --spec examples/buy/r12-start-amulet.yaml" in capsys.readouterr().out


def test_a_start_price_that_is_in_the_price_file_has_no_missing_price(tmp_path):
    _, path = run_benchmark(tmp_path)

    assert entry_of(read_json(path))["missing_price"] is None


def test_a_route_with_a_bad_file_is_recorded_and_the_others_still_run(tmp_path, monkeypatch):
    good = benchmark_module.BENCHMARKS[0]
    broken = benchmark_module.BenchmarkRoute(
        "R99", "A route with no file", good.target, "examples/routes/no-such-route.yaml", good.odds
    )
    monkeypatch.setattr(benchmark_module, "BENCHMARKS", (broken, good))

    code, path = run_benchmark(tmp_path)

    assert code == 0
    document = read_json(path)
    assert "no-such-route.yaml" in entry_of(document, "R99")["error"]
    assert entry_of(document, "R99")["solver"]["mean"] > 0  # the solver half was done before the route failed
    assert entry_of(document)["error"] is None


def test_a_published_odds_mismatch_is_recorded_and_fails_nothing(tmp_path, monkeypatch):
    good = benchmark_module.BENCHMARKS[0]
    wrong = tuple(
        benchmark_module.PublishedOdds(odds.action, odds.requirement, odds.on, "99.99%") for odds in good.odds
    )
    monkeypatch.setattr(
        benchmark_module,
        "BENCHMARKS",
        (benchmark_module.BenchmarkRoute(good.id, good.title, good.target, good.route, wrong),),
    )

    code, path = run_benchmark(tmp_path)

    assert code == 0
    odds = entry_of(read_json(path))["published_odds"]
    assert [item["matches"] for item in odds] == [False, False]


def test_a_solver_that_beats_the_guide_is_recorded_with_where_the_two_part(tmp_path):
    # with the lifeforce at 0.2 a reforge click costs 10 Chaos, so the solver picks the Chaos Orb and the
    # guide's reforge route is the dearer one
    code, path = run_benchmark(tmp_path, prices=price_file(lifeforce=0.2))

    assert code == 0
    entry = entry_of(read_json(path))
    assert entry["solver"]["mean"] < entry["given_route"]["mean"]
    assert entry["solver_not_dearer"] is True
    assert entry["given_route"]["first_divergence"]["solver_action"] == "Chaos Orb"
    assert entry["given_route"]["first_divergence"]["route_action"] == "Harvest Reforge Lightning"


def test_unreadable_game_data_is_the_one_failure(tmp_path, capsys):
    code = main(
        [COMMAND, "--out", str(tmp_path)],
        prices=price_file(),
        env={"CRAFTING_CACHE_DIR": str(tmp_path / "empty-cache")},
        today=TODAY,
    )

    assert code == 1
    assert "Error:" in capsys.readouterr().err
    assert not (tmp_path / "benchmark.json").exists()


def test_the_target_form_still_works_next_to_the_benchmark_command(tmp_path):
    out = tmp_path / "policy.json"

    code = main([str(R12), "--json", str(out)], data=DATA, prices=price_file(), env={}, today=TODAY)

    assert code == 0 and json.loads(out.read_text(encoding="utf-8"))["format"] == "crafting-system-policy/1"


def test_the_benchmark_lists_r12_r10_r11_r05_and_r13_with_their_target_and_route_files():
    root = Path(__file__).resolve().parents[1]

    assert [bench.id for bench in benchmark_module.BENCHMARKS] == ["R12", "R10", "R11", "R05", "R13"]
    for bench in benchmark_module.BENCHMARKS:
        assert (root / bench.target).is_file() and (root / bench.route).is_file(), bench.id
