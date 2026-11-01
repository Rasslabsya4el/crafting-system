"""The small checks behind docs/research/2026-11-01-buying-any-state.md (ticket #337).

    python docs/research/2026-11-01-buying-any-state-checks.py ninja BASETYPE.json   # poe.ninja BaseType overview, saved
    python docs/research/2026-11-01-buying-any-state-checks.py pools                 # equal-pool item-level groups of R05, R08, R13
    python docs/research/2026-11-01-buying-any-state-checks.py maxlevel              # highest required level of any spawnable mod
    python docs/research/2026-11-01-buying-any-state-checks.py leaves                # candidate fractured mods per target
    python docs/research/2026-11-01-buying-any-state-checks.py probe                 # 7 anonymous trade searches, totals only

`pools`, `maxlevel` and `leaves` need the pinned game data (`CRAFTING_CACHE_DIR`). `probe` is the only one that
touches the trade site: seven searches (no fetch), anonymous, through the repo's own client (headers read, budget 7), run
by hand once on 2026-11-01 with the owner's leave for "a handful" of requests; it never sends a session cookie. Do not
schedule it. The Allflame numbers in the note come from one run of each.
"""

import collections
import gzip
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {"R05": "r05-strength-ring", "R08": "r08-energy-shield-boots", "R13": "r13-life-resist-belt"}


def ninja(path: str) -> None:
    lines = json.load(open(path, encoding="utf-8"))["lines"]
    print(len(lines), "rows; fields", sorted(lines[0]))
    print("levelRequired", sorted(collections.Counter(row["levelRequired"] for row in lines).items()))
    print("variants", collections.Counter(row.get("variant") for row in lines).most_common(8))
    thick = [row for row in lines if row["count"] >= 5]
    print("count >= 5:", len(thick), "plain", sum(1 for row in thick if not row.get("variant")))
    blob = " ".join(json.dumps({k: v for k, v in row.items() if k != "sparkLine"}).lower() for row in lines)
    print("mentions fractured / synthesised:", "fractur" in blob, "synth" in blob)
    for name in ("Amethyst Ring", "Sorcerer Boots", "Leather Belt"):
        rows = sorted((r for r in lines if r["name"] == name), key=lambda r: (r["levelRequired"], r.get("variant") or ""))
        for row in rows:
            print(f"  {name:15} {row['levelRequired']} {str(row.get('variant')):18} {row['chaosValue']:>9} count {row['count']:>4} listings {row['listingCount']}")


def _data():
    sys.path.insert(0, str(ROOT / "src"))
    from crafting_system.data import load_game_data

    return load_game_data()


def pools() -> None:
    data = _data()
    from crafting_system.actions import build_pool
    from crafting_system.items import Item, Rarity
    from crafting_system.targets import load_target

    for route, stem in TARGETS.items():
        target = load_target(ROOT / "examples" / "targets" / f"{stem}.yaml", data)
        seen: dict = {}
        for ilvl in range(70, 101):
            item = Item.build(data, base_id=target.base_id, item_level=ilvl, rarity=Rarity.RARE)
            seen.setdefault(frozenset(e.mod.id for fam in build_pool(data, item) for e in fam.mods), []).append(ilvl)
        print(route, [f"{g[0]}-{g[-1]}" if len(g) > 1 else str(g[0]) for g in seen.values()])


def maxlevel() -> None:
    data = _data()
    levels = collections.Counter()
    above = collections.Counter()
    for mod in data.mods.values():
        if mod.spawn_weights and any(getattr(w, "weight", 0) > 0 for w in mod.spawn_weights):
            if mod.domain in ("item", "flask", "crafted", "misc"):
                levels[mod.required_level] += 1
            elif mod.required_level > 86:
                above[mod.domain] += 1
    print("top required levels of item-domain mods:", sorted(levels.items())[-6:])
    print("mods above 86 by domain:", dict(above))


def leaves() -> None:
    data = _data()
    from crafting_system.abstraction import Goal
    from crafting_system.actions import build_pool
    from crafting_system.items import Item, Rarity
    from crafting_system.prices.trade_stats import normalize_text
    from crafting_system.targets import load_target

    for route, stem in TARGETS.items():
        target = load_target(ROOT / "examples" / "targets" / f"{stem}.yaml", data)
        pool = {e.mod.id for fam in build_pool(data, Item.build(data, base_id=target.base_id, item_level=target.item_level, rarity=Rarity.RARE)) for e in fam.mods}
        texts = set()
        for leaf in Goal.from_target(target).leaves:
            texts |= {data.mods[m].text for m in leaf.mod_ids if m in pool and m in data.mods}
        families = {normalize_text(text) for text in texts}
        print(route, "distinct stat texts among spawnable leaf mods:", len(texts), "; one trade stat each (numbers as #):", len(families), sorted(families))


def probe() -> None:
    """Allflame, 2026-11-01: 16 searches (totals only) in three groups; the note also used 3 more searches and 4 fetches
    of the same kind, listed in section 2.1 (23 requests in all)."""
    sys.path.insert(0, str(ROOT / "src"))
    from crafting_system.prices.trade_http import RateLimiter, RequestBudget, TradeClient, package_version, urllib_transport, user_agent
    from crafting_system.prices.trade_query import BuyMod, BuySpec, build_query
    from crafting_system.prices.trade_stats import parse_trade_stats, resolve_buy_mod

    stats = parse_trade_stats(json.load(gzip.open(ROOT / "tests" / "fixtures" / "trade" / "recorded" / "stats_full.json.gz"))["stats"])
    client = TradeClient(urllib_transport(), user_agent(package_version()), RateLimiter(time.monotonic, time.sleep), RequestBudget(16), None)

    def belt(rarity, mods, level):
        return BuySpec("probe", rarity=rarity, mods=tuple(mods), base_type="Leather Belt", item_level_min=level)

    # Belt tiers (pinned data): Life tier 1 is +(130-144), tier 2 +(115-129); Fire and Cold Resistance tier 1 +(46-48), tier 2 +(42-45).
    life2, fire2, cold2 = BuyMod("+# to maximum Life", 115), BuyMod("+#% to Fire Resistance", 42), BuyMod("+#% to Cold Resistance", 42)
    life1, fire1, cold1 = BuyMod("+# to maximum Life", 130), BuyMod("+#% to Fire Resistance", 46), BuyMod("+#% to Cold Resistance", 46)
    frac1 = BuyMod("+# to maximum Life", 130, fractured=True)
    probes = [
        ("A tier 2 or better, ilvl 86+: rare life", belt("rare", [life2], 86)),
        ("A rare life + fire", belt("rare", [life2, fire2], 86)),
        ("A rare life + fire + cold", belt("rare", [life2, fire2, cold2], 86)),
        ("A magic life", belt("magic", [life2], 86)),
        ("A rare fractured life", belt("rare", [BuyMod("+# to maximum Life", 115, fractured=True)], 86)),
        ("A normal, no mods", belt("normal", [], 86)),
        ("B tier 1, ilvl 86+: rare life", belt("rare", [life1], 86)),
        ("B rare life + fire", belt("rare", [life1, fire1], 86)),
        ("B rare life + fire + cold", belt("rare", [life1, fire1, cold1], 86)),
        ("B magic life", belt("magic", [life1], 86)),
        ("B rare fractured life", belt("rare", [frac1], 86)),
        ("C tier 1, ilvl 84+: rare life + fire", belt("rare", [life1, fire1], 84)),
        ("C rare life + fire + cold", belt("rare", [life1, fire1, cold1], 84)),
        ("C rare fractured life", belt("rare", [frac1], 84)),
        ("C normal, no mods", belt("normal", [], 84)),
        ("ring rare ilvl 75+: fractured all attributes 13+ and life 100+", BuySpec("probe", rarity="rare", category="accessory.ring", item_level_min=75, mods=(BuyMod("+# to all Attributes", 13, fractured=True), BuyMod("+# to maximum Life", 100)))),
    ]
    for label, spec in probes:
        body = build_query(spec, [resolve_buy_mod(m, [], stats) for m in spec.mods]).body()
        answer = client.search("Allflame", body)
        print(json.dumps({"probe": label, "total": answer.get("total")}), flush=True)
        time.sleep(4)


if __name__ == "__main__":
    {"ninja": lambda: ninja(sys.argv[2]), "pools": pools, "maxlevel": maxlevel, "leaves": leaves, "probe": probe}[sys.argv[1]]()
