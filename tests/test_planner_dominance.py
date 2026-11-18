"""The Orb of Dominance as a method of the planner (#1195, OR-37: Dominance is batch B2, a beta method), planned through the entry and the
envelope search on the hand-typed Contract Helmet of `influence_support.py`.

The orb removes one influenced mod of the item and upgrades another, each ordered pair of the n influenced mods with chance 1/(n(n-1))
(`dominance.picks_uniform_remove_first`); the upgrade is the next tier of the mod's own influence, and a top-tier mod becomes its Elevated
version (`dominance.upgrade_next_tier_top_becomes_elevated`). The start is a bought rare helmet at `S` Chaos, the orb costs `d`, and the run's
methods setting offers the orb alone, so an item the orb can no longer bring to the goal is bought again.

* The next tier. The start holds the Shaper prefix P1 (tier 3) and the Shaper suffix S1 (tier 2); the goal is P2, the next tier of P1.
  Two outcomes, 1/2 each: S1 removed and P1 raised to P2 (the goal), or P1 removed and S1 raised to S2 (P is gone: bought again). So
  `V = d + (1/2)(S + V)`, `V = 2d + S`: 70 at d = 10, S = 50.
* The Elevated version. A Shaper and Elder helmet holds the top-tier Shaper prefix P3, S1 and the top-tier Elder suffix E; the goal is the
  Elevated P3 (named by `mod:`, OR-2: an Elevated mod has no natural tier). Six pairs, 1/6 each:
    (S1 out, P3 up) and (E out, P3 up): the goal;
    (P3 out, S1 up) and (P3 out, E up): P3 is gone, bought again;
    (S1 out, E up): {P3, Elevated E}; (E out, S1 up): {P3, S2}. From either, one more orb gives the goal with chance 1/2 (the other
    mod out, P3 up) and loses P3 with chance 1/2: `W = d + (1/2)(S + V)`.
  So `V = d + (1/3)(S + V) + (1/3)(d + (1/2)(S + V))`, `V/2 = (4/3)d + S/2`, `V = (8/3)d + S`: 130 at d = 30, S = 50.

The lower bound of the method: the orb reads the junk and the influenced mods (`Reads.influenced`) and adds a mod it does not name (the next
tier of whichever mod it picks, `Adds.named` None), so the offers' floors class it TERMINAL (`_offer_kinds`): its floor is its price, and
Wald's argument is cut at its first use. The search proves each plan exact: its last standing has its lower figure at the plan's cost, and
no standing is above it.
"""

import dataclasses
import datetime

import pytest
from influence_support import ELDER_S, ELEVATED, HELMET, INFLUENCE_DATA, P1, P2, P3, P3_MAVEN, PLAIN, S1
from test_cli_offers import with_currency_names

from crafting_system.abstraction import Goal
from crafting_system.actions import catalog, influence
from crafting_system.data.elevated import ElevatedMods
from crafting_system.items import Influence
from crafting_system.planner import PlanError, PlanSettings, plan_target
from crafting_system.planner import _envelope, _limits
from crafting_system.planner._offer_kinds import TERMINAL, _kind_of
from crafting_system.planner._offers import ROLLS_UNFOLLOWED, Offer, PricedOffer, offers_for
from crafting_system.prices import PriceFile
from crafting_system.prices.price_file import PriceEntry
from crafting_system.prices.provenance import EXCHANGE, Provenance
from crafting_system.targets import load_target

DATA = with_currency_names(INFLUENCE_DATA)
S = 50.0
METHODS = ("orb-of-dominance",)  # the run's methods setting (#405: a target names none)

TARGET = """\
base: Contract Helmet
item_level: 84
influence: [{influences}]
requirements:
  - family: {family}
    mod: {mod}
start_item:
  rarity: rare
  mods:
{mods}
start: bought
"""


@pytest.fixture(autouse=True)
def every_shared_kernel_checked(monkeypatch):
    monkeypatch.setattr(_envelope, "CHECK_SHARED", True)  # the search builds every kernel it shares by key again and compares (#886)


@pytest.fixture(autouse=True)
def the_fixture_knows_its_elevated_mods(monkeypatch):
    # The committed mapping holds for the export it was made for (`ElevatedMods.for_data`); the fixture's own pairs stand in for it here.
    mapping = ElevatedMods(DATA.version, "fixture", dict(ELEVATED), ())
    monkeypatch.setattr(influence, "load_elevated", lambda: mapping)


def _prices(dominance: float) -> PriceFile:
    day = "2026-10-30"
    entry = PriceEntry(dominance, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", day, 1e9))
    return PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, {"Orb of Dominance": entry})


def _target(tmp_path, family: str, mod: str, mods: tuple[tuple[str, tuple[int, ...]], ...], influences: str = "shaper"):
    lines = "\n".join(f"    - mod: {mod_id}\n      values: {list(values)}" for mod_id, values in mods)
    path = tmp_path / "helmet.yaml"
    path.write_text(TARGET.format(influences=influences, family=family, mod=mod, mods=lines), encoding="utf-8")
    return dataclasses.replace(load_target(path, DATA), actions=METHODS)


def _low(mod_id: str) -> tuple[int, ...]:
    return tuple(min(stat.min, stat.max) for stat in DATA.mods[mod_id].stats)


def _plan(target, prices: PriceFile, seen: list | None = None):
    settings = PlanSettings(recipe_starts=False, start_price=S, solver="envelope", watch=None if seen is None else seen.append)
    return plan_target(DATA, target, prices, settings)


def test_the_orb_of_dominance_is_a_planner_kind_offered_by_default():
    from crafting_system.actions import kinds

    (kind,) = [each for each in kinds() if each.name == "orb-of-dominance"]
    assert kind.planner and not kind.opt_in  # a beta method, offered by default (OR-37, OR-41)


def test_dominance_raises_p1_to_its_next_tier_at_2d_plus_s(tmp_path):
    target = _target(tmp_path, "ContractHelmetShaperP", P2, ((P1, _low(P1)), (S1, _low(S1))))
    assert target.base_id == HELMET
    seen: list = []
    plan = _plan(target, _prices(10.0), seen)
    assert plan.mean_remaining == pytest.approx(2 * 10.0 + S, rel=1e-9)
    assert seen and all(standing.lower <= 70.0 * (1 + 1e-9) for standing in seen)
    assert seen[-1].lower == pytest.approx(70.0, rel=1e-9)  # proved: the bound met the plan


def test_dominance_raises_the_top_tier_p3_to_its_elevated_version_at_8d_over_3_plus_s(tmp_path):
    mods = ((P3, _low(P3)), (S1, _low(S1)), (ELDER_S, _low(ELDER_S)))
    target = _target(tmp_path, "ContractHelmetShaperP", P3_MAVEN, mods, influences="shaper, elder")
    seen: list = []
    plan = _plan(target, _prices(30.0), seen)
    assert plan.mean_remaining == pytest.approx(8 * 30.0 / 3 + S, rel=1e-9)
    assert seen[-1].lower == pytest.approx(8 * 30.0 / 3 + S, rel=1e-9)


def test_an_item_with_one_influenced_mod_takes_no_orb(tmp_path):
    # P1 beside the Plain prefix: one influenced mod, so the orb is refused (`dominance.gate`), and with no other method there is no plan
    target = _target(tmp_path, "ContractHelmetShaperP", P2, ((P1, _low(P1)), (PLAIN, _low(PLAIN))))
    with pytest.raises(PlanError):
        _plan(target, _prices(10.0))


def test_the_orb_is_listed_where_it_may_act_on_the_way_and_not_where_it_never_can(tmp_path):
    start = _target(tmp_path, "ContractHelmetShaperP", P2, ((P1, _low(P1)), (S1, _low(S1)))).start_item
    assert len(catalog(DATA, start, planner_only=True, names=METHODS)) == 1
    plain = dataclasses.replace(start, influences=frozenset(), mods=())
    for may in (plain, dataclasses.replace(plain, rarity=start.rarity.NORMAL)):  # an influenced Exalted Orb and later draws may give it two
        assert len(catalog(DATA, may, planner_only=True, names=METHODS)) == 1
    for never in (
        dataclasses.replace(start, corrupted=True),
        dataclasses.replace(plain, item_level=67),  # no influence, and too low for an influenced Exalted Orb to give one
        dataclasses.replace(plain, mods=(dataclasses.replace(start.mods[0], mod_id=PLAIN, values=_low(PLAIN), fractured=True),)),
    ):
        assert catalog(DATA, never, planner_only=True, names=METHODS) == ()
    ring = dataclasses.replace(DATA.base_items[HELMET], item_class="Ring")
    data = dataclasses.replace(DATA, base_items={**DATA.base_items, HELMET: ring})
    assert catalog(data, start, planner_only=True, names=METHODS) == ()  # body armour, boots, gloves and helmets only


def test_the_orb_is_terminal_for_the_offers_floors_so_its_floor_is_its_price(tmp_path):
    start = _target(tmp_path, "ContractHelmetShaperP", P2, ((P1, _low(P1)), (S1, _low(S1)))).start_item
    (orb,) = catalog(DATA, start, planner_only=True, names=METHODS)
    assert _kind_of(DATA, start, PricedOffer(Offer(orb.label(), orb, {}), 10.0, ()))[0] == TERMINAL


def test_a_goal_with_a_roll_limit_leaves_the_orb_out_and_says_it_as_a_model_gap(tmp_path):
    # Under a roll limit the state cannot follow the new tier the orb puts on (it is kept at its lowest values) nor an Elevated mod it
    # rerolls, and only at the states where it picks one: the search would refuse the route, so the orb is left out and the answer says so
    # (`Adds.rolls_unfollowed`, #993). Without the limit it is offered.
    mods = ((P1, _low(P1)), (S1, _low(S1)))
    free = _target(tmp_path, "ContractHelmetShaperP", P2, mods)
    chosen = offers_for(DATA, Goal.from_target(free), free.base_id, free.start_item, free.actions)
    assert [offer.label for offer in chosen.offers] == ["Orb of Dominance"]
    lowest = [min(stat.min, stat.max) for stat in DATA.mods[P2].stats]
    path = tmp_path / "limited.yaml"
    path.write_text((tmp_path / "helmet.yaml").read_text(encoding="utf-8").replace(f"    mod: {P2}\n", f"    mod: {P2}\n    min_roll: [{lowest[0]}, null]\n"), encoding="utf-8")
    limited = dataclasses.replace(load_target(path, DATA), actions=METHODS)
    chosen = offers_for(DATA, Goal.from_target(limited), limited.base_id, limited.start_item, limited.actions)
    assert chosen.offers == ()
    (gap,) = [limit for limit in chosen.limits if limit.kind == _limits.LISTING_GAP]
    assert gap.labels == (_limits.kind_title("orb-of-dominance"),) and gap.names == (ROLLS_UNFOLLOWED,)


def test_a_roll_limited_goal_is_planned_without_the_orb_where_it_was_refused_before(tmp_path):
    # A rare helmet with no influence and the Plain prefix, the goal the top Shaper prefix P3 with a roll limit at its lowest values, and the
    # methods the orb and the influenced Exalted Orbs: the orb is listed (item level 84) but left out for the roll limit, said as a model gap,
    # and the plan is #818's Shaper's Exalted Orb until P3: `V = 9e + 8S`, 490 at e = 10, S = 50.
    lowest = [min(stat.min, stat.max) for stat in DATA.mods[P3].stats]
    limit = "[" + ", ".join([str(lowest[0])] + ["null"] * (len(lowest) - 1)) + "]"
    path = tmp_path / "limited.yaml"
    text = TARGET.format(influences="", family="ContractHelmetShaperP", mod=P3, mods=f"    - mod: {PLAIN}\n      values: {list(_low(PLAIN))}")
    path.write_text(text.replace(f"    mod: {P3}\n", f"    mod: {P3}\n    min_roll: {limit}\n"), encoding="utf-8")
    target = dataclasses.replace(load_target(path, DATA), actions=("influenced-exalted-orb", *METHODS))
    names = {"Orb of Dominance": 30.0, **{f"{influence.value.capitalize()}'s Exalted Orb": 1000.0 for influence in Influence}}
    names["Shaper's Exalted Orb"] = 10.0
    day = "2026-10-30"
    entries = {name: PriceEntry(value, "poe.ninja", None, None, Provenance(EXCHANGE, "Test", day, 1e9)) for name, value in names.items()}
    prices = PriceFile("Test", datetime.datetime(2026, 10, 30, tzinfo=datetime.UTC), 300.0, entries)
    plan = _plan(target, prices)
    assert plan.mean_remaining == pytest.approx(9 * 10.0 + 8 * S, rel=1e-9)
    gaps = [limit for limit in plan.limits if limit.kind == _limits.LISTING_GAP]
    assert len(gaps) == 1 and gaps[0].labels == (_limits.kind_title("orb-of-dominance"),) and gaps[0].names == (ROLLS_UNFOLLOWED,)
