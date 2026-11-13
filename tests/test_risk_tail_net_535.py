"""The tail rule of the budget DP and the time net of the attempt-wise runs (ticket #535).

Two faults of R14's risk at the 2026-11-10 prices. The hang itself (runs 42946872857, 42957520245) was a forked worker waiting
forever on a stdout lock copied at the fork (`parallel._fresh_streams`, caught by py-spy in 42964753874). Apart from it, rerun
42954014788 showed the attempt runs on a step of 0.3063 never meeting their tail of 1e-13, because `1 - lost - F` carries the
rounding of the running sums and settled just above it while the mass really in flight fell to 1e-137; they ran to their cap
of a million bins. Now the mass in flight is also summed from its parts once the difference is within its rounding of the
tail, and the attempt runs of a step have a time net that stops them (in the worker, or by killing a worker that does not
come back) and says so.
"""

import math
import os
import threading

import numpy as np
import pytest

from crafting_system import budget, parallel
from crafting_system.risk import _budget, _evaluate, _regen
from crafting_system.risk._budget import PLAIN_LIMIT, run_budget
from crafting_system.risk._chain import Chain
from crafting_system.solver import Action

TAIL = 1e-13
CAP = 400_000


def ring(n: int, q: float, seed: int, cycle: int, base: int = 1) -> tuple[Chain, list[int]]:
    """`n` states on a ring with random jumps; each ends in the goal with a chance near `q`, else moves on (costs `base` to `base + cycle - 1` bins)."""
    rng = np.random.default_rng(seed)
    act = Action("a", 1.0, (("x", 1),))
    succ = []
    for i in range(n):
        p_goal = q * (0.5 + rng.random())
        r = rng.random()
        succ.append(((n, p_goal), ((i + 1) % n, (1 - p_goal) * r), (int(rng.integers(n)), (1 - p_goal) * (1 - r))))
    succ.append(())
    chain = Chain(
        tuple(range(n + 1)), (*([False] * n), True), (*([act] * n), None), tuple(succ), (*([True] * n), True), ((),) * (n + 1)
    )
    return chain, [base + (i % cycle) for i in range(n)] + [0]


@pytest.mark.parametrize(
    "q,base",
    [(5e-4, 1), (3e-3, 16)],
    ids=["plain loop", "blocks"],
)
def test_a_long_run_stops_at_its_tail_though_one_minus_the_float_sums_stays_above_it(monkeypatch, q, base):
    chain, bins = ring(20, q, 1, 3, base)
    assert (20 * base <= PLAIN_LIMIT) == (base == 1)  # one case per loop

    run = run_budget(chain, bins, target=None, tail_mass=TAIL, max_bins=CAP)

    assert len(run.cdf) < CAP // 2
    assert run.unresolved <= TAIL

    monkeypatch.setattr(_budget, "_within_rounding", lambda *args: False)  # the rule before #535: the subtraction alone
    cap = 2 * len(run.cdf)
    before = run_budget(chain, bins, target=None, tail_mass=TAIL, max_bins=cap)
    assert len(before.cdf) == cap + 1 and before.unresolved < 1e-20  # it ran on to the cap with next to nothing in flight


@pytest.mark.parametrize("base", [1, 16], ids=["plain loop", "blocks"])
def test_a_passed_deadline_stops_the_run_with_its_mass_in_flight_unresolved(base):
    chain, bins = ring(20, 3e-3, 1, 3, base)

    run = run_budget(chain, bins, target=None, tail_mass=TAIL, max_bins=CAP, deadline=-math.inf)  # a deadline long past

    assert len(run.cdf) < 1000
    assert run.unresolved == pytest.approx(1.0 - run.cdf[-1], abs=1e-12) and run.unresolved > 0.5


def test_the_attempt_runs_stopped_by_the_time_net_say_so_and_leave_no_finer_step(monkeypatch):
    from test_risk_regen import narrow

    assert math.isfinite(narrow(regenerative=True).p90.high)
    monkeypatch.setattr(_evaluate, "REGEN_SECONDS", 0.0)
    tried = []
    original = _regen.regenerative_runs
    monkeypatch.setattr(_regen, "regenerative_runs", lambda *a, **k: tried.append(k["step"]) or original(*a, **k))

    stopped = narrow(regenerative=True)

    assert len(tried) == 1  # the time net stopped the first step and no finer one was tried
    (said,) = [line for line in stopped.grid.gave_up if "time limit" in line]
    assert said == _regen.time_net_words(0.0, coarser=False)  # no coarser step was kept: it says the slower method follows
    assert math.isinf(stopped.p90.high)  # no coarser step was kept: the ordinary grid ran instead and could not reach it


def test_the_ladder_reads_no_clock_and_runs_every_step_until_one_is_narrow_enough(monkeypatch):
    from test_risk_regen import narrow

    monkeypatch.setattr(_evaluate, "REGEN_WIDTH", 0.0)  # no step is ever narrow enough: the whole ladder runs
    tried = []
    original = _regen.regenerative_runs
    monkeypatch.setattr(_regen, "regenerative_runs", lambda *a, **k: tried.append(k["step"]) or original(*a, **k))

    narrow(regenerative=True)

    assert len(tried) == 1 + len(_evaluate.REGEN_PARTS)  # #535: no step is skipped for a guess of how long the next would take
    assert not hasattr(_evaluate, "time")  # the steps that run cannot depend on the machine's speed


def test_every_attempt_run_of_the_ladder_shares_one_deadline(monkeypatch):
    """#745: one net for the whole ladder. Run one after another (no workers), every run of every step stops at the same deadline, `REGEN_SECONDS`
    after the ladder began; before, each run had the whole net from its own start (five steps of four runs: twenty nets, about 10 hours)."""
    from test_risk_regen import narrow

    monkeypatch.setenv("CRAFTING_WORKERS", "1")
    monkeypatch.setattr(_evaluate, "REGEN_WIDTH", 0.0)  # no step is narrow enough: every step runs, so several deadlines would show
    given = []
    original = _regen.attempt_pmf
    monkeypatch.setattr(_regen, "attempt_pmf", lambda *a, **k: given.append(dict(k)) or original(*a, **k))

    serial = narrow(regenerative=True)

    deadlines = {k["deadline"] for k in given}
    assert len(given) > 4 and len(deadlines) == 1 and "seconds" not in given[0]
    assert not [line for line in serial.grid.gave_up if "time limit" in line]


class FakeTime:
    """A clock that only moves when the test says so (it stands in for the `time` module of `_regen` and of `budget`)."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def monotonic(self) -> float:
        return self.now

    perf_counter = monotonic


def test_the_ladders_net_is_its_own_or_what_the_runs_budget_has_left_when_less(monkeypatch):
    fake = FakeTime()
    monkeypatch.setattr(_regen, "time", fake)
    monkeypatch.setattr(budget, "time", fake)

    assert _regen.ladder_net(1800.0) == _regen.LadderNet(2800.0, 1800.0, False)  # no run budget: the ladder's own net

    clock = budget.Budget(seconds=600.0, memory_mb=None).start()
    fake.now = 1570.0  # the run has spent 570 of its 600 seconds
    with budget.running(clock), budget.stage("the cost figures", "kept"):
        net = _regen.ladder_net(1800.0)
        assert net == _regen.LadderNet(1600.0, 30.0, True)
        fake.now = 1601.0
        said = _regen.ladder_stopped(net, coarser=True)
    assert said == _regen.run_spent_words(coarser=True) and "the run's time limit" in said  # the run's net bound, not the ladder's
    (bound,) = clock.bindings  # the run's net bound: the one list of the run says so (#378)
    assert (bound.stage, bound.limit, bound.given, bound.reached) == ("the cost figures", budget.TIME, 600.0, 601.0)
    assert bound.what == "the figures of the coarser step already worked out are kept"


def test_the_ladders_own_net_binding_is_said_but_not_listed_as_the_runs(monkeypatch):
    fake = FakeTime()
    monkeypatch.setattr(_regen, "time", fake)
    monkeypatch.setattr(budget, "time", fake)
    clock = budget.Budget(seconds=None, memory_mb=None).start()
    with budget.running(clock):
        said = _regen.ladder_stopped(_regen.ladder_net(1800.0), coarser=False)
    assert said == _regen.time_net_words(1800.0, coarser=False) and "30 minutes" in said
    assert clock.bindings == []


class RecordingPool:
    """A stand-in for `parallel.WorkerPool` that runs the jobs here and keeps the timeout it was given."""

    timeouts: list = []

    def __init__(self, factory, args, *, workers):
        self.context, self.workers = factory(*args), workers

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def map(self, function, pieces, *, chunk=None, timeout=None):
        RecordingPool.timeouts.append((self.workers, timeout))
        saved, parallel._context = parallel._context, self.context
        try:
            return [function(piece) for piece in pieces]
        finally:
            parallel._context = saved


def test_the_pool_waits_until_the_ladders_deadline_and_the_margin(monkeypatch):
    monkeypatch.setenv("CRAFTING_WORKERS", "2")
    monkeypatch.setattr(parallel, "can_inherit", lambda: True)
    monkeypatch.setattr(parallel, "WorkerPool", RecordingPool)
    RecordingPool.timeouts.clear()

    monkeypatch.setattr(_regen, "time", FakeTime(1000.0))

    assert _regen.run_jobs([(abs, (-k,), {}) for k in range(4)], deadline=1100.0) == [0, 1, 2, 3]

    assert RecordingPool.timeouts == [(2, 100.0 + _regen.ABANDON_MARGIN)]  # four runs on two workers: still one deadline, then the margin


PARENT = os.getpid()


def dies_in_a_worker(value: int) -> int:
    if os.getpid() != PARENT:
        os._exit(3)
    return value


@pytest.mark.skipif(not parallel.can_inherit(), reason="the attempt runs go side by side only where workers are forked")
def test_attempt_jobs_whose_worker_dies_are_run_here_instead(monkeypatch):
    monkeypatch.setenv("CRAFTING_WORKERS", "2")

    assert _regen.run_jobs([(dies_in_a_worker, (1,), {}), (dies_in_a_worker, (2,), {})]) == [1, 2]


def never_ends(*args, **options):
    """A job stuck where no deadline is checked (a lock, a call that does not return): it waits for an event nobody sets."""
    threading.Event().wait()


@pytest.mark.skipif(not parallel.can_inherit(), reason="the attempt runs go side by side only where workers are forked")
def test_workers_that_never_come_back_are_killed_and_the_step_is_refused_and_said(monkeypatch):
    monkeypatch.setenv("CRAFTING_WORKERS", "2")
    monkeypatch.setattr(_regen, "ABANDON_MARGIN", 0.0)
    with pytest.raises(_regen.TimedOut):
        _regen.run_jobs([(never_ends, (), {}), (never_ends, (), {})], deadline=-math.inf)  # a deadline long past: the wait is the margin alone

    from test_risk_regen import narrow

    monkeypatch.setattr(_evaluate, "REGEN_SECONDS", 0.0)
    monkeypatch.setattr(_regen, "ABANDON_MARGIN", 0.0)
    monkeypatch.setattr(_regen, "attempt_pmf", never_ends)

    stopped = narrow(regenerative=True)

    (said,) = [line for line in stopped.grid.gave_up if "time limit" in line]
    assert said == _regen.time_net_words(0.0, coarser=False) and said.endswith("so it worked out none of them; the slower method follows")
    assert math.isinf(stopped.p90.high)  # the step was refused, no finer one tried; the ordinary grid could not reach the level
