"""The bought-base start options of a target, read from the price file (ADR-0061 decision 1, ticket #351).

The target's item level is a floor, not the level (ADR-0061, `targets.floor`): a belt that asks tier-1 resistances can be bought at
item level 84, and a base of 84 has a smaller pool than one of 86, so it can cost less to buy and to craft. `bought_base_starts` lists
one start option per **equal-pool group** of item levels from the floor up to 86 (levels with one pool are one plan), and per
**influence set** the target needs, each priced from the price file under the profile's price source. Nothing here plans: the choice
among the options is `_starts.plan_with_starts` (#359), and the realism rails that warn on an option are #353 (`StartCandidate.warnings`).

* **Levels.** `targets.floor.item_level_options` gives the floor and the groups; the groups run up to 86 (`TOP_ROW_LEVEL`, the highest
  level a poe.ninja base row has and the highest level any drawn mod needs), or to the file's level when that is higher. Each level of a
  group is looked up under its base price name (`targets.base_line_name`: "Leather Belt (ilvl 84)"), and the group's option is the
  cheapest level with a price (a tie goes to the lower level); the other priced levels are kept in `BoughtBase.priced`.
* **Influence sets.** The target's own set, and, when a requirement can only be met by the mods of an influence the start item lacks,
  that set too (the influenced row is then a start beside the plain one, ADR-0061: a base at a few Chaos against a conqueror Exalt). An
  influenced option is the same target with that influence on its start item; more than two influences is no item.
* **Price.** `prices.source_price` under the profile's `price_source` (`ninja`, `trade`, `both`): the trade price, the poe.ninja row as a
  marked fallback, or a hand override. No price from the chosen source means no option: the group is refused with the reason of each
  level (`NO_PRICE`). A poe.ninja row with fewer than 5 recorded observations (`MIN_COUNT`) is not a row (ADR-0061), and the option or the
  refusal says so with its count; a row whose count was not recorded is kept and marked.
* **Marks are never dropped** (OR-8 as amended by #718, OR-23): a thin or old trade price keeps its mark in `sourced.marks` and
  `price_mark`; the provenance of the price used (`prices.price_marks`: a depth below one unit, a previous league, a stand-in, "not recorded")
  is kept in `BoughtBase.input_marks`; under `both` the trade price and the poe.ninja row sit side by side with the gap flag.
* **The start item.** A base row prices a Normal base. A Rare start with no mods is that base plus one Orb of Alchemy, priced as a good
  of the option (OR-16: no hidden step; R08 and R09 say so). A Magic start is the item the market sells, with 1 or 2 mods (ADR-0064),
  which one Transmutation does not make (R13's file calls a Normal start plus one "a step the guide does not give"), so it is priced from
  the row alone and marked so (`MAGIC_ROW_MARK`, OR-23). An orb with no price leaves the option standing, marked (OR-23); a thin orb
  price is used, marked (OR-8). A start item that holds mods, is corrupted, or
  carries an enchantment, a memory strand or an imprint is not a plain base, and no row prices it (`NOT_A_PLAIN_BASE`). A given start (OR-6) buys
  nothing, so it has no bought-base option.
"""

import dataclasses
from collections.abc import Iterable
from datetime import date

from crafting_system.actions import OutOfScopeError
from crafting_system.actions.awakener import influence_mods
from crafting_system.data import GameData
from crafting_system.items import Influence, ItemError, Rarity
from crafting_system.items.model import MAX_ITEM_LEVEL
from crafting_system.prices import PriceEntry, PriceFile, SourcedPrice, planned_price, price_marks, source_price
from crafting_system.prices.fallbacks import MIN_COUNT
from crafting_system.prices.price_marks import OLD_THIN, THIN, units_text
from crafting_system.prices.price_names import INFLUENCES, canonical_price_name
from crafting_system.prices.price_source import USED_NINJA, USED_OVERRIDE, USED_TRADE, ninja_row
from crafting_system.prices.provenance import OBSERVATIONS
from crafting_system.targets import KOfN, StartKind, Target, TargetError, base_line_name, ninja_line_name, shared_name_refusal
from crafting_system.targets.floor import LevelGroup, item_level_options, level_groups, target_at_level

from ._start_options import StartContext, StartList
from ._start_types import (
    NO_PRICE,
    NO_INFLUENCED_BASE,
    NOT_A_PLAIN_BASE,
    SOURCE_BOUGHT_BASE,
    BoughtBase,
    NinjaRow,
    RefusedStart,
    StartCandidate,
)

TOP_ROW_LEVEL = 86  # the highest item level of a poe.ninja base row, and the highest level a drawn mod needs (research #337, section 2)
ORB_OF_ALCHEMY = "Orb of Alchemy"
RARITY_ORB = {Rarity.NORMAL: None, Rarity.MAGIC: None, Rarity.RARE: ORB_OF_ALCHEMY}
MAGIC_ROW_MARK = "price of the Normal base row: the start item is a Magic base as the market sells it, with 1 or 2 mods, which no base row prices"
_GAME_ORDER = {name.lower(): index for index, name in enumerate(INFLUENCES)}


def _shown(influences: Iterable[Influence]) -> tuple[str, ...]:
    """Influences in game order, as the price file writes them ("Shaper", "Elder")."""
    return tuple(sorted((each.value.capitalize() for each in influences), key=lambda name: _GAME_ORDER[name.lower()]))


def _not_plain(target: Target) -> str | None:
    """Why the start item is not a plain base a row can price, or None when it is one."""
    item = target.start_item
    found = [
        words
        for words, there in (
            ("holds mods", bool(item.mods)),
            ("is corrupted", item.corrupted),
            ("carries an enchantment", item.enchantment is not None),
            ("holds memory strands", item.memory_strands > 0),
            ("carries imprints", bool(item.imprints)),
            (f"is {item.rarity.value}", item.rarity not in RARITY_ORB),
        )
        if there
    ]
    if not found:
        return None
    return f"the start item {' and '.join(found)}; a base row prices a plain Normal base"


def needed_influence_sets(data: GameData, target: Target) -> tuple[tuple[frozenset[Influence], ...], str | None]:
    """The influence sets a bought base may have (the start item's own, then the set a requirement needs that the start lacks), and why a set was left out.

    A top-level requirement (not a member of an `at_least` group) needs an influence when every mod it counts is an influence mod of
    it on this base (`actions.awakener.influence_mods`). An item class with no influence key in the model has only its own set. A set
    of more than two influences is no item: it is left out. The second value says why a set was not listed (a model gap, too many
    influences), None when nothing was left out.
    """
    own = frozenset(target.influences)
    needed = set(own)
    pools: dict[Influence, frozenset[str]] = {}
    for requirement in target.requirements:
        if isinstance(requirement, KOfN) or not requirement.mod_ids:
            continue
        for influence in Influence:
            if influence not in pools:
                try:
                    pools[influence] = frozenset(influence_mods(data, target.base_id, MAX_ITEM_LEVEL, influence))
                except OutOfScopeError:  # a model gap: the item class has no influence key, so its influence mods are not modelled
                    kind = data.base_items[target.base_id].item_class
                    return (own,), f"the item class {kind} has no influence key in the model, so no requirement is checked for an influence mod"
            if requirement.mod_ids <= pools[influence]:
                needed.add(influence)
    wider = frozenset(needed)
    if len(wider) > 2:
        return (own,), f"the requirements need {len(wider)} influences ({', '.join(_shown(wider))}); an item holds at most two"
    return ((own,) if wider == own else (own, wider)), None


def _with_influences(data: GameData, target: Target, influences: frozenset[Influence]) -> Target:
    if influences == target.influences:
        return target
    return dataclasses.replace(target, influences=influences, start_item=target.start_item.changed(data, influences=influences))


def _observations(entry: PriceEntry) -> float | None:
    """The observation count a poe.ninja row rests on, or None when it was not recorded."""
    p = entry.provenance
    return p.depth if p is not None and p.depth is not None and p.depth_unit == OBSERVATIONS else None


def _without_thin_row(prices: PriceFile, name: str) -> tuple[PriceFile, PriceEntry | None, str | None]:
    """The price file with `name`'s poe.ninja row taken out when it rests on fewer than `MIN_COUNT` recorded observations, the row kept,
    and the words that say a row was taken out (None when none was)."""
    name = canonical_price_name(name)
    row = ninja_row(prices, name)
    if row is None:
        return prices, None, None
    seen = _observations(row)
    if seen is None or seen >= MIN_COUNT:
        return prices, row, None
    ninja = {key: value for key, value in prices.ninja.items() if key != name}
    kept = {key: value for key, value in prices.prices.items() if not (key == name and value is row)}
    words = f"the poe.ninja row {name} rests on {units_text(seen)} observations, under {MIN_COUNT}, so it is not a row"
    return dataclasses.replace(prices, prices=kept, ninja=ninja), None, words


def _used_entry(sourced: SourcedPrice, prices: PriceFile, row: PriceEntry | None) -> PriceEntry | None:
    """The price-file entry the planner's price came from (the trade price, the poe.ninja row or the hand override)."""
    if sourced.used == USED_TRADE and sourced.trade is not None:
        return sourced.trade.entry
    if sourced.used == USED_NINJA:
        return row
    if sourced.used == USED_OVERRIDE:
        return prices.prices.get(sourced.name)
    return None


def _input_marks(sourced: SourcedPrice, prices: PriceFile, row: PriceEntry | None) -> tuple[str, ...]:
    """Why the price used is an approximate input for one unit bought; the OR-8 mark of a trade price is left to `sourced.marks`."""
    entry = _used_entry(sourced, prices, row)
    if entry is None:
        return ()
    said = sourced.trade is not None and sourced.trade.mark is not None
    return tuple(mark.reason for mark in price_marks(entry, prices, 1.0) if not (said and mark.code in (THIN, OLD_THIN)))


class _Level:
    """One item level of a group, priced (or not) under the profile's price source."""

    def __init__(self, context: StartContext, target: Target, level: int, today: date) -> None:
        data = context.data
        self.level = level
        self.target = target_at_level(data, target, level)
        self.name = base_line_name(data, self.target)
        self.notes: list[str] = []  # what was read and not used: a thin poe.ninja row, a shared name's refused line
        view, row, note = _without_thin_row(context.prices, self.name)
        self.notes.extend([note] if note else [])
        sourced = source_price(view, self.name, context.price_source, today, gap_threshold=context.gap_percent)
        line = ninja_line_name(data, self.target)
        if not sourced.offered and line != self.name:  # a shared name: the poe.ninja line has no base id (`shared_name_refusal`)
            refusal = shared_name_refusal(data, target.base_id, "poe.ninja", line)
            if refusal is None:
                view, row, note = _without_thin_row(context.prices, line)
                self.notes.extend([note] if note else [])
                sourced = source_price(view, line, context.price_source, today, gap_threshold=context.gap_percent)
                self.name = line
            elif ninja_row(context.prices, line) is not None:
                self.notes.append(refusal)
        self.view, self.row, self.sourced = view, row, sourced

    @property
    def chaos(self) -> float | None:
        return self.sourced.chaos


def _label(target: Target, data: GameData, level: int, influences: tuple[str, ...], group: LevelGroup) -> str:
    base = data.base_items[target.base_id].name
    shown = f", {'/'.join(influences)}" if influences else ""
    span = f"level {group.lowest} has a pool of its own" if group.lowest == group.highest else f"levels {group.lowest} to {group.highest} have one pool"
    return f"{base}, item level {level}{shown} (bought base; {span})"


def _option(context: StartContext, group: LevelGroup, levels: list[_Level], influences: tuple[str, ...]) -> StartCandidate | RefusedStart:
    """The cheapest priced level of `group` as a start option, or the refusal that says why no level has a price."""
    data = context.data
    key = f"base:{group.lowest}-{group.highest}" + (f":{'/'.join(influences)}" if influences else "")
    priced = sorted((each for each in levels if each.chaos is not None), key=lambda each: (each.chaos, each.level))
    if not priced:
        why = "; ".join(f"{each.name}: {'; '.join([str(each.sourced.reason), *each.notes])}" for each in levels)
        return RefusedStart(key, _label(levels[0].target, data, levels[0].level, influences, group), NO_PRICE, f"no price from the price source {context.price_source}: {why}")
    best = priced[0]
    assert best.chaos is not None
    sourced = best.sourced
    item = best.target.start_item
    goods: list[tuple[str, int, float, str]] = [(best.name, 1, best.chaos, sourced.source_label)]
    # every level's notes, not only the chosen one's: a cheaper level whose thin row was set aside is said (OR-8, OR-23)
    marks = [*_input_marks(sourced, best.view, best.row), *(note for each in levels for note in each.notes)]
    if item.rarity is Rarity.MAGIC:
        marks.append(MAGIC_ROW_MARK)
    orb = RARITY_ORB[item.rarity]
    if orb is not None:
        planned = planned_price(context.prices, orb, context.price_source)
        if planned is None:  # OR-23: the option stands on its best estimate, marked, not dropped over a cheap orb
            marks.append(f"no price for {orb}: the step that makes the Normal base {item.rarity.value} is not counted")
        else:
            goods.append((orb, 1, planned.chaos, planned.source))
            if planned.mark is not None:
                marks.append(f"{orb}: {planned.mark}")
            said = planned.mark is not None
            marks.extend(f"{orb}: {m.reason}" for m in price_marks(planned.entry, context.prices, 1.0) if not (said and m.code in (THIN, OLD_THIN)))
    observations = None if best.row is None else _observations(best.row)
    ninja = None if best.row is None else NinjaRow(best.name, best.row.chaos, observations)
    bought = BoughtBase(
        level=best.level, group=(group.lowest, group.highest), influences=influences, row_name=best.name, row_chaos=best.chaos,
        ninja=ninja, trade_chaos=sourced.trade_chaos, input_marks=tuple(dict.fromkeys(marks)), rarity_orb=orb,
        priced=tuple(sorted((each.level, each.chaos) for each in priced if each.chaos is not None)),
    )  # fmt: skip
    mark = sourced.trade.mark if sourced.used == USED_TRADE and sourced.trade is not None else None
    label = _label(best.target, data, best.level, influences, group)
    return StartCandidate(
        key=key, source=SOURCE_BOUGHT_BASE, label=label, item=item, price=sum(part[2] for part in goods), price_name=best.name,
        price_source=" + ".join(f"{count} {name} [{source}]" for name, count, _, source in goods), goods=tuple(goods),
        sourced=sourced, price_mark=mark, bought=bought,
    )  # fmt: skip


def bought_base_starts(context: StartContext) -> StartList:
    """The bought-base start options of the target: one per equal-pool group of levels from the floor to 86 and per influence set.

    A group with no priced level is refused (`NO_PRICE`, with each level's reason); a start item no base row prices is refused once
    (`NOT_A_PLAIN_BASE`). A target whose start is given (OR-6) buys nothing and lists nothing.
    """
    data, target = context.data, context.target
    if target.start is not StartKind.BOUGHT:
        return StartList()
    problem = _not_plain(target)
    if problem is not None:
        return StartList(refused=(RefusedStart("base", "bought base", NOT_A_PLAIN_BASE, problem),))
    today = context.today if context.today is not None else context.prices.fetched_at.date()
    top = max(target.item_level, TOP_ROW_LEVEL)
    candidates: list[StartCandidate] = []
    refused: list[RefusedStart] = []
    sets, too_many = needed_influence_sets(data, target)
    if too_many is not None:
        refused.append(RefusedStart("base:influence", "bought base with an influence", NO_INFLUENCED_BASE, too_many))
    for influences in sets:
        try:
            shaped = target_at_level(data, _with_influences(data, target, influences), top)
            floor = item_level_options(data, shaped).floor.level  # the floor of the target the levels are planned from (R14: 81, its file says 78)
        except (ItemError, TargetError) as error:
            refused.append(RefusedStart("base", "bought base", NOT_A_PLAIN_BASE, f"the start item cannot be had with {sorted(i.value for i in influences)} at item level {top}: {error}"))
            continue
        shown = _shown(influences)
        for group in level_groups(data, shaped, floor):
            levels: list[_Level] = []
            for level in range(group.lowest, min(group.highest, top) + 1):
                try:
                    levels.append(_Level(context, shaped, level, today))
                except (ItemError, TargetError) as error:  # a level the target cannot be planned at is said, never a crash
                    key = f"base:{group.lowest}-{group.highest}" + (f":{'/'.join(shown)}" if shown else "")
                    refused.append(RefusedStart(key, f"bought base at item level {level}", NOT_A_PLAIN_BASE, str(error)))
            if levels:
                found = _option(context, group, levels, shown)
                (candidates if isinstance(found, StartCandidate) else refused).append(found)
    return StartList(tuple(candidates), tuple(refused))
