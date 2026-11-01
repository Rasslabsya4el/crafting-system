"""The contract answers inputs and rule axes (ticket #210, B3 T1; ADR-0022, ADR-0024 amendment, ADR-0033).

Done when: a toy two-input action defined only in a test (`inputs_support.ToyGraft`) is offered by the CLI, gets exact
kernels per reading and passes `contract_support.check_action`, as ADR-0024's toy action does, without the simulator
(nested runs are #222); input-free actions are unchanged bit for bit.
"""

import dataclasses
from fractions import Fraction

import pytest
from abstraction_pool import DAMAGE_1, LIFE_1, MANA_1
from cli_support import R12, price_file
from contract_support import CONTRACT_DATA, check_action, check_axes_and_inputs, contract_pairs, fixture_items
from inputs_support import COIN, GRAFT_KIND, PICK, TOY_ORB, ToyCoin, ToyGraft, donor_start, donor_want

from crafting_system.abstraction import Abstraction, Goal, Wanted
from crafting_system.actions import (
    Action,
    Axis,
    ChaosOrb,
    Kind,
    Need,
    OutOfScopeError,
    Reading,
    Reads,
    catalog,
    kinds,
    model_readings,
    registered,
)
from crafting_system.cli import PlanError, make_plan
from crafting_system.cli._offers import offers_for, price_offers
from crafting_system.items import Rarity
from crafting_system.prices import PriceEntry
from crafting_system.targets import load_target

GOAL_PAIR = Goal((Wanted(frozenset({DAMAGE_1})), Wanted(frozenset({MANA_1}))))


@pytest.fixture(scope="module")
def items():
    return fixture_items()


@pytest.fixture
def graft_registered():
    with registered(GRAFT_KIND):
        yield


# --- the declarations ------------------------------------------------------------------------------


def test_an_action_that_declares_nothing_has_no_inputs_and_no_axes():
    action = ChaosOrb()
    item = fixture_items()["rare_junk"]
    assert action.inputs(CONTRACT_DATA, item) == () and action.inputs(CONTRACT_DATA) == ()
    assert action.rule_axes(CONTRACT_DATA) == ()
    assert model_readings(CONTRACT_DATA, [action]) == (Reading(),)
    assert action.outcomes_under(CONTRACT_DATA, item, Reading.of({"toy.pick": Fraction(1, 4)})).chance_all([LIFE_1]) == action.outcomes(
        CONTRACT_DATA, item
    ).chance_all([LIFE_1])


def test_reads_say_which_of_the_two_items_mods_are_read():
    assert Reads().input_mods is False and Reads.nothing().input_mods is False and Reads.adding().input_mods is False
    assert Reads(junk=False, input_mods=True).input_mods and not Reads(junk=False, input_mods=True).junk  # the donor's mods only
    assert Reads(junk=True, input_mods=True).junk  # both
    assert Reads(junk=True).input_mods is False  # the item in hand only
    assert ToyGraft().reads(CONTRACT_DATA).input_mods

    class Declares(Action):  # an action that declares nothing reads the inputs' mods too, like every mod of the item
        def label(self, data=None):
            return "Declares nothing"

        def outcomes(self, data, item):
            raise NotImplementedError

        def resources(self, data=None):
            return {}

    assert Declares().reads(CONTRACT_DATA).input_mods


def test_a_need_is_a_start_and_a_want_and_is_hashable():
    need = Need(donor_start(), donor_want())
    assert need.start.rarity is Rarity.MAGIC and need.want.rarity is Rarity.RARE
    assert {need: 1}[Need(donor_start(), donor_want())] == 1


def test_an_axis_needs_two_readings_and_a_plan_among_them():
    with pytest.raises(ValueError):
        Axis("a", (1,), 1)
    with pytest.raises(ValueError):
        Axis("a", (1, 1), 1)
    with pytest.raises(ValueError):
        Axis("a", (1, 2), 3)
    with pytest.raises(ValueError):
        Axis("", (1, 2), 1)


def test_a_reading_is_one_value_per_axis():
    reading = Reading.of({"b": 2, "a": 1})
    assert reading["a"] == 1 and reading.get("b") == 2 and reading.get("c", 9) == 9 and reading
    assert reading == Reading.of({"a": 1, "b": 2}) and hash(reading) == hash(Reading.of({"a": 1, "b": 2}))
    assert not Reading() and Reading() == Reading.of()
    with pytest.raises(KeyError):
        reading["c"]


def test_the_readings_of_a_model_are_the_product_of_its_axes_with_the_plan_first():
    assert model_readings(CONTRACT_DATA, [ToyGraft()]) == tuple(
        Reading.of({PICK.name: value}) for value in (Fraction(1, 2), Fraction(1, 4), Fraction(3, 4))
    )
    both = model_readings(CONTRACT_DATA, [ToyGraft(), ToyCoin(), ChaosOrb()])
    assert len(both) == 6 == len(set(both))  # 3 x 2, the axes of the two actions
    assert both[0] == Reading.of({PICK.name: PICK.plan, COIN.name: COIN.plan})
    assert {reading[PICK.name] for reading in both} == set(PICK.readings) and {reading[COIN.name] for reading in both} == set(COIN.readings)
    assert model_readings(CONTRACT_DATA, [ToyGraft(), ToyGraft(), ToyGraft(with_axis=False)]) == model_readings(CONTRACT_DATA, [ToyGraft()])


def test_two_actions_that_name_one_axis_must_agree_on_its_readings():
    @dataclasses.dataclass(frozen=True)
    class Clash(ToyCoin):
        def rule_axes(self, data):
            return (Axis(PICK.name, (1, 2), 1),)

    with pytest.raises(ValueError, match="toy.pick"):
        model_readings(CONTRACT_DATA, [ToyGraft(), Clash()])


# --- the catalog and the CLI -----------------------------------------------------------------------


def test_the_catalog_and_the_planner_list_the_new_kinds(items, graft_registered):
    rare = items["rare_junk"]
    assert ToyGraft() in catalog(CONTRACT_DATA, rare) and ToyGraft() in catalog(CONTRACT_DATA, rare, planner_only=True)
    assert ToyGraft() not in catalog(CONTRACT_DATA, items["magic"])
    assert "toy-graft" in {entry.name for entry in kinds()}


def test_a_kind_the_planner_cannot_use_yet_stays_in_the_catalog_only(items):
    waiting = Kind("toy-graft", GRAFT_KIND.members, order=901, planner=False, why_not="the solver takes no donors yet (#212)")
    with registered(waiting):
        assert ToyGraft() in catalog(CONTRACT_DATA, items["rare_junk"])
        assert ToyGraft() not in catalog(CONTRACT_DATA, items["rare_junk"], planner_only=True)


def test_nothing_is_left_behind_by_the_registrations(items):
    assert ToyGraft() not in catalog(CONTRACT_DATA, items["rare_junk"]) and ToyCoin() not in catalog(CONTRACT_DATA, items["rare_junk"])


def test_the_cli_offers_the_toy_with_its_inputs_and_axes(items, graft_registered):
    start = items["rare_junk"]
    offers = offers_for(CONTRACT_DATA, GOAL_PAIR, start.base_id, start).offers
    toy = next(offer for offer in offers if offer.label == "Toy Graft")
    assert toy.action == ToyGraft() and dict(toy.resources) == {TOY_ORB: 1}
    assert toy.inputs == (Need(donor_start(), donor_want()),) and toy.axes == (PICK,)
    priced, dropped = price_offers([toy], dataclasses.replace(price_file(), prices={TOY_ORB: PriceEntry(2.5, "test")}))
    assert not dropped and priced[0].cost == 2.5
    chaos = next(offer for offer in offers if offer.label == "Chaos Orb")
    assert chaos.inputs == () and chaos.axes == ()  # an input-free action's offer is what it was


def test_the_planner_does_not_price_a_donor_as_free(items):
    # the graft's kernel is exact, but the donor it consumes costs something the plan would leave out: the planner refuses it
    start = items["rare_junk"]
    ab = Abstraction(CONTRACT_DATA, GOAL_PAIR, start.base_id, start.item_level, [ToyGraft(with_axis=False)], allow_inputs=False)
    with pytest.raises(OutOfScopeError, match="#212"):
        ab.kernel(ab.compress(start), ToyGraft(with_axis=False))
    prices = dataclasses.replace(price_file(), prices={**price_file().prices, TOY_ORB: PriceEntry(0.0001, "test")})
    plan = make_plan(CONTRACT_DATA, load_target(R12, CONTRACT_DATA), prices, offers=_offers_with(ToyGraft(with_axis=False)))
    assert "Toy Graft" in [priced.label for priced in plan.offers]
    assert "Toy Graft" not in [action.label for action in plan.policy.values()]


def test_the_planner_refuses_an_offered_axis_until_the_interval_driver_exists(graft_registered):
    prices = dataclasses.replace(price_file(), prices={**price_file().prices, TOY_ORB: PriceEntry(0.5, "test")})
    with pytest.raises(PlanError, match="toy.pick"):
        make_plan(CONTRACT_DATA, load_target(R12, CONTRACT_DATA), prices)


def _offers_with(action):
    from crafting_system.cli._offers import Offer, offer_of, offers_for as listed

    target = load_target(R12, CONTRACT_DATA)
    base = listed(CONTRACT_DATA, Goal.from_target(target), target.base_id, target.start_item).offers
    return (*base, offer_of(action, action.label(), CONTRACT_DATA, target.start_item))


# --- exact kernels per reading ----------------------------------------------------------------------


def _states(ab, start):
    """The compressed states of the item with the donor's damage mod added, and with its mana mod added."""
    donor = {entry.mod_id: entry for entry in donor_want().mods}
    return tuple(ab.compress(start.changed(CONTRACT_DATA, mods=(*start.mods, donor[mod_id]))) for mod_id in (DAMAGE_1, MANA_1))


def test_the_toy_has_an_exact_kernel_at_every_reading(items):
    start = items["rare_junk"]  # a resistance and a life mod: both of the donor's mods fit
    kernels = {}
    for reading in model_readings(CONTRACT_DATA, [ToyGraft()]):
        ab = Abstraction(CONTRACT_DATA, GOAL_PAIR, start.base_id, start.item_level, [ToyGraft()], reading=reading)
        damage, mana = _states(ab, start)
        assert ab.reading == reading
        kernel = dict(ab.kernel(ab.compress(start), ToyGraft()))
        chance = reading[PICK.name]
        assert kernel == {damage: chance, mana: 1 - chance}
        kernels[chance] = kernel
    assert set(kernels) == {Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)}
    assert all(kernels[a] != kernels[b] for a in kernels for b in kernels if a != b)  # three readings, three kernels


def test_a_pair_without_a_conflict_differs_between_readings_and_one_with_it_does_not(items):
    start = items["rare_fractured"]  # holds the mana leech family: only the damage mod can be added
    kernels = []
    for reading in model_readings(CONTRACT_DATA, [ToyGraft()]):
        ab = Abstraction(CONTRACT_DATA, GOAL_PAIR, start.base_id, start.item_level, [ToyGraft()], reading=reading)
        kernels.append(dict(ab.kernel(ab.compress(start), ToyGraft())))
    assert len(kernels) == 3 and all(kernel == kernels[0] and sum(kernel.values()) == 1 and len(kernel) == 1 for kernel in kernels)


def test_the_plain_outcomes_are_the_plans_reading(items):
    start = items["rare_junk"]
    plain = ToyGraft().outcomes(CONTRACT_DATA, start)
    plan = ToyGraft().outcomes_under(CONTRACT_DATA, start, Reading.of({PICK.name: PICK.plan}))
    assert plain.chance_all([DAMAGE_1]) == plan.chance_all([DAMAGE_1]) == Fraction(1, 2)
    assert ToyGraft().outcomes_under(CONTRACT_DATA, start, Reading.of({PICK.name: Fraction(1, 4)})).chance_all([DAMAGE_1]) == Fraction(1, 4)
    assert ToyGraft().outcomes_under(CONTRACT_DATA, start).chance_all([DAMAGE_1]) == Fraction(1, 2)  # no reading: the plan's
    assert ToyGraft().outcomes_under(CONTRACT_DATA, start, Reading.of({"another.axis": 1})).chance_all([DAMAGE_1]) == Fraction(1, 2)  # an axis it does not read


def test_the_inputs_of_a_state_are_asked_of_the_action_on_its_item(items):
    start = items["rare_junk"]
    ab = Abstraction(CONTRACT_DATA, GOAL_PAIR, start.base_id, start.item_level, [ToyGraft()])
    assert ab.inputs(ab.compress(start), ToyGraft()) == (Need(donor_start(), donor_want()),)
    free = Abstraction(CONTRACT_DATA, GOAL_PAIR, start.base_id, start.item_level, [])
    assert free.inputs(free.compress(start), ChaosOrb()) == ()


# --- the contract suite ------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["rare_junk", "rare_fractured", "rare_crafted", "rare_four"])
def test_the_toy_two_input_action_passes_the_contract_suite(items, name):
    assert check_action(ToyGraft(), items[name])


def test_the_toy_suite_runs_on_every_reading_and_refuses_what_the_game_refuses(items):
    assert not check_action(ToyGraft(), items["magic"])  # a magic item: refused at every reading, and the kernel refuses it the same way
    assert check_action(ToyGraft(with_axis=False), items["rare_junk"])  # inputs without an axis


@pytest.mark.parametrize("name", ["rare_junk", "rare_fractured", "rare_four"])
def test_the_toy_with_an_axis_and_no_input_passes_the_contract_suite(items, name):
    assert check_action(ToyCoin(), items[name])


def test_a_wrong_declaration_is_caught(items):
    start = items["rare_junk"]

    @dataclasses.dataclass(frozen=True)
    class DriftsFromThePlan(ToyGraft):
        def outcomes(self, data, item, reading=None):
            return super().outcomes(data, item, reading if reading is not None else Reading.of({PICK.name: Fraction(1, 4)}))

    with pytest.raises(AssertionError, match="plan"):
        check_action(DriftsFromThePlan(), start)

    @dataclasses.dataclass(frozen=True)
    class BadNeed(ToyGraft):
        def inputs(self, data, item=None):
            return ((donor_start(), donor_want()),)  # not a Need

    with pytest.raises(AssertionError, match="Needs"):
        check_axes_and_inputs(BadNeed(), start, CONTRACT_DATA, model_readings(CONTRACT_DATA, [BadNeed()]))

    counter = iter(range(10**6))

    @dataclasses.dataclass(frozen=True)
    class Unsteady(ToyGraft):
        def inputs(self, data, item=None):
            return (Need(donor_start(), donor_want()),) * (1 + next(counter) % 2)

    with pytest.raises(AssertionError, match="same inputs"):
        check_axes_and_inputs(Unsteady(), start, CONTRACT_DATA, model_readings(CONTRACT_DATA, [Unsteady()]))


def test_input_free_actions_are_unchanged_bit_for_bit():
    """No action of the catalog has an input or an axis, one reading is all there is, and the call with a reading is the call without."""
    for _, action, name in contract_pairs():
        item = fixture_items()[name]
        assert action.inputs(CONTRACT_DATA, item) == () and action.rule_axes(CONTRACT_DATA) == ()
        assert model_readings(CONTRACT_DATA, [action]) == (Reading(),)
        stray = Reading.of({"toy.pick": Fraction(1, 4)})
        try:
            plain = action.outcomes(CONTRACT_DATA, item)
        except Exception as refusal:  # the same refusal through the reading
            with pytest.raises(type(refusal)):
                action.outcomes_under(CONTRACT_DATA, item, stray)
            continue
        through = action.outcomes_under(CONTRACT_DATA, item, stray)
        assert type(through) is type(plain)
        assert through.components is not None and len(through.components) == len(plain.components)
        assert [share for share, _ in through.components] == [share for share, _ in plain.components]
