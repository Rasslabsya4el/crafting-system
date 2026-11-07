"""Where the cost of a benchmark route sits, and every divergence of the planner from the guide with the cost it carries (ticket #599).

    python .github/scripts/divergence_costs.py R04 OUT_DIR [EXTRA_ROUTE.yaml ...]

Plans the benchmark route (the packed solver, as `benchmark --heavy` does), then for the planner's policy, the guide as written, the guide
completed and each EXTRA route file (a completion read another way) prints and writes `OUT_DIR/costs.json`:

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


def hybrid_tools(plan, data):
    """Functions to evaluate the mean of a route that takes the planner's action in some states (ticket #599).

    `actions_of(route)` is the route's graph action and price at every state of the walked graph (a state it does nothing at: -1), `mean_of(chosen, cost)`
    the exact mean (the start price excluded) of the policy that takes those actions, found on the lumped chain with a dense solve.
    """
    import numpy as np

    from crafting_system.cli import _route_packed as packed
    from crafting_system.cli._packed import lumped_policy
    from crafting_system.solver import lump_policy
    from crafting_system.solver._packed_merge import exact_classes, quotient

    walked = plan.policy.walked
    graph = walked.graph

    def actions_of(route):
        reading = packed._Reading(plan, route, data)
        chosen = np.full(graph.n, -1, dtype=np.int64)
        cost = np.zeros(graph.n)
        for i in range(graph.n):
            if graph.goal[i]:
                continue
            found = reading.choose(i)
            if isinstance(found, str):
                continue
            chosen[i] = found[1]
            cost[i] = reading.priced[found[0]].cost
        return chosen, cost

    def mean_of(chosen, cost):
        chain = packed.restricted(graph, chosen, cost)
        classes = exact_classes(chain)
        reduced, _ = quotient(chain, classes)
        class_action = np.where(np.diff(reduced.act_ptr) > 0, reduced.act_ptr[:-1], -1)
        lumped = lump_policy(reduced, class_action, int(classes.cls[0]))
        policy = lumped_policy(lumped, reduced, walked.offers)
        goal = lumped.goal
        reach, todo = {lumped.start}, [lumped.start]
        while todo:
            block = todo.pop()
            if goal[block]:
                continue
            action = policy.get(block)
            if action is None:
                return float("inf")  # a reachable block with no action: the run never finishes
            for target, _ in action.outcomes:
                if target not in reach:
                    reach.add(target)
                    todo.append(target)
        blocks = sorted(b for b in reach if not goal[b])
        if lumped.start not in blocks:
            return 0.0
        index = {b: k for k, b in enumerate(blocks)}
        matrix = np.eye(len(blocks))
        rhs = np.zeros(len(blocks))
        for b in blocks:
            action = policy[b]
            total = sum(weight for _, weight in action.outcomes)
            rhs[index[b]] = action.cost
            for target, weight in action.outcomes:
                if target in index:
                    matrix[index[b], index[target]] -= weight / total
        try:
            return float(np.linalg.solve(matrix, rhs)[index[lumped.start]])
        except np.linalg.LinAlgError:
            return float("inf")  # the policy loops among its blocks and never reaches a goal

    return actions_of, mean_of, walked


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
                by_state[state] = (weight, step.cost, step.action.label)
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

    def top_states(by_state: dict, per_action: int = 6) -> dict:
        """The states that carry most of each action, with their expected visits and description."""
        found: dict = {}
        for state, (weight, price, label) in by_state.items():
            found.setdefault(label, []).append((weight * price, weight, state))
        return {
            label: [
                {"state": ids.get(state), "visits": weight, "carried": carried, "description": describe_state(plan, data, state)}
                for carried, weight, state in sorted(rows, key=lambda row: -row[0])[:per_action]
            ]
            for label, rows in found.items()
        }

    document["planner"]["top_states"] = top_states(planner_visits)
    routes = [("guide", bench.route), ("completed", bench.completed), *[(Path(p).name, p) for p in argv[2:]]]
    guide = load_route(root / bench.route, plan, data)  # the rules of the guide, to tell the restarts a completion added
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
            pv, pc, _ = planner_visits.get(divergence.state, (0.0, 0.0, ""))
            rv, rc, _ = route_visits.get(divergence.state, (0.0, 0.0, ""))
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
        entry["top_states"] = top_states(route_visits)
        entry["restart_rules"] = restart_rules(plan, data, route, guide, route_visits, ids)
        entry["gap_states"] = [
            {"state": ids.get(gap.state), "reason": gap.reason, "visits_in_completed": None, "description": describe_state(plan, data, gap.state)}
            for gap in result.gaps
        ]
        document["routes"][name] = entry
        say(f"route {name}: mean {entry['mean']}, success {entry['success']}, {entry['gaps']} gap(s), {entry['divergences']} divergences")
        for line in route_table:
            if line.get("carried"):
                say(f"    {line['action']}: uses {line['uses']:.4g} x {line['price']:.4g} = {line['carried']:,.1f}")
        for pair in entry["divergence_pairs"]:
            say(f"    pair guide {pair['route_action']} / planner {pair['planner_action']}: {pair['states']} states, planner carries {pair['planner_carried']:,.1f}, route carries {pair['route_carried']:,.1f}")
        for label, found in entry["top_states"].items():
            for row in found[:6]:
                say(f"    top {label}: {row['state']} visits {row['visits']:.4g} carried {row['carried']:,.1f}: {row['description']}")
        for gap in entry["gap_states"]:
            say(f"    gap {gap['state']}: {gap['reason']}: {gap['description']}")
        for line in entry["restart_rules"]:
            say(
                f"    restart rule at line {line['line']}{' (not in the guide)' if line['added'] else ''}: {line['states']} states, uses {line['uses']:.6g} per run"
                f" x start price {line['price']:.4g} = {line['carried']:,.2f}"
            )
            for row in line["top_states"]:
                say(f"        restart state {row['state']} visits {row['visits']:.4g}: {row['description']}")
        for row in rows[:12]:
            say(f"    {row['state']}: {row['description']}: guide {row['route_action']}, planner {row['planner_action']}, visits {row['planner_visits']:.4g} / {row['route_visits']:.4g}")
    for label, found in document["planner"]["top_states"].items():
        for row in found[:6]:
            say(f"planner top {label}: {row['state']} visits {row['visits']:.4g} carried {row['carried']:,.1f}: {row['description']}")
    for line in planner_table:
        if line.get("carried"):
            say(f"planner {line['action']}: uses {line['uses']:.4g} x {line['price']:.4g} = {line['carried']:,.1f}")
    try:
        hybrids(document, plan, data, root, routes, say, shift)
    except Exception:  # the tables above are already worth having
        import traceback

        say("hybrids failed:\n" + traceback.format_exc())
    (out / "costs.json").write_text(json.dumps(document, indent=1, default=str), encoding="utf-8")
    return 0


def restart_rules(plan, data, route, guide, route_visits, ids):
    """The `restart` uses of a route split by the rule that fires them (ticket #619).

    One row per rule of the route that fires a `restart` in some state of the walked graph: its line, whether the guide has it (a rule of the route whose
    conditions and action are not in the guide is `added`), the states, the expected uses per run (the visits of those states: each visit buys the start item
    once) and what they carry at the start price. The uses plus 1 are the start items bought per run.
    """
    from crafting_system.cli._report import describe_state
    from crafting_system.cli._route import RESTART
    from crafting_system.cli._route_completion import _fired, added_restarts
    from crafting_system.cli._route_packed import _Reading

    walked = plan.policy.walked
    index = {state: i for i, state in enumerate(walked.states)}
    reading = _Reading(plan, route, data)
    added = added_restarts(guide, route)
    rows: dict = {}
    for state, (weight, price, label) in route_visits.items():
        if label != RESTART:
            continue
        k = _fired(reading, route, index[state])
        row = rows.setdefault(k, {"line": route.rules[k].line, "states": 0, "uses": 0.0, "price": price, "members": []})
        row["states"] += 1
        row["uses"] += weight
        row["members"].append((weight, state))
    out = []
    for k, row in sorted(rows.items()):
        members = sorted(row.pop("members"), key=lambda m: -m[0])
        row["carried"] = row["uses"] * row["price"]
        row["added"] = k in added
        row["top_states"] = [{"state": ids.get(s), "visits": w, "description": describe_state(plan, data, s)} for w, s in members[:8]]
        out.append(row)
    return out


def hybrids(document, plan, data, root, routes, say, shift):
    """For each base route: its mean when it takes the planner's action in the divergence states of one group, and in all of them.

    A group is the pair (the route's action, the planner's action) together with which wanted mods the item holds and whether it carries a crafted
    mod. Adopting a group alone shows what that group costs the route; adopting all must give the planner's own mean (the check of the method).
    """
    from crafting_system.cli import evaluate_route, load_route
    from crafting_system.cli._report import describe_state

    actions_of, mean_of, walked = hybrid_tools(plan, data)
    graph = walked.graph
    index = {state: i for i, state in enumerate(walked.states)}
    mine = plan.policy.action_array
    planner_cost = graph.act_cost
    document["hybrids"] = {}
    for name, path in routes:
        if path is None or name == "guide":
            continue
        route = load_route(root / path if not Path(path).is_absolute() and (root / path).exists() else Path(path), plan, data)
        result = evaluate_route(plan, route, data)
        chosen, cost = actions_of(route)
        base = mean_of(chosen, cost) + shift
        say(f"hybrids of {name}: base mean {base:,.2f}")
        groups: dict = {}
        for divergence in result.divergences:
            state = divergence.state
            key = (divergence.route_action, divergence.solver_action, tuple(s.name for s in state.status), bool(state.crafted))
            groups.setdefault(key, []).append(index[state])

        def adopt(members):
            c2, k2 = chosen.copy(), cost.copy()
            for i in members:
                c2[i] = mine[i]
                k2[i] = planner_cost[mine[i]]
            return mean_of(c2, k2) + shift

        everything = [i for members in groups.values() for i in members]
        rows = []
        for key, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            mean = adopt(members)
            rows.append(
                {
                    "route_action": key[0], "planner_action": key[1], "status": key[2], "crafted": key[3], "states": len(members),
                    "mean_if_adopted": mean, "saves": base - mean, "example": describe_state(plan, data, walked.states[members[0]]),
                }
            )
            say(f"  adopt {key[1]} for {key[0]} at {len(members)} states {key[2]} crafted={key[3]}: mean {mean:,.2f} (saves {base - mean:,.2f})")
        pairs: dict = {}
        for key, members in groups.items():
            pairs.setdefault((key[0], key[1]), []).extend(members)
        pair_rows = []
        for (theirs, ours), members in sorted(pairs.items(), key=lambda kv: -len(kv[1])):
            mean = adopt(members)
            pair_rows.append({"route_action": theirs, "planner_action": ours, "states": len(members), "mean_if_adopted": mean, "saves": base - mean})
            say(f"  PAIR adopt {ours} for {theirs} at {len(members)} states: mean {mean:,.2f} (saves {base - mean:,.2f})")
        document["hybrids"][name] = {"base": base, "all_adopted": adopt(everything), "groups": rows, "pairs": pair_rows}
        say(f"  all adopted: {document['hybrids'][name]['all_adopted']:,.2f} (the planner's mean is {document['planner']['mean']:,.2f})")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
