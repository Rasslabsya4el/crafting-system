"""The approximate inputs of an answer (ticket #143, ADR-0028): the claims marked `approximate` that its policy reads.

No shipped claim is marked yet, so the tests use a toy action defined here: a Chaos Orb whose module holds a marked
and an unmarked `Rule`. The shipped registry does not know them, so the lookup of a claim by id is pointed at a
table of the toy rules. The plan is made by hand like `route_view_support.hand_input` does, with offers of the toy.
"""

import dataclasses
import datetime
import json
from html import escape

import pytest
from oracle import page_lint
from items_support import DATA, roll
from plan_support import planner_plan
from route_view_support import ACTIONS, BELT, COLD_REQ, FRACTURED_COLD, LEVEL, LIFE, PRICES, START_NAME, belt

from crafting_system.abstraction import Abstraction, Goal
from crafting_system.actions import ChaosOrb
from crafting_system.cli import Offer, _marking, price_offers
from crafting_system.cli._marking import (
    ApproximateInput,
    approximate_inputs,
    approximate_inputs_document,
    approximate_lines,
    approximate_page_line,
    approximate_page_lines,
)
from crafting_system.planner._plan import Plan, StartPrice, leaf_labels, offer_action
from crafting_system.cli._report import Report, build_report, policy_document, render_text
from crafting_system.cli._route import Route, RouteResult
from crafting_system.cli._route_report import render_route_text, route_document
from crafting_system.cli._route_view import RouteInput, build_section, route_input
from crafting_system.prices import CHAOS_ORB
from crafting_system.risk import evaluate
from crafting_system.rules import Rule, SourceKind, get_rule, load_registry, rule_by_id
from crafting_system.solver import Solution
from crafting_system.targets import StartKind, Target


def make_rule(rule_id: str, **marks) -> Rule:
    return Rule(
        id=rule_id,
        statement="A toy claim.",
        source_kind=SourceKind.COE,
        url="https://example.org/toy",
        quote="A toy claim.",
        patch_verified="3.29.3.3",
        date_checked=datetime.date(2026, 11, 1),
        **marks,
    )


TOY_WORDS = {"page_statement": "Only Craft of Exile's code gives the count.", "page_source": "Craft of Exile's code only"}
UNTAKEN_WORDS = {"page_statement": "The chance is a fit to a sample of player results.", "page_source": "one player sample"}
TOY_MARKED = make_rule("toy.marked", approximate=True, approximate_reason="only Craft of Exile's code gives the count", **TOY_WORDS)
TOY_PLAIN = make_rule("toy.plain")
UNTAKEN_REASON = "a fit to a sample"
RULES = {
    TOY_MARKED.id: TOY_MARKED,
    TOY_PLAIN.id: TOY_PLAIN,
    "toy.untaken": make_rule("toy.untaken", approximate=True, approximate_reason=UNTAKEN_REASON, **UNTAKEN_WORDS),
}  # the module constants above are what MarkedChaos reads; the third rule only an override names

MARKED_LINE = "Only Craft of Exile's code gives the count. Source: Craft of Exile's code only."  # the page and the text report print the
UNTAKEN_LINE = "The chance is a fit to a sample of player results. Source: one player sample."  # statement and the source, never the id (#553, #481)
PAGE_LINE = MARKED_LINE


@dataclasses.dataclass(frozen=True)
class MarkedChaos(ChaosOrb):
    """A Chaos Orb that reads the module's claims, one of them marked."""

    def label(self, data=None) -> str:  # noqa: ANN001
        return "Marked Chaos"


@dataclasses.dataclass(frozen=True)
class UntakenChaos(ChaosOrb):
    """Offered, and read a marked claim, but never chosen by the policies below unless they pick it."""

    def label(self, data=None) -> str:  # noqa: ANN001
        return "Untaken Chaos"

    def claims(self, data=None) -> frozenset[str]:  # noqa: ANN001
        return frozenset({"toy.untaken"})


OFFERS = (
    Offer("Marked Chaos", MarkedChaos(), {CHAOS_ORB: 1}),
    Offer("Untaken Chaos", UntakenChaos(), {CHAOS_ORB: 1}),
)


def lookup(rule_id: str) -> Rule:
    """The toy rules, then the shipped registry (the toy actions subclass a real one, so they read its claims too)."""
    return RULES[rule_id] if rule_id in RULES else rule_by_id(rule_id)


@pytest.fixture(autouse=True)
def toy_registry(monkeypatch):
    monkeypatch.setattr(_marking, "rule_by_id", lookup)


def toy_plan(label: str, offers=OFFERS) -> Plan:
    """A plan whose policy uses the offer called `label` in every state; the solver's values are 1 per state, as the report needs some."""
    start = belt(FRACTURED_COLD, roll("LifeRegeneration1"))
    target = Target(BELT, LEVEL, frozenset(), (COLD_REQ, LIFE), start, start=StartKind.BOUGHT)
    ab = Abstraction(DATA, Goal.from_target(target), BELT, LEVEL, ACTIONS)
    first = ab.compress(start)
    priced, _ = price_offers(offers, PRICES)
    by_label = {offer.label: offer for offer in priced}
    policy = {}
    order = [first]
    for state in order:
        if ab.is_goal(state):
            continue
        policy[state] = offer_action(ab, by_label[label], state)
        order += [s for s, w in policy[state].outcomes if w > 0 and s not in order]
    values = {state: 0.0 if ab.is_goal(state) else 1.0 for state in order}
    return planner_plan(
        target=target, abstraction=ab, leaf_labels=leaf_labels(target), prices=PRICES, start=first,
        start_price=StartPrice(START_NAME, 6.0, "trade-api"), offers=priced,
        solution=Solution(values, policy, 0.0), risk=evaluate(policy, first, ab.is_goal),
        solve_seconds=0.0, risk_seconds=0.0,
    )  # fmt: skip


MARKED = ApproximateInput("toy.marked", "only Craft of Exile's code gives the count", None, "", *TOY_WORDS.values())
UNTAKEN = ApproximateInput("toy.untaken", UNTAKEN_REASON, None, "", *UNTAKEN_WORDS.values())


def test_the_policy_lists_only_the_marked_claims_its_actions_read():
    plan = toy_plan("Marked Chaos")

    assert approximate_inputs(plan, plan.policy, DATA) == (MARKED,)  # toy.plain is not marked


def test_an_offered_action_the_policy_never_takes_is_not_listed():
    plan = toy_plan("Marked Chaos")

    assert "toy.untaken" not in {item.claim for item in approximate_inputs(plan, plan.policy, DATA)}
    assert "Untaken Chaos" in {priced.label for priced in plan.offers}


def test_each_policy_lists_its_own_actions_claims_sorted_by_claim_id():
    plan = toy_plan("Marked Chaos")
    marked_policy = plan.policy
    untaken_policy = toy_plan("Untaken Chaos").policy

    assert approximate_inputs(plan, untaken_policy, DATA) == (UNTAKEN,)
    mixed = dict(marked_policy)
    mixed[plan.start] = untaken_policy[plan.start]  # the start takes the other action, the states after it the first
    assert approximate_inputs(plan, mixed, DATA) == (MARKED, UNTAKEN)  # "toy.marked" sorts before "toy.untaken"


def test_a_policy_that_takes_nothing_reads_nothing():
    plan = toy_plan("Marked Chaos")

    assert approximate_inputs(plan, {}, DATA) == ()


def test_an_action_that_reads_only_unmarked_claims_says_nothing(monkeypatch):
    plan = toy_plan("Marked Chaos")
    monkeypatch.setattr(_marking, "rule_by_id", lambda rule_id: TOY_PLAIN if rule_id == "toy.marked" else lookup(rule_id))

    assert approximate_inputs(plan, plan.policy, DATA) == ()


def test_the_lines_and_the_document_of_the_inputs():
    assert approximate_lines(()) == []
    assert approximate_lines((MARKED, UNTAKEN)) == [
        "Approximate inputs (claims that no other source settles):",
        f"  {MARKED_LINE}",
        f"  {UNTAKEN_LINE}",
    ]
    assert approximate_inputs_document(()) == []
    assert approximate_inputs_document((MARKED,)) == [{"claim": "toy.marked", "reason": MARKED.reason}]


def test_the_text_report_names_the_input_before_the_note_and_the_requirements():
    plan = toy_plan("Marked Chaos")
    report = build_report(plan, DATA)

    text = render_text(report, target_name="Toy")
    lines = text.splitlines()

    assert report.approximate_inputs == (MARKED,)
    at = lines.index("Approximate inputs (claims that no other source settles):")
    assert lines[at + 1] == f"  {MARKED_LINE}"
    assert lines[at - 1] == "Target: Toy"
    assert lines[at + 2].startswith("Requirements:")


def test_the_json_policy_lists_the_input_and_is_an_empty_list_when_there_is_none():
    marked = policy_document(build_report(toy_plan("Marked Chaos"), DATA))
    assert marked["approximate_inputs"] == [{"claim": "toy.marked", "reason": MARKED.reason}]
    json.dumps(marked)  # serialisable

    plain = toy_plan("Marked Chaos")
    unmarked = Report(plain, {}, (), (), approximate_inputs(plain, {}, DATA))
    assert policy_document(unmarked)["approximate_inputs"] == []
    assert "Approximate inputs" not in render_text(unmarked)


def test_an_answer_with_no_marked_claim_prints_no_new_line(monkeypatch):
    monkeypatch.setattr(_marking, "rule_by_id", lambda rule_id: TOY_PLAIN if rule_id == "toy.marked" else lookup(rule_id))
    report = build_report(toy_plan("Marked Chaos"), DATA)

    assert report.approximate_inputs == ()
    assert "Approximate" not in render_text(report)
    assert policy_document(report)["approximate_inputs"] == []


def test_a_given_route_lists_the_inputs_of_its_own_policy_in_text_and_json():
    planner = toy_plan("Marked Chaos")
    report = build_report(planner, DATA)
    other = toy_plan("Untaken Chaos")  # the given route takes the other action
    result = RouteResult(dict(other.policy), other.risk, (), None, 0.0)
    route = Route("Toy route", "toy.yaml", ())

    text = render_route_text(report, route, result, DATA, file_name="toy.yaml").splitlines()
    document = route_document(report, route, result, DATA, file_name="toy.yaml")

    at = text.index("Approximate inputs (claims that no other source settles):")
    assert text[at + 1] == f"  {UNTAKEN_LINE}"  # the route's own, not the planner's
    assert text[0] == "Given route: Toy route (toy.yaml)" and at > 1
    assert MARKED_LINE not in "\n".join(text)
    assert document["approximate_inputs"] == [{"claim": "toy.untaken", "reason": UNTAKEN_REASON}]

    same = RouteResult(dict(planner.policy), planner.risk, (), None, 0.0)
    assert route_document(report, route, same, DATA, file_name="toy.yaml")["approximate_inputs"] == [
        {"claim": "toy.marked", "reason": MARKED.reason}
    ]


def test_a_given_route_that_reads_nothing_marked_says_nothing_in_text_and_json():
    planner = toy_plan("Marked Chaos")
    report = build_report(planner, DATA)
    empty = RouteResult({}, planner.risk, (), None, 0.0)
    route = Route(None, "toy.yaml", ())

    assert "Approximate" not in render_route_text(report, route, empty, DATA, file_name="toy.yaml")
    assert route_document(report, route, empty, DATA, file_name="toy.yaml")["approximate_inputs"] == []


def fields_of(inp: RouteInput) -> dict[str, list[str]]:
    return {field.label: [line.text for line in field.lines] for field in build_section(inp, DATA).goal.fields}


def test_the_goal_card_of_the_page_has_an_approximate_inputs_field_between_success_and_prices():
    fields = fields_of(route_input(toy_plan("Marked Chaos")))

    assert fields["Approximate inputs"] == [PAGE_LINE]
    labels = list(fields)
    assert labels.index("Approximate inputs") == labels.index("Prices") - 1
    assert labels.index("9 runs in 10") < labels.index("Approximate inputs")


def test_the_goal_card_marks_the_field_as_a_warning():
    section = build_section(route_input(toy_plan("Marked Chaos")), DATA)

    (field,) = [field for field in section.goal.fields if field.label == "Approximate inputs"]
    assert field.tone == "warn"


def test_the_planner_and_a_given_route_each_list_their_own_inputs_on_the_page():
    planner = route_input(toy_plan("Marked Chaos"))
    other = toy_plan("Untaken Chaos")
    given_inp = dataclasses.replace(planner, label="Given route: toy", policy=other.policy)

    assert fields_of(planner)["Approximate inputs"] == [PAGE_LINE]
    assert fields_of(given_inp)["Approximate inputs"] == [UNTAKEN_LINE]


def test_a_goal_card_with_no_marked_claim_has_no_such_field(monkeypatch):
    monkeypatch.setattr(_marking, "rule_by_id", lambda rule_id: TOY_PLAIN if rule_id == "toy.marked" else lookup(rule_id))

    assert "Approximate inputs" not in fields_of(route_input(toy_plan("Marked Chaos")))


def test_a_claim_marked_in_the_registry_reaches_the_report_through_a_real_action(monkeypatch):
    real = get_rule("chaos_orb.cost")
    reason = "a toy mark on a real claim"
    marked = dataclasses.replace(real, approximate=True, approximate_reason=reason, page_statement="A toy mark on a real claim.", page_source="a test")
    monkeypatch.setattr(_marking, "rule_by_id", lambda rule_id: marked if rule_id == real.id else rule_by_id(rule_id))
    plan = toy_plan("Chaos Orb", (Offer("Chaos Orb", ChaosOrb(), {CHAOS_ORB: 1}),))
    report = build_report(plan, DATA)

    assert report.approximate_inputs == (ApproximateInput("chaos_orb.cost", reason, None, "", "A toy mark on a real claim.", "a test"),)
    assert "  A toy mark on a real claim. Source: a test." in render_text(report).splitlines()
    assert "chaos_orb.cost" not in render_text(report) and reason not in render_text(report)  # the text report names no id and no reason (#604)
    assert policy_document(report)["approximate_inputs"] == [{"claim": "chaos_orb.cost", "reason": reason}]
    assert fields_of(route_input(plan))["Approximate inputs"] == ["A toy mark on a real claim. Source: a test."]


# -- a person reads the statement and the source, never the id or the reason (#553, #481, #604, #605) -------------------------


def test_the_page_line_of_an_input_is_its_statement_its_source_and_its_spread_and_never_its_id_or_its_reason():
    spread = ApproximateInput("recombinator.count_table", "internal reason", {"kind": "alternative_table"}, "the guide's table is used", "The table is measured.", "a player guide")

    assert approximate_page_line(MARKED) == MARKED_LINE
    assert approximate_page_line(spread) == "The table is measured. Source: a player guide. Spread: the guide's table is used."
    assert "toy.marked" not in approximate_page_line(MARKED) and MARKED.reason not in approximate_page_line(MARKED)


def test_two_inputs_that_say_the_same_to_a_person_are_printed_once_on_the_page_and_in_the_text():
    twin = dataclasses.replace(MARKED, claim="toy.twin", reason="another reason")

    assert approximate_page_lines((MARKED, twin, UNTAKEN)) == [MARKED_LINE, UNTAKEN_LINE]
    assert approximate_lines((MARKED, twin, UNTAKEN)) == [
        "Approximate inputs (claims that no other source settles):",
        f"  {MARKED_LINE}",
        f"  {UNTAKEN_LINE}",
    ]


HTML = (
    '<html><body><main><h1>t</h1><section id="policy"><div class="rw"><div class="cd tg"><h3>Route goal</h3><div class="f">'
    '<div class="k">Approximate inputs</div><div class="vl ml"><div>%s</div></div></div></div></div><div class="rw"><div class="cd" id="s1"><h3>1. Regal Orb</h3>'
    '<div class="f"><div class="k">Cost per use</div><div class="v ml"><div>1 c</div></div></div></div></div></section></main></body></html>'
)


def test_the_page_line_of_every_approximate_claim_of_the_registry_says_what_and_from_where_and_names_no_internal_thing():
    """Each claim marked approximate, as a page prints it (with its spread where it has one): the lint's check of the sources and of
    internal names finds nothing, and a person reads more than a name (the lint's own check of the line holds OR-23 again)."""
    marked = [rule for rule in load_registry().values() if rule.approximate]
    assert len(marked) > 100

    faults = []
    for rule in marked:
        spread = _marking.claim_interval(rule)
        item = ApproximateInput(rule.id, rule.approximate_reason, *(spread or (None, "")), rule.page_statement, rule.page_source)
        shown = page_lint.read_page(HTML % escape(approximate_page_line(item)))
        faults += [f"{rule.id}: {fault}" for fault in page_lint.check_no_internal_names(shown)]
        faults += [f"{rule.id}: {fault}" for fault in page_lint.check_approximate_marked(shown)]
    assert faults == []
