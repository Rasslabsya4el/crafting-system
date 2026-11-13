"""Stranded purchases: the buy offers of a target's start item with a minimum Memory Strand count (ADR-0043, ADR-0040; ticket #278).

A buy offer may name a minimum strand count `m`. The planner does not ask for all 100 counts: it offers the counts at which a **cut class
begins** for a tier table the target needs, usually two to four per query. This is a choice of which prices to fetch, not a claim that the
counts of one class are equivalent (the spend depends on the exact count, ADR-0040): the main chat's default, `approximate`.

* **The tables the target needs.** Each mod a requirement counts (a `k of n` group's members included) belongs to one tier table, the mods
  of one `(mod type, generation type, domain)` that the draw admits at the target's item level and influences (`actions.build_pool` of a
  normal start item with no mods: the cut is made before the mods on the item block their families, ADR-0040). `T` is the number of its
  distinct required levels. A table of one tier cannot be cut and gives no offer.
* **Where a class begins.** For `s` from 1 to 100 the kept tiers are `rollable_tiers(T, s)` (`actions.cut`, the formula of ADR-0040); a class
  begins at 1 (the first count that cuts) and wherever the kept tiers change. The offers are the union over the tables, in order.
* **The search.** `buy_spec_of(data, target, strands=m)`: the start item's own spec with the trade site's `memory_level` minimum `m`, instant
  buyout (OR-7), named by the plain key followed by ", m or more Memory Strands", which is the name its price is cached under in the price
  file (ADR-0007). Nothing fetches these specs yet: the `trade` command prices the plain start item only, so until the fetch is built
  (filed with this ticket) every stranded offer is dropped as unpriced unless the price file holds it.
* **The price** is `prices.planned_price` of that name under the profile's price source: a thin market keeps its mark (OR-8). **An offer
  without a price is dropped and the report lists it** (`StrandedOffers.dropped`, `report_lines`), as for any resource without a price.
* **A listing "with at least `m`" is planned as an item with exactly `m`.** Under the plan's weight reading more strands never hurt a requirement
  on a minimum tier, so the planned cost is an upper bound for what the listing really gives (ADR-0043).

The planner refuses a run with strands on until the gate opens in the B5 chain (#423), so no plan reads these offers yet: they are built and
priced here, and the gate's ticket puts them among the start options.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from crafting_system.actions import build_pool, rollable_tiers
from crafting_system.data import GameData
from crafting_system.items import MAX_MEMORY_STRANDS, Item, Rarity
from crafting_system.prices import PlannedPrice, PriceFile, planned_price
from crafting_system.prices.trade_query import BuySpec

from .model import KOfN, Node, Target
from .start_buy import buy_spec_of

__all__ = [
    "DroppedOffer",
    "StrandedOffer",
    "StrandedOffers",
    "cut_class_starts",
    "needed_tables",
    "stranded_offer_counts",
    "stranded_offers",
]

TableKey = tuple[str, str, str]  # (mod type, generation type, domain): one tier table (ADR-0040)


@dataclass(frozen=True)
class StrandedOffer:
    """A priced stranded purchase: the start item with at least `strands` Memory Strands, planned as exactly `strands`."""

    strands: int
    spec: BuySpec
    price: PlannedPrice

    @property
    def chaos(self) -> float:
        return self.price.entry.chaos


@dataclass(frozen=True)
class DroppedOffer:
    """A stranded purchase that has no price, and why it is left out."""

    strands: int
    name: str
    reason: str


@dataclass(frozen=True)
class StrandedOffers:
    """The stranded purchases of a target: those with a price, in order of the count, and those dropped for want of one."""

    offers: tuple[StrandedOffer, ...]
    dropped: tuple[DroppedOffer, ...]

    def report_lines(self) -> tuple[str, ...]:
        """One line per dropped offer, for the report: the item and why it is not offered."""
        return tuple(f"not offered: {dropped.name} ({dropped.reason})" for dropped in self.dropped)


def cut_class_starts(total_tiers: int) -> tuple[int, ...]:
    """The strand counts, 1 to 100, at which a cut class of a table of `total_tiers` tiers begins: 1, and every count whose kept tiers differ from the count before.

    A table of one tier is never cut and has none.
    """
    if total_tiers <= 1:
        return ()
    starts, kept = [], total_tiers
    for strands in range(1, MAX_MEMORY_STRANDS + 1):
        now = rollable_tiers(total_tiers, strands)
        if now != kept:
            starts.append(strands)
            kept = now
    return tuple(starts)


def _wanted_mods(nodes: Iterable[Node]) -> set[str]:
    found: set[str] = set()
    for node in nodes:
        found |= _wanted_mods(node.of) if isinstance(node, KOfN) else set(node.mod_ids)
    return found


def needed_tables(data: GameData, target: Target) -> Mapping[TableKey, int]:
    """The tier tables the target's requirements draw from, each with its number of tiers on the target's base, level and influences.

    The tiers are counted on the pool of a normal item of the start item's base, level and influences with no mods, so they are what the draw
    can roll there (ADR-0040). A wanted mod that is not in that pool (a crafted mod, an essence's own) is in no table.
    """
    start = target.start_item
    bare = Item.build(data, base_id=start.base_id, item_level=start.item_level, rarity=Rarity.NORMAL, influences=start.influences)
    levels: dict[TableKey, set[int]] = {}
    for family in build_pool(data, bare):
        for entry in family.mods:
            mod = entry.mod
            levels.setdefault((mod.type, mod.generation_type, mod.domain), set()).add(mod.required_level)
    wanted = {(mod.type, mod.generation_type, mod.domain) for mod in (data.mods[mod_id] for mod_id in _wanted_mods(target.requirements))}
    return {key: len(levels[key]) for key in sorted(wanted) if key in levels}


def stranded_offer_counts(data: GameData, target: Target) -> tuple[int, ...]:
    """The strand counts the target gets a buy offer at: where a cut class begins for a table it needs, in order."""
    return tuple(sorted({start for tiers in needed_tables(data, target).values() for start in cut_class_starts(tiers)}))


def stranded_offers(data: GameData, target: Target, prices: PriceFile, price_source: str = "both") -> StrandedOffers:
    """The stranded purchases of the target, priced from `prices` under `price_source`; one without a price is dropped with its reason."""
    offers, dropped = [], []
    for strands in stranded_offer_counts(data, target):
        spec = buy_spec_of(data, target, strands=strands)
        price = planned_price(prices, spec.name, price_source)
        if price is None:
            dropped.append(DroppedOffer(strands, spec.name, f"no price for the item with {strands} or more Memory Strands in the price file"))
        else:
            offers.append(StrandedOffer(strands, spec, price))
    return StrandedOffers(tuple(offers), tuple(dropped))
