"""The influence crafts' part of the contract suite's fixture (ticket #154): items on the helmet of the influence data.

The amulet of the fixture is no body armour, boots, gloves or helmet, so the Orb of Dominance has nothing to do on it; the helmet has
no mod of the fixture pool, so the other kinds would draw nothing on it. Each item is for the kinds named with it. Both helmets are
at item level 84.
"""

import functools

from contract_registry import register_extra_item
from influence_support import P1, PLAIN, S1, influence_data
from influence_support import helmet as contract_helmet
from influence_support import roll as roll_on_helmet

from crafting_system.items import Influence


@functools.cache
def contract_helmet_data():
    from contract_support import CONTRACT_DATA  # late: contract_support loads this module while it builds CONTRACT_DATA

    return influence_data(CONTRACT_DATA)  # the contract data with a helmet base and influence mods


register_extra_item(
    "helmet_two_shaper",
    ("orb-of-dominance",),
    contract_helmet_data,
    lambda: contract_helmet(roll_on_helmet(P1, 3), roll_on_helmet(S1, 2), influences=frozenset({Influence.SHAPER})),
)
register_extra_item("helmet_plain", ("influenced-exalted-orb",), contract_helmet_data, lambda: contract_helmet(roll_on_helmet(PLAIN, 1)))

# Strands (ticket #286): the influenced Exalted Orb cuts, and on this helmet its Shaper prefix family has three tiers and its suffix family two, so at 100 strands
# the cut leaves other mods than at 0 (the amulet fixtures have no such table; `check_cutting_kinds_differ_from_the_uncut_draw` asks for one).
register_extra_item(
    "helmet_plain_stranded",
    ("influenced-exalted-orb",),
    contract_helmet_data,
    lambda: contract_helmet(roll_on_helmet(PLAIN, 1), memory_strands=100),
)
