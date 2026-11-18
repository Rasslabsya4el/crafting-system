"""Influence mods that every enabled action treats alike share one kind (ticket #1238, root 1).

Under `Reads.influenced` (an Orb of Dominance, an Awakener's Orb) the state named every influence mod by mod (`$<mod id>`, #155), so the
listing draw of an unopened influenced rare drew the influence mods one by one: R20 with the Orb of Dominance grew past 12 GB in one kernel.
The influence mods of one family on one side, of one influence, that give the goal the same, are now one kind when every action that reads
them declares them alike (`Action.influence_alike`), and only under a goal with no roll limit (`Kinds._influence_groups`).

* which mods are grouped, and which stay apart: a goal that tells them apart, a roll limit, an upgrade the data cannot name or that leaves the
  group, an Awakener's Orb whose donor mod is in the group, an action that does not say;
* exact: the solver graph from a start is smaller, and the cheapest expected cost of the goal is the same with the groups and with every mod
  apart, counted in states (no clock); layer 1 of the influence crafts with the groups is `test_abstraction_dominance.py`.
"""

import pytest
from abstraction_b2_support import real_graph
from test_abstraction_dominance import (
    AWAKENERS,
    DATA,
    DOMINANCE,
    ELDER,
    ELDER_S,
    ELDER_S_MAVEN,
    RECIPES,

    MIXED_BEST,
    P1,
    P2,
    P3,
    S1,
    S2,
    S2_MAVEN,
    SHAPER,
    TOP_PREFIX,
    ability,
    starts,
)

from crafting_system.abstraction import Goal, Wanted
from crafting_system.abstraction._kinds import Kinds
from crafting_system.actions import ActionError, AnnulmentOrb, OrbOfDominance

ONE_PREFIX = Goal((TOP_PREFIX,))  # reads the best Shaper prefix only: the Shaper suffixes S1, S2 and the Elevated S2 give it nothing

def kind(found, mod_id, influences=frozenset({SHAPER})):
    return found.kind_of(DATA.mods[mod_id], influences)

def test_the_shaper_suffixes_the_goal_does_not_read_are_one_kind_named_by_the_lowest():
    found = ability((DOMINANCE,), ONE_PREFIX)
    assert kind(found, S1) == kind(found, S2) == kind(found, S2_MAVEN) == f"${S1}"
    assert kind(found, P3) == f"${P3}"  # the goal reads it

def test_a_group_whose_upgrade_leaves_it_stays_apart():
    found = ability((DOMINANCE,), ONE_PREFIX)
    # P1 and P2 give the goal nothing, but the Orb of Dominance upgrades P2 to P3, which the goal reads
    assert len({kind(found, P1), kind(found, P2), kind(found, P3)}) == 3

def test_a_goal_that_tells_the_mods_apart_keeps_them_apart():
    found = ability((DOMINANCE,), Goal((Wanted(frozenset({S2, S2_MAVEN})),)))
    assert kind(found, S1) == f"${S1}"
    assert kind(found, S2) == kind(found, S2_MAVEN) == f"${S2}"  # both pass: one group

def test_a_roll_limit_keeps_every_mod_apart():
    with_roll = Goal((TOP_PREFIX, Wanted(frozenset({S2}), min_roll=(1,))))
    found = ability((DOMINANCE,), with_roll)
    assert len({kind(found, S1), kind(found, S2), kind(found, S2_MAVEN)}) == 3

def test_an_upgrade_the_data_cannot_name_keeps_the_group_apart():
    no_elevated = OrbOfDominance(elevated=())  # S2 is a top tier with no Elevated version known
    found = ability((no_elevated,), ONE_PREFIX)
    assert kind(found, S1) != kind(found, S2)

def test_an_awakeners_orb_whose_donor_mod_is_in_the_group_keeps_it_apart():
    elder_donor = AWAKENERS[0]  # its donor holds ELDER_S
    assert kind(ability((DOMINANCE, elder_donor), ONE_PREFIX), ELDER_S, frozenset({ELDER})) == f"${ELDER_S}"
    assert kind(ability((DOMINANCE, elder_donor), ONE_PREFIX), ELDER_S_MAVEN, frozenset({ELDER})) == f"${ELDER_S_MAVEN}"
    assert kind(ability((DOMINANCE, AWAKENERS[1]), ONE_PREFIX), S2) == f"${S1}"  # a donor of P3: the Shaper suffixes stay one group

def test_an_action_that_reads_the_influence_mods_and_does_not_say_keeps_them_apart(monkeypatch):
    monkeypatch.setattr(OrbOfDominance, "influence_alike", lambda self, data, item, mods: False)
    found = ability((DOMINANCE,), ONE_PREFIX)
    assert kind(found, S1) == f"${S1}" and kind(found, S2) == f"${S2}"

def test_an_item_without_influence_has_the_kinds_it_had():
    found = ability((DOMINANCE,), ONE_PREFIX)
    assert found.kind_of(DATA.mods[S1]) == found.kind_of(DATA.mods[S1], frozenset())  # no influence: S1 is no influence mod there
    assert not found.kind_of(DATA.mods[S1]).startswith("$")

# --- exact: the cheapest cost is the cost with every mod apart ------------------------------------------------------------

PRICES = {DOMINANCE: 7.0, RECIPES[0]: 3.0, RECIPES[1]: 2.0}

def cheapest(found, start, actions) -> tuple[float, int]:
    """The least expected cost of the goal from `start` over the graph the kernels make (value iteration from below to its fixed point), and its states."""
    seen, _ = real_graph(found, [start], actions)
    kernels = {}
    for state in seen:
        if found.is_goal(state):
            continue
        for action in actions:
            try:
                kernels[state, action] = found.kernel(state, action)
            except ActionError:
                continue
    value = dict.fromkeys(seen, 0.0)  # from below: each sweep raises a value toward the least expected cost (every price is positive)
    for _ in range(200_000):
        changed = 0.0
        for state in seen:
            if found.is_goal(state):
                continue
            best = min(
                (PRICES.get(action, 1.0) + sum(float(chance) * value[after] for after, chance in kernel.items())
                 for (at, action), kernel in kernels.items() if at == state),
                default=float("inf"),
            )
            changed = max(changed, abs(best - value[state]))
            value[state] = best
        if changed < 1e-11:
            break
    return value[start], len(seen)

@pytest.mark.parametrize("goal", [ONE_PREFIX, Goal((MIXED_BEST,))], ids=["top_prefix", "mixed_tier"])
@pytest.mark.parametrize("name", ["two_shaper", "mixed_shaper"])
def test_the_cheapest_cost_with_the_groups_is_the_cost_with_every_mod_apart(goal, name, monkeypatch):
    actions = (DOMINANCE, *RECIPES, AnnulmentOrb())  # the recipes add influence mods to an influenced item, which the orbs refuse
    item = starts()[name]
    grouped = ability(actions, goal)
    cost, states = cheapest(grouped, grouped.compress(item), actions)
    with monkeypatch.context() as apart:
        apart.setattr(Kinds, "_influence_groups", lambda self: {})
        whole = ability(actions, goal)
        cost_apart, states_apart = cheapest(whole, whole.compress(item), actions)
    assert cost == pytest.approx(cost_apart, rel=1e-9, abs=1e-12) and cost < float("inf")
    assert states < states_apart  # the groups made the graph smaller
