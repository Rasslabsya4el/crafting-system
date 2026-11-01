"""The corrupted implicit pool on a small made-up export (ticket #256, ADR-0037); the real export is in `test_actions_corrupted_pool_real.py`.

Each rule of the pool is one case here: the first matching spawn tag decides the weight, a weight of 0 keeps a mod
out, the required level gates it (at the level itself the mod is in), the mod's domain must be the base's (an abyss jewel mod
lists only the `default` tag, so tags alone would give every class the abyss jewel implicits), every tier is its own draw,
and the Cluster and Timeless jewels and the classes with no pool are refused with a reason.
"""

from fractions import Fraction

import pytest

from crafting_system.actions import (
    CorruptedImplicitPool,
    NotApplicableError,
    OutOfScopeError,
    corrupted_implicit_pool,
)
from crafting_system.data import normalize_game_data
from crafting_system.items import UnknownBaseError

RING = "Metadata/Items/Rings/Ring1"
BELT = "Metadata/Items/Belts/Belt1"
JEWEL = "Metadata/Items/Jewels/JewelStr"
ABYSS = "Metadata/Items/Jewels/JewelAbyssMelee"
CLUSTER = "Metadata/Items/Jewels/JewelPassiveTreeExpansionLarge"
TIMELESS = "Metadata/Items/Jewels/JewelTimeless"
FLASK = "Metadata/Items/Flasks/FlaskLife1"
MAP = "Metadata/Items/Maps/MapWorlds1"


def mod(mod_id, *, weights, level=1, domain="item", generation_type="corrupted", group=None):
    return {
        "name": mod_id,
        "text": None,
        "type": group or mod_id,
        "groups": [group or mod_id],
        "domain": domain,
        "generation_type": generation_type,
        "required_level": level,
        "spawn_weights": [{"tag": tag, "weight": weight} for tag, weight in weights],
        "generation_weights": [],
        "adds_tags": [],
        "implicit_tags": [],
        "stats": [{"id": "stat", "min": 1, "max": 2}],
        "is_essence_only": False,
    }


def base(name, item_class, domain, tags):
    return {
        "name": name,
        "item_class": item_class,
        "domain": domain,
        "drop_level": 1,
        "tags": tags,
        "implicits": [],
        "release_state": "released",
    }


RAW_MODS = {
    # ring and belt share Resistance (tag ring first, then belt); the second weight is never read on a ring
    "Resist": mod("Resist", weights=[("ring", 1000), ("belt", 500), ("default", 0)], group="AllResist"),
    "BeltFirst": mod("BeltFirst", weights=[("belt", 250), ("ring", 1000), ("default", 0)]),
    "Late": mod("Late", weights=[("ring", 200), ("default", 0)], level=81),
    "Tier1": mod("Tier1", weights=[("ring", 1000), ("default", 0)], group="Added"),
    "Tier2": mod("Tier2", weights=[("ring", 1000), ("default", 0)], level=40, group="Added"),
    "Zero": mod("Zero", weights=[("ring", 0), ("default", 0)]),
    "NotCorrupted": mod("NotCorrupted", weights=[("ring", 1000), ("default", 0)], generation_type="prefix"),
    "AbyssOnly": mod("AbyssOnly", weights=[("default", 1000)], domain="abyss_jewel"),
    "MapOnly": mod("MapOnly", weights=[("default", 75)], domain="area"),
    "JewelOnly": mod("JewelOnly", weights=[("jewel", 1000), ("default", 0)], domain="misc", level=33),
}
RAW_BASES = {
    RING: base("Iron Ring", "Ring", "item", ["ring", "jewellery", "default"]),
    BELT: base("Leather Belt", "Belt", "item", ["belt", "default"]),
    JEWEL: base("Crimson Jewel", "Jewel", "misc", ["jewel", "default"]),
    ABYSS: base("Searching Eye Jewel", "AbyssJewel", "abyss_jewel", ["abyss_jewel", "default"]),
    CLUSTER: base("Large Cluster Jewel", "Jewel", "affliction_jewel", ["jewel", "expansion_jewel_large", "default"]),
    TIMELESS: base("Timeless Jewel", "Jewel", "misc", ["jewel", "default"]),
    FLASK: base("Small Life Flask", "LifeFlask", "flask", ["flask", "default"]),
    MAP: base("Tropical Island Map", "Map", "area", ["map", "default"]),
}


@pytest.fixture(scope="module")
def data():
    return normalize_game_data(RAW_MODS, RAW_BASES, {}, {}, [], version="0.0-test")


def ids(pool):
    return [entry.mod.id for entry in pool.mods]


def test_a_ring_pool_holds_the_corrupted_mods_with_a_positive_first_matching_weight_in_data_order(data):
    pool = corrupted_implicit_pool(data, RING, 100)

    assert isinstance(pool, CorruptedImplicitPool)
    assert ids(pool) == ["Resist", "BeltFirst", "Late", "Tier1", "Tier2"]
    assert [entry.weight for entry in pool.mods] == [1000, 1000, 200, 1000, 1000]
    assert pool.total_weight == 4200
    assert (pool.base_id, pool.item_class, pool.item_level) == (RING, "Ring", 100)


def test_the_first_matching_tag_decides_the_weight_not_the_best_one(data):
    ring, belt = corrupted_implicit_pool(data, RING, 100), corrupted_implicit_pool(data, BELT, 100)

    assert ring.weight_of("Resist") == 1000 and belt.weight_of("Resist") == 500
    assert ring.weight_of("BeltFirst") == 1000 and belt.weight_of("BeltFirst") == 250  # belt is listed first


def test_a_mod_is_in_the_pool_from_its_required_level_on(data):
    assert "Late" not in corrupted_implicit_pool(data, RING, 80).mod_ids()
    assert "Late" in corrupted_implicit_pool(data, RING, 81).mod_ids()
    assert corrupted_implicit_pool(data, RING, 80).total_weight == 4000
    assert corrupted_implicit_pool(data, RING, 39).mod_ids() == {"Resist", "BeltFirst", "Tier1"}
    assert corrupted_implicit_pool(data, RING, 40).mod_ids() == {"Resist", "BeltFirst", "Tier1", "Tier2"}


def test_every_tier_of_a_family_is_its_own_draw(data):
    pool = corrupted_implicit_pool(data, RING, 100)

    assert {entry.mod.families for entry in pool.mods if entry.mod.id.startswith("Tier")} == {("Added",)}
    assert pool.chance("Tier1") == Fraction(1000, 4200) == pool.chance("Tier2")


def test_a_mod_with_weight_zero_or_another_generation_type_is_not_a_candidate(data):
    assert not {"Zero", "NotCorrupted"} & corrupted_implicit_pool(data, RING, 100).mod_ids()


def test_the_mods_of_another_domain_do_not_enter_a_pool_even_when_the_tag_default_matches(data):
    # AbyssOnly lists only `default`, which the ring has; JewelOnly is a misc mod
    assert not {"AbyssOnly", "JewelOnly"} & corrupted_implicit_pool(data, RING, 100).mod_ids()
    assert ids(corrupted_implicit_pool(data, ABYSS, 100)) == ["AbyssOnly"]
    assert ids(corrupted_implicit_pool(data, JEWEL, 32)) == []
    assert ids(corrupted_implicit_pool(data, JEWEL, 33)) == ["JewelOnly"]


def test_the_chance_of_a_mod_is_its_weight_over_the_total_and_zero_outside_the_pool(data):
    pool = corrupted_implicit_pool(data, RING, 100)

    assert pool.chance("Late") == Fraction(200, 4200) == Fraction(1, 21)
    assert pool.chance("Zero") == 0
    assert sum(pool.chance(mod_id) for mod_id in pool.mod_ids()) == 1


def test_an_empty_pool_at_a_low_item_level_has_no_draw(data):
    pool = corrupted_implicit_pool(data, JEWEL, 1)

    assert pool.mods == () and pool.total_weight == 0
    with pytest.raises(ValueError, match="empty"):
        pool.chance("JewelOnly")


@pytest.mark.parametrize("base_id, kind", [(CLUSTER, "Cluster Jewel"), (TIMELESS, "Timeless Jewel")])
def test_cluster_and_timeless_jewels_are_refused_with_a_reason(data, base_id, kind):
    with pytest.raises(OutOfScopeError, match=f"is a {kind}.*not checked"):
        corrupted_implicit_pool(data, base_id, 100)


def test_a_class_with_no_pool_is_refused_with_the_class_named(data):
    with pytest.raises(NotApplicableError, match=r"Small Life Flask \(LifeFlask\).*no corrupted implicit pool"):
        corrupted_implicit_pool(data, FLASK, 100)


def test_a_base_outside_equipment_and_jewels_is_refused_although_a_corrupted_mod_matches_its_default_tag(data):
    # the map's own corrupted mod (domain area) lists the tag `default`; maps, relics and grafts hold such mods, no Vaal Orb draws them
    with pytest.raises(NotApplicableError, match=r"Tropical Island Map \(Map\).*no corrupted implicit pool"):
        corrupted_implicit_pool(data, MAP, 100)


@pytest.mark.parametrize("level", [0, -3, 80.0, True, "80", None])
def test_an_item_level_that_is_not_an_integer_of_at_least_1_is_refused(data, level):
    with pytest.raises(ValueError, match="item level"):
        corrupted_implicit_pool(data, RING, level)


def test_an_unknown_base_is_refused(data):
    with pytest.raises(UnknownBaseError, match="Nope"):
        corrupted_implicit_pool(data, "Metadata/Items/Rings/Nope", 100)


def test_the_pool_is_cached_per_game_data_and_a_second_data_object_gets_its_own(data):
    other = normalize_game_data(RAW_MODS, RAW_BASES, {}, {}, [], version="0.0-test")

    assert corrupted_implicit_pool(data, RING, 100) is corrupted_implicit_pool(data, RING, 100)
    assert corrupted_implicit_pool(other, RING, 100) == corrupted_implicit_pool(data, RING, 100)
    assert corrupted_implicit_pool(other, RING, 100) is not corrupted_implicit_pool(data, RING, 100)
