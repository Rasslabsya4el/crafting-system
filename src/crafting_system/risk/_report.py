"""What `evaluate` returns."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import NamedTuple


class Estimate(NamedTuple):
    """A number with a certified interval: `low <= value <= high` (ends may be `math.inf`)."""

    value: float
    low: float
    high: float


@dataclass(frozen=True, slots=True)
class GridInfo:
    """How the cost distribution was computed.

    `step` is the grid step in cost units (0.0 when no grid was needed). `exact` says every cost is
    a whole multiple of the step, so the grid distribution is the true one. `bins` is how far the
    DP ran, `unresolved_mass` the probability still in flight when it stopped, and `rounding` the
    probability allowance used for float rounding.
    """

    step: float
    exact: bool
    bins: int
    unresolved_mass: float
    rounding: float


@dataclass(frozen=True, slots=True)
class RiskReport:
    """Risk metrics of the total cost C of a fixed policy; see `evaluate` for what each interval certifies."""

    success_probability: Estimate
    mean: Estimate
    variance: Estimate
    quantiles: Mapping[float, Estimate]
    cvar: Estimate
    cvar_level: float
    grid: GridInfo

    @property
    def p50(self) -> Estimate:
        return self.quantiles[0.5]

    @property
    def p90(self) -> Estimate:
        return self.quantiles[0.9]
