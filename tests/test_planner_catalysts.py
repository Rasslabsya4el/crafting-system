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

The quality is a finish (`planner._quality_finish`): no other method changes the quality, so the plan is the plan of the mods without the quality
(`Plan.mean_remaining`) plus `E(q0) k` (`Plan.quality_finish_value`), the whole in `Plan.total_mean`, and the search of the mods holds no quality.

Where the finish is not exact (an offered action that corrupts the item, which then takes no catalyst; a run that names Hinekora's Lock) the quality
is searched with the mods, as before: the key of the bound's model holds the quality (`CompressedState.held`), so the model holds the catalyst's own
kernel, and its value at a state that meets every mod but the quality is the exact `E(q) k`. The search's first standing already has its lower
figure at the plan's cost. For the offers left out of that model the catalyst's floor is its price (`_offer_kinds`: it reads the quality, TERMINAL).
Both ways give the same mean (`test_the_finish_and_the_search_give_the_same_mean`).
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
from crafting_system.planner import _envelope, _quality_finish
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


def _plan(text: str, methods=("catalyst",), seen: list | None = None, prices: PriceFile | None = None, searched: bool = False):
    """The plan of `text`; `searched`: the quality is searched with the mods instead of finished last (the path where the finish is not exact)."""
    target = parse(text, methods=methods)
    if searched:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(_quality_finish, "FINISH", False)
            return plan_target(D, target, prices or _prices(), PlanSettings(recipe_starts=False, solver="envelope", watch=None if seen is None else seen.append))
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
    plan = _plan(LIGHTNING_HELD)
    assert plan.mean_remaining == 0.0  # the start holds every mod: the mods cost nothing
    assert plan.quality_finish is not None and plan.quality_finish.catalyst.label == "Intrinsic Catalyst"
    assert float(plan.quality_finish.uses) == pytest.approx(_mean(84), rel=1e-12)
    assert plan.total_mean == pytest.approx(_mean(84) * K, rel=1e-9)  # 13.35 x 2 = 26.69
    (said,) = [limit for limit in plan.limits if limit.kind == "quality-finish"]
    assert said.labels == ("Intrinsic Catalyst",) and "13.35 on average" in said.why and "26.69 Chaos" in said.why


def test_searched_with_the_mods_the_bound_is_the_plans_cost_from_the_first_standing():
    seen: list = []
    plan = _plan(LIGHTNING_HELD, seen=seen, searched=True)
    assert plan.quality_finish is None and "Intrinsic Catalyst" in {priced.label for priced in plan.offers}
    assert plan.mean_remaining == pytest.approx(_mean(84) * K, rel=1e-9)
    assert seen and seen[0].lower == pytest.approx(_mean(84) * K, rel=1e-9)  # the bound is the plan's cost from the first standing on


def test_a_start_that_holds_ten_percent_of_the_type_pays_for_the_rest():
    text = LIGHTNING_HELD.replace("      values: [45]\n", "      values: [45]\n  quality:\n    type: intrinsic\n    percent: 10\n")
    plan = _plan(text)
    assert plan.total_mean == pytest.approx(_mean(84, 10) * K, rel=1e-9)  # 6.79 x 2
    assert plan.quality_finish.start_percent == 10


def test_a_start_that_holds_the_quality_asked_adds_nothing():
    text = LIGHTNING_HELD.replace("      values: [45]\n", "      values: [45]\n  quality:\n    type: intrinsic\n    percent: 20\n")
    plan = _plan(text)
    assert plan.total_mean == 0.0 and plan.quality_finish.catalyst is None
    (said,) = [limit for limit in plan.limits if limit.kind == "quality-finish"]
    assert "already has 20% Intrinsic quality" in said.why


def test_a_start_that_holds_another_type_starts_again_from_zero_and_the_other_type_is_not_offered():
    text = LIGHTNING_HELD.replace("      values: [45]\n", "      values: [45]\n  quality:\n    type: tempering\n    percent: 15\n")
    plan = _plan(text)
    assert plan.total_mean == pytest.approx(_mean(84) * K, rel=1e-9)
    assert plan.quality_finish.catalyst.label == "Intrinsic Catalyst"  # the Tempering Catalyst (0.01 c) would only restart the quality
    (limit,) = [limit for limit in plan.limits if limit.kind == "quality-type"]
    assert "Tempering Catalyst" in limit.labels and "Intrinsic Catalyst" not in limit.labels


def test_a_bench_craft_then_the_catalysts_cost_6a_plus_e_times_k():
    plan = _plan(CRAFTED, methods=("bench-craft", "catalyst"))
    assert plan.mean_remaining == pytest.approx(6 * A, rel=1e-9)  # the mods: the craft
    assert plan.total_mean == pytest.approx(6 * A + _mean(84) * K, rel=1e-9)  # 3 + 26.69


def test_the_finish_and_the_search_give_the_same_mean():
    seen: list = []
    finished = _plan(CRAFTED, methods=("bench-craft", "catalyst"))
    searched = _plan(CRAFTED, methods=("bench-craft", "catalyst"), seen=seen, searched=True)
    expected = 6 * A + _mean(84) * K
    assert searched.quality_finish is None and searched.mean_remaining == pytest.approx(expected, rel=1e-9)
    assert finished.total_mean == pytest.approx(searched.total_mean, rel=1e-9)
    assert all(standing.lower <= expected * (1 + 1e-9) for standing in seen)
    assert seen[-1].lower == pytest.approx(expected, rel=1e-9)  # proved: the bound met the plan


def test_a_run_whose_methods_name_no_catalyst_is_refused_with_the_reason():
    with pytest.raises(PlanError, match="20% Intrinsic quality, and no catalyst of that type is among the methods offered"):
        _plan(CRAFTED, methods=("bench-craft",))


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
    assert plan.quality_finish is None  # the Lock's burn keeps no quality: the quality is searched with the mods
    assert plan.mean_remaining == pytest.approx(_mean(84) * K, rel=1e-9)
    assert plan.foresight is not None and plan.foresight.status is LockStatus.WITH_QUALITY


def test_with_no_method_named_the_catalyst_is_offered_by_default():
    plan = plan_target(D, parse(LIGHTNING_HELD), _prices(), PlanSettings(recipe_starts=False, solver="envelope"))  # the target names none (OR-41)
    assert plan.quality_finish.catalyst.label == "Intrinsic Catalyst"
    assert plan.total_mean == pytest.approx(_mean(84) * K, rel=1e-9)


THREE = """\
requirements:
  - family: LightningResistance
    min_tier: 2
  - family: FireResistance
    min_tier: 2
  - family: ColdResistance
    min_tier: 2
quality:
  type: intrinsic
  min_percent: 20
start_item:
  rarity: rare
"""


def test_the_quality_adds_e_times_k_to_a_rerolled_target_and_the_search_of_the_mods_is_the_same(monkeypatch):
    monkeypatch.setattr(_envelope, "CHECK_SHARED", False)  # the rebuild of every shared kernel takes a minute here; the small targets above check it
    # finished last, the quality costs the search of the mods nothing: the same bound and the same states as without it (R05 with its 20%
    # Intrinsic quality got less far in its time net when the search held the quality, #159)
    methods = ("chaos-orb", "annulment-orb", "exalted-orb", "catalyst")
    prices = _prices(**{"Chaos Orb": 1.0, "Exalted Orb": 10.0, "Orb of Annulment": 5.0})
    settings = PlanSettings(recipe_starts=False, solver="envelope")
    plain = plan_target(D, parse(THREE.replace("quality:\n  type: intrinsic\n  min_percent: 20\n", ""), methods=methods), prices, settings)
    asked = plan_target(D, parse(THREE, methods=methods), prices, settings)
    assert asked.mean_remaining == pytest.approx(plain.mean_remaining, rel=1e-12)
    assert asked.total_mean == pytest.approx(plain.mean_remaining + _mean(84) * K, rel=1e-9)
    assert (asked.search.bound_keys, asked.search.touched) == (plain.search.bound_keys, plain.search.touched)


def test_searched_with_the_mods_the_bound_does_not_copy_the_graph_per_percent(monkeypatch):
    monkeypatch.setattr(_envelope, "CHECK_SHARED", False)  # the rebuild of every shared kernel takes a minute here; the small targets above check it
    # Where only the quality is left, the bound's model offers the catalysts alone (`Abstraction.quality_finish_only`): the other actions would
    # copy the item's graph once for each percent of quality (2,244 keys here before, 192 now; 112 without the quality)
    methods = ("chaos-orb", "annulment-orb", "exalted-orb", "catalyst")
    prices = _prices(**{"Chaos Orb": 1.0, "Exalted Orb": 10.0, "Orb of Annulment": 5.0})
    settings = PlanSettings(recipe_starts=False, solver="envelope")
    plain = plan_target(D, parse(THREE.replace("quality:\n  type: intrinsic\n  min_percent: 20\n", ""), methods=methods), prices, settings)
    seen: list = []
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(_quality_finish, "FINISH", False)  # the quality searched with the mods, as where the finish is not exact
        asked = plan_target(D, parse(THREE, methods=methods), prices, dataclasses.replace(settings, watch=seen.append))
    assert asked.quality_finish is None
    assert asked.mean_remaining == pytest.approx(plain.mean_remaining + _mean(84) * K, rel=1e-9)
    assert seen[-1].lower == pytest.approx(asked.mean_remaining, rel=1e-9)
    assert asked.search.bound_keys <= 2 * plain.search.bound_keys


def test_a_named_lock_on_a_quality_target_is_said_in_the_answer():
    plan = _plan(LIGHTNING_HELD, methods=("catalyst", "hinekora-lock"))
    assert any(limit.what == "Hinekora's Lock is not offered" and "quality" in limit.why for limit in plan.limits)


def test_the_catalysts_gain_law_is_an_approximate_input_of_the_finished_plan():
    from crafting_system.cli._marking import approximate_inputs

    plan = _plan(CRAFTED, methods=("bench-craft", "catalyst"))
    assert "catalyst.gain_formula_and_rounding" in {found.claim for found in approximate_inputs(plan, plan.policy, D)}


def test_a_start_that_holds_every_mod_has_a_step_bound_for_the_simulator():
    from crafting_system.cli._verify import MIN_STEPS, max_steps_for

    assert max_steps_for(_plan(LIGHTNING_HELD)) == MIN_STEPS  # no action is offered to the mods: nothing to divide by


def test_a_plan_a_given_route_is_judged_against_keeps_the_catalyst_among_its_offers():
    # a route may name the catalyst as one of its steps, so a judged plan searches the quality with the mods (#159)
    target = parse(CRAFTED, methods=("bench-craft", "catalyst"))
    plan = plan_target(D, target, _prices(), PlanSettings(recipe_starts=False, solver="envelope", judges_route=True))
    assert plan.quality_finish is None and "Intrinsic Catalyst" in {priced.label for priced in plan.offers}
    assert plan.mean_remaining == pytest.approx(6 * A + _mean(84) * K, rel=1e-9)
