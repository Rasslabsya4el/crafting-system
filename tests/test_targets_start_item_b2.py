"""The start item's `implicits`, `quality` and `veil_offer` keys, and a veiled start mod without tier or values (ticket #141).

Item errors are blamed on the key that holds the offending entry: `start_item.implicits[i]`,
`start_item.quality`, `start_item.veil_offer` or `[i]`. The text of a test starts on line 5; the file is `t.yaml`.
"""

import pytest
from targets_implicits_support import assert_error, parse, parse_error

from crafting_system.items import CatalystType, ImplicitMod, Quality

START = "start_item:\n"
SHOCK = "AvoidShockEldritchImplicit"


def start(body: str) -> str:
    """A `start_item:` block (line 5) whose entries are `body`, indented by two."""
    return START + "".join(f"  {line}\n" for line in body.strip("\n").splitlines())


# -- implicits ------------------------------------------------------------------------------------


def test_an_eldritch_implicit_takes_its_grade_from_the_mod():
    item = parse(start(f"implicits:\n  - mod: {SHOCK}3\n    values: 40")).start_item

    assert item.implicits == (ImplicitMod(f"{SHOCK}3", 3, (40,)),)


def test_a_base_implicit_has_grade_zero_and_a_list_of_values_is_allowed():
    item = parse(start("implicits:\n  - mod: StrengthImplicitBelt1\n    values: [30]")).start_item

    assert item.implicits == (ImplicitMod("StrengthImplicitBelt1", 0, (30,)),)


def test_a_written_grade_is_kept_and_checked_by_the_item():
    item = parse(start(f"implicits:\n  - mod: {SHOCK}2\n    values: 37\n    grade: 2")).start_item

    assert item.implicits[0].grade == 2


def test_an_eldritch_implicit_on_each_side_is_allowed_with_a_base_implicit():
    item = parse(
        start(
            f"""
            implicits:
              - mod: StrengthImplicitBelt1
                values: 25
              - mod: {SHOCK}1
                values: 33
              - mod: ChanceToShockEldritchImplicit2
                values: 10
            """
        )
    ).start_item

    assert {entry.mod_id: entry.grade for entry in item.implicits} == {
        "StrengthImplicitBelt1": 0,
        f"{SHOCK}1": 1,
        "ChanceToShockEldritchImplicit2": 2,
    }


def test_implicits_of_the_start_item_must_be_a_list():
    message = parse_error(start("implicits: 5"))

    assert_error(message, 6, "start_item.implicits", "must be a list of implicit mods", "got 5")


def test_a_start_implicit_must_be_a_mapping():
    message = parse_error(start("implicits:\n  - 5"))

    assert_error(message, 7, "start_item.implicits[0]", "must be a mapping with `mod`, `values`")


def test_a_start_implicit_needs_a_mod():
    message = parse_error(start("implicits:\n  - values: 40"))

    assert_error(message, 7, "start_item.implicits[0].mod", "this key is required but missing")


def test_a_start_implicit_needs_values():
    message = parse_error(start(f"implicits:\n  - mod: {SHOCK}3"))

    assert_error(message, 7, "start_item.implicits[0].values", "this key is required but missing")


def test_an_unknown_start_implicit_key_suggests_the_close_one():
    message = parse_error(start(f"implicits:\n  - mod: {SHOCK}3\n    values: 40\n    grad: 3"))

    assert_error(message, 9, "start_item.implicits[0].grad", "unknown key `grad`", "did you mean `grade`?")


def test_an_unknown_start_implicit_mod_suggests_the_close_ones():
    message = parse_error(start(f"implicits:\n  - mod: {SHOCK}33\n    values: 40"))

    assert_error(message, 7, "start_item.implicits[0].mod", f"`{SHOCK}33` is not a mod id", f"`{SHOCK}3`")


@pytest.mark.parametrize("grade", ["7", "-1", '"x"', "2.5", "true"])
def test_a_written_grade_must_be_a_whole_number_from_0_to_6(grade):
    message = parse_error(start(f"implicits:\n  - mod: {SHOCK}3\n    values: 40\n    grade: {grade}"))

    assert_error(message, 9, "start_item.implicits[0].grade", "must be a whole number from 0 (a base implicit) to 6")


def test_a_grade_that_disagrees_with_the_mod_is_blamed_on_the_entry():
    message = parse_error(start(f"implicits:\n  - mod: {SHOCK}3\n    values: 40\n    grade: 2"))

    assert_error(message, 7, "start_item.implicits[0]", f"{SHOCK}3", "grade 3, not 2")


def test_a_base_implicit_with_a_grade_is_blamed_on_the_entry():
    message = parse_error(start("implicits:\n  - mod: StrengthImplicitBelt1\n    values: 30\n    grade: 1"))

    assert_error(message, 7, "start_item.implicits[0]", "implicit of the base", "grade is 0")


def test_a_mod_that_is_not_an_implicit_is_blamed_on_the_entry():
    message = parse_error(start("implicits:\n  - mod: IncreasedLife1\n    values: 12"))

    assert_error(message, 7, "start_item.implicits[0]", "neither an implicit of the base nor an Eldritch implicit")


def test_an_implicit_of_another_base_is_refused():
    message = parse_error(start("implicits:\n  - mod: IncreasedLifeImplicitBelt1\n    values: 30"))

    assert_error(message, 7, "start_item.implicits[0]", "neither an implicit of the base nor an Eldritch implicit")


@pytest.mark.parametrize("values, cause", [("[40, 41]", "2 rolled value(s)"), ("45", "outside 39 to 41"), ("[]", "0 rolled value(s)")])
def test_wrong_values_are_blamed_on_the_entry(values, cause):
    message = parse_error(start(f"implicits:\n  - mod: {SHOCK}3\n    values: {values}"))

    assert_error(message, 7, "start_item.implicits[0]", f"mod {SHOCK}3", cause)


def test_values_that_are_not_numbers_are_blamed_on_the_key():
    message = parse_error(start(f"implicits:\n  - mod: {SHOCK}3\n    values: [40, x]"))

    assert_error(message, 8, "start_item.implicits[0].values[1]", "must be a whole number")


def test_two_eldritch_implicits_of_one_side_are_blamed_on_the_second_written():
    body = f"implicits:\n  - mod: {SHOCK}3\n    values: 40\n  - mod: {SHOCK}1\n    values: 33"
    message = parse_error(start(body))

    assert_error(message, 9, "start_item.implicits[1]", "both of the exarch side")
    # written the other way round, it is the entry written second again
    body = f"implicits:\n  - mod: {SHOCK}1\n    values: 33\n  - mod: {SHOCK}3\n    values: 40"
    assert_error(parse_error(start(body)), 9, "start_item.implicits[1]", "both of the exarch side")


def test_the_same_implicit_twice_is_refused():
    body = f"implicits:\n  - mod: {SHOCK}3\n    values: 40\n  - mod: {SHOCK}3\n    values: 41"
    message = parse_error(start(body))

    assert_error(message, 9, "start_item.implicits[1]", "is on the item twice")


# -- quality ----------------------------------------------------------------------------------------


def test_the_start_item_can_carry_quality_on_a_belt():
    item = parse(start("quality:\n  type: Intrinsic\n  percent: 20")).start_item

    assert item.quality == Quality(CatalystType.INTRINSIC, 20)


def test_zero_percent_is_no_quality():
    assert parse(start("quality:\n  type: intrinsic\n  percent: 0")).start_item.quality is None


def test_quality_on_a_base_that_takes_none_is_blamed_on_quality():
    text = "base: Iron Greaves\nitem_level: 84\nrequirements:\n  - family: IncreasedLife\n" + start(
        "quality:\n  type: intrinsic\n  percent: 20"
    )

    message = parse_error(text, header=False)

    assert_error(message, 6, "start_item.quality", "needs a base of item class", "Boots")


def test_quality_of_the_start_item_must_be_a_mapping():
    message = parse_error(start("quality: 20"))

    assert_error(message, 6, "start_item.quality", "must be a mapping with `type` and `percent`", "got 20")


@pytest.mark.parametrize("missing", ["type", "percent"])
def test_quality_of_the_start_item_needs_both_keys(missing):
    kept = {"type": "type: intrinsic", "percent": "percent: 20"}
    del kept[missing]
    message = parse_error(start("quality:\n  " + "\n  ".join(kept.values())))

    assert_error(message, 7, f"start_item.quality.{missing}", "this key is required but missing")


def test_an_unknown_start_quality_type_lists_the_allowed_ones():
    message = parse_error(start("quality:\n  type: shiny\n  percent: 20"))

    assert_error(message, 7, "start_item.quality.type", 'got "shiny"', "`intrinsic`", "`sinistral`")


@pytest.mark.parametrize("value", ["-1", "21", '"x"', "7.5"])
def test_quality_percent_must_be_a_whole_number_from_0_to_20(value):
    message = parse_error(start(f"quality:\n  type: intrinsic\n  percent: {value}"))

    assert_error(message, 8, "start_item.quality.percent", "must be a whole number from 0 to 20")


def test_min_percent_is_not_a_start_quality_key():
    message = parse_error(start("quality:\n  type: intrinsic\n  min_percent: 20"))

    assert_error(message, 8, "start_item.quality.min_percent", "unknown key `min_percent`", "`percent`")


def test_an_unknown_start_item_key_names_the_new_ones():
    message = parse_error(start("veil_offers: []"))

    assert_error(message, 6, "start_item.veil_offers", "did you mean `veil_offer`?")


# -- the unveil offer and the veiled placeholder --------------------------------------------------------


def veiled(body: str = "") -> str:
    return start("mods:\n  - mod: VeiledPrefix\n" + body)


def test_a_veiled_start_mod_needs_neither_tier_nor_values():
    item = parse(veiled()).start_item

    (placeholder,) = item.mods
    assert placeholder.mod_id == "VeiledPrefix" and placeholder.tier == 1 and placeholder.values == (1, 1)
    assert item.rarity.value == "rare"


def test_a_written_veiled_seed_is_made_canonical_and_a_written_tier_is_kept():
    item = parse(veiled("    tier: 2\n    values: [1, 777]")).start_item

    assert item.mods[0].values == (1, 1) and item.mods[0].tier == 2


def test_a_veiled_suffix_gets_its_own_canonical_values():
    item = parse(start("mods:\n  - mod: VeiledSuffix")).start_item

    assert item.mods[0].values == (2, 1)


def test_every_other_start_mod_still_needs_a_tier_and_values():
    message = parse_error(start("mods:\n  - mod: IncreasedLife1\n    values: 12"))
    assert_error(message, 7, "start_item.mods[0].tier", "this key is required but missing")

    message = parse_error(start("mods:\n  - mod: IncreasedLife1\n    tier: 3"))
    assert_error(message, 7, "start_item.mods[0].values", "this key is required but missing")


def test_a_veiled_start_mod_still_checks_the_values_it_is_given():
    message = parse_error(veiled("    values: [1]"))

    assert_error(message, 7, "start_item.mods[0]", "VeiledPrefix", "1 rolled value(s)")


def test_a_veil_offer_is_read_and_sorted_by_the_item():
    item = parse(veiled() + "  veil_offer: [UnveiledPrefixMana1, UnveiledPrefixLife1]\n").start_item

    assert item.veil_offer == ("UnveiledPrefixLife1", "UnveiledPrefixMana1")


def test_a_veil_offer_of_the_start_item_must_be_a_list_of_known_ids():
    assert_error(parse_error(start("veil_offer: UnveiledPrefixLife1")), 6, "start_item.veil_offer", "must be a list of mod ids")
    assert_error(parse_error(start("veil_offer: [5]")), 6, "start_item.veil_offer[0]", "must be a mod id")
    message = parse_error(start("veil_offer: [UnveiledPrefixLife1, UnveiledPrefixLife]"))
    assert_error(message, 6, "start_item.veil_offer[1]", "`UnveiledPrefixLife` is not a mod id", "`UnveiledPrefixLife1`")


def test_an_offer_without_a_placeholder_is_blamed_on_the_offer_key():
    message = parse_error(start("veil_offer: [UnveiledPrefixLife1]"))

    assert_error(message, 6, "start_item.veil_offer", "exactly one veiled placeholder", "it has 0")


def test_an_offer_of_the_wrong_domain_is_blamed_on_that_entry():
    message = parse_error(veiled() + "  veil_offer: [UnveiledPrefixLife1, IncreasedLife1]\n")

    assert_error(message, 8, "start_item.veil_offer[1]", "IncreasedLife1", "domain item, not unveiled")


def test_an_offered_suffix_for_a_prefix_placeholder_is_blamed_on_that_entry():
    message = parse_error(veiled() + "  veil_offer: [UnveiledSuffixSpeed1]\n")

    assert_error(message, 8, "start_item.veil_offer[0]", "UnveiledSuffixSpeed1", "suffix")


def test_two_offered_mods_of_one_family_are_blamed_on_the_offer():
    message = parse_error(veiled() + "  veil_offer: [UnveiledPrefixAilments1, UnveiledPrefixAilments2]\n")

    assert_error(message, 8, "start_item.veil_offer[1]", "share the family AvoidAilments")


def test_an_offer_listing_a_mod_twice_is_blamed_on_the_repeat():
    message = parse_error(veiled() + "  veil_offer: [UnveiledPrefixLife1, UnveiledPrefixLife1]\n")

    assert_error(message, 8, "start_item.veil_offer[1]", "offered twice")


def test_an_offer_of_more_than_three_mods_is_blamed_on_the_offer_key():
    ids = "[UnveiledPrefixAilments1, UnveiledPrefixLife1, UnveiledPrefixMana1, UnveiledPrefixAilments2]"
    message = parse_error(veiled() + f"  veil_offer: {ids}\n")

    assert_error(message, 8, "start_item.veil_offer", "at most 3")


def test_explicit_mod_errors_are_still_blamed_on_the_mod():
    message = parse_error(start("implicits:\n  - mod: StrengthImplicitBelt1\n    values: 30\nmods:\n  - mod: IncreasedLife1\n    tier: 1\n    values: 99"))

    assert_error(message, 10, "start_item.mods[0]", "IncreasedLife1")
