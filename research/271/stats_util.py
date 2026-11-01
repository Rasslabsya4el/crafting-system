"""Small statistics helpers for ticket #271 (no scipy: the project depends on numpy only)."""
from __future__ import annotations

import math

import numpy as np


def _gamma_q(a: float, x: float) -> float:
    """Regularised upper incomplete gamma Q(a, x) (series for x < a + 1, continued fraction otherwise)."""
    if x <= 0:
        return 1.0
    gln = math.lgamma(a)
    if x < a + 1:
        term = total = 1.0 / a
        n = a
        while True:
            n += 1
            term *= x / n
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return 1.0 - total * math.exp(-x + a * math.log(x) - gln)
    b = x + 1 - a
    c = 1e300
    d = 1 / b
    h = d
    for i in range(1, 100000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def chi2_sf(x: float, df: float) -> float:
    """P(chi-square with `df` degrees of freedom > x)."""
    return _gamma_q(df / 2.0, x / 2.0)


def normal_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2))


def quadratic_form_test(observed: np.ndarray, expected: np.ndarray, covariance: np.ndarray) -> tuple[float, int, float]:
    """(O - E)' pinv(Cov) (O - E) with its degrees of freedom (the rank of Cov) and p-value."""
    diff = observed - expected
    rank = int(np.linalg.matrix_rank(covariance, tol=1e-9))
    stat = float(diff @ np.linalg.pinv(covariance, rcond=1e-10) @ diff)
    return stat, rank, chi2_sf(stat, rank)
