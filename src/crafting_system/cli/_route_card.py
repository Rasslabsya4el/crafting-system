"""The item cards of the route view (ticket #78): a concrete item, the target, and the state after a step.

An `ItemCard` holds only what the page draws: the base name, the properties the item has, its implicits,
its enchantments, and one `Slot` per line for the full capacity of each side. Nothing is shown as absent
(no influence or corrupted line on a plain item), nothing twice, and a mod's text is the game's own text
(`Mod.text`, roll ranges as `(51-58)`, the repoe markup `[Resistances|Lightning Resistance]` read as
`Lightning Resistance`, a hybrid's line break as ` / `).

* `mod_text(mod, values)`: the text of a mod; with the rolled `values` of an item, the ranges that roll
  are filled in (a stat the text shows scaled, `(0.2-0.4)%` for 20 to 40, is scaled back).
* `card_of_item(data, item)`: a concrete item, the start item. With `tiers` its mods carry their tier, with
  `rolled=False` they show the range of the tier, not the roll, and `filler` draws the slots it has no mod for.
* `card_of_target(data, target, start, forced)`: the goal. Each requirement leaf is a "wanted" slot on its mod's side,
  the rest `any mod or empty`; a k-of-n group is one heading `at least k of n of these:` with its members under it, each in the one mod
  format with its own tier and no note of the group (`ItemCard.groups`, OR-15). A group whose members are all on one side fills `at_least`
  slots of that side, each `one of A / B / C` (`Slot.stands_for` "group"), so the side draws as many lines as the item holds (#1533); the
  multimod is a slot of its own when the target asks more crafted mods than the item holds without it (`stands_for` "needed", #1614). Each implicit
  requirement is a wanted implicit (note `grade 3 or better, roll 30 or more`), the catalyst quality a
  property (`Prismatic catalyst quality 12% or more`).
* `card_of_states(abstraction, states)`: the item after a step, the join of the compressed states the
  step leads to. What a state keeps decides what it can say (see below).
* `tracks_junk(abstraction)`: whether the abstraction keeps the mods that are not fractured.

One format for every mod line: the game's text with its ranges, then the tier as the note, `+(100-114) to
maximum Life · T1`. The tier is the mod's place among the mods that can spawn on the base with the item's
influences (`page_tiers`, 1 is the best: a Hunter bow's Chaos Damage over Time is tier 1 of its own ladder, #980); a base with no tiers
(a base jewel) writes none (#963); a crafted mod has none and says `crafted` when a leaf can only be met by it. A mod that comes from an essence says the
essence's tier, `Shrieking essence`, `Deafening essence` (OR-47, #895), because the essence's level, not a tier of the ladder, is what the player
chooses. Where a mod comes from is a fact of the route, not of the target file: the caller passes `forced`, the mods the essences of the
route force on this item with the note of each (`essence_notes`), and a leaf that one mod meets says that note when the mod is among
them (the Shrieking Essence of Spite forces on boots the mod that is also tier 2 of Intelligence; with another route, or no route, the
line says `T2`). An essence-only mod needs no route to say it: only an essence gives it, so it says the essence of the base's class that
does (`essence_tier`), and `essence only` when none does. A leaf that several mods can
meet (the candidates are those that spawn on the base at the item level and that the leaf's tier judgement accepts, `tier_ok`) writes the texts
of all of them with `#` for the ranges, joined by ` or `, and the note `T2 or better` (`min_tier`) or
`any tier`, or the tiers the candidates have (`T1 to T3`) when the leaf asked a tier it did not write.

Fractured mods (OR-47, #895). A fracture is a fact of the start item, not a word of the target file (a requirement cannot say it), and it
never leaves the item. So a leaf of the target card that a fractured mod of the start item meets is drawn as that mod, with its tier
and the mark `fractured`, and so is that mod on every card after a step. A state stores a fractured mod by a canonical id that
stands for every tier of the same contribution: the start item's own mod of that class is the one drawn; a mod fractured on the way
(no start item mod of its class) is drawn as the tiers it stands for, the way a leaf of several mods is.

Implicits (ADR-0027) are slots of the tone `implicit` in the same format. The implicits the base has and the
item does not store are drawn as their ranges; a stored one always carries its rolled values (the implicit is
item state, not a tier of a bought mod). An Eldritch implicit has the note `grade 3 (Grand)` and the mark of its side (`searing
exarch`, `eater of worlds`); a stored base implicit has neither. The catalyst quality is a property pill, a
veiled placeholder reads `veiled prefix` or `veiled suffix` (its data has no text), and the offer of its
unveiling is one slot per offered mod, with the tier it has on the base.

The slots of a state. Fractured mods and crafted slots are shown as they are. A goal leaf that a state
meets (PASSING) is a wanted slot on the leaf's side; one that it only half meets (BELOW) is the same
text with the note `tier too low`. The other slots depend on what the abstraction keeps. With junk
tracked (`tracks_junk`), a slot of no kind that gives no leaf is junk: counted per side, `any mod` for
the smallest count over the states, `any mod or empty` for the spread, `empty` for the rest of the
capacity; a slot of a family told apart is a mod of that family. Without it (rerolls only: the junk is
erased by every action), everything besides the fractured, crafted and wanted slots is `any mod or
empty`, and `empty` on a normal item. With several states, a row every state has is plain; a row only some have is no line of
the item (a card is an item a player can hold, never a blend of outcomes: six prefixes on a Rare, #889), its slot is `any mod` or `any mod
or empty` and the row is listed once under the heading `VARIES` with its side; a property that differs reads `Magic or Rare` or `(some)`.

Reaches into the abstraction beyond its public names, because it exposes no public way to ask: the
`tracked` flag of `abstraction._kinds` (in `tracks_junk`) and `abstraction._drawn_contribution(mod)` (what
a mod gives each leaf, to count the tiers a canonical fractured mod stands for).
"""

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import reduce
from operator import and_
from typing import Literal

from crafting_system.abstraction import CompressedState, Status, Wanted, status_of
from crafting_system.abstraction import Slot as StateSlot
from crafting_system.actions import OutOfScopeError, crafted_limit_of, forced_mod_id, tiers_of
from crafting_system.data import GameData, Mod
from crafting_system.items import (
    EldritchSide,
    ExplicitMod,
    ImplicitMod,
    Influence,
    Item,
    Metamod,
    Rarity,
    Side,
    capacity,
    eldritch_side,
    memory_strands_line,
    natural_tiers,
    tier_table,
)
from crafting_system.items.model import EXPLICIT_EXTRA_DOMAINS, MAX_ITEM_LEVEL, UNVEILED_DOMAIN
from crafting_system.items.words import mod_text as mod_text_of
from crafting_system.targets import ImplicitRequirement, KOfN, Target

Tone = Literal["wanted", "mod", "crafted", "any", "empty", "implicit"]

SIDES = (Side.PREFIX, Side.SUFFIX)
FAMILY_TYPE_TEXT = "an unwanted mod"  # a player's words (#1442; the page says "unwanted" of every mod the target does not need); a fractured mod the state holds as its family type ("~n"), not as a mod (ticket #70)
CRAFTED_DOMAIN = "crafted"
VEILED_DOMAIN = "veiled"
GRADE_NAMES = {1: "Lesser", 2: "Greater", 3: "Grand", 4: "Exceptional", 5: "Exquisite", 6: "Perfect"}
SIDE_NAMES = {EldritchSide.EXARCH: "searing exarch", EldritchSide.EATER: "eater of worlds"}
_NUMBER = r"\d+(?:\.\d+)?"
_RANGE = re.compile(rf"\(\s*(-?{_NUMBER})\s*-\s*(-?{_NUMBER})\s*\)")
_RARITY_ORDER = (Rarity.NORMAL, Rarity.MAGIC, Rarity.RARE)


@dataclass(frozen=True)
class Slot:
    """One line of a side: the text, how it is drawn (`tone`), its marks and a note."""

    text: str  # exact mod text, or "any mod", "any mod or empty", "empty", "any mod with tag X"
    tone: Tone
    marks: tuple[str, ...] = ()  # "fractured", "crafted", "veiled", "influence", "essence only", "searing exarch", "eater of worlds", and for a member of a group "prefix" or "suffix"
    note: str = ""  # "any of 10 tiers", "tier too low", "at least 1 of 2", "in some"; "" otherwise
    stands_for: str = ""  # on a target card, a slot that is no mod the target names by itself: "group" (a slot of a k-of-n group, #1533), "needed" (the multimod two crafted mods need, #1614)


NESTED_GROUP = (
    "a k-of-n group inside another k-of-n group is not drawn on the target card yet: the card says each group once under its own heading, "
    "and two nested headings could not be told apart from a group said twice (OR-15)"
)


@dataclass(frozen=True)
class Group:
    """A k-of-n group of the target, said once: the `heading` ("at least 1 of 4 of these:") and its members, each a line in the one mod format
    with its own tier and no note of the group (OR-15). The members are not slots of a side: each says its side in words (the mark `prefix` or
    `suffix`), so the card still shows which open slot a member would take. A group holds leaves only (`NESTED_GROUP`)."""

    heading: str
    members: tuple[Slot, ...]


@dataclass(frozen=True)
class ItemCard:
    """An item as the page draws it. Each side has one slot per line, up to the capacity of a rare."""

    name: str
    properties: tuple[str, ...]  # rarity first, then "item level N", influences, quality, "corrupted": only what is there
    implicits: tuple[Slot, ...]
    enchantments: tuple[str, ...]
    prefixes: tuple[Slot, ...]
    suffixes: tuple[Slot, ...]
    offer: tuple[Slot, ...] = ()  # what a veiled placeholder offers when unveiled; drawn only when there is some
    groups: tuple[Group, ...] = ()  # the k-of-n groups of a target card, each once with its members under it (OR-15); empty on every other card


ANY_MOD = Slot("any mod", "any")
ANY_OR_EMPTY = Slot("any mod or empty", "any")
EMPTY = Slot("empty", "empty")


# --- the text of a mod ----------------------------------------------------------------------------------


def _hashes(text: str) -> str:
    return _RANGE.sub("#", text)


_LEAD = re.compile(r"^\+?(?:#|\([\d.]+-[\d.]+\)|[\d.]+)%?\s+(?:(?:to|increased|chance to)\s+)?")  # "reduced" and a minus sign stay: they turn the mod


def short_mod(text: str) -> str:
    """A wanted mod as a title names it: its first line without the figures in front ("+(13-14)% chance to Suppress Spell Damage" is
    "Suppress Spell Damage", "+# to maximum Life" is "maximum Life"); a text with no figure in front stays as it is."""
    first = text.split(" / ")[0]
    return _LEAD.sub("", first, count=1) or first


_FIGURE = re.compile(rf"(?<![\w.]){_NUMBER}(?![\w.])")


def _tiers_joined(texts: Iterable[str], every: bool = False) -> str:
    """The texts of the tiers of one line (ranges already `#`) joined by ` or `, a fixed tier beside the ranged ones of its text said once (#1442).

    The lowest tier of a ladder often rolls no range ("Adds 1 to 2 Physical Damage to Attacks" beside "Adds # to # Physical Damage to
    Attacks"): to a player that is one mod, so a group of texts that are the same with every figure as `#`, one of them written with `#`
    already, is written that way. Tiers that are all fixed values keep them ("35% increased Speed or 30% increased Speed"): there the
    figures are what tells the tiers apart, unless the line stands for `every` tier ("any tier"), where no figure tells anything the line
    asks ("#% increased Movement Speed · any tier", R24).

    A line of mods of two or more stat lines each (a hybrid, its lines joined by " / ") would read as one list of " / " and " or " (OR-15,
    R24's "+# to maximum Energy Shield / +# to maximum Life or +# to maximum Energy Shield / +# to maximum Mana"): it is written
    "one of: A / B; C / D", each mod whole between the semicolons."""
    groups: dict[str, list[str]] = {}
    for text in dict.fromkeys(texts):
        groups.setdefault(_FIGURE.sub("#", text), []).append(text)
    parts: list[str] = []
    for key, members in groups.items():
        if len(members) > 1 and (every or any("#" in member for member in members)):
            parts.append(key)
        else:
            parts.extend(members)
    if len(parts) > 1 and any(" / " in part for part in parts):
        return "one of: " + "; ".join(parts)
    return " or ".join(parts)


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
    text = mod_text_of(mod)
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


def _properties(
    rarity: str, item_level: int, influences: Sequence[str], corrupted: str, quality: str = "", strands: str = ""
) -> tuple[str, ...]:
    """Rarity, item level, influences, quality, Memory Strands, corrupted; `quality`, `strands` and `corrupted` are "" for none."""
    shown = [*([quality] if quality else []), *([strands] if strands else []), *([corrupted] if corrupted else [])]
    return (rarity, f"item level {item_level}", *influences, *shown)


def _quality(kind: str | None, percent: int, suffix: str = "") -> str:
    if kind is None:  # the plain quality of a weapon or armour (ADR-0049)
        return f"Quality {percent}%{suffix}"
    return f"{kind.title()} catalyst quality {percent}%{suffix}"


def _kind(quality) -> str | None:  # noqa: ANN001
    """The catalyst type name of a quality or of a quality requirement, or None for the plain quality of a weapon or armour."""
    return None if quality.type is None else quality.type.value


def _capacity(data: GameData, base_id: str, side: Side, rarity: Rarity = Rarity.RARE) -> int:
    """The slots a card draws on `side`: those of a Magic item for a Magic one (one prefix, one suffix, #962), else those of a rare.

    A Normal item holds no mod, and its card draws the slots of a rare as `empty` (what crafting can fill), never a Magic item's.
    """
    return capacity(data, base_id, Rarity.MAGIC if rarity is Rarity.MAGIC else Rarity.RARE).of(side)


def _implicits(data: GameData, base_id: str) -> tuple[Slot, ...]:
    """The implicits the base has, as ranges."""
    return tuple(Slot(mod_text(data.mods[mod_id]), "implicit") for mod_id in data.base_items[base_id].implicits)


def _stored_implicit(data: GameData, entry: ImplicitMod) -> Slot:
    """A stored implicit: its rolled values, also on a card that is not `rolled`; an Eldritch one has its grade and side."""
    mod = data.mods[entry.mod_id]
    side = eldritch_side(mod)
    note = f"grade {entry.grade} ({GRADE_NAMES[entry.grade]})" if side is not None else ""
    marks = (SIDE_NAMES[side],) if side is not None else ()
    return Slot(mod_text(mod, entry.values), "implicit", marks, note)


def _note(*parts: str) -> str:
    return ", ".join(part for part in parts if part)


def essence_note(name: str) -> str:
    """The note of a mod an essence gives, from the essence's name: its tier, the first word ("Shrieking Essence of Spite" is `Shrieking essence`);
    an essence with no such word (the corruption-only ones, "Essence of Horror") is said by its name."""
    word, sep, _ = name.partition(" Essence of ")
    return f"{word} essence" if sep else name


def essence_tier(data: GameData, base_id: str, mod_id: str) -> str:
    """The note of the essence that forces `mod_id` on the base's item class: `Shrieking essence`; "" when no essence does.

    Essences of different tiers that force one mod are joined by " or ", the lowest first.
    """
    found = sorted((essence.level, essence_note(essence.name)) for essence in data.essences.values() if forced_mod_id(data, essence, base_id) == mod_id)
    return " or ".join(dict.fromkeys(name for _, name in found))


def essence_notes(data: GameData, base_id: str, names: Iterable[str]) -> dict[str, str]:
    """The mods the essences `names` (as the game data names them) force on the base, each with the note of its essence.

    These are the essences a route uses: a mod line of that route's page that stands for one of these mods says where it comes from
    (`_leaf_slot`). The mod is the one the action itself forces (`crafting_system.actions.forced_mod_id`). An essence that forces nothing on
    the base, and a name that is no essence, give nothing.
    """
    by_name = {essence.name: essence for essence in data.essences.values()}
    found: dict[str, str] = {}
    for name in dict.fromkeys(names):
        essence = by_name.get(name)
        mod_id = None if essence is None else forced_mod_id(data, essence, base_id)
        if mod_id is not None:
            found[mod_id] = essence_note(name) if mod_id not in found else f"{found[mod_id]} or {essence_note(name)}"
    return found


def fractured_meeting(leaf, held: Sequence[ExplicitMod]) -> ExplicitMod | None:
    """The fractured mod among `held` (the start item's) that meets the requirement leaf, by the one judgement (`status_of`); None when none does."""
    for entry in held:
        if status_of(leaf, entry.mod_id, entry.values, entry.crafted) is Status.PASSING:
            return entry
    return None


class TierTable(dict):
    """The tier of every mod that can spawn on an item of one base, level and set of influences, by mod id (1 is the best), as the page reads it.

    `tierless` says the base has no tiers at all: every mod it can roll by nature is alone on its ladder (a base jewel, "(5-7)% increased
    maximum Life"), so the page writes no tier for any of its mods and no tier ladder (#963). A base with ladders keeps `T1` on a mod that
    is alone on its own (`+1 to Level of Socketed Gems · T1`, and its tier chance `T1 ≈0.85% · none ≈99%`), as the game's advanced
    description does: the mod line and the tier line of one mod say the same tier (OR-15, OR-31).
    """

    def __init__(self, table: Mapping[str, int] = (), tierless: bool = False) -> None:
        super().__init__(table)
        self.tierless = tierless


_PAGE_TIERS: dict[tuple[int, str, frozenset[Influence]], tuple[GameData, TierTable]] = {}
_PAGE_TIERS_LIMIT = 32


def page_tiers(data: GameData, base_id: str, influences: Iterable[Influence] = ()) -> TierTable:
    """The tiers of the mods that can spawn on the base with `influences`, as the planner judges a target's tier (#980).

    An influence adds its own mods and their ladders (the Hunter's "(90-94)% increased Chaos Damage over Time" is tier 1 of four on a Hunter
    bow): the table is `actions.tiers_of` of a rare of the base with those influences, the one `targets` reads a target's tiers from, and
    `items.tier_table` with no influence. Cached per game data, base and influences.
    """
    held = frozenset(influences)
    key = (id(data), base_id, held)
    hit = _PAGE_TIERS.get(key)
    if hit is not None and hit[0] is data:
        return hit[1]
    table: Mapping[str, int] = tier_table(data, base_id)
    if held:
        probe = Item.build(data, base_id=base_id, item_level=MAX_ITEM_LEVEL, rarity=Rarity.RARE, influences=held)
        try:
            table = tiers_of(data, probe)
        except OutOfScopeError:  # an item class with no influence pool: its tiers are the base's (as `targets` reads them)
            pass
    natural = natural_tiers(data, base_id, table)
    found = TierTable(table, tierless=bool(natural) and max(natural.values()) == 1)
    if key not in _PAGE_TIERS and len(_PAGE_TIERS) >= _PAGE_TIERS_LIMIT:
        del _PAGE_TIERS[next(iter(_PAGE_TIERS))]
    _PAGE_TIERS[key] = (data, found)
    return found


def _tier_note(tiers, mod_ids, min_tier: int | None = None, asked: bool = False) -> str:
    """The tier note of a line that stands for `mod_ids`: `T2`, `T2 or better`, `any tier`; "" for a mod with no tier.

    A mod of a base with no tiers (`TierTable.tierless`, a base jewel) has no tier either (#963). `asked` says the leaf's tier limit
    (`tier_ok`) left a spawning mod out without a written `min_tier` (OR-1, the top tier): the note then names the tiers its candidates have,
    `T1 to T3`. A leaf that leaves none out (`min_tier: any`, or no tier asked) is `any tier`.
    """
    ids = list(mod_ids)
    if getattr(tiers, "tierless", False) or not ids:
        return ""
    if len(ids) == 1:
        return f"T{tiers[ids[0]]}" if ids[0] in tiers else ""
    if min_tier is not None:
        return f"T{min_tier} or better"
    found = sorted({tiers[mod_id] for mod_id in ids if mod_id in tiers})
    if asked and found:
        return f"T{found[0]}" if len(found) == 1 else f"T{found[0]} to T{found[-1]}"
    return "any tier"


# --- a wanted mod drawn at random -----------------------------------------------------------------------


def _leaf_slot(
    data: GameData,
    base_id: str,
    tiers,
    mod_ids,
    min_tier: int | None,
    item_level: int | None = None,
    tier_ok: frozenset[str] | None = None,
    forced: Mapping[str, str] | None = None,
) -> tuple[Side, str, str]:
    """The side, the text and the tier note of a requirement leaf (see the module docstring).

    `forced` are the mods the route's essences force on this item, each with its essence's note (`essence_notes`); None for no route.
    """
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
    candidates = [mod_id for mod_id in spawning if tier_ok is None or mod_id in tier_ok]  # the leaf's own tier judgement (#457)
    at_level = [mod_id for mod_id in candidates if item_level is None or data.mods[mod_id].required_level <= item_level]
    candidates = at_level or candidates
    if not candidates:
        known = [mod_id for mod_id in mod_ids if mod_id in data.mods and data.mods[mod_id].generation_type in sides]
        if not known:
            raise ValueError(f"no mod of the requirement {sorted(mod_ids)[:3]} is a prefix or a suffix")
        # the mods the leaf's tier judgement accepts first: a leaf is never drawn as another mod of its family (OR-15, #980)
        known.sort(key=lambda mod_id: (tier_ok is not None and mod_id not in tier_ok, data.mods[mod_id].domain not in {base_domain, CRAFTED_DOMAIN}, mod_id))
        mod = data.mods[known[0]]
        if mod.domain == CRAFTED_DOMAIN:
            note = "crafted"
        elif mod.is_essence_only:
            note = essence_tier(data, base_id, mod.id) or "essence only"
        else:
            note = _tier_note(tiers, [known[0]])
        return Side(mod.generation_type), mod_text_of(mod), note
    side = Side(data.mods[candidates[0]].generation_type)
    if len(candidates) == 1:
        return side, mod_text_of(data.mods[candidates[0]]), (forced or {}).get(candidates[0]) or _tier_note(tiers, candidates)
    limited = tier_ok is not None and any(mod_id not in tier_ok for mod_id in spawning)  # the leaf's tier limit left some spawning mod out
    if getattr(tiers, "tierless", False):  # no tiers: each mod with its ranges (#963)
        return side, " or ".join(dict.fromkeys(mod_text_of(data.mods[mod_id]) for mod_id in candidates)), _tier_note(tiers, candidates, min_tier, limited)
    note = _tier_note(tiers, candidates, min_tier, limited)
    return side, _tiers_joined((_hashes(mod_text_of(data.mods[mod_id])) for mod_id in candidates), every=note == "any tier"), note


# --- the card of a concrete item ------------------------------------------------------------------------


def _fill(rows: list[Slot], limit: int, filler: Slot = EMPTY) -> tuple[Slot, ...]:
    return (*rows, *(filler,) * max(0, limit - len(rows)))


def card_of_item(
    data: GameData, item: Item, *, tiers: bool = False, rolled: bool = True, filler: Slot = EMPTY
) -> ItemCard:
    """The card of a concrete item: its mods with their rolled values, the empty slots of a rare's capacity.

    Within a side the fractured mods come first, then the other mods, then the crafted ones. A Magic item shows
    one prefix and one suffix slot (#962), a normal or rare one the capacity of a rare, the slots it cannot fill as `filler`. With `tiers` a mod carries
    its tier as the note; with `rolled` False it shows the range of its tier, not the roll.
    """
    table = page_tiers(data, item.base_id, item.influences) if tiers else TierTable()
    base_implicits = data.base_items[item.base_id].implicits
    shown_implicits = tuple(  # the base's implicit first, then the Eldritch ones by grade
        # an item carries every implicit of its base (#484), at a roll the state does not hold: without `rolled` the base's own shows its range
        Slot(mod_text(data.mods[entry.mod_id]), "implicit")
        if not rolled and entry.mod_id in base_implicits
        else _stored_implicit(data, entry)
        for entry in sorted(item.implicits, key=lambda entry: (entry.grade, entry.mod_id))
    )
    offer = tuple(
        Slot(mod_text(mod), "mod", _marks(mod), _tier_note(table, [mod.id]))
        for mod in (data.mods[mod_id] for mod_id in item.veil_offer)
    )
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
            rows.append(Slot(mod_text(mod, entry.values if rolled else None), tone, marks, _tier_note(table, [mod.id])))
        sides[side] = _fill(rows, _capacity(data, item.base_id, side, item.rarity), filler)
    influences = tuple(influence.value.title() for influence in sorted(item.influences))
    quality = _quality(_kind(item.quality), item.quality.percent) if item.quality is not None else ""
    properties = _properties(
        _title(item.rarity), item.item_level, influences, "corrupted" if item.corrupted else "", quality,
        memory_strands_line(item.memory_strands) or "",
    )  # fmt: skip
    return ItemCard(
        data.base_items[item.base_id].name,
        properties,
        shown_implicits,
        (),
        sides[Side.PREFIX],
        sides[Side.SUFFIX],
        offer,
    )


# --- the card of the target -----------------------------------------------------------------------------


def card_of_target(data: GameData, target: Target, start: Item | None = None, forced: Mapping[str, str] | None = None) -> ItemCard:
    """The goal as an item: a wanted slot per requirement leaf on its mod's side, the rest `any mod or empty`.

    A leaf drawn from several mods says `any of N tiers` and writes its ranges as `#`. A k-of-n group is
    said once, in `groups`: its heading and its members, which are not slots of a side (OR-15). An implicit
    requirement is a wanted implicit, the quality requirement a property pill. A leaf that a fractured mod of
    `start` meets (the item the route starts from; the target's own start item when None) is that mod with its
    tier, marked `fractured`: the finished item holds it, since a fracture never leaves the item (#895). `forced`
    are the mods the route's essences force (`essence_notes`): a leaf one of them meets says the essence's tier.
    """
    begin = target.start_item if start is None else start
    tiers = page_tiers(data, target.base_id, target.influences | begin.influences)
    wanted: dict[Side, list[Slot]] = {side: [] for side in SIDES}
    groups: list[Group] = []
    held = begin.fractured_mods

    def leaf(node, member: bool = False) -> tuple[Side, Slot]:
        """The slot of a leaf; a `member` of a group says its side in words (which of the open slots it would take)."""
        entry = fractured_meeting(node, held)
        if entry is not None:
            mod = data.mods[entry.mod_id]
            side, text, marks = Side(mod.generation_type), mod_text_of(mod), ("fractured",)
            tier_note = _tier_note(tiers, [mod.id]) or essence_tier(data, target.base_id, mod.id)  # an essence-only mod has no tier of the ladder
        else:
            side, text, tier_note = _leaf_slot(data, target.base_id, tiers, node.mod_ids, node.min_tier, target.item_level, node.tier_ok, forced)
            marks = ()
        tier_note = _note(tier_note, roll_note(node.min_roll))
        return side, Slot(text, "wanted", (*((side.value,) if member else ()), *marks), tier_note)

    reserved: list[tuple[Side, int, Slot]] = []  # the slots a group fills on its one side (#1533)

    def add(nodes) -> None:
        for node in nodes:
            if isinstance(node, KOfN):
                if any(isinstance(member, KOfN) for member in node.of):
                    raise ValueError(NESTED_GROUP)
                drawn = [leaf(member, member=True) for member in node.of]
                members = tuple(slot for _, slot in drawn)
                groups.append(Group(f"at least {node.at_least} of {len(node.of)} of these:", members))
                sides = {side for side, _ in drawn}
                if len(sides) == 1:  # every member on one side: the group fills `at_least` of its slots, each one of the members
                    names = list(dict.fromkeys(short_mod(slot.text) for slot in members))
                    text = f"one of {' / '.join(names)}" if len(names) > 1 else (names[0] if len(members) == 1 else f"{names[0]}, one of the {len(members)} below")
                    reserved.append((sides.pop(), node.at_least, Slot(text, "wanted", stands_for="group")))
                continue
            side, slot = leaf(node)
            wanted[side].append(slot)

    add(target.requirements)
    needed = _needed_multimod(data, target, begin)
    if needed is not None and len(wanted[needed[0]]) < _capacity(data, target.base_id, needed[0]):  # never a line past the side's slots (#1533)
        wanted[needed[0]].append(needed[1])
    for side, count_, slot in reserved:  # after the mods named alone: a group's slot is any of its members, the slots left over are open
        room = _capacity(data, target.base_id, side) - len(wanted[side])
        wanted[side] += [slot] * max(0, min(count_, room))
    influences = tuple(influence.value.title() for influence in sorted(target.influences))
    need = target.quality
    quality = _quality(_kind(need), need.min_percent, " or more") if need is not None else ""
    properties = _properties(_title(Rarity.RARE), target.item_level, influences, "", quality)
    prefixes, suffixes = (
        _fill(wanted[side], _capacity(data, target.base_id, side), ANY_OR_EMPTY) for side in SIDES
    )
    # a wished implicit is drawn once, with the roll asked, in the place of the base's range of it (#1234, crafter on R06)
    wished = {_hashes(mod_text_of(data.mods[mod_id])) for wish in target.implicits for mod_id in wish.mod_ids}
    held = tuple(slot for slot in _implicits(data, target.base_id) if _hashes(slot.text) not in wished)
    implicits = (*held, *(_wanted_implicit(data, wish) for wish in target.implicits))
    return ItemCard(data.base_items[target.base_id].name, properties, implicits, (), prefixes, suffixes, groups=tuple(groups))


def _needed_multimod(data: GameData, target: Target, start: Item) -> tuple[Side, Slot] | None:
    """The multimod ("Can have up to 3 Crafted Modifiers") as a slot of the target card when the target asks more crafted mods than the item
    holds without it (one, two with the enchantment of the extra crafted slot), and does not ask the multimod itself: the finished item
    cannot be without it, so its slot is never "any mod or empty" (#1614, R14's +2 Support Gems and Chaos Damage over Time Multiplier).
    A leaf counts when a crafted mod alone meets it; a k-of-n group by the members it must take among those (its `at_least` past the others).
    None otherwise."""
    multimods = [mod for mod in data.mods.values() if mod.domain == CRAFTED_DOMAIN and Metamod.MULTIPLE_CRAFTED_MODS.value in mod.families]
    if not multimods:
        return None
    ids = {mod.id for mod in multimods}

    def only_crafted(node) -> bool:
        known = [mod_id for mod_id in node.mod_ids if mod_id in data.mods]
        return bool(known) and all(data.mods[mod_id].domain == CRAFTED_DOMAIN for mod_id in known)

    crafted = 0
    for node in target.requirements:
        members = node.of if isinstance(node, KOfN) else (node,)
        if any(not isinstance(member, KOfN) and member.mod_ids & ids for member in members):
            return None  # the target asks the multimod: its own line draws it
        if isinstance(node, KOfN):
            others = sum(1 for member in node.of if isinstance(member, KOfN) or not only_crafted(member))
            crafted += max(0, node.at_least - others)
        elif only_crafted(node):
            crafted += 1
    if crafted <= crafted_limit_of(data, multimod=False, enchantment=start.enchantment):
        return None
    mod = min(multimods, key=lambda mod: mod.id)
    return Side(mod.generation_type), Slot(mod_text_of(mod), "wanted", (), "crafted, to hold the other crafted mods", stands_for="needed")


def with_quality(card: ItemCard, need) -> ItemCard:
    """`card` once a finish step gave it the quality `need` asks (#1234): the quality's pill beside the rarity and item level, as a target's."""
    shown = _quality(_kind(need), need.min_percent, " or more")
    properties = [entry for entry in card.properties if "quality" not in entry.lower()]
    at = next((index for index, entry in enumerate(properties) if entry in ("corrupted",) or entry.startswith("Memory Strands")), len(properties))
    return replace(card, properties=(*properties[:at], shown, *properties[at:]))


def with_implicits(card: ItemCard, data: GameData, wishes: Iterable[ImplicitRequirement]) -> ItemCard:
    """`card` once a finish step rolled its implicit as `wishes` ask (#1234): each wished implicit's line with the roll asked, in the place
    of the implicit's range."""
    wishes = tuple(wishes)
    texts = {_hashes(mod_text_of(data.mods[mod_id])) for wish in wishes for mod_id in wish.mod_ids}
    kept = tuple(slot for slot in card.implicits if _hashes(slot.text) not in texts)
    return replace(card, implicits=(*kept, *(_wanted_implicit(data, wish) for wish in wishes)))


def roll_note(min_roll) -> str:
    """The rolls a requirement asks of its mod, one per limited stat ("roll 12 or more"); "" for none. An explicit mod says it on the target
    card and wherever a line names it, as an implicit does: the plan re-rolls until it is reached (#1433, R06's Attributes at 12)."""
    rolls = [str(roll) for roll in min_roll or () if roll is not None]
    if not rolls:
        return ""
    return f"roll {rolls[0]} or more" if len(rolls) == 1 else f"rolls {' and '.join(rolls)} or more"


def below_note(asks_tier: bool, min_roll) -> str:
    """Why a mod of a wanted family does not meet its leaf: its tier, or its roll under the one asked ("below roll 12"); `asks_tier` when
    the leaf judges a tier too."""
    rolls = [roll for roll in min_roll or () if roll is not None]
    if not rolls:
        return "tier too low"
    below = "below roll " + " / ".join(map(str, rolls))
    return below if not asks_tier else f"tier too low or {below}"


def _wanted_implicit(data: GameData, wish: ImplicitRequirement) -> Slot:
    """An implicit requirement: the texts of its mods with `#` for the ranges, then the grade and rolls asked for."""
    texts = dict.fromkeys(_hashes(mod_text_of(data.mods[mod_id])) for mod_id in sorted(wish.mod_ids))
    grade = f"grade {wish.min_grade} or better" if wish.min_grade is not None else ""
    rolls = [f"roll {roll} or more" for roll in wish.min_roll or () if roll is not None]
    return Slot(" or ".join(texts), "wanted", (), _note(grade, *rolls))


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

    def __init__(
        self, abstraction, start: Item | None = None, forced: Mapping[str, str] | None = None, influences: Iterable[Influence] = ()
    ) -> None:
        """`start` is the item the route starts from: its fractured mods are the ones a state's fractured entries of their class are (#895).
        `forced` are the mods the route's essences force, each with its essence's note (`essence_notes`): a leaf line says it. The tiers
        are those of the item with `influences` and the start item's (`page_tiers`): the target's, so a leaf reads as on the target card."""
        self.ab = abstraction
        self.data: GameData = abstraction.data
        self.tiers = page_tiers(self.data, abstraction.base_id, {*influences, *(start.influences if start is not None else ())})
        self.tracked = tracks_junk(abstraction)
        self._held = tuple(self.data.mods[entry.mod_id] for entry in start.fractured_mods) if start is not None else ()
        self._forced = dict(forced or {})
        self._leaves: dict[int, tuple[Side, str, str]] = {}
        self._fractured: dict[tuple[str, tuple[Status, ...]], tuple[Side, Slot]] = {}
        self._families: dict[tuple[Side, str], Slot] = {}

    def leaf(self, index: int) -> tuple[Side, str, str]:
        """The side, text and tier note of the goal leaf number `index`."""
        if index not in self._leaves:
            leaf: Wanted = self.ab.goal.leaves[index]
            side, text, note = _leaf_slot(
                self.data, self.ab.base_id, self.tiers, leaf.mod_ids, leaf.min_tier, self.ab.item_level, leaf.tier_ok, self._forced
            )
            self._leaves[index] = (side, text, _note(note, roll_note(leaf.min_roll)))
        return self._leaves[index]

    def wanted(self, indexes: Sequence[int], status: Status) -> Slot:
        """The row of a mod that gives the leaves `indexes` this `status` (PASSING or BELOW)."""
        texts, notes = [], []
        for index in indexes:
            _, text, tier_note = self.leaf(index)
            texts.append(text if status is Status.PASSING else _hashes(text))
            leaf = self.ab.goal.leaves[index]
            notes.append(tier_note if status is Status.PASSING else below_note(leaf.tier_ok is not None, leaf.min_roll))
        return Slot(" / ".join(dict.fromkeys(texts)), "wanted", (), _note(*dict.fromkeys(notes)))

    def fractured(self, mod_id: str, contribution: tuple[Status, ...]) -> tuple[Side, Slot]:
        """A fractured mod stands for every tier of its families, side and domain that gives the same contribution."""
        key = (mod_id, contribution)
        if key not in self._fractured:
            self._fractured[key] = self._fractured_row(mod_id, contribution)
        return self._fractured[key]

    def _fractured_row(self, mod_id: str, contribution: tuple[Status, ...]) -> tuple[Side, Slot]:
        if mod_id not in self.data.mods:  # held as its family type: the state knows its side and what it gives the goal, not which mod it is
            side = self.ab._kinds.side_of(mod_id)
            best = max(contribution, default=Status.ABSENT)
            if best is Status.ABSENT:
                return side, Slot(FAMILY_TYPE_TEXT, "mod", ("fractured",))
            wanted = self.wanted([i for i, status in enumerate(contribution) if status is best], best)  # a wanted mod fractured: named (#1442)
            return side, replace(wanted, tone="wanted" if best is Status.PASSING else "mod", marks=("fractured", *wanted.marks))
        mod = self.data.mods[mod_id]
        kind = (mod.families, mod.generation_type, mod.domain)
        own = [held for held in self._held if (held.families, held.generation_type, held.domain) == kind and self.ab._drawn_contribution(held) == contribution]
        stands_for = [
            other.id
            for other in self.data.mods.values()
            if (other.families, other.generation_type, other.domain) == kind
            and other.id in self.tiers
            and self.ab._drawn_contribution(other) == contribution
        ]
        if own:  # the start item's own fractured mod: the item holds exactly this one (a fracture never leaves it)
            mod = own[0]
            text = mod_text(mod)
            note = _tier_note(self.tiers, [mod.id])
        elif len(stands_for) < 2:
            if stands_for and mod_id not in stands_for:  # the state names another mod of the class (an essence-only one, say)
                mod = self.data.mods[stands_for[0]]
            text = mod_text(mod)
            note = _tier_note(self.tiers, [mod.id])
        else:  # the texts of the tiers, as the target card writes a leaf drawn from several mods
            stands_for.sort(key=lambda other: (self.tiers[other], other))
            mod = self.data.mods[stands_for[0]]
            note = _tier_note(self.tiers, stands_for)
            text = _tiers_joined((_hashes(mod_text_of(self.data.mods[other])) for other in stands_for), every=note == "any tier")
        tone: Tone = "wanted" if Status.PASSING in contribution else "mod"
        return Side(mod.generation_type), Slot(text, tone, ("fractured", *_marks(mod)), note)

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
        """The mods of the slot's family a slot of that kind can hold, as the abstraction finds them (`_kinds._find_mod`): the base's domain and the
        extra explicit ones, never a crafted mod nor a mod unveiled from the pool, which has a kind of its own (#1442: a Jun mod read as a ring's
        Mana prefix). The mods that spawn on the base come first; a family none of whose mods does is one only an essence gives (Avoid being
        Frozen on boots), said by the mods an essence forces on this base, each with its essence; none forced here leaves "any mod"."""
        domains = ({self.data.base_items[self.ab.base_id].domain} | EXPLICIT_EXTRA_DOMAINS) - {CRAFTED_DOMAIN, UNVEILED_DOMAIN}
        held = [
            mod
            for mod_id, mod in self.data.mods.items()
            if mod.generation_type == slot.side.value and mod.domain in domains and ("|".join(mod.families) or f"#{mod_id}") == slot.kind
        ]
        family = [mod for mod in held if mod.id in self.tiers]
        if not family:  # a family only an essence gives on this base: its mods, each with the essence that forces it, as a leaf line says it
            forced = [(mod, essence_tier(self.data, self.ab.base_id, mod.id)) for mod in held if mod.is_essence_only]
            forced = [(mod, note) for mod, note in forced if note]
            if not forced:
                return ANY_MOD
            if len(forced) == 1:
                mod, note = forced[0]
                return Slot(mod_text(mod), "mod", tuple(mark for mark in _marks(mod) if mark != "essence only"), note)
            text = _tiers_joined(_hashes(mod_text_of(mod)) for mod, _ in forced)
            return Slot(text, "mod", tuple(mark for mark in _marks(forced[0][0]) if mark != "essence only"), " or ".join(dict.fromkeys(note for _, note in forced)))
        ordered = sorted(family, key=lambda mod: (self.tiers.get(mod.id, 0), mod.id))
        if len(ordered) == 1:
            return Slot(mod_text(ordered[0]), "mod", _marks(ordered[0]), _tier_note(self.tiers, [ordered[0].id]))
        note = _tier_note(self.tiers, [mod.id for mod in ordered])
        text = _tiers_joined((_hashes(mod_text_of(mod)) for mod in ordered), every=note == "any tier")
        return Slot(text, "mod", _marks(ordered[0]), note)

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


def _rank(row: Slot) -> int:
    """Fractured rows first, then wanted, other mods, crafted ones."""
    if "fractured" in row.marks:
        return 0
    return {"wanted": 1, "crafted": 3}.get(row.tone, 2)


VARIES = "only on some of these items, each in a slot marked any:"  # the heading of the rows only some states of a card hold (#889)


def _shared_rows(per_state: list[list[Slot]]) -> tuple[list[Slot], list[list[Slot]]]:
    """The rows every state has (as many times as each has it at least), and per state the rows it has beside them."""
    counts = [Counter(rows) for rows in per_state]
    shared = reduce(and_, counts)
    rest = [list((count - shared).elements()) for count in counts]
    return sorted(shared.elements(), key=_rank), rest


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
    A compressed state holds no implicits, quality or offer yet (ticket #69), so the card shows the base's
    implicits as ranges, no quality and no offer. Raises `ValueError` for no state, and for a state that belongs to another goal.
    """
    if not states:
        raise ValueError("a card needs at least one state")
    reader = reader or _StateReader(abstraction)
    data, base_id = reader.data, abstraction.base_id
    read = [reader.read(state) for state in states]
    only_normal = all(state.flags.rarity is Rarity.NORMAL for state in states)
    only_magic = all(state.flags.rarity is Rarity.MAGIC for state in states)  # a Magic item draws its own one prefix and one suffix (#962)
    sides: dict[Side, tuple[Slot, ...]] = {}
    varies: list[Slot] = []
    for side in SIDES:
        rows, rest = _shared_rows([entry.rows[side] for entry in read])
        limit = _capacity(data, base_id, side, Rarity.MAGIC if only_magic else Rarity.RARE)
        varies += [replace(row, marks=(*row.marks, side.value)) for row in dict.fromkeys(row for each in rest for row in each) if row.tone != "any"]
        if reader.tracked:
            counts = [entry.junk[side] + len(each) for entry, each in zip(read, rest)]  # what a state holds beside the shared rows
            rows += [ANY_MOD] * min(min(counts), max(0, limit - len(rows)))
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
        groups=(Group(VARIES, tuple(sorted(varies, key=_rank))),) if varies else (),
    )


def leaf_sides(data: GameData, target: Target) -> list[Side]:
    """The side of each requirement leaf of `target`, in the order of `Goal.leaves` (the text report says it of a group's members, as the card does)."""
    tiers = page_tiers(data, target.base_id, target.influences | target.start_item.influences)
    found: list[Side] = []

    def walk(node) -> None:
        if isinstance(node, KOfN):
            for member in node.of:
                walk(member)
        else:
            found.append(_leaf_slot(data, target.base_id, tiers, node.mod_ids, node.min_tier, target.item_level, node.tier_ok)[0])

    for requirement in target.requirements:
        walk(requirement)
    return found
