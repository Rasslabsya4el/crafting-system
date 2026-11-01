"""Data, items and the layer 1 oracle for the veils and the unveil offer in the compressed state (ticket #145, ADR-0026).

The data is the small amulet pool of `abstraction_pool` (seven ordinary families), the veiled records of `veiled_support` (the
placeholders, the unveiled prefixes and suffixes of the amulet) and three mods added here, so that the cases the compressed state
must keep apart exist:

* `SPEED_ORDINARY`, an ordinary suffix of the family `VeilTestSpeed`, the family of the unveiled `VeilTestSpeed1` (the real pairs:
  Movement Speed on boots, Life, Strength): the same family, one of them a veiled mod;
* `OTHER_CRAFT_ARMOUR`, a crafted prefix of another master in the family `VeilTestArmour`, the family of `JunMasterVeilTestArmour1`
  (the craftable version of the unveiled `VeilTestArmour1`): the same crafted family, one of them the craftable version of a veiled mod;
* the bench crafts of the Jun mod and of the other master (copies of the fixture's own option), for the unveil blocks.

`concrete_pushforward` is the layer 1 oracle: the exact distribution of the compressed states that the finished items of an action
on a concrete item give, listed from the action itself and compressed one by one. `closure` lists every concrete item that a set of
actions reaches from some starts. Nothing here reads the kernel of the abstraction.
"""

import dataclasses
from collections import defaultdict
from collections.abc import Iterable, Mapping
from fractions import Fraction

from abstraction_pool import LEVEL, SMALL
from contract_support import finished
from items_support import AMULET
from veiled_support import CRAFTED_ARMOUR, PLACEHOLDER_PREFIX, PLACEHOLDER_SUFFIX, veiled_mods

from crafting_system.abstraction import Abstraction
from crafting_system.actions import ActionError
from crafting_system.items import ExplicitMod, Item, Rarity, tier_table, veiled_placeholder

SPEED_ORDINARY = "VeilTestSpeedOrdinary1"
OTHER_CRAFT_ARMOUR = "HaakMasterVeilTestArmour1"


def _extra_mods() -> dict[str, object]:
    template = SMALL.mods["ManaLeechPermyriadSuffix1"]
    speed = dataclasses.replace(
        template,
        id=SPEED_ORDINARY,
        type="VeilTestSpeedOrdinary",
        families=("VeilTestSpeed",),
        stats=tuple(dataclasses.replace(stat, id="veil_test_speed_ordinary") for stat in template.stats),
    )
    unveiled_armour = veiled_mods()[CRAFTED_ARMOUR]
    other_craft = dataclasses.replace(
        unveiled_armour, id=OTHER_CRAFT_ARMOUR, type="HaakMasterVeilTestArmour", stats=tuple(dataclasses.replace(stat, id="haak_armour") for stat in unveiled_armour.stats)
    )
    return {speed.id: speed, other_craft.id: other_craft}


def _bench_options():
    options = [option for option in SMALL.bench_options if option.actions.add_explicit_mod in (None, *SMALL.mods)]  # the fixture's crafts of mods the small pool lacks are left out
    template = next(option for option in SMALL.bench_options if option.actions.add_explicit_mod is not None)
    for mod_id in (CRAFTED_ARMOUR, OTHER_CRAFT_ARMOUR):
        options.append(dataclasses.replace(template, item_classes=("Amulet",), actions=dataclasses.replace(template.actions, add_explicit_mod=mod_id)))
    return tuple(options)


DATA = dataclasses.replace(
    SMALL,
    mods={**SMALL.mods, **veiled_mods(), **_extra_mods()},
    bench_options=_bench_options(),
)
TIERS = tier_table(DATA, AMULET)
PRE, SUF = PLACEHOLDER_PREFIX, PLACEHOLDER_SUFFIX
F = Fraction


def rolled(mod_id: str, *, data=DATA, tiers: Mapping[str, int] | None = None, **flags) -> ExplicitMod:
    """Any mod of the data at its lowest values (and its tier on the amulet, 1 for a mod with none)."""
    mod = data.mods[mod_id]
    table = TIERS if tiers is None else tiers
    return ExplicitMod(mod_id, table.get(mod_id, 1), tuple(min(stat.min, stat.max) for stat in mod.stats), **flags)


def holder(mod_id: str, data=DATA) -> ExplicitMod:
    return veiled_placeholder(data, mod_id)


def amulet(*mods: ExplicitMod, data=DATA, rarity: Rarity = Rarity.RARE, **fields) -> Item:
    return Item.build(data, base_id=AMULET, item_level=LEVEL, rarity=rarity, mods=mods, **fields)


def concrete_pushforward(ab: Abstraction, data, item: Item, action) -> dict:
    """The exact kernel of `action` on `item` as its finished items give it: each compressed by `ab`, the chances added up.

    Raises what `action.outcomes` raises when the game refuses the item.
    """
    expected: dict = defaultdict(Fraction)
    for chance, result in finished(action.outcomes(data, item), data):
        expected[ab.compress(result)] += chance
    return dict(expected)


def closure(data, starts: Iterable[Item], actions, *, limit: int = 4000) -> list[Item]:
    """Every concrete item that `actions` reach from `starts` (the starts included), in the order found; at most `limit`.

    An action that refuses an item (`ActionError`) is skipped there.
    """
    seen: dict[Item, None] = dict.fromkeys(starts)
    queue = list(seen)
    while queue and len(seen) < limit:
        item = queue.pop(0)
        for action in actions:
            try:
                results = finished(action.outcomes(data, item), data)
            except ActionError:
                continue
            for _, result in results:
                if result not in seen:
                    seen[result] = None
                    queue.append(result)
    return list(seen)
