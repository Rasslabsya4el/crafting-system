"""Which parts of the compressed state make the states of a benchmark route, and do they change any decision (ticket #399, step 1 "bloat").

    python .github/scripts/state_bloat.py run     --route ID --out DIR      writes DIR/route-ID.json
    python .github/scripts/state_bloat.py summary --dir DIR  --out DIR2     writes DIR2/summary.md and DIR2/headline.txt

`run` builds the plan of one benchmark route the way `cli._benchmark.run_route(..., heavy=True)` does (same target, offers, prices,
start and options: it calls the same functions, only the risk run is left out; the prices are the committed file of the benchmark routes,
`PRICES`, because a CI checkout has no price file of its own), keeps the states the planner walked with the optimal
value and the first action of the optimal policy at each, and then, for each part of `CompressedState` (and for the names of the junk
mods inside `slots`), projects that part away and counts what is left:

* `states`: the distinct states after the projection;
* `groups`: the groups of walked states that the projection puts together (a group of at least two states);
* `value_groups`: those holding states whose optimal values differ by more than `VALUE_TOLERANCE` (relative), a finite value and an
  infinite one counting as different; `action_groups`: those holding states whose optimal first actions have different offer labels;
  `changing_groups`: either of the two;
* `max_rel`: the largest relative difference of the values in a group whose values are all finite.

A part that merges many states into groups that change no decision is a candidate to leave out of the state. Every walked state counts,
also those the optimal policy never reaches; `policy_states` and `policy_blocks` are the part of the graph the policy uses.

The junk projection: a mod that is not crafted and gives no leaf of the goal anything (all contributions ABSENT) loses its `kind` (the
numbered family type `~n` or a family key), keeping its side, its contribution and the Attack/Caster tag after an `@`; slots are then
a multiset again (sorted). `slots` replaces the whole tuple by a constant.

Never run on a PC for a real route: R04 and R14 hold hundreds of thousands of states. Run by `.github/workflows/measure-bloat.yml`.
"""

import argparse
import dataclasses
import json
import math
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from math import gcd
from pathlib import Path

import numpy as np

from crafting_system.abstraction import CompressedState
from crafting_system.config import Config, find_project_root, load_config
from crafting_system.data import GameData, load_game_data
from crafting_system.prices import PriceFile, load_price_file
from crafting_system.cli import _packed
from crafting_system.cli._benchmark import (
    BENCHMARKS,
    ROUTE_ERRORS,
    BenchmarkRoute,
    _missing_message,
    _missing_start_price,
    _without_root,
)
from crafting_system.cli._inputs import load_target_prices, write_json
from crafting_system.cli._plan import Plan, make_plan
from crafting_system.cli._route import evaluate_route, load_route
from crafting_system.cli._starts import plan_with_starts
from crafting_system.targets import load_target

PARTS = ("flags", "fractured", "status", "slots", "implicits", "quality", "offer", "imprints")
JUNK = "junk_names"
COLUMNS = (*PARTS, JUNK)
ORDER = ("R12", "R10", "R11", "R05", "R13", "R08", "R09", "R04", "R14")
VALUE_TOLERANCE = 1e-9  # values in a group differ when their relative difference is above this
FORMAT = "crafting-system-state-bloat/1"
PRICES = "tests/fixtures/prices/routes-allflame-2026-10-31.json"  # from the project root; the prices of the packed-solver measurements (ADR-0063)

RUSSIAN = {
    "flags": "флагов предмета",
    "fractured": "расколотых модов",
    "status": "статусов целей",
    "slots": "всех обычных модов",
    "implicits": "неявных модов",
    "quality": "качества",
    "offer": "предложения раскрытия",
    "imprints": "слепков",
    JUNK: "имён мусорных модов",
}


# --- the projections -----------------------------------------------------------------------------


def check_fields(cls: type = CompressedState) -> None:
    """Fail loudly when `cls` has fields other than the parts measured here: a new field of the state must be measured, not skipped."""
    names = tuple(field.name for field in dataclasses.fields(cls))
    if names != PARTS:
        raise ValueError(
            f"{cls.__name__} has the fields {names}, but state_bloat measures {PARTS}: "
            "add the new field to PARTS (and to RUSSIAN) so that the measurement sees it"
        )


def _values(state: CompressedState) -> list:
    return [getattr(state, name) for name in PARTS]


def _junk_kind(kind: str) -> str:
    """The kind of a junk mod without its name: the Attack/Caster tag after the `@` is kept, the rest is dropped."""
    return "@" + kind.partition("@")[2] if "@" in kind else ""


def _slots_without_junk_names(state: CompressedState) -> tuple:
    return tuple(
        sorted(
            (
                slot.side.value,
                slot.kind if slot.crafted or any(int(each) for each in slot.contribution) else _junk_kind(slot.kind),
                tuple(int(each) for each in slot.contribution),
                slot.crafted,
            )
            for slot in state.slots
        )
    )


def junk_key(state: CompressedState) -> tuple:
    """The state with the names of its junk mods dropped, as a hashable key (the imprints it holds are read the same way)."""
    values = _values(state)
    values[PARTS.index("slots")] = _slots_without_junk_names(state)
    values[PARTS.index("imprints")] = tuple(junk_key(held) for held in state.imprints)
    return tuple(values)


def projector(part: str, cls: type = CompressedState) -> Callable[[CompressedState], tuple]:
    """The function that maps a state to a hashable key with `part` replaced by a constant (`JUNK`: the junk mods' names dropped).

    Checks the fields of `cls` first, so a state with a new field is refused here and not measured with that field left in.
    """
    check_fields(cls)
    if part == JUNK:
        return junk_key
    if part not in PARTS:
        raise KeyError(f"{part!r} is not a part of the state: {COLUMNS}")
    position = PARTS.index(part)

    def project(state: CompressedState) -> tuple:
        values = _values(state)
        values[position] = None
        return tuple(values)

    return project


# --- what a projection merges --------------------------------------------------------------------


def relative_difference(low: float, high: float) -> float:
    """`(high - low) / max(|low|, |high|)` for finite values, 0 when both are 0."""
    scale = max(abs(low), abs(high))
    return (high - low) / scale if scale > 0 else 0.0


def measure_part(
    states: Sequence[object],
    values: Sequence[float],
    actions: Sequence[object],
    project: Callable[[object], object],
) -> dict:
    """Project every state away and count what is left, and what the groups that merge hold; one streaming pass.

    `values[i]` and `actions[i]` (any comparable label, None for none) belong to `states[i]`.
    """
    groups: dict = {}
    for state, value, action in zip(states, values, actions):
        key = project(state)
        group = groups.get(key)
        if group is None:
            # count, lowest finite value, highest finite value, any infinite value, first action, actions differ
            groups[key] = [1, value, value, False, action, False] if math.isfinite(value) else [1, math.inf, -math.inf, True, action, False]
            continue
        group[0] += 1
        if math.isfinite(value):
            if value < group[1]:
                group[1] = value
            if value > group[2]:
                group[2] = value
        else:
            group[3] = True
        if action != group[4]:
            group[5] = True
    merged = value_groups = action_groups = changing = 0
    largest = 0.0
    for count, low, high, infinite, _, differ in groups.values():
        if count < 2:
            continue
        merged += 1
        finite = low <= high
        spread = relative_difference(low, high) if finite else 0.0
        if not infinite:
            largest = max(largest, spread)
        changed = (infinite and finite) or spread > VALUE_TOLERANCE
        value_groups += changed
        action_groups += differ
        changing += changed or differ
    return {
        "states": len(groups),
        "groups": merged,
        "value_groups": value_groups,
        "action_groups": action_groups,
        "changing_groups": changing,
        "max_rel": largest,
    }


def measure_all(states: Sequence[CompressedState], values: Sequence[float], actions: Sequence[object]) -> dict:
    """`measure_part` for every part and for the junk names."""
    return {column: measure_part(states, values, actions, projector(column)) for column in COLUMNS}


# --- the lumped chain ----------------------------------------------------------------------------


def lump_chain(policy: Mapping, start: object, is_goal: Callable[[object], bool]) -> tuple[int, int]:
    """`(reached, blocks)` of the chain `policy` makes from `start`: the non-goal nodes it reaches, and the blocks of the coarsest partition
    of them in which two nodes pay the same cost and move to each block with the same chances.

    `policy[node]` has `.cost` and `.outcomes` (pairs `(successor, integer weight)`). A successor outside `policy` is a goal (one block) or
    a node of its own.
    """
    order = [start]
    seen = {start}
    for node in order:
        action = policy.get(node)
        if action is None:
            continue
        for successor, weight in action.outcomes:
            if weight > 0 and successor not in seen:
                seen.add(successor)
                order.append(successor)
    nodes = [node for node in order if node in policy]
    number = {node: i for i, node in enumerate(nodes)}
    goal = len(nodes)  # the one block of every goal
    outside: dict = {}
    moves: list[list[tuple[int, int]]] = []
    for node in nodes:
        row = []
        for successor, weight in policy[node].outcomes:
            if weight <= 0:
                continue
            if successor in number:
                row.append((number[successor], weight))
            elif is_goal(successor):
                row.append((goal, weight))
            else:
                row.append((outside.setdefault(successor, goal + 1 + len(outside)), weight))
        moves.append(row)
    block = [0] * (goal + 1 + len(outside))
    costs: dict[float, int] = {}
    for i, node in enumerate(nodes):
        block[i] = costs.setdefault(float(policy[node].cost), len(costs))
    top = len(costs)
    block[goal] = top
    for k in range(len(outside)):
        block[goal + 1 + k] = top + 1 + k  # a node outside the policy that is no goal stays alone
    count = len(costs)
    while True:
        names: dict = {}
        fresh = block[:]
        for i, row in enumerate(moves):
            into: dict[int, int] = {}
            for target, weight in row:
                into[block[target]] = into.get(block[target], 0) + weight
            divisor = 0
            for weight in into.values():
                divisor = gcd(divisor, weight)
            signature = (block[i], tuple(sorted((b, w // divisor) for b, w in into.items())))
            fresh[i] = names.setdefault(signature, len(names))
        if len(names) == count:
            return len(nodes), count
        count = len(names)
        shift = count + 1  # the goal and the outside nodes keep numbers apart from the blocks of the nodes
        block = fresh[: len(nodes)] + [shift + k for k in range(len(block) - len(nodes))]


# --- the plan of one route -----------------------------------------------------------------------


def plan_of(bench: BenchmarkRoute, data: GameData, root: Path, config: Config, prices: PriceFile | None, solver: str = "auto") -> Plan:
    """The plan `run_route` makes for `bench` (its target, prices, start options and offers), without the risk run."""
    target = load_target(root / bench.target, data)
    loaded = prices if prices is not None else load_target_prices(target.price_file, config)
    missing = _missing_start_price(target, loaded, root, config)
    if missing is not None:
        raise ValueError(_missing_message(missing))
    if bench.start is None:
        return make_plan(data, target, loaded, with_risk=False, solver=solver)
    return plan_with_starts(data, target, loaded, with_risk=False, solver=solver)


def walked_of(plan: Plan) -> dict:
    """What the plan walked: the states, the optimal value and the label of the optimal first action of each, and the counts.

    A packed plan (`plan.packed`) keeps every walked state in `policy._walked` and the action index of each in `policy._action`
    (-1 for a goal or a dead state); an object plan keeps the values of every state it solved in `solution.values` and the action of the
    states with a finite value in `solution.policy`.
    """
    solution = plan.solution
    walked = getattr(solution.policy, "_walked", None)
    if plan.packed is not None and walked is not None:
        states = walked.states
        values = [solution.values[state] for state in states]
        chosen = solution.policy._action  # type: ignore[attr-defined]
        names = [offer.label for offer in walked.offers]
        tag = np.where(chosen >= 0, walked.graph.act_tag[np.maximum(chosen, 0)], -1)
        actions = [names[t] if t >= 0 else None for t in tag.tolist()]
        policy, start, is_goal = plan.packed.risk_policy, plan.packed.risk_start, plan.packed.risk_is_goal
        return {
            "solver": "packed", "states": states, "values": values, "actions": actions,
            "merged": plan.packed.info.get("classes"), "chain": (policy, start, is_goal),
        }  # fmt: skip
    states = list(solution.values)
    values = [solution.values[state] for state in states]
    actions = [solution.policy[state].label if state in solution.policy else None for state in states]
    return {
        "solver": "object", "states": states, "values": values, "actions": actions,
        "merged": None, "chain": (solution.policy, plan.start, plan.is_goal),
    }  # fmt: skip


def peak_mb() -> int | None:
    """The peak resident memory of this process in MB (None where the system does not say)."""
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    except ImportError:
        return None


def bloat_route(
    bench: BenchmarkRoute,
    data: GameData,
    root: Path,
    config: Config,
    prices: PriceFile | None = None,
    *,
    solver: str = "auto",
    say: Callable[[str], None] = lambda _text: None,
    keep: Callable[[dict], None] = lambda _document: None,
) -> dict:
    """The document of one route: the counts of the walk, then what each projection leaves. `keep` gets the document before the guide's route is read."""
    began = time.perf_counter()
    document: dict = {"format": FORMAT, "route": bench.id, "title": bench.title, "error": None, "solver_asked": solver}
    try:
        plan = plan_of(bench, data, root, config, prices, solver)
    except ROUTE_ERRORS as error:
        document["error"] = _without_root(str(error), root)
        document["seconds"], document["peak_mb"] = round(time.perf_counter() - began, 1), peak_mb()
        return document
    say(f"planned in {plan.solve_seconds:.0f} s")
    found = walked_of(plan)
    states, values, actions = found.pop("states"), found.pop("values"), found.pop("actions")
    policy, start, is_goal = found.pop("chain")
    document.update(
        solver=found["solver"], walked=len(states), merged=found["merged"], mean_remaining=plan.mean_remaining, solve_seconds=round(plan.solve_seconds, 1),
        policy_states=None, policy_blocks=None, route_states=None, route_blocks=None, route_gaps=None, route_error=None,
    )  # fmt: skip
    document["policy_states"], document["policy_blocks"] = lump_chain(policy, start, is_goal)
    say(f"{len(states):,} states; the policy reaches {document['policy_states']:,}, lumped into {document['policy_blocks']:,} blocks")
    del policy
    document["parts"] = measure_all(states, values, actions)
    document["seconds"], document["peak_mb"] = round(time.perf_counter() - began, 1), peak_mb()
    say("projections done")
    keep(document)
    del states, values, actions
    if bench.route is not None:
        try:
            result = evaluate_route(plan, load_route(root / bench.route, plan, data), data)
            document["route_states"], document["route_gaps"] = len(result.policy), len(result.gaps)
            document["route_blocks"] = lump_chain(result.policy, plan.start, plan.is_goal)[1]
        except ROUTE_ERRORS as error:
            document["route_error"] = _without_root(str(error), root)
    document["seconds"], document["peak_mb"] = round(time.perf_counter() - began, 1), peak_mb()
    return document


# --- the summary ---------------------------------------------------------------------------------


def number(value: float | int | None) -> str:
    return "-" if value is None else f"{value:,}"


def russian_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _short(value: float) -> str:
    return "0" if value == 0 else f"{value:.2g}"


def _row(cells: Sequence[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    return [_row(header), _row(["---"] * len(header)), *(_row(row) for row in rows)]


def headline_of(documents: Mapping[str, dict]) -> str:
    """One Russian line: on the biggest route that was measured, the part whose removal leaves fewest states with no decision changed."""
    done = [d for d in documents.values() if d.get("parts")]
    if not done:
        return "bloat: ни один маршрут не измерен"
    chosen = max(done, key=lambda d: (d["walked"], d["route"]))
    parts = chosen["parts"]
    walked = chosen["walked"]
    head = f"{chosen['route']}: {russian_number(walked)} состояний"
    free = [c for c in COLUMNS if parts[c]["changing_groups"] == 0 and parts[c]["states"] < walked]
    if free:
        best = min(free, key=lambda c: (parts[c]["states"], COLUMNS.index(c)))
        return f"{head}; без {RUSSIAN[best]} останется {russian_number(parts[best]['states'])}, решения не меняются нигде"
    merging = [c for c in COLUMNS if parts[c]["states"] < walked]
    if not merging:
        return f"{head}; ни одна часть не склеивает состояния, убирать нечего"
    best = min(merging, key=lambda c: (parts[c]["changing_groups"], parts[c]["states"], COLUMNS.index(c)))
    return (
        f"{head}; ни одну часть нельзя убрать без смены решений; ближе всего без {RUSSIAN[best]}: "
        f"останется {russian_number(parts[best]['states'])}, решения меняются в {russian_number(parts[best]['changing_groups'])} группах"
    )


def build_summary(documents: Mapping[str, dict]) -> tuple[str, str]:
    """`(summary.md, headline.txt)` from the route documents by route id; a route not in `documents` is shown as `missing`."""
    lines = [
        "# bloat",
        "",
        "How many distinct states are left when one part of the compressed state is projected away (`junk_names`: the names of the mods that give",
        "the goal nothing are dropped), and in how many groups of merged states the optimal value (relative difference over 1e-9) or the optimal",
        "first action differs. All walked states count, also those the optimal policy never reaches.",
        "",
        "## states left after the projection",
        "",
    ]
    head = ["route", "walked", "merged", *COLUMNS]
    rows = []
    ids = [*ORDER, *sorted(set(documents) - set(ORDER))]
    for route in ids:
        d = documents.get(route)
        if d is None:
            rows.append([route, *["missing"] * (len(head) - 1)])
        elif d.get("error") or not d.get("parts"):
            rows.append([route, f"error: {d.get('error') or 'no result'}"[:80], *[""] * (len(head) - 2)])
        else:
            rows.append([route, number(d["walked"]), number(d["merged"]), *(number(d["parts"][c]["states"]) for c in COLUMNS)])
    lines += _table(head, rows)
    lines += ["", "## groups where the decision changes (value / first action), and the largest relative value difference", ""]
    changed = []
    for route in ids:
        d = documents.get(route)
        if d is None:
            changed.append([route, *["missing"] * len(COLUMNS)])
        elif d.get("error") or not d.get("parts"):
            changed.append([route, *[""] * len(COLUMNS)])
        else:
            cells = []
            for c in COLUMNS:
                p = d["parts"][c]
                cells.append(f"{number(p['value_groups'])} / {number(p['action_groups'])} ({_short(p['max_rel'])})")
            changed.append([route, *cells])
    lines += _table(["route", *COLUMNS], changed)
    lines += ["", "## the chains and the run", ""]
    chains = []
    for route in ids:
        d = documents.get(route)
        if d is None or not d.get("parts"):
            chains.append([route, *["missing" if d is None else ""] * 8])
            continue
        chains.append(
            [
                route, d.get("solver", "-"), number(d.get("policy_states")), number(d.get("policy_blocks")),
                number(d.get("route_states")), number(d.get("route_blocks")), number(d.get("route_gaps")),
                number(d.get("seconds")), number(d.get("peak_mb")),
            ]
        )  # fmt: skip
    lines += _table(
        ["route", "solver", "policy states", "policy blocks", "route states", "route blocks", "route gaps", "seconds", "peak MB"], chains
    )
    failed = [(r, documents[r]) for r in ids if r in documents and (documents[r].get("error") or documents[r].get("route_error"))]
    if failed:
        lines += ["", "## errors", ""]
        lines += [f"- {r}: {d.get('error') or ''} {('(route: ' + d['route_error'] + ')') if d.get('route_error') else ''}".rstrip() for r, d in failed]
    return "\n".join(lines) + "\n", headline_of(documents) + "\n"


def read_documents(folder: Path) -> dict[str, dict]:
    """Every `route-*.json` under `folder` (an artifact download keeps one subfolder per route), by route id."""
    found = {}
    for path in sorted(folder.rglob("route-*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        found[document["route"]] = document
    return found


# --- the command ---------------------------------------------------------------------------------


def run_command(arguments: argparse.Namespace) -> int:
    began = time.perf_counter()

    def say(line: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f} s, {peak_mb()} MB] {line}", flush=True)

    bench = next((b for b in BENCHMARKS if b.id == arguments.route), None)
    if bench is None:
        print(f"unknown route {arguments.route!r}; the benchmark routes are {', '.join(b.id for b in BENCHMARKS)}", file=sys.stderr)
        return 2
    _packed.PROGRESS = say
    config = load_config(None)
    data = load_game_data(cache_dir=config.cache_dir)
    out = Path(arguments.out) / f"route-{bench.id}.json"
    root = find_project_root()
    prices = load_price_file(Path(arguments.prices) if arguments.prices else root / PRICES)
    document = bloat_route(
        bench, data, root, config, prices, solver=arguments.solver, say=say, keep=lambda partial: write_json(out, _clean(partial))
    )
    write_json(out, _clean(document))
    say(f"written {out}")
    return 1 if document["error"] else 0


def _clean(value):
    """The document with every infinite or NaN number replaced by None (JSON has none)."""
    if isinstance(value, dict):
        return {key: _clean(each) for key, each in value.items()}
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def summary_command(arguments: argparse.Namespace) -> int:
    text, headline = build_summary(read_documents(Path(arguments.dir)))
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.md").write_text(text, encoding="utf-8", newline="\n")
    (out / "headline.txt").write_text(headline, encoding="utf-8", newline="\n")
    print(text)
    print(headline)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="measure one benchmark route")
    run.add_argument("--route", required=True, help="a benchmark route id (R12, R10, ...)")
    run.add_argument("--out", required=True, help="the folder for route-ID.json")
    run.add_argument("--prices", help=f"a price file (default {PRICES}, the committed prices of the benchmark routes: a CI checkout has no price file of its own)")
    run.add_argument("--solver", default="auto", choices=_packed.SOLVERS, help="the solver of the plan (default auto, as the benchmark)")
    run.set_defaults(handler=run_command)
    summary = commands.add_parser("summary", help="the tables of the routes measured")
    summary.add_argument("--dir", required=True, help="the folder holding the route-ID.json files (searched in subfolders too)")
    summary.add_argument("--out", required=True, help="the folder for summary.md and headline.txt")
    summary.set_defaults(handler=summary_command)
    arguments = parser.parse_args(argv)
    return arguments.handler(arguments)


if __name__ == "__main__":
    sys.exit(main())
