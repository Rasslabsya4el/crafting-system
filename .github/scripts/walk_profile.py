"""Where the packed walk of a route spends its time and memory (ticket #375); run by the `Run a command` workflow, never on a PC.

    python .github/scripts/walk_profile.py --route r14 --mode census|tracemalloc|cprofile [--stop-after N] --out $OUT_DIR

The walk is reached through `make_plan(solver="packed", with_risk=False)` and stopped when it ends (or after `--stop-after` states are
closed), so nothing after it runs.

* `census`: the whole walk, then each structure it holds is freed in turn (`malloc_trim` after each) and the resident memory read,
  so the drop is what that structure held: the kernel-key dict, each cache of the abstraction, the state index, the states, the arrays.
* `tracemalloc`: the live memory at the stop, by the line that allocated it (top 30, 4 frames).
* `cprofile`: the 50 functions with the most own and the most inclusive time up to the stop.
"""

import argparse
import cProfile
import ctypes
import gc
import io
import json
import os
import pstats
import sys
import threading
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from packed_routes import inputs, watch_memory  # noqa: E402

from crafting_system.cli import _packed, make_plan  # noqa: E402
from crafting_system.solver import _packed as solver_packed  # noqa: E402


class Stop(Exception):
    pass


HELD: dict = {}


def rss_mb() -> float:
    with open("/proc/self/status", encoding="utf-8") as handle:
        return int(next(line for line in handle if line.startswith("VmRSS")).split()[1]) / 1024


def trim() -> None:
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except OSError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", required=True)
    parser.add_argument("--mode", required=True, choices=("census", "tracemalloc", "cprofile"))
    parser.add_argument("--stop-after", type=int, default=0)
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=watch_memory, daemon=True).start()
    began = time.perf_counter()

    def say(line: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f}s, {rss_mb():.0f} MB] {line}", flush=True)

    _packed.PROGRESS = say
    data, target, prices, start_price = inputs(arguments.route)
    say("target loaded")
    original_close = solver_packed.PackedBuilder.close_state
    original_build = solver_packed.PackedBuilder.build
    counts = {"kernel_key": 0, "kernel": 0}
    for name in counts:
        method = getattr(_packed.Abstraction, name)

        def counted(self, *args, _method=method, _name=name, **kwargs):
            counts[_name] += 1
            return _method(self, *args, **kwargs)

        setattr(_packed.Abstraction, name, counted)

    def grab(frame) -> None:
        local = frame.f_locals
        HELD.update(states=local["states"], index=local["index"], shared=local["shared"], abstraction=local["abstraction"], builder=local["builder"])

    def close_state(self, is_goal):
        original_close(self, is_goal)
        if arguments.stop_after and self.states_closed >= arguments.stop_after:
            grab(sys._getframe(1))
            raise Stop

    def build(self):
        grab(sys._getframe(1))
        raise Stop

    solver_packed.PackedBuilder.close_state = close_state
    solver_packed.PackedBuilder.build = build
    profiler = cProfile.Profile() if arguments.mode == "cprofile" else None
    if arguments.mode == "tracemalloc":
        tracemalloc.start(4)
    walk_began = time.perf_counter()
    try:
        if profiler is not None:
            profiler.enable()
        make_plan(data, target, prices, start_price=start_price, budget=None, solver="packed", with_risk=False)
    except Stop:
        pass
    finally:
        if profiler is not None:
            profiler.disable()
    walk_seconds = time.perf_counter() - walk_began
    builder = HELD["builder"]
    result = {
        "route": arguments.route, "mode": arguments.mode, "walk_seconds": round(walk_seconds, 1), "states_found": len(HELD["states"]),
        "states_closed": builder.states_closed, "kernels": builder.kernels, "transitions": builder.edges, "shared_keys": len(HELD["shared"]),
        "calls": counts, "rss_mb_at_stop": round(rss_mb()),
    }
    say(f"stopped: {result}")
    if arguments.mode == "tracemalloc":
        snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()
        lines = []
        for stat in snapshot.statistics("traceback")[:30]:
            lines.append(f"{stat.size / 2**20:9.1f} MB {stat.count:>10,} blocks")
            lines.extend(f"      {frame.filename.split('src/')[-1]}:{frame.lineno}" for frame in stat.traceback)
        by_line = [f"{stat.size / 2**20:9.1f} MB {stat.count:>10,} {stat.traceback[0].filename.split('src/')[-1]}:{stat.traceback[0].lineno}" for stat in snapshot.statistics("lineno")[:40]]
        text = "\n".join(["by line:", *by_line, "", "by traceback:", *lines])
        print(text, flush=True)
        (out / f"{arguments.route}-tracemalloc.txt").write_text(text + "\n", encoding="utf-8")
    elif arguments.mode == "cprofile":
        for order in ("tottime", "cumulative"):
            stream = io.StringIO()
            pstats.Stats(profiler, stream=stream).sort_stats(order).print_stats(50)
            text = stream.getvalue()
            print(text, flush=True)
            (out / f"{arguments.route}-cprofile-{order}.txt").write_text(text, encoding="utf-8")
    else:
        trim()
        drops = {"start": round(rss_mb())}
        abstraction = HELD["abstraction"]
        sizes = {name: len(value) for name, value in vars(abstraction).items() if isinstance(value, (dict, set, list))}
        result["abstraction_sizes"] = sizes
        steps = [("shared kernel keys", lambda: HELD.pop("shared").clear())]
        for name in sorted(sizes, key=lambda n: -sizes[n]):
            if sizes[name]:
                steps.append((f"abstraction.{name}", lambda n=name: getattr(abstraction, n).clear()))
        steps += [
            ("state index", lambda: HELD.pop("index").clear()),
            ("states", lambda: HELD.pop("states").clear()),
            ("builder arrays", lambda: HELD.pop("builder")),
        ]
        for label, step in steps:
            before = rss_mb()
            step()
            trim()
            drops[label] = round(before - rss_mb())
            say(f"freed {label}: {drops[label]} MB")
        drops["left"] = round(rss_mb())
        result["freed_mb"] = drops
    text = json.dumps(result, indent=1)
    print(text, flush=True)
    (out / f"{arguments.route}-{arguments.mode}.json").write_text(text + "\n", encoding="utf-8")
    os._exit(0)


if __name__ == "__main__":
    main()
