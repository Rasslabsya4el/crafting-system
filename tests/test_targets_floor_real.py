"""The item level floor on the real 3.29.3.3 export and the benchmark target files (ticket #352, ADR-0061, research #337).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with `CRAFTING_CACHE_DIR`). They skip cleanly
when it is not there; CI fetches it (ticket #165).

* Since ticket #457 the key `tiers_top_at_item_level` is gone: a leaf with no `min_tier` asks the top tier of its ladder at the file's level (OR-1) and the
  floor asks the one judgement of each source. Five targets stay at their level (their leaves need it, or no source gives a leaf), nine are lowered:
  J01 to 1, R05 to 44, R08 to 84, R09 to 68, R10 and R10-70-life to 55, V01 to 64, R12 to 75 and R13 to 84 (the bench craft its damage line names needs 81).
* R08 (Sorcerer Boots) needs only item level 84 (tier-1 Energy Shield %), not the 86 its file says; its levels 84 to 100 are three plans: 84, 85 and 86 and up.
* A level below the floor is refused with the requirement that needs more; the level is set on the target and on its start item.
"""

import re
from pathlib import Path

import pytest
from abstraction_support import real_game_data

from crafting_system.actions import drawable_mod_ids
from crafting_system.targets import (
    TargetError,
    floor_of,
    item_level_options,
    load_target,
    parse_target,
    refusal_at,
    target_at_level,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "targets"
STEMS = sorted(path.stem for path in EXAMPLES.glob("*.yaml"))


@pytest.fixture(scope="module")
def data():
    return real_game_data()


def target_of(data, stem: str):
    return load_target(EXAMPLES / f"{stem}.yaml", data)


def spans(options) -> list[tuple[int, int]]:
    return [(group.lowest, group.highest) for group in options.groups]


# -- the benchmark routes ----------------------------------------------------------------------------------------


def test_r13_needs_only_item_level_84_for_its_tier_1_resistances(data):
    target = target_of(data, "r13-life-resist-belt")

    options = item_level_options(data, target)

    assert target.item_level == 86
    assert (options.floor.level, options.floor.kind) == (84, "derived")
    assert spans(options) == [(84, 84), (85, 85), (86, 100)]
    binding = options.floor.binding
    assert binding is not None and binding.level == 84 and binding.source == "pool"
    assert "FireResistance tier 1" in binding.label and "ColdResistance tier 1" in binding.label
    assert [node.level for node in options.floor.nodes] == [64, 84, 81]  # tier-1 Life needs 64; the named damage craft (bench) 81


def test_r08_needs_only_item_level_84_for_its_tier_1_energy_shield(data):
    target = target_of(data, "r08-energy-shield-boots")

    options = item_level_options(data, target)

    assert target.item_level == 86
    assert (options.floor.level, options.floor.kind) == (84, "derived")
    assert spans(options) == [(84, 84), (85, 85), (86, 100)]
    shield, speed = options.floor.nodes
    assert (shield.level, shield.source) == (84, "pool")
    assert (speed.level, speed.source) == (68, "bench")  # the bench Movement Speed (level 68) is named by `mod:`, so it is a way to the leaf; the rolled 35% needs 86


def test_r05_is_lowered_to_the_level_its_tiers_need(data):
    target = target_of(data, "r05-strength-ring")

    options = item_level_options(data, target)

    assert target.item_level == 75
    assert (options.floor.level, options.floor.kind) == (44, "derived")
    assert spans(options)[0] == (44, 44) and spans(options)[-1][1] == 75  # the groups run up to the file level (the last group ends where the file level ends)
    assert refusal_at(data, target, 43) is not None and refusal_at(data, target, 44) is None
    life = options.floor.binding
    assert life is not None and life.level == 44 and life.source == "pool" and life.mod_id == "IncreasedLife7"  # the bench Life has no natural tier: it opens nothing


# a target stays at its level when its leaves need it, or when no source the floor knows gives a leaf (`at target`)
STAYS = {
    "r03-avoid-shock-boots": (100, "at target"),
    "r04-penetrating-quiver": (81, "derived"),
    "r06-strength-heavy-belt": (75, "derived"),
    "r07-minion-wand": (84, "at target"),  # the minion speed and the Trigger are veiled and bench mods: no source the floor knows
    "r14-hunter-bow": (78, "at target"),
    "r24-avoid-shock-boots": (86, "at target"),  # the Movement Speed + Onslaught is a veiled mod: no source the floor knows
}
LOWERED = {
    "j01-cobalt-life-attack-speed": 1,  # a jewel's mods all open at level 1
    "r05-strength-ring": 44,
    "r08-energy-shield-boots": 84,
    "r09-life-boots": 68,
    "r10-fractured-boots": 55,
    "r10-fractured-boots-70-life": 55,
    "r11-reservation-helmet": 81,  # no leaf asks tier 1 any more (#404): the start helmet's fractured Chaos Resistance (tier 1) needs 81
    "r12-lightning-amulet": 75,  # the +1 gem level needs 75; the start amulet already holds the resistance (any tier)
    "r13-life-resist-belt": 84,  # the tier-1 resistances need 84
    "r17-lightning-talisman": 75,  # the two +1 gem levels need 75
    "v01-minion-helmet": 64,
}


@pytest.mark.parametrize("stem", sorted(STAYS))
def test_a_target_whose_leaves_need_its_level_stays_at_its_level(data, stem):
    target = target_of(data, stem)

    options = item_level_options(data, target)

    level, kind = STAYS[stem]
    assert (options.floor.level, options.floor.kind) == (level, kind)
    assert options.floor.level == target.item_level
    assert refusal_at(data, target, target.item_level - 1) is not None


def test_the_staying_and_the_lowered_examples_are_every_example_target(data):
    assert sorted([*STAYS, *LOWERED]) == STEMS
    for stem, floor in LOWERED.items():
        found = floor_of(data, target_of(data, stem))
        assert (found.level, found.kind) == (floor, "derived")
        assert found.level < target_of(data, stem).item_level or stem == "j01-cobalt-life-attack-speed" or found.level == 84


def test_r04_is_not_lowered_because_the_essence_that_gives_its_bow_skill_mod_is_not_offered(data):
    target = target_of(data, "r04-penetrating-quiver")

    options = item_level_options(data, target)

    bow = next(node for node in options.floor.nodes if node.label.startswith("DamageWithWeaponTypeSkill"))
    assert target.item_level == 81 and (bow.level, bow.source) == (81, "pool")  # the target names Insanity and Deafening Rage, not Woe
    assert options.floor.level == 81


def test_the_start_ring_of_r05_needs_level_33_and_the_essence_strength_asks_no_level(data):
    found = floor_of(data, target_of(data, "r05-strength-ring"))

    assert found.start_level == 33  # the fractured All Attributes of the start ring needs level 33
    strength = found.nodes[1]
    assert (strength.label, strength.source, strength.level) == ("Strength", "forced mod", 1)


# -- a level below the floor ------------------------------------------------------------------------------------


def test_r13_is_refused_below_84_and_planned_at_84_with_the_level_on_its_start_item(data):
    target = target_of(data, "r13-life-resist-belt")

    problem = refusal_at(data, target, 83)
    lowered = target_at_level(data, target, 84)

    assert problem is not None and "item level 83 is below 84" in problem and "FireResist8" in problem
    assert (lowered.item_level, lowered.start_item.item_level) == (84, 84)
    assert lowered.start_item.base_id == target.base_id and lowered.requirements == target.requirements
    with pytest.raises(TargetError, match="item level 83 is below 84"):
        target_at_level(data, target, 83)


def test_a_target_whose_leaf_needs_more_than_its_level_stays_at_its_level(data):
    text = (EXAMPLES / "r13-life-resist-belt.yaml").read_text(encoding="utf-8")
    shorter = re.sub(r"(?m)^item_level:\s*86", "item_level: 83", text)
    assert shorter != text

    options = item_level_options(data, parse_target(shorter, data))

    assert (options.floor.level, options.floor.kind) == (83, "at target")
    assert spans(options) == [(83, 83)]  # nothing below 83 is planned, and level 84 opens the tier-1 resistances
    assert "84" in options.floor.reason


# -- groups are equal pools -------------------------------------------------------------------------------------


@pytest.mark.parametrize("stem", ["r05-strength-ring", "r08-energy-shield-boots"])
def test_the_levels_of_a_group_open_one_pool_and_the_next_group_another(data, stem):
    target = target_of(data, stem)
    options = item_level_options(data, target)

    def pool(level: int):
        return drawable_mod_ids(data, target.start_item.changed(data, item_level=level))

    for group in options.groups:
        assert len({pool(level) for level in range(group.lowest, group.highest + 1)}) == 1
    for earlier, later in zip(options.groups, options.groups[1:], strict=False):
        assert pool(earlier.lowest) != pool(later.lowest)


@pytest.mark.parametrize("stem", STEMS)
def test_every_example_target_has_a_floor_not_above_its_level_and_groups_that_tile_the_levels(data, stem):
    target = target_of(data, stem)

    options = item_level_options(data, target)

    assert 1 <= options.floor.level <= target.item_level
    assert options.groups[0].lowest == options.floor.level
    assert options.groups[-1].contains(target.item_level)
    for earlier, later in zip(options.groups, options.groups[1:], strict=False):
        assert earlier.highest + 1 == later.lowest
