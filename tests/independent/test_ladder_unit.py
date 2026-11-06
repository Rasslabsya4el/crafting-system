"""The shared ladder on a hand-made export, one test per rule (ticket #419). No real dump is read here.

The made-up game: a ring and a jewel, a four-tier `Life` ladder of the ring (tier 1 the highest required level), the same type
in the jewel's own domain, an item-domain mod that carries a `default` weight (so it can "spawn" on a jewel by its tags), a Royale
copy, an essence-only mod, a crafted mod, a unique mod and a Hunter-only mod.
"""

import re

import pytest
from independent import ladder as shared

RING = "Metadata/Items/Rings/Ring1"
JEWEL = "Metadata/Items/Jewels/JewelInt"


def mod(type_, level, spawn, *, side="prefix", domain="item", essence=False):
    return {
        "type": type_,
        "generation_type": side,
        "domain": domain,
        "required_level": level,
        "is_essence_only": essence,
        "spawn_weights": [{"tag": tag, "weight": weight} for tag, weight in spawn],
    }


MODS = {
    "Life1": mod("Life", 1, [("ring", 1000), ("default", 0)]),
    "Life2": mod("Life", 30, [("ring", 1000), ("default", 0)]),
    "Life3": mod("Life", 60, [("ring", 1000), ("default", 0)]),
    "Life4": mod("Life", 80, [("ring", 1000), ("default", 0)]),
    "LifeZero": mod("Life", 90, [("ring", 0), ("default", 1000)]),  # the first matching entry decides: weight 0 on a ring
    "LifeRoyale": mod("Life", 70, [("ring", 1000), ("default", 0)]),
    "LifeEssence": mod("Life", 85, [("ring", 1000), ("default", 0)], essence=True),
    "LifeCrafted": mod("Life", 50, [("ring", 1000), ("default", 0)], domain="crafted"),
    "LifeUnique": mod("Life", 95, [("ring", 1000), ("default", 0)], side="unique"),
    "LifeSuffixTwin": mod("Life", 99, [("ring", 1000), ("default", 0)], side="suffix"),
    "LifeHunter": mod("Life", 83, [("ring_basilisk", 1000), ("ring", 0), ("default", 0)]),
    "TieA": mod("Tie", 10, [("ring", 1), ("default", 0)]),
    "TieB": mod("Tie", 10, [("ring", 1), ("default", 0)]),
    "TieLow": mod("Tie", 5, [("ring", 1), ("default", 0)]),
    "ItemLife": mod("ItemLife", 1, [("ring", 0), ("default", 1000)]),  # an item-domain mod that a jewel's tags would let spawn
    "ItemLife2": mod("ItemLife", 20, [("ring", 0), ("default", 1000)]),
    "JewelLife1": mod("JewelLife", 1, [("jewel", 1000), ("default", 0)], domain="misc"),
    "JewelLife2": mod("JewelLife", 20, [("jewel", 1000), ("default", 0)], domain="misc"),
}
RING_TAGS = ["ring", "default"]
JEWEL_TAGS = ["jewel", "default"]


def tiers(tags, domain, mod_id, mods=MODS):
    return shared.ladder_of(mods, shared.item_tags(tags), domain, mod_id)


def test_tier_1_is_the_highest_required_level():
    assert tiers(RING_TAGS, "item", "Life2") == {"Life4": 1, "Life3": 2, "Life2": 3, "Life1": 4}  # levels 80, 60, 30, 1


def test_mods_that_tie_on_the_required_level_share_a_tier_and_the_next_one_skips():
    assert tiers(RING_TAGS, "item", "TieLow") == {"TieA": 1, "TieB": 1, "TieLow": 3}


def test_the_first_matching_spawn_entry_decides_the_weight():
    zero_first = MODS["LifeZero"]

    assert shared.spawn_weight(zero_first, {"ring", "default"}) == 0
    assert shared.spawn_weight(zero_first, {"default"}) == 1000
    assert shared.spawn_weight(zero_first, {"amulet"}) == 0  # no entry matches


def test_a_ladder_leaves_out_zero_weight_royale_essence_crafted_and_non_prefix_suffix_mods():
    ladder = shared.natural_ladders(MODS, shared.item_tags(RING_TAGS), "item")[("Life", "prefix")]

    assert set(ladder) == {"Life1", "Life2", "Life3", "Life4"}
    assert "LifeZero" not in ladder and "LifeRoyale" not in ladder
    assert "LifeEssence" not in ladder and "LifeCrafted" not in ladder and "LifeUnique" not in ladder
    assert "LifeSuffixTwin" not in ladder  # the same type as a suffix is another ladder
    assert ("Life", "suffix") in shared.natural_ladders(MODS, shared.item_tags(RING_TAGS), "item")


def test_a_royale_copy_that_can_spawn_does_not_shift_the_tiers():
    mods = {**MODS, "Life1Royale": mod("Life", 99, [("ring", 1000), ("default", 0)])}

    assert shared.spawn_weight(mods["Life1Royale"], {"ring"}) > 0
    assert shared.ladder_of(mods, {"ring"}, "item", "Life1") == shared.ladder_of(MODS, {"ring"}, "item", "Life1")
    assert shared.is_royale("Life1Royale") and shared.is_royale("Metadata/Items/Belts/BeltRoyale1") and not shared.is_royale("Life1")


def test_the_domain_of_the_base_decides_not_the_domain_of_the_mod_asked_about():
    on_a_jewel = shared.natural_ladders(MODS, shared.item_tags(JEWEL_TAGS), "misc")

    assert set(on_a_jewel[("JewelLife", "prefix")]) == {"JewelLife1", "JewelLife2"}
    assert ("ItemLife", "prefix") not in on_a_jewel  # an item-domain mod with a default weight is no jewel mod
    assert tiers(JEWEL_TAGS, "misc", "ItemLife") == {}
    assert tiers(JEWEL_TAGS, "item", "ItemLife") == {"ItemLife2": 1, "ItemLife": 2}  # read as a gear base it would be a ladder


def test_an_influence_adds_its_tag_suffix_to_every_base_tag():
    assert shared.item_tags(["ring", "default"], ["hunter"], "Ring") == {"ring", "default", "ring_basilisk", "default_basilisk"}
    assert shared.item_tags(["ring"], ["hunter", "shaper"], "Ring") == {"ring", "ring_basilisk", "ring_shaper"}
    assert shared.item_tags(["ring"]) == {"ring"}
    assert shared.item_tags(["jewel", "default"]) == {"jewel", "default"}  # no influence: the class is not asked


@pytest.mark.parametrize("item_class", ["Jewel", "AbyssJewel", "LifeFlask", "Tincture", "Fishing Rod"])
def test_an_influence_on_a_class_that_takes_none_is_refused_as_the_planner_refuses_it(item_class):
    with pytest.raises(shared.InfluenceError, match=f"class '{item_class}' takes no influence"):
        shared.item_tags(["jewel", "default"], ["hunter"], item_class)
    assert shared.item_tags(["jewel", "default"], [], item_class) == {"jewel", "default"}


def test_an_unknown_influence_is_a_clear_error_that_lists_the_six():
    with pytest.raises(shared.InfluenceError, match="no influence named 'no-such-influence'; the influences are .*warlord"):
        shared.item_tags(["ring"], ["no-such-influence"], "Ring")
    with pytest.raises(shared.InfluenceError, match="no influence named 'no-such-influence'"):  # a typo is a typo on any class
        shared.item_tags(["jewel"], ["no-such-influence"], "Jewel")
    assert issubclass(shared.InfluenceError, ValueError)


def test_an_influence_without_the_item_class_is_refused_not_guessed():
    with pytest.raises(shared.InfluenceError, match="needs the item class"):
        shared.item_tags(["ring"], ["hunter"])


def test_the_classes_that_take_an_influence_are_the_24_gear_classes():
    assert len(shared.INFLUENCE_CLASSES) == 24
    assert {"Ring", "Bow", "Thrusting One Hand Sword", "Body Armour"} <= shared.INFLUENCE_CLASSES
    assert not shared.INFLUENCE_CLASSES & {"Jewel", "AbyssJewel", "LifeFlask", "Tincture", "Fishing Rod"}


def test_a_mod_that_only_an_influence_gives_is_on_the_ladder_of_an_influenced_item_only():
    plain = tiers(RING_TAGS, "item", "Life1")
    hunter = shared.ladder_of(MODS, shared.item_tags(RING_TAGS, ["hunter"], "Ring"), "item", "Life1")

    assert "LifeHunter" not in plain
    assert hunter["LifeHunter"] == 1 and hunter["Life4"] == 2  # level 83 is above the level 80 of the best natural tier
    assert set(hunter) - set(plain) == {"LifeHunter"}


def test_the_ladder_does_not_depend_on_the_order_of_the_mods():
    backwards = dict(reversed(list(MODS.items())))

    assert tiers(RING_TAGS, "item", "Life1", backwards) == tiers(RING_TAGS, "item", "Life1")


BASES = {
    "Metadata/Items/Rings/Ring1": {"name": "Ruby Ring", "item_class": "Ring", "tags": ["ring", "default"], "release_state": "released"},
    "Metadata/Items/Rings/Old": {"name": "Ruby Ring", "item_class": "Ring", "tags": ["ring", "default"], "release_state": "removed"},
    "Metadata/Items/Rings/RingRoyale9": {"name": "Ruby Ring", "item_class": "Ring", "tags": ["ring", "default"], "release_state": "released"},
    "Metadata/Items/Rings/Ring2": {"name": "Sapphire Ring", "item_class": "Ring", "tags": ["ring", "default"], "release_state": "released"},
    "Metadata/Items/Belts/Belt3": {"name": "Cloth Belt", "item_class": "Belt", "tags": ["belt", "default"], "release_state": "released"},
    "Metadata/Items/Belts/BeltRoyale1": {"name": "Cloth Belt", "item_class": "Belt", "tags": ["not_for_sale", "belt"], "release_state": "released"},
    "Metadata/Items/Belts/Belt9": {"name": "Cloth Belt", "item_class": "Belt", "tags": ["not_for_sale", "belt"], "release_state": "released"},
    "Metadata/Items/Boots/Atlas1": {"name": "Pied Boots", "item_class": "Boots", "tags": ["not_for_sale", "boots"], "release_state": "released"},
    "Metadata/Items/Boots/Atlas2": {"name": "Pied Boots", "item_class": "Boots", "tags": ["not_for_sale", "boots"], "release_state": "released"},
    "Metadata/Items/Jewels/JewelInt": {"name": "Cobalt Jewel", "item_class": "Jewel", "tags": ["not_for_sale", "jewel"], "release_state": "released"},
}


def test_a_name_means_the_released_bases_without_royale_and_without_not_for_sale_where_some_are_on_sale():
    assert shared.bases_named(BASES, "Ruby Ring") == ["Metadata/Items/Rings/Ring1"]  # not the removed ring, not the Royale ring
    assert shared.bases_named(BASES, "Cloth Belt") == ["Metadata/Items/Belts/Belt3"]  # the other two are not for sale
    assert shared.bases_named(BASES, "Pied Boots") == ["Metadata/Items/Boots/Atlas1", "Metadata/Items/Boots/Atlas2"]  # all not for sale: all stay
    assert shared.bases_named(BASES, "Cobalt Jewel") == ["Metadata/Items/Jewels/JewelInt"]
    assert shared.bases_named(BASES, "No Such Base") == []


@pytest.mark.parametrize(
    ("entry", "problem"),
    [
        ({"item_class": "Ring", "tags": ["ring"], "release_state": "released"}, "has no 'name'"),
        ({"name": None, "item_class": "Ring", "tags": ["ring"]}, "'name' is NoneType, not text"),
        ({"name": "Odd Ring", "item_class": "Ring", "release_state": "released"}, "has no 'tags'"),
        ({"name": "Odd Ring", "item_class": "Ring", "tags": "ring"}, "'tags' is str, not a list"),
        ("not a mapping", "is str, not a mapping"),
        (None, "is NoneType, not a mapping"),
    ],
)
def test_a_malformed_base_entry_fails_loudly_instead_of_being_skipped(entry, problem):
    broken = {**BASES, "Metadata/Items/Rings/Broken": entry}

    with pytest.raises(shared.MalformedBase, match="'Metadata/Items/Rings/Broken'.*" + re.escape(problem)):
        shared.bases_named(broken, "Sapphire Ring")  # even for a name the broken entry could not be
    with pytest.raises(shared.MalformedBase, match="Metadata/Items/Rings/Broken"):
        shared.base_ids_of(broken, "Sapphire Ring")


def test_a_base_entry_without_an_item_class_fails_loudly_in_a_category_search():
    broken = {**BASES, "Metadata/Items/Rings/Broken": {"name": "Odd Ring", "tags": ["ring"]}}

    with pytest.raises(shared.MalformedBase, match="'Metadata/Items/Rings/Broken' has no 'item_class'"):
        shared.bases_of_category(broken, "accessory.ring")
    assert issubclass(shared.MalformedBase, ValueError)


def test_a_missing_release_state_reads_as_released():
    bases = {"Metadata/Items/Rings/R": {"name": "Plain Ring", "item_class": "Ring", "tags": ["ring"]}}

    assert shared.bases_named(bases, "Plain Ring") == ["Metadata/Items/Rings/R"]
    assert shared.bases_of_category(bases, "accessory.ring") == ["Metadata/Items/Rings/R"]


def test_a_reference_is_an_id_or_a_name_and_an_id_wins():
    assert shared.base_ids_of(BASES, "Metadata/Items/Belts/Belt9") == ["Metadata/Items/Belts/Belt9"]
    assert shared.base_ids_of(BASES, "Cloth Belt") == ["Metadata/Items/Belts/Belt3"]
    assert shared.base_ids_of(BASES, "Nothing") == []


def test_a_category_is_the_released_bases_on_sale_of_its_item_classes():
    assert shared.bases_of_category(BASES, "accessory.ring") == ["Metadata/Items/Rings/Ring1", "Metadata/Items/Rings/Ring2"]
    assert shared.bases_of_category(BASES, "armour.boots") == []  # every boots here is not for sale
    assert shared.bases_of_category(BASES, "no.such") == []
