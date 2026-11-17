"""What a test compares when it runs the planner twice and checks that the two answers are the same (#1136).

The suite's rule, made once here: **two runs compared are counted in states** (`Budget.in_states`: a states net and no time net), never
masked. Since #886 a target is searched in rounds, and the answer's "rounds" limit names each round's spent work: its states when the run
is counted in states, else its seconds (`planner/_rounds.py`, `_round_line`: "... actions offered, 1 s)"). Seconds are measured, so two
runs round them apart (0 s against 1 s) whenever one round crosses a half second in one run and not in the other: the comparison flakes
(integration run 44048692232; PR #1124's CI). Masking those seconds would hide a round's spent work from the comparison; counting in
states keeps it, and the same plan then gives the same text on every machine.

So a test that compares two runs (the text, the JSON policy or `Plan.limits`) of a plan searched in rounds gives both runs a budget
counted in states: `make_plan(..., budget=Budget.in_states(n))`, `PlanSettings(budget=...)`, or, through the command, `in_states(monkeypatch)`
below. It compares their text through `masked` and their JSON through `without_timings`. These drop what is measured whatever the budget
(the `Run time:` line, the `timings_seconds` object) and fail loudly (the guard) when the answer still names a round's seconds: a
comparison left on the clock fails on every run instead of one run in a hundred. A plan searched in one round (the classic offers of the
real-data modules) names no round and needs no states net; the guard says so the day it gains rounds. The golden helpers
(`route_view_support.assert_golden`, `targets_sockets_support.assert_golden_json`) run the same guard: a golden is a second run too.
"""

from __future__ import annotations

import json
import re

from crafting_system.budget import Budget

STATES = 100_000  # never binds on the fixture targets and the toys: their rounds close in a few hundred states at most
MEASURED_ROUND = re.compile(r"actions offered, [\d,]+ s\)")  # `_rounds._round_line` on a run not counted in states
RUN_TIME = re.compile(r"^Run time:.*$", flags=re.MULTILINE)  # the text report's one line of measured times


def assert_counted_in_states(text: str, what: str = "the answer") -> None:
    """The guard: `text` (a report, or a JSON document dumped) names no round's measured seconds."""
    __tracebackhide__ = True
    found = MEASURED_ROUND.search(text)
    assert found is None, (
        f"{what} names a round's measured seconds ({found.group(0)!r}): two runs of one plan round them apart, so a comparison of answers "
        "or a golden must be counted in states (`Budget.in_states`; tests/two_runs_support.py)"
    )


def masked(text: str) -> str:
    """A text report without its `Run time:` line, checked to name no round's seconds."""
    __tracebackhide__ = True
    assert_counted_in_states(text, "the text report")
    return RUN_TIME.sub("Run time: <measured>", text)


def without_timings(document: dict) -> dict:
    """A JSON policy document without its `timings_seconds`, checked to name no round's seconds; a plain copy (read back from JSON)."""
    __tracebackhide__ = True
    dumped = json.dumps({key: value for key, value in document.items() if key != "timings_seconds"})
    assert_counted_in_states(dumped, "the JSON policy")
    return json.loads(dumped)


def in_states(monkeypatch, states: int = STATES) -> Budget:
    """Make the command (`cli._main.run_budget`) count its run in states; returns that budget for the run the test compares it with."""
    from crafting_system.cli import _main

    budget = Budget.in_states(states)
    monkeypatch.setattr(_main, "run_budget", lambda *args, **kwargs: budget)
    return budget
