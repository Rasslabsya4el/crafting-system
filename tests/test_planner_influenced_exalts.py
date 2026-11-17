"""The six influenced Exalted Orbs as a method of the planner (#818, OR-37: influence Exalts are batch B2, a beta method), planned through the
entry and the envelope search on the hand-typed Contract Helmet of `influence_support.py`.

The world: a bought rare Contract Helmet of item level 84 holding the Plain prefix (no influence), at `S` Chaos. An influenced Exalted Orb
adds its influence and one mod of that influence (`influence.exalt_adds_influence_and_one_mod`) and is refused on an influenced item, so
one orb is all an item takes; a failed item is bought again.

* Shaper's Exalted Orb, at `e`: the Shaper pool is the prefix family P (300 + 300 + 200 = 800) and the suffix family S (500 + 500 = 1,000),
  1,800 in all; the top prefix `ContractHelmetShaperP3` comes with chance 200 / 1,800 = 1/9. So `V = e + (8/9)(S + V)`, `V = 9e + 8S`:
  490 at S = 50, e = 10.
* Elder's Exalted Orb, at `e`: the Elder pool is the suffix `ContractHelmetElderS1` (400) and the prefix `ContractHelmetElderP1` (100); the
  suffix comes with chance 4/5. So `V = e + (1/5)(S + V)`, `V = 5e/4 + S/4`: 37.5 at S = 50, e = 20.

The lower bound of the method: the orb reads the implicits (it is refused on an Eldritch implicit) and changes the influences, so it leaves
the start's shape. The offers' floors class it TERMINAL (`_offer_kinds`): its floor is its price, and Wald's argument is cut at its first
use. The search proves each plan exact: its last standing has its lower figure at the plan's cost, and no standing is above it.
"""

import dataclasses
import datetime

import pytest
from influence_support import ELDER_S, HELMET, INFLUENCE_DATA, P3
from test_cli_offers import with_currency_names

from crafting_system.actions import catalog
from crafting_system.items import Influence
from crafting_system.planner import PlanError, PlanSettings, plan_target
from crafting_system.planner import _envelope
from crafting_system.planner._offer_kinds import TERMINAL, _kind_of
from crafting_system.planner._offers import Offer, PricedOffer
from crafting_system.prices import PriceFile
from crafting_system.prices.price_file import PriceEntry
from crafting_system.prices.provenance import EXCHANGE, Provenance
from crafting_system.targets import load_target

DATA = with_currency_names(INFLUENCE_DATA)
S = 50.0
METHODS = ("influenced-exalted-orb",)  # the run's methods setting (#405: a target names none)

TARGET = """\
base: Contract Helmet
item_level: {level}
requirements:
  - family: {family}
    mod: {mod}
start_item:
  rarity: rare
  mods:
    - mod: ContractHelmetPlain1
      values: [1, 5]
start: bought
"""


@pytest.fixture(autouse=True)
def every_shared_kernel_checked(monkeypatch):
    monkeypatch.setattr(_envelope, "CHECK_SHARED", True)  # the search builds every kernel it shares by key again and compares (#886)


def _prices(regal: float = 1000.0, **chaos: float) -> PriceFile:
    day = "2026-10-30"
    entry = lambda value: PriceEntry(value, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", day, 1e9))  # noqa: E731
    names = {f"{influence.value.capitalize()}'s Exalted Orb": influence.value for influence in Influence}
    entries = {name: entry(chaos.get(key, 1000.0)) for name, key in names.items()}
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, {**entries, "Regal Orb": entry(regal)})


def _target(tmp_path, family: str, mod: str, level: int = 84, rarity: str = "rare", methods: tuple[str, ...] = METHODS):
    path = tmp_path / "helmet.yaml"
    path.write_text(TARGET.format(family=family, mod=mod, level=level).replace("rarity: rare", f"rarity: {rarity}"), encoding="utf-8")
    return dataclasses.replace(load_target(path, DATA), actions=methods)


def _plan(target, prices: PriceFile, seen: list | None = None):
    settings = PlanSettings(recipe_starts=False, start_price=S, solver="envelope", watch=None if seen is None else seen.append)
    return plan_target(DATA, target, prices, settings)


def test_the_influenced_exalted_orb_is_a_planner_kind():
    from crafting_system.actions import kinds

    (kind,) = [each for each in kinds() if each.name == "influenced-exalted-orb"]
    assert kind.planner and not kind.opt_in  # a beta method, offered by default (OR-37, OR-41)


def test_a_shapers_exalted_orb_until_the_top_shaper_prefix_costs_9e_plus_8s(tmp_path):
    target = _target(tmp_path, "ContractHelmetShaperP", P3)
    assert target.base_id == HELMET
    seen: list = []
    plan = _plan(target, _prices(shaper=10.0, elder=1.0), seen)  # the Elder orb is cheaper but never gives a Shaper mod
    assert plan.mean_remaining == pytest.approx(9 * 10.0 + 8 * S, rel=1e-9)
    assert seen and all(standing.lower <= 490.0 * (1 + 1e-9) for standing in seen)
    assert seen[-1].lower == pytest.approx(490.0, rel=1e-9)  # proved: the bound met the plan


def test_an_elders_exalted_orb_until_the_elder_suffix_costs_5e_over_4_plus_s_over_4(tmp_path):
    target = _target(tmp_path, "ContractHelmetElderS", ELDER_S)
    plan = _plan(target, _prices(elder=20.0, shaper=1.0))
    assert plan.mean_remaining == pytest.approx(5 * 20.0 / 4 + S / 4, rel=1e-9)


def test_the_cheaper_orb_is_not_taken_when_its_influence_cannot_give_the_mod(tmp_path):
    # Only the Shaper orb gives P3: at a Shaper price of 1,000 the plan is 9,000 + 400, whatever the other five cost
    target = _target(tmp_path, "ContractHelmetShaperP", P3)
    plan = _plan(target, _prices(shaper=1000.0, elder=0.5, crusader=0.5, hunter=0.5, redeemer=0.5, warlord=0.5))
    assert plan.mean_remaining == pytest.approx(9 * 1000.0 + 8 * S, rel=1e-9)


def test_a_magic_start_is_made_rare_by_a_regal_orb_and_then_takes_the_orb_at_9_r_plus_e_plus_8s(tmp_path):
    # The catalog is asked for the start item once: the orbs are listed for a magic item, which a Regal Orb makes rare. The Regal Orb adds an
    # uninfluenced mod (the item has no influence), which leaves a prefix slot open and takes no Shaper family, so the Shaper orb still gives
    # P3 with chance 1/9: `V = r + e + (8/9)(S + V)`, `V = 9(r + e) + 8S`, 508 at r = 2, e = 10.
    target = _target(tmp_path, "ContractHelmetShaperP", P3, rarity="magic", methods=("regal-orb", *METHODS))
    plan = _plan(target, _prices(regal=2.0, shaper=10.0))
    assert plan.mean_remaining == pytest.approx(9 * (2.0 + 10.0) + 8 * S, rel=1e-9)


def test_the_orbs_are_not_listed_where_they_can_never_act(tmp_path):
    start = _target(tmp_path, "ContractHelmetShaperP", P3).start_item
    assert len(catalog(DATA, start, planner_only=True, names=METHODS)) == len(Influence)
    for never in (
        dataclasses.replace(start, corrupted=True),
        dataclasses.replace(start, item_level=67),
        dataclasses.replace(start, influences=frozenset({Influence.ELDER})),
        dataclasses.replace(start, mods=tuple(dataclasses.replace(entry, fractured=True) for entry in start.mods)),
    ):
        assert catalog(DATA, never, planner_only=True, names=METHODS) == ()


def test_the_orb_is_terminal_for_the_offers_floors_so_its_floor_is_its_price(tmp_path):
    start = _target(tmp_path, "ContractHelmetShaperP", P3).start_item
    orbs = catalog(DATA, start, planner_only=True, names=METHODS)
    assert sorted(orb.label() for orb in orbs) == sorted(f"{influence.value.capitalize()}'s Exalted Orb" for influence in Influence)
    for orb in orbs:
        assert _kind_of(DATA, start, PricedOffer(Offer(orb.label(), orb, {}), 10.0, ()))[0] == TERMINAL


def test_no_orb_on_an_item_that_has_an_influence(tmp_path):
    # an Elder helmet takes no influenced Exalted Orb (`influence.exalt_refused_on_influenced_item`): with no other method, no plan
    path = tmp_path / "elder.yaml"
    path.write_text(TARGET.format(family="ContractHelmetElderS", mod=ELDER_S, level=84).replace("start: bought", "influence: [elder]\nstart: bought"), encoding="utf-8")
    target = dataclasses.replace(load_target(path, DATA), actions=METHODS)
    with pytest.raises(PlanError):
        _plan(target, _prices(elder=20.0))
