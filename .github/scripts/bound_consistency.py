"""How far a route's sound lower bound sits above the least lower bound of its offers, key by key (ticket #539, the guard of `planner/_envelope.py`).

    python .github/scripts/bound_consistency.py --route r05|r13|r14|r04 [--out DIR]

The envelope search refuses a bound at a state when its value is above the least `la` of the offers there by more than `CONSISTENCY_LIMIT`
(and, in absolute terms, `CONSISTENCY_LIMIT` of the root's bound). A sound bound solves the model's own equation, so it is at most that least `la` at
every key up to the certified error of its solve. This script builds the bound of a route the way `make_plan(solver="envelope")` does and prints, over all
keys, the largest excess `value / least la - 1` and the number of keys over the limit: any key over it would be a state the guard refuses on a sound bound.
It walks nothing and expands nothing; the build is 12 to 258 s (docs/adr/0063, #497).

Never run on a PC for R04 and R14. Run by `.github/scripts/heavy_dispatch.py` (docs/ci.md).
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for extra in (ROOT / "research" / "312", ROOT / "research" / "376", ROOT / "src"):
    if str(extra) not in sys.path:
        sys.path.append(str(extra))

import exact_classes as E  # noqa: E402

from crafting_system.planner._envelope import CONSISTENCY_LIMIT  # noqa: E402
from crafting_system.planner._envelope_plan import CraftingProblem  # noqa: E402
from crafting_system.planner._pattern_bound import pattern_lower_bound  # noqa: E402

TARGETS = {
    "r04": "r04-penetrating-quiver",
    "r05": "r05-strength-ring",
    "r13": "r13-life-resist-belt",
    "r14": "r14-hunter-bow",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", required=True, choices=sorted(TARGETS))
    parser.add_argument("--out")
    args = parser.parse_args()
    began = time.perf_counter()
    path = ROOT / "examples" / "targets" / f"{TARGETS[args.route]}.yaml"
    _, _, _, abstraction, start, priced, _ = E.build_model(path, "twins", True, False)
    bound = pattern_lower_bound(abstraction, start, priced)
    problem = CraftingProblem(abstraction, start, priced, bound)
    excess = []
    for key, offered in enumerate(problem.lowest):
        if not offered:
            continue
        least = min(offered.values())
        value = float(problem.values[key])
        over = value - least
        excess.append((over / least if least > 0 else (0.0 if over <= 0 else float("inf")), over, key, least))
    excess.sort(reverse=True)
    root = float(problem.values[0])
    refused = [e for e in excess if e[1] > CONSISTENCY_LIMIT * (e[3] + root)]  # the test of `Search._consistent`
    result = {
        "route": args.route,
        "keys": len(problem.lowest),
        "keys_with_offers": len(excess),
        "largest_excess": excess[0][0] if excess else None,
        "largest_excess_absolute": excess[0][1] if excess else None,
        "keys_the_guard_would_refuse": len(refused),
        "error_bound": bound.error_bound,
        "root_bound": root,
        "seconds": round(time.perf_counter() - began, 1),
    }
    print(json.dumps(result, indent=1), flush=True)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{args.route}.bound_consistency.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    if refused:
        sys.exit(1)


if __name__ == "__main__":
    main()
