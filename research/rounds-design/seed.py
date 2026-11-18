"""#1276: a counted, search-free test of a seed rule on one reference target (no search runs; no repo file changed).

    python seed.py ROUTE OUT.json

It captures the priced offers the planner would search (hook on `_plan.rounds_apply`, which every plan passes before any search or donor),
builds the offers' floors (`OfferFloors`: kinds and pbars from what actions declare) and, for every necessary goal leaf that is open at the
start, each offer's chance of passing THAT leaf alone in one use (the pool bound `reach_bound` / `add_bound`, the same the floors use; a craft
or a veiled choice 1 when a mod it names passes the leaf), read at the bare item of every shape the floors know (the largest is taken).
Then it writes, per leaf, the offers ranked by cost / chance, and for each label of the guide's route: its kind, whether it provides a leaf
and at what rank, or that it provides none (a tool).
"""
import json, sys, time
from fractions import Fraction
from pathlib import Path

T0 = time.perf_counter()
from crafting_system.cli import _benchmark, _route
from crafting_system.cli._inputs import load_target_prices
from crafting_system.config import find_project_root, load_config
from crafting_system.data import load_game_data
from crafting_system.prices import load_price_file
from crafting_system.targets import load_target
from crafting_system.planner import _plan as pp
from crafting_system.planner import _offer_kinds as ok
from crafting_system.planner._offer_floor import OfferFloors
from crafting_system.planner._offers import BuyStartItem
from crafting_system.abstraction import Abstraction, add_bound, declared_add_bound, reach_bound
from crafting_system.abstraction import Goal
from crafting_system.actions import NotApplicableError, OutOfScopeError

PRICES = "tests/fixtures/prices/routes-allflame-2026-07-31.json"


class Captured(BaseException):
    pass


got = {}


def hook(data, target, priced, **kw):
    got.update(data=data, target=target, priced=tuple(priced), applies=real(data, target, priced, **kw))
    raise Captured


from crafting_system.planner import _offer_floor as _of
_of.through_listing = lambda *a, **k: None  # the exact draw of an unopened listing (R20: minutes) only sets the restart's pbar, which this report does not read
real = pp.rounds_apply
pp.rounds_apply = hook


def main(route_id, out):
    bench = next(b for b in _benchmark.BENCHMARKS if b.id == route_id)
    root = find_project_root()
    config = load_config(None)
    data = load_game_data(cache_dir=config.cache_dir)
    target = load_target(root / bench.target, data)
    own = _benchmark.reads_own_prices(bench, root)
    prices = load_target_prices(target.price_file, config) if own else load_price_file(root / PRICES)
    guide = []
    for path in (bench.route, bench.completed):
        if path:
            guide += [label for label in _route.route_actions(root / path) if label not in guide]
    start_price = None
    try:
        pp.make_plan(data, target, prices, with_risk=False)
    except Captured:
        pass
    except Exception as error:  # R06: no start price; a stand-in of 1 Chaos, as the audit did
        start_price = 1.0
        try:
            pp.make_plan(data, target, prices, with_risk=False, start_price=1.0)
        except Captured:
            pass
    target, priced = got["target"], got["priced"]
    goal = Goal.from_target(target)
    enabled = [p.offer.action for p in priced if (r := p.offer.action.reads(data)).junk or r.item_state]
    holds = bool(target.start_item.metamods(data) & pp.BLOCKING)
    ab = Abstraction(data, goal, target.base_id, target.item_level, enabled, metamods=holds, enchantment=target.start_item.enchantment, allow_inputs=True)
    listing = pp.unopened_listing(data, target.start_item) if any(isinstance(p.offer.action, BuyStartItem) for p in priced) else None
    start = ab.compress(listing or target.start_item)
    offered = tuple(ok.merge_twins(data, target.start_item, priced)[0])
    t = time.perf_counter()
    floors = OfferFloors(ab, start, offered, target.start_item)
    floors_s = time.perf_counter() - t
    shape = ab.compress(target.start_item) if start.flags.unopened else start
    necessary = ok.necessary_leaves(goal)
    status = shape.status if hasattr(shape, "status") else None
    open_leaves = [i for i in range(len(goal.leaves)) if not _passing(ab, shape, i)]  # every leaf, necessary or one of a k-of-n
    labels = pp.leaf_labels(target)
    rows = []
    t = time.perf_counter()
    bulky = [e for e in floors.entries if (e.priced.offer.kind or '') == 'fossil-set']
    near = {e.index for e in sorted(bulky, key=lambda e: (e.ratio, e.index))[:30]}  # per-leaf chances of fossil sets: only the 30 of least declared cost / pbar and the guide's (each is one built outcome per leaf and shape)
    for entry in floors.entries:
        action = entry.priced.offer.action
        skip = (entry.priced.offer.kind or '') == 'fossil-set' and entry.index not in near and entry.priced.label not in guide
        offer = entry.priced.offer
        kind0, named = ok._kind_of(data, target.start_item, entry.priced)
        chances = {}
        for leaf in open_leaves:
            best = Fraction(0)
            unknown = False
            for view in floors.views:
                if skip:
                    unknown = True
                    break
                try:
                    if kind0 == ok.RESTART_KIND or kind0 == ok.REFUSED or kind0 == ok.IMPLICIT:
                        found = Fraction(0)
                    elif kind0 in ok.FINISHING:
                        made = bool(action.adds(data, view.item).crafted)
                        found = Fraction(1) if ok.finishes(goal.leaves[leaf], named, made) else Fraction(0)
                    elif kind0 == ok.ADD:
                        if action.added_draw(data, view.item) is not None:
                            found = declared_add_bound(ab, action, view.item, (leaf,))
                        else:
                            found = add_bound(ab, view.bare, action, (leaf,))
                    elif kind0 == ok.REROLL:
                        adds = action.adds(data, view.item)
                        if adds.fractures or adds.keeps_crafted or action.reads(data).needs_crafted:
                            found = None
                        else:
                            found = reach_bound(ab, view.bare, action, (leaf,))
                    else:
                        found = None
                except (NotApplicableError, OutOfScopeError, ValueError):
                    continue
                if found is None:
                    unknown = True
                elif found > best:
                    best = found
            chances[leaf] = (float(best), unknown)
        reads, adds = action.reads(data), action.adds(data, target.start_item)
        rows.append({
            "label": entry.priced.label, "kind": offer.kind or offer.label, "class": kind0, "floor_kind": entry.kind, "cost": entry.priced.cost,
            "pbar": float(entry.pbar), "chances": {str(k): v[0] for k, v in chances.items()}, "unknown": any(v[1] for v in chances.values()),
            "blocks": offer.blocks is not None, "names": (len(named) if kind0 in ok.FINISHING else None),
            "decl": {"fractures": bool(adds.fractures), "veils": bool(adds.veils), "imprints": bool(adds.imprints), "needs_veiled": bool(reads.needs_veiled),
                     "needs_crafted": bool(reads.needs_crafted), "junk": bool(reads.junk), "item_state": bool(reads.item_state), "draws": bool(adds.draws),
                     "restore": bool((m := action.imprint_move()) is not None and m.restore), "imprint": bool(m is not None and not m.restore),
                     "metamod": bool(pp.adds_metamod(data, action)) if not isinstance(action, BuyStartItem) else False},
        })
    result = {
        "route": route_id, "start_price_stand_in": start_price, "rounds_apply": got["applies"], "offers": len(priced), "after_twins": len(offered),
        "shapes": len(floors.views), "rho": floors.rho, "U": list(floors.chosen), "necessary": list(necessary), "open": open_leaves,
        "leaf_labels": {str(i): labels[i] if i < len(labels) else str(i) for i in open_leaves}, "guide": guide, "rows": rows,
        "seconds": {"floors": round(floors_s, 1), "chances": round(time.perf_counter() - t, 1), "all": round(time.perf_counter() - T0, 1)},
        "start_rarity": str(target.start_item.rarity),
    }
    Path(out).write_text(json.dumps(result, indent=1))
    print(route_id, "offers", len(priced), "after twins", len(offered), "open leaves", len(open_leaves), "U", len(floors.chosen), result["seconds"], flush=True)


def _passing(ab, shape, leaf):
    from crafting_system.abstraction import Status
    try:
        return shape.status[leaf] == Status.PASSING
    except Exception:
        return ab.status_of(shape)[leaf] == Status.PASSING


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
