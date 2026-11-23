"""The memory question of a net reads the cheap resident sum first and the dear proportional sum at its own pace (ticket #1252).

`parallel.held_mb` read `smaps_rollup` under `/proc` (the proportional size, PSS) of the process and of each live worker at every question, about
8 ms per GB the process maps: under the 0.25 s gate of a making (`budget.ASK_SECONDS`) a process near a 12 GB net spent about a third of its time
reading its own memory. A net's question now passes its limit (`under`): the resident sum (`status` under `/proc`, microseconds) answers while it is
under the limit, since no proportional size is above its resident size, and the proportional sum is read only past it, at most once per
`parallel.READ_SHARE` times what the last reading took.

Every reading here is made by hand (the two sums and the clock the pace reads are patched): no test reads the clock.
"""

import sys

import pytest
from test_packed_walk_light import START_ITEM, make_offers

from coarse_support import abstraction
from crafting_system import budget, parallel
from crafting_system.planner._envelope import Net
from crafting_system.planner._envelope_plan import envelope_result


class Readings:
    """Hand-made memory: a resident sum, a proportional sum that takes `cost` seconds of a hand-moved clock to read, and the count of each read."""

    def __init__(self, monkeypatch, resident: float, proportional: float, cost: float = 0.0, group: float | None = None) -> None:
        self.resident, self.proportional, self.cost, self.group = resident, proportional, cost, group
        self.now = 0.0
        self.cheap = self.dear = 0
        monkeypatch.setattr(parallel, "_resident_sum", self.read_resident)
        monkeypatch.setattr(parallel, "_group_sum", lambda: self.group)  # no control group unless a test gives one (#1258)
        monkeypatch.setattr(parallel, "_proportional_sum", self.read_proportional)
        monkeypatch.setattr(parallel, "_now", lambda: self.now)
        monkeypatch.setattr(parallel, "_dear", [float("-inf"), None, None])

    def read_resident(self) -> float:
        self.cheap += 1
        return self.resident

    def read_proportional(self) -> float:
        self.dear += 1
        self.now += self.cost
        return self.proportional


def test_under_the_net_the_resident_sum_answers_and_the_proportional_sizes_are_not_read(monkeypatch):
    memory = Readings(monkeypatch, resident=11_000.0, proportional=9_000.0)
    answers = [parallel.held_mb(under=12_000.0) for _ in range(1_000)]
    assert memory.dear == 0 and memory.cheap == 1_000
    assert set(answers) == {11_000.0}  # an upper figure of the proportional sum: under the limit, so is the memory the net is about
    assert parallel.held_mb() == 9_000.0 and memory.dear == 1  # a figure that is said (no limit) is the proportional sum, read every time


def test_past_the_resident_sum_the_proportional_sum_decides_and_stops_the_net(monkeypatch):
    memory = Readings(monkeypatch, resident=40_000.0, proportional=9_000.0)  # four forked workers: each counts the shared pages in full
    assert parallel.held_mb(under=12_000.0) == 9_000.0 and memory.dear == 1  # not reached: the pages are counted once
    memory.proportional, memory.now = 12_500.0, 1.0
    assert parallel.held_mb(under=12_000.0) == 12_500.0  # reached: the net stops on the proportional sum, as before #1252


def test_the_proportional_sum_is_read_at_most_once_per_its_share_of_the_time(monkeypatch):
    """A question every 0.25 s (the making's gate) on a process whose proportional sum takes 0.1 s to read: on the code before #1252 the reads
    took 0.1 of every 0.35 s; now they take at most 1 / READ_SHARE of the time, and the answer between two reads is the last reading."""
    memory = Readings(monkeypatch, resident=40_000.0, proportional=9_000.0, cost=0.1)
    answers = []
    for _ in range(2_000):
        answers.append(parallel.held_mb(under=12_000.0))
        memory.now += 0.25
    reading = memory.dear * memory.cost
    assert reading / memory.now <= 1.0 / parallel.READ_SHARE + 1e-9
    assert memory.dear >= memory.now / ((1.0 + parallel.READ_SHARE) * memory.cost + 0.25) - 1  # and no rarer: the next read comes once the pace allows
    assert set(answers) == {9_000.0}


def test_a_paced_question_keeps_the_stop_of_the_last_reading(monkeypatch):
    memory = Readings(monkeypatch, resident=40_000.0, proportional=12_500.0, cost=0.1)
    assert parallel.held_mb(under=12_000.0) == 12_500.0
    memory.proportional = 1.0  # not read again within the pace: the last reading, past the net, answers
    memory.now += 0.5
    assert parallel.held_mb(under=12_000.0) == 12_500.0 and memory.dear == 1
    memory.now += parallel.READ_SHARE * memory.cost  # the pace is over: the next question reads again
    assert parallel.held_mb(under=12_000.0) == 1.0 and memory.dear == 2


def test_a_kept_reading_under_the_net_grows_with_the_upper_figure_and_stops_within_one_question(monkeypatch):
    """#1411: past the upper figure the proportional sum read 100 MB under the net, and that reading was the answer for the whole pace
    (`READ_SHARE` times its 2.4 s near 12 GB with four workers, ~48 s) while the workers grew by ~50 MB/s: R14 passed its 12,288 MB net by
    2.4 GB in the bound's build. Between two readings the answer is now the kept reading plus what the upper figure has grown since it was
    read: once the memory passes the net, the next question (0.5 s later) says so, with no new reading."""
    memory = Readings(monkeypatch, resident=12_100.0, proportional=11_900.0, cost=2.4)
    assert parallel.held_mb(under=12_000.0) == 11_900.0 and memory.dear == 1  # the file pages: the upper figure is past, the memory is not
    answers = []
    for _ in range(8):  # 50 MB/s in the workers, a question every 0.5 s: both sums grow by 25 MB a question
        memory.now += 0.5
        memory.resident += 25.0
        memory.proportional += 25.0
        answers.append(parallel.held_mb(under=12_000.0))
    assert memory.dear == 1  # all within the pace: no new reading
    assert answers == [11_925.0, 11_950.0, 11_975.0, 12_000.0, 12_025.0, 12_050.0, 12_075.0, 12_100.0]
    assert answers[3] >= 12_000.0  # the question at which the memory reaches the net is past it: the stop comes then, not ~48 s later


def test_a_kept_reading_never_answers_below_itself_when_the_upper_figure_falls_but_stays_past_the_net(monkeypatch):
    memory = Readings(monkeypatch, resident=40_000.0, proportional=11_000.0, cost=1.0)
    assert parallel.held_mb(under=12_000.0) == 11_000.0
    memory.resident, memory.now = 30_000.0, 0.5  # a worker freed pages: still past the limit, the kept reading answers
    assert parallel.held_mb(under=12_000.0) == 11_000.0 and memory.dear == 1


def test_forgetting_the_reading_drops_its_upper_figure_too(monkeypatch):
    memory = Readings(monkeypatch, resident=12_100.0, proportional=11_900.0, cost=1.0)
    assert parallel.held_mb(under=12_000.0) == 11_900.0
    parallel.forget_reading()
    assert parallel._dear == [float("-inf"), None, None]
    memory.resident, memory.proportional, memory.now = 12_500.0, 11_950.0, 0.5
    assert parallel.held_mb(under=12_000.0) == 11_950.0 and memory.dear == 2  # read anew, not the old reading plus 400 MB


def test_a_cheap_answer_does_not_wait_for_the_pace(monkeypatch):
    memory = Readings(monkeypatch, resident=40_000.0, proportional=12_500.0, cost=1.0)
    assert parallel.held_mb(under=12_000.0) == 12_500.0
    memory.resident = 3_000.0  # the workers ended: the resident sum is under the limit again
    assert parallel.held_mb(under=12_000.0) == 3_000.0 and memory.dear == 1


def test_the_cost_figures_own_question_reads_the_resident_size_first(monkeypatch):
    """The run of the cost figures (#738) asks `own_mb` with its net: under it the resident size answers, past it the proportional size."""
    dear = []
    monkeypatch.setattr(parallel.budget, "process_mb", lambda pid=None: 11_000.0)
    monkeypatch.setattr(parallel, "_proc_mb", lambda pid: dear.append(pid) or 9_000.0)
    assert parallel.own_mb(under=12_000.0) == 11_000.0 and dear == []
    assert parallel.own_mb(under=10_000.0) == 9_000.0 and dear == ["self"]
    assert parallel.own_mb() == 9_000.0 and len(dear) == 2


def test_the_searchs_questions_pass_their_limit(monkeypatch):
    """Every question of the envelope search and of its bound's build on its memory net (`Net.memory_mb`) passes the limit, so each is the cheap
    read while the process is under it; only the round's peak (a figure that is said) and the room check before the arrays grow read in full."""
    monkeypatch.setattr(budget, "ASK_EVERY", 1)
    monkeypatch.setattr(budget, "ASK_SECONDS", 0.0)  # no gate: every piece of every making asks
    asked = []
    monkeypatch.setattr(parallel, "held_mb", lambda under=None: asked.append(under) or 1.0)
    ab = abstraction()
    envelope_result(ab, ab.compress(START_ITEM), make_offers(), net=Net(memory_mb=5_000.0))
    limits = [under for under in asked if under is not None]
    assert len(limits) > 100
    assert set(limits) == {5_000.0}  # the net's limit
    assert asked.count(None) < len(limits) / 10


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="the proportional sizes are read from /proc")
def test_the_resident_sum_is_never_under_the_proportional_sum():
    """The reason the cheap answer is sound, on this process's own /proc: its resident size counts in full the pages it shares."""
    proportional = parallel.held_mb()
    resident = parallel.held_mb(under=float("inf"))
    assert resident >= proportional - 16.0 > 0.0  # 16 MB: what the process may free between the two reads
