"""Throwaway (not for main): write the route page of one benchmark route into OUT_DIR, as tests/test_cli_routes_real.py does."""

import gzip
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
from abstraction_support import real_game_data  # noqa: E402

from crafting_system.cli import build_report, evaluate_route, load_route, make_plan, plan_with_starts  # noqa: E402
from crafting_system.cli._route_view import write_route_page  # noqa: E402
from crafting_system.prices import load_buy_spec, load_price_file  # noqa: E402
from crafting_system.targets import load_target  # noqa: E402

STEMS = {
    "R04": "r04-penetrating-quiver", "R05": "r05-strength-ring", "R08": "r08-energy-shield-boots", "R09": "r09-life-boots",
    "R10": "r10-fractured-boots", "R11": "r11-reservation-helmet", "R12": "r12-lightning-amulet", "R13": "r13-life-resist-belt",
    "R14": "r14-hunter-bow", "V01": "v01-minion-helmet",
}
BUY = {"R04": "r04-start-quiver", "R05": "r05-start-ring", "R08": "r08-start-boots", "R09": "r09-start-boots", "R10": "r10-start-boots",
       "R11": "r11-start-helmet", "R12": "r12-start-amulet", "R14": "r14-start-bow"}
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"
TRADE_STATS = ROOT / "tests" / "fixtures" / "trade" / "recorded" / "stats_full.json.gz"


def main(route_id: str, out: Path) -> None:
    stem = STEMS[route_id]
    log = out / f"{route_id}.log"
    began = time.perf_counter()
    try:
        data = real_game_data()
        target = load_target(ROOT / "examples" / "targets" / f"{stem}.yaml", data)
        prices = load_price_file(target.price_file if target.price_file else PRICES)
        route_file = ROOT / "examples" / "routes" / f"{stem}.yaml"
        plan = make_plan(data, target, prices) if route_file.is_file() else plan_with_starts(data, target, prices)
        solved = time.perf_counter() - began
        route = load_route(route_file, plan, data) if route_file.is_file() else None
        given = evaluate_route(plan, route, data) if route is not None else None
        cache = out / "trade-cache"
        (cache / "trade").mkdir(parents=True, exist_ok=True)
        (cache / "trade" / "stats.json").write_bytes(gzip.decompress(TRADE_STATS.read_bytes()))
        spec = load_buy_spec(ROOT / "examples" / "buy" / f"{BUY[route_id]}.yaml") if route_id in BUY else None
        write_route_page(out / f"{route_id}-{stem}.route.html", build_report(plan, data), data, route=route, given=given,
                         buy_spec=spec, cache_dir=cache, target_name=f"{stem}.yaml")
        log.write_text(f"ok solve {solved:.0f}s total {time.perf_counter() - began:.0f}s\n", encoding="utf-8")
    except Exception:
        log.write_text(f"error after {time.perf_counter() - began:.0f}s\n{traceback.format_exc()}", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
