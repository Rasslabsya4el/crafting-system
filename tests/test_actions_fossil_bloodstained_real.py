"""The Bloodstained Fossil on the real 3.29.3.3 dump (ticket #261, ADR-0037, ADR-0038).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with `CRAFTING_CACHE_DIR`). They skip cleanly
when it is not there; CI fetches it (ticket #165), so they run there.

* A ring of item level 86 draws its corrupted implicit from the 39 mods of weight 31,850 (ADR-0037): "+(14-16)% to all Elemental
  Resistances" has weight 1000, so a resonator that holds a Bloodstained Fossil gives it with chance 1000/31,850 whatever else it
  holds, and the chance of an explicit mod AND that implicit is the product of the two (ADR-0038).
* The sampler rolls the same resonator at random and agrees within five standard errors.
* The listing of the sets of a boots item now holds the Bloodstained sets; the offers for a target that does not ask for a corrupted
  implicit hold none of them.
"""

import random
from collections import Counter
from fractions import Fraction

import pytest
from abstraction_support import real_game_data

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import ApplyFossils, corrupted_implicit_pool, fossil_actions, usable_fossils
from crafting_system.cli._offers import offers_for
from crafting_system.items import Item, Rarity, spawn_weight

BLOODSTAINED = "Bloodstained Fossil"
ALL_RES_TEXT = "+(14-16)% to all Elemental Resistances"
LEVEL = 86


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def base_named(data, name: str) -> str:
    return next(base.id for base in data.base_items.values() if base.name == name)


def empty_rare(data, name: str) -> Item:
    return Item.build(data, base_id=base_named(data, name), item_level=LEVEL, rarity=Rarity.RARE, mods=())


def all_resistances(data, item: Item) -> str:
    pool = corrupted_implicit_pool(data, item.base_id, item.item_level)
    (found,) = [entry.mod.id for entry in pool.mods if entry.mod.text == ALL_RES_TEXT]
    assert pool.weight_of(found) == 1000 and pool.total_weight == 31_850
    return found


def a_cold_resistance(data, item: Item) -> str:
    """A cold resistance suffix the ring can roll: the explicit mod the product is checked on (a Prismatic Fossil boosts it)."""
    base = data.base_items[item.base_id]
    return next(
        mod.id
        for mod in data.mods.values()
        if mod.generation_type == "suffix"
        and "ColdResistance" in mod.families
        and mod.domain == "item"
        and mod.required_level <= item.item_level
        and spawn_weight(mod, base.tags) > 0
    )


def test_the_chance_of_all_resistances_is_its_weight_over_the_pool_whatever_the_other_fossils_are(data):
    ring = empty_rare(data, "Iron Ring")
    wanted = all_resistances(data, ring)
    for others in ((), ("Prismatic Fossil",), ("Prismatic Fossil", "Pristine Fossil"), ("Gilded Fossil", "Aetheric Fossil")):
        outcomes = ApplyFossils((BLOODSTAINED, *others)).outcomes(data, ring)
        assert outcomes.chance_all([wanted]) == Fraction(1000, 31_850)


def test_the_chance_of_a_mod_and_the_implicit_is_the_product(data):
    ring = empty_rare(data, "Iron Ring")
    wanted = all_resistances(data, ring)
    explicit = a_cold_resistance(data, ring)
    corrupting = ApplyFossils((BLOODSTAINED, "Prismatic Fossil")).outcomes(data, ring)
    rerolling = ApplyFossils(("Prismatic Fossil",)).outcomes(data, ring)

    assert 0 < rerolling.chance_all([explicit]) < 1
    assert corrupting.chance_all([explicit, wanted]) == rerolling.chance_all([explicit]) * Fraction(1000, 31_850)


def test_the_sampler_agrees_with_the_chance_of_the_implicit_and_of_a_mod_together(data):
    ring = empty_rare(data, "Iron Ring")
    wanted = all_resistances(data, ring)
    explicit = a_cold_resistance(data, ring)
    outcomes = ApplyFossils((BLOODSTAINED, "Prismatic Fossil")).outcomes(data, ring)
    chances = {"implicit": float(outcomes.chance_all([wanted])), "both": float(outcomes.chance_all([explicit, wanted]))}
    runs = 20_000
    rng = random.Random(261)
    seen = Counter()
    for _ in range(runs):
        drawn = outcomes.sample(rng)
        assert drawn.corrupted
        has_implicit = any(entry.mod_id == wanted for entry in drawn.implicits)
        seen["implicit"] += has_implicit
        seen["both"] += has_implicit and any(entry.mod_id == explicit for entry in drawn.mods)
    for name, chance in chances.items():
        assert abs(seen[name] / runs - chance) < 5 * (chance * (1 - chance) / runs) ** 0.5, name


def test_the_kernel_of_a_resonator_with_the_fossil_is_the_one_without_it_made_corrupted(data):
    ring = empty_rare(data, "Iron Ring")
    explicit = a_cold_resistance(data, ring)
    goal = Goal((Wanted(frozenset({explicit})),), asks_corrupted=True)
    action, reroll = ApplyFossils((BLOODSTAINED, "Prismatic Fossil")), ApplyFossils(("Prismatic Fossil",))
    corrupting = Abstraction(data, goal, ring.base_id, LEVEL, [action])
    rerolling = Abstraction(data, Goal(goal.requirements), ring.base_id, LEVEL, [])

    kernel = corrupting.kernel(corrupting.compress(ring), action)
    plain = rerolling.kernel(rerolling.compress(ring), reroll)

    assert sum(kernel.values()) == 1
    assert sorted(kernel.values()) == sorted(plain.values())  # the same masses on the states, every state corrupted
    assert all(state.flags.corrupted for state in kernel)


def test_the_boots_listing_holds_the_bloodstained_sets(data):
    item = empty_rare(data, "Sorcerer Boots")
    actions = fossil_actions(data, item)
    assert BLOODSTAINED in usable_fossils(data, item)
    assert Counter(len(action.fossils) for action in actions) == {1: 25, 2: 299, 3: 2277, 4: 12397}
    assert len(actions) == 14_998  # 25 usable fossils, without the Hollow + Glyphic sets
    with_it = [action for action in actions if BLOODSTAINED in action.fossils]
    assert len(with_it) == 14_998 - 12_696  # the sets of the 24 others are the 12,696 of before the ticket
    assert len(set(actions)) == len(actions)


def test_the_real_bloodstained_record_forbids_the_heist_tags(data):
    record = next(fossil for fossil in data.fossils.values() if fossil.name == BLOODSTAINED)
    assert set(record.forbidden_tags) == {"heist_contract", "heist_blueprint", "heist_equipment"}
    assert not record.positive_mod_weights and not record.negative_mod_weights and not record.added_mods and not record.forced_mods


def test_the_offers_for_a_target_that_does_not_ask_hold_no_bloodstained_set_and_those_for_one_that_asks_do(data):
    ring = empty_rare(data, "Iron Ring")
    explicit = a_cold_resistance(data, ring)
    wanted = (Wanted(frozenset({explicit})),)

    def labels(goal: Goal) -> list[str]:
        return [offer.label for offer in offers_for(data, goal, ring.base_id, ring, ("fossil-set",)).offers]

    plain, allowing, asking = labels(Goal(wanted)), labels(Goal(wanted, allow_corrupted=True)), labels(Goal(wanted, asks_corrupted=True))

    assert plain and plain == allowing
    assert not any(BLOODSTAINED in label for label in plain)
    assert [label for label in asking if BLOODSTAINED not in label] == plain
    assert any(BLOODSTAINED in label for label in asking)
