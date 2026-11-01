"""The item level floor on the real 3.29.3.3 export and the benchmark target files (ticket #352, ADR-0061, research #337).

These tests need the cached dump (`<cache dir>/repoe-fork/3.29.3.3/`, set the cache folder with `CRAFTING_CACHE_DIR`). They skip cleanly
when it is not there; CI fetches it (ticket #165).

* R13 (a Leather Belt) and R08 (Sorcerer Boots) both need only item level 84 (tier-1 Fire and Cold Resistance, tier-1 Energy Shield %),
  not the 86 their files say; their levels 84 to 100 are three plans: 84, 85 and 86 and up (the note's table of section 1.3).
* R05's tiers are "the top tier at item level 75", its file says so, and the floor stays 75. The tiers alone would let a ring of level 33 do.
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
    assert [node.level for node in options.floor.nodes][:2] == [64, 84]  # tier-1 Life needs 64


def test_r08_needs_only_item_level_84_for_its_tier_1_energy_shield(data):
    target = target_of(data, "r08-energy-shield-boots")

    options = item_level_options(data, target)

    assert target.item_level == 86
    assert (options.floor.level, options.floor.kind) == (84, "derived")
    assert spans(options) == [(84, 84), (85, 85), (86, 100)]
    shield, speed = options.floor.nodes
    assert (shield.level, shield.source) == (84, "pool")
    assert (speed.level, speed.source) == (68, "bench")  # the bench Movement Speed (level 68) is a way to the leaf, the rolled 35% needs 86


def test_r05_is_not_lowered_because_its_file_says_its_tiers_are_the_top_of_its_level(data):
    target = target_of(data, "r05-strength-ring")

    options = item_level_options(data, target)

    assert target.item_level == 75 and target.tiers_top_at_item_level
    assert (options.floor.level, options.floor.kind) == (75, "pinned")
    assert spans(options) == [(75, 75)]
    assert refusal_at(data, target, 74) is not None and refusal_at(data, target, 75) is None


PINNED = [
    "r03-avoid-shock-boots",
    "r04-penetrating-quiver",
    "r05-strength-ring",
    "r06-strength-heavy-belt",
    "r09-life-boots",
    "r10-fractured-boots",
    "r10-fractured-boots-70-life",
    "r11-reservation-helmet",
    "r12-lightning-amulet",
    "r14-hunter-bow",
]
LOWERED = {"r08-energy-shield-boots": 84, "r13-life-resist-belt": 84, "j01-cobalt-life-attack-speed": 1, "v01-minion-helmet": 64}  # the ticket's R08 and R13; a jewel's mods all open at level 1; V01's tier-1 Life opens at 64 (ticket #331)


@pytest.mark.parametrize("stem", PINNED)
def test_a_target_whose_tiers_are_the_top_of_its_level_stays_at_its_level(data, stem):
    target = target_of(data, stem)

    options = item_level_options(data, target)

    assert target.tiers_top_at_item_level
    assert (options.floor.level, options.floor.kind) == (target.item_level, "pinned")
    assert refusal_at(data, target, target.item_level - 1) is not None


def test_the_pinned_and_the_lowered_examples_are_every_example_target(data):
    assert sorted([*PINNED, *LOWERED]) == STEMS
    for stem, floor in LOWERED.items():
        found = floor_of(data, target_of(data, stem))
        assert (found.level, found.kind) == (floor, "derived")
        assert not target_of(data, stem).tiers_top_at_item_level


def test_r04_is_not_lowered_because_the_essence_that_gives_its_bow_skill_mod_is_not_offered(data):
    target = target_of(data, "r04-penetrating-quiver")

    options = item_level_options(data, target)

    bow = next(node for node in options.floor.nodes if node.label.startswith("DamageWithWeaponTypeSkill"))
    assert target.item_level == 81 and (bow.level, bow.source) == (81, "pool")  # the target names Insanity and Deafening Rage, not Woe
    assert options.floor.level == 81


def test_without_that_line_the_tiers_of_r05_alone_would_let_a_ring_of_item_level_33_do(data):
    text = (EXAMPLES / "r05-strength-ring.yaml").read_text(encoding="utf-8")
    plain = re.sub(r"(?m)^tiers_top_at_item_level:.*\n", "", text)
    assert plain != text

    found = floor_of(data, parse_target(plain, data))

    assert (found.level, found.kind) == (33, "derived")
    assert "start item" in found.reason  # the fractured All Attributes of the start ring needs level 33


def test_the_essence_strength_of_r05_asks_no_level(data):
    plain = re.sub(r"(?m)^tiers_top_at_item_level:.*\n", "", (EXAMPLES / "r05-strength-ring.yaml").read_text(encoding="utf-8"))

    strength = floor_of(data, parse_target(plain, data)).nodes[1]

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


@pytest.mark.parametrize("stem", ["r13-life-resist-belt", "r08-energy-shield-boots"])
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
