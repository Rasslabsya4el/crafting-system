"""Shared helpers for the `cli` tests: a price file in memory, the R12 target, a run of the command."""

import dataclasses
import datetime
import json
import math
from pathlib import Path

from targets_support import DATA, EXAMPLES

from crafting_system.cli import main
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.prices.provenance import EXCHANGE, TRADE, Provenance
from crafting_system.targets import StartKind, Target, load_target, start_price_key

R12 = EXAMPLES / "r12-lightning-amulet.yaml"
TODAY = datetime.date(2026, 10, 31)
DAY = "2026-10-30"  # the day of the fixture price file
DEEP = 1e9  # units behind the fixture's prices: deep enough for any plan of these tests, so they are plain facts and the tests judge something else
LIFEFORCE = "Primal Crystallised Lifeforce"
START = start_price_key(DATA, load_target(R12, DATA))  # the price key computed from the R12 target (#474)
# the methods a test of one mechanism on R12 names (#886): every method is offered by default since, and a test of the walk, its forecast or
# its limits is about these, not about the rest
R12_KINDS = ("chaos-orb", "harvest-reforge", "essence", "bench-craft", "remove-crafted-mods")


# The CLASSIC offers: what a target with no `actions:` was offered before #886 turned every beta method on (OR-41). The real routes' CI
# tests plan with them (a module sets `CLASSIC_OFFERS = True`, `tests/conftest.py`), so their records of before #886 hold byte for byte:
# with every method on, most real routes give no plan within CI's time and memory, and their default plans are recorded by the heavy
# benchmark instead. A test planning with these is not a test of the default plan. `tests/test_classic_offers.py` pins the list.
# * The kinds on by default then, by the code's own names (`kinds()`; the order is the catalog's). The Eldritch currencies among them were
#   offered only to a target that asks for an Eldritch implicit (#835): the classic offers turn that gate on again (`_offers.ELDRITCH_GATE`).
CLASSIC_KINDS = (
    "chaos-orb", "harvest-reforge", "harvest-reforge-influence", "essence", "bench-craft", "remove-crafted-mods", "transmutation-orb",
    "alteration-orb", "augmentation-orb", "regal-orb", "divine-orb", "awakeners-orb", "eldritch-implicit-currency", "eldritch-chaos-orb",
    "eldritch-exalted-orb", "eldritch-annulment-orb", "orb-of-conflict", "foulborn-augmentation-orb", "foulborn-regal-orb",
    "orb-of-remembrance", "vaal", "locus", "unravelling-orb",
)
# * The catalysts stay on beside them (#1289): the kind came after #886 (#159), a target that asks for catalyst quality was refused before it,
#   and R05's target is the guide's ring with its 20% Intrinsic quality (OR-58). A target that asks for no quality is offered no catalyst and
#   its answer says no word about them (`planner/_offers`), so the records of the other routes hold.
CLASSIC_QUALITY_KINDS = ("catalyst",)
# * The corrupting kinds a target that takes a corrupted item could use without naming them, and no blocking crafts (`_offers.BLOCKING_CRAFTS`).
CLASSIC_CORRUPTING_KINDS = {"vaal": 1, "locus": 2}


def classic_offers(patch) -> None:
    """Make the default offers the CLASSIC ones (`CLASSIC_KINDS`) for as long as `patch` (a `pytest.MonkeyPatch`) is undone."""
    import importlib

    from crafting_system.planner import _offers
    from crafting_system.targets import corrupted

    catalog = importlib.import_module("crafting_system.actions.catalog")  # the module: `crafting_system.actions.catalog` is also a function
    for name, entry in list(catalog._KINDS.items()):
        if entry.planner and name not in CLASSIC_KINDS and name not in CLASSIC_QUALITY_KINDS and not entry.opt_in:
            patch.setitem(catalog._KINDS, name, dataclasses.replace(entry, opt_in=True))
        elif entry.planner and name in CLASSIC_KINDS and entry.opt_in:  # the Vaal Orb and the Locus, deferred since #1125 (OR-37), were classic
            patch.setitem(catalog._KINDS, name, dataclasses.replace(entry, opt_in=False))
    patch.setattr(_offers, "BLOCKING_CRAFTS", False)
    patch.setattr(_offers, "ELDRITCH_GATE", True)
    patch.setattr(corrupted, "DEFAULT_CORRUPTING_KINDS", dict(CLASSIC_CORRUPTING_KINDS))


def r12_named(data=DATA) -> Target:
    """The R12 target with `R12_KINDS` named in its `actions:`."""
    return dataclasses.replace(load_target(R12, data), actions=R12_KINDS)


def given(target: Target) -> Target:
    """`target` with its start item given (OR-6): its cost is not counted and the plan never buys another."""
    return dataclasses.replace(target, start=StartKind.GIVEN)


def price_file(lifeforce: float | None = 0.01, start: float | None = 4.0, divine: float = 300.0, data=None) -> PriceFile:
    """Prices in Chaos: the lifeforce of a Harvest reforge and the trade-API price of the R12 start amulet.

    The start amulet is priced under the key computed from the R12 target on `data` (default: the fixture data, `START`): the item level
    window, and so the key, depend on the game data.
    """
    prices = {}
    if lifeforce is not None:
        prices[LIFEFORCE] = PriceEntry(lifeforce, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", DAY, DEEP))
    if start is not None:
        prices[START if data is None else start_price_key(data, load_target(R12, data))] = PriceEntry(start, "trade-api", None, None, Provenance(TRADE, "Test", DAY, DEEP, "units", 5))
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), divine, prices)


def run(tmp_path: Path, *arguments: str, target: Path = R12, data=DATA, prices: PriceFile | None = None):
    """Run the command on the fixture game data; returns the exit code and the path of the JSON it wrote.

    `prices=None` makes the command read the price file the target names, as it does for a user. The run has no time or memory limit unless the
    test gives one (`--time-limit`, `--memory-limit`): these tests check the answers, and OR-33's net of the command is `tests/test_budget.py`'s (#825).
    """
    out = tmp_path / "policy.json"
    unlimited = [part for flag in ("--time-limit", "--memory-limit") if flag not in arguments for part in (flag, "none")]
    code = main(
        [str(target), "--json", str(out), *arguments, *unlimited],
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
