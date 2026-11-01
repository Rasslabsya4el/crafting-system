"""The Awakener's Orb's part of the contract suite's fixture (ticket #213): three influence mods and `rare_awakener`.

`rare_awakener` is a rare amulet of the Shaper holding two Shaper mods (a prefix and a suffix) and a life mod, so an orb with a
Crusader donor keeps either influenced mod. The donors are the two Crusader mods of `awakener_support`: one of a family of its
own, one of the family of the Shaper prefix (a group conflict).
"""

from awakener_support import SHAPER_PREFIX, SHAPER_SUFFIX, awakener_mods
from contract_registry import register_fixture_amulet, register_fixture_mods

from crafting_system.items import Influence, Rarity

register_fixture_mods(awakener_mods)  # nothing draws them on an item of no influence


def _rare_awakener():
    from abstraction_pool import LIFE_1
    from contract_support import _item, _roll  # late: contract_support loads this module while it builds CONTRACT_DATA

    return _item(Rarity.RARE, _roll(SHAPER_PREFIX), _roll(SHAPER_SUFFIX), _roll(LIFE_1), influences=frozenset({Influence.SHAPER}))


register_fixture_amulet("rare_awakener", _rare_awakener)
