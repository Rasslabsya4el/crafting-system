"""The influence crafts in the compressed state on the real 3.29.3.3 dump (ticket #155, ADR-0019, ADR-0030).

`test_abstraction_dominance.py` checks layer 1 on a small fixture pool; these check it on the real pool of Spiked Gloves (`GlovesStr1`) at item level 86, with the
committed Elevated mapping (`data/elevated.json`). They skip cleanly when the dump is not cached (CI has it). Layer 1 (ADR-0019): the kernel of a concrete
item's compressed state equals the finished items of the action on that item, compressed one by one and added up exactly
(`abstraction_b2_support.check_layer_1`). The Awakener's Orb is not here: it rerolls the rest of the item as a Chaos Orb does, over a pool of about sixty
families told apart one by one, which is a long run and not a different kind of check (the fixture test runs it).

* the real data holds ordinary and influence mods in one family (Increased Attack Speed on gloves: ordinary tiers, Elder tiers, and Elder tiers of the
  attack-and-cast-speed mod), so a family cannot say which mod a slot is;
* the Orb of Dominance (and an Annulment, which brings items it does not reach alone) on every item they reach from Elder and Shaper-Elder gloves that hold top-tier
  mods with an Elevated version, tier 2 mods, an Elder mod of the mixed family, an ordinary mod of it, and ordinary mods;
* the influenced Exalted Orbs and the beast recipes on the same kind of items, one application each, with the Orb of Dominance in the model (the kinds of a drawn
  influence mod are then mods).
"""

import pytest
from abstraction_b2_support import check_layer_1, closure
from abstraction_support import real_game_data

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import AnnulmentOrb, BeastInfluenceRecipe, InfluencedExaltedOrb, OrbOfDominance, tiers_of
from crafting_system.actions.pool import influence_spawn_test
from crafting_system.data.elevated import is_elevated, load_elevated
from crafting_system.items import ExplicitMod, Influence, Item, Rarity

GLOVES = "Metadata/Items/Armours/Gloves/GlovesStr1"
LEVEL = 86
SHAPER, ELDER = Influence.SHAPER, Influence.ELDER
SPEED_FAMILY = "IncreasedAttackSpeed"  # ordinary tiers, Elder tiers, and the Elder attack-and-cast-speed tiers
SPEED_ORDINARY = "IncreasedAttackSpeed2"  # an ordinary suffix of the family (level 11)
SPEED_ELDER_2, SPEED_ELDER_3 = "IncreasedAttackSpeedUber2_", "IncreasedAttackSpeedUber3"  # Elder; 3 is tier 1 and has an Elevated version
PROJECTILE_2, PROJECTILE_3 = "ProjectileSpeedUber2", "ProjectileSpeedUber3_"  # Elder prefixes; 3 is tier 1 and has an Elevated version
ACCURACY_3 = "IncreasedAccuracySupportedUber3"  # an Elder suffix, tier 1, with an Elevated version
BLOCK_1 = "AdditionalBlockChanceUber1"  # an Elder suffix of tier 2
BLIND_3 = "BlindOnHitSupportedUber3"  # a Shaper suffix, tier 1, with an Elevated version


@pytest.fixture(scope="module")
def data():
    return real_game_data()


@pytest.fixture(scope="module")
def mapping(data):
    found = load_elevated().for_data(data)
    if not found:
        pytest.skip("the Elevated mapping was not made for this export")
    return found


def gloves(data, *entries, influences=()) -> Item:
    """Gloves that hold the mods `entries` (ids), each at the tier it has among the mods of these influences."""
    tiers = tiers_of(data, Item.build(data, base_id=GLOVES, item_level=LEVEL, rarity=Rarity.RARE, influences=frozenset(influences)))
    mods = tuple(ExplicitMod(mod_id, tiers[mod_id], tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats)) for mod_id in entries)
    return Item.build(data, base_id=GLOVES, item_level=LEVEL, rarity=Rarity.RARE, mods=mods, influences=frozenset(influences))


def goal_of(data, mapping) -> Goal:
    speed = frozenset(mod.id for mod in data.mods.values() if mod.families == (SPEED_FAMILY,))
    return Goal(
        (
            Wanted(frozenset({PROJECTILE_3, mapping[PROJECTILE_3]})),
            Wanted(frozenset({ACCURACY_3, mapping[ACCURACY_3]})),
            Wanted(speed | {mapping[SPEED_ELDER_3]}, min_tier=1),
        )
    )


def test_the_mixed_family_holds_ordinary_and_elder_mods_in_the_real_data(data):
    is_elder = influence_spawn_test(data, gloves(data, influences={ELDER}))
    members = [mod for mod in data.mods.values() if mod.families == (SPEED_FAMILY,)]
    assert any(is_elder(mod) for mod in members) and any(not is_elder(mod) for mod in members)
    assert not is_elder(data.mods[SPEED_ORDINARY]) and is_elder(data.mods[SPEED_ELDER_2])


def test_layer_1_of_the_orb_of_dominance_on_the_real_pool(data, mapping):
    starts = [
        gloves(data, SPEED_ELDER_2, PROJECTILE_3, BLOCK_1, influences={ELDER}),
        gloves(data, SPEED_ORDINARY, PROJECTILE_2, ACCURACY_3, influences={ELDER}),
        gloves(data, PROJECTILE_3, BLIND_3, SPEED_ELDER_3, influences={SHAPER, ELDER}),
    ]
    actions = (OrbOfDominance(), AnnulmentOrb())
    found = Abstraction(data, goal_of(data, mapping), GLOVES, LEVEL, actions)
    assert found.tells_influenced
    items = closure(data, starts, actions, limit=80)
    applied = {action: 0 for action in actions}
    for held in items:
        for action in actions:
            applied[action] += check_layer_1(found, data, held, action)
    assert all(applied.values()), applied
    assert any(is_elevated(data.mods[entry.mod_id]) for held in items for entry in held.mods)  # a top-tier mod became its Elevated version
    assert any(SPEED_ELDER_3 in {entry.mod_id for entry in held.mods} for held in items)  # and the Elder mod of the mixed family went up a tier


def test_layer_1_of_the_orbs_and_the_recipes_that_draw_an_influence_mod_with_dominance_in_the_model(data, mapping):
    actions = (OrbOfDominance(), *(InfluencedExaltedOrb(influence) for influence in (SHAPER, ELDER)), BeastInfluenceRecipe(SHAPER), BeastInfluenceRecipe(ELDER))
    found = Abstraction(data, goal_of(data, mapping), GLOVES, LEVEL, actions)
    starts = [
        gloves(data, SPEED_ELDER_2, PROJECTILE_3, influences={ELDER}),  # the recipe of Elder applies, the orbs do not
        gloves(data, SPEED_ORDINARY, PROJECTILE_2, influences={ELDER}),  # an ordinary mod of the mixed family beside an Elder one
        gloves(data, SPEED_ORDINARY),  # the orbs apply
    ]
    applied = {action: 0 for action in actions}
    for start in starts:
        for action in actions:
            applied[action] += check_layer_1(found, data, start, action)
    assert applied[actions[1]] and applied[actions[2]] and applied[actions[4]]
