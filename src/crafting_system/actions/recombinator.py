"""The Kingsmarch recombinator, unpredictable mode, as an exact two-input action (ADR-0033, ticket #215).

The item in hand and the **donor** (an input, a `Need`, ADR-0022) are two magic or rare items of one item class, neither corrupted,
neither a jewel (`recombinator.jewels_refused`); both are destroyed and a new item is made (`recombinator.both_inputs_consumed`).

* **The base.** Each input is the base of the output with probability 1/2 (`recombinator.base_chosen_even`). The output copies from
  it its base type, influences, enchantment, quality and implicits (`recombinator.properties_from_chosen_base`); its item level is
  `min(floor((A + B) / 2 + 2), max(A, B))` (`recombinator.item_level_formula`) and its rarity follows its mods (normal with none,
  magic with at most one per side, rare otherwise; `recombinator.output_rarity_follows_mods`, approximate). Memory Strands are not
  modelled (`recombinator.memory_strands_stay_with_base`). A picked mod keeps its tier and its roll from its input: no source says
  they are rerolled (Craft of Exile's stale recombinator rerolls them).
* **The pools and the count.** The prefixes of both inputs form one pool, the suffixes another, and a mod on both inputs enters its
  pool twice (**doubling**, `recombinator.duplicates_enter_pool`). The number of mods kept on a side depends only on its pooled
  count (`recombinator.count_table`, the guide's figures renormalised to sum to 1; the wiki's rounding of the same table is the
  second table, `table="wiki"`); the sides are independent except that one prefix on one input and one suffix on the other
  give 1p, 1s or 1p1s, a third each (`recombinator.pools_per_side`). The output holds at most the base's capacity per side
  (`recombinator.output_capped_by_chosen_base`).
* **Which mods.** One side is filled first, 1/2 each (`recombinator.side_filled_first_even`); on a side the kept mods are drawn
  one at a time, without replacement, with chance proportional to `weight ** alpha` (`recombinator.selection_weighted_formula_unknown`,
  the rule axis `recombinator.alpha`, the plan at 1), and each pick closes every mod of its mod group in both pools
  (`recombinator.mod_group_exclusion`). The weight is the spawn weight of the mod on the chosen base. A side keeps fewer mods than
  the table says when its eligible mods run out. The exponent is a free parameter of the kernel: any reading is accepted, the grid
  of the axis is the set of values the planner uses.
* **Mods outside the plain rule.** A non-native mod (it spawns on its own input but not on the chosen base: an influenced or
  base-bound mod) counts in the pooled count and cannot appear (`recombinator.nnn_needs_native_base`); a fractured mod counts always
  but is eligible only if its own input is the base. An exclusive mod (crafted, essence-only, or one its own input could not roll
  naturally: a beast aspect, a Breach or Incursion mod) counts once per side in the pooled count
  (`recombinator.exclusive_counts_once_report_3_27`), is drawn at the weight of `recombinator.exclusive_mod_weight`, and once one is
  picked the other exclusive mods of both pools are ineligible (`recombinator.one_exclusive_per_item`). Several exclusive mods on one
  side each draw at that weight, though they count once in the pooled count.

Refusals. `NotApplicableError`: an item that is normal or corrupted, a jewel, or two items of different item classes. `OutOfScopeError`:
a veiled mod on either input (its unveil offer would have to be carried over, which no source describes) and a pooled count above 6 (the
count table has no row).

The catalog lists the kind for an item in hand with two donors (a copy of the item, and a donor of other mods the base can roll); it
is not a planner kind until the solver prices donors (#211, #212), the interval driver exists (#220) and the state of the
recombinator is built (#217). The cost of one use is `recombinator.cost_per_combine` until ticket #216 prices it.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from itertools import product

from crafting_system.data import GameData
from crafting_system.items import ExplicitMod, Item, Rarity, Side, capacity, spawn_weight
from crafting_system.rules import get_rule

from .catalog import kind
from .contract import Action, Adds, Axis, Need, Reading, Reads
from .draw import jewel_class
from .errors import NotApplicableError, OutOfScopeError
from .finite import Finite
from .pool import drawable_mod_ids, item_tags, tiers_of

__all__ = ["Recombinator"]

TWO_ITEMS = get_rule("recombinator.inputs_magic_or_rare_same_class")
CORRUPTED_REFUSED = get_rule("recombinator.corrupted_refused")
JEWELS_REFUSED = get_rule("recombinator.jewels_refused")
BOTH_CONSUMED = get_rule("recombinator.both_inputs_consumed")
BASE_EVEN = get_rule("recombinator.base_chosen_even")
FROM_CHOSEN_BASE = get_rule("recombinator.properties_from_chosen_base")
ITEM_LEVEL = get_rule("recombinator.item_level_formula")
RARITY = get_rule("recombinator.output_rarity_follows_mods")
POOLS_PER_SIDE = get_rule("recombinator.pools_per_side")
COUNT_TABLE = get_rule("recombinator.count_table")
COUNT_TABLE_WIKI = get_rule("recombinator.count_table_wiki")
CAPPED_BY_BASE = get_rule("recombinator.output_capped_by_chosen_base")
DOUBLING = get_rule("recombinator.duplicates_enter_pool")
GROUP_CLOSES = get_rule("recombinator.mod_group_exclusion")
SIDE_FIRST_EVEN = get_rule("recombinator.side_filled_first_even")
NON_NATIVE = get_rule("recombinator.nnn_needs_native_base")
ONE_EXCLUSIVE = get_rule("recombinator.one_exclusive_per_item")
EXCLUSIVE_ONCE = get_rule("recombinator.exclusive_counts_once_report_3_27")
EXCLUSIVE_WEIGHT = get_rule("recombinator.exclusive_mod_weight")
SELECTION = get_rule("recombinator.selection_weighted_formula_unknown")
COST = get_rule("recombinator.cost_per_combine")

ALPHA_AXIS = Axis(
    "recombinator.alpha",
    tuple(Fraction(str(value)) for value in SELECTION.value["grid"]),
    Fraction(str(SELECTION.value["plan"])),
)
"""The selection exponent: the grid of ADR-0033, the plan at 1."""

TABLES = {"guide": COUNT_TABLE, "wiki": COUNT_TABLE_WIKI}
MAX_POOLED = 6
MAX_EXPONENT = 16
EXCLUSIVE_DOMAINS = frozenset({"crafted", "delve"})
VEILED_DOMAIN = "veiled"
WHY_NOT_PLANNER = (
    "the solver takes no donors yet (#211, #212), the interval over its rule axis does not exist (#220) "
    "and the recombinator has no compressed state (#217)"
)


@cache
def count_table(name: str = "guide") -> Mapping[int, Mapping[int, Fraction]]:
    """The count table by pooled count, each row renormalised to sum to exactly 1: `{pooled: {kept: chance}}` (row 0 keeps none)."""
    rows = {0: {0: Fraction(1)}}
    for pooled, row in TABLES[name].value.items():
        exact = {kept: Fraction(str(percent)) for kept, percent in row.items()}
        total = sum(exact.values())
        rows[pooled] = {kept: percent / total for kept, percent in exact.items()}
    return rows


def effective_weight(weight: int, alpha: Fraction) -> Fraction:
    """`weight ** alpha` as an exact fraction: exact for a whole exponent, the float power taken exactly otherwise."""
    if alpha.denominator == 1:
        return Fraction(weight) ** alpha.numerator
    return Fraction(float(weight) ** float(alpha))


@dataclass(frozen=True)
class _Entry:
    """One mod of one input in a pool."""

    source: int  # 0 the item in hand, 1 the donor
    mod: ExplicitMod
    side: Side
    families: frozenset[str]
    exclusive: bool


def _pool_ids(entries: list[_Entry], side: Side) -> list[int]:
    return [index for index, entry in enumerate(entries) if entry.side is side]


@dataclass(frozen=True)
class Recombinator(Action):
    """One use of the recombinator on the item in hand with the donor `donor` (the item the donor must be when it is used).

    `table` is the count table, `"guide"` (the plan) or `"wiki"` (the sensitivity run).
    """

    donor: Item
    table: str = "guide"

    def __post_init__(self) -> None:
        if self.table not in TABLES:
            raise ValueError(f"the count table {self.table!r} is not one of {sorted(TABLES)}")

    @property
    def variant(self) -> str:
        mods = ",".join(
            f"{entry.mod_id}:{entry.tier}:{'/'.join(map(str, entry.values))}{'!' if entry.fractured else ''}{'*' if entry.crafted else ''}"
            for entry in self.donor.mods
        )
        influences = ",".join(sorted(influence.value for influence in self.donor.influences))
        return f"{self.donor.base_id} {self.donor.item_level} {self.donor.rarity.value} [{influences}] {mods} {self.table}"

    def label(self, data: GameData | None = None) -> str:
        if data is None:
            raise ValueError("a recombinator is named by the mods of its donor, so it needs the data")
        texts = []
        for entry in self.donor.mods:
            mod = data.mods.get(entry.mod_id)
            if mod is None:
                raise ValueError(f"the donor holds a mod ({entry.mod_id}) that is not in the game data")
            texts.append(" ".join((mod.text or mod.name or mod.id).split()))
        suffix = " (wiki count table)" if self.table == "wiki" else ""
        return f"Recombinator with a donor of {', '.join(sorted(texts))}{suffix}"

    def resources(self, data: GameData | None = None) -> Mapping[str, int]:
        return dict(COST.value)

    def reads(self, data: GameData) -> Reads:
        """Every mod of both inputs (the pool), and the implicits and the quality of the base."""
        return Reads(junk=True, families=None, input_mods=True, implicits=True, quality=True)

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        """Mods of the donor and of the item; a fractured mod of the base stays fractured; the implicits, the quality and the enchantment follow the base."""
        return Adds(draws=True, fractures=True, implicits=True, quality=True, enchantment=True)

    def inputs(self, data: GameData, item: Item | None = None) -> tuple[Need, ...]:
        """The donor: it starts as a bare item of its base and influences and must become `donor`."""
        start = Item.build(
            data,
            base_id=self.donor.base_id,
            item_level=self.donor.item_level,
            rarity=Rarity.NORMAL,
            influences=self.donor.influences,
        )
        return (Need(start, self.donor),)

    def rule_axes(self, data: GameData) -> tuple[Axis, ...]:
        return (ALPHA_AXIS,)

    # --- the refusals ---------------------------------------------------------------------------

    def _check(self, data: GameData, given: Item, who: str) -> None:
        if given.corrupted:
            raise NotApplicableError(f"the {who} is corrupted, and the recombinator refuses a corrupted item (3.26)")
        if given.rarity is Rarity.NORMAL:
            raise NotApplicableError(f"the {who} is a normal item, and the recombinator takes magic or rare items")
        if jewel_class(data, given) is not None:
            raise NotApplicableError(f"the {who} is a jewel, and jewels do not go into the recombinator")
        for entry in given.mods:
            if data.mods[entry.mod_id].domain == VEILED_DOMAIN:
                raise OutOfScopeError(
                    f"the {who} holds a veiled mod; its unveil offer would have to be carried over, and no source describes how"
                )

    # --- the result -----------------------------------------------------------------------------

    def outcomes(self, data: GameData, item: Item, reading: Reading | None = None) -> Finite:
        """The result of using the recombinator on `item` and the donor, at a reading of the selection exponent (the plan's when None)."""
        value = (reading if reading is not None else Reading()).get(ALPHA_AXIS.name, ALPHA_AXIS.plan)
        try:
            alpha = Fraction(value)  # type: ignore[arg-type]
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f"{value!r} is not a number: the reading of {ALPHA_AXIS.name} is an exponent") from None
        if abs(alpha) > MAX_EXPONENT:
            raise ValueError(f"the exponent {value!r} is far outside the fitted range (at most {MAX_EXPONENT} in size)")
        inputs = (item, self.donor)
        self._check(data, item, "item in hand")
        self._check(data, self.donor, "donor")
        classes = {data.base_items[given.base_id].item_class for given in inputs}
        if len(classes) != 1:
            raise NotApplicableError(f"the recombinator takes two items of one item class, got {' and '.join(sorted(classes))}")
        results: dict[Item, Fraction] = {}
        for base_index in (0, 1):
            for result, chance in self._with_base(data, inputs, base_index, alpha).items():
                results[result] = results.get(result, Fraction(0)) + chance / 2
        return Finite(data, item, tuple((chance, result) for result, chance in results.items()))

    def _entries(self, data: GameData, inputs: tuple[Item, Item]) -> list[_Entry]:
        tags = [item_tags(data, given) for given in inputs]
        entries = []
        for source, given in enumerate(inputs):
            for mod in given.mods:
                found = data.mods[mod.mod_id]
                exclusive = (
                    mod.crafted
                    or found.domain in EXCLUSIVE_DOMAINS
                    or found.is_essence_only
                    or spawn_weight(found, tags[source]) == 0  # its own input could not roll it
                )
                entries.append(_Entry(source, mod, Side(found.generation_type), frozenset(found.families), exclusive))
        return entries

    def _with_base(self, data: GameData, inputs: tuple[Item, Item], base_index: int, alpha: Fraction) -> dict[Item, Fraction]:
        """The results (with chances that sum to 1) when `inputs[base_index]` is the base."""
        base = inputs[base_index]
        base_tags = item_tags(data, base)
        entries = self._entries(data, inputs)
        pooled: dict[Side, int] = {}
        weights: dict[int, Fraction] = {}  # the eligible entries and their draw weights
        for side in Side:
            members = _pool_ids(entries, side)
            exclusive = [index for index in members if entries[index].exclusive]
            pooled[side] = len(members) - len(exclusive) + (1 if exclusive else 0)
            if pooled[side] > MAX_POOLED:
                raise OutOfScopeError(f"the pooled count of the {side.value}es is {pooled[side]} and the count table has rows to {MAX_POOLED} only")
        for index, entry in enumerate(entries):
            if entry.mod.fractured and entry.source != base_index:
                continue  # a fractured mod counts only if its own base is chosen
            if entry.exclusive:
                weights[index] = effective_weight(EXCLUSIVE_WEIGHT.value, alpha)
                continue
            native = spawn_weight(data.mods[entry.mod.mod_id], base_tags)
            if native > 0:
                weights[index] = effective_weight(native, alpha)
        counts = self._counts(data, inputs, base, pooled)
        picks: dict[frozenset[int], Fraction] = {}
        for (kept_prefix, kept_suffix), chance in counts.items():
            for first in (Side.PREFIX, Side.SUFFIX):
                order = (first, Side.SUFFIX if first is Side.PREFIX else Side.PREFIX)
                wanted = {Side.PREFIX: kept_prefix, Side.SUFFIX: kept_suffix}
                for chosen, drawn in _draw_sides(entries, weights, order, wanted).items():
                    picks[chosen] = picks.get(chosen, Fraction(0)) + chance * drawn / 2
        level = min((inputs[0].item_level + inputs[1].item_level) // 2 + 2, max(inputs[0].item_level, inputs[1].item_level))
        results: dict[Item, Fraction] = {}
        for chosen, chance in picks.items():
            mods = tuple(entries[index].mod for index in sorted(chosen))
            per_side = [sum(1 for index in chosen if entries[index].side is side) for side in Side]
            rarity = Rarity.NORMAL if not mods else Rarity.RARE if max(per_side) > 1 else Rarity.MAGIC
            # the output is a new item: no imprint of the base restores it (imprint.not_for_derived_items, ticket #219)
            result = base.changed(data, item_level=level, rarity=rarity, mods=mods, corrupted=False, veil_offer=(), imprints=())
            results[result] = results.get(result, Fraction(0)) + chance
        return results

    def _counts(self, data: GameData, inputs: tuple[Item, Item], base: Item, pooled: Mapping[Side, int]) -> dict[tuple[int, int], Fraction]:
        """The joint chance of the number of mods kept on the prefix and the suffix side, capped by the base's capacity."""
        room = capacity(data, base.base_id, Rarity.RARE)
        table = count_table(self.table)
        sides = [{Side(data.mods[entry.mod_id].generation_type) for entry in given.mods} for given in inputs]
        one_each = all(len(given.mods) == 1 for given in inputs) and sides[0] != sides[1]
        if one_each:  # one prefix on one input, one suffix on the other: 1p, 1s or 1p1s, a third each
            joint = {(1, 0): Fraction(1, 3), (0, 1): Fraction(1, 3), (1, 1): Fraction(1, 3)}
        else:
            joint = {
                (kp, ks): table[pooled[Side.PREFIX]][kp] * table[pooled[Side.SUFFIX]][ks]
                for kp, ks in product(table[pooled[Side.PREFIX]], table[pooled[Side.SUFFIX]])
            }
        capped: dict[tuple[int, int], Fraction] = {}
        for (kp, ks), chance in joint.items():
            key = (min(kp, room.prefix), min(ks, room.suffix))
            capped[key] = capped.get(key, Fraction(0)) + chance
        return capped


def _draw_sides(
    entries: list[_Entry], weights: Mapping[int, Fraction], order: tuple[Side, Side], wanted: Mapping[Side, int]
) -> dict[frozenset[int], Fraction]:
    """The chance of each set of picked entries when the sides are filled in `order`, `wanted[side]` picks on each."""
    found: dict[frozenset[int], Fraction] = {}

    def step(stage: int, left: int, picked: tuple[int, ...], chance: Fraction) -> None:
        side = order[stage]
        if left == 0:
            if stage == 0:
                step(1, wanted[order[1]], picked, chance)
            else:
                key = frozenset(picked)
                found[key] = found.get(key, Fraction(0)) + chance
            return
        closed_ids = {entries[index].mod.mod_id for index in picked}
        closed_families = set().union(*(entries[index].families for index in picked)) if picked else set()
        exclusive_taken = any(entries[index].exclusive for index in picked)
        eligible = [
            index
            for index in _pool_ids(entries, side)
            if index in weights
            and index not in picked
            and entries[index].mod.mod_id not in closed_ids
            and not entries[index].families & closed_families
            and not (exclusive_taken and entries[index].exclusive)
        ]
        if not eligible:  # the pool ran dry: the side keeps fewer mods
            step(stage, 0, picked, chance)
            return
        total = sum(weights[index] for index in eligible)
        for index in eligible:
            step(stage, left - 1, (*picked, index), chance * weights[index] / total)

    step(0, wanted[order[0]], (), Fraction(1))
    return found


def _complement(data: GameData, item: Item) -> Item | None:
    """A donor of other mods the item's base can roll: up to two prefixes and two suffixes of distinct families, none the item holds."""
    held = {family for entry in item.mods for family in data.mods[entry.mod_id].families}
    held |= {entry.mod_id for entry in item.mods}
    tiers = tiers_of(data, item)
    picked: list[ExplicitMod] = []
    taken: set[str] = set(held)
    per_side = {side: 0 for side in Side}
    for mod_id in sorted(drawable_mod_ids(data, item)):
        mod = data.mods[mod_id]
        side = Side(mod.generation_type)
        if per_side[side] >= 2 or mod_id in held or taken & set(mod.families):
            continue
        per_side[side] += 1
        taken |= set(mod.families)
        picked.append(ExplicitMod(mod_id, tiers.get(mod_id, 1), tuple(min(stat.min, stat.max) for stat in mod.stats)))
    if not picked:
        return None
    rarity = Rarity.RARE if max(per_side.values()) > 1 else Rarity.MAGIC
    return Item.build(
        data, base_id=item.base_id, item_level=item.item_level, rarity=rarity, mods=tuple(picked), influences=item.influences
    )


@kind("recombinator", order=89, planner=False, why_not=WHY_NOT_PLANNER, reads_item_state_while_not_planner="any")
def _recombinators(data: GameData, item: Item):
    """A copy of the item as the donor (every mod doubled), and a donor of other mods the base can roll."""
    if item.corrupted or item.rarity is Rarity.NORMAL or jewel_class(data, item) is not None:
        return
    if any(data.mods[entry.mod_id].domain == VEILED_DOMAIN for entry in item.mods):
        return
    yield Recombinator(item)
    other = _complement(data, item)
    if other is not None and other != item:
        yield Recombinator(other)
