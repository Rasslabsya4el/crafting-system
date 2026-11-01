"""The single-item beast crafts of 3.29 (ticket #147, rules of issues #88 and #93, ADR-0030).

A beast craft consumes red beasts (priced by name) and rare beasts of any kind: `recipe_resources` turns a
recipe of `beastcraft.recipe_beasts` into the resources of an action, the rare beasts at the setting
`rare_creature_price` (default `beastcraft.any_rare_creature_price`, 1 chaos each). The crafts here are the
Talisman fractures and the aspects; the Wild Bristle Matron and the two side-swap beasts are in `beast_swaps`.
Several rules rest on Craft of Exile alone and carry the approximate mark (ADR-0028).
"""

from collections.abc import Mapping

from crafting_system.rules import get_rule

RECIPE_BEASTS = get_rule("beastcraft.recipe_beasts")
DEFAULT_BEAST_LEVEL = get_rule("beastcraft.default_beast_level")
ANY_RARE_CREATURE_PRICE = get_rule("beastcraft.any_rare_creature_price")

ANY_RARE_CREATURE = "any_rare_creature"  # the key of `recipe_beasts` for the rare beasts of any kind
CHAOS_ORB = "Chaos Orb"  # the price-file name the rare beasts are paid in


def recipe_resources(recipe: str, rare_creature_price: int = ANY_RARE_CREATURE_PRICE.value) -> Mapping[str, int]:
    """What one use of `recipe` consumes by price-file name: its named beasts, and the rare beasts as Chaos Orbs."""
    resources: dict[str, int] = {}
    for name, count in RECIPE_BEASTS.value[recipe].items():
        if name == ANY_RARE_CREATURE:
            resources[CHAOS_ORB] = count * rare_creature_price
        else:
            resources[name] = count
    return resources
