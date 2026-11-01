"""The contract suite runs on every kind of the catalog without being edited (ticket #108).

The checks are in `contract_support.py`. A new kind registered in `actions` is found here by the
catalog: its members on the fixture items are checked, and `test_every_kind_applies_on_some_fixture_item`
fails when a kind is registered that no fixture item can use (register the item it needs in a `tests/contract_fixtures_<family>.py`, and
declare `applies_only_to` on a kind that works on one item class only: `docs/agents/new-action-family.md`).
"""

import dataclasses
import json

import pytest
from abstraction_pool import FIRE_RESIST
from cli_support import R12, price_file
from contract_support import (
    CONTRACT_DATA,
    check_action,
    check_block_invariance,
    check_cutting_kinds_differ_from_the_uncut_draw,
    check_every_kind_applies_on_some_fixture_item,
    contract_pairs,
    extra_fixture_items,
    extra_pairs,
    fixture_blocks,
    fixture_items,
)
from targets_support import DATA

from crafting_system.abstraction import Goal, Wanted
from crafting_system.actions import ExaltedOrb, NotApplicableError, OutOfScopeError, Reads, RegalOrb, catalog, kinds
from crafting_system.cli import PricedOffer, make_plan, parse_route
from crafting_system.cli._offers import offer_of, offers_for
from crafting_system.targets import load_target

PAIRS = contract_pairs()
ITEMS = fixture_items()
EXTRA_PAIRS = extra_pairs()  # the kinds that need a base of their own, asked about the items of `extra_fixture_items`
EXTRA = extra_fixture_items()  # name -> kinds, data and item


def _id(pair) -> str:
    kind, action, item = pair
    return f"{kind}:{action.label(CONTRACT_DATA)}@{item}"


@pytest.mark.parametrize("pair", PAIRS, ids=_id)
def test_the_action_meets_the_contract(pair):
    _, action, item = pair
    check_action(action, ITEMS[item])


@pytest.mark.parametrize("pair", EXTRA_PAIRS, ids=_id)
def test_the_action_meets_the_contract_on_the_helmet(pair):
    _, action, item = pair
    check_action(action, EXTRA[item].item, EXTRA[item].data)  # False where the game refuses it here: the kernel refuses it too


def test_every_kind_applies_on_some_fixture_item():
    """The kinds that declare `applies_only_to` (the Eldritch currency, ticket #151) are exempt: their own suite
    (`test_actions_eldritch.py`) runs `check_action` on a boots fixture and checks that each kind applies there."""
    applied = check_every_kind_applies_on_some_fixture_item()
    assert applied == {entry.name for entry in kinds() if not entry.applies_only_to} | (applied & {entry.name for entry in kinds()})


B1_KINDS_THAT_DECLARE_STRAND_USE = {
    "transmutation-orb", "alteration-orb", "augmentation-orb", "regal-orb", "alchemy-orb", "chaos-orb", "exalted-orb", "annulment-orb",
    "scouring-orb", "divine-orb", "fracturing-orb", "essence", "corrupted-essence", "fossil-set", "harvest-reforge",
    "harvest-reforge-influence", "harvest-reforge-likelihood", "bench-craft", "remove-crafted-mods", "harvest-quality-enchant", "tempering",
    "tailoring",
    "veiled-chaos-orb", "veiled-exalted-orb", "unveil", "pick",  # B5-11a (#284)
    "eldritch-implicit-currency", "eldritch-chaos-orb", "orb-of-conflict",  # B5-11b (#285); the Eldritch Exalted and Annulment Orbs stay refused
    "influenced-exalted-orb", "orb-of-dominance", "beast-influence-recipe",  # B5-11c (#286)
    "blessed-orb", "catalyst",  # B5-11d (#287)
    "awakeners-orb",  # B5-11f (#289)
}  # ADR-0041's table for the actions of B1 and the families of B5-11a to d and f (the others declare their own rows: B5-11e, g, h)
STRANDED = [name for name, item in ITEMS.items() if item.memory_strands]


def test_the_fixture_holds_stranded_items_and_the_suite_asks_every_kind_about_them():
    assert {"normal_stranded", "magic_stranded", "rare_stranded", "rare_four_stranded"} <= set(STRANDED)
    asked = {kind for kind, _, item in PAIRS if item in STRANDED}
    assert asked == {kind for kind, _, _ in PAIRS}


def test_exactly_the_kinds_of_the_b1_table_declare_their_strand_use_and_every_other_is_refused_on_a_stranded_item():
    declared, refused = set(), set()
    for kind, action, item in PAIRS:
        if not ITEMS[item].memory_strands:
            continue
        use = action.strand_use(CONTRACT_DATA)
        (declared if use is not None else refused).add(kind)
        if use is None:
            with pytest.raises(OutOfScopeError, match="has not declared"):
                action.outcomes_under(CONTRACT_DATA, ITEMS[item])
    assert declared >= B1_KINDS_THAT_DECLARE_STRAND_USE & {kind for kind, _, _ in PAIRS}  # a family added since declares its own rows (its own tests)
    assert refused.isdisjoint(declared) and refused  # the veiled, Eldritch, influence, beast and Harvest add/remove kinds wait for their tickets


def test_every_cutting_kind_draws_other_mods_than_at_0_strands_on_some_stranded_item():
    cutting = check_cutting_kinds_differ_from_the_uncut_draw()
    assert cutting >= {"transmutation-orb", "alteration-orb", "augmentation-orb", "regal-orb", "alchemy-orb", "chaos-orb", "exalted-orb", "essence"}
    assert cutting >= {"veiled-chaos-orb", "awakeners-orb", "influenced-exalted-orb"}  # the last two cut on the stranded extra items only
    assert cutting.isdisjoint({"fossil-set", "harvest-reforge", "bench-craft", "annulment-orb", "scouring-orb", "divine-orb"})


def test_a_kind_lists_each_action_once_per_item():
    for item in ITEMS.values():
        for entry in kinds():
            members = list(entry.members(CONTRACT_DATA, item))
            assert len(members) == len(set(members)), entry.name


@pytest.fixture(scope="module")
def plan():
    return make_plan(DATA, load_target(R12, DATA), price_file())


@pytest.mark.parametrize("pair", PAIRS, ids=_id)
def test_the_label_round_trips_through_a_given_route(pair, plan):
    _, action, item = pair
    label = action.label(CONTRACT_DATA)
    priced = PricedOffer(offer_of(action, label, CONTRACT_DATA, ITEMS[item]), 1.0, ())
    only = dataclasses.replace(plan, offers=(priced,), dropped=())
    route = parse_route(f"rules:\n  - do: {json.dumps(label)}\n", only, DATA, "route.yaml")
    assert route.rules[0].do == label


def test_actions_that_share_a_label_differ_in_their_variant():
    for item in ITEMS.values():
        seen = {}
        for action in catalog(CONTRACT_DATA, item):
            label = action.label(CONTRACT_DATA)
            assert (label, action.variant) not in seen, f"{label} twice with the variant {action.variant!r}"
            seen[(label, action.variant)] = action


@pytest.mark.parametrize("name", list(ITEMS))
def test_every_offer_label_of_the_planner_round_trips_through_a_given_route(name, plan):
    item = ITEMS[name]
    every_craft = Goal(tuple(Wanted(frozenset({mod.id})) for mod in CONTRACT_DATA.mods.values()))
    offers = offers_for(CONTRACT_DATA, every_craft, item.base_id, item).offers
    labels = [offer.label for offer in offers]
    assert len(labels) == len(set(labels))
    for offer in offers:
        only = dataclasses.replace(plan, offers=(PricedOffer(offer, 1.0, ()),), dropped=())
        text = "rules:\n  - do: " + json.dumps(offer.label) + "\n"
        route = parse_route(text, only, DATA, "route.yaml")
        assert route.rules[0].do == offer.label


def test_the_declared_block_invariant_kinds_are_compared_across_the_members_of_blocks():
    compared = {}
    for kind, action, _ in PAIRS:
        compared[kind] = compared.get(kind, 0) + check_block_invariance(action)
    for kind in ("chaos-orb", "harvest-reforge", "bench-craft", "remove-crafted-mods", "fossil-set", "annulment-orb", "transmutation-orb", "alteration-orb", "scouring-orb"):
        assert compared[kind] > 0, kind
    # the additions declare variants: the backups of the members are compared with those of the variants
    for kind in ("augmentation-orb", "regal-orb", "exalted-orb"):
        assert compared[kind] > 0, kind
    # every other kind refuses by default: nothing was declared, nothing compared
    for kind in ("alchemy-orb",):
        assert compared[kind] == 0, kind


def test_block_invariance_and_variants_are_refused_by_default():
    assert Reads().block_invariant is False and Reads.nothing().block_invariant is False
    assert Reads().variants is False and Reads.adding().variants is False and Reads.adding().block_invariant is False


@dataclasses.dataclass(frozen=True)
class UndeclaredAddition(RegalOrb):
    """An addition that declares neither block invariance nor variants: the coarse state must refuse it."""

    def reads(self, data) -> Reads:
        return Reads.adding()


def test_an_addition_that_declares_neither_block_invariance_nor_variants_is_refused_by_the_coarse_state():
    assert check_block_invariance(UndeclaredAddition()) == 0


@dataclasses.dataclass(frozen=True)
class WronglyInvariantRegal(RegalOrb):
    """A Regal Orb that claims the block invariance it does not have: the pool total depends on the family held."""

    def reads(self, data) -> Reads:
        return Reads(junk=True, families=frozenset({"ManaLeech"}), block_invariant=True)


@dataclasses.dataclass(frozen=True)
class InvariantAndReadsEveryFamily(RegalOrb):
    def reads(self, data) -> Reads:
        return Reads(junk=True, families=None, block_invariant=True)


@dataclasses.dataclass(frozen=True)
class WronglyVariantExalted(ExaltedOrb):
    """An Exalted Orb that claims variants but refuses an item that holds Fire Resistance: a member that is neither extreme."""

    def outcomes(self, data, item):
        if any(FIRE_RESIST in mod.mod_id for mod in item.mods):
            raise NotApplicableError("not on an item with fire resistance")
        return super().outcomes(data, item)


def test_a_wrong_claim_of_variants_is_caught_where_a_member_that_is_not_an_extreme_decides_the_legality():
    with pytest.raises(AssertionError):
        check_block_invariance(WronglyVariantExalted())


def test_a_wrong_block_invariance_claim_is_caught():
    assert all(len(blocks) > 3 for blocks in fixture_blocks())
    with pytest.raises(AssertionError, match="members of a block"):
        check_block_invariance(WronglyInvariantRegal())


def test_a_claim_of_block_invariance_by_an_action_that_reads_every_family_is_refused():
    with pytest.raises(AssertionError, match="reads every family"):
        check_block_invariance(InvariantAndReadsEveryFamily())
