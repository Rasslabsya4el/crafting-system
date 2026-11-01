"""The beast and Harvest crafts in the compressed state on the real 3.29.3.3 dump (ticket #149, ADR-0019, ADR-0030).

`test_abstraction_beasts.py` and `test_abstraction_harvest_b2.py` check layer 1 on small fixture pools; these check it on the real pools. They skip
cleanly when the dump is not cached (CI has it). Layer 1 (ADR-0019): the kernel of a concrete item's compressed state equals the finished items of the
action on that item, compressed one by one and added up exactly (`abstraction_b2_support.check_layer_1`). The closures are small and sampled, so the
file stays quick: a kernel and an oracle call on a real pool cost a fraction of a second.

* the Harvest add and remove crafts on Wrapped Boots (a Dex-Int base) at item level 86: every item the crafts reach from boots that hold a hybrid,
  a fractured mod and (with the metamods modelled) a crafted lock, against a goal of Mana, a resistance, Spell Suppression and Movement Speed;
* the six resistance swaps on those boots with resistances of mixed tiers, on a shield (the base that rolls the maximum resistances) and the six
  damage swaps on a Talisman (its pool holds the added, the percent and the spell damage of the three elements), a target family that is held,
  a target above the item level, and the families a swap tells apart by mod;
* the Talisman fractures, the aspects and the Wild Bristle Matron on a real Talisman, and the side swaps on boots where the beast level 83 and 80
  leave out mods that the item level 86 rolls;
* what the state must hold for them, on the real pools: the tag a Harvest add draws by and the level a beast draws at (the model is wrong without them).
"""

import dataclasses
from collections import Counter
from fractions import Fraction

import pytest
from abstraction_b2_support import check_layer_1, closure, disagrees
from abstraction_support import real_game_data

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    AnnulmentOrb,
    AspectBeast,
    BeastSideSwap,
    HarvestAddRemove,
    HarvestDamageSwap,
    HarvestResistanceSwap,
    NotApplicableError,
    Reads,
    TalismanFracture,
    WildBristleMatron,
)
from crafting_system.actions.beast_mods import wild_bristle_metamods
from crafting_system.actions.beasts import aspect_mod_id
from crafting_system.actions.pool import build_pool
from crafting_system.items import ExplicitMod, Item, Rarity, Side, tier_table

BOOTS = "Metadata/Items/Armours/Boots/BootsDexInt1"  # Wrapped Boots
SHIELD = "Metadata/Items/Armours/Shields/ShieldDexInt1"
TALISMAN = "Metadata/Items/Amulets/Talismans/Talisman1_1"  # Black Maw Talisman
LEVEL = 86
ELEMENTS = ("fire", "cold", "lightning")
PAIRS = tuple((source, target) for source in ELEMENTS for target in ELEMENTS if source != target)
LOCK = "DexMasterItemGenerationCannotChangeSuffixes"  # a crafted prefix that locks the suffixes


@pytest.fixture(scope="module")
def data():
    return real_game_data()


class Kit:
    """A base at an item level on the real data: mods by family and tier, rolled at their lowest values, and items built of them."""

    def __init__(self, data, base_id: str, level: int = LEVEL):
        self.data, self.base_id, self.level = data, base_id, level
        self.tiers = tier_table(data, base_id)
        empty = Item.build(data, base_id=base_id, item_level=level, rarity=Rarity.RARE, mods=())
        self.pool_ids = {entry.mod.id for family in build_pool(data, empty) for entry in family.mods}  # the mods the item can roll at its level

    def mod(self, family: str, tier: int = 1) -> str:
        """The id of the mod of `family` that has table tier `tier` on this base (1 is the best); there must be exactly one."""
        found = [
            mod.id
            for mod in self.data.mods.values()
            if mod.families == (family,) and mod.id in self.pool_ids and self.tiers.get(mod.id) == tier
        ]
        assert len(found) == 1, (family, tier, found)
        return found[0]

    def roll(self, mod_id: str, tier: int | None = None, **flags) -> ExplicitMod:
        mod = self.data.mods[mod_id]
        return ExplicitMod(mod_id, tier or self.tiers.get(mod_id, 1), tuple(min(s.min, s.max) for s in mod.stats), **flags)

    def of(self, *entries, **fields) -> Item:
        """A rare item of the base; an entry is a mod id, a `(family, tier)` pair, or a ready `ExplicitMod`."""
        mods = []
        for entry in entries:
            if isinstance(entry, ExplicitMod):
                mods.append(entry)
            elif isinstance(entry, tuple):
                mods.append(self.roll(self.mod(*entry)))
            else:
                mods.append(self.roll(entry))
        return Item.build(self.data, base_id=self.base_id, item_level=self.level, rarity=Rarity.RARE, mods=tuple(mods), **fields)


def spread(items, count: int):
    """`count` items spread over the list, the first and the last included."""
    if len(items) <= count:
        return list(items)
    step = (len(items) - 1) / (count - 1)
    return [items[round(index * step)] for index in range(count)]


def check_all(ability, data, items, actions) -> Counter:
    """Layer 1 of every action on every item; how many times each action applied."""
    applied: Counter = Counter()
    for item in items:
        for action in actions:
            applied[action] += check_layer_1(ability, data, item, action)
    return applied


# --- the Harvest add and remove crafts on boots ---------------------------------------------------------------------------------------


CRAFTS = tuple(HarvestAddRemove(craft) for craft in ("fire", "cold", "life", "defence", "speed", "chaos"))


@pytest.fixture(scope="module")
def boots(data):
    return Kit(data, BOOTS)


def boots_goal(boots: Kit) -> Goal:
    data = boots.data
    return Goal(
        (
            Wanted(family_ids(data, "IncreasedMana")),
            Wanted(family_ids(data, "FireResistance", "ColdResistance", "LightningResistance"), min_tier=2),
            Wanted(family_ids(data, "ChanceToSuppressSpells"), min_tier=1),
            Wanted(family_ids(data, "MovementVelocity")),
        )
    )


def harvest_starts(boots: Kit) -> dict[str, Item]:
    return {
        "route": boots.of(("IncreasedMana", 1), ("FireResistance", 2), ("ChanceToSuppressSpells", 1)),
        "mixed_tiers": boots.of(("IncreasedLife", 3), ("ColdResistance", 1), ("MovementVelocity", 2), ("LightningResistance", 4)),
        "hybrids": boots.of("LocalBaseEvasionRatingAndLife2", "LocalIncreasedEvasionAndEnergyShieldAndStunRecovery2", ("ChaosResistance", 3)),
        "fractured": boots.of(boots.roll(boots.mod("IncreasedMana", 1), fractured=True), ("FireResistance", 1), ("StunRecovery", 2)),
    }


def test_layer_1_of_the_harvest_add_and_remove_crafts_on_real_boots(boots):
    ability = Abstraction(boots.data, boots_goal(boots), BOOTS, LEVEL, CRAFTS)
    starts = harvest_starts(boots)
    items = closure(boots.data, starts.values(), CRAFTS, limit=40)
    assert len(items) > 100
    checked = [*starts.values(), *spread(items, 30)]
    applied = check_all(ability, boots.data, checked, CRAFTS)
    assert all(applied[craft] for craft in CRAFTS), {craft.craft: applied[craft] for craft in CRAFTS}
    assert any(item.fractured_mods for item in items)  # the fractured mod stays through the crafts


def test_layer_1_of_the_harvest_crafts_on_boots_with_a_crafted_lock_modelled(boots):
    ability = Abstraction(boots.data, boots_goal(boots), BOOTS, LEVEL, CRAFTS, metamods=True)
    locked = boots.of(("IncreasedMana", 1), ("FireResistance", 2), ("ChanceToSuppressSpells", 1), boots.roll(LOCK, crafted=True))
    others = [item for name, item in harvest_starts(boots).items() if name != "hybrids"]
    items = closure(boots.data, [locked, *others], CRAFTS, limit=30)
    checked = [locked, *others, *spread(items, 10)]
    applied = check_all(ability, boots.data, checked, CRAFTS)
    assert all(applied[craft] for craft in CRAFTS), {craft.craft: applied[craft] for craft in CRAFTS}
    # the lock keeps the suffixes the item holds: no craft removes one (the removal takes the Mana or the lock), and Fire has no mod to add (the family is held)
    suffixes = {e.mod_id for e in locked.mods if boots.data.mods[e.mod_id].generation_type == "suffix"}
    for craft in CRAFTS:
        took = check_layer_1(ability, boots.data, locked, craft)
        assert took == (craft.craft != "fire"), craft.craft
        if took:
            assert all(suffixes <= {e.mod_id for e in result.mods} for _, result in craft.outcomes(boots.data, locked).results)
        else:
            with pytest.raises(NotApplicableError):
                craft.outcomes(boots.data, locked)


# --- the resistance swaps ------------------------------------------------------------------------------------------------------------


RESISTANCE_SWAPS = tuple(HarvestResistanceSwap(source, target) for source, target in PAIRS)
DAMAGE_SWAPS = tuple(HarvestDamageSwap(source, target) for source, target in PAIRS)


def family_ids(data, *names: str) -> frozenset[str]:
    return frozenset(m.id for m in data.mods.values() if m.domain == "item" and m.families in {(name,) for name in names})


def swap_goal(data) -> Goal:
    """The tiers matter to a swap, so the goal asks for different tiers of the three elements."""
    return Goal(
        (
            Wanted(family_ids(data, "FireResistance")),
            Wanted(family_ids(data, "ColdResistance"), min_tier=2),
            Wanted(family_ids(data, "LightningResistance"), min_tier=1),
            Wanted(family_ids(data, "IncreasedMana")),
        )
    )


def test_layer_1_of_the_six_resistance_swaps_on_real_boots_of_mixed_tiers(boots):
    ability = Abstraction(boots.data, swap_goal(boots.data), BOOTS, LEVEL, RESISTANCE_SWAPS, metamods=True)
    starts = {
        "three_resists": boots.of(("FireResistance", 1), ("ColdResistance", 4), ("LightningResistance", 8)),  # every target is held: every swap is refused
        "fire_and_mana": boots.of(("FireResistance", 3), ("IncreasedMana", 1), ("ChanceToSuppressSpells", 1)),
        "cold_and_lightning": boots.of(("ColdResistance", 2), ("LightningResistance", 5), ("IncreasedMana", 4)),
        "lightning_alone": boots.of(("LightningResistance", 1), ("ChaosResistance", 3), ("IncreasedLife", 2)),
        "fractured_source": boots.of(boots.roll(boots.mod("FireResistance", 2), fractured=True), ("ColdResistance", 3), ("IncreasedMana", 2)),
        "locked_suffixes": boots.of(("FireResistance", 2), ("IncreasedMana", 1), boots.roll(LOCK, crafted=True)),
    }
    actions = (*RESISTANCE_SWAPS, AnnulmentOrb())
    items = closure(boots.data, starts.values(), actions, limit=60)
    assert len(items) > 40
    checked = [*starts.values(), *spread(items, 30)]
    applied = check_all(ability, boots.data, checked, RESISTANCE_SWAPS)
    assert all(applied[swap] for swap in RESISTANCE_SWAPS), {swap.label(): applied[swap] for swap in RESISTANCE_SWAPS}
    # the item that holds all three elements refuses every swap, as the kernel does; the locked suffixes refuse the swap of a suffix
    assert not any(check_layer_1(ability, boots.data, starts["three_resists"], swap) for swap in RESISTANCE_SWAPS)
    assert not check_layer_1(ability, boots.data, starts["locked_suffixes"], HarvestResistanceSwap("fire", "cold"))
    assert not check_layer_1(ability, boots.data, starts["fractured_source"], HarvestResistanceSwap("fire", "lightning"))


@pytest.fixture(scope="module")
def shield(data):
    return Kit(data, SHIELD)


def test_layer_1_of_the_resistance_swaps_on_a_real_shield_that_rolls_the_maximum_resistances(shield):
    ability = Abstraction(shield.data, swap_goal(shield.data), SHIELD, LEVEL, RESISTANCE_SWAPS, metamods=True)
    starts = {
        "maximum_and_plain": shield.of(("MaximumFireResist", 1), ("FireResistance", 3), ("IncreasedLife", 4)),  # a swap of Fire has two sources
        "maximum_cold": shield.of(("MaximumColdResist", 2), ("LightningResistance", 2), ("FireResistance", 1)),
        "maximum_lightning_held": shield.of(("MaximumLightningResistance", 3), ("MaximumFireResist", 3), ("ColdResistance", 1)),
        "plain_only": shield.of(("ColdResistance", 5), ("IncreasedLife", 1)),
    }
    actions = (*RESISTANCE_SWAPS, AnnulmentOrb())
    items = closure(shield.data, starts.values(), actions, limit=50)
    checked = [*starts.values(), *spread(items, 20)]
    applied = check_all(ability, shield.data, checked, RESISTANCE_SWAPS)
    assert all(applied[swap] for swap in RESISTANCE_SWAPS), {swap.label(): applied[swap] for swap in RESISTANCE_SWAPS}
    # the swap of Fire on the first start has two sources, each a half: the maximum and the plain one become their Cold twins at their tiers
    kernel = ability.kernel(ability.compress(starts["maximum_and_plain"]), HarvestResistanceSwap("fire", "cold"))
    assert sorted(kernel.values()) == [Fraction(1, 2), Fraction(1, 2)]
    results = HarvestResistanceSwap("fire", "cold").outcomes(shield.data, starts["maximum_and_plain"]).results
    assert {tuple(sorted(e.mod_id for e in r.mods if "Cold" in e.mod_id)) for _, r in results} == {(shield.mod("MaximumColdResist", 1),), (shield.mod("ColdResistance", 3),)}


# --- the damage swaps ----------------------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def talisman(data):
    return Kit(data, TALISMAN)


def metamod(data, family: str) -> str:
    """The id of the metamod the Wild Bristle Matron adds for `family` (the five of the bench: the locks, the Attack and Caster filters, the multimod)."""
    return next(mod.id for mod in wild_bristle_metamods(data) if mod.families == (family,))


def damage_goal(data) -> Goal:
    return Goal(
        (
            Wanted(family_ids(data, "FireDamage")),
            Wanted(family_ids(data, "ColdDamage"), min_tier=2),
            Wanted(family_ids(data, "FireDamagePercentage")),
            Wanted(family_ids(data, "LightningDamagePercentage"), min_tier=1),
            Wanted(family_ids(data, "IncreasedLife")),
        )
    )


def test_layer_1_of_the_six_damage_swaps_on_a_real_talisman_of_mixed_tiers(talisman):
    data = talisman.data
    lock = talisman.roll(metamod(data, "ItemGenerationCannotChangeSuffixes"), crafted=True)
    ability = Abstraction(data, damage_goal(data), TALISMAN, LEVEL, DAMAGE_SWAPS, metamods=True)
    starts = {
        "added_damage": talisman.of(("FireDamage", 1), ("ColdDamage", 4), ("LightningDamagePercentage", 2), ("IncreasedLife", 3)),
        "percent_damage": talisman.of(("FireDamagePercentage", 3), ("ColdDamagePercentage", 2), ("IncreasedLife", 2), ("FireResistance", 2)),
        "every_target_held": talisman.of(("FireDamage", 2), ("ColdDamage", 2), ("LightningDamage", 2)),  # the added damage of the other elements is held: every added damage swap is refused
        "added_and_percent": talisman.of(("LightningDamage", 3), ("ColdDamagePercentage", 1), ("FireDamagePercentage", 4), ("IncreasedLife", 4)),
        "fractured_source": talisman.of(talisman.roll(talisman.mod("FireDamage", 2), fractured=True), ("ColdDamagePercentage", 3), ("IncreasedLife", 1)),
        "locked_suffixes": talisman.of(("FireDamage", 3), ("FireDamagePercentage", 2), ("IncreasedLife", 2), lock),
    }
    actions = (*DAMAGE_SWAPS, AnnulmentOrb())
    items = closure(data, starts.values(), actions, limit=70)
    assert len(items) > 50
    checked = [*starts.values(), *spread(items, 30)]
    applied = check_all(ability, data, checked, DAMAGE_SWAPS)
    assert all(applied[swap] for swap in DAMAGE_SWAPS), {swap.label(): applied[swap] for swap in DAMAGE_SWAPS}
    # every target held: every swap is refused, by the item and by the kernel
    assert not any(check_layer_1(ability, data, starts["every_target_held"], swap) for swap in DAMAGE_SWAPS)
    # the Cold added damage is held, so the added Fire damage stays; the percent Fire damage (another family, another mod) is the only source
    both = talisman.of(("FireDamage", 3), ("ColdDamage", 3), ("FireDamagePercentage", 3))
    assert check_layer_1(ability, data, both, HarvestDamageSwap("fire", "cold"))
    (only,) = ability.kernel(ability.compress(both), HarvestDamageSwap("fire", "cold"))
    assert {slot.kind for slot in only.slots} == {slot.kind for slot in ability.compress(both).slots} - {f"${talisman.mod('FireDamagePercentage', 3)}"} | {f"${talisman.mod('ColdDamagePercentage', 3)}"}
    # the locked suffixes keep the percent damage: the added damage (a prefix) is the only source of the swap
    locked = starts["locked_suffixes"]
    assert check_layer_1(ability, data, locked, HarvestDamageSwap("fire", "cold"))
    (after,) = ability.kernel(ability.compress(locked), HarvestDamageSwap("fire", "cold"))
    assert f"${talisman.mod('FireDamagePercentage', 2)}" in {slot.kind for slot in after.slots}
    # a fractured source is not swapped
    assert not check_layer_1(ability, data, starts["fractured_source"], HarvestDamageSwap("fire", "lightning"))


def test_layer_1_of_the_damage_swaps_at_an_item_level_below_the_required_level_of_a_target(data):
    low = Kit(data, TALISMAN, 12)  # Added Fire Damage tier 8 needs level 12, the Cold tier 8 twin needs level 13
    ability = Abstraction(data, damage_goal(data), TALISMAN, 12, DAMAGE_SWAPS)
    starts = [low.of("AddedFireDamage2", "IncreasedLife1"), low.of("AddedColdDamage1", "FireDamagePercent1", "IncreasedLife2")]
    items = closure(data, starts, (*DAMAGE_SWAPS, AnnulmentOrb()), limit=40)
    took = sum(check_layer_1(ability, data, item, swap) for item in spread(items, 20) for swap in DAMAGE_SWAPS)
    assert took > 5
    refused = HarvestDamageSwap("fire", "cold")
    assert not check_layer_1(ability, data, starts[0], refused)
    with pytest.raises(NotApplicableError, match="above the item level"):
        ability.kernel(ability.compress(starts[0]), refused)


# --- the beast crafts on a Talisman ----------------------------------------------------------------------------------------------------


FRACTURES = (TalismanFracture(1), TalismanFracture(2))
ASPECTS = tuple(AspectBeast(aspect, level) for aspect in ("avian", "cat", "crab", "spider") for level in (20, 30))


def talisman_goal(data) -> Goal:
    return Goal(
        (
            Wanted(family_ids(data, "IncreasedLife")),
            Wanted(family_ids(data, "IncreasedEnergyShield"), min_tier=3),
            Wanted(family_ids(data, "FireResistance", "ColdResistance", "LightningResistance"), min_tier=2),
            Wanted(frozenset({aspect_mod_id("cat", 30)})),
        )
    )


def talisman_starts(talisman: Kit) -> dict[str, Item]:
    lock = talisman.roll(metamod(talisman.data, "ItemGenerationCannotChangePrefixes"), crafted=True)
    return {
        "four": talisman.of(("IncreasedLife", 3), ("IncreasedEnergyShield", 2), ("ColdResistance", 4), ("Strength", 5)),
        "six": talisman.of(
            ("IncreasedLife", 2), ("IncreasedEnergyShield", 4), ("FireDamage", 3), ("ColdResistance", 1), ("LightningResistance", 5), ("CriticalStrikeMultiplier", 3)
        ),
        "six_other": talisman.of(
            ("IncreasedLife", 5), ("IncreasedEnergyShield", 1), ("LightningDamage", 6), ("FireResistance", 4), ("Strength", 2), ("Intelligence", 6)
        ),
        "five": talisman.of(("IncreasedLife", 3), ("IncreasedEnergyShield", 2), ("FireResistance", 2), ("IncreasedCastSpeed", 2), ("Dexterity", 3)),
        "fractured": talisman.of(
            ("IncreasedLife", 3), talisman.roll(talisman.mod("IncreasedEnergyShield", 2), fractured=True), ("ColdResistance", 2), ("ManaRegeneration", 3)
        ),
        "lock_on_prefixes": talisman.of(("IncreasedLife", 3), ("IncreasedEnergyShield", 5), ("FireResistance", 3), ("Intelligence", 2), lock),
    }


def test_layer_1_of_the_talisman_fractures_on_real_talismans_of_four_five_and_six_mods(talisman):
    data, actions = talisman.data, (*FRACTURES, AnnulmentOrb())
    ability = Abstraction(data, talisman_goal(data), TALISMAN, LEVEL, actions, metamods=True)
    starts = talisman_starts(talisman)
    items = closure(data, starts.values(), actions, limit=80)
    assert len(items) > 60
    checked = [*starts.values(), *spread(items, 24)]
    applied = check_all(ability, data, checked, actions)
    assert all(applied[action] for action in actions), applied
    assert any(item.fractured_mods for item in items)  # the Annulment runs on fractured items too
    # a fracture of one mod of six: six results; of two: fifteen; the fractured mods are a family type in the state, and an item with one refuses both
    assert len(FRACTURES[0].outcomes(data, starts["six"]).results) == 6 and len(FRACTURES[1].outcomes(data, starts["six"]).results) == 15
    assert not any(check_layer_1(ability, data, starts["fractured"], fracture) for fracture in FRACTURES)
    assert not check_layer_1(ability, data, starts["four"], FRACTURES[1]) and check_layer_1(ability, data, starts["four"], FRACTURES[0])


def test_layer_1_of_the_aspects_on_real_talismans(talisman):
    data, actions = talisman.data, (*ASPECTS, AnnulmentOrb())
    ability = Abstraction(data, talisman_goal(data), TALISMAN, LEVEL, actions, metamods=True)
    starts = talisman_starts(talisman)
    items = closure(data, starts.values(), actions, limit=80)
    checked = [*starts.values(), *spread(items, 20)]
    applied = check_all(ability, data, checked, actions)
    assert all(applied[action] for action in actions), {a.label(): applied[a] for a in actions}
    assert any(aspect_mod_id("cat", 30) in {e.mod_id for e in item.mods} for item in items)
    # one aspect blocks the other (the family GrantedSkill), and the state of the item that holds one says so
    (with_cat,) = ability.kernel(ability.compress(talisman.of(("IncreasedLife", 3), ("ColdResistance", 2))), AspectBeast("cat", 30))
    assert with_cat.status[3].name == "PASSING"  # the goal's fourth leaf is the level 30 Cat aspect
    with pytest.raises(NotApplicableError, match="shares a family"):
        ability.kernel(with_cat, AspectBeast("avian", 20))


def test_layer_1_of_the_wild_bristle_matron_on_a_real_talisman(talisman):
    data, actions = talisman.data, (WildBristleMatron(), AnnulmentOrb())
    ability = Abstraction(data, talisman_goal(data), TALISMAN, LEVEL, actions)
    assert ability.models_metamods  # the Matron adds a metamod, so the state models the locks and the filters
    starts = talisman_starts(talisman)
    items = closure(data, starts.values(), actions, limit=60)
    checked = [*starts.values(), *spread(items, 24)]
    applied = check_all(ability, data, checked, actions)
    assert all(applied[action] for action in actions), applied
    assert any(any(e.crafted for e in item.mods) for item in items)
    # one state per metamod the item allows, each with the same chance
    kernel = ability.kernel(ability.compress(starts["four"]), WildBristleMatron())
    assert sum(kernel.values()) == 1 and len(kernel) == len(WildBristleMatron().outcomes(data, starts["four"]).results)


def test_layer_1_of_the_wild_bristle_matron_on_real_boots(boots):
    data, actions = boots.data, (WildBristleMatron(), AnnulmentOrb(), HarvestAddRemove("life"))
    ability = Abstraction(data, boots_goal(boots), BOOTS, LEVEL, actions)
    items = closure(data, harvest_starts(boots).values(), actions, limit=50)
    checked = spread(items, 20)
    applied = check_all(ability, data, [*harvest_starts(boots).values(), *checked], actions)
    assert all(applied[action] for action in actions), applied


# --- the side swaps: the pool at the level of the beast --------------------------------------------------------------------------------


SIDE_SWAPS = tuple(BeastSideSwap(side, beast_level=level) for level in (83, 80) for side in (Side.PREFIX, Side.SUFFIX))


def beast_goal(data) -> Goal:
    """Mana, Spell Suppression and Fire Resistance: Movement Speed, the Cold and Lightning Resistances and the others are junk to it."""
    return Goal(
        (
            Wanted(family_ids(data, "IncreasedMana")),
            Wanted(family_ids(data, "ChanceToSuppressSpells"), min_tier=1),
            Wanted(family_ids(data, "FireResistance")),
        )
    )


def side_swap_starts(boots: Kit) -> dict[str, Item]:
    return {
        "movement_speed": boots.of(("MovementVelocity", 3), ("IncreasedMana", 1), ("FireResistance", 2), ("ChanceToSuppressSpells", 1)),
        "stun_recovery_hybrid": boots.of(("DefencesPercentAndStunRecovery", 3), ("IncreasedLife", 3), ("ColdResistance", 3), ("LifeRegeneration", 2)),
        "fractured": boots.of(boots.roll(boots.mod("IncreasedMana", 1), fractured=True), ("LifeRegeneration", 4), ("ChaosResistance", 2)),
        "prefixes_full": boots.of(("IncreasedMana", 2), ("IncreasedLife", 4), ("MovementVelocity", 1), ("FireResistance", 3), ("ColdResistance", 4)),
        "locked_suffixes": boots.of(("IncreasedMana", 1), ("FireResistance", 2), ("LifeRegeneration", 3), boots.roll(LOCK, crafted=True)),
    }


def test_the_beast_level_leaves_out_mods_that_the_item_level_rolls(boots):
    """Some real mods need a level between 81 and 86 (Mana tier 1 needs 81, the tier 1 resistances 84): the beast of level 83 and 80 does not draw them."""
    item = side_swap_starts(boots)["movement_speed"]
    drawn = {
        level: {
            side: {e.mod_id for _, r in BeastSideSwap(side, beast_level=level).outcomes(boots.data, item).results for e in r.mods} - {e.mod_id for e in item.mods}
            for side in (Side.PREFIX, Side.SUFFIX)
        }
        for level in (86, 83, 80)
    }
    mana_1, cold_1 = boots.mod("IncreasedMana", 1), boots.mod("ColdResistance", 1)
    assert boots.data.mods[cold_1].required_level == 84 and cold_1 in drawn[86][Side.SUFFIX]
    assert cold_1 not in drawn[83][Side.SUFFIX] and cold_1 not in drawn[80][Side.SUFFIX]
    assert boots.data.mods[mana_1].required_level == 81
    other_mana = boots.of(("MovementVelocity", 3), ("FireResistance", 2), ("ChanceToSuppressSpells", 1))  # without Mana on it the prefix draw could roll it
    mana_drawn = {
        level: mana_1 in {e.mod_id for _, r in BeastSideSwap(Side.PREFIX, beast_level=level).outcomes(boots.data, other_mana).results for e in r.mods}
        for level in (86, 83, 80)
    }
    assert mana_drawn == {86: True, 83: True, 80: False}


def test_layer_1_of_the_side_swaps_of_the_beasts_of_level_83_and_80_on_real_boots(boots):
    data, actions = boots.data, (*SIDE_SWAPS, AnnulmentOrb())
    ability = Abstraction(data, beast_goal(data), BOOTS, LEVEL, actions, metamods=True)
    starts = side_swap_starts(boots)
    items = closure(data, starts.values(), actions, limit=25)
    checked = [*starts.values(), *spread(items, 10)]
    applied = check_all(ability, data, checked, actions)
    assert all(applied[action] for action in actions), {a.label(): applied[a] for a in actions}
    # the lock on the suffixes keeps them: the prefix swap adds a prefix and removes nothing; a full prefix side refuses it
    locked = starts["locked_suffixes"]
    for _, result in BeastSideSwap(Side.PREFIX).outcomes(data, locked).results:
        assert len(result.mods) == len(locked.mods) + 1
    assert not check_layer_1(ability, data, starts["prefixes_full"], BeastSideSwap(Side.PREFIX))
    assert check_layer_1(ability, data, starts["prefixes_full"], BeastSideSwap(Side.SUFFIX))


def test_the_family_types_carry_the_weight_at_the_level_of_the_beast_on_the_real_pool(boots):
    # Movement Speed and the Evasion-Energy Shield-Stun Recovery hybrid have six prefixes of weight 1000 at the item level 86; at the beast's 83 the first has five and
    # the second six. Life Regeneration and the Cold Resistance have eight suffixes at 86; at 83 eight and seven. The goal asks for none of them, so only the level
    # of the beast tells the two of a pair apart.
    data = boots.data
    swaps = tuple(BeastSideSwap(side, beast_level=83) for side in (Side.PREFIX, Side.SUFFIX))

    @dataclasses.dataclass(frozen=True)
    class BlindToTheLevel(BeastSideSwap):
        def reads(self, data):
            return Reads(junk=True, families=frozenset(), pool_weight=True)

    blind = tuple(BlindToTheLevel(side, beast_level=83) for side in (Side.PREFIX, Side.SUFFIX))
    pairs = [
        (boots.of(("MovementVelocity", 3), ("ColdResistance", 3), ("IncreasedMana", 2)), boots.of(("DefencesPercentAndStunRecovery", 3), ("LifeRegeneration", 3), ("IncreasedMana", 2))),
        (boots.of(("IncreasedLife", 3), ("LifeRegeneration", 3), ("ChanceToSuppressSpells", 2)), boots.of(("IncreasedLife", 3), ("ColdResistance", 3), ("ChanceToSuppressSpells", 2))),
    ]
    aware = Abstraction(data, beast_goal(data), BOOTS, LEVEL, swaps, metamods=True)
    unaware = Abstraction(data, beast_goal(data), BOOTS, LEVEL, blind, metamods=True)
    for one, other in pairs:
        assert unaware.compress(one) == unaware.compress(other)  # alike at the item's level, and nothing in the goal tells them apart
        assert aware.compress(one) != aware.compress(other)  # alike at 86, different at the beast's 83
        for item in (one, other):
            for swap in swaps:
                check_layer_1(aware, data, item, swap)
    assert sum(disagrees(unaware, data, item, swap) for pair in pairs for item in pair for swap in blind) > 0


# --- what the state must hold for the Harvest crafts, on the real pool ---------------------------------------------------------------------


def test_the_family_types_carry_the_tag_a_harvest_add_draws_by_on_the_real_pool(boots):
    # Fire and Cold Resistance have the same eight mods of weight 1000, and the goal gives them the same: only their tags tell them apart. A Fire craft draws a
    # Fire mod, so an item that holds the Fire Resistance has none left to draw, and one that holds the Cold Resistance has one. The model is exact with the tag.
    data = boots.data

    @dataclasses.dataclass(frozen=True)
    class BlindToTheTag(HarvestAddRemove):
        def reads(self, data):
            return Reads(junk=True, families=frozenset(), pool_weight=True)

    crafts = (HarvestAddRemove("fire"), HarvestAddRemove("cold"))
    blind = (BlindToTheTag("fire"), BlindToTheTag("cold"))
    fire = boots.of(("FireResistance", 3), ("IncreasedMana", 2), ("IncreasedLife", 3))
    cold = boots.of(("ColdResistance", 3), ("IncreasedMana", 2), ("IncreasedLife", 3))
    aware = Abstraction(data, boots_goal(boots), BOOTS, LEVEL, crafts)
    unaware = Abstraction(data, boots_goal(boots), BOOTS, LEVEL, blind)
    assert unaware.compress(fire) == unaware.compress(cold) and aware.compress(fire) != aware.compress(cold)
    assert sum(disagrees(unaware, data, item, craft) for item in (fire, cold) for craft in blind) > 0
    # the craft of the element the item does not hold applies, and the aware kernel is exact for it (the other craft has no mod to add and is refused by both)
    assert all(check_layer_1(aware, data, item, craft) for item in (fire, cold) for craft in crafts if (item is cold) != (craft.craft == "cold"))
    assert not any(check_layer_1(aware, data, item, craft) for item in (fire, cold) for craft in crafts if (item is cold) == (craft.craft == "cold"))


def test_a_swap_tells_apart_by_mod_the_families_it_looks_inside_on_the_real_pool(boots):
    swap = HarvestResistanceSwap("fire", "cold")
    reads = swap.reads(boots.data)
    families = {boots.data.mods[boots.mod(name, 1)].families[0] for name in ("FireResistance", "ColdResistance")}
    assert reads.by_mod == reads.families and reads.junk and not reads.pool_weight
    assert reads.by_mod >= families | {"MaximumFireResist", "MaximumColdResist"}  # the plain and the maximum resistance of the two elements (the Lightning ones are not this swap's)
    assert "LightningResistance" not in reads.by_mod and "IncreasedLife" not in reads.by_mod
    # a swap and an add together: the junk of the swap's families is told apart by mod, the rest by family type
    ability = Abstraction(boots.data, boots_goal(boots), BOOTS, LEVEL, (swap, HarvestAddRemove("life")))
    state = ability.compress(boots.of(("FireResistance", 3), ("IncreasedLife", 3), ("StunRecovery", 2)))
    by_mod = {slot.kind for slot in state.slots if slot.kind.startswith("$")}
    assert by_mod == {f"${boots.mod('FireResistance', 3)}"}
