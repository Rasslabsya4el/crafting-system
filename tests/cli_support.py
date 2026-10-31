"""Shared helpers for the `cli` tests: a price file in memory, the R12 target, a run of the command."""

import datetime
import json
import math
from pathlib import Path

from targets_support import DATA, EXAMPLES

from crafting_system.cli import main
from crafting_system.prices import PriceEntry, PriceFile

R12 = EXAMPLES / "r12-lightning-amulet.yaml"
TODAY = datetime.date(2026, 10, 31)
LIFEFORCE = "Primal Crystallised Lifeforce"
START = "R12 start amulet"


def price_file(lifeforce: float | None = 0.01, start: float | None = 4.0, divine: float = 300.0) -> PriceFile:
    """Prices in Chaos: the lifeforce of a Harvest reforge and the trade-API price of the R12 start amulet."""
    prices = {}
    if lifeforce is not None:
        prices[LIFEFORCE] = PriceEntry(lifeforce, "poe.ninja")
    if start is not None:
        prices[START] = PriceEntry(start, "trade-api")
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), divine, prices)


def run(tmp_path: Path, *arguments: str, target: Path = R12, data=DATA, prices: PriceFile | None = None):
    """Run the command on the fixture game data; returns the exit code and the path of the JSON it wrote.

    `prices=None` makes the command read the price file the target names, as it does for a user.
    """
    out = tmp_path / "policy.json"
    code = main(
        [str(target), "--json", str(out), *arguments],
        data=data,
        prices=prices,
        env={},
        today=TODAY,
    )
    return code, out


def read_json(path: Path) -> dict:
    """The policy file, read strictly: JSON has no NaN or Infinity."""

    def refuse(constant: str):
        raise AssertionError(f"the policy holds {constant}, which is not JSON")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=refuse)


def geometric_p90_clicks(chance: float) -> int:
    """The least number of clicks n with P(done within n) >= 0.9 when each click succeeds with `chance`."""
    return math.ceil(math.log(0.1) / math.log(1.0 - chance) - 1e-12)
