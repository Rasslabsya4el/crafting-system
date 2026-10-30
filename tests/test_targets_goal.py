"""The goal check: does a concrete item meet a target? Tier, roll, "not crafted", origin and k-of-n."""

import pytest
from targets_support import BODY, belt, item, parse, roll

from crafting_system.items import ExplicitMod
from crafting_system.targets import KOfN, Requirement


def life(tier: int, value: int, *, mod_id: str | None = None) -> ExplicitMod:
    """A life mod as stored on an item; the mod id follows the tier unless given."""
    return ExplicitMod(mod_id or f"IncreasedLife{tier}", tier, (value,))


def met(requirement_yaml: str, *mods: ExplicitMod, **fields) -> bool:
    """Whether a body armour with `mods` meets the one requirement written in `requirement_yaml`."""
    target = parse("requirements:\n" + requirement_yaml)
    return target.is_met_by(item(*mods, **fields))


def test_a_target_is_met_only_when_every_requirement_is():
    target = parse(
        """
        requirements:
          - family: IncreasedLife
          - family: LightningResistance
        """
    )
    both = item(roll("IncreasedLife1"), roll("LightningResist1"))
    only_life = item(roll("IncreasedLife1"))

    assert target.is_met_by(both) and target.unmet(both) == ()
    assert not target.is_met_by(only_life)
    assert target.unmet(only_life) == (target.requirements[1],)
    assert not target.is_met_by(item())


def test_a_family_id_and_the_stat_text_select_the_same_mods():
    by_family = parse("requirements:\n  - family: LightningResistance\n").requirements[0]
    by_stat = parse('requirements:\n  - stat: "+(6-11)% to Lightning Resistance"\n').requirements[0]

    assert by_family.mod_ids == by_stat.mod_ids
    assert {"LightningResist1", "LightningResist2", "LightningResist3"} <= by_family.mod_ids
    for mod_id in by_family.mod_ids:
        assert by_family.is_met_by(item(roll(mod_id))) and by_stat.is_met_by(item(roll(mod_id)))
    assert not by_stat.is_met_by(item(roll("ColdResist1")))


def test_the_range_form_and_the_hash_form_of_a_stat_text_are_the_same_requirement():
    hash_form = parse('requirements:\n  - stat: "+# to maximum Life"\n').requirements[0]
    range_form = parse('requirements:\n  - stat: "+(10-24) to maximum Life"\n').requirements[0]
    other_range = parse('requirements:\n  - stat: "+(40-54) to maximum Life"\n').requirements[0]

    assert hash_form.mod_ids == range_form.mod_ids == other_range.mod_ids
    assert {"IncreasedLife1", "IncreasedLife2", "IncreasedLife3"} <= hash_form.mod_ids
    assert "IncreasedLifeImplicitBelt1" not in hash_form.mod_ids


def test_a_two_line_hybrid_text_is_matched_line_by_line_and_takes_one_roll_per_stat():
    text = (
        '  - stat: "+(105-150) to Armour\\n  +(11-15) to maximum Energy Shield  "\n'
        "    min_roll: [null, 15]\n"
    )
    hybrid = roll("JunMaster2ArmourAndEnergyShield1", crafted=True)
    best = ExplicitMod("JunMaster2ArmourAndEnergyShield1", 1, (105, 15), crafted=True)

    assert "JunMaster2ArmourAndEnergyShield1" in parse("requirements:\n" + text).requirements[0].mod_ids
    assert not met(text, hybrid)
    assert met(text, best)


def test_a_family_also_counts_mods_that_are_not_prefixes_or_suffixes():
    requirement = parse("requirements:\n  - family: IncreasedLife\n").requirements[0]

    assert "IncreasedLifeImplicitBelt1" in requirement.mod_ids
    assert {"IncreasedLife1", "IncreasedLife2", "IncreasedLife3"} <= requirement.mod_ids


@pytest.mark.parametrize(("tier", "expected"), [(1, True), (2, True), (3, False)])
def test_minimum_tier_two_accepts_tiers_one_and_two(tier, expected):
    mod = life(tier, 30 if tier == 2 else 10 if tier == 1 else 40)

    assert met("  - family: IncreasedLife\n    min_tier: 2\n", mod) is expected


def test_the_stored_tier_is_read_and_never_derived():
    cheap_mod_marked_tier_one = ExplicitMod("IncreasedLife3", 1, (40,))
    best_mod_marked_tier_three = ExplicitMod("IncreasedLife1", 3, (10,))

    assert met("  - family: IncreasedLife\n    min_tier: 1\n", cheap_mod_marked_tier_one)
    assert not met("  - family: IncreasedLife\n    min_tier: 2\n", best_mod_marked_tier_three)


def test_minimum_roll_with_one_stat_passes_exactly_at_the_minimum_and_fails_one_below():
    text = "  - stat: \"+# to maximum Life\"\n    min_roll: 30\n"

    assert met(text, life(2, 30))
    assert met(text, life(2, 39))
    assert not met(text, life(2, 29))
    assert not met(text, life(1, 24))


def test_minimum_roll_as_a_list_may_skip_a_stat_with_null():
    two_stats = "  - stat: \"Adds (1-2) to (3-4) Cold Damage\"\n    min_roll: [null, 4]\n"
    first_stat = "  - stat: \"Adds (1-2) to (3-4) Cold Damage\"\n    min_roll: [2, null]\n"
    both = "  - stat: \"Adds (1-2) to (3-4) Cold Damage\"\n    min_roll: [2, 4]\n"

    low, high_second, high_first, top = (
        ExplicitMod("LocalAddedColdDamage1", 1, values) for values in ((1, 3), (1, 4), (2, 3), (2, 4))
    )

    assert not met(two_stats, low) and met(two_stats, high_second) and not met(two_stats, high_first)
    assert met(first_stat, high_first) and not met(first_stat, high_second)
    assert met(both, top) and not met(both, high_first) and not met(both, high_second)


def test_the_two_stat_mod_of_another_tier_is_also_counted_by_its_text():
    text = "  - stat: \"Adds # to # Cold Damage\"\n    min_roll: [2, 7]\n"

    assert met(text, ExplicitMod("LocalAddedColdDamageTwoHand1", 1, (2, 7)))
    assert not met(text, ExplicitMod("LocalAddedColdDamageTwoHand1", 1, (2, 6)))


def test_tier_and_roll_must_hold_on_the_same_mod():
    requirement = Requirement(
        None, "+# to maximum Life", frozenset({"IncreasedLife1", "IncreasedLife2"}), min_tier=1, min_roll=(25,)
    )
    tier_fails = item(life(2, 30))
    roll_fails = item(life(1, 24))
    both_on_one_mod = item(ExplicitMod("IncreasedLife2", 1, (30,)))

    assert not requirement.is_met_by(tier_fails)
    assert not requirement.is_met_by(roll_fails)
    assert requirement.is_met_by(both_on_one_mod)
    assert not requirement.is_met_by(item())


def test_not_crafted_rejects_a_crafted_mod_of_the_same_family_and_accepts_a_natural_one():
    text = "  - family: IncreasedEnergyShield\n    not_crafted: true\n"
    crafted = roll("JunMaster2ArmourAndEnergyShield1", crafted=True)
    natural = roll("IncreasedEnergyShield1")

    assert not met(text, crafted)
    assert met(text, natural)
    assert met("  - family: IncreasedEnergyShield\n", crafted)
    assert met("  - family: IncreasedEnergyShield\n    not_crafted: false\n", crafted)


def test_a_fractured_mod_satisfies_a_requirement_even_when_it_is_marked_not_crafted():
    fractured = roll("LightningResist2", fractured=True)

    assert met("  - family: LightningResistance\n", fractured)
    assert met("  - family: LightningResistance\n    not_crafted: true\n    min_tier: 3\n", ExplicitMod("LightningResist2", 3, (14,), fractured=True))


def test_a_mod_of_another_family_never_counts():
    assert not met("  - family: LightningResistance\n", roll("ColdResist1"), roll("IncreasedLife1"))


def test_k_of_n_is_met_at_k_and_not_below():
    target = parse(
        """
        requirements:
          - at_least: 2
            of:
              - family: FireResistance
              - family: ColdResistance
              - family: LightningResistance
        """
    )
    fire, cold, lightning = roll("FireResist1"), roll("ColdResist1"), roll("LightningResist1")

    assert not target.is_met_by(belt())
    assert not target.is_met_by(belt(fire))
    assert target.is_met_by(belt(fire, cold))
    assert target.is_met_by(belt(cold, lightning))
    assert target.is_met_by(belt(fire, cold, lightning))


def test_k_of_n_members_keep_their_own_limits():
    target = parse(
        """
        requirements:
          - at_least: 2
            of:
              - family: FireResistance
                min_tier: 1
              - family: ColdResistance
                min_roll: 10
              - family: LightningResistance
        """
    )

    assert not target.is_met_by(belt(roll("FireResist1"), ExplicitMod("ColdResist1", 1, (9,))))
    assert target.is_met_by(belt(roll("FireResist1"), ExplicitMod("ColdResist1", 1, (10,))))
    assert target.is_met_by(belt(ExplicitMod("ColdResist1", 1, (10,)), roll("LightningResist1")))
    assert not target.is_met_by(belt(ExplicitMod("FireResist1", 2, (6,)), roll("ColdResist1")))


def test_nested_k_of_n_counts_a_met_inner_entry_as_one_member():
    target = parse(
        """
        requirements:
          - at_least: 2
            of:
              - family: IncreasedLife
              - at_least: 2
                of:
                  - family: FireResistance
                  - family: ColdResistance
                  - family: LightningResistance
              - family: AllDamage
        """
    )
    life_mod = roll("IncreasedLife1")
    fire, cold = roll("FireResist1"), roll("ColdResist1")
    damage = roll("JunMaster2AllDamage2_", crafted=True)

    assert not target.is_met_by(belt(life_mod, fire))
    assert not target.is_met_by(belt(fire, cold))
    assert target.is_met_by(belt(life_mod, fire, cold))
    assert target.is_met_by(belt(life_mod, damage))
    assert target.is_met_by(belt(fire, cold, damage))


def test_group_members_are_checked_independently_so_one_mod_can_satisfy_two_of_them():
    target = parse(
        """
        requirements:
          - at_least: 2
            of:
              - family: LightningResistance
              - stat: "+(6-11)% to Lightning Resistance"
        """
    )

    assert target.is_met_by(belt(roll("LightningResist1")))
    assert not target.is_met_by(belt(roll("ColdResist1")))


def test_one_of_one_and_all_of_all_groups():
    one = parse("requirements:\n  - at_least: 1\n    of:\n      - family: FireResistance\n")
    both = parse(
        "requirements:\n  - at_least: 2\n    of:\n      - family: FireResistance\n      - family: ColdResistance\n"
    )

    assert one.is_met_by(belt(roll("FireResist1")))
    assert not both.is_met_by(belt(roll("FireResist1")))


def test_a_requirement_needs_exactly_one_selector_and_some_mods():
    with pytest.raises(ValueError):
        Requirement(None, None, frozenset({"IncreasedLife1"}))
    with pytest.raises(ValueError):
        Requirement("IncreasedLife", "+# to maximum Life", frozenset({"IncreasedLife1"}))
    with pytest.raises(ValueError):
        Requirement("IncreasedLife", None, frozenset())


@pytest.mark.parametrize("count", [0, 3, -1])
def test_a_k_of_n_entry_needs_k_between_one_and_its_size(count):
    members = (Requirement("A", None, frozenset({"m"})), Requirement("B", None, frozenset({"n"})))

    with pytest.raises(ValueError):
        KOfN(count, members)
    with pytest.raises(ValueError):
        KOfN(1, ())


def test_the_goal_check_never_needs_the_game_data():
    target = parse("requirements:\n  - family: IncreasedLife\n")

    assert target.is_met_by(item(roll("IncreasedLife1"), base_id=BODY))
