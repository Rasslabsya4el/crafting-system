"""Chains of loops: the exact cost distribution is a convolution of geometric distributions.

Two loops in a row (state A, then state B) have independent geometric counts, so the oracle is the
`Fraction` convolution of the two geometric pmfs, each cut where the remaining mass is below 1e-15,
which moves a quantile or CVaR by less than 1e-12 relative at the levels used here.
"""

from fractions import Fraction

import pytest
from risk_support import (
    convolve,
    decimal,
    geometric_moments,
    geometric_pmf,
    is_goal,
    pmf_cvar,
    pmf_quantile,
)

from crafting_system.risk import evaluate
from crafting_system.solver import Action

TAIL = Fraction(1, 10**15)
LEVELS = (0.25, 0.5, 0.9, 0.97)

# (cost of A, weights A->B and A->A, cost of B, weights B->goal and B->B)
CHAINS = [
    pytest.param(2.0, (1, 2), 3.0, (1, 3), id="integer-costs"),
    pytest.param(0.5, (2, 1), 1.5, (1, 4), id="half-steps"),
    pytest.param(0.7, (1, 1), 0.7, (1, 1), id="equal-loops"),
]


def two_loops(c1, ab, c2, bg):
    return {
        "A": Action("a", c1, (("B", ab[0]), ("A", ab[1]))),
        "B": Action("b", c2, (("goal", bg[0]), ("B", bg[1]))),
    }


@pytest.mark.parametrize(("c1", "ab", "c2", "bg"), CHAINS)
def test_two_loops_match_the_convolution_oracle(c1, ab, c2, bg):
    pa, pb = Fraction(ab[0], sum(ab)), Fraction(bg[0], sum(bg))
    pmf = convolve(geometric_pmf(pa, Fraction(c1), TAIL), geometric_pmf(pb, Fraction(c2), TAIL))
    mean_a, var_a = geometric_moments(pa, Fraction(c1))
    mean_b, var_b = geometric_moments(pb, Fraction(c2))

    report = evaluate(two_loops(c1, ab, c2, bg), "A", is_goal, quantile_levels=LEVELS, cvar_level=0.9)

    assert report.grid.exact
    assert report.mean.low <= mean_a + mean_b <= report.mean.high
    assert report.variance.low <= var_a + var_b <= report.variance.high
    assert report.variance.value == pytest.approx(float(var_a + var_b), rel=1e-8)
    for level in LEVELS:
        truth = float(pmf_quantile(pmf, decimal(level)))
        assert report.quantiles[level].low == pytest.approx(truth, rel=1e-9)
        assert report.quantiles[level].high == pytest.approx(truth, rel=1e-9)
    truth = float(pmf_cvar(pmf, decimal(0.9)))
    assert report.cvar.low <= truth <= report.cvar.high
    assert report.cvar.value == pytest.approx(truth, rel=1e-8)
