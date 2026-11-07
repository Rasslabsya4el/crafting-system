"""What the `actions:` key of a target hides: the walk and the envelope search of each route with the key kept, removed, and every kind named (ticket #475).

    python .github/scripts/actions_key.py plan    --count N                          which jobs each of N runners takes
    python .github/scripts/actions_key.py batch   --index I --count N --out DIR      run the jobs of runner I (the dispatcher's RUNNER_INDEX / RUNNER_COUNT)
    python .github/scripts/actions_key.py jobs    --jobs R08-kept-envelope,... --cap-minutes N --out DIR      named jobs under one cap
    python .github/scripts/actions_key.py one     --route R04 --variant removed --solver envelope --out DIR [--net-seconds S --memory-mb M]
    python .github/scripts/actions_key.py probe   --routes J01,V01 --index I --count N --out DIR      one more kind added to the key, one at a time
    python .github/scripts/actions_key.py summary --dir DIR --out DIR2               writes DIR2/summary.md

Seven targets carry an `actions:` key (J01, R04, R08, R09, R13, R14, V01). OR-5 says a target never restricts the actions, so the key goes.
A job is one route in one `variant` planned by one `solver`:

* `kept`: the target as committed (today's answer);
* `removed`: the key deleted from a copy of the target's text (the committed file is never written), which is what the product does for a target
  without the key: every kind it offers by default, the `opt_in` kinds (Exalted Orb, Annulment, Fracturing, the fossil sets) not among them;
* `all`: the key replaced, in the same copy, by every kind the planner can use (the `opt_in` ones too), which is what OR-5 asks for.

A fourth variant, `plus=KIND`, is for `probe`: the committed key with one more kind added, to find which kind makes a small route explode.

Solvers: `auto` is `make_plan`'s default (with 40 priced offers or more the bound pruning on the object solver, below that the walk on packed
arrays), `envelope` is `make_plan(solver="envelope")` (the exact branch and bound, ADR-0063). Each job runs in a child process with a wall-clock
cap and a memory cap, because a walk that does not finish is the measurement: the parent then records where the child stopped (the last progress
line, the number of `CompressedState` objects alive, the peak memory). The envelope also carries its own stop-and-say-so net (`Net`: seconds and
memory) so that it ends on its own with the plan and the interval `[LB, U]` where it can. The risk is never computed. The prices are the committed
snapshot of the benchmark routes (`PRICES`); V01 reads the price file its target names, as `benchmark` does.

For each job the record (`job-ROUTE-VARIANT-SOLVER.json`) holds: whether it finished, the path taken, the offers, the item states known (`walked`: for
the envelope the states it touched), the states the policy reaches (`kept`), the mean cost, the first actions of the plan and the labels it uses,
the seconds and the peak memory. `summary` joins the records into one table and lists, per route, where a variant changes the mean or the first action.

Never run on a PC for a real route: R04 and R14 hold hundreds of thousands of states. Run by `.github/scripts/heavy_dispatch.py` (docs/ci.md).
"""

import argparse
import faulthandler
import gc
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
import traceback
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRICES = "tests/fixtures/prices/routes-allflame-2026-11-07.json"  # from the project root; the prices of the packed-solver measurements (ADR-0063)
FORMAT = "crafting-system-actions-key/1"

ROUTES = ("J01", "R04", "R08", "R09", "R13", "R14", "V01")
J01_TARGET = "examples/targets/j01-cobalt-life-attack-speed.yaml"  # J01 is no benchmark route: its target is named here
VARIANTS = ("kept", "removed", "all")
SOLVERS = ("auto", "envelope")
CAP_MINUTES = {"J01": 8, "V01": 8, "R13": 15, "R08": 15, "R09": 15, "R04": 20, "R14": 20}  # wall-clock cap of a job that does not finish
KEPT_CAP_MINUTES = {"R04": 20, "R14": 45}  # the target as committed finishes (R14's walk takes about 35 minutes): it gets what it needs
NET_SHARE = 0.5  # the envelope's own time net is this share of the cap (the solve of the graph it ended with comes after it)
MEMORY_NET_MB = 10_000  # the envelope's own memory net
MEMORY_CAP_MB = 13_000  # the parent stops a child above this (a runner has 16 GB; one that runs out of memory leaves nothing)
GRACE_SECONDS = 60  # between the stack dump and the kill
BIN_MINUTES = 50  # the caps of the jobs of one runner add up to at most this (a run is stopped at 60 minutes, and starting takes a few)
STATUS_LINES = 3  # the last lines of a stopped job's log kept in its record


def job_id(route: str, variant: str, solver: str) -> str:
    return f"{route}-{variant}-{solver}"


def all_jobs(variants: Sequence[str] = VARIANTS) -> list[tuple[str, str, str]]:
    """Every job of the given variants (all three by default)."""
    return [(route, variant, solver) for route in ROUTES for variant in variants for solver in SOLVERS]


def cap_minutes(route: str, variant: str) -> int:
    return KEPT_CAP_MINUTES.get(route, CAP_MINUTES[route]) if variant == "kept" else CAP_MINUTES[route]


def bins_for(count: int, jobs: Sequence[tuple[str, str, str]] | None = None, limit: int | None = BIN_MINUTES) -> list[list[tuple[str, str, str]]]:
    """The jobs dealt over `count` runners, longest cap first onto the runner with the least load; `ValueError` when a runner would pass `limit` minutes."""
    chosen = list(all_jobs() if jobs is None else jobs)
    chosen.sort(key=lambda job: (-cap_minutes(job[0], job[1]), job))
    runners: list[list[tuple[str, str, str]]] = [[] for _ in range(count)]
    load = [0] * count
    for job in chosen:
        slot = min(range(count), key=lambda k: (load[k], k))
        runners[slot].append(job)
        load[slot] += cap_minutes(job[0], job[1])
    if limit is not None and max(load) > limit:
        raise ValueError(f"{count} runners cannot take the jobs inside {limit} minutes each (the busiest has {max(load)}); use more runners")
    return runners


# --- the target of a variant ---------------------------------------------------------------------


KEY = re.compile(r"(?m)^actions:[^\n]*\n(?:[ \t]+(?:-|#)[^\n]*\n)*")  # the key and, for a list on the next lines, its items


def key_names(text: str) -> list[str]:
    """The names in the `actions:` key of a target's text, whether it is written as a flow list or as lines."""
    found = KEY.search(text)
    if found is None:
        return []
    block = re.sub(r"(?m)#.*$", "", found.group(0)).removeprefix("actions:").strip()
    if block.startswith("["):
        return [name.strip() for name in block.strip("[]").split(",") if name.strip()]
    return [line.strip().removeprefix("-").strip() for line in block.splitlines() if line.strip()]


def with_variant(text: str, variant: str, kinds: Sequence[str] = ()) -> str:
    """`text` of a target with its `actions:` key kept, removed, or replaced by `kinds` (every kind the planner can use for `all`).

    Raises `ValueError` when the text has no key or still has one after the change: a variant that did not change anything is not a measurement.
    """
    if variant not in VARIANTS and not variant.startswith("plus="):
        raise ValueError(f"variant must be one of {', '.join(VARIANTS)} or plus=KIND, got {variant!r}")
    if variant == "kept":
        return text
    if len(KEY.findall(text)) != 1:
        raise ValueError("the target must have exactly one top-level `actions:` key")
    if variant.startswith("plus="):
        names = [*key_names(text), variant.removeprefix("plus=")]
        return KEY.sub(lambda _found: "actions: [" + ", ".join(names) + "]\n", text, count=1)
    if variant == "removed":
        changed = KEY.sub("", text, count=1)
    else:
        changed = KEY.sub(lambda _found: "actions: [" + ", ".join(kinds) + "]\n", text, count=1)
    if variant == "removed" and re.search(r"(?m)^actions:", changed):
        raise ValueError("the key is still in the text after it was removed")
    return changed


def every_kind() -> tuple[str, ...]:
    """The names of the kinds the planner can use, `opt_in` ones too; a kind that needs Memory Strands is no kind of a plan without them."""
    from crafting_system.actions import kinds

    return tuple(entry.name for entry in kinds(planner_only=True) if not entry.needs_strands)


def target_path(route: str) -> Path:
    if route == "J01":
        return ROOT / J01_TARGET
    from crafting_system.cli._benchmark import BENCHMARKS

    return ROOT / next(bench.target for bench in BENCHMARKS if bench.id == route)


def load_variant(route: str, variant: str, data):
    """`(target, bench)` of the route in a variant: the committed text with the key changed, read as `load_target` reads a file."""
    from crafting_system.cli._benchmark import BENCHMARKS
    from crafting_system.targets import TargetError  # noqa: F401  (the error a variant may give)
    from crafting_system.targets.parse import parse_target_text

    path = target_path(route)
    text = path.read_bytes().decode("utf-8-sig")
    text = with_variant(text, variant, every_kind() if variant == "all" else ())
    bench = next((each for each in BENCHMARKS if each.id == route), None)
    return parse_target_text(text, data, f"{path} [{variant}]", path.parent), bench


# --- one job -------------------------------------------------------------------------------------


def peak_mb() -> int | None:
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    except ImportError:
        return None


def live_states() -> int:
    """How many `CompressedState` objects are alive now (a rough size of the graph a stopped search held)."""
    from crafting_system.abstraction import CompressedState

    return sum(1 for each in gc.get_objects() if type(each) is CompressedState)


def reached_count(plan) -> int:
    """The states the plan's policy reaches from the start (a packed policy holds exactly these; an object policy holds every state it solved)."""
    if plan.packed is not None:
        return len(plan.policy)
    seen, order = {plan.start}, [plan.start]
    for state in order:
        action = plan.policy.get(state)
        if action is None:
            continue
        for successor, weight in action.outcomes:
            if weight > 0 and successor not in seen and not plan.is_goal(successor):
                seen.add(successor)
                order.append(successor)
    return sum(1 for state in order if state in plan.policy)


def offer_label(plan, state) -> str | None:
    if plan.packed is not None:
        try:
            return plan.policy.offer(state).label
        except KeyError:
            return None
    action = plan.policy.get(state)
    return None if action is None else action.label


def first_actions(plan, steps: int = 8) -> list[str]:
    """The action at the start, then at each next state along the likeliest outcome that is not a goal (up to `steps`)."""
    out: list[str] = []
    state = plan.start
    seen = {state}
    for _ in range(steps):
        label = offer_label(plan, state)
        if label is None:
            break
        out.append(label)
        action = plan.policy[state]
        best = max(
            ((s, w) for s, w in action.outcomes if s not in seen and not plan.is_goal(s) and offer_label(plan, s) is not None),
            key=lambda pair: pair[1],
            default=None,
        )
        if best is None:
            break
        state = best[0]
        seen.add(state)
    return out


def labels_used(plan) -> dict[str, int]:
    """How many states of the policy take each offer (the labels as the plan prints them)."""
    if plan.packed is not None:
        return dict(Counter(priced.label for _state, priced in plan.policy.offers()).most_common())
    return dict(Counter(action.label for action in plan.policy.values()).most_common())


def plan_of_job(route: str, variant: str, solver: str, data, net=None):
    from crafting_system.cli._inputs import load_target_prices
    from crafting_system.cli._plan import make_plan
    from crafting_system.cli._starts import plan_with_starts
    from crafting_system.config import load_config
    from crafting_system.prices import load_price_file

    target, bench = load_variant(route, variant, data)
    starts = bench is not None and bench.start is not None
    prices = load_target_prices(target.price_file, load_config(None)) if starts else load_price_file(ROOT / PRICES)
    options = {"net": net} if net is not None else {}
    if starts:  # `plan_with_starts` plans each start without the risk and measures it for the one it keeps (V01 is small)
        return plan_with_starts(data, target, prices, solver=solver, **options)
    return make_plan(data, target, prices, with_risk=False, solver=solver, **options)


def measure(route: str, variant: str, solver: str, data, *, net=None, say: Callable[[str], None] = lambda _text: None) -> dict:
    """The record of one job that ran to its end (or to the envelope's own net, or to a refusal)."""
    from crafting_system.cli._plan import PlanError

    began = time.perf_counter()
    record: dict = {
        "format": FORMAT, "route": route, "variant": variant, "solver": solver, "finished": False, "stop": None, "error": None,
    }  # fmt: skip
    try:
        plan = plan_of_job(route, variant, solver, data, net)
    except Exception as error:  # a refusal is an answer: the text says what the variant meets; a crash is one too, and does not end the other jobs
        text = f"{type(error).__name__}: {error}"
        if not isinstance(error, (PlanError, ValueError, OSError)):
            text += " | " + " < ".join(f"{frame.name}:{frame.lineno}" for frame in reversed(traceback.extract_tb(error.__traceback__)[-4:]))
        record.update(error=text[:700], seconds=round(time.perf_counter() - began, 1), peak_mb=peak_mb())
        return record
    elapsed = time.perf_counter() - began
    say(f"planned in {plan.solve_seconds:.0f} s ({elapsed:.0f} s with the inputs)")
    info = plan.packed.info.get("envelope") if plan.packed is not None else None
    path = "envelope" if info is not None else "packed" if plan.packed is not None else "pruned" if plan.pruned is not None else "object"
    kinds = Counter(priced.offer.kind for priced in plan.offers)
    record.update(
        finished=True,
        path=path,
        offers=len(plan.offers),
        offer_kinds=dict(kinds.most_common()),
        walked=len(plan.solution.values),
        kept=reached_count(plan),
        classes=plan.packed.info.get("classes") if plan.packed is not None else None,
        mean=plan.mean_remaining,
        start_price=plan.start_price.chaos,
        start_label=offer_label(plan, plan.start),
        start_key=plan.starts.chosen.key if plan.starts is not None else None,
        first_actions=first_actions(plan),
        labels_used=labels_used(plan),
        solve_seconds=round(plan.solve_seconds, 1),
        seconds=round(time.perf_counter() - began, 1),
        peak_mb=peak_mb(),
    )
    if info is not None:
        record.update(
            exact=info.exact, envelope_stop=info.stopped, lower=info.lower, upper=info.upper, rounds=info.rounds,
            touched=info.touched, expanded=info.expanded, realized=info.realized, candidates=info.candidates, bound_keys=info.bound_keys,
        )  # fmt: skip
    return record


def clean(value):
    """The record with every infinite or NaN number replaced by None (JSON has none)."""
    if isinstance(value, dict):
        return {key: clean(each) for key, each in value.items()}
    if isinstance(value, list):
        return [clean(each) for each in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(record), indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def one_command(arguments: argparse.Namespace) -> int:
    from crafting_system.cli import _packed
    from crafting_system.cli._envelope import Net
    from crafting_system.data import load_game_data

    out = Path(arguments.out)
    name = job_id(arguments.route, arguments.variant, arguments.solver)
    began = time.perf_counter()

    def say(line: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f} s, {peak_mb()} MB] {line}", flush=True)

    if hasattr(signal, "SIGUSR1"):
        faulthandler.register(signal.SIGUSR1, file=sys.stdout, all_threads=True)  # the parent asks for the stack before it stops the job
    if hasattr(signal, "SIGTERM"):

        def stopping(_signal, _frame):
            say("stopping: counting the states alive")
            write_record(out / f"stop-{name}.json", {"live_states": live_states(), "peak_mb": peak_mb(), "seconds": round(time.perf_counter() - began, 1)})
            os._exit(0)

        signal.signal(signal.SIGTERM, stopping)
    _packed.PROGRESS = say
    data = load_game_data()
    net = None
    if arguments.solver == "envelope":
        net = Net(seconds=arguments.net_seconds, memory_mb=arguments.memory_mb)
    say(f"{name}: start")
    record = measure(arguments.route, arguments.variant, arguments.solver, data, net=net, say=say)
    write_record(out / f"job-{name}.json", record)
    say(f"{name}: written ({'finished' if record['finished'] else 'refused: ' + str(record['error'])[:200]})")
    return 0


# --- the parent that runs the jobs of one runner -------------------------------------------------


def read_status(pid: int) -> tuple[int | None, int | None]:
    """`(resident, peak)` memory of a process in MB, from /proc (None where the system has none)."""
    try:
        with open(Path(os.sep, "proc", str(pid), "status"), encoding="utf-8") as handle:
            fields = dict(line.split(":", 1) for line in handle if ":" in line)
        return int(fields["VmRSS"].split()[0]) // 1024, int(fields["VmHWM"].split()[0]) // 1024
    except (OSError, KeyError, ValueError):
        return None, None


def tail(path: Path, lines: int) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except OSError:
        return []


def run_job(route: str, variant: str, solver: str, out: Path, *, cap: float | None = None, memory_cap: int = MEMORY_CAP_MB) -> dict:
    """Run one job in a child process and return its record; a child that has to be stopped leaves where it was in the record."""
    minutes = cap_minutes(route, variant) if cap is None else cap
    name = job_id(route, variant, solver)
    log = out / f"log-{name}.txt"
    out.mkdir(parents=True, exist_ok=True)
    for old in (out / f"job-{name}.json", out / f"stop-{name}.json"):
        old.unlink(missing_ok=True)
    command = [
        sys.executable, "-u", str(Path(__file__).resolve()), "one", "--route", route, "--variant", variant, "--solver", solver, "--out", str(out),
        "--net-seconds", str(minutes * 60 * NET_SHARE), "--memory-mb", str(MEMORY_NET_MB),
    ]
    began = time.monotonic()
    stop = None
    peak = 0
    with open(log, "w", encoding="utf-8") as handle:
        child = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT)
        while child.poll() is None:
            time.sleep(2)
            resident, high = read_status(child.pid)
            peak = max(peak, high or 0, resident or 0)
            if time.monotonic() - began > minutes * 60:
                stop = f"the cap of {minutes} minutes"
            elif resident is not None and resident > memory_cap:
                stop = f"the memory cap of {memory_cap:,} MB (resident {resident:,} MB)"
            if stop is not None:
                if hasattr(signal, "SIGUSR1"):
                    child.send_signal(signal.SIGUSR1)  # the stack where the job is
                    time.sleep(1)
                child.terminate()
                try:
                    child.wait(timeout=GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                break
    seconds = round(time.monotonic() - began, 1)
    found = out / f"job-{name}.json"
    if found.exists() and stop is None:
        record = json.loads(found.read_text(encoding="utf-8"))
        record["peak_mb"] = max(record.get("peak_mb") or 0, peak) or None
        record["wall_seconds"] = seconds
        write_record(found, record)
        return record
    record = {
        "format": FORMAT, "route": route, "variant": variant, "solver": solver, "finished": False, "error": None,
        "stop": stop or f"the job ended with exit code {child.returncode} and no record",
        "seconds": seconds, "peak_mb": peak or None, "last_lines": [line[:300] for line in tail(log, STATUS_LINES + 40) if line.startswith("[")][-STATUS_LINES:],
    }  # fmt: skip
    after = out / f"stop-{name}.json"
    if after.exists():
        record["live_states"] = json.loads(after.read_text(encoding="utf-8")).get("live_states")
    write_record(found, record)
    return record


def say_job(record: dict) -> str:
    where = f"{record['route']} {record['variant']} {record['solver']}"
    if record.get("finished"):
        return f"{where}: mean {record['mean']!r}, {record['walked']:,} known, {record['kept']:,} kept, {record['seconds']} s, {record['peak_mb']} MB"
    return f"{where}: {'refused: ' + record['error'] if record.get('error') else 'stopped: ' + str(record.get('stop'))} ({record.get('seconds')} s, {record.get('peak_mb')} MB)"


def batch_command(arguments: argparse.Namespace) -> int:
    jobs = all_jobs(variants_of(arguments.variants))
    mine = bins_for(arguments.count, jobs, limit=None if arguments.no_limit else BIN_MINUTES)[arguments.index - 1]
    print(f"runner {arguments.index} of {arguments.count}: {', '.join(job_id(*job) for job in mine)}", flush=True)
    for route, variant, solver in mine:
        print(say_job(run_job(route, variant, solver, Path(arguments.out))), flush=True)
    return 0


def variants_of(text: str) -> tuple[str, ...]:
    chosen = tuple(name for name in text.split(",") if name)
    unknown = [name for name in chosen if name not in VARIANTS]
    if unknown or not chosen:
        raise SystemExit(f"variants must be some of {', '.join(VARIANTS)}, got {text!r}")
    return chosen


def probe_jobs(routes: Sequence[str], text_of: Callable[[str], str] | None = None) -> list[tuple[str, str, str]]:
    """The probes: for each route, each kind the planner can use that its key does not name, added to the key alone, under each solver."""
    from_file = text_of or (lambda route: target_path(route).read_bytes().decode("utf-8-sig"))
    kinds_all = every_kind()
    jobs = []
    for route in routes:
        named = set(key_names(from_file(route)))
        jobs += [(route, f"plus={kind}", solver) for kind in kinds_all if kind not in named for solver in SOLVERS]
    return jobs


def probe_command(arguments: argparse.Namespace) -> int:
    """Run this runner's share of the probes, each under `--cap-seconds`."""
    routes = [name for name in arguments.routes.split(",") if name]
    mine = probe_jobs(routes)[arguments.index - 1 :: arguments.count]
    print(f"runner {arguments.index} of {arguments.count}: {len(mine)} probes", flush=True)
    for route, variant, solver in mine:
        print(say_job(run_job(route, variant, solver, Path(arguments.out), cap=arguments.cap_seconds / 60)), flush=True)
    return 0


def jobs_command(arguments: argparse.Namespace) -> int:
    """Run the named jobs one after the other on this runner, each under `--cap-minutes` (a second look at jobs the caps of `batch` stopped)."""
    for name in arguments.jobs.split(","):
        route, variant, solver = name.split("-")
        if (route, variant, solver) not in all_jobs():
            raise SystemExit(f"{name!r} is no job; a job is ROUTE-VARIANT-SOLVER, such as R08-kept-envelope")
        print(say_job(run_job(route, variant, solver, Path(arguments.out), cap=arguments.cap_minutes)), flush=True)
    return 0


def plan_command(arguments: argparse.Namespace) -> int:
    for number, mine in enumerate(bins_for(arguments.count, all_jobs(variants_of(arguments.variants)), limit=None), 1):
        total = sum(cap_minutes(route, variant) for route, variant, _ in mine)
        print(f"runner {number}: {total:3d} min  {', '.join(job_id(*job) for job in mine)}")
    return 0


# --- the summary ---------------------------------------------------------------------------------


def number(value) -> str:
    return "-" if value is None else f"{value:,}"


def mean_text(value) -> str:
    return "-" if value is None else f"{value:,.4f}"


def result_text(record: Mapping | None) -> str:
    if record is None:
        return "missing"
    if record.get("error"):
        return "refused"
    if not record.get("finished"):
        return "stopped"
    if record.get("exact") is False:
        return "net stop"
    return "done"


def _row(cells: Sequence[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    return [_row(header), _row(["---"] * len(header)), *(_row(row) for row in rows)]


def read_records(folder: Path) -> dict[tuple[str, str, str], dict]:
    found = {}
    for path in sorted(folder.rglob("job-*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        found[(record["route"], record["variant"], record["solver"])] = record
    return found


def short_stop(text: str) -> str:
    """A stop reason in a few words: `cap 15 min`, `memory 13 GB`."""
    found = re.search(r"cap of ([\d.]+) minutes", text)
    if found and "memory" not in text:
        return f"cap {found.group(1).removesuffix('.0')} min"
    found = re.search(r"memory cap of ([\d,]+) MB", text)
    return f"memory {int(found.group(1).replace(',', '')) // 1000} GB" if found else text[:40]


def cell(record: Mapping | None) -> str:
    """One job in a few words for the table: the mean and the sizes when it finished, where it was when it did not."""
    if record is None:
        return "missing"
    if record.get("error"):
        return "refused: " + ("no policy reaches the goal" if "no policy" in record["error"] else "the bound cannot be built (#507)" if "crafted-pattern bound" in record["error"] else record["error"][:60])
    if not record.get("finished"):
        alive = f"{record['live_states']:,} states alive" if record.get("live_states") is not None else ""
        building = re.search(r"keys found ([\d,]+) expanded ([\d,]+)", " ".join(record.get("last_lines") or []))
        if building:  # the envelope was still building its bound (the walk-free model of #497), which its net does not cover
            alive = f"in the bound: {building.group(1)} keys found, {building.group(2)} expanded"
        return f"stopped ({short_stop(str(record.get('stop')))}) {alive}; {round(record.get('seconds') or 0):,} s; {number(record.get('peak_mb'))} MB".replace(" ;", ";")
    net = " (net stop, not shown best)" if record.get("exact") is False else ""
    return f"{record['mean']:,.2f}{net}; {number(record.get('walked'))} known, {number(record.get('kept'))} kept; {round(record.get('seconds') or 0):,} s; {number(record.get('peak_mb'))} MB"


def runs_of(labels: Sequence[str]) -> list[str]:
    """`labels` with each run of the same label written once, `Chaos Orb x7` for seven in a row."""
    out: list[str] = []
    for label in labels:
        if out and out[-1].split(" x")[0] == label:
            count = int(out[-1].rsplit(" x", 1)[1]) + 1 if " x" in out[-1] and out[-1].rsplit(" x", 1)[1].isdigit() else 2
            out[-1] = f"{label} x{count}"
        else:
            out.append(label)
    return out


def relative(a: float, b: float) -> float:
    scale = max(abs(a), abs(b))
    return abs(a - b) / scale if scale > 0 else 0.0


def build_summary(records: Mapping[tuple[str, str, str], dict], run_ids: str = "") -> str:
    lines = [
        "# the actions: key of the targets (#475)",
        "",
        "`kept`: the target as committed. `removed`: the key deleted (the kinds offered by default; the opt-in kinds, the fossil sets among them, are not).",
        "`all`: every kind the planner can use named. `auto`: `make_plan`'s default solver; `envelope`: `make_plan(solver=\"envelope\")`.",
        "`known`: the item states the walk found (for the envelope, the states it touched); `kept`: the states the policy reaches. A stopped job shows the size",
        "it had when it was stopped (`alive`: the `CompressedState` objects alive).",
    ]
    if run_ids:
        lines += ["", f"Runs: {run_ids}"]
    lines += ["", "## the table: a route and a solver, the key kept, removed, and every kind named", ""]
    compact = []
    for route in ROUTES:
        for solver in SOLVERS:
            compact.append([route, solver, *(cell(records.get((route, variant, solver))) for variant in VARIANTS)])
    lines += _table(["route", "solver", "kept", "removed", "all"], compact)
    lines += ["", "## every job", ""]
    rows = []
    for route in ROUTES:
        for variant in VARIANTS:
            for solver in SOLVERS:
                record = records.get((route, variant, solver))
                status = result_text(record)
                if record is None:
                    rows.append([route, variant, solver, status, *[""] * 8])
                    continue
                if status == "refused":
                    rows.append([route, variant, solver, status, str(record["error"])[:140], *[""] * 7])
                    continue
                size = number(record.get("walked")) if record.get("finished") else f"alive {number(record.get('live_states'))}"
                rows.append(
                    [
                        route, variant, solver, status if status != "stopped" else f"stopped: {record.get('stop')}",
                        record.get("path") or "-", number(record.get("offers")), size, number(record.get("kept")), mean_text(record.get("mean")),
                        number(record.get("seconds")), number(record.get("peak_mb")),
                    ]
                )  # fmt: skip
    lines += _table(["route", "key", "solver", "result", "path", "offers", "known", "kept", "mean (Chaos, after the start item)", "seconds", "peak MB"], rows)
    lines += ["", "## first actions of the plans that finished", ""]
    firsts = []
    for route in ROUTES:
        for variant in VARIANTS:
            for solver in SOLVERS:
                record = records.get((route, variant, solver))
                if record is not None and record.get("finished"):
                    firsts.append([route, variant, solver, " > ".join(runs_of(record.get("first_actions") or []))])
    lines += _table(["route", "key", "solver", "the start action, then the likeliest next ones"], firsts)
    lines += ["", "## what the key hid: a variant against `kept` (same solver)", ""]
    changes = []
    for route in ROUTES:
        for solver in SOLVERS:
            base = records.get((route, "kept", solver))
            for variant in ("removed", "all"):
                record = records.get((route, variant, solver))
                if base is None or record is None or not base.get("finished") or not record.get("finished"):
                    changes.append([route, solver, variant, "no comparison: " + result_text(base) + " against " + result_text(record), "", ""])
                    continue
                gap = relative(base["mean"], record["mean"])
                same_mean = "same" if gap <= 1e-9 else f"{base['mean']:,.4f} to {record['mean']:,.4f} ({(record['mean'] - base['mean']) / base['mean']:+.2%})"
                same_first = "same" if base.get("start_label") == record.get("start_label") else f"{base.get('start_label')} to {record.get('start_label')}"
                changes.append([route, solver, variant, same_mean, same_first, ", ".join(sorted(set(record.get("labels_used") or {}) - set(base.get("labels_used") or {})))[:160]])
    lines += _table(["route", "solver", "key", "mean", "start action", "offers the plan newly uses"], changes)
    probes = sorted((r for r in records.values() if r["variant"].startswith("plus=")), key=lambda r: (r["route"], r["variant"], r["solver"]))
    if probes:
        lines += ["", "## one kind added to the key of a small route (the probes)", ""]
        base = {(r["route"], r["solver"]): r for r in records.values() if r["variant"] == "kept"}
        rows = []
        for r in probes:
            kept = base.get((r["route"], r["solver"]))
            gap = ""
            if r.get("finished") and kept is not None and kept.get("finished") and relative(kept["mean"], r["mean"]) > 1e-9:
                gap = f"mean {kept['mean']:,.4f} to {r['mean']:,.4f}"
            rows.append([r["route"], r["variant"].removeprefix("plus="), r["solver"], cell(r), gap])
        lines += _table(["route", "kind added", "solver", "result", "the mean moves"], rows)
    records = {key: record for key, record in records.items() if not record["variant"].startswith("plus=")}
    stopped = [r for r in records.values() if not r.get("finished") and not r.get("error")]
    if stopped:
        lines += ["", "## where the stopped jobs were", ""]
        for r in sorted(stopped, key=lambda r: (r["route"], r["variant"], r["solver"])):
            last = "; ".join(r.get("last_lines") or [])
            lines.append(f"- {r['route']} {r['variant']} {r['solver']}: {r.get('stop')}, {r.get('seconds')} s, peak {number(r.get('peak_mb'))} MB, alive {number(r.get('live_states'))} states. Last: {last}")
    return "\n".join(lines) + "\n"


def summary_command(arguments: argparse.Namespace) -> int:
    text = build_summary(read_records(Path(arguments.dir)), arguments.runs or "")
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.md").write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="which jobs each runner takes")
    plan.add_argument("--count", type=int, required=True)
    plan.add_argument("--variants", default=",".join(VARIANTS), help="comma separated variants (default all)")
    plan.set_defaults(handler=plan_command)
    batch = commands.add_parser("batch", help="run the jobs of one runner")
    batch.add_argument("--index", type=int, required=True, help="RUNNER_INDEX, 1..count")
    batch.add_argument("--count", type=int, required=True, help="RUNNER_COUNT")
    batch.add_argument("--out", required=True)
    batch.add_argument("--variants", default=",".join(VARIANTS), help="comma separated variants to run (default all); the runners are dealt only these")
    batch.add_argument("--no-limit", action="store_true", help="deal the jobs over the runners even when one passes the minutes a runner may take")
    batch.set_defaults(handler=batch_command)
    probe = commands.add_parser("probe", help="add one kind at a time to the committed key of small routes")
    probe.add_argument("--routes", default="J01,V01", help="comma separated routes (default J01,V01)")
    probe.add_argument("--index", type=int, required=True, help="RUNNER_INDEX, 1..count")
    probe.add_argument("--count", type=int, required=True, help="RUNNER_COUNT")
    probe.add_argument("--cap-seconds", type=float, default=45, help="the wall-clock cap of each probe")
    probe.add_argument("--out", required=True)
    probe.set_defaults(handler=probe_command)
    jobs = commands.add_parser("jobs", help="run the named jobs here, each under one cap")
    jobs.add_argument("--jobs", required=True, help="comma separated ROUTE-VARIANT-SOLVER names")
    jobs.add_argument("--cap-minutes", type=float, required=True, help="the wall-clock cap of each job (the runner's own limit is 60 minutes in all)")
    jobs.add_argument("--out", required=True)
    jobs.set_defaults(handler=jobs_command)
    one = commands.add_parser("one", help="run one job in this process (the child of `batch`)")
    one.add_argument("--route", required=True, choices=ROUTES)
    one.add_argument("--variant", required=True, help="kept, removed, all, or plus=KIND")
    one.add_argument("--solver", required=True, choices=SOLVERS)
    one.add_argument("--out", required=True)
    one.add_argument("--net-seconds", type=float, help="the envelope's own time net")
    one.add_argument("--memory-mb", type=float, help="the envelope's own memory net")
    one.set_defaults(handler=one_command)
    summary = commands.add_parser("summary", help="the table of the jobs measured")
    summary.add_argument("--dir", required=True, help="the folder holding the job-*.json files (searched in subfolders too)")
    summary.add_argument("--out", required=True)
    summary.add_argument("--runs", help="text naming the runs the records come from")
    summary.set_defaults(handler=summary_command)
    arguments = parser.parse_args(argv)
    return arguments.handler(arguments)


if __name__ == "__main__":
    sys.exit(main())
