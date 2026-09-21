"""Acceptance checks for the fixed policies in ``night-policies.md``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from craftoracle.actions import ActionData, load_action_data
from craftoracle.costs import geometric_cost
from craftoracle.distributions import OutcomeClass, probability
from craftoracle.item_model import ItemState, ModRef
from craftoracle.plan_inputs import load_loadout, load_spec
from craftoracle.policies import (
    _conditional_distribution,
    _chaos_policy,
    _harvest_distribution,
    _harvest_suffix_representatives,
    _item,
    _labels,
    _selected_mass,
    _success_probability,
    evaluate_policies,
)


ROOT = Path(__file__).parents[1]
ENVT = "Metadata/Items/Currency/CurrencyEssenceEnvy3"
GREED = "Metadata/Items/Currency/CurrencyEssenceGreed7"
HATRED = "Metadata/Items/Currency/CurrencyEssenceHatred7"
ANGER = "Metadata/Items/Currency/CurrencyEssenceAnger6"
WRATH = "Metadata/Items/Currency/CurrencyEssenceWrath5"


@dataclass(frozen=True)
class Criterion:
    group: str
    max_tier: int


@dataclass(frozen=True)
class HelmetSpec:
    base: str = "Royal Burgonet"
    item_level: int = 86
    quality: int = 20
    flags: dict[str, bool] = None  # type: ignore[assignment]
    required_mods: tuple[Criterion, ...] = (
        Criterion("IncreasedLife", 1),
        Criterion("ChaosResistance", 1),
    )
    any_of: tuple[tuple[Criterion, ...], ...] = (
        (Criterion("FireResistance", 1), Criterion("ColdResistance", 1), Criterion("LightningResistance", 1)),
    )
    tier_ids: dict[str, tuple[tuple[str, ...], ...]] = None  # type: ignore[assignment]
    value_table: None = None
    threshold: None = None
    labels: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "flags", {} if self.flags is None else self.flags)
        tier_ids = {
            "IncreasedLife": (("IncreasedLife9",),),
            "ChaosResistance": (("ChaosResist6",),),
            "FireResistance": (("FireResist8",),),
            "ColdResistance": (("ColdResist8",),),
            "LightningResistance": (("LightningResist8",),),
        }
        object.__setattr__(self, "tier_ids", tier_ids if self.tier_ids is None else self.tier_ids)
        labels = {
            "IncreasedLife9": "IncreasedLife:1",
            "ChaosResist6": "ChaosResistance:1",
            "FireResist8": "FireResistance:1",
            "ColdResist8": "ColdResistance:1",
            "LightningResist8": "LightningResistance:1",
        }
        object.__setattr__(self, "labels", labels if self.labels is None else self.labels)

    def matches(self, outcome: object) -> bool:
        labels = getattr(outcome, "labels")
        return (
            "IncreasedLife:1" in labels
            and "ChaosResistance:1" in labels
            and any(label in labels for label in ("FireResistance:1", "ColdResistance:1", "LightningResistance:1"))
        )

    def utility(self, outcome: object) -> float:
        return 1.0 if self.matches(outcome) else 0.0


@dataclass(frozen=True)
class Loadout:
    allowed_actions: frozenset[str]
    allowed_essences: frozenset[str]
    allowed_bench: frozenset[int]
    values: dict[str, float]
    bench_recipes: dict[int, dict[str, float]]
    budget: float = 100_000
    base_cost: float = 0
    unit: str = "chaos"

    def price(self, currency: str) -> float:
        if currency not in self.values:
            raise ValueError(f"missing price: {currency}")
        return self.values[currency]

    def bench_cost(self, index: int) -> float:
        if index not in self.bench_recipes:
            raise ValueError(f"missing bench recipe: {index}")
        return sum(self.price(currency) * quantity for currency, quantity in self.bench_recipes[index].items())

    def permits(self, actions: object, essence_id: str | None = None, bench_index: int | None = None) -> bool:
        requested = {actions} if isinstance(actions, str) else set(actions)  # type: ignore[arg-type]
        return (
            requested <= self.allowed_actions
            and (essence_id is None or essence_id in self.allowed_essences)
            and (bench_index is None or bench_index in self.allowed_bench)
        )


def _loadout(*, essences: frozenset[str] | None = None, bench: frozenset[int] | None = None) -> Loadout:
    return Loadout(
        frozenset({"alchemy", "chaos", "scour", "essence", "transmute", "alteration", "augmentation", "regal", "exalted", "bench", "harvest_reforge:life"}),
        frozenset({ENVT, GREED, HATRED, ANGER, WRATH}) if essences is None else essences,
        frozenset({131, 729}) if bench is None else bench,
        {
            "chaos": 1,
            "alchemy": 0.5,
            "scour": 0.5,
            "transmute": 0.1,
            "alteration": 0.1,
            "augmentation": 0.1,
            "regal": 0.5,
            "exalted": 10,
            "divine": 100,
            ENVT: 5,
            GREED: 5,
            HATRED: 3,
            ANGER: 3,
            WRATH: 3,
            "harvest_reforge:life": 1,
        },
        {729: {"divine": 2}, 131: {"chaos": 2}},
    )


@pytest.fixture(scope="module")
def action_data() -> ActionData:
    return load_action_data(ROOT)


@pytest.fixture(scope="module")
def distribution_cache() -> dict:
    return {}


@pytest.fixture(scope="module")
def evaluated(action_data: ActionData, distribution_cache: dict) -> dict:
    return evaluate_policies(HelmetSpec(), _loadout(), action_data, distribution_cache=distribution_cache)


def _policy(result: dict, policy_id: str) -> dict:
    return next(policy for policy in result["ranked"] if policy["id"] == policy_id)


def _stage(policy: dict, name: str) -> dict:
    return next(stage for stage in policy["stages"] if stage["name"] == name)


def test_helmet_policy_kernel_probabilities_and_costs(evaluated: dict) -> None:
    chaos = _policy(evaluated, "chaos-spam")
    alchemy = _policy(evaluated, "alchemy-scour")
    envy = _policy(evaluated, "essence-CurrencyEssenceEnvy3")
    magic = _policy(evaluated, "magic-regal-exalt")
    protected = _policy(evaluated, "suffix-protected-life")
    harvest = _policy(evaluated, "suffix-protected-harvest-life")
    bench = _policy(evaluated, "suffix-protected-life-bench-131")

    assert _stage(chaos, "chaos trial")["probability"] == pytest.approx(0.000024282088455126466, rel=1e-10)
    assert _stage(alchemy, "alchemy trial")["probability"] == pytest.approx(0.000024282088455126466, rel=1e-10)
    assert _stage(envy, "essence trial")["probability"] == pytest.approx(0.0025940606844434217, rel=1e-10)
    assert _stage(magic, "final six draws")["probability"] == pytest.approx(0.000053545793422886104, rel=1e-10)
    assert _stage(protected, "prepare three suffixes")["probability"] == pytest.approx(0.05567530208498237, rel=1e-10)
    assert _stage(protected, "roll protected life prefix")["probability"] == pytest.approx(1000 / 39275, rel=1e-10)
    assert _stage(harvest, "prepare three suffixes")["probability"] == pytest.approx(0.0556753020849824, rel=1e-10)
    assert _stage(harvest, "roll protected Harvest life prefix")["probability"] > 1 / 13
    assert harvest["full_prefix_failure_probability"] > 0
    assert harvest["expected_cost"] < protected["expected_cost"]
    assert harvest["cost_sample_count"] == 50_000
    assert harvest["cost_seed"] == 20260921
    assert harvest["cost_confidence"] == .99
    assert harvest["cost_p90_interval"][0] <= harvest["cost_p90"] <= harvest["cost_p90_interval"][1]
    assert "Before each Life reforge" in harvest["steps"][1]
    assert any("harvest_reforge:life=1 is an invented D21" in assumption for assumption in harvest["assumptions"])

    chaos_p = _stage(chaos, "chaos trial")["probability"]
    envy_p = _stage(envy, "essence trial")["probability"]
    life_p = _stage(protected, "roll protected life prefix")["probability"]
    assert chaos["expected_cost"] == pytest.approx(0.5 + 1 / chaos_p)
    assert alchemy["expected_cost"] == pytest.approx(1 / chaos_p - 0.5)
    assert envy["expected_cost"] == pytest.approx(5 / envy_p)
    assert protected["expected_cost"] == pytest.approx(5 / _stage(protected, "prepare three suffixes")["probability"] + 210.5 / life_p)
    assert bench["expected_cost"] == pytest.approx(8359.193927854994)
    assert bench["cost_p90"] == pytest.approx(18987)
    assert bench["expected_cost"] == pytest.approx(protected["expected_cost"] + 2)
    assert bench["cost_p90"] == pytest.approx(protected["cost_p90"] + 2)

    for policy in evaluated["ranked"]:
        assert sum(row["probability"] for row in policy["terminal_distribution"]) == pytest.approx(1)
        for stage in policy["stages"]:
            assert sum(row["probability"] for row in stage["attempt_distribution"]) == pytest.approx(1)
        assert policy["assumptions"]
        assert policy["steps"]
        assert policy["decision_points"]


def test_harvest_policy_reports_missing_permission_or_price(action_data: ActionData, distribution_cache: dict) -> None:
    denied = _loadout()
    denied = Loadout(
        denied.allowed_actions - {"harvest_reforge:life"}, denied.allowed_essences, denied.allowed_bench,
        denied.values, denied.bench_recipes,
    )
    result = evaluate_policies(HelmetSpec(), denied, action_data, distribution_cache=distribution_cache)
    assert any(row["id"] == "suffix-protected-harvest-life" and "permit" in " ".join(row["reasons"])
               for row in result["unavailable"])

    missing = _loadout()
    values = dict(missing.values)
    values.pop("harvest_reforge:life")
    result = evaluate_policies(
        HelmetSpec(),
        Loadout(missing.allowed_actions, missing.allowed_essences, missing.allowed_bench, values, missing.bench_recipes),
        action_data,
        distribution_cache=distribution_cache,
    )
    assert any(row["id"] == "suffix-protected-harvest-life" and "missing price" in " ".join(row["reasons"])
               for row in result["unavailable"])


def test_harvest_distribution_cache_tracks_a_mutated_resolved_plan(action_data: ActionData) -> None:
    mods = {
        mod_id: {
            **row,
            "weightKey": list(row["weightKey"]),
            "weightVal": list(row["weightVal"]),
            "modTags": list(row.get("modTags") or []),
        }
        for mod_id, row in action_data.mods.items()
    }
    mutable = ActionData(action_data.bases, mods, action_data.bench, action_data.essences, action_data.rules)
    suffixes = tuple(
        ModRef(mod_id, mods[mod_id]["type"], mods[mod_id]["group"])
        for mod_id in ("ChaosResist6", "FireResist8", "ColdResist8")
    )
    lock = mutable.bench[729]
    item = ItemState("Royal Burgonet", 86, "rare", (*suffixes, ModRef("bench:729", lock["type"], lock["group"])))
    cache: dict = {}
    before = _harvest_distribution(cache, mutable, item, {"IncreasedLife9": "Life9"})
    before_p = probability(before, lambda outcome: "Life9" in outcome.labels)
    mods["IncreasedLife9"]["weightVal"][-1] = 1
    after = _harvest_distribution(cache, mutable, item, {"IncreasedLife9": "Life9"})
    after_p = probability(after, lambda outcome: "Life9" in outcome.labels)

    assert len(cache) == 2
    assert after_p != pytest.approx(before_p)


def test_harvest_representative_suffixes_must_be_in_the_eligible_pool(action_data: ActionData) -> None:
    mods = {mod_id: {**row} for mod_id, row in action_data.mods.items()}
    mods["ColdResist8"]["level"] = 87
    unavailable = ActionData(action_data.bases, mods, action_data.bench, action_data.essences, action_data.rules)

    representatives, reason = _harvest_suffix_representatives(HelmetSpec(), unavailable)

    assert representatives is None
    assert reason == "representative protected suffix ColdResist8 is not in the eligible ordinary suffix pool"


def test_magic_stages_use_outer_cycle_count_and_keep_intermediate_probability(evaluated: dict) -> None:
    magic = _policy(evaluated, "magic-regal-exalt")
    final = _stage(magic, "final six draws")
    for name in ("transmute setup/reset", "magic completion", "regal", "final six draws"):
        assert _stage(magic, name)["expected_attempts"] == pytest.approx(1 / final["probability"])
    assert _stage(magic, "magic completion")["probability"] == 1
    assert _stage(magic, "regal")["probability"] == 1
    assert _stage(magic, "magic completion")["target_probability_after_stage"] == 0
    assert _stage(magic, "regal")["target_probability_after_stage"] >= 0
    assert "magic count weights are 1:1, 2:1 from CoE evidence" in magic["assumptions"]


def test_permission_and_bench_legality_failures_are_explicit(action_data: ActionData, distribution_cache: dict) -> None:
    no_envy = evaluate_policies(HelmetSpec(), _loadout(essences=frozenset({GREED})), action_data, distribution_cache=distribution_cache)
    assert any(row["id"] == "essence-CurrencyEssenceGreed7" and "unreachable" in " ".join(row["reasons"]) for row in no_envy["unavailable"])
    assert not any(row["id"] == "essence-CurrencyEssenceEnvy3" for row in no_envy["ranked"])

    no_lock = evaluate_policies(HelmetSpec(), _loadout(bench=frozenset({131})), action_data, distribution_cache=distribution_cache)
    assert any(row["id"] == "suffix-protected-life" and "bench 729" in " ".join(row["reasons"]) for row in no_lock["unavailable"])

    conflicting = ActionData(action_data.bases, action_data.mods, dict(action_data.bench), action_data.essences, action_data.rules)
    conflicting.bench[131] = {**conflicting.bench[131], "group": "IncreasedLife"}
    result = evaluate_policies(HelmetSpec(), _loadout(), conflicting, distribution_cache=distribution_cache)
    assert _policy(result, "suffix-protected-life")
    assert any(row["id"] == "suffix-protected-life-bench-131" and "life group" in " ".join(row["reasons"]) for row in result["unavailable"])

    suffix_conflict = ActionData(action_data.bases, action_data.mods, dict(action_data.bench), action_data.essences, action_data.rules)
    suffix_conflict.bench[131] = {**suffix_conflict.bench[131], "group": "ChaosResistance"}
    result = evaluate_policies(HelmetSpec(), _loadout(), suffix_conflict, distribution_cache=distribution_cache)
    assert any(row["id"] == "suffix-protected-life-bench-131" and "suffix group" in " ".join(row["reasons"]) for row in result["unavailable"])

    disallowed = evaluate_policies(HelmetSpec(), _loadout(bench=frozenset({729})), action_data, distribution_cache=distribution_cache)
    assert _policy(disallowed, "suffix-protected-life")
    assert any(row["id"] == "suffix-protected-life-bench-131" and "does not permit bench 131" in " ".join(row["reasons"]) for row in disallowed["unavailable"])


def test_policy_guards_reject_illegal_repeat_target_cycle_and_q9(
    action_data: ActionData, distribution_cache: dict, evaluated: dict
) -> None:
    tier_one = next(essence_id for essence_id, row in action_data.essences.items() if row["tier"] == 1)
    low_tier = evaluate_policies(
        HelmetSpec(),
        _loadout(essences=frozenset({tier_one})),
        action_data,
        distribution_cache=distribution_cache,
    )
    assert any(row["id"] == f"essence-{tier_one.rsplit('/', 1)[-1]}" and "tier 5 or higher" in " ".join(row["reasons"]) for row in low_tier["unavailable"])

    wrong_any_of = HelmetSpec(
        any_of=(
            (Criterion("FireResistance", 1),),
            (Criterion("ColdResistance", 1), Criterion("LightningResistance", 1)),
        )
    )
    wrong_target = evaluate_policies(wrong_any_of, _loadout(), action_data, distribution_cache=distribution_cache)
    assert any(row["id"] == "suffix-protected-life" and "elemental-any" in " ".join(row["reasons"]) for row in wrong_target["unavailable"])

    exhausted = ActionData(
        action_data.bases,
        {mod_id: action_data.mods[mod_id] for mod_id in ("IncreasedLife9", "ChaosResist6")},
        action_data.bench,
        action_data.essences,
        action_data.rules,
    )
    exhausted_result = evaluate_policies(HelmetSpec(), _loadout(essences=frozenset({ENVT})), exhausted, distribution_cache=distribution_cache)
    assert any(row["id"] == "magic-regal-exalt" and "pool exhausts" in " ".join(row["reasons"]) for row in exhausted_result["unavailable"])

    altered_rules = dict(action_data.rules)
    altered_rules["magic_count_weights"] = {"1": 1, "3": 1}
    incompatible_magic = ActionData(action_data.bases, action_data.mods, action_data.bench, action_data.essences, altered_rules)
    incompatible_result = evaluate_policies(HelmetSpec(), _loadout(), incompatible_magic, distribution_cache=distribution_cache)
    assert any(row["id"] == "magic-regal-exalt" and "one- and two-mod" in " ".join(row["reasons"]) for row in incompatible_result["unavailable"])

    protected = _policy(evaluated, "suffix-protected-life")
    assert all("ChaosResistance:1" in row["labels"] for row in _stage(protected, "roll protected life prefix")["attempt_distribution"])
    bench = _policy(evaluated, "suffix-protected-life-bench-131")
    assert _stage(bench, "deterministic bench finish")["attempt_distribution"] == bench["terminal_distribution"]

    with pytest.raises(NotImplementedError, match="out of tonight's slice: Q9"):
        evaluate_policies(HelmetSpec(flags={"corrupted": True}), _loadout(), action_data)


def test_cache_key_changes_when_action_rules_change(action_data: ActionData) -> None:
    rules = dict(action_data.rules)
    rules["rare_count_weights"] = dict(action_data.rules["rare_count_weights"])
    mutable_data = ActionData(action_data.bases, action_data.mods, action_data.bench, action_data.essences, rules)
    cache: dict = {}
    spec = HelmetSpec()
    labels = _labels(spec)
    first = _chaos_policy(spec, _loadout(), mutable_data, _item(spec, "normal"), _item(spec, "rare"), labels, cache)
    rules["rare_count_weights"] = {"4": 1, "5": 1, "6": 10}
    second = _chaos_policy(spec, _loadout(), mutable_data, _item(spec, "normal"), _item(spec, "rare"), labels, cache)

    assert _stage(first, "chaos trial")["probability"] != pytest.approx(
        _stage(second, "chaos trial")["probability"]
    )


def test_kernel_tolerance_normalizes_an_all_success_probability_before_costs() -> None:
    class AllSuccess:
        value_table = None

        @staticmethod
        def matches(outcome: object) -> bool:
            return True

        @staticmethod
        def utility(outcome: object) -> float:
            return 1

    distribution = {OutcomeClass(("target",), 1, 0): 1 + 5e-11}
    success = _success_probability(AllSuccess(), distribution)
    assert success == 1
    assert geometric_cost(success, 2).expected_cost == 2
    assert sum(_conditional_distribution(AllSuccess(), distribution).values()) == 1

    multiclass = {
        OutcomeClass(("target-a",), 1, 0): 0.2,
        OutcomeClass(("target-b",), 0, 1): 0.2,
        OutcomeClass(("target-c",), 1, 1): 0.2,
        OutcomeClass(("target-d",), 2, 1): 0.2,
        OutcomeClass(("target-e",), 1, 2): 0.2,
    }
    assert _selected_mass(AllSuccess(), multiclass) == pytest.approx(1)
    assert _success_probability(AllSuccess(), multiclass) == 1
    assert geometric_cost(_success_probability(AllSuccess(), multiclass), 2).expected_cost == 2


def test_accepted_planner_inputs_share_the_same_contract(action_data: ActionData, distribution_cache: dict) -> None:
    spec = load_spec(ROOT / "examples/helmet_life_chaos_res.yaml", action_data.mods)
    loadout = load_loadout(ROOT / "data/loadouts/endgame.json")
    result = evaluate_policies(spec, loadout, action_data, distribution_cache=distribution_cache)

    assert len(result["ranked"]) >= 3
    assert _policy(result, "suffix-protected-life-bench-131")["expected_cost"] == pytest.approx(8359.193927854994)
    assert all("p90_over_budget" in policy for policy in result["ranked"])


def test_price_changes_reuse_raw_distributions_without_changing_probability(
    action_data: ActionData, evaluated: dict, distribution_cache: dict
) -> None:
    original = _loadout()
    doubled = Loadout(
        original.allowed_actions,
        original.allowed_essences,
        original.allowed_bench,
        {currency: 2 * price for currency, price in original.values.items()},
        original.bench_recipes,
        budget=2 * original.budget,
        base_cost=2 * original.base_cost,
    )
    double_result = evaluate_policies(HelmetSpec(), doubled, action_data, distribution_cache=distribution_cache)
    original_by_id = {policy["id"]: policy for policy in evaluated["ranked"]}
    for policy in double_result["ranked"]:
        before = original_by_id[policy["id"]]
        assert policy["expected_cost"] == pytest.approx(2 * before["expected_cost"])
        assert policy["cost_p90"] == pytest.approx(2 * before["cost_p90"])
        assert [stage["probability"] for stage in policy["stages"]] == pytest.approx(
            [stage["probability"] for stage in before["stages"]]
        )

    repriced_values = dict(original.values)
    repriced_values[ENVT] = 100_000
    repriced = Loadout(
        original.allowed_actions,
        original.allowed_essences,
        original.allowed_bench,
        repriced_values,
        original.bench_recipes,
    )
    repriced_result = evaluate_policies(HelmetSpec(), repriced, action_data, distribution_cache=distribution_cache)
    assert [policy["id"] for policy in repriced_result["ranked"]] != [policy["id"] for policy in evaluated["ranked"]]
    assert _stage(_policy(repriced_result, "essence-CurrencyEssenceEnvy3"), "essence trial")["probability"] == pytest.approx(
        _stage(_policy(evaluated, "essence-CurrencyEssenceEnvy3"), "essence trial")["probability"]
    )
