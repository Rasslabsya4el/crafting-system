"""The crafted-pattern bound and the envelope search with imprints (ticket #833, ADR-0034, ADR-0060, OR-12, OR-13, OR-26, OR-32).

Until #833 the bound refused an abstraction that keeps the imprints (`pattern_refusal`, #507), so a target that offers the Craicic Croaker or the
Fenumal Plagued Arachnid was walked whole (R17 did not plan within an hour). What the bound gained (module docstring of `abstraction/_pattern.py`,
"The imprints"):

* **the key holds the key of each snapshot** (`CompressedState.held` at `IMPRINTS`), and a member holds one snapshot of each key (`Pattern.held_of`):
  the actions that do not move the imprints read none of them, an imprint leads to the key's own key added, a restore to the snapshot's key;
* an imprint and a restore are asked of one member (`PatternBuilder._move`), and the rule that refuses a dominated move (a state already held, a
  restore onto the state the item is in) is the only one that reads the member.

On the small amulet pool of `abstraction_pool` (a magic amulet, three wanted mods, the Alteration, Augmentation and Regal orbs, the Annulment, the
imprint and the restore), with the cap of one imprint and of two: every concrete move of the exact graph is matched by one the model offers at its
key, the model is a lower bound at every state of the exact graph, and the envelope search gives the exact graph's mean to 1e-9. The bound the
ticket's text proposed, `min(LB(s), c_restore + LB(h))` from the bound without the imprint, is not one: an item at its own snapshot is worth the
beast less than without it, and a gamble from it less still (`test_the_bound_without_the_imprint_is_no_bound_of_an_item_that_holds_one`).
"""

import random
from collections import defaultdict
from dataclasses import replace
from fractions import Fraction

import pytest
from abstraction_pool import DAMAGE_2, LEVEL, LIFE_2, RESIST_3, SMALL, small_item
from items_support import AMULET
from pattern_support import exact_values, pushed

from crafting_system.abstraction import Abstraction, Goal, Wanted, pattern_refusal
from crafting_system.abstraction._pattern import IMPRINTS, Mode, Pattern, PatternBuilder, PatternOffer, build_pattern_model
from crafting_system.actions import ActionError, AlterationOrb, AnnulmentOrb, AugmentationOrb, Imprint, RegalOrb, Restore, imprint_actions
from crafting_system.cli import Offer
from crafting_system.items import Rarity
from crafting_system.planner._envelope_plan import envelope_result
from crafting_system.planner._offers import RESTART, BuyStartItem, PricedOffer
from crafting_system.planner._pattern_bound import pack_pattern_model
from crafting_system.solver import solve_packed

TOLERANCE = 1e-9
BEAST = 2.0  # the Craicic Croaker
FREE = 1e-6  # a restore (`RESTORE_COST`)
RESTART_PRICE = 1.0
CRAFTS = {"Orb of Alteration": (AlterationOrb(), 0.1), "Orb of Augmentation": (AugmentationOrb(), 0.05), "Regal Orb": (RegalOrb(), 0.5), "Orb of Annulment": (AnnulmentOrb(), 5.0)}  # fmt: skip
GOAL = Goal((Wanted(frozenset({LIFE_2})), Wanted(frozenset({RESIST_3})), Wanted(frozenset({DAMAGE_2}))))
START = small_item(rarity=Rarity.MAGIC)


def moves(cap: int) -> dict:
    """The imprints and restores of a magic item under the cap, priced as the planner prices them (the beast, and a restore at the epsilon)."""
    found = {}
    for action in imprint_actions(SMALL, START, max_imprints=cap):
        if isinstance(action, Imprint):
            found[f"Imprint {action.replaces}"] = (action, BEAST)
        else:
            found[f"Restore {action.index}"] = (action, FREE)
    return found


def offered(cap: int | None) -> dict:
    return {**CRAFTS, **(moves(cap) if cap else {})}


def abstraction(cap: int | None) -> Abstraction:
    return Abstraction(SMALL, GOAL, AMULET, LEVEL, tuple(action for action, _ in offered(cap).values()))


def pattern_offers(cap: int | None) -> list[PatternOffer]:
    return [PatternOffer(label, action, cost) for label, (action, cost) in offered(cap).items()] + [PatternOffer(RESTART, None, RESTART_PRICE)]


def priced_offers(cap: int) -> list[PricedOffer]:
    offers = [PricedOffer(Offer(label, action, {label: 1}), cost, ()) for label, (action, cost) in offered(cap).items()]
    return [*offers, PricedOffer(Offer(RESTART, BuyStartItem(START), {}), RESTART_PRICE, ())]


@pytest.fixture(scope="module")
def world():
    """The exact graph and the model of the key with the cap of one imprint, built once: (cap, abstraction, start state, exact values, model,
    model values). With two the exact graph has about 60,000 states (a minute): `test_with_two_imprints_every_move_is_offered_at_its_key`."""
    cap = 1
    ab = abstraction(cap)
    first = ab.compress(START)
    offers = pattern_offers(cap)
    exact = exact_values(ab, first, offers)
    model = build_pattern_model(ab, first, offers)
    solved = solve_packed(pack_pattern_model(model, offers))
    return cap, ab, first, exact, model, [float(value) for value in solved.value]


def test_the_bound_no_longer_refuses_the_imprints():
    ab = abstraction(1)
    assert ab.tracks_imprints and pattern_refusal(ab) is None
    Pattern(ab)  # builds


def test_the_key_holds_the_key_of_each_snapshot_and_a_member_holds_one_snapshot_of_it(world):
    _cap, ab, _first, exact, _model, _values = world
    pattern = Pattern(ab, None, [action for action, _ in offered(1).values()])
    held = [state for state in exact if state.imprints]
    assert held
    by_key = defaultdict(set)
    for state in held:
        key = pattern.key(state)
        assert key.held[IMPRINTS] == tuple(sorted((pattern.key(snapshot) for snapshot in state.imprints), key=pattern._snapshot_order))
        by_key[key].add(state.imprints)
        for member in pattern.members(key, Mode.ANY):
            assert pattern.key(member) == key and len(member.imprints) == len(state.imprints)
    assert any(len(snapshots) > 1 for snapshots in by_key.values()), "no key holds two different snapshots: the key would be the snapshot itself"


def test_every_concrete_move_is_offered_at_its_key_or_dominated(world):
    """Brute force over the states of the exact graph: the pushed kernel of each imprint and restore a state takes is one the model offers at
    the state's key, except a move back to the key itself (a positive cost for nothing) and a restore onto a snapshot of the key's own key,
    which the module docstring proves is never needed."""
    cap, ab, _first, exact, model, _values = world
    pattern = Pattern(ab, None, [action for action, _ in offered(cap).values()])
    offers = pattern_offers(cap)
    labels = [offer.label for offer in offers]
    matched = dominated = 0
    for state in exact:
        if ab.is_goal(state):
            continue
        key = pattern.key(state)
        row = model.actions[model.index[key]]
        kernels = {_pushed_of(model, kid) for oi, kid in row if labels[oi].startswith(("Imprint", "Restore"))}
        for label, (action, _) in moves(cap).items():
            kernel = pushed(pattern, ab, state, action)
            if kernel is None:
                continue
            (successor,) = kernel
            if successor == key or (label.startswith("Restore") and _without_imprints(successor) == _without_imprints(key)):
                dominated += 1  # back to the key at a positive cost, or a restore onto a snapshot of the key's own key
                continue
            assert frozenset(kernel.items()) in kernels, (state, label)
            matched += 1
    assert matched and dominated


def test_the_model_is_a_lower_bound_at_every_state_of_the_exact_graph(world):
    cap, ab, first, exact, model, values = world
    pattern = Pattern(ab, None, [action for action, _ in offered(cap).values()])
    assert model.stopped is None
    for state, value in exact.items():
        key = pattern.key(state)
        assert key in model.index, "a state of the exact graph has a key the model never reached"
        assert values[model.index[key]] <= value * (1 + TOLERANCE) + TOLERANCE, (state, value)
    assert values[0] == pytest.approx(exact[first], rel=1e-6)  # on this pool the key loses nothing at the start


def test_the_imprint_is_worth_something_here(world):
    """The world is one where the imprint matters: without it the start costs more."""
    _cap, _ab, first, exact, _model, _values = world
    ab = abstraction(None)
    without = exact_values(ab, ab.compress(START), pattern_offers(None))[ab.compress(START)]
    assert exact[first] < 0.8 * without


def test_the_bound_without_the_imprint_is_no_bound_of_an_item_that_holds_one(world):
    """`min(LB(s), c + LB(h))` with `LB` the value of the item holding no imprint: at a state that holds its own snapshot it is above the exact
    value (by the beast, as in the toy loop of ADR-0060), so the key must hold the snapshot."""
    cap, _ab, _first, exact, _model, _values = world
    above = 0
    for state, value in exact.items():
        if len(state.imprints) != 1:
            continue
        bare = replace(state, imprints=())
        (snapshot,) = state.imprints
        if bare not in exact or snapshot not in exact:
            continue
        proposed = min(exact[bare], FREE + exact[snapshot])
        above += proposed > value * (1 + 1e-6) + 1e-9
    assert above, "no state where the proposed formula is above the exact value"


def _pushed_of(model, kid: int) -> frozenset:
    """The kernel `kid` of a model (or a builder) as a set of (successor key, chance)."""
    successors, weights = model.kernels[kid]
    return frozenset((model.keys[successor], Fraction(weight, sum(weights))) for successor, weight in zip(successors, weights))


def _without_imprints(key):
    return key._replace(held=(*key.held[:IMPRINTS], (), *key.held[IMPRINTS + 1 :]))


def test_the_envelope_search_gives_the_exact_graphs_mean():
    cap = 1
    ab = abstraction(cap)
    first = ab.compress(START)
    exact = exact_values(ab, first, pattern_offers(cap))[first]
    result = envelope_result(ab, first, priced_offers(cap))
    info = result.info["envelope"]
    assert info.exact and info.bound_stopped is None
    assert result.solution.values[first] == pytest.approx(exact, rel=TOLERANCE)
    assert info.lower <= exact * (1 + TOLERANCE)


def test_with_two_imprints_every_move_is_offered_at_its_key():
    """The cap of two: a key holds two snapshot keys in an order of the keys alone, a member holds one snapshot of each, and at the states a
    seeded random walk meets, each imprint (adding or replacing) and each restore a state takes leads to a key the model's move offers at its
    key (`PatternBuilder._move`) or is dominated as above. The restores are matched by the snapshot, not the index."""
    cap = 2
    ab = abstraction(cap)
    first = ab.compress(START)
    offers = pattern_offers(cap)
    builder = PatternBuilder(ab, first)
    builder.offers = list(offers)
    pattern = builder.pattern
    rng = random.Random(833)
    actions = [action for action, _ in offered(cap).values()]
    states = {}
    for _ in range(400):
        state = first
        for _ in range(10):
            states[state] = None
            if ab.is_goal(state):
                break
            try:
                kernel = ab.kernel(state, rng.choice(actions))
            except ActionError:
                continue
            state = rng.choices(list(kernel), weights=[float(chance) for chance in kernel.values()])[0]
    two = same = matched = 0
    for state in states:
        if ab.is_goal(state):
            continue
        key = pattern.key(state)
        two += len(key.held[IMPRINTS]) == 2
        same += len(key.held[IMPRINTS]) == 2 and key.held[IMPRINTS][0] == key.held[IMPRINTS][1]  # two snapshots of one key
        for member in pattern.members(key, Mode.ANY):
            assert pattern.key(member) == key
        offered_here = set()
        for offer in offers:
            move = offer.action.imprint_move() if offer.action is not None else None
            if move is not None and (kid := builder._move(key, offer, move)) is not None:
                offered_here.add(_pushed_of(builder, kid))
        for label, (action, _) in moves(cap).items():
            kernel = pushed(pattern, ab, state, action)
            if kernel is None:
                continue
            (successor,) = kernel
            if successor == key or (label.startswith("Restore") and _without_imprints(successor) == _without_imprints(key)):
                continue
            assert frozenset(kernel.items()) in offered_here, (state, label)
            matched += 1
    assert two and same and matched


def test_the_keys_after_a_fracture_hold_no_imprint_and_after_a_reroll_the_same():
    """What the forgetting rules of `Abstraction._carried` give the key: at the members of a rare Talisman's key that holds its imprint, the
    Fracturing Orb leads only to keys with no imprint (none can be used on a fractured item), a Chaos Orb and an Annulment to keys that hold
    the key's (`test_actions_imprint.py` checks the states themselves)."""
    from abstraction_pool import DAMAGE_1, LIFE_1, MANA_1, RESIST_2
    from test_actions_imprint import ARACHNID, rare, space

    from crafting_system.actions import ChaosOrb, FracturingOrb

    actions = (Imprint(ARACHNID), Restore(0), ChaosOrb(), FracturingOrb(), AnnulmentOrb())
    ab = space(*actions)
    pattern = Pattern(ab, None, actions)
    (held,) = ab.kernel(ab.compress(rare(RESIST_2, LIFE_1, MANA_1, DAMAGE_1)), Imprint(ARACHNID))
    key = pattern.key(held)
    assert len(key.held[IMPRINTS]) == 1
    members = pattern.members(key, Mode.ALL)
    assert members and all(pattern.key(member) == key for member in members)
    fractured = [successor for member in members for successor in pushed(pattern, ab, member, FracturingOrb()) or ()]
    assert fractured and all(successor.fractured and successor.held[IMPRINTS] == () for successor in fractured)
    for action in (ChaosOrb(), AnnulmentOrb()):
        kept = [successor for member in members for successor in pushed(pattern, ab, member, action) or ()]
        assert kept and all(successor.held[IMPRINTS] == key.held[IMPRINTS] for successor in kept)
