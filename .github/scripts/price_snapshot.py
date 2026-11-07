"""Make a price snapshot with provenance and depths (#616): the file the benchmark and the real-route tests read.

    python .github/scripts/price_snapshot.py --old tests/fixtures/prices/routes-allflame-2026-10-31.json \
        --out tests/fixtures/prices/routes-allflame-2026-11-07.json --cache .claude/scratch/616-cache

Anonymous only (no POESESSID, no login), within the trade site's rate limits (`prices.trade_http`), a few minutes of requests. Steps:

1. poe.ninja: every exchange overview (currency, fossils, resonators, essences, oils) with the units traded on the day, the
   stash overviews of the bases, then the fallback chain for the wanted names with no usable line (history, poe.watch,
   the previous league), each stamped with its provenance.
2. The trade site's bulk exchange for every wanted name that has no price or fewer than `--below` units behind it: the
   deeper of the two readings is the price, the other one is kept in its provenance (`prices.deepen`).
3. The start items of the old file that were priced on the trade site: each stored search is asked again today, and the
   exact item of the target is asked too; a price taken for a wider item says which item and what the exact one's listings ask.
4. The hand-made stand-in of R04's start quiver is read again from the stash lines.

Nothing is written until every step is done. The old file is only read.
"""

import argparse
import os
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from crafting_system.data import load_game_data  # noqa: E402
from crafting_system.prices import (  # noqa: E402
    CHAOS_ORB,
    DIVINE_ORB,
    PriceEntry,
    PriceFile,
    RateLimiter,
    RequestBudget,
    TradeClient,
    fetch_price_file,
    load_price_file,
    package_version,
    urllib_transport,
    user_agent,
    write_price_file,
)
from crafting_system.prices.__main__ import _deepen  # noqa: E402
from crafting_system.prices.http_json import http_get_json, paced  # noqa: E402
from crafting_system.prices.price_names import FORESIGHT_PRICE_NAMES, canonical_price_name  # noqa: E402
from crafting_system.prices.provenance import EXACT, STASH, TRADE, WIDER, Provenance  # noqa: E402
from crafting_system.prices.query_compare import other_item  # noqa: E402
from crafting_system.prices.trade_exchange import static_ids  # noqa: E402
from crafting_system.prices.trade_pricing import DEFAULT_K, FETCH_COUNT, _chaos_of, _listings, _stats  # noqa: E402
from crafting_system.prices.trade_query import build_query, query_hash  # noqa: E402
from crafting_system.prices.trade_stats import resolve_buy_mod  # noqa: E402
from crafting_system.targets import StartKind, buy_spec_of, load_target, start_price_key  # noqa: E402

COMPOSITES = {  # old key -> the item the price is of: a normal base plus one typed Alchemy (#494 point 2)
    "Sorcerer Boots, item level 86-100": EXACT,
    "Two-Toned Boots [BootsAtlas1], item level 86-100": WIDER,
}
ALCHEMY = "Orb of Alchemy"
QUIVER_KEY = "Penetrating Arrow Quiver [QuiverNew5], normal, item level 81"
QUIVER_ALIAS = "Penetrating Arrow Quiver (ilvl 81)"
QUIVER_LEVEL = 81
QUIVER_MIN_OBSERVATIONS = 5
EXCHANGE_GROUPS = ("Essences", "Delve")  # the bulk exchange's groups wanted whole: essences, fossils and resonators
LIFEFORCE_WORDS = ("Crystallised Lifeforce", "Crystallised Rancour")


def wanted_names(old: PriceFile, ids: dict[str, str]) -> list[str]:
    """The old file's names that are not trade prices, every essence, fossil and resonator, the lifeforces and the foresight names."""
    names = {name for name, entry in old.prices.items() if entry.source != "trade-api"}
    names |= {text for text in ids if any(word in text for word in LIFEFORCE_WORDS)}
    names |= {text for text in ids if "Essence of" in text or "Fossil" in text or "Resonator" in text}
    names |= set(FORESIGHT_PRICE_NAMES)
    return sorted(canonical_price_name(name) for name in names)


def trade_client(budget: int) -> TradeClient:
    return TradeClient(
        urllib_transport(), user_agent(package_version()), RateLimiter(time.monotonic, time.sleep, max_wait=1800.0, margin=2), RequestBudget(budget), None
    )


def priced_rows(rows, spec, price_file) -> list[float]:
    found = [_chaos_of(row, spec, price_file) for row in rows]
    return sorted(value for value in found if not isinstance(value, str))


def reread_start_items(old: PriceFile, new: PriceFile, cache: Path, now: datetime, data, targets: dict) -> tuple[dict[str, PriceEntry], list[str]]:
    """The trade-priced start items of `old`, asked again today: the stored search, and the exact item of the target."""
    client = trade_client(120)
    stats = _stats(client, cache, now, False)
    league, day = new.league, now.astimezone(UTC).date()
    found: dict[str, PriceEntry] = {}
    notes: list[str] = []
    alchemy = new.prices[ALCHEMY].chaos
    for name, entry in sorted(old.prices.items()):
        stored = (entry.detail or {}).get("query")
        if entry.source != "trade-api" or not isinstance(stored, dict):
            continue
        target = targets.get(name)
        if target is None:
            notes.append(f"{name}: no target of examples/targets has this key; the old entry is not carried over")
            continue
        spec = buy_spec_of(data, target)
        digest = query_hash(league, stored)
        total, rows = _listings(client, league, stored, cache / "trade" / f"{digest}.json", now)
        prices = priced_rows(rows, spec, new)
        if total < 10 or len(prices) < 3:
            notes.append(f"{name}: only {total} listings today ({len(prices)} priced); the old entry is not carried over")
            continue
        cheapest = prices[:DEFAULT_K]
        chaos = statistics.fmean(cheapest)
        sentence = f"mean of the {len(cheapest)} cheapest instant-buyout listings of {len(rows)} fetched, {total} on the site, listed any time"
        composite = COMPOSITES.get(name)
        if composite is not None:
            chaos += alchemy
            sentence += f"; plus one Orb of Alchemy ({alchemy:g}): the item is a normal base made rare by the Alchemy the plan casts"
        taken_for = None if composite is not None else other_item(spec, stored)  # a composite is a normal base the plan makes rare: its search is the item by design
        item = WIDER if (taken_for is not None or composite == WIDER) else EXACT
        for_item = taken_for if taken_for is not None else ("any of the bases that share this name on the trade site" if composite == WIDER else None)
        exact_listings = exact_price = None
        if taken_for is not None:
            filters = [resolve_buy_mod(mod, list(data.mods.values()), stats) for mod in spec.mods]
            exact_body = build_query(spec, filters, None).body()
            exact_total, exact_rows = _listings(client, league, exact_body, cache / "trade" / f"{query_hash(league, exact_body)}.json", now)
            exact = priced_rows(exact_rows, spec, new)
            exact_listings = exact_total
            exact_price = statistics.fmean(exact[:DEFAULT_K]) if exact else None  # the mean of the cheapest few, as every trade price (OR-8)
        depth = float(len(cheapest))
        provenance = Provenance(TRADE, league, day.isoformat(), depth, "units", len(cheapest), item, for_item, exact_listings, exact_price)
        detail = {"league": league, "date": day.isoformat(), "listings": total, "used": len(cheapest), "usable": len(prices), "k": DEFAULT_K, "query_hash": digest, "query": stored}
        found[name] = PriceEntry(chaos, "trade-api", sentence, detail, provenance)
        notes.append(f"{name}: {entry.chaos:g} -> {chaos:g} ({item}; exact listings {exact_listings}, ask {exact_price})")
    return found, notes


def quiver_standins(new: PriceFile, ninja_get, league: str, day: str) -> dict[str, PriceEntry]:
    """R04's start quiver: the cheapest normal line of item level 81 or more with enough observations, read from today's stash overview."""
    from crafting_system.prices.ninja_items import parse_stash_overview  # noqa: PLC0415
    from crafting_system.prices.poe_ninja import api_url  # noqa: PLC0415

    lines = parse_stash_overview(ninja_get(api_url("stash/current/item/overview", league=league, type="BaseType")), "BaseType")
    best = None
    for line in lines:
        if not line.key.startswith("Penetrating Arrow Quiver (ilvl "):
            continue
        level = int(line.key.split("ilvl ")[1].rstrip(")").split(",")[0])
        if level >= QUIVER_LEVEL and line.count >= QUIVER_MIN_OBSERVATIONS and (best is None or line.chaos < best[1].chaos):
            best = (level, line)
    if best is None:
        return {}
    level, line = best
    provenance = Provenance(
        STASH, league, day, float(line.count), "observations", None, WIDER,
        f"the cheapest normal Penetrating Arrow Quiver line of item level {QUIVER_LEVEL} or more with at least {QUIVER_MIN_OBSERVATIONS} observations (item level {level})",
        0, None,
    )  # fmt: skip
    entry = PriceEntry(line.chaos, "poe.ninja", f"poe.ninja BaseType overview, {league}, {day}: item level {level}, {line.count} observations", {"category": "BaseType"}, provenance)
    return {QUIVER_KEY: entry, QUIVER_ALIAS: entry}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--old", required=True, help="the earlier snapshot (its names and its trade searches)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--cache", required=True, help="a folder for the trade site's stat list and answers")
    parser.add_argument("--league", default="Allflame")
    parser.add_argument("--starts-only", action="store_true", help="read OUT, ask the start items again and write OUT: no poe.ninja and no bulk-exchange request")
    parser.add_argument("--resume", action="store_true", help="skip the poe.ninja step: read the file this run wrote after it (OUT.stage1)")
    parser.add_argument("--below", type=float, default=100.0, help="read the trade offers of every name with fewer units than this behind its price")
    args = parser.parse_args()

    now = datetime.now(UTC)
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    old = load_price_file(Path(args.old))
    data = load_game_data(cache_dir=Path(os.environ["CRAFTING_CACHE_DIR"]))
    targets = {}
    for path in sorted((ROOT / "examples" / "targets").glob("*.yaml")):
        target = load_target(path, data)
        if target.start is StartKind.BOUGHT:
            targets.setdefault(start_price_key(data, target), target)

    get_json = paced(http_get_json, time.monotonic, time.sleep)
    ids = static_ids(trade_client(5).data_static())
    wanted = wanted_names(old, ids)
    stage1 = Path(args.out + ".stage1")
    if args.starts_only:
        new = load_price_file(Path(args.out))
        now = datetime.now(UTC)
        starts, notes = reread_start_items(old, new, cache, now, data, targets)
        for note in notes:
            print("  start:", note)
        write_price_file(Path(args.out), PriceFile(new.league, new.fetched_at, new.chaos_per_divine, {**new.prices, **starts}, new.markets, new.ninja))
        print(f"wrote {args.out}: {len(starts)} start items asked again")
        return 0
    if args.resume:
        new = load_price_file(stage1)
        now = new.fetched_at
        print(f"resumed from {stage1}: {len(new.prices)} prices")
    else:
        result = fetch_price_file(get_json, now, wanted, args.league)
        print(f"poe.ninja: {len(result.price_file.prices)} prices, {len(result.missing)} wanted names missing, {len(result.thin)} thin lines left out", flush=True)
        for warning in result.warnings:
            print("  warning:", warning)
        new = result.price_file
        write_price_file(stage1, new)
    new, notes = _deepen(new, wanted, args.below, now, None, None, None, None)
    for note in notes:
        print("  trade:", note)
    day = now.astimezone(UTC).date().isoformat()
    prices = dict(new.prices)
    prices.update(quiver_standins(new, get_json, args.league, day))
    new = PriceFile(new.league, new.fetched_at, new.chaos_per_divine, prices, new.markets, new.ninja)
    starts, notes = reread_start_items(old, new, cache, now, data, targets)
    for note in notes:
        print("  start:", note)
    keep = {*wanted, *old.prices, *starts, CHAOS_ORB, DIVINE_ORB}  # the overviews list thousands of bases the targets never buy
    kept = {name: entry for name, entry in {**new.prices, **starts}.items() if name in keep}
    new = PriceFile(new.league, new.fetched_at, new.chaos_per_divine, kept, new.markets, new.ninja)
    write_price_file(Path(args.out), new)
    print(f"wrote {args.out}: {len(new.prices)} prices, {len(starts)} start items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
