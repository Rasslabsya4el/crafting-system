"""The proper states and the luckiest paths in one pass, not one sweep per step of the longest path (#1527, OR-40).

`proper_states` carried the luckiest-path costs one step further from the goals per sweep of the whole graph, so a plan whose chain reaches the
goal only at its far end took one sweep per state of the chain: 9.3 s on a chain of 20,000 states, more than 10 minutes on 200,000, about
1,000 s a round on R17's 210,847 (#1516's measurement). Now, once the sweeps have changed the distances `SWEEPS_BEFORE_PASS` (64) times, one
label-setting pass from the goals (`_cheapest_paths`) gives the fixed point, and the next sweep changes nothing.

The old pass is kept here as the oracle only: `proper_states` with `SWEEPS_BEFORE_PASS` past any count of sweeps is the old code, sweep for
sweep. Every output is compared to it bit for bit, with the pass forced after the first sweep, through the solver's public entry
(`solve_graph`, cold and warm) and through `proper_states`. The sweeps are counted by `kernel_min`, so nothing here reads a clock (ADR-0014).
"""

import math

import numpy as np
import pytest

from crafting_system.solver import ConvergenceError, PackedBuilder, PackedGraph
from crafting_system.solver import _packed_solve
from crafting_system.solver._packed_solve import Work, proper_states, solve_graph

INF = math.inf
# costs that round differently when added in another order (0.1 + 0.2 != 0.3), free steps, a tip's floor, a huge step, and ties (1.0 twice)
COSTS = [0.0, 0.1, 0.2, 0.3, 1.0 / 3.0, 1.0, 1.0, 2.0, 1e-200, 1e16]


NEVER = 1 << 62  # `SWEEPS_BEFORE_PASS` for the old pass: the sweeps alone


@pytest.fixture
def sweeps(monkeypatch) -> dict:
    """Counts the sweeps of `proper_states` (its calls of `kernel_min`) and its passes, and fails a run past `limit` sweeps."""
    count = {"sweeps": 0, "passes": 0, "limit": None}
    real_min, real_pass = _packed_solve.kernel_min, getattr(_packed_solve, "_cheapest_paths", None)  # (None on main: the chain fails on its sweeps)

    def swept(graph, f):
        count["sweeps"] += 1
        if count["limit"] is not None and count["sweeps"] > count["limit"]:
            raise AssertionError(f"more than {count['limit']} sweeps of the cheapest paths")
        return real_min(graph, f)

    def passed(work, cost, deadline=None):
        count["passes"] += 1
        return real_pass(work, cost, deadline)

    monkeypatch.setattr(_packed_solve, "kernel_min", swept)
    if real_pass is not None:
        monkeypatch.setattr(_packed_solve, "_cheapest_paths", passed)
    return count


def chain(n: int, stay: int = 1_000_000) -> PackedGraph:
    """States 0..n-1 in a row, each with one action of 1 c that moves on with weight 1 and stays with weight `stay`; state n is the goal."""
    goal = np.zeros(n + 1, dtype=bool)
    goal[n] = True
    return PackedGraph(
        goal=goal, act_ptr=np.concatenate((np.arange(n + 1, dtype=np.int64), [n])), act_tag=np.ones(n, dtype=np.int32), act_cost=np.ones(n),
        act_kernel=np.arange(n, dtype=np.int32), k_ptr=np.arange(0, 2 * n + 1, 2, dtype=np.int64),
        k_succ=np.stack((np.arange(1, n + 1), np.arange(n)), axis=1).ravel().astype(np.int32), k_wt=np.tile(np.array([1, stay], dtype=np.int64), n),
        k_prob=np.tile(np.array([1.0 / (stay + 1), stay / (stay + 1.0)]), n),
    )


def test_a_chain_of_200000_states_that_reaches_the_goal_at_its_end_takes_one_pass(sweeps) -> None:
    """On main this solve sweeps 200,000 times (more than 10 minutes); here it fails past 70 sweeps: 64 before the pass, one after it."""
    n = 200_000
    sweeps["limit"] = 70
    core = solve_graph(chain(n))
    assert _packed_solve.SWEEPS_BEFORE_PASS == 64
    assert sweeps["passes"] == 1 and sweeps["sweeps"] == 65
    assert core.solved.all() and core.value[0] == pytest.approx(n * 1_000_001.0, rel=1e-9)
    assert (core.action[:n] == np.arange(n)).all() and core.action[n] == -1


def random_graph(seed: int) -> PackedGraph:
    """2 to 40 states, 1 to 3 goals (some with actions of their own), states with no action, traps that only loop, and kernels drawn from a small
    pool that many actions share, with costs from `COSTS`."""
    rng = np.random.default_rng(seed)
    n = int(rng.integers(2, 41))
    goals = set(rng.choice(n, size=int(rng.integers(1, min(3, n) + 1)), replace=False).tolist())
    pool = []
    for _ in range(int(rng.integers(1, 2 * n + 1))):
        succ = rng.choice(n, size=int(rng.integers(1, min(4, n) + 1)), replace=False).tolist()
        pool.append((succ, rng.integers(1, 6, size=len(succ)).tolist()))
    builder = PackedBuilder()
    kernels = [builder.kernel(succ, weights) for succ, weights in pool]
    tag = 0
    for s in range(n):
        kind = rng.random()
        if kind < 0.1 and s not in goals:
            pass  # no action at all
        elif kind < 0.2:
            builder.action(tag, float(rng.choice(COSTS)), builder.kernel([s], [1]))  # a trap: it only stays (a goal's own loop is harmless)
            tag += 1
        else:
            for _ in range(int(rng.integers(1, 5))):
                if rng.random() < 0.3:
                    succ = rng.choice(n, size=int(rng.integers(1, min(3, n) + 1)), replace=False).tolist()
                    kernel = builder.kernel(succ, rng.integers(1, 4, size=len(succ)).tolist())
                else:
                    kernel = kernels[int(rng.integers(len(kernels)))]
                builder.action(tag, float(rng.choice(COSTS)), kernel)
                tag += 1
        builder.close_state(s in goals)
    return builder.build()


def proper_inputs(graph: PackedGraph) -> tuple[Work, np.ndarray, np.ndarray]:
    work = Work(graph)
    leave = work.shared_sums(np.ones(graph.n))
    alive = leave > 0.0
    with np.errstate(divide="ignore"):
        effective = np.where(alive, graph.act_cost / np.where(alive, leave, 1.0), INF)
    return work, alive, effective


def solved(graph: PackedGraph, **given):
    try:
        core = solve_graph(graph, **given)
    except ConvergenceError as error:
        return ("refused", str(error))
    return (core.value.tolist(), core.solved.tolist(), core.action.tolist())


@pytest.mark.parametrize("seed", range(300))
def test_proper_states_equal_the_old_sweeps_bit_for_bit(seed, monkeypatch) -> None:
    graph = random_graph(seed)
    work, alive, effective = proper_inputs(graph)
    rng = np.random.default_rng(seed + 10_000)
    start = np.where(rng.random(graph.n) < 0.5, rng.integers(-1, max(graph.num_actions, 1), size=graph.n), -1)
    monkeypatch.setattr(_packed_solve, "SWEEPS_BEFORE_PASS", NEVER)
    old = proper_states(work, alive, effective)
    old_cold, old_warm = solved(graph), solved(graph, start_policy=start)
    monkeypatch.setattr(_packed_solve, "SWEEPS_BEFORE_PASS", 1)
    new = proper_states(work, alive, effective)
    for got, want in zip(new, old):
        assert got.dtype == want.dtype and np.array_equal(got, want), (got, want)
    assert solved(graph) == old_cold and solved(graph, start_policy=start) == old_warm
    # the pass alone gives the old fixed point itself, to the bit, so the sweep after it changes nothing
    inside, ok, distance, _ = old
    assert np.array_equal(_packed_solve._cheapest_paths(work, np.where(ok, effective, INF)), distance)


def test_the_pass_asks_the_clock_and_stops_when_late(monkeypatch) -> None:
    """The pass asks the caller's deadline after every `PASS_ASK` states it settles; told the time is up, the solve stops inside it."""
    monkeypatch.setattr(_packed_solve, "PASS_ASK", 1_000)
    asked: list[str] = []

    def deadline(step: str) -> None:
        asked.append(step)
        if step.startswith("the rest of the shortest-path pass"):
            raise _packed_solve.Late("late", 0.0, step)

    work, alive, effective = proper_inputs(chain(5_000))
    with pytest.raises(_packed_solve.Late):
        proper_states(work, alive, effective, deadline)
    assert asked.count("a sweep of the cheapest paths to a goal") == 63 and asked[-1] == "the rest of the shortest-path pass to a goal"
    with pytest.raises(_packed_solve.Late, match="before the rest of the shortest-path pass to a goal"):
        solve_graph(chain(5_000), late=iter([False] * 63 + [True]).__next__)


def test_free_steps_ties_unreachable_states_and_a_shared_kernel() -> None:
    """By hand. 0 and 1 share kernel K = {2: 1, 3: 1}: 0 takes it for 0 c, 1 for 2 c; 1 also has a dearer tie of 2 c to the goal itself (the first
    action of least cost is the policy's). 2 steps free to the goal (4) and 3 for 1 c. 5 only reaches 6, which only loops, so neither is proper,
    and 7 can fall into 6 or reach the goal: its action leaves Y, so it is not proper either."""
    builder = PackedBuilder()
    shared = builder.kernel([2, 3], [1, 1])
    to_goal = builder.kernel([4], [1])
    builder.action(0, 0.0, shared); builder.close_state(False)  # 0
    builder.action(1, 2.0, shared); builder.action(2, 2.0, to_goal); builder.close_state(False)  # 1
    builder.action(3, 0.0, to_goal); builder.close_state(False)  # 2
    builder.action(4, 1.0, to_goal); builder.close_state(False)  # 3
    builder.close_state(True)  # 4, the goal
    builder.action(5, 1.0, builder.kernel([6], [1])); builder.close_state(False)  # 5
    builder.action(6, 1.0, builder.kernel([6], [1])); builder.close_state(False)  # 6
    builder.action(7, 1.0, builder.kernel([6, 4], [1, 1])); builder.close_state(False)  # 7
    graph = builder.build()
    inside, ok, distance, policy = proper_states(*proper_inputs(graph))
    assert inside.tolist() == [True, True, True, True, True, False, False, False]
    assert distance.tolist() == [0.0, 2.0, 0.0, 1.0, 0.0, INF, INF, INF]
    assert policy.tolist() == [0, 1, 3, 4, -1, -1, -1, -1]
    assert ok.tolist() == [True, True, True, True, True, False, False, False]


def test_a_graph_with_no_goal_reached_is_all_out() -> None:
    builder = PackedBuilder()
    builder.action(0, 1.0, builder.kernel([0, 1], [1, 1])); builder.close_state(False)
    builder.action(1, 1.0, builder.kernel([0], [1])); builder.close_state(False)
    builder.close_state(True)  # a goal no state reaches
    inside, ok, distance, policy = proper_states(*proper_inputs(builder.build()))
    assert inside.tolist() == [False, False, True] and distance.tolist() == [INF, INF, 0.0] and policy.tolist() == [-1, -1, -1]
    assert not ok.any()
