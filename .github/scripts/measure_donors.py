"""Measure the lazy offer loop on the R25-sized recombinator worlds of ADR-0062 (ticket #212; run by the `Run a command` workflow).

    python .github/scripts/measure_donors.py {class|raw|pool6|pool8|all-class} [--out DIR]

One line of JSON per case, printed and written to `<out>/<case>.json`: the rounds (product states, acquisition processes,
pairs offered and added in each), the pairs of the full model, the value at the empty item, the certified error bound and the
seconds of the whole run (the exploration of the model, which builds every recombination kernel the lower bound needs,
included). It prints what the code does and asserts nothing; the tests hold the class case
to the numbers of the ADR (`tests/test_donor_lazy_r25.py`).

* `class`: three target prefixes and nine junk prefixes in three weight classes, junk told apart by weight (63 item states).
* `raw`: the same with every junk mod named (299 item states, the lazy run is minutes).
* `pool6`, `pool8`: raw worlds with fewer junk mods (ADR-0062 "smaller pools").
* `all-class`: the class world with every donor offered up front (`seed` everything), the product the loop avoids building
  (3,969 states; ADR-0062 solved it in 814 s on a runner).

Never run it on a PC: use `.github/scripts/heavy_dispatch.py` (docs/ci.md).
"""

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))

from donor_world_support import R25World  # noqa: E402

from crafting_system.solver import solve_lazily  # noqa: E402

CASES = {
    "class": dict(raw=False),
    "raw": dict(raw=True),
    "pool6": dict(raw=True, junk=((500, 1), (1000, 1), (1500, 1))),
    "pool8": dict(raw=True, junk=((500, 1), (1000, 2), (1500, 2))),
    "all-class": dict(raw=False),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=sorted(CASES))
    parser.add_argument("--out")
    args = parser.parse_args()
    world = R25World(**CASES[args.case])
    everything = args.case == "all-class"
    began = time.perf_counter()
    result = solve_lazily(world.full_model(), world.blank, seed=(lambda state, action: True) if everything else world.isolated_feeder)
    seconds = time.perf_counter() - began
    line = {
        "case": args.case,
        "item_states": len(world.states()),
        "pairs": result.pairs,
        "offered_pairs": result.offered_pairs,
        "rounds": [dataclasses.asdict(round) for round in result.rounds],
        "product_states": len(result.values),
        "value": result.value,
        "error_bound": result.error_bound,
        "seconds": seconds,
    }
    text = json.dumps(line)
    print(text, flush=True)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{args.case}.json").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
