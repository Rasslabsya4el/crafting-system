"""The generated-family benchmark of planning speed: plan and measure every case of `tests/family_bench_support.py` (ticket #824).

    python .github/scripts/family_bench.py list    [--seed S] [--out FILE]
    python .github/scripts/family_bench.py run     --part K/N --out DIR [--seed S] [--only ID,ID] [--deadline-minutes M] [settings]
    python .github/scripts/family_bench.py summary --dir DIR [--dir DIR2 ...] --out FILE [--run-id ID ...] [--commit SHA]

It is the acceptance of every planning-speed ticket of #822 (research note `docs/research/2026-11-13-planning-speed.md`, section 10): a
benchmark route is a measurement, never the acceptance (#812). A heavy run, never on a PC (CLAUDE.md, "Heavy runs"):

    python .github/scripts/heavy_dispatch.py run --no-wait --ref BRANCH --runners 16 --min-runners 8 --command \\
      'uv run --no-sync python -u .github/scripts/family_bench.py run --part $RUNNER_INDEX/$RUNNER_COUNT --out $OUT_DIR'

**`run`** takes the cases of its part (every N-th of the seed's list, so each part gets small, medium and large ones) and, per case, starts
one child process per measurement, so that the memory of one case is its own and a case that runs away is stopped without losing the others:

1. **plan** (`one --mode plan`): the stages `setup` (the target, the scaled prices), `plan` (`make_plan(solver="auto", with_risk=False,
   net=Net(seconds=PLAN_SECONDS))`, or `plan_with_starts` for a vendor-recipe case: the planner's own path, whatever it picks today),
   `simulate` (the plan's policy played on concrete items, `cli._verify.verify`, in blocks until `SIM_SECONDS`), `risk` (`add_risk`).
   Each stage's seconds and peak memory (the resident memory of the process and its workers, sampled every `SAMPLE_SECONDS`) are written as
   the stage ends. Of the envelope search it records its own figures (`EnvelopeInfo`: rounds, states known and expanded, actions built and
   offered, the bound's keys and seconds, `L(root)` and `U` and the gap at the stop, why it stopped) and, per round, the seconds, the states
   and `L(root)` (`Search._net`, the hook `research/planning-speed/gap_trace.py` uses; `--upper-per-round` adds `U` per round as it does,
   at the price of one more solve per round, so it is off by default).
2. **walk** (`one --mode walk`), for a plan the auto path did not already solve on the full walk: `make_plan(solver="packed")`, the exact
   optimum `V*` where the full walk can hold the target within `WALK_SECONDS` and the memory cap.

**The nets** are measurement settings, not planner defaults (OR-12): `PLAN_SECONDS` is the 10-minute net of OR-33. The envelope search
honours it itself and says so; the other paths of today have no net, so the watchdog ends the stage `GRACE_SECONDS` after it and records
"stopped by the benchmark's net, no plan". `MEMORY_MB` stops a stage whose process tree passes it ("stopped at the memory cap") before the
runner's 16 GB kill the whole part. A part stops starting cases when what is left of `--deadline-minutes` is less than a case's worst time,
and records the rest as "not run" (run them again with `--only`).

**`summary`** reads the records of one or more runs and writes one JSON (the committed baseline is `tests/fixtures/family_bench/`): per case
the record, and per method family and size the checks of section 10: `L(root) <= V* <= U` where the walk held, the mean equal to `V*` to
1e-9 when the answer claims to be exact, |z| <= 4 of the simulation (OR-30), and every case whose outcome differs from the generator's
"refused today" mark. It asserts nothing: it is the record a later ticket is measured against.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))

PLAN_SECONDS = 600.0  # OR-33: the 10-minute net
GRACE_SECONDS = 60.0  # past the net, before the watchdog ends a stage whose path has no net of its own
SIM_SECONDS = 120.0
SIM_BLOCK = 200  # plays per `verify` call
SIM_MAX_RUNS = 20_000
RISK_SECONDS = 300.0
WALK_SECONDS = 300.0
MEMORY_MB = 13_000  # of the runner's 16 GB
SAMPLE_SECONDS = 0.5
SIGMAS = 4.0  # OR-30
TOLERANCE = 1e-9
SETUP_SECONDS = 180.0
CASE_SLACK = 120.0


# -- memory ------------------------------------------------------------------------------------------------------------------------------


def tree_rss_mb(pid: int) -> float | None:
    """The resident memory of `pid` and every process under it, in MB (Linux `/proc`); None where `/proc` is not there."""
    proc = Path("/proc")
    if not proc.is_dir():
        return None
    parent: dict[int, int] = {}
    rss: dict[int, int] = {}
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            text = (entry / "status").read_text()
        except OSError:
            continue
        fields = dict(line.split(":", 1) for line in text.splitlines() if ":" in line)
        try:
            parent[int(entry.name)] = int(fields["PPid"].strip())
            rss[int(entry.name)] = int(fields.get("VmRSS", "0 kB").split()[0])
        except (KeyError, ValueError):
            continue
    total, todo, seen = 0, [pid], set()
    while todo:
        current = todo.pop()
        if current in seen:
            continue
        seen.add(current)
        total += rss.get(current, 0)
        todo.extend(child for child, up in parent.items() if up == current)
    return total / 1024


class Watch:
    """The stage clock and memory of one child: the peak per stage, and a stop (written record, exit) past a stage's time or the memory cap."""

    def __init__(self, record: dict, path: Path, memory_mb: float) -> None:
        self.record, self.path, self.memory_mb = record, path, memory_mb
        self.stage: str | None = None
        self.limit = math.inf
        self.began = time.perf_counter()
        self.stage_began = self.began
        self.peak = 0.0
        self.lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()

    def start(self, stage: str, limit: float = math.inf) -> None:
        with self.lock:
            self.stage, self.limit, self.stage_began, self.peak = stage, limit, time.perf_counter(), 0.0
            self.record.setdefault("stages", {})[stage] = {"seconds": None, "peak_mb": None, "done": False}
        say(f"stage {stage} (limit {limit:g} s)")

    def end(self, **extra) -> None:
        with self.lock:
            entry = self.record["stages"][self.stage]
            entry.update(seconds=round(time.perf_counter() - self.stage_began, 2), peak_mb=round(self.peak, 1) if self.peak else peak_mb_self(), done=True, **extra)
            self.stage = None
            write(self.path, self.record)

    def _loop(self) -> None:
        while True:
            time.sleep(SAMPLE_SECONDS)
            mb = tree_rss_mb(os.getpid())
            with self.lock:
                if self.stage is None:
                    continue
                if mb is not None:
                    self.peak = max(self.peak, mb)
                spent = time.perf_counter() - self.stage_began
                why = None
                if mb is not None and mb > self.memory_mb:
                    why = f"stopped at the memory cap: {mb:,.0f} MB in the {self.stage} stage (cap {self.memory_mb:,.0f} MB)"
                elif spent > self.limit:
                    why = f"stopped by the benchmark's net: the {self.stage} stage passed {self.limit:g} s"
                if why is None:
                    continue
                entry = self.record["stages"][self.stage]
                entry.update(seconds=round(spent, 2), peak_mb=round(self.peak, 1), done=False, stopped=why)
                self.record.setdefault("stopped", why)
                if self.stage in ("plan", "walk", "setup"):
                    self.record["status"] = "stopped"
                    self.record["reason"] = why
                self.record["progress_tail"] = PROGRESS[-40:]
                write(self.path, self.record)
                say(why)
                os._exit(4)


def peak_mb_self() -> float | None:
    try:
        import resource

        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except ImportError:  # Windows: the quick test only
        return None


# -- the child -----------------------------------------------------------------------------------------------------------------------------

BEGAN = time.perf_counter()
PROGRESS: list[str] = []


def say(line: str) -> None:
    text = f"[{time.perf_counter() - BEGAN:8.1f}s] {line}"
    PROGRESS.append(text)
    del PROGRESS[:-400]
    print(text, flush=True)


def write(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def case_by_id(seed: int, case_id: str, data):
    import family_bench_support as F

    method, size = case_id.split("/")
    methods = [m for m in F.METHODS if m.name == method]
    sizes = [s for s in F.SIZES if s.name == size]
    if not methods or not sizes:
        raise SystemExit(f"no case {case_id!r}")
    # a case depends only on its own seed string and its family's class order, so generating it alone gives the same case as the full list
    found = F.cases(data, seed, methods=methods, sizes=F.SIZES)
    return next(c for c in found if c.size == size)


def case_head(case) -> dict:
    keys = ("id", "method", "batch", "size", "seed", "item_class", "base_id", "item_level", "wanted", "actions", "start", "start_price", "primary_snapshot", "vendor_starts", "refused")
    head = {key: getattr(case, key) for key in keys}
    head["digest"] = case.digest()
    head["keep_count"] = None if case.keep is None else len(case.keep)
    return head


def install_search_hooks(per_round: list, upper_per_round: bool) -> None:
    """Record the envelope search's figures per round (the hook of `gap_trace.py`), without changing what it does."""
    from crafting_system.cli import _envelope

    original = _envelope.Search._net
    started: dict[int, float] = {}

    def traced(self, began):
        key = id(self)
        started.setdefault(key, began)
        stats = self.stats
        if stats.rounds and (not per_round or per_round[-1]["round"] != stats.rounds):
            row = {
                "round": stats.rounds, "seconds": round(time.perf_counter() - started[key], 2), "known": len(self.states), "expanded": stats.expanded,
                "realized": stats.realized, "lower": float(stats.lower_history[-1]) if stats.lower_history else None,
            }  # fmt: skip
            if upper_per_round:
                try:
                    row["upper"] = self.upper_value()
                except Exception as error:  # noqa: BLE001 - a stiff graph the solver cannot certify: recorded, not fatal
                    row["upper_error"] = repr(error)[:200]
            per_round.append(row)
        return original(self, began)

    _envelope.Search._net = traced


def path_of(plan) -> str:
    if plan.approximation is not None:
        return "approximate (budget)"
    if plan.readings is not None:
        return "readings (object solver per reading)"
    if plan.pruned is not None:
        return "bound pruning (solve_pruned)"
    if plan.packed is not None and "envelope" in plan.packed.info:
        return "envelope search"
    if plan.packed is not None:
        return "full walk (packed)"
    return "full walk (object solver)"


def estimate(value) -> dict | None:
    if value is None:
        return None
    return {key: getattr(value, key) for key in ("value", "low", "high", "standard_error") if hasattr(value, key)}


def run_plan_child(args) -> None:
    from crafting_system.cli import _packed, make_plan
    from crafting_system.cli._envelope import Net
    from crafting_system.cli._plan import PlanError, add_risk
    from crafting_system.data import load_game_data

    import family_bench_support as F

    out = Path(args.out)
    record: dict = {"mode": "plan", "status": "running", "settings": settings(args)}
    path = out / "cases" / f"{args.case.replace('/', '__')}.plan.json"
    watch = Watch(record, path, args.memory_mb)
    _packed.PROGRESS = say
    per_round: list = []
    install_search_hooks(per_round, args.upper_per_round)

    watch.start("setup", SETUP_SECONDS)
    data = load_game_data()
    case = case_by_id(args.seed, args.case, data)
    record["case"] = case_head(case)
    target = F.target_of(case, data)
    prices = F.prices_for(case)
    record["prices"] = {"names": len(prices.prices), "primary": case.primary_snapshot}
    watch.end()

    watch.start("plan", args.plan_seconds + GRACE_SECONDS)
    net = Net(seconds=args.plan_seconds)
    try:
        if case.vendor_starts:
            from crafting_system.cli._starts import plan_with_starts

            plan = plan_with_starts(data, target, prices, recipe_starts=True, start_price=case.start_price, net=net, with_risk=False)
        else:
            plan = make_plan(data, target, prices, start_price=case.start_price, with_risk=False, net=net)
    except (PlanError, ValueError) as error:  # what the planner says when it refuses: the reason is the record
        text = f"{type(error).__name__}: {error}"[:2000]
        # a net that ended the search before any plan closed (a given start: no restart to fall back on) is OR-33's "stopped, no plan
        # found yet", not a refusal of the method: `_envelope_plan.envelope_result` words it "the search stopped (...)"
        stopped = "the search stopped" in text or "was stopped" in text
        record.update(status="stopped" if stopped else "refused", reason=text, no_plan=stopped)
        record["envelope_rounds"] = per_round
        watch.end()
        record["progress_tail"] = PROGRESS[-40:]
        write(path, record)
        return
    except Exception as error:  # noqa: BLE001 - a crash is a finding of the benchmark, recorded with its trace
        record.update(status="error", reason=f"{type(error).__name__}: {error}"[:2000], trace=traceback.format_exc()[-4000:])
        watch.end()
        record["progress_tail"] = PROGRESS[-40:]
        write(path, record)
        return
    info = plan.packed.info.get("envelope") if plan.packed is not None else None
    mean = float(plan.mean_remaining)
    record["path"] = path_of(plan)
    record["plan"] = {
        "mean_remaining": mean, "start_price": plan.start_price.chaos, "mean_total": plan.start_price.chaos + mean,
        "error_bound": getattr(plan.solution, "error_bound", None), "states_known": len(plan.solution.values), "reach": len(plan.policy),
        "offers": len(plan.offers), "solve_seconds": round(plan.solve_seconds, 2), "limits": [limit.what for limit in plan.limits],
        "start_label": plan.policy.offer(plan.start).label if hasattr(plan.policy, "offer") else None,
        "start_option": None if plan.starts is None else repr(plan.starts)[:500],
    }  # fmt: skip
    if info is not None:
        env = dataclasses.asdict(info)
        env["gap"] = None if not info.lower else info.upper / info.lower - 1.0
        record["envelope"] = env
        record["status"] = "planned" if info.exact else "stopped"
        record["reason"] = None if info.exact else f"the envelope search stopped: {info.stopped}"
        record["lower"], record["upper"] = info.lower, info.upper
    else:
        record["status"] = "planned"
        record["reason"] = None
        record["lower"] = record["upper"] = mean  # an exact solve: the bound and the plan's mean are one number
    record["envelope_rounds"] = per_round
    watch.end()
    spent = record["stages"]["plan"]["seconds"]
    record["breakdown"] = (  # the plan stage split: the bound's build, the search (with the solve of what it expanded), the rest (limits, lumping)
        {"bound": round(info.bound_seconds, 2), "search": round(info.seconds - info.bound_seconds, 2), "after_search": round(spent - info.seconds, 2)}
        if info is not None
        else {"solve": round(plan.solve_seconds, 2), "rest": round(spent - plan.solve_seconds, 2)}
    )
    write(path, record)

    watch.start("simulate", args.sim_seconds + GRACE_SECONDS)
    record["simulate"] = simulate(data, plan, args.sim_seconds)
    watch.end()

    watch.start("risk", args.risk_seconds)
    try:
        risked = add_risk(plan)
        risk = risked.risk
        record["risk"] = None if risk is None else {
            "p50": estimate(risk.quantiles.get(0.5)), "p90": estimate(risk.quantiles.get(0.9)), "mean": estimate(risk.mean), "grid": repr(risk.grid)[:300],
        }  # fmt: skip
    except Exception as error:  # noqa: BLE001 - recorded, the record of the plan stands
        record["risk"] = {"error": f"{type(error).__name__}: {error}"[:1000]}
    watch.end()
    record["progress_tail"] = PROGRESS[-40:]
    write(path, record)


def simulate(data, plan, seconds: float) -> dict:
    """The plan's policy played on concrete items (`verify`), pooled over blocks until `seconds`: the mean, its standard error and |z|."""
    from types import SimpleNamespace

    from crafting_system.cli._verify import verify

    if plan.risk is None:  # `verify` reads the p90 for its own report only; the risk stage runs after this one, under its own net
        plan = dataclasses.replace(plan, risk=SimpleNamespace(p90=SimpleNamespace(value=math.nan)))
    began = time.perf_counter()
    n = 0
    total = squares = 0.0
    unfinished = stopped = 0
    block = 0
    computed = plan.start_price.chaos + float(plan.mean_remaining)
    try:
        while n < SIM_MAX_RUNS and time.perf_counter() - began < seconds:
            check = verify(data, plan, runs=SIM_BLOCK, seed=1 + block)
            report = check.report
            runs = SIM_BLOCK
            mean, se = report.cost.value, report.cost.standard_error
            total += runs * mean
            squares += (runs - 1) * runs * se * se + runs * mean * mean
            unfinished += report.unfinished
            stopped += report.stopped
            n += runs
            block += 1
    except Exception as error:  # noqa: BLE001 - recorded
        return {"error": f"{type(error).__name__}: {error}"[:1000], "runs": n}
    if n == 0:
        return {"runs": 0}
    mean = total / n
    variance = max(squares - n * mean * mean, 0.0) / max(n - 1, 1)
    se = math.sqrt(variance / n)
    z = 0.0 if se == 0 and abs(mean - computed) <= TOLERANCE * max(1.0, abs(computed)) else (math.inf if se == 0 else (mean - computed) / se)
    return {"runs": n, "mean": mean, "standard_error": se, "computed": computed, "z": z, "unfinished": unfinished, "stopped": stopped, "seconds": round(time.perf_counter() - began, 1)}


def run_walk_child(args) -> None:
    from crafting_system.cli import _packed, make_plan
    from crafting_system.cli._plan import PlanError
    from crafting_system.data import load_game_data

    import family_bench_support as F

    out = Path(args.out)
    record: dict = {"mode": "walk", "status": "running", "settings": settings(args)}
    path = out / "cases" / f"{args.case.replace('/', '__')}.walk.json"
    watch = Watch(record, path, args.memory_mb)
    _packed.PROGRESS = say
    watch.start("setup", SETUP_SECONDS)
    data = load_game_data()
    case = case_by_id(args.seed, args.case, data)
    target, prices = F.target_of(case, data), F.prices_for(case)
    watch.end()
    watch.start("walk", args.walk_seconds)
    try:
        if case.vendor_starts:
            from crafting_system.cli._starts import plan_with_starts

            plan = plan_with_starts(data, target, prices, recipe_starts=True, start_price=case.start_price, solver="packed", with_risk=False)
        else:
            plan = make_plan(data, target, prices, start_price=case.start_price, solver="packed", with_risk=False)
        record.update(status="solved", optimum=float(plan.mean_remaining), states=len(plan.solution.values), reason=None)
    except (PlanError, ValueError) as error:
        record.update(status="refused", reason=f"{type(error).__name__}: {error}"[:1000])
    except Exception as error:  # noqa: BLE001
        record.update(status="error", reason=f"{type(error).__name__}: {error}"[:1000], trace=traceback.format_exc()[-3000:])
    watch.end()
    write(path, record)


def settings(args) -> dict:
    return {
        "seed": args.seed, "plan_seconds": args.plan_seconds, "sim_seconds": args.sim_seconds, "risk_seconds": args.risk_seconds,
        "walk_seconds": args.walk_seconds, "memory_mb": args.memory_mb, "upper_per_round": args.upper_per_round,
    }  # fmt: skip


# -- the parent ------------------------------------------------------------------------------------------------------------------------


def child(args, case_id: str, mode: str, wall: float) -> dict:
    """Run one child; return its record, or one that says how it ended when it wrote none."""
    command = [
        sys.executable, "-u", __file__, "one", "--case", case_id, "--mode", mode, "--out", args.out, "--seed", str(args.seed),
        "--plan-seconds", str(args.plan_seconds), "--sim-seconds", str(args.sim_seconds), "--risk-seconds", str(args.risk_seconds),
        "--walk-seconds", str(args.walk_seconds), "--memory-mb", str(args.memory_mb),
    ] + (["--upper-per-round"] if args.upper_per_round else [])  # fmt: skip
    path = Path(args.out) / "cases" / f"{case_id.replace('/', '__')}.{mode}.json"
    log = Path(args.out) / "logs" / f"{case_id.replace('/', '__')}.{mode}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    began = time.perf_counter()
    with open(log, "w", encoding="utf-8") as handle:
        process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT, cwd=ROOT)
        try:
            code = process.wait(timeout=wall)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            code = "killed"
    record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"mode": mode}
    record["exit"] = code
    record["wall_seconds"] = round(time.perf_counter() - began, 1)
    if record.get("status") in (None, "running"):
        tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]
        record["status"] = "stopped" if code in ("killed", 4, -9, 137) else "error"
        record["reason"] = record.get("stopped") or (f"the process was killed after {wall:g} s" if code == "killed" else f"exit {code} with no record")
        record["log_tail"] = tail
    return record


def run_part(args) -> None:
    from crafting_system.data import load_game_data

    import family_bench_support as F

    part, parts = (int(x) for x in args.part.split("/"))
    data = load_game_data()
    found = F.cases(data, args.seed)
    if args.only:
        wanted = set(args.only.split(","))
        found = [c for c in found if c.id in wanted]
        mine = found[part - 1 :: parts]
    else:
        mine = found[part - 1 :: parts]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    deadline = BEGAN + args.deadline_minutes * 60
    worst = SETUP_SECONDS + args.plan_seconds + GRACE_SECONDS + args.sim_seconds + GRACE_SECONDS + args.risk_seconds + CASE_SLACK
    say(f"part {part}/{parts}: {len(mine)} of {len(found)} cases; a case takes at most {worst:.0f} s, plus {args.walk_seconds + SETUP_SECONDS:.0f} s of walk")
    records = []
    for case in mine:
        left = deadline - time.perf_counter()
        head = case_head(case)
        if left < worst:
            records.append({"case": head, "status": "not run", "reason": f"the part's deadline: {left:.0f} s left, a case may take {worst:.0f} s"})
            say(f"{case.id}: not run (deadline)")
            continue
        say(f"{case.id}: plan ...")
        planned = child(args, case.id, "plan", worst)
        planned.setdefault("case", head)
        walk = None
        full = planned.get("path", "").startswith("full walk")
        left = deadline - time.perf_counter()
        if planned.get("status") in ("planned", "stopped") and planned.get("plan") is not None and not full:
            if left > args.walk_seconds + SETUP_SECONDS + CASE_SLACK:
                say(f"{case.id}: walk ...")
                walk = child(args, case.id, "walk", args.walk_seconds + SETUP_SECONDS + CASE_SLACK)
            else:
                walk = {"status": "not run", "reason": "the part's deadline"}
        elif full and planned.get("status") == "planned":
            walk = {"status": "solved", "optimum": planned["plan"]["mean_remaining"], "states": planned["plan"]["states_known"], "reason": "the auto path was the full walk"}
        planned["walk"] = walk
        records.append(planned)
        say(f"{case.id}: {planned.get('status')} ({planned.get('path')}) {planned.get('reason') or ''}"[:300])
        write(out / f"part-{part}-of-{parts}.json", {"part": part, "parts": parts, "seed": args.seed, "records": records})
    write(out / f"part-{part}-of-{parts}.json", {"part": part, "parts": parts, "seed": args.seed, "records": records, "complete": True})


# -- the summary ---------------------------------------------------------------------------------------------------------------------------


def checks(record: dict) -> dict:
    """The checks of section 10 on one record (none asserts: they are figures)."""
    out: dict = {}
    walk = record.get("walk") or {}
    optimum = walk.get("optimum")
    lower, upper = record.get("lower"), record.get("upper")
    if optimum is not None and lower is not None and upper is not None:
        slack = TOLERANCE * max(1.0, abs(optimum))
        out["lower_le_optimum"] = lower <= optimum + slack
        out["optimum_le_upper"] = optimum <= upper + slack
        out["gap_to_optimum"] = upper / optimum - 1.0 if optimum else None
        if record.get("status") == "planned":
            out["exact_mean_equals_optimum"] = abs(upper - optimum) <= slack
    sim = record.get("simulate") or {}
    if sim.get("z") is not None:
        out["z"] = sim["z"]
        out["z_within"] = abs(sim["z"]) <= SIGMAS and not sim.get("unfinished") and not sim.get("stopped")
    mark = (record.get("case") or {}).get("refused")
    status = record.get("status")
    if status in ("planned", "stopped", "refused"):
        out["mark_agrees"] = (mark is not None) == (status == "refused")
    return out


def summarize(args) -> None:
    records: dict[str, dict] = {}
    for folder in args.dir:
        for path in sorted(Path(folder).rglob("part-*-of-*.json")):
            for record in json.loads(path.read_text(encoding="utf-8"))["records"]:
                key = record["case"]["id"]
                if key not in records or records[key].get("status") == "not run":  # a later run of a case (`--only`) replaces "not run"
                    records[key] = record
    rows = []
    for key in sorted(records):
        record = records[key]
        record["checks"] = checks(record)
        rows.append(record)
    by_family: dict[str, dict] = {}
    for record in rows:
        case = record["case"]
        entry = by_family.setdefault(case["method"], {"batch": case["batch"], "sizes": {}})
        stages = record.get("stages") or {}
        plan_stage = stages.get("plan") or {}
        entry["sizes"][case["size"]] = {
            "status": record.get("status"), "path": record.get("path"), "plan_seconds": plan_stage.get("seconds"), "plan_peak_mb": plan_stage.get("peak_mb"),
            "gap": (record.get("envelope") or {}).get("gap"), "reach": (record.get("plan") or {}).get("reach"), "checks": record["checks"],
            "reason": (record.get("reason") or "")[:200],
        }  # fmt: skip
    disagreements = [r["case"]["id"] for r in rows if r["checks"].get("mark_agrees") is False]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.get("status") or "?"] = counts.get(r.get("status") or "?", 0) + 1
    summary = {
        "ticket": 824, "schema": __import__("family_bench_support").SCHEMA, "run_ids": args.run_id, "commit": args.commit,
        "cases": len(rows), "status_counts": counts, "mark_disagreements": disagreements,
        "z_outside": [r["case"]["id"] for r in rows if r["checks"].get("z_within") is False],
        "bound_violations": [r["case"]["id"] for r in rows if r["checks"].get("lower_le_optimum") is False or r["checks"].get("optimum_le_upper") is False],
        "families": by_family, "records": rows,
    }  # fmt: skip
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("cases", "status_counts", "mark_disagreements", "z_outside", "bound_violations")}, indent=1))


# -- the command line ----------------------------------------------------------------------------------------------------------------------


def main() -> None:
    import family_bench_support as F

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--seed", type=int, default=F.DEFAULT_SEED)
        p.add_argument("--plan-seconds", type=float, default=PLAN_SECONDS)
        p.add_argument("--sim-seconds", type=float, default=SIM_SECONDS)
        p.add_argument("--risk-seconds", type=float, default=RISK_SECONDS)
        p.add_argument("--walk-seconds", type=float, default=WALK_SECONDS)
        p.add_argument("--memory-mb", type=float, default=MEMORY_MB)
        p.add_argument("--upper-per-round", action="store_true")

    listing = sub.add_parser("list")
    listing.add_argument("--seed", type=int, default=F.DEFAULT_SEED)
    listing.add_argument("--out")
    run = sub.add_parser("run")
    common(run)
    run.add_argument("--part", default="1/1")
    run.add_argument("--out", required=True)
    run.add_argument("--only")
    run.add_argument("--deadline-minutes", type=float, default=50.0)
    one = sub.add_parser("one")
    common(one)
    one.add_argument("--case", required=True)
    one.add_argument("--mode", choices=("plan", "walk"), required=True)
    one.add_argument("--out", required=True)
    summary = sub.add_parser("summary")
    summary.add_argument("--dir", action="append", required=True)
    summary.add_argument("--out", required=True)
    summary.add_argument("--run-id", action="append", default=[])
    summary.add_argument("--commit")
    args = parser.parse_args()

    if args.command == "list":
        from crafting_system.data import load_game_data

        found = F.cases(load_game_data(), args.seed)
        if args.out:
            F.write_cases(found, Path(args.out))
        for case in found:
            print(f"{case.id:32} {case.item_class:26} {case.wanted} wanted  {case.digest()}  {case.refused or 'plans'}")
    elif args.command == "run":
        run_part(args)
    elif args.command == "one":
        (run_plan_child if args.mode == "plan" else run_walk_child)(args)
    else:
        summarize(args)


if __name__ == "__main__":
    main()
