"""The generated-family benchmark of planning speed: plan and measure every case of `tests/family_bench_support.py` (ticket #824).

    python .github/scripts/family_bench.py list    [--seed S] [--out FILE]
    python .github/scripts/family_bench.py run     --part K/N --out DIR [--seed S] [--only ID,ID] [--deadline-minutes M] [settings]
    python .github/scripts/family_bench.py summary --dir DIR [--dir DIR2 ...] --out FILE [--run-id ID ...] [--commit SHA]

It is the acceptance of every planning-speed ticket of #822 (research note `docs/research/2026-11-13-planning-speed.md`, section 10): a
benchmark route is a measurement, never the acceptance (#812). A heavy run, never on a PC (CLAUDE.md, "Heavy runs"):

    python .github/scripts/heavy_dispatch.py run --no-wait --ref BRANCH --runners 16 --command \\
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
runner's 16 GB kill the whole part. A part starts no case with less than `MIN_START_SECONDS` left of `--deadline-minutes`, and gives a case at most
what is left; a case the deadline cuts, and the cases it never started, are recorded "not run": run them again with `--only ID,ID` (the
summary takes a later record of a case over a "not run" one).

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
GRACE_SECONDS = 300.0  # past the net, before the watchdog ends the plan stage: what follows the search (the plan's solve, limits, lumping), or a path with no net of its own
SIM_SECONDS = 120.0
SIM_GRACE_SECONDS = 120.0  # one block may run past `SIM_SECONDS`
SIM_FIRST_BLOCK = 10  # plays of the first `verify` call; each next block doubles, up to `SIM_BLOCK`
SIM_BLOCK = 2000  # the simulator's own block
SIM_MAX_RUNS = 20_000
RISK_SECONDS = 300.0
WALK_SECONDS = 300.0
MEMORY_MB = 13_000  # of the runner's 16 GB
SAMPLE_SECONDS = 0.5
SIGMAS = 4.0  # OR-30
TOLERANCE = 1e-9
SETUP_SECONDS = 180.0
CASE_SLACK = 120.0
MIN_START_SECONDS = 480.0  # a part starts no case with less than this left before its deadline


# -- memory ------------------------------------------------------------------------------------------------------------------------------


def tree_memory_mb(pid: int) -> float | None:
    """The memory of `pid` and every process under it, in MB (Linux `/proc`); None where `/proc` is not there.

    Each process counts its proportional set size (`Pss` of `smaps_rollup`): a page that forked workers share copy-on-write with their
    parent is split among them, so the sum is what the tree really holds, not the resident size of each counted again (`VmRSS` is the
    fallback where `smaps_rollup` cannot be read).
    """
    proc = Path("/proc")
    if not proc.is_dir():
        return None
    parent: dict[int, int] = {}
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            text = (entry / "stat").read_text()
            parent[int(entry.name)] = int(text.rsplit(")", 1)[1].split()[1])  # the field after the state, past the command in parentheses
        except (OSError, ValueError, IndexError):
            continue
    tree, todo = set(), [pid]
    while todo:
        current = todo.pop()
        if current in tree:
            continue
        tree.add(current)
        todo.extend(child for child, up in parent.items() if up == current)
    total = 0
    for current in tree:
        total += _kb(proc / str(current) / "smaps_rollup", "Pss:") or _kb(proc / str(current) / "status", "VmRSS:") or 0
    return total / 1024


def _kb(path: Path, key: str) -> int | None:
    try:
        for line in path.read_text().splitlines():
            if line.startswith(key):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return None


def kill_tree() -> None:
    """End this process's group (the child is its own session: `child` starts it so), workers included, then this process."""
    if hasattr(os, "killpg") and os.getpgid(0) == os.getpid():  # only when this child leads its own group (`child` starts it so)
        try:
            os.killpg(os.getpgid(0), 9)
        except OSError:
            pass
    os._exit(4)


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
            sampled = round(self.peak, 1) if self.peak else None  # a stage shorter than one sample has no peak of its own
            entry.update(seconds=round(time.perf_counter() - self.stage_began, 2), peak_mb=sampled, process_peak_mb=peak_mb_self(), done=True, **extra)
            self.stage = None
            write(self.path, self.record)

    def _loop(self) -> None:
        while True:
            time.sleep(SAMPLE_SECONDS)
            try:
                self._check()
            except Exception as error:  # noqa: BLE001 - the watch must outlive any error of one sample (a record mutated while written)
                print(f"watch: {error!r}", flush=True)

    def _check(self) -> None:
        mb = tree_memory_mb(os.getpid())
        with self.lock:
            if self.stage is None:
                return
            if mb is not None:
                self.peak = max(self.peak, mb)
            spent = time.perf_counter() - self.stage_began
            if mb is not None and mb > self.memory_mb:
                why = f"stopped at the memory cap: {mb:,.0f} MB in the {self.stage} stage (cap {self.memory_mb:,.0f} MB)"
            elif spent > self.limit:
                why = f"stopped by the benchmark's net: the {self.stage} stage passed {self.limit:g} s"
            else:
                return
            entry = self.record["stages"][self.stage]
            entry.update(seconds=round(spent, 2), peak_mb=round(self.peak, 1), done=False, stopped=why)
            self.record.setdefault("stopped", why)
            if self.stage in ("plan", "walk", "setup"):
                self.record["status"] = "stopped"
                self.record["reason"] = why
                self.record["no_plan"] = self.stage != "walk"
            self.record["progress_tail"] = PROGRESS[-40:]
            say(why)
            for _ in range(5):  # the main thread may be changing the record while it is written: try again
                try:
                    write(self.path, self.record)
                    break
                except RuntimeError:
                    time.sleep(0.05)
            kill_tree()


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
    temporary = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")  # the watch and the main thread may write at once
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


def describe_plan(plan, record: dict):
    """Write the plan's figures into `record` (path, mean, states, reach, the search's or the pruning's counts, `L` and `U`); return its `EnvelopeInfo` or None."""
    info = plan.packed.info.get("envelope") if plan.packed is not None else None
    mean = float(plan.mean_remaining)
    record["path"] = path_of(plan)
    try:
        start_label = plan.policy.offer(plan.start).label if hasattr(plan.policy, "offer") else plan.offer_of(plan.policy[plan.start]).label
    except (KeyError, AttributeError):  # the start is already a goal, or the policy has no action there
        start_label = None
    record["plan"] = {
        "mean_remaining": mean, "start_price": plan.start_price.chaos, "mean_total": plan.start_price.chaos + mean,
        "error_bound": getattr(plan.solution, "error_bound", None), "states_known": len(plan.solution.values),
        "reach": len(plan.policy), "shown_reach": len(plan.view_policy), "offers": len(plan.offers), "solve_seconds": round(plan.solve_seconds, 2),
        "limits": [limit.what for limit in plan.limits], "start_label": start_label,
        "start_option": None if plan.starts is None else repr(plan.starts)[:500], "lock": None if plan.foresight is None else repr(plan.foresight)[:300],
    }  # fmt: skip
    if plan.pruned is not None:
        pruned = plan.pruned
        record["pruned"] = {
            "rounds": pruned.rounds, "used": len(pruned.used), "bounded": len(pruned.bounded), "twins": len(pruned.twins), "inapplicable": len(pruned.inapplicable),
            "fell_back": pruned.fell_back, "why": pruned.why[:300], "phases": [[name, round(seconds, 2)] for name, seconds in pruned.phases],
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
    return info


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

            # `plan_with_starts` measures the risk of the start it keeps itself (`with_risk` is its own argument to `make_plan`): the risk's
            # seconds are then inside this stage, and `breakdown` takes them out
            plan = plan_with_starts(data, target, prices, recipe_starts=True, start_price=case.start_price, net=net)
        else:
            plan = make_plan(data, target, prices, start_price=case.start_price, with_risk=False, net=net)
    except PlanError as error:  # what the planner says when it refuses: the reason is the record
        text = f"{type(error).__name__}: {error}"[:2000]
        # a net that ended the search before any plan closed (a given start: no restart to fall back on) is OR-33's "stopped, no plan
        # found yet", not a refusal of the method: `_envelope_plan.envelope_result` words it "the search stopped (...)"
        stopped = "the search stopped" in text or "was stopped" in text
        # a refusal of a method the planner does not build yet is "refused" (the generator marks those cases from the code); any other
        # PlanError on a case expected to plan (no policy found, a certificate not reached) is the planner failing it: "failed"
        status = "stopped" if stopped else "refused" if case.refused else "failed"
        record.update(status=status, reason=text, no_plan=True)
        record["envelope_rounds"] = per_round
        watch.end()
        record["progress_tail"] = PROGRESS[-40:]
        write(path, record)
        return
    except Exception as error:  # noqa: BLE001 - a crash is a finding of the benchmark, recorded with its trace
        record.update(no_plan=True, status="error", reason=f"{type(error).__name__}: {error}"[:2000], trace=traceback.format_exc()[-4000:])
        watch.end()
        record["progress_tail"] = PROGRESS[-40:]
        write(path, record)
        return
    try:
        info = describe_plan(plan, record)
    except Exception as error:  # noqa: BLE001 - the plan exists; a figure that cannot be read is recorded, the rest stands
        info = None
        if record.get("status") == "running":
            record["status"] = "planned"
        record["describe_error"] = f"{type(error).__name__}: {error}"[:1000]
    record["envelope_rounds"] = per_round
    watch.end()
    spent = record["stages"]["plan"]["seconds"]
    risk_inside = round(plan.risk_seconds, 2) if plan.risk is not None else 0.0  # a vendor-recipe plan comes with its risk measured
    record["breakdown"] = (  # the plan stage split: the bound's build, the search (with the solve of what it expanded), the rest (limits, lumping)
        {"bound": round(info.bound_seconds, 2), "search": round(info.seconds - info.bound_seconds, 2), "after_search": round(spent - info.seconds - risk_inside, 2), "risk": risk_inside,
         "note": "a vendor-recipe case: after_search also holds the plans of the other start options" if case.vendor_starts else ""}
        if info is not None
        else {"solve": round(plan.solve_seconds, 2), "rest": round(spent - plan.solve_seconds - risk_inside, 2), "risk": risk_inside}
    )
    write(path, record)

    watch.start("simulate", args.sim_seconds + SIM_GRACE_SECONDS)
    simulate(data, plan, args.sim_seconds, record, path)
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


def simulate(data, plan, seconds: float, record: dict, path: Path) -> None:
    """The plan's policy played on concrete items (`verify`), pooled over blocks until `seconds`: the mean, its standard error and z.

    The blocks grow from `SIM_FIRST_BLOCK` to `SIM_BLOCK` plays (a cheap plan plays thousands a second, R04's kind half a second a play), and
    the pooled figures are written into `record["simulate"]` after every block, so a net that ends the stage keeps what was played.
    """
    from types import SimpleNamespace

    from crafting_system.cli._verify import verify

    if plan.risk is None:  # `verify` reads the p90 for its own report only; the risk stage runs after this one, under its own net
        plan = dataclasses.replace(plan, risk=SimpleNamespace(p90=SimpleNamespace(value=math.nan)))
    began = time.perf_counter()
    totals = {"n": 0, "sum": 0.0, "squares": 0.0, "unfinished": 0, "stopped": 0}
    computed = plan.start_price.chaos + float(plan.mean_remaining)
    size, block = SIM_FIRST_BLOCK, 0
    try:
        while totals["n"] < SIM_MAX_RUNS and time.perf_counter() - began < seconds:
            if totals["n"]:  # size the block from the plays a second measured so far, so that one call cannot overrun the stage's net
                rate = totals["n"] / max(time.perf_counter() - began, 1e-6)
                size = max(1, min(size, int(rate * (seconds - (time.perf_counter() - began)))))
            report = verify(data, plan, runs=size, seed=1 + block).report
            mean, se = report.cost.value, report.cost.standard_error
            totals["sum"] += size * mean
            totals["squares"] += (size - 1) * size * se * se + size * mean * mean  # (n - 1) sd^2 + n mean^2 of the block: the sum of squares
            totals["unfinished"] += report.unfinished
            totals["stopped"] += report.stopped
            totals["n"] += size
            block += 1
            size = min(2 * size, SIM_BLOCK)
            record["simulate"] = pooled(totals, computed, time.perf_counter() - began)
            write(path, record)
    except Exception as error:  # noqa: BLE001 - recorded with what was played before it
        record["simulate"] = {**pooled(totals, computed, time.perf_counter() - began), "error": f"{type(error).__name__}: {error}"[:1000]}
        return
    record["simulate"] = pooled(totals, computed, time.perf_counter() - began)


def pooled(totals: dict, computed: float, seconds: float) -> dict:
    """The pooled mean, its standard error and z = (simulated - computed) / standard error of the plays so far."""
    n = totals["n"]
    if n == 0:
        return {"runs": 0, "computed": computed}
    mean = totals["sum"] / n
    variance = max(totals["squares"] - n * mean * mean, 0.0) / max(n - 1, 1)
    se = math.sqrt(variance / n)
    if se == 0:
        z = 0.0 if abs(mean - computed) <= TOLERANCE * max(1.0, abs(computed)) else math.inf
    else:
        z = (mean - computed) / se
    return {
        "runs": n, "mean": mean, "standard_error": se, "computed": computed, "z": z, "unfinished": totals["unfinished"], "stopped": totals["stopped"],
        "seconds": round(seconds, 1),
    }  # fmt: skip


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

            plan = plan_with_starts(data, target, prices, recipe_starts=True, start_price=case.start_price, solver="packed")
        else:
            plan = make_plan(data, target, prices, start_price=case.start_price, solver="packed", with_risk=False)
        record.update(status="solved", optimum=float(plan.mean_remaining), states=len(plan.solution.values), reason=None)
    except PlanError as error:
        record.update(status="refused", reason=f"{type(error).__name__}: {error}"[:1000])
    except Exception as error:  # noqa: BLE001
        record.update(status="error", reason=f"{type(error).__name__}: {error}"[:1000], trace=traceback.format_exc()[-3000:])
    watch.end()
    write(path, record)


def run_sleep_child(args) -> None:
    """A child that outlives its stage's limit (`--plan-seconds`): the watch must write its record and end it (the quick test of `Watch`)."""
    record: dict = {"mode": "sleep", "status": "running", "settings": settings(args)}
    watch = Watch(record, Path(args.out) / "cases" / f"{args.case.replace('/', '__')}.sleep.json", args.memory_mb)
    watch.start("plan", args.plan_seconds)
    time.sleep(60)
    record["status"] = "not stopped"
    watch.end()


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
    path.unlink(missing_ok=True)  # a record of an earlier run in the same folder is not this one's
    began = time.perf_counter()
    with open(log, "w", encoding="utf-8") as handle:
        # its own session, so that the child's pool workers (`parallel.py` forks them) end with it: `kill_tree` in the child, `_end_group` here
        process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT, cwd=ROOT, start_new_session=True)
        try:
            code = process.wait(timeout=wall)
        except subprocess.TimeoutExpired:
            _end_group(process)
            process.wait()
            code = "killed"
        _end_group(process)  # workers a finished child left behind
    try:
        record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"mode": mode}
    except ValueError as error:  # a record cut while written: what the log says is kept below
        record = {"mode": mode, "record_error": repr(error)[:200]}
    record["exit"] = code
    record["wall_seconds"] = round(time.perf_counter() - began, 1)
    if record.get("status") in (None, "running"):
        record["log_tail"] = log.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]
        if code == "killed":
            record["status"], record["reason"] = "stopped", f"the benchmark's wall of {wall:g} s for the whole case was reached"
        elif code in (-9, 137):
            record["status"], record["reason"] = "stopped", "killed by the system, probably out of memory (no record was written)"
        else:
            record["status"], record["reason"] = "error", f"exit {code} with no record"
        record.setdefault("no_plan", record.get("plan") is None)
    return record


def _end_group(process: subprocess.Popen) -> None:
    if hasattr(os, "killpg"):
        try:
            os.killpg(process.pid, 9)
        except OSError:  # the group is gone already
            pass
    else:
        process.kill()


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
    args.out = str(Path(args.out).resolve())  # the children run from the repository root
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    deadline = BEGAN + args.deadline_minutes * 60
    worst = SETUP_SECONDS + args.plan_seconds + GRACE_SECONDS + args.sim_seconds + SIM_GRACE_SECONDS + args.risk_seconds + CASE_SLACK
    say(f"part {part}/{parts}: {len(mine)} of {len(found)} cases; a case takes at most {worst:.0f} s, plus {args.walk_seconds + SETUP_SECONDS:.0f} s of walk")
    records = []
    for case in mine:
        left = deadline - time.perf_counter()
        head = case_head(case)
        if left < MIN_START_SECONDS:
            records.append({"case": head, "status": "not run", "reason": f"the part's deadline: {left:.0f} s left"})
            say(f"{case.id}: not run (deadline)")
            continue
        wall = min(worst, left - CASE_SLACK)
        say(f"{case.id}: plan (wall {wall:.0f} s) ...")
        planned = child(args, case.id, "plan", wall)
        planned.setdefault("case", head)
        if wall < worst and planned.get("exit") == "killed" and planned.get("plan") is None:  # the part's deadline cut it before a plan: run it again (`--only`)
            planned.update(status="not run", reason=f"the part's deadline cut the case after {wall:.0f} s")
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
    if status in ("planned", "stopped", "refused", "failed"):
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
        strip = ("progress_tail", "log_tail", "trace")  # those stay in the run's artifact
        record = {k: v for k, v in records[key].items() if k not in strip}
        if isinstance(record.get("walk"), dict):
            record["walk"] = {k: v for k, v in record["walk"].items() if k not in strip}
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
    one.add_argument("--mode", choices=("plan", "walk", "sleep"), required=True)  # sleep: the watch's own test (`tests/test_family_bench.py`)
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
        {"plan": run_plan_child, "walk": run_walk_child, "sleep": run_sleep_child}[args.mode](args)
    else:
        summarize(args)


if __name__ == "__main__":
    main()
