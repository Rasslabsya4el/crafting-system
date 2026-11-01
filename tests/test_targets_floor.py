"""The item level floor of a target and the groups of levels with one pool (ticket #352, ADR-0061), on the small fixture export.

The data is a Paua Amulet pool (`items_support.DATA`). The tiers there: Lightning Resistance tier 1 needs item level 84, tier 2 level 72,
Life tier 1 level 18, Chaos Resistance tier 1 (31-35) level 81. Every target below is `base: Paua Amulet`, `item_level: 84` unless
the test says otherwise (`targets_support.HEADER`). The real benchmark routes are in `test_targets_floor_real.py`.
"""

import pytest
from items_support import DATA
from targets_corrupted_support import DATA as CORRUPTED_DATA
from targets_corrupted_support import parse as parse_corrupted
from targets_support import parse, parse_error

from crafting_system.actions import drawable_mod_ids
from crafting_system.targets import (
    TargetError,
    floor_of,
    item_level_options,
    level_groups,
    parse_target,
    refusal_at,
    target_at_level,
)

LIGHTNING_1 = "family: LightningResistance\n  min_tier: 1"
LIGHTNING_2 = "family: LightningResistance\n  min_tier: 2"
LIFE_1 = "family: IncreasedLife\n  min_tier: 1"


def requirements(*entries: str, tail: str = "") -> str:
    """A target text: the `requirements:` list of the entries (each a block of lines, the first after `- `)."""
    lines = ["requirements:"]
    for entry in entries:
        first, *rest = entry.split("\n")
        lines.append(f"  - {first}")
        lines.extend(f"  {line}" for line in rest)
    return "\n".join(lines) + "\n" + tail


def floor(*entries: str, tail: str = ""):
    return floor_of(DATA, parse(requirements(*entries, tail=tail)))


# -- the floor comes from the tiers the requirements ask for -----------------------------------------------


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        (LIGHTNING_1, 84),  # tier 1 is LightningResist8, required level 84
        (LIGHTNING_2, 72),  # tier 2 accepts LightningResist7 (72)
        (LIFE_1, 18),
        ("family: LightningResistance", 1),  # any tier: the lowest tier is level 1
        ("family: ChaosResistance\n  min_roll: 31", 81),  # only ChaosResist6 rolls 31 or more
    ],
)
def test_the_floor_is_the_lowest_level_of_the_mods_that_pass_the_tier_and_the_roll(entry, expected):
    found = floor(entry)

    assert found.level == expected
    assert found.kind == "derived"
    assert found.start_level == 1


def test_the_highest_requirement_binds_and_the_reason_names_it():
    found = floor(LIFE_1, LIGHTNING_2)

    assert found.level == 72
    assert [node.level for node in found.nodes] == [18, 72]
    assert found.binding is not None and found.binding.mod_id == "LightningResist7"
    assert "LightningResistance tier 2 needs item level 72" in found.reason and "LightningResist7" in found.reason


def test_an_at_least_group_takes_the_k_th_lowest_of_its_members():
    members = (
        "    of:\n"
        "      - family: LightningResistance\n        min_tier: 1\n"
        "      - family: IncreasedLife\n        min_tier: 1\n"
    )

    one = floor_of(DATA, parse(f"requirements:\n  - at_least: 1\n{members}"))
    both = floor_of(DATA, parse(f"requirements:\n  - at_least: 2\n{members}"))

    assert (one.level, both.level) == (18, 84)
    assert "at least 1 of" in one.nodes[0].label


def test_a_requirement_the_start_item_meets_asks_no_level_but_its_mods_need_their_own():
    start = "start_item:\n  rarity: rare\n  mods:\n    - mod: LightningResist5\n      tier: 4\n      values: [30]\n      fractured: true\n"

    found = floor("family: LightningResistance", tail=start)

    assert found.nodes[0].source == "start item" and found.nodes[0].level == 1
    assert found.start_level == 49  # LightningResist5 needs level 49
    assert found.level == 49 and "start item" in found.reason


def test_the_bench_gives_a_mod_at_its_own_level_unless_the_target_wants_it_rolled_or_leaves_the_bench_out():
    entry = "family: IncreasedWeaponElementalDamagePercent"

    on_bench = floor(entry)
    rolled = floor(entry + "\n  not_crafted: true")
    left_out = floor(entry, tail="actions: [alteration-orb]\n")

    assert (on_bench.nodes[0].source, on_bench.nodes[0].level) == ("bench", 30)
    assert on_bench.level == 30
    assert rolled.nodes[0].level is None and left_out.nodes[0].level is None


def test_an_essence_gives_its_mod_when_the_target_offers_it_and_no_other_does():
    entry = "family: ColdDamagePercentage"  # only Whispering Essence of Hatred gives this mod to an amulet

    by_default = floor(entry)
    by_kind = floor(entry, tail="actions: [essence]\n")
    by_label = floor(entry, tail="actions: ['Whispering Essence of Hatred']\n")
    left_out = floor(entry, tail="actions: [alteration-orb]\n")

    for found in (by_default, by_kind, by_label):
        assert (found.nodes[0].source, found.nodes[0].level) == ("essence", 1)
    assert left_out.nodes[0].level is None


def test_naming_one_essence_offers_that_essence_only_and_a_corrupted_essence_only_when_named():
    hatred, hysteria = "family: ColdDamagePercentage", "family: IncreasedLifeLeechRate"  # the second mod needs level 63 as a drawn mod

    other_essence = floor(hatred, tail="actions: ['Essence of Hysteria']\n")
    unnamed = floor(hysteria)
    by_kind = floor(hysteria, tail="actions: [corrupted-essence]\n")
    by_label = floor(hysteria, tail="actions: ['Essence of Hysteria']\n")

    assert other_essence.nodes[0].level is None  # Hatred is not offered
    assert unnamed.nodes[0].level is None and unnamed.kind == "at target"  # corrupted essences are opt-in
    assert (by_kind.nodes[0].source, by_kind.nodes[0].level) == ("essence", 1)  # the essence ignores the item level
    assert (by_label.nodes[0].source, by_label.nodes[0].level) == ("essence", 1)
    assert by_label.level == 1


def test_naming_one_bench_craft_offers_that_craft_only():
    entry = "family: IncreasedWeaponElementalDamagePercent"

    by_label = floor(entry, tail="actions: ['Bench craft #% increased Elemental Damage with Attack Skills']\n")
    other = floor(entry, tail="actions: ['Bench craft Prefixes Cannot Be Changed']\n")

    assert (by_label.nodes[0].source, by_label.nodes[0].level) == ("bench", 30)
    assert other.nodes[0].level is None


def test_an_at_least_group_with_one_unreachable_member_still_has_a_level_when_enough_remain():
    members = "    of:\n      - family: ChaosDamageHybrid\n      - family: IncreasedLife\n        min_tier: 1\n"

    found = floor_of(DATA, parse(f"requirements:\n  - at_least: 1\n{members}"))
    both = floor_of(DATA, parse(f"requirements:\n  - at_least: 2\n{members}"))

    assert (found.level, found.kind) == (18, "derived")
    assert (both.level, both.kind) == (84, "at target")


# -- where the floor is not below the file's level -------------------------------------------------------------


def test_tiers_top_at_item_level_says_the_level_is_not_lowered():
    found = floor(LIFE_1, tail="tiers_top_at_item_level: true\n")

    assert (found.level, found.kind) == (84, "pinned")
    assert [group.lowest for group in item_level_options(DATA, parse(requirements(LIFE_1, tail="tiers_top_at_item_level: true\n"))).groups] == [84]


def test_a_stated_floor_raises_the_derived_one_and_never_lowers_it():
    higher = floor(LIFE_1, tail="item_level_floor: 80\n")
    lower = floor(LIGHTNING_1, tail="item_level_floor: 10\n")

    assert (higher.level, higher.kind) == (80, "stated") and "80" in higher.reason and "18" in higher.reason
    assert (lower.level, lower.kind) == (84, "derived")


def test_a_target_that_asks_for_more_than_its_own_level_is_not_lowered():
    target = parse_target("base: Paua Amulet\nitem_level: 80\n" + requirements(LIGHTNING_1), DATA)
    found = floor_of(DATA, target)

    assert (found.level, found.kind) == (80, "at target")
    assert "84" in found.reason and "80" in found.reason


def test_a_requirement_no_source_gives_leaves_the_level_where_the_file_put_it():
    found = floor("family: ChaosDamageHybrid")  # an influence mod: no tag of a plain amulet spawns it

    assert (found.level, found.kind) == (84, "at target")
    assert found.nodes[0].level is None and found.nodes[0].source == "none"
    assert "ChaosDamageHybrid" in found.reason


def test_a_corrupted_implicit_target_is_not_lowered():
    target = parse_corrupted("implicits:\n  - stat: '+#% to all Elemental Resistances'\n    corrupted: true\n")

    found = floor_of(CORRUPTED_DATA, target)

    assert (found.level, found.kind) == (target.item_level, "corrupted")


# -- the keys in a file ----------------------------------------------------------------------------------------


def test_the_two_keys_parse_and_default_to_off():
    plain = parse(requirements(LIFE_1))
    keyed = parse(requirements(LIFE_1, tail="item_level_floor: 70\ntiers_top_at_item_level: false\n"))

    assert (plain.item_level_floor, plain.tiers_top_at_item_level) == (None, False)
    assert (keyed.item_level_floor, keyed.tiers_top_at_item_level) == (70, False)


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("item_level_floor: 85\n", "item_level_floor: must be a whole number from 1 to the item level (84)"),
        ("item_level_floor: 0\n", "item_level_floor: must be a whole number from 1 to the item level (84)"),
        ("item_level_floor: high\n", "item_level_floor: must be a whole number"),
        ("tiers_top_at_item_level: yes please\n", "tiers_top_at_item_level: must be true or false"),
    ],
)
def test_error_a_bad_key_value_names_the_key(text, needle):
    assert needle in parse_error(requirements(LIFE_1, tail=text))


# -- groups of levels with one pool ----------------------------------------------------------------------------


def test_levels_are_grouped_by_the_pool_they_open_and_the_top_group_runs_past_the_files_level():
    target = parse(requirements(LIGHTNING_2))  # floor 72, file level 84

    groups = item_level_options(DATA, target).groups

    assert groups[0].lowest == 72
    assert groups[-1].highest == 100 and groups[-1].contains(84)
    for earlier, later in zip(groups, groups[1:], strict=False):
        assert earlier.highest + 1 == later.lowest  # no gap and no overlap


def test_every_level_of_a_group_has_one_pool_and_the_next_group_has_another():
    target = parse(requirements(LIFE_1))  # floor 18
    groups = item_level_options(DATA, target).groups
    start = target.start_item

    def pool(level: int):
        return drawable_mod_ids(DATA, start.changed(DATA, item_level=level))

    assert len(groups) > 3
    for group in groups:
        assert len({pool(level) for level in range(group.lowest, group.highest + 1)}) == 1
    for earlier, later in zip(groups, groups[1:], strict=False):
        assert pool(earlier.lowest) != pool(later.lowest)


def test_groups_start_at_the_floor_and_a_floor_inside_a_group_cuts_it():
    target = parse(requirements(LIGHTNING_1))  # floor 84 = the file's level

    (group,) = level_groups(DATA, target, 84)

    assert (group.lowest, group.highest) == (84, 100)
    assert level_groups(DATA, target, 83)[0].lowest == 83
    with pytest.raises(ValueError, match="floor 85"):
        level_groups(DATA, target, 85)


def test_a_catalyst_quality_makes_every_level_its_own_group():
    plain = parse(requirements(LIGHTNING_2, tail=""))
    with_quality = parse(requirements(LIGHTNING_2, tail="quality:\n  type: intrinsic\n  min_percent: 20\n"))

    assert len(item_level_options(DATA, plain).groups) < len(item_level_options(DATA, with_quality).groups)
    assert [group.lowest for group in item_level_options(DATA, with_quality).groups] == list(range(72, 85))


# -- planning at a level -----------------------------------------------------------------------------------------


def test_a_level_below_the_floor_is_refused_with_the_requirement_that_needs_more():
    target = parse(requirements(LIGHTNING_2))

    problem = refusal_at(DATA, target, 71)

    assert problem is not None and "item level 71 is below 72" in problem and "LightningResistance tier 2" in problem
    assert refusal_at(DATA, target, 72) is None
    assert refusal_at(DATA, target, 100) is None
    assert refusal_at(DATA, target, 101) is not None


def test_target_at_level_sets_the_level_of_the_target_and_its_start_item_and_refuses_below_the_floor():
    target = parse(requirements(LIGHTNING_2, tail="item_level_floor: 72\n"))

    lowered = target_at_level(DATA, target, 72)

    assert (lowered.item_level, lowered.start_item.item_level) == (72, 72)
    assert lowered.requirements == target.requirements and lowered.base_id == target.base_id
    assert target.item_level == 84 and target.start_item.item_level == 84  # the original is untouched
    assert target_at_level(DATA, target, 84) is target
    with pytest.raises(TargetError, match="item level 71 is below 72"):
        target_at_level(DATA, target, 71)


def test_a_lowered_target_keeps_the_stated_floor_so_it_cannot_be_lowered_again():
    target = parse(requirements(LIFE_1, tail="item_level_floor: 80\n"))

    lowered = target_at_level(DATA, target, 80)

    assert lowered.item_level_floor == 80
    assert refusal_at(DATA, lowered, 79) is not None


@pytest.mark.parametrize("level", [True, 84.0, "84", 0, 101])
def test_a_level_that_is_not_a_whole_number_of_1_to_100_is_refused(level):
    problem = refusal_at(DATA, parse(requirements(LIFE_1)), level)

    assert problem is not None and "outside 1 to 100" in problem
