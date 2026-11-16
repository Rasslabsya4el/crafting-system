"""`python -m crafting_system.web [--host HOST] [--port PORT] [--workers N] [--db PATH] [--price-refresh-hours H ...]`: the website's
service, one command (`docs/web.md`).

Each flag has an environment variable for a container: `CRAFTING_WEB_HOST` (default 127.0.0.1), `CRAFTING_WEB_PORT` (8000),
`CRAFTING_WEB_WORKERS` (1: plans run at once; each plan also uses the cores `CRAFTING_WORKERS` gives it) and `CRAFTING_WEB_DB` (the SQLite
file, default `<output folder>/web/site.sqlite3`). The game data, the prices and the planner's limits are the command's (`crafting.toml`).

The scheduled price refresh (OR-9, #1008; `_refresh`) is on when `CRAFTING_PRICE_REFRESH_HOURS` is above 0 (off by default; the image turns
it on): the price command runs every that many hours and its new file replaces the configured one. `CRAFTING_PRICE_LEAGUE` names the league
(default: the league of the price file in place, else poe.ninja's current one), `CRAFTING_PRICE_TRADE_BELOW` the command's `--trade-below`
(off by default), `CRAFTING_PRICE_WANTED_FILE` names to price beside what the methods in scope spend, `CRAFTING_PRICE_FETCH_MINUTES` the
time one fetch may take (60). With no price file in place the server first fetches one, and serves once it has it.
"""

import argparse
import logging
import math
import os
import sys
from datetime import timedelta
from pathlib import Path

from crafting_system.config import load_config
from crafting_system.data import load_game_data
from crafting_system.prices import default_overrides_path, default_price_file_path
from crafting_system.prices.price_names import canonical_price_name
from crafting_system.prices.spends import spent_names

from ._app import create_app
from ._refresh import MIN_INTERVAL, PriceRefresh, fetch_command
from ._service import Service
from ._store import SqliteStore
from ._world import load_world


def _refresh_hours(text: str) -> float:
    """Hours between two price fetches: 0 (never) or at least `MIN_INTERVAL`, a finite number."""
    hours = float(text)
    if not (hours == 0 or (math.isfinite(hours) and MIN_INTERVAL.total_seconds() / 3600 <= hours <= 24 * 365)):
        raise argparse.ArgumentTypeError(f"0 (never) or {MIN_INTERVAL.total_seconds() / 3600:g} to {24 * 365} hours, not {text}")
    return hours


def _optional_float(text: str | None) -> float | None:
    return None if text is None or not text.strip() else float(text)


def main(argv: list[str] | None = None) -> int:
    import uvicorn  # noqa: PLC0415  (the server is the `web` extra's; the app itself needs only Starlette)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config()
    env = os.environ
    parser = argparse.ArgumentParser(prog="python -m crafting_system.web", description="The planner behind an HTTP API (docs/web.md).")
    parser.add_argument("--host", default=env.get("CRAFTING_WEB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(env.get("CRAFTING_WEB_PORT", "8000")))
    parser.add_argument("--workers", type=int, default=int(env.get("CRAFTING_WEB_WORKERS", "1")), help="plans run at once")
    parser.add_argument("--db", default=env.get("CRAFTING_WEB_DB") or str(config.output_dir / "web" / "site.sqlite3"), help="the SQLite file of the store")
    parser.add_argument(
        "--price-refresh-hours",
        type=_refresh_hours,
        default=env.get("CRAFTING_PRICE_REFRESH_HOURS") or "0",
        help="fetch the prices every that many hours (0: never; at least a quarter of an hour)",
    )
    parser.add_argument("--price-league", default=env.get("CRAFTING_PRICE_LEAGUE") or None, help="the league whose prices are fetched")
    parser.add_argument("--price-trade-below", type=float, default=_optional_float(env.get("CRAFTING_PRICE_TRADE_BELOW")), help="the fetch's --trade-below")
    parser.add_argument("--price-wanted-file", default=env.get("CRAFTING_PRICE_WANTED_FILE") or None, help="more names to price, one per line")
    parser.add_argument("--price-fetch-minutes", type=float, default=float(env.get("CRAFTING_PRICE_FETCH_MINUTES") or 60), help="the time one fetch may take")
    args = parser.parse_args(argv)
    service = Service(SqliteStore(args.db), load_world, game="poe1", workers=args.workers)

    refresh = None
    if args.price_refresh_hours > 0:
        wanted = spent_names(load_game_data(cache_dir=config.cache_dir))  # every method in scope priced before a user picks it (#885)
        if args.price_wanted_file:
            lines = Path(args.price_wanted_file).read_text(encoding="utf-8-sig").splitlines()
            wanted += [canonical_price_name(line.strip()) for line in lines if line.strip() and not line.lstrip().startswith("#")]
        refresh = PriceRefresh(
            default_price_file_path(config),
            default_overrides_path(config),
            fetch_command(wanted=sorted(set(wanted)), trade_below=args.price_trade_below, timeout_seconds=args.price_fetch_minutes * 60),
            interval=timedelta(hours=args.price_refresh_hours),
            league=args.price_league,
            on_new_file=lambda: _load_now(service),
        )
        while not refresh.price_path.exists():  # nothing to plan with yet: the first fetch comes before the server
            logging.getLogger(__name__).info("no price file at %s: fetching one before the server starts", refresh.price_path)
            if not refresh.refresh() and refresh.wait_retry():
                return 1
        refresh.start()
    try:
        uvicorn.run(create_app({"poe1": service}), host=args.host, port=args.port)
    finally:
        if refresh is not None:
            refresh.stop()
    return 0


def _load_now(service: Service) -> None:
    """Load the new prices at once (the service would at its next request); nothing to do before the server has started."""
    try:
        service.world  # noqa: B018  (the property reloads the world when its files changed)
    except RuntimeError:
        pass


if __name__ == "__main__":
    sys.exit(main())
