"""The planner side of the long routes R04 and R14, for `tests/test_naive_crafter_routes.py` (ticket #610, PR #665).

    python tests/naive_planner_side.py plan R04 OUT_DIR
        Heavy (R04 about 10 minutes, R14 about 45 on a runner). Plans the route as `benchmark` does (`make_plan`), evaluates the guide's route as written and the completed
        route (the route file with a restart) and writes `OUT_DIR/planner-side-R04.json`.
    python tests/naive_planner_side.py write DIR --run RUN_ID --commit SHA
        Reads every `planner-side-*.json` under DIR and writes `tests/fixtures/naive_crafter/benchmark_means.json` (keeping the naive shares already recorded there).

What is recorded, and what it is not:
  * `mean_without_start`: `risk.mean.value` of the completed route. It does NOT include the price of the bought start item, as the naive player's mean does not (a `restart` pays
    it again, the first purchase is left out). `benchmark` prints `mean + start price` (`_benchmark._totals`, `shift`), so a number copied from its JSON is wrong by the start price:
    `start_price` and `mean_with_start` are written beside it and the test checks `mean_with_start - start_price == mean_without_start`.
  * the success of the guide's route as written is the planner's bracket `(low, high)` and its printed `value` (the low end, issue #683).
  * `inputs`: the hashes of the target and route files and the cost of one use of each action of the route at the price file; `pin`: the version of the game data.
This file is outside `tests/naive_crafter/`, so it may import the planner (the independence guard looks at the package only).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
KEYS = ROOT / "tests" / "reconcile" / "expected_keys.txt"
TARGETS = ROOT / "examples" / "targets"
ROUTES = ROOT / "examples" / "routes"
PIN_FILE = ROOT / "src" / "crafting_system" / "data" / "PIN.json"
RECORDED = ROOT / "tests" / "fixtures" / "naive_crafter" / "benchmark_means.json"
STEMS = {"R04": "r04-penetrating-quiver", "R14": "r14-hunter-bow"}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()  # line ends as in the repository, so a Windows checkout hashes the same


def data_pin() -> str:
    return json.loads(PIN_FILE.read_text(encoding="utf-8"))["version"]


def route_labels(stem: str) -> list[str]:
    seen: list[str] = []
    for rule in yaml.safe_load((ROUTES / f"{stem}.yaml").read_text(encoding="utf-8"))["rules"]:
        if rule["do"] not in seen:
            seen.append(rule["do"])
    return seen


def inputs_of(stem: str) -> dict:
    """What a planner number of this route is computed from: the target and route hashes, and the cost of one use of each action of the route at the price file."""
    from naive_crafter.world import load_world

    world = load_world(TARGETS / f"{stem.removesuffix('-restart')}.yaml", PRICES, KEYS)
    return {
        "target": sha256_of(TARGETS / f"{stem.removesuffix('-restart')}.yaml"),
        "route": sha256_of(ROUTES / f"{stem}.yaml"),
        "costs": {label: round(world.action(label).cost, 9) for label in route_labels(stem)},
    }


def plan_route(route_id: str, out: Path) -> Path:
    from crafting_system.cli import _packed, evaluate_route, load_route, make_plan
    from crafting_system.data import load_game_data
    from crafting_system.prices import load_price_file
    from crafting_system.targets import load_target

    _packed.PROGRESS = lambda text: print(text, flush=True)
    stem = STEMS[route_id]
    data = load_game_data()
    plan = make_plan(data, load_target(TARGETS / f"{stem}.yaml", data), load_price_file(PRICES))
    found: dict = {"route": route_id, "pin": data_pin(), "start_price": plan.start_price.chaos}
    for kind, name in (("guide", stem), ("completed", f"{stem}-restart")):
        result = evaluate_route(plan, load_route(ROUTES / f"{name}.yaml", plan, data), data)
        risk = result.risk
        found[kind] = {
            "stem": name,
            "mean_without_start": risk.mean.value,
            "success_value": risk.success_probability.value,
            "success_low": risk.success_probability.low,
            "success_high": risk.success_probability.high,
            "gaps": len(result.gaps),
        }
        print(f"{route_id} {kind}: {found[kind]}", flush=True)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"planner-side-{route_id}.json"
    path.write_text(json.dumps(found, indent=1, sort_keys=True, allow_nan=True), encoding="utf-8")
    return path


def write_fixture(folder: Path, run: str, commit: str) -> Path:
    old = json.loads(RECORDED.read_text(encoding="utf-8")) if RECORDED.is_file() else {"routes": {}}
    routes: dict = {}
    for path in sorted(folder.rglob("planner-side-*.json")):
        found = json.loads(path.read_text(encoding="utf-8"))
        route_id, start = found["route"], found["start_price"]
        for kind, label in (("completed", f"{route_id} with restart"), ("guide", route_id)):
            entry = dict(found[kind])
            stem = entry.pop("stem")
            mean = entry.pop("mean_without_start")
            record = {"stem": stem, "pin": found["pin"], "run": run, "commit": commit, "inputs": inputs_of(stem), **entry}
            if kind == "completed":
                record.update(mean_without_start=mean, start_price=start, mean_with_start=mean + start)
            if "naive_heavy" in old["routes"].get(label, {}):
                record["naive_heavy"] = old["routes"][label]["naive_heavy"]
            routes[label] = record
    for label, record in old["routes"].items():
        routes.setdefault(label, record)
    RECORDED.write_text(json.dumps({"provenance": old.get("provenance", {}), "routes": routes}, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return RECORDED


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="naive_planner_side")
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("route", choices=sorted(STEMS))
    plan.add_argument("out", type=Path)
    write = commands.add_parser("write")
    write.add_argument("folder", type=Path)
    write.add_argument("--run", required=True)
    write.add_argument("--commit", required=True)
    arguments = parser.parse_args(argv)
    if arguments.command == "plan":
        print(f"wrote {plan_route(arguments.route, arguments.out)}")
    else:
        print(f"wrote {write_fixture(arguments.folder, arguments.run, arguments.commit)}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main(sys.argv[1:]))
