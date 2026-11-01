"""State growth per extra imprint on the real models of the benchmark routes (ticket #218, ADR-0059).

    python research/218/growth.py TARGET.yaml [--limits 0,1,2,3] [--out DIR]

Walks the exact graph of a target (every priced offer and `restart`, as `.github/scripts/count_states.py` does), then counts
the states of shape A over it: an item state and the set of up to K compressed states an imprint was made at. The rules are
those of ADR-0034 as the prototype in `tests/imprint_prototype.py` has them: an imprint is made of a magic item that is not
corrupted or fractured (the Croaker; the rare Talisman of the Arachnid does not occur in these targets), a restore goes back to
a held state and uses the imprint up, an item that is fractured or corrupted holds no imprint, and at K held a new imprint
replaces one. The product is only counted: nothing is solved. Run it on GitHub (`docs/ci.md`), the graphs are large.
"""

import argparse
import json
import time
from pathlib import Path

from crafting_system.abstraction import Abstraction, Goal
from crafting_system.cli._offers import RESTART, BuyStartItem, Offer, PricedOffer, offers_for, price_offers, usable_actions
from crafting_system.cli._plan import offer_action, resolve_start_price
from crafting_system.data import load_game_data
from crafting_system.items import Rarity
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[2]
PRICES = ROOT / "tests" / "fixtures" / "prices" / "routes-allflame-2026-10-31.json"


def base_graph(target_path: Path):
    """`(abstraction, start, successors)`: the compressed states reachable from the start and, for each, the tuple of its offers' outcome states."""
    data = load_game_data()
    target = load_target(target_path, data)
    prices = load_price_file(PRICES)
    chosen = offers_for(data, Goal.from_target(target), target.base_id, target.start_item, target.actions)
    priced, _ = price_offers(chosen.offers, prices)
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
    successors = {}
    order = [start]
    while order:
        state = order.pop()
        if state in successors:
            continue
        rows = []
        if not abstraction.is_goal(state):
            for p in priced:
                try:
                    action = offer_action(abstraction, p, state, start)
                except Exception:  # the game refuses the action here
                    continue
                rows.append(tuple(o.state for o in action.outcomes if o.weight > 0))
        successors[state] = rows
        for row in rows:
            order.extend(t for t in row if t not in successors)
    return abstraction, start, successors


def imprintable(state) -> bool:
    return state.flags.rarity is Rarity.MAGIC and not state.flags.corrupted and not state.fractured


def restorable(state) -> bool:
    return not state.flags.corrupted and not state.fractured


def count_product(abstraction, start, successors, limit: int) -> dict:
    """States and transitions of the item-and-imprints graph with at most `limit` imprints held."""
    first = (start, frozenset())
    seen = {first}
    stack = [first]
    transitions = 0
    while stack:
        s, held = stack.pop()
        if abstraction.is_goal(s):
            continue
        targets = []
        for row in successors[s]:
            targets.extend((t, held if restorable(t) else frozenset()) for t in row)
        if limit and imprintable(s) and s not in held:
            if len(held) < limit:
                targets.append((s, held | {s}))
            else:
                targets.extend((s, (held - {h}) | {s}) for h in held)
        if restorable(s):
            targets.extend((h, held - {h}) for h in held if h != s)
        transitions += len(targets)
        for target in targets:
            if target not in seen:
                seen.add(target)
                stack.append(target)
    goals = sum(1 for s, _ in seen if abstraction.is_goal(s))
    held_sizes = {}
    for _, held in seen:
        held_sizes[len(held)] = held_sizes.get(len(held), 0) + 1
    return {"limit": limit, "states": len(seen) - goals, "goals": goals, "transitions": transitions, "by_held": dict(sorted(held_sizes.items()))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--limits", default="0,1,2,3")
    parser.add_argument("--out")
    args = parser.parse_args()
    path = Path(args.target)
    began = time.perf_counter()
    abstraction, start, successors = base_graph(path)
    magic = sum(1 for s in successors if imprintable(s))
    result = {"target": path.name, "base_states": sum(1 for s in successors if not abstraction.is_goal(s)), "imprintable_states": magic,
              "seconds_base": time.perf_counter() - began, "product": []}
    print(json.dumps({k: v for k, v in result.items() if k != "product"}), flush=True)
    for limit in (int(x) for x in args.limits.split(",")):
        began = time.perf_counter()
        row = count_product(abstraction, start, successors, limit)
        row["seconds"] = time.perf_counter() - began
        result["product"].append(row)
        print(json.dumps(row), flush=True)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{path.stem}.growth.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
