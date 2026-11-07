"""The rule of a completed route on every state it reaches (tickets #599, #628).

    python .github/scripts/completion_check.py R04 OUT_DIR

Plans the benchmark route (the packed solver), reads its completed route (`BenchmarkRoute.completed`) on the walked graph and lists every
state where a `restart` that the guide does not have fires while an action of the guide's own rules is legal: the restart throws away progress
the guide's loop could keep (`cli/_route_completion.py`). Prints each loss (the state, the line of the added rule, the legal actions) and writes
`OUT_DIR/completion.json`. Exit code 0 when there is none, 1 when there is one. R04 and R14 must pass (R14 since #619).

Never run on a PC: the plan of R04 takes about 10 minutes and 6 GB, R14's about 40 minutes and 9 GB. Run by `.github/scripts/heavy_dispatch.py`
(R14 with `--long`).
"""

import json
import sys
import time
from pathlib import Path

PRICES = "tests/fixtures/prices/routes-allflame-2026-10-31.json"


def main(argv: list[str]) -> int:
    from crafting_system.cli import _benchmark, _packed, load_route, make_plan
    from crafting_system.cli._report import describe_state
    from crafting_system.cli._route_completion import walked_losses
    from crafting_system.config import find_project_root
    from crafting_system.data import load_game_data
    from crafting_system.prices import load_price_file
    from crafting_system.targets import load_target

    began = time.perf_counter()

    def say(text: str) -> None:
        print(f"[{time.perf_counter() - began:7.1f}s] {text}", flush=True)

    _packed.PROGRESS = say
    bench = next(b for b in _benchmark.BENCHMARKS if b.id == argv[0])
    if bench.route is None or bench.completed is None:
        say(f"{bench.id} has no completed route")
        return 2
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    root = find_project_root()
    data = load_game_data()
    plan = make_plan(data, load_target(root / bench.target, data), load_price_file(root / PRICES))
    guide = load_route(root / bench.route, plan, data)
    completed = load_route(root / bench.completed, plan, data)
    found = walked_losses(plan, guide, completed, data)
    rows = [
        {"rule_line": loss.rule_line, "legal": list(loss.legal), "description": describe_state(plan, data, loss.state)}  # type: ignore[arg-type]
        for loss in found
    ]
    say(f"{bench.id}: {len(rows)} state(s) where a restart the guide does not have fires while a guide action is legal")
    for row in rows[:20]:
        say(f"    line {row['rule_line']}, legal {', '.join(row['legal'])}: {row['description']}")
    (out / "completion.json").write_text(json.dumps({"route": bench.id, "completed": bench.completed, "losses": rows}, indent=1), encoding="utf-8")
    return 1 if rows else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
