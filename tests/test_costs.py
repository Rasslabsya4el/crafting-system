"""Hand-computed acceptance cases from docs/specs/2026-09-21-loop-costs.md."""

from __future__ import annotations

import math

import pytest

from craftoracle.costs import (
    chain_cost,
    compound_geometric_cost,
    geometric_cdf,
    geometric_cost,
    geometric_quantile,
)


def test_geometric_cost_acceptance_cases() -> None:
    half = geometric_cost(0.5, 2)
    assert half.expected_attempts == 2
    assert half.expected_cost == 4
    assert half.attempts_p90 == 4
    assert half.cost_p90 == 8

    sixth = geometric_cost(1 / 6, 2)
    assert sixth.expected_attempts == 6
    assert sixth.expected_cost == 12
    assert sixth.attempts_p90 == 13
    assert sixth.cost_p90 == 26

    reset = geometric_cost(0.5, 2, reset_cost=3, setup_cost=7)
    assert reset.expected_cost == 14
    assert reset.cost_p90 == 24

    certain = geometric_cost(1, 2, reset_cost=3, setup_cost=7)
    assert certain.expected_attempts == 1
    assert certain.expected_cost == certain.cost_p90 == 9


def test_geometric_quantile_boundaries_and_unreachable() -> None:
    assert geometric_quantile(0.1) == 22
    assert geometric_cdf(21, 0.1) < 0.9 <= geometric_cdf(22, 0.1)
    assert geometric_cdf(0, 0.5) == 0
    assert geometric_cdf(-3, 0.5) == 0
    assert geometric_cdf(1, 1) == 1
    assert math.isfinite(geometric_quantile(1e-9))
    assert geometric_quantile(0) == math.inf

    with pytest.raises(ValueError):
        geometric_cdf(True, 0.5)
    with pytest.raises(ValueError):
        geometric_quantile(0.5, 1)

    unreachable = geometric_cost(0, 0)
    assert math.isinf(unreachable.expected_attempts)
    assert math.isinf(unreachable.expected_cost)
    assert math.isinf(unreachable.cost_p90)


@pytest.mark.parametrize("value", [-0.1, 1.1, math.nan, True])
def test_invalid_probability_is_rejected(value) -> None:
    with pytest.raises(ValueError):
        geometric_cost(value, 1)


@pytest.mark.parametrize("value", [True, math.nan, math.inf, -1])
def test_invalid_cost_is_rejected(value) -> None:
    with pytest.raises(ValueError):
        geometric_cost(0.5, value)


def test_chain_uses_exact_joint_quantile_not_sum_of_marginals() -> None:
    unit = chain_cost([(0.5, 1, 0, 0), (0.5, 1, 0, 0)])
    assert unit.expected_cost == 4
    assert unit.cost_p90 == 7

    doubled = chain_cost([(0.5, 2, 0, 0), (0.5, 2, 0, 0)])
    assert doubled.expected_cost == 8
    assert doubled.cost_p90 == 14

    quarters = chain_cost([(0.5, 0.25, 0, 0), (0.5, 0.25, 0, 0)])
    assert quarters.expected_cost == 1
    assert quarters.cost_p90 == 1.75

    deterministic = chain_cost([(0.5, 1, 0, 0), (0.5, 1, 0, 0), (1, 3, 0, 0)])
    assert deterministic.expected_cost == 7
    assert deterministic.cost_p90 == 10


def test_chain_empty_and_unreachable() -> None:
    empty = chain_cost([])
    assert empty.expected_cost == empty.cost_p90 == 0

    unreachable = chain_cost([(1, 3, 0, 0), (0, 0, 0, 0)])
    assert math.isinf(unreachable.expected_cost)
    assert math.isinf(unreachable.cost_p90)

    with pytest.raises(ValueError):
        chain_cost([(0.5, 1, 0, 0), (0, -1, 0, 0)])


def test_compound_geometric_cost_acceptance_pmf_and_quantile() -> None:
    result = compound_geometric_cost(0.5, [(1, 1), (2, 1)])
    assert result.expected_attempts == 2
    assert result.expected_cost == 3
    assert result.cost_p90 == 6

    constant = compound_geometric_cost(0.5, [(2, 1)])
    assert constant.expected_cost == 4
    assert constant.cost_p90 == 8

    with pytest.raises(ValueError):
        compound_geometric_cost(0.5, [(1, 0)])
