"""The world a service plans in: the game data, the price snapshot and the planner settings of the machine, loaded once per process.

A `WorldSource` is a module-level function with no arguments that loads the world; the service calls it in its own process (to check
requests and key them) and in every worker process (to plan), so it must be importable by name from a fresh process. `load_world` is the
site's: the pinned game data from the cache, the configured price file with its overrides, and the `[planner]` table of `crafting.toml`.

**A refreshed price file** (OR-9: the system fetches prices on a schedule and replaces the file in one step): a world names the files it was
read from that may change while the server runs (`sources`) and how they stood just before it read them (`stamp`). The service compares
that stamp with the files as they stand now (`World.outdated`) and loads a new world when they differ, so it keys new requests on the new
snapshot without a restart (#968).

**The age of a snapshot** (#976): `snapshot_age` says how many days old a snapshot is on a given day and whether that is past the limit the
command warns at (`prices.MAX_AGE_DAYS`, `prices.stale_warning`). The day is the caller's: nothing here reads the clock.
"""

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import cached_property
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version

from crafting_system.budget import PROOF_GAP, Budget
from crafting_system.config import Config, load_config
from crafting_system.data import GameData, load_game_data
from crafting_system.prices import PriceFile, default_price_file_path, stale_warning
from crafting_system.prices.price_file import MAX_AGE_DAYS, OVERRIDES_FILE_NAME
from crafting_system.cli import load_target_prices, run_budget
from crafting_system.planner import BUDGET_SECONDS


def _own_version() -> str:
    try:
        return f"crafting-system {version('crafting-system')}"
    except PackageNotFoundError:
        return "crafting-system"


PLANNER_VERSION = _own_version()

SNAPSHOT_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"  # a snapshot's fetch time as the API and a route's summary write it

Stamp = tuple[tuple[str, ...] | tuple[str, int, int, int], ...]


def stamp_of(paths: tuple[Path, ...]) -> Stamp:
    """How each file stands: its path, its file number, the time it was last written (nanoseconds) and its size; or the path and why it
    cannot be read when it is missing or unreadable. A file moved over the old one in one step has a new file number even when its time
    and size are the old ones."""
    stamp: list = []
    for path in paths:
        try:
            status = os.stat(path)
        except OSError as error:
            stamp.append((str(path), type(error).__name__))
        else:
            stamp.append((str(path), status.st_ino, status.st_mtime_ns, status.st_size))
    return tuple(stamp)


def snapshot_age(league: str, fetched_at: datetime, today: date, max_age_days: int = MAX_AGE_DAYS) -> dict:
    """The age of the price snapshot of `league` fetched at `fetched_at` on the day `today`, as the API says it: the day it was fetched,
    its age in whole days (from the UTC date of the fetch, as `prices.stale_warning` counts), the limit, whether it is past the limit
    (judged by `stale_warning` itself) and, when it is, a warning in the site's words (#976)."""
    fetched_on = fetched_at.astimezone(UTC).date()
    age = (today - fetched_on).days
    stale = stale_warning(PriceFile(league, fetched_at, 1.0), today, max_age_days) is not None
    warning = (
        f"The prices are {age} days old (the {league} price snapshot of {fetched_on.isoformat()}); prices older than {max_age_days} days "
        "may be out of date."
        if stale
        else None
    )
    return {
        "league": league,
        "fetched_at": fetched_at.astimezone(UTC).strftime(SNAPSHOT_TIME_FORMAT),
        "age_days": age,
        "max_age_days": max_age_days,
        "stale": stale,
        "warning": warning,
    }


@dataclass(frozen=True)
class World:
    """The inputs every request of one game is planned with. `planner_version` names the code (a deploy may set the commit), so a new
    planner never answers from routes an older one stored."""

    data: GameData
    prices: PriceFile
    config: Config
    planner_version: str = PLANNER_VERSION
    gap: float = PROOF_GAP  # the proof the search owes (OR-32, OR-39)
    sources: tuple[Path, ...] = ()  # the files read that a refresh may replace while the server runs (the price file, its overrides)
    stamp: Stamp = ()  # how `sources` stood just before they were read (`stamp_of`)

    def outdated(self) -> bool:
        """Whether a file this world was read from has changed since (a price refresh): the service then loads a new world (#968)."""
        return bool(self.sources) and stamp_of(self.sources) != self.stamp

    @cached_property
    def budget(self) -> Budget:
        """The budget of one run: the aim of the command, the nets of the machine's planner settings (OR-40) and the proof gap."""
        return run_budget(self.config, BUDGET_SECONDS, gap=self.gap)

    @property
    def machine(self) -> dict:
        """The planner settings of the machine that change an answer, as they go into a request's key."""
        budget = self.budget
        return {
            "gap": budget.gap,
            "time_limit_seconds": budget.seconds,
            "memory_limit_mb": budget.memory_mb,
            "max_imprints": self.config.max_imprints,
            "recombinator_junk_craft": self.config.recombinator_junk_craft,
            "price_gap_percent": self.config.price_gap_percent,
        }

    @property
    def price_day(self) -> date:
        """The day a price's age is judged on (`PlanSettings.today`): the day the snapshot was fetched, so a plan depends on the snapshot
        and never on the calendar, and a route stays the answer for as long as its snapshot stands (OR-36)."""
        return self.prices.fetched_at.date()

    @cached_property
    def price_snapshot(self) -> str:
        """The price snapshot by its league, the time it was fetched and a digest of every price in it (a hand override changes it)."""
        prices = self.prices
        parts = [repr(sorted(table.items())) for table in (prices.prices, prices.markets, prices.ninja, prices.deep)]
        digest = hashlib.sha256("\n".join([repr(prices.chaos_per_divine), *parts]).encode("utf-8")).hexdigest()[:16]
        return f"{prices.league} {prices.fetched_at.strftime('%Y-%m-%dT%H:%M:%SZ')} {digest}"


WorldSource = Callable[[], World]


def load_world() -> World:
    """The site's world, from the environment and `crafting.toml` as the command reads them (`CRAFTING_CACHE_DIR`, `CRAFTING_DATA_DIR`, ...)."""
    config = load_config()
    price_path = default_price_file_path(config)
    sources = (price_path, price_path.parent / OVERRIDES_FILE_NAME)  # as `load_target_prices` reads them
    stamp = stamp_of(sources)  # before the read: a file replaced during it is seen as changed at the next check
    return World(load_game_data(cache_dir=config.cache_dir), load_target_prices(None, config), config, sources=sources, stamp=stamp)
