"""Where the bound's build spends its time, and the envelope search of the seven keyed routes with and without every kind named (ticket #626).

    python .github/scripts/bound_build.py profile --route R08 --variant kept|all [--cap-minutes N] [--out DIR]
    python .github/scripts/bound_build.py jobs    --jobs R08-kept,R04-all,... [--cap-minutes N] [--out DIR]
    python .github/scripts/bound_build.py one     --route R04 --variant all [--net-seconds S --memory-mb M] [--solver envelope|auto] [--out DIR]

`profile` builds the bound alone (`pattern_lower_bound`, the call `envelope_result` makes first) in the process it runs in, with a sampler of the main thread's stack
(the time inside each function of the product, by the call stacks, every 0.2 s) and a timer around the named stages of the build. It reads the same
inputs as `make_plan` and stops at the end of the build, or at the cap with the table printed. `jobs` and `one` plan the route by `make_plan` (the envelope search, or the
full walk with `--solver auto`) under the stop-and-say-so net (`Net`), each job in a child process with a wall-clock cap and a memory cap: a job that does not
end is the measurement, and the parent then writes where it stopped. Each job writes `job-ROUTE-VARIANT-SOLVER.json`. The variants: `kept` is the target as committed;
`all` replaces its `actions:` key by every kind the planner can use (OR-5), in a copy of the text; the committed file is never written.

Never run on a PC for a real route (docs/ci.md): run by `.github/scripts/heavy_dispatch.py`.
"""

import argparse
import faulthandler
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import traceback
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRICES = "tests/fixtures/prices/routes-allflame-2026-10-31.json"
J01_TARGET = "examples/targets/j01-cobalt-life-attack-speed.yaml"
ROUTES = ("J01", "R04", "R08", "R09", "R13", "R14", "V01")
KEY = re.compile(r"(?m)^actions:[^\n]*\n(?:[ \t]+(?:-|#)[^\n]*\n)*")
MEMORY_CAP_MB = 13_000
GRACE_SECONDS = 60


def peak_mb() -> int | None:
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    except ImportError:
        return None


def resident_mb() -> int | None:
    from crafting_system.cli._envelope import resident_mb as read

    found = read()
    return None if found is None else int(found)


def every_kind() -> tuple[str, ...]:
    from crafting_system.actions import kinds

    return tuple(entry.name for entry in kinds(planner_only=True) if not entry.needs_strands)


def target_path(route: str) -> Path:
    if route == "J01":
        return ROOT / J01_TARGET
    from crafting_system.cli._benchmark import BENCHMARKS

    return ROOT / next(bench.target for bench in BENCHMARKS if bench.id == route)


def variant_text(text: str, variant: str) -> str:
    """`text` of a target with its `actions:` key kept, or replaced by every kind the planner can use."""
    if variant == "kept":
        return text
    if variant != "all":
        raise ValueError(f"variant must be kept or all, got {variant!r}")
    if len(KEY.findall(text)) != 1:
        raise ValueError("the target must have exactly one top-level `actions:` key")
    return KEY.sub(lambda _found: "actions: [" + ", ".join(every_kind()) + "]\n", text, count=1)


def load_variant(route: str, variant: str, data):
    from crafting_system.cli._benchmark import BENCHMARKS
    from crafting_system.targets.parse import parse_target_text

    path = target_path(route)
    text = variant_text(path.read_bytes().decode("utf-8-sig"), variant)
    bench = next((each for each in BENCHMARKS if each.id == route), None)
    return parse_target_text(text, data, f"{path} [{variant}]", path.parent), bench


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
    if starts:
        return plan_with_starts(data, target, prices, solver=solver, **options)
    return make_plan(data, target, prices, with_risk=False, solver=solver, **options)


# ---- the profile of the build ---------------------------------------------------------------------------------------------


class Stop(Exception):
    """Raised by the hooked bound to end the plan once the build was measured."""


class Sampler(threading.Thread):
    """Samples the main thread's stack: self time by the innermost product frame, inclusive time by every product frame on the stack."""

    def __init__(self, main_id: int, interval: float = 0.2) -> None:
        super().__init__(daemon=True)
        self.main_id, self.interval = main_id, interval
        self.inclusive: Counter = Counter()
        self.own: Counter = Counter()
        self.samples = 0
        self.stopped = threading.Event()

    def run(self) -> None:
        while not self.stopped.wait(self.interval):
            frame = sys._current_frames().get(self.main_id)
            if frame is None:
                continue
            self.samples += 1
            seen: set[str] = set()
            innermost = None
            while frame is not None:
                path = frame.f_code.co_filename.replace("\\", "/")
                if "/crafting_system/" in path:
                    name = f"{path.rsplit('/crafting_system/', 1)[1]}:{frame.f_code.co_name}"
                    if innermost is None:
                        innermost = f"{name}:{frame.f_lineno}"
                    seen.add(name)
                frame = frame.f_back
            for name in seen:
                self.inclusive[name] += 1
            self.own[innermost or "(outside the product)"] += 1

    def table(self, top: int = 30) -> list[str]:
        total = max(self.samples, 1)
        lines = [f"samples {self.samples} ({self.samples * self.interval:.0f} s)", "-- inclusive (share of the samples) --"]
        lines += [f"{count / total:6.1%} {name}" for name, count in self.inclusive.most_common(top)]
        lines.append("-- self, by line --")
        lines += [f"{count / total:6.1%} {name}" for name, count in self.own.most_common(top // 2)]
        return lines


STAGES = (
    ("crafting_system.abstraction._pattern", "Pattern", "members"),
    ("crafting_system.abstraction._pattern", "Pattern", "key"),
    ("crafting_system.abstraction._pattern", "Pattern", "note"),
    ("crafting_system.abstraction._pattern", "Pattern", "mode_of"),
    ("crafting_system.abstraction._pattern", None, "_kernel_id"),
    ("crafting_system.abstraction._pattern", None, "_gap_everywhere"),
    ("crafting_system.abstraction._kernel", "Abstraction", "kernel_key"),
    ("crafting_system.abstraction._kernel", "Abstraction", "kernel"),
    ("crafting_system.abstraction._kernel", "Abstraction", "_fracture_entries"),
    ("crafting_system.cli._pattern_bound", None, "pack_pattern_model"),
    ("crafting_system.cli._pattern_bound", None, "solve_packed"),
)


def install_timers(table: dict[str, list[float]]) -> None:
    """Wrap the stages of the build in timers (calls, seconds inclusive of what they call)."""
    import importlib

    for module_name, class_name, name in STAGES:
        module = importlib.import_module(module_name)
        owner = getattr(module, class_name) if class_name else module
        original = getattr(owner, name)
        label = f"{class_name + '.' if class_name else ''}{name}"
        table[label] = [0, 0.0]

        def timed(*args, __original=original, __label=label, **kwargs):
            began = time.perf_counter()
            try:
                return __original(*args, **kwargs)
            finally:
                entry = table[__label]
                entry[0] += 1
                entry[1] += time.perf_counter() - began

        setattr(owner, name, timed)


def profile_command(arguments: argparse.Namespace) -> int:
    from crafting_system.cli import _envelope_plan, _packed
    from crafting_system.data import load_game_data

    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    began = time.perf_counter()
    name = f"{arguments.route}-{arguments.variant}"

    def say(line: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f} s, {resident_mb()} MB] {line}", flush=True)

    sampler = Sampler(threading.main_thread().ident)
    timers: dict[str, list[float]] = {}
    record: dict = {"route": arguments.route, "variant": arguments.variant, "finished": False}

    def report(final: bool) -> None:
        lines = sampler.table()
        lines += ["-- stages (calls, seconds inclusive) --"] + [f"{calls:>10,.0f} {seconds:9.1f} s {label}" for label, (calls, seconds) in timers.items()]
        text = "\n".join(lines)
        (out / f"profile-{name}.txt").write_text(text + "\n", encoding="utf-8")
        record.update(peak_mb=peak_mb(), seconds=round(time.perf_counter() - began, 1), stages={label: [calls, round(seconds, 2)] for label, (calls, seconds) in timers.items()})
        (out / f"profile-{name}.json").write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
        if final:
            print(text, flush=True)

    def watch() -> None:
        deadline = began + arguments.cap_minutes * 60
        last = time.perf_counter()
        while True:
            time.sleep(1)
            now = time.perf_counter()
            if now > deadline:
                record["stop"] = f"the cap of {arguments.cap_minutes} minutes"
                report(True)
                faulthandler.dump_traceback(file=sys.stdout, all_threads=True)
                sys.stdout.flush()
                os._exit(0)
            if now - last >= 120:
                last = now
                report(False)
                print("\n".join(sampler.table(12)), flush=True)

    data = load_game_data()
    install_timers(timers)
    real = _envelope_plan.pattern_lower_bound

    def hooked(abstraction, start, offers, **options):
        kinds = Counter(priced.offer.kind for priced in offers)
        record["offers"] = len(offers)
        record["offer_kinds"] = dict(kinds.most_common())
        say(f"the build starts: {len(offers):,} offers, kinds {dict(kinds.most_common(12))}")
        sampler.start()
        threading.Thread(target=watch, daemon=True).start()
        bound = real(abstraction, start, offers, **{**options, "progress": say})
        stats = bound.model.stats
        record.update(
            finished=True, keys=stats.keys, kernels=stats.kernels, members=stats.members, pairs=stats.pairs, build_seconds=round(bound.build_seconds, 1),
            solve_seconds=round(bound.solve_seconds, 1), start_value=bound.start_value, abstract_actions=stats.abstract_actions,
            abstract_edges=stats.abstract_edges, universe_growth=stats.universe_growth,
        )
        say(f"the build ends: {stats}")
        raise Stop

    _envelope_plan.pattern_lower_bound = hooked
    _packed.PROGRESS = say
    say(f"{name}: start")
    try:
        plan_of_job(arguments.route, arguments.variant, "envelope", data)
    except Stop:
        pass
    sampler.stopped.set()
    report(True)
    return 0


# ---- the jobs ----------------------------------------------------------------------------------------------------------


def job_command(arguments: argparse.Namespace) -> int:
    from crafting_system.cli import _packed
    from crafting_system.cli._envelope import Net
    from crafting_system.data import load_game_data

    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    name = f"{arguments.route}-{arguments.variant}-{arguments.solver}"
    began = time.perf_counter()

    def say(line: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f} s, {resident_mb()} MB] {line}", flush=True)

    if hasattr(signal, "SIGUSR1"):
        faulthandler.register(signal.SIGUSR1, file=sys.stdout, all_threads=True)
    _packed.PROGRESS = say
    data = load_game_data()
    net = Net(seconds=arguments.net_seconds, memory_mb=arguments.memory_mb) if arguments.solver == "envelope" else None
    say(f"{name}: start")
    record: dict = {"route": arguments.route, "variant": arguments.variant, "solver": arguments.solver, "finished": False, "error": None}
    try:
        plan = plan_of_job(arguments.route, arguments.variant, arguments.solver, data, net)
    except Exception as error:  # a refusal is an answer
        text = f"{type(error).__name__}: {error}"
        text += " | " + " < ".join(f"{frame.name}:{frame.lineno}" for frame in reversed(traceback.extract_tb(error.__traceback__)[-4:]))
        record.update(error=text[:900])
    else:
        info = plan.packed.info.get("envelope") if plan.packed is not None else None
        record.update(
            finished=True, offers=len(plan.offers), mean=plan.mean_remaining, solve_seconds=round(plan.solve_seconds, 1), path="envelope" if info else "walk",
        )
        if info is not None:
            record.update(
                exact=info.exact, envelope_stop=info.stopped, lower=info.lower, upper=info.upper, rounds=info.rounds, touched=info.touched,
                expanded=info.expanded, realized=info.realized, candidates=info.candidates, bound_keys=info.bound_keys,
                bound_seconds=round(info.bound_seconds, 1),
            )
    record.update(seconds=round(time.perf_counter() - began, 1), peak_mb=peak_mb())
    (out / f"job-{name}.json").write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
    say(f"{name}: written ({'finished' if record['finished'] else 'refused: ' + str(record['error'])[:300]})")
    return 0


def read_status(pid: int) -> tuple[int | None, int | None]:
    try:
        with open(Path(os.sep, "proc", str(pid), "status"), encoding="utf-8") as handle:
            fields = dict(line.split(":", 1) for line in handle if ":" in line)
        return int(fields["VmRSS"].split()[0]) // 1024, int(fields["VmHWM"].split()[0]) // 1024
    except (OSError, KeyError, ValueError):
        return None, None


def run_job(route: str, variant: str, solver: str, out: Path, *, cap_minutes: float, net_share: float, memory_net_mb: int) -> dict:
    """One job in a child process with a wall-clock cap and a memory cap; a child that has to be stopped leaves where it was."""
    name = f"{route}-{variant}-{solver}"
    log = out / f"log-{name}.txt"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"job-{name}.json").unlink(missing_ok=True)
    command = [
        sys.executable, "-u", str(Path(__file__).resolve()), "one", "--route", route, "--variant", variant, "--solver", solver, "--out", str(out),
        "--net-seconds", str(cap_minutes * 60 * net_share), "--memory-mb", str(memory_net_mb),
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
            if time.monotonic() - began > cap_minutes * 60:
                stop = f"the wall-clock cap of {cap_minutes:g} minutes"
            elif resident is not None and resident > MEMORY_CAP_MB:
                stop = f"the memory cap of {MEMORY_CAP_MB:,} MB (resident {resident:,} MB)"
            if stop is not None:
                if hasattr(signal, "SIGUSR1"):
                    child.send_signal(signal.SIGUSR1)
                    time.sleep(1)
                child.terminate()
                try:
                    child.wait(timeout=GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                break
    found = out / f"job-{name}.json"
    if found.exists() and stop is None:
        record = json.loads(found.read_text(encoding="utf-8"))
        record["peak_mb"] = max(record.get("peak_mb") or 0, peak) or None
    else:
        lines = [line[:300] for line in log.read_text(encoding="utf-8", errors="replace").splitlines() if line.startswith("[")]
        record = {
            "route": route, "variant": variant, "solver": solver, "finished": False, "killed": True,
            "stop": stop or f"the job ended with exit code {child.returncode} and no record", "seconds": round(time.monotonic() - began, 1),
            "peak_mb": peak or None, "last_lines": lines[-3:],
        }  # fmt: skip
    found.write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
    return record


def jobs_command(arguments: argparse.Namespace) -> int:
    out = Path(arguments.out)
    for spec in arguments.jobs.split(","):
        route, variant, *rest = spec.strip().split("-")
        solver = rest[0] if rest else "envelope"
        record = run_job(route, variant, solver, out, cap_minutes=arguments.cap_minutes, net_share=arguments.net_share, memory_net_mb=arguments.memory_mb)
        print(json.dumps({key: record.get(key) for key in ("route", "variant", "solver", "finished", "killed", "stop", "exact", "envelope_stop", "mean", "lower", "upper", "seconds", "peak_mb", "bound_keys", "bound_seconds", "error")}, default=str), flush=True)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    profile = sub.add_parser("profile")
    profile.add_argument("--route", required=True, choices=ROUTES)
    profile.add_argument("--variant", default="kept", choices=("kept", "all"))
    profile.add_argument("--cap-minutes", type=float, default=30)
    profile.add_argument("--out", default="out")
    profile.set_defaults(run=profile_command)
    jobs = sub.add_parser("jobs")
    jobs.add_argument("--jobs", required=True, help="ROUTE-VARIANT[-SOLVER],... with VARIANT kept|all and SOLVER envelope (default) or auto")
    jobs.add_argument("--cap-minutes", type=float, default=50)
    jobs.add_argument("--net-share", type=float, default=0.5, help="the net's time is this share of the cap (the solve of the graph it ended with comes after)")
    jobs.add_argument("--memory-mb", type=int, default=10_000)
    jobs.add_argument("--out", default="out")
    jobs.set_defaults(run=jobs_command)
    one = sub.add_parser("one")
    one.add_argument("--route", required=True, choices=ROUTES)
    one.add_argument("--variant", default="kept", choices=("kept", "all"))
    one.add_argument("--solver", default="envelope", choices=("envelope", "auto"))
    one.add_argument("--net-seconds", type=float, default=None)
    one.add_argument("--memory-mb", type=float, default=None)
    one.add_argument("--out", default="out")
    one.set_defaults(run=job_command)
    arguments = parser.parse_args(argv)
    return arguments.run(arguments)


if __name__ == "__main__":
    sys.exit(main())
