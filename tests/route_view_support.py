"""Shared helpers of the route view tests (ticket #78): golden pages and hand-made policies on the fixture belt.

`assert_golden(name, html)` compares a page with `tests/golden/<name>.html`; `UPDATE_GOLDEN=1` rewrites it and
a missing file fails. `hand_input(...)` builds a `RouteInput` for a policy chosen by a small function: the plan
is made by hand (`make_plan` cannot enable bench actions yet), the abstraction has the bench crafts enabled so
the junk of a state is tracked, the offers are priced with `price_offers`, the actions are the solver's own
(`offer_action`), the risk is `risk.evaluate`. The solver's values are not read by the view and left empty.
"""

import datetime
import os
import re
from collections.abc import Callable
from pathlib import Path

import golden_diff
from abstraction_oracle import crafted_item
from items_support import DATA, item, roll
from plan_support import planner_plan

from crafting_system.abstraction import Abstraction, CompressedState, Goal
from crafting_system.actions import ApplyEssence, BenchCraft, ChaosOrb, RemoveCraftedMods
from crafting_system.cli import Offer, price_offers
from crafting_system.cli._plan import StartPrice, leaf_labels, offer_action
from crafting_system.cli._route_view import RouteInput, route_input
from crafting_system.items import Item, Rarity
from crafting_system.prices import CHAOS_ORB, PriceEntry, PriceFile
from crafting_system.prices.provenance import EXCHANGE, TRADE, Provenance
from crafting_system.risk import evaluate
from crafting_system.solver import Solution
from crafting_system.targets import Requirement, StartKind, Target

GOLDEN = Path(__file__).resolve().parent / "golden"

BELT = "Metadata/Items/Belts/Belt3"
LEVEL = 86
LIFE_MODS = frozenset({"IncreasedLife1", "IncreasedLife2", "IncreasedLife3"})
COLD = "ColdResist1"
DAMAGE = "JunMaster2AllDamage2_"  # a prefix craft, family AllDamage (not in the belt pool)
HYSTERIA = ApplyEssence("Essence of Hysteria")
HYSTERIA_MOD = "ElementalPenetrationDuringFlaskEffectEssence1"
START_NAME = "Hand start belt"
DEEP = 1e9  # units behind the fixture's prices: deep enough for any plan of these tests, so the tests judge something else than the price
EXCHANGE_LINE = Provenance(EXCHANGE, "Test", "2026-10-30", DEEP)
PRICES = PriceFile(
    "Test",
    datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC),
    300.0,
    {
        START_NAME: PriceEntry(6.0, "trade-api", None, None, Provenance(TRADE, "Test", "2026-10-30", DEEP, "units", 5)),
        "Essence of Hysteria": PriceEntry(3.0, "poe.ninja", None, None, EXCHANGE_LINE),
        "Orb of Scouring": PriceEntry(2.0, "poe.ninja", None, None, EXCHANGE_LINE),
        "Divine Orb": PriceEntry(300.0, "poe.ninja", None, None, EXCHANGE_LINE),
    },
)

LIFE = Requirement("IncreasedLife", None, LIFE_MODS)
COLD_REQ = Requirement("ColdResistance", None, frozenset({COLD}))
HYSTERIA_REQ = Requirement(None, "Elemental Penetration during Flask Effect", frozenset({HYSTERIA_MOD}))


def assert_golden(name: str, html: str, extension: str = "html") -> None:
    """The page equals `tests/golden/<name>.<extension>` (`html`, or `txt` for a text report); `UPDATE_GOLDEN=1` writes it first, a missing file fails."""
    __tracebackhide__ = True
    path = GOLDEN / f"{name}.{extension}"
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.mkdir(exist_ok=True)
        path.write_text(html, encoding="utf-8", newline="\n")
    assert path.exists(), f"no golden file {path}; run with UPDATE_GOLDEN=1 to write it"
    golden_diff.check(path.read_text(encoding="utf-8"), html, golden_diff.kind_of(path), f"{name} differs from its golden file tests/golden/{path.name}")


def alike_key(text: str) -> str:
    """A line of "Chance per use" or "On failure" without its chance: two lines of one step with the same key read alike."""
    return re.sub(r": [^:]*%$|\s\([^()]*%\)$", "", text)


def belt(*mods, rarity: Rarity = Rarity.RARE) -> Item:
    return item(*mods, base_id=BELT, rarity=rarity, item_level=LEVEL)


def crafted_damage(start: Item) -> Item:
    return crafted_item(DATA, start, DAMAGE)


FRACTURED_COLD = roll(COLD, fractured=True)

OFFERS = (
    Offer("Chaos Orb", ChaosOrb(), {CHAOS_ORB: 1}),
    Offer("Essence of Hysteria", HYSTERIA, {"Essence of Hysteria": 1}),
    Offer("Benchcraft: All Damage", BenchCraft(DAMAGE), {"Divine Orb": 1}),
    Offer("Remove Crafted Mods", RemoveCraftedMods(), {"Orb of Scouring": 1}),
)
ACTIONS = (BenchCraft(DAMAGE), RemoveCraftedMods(), HYSTERIA)  # the enabled actions that read the junk

Chooser = Callable[[CompressedState, Abstraction], str | None]


def hand_input(start: Item, requirements: tuple[Requirement, ...], choose: Chooser, label: str = "Hand-made policy") -> RouteInput:
    """A route drawn from the policy `choose(state, abstraction)` (an offer label, or None for no action)."""
    target = Target(BELT, LEVEL, frozenset(), requirements, start, start=StartKind.BOUGHT)
    ab = Abstraction(DATA, Goal.from_target(target), BELT, LEVEL, ACTIONS)
    first = ab.compress(start)
    priced, _ = price_offers(OFFERS, PRICES)
    by_label = {offer.label: offer for offer in priced}
    policy = {}
    order = [first]
    for state in order:
        if ab.is_goal(state):
            continue
        picked = choose(state, ab)
        if picked is None:
            continue
        policy[state] = offer_action(ab, by_label[picked], state)
        order += [s for s, w in policy[state].outcomes if w > 0 and s not in order]
    plan = planner_plan(
        target=target, abstraction=ab, leaf_labels=leaf_labels(target), prices=PRICES, start=first,
        start_price=StartPrice(START_NAME, 6.0, "trade-api"), offers=priced,
        solution=Solution({}, policy, 0.0), risk=evaluate(policy, first, ab.is_goal),
        solve_seconds=0.0, risk_seconds=0.0,
    )  # fmt: skip
    return route_input(plan)
