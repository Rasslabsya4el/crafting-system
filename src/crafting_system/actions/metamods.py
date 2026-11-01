"""What the five metamods do to an item's actions (ticket #68, rules of issues #11 and #28).

A metamod is a crafted mod that changes what the other actions may do. The item model finds them
(`Item.metamods`); this module says what each one means, and the actions ask it:

* `Prefixes Cannot Be Changed` / `Suffixes Cannot Be Changed` lock a side. Every mod on a locked side
  is kept by a reroll, by an Orb of Scouring and by an Orb of Annulment (`locked_sides`, `kept_by_lock`,
  `kept_by_reroll`); the open slots of that side can still be filled by a draw (`metamods.locks_protect_existing_mods`).
* `Cannot roll Attack Modifiers` / `Cannot roll Caster Modifiers` keep the mods with the `attack` /
  `caster` tag out of a draw (`blocked_tags`, `allowed_by_tags`; the tag is the mod's `implicit_tags`,
  `metamods.tag_is_implicit_tag`) and out of an Orb of Annulment's candidates. A reroll that removes the
  metamod itself is no longer under it (`metamods.reroll_needs_retained_carrier`): only a metamod the
  reroll keeps filters its draw.
* `Can have up to 3 Crafted Modifiers` raises the limit of crafted mods to three (`crafted_limit`). The enchantment
  "Can have 1 additional Crafted Modifier" raises it to two without using an affix slot; with both the limit is the
  larger of the two, three, never their sum (ADR-0053, `crafted_limit_of`).
* Essences and resonators refuse the four metamods above (`refuse_blocking_metamod`).

A metamod sits on the side opposite to the one it locks (the lock of prefixes is a suffix), so a
reroll under one lock removes the metamod and keeps the locked side, and an item that holds both locks
keeps everything.

The five metamods (`metamods.py`, ticket #68): `Prefixes` / `Suffixes Cannot Be Changed` keep the mods of
the locked side through a reroll (Chaos, Alteration, Harvest), a Scouring and an Annulment, and the open slots
still fill; `Cannot roll Attack` / `Caster Modifiers` keep the mods with that tag out of every draw on an item that
still holds the metamod (a reroll that removes it is not filtered), out of an Annulment's candidates, and, on a
Harvest reforge, out of the first (guaranteed) mod only; essences and resonators refuse the four; the multimod
lifts the crafted-mod limit to three, and the enchantment "Can have 1 additional Crafted Modifier" to two (the larger of
the two with both, ADR-0053; `crafted_limit_of`). No action raises `OutOfScopeError` for a metamod.
"""

from crafting_system.data import GameData, Mod
from crafting_system.items import ExplicitMod, Item, Metamod, Side, enchant_info
from crafting_system.rules import get_rule, rule_by_id

from .errors import NotApplicableError

__all__ = [
    "BLOCKED_TAG",
    "BLOCKING",
    "allowed_by_tags",
    "blocked_tags",
    "crafted_limit_of",
    "grants_extra_crafted_slot",
]

LOCKS_PROTECT_EXISTING_MODS = get_rule("metamods.locks_protect_existing_mods")
TAG_IS_IMPLICIT_TAG = get_rule("metamods.tag_is_implicit_tag")
ADDS_RESPECT_TAG_FILTERS = get_rule("metamods.adds_respect_tag_filters")
REROLL_NEEDS_RETAINED_CARRIER = get_rule("metamods.reroll_needs_retained_carrier")
ESSENCE_REFUSED_BY_METAMOD = get_rule("metamods.essence_refused")
MULTIMOD_RAISES_CRAFTED_LIMIT = get_rule("metamods.multimod_raises_crafted_limit")
ONE_CRAFTED_MOD = get_rule("bench_craft.one_crafted_mod_by_default")
# Both stay declared (the actions list them as claims they read); the "neither" and "multimod" entries of the table
# in `crafted_limit_of` repeat their values, and a test compares them.

LOCKED_SIDE: dict[Metamod, Side] = {
    Metamod.PREFIXES_CANNOT_CHANGE: Side.PREFIX,
    Metamod.SUFFIXES_CANNOT_CHANGE: Side.SUFFIX,
}
BLOCKED_TAG: dict[Metamod, str] = {
    Metamod.NO_ATTACK_MODS: "attack",
    Metamod.NO_CASTER_MODS: "caster",
}
BLOCKING = frozenset(LOCKED_SIDE) | frozenset(BLOCKED_TAG)  # the four that essences and resonators refuse


def locked_sides(data: GameData, item: Item) -> frozenset[Side]:
    """The sides whose mods the item's lock metamods protect."""
    return frozenset(LOCKED_SIDE[metamod] for metamod in item.metamods(data) if metamod in LOCKED_SIDE)


def blocked_tags(data: GameData, item: Item) -> frozenset[str]:
    """The mod tags the item's Attack and Caster metamods keep out of a draw."""
    return frozenset(BLOCKED_TAG[metamod] for metamod in item.metamods(data) if metamod in BLOCKED_TAG)


def allowed_by_tags(mod: Mod, blocked: frozenset[str]) -> bool:
    """Whether `mod` carries none of the `blocked` tags (a mod with both tags is blocked by either metamod)."""
    return not blocked.intersection(mod.implicit_tags)


def on_locked_side(data: GameData, entry: ExplicitMod, sides: frozenset[Side]) -> bool:
    """Whether the mod sits on one of the locked `sides`."""
    return data.mods[entry.mod_id].generation_type in {side.value for side in sides}


def kept_by_lock(data: GameData, item: Item) -> tuple[ExplicitMod, ...]:
    """The mods a lock protects: every mod on a locked side (fractured or not, crafted or not)."""
    sides = locked_sides(data, item)
    if not sides:
        return ()
    return tuple(entry for entry in item.mods if on_locked_side(data, entry, sides))


def kept_by_reroll(data: GameData, item: Item) -> tuple[ExplicitMod, ...]:
    """The mods a reroll leaves on the item: the fractured ones and those on a locked side."""
    locked = {entry.mod_id for entry in kept_by_lock(data, item)}
    return tuple(entry for entry in item.mods if entry.fractured or entry.mod_id in locked)


def grants_extra_crafted_slot(data: GameData, enchantment: str | None) -> bool:
    """Whether `enchantment` (a mod id or None) is the one that lets an item hold one more crafted mod."""
    mod = data.mods.get(enchantment) if enchantment is not None else None
    info = enchant_info(mod) if mod is not None else None
    return info is not None and info.extra_slot


def crafted_limit_of(data: GameData, *, multimod: bool, enchantment: str | None) -> int:
    """How many crafted mods an item holds at most, from what it has: 1 with neither, 2 with the extra slot, 3 with the multimod
    (itself one of them), 3 with both: the larger of the two, never the sum (`enchantment.crafted_slot_with_multimod_takes_the_larger`).

    The enchantment is a constant of the problem, which no action adds or removes, so the search passes the start item's to
    this function (the compressed state does not hold it) while an action reads it from the item (`crafted_limit`).

    The table is read here and not held as a constant of the module: a constant would make every bench craft and beast craft
    list this approximate claim, whose "both" case matters only on an item that holds the enchantment and the multimod.
    """
    extra = grants_extra_crafted_slot(data, enchantment)
    table = rule_by_id("enchantment.crafted_slot_with_multimod_takes_the_larger").value
    if multimod and extra:
        return table["both"]
    if multimod:
        return table["multimod"]
    return table["extra_slot"] if extra else table["neither"]


def crafted_limit(data: GameData, item: Item) -> int:
    """How many crafted mods the item holds at most: one, two with the extra slot enchant, three with the multimod (itself one of them)."""
    multimod = Metamod.MULTIPLE_CRAFTED_MODS in item.metamods(data)
    return crafted_limit_of(data, multimod=multimod, enchantment=item.enchantment)


def refuse_blocking_metamod(data: GameData, item: Item, what: str) -> None:
    """Raise `NotApplicableError` for an item holding a lock or an Attack/Caster metamod: `what` cannot be used on it.

    The multimod does not block an essence or a resonator.
    """
    blocking = item.metamods(data) & BLOCKING
    if blocking:
        names = ", ".join(sorted(metamod.value for metamod in blocking))
        raise NotApplicableError(f"{what} cannot be used on an item with a metamod that affects mod outcomes ({names})")
