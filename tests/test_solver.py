"""Focused mathematical checks for the bounded ordinary-action solver.

The H1--H3 and group-identity fixtures are specified in
docs/specs/2026-09-21-bounded-policy-solver.md.  They are abstract MDPs, not
claims about game currency mechanics.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from time import perf_counter

import pytest

from craftoracle.actions import load_action_data
from craftoracle.item_model import ItemState
from craftoracle.plan_inputs import load_spec
from craftoracle.solver import (
    Action,
    ExperimentInputError,
    ExperimentLimits,
    MDPInputError,
    SolverLimits,
    _ExperimentLimit,
    _GraphProgress,
    _roll_outcomes,
    _solver_json,
    run_helmet_experiment,
    solve_mdp,
    weighted_next_group_probability,
)


ROOT = Path(__file__).resolve().parents[1]


def test_h1_geometric_retry_has_value_eight() -> None:
    result = solve_mdp(
        {"S": (Action("retry", 2, {"goal": .25, "S": .75}),)},
        {"goal"},
    )

    assert result.values["S"] == pytest.approx(8)
    assert result.policy["S"] == "retry"
    assert result.residual <= 1e-10
    assert result.converged


def test_h2_prefers_cheap_then_finish() -> None:
    result = solve_mdp(
        {
            "S": (
                Action("cheap", 1, {"T": .5, "S": .5}),
                Action("direct", 6, {"goal": 1}),
            ),
            "T": (Action("finish", 2, {"goal": 1}),),
        },
        {"goal"},
    )

    assert result.values["S"] == pytest.approx(4)
    assert result.values["T"] == pytest.approx(2)
    assert result.policy == {"S": "cheap", "T": "finish", "goal": None}
    assert result.residual <= 1e-10


def test_h3_can_finish_after_a_failed_gamble() -> None:
    result = solve_mdp(
        {
            "A": (
                Action("gamble", 1, {"goal": .25, "B": .75}),
                Action("direct", 7, {"goal": 1}),
            ),
            "B": (
                Action("recover", 2, {"A": 1}),
                Action("finish", 5, {"goal": 1}),
            ),
            "dead": (Action("loop", 1, {"dead": 1}),),
        },
        {"goal"},
    )

    assert result.values["A"] == pytest.approx(4.75)
    assert result.values["B"] == pytest.approx(5)
    assert result.policy["A"] == "gamble"
    assert result.policy["B"] == "finish"
    assert math.isinf(result.values["dead"])
    assert result.policy["dead"] is None
    assert result.unreachable == frozenset({"dead"})
    assert result.residual <= 1e-10


def test_zero_probability_successor_does_not_poison_safe_action() -> None:
    result = solve_mdp(
        {
            "S": (Action("finish", 2, {"goal": 1, "dead": 0}),),
            "dead": (Action("loop", 1, {"dead": 1}),),
        },
        {"goal"},
    )

    assert result.values["S"] == pytest.approx(2)
    assert result.policy["S"] == "finish"
    assert math.isinf(result.values["dead"])


def test_malformed_probability_and_unknown_successor_reject() -> None:
    with pytest.raises(MDPInputError, match="sum to one"):
        solve_mdp({"S": (Action("bad", 1, {"goal": 1.1}),)}, {"goal"})
    with pytest.raises(MDPInputError, match="unknown successor"):
        solve_mdp({"S": (Action("bad", 1, {"missing": 1}),)}, {"goal"})


def test_nonterminal_zero_cost_and_terminal_stop_boundaries() -> None:
    terminal = solve_mdp({}, {"goal"})
    assert terminal.values == {"goal": 0.0}
    assert terminal.policy == {"goal": None}

    with pytest.raises(MDPInputError, match="positive"):
        solve_mdp({"S": (Action("free-loop", 0, {"S": 1}),)}, {"goal"})


def test_nonconvergence_is_json_safe_and_does_not_report_prefix_values() -> None:
    result = solve_mdp(
        {"S": (Action("slow", 1, {"goal": .00001, "S": .99999}),)},
        {"goal"},
        limits=SolverLimits(max_iterations=1),
    )

    assert not result.converged
    assert result.status == "iteration_limit"
    assert math.isinf(result.values["S"])
    assert _solver_json(result)["residual"] is None
    json.dumps(_solver_json(result), allow_nan=False)


def test_junk_identity_cannot_be_collapsed_by_count() -> None:
    # Spec fixture: target A has weight 1; junk B/C have weights 1/9.
    weights = {"A": 1, "B": 1, "C": 9}

    assert weighted_next_group_probability(weights, "A", occupied_groups={"B"}) == pytest.approx(.1)
    assert weighted_next_group_probability(weights, "A", occupied_groups={"C"}) == pytest.approx(.5)


@pytest.fixture(scope="module")
def helmet_inputs():
    data = load_action_data(ROOT)
    spec = load_spec(ROOT / "examples/helmet_life_chaos_res.yaml", data.mods)
    return data, spec, ItemState(spec.base, spec.item_level, "normal")


def test_real_transmute_row_is_concrete_and_normalized(helmet_inputs) -> None:
    data, spec, normal = helmet_inputs
    progress = _GraphProgress(perf_counter())

    outcomes = _roll_outcomes(
        "transmute",
        normal,
        spec,
        data,
        progress,
        ExperimentLimits(max_states=4_000, max_edges=10_000, build_seconds=30),
        ("initial",),
    )

    assert len(outcomes) == 3_569
    assert sum(outcomes.values()) == pytest.approx(1)
    assert progress.partial_edges == 7_138
    assert all(state.rarity == "magic" and state.group_profile for state in outcomes)
    assert all(state.target_tiers and state.junk_prefixes + state.junk_suffixes >= 0 for state in outcomes)


def test_pending_concrete_outcomes_count_against_state_limit(helmet_inputs) -> None:
    data, spec, normal = helmet_inputs
    progress = _GraphProgress(perf_counter())

    with pytest.raises(_ExperimentLimit) as raised:
        _roll_outcomes(
            "transmute",
            normal,
            spec,
            data,
            progress,
            ExperimentLimits(max_states=2, max_edges=10_000, build_seconds=30),
            ("initial",),
        )

    assert raised.value.kind == "states"
    assert progress.pending_concrete_states == 1
    assert progress.states + progress.pending_concrete_states == 2


def test_source_absence_is_an_input_error_not_a_complexity_result(tmp_path: Path) -> None:
    with pytest.raises(ExperimentInputError, match="source_or_input_error"):
        run_helmet_experiment(tmp_path)
