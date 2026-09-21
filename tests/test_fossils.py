"""Known-answer checks for ordinary fossil weight transforms and rerolls."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import math
import random

import pytest

from craftoracle.actions import ActionData, action_distribution, load_action_data
from craftoracle.distributions import probability
from craftoracle.fossils import apply_fossils, fossil_distribution, prepare_fossils, sample_fossils, transformed_weight
from craftoracle.item_model import ItemState, ModRef


ROOT = Path(__file__).parents[1]


def _mod(mod_id, side, group, weight=1, tags=()):
    return {"id": mod_id, "type": side, "group": group, "level": 1,
            "weightKey": ["default"], "weightVal": [weight], "modTags": list(tags),
            "source_path": "ModExplicit.lua"}


@pytest.fixture()
def toy() -> ActionData:
    return ActionData(
        {"Base": {"name": "Base", "type": "Helmet", "tags": {"default": True}}},
        {"A": _mod("A", "Prefix", "A", 1, ("fire",)), "B": _mod("B", "Prefix", "B", 1, ("cold",)),
         "C": _mod("C", "Suffix", "C", 2)},
        {
            728: {"source_index": 728, "type": "Suffix", "group": "ItemGenerationCannotChangePrefixes", "types": {"Helmet": True}, "modTags": []},
            729: {"source_index": 729, "type": "Prefix", "group": "ItemGenerationCannotChangeSuffixes", "types": {"Helmet": True}, "modTags": []},
            730: {"source_index": 730, "type": "Suffix", "group": "ItemGenerationCanHaveMultipleCraftedMods", "types": {"Helmet": True}, "modTags": []},
            731: {"source_index": 731, "type": "Suffix", "group": "ItemGenerationCannotRollAttackAffixes", "types": {"Helmet": True}, "modTags": []},
            732: {"source_index": 732, "type": "Suffix", "group": "ItemGenerationCannotRollCasterAffixes", "types": {"Helmet": True}, "modTags": []},
        }, {},
        {"magic_caps": [1, 1], "rare_caps": [3, 3], "magic_count_weights": {"1": 1}, "rare_count_weights": {"1": 1}},
    )


def test_hand_weight_transforms_and_hybrid_trace() -> None:
    rows = {row["id"]: row for row in __import__("craftoracle.fossils", fromlist=["_rules"])._rules()["ordinary"]}
    assert transformed_weight(100, ("attack",), ({"positive": {"attack": "3"}, "negative": {"attack": "0.5"}},)) == 150
    assert transformed_weight(100, ("attack",), ({"positive": {}, "negative": {"attack": "0"}},)) == 0
    factors = ({"positive": {"attack": "3"}, "negative": {}}, {"positive": {"fire": "4"}, "negative": {}})
    assert transformed_weight(100, ("attack", "fire"), factors) == 700
    assert transformed_weight(100, ("attack", "fire"), factors, "multiplicative") == 1200
    assert transformed_weight(100, (), factors) == 100
    assert transformed_weight(100, ("minion", "aura"), (rows[3],)) == 2000
    assert transformed_weight(126, ("caster",), (rows[14],)) == Fraction(189, 10)
    assert transformed_weight(100, ("physical", "ailment"), (rows[4],)) == 1000
    assert transformed_weight(100, ("physical",), (rows[4],)) == 100
    assert transformed_weight(100, ("physical", "ailment"), (rows[11], rows[8])) == 0
    assert transformed_weight(100, ("physical", "ailment"), (rows[4], rows[8])) == 1000
    assert transformed_weight(100, ("physical", "ailment", "attack"), (rows[4], rows[14])) == 2000
    assert transformed_weight(100, ("elemental", "fire"), (rows[11], rows[13])) == 1600


def test_toy_distribution_scaling_and_guards(toy: ActionData) -> None:
    item = ItemState("Base", 1, "rare")
    plan = prepare_fossils(item, toy, [13], {"A": "A", "C": "C"})
    assert {entry.mod_id: entry.weight for entry in plan.entries} == {"A": 5, "C": 1}
    assert {mod_id: plan.effective_weights[mod_id] for mod_id in ("A", "B", "C")} == {"A": 10, "B": 0, "C": 2}
    assert plan.scale == Fraction(1, 2)
    with pytest.raises(TypeError):
        plan.labels["new"] = "new"  # type: ignore[index]
    with pytest.raises(TypeError):
        plan.effective_weights["A"] = Fraction(1)  # type: ignore[index]
    one = fossil_distribution(item, toy, [13], {"A": "A", "C": "C"})
    assert probability(one, lambda out: "A" in out.labels) == pytest.approx(5 / 6)
    assert probability(one, lambda out: "C" in out.labels) == pytest.approx(1 / 6)
    assert sample_fossils(plan, random.Random(20260921)) == apply_fossils(
        item, toy, [13], random.Random(20260921), {"A": "A", "C": "C"}
    )
    assert item.mods == ()
    two_data = ActionData(toy.bases, toy.mods, toy.bench, toy.essences, {**toy.rules, "rare_count_weights": {"2": 1}})
    two = fossil_distribution(item, two_data, [13], {"A": "A", "C": "C"})
    assert probability(two, lambda out: out.labels == ("A", "C")) == pytest.approx(1)
    assert transformed_weight(2, (), ({"positive": {"drop": "10"}, "negative": {}, "untagged_factor": "0"},)) == 0
    tagless_only = ActionData(toy.bases, {"C": toy.mods["C"]}, toy.bench, toy.essences, toy.rules)
    with pytest.raises(ValueError, match="unreachable"):
        fossil_distribution(item, tagless_only, [23])
    for bad in ([], [13] * 2, [13, 14, 15, 1, 2]):
        with pytest.raises(ValueError):
            fossil_distribution(item, toy, bad)
    with pytest.raises(NotImplementedError, match="Q13"):
        fossil_distribution(item, toy, [19])
    with pytest.raises(NotImplementedError, match="Q13"):
        fossil_distribution(item, toy, [999])
    rules = __import__("craftoracle.fossils", fromlist=["_rules"])._rules()
    assert rules["source"]["confidence"] == "reimplemented-from-CoE"
    assert "S56" in rules["bound_s56_disagreement"]


def test_real_helmet_distribution_and_seeded_mc() -> None:
    data = load_action_data(ROOT)
    item = ItemState("Royal Burgonet", 86, "rare")
    labels = {"IncreasedLife9": "life", "ChaosResist6": "chaos", "FireResist8": "fire", "ColdResist8": "cold", "LightningResist8": "lightning"}
    plan = prepare_fossils(item, data, [12, 1], labels)
    exact = fossil_distribution(item, data, [12, 1], labels)
    target = lambda out: "life" in out.labels and "chaos" in out.labels and any(tag in out.labels for tag in ("fire", "cold", "lightning"))
    chance = probability(exact, target)
    life_chance = probability(exact, lambda out: "life" in out.labels)
    assert sum(exact.values()) == pytest.approx(1, abs=1e-10)
    assert plan.scale > 0
    assert all(entry.weight > 0 for entry in plan.entries)
    assert all(out.prefixes <= 3 and out.suffixes <= 3 for out in exact)
    rng = random.Random(20260921)
    samples = [sample_fossils(plan, rng) for _ in range(10_000)]
    successes = sum({"IncreasedLife9", "ChaosResist6"} <= {mod.id for mod in result.mods} and any(mod.id in {"FireResist8", "ColdResist8", "LightningResist8"} for mod in result.mods) for result in samples)
    bound = math.sqrt(math.log(2 / .001) / (2 * 10_000))
    assert abs(successes / 10_000 - chance) <= bound
    life_successes = sum(any(mod.id == "IncreasedLife9" for mod in result.mods) for result in samples)
    assert abs(life_successes / 10_000 - life_chance) <= bound
    assert all(len({mod.group for mod in result.mods}) == len(result.mods) for result in samples)
    assert all(sum(mod.type == "Prefix" for mod in result.mods) <= 3 for result in samples)
    assert all(sum(mod.type == "Suffix" for mod in result.mods) <= 3 for result in samples)
    assert all(
        all("lightning" not in (data.mods[mod.id].get("modTags") or []) for mod in result.mods)
        for result in samples
    )
    assert item.mods == ()

    crude_bow = ItemState("Crude Bow", 86, "rare")
    fire = data.mods["LocalAddedFireDamageTwoHand10"]
    assert fire["weightVal"][fire["weightKey"].index("bow")] == 126
    assert prepare_fossils(crude_bow, data, [13, 14]).effective_weights["LocalAddedFireDamageTwoHand10"] == 2520
    assert prepare_fossils(crude_bow, data, [13, 14], mode="multiplicative").effective_weights["LocalAddedFireDamageTwoHand10"] == 12600


def test_adapter_and_mutation_freshness(toy: ActionData) -> None:
    item = ItemState("Base", 1, "rare")
    before = fossil_distribution(item, toy, [13], {"A": "A"})
    toy.mods["C"]["weightVal"][0] = 100
    after = action_distribution("fossil", item, toy, {"A": "A"}, fossil_ids=[13])
    assert probability(before, lambda out: "A" in out.labels) == pytest.approx(5 / 6)
    assert probability(after, lambda out: "A" in out.labels) == pytest.approx(1 / 11)
    with pytest.raises(ValueError, match="fossil options"):
        action_distribution("chaos", item, toy, fossil_ids=[13])
    with pytest.raises(ValueError, match="socket_count"):
        fossil_distribution(item, toy, [13], socket_count=True)
    with pytest.raises(ValueError, match="fossil_ids"):
        action_distribution("fossil", item, toy)
    with pytest.raises(ValueError, match="fossil options"):
        action_distribution("chaos", item, toy, fossil_mode="multiplicative")
    with pytest.raises(ValueError, match="essence_id"):
        action_distribution("fossil", item, toy, fossil_ids=[13], essence_id="nope")
    with pytest.raises(ValueError, match="harvest options"):
        action_distribution("fossil", item, toy, fossil_ids=[13], harvest_tag="life")


@pytest.mark.parametrize("rarity", ("normal", "magic"))
def test_ordinary_chaotic_resonators_reject_nonrare_items(toy: ActionData, rarity: str) -> None:
    with pytest.raises(ValueError, match="requires rare"):
        fossil_distribution(ItemState("Base", 1, rarity), toy, [13])


@pytest.mark.parametrize("bench_id,side,group", (
    (728, "Suffix", "ItemGenerationCannotChangePrefixes"),
    (729, "Prefix", "ItemGenerationCannotChangeSuffixes"),
    (731, "Suffix", "ItemGenerationCannotRollAttackAffixes"),
    (732, "Suffix", "ItemGenerationCannotRollCasterAffixes"),
))
def test_outcome_affecting_metamods_reject_but_multimod_rerolls(
    toy: ActionData, bench_id: int, side: str, group: str
) -> None:
    item = ItemState("Base", 1, "rare", (ModRef(f"bench:{bench_id}", side, group),))
    with pytest.raises(ValueError, match="outcome-affecting metamod"):
        fossil_distribution(item, toy, [13])
    multimod = ItemState("Base", 1, "rare", (
        ModRef("bench:730", "Suffix", "ItemGenerationCanHaveMultipleCraftedMods"),
    ))
    result = apply_fossils(multimod, toy, [13], random.Random(20260921))
    assert all(mod.id != "bench:730" for mod in result.mods)
    assert multimod.mods[0].id == "bench:730"


@pytest.mark.parametrize("flag", ("corrupted", "influenced", "fractured", "synthesised", "mirrored", "split"))
def test_q9_flags_reject_fossils(toy: ActionData, flag: str) -> None:
    with pytest.raises(NotImplementedError, match="Q9"):
        fossil_distribution(ItemState("Base", 1, "rare", **{flag: True}), toy, [13])


def test_prepared_plan_copies_caller_labels(toy: ActionData) -> None:
    labels = {"A": "original"}
    plan = prepare_fossils(ItemState("Base", 1, "rare"), toy, [13], labels)
    labels["A"] = "changed"
    labels["C"] = "new"
    assert dict(plan.labels) == {"A": "original"}
