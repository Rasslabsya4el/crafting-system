"""The diagonal of the fundamental matrix from the cycles of a chain (tickets #572 and #490), against the dense inverse.

`inverse_diagonal` is exact by the structure of the chain (components, rows that states share, the Woodbury step); every test here builds a
random chain, inverts `I - P` densely with numpy, and compares. The limit above which a component is cut is lowered so that the cut and the
Woodbury step run on chains of a few dozen states.
"""

import numpy as np
import pytest

from crafting_system.solver import _packed_chain as pc


def random_chain(rng, n, *, shared=0, shared_users=0, density=3, leak=0.2):
    """`(dense P, ptr, col, weight)`: a random substochastic chain of `n` states with `shared` rows that `shared_users` states each take."""
    rows: list[dict[int, float]] = []
    kernels = []
    for _ in range(shared):
        width = int(rng.integers(2, max(3, n // 2)))
        targets = rng.choice(n, size=width, replace=False)
        weights = rng.random(width)
        weights = weights / weights.sum() * (1 - leak)
        kernels.append(dict(zip(targets.tolist(), weights.tolist(), strict=True)))
    taking = rng.permutation(n)[: shared * shared_users]
    taken = {int(s): kernels[i % shared] for i, s in enumerate(taking)} if shared else {}
    for s in range(n):
        if s in taken:
            row = {t: p for t, p in taken[s].items() if t != s}
        else:
            width = int(rng.integers(1, density + 1))
            targets = [t for t in rng.choice(n, size=width, replace=False).tolist() if t != s]
            weights = rng.random(len(targets))
            weights = weights / max(weights.sum(), 1e-12) * (1 - leak) * rng.random()
            row = dict(zip(targets, weights.tolist(), strict=True))
        rows.append(row)
    dense = np.zeros((n, n))
    ptr = [0]
    col: list[int] = []
    weight: list[float] = []
    for s, row in enumerate(rows):
        for t in sorted(row):
            dense[s, t] = row[t]
            col.append(t)
            weight.append(row[t])
        ptr.append(len(col))
    return dense, np.array(ptr, dtype=np.int64), np.array(col, dtype=np.int64), np.array(weight)


def inverse_of(dense):
    return np.linalg.inv(np.eye(len(dense)) - dense)


@pytest.mark.parametrize("seed", range(12))
def test_the_triangular_solves_match_the_dense_solves(seed):
    rng = np.random.default_rng(seed)
    n = int(rng.integers(5, 60))
    dense, ptr, col, weight = random_chain(rng, n, density=2)
    label, count = pc.components(n, ptr, col)
    solver = pc.Triangular(n, ptr, col, weight, label, count)
    rhs = rng.random((n, 4))
    exact = inverse_of(dense)

    assert solver.solve(rhs) == pytest.approx(exact @ rhs, rel=1e-9, abs=1e-12)
    assert solver.solve_transposed(rhs) == pytest.approx(exact.T @ rhs, rel=1e-9, abs=1e-12)
    assert solver.solve(rhs[:, 0]) == pytest.approx(exact @ rhs[:, 0], rel=1e-9, abs=1e-12)
    assert solver.diagonal() == pytest.approx(np.diag(exact), rel=1e-9)


@pytest.mark.parametrize("seed", range(10))
def test_the_components_of_a_random_graph_are_the_ones_of_the_reachability_closure(seed):
    rng = np.random.default_rng(100 + seed)
    n = int(rng.integers(2, 40))
    dense, ptr, col, _ = random_chain(rng, n, density=2)
    label, count = pc.components(n, ptr, col)
    reach = np.linalg.matrix_power((dense > 0).astype(float) + np.eye(n), n) > 0
    same = reach & reach.T
    assert count == len({tuple(row) for row in same.tolist()})
    assert all((label[s] == label[t]) == bool(same[s, t]) for s in range(n) for t in range(n))
    assert all(label[s] >= label[t] for s in range(n) for t in col[ptr[s] : ptr[s + 1]].tolist())  # sink-first


@pytest.mark.parametrize("seed", range(10))
def test_a_chain_whose_components_are_small_gets_its_diagonal_without_a_cut(seed):
    rng = np.random.default_rng(200 + seed)
    n = int(rng.integers(5, 50))
    dense, ptr, col, weight = random_chain(rng, n, density=3)

    got, _ = pc.inverse_diagonal(n, ptr, col, weight)

    assert got == pytest.approx(np.diag(inverse_of(dense)), rel=1e-9)


@pytest.mark.parametrize("seed", range(20))
def test_cutting_the_shared_rows_gives_the_same_diagonal_by_the_woodbury_identity(seed):
    rng = np.random.default_rng(300 + seed)
    n = int(rng.integers(20, 90))
    dense, ptr, col, weight = random_chain(rng, n, shared=int(rng.integers(1, 4)), shared_users=int(rng.integers(3, 12)), density=2)

    got, _ = pc.inverse_diagonal(n, ptr, col, weight, invert_limit=3)

    assert got == pytest.approx(np.diag(inverse_of(dense)), rel=1e-8)


@pytest.mark.parametrize("seed", range(10))
def test_a_component_that_stays_big_after_the_shared_rows_is_cut_state_by_state(seed):
    rng = np.random.default_rng(400 + seed)
    n = int(rng.integers(30, 80))
    dense, ptr, col, weight = random_chain(rng, n, shared=1, shared_users=4, density=3)

    got, _ = pc.inverse_diagonal(n, ptr, col, weight, invert_limit=2)

    assert got == pytest.approx(np.diag(inverse_of(dense)), rel=1e-8)


def test_a_block_of_solves_is_cut_into_pieces_without_changing_the_answer(monkeypatch):
    rng = np.random.default_rng(7)
    n = 60
    dense, ptr, col, weight = random_chain(rng, n, shared=2, shared_users=8, density=3)
    monkeypatch.setattr(pc, "BLOCK_CELLS", 90)  # one column and a few edges at a time

    got, _ = pc.inverse_diagonal(n, ptr, col, weight, invert_limit=3)

    assert got == pytest.approx(np.diag(inverse_of(dense)), rel=1e-8)


@pytest.mark.parametrize("limit", [1000, 3])
def test_the_row_of_the_start_found_by_the_same_pieces_agrees_with_the_dense_row_and_a_wrong_row_shows(limit):
    rng = np.random.default_rng(9)
    n = 50
    dense, ptr, col, weight = random_chain(rng, n, shared=2, shared_users=6, density=2)
    exact = inverse_of(dense)
    row = exact[0].copy()

    _, fine = pc.inverse_diagonal(n, ptr, col, weight, invert_limit=limit, start=0, start_row=row)
    wrong = row.copy()
    wrong[np.argmax(row[1:]) + 1] *= 1.01
    _, caught = pc.inverse_diagonal(n, ptr, col, weight, invert_limit=limit, start=0, start_row=wrong)

    assert fine < 1e-9
    assert caught > 1e-3


def test_cut_rows_too_many_to_put_back_in_the_memory_allowed_are_refused_not_guessed(monkeypatch):
    rng = np.random.default_rng(11)
    n = 40
    dense, ptr, col, weight = random_chain(rng, n, shared=2, shared_users=6, density=2)
    monkeypatch.setattr(pc, "WOODBURY_CELLS", 10)

    with pytest.raises(pc.CyclesTooTangled, match="cells"):
        pc.inverse_diagonal(n, ptr, col, weight, invert_limit=3)


def test_a_chain_of_one_state_and_of_none():
    ptr, col, weight = np.zeros(2, dtype=np.int64), np.zeros(0, dtype=np.int64), np.zeros(0)
    assert pc.inverse_diagonal(1, ptr, col, weight)[0].tolist() == [1.0]
    assert pc.inverse_diagonal(0, np.zeros(1, dtype=np.int64), col, weight)[0].tolist() == []
