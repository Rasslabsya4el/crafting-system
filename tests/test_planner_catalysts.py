"""Catalyst quality as a method of the planner (#159, OR-37: R06's catalysts are in the beta), planned through the entry and the envelope search on
the fixture Paua Amulet of item level 84 (`targets_support`).

The numbers, worked by hand from the gain law of `catalyst.gain_formula_and_rounding` (`f = 30 e^(-ilvl / 30) - 0.3`; one catalyst adds `floor(f)`
points with chance `1 - frac(f)` and one more with chance `frac(f)`, the quality capped at 20%):

* item level 84: `f = 30 e^(-2.8) - 0.3 = 1.5243`: +1 with chance 0.4757, +2 with chance 0.5243 (the wiki's table). From `q` points to 20, the mean
  number `E(q) = 1 + 0.4757 E(q + 1) + 0.5243 E(q + 2)`, `E(20) = 0`, `E(19) = 1`: `E(0) = 13.35` (the research's figure, ADR-0029), `E(10) = 6.79`.
* item level 75: `f = 30 e^(-2.5) - 0.3 = 2.1626`: +2 with chance 0.8374, +3 with chance 0.1626; `E(0) = 9.53` (the research's figure).

So a target that asks for 20% Intrinsic quality on an item that holds every mod it asks for costs `E(q) k` at `k` Chaos per Intrinsic Catalyst; and
with the one prefix of the bench craft `(15-23)% increased Elemental Damage with Attack Skills` (6 Orbs of Alteration at `a`; OR-2: asked by `mod:`)
on a rare amulet that holds one suffix, `6a + E(0) k`: the craft comes first, the catalysts last (`Abstraction.quality_offer_pruned`: quality changes no odds).

The lower bound of the method: the key of the bound's model holds the quality (`CompressedState.held`), so the model holds the catalyst's own
kernel, and its value at a state that meets every mod but the quality is the exact `E(q) k`. The search's first standing already has its lower
figure at the plan's cost. For the offers left out of that model the catalyst's floor is its price (`_offer_kinds`: it reads the quality, TERMINAL).
"""

import dataclasses
import datetime
from fractions import Fraction

import pytest
from targets_support import DATA, parse
from test_cli_offers import with_currency_names

from crafting_system.actions import ApplyCatalyst, expected_catalysts
from crafting_system.items import CatalystType
from crafting_system.planner import LockStatus, PlanError, PlanSettings, plan_target
from crafting_system.planner import _envelope
from crafting_system.planner._offer_kinds import TERMINAL, _kind_of
from crafting_system.planner._offers import Offer, PricedOffer
from crafting_system.prices import PriceFile
from crafting_system.prices.price_file import PriceEntry
from crafting_system.prices.provenance import EXCHANGE, Provenance
from crafting_system.targets import PlainQualityRequirement

D = with_currency_names(DATA)
K, A = 2.0, 0.5  # an Intrinsic Catalyst and an Orb of Alteration, in Chaos
LIGHTNING_HELD = """\
requirements:
  - family: LightningResistance
    min_tier: 2
quality:
  type: intrinsic
  min_percent: 20
start_item:
  rarity: rare
  mods:
    - mod: LightningResist7
      values: [45]
"""
CRAFTED = """\
requirements:
  - family: IncreasedWeaponElementalDamagePercent
    mod: EinharMasterWeaponElementalDamage1_
quality:
  type: intrinsic
  min_percent: 20
start_item:
  rarity: rare
  mods:
    - mod: LightningResist7
      values: [45]
"""


@pytest.fixture(autouse=True)
def every_shared_kernel_checked(monkeypatch):
    monkeypatch.setattr(_envelope, "CHECK_SHARED", True)  # the search builds every kernel it shares by key again and compares (#886)


def _prices(**chaos: float) -> PriceFile:
    entry = lambda value: PriceEntry(value, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", "2026-10-30", 1e9))  # noqa: E731
    named = {"Intrinsic Catalyst": K, "Tempering Catalyst": 0.01, "Orb of Alteration": A, "Hinekora's Lock": 50.0, **chaos}
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, {name: entry(value) for name, value in named.items()})


def _plan(text: str, methods=("catalyst",), seen: list | None = None, prices: PriceFile | None = None):
    target = parse(text, methods=methods)
    settings = PlanSettings(recipe_starts=False, solver="envelope", watch=None if seen is None else seen.append)
    return plan_target(D, target, prices or _prices(), settings)


def _mean(level: int, start: int = 0) -> float:
    return float(expected_catalysts(level, 20, start))


def test_the_mean_number_of_catalysts_is_the_hand_worked_one():
    assert _mean(84) == pytest.approx(13.35, abs=0.005)
    assert _mean(75) == pytest.approx(9.53, abs=0.005)
    # E(10) at item level 84, by the recursion of the module text from E(20) = 0 and E(19) = 1
    up, two = Fraction(4757, 10000), Fraction(5243, 10000)
    walk = {20: Fraction(0), 21: Fraction(0), 19: Fraction(1)}
    for q in range(18, 9, -1):
        walk[q] = 1 + up * walk[q + 1] + two * walk[q + 2]
    assert _mean(84, 10) == pytest.approx(float(walk[10]), abs=0.005) and _mean(84, 10) == pytest.approx(6.79, abs=0.005)


def test_an_item_with_every_mod_costs_its_catalysts_e_times_k():
    seen: list = []
    plan = _plan(LIGHTNING_HELD, seen=seen)
    assert plan.mean_remaining == pytest.approx(_mean(84) * K, rel=1e-9)  # 13.35 x 2 = 26.69
    assert seen and seen[0].lower == pytest.approx(_mean(84) * K, rel=1e-9)  # the bound is the plan's cost from the first standing on


def test_a_start_that_holds_ten_percent_of_the_type_pays_for_the_rest():
    text = LIGHTNING_HELD.replace("      values: [45]\n", "      values: [45]\n  quality:\n    type: intrinsic\n    percent: 10\n")
    plan = _plan(text)
    assert plan.mean_remaining == pytest.approx(_mean(84, 10) * K, rel=1e-9)  # 6.79 x 2


def test_a_start_that_holds_another_type_starts_again_from_zero_and_the_other_type_is_not_offered():
    text = LIGHTNING_HELD.replace("      values: [45]\n", "      values: [45]\n  quality:\n    type: tempering\n    percent: 15\n")
    plan = _plan(text)
    assert plan.mean_remaining == pytest.approx(_mean(84) * K, rel=1e-9)
    assert {priced.label for priced in plan.offers} == {"Intrinsic Catalyst"}  # the Tempering Catalyst (0.01 c) would only restart the quality
    (limit,) = [limit for limit in plan.limits if limit.kind == "quality-type"]
    assert "Tempering Catalyst" in limit.labels and "Intrinsic Catalyst" not in limit.labels


def test_a_bench_craft_then_the_catalysts_cost_6a_plus_e_times_k():
    seen: list = []
    plan = _plan(CRAFTED, methods=("bench-craft", "catalyst"), seen=seen)
    expected = 6 * A + _mean(84) * K  # 3 + 26.69
    assert plan.mean_remaining == pytest.approx(expected, rel=1e-9)
    assert all(standing.lower <= expected * (1 + 1e-9) for standing in seen)
    assert seen[-1].lower == pytest.approx(expected, rel=1e-9)  # proved: the bound met the plan


def test_a_target_with_no_quality_is_offered_no_catalyst_and_told_nothing_of_it():
    plan = _plan(LIGHTNING_HELD.replace("quality:\n  type: intrinsic\n  min_percent: 20\n", ""), methods=("catalyst", "chaos-orb"))
    assert not any(priced.label.endswith("Catalyst") for priced in plan.offers)
    assert not [limit for limit in plan.limits if limit.kind == "quality-type"]
    assert plan.mean_remaining == 0.0  # the start meets the goal


def test_the_catalyst_is_terminal_for_the_offers_floors_so_its_floor_is_its_price():
    start = parse(CRAFTED).start_item
    catalyst = ApplyCatalyst(CatalystType.INTRINSIC)
    assert _kind_of(D, start, PricedOffer(Offer(catalyst.label(D), catalyst, {}), K, ()))[0] == TERMINAL


def test_the_plain_quality_of_a_weapon_or_armour_is_still_refused():
    # the quality currency (a Whetstone, a Scrap) is not a planner kind yet: such a target is refused before anything is searched
    plain = dataclasses.replace(parse(LIGHTNING_HELD, methods=("catalyst",)), quality=PlainQualityRequirement(10))
    with pytest.raises(PlanError, match="plain quality of a weapon or armour"):
        plan_target(D, plain, _prices(), PlanSettings(recipe_starts=False, solver="envelope"))


def test_a_run_that_names_hinekoras_lock_plans_the_quality_without_it_and_says_so():
    plan = _plan(LIGHTNING_HELD, methods=("catalyst", "hinekora-lock"))
    assert plan.mean_remaining == pytest.approx(_mean(84) * K, rel=1e-9)
    assert plan.foresight is not None and plan.foresight.status is LockStatus.WITH_QUALITY
