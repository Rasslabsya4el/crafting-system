"""The Locus of Corruption's part of the contract suite's fixture (ticket #262): items of a world with a corrupted implicit pool.

The amulet of the fixture has no corrupted pool, so the Locus declares `applies_only_to` and the suite asks it about the items of
`locus_support.DATA` (the Vaal Orb's world plus a corrupted implicit that shares a mod group) and no other kind:

* `locus_amulet`: a rare amulet with two mods and no implicit (both are added); `locus_amulet_fractured`: a fractured mod stays;
* `locus_normal` and `locus_magic`: the altar takes any rarity; `locus_boots_one` and `locus_boots_two`: an Eldritch implicit or two, all go;
* `locus_belt_stored`: a belt with its base implicit; `locus_amulet_stranded`: 40 Memory Strands, which the altar neither cuts nor spends;
* `locus_amulet_corrupted`: the refusal.
"""

from contract_registry import register_extra_item

KINDS = ("locus",)


def _data():
    from locus_support import DATA  # late: contract_support loads this module while it builds CONTRACT_DATA

    return DATA


def _items():
    from abstraction_pool import LIFE_1, MANA_1, RESIST_2
    from contract_support import _roll
    from corruption_support import BELT, LEVEL, base_implicit, eater, exarch
    from implicits_support import BOOTS
    from items_support import AMULET
    from locus_support import DATA

    from crafting_system.items import Item, Rarity

    def on(base_id, *mods, implicits=(), rarity=Rarity.RARE, **fields):
        return Item.build(DATA, base_id=base_id, item_level=LEVEL, rarity=rarity, mods=mods, implicits=implicits, **fields)

    junk = (_roll(RESIST_2), _roll(LIFE_1))
    return {
        "locus_amulet": lambda: on(AMULET, *junk),
        "locus_amulet_fractured": lambda: on(AMULET, _roll(RESIST_2, fractured=True), _roll(LIFE_1), _roll(MANA_1)),
        "locus_normal": lambda: on(AMULET, rarity=Rarity.NORMAL),
        "locus_magic": lambda: on(AMULET, _roll(LIFE_1), rarity=Rarity.MAGIC),
        "locus_boots_one": lambda: on(BOOTS, *junk, implicits=(exarch(),)),
        "locus_boots_two": lambda: on(BOOTS, *junk, implicits=(exarch(), eater())),
        "locus_belt_stored": lambda: on(BELT, *junk, implicits=(base_implicit(),)),
        "locus_amulet_stranded": lambda: on(AMULET, *junk, memory_strands=40),
        "locus_amulet_corrupted": lambda: on(AMULET, *junk, corrupted=True),
    }


def _build(name: str):
    return _items()[name]()


for _name in (
    "locus_amulet", "locus_amulet_fractured", "locus_normal", "locus_magic", "locus_boots_one", "locus_boots_two", "locus_belt_stored",
    "locus_amulet_stranded", "locus_amulet_corrupted",
):
    register_extra_item(_name, KINDS, _data, lambda name=_name: _build(name))
