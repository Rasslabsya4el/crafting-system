"""What `simulate` returns."""

from dataclasses import dataclass

from ._estimate import SampledEstimate, cvar, quantile


def _check_level(name: str, level: float) -> None:
    """Raise ValueError unless `level` is a number strictly between 0 and 1; `name` says which estimator asked."""
    if isinstance(level, bool) or not isinstance(level, (int, float)) or not 0.0 < level < 1.0:
        raise ValueError(f"{name} level must be strictly between 0 and 1, got {level!r}")


@dataclass(frozen=True, slots=True)
class SimulationReport:
    """The outcome of `runs` simulated runs of one policy.

    Every run ends in exactly one of three ways: the goal was reached (`successes`), the policy
    returned None on an item that is not a goal (`stopped`) or the run hit `max_steps` (`unfinished`,
    a censored run: it might have succeeded later). So `successes + stopped + unfinished == runs`.

    * `success_rate`: the share of runs that reached the goal, with its Wilson score interval at
      `confidence`. Its `standard_error` is that of the Wilson-centred share, so it is above 0 even
      when every run succeeded.
    * `cost`: the mean over ALL runs of the total paid until the run ended, `start_cost` included,
      whatever the ending, with standard error (sample sd over sqrt(runs)) and mean -+ z standard
      errors. It equals the expected total cost of reaching the goal only when the success rate is
      1 (a proper policy that never stops or gets cut off). Otherwise it is the mean cost paid
      including the failed runs, which is what the policy costs the one who follows it.
    * `cost_of_successes`: the same, over the successful runs only; None when fewer than 2 succeeded.
    * `mean_steps`: the mean number of steps taken per run.
    * `costs`: the total of every run, in run order; `quantile(level)` reads it. For a policy whose steps consume
      other items (ADR-0022) a run's total holds the cost of its nested runs, and `mean_steps` counts their clicks.
    * `nested_runs`: how many nested runs all the runs started (0 for a policy with no inputs);
      `mean_nested_runs` is that per run, the simulated count of donors that `risk` reports as `input_runs`.
    * `cvar(level)` is the mean of the worst share (1 - level) of `costs`, the upper tail.

    Every interval is a normal approximation (Wilson for the rate): good for thousands of runs, not
    for a handful.
    """

    runs: int
    successes: int
    stopped: int
    unfinished: int
    success_rate: SampledEstimate
    cost: SampledEstimate
    cost_of_successes: SampledEstimate | None
    mean_steps: float
    confidence: float
    costs: tuple[float, ...]
    nested_runs: int = 0

    @property
    def mean_nested_runs(self) -> float:
        """The mean number of nested runs started per run."""
        return self.nested_runs / self.runs

    def quantile(self, level: float) -> SampledEstimate:
        """The empirical quantile of `costs` at `level` (strictly between 0 and 1).

        `value` is the smallest total with at least `level` of the runs at or below it. `low` and
        `high` are the order-statistic bracket at `confidence`: the count of runs at or below the
        true quantile is binomial, and its normal approximation gives the ranks, held inside the
        sample. `standard_error` is the bracket's half width over z, an approximation. It is the
        quantile of the cost paid by all runs, failed ones included.
        """
        _check_level("quantile", level)
        return quantile(self.costs, level, self.confidence)

    def cvar(self, level: float) -> SampledEstimate:
        """The conditional value at risk of `costs` at `level` (strictly between 0 and 1).

        It is the mean of the worst `1 - level` share of the runs, so at least `quantile(level)`. The
        interval is a normal approximation (see `cvar` in `_estimate`).
        """
        _check_level("cvar", level)
        return cvar(self.costs, level, self.confidence)
