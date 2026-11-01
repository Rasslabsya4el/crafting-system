"""Battle Royale copies of mods do not spawn: no pool, tier table or weight sum holds them (ticket #310).

The export marks no field on them; their id holds the word "Royale" (`affix_pool.royale_duplicates_do_not_spawn`).
Four of them carry spawn weights on ordinary bases in 3.29.3.3 but are not mods the game rolls. The tests on the
real dump need the cached export and skip cleanly without it (CI fetches it, ticket #165).
"""

import pytest
from abstraction_support import real_game_data
from items_support import DATA, item, roll

from crafting_system.actions.pool import pool_candidates
from crafting_system.items import Item, Rarity, Side, is_battle_royale, spawn_weight, tier_table
from crafting_system.rules import get_rule

FOUR = (
    "MovementVelocity2Royale",
    "IncreasedCastSpeed2Royale",
    "IncreasedAttackSpeed2Royale",
    "LocalIncreasedAttackSpeed2Royale____",
)
BOW = "Metadata/Items/Weapons/TwoHandWeapons/Bows/Bow16"  # the fixture bow, which holds LocalIncreasedAttackSpeed2Royale____
ATTACK_SPEED_OF_THE_FIXTURE_BOW = ("LocalIncreasedAttackSpeed1", "LocalIncreasedAttackSpeed2", "LocalIncreasedAttackSpeed3",
                                   "LocalIncreasedAttackSpeed4", "LocalIncreasedAttackSpeed5")  # fmt: skip


def rare(data, base_id: str, level: int = 100) -> Item:
    return Item.build(data, base_id=base_id, item_level=level, rarity=Rarity.RARE, mods=())


def prefix_suffix_tiers(data, base_id: str, mod_type: str, side: str) -> dict[str, int]:
    """The tiers of the ordinary (item-domain) mods of one mod type and side that can spawn on the base."""
    table = tier_table(data, base_id)
    return {
        mod_id: tier
        for mod_id, tier in table.items()
        if (mod := data.mods[mod_id]).type == mod_type and mod.generation_type == side and mod.domain == "item"
    }


# --- the rule and its claim (fixture) -----------------------------------------------------------------


def test_the_claim_reads_the_marker_from_the_registry():
    assert get_rule("affix_pool.royale_duplicates_do_not_spawn").value == {"id_marker": "Royale"}


def test_the_fixture_gives_the_royale_copy_a_spawn_weight_in_the_raw_data_and_zero_in_the_rule():
    royale = DATA.mods["LocalIncreasedAttackSpeed2Royale____"]
    tags = DATA.base_items[BOW].tags

    assert any(entry.weight > 0 and entry.tag in tags for entry in royale.spawn_weights)
    assert is_battle_royale(royale)
    assert spawn_weight(royale, tags) == 0
    assert not is_battle_royale(DATA.mods["LocalIncreasedAttackSpeed2"])
    assert spawn_weight(DATA.mods["LocalIncreasedAttackSpeed2"], tags) == 1000


def test_the_fixture_bows_pool_and_tier_table_leave_the_royale_copy_out():
    pool = pool_candidates(DATA, item(base_id=BOW, item_level=86))
    table = tier_table(DATA, BOW)

    assert "LocalIncreasedAttackSpeed2Royale____" not in {candidate.mod.id for candidate in pool}
    assert "LocalIncreasedAttackSpeed2Royale____" not in table
    attack_speed = sum(candidate.weight for candidate in pool if candidate.mod.id in ATTACK_SPEED_OF_THE_FIXTURE_BOW)
    assert attack_speed == 4000  # 1000 each for tiers 1 to 3 and 500 each for the two highest, not 5000


def test_the_attack_speed_tiers_of_the_fixture_bow_count_five_not_six():
    tiers = {mod_id: table_tier for mod_id, table_tier in tier_table(DATA, BOW).items() if mod_id.startswith("LocalIncreasedAttackSpeed")}

    assert tiers == {f"LocalIncreasedAttackSpeed{n}": 6 - n for n in range(1, 6)}


def test_a_royale_mod_can_still_be_held_by_an_item():
    held = item(roll("LocalIncreasedAttackSpeed2Royale____"), base_id=BOW, item_level=86)

    assert [entry.mod_id for entry in held.mods] == ["LocalIncreasedAttackSpeed2Royale____"]


# --- the real dump -------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def test_the_four_ids_have_a_raw_weight_and_the_marker_reaches_nothing_else_that_spawns(data):
    raw_weighted = sorted(
        mod.id for mod in data.mods.values() if is_battle_royale(mod) and any(entry.weight > 0 for entry in mod.spawn_weights)
    )

    assert raw_weighted == sorted(FOUR)


def test_none_of_the_four_spawns_on_any_base(data):
    for base in data.base_items.values():
        for mod_id in FOUR:
            assert spawn_weight(data.mods[mod_id], base.tags) == 0, (mod_id, base.id)


@pytest.mark.parametrize(
    "base_class",
    ["Boots", "Gloves", "Quiver", "Wand", "Sceptre", "One Hand Sword", "Two Hand Axe", "Bow", "Amulet", "Ring", "Body Armour"],
)
def test_none_of_the_four_is_in_a_pool_or_a_tier_table(data, base_class):
    base = next(
        base
        for base in data.base_items.values()
        if base.item_class == base_class and base.release_state == "released" and base.domain == "item"
    )

    ids = {candidate.mod.id for candidate in pool_candidates(data, rare(data, base.id))}

    assert not ids & set(FOUR)
    assert not set(tier_table(data, base.id)) & set(FOUR)


def test_the_amulet_pool_at_item_level_86_has_the_suffix_total_of_craft_of_exile(data):
    amulet = next(base for base in data.base_items.values() if base.item_class == "Amulet" and base.release_state == "released")

    pool = pool_candidates(data, rare(data, amulet.id, 86))

    assert sum(c.weight for c in pool if c.side is Side.SUFFIX) == 125_250  # 126,050 with IncreasedCastSpeed2Royale
    assert sum(c.weight for c in pool if c.side is Side.PREFIX) == 88_600


# T, the number of tiers of a mod type, as the game counts it (the highest tier number of the type on the base):
# movement speed has six prefixes, cast speed seven suffixes on a wand, attack speed four suffixes on gloves and
# local attack speed eight on a one-handed sword and five on a wand (with the Royale copies it was one more each).
@pytest.mark.parametrize(
    ("base_class", "mod_type", "side", "expected"),
    [
        ("Boots", "MovementVelocity", "prefix", 6),
        ("Wand", "IncreasedCastSpeed", "suffix", 7),
        ("Sceptre", "IncreasedCastSpeed", "suffix", 7),
        ("Amulet", "IncreasedCastSpeed", "suffix", 4),
        ("Gloves", "IncreasedAttackSpeed", "suffix", 4),
        ("Quiver", "IncreasedAttackSpeed", "suffix", 4),
        ("One Hand Sword", "LocalIncreasedAttackSpeed", "suffix", 8),
        ("Wand", "LocalIncreasedAttackSpeed", "suffix", 5),
        ("Bow", "LocalIncreasedAttackSpeed", "suffix", 5),
    ],
)
def test_t_of_the_three_mod_types_is_the_games_tier_count(data, base_class, mod_type, side, expected):
    base = next(
        base
        for base in data.base_items.values()
        if base.item_class == base_class and base.release_state == "released" and base.domain == "item"
    )

    tiers = prefix_suffix_tiers(data, base.id, mod_type, side)

    assert max(tiers.values()) == expected
    assert sorted(set(tiers.values())) == list(range(1, expected + 1))  # no tier number is skipped or doubled
