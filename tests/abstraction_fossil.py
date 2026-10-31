"""The brute force for a resonator, for the layer-1 tests of the fossil kernel (ticket #62).

`fossil_finished` lists every finished item of using `action` on `start` with its exact probability.
It takes from `actions` only what a fossil changes: the components (a mixture of pools, each with its
probability and its forced mod) and whether a Fractured Fossil is socketed. The draws inside a
component are enumerated by `abstraction_oracle.finished_items`, which does not touch
`exact_distribution`. A Fractured Fossil fractures one finished mod, uniformly: every finished item
turns into as many items as it has mods, each with one of them fractured.
"""

import dataclasses
from fractions import Fraction

from abstraction_oracle import finished_items

from crafting_system.data import GameData
from crafting_system.items import Item


def fossil_finished(data: GameData, action, start: Item) -> list[tuple[Item, Fraction]]:
    """Every finished item of the resonator `action` on `start`, with its probability (they sum to 1)."""
    outcomes = action.outcomes(data, start)
    result = []
    for share, part in outcomes.components:
        for item, chance in finished_items(data, start, None, forced=part.forced, pool=part.pool):
            if not outcomes.fractures or not item.mods:
                result.append((item, share * chance))
                continue
            for index in range(len(item.mods)):
                mods = tuple(
                    dataclasses.replace(entry, fractured=True) if number == index else entry
                    for number, entry in enumerate(item.mods)
                )
                result.append((item.changed(data, mods=mods), share * chance / len(item.mods)))
    assert sum(chance for _, chance in result) == 1
    return result
