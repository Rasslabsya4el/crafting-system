"""A model gap met while the actions of a kind are listed is a limit of the answer; a game refusal there stays silent (ticket #511, OR-13, OR-23, OR-26).

#506 made a gap met in the walk or the solve a `Limit`. The listing comes before the walk: a kind's `members` function leaves an action, a part
of the kind or the whole kind out, and until #511 its `except` clause caught both families, so a gap left the kind out and the answer said nothing.
Each clause now tells the two apart: the game's refusal is silent, the model's gap is said with `listing_gap` and collected by `catalog_kinds(...,
gaps=...)`, and `offers_for` makes it one limit of the kinds (`kinds-model-gap`) with the guarantee "the plan is the cheapest among the actions the
model can list for this item".

One test per clause (fossil item, fossil, fossil set, Vaal Orb, Locus of Corruption, the recombinator's junk craft) fails when its clause stops
saying its gap, and shows that a game refusal there adds none. The clause tests read the real game data (they skip where it is not cached; CI has it).
"""

from html import escape

import pytest
from abstraction_support import real_game_data
from cli_support import R12, price_file
from limits_support import of_kind
from targets_support import DATA

from crafting_system.abstraction import Goal
from crafting_system.actions import BenchCraft, Kind, ListingGap, NotApplicableError, OutOfScopeError, catalog_kinds, junk_craft_offered, listing_gap, registered
from crafting_system.actions import fossil as fossil_module
from crafting_system.cli import build_report, make_plan, policy_document, render_text
from crafting_system.cli._limits import SHOWN_LABELS, WITHIN_GAP, limit_text
from crafting_system.cli._offers import listing_gap_limits
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_view import Page, build_section, route_input
from crafting_system.items import Item, Rarity
from crafting_system.targets import load_target

LISTING = "kinds-model-gap"
CLUSTER = "Metadata/Items/Jewels/JewelPassiveTreeExpansionLarge"  # the model has no rule for its pools: fossils, Vaal Orb, Locus
FLASK = "Metadata/Items/Flasks/FlaskLife1"  # the game: a flask has no corrupted implicit pool
BOOTS = "Metadata/Items/Armours/Boots/BootsInt1"  # Hollow and Glyphic Fossil both go on boots
RING = "Metadata/Items/Rings/Ring1"  # the Hollow Fossil does not
GUARANTEE = "The plan is the cheapest among the actions the model can list for this item. An action the model has no rule for could make it cheaper."


@pytest.fixture(scope="module")
def real():
    return real_game_data()


def rare(data, base_id, **fields):
    return Item.build(data, base_id=base_id, rarity=Rarity.RARE, mods=(), item_level=84, **fields)


def gaps_listing(data, item, kind):
    found: list[ListingGap] = []
    catalog_kinds(data, item, names={kind}, gaps=found)
    return found


# --- the collector ----------------------------------------------------------------------------------------------------


def _toy_members(error, subject=""):
    def members(data, item):
        listing_gap(error, subject)
        listing_gap(error, subject)  # said twice: counted once
        return iter(())

    return members


def test_a_listing_collects_the_gaps_its_kinds_say_with_their_kind_and_a_listing_without_gaps_drops_them():
    error = OutOfScopeError("no rule for the toy", detail="toy detail")
    with registered(Kind("toy-listing", _toy_members(error, "Toy Orb"), order=9_999)):
        found: list[ListingGap] = []
        catalog_kinds(DATA, rare(DATA, R12_BASE()), names={"toy-listing"}, gaps=found)
        catalog_kinds(DATA, rare(DATA, R12_BASE()), names={"toy-listing"})  # no list: nothing collected, nothing raised

    assert found == [ListingGap("toy-listing", "Toy Orb", "no rule for the toy")]
    assert found[0].detail == "toy detail"
    listing_gap(error)  # outside a listing: a no-op


def test_a_listing_inside_a_listing_writes_to_its_own_caller():
    error = OutOfScopeError("inner gap")

    def outer(data, item):
        catalog_kinds(data, item, names={"toy-inner"})  # a listing with no list of its own: the inner gap goes nowhere
        return iter(())

    with registered(Kind("toy-inner", _toy_members(error), order=9_998)), registered(Kind("toy-outer", outer, order=9_999)):
        found: list[ListingGap] = []
        catalog_kinds(DATA, rare(DATA, R12_BASE()), names={"toy-outer"}, gaps=found)

    assert found == []


def R12_BASE():
    return load_target(R12, DATA).base_id


# --- one test per clause ----------------------------------------------------------------------------------------------


def test_the_fossil_item_clause_says_a_model_gap_and_not_a_game_refusal(real):
    (gap,) = gaps_listing(real, rare(real, CLUSTER), "fossil-set")  # a cluster jewel: no admitted rule for its pool

    assert gap.kind == "fossil-set" and gap.subject == "" and gap.cause
    assert gaps_listing(real, Item.build(real, base_id=BOOTS, rarity=Rarity.MAGIC, mods=(), item_level=84), "fossil-set") == []  # the game: a magic item takes no resonator
    assert gaps_listing(real, rare(real, BOOTS, corrupted=True), "fossil-set") == []  # the game: a corrupted item takes none


@pytest.mark.parametrize("error, said", [(NotApplicableError, False), (OutOfScopeError, True)])
def test_the_per_fossil_clause_says_a_model_gap_and_not_a_game_refusal(real, monkeypatch, error, said):
    real_check = fossil_module._check_fossil

    def planted(record, base_tags, item):
        if record.name == "Pristine Fossil":
            raise error("planted for the Pristine Fossil")
        return real_check(record, base_tags, item)

    monkeypatch.setattr(fossil_module, "_check_fossil", planted)
    found = [gap for gap in gaps_listing(real, rare(real, RING), "fossil-set") if gap.subject == "Pristine Fossil"]

    assert found == ([ListingGap("fossil-set", "Pristine Fossil", "planted for the Pristine Fossil")] if said else [])
    assert "Pristine Fossil" not in fossil_module.usable_fossils(real, rare(real, RING))  # left out either way


def test_the_fossil_set_clause_says_the_pair_the_model_has_no_rule_for_once(real):
    found = gaps_listing(real, rare(real, BOOTS), "fossil-set")

    (gap,) = found  # one for the pair, however many sets hold it
    assert gap.subject == "Hollow Fossil with Glyphic Fossil" and "Hollow and Glyphic" in gap.cause
    assert gaps_listing(real, rare(real, RING), "fossil-set") == []  # a ring takes no Hollow Fossil: no pair, no gap


@pytest.mark.parametrize("kind", ["vaal", "locus"])
def test_the_corrupting_clauses_say_a_model_gap_and_not_a_game_refusal(real, kind):
    (gap,) = gaps_listing(real, rare(real, CLUSTER), kind)  # a Cluster Jewel: the model has no rule for its corrupted pool

    assert gap.kind == kind and gap.subject == "" and "Cluster Jewel" in gap.cause
    assert gaps_listing(real, rare(real, FLASK), kind) == []  # the game: a flask has no corrupted implicit pool
    assert gaps_listing(real, rare(real, CLUSTER, corrupted=True), kind) == []  # a corrupted item lists neither, before any pool is asked


@pytest.mark.parametrize("error, said", [(NotApplicableError, False), (OutOfScopeError, True)])
def test_the_junk_craft_clause_says_a_model_gap_and_not_a_game_refusal(real, monkeypatch, error, said):
    monkeypatch.setattr(BenchCraft, "outcomes", lambda self, data, item, reading=None: (_ for _ in ()).throw(error("planted for the bench")))
    with junk_craft_offered():
        found = gaps_listing(real, rare(real, RING), "recombinator")

    assert bool(found) is said
    assert all(gap.kind == "recombinator" and gap.subject.startswith("Bench craft") and gap.cause == "planted for the bench" for gap in found)


# --- the limit ----------------------------------------------------------------------------------------------------------


def test_the_limit_names_each_kind_or_part_once_and_each_cause_once_with_the_guarantee():
    goal = Goal(())
    gaps = [
        ListingGap("fossil-set", "Hollow Fossil with Glyphic Fossil", "two force a mod"),
        ListingGap("fossil-set", "", "no rule for jewels"),
        ListingGap("recombinator", "Bench craft X", "no rule for jewels"),
    ]

    (limit,) = listing_gap_limits(gaps, goal)

    assert limit.kind == LISTING and limit.what == "Not offered"
    assert limit.labels == ("Fossil sets: Hollow Fossil with Glyphic Fossil", "Fossil sets", "Recombinators: Bench craft X")
    assert limit.names == ("two force a mod", "no rule for jewels")
    assert limit.reason() == "the model has no rule for them on this item: two force a mod, no rule for jewels"
    assert limit.guarantee == GUARANTEE and WITHIN_GAP in limit.approximate
    assert listing_gap_limits([], goal) == ()


def test_a_gap_of_a_corrupting_kind_is_said_only_to_a_target_that_takes_a_corrupted_item():
    gap = ListingGap("vaal", "", "no rule for Cluster Jewels")

    assert listing_gap_limits([gap], Goal(())) == ()  # the Orb would not be offered anyway: the corrupting limit's
    (limit,) = listing_gap_limits([gap], Goal((), allow_corrupted=True))
    assert limit.labels == ("Vaal Orb",)


def test_the_causes_of_many_listing_gaps_are_named_three_at_a_time():
    (limit,) = listing_gap_limits([ListingGap("fossil-set", f"Fossil {n}", f"cause {n}") for n in range(5)], Goal(()))

    assert limit.names == ("cause 0", "cause 1", "cause 2", "2 more causes") and len(limit.detail) == 4


def test_a_listing_gap_is_a_limit_of_the_plan_in_the_text_the_json_and_the_page():
    error = OutOfScopeError("the model has no rule for the toy orb on this item")
    with registered(Kind("toy-listing", _toy_members(error, "Toy Orb"), order=9_999)):
        plan = make_plan(DATA, load_target(R12, DATA), price_file(), solver="object")
    report = build_report(plan, DATA)
    text = render_text(report)
    document = policy_document(report)
    page = render_page(Page("x", (build_section(route_input(plan), DATA),)))

    (limit,) = of_kind(plan.limits, LISTING)
    assert limit.labels == ("Toy Listing: Toy Orb",) and limit.guarantee == GUARANTEE
    assert limit_text(limit) in text
    (entry,) = [each for each in document["limits"] if each["kind"] == LISTING]
    assert entry["labels"] == list(limit.labels) and entry["guarantee"] == limit.guarantee and entry["why"] == limit.reason()
    assert escape(limit_text(limit, SHOWN_LABELS)) in page
    assert "Methods the model cannot list for this item" in page


def test_a_plan_whose_listing_meets_no_gap_has_no_such_limit():
    plan = make_plan(DATA, load_target(R12, DATA), price_file(), solver="object")

    assert not of_kind(plan.limits, LISTING)


def test_r08_boots_name_the_fossil_pair_the_model_has_no_rule_for(real):
    from pathlib import Path

    from crafting_system.cli._offers import offers_for

    target = load_target(Path(__file__).resolve().parents[1] / "examples" / "targets" / "r08-energy-shield-boots.yaml", real)
    chosen = offers_for(real, Goal.from_target(target), target.base_id, target.start_item, target.actions)

    (limit,) = of_kind(chosen.limits, LISTING)
    assert limit.labels == ("Fossil sets: Hollow Fossil with Glyphic Fossil",) and limit.guarantee == GUARANTEE
