"""Plan one route or generated case under the planner's default budget and write what a pair compares (ticket #948). No `src/` change.

    python research/948/pair_plan.py (--route r04 | --case essences/medium) --tag .main-1 --out DIR
    CRAFTING_SOURCE=DIR python research/948/pair_plan.py ...   # plan with the copy of the package in DIR (main's, for the pair)

The plan is `make_plan(..., budget=Budget(), with_risk=False)`: the default budget of every caller (aim 60 s, the 10-minute net, the stop at a proved
1%), so a pair compares the path the planner takes today, the first plan, the rounds and the stop included. It writes `<name>.plain<tag>.json` with the
wall seconds, the mean, how the search ended and its whole-number counters (research/948/same.py reads them). A heavy run, never on a PC.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "research" / "881"))
if os.environ.get("CRAFTING_SOURCE"):
    sys.path.insert(0, os.environ["CRAFTING_SOURCE"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route")
    parser.add_argument("--case")
    parser.add_argument("--tag", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    import profile_plan

    from crafting_system.budget import Budget
    from crafting_system.cli import make_plan
    from crafting_system.planner import _envelope

    data, target, prices, start_price, solver = profile_plan.inputs(args)
    name = f"{(args.case or args.route).replace('/', '__')}.plain{args.tag}"
    found: dict = {}
    run = _envelope.Search.run

    def kept_run(self):  # the search's own counters, read when it ends
        try:
            return run(self)
        finally:
            found["stats"] = {k: v for k, v in vars(self.stats).items() if k != "lower_history"}
            found["states_known"] = len(self.states)

    _envelope.Search.run = kept_run
    began = time.perf_counter()
    plan = make_plan(data, target, prices, start_price=start_price, budget=Budget(), solver=solver, with_risk=False)
    seconds = round(time.perf_counter() - began, 2)
    envelope = plan.packed.info.get("envelope") if plan.packed is not None else None
    out = {
        "name": name, "source": os.environ.get("CRAFTING_SOURCE"), "seconds": seconds, "mean_remaining": plan.mean_remaining, "search": found,
        "ended": None if envelope is None else {"exact": envelope.exact, "within": envelope.within, "stopped": envelope.stopped, "lower": envelope.lower},
    }  # fmt: skip
    text = json.dumps(out, indent=1, default=str)
    print(text, flush=True)
    folder = Path(args.out)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
