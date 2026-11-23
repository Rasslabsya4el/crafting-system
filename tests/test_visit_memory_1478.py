"""The visit chances of the benchmark's divergences work in the memory of the kernels and stop at the run's memory net in words (ticket #1478).

R06's heavy benchmark of 2026-11-23 made its plan (595.11 c), then the kernel killed it at 16 GB within 25 s of the line "visit chances", and no
benchmark.json was written. The planner's chain had 92,341 states and 25,435 kernels (388,497 edges), but one reroll of 64,969 outcomes was taken
by 66,907 states: the visit chances read the chain's rows (`Chain._rows`), which copy each state's kernel, 4.3 billion edges. They now read the
kernels themselves: a kernel several states take is one shared row of the cycles of the chain (`_route_flow._kernel_rows`,
`_packed_chain.inverse_diagonal`), never copied per state. Measured on R06's two chains: 2.3 s and 420 MB at the peak.

Here the same shape is small: every state takes one reroll. The memory is asserted through the size of what the solve is handed and of what the
chain caches, never through time. Nothing here reads the clock.
"""

import pytest
from targets_support import DATA

import crafting_system.cli._benchmark as benchmark_module
import crafting_system.cli._benchmark_divergence as divergence_module
from crafting_system import budget
from crafting_system.cli import _route_flow
from crafting_system.cli._benchmark_divergence import STOPPED, divergences_of
from crafting_system.cli._report_net import report_net
from crafting_system.cli._route_flow import chain_of_policy, reach_of
from crafting_system.solver import Action, Outcome

from test_cli_benchmark_divergence import tiny  # noqa: F401 (a fixture)
from test_report_net_1381 import HELD_MB, NET_MB, words

STATES = 300
GOAL_WEIGHT = 40  # each use of the reroll lands in each state with weight 1 and in the goal with this weight


def reroll_policy() -> dict:
    """`STATES` states that all take one and the same reroll into every state and the goal: R06's shape, small."""
    reroll = Action("reroll", 1.0, tuple(Outcome(i, 1) for i in range(STATES)) + (Outcome("goal", GOAL_WEIGHT),))
    return {i: reroll for i in range(STATES)}


def test_a_reroll_that_every_state_takes_is_read_once_not_once_per_state(monkeypatch):
    chain = chain_of_policy(0, reroll_policy(), lambda s: s == "goal")
    kernel_edges = int(chain.kernels.kernel_sizes().sum())
    handed = []
    real = _route_flow.inverse_diagonal

    def counted(n, ptr, col, weight, leave, **keywords):
        handed.append(len(col) + sum(len(cols) for cols, _, _ in keywords.get("shared", ())))
        return real(n, ptr, col, weight, leave, **keywords)

    monkeypatch.setattr(_route_flow, "inverse_diagonal", counted)

    reached = reach_of(chain, list(range(chain.m)))

    assert chain.m == STATES and kernel_edges == STATES + 1
    assert handed == [STATES]  # the one row, its edges into the states once (the goal leaks): not STATES x STATES copies
    assert "_edges" not in chain.__dict__  # the chain's per-state copy of its kernels (`Chain._rows`) was never made
    assert reached[0].chance == 1.0
    for found in reached[1:]:  # each use lands in a state with chance 1 / (STATES + 40) and ends with 40 / (STATES + 40)
        assert found.chance == pytest.approx(1 / (1 + GOAL_WEIGHT), rel=1e-9)


def held_past_the_net_inside(monkeypatch, module, name: str) -> None:
    """While `module.name` runs, this process is said to hold `HELD_MB`; before and after it, what it holds."""
    real_mb, real_call = budget.process_mb, getattr(module, name)
    inside = {"on": False}

    def process_mb(pid=None):
        return HELD_MB if inside["on"] and pid is None else real_mb(pid)

    def call(*args, **kwargs):
        inside["on"] = True
        try:
            return real_call(*args, **kwargs)
        finally:
            inside["on"] = False

    monkeypatch.setattr(budget, "process_mb", process_mb)
    monkeypatch.setattr(module, name, call)


def test_visit_chances_past_the_memory_net_count_the_divergences_and_say_the_stop(tiny, monkeypatch):  # noqa: F811
    plan, result = tiny
    held_past_the_net_inside(monkeypatch, _route_flow, "_kernel_rows")

    with report_net(NET_MB):
        block = divergences_of(plan, result, DATA)

    assert block == {"count": len(result.divergences), "shown": [], "more": None, "notes": [f"{STOPPED}: {words()}"]}
    lines = divergence_module.divergence_lines(block)
    assert lines[-1] == f"    note: {STOPPED}: {words()}"


def test_the_guide_s_route_stopped_in_the_visit_chances_keeps_its_cost_and_its_ratio(tiny, monkeypatch):  # noqa: F811
    plan, result = tiny
    solver = plan.risk.mean.value
    free = benchmark_module._given_route(plan, result, DATA, 0.0, solver, 0.5)
    held_past_the_net_inside(monkeypatch, _route_flow, "_kernel_rows")

    with report_net(NET_MB):
        stopped = benchmark_module._given_route(plan, result, DATA, 0.0, solver, 0.5)

    assert free["divergences"]["shown"] and "notes" not in free["divergences"]
    assert {k: v for k, v in stopped.items() if k not in ("divergences", "seconds")} == {k: v for k, v in free.items() if k not in ("divergences", "seconds")}
    assert stopped["divergences"] == {"count": free["divergences"]["count"], "shown": [], "more": None, "notes": [f"{STOPPED}: {words()}"]}
