"""Target `implicits:` and `quality:` (ticket #141): the resolver, the schema errors with file, line and key, and the checks.

The text of a test starts on line 5 (see `targets_implicits_support`); the file is called `t.yaml`.
"""

import pytest
from implicits_support import implicit, make
from targets_implicits_support import AVOID_SHOCK, TEXTED, assert_error, parse, parse_error

from crafting_system.items import CatalystType, ImplicitMod, Quality
from crafting_system.targets import ImplicitRequirement, QualityRequirement
from crafting_system.targets.resolve import Resolver, Unresolved

GRADES = {"AvoidShockEldritchImplicit1", "AvoidShockEldritchImplicit2", "AvoidShockEldritchImplicit3"}
VARIANTS = {"AvoidShockEldritchImplicitUniquePresence4", "AvoidShockEldritchImplicitPinnaclePresence2"}


@pytest.fixture(scope="module")
def resolver():
    return Resolver(TEXTED)


# -- the resolver -------------------------------------------------------------------------------


def test_an_implicit_stat_text_resolves_to_implicit_mods_only(resolver):
    found = resolver.implicit_mods_for_stat(AVOID_SHOCK)

    assert found == GRADES
    assert "ChanceToAvoidShockEssence7" not in found and "AvoidShockInfluence1" not in found


def test_a_prefix_or_suffix_text_never_returns_an_implicit_and_is_unchanged(resolver):
    found = resolver.mods_for_stat(AVOID_SHOCK)

    assert found == {"ChanceToAvoidShockEssence7", "AvoidShockInfluence1"}


def test_an_implicit_family_resolves_to_implicit_mods_only_while_the_explicit_lookup_still_sees_both(resolver):
    assert resolver.implicit_mods_for_family("AvoidShock") == GRADES
    assert {"AvoidShockInfluence1", *GRADES} <= resolver.mods_for_family("AvoidShock")


def test_presence_variants_are_skipped_unless_asked_for(resolver):
    assert not VARIANTS & resolver.implicit_mods_for_stat(AVOID_SHOCK)
    assert not VARIANTS & resolver.implicit_mods_for_family("AvoidShock")
    assert resolver.implicit_mods_for_stat(AVOID_SHOCK, with_presence=True) == GRADES | VARIANTS
    assert resolver.implicit_mods_for_family("AvoidShock", with_presence=True) == GRADES | VARIANTS


def test_a_selector_that_only_has_presence_variants_keeps_them(resolver):
    assert resolver.implicit_mods_for_family("Lone") == {"LoneEldritchImplicitUniquePresence1"}
    assert resolver.implicit_mods_for_stat("5% lone") == {"LoneEldritchImplicitUniquePresence1"}


def test_the_implicits_of_a_base_are_in_the_universe(resolver):
    assert resolver.implicit_mods_for_stat("+# to Strength") == {"StrengthImplicitBelt1"}
    assert resolver.implicit_mods_for_family("Strength") == {"StrengthImplicitBelt1"}
    assert resolver.implicit_mods_for_family("IncreasedLife") == {"IncreasedLifeImplicitBelt1"}  # not the Life prefixes


def test_an_unknown_implicit_text_shows_the_closest_implicit_texts(resolver):
    with pytest.raises(Unresolved) as caught:
        resolver.implicit_mods_for_stat("#% chance to Avoid being Shoked")

    message = str(caught.value)
    assert 'no implicit mod has the text "#% chance to Avoid being Shoked"' in message
    assert '"#% chance to Avoid being Shocked"' in message


def test_a_text_that_is_nothing_like_an_implicit_says_so(resolver):
    with pytest.raises(Unresolved, match="no implicit mod in the game data has the text"):
        resolver.implicit_mods_for_stat("zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz")


def test_the_text_of_a_prefix_points_to_requirements(resolver):
    with pytest.raises(Unresolved, match="text of a prefix or suffix, not of an implicit.*requirements"):
        resolver.implicit_mods_for_stat("#% increased Attack Speed")


def test_a_family_id_written_as_a_stat_points_to_the_family_key(resolver):
    with pytest.raises(Unresolved, match="is a family id; write `family: AvoidShock`"):
        resolver.implicit_mods_for_stat("AvoidShock")


def test_an_unknown_implicit_family_suggests_the_close_one(resolver):
    with pytest.raises(Unresolved, match="not the family id of any implicit mod.*did you mean `AvoidShock`"):
        resolver.implicit_mods_for_family("AvoidShok")


def test_a_family_with_no_implicit_says_so(resolver):
    with pytest.raises(Unresolved, match="`LightningResistance` is a family id, but none of its mods is an implicit"):
        resolver.implicit_mods_for_family("LightningResistance")


# -- implicits: what is read ----------------------------------------------------------------------


def test_an_implicit_requirement_by_stat_selects_the_grades_and_keeps_the_rolls():
    target = parse(
        f"""
        implicits:
          - stat: "{AVOID_SHOCK}"
            min_grade: 2
            min_roll: 36
        """
    )

    (wanted,) = target.implicits
    assert wanted == ImplicitRequirement(None, AVOID_SHOCK, frozenset(GRADES), 2, (36,))
    assert target.quality is None


def test_an_implicit_requirement_by_family_with_a_range_written_in_full():
    target = parse(
        """
        implicits:
          - stat: "(10-20)% chance to Avoid being Shocked"
          - family: Strength
        """
    )

    assert [wanted.mod_ids for wanted in target.implicits] == [frozenset(GRADES), frozenset({"StrengthImplicitBelt1"})]
    assert target.implicits[1].family == "Strength" and target.implicits[1].stat is None


def test_mod_names_one_grade_and_a_presence_variant_is_reached_only_by_mod():
    target = parse(
        f"""
        implicits:
          - stat: "{AVOID_SHOCK}"
            mod: AvoidShockEldritchImplicit2
          - family: AvoidShock
            mod: AvoidShockEldritchImplicitUniquePresence4
            min_roll: [52, null]
        """
    )

    plain, variant = target.implicits
    assert plain.mod_ids == {"AvoidShockEldritchImplicit2"}
    assert variant.mod_ids == {"AvoidShockEldritchImplicitUniquePresence4"} and variant.min_roll == (52, None)


def test_a_wanted_roll_of_a_presence_variant_needs_one_entry_per_stat():
    message = parse_error(
        """
        implicits:
          - family: AvoidShock
            mod: AvoidShockEldritchImplicitUniquePresence4
            min_roll: 52
        """
    )

    assert_error(message, 8, "implicits[0].min_roll", "the mod has 2 stats", "[null, null]")


# -- implicits: the errors ---------------------------------------------------------------------


@pytest.mark.parametrize("value", ["5", "[]"])
def test_implicits_must_be_a_non_empty_list(value):
    message = parse_error(f"implicits: {value}\n")

    expected = "must hold at least one implicit requirement" if value == "[]" else "must be a list of implicit requirements"
    assert_error(message, 5, "implicits", expected)


def test_an_implicit_entry_must_be_a_mapping():
    message = parse_error("implicits:\n  - 7\n")

    assert_error(message, 6, "implicits[0]", "must be a mapping", "got 7")


def test_an_implicit_entry_needs_a_family_or_a_stat():
    message = parse_error("implicits:\n  - min_roll: 40\n")

    assert_error(message, 6, "implicits[0]", "`family: <family id>`", "`stat:")


def test_an_implicit_entry_with_both_family_and_stat_is_refused():
    message = parse_error(f'implicits:\n  - family: AvoidShock\n    stat: "{AVOID_SHOCK}"\n')

    assert_error(message, 6, "implicits[0]", "either `family` or `stat`, not both")


def test_an_unknown_implicit_key_suggests_the_close_one():
    message = parse_error(f'implicits:\n  - stat: "{AVOID_SHOCK}"\n    min_gradee: 2\n')

    assert_error(message, 7, "implicits[0].min_gradee", "unknown key `min_gradee`", "did you mean `min_grade`?")


def test_an_unknown_implicit_key_with_no_close_match_lists_the_allowed_ones():
    message = parse_error(f'implicits:\n  - stat: "{AVOID_SHOCK}"\n    qqqqqqqq: 1\n')

    assert_error(message, 7, "implicits[0].qqqqqqqq", "`family`", "`min_grade`", "`min_roll`")


def test_a_requirement_key_that_means_nothing_for_an_implicit_is_unknown():
    message = parse_error(f'implicits:\n  - stat: "{AVOID_SHOCK}"\n    min_tier: 1\n')

    assert_error(message, 7, "implicits[0].min_tier", "unknown key `min_tier`")


def test_an_unknown_implicit_stat_is_reported_at_its_line():
    message = parse_error('implicits:\n  - stat: "#% chance to Avoid being Shoked"\n')

    assert_error(message, 6, "implicits[0].stat", "no implicit mod has the text", '"#% chance to Avoid being Shocked"')


def test_an_explicit_suffix_text_is_not_an_implicit():
    message = parse_error('implicits:\n  - stat: "#% increased Attack Speed"\n')

    assert_error(message, 6, "implicits[0].stat", "text of a prefix or suffix, not of an implicit")


def test_an_unknown_implicit_family_is_reported_at_its_line():
    message = parse_error("implicits:\n  - family: AvoidShok\n")

    assert_error(message, 6, "implicits[0].family", "not the family id of any implicit mod", "`AvoidShock`")


def test_the_implicit_selector_must_not_be_an_empty_text():
    message = parse_error('implicits:\n  - stat: "  "\n')

    assert_error(message, 6, "implicits[0].stat", "must be non-empty text")


def test_mod_must_belong_to_the_selector_and_the_error_explains_presence_variants():
    message = parse_error(f'implicits:\n  - stat: "{AVOID_SHOCK}"\n    mod: StrengthImplicitBelt1\n')

    assert_error(message, 7, "implicits[0].mod", "`StrengthImplicitBelt1` is not an implicit mod of the stat", "Presence")


def test_mod_cannot_name_the_explicit_suffix_of_the_same_text():
    message = parse_error(f'implicits:\n  - stat: "{AVOID_SHOCK}"\n    mod: ChanceToAvoidShockEssence7\n')

    assert_error(message, 7, "implicits[0].mod", "`ChanceToAvoidShockEssence7` is not an implicit mod")


@pytest.mark.parametrize("value", ["0", "7", '"x"', "2.5", "true", "[3]"])
def test_min_grade_must_be_a_whole_number_from_1_to_6(value):
    message = parse_error(f'implicits:\n  - stat: "{AVOID_SHOCK}"\n    min_grade: {value}\n')

    assert_error(message, 7, "implicits[0].min_grade", "must be a whole number from 1 (Lesser) to 6 (Perfect)")


def test_min_grade_is_refused_on_a_base_implicit_and_says_why():
    message = parse_error("implicits:\n  - family: Strength\n    min_grade: 2\n")

    assert_error(message, 7, "implicits[0].min_grade", "only an Eldritch implicit has a grade", "`StrengthImplicitBelt1`")


def test_min_grade_above_the_best_grade_of_the_chosen_mod_is_refused():
    message = parse_error(f'implicits:\n  - stat: "{AVOID_SHOCK}"\n    mod: AvoidShockEldritchImplicit2\n    min_grade: 3\n')

    assert_error(message, 8, "implicits[0].min_grade", "3 is above the best grade any of these mods has, which is 2")


def test_min_roll_above_the_best_roll_is_refused():
    message = parse_error(f'implicits:\n  - stat: "{AVOID_SHOCK}"\n    min_roll: 42\n')

    assert_error(message, 7, "implicits[0].min_roll", "42 is above the best roll any of these mods can give, which is 41")


@pytest.mark.parametrize("value", ['"x"', "40.5", "[40, 41]", "true"])
def test_min_roll_of_the_wrong_shape_is_refused(value):
    message = parse_error(f'implicits:\n  - stat: "{AVOID_SHOCK}"\n    min_roll: {value}\n')

    assert message.startswith("t.yaml:7: ") and ": implicits[0].min_roll" in message, message


def test_a_list_min_roll_checks_each_entry():
    message = parse_error(
        """
        implicits:
          - family: AvoidShock
            mod: AvoidShockEldritchImplicitUniquePresence4
            min_roll: [60, null]
        """
    )

    assert_error(message, 8, "implicits[0].min_roll[0]", "60 is above the best roll", "53")


def test_the_second_entry_of_the_list_is_the_one_named():
    message = parse_error(f'implicits:\n  - stat: "{AVOID_SHOCK}"\n  - family: Nothing\n')

    assert_error(message, 7, "implicits[1].family", "not the family id of any implicit mod")


# -- quality: what is read, the errors -------------------------------------------------------------


def test_quality_is_read_with_any_case_of_the_type():
    target = parse("quality:\n  type: Intrinsic\n  min_percent: 20\n")

    assert target.quality == QualityRequirement(CatalystType.INTRINSIC, 20)


@pytest.mark.parametrize("catalyst", [catalyst.value for catalyst in CatalystType])
def test_every_catalyst_type_is_accepted(catalyst):
    assert parse(f"quality:\n  type: {catalyst.upper()}\n  min_percent: 1\n").quality.type.value == catalyst


def test_quality_must_be_a_mapping():
    message = parse_error("quality: 20\n")

    assert_error(message, 5, "quality", "must be a mapping with `type` and `min_percent`", "got 20")


@pytest.mark.parametrize("missing", ["type", "min_percent"])
def test_quality_needs_both_keys(missing):
    kept = {"type": "type: intrinsic", "min_percent": "min_percent: 20"}
    del kept[missing]
    message = parse_error("quality:\n  " + "\n  ".join(kept.values()) + "\n")

    assert_error(message, 6, f"quality.{missing}", "this key is required but missing")


def test_an_unknown_catalyst_type_lists_the_allowed_ones():
    message = parse_error("quality:\n  type: shiny\n  min_percent: 20\n")

    assert_error(message, 6, "quality.type", 'got "shiny"', "`intrinsic`", "`abrasive`", "`dextral`")


@pytest.mark.parametrize("value", ["0", "21", '"x"', "12.5", "true", "-1"])
def test_min_percent_must_be_a_whole_number_from_1_to_20(value):
    message = parse_error(f"quality:\n  type: intrinsic\n  min_percent: {value}\n")

    assert_error(message, 7, "quality.min_percent", "must be a whole number from 1 to 20")


def test_an_unknown_quality_key_suggests_the_close_one():
    message = parse_error("quality:\n  type: intrinsic\n  min_percnt: 20\n")

    assert_error(message, 7, "quality.min_percnt", "unknown key `min_percnt`", "did you mean `min_percent`?")


def test_the_start_item_key_percent_is_not_a_target_quality_key():
    message = parse_error("quality:\n  type: intrinsic\n  percent: 20\n")

    assert_error(message, 7, "quality.percent", "unknown key `percent`", "did you mean `min_percent`?")


def test_the_new_top_level_keys_are_suggested_for_a_typo():
    message = parse_error("implicit:\n  - family: Strength\n")

    assert_error(message, 5, "implicit", "unknown key `implicit`", "did you mean `implicits`?")


# -- is_met_by and unmet ---------------------------------------------------------------------------


def holding(*entries: ImplicitMod, quality: Quality | None = None):
    return make(implicits=entries, quality=quality)


def exarch(grade: int, value: int) -> ImplicitMod:
    return ImplicitMod(f"AvoidShockEldritchImplicit{grade}", grade, (value,))


def avoid_shock(**kwargs) -> ImplicitRequirement:
    return ImplicitRequirement(None, AVOID_SHOCK, frozenset(GRADES), **kwargs)


def test_an_implicit_requirement_needs_one_of_its_mods_on_the_item():
    wanted = avoid_shock()

    assert wanted.is_met_by(holding(exarch(1, 33)))
    assert not wanted.is_met_by(holding(implicit("StrengthImplicitBelt1")))
    assert not wanted.is_met_by(holding())
    assert not wanted.is_met_by(make())


def test_a_presence_variant_does_not_meet_a_plain_selector():
    variant = ImplicitMod("AvoidShockEldritchImplicitUniquePresence4", 4, (51, 1))

    assert not avoid_shock().is_met_by(holding(variant))
    assert ImplicitRequirement("AvoidShock", None, frozenset({variant.mod_id})).is_met_by(holding(variant))


@pytest.mark.parametrize("grade, value, met", [(3, 40, True), (3, 39, False), (3, 41, True), (2, 38, False), (1, 35, False)])
def test_the_roll_must_hold_on_the_value_of_the_implicit(grade, value, met):
    assert avoid_shock(min_roll=(40,)).is_met_by(holding(exarch(grade, value))) is met


@pytest.mark.parametrize("grade, met", [(1, False), (2, True), (3, True)])
def test_the_grade_must_reach_the_minimum(grade, met):
    assert avoid_shock(min_grade=2).is_met_by(holding(exarch(grade, {1: 33, 2: 36, 3: 39}[grade]))) is met


def test_grade_and_roll_must_hold_on_the_same_implicit():
    wanted = avoid_shock(min_grade=3, min_roll=(40,))

    assert wanted.is_met_by(holding(exarch(3, 40)))
    assert not wanted.is_met_by(holding(exarch(3, 39)))
    assert not wanted.is_met_by(holding(exarch(2, 38)))


def test_a_none_in_the_roll_is_any_value():
    variant = ImplicitMod("AvoidShockEldritchImplicitUniquePresence4", 4, (51, 1))
    wanted = ImplicitRequirement("AvoidShock", None, frozenset({variant.mod_id}), min_roll=(None, 1))

    assert wanted.is_met_by(holding(variant))
    assert not ImplicitRequirement("AvoidShock", None, frozenset({variant.mod_id}), min_roll=(52, None)).is_met_by(
        holding(variant)
    )
    assert not ImplicitRequirement("AvoidShock", None, frozenset({variant.mod_id}), min_roll=(51,)).is_met_by(
        holding(variant)
    )  # one wanted roll for two stats cannot match


def test_an_implicit_requirement_names_exactly_one_selector_and_some_mod():
    with pytest.raises(ValueError, match="exactly one"):
        ImplicitRequirement("AvoidShock", AVOID_SHOCK, frozenset(GRADES))
    with pytest.raises(ValueError, match="exactly one"):
        ImplicitRequirement(None, None, frozenset(GRADES))
    with pytest.raises(ValueError, match="at least one mod id"):
        ImplicitRequirement("AvoidShock", None, frozenset())


@pytest.mark.parametrize(
    "held, met",
    [
        (Quality(CatalystType.INTRINSIC, 20), True),
        (Quality(CatalystType.INTRINSIC, 19), False),
        (Quality(CatalystType.ABRASIVE, 20), False),
        (Quality(CatalystType.INTRINSIC, 0), False),
        (None, False),
    ],
)
def test_quality_needs_the_type_and_at_least_the_percent(held, met):
    assert QualityRequirement(CatalystType.INTRINSIC, 20).is_met_by(holding(quality=held)) is met


def test_a_lower_minimum_percent_accepts_a_higher_quality():
    assert QualityRequirement(CatalystType.INTRINSIC, 10).is_met_by(holding(quality=Quality(CatalystType.INTRINSIC, 14)))


def test_a_quality_requirement_must_be_well_formed():
    with pytest.raises(ValueError):
        QualityRequirement("intrinsic", 20)
    with pytest.raises(ValueError):
        QualityRequirement(CatalystType.INTRINSIC, 0)


def test_unmet_lists_requirements_then_implicits_then_quality():
    target = parse(
        f"""
        implicits:
          - stat: "{AVOID_SHOCK}"
            min_roll: 40
          - family: Strength
        quality:
          type: intrinsic
          min_percent: 20
        """
    )
    nothing = make()
    only_strength = holding(implicit("StrengthImplicitBelt1"), quality=Quality(CatalystType.INTRINSIC, 20))

    assert target.unmet(nothing) == (*target.requirements, *target.implicits, target.quality)
    assert target.unmet(only_strength) == (*target.requirements, target.implicits[0])
    assert not target.is_met_by(only_strength)


def test_a_target_is_met_when_requirements_implicits_and_quality_all_are():
    target = parse(
        f"""
        implicits:
          - stat: "{AVOID_SHOCK}"
            min_roll: 40
        quality:
          type: intrinsic
          min_percent: 20
        """
    )
    life = TEXTED.mods["IncreasedLife1"]
    from crafting_system.items import ExplicitMod

    done = make(
        ExplicitMod("IncreasedLife1", 9, (life.stats[0].min,)),
        implicits=(exarch(3, 40),),
        quality=Quality(CatalystType.INTRINSIC, 20),
    )

    assert target.unmet(done) == () and target.is_met_by(done)
    assert target.unmet(make(*done.mods, implicits=(exarch(3, 39),), quality=done.quality)) == (target.implicits[0],)
    assert target.unmet(make(*done.mods, implicits=done.implicits)) == (target.quality,)


def test_a_target_without_the_new_keys_has_none_and_behaves_as_before():
    target = parse("")

    assert target.implicits == () and target.quality is None
    assert target.unmet(make()) == target.requirements
