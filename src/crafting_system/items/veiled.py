"""Which mods count as veiled ones, read from the game data alone (tickets #144 and #145, ADR-0026).

Three kinds of mod are a veiled mod for the Veiled Exalted Orb's refusal and for the compressed state:

* a **placeholder** (domain `veiled`): `VeiledPrefix` and `VeiledSuffix` are the generic ones the orbs put on an item; the
  signature placeholders of the masters (`HakuVeiledPrefix` ...) share their family and are out of v1;
* a mod **unveiled from the pool** (domain `unveiled`);
* the **craftable version** of an unveiled mod: a crafted mod of Jun's bench (id prefix `JunMaster`) with the side and the stat
  ids of an unveiled mod (928 of 994 in 3.29.3.3, research VEI-20). A crafted mod of another master with the same stats is not
  one (Einhar's trap and mine speed, spell block).

`abstraction` and `actions` both read the answer here, so a state can keep a veiled mod apart from an ordinary mod of the same
family and the orbs refuse by the same test.
"""

from collections.abc import Mapping

from crafting_system.data import GameData, Mod

from .model import CRAFTED_DOMAIN, UNVEILED_DOMAIN, VEILED_DOMAIN

JUN_BENCH = "JunMaster"  # the id prefix of the crafted mods of Jun, whose bench makes the craftable versions of the veiled mods
GENERIC_PLACEHOLDERS: Mapping[str, str] = {"prefix": "VeiledPrefix", "suffix": "VeiledSuffix"}  # side -> the placeholder the orbs put on an item

_SIGNATURE_LIMIT = 8
_SIGNATURES: dict[int, tuple[GameData, frozenset[tuple[str, frozenset[str]]]]] = {}  # id(data) -> (data, signatures); the entry keeps `data` alive, so its id is not reused


def craftable_signatures(data: GameData) -> frozenset[tuple[str, frozenset[str]]]:
    """`(side, stat ids)` of every mod of the unveiled domain: a crafted mod of Jun with the same is its craftable version."""
    found = _SIGNATURES.get(id(data))
    if found is not None and found[0] is data:
        return found[1]
    signatures = frozenset(
        (mod.generation_type, frozenset(stat.id for stat in mod.stats))
        for mod in data.mods.values()
        if mod.domain == UNVEILED_DOMAIN and mod.stats
    )
    if len(_SIGNATURES) >= _SIGNATURE_LIMIT:
        _SIGNATURES.clear()
    _SIGNATURES[id(data)] = (data, signatures)
    return signatures


def is_craftable_version(data: GameData, mod: Mod) -> bool:
    """Whether `mod` is a crafted mod of Jun's bench that is the craftable version of an unveiled mod."""
    return (
        mod.domain == CRAFTED_DOMAIN
        and bool(mod.stats)
        and mod.id.startswith(JUN_BENCH)
        and (mod.generation_type, frozenset(stat.id for stat in mod.stats)) in craftable_signatures(data)
    )


def is_veiled_mod(data: GameData, mod: Mod) -> bool:
    """Whether `mod` is a placeholder, a mod unveiled from the pool, or the craftable version of one."""
    return mod.domain in (VEILED_DOMAIN, UNVEILED_DOMAIN) or is_craftable_version(data, mod)
