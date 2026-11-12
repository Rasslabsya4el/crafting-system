"""Shared helpers for the tests of the socket finish (ticket #231, B6 S5; ADR-0045, ADR-0058).

`finish_data()` is the contract data with every socket action the finish knows: the bench's count and link options of `sockets_support.bench_data()`,
the three colour options of `sockets_colour_support.colour_data()`, the Chromatic Orb named as in the game, and the body armour (class maximum 6) and the
helmet (4) asking for the three attributes alike, so a coloured socket is red, green or blue a third of the time each (the item of ADR-0058's fixture).
`all_steps` offers every finish action at one orb each, the bench crafts at their orb counts and the Omens at `omen` (ADR-0058, "Measured").
"""

import dataclasses
import functools

from items_support import BODY
from sockets_colour_support import BENCH_COLOUR_COSTS, CHROMATIC_ID
from sockets_support import BENCH_COUNT_COSTS, BENCH_LINK_COSTS, HELMET, bench_data

from crafting_system.abstraction import FinishStep
from crafting_system.actions.socket_colours import BenchSocketColours, ChromaticOrb
from crafting_system.actions.socket_orbs import BenchSocketCount, BenchSocketLinks, JewellersOrb, OrbOfFusing
from crafting_system.data import BaseItem, CostEntry

EQUAL = (50, 50, 50)


@functools.cache
def finish_data():
    """The bench data with the colour options, the Chromatic Orb, and the body armour and helmet asking for the three attributes alike."""
    data = bench_data()
    bases = dict(data.base_items)
    for base_id in (BODY, HELMET):
        bases[base_id] = dataclasses.replace(bases[base_id], attribute_requirements=EQUAL)
    bases[CHROMATIC_ID] = BaseItem(CHROMATIC_ID, "Chromatic Orb", "StackableCurrency", "currency", 1, (), (), "released")
    template = next(option for option in data.bench_options if option.actions.change_socket_count is not None)
    none = dataclasses.replace(template.actions, change_socket_count=None, link_sockets=None, color_sockets=None)
    options = list(data.bench_options)
    for minimum, price in BENCH_COLOUR_COSTS.items():
        options.append(dataclasses.replace(template, actions=dataclasses.replace(none, color_sockets="N" * minimum), cost=(CostEntry(CHROMATIC_ID, price),)))
    return dataclasses.replace(data, base_items=bases, bench_options=tuple(options))


def all_steps(data, *, orb: float = 1.0, omen: float = 50.0, bench: bool = True, omens: bool = True) -> list[FinishStep]:
    """Every finish action: the three orbs at `orb`, each with its Omen at `orb + omen`, and the bench crafts at their orb counts times `orb`."""
    steps = [
        FinishStep("Jeweller's Orb", JewellersOrb(), orb),
        FinishStep("Orb of Fusing", OrbOfFusing(), orb),
        FinishStep("Chromatic Orb", ChromaticOrb(), orb),
    ]
    if omens:
        steps += [
            FinishStep("Jeweller's Orb with Omen of the Jeweller", JewellersOrb(omen=True), orb + omen),
            FinishStep("Orb of Fusing with Omen of Connections", OrbOfFusing(omen=True), orb + omen),
            FinishStep("Chromatic Orb with Omen of Trichromatism", ChromaticOrb(omen=True), orb + omen),
        ]
    if bench:
        steps += [FinishStep(f"Bench craft {count} sockets", BenchSocketCount(count), price * orb) for count, price in BENCH_COUNT_COSTS.items()]
        steps += [FinishStep(f"Bench craft {links} links", BenchSocketLinks(links), price * orb) for links, price in BENCH_LINK_COSTS.items()]
        steps += [FinishStep(f"Bench craft {minimum} coloured sockets", BenchSocketColours(minimum), price * orb) for minimum, price in BENCH_COLOUR_COSTS.items()]
    return steps
