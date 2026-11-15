"""The crafted-pattern bound and the envelope search under a roll limit, with a Divine Orb (ticket #830, OR-12, OR-13, OR-26, OR-32).

Until #830 the bound refused a goal with a roll limit and an offered action that rerolls values (`pattern_refusal`), so such a target was walked
whole. The key already held what each wanted mod gives its leaf as it rolled (ABSENT, BELOW or PASSING the limit, `PatternKey.status`); what
was missing:

* the **member policy of a Divine Orb**: it keeps every slot and rolls afresh the slots a roll limit tells apart (`$<mod id>`, relevant slots);
  a pure junk slot gives the goal nothing at any roll and stays. It reads nothing else of the junk than its count, so its kernel pushed through
  the key is the same for every pure junk assignment: `Mode.ONE` (`Pattern.mode_of`), as Remove Crafted Mods. Before, it took `Mode.ALL`,
  every pure junk assignment at every key, which on divine-roll-limits/small spent the bound's whole share of the run's net (28 s);
* the **universe** holds every outcome of a rollable mod's law (`_rolled_contributions`), so a slot that rolled PASSING is not learnt from a
  kernel, which begins the build again;
* two slots that each stand for one mod of a shared family are never on one item: `_relevant` makes no such multiset.

On the tiny amulet pool of `abstraction_rolls_oracle` (short ranges, so every roll can be listed) with a Chaos Orb, an Exalted Orb, an Orb of
Annulment, a Divine Orb and the restart, for three goals with roll limits: the Divine Orb's offered member is as good as every member (brute force
over the key), the model is a lower bound at every state of the exact graph, and the envelope search gives the exact graph's mean to 1e-9.
"""

import random

import pytest
from abstraction_pool import CRAFTED, DAMAGE_1, DAMAGE_2, LEVEL, LIFE_1, MANA_1
from abstraction_rolls_oracle import TINY, rolled, tiny_item
from items_support import AMULET
from pattern_support import check_dominates, exact_values
from test_abstraction_rolls import GOALS

from crafting_system.abstraction import Abstraction, Status
from crafting_system.abstraction._kinds import MOD_PREFIX
from crafting_system.abstraction import _pattern
from crafting_system.abstraction._pattern import Mode, Pattern, PatternOffer, build_pattern_model
from crafting_system.actions import ActionError, AnnulmentOrb, ChaosOrb, DivineOrb, ExaltedOrb, OpenListing, unopened_listing
from crafting_system.cli import Offer
from crafting_system.items import Rarity, Side
from crafting_system.planner._envelope_plan import envelope_result
from crafting_system.planner._offers import RESTART, BuyStartItem, PricedOffer
from crafting_system.planner._pattern_bound import pack_pattern_model
from crafting_system.solver import solve_packed

TOLERANCE = 1e-9
CHAOS, EXALT, ANNUL, DIVINE = ChaosOrb(), ExaltedOrb(), AnnulmentOrb(), DivineOrb()
ACTIONS = {"Chaos Orb": (CHAOS, 6.0), "Exalted Orb": (EXALT, 2.0), "Orb of Annulment": (ANNUL, 5.0), "Divine Orb": (DIVINE, 1.0)}
RESTART_PRICE = 3.0
START = tiny_item(rolled(LIFE_1, 1), rolled(MANA_1, 2))  # Life 1 below the limit of "life" (3 of 1..4), and a pure junk suffix
CASES = ["life", "life_resist", "hybrid"]


def abstraction(goal: str, divine: bool = True) -> Abstraction:
    return Abstraction(TINY, GOALS[goal], AMULET, LEVEL, tuple(action for action, _ in ACTIONS.values() if divine or action is not DIVINE))


def pattern_offers_of(divine: bool = True) -> list[PatternOffer]:
    return [PatternOffer(label, action, cost) for label, (action, cost) in ACTIONS.items() if divine or action is not DIVINE] + [
        PatternOffer(RESTART, None, RESTART_PRICE)
    ]


def priced_offers(divine: bool = True) -> list[PricedOffer]:
    offers = [PricedOffer(Offer(label, action, {label: 1}), cost, ()) for label, (action, cost) in ACTIONS.items() if divine or action is not DIVINE]
    return [*offers, PricedOffer(Offer(RESTART, BuyStartItem(START), {}), RESTART_PRICE, ())]


def walked_states(ab: Abstraction, seed: int, walks: int = 40, steps: int = 8) -> list:
    """The states a seeded random walk of the offered actions meets from `START` (the keys the brute force is run on)."""
    rng = random.Random(seed)
    start = ab.compress(START)
    found = {}
    for _ in range(walks):
        state = start
        for _ in range(steps):
            found[state] = None
            if ab.is_goal(state):
                break
            try:
                kernel = ab.kernel(state, rng.choice([action for action, _ in ACTIONS.values()]))
            except ActionError:
                continue
            state = rng.choices(list(kernel), weights=[float(chance) for chance in kernel.values()])[0]
    return list(found)


@pytest.mark.parametrize("goal", CASES)
def test_the_divine_orbs_one_member_is_as_good_as_every_member_of_its_key(goal):
    """The soundness of `Mode.ONE` for a reroll of values, against every member of the key (`check_dominates`, random values of the successor keys)."""
    ab = abstraction(goal)
    pattern = Pattern(ab, None, [action for action, _ in ACTIONS.values()])
    keys = list(dict.fromkeys(pattern.key(state) for state in walked_states(ab, seed=830)))
    rng = random.Random(1)
    compared = choices = 0
    for key in keys:
        assert pattern.mode_of(DIVINE, key) is Mode.ONE  # no lock on this pool
        members, offered = check_dominates(pattern, ab, key, DIVINE, Mode.ONE, rng, trials=8)
        compared += offered
        choices += len(pattern.members(key, Mode.ONE)) < members
    assert compared, "no key of the walk has a member the Divine Orb can take"
    assert choices, "no key has a choice of pure junk: the check above compares nothing that `Mode.ONE` leaves out"


def test_under_a_lock_the_divine_orb_takes_every_member():
    """The locked side keeps its mods and their rolls through the orb: a key that holds a lock uses `Mode.ALL`, as a reroll under a lock does."""
    ab = Abstraction(TINY, GOALS["life"], AMULET, LEVEL, (CHAOS, DIVINE), metamods=True)
    pattern = Pattern(ab, None, [CHAOS, DIVINE])
    locked = pattern.key(ab.compress(tiny_item(rolled(LIFE_1, 1), rolled(CRAFTED, 1, crafted=True))))  # the crafted suffix lock
    assert pattern.holds_lock(locked) and pattern.mode_of(DIVINE, locked) is Mode.ALL
    plain = pattern.key(ab.compress(tiny_item(rolled(LIFE_1, 1))))
    assert pattern.mode_of(DIVINE, plain) is Mode.ONE


@pytest.mark.parametrize("goal", CASES)
def test_the_universe_holds_every_outcome_of_a_roll_before_any_kernel_is_run(goal):
    ab = abstraction(goal)
    universe = Pattern(ab, None, [action for action, _ in ACTIONS.values()]).universe(frozenset())
    rollable = DAMAGE_1 if goal == "hybrid" else LIFE_1  # the first leaf's mod: Life 1 rolls 1..4 and passes at 3; Damage 1 passes with both at 2
    outcomes = {slot.contribution[0] for side in universe.relevant.values() for slot in side if slot.kind == MOD_PREFIX + rollable}
    assert outcomes >= {Status.BELOW, Status.PASSING}
    model = build_pattern_model(ab, ab.compress(START), pattern_offers_of())
    assert model.stats.universe_growth == 0  # no kernel taught the build a slot: it never began again


def test_a_relevant_multiset_never_holds_two_mods_of_one_family():
    ab = abstraction("hybrid")  # Damage 1 and Damage 2 are slots by mod (`$<mod id>`) of one family
    pattern = Pattern(ab, None, [action for action, _ in ACTIONS.values()])
    universe = pattern.universe(frozenset())
    side = Side(TINY.mods[DAMAGE_1].generation_type)
    damages = {slot.kind for slot in universe.relevant[side] if slot.kind in (MOD_PREFIX + DAMAGE_1, MOD_PREFIX + DAMAGE_2)}
    assert len(damages) == 2
    multisets = pattern._relevant(universe, side, 3, (Status.PASSING,) * len(ab.goal.leaves))
    assert any(any(slot.kind in damages for slot in multiset) for multiset in multisets)
    for multiset in multisets:
        families = [family for slot in multiset for family in pattern._families_of(slot)]
        assert len(families) == len(set(families)), multiset


@pytest.mark.parametrize("divine", [True, False], ids=["divine", "no-divine"])
@pytest.mark.parametrize("goal", CASES)
def test_the_model_is_a_lower_bound_at_every_state_of_the_exact_graph(goal, divine):
    ab = abstraction(goal, divine)
    start = ab.compress(START)
    offers = pattern_offers_of(divine)
    exact = exact_values(ab, start, offers)
    model = build_pattern_model(ab, start, offers)
    solved = solve_packed(pack_pattern_model(model, offers))
    pattern = Pattern(ab, None, [offer.action for offer in offers if offer.action is not None])
    for state, value in exact.items():
        key = pattern.key(state)
        assert key in model.index, "a state of the exact graph has a key the model never reached"
        assert float(solved.value[model.index[key]]) <= value * (1 + TOLERANCE) + TOLERANCE, (state, value)
    assert 0 < solved.value[0] <= exact[start] * (1 + TOLERANCE)


@pytest.mark.parametrize("divine", [True, False], ids=["divine", "no-divine"])
@pytest.mark.parametrize("goal", CASES)
def test_the_envelope_search_gives_the_exact_graphs_mean(goal, divine):
    ab = abstraction(goal, divine)
    start = ab.compress(START)
    exact = exact_values(ab, start, pattern_offers_of(divine))[start]
    result = envelope_result(ab, start, priced_offers(divine))
    info = result.info["envelope"]
    assert info.exact and info.bound_stopped is None
    assert result.solution.values[start] == pytest.approx(exact, rel=TOLERANCE)
    assert info.lower <= exact * (1 + TOLERANCE)


@pytest.mark.parametrize("goal", CASES)
def test_the_divine_orb_is_worth_having_in_these_worlds(goal):
    """Each world's optimum is cheaper with the Divine Orb than without it, so the checks above compare plans that use it."""
    with_it, without = abstraction(goal), abstraction(goal, divine=False)
    cheaper = exact_values(with_it, with_it.compress(START), pattern_offers_of())[with_it.compress(START)]
    dearer = exact_values(without, without.compress(START), pattern_offers_of(False))[without.compress(START)]
    assert cheaper < dearer * (1 - 1e-6)


def test_the_draw_of_a_bought_listing_makes_no_member_at_an_opened_key(monkeypatch):
    """The listing's draw works only on the unopened listing, and every other action only on an opened item (a flag of the key): the build
    makes no member for either where the flag refuses it, nor asks the process pool for their distributions there (#830)."""
    monkeypatch.setattr(_pattern, "PRIME_FROM", 1)  # every key primes its offers (the product does from 16)
    primed: list = []
    monkeypatch.setattr(Abstraction, "prime", lambda self, requests: primed.extend(requests))
    draw = OpenListing(Rarity.RARE)
    ab = Abstraction(TINY, GOALS["life"], AMULET, LEVEL, (CHAOS, DIVINE, draw))
    start = ab.compress(unopened_listing(TINY, tiny_item()))
    offers = [PatternOffer("draw", draw, 0.0), PatternOffer("Chaos Orb", CHAOS, 1.0), PatternOffer("Divine Orb", DIVINE, 3.0), PatternOffer(RESTART, None, RESTART_PRICE)]
    model = build_pattern_model(ab, start, offers)
    assert len(model.keys) > 2 and model.keys[0].flags.unopened
    assert sum(count for (_, label), count in model.stats.modes.items() if label == "draw") == 1  # the start key alone
    assert primed and all((action is draw) == member.flags.unopened for member, action in primed)
    exact = exact_values(ab, start, offers)
    assert 0 < float(solve_packed(pack_pattern_model(model, offers)).value[0]) <= exact[start] * (1 + TOLERANCE)
