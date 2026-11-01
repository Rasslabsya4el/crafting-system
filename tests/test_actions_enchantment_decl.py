"""`Reads` and `Adds` declare the enchantment, and a toy that adds one is offered at no cost to the compressed state (ticket #238, ADR-0027, ADR-0050).

"Done when": the toy action of `test_actions_toy.py` and the contract suite pass unedited (those files are not touched; the
toy runs there as before and `test_the_toys_of_the_other_suites_...` below runs the older toys under the new fields); a toy
that declares `Adds(enchantment=...)` is offered, passes the contract suite, and the compressed state it runs through is the
same size as without it. The enchantment is not part of `item_state`: no declaration of it makes a state hold the enchantment.
"""

import dataclasses
from collections import deque
from fractions import Fraction

import pytest
from contract_support import (
    _check_at,
    check_axes_and_inputs,
    check_block_invariance,
    check_resources_are_priced,
)
from cli_support import price_file
from enchant_support import ARMOUR_EXTRA_SLOT, BODY, DATA, LIFE, SWORD
from items_support import roll as fixture_roll

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    Action,
    ActionError,
    Adds,
    AnnulmentOrb,
    Finite,
    Kind,
    NotApplicableError,
    Reads,
    kinds,
    registered,
)
from crafting_system.actions.contract import model_readings
from crafting_system.cli._offers import offers_for, price_offers
from crafting_system.data import GameData
from crafting_system.items import Item, Rarity
from crafting_system.prices import PriceEntry

TOY_ORB = "Toy Tempering Orb"
LIFE_MOD, RESIST = "IncreasedLife1", "ColdResist1"
GOAL = Goal((Wanted(frozenset({"FireResist1"})),))  # a mod the start item does not hold, so the walk expands it


def body(*, enchantment: str | None = None, rarity: Rarity = Rarity.RARE) -> Item:
    mods = (fixture_roll(LIFE_MOD), fixture_roll(RESIST)) if rarity is Rarity.RARE else ()
    return Item.build(DATA, base_id=BODY, item_level=84, rarity=rarity, mods=mods, enchantment=enchantment)


@dataclasses.dataclass(frozen=True)
class ToyEnchanter(Action):
    """A toy Tempering Orb: it puts `enchant` on a rare item, replacing the one there, and touches nothing else."""

    enchant: str = LIFE

    @property
    def variant(self) -> str:
        return self.enchant

    def label(self, data: GameData | None = None) -> str:
        return "Toy Tempering"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {TOY_ORB: 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset())  # it does not look at the enchantment it replaces

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds(named=frozenset(), draws=False, enchantment=True)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError("the toy works on a rare item only")
        return Finite(data, item, ((Fraction(1), item.changed(data, enchantment=self.enchant)),))


@dataclasses.dataclass(frozen=True)
class Undeclared(ToyEnchanter):
    """An action that declares nothing: it reads and adds everything, like it reads every mod."""

    def reads(self, data):
        return Action.reads(self, data)

    def adds(self, data=None, item=None):
        return Action.adds(self, data, item)


def toy_members(data: GameData, item: Item):
    if item.rarity is Rarity.RARE and item.base_id == BODY:
        yield ToyEnchanter()


@pytest.fixture
def toy_registered():
    with registered(Kind("toy-enchanter", toy_members, order=900)):
        yield


# --- the declarations ------------------------------------------------------------------------------


def test_the_declarations_default_to_leaving_the_enchantment_alone():
    assert Reads().enchantment is False and Adds().enchantment is False
    for builder in (Reads.adding, Reads.nothing):
        assert not builder().enchantment
    assert not Adds.removal().enchantment and not Adds.rerolling().enchantment and not Adds.erasing().enchantment


def test_the_enchantment_is_not_item_state():
    assert not Reads(enchantment=True).item_state and not Adds(enchantment=True).item_state
    assert Reads(enchantment=True, quality=True).item_state and Adds(enchantment=True, offer=True).item_state


def test_an_action_that_declares_nothing_reads_and_adds_the_enchantment_like_everything_else():
    reads, adds = Undeclared().reads(DATA), Undeclared().adds(DATA, None)
    assert (reads.junk, reads.implicits, reads.quality, reads.offer, reads.enchantment) == (True,) * 5
    assert (adds.implicits, adds.quality, adds.offer, adds.enchantment) == (True,) * 4


def test_no_kind_of_the_catalog_declares_the_enchantment_yet():
    # B1 to B4 read and set no enchantment: the planner and the cache see no change in any registered kind
    for item in (body(), body(enchantment=ARMOUR_EXTRA_SLOT), body(rarity=Rarity.NORMAL)):
        for kind in kinds():
            for action in kind.members(DATA, item):
                assert not action.reads(DATA).enchantment and not action.adds(DATA, item).enchantment, kind.name


# --- the toy passes the contract suite -----------------------------------------------------------------


def check_action(action: Action, item: Item, data: GameData = DATA, goal: Goal = GOAL) -> bool:
    """`contract_support.check_action` on an item that can hold an enchantment.

    The fixture world of that function is an amulet, which holds none, so its checks are run here one by one on a body
    armour of the enchantment data: the same checks, unedited. The block-invariance check reads the amulet world and
    runs as it always does (a toy that declares neither flag must be refused by the coarse state).
    """
    readings = model_readings(data, [action])
    applied = False
    for reading in readings:
        applied |= _check_at(action, item, data, goal, reading)
    if applied:
        check_axes_and_inputs(action, item, data, readings)
        check_resources_are_priced(action, item, data)
        check_block_invariance(action)
    return applied


@pytest.mark.parametrize("enchantment", [None, ARMOUR_EXTRA_SLOT, LIFE])
def test_a_toy_that_adds_an_enchantment_passes_the_contract_suite(enchantment):
    assert check_action(ToyEnchanter(), body(enchantment=enchantment), data=DATA, goal=GOAL)
    assert not check_action(ToyEnchanter(), body(rarity=Rarity.NORMAL), data=DATA, goal=GOAL)  # a refusal is checked too


def test_the_toy_really_sets_the_enchantment_and_the_one_that_declares_nothing_passes_too():
    held = body(enchantment=ARMOUR_EXTRA_SLOT)
    ((_, result),) = [(1, part.result) for _, part in ToyEnchanter().outcomes(DATA, held).components]
    assert result.enchantment == LIFE and held.enchantment == ARMOUR_EXTRA_SLOT
    assert check_action(Undeclared(), body(), data=DATA, goal=GOAL)


# --- the state is the same size ---------------------------------------------------------------------------


def reachable(ab: Abstraction, start, actions):
    """The states the solver's graph holds (a goal is not expanded) and the number of transitions."""
    seen, queue, transitions = {start}, deque([start]), 0
    while queue:
        state = queue.popleft()
        if ab.is_goal(state):
            continue
        for action in actions:
            try:
                kernel = ab.kernel(state, action)
            except ActionError:
                continue
            transitions += len(kernel)
            for successor in kernel:
                if successor not in seen:
                    seen.add(successor)
                    queue.append(successor)
    return seen, transitions


@pytest.mark.parametrize("enchantment", [None, ARMOUR_EXTRA_SLOT])
def test_a_toy_that_adds_an_enchantment_does_not_change_the_compressed_state_size(enchantment):
    plain, toy = [AnnulmentOrb()], [AnnulmentOrb(), ToyEnchanter()]
    start_item = body(enchantment=enchantment)

    without = Abstraction(DATA, GOAL, BODY, 84, plain, enchantment=enchantment)
    with_toy = Abstraction(DATA, GOAL, BODY, 84, toy, enchantment=enchantment)
    start = without.compress(start_item)
    assert with_toy.compress(start_item) == start and repr(with_toy.compress(start_item)) == repr(start)
    assert not without.sets_enchantment and with_toy.sets_enchantment
    assert (with_toy.tracks_implicits, with_toy.tracks_quality, with_toy.tracks_offer) == (False, False, False)

    states_without, transitions_without = reachable(without, start, plain)
    states_with, transitions_with = reachable(with_toy, start, toy)
    assert states_with == states_without and len(states_with) > 1
    assert transitions_with == transitions_without + len(states_with)  # one more kernel entry per state: the toy leaves the state where it is
    for state in states_with:
        assert dict(with_toy.kernel(state, ToyEnchanter())) == {state: 1}  # the enchantment is not in the state, so nothing moves


@dataclasses.dataclass(frozen=True)
class UndeclaredButTheEnchantment(Undeclared):
    """The same as `Undeclared`, with only the two enchantment flags taken off."""

    def reads(self, data):
        return dataclasses.replace(Action.reads(self, data), enchantment=False)

    def adds(self, data=None, item=None):
        return dataclasses.replace(Action.adds(self, data, item), enchantment=False)


def test_the_state_does_not_hold_the_enchantment_whether_or_not_an_action_reads_it():
    start_item = body(enchantment=LIFE)

    def state_of(actions):
        ab = Abstraction(DATA, GOAL, BODY, 84, actions, enchantment=LIFE)
        state = ab.compress(start_item)
        assert LIFE not in repr(state) and "nchant" not in repr(state)
        return state

    plain = state_of([AnnulmentOrb()])  # reads the junk as the toy does
    assert state_of([AnnulmentOrb(), ToyEnchanter()]) == plain and repr(state_of([ToyEnchanter()])) == repr(plain)
    # an action that declares nothing makes the state hold the implicits, the quality and the offer (ADR-0027), as before, and nothing more
    assert state_of([Undeclared()]) == state_of([UndeclaredButTheEnchantment()])
    assert repr(state_of([Undeclared()])) == repr(state_of([UndeclaredButTheEnchantment()]))
    assert state_of([AnnulmentOrb(), Undeclared()]) == state_of([AnnulmentOrb(), UndeclaredButTheEnchantment()])


def test_an_item_with_another_enchantment_is_still_refused_unless_an_action_sets_one():
    with pytest.raises(ValueError, match="enchantment"):
        Abstraction(DATA, GOAL, BODY, 84, [AnnulmentOrb()]).compress(body(enchantment=ARMOUR_EXTRA_SLOT))
    with pytest.raises(ValueError, match="enchantment"):
        Abstraction(DATA, GOAL, BODY, 84, [AnnulmentOrb(), Action_reading_only()]).compress(body(enchantment=ARMOUR_EXTRA_SLOT))
    assert Abstraction(DATA, GOAL, BODY, 84, [ToyEnchanter()]).compress(body(enchantment=ARMOUR_EXTRA_SLOT))


def Action_reading_only() -> Action:
    """An action that reads the enchantment and sets none: it does not lift the refusal."""

    @dataclasses.dataclass(frozen=True)
    class Reader(ToyEnchanter):
        def adds(self, data=None, item=None):
            return Adds(named=frozenset(), draws=False)

    return Reader()


# --- the toy is offered ---------------------------------------------------------------------------------------


def test_the_toy_is_offered_with_its_resources_and_priced(toy_registered):
    start = body()
    offers = offers_for(DATA, GOAL, start.base_id, start).offers
    toy = next(offer for offer in offers if offer.label == "Toy Tempering")
    assert toy.action == ToyEnchanter() and dict(toy.resources) == {TOY_ORB: 1}
    priced, dropped = price_offers([toy], dataclasses.replace(price_file(), prices={TOY_ORB: PriceEntry(3.0, "test")}))
    assert not dropped and priced[0].cost == 3.0


def test_the_toy_is_offered_on_an_item_that_holds_an_enchantment_and_not_on_a_weapon(toy_registered):
    held = body(enchantment=ARMOUR_EXTRA_SLOT)
    assert "Toy Tempering" in [offer.label for offer in offers_for(DATA, GOAL, held.base_id, held).offers]
    sword = Item.build(DATA, base_id=SWORD, item_level=84, rarity=Rarity.RARE, mods=())
    assert "Toy Tempering" not in [offer.label for offer in offers_for(DATA, Goal(()), sword.base_id, sword).offers]


def test_the_offers_of_the_catalog_are_the_same_with_the_toy_but_for_the_toy():
    start = body()
    plain = [offer.label for offer in offers_for(DATA, GOAL, start.base_id, start).offers]
    with registered(Kind("toy-enchanter", toy_members, order=900)):
        with_toy = [offer.label for offer in offers_for(DATA, GOAL, start.base_id, start).offers]
    assert sorted(with_toy) == sorted([*plain, "Toy Tempering"])
