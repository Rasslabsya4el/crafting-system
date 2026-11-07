"""Where the bound's build spends its time (ticket #626): a sampler of the stack and a timer around the stages of the build, for one route and variant.

    python .github/scripts/bound_build.py profile --route R08 --variant kept|all [--cap-minutes N] [--out DIR]

Builds the bound alone (`pattern_lower_bound`, the call `envelope_result` makes first) in the process it runs in, with a sampler of the main thread's stack
(the time inside each function of the product, by the call stacks, every 0.2 s) and a timer around the named stages of the build. It reads the same inputs
as `make_plan` (`actions_key.plan_of_job`) and ends at the end of the build, or at the cap with the tables printed. Writes `profile-ROUTE-VARIANT.txt` and
`.json` into `--out`. The planning of whole routes under the net is `actions_key.py` (`jobs`).

Never run on a PC for a real route (docs/ci.md): run by `.github/scripts/heavy_dispatch.py`.
"""

import argparse
import faulthandler
import json
import os
import sys
import threading
import time
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import actions_key  # noqa: E402  (the inputs of a route and its variants)

ROUTES = actions_key.ROUTES


def resident_mb() -> int | None:
    from crafting_system.cli._envelope import resident_mb as read

    found = read()
    return None if found is None else int(found)


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
        record.update(peak_mb=actions_key.peak_mb(), seconds=round(time.perf_counter() - began, 1), stages={label: [calls, round(seconds, 2)] for label, (calls, seconds) in timers.items()})
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
        actions_key.plan_of_job(arguments.route, arguments.variant, "envelope", data)
    except Stop:
        pass
    sampler.stopped.set()
    report(True)
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
    arguments = parser.parse_args(argv)
    return arguments.run(arguments)


if __name__ == "__main__":
    sys.exit(main())
