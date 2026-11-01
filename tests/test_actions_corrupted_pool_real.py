"""The corrupted implicit pools on the real 3.29.3.3 export (ticket #256, ADR-0037).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with `CRAFTING_CACHE_DIR`). They skip cleanly
when it is not there; CI fetches it (ticket #165).

* The pins are the counts and total weights of the research (#92, section 4) for an item level of 86 or more, written out here: the
  mods, the families and W of every class of its table, for every base of the class.
* A ring of item level 80 loses the three Added-damage tiers of level 81 to 83: 36 mods, W = 31,100.
* Ring, amulet and belt equal Craft of Exile's data mod by mod (`fixtures/coe/corrupted_pools.json`, made from the site's data by
  `fixtures/coe/make_corrupted_pools.py`): at every item level the same tiers with the same weights and value ranges, where Craft of
  Exile keeps a corrupted tier when its `ilvl` is at most the item level.
"""

import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import NotApplicableError, OutOfScopeError, corrupted_implicit_pool

COE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "coe" / "corrupted_pools.json"
HIGH = 100  # above the highest required level of any corrupted mod (85)

# item class -> (mods, families, W) at an item level of 86 or more
CLASS_PINS = {
    "Ring": (39, 22, 31850),
    "Amulet": (30, 28, 28500),
    "Belt": (19, 16, 18500),
    "Body Armour": (21, 21, 20500),
    "Boots": (25, 22, 21500),
    "Gloves": (28, 26, 27500),
    "Helmet": (29, 29, 27750),
    "Shield": (27, 26, 26500),
    "Quiver": (25, 17, 19850),
    "Bow": (27, 18, 21900),
    "Claw": (16, 10, 13750),
    "Dagger": (20, 12, 17000),
    "Rune Dagger": (27, 16, 20250),
    "Wand": (24, 14, 17250),
    "Sceptre": (20, 12, 14750),
    "Staff": (28, 22, 24250),
    "One Hand Axe": (12, 9, 11250),
    "One Hand Mace": (11, 8, 10250),
    "One Hand Sword": (12, 9, 11250),
    "Thrusting One Hand Sword": (9, 9, 9000),
    "Two Hand Axe": (18, 15, 17250),
    "Two Hand Mace": (15, 12, 14250),
    "Two Hand Sword": (15, 12, 13750),
    "FishingRod": (5, 5, 5000),
}
WARSTAFF_PINS = {(24, 15, 21000): 9, (28, 22, 24250): 3}  # nine ordinary Warstaves, three experimental rods with the Staff tags
JEWEL_PIN = (21, 21, 21000)
ORDINARY_JEWELS = (
    "Metadata/Items/Jewels/JewelStr",
    "Metadata/Items/Jewels/JewelDex",
    "Metadata/Items/Jewels/JewelInt",
    "Metadata/Items/Jewels/JewelPrismatic",
)
# classes whose bases hold corrupted mods of another domain (maps, relics, grafts) or none that matches: no pool
NO_POOL_CLASSES = (
    "Map",
    "MapKey",
    "MiscMapItem",
    "ExpeditionLogbook",
    "Relic",
    "SanctumSpecialRelic",
    "RemovedItem",
    "HiddenItem",
    "LifeFlask",
    "Active Skill Gem",
    "StackableCurrency",
)
ABYSS_JEWELS = (
    "Metadata/Items/Jewels/JewelAbyssMelee",
    "Metadata/Items/Jewels/JewelAbyssRanged",
    "Metadata/Items/Jewels/JewelAbyssCaster",
    "Metadata/Items/Jewels/JewelAbyssSummoner",
)
RING = "Metadata/Items/Rings/Ring1"
ALL_RESISTANCES = "V2AllResistancesCorrupted"
# the Added-damage tiers a ring of item level 80 cannot get, with the level each needs
HIGH_ADDED_DAMAGE = {
    "V2AddedColdDamageCorrupted3": 81,
    "V2AddedFireDamageCorrupted3": 82,
    "V2AddedLightningDamageCorrupted3": 83,
}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def shape(pool):
    """(mods, families, W) of a pool."""
    families = {family for entry in pool.mods for family in entry.mod.families}
    return len(pool.mods), len(families), pool.total_weight


def bases_of(data, item_class):
    return [base for base in data.base_items.values() if base.item_class == item_class and base.domain == "item"]


@pytest.mark.parametrize("item_class, pin", sorted(CLASS_PINS.items()))
def test_every_base_of_a_class_has_the_pinned_pool_at_a_high_item_level(data, item_class, pin):
    bases = bases_of(data, item_class)

    assert bases
    assert {shape(corrupted_implicit_pool(data, base.id, HIGH)) for base in bases} == {pin}


def test_a_warstaff_has_one_of_two_pools_and_the_rods_have_the_staff_one(data):
    shapes = Counter(shape(corrupted_implicit_pool(data, base.id, HIGH)) for base in bases_of(data, "Warstaff"))

    assert dict(shapes) == WARSTAFF_PINS
    assert (28, 22, 24250) == CLASS_PINS["Staff"]


def test_ordinary_jewels_and_abyss_jewels_have_21_mods_of_weight_1000_each(data):
    for base_id in (*ORDINARY_JEWELS, *ABYSS_JEWELS):
        pool = corrupted_implicit_pool(data, base_id, HIGH)

        assert shape(pool) == JEWEL_PIN
        assert {entry.weight for entry in pool.mods} == {1000}


def test_the_jewel_pools_are_the_domain_of_their_class(data):
    for base_id in ORDINARY_JEWELS:
        assert {entry.mod.domain for entry in corrupted_implicit_pool(data, base_id, HIGH).mods} == {"misc"}
    for base_id in ABYSS_JEWELS:
        assert {entry.mod.domain for entry in corrupted_implicit_pool(data, base_id, HIGH).mods} == {"abyss_jewel"}


def test_four_mods_of_each_jewel_pool_need_item_level_33_40_40_or_60(data):
    for base_id in (ORDINARY_JEWELS[0], ABYSS_JEWELS[0]):
        pool = corrupted_implicit_pool(data, base_id, HIGH)

        assert sorted(entry.mod.required_level for entry in pool.mods if entry.mod.required_level > 1) == [33, 40, 40, 60]
        assert shape(corrupted_implicit_pool(data, base_id, 59)) == (20, 20, 20000)
        assert shape(corrupted_implicit_pool(data, base_id, 32)) == (17, 17, 17000)


def test_the_abyss_conglomerate_jewel_has_the_abyss_pool(data):
    pool = corrupted_implicit_pool(data, "Metadata/Items/Jewels/JewelAbyssConglomerate", HIGH)

    assert shape(pool) == JEWEL_PIN
    assert {entry.mod.domain for entry in pool.mods} == {"abyss_jewel"}


def test_cluster_and_timeless_jewels_of_the_real_data_are_refused(data):
    refused = [
        base.id
        for base in data.base_items.values()
        if base.item_class == "Jewel" and (base.name.endswith("Cluster Jewel") or base.name == "Timeless Jewel")
    ]

    assert len(refused) == 4  # Small, Medium and Large Cluster Jewel, and the Timeless Jewel
    for base_id in refused:
        with pytest.raises(OutOfScopeError, match="not checked"):
            corrupted_implicit_pool(data, base_id, HIGH)


@pytest.mark.parametrize("item_class", NO_POOL_CLASSES)
def test_a_class_with_no_pool_is_refused_for_every_base(data, item_class):
    bases = [base for base in data.base_items.values() if base.item_class == item_class]

    assert bases
    for base in bases:
        with pytest.raises(NotApplicableError, match="no corrupted implicit pool"):
            corrupted_implicit_pool(data, base.id, HIGH)


def test_a_ring_of_item_level_80_has_w_31100(data):
    pool = corrupted_implicit_pool(data, RING, 80)
    whole = corrupted_implicit_pool(data, RING, 83)

    assert pool.total_weight == 31100
    assert len(pool.mods) == 36
    assert whole.mod_ids() - pool.mod_ids() == set(HIGH_ADDED_DAMAGE)
    assert {data.mods[mod_id].required_level for mod_id in HIGH_ADDED_DAMAGE} == set(HIGH_ADDED_DAMAGE.values())


@pytest.mark.parametrize("item_level, weight", [(80, 31100), (81, 31350), (82, 31600), (83, 31850), (86, 31850), (HIGH, 31850)])
def test_a_ring_gains_a_250_weight_tier_at_level_81_82_and_83(data, item_level, weight):
    assert corrupted_implicit_pool(data, RING, item_level).total_weight == weight


def test_the_all_resistances_implicit_is_one_in_31_85_of_a_ring_draw(data):
    pool = corrupted_implicit_pool(data, RING, 83)

    assert pool.weight_of(ALL_RESISTANCES) == 1000
    assert pool.chance(ALL_RESISTANCES) == Fraction(1000, 31850)
    assert pool.chance(ALL_RESISTANCES) / 4 == Fraction(1000, 127400)  # a quarter of the Vaal Orbs draw an implicit


# --- Craft of Exile, mod by mod ------------------------------------------------------------------------------


def coe_rows():
    return json.loads(COE_FIXTURE.read_text(encoding="utf-8"))["classes"]


def key(level, weight, ranges):
    """A tier as both sources can say it: its level, its weight and its value ranges that are more than one value.

    Craft of Exile writes a stat that never varies as a bare number, an empty list or a one-value range, repoe as `[n, n]`;
    the varying ranges are what tells two tiers with the same level and weight apart.
    """
    varying = [tuple(span) for span in ranges if isinstance(span, list) and span[0] != span[1]]
    return level, weight, tuple(sorted(varying))


def coe_pool(item_class, item_level):
    return Counter(key(row["ilvl"], row["weight"], row["values"]) for row in coe_rows()[item_class] if row["ilvl"] <= item_level)


def our_pool(data, base_id, item_level):
    pool = corrupted_implicit_pool(data, base_id, item_level)
    return Counter(
        key(entry.mod.required_level, entry.weight, [[stat.min, stat.max] for stat in entry.mod.stats]) for entry in pool.mods
    )


@pytest.mark.parametrize("item_class", ["Ring", "Amulet", "Belt"])
@pytest.mark.parametrize("item_level", [1, 33, 40, 60, 75, 80, 82, 83, 86, 100])
def test_ring_amulet_and_belt_equal_craft_of_exile_mod_by_mod(data, item_class, item_level):
    ours = our_pool(data, bases_of(data, item_class)[0].id, item_level)

    assert ours == coe_pool(item_class, item_level)
    assert sum(ours.values()) > 0


@pytest.mark.parametrize("item_class", ["Ring", "Amulet", "Belt"])
@pytest.mark.parametrize("item_level", [40, 80, 100])
def test_the_tiers_of_every_family_craft_of_exile_names_as_ours_are_the_same(data, item_class, item_level):
    """Where a Craft of Exile group has the name of one of our families, its tiers are that family's tiers.

    The two sources do not cut the families alike (Craft of Exile lists each aura of the Mana Reservation Efficiency family as a modifier,
    some modifiers have no group), so the names are compared where they agree: a tier in the wrong family would show here.
    """
    pool = corrupted_implicit_pool(data, bases_of(data, item_class)[0].id, item_level)
    ours: dict[str, Counter] = {}
    for entry in pool.mods:
        tier = key(entry.mod.required_level, entry.weight, [[stat.min, stat.max] for stat in entry.mod.stats])
        ours.setdefault(entry.mod.families[0], Counter())[tier] += 1
    theirs: dict[str, Counter] = {}
    for row in coe_rows()[item_class]:
        if row["group"] is not None and row["ilvl"] <= item_level:
            theirs.setdefault(row["group"], Counter())[key(row["ilvl"], row["weight"], row["values"])] += 1

    shared = ours.keys() & theirs.keys()
    assert len(shared) >= 5
    for family in shared:
        assert ours[family] == theirs[family], family


@pytest.mark.parametrize("item_class", ["Ring", "Amulet", "Belt"])
def test_the_craft_of_exile_fixture_has_the_pinned_counts_and_weights(item_class):
    rows = coe_rows()[item_class]
    mods, _, weight = CLASS_PINS[item_class]

    assert (len(rows), sum(row["weight"] for row in rows)) == (mods, weight)
