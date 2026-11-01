"""Does the item level of the bought base change the plan? R05, R08 and R13 planned at several item levels (ticket #337).

Run by the `Run a command` workflow through `.github/scripts/heavy_dispatch.py`, never on a PC:

    python docs/research/2026-11-01-buying-any-state-ilvl.py --routes r13,r08,r05 --part $RUNNER_INDEX/$RUNNER_COUNT --out $OUT_DIR

For each route and item level the target file is copied with its `item_level:` line changed (the start item takes the
level), the plan is made as `make_plan` makes it, and the file records the mean cost from the start item (`v_start`,
the start price not included) and the start price used. Start prices are poe.ninja's plain-base rows of 2026-11-01
(Leather Belt 84: 1.7, 85: 1.0, 86: 10.0; Sorcerer Boots 84: 1.0, 85: 5.3, 86: 7.4, plus the 0.02716 Orb of Alchemy that
makes the base rare; R05's start item is the fractured ring of the price file, 2.6, for every level). A level at which the target cannot be
met is recorded as such.
"""

import argparse
import json
import os
import re
import time
from pathlib import Path

from crafting_system.cli import make_plan
from crafting_system.data import load_game_data
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
ALCHEMY = 0.02716
ROUTES = {
    "r13": ("r13-life-resist-belt", {84: 1.7, 85: 1.0, 86: 10.0}),
    "r08": ("r08-energy-shield-boots", {84: 1.0 + ALCHEMY, 85: 5.3 + ALCHEMY, 86: 7.4 + ALCHEMY}),
    "r05": ("r05-strength-ring", {75: 2.6, 82: 2.6, 84: 2.6, 86: 2.6}),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--routes", default="r13,r08,r05")
    parser.add_argument("--part", default="1/1")
    parser.add_argument("--out", default=os.environ.get("OUT_DIR", "."))
    args = parser.parse_args()
    index, count = (int(x) for x in args.part.split("/"))
    routes = [r for i, r in enumerate(args.routes.split(",")) if i % count == index - 1]
    data = load_game_data()
    prices = load_price_file(PRICES)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for route in routes:
        stem, by_level = ROUTES[route]
        text = (ROOT / "examples" / "targets" / f"{stem}.yaml").read_text(encoding="utf-8")
        rows = []
        for level, price in by_level.items():
            changed, n = re.subn(r"(?m)^item_level:\s*\d+", f"item_level: {level}", text)
            assert n == 1, "the target has no item_level line"
            path = out / f"{route}-ilvl{level}.yaml"
            path.write_text(changed, encoding="utf-8")
            began = time.perf_counter()
            try:
                target = load_target(path, data)
                plan = make_plan(data, target, prices, start_price=price)
                row = {"item_level": level, "start_price": price, "v_start": plan.solution.values[plan.start],
                       "states": len(plan.solution.values), "offers": len(plan.offers)}
            except Exception as error:  # a level at which the target cannot be met
                row = {"item_level": level, "start_price": price, "error": f"{type(error).__name__}: {error}"[:300]}
            row["seconds"] = round(time.perf_counter() - began, 1)
            rows.append(row)
            print(json.dumps(row), flush=True)
        (out / f"{route}.json").write_text(json.dumps({"route": route, "rows": rows}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
