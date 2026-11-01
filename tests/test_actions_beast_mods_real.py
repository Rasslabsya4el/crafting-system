"""The Wild Bristle Matron and the side-swap beasts on the real 3.29.3.3 dump (ticket #147).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with
`CRAFTING_CACHE_DIR`). They skip cleanly when it is not there, with the reason; CI fetches it (ticket #165), so
they run there. The odds of the swaps are worked out here straight from the raw spawn weights of the dump, not
through the pool code under test.
"""

from fractions import Fraction

import pytest

from crafting_system.actions import NotApplicableError, catalog
from crafting_system.actions.beast_mods import BeastSideSwap, WildBristleMatron, wild_bristle_metamods
from crafting_system.data import MissingDataError, load_game_data
from crafting_system.items import ExplicitMod, Item, Rarity, Side, effective_weight

AMULET = "Metadata/Items/Amulets/Amulet1"
LIFE, SHIELD, FIRE, COLD, MANA = "IncreasedLife1", "IncreasedEnergyShield1", "FireResist1", "ColdResist1", "ManaLeechPermyriadSuffix1"
PCBC = "StrMasterItemGenerationCannotChangePrefixes"
SCBC = "DexMasterItemGenerationCannotChangeSuffixes"
NO_ATTACK = "IntMasterItemGenerationCannotRollAttackAffixes"
NO_CASTER = "StrDexMasterItemGenerationCannotRollCasterAffixes"
MULTI = "StrIntMasterItemGenerationCanHaveMultipleCraftedMods"
METAMODS = {PCBC, SCBC, NO_ATTACK, NO_CASTER, MULTI}


@pytest.fixture(scope="module")
def data():
    try:
        return load_game_data()
    except MissingDataError as problem:
        pytest.skip(f"the real game data is not in the cache: {problem}")


def rolled(data, mod_id, **flags):
    mod = data.mods[mod_id]
    return ExplicitMod(mod_id, 1, tuple(min(stat.min, stat.max) for stat in mod.stats), crafted=mod.domain == "crafted", **flags)


def rare(data, *mod_ids, item_level=84, **fields):
    mods = tuple(rolled(data, mod_id) for mod_id in mod_ids)
    return Item.build(data, base_id=AMULET, item_level=item_level, rarity=Rarity.RARE, mods=mods, **fields)


def table(outcomes):
    """`{ids of the finished item: chance}`."""
    return {frozenset(e.mod_id for e in result.mods): chance for chance, result in outcomes.results}


def raw_pool(data, side: Side, level: int, held_families: set[str]):
    """The weight of every amulet mod of `side` with required level up to `level` whose family is free, from the raw dump."""
    tags = data.base_items[AMULET].tags
    weights = {}
    for mod in data.mods.values():
        if mod.domain != "item" or mod.generation_type != side.value or mod.required_level > level:
            continue
        weight = effective_weight(mod, tags)
        if weight > 0 and not held_families & set(mod.families):
            weights[mod.id] = weight
    return weights


def family_of(data, mod_id):
    return set(data.mods[mod_id].families)


# --- the Wild Bristle Matron -----------------------------------------------------------------------------------


def test_the_five_metamods_are_in_the_dump_on_the_sides_the_claim_names(data):
    found = {mod.id: mod.generation_type for mod in wild_bristle_metamods(data)}

    assert found == {PCBC: "suffix", SCBC: "prefix", NO_ATTACK: "suffix", NO_CASTER: "suffix", MULTI: "suffix"}


def test_with_the_suffixes_full_and_a_prefix_open_the_matron_gives_suffixes_cannot_be_changed_with_probability_one(data):
    amulet = rare(data, LIFE, FIRE, COLD, MANA)

    outcomes = WildBristleMatron().outcomes(data, amulet)

    assert outcomes.chance_all([SCBC]) == Fraction(1)
    assert table(outcomes) == {frozenset({LIFE, FIRE, COLD, MANA, SCBC}): Fraction(1)}
    (_, finished) = outcomes.results[0]
    finished.validate(data)
    assert [e.mod_id for e in finished.crafted_mods] == [SCBC]


def test_with_every_slot_open_each_metamod_has_chance_one_fifth_and_the_limit_of_crafted_mods_holds(data):
    amulet = rare(data, LIFE, FIRE)

    shown = table(WildBristleMatron().outcomes(data, amulet))

    assert shown == {frozenset({LIFE, FIRE, metamod}): Fraction(1, 5) for metamod in METAMODS}
    for held in (SCBC, NO_ATTACK):
        with pytest.raises(NotApplicableError, match="the limit"):
            WildBristleMatron().outcomes(data, rare(data, LIFE, held))
    multi = table(WildBristleMatron().outcomes(data, rare(data, LIFE, MULTI)))
    assert multi == {frozenset({LIFE, MULTI, metamod}): Fraction(1, 4) for metamod in METAMODS - {MULTI}}


# --- the side swaps --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("item_level", [40, 84, 100])
def test_the_wolf_draws_a_prefix_by_the_raw_weights_at_beast_level_83_whatever_the_item_level(data, item_level):
    amulet = rare(data, LIFE, FIRE, COLD, item_level=item_level)  # the Life family is held; Fire or Cold goes
    weights = raw_pool(data, Side.PREFIX, 83, family_of(data, LIFE))
    total = sum(weights.values())

    shown = table(BeastSideSwap(Side.PREFIX).outcomes(data, amulet))

    assert len(weights) > 20 and len(shown) == 2 * len(weights)
    for mod_id, weight in weights.items():
        assert shown[frozenset({LIFE, COLD, mod_id})] == weight / total / 2  # Fire was removed
        assert shown[frozenset({LIFE, FIRE, mod_id})] == weight / total / 2  # Cold was removed
    assert sum(shown.values()) == 1


def test_a_prefix_above_the_level_of_the_beast_is_never_added_even_on_an_item_of_level_100(data):
    above = [m for m in raw_pool(data, Side.PREFIX, 100, set()) if data.mods[m].required_level > 83]
    assert above, "the dump has amulet prefixes that need a level above 83"

    shown = table(BeastSideSwap(Side.PREFIX).outcomes(data, rare(data, FIRE, item_level=100)))
    reachable = {mod_id for ids in shown for mod_id in ids}
    assert not reachable & set(above)
    higher = table(BeastSideSwap(Side.PREFIX, 100).outcomes(data, rare(data, FIRE, item_level=84)))
    assert {mod_id for ids in higher for mod_id in ids} >= set(above)  # at beast level 100 on an item of level 84 they are in


def test_the_lynx_draws_a_suffix_by_the_raw_weights_and_removes_a_prefix(data):
    amulet = rare(data, LIFE, SHIELD, FIRE)
    weights = raw_pool(data, Side.SUFFIX, 83, family_of(data, FIRE))
    total = sum(weights.values())

    shown = table(BeastSideSwap(Side.SUFFIX).outcomes(data, amulet))

    assert len(shown) == 2 * len(weights)
    for mod_id, weight in weights.items():
        assert shown[frozenset({SHIELD, FIRE, mod_id})] == weight / total / 2  # Life was removed
        assert shown[frozenset({LIFE, FIRE, mod_id})] == weight / total / 2  # Energy Shield was removed


def test_a_swap_under_a_lock_adds_without_removing_and_keeps_the_locked_side(data):
    amulet = rare(data, SCBC, LIFE, FIRE, COLD)  # Suffixes Cannot Be Changed
    weights = raw_pool(data, Side.PREFIX, 83, family_of(data, LIFE))
    total = sum(weights.values())

    shown = table(BeastSideSwap(Side.PREFIX).outcomes(data, amulet))

    assert shown == {frozenset({SCBC, LIFE, FIRE, COLD, mod_id}): weight / total for mod_id, weight in weights.items()}


def test_cannot_roll_attack_keeps_attack_mods_out_of_the_add_and_a_swap_can_remove_the_metamod(data):
    amulet = rare(data, NO_ATTACK, FIRE)
    tags = {"attack"}
    weights = {
        mod_id: weight
        for mod_id, weight in raw_pool(data, Side.PREFIX, 83, set()).items()
        if not tags & set(data.mods[mod_id].implicit_tags)
    }
    total = sum(weights.values())

    shown = table(BeastSideSwap(Side.PREFIX).outcomes(data, amulet))

    assert len(weights) < len(raw_pool(data, Side.PREFIX, 83, set())) and len(shown) == 2 * len(weights)
    for mod_id, weight in weights.items():
        assert shown[frozenset({FIRE, mod_id})] == weight / total / 2  # the metamod went
        assert shown[frozenset({NO_ATTACK, mod_id})] == weight / total / 2  # Fire went


def test_the_refusals_and_the_offers_on_a_real_amulet(data):
    with pytest.raises(NotApplicableError, match="no suffix that is not fractured"):
        BeastSideSwap(Side.PREFIX).outcomes(data, rare(data, LIFE))
    with pytest.raises(NotApplicableError, match="no open prefix slot"):
        BeastSideSwap(Side.PREFIX).outcomes(data, rare(data, LIFE, SHIELD, "AddedLightningDamage1", FIRE))
    offered = catalog(data, rare(data, LIFE, FIRE))
    assert [a for a in offered if isinstance(a, BeastSideSwap)] == [BeastSideSwap(Side.PREFIX), BeastSideSwap(Side.SUFFIX)]
    assert [a for a in offered if isinstance(a, WildBristleMatron)] == [WildBristleMatron()]
