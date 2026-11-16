"""Plan benchmark routes at default settings on this checkout and on `main`, one job per (route, ref) (#886 PR B probe; not for landing).

    python .github/scripts/probe_defaults.py jobs OUT_DIR            # the runner's share of the jobs, by RUNNER_INDEX / RUNNER_COUNT
    python .github/scripts/probe_defaults.py one ROUTE               # one plan, prints one JSON line
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
ROUTES = ["R14", "R13", "R09", "R11", "R05", "R10", "R12"]
CAP = int(os.environ.get("PROBE_CAP", "900"))


def one(route: str) -> None:
    from crafting_system.cli import _benchmark
    from crafting_system.data import load_game_data
    from crafting_system.planner import _packed
    from crafting_system.planner._entry import PlanSettings, plan_target
    from crafting_system.prices import load_price_file
    from crafting_system.targets import load_target

    began = time.perf_counter()
    last: list[str] = []

    def progress(line: str) -> None:
        stamp = f"[{time.perf_counter() - began:7.1f}s {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024} MB] {line}"
        last[:] = [*last[-3:], stamp]
        print(stamp, file=sys.stderr, flush=True)

    _packed.PROGRESS = progress
    variant = os.environ.get("PROBE_VARIANT", "")
    if variant:
        from crafting_system.planner import _offers, _plan

        _offers.BLOCKING_CRAFTS = variant != "nb"
        metamod = ("Cannot Be Changed", "Cannot roll", "Crafted Modifiers")
        original = _plan.cheapest_per_class

        def filtered(priced):
            kept, same = original(priced)
            drop = (lambda p: any(m in p.label for m in metamod)) if variant == "nometa" else (lambda p: not any(m in p.label for m in metamod))
            return tuple(p for p in kept if p.offer.blocks is None or not drop(p)), same

        if variant in ("nometa", "nofill"):
            _plan.cheapest_per_class = filtered
    bench = next(b for b in _benchmark.BENCHMARKS if b.id == route)
    data = load_game_data()
    target = load_target(ROOT / bench.target, data)
    prices = load_price_file(PRICES)
    result: dict = {"route": route}
    try:
        plan = plan_target(data, target, prices, PlanSettings(recipe_starts=bench.start is not None))
        values = getattr(plan.solution, "values", None)
        result.update(
            planned=True,
            mean=None if plan.risk is None else round(plan.risk.mean.value + plan.start_price.chaos, 2),
            start_value=None if values is None else values.get(plan.start),
            states=None if values is None else len(values),
            offers=len(plan.offers),
            solve_seconds=round(plan.solve_seconds, 1),
            approximate=plan.approximation is not None,
            limits=[str(limit)[:160] for limit in plan.limits],
        )
    except Exception as error:  # the probe reports any refusal as a row
        result.update(planned=False, error=f"{type(error).__name__}: {str(error)[:300]}")
    result.update(seconds=round(time.perf_counter() - began, 1), peak_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, last=last)
    print(json.dumps(result, default=str), flush=True)


def jobs(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    index, count = int(os.environ.get("RUNNER_INDEX", "1")), int(os.environ.get("RUNNER_COUNT", "1"))
    every = [(route, ref) for route in ROUTES for ref in ("branch", "main")]
    if os.environ.get("PROBE_V2"):
        every = [(r, "nb") for r in ("R09", "R11", "R13", "R05", "R10", "R12")] + [(r, "nometa") for r in ("R05", "R10", "R12")] + [(r, "nofill") for r in ("R05", "R10", "R12")]
    mine = every[index - 1 :: count]
    main_src = Path("/tmp/probe-main/src")
    if any(ref == "main" for _, ref in mine) and not main_src.exists():
        subprocess.run(["git", "fetch", "--depth=1", "origin", "main"], check=True)
        subprocess.run(["git", "worktree", "add", "--detach", "/tmp/probe-main", "FETCH_HEAD"], check=True)
    rows = []
    for route, ref in mine:
        env = dict(os.environ)
        if ref == "main":
            env["PYTHONPATH"] = str(main_src)
        elif ref != "branch":
            env["PROBE_VARIANT"] = ref
        began = time.perf_counter()
        try:
            done = subprocess.run([sys.executable, __file__, "one", route], env=env, capture_output=True, text=True, timeout=CAP)
            line = (done.stdout.strip().splitlines() or ["{}"])[-1]
            row = json.loads(line) if line.startswith("{") else {"route": route, "planned": False, "error": f"exit {done.returncode}: {done.stderr[-400:]}"}
            row["stderr_tail"] = done.stderr.strip().splitlines()[-3:]
        except subprocess.TimeoutExpired as expired:
            tail = (expired.stderr or b"").decode(errors="replace").strip().splitlines()[-3:] if isinstance(expired.stderr, bytes) else []
            row = {"route": route, "planned": False, "error": f"no plan within {CAP} s", "stderr_tail": tail}
        row.update(ref=ref, wall=round(time.perf_counter() - began, 1))
        rows.append(row)
        print(json.dumps(row, default=str), flush=True)
        (out / f"probe-{index}.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "one":
        one(sys.argv[2])
    else:
        jobs(Path(sys.argv[2]))
