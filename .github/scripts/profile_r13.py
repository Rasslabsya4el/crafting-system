"""Where the time of R13's two real test files goes (ticket #717): one phase per step the tests take, timed, some under cProfile.

    python .github/scripts/profile_r13.py --phases plan,route_object,route_packed --out DIR
    python .github/scripts/profile_r13.py --phases main --out DIR

Phases (each prints its seconds and writes `<phase>.txt` with the cProfile table when the phase is profiled, and `phases.json`):
`plan` (make_plan, object, risk: the `plan` fixture of test_cli_r13_real.py and half of `both`), `plan_packed` (packed, with risk: the
other half of `both`), `plan_packed_norisk`, `route_object` (evaluate_route of the given route on the object plan, profiled),
`route_packed`, `main` (the CLI of the `command` fixture: `--verify --runs 8 --route`, with `--progress` stage lines).
Never run on a PC. Run by `.github/scripts/heavy_dispatch.py`.
"""

import argparse
import contextlib
import cProfile
import datetime
import io
import json
import pstats
import sys
import time
from pathlib import Path

from crafting_system.cli import evaluate_route, load_route, main, make_plan
from crafting_system.data import load_game_data
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
TARGET = ROOT / "examples" / "targets" / "r13-life-resist-belt.yaml"
ROUTE = ROOT / "examples" / "routes" / "r13-life-resist-belt.yaml"
PROFILED = {"plan", "route_object"}


def timed(name: str, out: Path, function, profiled: bool):
    began = time.perf_counter()
    if profiled:
        profiler = cProfile.Profile()
        result = profiler.runcall(function)
    else:
        result = function()
    seconds = time.perf_counter() - began
    print(f"[phase] {name}: {seconds:,.1f} s", flush=True)
    if profiled:
        with (out / f"{name}.txt").open("w", encoding="utf-8") as handle:
            for key in ("cumulative", "tottime"):
                handle.write(f"== {name}: sorted by {key} ({seconds:,.1f} s wall, under cProfile) ==\n")
                stats = pstats.Stats(profiler, stream=handle)
                stats.strip_dirs().sort_stats(key).print_stats(45)
    return result, seconds


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phases", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--profile-all", action="store_true")
    arguments = parser.parse_args()
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    data = load_game_data()
    prices = load_price_file(PRICES)
    target = load_target(TARGET, data)
    seconds: dict[str, float] = {}
    plan = packed = None
    for phase in arguments.phases.split(","):
        profiled = phase in PROFILED or arguments.profile_all
        if phase == "plan":
            plan, seconds[phase] = timed(phase, out, lambda: make_plan(data, target, prices, solver="object"), profiled)
        elif phase == "plan_packed":
            packed, seconds[phase] = timed(phase, out, lambda: make_plan(data, target, prices, solver="packed"), profiled)
        elif phase == "plan_packed_norisk":
            packed, seconds[phase] = timed(phase, out, lambda: make_plan(data, target, prices, solver="packed", with_risk=False), profiled)
        elif phase == "route_object":
            result, seconds[phase] = timed(phase, out, lambda: evaluate_route(plan, load_route(ROUTE, plan, data), data), profiled)
            print(f"  object read: mean {result.risk.mean.value:,.4f}, p90 {result.risk.p90.value}, gaps {len(result.gaps)}", flush=True)
        elif phase == "route_packed":
            result, seconds[phase] = timed(phase, out, lambda: evaluate_route(packed, load_route(ROUTE, packed, data), data), profiled)
            print(f"  packed read: mean {result.risk.mean.value:,.4f}, p90 {result.risk.p90.value}, gaps {len(result.gaps)}", flush=True)
        elif phase == "main":

            def command():
                printed = io.StringIO()
                with contextlib.redirect_stdout(printed):
                    return main(
                        [str(TARGET), "--json", str(out / "policy.json"), "--verify", "--runs", "8", "--route", str(ROUTE), "--progress"],
                        data=data, prices=prices, env={}, today=datetime.date(2026, 11, 1),
                    )  # fmt: skip

            code, seconds[phase] = timed(phase, out, command, profiled)
            print(f"  exit code {code}", flush=True)
        else:
            sys.exit(f"unknown phase {phase}")
        (out / "phases.json").write_text(json.dumps(seconds, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
