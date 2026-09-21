"""Regression checks for the bounded policy-parameter optimizer.

The gate fixture is the hand-computed review1 case from
``docs/specs/2026-09-21-template-optimizer.md`` and the lead's 2026-09-21
review correction.  It is mathematical policy input, not a game fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

import craftoracle.optimizer as optimizer
from craftoracle.actions import ActionData
from craftoracle.distributions import DrawEntry, OutcomeClass
from craftoracle.item_model import ItemState, resolve_pool
from craftoracle.optimizer import (
    _chaos_mean,
    _magic_policy_stages,
    _magic_schedule,
    _magic_terminal_distribution,
    _magic_prefix_distribution,
    _merge_level_results,
    parse_item_level_range,
    _reached_stage_indices,
    _search_levels,
)
from craftoracle.policy_attempts import evaluate_grouped_schedule


def test_magic_gate_rejection_cannot_reenter_terminal_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    # First two draws have AC=1/8, AD=1/8, BC=3/8, BD=3/8.  C alone is
    # utility 60, but the two-desired-label gate deliberately rejects BC.
    entries = (
        DrawEntry("A", "Prefix", "A", 1),
        DrawEntry("B", "Prefix", "B", 3),
        DrawEntry("C", "Suffix", "C", 2),
        DrawEntry("D", "Suffix", "D", 2),
    )
    labels = {entry.mod_id: entry.mod_id for entry in entries}
    schedule = evaluate_grouped_schedule(
        entries,
        labels,
        ((2, 1, 1), (1, 3, 3)),
        (lambda outcome: sum(label in {"A", "C"} for label in outcome.labels) >= 2, None),
        # Threshold 60 accepts C alone; the policy gate remains stricter.
        lambda outcome: "C" in outcome.labels,
        early_stop=False,
    )

    first_failure = schedule.failure_by_stage[0]
    assert first_failure[OutcomeClass(("B", "C"), 1, 1)] == pytest.approx(3 / 8)
    terminal = _magic_terminal_distribution(schedule)
    assert sum(terminal.values()) == pytest.approx(1)
    assert all({"A", "C"}.issubset(outcome.labels) for outcome in terminal)

    class Target:
        threshold = None
        required_mods = ()
        any_of = ()
        value_table = None

        @staticmethod
        def matches(outcome: OutcomeClass) -> bool:
            return "C" in outcome.labels

    Target.labels = labels

    gates = (
        lambda outcome: sum(label in {"A", "C"} for label in outcome.labels) >= 2,
        None,
    )
    first = _magic_prefix_distribution(
        {}, entries, labels, frozenset({"A", "C"}), ((2, 1, 1), (1, 3, 3)), gates, Target(), False, 0
    )
    second = _magic_prefix_distribution(
        {}, entries, labels, frozenset({"A", "C"}), ((2, 1, 1), (1, 3, 3)), gates, Target(), False, 1
    )
    assert first[OutcomeClass(("A", "C"), 1, 1)] == pytest.approx(1 / 8)
    assert first[OutcomeClass(("B", "C"), 1, 1)] == pytest.approx(3 / 8)
    assert {outcome.prefixes + outcome.suffixes for outcome in first} == {2}
    assert {outcome.prefixes + outcome.suffixes for outcome in second} == {3}
    assert all({"A", "C"}.issubset(outcome.labels) for outcome in second)

    # Exercise the optimizer's terminal serialization path too.  The staged
    # schedule is the hand fixture above; p90 is outside this terminal-mass
    # regression, so keep its tie-breaker deterministic and tiny.
    optimizer_labels = {mod_id: f"{mod_id}:1" for mod_id in labels}

    class Target:
        base = "fixture"
        item_level = 1
        flags: dict[str, bool] = {}
        labels = optimizer_labels
        required_mods = ()
        any_of = ()
        tier_ids: dict[str, tuple[tuple[str, ...], ...]] = {}
        value_table = {"A": {1: 40.0}, "C": {1: 60.0}}
        threshold = 60.0

        @staticmethod
        def utility(outcome: OutcomeClass) -> float:
            return 60.0 if "C:1" in outcome.labels else 0.0

    class Loadout:
        allowed_bench = frozenset()
        base_cost = 0.0
        budget = 10_000.0
        unit = "fixture"

        @staticmethod
        def permits(*_args, **_kwargs) -> bool:
            return True

        @staticmethod
        def price(_currency: str) -> float:
            return 1.0

    def forced_schedule(_cache, _entries, _labels, _desired, stages, _gates, _spec, _early_stop):
        gates = (
            lambda outcome: sum(label in {"A:1", "C:1"} for label in outcome.labels) >= 2,
            *(None for _ in stages[1:]),
        )
        return evaluate_grouped_schedule(
            entries,
            optimizer_labels,
            stages,
            gates,
            lambda outcome: "C:1" in outcome.labels,
            early_stop=False,
        )

    def attach_tiny_p90(row, *_args) -> None:
        row["p90"] = 0.0
        row["estimate"] = SimpleNamespace(
            interval_lower=0.0, interval_upper=0.0, samples=1,
            confidence=1.0, dkw_epsilon=0.0,
        )

    monkeypatch.setattr(optimizer, "prepare_roll", lambda *_args, **_kwargs: SimpleNamespace(entries=entries))
    monkeypatch.setattr(optimizer, "_magic_schedule", forced_schedule)
    monkeypatch.setattr(optimizer, "_attach_magic_p90", attach_tiny_p90)
    monkeypatch.setattr(
        optimizer._fixed,
        "_action_distribution",
        lambda *_args, **_kwargs: {OutcomeClass(("A:1",), 1, 0): 1.0},
    )
    policy = optimizer._optimized_magic(
        Target(),
        Loadout(),
        SimpleNamespace(rules={"magic_caps": (1, 1), "rare_caps": (3, 3), "magic_count_weights": {"1": 1, "2": 1}}),
        {},
    )

    assert policy["expected_utility"] == 60.0
    assert all({"A:1", "C:1"}.issubset(row["labels"]) for row in policy["terminal_distribution"])


def test_magic_early_all_success_skips_unreached_stage_distributions(monkeypatch: pytest.MonkeyPatch) -> None:
    schedule = evaluate_grouped_schedule(
        (DrawEntry("A", "Prefix", "A", 1),),
        {"A": "A"},
        ((1, 3, 3), (1, 3, 3)),
        (None, None),
        lambda outcome: "A" in outcome.labels,
        early_stop=True,
    )
    assert _reached_stage_indices(schedule) == (0,)
    assert _magic_terminal_distribution(schedule) == {
        OutcomeClass(("A",), 1, 0): pytest.approx(1),
    }

    class Target:
        base = "fixture"
        item_level = 1
        flags: dict[str, bool] = {}

        @staticmethod
        def matches(outcome: OutcomeClass) -> bool:
            return "A" in outcome.labels

    selected = {"parameters": {"max_exalts": 2, "magic_min_desired": 0, "regal_min_desired": 0, "early_stop": True}}
    monkeypatch.setattr(
        optimizer._fixed,
        "_action_distribution",
        lambda *_args, **_kwargs: {OutcomeClass(("A",), 1, 0): 1.0},
    )
    stages = _magic_policy_stages(
        schedule,
        selected,
        {"transmute": 1.0, "alteration": 1.0, "augmentation": 1.0, "regal": 1.0, "exalted": 1.0},
        Target(),
        {"A": "A"},
        {},
        SimpleNamespace(),
        SimpleNamespace(),
        (DrawEntry("A", "Prefix", "A", 1),),
        frozenset({"A"}),
    )
    assert [stage["name"] for stage in stages] == ["transmute setup/reset", "magic two-mod gate"]


def test_incomplete_level_row_is_preserved_over_a_completed_same_id_row() -> None:
    complete = {
        "ranked": [{"id": "magic", "expected_cost": 10.0, "cost_p90": 20.0, "parameters": {}, "candidate_count": 1, "parameter_audit": []}],
        "unavailable": [], "assumptions": ["fixture"], "unit": "c",
    }
    incomplete = {
        "ranked": [],
        "unavailable": [{"id": "magic", "name": "Magic", "reasons": ["work limit"], "optimization_status": {"complete": False}}],
        "assumptions": ["fixture"], "unit": "c",
    }
    merged = _merge_level_results((complete, incomplete))
    assert merged["ranked"] == []
    assert merged["unavailable"][0]["id"] == "magic"
    assert "no cross-level optimum" in merged["unavailable"][0]["reasons"][-1]


def test_chaos_early_setup_formula_matches_the_documented_fixture() -> None:
    assert _chaos_mean(0.25, 0.5, 2.0, 3.0, False) == pytest.approx(8.0)
    assert _chaos_mean(0.25, 0.5, 2.0, 3.0, True) == pytest.approx(6.5)


@dataclass(frozen=True)
class _LevelSpec:
    base: str = "Fixture"
    item_level: int = 25
    flags: dict[str, bool] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "flags", {} if self.flags is None else self.flags)


def test_level_breakpoints_deduplicate_pools_without_downgrading_target() -> None:
    def row(group: str, level: int) -> dict[str, object]:
        return {
            "type": "Prefix", "group": group, "level": level,
            "weightKey": ["fixture"], "weightVal": [100],
            "source_path": "Data/ModExplicit.lua",
        }

    data = ActionData(
        {"Fixture": {"name": "Fixture", "tags": {"fixture": True}}},
        {"baseline": row("Baseline", 10), "Target20": row("Target20", 20)},
        {}, {}, {},
    )
    levels, requested, pools = _search_levels(_LevelSpec(), data, "10:25")
    low_pool = resolve_pool(ItemState("Fixture", 10, "rare"), data.bases, data.mods)
    high_pool = resolve_pool(ItemState("Fixture", 20, "rare"), data.bases, data.mods)

    assert requested == (10, 25)
    assert levels == [10, 20]
    assert pools == 2
    assert "Target20" not in {entry.mod_id for entry in low_pool}
    assert "Target20" in {entry.mod_id for entry in high_pool}


def test_magic_schedule_cache_tracks_changed_draw_inputs() -> None:
    class Target:
        labels = {"target": "target", "other": "other"}
        required_mods = ()
        any_of = ()
        value_table = None
        threshold = None

        @staticmethod
        def matches(outcome: OutcomeClass) -> bool:
            return "target" in outcome.labels

    cache: dict = {}
    first = _magic_schedule(
        cache,
        (DrawEntry("target", "Prefix", "target", 1), DrawEntry("other", "Prefix", "other", 1)),
        Target.labels,
        frozenset({"target"}),
        ((1, 3, 3),),
        (None,),
        Target(),
        True,
    )
    second = _magic_schedule(
        cache,
        (DrawEntry("target", "Prefix", "target", 1), DrawEntry("other", "Prefix", "other", 3)),
        Target.labels,
        frozenset({"target"}),
        ((1, 3, 3),),
        (None,),
        Target(),
        True,
    )

    assert len(cache) == 2
    assert first.success_probability == pytest.approx(0.5)
    assert second.success_probability == pytest.approx(0.25)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10:25", (10, 25)),
        ((10, 25), (10, 25)),
    ],
)
def test_item_level_range_is_explicit_and_inclusive(value: object, expected: tuple[int, int]) -> None:
    assert parse_item_level_range(value) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ("10", "25:10", "x:25", (True, 25)))
def test_item_level_range_rejects_invalid_endpoints(value: object) -> None:
    with pytest.raises(ValueError, match="item level range"):
        parse_item_level_range(value)  # type: ignore[arg-type]
