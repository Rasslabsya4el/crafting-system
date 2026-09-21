"""Finite conditional draw schedules and outcome-correlated renewal costs.

Sources: ``docs/design/parameter-search.md`` (2026-09-21), accepted D14
draw semantics.  The inputs are mathematical policy parameters, not game
facts.  The finite schedule deliberately keeps the private group-profile
state from :mod:`craftoracle.distributions` until a gate absorbs an outcome.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
import math
from numbers import Real

import numpy as np

from craftoracle import distributions as _distributions
from craftoracle.distributions import OutcomeClass


CostAtoms = Iterable[tuple[float, float]]
Predicate = Callable[[OutcomeClass], bool]


@dataclass(frozen=True)
class ScheduleEvaluation:
    """Unconditional terminal distributions for each zero-based schedule stage."""

    success_by_stage: tuple[dict[OutcomeClass, float], ...]
    failure_by_stage: tuple[dict[OutcomeClass, float], ...]
    stage_reach_probabilities: tuple[float, ...]
    peak_live_states: int

    @property
    def success_probability(self) -> float:
        return math.fsum(
            mass for distribution in self.success_by_stage for mass in distribution.values()
        )

    @property
    def failure_probability(self) -> float:
        return math.fsum(
            mass for distribution in self.failure_by_stage for mass in distribution.values()
        )


@dataclass(frozen=True)
class AttemptCostAtoms:
    """Conditional cost atoms derived from a schedule's terminal stage masses."""

    success_probability: float
    success_atoms: tuple[tuple[float, float], ...]
    failure_atoms: tuple[tuple[float, float], ...]
    unconditional_attempt_mean: float


@dataclass(frozen=True)
class CorrelatedAttemptMetrics:
    """Exact expectation for a retried attempt with outcome-correlated cost."""

    success_probability: float
    mean_attempt_cost: float
    mean_cost: float


@dataclass(frozen=True)
class CorrelatedAttemptEstimate:
    """Seeded empirical p90 with a DKW probability-space confidence interval."""

    success_probability: float
    mean_attempt_cost: float
    mean_cost: float
    p90: float
    interval_lower: float
    interval_upper: float
    samples: int
    confidence: float
    dkw_epsilon: float
    sample_mean: float
    sample_standard_error: float
    method: str = "sampled-correlated-attempt-geometric-multinomial-dkw"


@dataclass(frozen=True)
class ProtectedCycleMetrics:
    """Exact moments for the two-state preparation/protected-cycle renewal law."""

    mean_cost: float
    expected_preparations: float
    expected_cycles: float
    early_completion_probability: float
    via_cycle_probability: float
    unconditional_cycle_cost: float


@dataclass(frozen=True)
class ProtectedCycleEstimate:
    """Exact protected-cycle metrics plus a seeded N/H/J/K-law p90 estimate."""

    mean_cost: float
    expected_preparations: float
    expected_cycles: float
    early_completion_probability: float
    via_cycle_probability: float
    unconditional_cycle_cost: float
    p90: float
    interval_lower: float
    interval_upper: float
    samples: int
    confidence: float
    dkw_epsilon: float
    sample_mean: float
    sample_standard_error: float
    method: str = "sampled-protected-cycle-N-H-J-K-renewal-dkw"


def evaluate_grouped_schedule(
    entries: Iterable[object],
    labels: Mapping[str, str] | None,
    stages: Sequence[tuple[int, int, int]],
    continue_predicates: Sequence[Predicate | None] | None = None,
    target_predicate: Predicate | None = None,
    *,
    early_stop: bool = True,
    initial_prefixes: int = 0,
    initial_suffixes: int = 0,
    initial_labels: Iterable[str] = (),
    blocked_groups: Iterable[str] = (),
) -> ScheduleEvaluation:
    """Evaluate a finite grouped draw schedule without projecting live states.

    Each stage tuple is ``(draws, prefix_cap, suffix_cap)`` and caps can only
    grow.  A predicate sees an :class:`OutcomeClass` projection solely to
    decide whether that state can continue.  The retained state still includes
    selected group-profile counts, so equal projected labels with unequal
    future group weights never merge.  An exhausted non-final stage is the
    actual terminal state and checks the target even with ``early_stop=False``.
    """
    parsed_stages = _parse_stages(stages)
    parsed_labels = _distributions._validate_labels(labels)
    predicates = _parse_continue_predicates(continue_predicates, len(parsed_stages))
    _require_predicate(target_predicate, "target_predicate")
    if not isinstance(early_stop, bool):
        raise ValueError("early_stop must be a boolean")

    entry_rows = tuple(entries)
    if not entry_rows:
        raise ValueError("entries must not be empty")
    first_prefix_cap, first_suffix_cap = parsed_stages[0][1:]
    _, _, initial_prefixes, initial_suffixes, fixed_labels = _distributions._validate_initial(
        first_prefix_cap,
        first_suffix_cap,
        initial_prefixes,
        initial_suffixes,
        initial_labels,
    )
    profiles = _distributions._profiles(entry_rows, parsed_labels, blocked_groups)

    states: dict[object, float] = {
        _distributions._State(
            initial_prefixes, initial_suffixes, fixed_labels, (0,) * len(profiles)
        ): 1.0
    }
    success: list[dict[OutcomeClass, float]] = []
    failure: list[dict[OutcomeClass, float]] = []
    reaches: list[float] = []
    peak_live_states = len(states)

    for stage_index, (draws, prefix_cap, suffix_cap) in enumerate(parsed_stages):
        reaches.append(math.fsum(states.values()))
        for _ in range(draws):
            states = _distributions._advance(states, profiles, prefix_cap, suffix_cap)
            peak_live_states = max(peak_live_states, len(states))

        stage_success: dict[OutcomeClass, float] = defaultdict(float)
        stage_failure: dict[OutcomeClass, float] = defaultdict(float)
        continuing: dict[object, float] = defaultdict(float)
        final_stage = stage_index == len(parsed_stages) - 1
        predicate = predicates[stage_index]
        for state, mass in states.items():
            outcome = OutcomeClass(state.labels, state.prefixes, state.suffixes)
            can_draw_later = not final_stage and _can_draw_in_later_stage(
                state, profiles, parsed_stages[stage_index + 1 :]
            )
            succeeds_here = (early_stop or final_stage or not can_draw_later) and _run_predicate(
                target_predicate, outcome, "target_predicate"
            )
            if succeeds_here:
                stage_success[outcome] += mass
            elif final_stage:
                stage_failure[outcome] += mass
            elif predicate is not None and not _run_predicate(
                predicate, outcome, f"continue_predicates[{stage_index}]"
            ):
                stage_failure[outcome] += mass
            elif not can_draw_later:
                # No future draw can change this non-target state, so it must
                # absorb here and cannot be charged any later action.
                stage_failure[outcome] += mass
            else:
                continuing[state] += mass
        success.append(dict(stage_success))
        failure.append(dict(stage_failure))
        states = dict(continuing)
        peak_live_states = max(peak_live_states, len(states))

    result = ScheduleEvaluation(tuple(success), tuple(failure), tuple(reaches), peak_live_states)
    if not math.isclose(
        result.success_probability + result.failure_probability,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-10,
    ):
        raise AssertionError("schedule terminal mass did not sum to one")
    return result


def terminal_cost_atoms(
    schedule: ScheduleEvaluation, stage_costs: Sequence[float]
) -> AttemptCostAtoms:
    """Convert terminal stage distributions into conditional success/failure atoms."""
    if not isinstance(schedule, ScheduleEvaluation):
        raise ValueError("schedule must be a ScheduleEvaluation")
    costs = tuple(_nonnegative(value, "stage_cost") for value in stage_costs)
    stage_count = len(schedule.success_by_stage)
    if len(schedule.failure_by_stage) != stage_count or len(costs) != stage_count:
        raise ValueError("stage_costs must contain one cost per schedule stage")
    cumulative_costs: list[float] = []
    current = 0.0
    for cost in costs:
        current += cost
        _require_finite_nonnegative((current, "cumulative stage cost"))
        cumulative_costs.append(current)

    success_unconditional: dict[float, float] = defaultdict(float)
    failure_unconditional: dict[float, float] = defaultdict(float)
    for index, cost in enumerate(cumulative_costs):
        success_unconditional[cost] += math.fsum(schedule.success_by_stage[index].values())
        failure_unconditional[cost] += math.fsum(schedule.failure_by_stage[index].values())
    success_probability = math.fsum(success_unconditional.values())
    failure_probability = math.fsum(failure_unconditional.values())
    if not math.isclose(success_probability + failure_probability, 1.0, abs_tol=1e-10):
        raise ValueError("schedule terminal mass must sum to one")
    success_atoms = _conditional_atoms(success_unconditional, success_probability)
    failure_atoms = _conditional_atoms(failure_unconditional, failure_probability)
    mean = math.fsum(
        cost * mass for cost, mass in success_unconditional.items()
    ) + math.fsum(cost * mass for cost, mass in failure_unconditional.items())
    _require_finite_nonnegative((mean, "unconditional_attempt_mean"))
    return AttemptCostAtoms(success_probability, success_atoms, failure_atoms, mean)


def correlated_attempt_metrics(
    success_probability: float,
    success_cost_atoms: CostAtoms,
    failure_cost_atoms: CostAtoms,
    *,
    reset_cost: float = 0,
    setup_cost: float = 0,
) -> CorrelatedAttemptMetrics:
    """Return the exact mean for finite cost atoms correlated with outcome."""
    probability = _probability(success_probability, "success_probability")
    if probability == 0:
        raise ValueError("unreachable: success_probability is zero")
    success_atoms = _weighted_atoms(success_cost_atoms, "success_cost_atoms", required=True)
    failure_atoms = _weighted_atoms(
        failure_cost_atoms, "failure_cost_atoms", required=probability < 1
    )
    reset = _nonnegative(reset_cost, "reset_cost")
    setup = _nonnegative(setup_cost, "setup_cost")
    success_mean = _atom_mean(success_atoms)
    failure_mean = _atom_mean(failure_atoms) if failure_atoms else 0.0
    attempt_mean = probability * success_mean + (1 - probability) * failure_mean
    mean = setup + (attempt_mean + (1 - probability) * reset) / probability
    _require_finite_nonnegative(
        (attempt_mean, "mean_attempt_cost"),
        (mean, "mean_cost"),
    )
    return CorrelatedAttemptMetrics(probability, attempt_mean, mean)


def estimate_correlated_attempt_p90(
    success_probability: float,
    success_cost_atoms: CostAtoms,
    failure_cost_atoms: CostAtoms,
    *,
    reset_cost: float = 0,
    setup_cost: float = 0,
    rng: np.random.Generator,
    samples: int = 50_000,
    confidence: float = 0.99,
) -> CorrelatedAttemptEstimate:
    """Sample correlated retry costs via geometric failures and multinomials."""
    success_rows = _materialize_atoms(success_cost_atoms, "success_cost_atoms")
    failure_rows = _materialize_atoms(failure_cost_atoms, "failure_cost_atoms")
    metrics = correlated_attempt_metrics(
        success_probability,
        success_rows,
        failure_rows,
        reset_cost=reset_cost,
        setup_cost=setup_cost,
    )
    probability = metrics.success_probability
    success_atoms = _weighted_atoms(success_rows, "success_cost_atoms", required=True)
    failure_atoms = _weighted_atoms(
        failure_rows, "failure_cost_atoms", required=probability < 1
    )
    reset = _nonnegative(reset_cost, "reset_cost")
    setup = _nonnegative(setup_cost, "setup_cost")
    trial_count, coverage, epsilon = _sample_contract(rng, samples, confidence)

    _require_sampled_probability(probability, "success_probability")
    attempts = _positive_count_array(
        rng.geometric(probability, size=trial_count), "geometric attempt count"
    )
    failed_counts = attempts - 1
    _nonnegative_count_array(failed_counts, "failed attempt count")
    costs = np.full(trial_count, setup, dtype=float)
    costs += failed_counts * reset
    costs += _sample_failure_totals(rng, failed_counts, failure_atoms)
    costs += _sample_atom_values(rng, success_atoms, trial_count)
    p90, lower, upper, sample_mean, standard_error = _sample_statistics(costs, coverage, epsilon)
    return CorrelatedAttemptEstimate(
        probability,
        metrics.mean_attempt_cost,
        metrics.mean_cost,
        p90,
        lower,
        upper,
        trial_count,
        coverage,
        epsilon,
        sample_mean,
        standard_error,
    )


def protected_cycle_metrics(
    u: float,
    v: float,
    preparation_price: float,
    p: float,
    b: float,
    failed_cycle_cost: float,
    success_cycle_cost_atoms: CostAtoms,
    *,
    base_cost: float = 0,
) -> ProtectedCycleMetrics:
    """Evaluate the documented two-state preparation/protected-cycle law."""
    inputs = _protected_inputs(
        u, v, preparation_price, p, b, failed_cycle_cost, success_cycle_cost_atoms, base_cost
    )
    u_value, v_value, price, success, full_reset, failed, success_atoms, base = inputs
    if v_value == 0:
        mean = base + price / u_value
        preparations = 1 / u_value
        _require_finite_nonnegative(
            (mean, "mean_cost"),
            (preparations, "expected_preparations"),
        )
        return ProtectedCycleMetrics(
            mean,
            preparations,
            0.0,
            1.0,
            0.0,
            0.0,
        )

    terminal_cycle_probability = success + full_reset
    if success == 0 and full_reset == 0:
        raise ValueError("unreachable: prepared cycle can neither succeed nor reset")
    if success == 0 and u_value == 0:
        raise ValueError("unreachable: no early or cycle completion is possible")
    denominator = u_value * terminal_cycle_probability + v_value * success
    if denominator == 0:
        raise ValueError("unreachable: preparation/protected-cycle denominator is zero")
    success_mean = _atom_mean(success_atoms) if success_atoms else 0.0
    cycle_mean = success * success_mean + (1 - success) * failed
    mean = base + (price * terminal_cycle_probability + v_value * cycle_mean) / denominator
    preparations = terminal_cycle_probability / denominator
    cycles = v_value / denominator
    early_probability = u_value * terminal_cycle_probability / denominator
    via_cycle_probability = v_value * success / denominator
    _require_finite_nonnegative(
        (mean, "mean_cost"),
        (preparations, "expected_preparations"),
        (cycles, "expected_cycles"),
        (early_probability, "early_completion_probability"),
        (via_cycle_probability, "via_cycle_probability"),
        (cycle_mean, "unconditional_cycle_cost"),
    )
    return ProtectedCycleMetrics(
        mean,
        preparations,
        cycles,
        early_probability,
        via_cycle_probability,
        cycle_mean,
    )


def estimate_protected_cycle_p90(
    u: float,
    v: float,
    preparation_price: float,
    p: float,
    b: float,
    failed_cycle_cost: float,
    success_cycle_cost_atoms: CostAtoms,
    *,
    base_cost: float = 0,
    rng: np.random.Generator,
    samples: int = 50_000,
    confidence: float = 0.99,
) -> ProtectedCycleEstimate:
    """Sample the exact N/H/J/K renewal law using the caller's generator."""
    success_rows = _materialize_atoms(success_cycle_cost_atoms, "success_cycle_cost_atoms")
    metrics = protected_cycle_metrics(
        u,
        v,
        preparation_price,
        p,
        b,
        failed_cycle_cost,
        success_rows,
        base_cost=base_cost,
    )
    (
        u_value,
        v_value,
        price,
        success,
        full_reset,
        failed,
        success_atoms,
        base,
    ) = _protected_inputs(
        u, v, preparation_price, p, b, failed_cycle_cost, success_rows, base_cost
    )
    trial_count, coverage, epsilon = _sample_contract(rng, samples, confidence)

    if v_value == 0:
        _require_sampled_probability(u_value, "u")
        preparations = _positive_count_array(
            rng.geometric(u_value, size=trial_count), "pure-preparation count"
        )
        costs = base + price * preparations
    else:
        terminal_cycle_probability = success + full_reset
        denominator = u_value * terminal_cycle_probability + v_value * success
        raw_completion_probability = denominator / (
            (u_value + v_value) * terminal_cycle_probability
        )
        _require_sampled_probability(raw_completion_probability, "raw completion probability")
        _require_sampled_probability(u_value + v_value, "u + v")
        _require_sampled_probability(terminal_cycle_probability, "p + b")
        raw_blocks = _positive_count_array(
            rng.geometric(raw_completion_probability, size=trial_count), "raw block count"
        )
        final_visits_cycle_probability = v_value * success / denominator
        if final_visits_cycle_probability == 0:
            final_cycle = np.zeros(trial_count, dtype=np.int64)
        elif final_visits_cycle_probability == 1:
            final_cycle = np.ones(trial_count, dtype=np.int64)
        else:
            final_cycle = rng.binomial(1, final_visits_cycle_probability, size=trial_count)
        cycle_visits = _add_count_arrays(
            raw_blocks - 1, final_cycle, "cycle visit count"
        )
        preparation_failures = _nonnegative_count_array(
            rng.negative_binomial(raw_blocks, u_value + v_value), "preparation failure count"
        )
        preparations = _add_count_arrays(
            preparation_failures, raw_blocks, "preparation count"
        )
        cycle_attempts = np.zeros(trial_count, dtype=np.int64)
        active = cycle_visits > 0
        if np.any(active):
            cycle_failures = _nonnegative_count_array(
                rng.negative_binomial(cycle_visits[active], terminal_cycle_probability),
                "cycle failure count",
            )
            cycle_attempts[active] = _add_count_arrays(
                cycle_failures, cycle_visits[active], "cycle attempt count"
            )
        costs = base + price * preparations + failed * cycle_attempts
        final_count = int(np.sum(final_cycle))
        if final_count:
            final_indexes = np.flatnonzero(final_cycle)
            costs[final_indexes] += _sample_atom_values(rng, success_atoms, final_count) - failed

    p90, lower, upper, sample_mean, standard_error = _sample_statistics(costs, coverage, epsilon)
    return ProtectedCycleEstimate(
        metrics.mean_cost,
        metrics.expected_preparations,
        metrics.expected_cycles,
        metrics.early_completion_probability,
        metrics.via_cycle_probability,
        metrics.unconditional_cycle_cost,
        p90,
        lower,
        upper,
        trial_count,
        coverage,
        epsilon,
        sample_mean,
        standard_error,
    )


def _parse_stages(stages: Sequence[tuple[int, int, int]]) -> tuple[tuple[int, int, int], ...]:
    try:
        stage_rows = tuple(stages)
    except TypeError as error:
        raise ValueError("stages must be a non-empty sequence") from error
    if not stage_rows:
        raise ValueError("stages must not be empty")
    parsed: list[tuple[int, int, int]] = []
    previous_prefix_cap: int | None = None
    previous_suffix_cap: int | None = None
    for stage in stage_rows:
        try:
            draws, prefix_cap, suffix_cap = stage
        except (TypeError, ValueError) as error:
            raise ValueError("each stage must be (draw_count, prefix_cap, suffix_cap)") from error
        parsed_stage = (
            _distributions._nonnegative_int(draws, "draw_count"),
            _distributions._nonnegative_int(prefix_cap, "prefix_cap"),
            _distributions._nonnegative_int(suffix_cap, "suffix_cap"),
        )
        if (
            previous_prefix_cap is not None
            and (parsed_stage[1] < previous_prefix_cap or parsed_stage[2] < previous_suffix_cap)
        ):
            raise ValueError("stage caps cannot shrink in an add-only schedule")
        parsed.append(parsed_stage)
        previous_prefix_cap, previous_suffix_cap = parsed_stage[1:]
    return tuple(parsed)


def _parse_continue_predicates(
    predicates: Sequence[Predicate | None] | None, stage_count: int
) -> tuple[Predicate | None, ...]:
    if predicates is None:
        return (None,) * stage_count
    try:
        rows = tuple(predicates)
    except TypeError as error:
        raise ValueError("continue_predicates must be a sequence") from error
    if not rows:
        return (None,) * stage_count
    if len(rows) != stage_count:
        raise ValueError("continue_predicates must contain one value per stage")
    for index, predicate in enumerate(rows):
        if predicate is not None:
            _require_predicate(predicate, f"continue_predicates[{index}]")
    return rows


def _require_predicate(predicate: object, name: str) -> None:
    if not callable(predicate):
        raise ValueError(f"{name} must be callable")


def _run_predicate(predicate: Predicate, outcome: OutcomeClass, name: str) -> bool:
    result = predicate(outcome)
    if not isinstance(result, bool):
        raise ValueError(f"{name} must return a bool")
    return result


def _can_draw_in_later_stage(
    state: object,
    profiles: tuple[object, ...],
    later_stages: Sequence[tuple[int, int, int]],
) -> bool:
    for draws, prefix_cap, suffix_cap in later_stages:
        if draws == 0:
            continue
        for index, profile in enumerate(profiles):
            if profile.multiplicity == state.selected[index]:
                continue
            if profile.side == "Prefix" and state.prefixes >= prefix_cap:
                continue
            if profile.side == "Suffix" and state.suffixes >= suffix_cap:
                continue
            return True
    return False


def _conditional_atoms(
    unconditional: Mapping[float, float], probability: float
) -> tuple[tuple[float, float], ...]:
    if probability == 0:
        return ()
    return tuple(
        (cost, mass / probability)
        for cost, mass in sorted(unconditional.items())
        if mass > 0
    )


def _weighted_atoms(
    atoms: CostAtoms, name: str, *, required: bool
) -> tuple[tuple[float, float], ...]:
    try:
        rows = tuple(atoms)
    except TypeError as error:
        raise ValueError(f"{name} must be an iterable of (cost, weight) pairs") from error
    if not rows:
        if required:
            raise ValueError(f"{name} must not be empty")
        return ()
    combined: dict[float, float] = defaultdict(float)
    for row in rows:
        try:
            cost, weight = row
        except (TypeError, ValueError) as error:
            raise ValueError(f"each {name} value must be (cost, weight)") from error
        combined[_nonnegative(cost, f"{name} cost")] += _positive(weight, f"{name} weight")
    total = math.fsum(combined.values())
    return tuple((cost, weight / total) for cost, weight in sorted(combined.items()))


def _materialize_atoms(atoms: CostAtoms, name: str) -> tuple[tuple[float, float], ...]:
    try:
        return tuple(atoms)
    except TypeError as error:
        raise ValueError(f"{name} must be an iterable of (cost, weight) pairs") from error


def _atom_mean(atoms: Sequence[tuple[float, float]]) -> float:
    return math.fsum(cost * weight for cost, weight in atoms)


def _sample_failure_totals(
    rng: np.random.Generator,
    failed_counts: np.ndarray,
    failure_atoms: Sequence[tuple[float, float]],
) -> np.ndarray:
    totals = np.zeros(len(failed_counts), dtype=float)
    if not failure_atoms or not np.any(failed_counts):
        return totals
    costs = np.array([cost for cost, _ in failure_atoms], dtype=float)
    weights = np.array([weight for _, weight in failure_atoms], dtype=float)
    multinomial = rng.multinomial(failed_counts, weights)
    _nonnegative_count_array(multinomial, "conditional-failure multinomial count")
    if not np.array_equal(np.sum(multinomial, axis=1), failed_counts):
        raise ValueError("conditional-failure multinomial counts did not conserve attempts")
    totals = multinomial @ costs
    if not np.isfinite(totals).all() or np.any(totals < 0):
        raise ValueError("conditional-failure sampled costs must be finite and non-negative")
    return totals


def _sample_atom_values(
    rng: np.random.Generator, atoms: Sequence[tuple[float, float]], size: int
) -> np.ndarray:
    if size == 0:
        return np.empty(0, dtype=float)
    if not atoms:
        raise AssertionError("sampled an absent cost-atom distribution")
    costs = np.array([cost for cost, _ in atoms], dtype=float)
    weights = np.array([weight for _, weight in atoms], dtype=float)
    return costs[rng.choice(len(costs), size=size, p=weights)]


def _sample_contract(
    rng: np.random.Generator, samples: int, confidence: float
) -> tuple[int, float, float]:
    if not isinstance(rng, np.random.Generator):
        raise ValueError("rng must be a numpy.random.Generator")
    if isinstance(samples, bool) or not isinstance(samples, int) or samples <= 0:
        raise ValueError("samples must be a positive integer")
    coverage = _probability(confidence, "confidence")
    if coverage >= 1:
        raise ValueError("confidence must be in [0, 1)")
    epsilon = math.sqrt(math.log(2 / (1 - coverage)) / (2 * samples))
    if epsilon >= 0.1:
        raise ValueError("samples are insufficient to bracket the 0.9 quantile")
    return samples, coverage, epsilon


def _sample_statistics(
    costs: np.ndarray, confidence: float, epsilon: float
) -> tuple[float, float, float, float, float]:
    if not np.isfinite(costs).all() or np.any(costs < 0):
        raise ValueError("sampled costs must be finite and non-negative")
    ordered = np.sort(costs)
    p90 = _higher_quantile(ordered, 0.9)
    lower = _higher_quantile(ordered, max(0.0, 0.9 - epsilon))
    upper = _higher_quantile(ordered, min(1.0, 0.9 + epsilon))
    mean = float(np.mean(costs))
    standard_error = float(np.std(costs, ddof=1) / math.sqrt(len(costs)))
    _require_finite_nonnegative(
        (p90, "sampled p90"),
        (lower, "sampled interval lower"),
        (upper, "sampled interval upper"),
        (mean, "sample mean"),
        (standard_error, "sample standard error"),
    )
    return p90, lower, upper, mean, standard_error


def _higher_quantile(ordered: np.ndarray, probability: float) -> float:
    rank = max(0, min(len(ordered) - 1, math.ceil(probability * len(ordered)) - 1))
    return float(ordered[rank])


def _require_sampled_probability(probability: float, name: str) -> None:
    if probability < 1 / float(np.iinfo(np.int64).max):
        raise ValueError(f"{name} is too small for bounded int64 sampling")


def _positive_count_array(values: np.ndarray, name: str) -> np.ndarray:
    result = _nonnegative_count_array(values, name)
    if np.any(result == 0):
        raise ValueError(f"{name} must be positive")
    return result


def _nonnegative_count_array(values: np.ndarray, name: str) -> np.ndarray:
    result = np.asarray(values)
    if not np.issubdtype(result.dtype, np.integer) or np.any(result < 0):
        raise ValueError(f"{name} must be a non-negative integer array")
    return result.astype(np.int64, copy=False)


def _add_count_arrays(left: np.ndarray, right: np.ndarray, name: str) -> np.ndarray:
    left_values = _nonnegative_count_array(left, name)
    right_values = _nonnegative_count_array(right, name)
    if np.any(left_values > np.iinfo(np.int64).max - right_values):
        raise ValueError(f"{name} overflowed int64")
    return left_values + right_values


def _require_finite_nonnegative(*values: tuple[float, str]) -> None:
    for value, name in values:
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and non-negative")


def _protected_inputs(
    u: float,
    v: float,
    preparation_price: float,
    p: float,
    b: float,
    failed_cycle_cost: float,
    success_cycle_cost_atoms: CostAtoms,
    base_cost: float,
) -> tuple[float, float, float, float, float, float, tuple[tuple[float, float], ...], float]:
    u_value = _probability(u, "u")
    v_value = _probability(v, "v")
    if u_value + v_value > 1:
        raise ValueError("u + v must be at most one")
    price = _nonnegative(preparation_price, "preparation_price")
    success = _probability(p, "p")
    full_reset = _probability(b, "b")
    if full_reset > 1 - success:
        raise ValueError("b must not exceed 1-p")
    failed = _nonnegative(failed_cycle_cost, "failed_cycle_cost")
    base = _nonnegative(base_cost, "base_cost")
    success_atoms = _weighted_atoms(
        success_cycle_cost_atoms,
        "success_cycle_cost_atoms",
        required=v_value > 0 and success > 0,
    )
    if u_value == 0 and v_value == 0:
        raise ValueError("unreachable: preparation never terminates or prepares")
    if v_value > 0 and success == 0 and full_reset == 0:
        raise ValueError("unreachable: prepared cycle can neither succeed nor reset")
    if v_value > 0 and success == 0 and u_value == 0:
        raise ValueError("unreachable: no early or cycle completion is possible")
    return u_value, v_value, price, success, full_reset, failed, success_atoms, base


def _probability(value: object, name: str) -> float:
    result = _finite(value, name)
    if result < 0 or result > 1:
        raise ValueError(f"{name} must be in [0, 1]")
    return result


def _nonnegative(value: object, name: str) -> float:
    result = _finite(value, name)
    if result < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return result


def _positive(value: object, name: str) -> float:
    result = _finite(value, name)
    if result <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return result


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result
