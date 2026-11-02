"""Burns: the re-anoint, the declarations of the Blessed Orb, the Chromatic Orb and the quality currencies, and the legality of a burn (ticket #295, B8-3; ADR-0056).

"Done when" of the ticket, line by line (the price lines are in `test_prices_foresight.py`):

* A jewel has no burn: `test_a_jewel_has_no_burn_at_any_state`.
* A quality burn is legal only where the state keeps quality: `test_a_quality_burn_is_legal_only_where_the_state_keeps_quality`.
* A quality burn is not offered at maximum quality: `test_a_quality_burn_is_not_offered_at_maximum_quality`.
* A Chromatic burn lists its socket assumption among the approximate inputs: `test_a_chromatic_burn_lists_its_socket_assumption_among_the_approximate_inputs`
  (the claim, and the list a plan makes for it, `approximate_inputs_of`), with the assumption itself in
  `test_a_chromatic_burn_counts_an_item_that_states_no_sockets_as_having_one`.
* A burn is absent from the plain offers of every state: `test_a_burn_is_absent_from_the_plain_offers_of_every_state`.
* A Blessed Orb burn is refused with an Eldritch implicit and when a requirement reads the implicit: `test_a_blessed_burn_is_refused_*`.
* With two legal burns the cheaper at the file's prices is the one used: `test_with_two_legal_burns_the_cheaper_at_the_prices_of_the_file_is_the_one_used`
  (in `test_prices_foresight.py`, where the prices are).

The contract suite asks the re-anoint as it asks every kind (`test_actions_contract.py`, unchanged); the wrapper `Burn` is not a kind, so its contract checks are run here.
"""

from types import SimpleNamespace

import pytest
from abstraction_pool import LIFE_1
from burn_support import AVOID_SHOCK_1, DATA, JEWEL, RANGED_RING, RING, STRENGTH, belt, build, helmet, sword
from contract_support import check_action
from implicits_support import BELT, BOOTS, implicit
from items_support import AMULET
from sockets_support import HELMET, SWORD, socketed, white

from crafting_system.abstraction import Goal, Wanted
from crafting_system.actions import (
    ApplyQualityCurrency,
    BlessedOrb,
    Burn,
    BurnKeeps,
    ChromaticOrb,
    NotApplicableError,
    OutOfScopeError,
    ReAnoint,
    burns_at,
    catalog,
    kinds,
)
from crafting_system.cli._marking import approximate_inputs_of
from crafting_system.cli._offers import offers_for
from crafting_system.items import ImplicitMod, Item, Rarity
from crafting_system.prices.price_names import ARMOURERS_SCRAP, BLACKSMITHS_WHETSTONE, CLEAR_OIL
from crafting_system.rules import rule_by_id

EVERY_KEEPS = [BurnKeeps(quality=q, implicits=i, enchantment=e) for q in (False, True) for i in (False, True) for e in (False, True)]


# --- the re-anoint -----------------------------------------------------------------------------------------


def test_a_re_anoint_is_a_burn_of_a_ring_or_an_amulet_that_changes_nothing_the_model_keeps():
    for item in (build(RING), build(AMULET)):
        outcomes = ReAnoint().outcomes(DATA, item)
        ((chance, result),) = outcomes.results
        assert chance == 1 and result == item  # no mod, no implicit, no quality: the enchantment is no part of the state (ADR-0050)
        assert outcomes.chance_all([]) == 1
    assert ReAnoint().burn(DATA) is True
    assert ReAnoint().resources(DATA) == {CLEAR_OIL: 3}
    assert ReAnoint().adds(DATA, None).enchantment is True and ReAnoint().adds(DATA, None).named == frozenset()


def test_a_re_anoint_is_refused_on_anything_but_a_ring_or_an_amulet_and_on_a_corrupted_item():
    for item in (helmet(), sword(), build(BELT), build(JEWEL)):
        with pytest.raises(NotApplicableError, match="ring or an amulet"):
            ReAnoint().outcomes(DATA, item)
    with pytest.raises(NotApplicableError, match="corrupted"):
        ReAnoint().outcomes(DATA, build(RING, corrupted=True))


def test_a_re_anoint_is_refused_where_the_target_requires_the_enchantment_it_would_replace():
    ring = build(RING)
    assert ReAnoint().burn_refusal(DATA, ring, BurnKeeps()) is None
    reason = ReAnoint().burn_refusal(DATA, ring, BurnKeeps(enchantment=True))
    assert reason is not None and "enchantment" in reason
    assert [burn.action for burn in burns_at(DATA, ring, BurnKeeps(enchantment=True))] == []
    assert [burn.action for burn in burns_at(DATA, ring, BurnKeeps())] == [ReAnoint()]


def test_the_re_anoint_meets_the_contract_wrapped_as_a_burn():
    assert check_action(Burn(ReAnoint()), build(AMULET), DATA)
    assert check_action(ReAnoint(), build(AMULET), DATA)


# --- a jewel ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("keeps", EVERY_KEEPS)
def test_a_jewel_has_no_burn_at_any_state(keeps):
    jewel = build(JEWEL)
    assert burns_at(DATA, jewel, keeps) == ()
    for action in (ReAnoint(), BlessedOrb(), ChromaticOrb(), ApplyQualityCurrency(ARMOURERS_SCRAP), ApplyQualityCurrency(BLACKSMITHS_WHETSTONE)):
        assert action.burn_refusal(DATA, jewel, keeps) is not None  # each candidate refuses a jewel by its own rule too


def test_the_jewels_of_the_real_data_have_no_burn():
    from abstraction_support import real_game_data

    data = real_game_data()
    for base_id in ("Metadata/Items/Jewels/JewelInt", "Metadata/Items/Jewels/JewelAbyssMelee"):
        jewel = Item.build(data, base_id=base_id, item_level=84, rarity=Rarity.RARE)
        assert burns_at(data, jewel, BurnKeeps(quality=True, implicits=True, enchantment=True)) == ()


# --- a quality burn --------------------------------------------------------------------------------------


def test_a_quality_burn_is_legal_only_where_the_state_keeps_quality():
    scrap, whetstone = ApplyQualityCurrency(ARMOURERS_SCRAP), ApplyQualityCurrency(BLACKSMITHS_WHETSTONE)
    armour, weapon = helmet(10), sword(10)
    assert scrap.burn(DATA) and whetstone.burn(DATA)
    assert scrap in [burn.action for burn in burns_at(DATA, armour, BurnKeeps(quality=True))]
    assert scrap not in [burn.action for burn in burns_at(DATA, armour, BurnKeeps(quality=False))]
    reason = scrap.burn_refusal(DATA, armour, BurnKeeps())
    assert reason is not None and "does not keep the quality" in reason
    assert whetstone in [burn.action for burn in burns_at(DATA, weapon, BurnKeeps(quality=True))]
    assert whetstone not in [burn.action for burn in burns_at(DATA, weapon, BurnKeeps())]
    assert not any(isinstance(burn.action, ApplyQualityCurrency) for burn in burns_at(DATA, helmet(0), BurnKeeps()))  # no quality kept at 0%, either
    # the right currency for the class: a Whetstone is no burn of an armour, a Scrap none of a weapon
    assert whetstone.burn_refusal(DATA, armour, BurnKeeps(quality=True)) is not None
    assert scrap.burn_refusal(DATA, weapon, BurnKeeps(quality=True)) is not None


@pytest.mark.parametrize("percent", [20, 25, 30])
def test_a_quality_burn_is_not_offered_at_maximum_quality(percent):
    keeps = BurnKeeps(quality=True)
    for item, currency in ((helmet(percent), ARMOURERS_SCRAP), (sword(percent), BLACKSMITHS_WHETSTONE)):
        action = ApplyQualityCurrency(currency)
        reason = action.burn_refusal(DATA, item, keeps)
        assert reason is not None and "20%" in reason
        assert action not in [burn.action for burn in burns_at(DATA, item, keeps)]
        with pytest.raises(NotApplicableError):
            Burn(action).outcomes(DATA, item)
    below = helmet(19)
    assert ApplyQualityCurrency(ARMOURERS_SCRAP).burn_refusal(DATA, below, keeps) is None  # one step below the maximum it is still legal: the chain is finite


def test_a_quality_burn_moves_the_quality_the_state_keeps_and_runs_out():
    keeps, scrap = BurnKeeps(quality=True), ApplyQualityCurrency(ARMOURERS_SCRAP)
    item, steps = helmet(0), 0
    while scrap.burn_refusal(DATA, item, keeps) is None:
        ((_, item),) = Burn(scrap).outcomes(DATA, item).results[:1]
        steps += 1
        assert steps < 40
    assert item.quality.percent >= 20  # the chain stopped at the maximum: a finite chain, never a free loop
    assert 5 <= steps <= 20


# --- a Chromatic burn ------------------------------------------------------------------------------------


def test_a_chromatic_burn_counts_an_item_that_states_no_sockets_as_having_one():
    unsocketed = socketed(None, base_id=HELMET)
    assert unsocketed.sockets is None
    with pytest.raises(OutOfScopeError, match="no sockets"):
        ChromaticOrb().outcomes(DATA, unsocketed)  # the plain use refuses it
    assert ChromaticOrb().burn_refusal(DATA, unsocketed, BurnKeeps()) is None
    outcomes = Burn(ChromaticOrb()).outcomes(DATA, unsocketed)
    assert sum(chance for chance, _ in outcomes.results) == 1
    assert all(result.sockets.count == 1 and result.sockets.colours[0].value in "RGB" for _, result in outcomes.results)  # one socket, coloured: it cannot stay white
    states = socketed(white(3), base_id=HELMET)
    assert Burn(ChromaticOrb()).outcomes(DATA, states).results == ChromaticOrb().outcomes(DATA, states).results  # a stated item is rolled as it is


def test_the_chromatic_burn_is_the_plain_orb_only_on_an_item_of_a_socketed_class_that_is_not_corrupted():
    assert ChromaticOrb(omen=True).burn(DATA) is False
    with pytest.raises(ValueError, match="does not declare"):
        Burn(ChromaticOrb(omen=True))
    assert "not a burn" in ChromaticOrb(omen=True).burn_refusal(DATA, helmet(), BurnKeeps())
    for item in (build(RING), build(BELT), build(AMULET)):
        assert ChromaticOrb().burn_refusal(DATA, item, BurnKeeps()) is not None  # jewellery takes no sockets
    assert ChromaticOrb().burn_refusal(DATA, helmet(corrupted=True), BurnKeeps()) is not None
    assert ChromaticOrb().burn_refusal(DATA, socketed(None, base_id=HELMET, corrupted=True), BurnKeeps()) is not None
    # always legal on a socketed item, whatever the state keeps: a move where a target names sockets, a loop otherwise
    for keeps in EVERY_KEEPS:
        assert ChromaticOrb() in [burn.action for burn in burns_at(DATA, helmet(), keeps)]


def test_a_chromatic_burn_lists_its_socket_assumption_among_the_approximate_inputs():
    claim = "burn.chromatic_socket_assumption"
    assert rule_by_id(claim).approximate and "0056-burn" in rule_by_id(claim).url
    burn = Burn(ChromaticOrb())
    assert claim in burn.claims(DATA) and claim in ChromaticOrb().burn_claims(DATA)
    assert claim not in ChromaticOrb().claims(DATA)  # a plan that uses the Orb as a craft, not as a burn, never lists it
    assert ChromaticOrb(omen=True).burn_claims(DATA) == frozenset()

    class Plan:  # the part of a plan that the list of approximate inputs reads
        abstraction = SimpleNamespace(enchantment=None)
        target = SimpleNamespace(base_id=HELMET)
        starts = None

        def offer_of(self, action):
            return SimpleNamespace(offer=SimpleNamespace(action=action))

    listed = {entry.claim for entry in approximate_inputs_of(Plan(), [burn], DATA)}
    assert claim in listed
    assert claim not in {entry.claim for entry in approximate_inputs_of(Plan(), [ChromaticOrb()], DATA)}


@pytest.mark.parametrize("base", [HELMET, SWORD])
def test_the_burns_meet_the_contract(base):
    item = socketed(white(3), base_id=base, quality=10)
    assert check_action(ApplyQualityCurrency(ARMOURERS_SCRAP if base == HELMET else BLACKSMITHS_WHETSTONE), item, DATA)
    if base == HELMET:
        assert check_action(Burn(ChromaticOrb()), item, DATA)
        assert check_action(Burn(ApplyQualityCurrency(ARMOURERS_SCRAP)), item, DATA)


# --- a Blessed Orb burn ----------------------------------------------------------------------------------


def test_a_blessed_burn_is_legal_on_an_item_with_a_ranged_implicit_when_no_requirement_reads_it():
    for item in (belt(), build(RANGED_RING), build(BELT)):  # a belt, a ring; an item built without implicits still has its base's
        assert BlessedOrb().burn(DATA)
        assert BlessedOrb().burn_refusal(DATA, item, BurnKeeps()) is None
        assert BlessedOrb() in [burn.action for burn in burns_at(DATA, item, BurnKeeps())]
        ((chance, result),) = Burn(BlessedOrb()).outcomes(DATA, item).results
        assert chance == 1 and result.mods == item.mods  # no mod changes
    assert BlessedOrb().burn_refusal(DATA, build(RING), BurnKeeps()) is not None  # no ranged implicit: nothing to reroll


def test_a_blessed_burn_is_refused_when_a_requirement_reads_the_implicit():
    keeps = BurnKeeps(implicits=True)
    reason = BlessedOrb().burn_refusal(DATA, belt(), keeps)
    assert reason is not None and "requirement reads the implicits" in reason
    assert BlessedOrb() not in [burn.action for burn in burns_at(DATA, belt(), keeps)]
    assert BlessedOrb().outcomes(DATA, belt())  # the orb itself still works there: as a plain reroll, not as a burn


def test_a_blessed_burn_is_refused_with_an_eldritch_implicit():
    eldritch = implicit(AVOID_SHOCK_1, 1)
    boots = Item.build(DATA, base_id=BOOTS, item_level=84, rarity=Rarity.RARE, implicits=(eldritch,))
    with_ranged = build(BELT, implicits=(eldritch, ImplicitMod(STRENGTH, 0, (30,))))
    for item in (boots, with_ranged):
        for keeps in (BurnKeeps(), BurnKeeps(quality=True)):
            reason = BlessedOrb().burn_refusal(DATA, item, keeps)
            assert reason is not None and "Eldritch" in reason
            assert BlessedOrb() not in [burn.action for burn in burns_at(DATA, item, keeps)]
        with pytest.raises(OutOfScopeError, match="Eldritch"):
            Burn(BlessedOrb()).outcomes(DATA, item)


def test_a_blessed_burn_is_refused_on_a_corrupted_item():
    assert BlessedOrb().burn_refusal(DATA, belt(corrupted=True), BurnKeeps()) is not None


# --- a burn is never a plain action ---------------------------------------------------------------------


def test_a_burn_is_absent_from_the_plain_offers_of_every_state():
    items = [helmet(), helmet(20), sword(), socketed(None, base_id=HELMET), build(RING), build(RANGED_RING), build(AMULET), belt(), build(JEWEL)]
    burn_kinds = [entry for entry in kinds() if entry.burns]
    assert {entry.name for entry in burn_kinds} == {"chromatic-orb", "quality-currency", "blessed-orb", "re-anoint"}
    for item in items:
        for keeps in EVERY_KEEPS:
            burns = set(burns_at(DATA, item, keeps))
            for plain in (catalog(DATA, item, names={entry.name for entry in burn_kinds}), catalog(DATA, item, planner_only=True)):
                assert not any(isinstance(action, Burn) for action in plain) and burns.isdisjoint(plain)
        assert not any(isinstance(action, ReAnoint) for action in catalog(DATA, item, planner_only=True))  # the re-anoint is no planner kind
    for item in (build(RING), build(AMULET)):
        assert any(isinstance(action, ReAnoint) for action in catalog(DATA, item, names={"re-anoint"}))  # it exists in the catalog for the contract suite, not as an offer


def test_the_offers_of_a_target_hold_no_burn_and_the_burn_only_kind_cannot_be_named():
    ring = build(RING)
    goal = Goal((Wanted(frozenset({LIFE_1})),))
    offered = offers_for(DATA, goal, ring.base_id, ring)
    assert not any(isinstance(offer.action, (Burn, ReAnoint)) for offer in offered.offers)
    assert not any(label.startswith("Burn") or label == "Re-anoint" for offer in offered.offers for label in [offer.label])
    with pytest.raises(ValueError, match="re-anoint"):
        offers_for(DATA, goal, ring.base_id, ring, ["re-anoint"])


def test_a_burn_is_an_ordinary_unpreviewed_action_with_the_price_and_strand_declaration_of_the_currency():
    for action, item in ((ReAnoint(), build(AMULET)), (BlessedOrb(), belt()), (ChromaticOrb(), helmet()), (ApplyQualityCurrency(ARMOURERS_SCRAP), helmet())):
        burn = Burn(action)
        assert burn.label(DATA) == f"Burn with {action.label(DATA)}"
        assert burn.resources(DATA) == action.resources(DATA)
        assert burn.previewable(DATA).value == "no" and burn.currency_item(DATA) is None and burn.burn(DATA) is False  # a Burn is no option and no burn of a burn
        assert burn.strand_use(DATA) == action.strand_use(DATA)
        assert burn.reads(DATA) == action.reads(DATA) and burn.adds(DATA, item) == action.adds(DATA, item)
        assert action.claims(DATA) <= burn.claims(DATA)
        assert "hinekora_lock.neutral_currency_removes_foresight" in burn.claims(DATA)
    assert burns_at(DATA, belt(), BurnKeeps()) == (Burn(BlessedOrb()),)
    assert Burn(BlessedOrb()) == Burn(BlessedOrb()) and hash(Burn(BlessedOrb())) == hash(Burn(BlessedOrb()))
