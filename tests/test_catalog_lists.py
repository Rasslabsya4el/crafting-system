"""A new method changes no recorded answer of a route that does not use it (ticket #1277).

`catalog_lists_support` keeps the lists an answer reads off the catalog out of the recorded pages, text reports, JSON policies and
digests. Three things are held here in their place, on the fixture world's R12 (the committed target, every method on):

* the experiment of the ticket, as a test: a kind added to the catalog (one the planner cannot use, and one it offers by default whose
  currency has no price) does change the page, the text and the JSON the user reads, and changes nothing of what a test records;
* the lists themselves against the catalog: every kind of the catalog is offered, or stands in exactly one list, or is one of the kinds
  an answer may leave unsaid by a flag of its own; and every label of a list is a kind of the catalog;
* the group "Actions with no price", which the fixture world's pages do not record: what it names has no price in the price file, and
  no offer the plan kept is named in it.

What a list looks like in each surface (every label in the text and the JSON, three and a closed "details" on the page) is
`test_cli_limits.py`'s; which kind is a planner kind is `tests/golden/reachability.md`'s, the one recorded file a new kind changes.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from html import escape

import pytest
from catalog_lists_support import CATALOG_LISTS, FIXTURE_WORLD, LIST, document_without, limits_without, one_element_to_a_line, page_without, text_without
from cli_support import R12, price_file
from limits_support import of_kind
from targets_support import DATA
from two_runs_support import masked, without_timings

from crafting_system.actions import ChaosOrb, kinds
from crafting_system.actions.catalog import Kind, registered
from crafting_system.budget import Budget
from crafting_system.cli import build_report, make_plan, policy_document, render_text
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_view import Page, build_section, route_input
from crafting_system.planner._limits import NOT_BUILT, NOT_NAMED, OPT_IN, TITLES, UNPRICED, kind_title, limit_text
from crafting_system.planner._offers import LOCK_KIND
from crafting_system.targets import load_target

STATES = 100_000  # the toy R12 closes its rounds in a handful of states (`test_cli_route_view.GOLDEN_STATES`)


@dataclass(frozen=True)
class NewOrb(ChaosOrb):
    """A method that did not exist: a Chaos Orb under another name, paid with a currency no price file holds."""

    def label(self, data=None) -> str:
        return "New Orb"

    def currency_item(self, data=None) -> str:
        return "New Orb"

    def resources(self, data=None) -> Mapping[str, int]:
        return {"New Orb": 1}


NOT_BUILT_YET = Kind("new-method", lambda data, item: (), 9990, planner=False, why_not="a kind of ticket #1277's experiment")
ON_BY_DEFAULT = Kind("new-orb", lambda data, item: (NewOrb(),), 9991)


def surfaces() -> dict[str, str]:
    """What the user gets for R12 with the catalog as it stands (the route page, the text report, the JSON policy), and what a test records of it."""
    plan = make_plan(DATA, load_target(R12, DATA), price_file(), budget=Budget.in_states(STATES))
    report = build_report(plan, DATA)
    page = render_page(Page("R12", (build_section(route_input(plan), DATA),)))
    text = masked(render_text(report))
    document = without_timings(policy_document(report))
    return {
        "page": page,
        "text": text,
        "json": json.dumps(document, indent=2, sort_keys=True),
        "page recorded": page_without(page),  # a real route's page
        "fixture page recorded": page_without(page, FIXTURE_WORLD),
        "text recorded": text_without(text, report),
        "json recorded": json.dumps(document_without(document), indent=2, sort_keys=True),
        "limits recorded": repr(sorted(repr(limit) for limit in limits_without(plan.limits))),  # `b1_unchanged_support`
    }


RECORDED = ("page recorded", "fixture page recorded", "text recorded", "json recorded", "limits recorded")


@pytest.fixture(scope="module")
def today() -> dict[str, str]:
    return surfaces()


@pytest.fixture(scope="module")
def plan():
    return make_plan(DATA, load_target(R12, DATA), price_file(), budget=Budget.in_states(STATES))


# --- the experiment: a new kind changes what the user reads and nothing a test records ---------------------------------------------


def test_a_kind_the_planner_cannot_use_yet_changes_the_answer_the_user_reads_and_nothing_recorded(today):
    with registered(NOT_BUILT_YET):
        after = surfaces()

    for surface in ("page", "text", "json"):  # the user is told about the new method (OR-13)
        assert "New Method" in after[surface] and "New Method" not in today[surface]
    assert {name: after[name] == today[name] for name in RECORDED} == dict.fromkeys(RECORDED, True)


def test_a_new_planner_kind_under_the_classic_offers_changes_nothing_recorded(today):
    """The real routes' records plan with the classic offers (`cli_support.classic_offers`): there a new planner kind is offered only when named."""
    with registered(replace(ON_BY_DEFAULT, opt_in=True)):
        after = surfaces()

    for surface in ("page", "text", "json"):
        assert "New Orb" in after[surface] and "New Orb" not in today[surface]
    assert {name: after[name] == today[name] for name in RECORDED} == dict.fromkeys(RECORDED, True)


def test_a_new_kind_on_by_default_with_no_price_changes_no_recorded_page_of_the_fixture_world(today):
    """With every method on the new kind is offered, and the fixture price file has no price for it: one more line of "Actions with no price"."""
    with registered(ON_BY_DEFAULT):
        after = surfaces()

    assert "New Orb" in after["page"] and "New Orb" not in today["page"]
    assert after["fixture page recorded"] == today["fixture page recorded"]
    assert after["page recorded"] != today["page recorded"]  # a page that records the prices it lacks (a real route's) says the new one


# --- what is still recorded ---------------------------------------------------------------------------------------------------------


def lines_of(page: str, kind: str) -> list[str]:
    """The lines of the group `kind` on `page`, read by the markup of `cli._route_html._leaves_out`."""
    head = f'<div class="k">{escape(TITLES[kind])}</div><div class="v ml"><div>'
    return page.split(head, 1)[1].split('</div></div><div class="k">', 1)[0].split("</div><div>") if head in page else []


def test_a_recorded_line_keeps_what_is_left_out_why_and_the_guarantee(today, plan):
    recorded = today["page recorded"]

    for kind in CATALOG_LISTS:
        limits = of_kind(plan.limits, kind)
        assert lines_of(recorded, kind) == [escape(limit_text(replace(limit, labels=(LIST,)))) for limit in limits]
    assert lines_of(recorded, NOT_BUILT) and lines_of(recorded, OPT_IN)
    assert lines_of(recorded, UNPRICED) == lines_of(today["page"], UNPRICED)
    rest = today["page"]
    for kind in CATALOG_LISTS:
        for line in lines_of(today["page"], kind):
            rest = rest.replace(f"<div>{line}</div>", "", 1)
    for kind in CATALOG_LISTS:
        for line in lines_of(recorded, kind):
            recorded = recorded.replace(f"<div>{line}</div>", "", 1)
    assert recorded == rest  # nothing else of the page is touched


def test_the_fixture_worlds_page_records_actions_with_no_price_by_the_kinds_of_line(today, plan):
    recorded = lines_of(today["fixture page recorded"], UNPRICED)
    guarantee = "The plan is the cheapest among the actions that have a price. A price for these could make it cheaper."

    assert len(of_kind(plan.limits, UNPRICED)) > len(recorded)
    assert recorded == [f"These actions have no price: {LIST}. {guarantee}", f"Not offered: {LIST} (no price for {LIST}). {guarantee}"]


def test_a_step_a_price_or_a_cost_that_moves_still_fails_the_recorded_page(today):
    page = today["page"]
    cost = next(part for part in page.split(">") if "Chaos" in part and any(digit in part for digit in "123456789"))
    moved = page.replace(cost, cost.replace("Chaos", "Chaos more"), 1)

    assert page_without(moved, FIXTURE_WORLD) != page_without(page, FIXTURE_WORLD)


def test_a_line_that_is_not_written_as_a_limit_is_refused_not_passed_over(today):
    head = f'<div class="k">{escape(TITLES[NOT_BUILT])}</div><div class="v ml"><div>'
    with pytest.raises(AssertionError, match="is not written as `limit_text` writes one"):
        page_without(today["page"].replace(head, head + "no head and no guarantee</div><div>"))


def test_a_recorded_page_has_one_element_to_a_line_and_the_pages_own_bytes_between(today):
    page = today["page"]
    spread = one_element_to_a_line(page)

    body = max(page.splitlines(), key=len)
    assert max(map(len, spread.splitlines())) < len(body) / 4  # the one line of the body is many
    assert spread.count("\n") - page.count("\n") > 100 and one_element_to_a_line(spread) == spread
    kept = spread
    for tag in ("div", "section", "h3", "details"):
        kept = kept.replace(f">\n<{tag}", f"><{tag}")
    assert kept == page  # only line breaks between a tag and a block element came in


def test_the_text_and_the_json_keep_the_words_of_a_list_and_every_other_limit(today, plan):
    report = build_report(plan, DATA)
    whole = without_timings(policy_document(report))["limits"]
    text = today["text recorded"]
    recorded = json.loads(today["json recorded"])["limits"]

    kept = [limit for limit in plan.limits if limit.kind not in CATALOG_LISTS and limit.labels]
    assert kept and all(label in text for limit in kept for label in limit.labels)
    assert text.count(LIST) == sum(limit.kind in CATALOG_LISTS for limit in plan.limits) > 0
    assert "(methods the planner cannot use yet). The plan is the cheapest among the methods the planner can use." in text
    for entry, limit in zip(recorded, whole, strict=True):
        if entry["kind"] in CATALOG_LISTS:
            assert entry == {**limit, "count": LIST, "labels": LIST}
        else:
            assert entry == limit


# --- the lists against the catalog ----------------------------------------------------------------------------------------------------


def test_every_kind_of_the_catalog_is_offered_or_in_one_list_or_unsaid_by_its_own_flag(plan):
    lists = {kind: [label for limit in of_kind(plan.limits, kind) for label in limit.labels] for kind in CATALOG_LISTS}
    named = [label for labels in lists.values() for label in labels]

    assert len(named) == len(set(named))  # no kind twice
    assert set(named) <= {kind_title(entry.name) for entry in kinds()} | {kind_title(LOCK_KIND)}
    assert not lists[NOT_NAMED]  # the target names no methods: the run's default
    for entry in kinds():
        title = kind_title(entry.name)
        silent = entry.corrupting or entry.needs_strands or entry.only_quality or entry.only_implicit_rolls
        if not entry.planner:
            assert title in lists[NOT_BUILT] or entry.player_why or silent, entry.name
        elif entry.opt_in:
            assert title in lists[OPT_IN] or silent, entry.name
        else:
            assert title not in named, entry.name
    assert kind_title(LOCK_KIND) in lists[OPT_IN]  # Hinekora's Lock: no kind of the catalog, off unless named (OR-37)


def test_what_the_answer_calls_unpriced_has_no_price_and_no_kept_offer_is_among_it(plan):
    unpriced = of_kind(plan.limits, UNPRICED)
    prices = price_file().prices

    assert unpriced  # the fixture price file holds one lifeforce and the start item
    assert all(name not in prices for limit in unpriced for name in limit.names)
    kept = {offer.label for offer in plan.offers}
    assert kept and not kept.intersection(label for limit in unpriced for label in limit.labels)
