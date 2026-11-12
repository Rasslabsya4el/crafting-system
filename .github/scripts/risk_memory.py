"""The memory and time of a route's risk step (tickets #738, #744); run by the `Run a command` workflow, never on a PC.

    python .github/scripts/risk_memory.py product --route r14|r13|r04 --out DIR [--dump]
    python .github/scripts/risk_memory.py steps CHAIN.npz --parts 4 8 16 32 --out DIR

`product` makes the plan the way the planner does (`make_plan(solver="auto")`, at the price file `ROUTE_PRICES`, default the snapshot of
2026-11-10) without its risk, then adds the risk (`add_risk`, the product path: the attempt runs side by side in forked workers), and samples
every second the memory of the whole process tree (the sum of each process's PSS, so pages a worker shares with the parent count once) and
the runner's used memory (`MemTotal - MemAvailable`). It writes `<route>.memory.json`: the seconds and the peaks of the plan and of the risk,
the risk's numbers and grid step. With `--dump` it also writes the lumped chain of the plan (`<route>.chain.npz`, as `chain_dump.py`).

`steps` reads such a chain and runs, for each `--parts` (the restart's cost over that many parts, as `risk._evaluate.REGEN_PARTS`), the four
attempt runs of that step one after another, each in a forked child, and writes `steps.json`: per run the bins, the seconds, the child's peak
private memory and what the budget DP held (`risk._budget.held_peak` when the engine reports it).
"""

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("ROUTE_PRICES", "tests/fixtures/prices/routes-allflame-2026-11-10.json")


def _proc(*parts: str) -> Path:
    return Path(os.sep, "proc", *parts)


def _children(pid: int) -> list[int]:
    found = []
    for entry in _proc().iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
        except OSError:
            continue
        if int(fields[1]) == pid:
            found.append(int(entry.name))
    return found


def _kb(path: Path, *names: str) -> int:
    total = 0
    try:
        for line in path.read_text().splitlines():
            key = line.split(":", 1)[0]
            if key in names:
                total += int(line.split()[1])
    except OSError:
        return 0
    return total


def tree_pss_mb(pid: int) -> int:
    """The PSS of `pid` and all its descendants, in MB: shared pages counted once in all."""
    seen, todo, total = set(), [pid], 0
    while todo:
        p = todo.pop()
        if p in seen:
            continue
        seen.add(p)
        total += _kb(_proc(str(p), "smaps_rollup"), "Pss")
        todo.extend(_children(p))
    return total // 1024


def machine_used_mb() -> int:
    info = {}
    for line in _proc("meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        info[key] = int(value.split()[0])
    return (info["MemTotal"] - info["MemAvailable"]) // 1024


class Sampler:
    """Peaks of the tree's PSS and of the machine's used memory, sampled every `period` seconds, per named phase."""

    def __init__(self, period: float = 1.0) -> None:
        self.period, self.phase, self.peaks, self.workers = period, "start", {}, 0
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self) -> None:
        me, ticks = os.getpid(), 0
        while True:
            pss, used = tree_pss_mb(me), machine_used_mb()
            peak = self.peaks.setdefault(self.phase, {"tree_pss_mb": 0, "machine_used_mb": 0, "processes": 0})
            peak["tree_pss_mb"] = max(peak["tree_pss_mb"], pss)
            peak["machine_used_mb"] = max(peak["machine_used_mb"], used)
            peak["processes"] = max(peak["processes"], 1 + len(_children(me)))
            ticks += 1
            if ticks % 30 == 0:
                print(f"  memory ({self.phase}): tree {pss} MB, machine used {used} MB", flush=True)
            time.sleep(self.period)


def product(arguments) -> None:
    from packed_routes import inputs, risk_row

    from crafting_system.cli import _packed, make_plan
    from crafting_system.cli._plan import add_risk

    sampler = Sampler()
    began = time.perf_counter()
    _packed.PROGRESS = lambda line: print(f"[{time.perf_counter() - began:7.1f}s] {line}", flush=True)
    data, target, prices, start_price = inputs(arguments.route)
    sampler.phase = "plan"
    t = time.perf_counter()
    plan = make_plan(data, target, prices, start_price=start_price, budget=None, with_risk=False)
    plan_seconds = time.perf_counter() - t
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    if arguments.dump:
        from chain_dump import dump

        dump(plan, out / f"{arguments.route}.chain.npz")
    sampler.phase = "risk"
    t = time.perf_counter()
    risky = add_risk(plan)
    risk_seconds = time.perf_counter() - t
    time.sleep(2 * sampler.period)
    result = {
        "route": arguments.route, "prices": os.environ["ROUTE_PRICES"], "mean": plan.mean_remaining, "plan_seconds": round(plan_seconds, 1),
        "risk_seconds": round(risk_seconds, 1), "peaks": sampler.peaks, "risk": risk_row(risky),
        "step": None if risky.risk is None else risky.risk.grid.step, "limits": [f"{limit.what}: {limit.why}" for limit in risky.limits if limit.kind == "risk"],
    }
    text = json.dumps(result, indent=1, default=str)
    print(text, flush=True)
    (out / f"{arguments.route}.memory.json").write_text(text + "\n", encoding="utf-8")


def _private_peak(stop: threading.Event, holder: dict) -> None:
    while not stop.is_set():
        holder["mb"] = max(holder.get("mb", 0), _kb(_proc("self", "smaps_rollup"), "Private_Clean", "Private_Dirty") // 1024)
        time.sleep(0.2)


def steps(arguments) -> None:
    from risk_probe import load

    from crafting_system.risk import _budget, _evaluate, _regen
    from crafting_system.risk._chain import build_chain

    policy, start, goals, _ = load(Path(arguments.chain))
    chain = build_chain(policy, start, lambda s: s in goals, True)
    into = _regen.regeneration_edges(chain)
    counts: dict[float, int] = {}
    for i in into:
        counts[chain.action[i].cost] = counts.get(chain.action[i].cost, 0) + 1
    base = max(counts, key=lambda cost: counts[cost])
    rows = []
    for parts in arguments.parts:
        step = base / parts
        low, high = _evaluate._bin_costs(chain, step)
        for name, bins in (("low", low), ("high", high)):
            for success in (True, False):
                read, write = os.pipe()
                child = os.fork()
                if child == 0:
                    os.close(read)
                    stop, holder = threading.Event(), {}
                    threading.Thread(target=_private_peak, args=(stop, holder), daemon=True).start()
                    t = time.perf_counter()
                    found = _regen.attempt_pmf(chain, bins, success=success, max_bins=1_000_000)
                    row = {
                        "parts": parts, "step": step, "chain": name, "success": success, "bins": None if found is None else len(found[0]),
                        "seconds": round(time.perf_counter() - t, 1), "held_peak": getattr(_budget, "held_peak", lambda: None)(),
                    }
                    time.sleep(0.5)
                    stop.set()
                    row["private_peak_mb"] = holder.get("mb", 0)
                    os.write(write, json.dumps(row).encode())
                    os._exit(0)
                os.close(write)
                chunks = []
                while chunk := os.read(read, 65536):
                    chunks.append(chunk)
                os.waitpid(child, 0)
                row = json.loads(b"".join(chunks) or b"{}")
                print(json.dumps(row), flush=True)
                rows.append(row)
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "steps.json").write_text(json.dumps({"base": base, "rows": rows}, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    one = sub.add_parser("product")
    one.add_argument("--route", required=True)
    one.add_argument("--out", required=True)
    one.add_argument("--dump", action="store_true")
    two = sub.add_parser("steps")
    two.add_argument("chain")
    two.add_argument("--parts", type=int, nargs="+", default=[32])
    two.add_argument("--out", required=True)
    arguments = parser.parse_args()
    product(arguments) if arguments.mode == "product" else steps(arguments)


if __name__ == "__main__":
    main()
