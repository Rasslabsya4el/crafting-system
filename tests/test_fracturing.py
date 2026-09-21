"""Known answers for ordinary Fracturing Orb identity transitions.

Rules: ``docs/mechanics/fracturing.md`` and
``docs/specs/2026-09-21-fractured-item-actions.md``.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import pytest

from craftoracle.actions import (
    ActionData,
    action_distribution,
    apply_roll,
    load_action_data,
    prepare_roll,
    prepare_roll_plan,
    sample_roll,
)
from craftoracle.distributions import OutcomeClass, probability
from craftoracle.fracturing import apply_fracturing, fracture_distribution
from craftoracle.fossils import fossil_distribution
from craftoracle.harvest import harvest_distribution
from craftoracle.item_model import ItemState, ModRef
from craftoracle.plan_inputs import load_spec


ROOT = Path(__file__).parents[1]


def _mod(mod_id: str, side: str, group: str, *, weight: int = 1) -> dict:
    return {
        "id": mod_id,
        "type": side,
        "group": group,
        "level": 1,
        "weightKey": ["default"],
        "weightVal": [weight],
        "modTags": [],
        "source_path": "ModExplicit.lua",
    }


@pytest.fixture()
def toy_data() -> ActionData:
    mods = {
        "A": _mod("A", "Prefix", "A"),
        "B": _mod("B", "Suffix", "B"),
        "C": _mod("C", "Prefix", "C"),
        "D": _mod("D", "Suffix", "D"),
        "E": _mod("E", "Prefix", "E"),
        "F": _mod("F", "Suffix", "F"),
        "Forced": _mod("Forced", "Suffix", "Forced"),
        "ForcedA": _mod("ForcedA", "Suffix", "A"),
    }
    return ActionData(
        bases={"Base": {"name": "Base", "type": "Helmet", "tags": {"default": True}}},
        mods=mods,
        bench={
            728: {
                "source_index": 728,
                "type": "Suffix",
                "group": "ItemGenerationCannotChangePrefixes",
                "types": {"Helmet": True},
                "modTags": [],
            },
        },
        essences={
            "forced": {"id": "forced", "tier": 5, "mods": {"Helmet": "Forced"}},
            "conflict": {"id": "conflict", "tier": 5, "mods": {"Helmet": "ForcedA"}},
        },
        rules={
            "magic_caps": [1, 1],
            "rare_caps": [3, 3],
            "magic_count_weights": {"1": 1, "2": 1},
            "rare_count_weights": {"4": 8, "5": 3, "6": 1},
        },
    )


def _ref(mod_id: str, side: str, group: str) -> ModRef:
    return ModRef(mod_id, side, group)


def _four_mod_rare() -> ItemState:
    return ItemState("Base", 1, "rare", (
        _ref("A", "Prefix", "A"),
        _ref("B", "Suffix", "B"),
        _ref("C", "Prefix", "C"),
        _ref("D", "Suffix", "D"),
    ))


def test_fracturing_uniform_states_and_input_immutability(toy_data: ActionData) -> None:
    source = _four_mod_rare()
    distribution = fracture_distribution(source, toy_data)
    assert source.fractured is False
    assert source.fractured_mod_id is None
    assert len(distribution) == 4
    assert set(outcome.fractured_mod_id for outcome in distribution) == {"A", "B", "C", "D"}
    assert all(outcome.fractured for outcome in distribution)
    assert all(outcome.mods == source.mods for outcome in distribution)
    assert all(chance == pytest.approx(1 / 4) for chance in distribution.values())
    assert sum(chance for outcome, chance in distribution.items() if outcome.fractured_mod_id in {"A", "B"}) == pytest.approx(1 / 2)

    six = ItemState("Base", 1, "rare", (*source.mods, _ref("E", "Prefix", "E"), _ref("F", "Suffix", "F")))
    six_outcomes = fracture_distribution(six, toy_data)
    assert six_outcomes[next(outcome for outcome in six_outcomes if outcome.fractured_mod_id == "A")] == pytest.approx(1 / 6)
    with pytest.raises(ValueError, match="already fractured"):
        fracture_distribution(next(iter(distribution)), toy_data)


def test_fracturing_sampling_replays_and_validates_rng(toy_data: ActionData) -> None:
    source = _four_mod_rare()
    first = apply_fracturing(source, toy_data, random.Random(20260921))
    second = apply_fracturing(source, toy_data, random.Random(20260921))
    assert first == second
    assert first.fractured_mod_id in {"A", "B", "C", "D"}
    assert source.fractured_mod_id is None
    with pytest.raises(ValueError, match="random.Random"):
        apply_fracturing(source, toy_data, object())  # type: ignore[arg-type]


def test_fracturing_gates_and_only_ordinary_explicit_mods(toy_data: ActionData) -> None:
    with pytest.raises(ValueError, match="at least four"):
        fracture_distribution(ItemState("Base", 1, "rare", _four_mod_rare().mods[:3]), toy_data)
    with pytest.raises(ValueError, match="rare"):
        fracture_distribution(ItemState("Base", 1, "magic", _four_mod_rare().mods), toy_data)
    bench = ItemState("Base", 1, "rare", (*_four_mod_rare().mods[:3], _ref("bench:728", "Suffix", "ItemGenerationCannotChangePrefixes")))
    with pytest.raises(ValueError, match="ordinary explicit"):
        fracture_distribution(bench, toy_data)


def test_real_fracture_then_envy_exact_and_seeded_mc() -> None:
    data = load_action_data(ROOT)
    def ref(mod_id: str) -> ModRef:
        row = data.mods[mod_id]
        return ModRef(mod_id, row["type"], row["group"])

    source = ItemState("Royal Burgonet", 86, "rare", tuple(
        ref(mod_id) for mod_id in ("IncreasedLife9", "ChaosResist6", "FireResist8", "ColdResist8")
    ))
    fractures = fracture_distribution(source, data)
    life = next(outcome for outcome in fractures if outcome.fractured_mod_id == "IncreasedLife9")
    assert fractures[life] == pytest.approx(1 / 4)
    assert len(fractures) == 4

    spec = load_spec(ROOT / "examples/helmet_life_chaos_res.yaml", data.mods)
    exact = action_distribution("essence", life, data, spec.labels, essence_id="CurrencyEssenceEnvy3")
    target_probability = probability(exact, spec.matches)
    assert len(exact) == 30
    assert target_probability == pytest.approx(0.06101200110346221)

    plan = prepare_roll_plan("essence", life, data, essence_id="CurrencyEssenceEnvy3")
    rng = random.Random(20260921)
    samples = [sample_roll(plan, rng) for _ in range(10_000)]
    def sample_matches(sample: ItemState) -> bool:
        labels = tuple(sorted(spec.labels[mod.id] for mod in sample.mods if mod.id in spec.labels))
        prefixes = sum(mod.type == "Prefix" for mod in sample.mods)
        suffixes = sum(mod.type == "Suffix" for mod in sample.mods)
        return spec.matches(OutcomeClass(labels, prefixes, suffixes))
    successes = sum(sample_matches(sample) for sample in samples)
    observed = successes / len(samples)
    bound = math.sqrt(math.log(2 / 0.001) / (2 * len(samples)))
    assert bound == pytest.approx(0.019494746035204052)
    assert abs(observed - target_probability) <= bound
    assert all(sample.fractured_mod_id == "IncreasedLife9" for sample in samples)
    assert all(next(mod for mod in sample.mods if mod.id == "IncreasedLife9") == ref("IncreasedLife9") for sample in samples)
    assert apply_roll("essence", life, data, rng=random.Random(7), essence_id="CurrencyEssenceEnvy3") == sample_roll(plan, random.Random(7))
    with pytest.raises(NotImplementedError, match="Q9"):
        harvest_distribution(life, data, "life")
    with pytest.raises(NotImplementedError, match="Q9"):
        fossil_distribution(life, data, [13])


def test_essence_retains_fracture_counts_groups_and_source_immutability(toy_data: ActionData) -> None:
    source = ItemState("Base", 1, "rare", _four_mod_rare().mods, fractured=True, fractured_mod_id="A")
    scenario = prepare_roll(
        "essence", source, toy_data, {"A": "fracture", "Forced": "forced"}, essence_id="forced"
    )
    assert scenario.draw_counts == ((2, 8), (3, 3), (4, 1))
    assert scenario.initial_prefixes == 1
    assert scenario.initial_suffixes == 1
    assert scenario.blocked_groups == ("A", "Forced")
    assert source.mods == _four_mod_rare().mods
    plan = prepare_roll_plan("essence", source, toy_data, essence_id="forced")
    original_weight = next(entry.weight for entry in plan.scenario.entries if entry.mod_id == "B")
    toy_data.mods["B"]["weightVal"][0] = 17
    fresh_plan = prepare_roll_plan("essence", source, toy_data, essence_id="forced")
    assert next(entry.weight for entry in plan.scenario.entries if entry.mod_id == "B") == original_weight
    assert next(entry.weight for entry in fresh_plan.scenario.entries if entry.mod_id == "B") == 17
    assert sample_roll(plan, random.Random(3)) == sample_roll(plan, random.Random(3))
    with pytest.raises(ValueError, match="conflicts with fractured"):
        prepare_roll(
            "essence", source, toy_data, essence_id="conflict"
        )
    veiled_data = ActionData(
        toy_data.bases,
        {**toy_data.mods, "Veiled": {**_mod("Veiled", "Prefix", "Veiled"), "source_path": "ModVeiled.lua"}},
        toy_data.bench,
        toy_data.essences,
        toy_data.rules,
    )
    with pytest.raises(ValueError, match="ordinary explicit"):
        prepare_roll(
            "chaos",
            ItemState("Base", 1, "rare", (_ref("Veiled", "Prefix", "Veiled"),), fractured=True, fractured_mod_id="Veiled"),
            veiled_data,
        )
