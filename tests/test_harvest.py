"""Known-answer checks for accepted ordinary tagged Harvest reforges.

The fixtures reproduce the hand examples in ``docs/mechanics/harvest.md``.
"""

from __future__ import annotations

import math
from pathlib import Path
import random

import pytest

from craftoracle.actions import ActionData, action_distribution, load_action_data
from craftoracle.distributions import OutcomeClass, probability
from craftoracle.harvest import apply_harvest, harvest_distribution
from craftoracle.item_model import ItemState, ModRef


ROOT = Path(__file__).parents[1]


def _mod(mod_id: str, side: str, group: str, *, weight: int = 1, tags=()) -> dict:
    return {
        "id": mod_id,
        "type": side,
        "group": group,
        "level": 1,
        "weightKey": ["default"],
        "weightVal": [weight],
        "modTags": list(tags),
        "source_path": "ModExplicit.lua",
    }


def _bench(index: int, side: str, group: str) -> dict:
    return {
        "source_index": index,
        "type": side,
        "group": group,
        "types": {"Helmet": True},
        "modTags": [],
    }


def _ref(mod_id: str, side: str, group: str) -> ModRef:
    return ModRef(mod_id, side, group)


def _with_rare_counts(data: ActionData, counts: dict[str, int]) -> ActionData:
    rules = dict(data.rules)
    rules["rare_count_weights"] = counts
    return ActionData(data.bases, data.mods, data.bench, data.essences, rules)


@pytest.fixture()
def simple_data() -> ActionData:
    return ActionData(
        bases={"Base": {"name": "Base", "type": "Helmet", "tags": {"default": True}}},
        mods={
            "A": _mod("A", "Prefix", "L", weight=1, tags=("life",)),
            "B": _mod("B", "Prefix", "L", weight=3, tags=("life",)),
            "X": _mod("X", "Prefix", "X", weight=2, tags=("attack",)),
            "Y": _mod("Y", "Prefix", "Y", weight=2),
            "S1": _mod("S1", "Suffix", "S1"),
            "S2": _mod("S2", "Suffix", "S2"),
            "S3": _mod("S3", "Suffix", "S3"),
        },
        bench={729: _bench(729, "Prefix", "ItemGenerationCannotChangeSuffixes")},
        essences={},
        rules={
            "magic_caps": [1, 1], "rare_caps": [3, 3],
            "magic_count_weights": {"1": 1, "2": 1},
            "rare_count_weights": {"4": 8, "5": 3, "6": 1},
        },
    )


def _locked_suffixes() -> tuple[ModRef, ...]:
    return (
        _ref("S1", "Suffix", "S1"), _ref("S2", "Suffix", "S2"), _ref("S3", "Suffix", "S3"),
        _ref("bench:729", "Prefix", "ItemGenerationCannotChangeSuffixes"),
    )


def test_hand_examples_for_counts_and_forced_weight(simple_data: ActionData) -> None:
    item = ItemState("Base", 1, "rare", _locked_suffixes())
    labels = {"A": "A", "B": "B", "X": "X", "Y": "Y"}
    distribution = harvest_distribution(item, simple_data, "life", labels)
    assert sum(distribution.values()) == pytest.approx(1, abs=1e-10)
    assert probability(distribution, lambda outcome: "A" in outcome.labels) == pytest.approx(1 / 4)
    assert probability(distribution, lambda outcome: outcome.prefixes == 1) == pytest.approx(2 / 3)
    assert probability(distribution, lambda outcome: outcome.prefixes == 2) == pytest.approx(1 / 4)
    assert probability(distribution, lambda outcome: outcome.prefixes == 3) == pytest.approx(1 / 12)

    count_four = harvest_distribution(item, _with_rare_counts(simple_data, {"4": 1}), "life", labels)
    assert count_four == {
        OutcomeClass(("A",), 1, 3): pytest.approx(1 / 4),
        OutcomeClass(("B",), 1, 3): pytest.approx(3 / 4),
    }
    count_five = harvest_distribution(item, _with_rare_counts(simple_data, {"5": 1}), "life", labels)
    assert count_five == {
        OutcomeClass(tuple(sorted(("A", "X"))), 2, 3): pytest.approx(1 / 8),
        OutcomeClass(tuple(sorted(("A", "Y"))), 2, 3): pytest.approx(1 / 8),
        OutcomeClass(tuple(sorted(("B", "X"))), 2, 3): pytest.approx(3 / 8),
        OutcomeClass(tuple(sorted(("B", "Y"))), 2, 3): pytest.approx(3 / 8),
    }


def test_first_only_and_all_draws_use_original_attack_flag() -> None:
    data = ActionData(
        bases={"Base": {"name": "Base", "type": "Helmet", "tags": {"default": True}}},
        mods={
            "A": _mod("A", "Prefix", "A", weight=1, tags=("life", "attack")),
            "B": _mod("B", "Prefix", "B", weight=3, tags=("life",)),
            "X": _mod("X", "Prefix", "X", weight=2, tags=("attack",)),
            "Y": _mod("Y", "Prefix", "Y", weight=2),
            "S": _mod("S", "Suffix", "S"),
        },
        bench={
            729: _bench(729, "Prefix", "ItemGenerationCannotChangeSuffixes"),
            730: _bench(730, "Suffix", "ItemGenerationCanHaveMultipleCraftedMods"),
            731: _bench(731, "Suffix", "ItemGenerationCannotRollAttackAffixes"),
        },
        essences={},
        rules={"magic_caps": [1, 1], "rare_caps": [3, 3], "magic_count_weights": {"1": 1}, "rare_count_weights": {"4": 8, "5": 3, "6": 1}},
    )
    item = ItemState("Base", 1, "rare", (
        _ref("S", "Suffix", "S"), _ref("bench:730", "Suffix", "ItemGenerationCanHaveMultipleCraftedMods"),
        _ref("bench:731", "Suffix", "ItemGenerationCannotRollAttackAffixes"),
        _ref("bench:729", "Prefix", "ItemGenerationCannotChangeSuffixes"),
    ))
    labels = {"A": "A", "B": "B", "X": "X", "Y": "Y"}
    data = _with_rare_counts(data, {"5": 1})
    first_only = harvest_distribution(item, data, "life", labels)
    assert first_only == {
        OutcomeClass(tuple(sorted(("B", "A"))), 2, 3): pytest.approx(1 / 5),
        OutcomeClass(tuple(sorted(("B", "X"))), 2, 3): pytest.approx(2 / 5),
        OutcomeClass(tuple(sorted(("B", "Y"))), 2, 3): pytest.approx(2 / 5),
    }
    all_draws = harvest_distribution(item, data, "life", labels, type_filter="all_draws")
    assert all_draws == {OutcomeClass(tuple(sorted(("B", "Y"))), 2, 3): pytest.approx(1)}


def test_apply_harvest_uses_direct_seeded_draws_and_preserves_protected_side(simple_data: ActionData) -> None:
    item = ItemState("Base", 1, "rare", _locked_suffixes())
    result = apply_harvest(item, _with_rare_counts(simple_data, {"5": 1}), "life", random.Random(20260921))
    assert result.rarity == "rare"
    assert {mod.id for mod in _locked_suffixes()[:3]} <= {mod.id for mod in result.mods}
    assert item.mods == _locked_suffixes()


@pytest.mark.parametrize("bad_tag", ("drop", "unknown", 1, None))
def test_harvest_validates_tag_mode_rng_and_item(simple_data: ActionData, bad_tag: object) -> None:
    item = ItemState("Base", 1, "rare", _locked_suffixes())
    with pytest.raises(ValueError):
        harvest_distribution(item, simple_data, bad_tag)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        harvest_distribution(item, simple_data, "life", type_filter="sometimes")
    with pytest.raises(ValueError):
        apply_harvest(item, simple_data, "life", object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="requires rare"):
        harvest_distribution(ItemState("Base", 1, "magic"), simple_data, "life")
    with pytest.raises(NotImplementedError, match="Q9"):
        harvest_distribution(ItemState("Base", 1, "rare", _locked_suffixes(), corrupted=True), simple_data, "life")


def test_action_adapter_and_real_protected_helmet_seeded_comparison() -> None:
    data = load_action_data(ROOT)
    # Three ordinary suffixes; the later policy supplies its concrete target labels.
    suffixes = [entry for entry in data.mods.values() if entry["type"] == "Suffix" and entry["level"] <= 86]
    chosen = []
    groups = set()
    for row in suffixes:
        if row["group"] not in groups:
            chosen.append(ModRef(row["id"], row["type"], row["group"]))
            groups.add(row["group"])
        if len(chosen) == 3:
            break
    lock = ModRef("bench:729", "Prefix", "ItemGenerationCannotChangeSuffixes")
    item = ItemState("Royal Burgonet", 86, "rare", tuple((*chosen, lock)))
    labels = {"IncreasedLife9": "Life9"}
    distribution = action_distribution("harvest_reforge", item, data, labels, harvest_tag="life")
    exact = probability(distribution, lambda outcome: "Life9" in outcome.labels)
    assert sum(distribution.values()) == pytest.approx(1, abs=1e-10)
    assert exact >= 1 / 13
    assert len(distribution) > 1
    defence = action_distribution("harvest_reforge", item, data, harvest_tag="defence")
    assert sum(defence.values()) == pytest.approx(1, abs=1e-10)

    rng = random.Random(20260921)
    samples = [apply_harvest(item, data, "life", rng) for _ in range(10_000)]
    successes = sum(any(mod.id == "IncreasedLife9" for mod in result.mods) for result in samples)
    frequency = successes / len(samples)
    bound = math.sqrt(math.log(2 / 0.001) / (2 * len(samples)))
    assert abs(frequency - exact) <= bound
    assert all(set(chosen) <= set(result.mods) for result in samples)
