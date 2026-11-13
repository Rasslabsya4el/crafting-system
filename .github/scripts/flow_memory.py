"""Where the memory of a plan's flow goes (ticket #595); run by the `Run a command` workflow, never on a PC.

    python .github/scripts/flow_memory.py --route r04|r14 [--solver packed|envelope|auto] [--out DIR]

Plans the route (`make_plan`, no risk) and, when the plan is finished, measures what `display_limits` does with it: building the item chain
(`chain_of_plan`), the visits (`_route_flow._solved`, on the kernel classes), the page's lumping (`_page_blocks`) and the chances of entering
the steps (`_entries`, on the lumped chain; ticket #689). A sampler thread reads the resident
memory every 50 ms and keeps, for each stage, the highest it saw above what the stage began with, and the stack of the main thread at that moment.
Writes `<route>.<solver>.flow-memory.json`: the peak of the plan before the flow (the search or the walk), the memory resident when the flow began,
the peak of each stage, the size of the chain, and the stack at each stage's peak.
"""

import argparse
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import packed_routes as P  # noqa: E402

from crafting_system.cli import _plan, _route_flow, make_plan  # noqa: E402


def status_mb(field: str) -> int:
    with open(Path(os.sep, "proc", "self", "status"), encoding="utf-8") as handle:
        return int(next(line for line in handle if line.startswith(field)).split()[1]) // 1024


class Sampler:
    """The highest resident memory seen since `begin()`, and where the main thread was."""

    def __init__(self) -> None:
        self.main_id = threading.main_thread().ident
        self.peak = 0
        self.stack = ""
        self.lock = threading.Lock()
        threading.Thread(target=self.run, daemon=True).start()

    def begin(self) -> int:
        with self.lock:
            self.peak = status_mb("VmRSS")
            self.stack = ""
            return self.peak

    def end(self) -> tuple[int, str]:
        with self.lock:
            return max(self.peak, status_mb("VmRSS")), self.stack

    def run(self) -> None:
        while True:
            time.sleep(0.05)
            rss = status_mb("VmRSS")
            with self.lock:
                if rss > self.peak:
                    self.peak = rss
                    frame = sys._current_frames().get(self.main_id)
                    if frame is not None:
                        lines = [f"{f.name} ({Path(f.filename).name}:{f.lineno}) {f.line or ''}".strip() for f in traceback.extract_stack(frame)[-6:]]
                        self.stack = " <- ".join(reversed(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", required=True)
    parser.add_argument("--solver", default="packed", choices=("packed", "envelope", "auto"))
    parser.add_argument("--out")
    arguments = parser.parse_args()
    began = time.perf_counter()
    sampler = Sampler()
    result: dict = {"route": arguments.route, "solver": arguments.solver, "stages": {}}

    def say(line: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f}s, {status_mb('VmHWM')} MB peak] {line}", flush=True)

    def stage(name: str, work):
        before = sampler.begin()
        t = time.perf_counter()
        value = work()
        top, stack = sampler.end()
        result["stages"][name] = {"start_mb": before, "peak_mb": top, "rise_mb": top - before, "seconds": round(time.perf_counter() - t, 1), "stack_at_peak": stack}
        say(f"{name}: {before} -> peak {top} MB (+{top - before}), {time.perf_counter() - t:.1f} s; at the peak: {stack}")
        return value

    real_chain, real_limits = _plan.chain_of_plan, _plan.flow_limits

    def chain_of_plan(plan):
        result["peak_before_flow_mb"] = status_mb("VmHWM")
        result["resident_before_flow_mb"] = status_mb("VmRSS")
        say(f"plan finished, flow begins: resident {result['resident_before_flow_mb']} MB, peak so far {result['peak_before_flow_mb']} MB")
        return stage("chain_of_plan", lambda: real_chain(plan))

    def flow_limits(chain):
        sizes = chain.kernels.kernel_sizes()
        acting = chain.kernel >= 0
        copied = int(sizes[chain.kernel[acting]].sum())  # the edges a copy per state would hold (#689: not made)
        result["chain"] = {"states": chain.m, "kernels": len(sizes), "kernel_edges": int(sizes.sum()), "edges_if_copied_per_state": copied}
        say(f"chain: {chain.m:,} states, {len(sizes):,} kernels of {int(sizes.sum()):,} edges ({copied:,} edges if copied per state)")
        stage("solved (kernel classes, visits of every state)", lambda: _route_flow._solved(chain))
        blocks = stage("page lumping (the steps' labels)", lambda: _route_flow._page_blocks(chain))
        result["chain"]["page_blocks"] = int(blocks.max()) + 1 if len(blocks) else 0
        say(f"page lumping: {result['chain']['page_blocks']:,} blocks")
        stage("entries (lumping again, then the solves on the blocks)", lambda: _route_flow._entries(chain))
        return stage("flow_limits (rest)", lambda: real_limits(chain))

    _plan.chain_of_plan, _plan.flow_limits = chain_of_plan, flow_limits
    data, target, prices, start_price = P.inputs(arguments.route)
    plan = make_plan(data, target, prices, start_price=start_price, budget=None, solver=arguments.solver, with_risk=False)
    result.update(
        seconds=round(time.perf_counter() - began, 1), mean=plan.mean_remaining, policy_states=len(plan.policy), peak_mb=status_mb("VmHWM"),
        limits=[limit.what for limit in plan.limits],
    )
    result["peak_of_plan_mb"] = result["peak_mb"]
    if plan.lumped:  # the steps of the page (`flow_of`) on the same chain: a different peak from the plan's, measured here so it is not guessed
        from crafting_system.cli._route_chain import chain_of_packed_policy

        chain = chain_of_packed_policy(plan.policy)
        stage("flow_of (the page's steps)", lambda: _route_flow.flow_of(chain))
        result["peak_mb"] = status_mb("VmHWM")
    info = getattr(plan.packed, "info", {}) or {}
    if "envelope" in info:
        result["search_peak_mb"] = info["envelope"].peak_mb
    say(f"done: peak {result['peak_mb']} MB; before the flow {result.get('peak_before_flow_mb')} MB")
    text = json.dumps(result, indent=1, default=str)
    print(text, flush=True)
    if arguments.out:
        out = Path(arguments.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{arguments.route}.{arguments.solver}.flow-memory.json").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
