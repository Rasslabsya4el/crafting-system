"""The Memory Strands part of the contract suite's fixture (ticket #276): five amulets that hold strands.

Every kind of the catalog is asked about them like about the other fixture items (`contract_support.check_action`), and the strand
checks run on them: an action that declared nothing is refused, a declared one cuts only when it says so and its spend is a
distribution of the count after the craft that the sampler follows.

* `rare_shaper_stranded` (70): a Shaper item, for the kinds that need an influence;
* `normal_stranded` (45 strands): a normal item, for the orbs and essences that work on one;
* `magic_stranded` (60): a magic item with a life mod; * `rare_stranded` (100, the largest cut): a rare item with two mods;
* `rare_four_stranded` (3): a rare item with four mods and fewer strands than most ceilings, so a spend can be larger than the count.
"""

from contract_registry import register_fixture_amulet

from crafting_system.items import Rarity


def _stranded(rarity: Rarity, strands: int, *mod_ids: str):
    from contract_support import _item, _roll  # late: contract_support loads this module while it builds CONTRACT_DATA

    return _item(rarity, *(_roll(mod_id) for mod_id in mod_ids), memory_strands=strands)


def _normal():
    return _stranded(Rarity.NORMAL, 45)


def _magic():
    from abstraction_pool import LIFE_1

    return _stranded(Rarity.MAGIC, 60, LIFE_1)


def _rare():
    from abstraction_pool import LIFE_1, RESIST_2

    return _stranded(Rarity.RARE, 100, RESIST_2, LIFE_1)


def _rare_four():
    from abstraction_pool import DAMAGE_1, FIRE_GEM, LIFE_1, RESIST_2

    return _stranded(Rarity.RARE, 3, RESIST_2, LIFE_1, DAMAGE_1, FIRE_GEM)


def _rare_shaper():
    from abstraction_pool import LIFE_1, RESIST_2
    from contract_support import _item, _roll

    from crafting_system.items import Influence

    return _item(Rarity.RARE, _roll(RESIST_2), _roll(LIFE_1), influences=frozenset({Influence.SHAPER}), memory_strands=70)


register_fixture_amulet("rare_shaper_stranded", _rare_shaper)
register_fixture_amulet("normal_stranded", _normal)
register_fixture_amulet("magic_stranded", _magic)
register_fixture_amulet("rare_stranded", _rare)
register_fixture_amulet("rare_four_stranded", _rare_four)
