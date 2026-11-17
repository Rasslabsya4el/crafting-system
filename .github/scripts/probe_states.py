"""Plan one benchmark route under `Budget.in_states(N)` at rising N, one subprocess per N (#886 PR B2 measurement; not for landing).

    PROBE_ROUTES=R05,R10 PROBE_NS=500,2000 python .github/scripts/probe_states.py jobs OUT_DIR   # route RUNNER_INDEX of PROBE_ROUTES
    python .github/scripts/probe_states.py one ROUTE N                                           # one plan, one JSON line
"""

import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-07-31.json"
VENDOR = ROOT / "tests" / "fixtures" / "prices" / "vendor-v01-2026-11-01.json"
CAP = int(os.environ.get("PROBE_CAP", "900"))
TOTAL = int(os.environ.get("PROBE_TOTAL", "3200"))


def one(route: str, states: int) -> None:
    from crafting_system.budget import Budget
    from crafting_system.cli import _benchmark
    from crafting_system.data import load_game_data
    from crafting_system.planner import _packed
    from crafting_system.planner._entry import PlanSettings, plan_target
    from crafting_system.prices import load_price_file
    from crafting_system.targets import load_target

    resource.setrlimit(resource.RLIMIT_AS, (14 * 2**30, 14 * 2**30))
    began = time.perf_counter()
    last: list[str] = []

    def progress(line: str) -> None:
        stamp = f"[{time.perf_counter() - began:7.1f}s {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024} MB] {line}"
        last[:] = [*last[-3:], stamp]
        print(stamp, file=sys.stderr, flush=True)

    _packed.PROGRESS = progress
    bench = next(b for b in _benchmark.BENCHMARKS if b.id == route)
    data = load_game_data()
    target = load_target(ROOT / bench.target, data)
    prices = load_price_file(VENDOR if route == "V01" else PRICES.with_name("references-allflame-2026-07-31.json") if route == "R24" else PRICES)  # R24: its own file, with its start boots (#901)
    result: dict = {"route": route, "N": states}
    try:
        settings = PlanSettings(recipe_starts=bench.start is not None, judges_route=bench.route is not None, budget=Budget.in_states(states))
        plan = plan_target(data, target, prices, settings)
        search = plan.search
        result.update(
            planned=True,
            mean=None if plan.risk is None else round(plan.risk.mean.value + plan.start_price.chaos, 2),
            upper=None if search is None else round(search.upper + plan.start_price.chaos, 2),
            lower=None if search is None else round(search.lower + plan.start_price.chaos, 2),
            exact=None if search is None else search.exact,
            offers=len(plan.offers),
            solve_seconds=round(plan.solve_seconds, 1),
            limits=[str(limit)[:400] for limit in plan.limits],
        )
    except Exception as error:  # the probe reports any refusal as a row
        result.update(planned=False, error=f"{type(error).__name__}: {str(error)[:300]}")
    result.update(seconds=round(time.perf_counter() - began, 1), peak_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, last=last)
    print(json.dumps(result, default=str), flush=True)


def jobs(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    index = int(os.environ.get("RUNNER_INDEX", "1"))
    routes = os.environ["PROBE_ROUTES"].split(",")
    if index > len(routes):
        return
    route = routes[index - 1]
    ns = [int(n) for n in os.environ.get("PROBE_NS", "500,2000,8000,30000,120000").split(",")]
    began = time.perf_counter()
    rows = []
    for states in ns:
        cap = min(CAP, TOTAL - (time.perf_counter() - began))
        if cap < 60:
            break
        start = time.perf_counter()
        try:
            done = subprocess.run([sys.executable, __file__, "one", route, str(states)], capture_output=True, text=True, timeout=cap)
            line = (done.stdout.strip().splitlines() or ["{}"])[-1]
            row = json.loads(line) if line.startswith("{") else {"route": route, "N": states, "planned": False, "error": f"exit {done.returncode}: {done.stderr[-400:]}"}
            row["stderr_tail"] = done.stderr.strip().splitlines()[-3:]
        except subprocess.TimeoutExpired as expired:
            tail = (expired.stderr or b"").decode(errors="replace").strip().splitlines()[-3:] if isinstance(expired.stderr, bytes) else []
            row = {"route": route, "N": states, "planned": False, "error": f"no answer within {round(cap)} s", "stderr_tail": tail}
        row["wall"] = round(time.perf_counter() - start, 1)
        rows.append(row)
        print(json.dumps(row, default=str), flush=True)
        (out / f"states-{route}.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
        if str(row.get("error", "")).startswith(("no answer", "MemoryError", "exit")):
            break


if __name__ == "__main__":
    if sys.argv[1] == "one":
        one(sys.argv[2], int(sys.argv[3]))
    else:
        jobs(Path(sys.argv[2]))
