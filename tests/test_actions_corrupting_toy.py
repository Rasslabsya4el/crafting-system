"""Corrupting actions in the contract and the offer filter (ticket #258, ADR-0036): a toy corrupting action defined only here.

The toy corrupts a rare item. With chance 1/2 the item keeps its mods and gains a corrupted implicit (the outcome that can be the goal of
a target that asks for one); with chance 1/2 it keeps its fractured mods and loses the rest (the brick, a dead end for that target). It
subclasses `Action`, lists its results with `Finite` and registers its kind for the length of a test, as `test_actions_toy.py` does.

"Done when" of the ticket: the toy passes the contract suite; the offer filter keeps it for a target that asks for a corrupted implicit or
allows a corrupted item, and not for one that does neither; and the pruning of its offers to the states where every other requirement
passes never changes a value (solved with and without it).
"""

import dataclasses
from fractions import Fraction

import pytest
from abstraction_pool import LIFE_1, RESIST_2, RESISTS
from contract_support import CONTRACT_DATA, _roll, check_action, fixture_items
from targets_corrupted_support import DATA as TARGET_DATA
from targets_corrupted_support import parse

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    Action,
    Adds,
    ChaosOrb,
    Finite,
    Kind,
    NotApplicableError,
    Reads,
    catalog,
    registered,
)
from crafting_system.cli import PricedOffer
from crafting_system.cli._offers import RESTART, BuyStartItem, Offer, offer_of, offers_for
from crafting_system.cli._plan import _Model
from crafting_system.cli._prune import corrupting_offer_pruned, solver_actions
from crafting_system.data import GameData, Weight
from crafting_system.items import ImplicitMod, Item, Rarity
from crafting_system.solver import solve

TOY_ORB = "Toy Corruption Orb"
TOY_IMPLICIT = "ContractToyCorruptedImplicit"
KIND = "toy-corruption"


def _toy_data() -> GameData:
    """The fixture data of the contract suite with one corrupted implicit the amulet can get."""
    template = CONTRACT_DATA.mods[LIFE_1]
    mod = dataclasses.replace(
        template,
        id=TOY_IMPLICIT,
        name=TOY_IMPLICIT,
        type=TOY_IMPLICIT,
        families=(TOY_IMPLICIT,),
        generation_type="corrupted",
        domain="item",
        required_level=1,
        spawn_weights=(Weight("amulet", 1000), Weight("default", 0)),
        implicit_tags=(),
    )
    return dataclasses.replace(CONTRACT_DATA, mods={**CONTRACT_DATA.mods, TOY_IMPLICIT: mod})


TOY_DATA = _toy_data()


@dataclasses.dataclass(frozen=True)
class ToyCorruption(Action):
    """Corrupts a rare item: half the time it gains `implicit_id` and keeps its mods, half the time only the fractured mods are left."""

    implicit_id: str = TOY_IMPLICIT
    keeps: bool = True  # False: declares that the explicit mods are rerolled (a Bloodstained resonator), only the declaration is exercised

    def label(self, data: GameData | None = None) -> str:
        return "Toy Corruption"

    def resources(self, data: GameData | None = None) -> dict[str, int]:
        return {TOY_ORB: 1}

    def reads(self, data: GameData) -> Reads:
        return Reads(junk=True, families=frozenset())  # which mods the item holds decides what is kept; the implicits are not looked at

    def adds(self, data: GameData | None = None, item: Item | None = None) -> Adds:
        return Adds.corrupting(keeps_mods=self.keeps, draws=False)

    def outcomes(self, data: GameData, item: Item) -> Finite:
        if item.corrupted:
            raise NotApplicableError("a corrupted item takes no further action")
        if item.rarity is not Rarity.RARE:
            raise NotApplicableError("the toy corrupts a rare item only")
        mod = data.mods[self.implicit_id]
        gained = ImplicitMod(self.implicit_id, 0, tuple(stat.min for stat in mod.stats))
        kept = item.changed(data, corrupted=True, implicits=(*item.implicits, gained))
        brick = item.changed(data, corrupted=True, mods=tuple(entry for entry in item.mods if entry.fractured))
        half = Fraction(1, 2)
        return Finite(data, item, ((half, kept), (half, brick)))


def toy_members(data: GameData, item: Item):
    yield ToyCorruption(TOY_IMPLICIT if TOY_IMPLICIT in data.mods else "ResistCorrupted")


@pytest.fixture
def toy_registered():
    with registered(Kind(KIND, toy_members, order=901, corrupting=True)):
        yield


@pytest.fixture(scope="module")
def items():
    return fixture_items()


# --- the contract ----------------------------------------------------------------------------------------


def test_a_corrupting_declaration_needs_an_implicit_and_keeps_mods_needs_corrupting():
    assert Adds.corrupting().corrupts and Adds.corrupting().implicits and not Adds.corrupting().keeps_mods
    assert Adds().corrupts is False and Action.adds(ToyCorruption()).corrupts is False  # the default says it leaves the corruption alone
    with pytest.raises(ValueError, match="implicits"):
        Adds(corrupts=True)
    with pytest.raises(ValueError, match="corrupts"):
        Adds(keeps_mods=True)
    assert Adds.corrupting(keeps_mods=True).item_state  # it changes the implicits, so the state keeps them


@pytest.mark.parametrize("name", ["rare_junk", "rare_fractured", "rare_four", "rare_shaper", "rare_crafted", "rare_resists"])
def test_the_toy_passes_the_contract_suite(items, toy_registered, name):
    assert check_action(ToyCorruption(), items[name], TOY_DATA)


@pytest.mark.parametrize("name", ["normal", "magic"])
def test_the_toy_is_refused_where_the_game_refuses_it_and_the_kernel_agrees(items, toy_registered, name):
    assert not check_action(ToyCorruption(), items[name], TOY_DATA)  # the refusal is checked against the kernel's inside


def test_a_corrupted_item_is_final_for_every_action_of_the_catalog(items, toy_registered):
    start = items["rare_junk"]
    for _, result in ToyCorruption().outcomes(TOY_DATA, start).results:
        assert result.corrupted
        for action in catalog(TOY_DATA, result):
            with pytest.raises(NotApplicableError):
                action.outcomes(TOY_DATA, result)


def test_the_contract_suite_catches_an_action_that_corrupts_without_saying_so(items):
    @dataclasses.dataclass(frozen=True)
    class Liar(ToyCorruption):
        def adds(self, data=None, item=None):
            return Adds(implicits=True, draws=False)

    with pytest.raises(AssertionError, match="adds.corrupts"):
        check_action(Liar(), items["rare_junk"], TOY_DATA)


def test_the_contract_suite_catches_a_corrupting_action_that_leaves_a_result_uncorrupted(items):
    @dataclasses.dataclass(frozen=True)
    class Half(ToyCorruption):
        def outcomes(self, data, item):
            corrupted, plain = super().outcomes(data, item).results[0][1], item
            return Finite(data, item, ((Fraction(1, 2), corrupted), (Fraction(1, 2), plain)))

    with pytest.raises(AssertionError, match="corrupted item"):
        check_action(Half(), items["rare_junk"], TOY_DATA)


def test_the_contract_suite_catches_keeps_mods_on_an_action_that_reaches_the_goal_by_other_mods(items):
    """A brick that adds the mod the item lacks: from a state that misses a requirement it can be the goal, so it must not be pruned."""

    @dataclasses.dataclass(frozen=True)
    class Lucky(ToyCorruption):
        def outcomes(self, data, item):
            kept = super().outcomes(data, item).results[0][1]
            lucky = kept.add_mod(data, _roll(RESIST_2))
            return Finite(data, item, ((Fraction(1, 2), kept), (Fraction(1, 2), lucky)))

    goal = Goal((Wanted(frozenset({RESIST_2})),))
    with pytest.raises(AssertionError, match="misses a requirement"):
        check_action(Lucky(), items["rare_four"].changed(TOY_DATA, mods=()), TOY_DATA, goal)


# --- the goal ---------------------------------------------------------------------------------------------


def test_a_corrupted_state_is_a_goal_only_where_the_target_takes_corruption():
    start = fixture_items()["rare_junk"].changed(TOY_DATA, mods=(_mod(RESIST_2),))
    corrupted = start.changed(TOY_DATA, corrupted=True)
    wanted = (Wanted(RESISTS),)
    plain, allowing, asking = Goal(wanted), Goal(wanted, allow_corrupted=True), Goal(wanted, asks_corrupted=True)
    states = {}
    for name, goal in (("plain", plain), ("allowing", allowing), ("asking", asking)):
        ab = Abstraction(TOY_DATA, goal, start.base_id, start.item_level, [ToyCorruption()])
        states[name] = (ab.is_goal(ab.compress(start)), ab.is_goal(ab.compress(corrupted)))
    assert states == {
        "plain": (True, False),  # a corrupted item meets no target that does not take it
        "allowing": (True, True),  # allowed, not asked: either will do
        "asking": (False, True),  # the goal is a corrupted item
    }
    assert plain.takes_corrupted is False and allowing.takes_corrupted and asking.takes_corrupted


def _mod(mod_id: str):
    return _roll(mod_id)


def test_a_goal_reads_what_the_target_says_about_corruption():
    asking = Goal.from_target(parse("implicits:\n  - stat: '+#% to all Elemental Resistances'\n    corrupted: true\n"))
    allowing = Goal.from_target(parse("allow_corrupted: true\n"))
    neither = Goal.from_target(parse(""))
    assert (asking.asks_corrupted, asking.allow_corrupted) == (True, False)
    assert (allowing.asks_corrupted, allowing.allow_corrupted) == (False, True)
    assert (neither.asks_corrupted, neither.allow_corrupted, neither.takes_corrupted) == (False, False, False)


# --- the offer filter -------------------------------------------------------------------------------------


def _offered(text: str, names=None) -> list[str]:
    target = parse(text)
    offers = offers_for(TARGET_DATA, Goal.from_target(target), target.base_id, target.start_item, names)
    return [offer.label for offer in offers.offers]


def test_the_cli_offers_the_toy_for_a_target_with_corrupted_true_and_not_for_one_without(toy_registered):
    asking = "implicits:\n  - stat: '+#% to all Elemental Resistances'\n    corrupted: true\n"
    assert "Toy Corruption" in _offered(asking)
    assert "Toy Corruption" in _offered("allow_corrupted: true\n")
    assert "Toy Corruption" not in _offered("")
    assert "Chaos Orb" in _offered("")  # the other offers are as before


def test_the_report_says_nothing_of_a_corrupting_kind_for_a_target_that_takes_no_corrupted_item(toy_registered):
    def left_out(text: str) -> tuple[str, ...]:
        target = parse(text)
        chosen = offers_for(TARGET_DATA, Goal.from_target(target), target.base_id, target.start_item, target.actions)
        return tuple(name for entry in chosen.left_out for name in entry.labels)

    assert KIND not in left_out("actions: [chaos-orb]\n")  # nothing of it could be used, so the "does not name these kinds" line leaves it out
    assert KIND in left_out("actions: [chaos-orb]\nallow_corrupted: true\n")  # a target that could use it is told it was not named
    assert "harvest-reforge" in left_out("actions: [chaos-orb]\n")  # the other kinds are listed as before


def test_a_target_that_names_the_toy_kind_gets_it_only_when_it_takes_a_corrupted_item(toy_registered):
    assert "Toy Corruption" not in _offered("actions: [toy-corruption]\n")
    assert "Toy Corruption" in _offered("actions: [toy-corruption]\nallow_corrupted: true\n")


def test_the_toy_offer_declares_what_the_planner_needs(toy_registered):
    start = fixture_items()["rare_junk"]
    goal = Goal((Wanted(RESISTS),), asks_corrupted=True)
    offered = offers_for(TOY_DATA, goal, start.base_id, start).offers
    toy = next(offer for offer in offered if offer.label == "Toy Corruption")
    assert dict(toy.resources) == {TOY_ORB: 1} and toy.action.adds(TOY_DATA).corrupts


# --- the pruning of the offers ----------------------------------------------------------------------------


COST, RESTART_COST = 5.0, 3.0


def _priced(action: Action, cost: float, start: Item) -> PricedOffer:
    return PricedOffer(offer_of(action, action.label(TOY_DATA), TOY_DATA, start), cost, ())


def _restart(start: Item) -> PricedOffer:
    return PricedOffer(Offer(RESTART, BuyStartItem(start), {"start": 1}, shares=False), RESTART_COST, ())


def _model(goal: Goal, start_item: Item, *priced: PricedOffer):
    enabled = [p.offer.action for p in priced if (reads := p.offer.action.reads(TOY_DATA)).junk or reads.item_state]
    ab = Abstraction(TOY_DATA, goal, start_item.base_id, start_item.item_level, enabled)
    start = ab.compress(start_item)
    return ab, start, _Model(ab, start, priced)


def test_a_corrupting_offer_is_an_action_of_a_state_that_asks_only_where_every_other_requirement_passes():
    start_item = fixture_items()["rare_junk"].changed(TOY_DATA, mods=(_mod(LIFE_1),))  # no resistance
    toy, restart = _priced(ToyCorruption(), COST, start_item), _restart(start_item)
    passing = start_item.changed(TOY_DATA, mods=(_mod(LIFE_1), _mod(RESIST_2)))
    for goal, pruned_when_failing in (
        (Goal((Wanted(RESISTS),), asks_corrupted=True), True),  # asks: offered from the passing state only
        (Goal((Wanted(RESISTS),), allow_corrupted=True), False),  # allows: the brick may end in the goal, so offered everywhere
        (Goal((Wanted(RESISTS),)), False),  # takes none: the offer filter keeps the action out; the states are not pruned here
    ):
        ab, failing, _ = _model(goal, start_item, toy, restart)
        assert corrupting_offer_pruned(ab, toy, failing) is pruned_when_failing
        assert corrupting_offer_pruned(ab, toy, ab.compress(passing)) is False
        assert corrupting_offer_pruned(ab, restart, failing) is False  # restart is never pruned


def test_the_pruned_toy_value_is_the_hand_oracle_and_the_pruning_changes_nothing(monkeypatch):
    """Start item that already meets the explicit requirement: one use is the goal with chance 1/2, else a restart: V = 2c + R."""
    from crafting_system.cli import _plan

    start_item = fixture_items()["rare_junk"].changed(TOY_DATA, mods=(_mod(RESIST_2),))
    toy, restart = _priced(ToyCorruption(), COST, start_item), _restart(start_item)
    goal = Goal((Wanted(RESISTS),), asks_corrupted=True)
    values = {}
    for pruning in (True, False):
        monkeypatch.setattr(_plan, "PRUNE_CORRUPTING", pruning)
        ab, start, model = _model(goal, start_item, toy, restart)
        values[pruning] = solve(model, [start]).values[start]
    assert values[True] == values[False] == 2 * COST + RESTART_COST


@pytest.mark.parametrize("cost", [COST, 0.01], ids=["priced", "nearly-free"])  # the solver takes no cost of 0, so the cheapest use is a cent
@pytest.mark.parametrize("with_restart", [True, False], ids=["restart", "no-restart"])
def test_pruning_the_toy_to_the_states_that_pass_never_changes_the_value_on_a_fixture(monkeypatch, cost, with_restart):
    """A Chaos Orb rerolls until a resistance shows, the toy corrupts it: solved whole and pruned, every shared state has one value."""
    from crafting_system.cli import _plan

    start_item = fixture_items()["rare_junk"].changed(TOY_DATA, mods=(_mod(LIFE_1),))
    chaos = _priced(ChaosOrb(), 1.0, start_item)
    toy = _priced(ToyCorruption(), cost, start_item)
    offers = (chaos, toy, *([_restart(start_item)] if with_restart else []))
    goal = Goal((Wanted(RESISTS),), asks_corrupted=True)
    solved, offered = {}, {}
    for pruning in (True, False):
        monkeypatch.setattr(_plan, "PRUNE_CORRUPTING", pruning)
        ab, start, model = _model(goal, start_item, *offers)
        solved[pruning] = solve(model, [start])
        offered[pruning] = {state: {a.label for a in model.actions(state)} for state in solved[pruning].values}
    pruned, whole = solved[True], solved[False]
    assert pruned.values[start] == whole.values[start]
    if with_restart:
        assert 0 <= pruned.values[start] < float("inf")  # a dead end is a restart away, so the corrupting route is finite
    assert all(whole.values[state] == value for state, value in pruned.values.items() if state in whole.values)
    # it is a real test: the toy is an action of some states in the whole model and of fewer in the pruned one
    toy_states = lambda found: {state for state, labels in found.items() if "Toy Corruption" in labels}  # noqa: E731
    assert toy_states(offered[True]) < toy_states(offered[False])
    ab_ = Abstraction(TOY_DATA, goal, start_item.base_id, start_item.item_level, [ToyCorruption()])
    assert all(ab_.meets_requirements(state) for state in toy_states(offered[True]) if not state.flags.corrupted)


def test_a_corrupting_offer_is_terminal_for_the_bound_pruning():
    from crafting_system.cli._bound_prune import TERMINAL, _kind_of

    start_item = fixture_items()["rare_junk"]
    assert _kind_of(TOY_DATA, start_item, _priced(ToyCorruption(), COST, start_item))[0] == TERMINAL


def test_a_corrupting_action_never_keeps_the_shape_the_bound_pruning_holds_fixed():
    """`raise_level` makes an offer terminal when `keeps_shape` is False: a corrupting action moves the flags, so it always is."""
    from crafting_system.abstraction import keeps_shape

    start_item = fixture_items()["rare_junk"]
    ab, start, _ = _model(Goal((Wanted(RESISTS),), asks_corrupted=True), start_item, _priced(ToyCorruption(), COST, start_item))
    assert keeps_shape(ab, start, ToyCorruption()) is False


def test_a_corrupting_action_that_rerolls_the_mods_is_never_pruned_from_a_state_that_misses_a_requirement():
    start_item = fixture_items()["rare_junk"].changed(TOY_DATA, mods=(_mod(LIFE_1),))  # no resistance
    keeping, rerolling = _priced(ToyCorruption(), COST, start_item), _priced(ToyCorruption(keeps=False), COST, start_item)
    ab, failing, _ = _model(Goal((Wanted(RESISTS),), asks_corrupted=True), start_item, keeping, rerolling)
    assert corrupting_offer_pruned(ab, keeping, failing) is True
    assert corrupting_offer_pruned(ab, rerolling, failing) is False  # its outcomes may meet the requirement the state misses


def test_a_kind_marked_corrupting_lists_only_actions_that_corrupt(items, toy_registered):
    from crafting_system.actions import kinds

    seen = 0
    for entry in kinds():
        for item in items.values():
            members = list(entry.members(TOY_DATA, item))
            if members:
                seen += 1
                assert entry.corrupting == all(m.adds(TOY_DATA, item).corrupts for m in members), entry.name
    assert seen


def test_solver_actions_leaves_the_toy_in_when_pruning_is_off():
    start_item = fixture_items()["rare_junk"].changed(TOY_DATA, mods=(_mod(LIFE_1),))
    toy = _priced(ToyCorruption(), COST, start_item)
    ab, start, _ = _model(Goal((Wanted(RESISTS),), asks_corrupted=True), start_item, toy)
    assert [a.label for a in solver_actions(ab, [toy], start, start)] == []
    assert [a.label for a in solver_actions(ab, [toy], start, start, prune_corrupting=False)] == ["Toy Corruption"]


# --- through the planner ---------------------------------------------------------------------------------


def test_the_planner_offers_the_toy_to_a_target_that_allows_corruption_and_not_to_one_that_does_not(tmp_path, toy_registered):
    """`make_plan` on R12 with the toy registered: the offer filter is the one the planner calls (a target that asks is refused until #152/#158)."""
    from cli_support import R12, price_file
    from targets_support import DATA

    from crafting_system.cli import make_plan
    from crafting_system.prices import PriceEntry
    from crafting_system.targets import load_target

    data = dataclasses.replace(DATA, mods={**DATA.mods, TOY_IMPLICIT: TOY_DATA.mods[TOY_IMPLICIT]})
    prices = dataclasses.replace(price_file(), prices={**price_file().prices, TOY_ORB: PriceEntry(5.0, "test")})
    allowing = tmp_path / "allowing.yaml"
    allowing.write_text(R12.read_text(encoding="utf-8") + "\nallow_corrupted: true\n", encoding="utf-8")
    labels = {
        name: [priced.label for priced in make_plan(data, load_target(path, data), prices).offers]
        for name, path in (("allowing", allowing), ("plain", R12))
    }
    assert "Toy Corruption" in labels["allowing"] and "Toy Corruption" not in labels["plain"]
    assert "Chaos Orb" in labels["plain"]
