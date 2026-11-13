"""The answer carries its limits (ticket #459, OR-13): one `Limit` record in `Plan.limits`, shown in the text, the JSON and the route page.

One test per source of a limit, by the row of the fact base (`docs/research/2026-11-06-rebuild-3-5-inventory.md`, Part B):

* K1 kinds a target must name: `test_k1_*`. K2 kinds the planner cannot use: `test_k2_*`. K3, K6 and G1 Memory Strands:
  `test_g1_*`. K4 kinds the target does not name: `test_k4_*`. K5 a corrupting kind: `test_k5_*` and
  `test_actions_corrupting_toy.py`. K10 Remove Crafted Mods: `test_k10_*`. U1 an unpriced action: `test_u1_*`.
* K7 a craft that counts for nothing: `test_cli_offers.py`, `test_actions_toy.py`. K8 a fixed mod nobody wants:
  `test_offers_wanted_only.py`. K9 a value reroll: `test_cli_offers_divine.py`. K15 the pruning: `test_prune_bound.py`.
* Checker points of PR #479: the cheapest claim of an approximate answer `test_an_exact_plan_claims_*`, G20 through `make_plan` and `add_risk`
  `test_g20_*` and `test_add_risk_*`, no withheld kind hidden `test_the_text_and_the_json_name_every_*`, the cause of a withheld corrupting set
  `test_actions_fossil_bloodstained.py`.
* G12 a whole search run past the budget: `test_g12_*`. G13 the packed solver: `test_cli_decide.py`. G14 a tree of groups:
  `test_g14_*`. G19 percentiles not computed: `test_g19_*` and `test_packed_plan_real.py`. G20 a quantile the grid cannot reach: `test_g20_*`.
* P1 a given start item, P3 no restart for it: `test_p1_*`, `test_p3_*`.

Then what the three surfaces show: the text report, the JSON `crafting-system-policy/3` and the goal card of the route page.
"""

import dataclasses
import datetime
import json
import math
import re
from html import escape
from types import SimpleNamespace

import pytest
from cli_support import R12, given, price_file, read_json
from coarse_support import CRAFTS, REMOVE
from coarse_support import DATA as COARSE
from limits_support import labels_of, of_kind, only, sentences
from targets_support import DATA
from test_cli_approximate import PRICES as APPROX_PRICES
from test_cli_approximate import RATES as APPROX_RATES
from test_cli_approximate import TARGET as APPROX_TARGET

from crafting_system.cli import Limit, build_report, make_plan, offers_for, policy_document, render_text
from crafting_system.cli import _plan
from crafting_system.cli._limits import GROUPS, SHOWN_LABELS, WITHIN_GAP, approximate_limits, claim, grouped, kind_title, limit_document, limit_text, risk_limits
from crafting_system.cli._offers import offer_of
from crafting_system.cli._plan import add_risk
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_view import Page, PageError, build_section, route_input
from crafting_system.abstraction import Coarsening, Goal, Wanted
from crafting_system.prices import PriceEntry
from crafting_system.risk import Estimate
from crafting_system.risk._report import GridInfo
from crafting_system.targets import load_target, parse_target
from crafting_system.actions import kinds


@pytest.fixture(scope="module")
def plan():
    return make_plan(DATA, load_target(R12, DATA), price_file())


# --- the sources ---------------------------------------------------------------------------------------------


def test_k1_a_target_without_actions_lists_the_kinds_it_would_have_to_name(plan):
    withheld = only(plan.limits, "kinds-opt-in")

    assert {"Exalted Orb", "Annulment Orb", "Fracturing Orb", "Fossil sets"} <= set(withheld.labels)
    assert withheld.why == "kinds that are offered only when a target names them"
    assert "cheapest among the kinds offered" in withheld.guarantee
    assert not of_kind(plan.limits, "kinds-not-named")  # the target has no `actions:` key


def test_k4_a_target_with_actions_lists_the_kinds_it_does_not_name():
    target = load_target(R12, DATA)

    chosen = offers_for(DATA, Goal.from_target(target), target.base_id, target.start_item, ["chaos-orb"])

    named = only(chosen.limits, "kinds-not-named")
    assert "Exalted Orb" in named.labels and "Chaos Orb" not in named.labels
    assert limit_text(named).endswith("(kinds this target does not name). The plan is the cheapest among the kinds offered.")
    assert not of_kind(chosen.limits, "kinds-opt-in")  # one or the other: the target either names its kinds or it does not


def test_k4_the_sentence_of_the_ticket_is_what_the_report_prints():
    limit = Limit("kinds-not-named", "Not offered", "kinds this target does not name", labels=("Exalted Orb", "Annulment Orb"), **claim("the kinds offered"))

    assert limit_text(limit) == (
        "Not offered: Exalted Orb, Annulment Orb (kinds this target does not name). The plan is the cheapest among the kinds offered."
    )


def test_k2_the_kinds_the_planner_cannot_use_yet_are_listed_in_every_answer(plan):
    cannot = only(plan.limits, "kinds-not-built")

    assert len(cannot.labels) == sum(not entry.planner for entry in kinds())
    assert {"Alchemy Orb", "Scouring Orb"} <= set(cannot.labels)


def test_g1_k3_k6_the_kinds_that_need_memory_strands_are_one_limit_named_in_player_words(plan):
    strands = only(plan.limits, "strands")

    assert strands.labels == ("Foulborn Augmentation Orb", "Foulborn Regal Orb", "Foulborn Exalted Orb", "Orb of Remembrance")
    assert strands.guarantee == "The plan makes no use of Memory Strands."
    assert "Foulborn Exalted Orb" not in labels_of(plan.limits, "kinds-opt-in")  # counted once


def test_k5_a_corrupting_kind_is_named_as_unused_for_a_target_that_takes_no_corrupted_item():
    target = load_target(R12, DATA)

    chosen = offers_for(DATA, Goal.from_target(target), target.base_id, target.start_item, ["chaos-orb"])

    corrupting = only(chosen.limits, "corrupting")
    assert "Vaal Orb" in corrupting.labels and "unaffected" in corrupting.guarantee


def test_k10_remove_crafted_mods_is_named_when_no_crafted_mod_can_exist(plan):
    removed = only(plan.limits, "crafted-mods")

    assert removed.labels == ("Remove Crafted Mods",)
    assert "nothing to remove" in removed.why


def test_u1_the_actions_without_a_price_are_limits_grouped_by_what_is_missing(plan):
    unpriced = of_kind(plan.limits, "unpriced")

    assert unpriced and all(limit.names and limit.labels for limit in unpriced)
    assert len({limit.names for limit in unpriced}) == len(unpriced)  # one limit for each set of missing prices
    assert all(limit.why == "no price for {names}" and limit.reason() == f"no price for {', '.join(limit.names)}" for limit in unpriced)  # the names live in `names` only
    assert "Harvest Reforge Fire" in labels_of(plan.limits, "unpriced")


def test_g12_a_search_run_whole_past_the_budget_says_so_and_stays_exact():
    limits = make_plan(DATA, load_target(R12, DATA), price_file(), budget=1e-9, solver="packed").limits
    (solved,) = [limit for limit in of_kind(limits, "how-solved") if limit.what == "The whole search was run"]

    assert "no approximate answer was possible" in solved.why
    assert solved.guarantee == "The answer is exact among the methods offered."


def test_g21_a_policy_evaluation_that_stopped_short_of_the_exact_system_reaches_the_plans_limits(monkeypatch):
    """#621, OR-13: `info["linear_limit"]` of the packed solve is read by `make_plan`, so the reader is told (it was written by the solver and read by nobody)."""
    real = _plan.packed_result
    plain = make_plan(DATA, load_target(R12, DATA), price_file(), solver="packed")

    def stopped_short(*args, **kwargs):
        packed = real(*args, **kwargs)
        packed.info["linear_limit"] = {"states": 123_456, "residual": 3e-8, "amplification": 2.5e5, "why": "x", "rows": 900, "cells": 5e9, "allowed": 2.5e8}
        return packed

    monkeypatch.setattr(_plan, "packed_result", stopped_short)
    plan = make_plan(DATA, load_target(R12, DATA), price_file(), solver="packed")

    (said,) = [limit for limit in plan.limits if limit.what == "How much each state costs was found by approximation"]
    assert "123,456 states" in said.why and "3.0e-08" in said.why and "250,000" in said.why and "40.0 GB" in said.why
    assert not [limit for limit in plain.limits if "found by approximation" in limit.what]  # an exact solve says nothing


def test_g14_a_tree_of_groups_of_item_states_says_it_and_keeps_the_numbers_exact(monkeypatch):
    monkeypatch.setattr(_plan, "VIEW_FROM_STATES", 0)

    shown = only(make_plan(DATA, load_target(R12, DATA), price_file(), solver="packed").limits, "display")

    assert shown.what == "The tree shows groups of states" and "are one group" in shown.why
    assert shown.guarantee == "The odds and every cost figure are exact for the groups."


def test_g19_percentiles_the_memory_cannot_hold_are_a_limit_with_exact_odds_and_mean(monkeypatch):
    monkeypatch.setattr(_plan, "RISK_QUANTILE_TRANSITIONS", 0)

    cut = only(make_plan(DATA, load_target(R12, DATA), price_file(), solver="packed").limits, "risk")

    assert cut.what == "Not computed: the median cost, the cost 9 runs in 10 stay under, and the average of the worst tenth" and cut.guarantee == "The odds, the mean and the variance are exact."


def test_g20_a_quantile_the_grid_cannot_reach_is_a_limit_and_a_reached_one_is_not():
    def estimate(value):
        return Estimate(value, value, value)

    grid = GridInfo(0.5, True, 100, 0.0, 0.0)
    mean, variance = {"mean": estimate(5.0), "variance": estimate(1.0)}, {"mean": estimate(float("inf")), "variance": estimate(float("inf"))}
    unreached = SimpleNamespace(success_probability=estimate(1.0), **mean, p50=estimate(10.0), p90=estimate(float("inf")), cvar=estimate(float("inf")), grid=grid)
    reached = SimpleNamespace(success_probability=estimate(1.0), **mean, p50=estimate(10.0), p90=estimate(20.0), cvar=estimate(30.0), grid=grid)
    failing = SimpleNamespace(success_probability=estimate(0.5), **variance, p50=estimate(float("inf")), p90=estimate(float("inf")), cvar=estimate(float("inf")), grid=grid)

    (limit,) = risk_limits(unreached)
    assert limit.what == "Not computed: the cost 9 runs in 10 stay under and the average of the worst tenth" and limit.guarantee == "The success chance and the mean cost are exact."
    assert risk_limits(reached) == () and risk_limits(failing) == () and risk_limits(None) == ()


def test_p1_a_given_start_item_says_its_cost_is_not_counted_and_the_plan_never_buys_another():
    free = make_plan(DATA, given(load_target(R12, DATA)), price_file())

    (counted,) = [limit for limit in free.limits if limit.what == "The start item is given"]
    assert counted.why == "the target says the player already holds it"
    assert counted.guarantee == "The plan is the cheapest among the plans that never start over. The cost of the start item is not counted, and the plan never buys another."
    assert not [limit for limit in free.limits if limit.what in ("The start item is counted as free", "No restart")]


def test_p3_a_given_start_item_has_no_restart_offer_whatever_the_price_file_holds():
    free = make_plan(DATA, given(load_target(R12, DATA)), price_file(start=4.0))  # the file prices the item: a given item is still never bought again

    assert all(priced.label != "restart" for priced in free.offers)
    assert free.start_price.given and free.start_price.chaos == 0.0


def test_a_priced_start_item_has_neither_start_limit(plan):
    assert not of_kind(plan.limits, "start-item")


# --- OR-5, OR-13: a target with an `actions:` key and one without both list what is withheld ----------------


def test_a_target_with_an_actions_key_and_a_target_without_one_both_list_what_is_withheld(tmp_path):
    text = R12.read_text(encoding="utf-8")
    keyed = tmp_path / "keyed.yaml"
    keyed.write_text(text + "actions: [harvest-reforge, chaos-orb]\n", encoding="utf-8")

    for path, kind in ((R12, "kinds-opt-in"), (keyed, "kinds-not-named")):
        made = make_plan(DATA, load_target(path, DATA), price_file())
        report = render_text(build_report(made, DATA))
        withheld = only(made.limits, kind)

        assert "Exalted Orb" in withheld.labels
        assert f"  {limit_text(withheld)}" in report.splitlines() or limit_text(withheld) in report
        assert withheld.guarantee in report  # OR-13


# --- every limit has a guarantee, in player words -----------------------------------------------------------


def test_every_limit_of_an_answer_has_a_guarantee_without_internal_names(plan):
    for limit in plan.limits:
        assert limit.guarantee.endswith(".") and limit.guarantee[0].isupper()
        assert not re.search(r"[a-z]+-[a-z]+-?[a-z]*|_|`|#\d|ticket|ADR|OR-\d|\bkind\b=", limit.guarantee), limit.guarantee


def test_a_limit_without_a_guarantee_cannot_be_made():
    with pytest.raises(ValueError, match="needs a guarantee"):
        Limit("kinds-not-named", "Not offered", "kinds this target does not name", " ")


def test_a_kind_of_the_catalog_is_written_as_a_player_writes_it():
    assert kind_title("exalted-orb") == "Exalted Orb" and kind_title("orb-of-dominance") == "Orb of Dominance"
    assert all(kind_title(entry.name) != entry.name and kind_title(entry.name)[0].isupper() for entry in kinds())


def test_the_groups_have_a_title_each_and_a_group_unknown_to_the_list_is_shown_last():
    assert len({kind for kind, _ in GROUPS}) == len(GROUPS)
    odd = Limit("brand-new-kind", "Not offered", "", "The plan is unaffected.")
    first = Limit("kinds-not-named", "Not offered", "", "The plan is unaffected.")

    assert [title for title, _ in grouped([odd, first])] == ["Methods the target does not name", "brand-new-kind"]


# --- the three surfaces ---------------------------------------------------------------------------------------


def test_a_limit_with_many_labels_shows_its_count_and_the_first_three_and_the_json_keeps_all():
    labels = tuple(f"Kind {n}" for n in range(1, 11))
    limit = Limit("kinds-not-named", "Not offered", "kinds this target does not name", labels=labels, **claim("the kinds offered"))

    assert SHOWN_LABELS == 3
    assert limit_text(limit, SHOWN_LABELS).startswith("Not offered, 10 in all: Kind 1, Kind 2, Kind 3 and 7 more (kinds this target does not name).")
    assert limit_text(limit).startswith("Not offered, 10 in all: " + ", ".join(labels) + " (kinds this target does not name).")  # the text names every label
    assert limit_document(limit)["labels"] == list(labels) and limit_document(limit)["count"] == 10


def test_the_text_report_the_json_and_the_page_show_the_same_records(plan):
    report = build_report(plan, DATA)
    text = render_text(report)
    document = policy_document(report)
    page = render_page(Page("x", (build_section(route_input(plan), DATA),)))

    assert document["format"] == "crafting-system-policy/3"
    assert not {"note", "dropped_actions", "left_out_actions"} & set(document)
    assert [entry["kind"] for entry in document["limits"]] == [limit.kind for limit in sorted(plan.limits, key=lambda l: [k for k, _ in GROUPS].index(l.kind))]
    for limit in plan.limits:
        assert limit_text(limit) in text  # the text report names every label
        assert escape(limit_text(limit, SHOWN_LABELS)) in page
        assert all(escape(label) in page for label in limit.labels)  # the page holds every label too
    assert "What this answer leaves out" in text and "What this answer leaves out" in page


def test_the_goal_card_of_the_page_has_the_section_grouped_by_kind(plan):
    card = build_section(route_input(plan), DATA).goal

    titles = [field.label for field in card.leaves_out]
    assert titles == [title for title, _ in grouped(plan.limits)]
    assert "Methods offered only when the target names them" in titles and "Memory Strands" in titles
    assert [line.text for field in card.leaves_out for line in field.lines] == sentences(sorted(plan.limits, key=lambda l: [k for k, _ in GROUPS].index(l.kind)), SHOWN_LABELS)
    assert "leaves_out" not in [field.label for field in card.fields]


def test_a_plan_with_no_limit_is_refused_by_the_page_builder_not_drawn_without_the_section(plan):
    bare = dataclasses.replace(plan, limits=())

    with pytest.raises(PageError, match="no limits"):  # a page with no section "What this answer leaves out" claims a guarantee it does not state (OR-13, #550)
        build_section(route_input(bare), DATA)


def test_the_json_limit_is_the_record_with_every_field(plan, tmp_path):
    from cli_support import run

    code, out = run(tmp_path, prices=price_file())

    assert code == 0
    document = read_json(out)
    for entry in document["limits"]:
        assert set(entry) == {"kind", "what", "why", "guarantee", "count", "labels", "names"}
        assert entry["count"] == len(entry["labels"]) and entry["guarantee"]
    assert document["format"] == "crafting-system-policy/3"


# --- G20 on a real plan: through `make_plan` and through `add_risk` -------------------------------------------------


@pytest.fixture
def grid_too_small(monkeypatch):
    """A quantile grid of 3 bins: the p90 of R12 (about 49 clicks of 0.5 Chaos) is out of its reach, as with a cost scale far above the cheapest step."""
    monkeypatch.setattr(_plan, "RISK_BINS", 1)
    monkeypatch.setattr(_plan, "UNRESOLVED_BINS", 3)
    monkeypatch.setattr(_plan, "COARSE_BINS", 3)


def test_g20_a_plan_whose_p90_the_grid_does_not_reach_has_the_risk_limit_from_make_plan(grid_too_small):
    made = make_plan(DATA, load_target(R12, DATA), price_file())

    assert math.isinf(made.risk.p90.value) and made.risk.success_probability.value == 1.0  # the odds are 1: only the grid failed
    cut = only(made.limits, "risk")
    assert cut.what == "Not computed: the median cost, the cost 9 runs in 10 stay under, and the average of the worst tenth" and cut.guarantee == "The success chance and the mean cost are exact."
    assert limit_text(cut) in render_text(build_report(made, DATA))


def test_g20_the_same_limit_comes_from_add_risk(grid_too_small):
    bare = make_plan(DATA, load_target(R12, DATA), price_file(), with_risk=False)

    again = add_risk(bare)

    assert not of_kind(bare.limits, "risk") and math.isinf(again.risk.p90.value)
    assert only(again.limits, "risk") == only(make_plan(DATA, load_target(R12, DATA), price_file()).limits, "risk")


def test_g20_a_plan_whose_grid_reaches_its_p90_has_no_risk_limit(plan):
    assert math.isfinite(plan.risk.p90.value) and not of_kind(plan.limits, "risk")


def test_add_risk_replaces_a_risk_limit_it_finds_and_does_not_add_a_second(grid_too_small):
    bare = make_plan(DATA, load_target(R12, DATA), price_file(), with_risk=False)
    stale = Limit("risk", "Not computed: p50", "an earlier run", "The success chance and the mean cost are exact.")

    again = add_risk(dataclasses.replace(bare, limits=(*bare.limits, stale)))

    assert stale not in again.limits and len(of_kind(again.limits, "risk")) == 1


def test_add_risk_drops_a_stale_risk_limit_when_the_grid_reaches_every_percentile(plan):
    bare = make_plan(DATA, load_target(R12, DATA), price_file(), with_risk=False)
    stale = Limit("risk", "Not computed: p50", "an earlier run", "The success chance and the mean cost are exact.")

    again = add_risk(dataclasses.replace(bare, limits=(*bare.limits, stale)))

    assert not of_kind(again.limits, "risk")


# --- OR-13: a claim of the cheapest plan comes from the solve that made the answer ----------------------------------


@pytest.fixture(scope="module")
def approximate_pair():
    """The coarse fixture of `test_cli_approximate` planned through `offers_for` (the target names its crafts), exact and then approximate."""
    names = set()
    for action in (*CRAFTS, REMOVE):
        names |= set(offer_of(action, action.label(COARSE), COARSE).resources)
    prices = dataclasses.replace(APPROX_PRICES, prices={name: PriceEntry(2.0, "test") for name in names})
    keys = json.dumps(["chaos-orb", "remove-crafted-mods", *(craft.label(COARSE) for craft in CRAFTS)])
    target = parse_target(APPROX_TARGET + f"actions: {keys}\n", COARSE, source="t.yaml")
    exact = make_plan(COARSE, target, prices, solver="object")
    forecast = exact.abstraction.estimate([exact.start], [priced.offer.action for priced in exact.offers])
    pooling = Coarsening.pooling_irrelevant(exact.abstraction, None, exact.start)
    budget = (forecast.seconds(1.0, 1.0) + forecast.coarsened(pooling).seconds(1.0, 1.0)) / 2
    return exact, make_plan(COARSE, target, prices, budget=budget, rates=APPROX_RATES, solver="object")


def test_an_exact_plan_claims_the_cheapest_and_an_approximate_one_only_within_its_gap(approximate_pair):
    exact, approximate = approximate_pair

    assert exact.approximation is None and approximate.approximation is not None
    for plan_ in (exact, approximate):  # both have the kind limits of `offers_for` and the start limit
        assert {"kinds-not-named", "kinds-not-built", "start-item"} <= {limit.kind for limit in plan_.limits}
    claims = [limit for limit in exact.limits if "cheapest" in limit.guarantee]
    assert len(claims) >= 3 and all(limit.guarantee.startswith("The plan is the cheapest") for limit in claims)
    gapped = [limit for limit in approximate.limits if "cheapest" in limit.guarantee]
    assert [limit.kind for limit in gapped] == [limit.kind for limit in claims]  # every claim is still there ...
    assert all(WITHIN_GAP in limit.guarantee and not limit.guarantee.startswith("The plan is the cheapest") for limit in gapped)  # ... and none says "the cheapest"
    text = render_text(build_report(approximate, COARSE))
    assert "Answer:" in text and "The plan is the cheapest" not in text and WITHIN_GAP in text


def test_a_guarantee_that_claims_the_cheapest_plan_must_have_its_form_for_an_approximate_answer():
    with pytest.raises(ValueError, match="claims the cheapest plan"):
        Limit("kinds-not-named", "Not offered", "kinds this target does not name", "The plan is the cheapest among the kinds offered.")
    made = Limit("kinds-not-named", "Not offered", "", **claim("the kinds offered"))
    assert approximate_limits([made])[0].guarantee == "The plan is within the stated gap of the cheapest among the kinds offered."


# --- OR-13, OR-16: no withheld kind is hidden -----------------------------------------------------------------------


def test_the_text_and_the_json_name_every_withheld_kind_and_the_page_holds_the_rest_in_a_closed_details(plan):
    opt_in = only(plan.limits, "kinds-opt-in")
    assert len(opt_in.labels) > SHOWN_LABELS
    report = build_report(plan, DATA)
    text = render_text(report)
    document = policy_document(report)
    page = render_page(Page("x", (build_section(route_input(plan), DATA),)))

    assert ", ".join(opt_in.labels) in text  # every one, in order
    assert next(entry for entry in document["limits"] if entry["kind"] == "kinds-opt-in")["labels"] == list(opt_in.labels)
    first = ", ".join(opt_in.labels[:SHOWN_LABELS])
    assert f"{first} and {len(opt_in.labels) - SHOWN_LABELS} more" in page  # the page names the first three ...
    rest = escape(", ".join(opt_in.labels[SHOWN_LABELS:]))
    assert f"<details><summary>the other {len(opt_in.labels) - SHOWN_LABELS}</summary>{rest}</details>" in page  # ... and holds the others, closed
    assert "<details open" not in page and all(escape(label) in page for label in opt_in.labels)
