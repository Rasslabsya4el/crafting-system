"""A hand oracle for the Awakener's Orb (ticket #213), independent of `crafting_system.actions`.

It plays the rules of ADR-0032 as plain code over the mods of a small `GameData`, walking every pair and every draw order
exactly with `Fraction`s: it uses no pool builder, no engine, no item model. The only shared thing is the data (`Mod`
fields: family, side, spawn weights, required level) and the names of the influence tags.

The rules it plays:

* the receiver holds some influenced mods (named by the caller); the donor holds one; a pair is (a receiver mod, the donor mod)
  of two different mods, and every pair is equally likely;
* two mods of one family (a group conflict) leave one of them: the receiver's (`"receiver"`) or the donor's (`"donor"`);
* every other mod of the receiver goes; the finished item holds a total of 4, 5 or 6 mods (8:3:1) counting the kept ones, so
  `total - kept` mods are drawn, one at a time, from the mods of the domain with a positive weight on the item's tags and a
  required level within the item level, in proportion to weight; a drawn mod's whole family leaves the pool and its side takes
  a slot; a side holds 3; a draw stops short when nothing can be drawn.
"""

from fractions import Fraction
from functools import cache

TOTALS = {4: Fraction(8, 12), 5: Fraction(3, 12), 6: Fraction(1, 12)}
SIDE_CAPACITY = 3


def _weight(mod, tags: frozenset[str]) -> int:
    """The weight of the first spawn entry whose tag the item has (0 when none)."""
    for entry in mod.spawn_weights:
        if entry.tag in tags:
            return entry.weight
    return 0


def chance_of_holding(
    data, tags: frozenset[str], domain: str, item_level: int, held_influenced: list[str], donor: str, reading: str, wanted: set[str]
) -> Fraction:
    """The chance that the finished item holds every mod id in `wanted`.

    `tags` are the item's tags (its base tags and both influence tags); `held_influenced` the receiver's influenced mods.
    """
    pool = {
        mod.id: mod
        for mod in data.mods.values()
        if mod.domain == domain
        and mod.generation_type in ("prefix", "suffix")
        and mod.required_level <= item_level
        and _weight(mod, tags) > 0
    }
    pairs = [mod_id for mod_id in held_influenced if mod_id != donor]
    answer = Fraction(0)
    for received in pairs:
        if set(data.mods[received].families) & set(data.mods[donor].families):
            kept = [received] if reading == "receiver" else [donor]
        else:
            kept = [received, donor]
        answer += Fraction(1, len(pairs)) * _hold_after(data, tags, pool, tuple(sorted(kept)), frozenset(wanted))
    return answer


def _hold_after(data, tags, pool, kept: tuple[str, ...], wanted: frozenset[str]) -> Fraction:
    """The chance of holding `wanted` for one set of kept mods: the sum over the totals of the chance of the draws."""
    families = {family for mod_id in kept for family in data.mods[mod_id].families}
    used = {"prefix": 0, "suffix": 0}
    for mod_id in kept:
        used[data.mods[mod_id].generation_type] += 1
    pool = {mod_id: mod for mod_id, mod in pool.items() if not set(mod.families) & families and mod_id not in kept}

    @cache
    def walk(drawn: frozenset[str], picks: int, prefixes: int, suffixes: int) -> Fraction:
        if wanted <= set(kept) | drawn:
            return Fraction(1)
        if picks == 0:
            return Fraction(0)
        taken = {family for mod_id in drawn for family in data.mods[mod_id].families}
        room = {"prefix": SIDE_CAPACITY - prefixes, "suffix": SIDE_CAPACITY - suffixes}
        open_mods = [
            mod_id
            for mod_id, mod in pool.items()
            if mod_id not in drawn and not set(mod.families) & taken and room[mod.generation_type] > 0
        ]
        if not open_mods:
            return Fraction(0)  # the draw stops short and `wanted` is not all held
        total = sum(_weight(data.mods[mod_id], tags) for mod_id in open_mods)
        answer = Fraction(0)
        for mod_id in open_mods:
            side = data.mods[mod_id].generation_type
            answer += Fraction(_weight(data.mods[mod_id], tags), total) * walk(
                drawn | {mod_id}, picks - 1, prefixes + (side == "prefix"), suffixes + (side == "suffix")
            )
        return answer

    return sum(
        (chance * walk(frozenset(), max(0, count - len(kept)), used["prefix"], used["suffix"]) for count, chance in TOTALS.items()),
        Fraction(0),
    )
