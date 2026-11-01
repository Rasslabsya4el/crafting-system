"""The Harvest resistance and damage swaps on the small amulet pool (ticket #148, ADR-0030).

Every expected number is typed here from the wiki table, the rules and the data of the pool, not read from the registry or the
code: the 6 + 6 pairs with their keys, labels and lifeforce costs, the prices of 2026-10-31, the tiers of the small pool, the
lowest values of each mod, and which mods a swap changes into which.

The small pool (`abstraction_pool.SMALL`) holds one Fire and one Cold resistance (tier 1 each) and three Lightning resistances
(`LightningResist1` to `LightningResist3`, required levels 1, 13 and 25, so tiers 3, 2 and 1) and the Lightning damage mods
`AddedLightningDamage1` and `AddedLightningDamage2` (levels 3 and 13, tiers 2 and 1). The Fire and Cold damage mods, the
maximum resistances, a spell damage pair and a crafted resistance are not in it, so `WORLD` below derives them by hand: the
stat ids and the tags of a pool mod with the element word replaced, a new family, the same side. The Cold damage tier 1 needs
level 15 (Fire's and Lightning's 13), to have an element whose target needs more than the source.
"""

import dataclasses
import datetime
import random
from collections import Counter
from fractions import Fraction

import pytest
from abstraction_pool import (
    COLD_RESIST,
    DAMAGE_1,
    DAMAGE_2,
    FIRE_RESIST,
    GEM,
    LIFE_1,
    RESIST_1,
    RESIST_2,
    RESIST_3,
    SMALL,
)
from items_support import AMULET, DATA

from crafting_system.actions import (
    HarvestDamageSwap,
    HarvestResistanceSwap,
    NotApplicableError,
    catalog,
    kinds,
)
from crafting_system.cli._offers import offer_of, price_offers
from crafting_system.items import ExplicitMod, Influence, Item, Rarity
from crafting_system.prices import PriceEntry, PriceFile

# --- the pairs, typed from the wiki table ------------------------------------------------------------

PAIRS = [
    ("fire", "cold", "Vivid"),
    ("fire", "lightning", "Primal"),
    ("cold", "fire", "Wild"),
    ("cold", "lightning", "Primal"),
    ("lightning", "fire", "Wild"),
    ("lightning", "cold", "Vivid"),
]  # (from, to, the colour of the target's lifeforce)
RANCOUR = "Crystallised Rancour"

# the prices of 2026-10-31, in chaos
PRICES = {
    "Wild Crystallised Lifeforce": 0.0156,
    "Vivid Crystallised Lifeforce": 0.1688,
    "Primal Crystallised Lifeforce": 0.03529,
    RANCOUR: 465.3,
}
# what one use costs at those prices: 500 lifeforce of the target's colour, plus 1 Rancour for a damage swap
RESISTANCE_COST = {"fire": 7.8, "cold": 84.4, "lightning": 17.6}
DAMAGE_COST = {"fire": 473.1, "cold": 549.7, "lightning": 482.9}

# --- the world: the small pool and the mods it lacks -------------------------------------------------

FIRE_DAMAGE_1, FIRE_DAMAGE_2 = "TestFireDamage1", "TestFireDamage2"  # levels 3 and 13: tiers 2 and 1
COLD_DAMAGE_1, COLD_DAMAGE_2 = "TestColdDamage1", "TestColdDamage2"  # levels 3 and 15: tiers 2 and 1
FIRE_SPELL, COLD_SPELL = "TestFireSpell1", "TestColdSpell1"  # a spell damage prefix of its own family, tier 1 each
MAX_FIRE, MAX_COLD = "TestMaximumFireResist1", "TestMaximumColdResist1"  # suffixes, level 68, tier 1 each
CRAFTED_FIRE = "TestCraftedFireResist"  # a crafted-domain fire resistance
PCBC = "StrMasterItemGenerationCannotChangePrefixes"  # a suffix; locks the prefixes
SCBC = "DexMasterItemGenerationCannotChangeSuffixes"  # a prefix; locks the suffixes
NO_ATTACK = "IntMasterItemGenerationCannotRollAttackAffixes"  # a suffix
NO_CASTER = "StrDexMasterItemGenerationCannotRollCasterAffixes"  # a suffix


def _element(source: str, new_id: str, was: str, now: str, **changes):
    """The mod `source` with the element word `was` replaced by `now` in its stat ids and tags, as a mod of its own family."""
    mod = SMALL.mods[source] if source in SMALL.mods else DATA.mods[source]
    return dataclasses.replace(
        mod,
        id=new_id,
        families=(changes.pop("family", new_id),),
        type=changes.pop("type", new_id),
        implicit_tags=tuple(now if tag == was else tag for tag in mod.implicit_tags),
        stats=tuple(dataclasses.replace(stat, id=stat.id.replace(was, now)) for stat in mod.stats),
        **changes,
    )


def _world():
    mods = dict(SMALL.mods)
    for pair, tier_1, tier_2 in ((("fire", "FireDamage"), FIRE_DAMAGE_1, FIRE_DAMAGE_2), (("cold", "ColdDamage"), COLD_DAMAGE_1, COLD_DAMAGE_2)):
        element, family = pair
        mods[tier_1] = _element(DAMAGE_1, tier_1, "lightning", element, family=family, type=family)
        mods[tier_2] = _element(DAMAGE_2, tier_2, "lightning", element, family=family, type=family)
    mods[COLD_DAMAGE_2] = dataclasses.replace(mods[COLD_DAMAGE_2], required_level=15)
    for new_id, was, now in ((FIRE_SPELL, "lightning", "fire"), (COLD_SPELL, "lightning", "cold")):
        spell = _element(DAMAGE_1, new_id, was, now, family="SpellDamage" + now.title(), type="SpellDamage" + now.title())
        mods[new_id] = dataclasses.replace(
            spell, stats=tuple(dataclasses.replace(s, id=s.id.replace("attack_", "spell_")) for s in spell.stats), required_level=3
        )
    for new_id, now in ((MAX_FIRE, "fire"), (MAX_COLD, "cold")):
        resist = _element(FIRE_RESIST, new_id, "fire", now, family="Maximum" + now.title() + "Resistance", type="Maximum" + now.title() + "Resistance")
        stat = dataclasses.replace(resist.stats[0], id=f"base_maximum_{now}_damage_resistance_%", min=1, max=2)
        mods[new_id] = dataclasses.replace(resist, stats=(stat,), required_level=68)
    mods[CRAFTED_FIRE] = dataclasses.replace(
        mods[FIRE_RESIST], id=CRAFTED_FIRE, type=CRAFTED_FIRE, families=(CRAFTED_FIRE,), domain="crafted"
    )
    for metamod in (PCBC, NO_ATTACK, NO_CASTER):
        mods[metamod] = DATA.mods[metamod]
    return dataclasses.replace(SMALL, mods=mods)


WORLD = _world()

# the tier of each mod in WORLD, by hand (the item model checks it against the data when it builds an item)
TIER = {
    FIRE_RESIST: 1, COLD_RESIST: 1, RESIST_1: 3, RESIST_2: 2, RESIST_3: 1,
    DAMAGE_1: 2, DAMAGE_2: 1, FIRE_DAMAGE_1: 2, FIRE_DAMAGE_2: 1, COLD_DAMAGE_1: 2, COLD_DAMAGE_2: 1,
    FIRE_SPELL: 1, COLD_SPELL: 1, MAX_FIRE: 1, MAX_COLD: 1, CRAFTED_FIRE: 1, LIFE_1: 2, GEM: 1,
}  # fmt: skip
# the lowest value of each stat of the mods the tests expect, by hand
LOWEST = {
    FIRE_RESIST: (6,), COLD_RESIST: (6,), RESIST_1: (6,), RESIST_2: (12,), RESIST_3: (18,),
    DAMAGE_1: (1, 5), DAMAGE_2: (1, 14), FIRE_DAMAGE_1: (1, 5), FIRE_DAMAGE_2: (1, 14), COLD_DAMAGE_1: (1, 5), COLD_DAMAGE_2: (1, 14),
    FIRE_SPELL: (1, 5), COLD_SPELL: (1, 5), MAX_FIRE: (1,), MAX_COLD: (1,), LIFE_1: (10,), GEM: (1,),
}  # fmt: skip


def mod(mod_id: str, *, fractured: bool = False, crafted: bool = False) -> ExplicitMod:
    """The mod at its hand-typed tier and lowest values; a metamod and a crafted mod are tier 1."""
    values = LOWEST.get(mod_id) or tuple(min(s.min, s.max) for s in WORLD.mods[mod_id].stats)
    return ExplicitMod(mod_id, TIER.get(mod_id, 1), values, fractured=fractured, crafted=crafted)


def meta(mod_id: str) -> ExplicitMod:
    return mod(mod_id, crafted=True)


def amulet(*mods: ExplicitMod, level: int = 84, rarity: Rarity = Rarity.RARE, **fields) -> Item:
    return Item.build(WORLD, base_id=AMULET, item_level=level, rarity=rarity, mods=mods, **fields)


def held(item: Item) -> list[tuple]:
    """The mods of `item` as comparable tuples, sorted."""
    return sorted((e.mod_id, e.tier, e.values, e.fractured, e.crafted) for e in item.mods)


def line(*mods: ExplicitMod) -> list[tuple]:
    return sorted((e.mod_id, e.tier, e.values, e.fractured, e.crafted) for e in mods)


def swapped(action, item: Item) -> dict[tuple, Fraction]:
    """The results of `action` on `item`: the sorted mods of each, with its chance."""
    outcomes = action.outcomes(WORLD, item)
    assert sum(chance for chance, _ in outcomes.results) == 1
    return {tuple(held(result)): chance for chance, result in outcomes.results}


def resist(source: str, target: str) -> HarvestResistanceSwap:
    return HarvestResistanceSwap(source, target)


def damage(source: str, target: str) -> HarvestDamageSwap:
    return HarvestDamageSwap(source, target)


# --- the twelve pairs -------------------------------------------------------------------------------


def test_the_hand_typed_tiers_and_levels_are_the_pool_s():
    """Guards the typing: the levels the cases below rely on."""
    assert WORLD.mods[RESIST_3].required_level == 25
    assert WORLD.mods[RESIST_2].required_level == 13
    assert WORLD.mods[FIRE_RESIST].required_level == WORLD.mods[COLD_RESIST].required_level == 1
    assert WORLD.mods[COLD_DAMAGE_2].required_level == 15 and WORLD.mods[FIRE_DAMAGE_2].required_level == 13


@pytest.mark.parametrize(("source", "target", "colour"), PAIRS)
def test_a_resistance_swap_is_a_craft_of_500_lifeforce_of_the_targets_colour(source, target, colour):
    action = resist(source, target)
    assert action.label() == f"Harvest Swap Resistance {source.title()} to {target.title()}"
    assert action.resources() == {f"{colour} Crystallised Lifeforce": 500}


@pytest.mark.parametrize(("source", "target", "colour"), PAIRS)
def test_a_damage_swap_is_500_lifeforce_of_the_targets_colour_and_one_rancour(source, target, colour):
    action = damage(source, target)
    assert action.label() == f"Harvest Swap Damage {source.title()} to {target.title()}"
    assert action.resources() == {f"{colour} Crystallised Lifeforce": 500, RANCOUR: 1}


def test_the_labels_and_the_actions_are_all_different():
    actions = [resist(s, t) for s, t, _ in PAIRS] + [damage(s, t) for s, t, _ in PAIRS]
    assert len({a.label() for a in actions}) == 12
    assert len(set(actions)) == 12


def test_the_default_swap_is_fire_to_cold():
    assert resist("fire", "cold") == HarvestResistanceSwap()
    assert damage("fire", "cold") == HarvestDamageSwap()
    assert HarvestResistanceSwap().label() == "Harvest Swap Resistance Fire to Cold"
    assert HarvestDamageSwap().label() == "Harvest Swap Damage Fire to Cold"


@pytest.mark.parametrize("pair", [("fire", "fire"), ("cold", "cold"), ("lightning", "lightning"), ("fire", "earth"), ("chaos", "fire"), ("Fire", "cold"), ("fire", "Cold"), ("", ""), ("fire", None)])
@pytest.mark.parametrize("swap", [HarvestResistanceSwap, HarvestDamageSwap])
def test_a_pair_that_is_no_swap_is_refused_at_construction(swap, pair):
    with pytest.raises(ValueError, match="no Harvest swap"):
        swap(*pair)


# --- the prices ------------------------------------------------------------------------------------


def _cost(action) -> float:
    file = PriceFile("Test", datetime.datetime(2026, 10, 31, tzinfo=datetime.UTC), 300.0, {k: PriceEntry(v, "test") for k, v in PRICES.items()})
    offer = offer_of(action, action.label(WORLD), WORLD, amulet(mod(FIRE_RESIST)))
    priced, dropped = price_offers([offer], file)
    assert not dropped and len(priced) == 1
    return priced[0].cost


@pytest.mark.parametrize(("source", "target", "colour"), PAIRS)
def test_a_resistance_swap_costs_the_targets_lifeforce_at_the_prices_of_2026_10_31(source, target, colour):
    assert _cost(resist(source, target)) == pytest.approx(RESISTANCE_COST[target], abs=0.06)


@pytest.mark.parametrize(("source", "target", "colour"), PAIRS)
def test_a_damage_swap_costs_the_lifeforce_and_a_rancour(source, target, colour):
    assert _cost(damage(source, target)) == pytest.approx(DAMAGE_COST[target], abs=0.06)


# --- the exact results ------------------------------------------------------------------------------


def test_a_single_source_gives_one_result_of_probability_one_with_the_tier_kept():
    results = swapped(resist("fire", "cold"), amulet(mod(FIRE_RESIST)))
    assert results == {tuple(line(mod(COLD_RESIST))): Fraction(1)}


def test_the_other_mods_and_their_sides_stay_and_the_new_mod_is_at_its_lowest_values():
    item = amulet(mod(LIFE_1), mod(FIRE_RESIST), mod(GEM), mod(RESIST_3))
    results = swapped(resist("fire", "cold"), item)
    assert results == {tuple(line(mod(LIFE_1), mod(COLD_RESIST), mod(GEM), mod(RESIST_3))): Fraction(1)}
    (_, result), = resist("fire", "cold").outcomes(WORLD, item).results
    assert result.rarity is Rarity.RARE and result.item_level == 84 and not result.corrupted


@pytest.mark.parametrize(
    ("source", "target", "start", "end"),
    [
        ("cold", "fire", COLD_RESIST, FIRE_RESIST),
        ("fire", "cold", FIRE_RESIST, COLD_RESIST),
        ("fire", "lightning", FIRE_RESIST, RESIST_3),  # tier 1 of Lightning is LightningResist3
        ("cold", "lightning", COLD_RESIST, RESIST_3),
        ("lightning", "fire", RESIST_3, FIRE_RESIST),
        ("lightning", "cold", RESIST_3, COLD_RESIST),
        ("fire", "cold", MAX_FIRE, MAX_COLD),
        ("cold", "fire", MAX_COLD, MAX_FIRE),
    ],
)
def test_each_resistance_swap_changes_the_mod_into_the_same_tier_of_the_target(source, target, start, end):
    assert swapped(resist(source, target), amulet(mod(start))) == {tuple(line(mod(end))): Fraction(1)}


@pytest.mark.parametrize(
    ("source", "target", "start", "end"),
    [
        ("fire", "cold", FIRE_DAMAGE_1, COLD_DAMAGE_1),  # tier 2
        ("fire", "cold", FIRE_DAMAGE_2, COLD_DAMAGE_2),  # tier 1
        ("cold", "fire", COLD_DAMAGE_2, FIRE_DAMAGE_2),
        ("fire", "lightning", FIRE_DAMAGE_1, DAMAGE_1),
        ("fire", "lightning", FIRE_DAMAGE_2, DAMAGE_2),
        ("lightning", "fire", DAMAGE_1, FIRE_DAMAGE_1),
        ("lightning", "cold", DAMAGE_2, COLD_DAMAGE_2),
        ("cold", "lightning", COLD_DAMAGE_1, DAMAGE_1),
        ("fire", "cold", FIRE_SPELL, COLD_SPELL),
    ],
)
def test_each_damage_swap_changes_the_mod_into_the_same_tier_of_the_target(source, target, start, end):
    assert swapped(damage(source, target), amulet(mod(start))) == {tuple(line(mod(end))): Fraction(1)}


def test_two_sources_give_one_half_each():
    item = amulet(mod(FIRE_DAMAGE_1), mod(FIRE_SPELL))
    assert swapped(damage("fire", "cold"), item) == {
        tuple(line(mod(COLD_DAMAGE_1), mod(FIRE_SPELL))): Fraction(1, 2),
        tuple(line(mod(FIRE_DAMAGE_1), mod(COLD_SPELL))): Fraction(1, 2),
    }
    both = amulet(mod(FIRE_RESIST), mod(MAX_FIRE))
    assert swapped(resist("fire", "cold"), both) == {
        tuple(line(mod(COLD_RESIST), mod(MAX_FIRE))): Fraction(1, 2),
        tuple(line(mod(FIRE_RESIST), mod(MAX_COLD))): Fraction(1, 2),
    }


def test_each_swap_sees_only_its_own_kind_of_source():
    item = amulet(mod(FIRE_DAMAGE_2), mod(FIRE_SPELL), mod(LIFE_1), mod(FIRE_RESIST), mod(MAX_FIRE))
    results = swapped(resist("fire", "cold"), item)
    assert len(results) == 2 and set(results.values()) == {Fraction(1, 2)}  # the damage mods are no resistance source
    results = swapped(damage("fire", "cold"), item)
    assert results == {
        tuple(line(mod(COLD_DAMAGE_2), mod(FIRE_SPELL), mod(LIFE_1), mod(FIRE_RESIST), mod(MAX_FIRE))): Fraction(1, 2),
        tuple(line(mod(FIRE_DAMAGE_2), mod(COLD_SPELL), mod(LIFE_1), mod(FIRE_RESIST), mod(MAX_FIRE))): Fraction(1, 2),
    }


def test_a_source_whose_target_family_is_on_the_item_is_not_eligible():
    """Cold resistance is held, so Fire Resistance cannot become one; the maximum resistance can."""
    item = amulet(mod(FIRE_RESIST), mod(COLD_RESIST), mod(MAX_FIRE))
    assert swapped(resist("fire", "cold"), item) == {tuple(line(mod(FIRE_RESIST), mod(COLD_RESIST), mod(MAX_COLD))): Fraction(1)}


def test_when_every_source_clashes_the_swap_is_refused():
    with pytest.raises(NotApplicableError, match="item level or shares a family"):
        resist("fire", "cold").outcomes(WORLD, amulet(mod(FIRE_RESIST), mod(COLD_RESIST)))


def test_the_lightning_tiers_of_the_small_pool_decide_which_lightning_mods_can_swap():
    # LightningResist1 is tier 3 and LightningResist2 tier 2: Fire and Cold have a tier 1 only
    for start in (RESIST_1, RESIST_2):
        for target in ("fire", "cold"):
            with pytest.raises(NotApplicableError, match="same tier"):
                resist("lightning", target).outcomes(WORLD, amulet(mod(start)))
    # the other way: the tier-1 fire mod becomes the tier-1 lightning mod, LightningResist3
    assert swapped(resist("fire", "lightning"), amulet(mod(FIRE_RESIST))) == {tuple(line(mod(RESIST_3))): Fraction(1)}


def test_of_the_lightning_mods_only_the_tier_that_has_a_target_is_a_source():
    item = amulet(mod(RESIST_3), mod(DAMAGE_1))  # LightningResist3 is tier 1, AddedLightningDamage1 tier 2
    assert swapped(resist("lightning", "fire"), item) == {tuple(line(mod(FIRE_RESIST), mod(DAMAGE_1))): Fraction(1)}
    assert swapped(damage("lightning", "fire"), item) == {tuple(line(mod(RESIST_3), mod(FIRE_DAMAGE_1))): Fraction(1)}


def test_a_resistance_swap_leaves_the_damage_alone_and_the_reverse():
    with pytest.raises(NotApplicableError):
        resist("lightning", "fire").outcomes(WORLD, amulet(mod(DAMAGE_2)))
    with pytest.raises(NotApplicableError):
        damage("fire", "cold").outcomes(WORLD, amulet(mod(FIRE_RESIST)))
    with pytest.raises(NotApplicableError):
        damage("lightning", "fire").outcomes(WORLD, amulet(mod(GEM)))  # a gem level mod grants no damage stat


def test_the_source_is_chosen_by_the_swap_s_own_element():
    item = amulet(mod(FIRE_RESIST), mod(RESIST_3))
    assert swapped(resist("fire", "cold"), item) == {tuple(line(mod(COLD_RESIST), mod(RESIST_3))): Fraction(1)}
    assert swapped(resist("lightning", "cold"), item) == {tuple(line(mod(FIRE_RESIST), mod(COLD_RESIST))): Fraction(1)}


# --- what the game refuses -------------------------------------------------------------------------


@pytest.mark.parametrize("swap", [resist("fire", "cold"), damage("fire", "cold")])
def test_a_normal_item_is_refused(swap):
    with pytest.raises(NotApplicableError, match="normal"):
        swap.outcomes(WORLD, amulet(rarity=Rarity.NORMAL))


@pytest.mark.parametrize("swap", [resist("fire", "cold"), damage("fire", "cold")])
def test_a_corrupted_item_is_refused(swap):
    with pytest.raises(NotApplicableError, match="corrupted"):
        swap.outcomes(WORLD, amulet(mod(FIRE_RESIST), mod(FIRE_DAMAGE_1), corrupted=True))


def test_an_item_without_a_source_is_refused():
    for swap in (resist("fire", "cold"), damage("fire", "cold")):
        with pytest.raises(NotApplicableError, match="no mod of the item"):
            swap.outcomes(WORLD, amulet(mod(LIFE_1), mod(GEM)))
        with pytest.raises(NotApplicableError):
            swap.outcomes(WORLD, amulet())


def test_a_fractured_source_is_not_a_source():
    with pytest.raises(NotApplicableError):
        resist("fire", "cold").outcomes(WORLD, amulet(mod(FIRE_RESIST, fractured=True)))
    with pytest.raises(NotApplicableError):
        damage("fire", "cold").outcomes(WORLD, amulet(mod(FIRE_DAMAGE_1, fractured=True), mod(FIRE_RESIST)))
    # one fractured and one free source: only the free one is swapped, and the fractured one stays fractured
    item = amulet(mod(FIRE_RESIST, fractured=True), mod(MAX_FIRE))
    assert swapped(resist("fire", "cold"), item) == {tuple(line(mod(FIRE_RESIST, fractured=True), mod(MAX_COLD))): Fraction(1)}


def test_a_crafted_source_is_not_a_source():
    with pytest.raises(NotApplicableError):
        resist("fire", "cold").outcomes(WORLD, amulet(mod(CRAFTED_FIRE, crafted=True)))
    item = amulet(mod(CRAFTED_FIRE, crafted=True), mod(MAX_FIRE))
    assert swapped(resist("fire", "cold"), item) == {tuple(line(mod(CRAFTED_FIRE, crafted=True), mod(MAX_COLD))): Fraction(1)}


def test_a_source_on_a_side_that_cannot_be_changed_is_not_a_source():
    suffixes_locked = amulet(mod(FIRE_RESIST), meta(SCBC))  # SCBC is a prefix and locks the suffixes
    with pytest.raises(NotApplicableError):
        resist("fire", "cold").outcomes(WORLD, suffixes_locked)
    prefixes_locked = amulet(mod(FIRE_DAMAGE_1), meta(PCBC))  # PCBC is a suffix and locks the prefixes
    with pytest.raises(NotApplicableError):
        damage("fire", "cold").outcomes(WORLD, prefixes_locked)


def test_a_lock_protects_its_own_side_only():
    assert swapped(resist("fire", "cold"), amulet(mod(FIRE_RESIST), meta(PCBC))) == {
        tuple(line(mod(COLD_RESIST), meta(PCBC))): Fraction(1)
    }
    assert swapped(damage("fire", "cold"), amulet(mod(FIRE_DAMAGE_2), meta(SCBC))) == {
        tuple(line(mod(COLD_DAMAGE_2), meta(SCBC))): Fraction(1)
    }
    # both sides open to one source and locked to the other
    item = amulet(mod(FIRE_DAMAGE_1), mod(FIRE_RESIST), meta(SCBC))
    assert swapped(damage("fire", "cold"), item) == {tuple(line(mod(COLD_DAMAGE_1), mod(FIRE_RESIST), meta(SCBC))): Fraction(1)}


@pytest.mark.parametrize("blocker", [NO_ATTACK, NO_CASTER])
def test_the_attack_and_caster_metamods_protect_nothing_from_a_swap(blocker):
    item = amulet(mod(FIRE_DAMAGE_1), mod(FIRE_RESIST), meta(blocker))
    assert swapped(damage("fire", "cold"), item) == {tuple(line(mod(COLD_DAMAGE_1), mod(FIRE_RESIST), meta(blocker))): Fraction(1)}
    assert swapped(resist("fire", "cold"), item) == {tuple(line(mod(FIRE_DAMAGE_1), mod(COLD_RESIST), meta(blocker))): Fraction(1)}


@pytest.mark.parametrize(
    ("level", "works"),
    [(1, False), (24, False), (25, True), (26, True), (84, True)],
)
def test_a_target_above_the_item_level_is_refused(level, works):
    """Fire tier 1 to Lightning tier 1, LightningResist3, which needs level 25."""
    item = amulet(mod(FIRE_RESIST), level=level)
    if works:
        assert swapped(resist("fire", "lightning"), item) == {tuple(line(mod(RESIST_3))): Fraction(1)}
    else:
        with pytest.raises(NotApplicableError, match="above the item level"):
            resist("fire", "lightning").outcomes(WORLD, item)


@pytest.mark.parametrize(("level", "works"), [(14, False), (15, True)])
def test_the_cold_damage_that_needs_level_15_is_out_of_reach_below_it(level, works):
    item = amulet(mod(FIRE_DAMAGE_2), level=level)  # Fire's tier 1 needs 13, Cold's needs 15
    if works:
        assert swapped(damage("fire", "cold"), item) == {tuple(line(mod(COLD_DAMAGE_2))): Fraction(1)}
    else:
        with pytest.raises(NotApplicableError, match="above the item level"):
            damage("fire", "cold").outcomes(WORLD, item)


def test_the_item_level_refuses_one_target_and_not_another():
    """At level 24 the swap to Lightning (the target needs 25) is refused while the swap to Cold (the target needs 1) works."""
    item = amulet(mod(FIRE_RESIST), level=24)
    with pytest.raises(NotApplicableError, match="above the item level"):
        resist("fire", "lightning").outcomes(WORLD, item)
    assert swapped(resist("fire", "cold"), item) == {tuple(line(mod(COLD_RESIST))): Fraction(1)}


# --- what the game allows ---------------------------------------------------------------------------


def test_an_influenced_item_takes_a_swap_and_keeps_its_influence():
    item = amulet(mod(FIRE_RESIST), mod(LIFE_1), influences=frozenset({Influence.SHAPER}))
    outcomes = resist("fire", "cold").outcomes(WORLD, item)
    ((chance, result),) = outcomes.results
    assert chance == 1 and held(result) == line(mod(COLD_RESIST), mod(LIFE_1))
    assert result.influences == frozenset({Influence.SHAPER})


def test_a_magic_item_takes_a_swap_and_stays_magic():
    item = amulet(mod(FIRE_RESIST), rarity=Rarity.MAGIC)
    ((chance, result),) = resist("fire", "cold").outcomes(WORLD, item).results
    assert chance == 1 and held(result) == line(mod(COLD_RESIST)) and result.rarity is Rarity.MAGIC
    ((_, result),) = damage("fire", "cold").outcomes(WORLD, amulet(mod(FIRE_DAMAGE_1), rarity=Rarity.MAGIC)).results
    assert held(result) == line(mod(COLD_DAMAGE_1)) and result.rarity is Rarity.MAGIC


def test_an_item_with_another_mod_fractured_takes_a_swap():
    item = amulet(mod(LIFE_1, fractured=True), mod(FIRE_RESIST), mod(FIRE_DAMAGE_1))
    assert swapped(resist("fire", "cold"), item) == {
        tuple(line(mod(LIFE_1, fractured=True), mod(COLD_RESIST), mod(FIRE_DAMAGE_1))): Fraction(1)
    }
    assert swapped(damage("fire", "cold"), item) == {
        tuple(line(mod(LIFE_1, fractured=True), mod(FIRE_RESIST), mod(COLD_DAMAGE_1))): Fraction(1)
    }


def test_the_swap_moves_the_item_s_other_state_not_at_all():
    item = amulet(mod(FIRE_RESIST), influences=frozenset({Influence.SHAPER}), level=80)
    ((_, result),) = resist("fire", "cold").outcomes(WORLD, item).results
    assert (result.base_id, result.item_level, result.corrupted, result.influences) == (AMULET, 80, False, frozenset({Influence.SHAPER}))


# --- the sample ------------------------------------------------------------------------------------


def test_a_thousand_samples_validate_reroll_the_value_inside_the_tier_and_keep_the_tier():
    item = amulet(mod(FIRE_RESIST), mod(LIFE_1))
    outcomes = resist("fire", "cold").outcomes(WORLD, item)
    rng = random.Random(20261101)
    values = Counter()
    for _ in range(1000):
        drawn = outcomes.sample(rng)
        drawn.validate(WORLD)
        cold = next(e for e in drawn.mods if e.mod_id == COLD_RESIST)
        assert cold.tier == 1 and not cold.fractured and not cold.crafted
        assert next(e for e in drawn.mods if e.mod_id == LIFE_1) == mod(LIFE_1)
        assert len(drawn.mods) == 2
        values[cold.values] += 1
    assert set(values) == {(v,) for v in range(6, 12)}  # the range of Cold Resistance tier 1 is 6 to 11
    assert all(count > 100 for count in values.values())  # uniform over six values: about 167 each


def test_the_exact_result_keeps_the_lowest_values_and_the_sample_of_a_damage_swap_rolls_both_stats():
    item = amulet(mod(FIRE_DAMAGE_2))
    ((_, exact),) = damage("fire", "cold").outcomes(WORLD, item).results
    assert held(exact) == line(mod(COLD_DAMAGE_2)) and exact.mods[0].values == (1, 14)
    rng = random.Random(7)
    seen = set()
    for _ in range(300):
        drawn = damage("fire", "cold").outcomes(WORLD, item).sample(rng)
        drawn.validate(WORLD)
        low, high = drawn.mods[0].values
        assert low == 1 and 14 <= high <= 15 and drawn.mods[0].tier == 1  # the stat 1 to 1 and the stat 14 to 15
        seen.add(high)
    assert seen == {14, 15}


def test_with_two_sources_the_sample_picks_each_about_half_the_time():
    item = amulet(mod(FIRE_RESIST), mod(MAX_FIRE))
    outcomes = resist("fire", "cold").outcomes(WORLD, item)
    rng = random.Random(3)
    cold_first = sum(
        any(e.mod_id == COLD_RESIST for e in outcomes.sample(rng).mods) for _ in range(1000)
    )
    assert 450 <= cold_first <= 550  # about 500 of 1000, five standard errors being about 79


# --- the catalog -----------------------------------------------------------------------------------


def _members(name: str, item: Item) -> list:
    return [action for entry in kinds() if entry.name == name for action in entry.members(WORLD, item)]


@pytest.mark.parametrize("name", ["harvest-resistance-swap", "harvest-damage-swap"])
def test_the_swap_kinds_are_not_for_the_planner(name):
    entry = next(entry for entry in kinds() if entry.name == name)
    assert entry.planner is False and entry.why_not
    assert name not in {e.name for e in kinds(planner_only=True)}


def test_the_catalog_lists_the_six_swaps_of_each_kind_for_every_item():
    items = [
        amulet(),
        amulet(rarity=Rarity.NORMAL),
        amulet(mod(LIFE_1), rarity=Rarity.MAGIC),
        amulet(mod(GEM), corrupted=True),
        amulet(mod(FIRE_RESIST), influences=frozenset({Influence.SHAPER})),
        amulet(mod(RESIST_1, fractured=True)),
    ]
    for item in items:
        resistance = _members("harvest-resistance-swap", item)
        damages = _members("harvest-damage-swap", item)
        assert sorted(resistance, key=lambda a: a.label()) == sorted((resist(s, t) for s, t, _ in PAIRS), key=lambda a: a.label())
        assert sorted(damages, key=lambda a: a.label()) == sorted((damage(s, t) for s, t, _ in PAIRS), key=lambda a: a.label())
        assert len(resistance) == len(damages) == 6
    swaps = {a for a in catalog(WORLD, amulet()) if isinstance(a, (HarvestResistanceSwap, HarvestDamageSwap))}
    assert len(swaps) == 12
    assert not {a for a in catalog(WORLD, amulet(), planner_only=True) if isinstance(a, (HarvestResistanceSwap, HarvestDamageSwap))}
