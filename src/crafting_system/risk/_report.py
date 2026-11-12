"""What `evaluate` returns."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import NamedTuple


class Estimate(NamedTuple):
    """A number with a certified interval: `low <= value <= high` (ends may be `math.inf`)."""

    value: float
    low: float
    high: float


SUBCRITICAL = "subcritical"
UNDECIDED = "undecided"
UNORDERED = "unordered"
IMPROPER = "improper"
STUCK = "stuck"  # only of `Expected`: the policy can reach a state from which it cannot finish (a stuck state, or a loop with no way out)


@dataclass(frozen=True, slots=True)
class Expected:
    """An expected total of a fixed policy (`policy_mean`, `expected_total`) and, when it is infinite, why (M7, ticket #512).

    `estimate` is the number with its certified interval; `value`, `low` and `high` read it. `cause` is empty when the total is finite, else one
    of `SUBCRITICAL` (the policy starts more runs of its inputs than it finishes), `UNDECIDED` (the arithmetic could not certify the total) or
    `STUCK` (the policy can reach a state from which it cannot finish), the words `GridInfo.cause` uses for `evaluate`'s report.
    """

    estimate: Estimate
    cause: str = ""

    @property
    def value(self) -> float:
        return self.estimate.value

    @property
    def low(self) -> float:
        return self.estimate.low

    @property
    def high(self) -> float:
        return self.estimate.high


@dataclass(frozen=True, slots=True)
class GridInfo:
    """How the cost distribution was computed.

    `step` is the grid step in cost units (0.0 when no grid was needed). `exact` says every cost is
    a whole multiple of the step, so the grid distribution is the true one. `bins` is how far the
    DP ran, `unresolved_mass` the probability still in flight when it stopped, and `rounding` the
    probability allowance used for float rounding.

    `free_allowance` and `free_tail` are for a policy with free actions counted apart from the grid (ticket #349, `_free`): the free
    actions pay at most `free_allowance` altogether except with probability `free_tail`, which is what the quantile intervals are widened by,
    and the CVaR intervals are widened by `free_cvar_allowance` (E[E] / (1 - level), on each side); the intervals already contain them. Both are 0.0 when no action was free, and are not part of the `repr`, so a report without free actions reads as before.

    `cause` is why the quantiles are not computed when the grid is not the reason (M7): `SUBCRITICAL`, the policy starts more runs of its inputs than
    it finishes (`_inputs.NotSubcritical`), so its cost has no finite mean; `UNDECIDED`, the policy has a finite mean the arithmetic could not
    certify to within `_linear.REFUSED_ABOVE` (`_inputs.Undecided`: the chances are so close to 1 that the digits are lost), so no cost is computed;
    `IMPROPER`, a state it reaches cannot finish and its inputs depend on each
    other in a cycle, so no cost is computed; `UNORDERED`, the policy is proper but its inputs depend on each other in a cycle, so there is no order to
    run the distribution in (the mean and the variance are exact). Empty otherwise. `gave_up` holds the words of each faster method that
    reached a size limit and left the work to a slower one (`_gaveup`, C24, C25, C27). Neither is part of the `repr`.
    """

    step: float
    exact: bool
    bins: int
    unresolved_mass: float
    rounding: float
    free_allowance: float = field(default=0.0, repr=False)
    free_tail: float = field(default=0.0, repr=False)
    free_cvar_allowance: float = field(default=0.0, repr=False)
    cause: str = field(default="", repr=False)
    gave_up: tuple[str, ...] = field(default=(), repr=False)


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
