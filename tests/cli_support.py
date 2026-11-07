"""Shared helpers for the `cli` tests: a price file in memory, the R12 target, a run of the command."""

import dataclasses
import datetime
import json
import math
from pathlib import Path

from targets_support import DATA, EXAMPLES

from crafting_system.cli import main
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.prices.provenance import PREVIOUS_LEAGUE, Provenance
from crafting_system.targets import StartKind, Target, load_target, start_price_key

R12 = EXAMPLES / "r12-lightning-amulet.yaml"
TODAY = datetime.date(2026, 10, 31)
LIFEFORCE = "Primal Crystallised Lifeforce"
OTHER_RESOURCES = ("Wild Crystallised Lifeforce", "Vivid Crystallised Lifeforce", "Crystallised Rancour")  # the other goods of the Harvest reforges
EVIDENCE_PRICE = 100.0  # dear enough that no plan of these tests chooses a reforge that costs it
START = start_price_key(DATA, load_target(R12, DATA))  # the price key computed from the R12 target (#474)


def given(target: Target) -> Target:
    """`target` with its start item given (OR-6): its cost is not counted and the plan never buys another."""
    return dataclasses.replace(target, start=StartKind.GIVEN)


def price_file(lifeforce: float | None = 0.01, start: float | None = 4.0, divine: float = 300.0, data=None, evidence: bool = False) -> PriceFile:
    """Prices in Chaos: the lifeforce of a Harvest reforge and the trade-API price of the R12 start amulet.

    With `evidence`, the other goods of the Harvest reforges (`OTHER_RESOURCES`) are priced too, as a previous league's price (an approximate
    input, OR-23) so that no action is dropped for want of a price (#552): the pages of these tests then have no part "Actions with no price".

    The start amulet is priced under the key computed from the R12 target on `data` (default: the fixture data, `START`): the item level
    window, and so the key, depend on the game data.
    """
    prices = {}
    if lifeforce is not None:
        prices[LIFEFORCE] = PriceEntry(lifeforce, "poe.ninja")
    if start is not None:
        prices[START if data is None else start_price_key(data, load_target(R12, data))] = PriceEntry(start, "trade-api")
    if evidence:
        earlier = Provenance(PREVIOUS_LEAGUE, "Earlier", "2026-06-13")
        prices.update({name: PriceEntry(EVIDENCE_PRICE, "poe.ninja-previous-league", None, None, earlier) for name in OTHER_RESOURCES})
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
