"""How the values of a mod are rolled: uniformly over the integers of each stat's range, once or lucky (ticket #71).

A stat that runs `min` to `max` (the order in the data can be either) rolls a uniform integer between the two,
both included, independently of the other stats of the mod (`affix_pool.values_uniform_integers`; the
independence of a hybrid mod's stats is the approximate claim `divine_orb.hybrid_stats_roll_independently`).
A lucky roll (a Sanctified Fossil, `fossils.sanctified_values_lucky`) rolls the stat twice and keeps the better
one, the one nearer the stat's `max`. This module holds no rule of its own: the actions that call it cite them.
"""

import random

from crafting_system.data import Mod, StatRange


def roll_value(rng: random.Random, stat: StatRange, lucky: bool = False) -> int:
    """One value of `stat`; with `lucky` the better of two rolls (the one nearer `stat.max`)."""
    low, high = min(stat.min, stat.max), max(stat.min, stat.max)
    first = rng.randint(low, high)
    if not lucky:
        return first
    second = rng.randint(low, high)
    return max(first, second) if stat.max >= stat.min else min(first, second)


def roll_values(rng: random.Random, mod: Mod, lucky: bool = False) -> tuple[int, ...]:
    """The values of `mod`, one per stat in the order of `mod.stats`, each rolled by `roll_value`."""
    return tuple(roll_value(rng, stat, lucky) for stat in mod.stats)
