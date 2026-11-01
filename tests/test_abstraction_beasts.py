"""The beast crafts in the compressed state (ticket #149, ADR-0030, ADR-0009): the Talisman fractures, the aspects, the Wild Bristle Matron and the side swaps.

The data is the small pool of the beast tests (`beast_mods_support.SMALL`: six prefixes, six suffixes, the five metamods and a bench craft, an attack
mod and a caster mod) with the test Talisman base and the eight aspect suffixes of `beasts_support`.

* layer 1 (ADR-0019): for every concrete item that the beast crafts (and an Annulment and an Exalted Orb, which bring items they do not reach alone)
  reach from several starts, and every craft, the kernel of the item's state equals the finished items of the craft on the item, compressed one by one
  and added up exactly (`abstraction_b2_support.check_layer_1`);
* the fracture made in the middle of a route (#69's): the two mods of a Talisman recipe are held fractured, two junk mods of one family type that are
  fractured give one state, and the fractured items are the starts of the next crafts;
* the side swap draws at the level of the beast, not of the item: the family types carry the weight at the beast's level, and the tests show the model is
  wrong without it;
* what the state cannot hold: a roll limit on a mod that a craft adds.
"""

import dataclasses
from fractions import Fraction

import beast_mods_support as bm
import pytest
from abstraction_b2_support import check_layer_1, closure, disagrees, real_graph
from beasts_support import ASPECT_IDS, TALISMAN, beast_data

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    AnnulmentOrb,
    AspectBeast,
    BeastSideSwap,
    ExaltedOrb,
    NotApplicableError,
    OutOfScopeError,
    Reads,
    TalismanFracture,
    WildBristleMatron,
)
from crafting_system.items import ExplicitMod, Item, Rarity, Side, tier_table

DATA = beast_data(data=bm.SMALL)
LEVEL = 86
TIERS = tier_table(DATA, TALISMAN)
CAT_30, AVIAN_20 = ASPECT_IDS["cat", 30], ASPECT_IDS["avian", 20]
GOAL = Goal((Wanted(frozenset({bm.LIFE1, bm.LIFE2})), Wanted(frozenset({bm.FIRE, bm.COLD})), Wanted(frozenset({CAT_30}))))
ASPECTS = tuple(AspectBeast(aspect, level) for aspect in ("avian", "cat", "crab", "spider") for level in (20, 30))
SIDE_SWAPS = (BeastSideSwap(Side.PREFIX), BeastSideSwap(Side.SUFFIX), BeastSideSwap(Side.PREFIX, beast_level=80), BeastSideSwap(Side.SUFFIX, beast_level=80))
FRACTURES = (TalismanFracture(1), TalismanFracture(2))
MOVERS = (AnnulmentOrb(), ExaltedOrb())


def rolled(mod_id: str, data=DATA, **flags) -> ExplicitMod:
    mod = data.mods[mod_id]
    return ExplicitMod(mod_id, tier_table(data, TALISMAN).get(mod_id, 1), tuple(min(s.min, s.max) for s in mod.stats), **flags)


def talisman(*mod_ids: str, data=DATA, rarity: Rarity = Rarity.RARE, fractured=(), crafted=(), **fields) -> Item:
    mods = tuple(rolled(m, data, fractured=m in fractured, crafted=m in crafted or m in bm.METAMODS or m == bm.CRAFTED) for m in mod_ids)
    return Item.build(data, base_id=TALISMAN, item_level=LEVEL, rarity=rarity, mods=mods, **fields)


def ability_for(actions, goal=GOAL, data=DATA, **options) -> Abstraction:
    return Abstraction(data, goal, TALISMAN, LEVEL, actions, **options)


def starts(*, metamods: bool = True) -> dict[str, Item]:
    """The starts; without `metamods` the ones that hold a lock or a tag metamod are left out (a model without them refuses such an item)."""
    found = {
        "six": talisman(bm.LIFE1, bm.ES1, bm.LIGHTNING1, bm.FIRE, bm.COLD, bm.CHAOS1),
        "four": talisman(bm.LIFE1, bm.ES1, bm.FIRE, bm.COLD),
        "five": talisman(bm.LIFE1, bm.ES1, bm.FIRE, bm.COLD, bm.LEECH),
        "attack_and_caster": talisman(bm.LIGHTNING1, bm.LEECH, bm.LPCT, bm.ES1),
        "fractured": talisman(bm.LIFE1, bm.ES1, bm.FIRE, bm.COLD, fractured=(bm.ES1,)),
        "lock_on_suffixes": talisman(bm.LIFE1, bm.ES1, bm.FIRE, bm.SCBC),
        "lock_on_prefixes": talisman(bm.LIFE1, bm.FIRE, bm.COLD, bm.PCBC),
        "crafted": talisman(bm.LIFE1, bm.FIRE, bm.COLD, bm.CRAFTED),
    }
    return found if metamods else {name: item for name, item in found.items() if name not in ("lock_on_suffixes", "lock_on_prefixes")}


# --- layer 1 -------------------------------------------------------------------------------------------------------------


def test_layer_1_of_the_talisman_fractures_on_every_item_they_and_the_orbs_reach():
    actions = (*FRACTURES, *MOVERS)
    ability = ability_for(actions, metamods=True)
    items = closure(DATA, starts().values(), actions, limit=500)
    assert len(items) > 300
    applied = {action: 0 for action in actions}
    for item in items:
        for action in actions:
            applied[action] += check_layer_1(ability, DATA, item, action)
    assert all(applied.values()), applied
    assert any(item.fractured_mods for item in items)  # the crafts of the second step run on fractured items too


def test_layer_1_of_the_aspects_on_every_item_they_and_the_orbs_reach():
    actions = (*ASPECTS, *MOVERS)
    ability = ability_for(actions, metamods=True)
    items = closure(DATA, starts().values(), actions, limit=400)
    applied = {action: 0 for action in actions}
    for item in items:
        for action in actions:
            applied[action] += check_layer_1(ability, DATA, item, action)
    assert all(applied.values()), applied
    assert any(CAT_30 in {e.mod_id for e in item.mods} for item in items)


def test_layer_1_of_the_wild_bristle_matron_on_every_item_it_and_the_orbs_reach():
    actions = (WildBristleMatron(), *MOVERS)
    ability = ability_for(actions)
    assert ability.models_metamods  # the Matron adds a metamod, so the state models the lock and the tag filters
    items = closure(DATA, starts().values(), actions, limit=500)
    assert len(items) > 300
    took = sum(check_layer_1(ability, DATA, item, WildBristleMatron()) for item in items)
    assert took > 100
    assert sum(check_layer_1(ability, DATA, item, action) for item in items for action in MOVERS) > 300
    assert any(any(e.crafted for e in item.mods) for item in items)


def test_layer_1_of_the_side_swaps_on_every_item_they_and_the_orbs_reach():
    actions = (*SIDE_SWAPS, *MOVERS)
    ability = ability_for(actions, metamods=True)
    items = closure(DATA, starts().values(), actions, limit=400)
    assert len(items) > 250
    applied = {action: 0 for action in actions}
    for item in items:
        for action in actions:
            applied[action] += check_layer_1(ability, DATA, item, action)
    assert all(applied.values()), applied


def test_layer_1_of_every_beast_craft_together():
    actions = (*FRACTURES, ASPECTS[3], ASPECTS[5], WildBristleMatron(), *SIDE_SWAPS[:2], *MOVERS)
    ability = ability_for(actions)
    items = closure(DATA, starts().values(), actions, limit=300)
    applied = {action: 0 for action in actions}
    for item in items:
        for action in actions:
            applied[action] += check_layer_1(ability, DATA, item, action)
    assert all(applied.values()), applied


# --- the Talisman fractures: a fracture made in the middle of a route ------------------------------------------------------


def test_a_talisman_fracture_holds_the_fractured_mods_as_a_family_type_like_the_fracturing_orb():
    ability = ability_for(FRACTURES)
    start = talisman(bm.LIFE1, bm.ES1, bm.FIRE, bm.COLD)
    kernel = ability.kernel(ability.compress(start), TalismanFracture(1))
    assert sum(kernel.values()) == 1
    # Fire and Cold Resistance weigh the same and give the goal the same: fractured, they are the same state
    assert len(kernel) < 4
    assert all(len(state.fractured) == 1 and len(state.slots) == 3 for state in kernel)
    two = ability_for(FRACTURES).kernel(ability.compress(talisman(bm.LIFE1, bm.ES1, bm.LIGHTNING1, bm.FIRE, bm.COLD, bm.CHAOS1)), TalismanFracture(2))
    assert all(len(state.fractured) == 2 and len(state.slots) == 4 for state in two)
    assert sum(two.values()) == 1 and len(two) < 15  # fifteen pairs, fewer states: pairs of alike mods meet


def test_two_junk_mods_of_one_family_type_that_are_fractured_make_one_state():
    ability = ability_for(FRACTURES)
    state_of = ability.compress
    fire_and_cold = state_of(talisman(bm.LIFE1, bm.ES1, bm.FIRE, bm.COLD, fractured=(bm.FIRE, bm.COLD)))
    cold_and_fire = state_of(talisman(bm.LIFE1, bm.ES1, bm.COLD, bm.FIRE, fractured=(bm.COLD, bm.FIRE)))
    assert fire_and_cold == cold_and_fire
    kernel = ability.kernel(state_of(talisman(bm.LIFE1, bm.ES1, bm.FIRE, bm.COLD, bm.LIGHTNING1, bm.CHAOS1)), TalismanFracture(2))
    assert state_of(talisman(bm.LIFE1, bm.ES1, bm.LIGHTNING1, bm.CHAOS1, bm.FIRE, bm.COLD, fractured=(bm.FIRE, bm.COLD))) in kernel


def test_a_talisman_fracture_is_refused_by_the_state_of_an_item_it_refuses():
    ability = ability_for(FRACTURES)
    refused = {  # the item and the crafts that refuse it
        "three_mods": (talisman(bm.LIFE1, bm.ES1, bm.FIRE), FRACTURES),
        "five_mods": (talisman(bm.LIFE1, bm.ES1, bm.FIRE, bm.COLD, bm.CHAOS1), FRACTURES[1:]),
        "fractured": (talisman(bm.LIFE1, bm.ES1, bm.FIRE, bm.COLD, fractured=(bm.LIFE1,)), FRACTURES),
        "magic": (talisman(bm.LIFE1, rarity=Rarity.MAGIC), FRACTURES),
    }
    for name, (item, crafts) in refused.items():
        for action in crafts:
            assert not check_layer_1(ability, DATA, item, action), (name, action.count)
    assert check_layer_1(ability, DATA, talisman(bm.LIFE1, bm.ES1, bm.FIRE, bm.COLD, bm.CHAOS1), FRACTURES[0])  # five mods are enough for one


# --- the aspects -----------------------------------------------------------------------------------------------------------


def test_an_aspect_is_a_slot_of_its_own_family_and_one_aspect_blocks_the_others():
    ability = ability_for(ASPECTS)
    start = talisman(bm.LIFE1, bm.FIRE)
    (after,) = ability.kernel(ability.compress(start), AspectBeast("cat", 30))
    assert after.status[2].name == "PASSING"  # the goal asks for the level 30 Cat aspect
    kinds = {slot.kind for slot in after.slots}
    assert "GrantedSkill" in kinds
    with pytest.raises(NotApplicableError, match="shares a family"):
        ability.kernel(after, AspectBeast("avian", 20))
    assert ability.kernel(ability.compress(start), AspectBeast("avian", 20))  # the item without one takes any


def test_an_aspect_needs_an_open_suffix_and_a_rare_item():
    ability = ability_for(ASPECTS)
    full = talisman(bm.LIFE1, bm.FIRE, bm.COLD, bm.CHAOS1)
    assert not check_layer_1(ability, DATA, full, AspectBeast("cat", 20))
    assert check_layer_1(ability, DATA, talisman(bm.LIFE1, bm.FIRE, bm.COLD), AspectBeast("cat", 20))


def test_a_roll_limit_on_an_aspect_is_refused_not_answered():
    goal = Goal((Wanted(frozenset({CAT_30}), min_roll=(30,)),))
    ability = ability_for(ASPECTS, goal)
    with pytest.raises(OutOfScopeError, match="roll limit"):
        ability.kernel(ability.compress(talisman(bm.LIFE1, bm.FIRE)), AspectBeast("cat", 30))


# --- the Wild Bristle Matron -----------------------------------------------------------------------------------------------


def test_the_matron_is_uniform_among_the_metamods_the_state_allows():
    ability = ability_for((WildBristleMatron(),))
    state = ability.compress(talisman(bm.LIFE1, bm.ES1, bm.FIRE))
    kernel = ability.kernel(state, WildBristleMatron())
    assert sum(kernel.values()) == 1
    assert len(kernel) == 5 and set(kernel.values()) == {Fraction(1, 5)}  # the five metamods, alike
    full_suffixes = ability.kernel(ability.compress(talisman(bm.LIFE1, bm.FIRE, bm.COLD, bm.CHAOS1)), WildBristleMatron())
    assert len(full_suffixes) == 1  # only the metamod on the prefix side is allowed: Suffixes Cannot Be Changed
    assert not check_layer_1(ability, DATA, talisman(bm.LIFE1, bm.FIRE, bm.PCBC), WildBristleMatron())  # one crafted mod held: the limit
    assert check_layer_1(ability, DATA, talisman(bm.LIFE1, bm.FIRE, bm.PCBC, bm.MULTI), WildBristleMatron())  # the multimod lifts it to three


# --- the side swaps: the pool at the level of the beast --------------------------------------------------------------------


def leveled_data():
    """The beast data where Cold Resistance needs level 84 (Fire's is 1): alike at the item's level 86, not at a beast of level 80."""
    mods = dict(DATA.mods)
    mods[bm.COLD] = dataclasses.replace(mods[bm.COLD], required_level=84)
    return dataclasses.replace(DATA, mods=mods)


def test_the_family_types_carry_the_weight_at_the_level_of_the_beast():
    data = leveled_data()
    goal = Goal((Wanted(frozenset({bm.LIFE1, bm.LIFE2})),))

    @dataclasses.dataclass(frozen=True)
    class BlindToTheLevel(BeastSideSwap):
        def reads(self, data):
            return Reads(junk=True, families=frozenset(), pool_weight=True)

    swaps = (BeastSideSwap(Side.PREFIX, beast_level=80), BeastSideSwap(Side.SUFFIX, beast_level=80), AnnulmentOrb())
    blind = (BlindToTheLevel(Side.PREFIX, beast_level=80), BlindToTheLevel(Side.SUFFIX, beast_level=80), AnnulmentOrb())
    items_start = [
        talisman(bm.LIFE1, bm.ES1, bm.FIRE, bm.CHAOS1, data=data),
        talisman(bm.LIFE1, bm.ES1, bm.COLD, bm.CHAOS1, data=data),
        talisman(bm.LIFE1, bm.FIRE, bm.LEECH, data=data),
        talisman(bm.LIFE1, bm.COLD, bm.LEECH, data=data),
    ]
    items = closure(data, items_start, swaps, limit=250)
    aware = ability_for(swaps, goal, data, metamods=True)
    assert sum(check_layer_1(aware, data, item, action) for item in items for action in swaps) > 50
    wrong = ability_for(blind, goal, data, metamods=True)
    assert sum(disagrees(wrong, data, item, action) for item in items for action in blind) > 0


def test_a_side_swap_removes_nothing_from_a_locked_side_and_never_a_fractured_mod():
    ability = ability_for(SIDE_SWAPS, metamods=True)
    locked = talisman(bm.LIFE1, bm.FIRE, bm.COLD, bm.SCBC)
    kernel = ability.kernel(ability.compress(locked), BeastSideSwap(Side.PREFIX))  # adds a prefix, would remove a suffix: the lock keeps them
    assert all(len(state.slots) == 5 for state in kernel)
    assert check_layer_1(ability, DATA, locked, BeastSideSwap(Side.PREFIX))
    only_fractured = talisman(bm.LIFE1, bm.FIRE, bm.COLD, fractured=(bm.FIRE, bm.COLD))
    assert not check_layer_1(ability, DATA, only_fractured, BeastSideSwap(Side.PREFIX))  # no suffix to remove
    with pytest.raises(NotApplicableError):
        ability.kernel(ability.compress(only_fractured), BeastSideSwap(Side.PREFIX))


# --- the pilot count -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "actions",
    [
        (TalismanFracture(1), AnnulmentOrb()),
        (BeastSideSwap(Side.PREFIX), BeastSideSwap(Side.SUFFIX, beast_level=80), AnnulmentOrb()),
        (AspectBeast("cat", 30), AnnulmentOrb()),
        (WildBristleMatron(), AnnulmentOrb()),
    ],
    ids=["fracture", "side_swaps", "aspect", "matron"],
)
def test_the_pilot_count_of_a_beast_model_is_the_graph_the_kernels_make(actions):
    ability = ability_for(actions, metamods=True)
    start = ability.compress(talisman(bm.LIFE1, bm.ES1, bm.FIRE, bm.COLD))
    seen, transitions = real_graph(ability, [start], actions)
    try:
        pilot = ability.estimate([start], actions)
    except Exception as refusal:  # the pilot has no rule for a fracture made mid-route (`EstimateRefused`): a caller builds the graph without a forecast
        assert type(refusal).__name__ == "EstimateRefused" and any(isinstance(a, TalismanFracture) for a in actions)
        return
    assert (pilot.states, pilot.transitions) == (len(seen), transitions) and pilot.states > 5
