"""Known-answer checks for the ordinary action adapter.

Rules and values are fixed by docs/mechanics/basic_currency.md,
affix_generation.md, bench_metamods.md, and essences.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from craftoracle.actions import (
    ActionData,
    action_distribution,
    bench_item,
    load_action_data,
    scour_item,
)
from craftoracle.distributions import OutcomeClass, expected_value, probability
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


@pytest.fixture()
def synthetic() -> ActionData:
    return ActionData(
        bases={"Base": {"name": "Base", "type": "Helmet", "tags": {"default": True}}},
        mods={
            "A": _mod("A", "Prefix", "A", weight=1),
            "C": _mod("C", "Prefix", "C"),
            "D": _mod("D", "Prefix", "D"),
            "B": _mod("B", "Suffix", "B", weight=3),
            "E": _mod("E", "Suffix", "E"),
            "F": _mod("F", "Suffix", "F"),
        },
        bench={
            728: {"source_index": 728, "type": "Suffix", "group": "ItemGenerationCannotChangePrefixes", "types": {"Helmet": True}, "modTags": []},
            729: {"source_index": 729, "type": "Prefix", "group": "ItemGenerationCannotChangeSuffixes", "types": {"Helmet": True}, "modTags": []},
            730: {"source_index": 730, "type": "Suffix", "group": "ItemGenerationCanHaveMultipleCraftedMods", "types": {"Helmet": True}, "modTags": []},
            731: {"source_index": 731, "type": "Suffix", "group": "ItemGenerationCannotRollAttackAffixes", "types": {"Helmet": True}, "modTags": []},
        },
        essences={},
        rules={
            "magic_caps": [1, 1],
            "rare_caps": [3, 3],
            "magic_count_weights": {"1": 1, "2": 1},
            "rare_count_weights": {"4": 8, "5": 3, "6": 1},
        },
    )


def ref(mod_id: str, side: str, group: str) -> ModRef:
    return ModRef(mod_id, side, group)


def test_transmute_matches_magic_mixture(synthetic: ActionData) -> None:
    magic_data = ActionData(synthetic.bases, {key: synthetic.mods[key] for key in ("A", "B")}, synthetic.bench, {}, synthetic.rules)
    distribution = action_distribution(
        "transmute", ItemState("Base", 1, "normal"), magic_data, {"A": "A", "B": "B"}
    )
    assert distribution == {
        OutcomeClass(("A",), 1, 0): pytest.approx(1 / 8),
        OutcomeClass(("B",), 0, 1): pytest.approx(3 / 8),
        OutcomeClass(("A", "B"), 1, 1): pytest.approx(1 / 2),
    }


def test_additions_and_wrong_rarities(synthetic: ActionData) -> None:
    addition_data = ActionData(synthetic.bases, {key: synthetic.mods[key] for key in ("A", "B", "C")}, synthetic.bench, {}, synthetic.rules)
    magic = ItemState("Base", 1, "magic", (ref("A", "Prefix", "A"),))
    augmented = action_distribution("augmentation", magic, addition_data, {"B": "B"})
    assert augmented == {OutcomeClass(("B",), 1, 1): pytest.approx(1)}
    regal = action_distribution("regal", ItemState("Base", 1, "magic", (ref("A", "Prefix", "A"), ref("B", "Suffix", "B"))), addition_data)
    assert regal == {OutcomeClass((), 2, 1): pytest.approx(1)}
    with pytest.raises(ValueError, match="full"):
        action_distribution("exalted", ItemState("Base", 1, "rare", (ref("A", "Prefix", "A"), ref("C", "Prefix", "C"), ref("D", "Prefix", "D"), ref("B", "Suffix", "B"), ref("E", "Suffix", "E"), ref("F", "Suffix", "F"))), synthetic)
    with pytest.raises(ValueError, match="requires magic"):
        action_distribution("alteration", ItemState("Base", 1, "rare"), synthetic)


def test_annul_uniform_and_scour_locks(synthetic: ActionData) -> None:
    item = ItemState("Base", 1, "rare", (ref("A", "Prefix", "A"), ref("C", "Prefix", "C"), ref("B", "Suffix", "B")))
    distribution = action_distribution("annul", item, synthetic, {"A": "A", "B": "B", "C": "C"})
    assert sum(distribution.values()) == pytest.approx(1)
    assert probability(distribution, lambda out: "A" not in out.labels) == pytest.approx(1 / 3)
    assert probability(distribution, lambda out: "B" not in out.labels) == pytest.approx(1 / 3)
    assert probability(distribution, lambda out: "C" not in out.labels) == pytest.approx(1 / 3)

    locked = ItemState("Base", 1, "rare", (ref("A", "Prefix", "A"), ref("C", "Prefix", "C"), ref("bench:728", "Suffix", "ItemGenerationCannotChangePrefixes")))
    scoured = scour_item(locked, synthetic)
    assert scoured.rarity == "rare"
    assert scoured.mods == (ref("A", "Prefix", "A"), ref("C", "Prefix", "C"))
    one = scour_item(ItemState("Base", 1, "rare", (ref("A", "Prefix", "A"), ref("bench:728", "Suffix", "ItemGenerationCannotChangePrefixes"))), synthetic)
    assert one.rarity == "magic"
    suffix_locked = scour_item(ItemState("Base", 1, "rare", (ref("B", "Suffix", "B"), ref("bench:729", "Prefix", "ItemGenerationCannotChangeSuffixes"))), synthetic)
    assert suffix_locked.rarity == "magic"
    assert suffix_locked.mods == (ref("B", "Suffix", "B"),)


def test_bench_identity_slots_and_multimod(synthetic: ActionData) -> None:
    item = bench_item(ItemState("Base", 1, "normal"), synthetic, 728)
    assert item.rarity == "magic"
    assert item.mods == (ref("bench:728", "Suffix", "ItemGenerationCannotChangePrefixes"),)
    multi = bench_item(ItemState("Base", 1, "rare"), synthetic, 730)
    multi = bench_item(multi, synthetic, 728)
    multi = bench_item(multi, synthetic, 731)
    with pytest.raises(ValueError, match="crafted"):
        bench_item(multi, synthetic, 729)


def test_chaos_keeps_only_the_locked_side_and_special_families_are_explicit(synthetic: ActionData) -> None:
    locked = ItemState("Base", 1, "rare", (
        ref("A", "Prefix", "A"), ref("C", "Prefix", "C"),
        ref("bench:728", "Suffix", "ItemGenerationCannotChangePrefixes"),
    ))
    chaos = action_distribution("chaos", locked, synthetic)
    assert all(out.prefixes >= 2 for out in chaos)
    assert all(out.suffixes <= 3 for out in chaos)
    for action, question in (("harvest", "Q6"), ("fossil", "Q13"), ("eldritch", "Q11"), ("awakener", "Q20")):
        with pytest.raises(NotImplementedError, match=question):
            action_distribution(action, ItemState("Base", 1, "normal"), synthetic)
    with pytest.raises(ValueError, match="unknown action"):
        action_distribution("divine", ItemState("Base", 1, "normal"), synthetic)


def test_rare_mixture_and_real_essence_mapping() -> None:
    data = load_action_data(ROOT)
    rare = ItemState("Royal Burgonet", 86, "normal")
    alchemy = action_distribution("alchemy", rare, data)
    assert expected_value(alchemy, lambda out: out.prefixes + out.suffixes) == pytest.approx(53 / 12)
    essence = action_distribution(
        "essence", rare, data, {"ChaosResist6": "chaos"}, essence_id="CurrencyEssenceEnvy3"
    )
    assert probability(essence, lambda out: "chaos" in out.labels) == pytest.approx(1)
    greed = data.essences["Metadata/Items/Currency/CurrencyEssenceGreed7"]
    assert greed["mods"]["Helmet"] == "IncreasedLifeEssenceBootsGloves1"
    assert probability(
        action_distribution("essence", rare, data, {"IncreasedLife9": "t1"}, essence_id="Metadata/Items/Currency/CurrencyEssenceGreed7"),
        lambda out: "t1" in out.labels,
    ) == pytest.approx(0)
