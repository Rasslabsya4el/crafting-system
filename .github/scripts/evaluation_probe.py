"""The time and the memory of the policy evaluations of a route's plan, one JSON file (ticket #621); run by the `Run a command` workflow.

    python .github/scripts/evaluation_probe.py --route r04|r14 --out DIR [--force-exact]

Plans the route as `packed_routes.py plan` does and wraps `solver/_packed_solve.evaluate_policy`: for each call it notes the seconds and the
resident memory before, the peak while it ran (a thread reads the resident memory of the process every 0.2 seconds) and the `info` counters it left (iterations,
residual, backward error, the exact solve by the cycles of the chain when it was made). The file `DIR/<route>.evaluation.json` holds the calls and
their totals, so that the same route can be measured on two refs and the two files compared (the memory of the whole plan is in `peak_mb`).

`--force-exact` makes the iteration give up at once (it returns its start as an iterate that did not converge), so that every evaluation takes the exact
solve by the cycles of the policy's chain: what that fallback costs in seconds and memory on the route's own policy, and that its mean is the iteration's.
When the cycles do not fit in the memory of the run the plan is refused and the file holds the refusal, which names what they would have cost.

Never run on a PC for R04 or R14. Run by `.github/scripts/heavy_dispatch.py`.
"""

import argparse
import json
import os
import threading
import time
from pathlib import Path

from crafting_system.cli import make_plan
from crafting_system.solver import _packed_solve

import packed_routes  # noqa: E402  (this folder is on the path when the script is run)


def resident_mb() -> int:
    try:
        with open(Path(os.sep, "proc", "self", "status"), encoding="utf-8") as handle:
            return int(next(line for line in handle if line.startswith("VmRSS")).split()[1]) // 1024
    except (OSError, StopIteration):
        return 0


class Sampler:
    """The peak resident memory between `start()` and `stop()`."""

    def __init__(self) -> None:
        self.peak = 0
        self.running = False

    def start(self) -> None:
        self.peak = resident_mb()
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        while self.running:
            self.peak = max(self.peak, resident_mb())
            time.sleep(0.2)

    def stop(self) -> int:
        self.running = False
        return max(self.peak, resident_mb())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", required=True, choices=("r04", "r14"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--force-exact", action="store_true")
    arguments = parser.parse_args()
    calls: list[dict] = []
    real = _packed_solve.evaluate_policy

    def probe(work, leave, policy, start, dense_limit, tol, info):
        before = {key: value for key, value in info.items() if isinstance(value, int | float)}
        sampler = Sampler()
        resident = resident_mb()
        began = time.perf_counter()
        sampler.start()
        try:
            return real(work, leave, policy, start, dense_limit, tol, info)
        finally:
            seconds = time.perf_counter() - began
            peak = sampler.stop()
            calls.append(
                {
                    "states": int((policy >= 0).sum()), "seconds": round(seconds, 2), "resident_mb_before": resident, "peak_mb": peak,
                    "info": {key: value for key, value in info.items() if key.startswith("linear") or key in ("matvecs", "seconds_cycles")},
                    "info_before": {key: value for key, value in before.items() if key.startswith("linear") or key in ("matvecs", "seconds_cycles")},
                }
            )
            print(f"evaluation {len(calls)}: {calls[-1]['states']:,} states, {seconds:.1f} s, peak {peak} MB (resident {resident} MB before)", flush=True)

    _packed_solve.evaluate_policy = probe
    if arguments.force_exact:
        _packed_solve.bicgstab_checked = lambda matvec, b, x0, tol: (x0, 1.0, 0)
    began = time.perf_counter()
    data, target, prices, start_price = packed_routes.inputs(arguments.route)
    result = {"route": arguments.route, "force_exact": arguments.force_exact}
    try:
        plan = make_plan(data, target, prices, start_price=start_price, budget=None, solver="packed")  # the walk's policy evaluation, as before #535 made `auto` the envelope search
    except Exception as refused:  # the refusal of an evaluation says what the exact solve would have cost
        result.update(refused=f"{type(refused).__name__}: {refused}")
    else:
        result.update(
            mean_remaining=plan.mean_remaining, error_bound=plan.solution.error_bound, policy_states=len(plan.policy),
            plan_info={key: value for key, value in (plan.packed.info if plan.packed else {}).items() if isinstance(value, int | float | str)},
        )
    result.update(
        seconds=round(time.perf_counter() - began, 1), peak_mb=packed_routes.peak_mb(), evaluations=calls,
        evaluation_seconds=round(sum(call["seconds"] for call in calls), 1), evaluation_peak_mb=max((call["peak_mb"] for call in calls), default=0),
    )
    text = json.dumps(result, indent=1)
    print(text, flush=True)
    Path(arguments.out).mkdir(parents=True, exist_ok=True)
    suffix = ".exact" if arguments.force_exact else ""
    (Path(arguments.out) / f"{arguments.route}{suffix}.evaluation.json").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
