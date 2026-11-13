"""What the crafting methods in scope spend, by price-file name, and which of it a price file does not price (#885).

The owner looked through the default price file and saw no beasts in it: the file held only what the test routes of the day spent.
A method a user may pick must be priced before he picks it, so the question is asked of the action catalog, not of the routes:
**walk every action kind in scope over a set of items, and collect the names its actions' `resources` return.**

**In scope** is every registered kind that is not deferred (`DEFERRED_KINDS`, CLAUDE.md "Direction since 2026-11-13": corruption B4,
Memory Strands B5, sockets and quality B6, enchants B7, Hinekora's Lock B8 and the recombinator wait; ADR-0013 lists the batches).
A kind added later is in scope until someone defers it by name, so a new method cannot stay unpriced unseen. Whether the planner
offers a kind yet (`planner`, `opt_in`) does not matter here: a method is priced before it is built end to end. Scope is by kind,
not by ingredient: the fossil sets are in scope whole, the Bloodstained Fossil among them (its corrupted outcomes are B4; the
fossil is bought like the others).

**The items** (`probe_items`): an action's `resources` reads the action alone, never the item, so the items only have to make every
kind list its actions. For each item class of the equipment domains, the first released base (by id) and, where the class has bases
with a tag some recipe is told by (`SPECIAL_TAGS`: a Talisman takes its own beast recipes), the first of those too; each base as a
normal, a magic and a rare item with no mods, and as a rare item of each influence (the influence recipes are listed per influence).
A kind of `ASKED_ONCE` (the fossil sets: thousands per item, the same fossils and resonators whatever the item) is asked on the
uninfluenced items only.

`unpriced` reads a name as the planner prices an offer (`planner/_offers.py`, `price_offers`): a Chaos Orb is 1, a Divine Orb the
file's rate, a standing default counts, and otherwise the name needs a price in the file (or a thin trade record that gives one).
`tests/test_prices_spends.py` holds the two readings equal. Pure: no I/O, no clock.
"""

from collections.abc import Collection, Iterable, Mapping, Sequence

from crafting_system.actions import NotApplicableError, OutOfScopeError, catalog_kinds, kinds
from crafting_system.data import GameData
from crafting_system.items import Influence, Item, ItemError, Rarity

from .default_prices import standing_defaults
from .price_file import CHAOS_ORB, DIVINE_ORB, PriceFile
from .price_source import DEFAULT_PRICE_SOURCE
from .trade_market import planned_price

__all__ = ["DEFERRED_KINDS", "kinds_in_scope", "probe_items", "spends", "spent_names", "unpriced"]

# kind -> the deferred batch it belongs to (ADR-0013 and the ADRs of each batch)
DEFERRED_KINDS: Mapping[str, str] = {
    "vaal": "B4 corruption",
    "locus": "B4 corruption",
    "foulborn-augmentation-orb": "B5 Memory Strands",
    "foulborn-regal-orb": "B5 Memory Strands",
    "foulborn-exalted-orb": "B5 Memory Strands",
    "orb-of-remembrance": "B5 Memory Strands",
    "unravelling-orb": "B5 Memory Strands",
    "jewellers-orb": "B6 sockets",
    "orb-of-fusing": "B6 sockets",
    "chromatic-orb": "B6 sockets",
    "bench-socket-count": "B6 sockets",
    "bench-socket-links": "B6 sockets",
    "bench-socket-colours": "B6 sockets",
    "quality-currency": "B6 quality",
    "tempering": "B7 enchants",
    "tailoring": "B7 enchants",
    "harvest-quality-enchant": "B7 enchants",
    "re-anoint": "B8 Hinekora's Lock",
    "recombinator": "the recombinator of B3",
}

EQUIPMENT_DOMAINS = ("item", "misc", "abyss_jewel", "flask")  # the domains of the bases a player crafts on: gear, the two kinds of jewels, flasks
NOT_EQUIPMENT = ("HiddenItem",)  # a class of the `item` domain that is no item a player holds
SPECIAL_TAGS = ("talisman",)  # the base tag of a Talisman, which the Talisman fractures and the imprint of a rare Talisman are listed by
ASKED_ONCE = ("fossil-set",)
PROBE_ITEM_LEVEL = 86


def kinds_in_scope() -> tuple[str, ...]:
    """The names of the registered kinds that are not deferred, in catalog order."""
    return tuple(entry.name for entry in kinds() if entry.name not in DEFERRED_KINDS)


def probe_items(data: GameData) -> tuple[Item, ...]:
    """The items the walk asks (the module docstring), in a fixed order."""
    first: dict[tuple[str, str], str] = {}
    for base_id in sorted(data.base_items):
        base = data.base_items[base_id]
        if base.release_state != "released" or base.domain not in EQUIPMENT_DOMAINS or base.item_class in NOT_EQUIPMENT:
            continue
        first.setdefault((base.item_class, ""), base_id)
        for tag in SPECIAL_TAGS:
            if tag in base.tags:
                first.setdefault((base.item_class, tag), base_id)
    found: list[Item] = []
    for base_id in dict.fromkeys(first.values()):
        states = [(rarity, frozenset()) for rarity in (Rarity.NORMAL, Rarity.MAGIC, Rarity.RARE)]
        states += [(Rarity.RARE, frozenset({influence})) for influence in Influence]
        for rarity, influences in states:
            try:
                found.append(Item.build(data, base_id=base_id, item_level=PROBE_ITEM_LEVEL, rarity=rarity, influences=influences))
            except ItemError:
                continue  # the base takes no such item (a class with no influence)
    return tuple(found)


def spends(data: GameData, items: Sequence[Item] | None = None, kind_names: Collection[str] | None = None) -> dict[str, dict[str, str]]:
    """kind -> {price name: the label of the first action met that spends it}, for the kinds `kind_names` (default: those in scope)
    asked on `items` (default: `probe_items`). A kind that listed no action on any item has an empty entry: the walk did not reach it."""
    asked = frozenset(kinds_in_scope() if kind_names is None else kind_names)
    found: dict[str, dict[str, str]] = {entry.name: {} for entry in kinds() if entry.name in asked}
    for item in probe_items(data) if items is None else items:
        for kind in found:
            if item.influences and kind in ASKED_ONCE:
                continue
            try:
                listed = catalog_kinds(data, item, names=(kind,), strands=True)
            except (NotApplicableError, OutOfScopeError):
                continue  # the kind refused the item while it listed (an influenced item of a class the model gives no influence)
            spent = found[kind]
            for action in listed:
                for name in action.resources(data):
                    if name not in spent:
                        spent[name] = action.label(data)
    return found


def spent_names(data: GameData, items: Sequence[Item] | None = None, kind_names: Collection[str] | None = None) -> list[str]:
    """Every price name the kinds spend (`spends`), sorted."""
    return sorted({name for spent in spends(data, items, kind_names).values() for name in spent})


def unpriced(names: Iterable[str], price_file: PriceFile, price_source: str = DEFAULT_PRICE_SOURCE) -> list[str]:
    """The names of `names` the planner could not price at `price_file` under the profile's `price_source`, sorted (the module
    docstring says how it reads one)."""
    defaults = standing_defaults()
    return sorted(
        name for name in set(names)
        if name not in (CHAOS_ORB, DIVINE_ORB) and name not in defaults and planned_price(price_file, name, price_source) is None
    )  # fmt: skip
