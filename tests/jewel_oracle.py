"""A hand oracle for crafting a jewel, independent of `crafting_system.actions` (ticket #201).

It reads the raw mods of the game data (domain, generation type, required level, spawn weights, families) and
works out the draws of the jewel orbs with `Fraction`s: the pool of a jewel base is every prefix and suffix mod
of the domain of the base whose required level is at most the item level, with the weight of the first
spawn-weight entry whose tag the base has (`affix_pool.spawn_weight_first_match`), grouped by family and side.
It does not use the pool, the draw engine or the item model.

Rules it plays, written again as plain code: one draw picks a mod among the families not yet drawn, from the
sides that still have a slot, in proportion to weight (`affix_pool.draw_proportional_to_weight`,
`affix_pool.one_pool_for_both_sides`); the whole family leaves, whichever side its mod was on
(`affix_pool.family_may_span_both_sides`); a rare jewel holds 2 prefixes and 2 suffixes and a magic one 1 and 1.
"""

from collections import defaultdict
from fractions import Fraction
from itertools import combinations, permutations

PREFIX, SUFFIX = "prefix", "suffix"


def family_table(data, base_id: str, item_level: int) -> dict[str, dict[str, Fraction]]:
    """`{family: {side: weight}}` of the draws on an empty jewel of `base_id`, read from the raw mods."""
    base = data.base_items[base_id]
    table: dict[str, dict[str, Fraction]] = defaultdict(lambda: defaultdict(Fraction))
    for mod in data.mods.values():
        if mod.domain != base.domain or mod.generation_type not in (PREFIX, SUFFIX) or mod.required_level > item_level:
            continue
        weight = next((w.weight for w in mod.spawn_weights if w.tag in base.tags), 0)
        if weight > 0:
            table[mod.families[0]][mod.generation_type] += weight
    return {name: dict(sides) for name, sides in table.items()}


def sequence_chance(table, order: tuple[str, ...], free: dict[str, int]) -> Fraction:
    """The chance that the draws pick the families of `order` in that order, whichever side each mod is on."""

    def walk(step: int, gone: frozenset[str], room: dict[str, int]) -> Fraction:
        if step == len(order):
            return Fraction(1)
        open_ = {
            (name, side): weight
            for name, sides in table.items()
            if name not in gone
            for side, weight in sides.items()
            if room[side] > 0
        }
        whole = sum(open_.values(), Fraction(0))
        chance = Fraction(0)
        for side, weight in table[order[step]].items():
            if room[side] > 0:
                chance += weight / whole * walk(step + 1, gone | {order[step]}, {**room, side: room[side] - 1})
        return chance

    return walk(0, frozenset(), dict(free))


def chance_of_families(table, free: dict[str, int], picks: int, wanted: tuple[str, ...]) -> Fraction:
    """The chance that `picks` draws (all the room allows) pick every family of `wanted`, among other families."""
    others = [name for name in table if name not in wanted]
    total = Fraction(0)
    for extra in combinations(others, picks - len(wanted)):
        for order in permutations((*wanted, *extra)):
            total += sequence_chance(table, order, free)
    return total
