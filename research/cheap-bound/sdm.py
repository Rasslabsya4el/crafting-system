"""#1315, point 2: a status model built DIRECTLY over every offer of one reference target, by count. No planner code is changed.

    python sdm.py ROUTE OUT.json        (env LIMIT=seconds of building, default 1500; OFFERS=guide for the guide's labels and the restart only)

The key of the status model is the bound's key (`PatternKey`) without the junk: the counts and the protected tags of the ordinary mods are
dropped; flags, fractured mods, status, held, crafted and veiled slots stay (the note of #1310, section 2, last paragraph).

How a coarse key gets its rows. It holds REPRESENTATIVES: concrete states that some kernel produced and that have the key. An action is taken
at a representative with the abstraction's exact kernel (`Abstraction.kernel`), each successor pushed to its coarse key, and offered
  - as that exact kernel, when the bound's own rule says one member stands for the key whatever its junk (`Pattern.mode_of` is `ANY`: an
    erasing reroll that reads no junk, no lock held), or when the kernel has one successor (a certain move);
  - else ANGELIC: one certain row to each coarse key the kernel can reach, at the offer's cost (the least outcome is at most the mean).
A key is worked out at its first representative, and again at a later one that holds fewer or more ordinary mods than every one before.
NOT A PROOF: a member that is no representative could reach a coarse key that none of the representatives reaches. The test of the note
(#1310, section 5) is the measure of that: on the guide's offers the direct value must be at or under the merged one (run with OFFERS=guide
and compare with ka.py's row "without tags, counts").

The order. The model is worked out where its own cheapest policy goes (a tip costs nothing more: the planner's floor action at the least
cost), until the policy meets no tip: the start value is then the value of the whole direct model, though most keys were never worked out.
Stopped at LIMIT, the start value is still a value of the model with every tip free, so it is at most the complete one.
"""
import json, math, os, sys, time
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

T0 = time.perf_counter()
from crafting_system.abstraction import Abstraction, Goal
from crafting_system.abstraction._pattern import Mode, Pattern
from crafting_system.actions import NotApplicableError, OutOfScopeError
from crafting_system.cli import _benchmark, _route
from crafting_system.cli._inputs import load_target_prices
from crafting_system.config import find_project_root, load_config
from crafting_system.data import load_game_data
from crafting_system.planner import _offer_kinds as ok
from crafting_system.planner import _pattern_bound as pb
from crafting_system.planner import _plan as pp
from crafting_system.planner._offers import BuyStartItem
from crafting_system.prices import load_price_file
from crafting_system.solver import PackedBuilder, solve_packed
from crafting_system.targets import load_target

PRICES = "tests/fixtures/prices/routes-allflame-2026-07-31.json"
LIMIT = float(os.environ.get("LIMIT", "1500"))


class Captured(BaseException):
    pass


got = {}
real = pp.rounds_apply


def hook(data, target, priced, **kw):
    got.update(data=data, target=target, priced=tuple(priced))
    raise Captured


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
    stand_in = None
    try:
        pp.make_plan(data, target, prices, with_risk=False)
    except Captured:
        pass
    except Exception:  # no start price (R06): a stand-in of 1 Chaos, as #1276's seed.py
        stand_in = 1.0
        try:
            pp.make_plan(data, target, prices, with_risk=False, start_price=1.0)
        except Captured:
            pass
    target, priced = got["target"], got["priced"]
    goal = Goal.from_target(target)
    enabled = [p.offer.action for p in priced if (r := p.offer.action.reads(data)).junk or r.item_state]
    holds = bool(target.start_item.metamods(data) & pp.BLOCKING)
    ab = Abstraction(data, goal, target.base_id, target.item_level, enabled, metamods=holds, enchantment=target.start_item.enchantment, allow_inputs=True)
    restart = any(isinstance(p.offer.action, BuyStartItem) for p in priced)
    listing = pp.unopened_listing(data, target.start_item) if restart else None
    start = ab.compress(listing or target.start_item)
    offered = list(ok.merge_twins(data, target.start_item, priced)[0])
    if os.environ.get("OFFERS") == "guide":
        offered = [p for p in offered if p.label in guide or isinstance(p.offer.action, BuyStartItem)]
    acts = [(p.label, None if isinstance(p.offer.action, BuyStartItem) else p.offer.action, float(p.cost)) for p in offered]
    pattern = Pattern(ab, None, [a for _l, a, _c in acts if a is not None])
    cheapest = min(c for _l, _a, c in acts)
    print(f"{route_id}: offers {len(priced)}, after twins {len(acts)}, guide labels {len(guide)} ({sum(1 for g in guide if any(l == g for l, _a, _c in acts))} among the offers), setup {time.perf_counter() - T0:.0f} s", flush=True)

    index, keys, is_goal = {}, [], []  # coarse key -> number
    reps: list[list] = []  # per key: the representatives waiting to be worked out
    span: list[list[int] | None] = []  # per key: [fewest, most] ordinary mods among the representatives worked out; None for a tip
    exact_rows: list[dict] = []  # per key: pushed kernel -> (cost, label)
    angel_rows: list[dict] = []  # per key: successor key -> (cost, label)
    stats = Counter()
    memo = {}

    def coarse(state):
        pattern.note(state)
        key = pattern.key(state)
        junk = key.counts[0] + key.counts[1]
        ck = key._replace(counts=None, tags=None)
        i = index.get(ck)
        if i is None:
            i = index[ck] = len(keys)
            keys.append(ck)
            is_goal.append(False)
            reps.append([])
            span.append(None)
            exact_rows.append({})
            angel_rows.append({})
        if ab.is_goal(state):
            is_goal[i] = True
        s = span[i]
        if (s is None and not reps[i]) or (s is not None and (junk < s[0] or junk > s[1]) and all(j != junk for j, _k, _s in reps[i])):
            reps[i].append((junk, key, state))
        return i

    def work(i):
        waiting, reps[i] = reps[i], []
        for junk, key, state in waiting:
            s = span[i]
            span[i] = [junk, junk] if s is None else [min(s[0], junk), max(s[1], junk)]
            stats["representatives"] += 1
            for label, action, cost in acts:
                if action is None:
                    if i != 0:
                        row = ((0, 1),)
                        if row not in exact_rows[i] or exact_rows[i][row][0] > cost:
                            exact_rows[i][row] = (cost, label)
                    continue
                try:
                    kk = ab.kernel_key(state, action)
                    pushed = memo.get(kk)
                    if pushed is None:
                        stats["kernels"] += 1
                        acc = defaultdict(Fraction)
                        for successor, chance in ab.kernel(state, action).items():
                            acc[coarse(successor)] += chance
                        pushed = memo[kk] = tuple(sorted(acc.items()))
                    stats["pairs"] += 1
                except (NotApplicableError, OutOfScopeError, ValueError):
                    stats["refused"] += 1
                    continue
                if len(pushed) == 1 and pushed[0][0] == i:
                    continue
                try:
                    one = len(pushed) == 1 or pattern.mode_of(action, key) is Mode.ANY
                except Exception:
                    one = False
                if one:
                    stats["exact rows"] += 1
                    if pushed not in exact_rows[i] or exact_rows[i][pushed][0] > cost:
                        exact_rows[i][pushed] = (cost, label)
                else:
                    stats["angelic rows"] += 1
                    for s, _chance in pushed:
                        if s != i and (s not in angel_rows[i] or angel_rows[i][s][0] > cost):
                            angel_rows[i][s] = (cost, label)

    def solve():
        n = len(keys)
        b = PackedBuilder()
        tags = []  # action number -> (key, label, successors)
        for i in range(n):
            if span[i] is not None and not is_goal[i]:
                for pushed, (cost, label) in exact_rows[i].items():
                    weights = [c.numerator * (math.lcm(*(x.denominator for _s, x in pushed)) // c.denominator) for _s, c in pushed]
                    b.action(len(tags), cost, b.kernel([s for s, _c in pushed], weights))
                    tags.append((i, label, [s for s, _c in pushed]))
                for s, (cost, label) in angel_rows[i].items():
                    b.action(len(tags), cost, b.kernel([s], [1]))
                    tags.append((i, label, [s]))
            elif not is_goal[i]:
                b.action(len(tags), pb.FLOOR_COST, b.kernel([n], [1]))
                tags.append((i, None, []))
            b.close_state(is_goal[i])
        b.close_state(True)
        graph = b.build()
        solved = solve_packed(graph, progress=None, refuse_above=math.inf)
        chosen = {}
        for i in range(n):  # an action's number in the graph is the order it was given in: its place in `tags`
            a = int(solved.action[i])
            if a >= 0:
                chosen[i] = tags[a]
        seen, todo, tips, used = {0}, [0], [], Counter()
        while todo:
            i = todo.pop()
            if is_goal[i]:
                continue
            if span[i] is None or reps[i]:
                tips.append(i)
                if span[i] is None:
                    continue
            pick = chosen.get(i)
            if pick is None:
                continue
            used[pick[1]] += 1
            for s in pick[2]:
                if s not in seen:
                    seen.add(s)
                    todo.append(s)
        return float(solved.value[0]), tips, used, len(seen)

    coarse(start)
    assert index[keys[0]] == 0
    rounds, stopped = 0, None
    while True:
        rounds += 1
        value, tips, used, on_policy = solve()
        worked = sum(1 for s in span if s is not None)
        if rounds <= 3 or rounds % 25 == 0 or not tips:
            print(f"  round {rounds}: keys {len(keys)}, worked out {worked}, start value {value:.4f}, tips on the policy {len(tips)}, {time.perf_counter() - T0:.0f} s", flush=True)
        if not tips:
            break
        if time.perf_counter() - T0 > LIMIT:
            stopped = f"the limit of {LIMIT:.0f} s"
            break
        for i in tips:
            work(i)
            if time.perf_counter() - T0 > LIMIT:
                break
    worked = sum(1 for s in span if s is not None)
    on_plan = [g for g in guide if used.get(g)]
    result = {
        "route": route_id, "offers": len(priced), "after_twins": len(acts), "guide": guide, "guide_among_offers": [g for g in guide if any(l == g for l, _a, _c in acts)],
        "keys": len(keys), "worked_out": worked, "rounds": rounds, "stopped": stopped, "start_value": value, "seconds": round(time.perf_counter() - T0, 1),
        "load": os.getloadavg()[0], "policy_keys": on_policy, "policy_offers": dict(used.most_common()), "guide_on_policy": on_plan, "stats": dict(stats),
        "cheapest_offer": cheapest, "start_price_stand_in": stand_in, "offers_mode": os.environ.get("OFFERS", "all"),
    }
    Path(out).write_text(json.dumps(result, indent=1))
    print(f"RESULT {route_id} offers {len(acts)} ({result['offers_mode']}): coarse keys {len(keys)}, worked out {worked}, rounds {rounds}, stopped {stopped}, start value {value!r}, "
          f"{result['seconds']} s (load {result['load']:.1f}); kernels {stats['kernels']}, pairs {stats['pairs']}, exact rows {stats['exact rows']}, angelic rows {stats['angelic rows']}; "
          f"policy keys {on_policy}; guide's labels on the policy {len(on_plan)} of {len(guide)}: {on_plan}; policy uses: " + "; ".join(f"{l} x{k}" for l, k in used.most_common(15)), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
