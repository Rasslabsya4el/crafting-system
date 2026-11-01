"""The Tempering Orb and the Tailoring Orb as exact actions (ticket #239, ADR-0050, ADR-0051).

"Done when", test by test:

* the contract suite passes unedited on both kinds: `test_the_orbs_meet_the_contract_on_their_fixture_items` runs `check_action` on the items
  of `contract_fixtures_enchant.py` (the shared suite runs the same through the catalog and names no kind);
* the share of an enchant (`chance_enchant`, the weight share) equals the hand-computed one: `test_the_share_of_each_enchant_is_its_weight_over_the_total`
  on the real-shaped slice and `test_the_closed_forms_of_adr_0051_on_the_real_pools` on the whole dump;
* a second click replaces the first: `test_a_second_click_replaces_the_first`;
* each refusal has a test: the wrong class, the corrupted item, the mirrored item (the model holds none), a pool the claims do not cover;
* the orb's price is read from a fixture price file, and a missing price is dropped with its name: `test_the_price_comes_from_the_price_file...`.

`chance_all` is the contract's (explicit mods held by the result), so it is 0 for an enchant: `test_chance_all_counts_explicit_mods_only`.
"""

import dataclasses
import datetime
from fractions import Fraction

import pytest
from abstraction_support import real_game_data
from contract_support import check_action, extra_fixture_items
from enchant_support import (
    ARMOUR_EXTRA_SLOT,
    ARMOUR_LINKED,
    ARMOUR_REQUIREMENTS,
    BODY,
    CLEAN_LIFE,
    DATA,
    LIFE,
    LIFE_ATTRIBUTE,
    LIFE_LINKED,
    LIFE_NO_RED,
    LIFE_REQUIREMENTS,
    LIFE_REQUIREMENTS_PENALTY,
    LIFE_RESISTANCE,
    LIFE_RESISTANCE_PENALTY,
    LIFE_SOCKET_PENALTY,
    QUALITY_LIFE,
    RESISTANCE_LIFE_PENALTY,
    SWORD,
    WEAPON_CRITICAL,
    WEAPON_EXTRA_SLOT,
)
from items_support import AMULET
from items_support import roll as fixture_roll

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    ActionError,
    AnnulmentOrb,
    EnchantOutcomes,
    NotApplicableError,
    OutOfScopeError,
    TailoringOrb,
    TemperingOrb,
    catalog,
    enchant_pool,
    kinds,
)
from crafting_system.cli._offers import offer_of, price_offers
from crafting_system.items import EnchantClass, Item, Rarity, enchant_info
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.rules import rule_by_id

LIFE_MOD, RESIST = "IncreasedLife1", "ColdResist1"
# The hand oracle: the weight of every armour enchant of the slice, written from the counts of ADR-0051 and not read from the claim.
ARMOUR_WEIGHTS = {
    LIFE: Fraction(752),
    LIFE_ATTRIBUTE: Fraction(233, 6),  # six-plus-six: 6 enchants cover 233 sample items
    LIFE_REQUIREMENTS: Fraction(119, 3),  # 6% plus 25% less requirements: 3 enchants, 119 items
    LIFE_RESISTANCE: Fraction(233, 6),
    LIFE_RESISTANCE_PENALTY: Fraction(126, 7),  # penalty hybrid: 7 enchants, 126 items
    LIFE_REQUIREMENTS_PENALTY: Fraction(104, 5),  # 200% requirements: 5 enchants, 104 items
    LIFE_SOCKET_PENALTY: Fraction(111, 5),  # -3 maximum sockets: 5 enchants, 111 items
    LIFE_LINKED: Fraction(22, 5),  # 6% plus All Sockets Linked: 5 enchants, 22 items
    LIFE_NO_RED: Fraction(666, 15),  # 8% plus no colour: 15 enchants, 666 items
    RESISTANCE_LIFE_PENALTY: Fraction(126, 7),
    ARMOUR_REQUIREMENTS: Fraction(456),
    ARMOUR_LINKED: Fraction(45),
    ARMOUR_EXTRA_SLOT: Fraction(36),
}
WEAPON_WEIGHTS = {WEAPON_CRITICAL: Fraction(453), WEAPON_EXTRA_SLOT: Fraction(32)}


def body(*, enchantment: str | None = None, rarity: Rarity = Rarity.RARE, corrupted: bool = False) -> Item:
    mods = (fixture_roll(LIFE_MOD), fixture_roll(RESIST)) if rarity is Rarity.RARE else ()
    return Item.build(DATA, base_id=BODY, item_level=84, rarity=rarity, mods=mods, enchantment=enchantment, corrupted=corrupted)


def sword(*, enchantment: str | None = None, rarity: Rarity = Rarity.RARE, corrupted: bool = False) -> Item:
    mods = (fixture_roll(LIFE_MOD),) if rarity is Rarity.RARE else ()
    return Item.build(DATA, base_id=SWORD, item_level=84, rarity=rarity, mods=mods, enchantment=enchantment, corrupted=corrupted)


def price_file(**prices: float) -> PriceFile:
    entries = {name.replace("_", " "): PriceEntry(chaos, "fixture") for name, chaos in prices.items()}
    return PriceFile("Test", datetime.datetime(2026, 11, 1, tzinfo=datetime.UTC), 300.0, entries)


# --- the contract suite, unedited ------------------------------------------------------------------------


def test_the_orbs_meet_the_contract_on_their_fixture_items():
    items = extra_fixture_items()
    asked = {"tailoring": ["body_armour_enchanted", "body_armour_normal"], "tempering": ["sword_rare", "sword_magic_enchanted"]}
    orbs = {"tailoring": TailoringOrb(), "tempering": TemperingOrb()}
    for kind_name, names in asked.items():
        for name in names:
            assert kind_name in items[name].kinds
            assert check_action(orbs[kind_name], items[name].item, items[name].data), (kind_name, name)


def test_the_contract_refuses_the_wrong_class_the_same_way_in_the_kernel():
    items = extra_fixture_items()
    # check_action returns False where the action refuses the item, after the kernel is checked to refuse it for the same reason
    assert not check_action(TemperingOrb(), items["body_armour_enchanted"].item, items["body_armour_enchanted"].data)
    assert not check_action(TailoringOrb(), items["sword_rare"].item, items["sword_rare"].data)


def test_the_kinds_are_limited_to_their_class_and_are_no_planner_kinds():
    registered = {entry.name: entry for entry in kinds()}
    assert registered["tempering"].applies_only_to == "weapon" and registered["tailoring"].applies_only_to == "body armour"
    for name in ("tempering", "tailoring"):
        assert not registered[name].planner and registered[name].why_not
    assert catalog(DATA, sword()).count(TemperingOrb()) == 1 and TailoringOrb() not in catalog(DATA, sword())
    assert catalog(DATA, body()).count(TailoringOrb()) == 1 and TemperingOrb() not in catalog(DATA, body())
    assert not [action for action in catalog(DATA, body(), planner_only=True) if isinstance(action, TailoringOrb)]
    amulet = Item.build(DATA, base_id=AMULET, item_level=84, rarity=Rarity.RARE)
    assert not [action for action in catalog(DATA, amulet) if isinstance(action, (TemperingOrb, TailoringOrb))]


# --- one draw with the weights ------------------------------------------------------------------------------


@pytest.mark.parametrize("enchantment", [None, ARMOUR_EXTRA_SLOT, LIFE])
def test_the_share_of_each_enchant_is_its_weight_over_the_total(enchantment):
    outcomes = TailoringOrb().outcomes(DATA, body(enchantment=enchantment))
    total = sum(ARMOUR_WEIGHTS.values())
    assert isinstance(outcomes, EnchantOutcomes) and set(outcomes.shares) == set(ARMOUR_WEIGHTS)
    for mod_id, weight in ARMOUR_WEIGHTS.items():
        assert outcomes.chance_enchant([mod_id]) == weight / total == outcomes.shares[mod_id], mod_id
    assert sum(outcomes.shares.values()) == 1


def test_the_weapon_pool_of_the_slice_is_drawn_with_the_weapon_counts():
    outcomes = TemperingOrb().outcomes(DATA, sword())
    total = sum(WEAPON_WEIGHTS.values())
    assert dict(outcomes.shares) == {mod_id: weight / total for mod_id, weight in WEAPON_WEIGHTS.items()}
    assert outcomes.shares[WEAPON_CRITICAL] == Fraction(453, 485)


def test_the_chance_of_a_set_of_enchants_is_the_sum_of_their_shares_and_a_quality_enchant_is_never_drawn():
    outcomes = TailoringOrb().outcomes(DATA, body())
    total = sum(ARMOUR_WEIGHTS.values())
    assert outcomes.chance_enchant(CLEAN_LIFE) == sum(ARMOUR_WEIGHTS[mod_id] for mod_id in CLEAN_LIFE) / total
    assert outcomes.chance_enchant([QUALITY_LIFE]) == 0 and outcomes.chance_enchant([LIFE_MOD]) == 0
    assert outcomes.chance_enchant([]) == 0
    with pytest.raises(ValueError, match="NotAMod is not in the game data"):
        outcomes.chance_enchant(["NotAMod"])


def test_the_draw_has_one_result_per_enchant_and_changes_nothing_but_the_enchantment():
    start = body(enchantment=LIFE_NO_RED)
    outcomes = TailoringOrb().outcomes(DATA, start)
    assert len(outcomes.results) == len(ARMOUR_WEIGHTS)
    for _, result in outcomes.results:
        assert dataclasses.replace(result, enchantment=None) == dataclasses.replace(start, enchantment=None)
    assert outcomes.distribution(lambda mod: mod.id) == {frozenset(): 1}
    assert not outcomes.fractures


def test_a_second_click_replaces_the_first():
    start = body()
    first = TailoringOrb().outcomes(DATA, start)
    for _, clicked in first.results:
        assert clicked.enchantment is not None
        second = TailoringOrb().outcomes(DATA, clicked)
        # the shares do not depend on the old enchantment: the draw is with replacement, the new one replaces the old
        assert dict(second.shares) == dict(first.shares)
        for _, again in second.results:
            assert again.enchantment is not None and again.mods == clicked.mods
    held = body(enchantment=ARMOUR_LINKED)
    replaced = {result.enchantment for _, result in TailoringOrb().outcomes(DATA, held).results}
    assert replaced == set(ARMOUR_WEIGHTS)  # the old one comes back only as one of the draws, at its own share
    assert held.enchantment == ARMOUR_LINKED  # the item in hand is not changed


def test_the_sampler_replaces_the_enchantment_and_keeps_the_mods():
    import random

    rng = random.Random(7)
    held = sword(enchantment=WEAPON_EXTRA_SLOT)
    seen = {TemperingOrb().outcomes(DATA, held).sample(rng).enchantment for _ in range(200)}
    assert seen == set(WEAPON_WEIGHTS)


def test_chance_all_counts_explicit_mods_only():
    outcomes = TailoringOrb().outcomes(DATA, body(enchantment=LIFE))
    assert outcomes.chance_all([LIFE_MOD]) == 1 and outcomes.chance_all([LIFE_MOD, RESIST]) == 1
    assert outcomes.chance_all([LIFE]) == 0  # an enchantment is no explicit mod; its chance is `chance_enchant`
    assert outcomes.chance_enchant([LIFE]) == outcomes.shares[LIFE] > 0


# --- the refusals --------------------------------------------------------------------------------------------


def test_a_tempering_orb_refuses_what_is_not_a_weapon_and_names_the_class():
    for item in (body(), Item.build(DATA, base_id=AMULET, item_level=84, rarity=Rarity.RARE)):
        with pytest.raises(NotApplicableError, match="Tempering Orb works on a weapon only, and this item is a"):
            TemperingOrb().outcomes(DATA, item)


def test_a_tailoring_orb_refuses_what_is_not_a_body_armour_and_names_the_class():
    for item in (sword(), Item.build(DATA, base_id=AMULET, item_level=84, rarity=Rarity.RARE)):
        with pytest.raises(NotApplicableError, match="Tailoring Orb works on a body armour only, and this item is a"):
            TailoringOrb().outcomes(DATA, item)


def test_the_orbs_refuse_a_corrupted_item_as_out_of_scope_and_name_the_claim():
    with pytest.raises(OutOfScopeError, match="corrupted.*Tailoring Orb.*enchantment.mirrored_and_corruption"):
        TailoringOrb().outcomes(DATA, body(corrupted=True))
    with pytest.raises(OutOfScopeError, match="corrupted.*Tempering Orb.*enchantment.mirrored_and_corruption"):
        TemperingOrb().outcomes(DATA, sword(corrupted=True))
    # a corrupted item that already holds an enchantment keeps it (the claim) and is still refused
    with pytest.raises(OutOfScopeError):
        TailoringOrb().outcomes(DATA, body(enchantment=LIFE, corrupted=True))


def test_a_mirrored_item_is_not_in_the_item_model_so_the_refusal_waits_for_the_field():
    # `enchantment.mirrored_and_corruption`: the game refuses a mirrored item. The model has no such item (as `divine.py` and `fracture.py`
    # say), so there is nothing to refuse; the day `Item` gets a mirrored field this test fails, and the orbs must refuse it.
    assert "mirrored" not in {field.name for field in dataclasses.fields(Item)}


def test_a_pool_enchant_with_no_weight_in_the_claim_is_out_of_scope_and_named():
    stray = dataclasses.replace(DATA.mods[LIFE], id="ArmourEnchantmentHeistNotInTheSample1")
    data = dataclasses.replace(DATA, mods={**DATA.mods, stray.id: stray})
    with pytest.raises(OutOfScopeError, match="body_armour_weight_classes gives the body armour enchant ArmourEnchantmentHeistNotInTheSample1 no weight"):
        TailoringOrb().outcomes(data, body())
    weapon = dataclasses.replace(DATA.mods[WEAPON_CRITICAL], id="WeaponEnchantmentHeistNotInTheSample1")
    data = dataclasses.replace(DATA, mods={**DATA.mods, weapon.id: weapon})
    with pytest.raises(OutOfScopeError, match="weapon_weights_depend_on_tag gives the weapon enchant WeaponEnchantmentHeistNotInTheSample1 no weight"):
        TemperingOrb().outcomes(data, sword())


def test_a_game_data_without_enchants_has_no_pool():
    from items_support import DATA as PLAIN

    plain_sword = Item.build(PLAIN, base_id=SWORD, item_level=84, rarity=Rarity.RARE)
    with pytest.raises(OutOfScopeError, match="no weapon enchantment of the Tempering or Tailoring pool"):
        TemperingOrb().outcomes(PLAIN, plain_sword)
    with pytest.raises(ActionError):
        enchant_pool(PLAIN, EnchantClass.BODY_ARMOUR)


def test_the_pools_of_the_slice_hold_the_enchants_the_item_model_calls_pool_enchants():
    assert {mod.id for mod, _ in enchant_pool(DATA, EnchantClass.BODY_ARMOUR)} == set(ARMOUR_WEIGHTS)  # not the white sockets, not the quality enchant
    assert {mod.id for mod, _ in enchant_pool(DATA, EnchantClass.WEAPON)} == set(WEAPON_WEIGHTS)
    assert enchant_info(DATA.mods[ARMOUR_EXTRA_SLOT]).extra_slot


# --- the price ----------------------------------------------------------------------------------------------------


def test_the_price_comes_from_the_price_file_by_the_name_of_the_orb():
    for orb, item in ((TemperingOrb(), sword()), (TailoringOrb(), body())):
        assert orb.resources(DATA) == {orb.label(DATA): 1}
        offer = offer_of(orb, orb.label(DATA), DATA, item)
        priced, dropped = price_offers([offer], price_file(**{orb.label(DATA).replace(" ", "_"): 12.5}))
        assert not dropped and priced[0].cost == 12.5
        assert priced[0].parts == ((orb.label(DATA), 1, 12.5, "fixture"),)


def test_a_missing_price_is_a_refusal_that_names_the_orb():
    offers = [offer_of(TemperingOrb(), "Tempering Orb", DATA, sword()), offer_of(TailoringOrb(), "Tailoring Orb", DATA, body())]
    priced, dropped = price_offers(offers, price_file(Tailoring_Orb=3.0))
    assert [entry.label for entry in priced] == ["Tailoring Orb"]
    assert [(entry.label, entry.missing) for entry in dropped] == [("Tempering Orb", ("Tempering Orb",))]
    priced, dropped = price_offers(offers, price_file())
    assert not priced and [entry.missing for entry in dropped] == [("Tempering Orb",), ("Tailoring Orb",)]


# --- the claims ---------------------------------------------------------------------------------------------------------------


def test_each_orb_names_its_own_claims_and_the_approximate_ones_among_them():
    tempering, tailoring = TemperingOrb().claims(DATA), TailoringOrb().claims(DATA)
    assert "enchantment.weapon_weights_depend_on_tag" in tempering and "enchantment.body_armour_weight_classes" not in tempering
    assert "enchantment.body_armour_weight_classes" in tailoring and "enchantment.weapon_weights_depend_on_tag" not in tailoring
    assert "tempering_orb.cost" in tempering and "tailoring_orb.cost" not in tempering
    assert "tailoring_orb.cost" in tailoring and "tempering_orb.cost" not in tailoring
    for claims in (tempering, tailoring):
        assert {"enchantment.pool_is_weighted", "enchantment.extra_crafted_modifier_curio_display_rate"} <= claims
        assert all(rule_by_id(claim_id).approximate_reason for claim_id in claims if rule_by_id(claim_id).approximate)
    assert rule_by_id("enchantment.armour_pool_54").approximate and "enchantment.armour_pool_54" in tailoring


def test_the_declarations_set_the_enchantment_and_read_nothing_of_it():
    for orb in (TemperingOrb(), TailoringOrb()):
        reads, adds = orb.reads(DATA), orb.adds(DATA, None)
        assert adds.enchantment and not reads.enchantment
        assert not reads.item_state and not adds.item_state and not adds.draws and adds.named == frozenset()


def test_the_orb_costs_the_compressed_state_nothing():
    goal = Goal((Wanted(frozenset({"FireResist1"})),))
    plain = Abstraction(DATA, goal, BODY, 84, [AnnulmentOrb()])
    with_orb = Abstraction(DATA, goal, BODY, 84, [AnnulmentOrb(), TailoringOrb()])
    start = body()
    state = with_orb.compress(start)
    assert state == plain.compress(start) and with_orb.sets_enchantment
    assert dict(with_orb.kernel(state, TailoringOrb())) == {state: 1}  # the enchantment is no part of the state: a click leads back to it


# --- the whole dump -------------------------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real():
    return real_game_data()


def share(real, base_id: str, orb, mod_ids) -> Fraction:
    start = Item.build(real, base_id=base_id, item_level=84, rarity=Rarity.RARE)
    return orb.outcomes(real, start).chance_enchant(mod_ids)


ARMOUR_BASE = "Metadata/Items/Armours/BodyArmours/BodyStr1"
SWORD_BASE = "Metadata/Items/Weapons/OneHandWeapons/OneHandSwords/OneHandSword1"


def tagged(real, item_class: EnchantClass, tag: str, *, clean: bool) -> set[str]:
    """The pool enchants that raise `tag`: the clean ones, or (`clean=False`, the "any" of ADR-0051) the clean ones and the "plus no colour" ones.

    The second set is what the closed form "any Life: 23.2%" counts: a positive magnitude on the tag, no downside, no link or socket-count rider.
    """
    found = set()
    for mod_id, mod in real.mods.items():
        info = enchant_info(mod)
        if info is None or info.item_class is not item_class or info.kind.value != "pool" or tag not in info.tags:
            continue
        stats = {stat.id for stat in mod.stats}
        no_colour_only = not info.downside and not stats & {"local_all_sockets_linked", "local_maximum_sockets_+"}
        if info.clean or (not clean and no_colour_only):
            found.add(mod_id)
    return found


def test_the_pools_of_the_dump_are_136_and_54_and_every_enchant_has_a_weight(real):
    assert len(enchant_pool(real, EnchantClass.WEAPON)) == 136 and len(enchant_pool(real, EnchantClass.BODY_ARMOUR)) == 54
    for orb, base in ((TemperingOrb(), SWORD_BASE), (TailoringOrb(), ARMOUR_BASE)):
        outcomes = orb.outcomes(real, Item.build(real, base_id=base, item_level=84, rarity=Rarity.RARE))
        assert sum(outcomes.shares.values()) == 1 and all(chance > 0 for chance in outcomes.shares.values())


# The closed forms of ADR-0051: the share of a clean tag per click, and 1/share orbs. The armour ones use the kind means, so they agree
# with the figures shown within the rounding of their digits.
@pytest.mark.parametrize(
    ("item_class", "tag", "clean", "per_click", "orbs"),
    [
        (EnchantClass.BODY_ARMOUR, "Life", True, 0.201, 5.0),
        (EnchantClass.BODY_ARMOUR, "Life", False, 0.232, 4.3),
        (EnchantClass.BODY_ARMOUR, "Resistance", True, 0.144, 7.0),
        (EnchantClass.BODY_ARMOUR, "Defence", True, 0.187, 5.35),
        (EnchantClass.WEAPON, "Critical", True, 0.118, 8.5),
        (EnchantClass.WEAPON, "Speed", True, 0.127, 7.9),
        (EnchantClass.WEAPON, "Physical", True, 0.094, 10.6),
    ],
)
def test_the_closed_forms_of_adr_0051_on_the_real_pools(real, item_class, tag, clean, per_click, orbs):
    orb, base = (TailoringOrb(), ARMOUR_BASE) if item_class is EnchantClass.BODY_ARMOUR else (TemperingOrb(), SWORD_BASE)
    wanted = tagged(real, item_class, tag, clean=clean)
    assert wanted
    chance = float(share(real, base, orb, wanted))
    assert chance == pytest.approx(per_click, abs=0.0006)
    assert 1 / chance == pytest.approx(orbs, abs=0.06)


def test_a_clean_life_enchant_set_of_the_dump_is_the_four_of_the_slice(real):
    assert len(tagged(real, EnchantClass.BODY_ARMOUR, "Life", clean=True)) == len(CLEAN_LIFE) == 4


def test_the_shield_and_the_quiver_take_neither_orb(real):
    for item_class in ("Shield", "Quiver"):
        base = next(base for base in real.base_items.values() if base.item_class == item_class)
        item = Item.build(real, base_id=base.id, item_level=84, rarity=Rarity.RARE)
        with pytest.raises(NotApplicableError, match=f"Tempering Orb works on a weapon only, and this item is a {item_class}"):
            TemperingOrb().outcomes(real, item)
        with pytest.raises(NotApplicableError, match=f"Tailoring Orb works on a body armour only, and this item is a {item_class}"):
            TailoringOrb().outcomes(real, item)
    assert not [a for a in catalog(real, item) if isinstance(a, (TemperingOrb, TailoringOrb))]

