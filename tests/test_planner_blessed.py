"""A base implicit's roll and the Blessed Orb as a method of the planner (#1231, #159 part 2, OR-37: R06's Blessed Orb is in the beta), planned
through the entry and the envelope search on the fixture Paua Amulet of item level 84 (`targets_support`).

The amulet's own implicit is `ManaRegenerationImplicitAmulet1`, "(20-30)% increased Mana Regeneration Rate": 11 whole values. A start item that
does not list it holds it at the low end, 20 (`targets.parse`). The numbers, worked by hand from the roll law of the Blessed Orb
(`blessed_orb.new_value_uniform_in_range`, `blessed_orb.previous_value_can_repeat`: each value uniform over the range, whatever it was):

* a wish for 30 or more: one use meets it with chance `p = 1/11`, the same at every use, so the mean number of uses is `1 / p = 11` and the
  roll costs `11 b` at `b` Chaos per Blessed Orb; a wish for 28 or more: `p = 3/11`, `11/3 b`; a start that holds 30 already: 0.
* with the one prefix of the bench craft `(15-23)% increased Elemental Damage with Attack Skills` (6 Orbs of Alteration at `a`; as in
  `test_planner_catalysts`): `6a + 11 b`; with 20% Intrinsic quality too, `6a + 11 b + E(0) k` (`E(0) = 13.35` catalysts at item level 84).

The roll is a finish (`planner._implicit_finish`): no other method of the beta changes a base implicit, so the plan is the plan of the mods without
the wish (`Plan.mean_remaining`) plus `b / p` (`Plan.implicit_finish_value`), the whole in `Plan.total_mean`. Where the finish is not exact the
wish is searched with the mods: the key of the bound's model holds the implicit's roll status (ticket #158) and the Blessed Orb is an offer of
the search; both ways give the same mean (`test_the_finish_and_the_search_give_the_same_mean`).
"""

import datetime
from fractions import Fraction

import pytest
from targets_support import DATA, parse
from test_cli_offers import with_currency_names

from crafting_system.actions import ApplyCatalyst, BlessedOrb, expected_catalysts
from crafting_system.items import CatalystType
from crafting_system.planner import PlanError, PlanSettings, plan_target
from crafting_system.planner import _envelope, _implicit_finish
from crafting_system.prices import PriceFile
from crafting_system.prices.price_file import PriceEntry
from crafting_system.prices.provenance import EXCHANGE, Provenance

D = with_currency_names(DATA)
B, A, K = 0.25, 0.5, 2.0  # a Blessed Orb, an Orb of Alteration and an Intrinsic Catalyst, in Chaos
IMPLICIT = "ManaRegenerationImplicitAmulet1"
FAMILY = DATA.mods[IMPLICIT].families[0]
HELD = f"""\
requirements:
  - family: LightningResistance
    min_tier: 2
implicits:
  - family: {FAMILY}
    min_roll: 30
start_item:
  rarity: rare
  mods:
    - mod: LightningResist7
      values: [45]
"""
CRAFTED = f"""\
requirements:
  - family: IncreasedWeaponElementalDamagePercent
    mod: EinharMasterWeaponElementalDamage1_
implicits:
  - family: {FAMILY}
    min_roll: 30
start_item:
  rarity: rare
  mods:
    - mod: LightningResist7
      values: [45]
"""
QUALITY = "quality:\n  type: intrinsic\n  min_percent: 20\nstart_item:\n"


@pytest.fixture(autouse=True)
def every_shared_kernel_checked(monkeypatch):
    monkeypatch.setattr(_envelope, "CHECK_SHARED", True)  # the search builds every kernel it shares by key again and compares (#886)


def _prices(**chaos: float) -> PriceFile:
    entry = lambda value: PriceEntry(value, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", "2026-10-30", 1e9))  # noqa: E731
    named = {"Blessed Orb": B, "Orb of Alteration": A, "Intrinsic Catalyst": K, **chaos}
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, {name: entry(value) for name, value in named.items()})


def _plan(text: str, methods=("blessed-orb",), seen: list | None = None, searched: bool = False):
    """The plan of `text`; `searched`: the implicit is searched with the mods instead of finished last (the path where the finish is not exact)."""
    target = parse(text, methods=methods)
    settings = PlanSettings(recipe_starts=False, solver="envelope", watch=None if seen is None else seen.append)
    if searched:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(_implicit_finish, "FINISH", False)
            return plan_target(D, target, _prices(), settings)
    return plan_target(D, target, _prices(), settings)


def test_the_fixture_implicit_rolls_over_eleven_values_and_the_start_holds_its_lowest():
    stat = DATA.mods[IMPLICIT].stats[0]
    assert (stat.min, stat.max) == (20, 30)
    (held,) = parse(HELD).start_item.implicits
    assert held.mod_id == IMPLICIT and held.values == (20,)


def test_one_orb_meets_the_wish_with_the_hand_worked_chance():
    start = parse(HELD).start_item
    wish = parse(HELD).implicits
    assert _implicit_finish.chance_of_meeting(D, BlessedOrb(), start, wish) == Fraction(1, 11)
    lower = parse(HELD.replace("min_roll: 30", "min_roll: 28")).implicits
    assert _implicit_finish.chance_of_meeting(D, BlessedOrb(), start, lower) == Fraction(3, 11)


def test_an_item_with_every_mod_costs_its_blessed_orbs_eleven_b():
    plan = _plan(HELD)
    assert plan.mean_remaining == 0.0  # the start holds every mod: the mods cost nothing
    assert plan.implicit_finish is not None and plan.implicit_finish.orb.label == "Blessed Orb"
    assert plan.implicit_finish.uses == 11
    assert plan.total_mean == pytest.approx(11 * B, rel=1e-12)  # 2.75
    assert not any(priced.label == "Blessed Orb" for priced in plan.offers)  # the mods are planned without the wish
    (said,) = [limit for limit in plan.limits if limit.kind == "implicit-finish"]
    assert said.labels == ("Blessed Orb",) and "11.00 on average" in said.why and "2.75 Chaos" in said.why and "rolls 30 or more" in said.why


def test_a_lower_wish_costs_eleven_thirds_b():
    plan = _plan(HELD.replace("min_roll: 30", "min_roll: 28"))
    assert plan.implicit_finish.uses == Fraction(11, 3)
    assert plan.total_mean == pytest.approx(11 / 3 * B, rel=1e-12)


def test_a_start_that_holds_the_roll_asked_adds_nothing():
    text = HELD.replace("      values: [45]\n", f"      values: [45]\n  implicits:\n    - mod: {IMPLICIT}\n      values: [30]\n")
    plan = _plan(text)
    assert plan.total_mean == 0.0 and plan.implicit_finish.orb is None
    (said,) = [limit for limit in plan.limits if limit.kind == "implicit-finish"]
    assert "nothing is added" in said.why


def test_a_bench_craft_then_the_blessed_orbs_cost_6a_plus_11b():
    plan = _plan(CRAFTED, methods=("bench-craft", "blessed-orb"))
    assert plan.mean_remaining == pytest.approx(6 * A, rel=1e-9)  # the mods: the craft
    assert plan.total_mean == pytest.approx(6 * A + 11 * B, rel=1e-9)  # 3 + 2.75


def test_the_quality_and_the_implicit_are_both_finished_and_each_line_gives_the_whole_total():
    plan = _plan(CRAFTED.replace("start_item:\n", QUALITY), methods=("bench-craft", "blessed-orb", "catalyst"))
    catalysts = float(expected_catalysts(84, 20, 0)) * K
    assert plan.quality_finish is not None and plan.implicit_finish is not None
    assert plan.total_mean == pytest.approx(6 * A + 11 * B + catalysts, rel=1e-9)  # 3 + 2.75 + 26.69
    total = f"{6 * A + 11 * B + catalysts:,.2f} Chaos on average after the start item"
    assert all(total in limit.why for limit in plan.limits if limit.kind in ("implicit-finish", "quality-finish"))


def test_the_finish_and_the_search_give_the_same_mean():
    seen: list = []
    finished = _plan(CRAFTED, methods=("bench-craft", "blessed-orb"))
    searched = _plan(CRAFTED, methods=("bench-craft", "blessed-orb"), seen=seen, searched=True)
    expected = 6 * A + 11 * B
    assert searched.implicit_finish is None and "Blessed Orb" in {priced.label for priced in searched.offers}
    assert searched.mean_remaining == pytest.approx(expected, rel=1e-9)
    assert finished.total_mean == pytest.approx(searched.total_mean, rel=1e-9)
    assert all(standing.lower <= expected * (1 + 1e-9) for standing in seen)
    assert seen[-1].lower == pytest.approx(expected, rel=1e-9)  # proved: the bound met the plan


def test_searched_alone_the_bound_is_the_plans_cost_from_the_first_standing():
    seen: list = []
    plan = _plan(HELD, seen=seen, searched=True)
    assert plan.mean_remaining == pytest.approx(11 * B, rel=1e-9)
    assert seen and seen[0].lower == pytest.approx(11 * B, rel=1e-9)  # the Blessed Orb's kernel is in the bound's model


def test_a_run_whose_methods_name_no_blessed_orb_is_refused_with_the_reason():
    with pytest.raises(PlanError, match="rolls 30 or more, and no Blessed Orb is among the methods offered"):
        _plan(CRAFTED, methods=("bench-craft",))


def test_a_blessed_orb_without_a_price_is_refused_with_the_reason():
    target = parse(HELD, methods=("blessed-orb",))
    prices = _prices()
    prices = PriceFile(prices.league, prices.fetched_at, prices.chaos_per_divine, {k: v for k, v in prices.prices.items() if k != "Blessed Orb"})
    with pytest.raises(PlanError, match="no Blessed Orb has a price"):
        plan_target(D, target, prices, PlanSettings(recipe_starts=False, solver="envelope"))


def test_a_target_with_no_implicit_roll_is_offered_no_blessed_orb_and_told_nothing_of_it():
    no_wish = HELD.replace(f"implicits:\n  - family: {FAMILY}\n    min_roll: 30\n", "")
    plan = _plan(no_wish, methods=("blessed-orb", "chaos-orb"))
    assert not any(priced.label == "Blessed Orb" for priced in plan.offers)
    assert not any("Blessed Orb" in limit.labels for limit in plan.limits)
    assert plan.implicit_finish is None and plan.mean_remaining == 0.0  # the start meets the goal
    plan = plan_target(D, parse(no_wish), _prices(), PlanSettings(recipe_starts=False, solver="envelope"))  # nor with the default offers
    assert not any("Blessed Orb" in limit.labels for limit in plan.limits)


def test_the_finish_holds_only_while_no_offered_action_changes_the_implicits():
    assert _implicit_finish.holds(D, [ApplyCatalyst(CatalystType.INTRINSIC)])
    assert not _implicit_finish.holds(D, [BlessedOrb()])  # an action that rerolls the implicits: the wish is searched with the mods
    target = parse(HELD, methods=("blessed-orb", "hinekora-lock"))
    assert not _implicit_finish.applies(D, target)  # a Blessed Orb is a burn of the Lock (ADR-0056): with the Lock named, the roll is searched
    assert _implicit_finish.applies(D, parse(HELD, methods=("blessed-orb",)))
    assert not _implicit_finish.applies(D, parse(HELD, methods=("blessed-orb",)), judged=True)  # a judged route may name the orb as a step
