"""The Jeweller's Orb, the Orb of Fusing and the bench's count and link crafts: the actions that change the sockets of a weapon or armour (ticket #228, B6 S2).

These are the finish actions of ADR-0045: they change the number of sockets (`JewellersOrb`, `BenchSocketCount`) or the link groups (`OrbOfFusing`,
`BenchSocketLinks`) and **nothing else**; every mod, the quality, the implicits and the colours of the sockets that stay are as they were. They
declare it with `Adds.socket_action` (the contract suite checks that no result differs from the item in a mod, and that an action which does
not declare `adds.socket_*` leaves the sockets alone), and they stay out of the compressed state of the mods (ADR-0045: the finish is solved on
its own state, ticket #231). So the four kinds are not planner kinds yet (`planner=False`): they are in the catalog and under the contract suite,
and the planner refuses a target with sockets until S5 attaches the finish. The Chromatic Orb, the Omen of Trichromatism and the colour crafts
are ticket #229 (S3), Binding and the beast recipes #232 (S6).

**The sockets of the item** are `Item.sockets` (ADR-0046): one colour per socket in socket order and the link groups as their sizes in the same
order, so a link group is a contiguous run. An item that states no sockets is refused as out of scope (`OutOfScopeError`): the one white socket
is assumed only for a target that names sockets (`Target.start_sockets_assumed`), and the planner will give the item its sockets before it asks.

**Refusals**, which spend nothing and name the reason: `NotApplicableError` for a corrupted item (the Tainted orbs and the bench crafts that cost
Vaal Orbs are B4's, ADR-0046), for jewellery and any class with no socket table, and for a use that does nothing the game allows (a Jeweller's Orb at
its maximum, an Orb of Fusing on one socket or on an item whose sockets are all linked, a bench craft that leaves the item as it is or asks for more
sockets than the class holds); `OutOfScopeError` for an item with an Abyssal-socket mod (no admitted rule says how those count) and for an Orb of
Fusing below 20% quality (the only table is the 20% one: below it the finish buys quality first, ADR-0049).

**The Jeweller's Orb** rerolls the number of sockets to a number **different from the current one**, never above the class maximum
(`sockets.class_maximum_sockets`) or the item-level gate (3 sockets from item level 2, 4 from 25, 5 from 35, 6 from 50), and is not usable at the
maximum. The weights are the item-generation table, renormalised without the current count: 50, 120, 100, 30, 5, 1 for 1 to 6 sockets on the
six- and three-socket classes, 100, 90, 80, 30 on the four-socket classes (`sockets.socket_count_weights`, wiki; `approximate`: that the orb uses
the generation weights is an inference). The **second reading** is GGG's 2014 table for the six- and three-socket classes, 100, 90, 80, 30, 5, 1
(`sockets.jeweller_second_reading_2014_table`): the rule axis `jeweller_table`, whose plan reading is the wiki table, so a model that asks for
all readings gets both (ADR-0033). Quality has no effect in the model (`sockets.jeweller_ignores_quality`, `approximate`, pessimistic). **The
sockets that stay keep their colours and links, new sockets are white and unlinked, and a lower count removes the last sockets** (the first keep
their colours, a link group is cut where the sockets end): the owner's answer for adding, the main chat's reading for removing
(`approximate`). With the **Omen of the Jeweller** (`omen=True`) the roll is the maximum of class and item level (exact).

**The Orb of Fusing** rerolls the link groups by **sequential group sizes** (`sockets.fusing_group_size_weights`, `approximate`): from the first
socket a group size is drawn from one weight table cut to the sockets that remain and renormalised, then the next group starts, until every socket
is placed. The table (a 2017 fit of 100,000 orbs) exists for 20% quality only, so the orb is offered at 20% quality or more and uses it above that.
It may leave the links as they were. With the **Omen of Connections** (`omen=True`) every socket is linked (exact). All linked has the chance
`w_n / (w_1 + ... + w_n)` for `n` sockets: 66.1, 33.7, 19.9, 0.83 and 0.10% for 2 to 6 (`SocketOutcomes.chance_all_linked`).

**The bench** sets the count exactly (2 to 6 for 1, 3, 10, 70, 350 Jeweller's Orbs; any item level, up to the class maximum) and the links exactly
(2 to 6 for 1, 3, 5, 150, 1500 Orbs of Fusing; the first N sockets become one group and the rest are unlinked, `approximate`), on the 20 classes of
the bench data (datamined, exact). A craft is priced as its orb count times the orb price, by the names of the game data (`resources`), as
`bench_craft.option_cost` does for the mod crafts. The count craft takes the Jeweller's rule for which sockets stay.

**Prices.** An orb or an Omen is priced by the name the game data gives it (`sockets.jewellers_orb_cost`, `sockets.fusing_cost`,
`sockets.omen_of_the_jeweller_cost`, `sockets.omen_of_connections_cost`; `prices.price_names` holds the same names); an offer whose price the file
lacks is dropped and reported with that name (ADR-0007). **Memory Strands** (ADR-0041): none of the four draws mods or spends strands, so each
declares `StrandUse.untouched`.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import cache, cached_property

from crafting_system.data import BenchOption, GameData
from crafting_system.items import Item, PlainQuality, SocketColour, Sockets, class_maximum, has_abyssal_socket
from crafting_system.rules import get_rule

from .bench import CurrencyCost
from .catalog import kind
from .contract import Action, Adds, Axis, Reading, Reads
from .errors import NotApplicableError, OutOfScopeError
from .finite import Finite
from .strand_use import CUT_FOLLOWS_SPEND_TABLE, NOT_SPENT_BY, StrandUse

__all__ = [
    "BenchSocketCount",
    "BenchSocketLinks",
    "JEWELLER_TABLE",
    "JewellersOrb",
    "OrbOfFusing",
    "SocketOutcomes",
    "fusing_links",
    "item_level_gate",
    "jeweller_weights",
    "resized_sockets",
]

CLASS_MAXIMUM = get_rule("sockets.class_maximum_sockets")
JEWELLER_REROLLS_COUNT = get_rule("sockets.jeweller_rerolls_count_to_a_different_number")
SOCKET_COUNT_WEIGHTS = get_rule("sockets.socket_count_weights")
SECOND_READING_2014 = get_rule("sockets.jeweller_second_reading_2014_table")
JEWELLER_IGNORES_QUALITY = get_rule("sockets.jeweller_ignores_quality")
KEEPS_OLD_SOCKETS = get_rule("sockets.jeweller_keeps_old_sockets_when_adding")
REMOVES_FROM_THE_END = get_rule("sockets.jeweller_removes_sockets_from_the_end")
ADDED_SOCKETS_ARE_WHITE = get_rule("sockets.added_sockets_are_white")
OMEN_OF_THE_JEWELLER = get_rule("sockets.omen_of_the_jeweller_max_sockets")
FUSING_REROLLS_LINKS_ONLY = get_rule("sockets.fusing_rerolls_links_only")
FUSING_GROUP_SIZE_WEIGHTS = get_rule("sockets.fusing_group_size_weights")
OMEN_OF_CONNECTIONS = get_rule("sockets.omen_of_connections_all_linked")
BENCH_SOCKET_COUNT_COST = get_rule("sockets.bench_socket_count_cost")
BENCH_LINK_COST = get_rule("sockets.bench_link_cost")
BENCH_LINK_MAKES_THE_FIRST_SOCKETS_ONE_GROUP = get_rule("sockets.bench_link_makes_the_first_sockets_one_group")
BENCH_ON_CORRUPTED_COSTS_VAAL = get_rule("sockets.bench_on_corrupted_costs_vaal")
JEWELLERS_ORB_COST = get_rule("sockets.jewellers_orb_cost")
FUSING_COST = get_rule("sockets.fusing_cost")
OMEN_OF_THE_JEWELLER_COST = get_rule("sockets.omen_of_the_jeweller_cost")
OMEN_OF_CONNECTIONS_COST = get_rule("sockets.omen_of_connections_cost")

ONE = Fraction(1)
FUSING_MIN_QUALITY = FUSING_GROUP_SIZE_WEIGHTS.value["at_quality"]  # the table is the 20% one
WIKI_TABLE, DEVELOPER_2014_TABLE = "wiki_developer_table", "chris_wilson_2014"
JEWELLER_TABLE = Axis("jeweller_table", (WIKI_TABLE, DEVELOPER_2014_TABLE), WIKI_TABLE)
WHY_NOT_PLANNER = (
    "a step of the socket finish (ADR-0045), which the compressed state of the mods does not hold; the finish is attached to the goal states "
    "by ticket #231 (B6 S5)"
)


@dataclass(frozen=True, eq=False)
class SocketOutcomes(Finite):
    """The finished items of a socket action, each with its probability; `chance_all` and `distribution` are those of every `Finite` (no mod changes).

    `by_sockets` lists the sockets the item can end with and `chance_all_linked` the chance that all of them are linked.
    """

    @cached_property
    def by_sockets(self) -> Mapping[Sockets, Fraction]:
        """The chance of each `Sockets` the item can end with; they sum to 1."""
        found: dict[Sockets, Fraction] = defaultdict(Fraction)
        for chance, result in self.results:
            found[result.sockets] += chance
        return dict(found)

    def chance_count(self, count: int) -> Fraction:
        """The chance that the finished item has exactly `count` sockets."""
        return sum((chance for sockets, chance in self.by_sockets.items() if sockets.count == count), Fraction(0))

    def chance_all_linked(self) -> Fraction:
        """The chance that the finished item has one link group holding every socket."""
        return sum((chance for sockets, chance in self.by_sockets.items() if len(sockets.links) == 1), Fraction(0))


def _outcomes(data: GameData, item: Item, results: Mapping[Sockets, Fraction]) -> SocketOutcomes:
    """The result items for the sockets in `results` (chances that sum to 1), the rest of the item as it was."""
    return SocketOutcomes(data, item, tuple((chance, item.changed(data, sockets=sockets)) for sockets, chance in results.items()))


def _accept(data: GameData, item: Item, what: str) -> tuple[Sockets, int]:
    """The sockets of `item` and the class maximum, or the refusal: corrupted, a class with no sockets, none stated, an Abyssal socket."""
    if item.corrupted:
        raise NotApplicableError(f"the item is corrupted, and a corrupted item takes no {what} (the Tainted orbs and the bench crafts on one are B4's)")
    base = data.base_items.get(item.base_id)
    most = class_maximum(base) if base is not None else None
    if most is None:
        item_class = base.item_class if base is not None else item.base_id
        raise NotApplicableError(f"a {what} works on a weapon or armour, and {item_class} takes no sockets")
    if item.sockets is None:
        raise OutOfScopeError(
            f"the item states no sockets, so a {what} has nothing to change; the one white socket is assumed only for a target that names sockets (ADR-0046)"
        )
    if has_abyssal_socket(data, item.base_id, tuple(entry.mod_id for entry in (*item.mods, *item.implicits))):
        raise OutOfScopeError("the item holds an Abyssal Socket, and no admitted rule says how an Abyssal Socket counts toward the sockets (ADR-0045)")
    return item.sockets, most


def item_level_gate(item_level: int) -> int:
    """The most sockets the Jeweller's Orb can give at `item_level`: 1 and 2 from item level 1, 3 from 2, 4 from 25, 5 from 35, 6 from 50."""
    minimum = SOCKET_COUNT_WEIGHTS.value["minimum_item_level"]
    return max((count for count, level in enumerate(minimum, 1) if item_level >= level), default=1)


def jeweller_weights(class_maximum_sockets: int, reading: Reading | None = None) -> tuple[int, ...]:
    """The weights of 1 to `class_maximum_sockets` sockets for the Jeweller's Orb at a reading of the table (the plan: the wiki's).

    The four-socket classes have a table of their own, the same in both readings; the six- and three-socket classes use the first
    `class_maximum_sockets` weights of the six-socket table, the wiki's or the 2014 one.
    """
    if class_maximum_sockets == 4:
        return tuple(SOCKET_COUNT_WEIGHTS.value["four"])
    second = reading is not None and reading.get(JEWELLER_TABLE.name, WIKI_TABLE) == DEVELOPER_2014_TABLE
    table = SECOND_READING_2014.value["six_or_three"] if second else SOCKET_COUNT_WEIGHTS.value["six_or_three"]
    return tuple(table[:class_maximum_sockets])


def resized_sockets(sockets: Sockets, count: int) -> Sockets:
    """`sockets` with `count` sockets: new ones are white and unlinked at the end, a lower count removes the last ones (ADR-0046).

    The sockets that stay keep their colours and links; a link group is cut where the sockets end.
    """
    if count >= sockets.count:
        added = count - sockets.count
        return Sockets((*sockets.colours, *([SocketColour.WHITE] * added)), (*sockets.links, *([1] * added)))
    links, left = [], count
    for size in sockets.links:
        if left <= 0:
            break
        links.append(min(size, left))
        left -= size
    return Sockets(sockets.colours[:count], tuple(links))


@cache
def _link_chances(count: int) -> Mapping[tuple[int, ...], Fraction]:
    """The chance of each tuple of link-group sizes of `count` sockets: sizes are drawn in turn from the Fusing weights cut to the sockets left."""
    weights = FUSING_GROUP_SIZE_WEIGHTS.value["parts_of_100000"]
    found: dict[tuple[int, ...], Fraction] = {(): ONE}
    for _ in range(count):
        step: dict[tuple[int, ...], Fraction] = defaultdict(Fraction)
        for sizes, chance in found.items():
            left = count - sum(sizes)
            if left == 0:
                step[sizes] += chance
                continue
            total = sum(weights[:left])
            for size in range(1, left + 1):
                step[(*sizes, size)] += chance * Fraction(weights[size - 1], total)
        found = step
    return dict(found)


def fusing_links(count: int) -> Mapping[tuple[int, ...], Fraction]:
    """The chance of each tuple of link-group sizes an Orb of Fusing leaves on `count` sockets (at 20% quality or more); they sum to 1."""
    if count < 1:
        raise ValueError(f"an item has at least one socket, got {count!r}")
    return _link_chances(count)


def _cost(data: GameData, option: BenchOption) -> tuple[CurrencyCost, ...]:
    entries = []
    for entry in option.cost:
        base = data.base_items.get(entry.item_id)
        if base is None:
            raise ValueError(f"the bench cost names {entry.item_id}, which is not a base item in the game data")
        entries.append(CurrencyCost(base.name, entry.count))
    return tuple(entries)


def _offered(data: GameData, item: Item, wanted) -> list[int]:
    """The numbers of the bench options that `wanted` reads (a socket count or a link count) and that are offered for the item class, in data order."""
    base = data.base_items.get(item.base_id)
    if base is None or class_maximum(base) is None:
        return []
    return [number for option in data.bench_options if (number := wanted(option)) is not None and base.item_class in option.item_classes]


@dataclass(frozen=True)
class JewellersOrb(Action):
    """One Jeweller's Orb, or one used with the Omen of the Jeweller (`omen=True`)."""

    omen: bool = False

    def label(self, data: GameData | None = None) -> str:
        return "Jeweller's Orb with Omen of the Jeweller" if self.omen else "Jeweller's Orb"

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.untouched(CUT_FOLLOWS_SPEND_TABLE)  # ADR-0041: it draws no mod and the wiki's strand table has no row for it

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        found = dict(JEWELLERS_ORB_COST.value)
        if self.omen:
            found.update(OMEN_OF_THE_JEWELLER_COST.value)
        return found

    def reads(self, data: GameData) -> Reads:
        """The count (the current one is excluded and the maximum refuses); the colours and links that stay are carried over, not read."""
        return Reads(junk=True, families=frozenset(), socket_count=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.socket_action(count=True)

    def rule_axes(self, data: GameData) -> tuple[Axis, ...]:
        """The Jeweller's table has a second reading (the 2014 numbers); the Omen rolls no table, so it has none."""
        return () if self.omen else (JEWELLER_TABLE,)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        found = {
            CLASS_MAXIMUM, JEWELLER_REROLLS_COUNT, JEWELLER_IGNORES_QUALITY, KEEPS_OLD_SOCKETS, REMOVES_FROM_THE_END, ADDED_SOCKETS_ARE_WHITE,
            JEWELLERS_ORB_COST,
        }
        found |= {OMEN_OF_THE_JEWELLER, OMEN_OF_THE_JEWELLER_COST} if self.omen else {SOCKET_COUNT_WEIGHTS, SECOND_READING_2014}
        return frozenset(rule.id for rule in found)

    def outcomes(self, data: GameData, item: Item, reading: Reading | None = None) -> SocketOutcomes:
        """The sockets the orb leaves: a count other than the current one, from 1 to the lesser of the class maximum and the item-level gate.

        Raises `NotApplicableError` for a corrupted item, a class with no sockets and an item at its maximum (the class maximum, or the
        count the item level allows), `OutOfScopeError` for an item with no stated sockets or an Abyssal Socket. With the Omen the roll is that
        maximum; without it the weights of the reading, renormalised without the current count. An item above the item-level gate (sockets
        from the bench) rolls among the counts the gate allows.
        """
        sockets, most = _accept(data, item, "Jeweller's Orb")
        reach = min(most, item_level_gate(item.item_level))
        if sockets.count == most or sockets.count == reach:
            raise NotApplicableError(f"the item has {sockets.count} sockets, the most a Jeweller's Orb can give it (class maximum {most}, item level {item.item_level}); it rerolls no item at its maximum")
        if self.omen:
            return _outcomes(data, item, {resized_sockets(sockets, reach): ONE})
        weights = jeweller_weights(most, reading)
        rolls = {count: weights[count - 1] for count in range(1, reach + 1) if count != sockets.count}
        total = sum(rolls.values())
        return _outcomes(data, item, {resized_sockets(sockets, count): Fraction(weight, total) for count, weight in rolls.items()})


@dataclass(frozen=True)
class OrbOfFusing(Action):
    """One Orb of Fusing, or one used with the Omen of Connections (`omen=True`)."""

    omen: bool = False

    def label(self, data: GameData | None = None) -> str:
        return "Orb of Fusing with Omen of Connections" if self.omen else "Orb of Fusing"

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.untouched(CUT_FOLLOWS_SPEND_TABLE)  # ADR-0041: it draws no mod and the wiki's strand table has no row for it

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        found = dict(FUSING_COST.value)
        if self.omen:
            found.update(OMEN_OF_CONNECTIONS_COST.value)
        return found

    def reads(self, data: GameData) -> Reads:
        """The count (the group sizes are cut to the sockets that remain), the links (an item that is all linked is refused) and the plain quality (20% or more)."""
        return Reads(junk=True, families=frozenset(), quality=True, socket_count=True, socket_links=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.socket_action(links=True)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        found = {CLASS_MAXIMUM, FUSING_REROLLS_LINKS_ONLY, FUSING_COST}
        found |= {OMEN_OF_CONNECTIONS, OMEN_OF_CONNECTIONS_COST} if self.omen else {FUSING_GROUP_SIZE_WEIGHTS, JEWELLER_IGNORES_QUALITY}
        return frozenset(rule.id for rule in found)

    def outcomes(self, data: GameData, item: Item) -> SocketOutcomes:
        """The link groups the orb leaves: sequential group sizes from the first socket (all linked with the Omen); the colours and the count stay.

        Raises `NotApplicableError` for a corrupted item, a class with no sockets, a one-socket item and an item whose sockets are all linked;
        `OutOfScopeError` for an item with no stated sockets or an Abyssal Socket, and for a weapon or armour below 20% quality (no table).
        """
        sockets, _ = _accept(data, item, "Orb of Fusing")
        if sockets.count == 1:
            raise NotApplicableError("the item has one socket, and an Orb of Fusing has nothing to link")
        if len(sockets.links) == 1:
            raise NotApplicableError("the sockets of the item are all linked, and an Orb of Fusing is not used on such an item")
        percent = item.quality.percent if isinstance(item.quality, PlainQuality) else 0
        if percent < FUSING_MIN_QUALITY:
            raise OutOfScopeError(
                f"the item has {percent}% quality; the only table of the Orb of Fusing is the one for {FUSING_MIN_QUALITY}% quality, "
                "so it is offered from there (below it the finish buys quality first, ADR-0049)"
            )
        if self.omen:
            return _outcomes(data, item, {Sockets(sockets.colours, (sockets.count,)): ONE})
        chances: dict[Sockets, Fraction] = {}
        for links, chance in fusing_links(sockets.count).items():
            chances[Sockets(sockets.colours, links)] = chance
        return _outcomes(data, item, chances)


@dataclass(frozen=True)
class BenchSocketCount(Action):
    """The bench craft that sets the number of sockets to `count` (2 to 6), for `count` Jeweller's Orbs of the option's price."""

    count: int

    def label(self, data: GameData | None = None) -> str:
        return f"Bench craft {self.count} sockets"

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.untouched(NOT_SPENT_BY, CUT_FOLLOWS_SPEND_TABLE)  # ADR-0041: a bench craft draws no mod and spends nothing

    def option(self, data: GameData) -> BenchOption:
        """The bench option that sets this count; `ValueError` when the data has none."""
        for option in data.bench_options:
            if option.actions.change_socket_count == self.count:
                return option
        raise ValueError(f"the bench has no option that sets {self.count} sockets")

    def cost(self, data: GameData) -> tuple[CurrencyCost, ...]:
        """The price of one craft, as currency names and counts."""
        return _cost(data, self.option(data))

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        if data is None:
            raise ValueError("a bench craft is priced from the bench data, so it needs the data")
        return {entry.currency: entry.count for entry in self.cost(data)}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset(), socket_count=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.socket_action(count=True)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        rules = (CLASS_MAXIMUM, BENCH_SOCKET_COUNT_COST, BENCH_ON_CORRUPTED_COSTS_VAAL, KEEPS_OLD_SOCKETS, REMOVES_FROM_THE_END, ADDED_SOCKETS_ARE_WHITE)
        return frozenset(rule.id for rule in rules)

    def outcomes(self, data: GameData, item: Item) -> SocketOutcomes:
        """The item with exactly `count` sockets: new ones white and unlinked, a lower count removes the last (the Jeweller's rule), any item level.

        Raises `NotApplicableError` for a corrupted item, a class the option is not offered for, a count above the class maximum and a count the
        item already has; `OutOfScopeError` for an item with no stated sockets or an Abyssal Socket.
        """
        option = self.option(data)
        sockets, most = _accept(data, item, "bench craft")
        base = data.base_items[item.base_id]
        if base.item_class not in option.item_classes:
            raise NotApplicableError(f"the bench does not offer {self.count} sockets for the item class {base.item_class}")
        if self.count > most:
            raise NotApplicableError(f"a {base.item_class} holds at most {most} sockets, and the craft sets {self.count}")
        if self.count == sockets.count:
            raise NotApplicableError(f"the item already has {self.count} sockets, so the craft would change nothing")
        return _outcomes(data, item, {resized_sockets(sockets, self.count): ONE})


@dataclass(frozen=True)
class BenchSocketLinks(Action):
    """The bench craft that links the first `links` sockets (2 to 6), for `links` Orbs of Fusing of the option's price."""

    links: int

    def label(self, data: GameData | None = None) -> str:
        return f"Bench craft {self.links} links"

    def strand_use(self, data: GameData | None = None) -> StrandUse:
        return StrandUse.untouched(NOT_SPENT_BY, CUT_FOLLOWS_SPEND_TABLE)  # ADR-0041: a bench craft draws no mod and spends nothing

    def option(self, data: GameData) -> BenchOption:
        """The bench option that links this many sockets; `ValueError` when the data has none."""
        for option in data.bench_options:
            if option.actions.link_sockets == self.links:
                return option
        raise ValueError(f"the bench has no option that links {self.links} sockets")

    def cost(self, data: GameData) -> tuple[CurrencyCost, ...]:
        """The price of one craft, as currency names and counts."""
        return _cost(data, self.option(data))

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        if data is None:
            raise ValueError("a bench craft is priced from the bench data, so it needs the data")
        return {entry.currency: entry.count for entry in self.cost(data)}

    def reads(self, data: GameData) -> Reads:
        """The count (the craft needs `links` sockets) and the links (a craft that leaves them as they are is refused)."""
        return Reads(junk=True, families=frozenset(), socket_count=True, socket_links=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.socket_action(links=True)

    def claims(self, data: GameData | None = None) -> frozenset[str]:
        rules = (CLASS_MAXIMUM, BENCH_LINK_COST, BENCH_LINK_MAKES_THE_FIRST_SOCKETS_ONE_GROUP, BENCH_ON_CORRUPTED_COSTS_VAAL)
        return frozenset(rule.id for rule in rules)

    def outcomes(self, data: GameData, item: Item) -> SocketOutcomes:
        """The item with its first `links` sockets in one group and the rest unlinked, the colours and the count as they were.

        Raises `NotApplicableError` for a corrupted item, a class the option is not offered for, an item with fewer sockets than `links` and
        a craft that would leave the links as they are; `OutOfScopeError` for an item with no stated sockets or an Abyssal Socket.
        """
        option = self.option(data)
        sockets, _ = _accept(data, item, "bench craft")
        base = data.base_items[item.base_id]
        if base.item_class not in option.item_classes:
            raise NotApplicableError(f"the bench does not offer {self.links} links for the item class {base.item_class}")
        if self.links > sockets.count:
            raise NotApplicableError(f"the item has {sockets.count} sockets, so it cannot have {self.links} of them linked")
        linked = Sockets(sockets.colours, (self.links, *([1] * (sockets.count - self.links))))
        if linked == sockets:
            raise NotApplicableError(f"the first {self.links} sockets of the item are already one group and the rest unlinked, so the craft would change nothing")
        return _outcomes(data, item, {linked: ONE})


@kind("jewellers-orb", order=100, planner=False, why_not=WHY_NOT_PLANNER, applies_only_to="weapon and armour")
def _jewellers_orb(data: GameData, item: Item):
    base = data.base_items.get(item.base_id)
    if base is not None and class_maximum(base) is not None:
        yield JewellersOrb()
        yield JewellersOrb(omen=True)


@kind("orb-of-fusing", order=101, planner=False, why_not=WHY_NOT_PLANNER, applies_only_to="weapon and armour")
def _orb_of_fusing(data: GameData, item: Item):
    base = data.base_items.get(item.base_id)
    if base is not None and class_maximum(base) is not None:
        yield OrbOfFusing()
        yield OrbOfFusing(omen=True)


@kind("bench-socket-count", order=102, planner=False, why_not=WHY_NOT_PLANNER, applies_only_to="weapon and armour")
def _bench_socket_counts(data: GameData, item: Item):
    for count in _offered(data, item, lambda option: option.actions.change_socket_count):
        yield BenchSocketCount(count)


@kind("bench-socket-links", order=103, planner=False, why_not=WHY_NOT_PLANNER, applies_only_to="weapon and armour")
def _bench_socket_links(data: GameData, item: Item):
    for links in _offered(data, item, lambda option: option.actions.link_sockets):
        yield BenchSocketLinks(links)
