"""Building an item: the structural rules that need no game data (ADR-0018: items sits on data and rules)."""

import pytest

from crafting_system.items import (
    ExplicitMod,
    Influence,
    Item,
    ItemError,
    Metamod,
    Rarity,
    Side,
)

BASE = "Metadata/Items/Armours/BodyArmours/BodyInt1"


def make(**fields) -> Item:
    fields.setdefault("base_id", BASE)
    fields.setdefault("item_level", 84)
    fields.setdefault("rarity", Rarity.RARE)
    return Item(**fields)


def mod(mod_id, **fields) -> ExplicitMod:
    fields.setdefault("tier", 1)
    fields.setdefault("values", (1,))
    return ExplicitMod(mod_id, **fields)


def test_the_enums_use_the_repoe_words():
    assert Rarity("magic") is Rarity.MAGIC
    assert Side("prefix") is Side.PREFIX and Side("suffix") is Side.SUFFIX
    assert Influence.SHAPER == "shaper" and len(Influence) == 6
    assert Metamod.PREFIXES_CANNOT_CHANGE == "ItemGenerationCannotChangePrefixes"
    assert len(Metamod) == 5


def test_a_plain_item_has_no_mods_influences_or_corruption():
    item = make()

    assert item.mods == () and item.influences == frozenset() and item.corrupted is False


def test_mods_are_stored_sorted_by_id_whatever_the_input_order():
    a, b = mod("AaaMod"), mod("ZzzMod")

    assert make(mods=(b, a)).mods == (a, b)
    assert make(mods=(b, a)) == make(mods=(a, b))


def test_equal_items_hash_equal():
    a, b = mod("AaaMod"), mod("ZzzMod")

    assert hash(make(mods=(b, a))) == hash(make(mods=(a, b)))
    assert len({make(mods=(b, a)), make(mods=(a, b))}) == 1


@pytest.mark.parametrize("level", [0, 101, -5])
def test_an_item_level_outside_1_to_100_is_rejected(level):
    with pytest.raises(ItemError, match=rf"item level {level}.*1 to 100"):
        make(item_level=level)


@pytest.mark.parametrize("level", [1, 100])
def test_the_edge_item_levels_are_accepted(level):
    assert make(item_level=level).item_level == level


def test_a_tier_below_1_is_rejected():
    with pytest.raises(ItemError, match="AaaMod.*tier 0"):
        make(mods=(mod("AaaMod", tier=0),))


def test_a_mod_cannot_be_both_fractured_and_crafted():
    with pytest.raises(ItemError, match="AaaMod.*fractured and crafted"):
        make(mods=(mod("AaaMod", fractured=True, crafted=True),))


def test_the_same_mod_twice_is_rejected():
    with pytest.raises(ItemError, match="AaaMod.*twice"):
        make(mods=(mod("AaaMod"), mod("AaaMod")))


def test_influences_must_be_a_frozenset_of_influences():
    with pytest.raises(ItemError, match="influences"):
        make(influences={Influence.SHAPER})
    with pytest.raises(ItemError, match="influences"):
        make(influences=frozenset({"shaper"}))


def test_an_error_names_the_base():
    with pytest.raises(ItemError, match="BodyInt1"):
        make(item_level=0)


def test_fractured_and_crafted_mods_are_listed():
    plain, fractured, crafted = mod("A"), mod("B", fractured=True), mod("C", crafted=True)
    item = make(mods=(plain, fractured, crafted))

    assert item.fractured_mods == (fractured,) and item.crafted_mods == (crafted,)


def test_the_item_is_immutable():
    item = make()

    with pytest.raises(AttributeError):
        item.item_level = 5


def test_the_rarity_must_be_a_rarity():
    with pytest.raises(ItemError, match="rarity 'rare' is not a Rarity"):
        make(rarity="rare")


@pytest.mark.parametrize(
    "fields",
    [
        {"item_level": 50.5},
        {"item_level": True},
        {"mods": ("IncreasedLife1",)},
        {"mods": (ExplicitMod("IncreasedLife1", 1.5, (10,)),)},
        {"mods": (ExplicitMod("IncreasedLife1", 1, [10]),)},
        {"mods": (ExplicitMod("IncreasedLife1", 1, (10.5,)),)},
    ],
)
def test_wrongly_typed_fields_are_an_item_error_not_a_stray_type_error(fields):
    with pytest.raises(ItemError):
        make(**fields)
