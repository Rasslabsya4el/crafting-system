"""The preconditioned solve of a system whose plain iteration stalls (ticket #1484, H20 of board #1434): an incomplete LU factorisation of the system
in its sparse form with extra unknowns, as the preconditioner of the planner's own BiCGSTAB.

A policy whose chain is one huge, slowly mixing cycle with a single exit (R17's first plan: 1,024,996 states, 943,748 of them in one strongly
connected part, one exit at 0.0089 per step, 712,952 states on a free action) leaves the plain BiCGSTAB of `_packed_linear.solve` flat at a
backward error of 0.0957, and its exact solve by the cycles of the chain needs 25,133 cut rows (1.96e9 cells against `WOODBURY_CELLS`). The
same system with one unknown per kernel the policy uses (`(leave + self) x_s - y_k(s) = cost_s`, `y_k = K_k x`: 5.2M entries, no kernel
expanded state by state) is factored incompletely by SuperLU (`scipy.sparse.linalg.spilu`, drop tolerance `ILU_DROP`) in 146 s and 3 GB, and
BiCGSTAB preconditioned by it reaches a backward error of 6.6e-16 in 13 steps (the probe of #1467, `.claude/scratch/t1311c/`).

The caller gives the system (`_packed_linear.Sparse`): a square sparse matrix in triplets whose first `n` unknowns are the `x` of `x = b + T x`, and
the factor `scale` its first `n` rows were multiplied by (the other rows have a right-hand side of 0). Nothing here judges an answer: the caller
measures it as any other (the backward error, the forward estimate, then the certificate of the policy's values).

The factorisation asks the run's memory net first (`parallel.active_memory_net`, as the bound's solve does, #1366): the factors hold at most
`ILU_FILL` times the entries of the matrix, and it is not begun when what the process holds and that would reach the net.

Uses scipy, the one file of `solver/` that does (ADR-0010 amended, #1484).
"""

import math
import time

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as sla

from crafting_system import parallel

ILU_DROP = 1e-4  # the drop tolerance of the incomplete factors (the probe's: R17's system to 6.6e-16 in 13 steps)
ILU_FILL = 20  # the most the factors may hold, in times the entries of the matrix (SuperLU's bound; R17's held 3.5 times)
ILU_BYTES = 12  # an entry of the factors: a float64 and its int32 index
VECTORS = 16  # the work vectors of a solve, each of the size of the system (BiCGSTAB's, the right-hand side, the factors' own)


class NoRoom(Exception):
    """The factorisation would pass the run's memory net."""


class Preconditioned:
    """`solve(b, tol)`: `x` of `x = b + T x` by BiCGSTAB (`_packed_linear.bicgstab`) on the system right-preconditioned by its incomplete LU factors.

    Built once per system; `seconds` is the time of the factorisation, `entries` what the factors hold, `iterations` the BiCGSTAB steps of all the
    solves made with it.
    """

    def __init__(self, system, drop: float | None = None, fill: float | None = None) -> None:
        from ._packed_linear import BICGSTAB_ITERATIONS  # (the linear solve imports this file only when it needs it)

        self.n, self.size = len(system.scale), int(system.size)
        self.scale = system.scale
        self.max_iter = BICGSTAB_ITERATIONS
        fill = ILU_FILL if fill is None else fill
        entries = len(system.value)
        need = (fill * entries * ILU_BYTES + VECTORS * self.size * 8) / (1 << 20)
        net = parallel.active_memory_net()
        if net is not None:
            held = parallel.held_mb(under=max(net - need, 0.0), paced=False)  # never late: asked once, before the step that cannot be cut
            if held is not None and held + need >= net:
                raise NoRoom(
                    f"the process held {held:,.0f} MB and the incomplete factors of {self.size:,} unknowns take up to {need:,.0f} MB more, "
                    f"past the limit of {net:,.0f} MB"
                )
        began = time.perf_counter()
        matrix = sp.csc_matrix((system.value, (system.row, system.col)), shape=(self.size, self.size))
        self.matrix = matrix.tocsr()
        self.factors = sla.spilu(matrix, drop_tol=ILU_DROP if drop is None else drop, fill_factor=fill)
        self.seconds = time.perf_counter() - began
        self.entries = int(self.factors.L.nnz + self.factors.U.nnz)
        self.iterations = 0
        self.stagnated = False

    def _matvec(self, u: np.ndarray) -> np.ndarray:
        return self.matrix @ self.factors.solve(u)

    def solve(self, b: np.ndarray, tol: float) -> np.ndarray:
        """`x` for `x = b + T x`, BiCGSTAB aiming at the relative residual `tol` of the preconditioned system (a stop rule, not a judge)."""
        from ._packed_linear import bicgstab

        rhs = np.zeros(self.size)
        rhs[: self.n] = self.scale * b
        with np.errstate(all="ignore"):
            u, _, iterations, stagnated = bicgstab(self._matvec, rhs, np.zeros(self.size), tol, self.max_iter)
            self.iterations += iterations
            self.stagnated = self.stagnated or stagnated
            z = self.factors.solve(u)
        return z[: self.n] if np.all(np.isfinite(z)) else np.full(self.n, math.nan)

