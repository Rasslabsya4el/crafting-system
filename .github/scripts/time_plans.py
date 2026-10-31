"""Time `make_plan` on the benchmark routes, one route per runner (ticket #118; run by the `Run a command` workflow).

    python .github/scripts/time_plans.py --routes r11,r10,r05,r08 --part 1/4 --out $OUT_DIR [--fossils]

`--part I/N` takes the I-th of N slices of the route list (RUNNER_INDEX / RUNNER_COUNT). Routes: r11, r10, r05 (the
examples), r08 and r09 (boots written below, empty rare, Sorcerer Boots / Leatherscale-class boots at item level 86). With
`--fossils` r08 and r09 are planned with every fossil set offered, priced with MADE-UP prices (no price source has
fossils or resonators yet), so no fossil set is expected to win: it times the pruning, not a fossil plan. The script
writes `<route>.json` (seconds, mean, states, offers, pruning numbers if the code has them) and prints it.
"""

import argparse
import hashlib
import json
import os
import platform
import time
from pathlib import Path

from crafting_system.abstraction import Goal
from crafting_system.actions import kinds
from crafting_system.cli import make_plan
from crafting_system.cli._offers import offer_of, offers_for
from crafting_system.data import load_game_data
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
EXAMPLES = {"r11": "r11-reservation-helmet", "r10": "r10-fractured-boots", "r05": "r05-strength-ring"}
R08 = """base: Sorcerer Boots
item_level: 86
influence: []
requirements:
  - family: DefencesPercent
    min_tier: 3
    not_crafted: true
  - family: MovementVelocity
    min_tier: 1
start_item:
  rarity: rare
  mods: []
"""
R09 = """base: Metadata/Items/Armours/Boots/BootsAtlas1
item_level: 86
influence: []
requirements:
  - family: IncreasedLife
    min_tier: 3
    not_crafted: true
  - family: MovementVelocity
    min_tier: 1
  - at_least: 1
    of:
      - family: FireResistance
      - family: ColdResistance
      - family: LightningResistance
start_item:
  rarity: rare
  mods: []
"""


def made_up_prices(data, out: Path) -> Path:
    """The fixture prices plus a deterministic made-up price for every fossil and resonator."""
    document = json.loads(PRICES.read_text(encoding="utf-8"))
    for record in data.fossils.values():
        if record.name:
            share = int(hashlib.sha256(record.name.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
            document["prices"][record.name] = {"chaos": round(0.6 + 11.4 * share, 2), "source": "made-up (timing only)"}
    for name, cost in {"Primitive": 0.5, "Potent": 1.6, "Powerful": 4.0, "Prime": 12.0}.items():
        document["prices"][f"{name} Chaotic Resonator"] = {"chaos": cost, "source": "made-up (timing only)"}
    path = out / "prices-with-fossils.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--routes", default="r11,r10,r05,r08")
    parser.add_argument("--part", default="1/1")
    parser.add_argument("--out", required=True)
    parser.add_argument("--fossils", action="store_true", help="offer every fossil set on r08 and r09")
    arguments = parser.parse_args()
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    index, count = (int(piece) for piece in arguments.part.split("/"))
    routes = arguments.routes.split(",")[index - 1 :: count]
    data = load_game_data()
    for route in routes:
        if route in EXAMPLES:
            path, prices = ROOT / "examples" / "targets" / f"{EXAMPLES[route]}.yaml", PRICES
        else:
            path = out / f"{route}.yaml"
            path.write_text(R08 if route == "r08" else R09, encoding="utf-8")
            prices = made_up_prices(data, out) if arguments.fossils else PRICES
        target = load_target(path, data)
        offers = None
        if arguments.fossils and route in ("r08", "r09"):
            base = offers_for(data, Goal.from_target(target), target.base_id, target.start_item).offers
            fossil_kind = next(kind for kind in kinds() if kind.name == "fossil-set")
            fossils = [offer_of(a, a.label(data), data, target.start_item) for a in fossil_kind.members(data, target.start_item)]
            offers = [*base, *fossils]
        began = time.perf_counter()
        plan = make_plan(data, target, load_price_file(prices), offers=offers)
        seconds = time.perf_counter() - began
        pruned = getattr(plan, "pruned", None)
        result = {
            "route": route,
            "fossils": bool(offers),
            "seconds": round(seconds, 1),
            "solve_seconds": round(plan.solve_seconds, 1),
            "mean_remaining": plan.mean_remaining,
            "states": len(plan.solution.values),
            "offers": len(plan.offers),
            "machine": {"system": platform.platform(), "cpus": os.cpu_count(), "python": platform.python_version()},
        }
        if pruned is not None:
            result["pruning"] = {
                "twins": len(pruned.twins), "bounded": len(pruned.bounded), "rounds": pruned.rounds, "rho": pruned.rho,
                "j_max": pruned.j_max, "offers_in_final_model": len(pruned.used), "fell_back": pruned.fell_back,
                "why": pruned.why, "phases": [[name, round(spent, 1)] for name, spent in pruned.phases],
            }
        (out / f"{route}{'-fossils' if offers else ''}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
