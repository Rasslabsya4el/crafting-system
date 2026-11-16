"""Blocking and filler bench crafts offered by a rule, not by the target (#886, OR-41), on a hand-worked belt of the fixture data.

The world: a rare belt that holds the Energy Shield prefix and two suffixes (Fire and Cold Resistance). The goal is the top Life prefix,
`IncreasedLife3`. The belt's open pool, with no family it holds: prefixes Life 1, 2 and 3 (1,000 each); suffixes Life Regeneration (1,000),
Lightning Resistance (8 x 1,000) and Chaos Resistance (6 x 250), 10,500 in all. Two prefix slots are open and one suffix slot. The test data
adds two bench crafts of Belts, both suffixes of a family no draw gives (`TestFiller` and `TestFillerTwo`), at 1 and 3 Orbs of Alteration.
The bought start item costs `S`, an Exalted Orb `e`, an Orb of Alteration `c`.

* An Exalted Orb adds a prefix with chance 3,000 / 13,500 = 2/9, and that prefix is Life 3 with chance 1/3; otherwise it adds a suffix,
  which fills the suffixes, and the next Exalted Orb adds a prefix, Life 3 with chance 1/3. A Life 1 or 2 takes the Life family for good,
  and the item is bought again. So `V = e + (7/9) e + (2/3)(S + V)`, that is `V = 16e/3 + 2S`.
* With the filler crafted first the suffixes are full at once: `V = c + e + (2/3)(S + V)`, that is `V = 3(c + e) + 2S`, cheaper exactly
  when `c < 7e/9`.

At S = 50, e = 10, c = 1: 153.33 without the craft and 133 with it. The target names the kinds it uses (an Exalted Orb is opt-in until
#886's second part) and names no craft.
"""

import dataclasses
import datetime

import pytest
from test_cli_offers import BELT, PRICED_DATA

from crafting_system.abstraction import Goal
from crafting_system.data.model import BenchActions, BenchOption, CostEntry, Mod, StatRange
from crafting_system.planner import PlanSettings, _envelope, _offers, plan_target
from crafting_system.planner import _plan as planner_plan
from crafting_system.planner._offers import offers_for
from crafting_system.prices import PriceFile
from crafting_system.prices.price_file import PriceEntry
from crafting_system.prices.provenance import EXCHANGE, Provenance
from crafting_system.targets import load_target

ALTERATION = "Metadata/Items/Currency/CurrencyRerollMagic"
FILLER, FILLER_TWO = "TestMasterFiller", "TestMasterFillerTwo"
S, E, C = 50.0, 10.0, 1.0


def _filler(mod_id: str, family: str) -> Mod:
    template = PRICED_DATA.mods["StrMasterItemGenerationCannotChangePrefixes"]  # a crafted suffix of the fixture, as a template
    return dataclasses.replace(
        template, id=mod_id, name="of Filling", text="+1 to Filling", type=family, families=(family,), stats=(StatRange(f"test_{family}", 1, 1),)
    )


def _option(mod_id: str, alterations: int) -> BenchOption:
    return BenchOption("Test Master", 0, ("Belt",), (CostEntry(ALTERATION, alterations),), BenchActions(mod_id, None, None, None, None, None, None, None, None))


@pytest.fixture(scope="module")
def data():
    mods = {**PRICED_DATA.mods, FILLER: _filler(FILLER, "TestFiller"), FILLER_TWO: _filler(FILLER_TWO, "TestFillerTwo")}
    regal = "Metadata/Items/Currency/CurrencyUpgradeToRare"  # some belt crafts of the fixture bench cost it (unpriced here: they are left out)
    template = PRICED_DATA.base_items[ALTERATION]
    bases = {**PRICED_DATA.base_items, regal: dataclasses.replace(template, id=regal, name="Regal Orb")}
    options = (*PRICED_DATA.bench_options, _option(FILLER, 1), _option(FILLER_TWO, 3))
    return dataclasses.replace(PRICED_DATA, mods=mods, base_items=bases, bench_options=options)


def _prices(alteration: float = C) -> PriceFile:
    day = "2026-10-30"
    entry = lambda chaos: PriceEntry(chaos, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", day, 1e9))  # noqa: E731
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, {"Exalted Orb": entry(E), "Orb of Alteration": entry(alteration)})


TARGET = """\
base: Leather Belt
item_level: 84
influence: []
requirements:
  - family: IncreasedLife
start_item:
  rarity: rare
  mods:
    - mod: IncreasedEnergyShield1
      values: [1]
    - mod: FireResist1
      values: [6]
    - mod: ColdResist1
      values: [6]
start: bought
actions: [exalted-orb, bench-craft]
"""


@pytest.fixture
def target(tmp_path, data):
    path = tmp_path / "belt.yaml"
    path.write_text(TARGET, encoding="utf-8")
    return load_target(path, data)


@pytest.fixture(autouse=True)
def every_shared_kernel_checked(monkeypatch):
    monkeypatch.setattr(_envelope, "CHECK_SHARED", True)  # the search builds every kernel it shares by key again and compares (#886)


def _plan(data, target, monkeypatch, blocking: bool, alteration: float = C):
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", blocking)
    return plan_target(data, target, _prices(alteration), PlanSettings(recipe_starts=False, start_price=S, solver="envelope"))


def _fills(label: str) -> bool:
    return "Filling" in label


def test_without_the_rule_the_plan_exalts_until_a_prefix_at_16e_over_3_plus_2s(data, target, monkeypatch):
    plan = _plan(data, target, monkeypatch, blocking=False)
    assert target.base_id == BELT
    assert plan.mean_remaining == pytest.approx(16 * E / 3 + 2 * S, rel=1e-9)
    assert not any(_fills(entry.label) for entry in plan.offers)


def test_with_the_rule_the_plan_fills_the_suffix_with_the_cheaper_craft_then_exalts_at_3_c_plus_e_plus_2s(data, target, monkeypatch):
    plan = _plan(data, target, monkeypatch, blocking=True)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    first = next(entry for entry in plan.offers if entry.label == plan.solution.policy[plan.start].label)  # the solver's action of that offer
    assert _fills(first.label) and first.cost == C
    assert [entry.label for entry in plan.offers if _fills(entry.label)] == [first.label]  # one class: the dearer filler is not offered ...
    assert any(_fills(label) for limit in plan.limits for label in limit.labels)  # ... and the answer says so


def test_when_the_craft_costs_more_than_seven_ninths_of_an_exalted_orb_the_plan_does_not_use_it(data, target, monkeypatch):
    plan = _plan(data, target, monkeypatch, blocking=True, alteration=8.0)
    assert plan.mean_remaining == pytest.approx(16 * E / 3 + 2 * S, rel=1e-9)


def test_with_no_action_that_keeps_a_craft_and_reads_the_mods_only_the_metamods_are_offered(data, target):
    goal = Goal.from_target(target)
    rerolls = offers_for(data, goal, BELT, target.start_item, ["chaos-orb", "bench-craft"], blocking=True)
    crafts = [entry for entry in rerolls.offers if entry.kind == "bench-craft"]
    assert crafts and all(entry.blocks is not None for entry in crafts)  # every one is offered by the rule ...
    assert all({family for mod_id in entry.action.adds(data, target.start_item).named for family in data.mods[mod_id].families} & _offers.METAMOD_FAMILIES for entry in crafts)  # ... as a metamod
    assert any(_fills(label) for limit in rerolls.limits for label in limit.labels)


def test_a_filler_and_a_family_a_draw_gives_are_different_classes(data, target):
    goal = Goal.from_target(target)
    found = offers_for(data, goal, BELT, target.start_item, ["exalted-orb", "bench-craft"], blocking=True)
    classes = {entry.label: entry.blocks for entry in found.offers if entry.blocks is not None}
    fillers = {blocks for label, blocks in classes.items() if _fills(label)}
    assert fillers == {(("suffix",), frozenset(), frozenset())}  # the two fillers: one class
    assert set(classes.values()) == {
        (("suffix",), frozenset(), frozenset()),
        (("prefix",), frozenset(), frozenset()),  # the Elemental Damage with Attack Skills crafts: no draw on a belt gives that family
        (("prefix",), frozenset({"IncreasedEnergyShield"}), frozenset()),  # the Armour and Energy Shield craft blocks a family the belt draws
        (("suffix",), frozenset({"ItemGenerationCannotChangePrefixes"}), frozenset()),  # a metamod is told apart
    }


def test_on_an_item_that_takes_a_second_craft_two_fillers_are_told_apart_and_both_offered(tmp_path, data, monkeypatch):
    # with the multimod on the item a craft of a family already crafted is refused and one of another family is not: the two fillers differ
    held = TARGET.replace("    - mod: ColdResist1\n      values: [6]\n", "    - mod: StrIntMasterItemGenerationCanHaveMultipleCraftedMods\n      values: [1]\n      crafted: true\n")
    path = tmp_path / "multimod.yaml"
    path.write_text(held, encoding="utf-8")
    multimod = load_target(path, data)
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    plan = plan_target(data, multimod, _prices(), PlanSettings(recipe_starts=False, start_price=S, solver="envelope"))
    assert {entry.label for entry in plan.offers if _fills(entry.label)} == {"Bench craft +1 to Filling [TestMasterFiller]", "Bench craft +1 to Filling [TestMasterFillerTwo]"}


def test_r12_with_every_shared_kernel_checked_gives_the_plan_it_gives_unchecked(monkeypatch):
    from cli_support import R12, price_file
    from items_support import DATA

    settings = PlanSettings(recipe_starts=False, solver="envelope")
    checked = plan_target(DATA, load_target(R12, DATA), price_file(), settings)  # `CHECK_SHARED` is on (the fixture of this module)
    monkeypatch.setattr(_envelope, "CHECK_SHARED", False)
    unchecked = plan_target(DATA, load_target(R12, DATA), price_file(), settings)
    assert checked.mean_remaining == unchecked.mean_remaining


# ---- the exact price cut (#1069, `planner/_price_cut.py`) ---------------------------------------------------------------------------------------
# With the rule on, the belt is offered Prefixes Cannot Be Changed at two Divine Orbs. A plan without the metamods is made first: it is the filler
# plan above, `U = 3(c + e) + 2S = 133`. Buying the belt again and following that plan costs `S + U = 183`, so a craft priced at 183 or more is never
# better than that restart at any state but the start, and at the start it costs more than the whole plan: it is left out before the model is built,
# and the model then tracks no metamod. A Divine Orb at 92 Chaos prices the lock at 184 (cut), at 91 at 182 (kept); the plan is 133 either way.

LOCK = "Bench craft Prefixes Cannot Be Changed"


def _plan_at(data, target, monkeypatch, divine: float):
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    prices = dataclasses.replace(_prices(), chaos_per_divine=divine)
    return plan_target(data, target, prices, PlanSettings(recipe_starts=False, start_price=S, solver="envelope"))


def _cut_labels(plan) -> set[str]:
    return {label for limit in plan.limits if limit.kind == "proved-unneeded" and limit.what == "Not searched" for label in limit.labels}


def test_a_lock_priced_above_a_restart_and_the_known_plan_is_cut_and_the_model_tracks_no_metamod(data, target, monkeypatch):
    plan = _plan_at(data, target, monkeypatch, divine=92.0)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    assert LOCK not in {entry.label for entry in plan.offers}
    assert LOCK in _cut_labels(plan)  # ... and the answer says why (OR-13)
    assert not plan.abstraction.models_metamods


def test_a_lock_priced_just_below_is_kept_and_the_plan_is_the_same(data, target, monkeypatch):
    plan = _plan_at(data, target, monkeypatch, divine=91.0)
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    assert LOCK in {entry.label for entry in plan.offers} and not _cut_labels(plan)
    assert plan.abstraction.models_metamods


def test_a_given_start_has_no_restart_so_nothing_is_cut(tmp_path, data, monkeypatch):
    path = tmp_path / "given.yaml"
    path.write_text(TARGET.replace("start: bought", "start: given"), encoding="utf-8")
    given = load_target(path, data)
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    asked = []
    monkeypatch.setattr(planner_plan, "plan_without", lambda *args, **kwargs: asked.append(1))
    with pytest.raises(planner_plan.PlanError, match="no policy"):  # a Life 1 or 2 takes the family for good, and a held belt cannot be bought again
        plan_target(data, given, _prices(), PlanSettings(recipe_starts=False, solver="envelope"))
    assert not asked  # no plan is made to cut against: with no restart an offer dearer than any plan may still be the only way on


def test_the_cut_keeps_the_restart_cuts_at_a_tie_and_cuts_nothing_without_a_finite_figure():
    from crafting_system.planner._offers import RESTART, BuyStartItem, Offer, PricedOffer
    from crafting_system.planner._price_cut import restart_dominated

    restart = PricedOffer(Offer(RESTART, BuyStartItem(None), {"belt": 1}, shares=False), 500.0, ())
    cheap, tie, dear = (PricedOffer(Offer(label, None, {}), cost, ()) for label, cost in (("cheap", 182.9), ("tie", 183.0), ("dear", 600.0)))
    kept, cut = restart_dominated((cheap, tie, dear, restart), 50.0, 133.0)
    assert kept == (cheap, restart) and cut == (tie, dear)
    assert restart_dominated((cheap, dear), 50.0, float("inf")) == ((cheap, dear), ())


def test_a_judged_route_is_judged_against_every_offer_so_nothing_is_cut(data, target, monkeypatch):
    monkeypatch.setattr(_offers, "BLOCKING_CRAFTS", True)
    prices = dataclasses.replace(_prices(), chaos_per_divine=92.0)
    plan = plan_target(data, target, prices, PlanSettings(recipe_starts=False, start_price=S, solver="envelope", judges_route=True))
    assert LOCK in {entry.label for entry in plan.offers} and not _cut_labels(plan)  # a route may name the lock: it is a fixed policy, not the cheapest


def test_when_the_net_stops_the_plan_without_the_metamods_that_plan_is_the_answer_and_says_what_it_did_not_try(data, target, monkeypatch):
    real = planner_plan.plan_without

    def stopped(*args, **kwargs):  # the plan without the lock, as a net would leave it
        plan = real(*args, **kwargs)
        info = plan.packed.info["envelope"]
        plan.packed.info["envelope"] = dataclasses.replace(info, exact=False, stopped="the time limit of 600 seconds was reached")
        return plan

    monkeypatch.setattr(planner_plan, "plan_without", stopped)
    plan = _plan_at(data, target, monkeypatch, divine=91.0)  # a lock at 182 would be kept: it is not tried at all
    assert plan.mean_remaining == pytest.approx(3 * (C + E) + 2 * S, rel=1e-9)
    assert LOCK not in {entry.label for entry in plan.offers}
    assert any(limit.what == "Not tried" and LOCK in limit.labels for limit in plan.limits)
    assert plan.risk is not None
