"""A key whose fractured mods leave the goal no room is one state, valued by the restart, never worked out (ticket #1367, Proposal A of #1360).

A fractured mod is never removed. When a key's fractured mods leave no item that meets the goal (a fractured mod that gives no leaf takes a
slot of its side; one below a leaf's tier takes that leaf's family), no plan from it reaches the goal without the restart, and its value is
exactly the restart's price plus the start's value (`abstraction/_pattern.py`, "The ruined keys"). The bound's build holds every such key in one
state whose row is the restart alone (`PatternModel.ruined`). On the hand-worked bow of `test_abstraction_pattern.py` with a Fracturing Orb:

* the test of a key: a fractured junk prefix ruins a key whose target needs all three prefixes, a fractured mod that gives a leaf does not, a
  fractured junk suffix does not where the suffixes have room; a fractured attack speed below the leaf's tier takes the leaf's family and ruins
  the key, unless the target accepts another leaf in its place; the test is off without a restart and with an offer that may take a fractured
  mod off;
* the model on all its offers with the ruined state and without it (`RUIN_KEYS`) have the same value at every key, the start's included
  (OR-12): a ruined key at the ruined state's value, and the keys the model without it reached only through ruined keys are ruined and at that
  value too;
* no member of a ruined key is made and no kernel is asked at a member of one;
* the plan through the planner's entry (`plan_target`) is the plan without it, on a bound with fewer keys.

Nothing here reads the clock; the bound's build runs with no net.
"""

import contextlib
import dataclasses
import datetime

import pytest
from abstraction_removals_support import ARROW_LEAF, AS_1, AS_5, BOW_DATA, SOCKET_LEAF, SPEED_TIER_1, bow
from test_abstraction_pattern import ACTIONS, BOW, EXTRA_PREFIXES, LEVEL, build, pattern_data

import crafting_system.cli  # noqa: F401 - names the presenter of plans (`planner.present_with`, issue #882)
from crafting_system.abstraction import Abstraction, AtLeast, Goal, Wanted, _pattern
from crafting_system.abstraction._kernel import Abstraction as KernelAbstraction
from crafting_system.abstraction._pattern import Pattern, PatternOffer, Ruin
from crafting_system.actions import Adds, ChaosOrb, FracturingOrb
from crafting_system.planner import PlanSettings, plan_target
from crafting_system.planner._offers import BuyStartItem, Offer, PricedOffer
from crafting_system.planner import _pattern_bound
from crafting_system.planner._pattern_bound import pattern_lower_bound
from crafting_system.prices import PriceEntry, PriceFile
from crafting_system.prices.provenance import EXCHANGE, Provenance
from crafting_system.targets import parse_target

FIRE, SOCKET, FIRE_RES = "LocalAddedFireDamageTwoHand1", "LocalIncreaseSocketedGemLevel1", "FireResist1"
JUNK_PREFIX, NEEDED_PREFIX = EXTRA_PREFIXES[0][0], EXTRA_PREFIXES[2][0]
# the three prefixes and a suffix: a fractured prefix that gives no leaf leaves two prefixes for three leaves
THREE_PREFIXES = Goal((SOCKET_LEAF, Wanted(frozenset({FIRE})), Wanted(frozenset({NEEDED_PREFIX})), SPEED_TIER_1))
MODEL_ACTIONS = ("chaos", "fracture")
RESTART_COST = 10.0
COSTS = {"chaos": 1.0, "fracture": 3.0}


def abstraction(goal: Goal = THREE_PREFIXES, data=None) -> Abstraction:
    return Abstraction(data or pattern_data(), goal, BOW, LEVEL, tuple(ACTIONS[name] for name in MODEL_ACTIONS), metamods=True)


def offers() -> list[PatternOffer]:
    return [PatternOffer("restart", None, RESTART_COST), *(PatternOffer(name, ACTIONS[name], COSTS[name]) for name in MODEL_ACTIONS)]


def key_of(ab: Abstraction, *mods: str, fractured: str, data=None):
    state = ab.compress(build(data or pattern_data(), BOW, (*mods, fractured), fractured=(fractured,)))
    return Pattern(ab, None, [ACTIONS[name] for name in MODEL_ACTIONS]).key(state)


def test_a_fractured_mod_that_takes_a_slot_the_target_needs_ruins_the_key():
    ab = abstraction()
    ruin = Ruin.of(ab, offers())
    assert ruin(key_of(ab, FIRE, SOCKET, AS_5, fractured=JUNK_PREFIX))  # two prefixes left, three prefix leaves
    assert not ruin(key_of(ab, SOCKET, JUNK_PREFIX, AS_5, fractured=FIRE))  # the fractured mod gives its leaf
    assert not ruin(key_of(ab, FIRE, SOCKET, AS_5, fractured=FIRE_RES))  # a junk suffix: two suffixes left for one suffix leaf


def test_a_fractured_mod_below_the_leafs_tier_takes_its_family():
    def ruined(goal: Goal, fractured: str) -> bool:
        ab = Abstraction(BOW_DATA, goal, BOW, LEVEL, (ChaosOrb(), FracturingOrb()))
        state = ab.compress(bow(SOCKET, FIRE, FIRE_RES, fractured, fractured=(fractured,)))
        return Ruin.of(ab, [PatternOffer("restart", None, 1.0)])(Pattern(ab).key(state))

    assert ruined(Goal((SOCKET_LEAF, SPEED_TIER_1)), AS_1)  # the attack speed family is held by a tier the leaf refuses
    assert not ruined(Goal((SOCKET_LEAF, SPEED_TIER_1)), AS_5)  # tier 1: the leaf is met
    assert not ruined(Goal((SOCKET_LEAF, AtLeast(1, (SPEED_TIER_1, ARROW_LEAF)))), AS_1)  # the arrows meet the alternative


def test_the_test_is_off_without_a_restart_or_with_an_offer_that_may_take_a_fractured_mod_off():
    ab = abstraction()
    assert Ruin.of(ab, offers()) is not None
    assert Ruin.of(ab, offers()[1:]) is None

    @dataclasses.dataclass(frozen=True)
    class Brick(ChaosOrb):
        """An offer that declares it may take the fractured mods off (a Vaal Orb's brick at Craft of Exile's reading)."""

        def adds(self, data=None, item=None):
            return Adds.corrupting(erases_fractured=True)

    assert Ruin.of(ab, [*offers(), PatternOffer("brick", Brick(), 1.0)]) is None


def priced():
    ab = abstraction()
    start_item = build(pattern_data(), BOW, (FIRE, SOCKET, AS_5, FIRE_RES))
    restart = PricedOffer(Offer("restart", BuyStartItem(start_item), {}), RESTART_COST, ())
    return [restart, *(PricedOffer(Offer(name, ACTIONS[name], {}), COSTS[name], ()) for name in MODEL_ACTIONS)], ab, ab.compress(start_item)


@contextlib.contextmanager
def ruin_keys(on: bool):
    before = _pattern.RUIN_KEYS
    _pattern.RUIN_KEYS = on
    try:
        yield
    finally:
        _pattern.RUIN_KEYS = before


def bound(on: bool):
    offered, ab, start = priced()
    with ruin_keys(on):
        return pattern_lower_bound(ab, start, offered, tags=True), ab


def test_the_model_with_the_ruined_state_has_the_value_of_the_model_without_it_at_every_key():
    old, _ = bound(False)
    new, ab = bound(True)
    model = new.model
    assert old.model.ruined is None and old.model.stats.ruined_keys == 0
    assert model.ruined is not None and model.stats.ruined_keys > 20
    assert model.actions[model.ruined] == [(0, model.actions[model.ruined][0][1])]  # the restart (offer 0) alone
    assert model.kernels[model.actions[model.ruined][0][1]] == ((0,), (1,))  # to the start key
    assert new.start_value == pytest.approx(old.start_value, rel=1e-12)
    ruined_value = RESTART_COST + new.start_value
    assert new.value[model.ruined] == pytest.approx(ruined_value, rel=1e-12)
    test = Ruin.of(ab, offers())
    for key, k in old.model.index.items():
        j = model.index.get(key)
        if j is None:  # reached only through a ruined key: ruined itself
            assert test(key) and old.value[k] == pytest.approx(ruined_value, rel=1e-12)
            continue
        assert new.value[j] == pytest.approx(old.value[k], rel=1e-12, abs=1e-12)
        assert (j == model.ruined) == test(key)
    assert len(model.keys) < len(old.model.keys) and model.stats.pairs < old.model.stats.pairs


@pytest.mark.parametrize("on", [True, False], ids=["ruin", "control"])
def test_a_ruined_key_is_never_worked_out(monkeypatch, on):
    """With the ruined state no member of a ruined key is made and no kernel asked at one; without it (the control) both are, so the spy
    sees them. The test reads the flags, the fractured mods and the imprints of a key, which a `Pattern` with or without tags reads alike."""
    test = Ruin.of(abstraction(), offers())
    asked: list = []
    members, kernel_key = Pattern.members, KernelAbstraction.kernel_key

    def members_asked(self, key, *args, **kwargs):
        asked.append(key)
        return members(self, key, *args, **kwargs)

    def kernel_key_asked(self, state, action):
        asked.append(Pattern(self).key(state))
        return kernel_key(self, state, action)

    monkeypatch.setattr(Pattern, "members", members_asked)
    monkeypatch.setattr(KernelAbstraction, "kernel_key", kernel_key_asked)
    made, _ = bound(on)
    assert asked and (made.model.stats.ruined_keys > 0) == on
    assert bool([key for key in asked if test(key)]) != on


def test_too_many_choices_of_a_fractured_family_type_call_no_key_ruined(monkeypatch):
    """A fractured attack speed is held as its family type here (a Fracturing Orb is offered): its family is tried for each mod the leaf
    names (`Ruin._type_families`); with no choice allowed none is taken, and the key is not called ruined (weaker, never stronger)."""
    ab = Abstraction(BOW_DATA, Goal((SOCKET_LEAF, SPEED_TIER_1)), BOW, LEVEL, (ChaosOrb(), FracturingOrb()))
    state = ab.compress(bow(SOCKET, FIRE, FIRE_RES, AS_1, fractured=(AS_1,)))
    assert state.fractured[0].mod_id.startswith("~")
    assert Ruin.of(ab, offers()[:1])(Pattern(ab).key(state))
    monkeypatch.setattr(_pattern, "RUIN_CHOICES", 0)
    assert not Ruin.of(ab, offers()[:1])(Pattern(ab).key(state))


TARGET = f"""\
base: Thicket Bow
item_level: {LEVEL}
influence: []
requirements:
  - family: IncreaseSocketedGemLevel
    min_tier: any
  - family: FireDamage
    min_tier: any
  - family: ColdDamage
    min_tier: any
  - family: IncreasedAttackSpeed
start_item:
  rarity: normal
start: bought
"""


@pytest.mark.parametrize("floors", [False, True], ids=["all-offers", "floors"])
def test_the_plan_through_the_planners_entry_is_the_plan_without_the_ruined_state(monkeypatch, floors):
    """`floors`: the bound built on the offers' floors' path (`_pattern_bound.MIN_OFFERS` lowered to these three offers). Here every offer is in
    its first model; a ruined state beside offers left outside the model is met on R04's heavy run (#1367's PR)."""
    if floors:
        monkeypatch.setattr(_pattern_bound, "MIN_OFFERS", 2)
    data = BOW_DATA  # the fixture bow whole (its bench crafts name its mods): the third prefix the target needs is the cold damage
    start_item = bow(FIRE, SOCKET, AS_5, FIRE_RES)  # a rare bow of four mods, none fractured: a Fracturing Orb takes it
    target = dataclasses.replace(parse_target(TARGET, data, source="t.yaml"), start_item=start_item, actions=("chaos-orb", "fracturing-orb"))
    day = "2026-11-20"
    entry = PriceEntry(COSTS["fracture"], "poe.ninja", None, None, Provenance(EXCHANGE, "Test", day, 1e9))
    prices = PriceFile("Test", datetime.datetime(2026, 11, 20, tzinfo=datetime.UTC), 300.0, {"Fracturing Orb": entry})

    def plan(on: bool):
        with ruin_keys(on):
            return plan_target(data, target, prices, PlanSettings(recipe_starts=False, start_price=RESTART_COST, solver="envelope"))

    old, new = plan(False), plan(True)
    assert new.mean_remaining == pytest.approx(old.mean_remaining, rel=1e-9)
    assert new.search.lower == pytest.approx(old.search.lower, rel=1e-9)
    assert new.search.bound_keys < old.search.bound_keys
