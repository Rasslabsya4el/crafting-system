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
    prepare_roll,
    scour_item,
)
from craftoracle.distributions import OutcomeClass, expected_value, probability
from craftoracle.item_model import ItemState, ModRef


ROOT = Path(__file__).parents[1]


def _mod(mod_id: str, side: str, group: str, *, weight: int = 1, level: int = 1, tags=()) -> dict:
    return {
        "id": mod_id,
        "type": side,
        "group": group,
        "level": level,
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
            "Attack": _mod("Attack", "Prefix", "Attack", tags=("attack",)),
        },
        bench={
            700: {"source_index": 700, "type": "Prefix", "group": "BenchPrefix", "types": {"Helmet": True}, "modTags": []},
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
    crafted_prefix = scour_item(ItemState("Base", 1, "rare", (
        ref("bench:730", "Suffix", "ItemGenerationCanHaveMultipleCraftedMods"),
        ref("bench:700", "Prefix", "BenchPrefix"),
        ref("bench:728", "Suffix", "ItemGenerationCannotChangePrefixes"),
    )), synthetic)
    assert crafted_prefix.mods == (ref("bench:700", "Prefix", "BenchPrefix"),)


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
    for action, question in (("harvest", "Q6"), ("fossils", "Q13"), ("eldritch", "Q11"), ("awakener", "Q20"), ("recombinator", "Q21"), ("fracture", "Q12"), ("veiled", "Q12"), ("corruption", "Q18"), ("beasts", "Q25"), ("catalysts", "Q23")):
        with pytest.raises(NotImplementedError, match=question):
            action_distribution(action, ItemState("Base", 1, "normal"), synthetic)
    with pytest.raises(ValueError, match="fossil_ids"):
        action_distribution("fossil", ItemState("Base", 1, "normal"), synthetic)
    with pytest.raises(ValueError, match="unknown action"):
        action_distribution("divine", ItemState("Base", 1, "normal"), synthetic)


def test_additions_and_removals_respect_full_sides_and_attack_lock(synthetic: ActionData) -> None:
    prefix_only = ActionData(synthetic.bases, {key: synthetic.mods[key] for key in ("A", "C")}, synthetic.bench, {}, synthetic.rules)
    with pytest.raises(ValueError, match="no eligible"):
        action_distribution("augmentation", ItemState("Base", 1, "magic", (ref("A", "Prefix", "A"),)), prefix_only)

    retained_no_attack = ItemState("Base", 1, "rare", (
        ref("bench:730", "Suffix", "ItemGenerationCanHaveMultipleCraftedMods"),
        ref("bench:729", "Prefix", "ItemGenerationCannotChangeSuffixes"),
        ref("bench:731", "Suffix", "ItemGenerationCannotRollAttackAffixes"),
    ))
    assert "Attack" not in {entry.mod_id for entry in prepare_roll("chaos", retained_no_attack, synthetic).entries}
    removed_no_attack = ItemState("Base", 1, "rare", (
        ref("bench:730", "Suffix", "ItemGenerationCanHaveMultipleCraftedMods"),
        ref("bench:731", "Suffix", "ItemGenerationCannotRollAttackAffixes"),
    ))
    assert "Attack" in {entry.mod_id for entry in prepare_roll("chaos", removed_no_attack, synthetic).entries}

    exalt_input = ItemState("Base", 1, "rare", (
        ref("A", "Prefix", "A"), ref("bench:730", "Suffix", "ItemGenerationCanHaveMultipleCraftedMods"),
        ref("bench:731", "Suffix", "ItemGenerationCannotRollAttackAffixes"),
    ))
    assert "Attack" not in {entry.mod_id for entry in prepare_roll("exalted", exalt_input, synthetic).entries}
    annul_input = ItemState("Base", 1, "rare", (
        ref("Attack", "Prefix", "Attack"), ref("B", "Suffix", "B"),
        ref("bench:730", "Suffix", "ItemGenerationCanHaveMultipleCraftedMods"),
        ref("bench:731", "Suffix", "ItemGenerationCannotRollAttackAffixes"),
    ))
    annul = action_distribution("annul", annul_input, synthetic, {"Attack": "attack"})
    assert all("attack" in outcome.labels for outcome in annul)


@pytest.mark.parametrize("flag", ("corrupted", "influenced", "fractured", "synthesised", "mirrored", "split"))
def test_q9_flags_are_rejected_by_actions(synthetic: ActionData, flag: str) -> None:
    with pytest.raises(NotImplementedError, match=r"^out of tonight's slice: Q9$"):
        action_distribution("transmute", ItemState("Base", 1, "normal", **{flag: True}), synthetic)


def test_essence_tier_cap_and_metamod_rules(synthetic: ActionData) -> None:
    essence_data = ActionData(
        synthetic.bases,
        {
            "Forced": _mod("Forced", "Prefix", "Forced", level=100),
            "Low": _mod("Low", "Suffix", "Low", level=35),
            "High": _mod("High", "Suffix", "High", level=36),
        },
        synthetic.bench,
        {
            "low": {"id": "low", "tier": 1, "mods": {"Helmet": "Forced"}},
            "high": {"id": "high", "tier": 5, "mods": {"Helmet": "Forced"}},
        },
        synthetic.rules,
    )
    with pytest.raises(ValueError, match="tier 1-4"):
        action_distribution("essence", ItemState("Base", 100, "rare"), essence_data, essence_id="low")
    scenario = prepare_roll("essence", ItemState("Base", 100, "normal"), essence_data, essence_id="low")
    assert {entry.mod_id for entry in scenario.entries} == {"Low"}
    with pytest.raises(ValueError, match="metamod"):
        action_distribution("essence", ItemState("Base", 100, "rare", (ref("bench:728", "Suffix", "ItemGenerationCannotChangePrefixes"),)), essence_data, essence_id="high")
    assert sum(action_distribution("essence", ItemState("Base", 100, "rare", (ref("bench:730", "Suffix", "ItemGenerationCanHaveMultipleCraftedMods"),)), essence_data, essence_id="high").values()) == pytest.approx(1)


def test_existing_bench_must_support_the_item_class(synthetic: ActionData) -> None:
    unsupported = dict(synthetic.bench)
    unsupported[999] = {"source_index": 999, "type": "Suffix", "group": "Unsupported", "types": {"Ring": True}, "modTags": []}
    data = ActionData(synthetic.bases, synthetic.mods, unsupported, {}, synthetic.rules)
    with pytest.raises(ValueError, match="does not support"):
        action_distribution("scour", ItemState("Base", 1, "magic", (ref("bench:999", "Suffix", "Unsupported"),)), data)


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
