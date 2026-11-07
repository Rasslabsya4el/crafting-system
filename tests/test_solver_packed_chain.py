"""The diagonal of the fundamental matrix from the cycles of a chain (tickets #572 and #490), against the dense inverse.

`inverse_diagonal` is exact by the structure of the chain (components, rows that states share, the Woodbury step); every test here builds a
random chain, inverts `I - P` densely with numpy, and compares. The limit above which a component is cut is lowered so that the cut and the
Woodbury step run on chains of a few dozen states.
"""

import numpy as np
import pytest

from crafting_system.solver import _packed_chain as pc


def random_chain(rng, n, *, shared=0, shared_users=0, density=3, leak=0.2, loops=False):
    """`(dense Q, ptr, col, weight)`: a random substochastic chain of `n` states with `shared` rows that `shared_users` states each take.

    With `loops` a row may hold a self-loop, and a shared row keeps the entry of a taker that is among its outcomes (so the rows stay identical)."""
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
            row = {t: p for t, p in taken[s].items() if loops or t != s}
        else:
            width = int(rng.integers(1, density + 1))
            targets = [t for t in rng.choice(n, size=width, replace=False).tolist() if loops or t != s]
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


def leave_of(dense):
    """The chance to leave each state for any other: one minus its self-loop."""
    return 1.0 - np.diag(dense)


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
    dense, ptr, col, weight = random_chain(rng, n, density=3, loops=True)

    got, _ = pc.inverse_diagonal(n, ptr, col, weight, leave_of(dense))

    assert got == pytest.approx(np.diag(inverse_of(dense)), rel=1e-9)


@pytest.mark.parametrize("seed", range(20))
def test_cutting_the_shared_rows_gives_the_same_diagonal_by_the_woodbury_identity(seed):
    rng = np.random.default_rng(300 + seed)
    n = int(rng.integers(20, 90))
    dense, ptr, col, weight = random_chain(rng, n, shared=int(rng.integers(1, 4)), shared_users=int(rng.integers(3, 12)), density=2, loops=True)

    got, _ = pc.inverse_diagonal(n, ptr, col, weight, leave_of(dense), invert_limit=3)

    assert got == pytest.approx(np.diag(inverse_of(dense)), rel=1e-8)


@pytest.mark.parametrize("seed", range(10))
def test_a_component_that_stays_big_after_the_shared_rows_is_cut_state_by_state(seed):
    rng = np.random.default_rng(400 + seed)
    n = int(rng.integers(30, 80))
    dense, ptr, col, weight = random_chain(rng, n, shared=1, shared_users=4, density=3, loops=True)

    got, _ = pc.inverse_diagonal(n, ptr, col, weight, leave_of(dense), invert_limit=2)

    assert got == pytest.approx(np.diag(inverse_of(dense)), rel=1e-8)


def test_a_block_of_solves_is_cut_into_pieces_without_changing_the_answer(monkeypatch):
    rng = np.random.default_rng(7)
    n = 60
    dense, ptr, col, weight = random_chain(rng, n, shared=2, shared_users=8, density=3, loops=True)
    monkeypatch.setattr(pc, "BLOCK_CELLS", 90)  # one column and a few edges at a time

    got, _ = pc.inverse_diagonal(n, ptr, col, weight, leave_of(dense), invert_limit=3)

    assert got == pytest.approx(np.diag(inverse_of(dense)), rel=1e-8)


@pytest.mark.parametrize("limit", [1000, 3])
def test_the_row_of_the_start_found_by_the_same_pieces_agrees_with_the_dense_row_and_a_wrong_row_shows(limit):
    rng = np.random.default_rng(9)
    n = 50
    dense, ptr, col, weight = random_chain(rng, n, shared=2, shared_users=6, density=2, loops=True)
    exact = inverse_of(dense)
    row = exact[0].copy()

    _, fine = pc.inverse_diagonal(n, ptr, col, weight, leave_of(dense), invert_limit=limit, start=0, start_row=row)
    wrong = row.copy()
    wrong[np.argmax(row[1:]) + 1] *= 1.01
    _, caught = pc.inverse_diagonal(n, ptr, col, weight, leave_of(dense), invert_limit=limit, start=0, start_row=wrong)

    assert fine < 1e-9
    assert caught > 1e-3


def layered_chain(rng, n, layers, back):
    """`(dense Q, ptr, col, weight)` of a sparse chain in layers: each state goes to three states of the next layer and `back` states of an earlier one (a state may be named twice in a row)."""
    per = n // layers
    rows, cols = [], []
    for s in range(n):
        layer = s // per
        for _ in range(3):
            rows.append(s)
            cols.append(min(layers - 1, layer + 1) * per + int(rng.integers(per)))
        for _ in range(back):
            rows.append(s)
            cols.append(int(rng.integers(0, layer + 1)) * per + int(rng.integers(per)))
    rows, cols = np.array(rows), np.array(cols)
    keep = rows != cols
    rows, cols = rows[keep], cols[keep]
    order = np.lexsort((cols, rows))
    rows, cols = rows[order], cols[order]
    weight = rng.random(len(rows))
    weight = weight / np.bincount(rows, weights=weight, minlength=n)[rows] * 0.85
    dense = np.zeros((n, n))
    np.add.at(dense, (rows, cols), weight)
    return dense, np.searchsorted(rows, np.arange(n + 1)), cols, weight


@pytest.mark.parametrize("seed", range(4))
def test_a_big_component_of_a_sparse_layered_chain_is_cut_state_by_state_in_batches_and_put_back_exactly(seed):
    """The shape of R14's policy (372,000 edges for 87,000 states, one component of 18,786 after its 12 shared rows are cut), at a size a dense inverse can check."""
    rng = np.random.default_rng(700 + seed)
    n = 400
    dense, ptr, col, weight = layered_chain(rng, n, 10, 1)
    exact = inverse_of(dense)

    got, deviation = pc.inverse_diagonal(n, ptr, col, weight, np.ones(n), invert_limit=60, start=0, start_row=exact[0])

    assert got == pytest.approx(np.diag(exact), rel=1e-9)
    assert deviation < 1e-9


def stiff_chain(rng, n, power):
    """`(ptr, col, weight, leave, leak, exact N)`: every state stays with chance 1 - delta (delta from 10**-power to 10**-(power - 3)), and sends 0.7 delta to one to three others and 0.3 delta out.

    The reference is (I - P)^-1 diag(1 / leave) with P the rows divided by `leave`: it has no `1 - p` in it, so it is good to the last digits.
    """
    delta = 10.0 ** -(power - rng.integers(0, 4, size=n))
    ptr, col, weight = [0], [], []
    scaled = np.zeros((n, n))
    for s in range(n):
        targets = [u for u in rng.choice(n, size=int(rng.integers(1, 4)), replace=False).tolist() if u != s]
        share = rng.random(len(targets))
        share = share / share.sum() * 0.7 * delta[s]
        for u, w in sorted([(s, 1.0 - delta[s]), *zip(targets, share.tolist(), strict=True)]):
            col.append(u)
            weight.append(w)
            if u != s:
                scaled[s, u] = w / delta[s]
        ptr.append(len(col))
    exact = np.linalg.inv(np.eye(n) - scaled) / delta[None, :]
    return np.array(ptr), np.array(col), np.array(weight), delta, 0.3 * delta, exact


@pytest.mark.parametrize("power", [6, 10, 13])
@pytest.mark.parametrize("limit", [1000, 3])
def test_a_chain_that_stays_where_it_is_with_chance_one_minus_1e_minus_13_gets_its_diagonal_whole_and_cut(power, limit):
    """#615: the rows put back by the Woodbury step are not formed as 1 - p (the first version lost all digits at 1e-13); the check of the start row stays under `AGREE`."""
    for seed in range(8):
        rng = np.random.default_rng(900 + seed)
        n = int(rng.integers(20, 50))
        ptr, col, weight, leave, leak, exact = stiff_chain(rng, n, power)

        got, deviation = pc.inverse_diagonal(n, ptr, col, weight, leave, invert_limit=limit, start=0, start_row=exact[0], leak=leak)

        assert got == pytest.approx(np.diag(exact), rel=1e-9), (power, limit, seed)
        assert deviation < 1e-6, (power, limit, seed)  # `AGREE` of the route flow


def test_the_memory_counted_for_putting_cut_rows_back_has_the_blocks_in_it(monkeypatch):
    rng = np.random.default_rng(12)
    n = 80
    dense, ptr, col, weight = random_chain(rng, n, shared=2, shared_users=10, density=3, loops=True)
    monkeypatch.setattr(pc, "WOODBURY_CELLS", 1)
    with pytest.raises(pc.CyclesTooTangled) as refused:
        pc.inverse_diagonal(n, ptr, col, weight, leave_of(dense), invert_limit=3)
    words = str(refused.value).replace(",", "").split()
    q, wanted, cells = int(words[2]), int(words[7]), int(words[10])

    assert cells >= (2 * wanted + 2 * q) * q + 6 * min(pc.BLOCK_CELLS, n * q)  # the blocks of a solve are held too, six of them


def test_cut_rows_too_many_to_put_back_in_the_memory_allowed_are_refused_not_guessed(monkeypatch):
    rng = np.random.default_rng(11)
    n = 40
    dense, ptr, col, weight = random_chain(rng, n, shared=2, shared_users=6, density=2, loops=True)
    monkeypatch.setattr(pc, "WOODBURY_CELLS", 10)

    with pytest.raises(pc.CyclesTooTangled, match="cells"):
        pc.inverse_diagonal(n, ptr, col, weight, leave_of(dense), invert_limit=3)


def test_a_chain_of_one_state_and_of_none():
    ptr, col, weight = np.zeros(2, dtype=np.int64), np.zeros(0, dtype=np.int64), np.zeros(0)
    assert pc.inverse_diagonal(1, ptr, col, weight, np.ones(1))[0].tolist() == [1.0]
    assert pc.inverse_diagonal(0, np.zeros(1, dtype=np.int64), col, weight, np.ones(0))[0].tolist() == []


# --- ChainSolver: `(I - P) x = b` from the cycles of the chain (ticket #621) --------------------------------------------------------------------


def chain_solver_inputs(dense, ptr, col, weight, *, pool: bool, leak=None):
    """The arguments of `ChainSolver` for a chain: with `pool`, every row that two or more states share is given once (`shared`), as the policy evaluation gives a kernel."""
    n = len(dense)
    leave = leave_of(dense)
    leak = np.maximum(0.0, 1.0 - dense.sum(axis=1)) if leak is None else leak
    if not pool:
        return n, ptr, col, weight, leave, leak, None, ()
    shared_of = np.full(n, -1, dtype=np.int64)
    shared = []
    keep = np.ones(len(col), dtype=bool)
    for g in pc._row_groups(ptr, col, weight, np.arange(n)):
        if len(g) < 2:
            continue
        shared_of[g] = len(shared)
        shared.append((col[ptr[g[0]] : ptr[g[0] + 1]], weight[ptr[g[0]] : ptr[g[0] + 1]], float(leak[g[0]])))
        for s in g:
            keep[ptr[s] : ptr[s + 1]] = False
    sizes = np.where(shared_of >= 0, 0, np.diff(ptr))
    return n, np.concatenate(([0], np.cumsum(sizes))), col[keep], weight[keep], leave, leak, shared_of, tuple(shared)


def dense_solution(dense, b):
    """`x` with `x[s] = b[s] + sum over t != s of Q[s, t] / leave[s] x[t]`, the system of the policy evaluation, solved densely."""
    off = dense.copy()
    np.fill_diagonal(off, 0.0)
    return np.linalg.solve(np.eye(len(dense)) - off / leave_of(dense)[:, None], b)


@pytest.mark.parametrize("pool", [False, True])
@pytest.mark.parametrize("limit", [1000, 3])
@pytest.mark.parametrize("seed", range(6))
def test_the_chain_solver_gives_the_dense_solution_with_the_rows_that_states_share_given_once_or_expanded(seed, limit, pool):
    rng = np.random.default_rng(1200 + seed)
    n = int(rng.integers(30, 80))
    dense, ptr, col, weight = random_chain(rng, n, shared=3, shared_users=8, density=3, loops=True)
    b = rng.random(n) + 0.1

    solver = pc.ChainSolver(*chain_solver_inputs(dense, ptr, col, weight, pool=pool), invert_limit=limit)

    assert solver.solve(b) == pytest.approx(dense_solution(dense, b), rel=1e-9)
    assert (solver.q > 0) == (pool or limit < n)  # rows were cut when they were given as shared or a component was above the limit


def test_the_chain_solver_puts_back_a_shared_row_even_when_every_component_is_small():
    rng = np.random.default_rng(31)
    n = 40
    dense, ptr, col, weight = random_chain(rng, n, shared=2, shared_users=10, density=2, loops=False)
    b = rng.random(n) + 0.1

    solver = pc.ChainSolver(*chain_solver_inputs(dense, ptr, col, weight, pool=True))  # the default limit of 4,000: nothing is big

    assert solver.q == 2 and solver.solve(b) == pytest.approx(dense_solution(dense, b), rel=1e-9)


@pytest.mark.parametrize("power", [6, 10, 13])
@pytest.mark.parametrize("limit", [1000, 3])
def test_the_chain_solver_of_a_stiff_chain_is_as_good_as_the_exact_reference(power, limit):
    """#615's stiff chain (every state stays with chance 1 - delta), whole and cut, against `N diag(leave) rhs` of the reference."""
    for seed in range(8):
        rng = np.random.default_rng(1300 + seed)
        n = int(rng.integers(20, 50))
        ptr, col, weight, leave, leak, exact = stiff_chain(rng, n, power)
        rhs = rng.random(n) + 0.1
        solver = pc.ChainSolver(n, ptr, col, weight, leave, leak, invert_limit=limit)
        reference = exact @ (leave * rhs)

        x = solver.solve(rhs)

        assert x == pytest.approx(reference, rel=1e-9), (power, limit, seed)


def test_a_shared_row_that_does_not_fit_the_memory_of_a_run_is_refused_by_the_cost_of_the_cycles_not_by_a_count_of_states(monkeypatch):
    rng = np.random.default_rng(12)
    n = 60
    dense, ptr, col, weight = random_chain(rng, n, shared=3, shared_users=6, density=2, loops=True)
    monkeypatch.setattr(pc, "WOODBURY_CELLS", 10)

    with pytest.raises(pc.CyclesTooTangled, match="needs .* cells"):
        pc.ChainSolver(*chain_solver_inputs(dense, ptr, col, weight, pool=True))


def test_a_chain_solver_of_one_state():
    one = pc.ChainSolver(1, np.zeros(2, dtype=np.int64), np.zeros(0, dtype=np.int64), np.zeros(0), np.ones(1), np.ones(1))
    assert one.solve(np.array([3.0])).tolist() == [3.0]
