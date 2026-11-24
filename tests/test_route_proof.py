"""The route page says truthfully how far the planner proved its plan, in a player's words (#1161, #1508, #1512; OR-13, OR-33, OR-40).

R12 on the fixture data is planned once; its search's record is then set as each case needs it (stopped by time with a plan in hand, proved
within the run's gap, exact), with the rounds' limits the planner writes for those records (`_rounds.rounds_limits`), and the page is drawn
through `build_section`, as `write_route_page` draws it.
"""

from __future__ import annotations

import dataclasses
import re
from types import SimpleNamespace

import pytest
from cli_support import R12, price_file
from items_support import DATA

from crafting_system.budget import Budget
from crafting_system.cli import make_plan
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_proof import UNTRIED_TITLE
from crafting_system.cli._route_view import Page, build_section, money, route_input
from crafting_system.planner import _limits
from crafting_system.planner._price_cut import price_cut_limit
from crafting_system.planner._rounds import BEATEN, CLOSED, STOPPED, UNTRIED, RoundRecord, rounds_limits
from crafting_system.targets import load_target

# words of the search that no line of a planner's page may hold (#1161: R14's and R20's pages)
SEARCH_WORDS = re.compile(r"stated gap|gave way|\brounds?\b|time limit of|plan in hand|\b[a-z]+(?:-[a-z]+)+\b")

GROWN = "the plan's dearest step not yet read, Essence of Horror (35,058,189.45 Chaos of the plan), waits for mods"
STOPPED_ROUNDS = (
    RoundRecord(("Orb of Alchemy", "Essence of Horror"), 2, CLOSED, "", 30.0, 30.0, 8.0, growth="the seed: the cheapest methods for each wanted mod, by cost over chance"),
    RoundRecord(("Orb of Annulment", "Essence of Horror"), 3, BEATEN, "no plan with these methods costs less than the plan in hand (to within the gap of 1.00% this run allows)", 29.9, None, 2.0, within=0.01, growth=GROWN),
    RoundRecord(("Harvest Reforge Influence", "Essence of Horror"), 9, STOPPED, "the time limit of 0 seconds was reached; the growth reads on with the next lock group", 0.2, None, 418.0, growth=GROWN),
    RoundRecord(("alchemy-orb",), 4, STOPPED, "the time limit of 0 seconds was reached", 0.02, None, 4.0),
    RoundRecord(("harvest-reforge-likelihood",), 2, UNTRIED, "the run's time was used up before this round", None, None, 0.0),
)
CLOSED_ROUNDS = (
    RoundRecord(("chaos-orb",), 2, CLOSED, "", 235.04, 235.04, 0.0),
    RoundRecord(("harvest-reforge",), 18, CLOSED, "", 39.93, 39.93, 1.0),
    RoundRecord(("essence", "fossil-set"), 9297, BEATEN, "no plan with these methods costs less than the plan in hand", 39.93, None, 15.0, within=0.01),
)


@pytest.fixture(scope="module")
def r12():
    return make_plan(DATA, load_target(R12, DATA), price_file(), budget=Budget.in_states(200_000))


def searched(plan, records, **search):
    """`plan` as if its search had ended as `search` says, over `records`, with the limits the planner writes for them."""
    info = plan.search
    assert info is not None, "the fixture plan is made by the envelope search"
    info = dataclasses.replace(info, widening=records, **search)
    packed = dataclasses.replace(plan.packed, info={**plan.packed.info, "envelope": info})
    own = tuple(limit for limit in plan.limits if limit.kind not in (_limits.ROUNDS, _limits.UNTRIED))
    exact = info.exact
    within = max((record.within for record in records if record.within is not None), default=None)
    cut = price_cut_limit([SimpleNamespace(label="Harvest Reforge Elemental")], plan.start_price.chaos, 235.04)
    limits = (*own, cut, *rounds_limits(records, exact, within)) if records else (*own, cut)
    # the claims of cheapness as the planner writes them for an answer that is not exact ("within the stated gap", `Plan.__post_init__`)
    return dataclasses.replace(plan, packed=packed, limits=limits)


def goal(plan):
    section = build_section(route_input(plan), DATA)
    fields = {field.label: field for field in section.goal.fields}
    leaves = [(field.label, line) for field in section.goal.leaves_out for line in field.lines]
    return section, fields, leaves


def every_word(fields, leaves) -> str:
    return "\n".join([line.text for field in fields.values() for line in field.lines] + [f"{label}: {line.text} {' '.join(line.more)}" for label, line in leaves])


def test_a_plan_whose_search_was_stopped_is_the_best_found_never_the_cheapest(r12):
    # #1161: R20's page on a808862e said "Cheapest policy of the planner" and "within the stated gap of the cheapest" over a search stopped by time
    plan = searched(r12, STOPPED_ROUNDS, exact=False, within=None, stopped="not every round of the methods finished", lower=0.0)
    section, fields, leaves = goal(plan)

    assert fields["Route"].lines[0].text == "The planner's plan" and section.title == "The planner's plan"
    proof = fields["Proof"]
    assert proof.tone == "warn"
    assert proof.lines[0].text.startswith("Not proved the cheapest: this is the best plan the search found in the time and memory it was given, and a cheaper one may exist.")
    assert "5 batches and finished 2 of them" in proof.lines[0].text  # how far it got: the closed and the beaten batch
    words = every_word(fields, leaves)
    assert "Cheapest" not in words and "within the stated gap" not in words and "1%" not in proof.lines[0].text
    for label, line in leaves:
        assert not SEARCH_WORDS.search(line.text + " ".join(line.more)), (label, line.text)
        if "cheapest" in line.text and label != "How the methods were searched":
            assert "the best the search found before it stopped, not proved the cheapest" in line.text, line.text
    rounds = next(line for label, line in leaves if label == "How the methods were searched")
    assert "not proved the cheapest" in rounds.text and "may cost less" in rounds.text
    assert rounds.more[2] == (
        "Batch 3 (methods the plan found so far uses or needs: Harvest Reforge Influence, Essence of Horror; 9 actions): not finished: the time "
        "set aside for it ran out, with no plan."
    )  # no "0 seconds", no lower figure of an unfinished search (R20: "no plan with them costs less than 26.18 Chaos" beside 206k)
    assert rounds.more[3].startswith("Batch 4 (Orb of Alchemy with the methods of the plan found so far; 4 actions)")
    assert rounds.more[4] == "Batch 5 (Harvest reforges that favour a mod with the methods of the plan found so far; 2 actions): not searched: the time ran out before it."
    untried = next(line for label, line in leaves if label == UNTRIED_TITLE)
    # the alchemy orb of the unfinished batch 4 was searched in the finished batch 1: it is not listed as not searched (crafter, #1161)
    assert "Orb of Alchemy" not in untried.text and "Harvest Reforge Influence" in untried.text and "Harvest reforges that favour a mod" in untried.text
    assert "a plan that uses them may cost less" in untried.text


def test_a_plan_proved_within_the_gap_says_the_gap_and_the_figure_in_the_terms_of_its_mean(r12):
    # #1508: "within the stated gap" in four notes, 1% only at the end of the rounds; the proof's figure without the start item's price
    lower = r12.risk.mean.value * 0.995
    plan = searched(r12, CLOSED_ROUNDS, exact=False, within=0.01, stopped=None, lower=lower)
    _, fields, leaves = goal(plan)
    start = plan.start_price.chaos

    proof = fields["Proof"].lines[0].text
    assert fields["Proof"].tone == ""
    assert proof.startswith("Proved within 1% of the cheapest of the methods searched: no plan of them costs less than ")
    assert money(lower + start) in proof and money(lower) in proof and money(start) in proof
    assert proof.endswith(f", so this plan is at most {money(r12.risk.mean.value - lower)} dearer than the cheapest.")
    words = every_word(fields, leaves)
    assert "stated gap" not in words and "Cheapest" not in words
    for label, line in leaves:
        assert not SEARCH_WORDS.search(line.text + " ".join(line.more)), (label, line.text)
    claims = [line.text for _, line in leaves if "of the cheapest" in line.text]
    assert claims and all("within 1% of the cheapest" in text for text in claims)
    rounds = next(line for label, line in leaves if label == "How the methods were searched")
    assert rounds.text.startswith("The planner searched the methods in 3 batches and finished every one. The plan is within 1% of the cheapest")
    assert rounds.more[0] == f"Batch 1 (Chaos Orb; 2 actions): finished; its best plan costs {money(235.04)} of crafting."
    assert rounds.more[2].startswith("Batch 3 (Essences, Fossil sets with the methods of the earlier batches; 9,297 actions): finished early: these methods cannot beat")


def test_an_exact_plan_is_the_cheapest_of_the_methods_searched(r12):
    plan = searched(r12, (), exact=True, within=None, stopped=None)
    _, fields, _ = goal(plan)
    assert fields["Proof"].lines[0].text.startswith("Proved the cheapest of the methods searched")


def test_actions_ruled_out_by_price_are_said_against_the_plan_shown(r12):
    # #1512: "at least 236.04 c a use: ... a plan already found (235.04 on average)" beside a plan of 40.93 c
    plan = searched(r12, CLOSED_ROUNDS, exact=False, within=0.01, stopped=None, lower=r12.risk.mean.value)
    _, _, leaves = goal(plan)
    (line,) = [line for label, line in leaves if line.text.startswith("Not searched: Harvest Reforge Elemental")]
    whole = money(plan.start_price.chaos + plan.risk.mean.value)
    assert f"buying a new start item and following this plan from there ({whole} in all)" in line.text
    assert "235.04" not in line.text and "236.04" not in line.text


def test_the_batches_are_drawn_one_to_a_line(r12):
    plan = searched(r12, STOPPED_ROUNDS, exact=False, within=None, stopped="not every round of the methods finished", lower=0.0)
    html = render_page(Page("Route to craft: Paua Amulet", (build_section(route_input(plan), DATA),)))
    assert "<summary>each batch</summary><div>Batch 1 (" in html
