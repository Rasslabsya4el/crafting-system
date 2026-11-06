"""The Vaal Orb's part of the contract suite's fixture (ticket #259): items of a world with a corrupted implicit pool.

The amulet of the fixture has no corrupted pool, so the Vaal Orb declares `applies_only_to` and the suite asks it about the items of
`corruption_support.DATA` (the contract data plus a pool on an amulet, boots, a belt and four jewels) and no other kind:

* `vaal_amulet`: a rare amulet with two mods and no implicit (the implicit is just added); `vaal_amulet_fractured`: a fractured mod stays;
* `vaal_normal` and `vaal_magic`: the Orb is accepted on any rarity; * `vaal_boots_two`: an Exarch and an Eater implicit, one goes;
* `vaal_belt_stored` and `vaal_belt_replaced`: a belt with its base implicit, and an item whose base implicit went to an Ember (it lists the Eater one alone, #484);
* `vaal_cobalt` and `vaal_prismatic`: a jewel with a corruption-exclusive unique (a dead end) and one without (nothing);
* `vaal_amulet_stranded`: 40 Memory Strands, which the Orb neither cuts nor spends; `vaal_amulet_corrupted`: the refusal.
"""

from contract_registry import register_extra_item

KINDS = ("vaal",)


def _data():
    from corruption_support import DATA  # late: contract_support loads this module while it builds CONTRACT_DATA

    return DATA


def _items():
    from abstraction_pool import LIFE_1, MANA_1, RESIST_2
    from contract_support import _roll
    from corruption_support import BELT, COBALT, PRISMATIC, amulet, base_implicit, eater, exarch, on
    from implicits_support import BOOTS

    from crafting_system.items import Rarity

    junk = (_roll(RESIST_2), _roll(LIFE_1))
    return {
        "vaal_amulet": lambda: amulet(*junk),
        "vaal_amulet_fractured": lambda: amulet(_roll(RESIST_2, fractured=True), _roll(LIFE_1), _roll(MANA_1)),
        "vaal_normal": lambda: amulet(rarity=Rarity.NORMAL),
        "vaal_magic": lambda: amulet(_roll(LIFE_1), rarity=Rarity.MAGIC),
        "vaal_boots_two": lambda: on(BOOTS, *junk, implicits=(exarch(), eater())),
        "vaal_belt_stored": lambda: on(BELT, *junk, implicits=(base_implicit(),)),
        "vaal_belt_replaced": lambda: on(BELT, *junk, implicits=(eater(),)),
        "vaal_cobalt": lambda: on(COBALT),
        "vaal_prismatic": lambda: on(PRISMATIC),
        "vaal_amulet_stranded": lambda: amulet(*junk, memory_strands=40),
        "vaal_amulet_corrupted": lambda: amulet(*junk, corrupted=True),
    }


def _build(name: str):
    return _items()[name]()


for _name in (
    "vaal_amulet", "vaal_amulet_fractured", "vaal_normal", "vaal_magic", "vaal_boots_two", "vaal_belt_stored", "vaal_belt_replaced",
    "vaal_cobalt", "vaal_prismatic", "vaal_amulet_stranded", "vaal_amulet_corrupted",
):
    register_extra_item(_name, KINDS, _data, lambda name=_name: _build(name))
