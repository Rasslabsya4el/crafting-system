"""The item cards of the route view (ticket #78): a concrete item, the target, and the state after a step.

An `ItemCard` holds only what the page draws: the base name, the properties the item has, its implicits,
its enchantments, and one `Slot` per line for the full capacity of each side. Nothing is shown as absent
(no influence or corrupted line on a plain item), nothing twice, and a mod's text is the game's own text
(`Mod.text`, roll ranges as `(51-58)`, the repoe markup `[Resistances|Lightning Resistance]` read as
`Lightning Resistance`, a hybrid's line break as ` / `).

* `mod_text(mod, values)`: the text of a mod; with the rolled `values` of an item, the ranges that roll
  are filled in (a stat the text shows scaled, `(0.2-0.4)%` for 20 to 40, is scaled back).
* `card_of_item(data, item)`: a concrete item, the start item.
* `card_of_target(data, target)`: the goal. Each requirement leaf is a "wanted" slot on its mod's side,
  the rest `any mod or empty`; a k-of-n group's members carry the note `at least k of n`.
* `card_of_states(abstraction, states)`: the item after a step, the join of the compressed states the
  step leads to. What a state keeps decides what it can say (see below).
* `tracks_junk(abstraction)`: whether the abstraction keeps the mods that are not fractured.

A wanted mod drawn at random writes its ranges as `#` and says `any of N tiers`, N being the mods of the
leaf that can spawn on the base (`items.tier_table`) and pass `min_tier`; with one such mod the note is
left out and the text keeps its ranges. A fractured mod of a state is stored by a canonical id that
stands for every tier of the same contribution, so it is drawn the same way.

The slots of a state. Fractured mods and crafted slots are shown as they are. A goal leaf that a state
meets (PASSING) is a wanted slot on the leaf's side; one that it only half meets (BELOW) is the same
text with the note `tier too low`. The other slots depend on what the abstraction keeps. With junk
tracked (`tracks_junk`), a slot of no kind that gives no leaf is junk: counted per side, `any mod` for
the smallest count over the states, `any mod or empty` for the spread, `empty` for the rest of the
capacity; a slot of a family told apart is a mod of that family. Without it (rerolls only: the junk is
erased by every action), everything besides the fractured, crafted and wanted slots is `any mod or
empty`, and `empty` on a normal item. With several states, a row every state has is plain, a row only
some have carries the note `in some`, and a property that differs reads `Magic or Rare` or `(some)`.

Reaches into the abstraction beyond its public names, because it exposes no public way to ask: the
`tracked` flag of `abstraction._kinds` (in `tracks_junk`) and `abstraction._drawn_contribution(mod)` (what
a mod gives each leaf, to count the tiers a canonical fractured mod stands for).
"""

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import reduce
from operator import and_
from typing import Literal

from crafting_system.abstraction import CompressedState, Status, Wanted
from crafting_system.abstraction import Slot as StateSlot
from crafting_system.data import GameData, Mod
from crafting_system.items import Influence, Item, Rarity, Side, capacity, tier_table
from crafting_system.targets import KOfN, Target

Tone = Literal["wanted", "mod", "crafted", "any", "empty"]

SIDES = (Side.PREFIX, Side.SUFFIX)
CRAFTED_DOMAIN = "crafted"
_NUMBER = r"\d+(?:\.\d+)?"
_RANGE = re.compile(rf"\(\s*(-?{_NUMBER})\s*-\s*(-?{_NUMBER})\s*\)")
_LINK_WITH_LABEL = re.compile(r"\[[^\]|]*\|([^\]]*)\]")
_LINK = re.compile(r"\[([^\]|]*)\]")
_RARITY_ORDER = (Rarity.NORMAL, Rarity.MAGIC, Rarity.RARE)


@dataclass(frozen=True)
class Slot:
    """One line of a side: the text, how it is drawn (`tone`), its marks and a note."""

    text: str  # exact mod text, or "any mod", "any mod or empty", "empty", "any mod with tag X"
    tone: Tone
    marks: tuple[str, ...] = ()  # "fractured", "crafted", "veiled", "influence", "essence only"
    note: str = ""  # "any of 10 tiers", "tier too low", "at least 1 of 2", "in some"; "" otherwise


@dataclass(frozen=True)
class ItemCard:
    """An item as the page draws it. Each side has one slot per line, up to the capacity of a rare."""

    name: str
    properties: tuple[str, ...]  # rarity first, then "item level N", influences, "corrupted": only what is there
    implicits: tuple[str, ...]
    enchantments: tuple[str, ...]
    prefixes: tuple[Slot, ...]
    suffixes: tuple[Slot, ...]


ANY_MOD = Slot("any mod", "any")
ANY_OR_EMPTY = Slot("any mod or empty", "any")
EMPTY = Slot("empty", "empty")


# --- the text of a mod ----------------------------------------------------------------------------------


def _clean(text: str) -> str:
    text = _LINK.sub(r"\1", _LINK_WITH_LABEL.sub(r"\1", text))
    return " / ".join(line.strip() for line in text.split("\n"))


def _hashes(text: str) -> str:
    return _RANGE.sub("#", text)


def _own_text(mod: Mod) -> str:
    return _clean(mod.text) if mod.text else (mod.name or mod.id)


def _factor(text_low: float, text_high: float, stat_low: int, stat_high: int) -> float | None:
    """The k with text = k * stat at both ends of the range (k may be negative), or None."""
    for first, second in ((stat_low, stat_high), (stat_high, stat_low)):
        k = (text_high - text_low) / (second - first)
        if abs(k * first - text_low) <= 1e-9 * max(1.0, abs(text_low)):
            return k
    return None


def _shown(number: float) -> str:
    rounded = round(number, 2)
    return str(int(rounded)) if rounded == int(rounded) else str(rounded)


def mod_text(mod: Mod, values: Sequence[int] | None = None) -> str:
    """The text of `mod` as the game data has it, markup stripped, a hybrid's lines joined with ` / `.

    With `values` (one rolled integer per stat, as on an `ExplicitMod`), every range of the text that a
    stat rolls is replaced by the rolled value, scaled the way the text shows it. A range that cannot be
    matched to a stat stays as it is. Raises `ValueError` when `values` does not have one entry per stat.
    """
    text = _own_text(mod)
    if values is None:
        return text
    if len(values) != len(mod.stats):
        raise ValueError(f"the mod {mod.id} has {len(mod.stats)} stat(s) but {len(values)} values were given")
    rolling = [(stat, value) for stat, value in zip(mod.stats, values, strict=True) if stat.min != stat.max]
    ranges = list(_RANGE.finditer(text))
    if len(ranges) != len(rolling):
        return text
    pieces, end = [], 0
    for found, (stat, value) in zip(ranges, rolling, strict=True):
        low, high = sorted((float(found.group(1)), float(found.group(2))))
        k = _factor(low, high, min(stat.min, stat.max), max(stat.min, stat.max))
        pieces.append(text[end : found.start()])
        pieces.append(found.group(0) if k is None else _shown(k * value))
        end = found.end()
    pieces.append(text[end:])
    return "".join(pieces)


def _marks(mod: Mod) -> tuple[str, ...]:
    """The marks a mod carries by itself: veiled, influence (an influence tag in its spawn weights), essence only."""
    marks = []
    if mod.domain == "veiled":
        marks.append("veiled")
    influences = {influence.value for influence in Influence}
    if any(weight.weight > 0 and weight.tag.rsplit("_", 1)[-1] in influences for weight in mod.spawn_weights):
        marks.append("influence")
    if mod.is_essence_only:
        marks.append("essence only")
    return tuple(marks)


# --- properties and capacity ----------------------------------------------------------------------------


def _title(rarity: Rarity) -> str:
    return rarity.value.title()


def _properties(rarity: str, item_level: int, influences: Sequence[str], corrupted: str) -> tuple[str, ...]:
    """Rarity, item level, influences, corrupted; `corrupted` is "" for none."""
    return (rarity, f"item level {item_level}", *influences, *([corrupted] if corrupted else []))


def _capacity(data: GameData, base_id: str, side: Side) -> int:
    return capacity(data, base_id, Rarity.RARE).of(side)


def _implicits(data: GameData, base_id: str) -> tuple[str, ...]:
    return tuple(mod_text(data.mods[mod_id]) for mod_id in data.base_items[base_id].implicits)


def _note(*parts: str) -> str:
    return ", ".join(part for part in parts if part)


def _tiers_note(count: int) -> str:
    return f"any of {count} tiers" if count > 1 else ""


# --- a wanted mod drawn at random -----------------------------------------------------------------------


def _leaf_slot(data: GameData, base_id: str, tiers, mod_ids, min_tier: int | None) -> tuple[Side, str, str]:
    """The side, the text and the tier note of a requirement leaf (see the module docstring)."""
    base_domain = data.base_items[base_id].domain
    sides = {side.value for side in SIDES}
    spawning = sorted(
        (
            mod_id
            for mod_id in mod_ids
            if mod_id in tiers and data.mods[mod_id].generation_type in sides and data.mods[mod_id].domain == base_domain
        ),
        key=lambda mod_id: (tiers[mod_id], mod_id),
    )
    candidates = [mod_id for mod_id in spawning if min_tier is None or tiers[mod_id] <= min_tier]
    if not candidates:
        known = [mod_id for mod_id in mod_ids if mod_id in data.mods and data.mods[mod_id].generation_type in sides]
        if not known:
            raise ValueError(f"no mod of the requirement {sorted(mod_ids)[:3]} is a prefix or a suffix")
        known.sort(key=lambda mod_id: (data.mods[mod_id].domain not in {base_domain, CRAFTED_DOMAIN}, mod_id))
        mod = data.mods[known[0]]
        return Side(mod.generation_type), _own_text(mod), ""
    side = Side(data.mods[candidates[0]].generation_type)
    if len(candidates) == 1:
        return side, _own_text(data.mods[candidates[0]]), ""
    texts = list(dict.fromkeys(_hashes(_own_text(data.mods[mod_id])) for mod_id in candidates))
    return side, " or ".join(texts), _tiers_note(len(candidates))


# --- the card of a concrete item ------------------------------------------------------------------------


def _fill(rows: list[Slot], limit: int, filler: Slot = EMPTY) -> tuple[Slot, ...]:
    return (*rows, *(filler,) * max(0, limit - len(rows)))


def card_of_item(data: GameData, item: Item) -> ItemCard:
    """The card of a concrete item: its mods with their rolled values, the empty slots of a rare's capacity.

    Within a side the fractured mods come first, then the other mods, then the crafted ones. A magic or
    normal item shows the capacity of a rare, the slots it cannot fill as `empty`.
    """
    sides: dict[Side, tuple[Slot, ...]] = {}
    for side in SIDES:
        entries = sorted(
            item.mods_on(data, side), key=lambda entry: (not entry.fractured, entry.crafted, entry.mod_id)
        )
        rows = []
        for entry in entries:
            mod = data.mods[entry.mod_id]
            marks = (*(("fractured",) * entry.fractured), *(("crafted",) * entry.crafted), *_marks(mod))
            tone: Tone = "crafted" if entry.crafted else "mod"
            rows.append(Slot(mod_text(mod, entry.values), tone, marks))
        sides[side] = _fill(rows, _capacity(data, item.base_id, side))
    influences = tuple(influence.value.title() for influence in sorted(item.influences))
    properties = _properties(_title(item.rarity), item.item_level, influences, "corrupted" if item.corrupted else "")
    return ItemCard(
        data.base_items[item.base_id].name,
        properties,
        _implicits(data, item.base_id),
        (),
        sides[Side.PREFIX],
        sides[Side.SUFFIX],
    )


# --- the card of the target -----------------------------------------------------------------------------


def card_of_target(data: GameData, target: Target) -> ItemCard:
    """The goal as an item: a wanted slot per requirement leaf on its mod's side, the rest `any mod or empty`.

    A leaf drawn from several mods says `any of N tiers` and writes its ranges as `#`; the members of a
    k-of-n group carry `at least k of n`.
    """
    tiers = tier_table(data, target.base_id)
    wanted: dict[Side, list[Slot]] = {side: [] for side in SIDES}

    def add(nodes, group: str) -> None:
        for node in nodes:
            if isinstance(node, KOfN):
                add(node.of, f"at least {node.at_least} of {len(node.of)}")
                continue
            side, text, tier_note = _leaf_slot(data, target.base_id, tiers, node.mod_ids, node.min_tier)
            wanted[side].append(Slot(text, "wanted", (), _note(tier_note, group)))

    add(target.requirements, "")
    influences = tuple(influence.value.title() for influence in sorted(target.influences))
    properties = _properties(_title(Rarity.RARE), target.item_level, influences, "")
    prefixes, suffixes = (
        _fill(wanted[side], _capacity(data, target.base_id, side), ANY_OR_EMPTY) for side in SIDES
    )
    return ItemCard(
        data.base_items[target.base_id].name, properties, _implicits(data, target.base_id), (), prefixes, suffixes
    )


# --- the card of the state after a step -----------------------------------------------------------------


def tracks_junk(abstraction) -> bool:
    """Whether the abstraction keeps the mods that are not fractured (an enabled action reads them).

    The abstraction has no public flag for it; this reads `abstraction._kinds.tracked`.
    """
    return abstraction._kinds.tracked


@dataclass
class _Rows:
    """What one state says about each side: the rows it names, and the junk it counts (tracked only)."""

    rows: dict[Side, list[Slot]]
    junk: dict[Side, int]


class _StateReader:
    """Reads compressed states of one abstraction into rows; keeps what it looked up."""

    def __init__(self, abstraction) -> None:
        self.ab = abstraction
        self.data: GameData = abstraction.data
        self.tiers = tier_table(self.data, abstraction.base_id)
        self.tracked = tracks_junk(abstraction)
        self._leaves: dict[int, tuple[Side, str, str]] = {}
        self._fractured: dict[tuple[str, tuple[Status, ...]], tuple[Side, Slot]] = {}
        self._families: dict[tuple[Side, str], Slot] = {}

    def leaf(self, index: int) -> tuple[Side, str, str]:
        """The side, text and tier note of the goal leaf number `index`."""
        if index not in self._leaves:
            leaf: Wanted = self.ab.goal.leaves[index]
            self._leaves[index] = _leaf_slot(self.data, self.ab.base_id, self.tiers, leaf.mod_ids, leaf.min_tier)
        return self._leaves[index]

    def wanted(self, indexes: Sequence[int], status: Status) -> Slot:
        """The row of a mod that gives the leaves `indexes` this `status` (PASSING or BELOW)."""
        texts, notes = [], []
        for index in indexes:
            _, text, tier_note = self.leaf(index)
            texts.append(text if status is Status.PASSING else _hashes(text))
            notes.append(tier_note if status is Status.PASSING else "tier too low")
        return Slot(" / ".join(dict.fromkeys(texts)), "wanted", (), _note(*dict.fromkeys(notes)))

    def fractured(self, mod_id: str, contribution: tuple[Status, ...]) -> tuple[Side, Slot]:
        """A fractured mod stands for every tier of its families, side and domain that gives the same contribution."""
        key = (mod_id, contribution)
        if key not in self._fractured:
            self._fractured[key] = self._fractured_row(mod_id, contribution)
        return self._fractured[key]

    def _fractured_row(self, mod_id: str, contribution: tuple[Status, ...]) -> tuple[Side, Slot]:
        mod = self.data.mods[mod_id]
        stands_for = [
            other.id
            for other in self.data.mods.values()
            if (other.families, other.generation_type, other.domain) == (mod.families, mod.generation_type, mod.domain)
            and other.id in self.tiers
            and self.ab._drawn_contribution(other) == contribution
        ]
        if len(stands_for) < 2:
            if stands_for and mod_id not in stands_for:  # the state names another mod of the class (an essence-only one, say)
                mod = self.data.mods[stands_for[0]]
            text = mod_text(mod)
        else:  # the texts of the tiers, as the target card writes a leaf drawn from several mods
            stands_for.sort(key=lambda other: (self.tiers[other], other))
            mod = self.data.mods[stands_for[0]]
            text = " or ".join(dict.fromkeys(_hashes(_own_text(self.data.mods[other])) for other in stands_for))
        tone: Tone = "wanted" if Status.PASSING in contribution else "mod"
        return Side(mod.generation_type), Slot(text, tone, ("fractured", *_marks(mod)), _tiers_note(len(stands_for)))

    def crafted(self, slot: StateSlot) -> Slot:
        mod = self.data.mods[slot.kind]
        return Slot(mod_text(mod), "crafted", ("crafted", *_marks(mod)))

    def family(self, slot: StateSlot) -> Slot:
        """A slot of a family told apart: a mod of that family on its side, with the tiers it can have."""
        key = (slot.side, slot.kind)
        if key not in self._families:
            self._families[key] = self._family_row(slot)
        return self._families[key]

    def _family_row(self, slot: StateSlot) -> Slot:
        family = [
            mod
            for mod_id, mod in self.data.mods.items()
            if mod_id in self.tiers
            and mod.generation_type == slot.side.value
            and ("|".join(mod.families) or f"#{mod_id}") == slot.kind
        ]
        if not family:
            return ANY_MOD
        ordered = sorted(family, key=lambda mod: (self.tiers[mod.id], mod.id))
        if len(ordered) == 1:
            return Slot(mod_text(ordered[0]), "mod", _marks(ordered[0]))
        text = " or ".join(dict.fromkeys(_hashes(_own_text(mod)) for mod in ordered))
        return Slot(text, "mod", _marks(ordered[0]), _tiers_note(len(ordered)))

    def read(self, state: CompressedState) -> _Rows:
        if len(state.status) != len(self.ab.goal.leaves):
            raise ValueError("the state comes from another abstraction: its goal has other leaves")
        fractured: dict[Side, list[Slot]] = {side: [] for side in SIDES}
        wanted: dict[Side, list[Slot]] = {side: [] for side in SIDES}
        others: dict[Side, list[Slot]] = {side: [] for side in SIDES}
        crafted: dict[Side, list[Slot]] = {side: [] for side in SIDES}
        junk = {side: 0 for side in SIDES}
        for entry in state.fractured:
            side, row = self.fractured(entry.mod_id, entry.contribution)
            fractured[side].append(row)
        for slot in state.slots:
            if slot.crafted:
                crafted[slot.side].append(self.crafted(slot))
                continue
            passing = [index for index, status in enumerate(slot.contribution) if status is Status.PASSING]
            below = [index for index, status in enumerate(slot.contribution) if status is Status.BELOW]
            if passing:
                wanted[slot.side].append(self.wanted(passing, Status.PASSING))
            elif below:
                wanted[slot.side].append(self.wanted(below, Status.BELOW))
            elif slot.kind:
                others[slot.side].append(self.family(slot))
            else:
                junk[slot.side] += 1
        if not self.tracked:
            for index, status in enumerate(state.status):
                explained = any(entry.contribution[index] is status for entry in state.fractured) or any(
                    slot.crafted and slot.contribution[index] is status for slot in state.slots
                )
                if status is not Status.ABSENT and not explained:
                    wanted[self.leaf(index)[0]].append(self.wanted([index], status))
        rows = {side: [*fractured[side], *wanted[side], *others[side], *crafted[side]] for side in SIDES}
        return _Rows(rows, junk)


def _some(row: Slot) -> Slot:
    return replace(row, note=_note(row.note, "in some"))


def _rank(row: Slot) -> int:
    """Fractured rows first, then wanted, other mods, crafted ones."""
    if "fractured" in row.marks:
        return 0
    return {"wanted": 1, "crafted": 3}.get(row.tone, 2)


def _join_rows(per_state: list[list[Slot]]) -> list[Slot]:
    """The rows every state has, plain; the rows only some have, with the note `in some`."""
    if len(per_state) == 1:
        return list(per_state[0])
    counts = [Counter(rows) for rows in per_state]
    shared = reduce(and_, counts)
    joined: list[Slot] = []
    for row in dict.fromkeys(row for rows in per_state for row in rows):
        extra = max(count[row] for count in counts) - shared[row]
        joined += [row] * shared[row] + [_some(row)] * extra
    return sorted(joined, key=_rank)


def _join_properties(states: Sequence[CompressedState], item_level: int) -> tuple[str, ...]:
    rarities = [rarity for rarity in _RARITY_ORDER if any(state.flags.rarity is rarity for state in states)]
    rarity = " or ".join(_title(entry) for entry in rarities)
    influences = []
    for influence in sorted(Influence):
        holding = sum(influence in state.flags.influences for state in states)
        if holding:
            influences.append(influence.value.title() + ("" if holding == len(states) else " (some)"))
    corrupted = sum(state.flags.corrupted for state in states)
    shown = "" if not corrupted else "corrupted" if corrupted == len(states) else "corrupted (some)"
    return _properties(rarity, item_level, influences, shown)


def card_of_states(abstraction, states: Sequence[CompressedState], reader: _StateReader | None = None) -> ItemCard:
    """The item after a step: the join of the compressed `states` it can be in (see the module docstring).

    `reader` is the `_StateReader` of `abstraction` when the caller draws many cards (it keeps what it looked up).
    Raises `ValueError` for no state, and for a state that belongs to another goal.
    """
    if not states:
        raise ValueError("a card needs at least one state")
    reader = reader or _StateReader(abstraction)
    data, base_id = reader.data, abstraction.base_id
    read = [reader.read(state) for state in states]
    only_normal = all(state.flags.rarity is Rarity.NORMAL for state in states)
    sides: dict[Side, tuple[Slot, ...]] = {}
    for side in SIDES:
        rows = _join_rows([entry.rows[side] for entry in read])
        limit = _capacity(data, base_id, side)
        if reader.tracked:
            counts = [entry.junk[side] for entry in read]
            rows += [ANY_MOD] * min(counts)
            spread = max(counts) - min(counts)
            rows += [ANY_OR_EMPTY] * max(0, min(spread, limit - len(rows)))
            sides[side] = _fill(rows, limit)
        else:
            sides[side] = _fill(rows, limit, EMPTY if only_normal else ANY_OR_EMPTY)
    return ItemCard(
        data.base_items[base_id].name,
        _join_properties(states, abstraction.item_level),
        _implicits(data, base_id),
        (),
        sides[Side.PREFIX],
        sides[Side.SUFFIX],
    )
