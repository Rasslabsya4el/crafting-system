"""The answer carries its limits (ticket #459, OR-13): one `Limit` record in `Plan.limits`, shown in the text, the JSON and the route page.

One test per source of a limit, by the row of the fact base (`docs/research/2026-11-06-rebuild-3-5-inventory.md`, Part B):

* K1 kinds a target must name: `test_k1_*`. K2 kinds the planner cannot use: `test_k2_*`. K3, K6 and G1 Memory Strands:
  `test_g1_*`. K4 kinds the target does not name: `test_k4_*`. K5 a corrupting kind: `test_k5_*` and
  `test_actions_corrupting_toy.py`. K10 Remove Crafted Mods: `test_k10_*`. U1 an unpriced action: `test_u1_*`.
* K7 a craft that counts for nothing: `test_cli_offers.py`, `test_actions_toy.py`. K8 a fixed mod nobody wants:
  `test_offers_wanted_only.py`. K9 a value reroll: `test_cli_offers_divine.py`. K15 the pruning: `test_prune_bound.py`.
* G12 a whole search run past the budget: `test_g12_*`. G13 the packed solver: `test_cli_decide.py`. G14 a tree of groups:
  `test_g14_*`. G19 percentiles not computed: `test_g19_*` and `test_packed_plan_real.py`. G20 a quantile the grid cannot reach: `test_g20_*`.
* P1 a start item counted as free, P3 no restart: `test_p1_*`, `test_p3_*`.

Then what the three surfaces show: the text report, the JSON `crafting-system-policy/2` and the goal card of the route page.
"""

import dataclasses
import re
from types import SimpleNamespace

import pytest
from cli_support import R12, price_file, read_json
from limits_support import labels_of, of_kind, only, sentences
from targets_support import DATA

from crafting_system.cli import Limit, build_report, make_plan, offers_for, policy_document, render_text
from crafting_system.cli import _plan
from crafting_system.cli._limits import GROUPS, SHOWN_LABELS, grouped, kind_title, limit_document, limit_text, risk_limits
from crafting_system.cli._route_html import render_page
from crafting_system.cli._route_view import Page, build_section, route_input
from crafting_system.risk import Estimate
from crafting_system.targets import load_target
from crafting_system.abstraction import Goal, Wanted
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
    limit = Limit("kinds-not-named", "Not offered", "kinds this target does not name", "The plan is the cheapest among the kinds offered.", ("Exalted Orb", "Annulment Orb"))

    assert limit_text(limit) == (
        "Not offered: Exalted Orb, Annulment Orb (kinds this target does not name). The plan is the cheapest among the kinds offered."
    )


def test_k2_the_kinds_the_planner_cannot_use_yet_are_listed_in_every_answer(plan):
    cannot = only(plan.limits, "kinds-not-built")

    assert len(cannot.labels) == sum(not entry.planner for entry in kinds())
    assert {"Alchemy Orb", "Scouring Orb"} <= set(cannot.labels)


def test_g1_k3_k6_the_kinds_that_need_memory_strands_are_one_limit_named_in_player_words(plan):
    strands = only(plan.limits, "strands")

    assert strands.labels == ("Foulborn Augmentation Orb", "Foulborn Regal Orb", "Foulborn Exalted Orb")
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
    assert all(limit.why == f"no price for {', '.join(limit.names)}" for limit in unpriced)
    assert "Harvest Reforge Fire" in labels_of(plan.limits, "unpriced")


def test_g12_a_search_run_whole_past_the_budget_says_so_and_stays_exact():
    solved = only(make_plan(DATA, load_target(R12, DATA), price_file(), budget=1e-9).limits, "how-solved")

    assert solved.what == "The whole search was run" and "no approximate level available" in solved.why
    assert solved.guarantee == "The answer is exact."


def test_g14_a_tree_of_groups_of_item_states_says_it_and_keeps_the_numbers_exact(monkeypatch):
    monkeypatch.setattr(_plan, "VIEW_FROM_STATES", 0)

    shown = only(make_plan(DATA, load_target(R12, DATA), price_file(), solver="packed").limits, "display")

    assert shown.what == "The tree shows groups of item states" and "are one group" in shown.why
    assert shown.guarantee == "The odds, costs and percentiles are exact for the groups."


def test_g19_percentiles_the_memory_cannot_hold_are_a_limit_with_exact_odds_and_mean(monkeypatch):
    monkeypatch.setattr(_plan, "RISK_QUANTILE_TRANSITIONS", 0)

    cut = only(make_plan(DATA, load_target(R12, DATA), price_file(), solver="packed").limits, "risk")

    assert cut.what == "Not computed: p50, p90, CVaR" and cut.guarantee == "The odds, the mean and the variance are exact."


def test_g20_a_quantile_the_grid_cannot_reach_is_a_limit_and_a_reached_one_is_not():
    def estimate(value):
        return Estimate(value, value, value)

    unreached = SimpleNamespace(success_probability=estimate(1.0), p50=estimate(10.0), p90=estimate(float("inf")), cvar=estimate(float("inf")))
    reached = SimpleNamespace(success_probability=estimate(1.0), p50=estimate(10.0), p90=estimate(20.0), cvar=estimate(30.0))
    failing = SimpleNamespace(success_probability=estimate(0.5), p50=estimate(float("inf")), p90=estimate(float("inf")), cvar=estimate(float("inf")))

    (limit,) = risk_limits(unreached)
    assert limit.what == "Not computed: p90, CVaR" and limit.guarantee == "The success chance and the mean cost are exact."
    assert risk_limits(reached) == () and risk_limits(failing) == () and risk_limits(None) == ()


def test_p1_a_start_item_the_target_gives_no_price_is_counted_as_free(tmp_path):
    text = R12.read_text(encoding="utf-8")
    assert "start_price:" in text
    path = tmp_path / "free.yaml"
    path.write_text(re.sub(r"(?m)^start_price:.*\n", "", text), encoding="utf-8")

    free = make_plan(DATA, load_target(path, DATA), price_file())

    (counted,) = [limit for limit in free.limits if limit.what == "The start item is counted as free"]
    assert counted.why == "the target names no start price" and "does not include getting the start item" in counted.guarantee


def test_p3_a_free_start_item_has_no_restart_and_the_plan_says_so():
    free = make_plan(DATA, load_target(R12, DATA), price_file(), start_price=0.0)

    (no_restart,) = [limit for limit in free.limits if limit.what == "No restart"]
    assert "never starts over" in no_restart.guarantee
    assert not [limit for limit in free.limits if limit.what == "The start item is counted as free"]  # P2: the price was given as 0, not left out


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
    limit = Limit("kinds-not-named", "Not offered", "kinds this target does not name", "The plan is the cheapest among the kinds offered.", labels)

    assert SHOWN_LABELS == 3
    assert limit_text(limit).startswith("Not offered, 10 in all: Kind 1, Kind 2, Kind 3 and 7 more (kinds this target does not name).")
    assert limit_document(limit)["labels"] == list(labels) and limit_document(limit)["count"] == 10


def test_the_text_report_the_json_and_the_page_show_the_same_records(plan):
    report = build_report(plan, DATA)
    text = render_text(report)
    document = policy_document(report)
    page = render_page(Page("x", (build_section(route_input(plan), DATA),)))

    assert document["format"] == "crafting-system-policy/2"
    assert not {"note", "dropped_actions", "left_out_actions"} & set(document)
    assert [entry["kind"] for entry in document["limits"]] == [limit.kind for limit in sorted(plan.limits, key=lambda l: [k for k, _ in GROUPS].index(l.kind))]
    for limit in plan.limits:
        sentence = limit_text(limit)
        assert sentence in text
        assert sentence.replace("&", "&amp;").replace("'", "&#x27;") in page.replace("&quot;", '"')
    assert "What this answer leaves out" in text and "What this answer leaves out" in page


def test_the_goal_card_of_the_page_has_the_section_grouped_by_kind(plan):
    card = build_section(route_input(plan), DATA).goal

    titles = [field.label for field in card.leaves_out]
    assert titles == [title for title, _ in grouped(plan.limits)]
    assert "Methods offered only when the target names them" in titles and "Memory Strands" in titles
    assert [line.text for field in card.leaves_out for line in field.lines] == sentences(sorted(plan.limits, key=lambda l: [k for k, _ in GROUPS].index(l.kind)))
    assert "leaves_out" not in [field.label for field in card.fields]


def test_a_plan_with_no_limit_has_no_section_on_the_page(plan):
    bare = dataclasses.replace(plan, limits=())

    page = render_page(Page("x", (build_section(route_input(bare), DATA),)))

    assert "What this answer leaves out" not in page


def test_the_json_limit_is_the_record_with_every_field(plan, tmp_path):
    from cli_support import run

    code, out = run(tmp_path, prices=price_file())

    assert code == 0
    document = read_json(out)
    for entry in document["limits"]:
        assert set(entry) == {"kind", "what", "why", "guarantee", "count", "labels", "names"}
        assert entry["count"] == len(entry["labels"]) and entry["guarantee"]
    assert document["format"] == "crafting-system-policy/2"
