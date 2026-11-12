"""The socket finish of ADR-0045 and ADR-0058 (ticket #231, B6 S5): its kernels, its value and its policy, on the toy data of `finish_support`.

Layer 1 (ADR-0019): the finish kernel of every action on every reduced state equals the action itself run on every concrete socket assignment of up to
four sockets, its results reduced the same way. Layer 2: a simulation of the finish policy on concrete items, drawing every use from the action itself,
has a mean within five standard errors of the solved value. Layer 3: the value equals the dense policy iteration of `test_socket_finish_reference.py`,
which keeps every state and lists every Chromatic outcome. The numbers of the ticket and the ADRs (214.9 Jeweller's Orbs, 1,000 Orbs of Fusing for six
links, 44.60 for the fixture, the state counts of ADR-0058) are checked as written there.
"""

import itertools
import math
import time
from fractions import Fraction

import numpy as np
import pytest
from finish_support import all_steps, finish_data
from items_support import BODY
from sockets_colour_support import colour_data
from sockets_support import HELMET
from test_socket_finish_reference import solve as dense_solve

from crafting_system.abstraction import FinishModel, FinishStep, SocketWanted, solve_finish
from crafting_system.abstraction._finish import state_of
from crafting_system.actions.errors import NotApplicableError
from crafting_system.actions.quality_currency import ApplyQualityCurrency, expected_quality_currency
from crafting_system.actions.socket_colours import BenchSocketColours, ChromaticOrb
from crafting_system.actions.socket_orbs import JewellersOrb, OrbOfFusing
from crafting_system.items import Item, PlainQuality, Rarity, SocketColour, Sockets

W, R, G, B = SocketColour.WHITE, SocketColour.RED, SocketColour.GREEN, SocketColour.BLUE


def item_of(sockets: Sockets, base_id: str = BODY, quality: int = 20, item_level: int = 84) -> Item:
    return Item.build(
        finish_data(), base_id=base_id, item_level=item_level, rarity=Rarity.RARE, mods=(), sockets=sockets, quality=PlainQuality(quality) if quality else None
    )


def assignments(count: int):
    """Every socket assignment of `count` sockets: each colour per socket and every split of the sockets into consecutive link groups."""
    splits = []
    for cuts in itertools.product((False, True), repeat=count - 1):
        sizes, size = [], 1
        for cut in cuts:
            if cut:
                sizes.append(size)
                size = 1
            else:
                size += 1
        sizes.append(size)
        splits.append(tuple(sizes))
    for colours in itertools.product((W, R, G, B), repeat=count):
        for links in splits:
            yield Sockets(colours, links)


# --- layer 1: the kernels against the actions on every concrete assignment ----------------------------------------------------------------


WANTS = {
    "a group of three with red, green and blue": SocketWanted(count=4, links=3, red=1, green=1, blue=1),
    "two red anywhere": SocketWanted(red=2),
}
_concrete: dict = {}


def concrete(step: FinishStep, sockets: Sockets, base_id: str):
    """The action run on the item with `sockets`: the chance of each `Sockets` it ends with, or None when the game refuses it (cached)."""
    key = (step.label, sockets, base_id)
    if key not in _concrete:
        try:
            _concrete[key] = dict(step.action.outcomes(finish_data(), item_of(sockets, base_id)).by_sockets)
        except NotApplicableError:
            _concrete[key] = None
    return _concrete[key]


@pytest.mark.parametrize("count", [1, 2, 3, 4])
@pytest.mark.parametrize("want", list(WANTS))
@pytest.mark.parametrize("base_id", [BODY, HELMET], ids=["body armour", "helmet"])
def test_every_finish_kernel_equals_the_action_on_every_assignment(base_id, want, count):
    """Every action on the body armour (class maximum 6); on the helmet (4) the count and link actions, whose kernels read the class maximum. The
    colour actions read no class (their roll is the base's requirements, item level and quality), and running them on four sockets takes about a
    minute per base, so they run on the body armour only."""
    data = finish_data()
    steps = all_steps(data)
    model = FinishModel(data, base_id, 84, WANTS[want], steps, quality=20)
    checked = 0
    for sockets in assignments(count):
        state = model.reduce(state_of(sockets))
        for step in model.steps:
            if base_id == HELMET and isinstance(step.action, (ChromaticOrb, BenchSocketColours)):
                continue
            found = model.kernel(state, step)
            outcomes = concrete(step, sockets, base_id)
            if outcomes is None:
                assert found is None, (step.label, sockets)
                continue
            reduced: dict = {}
            for result, chance in outcomes.items():
                key = model.reduce(state_of(result))
                reduced[key] = reduced.get(key, Fraction(0)) + chance
            if found is None:  # the reduced state refuses it, or it only costs there: the concrete item may only stay where it is
                assert reduced == {state: Fraction(1)}, (step.label, sockets)
            else:
                assert found == reduced, (step.label, sockets)
            checked += 1
    assert checked > 0


@pytest.mark.parametrize("count", [1, 2, 3])
def test_the_colour_kernels_equal_the_actions_on_a_base_of_two_attributes(count):
    """The colour actions on the dexterity-intelligence helmet of `colour_data` (red the missing colour, ADR-0047's two-attribute weights), every
    assignment of up to three sockets, a target of one red socket in a group of two (the forced colour matters)."""
    data = colour_data()
    steps = [FinishStep("Chromatic Orb", ChromaticOrb(), 1.0), FinishStep("Chromatic Orb with Omen of Trichromatism", ChromaticOrb(omen=True), 2.0)]
    model = FinishModel(data, HELMET, 84, SocketWanted(links=2, red=1), steps, quality=10)
    for sockets in assignments(count):
        item = Item.build(data, base_id=HELMET, item_level=84, rarity=Rarity.RARE, mods=(), sockets=sockets, quality=PlainQuality(10))
        state = model.reduce(state_of(sockets))
        for step in model.steps:
            try:
                outcomes = step.action.outcomes(data, item).by_sockets
            except NotApplicableError:
                assert model.kernel(state, step) is None
                continue
            reduced: dict = {}
            for result, chance in outcomes.items():
                key = model.reduce(state_of(result))
                reduced[key] = reduced.get(key, Fraction(0)) + chance
            assert model.kernel(state, step) == reduced, (step.label, sockets)


def test_a_group_shorter_than_the_target_s_group_is_forgotten():
    model = FinishModel(finish_data(), BODY, 84, SocketWanted(links=3), all_steps(finish_data()))
    assert model.reduce(((1, 2, 3, 0), (2, 2))) == ((1, 2, 3, 0), (1, 1, 1, 1))
    assert model.reduce(((1, 2, 3, 0), (3, 1))) == ((1, 2, 3, 0), (3, 1))
    assert model.reduce(((1, 2, 3, 0, 0), (2, 3))) == ((1, 2, 3, 0, 0), (1, 1, 3))


# --- layer 3: the value against the dense policy iteration ---------------------------------------------------------------------------------

DENSE_CASES = [(3, (1, 1, 1)), (2, (1, 1, 0)), (4, (2, 1, 0)), (3, (0, 0, 0)), (4, (1, 1, 1))]


@pytest.mark.parametrize(("links", "needs"), DENSE_CASES, ids=[f"{links} linked, {needs}" for links, needs in DENSE_CASES])
def test_the_value_equals_the_dense_policy_iteration(links, needs):
    """The fixture of ADR-0058: four white unlinked sockets on a helmet asking the three attributes alike, item level 84, 20%, Fusing and Chromatic at 1."""
    steps = [FinishStep("Orb of Fusing", OrbOfFusing(), 1.0), FinishStep("Chromatic Orb", ChromaticOrb(), 1.0)]
    wanted = SocketWanted(links=links, red=needs[0], green=needs[1], blue=needs[2])
    finish = solve_finish(finish_data(), HELMET, 84, wanted, Sockets.unlinked((W,) * 4), steps, quality=20)
    dense, _ = dense_solve(4, links, needs)
    assert finish.value == pytest.approx(dense, rel=1e-9)


def test_the_fixture_of_adr_0058_costs_44_60_orbs():
    steps = [FinishStep("Orb of Fusing", OrbOfFusing(), 1.0), FinishStep("Chromatic Orb", ChromaticOrb(), 1.0)]
    finish = solve_finish(finish_data(), HELMET, 84, SocketWanted(links=3, red=1, green=1, blue=1), Sockets.unlinked((W,) * 4), steps, quality=20)
    assert round(finish.value, 2) == 44.60


# --- layer 2: a simulation of the finish policy on concrete items ---------------------------------------------------------------------------


def simulate(finish, base_id: str, start: Sockets, runs: int, seed: int) -> tuple[float, float]:
    """The mean cost of the finish policy over `runs` plays, every use drawn from the action itself on the concrete item, and its standard error."""
    model = finish.model
    steps = {step.label: step for step in model.steps}
    rng = np.random.default_rng(seed)
    draws: dict = {}
    totals = []
    for _ in range(runs):
        sockets, total = start, 0.0
        for _ in range(100_000):
            state = model.reduce(state_of(sockets))
            if model.is_goal(state):
                break
            step = steps[finish.policy[state]]
            key = (step.label, sockets)
            if key not in draws:
                outcomes = list(step.action.outcomes(finish_data(), item_of(sockets, base_id)).by_sockets.items())
                draws[key] = ([result for result, _ in outcomes], np.cumsum([float(chance) for _, chance in outcomes]))
            results, cumulative = draws[key]
            sockets = results[min(int(np.searchsorted(cumulative, rng.random() * cumulative[-1], side="right")), len(results) - 1)]
            total += step.cost
        else:
            raise AssertionError("a play did not finish")
        totals.append(total)
    values = np.array(totals)
    return float(values.mean()), float(values.std(ddof=1) / math.sqrt(runs))


def test_the_simulated_mean_of_the_finish_policy_is_within_five_standard_errors():
    data = finish_data()
    start = Sockets.unlinked((W,) * 2)
    wanted = SocketWanted(count=4, links=3, red=1, green=1, blue=1)
    finish = solve_finish(data, HELMET, 84, wanted, start, all_steps(data, omen=30.0), quality=20)
    taken = set(finish.policy.values())
    assert len(taken) >= 3  # the policy mixes count, link and colour actions
    mean, error = simulate(finish, HELMET, start, runs=3000, seed=231)
    assert abs(mean - finish.value) <= 5 * error, (mean, error, finish.value)


# --- the numbers of the ticket and the ADRs ----------------------------------------------------------------------------------------------


def test_six_links_from_one_white_socket_by_orbs_alone_costs_214_9_and_1000_orbs():
    """With only the orbs (no Omen, no bench) a six-link target from one white socket at 20% quality costs 214.9 Jeweller's Orbs and 1,000.0 Orbs of
    Fusing (ADR-0047's amendment: 214.9 to six sockets from one; Fusing links six with chance 100 in 100,000)."""
    data = finish_data()
    jeweller, fusing = FinishStep("Jeweller's Orb", JewellersOrb(), 1.0), FinishStep("Orb of Fusing", OrbOfFusing(), 1.0)
    start = Sockets.unlinked((W,))
    sockets_only = solve_finish(data, BODY, 84, SocketWanted(count=6), start, [jeweller], quality=20)
    assert round(sockets_only.value, 1) == 214.9
    six_links = solve_finish(data, BODY, 84, SocketWanted(count=6, links=6), start, [jeweller, fusing], quality=20)
    assert six_links.value == pytest.approx(sockets_only.value + 1000.0, rel=1e-9)
    priced = solve_finish(data, BODY, 84, SocketWanted(count=6, links=6), start, [FinishStep("Jeweller's Orb", JewellersOrb(), 0.5), fusing], quality=20)
    assert priced.value == pytest.approx(sockets_only.value * 0.5 + 1000.0, rel=1e-9)


def test_the_second_reading_of_the_jeweller_s_table_is_the_plan_s_policy_at_the_2014_table():
    """ADR-0047's amendment: 222.6 Jeweller's Orbs to six sockets from one at the 2014 table, beside the plan's 214.9."""
    finish = solve_finish(finish_data(), BODY, 84, SocketWanted(count=6), Sockets.unlinked((W,)), [FinishStep("Jeweller's Orb", JewellersOrb(), 1.0)], quality=20)
    assert round(finish.second_readings["jeweller_table"], 1) == 222.6
    assert "chromatic_forced_colour" not in finish.second_readings  # no colour asked


def test_the_forced_colour_has_a_second_reading_only_for_a_target_of_one_coloured_socket():
    """On the dexterity-intelligence helmet of `colour_data` (red is the missing colour, 0.1 of a coloured socket), where the flatter reading of the
    forced colour differs from Siveran's weights; on a base asking the three alike the two readings are the same thirds."""
    data = colour_data()
    chromatic = [FinishStep("Chromatic Orb", ChromaticOrb(), 1.0)]
    one = solve_finish(data, HELMET, 84, SocketWanted(red=1), Sockets.unlinked((W,) * 2), chromatic, quality=20)
    assert set(one.second_readings) == {"chromatic_forced_colour"}
    assert one.second_readings["chromatic_forced_colour"] < one.value  # the flatter reading forces red more often than Siveran's weights
    two = solve_finish(data, HELMET, 84, SocketWanted(red=2), Sockets.unlinked((W,) * 2), chromatic, quality=20)
    assert two.second_readings == {}


def test_a_start_that_meets_the_target_costs_nothing():
    finish = solve_finish(finish_data(), BODY, 84, SocketWanted(count=3, links=3), Sockets((R, G, B), (3,)), all_steps(finish_data()), quality=20)
    assert finish.met and finish.value == 0.0 and finish.policy == {}


def test_below_20_quality_the_finish_buys_quality_when_the_links_need_it():
    """ADR-0049: the finish is solved at the item's own quality and at 20%, the currency to get there added, and takes the cheaper."""
    data = finish_data()
    steps = [FinishStep("Orb of Fusing", OrbOfFusing(), 1.0)]
    scrap = FinishStep("Armourer's Scrap", ApplyQualityCurrency("Armourer's Scrap"), 0.25)
    start = Sockets.unlinked((W,) * 4)
    without = solve_finish(data, BODY, 84, SocketWanted(links=3), start, steps, quality=5)
    assert without.value == math.inf  # no Fusing table below 20%, and nothing else links
    bought = solve_finish(data, BODY, 84, SocketWanted(links=3), start, steps, quality=5, quality_step=scrap)
    at_twenty = solve_finish(data, BODY, 84, SocketWanted(links=3), start, steps, quality=20)
    cost = float(expected_quality_currency(84, 20, 5)) * 0.25
    assert bought.quality_bought and bought.quality_cost == pytest.approx(cost)
    assert bought.value == pytest.approx(at_twenty.value + cost, rel=1e-12)


def test_the_finish_keeps_the_item_s_own_quality_when_buying_it_does_not_pay():
    data = finish_data()
    steps = [FinishStep("Jeweller's Orb", JewellersOrb(), 1.0)]
    scrap = FinishStep("Armourer's Scrap", ApplyQualityCurrency("Armourer's Scrap"), 0.25)
    finish = solve_finish(data, BODY, 84, SocketWanted(count=5), Sockets.unlinked((W,)), steps, quality=0, quality_step=scrap)
    assert not finish.quality_bought and finish.quality_cost == 0.0  # the Jeweller's Orb ignores quality (ADR-0047)


def test_a_policy_of_the_finish_reaches_the_goal_from_every_state_it_acts_in():
    data = finish_data()
    finish = solve_finish(data, HELMET, 84, SocketWanted(count=4, links=4, red=1, green=1, blue=1), Sockets.unlinked((W,)), all_steps(data), quality=20)
    assert math.isfinite(finish.value)
    assert all(math.isfinite(finish.solution.values[state]) for state in finish.policy)


# --- the budget of ADR-0058 ---------------------------------------------------------------------------------------------------------------

BUDGET_SECONDS = 60.0  # ADR-0058 keeps ADR-0010's goal of a minute for the finish


@pytest.mark.parametrize(
    ("links", "states"),
    [(5, 13_552), (3, 47_124), (None, 3_360)],
    ids=["a group of five", "a group of three", "no link"],
)
def test_six_sockets_with_three_named_colours_solve_within_the_budget(links, states):
    """ADR-0058, "Measured": six sockets, red, green and blue (in a group of `links`), every finish action, Omens at 50, from one white socket; the
    states the routine reaches that are not finished are the ADR's counts."""
    data = finish_data()
    began = time.perf_counter()
    finish = solve_finish(data, BODY, 84, SocketWanted(count=6, links=links, red=1, green=1, blue=1), Sockets.unlinked((W,)), all_steps(data, omen=50.0), quality=20)
    seconds = time.perf_counter() - began
    assert finish.solution.open_states == states
    assert math.isfinite(finish.value)
    assert seconds < BUDGET_SECONDS
