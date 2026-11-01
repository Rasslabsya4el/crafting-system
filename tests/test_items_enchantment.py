"""`Item.enchantment` (ticket #236, ADR-0050): the field, its validation against the pools, and that an item without it is unchanged."""

import dataclasses

import pytest
from enchant_support import (
    AMULET,
    ARMOUR_EXTRA_SLOT,
    ARMOUR_WHITE_SOCKETS,
    BODY,
    BOW,
    DATA,
    LIFE,
    QUALITY_ACCURACY,
    QUALITY_LIFE,
    SWORD,
    WEAPON_CRITICAL,
    WEAPON_EXTRA_SLOT,
)

from crafting_system.items import (
    EnchantClass,
    EnchantKind,
    EnchantmentError,
    Item,
    ItemError,
    Rarity,
    UnknownModError,
    enchant_info,
)

LIFE_PREFIX = "IncreasedLife1"


def build(base_id: str = BODY, **fields) -> Item:
    fields.setdefault("item_level", 84)
    fields.setdefault("rarity", Rarity.RARE)
    return Item.build(DATA, base_id=base_id, **fields)


def test_an_item_without_the_field_has_none_and_equals_one_built_with_none():
    plain = build()
    assert plain.enchantment is None
    assert plain == build(enchantment=None)
    assert hash(plain) == hash(build(enchantment=None))


def test_the_field_comes_after_the_older_ones_so_an_item_built_before_it_keeps_its_positional_fields():
    names = [field.name for field in dataclasses.fields(Item)]
    assert names[9:] == ["enchantment", "memory_strands"]  # a new field goes last (memory_strands, ADR-0040)
    assert names[:9] == [
        "base_id", "item_level", "rarity", "mods", "influences", "corrupted", "implicits", "quality", "veil_offer",
    ]  # fmt: skip


def test_round_trip_of_an_item_with_and_without_the_field():
    for enchantment in (None, LIFE):
        held = build(enchantment=enchantment)
        again = Item.build(DATA, **{field.name: getattr(held, field.name) for field in dataclasses.fields(Item)})
        assert again == held
        assert again.enchantment == enchantment


def test_the_enchantment_is_set_replaced_and_cleared_through_changed():
    plain = build()
    held = plain.changed(DATA, enchantment=LIFE)
    assert held.enchantment == LIFE
    assert held != plain
    assert held.changed(DATA, enchantment=ARMOUR_EXTRA_SLOT).enchantment == ARMOUR_EXTRA_SLOT
    assert held.changed(DATA, enchantment=None) == plain


def test_the_enchantment_rides_along_when_mods_change():
    held = build(enchantment=LIFE)
    from crafting_system.items import ExplicitMod

    life = DATA.mods[LIFE_PREFIX]
    rolled = ExplicitMod(LIFE_PREFIX, 1, tuple(stat.min for stat in life.stats))
    assert held.add_mod(DATA, rolled).enchantment == LIFE
    assert held.add_mod(DATA, rolled).remove_mod(DATA, LIFE_PREFIX).enchantment == LIFE


@pytest.mark.parametrize(
    ("base", "enchantment"),
    [
        (BODY, LIFE),
        (BODY, ARMOUR_EXTRA_SLOT),
        (BODY, QUALITY_LIFE),
        (SWORD, WEAPON_CRITICAL),
        (BOW, WEAPON_EXTRA_SLOT),
        (SWORD, QUALITY_ACCURACY),
    ],
)
def test_an_enchantment_that_fits_the_base_is_accepted(base, enchantment):
    assert build(base, enchantment=enchantment).enchantment == enchantment


def test_normal_and_corrupted_items_can_hold_an_enchantment():
    assert build(rarity=Rarity.NORMAL, enchantment=LIFE).enchantment == LIFE
    assert build(corrupted=True, enchantment=LIFE).corrupted


def test_an_unknown_mod_id_is_refused_naming_it():
    with pytest.raises(UnknownModError, match=r"enchantment NoSuchEnchant is not in the game data"):
        build(enchantment="NoSuchEnchant")


def test_a_mod_that_is_no_enchantment_is_refused_naming_it():
    with pytest.raises(EnchantmentError, match=rf"enchantment {LIFE_PREFIX} is not an enchantment"):
        build(enchantment=LIFE_PREFIX)


def test_a_pool_enchant_the_3_29_patch_removed_is_refused_with_the_reason():
    with pytest.raises(EnchantmentError, match=rf"enchantment {ARMOUR_WHITE_SOCKETS} was removed from the enchant pool in 3.29.0"):
        build(enchantment=ARMOUR_WHITE_SOCKETS)


def test_an_armour_enchant_on_a_weapon_and_a_weapon_enchant_on_armour_are_refused():
    with pytest.raises(EnchantmentError, match=rf"enchantment {LIFE} is a body armour enchantment, but the base is a weapon"):
        build(SWORD, enchantment=LIFE)
    with pytest.raises(EnchantmentError, match=rf"enchantment {WEAPON_CRITICAL} is a weapon enchantment, but the base is a body armour"):
        build(BODY, enchantment=WEAPON_CRITICAL)
    with pytest.raises(EnchantmentError, match="is a weapon enchantment, but the base is a body armour"):
        build(BODY, enchantment=QUALITY_ACCURACY)


def test_a_base_that_takes_no_enchantment_is_refused():
    with pytest.raises(EnchantmentError, match=rf"enchantment {LIFE} cannot sit on a base of item class Amulet: only weapons and body armour"):
        build(AMULET, enchantment=LIFE)


@pytest.mark.parametrize("value", ["", 7, b"x"])
def test_a_value_that_is_not_a_mod_id_is_refused(value):
    with pytest.raises(EnchantmentError, match="is not a mod id or None"):
        Item(base_id=BODY, item_level=84, rarity=Rarity.RARE, enchantment=value)


def test_every_enchantment_error_is_an_item_error():
    assert issubclass(EnchantmentError, ItemError)


def test_enchant_info_tells_the_kinds_apart():
    life = enchant_info(DATA.mods[LIFE])
    assert (life.kind, life.item_class, life.tags, life.clean) == (EnchantKind.POOL, EnchantClass.BODY_ARMOUR, ("Life",), True)
    slot = enchant_info(DATA.mods[ARMOUR_EXTRA_SLOT])
    assert slot.extra_slot and not slot.clean and slot.tags == ()
    quality = enchant_info(DATA.mods[QUALITY_LIFE])
    assert quality.kind is EnchantKind.QUALITY and not quality.clean
    assert enchant_info(DATA.mods[LIFE_PREFIX]) is None
    assert enchant_info(DATA.mods[ARMOUR_WHITE_SOCKETS]) is None
