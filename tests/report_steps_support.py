"""The text report's blocks next to the route page's rows and next to `build_flow` (ticket #488, OR-18, OR-20).

`blocks_of(text)` reads the tree of a text report as `(number, title, [(chance text, words), ...])`; `assert_report_is_the_page(...)` says that
the report has one block for each step of the page, with the page's title and the chances of the same flow.
"""

import re

from crafting_system.abstraction import Status
from crafting_system.cli._report import POLICY_HEADING, percent
from crafting_system.cli._route_flow import build_flow
from crafting_system.cli._route_view import chance_text

BLOCK = re.compile(r"^Step (\d+): (.*)$")
OUTCOME = re.compile(r"^ {4,}(\S+)\s{2,}(.*)$")


def blocks_of(text: str) -> list[tuple[int, str, list[tuple[str, str]]]]:
    """The blocks of the tree: from the line after the policy heading to the first empty line."""
    lines = text.splitlines()
    found: list[tuple[int, str, list[tuple[str, str]]]] = []
    for line in lines[lines.index(POLICY_HEADING) + 1 :]:
        if not line.strip():
            break
        if match := BLOCK.match(line):
            found.append((int(match[1]), match[2], []))
        elif (outcome := OUTCOME.match(line)) and found:
            found[-1][2].append((outcome[1], outcome[2]))
    return found


def row_text(row) -> str:
    return " | ".join(line.text for field in row.fields for line in field.lines)


def assert_report_is_the_page(text: str, section, plan, restart: str = "restart", reasons=None) -> None:
    """One block for each step row of the page (row 1 is the start item), the same title, and each branch's chance the page's and `build_flow`'s."""
    blocks = blocks_of(text)
    rows = section.rows[1:]
    assert [(number, title) for number, title, _ in blocks] == [(row.number, row.title) for row in rows]

    def lost(state, landing):  # the leaves a use stops meeting, as the page reads them
        return tuple(i for i, (before, after) in enumerate(zip(state.status, landing.status)) if before is Status.PASSING and after is not Status.PASSING)

    flow = build_flow(plan.start, plan.policy, plan.abstraction.is_goal, reasons, lambda action: action.label == restart, lost)
    assert len(flow.steps) == len(blocks)
    for step, (number, _, outcomes), row in zip(flow.steps, blocks, rows):
        assert step.number + 1 == number
        assert [shown for shown, _ in outcomes] == [percent(edge.chance) for edge in step.edges], f"step {number}"
        if len(outcomes) > 1:  # a single branch is certain, and the page says nothing about it
            assert all(chance_text(edge.chance) in row_text(row) for edge in step.edges), f"step {number}: {row_text(row)}"
