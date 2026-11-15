"""The crafted-pattern bound and the envelope search with the veiled orbs, the unveil and the picks (ticket #828, ADR-0026, OR-12, OR-13, OR-26).

Until #828 the bound refused an abstraction that keeps the unveil offer (`pattern_refusal`, #507), so a target with the veiled kinds was walked
whole (R07 out of memory, R24 1.14 M states). What the bound gained:

* **the key holds the veiled slots exactly** (`PatternKey.veiled`): the placeholder and every mod unveiled from the pool, as the crafted slots are.
  They are never a member's choice: the universe of the members holds none of them, so no member holds two placeholders (a double veil, which
  every veiled action refuses as a model gap) or a placeholder the key does not. The offer is in the key already (`held`), whole: a pick takes the
  k-th mod of it;
* **the member policies** (`Pattern.mode_of`): the Veiled Chaos Orb is given a view of the item without its ordinary slots wherever no lock keeps
  a side (`Abstraction._erases`), so every member has the same kernel: `Mode.ANY`; the unveil, the picks and the Veiled Exalted Orb read of the
  junk its count and the families they name (the unveiled pool's, told apart by name: relevant slots, enumerated exactly) and keep the rest, so
  their kernel pushed through the key is the same for every pure junk assignment: `Mode.ONE`, a lock or not (the unveil and the picks change no
  ordinary slot; the Veiled Exalted Orb removes one of the removable slots uniformly, and those are counted by class in the key);
* the pick's backup, a minimum inside the expectation of the unveil, is the model's own: the unveil leads to the offer keys, where the only
  actions are the picks.

On the small amulet pool of `abstraction_veiled_support` (the veiled records, an ordinary mod in the family of an unveiled one), for two goals and
a start with and without a lock: each offered member is as good as every member of its key (brute force over the key, random values of the
successor keys), the model is a lower bound at every state of the exact graph, and the envelope search gives the exact graph's mean to 1e-9.
"""

import random

import pytest
from abstraction_pool import CRAFTED as LOCK_SUFFIXES
from abstraction_pool import LEVEL, LIFE_1, RESIST_2
from abstraction_veiled_support import DATA, PRE, SUF, amulet, holder, rolled
from items_support import AMULET
from pattern_support import check_dominates, exact_values
from veiled_support import LIFE_2 as VEIL_LIFE_2
from veiled_support import SPEED

from crafting_system.abstraction import Abstraction, Goal, Wanted, pattern_refusal
from crafting_system.abstraction._kinds import UNVEILED_PREFIX
from crafting_system.abstraction._pattern import Mode, Pattern, PatternOffer, build_pattern_model
from crafting_system.actions import ActionError, AnnulmentOrb, Pick, Unveil, VeiledChaosOrb, VeiledExaltedOrb
from crafting_system.cli import Offer
from crafting_system.planner._envelope_plan import envelope_result
from crafting_system.planner._offers import RESTART, BuyStartItem, PricedOffer
from crafting_system.planner._pattern_bound import pack_pattern_model
from crafting_system.solver import solve_packed

TOLERANCE = 1e-9
VEILED_CHAOS, VEILED_EXALT, UNVEIL, ANNUL = VeiledChaosOrb(), VeiledExaltedOrb(), Unveil(), AnnulmentOrb()
PICKS = (Pick(1), Pick(2), Pick(3))
FREE = 1e-6  # what `price_offers` gives an action that consumes nothing (ADR-0026, the epsilon)
ACTIONS = {
    "Veiled Chaos Orb": (VEILED_CHAOS, 5.0), "Veiled Exalted Orb": (VEILED_EXALT, 3.0), "Orb of Annulment": (ANNUL, 1.0), "Unveil": (UNVEIL, FREE),
    **{f"Pick {pick.index}": (pick, FREE) for pick in PICKS},
}  # fmt: skip
VEILED = (VEILED_CHAOS, VEILED_EXALT, UNVEIL, *PICKS)
RESTART_PRICE = 2.0
GOALS = {"speed": Goal((Wanted(frozenset({SPEED})),)), "life_2": Goal((Wanted(frozenset({VEIL_LIFE_2})),))}
STARTS = {
    "plain": amulet(rolled(LIFE_1), rolled(RESIST_2)),
    "lock": amulet(rolled(LIFE_1), rolled(RESIST_2), rolled(LOCK_SUFFIXES, crafted=True)),  # Suffixes Cannot Be Changed, crafted
}


def abstraction(goal: str) -> Abstraction:
    return Abstraction(DATA, GOALS[goal], AMULET, LEVEL, tuple(action for action, _ in ACTIONS.values()), metamods=True)


def pattern_offers() -> list[PatternOffer]:
    return [PatternOffer(label, action, cost) for label, (action, cost) in ACTIONS.items()] + [PatternOffer(RESTART, None, RESTART_PRICE)]


def priced_offers(start) -> list[PricedOffer]:
    offers = [PricedOffer(Offer(label, action, {label: 1}), cost, ()) for label, (action, cost) in ACTIONS.items()]
    return [*offers, PricedOffer(Offer(RESTART, BuyStartItem(start), {}), RESTART_PRICE, ())]


def walked_states(ab: Abstraction, start, seed: int, walks: int = 60, steps: int = 8) -> list:
    """The states a seeded random walk of the offered actions meets from `start`, the picks taken where an offer is held (the keys checked)."""
    rng = random.Random(seed)
    first = ab.compress(start)
    found = {}
    actions = [action for action, _ in ACTIONS.values()]
    for _ in range(walks):
        state = first
        for _ in range(steps):
            found[state] = None
            if ab.is_goal(state):
                break
            try:
                kernel = ab.kernel(state, rng.choice(PICKS if state.offer else actions))
            except ActionError:
                continue
            state = rng.choices(list(kernel), weights=[float(chance) for chance in kernel.values()])[0]
    return list(found)


def test_the_bound_no_longer_refuses_the_unveil_offer():
    ab = abstraction("speed")
    assert ab.tracks_offer and pattern_refusal(ab) is None


@pytest.mark.parametrize("start", STARTS)
def test_the_member_policies_of_the_veiled_actions(start):
    ab = abstraction("speed")
    pattern = Pattern(ab, None, VEILED)
    key = pattern.key(ab.compress(STARTS[start]))
    locked = start == "lock"
    assert pattern.holds_lock(key) is locked
    assert pattern.mode_of(VEILED_CHAOS, key) is (Mode.ALL if locked else Mode.ANY)  # a lock keeps its side through the reroll: every member
    for action in (VEILED_EXALT, UNVEIL, *PICKS):
        assert pattern.mode_of(action, key) is Mode.ONE


def test_the_key_holds_the_placeholder_and_the_unveiled_mods_and_no_member_chooses_them():
    ab = abstraction("speed")
    pattern = Pattern(ab, None, VEILED)
    state = ab.compress(amulet(holder(SUF), rolled(RESIST_2), veil_offer=(SPEED,)))
    key = pattern.key(state)
    assert len(key.veiled) == 1 and key.counts == (0, 1)  # the placeholder is in the key, the resistance is an ordinary suffix
    assert key.held == state.held
    picked = next(iter(ab.kernel(state, Pick(1))))
    after = pattern.key(picked)
    assert [slot.kind[0] for slot in after.veiled] == [UNVEILED_PREFIX] and after.counts == key.counts
    universe = pattern.universe(frozenset())
    for members in (pattern.members(key, Mode.ALL), pattern.members(after, Mode.ALL)):
        assert members and all(pattern.key(member) in (key, after) for member in members)
    assert not any(pattern.is_veiled(slot) for side in universe.relevant.values() for slot in side)
    two = ab.compress(amulet(holder(PRE), rolled(RESIST_2)))
    assert pattern.key(two) != pattern.key(ab.compress(amulet(holder(SUF), rolled(RESIST_2))))  # the side of the veil is in the key


@pytest.mark.parametrize("start", STARTS)
@pytest.mark.parametrize("goal", GOALS)
def test_each_veiled_actions_offered_member_is_as_good_as_every_member_of_its_key(goal, start):
    """The soundness of `Mode.ANY` and `Mode.ONE` for the veiled actions, against every member of the key (`check_dominates`)."""
    ab = abstraction(goal)
    pattern = Pattern(ab, None, [action for action, _ in ACTIONS.values()])
    keys = list(dict.fromkeys(pattern.key(state) for state in walked_states(ab, STARTS[start], seed=828)))
    rng = random.Random(1)
    compared = {action: 0 for action in VEILED}
    choices = 0
    for key in keys:
        for action in VEILED:
            mode = pattern.mode_of(action, key)
            if mode is Mode.ALL:
                continue
            members, offered = check_dominates(pattern, ab, key, action, mode, rng, trials=6)
            compared[action] += offered
            choices += len(pattern.members(key, mode)) < members
    assert all(compared[action] for action in (VEILED_CHAOS, UNVEIL, PICKS[0])), compared
    assert compared[VEILED_EXALT] or start == "lock", compared  # the plain start's walk holds no veiled mod at some key
    assert choices, "no key has a choice of pure junk: the check above compares nothing the member policies leave out"


@pytest.mark.parametrize("start", STARTS)
@pytest.mark.parametrize("goal", GOALS)
def test_the_model_is_a_lower_bound_at_every_state_of_the_exact_graph(goal, start):
    ab = abstraction(goal)
    first = ab.compress(STARTS[start])
    offers = pattern_offers()
    exact = exact_values(ab, first, offers)
    model = build_pattern_model(ab, first, offers)
    assert model.stopped is None
    solved = solve_packed(pack_pattern_model(model, offers))
    pattern = Pattern(ab, None, [offer.action for offer in offers if offer.action is not None])
    for state, value in exact.items():
        key = pattern.key(state)
        assert key in model.index, "a state of the exact graph has a key the model never reached"
        assert float(solved.value[model.index[key]]) <= value * (1 + TOLERANCE) + TOLERANCE, (state, value)
    assert 0 < solved.value[0] <= exact[first] * (1 + TOLERANCE)


@pytest.mark.parametrize("start", STARTS)
@pytest.mark.parametrize("goal", ["speed"])  # the goal of Life 2 takes 30 s a start here for the same check
def test_the_envelope_search_gives_the_exact_graphs_mean(goal, start):
    ab = abstraction(goal)
    first = ab.compress(STARTS[start])
    exact = exact_values(ab, first, pattern_offers())[first]
    result = envelope_result(ab, first, priced_offers(STARTS[start]))
    info = result.info["envelope"]
    assert info.exact and info.bound_stopped is None
    assert result.solution.values[first] == pytest.approx(exact, rel=TOLERANCE)
    assert info.lower <= exact * (1 + TOLERANCE)
