"""The Foulborn part of the contract suite's fixture (ticket #279): a stranded rare item whose open suffix side holds a three-tier table.

A Foulborn orb cuts at 0 strands too (`D = 175`), so the suite's check that a cutting kind draws other mods on a stranded item than at 0
strands needs a table that the 0-strand Foulborn cut and the cut of a larger count keep apart: three tiers keep two at `D = 175` and one at
`D = 550` and above. The Lightning Resistance suffix of the fixture has three tiers and the other stranded rare items hold it, so this one
does not.
"""

from contract_registry import register_fixture_amulet

from crafting_system.items import Rarity


def _rare_open_suffixes():
    from abstraction_pool import DAMAGE_1, LIFE_1
    from contract_support import _item, _roll

    return _item(Rarity.RARE, _roll(LIFE_1), _roll(DAMAGE_1), memory_strands=40)


register_fixture_amulet("rare_open_suffixes_stranded", _rare_open_suffixes)
