"""`evaluate`: risk metrics of a fixed policy on the absorbing chain it induces.

Let C be the total cost paid until a goal is reached (C = infinity when it never is). The chain,
the states that can finish and the proper case are defined in `_chain`; the mean and variance
come from the solver (`_moments`), the quantiles and CVaR from the budget DP (`_budget`).

Success probability. Exactly 1 when the policy is proper (every reachable state can reach a goal).
Otherwise a bracket from the DP, [absorbed mass, absorbed mass + unresolved mass], whose value is
the low end; it is 0 without a DP when the start itself cannot finish. Mean, variance and CVaR are
infinite whenever the success probability is below 1, and the quantile at a level above the top of
the success bracket is infinite.

Inputs (ADR-0022, `_inputs`, `_nested`). An action with `extra_inputs` pays, on every execution, one
independent run per input copy, started at the input state and run by the same policy to a goal
(so the policy lists the input states too; `is_goal` tells their goals). The chain then also
reaches the input states, a state can finish only if an outcome and every input can, and the cost of
an attempt is a random increment. The mean and the second moment come from the linear systems of
`_inputs` (`(I - M) V = c`, certified by its residual; no certificate means a supercritical policy,
whose cost has no finite mean, and it is reported like an improper one), the expected number of
runs started at each input state (`RiskReport.input_runs`) from a row of `(I - M)^-1`, and the
distribution from the budget DP with each input's pmf convolved in (`_nested`). A policy whose
inputs sit in a cycle with their users (an input edge inside a strongly connected component) has no
such order; its mean and variance are still exact but its quantiles and CVaR are reported
unresolved. A policy without inputs takes the old path unchanged.

The grid. Costs are floats, the DP counts whole bins of a step D. A cost c becomes k_hi =
ceil(c / D) bins on the upper chain and k_lo = floor(c / D) on the lower one; a cost within 1e-12
relative of a multiple of D is that multiple on both. The same trajectory then has
C_lo <= C <= C_hi, so F_hi <= F_C <= F_lo, the quantiles of the two grid chains bracket the true
quantile, and CVaR (monotone under this ordering) is bracketed too. The grid is `exact` when
every cost is a multiple of D; then one chain is run and the answer is the true one. D must not
exceed the smallest cost of a state that can finish, so every k_lo is at least 1.

Choosing D (`resolution=None`). If every cost is a multiple of one unit u (found with
`_chain.exact_unit`) and the DP can cover the horizon in at most `max_bins` units, D = u and the
grid is exact. The horizon is H = mean + 6 sd for a proper policy; for a policy that is not proper
it is 64 c_min, so the unit must let the DP span 64 of the smallest costs (a unit of 1e-12 would
leave 200k bins covering nothing). Otherwise D = min(c_min, max(c_min / 64, H / max_bins)) with
c_min the smallest cost (H = 64 c_min if the policy is not proper, so 200k bins then cover about
3000 c_min): the smallest cost is 64 bins unless the horizon needs coarser. That grid is usually inexact; its interval width is data
driven and reported, and a smaller `resolution` tightens it. An explicit `resolution` is used as
given; one so small that cost / resolution overflows is a `ValueError`.

Work budget (`resolution=None` only). The DP expands one entry per (state, bin) the mass reaches, so
its work is about runs * edges * spread / D, with spread the width over which a state's arrival cost
scatters (6 standard deviations of the total cost for a proper policy, the covered horizon
otherwise) and `runs` 2 on an inexact grid. When that exceeds `work_budget` (default 3e8 entries,
about a minute) the step is raised to the finest one that fits, at most the smallest cost; the
intervals widen to match and stay certified, and the report's `grid.step` says what was used. An
exact unit grid is given up in the same case. A small policy is never touched.
With inputs the DP is the nested one, whose work is about (runs * (starts * states + extra input copies))
* (spread / D)^2 convolution cells (`nested_work`), counted at 1/30 of an entry against the same budget.

Coarse grid (`resolution=None`, a proper policy without inputs; ticket #190). When the highest level asked
certainly lies beyond `max_bins` times the smallest cost (`_coarse.beyond_ordinary_grid`), a step at most the
smallest cost cannot reach it (R13: an Orb of Transmutation at 0.0058 Chaos next to a mean of 6,300). `_coarse.choose_step` then looks for a
step above the smallest cost at which the actions that are visited often are whole multiples: the
lower chain gives an action cheaper than the step 0 bins (the free states are replaced by their exit
distributions, `_fold`), the upper chain 1 bin, and the intervals widen by one step per visit of such
an action (the expected gap is in `_coarse`). The DP is then dense (`_dense`) and runs up to
`max_coarse_bins` bins (default `max_bins`). When no step has an expected gap within a tenth of the
mean, or the chain is too large for the dense DP, the ordinary grid is used as before. The trigger looks at the
highest level asked: when only that level is out of reach, the lower levels come as brackets of the coarse grid too.

Mean of a grid chain, for CVaR. The exact grid uses the solver mean of the real costs. An inexact
grid solves again with the costs k_lo * D and k_hi * D to get the mean of each grid chain, and CVaR
of each chain uses the matching end of its mean interval.

Supported costs. Every cost of a state that can finish lies in [1e-150, 1e150], so the squares in
the second moment stay representable; anything else is a `ValueError`.

Rounding. All bounds hold up to ties within `grid.rounding` in probability (see `_budget`), and a
cost within 1e-12 relative of a multiple of D counts as that multiple. Levels within `rounding`
of 1 cannot be certified at the high end and are reported unresolved (high = inf, even on an exact
grid); a level within `rounding` of 0 gets low = 0 and a high end, with no point claim.

Complexity. Time O(entries * edges), one entry per (bins paid, state) pair that holds mass, and
memory O(entries in flight) plus O(bins) floats for the cumulative distribution (see `_budget`,
numpy-vectorised); one or two solver runs for the moments, and two more for CVaR on an inexact
grid.
"""

import math
from collections.abc import Callable, Mapping, Sequence
from numbers import Integral, Real

from .. import parallel
from ..solver import Action
from . import _inputs, _moments
from ._budget import BudgetRun, run_budget, tail_mean
from ._chain import UNIT_TOLERANCE, Chain, build_chain, exact_unit
from ._coarse import beyond_ordinary_grid, choose_step, expected_visits
from ._dense import fits_dense, run_dense
from ._fold import fold_free
from ._moments import interval, real_costs
from ._nested import nested_work, run_nested
from ._report import Estimate, GridInfo, RiskReport

INFINITE = Estimate(math.inf, math.inf, math.inf)
ZERO = Estimate(0.0, 0.0, 0.0)
HORIZON_SDS = 6.0
MIN_COST = 1e-150  # the second moment squares a cost: outside this range c * c under- or overflows
MAX_COST = 1e150
COVERED_STEPS = 64  # an unproper policy's unit must let the DP cover this many of the smallest costs
FINE_STEPS = 64  # default grid: the smallest cost is at least this many bins unless the horizon needs coarser
WORK_BUDGET = 3e8  # default cap on the DP's expanded entries (about a minute); a larger policy gets a coarser grid
CELLS_PER_ENTRY = 30.0  # the nested DP's work counts convolution cells, each about this much cheaper than an expanded entry
SPREAD_SDS = 6.0  # the arrival cost of a state spreads over about this many standard deviations of the total cost
FREE_BINS = 0.1  # bins charged to a free state when the solver takes the mean of the lower coarse chain (it needs a positive cost; the charge is taken off again)
FREE_SLACK = 1e-6  # relative allowance on the visits of the free states that give that charge back


def evaluate[S](
    policy: Mapping[S, Action[S]],
    start: S,
    is_goal: Callable[[S], bool],
    *,
    resolution: float | None = None,
    quantile_levels: Sequence[float] = (0.5, 0.9),
    cvar_level: float = 0.9,
    tail_mass: float = 1e-9,
    max_bins: int = 200_000,
    work_budget: float = WORK_BUDGET,
    max_coarse_bins: int | None = None,
) -> RiskReport:
    """Risk metrics of the total cost of `policy` from `start`; see the module docstring.

    `policy` maps each state to its action (e.g. `Solution.policy`); a goal is never expanded and a
    reachable non-goal state without an entry is stuck. `quantile_levels` and `cvar_level` lie
    strictly between 0 and 1. The DP stops once the asked levels are certified (proper policy) or
    the probability still in flight is at most `tail_mass`; it never runs past `max_bins` bins and
    reports what was left as `grid.unresolved_mass`. `work_budget` caps the DP's work when `resolution`
    is not given (see the module docstring), and `max_coarse_bins` the most bins of the coarse grid (default `max_bins`).
    Raises `ValueError` for a bad argument or a
    `resolution` above the smallest cost, a `max_bins` so large that a (bin, state) pair no longer fits
    62 bits, and the solver's `ConvergenceError` if a moment solve
    cannot converge.
    """
    levels = tuple(_level(x, "quantile level") for x in quantile_levels)
    cvar_level = _level(cvar_level, "cvar_level")
    if isinstance(tail_mass, bool) or not isinstance(tail_mass, Real) or not 0.0 < tail_mass < 1.0:
        raise ValueError(f"tail_mass must be strictly between 0 and 1, got {tail_mass!r}")
    if isinstance(max_bins, bool) or not isinstance(max_bins, Integral) or max_bins < 1:
        raise ValueError(f"max_bins must be an integer of at least 1, got {max_bins!r}")
    if max_coarse_bins is not None and (
        isinstance(max_coarse_bins, bool) or not isinstance(max_coarse_bins, Integral) or max_coarse_bins < 1
    ):
        raise ValueError(f"max_coarse_bins must be an integer of at least 1, or None, got {max_coarse_bins!r}")
    if isinstance(work_budget, bool) or not isinstance(work_budget, Real) or not work_budget > 0.0:
        raise ValueError(f"work_budget must be a number above zero, got {work_budget!r}")
    try:
        work_budget = float(work_budget)
    except OverflowError:
        work_budget = math.inf
    if resolution is not None and (
        isinstance(resolution, bool)
        or not isinstance(resolution, Real)
        or not (math.isfinite(resolution) and resolution > 0.0)
    ):
        raise ValueError(f"resolution must be finite and above zero, or None, got {resolution!r}")
    for state, chosen in policy.items():
        if not isinstance(chosen, Action):
            raise ValueError(f"policy value for {state!r} must be an Action, got {chosen!r}")

    no_grid = GridInfo(0.0, True, 0, 0.0, 0.0)
    chain = build_chain(policy, start, is_goal)
    if chain.goal[0]:
        return RiskReport(
            Estimate(1.0, 1.0, 1.0), ZERO, ZERO, {x: ZERO for x in levels}, ZERO, cvar_level, no_grid
        )
    if not chain.can_finish[0]:
        return RiskReport(
            ZERO, INFINITE, INFINITE, {x: INFINITE for x in levels}, INFINITE, cvar_level, no_grid
        )

    costs = [chain.action[i].cost for i in chain.finishing_states()]
    c_min = min(costs)
    if c_min < MIN_COST or max(costs) > MAX_COST:
        raise ValueError(
            f"costs must lie in the supported range {MIN_COST:g} to {MAX_COST:g} so that "
            f"their squares stay representable, got {c_min!r} to {max(costs)!r}"
        )
    if resolution is not None and resolution > c_min * (1.0 + UNIT_TOLERANCE):
        raise ValueError(
            f"resolution {resolution!r} exceeds the smallest cost {c_min!r}: a step would "
            "round to zero bins and the budget DP needs every step to cost at least one bin"
        )
    proper = chain.proper
    horizon = None
    spread = COVERED_STEPS * c_min
    if proper:
        try:
            mean, variance, m1 = _mean_and_variance(chain)
        except _inputs.NotSubcritical:  # every state can finish, but the runs need more than they make
            proper = False
        else:
            horizon = m1[0] + HORIZON_SDS * math.sqrt(variance[0])
            spread = SPREAD_SDS * math.sqrt(variance[0])
    if chain.has_inputs and _inputs.branching(chain):
        return _unordered_report(chain, (mean, variance) if proper else None, cvar_level, levels)
    if (
        resolution is None and proper and not chain.has_inputs
        and beyond_ordinary_grid(mean[0], variance[0], max([*levels, cvar_level]), c_min, max_bins)
    ):
        coarse = _coarse_report(
            chain, mean, variance, levels, cvar_level, tail_mass, max_bins if max_coarse_bins is None else max_coarse_bins
        )
        if coarse is not None:
            return coarse
    step = resolution
    if step is None:
        step = _choose_step(costs, c_min, max_bins, horizon, _affordable(chain, spread, work_budget))
    low_bins, high_bins = _bin_costs(chain, step)
    exact = low_bins == high_bins

    target = max([*levels, cvar_level]) if proper else None
    horizon_bins = None if horizon is None else math.ceil(horizon / step)
    if exact:
        low_run = high_run = _run(chain, low_bins, target, tail_mass, max_bins, horizon_bins)
    else:
        low_run, high_run = _both(
            (_run, (chain, low_bins, target, tail_mass, max_bins, horizon_bins), {}),
            (_run, (chain, high_bins, target, tail_mass, max_bins, horizon_bins), {}),
        )
    runs = (low_run,) if exact else (low_run, high_run)

    if proper:
        success = Estimate(1.0, 1.0, 1.0)
        mean_low, mean_high = _chain_means(chain, step, low_bins, high_bins, mean, exact)
        cvar = _cvar(step, cvar_level, low_run, high_run, mean_low, mean_high, mean[0])
        success_high = None
    else:
        absorbed = max(r.absorbed for r in runs)
        success_high = min(1.0, min(r.absorbed + r.unresolved for r in runs))
        success = Estimate(absorbed, absorbed, max(absorbed, success_high))
        mean = variance = cvar = INFINITE
    quantiles = {x: _quantile(x, step, low_run, high_run, success_high) for x in levels}
    grid = GridInfo(
        step, exact, max(r.bins for r in runs), max(r.unresolved for r in runs), max(r.delta for r in runs)
    )
    return RiskReport(
        success,
        Estimate(*mean),
        Estimate(*variance),
        quantiles,
        Estimate(*cvar),
        cvar_level,
        grid,
        _input_runs(chain) if proper and chain.has_inputs else {},
    )


def _coarse_report(
    chain: Chain,
    mean: tuple[float, float, float],
    variance: tuple[float, float, float],
    levels: Sequence[float],
    cvar_level: float,
    tail_mass: float,
    max_bins: int,
) -> RiskReport | None:
    """The report on the coarse grid of `_coarse`, or `None` when the ordinary grid has to do (see the module docstring)."""
    target = max([*levels, cvar_level])
    chosen = choose_step(chain, mean[0], variance[0], target, max_bins)
    if chosen is None:
        return None
    step = chosen[0]
    low_bins, high_bins = _bin_costs(chain, step)
    folded = fold_free(chain, low_bins)
    if folded is None or not fits_dense(folded.chain, low_bins, max_bins) or not fits_dense(chain, high_bins, max_bins):
        return None
    low_run, high_run = _both(
        (run_dense, (folded.chain, low_bins), dict(
            initial=folded.initial, goal_mass=folded.goal_mass, target=target, tail_mass=tail_mass, max_bins=max_bins)),
        (run_dense, (chain, high_bins), dict(initial=((0, 1.0),), target=target, tail_mass=tail_mass, max_bins=max_bins)),
    )  # fmt: skip
    mean_low, mean_high = _coarse_means(chain, step, low_bins, high_bins)
    cvar = _cvar(step, cvar_level, low_run, high_run, mean_low, mean_high, mean[0])
    quantiles = {x: _quantile(x, step, low_run, high_run, None) for x in levels}
    runs = (low_run, high_run)
    grid = GridInfo(
        step, False, max(r.bins for r in runs), max(r.unresolved for r in runs), max(r.delta for r in runs)
    )
    return RiskReport(
        Estimate(1.0, 1.0, 1.0), Estimate(*mean), Estimate(*variance), quantiles, Estimate(*cvar), cvar_level, grid
    )


def _coarse_means(chain: Chain, step: float, low_bins: Sequence[int], high_bins: Sequence[int]) -> tuple[float, float]:
    """Mean of the lower and the upper coarse chain, as `(low end for the lower, high end for the upper)`.

    The solver wants positive costs, so a free state is charged `FREE_BINS` bins and the charge is given back from
    the expected visits of the free states (the mean is linear in the costs and the visits do not depend on them).
    """
    states, visits = expected_visits(chain)
    free = math.fsum(v for s, v in zip(states, visits) if low_bins[s] == 0)
    low_mean, low_error = _solve_costs(chain, [max(float(k), FREE_BINS) * step for k in low_bins])
    high_mean, high_error = _solve_costs(chain, [float(k) * step for k in high_bins])
    low = interval(low_mean[0], low_error)[0] - FREE_BINS * step * free * (1.0 + FREE_SLACK)
    return max(low, 0.0), interval(high_mean[0], high_error)[1]


def _mean_and_variance(chain: Chain):
    """Solver moments for a chain without inputs, the linear systems of `_inputs` for one with."""
    return _inputs.mean_and_variance(chain) if chain.has_inputs else _moments.mean_and_variance(chain)


def _solve_costs(chain: Chain, costs: Sequence[float]) -> tuple[list[float], float]:
    return _inputs.solve_costs(chain, costs) if chain.has_inputs else _moments.solve_costs(chain, costs)


def _affordable(chain: Chain, spread: float, work_budget: float) -> float:
    """The finest step whose DP stays within `work_budget`, by the cost model of the DP that will run."""
    finishing = chain.finishing_states()
    if not chain.has_inputs:
        edges = sum(len(chain.succ[i]) for i in finishing)
        return 2.0 * edges * spread / work_budget
    return spread * math.sqrt(2.0 * nested_work(chain, 1) / (CELLS_PER_ENTRY * work_budget))


def _run(
    chain: Chain,
    bins: Sequence[int],
    target: float | None,
    tail_mass: float,
    max_bins: int,
    horizon_bins: int | None,
) -> BudgetRun:
    if chain.has_inputs:
        return run_nested(
            chain, bins, target=target, tail_mass=tail_mass, max_bins=max_bins, horizon=horizon_bins
        )
    return run_budget(chain, bins, target=target, tail_mass=tail_mass, max_bins=max_bins)


def _held(jobs: dict) -> dict:
    return jobs


def _call(name: str):
    function, args, kwargs = parallel.context()[name]
    return function(*args, **kwargs)


def _both(low: tuple, high: tuple) -> tuple:
    """The results of the lower and the upper run, each `(function, args, kwargs)`.

    The two runs share nothing and each is a function of its own arguments, so they run side by side in a pool of two
    when `CRAFTING_WORKERS` is above 1 and workers can be forked (ticket #250); the pair is the same either way. A spawned
    worker would be sent the chain by pickle twice, which costs more than a second run saves.
    """
    if parallel.worker_count() < 2 or not parallel.can_inherit():
        return tuple(function(*args, **kwargs) for function, args, kwargs in (low, high))
    with parallel.WorkerPool(_held, ({"low": low, "high": high},), workers=2) as pool:
        found = pool.map(_call, ["low", "high"], chunk=1)
    return found[0], found[1]


def _input_runs(chain: Chain) -> dict:
    values, error = _inputs.solve_costs(chain, real_costs(chain))
    uses = _inputs.expected_uses(chain, values, error)
    return {chain.states[y]: Estimate(*u) for y, u in uses.items()}


def _unordered_report(chain: Chain, moments, cvar_level: float, levels: Sequence[float]) -> RiskReport:
    """The report for inputs in a cycle with their users: exact moments, quantiles and CVaR unresolved."""
    unresolved = GridInfo(0.0, False, 0, 1.0, 0.0)
    first = chain.action[0].cost  # every run pays the first action at least
    quantiles = {x: Estimate(math.inf, first, math.inf) for x in levels}
    if moments is None:
        return RiskReport(Estimate(0.0, 0.0, 1.0), INFINITE, INFINITE, quantiles, INFINITE, cvar_level, unresolved)
    mean, variance = moments
    cvar = Estimate(math.inf, mean[1], math.inf)
    return RiskReport(
        Estimate(1.0, 1.0, 1.0),
        Estimate(*mean),
        Estimate(*variance),
        quantiles,
        cvar,
        cvar_level,
        unresolved,
        _input_runs(chain),
    )


def _level(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not 0.0 < value < 1.0:
        raise ValueError(f"{name} must be a number strictly between 0 and 1, got {value!r}")
    return float(value)


def _choose_step(
    costs: Sequence[float], c_min: float, max_bins: int, horizon: float | None, affordable: float
) -> float:
    """The grid step; `affordable` is the finest step whose DP stays within the work budget."""
    unit = exact_unit(costs)
    horizon = COVERED_STEPS * c_min if horizon is None else horizon
    if unit is not None and horizon / unit <= max_bins and unit >= affordable:
        return unit
    return min(c_min, max(c_min / FINE_STEPS, horizon / max_bins, affordable))


def _cost_bins(cost: float, step: float) -> tuple[int, int]:
    ratio = cost / step
    if not math.isfinite(ratio):
        raise ValueError(
            f"resolution {step!r} is too small for the cost {cost!r}: cost / resolution must be finite"
        )
    nearest = round(ratio)
    if nearest >= 1 and abs(ratio - nearest) <= UNIT_TOLERANCE * ratio:
        return nearest, nearest
    return math.floor(ratio), math.ceil(ratio)


def _bin_costs(chain: Chain, step: float) -> tuple[list[int], list[int]]:
    low, high = [0] * len(chain.states), [0] * len(chain.states)
    for i in chain.finishing_states():
        low[i], high[i] = _cost_bins(chain.action[i].cost, step)
    return low, high


def _quantile(
    level: float, step: float, low_run: BudgetRun, high_run: BudgetRun, success_high: float | None
) -> Estimate:
    delta = low_run.delta
    if success_high is not None and level > success_high + delta:
        return INFINITE
    k_low = low_run.first_reaching(level - delta)
    low = (low_run.bins if k_low is None else k_low) * step
    if low_run is high_run and 0.0 < level - delta and level + delta < 1.0:
        if k_low is None:
            return Estimate(math.inf, low, math.inf)
        return Estimate(low, low, low)
    # an inexact grid, or a level too close to 0 or 1 for a tie-tolerant point answer
    k_high = high_run.first_reaching(level + high_run.delta) if level + high_run.delta < 1.0 else None
    if k_high is None:
        return Estimate(math.inf, low, math.inf)
    high = k_high * step
    return Estimate((low + high) / 2.0, low, high)


def _chain_means(
    chain: Chain,
    step: float,
    low_bins: Sequence[int],
    high_bins: Sequence[int],
    mean: tuple[float, float, float],
    exact: bool,
) -> tuple[float, float]:
    """Mean of the lower and the upper grid chain, as `(low end for the lower, high end for the upper)`."""
    if exact:
        return mean[1], mean[2]
    low_mean, low_error = _solve_costs(chain, [float(k) * step for k in low_bins])
    high_mean, high_error = _solve_costs(chain, [float(k) * step for k in high_bins])
    return interval(low_mean[0], low_error)[0], interval(high_mean[0], high_error)[1]


def _cvar(
    step: float,
    level: float,
    low_run: BudgetRun,
    high_run: BudgetRun,
    mean_low: float,
    mean_high: float,
    mean_value: float,
) -> tuple[float, float, float]:
    below = tail_mean(low_run, step, level, mean_low)
    if below is None:
        return math.inf, low_run.bins * step, math.inf
    low = max(below[0] - below[2], below[1])
    above = tail_mean(high_run, step, level, mean_high)
    if above is None:
        return math.inf, low, math.inf
    high = above[0] + above[2]
    centre = tail_mean(low_run, step, level, mean_value)[0] if low_run is high_run else (low + high) / 2.0
    return min(max(centre, low), high), low, high
