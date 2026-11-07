"""What each benchmark route buys, against the depth of the price (#616): the plan's expected uses of every priced resource, its marks.

    python .github/scripts/price_uses_report.py ROUTES OUT_DIR [--prices FILE]

ROUTES is a comma list of benchmark ids (R12,R10,...), or `split`: the routes are dealt out to the dispatcher's runners (RUNNER_INDEX of
RUNNER_COUNT, five runners: one for each group in `GROUPS`). For each route it makes the plan the benchmark makes (`make_plan`, or
`plan_with_starts` for a route that starts from a vendor recipe), reads `price_uses` of the policy the report shows, and writes
`OUT_DIR/price-uses-<ROUTE>.json`: the mean and, for each priced resource, its price, source, depth in units, the units the plan expects
to buy and the marks the rule gives it. A line is printed per resource. Never run for R04 or R14 on a PC (docs/ci.md): use the dispatcher.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
PRICES = "tests/fixtures/prices/routes-allflame-2026-11-07.json"
GROUPS = ("R12,R10,R11", "R05,R13", "R08,R09", "R04", "R14")  # what one runner takes; R04 and R14 hold hundreds of thousands of states each


def main(argv: list[str]) -> int:
    from crafting_system.cli import _benchmark, make_plan, plan_with_starts
    from crafting_system.cli._decide import Rates
    from crafting_system.cli._price_marks import price_uses
    from crafting_system.config import find_project_root, load_config
    from crafting_system.data import load_game_data
    from crafting_system.prices import load_price_file
    from crafting_system.targets import load_target

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("routes")
    parser.add_argument("out")
    parser.add_argument("--prices", default=PRICES)
    parser.add_argument("--budget", type=float, default=None, help="seconds the plan may take (the decision of `make_plan`: exact when the forecast fits, else approximate), as the real-route tests plan R08 and R09")
    args = parser.parse_args(argv)
    if args.routes == "split":
        index, count = int(os.environ.get("RUNNER_INDEX", "1")), int(os.environ.get("RUNNER_COUNT", "1"))
        args.routes = ",".join(group for position, group in enumerate(GROUPS) if position % count == index - 1)
    root = find_project_root()
    config = load_config()
    data = load_game_data(cache_dir=config.cache_dir)
    prices = load_price_file(root / args.prices)
    known = {bench.id: bench for bench in _benchmark.BENCHMARKS}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    code = 0
    for name in [each for each in args.routes.split(",") if each]:
        bench = known.get(name)
        if bench is None:
            print(f"no benchmark route {name}; the routes are {', '.join(known)}", file=sys.stderr)
            return 2
        began = time.perf_counter()
        target = load_target(root / bench.target, data)
        extra = {} if args.budget is None else {"budget": args.budget, "rates": Rates(4e-5, 7e-6)}  # the rates are injected, so the decision does not depend on the machine
        plan = make_plan(data, target, prices, **extra) if bench.start is None else plan_with_starts(data, target, prices, **extra)
        print(f"{name}: planned in {time.perf_counter() - began:,.0f} s; {len(plan.view_policy):,} states in the policy, {len(plan.offers):,} offers", flush=True)
        uses = price_uses(plan, plan.view_policy, all_uses=True)
        print(f"{name}: the uses solved in {time.perf_counter() - began:,.0f} s", flush=True)
        document = {
            "route": name,
            "prices": args.prices,
            "mean_remaining": plan.mean_remaining,
            "start_price": plan.start_price.chaos,
            "start_name": plan.start_price.name,
            "seconds": time.perf_counter() - began,
            "resources": [
                {
                    "name": use.name,
                    "chaos": use.chaos,
                    "source": use.source,
                    "depth": use.depth,
                    "uses": use.uses,
                    "marks": [mark.reason for mark in use.marks],
                }
                for use in uses
            ],
        }
        (out / f"price-uses-{name}.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        print(f"{name}: mean to pay {plan.mean_remaining:,.2f} Chaos after a start of {plan.start_price.chaos:,.2f}; {len(uses)} priced resources", flush=True)
        for use in uses:
            depth = "no depth" if use.depth is None else f"{use.depth:,.1f} units"
            bought = "uses not solved" if use.uses is None else f"{use.uses:,.1f} bought"
            print(f"  {use.name}: {use.chaos:g} c, {depth}, {bought}; {'; '.join(mark.reason for mark in use.marks) or 'plain fact'}", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
