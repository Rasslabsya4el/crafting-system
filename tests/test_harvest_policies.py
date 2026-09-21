"""Known answers for the sourced protected-suffix renewal cost law."""

from __future__ import annotations

import math

import pytest

from craftoracle.harvest_policies import estimate_renewal_cost_p90, renewal_metrics


def test_renewal_synthetic_exact_means_and_attempts() -> None:
    first = renewal_metrics(.5, 5, .25, .25, 2)
    assert first.preparation_cost == pytest.approx(10)
    assert first.mean_cost == pytest.approx(28)
    assert first.reforge_attempts == pytest.approx(4)
    assert first.preparations == pytest.approx(2)
    assert first.essence_attempts == pytest.approx(4)

    assert renewal_metrics(.5, 5, .25, 0, 2).mean_cost == pytest.approx(18)
    assert renewal_metrics(.5, 5, .25, .25, 2, base_cost=7).mean_cost == pytest.approx(35)
    assert renewal_metrics(.5, 5, 1, 0, 2).mean_cost == pytest.approx(12)


def test_renewal_p90_is_seeded_and_has_explicit_dkw_metadata() -> None:
    first = estimate_renewal_cost_p90(.5, 5, .25, .25, 2)
    second = estimate_renewal_cost_p90(.5, 5, .25, .25, 2)
    assert first == second
    assert first.samples == 50_000
    assert first.seed == 20260921
    assert first.confidence == .99
    assert first.interval_lower <= first.p90 <= first.interval_upper
    assert first.dkw_epsilon < .1
    # The exact synthetic mean is 28.  Six empirical standard errors is a
    # deliberately loose, fixed-seed regression bound rather than a claim
    # that a percentile has no sampling uncertainty.
    assert abs(first.sample_mean - 28) <= 6 * first.sample_standard_error


def test_small_fixture_p90_cdf_is_checked_by_independent_bounded_enumeration() -> None:
    # p=.5, b=.25, prep=.5, essence=5, reforge=2.  This does not call the
    # sampler: it enumerates K, R, and J from the renewal law directly.
    masses: dict[int, float] = {}
    for k in range(1, 40):
        k_mass = .5**k
        for resets in range(k):
            reset_mass = math.comb(k - 1, resets) * .5 ** (k - 1)
            preparations = resets + 1
            for essence_attempts in range(preparations, 120):
                failures = essence_attempts - preparations
                j_mass = math.comb(failures + preparations - 1, failures) * .5 ** (failures + preparations)
                cost = k * 2 + essence_attempts * 5
                masses[cost] = masses.get(cost, 0) + k_mass * reset_mass * j_mass

    cumulative = 0.0
    exact_p90 = 0
    for cost, mass in sorted(masses.items()):
        cumulative += mass
        if cumulative >= .9:
            exact_p90 = cost
            break
    assert exact_p90 == 37
    assert sum(mass for cost, mass in masses.items() if cost < exact_p90) < .9
    assert sum(mass for cost, mass in masses.items() if cost <= exact_p90) >= .9
    estimate = estimate_renewal_cost_p90(.5, 5, .5, .25, 2)
    assert estimate.p90 == exact_p90


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"preparation_p": 0}, "preparation_p"),
        ({"p": 0}, "p"),
        ({"b": .8}, "b"),
        ({"samples": 1}, "samples"),
    ],
)
def test_renewal_rejects_invalid_inputs(kwargs: dict[str, object], message: str) -> None:
    arguments: dict[str, object] = {
        "preparation_p": .5,
        "essence_price": 5,
        "p": .25,
        "b": .25,
        "reforge_cost": 2,
    }
    arguments.update(kwargs)
    with pytest.raises(ValueError, match=message):
        estimate_renewal_cost_p90(**arguments)  # type: ignore[arg-type]
