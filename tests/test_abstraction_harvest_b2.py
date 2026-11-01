"""The Harvest add and remove crafts and the Harvest swaps in the compressed state (ticket #149, ADR-0030, ADR-0009).

* layer 1 (ADR-0019): for every concrete item that the crafts reach from several starts, and every craft, the kernel of the item's state equals
  the finished items of the craft on the item, compressed one by one and added up exactly (`abstraction_b2_support.check_layer_1`). The add and
  remove crafts run on the hand-tagged small amulet pool with the lock and tag metamods (`harvest_augment_support`), the swaps on the
  `WORLD` of the swap tests (tiers, a Cold damage tier that needs more level than Fire's, maximum resistances, a spell damage pair, a crafted
  fire resistance, the lock metamods);
* what the state must hold for them: the tier of a swap's source mod, the tag a Harvest add draws by (the family types of the state carry it,
  and the tests show the model is wrong without it), and the families a swapped mod would clash with;
* what the state cannot hold: a roll limit on a mod that a craft adds at a roll of its own.
"""

import dataclasses
from fractions import Fraction

import pytest
from abstraction_b2_support import check_layer_1, closure, disagrees, real_graph
from abstraction_pool import COLD_RESIST, DAMAGE_1, DAMAGE_2, FIRE_RESIST, GEM, LEVEL, LIFE_1, LIVES, MANA_1, MANA_2, RESISTS, RESIST_1, RESIST_2, RESIST_3
from harvest_augment_support import CRAFTS, META_DATA, NO_ATTACK, NO_CASTER, PCBC, amulet as tagged_amulet, lowest
from items_support import AMULET
from test_actions_harvest_swap import (
    COLD_DAMAGE_1,
    COLD_DAMAGE_2,
    FIRE_DAMAGE_1,
    FIRE_DAMAGE_2,
    FIRE_SPELL,
    MAX_COLD,
    MAX_FIRE,
    PAIRS,
    SCBC,
    WORLD,
    amulet as world_amulet,
    meta,
    mod as world_mod,
)

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    ActionError,
    AnnulmentOrb,
    ExaltedOrb,
    HarvestAddRemove,
    HarvestDamageSwap,
    HarvestResistanceSwap,
    NotApplicableError,
    OutOfScopeError,
    Reads,
)
from crafting_system.items import tier_table

F = Fraction
TAGGED_TIERS = tier_table(META_DATA, AMULET)
ADD_REMOVE_GOALS = {
    "gem_resist_life": Goal((Wanted(frozenset({GEM})), Wanted(RESISTS), Wanted(LIVES))),
    "mana_and_fire": Goal((Wanted(frozenset({MANA_1, MANA_2})), Wanted(frozenset({FIRE_RESIST, COLD_RESIST})))),
}
ALL_ADD_REMOVE = tuple(HarvestAddRemove(craft) for craft in CRAFTS)


def tagged(mod_id: str, **flags):
    return lowest(mod_id, data=META_DATA, tier=TAGGED_TIERS.get(mod_id, 1), **flags)


def add_remove_starts():
    return {
        "two": tagged_amulet(tagged(RESIST_2), tagged(LIFE_1)),
        "four": tagged_amulet(tagged(RESIST_2), tagged(LIFE_1), tagged(DAMAGE_1), tagged(MANA_1)),
        "fractured": tagged_amulet(tagged(RESIST_2, fractured=True), tagged(LIFE_1), tagged(MANA_1)),
        "lock_on_suffixes": tagged_amulet(tagged(RESIST_2), tagged(LIFE_1), tagged(PCBC, crafted=True)),
        "no_attack": tagged_amulet(tagged(RESIST_2), tagged(LIFE_1), tagged(NO_ATTACK, crafted=True)),
        "no_caster": tagged_amulet(tagged(DAMAGE_1), tagged(MANA_1), tagged(NO_CASTER, crafted=True)),
        "fire_and_cold": tagged_amulet(tagged(FIRE_RESIST), tagged(COLD_RESIST), tagged(LIFE_1)),
    }


def ability_for(actions, goal, *, data=META_DATA, level=LEVEL, **options) -> Abstraction:
    return Abstraction(data, goal, AMULET, level, actions, metamods=True, **options)


# --- layer 1: the add and remove crafts -------------------------------------------------------------------------------


@pytest.mark.parametrize("goal", ADD_REMOVE_GOALS)
def test_layer_1_of_every_add_and_remove_craft_on_every_item_the_crafts_reach(goal):
    ability = ability_for(ALL_ADD_REMOVE, ADD_REMOVE_GOALS[goal])
    items = closure(META_DATA, add_remove_starts().values(), ALL_ADD_REMOVE, limit=250)
    assert len(items) > 200
    applied = {craft: 0 for craft in ALL_ADD_REMOVE}
    for item in items:
        for craft in ALL_ADD_REMOVE:
            applied[craft] += check_layer_1(ability, META_DATA, item, craft)
    assert all(applied.values()), applied  # every craft applied somewhere: none was only ever compared as a refusal


def test_layer_1_of_the_add_and_remove_crafts_reached_through_an_annulment_too():
    actions = (HarvestAddRemove("lightning"), HarvestAddRemove("life"), AnnulmentOrb())
    ability = ability_for(actions, ADD_REMOVE_GOALS["gem_resist_life"])
    items = closure(META_DATA, add_remove_starts().values(), actions, limit=250)
    assert sum(check_layer_1(ability, META_DATA, item, action) for item in items for action in actions) > 500


def test_the_family_types_of_the_junk_carry_the_tag_a_harvest_add_draws_by():
    # Fire and Cold Resistance weigh the same and give the goal nothing, so only their tags tell them apart: an add that did not read the tag
    # would see them as one family type and answer for the wrong one. The test model is exact with the tag and wrong without it.

    @dataclasses.dataclass(frozen=True)
    class BlindToTheTag(HarvestAddRemove):
        def reads(self, data):
            return Reads(junk=True, families=frozenset(), pool_weight=True)

    goal = ADD_REMOVE_GOALS["gem_resist_life"]
    blind = tuple(BlindToTheTag(craft) for craft in CRAFTS)
    starts = [add_remove_starts()[name] for name in ("two", "four", "fire_and_cold")]
    items = closure(META_DATA, starts, blind, limit=120)
    ability = ability_for(blind, goal)
    assert sum(disagrees(ability, META_DATA, item, craft) for item in items for craft in blind) > 0
    aware = ability_for(ALL_ADD_REMOVE, goal)
    for item in items:
        for craft in ALL_ADD_REMOVE:
            check_layer_1(aware, META_DATA, item, craft)


def test_the_state_of_a_harvest_add_is_smaller_than_one_that_tells_every_family_apart():
    # the same crafts declared the old way (`Reads()`: every family by name) keep a state per family, the types of the new declaration keep one per type
    @dataclasses.dataclass(frozen=True)
    class ByName(HarvestAddRemove):
        def reads(self, data):
            return Reads()

    goal = ADD_REMOVE_GOALS["gem_resist_life"]
    crafts = tuple(HarvestAddRemove(craft) for craft in ("lightning", "life"))
    named = tuple(ByName(craft) for craft in ("lightning", "life"))
    items = closure(META_DATA, add_remove_starts().values(), crafts, limit=250)
    pooled, by_name = ability_for(crafts, goal), ability_for(named, goal)
    states_pooled = {pooled.compress(item) for item in items}
    states_named = {by_name.compress(item) for item in items}
    assert len(states_pooled) < len(states_named)
    for item in items[::7]:  # the smaller model is as exact
        for craft in crafts:
            check_layer_1(pooled, META_DATA, item, craft)


def test_a_craft_leaves_the_item_for_a_state_that_holds_the_new_mod_as_a_slot_of_its_family_type():
    ability = ability_for((HarvestAddRemove("life"),), ADD_REMOVE_GOALS["gem_resist_life"])
    start = tagged_amulet(tagged(RESIST_2), tagged(DAMAGE_1))
    kernel = ability.kernel(ability.compress(start), HarvestAddRemove("life"))
    assert sum(kernel.values()) == 1
    assert all(len(state.slots) == 2 for state in kernel)  # one in, one out
    assert any(state.status != ability.compress(start).status for state in kernel)  # a Life mod comes on the item: the goal's third leaf


@pytest.mark.parametrize("craft", ["fire", "attack"])
def test_a_refusal_of_a_craft_is_the_refusal_of_the_kernel(craft):
    ability = ability_for(ALL_ADD_REMOVE, ADD_REMOVE_GOALS["gem_resist_life"])
    full_fractured = tagged_amulet(*(tagged(mod_id, fractured=True) for mod_id in (RESIST_2, LIFE_1, DAMAGE_1)))
    assert not check_layer_1(ability, META_DATA, full_fractured, HarvestAddRemove(craft))  # nothing to remove: refused by both
    with pytest.raises(NotApplicableError):
        ability.kernel(ability.compress(full_fractured), HarvestAddRemove(craft))


def test_a_roll_limit_on_a_mod_a_craft_adds_is_refused_not_answered():
    # the added mod is drawn at a roll of its own, and the compressed result of a fixed-result mod has no roll law (the kernel's `_guard_roll`)
    goal = Goal((Wanted(frozenset({RESIST_2, RESIST_3}), min_roll=(15,)),))
    ability = ability_for((HarvestAddRemove("lightning"),), goal)
    start = tagged_amulet(tagged(LIFE_1), tagged(DAMAGE_1))
    with pytest.raises(OutOfScopeError, match="roll limit"):
        ability.kernel(ability.compress(start), HarvestAddRemove("lightning"))


# --- layer 1: the swaps ------------------------------------------------------------------------------------------------


SWAPS = tuple(HarvestResistanceSwap(source, target) for source, target, _ in PAIRS) + tuple(HarvestDamageSwap(source, target) for source, target, _ in PAIRS)
SWAP_GOAL = Goal(
    (
        Wanted(frozenset({RESIST_3, RESIST_2})),
        Wanted(frozenset({FIRE_RESIST})),
        Wanted(frozenset({COLD_DAMAGE_2, FIRE_DAMAGE_2}), min_tier=1),
        Wanted(frozenset({LIFE_1})),
    )
)


def swap_starts(level: int = 84):
    """Items with several tiers of one family, a family that would clash with a swap's target, a lock, a crafted mod and a fractured source."""
    items = {
        "tier_1_resist": (RESIST_3, LIFE_1),
        "tier_2_resist": (RESIST_2, LIFE_1),
        "tier_3_resist_and_cold": (RESIST_1, COLD_RESIST),
        "fire_and_tier_1": (FIRE_RESIST, RESIST_3),
        "damage": (DAMAGE_2, GEM),
        "damage_pair": (DAMAGE_1, FIRE_DAMAGE_1),
        "cold_damage": (COLD_DAMAGE_2, LIFE_1),
        "fire_damage": (FIRE_DAMAGE_2, LIFE_1),
        "spell": (FIRE_SPELL, LIFE_1),
        "maximum": (MAX_FIRE, RESIST_2),
        "both_maxima": (MAX_FIRE, MAX_COLD),
    }
    found = {name: world_amulet(*(world_mod(mod_id) for mod_id in ids), level=level) for name, ids in items.items()}
    found["lock_suffixes"] = world_amulet(world_mod(DAMAGE_2), world_mod(FIRE_RESIST), meta(SCBC), level=level)
    found["fractured_source"] = world_amulet(world_mod(RESIST_2, fractured=True), world_mod(FIRE_RESIST), level=level)
    return found


def test_layer_1_of_every_swap_on_every_item_the_swaps_reach():
    ability = ability_for(SWAPS, SWAP_GOAL, data=WORLD)
    starts = {name: item for name, item in swap_starts().items()}
    items = closure(WORLD, starts.values(), (*SWAPS, AnnulmentOrb(), ExaltedOrb()), limit=300)  # the orbs bring items the swaps alone do not reach
    assert len(items) > 150
    applied = {swap: 0 for swap in SWAPS}
    for item in items:
        for swap in SWAPS:
            applied[swap] += check_layer_1(ability, WORLD, item, swap)
    assert all(applied.values()), {swap.label(): n for swap, n in applied.items() if not n}


def test_layer_1_of_every_swap_at_an_item_level_below_the_required_level_of_a_target():
    # COLD_DAMAGE_2 needs level 15: a Fire damage tier 1 (level 13) cannot become it on a level 14 item, whatever else the item holds
    ability = ability_for(SWAPS, SWAP_GOAL, data=WORLD, level=14)
    starts = [world_amulet(world_mod(FIRE_DAMAGE_2), world_mod(LIFE_1), level=14), world_amulet(world_mod(DAMAGE_2), world_mod(FIRE_RESIST), level=14)]
    items = closure(WORLD, starts, (*SWAPS, AnnulmentOrb(), ExaltedOrb()), limit=150)
    took = sum(check_layer_1(ability, WORLD, item, swap) for item in items for swap in SWAPS)
    assert took > 50
    refused = HarvestDamageSwap("fire", "cold")
    assert not check_layer_1(ability, WORLD, starts[0], refused)
    with pytest.raises(NotApplicableError, match="above the item level"):
        ability.kernel(ability.compress(starts[0]), refused)


def test_a_swap_keeps_the_tier_so_the_state_of_a_source_tells_its_tier():
    ability = ability_for(SWAPS, SWAP_GOAL, data=WORLD)
    tier_1, tier_2, tier_3 = (ability.compress(world_amulet(world_mod(mod_id), world_mod(LIFE_1))) for mod_id in (RESIST_3, RESIST_2, RESIST_1))
    assert len({tier_1, tier_2, tier_3}) == 3  # three tiers of one family: three states, whatever the goal asks
    fire = HarvestResistanceSwap("lightning", "fire")
    assert dict(ability.kernel(tier_1, fire)) == {ability.compress(world_amulet(world_mod(FIRE_RESIST), world_mod(LIFE_1))): 1}  # tier 1 has a Fire twin
    for refused in (tier_2, tier_3):  # a family of the small pool has one Fire tier, the first
        with pytest.raises(NotApplicableError, match="same tier"):
            ability.kernel(refused, fire)


def test_a_swap_is_refused_when_the_target_family_is_held_and_not_when_a_third_family_is():
    ability = ability_for(SWAPS, SWAP_GOAL, data=WORLD)
    fire_and_cold = world_amulet(world_mod(FIRE_RESIST), world_mod(COLD_RESIST))
    assert not check_layer_1(ability, WORLD, fire_and_cold, HarvestResistanceSwap("fire", "cold"))  # the cold family is held
    with pytest.raises(NotApplicableError):
        ability.kernel(ability.compress(fire_and_cold), HarvestResistanceSwap("fire", "cold"))
    with_life = world_amulet(world_mod(FIRE_RESIST), world_mod(LIFE_1))
    assert check_layer_1(ability, WORLD, with_life, HarvestResistanceSwap("fire", "cold"))


def test_only_the_families_a_swap_looks_inside_are_told_apart_by_mod():
    swap = HarvestResistanceSwap("fire", "cold")
    reads = swap.reads(WORLD)
    assert reads.by_mod == reads.families and reads.junk and not reads.pool_weight
    families = {WORLD.mods[mod_id].families[0] for mod_id in (FIRE_RESIST, COLD_RESIST, MAX_FIRE, MAX_COLD)}
    assert reads.by_mod >= families  # the plain and the maximum resistance of the two elements (the lightning ones are not this swap's)
    assert WORLD.mods[RESIST_3].families[0] not in reads.by_mod and WORLD.mods[LIFE_1].families[0] not in reads.by_mod
    # a swap and an add together: the junk of the swap's families is by mod, the rest by family type
    ability = ability_for((swap, HarvestAddRemove("life")), SWAP_GOAL, data=WORLD)
    state = ability.compress(world_amulet(world_mod(FIRE_RESIST), world_mod(LIFE_1)))
    kinds = {slot.kind for slot in state.slots}
    assert f"${FIRE_RESIST}" in kinds and not any(kind.startswith("$") for kind in kinds - {f"${FIRE_RESIST}"})


def test_a_roll_limit_on_a_mod_a_swap_makes_is_refused_not_answered():
    goal = Goal((Wanted(frozenset({COLD_RESIST}), min_roll=(7,)),))
    ability = ability_for(SWAPS, goal, data=WORLD)
    item = world_amulet(world_mod(FIRE_RESIST), world_mod(LIFE_1))
    with pytest.raises(OutOfScopeError, match="roll limit"):
        ability.kernel(ability.compress(item), HarvestResistanceSwap("fire", "cold"))


# --- the pilot count ---------------------------------------------------------------------------------------------------


def test_the_pilot_count_of_the_harvest_crafts_is_the_graph_the_kernels_make():
    actions = (HarvestAddRemove("lightning"), HarvestAddRemove("life"), AnnulmentOrb())
    ability = ability_for(actions, ADD_REMOVE_GOALS["gem_resist_life"], data=META_DATA)
    start = ability.compress(tagged_amulet(tagged(RESIST_2), tagged(LIFE_1)))
    pilot = ability.estimate([start], actions)
    seen, transitions = real_graph(ability, [start], actions)
    assert (pilot.states, pilot.transitions) == (len(seen), transitions) and pilot.states > 10


def test_the_pilot_count_of_the_swaps_is_the_graph_the_kernels_make():
    actions = (HarvestResistanceSwap("lightning", "fire"), HarvestResistanceSwap("fire", "cold"), HarvestDamageSwap("fire", "cold"), AnnulmentOrb())
    ability = ability_for(actions, SWAP_GOAL, data=WORLD)
    start = ability.compress(world_amulet(world_mod(RESIST_3), world_mod(DAMAGE_2), world_mod(LIFE_1)))
    pilot = ability.estimate([start], actions)
    seen, transitions = real_graph(ability, [start], actions)
    assert (pilot.states, pilot.transitions) == (len(seen), transitions) and pilot.states > 10
