"""The imprint family's part of the contract suite's fixture (ticket #219): items that hold imprints, and a rare Talisman of the Arachnid.

* `magic_imprinted`: a magic amulet whose imprint is another magic state, so a Restore applies;
* `rare_imprinted`: a rare amulet that holds the imprint of the magic item it was (the loop of R15);
* a rare Talisman on a base of its own (`register_extra_item`), asked about the two imprint kinds only, so the Fenumal Plagued Arachnid applies.

A Restore consumes nothing, so the family registers it as a free action.
"""

from contract_registry import register_extra_item, register_fixture_amulet, register_free_actions

from crafting_system.actions import Restore

register_free_actions(Restore)


def _magic_imprinted():
    from abstraction_pool import LIFE_1, RESIST_2
    from contract_support import _item, _roll  # late: contract_support loads this module while it builds CONTRACT_DATA

    from crafting_system.items import Rarity

    return _item(Rarity.MAGIC, _roll(LIFE_1), imprints=(_item(Rarity.MAGIC, _roll(RESIST_2)),))


def _rare_imprinted():
    from abstraction_pool import LIFE_1, RESIST_2
    from contract_support import _item, _roll

    from crafting_system.items import Rarity

    return _item(Rarity.RARE, _roll(RESIST_2), _roll(LIFE_1), imprints=(_item(Rarity.MAGIC, _roll(LIFE_1)),))


register_fixture_amulet("magic_imprinted", _magic_imprinted)
register_fixture_amulet("rare_imprinted", _rare_imprinted)


def _talisman_data():
    from beasts_support import contract_beast_data

    return contract_beast_data()


def _rare_talisman():
    from abstraction_pool import LIFE_1, RESIST_2
    from beasts_support import TALISMAN
    from contract_support import LEVEL, _roll

    from crafting_system.items import Item, Rarity

    data = _talisman_data()
    mods = (_roll(RESIST_2), _roll(LIFE_1))
    snapshot = Item.build(data, base_id=TALISMAN, item_level=LEVEL, rarity=Rarity.RARE, mods=(_roll(LIFE_1),))
    return Item.build(data, base_id=TALISMAN, item_level=LEVEL, rarity=Rarity.RARE, mods=mods, imprints=(snapshot,))


register_extra_item("rare_talisman_imprinted", ("imprint", "restore"), _talisman_data, _rare_talisman)
