"""A mod an action names, of a family the pool lists on its side in mods with other protected tags (#1453).

The Screaming Essence of Woe gives a bow the prefix `SpellDamageOnTwoHandWeaponEssence5` (tagged `caster`), of the family
`WeaponCasterDamagePrefix`. On R14's Hunter Thicket Bow the pool lists that family in the Hunter's Chaos Damage over Time prefixes, which carry
no protected tag. With a metamod among the offers (the bench's "Cannot roll Attack Modifiers") the kinds carry the protected tags, so the
essence's mod has the kind of its family's type with `caster` (`Kinds.of`), and no mod of the pool can stand for it (`Kinds.representative`).
The state the essence gave was then no item (`Abstraction._item_of` refused it): the bound's build met a key with no member, and R14's 1 h
run of 2026-11-23 refused 11 widening groups with "a fault of its own" (OR-12, OR-13).
"""

from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.abstraction import Abstraction, Goal
from crafting_system.abstraction._kinds import protected_tags
from crafting_system.items import ExplicitMod, Influence, Item, Rarity
from crafting_system.planner import offers_for
from crafting_system.targets import load_target

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "examples" / "targets" / "r14-hunter-bow.yaml"
ESSENCE = "SpellDamageOnTwoHandWeaponEssence5"  # the Screaming Essence of Woe's bow prefix
FAMILY = "WeaponCasterDamagePrefix"
LABELS = (  # R14's plan in hand of 2026-11-23, carried into each widening group: the bench's metamod turns the protected tags on
    "Bench craft +(18-20)% to Chaos Damage over Time Multiplier", "Bench craft +2 to Level of Socketed Support Gems",
    "Bench craft Can have up to 3 Crafted Modifiers", "Bench craft Cannot roll Attack Modifiers", "Exalted Orb", "Orb of Alteration",
    "Orb of Annulment", "Orb of Augmentation", "Regal Orb", "Remove Crafted Mods",
)


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def test_the_state_that_holds_the_essences_tagged_prefix_is_an_item(data):
    target = load_target(TARGET, data)
    goal = Goal.from_target(target)
    chosen = offers_for(data, goal, target.base_id, target.start_item).offers  # every method, as the run with every method on
    offered = [offer.action for offer in chosen if offer.label in LABELS or offer.kind == "essence"]  # the essence group of R14's run
    assert len(offered) > len(LABELS)
    ability = Abstraction(data, goal, target.base_id, target.item_level, [action for action in offered if action.reads(data).junk])
    assert ability._kinds.metamods  # the kinds carry the protected tags
    pool_mods = [mod for mod in data.mods.values() if FAMILY in mod.families and mod.id.startswith("PoisonDamagePrefixInfluence")]
    assert pool_mods and all(not protected_tags(mod) for mod in pool_mods)  # the family's mods in the Hunter bow's pool: untagged
    assert protected_tags(data.mods[ESSENCE]) == frozenset({"caster"})

    low = lambda mod_id: tuple(min(stat.min, stat.max) for stat in data.mods[mod_id].stats)  # noqa: E731
    item = Item.build(
        data, base_id=target.base_id, item_level=target.item_level, rarity=Rarity.RARE, influences=frozenset({Influence.HUNTER}),
        mods=tuple(ExplicitMod(mod_id, low(mod_id)) for mod_id in (ESSENCE, "FireResist1")),
    )  # fmt: skip
    state = ability.compress(item)
    essence_slot = next(slot for slot in state.slots if slot.side.value == "prefix")
    assert essence_slot.kind.startswith("~") and essence_slot.kind.endswith("@caster")  # the type of its family, with its tag

    back, origins = ability._item_of(state, False)  # before #1453: ValueError, "more prefix slots ... than the pool has families"

    held = [data.mods[entry.mod_id] for entry in back.mods]
    stand_in = next(mod for mod in held if mod.generation_type == "prefix")
    assert FAMILY in stand_in.families and protected_tags(stand_in) == frozenset({"caster"})  # a mod of the family, with the kind's tag
    assert not ability._kinds.is_influenced(stand_in)
    assert origins[(stand_in.id, False, False)] == essence_slot  # and the slot keeps what the essence's mod gives the goal
    assert ability.compress(back) == state  # the item it stands for is the state again
