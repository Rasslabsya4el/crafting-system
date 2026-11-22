"""A finished round holds its plan and its figures, not the memos its search filled (#1076, OR-39, OR-40), on the hand-worked belt of
`test_planner_blocking_crafts.py` (its module text has the figures: 16e/3 + 2S = 153.33 with the Exalted Orb alone, 3(c + e) + 2S = 133
with the filler crafted first).

R12 under a 6-hour net and a 12 GB memory net (main 3a3c0387, 2026-11-20): the round of five offers had a share of about 800 s, and the fourth
round of its search walked 20,858 tips alone for six minutes. The kernels it made filled its abstraction's label distributions (`_cache`,
`_expanded`: 4,078 distributions of 11.7 million outcomes, 12.4 GB). Its plan was the cheapest so far, the plan keeps its abstraction to read
its policy's actions (`Plan.abstraction`, `PackedPolicy`), and so those 12.4 GB stayed through every later round: each stopped at once on the
memory net, the Harvest round never ran, and the answer was 232.72 c where the short run (600 s) gives the guide's 40.93 c. The memos are
made again on demand (each is a function of its key), so a finished round's plan lets them go (`Abstraction.release_memos`, `_rounds.widen`'s
`release`). Here the memory is a figure the test controls: 100 MB, plus 1,000 MB for each label distribution a finished round's plan still
keeps while a later round runs. Nothing reads the clock: the run is counted in states (`Budget.in_states`)."""

import dataclasses
import weakref

import pytest
from test_planner_blocking_crafts import C, E, S, _fills, _prices, data, target  # noqa: F401 (the fixtures)

from crafting_system import budget, parallel
from crafting_system.budget import Budget
from crafting_system.planner import PlanSettings, _envelope, _offers, _rounds, plan_target
from crafting_system.planner import _plan as planner_plan
from crafting_system.planner._offers import RESTART

NET_MB = 500.0


def _kept(abstraction) -> int:
    """The label distributions an abstraction keeps, exact and in floats (read off its memos, not through the method under test)."""
    return len(abstraction._cache) + len(abstraction._approx[0])


@pytest.fixture
def rounds(monkeypatch):
    """The belt in two rounds (the Exalted Orb, then the fillers), as `test_a_later_round_that_finds_a_cheaper_plan_replaces_the_plan_in_hand`,
    with the memory read as the test's figure. Returns what each round's search saw held by the plans of the rounds before it."""
    real_groups, real_make, real_widen = _rounds.round_groups, planner_plan._make_plan, _rounds.widen

    def named_alone(offers, named, added, seed=()):
        head, *rest = real_groups(offers, named, added, seed)
        asked = tuple(i for i in head.positions if offers[i].blocks is None)
        fillers = tuple(i for i in head.positions if i not in asked)
        return (_rounds.Group(asked, (), frozenset()), _rounds.Group(fillers, ("bench-craft",), head.features), *rest)

    finished: list[weakref.ref] = []  # the abstractions of the plans the rounds made, while the rounds run
    seen: list[int] = []

    def held() -> float:
        return 100.0 + 1_000.0 * sum(_kept(ab) for ref in finished if (ab := ref()) is not None)

    def make(*args, **kwargs):
        if kwargs.get("round_call") is not None:
            seen.append(sum(_kept(ab) for ref in finished if (ab := ref()) is not None))
        plan = real_make(*args, **kwargs)
        if kwargs.get("round_call") is not None:
            finished.append(weakref.ref(plan.abstraction))
        return plan

    def widen(*args, **kwargs):
        try:
            return real_widen(*args, **kwargs)
        finally:
            finished.clear()  # the answer's own steps after the rounds (the Lock, the risk) make the kernels they read again: not this test's

    monkeypatch.setattr(_rounds, "round_groups", named_alone)
    monkeypatch.setattr(_rounds, "widen", widen)
    monkeypatch.setattr(planner_plan, "_make_plan", make)
    monkeypatch.setattr(parallel, "held_mb", lambda under=None, paced=True: held())
    monkeypatch.setattr(budget, "process_mb", lambda pid=None: held())
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    return seen


def _belt(data, target, states=10_000):  # noqa: F811
    given = dataclasses.replace(Budget.in_states(states), memory_mb=NET_MB)
    return plan_target(data, target, dataclasses.replace(_prices(), chaos_per_divine=92.0), PlanSettings(recipe_starts=False, start_price=S, solver="envelope", budget=given))


def test_a_later_round_runs_after_an_earlier_rounds_memos_and_finds_the_cheaper_plan(data, target, rounds):  # noqa: F811
    # Round 1 (the Exalted Orb) closes at 16e/3 + 2S = 153.33, and its search kept label distributions: held by its plan, each would read as
    # 1,000 MB, past the 500 MB net, and round 2 would stop at once in its build. It lets them go as it ends, so round 2 begins at 100 MB,
    # closes on the filler's plan, 3(c + e) + 2S = 133, and the answer reads that plan's actions (its kernels made again).
    plan = _belt(data, target)
    first, second = plan.search.widening[:2]
    assert (first.status, first.upper) == ("closed", pytest.approx(16 * E / 3 + 2 * S, rel=1e-9))
    assert second.status == "closed", second.reason
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    assert _fills(plan.solution.policy[plan.start].label)
    assert rounds[:2] == [0, 0]  # what the plans of the finished rounds kept when each round began: nothing


def test_what_a_finished_round_holds_is_its_plan_not_its_memos(data, target, rounds, monkeypatch):  # noqa: F811
    # Each round's plan, at the moment the rounds hand it back (`release`), kept some distributions (its search made kernels); after it, none.
    # Without the release, round 1's plan holds them through round 2, which then stops on the memory net with round 1's plan as the answer.
    kept = []
    real = planner_plan.release_round

    def release(plan):
        before = _kept(plan.abstraction)
        real(plan)
        kept.append((before, _kept(plan.abstraction)))

    monkeypatch.setattr(planner_plan, "release_round", release)
    _belt(data, target)
    assert len(kept) >= 2 and all(before > 0 and after == 0 for before, after in kept)

    kept.clear()
    rounds.clear()
    monkeypatch.setattr(planner_plan, "release_round", lambda plan: None)  # the rounds before #1076
    plan = _belt(data, target)
    second = plan.search.widening[1]
    assert rounds[1] > 0 and second.status == "undone" and "the limit is 500 MB" in second.reason  # its build stopped: undone (#1276)
    assert plan.mean_remaining == pytest.approx(16 * E / 3 + 2 * S, rel=1e-9)


def test_a_rounds_walk_that_a_net_ends_says_so():
    # A search round's walk of its tips that a net ends was silent (R12: six minutes with no line, then the plan): it says where it stopped,
    # what the process held, and why. A generated graph of 400 states (`envelope_support`), counted in 150 states (asked at every state).
    from envelope_support import ExplicitProblem, dense_optimum, random_graph

    graph = random_graph(1, 400)
    value, _ = dense_optimum(graph)
    said = []
    result = _envelope.Search(ExplicitProblem(graph, value, 0.3), net=_envelope.Net(states=150, pieces=10_000), progress=said.append, workers=1).run()
    (walk,) = [line for line in said if "its walk stopped after" in line]
    assert result.stopped.startswith("150 states were known, the limit is 150") and walk.endswith(f": {result.stopped}")
    assert f"round {result.stats.rounds + 1}: its walk stopped after " in walk and ("MB held" in walk or "memory not read" in walk)


def test_release_memos_drops_the_distributions_and_the_kernels_made_again_are_the_same(data, target):  # noqa: F811
    # The memos are a function of their key: a kernel asked after `release_memos` is the kernel asked before, and the memos are empty after it.
    plan = plan_target(data, target, _prices(), PlanSettings(recipe_starts=False, start_price=S, solver="envelope"))
    ab = plan.abstraction
    policy = plan.solution.policy
    before = {state: policy.offer(state) for state in policy if policy.offer(state).label != RESTART}
    states = list(before)[:5]
    assert states
    kernels = {state: ab.kernel(state, before[state].offer.action) for state in states}
    assert _kept(ab) > 0
    assert ab.release_memos() > 0 and _kept(ab) == 0 and ab.memo_count() == 0
    assert {state: ab.kernel(state, before[state].offer.action) for state in states} == kernels
    assert _envelope.SAY_SECONDS > 0  # the walk's line on the clock is a pace of the log, never a limit (OR-40)
