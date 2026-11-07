"""Where the cost of a benchmark route sits, and every divergence of the planner from the guide with the cost it carries (ticket #599).

    python .github/scripts/divergence_costs.py R04 OUT_DIR [EXTRA_ROUTE.yaml ...]

Plans the benchmark route (the packed solver, as `benchmark --heavy` does), then for the planner's policy, the guide as written, the guide
completed with a restart and each EXTRA route file (a completion read another way) prints and writes `OUT_DIR/costs.json`:

* the steps of the policy by action: the expected uses of the action in one run and the Chaos it carries (uses x price), which add up
  to the mean;
* for the completed route and each extra route: the same, and its mean, its success and its gaps;
* every divergence of the planner's main line from the completed route, one row each, with the expected visits of the state under the
  planner and under the route and the Chaos each carries (visits x the price of that side's action), and the sums per pair of actions.

The expected visits are the row of (I - Q)^-1 of `_route_flow.flow_of` (OR-20), exact, not the upper bounds `reach_of` gives on a chain
of millions of edges. Never run on a PC: the plan of R04 takes about 5 minutes and 6 GB. Run by `.github/scripts/heavy_dispatch.py`.
"""

import json
import sys
import time
from pathlib import Path

PRICES = "tests/fixtures/prices/routes-allflame-2026-10-31.json"


def main(argv: list[str]) -> int:
    from crafting_system.cli import _benchmark, _packed, evaluate_route, load_route, make_plan
    from crafting_system.cli._report import describe_state, number_states
    from crafting_system.cli._route_chain import chain_of_plan
    from crafting_system.cli._route_flow import flow_of
    from crafting_system.config import find_project_root
    from crafting_system.data import load_game_data
    from crafting_system.prices import load_price_file
    from crafting_system.targets import load_target

    began = time.perf_counter()

    def say(text: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f}s] {text}", flush=True)

    _packed.PROGRESS = say
    bench = next(b for b in _benchmark.BENCHMARKS if b.id == argv[0])
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    root = find_project_root()
    data = load_game_data()
    target = load_target(root / bench.target, data)
    plan = make_plan(data, target, load_price_file(root / PRICES))
    shift = plan.start_price.chaos
    say(f"planned: mean {plan.mean_remaining + shift:,.2f} with the start price {shift}")

    def visits_of(chain) -> tuple[dict, list[dict]]:
        flow = flow_of(chain)
        by_state: dict = {}
        table = []
        for step in flow.steps:
            if step.action is None:
                table.append({"step": step.number, "action": None, "reason": step.reason, "states": len(step.states)})
                continue
            for state, weight in zip(step.states, step.weights):
                by_state[state] = (weight, step.cost)
            uses = step.uses
            table.append(
                {
                    "step": step.number,
                    "action": step.action.label,
                    "states": len(step.states),
                    "uses": uses,
                    "price": step.cost,
                    "carried": None if uses is None else uses * step.cost,
                }
            )
        say(f"flow of a chain of {chain.m:,} states made, measured={flow.measured}")
        return by_state, table

    planner_visits, planner_table = visits_of(chain_of_plan(plan))
    document: dict = {
        "route": bench.id,
        "planner": {"mean": plan.mean_remaining + shift, "steps": planner_table},
        "routes": {},
    }
    ids = number_states(plan)
    routes = [("guide", bench.route), ("completed", bench.completed), *[(Path(p).name, p) for p in argv[2:]]]
    for name, path in routes:
        if path is None:
            continue
        route = load_route(root / path if not Path(path).is_absolute() and (root / path).exists() else Path(path), plan, data)
        result = evaluate_route(plan, route, data)
        risk = result.risk
        route_visits, route_table = visits_of(result.chain) if result.chain is not None else ({}, [])
        entry = {
            "path": str(path),
            "mean": risk.mean.value + shift,
            "success": risk.success_probability.value,
            "gaps": len(result.gaps),
            "steps": route_table,
            "divergences": len(result.divergences),
        }
        pairs: dict = {}
        rows = []
        for divergence in result.divergences:
            pv, pc = planner_visits.get(divergence.state, (0.0, 0.0))
            rv, rc = route_visits.get(divergence.state, (0.0, 0.0))
            rows.append(
                {
                    "state": ids.get(divergence.state),
                    "description": describe_state(plan, data, divergence.state),
                    "planner_action": divergence.solver_action,
                    "route_action": divergence.route_action,
                    "planner_visits": pv,
                    "route_visits": rv,
                    "planner_carried": pv * pc,
                    "route_carried": rv * rc,
                }
            )
            pair = pairs.setdefault((divergence.route_action, divergence.solver_action), [0, 0.0, 0.0, 0.0, 0.0])
            pair[0] += 1
            pair[1] += pv
            pair[2] += rv
            pair[3] += pv * pc
            pair[4] += rv * rc
        rows.sort(key=lambda r: -(r["planner_carried"] + r["route_carried"]))
        entry["divergence_rows"] = rows
        entry["divergence_pairs"] = [
            {"route_action": a, "planner_action": b, "states": v[0], "planner_visits": v[1], "route_visits": v[2], "planner_carried": v[3], "route_carried": v[4]}
            for (a, b), v in sorted(pairs.items(), key=lambda kv: -(kv[1][3] + kv[1][4]))
        ]
        document["routes"][name] = entry
        say(f"route {name}: mean {entry['mean']}, success {entry['success']}, {entry['gaps']} gap(s), {entry['divergences']} divergences")
        for line in route_table:
            if line.get("carried"):
                say(f"    {line['action']}: uses {line['uses']:.4g} x {line['price']:.4g} = {line['carried']:,.1f}")
        for pair in entry["divergence_pairs"]:
            say(f"    pair guide {pair['route_action']} / planner {pair['planner_action']}: {pair['states']} states, planner carries {pair['planner_carried']:,.1f}, route carries {pair['route_carried']:,.1f}")
        for row in rows[:12]:
            say(f"    {row['state']}: {row['description']}: guide {row['route_action']}, planner {row['planner_action']}, visits {row['planner_visits']:.4g} / {row['route_visits']:.4g}")
    for line in planner_table:
        if line.get("carried"):
            say(f"planner {line['action']}: uses {line['uses']:.4g} x {line['price']:.4g} = {line['carried']:,.1f}")
    (out / "costs.json").write_text(json.dumps(document, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
