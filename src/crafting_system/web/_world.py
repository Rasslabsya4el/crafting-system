"""The world a service plans in: the game data, the price snapshot and the planner settings of the machine, loaded once per process.

A `WorldSource` is a module-level function with no arguments that loads the world; the service calls it in its own process (to check
requests and key them) and in every worker process (to plan), so it must be importable by name from a fresh process. `load_world` is the
site's: the pinned game data from the cache, the configured price file with its overrides, and the `[planner]` table of `crafting.toml`.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from functools import cached_property
from importlib.metadata import PackageNotFoundError, version

from crafting_system.budget import PROOF_GAP, Budget
from crafting_system.config import Config, load_config
from crafting_system.data import GameData, load_game_data
from crafting_system.prices import PriceFile
from crafting_system.cli import load_target_prices, run_budget
from crafting_system.planner import BUDGET_SECONDS


def _own_version() -> str:
    try:
        return f"crafting-system {version('crafting-system')}"
    except PackageNotFoundError:
        return "crafting-system"


PLANNER_VERSION = _own_version()


@dataclass(frozen=True)
class World:
    """The inputs every request of one game is planned with. `planner_version` names the code (a deploy may set the commit), so a new
    planner never answers from routes an older one stored."""

    data: GameData
    prices: PriceFile
    config: Config
    planner_version: str = PLANNER_VERSION
    gap: float = PROOF_GAP  # the proof the search owes (OR-32, OR-39)

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
    return World(load_game_data(cache_dir=config.cache_dir), load_target_prices(None, config), config)
