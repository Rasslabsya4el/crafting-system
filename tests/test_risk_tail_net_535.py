"""The tail rule of the budget DP and the time net of the attempt-wise runs (ticket #535).

R14 at the 2026-11-10 prices hung in `packed_risk` (heavy run 42946872857, 1 h 50 min on a step of 0.6125 Chaos); its rerun
42954014788 showed why: the attempt runs on a step of 0.3063 never met their tail of 1e-13, because `1 - lost - F` carries the
rounding of the running sums and settled just above it while the mass really in flight fell to 1e-137; they ran to their cap
of a million bins, four workers filling the 16 GB runner, and the pool waited on them. Now the
mass in flight is also summed from its parts once the difference is within its rounding of the tail, and the attempt runs of a
step stop at a time limit and say so.
"""

import math
import os

import numpy as np
import pytest

from crafting_system import parallel
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
    (said,) = [line for line in stopped.grid.gave_up if line.startswith("the attempt runs on a step of ")]
    assert "were stopped at the time limit of 0 s" in said and said.endswith("this step's percentiles are not used (a coarser one's brackets stand)")
    assert math.isinf(stopped.p90.high)  # no coarser step was kept: the ordinary grid ran instead and could not reach it


class SlowClock:
    """A stand-in for `_evaluate`'s clock on which every step seems to take 250 s (a slow runner), below the 600 s net."""

    def __init__(self):
        self.now = 0.0

    def perf_counter(self):
        self.now += 250.0
        return self.now


def test_a_slow_machine_runs_the_same_steps_as_a_fast_one(monkeypatch):
    from test_risk_regen import narrow

    monkeypatch.setattr(_evaluate, "REGEN_WIDTH", 0.0)  # no step is ever narrow enough: the whole ladder runs
    tried = []
    original = _regen.regenerative_runs
    monkeypatch.setattr(_regen, "regenerative_runs", lambda *a, **k: tried.append(k["step"]) or original(*a, **k))
    fast = narrow(regenerative=True)
    every = list(tried)
    tried.clear()
    monkeypatch.setattr(_evaluate, "time", SlowClock())

    slow = narrow(regenerative=True)

    assert tried == every and len(every) == 1 + len(_evaluate.REGEN_PARTS)  # #535: not cut after 250 s for a guess that the next takes 750
    assert slow == fast


PARENT = os.getpid()


def dies_in_a_worker(value: int) -> int:
    if os.getpid() != PARENT:
        os._exit(3)
    return value


@pytest.mark.skipif(not parallel.can_inherit(), reason="the attempt runs go side by side only where workers are forked")
def test_attempt_jobs_whose_worker_dies_are_run_here_instead(monkeypatch):
    monkeypatch.setenv("CRAFTING_WORKERS", "2")

    assert _regen.run_jobs([(dies_in_a_worker, (1,), {}), (dies_in_a_worker, (2,), {})]) == [1, 2]
