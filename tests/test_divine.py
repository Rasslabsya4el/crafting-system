"""Known answers for the bounded ordinary Divine value API.

Mechanics: docs/mechanics/basic_currency.md worked example 5 and the
2026-09-21 Divine-value worker specification.  Real ranges are the accepted
PoB projections cited by that specification.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import pytest

from craftoracle.actions import ActionData, load_action_data
from craftoracle.divine import RolledItem, apply_divine, divine_distribution
from craftoracle.item_model import ItemState, ModRef


ROOT = Path(__file__).parents[1]


def _mod(mod_id: str, side: str, group: str, stat_text: list[str]) -> dict:
    return {
        "id": mod_id,
        "type": side,
        "group": group,
        "level": 1,
        "weightKey": ["default"],
        "weightVal": [1],
        "source_path": "ModExplicit.lua",
        "stat_text": stat_text,
    }


def _synthetic_data(*mods: dict, bench: dict[int, dict] | None = None) -> ActionData:
    return ActionData(
        bases={"Base": {"type": "Helmet"}},
        mods={mod["id"]: mod for mod in mods},
        bench={} if bench is None else bench,
        essences={},
        rules={
            "magic_caps": [1, 1],
            "rare_caps": [3, 3],
            "magic_count_weights": {"1": 1},
            "rare_count_weights": {"4": 1},
        },
    )


def _ref(mod_id: str, side: str, group: str) -> ModRef:
    return ModRef(mod_id, side, group)


def test_single_and_two_range_exact_distributions() -> None:
    first = _mod("First", "Prefix", "First", ["+(10-12) to Synthetic Value"])
    second = _mod("Second", "Suffix", "Second", ["+(1-2) to Synthetic Value"])
    data = _synthetic_data(first, second)
    one_item = ItemState("Base", 1, "rare", (_ref("First", "Prefix", "First"),))
    one = RolledItem(one_item, (("First", 10),))
    one_distribution = divine_distribution(one, data)
    assert len(one_distribution) == 3
    assert all(probability == pytest.approx(1 / 3) for probability in one_distribution.values())
    assert sum(outcome.values[0][1] * probability for outcome, probability in one_distribution.items()) == pytest.approx(11)
    assert all(outcome.item == one_item for outcome in one_distribution)

    two_item = ItemState("Base", 1, "rare", (
        _ref("First", "Prefix", "First"), _ref("Second", "Suffix", "Second"),
    ))
    two = RolledItem(two_item, (("First", 10), ("Second", 1)))
    two_distribution = divine_distribution(two, data)
    assert len(two_distribution) == 6
    assert all(probability == pytest.approx(1 / 6) for probability in two_distribution.values())
    assert two_distribution[RolledItem(two_item, (("First", 12), ("Second", 2)))] == pytest.approx(1 / 6)

    signed = _synthetic_data(_mod("Signed", "Prefix", "Signed", ["+(-2--1) to Synthetic Value (local)"]))
    signed_item = ItemState("Base", 1, "rare", (_ref("Signed", "Prefix", "Signed"),))
    assert divine_distribution(RolledItem(signed_item, (("Signed", -2),)), signed) == {
        RolledItem(signed_item, (("Signed", -2),)): pytest.approx(1 / 2),
        RolledItem(signed_item, (("Signed", -1),)): pytest.approx(1 / 2),
    }


@pytest.fixture(scope="module")
def real_data() -> ActionData:
    return load_action_data(ROOT)


def _royal_ref(data: ActionData, mod_id: str) -> ModRef:
    row = data.mods[mod_id]
    return ModRef(mod_id, row["type"], row["group"])


def test_real_ranges_locks_and_no_ranged_value(real_data: ActionData) -> None:
    life = _royal_ref(real_data, "IncreasedLife9")
    chaos = _royal_ref(real_data, "ChaosResist6")
    fire = _royal_ref(real_data, "FireResist8")
    item = ItemState("Royal Burgonet", 86, "rare", (life, chaos))
    rolled = RolledItem(item, ((life.id, 130), (chaos.id, 31)))
    distribution = divine_distribution(rolled, real_data)
    assert len(distribution) == 75
    assert all(probability == pytest.approx(1 / 75) for probability in distribution.values())
    assert sum(outcome.values[0][1] * probability for outcome, probability in distribution.items()) == pytest.approx(137)
    assert sum(outcome.values[1][1] * probability for outcome, probability in distribution.items()) == pytest.approx(33)
    event = sum(
        probability
        for outcome, probability in distribution.items()
        if outcome.values[0][1] >= 140 and outcome.values[1][1] >= 34
    )
    assert event == pytest.approx(2 / 15)

    three = RolledItem(ItemState("Royal Burgonet", 86, "rare", (life, chaos, fire)), (
        (life.id, 130), (chaos.id, 31), (fire.id, 46),
    ))
    assert len(divine_distribution(three, real_data)) == 225

    prefix_lock = _ref("bench:728", "Suffix", "ItemGenerationCannotChangePrefixes")
    locked_prefixes = RolledItem(ItemState("Royal Burgonet", 86, "rare", (life, chaos, prefix_lock)), (
        (life.id, 132), (chaos.id, 31),
    ))
    locked_prefix_distribution = divine_distribution(locked_prefixes, real_data)
    assert len(locked_prefix_distribution) == 5
    assert {outcome.values[0][1] for outcome in locked_prefix_distribution} == {132}
    assert {outcome.values[1][1] for outcome in locked_prefix_distribution} == set(range(31, 36))

    suffix_lock = _ref("bench:729", "Prefix", "ItemGenerationCannotChangeSuffixes")
    locked_suffixes = RolledItem(ItemState("Royal Burgonet", 86, "rare", (life, chaos, suffix_lock)), (
        (life.id, 130), (chaos.id, 31),
    ))
    locked_suffix_distribution = divine_distribution(locked_suffixes, real_data)
    assert len(locked_suffix_distribution) == 15
    assert {outcome.values[0][1] for outcome in locked_suffix_distribution} == set(range(130, 145))
    assert {outcome.values[1][1] for outcome in locked_suffix_distribution} == {31}

    lock_only = RolledItem(ItemState("Royal Burgonet", 86, "rare", (prefix_lock,)), ())
    assert divine_distribution(lock_only, real_data) == {lock_only: 1.0}


def test_sampling_replays_and_matches_exact_event(real_data: ActionData) -> None:
    life = _royal_ref(real_data, "IncreasedLife9")
    chaos = _royal_ref(real_data, "ChaosResist6")
    rolled = RolledItem(
        ItemState("Royal Burgonet", 86, "rare", (life, chaos)),
        ((life.id, 130), (chaos.id, 31)),
    )
    first = apply_divine(rolled, real_data, rng=random.Random(20260921))
    second = apply_divine(rolled, real_data, rng=random.Random(20260921))
    assert first == second
    assert 130 <= first.values[0][1] <= 144
    assert 31 <= first.values[1][1] <= 35

    rng = random.Random(20260921)
    samples = [apply_divine(rolled, real_data, rng=rng) for _ in range(5000)]
    observed = sum(sample.values[0][1] >= 140 and sample.values[1][1] >= 34 for sample in samples) / len(samples)
    bound = math.sqrt(math.log(2 / 0.001) / (2 * len(samples)))
    assert abs(observed - 2 / 15) <= bound


def test_validation_boundaries_and_large_sampling() -> None:
    range_mod = _mod("Range", "Prefix", "Range", ["+(10-12) to Synthetic Value"])
    data = _synthetic_data(range_mod)
    item = ItemState("Base", 1, "rare", (_ref("Range", "Prefix", "Range"),))
    with pytest.raises(ValueError, match="non-normal"):
        divine_distribution(RolledItem(ItemState("Base", 1, "normal"), ()), data)
    with pytest.raises(ValueError, match="duplicate"):
        divine_distribution(RolledItem(item, (("Range", 10), ("Range", 11))), data)
    with pytest.raises(ValueError, match="match"):
        divine_distribution(RolledItem(item, ()), data)
    with pytest.raises(ValueError, match="range"):
        divine_distribution(RolledItem(item, (("Range", 13),)), data)
    with pytest.raises(ValueError, match="integer"):
        divine_distribution(RolledItem(item, (("Range", True),)), data)
    with pytest.raises(ValueError, match="at least one explicit"):
        divine_distribution(RolledItem(ItemState("Base", 1, "rare"), ()), data)

    second = _mod("Second", "Suffix", "Second", ["+(1-2) to Synthetic Value"])
    two_ranges = _synthetic_data(range_mod, second)
    two_range_item = ItemState("Base", 1, "rare", (
        _ref("Range", "Prefix", "Range"), _ref("Second", "Suffix", "Second"),
    ))
    with pytest.raises(ValueError, match="source-item order"):
        divine_distribution(RolledItem(two_range_item, (("Second", 1), ("Range", 10))), two_ranges)
    for flag in ("corrupted", "influenced", "fractured", "synthesised", "mirrored", "split"):
        with pytest.raises(NotImplementedError, match=r"^out of tonight's slice: Q9$"):
            divine_distribution(RolledItem(ItemState("Base", 1, "rare", (_ref("Range", "Prefix", "Range"),), **{flag: True}), (("Range", 10),)), data)

    for stat_text in (
        ["+(1.5-2.5) to Value"],
        ["+(10-12) to Value", "+(1-2) to Other"],
        ["+(10-12) and +(1-2) to Value"],
        ["+(10-12) to Value at level 5"],
        ["+10 to Value"],
    ):
        unsupported = _synthetic_data(_mod("Unsupported", "Prefix", "Unsupported", stat_text))
        unsupported_item = ItemState("Base", 1, "rare", (_ref("Unsupported", "Prefix", "Unsupported"),))
        with pytest.raises(NotImplementedError, match=r"^unsupported Divine value shape: Unsupported$"):
            divine_distribution(RolledItem(unsupported_item, ()), unsupported)

    huge = _synthetic_data(_mod("Huge", "Prefix", "Huge", ["+(0-100000) to Value"]))
    huge_item = ItemState("Base", 1, "rare", (_ref("Huge", "Prefix", "Huge"),))
    huge_rolled = RolledItem(huge_item, (("Huge", 0),))
    with pytest.raises(NotImplementedError, match=r"^Divine distribution work limit$"):
        divine_distribution(huge_rolled, huge)
    sampled = apply_divine(huge_rolled, huge, rng=random.Random(1))
    assert 0 <= sampled.values[0][1] <= 100000
