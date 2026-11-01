"""Temporary exploration for ticket #331 (removed before the PR is final)."""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from abstraction_support import real_game_data  # noqa: E402

from crafting_system.cli import build_report, plan_with_starts, render_text  # noqa: E402
from crafting_system.prices import load_price_file  # noqa: E402
from crafting_system.targets import load_target  # noqa: E402

data = real_game_data()
prices = load_price_file(ROOT / "tests/fixtures/prices/vendor-v01-2026-11-01.json")
for name in sys.argv[1:]:
    target = load_target(ROOT / ".explore" / f"{name}.yaml", data)
    began = time.perf_counter()
    try:
        plan = plan_with_starts(data, target, prices, budget=None)
    except Exception as error:  # noqa: BLE001
        print(f"=== {name}: FAILED in {time.perf_counter() - began:.1f}s: {error}", flush=True)
        continue
    took = time.perf_counter() - began
    text = render_text(build_report(plan, data), target_name=name)
    print(f"=== {name}: {took:.1f}s (solve {plan.solve_seconds:.1f}s, risk {plan.risk_seconds:.1f}s)", flush=True)
    print("\n".join(text.splitlines()[:40]), flush=True)
