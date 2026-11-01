"""Count the reachable states of a target's exact graph, with progress (ticket #70; run by the `Run a command` workflow).

    python .github/scripts/count_states.py TARGET.yaml [--drop LABEL,LABEL] [--limit N] [--seconds S] [--out DIR]

Breadth-first from the start state over every offer of the plan and `restart`, the same graph the exact solver walks.
Every 30 seconds it prints `states found, states expanded, kernels, resident memory`; at the end (the graph is
finished, the state limit or the time limit is reached) it prints the same and writes `<target>.count.json`. `--drop`
leaves offers out by label (to see what a smaller list of actions would cost). Never run it on a PC: the graphs are large.
"""

import argparse
import json
import resource
import time
from pathlib import Path

from crafting_system.abstraction import Abstraction, Goal
from crafting_system.cli._offers import RESTART, BuyStartItem, Offer, PricedOffer, offers_for, price_offers, usable_actions
from crafting_system.cli._plan import offer_action, resolve_start_price
from crafting_system.data import load_game_data
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--drop", default="", help="offer labels to leave out, separated by commas")
    parser.add_argument("--limit", type=int, default=5_000_000)
    parser.add_argument("--seconds", type=float, default=19_000)
    parser.add_argument("--out")
    args = parser.parse_args()

    data = load_game_data()
    path = Path(args.target)
    target = load_target(path, data)
    prices = load_price_file(PRICES)
    chosen = offers_for(data, Goal.from_target(target), target.base_id, target.start_item, target.actions)
    priced, _ = price_offers(chosen.offers, prices)
    drop = {label.strip() for label in args.drop.split(",") if label.strip()}
    priced = tuple(p for p in priced if p.label not in drop)
    kept = usable_actions(data, target.start_item, [p.offer.action for p in priced])
    priced = tuple(p for p in priced if p.offer.action in kept)
    start_price = resolve_start_price(target, prices, None)
    if start_price.chaos > 0:
        restart = Offer(RESTART, BuyStartItem(target.start_item), {start_price.name or "start item": 1}, shares=False)
        priced = (*priced, PricedOffer(restart, start_price.chaos, ()))
    enabled = [p.offer.action for p in priced if p.offer.action.reads(data).junk]
    goal = Goal.from_target(target)
    abstraction = Abstraction(data, goal, target.base_id, target.item_level, enabled)
    start = abstraction.compress(target.start_item)
    print("offers:", ", ".join(p.label for p in priced), flush=True)

    began = time.perf_counter()
    seen = {start}
    order = [start]
    transitions = 0
    last = began
    index = 0
    reason = "finished"
    while index < len(order):
        state = order[index]
        index += 1
        if not abstraction.is_goal(state):
            for p in priced:
                try:
                    action = offer_action(abstraction, p, state, start)
                except Exception:  # the game refuses the action here
                    continue
                transitions += len(action.outcomes)
                for outcome in action.outcomes:
                    if outcome.weight > 0 and outcome.state not in seen:
                        seen.add(outcome.state)
                        order.append(outcome.state)
        now = time.perf_counter()
        if now - last >= 30:
            last = now
            print(f"{now - began:7.0f}s found {len(seen):>9,} expanded {index:>9,} transitions {transitions:>11,} rss {rss_mb():,.0f} MB", flush=True)
        if len(seen) >= args.limit:
            reason = "state limit"
            break
        if now - began >= args.seconds:
            reason = "time limit"
            break
    summary = {
        "target": path.name, "dropped": sorted(drop), "result": reason, "states_found": len(seen), "states_expanded": index,
        "transitions": transitions, "seconds": time.perf_counter() - began, "rss_mb": rss_mb(),
        "offers": [p.label for p in priced],
    }
    print(json.dumps(summary), flush=True)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{path.stem}.count{'-' + '_'.join(sorted(drop)) if drop else ''}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
