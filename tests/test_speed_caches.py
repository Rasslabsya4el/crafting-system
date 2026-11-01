"""The speed caches of `tier_table` and `pool_candidates`: the same answer, the same object, and the errors kept."""

import dataclasses

import pytest
from actions_support import AMULET, DATA, amulet, roll
from repoe_support import no_network  # noqa: F401

from crafting_system.actions.errors import OutOfScopeError
from crafting_system.actions.pool import pool_candidates
from crafting_system.items import Item, Rarity, UnknownBaseError, tier_table
from crafting_system.items.tiers import _compute_tier_table

NO_BASE = "Metadata/Items/Amulets/NoSuchAmulet"


def families(pool):
    return {candidate.family for candidate in pool}


def test_tier_table_called_twice_returns_the_same_object():
    first = tier_table(DATA, AMULET)

    assert tier_table(DATA, AMULET) is first


def test_the_cached_tier_table_equals_a_fresh_computation():
    assert dict(tier_table(DATA, AMULET)) == dict(_compute_tier_table(DATA, AMULET))


def test_a_different_data_object_is_not_served_the_old_table():
    other = dataclasses.replace(DATA)

    table = tier_table(other, AMULET)

    assert table is not tier_table(DATA, AMULET)
    assert dict(table) == dict(_compute_tier_table(DATA, AMULET))


def test_pool_candidates_called_twice_on_equal_items_returns_the_same_tuple():
    first = pool_candidates(DATA, amulet())

    assert pool_candidates(DATA, amulet()) is first


def test_a_different_item_level_gives_a_different_pool():
    base = pool_candidates(DATA, amulet())
    lower = pool_candidates(DATA, amulet(item_level=74))

    assert lower is not base
    assert "GlobalDamageTypeGemLevel" in families(base)
    assert "GlobalDamageTypeGemLevel" not in families(lower)


def test_a_different_max_level_gives_a_different_pool():
    base = pool_candidates(DATA, amulet())
    capped = pool_candidates(DATA, amulet(), max_level=80)

    assert capped is not base
    assert any(candidate.mod.required_level > 80 for candidate in base)
    assert all(candidate.mod.required_level <= 80 for candidate in capped)


def test_an_item_with_a_different_mod_gives_a_different_pool():
    plain = pool_candidates(DATA, amulet())
    with_resist = pool_candidates(DATA, amulet(roll("LightningResist1")))

    assert with_resist is not plain
    assert "LightningResistance" in families(plain)
    assert "LightningResistance" not in families(with_resist)


def test_extra_mods_join_the_pool_and_a_different_extra_gives_a_different_pool():
    plain = pool_candidates(DATA, amulet())
    joined = dataclasses.replace(DATA.mods["IncreasedLife1"], id="ExtraIncreasedLife", families=("ExtraLife",))
    other = dataclasses.replace(joined, id="OtherExtraLife", families=("OtherLife",))

    with_extra = pool_candidates(DATA, amulet(), extra=[joined])

    assert with_extra is not plain
    assert "ExtraLife" in families(with_extra)
    assert "ExtraLife" not in families(plain)
    assert pool_candidates(DATA, amulet(), extra=iter([joined])) is with_extra
    assert "OtherLife" in families(pool_candidates(DATA, amulet(), extra=(other,)))


def test_an_unknown_base_is_refused_on_every_call():
    with pytest.raises(UnknownBaseError, match="is not in the game data"):
        tier_table(DATA, NO_BASE)
    with pytest.raises(UnknownBaseError, match="is not in the game data"):
        tier_table(DATA, NO_BASE)

    no_base_item = Item(base_id=NO_BASE, item_level=86, rarity=Rarity.RARE)
    for _ in range(2):
        with pytest.raises(UnknownBaseError, match="is not in the game data"):
            pool_candidates(DATA, no_base_item)


def test_an_out_of_scope_pool_is_refused_on_every_call():
    mod = DATA.mods["IncreasedLife1"]
    two = dataclasses.replace(mod, families=("IncreasedLife", "SomethingElse"))
    data = dataclasses.replace(DATA, mods={**DATA.mods, mod.id: two})

    for _ in range(2):
        with pytest.raises(OutOfScopeError, match="IncreasedLife1.*2 families"):
            pool_candidates(data, amulet())


def test_the_tag_filter_is_part_of_the_pool_key():
    on = pool_candidates(DATA, amulet(), tag_filter=True)
    off = pool_candidates(DATA, amulet(), tag_filter=False)

    assert pool_candidates(DATA, amulet(), tag_filter=False) is off
    assert pool_candidates(DATA, amulet(), tag_filter=True) is on
