"""Finite stochastic shortest-path solving and a bounded helmet graph probe.

The generic solver implements the mathematical MDP contract in
``docs/specs/2026-09-21-bounded-policy-solver.md``.  The helmet probe only
uses ordinary action legality and draw setup from :mod:`craftoracle.actions`.
It deliberately retains concrete modifier identity until a state is terminal:
``OutcomeClass`` is not a transition-state representation.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Collection, Mapping, Sequence
from dataclasses import asdict, dataclass
import math
from pathlib import Path
from time import perf_counter
from typing import Any

from craftoracle.actions import (
    ActionData,
    bench_item,
    load_action_data,
    prepare_roll,
    scour_item,
)
from craftoracle.distributions import OutcomeClass
from craftoracle.item_model import ItemState, ModRef
from craftoracle.plan_inputs import ItemSpec, Loadout, load_loadout, load_spec


_EPSILON = 1e-10
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_DRAW_ACTIONS = frozenset((
    "transmute", "alteration", "augmentation", "regal", "alchemy",
    "chaos", "exalted", "essence",
))
_REROLL_ACTIONS = frozenset(("transmute", "alteration", "alchemy", "chaos"))
_RESULT_RARITIES = {
    "transmute": "magic",
    "alteration": "magic",
    "augmentation": "magic",
    "regal": "rare",
    "alchemy": "rare",
    "chaos": "rare",
    "exalted": "rare",
    "essence": "rare",
}
_METAMOD_GROUPS = frozenset((
    "ItemGenerationCannotChangePrefixes",
    "ItemGenerationCannotChangeSuffixes",
    "ItemGenerationCanHaveMultipleCraftedMods",
    "ItemGenerationCannotRollAttackAffixes",
    "ItemGenerationCannotRollCasterAffixes",
))
_ORDINARY_ACTIONS = (
    "transmute", "alteration", "augmentation", "regal", "alchemy", "chaos",
    "exalted", "annul", "scour", "essence", "bench",
)


class MDPInputError(ValueError):
    """The supplied MDP violates the finite stochastic shortest-path contract."""


class ExperimentInputError(ValueError):
    """A required committed input is absent or cannot form a permitted action."""


@dataclass(frozen=True)
class Action:
    """One player-chosen action and its complete successor probability row."""

    name: str
    cost: float
    successors: Mapping[str, float]


@dataclass(frozen=True)
class SolverLimits:
    """Finite safeguards for value iteration; no zero-cost nonterminal cycle is allowed."""

    max_iterations: int = 10_000
    residual: float = 1e-10
    max_seconds: float | None = None


@dataclass(frozen=True)
class SolverResult:
    values: dict[str, float]
    policy: dict[str, str | None]
    residual: float
    iterations: int
    states: int
    edges: int
    runtime_seconds: float
    unreachable: frozenset[str]
    unresolved: frozenset[str]
    converged: bool
    status: str


def solve_mdp(
    actions: Mapping[str, Sequence[Action]],
    terminal_states: Collection[str],
    *,
    limits: SolverLimits = SolverLimits(),
) -> SolverResult:
    """Solve a finite positive-cost MDP by monotone Bellman value iteration.

    A state without even a graph path to a terminal, or one whose every action
    can enter such a state, receives ``inf`` and no selected action.  If the
    requested residual is not reached, unresolved values are also returned as
    ``inf`` so callers cannot mistake an iteration prefix for an exact cost.
    """
    checked_actions, terminals, edge_count = _validate_mdp(actions, terminal_states, limits)
    started = perf_counter()
    all_states = set(checked_actions) | terminals
    unreachable = _unreachable_states(checked_actions, terminals)
    unsafe = set(unreachable)

    # Remove actions which can transition to a state already known not to
    # reach a terminal.  The least fixpoint propagates that fact backward.
    while True:
        newly_unsafe = {
            state
            for state, options in checked_actions.items()
            if state not in unsafe
            and not any(all(successor not in unsafe for successor in action.successors) for action in options)
        }
        if not newly_unsafe:
            break
        unsafe.update(newly_unsafe)

    finite_states = all_states - terminals - unsafe
    values = {state: 0.0 for state in finite_states}
    values.update({terminal: 0.0 for terminal in terminals})
    iterations = 0
    residual = math.inf
    status = "iteration_limit"

    while iterations < limits.max_iterations:
        if limits.max_seconds is not None and perf_counter() - started > limits.max_seconds:
            status = "time_limit"
            break
        iterations += 1
        updated: dict[str, float] = {}
        for state in finite_states:
            candidates = [
                action.cost + sum(probability * values[successor] for successor, probability in action.successors.items())
                for action in checked_actions[state]
                if all(successor not in unsafe for successor in action.successors)
            ]
            if not candidates:
                unsafe.add(state)
                continue
            updated[state] = min(candidates)
        residual = max((abs(updated[state] - values[state]) for state in updated), default=0.0)
        values.update(updated)
        if residual <= limits.residual:
            status = "converged"
            break

    runtime = perf_counter() - started
    converged = status == "converged"
    policy: dict[str, str | None] = {terminal: None for terminal in terminals}
    if converged:
        for state in finite_states:
            policy[state] = _best_action(checked_actions[state], values, unsafe)
    else:
        # The finite prefix is not reported as a calculated expected cost.
        unsafe.update(finite_states)
        values = {state: 0.0 if state in terminals else math.inf for state in all_states}
        policy.update({state: None for state in all_states if state not in terminals})

    for state in unsafe:
        values[state] = math.inf
        policy[state] = None
    bellman_residual = residual if converged else math.inf
    return SolverResult(
        values=dict(sorted(values.items())),
        policy=dict(sorted(policy.items())),
        residual=bellman_residual,
        iterations=iterations,
        states=len(all_states),
        edges=edge_count,
        runtime_seconds=runtime,
        unreachable=frozenset(unreachable),
        unresolved=frozenset(unsafe - unreachable),
        converged=converged,
        status=status,
    )


def weighted_next_group_probability(
    weights: Mapping[str, float], target_group: str, *, occupied_groups: Collection[str] = ()
) -> float:
    """Return the next-draw chance of one concrete group after occupied groups.

    This tiny helper makes the non-lumpability counterexample explicit.  It is
    intentionally group-aware; callers must not replace ``occupied_groups``
    with only a count of junk affixes.
    """
    if not isinstance(target_group, str) or not target_group:
        raise MDPInputError("target_group must be a non-empty string")
    if not isinstance(weights, Mapping) or not weights:
        raise MDPInputError("weights must be a non-empty mapping")
    occupied = set(occupied_groups)
    if not all(isinstance(group, str) and group for group in occupied):
        raise MDPInputError("occupied_groups must contain non-empty strings")
    remaining: dict[str, float] = {}
    for group, raw_weight in weights.items():
        if not isinstance(group, str) or not group:
            raise MDPInputError("weight groups must be non-empty strings")
        if isinstance(raw_weight, bool) or not isinstance(raw_weight, (int, float)) or not math.isfinite(raw_weight) or raw_weight <= 0:
            raise MDPInputError("group weights must be finite positive numbers")
        if group not in occupied:
            remaining[group] = float(raw_weight)
    total = sum(remaining.values())
    if total == 0:
        return 0.0
    return remaining.get(target_group, 0.0) / total


def _validate_mdp(
    actions: Mapping[str, Sequence[Action]], terminal_states: Collection[str], limits: SolverLimits
) -> tuple[dict[str, tuple[Action, ...]], frozenset[str], int]:
    if not isinstance(actions, Mapping):
        raise MDPInputError("actions must map state IDs to action sequences")
    if not isinstance(limits.max_iterations, int) or isinstance(limits.max_iterations, bool) or limits.max_iterations <= 0:
        raise MDPInputError("max_iterations must be a positive integer")
    if not isinstance(limits.residual, (int, float)) or isinstance(limits.residual, bool) or not math.isfinite(limits.residual) or limits.residual <= 0:
        raise MDPInputError("residual must be a finite positive number")
    if limits.max_seconds is not None and (
        isinstance(limits.max_seconds, bool)
        or not isinstance(limits.max_seconds, (int, float))
        or not math.isfinite(limits.max_seconds)
        or limits.max_seconds <= 0
    ):
        raise MDPInputError("max_seconds must be a finite positive number or None")
    terminals = frozenset(terminal_states)
    if not terminals or not all(isinstance(state, str) and state for state in terminals):
        raise MDPInputError("terminal_states must contain non-empty string IDs")
    if not all(isinstance(state, str) and state for state in actions):
        raise MDPInputError("state IDs must be non-empty strings")
    overlap = terminals & set(actions)
    if overlap:
        raise MDPInputError(f"terminal states cannot have actions: {sorted(overlap)!r}")

    known = set(actions) | terminals
    checked: dict[str, tuple[Action, ...]] = {}
    edge_count = 0
    for state, raw_options in actions.items():
        try:
            options = tuple(raw_options)
        except TypeError as exc:
            raise MDPInputError(f"actions for {state!r} must be iterable") from exc
        names: set[str] = set()
        parsed: list[Action] = []
        for action in options:
            if not isinstance(action, Action):
                raise MDPInputError(f"action for {state!r} must be an Action")
            if not isinstance(action.name, str) or not action.name:
                raise MDPInputError("action names must be non-empty strings")
            if action.name in names:
                raise MDPInputError(f"duplicate action name at {state!r}: {action.name}")
            names.add(action.name)
            if isinstance(action.cost, bool) or not isinstance(action.cost, (int, float)) or not math.isfinite(action.cost) or action.cost <= 0:
                raise MDPInputError("nonterminal action costs must be finite and positive")
            if not isinstance(action.successors, Mapping) or not action.successors:
                raise MDPInputError(f"action {action.name!r} needs a non-empty successor row")
            mass = 0.0
            successors: dict[str, float] = {}
            for successor, probability in action.successors.items():
                if not isinstance(successor, str) or not successor:
                    raise MDPInputError("successor IDs must be non-empty strings")
                if successor not in known:
                    raise MDPInputError(f"unknown successor ID: {successor!r}")
                if isinstance(probability, bool) or not isinstance(probability, (int, float)) or not math.isfinite(probability) or probability < 0:
                    raise MDPInputError("successor probabilities must be finite and non-negative")
                mass += float(probability)
                # A zero-mass key is validation input, not an MDP edge.  In
                # particular it must not make a safe row appear to reach an
                # unreachable state.
                if probability > 0:
                    successors[successor] = float(probability)
            if not math.isclose(mass, 1.0, rel_tol=0.0, abs_tol=_EPSILON):
                raise MDPInputError(f"successor probabilities for {action.name!r} must sum to one, got {mass!r}")
            edge_count += sum(probability > 0 for probability in successors.values())
            parsed.append(Action(action.name, float(action.cost), successors))
        checked[state] = tuple(parsed)
    return checked, terminals, edge_count


def _unreachable_states(actions: Mapping[str, Sequence[Action]], terminals: Collection[str]) -> set[str]:
    predecessors: dict[str, set[str]] = defaultdict(set)
    for state, options in actions.items():
        for action in options:
            for successor, probability in action.successors.items():
                if probability > 0:
                    predecessors[successor].add(state)
    reachable = set(terminals)
    queue = deque(terminals)
    while queue:
        successor = queue.popleft()
        for predecessor in predecessors.get(successor, ()):
            if predecessor not in reachable:
                reachable.add(predecessor)
                queue.append(predecessor)
    return set(actions) - reachable


def _best_action(options: Sequence[Action], values: Mapping[str, float], unsafe: Collection[str]) -> str | None:
    candidates = [
        (action.cost + sum(probability * values[successor] for successor, probability in action.successors.items()), action.name)
        for action in options
        if all(successor not in unsafe for successor in action.successors)
    ]
    return min(candidates)[1] if candidates else None


@dataclass(frozen=True)
class CraftState:
    """Concrete Markov state for the bounded experiment.

    ``mods`` and ``group_profile`` retain the identity that changes later draw
    weights.  The redundant target/count/meta fields make the required state
    fidelity auditable in a JSON report without using an OutcomeClass.
    """

    rarity: str
    mods: tuple[ModRef, ...]
    target_tiers: tuple[tuple[str, int | None], ...]
    junk_prefixes: int
    junk_suffixes: int
    crafted_mod_count: int
    metamod_flags: tuple[str, ...]
    group_profile: tuple[tuple[str, str, str], ...]

    def key(self) -> str:
        return repr((self.rarity, self.group_profile))


@dataclass(frozen=True)
class ExperimentLimits:
    max_states: int = 100_000
    max_edges: int = 2_000_000
    build_seconds: float = 120.0
    solve_seconds: float = 120.0
    max_iterations: int = 10_000
    residual: float = 1e-10


@dataclass
class _GraphProgress:
    started: float
    states: int = 1
    completed_edges: int = 0
    partial_edges: int = 0
    peak_frontier: int = 1
    probability_row_violations: int = 0
    completed_rows: int = 0
    pending_concrete_states: int = 0
    peak_pending_concrete_states: int = 0


class _ExperimentLimit(Exception):
    def __init__(self, kind: str, operation: str):
        self.kind = kind
        self.operation = operation


def run_helmet_experiment(
    root: str | Path = _REPOSITORY_ROOT,
    *,
    limits: ExperimentLimits = ExperimentLimits(),
) -> dict[str, Any]:
    """Build and solve the ordinary-action Royal Burgonet MDP within hard limits.

    Harvest is intentionally omitted because its forced-draw continuation has
    not been made group-preserving for this general solver experiment.  A graph
    limit is a successful measured negative result and is returned as JSON data.
    """
    _validate_experiment_limits(limits)
    root = Path(root)
    try:
        data = load_action_data(root)
        spec = load_spec(root / "examples/helmet_life_chaos_res.yaml", data.mods)
        loadout = load_loadout(root / "data/loadouts/endgame.json")
    except (OSError, ValueError, NotImplementedError) as exc:
        raise ExperimentInputError(f"source_or_input_error: {exc}") from exc

    normal = ItemState(spec.base, spec.item_level, "normal")
    initial = _craft_state(normal, spec)
    states: dict[str, CraftState] = {initial.key(): initial}
    items: dict[str, ItemState] = {initial.key(): normal}
    rows: dict[str, list[Action]] = {}
    queue = deque([initial.key()])
    progress = _GraphProgress(perf_counter())
    availability = _action_availability(loadout)

    try:
        while queue:
            _check_build_time(progress, limits, "expand_graph_state")
            state_key = queue.popleft()
            item = items[state_key]
            options: list[Action] = []
            if _matches_spec(item, spec):
                rows[state_key] = []
                continue
            for name, cost, successors in _state_actions(
                item, spec, data, loadout, availability, progress, limits, states.keys()
            ):
                row: dict[str, float] = {}
                for successor, probability in successors.items():
                    successor_key = successor.key()
                    if successor_key not in states:
                        if progress.states >= limits.max_states:
                            raise _ExperimentLimit("states", f"enumerate {name} from {state_key}")
                        states[successor_key] = successor
                        items[successor_key] = _item_from_craft_state(successor, spec)
                        progress.states += 1
                        queue.append(successor_key)
                    row[successor_key] = row.get(successor_key, 0.0) + probability
                _validate_completed_row(row)
                progress.completed_rows += 1
                if progress.completed_edges + len(row) > limits.max_edges:
                    raise _ExperimentLimit("edges", f"complete {name} from {state_key}")
                progress.completed_edges += len(row)
                options.append(Action(name, cost, row))
            rows[state_key] = options
            progress.peak_frontier = max(progress.peak_frontier, len(queue))
    except _ExperimentLimit as limit:
        return _limit_report(spec, loadout, availability, progress, limit, limits)

    terminal_states = {state_key for state_key, item in items.items() if _matches_spec(item, spec)}
    terminal_rows = {state_key: options for state_key, options in rows.items() if state_key not in terminal_states}
    if not terminal_states:
        report = _base_report(spec, loadout, availability, progress, limits)
        report["graph"]["complete"] = True
        report["status"] = "complexity_limit"
        report["limit"] = {"kind": "unreachable_target", "operation": "classify terminal target states"}
        report["helmet_result"] = None
        report["template_comparison"] = None
        return report
    try:
        solved = solve_mdp(
            terminal_rows,
            terminal_states,
            limits=SolverLimits(limits.max_iterations, limits.residual, limits.solve_seconds),
        )
    except MDPInputError as exc:
        raise ExperimentInputError(f"constructed invalid MDP: {exc}") from exc
    report = _base_report(spec, loadout, availability, progress, limits)
    report["graph"]["complete"] = True
    report["solver"] = _solver_json(solved)
    if not solved.converged:
        report["status"] = "complexity_limit"
        report["limit"] = {"kind": solved.status, "operation": "solve finite MDP"}
        report["helmet_result"] = None
        report["template_comparison"] = None
        return report

    start_value = loadout.base_cost + solved.values[initial.key()]
    report["helmet_result"] = {
        "expected_cost": start_value,
        "unit": loadout.unit,
        "policy_steps": _policy_steps(initial.key(), solved.policy, terminal_rows),
    }
    report["template_comparison"] = _template_comparison(spec, loadout, data, start_value)
    report["status"] = (
        "success" if report["template_comparison"]["solver_matches_or_beats_template"]
        else "completed_not_positive"
    )
    if report["status"] != "success":
        report["negative_result"] = (
            "The complete bounded action/state set did not match the best available template; "
            "the report records omitted actions and does not claim an optimum."
        )
    return report


def _validate_experiment_limits(limits: ExperimentLimits) -> None:
    for name in ("max_states", "max_edges", "max_iterations"):
        value = getattr(limits, name)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ExperimentInputError(f"{name} must be a positive integer")
    for name in ("build_seconds", "solve_seconds", "residual"):
        value = getattr(limits, name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ExperimentInputError(f"{name} must be a finite positive number")


def _action_availability(loadout: Loadout) -> dict[str, Any]:
    included: list[str] = []
    skipped: dict[str, str] = {}
    for action in _ORDINARY_ACTIONS:
        if action not in loadout.allowed_actions:
            skipped[action] = "not permitted by endgame loadout"
        elif action == "annul":
            # The adapter has Annul legality, but this first probe does not
            # yet enumerate its concrete eligible removal profile.  It must
            # never be advertised as an included action without transitions.
            try:
                loadout.price("annul")
            except ValueError as exc:
                skipped[action] = f"omitted: concrete group-preserving Annul enumeration; missing required price: {exc}"
            else:
                skipped[action] = "omitted: concrete group-preserving Annul enumeration is not implemented in this first probe"
        elif action == "essence":
            for essence_id in sorted(loadout.allowed_essences):
                try:
                    loadout.price(essence_id)
                except ValueError as exc:
                    skipped[f"essence:{essence_id}"] = f"missing required price: {exc}"
                else:
                    included.append(f"essence:{essence_id}")
        elif action == "bench":
            for index in sorted(loadout.allowed_bench):
                try:
                    loadout.bench_cost(index)
                except ValueError as exc:
                    skipped[f"bench:{index}"] = f"missing required recipe price: {exc}"
                else:
                    included.append(f"bench:{index}")
        else:
            try:
                loadout.price(action)
            except ValueError as exc:
                skipped[action] = f"missing required price: {exc}"
            else:
                included.append(action)
    return {
        "included": included,
        "skipped": skipped,
        "harvest": "omitted: forced-draw continuation is not group-preserving in this first ordinary-action experiment",
    }


def _state_actions(
    item: ItemState,
    spec: ItemSpec,
    data: ActionData,
    loadout: Loadout,
    availability: Mapping[str, Any],
    progress: _GraphProgress,
    limits: ExperimentLimits,
    known_state_keys: Collection[str],
) -> list[tuple[str, float, dict[CraftState, float]]]:
    actions: list[tuple[str, float, dict[CraftState, float]]] = []
    included = set(availability["included"])
    for action in ("alchemy", "transmute", "alteration", "augmentation", "regal", "chaos", "exalted"):
        if action not in included:
            continue
        try:
            outcomes = _roll_outcomes(action, item, spec, data, progress, limits, known_state_keys)
        except ValueError:
            continue
        if outcomes:
            actions.append((action, loadout.price(action), outcomes))
    for entry in sorted(included):
        if entry.startswith("essence:"):
            essence_id = entry.removeprefix("essence:")
            try:
                outcomes = _roll_outcomes(
                    "essence", item, spec, data, progress, limits, known_state_keys, essence_id=essence_id
                )
            except (ValueError, NotImplementedError):
                continue
            if outcomes:
                actions.append((entry, loadout.price(essence_id), outcomes))
        elif entry.startswith("bench:"):
            index = int(entry.removeprefix("bench:"))
            try:
                output = bench_item(item, data, index)
            except ValueError:
                continue
            actions.append((entry, loadout.bench_cost(index), {_craft_state(output, spec): 1.0}))
    if "scour" in included:
        try:
            output = scour_item(item, data)
        except ValueError:
            pass
        else:
            actions.append(("scour", loadout.price("scour"), {_craft_state(output, spec): 1.0}))
    # Annul is intentionally absent when its endgame price is absent.  No
    # imputed price is allowed by the loadout contract.
    return actions


def _roll_outcomes(
    action: str,
    item: ItemState,
    spec: ItemSpec,
    data: ActionData,
    progress: _GraphProgress,
    limits: ExperimentLimits,
    known_state_keys: Collection[str],
    *,
    essence_id: str | None = None,
) -> dict[CraftState, float]:
    scenario = prepare_roll(action, item, data, spec.labels, essence_id=essence_id)
    fixed = _fixed_mods_for_roll(action, item, data, essence_id)
    count_total = sum(weight for _, weight in scenario.draw_counts)
    outcomes: dict[CraftState, float] = defaultdict(float)
    pending_keys: set[str] = set()
    stack: list[tuple[tuple[ModRef, ...], float, int]] = []
    for draws, count_weight in scenario.draw_counts:
        stack.append((fixed, count_weight / count_total, draws))

    while stack:
        _check_build_time(progress, limits, f"enumerate {action}")
        progress.peak_frontier = max(progress.peak_frontier, len(stack))
        mods, mass, draws = stack.pop()
        if draws == 0:
            output = ItemState(item.base_name, item.item_level, _RESULT_RARITIES[action], _canonical_mods(mods))
            _record_roll_outcome(
                outcomes, _craft_state(output, spec), mass, known_state_keys, pending_keys, progress, limits, action
            )
            continue
        prefix_count = sum(mod.type == "Prefix" for mod in mods)
        suffix_count = sum(mod.type == "Suffix" for mod in mods)
        groups = {mod.group for mod in mods}
        entries = [
            entry for entry in scenario.entries
            if entry.group not in groups
            and not (entry.type == "Prefix" and prefix_count >= scenario.prefix_cap)
            and not (entry.type == "Suffix" and suffix_count >= scenario.suffix_cap)
        ]
        total = sum(entry.weight for entry in entries)
        if total == 0:
            output = ItemState(item.base_name, item.item_level, _RESULT_RARITIES[action], _canonical_mods(mods))
            _record_roll_outcome(
                outcomes, _craft_state(output, spec), mass, known_state_keys, pending_keys, progress, limits, action
            )
            continue
        for entry in entries:
            if progress.partial_edges >= limits.max_edges:
                raise _ExperimentLimit("edges", f"enumerate {action} draw substage")
            progress.partial_edges += 1
            stack.append((
                (*mods, ModRef(entry.mod_id, entry.type, entry.group)),
                mass * entry.weight / total,
                draws - 1,
            ))
    progress.pending_concrete_states = 0
    return dict(outcomes)


def _record_roll_outcome(
    outcomes: dict[CraftState, float],
    outcome: CraftState,
    mass: float,
    known_state_keys: Collection[str],
    pending_keys: set[str],
    progress: _GraphProgress,
    limits: ExperimentLimits,
    action: str,
) -> None:
    key = outcome.key()
    if outcome not in outcomes and key not in known_state_keys:
        if progress.states + len(pending_keys) >= limits.max_states:
            progress.pending_concrete_states = len(pending_keys)
            raise _ExperimentLimit("states", f"materialize pending {action} outcome")
        pending_keys.add(key)
        progress.pending_concrete_states = len(pending_keys)
        progress.peak_pending_concrete_states = max(progress.peak_pending_concrete_states, len(pending_keys))
    outcomes[outcome] += mass


def _fixed_mods_for_roll(action: str, item: ItemState, data: ActionData, essence_id: str | None) -> tuple[ModRef, ...]:
    if action in _REROLL_ACTIONS:
        return () if item.rarity == "normal" else scour_item(item, data).mods
    if action == "essence":
        assert essence_id is not None
        essence = data.essences[essence_id]
        base_type = data.bases[item.base_name]["type"]
        forced_id = essence["mods"][base_type]
        row = data.mods[forced_id]
        return (ModRef(forced_id, row["type"], row["group"]),)
    return item.mods


def _canonical_mods(mods: Collection[ModRef]) -> tuple[ModRef, ...]:
    return tuple(sorted(mods, key=lambda mod: (mod.type, mod.group, mod.id)))


def _craft_state(item: ItemState, spec: ItemSpec) -> CraftState:
    mods = _canonical_mods(item.mods)
    tier_lookup = {
        mod_id: (group, tier)
        for group, tiers in spec.tier_ids.items()
        for tier, ids in enumerate(tiers, start=1)
        for mod_id in ids
    }
    target_tiers = tuple(
        (group, next((tier_lookup[mod.id][1] for mod in mods if mod.id in tier_lookup and tier_lookup[mod.id][0] == group), None))
        for group in sorted(spec.tier_ids)
    )
    junk_prefixes = sum(mod.type == "Prefix" and mod.id not in tier_lookup for mod in mods)
    junk_suffixes = sum(mod.type == "Suffix" and mod.id not in tier_lookup for mod in mods)
    return CraftState(
        item.rarity,
        mods,
        target_tiers,
        junk_prefixes,
        junk_suffixes,
        sum(mod.id.startswith("bench:") for mod in mods),
        tuple(sorted(mod.group for mod in mods if mod.group in _METAMOD_GROUPS)),
        tuple((mod.type, mod.group, mod.id) for mod in mods),
    )


def _item_from_craft_state(state: CraftState, spec: ItemSpec) -> ItemState:
    return ItemState(spec.base, spec.item_level, state.rarity, state.mods)


def _matches_spec(item: ItemState, spec: ItemSpec) -> bool:
    labels = tuple(sorted(spec.labels[mod.id] for mod in item.mods if mod.id in spec.labels))
    outcome = OutcomeClass(
        labels,
        sum(mod.type == "Prefix" for mod in item.mods),
        sum(mod.type == "Suffix" for mod in item.mods),
    )
    return spec.matches(outcome)


def _check_build_time(progress: _GraphProgress, limits: ExperimentLimits, operation: str) -> None:
    if perf_counter() - progress.started > limits.build_seconds:
        raise _ExperimentLimit("build_time", operation)


def _validate_completed_row(row: Mapping[str, float]) -> None:
    mass = sum(row.values())
    if not math.isclose(mass, 1.0, rel_tol=0.0, abs_tol=_EPSILON):
        raise ExperimentInputError(f"constructed transition row does not sum to one: {mass!r}")


def _base_report(spec: ItemSpec, loadout: Loadout, availability: Mapping[str, Any], progress: _GraphProgress, limits: ExperimentLimits) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "incomplete",
        "target": {"name": spec.name, "base": spec.base, "item_level": spec.item_level},
        "unit": loadout.unit,
        "action_set": availability,
        "model_scope": {
            "q9_flags": "all false",
            "generated_tags_and_weight_multipliers": "omitted under D14",
            "state_representation": "rarity, concrete group/mod profile, target tiers, junk side counts, crafted count, metamod flags",
        },
        "graph": {
            "complete": False,
            "states": progress.states + progress.pending_concrete_states,
            "materialized_states": progress.states,
            "pending_concrete_states": progress.pending_concrete_states,
            "peak_pending_concrete_states": progress.peak_pending_concrete_states,
            "completed_successor_edges": progress.completed_edges,
            "partial_draw_edges": progress.partial_edges,
            "completed_rows": progress.completed_rows,
            "completed_probability_row_violations": progress.probability_row_violations,
            "peak_frontier": progress.peak_frontier,
            "build_seconds": perf_counter() - progress.started,
        },
        "limits": asdict(limits),
    }


def _limit_report(
    spec: ItemSpec,
    loadout: Loadout,
    availability: Mapping[str, Any],
    progress: _GraphProgress,
    limit: _ExperimentLimit,
    limits: ExperimentLimits,
) -> dict[str, Any]:
    report = _base_report(spec, loadout, availability, progress, limits)
    report["status"] = "complexity_limit"
    report["limit"] = {"kind": limit.kind, "operation": limit.operation}
    report["helmet_result"] = None
    report["template_comparison"] = None
    return report


def _solver_json(result: SolverResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "converged": result.converged,
        "residual": result.residual if math.isfinite(result.residual) else None,
        "iterations": result.iterations,
        "states": result.states,
        "edges": result.edges,
        "runtime_seconds": result.runtime_seconds,
        "unreachable": sorted(result.unreachable),
        "unresolved": sorted(result.unresolved),
    }


def _policy_steps(start: str, policy: Mapping[str, str | None], rows: Mapping[str, Sequence[Action]]) -> list[str]:
    steps: list[str] = []
    state = start
    seen: set[str] = set()
    for _ in range(100):
        if state in seen:
            steps.append("policy revisits a state; stochastic continuation omitted from readable trace")
            break
        seen.add(state)
        selected = policy.get(state)
        if selected is None:
            break
        steps.append(f"{state}: {selected}")
        action = next(action for action in rows[state] if action.name == selected)
        state = max(action.successors.items(), key=lambda entry: entry[1])[0]
    return steps


def _template_comparison(spec: ItemSpec, loadout: Loadout, data: ActionData, expected_cost: float) -> dict[str, Any]:
    try:
        from craftoracle.optimizer import optimize_policies
    except ImportError:
        from craftoracle.policies import evaluate_policies
        templates = evaluate_policies(spec, loadout, data)
        comparison_source = "fixed policy fallback: optimize_policies is unavailable at this commit"
    else:
        templates = optimize_policies(spec, loadout, data)
        comparison_source = "parameterized optimize_policies"
    best = templates["ranked"][0]
    template_cost = best["expected_cost"]
    return {
        "best_accepted_parameterized_template": {
            "id": best["id"], "expected_cost": template_cost,
            "unit": loadout.unit,
        },
        "solver_matches_or_beats_template": expected_cost <= template_cost,
        "comparison_source": comparison_source,
        "scope": "bounded ordinary-action graph only; not a global game optimum",
    }
