"""The foresight contract, the Lock kind and its claims (ticket #294, B8-2; ADR-0054 to ADR-0056, the amendment of ADR-0024).

* A toy action defined in this module declares `previewable`, `currency_item` and `burn` and the contract returns them; an action that
  declares nothing is `no`, no currency item, no burn (the default that keeps every existing kind blind).
* The kinds are listed by `previewable` value, and the listing fails when a kind outside the table of ADR-0055 is not `no`.
* `HinekoraLock` refuses a corrupted, a mirrored and an unmodifiable item, costs one Lock and declares its strand use; it is no catalog kind.
* `rules/claims/hinekora_lock.yaml` holds the 14 draft claims of the research note (two reworded), the owner's four, the six previews that only
  the Lock's item text covers (approximate) and the Lock's cost; every preview a kind declares cites claims that exist.

The contract suite itself (`test_actions_contract.py`) runs unchanged on every kind: the new declarations have defaults and nothing there names them.
"""

import dataclasses
import datetime
from collections import defaultdict

import pytest
from contract_support import CONTRACT_DATA, contract_pairs, extra_fixture_items, extra_pairs, fixture_items

from crafting_system.actions import (
    Action,
    Adds,
    Finite,
    HinekoraLock,
    Kind,
    NotApplicableError,
    Previewable,
    Reads,
    catalog,
    kinds,
    registered,
)
from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.rules import SourceKind, load_registry, rule_by_id

# ADR-0055's table, by the name of the kind (the catalog's name, not a class). Tailoring is in the table as named but errs low: the ticket
# declares it on no kind (B7 never offers the enchant orbs as search steps), so it may be `no` or `named`.
NAMED = {"chaos-orb", "exalted-orb", "annulment-orb", "regal-orb", "divine-orb"}
BY_ITEM_TEXT = {"transmutation-orb", "alteration-orb", "augmentation-orb", "alchemy-orb", "scouring-orb", "vaal"}
IN_THE_TABLE_ONLY_BY_ITS_ERRING_LOW = {"tailoring"}
TABLE = NAMED | BY_ITEM_TEXT | IN_THE_TABLE_ONLY_BY_ITS_ERRING_LOW

REGISTRY = load_registry()


# --- the listing -------------------------------------------------------------------------------------------------------------------------


def declared_actions() -> dict[str, list[tuple[Action, GameData]]]:
    """Every action the shared contract suite asks about, by kind: the members on the fixture items and on the items of a base of their own."""
    found: dict[str, list[tuple[Action, GameData]]] = defaultdict(list)
    for kind, action, _ in contract_pairs():
        found[kind].append((action, CONTRACT_DATA))
    extra = extra_fixture_items()
    for kind, action, name in extra_pairs():
        found[kind].append((action, extra[name].data))
    return found


def kinds_by_previewable() -> dict[Previewable, set[str]]:
    """The kinds listed by what their actions declare (a kind whose members disagree is listed under both values)."""
    listing: dict[Previewable, set[str]] = defaultdict(set)
    for kind, members in declared_actions().items():
        for action, data in members:
            listing[action.previewable(data)].add(kind)
    return listing


def outside_the_table(listing: dict[Previewable, set[str]]) -> set[str]:
    """The kinds that are not `no` and are not in the table of ADR-0055."""
    return {kind for value, names in listing.items() if value is not Previewable.NO for kind in names} - TABLE


def test_the_kinds_by_previewable_value_are_the_table_of_adr_0055():
    listing = kinds_by_previewable()
    assert not outside_the_table(listing), "a kind outside the table of ADR-0055 must stay `no` until a claim and an ADR line say otherwise"
    assert listing[Previewable.NAMED] == NAMED
    assert listing[Previewable.BY_ITEM_TEXT] == BY_ITEM_TEXT
    assert listing[Previewable.NO].isdisjoint(NAMED | BY_ITEM_TEXT)  # no kind is declared both ways
    assert {entry.name for entry in kinds()} >= (TABLE - {"tailoring"})  # every kind of the table exists


def all_subclasses(cls: type) -> set[type]:
    found = set()
    for sub in cls.__subclasses__():
        found |= {sub} | all_subclasses(sub)
    return found


def test_no_action_class_declares_previewable_without_the_listing_having_seen_it():
    """A few kinds apply only to an item of their own (the Eldritch currency, the Blessed Orb) and the shared suite never lists them; none
    of them may override `previewable`, because this listing could not tell. Every class that does is among the ones the listing asked."""
    seen = {type(action) for members in declared_actions().values() for action, _ in members}
    overriding = {cls for cls in all_subclasses(Action) if cls.__module__.startswith("crafting_system.actions") and cls.previewable is not Action.previewable}
    assert overriding and overriding <= seen, sorted(cls.__name__ for cls in overriding - seen)


@dataclasses.dataclass(frozen=True)
class ToyBlind(Action):
    """An action that declares nothing about foresight."""

    def label(self, data: GameData | None = None) -> str:
        return "Toy Blind"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {"Toy Blind Orb": 1}

    def reads(self, data: GameData) -> Reads:
        return Reads.nothing()

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.erasing(named=frozenset())

    def outcomes(self, data: GameData, item: Item) -> Finite:
        raise NotApplicableError("a toy")


@dataclasses.dataclass(frozen=True)
class ToyForeseen(ToyBlind):
    """An action that declares what a toy defined in a test may declare: previewable, a currency item, a burn and the claims behind the preview."""

    how: Previewable = Previewable.BY_ITEM_TEXT
    is_burn: bool = False

    def label(self, data: GameData | None = None) -> str:
        return "Toy Foreseen"

    def previewable(self, data: GameData | None = None) -> Previewable:
        return self.how

    def currency_item(self, data: GameData | None = None) -> str:
        return "Toy Foreseen Orb"

    def burn(self, data: GameData | None = None) -> bool:
        return self.is_burn

    def preview_claims(self, data: GameData | None = None) -> frozenset[str]:
        return frozenset({"hinekora_lock.scouring_orb_previewed"})


def test_an_action_that_declares_nothing_is_blind_has_no_currency_item_and_is_no_burn():
    blind = ToyBlind()
    assert blind.previewable(CONTRACT_DATA) is Previewable.NO and blind.previewable() is Previewable.NO
    assert blind.currency_item(CONTRACT_DATA) is None and blind.burn(CONTRACT_DATA) is False and blind.preview_claims(CONTRACT_DATA) == frozenset()
    assert str(Previewable.NO) == "no" and str(Previewable.NAMED) == "named" and str(Previewable.BY_ITEM_TEXT) == "by_item_text"


@pytest.mark.parametrize("how", [Previewable.NAMED, Previewable.BY_ITEM_TEXT])
@pytest.mark.parametrize("is_burn", [False, True])
def test_a_toy_defined_in_a_test_declares_previewable_currency_item_and_burn_and_the_contract_returns_them(how, is_burn):
    toy = ToyForeseen(how, is_burn)
    assert toy.previewable(CONTRACT_DATA) is how
    assert toy.currency_item(CONTRACT_DATA) == "Toy Foreseen Orb"
    assert toy.burn(CONTRACT_DATA) is is_burn
    assert toy.preview_claims(CONTRACT_DATA) == {"hinekora_lock.scouring_orb_previewed"}
    assert toy.strand_use(CONTRACT_DATA) is None  # the declarations are independent of the strand declaration


def toy_members(data: GameData, item: Item):
    yield ToyForeseen()


def test_a_toy_kind_outside_the_table_that_is_previewable_fails_the_listing_and_one_that_is_blind_does_not():
    with registered(Kind("toy-foreseen", toy_members, order=901, planner=False, why_not="a toy")):
        item = fixture_items()["rare_junk"]
        assert [type(action) for action in catalog(CONTRACT_DATA, item) if action.label(CONTRACT_DATA) == "Toy Foreseen"] == [ToyForeseen]
        listing: dict[Previewable, set[str]] = defaultdict(set)
        for entry in kinds():
            for action in entry.members(CONTRACT_DATA, item):
                listing[action.previewable(CONTRACT_DATA)].add(entry.name)
        assert "toy-foreseen" in listing[Previewable.BY_ITEM_TEXT]
        assert outside_the_table(listing) == {"toy-foreseen"}

    def blind_members(data: GameData, item: Item):
        yield ToyBlind()

    with registered(Kind("toy-blind", blind_members, order=902, planner=False, why_not="a toy")):
        listing = defaultdict(set)
        for entry in kinds():
            for action in entry.members(CONTRACT_DATA, fixture_items()["rare_junk"]):
                listing[action.previewable(CONTRACT_DATA)].add(entry.name)
        assert "toy-blind" in listing[Previewable.NO] and not outside_the_table(listing)


# --- what the existing kinds declare -------------------------------------------------------------------------------------------------------


def previewable_actions():
    return [(kind, action, data) for kind, members in declared_actions().items() for action, data in members if action.previewable(data) is not Previewable.NO]


def test_every_previewable_action_names_the_currency_item_it_consumes():
    found = previewable_actions()
    assert {kind for kind, _, _ in found} == NAMED | BY_ITEM_TEXT
    for kind, action, data in found:
        item = action.currency_item(data)
        assert item and item in action.resources(data), f"{kind}: the currency item {item!r} is not what the action consumes {dict(action.resources(data))}"


def test_every_previewable_action_cites_claims_that_exist_and_an_approximate_preview_is_marked_so():
    for kind, action, data in previewable_actions():
        ids = action.preview_claims(data)
        assert ids, f"{kind} is previewable and cites no claim"
        rules = [rule_by_id(claim) for claim in ids]
        assert all(rule.id.startswith("hinekora_lock.") for rule in rules)
        if action.previewable(data) is Previewable.BY_ITEM_TEXT:
            assert all(rule.approximate for rule in rules), f"{kind} is previewed by item text only, so its claim is approximate"
        else:
            assert not any(rule.approximate for rule in rules), f"{kind} is a named preview and must not be marked approximate"


def test_the_preview_claims_are_not_among_the_claims_of_the_action():
    """An answer with no Lock step lists none of the Lock's approximate inputs (ADR-0057): the preview claims are kept apart, as the strand claims are."""
    for kind, action, data in previewable_actions():
        assert not action.preview_claims(data) & action.claims(data), kind


def test_no_existing_kind_declares_a_burn_yet_and_the_other_declarations_are_blind_by_default():
    for kind, members in declared_actions().items():
        for action, data in members:
            assert action.burn(data) is False, f"{kind}: burns are B8-3's"
            if action.previewable(data) is Previewable.NO:
                assert action.currency_item(data) is None and action.preview_claims(data) == frozenset(), kind


def test_the_named_previews_cite_the_wiki_or_the_owner_and_the_five_plain_orbs_the_item_text():
    by_kind = {kind: set(action.preview_claims(data)) for kind, action, data in previewable_actions()}
    assert by_kind["chaos-orb"] == {"hinekora_lock.chaos_orb_previewed"}
    assert by_kind["divine-orb"] == {"hinekora_lock.divine_tailoring_sacred_previewed"}
    for kind in ("exalted-orb", "annulment-orb", "regal-orb"):
        assert by_kind[kind] == {"hinekora_lock.exalted_annulment_regal_previewed"}
    assert REGISTRY["hinekora_lock.exalted_annulment_regal_previewed"].source_kind is SourceKind.OWNER
    for kind, claim in {
        "transmutation-orb": "transmutation_orb_previewed",
        "alteration-orb": "alteration_orb_previewed",
        "augmentation-orb": "augmentation_orb_previewed",
        "alchemy-orb": "alchemy_orb_previewed",
        "scouring-orb": "scouring_orb_previewed",
        "vaal": "vaal_orb_previewed",
    }.items():
        assert by_kind[kind] == {f"hinekora_lock.{claim}"}


# --- the Lock ----------------------------------------------------------------------------------------------------------------------------


def test_the_lock_is_no_action_and_no_catalog_kind():
    assert not issubclass(HinekoraLock, Action)
    assert all("lock" not in entry.name for entry in kinds())
    assert HinekoraLock().label(CONTRACT_DATA) == "Hinekora's Lock"
    assert not hasattr(HinekoraLock(), "outcomes")


@pytest.mark.parametrize("name", ["normal", "magic", "rare_junk", "rare_fractured", "rare_four"])
def test_the_lock_is_allowed_on_a_normal_magic_or_rare_item(name):
    item = fixture_items()[name]
    assert HinekoraLock().refused_on(item) is None
    HinekoraLock().check(item)


def test_the_lock_refuses_a_corrupted_item():
    corrupted = fixture_items()["rare_junk"].changed(CONTRACT_DATA, corrupted=True)
    assert "corrupted" in HinekoraLock().refused_on(corrupted)
    with pytest.raises(NotApplicableError, match="corrupted"):
        HinekoraLock().check(corrupted)


def test_the_lock_refuses_a_mirrored_item():
    item = fixture_items()["rare_junk"]
    assert "mirrored" in HinekoraLock().refused_on(item, mirrored=True)
    with pytest.raises(NotApplicableError, match="mirrored"):
        HinekoraLock().check(item, mirrored=True)


def test_the_lock_refuses_an_unmodifiable_item():
    item = fixture_items()["rare_junk"]
    assert "unmodifiable" in HinekoraLock().refused_on(item, unmodifiable=True)
    with pytest.raises(NotApplicableError, match="unmodifiable"):
        HinekoraLock().check(item, unmodifiable=True)


def test_the_lock_refuses_every_rarity_of_a_corrupted_item():
    for rarity in (Rarity.NORMAL, Rarity.MAGIC, Rarity.RARE):
        item = next(it for it in fixture_items().values() if it.rarity is rarity)
        assert HinekoraLock().refused_on(item.changed(CONTRACT_DATA, corrupted=True)) is not None


def test_the_lock_costs_one_lock_by_its_game_data_name():
    cost = HinekoraLock().resources(CONTRACT_DATA)
    assert dict(cost) == {"Hinekora's Lock": 1} == dict(HinekoraLock().resources())
    assert dict(REGISTRY["hinekora_lock.cost"].value) == {"Hinekora's Lock": 1}


def test_the_lock_declares_its_strand_use_it_neither_cuts_nor_spends():
    use = HinekoraLock().strand_use(CONTRACT_DATA)
    assert use is not None and use.cuts is False and use.spend is None
    assert use.claims and all(claim in REGISTRY for claim in use.claims)


def test_the_lock_names_its_own_claims():
    claims = HinekoraLock().claims(CONTRACT_DATA)
    assert {
        "hinekora_lock.foresees_next_currency",
        "hinekora_lock.refused_on",
        "hinekora_lock.lock_is_used_up",
        "hinekora_lock.no_second_lock_on_a_foreseeing_item",
        "hinekora_lock.cost",
    } == claims


def test_the_lock_is_exported_by_the_package():
    import crafting_system.actions as actions

    assert actions.HinekoraLock is HinekoraLock and "HinekoraLock" in actions.__all__


# --- the claims -------------------------------------------------------------------------------------------------------------------------


DRAFT = [
    "foresees_next_currency",
    "looking_changes_nothing",
    "preview_fixed_per_currency_type",
    "applied_result_is_the_preview",
    "one_applied_currency_voids_other_previews",
    "neutral_currency_removes_foresight",
    "unpreviewed_crafts_remove_foresight",
    "altar_of_corruption_not_foreseen",
    "awakener_preview_depends_on_donor",
    "refused_on",
    "stack_of_ten",
    "tradeable_on_currency_exchange",
    "chaos_orb_previewed",
    "divine_tailoring_sacred_previewed",
]
OWNER = [
    "preview_independent_across_currencies",
    "exalted_annulment_regal_previewed",
    "no_second_lock_on_a_foreseeing_item",
    "lock_is_used_up",
]
BY_ITEM_TEXT_CLAIMS = [
    "transmutation_orb_previewed",
    "alteration_orb_previewed",
    "augmentation_orb_previewed",
    "alchemy_orb_previewed",
    "scouring_orb_previewed",
    "vaal_orb_previewed",
]


def family() -> dict:
    return {rule_id: rule for rule_id, rule in REGISTRY.items() if rule_id.startswith("hinekora_lock.")}


def test_the_claim_file_holds_the_draft_the_owners_four_the_item_text_previews_and_the_cost():
    assert set(family()) == {f"hinekora_lock.{name}" for name in DRAFT + OWNER + BY_ITEM_TEXT_CLAIMS + ["cost"]}
    assert len(DRAFT) == 14 and len(OWNER) == 4 and len(BY_ITEM_TEXT_CLAIMS) == 6


def test_every_claim_has_its_provenance():
    for rule in family().values():
        assert rule.statement and rule.url.startswith("https://") and rule.quote and rule.patch_verified == "3.29.3.3"
        assert isinstance(rule.date_checked, datetime.date)


def test_the_owners_four_are_of_source_kind_owner_and_dated_2026_11_01():
    for name in OWNER:
        rule = REGISTRY[f"hinekora_lock.{name}"]
        assert rule.source_kind is SourceKind.OWNER and rule.date_checked == datetime.date(2026, 11, 1) and not rule.approximate, name
        assert "issues/106" in rule.url


def test_the_item_text_previews_are_approximate_with_a_reason_and_nothing_else_of_the_family_is_but_they():
    approximate = {rule_id for rule_id, rule in family().items() if rule.approximate}
    assert approximate == {f"hinekora_lock.{name}" for name in BY_ITEM_TEXT_CLAIMS}
    for rule_id in approximate:
        assert family()[rule_id].approximate_reason


def test_the_two_reworded_claims_no_longer_wait_for_the_owner():
    for name in ("chaos_orb_previewed", "divine_tailoring_sacred_previewed"):
        rule = REGISTRY[f"hinekora_lock.{name}"]
        assert "owner admits" not in rule.statement and "Q2" not in rule.statement
    assert "named preview" in REGISTRY["hinekora_lock.chaos_orb_previewed"].statement
    assert "Tailoring Orb is not" in REGISTRY["hinekora_lock.divine_tailoring_sacred_previewed"].statement


def test_the_draft_claims_keep_their_sources():
    assert REGISTRY["hinekora_lock.altar_of_corruption_not_foreseen"].source_kind is SourceKind.OFFICIAL
    assert REGISTRY["hinekora_lock.foresees_next_currency"].source_kind is SourceKind.DATAMINED
    assert REGISTRY["hinekora_lock.refused_on"].source_kind is SourceKind.WIKI


def test_the_general_rule_the_research_left_out_is_not_admitted():
    assert "hinekora_lock.preview_covers_all_currency_items" not in REGISTRY  # essences and fossils stay blind (ADR-0055)
