"""What `evaluate` returns."""

from collections.abc import Mapping
from dataclasses import dataclass, field
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

    `free_allowance` and `free_tail` are for a policy with free actions counted apart from the grid (ticket #349, `_free`): the free
    actions pay at most `free_allowance` altogether except with probability `free_tail`, and the quantile and CVaR intervals already
    contain it. Both are 0.0 when no action was free, and are not part of the `repr`, so a report without free actions reads as before.
    """

    step: float
    exact: bool
    bins: int
    unresolved_mass: float
    rounding: float
    free_allowance: float = field(default=0.0, repr=False)
    free_tail: float = field(default=0.0, repr=False)


@dataclass(frozen=True, slots=True)
class RiskReport:
    """Risk metrics of the total cost C of a fixed policy; see `evaluate` for what each interval certifies.

    `input_runs` is for a policy with `extra_inputs` and a finite mean: the expected number of runs
    started at each input state (how many donors of each kind the policy builds); empty otherwise.
    """

    success_probability: Estimate
    mean: Estimate
    variance: Estimate
    quantiles: Mapping[float, Estimate]
    cvar: Estimate
    cvar_level: float
    grid: GridInfo
    input_runs: Mapping = field(default_factory=dict)

    @property
    def p50(self) -> Estimate:
        return self.quantiles[0.5]

    @property
    def p90(self) -> Estimate:
        return self.quantiles[0.9]
