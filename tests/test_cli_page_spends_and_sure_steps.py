"""The route page's price list and notes name every currency a step pays with, and a sure action reads as one sure use (#983, #984).

Small hand-made policies on a belt, drawn through the page's entry (`build_section`), as `test_cli_route_view.py` does:
- #983: a bench craft paid in Divine Orbs and a Chaos Orb step put both currencies in "Prices", with a source; a kind of the catalog named by
  a currency the plan pays with is named by its use in "What this answer leaves out", so no note calls a spent currency not offered (OR-7).
- #984: a bench craft never misses, so its row has no "Chance per use"; where its items go on differs only by the item it was used on, and its
  uses read as one each time; an edge that crafts the mod a requirement asks for names it once (OR-18, OR-20).
"""

import dataclasses
import json

from items_support import DATA, roll
from route_view_support import COLD_REQ, DAMAGE, FRACTURED_COLD, LIFE, belt, hand_input

from crafting_system.cli._route_view import SURE_NEXT, build_section
from crafting_system.planner import Limit, claim, spent_kinds_named
from crafting_system.planner._limits import NOT_NAMED, USED_ON_THE_ITEM
from crafting_system.targets import Requirement

DAMAGE_REQ = Requirement("AllDamage", None, frozenset({DAMAGE}))
START = belt(FRACTURED_COLD, roll("LifeRegeneration1"))


def _junk(state) -> int:
    return sum(1 for slot in state.slots if not slot.crafted)


def bench_then_by_the_item(state, ab):
    """The bench craft on an item with a free prefix; after it, the essence on the item that holds one other mod and a Chaos Orb on any other.

    So the one bench step leads to two steps, by the item it was used on, and a run comes back to it after a reroll that misses."""
    if state.crafted:
        return "Essence of Hysteria" if _junk(state) == 1 else "Chaos Orb"
    prefixes = sum(1 for slot in state.slots if slot.side.value == "prefix")
    return "Benchcraft: All Damage" if prefixes < 3 else "Chaos Orb"


def lines(row, label: str) -> list[str]:
    return [line.text for field in row.fields if field.label == label for line in field.lines]


def card_lines(goal, label: str) -> list[str]:
    return [line.text for field in goal.fields if field.label == label for line in field.lines]


def bench_row(section):
    (row,) = [row for row in section.rows if row.title.startswith("Benchcraft")]
    return row


def test_a_sure_bench_craft_has_no_chance_per_use_and_its_branches_are_shares_of_its_uses_by_the_item():
    section = build_section(hand_input(START, (COLD_REQ, LIFE), bench_then_by_the_item), DATA)
    row = bench_row(section)

    assert lines(row, "Chance per use") == []  # a bench craft never misses (#984)
    branches = lines(row, SURE_NEXT)
    assert len(branches) == 2
    assert all(line.endswith("% of uses") for line in branches)
    assert {line.split(", then ")[-1].split(":")[0] for line in branches} == {"Chaos Orb", "Essence of Hysteria"}


def test_a_sure_bench_craft_reads_one_use_each_time_the_run_is_there():
    section = build_section(hand_input(START, (COLD_REQ, LIFE), bench_then_by_the_item), DATA)
    (uses,) = lines(bench_row(section), "Uses on average")

    assert uses.startswith("1 each time, ")  # a run comes back to it after each reroll: one sure use each time, never "≈ 1.4 uses"
    assert uses.endswith("times in a run that reaches it")


def test_a_bench_craft_used_once_a_run_reads_1():
    section = build_section(hand_input(START, (COLD_REQ, DAMAGE_REQ), lambda state, ab: "Benchcraft: All Damage"), DATA)

    assert lines(bench_row(section), "Uses on average") == ["1"]
    assert lines(bench_row(section), SURE_NEXT) == []


def test_a_random_action_keeps_its_chance_per_use():
    section = build_section(hand_input(START, (COLD_REQ, LIFE), bench_then_by_the_item), DATA)
    (chaos,) = [row for row in section.rows if row.title == "Chaos Orb"]

    assert lines(chaos, "Chance per use")
    assert lines(chaos, SURE_NEXT) == []
    assert not lines(chaos, "Uses on average")[0].startswith("1 each time")


def test_the_price_list_holds_every_currency_a_step_pays_with_a_bench_crafts_included():
    section = build_section(hand_input(START, (COLD_REQ, LIFE), bench_then_by_the_item), DATA)
    prices = card_lines(section.goal, "Prices")

    assert any(line.startswith("Divine Orb: 300 Chaos, poe.ninja exchange, Test, 2026-10-30") for line in prices)  # the bench craft's (#983)
    assert "Chaos Orb: 1 Chaos, the unit every price is in" in prices
    assert not any("approximate" in line for line in prices if line.startswith(("Divine Orb", "Chaos Orb")))


def test_a_kind_named_by_a_currency_the_plan_spends_is_named_by_its_use_in_what_the_answer_leaves_out():
    inp = hand_input(START, (COLD_REQ, LIFE), bench_then_by_the_item)
    left_out = Limit(NOT_NAMED, "Not offered", "kinds the run's methods setting does not name", labels=("Divine Orb", "Scouring Orb", "Fracturing Orb"), **claim("the kinds offered"))
    plan = dataclasses.replace(inp.plan, limits=(*inp.plan.limits, left_out))
    section = build_section(dataclasses.replace(inp, plan=plan), DATA)
    text = " ".join(line.text for field in section.goal.leaves_out for line in field.lines)

    assert f"Divine Orb{USED_ON_THE_ITEM}" in text  # the bench craft pays with Divine Orbs: the kind left out is the orb used on the item
    assert "Fracturing Orb," in text or text.endswith("Fracturing Orb") or "Fracturing Orb " in text  # not spent: named as it was
    assert f"Fracturing Orb{USED_ON_THE_ITEM}" not in text
    assert f"Scouring Orb{USED_ON_THE_ITEM}" not in text  # this plan buys no Orb of Scouring


def test_the_json_policy_names_a_spent_kind_as_the_page_does():
    from crafting_system.cli._report import build_report, policy_document

    inp = hand_input(START, (COLD_REQ, LIFE), bench_then_by_the_item)
    left_out = Limit(NOT_NAMED, "Not offered", "kinds the run's methods setting does not name", labels=("Divine Orb", "Fracturing Orb"), **claim("the kinds offered"))
    policy = inp.plan.solution.policy
    values = {state: 0.0 for action in policy.values() for state, _ in action.outcomes} | dict.fromkeys(policy, 0.0)  # no solve: a hand-made policy
    solution = dataclasses.replace(inp.plan.solution, values=values)
    plan = dataclasses.replace(inp.plan, limits=(*inp.plan.limits, left_out), solution=solution)
    text = json.dumps(policy_document(build_report(plan, DATA))["limits"])

    assert f"Divine Orb{USED_ON_THE_ITEM}" in text  # the JSON never calls a spent currency not offered either (#983)
    assert f"Fracturing Orb{USED_ON_THE_ITEM}" not in text


def test_two_lost_leaves_that_read_alike_are_one_mod():
    from types import SimpleNamespace

    from crafting_system.cli._route_view import _View

    view = SimpleNamespace(leaf_text={0: "+80 to maximum Life", 1: "+80 to maximum Life", 2: "+40% to Cold Resistance"}.get)

    assert _View.lost(view, SimpleNamespace(lost=(0, 1))) == ["+80 to maximum Life lost"]
    assert _View.lost(view, SimpleNamespace(lost=(0, 1, 2))) == ["one of these lost: +80 to maximum Life; +40% to Cold Resistance"]


def test_the_two_spellings_of_an_orb_are_one_currency():
    left_out = Limit(NOT_NAMED, "Not offered", "kinds the run's methods setting does not name", labels=("Scouring Orb", "Chaos Orb", "Regal Orb"), **claim("the kinds offered"))

    (named,) = spent_kinds_named((left_out,), ("Orb of Scouring", "Chaos Orb"))

    assert named.labels == (f"Scouring Orb{USED_ON_THE_ITEM}", f"Chaos Orb{USED_ON_THE_ITEM}", "Regal Orb")
    assert spent_kinds_named((left_out,), ()) == (left_out,)


def test_an_edge_that_crafts_the_wanted_mod_names_it_once():
    """The bench craft meets the requirement it adds on its way to two steps: each branch names the crafted mod once, not also the
    requirement it meets in the same words (#984, as `gains` names the goal)."""
    section = build_section(hand_input(START, (COLD_REQ, DAMAGE_REQ, LIFE), bench_then_by_the_item), DATA)
    row = bench_row(section)
    branches = [line for line in lines(row, SURE_NEXT) if ", then " in line]  # the third is the target

    assert len(branches) == 2
    for line in branches:
        named = line.split(", then ")[0]
        assert named.count(DATA.mods[DAMAGE].text) == 1, line
        assert " and " not in named, line


def test_the_uses_of_a_sure_step_never_read_as_a_fraction_of_a_use():
    from crafting_system.cli._route_view import _View

    assert _View.uses_text(0.3, None, True) == "1 each time"  # no reach solved: one sure use each time, the times not known
    assert _View.uses_text(5.0, None, True) == "1 each time"  # never "1" for a step a run may be at five times
    assert _View.uses_text(0.92, 0.92, True) == "1"  # once in each run that reaches it ("reached in 92% of runs" follows)
    assert _View.uses_text(1.0004, 1.0, True) == "1"  # never "≈1 times"
    assert _View.uses_text(2.4, 0.8, True) == "1 each time, 3 times in a run that reaches it"
    assert _View.uses_text(2.4, 0.8, False) == "2.4"
