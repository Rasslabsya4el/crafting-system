"""The one proof sentence (#1576, OR-58): "proved" only over every method; otherwise best found, not proved, with how many of the actions open
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
    assert words.sentence == "Proved: no cheaper way exists. The search held all 5 actions open to this craft together and finished."


def test_a_group_stopped_is_best_found_not_proved_with_what_was_tried_and_the_guide(tmp_path, data, rounds):
    plan = plan_target(data, _target(tmp_path, data), _prices(), _settings(15))
    assert [record.status for record in plan.search.widening] == [_rounds.CLOSED, _rounds.STOPPED]
    words = proof_words(plan, guide=500.0)
    assert words.case == PROOF_BEST_FOUND and (words.open, words.tried_together) == (5, 1)
    cost = plan.start_price.chaos + plan.risk.mean.value
    assert words.sentence == (
        "Best plan found, not proved the cheapest: 1 of the 5 actions open to this craft were searched to the end together with this plan before "
        f"the search ran out of time or memory, so a cheaper plan that uses the others may exist. It costs {cost:,.2f} Chaos in all, against "
        "500.00 Chaos for the guide's route."
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
    assert document["proof"]["case"] == PROOF_PROVED and sentence.startswith("Proved: no cheaper way exists")
    page = (out.parent / "r12-lightning-amulet.route.html").read_text(encoding="utf-8")
    assert sentence in page.replace("&#x27;", "'").replace("&#39;", "'")


def test_the_command_prints_the_proof_line_and_the_no_plan_line(tmp_path, capsys):
    code, _ = run(tmp_path, prices=price_file())
    assert code == 0
    printed = capsys.readouterr().out
    (line,) = [line for line in printed.splitlines() if line.startswith("Proof: ")]
    assert line.startswith("Proof: Proved: no cheaper way exists")
