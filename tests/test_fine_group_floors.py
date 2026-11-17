"""The offers' floors of the fine groups: the implicit changes, the Eldritch Exalted Orb and the Beastcraft side swap (ticket #1074, OR-12, OR-13).

Until #1074 these were TERMINAL offers of the Wald floor `rho` (`planner/_offer_kinds.py`): pbar 1, floor = price. R10 and R11's single search
had rho at a Lesser Eldritch Ember's price (0.2432), R05 and R12's at a Beastcraft side swap's (5.0).

* An implicit change (an Ember, an Ichor) puts no explicit mod on, and E reads the explicit leaves only: pbar 0 once its use at the bare item keeps
  the shape.
* The Eldritch Exalted Orb and the Beastcraft side swap add one drawn mod; the bare item refuses both (no dominant side; nothing to remove), so
  their class declares the draw of the shape (`Action.added_draw`) and the bound of one added mod is read from it (`declared_add_bound`).

The world is the boots of `eldritch_support`: prefixes Life 1000, Armour 500, Evasion 300, Attack 200 and suffixes Fire 1000, Cold 600, Speed 400,
Caster 100, three of each side. By hand, for the Life leaf: one added prefix is Life at most 1000 / (1000 + 200) = 5/6 of the time (Armour and
Evasion held, a third prefix slot open, the Attack family left in the draw); for the Speed leaf at most 400 / (400 + 100) = 4/5. The draw of
either action on a member is one of those scenarios, so the bound of both, for the leaves (Life) and (Life, Speed), is 5/6. The bound is checked
against the exact chance at every member of the shape (every set of mods and every pair of implicits), and the floors against the exact Q* at
every state of the exact graph.
"""

import itertools
from fractions import Fraction

import pytest
from eldritch_support import ARMOUR, ATTACK, BOOTS, CASTER, COLD, DATA, EVASION, FIRE, LEVEL, LIFE, SHAPER, SPEED, boots, eater, exarch, roll
from pattern_support import exact_values
from test_free_action_floors import assert_floors_below_exact_q

from crafting_system.abstraction import Abstraction, Goal, Status, Wanted, declared_add_bound
from crafting_system.abstraction._pattern import PatternOffer
from crafting_system.actions import BeastSideSwap, ChaosOrb, EldritchExaltedOrb, EldritchImplicitCurrency, NotApplicableError
from crafting_system.cli import Offer
from crafting_system.items import EldritchSide, Side
from crafting_system.planner._offer_floor import INSIDE, OUTSIDE, OfferFloors
from crafting_system.planner._offer_kinds import ADD, IMPLICIT, REROLL, SLACK, TERMINAL, _kind_of
from crafting_system.planner._offers import RESTART, BuyStartItem, PricedOffer

EMBER, ICHOR = EldritchImplicitCurrency(EldritchSide.EXARCH, 1), EldritchImplicitCurrency(EldritchSide.EATER, 1)
ELDRITCH_EXALTED, SWAP = EldritchExaltedOrb(), BeastSideSwap(Side.PREFIX)
ACTIONS = {"Ember": (EMBER, 0.1), "Ichor": (ICHOR, 0.1), "Eldritch Exalted Orb": (ELDRITCH_EXALTED, 1.0), "Side swap": (SWAP, 2.0), "Chaos Orb": (ChaosOrb(), 3.0)}
RESTART_PRICE = 1.0
LIFE_LEAF, SPEED_LEAF = Wanted(frozenset({LIFE})), Wanted(frozenset({SPEED}))
START = boots(roll(FIRE))
PREFIXES = ((None, LIFE), (None, ARMOUR), (None, EVASION), (None, ATTACK))
SUFFIXES = ((None, FIRE), (None, COLD), (None, SPEED), (None, CASTER))


def abstraction(*leaves: Wanted, actions=ACTIONS) -> Abstraction:
    return Abstraction(DATA, Goal(leaves), BOOTS, LEVEL, tuple(action for action, _ in actions.values()))


def priced_offers(actions=ACTIONS) -> list[PricedOffer]:
    offers = [PricedOffer(Offer(label, action, {label: 1}), cost, ()) for label, (action, cost) in actions.items()]
    return [*offers, PricedOffer(Offer(RESTART, BuyStartItem(START), {}), RESTART_PRICE, ())]


def pattern_offers(actions=ACTIONS) -> list[PatternOffer]:
    return [PatternOffer(label, action, cost) for label, (action, cost) in actions.items()] + [PatternOffer(RESTART, None, RESTART_PRICE)]


def kinds(floors: OfferFloors) -> dict[str, tuple[str, object]]:
    return {entry.priced.label: (entry.kind, entry.pbar) for entry in floors.entries}


def members():
    """Every rare boots item (no mod fractured) without Life, with every pair of Lesser implicits or none: the members of the start's shape."""
    for combo in itertools.product(*PREFIXES, *SUFFIXES):
        mods = [mod for mod in combo if mod]
        if LIFE in mods or sum(mod in (FIRE, COLD, SPEED, CASTER) for mod in mods) > 3 or len(mods) - sum(mod in (FIRE, COLD, SPEED, CASTER) for mod in mods) > 3:
            continue
        for implicits in ((), (exarch(1),), (eater(1),), (exarch(2), eater(1)), (exarch(1), eater(2))):
            yield boots(*(roll(mod) for mod in mods), implicits=implicits)


def test_the_kinds_of_the_fine_groups():
    offers = {offer.label: offer for offer in priced_offers()}

    assert _kind_of(DATA, START, offers["Ember"])[0] == IMPLICIT
    assert _kind_of(DATA, START, offers["Ichor"])[0] == IMPLICIT
    assert _kind_of(DATA, START, offers["Eldritch Exalted Orb"])[0] == ADD  # it reads the implicits, but its class declares its draw
    assert _kind_of(DATA, START, offers["Side swap"])[0] == ADD  # it reads the beast level's pool, but its class declares its draw
    assert _kind_of(DATA, START, offers["Chaos Orb"])[0] == REROLL


@pytest.mark.parametrize("action", [ELDRITCH_EXALTED, SWAP], ids=["eldritch exalted", "side swap"])
def test_the_declared_bound_is_never_below_the_exact_chance_at_any_member_and_is_reached(action):
    ab = abstraction(LIFE_LEAF, SPEED_LEAF)
    bound = declared_add_bound(ab, action, START, (0,))
    chances = []
    for item in members():
        try:
            kernel = ab.kernel(ab.compress(item), action)
        except NotApplicableError:
            continue  # no dominant side, a full side, nothing to remove: no chance at all
        chances.append(sum((chance for state, chance in kernel.items() if state.status[0] is Status.PASSING), Fraction(0)))

    assert bound == Fraction(5, 6)  # by hand (module text)
    assert declared_add_bound(ab, action, START, (0, 1)) == Fraction(5, 6)
    assert len(chances) > 50
    assert max(chances) == bound  # every chance is at most the bound, and a member reaches it


def test_the_floors_by_hand_and_rho_is_no_longer_an_embers_price():
    """U is Life and Speed (both open on the Fire boots). The Ember and the Ichor are implicit changes at pbar 0 (they no longer set rho at 0.1);
    the Eldritch Exalted Orb is an addition at 5/6 (ratio 1.2), the side swap at 5/6 (2.4); the Chaos Orb a reroll at 3 / its chance of both."""
    ab = abstraction(LIFE_LEAF, SPEED_LEAF)
    floors = OfferFloors(ab, ab.compress(START), priced_offers(), START)
    for entry in floors.entries:
        floors._raise(entry, 2) if entry.kind == REROLL else floors._raise(entry, 1) if entry.kind in (ADD, IMPLICIT) else None
    found = kinds(floors)

    assert floors.chosen == (0, 1)
    assert found["Ember"] == (IMPLICIT, 0) and found["Ichor"] == (IMPLICIT, 0)
    assert found["Eldritch Exalted Orb"] == (ADD, Fraction(5, 6))
    assert found["Side swap"] == (ADD, Fraction(5, 6))
    chaos = found["Chaos Orb"][1]
    assert floors.rho == pytest.approx(min(1.0 / (5 / 6), 3.0 / float(chaos)) * (1 - SLACK), rel=1e-12)
    assert floors.rho > 1.0


def test_an_implicit_change_that_the_bare_item_refuses_stays_terminal():
    shaper = boots(roll(FIRE), influences=SHAPER)  # influenced: no Eldritch currency
    ab = abstraction(LIFE_LEAF)
    floors = OfferFloors(ab, ab.compress(shaper), priced_offers(), shaper)
    floors._raise(next(entry for entry in floors.entries if entry.priced.label == "Ember"), 1)

    assert kinds(floors)["Ember"] == (TERMINAL, 1)


@pytest.mark.parametrize("leaves", [(LIFE_LEAF,), (LIFE_LEAF, SPEED_LEAF)], ids=["life", "life and speed"])
def test_the_fine_groups_floors_are_below_the_exact_q_at_every_state(leaves):
    actions = {label: offer for label, offer in ACTIONS.items() if label != "Chaos Orb"}  # the exact graph stays small without the reroll
    seen = assert_floors_below_exact_q(abstraction(*leaves, actions=actions), START, priced_offers(actions), pattern_offers(actions))

    assert {INSIDE, OUTSIDE} <= seen


@pytest.mark.parametrize("action", [ELDRITCH_EXALTED, SWAP], ids=["eldritch exalted", "side swap"])
def test_the_declared_draw_is_what_the_action_does_at_every_member(action):
    """The contract of `Action.added_draw`, at every member of the boots shape (the contract suite's fixtures hold no item an Eldritch Exalted
    Orb takes): the flags and the fractured mods kept, one mod added, drawn by the declared weights on one side with room."""
    from contract_support import check_added_draw, finished

    checked = 0
    for item in members():
        try:
            outcomes = action.outcomes(DATA, item)
        except NotApplicableError:
            continue
        check_added_draw(action, item, finished(outcomes, DATA), DATA)
        checked += 1
    assert checked > 50
