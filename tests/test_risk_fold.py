"""Folding the free states of a chain: exit distributions against a dense solve, the stiff cases, the limits."""

import random

import numpy as np
import pytest
from risk_support import GOAL, is_goal

from crafting_system.risk import _fold
from crafting_system.risk._chain import build_chain
from crafting_system.risk._fold import Folded, fold_free
from crafting_system.solver import Action

DEAD = "dead"  # reachable, no policy entry: stuck


def random_policy(rng, size, *, proper):
    """States 0..size-1 with random outcomes (self-loops and cycles included); `proper` gives each a goal outcome."""
    labels = [*range(size), GOAL] if proper else [*range(size), GOAL, DEAD, "trap"]
    policy = {"trap": Action("trap", 1.0, (("trap", 1),))}
    for s in range(size):
        outcomes = {rng.choice(labels): rng.randint(1, 9) for _ in range(rng.randint(1, 4))}
        if proper or rng.random() < 0.3:
            outcomes[GOAL] = rng.randint(1, 9)
        if rng.random() < 0.3:
            outcomes[s] = rng.randint(1, 60)
        policy[s] = Action(f"a{s}", 1.0, tuple(outcomes.items()))
    return policy


def random_bins(rng, chain):
    return [rng.choice((0, 0, 1, 2, 3)) for _ in chain.states]


def dense(chain):
    n = len(chain.states)
    p = np.zeros((n, n))
    for i, edges in enumerate(chain.succ):
        for j, q in edges:
            p[i, j] = q
    return p


def folded_dense(folded):
    return dense(folded.chain)


def oracle_exits(p, free):
    """Rows of the dense solve (I - P_ZZ) X = P_Z,out for the free set Z, placed in full width."""
    n = len(p)
    z = sorted(free)
    out = [j for j in range(n) if j not in free]
    exits = np.zeros((n, n))
    exits[np.ix_(z, out)] = np.linalg.solve(np.eye(len(z)) - p[np.ix_(z, z)], p[np.ix_(z, out)])
    return exits


@pytest.mark.parametrize("seed", range(80))
def test_exits_match_the_dense_solve(seed):
    rng = random.Random(seed)
    chain = build_chain(random_policy(rng, rng.randint(2, 30), proper=False), 0, is_goal)
    bins = random_bins(rng, chain)
    finishing = chain.finishing_states()
    free = {i for i in finishing if bins[i] == 0}
    paying = [i for i in finishing if i not in free]

    folded = fold_free(chain, bins)

    assert folded is not None
    after = folded.chain
    assert after.finishing_states() == paying
    assert (after.states, after.goal, after.can_finish, after.inputs) == (
        chain.states,
        chain.goal,
        chain.can_finish,
        chain.inputs,
    )
    if not free:
        assert after is chain
        return
    p = dense(chain)
    exits = oracle_exits(p, free)
    got = folded_dense(folded)
    for i in paying:
        want = p[i] * np.isin(range(len(p)), sorted(free), invert=True) + p[i] @ exits
        assert got[i] == pytest.approx(want, abs=1e-12, rel=1e-10)
        assert got[i].sum() == pytest.approx(p[i].sum(), abs=1e-12)
        assert not got[i][sorted(free)].any()
    for i in free:
        assert after.action[i] is None
    start = np.zeros(len(p))
    if 0 in free:
        start = exits[0]
        assert folded.initial == tuple(sorted(folded.initial))
    elif 0 in paying:
        start[0] = 1.0
    initial = np.zeros(len(p))
    for i, mass in folded.initial:
        initial[i] = mass
    goals = np.array(chain.goal)
    assert initial == pytest.approx(start * ~goals * np.array(chain.can_finish), abs=1e-12, rel=1e-10)
    assert folded.goal_mass == pytest.approx(start[goals].sum(), abs=1e-12)
    assert sum(m for _, m in folded.initial) + folded.goal_mass <= 1 + 1e-12


@pytest.mark.parametrize(("stay", "exit_b", "exit_goal"), [(10**15 - 3, 1, 2), (10**9 - 3, 1, 2), (10**15 - 1, 1, 0)])
def test_a_stiff_free_self_loop_keeps_the_exact_exit(stay, exit_b, exit_goal):
    policy = {
        "A": Action("a", 1.0, (("F", 1),)),
        "F": Action("f", 1.0, (("F", stay), ("B", exit_b), (GOAL, exit_goal))),
        "B": Action("b", 1.0, ((GOAL, 1),)),
    }
    chain = build_chain(policy, "A", is_goal)
    bins = [{"A": 1, "F": 0, "B": 1}.get(s, 0) for s in chain.states]

    folded = fold_free(chain, bins)

    assert folded is not None
    row = dict(folded.chain.succ[0])
    to_b = chain.states.index("B")
    assert row[to_b] == pytest.approx(exit_b / (exit_b + exit_goal), rel=1e-12)
    assert sum(row.values()) == pytest.approx(1.0, rel=1e-12)
    assert folded.initial == ((0, 1.0),)


def test_a_free_start_gives_its_exits_as_the_initial_mass():
    policy = {
        "F": Action("f", 1.0, (("F", 10**15), ("B", 1), (GOAL, 3), (DEAD, 4))),
        "B": Action("b", 1.0, ((GOAL, 1),)),
    }
    chain = build_chain(policy, "F", is_goal)
    bins = [0 if s == "F" else 1 for s in chain.states]

    folded = fold_free(chain, bins)

    assert folded is not None
    assert folded.initial == ((chain.states.index("B"), pytest.approx(1 / 8, rel=1e-12)),)
    assert folded.goal_mass == pytest.approx(3 / 8, rel=1e-12)


def test_no_free_state_returns_the_same_chain():
    policy = {"S": Action("try", 1.0, ((GOAL, 1), ("S", 1)))}
    chain = build_chain(policy, "S", is_goal)

    folded = fold_free(chain, [1, 0])

    assert folded == Folded(chain, ((0, 1.0),), 0.0)
    assert folded.chain is chain


def test_a_free_component_over_the_limit_is_not_folded(monkeypatch):
    monkeypatch.setattr(_fold, "FOLD_LIMIT", 3)
    size = 5
    policy = {"S": Action("s", 1.0, ((0, 1),))}
    for i in range(size):
        ring = ((i + 1) % size, 1)
        policy[i] = Action("f", 1.0, (ring, (GOAL, 1)) if i == 0 else (ring,))
    chain = build_chain(policy, "S", is_goal)
    bins = [0 if isinstance(s, int) else 1 for s in chain.states]

    assert fold_free(chain, bins) is None

    monkeypatch.setattr(_fold, "FOLD_LIMIT", size)
    assert fold_free(chain, bins) is not None


def test_a_long_free_path_folds_without_recursion(monkeypatch):
    size = 5000
    monkeypatch.setattr(_fold, "FOLD_LIMIT", 3)  # a path is singleton components, so the limit does not bind
    policy = {"P": Action("p", 1.0, ((0, 1),))}
    for i in range(size):
        policy[i] = Action("f", 1.0, ((i + 1, 1), (GOAL, 1)) if i + 1 < size else ((GOAL, 1),))
    chain = build_chain(policy, "P", is_goal)
    bins = [1 if s == "P" else 0 for s in chain.states]

    folded = fold_free(chain, bins)

    assert folded is not None
    assert folded.chain.succ[0] == ((chain.states.index(GOAL), pytest.approx(1.0, rel=1e-12)),)


def test_a_long_free_cycle_folds_without_recursion(monkeypatch):
    size, leak_at = 5000, 2500
    monkeypatch.setattr(_fold, "FOLD_LIMIT", 10_000)
    policy = {"P": Action("p", 1.0, ((0, 1),))}
    for i in range(size):
        nxt = ((i + 1) % size, 1)
        policy[i] = Action("f", 1.0, (nxt, (GOAL, 1)) if i == 0 else (nxt, (DEAD, 1)) if i == leak_at else (nxt,))
    chain = build_chain(policy, "P", is_goal)
    bins = [1 if s == "P" else 0 for s in chain.states]

    folded = fold_free(chain, bins)

    assert folded is not None
    row = dict(folded.chain.succ[0])
    assert row[chain.states.index(GOAL)] == pytest.approx(2 / 3, rel=1e-12)
    assert row[chain.states.index(DEAD)] == pytest.approx(1 / 3, rel=1e-12)
