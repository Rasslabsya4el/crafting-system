"""Where the envelope search spends its work, against the gap it is closing (research "planning speed", 2026-11-13). No `src/` change.

    python research/planning-speed/gap_trace.py --route r04|r14|r13|r05|r08|j01|v01|<target.yaml> [--out DIR] [--rollout-only]

It plans the route with `make_plan(solver="envelope", with_risk=False)`, the planner's own search, with two measurements added from outside:

1. **The gap after each round.** After each round's solve the search knows `L(root)`, the lower figure (no plan costs less). The script also
   solves the plan that can be executed now (`Search.upper_value`: the actions realized so far, and the restart wherever the search has not
   looked), whose mean `U` is an upper figure (that plan costs `U`, so the best costs at most `U`). It records, per round, the states known,
   expanded and the actions realized, `L`, `U`, and the search's own seconds (the seconds of the `U` solves are taken off). From that trace one
   reads how many states a search that stops when `U <= (1 + eps) L` would have expanded, for eps 1%, 0.1%, 0.01%, against the exact stop.
2. **One cheap policy, evaluated exactly.** Before the search, on the same problem (the same bound, the same offers), it follows from the start
   the action whose lower figure `la` is least at each state (the action the walk-free bound thinks best; a refused offer passes to the next),
   builds only the kernels that policy takes, and solves the chain with the restart allowed at every state. Its mean `U_abs` is the exact mean
   of an executable plan; its states are the only ones it needed. `U_abs / L(root)` is the gap a "bound plus one good policy" design would show.

At the end it reads, on the graph the search ended with: the states the optimal policy reaches, the expanded states outside that reach, and the
expanded states where the optimal action is the restart (the item is not worth going on with).

Settings here are measurement settings, not planner defaults (OR-12). Never run R04 or R14 on a PC: run them through
`python .github/scripts/heavy_dispatch.py run --ref research/planning-speed --runners N --command '...' --no-wait`.
"""

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
import packed_routes as P  # noqa: E402  (the inputs of a route and its prices; `ROUTE_PRICES` names another snapshot)

from crafting_system.cli import make_plan  # noqa: E402
from crafting_system.planner import _envelope, _envelope_plan, _packed  # noqa: E402
from crafting_system.planner._envelope import Refused, Search  # noqa: E402
from crafting_system.data import load_game_data  # noqa: E402
from crafting_system.solver import policy_reach  # noqa: E402
from crafting_system.solver._packed_solve import solve_graph  # noqa: E402
from crafting_system.targets import load_target  # noqa: E402

U_BUDGET = 1200.0  # seconds of `U` solves; past it `U` is solved every 5th round only (a measurement setting)
ROLLOUT_STATES = 2_000_000  # the cheap policy's reach is cut here, and the run says so (a measurement setting)
EXTRA = {"j01": "j01-cobalt-life-attack-speed", "v01": "v01-minion-helmet", "r09": "r09-life-boots", "r07": "r07-minion-wand", "r24": "r24-avoid-shock-boots"}
OUT: dict = {}


def say(line: str) -> None:
    print(f"[{time.perf_counter() - BEGAN:8.1f}s, {P.peak_mb()} MB] {line}", flush=True)


BEGAN = time.perf_counter()


def rollout(problem, tolerance: float) -> dict:
    """Follow the least-`la` action from the start, build only its kernels, and solve that policy with the restart allowed everywhere."""
    began = time.perf_counter()
    s = Search(problem, tolerance=tolerance, guard=False)
    if problem.restart is not None:
        s.restart_kernel = s._store([0], [1])
    queue, seen = [0], {0}
    refused = 0
    for i in queue:
        if s.goal[i]:
            continue
        if len(queue) > ROLLOUT_STATES:
            OUT["rollout_cut"] = ROLLOUT_STATES
            break
        s.expand(i)
        cands = s.cands[i]
        while cands:
            _, position = cands.pop()  # the least `la` is last
            try:
                kid = s._kernel(i, position)
            except Refused:
                refused += 1
                continue
            s.rows[i].append((position, problem.cost(position), kid, s._self_mass(i, kid)))
            s.stats.realized += 1
            for j in s.kernels.succ[s.kernels.span(kid)].tolist():
                if j not in seen:
                    seen.add(j)
                    queue.append(j)
            break
        problem.release()
        if len(queue) % 20_000 == 0:
            say(f"rollout: {len(queue):,} states")
    built = time.perf_counter() - began
    graph = s._graph("upper")
    core = solve_graph(graph, tolerance=tolerance, self_mass=s.self_mass)
    reach = policy_reach(graph, core.action, 0)
    acting = reach[core.action[reach] >= 0]
    restart_tag = problem.restart
    restarts = int(np.sum(graph.act_tag[core.action[acting]] == restart_tag)) if restart_tag is not None else 0
    return {
        "states": len(s.states), "kernels": s.stats.kernels, "refused": refused, "value": float(core.value[0]), "bound": float(core.certificate.bound),
        "reach": int(len(reach)), "acting": int(len(acting)), "restart_states": restarts, "build_seconds": round(built, 1),
        "seconds": round(time.perf_counter() - began, 1), "start_lower": float(problem.start_lower),
    }


class TracedSearch(Search):
    """The planner's search, with `U` solved after each round (see the module text)."""

    rollout_only = False

    def __init__(self, problem, **kwargs) -> None:
        super().__init__(problem, **kwargs)
        self.trace: list[dict] = []
        self._seen_round = 0
        self.u_seconds = 0.0
        self.began = None

    def run(self):
        say("rollout of the least-la policy ...")
        OUT["rollout"] = r = rollout(self.p, self.tolerance)
        say(f"rollout: {json.dumps(r)}")
        if self.rollout_only:
            raise SystemExit(0)
        self.began = time.perf_counter()
        result = super().run()
        if result.exact:
            self.trace.append(self._row(float(result.lower), float(result.lower), 0.0))
        OUT["trace"] = self.trace
        OUT["final"] = self._final(result)
        return result

    def _row(self, lower: float, upper: float | None, u_time: float) -> dict:
        st = self.stats
        return {
            "round": st.rounds, "seconds": round(time.perf_counter() - self.began - self.u_seconds, 1), "known": len(self.states),
            "expanded": st.expanded, "realized": st.realized, "kernels": st.kernels, "lower": lower, "upper": upper, "u_seconds": round(u_time, 2),
        }

    def _net(self, began, *args, **kwargs):  # also asked inside the first plan's chain since #826, before any round
        if self.stats.rounds != self._seen_round:
            self._seen_round = self.stats.rounds
            upper = None
            mark = time.perf_counter()
            if self.u_seconds < U_BUDGET or self.stats.rounds % 5 == 0:
                try:
                    upper = self.upper_value()
                except Exception as error:  # a stiff graph the solver cannot certify: recorded, not fatal
                    say(f"upper solve failed: {error!r}")
            spent = time.perf_counter() - mark
            self.u_seconds += spent
            row = self._row(float(self.stats.lower_history[-1]), upper, spent)
            self.trace.append(row)
            gap = (upper / row["lower"] - 1.0) if upper is not None and row["lower"] > 0 and math.isfinite(upper) else None
            say(f"TRACE round {row['round']} expanded {row['expanded']:,} L {row['lower']!r} U {upper!r} gap {gap!r} (U solve {spent:.1f} s)")
        return super()._net(began, *args, **kwargs)

    def _final(self, result) -> dict:
        """On the graph the search ended with: the optimal policy's reach, and the expanded states outside it or where it restarts."""
        graph = result.graph
        core = solve_graph(graph, tolerance=self.tolerance)
        reach = policy_reach(graph, core.action, 0)
        acting = reach[core.action[reach] >= 0]
        expanded = np.frombuffer(bytes(self.expanded), dtype=np.uint8).astype(bool)
        in_reach = np.zeros(graph.n, dtype=bool)
        in_reach[reach] = True
        restart_tag = self.p.restart
        chosen = np.full(graph.n, -9, dtype=np.int64)
        has = core.action >= 0
        chosen[has] = graph.act_tag[core.action[has]]
        restart_states = int(np.sum(expanded & (chosen == restart_tag))) if restart_tag is not None else 0
        return {
            "mean": float(core.value[0]), "policy_reach": int(len(reach)), "policy_acting": int(len(acting)),
            "expanded": int(expanded.sum()), "expanded_outside_reach": int(np.sum(expanded & ~in_reach)),
            "expanded_restart_optimal": restart_states, "known": len(self.states), "rounds": self.stats.rounds,
            "search_seconds": round(time.perf_counter() - self.began - self.u_seconds, 1), "u_seconds": round(self.u_seconds, 1),
            "solve_seconds": round(self.stats.solve_seconds, 1), "expand_seconds": round(self.stats.expand_seconds, 1),
            "peak_mb": self.stats.peak_mb,
        }


def stops(trace: list[dict]) -> dict:
    """The first round at which `U <= (1 + eps) L`, for each eps: what an eps stop would have expanded and taken."""
    found = {}
    for eps in (0.01, 0.001, 0.0001, 0.0):
        for row in trace:
            u, low = row["upper"], row["lower"]
            if u is not None and low > 0 and u <= low * (1 + eps) + 1e-9 * low:
                found[str(eps)] = {k: row[k] for k in ("round", "seconds", "known", "expanded", "realized", "lower", "upper")}
                break
    return found


def target_of(route: str):
    if route.endswith(".yaml"):
        data = load_game_data()
        return data, load_target(Path(route), data), P.load_price_file(ROOT / os.environ["ROUTE_PRICES"] if os.environ.get("ROUTE_PRICES") else P.PRICES), None
    if route in EXTRA:
        data = load_game_data()
        prices = P.load_price_file(ROOT / os.environ["ROUTE_PRICES"] if os.environ.get("ROUTE_PRICES") else P.PRICES)
        return data, load_target(ROOT / "examples" / "targets" / f"{EXTRA[route]}.yaml", data), prices, None
    return P.inputs(route)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", required=True)
    parser.add_argument("--out")
    parser.add_argument("--rollout-only", action="store_true")
    arguments = parser.parse_args()
    TracedSearch.rollout_only = arguments.rollout_only
    _envelope_plan.Search = TracedSearch  # the plan's search, traced
    _packed.PROGRESS = say
    data, target, prices, start_price = target_of(arguments.route)
    say(f"{arguments.route}: target loaded, prices {os.environ.get('ROUTE_PRICES', 'default fixture')}")
    began = time.perf_counter()
    plan = make_plan(data, target, prices, start_price=start_price, budget=None, solver="envelope", with_risk=False)
    info = plan.info if hasattr(plan, "info") else None
    OUT.update(route=arguments.route, plan_seconds=round(time.perf_counter() - began, 1), mean_remaining=plan.mean_remaining, policy_states=len(plan.policy), peak_mb=P.peak_mb())
    if "trace" in OUT:
        OUT["stops"] = stops(OUT["trace"])
    text = json.dumps(OUT, indent=1, default=str)
    print(text, flush=True)
    if arguments.out:
        out = Path(arguments.out)
        out.mkdir(parents=True, exist_ok=True)
        name = Path(arguments.route).stem
        (out / f"{name}.trace.json").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
