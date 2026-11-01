"""TEMPORARY probe for #66: how long R13 takes with each set of offered actions. Not part of the PR."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "tests")
from abstraction_support import real_game_data

from crafting_system.abstraction import Goal
from crafting_system.cli import make_plan
from crafting_system.cli._offers import offers_for
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

SETS = {
    "A": {"Orb of Transmutation", "Orb of Alteration", "Orb of Augmentation", "Regal Orb"},
    "B": {"Orb of Transmutation", "Orb of Alteration", "Orb of Augmentation", "Regal Orb", "Chaos Orb"},
    "C": {"Orb of Transmutation", "Orb of Alteration", "Orb of Augmentation", "Regal Orb", "Orb of Alchemy", "Orb of Scouring"},
    "D": {"Orb of Transmutation", "Orb of Alteration", "Orb of Augmentation", "Regal Orb", "Orb of Alchemy", "Orb of Scouring", "Chaos Orb"},
    "E": None,  # everything with a price except the essences
}
name = sys.argv[1]
out = Path(sys.argv[2])
data = real_game_data()
target = load_target(Path("examples/targets/r13-life-resist-belt.yaml"), data)
prices = load_price_file(Path("tests/fixtures/prices/routes-allflame-2026-10-31.json"))
chosen = offers_for(data, Goal.from_target(target), target.base_id, target.start_item).offers
keep = SETS[name]
offers = [
    o for o in chosen
    if (keep is None and "Essence" not in o.label) or (keep is not None and (o.label in keep or o.label.startswith("Bench craft") or o.label == "Remove Crafted Mods"))
]
began = time.perf_counter()
plan = make_plan(data, target, prices, offers=offers)
result = {
    "set": name, "offers": sorted(p.label for p in plan.offers), "dropped": [d.label for d in plan.dropped],
    "states": len(plan.policy), "mean": plan.risk.mean.value, "p90": plan.risk.p90.value,
    "solve_seconds": plan.solve_seconds, "risk_seconds": plan.risk_seconds, "total_seconds": time.perf_counter() - began,
}
out.mkdir(parents=True, exist_ok=True)
(out / f"probe_{name}.json").write_text(json.dumps(result, indent=1))
print(json.dumps(result, indent=1))
