"""The text report's tree is the route page's steps: one block for each player action (ticket #488, OR-18, OR-20).

Before, the tree had one block for each item state the policy reaches (V01: 88 blocks, 79 of them a restart) while the page had one row for each
action. The blocks are now made by the page's own code (`_report_steps` reads `_route_view`), so the two cannot disagree; these tests say they do not:
the same steps in the same order with the same titles, and every branch with the chance `build_flow` gives it, which is the page's chance.
The V01 case, on the real data, is in `test_vendor_benchmark_real.py`.
"""

import dataclasses

import pytest
from report_steps_support import assert_report_is_the_page, blocks_of
from route_view_support import DATA
from test_cli_route_view import INPUTS

from crafting_system.cli import build_report, render_text
from crafting_system.cli._route_view import build_section
from crafting_system.solver import Solution


def report_of(name):
    """The report of a hand-made policy of the page tests (their plans carry no solved values, so each state is given 0)."""
    inp = INPUTS[name]()
    plan = dataclasses.replace(inp.plan, solution=Solution({state: 0.0 for state in inp.plan.policy}, inp.plan.policy, 0.0))
    return plan, build_report(plan, DATA), build_section(inp, DATA)


def test_a_policy_with_a_branch_has_one_block_for_each_action_and_the_page_s_chances():
    plan, report, section = report_of("branch")
    text = render_text(report)

    assert_report_is_the_page(text, section, plan)
    blocks = blocks_of(text)
    assert [title for _, title, _ in blocks] == ["Essence of Hysteria", "Chaos Orb"]  # 2 actions, though the policy holds more states than that
    assert len(report.states) > len(blocks)
    essence, chaos = blocks
    assert [words for _, words in essence[2]] == ["the target", "step 3: Chaos Orb"]  # the branches are grouped by where they lead
    assert [words for _, words in chaos[2]] == ["the target", "nothing gained, this step again"]


def test_the_block_of_several_states_shows_the_mixture_of_their_chances_once():
    plan, report, section = report_of("branch")

    chaos = next(step for step in report.steps if step.title == "Chaos Orb")

    assert chaos.items == 2  # two item states take the action, and the block says so
    assert "2 items take this action; what they all share: rare; " in render_text(report)
    assert sum(outcome.chance for outcome in chaos.outcomes) == pytest.approx(1.0)


def test_a_step_with_no_action_is_a_block_with_its_reason_and_the_branch_to_it_names_it():
    plan, report, section = report_of("dead_end")
    text = render_text(report)

    assert_report_is_the_page(text, section, plan)
    assert [title for _, title, _ in blocks_of(text)] == ["Chaos Orb", "No action"]
    assert "step 3: no action" in text
    assert "  no action here" in text


def test_the_tree_holds_no_state_id_and_no_cut():
    _, report, _ = report_of("branch")
    text = render_text(report)

    assert "S1" not in text and "S2" not in text and "not shown" not in text
