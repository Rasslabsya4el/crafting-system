"""The one proof sentence (#1576, OR-59): "proved" only over every method; otherwise best found, not proved, with how many of the actions open
to the craft were searched to the end together with the plan; or no plan. Through the planner's entry on a small world, counted in states.

The fixture belt of `test_planner_blocking_crafts` (`test_stop_is_not_unreachable`): the Exalted Orb reaches the goal, the bench's two filler
crafts do not. The rounds are set by hand: round 1 the Exalted Orb, round 2 the fillers; the world offers 5 actions in all. With no net both close: proved.
With 15 states round 1 closes with its plan and round 2 stops: best found, 1 of the 5 actions searched to the end with it. With 3 states no
round makes a plan: no plan. The command's text, its JSON and its page say the same sentence (ADR-0063).
"""

import re

import pytest
from cli_support import price_file, read_json, run
from test_planner_blocking_crafts import S, TARGET, _prices, data, every_shared_kernel_checked  # noqa: F401 (fixtures)
from test_stop_is_not_unreachable import _settings, _target

from crafting_system.budget import NO_PLAN
from crafting_system.planner import PROOF_BEST_FOUND, PROOF_NO_PLAN, PROOF_PROVED, PlanError, _growth, _offers, _rounds, no_plan_words, plan_target, proof_words
from crafting_system.planner import _plan as planner_plan

SEARCH_WORDS = re.compile(r"\brounds?\b|\bbounds?\b|\bkeys?\b|envelope", re.IGNORECASE)


@pytest.fixture
def rounds(monkeypatch):
    monkeypatch.setattr(_growth, "GROWS", False)

    def groups(data, goal, target, grouped, route):
        fills = tuple(i for i, offer in enumerate(grouped) if offer.kind == "bench-craft" and "Fill" in offer.label)
        exalts = tuple(i for i, offer in enumerate(grouped) if offer.kind == "exalted-orb")
        return (_rounds.Group(exalts, ("exalted-orb",), frozenset()), _rounds.Group(fills, ("bench-craft",), frozenset()))

    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    monkeypatch.setattr(planner_plan, "offer_groups", groups)


def test_every_group_finished_is_proved(tmp_path, data, rounds):
    plan = plan_target(data, _target(tmp_path, data), _prices(), _settings(None))
    words = proof_words(plan)
    assert words.case == PROOF_PROVED and words.open == words.tried_together == 5
    assert words.sentence == (
        "Proved: no cheaper plan exists among all 5 crafts this planner can use on this item, every one checked to the end."
        " Methods it cannot use yet are listed below the prices, and one of them could be cheaper."
    )


def test_a_group_stopped_is_best_found_not_proved_with_what_was_tried_and_the_guide(tmp_path, data, rounds):
    plan = plan_target(data, _target(tmp_path, data), _prices(), _settings(15))
    assert [record.status for record in plan.search.widening] == [_rounds.CLOSED, _rounds.STOPPED]
    words = proof_words(plan, guide=500.0)
    assert words.case == PROOF_BEST_FOUND and (words.open, words.tried_together) == (5, 1)
    cost = plan.start_price.chaos + plan.risk.mean.value
    assert words.sentence == (
        "Best plan found, not proved to be the cheapest: the search ran out of time or memory after checking only 1 of the 5 crafts this planner "
        "can use on this item fully checked in combination with this plan (the groups are under \"How the methods were searched\"), so a "
        "cheaper plan that uses the other crafts may exist. "
        f"It costs {cost:,.2f} Chaos in all, against 500.00 Chaos for the guide's route."
    )
    assert "Proved" not in words.sentence and not SEARCH_WORDS.search(words.sentence)
    assert words.document() == {"case": PROOF_BEST_FOUND, "sentence": words.sentence, "actions_open": 5, "actions_tried_together": 1, "guide_cost": 500.0}


def test_no_plan_is_said_as_no_plan(tmp_path, data, rounds):
    with pytest.raises(PlanError) as raised:
        plan_target(data, _target(tmp_path, data), _prices(), _settings(3))
    assert NO_PLAN in str(raised.value)
    words = no_plan_words()
    assert words.case == PROOF_NO_PLAN and words.sentence.startswith("No plan found: ") and "Proved" not in words.sentence


def test_the_text_the_json_and_the_page_say_the_one_sentence(tmp_path):
    # the R12 fixture through the command: one search over its offers, proved (ADR-0063: the three outputs say the same)
    code, out = run(tmp_path, prices=price_file())
    assert code == 0
    document = read_json(out)
    sentence = document["proof"]["sentence"]
    assert document["proof"]["case"] == PROOF_PROVED and sentence.startswith("Proved: no cheaper plan exists")
    page = (out.parent / "r12-lightning-amulet.route.html").read_text(encoding="utf-8")
    assert sentence in page.replace("&#x27;", "'").replace("&#39;", "'")


def test_the_command_prints_the_proof_line_and_the_no_plan_line(tmp_path, capsys):
    code, _ = run(tmp_path, prices=price_file())
    assert code == 0
    printed = capsys.readouterr().out
    (line,) = [line for line in printed.splitlines() if line.startswith("Proof: ")]
    assert line.startswith("Proof: Proved: no cheaper plan exists")


def test_a_round_after_a_stopped_plan_s_round_did_not_hold_its_actions():
    # checker, #1576: a round that stopped with the plan did not join the base of the later rounds (`_rounds.widen`), so a later round that
    # finished searched other actions, not this plan's; only after a closed round of the plan does a later round count
    from types import SimpleNamespace

    from crafting_system.planner._proof_words import _tried_together
    from crafting_system.planner._rounds import RoundRecord

    def tried(second: str) -> int:
        records = (
            RoundRecord(("a",), 2, _rounds.CLOSED, "", 100.0, 100.0, 0.0),
            RoundRecord(("a", "b"), 5, second, "", 80.0 if second == _rounds.CLOSED else 1.0, 80.0, 0.0),
            RoundRecord(("a", "c"), 4, _rounds.BEATEN, "", 80.0, None, 0.0),
        )
        return _tried_together(SimpleNamespace(search=SimpleNamespace(widening=records)), 7)

    assert tried(_rounds.STOPPED) == 0
    assert tried(_rounds.CLOSED) == 5
