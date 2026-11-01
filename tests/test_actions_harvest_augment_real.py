"""The Harvest add/remove and swap crafts on the real 3.29.3.3 dump (ticket #148); these skip cleanly when the dump is not cached (CI has it).

Every expected number is a hand walk over `data.mods`, written without the action code, as `test_actions_harvest_reforges_real.py` does:

* Fire add/remove on a rare Coral Amulet of item level 86 holding three mods: the addable mods are the ones with the `fire` implicit
  tag that an amulet rolls at that level (the first matching spawn tag decides, the generation weight scales it), minus the families the
  item holds, on a side with a free slot; the sum of the weights, the chance of one mod and the number of results (mods times 3
  removals) are typed here. The same craft costs 283.75 chaos at the prices of 2026-10-31.
* The resistance swaps on a rare Coral Ring: the tier is kept (the tier-1 Fire Resistance `FireResist8` becomes `ColdResist8`), and at
  item level 49 the tier-4 Fire Resistance `FireResist5` (level 48) cannot become the Cold one (`ColdResist5` needs 50) but can become
  the Lightning one (`LightningResist5` needs 49). Tiers count down from the highest level: tier 1 is `FireResist8`, tier 8 `FireResist1`.
* A maximum-resistance swap on a Splintered Tower Shield keeps the tier (`MaximumFireResist1` to `MaximumColdResist1`, tier 3).
* A damage swap on a Driftwood Wand turns `LocalAddedFireDamage8` (tier 3) into `LocalAddedColdDamage8` (tier 3).
"""

import datetime
from fractions import Fraction

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import HarvestAddRemove, HarvestDamageSwap, HarvestResistanceSwap, NotApplicableError
from crafting_system.cli._offers import offer_of, price_offers
from crafting_system.items import ExplicitMod, ImplicitMod, Item, Rarity
from crafting_system.prices import PriceEntry, PriceFile

# the prices of 2026-10-31 in chaos; the Sacred price is the one that makes the Fire craft 283.75 (15000 Wild = 234, Sacred = 49.75)
PRICES = {
    "Wild Crystallised Lifeforce": 0.0156,
    "Vivid Crystallised Lifeforce": 0.1688,
    "Primal Crystallised Lifeforce": 0.03529,
    "Sacred Crystallised Lifeforce": 49.75,
    "Crystallised Rancour": 465.3,
}


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def base_id(data, name: str) -> str:
    return next(b for b in data.base_items.values() if b.name == name).id


def rare(data, name: str, level: int, *mods: ExplicitMod) -> Item:
    return Item.build(data, base_id=base_id(data, name), item_level=level, rarity=Rarity.RARE, mods=mods)


def only_result(outcomes) -> Item:
    ((chance, result),) = outcomes.results
    assert chance == 1
    return result


def shown(item: Item) -> list[tuple]:
    return sorted((e.mod_id, e.tier, e.values) for e in item.mods)


# --- (1) Fire add/remove on the amulet ---------------------------------------------------------------

# three prefixes (a full side): Life 8 (tier 1), Mana 8 (tier 6), Lightning gem level (tier 1), each at its lowest values
FULL_PREFIXES = (
    ExplicitMod("IncreasedLife8", 1, (115,)),
    ExplicitMod("IncreasedMana8", 6, (50,)),
    ExplicitMod("GlobalLightningGemLevel1", 1, (1,)),
)
# two prefixes and a suffix, the families Fire Damage and Fire Resistance held: Life 8, Added Fire Damage 5 (tier 5), Fire Resistance 5 (tier 4)
FIRE_HELD = (
    ExplicitMod("IncreasedLife8", 1, (115,)),
    ExplicitMod("AddedFireDamage5", 5, (9, 19)),
    ExplicitMod("FireResist5", 4, (30,)),
)
# what the hand walk finds (by hand): the fire mods an empty amulet rolls at level 86 are AddedFireDamage1..9 (prefixes, 500 each but
# 250 for the 9th), FireResist1..8 (suffixes, 1000), FireDamagePercent1..5 (suffixes, 500) and GlobalFireGemLevel1_ (a prefix, 200)
SUFFIX_FIRE = {f"FireResist{n}": 1000 for n in range(1, 9)} | {f"FireDamagePercent{n}": 500 for n in range(1, 6)}  # 13 mods, 10,500
FIRE_HELD_FIRE = {f"FireDamagePercent{n}": 500 for n in range(1, 6)} | {"GlobalFireGemLevel1_": 200}  # 6 mods, 2,700


def hand_addable(data, item: Item, level: int = 86) -> dict[str, int]:
    """The weight of each fire mod an amulet of `item`'s kind can be given, by a walk over the dump."""
    base = data.base_items[item.base_id]
    tags = set(base.tags)
    held_families = {family for e in item.mods for family in data.mods[e.mod_id].families}
    held_per_side = {side: sum(data.mods[e.mod_id].generation_type == side for e in item.mods) for side in ("prefix", "suffix")}
    found = {}
    for mod in data.mods.values():
        if mod.domain != base.domain or mod.generation_type not in ("prefix", "suffix") or mod.required_level > level:
            continue
        spawn = 0 if "Royale" in mod.id else next((w.weight for w in mod.spawn_weights if w.tag in tags), 0)  # a Battle Royale copy is not rolled (#310)
        if not spawn or "fire" not in mod.implicit_tags or held_families & set(mod.families):
            continue
        if held_per_side[mod.generation_type] >= 3:  # a rare item holds three prefixes and three suffixes
            continue
        factor = next((Fraction(w.weight, 100) for w in mod.generation_weights if w.tag in tags), Fraction(1))
        found[mod.id] = spawn * factor
    return found


def pairs(outcomes, given: Item) -> dict[tuple[str, str], Fraction]:
    """(added mod, removed mod) -> the chance of that result."""
    before = {e.mod_id for e in given.mods}
    table = {}
    for chance, result in outcomes.results:
        after = {e.mod_id for e in result.mods}
        (added,) = after - before
        (removed,) = before - after
        assert (added, removed) not in table
        table[(added, removed)] = chance
    return table


def test_the_hand_walk_finds_the_typed_candidates(data):
    full = hand_addable(data, rare(data, "Coral Amulet", 86, *FULL_PREFIXES))
    assert full == SUFFIX_FIRE and sum(full.values()) == 10500
    held = hand_addable(data, rare(data, "Coral Amulet", 86, *FIRE_HELD))
    assert held == FIRE_HELD_FIRE and sum(held.values()) == 2700
    empty = hand_addable(data, rare(data, "Coral Amulet", 86))
    assert len(empty) == 23 and sum(empty.values()) == 9 * 500 - 250 + 8000 + 2500 + 200


def test_fire_add_remove_with_a_full_prefix_side_draws_only_among_the_fire_suffixes(data):
    item = rare(data, "Coral Amulet", 86, *FULL_PREFIXES)
    outcomes = HarvestAddRemove("fire").outcomes(data, item)
    table = pairs(outcomes, item)
    removable = ["IncreasedLife8", "IncreasedMana8", "GlobalLightningGemLevel1"]
    assert len(outcomes.results) == 13 * 3 == 39
    assert set(table) == {(added, gone) for added in SUFFIX_FIRE for gone in removable}
    for (added, gone), chance in table.items():
        assert chance == Fraction(SUFFIX_FIRE[added], 10500) / 3, (added, gone)
    assert table[("FireResist8", "IncreasedMana8")] == Fraction(2, 63)  # 1000 / 10500 / 3
    assert table[("FireDamagePercent5", "IncreasedLife8")] == Fraction(1, 63)  # 500 / 10500 / 3
    assert outcomes.chance_all(["FireResist8"]) == Fraction(2, 21)
    assert outcomes.chance_all(["IncreasedLife8", "FireResist8"]) == Fraction(2, 21) * Fraction(2, 3)


def test_the_new_mod_is_rolled_at_its_table_tier_and_lowest_values(data):
    item = rare(data, "Coral Amulet", 86, *FULL_PREFIXES)
    new = {
        (e.mod_id, e.tier, e.values)
        for _, result in HarvestAddRemove("fire").outcomes(data, item).results
        for e in result.mods
        if e.mod_id in ("FireResist8", "FireResist1", "FireDamagePercent5")
    }
    assert new == {("FireResist8", 1, (46,)), ("FireResist1", 8, (6,)), ("FireDamagePercent5", 1, (23,))}


def test_fire_add_remove_leaves_the_families_the_item_holds_out_of_the_draw(data):
    item = rare(data, "Coral Amulet", 86, *FIRE_HELD)
    outcomes = HarvestAddRemove("fire").outcomes(data, item)
    table = pairs(outcomes, item)
    assert len(outcomes.results) == 6 * 3 == 18
    assert set(table) == {(added, gone) for added in FIRE_HELD_FIRE for gone in ("IncreasedLife8", "AddedFireDamage5", "FireResist5")}
    for (added, gone), chance in table.items():
        assert chance == Fraction(FIRE_HELD_FIRE[added], 2700) / 3, (added, gone)
    assert table[("GlobalFireGemLevel1_", "FireResist5")] == Fraction(2, 81)  # 200 / 2700 / 3
    assert outcomes.chance_all(["GlobalFireGemLevel1_"]) == Fraction(2, 27)
    # no Fire Damage or Fire Resistance mod other than the held one is ever added
    assert outcomes.chance_all(["AddedFireDamage9"]) == 0 and outcomes.chance_all(["FireResist8"]) == 0


def test_fire_add_remove_costs_283_75_chaos_at_the_prices_of_2026_10_31(data):
    action = HarvestAddRemove("fire")
    assert action.resources() == {"Wild Crystallised Lifeforce": 15000, "Sacred Crystallised Lifeforce": 1}
    file = PriceFile("Test", datetime.datetime(2026, 10, 31, tzinfo=datetime.UTC), 300.0, {k: PriceEntry(v, "test") for k, v in PRICES.items()})
    offer = offer_of(action, action.label(data), data, rare(data, "Coral Amulet", 86, *FIRE_HELD))
    priced, dropped = price_offers([offer], file)
    assert not dropped
    assert priced[0].cost == pytest.approx(283.75, abs=0.01)  # 15000 * 0.0156 + 49.75


# --- (2) the resistance swaps on the ring ------------------------------------------------------------


def test_fire_to_cold_on_a_ring_keeps_tier_one(data):
    item = rare(data, "Coral Ring", 86, ExplicitMod("FireResist8", 1, (46,)))
    result = only_result(HarvestResistanceSwap("fire", "cold").outcomes(data, item))
    assert shown(result) == [("ColdResist8", 1, (46,))]


def test_a_tier_four_fire_resistance_cannot_become_cold_at_item_level_49_but_can_become_lightning(data):
    item = rare(data, "Coral Ring", 49, ExplicitMod("FireResist5", 4, (30,)))  # Fire tier 4 needs 48
    with pytest.raises(NotApplicableError, match="above the item level"):
        HarvestResistanceSwap("fire", "cold").outcomes(data, item)  # ColdResist5, tier 4, needs 50
    result = only_result(HarvestResistanceSwap("fire", "lightning").outcomes(data, item))  # LightningResist5 needs 49
    assert shown(result) == [("LightningResist5", 4, (30,))]


def test_at_item_level_50_the_same_swap_to_cold_works(data):
    item = rare(data, "Coral Ring", 50, ExplicitMod("FireResist5", 4, (30,)))
    result = only_result(HarvestResistanceSwap("fire", "cold").outcomes(data, item))
    assert shown(result) == [("ColdResist5", 4, (30,))]


@pytest.mark.parametrize(
    ("start", "tier", "low", "target", "end"),
    [
        ("FireResist1", 8, 6, "cold", "ColdResist1"),
        ("FireResist2", 7, 12, "cold", "ColdResist2"),
        ("FireResist3", 6, 18, "lightning", "LightningResist3"),
        ("FireResist7", 2, 42, "cold", "ColdResist7"),
    ],
)
def test_the_tier_is_kept_down_the_ladder(data, start, tier, low, target, end):
    item = rare(data, "Coral Ring", 86, ExplicitMod(start, tier, (low,)))
    result = only_result(HarvestResistanceSwap("fire", target).outcomes(data, item))
    assert shown(result) == [(end, tier, (low,))]


# --- (3) a maximum-resistance swap on a shield ---------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "tier", "value", "end"),
    [
        ("MaximumFireResist1", 3, 1, "MaximumColdResist1"),  # +1 maximum resistance, level 68 (Cold 68)
        ("MaximumFireResist2_", 2, 2, "MaximumColdResist2"),  # +2, level 75 (Cold 75)
        ("MaximumFireResist3", 1, 3, "MaximumColdResist3"),  # +3, level 81 (Cold 81)
    ],
)
def test_a_maximum_resistance_swap_keeps_the_tier(data, start, tier, value, end):
    item = rare(data, "Splintered Tower Shield", 86, ExplicitMod(start, tier, (value,)))
    result = only_result(HarvestResistanceSwap("fire", "cold").outcomes(data, item))
    assert shown(result) == [(end, tier, (value,))]


def test_a_plain_and_a_maximum_resistance_on_a_shield_are_two_sources_of_one_half(data):
    item = rare(
        data, "Splintered Tower Shield", 86, ExplicitMod("FireResist8", 1, (46,)), ExplicitMod("MaximumFireResist1", 3, (1,))
    )
    outcomes = HarvestResistanceSwap("fire", "cold").outcomes(data, item)
    assert {tuple(shown(result)): chance for chance, result in outcomes.results} == {
        (("ColdResist8", 1, (46,)), ("MaximumFireResist1", 3, (1,))): Fraction(1, 2),
        (("FireResist8", 1, (46,)), ("MaximumColdResist1", 3, (1,))): Fraction(1, 2),
    }


# --- (4) a damage swap on a wand --------------------------------------------------------------------------


def test_local_added_fire_damage_becomes_the_cold_mod_of_the_same_tier(data):
    item = rare(data, "Driftwood Wand", 86, ExplicitMod("LocalAddedFireDamage8", 3, (59, 120)))
    result = only_result(HarvestDamageSwap("fire", "cold").outcomes(data, item))
    assert shown(result) == [("LocalAddedColdDamage8", 3, (54, 108))]  # tier 3: Fire needs level 62, Cold 63


def test_the_top_tier_of_local_added_damage_swaps_too(data):
    item = rare(data, "Driftwood Wand", 86, ExplicitMod("LocalAddedFireDamage10_", 1, (89, 180)))
    result = only_result(HarvestDamageSwap("fire", "cold").outcomes(data, item))
    assert shown(result) == [("LocalAddedColdDamage10__", 1, (81, 163))]


@pytest.mark.parametrize(("level", "works"), [(62, False), (63, True)])
def test_a_wand_at_item_level_62_cannot_take_the_cold_mod_that_needs_63(data, level, works):
    item = rare(data, "Driftwood Wand", level, ExplicitMod("LocalAddedFireDamage8", 3, (59, 120)))
    if works:
        assert shown(only_result(HarvestDamageSwap("fire", "cold").outcomes(data, item))) == [("LocalAddedColdDamage8", 3, (54, 108))]
    else:
        with pytest.raises(NotApplicableError, match="above the item level"):
            HarvestDamageSwap("fire", "cold").outcomes(data, item)


def test_an_eldritch_implicit_does_not_refuse_the_add_remove_craft_and_stays_on_the_item(data):
    """The owner's answer (grill B2): the craft works on an item with an Eldritch implicit; the implicit is no explicit mod, so it is never removed."""
    implicit = ImplicitMod("AvoidShockEldritchImplicit3", 3, (min(data.mods["AvoidShockEldritchImplicit3"].stats[0].min, data.mods["AvoidShockEldritchImplicit3"].stats[0].max),))
    body = base_id(data, "Astral Plate")
    life = ExplicitMod("IncreasedLife7", 1, (min(data.mods["IncreasedLife7"].stats[0].min, data.mods["IncreasedLife7"].stats[0].max),))
    item = Item.build(data, base_id=body, item_level=86, rarity=Rarity.RARE, mods=(life,), implicits=(implicit,))
    outcomes = HarvestAddRemove("life").outcomes(data, item)
    assert outcomes.results
    for chance, result in outcomes.results:
        assert result.implicits == (implicit,)
        assert [entry.mod_id for entry in result.mods if entry.mod_id == "IncreasedLife7"] == []  # the only removable mod is the old one
