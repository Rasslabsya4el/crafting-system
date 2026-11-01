"""The three Foulborn orbs (ticket #279, ADR-0043, ADR-0040, ADR-0041): "Done when" and where it is shown.

* The three are in the catalog only when strands are on: `test_the_three_kinds_are_in_the_catalog_only_when_strands_are_on` and the two after it.
* The kept-tier list for N = 1 to 13 at 0 strands: `test_the_kept_tiers_of_a_foulborn_orb_at_0_strands_are_the_wikis_list_for_one_to_thirteen_tiers`
  (the orb's own draw on a toy table of N tiers, not only the formula).
* Ceilings 32, 48 and the Exalted row: `test_the_spend_ceilings_...` (the Exalted row is the claim's 46, 52, 56, 60, 62, 66 that the amendment of
  ADR-0041 put in place of the 29/40/47/58/62 of the ticket text).
* The plain version's refusals hold: `test_a_foulborn_orb_refuses_exactly_what_its_plain_version_refuses`.
* Priced from a fixture price file, unpriced means not offered and reported: the three `..._price_...` tests.
* The kernel equals enumeration: the contract suite runs every kind of the catalog (`test_actions_contract.py`), and `check_action` is
  asked of the three here on 0-strand and stranded items; `test_the_kernel_sees_the_foulborn_cut` shows the cut reaches the kernel.
"""

import dataclasses
from fractions import Fraction
from pathlib import Path

import pytest
from abstraction_pool import AMULET, DAMAGE_1, LIFE_1, SMALL, roll, small_item
from contract_support import CONTRACT_DATA, check_action, fixture_items

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    AugmentationOrb,
    ExaltedOrb,
    FoulbornAugmentationOrb,
    FoulbornExaltedOrb,
    FoulbornRegalOrb,
    RegalOrb,
    Spent,
    catalog,
    kinds,
    strands_after,
)
from crafting_system.actions.errors import ActionError
from crafting_system.actions.cut import Cut, rollable_tiers
from crafting_system.actions.pool import build_pool
from crafting_system.cli._offers import offer_of, price_offers
from crafting_system.data import Weight
from crafting_system.items import Item, Rarity
from crafting_system.prices.price_file import load_price_file, missing_prices
from crafting_system.rules import get_rule

PRICES = Path(__file__).parent / "fixtures" / "strands" / "foulborn_prices.json"
FOULBORN = (FoulbornAugmentationOrb(), FoulbornRegalOrb(), FoulbornExaltedOrb())
KIND_NAMES = ("foulborn-augmentation-orb", "foulborn-regal-orb", "foulborn-exalted-orb")
WIKI_LIST = [1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6, 7, 7]  # kept tiers for N = 1..13 eligible tiers (ADR-0040)


def foulborn_names(actions) -> set[str]:
    return {type(action).__name__ for action in actions if type(action).__name__.startswith("Foulborn")}


# --- the catalog: the three exist only when strands are on ---------------------------------------------------------------------


def test_the_three_kinds_are_registered_and_flagged_as_needing_strands():
    registered = {entry.name: entry for entry in kinds()}

    assert all(registered[name].needs_strands for name in KIND_NAMES)
    assert not any(entry.needs_strands for entry in kinds() if entry.name not in KIND_NAMES)  # no other kind is gated
    assert [registered[name].opt_in for name in KIND_NAMES] == [False, False, True]  # like the plain orbs: the Exalted Orb only when named


def test_the_three_kinds_are_in_the_catalog_only_when_strands_are_on():
    items = fixture_items()
    for name in ("normal", "magic", "rare_junk"):
        item = items[name]

        assert foulborn_names(catalog(CONTRACT_DATA, item)) == set(), name  # strands off: none of the three, whatever the item
        assert foulborn_names(catalog(CONTRACT_DATA, item, planner_only=True)) == set(), name
        assert foulborn_names(catalog(CONTRACT_DATA, item, strands=True)) >= {"FoulbornExaltedOrb"}, name
    assert foulborn_names(catalog(CONTRACT_DATA, items["magic"], strands=True)) == {
        "FoulbornAugmentationOrb", "FoulbornRegalOrb", "FoulbornExaltedOrb",
    }  # fmt: skip
    assert foulborn_names(catalog(CONTRACT_DATA, items["rare_junk"], strands=True)) == {"FoulbornExaltedOrb"}  # a rare item takes only the Exalted


def test_an_item_that_holds_strands_turns_them_on_by_itself():
    stranded = fixture_items()["magic_stranded"]

    assert foulborn_names(catalog(CONTRACT_DATA, stranded)) == {"FoulbornAugmentationOrb", "FoulbornRegalOrb", "FoulbornExaltedOrb"}
    assert foulborn_names(catalog(CONTRACT_DATA, stranded, strands=False)) == foulborn_names(catalog(CONTRACT_DATA, stranded))


def test_the_plain_catalog_is_the_same_with_strands_on_apart_from_the_gated_kinds():
    gated = {type(action).__name__ for action in FOULBORN}
    for item in fixture_items().values():
        off = catalog(CONTRACT_DATA, item)
        on = catalog(CONTRACT_DATA, item, strands=True)

        assert [a for a in on if type(a).__name__ not in gated] == [a for a in off if type(a).__name__ not in gated]  # no answer of B1 to B4 changes
        if not item.memory_strands:
            assert not gated & {type(a).__name__ for a in off}


def test_an_exalted_foulborn_orb_is_opt_in_so_a_planner_offer_set_names_it():
    item = fixture_items()["magic"]

    assert foulborn_names(catalog(CONTRACT_DATA, item, strands=True, planner_only=True)) == {"FoulbornAugmentationOrb", "FoulbornRegalOrb"}
    assert foulborn_names(catalog(CONTRACT_DATA, item, strands=True, planner_only=True, names={"foulborn-exalted-orb"})) == {"FoulbornExaltedOrb"}


# --- the cut ---------------------------------------------------------------------------------------------------------------------


def toy_data(tiers: int):
    """SMALL with the Lightning Resistance suffix table replaced by `tiers` tiers of equal weight, at levels 1, 6, 11, ... (the highest last)."""
    template = SMALL.mods["LightningResist1"]
    mods = {mod_id: mod for mod_id, mod in SMALL.mods.items() if mod.type != "LightningResistance"}
    for number in range(1, tiers + 1):
        mod_id = f"ToyResist{number}"
        mods[mod_id] = dataclasses.replace(
            template, id=mod_id, required_level=1 + 5 * (number - 1), spawn_weights=(Weight("amulet", 1000), Weight("default", 0))
        )
    return dataclasses.replace(SMALL, mods=mods)


def toy_resists(data, outcomes) -> list[str]:
    return sorted((entry.mod.id for family in outcomes.pool for entry in family.mods if entry.mod.type == "LightningResistance"), key=lambda i: int(i[9:]))


@pytest.mark.parametrize("tiers", range(1, 14))
def test_the_kept_tiers_of_a_foulborn_orb_at_0_strands_are_the_wikis_list_for_one_to_thirteen_tiers(tiers):
    data = toy_data(tiers)
    item = Item.build(data, base_id=AMULET, item_level=84, rarity=Rarity.MAGIC, mods=(roll(LIFE_1),))  # a prefix: the suffix table is open
    kept = WIKI_LIST[tiers - 1]

    for action in (FoulbornAugmentationOrb(), FoulbornRegalOrb()):
        outcomes = action.outcomes(data, item)

        assert toy_resists(data, outcomes) == [f"ToyResist{n}" for n in range(tiers - kept + 1, tiers + 1)], (action, tiers)  # the K highest
    assert FoulbornExaltedOrb().cut_of(data, item.changed(data, rarity=Rarity.RARE)).kept(tiers) == kept
    assert [rollable_tiers(n, 0, foulborn=True) for n in range(1, 14)] == WIKI_LIST
    assert not isinstance(FoulbornAugmentationOrb().outcomes(data, item), Spent)  # 0 strands: nothing to spend


def test_the_plain_orb_on_the_same_toy_table_keeps_every_tier():
    data = toy_data(8)
    item = Item.build(data, base_id=AMULET, item_level=84, rarity=Rarity.MAGIC, mods=(roll(LIFE_1),))

    assert len(toy_resists(data, AugmentationOrb().outcomes(data, item))) == 8
    assert len(toy_resists(data, FoulbornAugmentationOrb().outcomes(data, item))) == 5  # D = 175: 4 highest of 8 would be wrong, 5 is the wiki


@pytest.mark.parametrize("strands", [1, 10, 21, 40, 70, 100])
def test_on_a_stranded_item_a_foulborn_orb_cuts_the_count_before_the_craft_plus_seventy_five(strands):
    item = small_item(roll(LIFE_1), rarity=Rarity.MAGIC, memory_strands=strands)

    for action, plain in ((FoulbornAugmentationOrb(), AugmentationOrb()), (FoulbornRegalOrb(), RegalOrb())):
        outcomes = action.outcomes(SMALL, item)

        assert isinstance(outcomes, Spent) and outcomes.before == strands
        assert outcomes.pool == build_pool(SMALL, outcomes.retained, cut=Cut(strands, foulborn=True))
        if strands + 30 <= 100:  # a Cut holds at most 100 strands; the formula itself is defined above (the wiki's table runs to 122)
            assert outcomes.pool == build_pool(SMALL, outcomes.retained, cut=Cut(strands + 30))  # the same as 30 strands more (ADR-0040)
        assert plain.outcomes(SMALL, item).pool == build_pool(SMALL, outcomes.retained, cut=Cut(strands))


def test_the_foulborn_cut_of_a_second_orb_is_the_same_rule_applied_to_the_count_that_is_left():
    item = small_item(roll(LIFE_1), rarity=Rarity.MAGIC, memory_strands=50)
    first = FoulbornAugmentationOrb().outcomes(SMALL, item)

    for left in first.strands_after:  # whatever the first orb spent, the next draws from the cut of what remains
        again = FoulbornRegalOrb().outcomes(SMALL, dataclasses.replace(item, memory_strands=left))
        expected = build_pool(SMALL, again.retained, cut=Cut(left, foulborn=True))

        assert again.pool == expected


# --- the spend -------------------------------------------------------------------------------------------------------------------


def test_the_spend_ceilings_are_32_for_augmentation_48_for_regal_and_the_claims_row_for_exalted():
    assert FoulbornAugmentationOrb().strand_use(None).spend.ceilings == (32,)
    assert FoulbornRegalOrb().strand_use(None).spend.ceilings == (48,)
    row = FoulbornExaltedOrb().strand_use(None).spend
    assert [row.ceiling(mods) for mods in range(6)] == [46, 52, 56, 60, 62, 66] == list(get_rule("foulborn.exalted_spend_by_mod_count").value)
    assert row.ceiling(9) == 66  # a larger number of mods takes the last
    # the scaling of the ticket text (the plain row times 62/34: 29, 40, 47, 58, 62) is the draft that the amendment of ADR-0041 dropped
    assert [row.ceiling(mods) for mods in range(1, 6)] != [29, 40, 47, 58, 62]
    assert get_rule("foulborn.spend_ranges").value == {"augmentation": 32, "regal": 48}


def test_the_spend_is_uniform_and_a_spend_larger_than_the_count_empties_it():
    item = small_item(roll(LIFE_1), rarity=Rarity.MAGIC, memory_strands=100)

    assert dict(strands_after(FoulbornAugmentationOrb().outcomes(SMALL, item), 100)) == {left: Fraction(1, 33) for left in range(68, 101)}
    assert dict(strands_after(FoulbornRegalOrb().outcomes(SMALL, item), 100)) == {left: Fraction(1, 49) for left in range(52, 101)}
    few = dataclasses.replace(item, memory_strands=3)
    after = strands_after(FoulbornAugmentationOrb().outcomes(SMALL, few), 3)
    assert after == {0: Fraction(30, 33), 1: Fraction(1, 33), 2: Fraction(1, 33), 3: Fraction(1, 33)}  # a spend of 3 to 32 leaves 0


def test_the_exalted_ceiling_follows_the_mods_on_the_item_before_the_craft():
    items = fixture_items()
    two, four = items["rare_stranded"], items["rare_four_stranded"]

    assert (len(two.mods), len(four.mods)) == (2, 4)
    assert FoulbornExaltedOrb().outcomes(CONTRACT_DATA, two).law.ceiling(2) == 56
    assert FoulbornExaltedOrb().outcomes(CONTRACT_DATA, four).law.ceiling(4) == 62
    assert max(strands_after(FoulbornExaltedOrb().outcomes(CONTRACT_DATA, two), 100)) == 100
    assert min(strands_after(FoulbornExaltedOrb().outcomes(CONTRACT_DATA, two), 100)) == 100 - 56
    assert min(strands_after(ExaltedOrb().outcomes(CONTRACT_DATA, two), 100)) == 100 - 26  # the plain orb's own row, for contrast


# --- the plain version's refusals hold -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("foul", "plain"), [(FoulbornAugmentationOrb(), AugmentationOrb()), (FoulbornRegalOrb(), RegalOrb()), (FoulbornExaltedOrb(), ExaltedOrb())])
def test_a_foulborn_orb_refuses_exactly_what_its_plain_version_refuses(foul, plain):
    checked = refused = 0
    for name, item in fixture_items().items():
        for variant in (item, item.changed(CONTRACT_DATA, corrupted=True)):
            try:
                expected = plain.outcomes(CONTRACT_DATA, variant)
            except ActionError as error:
                with pytest.raises(type(error)):
                    foul.outcomes(CONTRACT_DATA, variant)
                refused += 1
            else:
                result = foul.outcomes(CONTRACT_DATA, variant)  # applies where the plain orb applies
                assert len(result.components) == len(expected.components), name
            checked += 1
    assert refused and refused < checked  # both refusals and acceptances were exercised


def test_a_corrupted_item_and_the_wrong_rarity_are_refused_with_the_same_errors_as_the_plain_orb():
    items = fixture_items()
    corrupted_magic = items["magic"].changed(CONTRACT_DATA, corrupted=True)

    for foul in (FoulbornAugmentationOrb(), FoulbornRegalOrb()):
        with pytest.raises(ActionError, match="corrupted"):
            foul.outcomes(CONTRACT_DATA, corrupted_magic)
        with pytest.raises(ActionError, match="magic"):
            foul.outcomes(CONTRACT_DATA, items["rare_junk"])  # works on a magic item only
    with pytest.raises(ActionError, match="rare"):
        FoulbornExaltedOrb().outcomes(CONTRACT_DATA, items["magic"])


# --- the price -------------------------------------------------------------------------------------------------------------------


def test_each_orb_is_a_currency_in_the_price_file_under_its_own_name():
    assert [dict(action.resources(None)) for action in FOULBORN] == [
        {"Foulborn Orb of Augmentation": 1}, {"Foulborn Regal Orb": 1}, {"Foulborn Exalted Orb": 1},
    ]  # fmt: skip
    assert [action.label(None) for action in FOULBORN] == ["Foulborn Orb of Augmentation", "Foulborn Regal Orb", "Foulborn Exalted Orb"]


def test_a_priced_foulborn_orb_costs_its_market_price_from_the_fixture_price_file():
    prices = load_price_file(PRICES)
    offers = [offer_of(action, action.label(None)) for action in FOULBORN[:2]]

    priced, dropped = price_offers(offers, prices)

    assert not dropped
    assert {entry.offer.label: entry.cost for entry in priced} == {"Foulborn Orb of Augmentation": 4.5, "Foulborn Regal Orb": 12.0}
    assert prices.prices["Foulborn Orb of Augmentation"].chaos > prices.prices["Orb of Augmentation"].chaos  # priced apart from the plain orb


def test_an_unpriced_foulborn_orb_is_not_offered_and_the_drop_names_the_missing_price():
    prices = load_price_file(PRICES)  # the fixture file has no Foulborn Exalted Orb
    offers = [offer_of(action, action.label(None)) for action in (*FOULBORN, ExaltedOrb())]

    priced, dropped = price_offers(offers, prices)

    assert [(entry.label, entry.missing) for entry in dropped] == [("Foulborn Exalted Orb", ("Foulborn Exalted Orb",))]
    assert {entry.offer.label for entry in priced} == {"Foulborn Orb of Augmentation", "Foulborn Regal Orb", "Exalted Orb"}
    assert missing_prices([name for action in FOULBORN for name in action.resources(None)], prices.prices) == ["Foulborn Exalted Orb"]


def test_a_price_file_with_no_foulborn_price_drops_all_three_and_keeps_the_plain_orbs():
    prices = load_price_file(PRICES)
    bare = dataclasses.replace(prices, prices={name: entry for name, entry in prices.prices.items() if not name.startswith("Foulborn")})
    offers = [offer_of(action, action.label(None)) for action in (*FOULBORN, AugmentationOrb(), RegalOrb(), ExaltedOrb())]

    priced, dropped = price_offers(offers, bare)

    assert {entry.label for entry in dropped} == {action.label(None) for action in FOULBORN}
    assert {entry.offer.label for entry in priced} == {"Orb of Augmentation", "Regal Orb", "Exalted Orb"}


# --- the claims ------------------------------------------------------------------------------------------------------------------


def test_the_declarations_cite_the_foulborn_and_strand_claims_apart_from_claims():
    for action in FOULBORN:
        cited = action.strand_claims(None)

        assert {"memory_strands.rollable_tiers", "foulborn.bonus_is_added_to_the_strand_denominator", "foulborn.zero_strand_cut_matches_eleven_strands"} <= cited
        assert "foulborn.effect_tier_cull" in cited and "foulborn.availability" in cited
        assert not {claim for claim in action.claims(None) if claim.startswith(("memory_strands.", "foulborn."))}  # kept out of `claims`
    assert "foulborn.spend_ranges" in FoulbornAugmentationOrb().strand_claims(None) and "foulborn.spend_ranges" in FoulbornRegalOrb().strand_claims(None)
    assert "foulborn.exalted_spend_by_mod_count" in FoulbornExaltedOrb().strand_claims(None)
    assert "foulborn.exalted_spend_by_mod_count" not in FoulbornAugmentationOrb().strand_claims(None)


# --- the kernel ------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("action", FOULBORN, ids=lambda a: a.label(None))
def test_the_contract_suite_checks_pass_on_items_with_and_without_strands(action):
    applied = 0
    for name, item in fixture_items().items():
        applied += bool(check_action(action, item))  # the kernel equals brute force at 0 strands; with strands the declarations and the sampler
    assert applied >= 2  # the magic items for the first two orbs, the rare ones for the Exalted


def test_the_kernel_sees_the_foulborn_cut():
    # A magic amulet with a life mod and the three-tier Lightning Resistance suffix table (levels 1, 13, 25 in SMALL): the plain orb keeps all
    # three, the Foulborn orb keeps two at D = 175, so the two kernels differ on the state, and each equals the enumeration of its own draw.
    item = small_item(roll(LIFE_1), rarity=Rarity.MAGIC)
    goal = Goal((Wanted(frozenset({"LightningResist3"})),))
    ab = Abstraction(SMALL, goal, item.base_id, item.item_level, [AugmentationOrb(), FoulbornAugmentationOrb()])
    state = ab.compress(item)

    plain, foul = ab.kernel(state, AugmentationOrb()), ab.kernel(state, FoulbornAugmentationOrb())
    expected = {}
    for chance, result in _finished(FoulbornAugmentationOrb().outcomes(SMALL, item)):
        expected[ab.compress(result)] = expected.get(ab.compress(result), Fraction(0)) + chance

    assert dict(foul) == expected and sum(foul.values()) == 1
    assert dict(plain) != dict(foul)


def _finished(outcomes):
    from contract_support import finished

    return finished(outcomes, SMALL)


# --- no answer without strands changes (the checker's finding on the left-out list) ---------------------------------------------


def test_an_offer_set_with_named_kinds_and_no_strands_does_not_mention_the_foulborn_kinds():
    from crafting_system.cli._offers import offers_for

    item = fixture_items()["magic"]
    goal = Goal((Wanted(frozenset({"LightningResist3"})),))

    chosen = offers_for(CONTRACT_DATA, goal, item.base_id, item, ["chaos-orb"])

    mentioned = {name for left in chosen.left_out for name in left.labels}
    assert mentioned and not mentioned & set(KIND_NAMES)


def test_naming_a_foulborn_kind_in_a_target_is_refused_until_the_planner_plans_with_strands():
    from crafting_system.cli._offers import offers_for

    item = fixture_items()["magic"]
    goal = Goal((Wanted(frozenset({"LightningResist3"})),))

    with pytest.raises(ValueError, match="foulborn-regal-orb"):
        offers_for(CONTRACT_DATA, goal, item.base_id, item, ["foulborn-regal-orb"])
