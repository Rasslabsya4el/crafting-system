"""The veiled orbs' part of the contract suite's fixture (ticket #144): the placeholders and the unveiled pool, and two amulets.

`rare_veiled` holds a veiled placeholder (for Unveil and the Veiled Chaos Orb), `rare_offer` the same with its offer drawn (for Pick).
Unveil and Pick are free (`unveil.is_free_and_in_place`), and the Veiled Chaos Orb may put back the placeholder it erased.
"""

from contract_registry import register_fixture_amulet, register_fixture_mods, register_forced_put_back, register_free_actions
from veiled_support import ARMOUR, MANA, PLACEHOLDER_PREFIX, veiled_mods
from veiled_support import LIFE_1 as VEIL_LIFE

from crafting_system.actions import Pick, Unveil, VeiledChaosOrb
from crafting_system.items import ExplicitMod, Rarity

register_fixture_mods(veiled_mods)  # nothing draws them
register_free_actions(Unveil, Pick)
register_forced_put_back(VeiledChaosOrb)  # the placeholder it erased may be put back: forced, not kept


def _placeholder() -> ExplicitMod:
    from contract_support import CONTRACT_DATA  # late: contract_support loads this module while it builds CONTRACT_DATA

    return ExplicitMod(PLACEHOLDER_PREFIX, 1, tuple(min(stat.min, stat.max) for stat in CONTRACT_DATA.mods[PLACEHOLDER_PREFIX].stats))


def _rare_veiled():
    from abstraction_pool import RESIST_2
    from contract_support import _item, _roll

    return _item(Rarity.RARE, _placeholder(), _roll(RESIST_2))


def _rare_offer():
    from abstraction_pool import RESIST_2
    from contract_support import _item, _roll

    return _item(Rarity.RARE, _placeholder(), _roll(RESIST_2), veil_offer=(ARMOUR, VEIL_LIFE, MANA))


register_fixture_amulet("rare_veiled", _rare_veiled)
register_fixture_amulet("rare_offer", _rare_offer)
